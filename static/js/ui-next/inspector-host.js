export const MODULE_RELEASE = "wp05.1";

import { createOverlayController } from "../ui/components/overlay.js?release=wp05.1";

const LAYER_ID = "inspector:context";
const SIZES = Object.freeze(["narrow", "default", "wide"]);

// UI_CATALOG_START: responsive inspector labels and states.
const INSPECTOR_COPY = Object.freeze({
  libraryTitle: "Library details",
  libraryBody: "Choose an item when the Library replacement arrives to see its details here.",
  settingsTitle: "Settings help",
  settingsBody: "Contextual guidance appears here without moving system controls into Play.",
  storyTitle: "Story tools",
  storyBody: "Choose a story before opening its contextual tools.",
  close: "Close",
});
// UI_CATALOG_END

function createElement(documentRef, tag, className = "", text = "") {
  const node = documentRef.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function safePanes(localState) {
  const panes = localState.snapshot().panes || {};
  const inspector = panes.inspector || {};
  return {
    open: inspector.open !== false,
    pinned: inspector.pinned !== false,
    size: SIZES.includes(inspector.size) ? inspector.size : "default",
  };
}

function contextCopy(destination, t) {
  if (destination === "library") {
    return {
      title: t("Library details"),
      body: t(INSPECTOR_COPY.libraryBody),
    };
  }
  if (destination === "settings") {
    return {
      title: t(INSPECTOR_COPY.settingsTitle),
      body: t(INSPECTOR_COPY.settingsBody),
    };
  }
  return {
    title: t(INSPECTOR_COPY.storyTitle),
    body: t(INSPECTOR_COPY.storyBody),
  };
}

function sheetContent(documentRef, t) {
  const overlay = createElement(documentRef, "div", "ui-overlay");
  overlay.hidden = true;
  overlay.dataset.shellInspectorSheet = "true";
  const sheet = createElement(documentRef, "section", "ui-sheet ui-shell__inspector-sheet");
  sheet.setAttribute("role", "dialog");
  sheet.setAttribute("aria-modal", "true");
  sheet.setAttribute("aria-labelledby", "ui-shell-inspector-sheet-title");
  const header = createElement(documentRef, "header", "ui-shell__inspector-header");
  const heading = createElement(documentRef, "h2", "ui-heading ui-heading--2", t(INSPECTOR_COPY.storyTitle));
  heading.id = "ui-shell-inspector-sheet-title";
  heading.tabIndex = -1;
  const close = createElement(documentRef, "button", "ui-button ui-button--quiet", t(INSPECTOR_COPY.close));
  close.type = "button";
  close.dataset.shellInspectorSheetClose = "true";
  header.append(heading, close);
  const body = createElement(documentRef, "div", "ui-shell__inspector-body");
  sheet.append(header, body);
  overlay.append(sheet);
  return { overlay, heading, body, close };
}

export function createInspectorHost(options = {}) {
  const { services, modules } = options;
  const documentRef = options.document || document;
  const root = options.root || documentRef.documentElement;
  const aside = documentRef.querySelector("[data-shell-inspector]");
  const heading = documentRef.querySelector("[data-shell-inspector-heading]");
  const body = documentRef.querySelector("[data-shell-inspector-body]");
  const openButton = documentRef.querySelector("[data-shell-inspector-open]");
  const closeButton = documentRef.querySelector("[data-shell-inspector-close]");
  const pinButton = documentRef.querySelector("[data-shell-inspector-pin]");
  const resizeButton = documentRef.querySelector("[data-shell-inspector-resize]");
  const overlayHost = documentRef.querySelector("[data-shell-overlay-host]");
  if (!aside || !heading || !body || !openButton || !closeButton
      || !pinButton || !resizeButton || !overlayHost) {
    throw new Error("The contextual inspector frame is incomplete.");
  }

  let panes = safePanes(services.localState);
  let layout = root.dataset.layoutState || "wide";
  let route = services.router.current();
  let syncing = false;
  let stopped = false;
  let desktopStoryTools = null;
  let sheetStoryTools = null;
  const sheet = sheetContent(documentRef, services.localizer.t);
  overlayHost.append(sheet.overlay);
  const overlay = createOverlayController(sheet.overlay, {
    backgroundRoot: overlayHost.parentElement,
    onClose: () => {
      if (!syncing && services.router.current().layers.some(layer => layer.id === LAYER_ID)) {
        services.router.closeTopLayer();
      }
    },
  });

  const persist = () => {
    const current = services.localState.snapshot().panes || {};
    services.localState.setRecord("panes", { ...current, inspector: panes });
  };

  const clearStoryTools = () => {
    desktopStoryTools?.teardown();
    sheetStoryTools?.teardown();
    desktopStoryTools = null;
    sheetStoryTools = null;
  };

  const updateCopy = destination => {
    const copy = contextCopy(destination, services.localizer.t);
    heading.textContent = copy.title;
    sheet.heading.textContent = copy.title;
    clearStoryTools();
    if (destination === "play" && modules?.storyToolsView && modules?.storyToolsRegistry) {
      desktopStoryTools = modules.storyToolsView.mountStoryTools({
        document: documentRef,
        services,
        registry: modules.storyToolsRegistry,
        target: body,
        compact: false,
        interactive: isPaneLayout() && panes.open,
        tools: modules.liveStoryTools,
      });
      sheetStoryTools = modules.storyToolsView.mountStoryTools({
        document: documentRef,
        services,
        registry: modules.storyToolsRegistry,
        target: sheet.body,
        compact: true,
        interactive: !isPaneLayout() && layerOpen(),
        tools: modules.liveStoryTools,
      });
      return;
    }
    body.replaceChildren(createElement(documentRef, "p", "ui-muted", copy.body));
    sheet.body.replaceChildren(createElement(documentRef, "p", "ui-muted", copy.body));
  };

  const layerOpen = () => route.layers.some(layer => layer.id === LAYER_ID);
  const isPaneLayout = () => layout === "wide" || layout === "expansive";

  const apply = () => {
    if (stopped) return;
    root.dataset.inspectorOpen = String(panes.open);
    root.dataset.inspectorSize = panes.size;
    root.dataset.inspectorPinned = String(panes.pinned);
    pinButton.setAttribute("aria-pressed", String(panes.pinned));
    aside.hidden = !isPaneLayout() || !panes.open;
    updateCopy(route.destination);
    syncing = true;
    if (!isPaneLayout() && layerOpen()) overlay.show();
    else overlay.close("layout-sync");
    syncing = false;
  };

  const open = () => {
    if (isPaneLayout()) {
      panes = { ...panes, open: true };
      persist();
      apply();
      heading.focus({ preventScroll: true });
      return;
    }
    if (!layerOpen()) {
      services.router.openLayer({ id: LAYER_ID, focusReturn: "inspector-toggle" });
    }
    route = services.router.current();
    apply();
  };

  const close = () => {
    if (isPaneLayout()) {
      panes = { ...panes, open: false };
      persist();
      apply();
      openButton.focus({ preventScroll: true });
      return;
    }
    services.router.closeTopLayer();
  };

  const togglePin = () => {
    panes = { ...panes, pinned: !panes.pinned };
    persist();
    apply();
  };

  const resize = () => {
    const next = SIZES[(SIZES.indexOf(panes.size) + 1) % SIZES.length];
    panes = { ...panes, size: next };
    persist();
    apply();
  };

  openButton.addEventListener("click", open);
  closeButton.addEventListener("click", close);
  sheet.close.addEventListener("click", close);
  pinButton.addEventListener("click", togglePin);
  resizeButton.addEventListener("click", resize);

  const sync = nextRoute => {
    route = nextRoute;
    if (!panes.pinned && route.destination !== "play" && isPaneLayout()) {
      panes = { ...panes, open: false };
      persist();
    }
    apply();
  };
  const setLayout = nextLayout => {
    layout = nextLayout;
    if (isPaneLayout() && layerOpen()) services.router.closeTopLayer();
    apply();
  };

  apply();
  const teardown = () => {
    if (stopped) return;
    stopped = true;
    openButton.removeEventListener("click", open);
    closeButton.removeEventListener("click", close);
    sheet.close.removeEventListener("click", close);
    pinButton.removeEventListener("click", togglePin);
    resizeButton.removeEventListener("click", resize);
    clearStoryTools();
    overlay.destroy();
    sheet.overlay.remove();
  };

  return Object.freeze({ sync, setLayout, open, close, teardown });
}
