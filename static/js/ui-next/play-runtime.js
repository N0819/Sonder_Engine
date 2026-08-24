export const MODULE_RELEASE = "alpha98-ui15-5b0f039aae29";

import { ApiError } from "./errors.js?release=alpha98-ui15-5b0f039aae29";

const FRIENDLY_PHASES = Object.freeze({
  director_establish: "Setting the scene",
  director_interpret: "Reading what you did",
  mapping_stage: "Working out the surroundings",
  mapping_quick: "Checking the surroundings",
  perception_establish: "Working out what you notice",
  perception_act: "Working out who notices",
  reaction_loop: "Characters reacting",
  interaction_loop: "Characters responding",
  director_resolve: "Deciding what happens",
  perception_outcome: "Working out what everyone just saw",
  narrator: "Writing the scene",
  narrator_extra: "Writing the scene",
  commit: "Saving the story",
  background_react: "Bringing the room to life",
});
const DETAIL_LIMIT = 120;
const NARRATION_STEPS = new Set(["narrator", "narrator_extra"]);
// UI_CATALOG_START: composer validation shown beside the active field.
const WHITESPACE_MESSAGE = "Remove the spaces to send an empty continue turn.";
// UI_CATALOG_END

function numericId(value) {
  const id = Number(value);
  return Number.isSafeInteger(id) && id > 0 ? id : null;
}

function frameIdentity(value) {
  if (value === null || value === undefined || value === "" || value === "present") {
    return null;
  }
  return numericId(value);
}

function ownerFor(chatId, frameId) {
  return `chat-${chatId}:frame-${frameId ?? "present"}`;
}

function phaseFor(event) {
  const key = String(event?.key || "");
  const label = String(event?.label || "");
  if (/^Scene life/.test(label)) return "Bringing the room to life";
  if (FRIENDLY_PHASES[key]) return FRIENDLY_PHASES[key];
  if (key.startsWith("character:")) {
    const name = label.replace(/^Character\s*·\s*/, "").trim();
    return `${name || "A character"} is deciding what to do`;
  }
  return label || "Working…";
}

function safeName(value) {
  const name = String(value || "").trim();
  if (!name) throw new TypeError("A story name is required.");
  return name.slice(0, 200);
}

function storyPayload(value) {
  return Boolean(
    value && typeof value === "object" && !Array.isArray(value)
    && value.chat && typeof value.chat === "object"
    && Array.isArray(value.turns) && Array.isArray(value.frames),
  );
}

