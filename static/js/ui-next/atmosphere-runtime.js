export const MODULE_RELEASE = "alpha98-ui2-3f44d1cc71ed";

const DEFAULTS = Object.freeze({ muted: false, volume: 0.7, chime: false });

function boundedVolume(value) {
  const number = Number(value);
  return Number.isFinite(number) ? Math.min(1, Math.max(0, number)) : DEFAULTS.volume;
}

function ownerOf(story) {
  return story?.owner || null;
}

function latestTurn(story) {
  const frameId = story?.frameId ?? null;
  const turns = (story?.data?.turns || []).filter(
    turn => (turn.frame_id ?? null) === frameId,
  );
  return turns.at(-1) || null;
}

export function createAtmosphereRuntime(options = {}) {
  const { store, apiClient, localState } = options;
  const target = options.target || window;
  const documentRef = options.document || document;
  if (!store || !apiClient || !localState) {
    throw new TypeError("Play atmosphere requires the coherent host runtime.");
  }

  const saved = localState.snapshot().panes?.atmosphere || {};
  let preferences = {
    muted: Boolean(saved.muted),
    volume: boundedVolume(saved.volume ?? DEFAULTS.volume),
    chime: Boolean(saved.chime),
  };
  let currentOwner = null;
  let unlocked = false;
  let hidden = Boolean(documentRef.hidden);
  let ambienceToken = null;
  let audioLayers = [];
  let stopped = false;
  let previousStatus = store.getSnapshot().composer.status;
  let loadSequence = 0;
  const inflight = new Map();

  const snapshot = patch => ({
    ...store.getSnapshot().atmosphere,
    owner: currentOwner,
    preferences: { ...preferences },
    audio: {
      unlocked,
      playing: unlocked && !hidden && !preferences.muted && audioLayers.length > 0,
      token: ambienceToken,
    },
    ...patch,
  });
  const publish = patch => store.dispatch({
    type: "presentation/replace",
    slice: "atmosphere",
    value: snapshot(patch),
  });

  const persist = () => {
    const panes = localState.snapshot().panes || {};
    localState.setRecord("panes", {
      ...panes,
      atmosphere: {
        muted: preferences.muted,
        volume: preferences.volume,
        chime: preferences.chime,
      },
    });
  };

  const retireAudio = () => {
    for (const audio of audioLayers) {
      audio.pause();
      audio.removeAttribute?.("src");
      audio.load?.();
    }
    audioLayers = [];
    ambienceToken = null;
  };

  const syncAudio = () => {
    const shouldPlay = unlocked && !hidden && !preferences.muted;
    for (const audio of audioLayers) {
      audio.volume = boundedVolume(
        preferences.volume * Number(audio.dataset?.gain ?? 1),
      );
      if (shouldPlay) {
        audio.preload = "auto";
        audio.load?.();
        void audio.play().catch(() => publish({ mediaError: "Audio could not start." }));
      } else audio.pause();
    }
    publish({});
  };

  const applyBackdrop = (payload, owner = currentOwner, turnId = null) => {
    if (stopped || owner !== currentOwner) return false;
    publish({
      backdrop: {
        status: payload?.status || "absent",
        turnId,
        payload: payload || null,
      },
    });
    return true;
  };

  const applyAmbience = (payload, owner = currentOwner, turnId = null) => {
    if (stopped || owner !== currentOwner) return false;
    const token = payload?.token || null;
    if (token !== ambienceToken) {
      retireAudio();
      ambienceToken = token;
      if (payload?.ready && !payload?.silent && token) {
        const layers = payload.layers?.length ? payload.layers : [{ url: payload.url, gain: 1 }];
        audioLayers = layers.filter(layer => layer?.url).map(layer => {
          const audio = new target.Audio();
          audio.loop = true;
          audio.preload = "none";
          audio.src = layer.url;
          audio.dataset ||= {};
          audio.dataset.gain = String((payload.gain ?? 1) * (layer.gain ?? 1));
          return audio;
        });
      }
    }
    publish({
      ambience: {
        status: payload?.status || "absent",
        turnId,
        payload: payload || null,
      },
      mediaError: null,
    });
    syncAudio();
    return true;
  };

  const requestKind = (kind, turnId, requestOptions = {}) => {
    const owner = currentOwner;
    if (!owner || !turnId) return Promise.resolve(null);
    const method = String(requestOptions.method || "GET").toUpperCase();
    const current = store.getSnapshot().atmosphere?.[kind];
    if (method === "GET" && !requestOptions.refresh
        && current?.turnId === turnId && current?.payload) {
      return Promise.resolve(current.payload);
    }
    const key = `${owner}:${kind}:${turnId}:${method}`;
    if (inflight.has(key)) return inflight.get(key);
    const path = `/api/turns/${turnId}/${kind}`;
    const request = method === "GET"
      ? apiClient.get(path, { channel: `atmosphere:${kind}`, owner })
      : apiClient.request(method, path, {
        channel: `atmosphere:${kind}`, owner, body: requestOptions.body,
      });
    const job = request.then(response => {
      if (stopped || owner !== currentOwner) return null;
      if (kind === "backdrop") applyBackdrop(response.data, owner, turnId);
      else applyAmbience(response.data, owner, turnId);
      return response.data;
    }).finally(() => inflight.delete(key));
    inflight.set(key, job);
    return job;
  };

  const loadBackdrop = (turnId, requestOptions = {}) => requestKind("backdrop", turnId, requestOptions);
  const loadAmbience = (turnId, requestOptions = {}) => requestKind("ambience", turnId, requestOptions);

  const setMuted = value => {
    preferences = { ...preferences, muted: Boolean(value) };
    persist();
    syncAudio();
  };
  const setVolume = value => {
    preferences = { ...preferences, volume: boundedVolume(value) };
    persist();
    syncAudio();
  };
  const setChime = value => {
    preferences = { ...preferences, chime: Boolean(value) };
    persist();
    publish({});
  };
  const unlock = async () => {
    unlocked = true;
    syncAudio();
    return true;
  };

  const playOneshot = payload => {
    if (!payload?.ready || !payload.url || !unlocked || hidden || preferences.muted) return false;
    const clip = new target.Audio(payload.url);
    clip.volume = boundedVolume(preferences.volume * 0.7);
    void clip.play().catch(() => {});
    return true;
  };

  const completionChime = () => {
    if (!preferences.chime || !unlocked || hidden || preferences.muted) return;
    const AudioContext = target.AudioContext || target.webkitAudioContext;
    if (!AudioContext) return;
    try {
      const context = new AudioContext();
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      oscillator.frequency.value = 660;
      gain.gain.value = Math.min(0.12, preferences.volume * 0.12);
      oscillator.connect(gain); gain.connect(context.destination);
      oscillator.start(); oscillator.stop(context.currentTime + 0.12);
      oscillator.addEventListener("ended", () => void context.close(), { once: true });
    } catch {
      // Sound feedback is optional and must never interrupt a completed turn.
    }
  };

  const loadAutomatic = async state => {
    const story = state.story;
    const owner = ownerOf(story);
    const turn = latestTurn(story);
    if (!owner || !turn) return;
    const sequence = ++loadSequence;
    const loadOne = async (kind) => {
      try {
        const payload = await requestKind(kind, turn.id);
        if (!payload || sequence !== loadSequence) return;
      } catch (error) {
        if (error?.kind === "aborted" || error?.kind === "stale") return;
        publish({ [`${kind}Error`]: error?.userMessage || error?.message || `${kind} unavailable` });
      }
    };
    await Promise.all([loadOne("backdrop"), loadOne("ambience")]);
  };

  const onVisibility = () => {
    hidden = Boolean(documentRef.hidden);
    documentRef.documentElement.dataset.pageVisibility = hidden ? "hidden" : "visible";
    syncAudio();
  };
  documentRef.documentElement.dataset.pageVisibility = hidden ? "hidden" : "visible";
  documentRef.addEventListener("visibilitychange", onVisibility);

  const unsubscribe = store.subscribe(
    state => ({ story: state.story, route: state.route, composer: state.composer }),
    state => {
      const nextOwner = ownerOf(state.story);
      if (nextOwner !== currentOwner) {
        currentOwner = nextOwner;
        loadSequence += 1;
        retireAudio();
        publish({
          backdrop: { status: nextOwner ? "loading" : "absent", turnId: null, payload: null },
          ambience: { status: nextOwner ? "loading" : "absent", turnId: null, payload: null },
          mediaError: null,
        });
        if (nextOwner) void loadAutomatic(state);
      }
      const nextStatus = state.composer.status;
      if (previousStatus === "running" && nextStatus === "ready") completionChime();
      previousStatus = nextStatus;
    },
    { equality: (left, right) => (
      left.story === right.story && left.route === right.route && left.composer === right.composer
    ) },
  );

  currentOwner = ownerOf(store.getSnapshot().story);
  publish({
    status: "ready",
    backdrop: { status: "unrequested", turnId: null, payload: null },
    ambience: { status: "unrequested", turnId: null, payload: null },
    mediaError: null,
  });
  if (currentOwner) void loadAutomatic(store.getSnapshot());

  return Object.freeze({
    applyBackdrop, applyAmbience, loadBackdrop, loadAmbience,
    setMuted, setVolume, setChime, unlock,
    playOneshot,
    snapshot: () => store.getSnapshot().atmosphere,
    teardown() {
      if (stopped) return;
      stopped = true;
      loadSequence += 1;
      apiClient.cancel("atmosphere:backdrop", "runtime-stop");
      apiClient.cancel("atmosphere:ambience", "runtime-stop");
      documentRef.removeEventListener("visibilitychange", onVisibility);
      delete documentRef.documentElement.dataset.pageVisibility;
      unsubscribe();
      retireAudio();
    },
  });
}
