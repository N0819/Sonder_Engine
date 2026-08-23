export const MODULE_RELEASE = "alpha98-ui4-842dd802b09f";

import { generateLivedLocation } from "./lived-location.js?release=alpha98-ui4-842dd802b09f";

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
const SORTS = new Set(["name", "type", "created", "usage", "recent"]);
const VISIBILITIES = new Set(["active", "archived"]);
const MODES = new Set(["view", "edit", "create", "import"]);
const ITEM_ID = /^(story|character|persona|lore):([1-9][0-9]*)$/;
const MAX_FAVORITES = 20;
const MAX_RECENTS = 50;
const MAX_SCROLLS = 20;
const UNDO_LIFETIME_MS = 12_000;

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
  const mode = MODES.has(raw.mode) ? raw.mode : "view";
  const q = boundedText(raw.q, 200);
  const reasons = [];
  if (raw.scope && raw.scope !== scope) reasons.push("scope");
  if (raw.story && !story) reasons.push("story");
  if (scope === "story" && !story) reasons.push("story-required");
  if (raw.sort && raw.sort !== sort) reasons.push("sort");
  if (raw.visibility && raw.visibility !== visibility) reasons.push("visibility");
  if (raw.item && !item) reasons.push("item");
  if (raw.mode && raw.mode !== mode) reasons.push("mode");
  if (mode === "edit" && !item) reasons.push("edit-item-required");
  const effectiveScope = scope === "story" && !story ? "all" : scope;
  const query = {};
  if (effectiveScope !== "all") query.scope = effectiveScope;
  if (story) query.story = String(story);
  if (item) query.item = item;
  if (mode !== "view" && !(mode === "edit" && !item)) query.mode = mode;
  if (q) query.q = q;
  if (sort !== "name") query.sort = sort;
  if (visibility !== "active") query.visibility = visibility;
  return Object.freeze({
    type,
    segment: SEGMENT_BY_TYPE[type] || "",
    scope: effectiveScope,
    story,
    item,
    mode: mode === "edit" && !item ? "view" : mode,
    q,
    sort,
    visibility,
    query: Object.freeze(query),
    invalid: reasons.length > 0,
    reason: reasons.join(","),
  });
}

