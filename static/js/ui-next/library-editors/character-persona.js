export const MODULE_RELEASE = "alpha98-ui7-516e7c3e67a7";

import { buildQuickStartLivedLocation, mountLivedLocationFields } from "../lived-location.js?release=alpha98-ui7-516e7c3e67a7";
import { createPersonSectionEditor } from "./person-sections.js?release=alpha98-ui7-516e7c3e67a7";

const quickStartDrafts = new Map();

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
  discardTitle: "Discard changes to ${name}?",
  discardHelp: "This removes the local draft for ${name} and restores the last version saved to Library.",
  keepEditing: "Keep editing",
  discardChanges: "Discard local changes",
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
  more: "More",
  character: "Character",
  persona: "Persona",
  editHelp: "Changes remain a local draft until you save.",
  createHelp: "Build the complete reusable card, then save it to Library.",
  quickStartHelp: "Save this card and open a new Story from one of its greetings.",
  quickStartBoundary: "The place may publish public resident cards. This Character's generated past is handed only to this Character.",
  lore: "Lore",
  noLore: "No Lore selected",
  untitledLore: "Untitled Lore",
  alreadyKnown: "The Character already knows the Persona",
  livedLocation: "Begin in a lived location",
  playAs: "Play as",
  openingGreeting: "Opening greeting",
  startStory: "Save and start Story",
  quickStartUnavailable: "Add a greeting and create a Persona to quick-start this Character.",
  storyCard: "Story Character card",
  storyCardHelp: "This card applies only to ${story}. Live mood, stress, memories, relationships, and physical state stay intact.",
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

