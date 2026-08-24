export const MODULE_RELEASE = "alpha98-ui12-7eaf6b3481a3";

export const PERSON_SECTION_IDS = Object.freeze([
  "basics", "appearance", "history", "inner-life", "opening",
  "simulation", "story-presence", "quick-start", "additional", "advanced",
]);

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
  quickStart: "Start a Story",
  additional: "Additional fields",
  advanced: "Advanced",
  more: "More",
  moreActive: "More · ${section}",
  name: "Name",
  aliases: "Aliases · one per line",
  subject: "Subject pronoun",
  object: "Object pronoun",
  possessive: "Possessive pronoun",
  appearance: "Visible appearance",
  history: "Public history",
  greeting: "First message",
  stableIdentity: "Stable identity is read-only.",
  identityDetails: "Card identity",
  stableIdentityLabel: "Stable identity",
  startingOutfit: "Starting outfit",
  wornItems: "Worn items",
  outfitCondition: "Outfit condition",
  outfitRegions: "Outfit by body region",
  bodyAndSenses: "Body and senses",
  senses: "Senses",
  build: "Build",
  face: "Face",
  hair: "Hair",
  eyes: "Eyes",
  distinctiveFeatures: "Distinctive features",
  scent: "Scent",
  hiddenCapabilities: "Hidden capabilities",
  extraBodyParts: "Additional body parts",
  bodyAwareness: "Body awareness",
  painSensitivity: "Pain sensitivity",
  fatigueSensitivity: "Fatigue sensitivity",
  pleasureSensitivity: "Pleasure sensitivity",
  abilitiesGroup: "Abilities",
  abilities: "Abilities and skills",
  privateKnowledge: "Private knowledge and access",
  accessTags: "Access tags",
  excludedLore: "Excluded Lore titles",
  privateHistory: "Private history",
  motivation: "Motivation and personality",
  centralDrive: "Central drive",
  driveExpression: "How the drive appears",
  hardBoundary: "Hard boundary",
  traits: "Personality traits",
  values: "Values",
  selfImage: "Self-image and beliefs",
  coping: "Coping patterns",
  stressProfile: "Stress profile",
  learnedAssociations: "Learned associations",
  attentionCapacity: "Attention capacity",
  longTermProjects: "Long-term projects",
  voiceAndSocial: "Voice and social behavior",
  voiceRegister: "Voice register",
  cadence: "Cadence",
  verbosity: "Verbosity",
  verbalMarkers: "Verbal markers",
  voiceNotes: "Voice notes",
  startingAttitudes: "Starting attitudes",
  emotionalState: "Starting emotional state",
  startingMood: "Starting mood",
  moodValence: "Mood valence",
  moodEnergy: "Mood energy",
  currentGoals: "Current goals",
  activeConcerns: "Active concerns",
  stressState: "Stress state",
  comfortState: "Comfort and discomfort",
  moreGreetings: "More greetings",
  additionalGreetings: "Additional greetings",
  behaviorSettings: "Behavior settings",
  characterDetail: "Character detail level",
  creativity: "Creativity",
  samplingOverrides: "Sampling overrides",
  curiosity: "Curiosity",
  backgroundActivity: "Background activity",
  backgroundImportance: "Background importance",
  narrationGroup: "Narration",
  narrationVoice: "Narration voice",
  structuredHelp: "Edit this structured value as JSON. Invalid JSON is kept in the field and is not applied.",
  curiosityHelp: "How readily this Character leaves a proven approach to explore something new. 0 is methodical; 1 is restless.",
  creativityHelp: "Controls response variation for this Character. Lower values are steadier; higher values are less predictable.",
  backgroundActivityHelp: "Allows this Character to receive paid off-screen turns when the Story settings also permit them.",
  capacityHelp: "How many wants and intentions this Character can keep active at once.",
  moodScaleHelp: "Use a value from -1 to 1.",
  unitScaleHelp: "Use a value from 0 to 1.",
  detailBackground: "Background",
  detailSupporting: "Supporting",
  detailMajor: "Major",
  capacityUnset: "Use Story default",
  capacityNarrow: "Narrow",
  capacityFocused: "Focused",
  capacityOrdinary: "Ordinary",
  capacityBroad: "Broad",
  capacityWide: "Wide",
});
// UI_CATALOG_END

