export const MODULE_RELEASE = "wp07.1";

import {
  button, element, errorState, fieldLabel, markData, replaceLocalized, stateMessage, toolScope,
} from "./shared.js?release=wp07.1";

// UI_CATALOG_START: Ambience tool actions, credits, and explicit states.
const COPY = Object.freeze({
  loading: "Checking this room's sound…",
  noTurn: "Write the first turn before choosing room ambience.",
  disabled: "Room ambience is turned off in Settings.",
  unconfigured: "Choose an ambience source in Settings before finding room sound.",
  absent: "No room ambience has been chosen yet.",
  pending: "Room ambience is being prepared.",
  silent: "This room is intentionally quiet.",
  error: "Room ambience is unavailable.",
  enable: "Enable audio",
  mute: "Mute",
  unmute: "Unmute",
  volume: "Ambience volume",
  chime: "Completion chime",
  check: "Check status",
  resolve: "Find room ambience",
  reroll: "Choose different ambience",
  settings: "Open ambience settings",
  pin: "Pin this sound to the room",
  clearPin: "Return room to automatic sound",
  thunder: "Preview thunder",
  layers: "Sound layers",
  source: "Source",
  browse: "Browse library",
  readingLibrary: "Reading the library…",
  emptyLibrary: "No playable files were found in the configured local library.",
  useHere: "Use here",
});
// UI_CATALOG_END

function latestTurn(services) {
  const story = services.store.getSnapshot().story;
  const frameId = story.frameId ?? null;
  return (story.data?.turns || []).filter(
    turn => (turn.frame_id ?? null) === frameId,
  ).at(-1) || null;
}

