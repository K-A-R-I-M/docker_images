/** One cloud turn: SSE parsing, cancellation, and completion. */
import { $, state, api, money } from "./core.js";
import { showBanner, setState, startStageTimer, clearActivity } from "./ui.js";
import { renderTranscript, updateBreakdown, nearBottom } from "./transcript.js";
import { enqueueAudio, speakFallback, stopPlayback, maybeIdle, stopSession } from "./audio.js";
import { refreshHistory, refreshStatusSoon } from "./panels-system.js";

/** Send PCM or text, consume the SSE events, and settle the state. */
export async function sendTurn(pcm, text) {
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

/** Abort the stream and ask the server to stop the turn. */
export function cancelTurn() {
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

