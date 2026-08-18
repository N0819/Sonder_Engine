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
  _topbar: [],
  _views: [],
  _composer: [],
  //: the open view's id, or null for the transcript. Host-owned, so disabling
  //: an extension whose view is open can put the reader back on their story.
  _openView: null,
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

  // ---- ES module entries ----
  //
  // The classic path attributes registrations with a `_begin(id)`/`_end()`
  // pair around synchronous top-level code. That does not survive a module: a
  // `register` may await, and ambient owner state set before the await belongs
  // to somebody else after it. So a module gets an ID-BOUND facade instead and
  // never relies on `_owner` at all.
  //
  // The facade carries whatever this registry publishes, DERIVED rather than
  // listed: a hand-kept list is a second copy of the registration surface, and
  // the copy that falls behind is the one nobody notices -- a call added below
  // would work for a classic `ui.js` extension and simply not exist for a
  // module one, which reads as "modules are broken".
  //
  // The `_` prefix is the whole convention: everything host-internal already
  // wears one, so "public" needs no separate declaration to stay true.
  _publicNames() {
    return Object.keys(Sonder).filter(
      name => name.charAt(0) !== "_" && typeof Sonder[name] === "function");
  },

  _facade(extId) {
    const owner = String(extId || "");
    const facade = { id: owner };
    for (const name of Sonder._publicNames()) {
      const fn = Sonder[name];
      facade[name] = (...args) => {
        const previous = Sonder._owner;
        Sonder._owner = owner;
        try { return fn.apply(Sonder, args); }
        finally { Sonder._owner = previous; }
      };
    }
    return facade;
  },

  // Load one extension's ES module and hand it its facade. Called from the
  // loader line the server emits for a `capabilities.ui.module` entry, so an
  // extension author never writes this call themselves.
  //
  // Resolves rather than rejects on every path: a broken extension is charged
  // a fault and the host keeps its page.
  async _loadModule(extId, href) {
    const owner = String(extId || "");
    let module = null;
    try {
      module = await import(href);
    } catch (error) {
      Sonder._fault(owner, error);
      return false;
    }
    const register = module && module.register;
    if (typeof register !== "function") {
      // Not an error -- a module may have done its work at import time -- but
      // nothing it registered while importing was attributed to it, so say so
      // once rather than leaving a silent no-op to be debugged later.
      console.warn({ extension: owner, missing: "register" });
      return true;
    }
    try {
      await register(Sonder._facade(owner));
    } catch (error) {
      Sonder._fault(owner, error);
      return false;
    }
    // A module registers AFTER boot has drawn the page -- import resolution is
    // asynchronous, so unlike a classic entry it cannot rely on a render that
    // has not happened yet. Redraw once, here, so a sidebar tab registered by
    // a module is not invisible until the reader clicks something.
    Sonder._safe(owner, () => Sonder.refresh());
    return true;
  },

  // ---- Registration surface ----
  registerSidebarTab({ id, label, render }) {
    if (!id || typeof render !== "function") return;
    const owner = Sonder._owner;
    Sonder._sidebar = Sonder._sidebar.filter(tab => tab.id !== id);
    Sonder._sidebar.push({ id: String(id), label: String(label || id), render, owner });
  },

  // A button beside the host's own in the story toolbar. The launcher an
  // overlay extension needs: without one it has to find `#topactions` and
  // append to it, which works and is outside every safety net here -- a throw
  // in the handler is not charged to anyone and disabling the extension leaves
  // the button on the page.
  registerTopBarButton({ id, icon, title, onClick }) {
    if (!id || typeof onClick !== "function") return;
    const owner = Sonder._owner;
    Sonder._topbar = Sonder._topbar.filter(item => item.id !== id);
    Sonder._topbar.push({
      id: String(id), icon: String(icon || "🧩"),
      title: String(title || id), onClick, owner
    });
    Sonder._renderTopBar();
  },

  // A full-window surface over the transcript, which is what an extension that
  // is an APPLICATION rather than a panel actually needs. The host owns the
  // container and the open/close state, so `_unload` can take a view away and
  // a throw inside `render` is charged to its owner -- neither of which is
  // true of an extension that appends its own overlay to `document.body`.
  registerView({ id, label, render }) {
    if (!id || typeof render !== "function") return;
    const owner = Sonder._owner;
    Sonder._views = Sonder._views.filter(view => view.id !== id);
    Sonder._views.push({ id: String(id), label: String(label || id), render, owner });
  },

  // A control beside the composer's send button.
  registerComposerControl({ id, render }) {
    if (!id || typeof render !== "function") return;
    const owner = Sonder._owner;
    Sonder._composer = Sonder._composer.filter(item => item.id !== id);
    Sonder._composer.push({ id: String(id), render, owner });
    Sonder._renderComposer();
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
    Sonder._renderTopBar();
    Sonder._renderComposer();
    Sonder._renderView();
  },

  // Open one registered view over the transcript, or return to the story with
  // `closeView()`. Both are callable by an extension -- a launcher button that
  // could not open its own app would be decoration.
  openView(id) {
    const view = Sonder._views.find(entry => entry.id === String(id || ""));
    if (!view) return false;
    Sonder._openView = view.id;
    Sonder._renderView();
    return true;
  },

  closeView() {
    if (Sonder._openView === null) return;
    Sonder._openView = null;
    Sonder._renderView();
  },

  // ---- Host-internal accessors ----
  // Used by app.js and chat.js; not part of what an extension calls.
  _sidebarTabs() { return [...Sonder._sidebar]; },

  // Redraw the extension buttons in the story toolbar. Host elements are left
  // alone: only nodes this registry created are removed, matched by a data
  // attribute rather than by position, so the host may add or reorder its own
  // buttons without this having to know.
  _renderTopBar() {
    const host = document.getElementById("topactions");
    if (!host) return;
    for (const node of [...host.querySelectorAll("[data-ext-button]")]) {
      node.remove();
    }
    for (const item of Sonder._topbar) {
      const button = document.createElement("button");
      button.className = "icon-button";
      button.dataset.extButton = item.id;
      button.textContent = item.icon;
      button.title = item.title;
      button.setAttribute("aria-label", item.title);
      button.onclick = () => Sonder._safe(item.owner, item.onClick);
      host.append(button);
    }
  },

  _renderComposer() {
    const host = document.getElementById("composer-inner");
    if (!host) return;
    for (const node of [...host.querySelectorAll("[data-ext-composer]")]) {
      node.remove();
    }
    for (const item of Sonder._composer) {
      const slot = document.createElement("span");
      slot.dataset.extComposer = item.id;
      host.append(slot);
      const result = Sonder._safe(item.owner, item.render, slot);
      if (result && typeof result.catch === "function") {
        result.catch(error => Sonder._fault(item.owner, error));
      }
    }
  },

  // Draw or tear down the open view. The container is created on demand and
  // removed on close rather than left hidden, because a view left in the DOM
  // keeps its timers, its listeners and its scroll position -- and an
  // extension retired mid-view would leave all three running.
  _renderView() {
    const main = document.getElementById("main");
    if (!main) return;
    const existing = document.getElementById("ext-view");
    if (existing) existing.remove();
    const view = Sonder._views.find(entry => entry.id === Sonder._openView);
    if (!view) {
      Sonder._openView = null;
      main.classList.remove("ext-view-open");
      return;
    }
    const container = document.createElement("div");
    container.id = "ext-view";
    container.dataset.extView = view.id;
    main.append(container);
    main.classList.add("ext-view-open");
    const result = Sonder._safe(view.owner, view.render, container);
    if (result && typeof result.catch === "function") {
      result.catch(error => Sonder._fault(view.owner, error));
    }
  },

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
  //
  // What this can and cannot undo is worth being exact about: it removes every
  // registration made through this registry, and the script and stylesheet
  // elements the host injected. It cannot undo side effects the extension's
  // code had on its way past -- a monkeypatched global, a timer, a listener
  // added straight to `document`. An extension that does those things and
  // wants to be cleanly disableable has to undo them itself.
  _unregister(extId) {
    if (!extId) return;
    Sonder._sidebar = Sonder._sidebar.filter(tab => tab.owner !== extId);
    Sonder._topbar = Sonder._topbar.filter(item => item.owner !== extId);
    Sonder._composer = Sonder._composer.filter(item => item.owner !== extId);
    // A view belonging to a retired extension must not stay on screen: the
    // reader would be left looking at a dead application with no way back to
    // their story, which is the worst failure this registry can produce.
    const open = Sonder._views.find(view => view.id === Sonder._openView);
    if (open && open.owner === extId) Sonder._openView = null;
    Sonder._views = Sonder._views.filter(view => view.owner !== extId);
    Sonder._renderTopBar();
    Sonder._renderComposer();
    Sonder._renderView();
    for (const [key, entry] of [...Sonder._steps]) {
      if (entry.owner === extId) Sonder._steps.delete(key);
    }
    for (const [event, list] of [...Sonder._events]) {
      Sonder._events.set(event, list.filter(entry => entry.owner !== extId));
    }
    Sonder._faults.delete(extId);
    Sonder._dropAssets(extId);
  },

  // ---- Hot load / unload ----
  //
  // The page-load path is one `<script>` for every enabled extension, and a
  // script tag loads once: a page served while an extension was disabled holds
  // an EMPTY bundle forever, so enabling it made the pipeline stage appear on
  // the next turn while the sidebar tab never did. Measured in play, not in
  // tests. Every registry is genuinely consulted per use -- it was the
  // bundle's ARRIVAL that was page-bound, so that is what these fix.
  //
  // Ids are host-controlled (they come back from `/api/extensions`, and the
  // server validates them against EXTENSION_ID before anything is served), but
  // they still go through `encodeURIComponent` and into `dataset` rather than
  // into an interpolated selector.
  _elementId(kind, extId) { return `ext-${kind}-${extId}`; },

  _dropAssets(extId) {
    for (const kind of ["js", "css"]) {
      const node = document.getElementById(Sonder._elementId(kind, extId));
      if (node) node.remove();
    }
  },

  // Load one extension's assets into the live page. Resolves when its script
  // has run (or failed), so the caller can redraw and see the new tab.
  _load(extId) {
    if (!extId) return Promise.resolve(false);
    Sonder._dropAssets(extId);
    const encoded = encodeURIComponent(extId);

    const style = document.createElement("link");
    style.id = Sonder._elementId("css", extId);
    style.rel = "stylesheet";
    style.href = `/api/extensions/${encoded}/ui.css`;
    document.head.append(style);

    return new Promise(resolve => {
      const script = document.createElement("script");
      script.id = Sonder._elementId("js", extId);
      script.src = `/api/extensions/${encoded}/ui.js`;
      // Both paths resolve: a failed fetch is a broken extension, not a
      // broken host, and the caller still has a page to redraw.
      script.onload = () => resolve(true);
      script.onerror = () => { Sonder._fault(extId, new Error("ui.js")); resolve(false); };
      document.body.append(script);
    });
  },

  // Disable: drop the registrations, then the assets. Order matters only in
  // that `_unregister` already drops the assets, so this stays one call.
  _unload(extId) { Sonder._unregister(extId); }
};

window.Sonder = Sonder;
