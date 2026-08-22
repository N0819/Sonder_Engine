export const MODULE_RELEASE = "wp06.1";

const TYPE_BY_SEGMENT = Object.freeze({
  "": "",
  stories: "story",
  characters: "character",
  personas: "persona",
  lore: "lore",
});
const SEGMENT_BY_TYPE = Object.freeze({
  story: "stories",
  character: "characters",
  persona: "personas",
  lore: "lore",
});
const SCOPES = new Set(["all", "story", "unassigned", "multiple"]);
const SORTS = new Set(["name", "type", "created", "usage"]);
const VISIBILITIES = new Set(["active", "archived"]);
const ITEM_ID = /^(story|character|persona|lore):([1-9][0-9]*)$/;
const MAX_FAVORITES = 20;
const MAX_RECENTS = 50;
const MAX_SCROLLS = 20;

function numericId(value) {
  const number = Number(value);
  return Number.isSafeInteger(number) && number > 0 ? number : null;
}

function boundedText(value, maximum = 200) {
  return String(value || "").trim().slice(0, maximum);
}

function cleanItemId(value) {
  const candidate = boundedText(value, 80).toLowerCase();
  return ITEM_ID.test(candidate) ? candidate : "";
}

export function normalizeLibraryRoute(route) {
  const segment = String(route?.segments?.[0] || "").toLowerCase();
  const type = Object.hasOwn(TYPE_BY_SEGMENT, segment) ? TYPE_BY_SEGMENT[segment] : "";
  const raw = route?.query || {};
  const scope = SCOPES.has(raw.scope) ? raw.scope : "all";
  const story = numericId(raw.story);
  const sort = SORTS.has(raw.sort) ? raw.sort : "name";
  const visibility = VISIBILITIES.has(raw.visibility) ? raw.visibility : "active";
  const item = cleanItemId(raw.item);
  const q = boundedText(raw.q, 200);
  const reasons = [];
  if (raw.scope && raw.scope !== scope) reasons.push("scope");
  if (raw.story && !story) reasons.push("story");
  if (scope === "story" && !story) reasons.push("story-required");
  if (raw.sort && raw.sort !== sort) reasons.push("sort");
  if (raw.visibility && raw.visibility !== visibility) reasons.push("visibility");
  if (raw.item && !item) reasons.push("item");
  const effectiveScope = scope === "story" && !story ? "all" : scope;
  const query = {};
  if (effectiveScope !== "all") query.scope = effectiveScope;
  if (story) query.story = String(story);
  if (item) query.item = item;
  if (q) query.q = q;
  if (sort !== "name") query.sort = sort;
  if (visibility !== "active") query.visibility = visibility;
  return Object.freeze({
    type,
    segment: SEGMENT_BY_TYPE[type] || "",
    scope: effectiveScope,
    story,
    item,
    q,
    sort,
    visibility,
    query: Object.freeze(query),
    invalid: reasons.length > 0,
    reason: reasons.join(","),
  });
}

function requestPath(route) {
  const params = new URLSearchParams({
    scope: route.scope,
    sort: route.sort,
    visibility: route.visibility,
    offset: "0",
    limit: "100",
  });
  if (route.story) params.set("story_id", String(route.story));
  if (route.type) params.set("types", route.type);
  if (route.q) params.set("q", route.q);
  return "/api/library?" + params.toString();
}

function presentationRecord(localState) {
  const record = localState.snapshot().panes?.library;
  const safe = record && typeof record === "object" ? record : {};
  const identities = (value, maximum) => Array.isArray(value)
    ? value.map(cleanItemId).filter(Boolean).slice(0, maximum) : [];
  const scrolls = {};
  for (const [key, value] of Object.entries(safe.scrolls || {}).slice(-MAX_SCROLLS)) {
    if (typeof key !== "string" || key.length > 512) continue;
    const number = Number(value);
    if (Number.isFinite(number) && number >= 0) scrolls[key] = Math.round(number);
  }
  return {
    favorites: identities(safe.favorites, MAX_FAVORITES),
    recents: identities(safe.recents, MAX_RECENTS),
    lastRoute: boundedText(safe.lastRoute, 768),
    scrolls,
  };
}

function savePresentation(localState, record) {
  const panes = localState.snapshot().panes || {};
  localState.setRecord("panes", { ...panes, library: record });
}

function sameQuery(left, right) {
  return left?.destination === "library" && right?.destination === "library"
    && left.canonicalHash === right.canonicalHash;
}

function statusForError(error) {
  return ["network", "offline", "timeout"].includes(error?.kind) ? "offline" : "error";
}

