// ---- Boot & sidebar ----

// A language pack the server could not use is reported once per session.
// `boot()` reruns on every import, save and NSFW toggle, and a report
// repeated on each of those is a nag rather than a report.
let languagePackErrorReported = false;

async function boot() {
  S.boot = await api("GET", "/api/bootstrap");
  S.uiCatalog = S.boot.ui_messages || {};
  S.uiLanguage = S.boot.ui_language || "en";
  S.uiTemplateRules = null;
  localizeDocument();
  watchUILanguage();
  S.nsfw = S.boot.nsfw_enabled || false;

  // The bootstrap refuses to die on a malformed pack and reports why instead
  // -- and then nothing showed the report, so a host who installed a pack got
  // English with no reason given. The wording is the server's because the
  // reason IS the pack's own error, naming the file and what was wrong with it.
  if (S.boot.language_error && !languagePackErrorReported) {
    languagePackErrorReported = true;
    toast(S.boot.language_error, "warn", 8000);
  }

  updateNSFWBtn();
  // See the guard in chat.js's observer: an optional experimental module must
  // never be able to abort boot() before the sidebar and transcript render.
  if (typeof syncBackdrops === "function") syncBackdrops();
  if (typeof syncAmbience === "function") syncAmbience();
  renderSide();

  // On cold boot no chat is open yet, so nothing else would ever replace
  // the static placeholder markup in #msgs with the real first-run
  // checklist. Safe to call unconditionally here since it's a no-op
  // when a chat IS already open (renderChat's early-return branch only
  // fires for !S.chat) -- but guard on !S.chatId anyway so a boot()
  // triggered while a chat is open (e.g. after importing a character)
  // never re-renders the transcript out from under an active view.
  if (!S.chatId) {
    renderChat();
  }
}

$$("#tabs button").forEach(button => {
  button.onclick = () => {
    $$("#tabs button").forEach(item => item.classList.remove("on"));
    button.classList.add("on");
    S.tab = button.dataset.tab;
    renderSide();
  };
});

$("#b-menu").onclick = () => {
  // Narrow viewports use the slide-in drawer (.open); desktop fully
  // collapses the sidebar to give the story more room, remembering the
  // choice across reloads.
  if (window.innerWidth <= 680) {
    $("#side").classList.toggle("open");
  } else {
    const collapsed = $("#side").classList.toggle("collapsed");
    try { localStorage.setItem("sideCollapsed", collapsed ? "1" : "0"); }
    catch (e) {}
  }
};

// Restore the persisted desktop collapse state on load.
try {
  if (localStorage.getItem("sideCollapsed") === "1") {
    $("#side").classList.add("collapsed");
  }
} catch (e) {}

$("#sidelist").addEventListener("click", () => {
  if (window.innerWidth <= 680) {
    $("#side").classList.remove("open");
  }
});

function renderSide() {
  const list = $("#sidelist");
  const actions = $("#sideactions");

  list.innerHTML = "";
  actions.innerHTML = "";

  syncExtensionTabs();

  if (S.tab === "chats") {
    renderChatSidebar(list, actions);
  } else if (S.tab === "chars") {
    renderCharacterSidebar(list, actions);
  } else if (S.tab === "personas") {
    renderPersonaSidebar(list, actions);
  } else if (S.tab === "lore") {
    if (typeof renderLoreLibrarySidebar === "function") {
      renderLoreLibrarySidebar(list, actions);
    } else {
      renderLegacyLoreSidebar(list, actions);
    }
  } else if (typeof S.tab === "string" && S.tab.startsWith("ext:")) {
    // An extension owns this tab. If it has been retired since the reader
    // selected it, fall back to the stories list rather than showing an empty
    // sidebar with no way out.
    const claimed = window.Sonder
      && Sonder._renderSidebarTab(S.tab.slice(4), list);
    if (!claimed) {
      S.tab = "chats";
      renderSide();
    }
  }
}

