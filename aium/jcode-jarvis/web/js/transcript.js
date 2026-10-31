/** Transcript messages, rich text, diagrams, and the last-turn breakdown. */
import { $, state, money, num, ms } from "./core.js";
import { renderDiagrams } from "./diagrams.js";

/** Build one message; live replies stay plain until the turn completes. */
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

/** Split reply text into prose and mermaid diagram placeholders. */
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

export function nearBottom(box) {
  return box.scrollHeight - box.scrollTop - box.clientHeight < 48;
}

/** Rebuild the conversation from state and keep the newest message in view. */
export function renderTranscript() {
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

/** Fill the one-line timing and cost breakdown for the last turn. */
export function updateBreakdown(turn) {
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

