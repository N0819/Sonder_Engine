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
function t(source, vars = {}) {
  source = String(source ?? "");
  let out = S.uiCatalog && S.uiCatalog[source];
  if (out === undefined && S.uiCatalog) {
    if (!S.uiTemplateRules) {
      // Two rules decide whether a template can be matched back from its
      // interpolated result at all, and both were missing:
      //
      // 1. A key made only of placeholders ("${a} ${b}") compiles to
      //    /^(.+?) (.+?)$/ -- every string with a space. One such rule sat
      //    near the front of the catalog and shadowed 220 of the 226
      //    templates behind it, so almost every counter and "X of Y" label
      //    rendered English despite being correctly translated.
      // 2. Order must be by how much LITERAL text a rule pins down, not by
      //    catalog position, or a vague rule still wins over a precise one.
      S.uiTemplateRules = Object.entries(S.uiCatalog)
        .filter(([key]) => key.includes("${"))
        .map(([key, value]) => {
          const literals = key.split(/\$\{[^}]+\}/g);
          const anchored = literals.join("").trim();
          const parts = literals
            .map(part => part.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
          return {
            regex: new RegExp(`^${parts.join("(.+?)")}$`),
            value,
            weight: anchored.length,
          };
        })
        // At least three characters of real text, so a rule has to recognise
        // something about the message rather than merely its shape.
        .filter(rule => rule.weight >= 3)
        .sort((a, b) => b.weight - a.weight);
    }
    for (const rule of S.uiTemplateRules) {
      const match = source.match(rule.regex);
      if (!match) continue;
      let index = 1;
      // Translate each CAPTURE too. The captured span is whatever the caller
      // interpolated, and it is very often another engine string that has its
      // own catalog entry -- `${phase} (+2 running alongside)` captures an
      // already-English step label, so the status bar came out half Japanese:
      // 「Writing the scene (他に2が並行して実行中)」.
      out = rule.value.replace(/\$\{[^}]+\}/g, () => {
        const captured = match[index++] || "";
        const inner = S.uiCatalog && S.uiCatalog[captured.trim()];
        return inner === undefined ? captured : inner;
      });
      break;
    }
  }
  if (out === undefined) out = source;
  for (const [key, value] of Object.entries(vars || {})) {
    out = out.split(`{${key}}`).join(String(value));
  }
  return out;
}

function watchUILanguage() {
  if (S.uiObserver) S.uiObserver.disconnect();
  S.uiObserver = new MutationObserver(records => {
    for (const record of records) {
      if (record.type === "attributes") {
        const element = record.target;
        if (element && element.nodeType === Node.ELEMENT_NODE
            && !element.closest(I18N_SKIP_TREE)) {
          const current = element.getAttribute(record.attributeName);
          const translated = t(String(current || ""));
          if (current && translated !== current) {
            element.setAttribute(record.attributeName, translated);
          }
        }
        continue;
      }
      for (const node of record.addedNodes) {
        if (node.nodeType === Node.TEXT_NODE) {
          if (node.parentElement) localizeDocument(node.parentElement);
        } else if (node.nodeType === Node.ELEMENT_NODE) {
          localizeDocument(node);
        }
      }
    }
  });
  // `attributes` as well as `childList`: several toggles set `.title` after
  // the element is already in the DOM (the ambience mute, the backdrop and
  // chime toggles), and a childList-only observer never sees it -- so those
  // tooltips stayed English although the pack has all of them.
  S.uiObserver.observe(document.body, {
    childList: true, subtree: true,
    attributes: true,
    attributeFilter: ["title", "aria-label", "placeholder", "alt"],
  });
}

// Text this layer must never touch. The UI catalog is a map of ENGINE source
// strings; story text is authored by a model or by the reader, and it only
// looks like a catalog key by accident. 134 single-word keys have real
// translations, so narrator prose containing "Close" rendered 閉じる mid-
// sentence and a story named "Cast" became 配役. `translate="no"` is the
// standard HTML opt-out and is honoured here for the same reason browsers
// honour it.
//
// `textarea` and `input` are here because their content is DATA being edited,
// not chrome. boot() re-localizes the whole document, and boot() runs while
// the prompt editor is open -- so a system prompt sitting in a textarea was
// walked by the translator on its way to being saved.
// Two different exclusions, and conflating them cost every placeholder.
// A whole SUBTREE is off-limits for script/style and anything opted out;
// a textarea or input excludes only its CONTENT, because that content is
// data being edited while its placeholder and title are still chrome.
const I18N_SKIP_TREE = 'script,style,[data-no-i18n],[translate="no"]';
const I18N_SKIP_TEXT = I18N_SKIP_TREE + ',textarea,input';

function localizeDocument(root = document.body) {
  document.documentElement.lang = S.uiLanguage || "en";
  document.documentElement.dir = (S.boot && S.boot.ui_direction) || "ltr";
  if (!root || typeof root.querySelectorAll !== "function") {
    // A text node has no querySelectorAll. Callers pass `parentElement`
    // today, but the nodeType guards below imply other roots are allowed.
    root = root && root.parentElement;
    if (!root) return;
  }
  if (root.nodeType === Node.ELEMENT_NODE && root.closest(I18N_SKIP_TREE)) return;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  for (const node of nodes) {
    if (node.parentElement?.closest(I18N_SKIP_TEXT)) continue;
    const trimmed = String(node.nodeValue || "").trim();
    if (!trimmed) continue;
    const translated = t(trimmed);
    if (translated !== trimmed) {
      const lead = String(node.nodeValue).match(/^\s*/)?.[0] || "";
      const tail = String(node.nodeValue).match(/\s*$/)?.[0] || "";
      node.nodeValue = lead + translated + tail;
    }
  }
  // `root` ITSELF, not just its descendants. The observer hands us each
  // newly added element as the root, and querySelectorAll never matches the
  // node it is called on -- so a dynamically created input's placeholder was
  // never translated at all.
  // The SAME skip tree the text pass uses. It was applied to text nodes only,
  // so a tooltip under `translate="no"` was still translated -- a character
  // named "Cast" got a キャスト tooltip on the very element whose text the
  // guard was protecting. Attributes are chrome by default, which is why
  // textarea/input are not excluded here, but a subtree opted out is opted
  // out for both passes.
  const ATTRS = "[title],[aria-label],[placeholder],[alt]";
  const attrHosts = [...root.querySelectorAll(ATTRS)]
    .filter(element => !element.closest(I18N_SKIP_TREE));
  if (root.nodeType === Node.ELEMENT_NODE && root.matches(ATTRS)
      && !root.closest(I18N_SKIP_TREE)) {
    attrHosts.push(root);
  }
  for (const element of attrHosts) {
    for (const attr of ["title", "aria-label", "placeholder", "alt"]) {
      if (element.hasAttribute(attr)) {
        element.setAttribute(attr, t(element.getAttribute(attr)));
      }
    }
  }
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