// Extension tabs sit in #tabs next to the built-in four, but they cannot be
// authored there: an extension's UI script is the LAST script on the page, so
// the static `$$("#tabs button")` binding above has already run by the time
// the registration exists. Rebuilding them on every renderSide is also what
// makes an extension disappearing (disabled, or retired after three throws)
// take its tab with it.
function syncExtensionTabs() {
  const bar = $("#tabs");
  if (!bar) return;
  for (const stale of $$("#tabs button[data-ext-tab]")) stale.remove();

  const tabs = (window.Sonder && Sonder._sidebarTabs()) || [];
  for (const tab of tabs) {
    // Concatenated rather than interpolated: a template literal is a message
    // candidate to tools/extract_ui_catalog.py, and "ext:<id>" is a state key,
    // not something to translate.
    const key = "ext:" + tab.id;
    bar.append(el("button", {
      "data-tab": key,
      "data-ext-tab": tab.id,
      onclick: () => {
        S.tab = key;
        renderSide();
      }
    }, tab.label));
  }

  // The built-in handler only ever sets `.on` on built-in buttons, so the
  // highlight is settled here for all of them at once -- otherwise a story
  // tab stayed lit while an extension's panel was on screen.
  for (const button of $$("#tabs button")) {
    button.classList.toggle("on", button.dataset.tab === S.tab);
  }
}

function renderChatSidebar(list, actions) {
  if (!S.boot.chats.length) {
    list.append(el("div", { class: "empty-state" },
      el("div", { style: "margin-bottom:10px" }, "No stories yet."),
      el("button", { class: "primary", onclick: () => newChatWizard() }, "✨ New story")));
  }

  for (const chat of S.boot.chats) {
    const storyName = el("span", {
      class: "item-label",
      title: chat.name,
    }, chat.name);
    const storyActions = el(
      "div",
      {
        class: "item-actions",
        role: "group",
        "aria-label": `Actions for ${chat.name}`,
      },
        el(
          "button",
          {
            class: "icon-button story-action",
            title: "Rename",
            "aria-label": `Rename ${chat.name}`,
            onclick: async event => {
              event.stopPropagation();
              const name = await promptModal("Rename story:", chat.name);
              if (name == null) return;
              const trimmed = name.trim();
              if (!trimmed || trimmed === chat.name) return;
              await api("PUT", `/api/chats/${chat.id}`, { name: trimmed });
              if (S.chat && S.chatId === chat.id) {
                S.chat.chat.name = trimmed;
                const header = document.getElementById("chatname");
                if (header) { header.textContent = trimmed; header.title = trimmed; }
              }
              await boot();
            }
          },
          "✎"
        ),
        el(
          "button",
          {
            class: "icon-button story-action",
            title: "Export",
            "aria-label": `Export ${chat.name}`,
            onclick: event => {
              event.stopPropagation();
              exportChat(chat.id);
            }
          },
          "⤓"
        ),
        el(
          "button",
          {
            class: "icon-button story-action danger",
            title: "Delete",
            "aria-label": `Delete ${chat.name}`,
            onclick: async event => {
              event.stopPropagation();

              if (!await confirmModal("Delete story?", { danger: true, confirmLabel: "Delete" })) {
                return;
              }

              await api("DELETE", `/api/chats/${chat.id}`);

              if (S.chatId === chat.id) {
                S.chatId = null;
                S.chat = null;
                renderChat();
              }

              await boot();
            }
          },
          "✕"
        )
      );

    list.append(el(
      "div",
      {
        class: "item story-item" + (chat.id === S.chatId ? " on" : ""),
        tabindex: "0",
        "aria-label": `Open ${chat.name}`,
        "aria-current": chat.id === S.chatId ? "true" : "false",
        onclick: () => openChat(chat.id),
        onkeydown: event => {
          if (event.target !== event.currentTarget) return;
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            openChat(chat.id);
          }
        },
      },
      storyName,
      storyActions
    ));
  }

  actions.append(
    el(
      "button",
      { onclick: () => newChatWizard() },
      "+ Story"
    ),
    el(
      "button",
      { onclick: () => importChatModal() },
      "⤓ Import story"
    )
  );
}

// ---- New chat wizard ----
// Two paths that land in the same underlying data model: "quick start"
// generates a persona/cast from plain-text descriptions using the existing
// /generate endpoints (same ones the Characters/Personas tabs already use),
// "build from scratch" is the old bare promptModal()-based flow for anyone who
// wants to hand-author everything in the full editors first. Either way the
// result is a normal chat with normal persona/character records -- quick
// start is just a fast way to fill them in, not a separate simplified mode.
function newChatWizard() {
  if (!hasDefaultModel()) {
    toast("Connect an AI provider first — opening API Connections.", "warn");
    $("#b-api").click();
    return;
  }
  modal("New story", b => renderWizardChoice(b), { wide: true });
}

