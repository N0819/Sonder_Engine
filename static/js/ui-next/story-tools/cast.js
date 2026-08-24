export const MODULE_RELEASE = "alpha98-ui10-0415f377b12f";

import {
  button, element, errorState, fieldLabel, frameQuery, markData, replaceLocalized, stateMessage, toolScope,
} from "./shared.js?release=alpha98-ui10-0415f377b12f";

// UI_CATALOG_START: Cast tool actions and states.
const COPY = Object.freeze({
  loading: "Loading the current cast…",
  empty: "No characters are attached to this story yet.",
  unavailable: "The current cast could not be loaded.",
  participants: "Story cast",
  add: "Add to story",
  active: "Active",
  dormant: "Dormant",
  location: "Current location",
  offscreen: "Off screen",
  colour: "Dialogue colour",
  automatic: "Use automatic colour",
});
// UI_CATALOG_END

export function mountCastTool({ services, target, document: documentRef }) {
  const scope = toolScope(services, "cast");
  let stopped = false;

  const load = async () => {
    const { chatId, frameId } = scope.current();
    replaceLocalized(services, target, stateMessage(documentRef, "loading", COPY.loading));
    try {
      const [story, positions] = await Promise.all([
        scope.run("GET", "story", `/api/chats/${chatId}`),
        scope.run("GET", "positions", `/api/chats/${chatId}/positions${frameQuery(frameId)}`),
      ]);
      if (stopped || !scope.isLive() || !story || !positions) return;
      render(story, positions);
    } catch (error) {
      if (stopped || error?.kind === "stale" || error?.kind === "aborted") return;
      const problem = errorState(error);
      replaceLocalized(services, target, stateMessage(documentRef, problem.state, problem.message || COPY.unavailable, load));
    }
  };

  const mutate = async (method, key, path, body) => {
    const controlState = stateMessage(documentRef, "loading", "Saving cast change…");
    target.prepend(controlState);
    try {
      await scope.run(method, key, path, body);
      await services.play.refresh();
      await load();
    } catch (error) {
      controlState.replaceWith(stateMessage(documentRef, errorState(error).state, errorState(error).message, load));
      services.localizer.localize(target);
    }
  };

  const render = (story, positions) => {
    const { chatId, frameId } = scope.current();
    const participants = Array.isArray(story.participants) ? story.participants : [];
    const positionById = new Map((positions.characters || []).map(row => [Number(row.id), row]));
    const roomOptions = Array.isArray(positions.rooms) ? positions.rooms : [];
    const body = element(documentRef, "div", "ui-tool-stack");
    body.append(element(documentRef, "h4", "ui-heading ui-heading--4", COPY.participants));
    if (!participants.length) body.append(stateMessage(documentRef, "empty", COPY.empty));

    for (const person of participants) {
      const characterId = person.id;
      const row = element(documentRef, "article", "ui-tool-card ui-cast-card");
      row.dataset.characterId = String(characterId);
      const head = element(documentRef, "header", "ui-tool-card__header");
      const identity = element(documentRef, "div");
      identity.append(
        markData(element(documentRef, "h5", "ui-heading ui-heading--5", person.name)),
        element(documentRef, "span", "ui-badge", person.status === "active" ? COPY.active : COPY.dormant),
      );
      const status = button(documentRef, person.status === "active" ? "Move to dormant" : "Restore to active");
      status.addEventListener("click", () => mutate(
        person.status === "active" ? "DELETE" : "POST",
        `membership-${characterId}`,
        `/api/chats/${chatId}/characters${person.status === "active" ? `/${characterId}` : ""}`,
        person.status === "active" ? undefined : { char_id: characterId },
      ));
      head.append(identity, status);

      const location = documentRef.createElement("select");
      location.setAttribute("aria-label", `${COPY.location}: ${person.name}`);
      const placed = positionById.get(Number(person.id))?.room || "";
      const offscreen = element(documentRef, "option", "", COPY.offscreen);
      offscreen.value = "";
      location.append(offscreen);
      for (const room of roomOptions) {
        const option = element(documentRef, "option", "", room.parent_name
          ? `${room.parent_name} — ${room.name}` : room.name);
        option.value = room.id;
        option.selected = room.id === placed;
        markData(option);
        location.append(option);
      }
      location.addEventListener("change", () => mutate(
        "PUT", `position-${characterId}`,
        `/api/chats/${chatId}/characters/${characterId}/position${frameQuery(frameId)}`,
        { room: location.value },
      ));

      const colourWrap = element(documentRef, "div", "ui-tool-inline");
      const colour = documentRef.createElement("input");
      colour.type = "color";
      colour.value = story.dialogue_colors?.[person.name] || "#cccccc";
      colour.setAttribute("aria-label", `${COPY.colour}: ${person.name}`);
      colour.addEventListener("change", () => mutate(
        "PUT", `colour-${characterId}`,
        `/api/chats/${chatId}/characters/${characterId}/dialogue_color`,
        { color: colour.value },
      ));
      const automatic = button(documentRef, COPY.automatic);
      automatic.addEventListener("click", () => mutate(
        "PUT", `colour-${characterId}`,
        `/api/chats/${chatId}/characters/${characterId}/dialogue_color`,
        { color: "" },
      ));
      colourWrap.append(colour, automatic);
      row.append(head, fieldLabel(documentRef, COPY.location, location), fieldLabel(documentRef, COPY.colour, colourWrap));
      body.append(row);
    }

    const attached = new Set(participants.map(person => Number(person.id)));
    const available = (services.store.getSnapshot().library?.characters || [])
      .filter(person => !attached.has(Number(person.id)));
    if (available.length) {
      const addRow = element(documentRef, "div", "ui-tool-inline");
      const select = documentRef.createElement("select");
      select.setAttribute("aria-label", "Character to add");
      for (const person of available) {
        const option = element(documentRef, "option", "", person.name);
        option.value = person.id;
        markData(option);
        select.append(option);
      }
      const add = button(documentRef, COPY.add, "ui-button ui-button--primary");
      add.addEventListener("click", () => mutate("POST", "membership-add", `/api/chats/${chatId}/characters`, { char_id: Number(select.value) }));
      addRow.append(select, add);
      body.append(addRow);
    }
    replaceLocalized(services, target, body);
  };

  void load();
  return Object.freeze({ teardown() { stopped = true; scope.teardown(); } });
}
