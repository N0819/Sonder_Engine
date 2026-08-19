// The "fill body and clothing" button, shared by both card editors.
//
// `readDraft` returns what the author currently has TYPED, which is not what is
// saved -- generating from the stored copy would ignore the two lines they just
// wrote, which is exactly the moment anyone presses this. Nothing is written:
// the proposal reopens the editor unsaved, and the author's ordinary Save is
// still what commits it.
function appearanceFillButton(kind, card, readDraft, reopen) {
  const path = kind === "character" ? "characters" : "personas";
  const button = el("button", {
    title: "Generate the body and the starting outfit from this card and your notes",
    onclick: async () => {
      const answer = await promptModalWithToggle(
        "What should this body and outfit be? Anything already on the card is "
        + "kept — describe build, colouring, bearing, what they wear and how "
        + "they wear it, or leave it blank and let the rest of the card decide.",
        "Also write what each clothed region shows underneath",
        { toggleNote: "Body description under the clothes, region by region. "
            + "Written onto the card only if you tick this, and used in play "
            + "only while the matching switch in Settings is on." });
      if (answer === null) return;
      const label = button.textContent;
      button.textContent = "Generating…";
      button.disabled = true;
      try {
        const r = await api("POST", `/api/${path}/${card.id}/fill_appearance`,
          { prompt: answer.text, beneath: answer.checked, draft: readDraft() });
        const refreshed = {
          ...card,
          name: r.sheet?.identity?.name || card.name,
          sheet: JSON.stringify(r.sheet)
        };
        closeAllModals();
        await boot();
        reopen(refreshed);
        toast("Body and clothing generated. Review, then save.", "ok");
        showCardWarnings(r);
      } catch (e) {
        toast(`Appearance fill failed: ${e.message}`, "err");
        button.textContent = label;
        button.disabled = false;
      }
    }
  }, "✨ Fill body & clothing");
  return button;
}

function defaultCharacterSheet() {
  return {
    identity: { name: "New Character", aliases: [], pronouns: { subject: "they", object: "them", possessive: "their" } },
    initial_outfit: { regions: {} },
    simulation: { tier: "mid", temperature: 0.8, sampler: {}, offscreen_agent: false },
    embodiment: { senses: [{ channel: "general", acuity: "ordinary", range: "ordinary", notes: "ordinary human senses" }], visible: { summary: "A person of unremarkable appearance.", build: "", face: "", hair: "", eyes: "", distinctive_features: [] }, scent: "", latent: [], interoception: { acuity: 0.5, pain_sensitivity: 0.5, fatigue_sensitivity: 0.5, pleasure_sensitivity: 0.5 } },
    psychology: { drive: { essence: "", expression: "", taboo: "" }, capacity: "", traits: [], values: [], self_model: { summary: "", protected_beliefs: [], pride_triggers: [], shame_triggers: [], beliefs: [] }, coping: { under_stress: [], default_conflict_style: "", strategies: [], recovery_supports: [] }, stress_profile: { baseline_reactivity: 0.5, recovery_rate: 0.5, overload_threshold: 0.8, attentional_style: "", somatic_signs: [] }, learning: { associations: [] } },
    social: { voice: { register: "", cadence: "", verbosity: "natural", markers: [], notes: "" }, baseline_stances: { unknown_person: { trust: 0, warmth: 0, threat_sensitivity: 0 } } },
    competence: { abilities: [] },
    knowledge: { access_tags: ["common"], excluded_titles: [], public_history: "", private_history: [] },
    initial_state: { mood: { label: "neutral", valence: 0, arousal: 0 }, goals: [], active_concerns: [], stress: { activation: 0, load: 0, coping_mode: "" }, hedonic: { pain: 0, pleasure: 0, source: "" } },
    opening: { first_message: "" }
  };
}

// ---- Carrying the fields an editor has no widget for ----
//
// A card editor rebuilds its sheet field by field from its widgets, and the
// PUT that saves it REPLACES the stored sheet wholesale -- there is no merge
// on the server. Every field the editor has no widget for therefore dies the
// first time anyone opens the card, and `_deep_defaults` backfills the hole
// on the way back out, so the loss reads as a value somebody chose rather
// than as a deletion. Measured on three live fields: `simulation.sampler`
// (read by `character_sampler` and passed to the model call),
// `simulation.curiosity` (reverted to 0.5 every save), and
// `psychology.projects` -- a life's work a character adopted mid-play, erased
// by looking at their card.
//
// The rule is structural rather than a list of those three, because the
// fourth field would be lost the same way: what the editor PRESENTS it owns,
// and what it does not present it carries forward unchanged. Arrays and
// scalars the editor built always win -- clearing a list is an authored act.
// Only a path the editor rebuilds WHOLE is exempt; see OWNED_SHEET_PATHS.
function carryUnpresentedFields(stored, built, owned, path) {
  const isMap = v => !!v && typeof v === "object" && !Array.isArray(v);
  if (!isMap(stored) || !isMap(built)) return built;
  const out = { ...built };
  for (const key of Object.keys(stored)) {
    const here = path ? path + "." + key : key;
    if ((owned || []).includes(here)) continue;
    if (!(key in out)) out[key] = stored[key];
    else out[key] = carryUnpresentedFields(stored[key], out[key], owned, here);
  }
  return out;
}

// Paths whose widget rebuilds the entire subtree, so an absence underneath
// one is an authored DELETION rather than a field the editor never knew
// about. `initial_outfit` is the whole list: `regions` is a map the garment
// widget rebuilds from scratch, so carrying a stored region back resurrects a
// garment the author just removed -- and `wearing`/`state` are derived
// mirrors `character_schema._normalize_initial_outfit` folds back INTO
// `regions`, which would let the same garment return through the other door.
const OWNED_SHEET_PATHS = ["initial_outfit"];