function renderWizardChoice(b) {
  b.innerHTML = "";
  b.append(
    el("div", { class: "small dim", style: "margin-bottom:12px" },
      "Start from a description, or build the persona and cast by hand first."),
    el("div", { class: "row", style: "gap:10px" },
      el("button", { class: "primary", onclick: () => renderWizardPersona(b, wizardState()) },
        "✨ Quick start — describe your story"),
      el("button", { onclick: () => wizardFromScratch() },
        "Build from scratch")));
}

function storyLanguagePacks() {
  return ((S.boot && S.boot.language_packs) || []).filter(pack => pack.story);
}

function defaultStoryLanguage() {
  // Falls back to the INTERFACE language, not to English. The wizard's own
  // dropdown is the only thing that writes `storyLanguage`, so a host who set
  // Japanese from the Prompts menu still got an English wizard -- and then
  // English characters, because the wizard is what sends `language` to the
  // generators.
  let saved = "";
  try { saved = localStorage.getItem("storyLanguage") || ""; }
  catch (e) {}
  const known = id => storyLanguagePacks().some(pack => pack.id === id);
  if (saved && known(saved)) return saved;
  const ui = S.uiLanguage || (S.boot && S.boot.ui_language) || "en";
  return known(ui) ? ui : "en";
}

function wizardState() {
  return {
    name: "",
    scenario: "",
    language: defaultStoryLanguage(),
    personaMode: "generate",
    personaBrief: "",
    personaId: null,
    characterBriefs: [""],
    characterBriefsKnown: [false],
    existingCharacterIds: new Set(),
    alreadyKnownCharacterIds: new Set()
  };
}

async function wizardFromScratch() {
  const name = await promptModal("Story name?");
  if (name == null) return;               // Cancel/Escape -> abort, don't create a chat
  const scenario = await promptModal("Scenario?");
  if (scenario == null) return;
  const chat = await api("POST", "/api/chats", {
    name: name || "", scenario: scenario || "", language: defaultStoryLanguage()
  });
  await boot();
  await openChat(chat.id);
}

function renderWizardPersona(b, state) {
  b.innerHTML = "";

  const genOpt = el("option", { value: "generate" }, "✨ Describe a new persona");
  const existingOpts = S.boot.personas.map(p => el("option", { value: String(p.id) }, p.name));
  const modeSel = el("select", {}, genOpt, ...existingOpts);
  modeSel.value = state.personaMode === "generate" ? "generate" : String(state.personaId);

  const briefTa = el("textarea", {
    style: "width:100%;height:110px;margin-top:8px",
    placeholder: "Who are you in this story? A line or two is enough — "
      + "e.g. \"Dana Osei, a supply pilot returning to a station that's gone dark.\""
  }, state.personaBrief);

  const refreshVisibility = () => {
    briefTa.style.display = modeSel.value === "generate" ? "" : "none";
  };
  refreshVisibility();
  modeSel.onchange = refreshVisibility;

  b.append(
    el("div", { class: "small dim" }, "Step 1 of 3 — your persona"),
    el("div", { style: "margin-top:8px" }, modeSel, briefTa),
    el("div", { class: "row", style: "margin-top:14px" },
      el("button", { onclick: () => renderWizardChoice(b) }, "← Back"),
      el("span", { class: "spacer" }),
      el("button", { class: "primary", onclick: () => {
        state.personaMode = modeSel.value === "generate" ? "generate" : "existing";
        state.personaBrief = briefTa.value.trim();
        state.personaId = modeSel.value === "generate" ? null : +modeSel.value;
        if (state.personaMode === "generate" && !state.personaBrief) {
          toast("Describe your persona, or pick an existing one.", "warn");
          return;
        }
        renderWizardCharacters(b, state);
      } }, "Next →")));
}

