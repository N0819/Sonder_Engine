export const MODULE_RELEASE = "alpha98-ui5-7fa758fa6df7";

// UI_CATALOG_START: Story authoring labels and recovery copy.
const COPY = Object.freeze({
  name: "Story name",
  scenario: "Story premise",
  persona: "Player persona",
  noPersona: "No player persona",
  save: "Save story",
  discard: "Discard draft",
  restored: "Recovered local draft",
  importTitle: "Import story archive",
  importFile: "Story archive JSON",
  importHelp: "A new Story will be created. The selected archive is checked before it is sent.",
  importAction: "Import story",
  importing: "Importing story…",
  retryImport: "Retry import",
  invalidArchive: "Choose a valid Story JSON archive.",
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

export function createStoryImporter(options = {}) {
  const { document: documentRef, services, state } = options;
  const form = node(documentRef, "form", "ui-authoring-form");
  form.dataset.storyImporter = "true";
  form.append(
    node(documentRef, "h3", "ui-heading ui-heading--2", services.localizer.t(COPY.importTitle)),
    node(documentRef, "p", "ui-muted", services.localizer.t(COPY.importHelp)),
  );
  const archive = node(documentRef, "input", "ui-input");
  archive.type = "file";
  archive.id = "ui-story-import-archive";
  archive.name = "story_archive";
  archive.accept = "application/json,.json";
  const archiveField = field(documentRef, services.localizer.t(COPY.importFile), archive);
  const feedback = node(documentRef, "p", "ui-authoring__status", state.error || "");
  feedback.setAttribute("role", "status");
  if (state.error) feedback.dataset.tone = "danger";
  let parsed = null;
  archive.addEventListener("change", async () => {
    parsed = null;
    feedback.textContent = "";
    archive.removeAttribute("aria-invalid");
    const file = archive.files?.[0];
    if (!file) return;
    try {
      const value = JSON.parse(await file.text());
      if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("invalid");
      parsed = value;
    } catch {
      archive.setAttribute("aria-invalid", "true");
      feedback.textContent = services.localizer.t(COPY.invalidArchive);
      feedback.dataset.tone = "danger";
    }
  });
  const actions = node(documentRef, "div", "ui-authoring-form__actions");
  const submit = node(
    documentRef, "button", "ui-button ui-button--primary",
    services.localizer.t(state.status === "importing" ? COPY.importing : COPY.importAction),
  );
  submit.type = "submit";
  submit.disabled = state.status === "importing";
  actions.append(submit);
  if (state.retryAvailable && state.status === "import-error") {
    const retry = node(
      documentRef, "button", "ui-button ui-button--quiet",
      services.localizer.t(COPY.retryImport),
    );
    retry.type = "button";
    retry.addEventListener("click", () => services.authoring.retryImport());
    actions.append(retry);
  }
  form.append(archiveField, feedback, actions);
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (!parsed) {
      archive.setAttribute("aria-invalid", "true");
      feedback.textContent = services.localizer.t(COPY.invalidArchive);
      feedback.dataset.tone = "danger";
      archive.focus();
      return;
    }
    await services.authoring.importStory(parsed);
  });
  return form;
}
