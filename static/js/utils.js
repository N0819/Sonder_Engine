"use strict";
const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const S = {
  boot: null, tab: "chats", chatId: null, chat: null, busy: false, models: {},
  // Image-generation catalogues are a separate listing on the one provider
  // that publishes one, so they cache separately from chat models.
  imageModels: {}, uiCatalog: {}, uiLanguage: "en", uiTemplateRules: null,
  nsfw: false, tasks: new Map(), taskSeq: 0,
  modalToken: 0, modalOwnerToken: null, memoryCharacter: null,
  // Which frame (diegetic era) this browser tab is currently viewing and
  // will post new turns into -- null means the present, the implicit
  // default every chat starts in. Purely client-side view state (see
  // frames.py's module docstring): the server has no single "current
  // frame" concept anymore, since two frames can be simultaneously live.
  currentFrameId: null
};

// Gettext-style UI lookup: English source text is the stable message id.
// Catalog completeness is enforced server-side; the fallback protects a tab
// whose cached JavaScript is newer than its bootstrap response.
//
// The lookup RULES -- template compilation, the skip sets, the walk -- are
// i18n-core.js, which the login and guest pages load too. This file owns only
// what is the SPA's own: the catalog comes from the bootstrap, and `{var}`
// interpolation runs on top of the lookup. See i18n-core.js for why there is
// no second copy of the rules any more (B25, review 2026-09-07).
function t(source, vars = {}) {
  source = String(source ?? "");
  let out = source;
  if (S.uiCatalog) {
    if (!S.uiTemplateRules) {
      S.uiTemplateRules = i18nCompileTemplates(S.uiCatalog);
    }
    out = i18nTranslate(S.uiCatalog, S.uiTemplateRules, source);
  }
  for (const [key, value] of Object.entries(vars || {})) {
    out = out.split(`{${key}}`).join(String(value));
  }
  return out;
}

function watchUILanguage() {
  if (S.uiObserver) S.uiObserver.disconnect();
  S.uiObserver = i18nObserve(localizeDocument, t);
}

function localizeDocument(root = document.body) {
  document.documentElement.lang = S.uiLanguage || "en";
  document.documentElement.dir = (S.boot && S.boot.ui_direction) || "ltr";
  i18nLocalize(root, t);
}

// The memory vocabularies belong to `mind/memory.py` (MEMORY_CATEGORIES /
// MEMORY_PROVENANCE) and ride every bootstrap. Read them from there rather
// than from a second copy here. Both ends coerce silently: `memory.py` rewrites
// an unrecognised category or provenance to a default instead of rejecting it,
// so a term added server-side is simply missing from the dropdown, and one
// removed server-side is offered in the dropdown and quietly changed on save.
// A drifted copy has no symptom -- which is why there must not be one.
//
// The literals survive only as the fallback for a tab whose cached JavaScript
// is running ahead of its first bootstrap response, the same reason `t()`
// keeps one.
const MEM_CATS_FALLBACK = ["episode", "dialogue", "promise", "relationship", "person", "place", "semantic", "intention", "emotion", "self", "inference"];
const MEM_PROV_FALLBACK = ["witnessed", "heard", "told", "read", "inferred", "remembered"];

function memoryCategories() {
  const shipped = S.boot && S.boot.memory_categories;
  return Array.isArray(shipped) && shipped.length ? shipped : MEM_CATS_FALLBACK;
}

function memoryProvenance() {
  const shipped = S.boot && S.boot.memory_provenance;
  return Array.isArray(shipped) && shipped.length ? shipped : MEM_PROV_FALLBACK;
}

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
// A server error's `detail` is not always a sentence. FastAPI's validation
// failures arrive as an ARRAY of {loc, msg, type} objects, and handing that to
// `new Error(...)` stringifies it as "[object Object]" -- which is exactly as
// informative as no message at all, and is what a mis-wired route reported for
// every step edit. Render the shape rather than concatenating it.
function errorDetailText(detail) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const lines = detail.map((item) => {
      if (typeof item === "string") return item;
      if (!item || typeof item !== "object") return String(item);
      // `loc` is the path to the offending field; the last hop is the part a
      // reader can act on ("content", "s"), the rest is transport plumbing.
      const where = Array.isArray(item.loc) ? item.loc.slice(-1)[0] : "";
      const msg = item.msg || item.detail || item.type || "";
      return where ? where + ": " + msg : String(msg);
    }).filter(Boolean);
    if (lines.length) return lines.join("; ");
  }
  if (detail && typeof detail === "object") {
    const msg = detail.msg || detail.error || detail.message;
    if (msg) return String(msg);
    try { return JSON.stringify(detail); } catch (e) { /* fall through */ }
  }
  return "";
}

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
      message = errorDetailText(parsed.detail)
        || errorDetailText(parsed.error)
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
    try {
      message = errorDetailText(JSON.parse(message).detail) || message;
    } catch (e) { /* keep the response body */ }
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

// ---- Card authoring warnings ----
// Every route that creates or edits a character card returns `warnings`, and
// every caller shows them the same way. One helper rather than a copy per
// call site: the warnings used to reach exactly ONE of nine card-producing
// surfaces (the import route), and the reason the other eight were silent is
// that nothing made showing them the default. An unfilled psychology field
// does not error, does not warn at runtime and shows up fifty beats later as
// a character who behaves wrongly, so the moment the card is written is the
// only moment the host can act on it cheaply.
function showCardWarnings(result) {
  for (const warning of (result?.warnings || [])) toast(warning, "warn");
  return result;
}