// Editable, swipeable greetings for a saved character card. Greetings are
// captured at import (first_mes + alternate_greetings, stored on
// sheet.opening.greetings) and can be added/edited/removed here; the list is
// read back into the main character Save. {{PLAYER}} is the neutral player
// token, substituted with the real persona name when a story launches.
// Returns { node, read } -- read() yields the current (edited) greetings list.
function greetingCarousel(character, initial) {
  const list = (initial || []).map(g => ({ ...g }));
  let i = 0;

  const counter = el("span", { class: "small dim" });
  const ta = el("textarea", {
    style: "width:100%;min-height:120px;margin-top:6px;font-size:13px",
    placeholder: "Greeting prose — shown verbatim as the opening scene. "
      + "Use {{PLAYER}} where the player's name should appear."
  });
  ta.oninput = () => {
    if (list[i]) { list[i].prose = ta.value; list[i].extraction = null; }
  };
  const slot = el("div");
  const render = () => {
    slot.innerHTML = "";
    if (!list.length) {
      counter.textContent = "0 greetings";
      slot.append(el("div", { class: "small dim", style: "margin-top:6px" },
        "No greetings yet — add one, or recover them from the imported card."));
      return;
    }
    i = Math.max(0, Math.min(i, list.length - 1));
    counter.textContent = `Greeting ${i + 1} / ${list.length}`;
    ta.value = list[i].prose || "";
    slot.append(ta);
  };

  const prev = el("button", { title: "Previous greeting",
    onclick: () => { i -= 1; render(); } }, "‹");
  const next = el("button", { title: "Next greeting",
    onclick: () => { i += 1; render(); } }, "›");
  const add = el("button", { title: "Add a greeting",
    onclick: () => {
      list.push({
        greeting_id: "greet_" + Math.random().toString(16).slice(2, 18),
        prose: "", extraction: null, extractor_version: null
      });
      i = list.length - 1; render();
    } }, "＋ Add");
  const del = el("button", { title: "Remove this greeting",
    onclick: () => { if (list.length) { list.splice(i, 1); render(); } } }, "🗑");
  const gen = el("button", { title: "Generate a greeting in this character's voice",
    onclick: async () => {
      // Optional situation brief -- blank lets the model invent a fitting moment.
      const brief = await promptModal(
        "Situation for the greeting? (optional — leave blank to let the model choose)");
      if (brief === null) return;  // cancelled
      const label = gen.textContent;
      gen.textContent = "…"; gen.disabled = true;
      try {
        const r = await api("POST",
          `/api/characters/${character.id}/generate_greeting`, { prompt: brief });
        list.push({ ...r.greeting });
        i = list.length - 1; render();
        toast("Greeting generated — edit it if you like, then save or quick-start.", "ok");
      } catch (e) {
        toast(`Generate failed: ${e.message}`, "err");
      } finally { gen.textContent = label; gen.disabled = false; }
    } }, "✨ Generate");
  const recover = el("button", { title: "Recover greetings from the imported card",
    onclick: async () => {
      try {
        const r = await api("POST", `/api/characters/${character.id}/recover_greetings`);
        list.length = 0;
        (r.greetings || []).forEach(g => list.push({ ...g }));
        if (r.sheet) character.sheet = JSON.stringify(r.sheet);
        i = 0; render();
        toast(`Recovered ${list.length} greeting(s) from the card.`, "ok");
      } catch (e) { toast(`Recover failed: ${e.message}`, "err"); }
    } }, "⟲ Recover from card");
  const quick = el("button", { class: "primary",
    onclick: () => {
      if (!list.length) { toast("Add a greeting first.", "warn"); return; }
      // Persist current greetings before launch -- start_story reads the DB.
      const stored = JSON.parse(character.sheet);
      const updated = { ...stored,
        opening: { ...(stored.opening || {}),
          greetings: list.map(g => ({ ...g })),
          first_message: list[i] ? list[i].prose : (stored.opening || {}).first_message } };
      const idx = i;
      api("PUT", "/api/characters/" + character.id, { sheet: updated })
        .then(() => { character.sheet = JSON.stringify(updated); quickStartModal(character, idx); })
        .catch(e => toast(`Could not save greetings: ${e.message}`, "err"));
    } }, "⚡ Quick start with this greeting");

  render();
  return {
    node: el("div", { style: "margin-bottom:4px" },
      el("div", { class: "row", style: "align-items:center;gap:6px;flex-wrap:wrap" },
        prev, counter, next, add, gen, del, el("span", { class: "spacer" }), recover),
      slot,
      el("div", { class: "row", style: "margin-top:8px" }, quick)),
    read: () => list.map(g => ({ ...g }))
  };
}

// Persona picker -> POST /api/characters/{id}/start with the chosen greeting
// index. The greeting becomes the opening scene (shown verbatim); the pipeline
// runs underneath it. See greetings.start_story / docs/design/GREETING_IMPORT_DESIGN.md.
function quickStartModal(character, greetingIndex) {
  const personas = S.boot.personas || [];
  if (!personas.length) {
    toast("Create a persona first — quick start needs someone to play as.", "warn");
    return;
  }
  const sel = el("select", { style: "width:100%;margin-top:6px" },
    ...personas.map(p => el("option", { value: String(p.id) }, p.name)));
  const books = S.boot.lorebooks || [];
  const loreSel = el("select", { style: "width:100%;margin-top:6px" },
    el("option", { value: "" }, "— none —"),
    ...books.map(b => el("option", { value: String(b.id) },
      b.name + (b.book_type && b.book_type !== "general" ? ` (${b.book_type})` : ""))));
  const knownCb = el("input", {
    type: "checkbox", checked: "",
    title: character.name + " already knows your persona by name from the start. "
      + "Uncheck for a strangers-meeting greeting, so they don't begin knowing "
      + "your name."
  });
  modal(`Quick start — ${character.name}`, b => {
    b.append(
      el("div", { class: "small dim" },
        "Play as which persona? The greeting you selected becomes the opening "
        + "scene, shown to you verbatim."),
      sel,
      el("label", { class: "small dim", style: "display:block;margin-top:10px" },
        "Attach a lorebook (optional)"),
      loreSel,
      el("label", { class: "row small dim", style: "gap:6px;margin-top:10px" },
        knownCb, character.name + " already knows me"),
      el("div", { class: "row", style: "margin-top:12px" },
        el("button", {
          class: "primary",
          onclick: () => {
            const persona_id = +sel.value;
            const lorebook_id = loreSel.value ? +loreSel.value : null;
            backgroundTask("Starting story",
              () => api("POST", `/api/characters/${character.id}/start`,
                { persona_id, greeting_index: greetingIndex, lorebook_id,
                  already_known: knownCb.checked }),
              {
                onSuccess: async r => {
                  closeAllModals();
                  await boot();
                  await openChat(r.chat_id);
                  // The last moment before the card starts BEHAVING.
                  showCardWarnings(r);
                },
                successMessage: "Story started.",
                errorPrefix: "Quick start failed"
              });
          }
        }, "⚡ Start story")));
  });
}