export function createLibraryRuntime(options = {}) {
  const { store, apiClient, localState, router } = options;
  if (!store || !apiClient || !localState || !router) {
    throw new Error("The Library runtime requires store, API, local state, and routing.");
  }
  let stopped = false;
  let generation = 0;
  let owner = "";
  let currentRoute = null;
  let safeLinkNotice = false;
  let presentation = presentationRecord(localState);

  const replace = value => store.dispatch({
    type: "server/replace",
    slice: "library",
    value,
  });

  const legacy = () => {
    const library = store.getSnapshot().library || {};
    return {
      chats: library.chats || [],
      characters: library.characters || [],
      personas: library.personas || [],
      lorebooks: library.lorebooks || [],
    };
  };

  const refresh = async route => {
    const normalized = normalizeLibraryRoute(route);
    currentRoute = normalized;
    generation += 1;
    const requestGeneration = generation;
    owner = route.canonicalHash;
    const requestOwner = owner;
    const previous = store.getSnapshot().library || {};
    const confirmedItems = Array.isArray(previous.items) ? previous.items : [];
    const confirmedSelection = normalized.item
      ? confirmedItems.find(item => item?.key === normalized.item) || null : null;
    replace({
      ...legacy(),
      ...previous,
      status: previous.items?.length ? "refreshing" : "loading",
      owner: requestOwner,
      route: normalized,
      selected: confirmedSelection,
      unavailableItem: false,
      notice: normalized.invalid || safeLinkNotice
        ? "Some Library link options were invalid and were safely ignored." : "",
      error: null,
    });
    try {
      const result = await apiClient.get(requestPath(normalized), {
        channel: "library-projection",
        owner: requestOwner,
        isCurrent: identity => !stopped
          && identity.owner === owner
          && requestGeneration === generation,
      });
      if (stopped || requestOwner !== owner || requestGeneration !== generation) return;
      const payload = result.data;
      if (!payload || !Array.isArray(payload.items) || !payload.page || !payload.facets) {
        throw new Error("The Library projection response was incomplete.");
      }
      const selected = normalized.item
        ? payload.items.find(item => item?.key === normalized.item) || null : null;
      replace({
        ...legacy(),
        status: payload.items.length ? "ready" : "empty",
        owner: requestOwner,
        route: normalized,
        items: payload.items.slice(0, 100),
        facets: payload.facets,
        page: payload.page,
        query: payload.query,
        selected,
        unavailableItem: Boolean(normalized.item && !selected),
        notice: normalized.invalid || safeLinkNotice
          ? "Some Library link options were invalid and were safely ignored." : "",
        error: null,
      });
      presentation = { ...presentation, lastRoute: route.canonicalHash };
      savePresentation(localState, presentation);
      safeLinkNotice = false;
    } catch (error) {
      if (stopped || requestOwner !== owner || requestGeneration !== generation
          || ["aborted", "stale"].includes(error?.kind)) return;
      replace({
        ...legacy(),
        ...previous,
        status: statusForError(error),
        owner: requestOwner,
        route: normalized,
        items: confirmedItems,
        selected: confirmedSelection,
        unavailableItem: false,
        error: {
          kind: error?.kind || "unavailable",
          message: "Library information is temporarily unavailable.",
        },
      });
    }
  };

  const onRoute = route => {
    if (route?.destination !== "library") return;
    const normalized = normalizeLibraryRoute(route);
    if (normalized.invalid) {
      safeLinkNotice = true;
      router.navigate({
        destination: "library",
        segments: normalized.segment ? [normalized.segment] : [],
        query: normalized.query,
      }, { replace: true });
      return;
    }
    if (sameQuery(route, { destination: "library", canonicalHash: owner })) return;
    refresh(route);
  };
  const unsubscribe = store.subscribe(state => state.route, onRoute);
  onRoute(store.getSnapshot().route);

  const navigate = changes => {
    const route = router.current();
    const normalized = normalizeLibraryRoute(route);
    const type = changes.type === undefined ? normalized.type : changes.type;
    const query = { ...normalized.query, ...changes.query };
    for (const [key, value] of Object.entries(query)) {
      if (value === "" || value === null || value === undefined) delete query[key];
    }
    return router.navigate({
      destination: "library",
      segments: type && SEGMENT_BY_TYPE[type] ? [SEGMENT_BY_TYPE[type]] : [],
      query,
    }, changes.replace ? { replace: true } : {});
  };

  const recordRecent = itemId => {
    const id = cleanItemId(itemId);
    if (!id) return;
    presentation = {
      ...presentation,
      recents: [id, ...presentation.recents.filter(value => value !== id)].slice(0, MAX_RECENTS),
    };
    savePresentation(localState, presentation);
  };

  const toggleFavorite = itemId => {
    const id = cleanItemId(itemId);
    if (!id) return false;
    const exists = presentation.favorites.includes(id);
    presentation = {
      ...presentation,
      favorites: exists
        ? presentation.favorites.filter(value => value !== id)
        : [id, ...presentation.favorites].slice(0, MAX_FAVORITES),
    };
    savePresentation(localState, presentation);
    return !exists;
  };

  const saveScroll = (routeIdentity, position) => {
    const key = boundedText(routeIdentity, 512);
    const value = Math.max(0, Math.round(Number(position) || 0));
    const entries = Object.entries({ ...presentation.scrolls, [key]: value }).slice(-MAX_SCROLLS);
    presentation = { ...presentation, scrolls: Object.fromEntries(entries) };
    savePresentation(localState, presentation);
  };

  const teardown = () => {
    if (stopped) return;
    stopped = true;
    generation += 1;
    apiClient.cancel("library-projection", "runtime-stop");
    unsubscribe();
  };

  return Object.freeze({
    refresh: () => refresh(router.current()),
    navigate,
    recordRecent,
    toggleFavorite,
    isFavorite: itemId => presentation.favorites.includes(cleanItemId(itemId)),
    scrollFor: routeIdentity => presentation.scrolls[routeIdentity] || 0,
    saveScroll,
    currentRoute: () => currentRoute,
    teardown,
  });
}
