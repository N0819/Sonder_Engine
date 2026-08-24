export const MODULE_RELEASE = "alpha98-ui10-0415f377b12f";

export const REGISTRATION_KINDS = Object.freeze([
  "destination",
  "library-type",
  "play-tool",
  "addon-settings",
  "task-provider",
  "legacy-sidebar",
  "legacy-topbar",
  "legacy-composer",
  "legacy-view",
  "legacy-step",
  "notice",
  "event",
]);

const OWNER_ID = /^[a-z][a-z0-9_-]{1,63}$/;
const ENTRY_ID = /^[A-Za-z0-9:._-]{1,160}$/;
const FAULT_LIMIT = 3;

export class ExtensionRegistryError extends Error {
  constructor(kind, message) {
    super(message);
    this.name = "ExtensionRegistryError";
    this.kind = kind;
  }
}

function clone(value) {
  return globalThis.structuredClone
    ? globalThis.structuredClone(value)
    : JSON.parse(JSON.stringify(value));
}

function deepFreeze(value) {
  if (!value || typeof value !== "object" || Object.isFrozen(value)) return value;
  for (const child of Object.values(value)) deepFreeze(child);
  return Object.freeze(value);
}

function ownerId(value) {
  const owner = String(value || "");
  if (!OWNER_ID.test(owner)) {
    throw new ExtensionRegistryError("extension-owner", "Extension ownership is invalid.");
  }
  return owner;
}

function entryId(value) {
  const id = String(value || "");
  if (!ENTRY_ID.test(id)) {
    throw new ExtensionRegistryError("extension-entry", "Extension registration identity is invalid.");
  }
  return id;
}

function publicEntry(entry) {
  const output = {};
  for (const [key, value] of Object.entries(entry)) {
    if (typeof value !== "function" && key !== "kind") output[key] = clone(value);
  }
  return deepFreeze(output);
}