function charEditor(c, options = {}) {
  const chatId = options.chatId ?? null;
  const isChatCard = chatId !== null;
  const sheet = c ? JSON.parse(c.sheet) : defaultCharacterSheet();
  const f = {};
  const greetings = Array.isArray(sheet.opening?.greetings)
    ? sheet.opening.greetings : [];
  // Editable greetings box (saved characters only -- it needs a real id to
  // save/recover/quick-start against). gc.read() feeds back into Save below.
  const gc = c && !isChatCard ? greetingCarousel(c, greetings) : null;

  f.name = fText("Name", sheet.identity?.name);
  if (isChatCard) {
    const nameInput = f.name.node.querySelector("input");
    if (nameInput) nameInput.disabled = true;
  }
  f.aliases = fStrList("Aliases", sheet.identity?.aliases);
  f.pronouns = fPronouns("Pronouns", sheet.identity?.pronouns);
  // Regions are the only place clothing is authored. The card's legacy flat
  // `wearing` list is migrated into regions by character_schema on read, so an
  // older or imported card arrives here with its clothes already placed -- and
  // with `attire.region_of`'s guess visible, where it can be corrected.
  f.outfit_regions = fAttireGarments(
    "Starting clothes", sheet.initial_outfit?.regions
  );
  f.tier = fSelect("Tier", [["bg", "background"], ["mid", "recurring"], ["major", "major/antagonist"]], sheet.simulation?.tier);
  f.temperature = fNum("Temperature (0.5–1.1)", sheet.simulation?.temperature, "0.05");
  f.offscreen_agent = el("label", { class: "tgl", style: "margin-top:8px" },
    el("input", { type: "checkbox" }),
    " Allow this character to act autonomously while off screen");
  f.offscreen_agent.querySelector("input").checked = Boolean(sheet.simulation?.offscreen_agent);

  f.summary = fArea(
    "Body appearance — stable visible features, excluding clothing",
    sheet.embodiment?.visible?.summary, 3
  );
  f.scent = fText(
    "Body scent — what this body standingly smells of, excluding clothing",
    sheet.embodiment?.scent
  );
  f.senses = fSenses("Senses", sheet.embodiment?.senses);
  f.build = fText("Build", sheet.embodiment?.visible?.build);
  f.face = fText("Face", sheet.embodiment?.visible?.face);
  f.hair = fText("Hair", sheet.embodiment?.visible?.hair);
  f.eyes = fText("Eyes", sheet.embodiment?.visible?.eyes);
  f.distinctive = fLineList("Distinctive features (one per line)", sheet.embodiment?.visible?.distinctive_features);
  f.latent = fLatent("Latent/hidden capabilities (powers, secret identities, equipment functions)", sheet.embodiment?.latent);
  f.extra_parts = fExtraParts("Extra body parts (tails, wings, horns…) — where each emerges, from menus", sheet.embodiment?.extra_parts);
  f.intero_acuity = fNum("Interoceptive acuity (0..1)", sheet.embodiment?.interoception?.acuity, "0.1");
  f.pain_sensitivity = fNum("Pain sensitivity (0..1)", sheet.embodiment?.interoception?.pain_sensitivity, "0.1");
  f.fatigue_sensitivity = fNum("Fatigue sensitivity (0..1)", sheet.embodiment?.interoception?.fatigue_sensitivity, "0.1");
  f.pleasure_sensitivity = fNum("Pleasure sensitivity (0..1)", sheet.embodiment?.interoception?.pleasure_sensitivity, "0.1");

  f.drive_essence = fText("Drive — essence (the deepest thing they pursue/protect)", sheet.psychology?.drive?.essence);
  f.drive_expression = fText("Drive — expression (how it shows in ACTION, incl. their initiative)", sheet.psychology?.drive?.expression);
  f.drive_taboo = fText("Drive — taboo (the line they will not cross)", sheet.psychology?.drive?.taboo);
  // How much this mind holds at once (affect.CAPACITY_LADDER). The blank
  // option is stored blank on purpose: it behaves as "ordinary" everywhere,
  // and keeping it distinguishable is what lets the import warning say the
  // field was never authored rather than silently claiming the middle.
  f.capacity = fSelect("Attentional capacity (wants / commitments held at once)", [
    ["", "not set — ordinary (3 wants, 4 commitments)"],
    ["narrow", "narrow — one thing at a time (1 / 2)"],
    ["focused", "focused — a purpose and one pull against it (2 / 3)"],
    ["ordinary", "ordinary — the human middle (3 / 4)"],
    ["broad", "broad — keeps more in the air than most (4 / 5)"],
    ["wide", "wide — several commitments live at once (5 / 6)"],
  ], sheet.psychology?.capacity || "");
  f.traits = fTraits("Core traits", sheet.psychology?.traits);
  f.values = fValues("Core values", sheet.psychology?.values);
  f.self_summary = fArea("Self-model summary", sheet.psychology?.self_model?.summary, 3);
  f.protected = fLineList("Protected beliefs", sheet.psychology?.self_model?.protected_beliefs);
  f.pride = fLineList("Pride triggers", sheet.psychology?.self_model?.pride_triggers);
  f.shame = fLineList("Shame triggers", sheet.psychology?.self_model?.shame_triggers);
  f.beliefs = fBeliefs("Durable self/world beliefs", sheet.psychology?.self_model?.beliefs);
  f.coping = fArea("Coping under stress", sheet.psychology?.coping?.under_stress?.join(", "), 2);
  f.conflict = fText("Default conflict style", sheet.psychology?.coping?.default_conflict_style);
  f.coping_strategies = fCopingStrategies("Coping strategies", sheet.psychology?.coping?.strategies);
  f.recovery_supports = fLineList("Recovery supports", sheet.psychology?.coping?.recovery_supports);
  f.stress_reactivity = fNum("Baseline stress reactivity (0..1)", sheet.psychology?.stress_profile?.baseline_reactivity, "0.1");
  f.stress_recovery = fNum("Stress recovery rate (0..1)", sheet.psychology?.stress_profile?.recovery_rate, "0.1");
  f.overload_threshold = fNum("Overload threshold (0..1)", sheet.psychology?.stress_profile?.overload_threshold, "0.1");
  f.attentional_style = fText("Attention under stress", sheet.psychology?.stress_profile?.attentional_style);
  f.somatic_signs = fLineList("Characteristic stress signs", sheet.psychology?.stress_profile?.somatic_signs);
  f.associations = fAssociations("Learned cue-response associations", sheet.psychology?.learning?.associations);

  f.voice_register = fText("Voice register", sheet.social?.voice?.register);
  f.voice_cadence = fText("Voice cadence", sheet.social?.voice?.cadence);
  f.voice_verbosity = fSelect("Voice verbosity", [["terse", "terse"], ["natural", "natural"], ["chatty", "chatty"]], sheet.social?.voice?.verbosity);
  f.voice_markers = fLineList("Voice markers", sheet.social?.voice?.markers);
  f.voice_notes = fArea("Voice notes", sheet.social?.voice?.notes, 2);

  f.trust = fNum("Baseline trust (unknown person)", sheet.social?.baseline_stances?.unknown_person?.trust, "0.1");
  f.warmth = fNum("Baseline warmth", sheet.social?.baseline_stances?.unknown_person?.warmth, "0.1");
  f.threat = fNum("Baseline threat sensitivity", sheet.social?.baseline_stances?.unknown_person?.threat_sensitivity, "0.1");

  f.abilities = fAbilities("Abilities", sheet.competence?.abilities);

  f.knowledge_common = el("input", { type: "checkbox", ...(sheet.knowledge?.access_tags?.includes("common") ? { checked: "" } : {}) });
  f.knowledge_scholarly = el("input", { type: "checkbox", ...(sheet.knowledge?.access_tags?.includes("scholarly") ? { checked: "" } : {}) });
  f.knowledge_esoteric = el("input", { type: "checkbox", ...(sheet.knowledge?.access_tags?.includes("esoteric") ? { checked: "" } : {}) });
  f.excluded_titles = fLineList("Excluded knowledge titles", sheet.knowledge?.excluded_titles);
  f.public_history = fArea("Public history (world could know)", sheet.knowledge?.public_history, 3);

  f.mood = fText("Current mood label", sheet.initial_state?.mood?.label);
  f.valence = fNum("Mood valence (-1..1)", sheet.initial_state?.mood?.valence, "0.1");
  f.arousal = fNum("Mood arousal (0..1)", sheet.initial_state?.mood?.arousal, "0.1");
  f.goals = fGoals("Standing goals (durable objectives the character actively pursues)", sheet.initial_state?.goals);
  f.active_concerns = fLineList("Active concerns", sheet.initial_state?.active_concerns);
  f.initial_stress = fNum("Initial stress activation (0..1)", sheet.initial_state?.stress?.activation, "0.1");
  f.initial_load = fNum("Initial cumulative stress load (0..1)", sheet.initial_state?.stress?.load, "0.1");
  f.initial_coping = fText("Initial active coping mode", sheet.initial_state?.stress?.coping_mode);
  f.initial_pain = fNum("Initial pain (0..1)", sheet.initial_state?.hedonic?.pain, "0.1");
  f.initial_pleasure = fNum("Initial pleasure (0..1)", sheet.initial_state?.hedonic?.pleasure, "0.1");
  f.initial_hedonic_source = fText("Initial pain/pleasure source", sheet.initial_state?.hedonic?.source);

  f.first_message = fArea("First message (optional, for scene open)", sheet.opening?.first_message, 3);
  const ph = phEditor(sheet.knowledge?.private_history, true);
  const fillPsychology = c && !isChatCard ? el("button", {
    title: "Generate only missing psychology fields; populated fields are preserved",
    onclick: async () => {
      const brief = await promptModal(
        "What kind of person is this? Describe formative pressures, what reliably "
        + "sets them off or settles them, how their values conflict, how they cope "
        + "under stress, and any learned sensitivities or recurring cues.");
      if (brief === null) return;
      const label = fillPsychology.textContent;
      fillPsychology.textContent = "Filling…";
      fillPsychology.disabled = true;
      try {
        const r = await api("POST", `/api/characters/${c.id}/fill_psychology`,
          { prompt: brief });
        const refreshed = {
          ...c,
          name: r.sheet?.identity?.name || c.name,
          sheet: JSON.stringify(r.sheet)
        };
        closeAllModals();
        await boot();
        charEditor(refreshed);
        toast("Missing psychology fields filled. Review and save any edits.", "ok");
        showCardWarnings(r);
      } catch (e) {
        toast(`Psychology fill failed: ${e.message}`, "err");
        fillPsychology.textContent = label;
        fillPsychology.disabled = false;
      }
    }
  }, "✨ Fill psychology gaps") : null;

  const fillAppearance = c && !isChatCard
    ? appearanceFillButton("character", c, () => ({
        appearance: {
          summary: f.summary.read(), build: f.build.read(), face: f.face.read(),
          hair: f.hair.read(), eyes: f.eyes.read(),
          distinctive_features: f.distinctive.read()
        },
        extra_parts: f.extra_parts.read(),
        initial_outfit: { regions: f.outfit_regions.read() }
      }), refreshed => charEditor(refreshed))
    : null;

  modal(
    isChatCard
      ? "Edit story card — " + sheet.identity?.name
      : c ? "Edit character — " + sheet.identity?.name : "New character",
    b => {
    if (isChatCard) {
      b.append(el("div", { class: "card small dim" },
        "This is a story-specific card. Changes affect this story only. "
        + "Live mood, stress, memories, relationships, and physical state are "
        + "preserved. Name and identity are locked because scene history uses "
        + "them as stable keys."));
    }
    if (gc) {
      b.append(el("div", { class: "card" },
        el("div", { style: "font-weight:600;margin-bottom:2px" }, "Greetings"),
        el("div", { class: "small dim", style: "margin-bottom:8px" },
          "Swipe, add, or remove greetings, and start a story from the one you "
          + "pick — it becomes the opening scene. Edits save with the character."),
        gc.node));
    }
    b.append(
      el("details", { open: "" }, el("summary", {}, "Identity & Simulation"),
        f.name.node, f.aliases.node, f.pronouns.node,
        el("div", { class: "small dim" },
          "Appearance describes the body and stable visible features. Initial "
          + "outfit is copied into the story's live attire state, where it can "
          + "later be changed without rewriting this card."),
        f.outfit_regions.node,
        el("div", { class: "small dim" },
          "Each garment covers part of a body, which is what lets the story "
          + "undress someone one piece at a time — worn, then loosened, then "
          + "open, then off, a step per beat — and lets a spill or a tear "
          + "belong to the garment, so it goes with the shirt when the shirt "
          + "comes off. Most clothing is not one body part: a kimono or a "
          + "toga is the whole body, a dress is shoulders to ankles, a coat "
          + "goes over the shoulders. Leave the coverage on “auto” and it is "
          + "worked out from the name. Note that waist means the belt line "
          + "only — a sash does not cover the groin. List the outermost "
          + "garment first. \"Underneath\" is what a region shows once "
          + "nothing covers it, and is used only when it has been switched "
          + "on in Settings."),
        fillAppearance,
        f.tier.node, f.temperature.node, f.offscreen_agent,
        el("div", { class: "small dim" },
          "Opt-in only. It does nothing unless this story also enables the "
          + "character-agent ceiling; off-screen decisions use only this "
          + "character's own carried knowledge.")),
      el("details", { open: "" }, el("summary", {}, "Embodiment (Visible & Senses)"),
        f.summary.node, f.scent.node, f.senses.node, f.build.node,
        f.face.node, f.hair.node,
        f.eyes.node, f.distinctive.node, f.latent.node,
        el("div", { class: "small dim", style: "margin-top:8px" },
          "Extra body parts are structured, not prose: declare a part once, "
          + "with where it emerges, and the story can see it, cover it, and "
          + "touch it deterministically. “Through clothing” means garments "
          + "over that region are worn around it (a tail through a skirt); "
          + "unchecked, the part hides under clothing that covers the region."),
        f.extra_parts.node,
        el("div", { class: "small dim", style: "margin-top:8px" },
          "Interoception controls how strongly this character notices internal "
          + "body signals. Pain and pleasure work even when survival mode is off."),
        f.intero_acuity.node, f.pain_sensitivity.node, f.fatigue_sensitivity.node,
        f.pleasure_sensitivity.node),
      el("details", { open: "" }, el("summary", {}, "Psychology & Coping"),
        el("div", { class: "small dim", style: "margin-bottom:6px" },
          "Drive is the character's core motivation — the engine derives their proactive "
          + "wants from it every beat. A blank drive makes the character passive."),
        fillPsychology,
        f.drive_essence.node, f.drive_expression.node, f.drive_taboo.node,
        f.capacity.node,
        f.traits.node, f.values.node, f.self_summary.node, f.protected.node,
        f.pride.node, f.shame.node, f.beliefs.node, f.coping.node, f.conflict.node,
        f.coping_strategies.node, f.recovery_supports.node,
        f.stress_reactivity.node, f.stress_recovery.node,
        f.overload_threshold.node, f.attentional_style.node,
        f.somatic_signs.node, f.associations.node),
      el("details", { open: "" }, el("summary", {}, "Social & Voice"),
        f.voice_register.node, f.voice_cadence.node, f.voice_verbosity.node, f.voice_markers.node, f.voice_notes.node,
        f.trust.node, f.warmth.node, f.threat.node),
      el("details", { open: "" }, el("summary", {}, "Competence"), f.abilities.node),
      el("details", { open: "" }, el("summary", {}, "Knowledge & History"),
        el("div", { class: "ff" }, el("label", {}, "Knowledge levels"),
          el("div", { class: "row" },
            el("label", { class: "tgl" }, f.knowledge_common, " common"),
            el("label", { class: "tgl" }, f.knowledge_scholarly, " scholarly"),
            el("label", { class: "tgl" }, f.knowledge_esoteric, " esoteric"))),
        f.excluded_titles.node, f.public_history.node),
      el("details", { open: "" }, el("summary", {}, "Initial State & Opening"),
        f.mood.node, f.valence.node, f.arousal.node, f.goals.node,
        f.active_concerns.node, f.initial_stress.node, f.initial_load.node,
        f.initial_coping.node, f.initial_pain.node, f.initial_pleasure.node,
        f.initial_hedonic_source.node, f.first_message.node),
      el("details", { open: "" }, el("summary", {}, "Private history"),
        el("div", { class: "small dim" }, "Secrets only this character (and anyone tagged in known_by) knows."), ph.node),
      el("div", { class: "row", style: "margin-top:10px" },
        el("button", { class: "primary", onclick: async () => {
          const access_tags = [];
          if (f.knowledge_common.checked) access_tags.push("common");
          if (f.knowledge_scholarly.checked) access_tags.push("scholarly");
          if (f.knowledge_esoteric.checked) access_tags.push("esoteric");

          // Everything below is what the widgets OWN. Anything else the
          // stored sheet carries is merged back by carryUnpresentedFields --
          // without it a full-replacement PUT behind a field-by-field editor
          // deletes every field that has no widget.
          const s = carryUnpresentedFields(sheet, {
            identity: {
              uid: sheet.identity?.uid,
              name: f.name.read(),
              aliases: f.aliases.read(),
              pronouns: f.pronouns.read()
            },
            // `wearing` is derived from the regions by the schema, never
            // sent from here -- two authored copies of one outfit is how the
            // ledger ends up saying different things about the same body.
            initial_outfit: { regions: f.outfit_regions.read() },
            // No `sampler` key: there is no widget for it, so writing one
            // here would erase whatever was authored or imported into it. It
            // rides the carry with every other unpresented field.
            simulation: { tier: f.tier.read(), temperature: f.temperature.read(),
              offscreen_agent: f.offscreen_agent.querySelector("input").checked },
            embodiment: {
              senses: f.senses.read(),
              visible: { summary: f.summary.read(), build: f.build.read(), face: f.face.read(), hair: f.hair.read(), eyes: f.eyes.read(), distinctive_features: f.distinctive.read() },
              scent: f.scent.read(),
              latent: f.latent.read(),
              extra_parts: f.extra_parts.read(),
              interoception: {
                acuity: f.intero_acuity.read() ?? 0.5,
                pain_sensitivity: f.pain_sensitivity.read() ?? 0.5,
                fatigue_sensitivity: f.fatigue_sensitivity.read() ?? 0.5,
                pleasure_sensitivity: f.pleasure_sensitivity.read() ?? 0.5
              }
            },
            psychology: {
              drive: { essence: f.drive_essence.read(), expression: f.drive_expression.read(), taboo: f.drive_taboo.read() },
              capacity: f.capacity.read(),
              traits: f.traits.read(),
              values: f.values.read(),
              self_model: {
                summary: f.self_summary.read(), protected_beliefs: f.protected.read(),
                pride_triggers: f.pride.read(), shame_triggers: f.shame.read(),
                beliefs: f.beliefs.read()
              },
              coping: {
                under_stress: splitCL(f.coping.read()),
                default_conflict_style: f.conflict.read(),
                strategies: f.coping_strategies.read(),
                recovery_supports: f.recovery_supports.read()
              },
              stress_profile: {
                baseline_reactivity: f.stress_reactivity.read() ?? 0.5,
                recovery_rate: f.stress_recovery.read() ?? 0.5,
                overload_threshold: f.overload_threshold.read() ?? 0.8,
                attentional_style: f.attentional_style.read(),
                somatic_signs: f.somatic_signs.read()
              },
              learning: { associations: f.associations.read() }
            },
            social: {
              voice: { register: f.voice_register.read(), cadence: f.voice_cadence.read(), verbosity: f.voice_verbosity.read(), markers: f.voice_markers.read(), notes: f.voice_notes.read() },
              baseline_stances: { unknown_person: { trust: f.trust.read() || 0, warmth: f.warmth.read() || 0, threat_sensitivity: f.threat.read() || 0 } }
            },
            competence: { abilities: f.abilities.read() },
            knowledge: { access_tags, excluded_titles: f.excluded_titles.read(), public_history: f.public_history.read(), private_history: ph.read() },
            initial_state: {
              mood: { label: f.mood.read(), valence: f.valence.read() || 0, arousal: f.arousal.read() || 0 },
              goals: f.goals.read(), active_concerns: f.active_concerns.read(),
              stress: {
                activation: f.initial_stress.read() || 0,
                load: f.initial_load.read() || 0,
                coping_mode: f.initial_coping.read()
              },
              hedonic: {
                pain: f.initial_pain.read() || 0,
                pleasure: f.initial_pleasure.read() || 0,
                source: f.initial_hedonic_source.read()
              }
            },
            // Persist the (possibly edited) greetings alongside first_message.
            // gc.read() is the live list from the greetings box; falling back to
            // the stored list keeps them intact for the new-character form.
            opening: {
              ...(sheet.opening || {}),
              first_message: f.first_message.read(),
              greetings: gc ? gc.read() : (sheet.opening?.greetings || [])
            }
          }, OWNED_SHEET_PATHS);
          try {
            let result = null;
            if (isChatCard) {
              result = await api(
                "PUT",
                `/api/chats/${chatId}/characters/${c.id}/card`,
                { sheet: s }
              );
            } else if (c) {
              result = await api("PUT", "/api/characters/" + c.id, { sheet: s });
            }
            else result = await api("POST", "/api/characters", { sheet: s });
            // Saving a card by hand is a card-producing surface like any
            // other, and the blank-card route is the one that produces the
            // empty drive by construction.
            showCardWarnings(result);
            if (result?.sheet && c) {
              c.sheet = JSON.stringify(result.sheet);
              c.name = result.sheet.identity?.name || c.name;
            }
            closeModal();
            if (!isChatCard) await boot();
            toast(
              isChatCard ? "Story character card saved."
                : c ? "Character saved." : "Character created.",
              "ok"
            );
          } catch (e) { toast(`Could not save: ${e.message}`, "err") }
        } }, "Save")));
  }, { wide: true });
}