const GROUP_SPECS = Object.freeze({
  identity: { section: "basics", label: COPY.identityDetails },
  outfit: { section: "appearance", label: COPY.startingOutfit },
  body: { section: "appearance", label: COPY.bodyAndSenses },
  abilities: { section: "appearance", label: COPY.abilitiesGroup },
  knowledge: { section: "history", label: COPY.privateKnowledge },
  motivation: { section: "inner-life", label: COPY.motivation },
  social: { section: "inner-life", label: COPY.voiceAndSocial },
  state: { section: "inner-life", label: COPY.emotionalState },
  greetings: { section: "opening", label: COPY.moreGreetings },
  behavior: { section: "simulation", label: COPY.behaviorSettings },
  narration: { section: "story-presence", label: COPY.narrationGroup },
});

const FIELD_SPECS = Object.freeze([
  { path: "identity.uid", group: "identity", label: COPY.stableIdentityLabel, control: "text" },
  { path: "initial_outfit.wearing", group: "outfit", label: COPY.wornItems, control: "json" },
  { path: "initial_outfit.state", group: "outfit", label: COPY.outfitCondition, control: "json" },
  { path: "initial_outfit.regions", group: "outfit", label: COPY.outfitRegions, control: "json" },
  { path: "embodiment.senses", group: "body", label: COPY.senses, control: "json" },
  { path: "embodiment.visible.build", group: "body", label: COPY.build, control: "text" },
  { path: "embodiment.visible.face", group: "body", label: COPY.face, control: "text" },
  { path: "embodiment.visible.hair", group: "body", label: COPY.hair, control: "text" },
  { path: "embodiment.visible.eyes", group: "body", label: COPY.eyes, control: "text" },
  { path: "embodiment.visible.distinctive_features", group: "body", label: COPY.distinctiveFeatures, control: "json" },
  { path: "embodiment.scent", group: "body", label: COPY.scent, control: "text" },
  { path: "embodiment.latent", group: "body", label: COPY.hiddenCapabilities, control: "json" },
  { path: "embodiment.extra_parts", group: "body", label: COPY.extraBodyParts, control: "json" },
  { path: "embodiment.interoception.acuity", group: "body", label: COPY.bodyAwareness, control: "number", min: 0, max: 1, step: 0.05, help: COPY.unitScaleHelp },
  { path: "embodiment.interoception.pain_sensitivity", group: "body", label: COPY.painSensitivity, control: "number", min: 0, max: 1, step: 0.05, help: COPY.unitScaleHelp },
  { path: "embodiment.interoception.fatigue_sensitivity", group: "body", label: COPY.fatigueSensitivity, control: "number", min: 0, max: 1, step: 0.05, help: COPY.unitScaleHelp },
  { path: "embodiment.interoception.pleasure_sensitivity", group: "body", label: COPY.pleasureSensitivity, control: "number", min: 0, max: 1, step: 0.05, help: COPY.unitScaleHelp },
  { path: "competence.abilities", group: "abilities", label: COPY.abilities, control: "json" },
  { path: "knowledge.access_tags", group: "knowledge", label: COPY.accessTags, control: "json" },
  { path: "knowledge.excluded_titles", group: "knowledge", label: COPY.excludedLore, control: "json" },
  { path: "knowledge.private_history", group: "knowledge", label: COPY.privateHistory, control: "json" },
  { path: "psychology.drive.essence", group: "motivation", label: COPY.centralDrive, control: "textarea" },
  { path: "psychology.drive.expression", group: "motivation", label: COPY.driveExpression, control: "textarea" },
  { path: "psychology.drive.taboo", group: "motivation", label: COPY.hardBoundary, control: "textarea" },
  { path: "psychology.traits", group: "motivation", label: COPY.traits, control: "json" },
  { path: "psychology.values", group: "motivation", label: COPY.values, control: "json" },
  { path: "psychology.self_model", group: "motivation", label: COPY.selfImage, control: "json" },
  { path: "psychology.coping", group: "motivation", label: COPY.coping, control: "json" },
  { path: "psychology.stress_profile", group: "motivation", label: COPY.stressProfile, control: "json" },
  { path: "psychology.learning", group: "motivation", label: COPY.learnedAssociations, control: "json" },
  { path: "psychology.capacity", group: "motivation", label: COPY.attentionCapacity, control: "select", help: COPY.capacityHelp, options: [
    ["", COPY.capacityUnset], ["narrow", COPY.capacityNarrow], ["focused", COPY.capacityFocused],
    ["ordinary", COPY.capacityOrdinary], ["broad", COPY.capacityBroad], ["wide", COPY.capacityWide],
  ] },
  { path: "psychology.projects", group: "motivation", label: COPY.longTermProjects, control: "json" },
  { path: "social.voice.register", group: "social", label: COPY.voiceRegister, control: "text" },
  { path: "social.voice.cadence", group: "social", label: COPY.cadence, control: "text" },
  { path: "social.voice.verbosity", group: "social", label: COPY.verbosity, control: "text" },
  { path: "social.voice.markers", group: "social", label: COPY.verbalMarkers, control: "json" },
  { path: "social.voice.notes", group: "social", label: COPY.voiceNotes, control: "textarea" },
  { path: "social.baseline_stances", group: "social", label: COPY.startingAttitudes, control: "json" },
  { path: "initial_state.mood.label", group: "state", label: COPY.startingMood, control: "text" },
  { path: "initial_state.mood.valence", group: "state", label: COPY.moodValence, control: "number", min: -1, max: 1, step: 0.05, help: COPY.moodScaleHelp },
  { path: "initial_state.mood.arousal", group: "state", label: COPY.moodEnergy, control: "number", min: 0, max: 1, step: 0.05, help: COPY.unitScaleHelp },
  { path: "initial_state.goals", group: "state", label: COPY.currentGoals, control: "json" },
  { path: "initial_state.active_concerns", group: "state", label: COPY.activeConcerns, control: "json" },
  { path: "initial_state.stress", group: "state", label: COPY.stressState, control: "json" },
  { path: "initial_state.hedonic", group: "state", label: COPY.comfortState, control: "json" },
  { path: "opening.greetings", group: "greetings", label: COPY.additionalGreetings, control: "json" },
  { path: "simulation.tier", group: "behavior", label: COPY.characterDetail, control: "select", options: [
    ["bg", COPY.detailBackground], ["mid", COPY.detailSupporting], ["major", COPY.detailMajor],
  ] },
  { path: "simulation.temperature", group: "behavior", label: COPY.creativity, control: "number", min: 0, step: 0.05, help: COPY.creativityHelp },
  { path: "simulation.sampler", group: "behavior", label: COPY.samplingOverrides, control: "json" },
  { path: "simulation.curiosity", group: "behavior", label: COPY.curiosity, control: "number", min: 0, max: 1, step: 0.05, help: COPY.curiosityHelp },
  { path: "simulation.offscreen_agent", group: "behavior", label: COPY.backgroundActivity, control: "checkbox", help: COPY.backgroundActivityHelp },
  { path: "simulation.offscreen_importance", group: "behavior", label: COPY.backgroundImportance, control: "select", options: [
    ["background", COPY.detailBackground], ["supporting", COPY.detailSupporting], ["major", COPY.detailMajor],
  ] },
  { path: "narration.voice_setting", group: "narration", label: COPY.narrationVoice, control: "textarea" },
]);

