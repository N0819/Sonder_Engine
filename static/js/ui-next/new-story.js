export const MODULE_RELEASE = "alpha98-ui4-842dd802b09f";

// UI_CATALOG_START: Alpha 9.8 New Story copy.
const ALPHA98_NEW_STORY_COPY = Object.freeze([
  "Prepare a lived location",
  "Lived location",
  "Character pasts",
  "View incomplete Story",
  "Choose no more than 16 Characters when preparing a lived location.",
]);
// UI_CATALOG_END

import {
  buildLivedLocationRequest,
  generateLivedLocation,
  mountLivedLocationFields,
  normalizeLivedLocation,
} from "./lived-location.js?release=alpha98-ui4-842dd802b09f";

const DRAFT_TYPE = "new-story";
const DRAFT_OWNER = "current";

function node(documentRef, tag, className = "", text = "") {
  const element = documentRef.createElement(tag);
  if (className) element.className = className;
  if (text) element.textContent = text;
  return element;
}

function icon(documentRef, name) {
  const svg = documentRef.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", "ui-icon");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");
  const use = documentRef.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", `/static/assets/icons/sonder-icons.svg?release=${MODULE_RELEASE}#icon-${name}`);
  svg.append(use);
  return svg;
}

function defaultLanguage(settings) {
  const packs = (settings?.language_packs || []).filter(pack => pack.story);
  const preferred = settings?.ui_language || "en";
  return packs.some(pack => pack.id === preferred) ? preferred : (packs[0]?.id || "en");
}

function emptyDraft(settings) {
  return {
    route: "",
    step: "choice",
    name: "",
    scenario: "",
    language: defaultLanguage(settings),
    personaId: "",
    generatePersona: false,
    personaBrief: "",
    characterIds: [],
    characterBriefs: [""],
    loreIds: [],
    preparedPersonaId: null,
    preparedCharacterIds: [],
    cardWarnings: [],
    cardWarningsReviewed: false,
    livedLocation: normalizeLivedLocation(),
  };
}

function restoreDraft(services, settings) {
  const fallback = emptyDraft(settings);
  try {
    const raw = services.localState.getDraft(DRAFT_TYPE, DRAFT_OWNER);
    if (!raw) return { state: fallback, restored: false };
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("invalid");
    return {
      state: {
        ...fallback,
        ...parsed,
        characterIds: Array.isArray(parsed.characterIds) ? parsed.characterIds : [],
        characterBriefs: Array.isArray(parsed.characterBriefs) && parsed.characterBriefs.length
          ? parsed.characterBriefs : [""],
        loreIds: Array.isArray(parsed.loreIds) ? parsed.loreIds : [],
        preparedCharacterIds: Array.isArray(parsed.preparedCharacterIds) ? parsed.preparedCharacterIds : [],
        cardWarnings: Array.isArray(parsed.cardWarnings) ? parsed.cardWarnings : [],
        livedLocation: normalizeLivedLocation(parsed.livedLocation),
      },
      restored: true,
    };
  } catch {
    services.localState.clearDraft(DRAFT_TYPE, DRAFT_OWNER);
    return { state: fallback, restored: false };
  }
}

function field(documentRef, labelText, control, help = "") {
  const label = node(documentRef, "label", "ui-new-story__field");
  label.append(node(documentRef, "span", "ui-field__label", labelText), control);
  if (help) label.append(node(documentRef, "small", "ui-muted", help));
  return label;
}

function hasGenerationModel(settings) {
  const model = settings?.agent_models?.default;
  return Boolean(model?.provider && model?.model);
}

function routeCard(documentRef, index, title, detail, options = {}) {
  const button = node(documentRef, "button", `ui-new-story__route${options.recommended ? " is-recommended" : ""}`);
  button.type = "button";
  button.setAttribute("aria-label", title);
  button.append(
    node(documentRef, "span", "ui-new-story__choice-index", String(index).padStart(2, "0")),
    node(documentRef, "strong", "", title),
    node(documentRef, "small", "", detail),
  );
  if (options.recommended) button.append(node(documentRef, "span", "ui-new-story__tag", "Recommended"));
  return button;
}

