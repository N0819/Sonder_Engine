export const MODULE_RELEASE = "wp07.1";

// UI_CATALOG_START: Story authoring labels and recovery copy.
const COPY = Object.freeze({
  name: "Story name",
  scenario: "Story premise",
  persona: "Player persona",
  noPersona: "No player persona",
  save: "Save story",
  discard: "Discard draft",
  restored: "Recovered local draft",
});
// UI_CATALOG_END

function node(documentRef, tag, className = "", text = "") {
  const element = documentRef.createElement(tag);
  if (className) element.className = className;
  if (text) element.textContent = text;
  return element;
}

function field(documentRef, labelText, control) {
  const wrapper = node(documentRef, "div", "ui-authoring-field");
  const label = node(documentRef, "label", "ui-authoring-field__label", labelText);
  label.htmlFor = control.id;
  wrapper.append(label, control);
  return wrapper;
}

export function createStoryEditor(options = {}) {
  const { document: documentRef, services, state, onRender } = options;
  const form = node(documentRef, "form", "ui-authoring-form");
  form.dataset.storyEditor = "true";
  const name = node(documentRef, "input", "ui-input");
  name.type = "text";
  name.id = `ui-story-name-${state.id}`;
  name.name = "name";
  name.required = true;
  name.maxLength = 240;
  name.value = state.draft?.name || "";
  const scenario = node(documentRef, "textarea", "ui-textarea ui-authoring-form__long");
  scenario.id = `ui-story-scenario-${state.id}`;
  scenario.name = "scenario";
  scenario.value = state.draft?.scenario || "";
  const persona = node(documentRef, "select", "ui-select");
  persona.id = `ui-story-persona-${state.id}`;
  persona.name = "persona_id";
  const empty = node(documentRef, "option", "", services.localizer.t(COPY.noPersona));
  empty.value = "";
  persona.append(empty);
  for (const item of services.store.getSnapshot().library.personas || []) {
    const option = node(documentRef, "option", "", item.name || "Untitled persona");
    option.value = String(item.id);
    persona.append(option);
  }
  persona.value = state.draft?.persona_id == null ? "" : String(state.draft.persona_id);

  const read = () => ({
    name: name.value.trim(),
    scenario: scenario.value,
    persona_id: persona.value ? Number(persona.value) : null,
  });
  const onInput = () => services.authoring.stage(read());
  name.addEventListener("input", onInput);
  scenario.addEventListener("input", onInput);
  persona.addEventListener("change", onInput);
  form.append(
    field(documentRef, services.localizer.t(COPY.name), name),
    field(documentRef, services.localizer.t(COPY.scenario), scenario),
    field(documentRef, services.localizer.t(COPY.persona), persona),
  );
  if (state.restored) {
    const restored = node(documentRef, "p", "ui-notice", services.localizer.t(COPY.restored));
    restored.dataset.tone = "warning";
    form.append(restored);
  }
  const actions = node(documentRef, "div", "ui-authoring-form__actions");
  const discard = node(documentRef, "button", "ui-button ui-button--quiet", services.localizer.t(COPY.discard));
  discard.type = "button";
  discard.addEventListener("click", () => {
    services.authoring.discard();
    onRender?.();
  });
  const save = node(documentRef, "button", "ui-button ui-button--primary", services.localizer.t(COPY.save));
  save.type = "submit";
  save.disabled = state.status === "saving" || !name.value.trim();
  actions.append(discard, save);
  form.append(actions);
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (!name.value.trim()) {
      name.setAttribute("aria-invalid", "true");
      name.focus();
      return;
    }
    await services.authoring.save();
    onRender?.();
  });
  return form;
}
