export const MODULE_RELEASE = "alpha98-ui11-0acc47fb0573";

import { element, errorState, frameQuery, markData, replaceLocalized, stateMessage, toolScope } from "./shared.js?release=alpha98-ui11-0acc47fb0573";
import { mountDocumentEditor } from "./document-editor.js?release=alpha98-ui11-0acc47fb0573";

// UI_CATALOG_START: Attire summary copy.
const COPY = Object.freeze({
  loading: "Loading current attire…",
  empty: "No attire is recorded in this frame yet.",
  wearing: "Wearing",
  regions: "Body regions",
  state: "Visible state",
});
// UI_CATALOG_END

export function mountAttireTool({ services, target, document: documentRef }) {
  const scope = toolScope(services, "attire");
  let child = null;
  const load = async () => {
    const { chatId, frameId, owner } = scope.current();
    replaceLocalized(services, target, stateMessage(documentRef, "loading", COPY.loading));
    try {
      const data = await scope.run("GET", "attire", `/api/chats/${chatId}/attire${frameQuery(frameId)}`);
      if (!scope.isLive() || !data) return;
      child = mountDocumentEditor({
        services, target, document: documentRef, toolId: "attire", owner,
        serverValue: data,
        summary(value) {
          const people = Object.entries(value || {});
          if (!people.length) return stateMessage(documentRef, "empty", COPY.empty);
          return people.map(([name, entry]) => {
            const card = element(documentRef, "article", "ui-tool-card");
            card.append(markData(element(documentRef, "h4", "ui-heading ui-heading--5", name)));
            const list = (label, values) => {
              const safe = Array.isArray(values) ? values : Object.keys(values || {});
              const line = element(documentRef, "p", "ui-muted");
              line.append(element(documentRef, "span", "", label), ": ", markData(element(documentRef, "span", "", safe.join(", ") || "—")));
              return line;
            };
            card.append(list(COPY.wearing, entry?.wearing), list(COPY.regions, entry?.regions), list(COPY.state, entry?.state));
            return card;
          });
        },
        onSave: value => scope.run("PUT", "attire-save", `/api/chats/${chatId}/attire${frameQuery(frameId)}`, value),
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
