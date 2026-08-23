export const MODULE_RELEASE = "alpha98-ui4-842dd802b09f";

import {
  button, element, errorState, markData, replaceLocalized, stateMessage, toolScope,
} from "./shared.js?release=alpha98-ui4-842dd802b09f";

// UI_CATALOG_START: Backdrop tool actions and explicit route states.
const COPY = Object.freeze({
  loading: "Checking this scene's backdrop…",
  noTurn: "Write the first turn before creating a scene backdrop.",
  disabled: "Scene backdrops are turned off in Settings.",
  unconfigured: "Choose an image model in Settings before generating backdrops.",
  absent: "This scene does not have a backdrop yet.",
  pending: "Backdrop is being prepared.",
  ready: "Backdrop ready",
  error: "This backdrop could not be prepared.",
  generate: "Generate backdrop",
  reroll: "Generate a different backdrop",
  check: "Check status",
  settings: "Open backdrop settings",
  weather: "Weather effect",
});
// UI_CATALOG_END

function latestTurn(services) {
  const story = services.store.getSnapshot().story;
  const frameId = story.frameId ?? null;
  return (story.data?.turns || []).filter(
    turn => (turn.frame_id ?? null) === frameId,
  ).at(-1) || null;
}

export function mountBackdropsTool({ services, target, document: documentRef }) {
  const scope = toolScope(services, "backdrops");
  let stopped = false;

  const openSettings = () => services.router.navigate({
    destination: "settings",
    segments: ["ai-connections"],
    query: { section: "backdrops" },
  });

  const request = async (method, force = false) => {
    const turn = latestTurn(services);
    if (!turn) {
      replaceLocalized(services, target, stateMessage(documentRef, "empty", COPY.noTurn));
      return;
    }
    const turnId = turn.id;
    replaceLocalized(services, target, stateMessage(documentRef, "loading", COPY.loading));
    try {
      const payload = await services.atmosphere.loadBackdrop(turnId, {
        method,
        refresh: method === "GET" && force,
        body: method === "POST" ? { force } : undefined,
      });
      if (stopped || !scope.isLive() || !payload) return;
      render(payload);
    } catch (error) {
      if (stopped || error?.kind === "stale" || error?.kind === "aborted") return;
      const problem = errorState(error);
      replaceLocalized(services, target, stateMessage(documentRef, problem.state, problem.message, () => request("GET")));
    }
  };

  const render = payload => {
    const body = element(documentRef, "div", "ui-tool-stack ui-backdrop-tool");
    const card = element(documentRef, "section", "ui-tool-card");
    if (payload.room) {
      card.append(markData(element(documentRef, "h4", "ui-heading ui-heading--4", payload.room)));
    }
    let state = "empty";
    let message = COPY.absent;
    if (!payload.enabled) { state = "disabled"; message = COPY.disabled; }
    else if (!payload.configured) { state = "disabled"; message = COPY.unconfigured; }
    else if (payload.status === "pending") { state = "loading"; message = COPY.pending; }
    else if (payload.status === "ready" && payload.ready) { state = "ready"; message = COPY.ready; }
    else if (payload.status === "error") { state = "error"; message = payload.error || COPY.error; }
    card.append(stateMessage(documentRef, state, message));

    if (payload.weather && Object.keys(payload.weather).length) {
      const weather = element(documentRef, "dl", "ui-tool-inline");
      const kind = payload.weather.precipitation || payload.weather.sky || payload.weather.kind || COPY.weather;
      weather.append(
        element(documentRef, "dt", "ui-kicker", COPY.weather),
        markData(element(documentRef, "dd", "", `${kind} · ${payload.weather.severity || "ordinary"}`)),
      );
      card.append(weather);
    }

    const actions = element(documentRef, "div", "ui-tool-inline");
    if (!payload.configured) {
      const settings = button(documentRef, COPY.settings, "ui-button ui-button--primary");
      settings.addEventListener("click", openSettings);
      actions.append(settings);
    } else if (payload.status === "pending") {
      const check = button(documentRef, COPY.check, "ui-button ui-button--primary");
      check.addEventListener("click", () => void request("GET", true));
      actions.append(check);
    } else if (payload.ready) {
      const reroll = button(documentRef, COPY.reroll);
      reroll.addEventListener("click", () => void request("POST", true));
      actions.append(reroll);
    } else if (payload.enabled) {
      const generate = button(documentRef, COPY.generate, "ui-button ui-button--primary");
      generate.addEventListener("click", () => void request("POST", false));
      actions.append(generate);
    }
    card.append(actions);
    body.append(card);
    replaceLocalized(services, target, body);
  };

  void request("GET");
  return Object.freeze({ teardown() { stopped = true; scope.teardown(); } });
}
