"use strict";
// ---- Extension host ----
//
// The registry an extension's UI script talks to. Loaded BEFORE app.js and
// after components.js, because two things must be true at once: the extension
// bundle (`/api/extensions/ui.js`, the last script on the page) needs
// `window.Sonder` to already exist, and this file must be unable to break the
// boot it precedes. So it defines registries and pure functions only, touches
// no DOM at load, and reads nothing from `S` until a call actually arrives.
//
// The doctrine here is app.js's `typeof fn === "function"` guard around an
// optional module, made systematic: an extension is optional code written by
// someone who does not have to have read this repo, and NOTHING it does may
// take the reader's story down with it. Every callback it registers is invoked
// through `_safe`, which swallows the throw, counts it against the owning
// extension, and retires that extension after three -- a misbehaving panel
// stops being drawn, and the sidebar it was drawn into keeps working.

const Sonder = {
  // ---- Registration attribution ----
  // The bundle wraps each extension's code as
  //   window.Sonder && Sonder._begin("<id>"); <code> ;Sonder._end();
  // so every registration made while that code runs is attributed to that id
  // without the extension having to name itself on each call (and without
  // being able to claim another extension's name by doing so).
  _owner: null,
  _begin(id) { Sonder._owner = String(id || "") || null; },
  _end() { Sonder._owner = null; },

  _sidebar: [],
  _steps: new Map(),
  _events: new Map(),
  //: extension id -> consecutive-ish throw count, for the three-strikes rule.
  _faults: new Map(),

  // ---- Failure containment ----
  // Wrap a callback so a throw is contained and ATTRIBUTED. Returning
  // `undefined` on failure is deliberate: every caller here treats a missing
  // result as "this extension contributed nothing", which is exactly the
  // state we want a broken extension to be in.
  _safe(owner, fn, ...args) {
    try {
      return fn(...args);
    } catch (error) {
      Sonder._fault(owner, error);
      return undefined;
    }
  },

  _fault(owner, error) {
    // Structured rather than an interpolated prefix string: every string
    // literal under static/js is harvested into the English UI catalog
    // (tools/extract_ui_catalog.py is deliberately overinclusive), and a
    // console prefix is not a message anyone should have to translate.
    console.error({ extension: owner || null, error });
    if (!owner) return;
    const count = (Sonder._faults.get(owner) || 0) + 1;
    Sonder._faults.set(owner, count);
    if (count < 3) return;
    Sonder._unregister(owner);
    if (typeof toast === "function") {
      toast(`Extension "${owner}" was disabled after repeated errors.`, "err", 8000);
    }
  },

  // ---- Registration surface ----
  registerSidebarTab({ id, label, render }) {
    if (!id || typeof render !== "function") return;
    const owner = Sonder._owner;
    Sonder._sidebar = Sonder._sidebar.filter(tab => tab.id !== id);
    Sonder._sidebar.push({ id: String(id), label: String(label || id), render, owner });
  },

  // A step key an extension added to the pipeline, rendered its way in the
  // pipeline drawer instead of as raw JSON.
  registerStepRenderer(key, fn) {
    if (!key || typeof fn !== "function") return;
    Sonder._steps.set(String(key), { fn, owner: Sonder._owner });
  },

  on(event, fn) {
    if (!event || typeof fn !== "function") return;
    const list = Sonder._events.get(event) || [];
    list.push({ fn, owner: Sonder._owner });
    Sonder._events.set(event, list);
  },

  off(event, fn) {
    const list = Sonder._events.get(event);
    if (!list) return;
    Sonder._events.set(event, list.filter(entry => entry.fn !== fn));
  },

  // Never throws, whatever the listeners do -- `emit` is called from the
  // stream handler, i.e. from inside a turn in progress.
  emit(event, payload) {
    const list = Sonder._events.get(event);
    if (!list || !list.length) return;
    for (const entry of [...list]) Sonder._safe(entry.owner, entry.fn, payload);
  },

  // ---- Host services ----
  // Read-only view of what the app currently has open. A copy, so an
  // extension cannot write to `S` through it.
  state() {
    return {
      boot: typeof S === "object" && S ? S.boot : null,
      chat: typeof S === "object" && S ? S.chat : null,
      chatId: typeof S === "object" && S ? S.chatId : null
    };
  },

  // Late-bound on purpose: `api` is defined in utils.js, but a property
  // initialised to `api` here would capture whatever that name meant at LOAD
  // time, and this file is parsed before app.js has run any of it.
  api(...args) { return window.api(...args); },

  call(extId, method, path, body) {
    return window.api(method, `/api/extensions/${extId}${path}`, body);
  },

  // An extension's chat-scoped state. Null chat is a normal condition (no
  // story open yet), not an error, so it resolves to null rather than
  // fetching a route that has nothing to answer with.
  extState(extId) {
    const chatId = typeof S === "object" && S ? S.chatId : null;
    if (!chatId) return Promise.resolve(null);
    return window.api("GET", `/api/extensions/${extId}/state?chat_id=${chatId}`);
  },

  // Redraw whatever the host currently shows. Guarded the same way boot()
  // guards the optional modules: this may be called from a page that never
  // loaded the chat view.
  refresh() {
    if (typeof renderSide === "function") renderSide();
    if (typeof renderChat === "function") renderChat();
  },

  // ---- Host-internal accessors ----
  // Used by app.js and chat.js; not part of what an extension calls.
  _sidebarTabs() { return [...Sonder._sidebar]; },

  _renderSidebarTab(id, container) {
    const tab = Sonder._sidebar.find(entry => entry.id === id);
    if (!tab) return false;
    // `render` may be async; a rejected promise is a throw the try/catch in
    // `_safe` never sees, so charge it to the same counter by hand.
    const result = Sonder._safe(tab.owner, tab.render, container);
    if (result && typeof result.catch === "function") {
      result.catch(error => Sonder._fault(tab.owner, error));
    }
    return true;
  },

  // Returns a already-safe-wrapped renderer, or null. The caller can then
  // treat "an extension owns this step" as a plain truthiness test.
  _stepRenderer(key) {
    const entry = Sonder._steps.get(String(key || ""));
    if (!entry) return null;
    return (content, container, step) =>
      Sonder._safe(entry.owner, entry.fn, content, container, step);
  },

  // Teardown: drop every registration owned by `extId`. Called by the
  // three-strikes rule, and by the host when an extension is disabled.
  _unregister(extId) {
    if (!extId) return;
    Sonder._sidebar = Sonder._sidebar.filter(tab => tab.owner !== extId);
    for (const [key, entry] of [...Sonder._steps]) {
      if (entry.owner === extId) Sonder._steps.delete(key);
    }
    for (const [event, list] of [...Sonder._events]) {
      Sonder._events.set(event, list.filter(entry => entry.owner !== extId));
    }
    Sonder._faults.delete(extId);
  }
};

window.Sonder = Sonder;
