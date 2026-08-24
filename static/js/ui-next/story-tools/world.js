export const MODULE_RELEASE = "alpha98-ui5-7fa758fa6df7";

import { element, errorState, markData, replaceLocalized, stateMessage, toolScope } from "./shared.js?release=alpha98-ui5-7fa758fa6df7";
import { mountDocumentEditor } from "./document-editor.js?release=alpha98-ui5-7fa758fa6df7";

// UI_CATALOG_START: World summary copy.
const COPY = Object.freeze({
  loading: "Loading the current world…",
  empty: "The story has no world records yet.",
  records: "World records",
  rooms: "Rooms",
  entities: "Entities",
  positions: "Placements",
  conditions: "Standing conditions",
  location: "Current location",
});
// UI_CATALOG_END

function sceneFrom(world) {
  if (world?.scene && typeof world.scene === "object") return world.scene;
  const key = Object.keys(world || {}).find(name => name === "scene" || name.startsWith("scene"));
  return key && typeof world[key] === "object" ? world[key] : {};
}

export function mountWorldTool({ services, target, document: documentRef }) {
  const scope = toolScope(services, "world");
  let child = null;
  const load = async () => {
    const { chatId, owner } = scope.current();
    replaceLocalized(services, target, stateMessage(documentRef, "loading", COPY.loading));
    try {
      const world = await scope.run("GET", "world", `/api/chats/${chatId}/world`);
      if (!scope.isLive() || !world) return;
      if (!Object.keys(world).length) {
        replaceLocalized(services, target, stateMessage(documentRef, "empty", COPY.empty));
        return;
      }
      child = mountDocumentEditor({
        services, target, document: documentRef, toolId: "world", owner,
        serverValue: world,
        summary(value) {
          const scene = sceneFrom(value);
          const cards = element(documentRef, "div", "ui-tool-summary-grid");
          const metric = (label, amount) => {
            const card = element(documentRef, "article", "ui-tool-card ui-tool-metric");
            card.append(markData(element(documentRef, "strong", "", amount)), element(documentRef, "span", "", label));
            return card;
          };
          cards.append(
            metric(COPY.records, Object.keys(value || {}).length),
            metric(COPY.rooms, Object.keys(scene.rooms || {}).length),
            metric(COPY.entities, Object.keys(scene.entities || {}).length),
            metric(COPY.positions, Object.keys(scene.positions || {}).length),
            metric(COPY.conditions, Array.isArray(scene.world_conditions) ? scene.world_conditions.length : Object.keys(scene.conditions || {}).length),
          );
          const nodes = [cards];
          if (scene.location) {
            const location = element(documentRef, "p", "ui-muted");
            location.append(element(documentRef, "span", "", COPY.location), ": ", markData(element(documentRef, "span", "", scene.location)));
            nodes.unshift(location);
          }
          return nodes;
        },
        onSave: value => scope.run("PUT", "world-save", `/api/chats/${chatId}/world`, value),
      });
    } catch (error) {
      if (!scope.isLive() || error?.kind === "stale" || error?.kind === "aborted") return;
      const problem = errorState(error);
      replaceLocalized(services, target, stateMessage(documentRef, problem.state, problem.message, load));
    }
  };
  void load();
  return Object.freeze({ teardown() { child?.teardown(); scope.teardown(); } });
}
