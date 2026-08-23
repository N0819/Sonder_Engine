export const MODULE_RELEASE = "alpha98-ui2-3f44d1cc71ed";

export const PERSON_SECTION_IDS = Object.freeze([
  "basics", "appearance", "history", "inner-life", "opening",
  "simulation", "story-presence", "quick-start", "additional", "advanced",
]);

const GROUPS = Object.freeze({
  identity: "basics",
  initial_outfit: "appearance",
  embodiment: "appearance",
  competence: "appearance",
  knowledge: "history",
  psychology: "inner-life",
  social: "inner-life",
  initial_state: "inner-life",
  opening: "opening",
  simulation: "simulation",
  narration: "story-presence",
});

const PRIMARY_PATHS = new Set([
  "identity.name", "identity.aliases", "identity.pronouns.subject",
  "identity.pronouns.object", "identity.pronouns.possessive",
  "embodiment.visible.summary", "knowledge.public_history",
  "opening.first_message",
]);

const activeSections = new Map();

// UI_CATALOG_START: Shared person editor sections and fields.
const COPY = Object.freeze({
  sections: "Editor sections",
  basics: "Basics",
  appearanceSection: "Appearance",
  historySection: "History",
  innerLife: "Inner life",
  openingSection: "Opening",
  simulation: "Simulation",
  storyPresence: "Story presence",
  quickStart: "Quick start",
  additional: "Additional fields",
  advanced: "Advanced",
  name: "Name",
  aliases: "Aliases · one per line",
  subject: "Subject pronoun",
  object: "Object pronoun",
  possessive: "Possessive pronoun",
  appearance: "Visible appearance",
  history: "Public history",
  greeting: "First message",
  stableIdentity: "Stable identity is read-only.",
});
// UI_CATALOG_END

const LABELS = Object.freeze({
  basics: COPY.basics,
  appearance: COPY.appearanceSection,
  history: COPY.historySection,
  "inner-life": COPY.innerLife,
  opening: COPY.openingSection,
  simulation: COPY.simulation,
  "story-presence": COPY.storyPresence,
  "quick-start": COPY.quickStart,
  additional: COPY.additional,
  advanced: COPY.advanced,
});

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

function textControl(documentRef, id, name, value, long = false) {
  const control = node(documentRef, long ? "textarea" : "input", long ? "ui-textarea" : "ui-input");
  if (!long) control.type = "text";
  control.id = id;
  control.name = name;
  control.value = String(value ?? "");
  return control;
}

function humanize(value) {
  return String(value || "").replace(/_/g, " ").replace(/^./, letter => letter.toUpperCase());
}

function createSchemaNode(documentRef, path, value, onChange, t) {
  const dotted = path.join(".");
  if (PRIMARY_PATHS.has(dotted)) return null;
  if (value && typeof value === "object" && !Array.isArray(value)) {
    const details = node(documentRef, "details", "ui-authoring-schema__group");
    details.dataset.schemaPath = dotted;
    details.append(node(documentRef, "summary", "ui-authoring-field__label", humanize(path.at(-1))));
    const children = Object.entries(value)
      .map(([key, child]) => createSchemaNode(documentRef, [...path, key], child, onChange, t))
      .filter(Boolean);
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
        onChange(path, parsed);
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
    control.addEventListener("change", () => onChange(path, control.checked));
  } else if (typeof value === "number") {
    control = node(documentRef, "input", "ui-input");
    control.type = "number";
    control.step = "any";
    control.id = id;
    control.name = dotted;
    control.value = String(value);
    control.addEventListener("input", () => {
      if (control.value !== "" && Number.isFinite(Number(control.value))) {
        onChange(path, Number(control.value));
      }
    });
  } else {
    control = textControl(documentRef, id, dotted, value, String(value ?? "").length > 80);
    control.addEventListener("input", () => onChange(path, control.value));
  }
  control.dataset.schemaPath = dotted;
  if (dotted === "identity.uid") {
    control.disabled = true;
    control.setAttribute("aria-description", t(COPY.stableIdentity));
  }
  return field(documentRef, humanize(path.at(-1)), control);
}

function applicableSectionIds(current, kind, mode) {
  const base = kind === "character"
    ? ["basics", "appearance", "history", "inner-life", "opening", "simulation"]
    : ["basics", "appearance", "history", "story-presence"];
  if (kind === "character" && mode === "edit") base.push("quick-start");
  const baseSet = new Set(base);
  const hasAdditional = Object.keys(current).some(key => !baseSet.has(GROUPS[key]));
  if (hasAdditional) base.push("additional");
  base.push("advanced");
  return base;
}

function rememberActive(key, sectionId) {
  activeSections.delete(key);
  activeSections.set(key, sectionId);
  while (activeSections.size > 24) activeSections.delete(activeSections.keys().next().value);
}

