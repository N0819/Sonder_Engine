export const MODULE_RELEASE = "alpha98-ui4-842dd802b09f";

function numericId(value) {
  const id = Number(value);
  return Number.isSafeInteger(id) && id > 0 ? id : null;
}

function contextFrom(state, registry) {
  const story = state.story || {};
  const chatId = numericId(story.data?.chat?.id);
  const frameId = story.frameId ?? null;
  const requestedTool = state.route?.query?.tool;
  const toolId = requestedTool ? registry.resolveStoryTool(requestedTool).id : null;
  return {
    chatId,
    frameId,
    toolId,
    owner: chatId
      ? `chat-${chatId}:frame-${frameId ?? "present"}:tool-${toolId}`
      : null,
  };
}

export function createStoryToolsRuntime(options = {}) {
  const { store, apiClient, localState, router, toolRegistry } = options;
  if (!store || !apiClient || !localState || !router || !toolRegistry) {
    throw new TypeError("Story Tools require the coherent host runtime.");
  }
  let stopped = false;
  let sequence = 0;
  let activeRequest = null;
  const requestSequences = new Map();
  let current = contextFrom(store.getSnapshot(), toolRegistry);

  const publish = (status = "ready", patch = {}) => store.dispatch({
    type: "presentation/replace",
    slice: "inspector",
    value: {
      status,
      owner: current.owner,
      chatId: current.chatId,
      frameId: current.frameId,
      toolId: current.toolId,
      sequence,
      data: null,
      error: null,
      ...patch,
    },
  });

  const persistTool = toolId => {
    const panes = localState.snapshot().panes || {};
    const storyTools = panes.storyTools || {};
    localState.setRecord("panes", {
      ...panes,
      storyTools: { ...storyTools, toolId },
    });
  };

  const sync = state => {
    const next = contextFrom(state, toolRegistry);
    const changed = next.owner !== current.owner || next.toolId !== current.toolId;
    current = next;
    if (changed) {
      sequence += 1;
      activeRequest?.abort("story-tool-owner-changed");
      activeRequest = null;
    }
    publish(current.chatId ? "ready" : "empty");
  };

  const open = (toolValue, navigationOptions = {}) => {
    const snapshot = store.getSnapshot();
    const story = snapshot.story || {};
    const chatId = numericId(story.data?.chat?.id);
    if (!chatId) return false;
    const toolId = toolRegistry.resolveStoryTool(toolValue).id;
    const query = { chat: String(chatId), tool: toolId };
    if (story.frameId !== null && story.frameId !== undefined) {
      query.frame = String(story.frameId);
    }
    persistTool(toolId);
    router.navigate({
      destination: "play",
      segments: ["story-tools"],
      query,
    }, {
      replace: navigationOptions.replace !== false,
      preserveLayers: navigationOptions.preserveLayers === true,
    });
    return true;
  };

  const openFrame = frameValue => {
    const chatId = current.chatId;
    if (!chatId) return false;
    const frameId = numericId(frameValue);
    const query = { chat: String(chatId), tool: current.toolId };
    if (frameId) query.frame = String(frameId);
    router.navigate({
      destination: "play",
      segments: ["story-tools"],
      query,
    }, { replace: false, preserveLayers: true });
    return true;
  };

  const close = () => {
    if (!current.chatId) return false;
    const query = { chat: String(current.chatId) };
    if (current.frameId !== null && current.frameId !== undefined) {
      query.frame = String(current.frameId);
    }
    router.navigate({ destination: "play", segments: [], query }, {
      replace: true,
      preserveLayers: true,
    });
    return true;
  };

  const request = async (toolValue, key, method, path, body) => {
    const toolId = toolRegistry.resolveStoryTool(toolValue).id;
    if (!current.chatId || toolId !== current.toolId || !path) return null;
    const owner = current.owner;
    const requestKey = `${toolId}:${String(key || "data")}`;
    const requestSequence = (requestSequences.get(requestKey) || 0) + 1;
    requestSequences.set(requestKey, requestSequence);
    const options = {
      channel: `story-tools:${requestKey}`,
      owner,
      isCurrent: () => (
        !stopped
        && current.owner === owner
        && requestSequences.get(requestKey) === requestSequence
      ),
    };
    const verb = String(method || "GET").toUpperCase();
    const response = verb === "GET"
      ? await apiClient.get(path, options)
      : verb === "DELETE"
        ? await apiClient.delete(path, options)
        : await apiClient.request(verb, path, { ...options, body });
    return response.data;
  };

  const cancelRequest = (toolValue, key) => {
    const toolId = toolRegistry.resolveStoryTool(toolValue).id;
    const requestKey = `${toolId}:${String(key || "data")}`;
    requestSequences.delete(requestKey);
    return apiClient.cancel(`story-tools:${requestKey}`, "story-tool-unmounted");
  };

  const load = async (toolValue, path) => {
    const toolId = toolRegistry.resolveStoryTool(toolValue).id;
    if (!current.chatId || toolId !== current.toolId || !path) return null;
    activeRequest?.abort("story-tool-superseded");
    const controller = new AbortController();
    activeRequest = controller;
    const requestSequence = ++sequence;
    const requestOwner = current.owner;
    publish("loading");
    try {
      const response = await apiClient.get(path, {
        channel: `story-tools:${toolId}`,
        owner: requestOwner,
        isCurrent: () => (
          !stopped
          && !controller.signal.aborted
          && requestSequence === sequence
          && requestOwner === current.owner
        ),
      });
      if (controller.signal.aborted || requestSequence !== sequence) return null;
      publish("ready", { data: response.data });
      return response.data;
    } catch (error) {
      if (error?.kind === "aborted" || error?.kind === "stale") return null;
      if (requestSequence !== sequence || requestOwner !== current.owner) return null;
      publish(error?.kind === "network" ? "offline" : "error", {
        error: {
          kind: error?.kind || "server",
          message: error?.userMessage || error?.message || "This tool could not be loaded.",
        },
      });
      return null;
    } finally {
      if (activeRequest === controller) activeRequest = null;
    }
  };

  const unsubscribe = store.subscribe(
    state => ({ story: state.story, route: state.route }),
    value => sync({ ...store.getSnapshot(), ...value }),
    { equality: (left, right) => left.story === right.story && left.route === right.route },
  );
  sync(store.getSnapshot());

  const teardown = () => {
    if (stopped) return;
    stopped = true;
    sequence += 1;
    requestSequences.clear();
    activeRequest?.abort("story-tools-stop");
    activeRequest = null;
    unsubscribe();
  };

  return Object.freeze({
    open,
    close,
    openFrame,
    request,
    cancelRequest,
    load,
    current: () => Object.freeze({ ...current, sequence }),
    teardown,
  });
}
