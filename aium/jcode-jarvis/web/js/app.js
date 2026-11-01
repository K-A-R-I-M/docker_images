/** Entry module: tabs, wiring, polling, and first paint. */
import { $, state, setNotifier, api, download } from "./core.js";
import { setState, showBanner, startStageTimer } from "./ui.js";
import { initAudio, toggleSession, startSession, stopSession, stopPlayback, setLevel } from "./audio.js";
import { sendTurn, cancelTurn } from "./turn.js";
import { refreshStatus, refreshHealth, refreshEvents, refreshHistory, renderLogs } from "./panels-system.js";
import { refreshBrain, refreshSettings, refreshFacts, refreshCost, refreshMics, refreshMicDiag, saveSettings } from "./panels-config.js";

setNotifier(showBanner);
initAudio(sendTurn);

/* ---------- tabs ---------- */

/** Show one panel and refresh it if it is a data view. */
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
    silence_ms: Number($("silenceSel").value),
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

/** Refresh the always-visible parts and the active data tab. */
function poll() {
  // One poll drives the top bar, health, and live feed.
  if (document.hidden) return;
  refreshStatus();
  refreshHealth();
  refreshEvents();
  if (state.tab === "cost") refreshCost();
  if (state.tab === "memory") refreshFacts();
}

/* ---------- boot ---------- */

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
