/** Brain, voice, memory, cost, and microphone panels. */
import { $, state, api, download, money, ms, num, rowEl } from "./core.js";
import { showBanner } from "./ui.js";

/** Load providers and models, then fill the Brain selects. */
export async function refreshBrain(provider) {
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
    $("skillsEnabled").checked = data.config?.skills === true;
    state.brainLoaded = true;
  } catch (error) {
    $("brainStatus").textContent = error.message;
  }
}

/** Populate a select while keeping the current value when possible. */
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

/** Load speech settings once; tab switches must not overwrite edits. */
export async function refreshSettings() {
  try {
    const data = await (await api("/api/settings")).json();
    state.settings = data;
    state.lang = data.lang || "auto";
    $("langChip").textContent = state.lang === "auto" ? "Auto" : state.lang.toUpperCase();
    $("langSel").value = state.lang;
    $("ttsSel").value = data.tts === false ? "off" : "on";
    $("silenceSel").value = String(data.silence_ms || 1200);
    $("voiceEn").value = data.voice_en || "";
    $("voiceFr").value = data.voice_fr || "";
    $("voiceModel").textContent = data.whisper_model || "—";
    $("voiceProfile").textContent = data.profile || "—";
    state.settingsLoaded = true;
  } catch (_) {}
}

/** Persist the supplied settings and sync only the fields that were sent. */
export async function saveSettings(partial) {
  try {
    const data = await (await api("/api/settings", { method: "POST", body: JSON.stringify(partial) })).json();
    state.settings = data;
    state.lang = data.lang || state.lang;
    $("langChip").textContent = state.lang === "auto" ? "Auto" : state.lang.toUpperCase();
    $("voiceStatus").textContent = "Saved.";
    const sync = { lang: $("langSel"), tts: $("ttsSel"), voice_en: $("voiceEn"), voice_fr: $("voiceFr"), silence_ms: $("silenceSel") };
    Object.keys(partial).forEach((key) => {
      if (key === "lang") sync.lang.value = data.lang;
      else if (key === "tts") sync.tts.value = data.tts === false ? "off" : "on";
      else if (key === "voice_en") sync.voice_en.value = data.voice_en || "";
      else if (key === "voice_fr") sync.voice_fr.value = data.voice_fr || "";
      else if (key === "silence_ms") sync.silence_ms.value = String(data.silence_ms);
    });
    return data;
  } catch (error) {
    $("voiceStatus").textContent = error.message;
    showBanner(error.message);
    return null;
  }
}

/** Draw the cost totals, 7-day bars, and recent-turn table. */
export async function refreshCost() {
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

/** List stored facts with per-fact forget controls. */
export async function refreshFacts() {
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

/** Fill the microphone select; labels appear after permission is granted. */
export async function refreshMics() {
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

/** Show browser facts behind microphone access and the last error. */
export async function refreshMicDiag() {
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