function personaEditor(p) {
  const sheet = p ? JSON.parse(p.sheet) : {
    identity: { name: "New Persona", aliases: [], pronouns: { subject: "they", object: "them", possessive: "their" } },
    initial_outfit: { regions: {} },
    embodiment: {
      senses: [{ channel: "general", acuity: "ordinary", range: "ordinary", notes: "ordinary human senses" }],
      visible: { summary: "A person of unremarkable appearance.", build: "", face: "", hair: "", eyes: "", distinctive_features: [] },
      scent: "",
      latent: []
    },
    competence: { abilities: [] },
    knowledge: { public_history: "", private_history: [] },
    narration: { voice_setting: "" }
  };
  const f = {};
  f.name = fText("Name", sheet.identity?.name);
  f.aliases = fStrList("Aliases", sheet.identity?.aliases);
  f.pronouns = fPronouns("Pronouns", sheet.identity?.pronouns);
  // Regions are the only place clothing is authored. The card's legacy flat
  // `wearing` list is migrated into regions by character_schema on read, so an
  // older or imported card arrives here with its clothes already placed -- and
  // with `attire.region_of`'s guess visible, where it can be corrected.
  f.outfit_regions = fAttireGarments(
    "Starting clothes", sheet.initial_outfit?.regions
  );
  f.senses = fSenses("Senses", sheet.embodiment?.senses);
  f.appearance = fArea(
    "Body appearance — stable visible features, excluding clothing",
    sheet.embodiment?.visible?.summary, 3
  );
  f.scent = fText(
    "Body scent — what this body standingly smells of, excluding clothing",
    sheet.embodiment?.scent
  );
  f.build = fText("Build", sheet.embodiment?.visible?.build);
  f.face = fText("Face", sheet.embodiment?.visible?.face);
  f.hair = fText("Hair", sheet.embodiment?.visible?.hair);
  f.eyes = fText("Eyes", sheet.embodiment?.visible?.eyes);
  f.distinctive = fLineList("Distinctive features (one per line)", sheet.embodiment?.visible?.distinctive_features);
  f.latent = fLatent("Latent/hidden capabilities", sheet.embodiment?.latent);
  f.extra_parts = fExtraParts("Extra body parts (tails, wings, horns…) — where each emerges, from menus", sheet.embodiment?.extra_parts);
  f.public_history = fArea("Public history (world could know)", sheet.knowledge?.public_history, 3);
  f.voice_setting = fArea("Voice setting (PRIVATE — narrator only)", sheet.narration?.voice_setting, 3);
  f.abilities = fAbilities("Abilities", sheet.competence?.abilities);
  const fillAppearance = p ? appearanceFillButton("persona", p, () => ({
    appearance: {
      summary: f.appearance.read(), build: f.build.read(), face: f.face.read(),
      hair: f.hair.read(), eyes: f.eyes.read(),
      distinctive_features: f.distinctive.read()
    },
    extra_parts: f.extra_parts.read(),
    initial_outfit: { regions: f.outfit_regions.read() }
  }), refreshed => personaEditor(refreshed)) : null;
  const ph = phEditor(sheet.knowledge?.private_history, false);

  modal(p ? "Edit persona — " + sheet.identity?.name : "New persona", b => {
    b.append(
      el("details", { open: "" }, el("summary", {}, "Basic"),
        f.name.node, f.aliases.node, f.pronouns.node,
        el("div", { class: "small dim" },
          "Keep body appearance separate from clothing. Initial outfit seeds "
          + "the story's live attire state and can change during play."),
        f.outfit_regions.node,
        el("div", { class: "small dim" },
          "Each garment covers part of a body, which is what lets the story "
          + "undress someone one piece at a time — worn, then loosened, then "
          + "open, then off, a step per beat — and lets a spill or a tear "
          + "belong to the garment, so it goes with the shirt when the shirt "
          + "comes off. Most clothing is not one body part: a kimono or a "
          + "toga is the whole body, a dress is shoulders to ankles, a coat "
          + "goes over the shoulders. Leave the coverage on “auto” and it is "
          + "worked out from the name. Note that waist means the belt line "
          + "only — a sash does not cover the groin. List the outermost "
          + "garment first. \"Underneath\" is what a region shows once "
          + "nothing covers it, and is used only when it has been switched "
          + "on in Settings."),
        fillAppearance),
      el("details", { open: "" }, el("summary", {}, "Embodiment (Visible & Senses)"),
        f.appearance.node, f.scent.node, f.senses.node, f.build.node, f.face.node, f.hair.node, f.eyes.node, f.distinctive.node, f.latent.node,
        el("div", { class: "small dim", style: "margin-top:8px" },
          "Extra body parts are structured, not prose: declare a part once, "
          + "with where it emerges, and the story can see it, cover it, and "
          + "touch it deterministically."),
        f.extra_parts.node),
      el("details", { open: "" }, el("summary", {}, "History & Voice"), f.public_history.node, f.voice_setting.node),
      el("details", { open: "" }, el("summary", {}, "Abilities"), f.abilities.node),
      el("details", { open: "" }, el("summary", {}, "Private history"), ph.node),
      el("div", { class: "row", style: "margin-top:10px" },
        el("button", { class: "primary", onclick: async () => {
          const s = carryUnpresentedFields(sheet, {
            identity: {
              uid: sheet.identity?.uid,
              name: f.name.read(),
              aliases: f.aliases.read(),
              pronouns: f.pronouns.read()
            },
            // `wearing` is derived from the regions by the schema, never
            // sent from here -- two authored copies of one outfit is how the
            // ledger ends up saying different things about the same body.
            initial_outfit: { regions: f.outfit_regions.read() },
            embodiment: {
              senses: f.senses.read(),
              visible: { summary: f.appearance.read(), build: f.build.read(), face: f.face.read(), hair: f.hair.read(), eyes: f.eyes.read(), distinctive_features: f.distinctive.read() },
              scent: f.scent.read(),
              latent: f.latent.read(),
              extra_parts: f.extra_parts.read()
            },
            competence: { abilities: f.abilities.read() },
            knowledge: { public_history: f.public_history.read(), private_history: ph.read() },
            narration: { voice_setting: f.voice_setting.read() }
          }, OWNED_SHEET_PATHS);
          try {
            if (p) await api("PUT", "/api/personas/" + p.id, { sheet: s });
            else await api("POST", "/api/personas", { sheet: s });
            closeModal(); await boot(); toast(p ? "Persona saved." : "Persona created.", "ok");
          } catch (e) { toast(`Could not save: ${e.message}`, "err") }
        } }, "Save")));
  });
}