function renderWizardCharacters(b, state) {
  b.innerHTML = "";

  const briefList = el("div");
  const renderBriefs = () => {
    briefList.innerHTML = "";
    state.characterBriefs.forEach((val, i) => {
      const ta = el("textarea", {
        style: "width:100%;height:70px;margin-top:6px",
        placeholder: "Describe a character in this story — "
          + "e.g. \"Yusuf Kessler, a jumpy station engineer hiding what he did during the breach.\""
      }, val);
      ta.oninput = () => { state.characterBriefs[i] = ta.value };
      const knownCb = el("input", {
        type: "checkbox",
        title: "They already know your persona by name from the start, "
          + "instead of meeting for the first time in-story."
      });
      knownCb.checked = !!state.characterBriefsKnown[i];
      knownCb.onchange = () => { state.characterBriefsKnown[i] = knownCb.checked };
      const knownLbl = el("label", { class: "row small dim", style: "gap:6px;margin-top:4px" },
        knownCb, "already knows you");
      const row = el("div", { class: "row", style: "align-items:flex-start" }, ta);
      if (state.characterBriefs.length > 1) {
        row.append(el("button", {
          title: "Remove", onclick: () => {
            state.characterBriefs.splice(i, 1);
            state.characterBriefsKnown.splice(i, 1);
            renderBriefs();
          }
        }, "✕"));
      }
      briefList.append(el("div", {}, row, knownLbl));
    });
  };
  renderBriefs();

  const existingBox = el("div", { style: "margin-top:8px" },
    ...S.boot.characters.map(c => {
      const cb = el("input", { type: "checkbox" });
      cb.checked = state.existingCharacterIds.has(c.id);
      const knownCb = el("input", {
        type: "checkbox",
        title: "They already know your persona by name from the start, "
          + "instead of meeting for the first time in-story."
      });
      knownCb.checked = state.alreadyKnownCharacterIds.has(c.id);
      knownCb.disabled = !cb.checked;
      knownCb.onchange = () => {
        if (knownCb.checked) state.alreadyKnownCharacterIds.add(c.id);
        else state.alreadyKnownCharacterIds.delete(c.id);
      };
      cb.onchange = () => {
        if (cb.checked) {
          state.existingCharacterIds.add(c.id);
        } else {
          state.existingCharacterIds.delete(c.id);
          state.alreadyKnownCharacterIds.delete(c.id);
          knownCb.checked = false;
        }
        knownCb.disabled = !cb.checked;
      };
      return el("label", { class: "row", style: "gap:6px" }, cb, c.name,
        el("span", { class: "small dim", style: "margin-left:8px" }, "already knows you"),
        knownCb);
    }));

  b.append(
    el("div", { class: "small dim" }, "Step 2 of 3 — who else is in this story?"),
    briefList,
    el("button", { style: "margin-top:6px", onclick: () => {
      state.characterBriefs.push("");
      state.characterBriefsKnown.push(false);
      renderBriefs();
    } }, "+ Add another character"),
    S.boot.characters.length
      ? el("div", { style: "margin-top:14px" },
          el("div", { class: "small dim" }, "Or include an existing character:"), existingBox)
      : null,
    el("div", { class: "row", style: "margin-top:14px" },
      el("button", { onclick: () => renderWizardPersona(b, state) }, "← Back"),
      el("span", { class: "spacer" }),
      el("button", { class: "primary", onclick: () => renderWizardScenario(b, state) }, "Next →")));
}

function renderWizardScenario(b, state) {
  b.innerHTML = "";

  const nameIn = el("input", { type: "text", style: "width:100%", value: state.name,
    placeholder: "Story name" });
  const scenIn = el("textarea", { style: "width:100%;height:140px", placeholder:
    "Set the scene — where this starts, what's mapped so far, who's present." }, state.scenario);
  const language = el("select", { style: "flex:1" },
    storyLanguagePacks().map(pack => el("option", {
      value: pack.id,
      ...(pack.id === state.language ? { selected: "" } : {})
    }, pack.native_name || pack.name || pack.id)));

  b.append(
    el("div", { class: "small dim" }, "Step 3 of 3 — the scenario"),
    el("div", { style: "margin-top:8px" }, nameIn, scenIn),
    el("div", { class: "row", style: "margin-top:8px" },
      el("span", { class: "small", style: "width:70px" }, "Language"), language),
    el("div", { class: "row", style: "margin-top:14px" },
      el("button", { onclick: () => renderWizardCharacters(b, state) }, "← Back"),
      el("span", { class: "spacer" }),
      el("button", { class: "primary", onclick: () => {
        state.name = nameIn.value.trim();
        state.scenario = scenIn.value.trim();
        state.language = language.value || "en";
        try { localStorage.setItem("storyLanguage", state.language); }
        catch (e) {}
        runWizard(state);
      } }, "Create story")));
}

