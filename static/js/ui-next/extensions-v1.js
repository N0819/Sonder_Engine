export const MODULE_RELEASE = "alpha98-ui6-57d168ae23cf";

const LEGACY_REGISTRATIONS = Object.freeze({
  registerSidebarTab: ["legacy-sidebar", "render"],
  registerTopBarButton: ["legacy-topbar", "onClick"],
  registerView: ["legacy-view", "render"],
  registerComposerControl: ["legacy-composer", "render"],
  registerSettingsSection: ["addon-settings", "render"],
});

export function createV1Adapter(registry) {
  let adapter;

  const registerDefinition = (kind, callbackName, definition = {}) => {
    if (!definition.id || typeof definition[callbackName] !== "function") return false;
    return registry.registerAmbient(kind, definition);
  };

  const boundFacade = owner => {
    const facade = { apiVersion: 1, id: owner, chats: registry.chats };
    const publicNames = [
      ...Object.keys(LEGACY_REGISTRATIONS),
      "registerStepRenderer",
      "openView",
      "closeView",
      "notify",
      "dismissNotice",
      "notices",
      "on",
      "off",
      "state",
      "api",
      "call",
      "extState",
      "refresh",
    ];
    for (const name of publicNames) {
      facade[name] = (...args) => registry.withOwner(owner, () => adapter[name](...args));
    }
    return Object.freeze(facade);
  };

  adapter = {
    apiVersion: 1,
    _begin: owner => registry.begin(owner),
    _end: () => registry.end(),
    _fault: (owner, error) => registry.fault(owner, error),
    _safe: (owner, callback, ...args) => registry.safe(owner, callback, ...args),
    _facade: owner => boundFacade(owner),
    _loadModule: (owner, href) => registry.loadModule(owner, href),
    _load: async owner => {
      const [result] = await registry.loadEnabled([{
        id: owner,
        enabled: true,
        capabilities: { ui: { js: "ui.js", css: "ui.css" } },
      }]);
      return result?.loaded === true;
    },
    _unload: owner => registry.unregisterOwner(owner),
    _unregister: owner => registry.unregisterOwner(owner),
    _sidebarTabs: () => registry.entries("legacy-sidebar"),
    _settingsFor: owner => registry.entries("addon-settings")
      .filter(entry => entry.owner === String(owner)),
    _stepRenderer: key => {
      const entry = registry.entries("legacy-step").find(item => item.id === String(key));
      return entry ? (...args) => registry.run(entry, "render", ...args) : null;
    },
    emit: (event, payload) => registry.emitEvent(event, payload),
    registerStepRenderer: (key, render) => (
      typeof render === "function"
        ? registry.registerAmbient("legacy-step", { id: String(key), render })
        : false
    ),
    openView: id => registry.setOpenView(id),
    closeView: () => registry.setOpenView(null),
    notify: definition => registry.notify(definition),
    dismissNotice: id => registry.dismissNotice(id),
    notices: () => registry.notices(),
    on: (event, callback) => registry.on(event, callback),
    off: (event, callback) => registry.off(event, callback),
    state: () => registry.state(),
    api: (method, path, body) => registry.api(method, path, body),
    call: (owner, method, path, body) => registry.call(owner, method, path, body),
    extState: owner => {
      const chatId = registry.state().chatId;
      return chatId
        ? registry.api("GET", `/api/extensions/${encodeURIComponent(owner)}/state?chat_id=${encodeURIComponent(chatId)}`)
        : Promise.resolve(null);
    },
    chats: registry.chats,
    refresh: () => registry.refresh(),
  };

  for (const [name, [kind, callbackName]] of Object.entries(LEGACY_REGISTRATIONS)) {
    adapter[name] = definition => registerDefinition(kind, callbackName, definition);
  }
  registry.setLegacyFacadeFactory(boundFacade);
  return Object.freeze(adapter);
}

export function installV1Adapter(adapter) {
  window.Sonder = adapter;
  return () => {
    if (window.Sonder === adapter) delete window.Sonder;
  };
}
