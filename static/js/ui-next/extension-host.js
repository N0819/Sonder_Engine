export const MODULE_RELEASE = "alpha98-ui10-0415f377b12f";

const VIEW_KINDS = Object.freeze([
  "destination",
  "legacy-view",
  "addon-settings",
  "play-tool",
  "library-type",
]);
const KIND_DESTINATIONS = Object.freeze({
  destination: "settings",
  "legacy-view": "settings",
  "addon-settings": "settings",
  "play-tool": "play",
  "library-type": "library",
});

// UI_CATALOG_START: contained add-on surface labels and failure states.
const EXTENSION_COPY = Object.freeze({
  view: "Add-on View",
  addon: "Add-on",
  unavailable: "This add-on view is unavailable. The rest of Sonder Engine is still ready.",
  views: "Add-on Views",
  viewsHelp: "Open a contained view supplied by an enabled add-on.",
  removed: "That add-on view is no longer available. Add-ons was opened instead.",
});
// UI_CATALOG_END

function element(documentRef, tag, className = "", text = "") {
  const node = documentRef.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function parentRoute(entryOrRoute) {
  const destination = KIND_DESTINATIONS[entryOrRoute?.kind]
    || String(entryOrRoute?.destination || "settings");
  return destination === "settings"
    ? { destination, segments: ["add-ons"] }
    : { destination, segments: [] };
}

function routeFor(entry) {
  const parent = parentRoute(entry);
  return {
    ...parent,
    query: {
      extension: entry.owner,
      view: entry.id,
      kind: entry.kind,
    },
  };
}

function selectedEntry(registry, route) {
  const owner = String(route?.query?.extension || "");
  const id = String(route?.query?.view || "");
  const kind = String(route?.query?.kind || "legacy-view");
  if (!owner || !id || !VIEW_KINDS.includes(kind)) return null;
  if (KIND_DESTINATIONS[kind] !== route?.destination) return null;
  return registry.entries(kind).find(entry => entry.owner === owner && entry.id === id) || null;
}

export function createExtensionHost(options = {}) {
  const { services } = options;
  const documentRef = options.document || document;
  const t = services.localizer.t;
  let route = services.router.current();
  let active = null;
  let stopped = false;

  const viewEntries = currentRoute => VIEW_KINDS
    .filter(kind => KIND_DESTINATIONS[kind] === currentRoute?.destination)
    .flatMap(kind => services.registry.entries(kind));

  const cleanupActive = () => {
    if (!active) return;
    try {
      active.teardown?.();
    } catch {
      // A view teardown cannot keep the shell from moving to another surface.
    }
    active.container.remove();
    active = null;
  };

  const mount = (entry, host) => {
    cleanupActive();
    const section = element(documentRef, "section", "ui-card ui-extension-view");
    section.dataset.extensionOwner = entry.owner;
    section.dataset.extensionView = entry.id;
    const header = element(documentRef, "header", "ui-extension-view__header");
    header.append(
      element(documentRef, "p", "ui-shell__eyebrow", t(EXTENSION_COPY.view)),
      element(documentRef, "h2", "ui-heading ui-heading--2", String(entry.label || entry.title || entry.id)),
    );
    const container = element(documentRef, "div", "ui-extension-view__mount");
    container.setAttribute("role", "region");
    container.setAttribute("aria-label", String(entry.label || entry.title || entry.id));
    section.append(header, container);
    host.append(section);
    active = { entry, container: section, teardown: null };
    const result = services.registry.run(entry, "render", container);
    Promise.resolve(result).then(teardown => {
      if (!active || active.entry !== entry) {
        if (typeof teardown === "function") teardown();
        return;
      }
      if (typeof teardown === "function") active.teardown = teardown;
      if (!container.childNodes.length && !container.textContent.trim()) {
        const unavailable = element(
          documentRef,
          "div",
          "ui-empty",
          t(EXTENSION_COPY.unavailable),
        );
        unavailable.dataset.state = "error";
        container.append(unavailable);
      }
    });
  };

  const launcher = (entry, host) => {
    const link = element(
      documentRef,
      "a",
      "ui-list-row ui-extension-launcher",
    );
    link.href = services.router.serialize
      ? services.router.serialize(routeFor(entry))
      : `#/settings/add-ons?extension=${encodeURIComponent(entry.owner)}&kind=${encodeURIComponent(entry.kind)}&view=${encodeURIComponent(entry.id)}`;
    link.dataset.extensionOwner = entry.owner;
    link.dataset.extensionView = entry.id;
    const copy = element(documentRef, "span", "ui-list-row__copy");
    copy.append(
      element(documentRef, "span", "ui-list-row__title", String(entry.label || entry.title || entry.id)),
      element(documentRef, "span", "ui-list-row__meta", `${t(EXTENSION_COPY.addon)} · ${entry.owner}`),
    );
    link.append(copy);
    host.append(link);
  };

  const decorate = ({ route: nextRoute, view }) => {
    route = nextRoute;
    cleanupActive();
    const supportedDestination = ["play", "library"].includes(route.destination)
      || (route.destination === "settings" && route.segments?.[0] === "add-ons");
    if (!supportedDestination) return;
    const selected = selectedEntry(services.registry, route);
    if (selected) {
      mount(selected, view);
      return;
    }
    const entries = viewEntries(route);
    if (!entries.length) return;
    const section = element(documentRef, "section", "ui-shell-placeholder ui-extension-launchers");
    section.append(
      element(documentRef, "h2", "ui-heading ui-heading--2", t(EXTENSION_COPY.views)),
      element(documentRef, "p", "ui-muted", t(EXTENSION_COPY.viewsHelp)),
    );
    const list = element(documentRef, "div", "ui-list");
    for (const entry of entries) launcher(entry, list);
    section.append(list);
    view.append(section);
  };

  const goToResults = () => VIEW_KINDS.flatMap(kind => services.registry.entries(kind)).map(entry => ({
    label: String(entry.label || entry.title || entry.id),
    context: `${t(EXTENSION_COPY.view)} · ${entry.owner}`,
    route: routeFor(entry),
  }));

  const onRegistryChange = () => {
    if (stopped) return;
    if (route.query?.extension && !selectedEntry(services.registry, route)) {
      cleanupActive();
      services.notices.problem({
        owner: String(route.query.extension),
        condition: "extension-view-unavailable",
        message: t(EXTENSION_COPY.removed),
        error: { kind: "extension", retryable: false },
      });
      services.router.navigate(parentRoute(route), { replace: true });
      return;
    }
    options.onChange?.();
  };

  const unregister = services.registry.subscribe(onRegistryChange);
  const teardown = () => {
    if (stopped) return;
    stopped = true;
    unregister();
    cleanupActive();
  };

  return Object.freeze({ decorate, goToResults, teardown });
}
