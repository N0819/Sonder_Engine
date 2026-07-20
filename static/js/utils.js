"use strict";
const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const S = {
  boot: null, tab: "chats", chatId: null, chat: null, busy: false, models: {},
  nsfw: false, tasks: new Map(), taskSeq: 0, modalToken: 0, memoryCharacter: null,
  // Which frame (diegetic era) this browser tab is currently viewing and
  // will post new turns into -- null means the present, the implicit
  // default every chat starts in. Purely client-side view state (see
  // frames.py's module docstring): the server has no single "current
  // frame" concept anymore, since two frames can be simultaneously live.
  currentFrameId: null
};

const MEM_CATS = ["episode", "dialogue", "promise", "relationship", "person", "place", "semantic", "intention", "emotion", "self", "inference"];
const MEM_PROV = ["witnessed", "heard", "told", "read", "inferred", "remembered"];

// Whether a turn can actually run yet: resolve_role() in providers.py falls
// back to agent_models.default for any role that isn't set individually, so
// "default" having both a provider and a model is the one thing that has to
// be true before anything -- wizard, first turn, generation -- can succeed.
function hasDefaultModel() {
  const d = S.boot && S.boot.agent_models && S.boot.agent_models.default;
  return !!(d && d.provider && d.model);
}

function safeId(s) { return String(s).replace(/[^a-zA-Z0-9_-]/g, "_"); }
function splitCL(v) { return String(v || "").split(",").map(s => s.trim()).filter(Boolean); }
function numOr(v, f) { const n = Number(v); return Number.isFinite(n) ? n : f; }

// ---- API ----
async function api(method, url, body) {
  let response;
  try {
    response = await fetch(url, {
      method,
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache"
      },
      body: body === undefined
        ? undefined
        : JSON.stringify(body)
    });
  } catch (error) {
    throw new Error(
      "Could not reach the server. "
      + (error?.message || "Network error")
    );
  }
  if (!response.ok) {
    if (response.status === 401) {
      // No valid host session (never had one, or it expired): send the
      // whole tab to the sign-in page. 403 deliberately does NOT
      // redirect -- that's a valid-but-guest-scoped session, a
      // different meaning.
      window.location.href = "/login";
      throw new Error("Unauthorized");
    }
    let message = await response.text();
    try {
      const parsed = JSON.parse(message);
      message = parsed.detail
        || parsed.error
        || message;
    } catch (e) {
      // keep the response body
    }
    throw new Error(message || `HTTP ${response.status}`);
  }
  const ct = response.headers.get("content-type") || "";
  return ct.includes("json")
    ? response.json()
    : response.text();
}

async function streamPost(url, body, onEvt) {
  const response = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
  if (!response.ok) {
    let message = await response.text();
    try { message = JSON.parse(message).detail || message } catch (e) { }
    throw new Error(message || `HTTP ${response.status}`);
  }
  if (!response.body) throw new Error("No response stream.");
  const reader = response.body.getReader(), dec = new TextDecoder(); let buf = "";
  for (;;) {
    const { done, value } = await reader.read(); if (done) break;
    buf += dec.decode(value, { stream: true }); let i;
    while ((i = buf.indexOf("\n")) >= 0) {
      const ln = buf.slice(0, i).trim(); buf = buf.slice(i + 1);
      if (ln) { try { onEvt(JSON.parse(ln)) } catch (e) { } }
    }
  }
  const tail = buf.trim();
  if (tail) { try { onEvt(JSON.parse(tail)) } catch (e) { } }
}

// ---- Download ----
function downloadJSON(data, filename) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a"); a.href = url;
  a.download = filename || "export.json";
  document.body.append(a); a.click(); a.remove(); URL.revokeObjectURL(url);
}