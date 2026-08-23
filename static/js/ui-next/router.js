export const MODULE_RELEASE = "alpha98-ui1";

const ROUTES = Object.freeze({
  play: Object.freeze(["story-tools"]),
  library: Object.freeze([
    "stories",
    "characters",
    "personas",
    "lore",
  ]),
  settings: Object.freeze([
    "experience",
    "ai-connections",
    "content",
    "add-ons",
    "maintenance",
    "appearance",
    "language",
    "providers",
    "models",
    "extensions",
    "advanced",
  ]),
});

const BLOCKED_QUERY_KEYS = new Set([
  "__proto__",
  "prototype",
  "constructor",
]);
const QUERY_KEY = /^[a-z][a-z0-9_-]{0,39}$/;
const SEGMENT = /^[a-z][a-z0-9_-]{0,63}$/;
const LAYER_ID = /^[A-Za-z0-9:_-]{1,80}$/;

// UI_CATALOG_START: invalid-link explanations shown beside the safe fallback.
const DEFAULT_EXPLANATIONS = Object.freeze({
  "unknown-destination": "That area does not exist. Play was opened instead.",
  "unknown-segment": "That page does not exist. Its parent area was opened instead.",
  "malformed-route": "That link could not be read. Its nearest safe area was opened.",
  "unsafe-query": "That link contained an unsafe option. It was not opened.",
  "query-too-long": "That link contained too much information. It was not opened.",
});
// UI_CATALOG_END

export class RouteError extends Error {
  constructor(kind, message) {
    super(message);
    this.name = "RouteError";
    this.kind = kind;
  }
}

function explanation(reason, explain) {
  if (!reason) return "";
  const key = `route.${reason}`;
  const localized = explain?.(key);
  return localized && localized !== key ? localized : DEFAULT_EXPLANATIONS[reason];
}

function safeDestination(raw) {
  try {
    const candidate = decodeURIComponent(raw || "").toLowerCase();
    return Object.hasOwn(ROUTES, candidate) ? candidate : "play";
  } catch {
    return "play";
  }
}

function routeResult({
  valid,
  destination,
  segments = [],
  query = {},
  reason = "",
  explain,
}) {
  const canonicalHash = canonical(destination, segments, query);
  return Object.freeze({
    valid,
    destination,
    segments: Object.freeze([...segments]),
    query: Object.freeze({ ...query }),
    canonicalHash,
    explanation: explanation(reason, explain),
    reason,
    layers: Object.freeze([]),
  });
}

function fallback(destination, reason, explain) {
  return routeResult({ valid: false, destination, reason, explain });
}

function parseQuery(rawQuery, destination, explain) {
  if (!rawQuery) return { query: {} };
  if (rawQuery.length > 768) return { error: fallback(destination, "query-too-long", explain) };
  const params = new URLSearchParams(rawQuery);
  if ([...params].length > 12) {
    return { error: fallback(destination, "query-too-long", explain) };
  }
  const query = {};
  for (const [rawKey, value] of params) {
    const key = rawKey.toLowerCase();
    if (BLOCKED_QUERY_KEYS.has(key) || !QUERY_KEY.test(key) || Object.hasOwn(query, key)) {
      return { error: fallback(destination, "unsafe-query", explain) };
    }
    if (value.length > 200) {
      return { error: fallback(destination, "query-too-long", explain) };
    }
    query[key] = value;
  }
  return { query };
}

function canonical(destination, segments, query) {
  const path = [destination, ...segments].map(encodeURIComponent).join("/");
  const params = new URLSearchParams();
  for (const key of Object.keys(query || {}).sort()) {
    params.set(key, String(query[key]));
  }
  const suffix = params.toString();
  return `#/${path}${suffix ? `?${suffix}` : ""}`;
}

export function parseHashRoute(hash, options = {}) {
  const source = String(hash || "#/play");
  if (source.length > 1024 || !source.startsWith("#/")) {
    return fallback("play", source.length > 1024 ? "query-too-long" : "malformed-route", options.explain);
  }
  const routeBody = source.slice(2);
  const queryAt = routeBody.indexOf("?");
  const rawPath = queryAt === -1 ? routeBody : routeBody.slice(0, queryAt);
  const rawQuery = queryAt === -1 ? "" : routeBody.slice(queryAt + 1);
  const rawSegments = rawPath.split("/").filter(Boolean);
  const destination = safeDestination(rawSegments[0]);
  let decoded;
  try {
    decoded = rawSegments.map(value => decodeURIComponent(value).toLowerCase());
  } catch {
    return fallback(destination, "malformed-route", options.explain);
  }
  if (!Object.hasOwn(ROUTES, decoded[0])) {
    return fallback("play", "unknown-destination", options.explain);
  }
  const segments = decoded.slice(1);
  if (segments.length > 1 || segments.some(segment => !SEGMENT.test(segment))) {
    return fallback(destination, "malformed-route", options.explain);
  }
  if (segments.length && !ROUTES[destination].includes(segments[0])) {
    return fallback(destination, "unknown-segment", options.explain);
  }
  const parsedQuery = parseQuery(rawQuery, destination, options.explain);
  if (parsedQuery.error) return parsedQuery.error;
  return routeResult({
    valid: true,
    destination,
    segments,
    query: parsedQuery.query,
    explain: options.explain,
  });
}