// ---- Background-character promotion ----
// A lighter review UI than the full charEditor form: the draft doesn't
// have a characters-table row yet (no id to save against), and the
// generated sheet is meant to be spot-checked against the evidence it
// was grounded in, not rebuilt field-by-field -- raw JSON + a plain
// per-line memory list matches how this app already lets you hand-edit
// less-common shapes (e.g. the pipeline drawer's step editor) rather
// than inventing a second bespoke form.
function promotionReviewModal(cid, name, draft) {
  const sheetTa = el("textarea", { style: "width:100%;height:340px" },
    JSON.stringify(draft.sheet, null, 2));
  const seedsTa = el("textarea", { style: "width:100%;height:90px" },
    draft.memory_seeds.join("\n"));

  modal(`Promote ${name}`, b => b.append(
    el("div", { class: "small dim", style: "margin-bottom:8px" },
      `Grounded in ${draft.evidence_turns.length} recorded turn(s) `
      + `(#${draft.evidence_turns.join(", #")}). Review before attaching -- `
      + "this becomes a real character going forward; past turns are untouched."),
    el("div", { class: "ff" }, el("label", {}, "Character sheet (JSON)"), sheetTa),
    el("div", { class: "ff", style: "margin-top:8px" },
      el("label", {}, "Starter memories (one per line)"), seedsTa),
    el("div", { class: "row", style: "margin-top:10px" },
      el("button", { class: "primary", onclick: async () => {
        let sheet;
        try { sheet = JSON.parse(sheetTa.value) }
        catch (e) { toast(`Invalid JSON: ${e.message}`, "err"); return }
        const memory_seeds = seedsTa.value.split("\n").map(s => s.trim()).filter(Boolean);
        try {
          const r = await api("POST", `/api/chats/${cid}/promotions/confirm`,
            { name, sheet, memory_seeds });
          closeModal();
          await boot();
          toast(name + " is now a full character.", "ok");
          // The draft's warnings were about the DRAFT; this sheet is
          // whatever the host approved after editing it.
          showCardWarnings(r);
        } catch (e) { toast(`Could not promote: ${e.message}`, "err") }
      } }, "✨ Confirm & attach"))));
}