function checkboxRow(documentRef, labelText, checked, onChange, description = "") {
  const label = node(documentRef, "label", "ui-new-story__check");
  const input = documentRef.createElement("input");
  input.type = "checkbox";
  input.checked = checked;
  input.addEventListener("change", () => onChange(input.checked));
  const copy = node(documentRef, "span", "");
  copy.append(node(documentRef, "strong", "", labelText));
  if (description) copy.append(node(documentRef, "small", "", description));
  label.append(input, copy);
  return label;
}

export function openNewStory(options = {}) {
  const documentRef = options.document || document;
  const { services } = options;
  if (!services?.apiClient || !services?.localState || !services?.router || !services?.store) {
    throw new Error("New Story requires current API, draft, route, and state services.");
  }
  documentRef.querySelector("[data-new-story-dialog]")?.close("replaced");
  const settings = services.store.getSnapshot().settings?.data || {};
  const library = () => services.store.getSnapshot().library || {};
  const recovered = restoreDraft(services, settings);
  const state = recovered.state;
  let restored = recovered.restored;
  let creating = false;

  const dialog = node(documentRef, "dialog", "ui-new-story");
  dialog.dataset.newStoryDialog = "true";
  dialog.setAttribute("aria-labelledby", "ui-new-story-title");
  const header = node(documentRef, "header", "ui-new-story__header");
  const title = node(documentRef, "strong", "", "New story");
  title.id = "ui-new-story-title";
  const close = node(documentRef, "button", "ui-button ui-button--quiet ui-button--icon");
  close.append(icon(documentRef, "close"));
  close.type = "button";
  close.setAttribute("aria-label", "Close New story");
  close.addEventListener("click", () => dialog.close("close"));
  header.append(title, close);
  const body = node(documentRef, "div", "ui-new-story__body");
  dialog.append(header, body);
  (documentRef.querySelector("[data-shell-overlay-host]") || documentRef.body).append(dialog);

  const persist = () => services.localState.setDraft(DRAFT_TYPE, DRAFT_OWNER, JSON.stringify(state));
  const mountLocation = (target, characters = []) => mountLivedLocationFields({
    document: documentRef,
    target,
    value: state.livedLocation,
    characters,
    onChange(value) {
      state.livedLocation = value;
      persist();
    },
  });
  const setStep = (step, route = state.route) => {
    state.step = step;
    state.route = route;
    persist();
    render();
  };
  const heading = (eyebrow, text, detail) => {
    const head = node(documentRef, "div", "ui-new-story__stage-head");
    head.append(
      node(documentRef, "p", "ui-new-story__eyebrow", eyebrow),
      node(documentRef, "h2", "ui-heading ui-heading--2", text),
      node(documentRef, "p", "ui-muted", detail),
    );
    return head;
  };
  const backButton = (text, next) => {
    const button = node(documentRef, "button", "ui-button ui-button--quiet", text);
    button.type = "button";
    button.addEventListener("click", next);
    return button;
  };
  const clearDraft = () => {
    services.localState.clearDraft(DRAFT_TYPE, DRAFT_OWNER);
    Object.assign(state, emptyDraft(settings));
    restored = false;
  };
  const renderRecovered = () => {
    if (!restored || state.step === "choice") return;
    const notice = node(documentRef, "div", "ui-new-story__resume");
    notice.append(
      node(documentRef, "strong", "", "Recovered setup draft"),
      node(documentRef, "span", "", "This stage was restored from this browser."),
    );
    const discard = node(documentRef, "button", "ui-button ui-button--quiet", "Discard setup draft");
    discard.type = "button";
    discard.addEventListener("click", () => { clearDraft(); render(); });
    notice.append(discard);
    body.append(notice);
  };

  const renderChoice = () => {
    body.append(heading(
      "New story",
      "Choose how to begin",
      "Each route creates the same complete Sonder story. The difference is how much material you prepare before entering Play.",
    ));
    if (restored && state.route) {
      const notice = node(documentRef, "div", "ui-new-story__resume");
      notice.append(
        node(documentRef, "strong", "", "Your setup draft is still here."),
        node(documentRef, "span", "", "Resume where you stopped or discard only this setup draft."),
      );
      const resume = node(documentRef, "button", "ui-button ui-button--primary", "Resume setup");
      resume.type = "button";
      resume.addEventListener("click", () => setStep(state.step || "details"));
      const discard = node(documentRef, "button", "ui-button ui-button--quiet", "Discard setup draft");
      discard.type = "button";
      discard.addEventListener("click", () => { clearDraft(); render(); });
      notice.append(resume, discard);
      body.append(notice);
    }
    const routes = node(documentRef, "div", "ui-new-story__routes");
    const describe = routeCard(documentRef, 1, "Describe a story", "Tell Sonder the premise, then review your persona and cast.", { recommended: true });
    const fromLibrary = routeCard(documentRef, 2, "Use my Library", "Start from personas, characters, and lore you already saved.");
    const blank = routeCard(documentRef, 3, "Start blank", "Open an empty story and configure it as you go.");
    describe.addEventListener("click", () => setStep("details", "describe"));
    fromLibrary.addEventListener("click", () => setStep("details", "library"));
    blank.addEventListener("click", () => setStep("details", "blank"));
    routes.append(describe, fromLibrary, blank);
    body.append(routes);
  };

  const renderDetails = () => {
    body.append(heading(
      "Step 1 of 3",
      state.route === "blank" ? "Name the blank story" : "Set the story direction",
      state.route === "blank"
        ? "Both fields are optional. You can change them later in Story tools."
        : "Give the story a name and opening situation. You can refine both before creation.",
    ));
    const form = node(documentRef, "form", "ui-new-story__form");
    const name = node(documentRef, "input", "ui-input");
    name.type = "text";
    name.value = state.name;
    name.maxLength = 240;
    name.addEventListener("input", () => { state.name = name.value; persist(); });
    const scenario = node(documentRef, "textarea", "ui-textarea ui-new-story__scenario");
    scenario.value = state.scenario;
    scenario.addEventListener("input", () => { state.scenario = scenario.value; persist(); });
    const language = node(documentRef, "select", "ui-select");
    language.setAttribute("aria-label", "Story language");
    const packs = (settings.language_packs || []).filter(pack => pack.story);
    (packs.length ? packs : [{ id: "en", native_name: "English" }]).forEach(pack => {
      const option = node(documentRef, "option", "", pack.native_name || pack.name || pack.id);
      option.value = pack.id;
      option.selected = pack.id === state.language;
      language.append(option);
    });
    language.addEventListener("change", () => { state.language = language.value; persist(); });
    form.append(
      field(documentRef, "Story name", name, "Optional; defaults to New story."),
      field(documentRef, "Opening situation", scenario, "Where play begins and what is already true."),
      field(documentRef, "Story language", language),
    );
    if (state.route === "blank") mountLocation(form);
    const actions = node(documentRef, "div", "ui-new-story__actions");
    actions.append(backButton("Back", () => setStep("choice", "")));
    const next = node(documentRef, "button", "ui-button ui-button--primary", state.route === "blank" ? "Review story" : "Choose story material");
    next.type = "submit";
    actions.append(next);
    form.append(actions);
    form.addEventListener("submit", event => {
      event.preventDefault();
      state.name = name.value.trim();
      state.scenario = scenario.value.trim();
      state.language = language.value || "en";
      setStep(state.route === "blank" ? "review" : "assets");
    });
    body.append(form);
  };

  const renderAssets = () => {
    const data = library();
    body.append(heading(
      "Step 2 of 3",
      "Choose story material",
      "Saved and generated material can be mixed. Everything stays editable in Library after creation.",
    ));
    const grid = node(documentRef, "div", "ui-new-story__asset-grid");
    let updateGenerationState = () => {};
    const personaSection = node(documentRef, "section", "ui-new-story__asset-section");
    personaSection.append(node(documentRef, "h3", "ui-heading ui-heading--3", "Player persona"));
    const persona = node(documentRef, "select", "ui-select");
    persona.setAttribute("aria-label", "Player persona");
    const noPersona = node(documentRef, "option", "", "No persona yet");
    noPersona.value = "";
    persona.append(noPersona);
    (data.personas || []).forEach(item => {
      const option = node(documentRef, "option", "", item.name || "Untitled persona");
      option.value = String(item.id);
      option.selected = String(item.id) === String(state.personaId);
      persona.append(option);
    });
    persona.addEventListener("change", () => { state.personaId = persona.value; state.generatePersona = false; persist(); render(); });
    personaSection.append(persona);
    const generatePersona = checkboxRow(documentRef, "Generate a new persona", state.generatePersona, checked => {
      state.generatePersona = checked;
      if (checked) state.personaId = "";
      persist(); render();
    }, "Uses the configured text model only when the story is created.");
    personaSection.append(generatePersona);
    if (state.generatePersona) {
      const brief = node(documentRef, "textarea", "ui-textarea");
      brief.setAttribute("aria-label", "New persona description");
      brief.value = state.personaBrief;
      brief.addEventListener("input", () => { state.personaBrief = brief.value; persist(); });
      personaSection.append(brief);
    }

    const castSection = node(documentRef, "section", "ui-new-story__asset-section");
    castSection.append(node(documentRef, "h3", "ui-heading ui-heading--3", "Cast"));
    if (!(data.characters || []).length) castSection.append(node(documentRef, "p", "ui-muted", "No saved characters yet. You can continue without one."));
    (data.characters || []).forEach(item => castSection.append(checkboxRow(
      documentRef, item.name || "Untitled character", state.characterIds.includes(Number(item.id)), checked => {
        state.characterIds = checked
          ? [...new Set([...state.characterIds, Number(item.id)])]
          : state.characterIds.filter(id => Number(id) !== Number(item.id));
        persist();
        render();
      }, "Saved in Library",
    )));
    const brief = node(documentRef, "textarea", "ui-textarea");
    brief.setAttribute("aria-label", "New character description");
    brief.placeholder = "Optional: describe one new character for Sonder to generate.";
    brief.value = state.characterBriefs[0] || "";
    brief.addEventListener("input", () => {
      state.characterBriefs[0] = brief.value;
      persist();
      updateGenerationState();
    });
    castSection.append(brief, node(documentRef, "small", "ui-muted", "Generation uses the configured text model only when you create the story."));

    const loreSection = node(documentRef, "section", "ui-new-story__asset-section");
    loreSection.append(node(documentRef, "h3", "ui-heading ui-heading--3", "Lore"));
    if (!(data.lorebooks || []).length) loreSection.append(node(documentRef, "p", "ui-muted", "No saved lore yet. Lore is optional."));
    (data.lorebooks || []).forEach(item => loreSection.append(checkboxRow(
      documentRef, item.name || "Untitled lorebook", state.loreIds.includes(Number(item.id)), checked => {
        state.loreIds = checked
          ? [...new Set([...state.loreIds, Number(item.id)])]
          : state.loreIds.filter(id => Number(id) !== Number(item.id));
        persist();
      }, "A story-owned copy will be attached.",
    )));
    grid.append(personaSection, castSection, loreSection);
    body.append(grid);
    const locationCharacters = (data.characters || []).filter(item => (
      state.characterIds.includes(Number(item.id))
    )).map(item => ({
      key: `saved:${item.id}`,
      name: item.name || "Untitled character",
    }));
    if (state.route === "describe") {
      locationCharacters.push({ key: "generated:0", name: "New generated character" });
    }
    mountLocation(body, locationCharacters);
    const warning = node(documentRef, "div", "ui-new-story__warning");
    warning.append(
      node(documentRef, "strong", "", "AI generation is unavailable."),
      node(documentRef, "span", "", "Choose saved material, remove the generation descriptions, or connect a default text model in Settings."),
    );
    const connect = node(documentRef, "button", "ui-button ui-button--quiet", "Open AI Connections");
    connect.type = "button";
    connect.addEventListener("click", () => { dialog.close("settings"); services.router.navigate({ destination: "settings", segments: ["ai-connections"] }); });
    warning.append(connect);
    body.append(warning);
    const actions = node(documentRef, "div", "ui-new-story__actions");
    actions.append(backButton("Back", () => setStep("details")));
    const review = node(documentRef, "button", "ui-button ui-button--primary", "Review story");
    review.type = "button";
    review.addEventListener("click", () => setStep("review"));
    actions.append(review);
    body.append(actions);
    updateGenerationState = () => {
      const needsModel = state.generatePersona || state.characterBriefs.some(value => value.trim());
      const blocked = needsModel && !hasGenerationModel(settings);
      warning.hidden = !blocked;
      review.disabled = blocked;
    };
    updateGenerationState();
  };

  const renderReview = () => {
    const data = library();
    const personaName = state.generatePersona
      ? "A new persona will be generated"
      : (data.personas || []).find(item => String(item.id) === String(state.personaId))?.name || "No persona selected";
    const selectedCharacters = (data.characters || []).filter(item => state.characterIds.includes(Number(item.id)));
    const generatedCount = state.characterBriefs.filter(value => value.trim()).length;
    const selectedLore = (data.lorebooks || []).filter(item => state.loreIds.includes(Number(item.id)));
    body.append(heading("Step 3 of 3", "Review your story", "Nothing is created until you choose Create story."));
    const review = node(documentRef, "dl", "ui-new-story__review");
    const row = (term, value) => {
      review.append(node(documentRef, "dt", "", term), node(documentRef, "dd", "", value));
    };
    row("Story", state.name || "New story");
    row("Opening", state.scenario || "No opening situation yet");
    row("Language", state.language || "en");
    row("Persona", personaName);
    row("Cast", `${selectedCharacters.length} saved · ${generatedCount} generated`);
    row("Lore", `${selectedLore.length} selected`);
    if (state.livedLocation.enabled) {
      const horizon = Number(state.livedLocation.horizonHours) || 0;
      row("Lived location", state.livedLocation.brief.trim() || "Prepared from the story setup");
      row("Character pasts", horizon
        ? `${horizon === 720 ? "Past month" : "Past week"} · active tail ${Math.min(96, horizon)} hours`
        : "Start at the present");
    }
    body.append(review);
    const needsModel = state.generatePersona || generatedCount > 0 || state.livedLocation.enabled;
    body.append(node(documentRef, "p", "ui-new-story__cost", needsModel
      ? "AI generation selected · provider usage may incur model cost."
      : "No AI generation selected"));
    if (state.cardWarnings.length) {
      const warning = node(documentRef, "section", "ui-new-story__card-warnings");
      warning.append(node(documentRef, "strong", "", "Generated card needs review"));
      const list = node(documentRef, "ul", "");
      state.cardWarnings.forEach(message => list.append(node(documentRef, "li", "", String(message))));
      warning.append(list);
      body.append(warning);
    }
    const error = node(documentRef, "p", "ui-new-story__error");
    error.setAttribute("role", "status");
    body.append(error);
    const actions = node(documentRef, "div", "ui-new-story__actions");
    actions.append(backButton("Edit", () => setStep(state.route === "blank" ? "details" : "assets")));
    const create = node(
      documentRef,
      "button",
      "ui-button ui-button--primary",
      state.cardWarnings.length && !state.cardWarningsReviewed
        ? "Create story after reviewing warnings"
        : "Create story",
    );
    create.type = "button";
    create.addEventListener("click", async () => {
      if (creating) return;
      creating = true;
      create.disabled = true;
      error.textContent = "Creating story…";
      let incompleteStoryId = null;
      try {
        if (state.cardWarnings.length && !state.cardWarningsReviewed) {
          state.cardWarningsReviewed = true;
          persist();
        }
        const generatedWarnings = [];
        let personaId = state.preparedPersonaId || (state.personaId ? Number(state.personaId) : null);
        if (state.generatePersona && !state.preparedPersonaId) {
          if (!state.personaBrief.trim()) throw new Error("Describe the new persona before creating the story.");
          const result = await services.apiClient.post("/api/personas/generate", {
            prompt: state.personaBrief.trim(), language: state.language,
          }, { channel: "new-story-persona", owner: DRAFT_OWNER });
          personaId = Number(result.data?.id);
          if (!Number.isSafeInteger(personaId)) throw new Error("A generated Persona response was incomplete.");
          generatedWarnings.push(...(Array.isArray(result.data?.warnings) ? result.data.warnings : []));
        }
        const generatedCharacterIds = [...state.preparedCharacterIds];
        for (const description of state.preparedCharacterIds.length
          ? [] : state.characterBriefs.map(value => value.trim()).filter(Boolean)) {
          const result = await services.apiClient.post("/api/characters/generate", {
            prompt: description, language: state.language,
          }, { channel: "new-story-character", owner: DRAFT_OWNER });
          const id = Number(result.data?.id);
          if (!Number.isSafeInteger(id)) throw new Error("A generated Character response was incomplete.");
          generatedCharacterIds.push(id);
          generatedWarnings.push(...(Array.isArray(result.data?.warnings) ? result.data.warnings : []));
        }
        if ((state.generatePersona && !state.preparedPersonaId)
            || (!state.preparedCharacterIds.length && generatedCharacterIds.length)) {
          state.preparedPersonaId = state.generatePersona ? personaId : null;
          state.preparedCharacterIds = generatedCharacterIds;
          persist();
        }
        if (generatedWarnings.length) {
          state.cardWarnings = [...new Set(generatedWarnings.map(String))];
          state.cardWarningsReviewed = false;
          persist();
          render();
          return;
        }
        const characterIds = [...state.characterIds, ...generatedCharacterIds];
        if (state.livedLocation.enabled && characterIds.length > 16) {
          throw new Error("A lived-location start can prepare at most 16 full Characters. Remove a Character route or turn off lived-location preparation; the Story setup is still here.");
        }
        const result = await services.apiClient.post("/api/chats", {
          name: state.name || "New story", scenario: state.scenario, language: state.language || "en",
        }, { channel: "new-story-create", owner: DRAFT_OWNER });
        const chatId = Number(result.data?.id);
        if (!Number.isSafeInteger(chatId)) throw new Error("The created Story response was incomplete.");
        incompleteStoryId = chatId;
        if (personaId) await services.apiClient.put(`/api/chats/${chatId}`, { persona_id: personaId }, { channel: "new-story-persona-attach", owner: DRAFT_OWNER });
        for (const charId of characterIds) await services.apiClient.post(`/api/chats/${chatId}/characters`, { char_id: Number(charId), already_known: false }, { channel: "new-story-cast-attach", owner: DRAFT_OWNER });
        let owningLorebookId = null;
        for (const loreId of state.loreIds) {
          const attached = await services.apiClient.post(`/api/chats/${chatId}/lorebooks`, { lorebook_id: Number(loreId) }, { channel: "new-story-lore-attach", owner: DRAFT_OWNER });
          if (!owningLorebookId) owningLorebookId = Number(attached.data?.lorebook_id || attached.data?.id) || null;
        }
        if (state.livedLocation.enabled) {
          const generatedByIndex = new Map(generatedCharacterIds.map((id, index) => [`generated:${index}`, id]));
          const savedIds = new Set(state.characterIds.map(Number));
          await generateLivedLocation({
            apiClient: services.apiClient,
            chatId,
            value: state.livedLocation,
            sourceLorebookId: state.loreIds[0] || null,
            owningLorebookId,
            resolveCharacterId(key) {
              if (key.startsWith("saved:")) {
                const id = Number(key.slice(6));
                return savedIds.has(id) ? id : null;
              }
              return generatedByIndex.get(key) || null;
            },
            requestOptions: { channel: "new-story-lived-location", owner: DRAFT_OWNER },
          });
        }
        services.localState.clearDraft(DRAFT_TYPE, DRAFT_OWNER);
        const current = services.store.getSnapshot().library;
        services.store.dispatch({ type: "server/patch", slice: "library", value: {
          chats: [{ id: chatId, name: state.name || "New story" }, ...(current.chats || [])],
        } });
        dialog.close("created");
        incompleteStoryId = null;
        services.router.navigate({ destination: "play", query: { chat: String(chatId) } });
      } catch (caught) {
        if (incompleteStoryId) {
          try {
            await services.apiClient.delete(`/api/chats/${incompleteStoryId}`, {
              channel: "new-story-cleanup", owner: DRAFT_OWNER,
            });
          } catch (cleanupError) {
            error.replaceChildren(documentRef.createTextNode("Story setup failed and the incomplete Story could not be removed. Your setup draft is still here. "));
            const link = node(documentRef, "button", "ui-button ui-button--quiet", "View incomplete Story");
            link.type = "button";
            link.addEventListener("click", () => {
              dialog.close("incomplete");
              services.router.navigate({ destination: "play", query: { chat: String(incompleteStoryId) } });
            });
            error.append(link);
            create.disabled = false;
            return;
          }
        }
        error.textContent = caught?.userMessage || caught?.message || "Sonder could not create the story. Your setup draft is still here.";
        create.disabled = false;
      } finally {
        creating = false;
      }
    });
    actions.append(create);
    body.append(actions);
  };

  function render() {
    body.replaceChildren();
    renderRecovered();
    if (state.step === "details") renderDetails();
    else if (state.step === "assets") renderAssets();
    else if (state.step === "review") renderReview();
    else renderChoice();
    services.localizer?.localize(body);
  }

  dialog.addEventListener("close", () => dialog.remove(), { once: true });
  dialog.addEventListener("cancel", event => {
    event.preventDefault();
    dialog.close("cancel");
  });
  render();
  dialog.showModal();
  return dialog;
}