const REGISTERED_PATHS = new Set(FIELD_SPECS.map(spec => spec.path));
const AUXILIARY_SECTION_IDS = new Set(["quick-start", "additional", "advanced"]);

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

function field(documentRef, labelText, control, helpText = "") {
  const wrapper = node(documentRef, "div", "ui-authoring-field");
  const label = node(documentRef, "label", "ui-authoring-field__label", labelText);
  label.htmlFor = control.id;
  wrapper.append(label, control);
  if (helpText) {
    const help = node(documentRef, "p", "ui-field__help", helpText);
    help.id = `${control.id}-help`;
    control.setAttribute("aria-describedby", help.id);
    wrapper.append(help);
  }
  return wrapper;
}

function textControl(documentRef, id, name, value, long = false) {
  const control = node(documentRef, long ? "textarea" : "input", "ui-field__control");
  if (long) control.classList.add("ui-authoring-form__long");
  if (!long) control.type = "text";
  control.id = id;
  control.name = name;
  control.value = String(value ?? "");
  return control;
}

function humanize(value) {
  return String(value || "").replace(/_/g, " ").replace(/^./, letter => letter.toUpperCase());
}

function createTechnicalSchemaNode(documentRef, path, value, onChange, t) {
  const dotted = path.join(".");
  if (PRIMARY_PATHS.has(dotted)) return null;
  if (value && typeof value === "object" && !Array.isArray(value)) {
    const details = node(documentRef, "details", "ui-authoring-schema__group");
    details.dataset.schemaPath = dotted;
    details.append(node(documentRef, "summary", "ui-authoring-field__label", humanize(path.at(-1))));
    const children = Object.entries(value)
      .map(([key, child]) => createTechnicalSchemaNode(documentRef, [...path, key], child, onChange, t))
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
    control = node(documentRef, "input", "ui-field__control");
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

function pathValue(value, dotted) {
  let cursor = value;
  for (const part of dotted.split(".")) {
    if (!cursor || typeof cursor !== "object" || !Object.hasOwn(cursor, part)) {
      return { found: false, value: undefined };
    }
    cursor = cursor[part];
  }
  return { found: true, value: cursor };
}

function hasRegisteredDescendant(dotted) {
  const prefix = `${dotted}.`;
  return FIELD_SPECS.some(spec => spec.path.startsWith(prefix));
}

function hasAdditionalValue(path, value) {
  const dotted = path.join(".");
  if (PRIMARY_PATHS.has(dotted) || REGISTERED_PATHS.has(dotted)) return false;
  if (value && typeof value === "object" && !Array.isArray(value)
      && hasRegisteredDescendant(dotted)) {
    return Object.entries(value).some(([key, child]) => hasAdditionalValue([...path, key], child));
  }
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return Object.keys(value).length > 0;
  }
  return true;
}

function createAdditionalNode(documentRef, path, value, onChange, t) {
  const dotted = path.join(".");
  if (PRIMARY_PATHS.has(dotted) || REGISTERED_PATHS.has(dotted)) return null;
  if (value && typeof value === "object" && !Array.isArray(value)
      && hasRegisteredDescendant(dotted)) {
    const details = node(documentRef, "details", "ui-authoring-schema__group");
    details.dataset.schemaPath = dotted;
    details.append(node(documentRef, "summary", "ui-authoring-field__label", humanize(path.at(-1))));
    const children = Object.entries(value)
      .map(([key, child]) => createAdditionalNode(documentRef, [...path, key], child, onChange, t))
      .filter(Boolean);
    if (!children.length) return null;
    details.append(...children);
    return details;
  }
  return createTechnicalSchemaNode(documentRef, path, value, onChange, t);
}

function createSemanticField(documentRef, spec, value, onChange, t) {
  const path = spec.path.split(".");
  const id = `ui-schema-${spec.path.replace(/[^a-zA-Z0-9_-]/g, "-")}`;
  let control;
  if (spec.control === "json") {
    control = node(documentRef, "textarea", "ui-field__control ui-authoring-schema__json");
    control.value = JSON.stringify(value, null, 2);
    control.addEventListener("change", () => {
      try {
        const parsed = JSON.parse(control.value);
        if (Array.isArray(value) !== Array.isArray(parsed)
            || (value && typeof value === "object" && !Array.isArray(value)
              && (!parsed || typeof parsed !== "object" || Array.isArray(parsed)))) {
          throw new Error("structured value required");
        }
        control.removeAttribute("aria-invalid");
        onChange(path, parsed);
      } catch {
        control.setAttribute("aria-invalid", "true");
      }
    });
  } else if (spec.control === "checkbox") {
    control = node(documentRef, "input");
    control.type = "checkbox";
    control.checked = Boolean(value);
    control.addEventListener("change", () => onChange(path, control.checked));
  } else if (spec.control === "number") {
    control = node(documentRef, "input", "ui-field__control");
    control.type = "number";
    control.value = String(value);
    if (spec.min !== undefined) control.min = String(spec.min);
    if (spec.max !== undefined) control.max = String(spec.max);
    control.step = String(spec.step ?? "any");
    control.addEventListener("input", () => {
      if (control.value !== "" && Number.isFinite(Number(control.value))) {
        onChange(path, Number(control.value));
      }
    });
  } else if (spec.control === "select") {
    control = node(documentRef, "select", "ui-field__control");
    for (const [optionValue, optionLabel] of spec.options || []) {
      const option = node(documentRef, "option", "", t(optionLabel));
      option.value = optionValue;
      option.selected = String(value ?? "") === optionValue;
      control.append(option);
    }
    control.addEventListener("change", () => onChange(path, control.value));
  } else {
    control = textControl(
      documentRef, id, spec.path, value,
      spec.control === "textarea" || String(value ?? "").length > 100,
    );
    control.addEventListener("input", () => onChange(path, control.value));
  }
  control.id = id;
  control.name = spec.path;
  control.dataset.schemaPath = spec.path;
  if (spec.path === "identity.uid") {
    control.disabled = true;
    control.setAttribute("aria-description", t(COPY.stableIdentity));
  }
  const help = spec.control === "json" ? COPY.structuredHelp : spec.help;
  return field(documentRef, t(spec.label), control, help ? t(help) : "");
}

function applicableSectionIds(current, kind, mode) {
  const base = kind === "character"
    ? ["basics", "appearance", "history", "inner-life", "opening", "simulation"]
    : ["basics", "appearance", "history", "story-presence"];
  if (kind === "character" && mode === "edit") base.push("quick-start");
  const hasAdditional = Object.entries(current)
    .some(([key, value]) => hasAdditionalValue([key], value));
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
  const nav = node(documentRef, "nav", "ui-person-editor__nav");
  nav.setAttribute("aria-label", t(COPY.sections));
  const tabsHost = node(documentRef, "div", "ui-person-editor__tabs");
  tabsHost.setAttribute("role", "tablist");
  const more = node(documentRef, "details", "ui-person-editor__more");
  const moreSummary = node(documentRef, "summary", "ui-person-editor__more-summary", t(COPY.more));
  const moreMenu = node(documentRef, "div", "ui-person-editor__more-menu");
  more.append(moreSummary, moreMenu);
  const panelsHost = node(documentRef, "div", "ui-person-editor__panels");
  panelsHost.dataset.personScrollRegion = "true";
  const panels = new Map();
  const buttons = new Map();
  const key = String(owner || `${kind}:new`);

  for (const sectionId of ids) {
    const button = node(documentRef, "button", "ui-person-editor__tab", t(LABELS[sectionId]));
    const panel = node(documentRef, "section", "ui-person-editor__panel");
    const suffix = `${key}-${sectionId}`.replace(/[^a-zA-Z0-9_-]/g, "-");
    button.type = "button";
    button.id = `ui-person-tab-${suffix}`;
    button.setAttribute("aria-controls", `ui-person-panel-${suffix}`);
    if (AUXILIARY_SECTION_IDS.has(sectionId)) {
      button.classList.add("ui-person-editor__more-button");
      moreMenu.append(button);
    } else {
      button.setAttribute("role", "tab");
      tabsHost.append(button);
    }
    panel.id = `ui-person-panel-${suffix}`;
    panel.dataset.editorSection = sectionId;
    panel.setAttribute("role", "tabpanel");
    panel.setAttribute("aria-labelledby", button.id);
    panel.append(node(documentRef, "h3", "ui-heading ui-heading--3", t(LABELS[sectionId])));
    panelsHost.append(panel);
    buttons.set(sectionId, button);
    panels.set(sectionId, panel);
  }
  nav.append(tabsHost);
  if (moreMenu.childElementCount) nav.append(more);

  const activate = (requested, focusTab = false) => {
    const sectionId = panels.has(requested) ? requested : ids[0];
    for (const id of ids) {
      const active = id === sectionId;
      const button = buttons.get(id);
      const panel = panels.get(id);
      if (AUXILIARY_SECTION_IDS.has(id)) {
        if (active) button.setAttribute("aria-current", "page");
        else button.removeAttribute("aria-current");
      } else {
        button.setAttribute("aria-selected", String(active));
        button.tabIndex = active ? 0 : -1;
      }
      panel.hidden = !active;
    }
    const auxiliaryActive = AUXILIARY_SECTION_IDS.has(sectionId);
    moreSummary.textContent = auxiliaryActive
      ? t(COPY.moreActive).replace("${section}", t(LABELS[sectionId]))
      : t(COPY.more);
    moreSummary.dataset.state = auxiliaryActive ? "selected" : "idle";
    if (auxiliaryActive) more.open = false;
    rememberActive(key, sectionId);
    const activeButton = buttons.get(sectionId);
    if (focusTab) activeButton?.focus();
    const visibleAnchor = auxiliaryActive ? moreSummary : activeButton;
    globalThis.queueMicrotask?.(() => visibleAnchor?.scrollIntoView({
      block: "nearest", inline: "nearest",
    }));
    return sectionId;
  };

  const peerIds = ids.filter(sectionId => !AUXILIARY_SECTION_IDS.has(sectionId));
  ids.forEach(sectionId => {
    const button = buttons.get(sectionId);
    button.addEventListener("click", () => activate(sectionId));
    if (AUXILIARY_SECTION_IDS.has(sectionId)) return;
    const index = peerIds.indexOf(sectionId);
    button.addEventListener("keydown", event => {
      let next = null;
      if (event.key === "ArrowDown" || event.key === "ArrowRight") next = (index + 1) % peerIds.length;
      if (event.key === "ArrowUp" || event.key === "ArrowLeft") next = (index - 1 + peerIds.length) % peerIds.length;
      if (event.key === "Home") next = 0;
      if (event.key === "End") next = peerIds.length - 1;
      if (next === null) return;
      event.preventDefault();
      activate(peerIds[next], true);
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

  const fieldGroups = new Map();
  for (const spec of FIELD_SPECS) {
    const stored = pathValue(current, spec.path);
    if (!stored.found) continue;
    const groupSpec = GROUP_SPECS[spec.group];
    const section = panels.get(groupSpec?.section);
    if (!section) continue;
    let group = fieldGroups.get(spec.group);
    if (!group) {
      group = node(documentRef, "section", "ui-authoring-field-group");
      group.append(node(documentRef, "h4", "ui-authoring-field-group__title", t(groupSpec.label)));
      fieldGroups.set(spec.group, group);
      section.append(group);
    }
    group.append(createSemanticField(documentRef, spec, stored.value, onChange, t));
  }

  const additionalPanel = panels.get("additional");
  if (additionalPanel) {
    for (const [topLevel, value] of Object.entries(current)) {
      const schemaNode = createAdditionalNode(documentRef, [topLevel], value, onChange, t);
      if (schemaNode) additionalPanel.append(schemaNode);
    }
  }

  const mount = (sectionId, ...children) => panels.get(sectionId)?.append(...children.filter(Boolean));
  const firstInvalid = () => {
    for (const [sectionId, panel] of panels) {
      const invalid = panel.querySelector('[aria-invalid="true"], :invalid');
      if (!invalid) continue;
      activate(sectionId);
      let disclosure = invalid.closest("details");
      while (disclosure && panel.contains(disclosure)) {
        disclosure.open = true;
        disclosure = disclosure.parentElement?.closest("details");
      }
      return invalid;
    }
    return null;
  };

  editor.append(nav, panelsHost);
  activate(activeSections.get(key) || ids[0]);
  return Object.freeze({ element: editor, name, activate, firstInvalid, mount, panels });
}