export function mountAmbienceTool({ services, target, document: documentRef }) {
  const scope = toolScope(services, "ambience");
  let stopped = false;

  const request = async (method, body = undefined) => {
    const turn = latestTurn(services);
    const { chatId } = scope.current();
    if (!turn) {
      replaceLocalized(services, target, stateMessage(documentRef, "empty", COPY.noTurn));
      return;
    }
    const turnId = turn.id;
    replaceLocalized(services, target, stateMessage(documentRef, "loading", COPY.loading));
    try {
      const [payload, pins] = await Promise.all([
        services.atmosphere.loadAmbience(turnId, {
          method,
          refresh: method === "GET" && body?.refresh === true,
          body: method === "POST" ? body : undefined,
        }),
        scope.run("GET", "pins", `/api/chats/${chatId}/ambience/pins`),
      ]);
      if (stopped || !scope.isLive() || !payload) return;
      render(payload, pins?.pins || {});
    } catch (error) {
      if (stopped || error?.kind === "stale" || error?.kind === "aborted") return;
      const problem = errorState(error);
      replaceLocalized(services, target, stateMessage(documentRef, problem.state, problem.message, () => request("GET")));
    }
  };

  const pin = async (payload, clear = false) => {
    const { chatId } = scope.current();
    const room = payload.room_id;
    const layer = payload.layers?.[0] || {};
    const path = `/api/chats/${chatId}/ambience/pin${clear ? `?room=${encodeURIComponent(room)}` : ""}`;
    try {
      await scope.run(clear ? "DELETE" : "PUT", "pin-write", path, clear ? undefined : {
        room,
        choice: {
          source: layer.source, path: layer.path, id: layer.id, title: layer.title,
          license: layer.license, username: layer.username, url: layer.credit_url,
        },
      });
      await request("GET");
    } catch (error) {
      if (stopped || error?.kind === "stale" || error?.kind === "aborted") return;
      target.prepend(stateMessage(documentRef, errorState(error).state, errorState(error).message));
      services.localizer.localize(target);
    }
  };

  const pinChoice = async (payload, choice) => {
    const { chatId } = scope.current();
    if (!payload.room_id) return;
    try {
      await scope.run("PUT", "pin-choice", `/api/chats/${chatId}/ambience/pin`, {
        room: payload.room_id,
        choice,
      });
      await request("GET");
    } catch (error) {
      if (stopped || error?.kind === "stale" || error?.kind === "aborted") return;
      target.prepend(stateMessage(documentRef, errorState(error).state, errorState(error).message));
      services.localizer.localize(target);
    }
  };

  const previewThunder = async () => {
    const { chatId } = scope.current();
    try {
      const payload = await scope.run(
        "GET", "oneshot-thunder", `/api/chats/${chatId}/ambience/oneshot/thunder`,
      );
      if (payload) services.atmosphere.playOneshot(payload);
    } catch (error) {
      if (stopped || error?.kind === "stale" || error?.kind === "aborted") return;
      target.prepend(stateMessage(documentRef, errorState(error).state, errorState(error).message));
      services.localizer.localize(target);
    }
  };

  const render = (payload, _pins) => {
    const media = services.atmosphere.snapshot();
    const preferences = media.preferences;
    const body = element(documentRef, "div", "ui-tool-stack ui-ambience-tool");
    const card = element(documentRef, "section", "ui-tool-card");
    if (payload.room) card.append(markData(element(documentRef, "h4", "ui-heading ui-heading--4", payload.room)));

    let state = "empty";
    let message = COPY.absent;
    if (!payload.enabled) { state = "disabled"; message = COPY.disabled; }
    else if (!payload.configured) { state = "disabled"; message = COPY.unconfigured; }
    else if (payload.status === "pending") { state = "loading"; message = COPY.pending; }
    else if (payload.silent) { state = "ready"; message = payload.reason || COPY.silent; }
    else if (payload.status === "ready" && payload.ready) { state = "ready"; message = payload.track?.title || "Room ambience ready"; }
    else if (payload.status === "error") { state = "error"; message = payload.error || COPY.error; }
    const statusBox = stateMessage(documentRef, state, message);
    if ((payload.silent && payload.reason)
        || (payload.ready && payload.track?.title)
        || (payload.status === "error" && payload.error)) markData(statusBox);
    card.append(statusBox);

    const controls = element(documentRef, "div", "ui-tool-form ui-ambience-controls");
    const audio = button(documentRef, media.audio.unlocked ? "Audio enabled" : COPY.enable, "ui-button ui-button--primary");
    audio.disabled = media.audio.unlocked;
    audio.addEventListener("click", async () => { await services.atmosphere.unlock(); render(payload, _pins); });
    const mute = button(documentRef, preferences.muted ? COPY.unmute : COPY.mute);
    mute.addEventListener("click", () => { services.atmosphere.setMuted(!preferences.muted); render(payload, _pins); });
    const immediate = element(documentRef, "div", "ui-tool-inline");
    immediate.append(audio, mute);

    const volume = documentRef.createElement("input");
    volume.type = "range"; volume.min = "0"; volume.max = "1"; volume.step = "0.05";
    volume.value = String(preferences.volume);
    volume.setAttribute("aria-label", COPY.volume);
    volume.addEventListener("input", () => services.atmosphere.setVolume(volume.value));

    const chime = documentRef.createElement("input");
    chime.type = "checkbox"; chime.checked = preferences.chime;
    chime.addEventListener("change", () => services.atmosphere.setChime(chime.checked));
    controls.append(immediate, fieldLabel(documentRef, COPY.volume, volume), fieldLabel(documentRef, COPY.chime, chime));
    card.append(controls);

    if (payload.layers?.length) {
      card.append(element(documentRef, "h5", "ui-heading ui-heading--5", COPY.layers));
      for (const layer of payload.layers) {
        const row = element(documentRef, "div", "ui-sound-layer");
        row.append(markData(element(documentRef, "strong", "", layer.title || layer.role || "Sound layer")));
        if (layer.username || layer.license) {
          row.append(markData(element(documentRef, "span", "ui-muted", `${layer.username || ""}${layer.license ? ` · ${layer.license}` : ""}`)));
        }
        if (layer.credit_url) {
          const source = element(documentRef, "a", "", COPY.source);
          source.href = layer.credit_url; source.target = "_blank"; source.rel = "noreferrer";
          row.append(source);
        }
        card.append(row);
      }
    }

    const actions = element(documentRef, "div", "ui-tool-inline");
    if (!payload.configured) {
      const settings = button(documentRef, COPY.settings);
      settings.addEventListener("click", () => services.router.navigate({
        destination: "settings", segments: ["ai-connections"], query: { section: "ambience" },
      }));
      actions.append(settings);
    } else if (payload.status === "pending") {
      const check = button(documentRef, COPY.check);
      check.addEventListener("click", () => void request("GET", { refresh: true }));
      actions.append(check);
    } else if (payload.ready) {
      const reroll = button(documentRef, COPY.reroll);
      reroll.addEventListener("click", () => void request("POST", { force: true, reroll: true }));
      actions.append(reroll);
    } else if (payload.enabled) {
      const resolve = button(documentRef, COPY.resolve);
      resolve.addEventListener("click", () => void request("POST", { force: true }));
      actions.append(resolve);
    }
    if (payload.ready && !payload.silent && payload.room_id) {
      const pinControl = button(documentRef, payload.pinned ? COPY.clearPin : COPY.pin);
      pinControl.addEventListener("click", () => void pin(payload, payload.pinned));
      actions.append(pinControl);
    }
    const thunder = button(documentRef, COPY.thunder);
    thunder.addEventListener("click", () => void previewThunder());
    actions.append(thunder);
    card.append(actions);
    body.append(card);
    if (payload.room_id) {
      const library = element(documentRef, "details", "ui-tool-card ui-ambience-library");
      const summary = element(documentRef, "summary", "ui-button ui-button--quiet", COPY.browse);
      const libraryBody = element(documentRef, "div", "ui-tool-stack");
      library.append(summary, libraryBody);
      library.addEventListener("toggle", () => {
        if (library.dataset.loaded || !library.open) return;
        library.dataset.loaded = "true";
        libraryBody.replaceChildren(stateMessage(documentRef, "loading", COPY.readingLibrary));
        void scope.run("GET", "library", "/api/ambience/library").then(result => {
          if (stopped || !scope.isLive()) return;
          libraryBody.replaceChildren();
          const files = Array.isArray(result?.files) ? result.files : [];
          if (!files.length) {
            libraryBody.append(stateMessage(documentRef, "empty", COPY.emptyLibrary));
            return;
          }
          for (const path of files) {
            const row = element(documentRef, "div", "ui-sound-layer");
            const label = markData(element(documentRef, "span", "", path));
            const use = button(documentRef, COPY.useHere);
            use.addEventListener("click", () => void pinChoice(payload, { source: "local", path }));
            row.append(label, use);
            libraryBody.append(row);
          }
          services.localizer.localize(libraryBody);
        }).catch(error => {
          if (stopped || error?.kind === "stale" || error?.kind === "aborted") return;
          libraryBody.replaceChildren(stateMessage(documentRef, errorState(error).state, errorState(error).message));
          services.localizer.localize(libraryBody);
        });
      });
      body.append(library);
    }
    replaceLocalized(services, target, body);
  };

  void request("GET");
  return Object.freeze({ teardown() { stopped = true; scope.teardown(); } });
}