async function runWizard(state) {
  backgroundTask("Setting up story", async () => {
    let personaId = state.personaId;
    if (state.personaMode === "generate") {
      const r = await api("POST", "/api/personas/generate", {
        prompt: state.personaBrief, language: state.language
      });
      personaId = r.id;
    }

    const characterIds = [...state.existingCharacterIds];
    const knownIds = new Set(state.alreadyKnownCharacterIds);
    for (let i = 0; i < state.characterBriefs.length; i++) {
      const text = state.characterBriefs[i].trim();
      if (!text) continue;
      const r = await api("POST", "/api/characters/generate", {
        prompt: text, language: state.language
      });
      showCardWarnings(r);
      characterIds.push(r.id);
      if (state.characterBriefsKnown[i]) knownIds.add(r.id);
    }

    const chat = await api("POST", "/api/chats", {
      name: state.name || "New story",
      scenario: state.scenario,
      language: state.language
    });
    if (personaId) {
      await api("PUT", `/api/chats/${chat.id}`, { persona_id: personaId });
    }
    for (const cid of characterIds) {
      await api("POST", `/api/chats/${chat.id}/characters`, {
        char_id: cid,
        already_known: knownIds.has(cid)
      });
    }
    return chat;
  }, {
    onSuccess: async chat => {
      await boot();
      await openChat(chat.id);
    },
    successMessage: "Story ready.",
    errorPrefix: "Couldn't set up story"
  });
}

function renderCharacterSidebar(list, actions) {
  for (const character of S.boot.characters) {
    list.append(el(
      "div",
      {
        class: "item library-item",
        tabindex: "0",
        "aria-label": `Edit ${character.name}`,
        onclick: () => charEditor(character),
        onkeydown: event => {
          if (event.target !== event.currentTarget) return;
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            charEditor(character);
          }
        },
      },
      el("span", { class: "item-label", title: character.name }, character.name),
      el(
        "div",
        { class: "item-actions", role: "group", "aria-label": `Actions for ${character.name}` },
        el(
          "button",
          {
            class: "icon-button story-action",
            title: "Export",
            "aria-label": `Export ${character.name}`,
            onclick: event => {
              event.stopPropagation();
              exportCharacter(character.id);
            }
          },
          "⤓"
        ),
        el(
          "button",
          {
            class: "icon-button story-action danger",
            title: "Delete",
            "aria-label": `Delete ${character.name}`,
            onclick: async event => {
              event.stopPropagation();

              if (!await confirmModal("Delete character?", { danger: true, confirmLabel: "Delete" })) {
                return;
              }

              await api(
                "DELETE",
                `/api/characters/${character.id}`
              );
              await boot();
            }
          },
          "✕"
        )
      )
    ));
  }

  actions.append(
    el(
      "button",
      { onclick: () => charEditor(null) },
      "+ Character"
    ),
    el(
      "button",
      { onclick: () => importModal("character") },
      "⤓ Import"
    ),
    el(
      "button",
      { onclick: () => generateModal("character") },
      "✨ Generate"
    )
  );
}

function renderPersonaSidebar(list, actions) {
  for (const persona of S.boot.personas) {
    list.append(el(
      "div",
      {
        class: "item library-item",
        tabindex: "0",
        "aria-label": `Edit ${persona.name}`,
        onclick: () => personaEditor(persona),
        onkeydown: event => {
          if (event.target !== event.currentTarget) return;
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            personaEditor(persona);
          }
        },
      },
      el("span", { class: "item-label", title: persona.name }, persona.name),
      el(
        "div",
        { class: "item-actions", role: "group", "aria-label": `Actions for ${persona.name}` },
        el(
          "button",
          {
            class: "icon-button story-action",
            title: "Export",
            "aria-label": `Export ${persona.name}`,
            onclick: event => {
              event.stopPropagation();
              exportPersona(persona.id);
            }
          },
          "⤓"
        ),
        el(
          "button",
          {
            class: "icon-button story-action danger",
            title: "Delete",
            "aria-label": `Delete ${persona.name}`,
            onclick: async event => {
              event.stopPropagation();

              if (!await confirmModal("Delete persona?", { danger: true, confirmLabel: "Delete" })) {
                return;
              }

              await api(
                "DELETE",
                `/api/personas/${persona.id}`
              );
              await boot();
            }
          },
          "✕"
        )
      )
    ));
  }

  actions.append(
    el(
      "button",
      { onclick: () => personaEditor(null) },
      "+ Persona"
    ),
    el(
      "button",
      { onclick: () => importModal("persona") },
      "⤓ Import"
    ),
    el(
      "button",
      { onclick: () => generateModal("persona") },
      "✨ Generate"
    )
  );
}

