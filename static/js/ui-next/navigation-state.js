export const MODULE_RELEASE = "alpha98-ui10-0415f377b12f";

const MAX_SCROLL_REGIONS = 80;
const MAX_SCROLL_OFFSET = 10_000_000;

function finiteOffset(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return 0;
  return Math.max(0, Math.min(MAX_SCROLL_OFFSET, Math.round(number)));
}

function safeNavigation(value) {
  const navigation = value && typeof value === "object" ? value : {};
  const scrollRegions = {};
  for (const [key, offset] of Object.entries(navigation.scrollRegions || {}).slice(
    -MAX_SCROLL_REGIONS,
  )) {
    if (/^#[A-Za-z0-9/?=&%._:-]{1,1000}::[A-Za-z0-9:_-]{1,80}$/.test(key)) {
      scrollRegions[key] = finiteOffset(offset);
    }
  }
  return {
    route: typeof navigation.route === "string" ? navigation.route.slice(0, 1024) : "",
    scrollRegions,
    focusIdentity: typeof navigation.focusIdentity === "string"
      ? navigation.focusIdentity.slice(0, 120)
      : "",
  };
}

export function createNavigationState(options = {}) {
  const { localState } = options;
  const target = options.target || window;
  const documentRef = options.document || document;
  if (!localState?.snapshot || !localState?.setRecord) {
    throw new TypeError("Navigation state requires versioned local state.");
  }

  let navigation = safeNavigation(localState.snapshot().navigation);
  let currentHash = "";
  let stopped = false;

  const regions = () => [...documentRef.querySelectorAll("[data-shell-scroll-region]")];
  const regionKey = (hash, node) => `${hash}::${node.dataset.shellScrollRegion}`;
  const persist = () => localState.setRecord("navigation", navigation);

  const captureScroll = () => {
    if (!currentHash) return;
    const scrollRegions = { ...navigation.scrollRegions };
    for (const node of regions()) {
      scrollRegions[regionKey(currentHash, node)] = finiteOffset(node.scrollTop);
    }
    const entries = Object.entries(scrollRegions).slice(-MAX_SCROLL_REGIONS);
    navigation = { ...navigation, scrollRegions: Object.fromEntries(entries) };
  };

  const restoreScroll = hash => {
    target.requestAnimationFrame(() => {
      if (stopped || currentHash !== hash) return;
      for (const node of regions()) {
        node.scrollTop = navigation.scrollRegions[regionKey(hash, node)] || 0;
      }
    });
  };

  const initialHash = parseRoute => {
    const requested = String(target.location.hash || "");
    if (requested) return requested;
    const restored = parseRoute(navigation.route);
    return restored.valid ? restored.canonicalHash : "#/play";
  };

  const prepareInitialRoute = parseRoute => {
    const hash = initialHash(parseRoute);
    if (!target.location.hash) {
      target.history.replaceState({ sonderUi: { hash, layers: [] } }, "", hash);
    }
    return hash;
  };

  const onRoute = route => {
    captureScroll();
    currentHash = route.canonicalHash;
    const keepOverviewFocus = route.destination === "settings"
      && navigation.focusIdentity.startsWith("settings-overview:");
    navigation = {
      ...navigation,
      route: route.valid ? route.canonicalHash : `#/${route.destination}`,
      focusIdentity: keepOverviewFocus
        ? navigation.focusIdentity
        : `destination:${route.destination}`,
    };
    persist();
    restoreScroll(currentHash);
  };

  const restoreFocus = focusIdentity => {
    const identity = String(focusIdentity || "");
    const match = [...documentRef.querySelectorAll("[data-focus-identity]")].find(
      node => node.dataset.focusIdentity === identity,
    );
    match?.focus({ preventScroll: true });
    navigation = { ...navigation, focusIdentity: identity };
    persist();
    return Boolean(match);
  };

  const rememberFocus = focusIdentity => {
    const identity = String(focusIdentity || "").slice(0, 120);
    navigation = { ...navigation, focusIdentity: identity };
    persist();
  };

  const teardown = () => {
    if (stopped) return;
    captureScroll();
    persist();
    stopped = true;
  };

  return Object.freeze({
    prepareInitialRoute,
    onRoute,
    rememberFocus,
    restoreFocus,
    captureScroll,
    teardown,
    snapshot: () => Object.freeze({ ...navigation }),
  });
}