async function promoteBackgroundPresence(cid, name) {
  let draft;
  try {
    draft = await api("POST", `/api/chats/${cid}/promotions/draft`, { name });
  } catch (e) {
    toast(`Could not draft promotion: ${e.message}`, "err");
    return;
  }
  promotionReviewModal(cid, name, draft);
}

// ---- Import (file upload) ----
function importModal(kind) {
  let fileContent = null;
  const acceptsImage = kind === "character" || kind === "persona";
  const status = el("div", { class: "small dim", style: "margin-top:8px" }, "No file selected");
  const fileIn = el("input", {
    type: "file",
    accept: acceptsImage ? ".json,application/json,.png,image/png" : ".json,application/json",
    style: "display:none"
  });
  const drop = el("div", { class: "filedrop", onclick: () => fileIn.click() },
    acceptsImage ? "Choose a JSON or PNG card" : "Choose a JSON file",
    el("div", { class: "small", style: "margin-top:5px" },
      acceptsImage ? "Native sheets, SillyTavern cards (JSON or PNG), and World Info"
                   : "Native sheets, SillyTavern cards and World Info"));
  fileIn.onchange = () => {
    const f = fileIn.files[0]; if (!f) return;
    status.textContent = "Reading " + f.name + "…"; status.className = "small dim";
    const isPng = acceptsImage && (f.type === "image/png" || /\.png$/i.test(f.name));
    const r = new FileReader();
    if (isPng) {
      r.onload = () => { fileContent = { png_base64: r.result }; status.textContent = "Loaded " + f.name + " ✓ (PNG card)"; status.className = "small" };
      r.onerror = () => { fileContent = null; status.textContent = "Failed to read file"; status.className = "small err" };
      r.readAsDataURL(f);
    } else {
      r.onload = () => {
        try { fileContent = JSON.parse(r.result); status.textContent = "Loaded " + f.name + " ✓"; status.className = "small" }
        catch (e) { fileContent = null; status.textContent = "Invalid JSON: " + e.message; status.className = "small err" }
      };
      r.readAsText(f);
    }
  };
  const re = el("input", { type: "checkbox", checked: true });
  const typeSel = kind === "lorebook" ? el("select", {}, S.boot.lorebook_types.map(t => el("option", { value: t }, t))) : null;
  const sumIn = kind === "lorebook" ? el("input", { placeholder: "Brief summary for the mapping agent", style: "width:100%" }) : null;

  modal(`Import ${kind}`, b => {
    b.append(drop, fileIn, status,
      kind === "lorebook" ? el("div", { class: "card" },
        el("div", { class: "ff" }, el("label", {}, "Book type"), typeSel),
        el("div", { class: "ff" }, el("label", {}, "Summary"), sumIn)) : null,
      el("label", { class: "tgl", style: "margin:11px 0" }, re, " AI reinterpretation"),
      el("div", { class: "small dim", style: "margin:-6px 0 11px 0" },
        "Recommended for everything except native sheets this app exported. "
        + "SillyTavern cards and World Info are built around free-text "
        + "description/personality prose that doesn't map cleanly onto Sonder's "
        + "structured character model, so reinterpretation rebuilds the card into "
        + "a proper native sheet (separating what's visible from what's hidden, "
        + "structured traits, and so on). Greetings and any embedded lorebook are "
        + "preserved verbatim either way."),
      el("div", { class: "row", style: "margin-top:12px" },
        el("button", { class: "primary", onclick: () => {
          if (!fileContent) { toast("Choose a valid JSON file first.", "warn"); return }
          const endpoint = { character: "/api/characters/import", persona: "/api/personas/import", lorebook: "/api/lorebooks/import" }[kind];
          const payload = kind === "character" ? { card: fileContent, reinterpret: re.checked }
            : kind === "persona" ? { card: fileContent, reinterpret: re.checked }
              : { book: fileContent, reinterpret: re.checked, book_type: typeSel.value, summary: sumIn.value };
          backgroundTask(`Importing ${kind}`, () => api("POST", endpoint, payload),
            { onSuccess: async r => {
              await boot();
              if (kind === "lorebook" && r?.id) await openLoreWorkspace(r.id);
              // A card with no drive imports cleanly and then reads as a dull
              // character rather than an unfilled field. Say so.
              showCardWarnings(r);
            },
             successMessage: kind.charAt(0).toUpperCase() + kind.slice(1) + " imported.",
             errorPrefix: kind.charAt(0).toUpperCase() + kind.slice(1) + " import failed" });
        } }, "Import")));
  });
}

