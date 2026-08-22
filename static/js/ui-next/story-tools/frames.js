export const MODULE_RELEASE = "wp07.1";

import { button, element, errorState, fieldLabel, markData, replaceLocalized, stateMessage, toolScope } from "./shared.js?release=wp07.1";

// UI_CATALOG_START: Frames tool copy.
const COPY = Object.freeze({
  loading: "Loading story frames…",
  unavailable: "Story frames could not be loaded.",
  current: "Current frame",
  open: "Open frame",
  create: "Create frame",
  label: "Frame name",
  ordinal: "Story order",
  kind: "Relationship to the present",
  travelers: "Travelers who keep memory continuity",
  nonexistent: "Cast not yet existing in this frame",
  stationing: "Participant stationing",
  noPlayers: "No additional players are attached to this story.",
  present: "Present",
});
// UI_CATALOG_END

export function mountFramesTool({ services, target, document: documentRef }) {
  const scope = toolScope(services, "frames");
  let stopped = false;

  const load = async () => {
    const { chatId } = scope.current();
    replaceLocalized(services, target, stateMessage(documentRef, "loading", COPY.loading));
    try {
      const [frameData, personaData] = await Promise.all([
        scope.run("GET", "frames", `/api/chats/${chatId}/frames`),
        scope.run("GET", "personas", `/api/chats/${chatId}/personas`),
      ]);
      if (stopped || !scope.isLive() || !frameData || !personaData) return;
      render(frameData.frames || [], personaData.personas || []);
    } catch (error) {
      if (stopped || error?.kind === "stale" || error?.kind === "aborted") return;
      const problem = errorState(error);
      replaceLocalized(services, target, stateMessage(documentRef, problem.state, problem.message || COPY.unavailable, load));
    }
  };

  const save = async (method, key, path, body) => {
    try {
      await scope.run(method, key, path, body);
      await services.play.refresh();
      await load();
    } catch (error) {
      target.prepend(stateMessage(documentRef, errorState(error).state, errorState(error).message, load));
      services.localizer.localize(target);
    }
  };

  const render = (frames, personas) => {
    const { chatId, frameId } = scope.current();
    const body = element(documentRef, "div", "ui-tool-stack");
    const list = element(documentRef, "section", "ui-tool-stack");
    for (const frame of frames) {
      const id = frame.id ?? null;
      const card = element(documentRef, "article", "ui-tool-card ui-frame-card");
      const title = id === null ? COPY.present : frame.label;
      const head = element(documentRef, "header", "ui-tool-card__header");
      const identity = element(documentRef, "div");
      identity.append(
        markData(element(documentRef, "h4", "ui-heading ui-heading--5", title)),
        element(documentRef, "span", "ui-badge", frame.kind || COPY.present),
      );
      if (id === frameId) identity.append(element(documentRef, "span", "ui-badge", COPY.current));
      const open = button(documentRef, `${COPY.open}: ${title}`);
      open.disabled = id === frameId;
      open.addEventListener("click", () => {
        services.storyTools.openFrame(id);
      });
      head.append(identity, open);
      const details = element(documentRef, "p", "ui-muted",
        `${Number(frame.travelers?.length || 0)} travelers · ${Number(frame.nonexistent_cast?.length || 0)} not yet existing`);
      card.append(head, details);
      list.append(card);
    }
    body.append(list);

    const form = element(documentRef, "form", "ui-tool-form ui-tool-card");
    const label = documentRef.createElement("input");
    label.required = true;
    const ordinal = documentRef.createElement("input");
    ordinal.type = "number";
    ordinal.value = "0";
    const kind = documentRef.createElement("select");
    for (const value of ["future", "past", "other"]) {
      const option = element(documentRef, "option", "", value);
      option.value = value;
      kind.append(option);
    }
    const multi = (name, text) => {
      const select = documentRef.createElement("select");
      select.multiple = true;
      select.size = 3;
      select.setAttribute("aria-label", text);
      select.dataset.field = name;
      for (const person of services.store.getSnapshot().story.data?.participants || []) {
        const option = element(documentRef, "option", "", person.name);
        option.value = person.id;
        markData(option);
        select.append(option);
      }
      return select;
    };
    const travelers = multi("travelers", COPY.travelers);
    const nonexistent = multi("nonexistent", COPY.nonexistent);
    const create = button(documentRef, COPY.create, "ui-button ui-button--primary");
    create.type = "submit";
    form.append(
      fieldLabel(documentRef, COPY.label, label),
      fieldLabel(documentRef, COPY.ordinal, ordinal),
      fieldLabel(documentRef, COPY.kind, kind),
      fieldLabel(documentRef, COPY.travelers, travelers),
      fieldLabel(documentRef, COPY.nonexistent, nonexistent),
      create,
    );
    form.addEventListener("submit", event => {
      event.preventDefault();
      if (!label.value.trim()) return label.focus();
      save("POST", "create", `/api/chats/${chatId}/frames`, {
        label: label.value.trim(),
        ordinal: Number(ordinal.value) || 0,
        kind: kind.value,
        travelers: [...travelers.selectedOptions].map(option => Number(option.value)),
        nonexistent_cast: [...nonexistent.selectedOptions].map(option => Number(option.value)),
      });
    });
    body.append(form, element(documentRef, "h4", "ui-heading ui-heading--4", COPY.stationing));
    if (!personas.length) body.append(stateMessage(documentRef, "empty", COPY.noPlayers));
    for (const persona of personas) {
      const personaId = persona.id;
      const select = documentRef.createElement("select");
      select.setAttribute("aria-label", `${persona.name}: ${COPY.stationing}`);
      for (const frame of frames) {
        const option = element(documentRef, "option", "", frame.id === null ? COPY.present : frame.label);
        option.value = frame.id ?? "";
        option.selected = (frame.id ?? null) === (persona.frame_id ?? null);
        if (frame.id !== null) markData(option);
        select.append(option);
      }
      select.addEventListener("change", () => save(
        "PUT", `station-${personaId}`,
        `/api/chats/${chatId}/personas/${personaId}/station`,
        { frame_id: select.value ? Number(select.value) : null },
      ));
      const row = element(documentRef, "div", "ui-tool-card ui-tool-inline");
      row.append(markData(element(documentRef, "strong", "", persona.name)), select);
      body.append(row);
    }
    replaceLocalized(services, target, body);
  };

  void load();
  return Object.freeze({ teardown() { stopped = true; scope.teardown(); } });
}
