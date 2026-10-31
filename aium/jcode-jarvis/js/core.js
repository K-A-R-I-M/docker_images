/** Shared state, DOM helpers, formatting, and the API client. */
export const $ = (id) => document.getElementById(id);
/** One mutable store shared by every module. */
export const state = {
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
/** Compact display helpers. Never use these for storage math. */
export function money(value) {
  if (value === null || value === undefined) return "—";
  if (value === 0) return "$0.00";
  if (value < 0.0001) return "<$0.0001";
  return "~$" + value.toFixed(value < 0.01 ? 6 : 4).replace(/0+$/, "").replace(/\.$/, "");
}

export function num(value) {
  const n = Number(value || 0);
  if (n >= 1000000) return (n / 1000000).toFixed(1) + "M";
  if (n >= 1000) return (n / 1000).toFixed(1) + "k";
  return String(n);
}

export function ms(value) {
  const n = Number(value || 0);
  return n >= 1000 ? (n / 1000).toFixed(1) + "s" : n + "ms";
}

export function bytes(value) {
  const n = Number(value || 0);
  if (n >= 1048576) return (n / 1048576).toFixed(1) + " MB";
  if (n >= 1024) return (n / 1024).toFixed(0) + " kB";
  return n + " B";
}

export function uptime(seconds) {
  const s = Number(seconds || 0);
  if (s >= 86400) return Math.floor(s / 86400) + "d " + Math.floor((s % 86400) / 3600) + "h";
  if (s >= 3600) return Math.floor(s / 3600) + "h " + Math.floor((s % 3600) / 60) + "m";
  if (s >= 60) return Math.floor(s / 60) + "m";
  return s + "s";
}

let notify = () => {};

/** Let the UI own user-facing error messages. */
export function setNotifier(fn) {
  notify = fn;
}

/** Fetch wrapper: attaches the token and rejects non-2xx responses. */
export async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (state.token) headers.set("Authorization", "Bearer " + state.token);
  const init = { ...options, headers };
  if (options.body && !headers.has("Content-Type") && typeof options.body === "string") {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(path, init);
  if (response.status === 401) {
    notify("Access token needed. Open System and save it.");
    throw new Error("Unauthorized");
  }
  if (!response.ok) {
    let message = "Request failed";
    try { message = (await response.json()).error || message; } catch (_) {}
    throw new Error(message);
  }
  return response;
}

/** Download an authenticated export without leaving the panel. */
export async function download(path, filename) {
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

/** Build one label/value row; pass a node for status pills. */
export function rowEl(key, value, node) {
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

/** Escape the one server string that is placed with innerHTML. */
export function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

