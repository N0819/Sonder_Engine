export const MODULE_RELEASE = "alpha98-ui15-5b0f039aae29";

export const SLICE_OWNERS = Object.freeze({
  server: Object.freeze([
    "session",
    "story",
    "transcript",
    "library",
    "settings",
    "extensions",
  ]),
  presentation: Object.freeze([
    "route",
    "composer",
    "inspector",
    "tasks",
    "notices",
    "appearance",
    "atmosphere",
    "diagnostics",
  ]),
});

const DEFAULT_STATE = Object.freeze({
  session: { status: "unrequested", account: null },
  route: {
    status: "ready",
    destination: "play",
    segments: [],
    query: {},
    layers: [],
    explanation: "",
  },
  story: { status: "unrequested", data: null },
  transcript: { status: "unrequested", items: [] },
  composer: { status: "ready", owner: null, draft: "" },
  inspector: { status: "ready", owner: null, panel: null },
  library: { status: "unrequested", items: [] },
  settings: { status: "unrequested", data: null },
  tasks: { status: "ready", items: [] },
  notices: { status: "ready", items: [] },
  appearance: {
    status: "ready",
    theme: "carbon-signal",
    density: "comfortable",
    motion: "system",
  },
  atmosphere: {
    status: "unrequested",
    owner: null,
    backdrop: { status: "unrequested", turnId: null, payload: null },
    ambience: { status: "unrequested", turnId: null, payload: null },
    preferences: { muted: false, volume: 0.7, chime: false },
    audio: { unlocked: false, playing: false, token: null },
    mediaError: null,
  },
  extensions: { status: "unrequested", items: [] },
  diagnostics: { status: "ready", enabled: false, entries: [] },
});

const KNOWN_SLICES = new Set(Object.keys(DEFAULT_STATE));
const OWNER_BY_SLICE = new Map([
  ...SLICE_OWNERS.server.map(name => [name, "server"]),
  ...SLICE_OWNERS.presentation.map(name => [name, "presentation"]),
]);

class StoreError extends Error {
  constructor(kind, message) {
    super(message);
    this.name = "StoreError";
    this.kind = kind;
  }
}

function clone(value) {
  return globalThis.structuredClone
    ? globalThis.structuredClone(value)
    : JSON.parse(JSON.stringify(value));
}

function deepFreeze(value, seen = new WeakSet()) {
  if (!value || typeof value !== "object" || seen.has(value)) return value;
  seen.add(value);
  for (const child of Object.values(value)) deepFreeze(child, seen);
  return Object.freeze(value);
}

function immutableCopy(value) {
  return deepFreeze(clone(value));
}

function initialState(overrides) {
  for (const slice of Object.keys(overrides || {})) {
    if (!KNOWN_SLICES.has(slice)) {
      throw new StoreError("unknown-slice", `Unknown state slice: ${slice}`);
    }
  }
  const state = {};
  for (const [slice, fallback] of Object.entries(DEFAULT_STATE)) {
    state[slice] = immutableCopy(
      Object.hasOwn(overrides || {}, slice) ? overrides[slice] : fallback,
    );
  }
  return deepFreeze(state);
}

function validateAction(action) {
  if (!action || typeof action !== "object") {
    throw new StoreError("unknown-action", "State actions must be named objects.");
  }
  const match = /^(server|presentation)\/(replace|patch)$/.exec(action.type || "");
  if (!match) {
    throw new StoreError("unknown-action", `Unknown state action: ${action.type || ""}`);
  }
  if (!KNOWN_SLICES.has(action.slice)) {
    throw new StoreError("unknown-slice", `Unknown state slice: ${action.slice || ""}`);
  }
  if (OWNER_BY_SLICE.get(action.slice) !== match[1]) {
    throw new StoreError(
      "slice-owner",
      `${action.slice} is not owned by ${match[1]} state.`,
    );
  }
  return { owner: match[1], operation: match[2] };
}

export function createStore(overrides = {}) {
  let state = initialState(overrides);
  let destroyed = false;
  let batchDepth = 0;
  let pendingPrevious = null;
  let pendingActions = [];
  const subscribers = new Set();

  const requireActive = () => {
    if (destroyed) {
      throw new StoreError("store-destroyed", "The state store has been destroyed.");
    }
  };

  const notify = () => {
    if (!pendingPrevious || !pendingActions.length) return;
    const previousState = pendingPrevious;
    const actions = Object.freeze([...pendingActions]);
    pendingPrevious = null;
    pendingActions = [];
    for (const subscriber of [...subscribers]) {
      if (!subscribers.has(subscriber)) continue;
      const nextSelected = subscriber.selector(state);
      if (subscriber.equality(nextSelected, subscriber.selected)) continue;
      const previousSelected = subscriber.selected;
      subscriber.selected = nextSelected;
      subscriber.listener(nextSelected, previousSelected, actions);
    }
  };

  const dispatch = (action) => {
    requireActive();
    const { operation } = validateAction(action);
    const previous = state;
    const currentSlice = state[action.slice];
    let nextSlice;
    if (operation === "patch") {
      if (!action.value || typeof action.value !== "object"
          || Array.isArray(action.value)) {
        throw new StoreError("invalid-value", "Patch state must be an object.");
      }
      nextSlice = { ...currentSlice, ...clone(action.value) };
    } else {
      nextSlice = clone(action.value);
    }
    state = deepFreeze({ ...state, [action.slice]: deepFreeze(nextSlice) });
    if (!pendingPrevious) pendingPrevious = previous;
    pendingActions.push(action.type);
    if (batchDepth === 0) notify();
    return state;
  };

  const subscribe = (selector, listener, subscribeOptions = {}) => {
    requireActive();
    if (typeof selector !== "function" || typeof listener !== "function") {
      throw new StoreError("invalid-subscriber", "A selector and listener are required.");
    }
    const subscriber = {
      selector,
      listener,
      equality: subscribeOptions.equality || Object.is,
      selected: selector(state),
    };
    subscribers.add(subscriber);
    let subscribed = true;
    return () => {
      if (!subscribed) return;
      subscribed = false;
      subscribers.delete(subscriber);
    };
  };

  const batch = (callback) => {
    requireActive();
    batchDepth += 1;
    try {
      return callback();
    } finally {
      batchDepth -= 1;
      if (batchDepth === 0) notify();
    }
  };

  const destroy = () => {
    if (destroyed) return;
    destroyed = true;
    subscribers.clear();
    pendingPrevious = null;
    pendingActions = [];
  };

  return Object.freeze({
    getSnapshot: () => state,
    select: selector => selector(state),
    dispatch,
    subscribe,
    batch,
    destroy,
  });
}