export function libraryScrollIdentity(route) {
  const normalized = normalizeLibraryRoute(route);
  const query = { ...normalized.query };
  delete query.mode;
  const params = new URLSearchParams(query).toString();
  return `#/library${normalized.segment ? `/${normalized.segment}` : ""}${params ? `?${params}` : ""}`;
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
  let returnFocusIdentity = "";
  let mutationGeneration = 0;
  let undoReceipt = null;
  let undoTimer = null;

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

  const publicUndo = () => undoReceipt ? Object.freeze({
    owner: undoReceipt.owner,
    action: undoReceipt.action,
    expiresAt: undoReceipt.expiresAt,
    message: undoReceipt.message,
  }) : null;

  const patchLibrary = value => store.dispatch({
    type: "server/patch",
    slice: "library",
    value,
  });

  const clearUndo = () => {
    if (undoTimer) clearTimeout(undoTimer);
    undoTimer = null;
    undoReceipt = null;
    patchLibrary({ undo: null });
  };

  const holdUndo = receipt => {
    if (undoTimer) clearTimeout(undoTimer);
    undoReceipt = receipt;
    patchLibrary({ undo: publicUndo() });
    undoTimer = setTimeout(() => {
      if (undoReceipt?.owner === receipt.owner
          && undoReceipt?.action === receipt.action) clearUndo();
    }, UNDO_LIFETIME_MS);
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
      undo: publicUndo(),
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
      const latest = store.getSnapshot().library || {};
      const selected = normalized.item
        ? payload.items.find(item => item?.key === normalized.item) || null : null;
      replace({
        ...legacy(),
        ...latest,
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
        undo: publicUndo(),
      });
      presentation = { ...presentation, lastRoute: route.canonicalHash };
      savePresentation(localState, presentation);
      safeLinkNotice = false;
    } catch (error) {
      if (stopped || requestOwner !== owner || requestGeneration !== generation
          || ["aborted", "stale"].includes(error?.kind)) return;
      const latest = store.getSnapshot().library || {};
      replace({
        ...legacy(),
        ...latest,
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
        undo: publicUndo(),
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

  const requestMutation = async spec => {
    const itemKey = cleanItemId(spec.itemKey);
    const storyId = numericId(spec.storyId);
    const action = boundedText(spec.action, 80);
    if (!itemKey || !action || (spec.storyId !== undefined && !storyId)) {
      throw new Error("Library mutation ownership is invalid.");
    }
    mutationGeneration += 1;
    const requestGeneration = mutationGeneration;
    const mutationOwner = `${itemKey}:${storyId || 0}:${action}`;
    const routeOwner = boundedText(router.current()?.canonicalHash, 768);
    const stillOwnsSelection = () => !stopped
      && requestGeneration === mutationGeneration
      && router.current()?.canonicalHash === routeOwner;
    patchLibrary({
      mutation: { status: "saving", owner: mutationOwner, routeOwner },
      error: null,
    });
    try {
      const result = await apiClient.request(spec.method, spec.path, {
        body: spec.body,
        channel: "library-mutation",
        owner: mutationOwner,
        isCurrent: identity => !stopped
          && identity.owner === mutationOwner
          && stillOwnsSelection(),
      });
      if (!stillOwnsSelection()) return false;
      const inverse = typeof spec.inverse === "function"
        ? spec.inverse(result.data) : spec.inverse;
      if (inverse) {
        holdUndo({
          owner: mutationOwner,
          action,
          expiresAt: Date.now() + UNDO_LIFETIME_MS,
          message: spec.undoMessage || "The Library change can be undone briefly.",
          inverse,
        });
      } else {
        clearUndo();
      }
      patchLibrary({
        mutation: { status: "accepted", owner: mutationOwner, routeOwner },
      });
      if (spec.navigateAfter) {
        const normalized = normalizeLibraryRoute(router.current());
        const { item: _selectedItem, ...parentQuery } = normalized.query;
        router.navigate({
          destination: "library",
          segments: normalized.segment ? [normalized.segment] : [],
          query: parentQuery,
        });
      } else {
        await refresh(router.current());
      }
      return true;
    } catch (error) {
      if (stopped || requestGeneration !== mutationGeneration
          || ["aborted", "stale"].includes(error?.kind)) return false;
      patchLibrary({
        mutation: {
          status: "error",
          owner: mutationOwner,
          routeOwner,
          message: error?.userMessage || error?.message || "The Library change was not saved.",
        },
      });
      return false;
    }
  };

  const setAssociation = (item, association) => {
    const storyId = numericId(association?.story_id);
    const itemKey = cleanItemId(item?.key);
    if (!storyId || !itemKey) return Promise.resolve(false);
    if (item.kind === "character") {
      const active = association.state === "active";
      return requestMutation({
        itemKey, storyId,
        action: active ? "cast-remove" : "cast-reactivate",
        method: active ? "DELETE" : "POST",
        path: active
          ? `/api/chats/${storyId}/characters/${item.id}`
          : `/api/chats/${storyId}/characters`,
        body: active ? undefined : { char_id: item.id },
        inverse: active
          ? { method: "POST", path: `/api/chats/${storyId}/characters`, body: { char_id: item.id } }
          : { method: "DELETE", path: `/api/chats/${storyId}/characters/${item.id}` },
        undoMessage: active
          ? "Character removed from the active cast. Their story history remains."
          : "Character restored to the active cast.",
      });
    }
    if (item.kind === "persona") {
      if (association.state === "primary") return Promise.resolve(false);
      const active = association.state === "active";
      return requestMutation({
        itemKey, storyId,
        action: active ? "persona-remove" : "persona-reactivate",
        method: active ? "DELETE" : "POST",
        path: active
          ? `/api/chats/${storyId}/personas/${item.id}`
          : `/api/chats/${storyId}/personas`,
        body: active ? undefined : { persona_id: item.id },
        inverse: active
          ? { method: "POST", path: `/api/chats/${storyId}/personas`, body: { persona_id: item.id } }
          : { method: "DELETE", path: `/api/chats/${storyId}/personas/${item.id}` },
        undoMessage: active ? "Additional player removed from the story." : "Additional player restored.",
      });
    }
    if (item.kind === "lore" && item.reusable
        && ["attached", "disabled", "canon"].includes(association.state)) {
      const canon = association.state === "canon";
      const storyItemId = numericId(association.story_item_id);
      if (!canon && !storyItemId) return Promise.resolve(false);
      return requestMutation({
        itemKey, storyId,
        action: "lore-detach",
        method: "DELETE",
        path: canon
          ? `/api/chats/${storyId}/lorebook`
          : `/api/chats/${storyId}/lorebooks/${storyItemId}`,
        inverse: {
          method: "POST",
          path: canon
            ? `/api/chats/${storyId}/lorebook`
            : `/api/chats/${storyId}/lorebooks`,
          body: { lorebook_id: item.id },
        },
        undoMessage: "Lore detached from the story; the reusable original remains in Library.",
      });
    }
    return Promise.resolve(false);
  };

  const addToStory = (item, storyIdValue) => {
    const storyId = numericId(storyIdValue);
    const itemKey = cleanItemId(item?.key);
    if (!storyId || !itemKey || item.kind === "story") return Promise.resolve(false);
    if (item.kind === "character") {
      return requestMutation({
        itemKey, storyId, action: "cast-add", method: "POST",
        path: `/api/chats/${storyId}/characters`, body: { char_id: item.id },
        inverse: { method: "DELETE", path: `/api/chats/${storyId}/characters/${item.id}` },
        undoMessage: "Character added to the story.",
      });
    }
    if (item.kind === "persona") {
      return requestMutation({
        itemKey, storyId, action: "persona-add", method: "POST",
        path: `/api/chats/${storyId}/personas`, body: { persona_id: item.id },
        inverse: { method: "DELETE", path: `/api/chats/${storyId}/personas/${item.id}` },
        undoMessage: "Additional player added to the story.",
      });
    }
    if (item.kind === "lore" && item.reusable) {
      return requestMutation({
        itemKey, storyId, action: "lore-add", method: "POST",
        path: `/api/chats/${storyId}/lorebooks`, body: { lorebook_id: item.id },
        inverse: data => {
          const storyItemId = numericId(data?.lorebook_id);
          return storyItemId ? {
            method: "DELETE",
            path: `/api/chats/${storyId}/lorebooks/${storyItemId}`,
          } : null;
        },
        undoMessage: "Lore attached to the story.",
      });
    }
    return Promise.resolve(false);
  };

  const setArchived = (item, archived) => requestMutation({
    itemKey: item?.key,
    action: archived ? "archive" : "restore",
    method: archived ? "PUT" : "DELETE",
    path: `/api/library/${item?.kind}/${item?.id}/archive`,
    inverse: {
      method: archived ? "DELETE" : "PUT",
      path: `/api/library/${item?.kind}/${item?.id}/archive`,
    },
    undoMessage: archived ? `${item?.name || "Item"} archived.` : `${item?.name || "Item"} restored.`,
    navigateAfter: true,
  });

  const deleteStory = item => requestMutation({
    itemKey: item?.key,
    storyId: item?.id,
    action: "story-delete",
    method: "DELETE",
    path: `/api/chats/${item?.id}`,
    inverse: null,
    navigateAfter: true,
  });

  const generateLocationFromLore = async (item, value) => {
    const story = store.getSnapshot().story;
    const chatId = numericId(story?.data?.chat?.id);
    if (!chatId) throw new Error("Open the Story that should own this location, then return to this Lore.");
    if (story.frameId !== null && story.frameId !== undefined) {
      throw new Error("Return to the Story's present frame before creating a lived location.");
    }
    if (item?.kind !== "lore" || !numericId(item.id)) throw new Error("Choose reusable Lore first.");
    const capturedItem = item.key;
    const capturedRoute = currentRoute?.canonicalHash;
    patchLibrary({ mutation: { status: "saving", owner: capturedItem, message: "Creating lived location…" } });
    try {
      const data = await generateLivedLocation({
        apiClient, chatId, value, lorebookId: item.id,
        requestOptions: {
          channel: "library-lore-lived-location", owner: `${capturedItem}:story:${chatId}`,
          isCurrent: () => !stopped && currentRoute?.canonicalHash === capturedRoute
            && store.getSnapshot().library?.selected?.key === capturedItem,
        },
      });
      if (stopped || currentRoute?.canonicalHash !== capturedRoute) return null;
      const institutionCount = Object.keys(data?.charters?.items || {}).length;
      patchLibrary({ mutation: {
        status: "saved", owner: capturedItem,
        message: `${institutionCount} institutions prepared.`,
      } });
      return data;
    } catch (error) {
      if (["aborted", "stale"].includes(error?.kind)) return null;
      patchLibrary({ mutation: { status: "error", owner: capturedItem, message: error?.userMessage || error?.message || "The lived location could not be created." } });
      return null;
    }
  };

  const runUndo = async () => {
    const receipt = undoReceipt;
    if (!receipt || receipt.expiresAt <= Date.now()) {
      if (receipt) clearUndo();
      return false;
    }
    const requestGeneration = ++mutationGeneration;
    try {
      await apiClient.request(receipt.inverse.method, receipt.inverse.path, {
        body: receipt.inverse.body,
        channel: "library-mutation",
        owner: receipt.owner,
        isCurrent: identity => !stopped
          && identity.owner === receipt.owner
          && requestGeneration === mutationGeneration
          && undoReceipt === receipt,
      });
      if (stopped || undoReceipt !== receipt) return false;
      clearUndo();
      await refresh(router.current());
      return true;
    } catch (error) {
      if (stopped || ["aborted", "stale"].includes(error?.kind)) return false;
      patchLibrary({
        mutation: {
          status: "error",
          owner: receipt.owner,
          message: error?.userMessage || error?.message || "Undo was not accepted.",
        },
      });
      return false;
    }
  };

  const teardown = () => {
    if (stopped) return;
    stopped = true;
    generation += 1;
    mutationGeneration += 1;
    if (undoTimer) clearTimeout(undoTimer);
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
    scrollIdentity: libraryScrollIdentity,
    saveScroll,
    focusOnReturn: identity => {
      returnFocusIdentity = boundedText(identity, 160);
      return Boolean(returnFocusIdentity);
    },
    returnFocusIdentity: () => returnFocusIdentity,
    clearReturnFocus: identity => {
      if (returnFocusIdentity === identity) returnFocusIdentity = "";
    },
    setAssociation,
    addToStory,
    setArchived,
    deleteStory,
    generateLocationFromLore,
    runUndo,
    currentRoute: () => currentRoute,
    homeState: () => {
      const drafts = localState.snapshot().drafts?.["library-authoring"] || {};
      return Object.freeze({
        recents: presentation.recents.slice(0, 8),
        favorites: presentation.favorites.slice(0, 8),
        drafts: Object.keys(drafts).map(cleanItemId).filter(Boolean).slice(0, 8),
      });
    },
    teardown,
  });
}
