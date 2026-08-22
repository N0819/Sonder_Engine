export const MODULE_RELEASE = "wp03.1";

export const LAYOUT_STATES = Object.freeze(["compact", "medium", "wide", "expansive"]);

// UI_CATALOG_START: global shell shortcut and orientation labels.
const SHELL_COPY = Object.freeze({
  name: "Sonder Engine",
  openSettings: "Open Settings",
  closeLayer: "Close the top panel",
});
// UI_CATALOG_END

function layoutStateFor(width, height) {
  if (width < 720 || (height <= 430 && width < 900)) return "compact";
  if (width < 1100) return "medium";
  if (width < 1440) return "wide";
  return "expansive";
}

function required(documentRef, selector) {
  const node = documentRef.querySelector(selector);
  if (!node) throw new Error(`Application shell region is missing: ${selector}`);
  return node;
}

function sameShellState(left, right) {
  return left.route === right.route
    && left.story === right.story
    && left.library === right.library
    && left.settings === right.settings
    && left.extensions === right.extensions;
}

export function createApplicationShell(options = {}) {
  const { services, modules } = options;
  const documentRef = options.document || document;
  const target = options.target || window;
  const root = options.root || documentRef.documentElement;
  if (!services?.store || !services?.router || !services?.localizer) {
    throw new Error("The application shell requires the coherent host runtime.");
  }
  if (!modules?.destinations || !modules?.inspectorHost
      || !modules?.shortcuts || !modules?.goTo || !modules?.extensionHost) {
    throw new Error("The application shell presentation modules are missing.");
  }

  const heading = required(documentRef, "[data-shell-heading]");
  const parent = required(documentRef, "[data-shell-parent]");
  const context = required(documentRef, "[data-shell-context]");
  const view = required(documentRef, "[data-shell-destination-view]");
  const links = [...documentRef.querySelectorAll("[data-core-destination]")];
  const t = services.localizer.t;
  let stopped = false;
  let renderedDestination = null;
  let inspectorHost = null;
  let goTo = null;
  let extensionHost = null;

  const applyLayout = () => {
    root.dataset.layoutState = layoutStateFor(target.innerWidth, target.innerHeight);
    inspectorHost?.setLayout(root.dataset.layoutState);
  };

  const render = shellState => {
    if (stopped) return;
    const destination = modules.destinations.CORE_DESTINATIONS.includes(
      shellState.route?.destination,
    ) ? shellState.route.destination : "play";
    const segment = shellState.route?.segments?.[0] || "";
    const copy = modules.destinations.destinationCopy(destination, segment, t);
    parent.textContent = copy.parent;
    heading.textContent = copy.label;
    heading.dataset.focusIdentity = `destination:${destination}`;
    context.textContent = copy.context;
    for (const link of links) {
      if (link.dataset.coreDestination === destination) {
        link.setAttribute("aria-current", "page");
      } else {
        link.removeAttribute("aria-current");
      }
    }
    const destinationView = modules.destinations.renderDestination({
      document: documentRef,
      destination,
      state: services.store.getSnapshot(),
      t,
    });
    if (shellState.route?.explanation) {
      const notice = documentRef.createElement("div");
      notice.className = "ui-notice ui-shell__route-notice";
      notice.dataset.tone = "warning";
      notice.dataset.marker = "!";
      notice.setAttribute("role", "status");
      const message = documentRef.createElement("p");
      message.textContent = shellState.route.explanation;
      notice.append(message);
      view.replaceChildren(notice, destinationView);
    } else {
      view.replaceChildren(destinationView);
    }
    extensionHost?.decorate({ route: shellState.route, view });
    services.localizer.localize(view);
    inspectorHost?.sync(shellState.route);
    goTo?.sync(shellState.route);
    if (renderedDestination !== destination) {
      renderedDestination = destination;
      target.requestAnimationFrame(() => heading.focus({ preventScroll: true }));
    }
  };

  inspectorHost = modules.inspectorHost.createInspectorHost({
    services,
    document: documentRef,
    root,
  });
  const shortcutRegistry = modules.shortcuts.createShortcutRegistry({
    target,
    onCollision: entry => services.diagnostics.record({ kind: "shortcut-collision", ...entry }),
  });
  shortcutRegistry.start();
  extensionHost = modules.extensionHost.createExtensionHost({
    services,
    modules,
    shortcutRegistry,
    document: documentRef,
    onChange: () => render(selectShellState(services.store.getSnapshot())),
  });
  goTo = modules.goTo.createGoTo({
    services,
    modules,
    shortcutRegistry,
    document: documentRef,
    resultProviders: [extensionHost.goToResults],
  });
  const unregisterSettings = shortcutRegistry.register({
    owner: "core-shell",
    id: "open-settings",
    combo: "mod+,",
    label: services.localizer.t(SHELL_COPY.openSettings),
    handler: () => services.router.navigate({ destination: "settings" }),
    core: true,
  });
  const unregisterEscape = shortcutRegistry.register({
    owner: "core-shell",
    id: "close-layer",
    combo: "escape",
    label: services.localizer.t(SHELL_COPY.closeLayer),
    handler: () => services.router.closeTopLayer(),
    allowWhenTyping: true,
    core: true,
  });
  applyLayout();
  target.addEventListener("resize", applyLayout);
  const selectShellState = state => ({
    route: state.route,
    story: state.story,
    library: state.library,
    settings: state.settings,
    extensions: state.extensions,
  });
  const unsubscribe = services.store.subscribe(selectShellState, render, {
    equality: sameShellState,
  });
  render(selectShellState(services.store.getSnapshot()));

  const teardown = () => {
    if (stopped) return;
    stopped = true;
    unsubscribe();
    target.removeEventListener("resize", applyLayout);
    unregisterEscape();
    unregisterSettings();
    goTo.teardown();
    extensionHost.teardown();
    shortcutRegistry.stop();
    inspectorHost.teardown();
    view.replaceChildren();
  };

  return Object.freeze({
    teardown,
    layoutState: () => root.dataset.layoutState,
    shortcuts: shortcutRegistry,
    goTo,
    extensionHost,
  });
}