// ---- Generate ----
function generateModal(kind) {
  const ta = el("textarea", { style: "width:100%;height:170px", placeholder: "Describe the " + kind + " you want…" });
  modal(`Generate ${kind}`, b => {
    b.append(ta,
      el("div", { class: "small dim", style: "margin-top:8px" }, "The dialog will close when generation starts. Progress is visible in the activity panel."),
      el("div", { class: "row", style: "margin-top:11px" },
        el("button", { class: "primary", onclick: () => {
          const prompt = ta.value.trim();
          backgroundTask(`Generating ${kind}`,
            () => api("POST", `/api/${kind === "character" ? "characters" : "personas"}/generate`, { prompt }),
            { onSuccess: async () => { await boot() },
             successMessage: kind.charAt(0).toUpperCase() + kind.slice(1) + " generated.",
             errorPrefix: kind.charAt(0).toUpperCase() + kind.slice(1) + " generation failed" });
        } }, "Generate")));
  });
}

// ---- Lorebook generate ----
function generateLoreModal(lid) {
  const ta = el("textarea", { style: "width:100%;height:170px", placeholder: "Describe the entries to create…" });
  modal("Generate lorebook entries", b => {
    b.append(ta,
      el("div", { class: "small dim", style: "margin-top:8px" }, "Generation continues after this dialog closes."),
      el("div", { class: "row", style: "margin-top:11px" },
        el("button", { class: "primary", onclick: () => {
          backgroundTask("Generating lorebook entries",
            () => api("POST", `/api/lorebooks/${lid}/generate`, { prompt: ta.value.trim() }),
            { onSuccess: async r => { await boot(); if (r?.added) await openLoreWorkspace(lid) },
             successMessage: r => `Generated ${r?.added || 0} entries.`,
             errorPrefix: "Lore generation failed" });
        } }, "Generate entries")));
  });
}

// ---- Export ----
async function exportCharacter(id) {
  try { const d = await api("GET", `/api/characters/${id}/export`); downloadJSON(d, (d.data?.identity?.name || d.name || "character").replace(/[^a-z0-9_-]/gi, "_") + ".json"); toast("Character exported.", "ok"); }
  catch (e) { toast(`Export failed: ${e.message}`, "err") }
}
async function exportPersona(id) {
  try { const d = await api("GET", `/api/personas/${id}/export`); downloadJSON(d, (d.data?.identity?.name || d.name || "persona").replace(/[^a-z0-9_-]/gi, "_") + ".json"); toast("Persona exported.", "ok"); }
  catch (e) { toast(`Export failed: ${e.message}`, "err") }
}
async function exportLorebook(id) {
  try { const d = await api("GET", `/api/lorebooks/${id}/export`); downloadJSON(d, (d.name || "lorebook").replace(/[^a-z0-9_-]/gi, "_") + ".json"); toast("Lorebook exported.", "ok"); }
  catch (e) { toast(`Export failed: ${e.message}`, "err") }
}
