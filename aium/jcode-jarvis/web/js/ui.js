/** Shared status chip, banner, orb state, and stage timer. */
import { $, state } from "./core.js";

const MIC_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3z"/><path d="M5 11a7 7 0 0 0 14 0"/><path d="M12 18v3"/><path d="M9 21h6"/></svg>';
const icons = {
  speaking: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 9v6h4l5 4V5L8 9H4z"/><path d="M16 8.5a5 5 0 0 1 0 7"/><path d="M19 6a9 9 0 0 1 0 12"/></svg>',
};
/** Mirror the session state into the chip, button, orb, and activity line. */
export function setState(ui, text) {
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

/** Show or clear the single alert line above the stage. */
export function showBanner(message) {
  const el = $("banner");
  el.textContent = message;
  el.dataset.show = message ? "true" : "false";
}

/** Start the live stage clock shown while a turn runs. */
export function startStageTimer(label) {
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

export function stopStageTimer() {
  if (state.stageTimer) clearInterval(state.stageTimer);
  state.stageTimer = null;
}

/** Clear the stage clock and activity line. */
export function clearActivity() {
  stopStageTimer();
  $("activity").textContent = "";
}

/* ---------- playback ---------- */