function renderLegacyLoreSidebar(list, actions) {
  for (const book of S.boot.lorebooks) {
    list.append(el(
      "div",
      {
        class: "item",
        onclick: () => openLoreWorkspace(book.id)
      },
      el(
        "span",
        { class: "item-label", title: book.name },
        book.name,
        " ",
        el(
          "span",
          { class: "badge" },
          book.book_type || "general"
        )
      )
    ));
  }

  actions.append(
    el(
      "button",
      {
        onclick: async () => {
          const name = await promptModal("Lorebook name?") || "New lorebook";
          const result = await api("POST", "/api/lorebooks", {
            name
          });

          await boot();
          await openLoreWorkspace(result.id);
        }
      },
      "+ Lorebook"
    ),
    el(
      "button",
      { onclick: () => importModal("lorebook") },
      "⤓ Import"
    )
  );
}

// ---- NSFW ----

function updateNSFWBtn() {
  const button = $("#b-nsfw");

  if (!button) {
    return;
  }

  button.textContent = "NSFW: " + (S.nsfw ? "ON" : "OFF");
  button.classList.toggle("on", S.nsfw);
}

async function toggleNSFW() {
  S.nsfw = !S.nsfw;
  updateNSFWBtn();

  try {
    await api("PUT", "/api/nsfw", {
      enabled: S.nsfw
    });
  } catch (error) {
    S.nsfw = !S.nsfw;
    updateNSFWBtn();
    toast("Could not toggle NSFW.", "err");
  }
}

// ---- Composer ----

// Coalesced to one measure per painted frame: the body forces a synchronous
// layout (height:auto, then scrollHeight), and it used to run per `input`
// event -- every keystroke, plus a second cascade when the height change
// tripped the #composer ResizeObserver. A frame of delay on a textarea
// growing is imperceptible; the forced layout per keystroke was not free.
let _composerResizeQueued = false;
function resizeComposer() {
  if (_composerResizeQueued) return;
  _composerResizeQueued = true;
  requestAnimationFrame(() => {
    _composerResizeQueued = false;
    const input = $("#input");
    if (!input) return;
    input.style.height = "auto";
    // The ceiling lives in CSS (#input's max-height) rather than being
    // repeated here -- it is viewport-relative now, and two copies of the
    // same number drift the moment one of them is tuned.
    const max = parseFloat(getComputedStyle(input).maxHeight);
    input.style.height =
      Math.min(input.scrollHeight, Number.isFinite(max) ? max : 220) + "px";
  });
}

$("#input").addEventListener("input", resizeComposer);
// Story text sizing drives the composer's font, so the height it needs for
// the same text changes with it. Without this the box keeps the height it
// computed at the old size until you next type.
window.addEventListener("sonder-prose-size-change", resizeComposer);

$("#input").addEventListener("keydown", event => {
  if (
    event.key === "Enter"
    && !event.shiftKey
    && (event.ctrlKey || event.metaKey)
  ) {
    event.preventDefault();
    $("#send").click();
  }
});

$("#send").onclick = () => {
  if (S.busy) {
    return;
  }

  if (!S.chatId) {
    newChatWizard();
    return;
  }

  const input = $("#input");
  const text = input.value.trim();

  input.value = "";
  resizeComposer();

  runStream(
    `/api/chats/${S.chatId}/turns`,
    { input: text, frame_id: S.currentFrameId },
    { chatId: S.chatId, frameId: S.currentFrameId, playerInput: text }
  ).then(ok => {
    // The turn never started (e.g. immediate POST failure) -- give the
    // player their typed input back instead of silently eating it.
    if (ok === false && !input.value.trim()) {
      input.value = text;
      resizeComposer();
    }
  });
};

