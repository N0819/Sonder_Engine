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
  tools: "Authoring tools",
  toolBrief: "Optional direction for generation",
  generate: "Generate preview",
  appearanceFill: "Fill appearance",
  psychologyFill: "Fill psychology",
  greetingGenerate: "Generate greeting",
  greetingRecover: "Recover imported greetings",
  retryPreview: "Retry preview",
  discardPreview: "Discard preview",
  previewReady: "Preview applied to this draft. Save to accept it, or discard the preview.",
  previewFailed: "The preview failed. Your earlier draft is unchanged.",
  importTitle: "Import ${kind}",
  importHelp: "Choose a JSON card. Import creates a new reusable Library item.",
  importFile: "JSON card",
  reinterpret: "Reinterpret unfamiliar card fields with AI",
  importAction: "Import ${kind}",
  importing: "Importing…",
  invalidImport: "Choose a valid JSON object to import.",
  retryImport: "Retry import",
  stableIdentity: "Stable identity is read-only.",
  completeFields: "Complete card fields",
  completeFieldsHelp: "Every stored field is available below. Structured lists use JSON and apply when valid.",
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

const PRIMARY_PATHS = new Set([
  "identity.name", "identity.aliases", "identity.pronouns.subject",
  "identity.pronouns.object", "identity.pronouns.possessive",
  "embodiment.visible.summary", "knowledge.public_history",
  "opening.first_message",
]);

function humanize(value) {
  return String(value || "").replace(/_/g, " ").replace(/^./, letter => letter.toUpperCase());
}

function createSchemaNode(documentRef, path, value, update, t) {
  const dotted = path.join(".");
  if (PRIMARY_PATHS.has(dotted)) return null;
  if (value && typeof value === "object" && !Array.isArray(value)) {
    const details = node(documentRef, "details", "ui-authoring-schema__group");
    details.dataset.schemaPath = dotted;
    details.append(node(documentRef, "summary", "ui-authoring-field__label", humanize(path.at(-1))));
    const children = Object.entries(value).map(([key, child]) => (
      createSchemaNode(documentRef, [...path, key], child, update, t)
    )).filter(Boolean);
    if (!children.length) return null;
    details.append(...children);
    return details;
  }
  const id = `ui-schema-${dotted.replace(/[^a-zA-Z0-9_-]/g, "-")}`;
  let control;
  if (Array.isArray(value)) {
    control = textControl(documentRef, id, dotted, JSON.stringify(value, null, 2), true);
    control.classList.add("ui-authoring-schema__json");
    control.addEventListener("change", () => {
      try {
        const parsed = JSON.parse(control.value);
        if (!Array.isArray(parsed)) throw new Error("array required");
        control.removeAttribute("aria-invalid");
        update(path, parsed);
      } catch {
        control.setAttribute("aria-invalid", "true");
      }
    });
  } else if (typeof value === "boolean") {
    control = node(documentRef, "input");
    control.type = "checkbox";
    control.id = id;
    control.name = dotted;
    control.checked = value;
    control.addEventListener("change", () => update(path, control.checked));
  } else if (typeof value === "number") {
    control = node(documentRef, "input", "ui-input");
    control.type = "number";
    control.step = "any";
    control.id = id;
    control.name = dotted;
    control.value = String(value);
    control.addEventListener("input", () => {
      if (control.value !== "" && Number.isFinite(Number(control.value))) {
        update(path, Number(control.value));
      }
    });
  } else {
    control = textControl(documentRef, id, dotted, value, String(value || "").length > 80);
    control.addEventListener("input", () => update(path, control.value));
  }
  control.dataset.schemaPath = dotted;
  if (dotted === "identity.uid") {
    control.disabled = true;
    control.setAttribute("aria-description", t(COPY.stableIdentity));
  }
  return field(documentRef, humanize(path.at(-1)), control);
}

