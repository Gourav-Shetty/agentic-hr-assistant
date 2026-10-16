/* API client for the FastAPI backend.
 * Backend URL comes from VITE_API_URL (default http://localhost:8000).
 *
 * REST:
 *   POST /api/chat        -> { reply, route, citations, booking, thread_id }
 *   POST /api/chat/stream -> SSE events: node / token / done (+ forward-compat extras)
 *   GET  /api/slots       -> { slots: string[3] }
 *   POST /api/reset       -> { thread_id, status }
 */

const API_BASE =
  (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

async function parseJsonSafe(res) {
  const text = await res.text();
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(`Bad JSON from ${res.url}: ${text.slice(0, 120)}`);
  }
}

async function raiseForStatus(res) {
  if (res.ok) return res;
  let detail = `${res.status} ${res.statusText}`;
  try {
    const body = await res.clone().json();
    if (body && body.detail) detail = String(body.detail);
  } catch {
    /* keep default detail */
  }
  throw new Error(detail);
}

/** Non-streaming chat. */
export async function chat(message, thread_id) {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, thread_id: thread_id || "" }),
  });
  await raiseForStatus(res);
  return parseJsonSafe(res);
}

/** Available review slots. Returns string[] (max 3). */
export async function getSlots() {
  const res = await fetch(`${API_BASE}/api/slots`);
  await raiseForStatus(res);
  const data = await parseJsonSafe(res);
  return Array.isArray(data.slots) ? data.slots : [];
}

/** Clear server-side checkpoint state for a thread. */
export async function reset(thread_id) {
  const res = await fetch(`${API_BASE}/api/reset`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ thread_id: thread_id || "" }),
  });
  await raiseForStatus(res);
  return parseJsonSafe(res);
}

/**
 * Streaming chat via SSE.
 * Parses `event:` / `data:` frames from POST /api/chat/stream.
 *
 * Backend events: node {route, thread_id}, token {token}, done {thread_id, route, stage}.
 * Forward-compatible: also accepts citations {citations}, booking {booking},
 * meta/reply {reply|citations|booking|route|thread_id|stage}, and error {detail|message}.
 *
 * @param {string} message
 * @param {string} thread_id
 * @param {{ onNode?, onToken?, onDone?, onError? }} handlers
 * @returns {Promise<{ reply, route, citations, booking, thread_id, stage }>}
 */
export async function streamChat(message, thread_id, handlers = {}) {
  const { onNode, onToken, onDone, onError } = handlers;

  const res = await fetch(`${API_BASE}/api/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({ message, thread_id: thread_id || "" }),
  });
  await raiseForStatus(res);

  if (!res.body || typeof res.body.getReader !== "function") {
    // No streaming support — fall back to plain chat.
    const full = await parseJsonSafe(res);
    if (onNode) onNode({ route: full.route, thread_id: full.thread_id });
    if (onToken && full.reply) onToken(full.reply);
    if (onDone) onDone(full);
    return full;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let reply = "";
  let route = "";
  let tid = thread_id || "";
  let citations = [];
  let booking = null;
  let stage = "";
  let serverError = null;

  const dispatch = (event, rawData) => {
    let data = {};
    const text = (rawData || "").trim();
    if (text) {
      try {
        data = JSON.parse(text);
      } catch {
        data = { _raw: text };
      }
    }
    switch (event) {
      case "node":
        if (data.route) route = String(data.route);
        if (data.thread_id) tid = String(data.thread_id);
        if (typeof data.stage === "string" && data.stage) stage = String(data.stage);
        if (onNode) onNode(data);
        break;
      case "token":
        if (typeof data.token === "string") {
          reply += data.token;
          if (onToken) onToken(data.token);
        }
        break;
      case "citations":
        if (Array.isArray(data.citations)) citations = data.citations;
        else if (Array.isArray(data)) citations = data;
        if (typeof data.stage === "string" && data.stage) stage = String(data.stage);
        break;
      case "booking":
        booking = data.booking !== undefined ? data.booking : data;
        if (typeof data.stage === "string" && data.stage) stage = String(data.stage);
        break;
      case "meta":
      case "reply":
      case "done":
        if (typeof data.reply === "string" && data.reply && !reply) reply = data.reply;
        if (data.route) route = String(data.route);
        if (data.thread_id) tid = String(data.thread_id);
        if (typeof data.stage === "string" && data.stage) stage = String(data.stage);
        if (Array.isArray(data.citations)) citations = data.citations;
        if (data.booking !== undefined) booking = data.booking;
        if (event === "done" && onDone) {
          onDone({ reply, route, citations, booking, thread_id: tid, stage });
        }
        break;
      case "error":
        serverError = new Error(
          String(data.detail || data.message || data._raw || "Stream error")
        );
        if (onError) onError(serverError);
        break;
      default:
        // Unknown events: surface token-like payloads so nothing is lost.
        if (typeof data.token === "string") {
          reply += data.token;
          if (onToken) onToken(data.token);
        }
        break;
    }
  };

  // Parse SSE frames: blocks separated by a blank line.
  const pump = (chunkText, flush = false) => {
    buffer += chunkText;
    let idx;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      let event = "message";
      const dataLines = [];
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
        // ignore `id:`, `retry:`, comments
      }
      if (dataLines.length) dispatch(event, dataLines.join("\n"));
    }
    if (flush && buffer.trim()) {
      let event = "message";
      const dataLines = [];
      for (const line of buffer.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
      }
      if (dataLines.length) dispatch(event, dataLines.join("\n"));
      buffer = "";
    }
  };

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      pump(decoder.decode(value, { stream: true }));
      if (serverError) break;
    }
    pump(decoder.decode(), true);
  } finally {
    try {
      reader.releaseLock();
    } catch {
      /* noop */
    }
  }

  if (serverError) throw serverError;
  return { reply, route, citations, booking, thread_id: tid, stage };
}

export const API_BASE_URL = API_BASE;
