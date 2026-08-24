export const MODULE_RELEASE = "alpha98-ui11-0acc47fb0573";

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
  const kind = match[1];
  const id = Number(match[2]);
  const mode = String(route.query?.mode || "view");
  const storyId = mode === "story-card" && kind === "character"
    ? Number(route.query?.story) : null;
  if (storyId !== null && (!Number.isSafeInteger(storyId) || storyId < 1)) return null;
  return Object.freeze({
    kind,
    id,
    storyId,
    owner: storyId ? `story-character:${storyId}:${id}` : `${kind}:${id}`,
    mode,
    route: String(route.canonicalHash || ""),
  });
}

function workflowOwner(route) {
  if (route?.destination !== "library"
      || !["create", "import"].includes(route.query?.mode)) return null;
  const kind = ({ stories: "story", characters: "character", personas: "persona", lore: "lore" })[
    route.segments?.[0]
  ] || "story";
  const mode = String(route.query.mode);
  const session = String(route.query?.session || "current").replace(/[^a-zA-Z0-9_-]/g, "").slice(0, 80) || "current";
  return Object.freeze({
    kind, id: null, owner: `${kind}:${mode}:${session}`, mode,
    route: String(route.canonicalHash || ""),
  });
}

function routeOwner(route) {
  return selectedOwner(route) || workflowOwner(route);
}

