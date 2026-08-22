export const MODULE_RELEASE = "wp07.1";

const ITEM_ID = /^(story|character|persona|lore):([1-9][0-9]*)$/;
const DIRTY_STATES = new Set([
  "dirty", "saving", "conflict", "recoverable-error", "validation-error",
]);

function clone(value) {
  return globalThis.structuredClone
    ? globalThis.structuredClone(value)
    : JSON.parse(JSON.stringify(value));
}

function selectedOwner(route) {
  if (route?.destination !== "library") return null;
  const match = ITEM_ID.exec(String(route.query?.item || "").toLowerCase());
  if (!match) return null;
  return Object.freeze({
    kind: match[1],
    id: Number(match[2]),
    owner: `${match[1]}:${Number(match[2])}`,
    mode: String(route.query?.mode || "view"),
    route: String(route.canonicalHash || ""),
  });
}

function writeSpec(owner, draft, revision) {
  const paths = {
    story: `/api/chats/${owner.id}`,
    character: `/api/characters/${owner.id}`,
    persona: `/api/personas/${owner.id}`,
    lore: `/api/lorebooks/${owner.id}`,
  };
  const document = clone(draft);
  return {
    method: "PUT",
    path: paths[owner.kind],
    body: owner.kind === "story"
      ? { ...document, expected_revision: revision }
      : { sheet: document, expected_revision: revision },
  };
}

function restoredDraft(localState, owner) {
  const raw = localState.getDraft("library-authoring", owner);
  if (raw === null) return null;
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? parsed : null;
  } catch {
    return null;
  }
}

export function createLibraryAuthoringRuntime(options = {}) {
  const { store, apiClient, localState, router } = options;
  const target = options.target || window;
  if (!store || !apiClient || !localState || !router || !target) {
    throw new Error("Library authoring requires store, API, local state, routing, and a window target.");
  }
  let stopped = false;
  let generation = 0;
  let active = null;

  const patch = value => store.dispatch({
    type: "server/patch", slice: "library", value,
  });
  const isOwnerCurrent = captured => {
    const now = selectedOwner(router.current());
    return !stopped && now?.owner === captured.owner && active?.owner === captured.owner;
  };

  const load = async owner => {
    generation += 1;
    const requestGeneration = generation;
    active = owner;
    patch({ authoring: {
      status: "loading", owner: owner.owner, kind: owner.kind, id: owner.id,
      mode: owner.mode, route: owner.route, document: null, draft: null,
      revision: "", overview: null, restored: false, error: "",
    } });
    try {
      const result = await apiClient.get(
        `/api/library/authoring/${owner.kind}/${owner.id}`,
        {
          channel: "library-authoring-load",
          owner: owner.owner,
          isCurrent: identity => !stopped
            && identity.owner === active?.owner
            && requestGeneration === generation
            && selectedOwner(router.current())?.owner === owner.owner,
        },
      );
      if (!isOwnerCurrent(owner) || requestGeneration !== generation) return false;
      const data = result.data;
      if (data?.owner !== owner.owner || !data.document || !data.revision) {
        throw new Error("The authoring document response was incomplete.");
      }
      const recovered = restoredDraft(localState, owner.owner);
      patch({ authoring: {
        status: recovered ? "dirty" : "saved",
        owner: owner.owner, kind: owner.kind, id: owner.id,
        mode: owner.mode, route: owner.route,
        document: clone(data.document),
        draft: clone(recovered || data.document),
        revision: String(data.revision),
        overview: data.overview ? clone(data.overview) : null,
        restored: Boolean(recovered), error: "",
      } });
      return true;
    } catch (error) {
      if (stopped || requestGeneration !== generation
          || ["aborted", "stale"].includes(error?.kind)) return false;
      patch({ authoring: {
        status: error?.kind === "forbidden" ? "permission-error" : "load-error",
        owner: owner.owner, kind: owner.kind, id: owner.id,
        mode: owner.mode, route: owner.route,
        document: null, draft: restoredDraft(localState, owner.owner),
        revision: "", overview: null, restored: false,
        error: String(error?.userMessage || error?.message || "This item could not be opened."),
      } });
      return false;
    }
  };

  const onRoute = route => {
    const owner = selectedOwner(route);
    if (!owner) {
      active = null;
      generation += 1;
      patch({ authoring: null });
      return;
    }
    if (active?.owner === owner.owner && active?.route === owner.route) return;
    load(owner);
  };
  const unsubscribe = store.subscribe(state => state.route, onRoute);
  onRoute(store.getSnapshot().route);

  const stage = document => {
    const state = store.getSnapshot().library.authoring;
    if (!state?.owner || !active || state.owner !== active.owner) {
      throw new Error("No Library authoring item is active.");
    }
    const draft = clone(document);
    localState.setDraft("library-authoring", state.owner, JSON.stringify(draft));
    patch({ authoring: {
      ...state, status: "dirty", draft, restored: false, error: "",
    } });
    return draft;
  };

  const save = async () => {
    const state = store.getSnapshot().library.authoring;
    if (!state?.owner || !active || state.owner !== active.owner
        || !DIRTY_STATES.has(state.status) || state.status === "saving") return false;
    const captured = Object.freeze({
      ...active, revision: state.revision, draft: clone(state.draft),
      generation,
    });
    const spec = writeSpec(captured, captured.draft, captured.revision);
    patch({ authoring: { ...state, status: "saving", error: "" } });
    try {
      const result = await apiClient.request(spec.method, spec.path, {
        body: spec.body,
        channel: "library-authoring-save",
        owner: captured.owner,
        isCurrent: identity => identity.owner === captured.owner
          && isOwnerCurrent(captured) && generation === captured.generation,
      });
      if (!isOwnerCurrent(captured) || generation !== captured.generation) return false;
      const data = result.data;
      if (data?.owner !== captured.owner || !data.document || !data.revision) {
        throw new Error("The saved authoring document response was incomplete.");
      }
      localState.clearDraft("library-authoring", captured.owner);
      patch({ authoring: {
        ...store.getSnapshot().library.authoring,
        status: "saved", document: clone(data.document), draft: clone(data.document),
        revision: String(data.revision), restored: false, error: "",
      } });
      return true;
    } catch (error) {
      if (!isOwnerCurrent(captured) || generation !== captured.generation
          || ["aborted", "stale"].includes(error?.kind)) return false;
      patch({ authoring: {
        ...store.getSnapshot().library.authoring,
        status: error?.kind === "conflict" ? "conflict" : "recoverable-error",
        draft: clone(captured.draft),
        error: String(error?.userMessage || error?.message || "The draft could not be saved."),
      } });
      return false;
    }
  };

  const discard = () => {
    const state = store.getSnapshot().library.authoring;
    if (!state?.owner || !state.document) return false;
    localState.clearDraft("library-authoring", state.owner);
    patch({ authoring: {
      ...state, status: "saved", draft: clone(state.document), restored: false, error: "",
    } });
    return true;
  };

  const beforeUnload = event => {
    const state = store.getSnapshot().library.authoring;
    if (!state || !DIRTY_STATES.has(state.status)) return;
    event.preventDefault();
    event.returnValue = "";
  };
  target.addEventListener("beforeunload", beforeUnload);

  const teardown = () => {
    if (stopped) return;
    stopped = true;
    generation += 1;
    unsubscribe();
    apiClient.cancel?.("library-authoring-load", "runtime-stop");
    apiClient.cancel?.("library-authoring-save", "runtime-stop");
    target.removeEventListener("beforeunload", beforeUnload);
  };

  return Object.freeze({ stage, save, discard, reload: () => active && load(active), teardown });
}
