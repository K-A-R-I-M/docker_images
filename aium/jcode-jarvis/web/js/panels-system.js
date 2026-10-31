/** Status, health, events, logs, and history panels. */
import { $, state, api, money, bytes, uptime, rowEl, escapeHtml } from "./core.js";
import { renderTranscript, updateBreakdown } from "./transcript.js";

let statusTimer = null;

/** Debounce status refreshes after a turn settles. */
export function refreshStatusSoon() {
  if (statusTimer) return;
  statusTimer = setTimeout(() => {
    statusTimer = null;
    refreshStatus();
  }, 400);
}

/** Update the top bar and, when open, the System rows. */
export async function refreshStatus() {
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

/** Update the four health dots and the rail rows. */
export async function refreshHealth() {
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

/** Update the live feed; rebuild the log list only when visible. */
export async function refreshEvents() {
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

/** Render the current events with the selected level filter. */
export function renderLogs() {
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

/** Reload the last 50 turns and repaint the conversation. */
export async function refreshHistory() {
  try {
    const data = await (await api("/api/history?limit=50")).json();
    state.turns = data.turns || [];
    renderTranscript();
    updateBreakdown();
  } catch (_) {}
}

