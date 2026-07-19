function defaultCharacterSheet() {
  return {
    identity: { name: "New Character", aliases: [], pronouns: { subject: "they", object: "them", possessive: "their" } },
    simulation: { tier: "mid", temperature: 0.8, sampler: {} },
    embodiment: { senses: [{ channel: "general", acuity: "ordinary", range: "ordinary", notes: "ordinary human senses" }], visible: { summary: "A person of unremarkable appearance.", build: "", face: "", hair: "", eyes: "", distinctive_features: [] }, latent: [] },
    psychology: { traits: [], values: [], self_model: { summary: "", protected_beliefs: [], pride_triggers: [], shame_triggers: [] }, coping: { under_stress: [], default_conflict_style: "" } },
    social: { voice: { register: "", cadence: "", verbosity: "natural", markers: [], notes: "" }, baseline_stances: { unknown_person: { trust: 0, warmth: 0, threat_sensitivity: 0 } } },
    competence: { abilities: [] },
    knowledge: { access_tags: ["common"], excluded_titles: [], public_history: "", private_history: [] },
    initial_state: { mood: { label: "neutral", valence: 0, arousal: 0 }, goals: [], active_concerns: [] },
    opening: { first_message: "" }
  };
}

function charEditor(c) {
  const sheet = c ? JSON.parse(c.sheet) : defaultCharacterSheet();
  const f = {};

  f.name = fText("Name", sheet.identity?.name);
  f.aliases = fStrList("Aliases", sheet.identity?.aliases);
  f.pronouns = fPronouns("Pronouns", sheet.identity?.pronouns);
  f.tier = fSelect("Tier", [["bg", "background"], ["mid", "recurring"], ["major", "major/antagonist"]], sheet.simulation?.tier);
  f.temperature = fNum("Temperature (0.5–1.1)", sheet.simulation?.temperature, "0.05");

  f.summary = fArea("Visible summary — what a stranger sees at a glance", sheet.embodiment?.visible?.summary, 3);
  f.senses = fSenses("Senses", sheet.embodiment?.senses);
  f.build = fText("Build", sheet.embodiment?.visible?.build);
  f.face = fText("Face", sheet.embodiment?.visible?.face);
  f.hair = fText("Hair", sheet.embodiment?.visible?.hair);
  f.eyes = fText("Eyes", sheet.embodiment?.visible?.eyes);
  f.distinctive = fStrList("Distinctive features", sheet.embodiment?.visible?.distinctive_features);
  f.latent = fLatent("Latent/hidden capabilities (powers, secret identities, equipment functions)", sheet.embodiment?.latent);

  f.traits = fTraits("Core traits", sheet.psychology?.traits);
  f.values = fValues("Core values", sheet.psychology?.values);
  f.self_summary = fArea("Self-model summary", sheet.psychology?.self_model?.summary, 3);
  f.protected = fStrList("Protected beliefs", sheet.psychology?.self_model?.protected_beliefs);
  f.pride = fStrList("Pride triggers", sheet.psychology?.self_model?.pride_triggers);
  f.shame = fStrList("Shame triggers", sheet.psychology?.self_model?.shame_triggers);
  f.coping = fArea("Coping under stress", sheet.psychology?.coping?.under_stress?.join(", "), 2);
  f.conflict = fText("Default conflict style", sheet.psychology?.coping?.default_conflict_style);

  f.voice_register = fText("Voice register", sheet.social?.voice?.register);
  f.voice_cadence = fText("Voice cadence", sheet.social?.voice?.cadence);
  f.voice_verbosity = fSelect("Voice verbosity", [["terse", "terse"], ["natural", "natural"], ["chatty", "chatty"]], sheet.social?.voice?.verbosity);
  f.voice_markers = fStrList("Voice markers", sheet.social?.voice?.markers);
  f.voice_notes = fArea("Voice notes", sheet.social?.voice?.notes, 2);

  f.trust = fNum("Baseline trust (unknown person)", sheet.social?.baseline_stances?.unknown_person?.trust, "0.1");
  f.warmth = fNum("Baseline warmth", sheet.social?.baseline_stances?.unknown_person?.warmth, "0.1");
  f.threat = fNum("Baseline threat sensitivity", sheet.social?.baseline_stances?.unknown_person?.threat_sensitivity, "0.1");

  f.abilities = fAbilities("Abilities", sheet.competence?.abilities);

  f.knowledge_common = el("input", { type: "checkbox", ...(sheet.knowledge?.access_tags?.includes("common") ? { checked: "" } : {}) });
  f.knowledge_scholarly = el("input", { type: "checkbox", ...(sheet.knowledge?.access_tags?.includes("scholarly") ? { checked: "" } : {}) });
  f.knowledge_esoteric = el("input", { type: "checkbox", ...(sheet.knowledge?.access_tags?.includes("esoteric") ? { checked: "" } : {}) });
  f.excluded_titles = fStrList("Excluded knowledge titles", sheet.knowledge?.excluded_titles);
  f.public_history = fArea("Public history (world could know)", sheet.knowledge?.public_history, 3);

  f.mood = fText("Current mood label", sheet.initial_state?.mood?.label);
  f.valence = fNum("Mood valence (-1..1)", sheet.initial_state?.mood?.valence, "0.1");
  f.arousal = fNum("Mood arousal (0..1)", sheet.initial_state?.mood?.arousal, "0.1");
  f.goals = fGoals("Current goals", sheet.initial_state?.goals);
  f.active_concerns = fStrList("Active concerns", sheet.initial_state?.active_concerns);

  f.first_message = fArea("First message (optional, for scene open)", sheet.opening?.first_message, 3);
  const ph = phEditor(sheet.knowledge?.private_history, true);

  modal(c ? "Edit character — " + sheet.identity?.name : "New character", b => {
    b.append(
      el("details", { open: "" }, el("summary", {}, "Identity & Simulation"),
        f.name.node, f.aliases.node, f.pronouns.node, f.tier.node, f.temperature.node),
      el("details", { open: "" }, el("summary", {}, "Embodiment (Visible & Senses)"),
        f.summary.node, f.senses.node, f.build.node, f.face.node, f.hair.node, f.eyes.node, f.distinctive.node, f.latent.node),
      el("details", { open: "" }, el("summary", {}, "Psychology & Coping"),
        f.traits.node, f.values.node, f.self_summary.node, f.protected.node, f.pride.node, f.shame.node, f.coping.node, f.conflict.node),
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
        f.mood.node, f.valence.node, f.arousal.node, f.goals.node, f.active_concerns.node, f.first_message.node),
      el("details", { open: "" }, el("summary", {}, "Private history"),
        el("div", { class: "small dim" }, "Secrets only this character (and anyone tagged in known_by) knows."), ph.node),
      el("div", { class: "row", style: "margin-top:10px" },
        el("button", { class: "primary", onclick: async () => {
          const access_tags = [];
          if (f.knowledge_common.checked) access_tags.push("common");
          if (f.knowledge_scholarly.checked) access_tags.push("scholarly");
          if (f.knowledge_esoteric.checked) access_tags.push("esoteric");

          const s = {
            identity: { name: f.name.read(), aliases: f.aliases.read(), pronouns: f.pronouns.read() },
            simulation: { tier: f.tier.read(), temperature: f.temperature.read(), sampler: {} },
            embodiment: {
              senses: f.senses.read(),
              visible: { summary: f.summary.read(), build: f.build.read(), face: f.face.read(), hair: f.hair.read(), eyes: f.eyes.read(), distinctive_features: f.distinctive.read() },
              latent: f.latent.read()
            },
            psychology: {
              traits: f.traits.read(),
              values: f.values.read(),
              self_model: { summary: f.self_summary.read(), protected_beliefs: f.protected.read(), pride_triggers: f.pride.read(), shame_triggers: f.shame.read() },
              coping: { under_stress: splitCL(f.coping.read()), default_conflict_style: f.conflict.read() }
            },
            social: {
              voice: { register: f.voice_register.read(), cadence: f.voice_cadence.read(), verbosity: f.voice_verbosity.read(), markers: f.voice_markers.read(), notes: f.voice_notes.read() },
              baseline_stances: { unknown_person: { trust: f.trust.read() || 0, warmth: f.warmth.read() || 0, threat_sensitivity: f.threat.read() || 0 } }
            },
            competence: { abilities: f.abilities.read() },
            knowledge: { access_tags, excluded_titles: f.excluded_titles.read(), public_history: f.public_history.read(), private_history: ph.read() },
            initial_state: { mood: { label: f.mood.read(), valence: f.valence.read() || 0, arousal: f.arousal.read() || 0 }, goals: f.goals.read(), active_concerns: f.active_concerns.read() },
            opening: { first_message: f.first_message.read() }
          };
          try {
            if (c) await api("PUT", "/api/characters/" + c.id, { sheet: s });
            else await api("POST", "/api/characters", { sheet: s });
            closeModal(); await boot(); toast(c ? "Character saved." : "Character created.", "ok");
          } catch (e) { toast("Could not save: " + e.message, "err") }
        } }, "Save")));
  });
}