export function serializeRoute(route) {
  const hash = canonical(
    String(route?.destination || ""),
    Array.isArray(route?.segments) ? route.segments : [],
    route?.query || {},
  );
  const parsed = parseHashRoute(hash);
  if (!parsed.valid) throw new RouteError(parsed.reason, parsed.explanation);
  return parsed.canonicalHash;
}

function safeLayers(state, hash) {
  const candidate = state?.sonderUi;
  if (candidate?.hash !== hash || !Array.isArray(candidate.layers)) return [];
  const layers = [];
  for (const layer of candidate.layers.slice(0, 8)) {
    if (!LAYER_ID.test(String(layer?.id || ""))) continue;
    const focusReturn = String(layer?.focusReturn || "").slice(0, 120);
    layers.push(Object.freeze({ id: String(layer.id), focusReturn }));
  }
  return layers;
}

function withLayers(route, layers) {
  return Object.freeze({ ...route, layers: Object.freeze([...layers]) });
}

export function createRouter(options = {}) {
  const target = options.target || window;
  const history = target.history;
  const location = target.location;
  let started = false;
  let route = withLayers(
    parseHashRoute(location.hash, { explain: options.explain }),
    safeLayers(history.state, location.hash),
  );
  let signature = "";

  const emit = () => {
    const nextSignature = JSON.stringify([
      route.canonicalHash,
      route.valid,
      route.reason,
      route.layers.map(layer => [layer.id, layer.focusReturn]),
    ]);
    if (nextSignature === signature) return;
    signature = nextSignature;
    options.onRoute?.(route);
  };

  const readLocation = () => {
    const previousLayers = route.layers;
    const parsed = parseHashRoute(location.hash, { explain: options.explain });
    const layers = safeLayers(history.state, location.hash);
    route = withLayers(parsed, layers);
    for (const closed of previousLayers.slice(layers.length).reverse()) {
      if (closed.focusReturn) options.onFocusReturn?.(closed.focusReturn);
    }
    emit();
  };

  const start = () => {
    if (started) return;
    started = true;
    target.addEventListener("hashchange", readLocation);
    target.addEventListener("popstate", readLocation);
    emit();
  };

  const stop = () => {
    if (!started) return;
    started = false;
    target.removeEventListener("hashchange", readLocation);
    target.removeEventListener("popstate", readLocation);
  };

  const navigate = (next, navigationOptions = {}) => {
    const hash = typeof next === "string" ? next : serializeRoute(next);
    const parsed = parseHashRoute(hash, { explain: options.explain });
    const method = navigationOptions.replace ? "replaceState" : "pushState";
    const layers = navigationOptions.preserveLayers ? route.layers : [];
    history[method]({ sonderUi: { hash: parsed.canonicalHash, layers } }, "", parsed.canonicalHash);
    route = withLayers(parsed, layers);
    emit();
    return route;
  };

  const openLayer = (layer) => {
    const id = String(layer?.id || "");
    const focusReturn = String(layer?.focusReturn || "");
    if (!LAYER_ID.test(id) || focusReturn.length > 120) {
      throw new RouteError("invalid-layer", "Transient layer identity is invalid.");
    }
    const layers = [...route.layers, Object.freeze({ id, focusReturn })];
    if (layers.length > 8) {
      throw new RouteError("too-many-layers", "Too many transient layers are open.");
    }
    history.pushState({
      sonderUi: { hash: route.canonicalHash, layers },
    }, "", route.canonicalHash);
    route = withLayers(route, layers);
    emit();
    return route;
  };

  const closeTopLayer = () => {
    if (!route.layers.length) return false;
    history.back();
    return true;
  };

  return Object.freeze({
    start,
    stop,
    navigate,
    openLayer,
    closeTopLayer,
    current: () => route,
  });
}