export function createPlayRuntime(options = {}) {
  const { store, apiClient, localState, tasks, notices, router, registry } = options;
  if (!store || !apiClient || !localState || !tasks || !notices || !router) {
    throw new TypeError("Play requires the coherent host runtime.");
  }
  const clock = options.clock || (() => Date.now());
  let stopped = false;
  let selected = { chatId: null, frameId: null, owner: null };
  let activeRun = null;
  let lastFailure = null;
  let loadSequence = 0;

  const replaceServer = (slice, value) => store.dispatch({
    type: "server/replace", slice, value,
  });
  const replacePresentation = (slice, value) => store.dispatch({
    type: "presentation/replace", slice, value,
  });
  const libraryChats = () => store.getSnapshot().library?.chats || [];
  const selectedStillMatches = (chatId, frameId = selected.frameId) => (
    !stopped && selected.chatId === chatId && selected.frameId === frameId
  );
  const currentTurns = payload => (payload.turns || []).filter(
    turn => (turn.frame_id ?? null) === selected.frameId,
  );

  const composerState = (patch = {}) => ({
    ...store.getSnapshot().composer,
    ...patch,
  });
  const publishComposer = patch => replacePresentation("composer", composerState(patch));

  const setEmpty = (reason = "no-story") => {
    selected = { chatId: null, frameId: null, owner: null };
    replaceServer("story", { status: "empty", data: null, reason });
    replaceServer("transcript", { status: "empty", owner: null, items: [], preview: null });
    replacePresentation("composer", {
      status: "ready", owner: null, draft: "", validation: "", run: null,
      failure: null,
    });
  };

  const applyStory = (payload, chatId, frameId) => {
    const owner = ownerFor(chatId, frameId);
    selected = { chatId, frameId, owner };
    const turns = (payload.turns || []).filter(
      turn => (turn.frame_id ?? null) === frameId,
    );
    replaceServer("story", {
      status: "ready",
      owner,
      frameId,
      data: payload,
      error: null,
    });
    replaceServer("transcript", {
      status: turns.length ? "ready" : "empty",
      owner,
      items: turns,
      preview: activeRun?.chatId === chatId && activeRun?.frameId === frameId
        ? activeRun.preview : null,
    });
    const run = activeRun?.chatId === chatId && activeRun?.frameId === frameId
      ? publicRun(activeRun) : null;
    const failure = lastFailure?.owner === owner ? lastFailure.public : null;
    replacePresentation("composer", {
      status: run?.status || (failure ? "recoverable-error" : "ready"),
      owner,
      draft: localState.getDraft("story", owner) ?? "",
      validation: "",
      run,
      failure,
    });
  };

  const loadStory = async (chatId, frameId = null, loadOptions = {}) => {
    const id = numericId(chatId);
    const frame = frameIdentity(frameId);
    const exists = libraryChats().some(chat => numericId(chat?.id) === id);
    if (!id || !exists) {
      setEmpty(id ? "story-unavailable" : "no-story");
      return false;
    }
    const owner = ownerFor(id, frame);
    selected = { chatId: id, frameId: frame, owner };
    const sequence = ++loadSequence;
    if (!loadOptions.silent) {
      replaceServer("story", { status: "loading", owner, data: null, error: null });
      replaceServer("transcript", { status: "loading", owner, items: [], preview: null });
      replacePresentation("composer", {
        status: activeRun?.chatId === id && activeRun?.frameId === frame
          ? activeRun.status : "ready",
        owner,
        draft: localState.getDraft("story", owner) ?? "",
        validation: "",
        run: activeRun?.chatId === id && activeRun?.frameId === frame
          ? publicRun(activeRun) : null,
        failure: lastFailure?.owner === owner ? lastFailure.public : null,
      });
    }
    try {
      const response = await apiClient.get(`/api/chats/${id}`, {
        channel: "play-story",
        owner,
        isCurrent: () => sequence === loadSequence && selectedStillMatches(id, frame),
      });
      if (!storyPayload(response.data)) {
        throw new ApiError("malformed-response", {
          status: response.status,
          requestId: response.requestId,
          correlationId: response.correlationId,
          technicalDetail: "Story payload was incomplete.",
        });
      }
      if (!selectedStillMatches(id, frame) || sequence !== loadSequence) return false;
      applyStory(response.data, id, frame);
      return true;
    } catch (error) {
      if (error?.kind === "aborted" || error?.kind === "stale") return false;
      if (!selectedStillMatches(id, frame) || sequence !== loadSequence) return false;
      replaceServer("story", {
        status: error?.kind === "malformed-response"
          ? "fatal"
          : (error?.kind === "network" ? "offline" : "error"),
        owner,
        data: null,
        error: {
          kind: error?.kind || "server",
          message: error?.userMessage || error?.message || "This story could not be opened.",
        },
      });
      replaceServer("transcript", { status: "error", owner, items: [], preview: null });
      publishComposer({ status: "recoverable-error", failure: {
        operation: "load", message: error.userMessage || error.message,
      } });
      return false;
    }
  };

  const syncRoute = route => {
    if (route?.destination !== "play") return;
    const chatId = numericId(route.query?.chat);
    const frameId = frameIdentity(route.query?.frame);
    if (chatId === selected.chatId && frameId === selected.frameId
        && store.getSnapshot().story.status !== "unrequested") return;
    if (!chatId) {
      loadSequence += 1;
      setEmpty();
      return;
    }
    void loadStory(chatId, frameId);
  };

  const routeUnsubscribe = store.subscribe(
    state => state.route,
    route => syncRoute(route),
    { equality: (left, right) => left?.canonicalHash === right?.canonicalHash },
  );

  const openStory = (chatId, frameId = null) => {
    const query = { chat: String(chatId) };
    if (frameId !== null && frameId !== undefined) query.frame = String(frameId);
    return router.navigate({ destination: "play", query });
  };

  const updateDraft = value => {
    if (!selected.owner) return false;
    const draft = String(value ?? "");
    localState.setDraft("story", selected.owner, draft);
    publishComposer({ draft, validation: "", failure: null });
    return true;
  };

  function publicRun(run) {
    if (!run) return null;
    return Object.freeze({
      id: run.id,
      owner: run.owner,
      chatId: run.chatId,
      frameId: run.frameId,
      turnId: run.turnId,
      kind: run.kind,
      status: run.status,
      phase: run.phase,
      startedAt: run.startedAt,
      accepted: run.accepted,
      detail: Object.freeze([...run.detail]),
    });
  }

  const publishRun = run => {
    if (!selectedStillMatches(run.chatId, run.frameId)) return;
    publishComposer({ status: run.status, run: publicRun(run), failure: null });
    if (run.preview && run.preview !== run.publishedPreview) {
      run.publishedPreview = run.preview;
      const transcript = store.getSnapshot().transcript;
      replaceServer("transcript", { ...transcript, preview: run.preview });
    }
  };

  const appendDetail = (run, event) => {
    const entry = {
      type: String(event?.type || "event"),
      key: String(event?.key || ""),
      label: String(event?.label || ""),
      reason: String(event?.reason || ""),
    };
    run.detail.push(entry);
    if (run.detail.length > DETAIL_LIMIT) run.detail.splice(0, run.detail.length - DETAIL_LIMIT);
  };

  const handleEvent = (run, event) => {
    if (activeRun !== run || !event || typeof event !== "object") return;
    if (event.type === "step_start") {
      run.phase = phaseFor(event);
    } else if (event.type === "step" && NARRATION_STEPS.has(event.key)) {
      const prose = event.content?.prose;
      if (typeof prose === "string" && prose.trim()) {
        run.preview = { prose, playerInput: run.input, turnId: run.turnId };
      }
    } else if (event.type === "aborted") {
      run.status = "stopping";
      run.phase = "Stopping generation";
    } else if (event.type === "error") {
      run.phase = "Generation reported a problem";
    }
    if (event.type !== "token") appendDetail(run, event);
    publishRun(run);
    void registry?.emitEvent?.(`turn:${event.type}`, event);
  };

  const runOperation = async operation => {
    if (activeRun) return false;
    const run = {
      id: `play-run-${clock()}`,
      owner: operation.owner,
      chatId: operation.chatId,
      frameId: operation.frameId,
      turnId: operation.turnId ?? null,
      input: operation.input || "",
      kind: operation.kind,
      path: operation.path,
      body: operation.body || {},
      status: "running",
      phase: "Getting started…",
      startedAt: clock(),
      accepted: false,
      detail: [],
      preview: null,
      publishedPreview: null,
      taskId: null,
    };
    activeRun = run;
    lastFailure = null;
    if (selectedStillMatches(run.chatId, run.frameId)) {
      const transcript = store.getSnapshot().transcript;
      if (transcript.preview) {
        replaceServer("transcript", { ...transcript, preview: null });
      }
    }
    run.taskId = tasks.start({
      owner: run.owner,
      name: run.kind === "reroll" ? "Reroll story turn" : "Generate story turn",
      phase: run.phase,
      cancel: () => stop(),
    });
    publishRun(run);
    let completed = false;
    const acceptRun = () => {
      if (activeRun !== run || run.accepted) return;
      run.accepted = true;
      if (run.kind === "send") {
        localState.clearDraft("story", run.owner);
        if (selected.owner === run.owner) publishComposer({ draft: "" });
      }
      publishRun(run);
    };
    try {
      await apiClient.stream(run.path, {
        method: "POST",
        body: run.body,
        channel: "play-generation",
        owner: run.owner,
        collectEvents: false,
        isCurrent: () => activeRun === run,
        onResponse: acceptRun,
        onEvent: event => {
          handleEvent(run, event);
          tasks.update(run.taskId, { phase: run.phase });
          if (event?.type === "done") completed = true;
        },
      });
      if (!completed && run.status !== "stopping") {
        throw new Error("Generation ended before the story was complete.");
      }
      tasks.complete(run.taskId, { summary: run.status === "stopping"
        ? "Generation stopped" : "Turn complete" });
      return completed;
    } catch (error) {
      if (run.status === "stopping" || error?.kind === "aborted") {
        tasks.complete(run.taskId, { summary: "Generation stopped" });
        return false;
      }
      tasks.fail(run.taskId, error);
      const retryable = !run.accepted;
      lastFailure = {
        owner: run.owner,
        operation: { ...operation },
        public: {
          operation: run.kind,
          message: error.userMessage || error.message || "Generation failed.",
          retryable,
        },
      };
      if (selected.owner === run.owner) publishComposer({
        status: "recoverable-error",
        failure: lastFailure.public,
      });
      notices.problem({
        owner: "play",
        condition: `generation:${run.owner}`,
        message: error.userMessage || error.message || "Generation failed.",
        error: { kind: error.kind || "server", retryable },
        retry: retryable ? () => retry() : null,
      });
      return false;
    } finally {
      if (activeRun === run) activeRun = null;
      if (selectedStillMatches(run.chatId, run.frameId)) {
        await loadStory(run.chatId, run.frameId, { silent: true });
        if (store.getSnapshot().composer.owner === run.owner
            && store.getSnapshot().composer.status !== "recoverable-error") {
          publishComposer({ status: "ready", run: null });
        }
      }
    }
  };

  const send = (value = store.getSnapshot().composer.draft) => {
    if (!selected.chatId || activeRun) return Promise.resolve(false);
    const input = String(value ?? "");
    updateDraft(input);
    if (input.length > 0 && !input.trim()) {
      publishComposer({ validation: WHITESPACE_MESSAGE });
      return Promise.resolve(false);
    }
    return runOperation({
      kind: "send",
      owner: selected.owner,
      chatId: selected.chatId,
      frameId: selected.frameId,
      input,
      path: `/api/chats/${selected.chatId}/turns`,
      body: { input: input.trim(), frame_id: selected.frameId },
    });
  };

  const reroll = turnId => {
    if (!selected.chatId || activeRun) return Promise.resolve(false);
    const id = numericId(turnId);
    if (!id) return Promise.resolve(false);
    return runOperation({
      kind: "reroll",
      owner: selected.owner,
      chatId: selected.chatId,
      frameId: selected.frameId,
      turnId: id,
      path: `/api/turns/${id}/reroll`,
      body: {},
    });
  };

  const retry = () => {
    if (!lastFailure?.operation || activeRun) return Promise.resolve(false);
    const operation = lastFailure.operation;
    if (operation.owner !== selected.owner) return Promise.resolve(false);
    return runOperation(operation);
  };

  async function stop() {
    const run = activeRun;
    if (!run) return false;
    run.status = "stopping";
    run.phase = "Stopping generation";
    publishRun(run);
    tasks.update(run.taskId, { phase: run.phase });
    const suffix = run.frameId === null ? "" : `?frame_id=${run.frameId}`;
    await apiClient.post(`/api/chats/${run.chatId}/abort${suffix}`, {}, {
      channel: `play-abort:${run.owner}`,
      owner: run.owner,
    });
    return true;
  }

  const refresh = () => selected.chatId
    ? loadStory(selected.chatId, selected.frameId, { silent: true })
    : Promise.resolve(false);

  const mutate = async (method, path, body) => {
    const response = await apiClient.request(method, path, {
      body,
      channel: `play-mutation:${path}`,
      owner: selected.owner,
    });
    await refresh();
    return response.data;
  };

  const rename = async value => {
    const name = safeName(value);
    await mutate("PUT", `/api/chats/${selected.chatId}`, { name });
    const library = store.getSnapshot().library;
    replaceServer("library", {
      ...library,
      chats: (library.chats || []).map(chat => (
        numericId(chat.id) === selected.chatId ? { ...chat, name } : chat
      )),
    });
    return name;
  };

  const exportArchive = async () => {
    const response = await apiClient.get(`/api/chats/${selected.chatId}/export`, {
      channel: `play-export:${selected.chatId}`,
      owner: selected.owner,
    });
    return {
      data: response.data,
      filename: `${String(response.data?.chat?.name || "story")
        .replace(/[^a-z0-9_-]/gi, "_")}.json`,
    };
  };

  const variants = async turnId => (await apiClient.get(
    `/api/turns/${numericId(turnId)}/narration`,
    { channel: `play-variants:${turnId}`, owner: selected.owner },
  )).data;
  const selectVariant = (turnId, variantId) => mutate(
    "POST", `/api/turns/${numericId(turnId)}/narration`, { variant_id: variantId },
  );
  const editInput = (turnId, input) => mutate(
    "PUT", `/api/turns/${numericId(turnId)}/input`, { input: String(input ?? "") },
  );
  const editProse = (turnId, prose) => mutate(
    "PUT", `/api/turns/${numericId(turnId)}/prose`, { prose: String(prose ?? "") },
  );
  const deleteTurn = turnId => mutate("DELETE", `/api/turns/${numericId(turnId)}`);
  const pipeline = async turnId => (await apiClient.get(
    `/api/turns/${numericId(turnId)}/pipeline`,
    { channel: `play-pipeline:${turnId}`, owner: selected.owner },
  )).data;
  const branch = async turnId => {
    const response = await apiClient.post(`/api/turns/${numericId(turnId)}/branch`, {}, {
      channel: `play-branch:${turnId}`, owner: selected.owner,
    });
    return response.data;
  };

  syncRoute(store.getSnapshot().route);

  const teardown = () => {
    if (stopped) return;
    stopped = true;
    loadSequence += 1;
    routeUnsubscribe();
  };

  return Object.freeze({
    openStory,
    loadStory,
    refresh,
    updateDraft,
    send,
    stop,
    retry,
    reroll,
    variants,
    selectVariant,
    rename,
    exportArchive,
    editInput,
    editProse,
    deleteTurn,
    pipeline,
    branch,
    activeRun: () => publicRun(activeRun),
    teardown,
  });
}