$("#stop").onclick = () => {
  abortActiveRun();
};

$("#b-nsfw").onclick = toggleNSFW;

// ---- Init ----

$("#modalx").onclick = closeModal;

$("#modal").onclick = event => {
  if (event.target.id === "modal") {
    closeModal();
  }
};

document.addEventListener("keydown", event => {
  if (
    event.key === "Escape"
    && !$("#modal").classList.contains("hidden")
    // A confirm/prompt overlay handles its own Escape (to cancel just the
    // confirm); without this guard we'd ALSO closeModal() the dialog beneath
    // it, discarding unsaved form state.
    && !document.querySelector(".confirm-overlay")
  ) {
    closeModal();
  }

  if (
    (event.ctrlKey || event.metaKey)
    && event.key === "Enter"
    && document.activeElement === $("#input")
  ) {
    event.preventDefault();
    $("#send").click();
  }
});

// Global safety net: many onclick handlers `await api(...)` without a local
// catch, so a rejection would otherwise fail silently ("nothing happens").
// Surface it. buttonTask marks errors it already toasted (__handled) so this
// doesn't double up.
window.addEventListener("unhandledrejection", event => {
  const reason = event.reason;
  if (reason && reason.__handled) return;
  toast(reason?.message || String(reason || "Something went wrong"), "err", 8000);
});

// The other half of the same net, and the half that was missing: a handler
// that throws SYNCHRONOUSLY never produces a rejection, so it reached nothing.
// A bare `JSON.parse` over a malformed sheet, a `.map` over a bootstrap key
// that did not arrive -- each is the identical "clicking does nothing" the
// listener above exists to eliminate, and each was still silent.
//
// `error` also fires for a failed script or image load, which carries no
// usable message; those stay in the console rather than becoming a toast the
// reader can do nothing with.
window.addEventListener("error", event => {
  const thrown = event.error;
  if (thrown && thrown.__handled) return;
  const message = thrown?.message || event.message;
  if (!message) return;
  toast(String(message), "err", 8000);
});


// ---- Embedding reconciler progress -----------------------------------------
//
// Changing the embeddings provider does not re-embed anything already stored,
// and a memory embedded by a different model scores 0 on both vector rankings
// for good -- so the server reconciles the bank in the background at startup
// and whenever the `embeddings` role changes. This card is what a host sees
// while that runs: it appears when there is work, counts it down, says so when
// it is finished, and removes itself.
//
// It covers ONE of the two occasions, and the smaller one. `erWatch` is the
// only thing that starts the poll and `erOfferRebuild` is its only caller, so
// the card appears only for a rebuild the host has just confirmed in the offer
// dialog. A reconcile the server begins at STARTUP is never polled for and runs
// entirely unseen. Making the sentence above true again means calling
// `erWatch()` once from boot -- one request, and the interval clears itself
// when nothing is running -- which is a decision about how much a background
// maintenance task should announce itself, not an oversight to patch quietly.
//
// Deliberately not a modal and not a toast. It can run for a while on a large
// bank, nothing is blocked while it does, and interrupting the reader to say
// "your memories are being upgraded" would be worse than saying nothing.
const ER = { timer: null, seen: false, card: null };

function erCard() {
  if (ER.card) return ER.card;
  const fill = el("div", { class: "er-fill" });
  const head = el("div", { class: "er-head" }, "Upgrading memory search");
  const note = el("div", { class: "er-note" }, "");
  ER.card = el("div", { id: "embed-rebuild" },
               head, el("div", { class: "er-bar" }, fill), note);
  ER.card._fill = fill; ER.card._head = head; ER.card._note = note;
  document.body.appendChild(ER.card);
  return ER.card;
}

function erDismiss(after = 0) {
  if (!ER.card) return;
  const card = ER.card; ER.card = null;
  setTimeout(() => card.remove(), after);
}

