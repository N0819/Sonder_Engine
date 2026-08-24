export const MODULE_RELEASE = "alpha98-ui8-eb87a8415bda";

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

function isPersonAuthoringRoute(route) {
  if (route?.destination !== "library") return false;
  if (!["edit", "create", "import", "story-card"].includes(route.query?.mode)) {
    return false;
  }
  const segment = route.segments?.[0];
  const item = String(route.query?.item || "");
  return ["characters", "personas"].includes(segment)
    || /^(character|persona):[1-9][0-9]*$/.test(item);
}

function sameShellState(left, right) {
  if (left.route !== right.route || left.extensions !== right.extensions
      || left.notices !== right.notices) return false;
  const destination = left.route?.destination || "play";
  if (destination === "library") {
    if (isPersonAuthoringRoute(left.route)) {
      return left.library?.authoring?.owner === right.library?.authoring?.owner;
    }
    return left.library === right.library;
  }
  if (destination === "settings") return left.settings === right.settings;
  return left.story?.status === right.story?.status
    && left.story?.owner === right.story?.owner;
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
      || !modules?.shortcuts || !modules?.goTo || !modules?.extensionHost
      || !modules?.playView || !modules?.prose || !modules?.storyToolsRegistry
      || !modules?.storyToolsView || !modules?.libraryView
      || !modules?.libraryAuthoringView || !modules?.settingsView) {
    throw new Error("The application shell presentation modules are missing.");
  }

  const heading = required(documentRef, "[data-shell-heading]");
  const parent = required(documentRef, "[data-shell-parent]");
  const context = required(documentRef, "[data-shell-context]");
  const view = required(documentRef, "[data-shell-destination-view]");
  const noticeHost = required(documentRef, "[data-shell-notice-host]");
  const links = [...documentRef.querySelectorAll("[data-core-destination]")];
  const t = services.localizer.t;
  let stopped = false;
  let renderedDestination = null;
  let inspectorHost = null;
  let goTo = null;
  let extensionHost = null;
  let destinationTeardown = null;
  let renderedData = null;
  let renderedRouteIdentity = null;
  let renderedNotices = null;

  const syncNotices = noticeState => {
    if (noticeState === renderedNotices) return;
    renderedNotices = noticeState;
    noticeHost.replaceChildren();
    for (const item of noticeState?.items || []) {
      const notice = documentRef.createElement("section");
      notice.className = "ui-notice ui-shell__notice";
      notice.dataset.noticeId = item.id;
      notice.dataset.tone = item.kind === "problem" ? "error" : "success";
      notice.dataset.marker = item.kind === "problem" ? "!" : "✓";
      notice.setAttribute("role", item.kind === "problem" ? "alert" : "status");
      const message = documentRef.createElement("p");
      message.textContent = item.message;
      const dismiss = documentRef.createElement("button");
      dismiss.type = "button";
      dismiss.className = "ui-button ui-button--quiet";
      dismiss.textContent = "Dismiss";
      dismiss.setAttribute("aria-label", `Dismiss notification: ${item.message}`);
      dismiss.addEventListener("click", () => services.notices.dismiss(item.id));
      notice.append(message, dismiss);
      noticeHost.append(notice);
    }
  };

  const applyLayout = () => {
    root.dataset.layoutState = layoutStateFor(target.innerWidth, target.innerHeight);
    inspectorHost?.setLayout(root.dataset.layoutState);
  };

  const render = shellState => {
    if (stopped) return;
    syncNotices(shellState.notices);
    const destination = modules.destinations.CORE_DESTINATIONS.includes(
      shellState.route?.destination,
    ) ? shellState.route.destination : "play";
    root.dataset.destination = destination;
    root.dataset.librarySelection = destination === "library" && shellState.route?.query?.item
      ? "true" : "false";
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
    const data = destination === "play"
      ? shellState.story
      : (destination === "library" ? shellState.library : shellState.settings);
    const routeIdentity = destination === "play"
      ? String(shellState.route?.explanation || "")
      : String(shellState.route?.canonicalHash || "");
    if (renderedDestination !== destination || renderedData !== data
        || renderedRouteIdentity !== routeIdentity) {
      const activeIdentity = documentRef.activeElement?.dataset?.focusIdentity || "";
      const destinationMount = modules.destinations.renderDestination({
        document: documentRef,
        destination,
        state: services.store.getSnapshot(),
        t,
        services,
        modules,
      });
      const destinationView = destinationMount?.element || destinationMount;
      destinationTeardown?.();
      destinationTeardown = typeof destinationMount?.teardown === "function"
        ? destinationMount.teardown : null;
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
      if (activeIdentity) {
        const restoredFocus = [...view.querySelectorAll("[data-focus-identity]")]
          .find(element => element.dataset.focusIdentity === activeIdentity);
        if (restoredFocus) {
          target.requestAnimationFrame(() => restoredFocus.focus({ preventScroll: true }));
        }
      }
      renderedData = data;
      renderedRouteIdentity = routeIdentity;
    }
    inspectorHost?.sync(shellState.route);
    goTo?.sync(shellState.route);
    if (renderedDestination !== destination) {
      renderedDestination = destination;
      target.requestAnimationFrame(() => {
        const focusTarget = destination === "library"
          ? view.querySelector('[data-focus-identity="destination:library"]')
          : heading;
        focusTarget?.focus({ preventScroll: true });
      });
    }
  };

  inspectorHost = modules.inspectorHost.createInspectorHost({
    services,
    modules,
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
    notices: state.notices,
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
    destinationTeardown?.();
    destinationTeardown = null;
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