function createSchemaSections(documentRef, current, update, t) {
  const host = node(documentRef, "section", "ui-authoring-schema");
  host.append(node(documentRef, "h3", "ui-heading ui-heading--3", t(COPY.completeFields)));
  host.append(node(
    documentRef, "p", "ui-muted",
    t(COPY.completeFieldsHelp),
  ));
  for (const [key, value] of Object.entries(current)) {
    const section = createSchemaNode(documentRef, [key], value, update, t);
    if (section) host.append(section);
  }
  return host;
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
  const tools = node(documentRef, "section", "ui-authoring-tools");
  tools.append(node(documentRef, "h3", "ui-heading ui-heading--3", services.localizer.t(COPY.tools)));
  const brief = textControl(
    documentRef, `ui-person-tool-brief-${state.id || "new"}`, "authoring_brief", "", true,
  );
  tools.append(field(documentRef, services.localizer.t(COPY.toolBrief), brief));
  const toolActions = node(documentRef, "div", "ui-authoring-form__actions");
  const toolButton = (label, action) => {
    const control = node(documentRef, "button", "ui-button ui-button--quiet", services.localizer.t(label));
    control.type = "button";
    control.disabled = state.status === "previewing";
    control.addEventListener("click", () => action(brief.value.trim()));
    toolActions.append(control);
  };
  if (state.mode === "create") {
    toolButton(COPY.generate, value => services.authoring.previewGenerate(value));
  } else {
    toolButton(COPY.appearanceFill, value => services.authoring.previewAppearance(value));
    if (state.kind === "character") {
      toolButton(COPY.psychologyFill, value => services.authoring.previewPsychology(value));
      toolButton(COPY.greetingGenerate, value => services.authoring.previewGreeting(value));
      toolButton(COPY.greetingRecover, () => services.authoring.previewGreetingRecovery());
    }
  }
  if (state.status === "generation-error") {
    toolButton(COPY.retryPreview, () => services.authoring.retryPreview());
  }
  if (state.preview) {
    const discardGenerated = node(
      documentRef, "button", "ui-button ui-button--quiet",
      services.localizer.t(COPY.discardPreview),
    );
    discardGenerated.type = "button";
    discardGenerated.addEventListener("click", () => services.authoring.discardPreview());
    toolActions.append(discardGenerated);
  }
  tools.append(toolActions);
  if (state.preview || state.status === "generation-error") {
    const previewStatus = node(
      documentRef, "p", "ui-authoring__status",
      services.localizer.t(state.preview ? COPY.previewReady : COPY.previewFailed),
    );
    previewStatus.setAttribute("role", "status");
    if (state.status === "generation-error") previewStatus.dataset.tone = "danger";
    tools.append(previewStatus);
  }
  form.append(tools);
  form.append(createSchemaSections(
    documentRef, current, update, services.localizer.t,
  ));
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

export function createPersonImporter(options = {}) {
  const { document: documentRef, services, state } = options;
  const kind = state.kind === "character" ? "character" : "persona";
  const label = value => services.localizer.t(value).replace("${kind}", kind);
  const form = node(documentRef, "form", "ui-authoring-form");
  form.dataset.personImporter = kind;
  form.append(
    node(documentRef, "h3", "ui-heading ui-heading--2", label(COPY.importTitle)),
    node(documentRef, "p", "ui-muted", services.localizer.t(COPY.importHelp)),
  );
  const input = node(documentRef, "input", "ui-input");
  input.type = "file";
  input.id = `ui-${kind}-import-card`;
  input.name = `${kind}_card`;
  input.accept = "application/json,.json";
  let parsed = null;
  const feedback = node(documentRef, "p", "ui-authoring__status", state.error || "");
  feedback.setAttribute("role", "status");
  if (state.error) feedback.dataset.tone = "danger";
  input.addEventListener("change", async () => {
    parsed = null;
    feedback.textContent = "";
    input.removeAttribute("aria-invalid");
    try {
      const value = JSON.parse(await input.files?.[0]?.text());
      if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("invalid");
      parsed = value;
    } catch {
      input.setAttribute("aria-invalid", "true");
      feedback.textContent = services.localizer.t(COPY.invalidImport);
      feedback.dataset.tone = "danger";
    }
  });
  const reinterpretLabel = node(documentRef, "label", "ui-authoring-check");
  const reinterpret = node(documentRef, "input");
  reinterpret.type = "checkbox";
  reinterpret.name = "reinterpret";
  reinterpretLabel.append(reinterpret, node(documentRef, "span", "", services.localizer.t(COPY.reinterpret)));
  const actions = node(documentRef, "div", "ui-authoring-form__actions");
  const submit = node(
    documentRef, "button", "ui-button ui-button--primary",
    label(state.status === "importing" ? COPY.importing : COPY.importAction),
  );
  submit.type = "submit";
  submit.disabled = state.status === "importing";
  actions.append(submit);
  if (state.retryAvailable && state.status === "import-error") {
    const retry = node(documentRef, "button", "ui-button ui-button--quiet", services.localizer.t(COPY.retryImport));
    retry.type = "button";
    retry.addEventListener("click", () => services.authoring.retryImport());
    actions.append(retry);
  }
  form.append(field(documentRef, services.localizer.t(COPY.importFile), input), reinterpretLabel, feedback, actions);
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (!parsed) {
      input.setAttribute("aria-invalid", "true");
      feedback.textContent = services.localizer.t(COPY.invalidImport);
      feedback.dataset.tone = "danger";
      input.focus();
      return;
    }
    await services.authoring.importPerson(parsed, reinterpret.checked);
  });
  return form;
}
