export const MODULE_RELEASE = "alpha98-ui14-8c5f0c3f2d06";

import { canPinContext } from "./layout-contract.js?release=alpha98-ui14-8c5f0c3f2d06";
import { focusRouteTarget } from "../ui/components/route-focus.js?release=alpha98-ui14-8c5f0c3f2d06";

const LAYER_ID = "inspector:context";

const INSPECTOR_COPY = Object.freeze({
  libraryTitle: "Library details",
  libraryBody: "Select a Library row to see its usage and details.",
  settingsTitle: "Settings help",
  settingsBody: "Contextual guidance appears here without moving system controls into Play.",
  storyTitle: "Story tools",
  storyBody: "Choose a story before opening its contextual tools.",
});

function createElement(documentRef, tag, className = "", text = "") {
  const node = documentRef.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function safePanes(localState) {
  const panes = localState.snapshot().panes || {};
  const inspector = panes.inspector || {};
  return { open: inspector.open === true, pinned: inspector.pinned === true };
}

function contextCopy(destination, t) {
  if (destination === "library") {
    return { title: t(INSPECTOR_COPY.libraryTitle), body: t(INSPECTOR_COPY.libraryBody) };
  }
  if (destination === "settings") {
    return { title: t(INSPECTOR_COPY.settingsTitle), body: t(INSPECTOR_COPY.settingsBody) };
  }
  return { title: t(INSPECTOR_COPY.storyTitle), body: t(INSPECTOR_COPY.storyBody) };
}

function inspectorKind(destination) {
  if (destination === "play") return "story-tools";
  if (destination === "library") return "library-details";
  return "context";
}

export function createInspectorHost(options = {}) {
  const { services, modules } = options;
  const documentRef = options.document || document;
  const target = documentRef.defaultView || window;
  const root = options.root || documentRef.documentElement;
  const aside = documentRef.querySelector("[data-shell-inspector]");
  const heading = documentRef.querySelector("[data-shell-inspector-heading]");
  const body = documentRef.querySelector("[data-shell-inspector-body]");
  const openButton = documentRef.querySelector("[data-shell-inspector-open]");
  const openButtonLabel = openButton?.querySelector(".ui-icon-label");
  const closeButton = documentRef.querySelector("[data-shell-inspector-close]");
  const pinButton = documentRef.querySelector("[data-shell-inspector-pin]");
  const overlayHost = documentRef.querySelector("[data-shell-overlay-host]");
  if (!aside || !heading || !body || !openButton || !closeButton || !pinButton || !overlayHost) {
    throw new Error("The contextual drawer frame is incomplete.");
  }

  let panes = safePanes(services.localState);
  let route = services.router.current();
  let stopped = false;
  let contextMount = null;
  let mountedIdentity = "";
  let applying = false;

  const drawer = modules.responsiveDrawer.createResponsiveDrawer({
    document: documentRef,
    root,
    surface: aside,
    overlayHost,
    onRequestClose: () => close(),
  });

  const persist = () => {
    const current = services.localState.snapshot().panes || {};
    services.localState.setRecord("panes", { ...current, inspector: panes });
  };
  const layerOpen = () => route.layers.some(layer => layer.id === LAYER_ID);
  const personAuthoring = () => modules.libraryAuthoringView.isPersonAuthoringRoute(route);
  const pinAllowed = () => canPinContext({
    viewportWidth: target.innerWidth,
    viewportHeight: target.innerHeight,
    railWidth: root.dataset.navCollapsed === "true" ? 72 : 192,
    drawerWidth: 360,
  });
  const desiredMode = () => {
    if (personAuthoring() || !panes.open) return "closed";
    if (panes.pinned && pinAllowed()) return "pinned";
    return "overlay";
  };

  const clearContext = () => {
    contextMount?.teardown?.();
    contextMount = null;
    body.replaceChildren();
  };
  const mountContext = () => {
    const authoringMode = ["edit", "import", "create", "story-card"].includes(route.query?.mode);
    const identity = `${route.destination}:${authoringMode}:${route.query?.item || ""}`;
    if (identity === mountedIdentity && body.childElementCount) return;
    mountedIdentity = identity;
    clearContext();
    const copy = contextCopy(route.destination, services.localizer.t);
    heading.textContent = copy.title;
    aside.setAttribute("aria-label", copy.title);
    if (route.destination === "play") {
      contextMount = modules.storyToolsView.mountStoryTools({
        document: documentRef,
        services,
        registry: modules.storyToolsRegistry,
        target: body,
        compact: desiredMode() !== "pinned",
        interactive: desiredMode() !== "closed",
        tools: modules.liveStoryTools,
      });
      return;
    }
    if (route.destination === "library") {
      body.dataset.libraryContext = "true";
      if (personAuthoring()) return;
      const libraryModule = authoringMode ? modules.libraryAuthoringView : modules.libraryView;
      contextMount = (authoringMode
        ? libraryModule.mountLibraryAuthoring : libraryModule.mountLibraryDetail)({
        document: documentRef, services, target: body,
      });
      return;
    }
    body.replaceChildren(createElement(documentRef, "p", "ui-muted", copy.body));
  };

  const apply = () => {
    if (stopped || applying) return;
    applying = true;
    const authoring = personAuthoring();
    if (panes.pinned && !pinAllowed()) {
      panes = { ...panes, pinned: false };
      persist();
      if (panes.open && !layerOpen()) {
        services.router.openLayer({ id: LAYER_ID, focusReturn: "inspector-toggle" });
        route = services.router.current();
      }
    }
    const mode = desiredMode();
    root.dataset.libraryAuthoring = String(authoring);
    root.dataset.inspectorOpen = String(mode !== "closed");
    root.dataset.inspectorPinned = String(mode === "pinned");
    root.dataset.inspectorKind = inspectorKind(route.destination);
    pinButton.hidden = !pinAllowed();
    pinButton.setAttribute("aria-pressed", String(mode === "pinned"));
    const contextAvailable = route.destination === "play"
      || (route.destination === "library" && Boolean(route.query?.item));
    const openerLabel = route.destination === "library" ? "Library details" : "Story tools";
    openButton.hidden = authoring || !contextAvailable || mode !== "closed";
    openButton.setAttribute("aria-label", `Open ${openerLabel.toLowerCase()}`);
    openButton.title = openerLabel;
    if (openButtonLabel) openButtonLabel.textContent = openerLabel;
    mountContext();
    drawer.setMode(mode);
    applying = false;
  };

  function open() {
    const keepPinned = panes.pinned && pinAllowed();
    panes = { ...panes, open: true, pinned: keepPinned };
    persist();
    if (!keepPinned && !layerOpen()) {
      services.router.openLayer({ id: LAYER_ID, focusReturn: "inspector-toggle" });
    }
    route = services.router.current();
    mountedIdentity = "";
    apply();
  }
  function close() {
    panes = { ...panes, open: false, pinned: false };
    persist();
    if (layerOpen()) services.router.closeTopLayer();
    route = services.router.current();
    apply();
    focusRouteTarget(openButton);
  }
  const togglePin = () => {
    if (!pinAllowed()) return;
    panes = { ...panes, open: true, pinned: !panes.pinned };
    persist();
    if (panes.pinned && layerOpen()) services.router.closeTopLayer();
    else if (!panes.pinned && !layerOpen()) {
      services.router.openLayer({ id: LAYER_ID, focusReturn: "inspector-toggle" });
    }
    route = services.router.current();
    mountedIdentity = "";
    apply();
  };

  openButton.addEventListener("click", open);
  closeButton.addEventListener("click", close);
  pinButton.addEventListener("click", togglePin);
  const onLibrarySelect = () => open();
  documentRef.addEventListener("sonder:library-select", onLibrarySelect);

  const sync = nextRoute => {
    const restoreOpener = panes.open && !panes.pinned
      && !nextRoute.layers.some(layer => layer.id === LAYER_ID);
    route = nextRoute;
    if (!layerOpen() && !panes.pinned && panes.open) panes = { ...panes, open: false };
    mountedIdentity = "";
    apply();
    if (restoreOpener) target.requestAnimationFrame(() => focusRouteTarget(openButton));
  };
  const setLayout = () => apply();

  if (route.destination === "library" && route.query?.item && !personAuthoring()) {
    panes = { ...panes, open: true, pinned: false };
    if (!layerOpen()) {
      services.router.openLayer({ id: LAYER_ID, focusReturn: "destination:library" });
      route = services.router.current();
    }
  }
  apply();
  return Object.freeze({
    sync,
    setLayout,
    open,
    close,
    teardown() {
      if (stopped) return;
      stopped = true;
      openButton.removeEventListener("click", open);
      closeButton.removeEventListener("click", close);
      pinButton.removeEventListener("click", togglePin);
      documentRef.removeEventListener("sonder:library-select", onLibrarySelect);
      clearContext();
      drawer.teardown();
    },
  });
}