function personaEditor(p) {
  const sheet = p ? JSON.parse(p.sheet) : {
    identity: { name: "New Persona", aliases: [], pronouns: { subject: "they", object: "them", possessive: "their" } },
    embodiment: {
      senses: [{ channel: "general", acuity: "ordinary", range: "ordinary", notes: "ordinary human senses" }],
      visible: { summary: "A person of unremarkable appearance.", build: "", face: "", hair: "", eyes: "", distinctive_features: [] },
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
  f.senses = fSenses("Senses", sheet.embodiment?.senses);
  f.appearance = fArea("Appearance — what strangers see", sheet.embodiment?.visible?.summary, 3);
  f.build = fText("Build", sheet.embodiment?.visible?.build);
  f.face = fText("Face", sheet.embodiment?.visible?.face);
  f.hair = fText("Hair", sheet.embodiment?.visible?.hair);
  f.eyes = fText("Eyes", sheet.embodiment?.visible?.eyes);
  f.distinctive = fStrList("Distinctive features", sheet.embodiment?.visible?.distinctive_features);
  f.latent = fLatent("Latent/hidden capabilities", sheet.embodiment?.latent);
  f.public_history = fArea("Public history (world could know)", sheet.knowledge?.public_history, 3);
  f.voice_setting = fArea("Voice setting (PRIVATE — narrator only)", sheet.narration?.voice_setting, 3);
  f.abilities = fAbilities("Abilities", sheet.competence?.abilities);
  const ph = phEditor(sheet.knowledge?.private_history, false);

  modal(p ? "Edit persona — " + sheet.identity?.name : "New persona", b => {
    b.append(
      el("details", { open: "" }, el("summary", {}, "Basic"),
        f.name.node, f.aliases.node, f.pronouns.node),
      el("details", { open: "" }, el("summary", {}, "Embodiment (Visible & Senses)"),
        f.appearance.node, f.senses.node, f.build.node, f.face.node, f.hair.node, f.eyes.node, f.distinctive.node, f.latent.node),
      el("details", { open: "" }, el("summary", {}, "History & Voice"), f.public_history.node, f.voice_setting.node),
      el("details", { open: "" }, el("summary", {}, "Abilities"), f.abilities.node),
      el("details", { open: "" }, el("summary", {}, "Private history"), ph.node),
      el("div", { class: "row", style: "margin-top:10px" },
        el("button", { class: "primary", onclick: async () => {
          const s = {
            identity: { name: f.name.read(), aliases: f.aliases.read(), pronouns: f.pronouns.read() },
            embodiment: {
              senses: f.senses.read(),
              visible: { summary: f.appearance.read(), build: f.build.read(), face: f.face.read(), hair: f.hair.read(), eyes: f.eyes.read(), distinctive_features: f.distinctive.read() },
              latent: f.latent.read()
            },
            competence: { abilities: f.abilities.read() },
            knowledge: { public_history: f.public_history.read(), private_history: ph.read() },
            narration: { voice_setting: f.voice_setting.read() }
          };
          try {
            if (p) await api("PUT", "/api/personas/" + p.id, { sheet: s });
            else await api("POST", "/api/personas", { sheet: s });
            closeModal(); await boot(); toast(p ? "Persona saved." : "Persona created.", "ok");
          } catch (e) { toast("Could not save: " + e.message, "err") }
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

  modal("Promote " + name, b => b.append(
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
        catch (e) { toast("Invalid JSON: " + e.message, "err"); return }
        const memory_seeds = seedsTa.value.split("\n").map(s => s.trim()).filter(Boolean);
        try {
          await api("POST", `/api/chats/${cid}/promotions/confirm`,
            { name, sheet, memory_seeds });
          closeModal();
          await boot();
          toast(name + " is now a full character.", "ok");
        } catch (e) { toast("Could not promote: " + e.message, "err") }
      } }, "✨ Confirm & attach"))));
}

async function promoteBackgroundPresence(cid, name) {
  let draft;
  try {
    draft = await api("POST", `/api/chats/${cid}/promotions/draft`, { name });
  } catch (e) {
    toast("Could not draft promotion: " + e.message, "err");
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

  modal("Import " + kind, b => {
    b.append(drop, fileIn, status,
      kind === "lorebook" ? el("div", { class: "card" },
        el("div", { class: "ff" }, el("label", {}, "Book type"), typeSel),
        el("div", { class: "ff" }, el("label", {}, "Summary"), sumIn)) : null,
      el("label", { class: "tgl", style: "margin:11px 0" }, re, " AI reinterpretation"),
      el("div", { class: "small dim", style: "margin:-6px 0 11px 0" },
        "Recommended for anything that isn't already a native sheet or a plain SillyTavern V2/V3 card — the ecosystem has too many export shapes to hand-parse them all."),
      el("div", { class: "row", style: "margin-top:12px" },
        el("button", { class: "primary", onclick: () => {
          if (!fileContent) { toast("Choose a valid JSON file first.", "warn"); return }
          const endpoint = { character: "/api/characters/import", persona: "/api/personas/import", lorebook: "/api/lorebooks/import" }[kind];
          const payload = kind === "character" ? { card: fileContent, reinterpret: re.checked }
            : kind === "persona" ? { card: fileContent, reinterpret: re.checked }
              : { book: fileContent, reinterpret: re.checked, book_type: typeSel.value, summary: sumIn.value };
          backgroundTask("Importing " + kind, () => api("POST", endpoint, payload),
            { onSuccess: async r => { await boot(); if (kind === "lorebook" && r?.id) await loreModal(r.id) },
             successMessage: kind.charAt(0).toUpperCase() + kind.slice(1) + " imported.",
             errorPrefix: kind.charAt(0).toUpperCase() + kind.slice(1) + " import failed" });
        } }, "Import")));
  });
}

// ---- Generate ----
function generateModal(kind) {
  const ta = el("textarea", { style: "width:100%;height:170px", placeholder: "Describe the " + kind + " you want…" });
  modal("Generate " + kind, b => {
    b.append(ta,
      el("div", { class: "small dim", style: "margin-top:8px" }, "The dialog will close when generation starts. Progress is visible in the activity panel."),
      el("div", { class: "row", style: "margin-top:11px" },
        el("button", { class: "primary", onclick: () => {
          const prompt = ta.value.trim();
          backgroundTask("Generating " + kind,
            () => api("POST", `/api/${kind === "character" ? "characters" : "personas"}/generate`, { prompt }),
            { onSuccess: async () => { await boot() },
             successMessage: kind.charAt(0).toUpperCase() + kind.slice(1) + " generated.",
             errorPrefix: kind.charAt(0).toUpperCase() + kind.slice(1) + " generation failed" });
        } }, "Generate")));
  });
}

// ---- Lorebook generate ----
function generateLoreModal(lid, isChat) {
  const ta = el("textarea", { style: "width:100%;height:170px", placeholder: "Describe the entries to create…" });
  modal("Generate lorebook entries", b => {
    b.append(ta,
      el("div", { class: "small dim", style: "margin-top:8px" }, "Generation continues after this dialog closes."),
      el("div", { class: "row", style: "margin-top:11px" },
        el("button", { class: "primary", onclick: () => {
          backgroundTask("Generating lorebook entries",
            () => api("POST", `/api/lorebooks/${lid}/generate`, { prompt: ta.value.trim() }),
            { onSuccess: async r => { await boot(); if (r?.added) await loreModal(lid) },
             successMessage: r => `Generated ${r?.added || 0} entries.`,
             errorPrefix: "Lore generation failed" });
        } }, "Generate entries")));
  });
}

// ---- Lorebooks ----
async function loreModal(lid) {
  modal("Lorebook", b => { b.append(loadingBlock("Loading lorebook…")) }, { wide: true });
  let d;
  try { d = await api("GET", "/api/lorebooks/" + lid) }
  catch (e) { $("#modalbody").innerHTML = ""; $("#modalbody").append(emptyState("Could not load lorebook: " + e.message)); return }
  const cats = S.boot.lore_categories, types = S.boot.lorebook_types;
  modal("Lorebook — " + d.book.name, b => {
    const typeSel = fSelect("Type", types, d.book.book_type || "general");
    const sumIn = fArea("Summary for the mapping agent", d.book.summary || "", 2);
    b.append(el("div", { class: "row" },
      el("button", { onclick: async () => {
        const n = await promptModal("Rename:", d.book.name); if (n == null) return;
        await api("PUT", "/api/lorebooks/" + lid, { name: n });
        closeModal(); boot();
      } }, "Rename"),
      el("button", { onclick: async () => { await exportLorebook(lid) } }, "⤓ Export"),
      el("button", { onclick: () => {
        backgroundTask("Reinterpreting " + d.book.name,
          () => api("POST", `/api/lorebooks/${lid}/reinterpret`),
          { onSuccess: async () => { await boot(); await loreModal(lid) },
           successMessage: r => `Reinterpreted ${r?.reinterpreted || 0} entries.`,
           errorPrefix: "Reinterpretation failed" });
      } }, "✨ Reinterpret / categorize"),
      el("button", { onclick: () => generateLoreModal(lid, false) }, "✨ Generate entries"),
      el("button", { onclick: async () => {
        await api("POST", `/api/lorebooks/${lid}/entries`, { keys: "", content: "New entry", category: "other" });
        closeModal(); loreModal(lid);
      } }, "+ Entry")));
    b.append(typeSel.node, sumIn.node,
      el("div", { class: "row", style: "margin:6px 0" },
        el("button", { onclick: async () => {
          await api("PUT", "/api/lorebooks/" + lid, { book_type: typeSel.read(), summary: sumIn.read() });
          closeModal(); boot();
        } }, "Save book meta")));
    let lastCat = "";
    for (const e of d.entries) {
      const cat = e.category || "other";
      if (cat !== lastCat) { b.append(el("div", { style: "margin:10px 0 2px;font-weight:600;color:var(--dim);text-transform:uppercase;font-size:11px" }, cat)); lastCat = cat }
      const k = el("input", { style: "flex:1", value: e.keys || "", placeholder: "keys (comma-separated)" });
      const titleIn = el("input", { style: "flex:1", value: e.title || "", placeholder: "title" });
      const catSel = el("select", {}, cats.map(c => el("option", { value: c, ...(c === cat ? { selected: "" } : {}) }, c)));
      const c = el("textarea", { style: "width:100%", rows: "3" }, e.content || "");
      const tagSel = el("select", {}, ["common", "scholarly", "esoteric"].map(t => el("option", { value: t, ...(t === (e.knowledge_tag || "common") ? { selected: "" } : {}) }, t)));
      const rangeSel = el("select", {}, ["global", "local"].map(r => el("option", { value: r, ...(r === (e.knowledge_range || "global") ? { selected: "" } : {}) }, r)));
      let locsVal = ""; try { locsVal = (JSON.parse(e.knowledge_locations || "[]") || []).join(", ") } catch (err) { }
      const locsIn = el("input", { style: "flex:1", value: locsVal, placeholder: "room IDs (comma-separated)" });
      const knowledgeFields = el("div", { class: "row small", style: catSel.value === "knowledge" ? "" : "display:none" }, titleIn, tagSel, rangeSel, locsIn);
      catSel.onchange = () => { knowledgeFields.style.display = catSel.value === "knowledge" ? "" : "none" };
      b.append(el("div", { class: "card" },
        el("div", { class: "row" }, k, catSel,
          e.canon_locked ? el("span", { class: "badge" }, "🔒 locked") : null,
          el("button", { onclick: async () => {
            let kloc = null;
            if (catSel.value === "knowledge" && rangeSel.value === "local")
              kloc = JSON.stringify(locsIn.value.split(",").map(s => s.trim()).filter(Boolean));
            await api("PUT", "/api/lore_entries/" + e.id,
              { keys: k.value, content: c.value, category: catSel.value, title: titleIn.value,
               knowledge_tag: catSel.value === "knowledge" ? tagSel.value : null,
               knowledge_range: catSel.value === "knowledge" ? rangeSel.value : null,
               knowledge_locations: kloc });
            closeModal(); loreModal(lid);
          } }, "Save"),
          el("button", { onclick: async () => {
            if (!await confirmModal("Delete this entry?", { danger: true, confirmLabel: "Delete" })) return;
            await api("DELETE", "/api/lore_entries/" + e.id);
            closeModal(); loreModal(lid);
          } }, "✕")),
        knowledgeFields, c));
    }
    if (!d.entries.length) b.append(el("div", { class: "dim" }, "No entries yet. Click + Entry to add one."));
  }, { wide: true });
}

// ---- Export ----
async function exportCharacter(id) {
  try { const d = await api("GET", `/api/characters/${id}/export`); downloadJSON(d, (d.data?.identity?.name || d.name || "character").replace(/[^a-z0-9_-]/gi, "_") + ".json"); toast("Character exported.", "ok"); }
  catch (e) { toast("Export failed: " + e.message, "err") }
}
async function exportPersona(id) {
  try { const d = await api("GET", `/api/personas/${id}/export`); downloadJSON(d, (d.data?.identity?.name || d.name || "persona").replace(/[^a-z0-9_-]/gi, "_") + ".json"); toast("Persona exported.", "ok"); }
  catch (e) { toast("Export failed: " + e.message, "err") }
}
async function exportLorebook(id) {
  try { const d = await api("GET", `/api/lorebooks/${id}/export`); downloadJSON(d, (d.name || "lorebook").replace(/[^a-z0-9_-]/gi, "_") + ".json"); toast("Lorebook exported.", "ok"); }
  catch (e) { toast("Export failed: " + e.message, "err") }
}