function writeSpec(owner, draft, revision) {
  if (owner.mode === "story-card" && owner.storyId) {
    return {
      method: "PUT",
      path: `/api/chats/${owner.storyId}/characters/${owner.id}/card`,
      body: { sheet: clone(draft) },
    };
  }
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
  let importDraft = null;
  let personImportDraft = null;
  let previewRetry = null;
  let previewBase = null;

  const patch = value => store.dispatch({
    type: "server/patch", slice: "library", value,
  });
  const isOwnerCurrent = captured => {
    const now = routeOwner(router.current());
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
        owner.mode === "story-card" && owner.storyId
          ? `/api/chats/${owner.storyId}`
          : `/api/library/authoring/${owner.kind}/${owner.id}`,
        {
          channel: "library-authoring-load",
          owner: owner.owner,
          isCurrent: identity => !stopped
            && identity.owner === active?.owner
            && requestGeneration === generation
            && routeOwner(router.current())?.owner === owner.owner,
        },
      );
      if (!isOwnerCurrent(owner) || requestGeneration !== generation) return false;
      let data = result.data;
      if (owner.mode === "story-card" && owner.storyId) {
        const participant = (data?.participants || []).find(
          row => Number(row.id) === owner.id,
        );
        if (!participant) throw new Error("That Character is not part of this Story.");
        let document;
        try {
          document = JSON.parse(participant.sheet || "{}");
        } catch {
          throw new Error("The Story card document was invalid.");
        }
        data = {
          owner: owner.owner, kind: "character", id: owner.id,
          revision: `story-card:${participant.card_source || "library"}`,
          document,
          overview: {
            story_id: owner.storyId,
            story_name: result.data?.chat?.name || "",
            card_source: participant.card_source || "library",
          },
        };
      }
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

  const loadTemplate = async owner => {
    generation += 1;
    const requestGeneration = generation;
    active = owner;
    patch({ authoring: {
      status: "loading", owner: owner.owner, kind: owner.kind, id: null,
      mode: owner.mode, route: owner.route, document: null, draft: null,
      revision: "", overview: null, restored: false, error: "",
    } });
    try {
      const path = owner.kind === "character"
        ? "/api/characters/new-document" : "/api/personas/new-document";
      const result = await apiClient.get(path, {
        channel: "library-authoring-template", owner: owner.owner,
        isCurrent: identity => identity.owner === owner.owner
          && requestGeneration === generation && routeOwner(router.current())?.owner === owner.owner,
      });
      if (!isOwnerCurrent(owner) || requestGeneration !== generation) return false;
      const template = result.data?.sheet;
      if (!template || typeof template !== "object" || Array.isArray(template)) {
        throw new Error("The new document template was incomplete.");
      }
      const recovered = restoredDraft(localState, owner.owner);
      patch({ authoring: {
        status: recovered ? "dirty" : "create-ready",
        owner: owner.owner, kind: owner.kind, id: null, mode: owner.mode,
        route: owner.route, document: clone(template),
        draft: clone(recovered || template), revision: "", overview: null,
        restored: Boolean(recovered), error: "", preview: null,
      } });
      return true;
    } catch (error) {
      if (stopped || requestGeneration !== generation
          || ["aborted", "stale"].includes(error?.kind)) return false;
      patch({ authoring: {
        status: "load-error", owner: owner.owner, kind: owner.kind, id: null,
        mode: owner.mode, route: owner.route, document: null,
        draft: restoredDraft(localState, owner.owner), revision: "",
        overview: null, restored: false,
        error: String(error?.userMessage || error?.message || "The new document could not be opened."),
      } });
      return false;
    }
  };

  const onRoute = route => {
    const owner = selectedOwner(route);
    const workflow = workflowOwner(route);
    if (!owner && workflow) {
      if (workflow.mode === "create" && ["character", "persona"].includes(workflow.kind)) {
        if (active?.owner === workflow.owner && active?.route === workflow.route) return;
        loadTemplate(workflow);
        return;
      }
      generation += 1;
      active = workflow;
      patch({ authoring: {
        status: "import-ready", owner: workflow.owner, kind: workflow.kind,
        id: null, mode: "import", route: workflow.route,
        document: null, draft: null, revision: "", overview: null,
        restored: false, error: "",
        retryAvailable: Boolean(importDraft || personImportDraft),
      } });
      return;
    }
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

  const stage = (document, options = {}) => {
    const state = store.getSnapshot().library.authoring;
    if (!state?.owner || !active || state.owner !== active.owner) {
      throw new Error("No Library authoring item is active.");
    }
    const draft = clone(document);
    const renderRevision = Number(state.renderRevision || 0)
      + (options.render ? 1 : 0);
    localState.setDraft("library-authoring", state.owner, JSON.stringify(draft));
    patch({ authoring: {
      ...state, status: "dirty", draft, restored: false, error: "",
      renderRevision,
    } });
    return draft;
  };

  const save = async () => {
    const state = store.getSnapshot().library.authoring;
    if (!state?.owner || !active || state.owner !== active.owner
        || (!DIRTY_STATES.has(state.status) && state.status !== "create-ready")
        || state.status === "saving") return false;
    const captured = Object.freeze({
      ...active, revision: state.revision, draft: clone(state.draft),
      generation,
    });
    const isCreate = captured.mode === "create" && captured.id === null;
    const spec = isCreate ? {
      method: "POST",
      path: captured.kind === "character" ? "/api/characters" : "/api/personas",
      body: { sheet: clone(captured.draft) },
    } : writeSpec(captured, captured.draft, captured.revision);
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
      if (captured.mode === "story-card" && captured.storyId) {
        if (!data?.sheet || typeof data.sheet !== "object") {
          throw new Error("The saved Story card response was incomplete.");
        }
        localState.clearDraft("library-authoring", captured.owner);
        patch({ authoring: {
          ...store.getSnapshot().library.authoring,
          status: "saved", document: clone(data.sheet), draft: clone(data.sheet),
          revision: "story-card:chat", restored: false, error: "",
          overview: {
            ...(store.getSnapshot().library.authoring.overview || {}),
            card_source: data.card_source || "chat",
          },
        } });
        return true;
      }
      if (isCreate) {
        const id = Number(data?.id);
        if (!Number.isSafeInteger(id) || id < 1) {
          throw new Error("The created item response was incomplete.");
        }
        localState.clearDraft("library-authoring", captured.owner);
        router.navigate({
          destination: "library",
          segments: [captured.kind === "character" ? "characters" : "personas"],
          query: { item: `${captured.kind}:${id}` },
        });
        return true;
      }
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

  const returnToLibrary = () => {
    const route = router.current();
    if (route?.destination !== "library") return false;
    const query = { ...(route.query || {}) };
    delete query.mode;
    delete query.session;
    if (["create", "import"].includes(active?.mode)) delete query.item;
    router.navigate({
      destination: "library",
      segments: Array.isArray(route.segments) ? route.segments.slice() : [],
      query,
    }, { replace: true });
    return true;
  };

  const importStory = async data => {
    if (active?.kind !== "story" || active?.mode !== "import") return false;
    importDraft = clone(data);
    const captured = Object.freeze({ ...active, generation });
    patch({ authoring: {
      ...store.getSnapshot().library.authoring,
      status: "importing", error: "", retryAvailable: true,
    } });
    try {
      const result = await apiClient.request("POST", "/api/chats/import", {
        body: { data: importDraft },
        channel: "library-authoring-import",
        owner: captured.owner,
        isCurrent: identity => identity.owner === captured.owner
          && isOwnerCurrent(captured) && generation === captured.generation,
      });
      if (!isOwnerCurrent(captured) || generation !== captured.generation) return false;
      const id = Number(result.data?.id);
      if (!Number.isSafeInteger(id) || id < 1) {
        throw new Error("The imported Story response was incomplete.");
      }
      importDraft = null;
      servicesNavigateToStory(id);
      return true;
    } catch (error) {
      if (!isOwnerCurrent(captured) || generation !== captured.generation
          || ["aborted", "stale"].includes(error?.kind)) return false;
      patch({ authoring: {
        ...store.getSnapshot().library.authoring,
        status: error?.kind === "forbidden" ? "permission-error" : "import-error",
        error: String(error?.userMessage || error?.message || "The Story could not be imported."),
        retryAvailable: true,
      } });
      return false;
    }
  };

  const importPerson = async (data, reinterpret = false) => {
    if (!active || active.mode !== "import"
        || !["character", "persona"].includes(active.kind)) return false;
    personImportDraft = { data: clone(data), reinterpret: Boolean(reinterpret) };
    const captured = Object.freeze({ ...active, generation });
    const state = store.getSnapshot().library.authoring;
    patch({ authoring: { ...state, status: "importing", error: "", retryAvailable: true } });
    try {
      const path = captured.kind === "character" ? "/api/characters/import" : "/api/personas/import";
      const result = await apiClient.request("POST", path, {
        body: { card: personImportDraft.data, reinterpret: personImportDraft.reinterpret },
        channel: "library-authoring-import", owner: captured.owner,
        isCurrent: identity => identity.owner === captured.owner
          && isOwnerCurrent(captured) && generation === captured.generation,
      });
      if (!isOwnerCurrent(captured) || generation !== captured.generation) return false;
      const id = Number(result.data?.id);
      if (!Number.isSafeInteger(id) || id < 1) throw new Error("The imported item response was incomplete.");
      personImportDraft = null;
      router.navigate({
        destination: "library",
        segments: [captured.kind === "character" ? "characters" : "personas"],
        query: { item: `${captured.kind}:${id}` },
      });
      return true;
    } catch (error) {
      if (!isOwnerCurrent(captured) || generation !== captured.generation
          || ["aborted", "stale"].includes(error?.kind)) return false;
      patch({ authoring: {
        ...store.getSnapshot().library.authoring,
        status: error?.kind === "forbidden" ? "permission-error" : "import-error",
        error: String(error?.userMessage || error?.message || "The item could not be imported."),
        retryAvailable: true,
      } });
      return false;
    }
  };

  const runPreview = async (name, path, body, applyResult) => {
    const state = store.getSnapshot().library.authoring;
    if (!active || !state?.draft || state.owner !== active.owner
        || state.status === "previewing") return false;
    const captured = Object.freeze({ ...active, generation });
    const base = clone(state.draft);
    previewRetry = () => runPreview(name, path, body, applyResult);
    patch({ authoring: { ...state, status: "previewing", error: "", previewTask: name } });
    try {
      const result = await apiClient.request("POST", path, {
        body, channel: "library-authoring-preview", owner: captured.owner,
        isCurrent: identity => identity.owner === captured.owner
          && isOwnerCurrent(captured) && generation === captured.generation,
      });
      if (!isOwnerCurrent(captured) || generation !== captured.generation) return false;
      const next = applyResult(result.data, base);
      if (!next || typeof next !== "object" || Array.isArray(next)) {
        throw new Error("The preview response was incomplete.");
      }
      previewBase = base;
      stage(next);
      const current = store.getSnapshot().library.authoring;
      patch({ authoring: {
        ...current, preview: { task: name }, error: "",
        renderRevision: Number(current.renderRevision || 0) + 1,
      } });
      return true;
    } catch (error) {
      if (!isOwnerCurrent(captured) || generation !== captured.generation
          || ["aborted", "stale"].includes(error?.kind)) return false;
      patch({ authoring: {
        ...store.getSnapshot().library.authoring, status: "generation-error",
        draft: base,
        error: String(error?.userMessage || error?.message || "The preview could not be generated."),
      } });
      return false;
    }
  };

  const previewGenerate = brief => {
    if (!active || active.mode !== "create") return false;
    const path = active.kind === "character"
      ? "/api/characters/generate-preview" : "/api/personas/generate-preview";
    return runPreview("generate", path, { brief }, data => data?.sheet);
  };
  const previewAppearance = brief => {
    if (!active?.id || !["character", "persona"].includes(active.kind)) return false;
    const state = store.getSnapshot().library.authoring;
    return runPreview(
      "appearance", `/api/${active.kind === "character" ? "characters" : "personas"}/${active.id}/fill_appearance`,
      { brief, draft: clone(state.draft) }, data => data?.sheet,
    );
  };
  const previewPsychology = brief => {
    if (!active?.id || active.kind !== "character") return false;
    const state = store.getSnapshot().library.authoring;
    return runPreview(
      "psychology", `/api/characters/${active.id}/fill_psychology`,
      { brief, draft: clone(state.draft) }, data => data?.sheet,
    );
  };
  const previewGreeting = brief => {
    if (!active?.id || active.kind !== "character") return false;
    return runPreview(
      "greeting", `/api/characters/${active.id}/generate_greeting`, { brief },
      (data, base) => {
        const next = clone(base);
        next.opening = { ...(next.opening || {}) };
        const greetings = Array.isArray(next.opening.greetings)
          ? next.opening.greetings.slice() : [];
        greetings.push(clone(data?.greeting));
        next.opening.greetings = greetings;
        if (!next.opening.first_message && data?.greeting?.prose) {
          next.opening.first_message = data.greeting.prose;
        }
        return next;
      },
    );
  };
  const previewGreetingRecovery = () => {
    if (!active?.id || active.kind !== "character") return false;
    const state = store.getSnapshot().library.authoring;
    return runPreview(
      "greeting-recovery", `/api/characters/${active.id}/recover_greetings_preview`,
      { draft: clone(state.draft) }, data => data?.sheet,
    );
  };

  const discardPreview = () => {
    if (!previewBase) return false;
    const base = clone(previewBase);
    previewBase = null;
    previewRetry = null;
    stage(base);
    const state = store.getSnapshot().library.authoring;
    patch({ authoring: {
      ...state, preview: null, error: "",
      renderRevision: Number(state.renderRevision || 0) + 1,
    } });
    return true;
  };

  const quickStart = async (options = {}) => {
    const personaId = Number(options.personaId);
    const greetingIndex = Number(options.greetingIndex || 0);
    let state = store.getSnapshot().library.authoring;
    if (!active?.id || active.kind !== "character"
        || !Number.isSafeInteger(personaId) || personaId < 1
        || !Number.isSafeInteger(greetingIndex) || greetingIndex < 0) return false;
    if (DIRTY_STATES.has(state.status)) {
      const saved = await save();
      if (!saved) return false;
      state = store.getSnapshot().library.authoring;
    }
    const captured = Object.freeze({ ...active, generation });
    patch({ authoring: { ...state, status: "starting-story", error: "" } });
    try {
      const result = await apiClient.request("POST", `/api/characters/${active.id}/start`, {
        body: {
          persona_id: personaId,
          greeting_index: greetingIndex,
          ...(options.lorebookId ? { lorebook_id: Number(options.lorebookId) } : {}),
          already_known: Boolean(options.alreadyKnown),
          language: String(options.language || "en"),
          ...(options.livedLocation ? { lived_location: clone(options.livedLocation) } : {}),
        },
        channel: "library-authoring-quick-start", owner: captured.owner,
        isCurrent: identity => identity.owner === captured.owner
          && isOwnerCurrent(captured) && generation === captured.generation,
      });
      if (!isOwnerCurrent(captured) || generation !== captured.generation) return false;
      const chatId = Number(result.data?.chat_id);
      if (!Number.isSafeInteger(chatId) || chatId < 1) {
        throw new Error("The started Story response was incomplete.");
      }
      router.navigate({ destination: "play", query: { chat: String(chatId) } });
      return true;
    } catch (error) {
      if (!isOwnerCurrent(captured) || generation !== captured.generation
          || ["aborted", "stale"].includes(error?.kind)) return false;
      patch({ authoring: {
        ...store.getSnapshot().library.authoring, status: "recoverable-error",
        error: String(error?.userMessage || error?.message || "The Story could not be started."),
      } });
      return false;
    }
  };

  const servicesNavigateToStory = id => router.navigate({
    destination: "library", segments: ["stories"],
    query: { item: `story:${id}` },
  });

  const branchStory = async turnIdValue => {
    const state = store.getSnapshot().library.authoring;
    const turnId = Number(turnIdValue);
    if (active?.kind !== "story" || active.id === null
        || !Number.isSafeInteger(turnId) || turnId < 1 || state?.status === "branching") {
      return false;
    }
    const captured = Object.freeze({ ...active, generation });
    patch({ authoring: { ...state, status: "branching", error: "" } });
    try {
      const result = await apiClient.request("POST", `/api/turns/${turnId}/branch`, {
        channel: "library-authoring-branch",
        owner: captured.owner,
        isCurrent: identity => identity.owner === captured.owner
          && isOwnerCurrent(captured) && generation === captured.generation,
      });
      if (!isOwnerCurrent(captured) || generation !== captured.generation) return false;
      const id = Number(result.data?.id);
      if (!Number.isSafeInteger(id) || id < 1) {
        throw new Error("The branched Story response was incomplete.");
      }
      servicesNavigateToStory(id);
      return true;
    } catch (error) {
      if (!isOwnerCurrent(captured) || generation !== captured.generation
          || ["aborted", "stale"].includes(error?.kind)) return false;
      patch({ authoring: {
        ...store.getSnapshot().library.authoring,
        status: "recoverable-error",
        error: String(error?.userMessage || error?.message || "The Story could not be branched."),
      } });
      return false;
    }
  };

  const duplicate = async () => {
    if (!active || !["character", "persona"].includes(active.kind) || !active.id) return false;
    const captured = Object.freeze({ ...active, generation });
    const state = store.getSnapshot().library.authoring;
    patch({ authoring: { ...state, status: "duplicating", error: "" } });
    const path = active.kind === "character"
      ? `/api/characters/${active.id}/duplicate`
      : `/api/personas/${active.id}/duplicate`;
    try {
      const result = await apiClient.request("POST", path, {
        channel: "library-authoring-duplicate",
        owner: captured.owner,
        isCurrent: identity => identity.owner === captured.owner
          && isOwnerCurrent(captured) && generation === captured.generation,
      });
      if (!isOwnerCurrent(captured) || generation !== captured.generation) return false;
      const id = Number(result.data?.id);
      if (!Number.isSafeInteger(id) || id < 1) throw new Error("The duplicate response was incomplete.");
      router.navigate({
        destination: "library",
        segments: [captured.kind === "character" ? "characters" : "personas"],
        query: { item: `${captured.kind}:${id}` },
      });
      return true;
    } catch (error) {
      if (!isOwnerCurrent(captured) || generation !== captured.generation
          || ["aborted", "stale"].includes(error?.kind)) return false;
      patch({ authoring: {
        ...store.getSnapshot().library.authoring,
        status: "recoverable-error",
        error: String(error?.userMessage || error?.message || "The item could not be duplicated."),
      } });
      return false;
    }
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
    apiClient.cancel?.("library-authoring-import", "runtime-stop");
    apiClient.cancel?.("library-authoring-branch", "runtime-stop");
    apiClient.cancel?.("library-authoring-duplicate", "runtime-stop");
    apiClient.cancel?.("library-authoring-template", "runtime-stop");
    apiClient.cancel?.("library-authoring-preview", "runtime-stop");
    apiClient.cancel?.("library-authoring-quick-start", "runtime-stop");
    target.removeEventListener("beforeunload", beforeUnload);
  };

  return Object.freeze({
    stage,
    save,
    discard,
    returnToLibrary,
    importStory,
    importPerson,
    retryImport: () => active?.kind === "story"
      ? (importDraft && importStory(importDraft))
      : (personImportDraft && importPerson(
        personImportDraft.data, personImportDraft.reinterpret,
      )),
    branchStory,
    duplicate,
    previewGenerate,
    previewAppearance,
    previewPsychology,
    previewGreeting,
    previewGreetingRecovery,
    retryPreview: () => previewRetry?.(),
    discardPreview,
    quickStart,
    reload: () => active?.id && load(active),
    teardown,
  });
}
