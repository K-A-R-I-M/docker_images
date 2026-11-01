/** Microphone capture, voice activity detection, playback, and TTS fallback. */
import { $, state, api } from "./core.js";
import { setState, showBanner, startStageTimer } from "./ui.js";
import { refreshMics, refreshMicDiag } from "./panels-config.js";

let sendUtterance = null;

/** app.js injects sendTurn so audio never imports the turn module. */
export function initAudio(send) {
  sendUtterance = send;
}

// VAD: RMS gate, endpoint delay, short utterance, and max utterance.
const THRESHOLD = 0.025;
const VAD_POLICY = { silenceMs: 1200, minSpeechMs: 400, maxUtteranceMs: 15000 };
/** End-of-turn wait in ms; the Voice tab can change this live. */
function endpointMs() {
  const value = Number(state.settings?.silence_ms);
  return Number.isFinite(value) && value > 0 ? Math.min(4000, Math.max(600, value)) : VAD_POLICY.silenceMs;
}
/** Clear capture state after a turn, a stop, or a barge-in. */
function resetVad() {
  state.frames = [];
  state.speaking = false;
  state.silenceMs = 0;
  state.speechMs = 0;
  state.utteranceMs = 0;
}

const RING = 2 * Math.PI * 54;
/** Drive the level ring and the mic meter from 0 to 1. */
export function setLevel(value) {
  const level = Math.max(0, Math.min(1, value));
  state.level = level;
  const ring = $("levelRing");
  ring.style.strokeDasharray = String(RING);
  ring.style.strokeDashoffset = String(RING * (1 - level * 0.92));
  $("micBar").style.width = Math.round(level * 100) + "%";
}

/** Ask for the mic, start capture, and mark the session listening. */
export async function startSession(forceDefault = false) {
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
    resetVad();
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

/** Drop the mic, stop playback, and tell the server the session ended. */
export async function stopSession() {
  if (!state.enabled) return;
  state.enabled = false;
  stopCapture();
  stopPlayback();
  setLevel(0);
  setState("idle", "Ready");
  try { await api("/api/session", { method: "POST", body: JSON.stringify({ enabled: false }) }); } catch (_) {}
}

export function toggleSession() {
  if (state.enabled) stopSession(); else startSession();
}

/** Release the audio graph and reset capture state. */
function stopCapture() {
  if (state.processor) { try { state.processor.disconnect(); } catch (_) {} }
  if (state.source) { try { state.source.disconnect(); } catch (_) {} }
  if (state.stream) state.stream.getTracks().forEach((track) => track.stop());
  if (state.ctx) { try { state.ctx.close(); } catch (_) {} }
  state.processor = null;
  state.source = null;
  state.stream = null;
  state.ctx = null;
  resetVad();
}

/** Linear resample to the 16 kHz whisper expects. */
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

/** VAD: track level, start speech, and end after enough silence. */
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
  const durationMs = (raw.length / state.sampleRate) * 1000;
  setLevel(state.level * 0.7 + Math.min(1, rms * 4) * 0.3);

  if (state.ui === "speaking" && rms > 0.04) {
    stopPlayback();
    if (state.turnAbort) {
      state.turnAbort.abort();
      state.turnAbort = null;
    }
    api("/api/cancel", { method: "POST" }).catch(() => {});
    setState("listening", "Listening");
    resetVad();
  }
  if (state.ui === "thinking") return;

  if (rms > THRESHOLD) {
    state.speaking = true;
    state.silenceMs = 0;
    state.speechMs += durationMs;
    state.utteranceMs += durationMs;
    state.frames.push(pcm);
    if (state.utteranceMs >= VAD_POLICY.maxUtteranceMs) finalizeUtterance();
  } else if (state.speaking) {
    state.silenceMs += durationMs;
    state.utteranceMs += durationMs;
    state.frames.push(pcm);
    if (state.silenceMs >= endpointMs()) finalizeUtterance();
  }
}

/** Join captured frames and hand them to the turn pipeline. */
function finalizeUtterance() {
  const frames = state.frames;
  const speechMs = state.speechMs;
  resetVad();
  if (speechMs < VAD_POLICY.minSpeechMs) return;
  let length = 0;
  frames.forEach((frame) => { length += frame.length; });
  const pcm = new Int16Array(length);
  let offset = 0;
  frames.forEach((frame) => { pcm.set(frame, offset); offset += frame.length; });
  setState("thinking", "Thinking");
  startStageTimer("Transcribing");
  sendUtterance(pcm, null);
}

/* ---------- turn ---------- */

/** Queue one synthesized WAV and play it after the current sentence. */
export function enqueueAudio(base64) {
  try {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
    const url = URL.createObjectURL(new Blob([bytes], { type: "audio/wav" }));
    state.audioQueue.push(url);
    playNext();
  } catch (_) {}
}

/** Play the next queued sentence and settle when the queue empties. */
function playNext() {
  if (state.playing) return;
  if (!state.audioQueue.length) {
    maybeIdle();
    return;
  }
  const url = state.audioQueue.shift();
  state.playing = true;
  resetVad();
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

/** Use the browser voice when server audio is missing. */
export function speakFallback(text, lang) {
  if (!("speechSynthesis" in window)) return;
  resetVad();
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

/** Return to listening or idle once the queue is empty. */
export function maybeIdle() {
  if (state.playing || state.audioQueue.length || state.fallbackCount) return;
  setState(state.enabled ? "listening" : "idle", state.enabled ? "Listening" : "Ready");
}

/** Cancel all queued and current audio. */
export function stopPlayback() {
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