async function erPoll() {
  let data;
  try { data = await api("GET", "/api/memory/embeddings"); }
  catch { return; }                       // a failed poll is not worth saying
  const p = data?.progress || {};
  const stranded = (data?.memories?.stranded || 0)
                 + (data?.memory_summaries?.stranded || 0);

  if (p.running) {
    ER.seen = true;
    const card = erCard();
    const total = Math.max(p.total || 0, p.done || 0, 1);
    card._fill.style.width = Math.round((p.done / total) * 100) + "%";
    card._head.textContent = "Upgrading memory search";
    card._note.textContent =
      `Re-reading ${total.toLocaleString()} memories so older ones can be `
      + `found by meaning again. ${(p.done || 0).toLocaleString()} done — `
      + `you can keep playing.`;
    return;
  }

  if (ER.seen && ER.card) {              // it was running and has just stopped
    const card = ER.card;
    const failed = p.stopped_early || p.error;
    card.classList.add(failed ? "er-err" : "er-done");
    card._fill.style.width = "100%";
    card._head.textContent = failed
      ? "Memory upgrade interrupted" : "Memory search upgraded";
    card._note.textContent = failed
      ? `${(p.done || 0).toLocaleString()} done before it stopped`
        + `${p.error ? ": " + p.error : ""}. It will pick up where it left `
        + `off next time — nothing was lost.`
      : `${(p.done || 0).toLocaleString()} memories re-read. Older memories `
        + `are searchable by meaning again.`;
    ER.seen = false;
    erDismiss(failed ? 14000 : 7000);
    return;
  }

}

// Poll only while something is actually running; a background maintenance task
// does not deserve a standing timer.
function erWatch() {
  if (ER.timer) return;
  ER.timer = setInterval(async () => {
    await erPoll();
    if (!ER.seen && !ER.card) { clearInterval(ER.timer); ER.timer = null; }
  }, 1500);
}

// Offered when a chat is opened and its memories turn out to have been
// embedded by a different model than the one configured now. An OFFER rather
// than an automatic run: a rebuild talks to a paid provider and can take a
// while on a long story, and spending someone's money because they opened a
// chat is not a decision this code gets to make.
window.erOfferRebuild = erOfferRebuild;
async function erOfferRebuild(chatId, bank) {
  if (!bank || !bank.stranded) return;
  // The configured provider did not answer the status probe, so the server
  // could not compare anything and reported no stranded rows. Belt and
  // braces against a stale or hand-built payload: never say a word about the
  // bank on a comparison that was not made. This is the shape of the live
  // report — a fully healthy 34-memory story announcing all 34 stranded on
  // every open, because a rate limit answered the probe.
  if (bank.live_unknown) return;
  const n = bank.stranded.toLocaleString();

  if (bank.is_fallback) {
    // No embeddings provider configured, so rebuilding would overwrite real
    // vectors with the local hash — a downgrade. Say what is true and stop.
    toast(`${n} of this story's memories were written with a different `
          + `embedding model, so they can only be found by keyword. Set an `
          + `embeddings provider in API Connections to restore search by `
          + `meaning.`, "warn", 12000);
    return;
  }

  const ok = await confirmModal(
    `Out-of-date memories\n\n`
    + `${n} of this story's memories were written with a different embedding `
    + `model than the one configured now (${bank.model}). Until they are `
    + `rebuilt they can only be found by keyword and exact phrase — not by `
    + `meaning.\n\n`
    + `Rebuilding re-reads them through the current model. It runs in the `
    + `background, you can keep playing, and it resumes where it left off if `
    + `it is interrupted.`,
    { confirmLabel: "Rebuild now", cancelLabel: "Not now" });
  if (!ok) return;
  await api("POST", "/api/memory/embeddings/rebuild", { chat_id: chatId });
  ER.seen = true;
  erWatch();
}

// `body.page-hidden` (the CSS hook for "nobody is looking at this") is
// stamped by theme-init.js, which every themed page loads -- including guest
// and login, which never load this file.

boot()
  .then(() => {
    // A language change from the Prompts menu has to reload (localizeDocument
    // rewrites English source text in place and cannot translate twice), so
    // it leaves a marker and we come back to that menu here. Without it the
    // reader is dropped onto the story and the menu looks like it crashed.
    if (typeof reopenPromptsIfRequested === "function") {
      reopenPromptsIfRequested();
    }
  })
  .catch(e => toast(`Could not load the app: ${(e?.message || e)}`, "err", 0));
