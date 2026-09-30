// Empty in local dev (falls back to CRA's "proxy" field in package.json,
// so relative /api/... calls reach the local backend). In production this
// must be baked in at BUILD time as a Docker build arg — CRA inlines
// process.env.REACT_APP_* into the bundle at build, a runtime env var on
// the container has no effect.
const API_BASE = process.env.REACT_APP_API_URL || "";

// A per-tab session id (sessionStorage, not localStorage) so it resets
// whenever someone opens a fresh tab/browser — that's what keeps one
// visitor's chats from ever showing up for the next person on the same
// deployment, without any login system.
function getSessionId() {
  let id = sessionStorage.getItem("session_id");
  if (!id) {
    id = crypto.randomUUID();
    sessionStorage.setItem("session_id", id);
  }
  return id;
}

function sessionHeaders(extra = {}) {
  return { "X-Session-Id": getSessionId(), ...extra };
}

export async function getStatus() {
  const res = await fetch(`${API_BASE}/api/status`);
  return res.json();
}

export async function getDocuments(chatId) {
  const res = await fetch(`${API_BASE}/api/documents?chat_id=${encodeURIComponent(chatId)}`, {
    headers: sessionHeaders(),
  });
  return res.json();
}

// The backend queues ingestion on a Celery worker and returns a task id
// right away; poll until it finishes and resolve with the same
// { indexed, total_chunks } shape the old synchronous endpoint returned.
export async function uploadDocuments(files, chatId) {
  const formData = new FormData();
  formData.append("chat_id", chatId);
  for (const file of files) formData.append("files", file);
  const res = await fetch(`${API_BASE}/api/documents`, { method: "POST", headers: sessionHeaders(), body: formData });
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail || `Upload failed (${res.status})`);

  const deadline = Date.now() + 5 * 60 * 1000;
  while (Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 1000));
    const statusRes = await fetch(`${API_BASE}/api/upload/status/${body.task_id}`, { headers: sessionHeaders() });
    const status = await statusRes.json();
    if (status.status === "success") return status.result;
    if (status.status === "failure" || !statusRes.ok) throw new Error(status.error || status.detail || "Ingestion failed");
  }
  throw new Error("Ingestion timed out");
}

export async function sendChat(question, history, chatId) {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: sessionHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ question, history, chat_id: chatId }),
  });
  const body = await res.json();
  // Rate limited: show the server's "try again in Ns" text as the reply.
  if (res.status === 429) return { answer: body.detail, chat_id: chatId };
  return body;
}

export async function getChats() {
  const res = await fetch(`${API_BASE}/api/chats`, { headers: sessionHeaders() });
  return res.json();
}

export async function createChat() {
  const res = await fetch(`${API_BASE}/api/chats`, { method: "POST", headers: sessionHeaders() });
  return res.json();
}

export async function getChatById(chatId) {
  const res = await fetch(`${API_BASE}/api/chats/${chatId}`, { headers: sessionHeaders() });
  return res.json();
}

export async function clearSession() {
  const res = await fetch(`${API_BASE}/api/session`, { method: "DELETE", headers: sessionHeaders() });
  return res.json();
}

// sendBeacon can't set the X-Session-Id header, so the id goes in the
// query string instead — this is the only browser API that reliably
// fires while the page is unloading (reload, tab close, navigating away),
// which a normal fetch isn't guaranteed to complete before that happens.
export function clearSessionOnUnload() {
  const id = getSessionId();
  navigator.sendBeacon(`${API_BASE}/api/session/clear-beacon?session_id=${encodeURIComponent(id)}`);
}