export function createPersonSectionEditor(options = {}) {
  const {
    document: documentRef, current, kind, mode, t,
    onChange, onNameChange = () => {}, owner = `${kind}:new`,
  } = options;
  const ids = applicableSectionIds(current, kind, mode);
  const editor = node(documentRef, "div", "ui-person-editor");
  const nav = node(documentRef, "div", "ui-person-editor__nav");
  nav.setAttribute("role", "tablist");
  nav.setAttribute("aria-label", t(COPY.sections));
  const panelsHost = node(documentRef, "div", "ui-person-editor__panels");
  const panels = new Map();
  const buttons = new Map();
  const key = String(owner || `${kind}:new`);

  for (const sectionId of ids) {
    const button = node(documentRef, "button", "ui-person-editor__tab", t(LABELS[sectionId]));
    const panel = node(documentRef, "section", "ui-person-editor__panel");
    const suffix = `${key}-${sectionId}`.replace(/[^a-zA-Z0-9_-]/g, "-");
    button.type = "button";
    button.id = `ui-person-tab-${suffix}`;
    button.setAttribute("role", "tab");
    button.setAttribute("aria-controls", `ui-person-panel-${suffix}`);
    panel.id = `ui-person-panel-${suffix}`;
    panel.dataset.editorSection = sectionId;
    panel.setAttribute("role", "tabpanel");
    panel.setAttribute("aria-labelledby", button.id);
    panel.append(node(documentRef, "h3", "ui-heading ui-heading--3", t(LABELS[sectionId])));
    nav.append(button);
    panelsHost.append(panel);
    buttons.set(sectionId, button);
    panels.set(sectionId, panel);
  }

  const activate = (requested, focusTab = false) => {
    const sectionId = panels.has(requested) ? requested : ids[0];
    for (const id of ids) {
      const active = id === sectionId;
      const button = buttons.get(id);
      const panel = panels.get(id);
      button.setAttribute("aria-selected", String(active));
      button.tabIndex = active ? 0 : -1;
      panel.hidden = !active;
    }
    rememberActive(key, sectionId);
    if (focusTab) buttons.get(sectionId)?.focus();
    return sectionId;
  };

  ids.forEach((sectionId, index) => {
    const button = buttons.get(sectionId);
    button.addEventListener("click", () => activate(sectionId));
    button.addEventListener("keydown", event => {
      let next = null;
      if (event.key === "ArrowDown" || event.key === "ArrowRight") next = (index + 1) % ids.length;
      if (event.key === "ArrowUp" || event.key === "ArrowLeft") next = (index - 1 + ids.length) % ids.length;
      if (event.key === "Home") next = 0;
      if (event.key === "End") next = ids.length - 1;
      if (next === null) return;
      event.preventDefault();
      activate(ids[next], true);
    });
  });

  const bindText = (sectionId, labelText, id, name, value, path, long = false, read = control => control.value) => {
    const control = textControl(documentRef, id, name, value, long);
    control.addEventListener("input", () => onChange(path, read(control)));
    panels.get(sectionId)?.append(field(documentRef, t(labelText), control));
    return control;
  };

  const identity = current.identity || {};
  const pronouns = identity.pronouns || {};
  const name = bindText("basics", COPY.name, `ui-person-name-${owner}`, "identity.name", identity.name, ["identity", "name"]);
  name.required = true;
  name.maxLength = 240;
  name.disabled = mode === "story-card";
  name.addEventListener("input", () => onNameChange(name.value));
  bindText(
    "basics", COPY.aliases, `ui-person-aliases-${owner}`, "identity.aliases",
    (identity.aliases || []).join("\n"), ["identity", "aliases"], true,
    control => control.value.split(/\r?\n/).map(value => value.trim()).filter(Boolean),
  );
  bindText("basics", COPY.subject, `ui-person-subject-${owner}`, "identity.pronouns.subject", pronouns.subject, ["identity", "pronouns", "subject"]);
  bindText("basics", COPY.object, `ui-person-object-${owner}`, "identity.pronouns.object", pronouns.object, ["identity", "pronouns", "object"]);
  bindText("basics", COPY.possessive, `ui-person-possessive-${owner}`, "identity.pronouns.possessive", pronouns.possessive, ["identity", "pronouns", "possessive"]);
  bindText(
    "appearance", COPY.appearance, `ui-person-appearance-${owner}`, "embodiment.visible.summary",
    current.embodiment?.visible?.summary, ["embodiment", "visible", "summary"], true,
  );
  bindText(
    "history", COPY.history, `ui-person-history-${owner}`, "knowledge.public_history",
    current.knowledge?.public_history, ["knowledge", "public_history"], true,
  );
  if (kind === "character") {
    bindText(
      "opening", COPY.greeting, `ui-character-greeting-${owner}`, "opening.first_message",
      current.opening?.first_message, ["opening", "first_message"], true,
    );
  }

  for (const [topLevel, value] of Object.entries(current)) {
    let sectionId = GROUPS[topLevel];
    if (!panels.has(sectionId)) sectionId = "additional";
    const section = panels.get(sectionId);
    const schemaNode = createSchemaNode(documentRef, [topLevel], value, onChange, t);
    if (section && schemaNode) section.append(schemaNode);
  }

  const mount = (sectionId, ...children) => panels.get(sectionId)?.append(...children.filter(Boolean));
  const firstInvalid = () => {
    for (const [sectionId, panel] of panels) {
      const invalid = panel.querySelector('[aria-invalid="true"], :invalid');
      if (!invalid) continue;
      activate(sectionId);
      return invalid;
    }
    return null;
  };

  editor.append(nav, panelsHost);
  activate(activeSections.get(key) || ids[0]);
  return Object.freeze({ element: editor, name, activate, firstInvalid, mount, panels });
}
