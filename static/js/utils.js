"use strict";
const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const S = {
  boot: null, tab: "chats", chatId: null, chat: null, busy: false, models: {},
  // Image-generation catalogues are a separate listing on the one provider
  // that publishes one, so they cache separately from chat models.
  imageModels: {},
  nsfw: false, tasks: new Map(), taskSeq: 0,
  modalToken: 0, modalOwnerToken: null, memoryCharacter: null,
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

// An Error that carries HOW the work ended, for the out-of-band poll loops in
// backdrops.js and ambience.js (twins by construction, so the tag lives once).
// The kinds are the queue's own endings -- "failed" (a recorded verdict),
// "notfound" (searched, and there genuinely is nothing), "slow" (still
// honestly pending when the poll budget ran out), "gone" (retired with
// nothing produced -- called off) -- and the catch that shows the toast picks
// severity and the give-up decision by tag rather than by re-deriving them
// from wording. The wording is what went wrong last time: four different
// endings all read as one message describing none of them.
function taggedError(kind, message) {
  const error = new Error(message);
  error.kind = kind;
  return error;
}

// ---- API ----
async function api(method, url, body) {
  // Arm on the way IN. Generating a character or a lorebook takes minutes, and
  // this call almost always originates from a click -- which is the gesture
  // the browser will let us unlock audio with, and the last one available
  // before the reader tabs away. See chime.js.
  const chimed = typeof chimeWatches === "function" && chimeWatches(method, url);
  if (chimed && typeof chimeArm === "function") chimeArm();
  const startedAt = performance.now();
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
  // Only on the way out, and only on success: a rejection has already thrown
  // above, and every failure path in this app raises its own toast.
  if (chimed && typeof chimeWorkFinished === "function") {
    chimeWorkFinished(method, url, performance.now() - startedAt);
  }
  const ct = response.headers.get("content-type") || "";
  return ct.includes("json")
    ? response.json()
    : response.text();
}

async function streamPost(url, body, onEvt) {
  const response = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
  if (!response.ok) {
    // Same 401 contract as api() above: no valid host session means the
    // whole tab belongs on the sign-in page. This path missed it, so a
    // session expiring between turns surfaced as a "Pipeline failed:
    // Unauthorized" toast on an SPA that looked signed in and wasn't.
    // 403 stays a thrown error here too -- that's a valid-but-guest-scoped
    // session, a different meaning.
    if (response.status === 401) {
      window.location.href = "/login";
      throw new Error("Unauthorized");
    }
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
