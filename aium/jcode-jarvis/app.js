(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  // VAD: RMS gate, ~0.8 s of silence, ~15 s max utterance.
  const THRESHOLD = 0.025;
  const SILENCE_FRAMES = 6;
  const MIN_FRAMES = 3;
  const MAX_FRAMES = 120;
  const RING = 2 * Math.PI * 54;

  const state = {
    enabled: false,
    ui: "idle",
    lang: "auto",
    settings: null,
    events: [],
    turns: [],
    liveUser: "",
    liveReply: "",
    ctx: null,
    stream: null,
    source: null,
    processor: null,
    frames: [],
    speaking: false,
    silence: 0,
    lastDone: null,
    audioQueue: [],
    playing: false,
    fallbackCount: 0,
    currentAudio: null,
    turnAbort: null,
    token: localStorage.getItem("jarvis_token") || "",
    sampleRate: 16000,
    stageTimer: null,
    stageStart: 0,
    lastStage: "",
    level: 0,
    deviceId: localStorage.getItem("jarvis_device") || "",
    lastMicError: "",
    tab: "brain",
    // Forms load once so unsaved edits survive tab switches.
    settingsLoaded: false,
    brainLoaded: false,
  };

  const MIC_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3z"/><path d="M5 11a7 7 0 0 0 14 0"/><path d="M12 18v3"/><path d="M9 21h6"/></svg>';
  const icons = {
    speaking: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 9v6h4l5 4V5L8 9H4z"/><path d="M16 8.5a5 5 0 0 1 0 7"/><path d="M19 6a9 9 0 0 1 0 12"/></svg>',
  };

  function setState(ui, text) {
    state.ui = ui;
    document.body.dataset.state = ui;
    $("status").textContent = text;
    $("stateChip").textContent = text;
    $("stateChip").dataset.state = ui;
    $("orb").setAttribute("aria-label", ui === "idle" ? "Start session" : "End session");
    $("orb").innerHTML = icons[ui] || MIC_ICON;
    $("sessionBtn").textContent = state.enabled ? "Stop" : "Start";
    $("sessionBtn").setAttribute("aria-label", state.enabled ? "Stop session" : "Start session");
    $("cancelBtn").hidden = ui !== "thinking";
    if (ui !== "thinking") {
      stopStageTimer();
      $("activity").textContent = "";
    }
  }

  function showBanner(message) {
    const el = $("banner");
    el.textContent = message;
    el.dataset.show = message ? "true" : "false";
  }

  function money(value) {
    if (value === null || value === undefined) return "—";
    if (value === 0) return "$0.00";
    if (value < 0.0001) return "<$0.0001";
    return "~$" + value.toFixed(value < 0.01 ? 6 : 4).replace(/0+$/, "").replace(/\.$/, "");
  }

  function num(value) {
    const n = Number(value || 0);
    if (n >= 1000000) return (n / 1000000).toFixed(1) + "M";
    if (n >= 1000) return (n / 1000).toFixed(1) + "k";
    return String(n);
  }

  function ms(value) {
    const n = Number(value || 0);
    return n >= 1000 ? (n / 1000).toFixed(1) + "s" : n + "ms";
  }

  function bytes(value) {
    const n = Number(value || 0);
    if (n >= 1048576) return (n / 1048576).toFixed(1) + " MB";
    if (n >= 1024) return (n / 1024).toFixed(0) + " kB";
    return n + " B";
  }

  function uptime(seconds) {
    const s = Number(seconds || 0);
    if (s >= 86400) return Math.floor(s / 86400) + "d " + Math.floor((s % 86400) / 3600) + "h";
    if (s >= 3600) return Math.floor(s / 3600) + "h " + Math.floor((s % 3600) / 60) + "m";
    if (s >= 60) return Math.floor(s / 60) + "m";
    return s + "s";
  }

  async function api(path, options = {}) {
    const headers = new Headers(options.headers || {});
    if (state.token) headers.set("Authorization", "Bearer " + state.token);
    const init = { ...options, headers };
    if (options.body && !headers.has("Content-Type") && typeof options.body === "string") {
      headers.set("Content-Type", "application/json");
    }
    const response = await fetch(path, init);
    if (response.status === 401) {
      showBanner("Access token needed. Open System and save it.");
      throw new Error("Unauthorized");
    }
    if (!response.ok) {
      let message = "Request failed";
      try { message = (await response.json()).error || message; } catch (_) {}
      throw new Error(message);
    }
    return response;
  }

  async function download(path, filename) {
    const response = await api(path);
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  }

  /* ---------- transcript ---------- */

  function messageEl(role, text, live) {
    const wrap = document.createElement("div");
    wrap.className = "msg " + (role === "assistant" ? "jarvis" : role);
    const who = document.createElement("div");
    who.className = "who";
    who.textContent = role === "assistant" ? "Jarvis" : role === "user" ? "You" : role;
    const body = document.createElement("div");
    body.className = "body";
    if (live) {
      body.id = "liveReplyBody";
      body.textContent = text;
    } else {
      appendRichText(body, text);
    }
    wrap.append(who, body);
    return wrap;
  }

  function textSegment(text) {
    const node = document.createElement("div");
    node.className = "seg";
    node.textContent = text;
    return node;
  }

  function appendRichText(container, text) {
    const fence = /```mermaid[ \t]*\r?\n([\s\S]*?)```/gi;
    let last = 0;
    let match;
    while ((match = fence.exec(text || ""))) {
      if (match.index > last) container.appendChild(textSegment(text.slice(last, match.index)));
      const code = (match[1] || "").trim();
      if (code) {
        const diagram = document.createElement("div");
        diagram.className = "mermaid";
        diagram.tabIndex = 0;
        diagram.setAttribute("role", "img");
        diagram.setAttribute("aria-label", "Diagram");
        diagram.textContent = code;
        diagram.dataset.code = code;
        container.appendChild(diagram);
      }
      last = fence.lastIndex;
    }
    const rest = (text || "").slice(last);
    if (rest || last === 0) container.appendChild(textSegment(rest));
  }

  let mermaidPromise = null;

  // The 2.7 MB renderer loads only when a reply actually contains a diagram.
  function loadMermaid() {
    if (window.mermaid) return Promise.resolve(window.mermaid);
    if (!mermaidPromise) {
      mermaidPromise = new Promise((resolve, reject) => {
        const script = document.createElement("script");
        script.src = "/vendor/mermaid.min.js";
        script.onload = () => {
          try {
            window.mermaid.initialize({
              startOnLoad: false,
              securityLevel: "strict",
              theme: window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "neutral",
            });
            resolve(window.mermaid);
          } catch (error) {
            reject(error);
          }
        };
        script.onerror = () => reject(new Error("mermaid failed to load"));
        document.head.appendChild(script);
      });
    }
    return mermaidPromise;
  }

  function renderDiagrams(root) {
    const nodes = root.querySelectorAll(".mermaid[data-code]");
    if (!nodes.length) return;
    loadMermaid().then((lib) => {
      nodes.forEach((node) => {
        const code = node.dataset.code;
        if (!code) return;
        delete node.dataset.code;
        const id = "mmd" + Math.random().toString(36).slice(2);
        Promise.resolve(lib.render(id, code)).then((result) => {
          node.innerHTML = result.svg;
          const svg = node.querySelector("svg");
          if (svg && svg.viewBox && svg.viewBox.baseVal && svg.viewBox.baseVal.width) {
            const box = svg.viewBox.baseVal;
            const width = Math.round(Math.min(Math.max(box.width, 260), 1100));
            svg.style.maxWidth = "none";
            svg.style.width = width + "px";
            svg.style.height = "auto";
          }
          node.classList.add("rendered");
        }).catch(() => {
          node.textContent = code;
          node.classList.add("failed");
        });
      });
    }).catch(() => {
      nodes.forEach((node) => {
        if (!node.dataset.code) return;
        node.textContent = node.dataset.code;
        delete node.dataset.code;
        node.classList.add("failed");
      });
    });
  }

  function nearBottom(box) {
    return box.scrollHeight - box.scrollTop - box.clientHeight < 48;
  }

  function renderTranscript() {
    const box = $("transcript");
    const stick = nearBottom(box);
    box.innerHTML = "";
    if (!state.turns.length && !state.liveUser && !state.liveReply) {
      const empty = document.createElement("p");
      empty.className = "empty";
      empty.textContent = "Press Start or Space, then speak. You can also type below.";
      box.appendChild(empty);
      return;
    }
    // Server caps history at 50; render oldest to newest.
    state.turns.forEach((turn) => box.appendChild(messageEl(turn.role, turn.text)));
    if (state.liveUser) box.appendChild(messageEl("user", state.liveUser));
    if (state.liveReply) box.appendChild(messageEl("assistant", state.liveReply, true));
    renderDiagrams(box);
    if (stick) box.scrollTop = box.scrollHeight;
  }

  function updateBreakdown(turn) {
    const el = $("breakdown");
    const data = turn || state.lastDone || [...state.turns].reverse().find((t) => t.role === "assistant");
    if (!data) { el.textContent = ""; return; }
    const t = data.timings || data;
    const usage = data.usage || data;
    const input = usage.input_tokens || 0;
    const output = usage.output_tokens || 0;
    const parts = [
      ["STT", ms(t.stt_ms)],
      ["first token", ms(t.ttft_ms)],
      ["total", ms(t.total_ms)],
      ["tokens", num(input + output)],
      ["cost", money(data.cost_usd)],
      ["brain", (data.provider || "—") + "/" + (data.model || "—")],
    ];
    el.innerHTML = "";
    parts.forEach(([key, value]) => {
      const span = document.createElement("span");
      const bold = document.createElement("b");
      bold.textContent = key;
      span.append(bold, document.createTextNode(value));
      el.appendChild(span);
    });
  }

  /* ---------- mic + session ---------- */

  function setLevel(value) {
    const level = Math.max(0, Math.min(1, value));
    state.level = level;
    const ring = $("levelRing");
    ring.style.strokeDasharray = String(RING);
    ring.style.strokeDashoffset = String(RING * (1 - level * 0.92));
    $("micBar").style.width = Math.round(level * 100) + "%";
  }

  async function startSession(forceDefault = false) {
    if (state.enabled) return;
    showBanner("");
    if (!window.isSecureContext) {
      const message = "Browsers allow the microphone only on https:// or localhost. Open this page at http://localhost" + (location.port ? ":" + location.port : "") + " on the server, or serve it over HTTPS.";
      state.lastMicError = message;
      setState("error", "Microphone blocked");
      showBanner(message);
      refreshMicDiag();
      return;
    }
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error("Microphone is not available in this browser.");
      const audio = { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 };
      if (state.deviceId && !forceDefault) audio.deviceId = { exact: state.deviceId };
      const stream = await navigator.mediaDevices.getUserMedia({ audio });
      state.stream = stream;
      state.ctx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
      await state.ctx.resume();
      state.sampleRate = state.ctx.sampleRate;
      state.source = state.ctx.createMediaStreamSource(stream);
      state.processor = state.ctx.createScriptProcessor(2048, 1, 1);
      state.processor.onaudioprocess = onAudio;
      state.source.connect(state.processor);
      state.processor.connect(state.ctx.destination);
      state.enabled = true;
      state.frames = [];
      state.speaking = false;
      state.silence = 0;
      state.lastMicError = "";
      setState("listening", "Listening");
      await api("/api/session", { method: "POST", body: JSON.stringify({ enabled: true }) });
      refreshMics();
      refreshMicDiag();
    } catch (error) {
      stopCapture();
      if (!forceDefault && state.deviceId && (error.name === "OverconstrainedError" || error.name === "NotFoundError")) {
        state.deviceId = "";
        localStorage.removeItem("jarvis_device");
        refreshMics();
        return startSession(true);
      }
      state.enabled = false;
      setLevel(0);
      setState("error", "Microphone blocked");
      state.lastMicError = (error.name ? error.name + ": " : "") + (error.message || "unknown error");
      const denied = error.name === "NotAllowedError" || error.name === "SecurityError";
      showBanner(denied
        ? "Microphone blocked. Allow it in site settings. If this page is embedded in another app, open it in its own tab."
        : (error.message || "Allow microphone access in the browser."));
      refreshMicDiag();
    }
  }

  async function stopSession() {
    if (!state.enabled) return;
    state.enabled = false;
    stopCapture();
    stopPlayback();
    setLevel(0);
    setState("idle", "Ready");
    try { await api("/api/session", { method: "POST", body: JSON.stringify({ enabled: false }) }); } catch (_) {}
  }

  function toggleSession() {
    if (state.enabled) stopSession(); else startSession();
  }

  function stopCapture() {
    if (state.processor) { try { state.processor.disconnect(); } catch (_) {} }
    if (state.source) { try { state.source.disconnect(); } catch (_) {} }
    if (state.stream) state.stream.getTracks().forEach((track) => track.stop());
    if (state.ctx) { try { state.ctx.close(); } catch (_) {} }
    state.processor = null;
    state.source = null;
    state.stream = null;
    state.ctx = null;
    state.frames = [];
    state.speaking = false;
    state.silence = 0;
  }

  function resample(input, from, to) {
    if (from === to) return input;
    const ratio = from / to;
    const length = Math.floor(input.length / ratio);
    const out = new Float32Array(length);
    for (let i = 0; i < length; i += 1) {
      const position = i * ratio;
      const index = Math.floor(position);
      const fraction = position - index;
      const a = input[index] || 0;
      const b = input[index + 1] || a;
      out[i] = a + (b - a) * fraction;
    }
    return out;
  }

  function onAudio(event) {
    if (!state.enabled || !state.processor) return;
    const raw = event.inputBuffer.getChannelData(0);
    const input = state.sampleRate === 16000 ? raw : resample(raw, state.sampleRate, 16000);
    const output = event.outputBuffer.getChannelData(0);
    output.fill(0);
    let sum = 0;
    const pcm = new Int16Array(input.length);
    for (let i = 0; i < input.length; i += 1) {
      const sample = Math.max(-1, Math.min(1, input[i]));
      pcm[i] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
      sum += sample * sample;
    }
    const rms = Math.sqrt(sum / input.length);
    setLevel(state.level * 0.7 + Math.min(1, rms * 4) * 0.3);

    if (state.ui === "speaking" && rms > 0.04) {
      stopPlayback();
      if (state.turnAbort) {
        state.turnAbort.abort();
        state.turnAbort = null;
      }
      api("/api/cancel", { method: "POST" }).catch(() => {});
      setState("listening", "Listening");
      state.frames = [];
      state.speaking = false;
      state.silence = 0;
    }
    if (state.ui === "thinking") return;

    if (rms > THRESHOLD) {
      state.speaking = true;
      state.silence = 0;
      state.frames.push(pcm);
      if (state.frames.length > MAX_FRAMES) finalizeUtterance();
    } else if (state.speaking) {
      state.silence += 1;
      state.frames.push(pcm);
      if (state.silence >= SILENCE_FRAMES) finalizeUtterance();
    }
  }

  function finalizeUtterance() {
    const frames = state.frames;
    state.frames = [];
    state.speaking = false;
    state.silence = 0;
    if (frames.length < MIN_FRAMES) return;
    let length = 0;
    frames.forEach((frame) => { length += frame.length; });
    const pcm = new Int16Array(length);
    let offset = 0;
    frames.forEach((frame) => { pcm.set(frame, offset); offset += frame.length; });
    setState("thinking", "Thinking");
    startStageTimer("Transcribing");
    sendTurn(pcm, null);
  }

  /* ---------- turn ---------- */

  async function sendTurn(pcm, text) {
    if (state.turnAbort) state.turnAbort.abort();
    const controller = new AbortController();
    state.turnAbort = controller;
    state.liveUser = "";
    state.liveReply = "";
    renderTranscript();
    let reply = "";
    let lang = state.lang;
    try {
      const headers = { "X-Lang": state.lang, "Accept": "text/event-stream" };
      let body;
      if (pcm) {
        headers["Content-Type"] = "application/octet-stream";
        body = pcm.buffer;
      } else {
        headers["Content-Type"] = "application/json";
        body = JSON.stringify({ text, lang: state.lang });
      }
      const response = await api("/api/turn?stream=1", { method: "POST", headers, body, signal: controller.signal });
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let index;
        while ((index = buffer.indexOf("\n\n")) >= 0) {
          const block = buffer.slice(0, index);
          buffer = buffer.slice(index + 2);
          for (const line of block.split("\n")) {
            if (!line.startsWith("data:")) continue;
            const data = line.slice(5).trim();
            if (!data) continue;
            let event;
            try { event = JSON.parse(data); } catch (_) { continue; }
            if (event.type === "transcript") {
              lang = event.lang || lang;
              state.liveUser = event.text;
              renderTranscript();
            } else if (event.type === "stage") {
              startStageTimer(event.stage === "transcribing" ? "Transcribing" : "Thinking");
            } else if (event.type === "delta") {
              reply += event.text || "";
              state.liveReply = reply;
              const live = $("liveReplyBody");
              if (live) {
                const box = $("transcript");
                const stick = nearBottom(box);
                live.textContent = reply;
                if (stick) box.scrollTop = box.scrollHeight;
              } else {
                renderTranscript();
              }
            } else if (event.type === "sentence") {
              if (event.audio) enqueueAudio(event.audio);
              else if (state.settings?.tts !== false) speakFallback(event.text, lang);
            } else if (event.type === "done") {
              reply = event.reply || reply;
              state.liveUser = "";
              state.liveReply = "";
              state.lastDone = event;
              updateBreakdown(event);
              $("topSpend").textContent = money(event.session_cost_usd);
              clearActivity();
              if (event.action === "end") stopSession();
              else if (event.action === "stop") stopPlayback();
              else maybeIdle();
              await refreshHistory();
              refreshStatusSoon();
            } else if (event.type === "error") {
              showBanner(event.message || "Jarvis could not answer.");
              state.liveReply = "";
              clearActivity();
              setState(state.enabled ? "listening" : "idle", state.enabled ? "Listening" : "Ready");
            }
          }
        }
      }
    } catch (error) {
      if (error.name === "AbortError") return;
      showBanner(error.message || "Request failed.");
      state.liveReply = "";
      clearActivity();
      setState(state.enabled ? "listening" : "idle", state.enabled ? "Listening" : "Ready");
    } finally {
      if (state.turnAbort === controller) state.turnAbort = null;
    }
  }

  function cancelTurn() {
    if (state.turnAbort) {
      state.turnAbort.abort();
      state.turnAbort = null;
    }
    api("/api/cancel", { method: "POST" }).catch(() => {});
    stopPlayback();
    state.liveReply = "";
    clearActivity();
    setState(state.enabled ? "listening" : "idle", state.enabled ? "Listening" : "Ready");
  }

  function startStageTimer(label) {
    stopStageTimer();
    state.stageStart = performance.now();
    state.lastStage = label || "";
    const tick = () => {
      const elapsed = (performance.now() - state.stageStart) / 1000;
      $("activity").textContent = (state.lastStage || "Thinking") + " " + elapsed.toFixed(1) + "s";
    };
    tick();
    state.stageTimer = setInterval(tick, 100);
  }

  function stopStageTimer() {
    if (state.stageTimer) clearInterval(state.stageTimer);
    state.stageTimer = null;
  }

  function clearActivity() {
    stopStageTimer();
    $("activity").textContent = "";
  }

  /* ---------- playback ---------- */

  function enqueueAudio(base64) {
    try {
      const binary = atob(base64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
      const url = URL.createObjectURL(new Blob([bytes], { type: "audio/wav" }));
      state.audioQueue.push(url);
      playNext();
    } catch (_) {}
  }

  function playNext() {
    if (state.playing) return;
    if (!state.audioQueue.length) {
      maybeIdle();
      return;
    }
    const url = state.audioQueue.shift();
    state.playing = true;
    state.frames = [];
    state.speaking = false;
    state.silence = 0;
    setState("speaking", "Speaking");
    const audio = new Audio(url);
    state.currentAudio = audio;
    audio.onended = () => {
      URL.revokeObjectURL(url);
      state.playing = false;
      state.currentAudio = null;
      playNext();
    };
    audio.onerror = () => {
      URL.revokeObjectURL(url);
      state.playing = false;
      state.currentAudio = null;
      playNext();
    };
    audio.play().catch(() => {
      state.playing = false;
      state.currentAudio = null;
      playNext();
    });
  }

  function speakFallback(text, lang) {
    if (!("speechSynthesis" in window)) return;
    state.frames = [];
    state.speaking = false;
    state.silence = 0;
    state.fallbackCount += 1;
    state.playing = true;
    setState("speaking", "Speaking");
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = lang === "fr" ? "fr-FR" : "en-US";
    utterance.onend = () => {
      state.fallbackCount = Math.max(0, state.fallbackCount - 1);
      if (state.fallbackCount === 0) state.playing = false;
      maybeIdle();
    };
    utterance.onerror = utterance.onend;
    window.speechSynthesis.speak(utterance);
  }

  function maybeIdle() {
    if (state.playing || state.audioQueue.length || state.fallbackCount) return;
    setState(state.enabled ? "listening" : "idle", state.enabled ? "Listening" : "Ready");
  }

  function stopPlayback() {
    state.audioQueue = [];
    state.fallbackCount = 0;
    if (state.currentAudio) {
      try { state.currentAudio.pause(); } catch (_) {}
      state.currentAudio = null;
    }
    state.playing = false;
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    maybeIdle();
  }

  /* ---------- data refresh ---------- */

  let statusTimer = null;
  function refreshStatusSoon() {
    if (statusTimer) return;
    statusTimer = setTimeout(() => {
      statusTimer = null;
      refreshStatus();
    }, 400);
  }

  async function refreshStatus() {
    try {
      const data = await (await api("/api/status")).json();
      $("topBrain").textContent = (data.brain?.provider || "—") + "/" + (data.brain?.model || "—");
      $("topBrain").title = $("topBrain").textContent;
      $("topSpend").textContent = money(data.spend_today ?? data.cost_usd);
      if ($("stateChip").textContent === "Offline") {
        const labels = { idle: "Ready", listening: "Listening", thinking: "Thinking", speaking: "Speaking", error: "Microphone blocked" };
        $("stateChip").textContent = labels[state.ui] || "Ready";
        $("stateChip").dataset.state = state.ui;
      }
      if (!data.brain) return;
      // System rows are only visible on that tab; skip the rebuild otherwise.
      if (state.tab !== "system") return;
      const rows = [
        ["State", data.state],
        ["Session", data.session_id],
        ["Turns", data.turns],
        ["Facts", data.facts],
        ["Profile", data.profile],
        ["Version", data.version || "—"],
        ["Arch", data.arch || "—"],
        ["Uptime", data.uptime_s !== undefined ? uptime(data.uptime_s) : "—"],
        ["Database", bytes(data.db_bytes)],
        ["Started", data.started_at || "—"],
        ["Brain", (data.brain.provider || "—") + "/" + (data.brain.model || "—")],
      ];
      $("sysRows").innerHTML = "";
      rows.forEach(([key, value]) => $("sysRows").appendChild(rowEl(key, value)));
    } catch (_) {
      $("stateChip").textContent = "Offline";
      $("stateChip").dataset.state = "error";
    }
  }

  function rowEl(key, value, node) {
    const row = document.createElement("div");
    row.className = "row";
    const k = document.createElement("span");
    k.className = "k";
    k.textContent = key;
    const v = document.createElement("span");
    v.className = "v";
    if (node) v.appendChild(node); else v.textContent = value === undefined || value === null || value === "" ? "—" : String(value);
    row.append(k, v);
    return row;
  }

  async function refreshHealth() {
    try {
      const data = await (await api("/api/health")).json();
      const items = [["whisper", "Whisper", "dotWhisper"], ["piper", "Piper", "dotPiper"], ["jcode", "jcode", "dotJcode"], ["db", "Database", "dotDb"]];
      $("healthRows").innerHTML = "";
      items.forEach(([key, label, dotId]) => {
        const ok = Boolean(data[key]);
        const dot = $(dotId);
        dot.dataset.ok = String(ok);
        dot.setAttribute("aria-label", label + ": " + (ok ? "ok" : "off"));
        const pill = document.createElement("span");
        pill.className = "pill " + (ok ? "ok" : "bad");
        pill.textContent = ok ? "ok" : "off";
        $("healthRows").appendChild(rowEl(label, "", pill));
      });
      const brain = document.createElement("div");
      brain.className = "row";
      brain.innerHTML = '<span class="k">Brain</span><span class="v">' + escapeHtml(data.brain || "—") + "</span>";
      $("healthRows").appendChild(brain);
    } catch (_) {}
  }

  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  async function refreshEvents() {
    try {
      const data = await (await api("/api/events")).json();
      state.events = data.events || [];
      const feed = $("eventFeed");
      feed.innerHTML = "";
      state.events.slice(0, 40).forEach((event) => {
        const row = document.createElement("div");
        row.className = "ev";
        row.dataset.level = event.level || "info";
        const time = document.createElement("time");
        time.textContent = (event.ts || "").slice(11, 19);
        row.append(time, document.createTextNode(event.event + (event.detail ? " · " + event.detail : "")));
        feed.appendChild(row);
      });
      if (state.tab === "logs") renderLogs();
      $("logStatus").textContent = state.events.length + " events";
      if (!state.events.length) {
        const empty = document.createElement("p");
        empty.className = "hint";
        empty.textContent = "No activity yet. Turns and supervisor messages appear here.";
        feed.appendChild(empty);
      }
    } catch (_) {}
  }

  function renderLogs() {
    const level = $("logLevel").value;
    const list = $("logList");
    list.innerHTML = "";
    state.events.filter((event) => level === "all" || event.level === level).forEach((event) => {
      const row = document.createElement("div");
      row.dataset.level = event.level || "info";
      row.textContent = (event.ts || "").slice(11, 19) + " " + (event.level || "info").toUpperCase() + " " + event.event + (event.detail ? " · " + event.detail : "");
      list.appendChild(row);
    });
    if (!list.children.length) list.textContent = "No events at this level.";
  }

  async function refreshHistory() {
    try {
      const data = await (await api("/api/history?limit=50")).json();
      state.turns = data.turns || [];
      renderTranscript();
      updateBreakdown();
    } catch (_) {}
  }

  async function refreshBrain(provider) {
    try {
      const suffix = provider ? "?provider=" + encodeURIComponent(provider) : "";
      const data = await (await api("/api/brain" + suffix)).json();
      const providers = (data.providers || []).map((line) => {
        const parts = line.split("\t");
        return { id: parts[0], label: parts[1] || parts[0] };
      });
      fillSelect($("provider"), providers, data.config?.provider || "");
      fillSelect($("modelSel"), (data.models || []).map((m) => ({ value: m, label: m })), data.config?.model || "");
      $("brainStatus").textContent = "Current: " + (data.config?.provider || "—") + "/" + (data.config?.model || "—");
      $("brainFallback").textContent = (data.config?.fallback || []).join(", ") || "none";
      state.brainLoaded = true;
    } catch (error) {
      $("brainStatus").textContent = error.message;
    }
  }

  function fillSelect(select, items, current) {
    select.innerHTML = "";
    const seen = new Set();
    if (current && !items.some((item) => item.value === current)) {
      items = [{ value: current, label: current + " (current)" }, ...items];
    }
    items.forEach((item) => {
      if (seen.has(item.value)) return;
      seen.add(item.value);
      const option = document.createElement("option");
      option.value = item.value;
      option.textContent = item.label;
      if (item.value === current) option.selected = true;
      select.appendChild(option);
    });
    if (!items.length) {
      const option = document.createElement("option");
      option.value = current || "";
      option.textContent = current || "—";
      select.appendChild(option);
    }
  }

  async function refreshSettings() {
    try {
      const data = await (await api("/api/settings")).json();
      state.settings = data;
      state.lang = data.lang || "auto";
      $("langChip").textContent = state.lang === "auto" ? "Auto" : state.lang.toUpperCase();
      $("langSel").value = state.lang;
      $("ttsSel").value = data.tts === false ? "off" : "on";
      $("voiceEn").value = data.voice_en || "";
      $("voiceFr").value = data.voice_fr || "";
      $("voiceModel").textContent = data.whisper_model || "—";
      $("voiceProfile").textContent = data.profile || "—";
      state.settingsLoaded = true;
    } catch (_) {}
  }

  async function saveSettings(partial) {
    try {
      const data = await (await api("/api/settings", { method: "POST", body: JSON.stringify(partial) })).json();
      state.settings = data;
      state.lang = data.lang || state.lang;
      $("langChip").textContent = state.lang === "auto" ? "Auto" : state.lang.toUpperCase();
      $("voiceStatus").textContent = "Saved. Applies to the next turn.";
      const sync = { lang: $("langSel"), tts: $("ttsSel"), voice_en: $("voiceEn"), voice_fr: $("voiceFr") };
      Object.keys(partial).forEach((key) => {
        if (key === "lang") sync.lang.value = data.lang;
        else if (key === "tts") sync.tts.value = data.tts === false ? "off" : "on";
        else if (key === "voice_en") sync.voice_en.value = data.voice_en || "";
        else if (key === "voice_fr") sync.voice_fr.value = data.voice_fr || "";
      });
      return data;
    } catch (error) {
      $("voiceStatus").textContent = error.message;
      showBanner(error.message);
      return null;
    }
  }

  async function refreshCost() {
    try {
      const cost = await (await api("/api/cost?days=7")).json();
      $("costToday").textContent = money(cost.today);
      $("costSession").textContent = money(cost.session);
      $("costLast").textContent = money(cost.last);
      const days = cost.days || [];
      const total = days.reduce((sum, day) => sum + Number(day.cost_usd || 0), 0);
      $("costChart").innerHTML = "";
      $("costChart").classList.toggle("empty", total <= 0);
      if (total <= 0) {
        const empty = document.createElement("p");
        empty.className = "hint";
        empty.textContent = "No cloud spend in the last 7 days. Local speech and routing are free.";
        $("costChart").appendChild(empty);
      }
      const max = Math.max(0.000001, ...days.map((d) => Number(d.cost_usd || 0)));
      if (total > 0) days.forEach((day) => {
        const bar = document.createElement("div");
        bar.className = "bar";
        bar.title = day.date + ": " + money(day.cost_usd) + " · " + day.turns + " turns";
        const fill = document.createElement("div");
        fill.className = "fill";
        fill.style.height = Math.max(2, Math.round((Number(day.cost_usd || 0) / max) * 68)) + "px";
        fill.style.display = Number(day.cost_usd || 0) > 0 ? "" : "none";
        const label = document.createElement("div");
        label.className = "lbl";
        label.textContent = (day.date || "").slice(5);
        bar.append(fill, label);
        $("costChart").appendChild(bar);
      });
      const history = await (await api("/api/history?limit=100&all=1")).json();
      const rows = (history.turns || []).filter((turn) => turn.role === "assistant").slice(-20).reverse();
      const body = $("costTable");
      body.innerHTML = "";
      rows.forEach((turn) => {
        const tr = document.createElement("tr");
        const tokens = (Number(turn.input_tokens) || 0) + (Number(turn.output_tokens) || 0);
        [[(turn.ts || "").slice(11, 19)], [(turn.provider || "") + "/" + (turn.model || "")], [ms(turn.total_ms), "num"], [num(tokens), "num"], [money(turn.cost_usd), "num"]].forEach(([value, cls]) => {
          const td = document.createElement("td");
          if (cls) td.className = cls;
          td.textContent = value;
          tr.appendChild(td);
        });
        body.appendChild(tr);
      });
      if (!rows.length) body.innerHTML = '<tr><td colspan="5">No turns yet.</td></tr>';
    } catch (error) {
      $("costToday").textContent = error.message;
    }
  }

  async function refreshFacts() {
    try {
      const data = await (await api("/api/facts?limit=200")).json();
      const facts = data.facts || [];
      const list = $("factList");
      list.innerHTML = "";
      facts.forEach((fact) => {
        const li = document.createElement("li");
        const text = document.createElement("span");
        text.className = "text";
        text.textContent = fact.text;
        const button = document.createElement("button");
        button.className = "act tiny danger";
        button.textContent = "Forget";
        button.dataset.id = fact.id;
        button.setAttribute("aria-label", "Forget: " + fact.text);
        li.append(text, button);
        list.appendChild(li);
      });
      if (!facts.length) {
        const li = document.createElement("li");
        li.className = "hint";
        li.textContent = "No facts yet. Say \"remember that ...\" or add one above.";
        list.appendChild(li);
      }
      $("memoryStatus").textContent = (data.count ?? facts.length) + " facts";
    } catch (error) {
      $("memoryStatus").textContent = error.message;
    }
  }

  async function refreshMics() {
    const select = $("micSel");
    if (!navigator.mediaDevices?.enumerateDevices) {
      select.innerHTML = "<option>Not available</option>";
      select.disabled = true;
      return;
    }
    try {
      const devices = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === "audioinput");
      select.innerHTML = "";
      select.appendChild(new Option("System default", ""));
      devices.forEach((device, index) => {
        select.appendChild(new Option(device.label || "Microphone " + (index + 1), device.deviceId));
      });
      select.value = state.deviceId;
      select.disabled = devices.length === 0;
    } catch (_) {}
  }

  async function refreshMicDiag() {
    const box = $("micDiag");
    const rows = [
      ["Origin", location.origin],
      ["Secure context", window.isSecureContext ? "yes" : "no"],
    ];
    let permission = "unknown";
    try {
      const status = await navigator.permissions.query({ name: "microphone" });
      permission = status.state;
    } catch (_) {}
    rows.push(["Mic permission", permission]);
    if (state.lastMicError) rows.push(["Last error", state.lastMicError]);
    box.innerHTML = "";
    rows.forEach(([key, value]) => box.appendChild(rowEl(key, value)));
    const hint = document.createElement("p");
    hint.className = "hint";
    if (!window.isSecureContext) {
      hint.textContent = "Browsers require HTTPS or localhost before they allow a microphone.";
    } else if (permission === "denied") {
      hint.textContent = "The microphone is blocked for this site. Reset it in browser site settings, then reload.";
    } else if (state.lastMicError) {
      hint.textContent = "If this page is inside another app, open it in its own tab; embedded frames need explicit microphone permission.";
    } else {
      hint.textContent = "Browser facts behind the microphone. If Start fails, this line explains why.";
    }
    box.appendChild(hint);
  }

  /* ---------- tabs ---------- */

  function activateTab(name) {
    // Data tabs refresh on open; form tabs keep their current state.
    state.tab = name;
    if (history.replaceState) history.replaceState(null, "", "#" + name);
    document.querySelectorAll(".tab").forEach((tab) => {
      const on = tab.dataset.tab === name;
      tab.setAttribute("aria-selected", String(on));
      tab.tabIndex = on ? 0 : -1;
    });
    document.querySelectorAll(".tabpanel").forEach((panel) => {
      panel.hidden = panel.id !== "panel-" + name;
    });
    if (name === "brain") { if (!state.brainLoaded) refreshBrain(); }
    else if (name === "voice") { refreshMics(); refreshMicDiag(); if (!state.settingsLoaded) refreshSettings(); }
    else if (name === "memory") refreshFacts();
    else if (name === "cost") refreshCost();
    else if (name === "system") refreshStatus();
    else if (name === "logs") refreshEvents();
  }

  /* ---------- wiring ---------- */

  $("orb").addEventListener("click", toggleSession);
  $("sessionBtn").addEventListener("click", toggleSession);
  $("cancelBtn").addEventListener("click", cancelTurn);
  $("langChip").addEventListener("click", () => {
    const next = state.lang === "auto" ? "en" : state.lang === "en" ? "fr" : "auto";
    saveSettings({ lang: next });
  });

  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => activateTab(tab.dataset.tab));
  });
  $("tab-brain").parentElement.addEventListener("keydown", (event) => {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    event.preventDefault();
    const tabs = Array.from(document.querySelectorAll(".tab"));
    const index = tabs.findIndex((tab) => tab.getAttribute("aria-selected") === "true");
    const next = tabs[(index + (event.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length];
    next.focus();
    activateTab(next.dataset.tab);
  });

  document.querySelectorAll(".dot").forEach((dot) => {
    dot.addEventListener("click", () => activateTab("system"));
  });

  $("provider").addEventListener("change", () => refreshBrain($("provider").value));
  $("applyBrain").addEventListener("click", async () => {
    try {
      await api("/api/brain", { method: "POST", body: JSON.stringify({ provider: $("provider").value, model: $("modelSel").value }) });
      $("brainStatus").textContent = "Applied " + $("provider").value + "/" + $("modelSel").value;
      state.lastDone = null;
      refreshStatus();
    } catch (error) {
      $("brainStatus").textContent = error.message;
    }
  });
  $("testBrain").addEventListener("click", async () => {
    $("brainStatus").textContent = "Testing…";
    try {
      const data = await (await api("/api/brain/test", { method: "POST", body: JSON.stringify({ provider: $("provider").value, model: $("modelSel").value }) })).json();
      $("brainStatus").textContent = data.ok ? "OK: " + (data.text || "") : "Failed: " + (data.error || "");
    } catch (error) {
      $("brainStatus").textContent = error.message;
    }
  });

  $("saveVoice").addEventListener("click", () => {
    saveSettings({
      lang: $("langSel").value,
      tts: $("ttsSel").value === "on",
      voice_en: $("voiceEn").value.trim(),
      voice_fr: $("voiceFr").value.trim(),
    });
  });

  $("micSel").addEventListener("change", async () => {
    state.deviceId = $("micSel").value;
    if (state.deviceId) localStorage.setItem("jarvis_device", state.deviceId);
    else localStorage.removeItem("jarvis_device");
    if (state.enabled) {
      await stopSession();
      await startSession();
    }
  });

  $("addFact").addEventListener("click", async () => {
    const text = $("newFact").value.trim();
    if (!text) return;
    try {
      await api("/api/facts", { method: "POST", body: JSON.stringify({ text }) });
      $("newFact").value = "";
      $("memoryStatus").textContent = "Saved.";
      refreshFacts();
    } catch (error) {
      $("memoryStatus").textContent = error.message;
    }
  });
  $("newFact").addEventListener("keydown", (event) => { if (event.key === "Enter") $("addFact").click(); });

  $("factList").addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-id]");
    if (!button) return;
    try {
      await api("/api/facts/forget", { method: "POST", body: JSON.stringify({ id: Number(button.dataset.id) }) });
      refreshFacts();
    } catch (error) {
      $("memoryStatus").textContent = error.message;
    }
  });

  $("exportFacts").addEventListener("click", () => download("/api/export?what=facts", "jarvis-facts.json").catch((e) => { $("memoryStatus").textContent = e.message; }));
  $("exportAll").addEventListener("click", () => download("/api/export?what=all", "jarvis-export.json").catch((e) => { $("logStatus").textContent = e.message; }));

  $("forgetAll").addEventListener("click", async () => {
    if (!confirm("Delete all facts, turns, and events?")) return;
    try {
      await api("/api/forget", { method: "POST", body: JSON.stringify({ all: true }) });
      await refreshFacts();
      await refreshHistory();
      await refreshEvents();
      refreshStatus();
    } catch (error) {
      showBanner(error.message);
    }
  });

  $("logLevel").addEventListener("change", renderLogs);
  $("refreshLogs").addEventListener("click", refreshEvents);
  $("copyLogs").addEventListener("click", async () => {
    const text = state.events.map((e) => (e.ts || "") + " " + (e.level || "info") + " " + e.event + (e.detail ? " · " + e.detail : "")).join("\n");
    try {
      await navigator.clipboard.writeText(text);
      $("logStatus").textContent = "Copied.";
    } catch (_) {
      $("logStatus").textContent = "Copy failed.";
    }
  });

  $("sendText").addEventListener("click", () => {
    const text = $("textInput").value.trim();
    if (!text) return;
    $("textInput").value = "";
    setState("thinking", "Thinking");
    startStageTimer("Thinking");
    sendTurn(null, text);
  });
  $("textInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter") $("sendText").click();
  });

  $("tokenInput").value = state.token;
  $("saveToken").addEventListener("click", () => {
    state.token = $("tokenInput").value.trim();
    if (state.token) localStorage.setItem("jarvis_token", state.token);
    else localStorage.removeItem("jarvis_token");
    showBanner("");
    refreshStatus();
  });

  document.addEventListener("keydown", (event) => {
    const tag = (event.target && event.target.tagName) || "";
    const typing = ["INPUT", "TEXTAREA", "SELECT"].includes(tag) || tag === "BUTTON" || tag === "A";
    if (event.code === "Space" && !typing) {
      event.preventDefault();
      toggleSession();
    } else if (event.key === "Escape") {
      stopPlayback();
      if (state.turnAbort) cancelTurn();
      else setState(state.enabled ? "listening" : "idle", state.enabled ? "Listening" : "Ready");
    } else if (event.key === "/" && !typing) {
      event.preventDefault();
      $("textInput").focus();
    }
  });

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) stopPlayback();
  });

  function poll() {
    // One poll drives the top bar, health, and live feed.
    if (document.hidden) return;
    refreshStatus();
    refreshHealth();
    refreshEvents();
    if (state.tab === "cost") refreshCost();
    if (state.tab === "memory") refreshFacts();
  }

  setLevel(0);
  setState("idle", "Ready");
  document.querySelectorAll("#transcript, #eventFeed, .tabpanel, .log-list, .table-wrap").forEach((el) => { el.tabIndex = 0; });
  const initialTab = location.hash.slice(1);
  if (["brain", "voice", "memory", "cost", "system", "logs"].includes(initialTab)) activateTab(initialTab);
  window.addEventListener("hashchange", () => {
    const name = location.hash.slice(1);
    if (["brain", "voice", "memory", "cost", "system", "logs"].includes(name) && name !== state.tab) activateTab(name);
  });
  refreshSettings();
  refreshStatus();
  refreshHealth();
  refreshEvents();
  refreshHistory();
  refreshBrain();
  refreshMics();
  refreshMicDiag();
  setInterval(poll, 5000);
})();
