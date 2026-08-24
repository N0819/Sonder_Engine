export const MODULE_RELEASE = "alpha98-ui6-ff8a9b712a2d";

import { element, errorState, frameQuery, markData, replaceLocalized, stateMessage, toolScope } from "./shared.js?release=alpha98-ui6-ff8a9b712a2d";

const VITALS = Object.freeze([
  Object.freeze({ key: "air", label: "Air", invert: false }),
  Object.freeze({ key: "stamina", label: "Stamina", invert: false }),
  Object.freeze({ key: "nourishment", label: "Satiation", invert: false }),
  Object.freeze({ key: "injury", label: "Injury", invert: true }),
]);

// UI_CATALOG_START: Conditions tool states and labels.
const COPY = Object.freeze({
  loading: "Loading current condition…",
  disabled: "Condition tracking is off for this story.",
  empty: "Condition tracking is on, but no bodies are tracked yet.",
  offline: "Condition is unavailable while the engine is offline.",
  error: "Current condition could not be read.",
  player: "Player",
  cast: "Cast",
});
// UI_CATALOG_END

function meter(documentRef, vital, value, label) {
  const numeric = Math.max(0, Math.min(Number(value ?? (vital.invert ? 0 : 1)), 1));
  const percent = Math.round(numeric * 100);
  const severity = vital.invert ? percent : 100 - percent;
  const row = element(documentRef, "div", "ui-vital");
  row.dataset.tone = severity >= 70 ? "danger" : severity >= 40 ? "warning" : "calm";
  const name = element(documentRef, "span", "ui-vital__name", vital.label);
  const bar = element(documentRef, "div", "ui-vital__meter");
  bar.setAttribute("role", "progressbar");
  bar.setAttribute("aria-label", `${vital.label}: ${label || `${percent}%`}`);
  bar.setAttribute("aria-valuemin", "0");
  bar.setAttribute("aria-valuemax", "100");
  bar.setAttribute("aria-valuenow", String(percent));
  const fill = element(documentRef, "span", "ui-vital__fill");
  fill.style.inlineSize = `${percent}%`;
  bar.append(fill);
  row.append(name, bar, element(documentRef, "span", "ui-vital__label", label || "—"));
  return row;
}

export function mountConditionsTool({ services, target, document: documentRef }) {
  const scope = toolScope(services, "conditions");
  let stopped = false;
  const load = async () => {
    const { chatId, frameId } = scope.current();
    replaceLocalized(services, target, stateMessage(documentRef, "loading", COPY.loading));
    try {
      const data = await scope.run("GET", "vitals", `/api/chats/${chatId}/vitals${frameQuery(frameId)}`);
      if (stopped || !scope.isLive() || !data) return;
      if (!data.enabled) {
        replaceLocalized(services, target, stateMessage(documentRef, "disabled", COPY.disabled));
        return;
      }
      const bodies = Array.isArray(data.bodies) ? data.bodies : [];
      if (!bodies.length) {
        replaceLocalized(services, target, stateMessage(documentRef, "empty", COPY.empty));
        return;
      }
      const list = element(documentRef, "div", "ui-tool-stack ui-conditions");
      list.dataset.state = "ready";
      for (const body of bodies) {
        const card = element(documentRef, "article", "ui-tool-card ui-condition-card");
        const heading = element(documentRef, "header", "ui-tool-card__header");
        heading.append(
          markData(element(documentRef, "h4", "ui-heading ui-heading--5", body.name)),
          element(documentRef, "span", "ui-badge", body.is_player ? COPY.player : COPY.cast),
        );
        const grid = element(documentRef, "div", "ui-condition-card__vitals");
        for (const vital of VITALS) {
          grid.append(meter(documentRef, vital, body.vitals?.[vital.key], body.labels?.[vital.key]));
        }
        card.append(heading, grid);
        list.append(card);
      }
      replaceLocalized(services, target, list);
    } catch (error) {
      if (stopped || error?.kind === "stale" || error?.kind === "aborted") return;
      const problem = errorState(error);
      const state = problem.state === "offline" ? "offline" : "error";
      replaceLocalized(services, target, stateMessage(documentRef, state, COPY[state] || problem.message, load));
    }
  };
  void load();
  return Object.freeze({ teardown() { stopped = true; scope.teardown(); } });
}
