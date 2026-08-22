export const MODULE_RELEASE = "wp07.1";

// UI_CATALOG_START: Reusable person authoring labels.
const COPY = Object.freeze({
  name: "Name",
  aliases: "Aliases · one per line",
  subject: "Subject pronoun",
  object: "Object pronoun",
  possessive: "Possessive pronoun",
  appearance: "Visible appearance",
  history: "Public history",
  greeting: "First message",
  advanced: "Advanced JSON",
  advancedHelp: "This complete document includes fields not shown above. Apply only valid JSON.",
  applyAdvanced: "Apply advanced JSON",
  invalidJson: "The advanced document is not valid JSON. Nothing was applied.",
  saveCharacter: "Save character",
  savePersona: "Save persona",
  discard: "Discard draft",
});
// UI_CATALOG_END

function clone(value) {
  return globalThis.structuredClone
    ? globalThis.structuredClone(value)
    : JSON.parse(JSON.stringify(value));
}

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

function setPath(documentValue, path, value) {
  const next = clone(documentValue);
  let cursor = next;
  for (const part of path.slice(0, -1)) {
    if (!cursor[part] || typeof cursor[part] !== "object" || Array.isArray(cursor[part])) {
      cursor[part] = {};
    }
    cursor = cursor[part];
  }
  cursor[path.at(-1)] = value;
  return next;
}

function textControl(documentRef, id, name, value, long = false) {
  const control = node(documentRef, long ? "textarea" : "input", long ? "ui-textarea" : "ui-input");
  if (!long) control.type = "text";
  control.id = id;
  control.name = name;
  control.value = String(value || "");
  return control;
}

export function createPersonEditor(options = {}) {
  const { document: documentRef, services, state } = options;
  let current = clone(state.draft);
  let advanced;
  const form = node(documentRef, "form", "ui-authoring-form");
  form.dataset.personEditor = state.kind;
  const update = (path, value) => {
    current = setPath(current, path, value);
    if (advanced) advanced.value = JSON.stringify(current, null, 2);
    services.authoring.stage(current);
  };
  const bind = (control, path, read = element => element.value) => {
    control.addEventListener("input", () => update(path, read(control)));
    return control;
  };
  const identity = current.identity || {};
  const pronouns = identity.pronouns || {};
  const visible = current.embodiment?.visible || {};
  const name = bind(textControl(
    documentRef, `ui-person-name-${state.id}`, "identity.name", identity.name,
  ), ["identity", "name"]);
  name.required = true;
  name.maxLength = 240;
  const aliases = bind(textControl(
    documentRef, `ui-person-aliases-${state.id}`, "identity.aliases",
    (identity.aliases || []).join("\n"), true,
  ), ["identity", "aliases"], element => element.value.split(/\r?\n/)
    .map(value => value.trim()).filter(Boolean));
  const subject = bind(textControl(
    documentRef, `ui-person-subject-${state.id}`, "identity.pronouns.subject", pronouns.subject,
  ), ["identity", "pronouns", "subject"]);
  const object = bind(textControl(
    documentRef, `ui-person-object-${state.id}`, "identity.pronouns.object", pronouns.object,
  ), ["identity", "pronouns", "object"]);
  const possessive = bind(textControl(
    documentRef, `ui-person-possessive-${state.id}`, "identity.pronouns.possessive", pronouns.possessive,
  ), ["identity", "pronouns", "possessive"]);
  const appearance = bind(textControl(
    documentRef, `ui-person-appearance-${state.id}`, "embodiment.visible.summary",
    visible.summary, true,
  ), ["embodiment", "visible", "summary"]);
  const history = bind(textControl(
    documentRef, `ui-person-history-${state.id}`, "knowledge.public_history",
    current.knowledge?.public_history, true,
  ), ["knowledge", "public_history"]);
  form.append(
    field(documentRef, services.localizer.t(COPY.name), name),
    field(documentRef, services.localizer.t(COPY.aliases), aliases),
    field(documentRef, services.localizer.t(COPY.subject), subject),
    field(documentRef, services.localizer.t(COPY.object), object),
    field(documentRef, services.localizer.t(COPY.possessive), possessive),
    field(documentRef, services.localizer.t(COPY.appearance), appearance),
    field(documentRef, services.localizer.t(COPY.history), history),
  );
  if (state.kind === "character") {
    const greeting = bind(textControl(
      documentRef, `ui-character-greeting-${state.id}`, "opening.first_message",
      current.opening?.first_message, true,
    ), ["opening", "first_message"]);
    form.append(field(documentRef, services.localizer.t(COPY.greeting), greeting));
  }
  const disclosure = node(documentRef, "details", "ui-authoring-advanced");
  disclosure.append(node(documentRef, "summary", "ui-authoring-field__label", services.localizer.t(COPY.advanced)));
  disclosure.append(node(documentRef, "p", "ui-muted", services.localizer.t(COPY.advancedHelp)));
  advanced = textControl(
    documentRef, `ui-person-advanced-${state.id}`, "advanced_json",
    JSON.stringify(state.draft, null, 2), true,
  );
  advanced.classList.add("ui-authoring-form__json");
  const feedback = node(documentRef, "p", "ui-authoring__status");
  feedback.setAttribute("role", "status");
  const applyAdvanced = node(documentRef, "button", "ui-button ui-button--quiet", services.localizer.t(COPY.applyAdvanced));
  applyAdvanced.type = "button";
  applyAdvanced.dataset.applyAdvanced = "true";
  applyAdvanced.addEventListener("click", () => {
    try {
      const parsed = JSON.parse(advanced.value);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("invalid");
      current = clone(parsed);
      advanced.removeAttribute("aria-invalid");
      feedback.textContent = "";
      services.authoring.stage(parsed);
    } catch {
      advanced.setAttribute("aria-invalid", "true");
      feedback.textContent = services.localizer.t(COPY.invalidJson);
      feedback.dataset.tone = "danger";
      advanced.focus();
    }
  });
  disclosure.append(advanced, feedback, applyAdvanced);
  form.append(disclosure);
  const actions = node(documentRef, "div", "ui-authoring-form__actions");
  const discard = node(documentRef, "button", "ui-button ui-button--quiet", services.localizer.t(COPY.discard));
  discard.type = "button";
  discard.addEventListener("click", () => services.authoring.discard());
  const save = node(
    documentRef, "button", "ui-button ui-button--primary",
    services.localizer.t(state.kind === "character" ? COPY.saveCharacter : COPY.savePersona),
  );
  save.type = "submit";
  save.disabled = state.status === "saving" || !String(identity.name || "").trim();
  actions.append(discard, save);
  form.append(actions);
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (!String(current.identity?.name || "").trim()) {
      name.setAttribute("aria-invalid", "true");
      name.focus();
      return;
    }
    await services.authoring.save();
  });
  return form;
}