function availableLibraryRows(services, kind) {
  const library = services.store.getSnapshot().library || {};
  const bootstrapRows = kind === "persona" ? library.personas : library.lorebooks;
  const rows = [
    ...(Array.isArray(bootstrapRows) ? bootstrapRows.map(item => ({ ...item, kind })) : []),
    ...(Array.isArray(library.items) ? library.items : []),
  ];
  const seen = new Set();
  return rows.filter(item => {
    const id = Number(item?.id);
    if (item?.kind !== kind || item.archived || !Number.isSafeInteger(id) || seen.has(id)) return false;
    seen.add(id);
    return true;
  });
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
  const control = node(documentRef, long ? "textarea" : "input", "ui-field__control");
  if (long) control.classList.add("ui-authoring-form__long");
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
  let save;
  const form = node(documentRef, "form", "ui-authoring-form");
  form.dataset.personEditor = state.kind;
  const editorHeader = node(documentRef, "header", "ui-authoring-form__header");
  editorHeader.append(node(
    documentRef, "p", "ui-authoring-form__eyebrow",
    services.localizer.t(
      state.mode === "story-card" ? COPY.storyCard
        : state.kind === "character" ? COPY.character : COPY.persona,
    ),
  ));
  const editorTitle = node(
    documentRef, "h2", "ui-heading ui-heading--2",
    String(state.draft.identity?.name || ""),
  );
  editorHeader.append(
    editorTitle,
    node(
      documentRef, "p", "ui-muted",
      state.mode === "story-card"
        ? services.localizer.t(COPY.storyCardHelp).replace(
          "${story}", state.overview?.story_name || "this Story",
        )
        : services.localizer.t(state.mode === "create" ? COPY.createHelp : COPY.editHelp),
    ),
  );
  const update = (path, value) => {
    current = setPath(current, path, value);
    if (advanced) advanced.value = JSON.stringify(current, null, 2);
    services.authoring.stage(current);
  };
  const sections = createPersonSectionEditor({
    document: documentRef,
    current,
    kind: state.kind,
    mode: state.mode,
    owner: state.owner || `${state.kind}:${state.id || "new"}`,
    t: services.localizer.t,
    onChange: update,
    onNameChange(value) {
      editorTitle.textContent = value;
      if (save) save.disabled = state.status === "saving" || !value.trim();
    },
  });
  const name = sections.name;
  form.append(editorHeader, sections.element);
  const tools = node(documentRef, "section", "ui-authoring-tools");
  tools.append(node(documentRef, "h3", "ui-heading ui-heading--3", services.localizer.t(COPY.tools)));
  const brief = textControl(
    documentRef, `ui-person-tool-brief-${state.id || "new"}`, "authoring_brief", "", true,
  );
  tools.append(field(documentRef, services.localizer.t(COPY.toolBrief), brief));
  const toolActions = node(documentRef, "div", "ui-authoring-form__actions ui-action-cluster");
  toolActions.setAttribute("role", "toolbar");
  toolActions.setAttribute("aria-label", services.localizer.t(COPY.tools));
  const more = node(documentRef, "details", "ui-action-more");
  more.append(node(documentRef, "summary", "ui-button ui-button--quiet", services.localizer.t(COPY.more)));
  const moreBody = node(documentRef, "div", "ui-action-more__menu");
  more.append(moreBody);
  const toolButton = (label, action, secondary = false) => {
    const control = node(documentRef, "button", "ui-button ui-button--quiet", services.localizer.t(label));
    control.type = "button";
    control.disabled = state.status === "previewing";
    control.addEventListener("click", () => action(brief.value.trim()));
    (secondary ? moreBody : toolActions).append(control);
  };
  if (state.mode === "create") {
    toolButton(COPY.generate, value => services.authoring.previewGenerate(value));
  } else {
    toolButton(COPY.appearanceFill, value => services.authoring.previewAppearance(value));
    if (state.kind === "character") {
      toolButton(COPY.psychologyFill, value => services.authoring.previewPsychology(value));
      toolButton(COPY.greetingGenerate, value => services.authoring.previewGreeting(value), true);
      toolButton(COPY.greetingRecover, () => services.authoring.previewGreetingRecovery(), true);
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
  if (moreBody.childElementCount) toolActions.append(more);
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
  sections.mount(state.kind === "character" ? "opening" : "story-presence", tools);
  if (state.kind === "character" && state.mode === "edit") {
    const personas = availableLibraryRows(services, "persona");
    const greetings = Array.isArray(current.opening?.greetings)
      ? current.opening.greetings : [];
    const quick = node(documentRef, "section", "ui-authoring-quick-start");
    quick.append(node(documentRef, "p", "ui-muted", services.localizer.t(COPY.quickStartHelp)));
    if (!personas.length || !greetings.length) {
      quick.append(node(documentRef, "p", "ui-muted", services.localizer.t(COPY.quickStartUnavailable)));
    } else {
      const quickKey = String(state.owner || `character:${state.id}`);
      const quickDraft = quickStartDrafts.get(quickKey) || {
        lorebookId: "", alreadyKnown: false,
        livedLocation: { enabled: false, brief: "", horizonHours: 0, characterHistories: [{ key: `quick:${state.id}`, mode: "auto", brief: "" }] },
      };
      quickStartDrafts.set(quickKey, quickDraft);
      const persona = node(documentRef, "select", "ui-field__control");
      persona.id = `ui-quick-persona-${state.id}`;
      for (const item of personas) {
        const option = node(documentRef, "option", "", item.name || services.localizer.t(COPY.persona));
        option.value = String(item.id);
        persona.append(option);
      }
      const greeting = node(documentRef, "select", "ui-field__control");
      greeting.id = `ui-quick-greeting-${state.id}`;
      greetings.forEach((entry, index) => {
        const prose = String(entry?.prose || current.opening?.first_message || "").replace(/\s+/g, " ").trim();
        const option = node(documentRef, "option", "", `${index + 1} · ${prose.slice(0, 80)}`);
        option.value = String(index);
        greeting.append(option);
      });
      const lore = node(documentRef, "select", "ui-field__control");
      const noLore = node(documentRef, "option", "", services.localizer.t(COPY.noLore));
      noLore.value = "";
      lore.append(noLore);
      availableLibraryRows(services, "lore")
        .forEach(item => {
          const option = node(documentRef, "option", "", item.name || services.localizer.t(COPY.untitledLore));
          option.value = String(item.id);
          option.selected = String(item.id) === String(quickDraft.lorebookId);
          lore.append(option);
        });
      lore.addEventListener("change", () => { quickDraft.lorebookId = lore.value; });
      const known = node(documentRef, "label", "ui-authoring-quick-start__known");
      const knownInput = documentRef.createElement("input");
      knownInput.type = "checkbox";
      knownInput.checked = Boolean(quickDraft.alreadyKnown);
      knownInput.addEventListener("change", () => { quickDraft.alreadyKnown = knownInput.checked; });
      known.append(knownInput, documentRef.createTextNode(` ${services.localizer.t(COPY.alreadyKnown)}`));
      const livedHost = node(documentRef, "div", "ui-authoring-quick-start__location");
      mountLivedLocationFields({
        document: documentRef, target: livedHost, value: quickDraft.livedLocation,
        characters: [{ key: `quick:${state.id}`, name: current.identity?.name || current.name || "Character" }],
        title: "Begin in a lived location",
        onChange(value) { quickDraft.livedLocation = value; },
      });
      const start = node(documentRef, "button", "ui-button ui-button--primary", services.localizer.t(COPY.startStory));
      start.type = "button";
      start.disabled = state.status === "starting-story";
      start.addEventListener("click", () => services.authoring.quickStart({
        personaId: Number(persona.value),
        greetingIndex: Number(greeting.value),
        lorebookId: lore.value ? Number(lore.value) : null,
        alreadyKnown: knownInput.checked,
        language: services.store.getSnapshot().settings?.data?.ui_language || "en",
        livedLocation: buildQuickStartLivedLocation(quickDraft.livedLocation),
      }));
      quick.append(
        field(documentRef, services.localizer.t(COPY.playAs), persona),
        field(documentRef, services.localizer.t(COPY.openingGreeting), greeting),
        field(documentRef, services.localizer.t(COPY.lore), lore),
        known,
        livedHost,
        node(documentRef, "p", "ui-muted", services.localizer.t(COPY.quickStartBoundary)),
        start,
      );
    }
    sections.mount("quick-start", quick);
  }
  const disclosure = node(documentRef, "div", "ui-authoring-advanced");
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
      services.authoring.stage(parsed, { render: true });
    } catch {
      advanced.setAttribute("aria-invalid", "true");
      feedback.textContent = services.localizer.t(COPY.invalidJson);
      feedback.dataset.tone = "danger";
      advanced.focus();
    }
  });
  disclosure.append(advanced, feedback, applyAdvanced);
  sections.mount("advanced", disclosure);
  const actions = node(documentRef, "div", "ui-authoring-form__actions ui-action-cluster");
  actions.setAttribute("role", "toolbar");
  const discard = node(documentRef, "button", "ui-button ui-button--quiet", services.localizer.t(COPY.discard));
  discard.type = "button";
  discard.disabled = state.status === "saving";
  discard.addEventListener("click", () => {
    const nameValue = String(current.identity?.name || "this draft").trim() || "this draft";
    const titleText = services.localizer.t(COPY.discardTitle).replace("${name}", nameValue);
    const helpText = services.localizer.t(COPY.discardHelp).replace("${name}", nameValue);
    const dialog = node(documentRef, "dialog", "ui-dialog ui-confirmation ui-person-discard-dialog");
    const suffix = String(state.owner || `${state.kind}:${state.id || "new"}`)
      .replace(/[^a-zA-Z0-9_-]/g, "-");
    const title = node(documentRef, "h2", "ui-heading ui-heading--2", titleText);
    title.id = `ui-person-discard-title-${suffix}`;
    dialog.setAttribute("aria-labelledby", title.id);
    dialog.append(title, node(documentRef, "p", "ui-muted", helpText));
    const dialogActions = node(documentRef, "div", "ui-person-discard-dialog__actions");
    const keep = node(documentRef, "button", "ui-button ui-button--quiet", services.localizer.t(COPY.keepEditing));
    keep.type = "button";
    const confirm = node(
      documentRef, "button", "ui-button ui-button--destructive",
      services.localizer.t(COPY.discardChanges),
    );
    confirm.type = "button";
    dialogActions.append(keep, confirm);
    dialog.append(dialogActions);
    const close = returnValue => {
      if (dialog.open) dialog.close(returnValue);
      else dialog.remove();
    };
    keep.addEventListener("click", () => close("cancel"));
    confirm.addEventListener("click", () => {
      close("discard");
      services.authoring.discard();
    });
    dialog.addEventListener("cancel", event => {
      event.preventDefault();
      close("cancel");
    });
    dialog.addEventListener("close", () => dialog.remove(), { once: true });
    (documentRef.querySelector("[data-shell-overlay-host]") || documentRef.body).append(dialog);
    dialog.showModal();
    keep.focus();
  });
  save = node(
    documentRef, "button", "ui-button ui-button--primary",
    services.localizer.t(state.kind === "character" ? COPY.saveCharacter : COPY.savePersona),
  );
  save.type = "submit";
  save.disabled = state.status === "saving" || !String(current.identity?.name || "").trim();
  actions.append(discard, save);
  sections.element.append(actions);
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (!String(current.identity?.name || "").trim()) {
      name.setAttribute("aria-invalid", "true");
    }
    const invalid = sections.firstInvalid();
    if (invalid) {
      invalid.focus();
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
  const input = node(documentRef, "input", "ui-field__control");
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
