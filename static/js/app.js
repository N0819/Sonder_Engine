// ---- Boot & sidebar ----

const LORE_LINK_TYPES = [
  "related",
  "references",
  "depends_on",
  "supplements",
  "overlaps",
  "supersedes",
  "contradicts",
  "alternate_version",
  "same_setting",
  "portal"
];

async function boot() {
  S.boot = await api("GET", "/api/bootstrap");
  S.nsfw = S.boot.nsfw_enabled || false;

  if (!Array.isArray(S.boot.lorebook_link_types)) {
    S.boot.lorebook_link_types = LORE_LINK_TYPES;
  }

  updateNSFWBtn();
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
  }
}

function renderChatSidebar(list, actions) {
  if (!S.boot.chats.length) {
    list.append(el("div", { class: "empty-state" },
      el("div", { style: "margin-bottom:10px" }, "No stories yet."),
      el("button", { class: "primary", onclick: () => newChatWizard() }, "✨ New story")));
  }

  for (const chat of S.boot.chats) {
    list.append(el(
      "div",
      {
        class: "item" + (chat.id === S.chatId ? " on" : ""),
        onclick: () => openChat(chat.id)
      },
      el("span", {}, chat.name),
      el(
        "div",
        { class: "row" },
        el(
          "button",
          {
            title: "Rename",
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
                if (header) header.textContent = trimmed;
              }
              await boot();
            }
          },
          "✎"
        ),
        el(
          "button",
          {
            title: "Export",
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
            title: "Delete",
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
      )
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

function wizardState() {
  return {
    name: "",
    scenario: "",
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
  const chat = await api("POST", "/api/chats", { name: name || "", scenario: scenario || "" });
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

  b.append(
    el("div", { class: "small dim" }, "Step 3 of 3 — the scenario"),
    el("div", { style: "margin-top:8px" }, nameIn, scenIn),
    el("div", { class: "row", style: "margin-top:14px" },
      el("button", { onclick: () => renderWizardCharacters(b, state) }, "← Back"),
      el("span", { class: "spacer" }),
      el("button", { class: "primary", onclick: () => {
        state.name = nameIn.value.trim();
        state.scenario = scenIn.value.trim();
        runWizard(state);
      } }, "Create story")));
}

async function runWizard(state) {
  backgroundTask("Setting up story", async () => {
    let personaId = state.personaId;
    if (state.personaMode === "generate") {
      const r = await api("POST", "/api/personas/generate", { prompt: state.personaBrief });
      personaId = r.id;
    }

    const characterIds = [...state.existingCharacterIds];
    const knownIds = new Set(state.alreadyKnownCharacterIds);
    for (let i = 0; i < state.characterBriefs.length; i++) {
      const text = state.characterBriefs[i].trim();
      if (!text) continue;
      const r = await api("POST", "/api/characters/generate", { prompt: text });
      characterIds.push(r.id);
      if (state.characterBriefsKnown[i]) knownIds.add(r.id);
    }

    const chat = await api("POST", "/api/chats", {
      name: state.name || "New story",
      scenario: state.scenario
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
        class: "item",
        onclick: () => charEditor(character)
      },
      el("span", {}, character.name),
      el(
        "div",
        { class: "row" },
        el(
          "button",
          {
            title: "Export",
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
            title: "Delete",
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
        class: "item",
        onclick: () => personaEditor(persona)
      },
      el("span", {}, persona.name),
      el(
        "div",
        { class: "row" },
        el(
          "button",
          {
            title: "Export",
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
            title: "Delete",
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
        onclick: () => loreModal(book.id)
      },
      el(
        "span",
        {},
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
          await loreModal(result.id);
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

function resizeComposer() {
  const input = $("#input");
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 220) + "px";
}

$("#input").addEventListener("input", resizeComposer);

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
    { input: text, frame_id: S.currentFrameId }
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
  if (S.chatId) {
    const q = S.currentFrameId != null ? `?frame_id=${S.currentFrameId}` : "";
    api("POST", `/api/chats/${S.chatId}/abort${q}`);
  }
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

boot().catch(e => toast("Could not load the app: " + (e?.message || e), "err", 0));