export function createExtensionRegistry(options = {}) {
  if (typeof options.apiClient?.request !== "function") {
    throw new ExtensionRegistryError("extension-api", "An API client is required.");
  }
  const registrations = Object.fromEntries(
    REGISTRATION_KINDS.map(kind => [kind, []]),
  );
  const faults = new Map();
  const retired = new Set();
  const assets = new Map();
  const teardowns = new Map();
  const pendingModules = new Map();
  const uiApiVersions = new Map();
  const listeners = new Set();
  const importModule = options.importModule || (href => import(href));
  const documentRef = options.document || document;
  const faultLimit = Math.max(1, Math.min(10, Number(options.faultLimit || FAULT_LIMIT)));
  let ambientOwner = null;
  let openView = null;
  let noticeSequence = 0;
  let eventSequence = 0;

  const emit = () => {
    options.onChange?.();
    for (const listener of [...listeners]) listener();
  };
  const subscribe = listener => {
    if (typeof listener !== "function") return () => {};
    listeners.add(listener);
    return () => listeners.delete(listener);
  };
  const entries = kind => Object.freeze([...(registrations[kind] || [])]);
  const snapshot = () => deepFreeze(Object.fromEntries(
    REGISTRATION_KINDS.map(kind => [kind, registrations[kind].map(publicEntry)]),
  ));

  const register = (ownerValue, kind, definition = {}) => {
    const owner = ownerId(ownerValue);
    if (!REGISTRATION_KINDS.includes(kind)) {
      throw new ExtensionRegistryError("extension-kind", `Unknown extension registration kind: ${kind}`);
    }
    if (retired.has(owner)) return false;
    const id = entryId(definition.id);
    const entry = Object.freeze({ ...definition, id, owner, kind });
    registrations[kind] = registrations[kind].filter(
      current => current.owner !== owner || current.id !== id,
    );
    registrations[kind].push(entry);
    emit();
    return entry;
  };

  const withOwner = (ownerValue, callback) => {
    const owner = ownerId(ownerValue);
    const previous = ambientOwner;
    ambientOwner = owner;
    try {
      return callback();
    } finally {
      ambientOwner = previous;
    }
  };

  const registerAmbient = (kind, definition) => {
    if (!ambientOwner) return false;
    return register(ambientOwner, kind, definition);
  };

  const dropAssets = (ownerValue) => {
    const owner = String(ownerValue || "");
    for (const node of assets.get(owner) || []) node.remove?.();
    assets.delete(owner);
  };

  const callTeardowns = (owner) => {
    for (const teardown of teardowns.get(owner) || []) {
      try {
        const result = teardown();
        if (result && typeof result.catch === "function") result.catch(() => undefined);
      } catch {
        // Teardown is best-effort and cannot keep a retired owner alive.
      }
    }
    teardowns.delete(owner);
  };

  const unregisterOwner = (ownerValue, unregisterOptions = {}) => {
    const owner = ownerId(ownerValue);
    for (const kind of REGISTRATION_KINDS) {
      registrations[kind] = registrations[kind].filter(entry => entry.owner !== owner);
    }
    if (openView?.owner === owner) {
      openView = null;
      options.onViewChange?.(null);
    }
    callTeardowns(owner);
    dropAssets(owner);
    uiApiVersions.delete(owner);
    if (unregisterOptions.retire) retired.add(owner);
    emit();
    return true;
  };

  const fault = (ownerValue, error) => {
    let owner;
    try {
      owner = ownerId(ownerValue);
    } catch {
      return 0;
    }
    const count = (faults.get(owner) || 0) + 1;
    faults.set(owner, count);
    options.onFault?.({
      owner,
      count,
      message: String(error?.message || error || "Extension failed.").slice(0, 300),
    });
    if (count >= faultLimit && !retired.has(owner)) {
      unregisterOwner(owner, { retire: true });
      options.onRetired?.(owner);
    }
    return count;
  };

  const safe = (ownerValue, callback, ...args) => {
    const owner = String(ownerValue || "");
    if (retired.has(owner) || typeof callback !== "function") return undefined;
    try {
      const result = callback(...args);
      if (result && typeof result.then === "function") {
        return result.catch(error => {
          fault(owner, error);
          return undefined;
        });
      }
      return result;
    } catch (error) {
      fault(owner, error);
      return undefined;
    }
  };

  const run = (entry, callbackName, ...args) => {
    if (!entry || !registrations[entry.kind]?.includes(entry)) return undefined;
    return safe(entry.owner, entry[callbackName], ...args);
  };

  const addTeardown = (ownerValue, teardown) => {
    const owner = ownerId(ownerValue);
    if (typeof teardown !== "function") return false;
    const hooks = teardowns.get(owner) || [];
    hooks.push(teardown);
    teardowns.set(owner, hooks);
    return true;
  };

  const loadModuleNow = async (ownerValue, href) => {
    const owner = ownerId(ownerValue);
    if (!String(href || "").startsWith(`/api/extensions/${encodeURIComponent(owner)}/asset/`)) {
      fault(owner, new ExtensionRegistryError("extension-module-url", "Module URL is not owner-bound."));
      return false;
    }
    try {
      const module = await importModule(href);
      if (typeof module?.register !== "function") return true;
      const faultsBefore = faults.get(owner) || 0;
      const moduleFacade = (uiApiVersions.get(owner) || 1) >= 2
        ? facade(owner)
        : legacyFacade(owner);
      const registered = await safe(owner, module.register, moduleFacade);
      if ((faults.get(owner) || 0) > faultsBefore) return false;
      if (typeof registered === "function") addTeardown(owner, registered);
      else if (typeof registered?.teardown === "function") {
        addTeardown(owner, registered.teardown);
      }
      options.onRefresh?.();
      return !retired.has(owner);
    } catch (error) {
      fault(owner, error);
      return false;
    }
  };

  const loadModule = (ownerValue, href) => {
    const owner = ownerId(ownerValue);
    const pending = loadModuleNow(owner, href);
    const owned = pendingModules.get(owner) || new Set();
    owned.add(pending);
    pendingModules.set(owner, owned);
    pending.finally(() => {
      owned.delete(pending);
      if (!owned.size) pendingModules.delete(owner);
    });
    return pending;
  };

  const trackAsset = (owner, node) => {
    node.dataset.sonderExtensionAsset = owner;
    const owned = assets.get(owner) || new Set();
    owned.add(node);
    assets.set(owner, owned);
  };

  const loadElement = (owner, node, parent) => new Promise(resolve => {
    node.addEventListener("load", () => resolve(true), { once: true });
    node.addEventListener("error", event => {
      fault(owner, event.error || new Error("Extension asset failed to load."));
      resolve(false);
    }, { once: true });
    trackAsset(owner, node);
    parent.append(node);
  });

  const loadOwnerAssets = async (extension) => {
    const owner = ownerId(extension?.id);
    if (!extension?.enabled || retired.has(owner)) return { id: owner, loaded: false };
    dropAssets(owner);
    const ui = extension.capabilities?.ui;
    if (!ui || typeof ui !== "object") return { id: owner, loaded: true };
    uiApiVersions.set(owner, Math.max(1, Number(ui.api || 1)));
    const encoded = encodeURIComponent(owner);
    const pending = [];
    if (ui.css) {
      const link = documentRef.createElement("link");
      link.rel = "stylesheet";
      link.href = `/api/extensions/${encoded}/ui.css`;
      link.dataset.sonderExtensionKind = "css";
      pending.push(loadElement(owner, link, documentRef.head));
    }
    if (ui.js || ui.module) {
      const script = documentRef.createElement("script");
      script.src = `/api/extensions/${encoded}/ui.js`;
      script.dataset.sonderExtensionKind = "script";
      pending.push(loadElement(owner, script, documentRef.body));
    }
    const outcomes = await Promise.all(pending);
    const moduleOutcomes = await Promise.allSettled([
      ...(pendingModules.get(owner) || []),
    ]);
    const loaded = outcomes.every(Boolean) && moduleOutcomes.every(outcome => (
      outcome.status === "fulfilled" && outcome.value === true
    ));
    if (!loaded) dropAssets(owner);
    return {
      id: owner,
      loaded,
    };
  };

  const loadEnabled = async (extensions) => Promise.all(
    (extensions || []).filter(extension => extension?.enabled).map(async extension => {
      try {
        return await loadOwnerAssets(extension);
      } catch (error) {
        const owner = String(extension?.id || "");
        fault(owner, error);
        return { id: owner, loaded: false };
      }
    }),
  );

  const state = () => deepFreeze(clone(options.stateProvider?.() || {
    boot: null,
    chat: null,
    chatId: null,
  }));
  const api = async (method, path, body) => {
    const endpoint = String(path || "");
    if (!endpoint.startsWith("/api/") || endpoint.includes("://")) {
      throw new ExtensionRegistryError("extension-api-path", "Extension API paths must be host API paths.");
    }
    const result = await options.apiClient.request(String(method || "GET").toUpperCase(), endpoint, {
      body,
      channel: `extension:${String(method || "GET").toUpperCase()}:${endpoint}`,
      owner: ambientOwner,
    });
    return result.data;
  };

  const call = (extensionId, method, path, body) => {
    const owner = ownerId(extensionId);
    const suffix = String(path || "");
    if (!suffix.startsWith("/x/") || suffix.includes("?") && /(?:token|key|secret|session)=/i.test(suffix)) {
      throw new ExtensionRegistryError("extension-call-path", "Extension route path is invalid.");
    }
    return api(method, `/api/extensions/${encodeURIComponent(owner)}${suffix}`, body);
  };

  const notify = (definition = {}) => {
    const id = `notice-${++noticeSequence}`;
    registerAmbient("notice", {
      ...definition,
      id,
      title: String(definition.title || ""),
      body: String(definition.body || ""),
      level: new Set(["info", "ok", "warn", "err"]).has(definition.level)
        ? definition.level
        : "info",
      onClick: typeof definition.onClick === "function" ? definition.onClick : null,
    });
    const notices = registrations.notice;
    if (notices.length > 8) registrations.notice = notices.slice(notices.length - 8);
    return id;
  };

  const dismissNotice = (id) => {
    registrations.notice = registrations.notice.filter(entry => (
      entry.id !== String(id) || (ambientOwner && entry.owner !== ambientOwner)
    ));
    emit();
  };

  const on = (event, callback) => registerAmbient("event", {
    id: `${entryId(event)}:${++eventSequence}`,
    event: String(event),
    callback,
  });
  const off = (event, callback) => {
    registrations.event = registrations.event.filter(entry => !(
      entry.event === String(event)
      && entry.callback === callback
      && (!ambientOwner || entry.owner === ambientOwner)
    ));
    emit();
  };
  const emitEvent = async (event, payload) => {
    for (const entry of [...registrations.event]) {
      if (entry.event === String(event)) await run(entry, "callback", payload);
    }
  };

  const setOpenView = (id) => {
    if (id === null) {
      openView = null;
      options.onViewChange?.(null);
      return true;
    }
    const entry = registrations["legacy-view"].find(view => (
      view.id === String(id) && (!ambientOwner || view.owner === ambientOwner)
    ));
    if (!entry) return false;
    openView = Object.freeze({ owner: entry.owner, id: entry.id });
    options.onViewChange?.(openView);
    return true;
  };

  const chats = Object.freeze({
    list: () => api("GET", "/api/chats"),
    get: chatId => api("GET", `/api/chats/${encodeURIComponent(chatId)}`),
    create: body => api("POST", "/api/chats", body || {}),
    open: chatId => options.onOpenStory?.(chatId) ?? Promise.resolve(null),
    branch: turnId => api("POST", `/api/turns/${encodeURIComponent(turnId)}/branch`, {}),
    narration: turnId => api("GET", `/api/turns/${encodeURIComponent(turnId)}/narration`),
    selectNarration: (turnId, variantId) => api(
      "POST",
      `/api/turns/${encodeURIComponent(turnId)}/narration`,
      { variant_id: variantId },
    ),
    reroll: turnId => api("POST", `/api/turns/${encodeURIComponent(turnId)}/reroll`, {}),
  });

  const V2_TOKENS = Object.freeze({
    canvas: "--ui-color-canvas",
    surface: "--ui-color-surface-muted",
    text: "--ui-color-text",
    border: "--ui-color-border",
    accent: "--ui-color-interactive",
    danger: "--ui-color-danger",
  });
  const V2_REGISTRATIONS = Object.freeze({
    registerDestination: ["destination", "render"],
    registerLibraryType: ["library-type", "render"],
    registerPlayTool: ["play-tool", "render"],
    registerSettingsSection: ["addon-settings", "render"],
    registerTaskProvider: ["task-provider", "provide"],
  });
  const createV2Facade = owner => {
    const bound = {
      apiVersion: 2,
      id: owner,
      tokens: V2_TOKENS,
      state,
      chats,
      api: (method, path, body) => withOwner(owner, () => api(method, path, body)),
      call: (method, path, body) => withOwner(owner, () => call(owner, method, path, body)),
      notify: definition => withOwner(owner, () => notify(definition)),
      dismissNotice: id => withOwner(owner, () => dismissNotice(id)),
      on: (event, callback) => withOwner(owner, () => on(event, callback)),
      off: (event, callback) => withOwner(owner, () => off(event, callback)),
      addTeardown: teardown => addTeardown(owner, teardown),
      refresh: () => options.onRefresh?.(),
      openStory: chatId => options.onOpenStory?.(chatId) ?? Promise.resolve(null),
    };
    for (const [name, [kind, callbackName]] of Object.entries(V2_REGISTRATIONS)) {
      bound[name] = definition => {
        if (!definition?.id || typeof definition[callbackName] !== "function") return false;
        return register(owner, kind, definition);
      };
    }
    return Object.freeze(bound);
  };

  let makeFacade = options.makeFacade || createV2Facade;
  let makeLegacyFacade = null;
  const facade = ownerValue => makeFacade(ownerId(ownerValue));
  const legacyFacade = ownerValue => {
    const owner = ownerId(ownerValue);
    if (typeof makeLegacyFacade !== "function") {
      throw new ExtensionRegistryError(
        "extension-v1-facade",
        `No extension-v1 adapter is installed for ${owner}.`,
      );
    }
    return makeLegacyFacade(owner);
  };
  const setFacadeFactory = factory => { makeFacade = factory; };
  const setLegacyFacadeFactory = factory => { makeLegacyFacade = factory; };

  return Object.freeze({
    register,
    registerAmbient,
    subscribe,
    entries,
    snapshot,
    withOwner,
    begin: owner => { ambientOwner = ownerId(owner); },
    end: () => { ambientOwner = null; },
    ambientOwner: () => ambientOwner,
    unregisterOwner,
    isRetired: owner => retired.has(String(owner || "")),
    fault,
    faultCount: owner => faults.get(String(owner || "")) || 0,
    safe,
    run,
    addTeardown,
    loadModule,
    loadEnabled,
    dropAssets,
    state,
    api,
    call,
    chats,
    notify,
    dismissNotice,
    notices: () => registrations.notice.map(publicEntry),
    on,
    off,
    emitEvent,
    setOpenView,
    openView: () => openView,
    refresh: () => options.onRefresh?.(),
    openStory: chatId => options.onOpenStory?.(chatId) ?? Promise.resolve(null),
    facade,
    setFacadeFactory,
    setLegacyFacadeFactory,
  });
}
