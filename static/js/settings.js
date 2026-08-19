// ---- Chat tool modals ----

// The era the reader is currently viewing (chat.js's frame pills), as a
// query string for the scene-authoring routes -- positions, attire, vitals,
// survival seeding. Empty for the present, which is also the frameless-chat
// case. The raw world editor deliberately takes no frame: it shows every
// era's rows verbatim (web/app.py world_get).
function frameQuery() {
  return S.currentFrameId != null ? `?frame_id=${S.currentFrameId}` : "";
}

$("#b-world").onclick = async () => {
  if (!S.chatId) return;
  const chatId = S.chatId;
  const w = await api("GET", `/api/chats/${chatId}/world`);
  if (S.chatId !== chatId) return;
  const ta = el("textarea", { style: "width:100%;height:420px" }, JSON.stringify(w, null, 2));
  modal("World state", b => b.append(
    el("div", { class: "small dim", style: "margin-bottom:8px" },
      "The raw internal record of the scene — rooms, positions, objects, standing facts — that every stage of "
      + "a turn reads from and writes to. The story keeps this updated on its own; you don't need to touch it "
      + "to play. Edit it only to hand-correct something that's drifted wrong (a character in the wrong room, "
      + "a fact that should no longer be true)."),
    ta,
    el("div", { class: "row", style: "margin-top:8px" },
      el("button", { class: "primary", onclick: async () => { let j; try { j = JSON.parse(ta.value) } catch (e) { return toast("Invalid JSON", "err") } await api("PUT", `/api/chats/${chatId}/world`, j); closeModal(); toast("World state saved.", "ok"); } }, "Save"))));
};

$("#b-attire").onclick = async () => {
  if (!S.chatId) return;
  const chatId = S.chatId;
  const a = await api("GET", `/api/chats/${chatId}/attire${frameQuery()}`);
  if (S.chatId !== chatId) return;
  const ta = el("textarea", { style: "width:100%;height:340px" }, JSON.stringify(a, null, 2));
  modal("Attire — {name:{wearing:[],state:[]}}", b => b.append(
    el("div", { class: "small dim", style: "margin-bottom:8px" },
      "What each character is currently wearing and any visible physical state (injuries, disguises, damage) "
      + "the story should keep consistent going forward. Updates automatically as the story progresses; edit "
      + "directly only to correct something or set up a scene's starting appearance by hand."),
    ta,
    el("div", { class: "row", style: "margin-top:8px" },
      el("button", { class: "primary", onclick: async () => { let j; try { j = JSON.parse(ta.value) } catch (e) { return toast("Invalid JSON", "err") } await api("PUT", `/api/chats/${chatId}/attire${frameQuery()}`, j); closeModal(); toast("Attire saved.", "ok"); } }, "Save"))));
};

// Genre & style: the author's standing instruction for anything the engine
// INVENTS. Self-determination is the default and stays first-class -- a blank
// genre means "you work it out", which is what the engine did before this
// existed, not "this world has no style".
$("#b-style").onclick = async () => {
  if (!S.chatId) return;
  const chatId = S.chatId;
  const r = await api("GET", `/api/chats/${chatId}/style_guide`);
  if (S.chatId !== chatId) return;
  const g = r.style_guide || {};
  // Non-fatal: api() throws on any non-ok response, so a language failure
  // used to mean the whole style-guide modal never opened.
  let languageState = { language: "en", stored: "en", installed: true };
  try { languageState = await api("GET", `/api/chats/${chatId}/language`); }
  catch (e) { toast(e.message, "warn"); }
  if (S.chatId !== chatId) return;
  // When the stored pack is not installed on this machine (a chat carried
  // over from another install), the value on disk is still correct and comes
  // back when the pack returns. Offer it as the selected option rather than
  // silently showing English -- pressing Save then wrote English over it, and
  // that is not recoverable.
  const storedMissing = languageState.installed === false;
  const language = el("select", { style: "flex:1" }, [
    ...(storedMissing ? [el("option", { value: languageState.stored, selected: "" },
      `${languageState.stored} (pack not installed)`)] : []),
    ...((S.boot && S.boot.language_packs) || []).filter(pack => pack.story)
      .map(pack => el("option", {
        value: pack.id,
        ...(!storedMissing && pack.id === languageState.language ? { selected: "" } : {})
      }, pack.native_name || pack.name || pack.id))]);
  const uiLanguage = el("select", { style: "flex:1" },
    ((S.boot && S.boot.language_packs) || []).filter(pack => pack.ui)
      .map(pack => el("option", {
        value: pack.id,
        ...(pack.id === S.uiLanguage ? { selected: "" } : {})
      }, pack.native_name || pack.name || pack.id)));

  const SELF = "(self-determine — infer from scenario & lore)";
  const PRESETS = ["cosmic horror", "noir", "cyberpunk", "high fantasy",
    "grimdark", "space opera", "weird western", "gothic romance",
    "hardboiled mystery", "post-apocalyptic", "slice of life"];

  // A datalist rather than a fixed dropdown: the presets are a starting point,
  // not a closed set -- any genre can be typed.
  const listId = "style-genre-presets";
  const genre = el("input", {
    style: "flex:1", list: listId, placeholder: SELF, value: g.genre || "",
  });
  const datalist = el("datalist", { id: listId },
    PRESETS.map(x => el("option", { value: x })));

  // How far the sky may go, and how much of the world it may touch. A closed
  // set, unlike everything else here, because it GATES engine behaviour rather
  // than describing it: the ground state machine, the drift cap and what the
  // Director is permitted to do with weather all read it.
  const severity = el("select", { style: "flex:1" }, [
    ["calm", "Calm — weather is scenery, and leaves no mark"],
    ["seasonal", "Seasonal — real weather, and ground that answers to it"],
    ["harsh", "Harsh — weather you would not want to be caught out in"],
    ["catastrophic", "Catastrophic — weather may become the event"],
  ].map(([v, label]) => el("option",
    { value: v, ...(v === (g.weather_severity || "seasonal") ? { selected: "" } : {}) },
    label)));
  const selfBtn = el("button", {
    onclick: () => { genre.value = ""; toast("Genre left to the engine.", "ok"); },
  }, "Self-determine");

  const tone = el("input", { style: "flex:1", value: g.tone || "",
    placeholder: "e.g. cold, clinical, understated" });
  const dirNotes = el("textarea", { rows: "3", style: "width:100%",
    placeholder: "Standing instruction for the Director — how events should resolve and read." },
    g.director_notes || "");
  const mapNotes = el("textarea", { rows: "3", style: "width:100%",
    placeholder: "Standing instruction for mapping — how NEW rooms, objects and lore should feel." },
    g.mapping_notes || "");
  const avoid = el("textarea", { rows: "2", style: "width:100%",
    placeholder: "Never generate — e.g. modern tech, gore, named real people." },
    g.avoid || "");

  const survivalState = await api("GET", `/api/chats/${chatId}/survival`);
  if (S.chatId !== chatId) return;
  // Player authority belongs here rather than beside the simulation dials:
  // it decides what a DECLARATION MEANS in this story, which is a question
  // about the fiction, not about how much happens off screen.
  let authorityState = { mode: "world_author" };
  try { authorityState = await api("GET", `/api/chats/${chatId}/player_authority`); }
  catch (e) { toast(e.message, "warn"); }
  if (S.chatId !== chatId) return;
  // A closed set, like Weather above and for the same reason: it gates engine
  // behaviour rather than describing it. The engine owns the ladder
  // (scene.PLAYER_AUTHORITY_MODES) and the route serves it, so a rung added
  // later cannot go missing from this menu.
  const AUTHORITY_LABELS = {
    world_author:
      "Full authorship — what you write is true, including events and people",
    explicit_outcomes:
      "Your outcomes — your acts land as you declare them; the world is the Director's",
    actor_only:
      "Hard mode — you declare what you attempt, the Director decides what it did",
  };
  const authority = el("select", { style: "flex:1" },
    (authorityState.modes || Object.keys(AUTHORITY_LABELS).map(m => ({ value: m })))
      .map(entry => el("option", {
        value: entry.value,
        ...(entry.value === authorityState.mode ? { selected: "" } : {}),
      }, AUTHORITY_LABELS[entry.value] || entry.value)));
  const survivalBox = el("input", {
    type: "checkbox", ...(survivalState.enabled ? { checked: "" } : {})
  });
  const npcBox = el("input", {
    type: "checkbox", ...(survivalState.show_npcs ? { checked: "" } : {})
  });

  modal("Genre & style", b => b.append(
    el("div", { class: "small dim" },
      "Applies to what the engine ", el("b", {}, "invents"),
      " — new rooms, objects, lore, and the register of resolved events. It never overrides canon, an established room, or something you declared yourself, and it is never quoted back into the prose."),
    el("div", { class: "row", style: "margin-top:10px" },
      el("span", { class: "small", style: "width:100px" }, "Story language"), language),
    el("div", { class: "small dim", style: "margin-top:4px" },
      "Controls future Director interpretation, deterministic compositor output, and generated memories. Existing prose and memories are not translated."),
    el("div", { class: "row", style: "margin-top:8px" },
      el("span", { class: "small", style: "width:100px" }, "Interface"), uiLanguage),
    el("div", { class: "small dim", style: "margin-top:4px" },
      "Controls menus, dialogs, labels, and error messages for this installation."),
    el("div", { class: "row", style: "margin-top:10px" },
      el("span", { class: "small", style: "width:70px" }, "Genre"), genre, datalist, selfBtn),
    el("div", { class: "row", style: "margin-top:6px" },
      el("span", { class: "small", style: "width:70px" }, "Tone"), tone),
    el("div", { class: "row", style: "margin-top:6px" },
      el("span", { class: "small", style: "width:70px" }, "Weather"), severity),
    el("div", { class: "small dim", style: "margin-top:4px" },
      "How far the sky may go, and how much of the world it may touch. Beyond "
      + "Calm, weather leaves a mark that stays: an hour of heavy rain turns an "
      + "open yard to mud, a night of snow leaves drifts, and both are still "
      + "there when the sky clears — the room sounds and looks like it. "
      + "Catastrophic is the only setting that lets weather hurt anyone or "
      + "break anything, and nothing reaches for it unless you do."),
    el("div", { class: "row", style: "margin-top:10px" },
      el("span", { class: "small", style: "width:70px" }, "Authority"), authority),
    el("div", { class: "small dim", style: "margin-top:4px" },
      "Who decides what your declaration achieved. Under full authorship — the "
      + "default — writing \u201cthe door gives way\u201d makes it so, and the "
      + "engine encodes it. Hard mode keeps your words exactly as you wrote "
      + "them and turns the OUTCOME back into a question: the Director may "
      + "grant it, roll for it, or refuse it, and the cast gets to push back "
      + "physically. What you say, attempt and do with your own body is yours "
      + "in every setting and is never rewritten. Changing this mid-story is "
      + "allowed and is recorded, because it changes what the earlier turns "
      + "meant."),
    el("div", { style: "margin-top:10px" },
      el("div", { class: "small" }, "Director notes"), dirNotes),
    el("div", { style: "margin-top:8px" },
      el("div", { class: "small" }, "Mapping notes ", el("span", { class: "dim" }, "— shapes newly generated rooms")), mapNotes),
    el("div", { style: "margin-top:8px" },
      el("div", { class: "small" }, "Avoid"), avoid),
    el("div", { style: "margin-top:12px;border-top:1px solid var(--bd);padding-top:10px" },
      el("label", { class: "tgl" }, survivalBox, " track bodily condition"),
      el("div", { class: "small dim", style: "margin-top:4px" },
        "Breath, stamina, nourishment and injury for every body, moved by how much time a beat takes rather than by turns. Off means absent: nothing is tracked and nothing reaches the Director, so a story that did not ask for a hunger clock never pays for one. Air is the sharp one, since a body sealed in a closed container runs out."),
      el("label", { class: "tgl", style: "margin-top:8px" },
        npcBox, " also show other characters beside the story"),
      el("div", { class: "small dim", style: "margin-top:4px" },
        "Your own condition sits in the margin beside the prose. Everyone else's is tracked either way and read in the Cast panel — turn this on to have theirs surface alongside yours as well.")),
    el("div", { class: "row", style: "margin-top:10px" },
      el("button", { class: "primary", onclick: async () => {
        const uiChanged = uiLanguage.value !== S.uiLanguage;
        const languageChanged = language.value !== languageState.stored;
        await api("PUT", `/api/chats/${chatId}/survival${frameQuery()}`,
                  { enabled: survivalBox.checked,
                    show_npcs: npcBox.checked });
        const out = await api("PUT", `/api/chats/${chatId}/style_guide`, {
          style_guide: {
            genre: genre.value, tone: tone.value,
            director_notes: dirNotes.value, mapping_notes: mapNotes.value,
            avoid: avoid.value, weather_severity: severity.value,
          },
        });
        if (authority.value !== authorityState.mode) {
          await api("PUT", `/api/chats/${chatId}/player_authority`, {
            mode: authority.value,
            turn_idx: (S.chat && S.chat.turns && S.chat.turns.length)
              ? S.chat.turns[S.chat.turns.length - 1].idx : null,
          });
        }
        // Last, and only on a real change: this is the one field here whose
        // route refuses to run mid-turn, and the only one whose loss is
        // permanent.
        if (languageChanged) {
          const languageOut = await api(
            "PUT", `/api/chats/${chatId}/language`, { language: language.value });
          if (S.chat && S.chatId === chatId) {
            S.chat.chat.story_language = languageOut.language;
          }
        }
        if (uiChanged) {
          await api("PUT", "/api/ui-language", { language: uiLanguage.value });
        }
        if (S.chatId === chatId) await refreshVitalsHud();
        closeModal();
        toast(Object.keys(out.style_guide).length
          ? "Style guide saved." : "Style guide cleared — the engine self-determines.", "ok");
        if (uiChanged) window.location.reload();
      } }, "Save"),
      el("button", { onclick: async () => {
        await api("PUT", `/api/chats/${chatId}/style_guide`, { style_guide: {} });
        closeModal(); toast("Style guide cleared — the engine self-determines.", "ok");
      } }, "Clear all"))));
};

$("#b-dlg").onclick = async () => {
  if (!S.chatId) return;
  const chatId = S.chatId;
  const c = await api("GET", `/api/chats/${chatId}/dialogue_config`);
  if (S.chatId !== chatId) return;
  const bg = await api("GET", `/api/chats/${chatId}/background_config`);
  if (S.chatId !== chatId) return;
  const lw = await api("GET", `/api/chats/${chatId}/living_world`);
  if (S.chatId !== chatId) return;
  const st = el("select", {}, ["terse", "natural", "chatty"].map(s => el("option", { value: s, ...(s === c.style ? { selected: "" } : {}) }, s)));
  const mn = el("input", { type: "number", value: c.min_lines, min: "0" });
  const mx = el("input", { type: "number", value: c.max_lines, min: "0" });
  const va = el("input", { type: "number", step: "0.1", value: c.variance, min: "0", max: "1" });
  const auto = el("input", { type: "range", min: "0", max: "100", value: c.autonomy ?? 50, style: "width:100%" });
  const autoVal = el("span", {}, auto.value);
  auto.oninput = () => autoVal.textContent = auto.value;

  const npcInit = el("input", { type: "checkbox", ...(c.allow_npc_initiative ? { checked: "" } : {}) });
  const npcNpc = el("input", { type: "checkbox", ...(c.allow_npc_to_npc_dialogue ? { checked: "" } : {}) });
  const stopAddr = el("input", { type: "checkbox", ...(c.stop_on_player_address ? { checked: "" } : {}) });
  const stopQ = el("input", { type: "checkbox", ...(c.stop_on_question_to_player ? { checked: "" } : {}) });
  const silence = el("input", { type: "checkbox", ...(c.silence_ends_exchange ? { checked: "" } : {}) });

  // Background life (docs/design/BACKGROUND_LIFE_DESIGN.md). Sits here rather than in
  // Genre & style because these are simulation dials -- who gets to speak --
  // the same family as NPC-to-NPC dialogue above. The style guide still owns
  // how invented extras SOUND.
  const sceneLife = el("select", {}, [
    ["off", "Off — extras react only when prompted"],
    ["ambient", "Ambient — the room talks among itself (safest)"],
    ["full", "Full — one manager runs the whole room"],
  ].map(([v, label]) => el("option",
    { value: v, ...(v === (bg.scene_life || "off") ? { selected: "" } : {}) }, label)));
  const maxManaged = el("input", { type: "number", min: "1", max: "8",
                                   value: bg.max_managed ?? 6 });
  const maxReactors = el("input", { type: "number", min: "1", max: "3",
                                    value: bg.max_reactors ?? 1 });
  // Promotion. Deliberately here, next to the controls that decide who gets to
  // speak, and deliberately visible: acquiring a permanent cast member is the
  // largest thing this menu can cause, and it used to happen with no dial at
  // all and nothing on screen to say it might.
  const promoteAfter = el("input", { type: "number", min: "0", max: "99",
                                     value: c.promote_after_addressed ?? 0 });
  // Off-screen life (docs/design/OFFSCREEN_LIFE_DESIGN.md). The rungs come from the
  // server rather than being listed here, so the menu cannot drift from the
  // ladder the engine actually implements.
  const offLife = el("select", {}, (c.offscreen_life_levels || []).map(
    lvl => el("option",
      { value: lvl.value, ...(lvl.value === c.offscreen_life ? { selected: "" } : {}) },
      `${lvl.value} — ${lvl.description}`)));
  // The rung names are the engine's own (schemas.BehaviorController), so the
  // menu spells out what each one means rather than relying on the word.
  const maxOffscreen = el("input", { type: "number", min: "0", max: "12",
                                     value: c.max_offscreen_actors ?? 3 });
  // Living world mechanisms (docs/design/DESIGN_LIVING_WORLD.md), same convention —
  // and the clamp shown is the engine's own: each depth's `requires` rung
  // arrives computed, and refreshLw mirrors living_world.effective_depth
  // (the highest depth at or below the request that is built AND within
  // the ceiling), so moving either dropdown updates what every mechanism
  // will actually run as. One ceiling, many mechanisms; a mechanism above
  // the ceiling is clamped visibly, never silently run or ignored.
  const ladder = (c.offscreen_life_levels || []).map(l => l.value);
  const permits = d => ladder.indexOf(offLife.value) >= ladder.indexOf(d.requires);
  const lwSelects = {}, lwStatus = {};
  const refreshLw = () => (lw.approaches || []).forEach(a => {
    const value = lwSelects[a.approach].value;
    let eff = "off", d = null;
    for (const x of a.depths || []) {
      if (x.built && permits(x)) eff = x.value;
      if (x.value === value) { d = x; break; }
    }
    lwStatus[a.approach].textContent = !d || eff === value ? "" :
      `runs as ${eff} — ` + [d.built ? "" : "that tier is unbuilt",
        permits(d) ? "" : `off-screen life at ${offLife.value} caps it (needs ${d.requires})`]
        .filter(Boolean).join("; ");
  });
  offLife.onchange = refreshLw;
  const lwRows = (lw.approaches || []).map(a => {
    const sel = el("select", { onchange: refreshLw },
      [el("option", { value: "off", ...(a.value === "off" ? { selected: "" } : {}) }, "off")]
        .concat((a.depths || []).map(d => el("option",
          { value: d.value, ...(d.value === a.value ? { selected: "" } : {}) },
          d.built ? d.value : `${d.value} — not built yet`))));
    const status = el("div", { class: "small dim" });
    lwSelects[a.approach] = sel;
    lwStatus[a.approach] = status;
    return el("tr", {}, el("td", {}, a.label), el("td", {}, sel, status));
  });
  refreshLw();

  modal("Dialogue config", b => b.append(
    el("div", { class: "small dim", style: "margin-bottom:10px" },
      "Controls how much NPCs act on their own each turn, versus waiting for you to prompt them. "
      + "Leave this alone unless a scene feels too passive (raise autonomy) or too chaotic (lower it)."),
    el("div", { class: "card" },
      el("div", { class: "section-title", style: "margin-top:0" }, "NPC Autonomy"),
      el("div", { class: "small dim" },
        "How many NPCs get to react and speak in a single turn without you addressing them directly. "
        + "Low = one reaction at most, keeps the scene tightly focused on your input. "
        + "High = NPCs can chain reactions to each other, letting a scene unfold on its own."),
      el("div", { class: "row", style: "margin-top:6px" }, el("span", {}, "Low (1 reaction)"), auto, el("span", {}, "High (autonomous scene)")),
      el("div", { class: "small dim", style: "margin-top:4px" }, "Current value: ", autoVal, " / 100"),
      el("div", { class: "row", style: "margin-top:10px" },
        el("label", { class: "tgl" }, npcInit, " NPC initiative"),
        el("label", { class: "tgl" }, npcNpc, " NPC-to-NPC dialogue"),
        el("label", { class: "tgl" }, stopAddr, " Stop on player address"),
        el("label", { class: "tgl" }, stopQ, " Stop on question to player"),
        el("label", { class: "tgl" }, silence, " Silence ends exchange")),
      el("div", { class: "small dim", style: "margin-top:6px" },
        el("div", {}, "NPC initiative — NPCs can start doing something without you prompting them first."),
        el("div", {}, "NPC-to-NPC dialogue — NPCs can talk to each other, not only to you."),
        el("div", {}, "Stop on player address — a scene running on its own pauses once an NPC speaks directly to you, so you don't miss your cue to respond."),
        el("div", {}, "Stop on question to player — same pause, triggered specifically by an NPC asking you something."),
        el("div", {}, "Silence ends exchange — if nobody has anything to say or do, the scene stops rather than manufacturing more dialogue to fill the turn."))),
    el("div", { class: "card", style: "margin-top:10px" },
      el("div", { class: "section-title", style: "margin-top:0" }, "World simulation"),
      el("div", { class: "small dim" },
        "What the world and cast may do while you are not watching. One "
        + "ceiling, many mechanisms: ", el("b", {}, "Off-screen life"),
        " says how much authority any off-screen work may have, and every "
        + "mechanism beneath runs only up to it. A ceiling, not an instruction: "
        + "nothing is obliged to act at any level, "
        + "and a quiet turn still costs nothing. Each level adds to the one above it."),
      el("table", { class: "grid", style: "margin-top:6px" },
        el("tr", {}, el("td", {}, "off-screen life"), el("td", {}, offLife)),
        el("tr", {}, el("td", {}, "max off-screen actors"), el("td", {}, maxOffscreen))),
      el("div", { class: "small dim", style: "margin-top:6px" },
        el("div", {}, el("b", {}, "inert"), " — nothing happens off screen. A dormant "
          + "character is exactly where you left them."),
        el("div", {}, el("b", {}, "deterministic"), " — only things already on a "
          + "clock: someone arriving when they said they would, food spoiling, news "
          + "taking days to travel. Costs nothing and is always running anyway; this "
          + "level just says that is all you want."),
        el("div", {}, el("b", {}, "reactive"), " — a character may carry out bounded "
          + "stages they explicitly declared while present. Time and event triggers "
          + "fire only the effect already adjudicated; there is no new model call or plan."),
        el("div", {}, el("b", {}, "stochastic"), " — at meaningful world changes, dormant "
          + "characters get a sentence of what they have been up to, kept in a log. "
          + "No plans, no decisions, nothing that moves anyone. This is what the "
          + "engine has always done, which is why it is the default."),
        el("div", {}, el("b", {}, "character_agent"), " — characters you have "
          + "explicitly opted in on their card actually advance their own plans "
          + "while you are away, acting only on what has genuinely reached them, "
          + "and the consequences are waiting when you arrive. A villain with a "
          + "clock can beat you to something. Also requires the antagonist "
          + "ladder's ceiling under Living world."),
        el("div", { style: "margin-top:4px" },
          el("b", {}, "Max off-screen actors"), " — how many characters may be ticked "
          + "in one beat. 0 means none, whatever the level says."),
        el("div", { style: "margin-top:4px" },
          "Whatever the level, an off-screen character acts on what ",
          el("i", {}, "they"),
          " know — never on where you are or what you just did. Someone who has "
          + "not been told cannot react to it.")),
      el("div", { class: "section-title" }, "World mechanisms"),
      el("div", { class: "small dim" },
        "How much the WORLD does on its own — rooms drifting while unwatched, "
        + "consequences landing on the clock, unvisited places accruing history. "
        + "Each runs only up to the ceiling above; one set past it says what it "
        + "actually runs as. Everything here is encountered, never reported: an "
        + "off-screen event reaches you as changed state when you arrive, or not "
        + "at all. All off by default; turning one on changes nothing already "
        + "written."),
      el("table", { class: "grid", style: "margin-top:6px" }, lwRows),
      el("div", { class: "small dim", style: "margin-top:6px" },
        (lw.approaches || []).map(a => el("div", { style: "margin-top:4px" },
          el("div", {}, el("b", {}, a.label), " — ",
            ((a.depths || [])[0] || {}).description || ""),
          el("div", {}, "Cost — ", a.cost))))),
    el("div", { class: "card", style: "margin-top:10px" },
      el("div", { class: "section-title", style: "margin-top:0" }, "Background life"),
      el("div", { class: "small dim" },
        "Extras with no character sheet — patrons, crew, bystanders. Normally they "
        + "speak only when the scene pokes them. Turn this on and one model is given "
        + "the room's whole populace each beat, so people talk to each other and act "
        + "on their own instead of only reacting to you."),
      el("table", { class: "grid", style: "margin-top:6px" },
        el("tr", {}, el("td", {}, "scene life"), el("td", {}, sceneLife)),
        el("tr", {}, el("td", {}, "max managed"), el("td", {}, maxManaged)),
        el("tr", {}, el("td", {}, "max reactors"), el("td", {}, maxReactors)),
        el("tr", {}, el("td", {}, "turns till auto-promotion"),
          el("td", {}, promoteAfter))),
      el("div", { class: "small dim", style: "margin-top:6px" },
        el("div", {}, el("b", {}, "Ambient"), " — the manager is only ever shown what "
          + "everyone present already heard, so it cannot leak one extra's knowledge "
          + "to another. Anything said directly to an extra is handled the old way."),
        el("div", {}, el("b", {}, "Full"), " — the manager also sees lines aimed at one "
          + "person, tagged with who heard them. Richer, because a reply and a muttered "
          + "aside can happen in one beat, but it relies on the model honouring those tags."),
        el("div", {}, el("b", {}, "Max managed"), " — how many extras one call may hold. "
          + "Past a handful a crowd reads as noise."),
        el("div", {}, el("b", {}, "Max reactors"), " — used only when scene life is off: "
          + "how many extras the old one-at-a-time path may voice."),
        el("div", { style: "margin-top:4px" },
          "Extras invent small local details — a name, an old grudge. These are recorded "
          + "as hearsay for the Director to confirm, contradict, or quietly drop; they "
          + "never become fact on their own."),
        el("div", {}, "Their manner and look follow ",
          el("b", {}, "Genre & style"), " — set the genre there first."),
        el("div", { style: "margin-top:4px" },
          el("b", {}, "Turns till auto-promotion"), " — how many turns of DELIBERATE "
          + "interaction turn an extra into a full character with a sheet, memory and "
          + "psychology. 0 (the default) never promotes anyone. The counter only moves "
          + "on a turn where you addressed them or a real character spoke to them — "
          + "extras chattering among themselves does not count, however long it goes "
          + "on. Promotion also has to be switched on globally in ⚙ API."))),
    el("div", { class: "small dim", style: "margin-top:10px" },
      "Prose pacing for NPC dialogue — how much NPCs tend to say, independent of autonomy above."),
    el("table", { class: "grid" },
      el("tr", {}, el("td", {}, "style"), el("td", {}, st)),
      el("tr", {}, el("td", {}, "min lines"), el("td", {}, mn)),
      el("tr", {}, el("td", {}, "max lines"), el("td", {}, mx)),
      el("tr", {}, el("td", {}, "variance"), el("td", {}, va))),
    el("div", { class: "row", style: "margin-top:8px" },
      el("button", { class: "primary", onclick: async () => {
        await api("PUT", `/api/chats/${chatId}/dialogue_config`, {
          style: st.value, min_lines: mn.value, max_lines: mx.value, variance: va.value,
          autonomy: +auto.value, allow_npc_initiative: npcInit.checked, allow_npc_to_npc_dialogue: npcNpc.checked,
          stop_on_player_address: stopAddr.checked, stop_on_question_to_player: stopQ.checked, silence_ends_exchange: silence.checked,
          promote_after_addressed: +promoteAfter.value,
          offscreen_life: offLife.value,
          max_offscreen_actors: +maxOffscreen.value
        });
        await api("PUT", `/api/chats/${chatId}/background_config`, {
          scene_life: sceneLife.value, max_managed: +maxManaged.value,
          max_reactors: +maxReactors.value
        });
        await api("PUT", `/api/chats/${chatId}/living_world`, {
          living_world: Object.fromEntries(
            Object.entries(lwSelects).map(([k, s]) => [k, s.value]))
        });
        closeModal(); toast("Dialogue config saved.", "ok");
      } }, "Save"))));
};

// The Cast modal used to be one long scrolling column: a bare persona
// row, a lorebook tree, a bare "Participants" header (styled differently
// from every other section's own card), then two more async panels
// (background presences, guest invites) each rendering cards-inside-
// cards with the parent panel. Four features, four ad-hoc layouts, no
// shared rhythm -- restructured into tabs sharing the same
// lore-inspector-tabs/lore-inspector-content treatment lorebooks.js's
// own inspector already uses, so this doesn't invent a second tab
// component.
$("#b-cast").onclick = async () => {
  if (!S.chatId) return;
  const chatId = S.chatId;
  const d = await api("GET", "/api/chats/" + chatId);
  if (S.chatId !== chatId) return;

  const tabs = [
    { id: "cast", label: "Cast", render: renderCastTab },
    { id: "lorebooks", label: "Lorebooks", render: renderLorebooksTab },
    { id: "condition", label: "Condition", render: renderConditionTab },
    { id: "insights", label: "Insights", render: renderInsightsTab },
    { id: "multiplayer", label: "Multiplayer", render: renderMultiplayerTab },
    { id: "frames", label: "Frames", render: renderFramesTab },
  ];
  let activeTab = "cast";

  modal("Cast, persona & lorebooks", b => {
    const tabBar = el("div", { class: "lore-inspector-tabs" });
    const content = el("div", { class: "lore-inspector-content" });

    function selectTab(tabId) {
      activeTab = tabId;
      for (const button of tabBar.querySelectorAll("button")) {
        button.classList.toggle("on", button.dataset.tab === tabId);
      }
      content.innerHTML = "";
      tabs.find(t => t.id === tabId).render(d, content, chatId);
    }

    for (const tab of tabs) {
      tabBar.append(el("button", {
        "data-tab": tab.id,
        class: tab.id === activeTab ? "on" : "",
        onclick: () => selectTab(tab.id),
      }, tab.label));
    }

    b.append(tabBar, content);
    selectTab(activeTab);
  }, { wide: true });
};

// The colour this character's spoken lines are tinted in the transcript.
// `p.dialogue_color` is the host's PICK ("" when they have not made one);
// `d.dialogue_colors[name]` is what they actually see, which for an unpicked
// character is derived from the authored psychology. The swatch shows the
// second and edits the first, and "auto" clears the pick rather than storing
// the derived value -- store it and the colour stops following the card.
//
// The server returns the whole re-resolved cast because colours are spread
// against each other: pinning one can legitimately move another, and
// repainting only this row would leave a stale palette on screen.
function dialogueColorControl(p, d, chatId) {
  const colors = d.dialogue_colors || {};
  const swatch = el("input", {
    type: "color",
    class: "dialogue-swatch",
    title: p.dialogue_color
      ? `Dialogue colour for ${p.name} (chosen)`
      : `Dialogue colour for ${p.name} (from their card)`,
    value: colors[p.name] || "#cccccc",
  });
  const auto = el("button", {
    class: "small",
    title: "Go back to the colour derived from this character's card",
    onclick: async () => { await save(""); },
  }, "auto");

  async function save(color) {
    const r = await api(
      "PUT", `/api/chats/${chatId}/characters/${p.id}/dialogue_color`,
      { color });
    p.dialogue_color = r.color || "";
    d.dialogue_colors = r.dialogue_colors || {};
    if (S.chat && S.chatId === chatId) {
      S.chat.dialogue_colors = d.dialogue_colors;
      renderChat();
    }
    swatch.value = d.dialogue_colors[p.name] || "#cccccc";
    auto.style.visibility = p.dialogue_color ? "visible" : "hidden";
  }

  // `change` rather than `input`: a colour picker fires continuously while
  // the user drags, and each one is a write plus a full transcript repaint.
  swatch.addEventListener("change", () => save(swatch.value));
  auto.style.visibility = p.dialogue_color ? "visible" : "hidden";
  return el("span", { class: "dialogue-color" }, swatch, auto);
}

function renderCastTab(d, b, chatId) {
  const ps = el("select", {}, [
    el("option", { value: "" }, "(no persona)"),
    ...S.boot.personas.map(p => el("option", {
      value: p.id,
      ...(p.id === d.chat.persona_id ? { selected: "" } : {})
    }, p.name))
  ]);
  ps.onchange = () =>
    api("PUT", "/api/chats/" + chatId, {
      persona_id: ps.value ? +ps.value : null
    });

  b.append(
    el("div", { class: "row" },
      "Persona: ", ps,
      el("button", {
        onclick: () => personaPH(chatId)
      }, "🔒 persona secrets")
    )
  );

  b.append(el("h4", {}, "Participants"));

  // Filled in by hydrateCastLocations once the scene has been read: the room
  // list lives in the scene blob, not in the chat payload this tab renders
  // from, so the row is drawn first and the control dropped in after.
  const locationSlots = new Map();
  const sceneSlot = el("div", { class: "small dim" });
  b.append(sceneSlot);

  for (const p of d.participants) {
    const locationSlot = el("span", { class: "cast-location" });
    locationSlots.set(p.id, locationSlot);

    b.append(el("div", { class: "card row" },
      el("b", {}, p.name),
      el("span", { class: "badge" }, p.status),
      p.card_source === "chat"
        ? el("span", { class: "badge" }, "story card") : null,
      locationSlot,
      el("span", { class: "spacer" }),
      dialogueColorControl(p, d, chatId),
      el("button", {
        title: "Edit this character card for this story only",
        onclick: () => charEditor(p, { chatId })
      }, "✏️ card"),
      el("button", {
        onclick: async () => {
          if (p.status === "active")
            await api("DELETE",
              `/api/chats/${chatId}/characters/${p.id}`);
          else
            await api("POST",
              `/api/chats/${chatId}/characters`,
              { char_id: p.id });
          closeModal();
          if (S.chatId === chatId) $("#b-cast").click();
        }
      }, p.status === "active"
        ? "→ dormant" : "→ active"),
      el("button", {
        title: "Memory browser",
        onclick: () => memModal(p)
      }, "🧠"),
      el("button", {
        title: "How this character feels about everyone else",
        onclick: () => relationshipModal(p, chatId)
      }, "💞"),
      el("button", {
        title: "Per-story private history",
        onclick: () => chatPH(p, chatId)
      }, "🔒")));
  }

  const inChat = new Set(
    d.participants.map(p => p.id)
  );
  const addOpts = S.boot.characters
    .filter(c => !inChat.has(c.id))
    .map(c => el("option", {
      value: c.id
    }, c.name));

  if (addOpts.length) {
    const addSel = el("select", {}, addOpts);
    b.append(
      el("div", {
        class: "row",
        style: "margin-top:8px"
      }, addSel,
        el("button", {
          onclick: async () => {
            await api("POST",
              `/api/chats/${chatId}/characters`,
              { char_id: +addSel.value });
            closeModal();
            if (S.chatId === chatId) $("#b-cast").click();
          }
        }, "+ add to story")));
  }

  b.append(renderBackgroundPresencesPanel(chatId));

  hydrateCastLocations(locationSlots, sceneSlot, chatId);

}

// ---- Condition tab ---------------------------------------------------------
// Where everyone's numbers live. The margin tracker shows the player by
// default because that is the body you act with; this is the full table,
// including every NPC, and it is why showing them beside the prose can stay
// off without the information being lost.

function renderConditionTab(d, b, chatId) {
  const panel = el("div");
  b.append(panel);
  hydrateConditionTab(panel, chatId);
}

async function hydrateConditionTab(panel, chatId) {
  if (!chatId) {
    return;
  }

  let data;
  try {
    data = await api("GET", `/api/chats/${chatId}/vitals${frameQuery()}`);
  } catch (error) {
    panel.append(emptyState("Could not read condition."));
    return;
  }
  if (!panel.isConnected) {
    return;
  }

  if (!data.enabled) {
    panel.append(el("div", { class: "small dim" },
      "This story does not track bodily condition. Turn it on in Genre & style — breath, stamina, nourishment and injury, moved by how much time each beat takes."));
    return;
  }

  if (!(data.bodies || []).length) {
    panel.append(emptyState("Nothing tracked yet."));
    return;
  }

  panel.append(el("div", { class: "small dim" },
    "Everyone this story is tracking. Your own condition also sits in the margin beside the prose; the rest appear there only if you switch that on."));

  for (const body of data.bodies) {
    const rows = el("div", { class: "vitals-grid full" });
    for (const row of VITAL_ROWS) {
      rows.append(
        el("span", { class: "vital-name" }, row.label),
        vitalMeter(body.vitals?.[row.key], row.invert),
        el("span", { class: "vital-word" }, body.labels?.[row.key] || "—")
      );
    }
    panel.append(el("div", { class: "card", style: "margin-top:8px" },
      el("div", { class: "row" },
        el("b", {}, body.name),
        body.is_player ? el("span", { class: "badge" }, "you") : null),
      rows));
  }

}

// ---- Survival tracker ------------------------------------------------------

const VITAL_ROWS = [
  { key: "air", label: "Air", invert: false },
  { key: "stamina", label: "Stamina", invert: false },
  { key: "nourishment", label: "Satiation", invert: false },
  { key: "injury", label: "Injury", invert: true }
];

function vitalMeter(value, invert) {
  const pct = Math.round(
    Math.max(0, Math.min(Number(value ?? (invert ? 0 : 1)), 1)) * 100
  );
  // For injury a HIGH number is bad; for the rest a low one is. One scale,
  // read the right way round, so green always means "fine".
  const severity = invert ? pct : 100 - pct;
  const tone = severity >= 70 ? "bad" : severity >= 40 ? "warn" : "ok";
  return el("div", { class: "vital-meter" },
    el("div", {
      class: `vital-fill ${tone}`,
      style: `width:${pct}%`
    })
  );
}

// The corner HUD. Rendered into #vitals, which sits opposite the activity
// panel so the two never collide, and styled to match it -- this is chrome,
// not content, and should read as part of the frame.
//
// It shows the player first and every other tracked body after, because the
// Director tracks NPCs too: a companion who is starving matters to the player
// even though it is not the player who is starving.
// Resize resistance, measured rather than guessed. The usable gutter is a
// function of #main's width, which changes when the window resizes AND when the
// sidebar collapses -- a media query on viewport width can only see one of
// those. This measures the real distance between #main's left edge and the
// centred transcript column, and hides the tracker when there is not enough of
// it rather than letting the margin note sit on top of the prose.
const VITALS_MIN_GUTTER = 186;
const VITALS_MAX_WIDTH = 232;

// The story column's width. It used to be a flat 720px, which left a wide
// window mostly empty either side of the transcript; it now grows into
// whatever space the furniture around it is not using, and stops there.
//
// STOPS THERE is the whole point. The vitals tracker and the ambience buttons
// float OVER #main (see "positions #vitals-npcs over the story" in
// styles.css); the sidebar and the pipeline drawer are in flow, so they
// already shrink #main and need no reservation here. Growing past the two
// floats would put prose underneath them.
//
// The TEXT does not widen with the panel -- .prose keeps its reading measure
// and gains margins instead, the way a book page gets wider. Past roughly
// 75-80 characters a line the eye loses the return sweep, so a wider column
// would undo the measure the prose face was chosen for.
//
// The reserve is symmetric because the column is centred: whichever side needs
// more room sets both. It keys on `hidden` (the panel holds nothing) rather
// than `fits` (the panel has no room), which is what stops this feeding back
// into itself -- `fits` is an OUTPUT of the width chosen here, so keying on it
// would let the column widen, evict the tracker, and widen again.
const STORY_MIN_WIDTH = 720;
const STORY_MAX_WIDTH = 1080;
const STORY_EDGE = 24;

function syncVitalsGutterNow() {
  const composer = $("#composer");
  const inner = $("#composer-inner");
  if (!composer || !inner) {
    return;
  }

  // ALL layout reads first, then all writes. This handler used to interleave
  // them (set --vitals-bottom, then read the player panel's offsetHeight),
  // which forces the browser to run layout synchronously mid-handler -- and
  // this runs on every resize frame and, via the ResizeObserver below, on
  // every keystroke that grows the composer.
  //
  // The input box is capped and centred inside #composer, so the gutter is
  // the real distance from the composer's left edge to the box. Measured from
  // the elements rather than assumed from the viewport, because the sidebar
  // collapsing changes it and no resize event reports that.
  const usable = Math.floor(
    inner.getBoundingClientRect().left - composer.getBoundingClientRect().left - 10
  );
  // The NPC panel sits ABOVE the composer, not over it. The composer's height
  // changes as the textarea grows, so this is measured every sync rather than
  // assumed -- a fixed offset put the panel on top of the input box.
  // Vertical placement. Both panels are stacked up from the bottom of #main:
  // yours starts just above the composer, theirs above yours. Measured every
  // sync because the composer grows as you type and either panel's height
  // depends on how many bodies it holds.
  const band = composer.offsetHeight;
  const playerHost = $("#vitals");
  const npcHost = $("#vitals-npcs");
  // Read with the other measurements, ahead of every write. The ambience
  // cluster is measured rather than assumed: it is a variable number of icon
  // buttons and it grows when a track is playing.
  const shellWidth = composer.getBoundingClientRect().width;
  const ambBar = $("#ambience-bar");
  const ambWidth = ambBar ? Math.ceil(ambBar.getBoundingClientRect().width) : 0;

  const playerVisible = playerHost && !playerHost.classList.contains("hidden");
  // Read up here with the other measurements: the panel's own height does not
  // depend on the --vitals-bottom write below (that only moves it), so the
  // value is identical to the old post-write read, minus the forced layout.
  const playerHeight = playerVisible ? playerHost.offsetHeight : 0;
  if (playerHost) {
    playerHost.style.setProperty("--vitals-bottom", (band + 12) + "px");
  }
  if (npcHost) {
    const above = playerVisible ? playerHeight + 10 : 0;
    npcHost.style.setProperty("--vitals-bottom", (band + 12 + above) + "px");
  }
  // Widest the story column may be without running under either float. The
  // tracker sits on the left and the ambience cluster on the right; the column
  // is centred, so the larger of the two claims both margins.
  const npcVisible = npcHost && !npcHost.classList.contains("hidden");
  const trackerPresent = Boolean(playerVisible || npcVisible);
  const reserve = Math.max(
    STORY_EDGE,
    trackerPresent ? VITALS_MIN_GUTTER + 12 : 0,
    ambWidth ? ambWidth + 20 : 0,
  );
  const storyWidth = Math.round(Math.min(
    STORY_MAX_WIDTH,
    Math.max(STORY_MIN_WIDTH, shellWidth - reserve * 2),
  ));
  // On the root, beside --bd-panel: the transcript and the composer both read
  // it, and they must not disagree -- #composer-inner shares the column so the
  // input box keeps the same left and right edge as the prose above it.
  document.documentElement.style.setProperty("--story-width", storyWidth + "px");

  const fits = usable >= VITALS_MIN_GUTTER;
  const width = Math.min(Math.max(usable, 0), VITALS_MAX_WIDTH) + "px";

  for (const host of [playerHost, npcHost]) {
    if (!host) {
      continue;
    }
    host.style.setProperty("--vitals-width", width);
    host.style.setProperty("--vitals-left", "12px");
    // Never let geometry resurrect a panel with nothing in it.
    if (fits && !host.classList.contains("hidden")) {
      host.classList.add("fits");
    } else {
      host.classList.remove("fits");
    }
  }
}

// Public form: coalesced to one run per painted frame. Resize fires this per
// frame while dragging the window edge, the ResizeObserver fires it per
// keystroke, and refreshVitalsHud calls it twice back-to-back -- each call
// was a full measure-and-write pass. One pass per frame is all the screen
// can show anyway.
let _vitalsGutterQueued = false;
function syncVitalsGutter() {
  if (_vitalsGutterQueued) return;
  _vitalsGutterQueued = true;
  requestAnimationFrame(() => {
    _vitalsGutterQueued = false;
    syncVitalsGutterNow();
  });
}

window.syncVitalsGutter = syncVitalsGutter;
window.addEventListener("resize", syncVitalsGutter);
// A theme may change any of the three things this measure depends on: the
// sidebar's width, the composer's padding, and the ambience cluster's own
// footprint. The observer below catches the first two because they resize
// #composer, but the ambience bar is absolutely positioned inside it, so a
// theme that only re-pads THAT would leave the reserve stale until the next
// window resize -- a tracker sitting under the cluster, or hidden for want of
// a gutter it actually has. The event already exists; this is the listener it
// was missing.
window.addEventListener("sonder-theme-change", syncVitalsGutter);
if (window.ResizeObserver) {
  // Catches the sidebar collapsing, which no resize event reports.
  const observed = $("#composer");
  if (observed) {
    new ResizeObserver(syncVitalsGutter).observe(observed);
  }
  // And the AMBIENCE CLUSTER, which is the other half of the reserve above and
  // was the half nobody watched. Its width is an input to --story-width, and
  // it changes for reasons that never resize #composer: the volume slider
  // dropping out at the container-query breakpoint, the bar growing when a
  // track starts (the read above says so in as many words), and a themed
  // webfont swapping in under the controls after first paint. Whenever it grew
  // after the one measure that mattered, the story column stayed as wide as
  // the stale figure allowed and the send button was laid out into space the
  // cluster had since taken -- measured at 19px of overlap, send sitting under
  // the mute control. Absolutely positioned, so it cannot report this by
  // resizing its parent; it has to be observed directly.
  const ambBar = $("#ambience-bar");
  if (ambBar) {
    new ResizeObserver(syncVitalsGutter).observe(ambBar);
  }
}

function hideVitalsHud(host) {
  if (!host) {
    return;
  }
  host.classList.add("hidden");
  host.classList.remove("fits");
  host.innerHTML = "";
}

function vitalsBlock(body) {
  const rows = el("div", { class: "vitals-grid" });
  for (const row of VITAL_ROWS) {
    rows.append(
      el("span", { class: "vital-name" }, row.label),
      vitalMeter(body.vitals?.[row.key], row.invert),
      el("span", { class: "vital-word" }, body.labels?.[row.key] || "—")
    );
  }
  return el("div", {
    class: "vitals-body" + (body.is_player ? "" : " npc")
  },
    body.is_player
      ? null
      : el("div", { class: "vitals-who" }, body.name),
    rows);
}

async function refreshVitalsHud() {
  const host = $("#vitals");
  if (!host) {
    return;
  }

  if (!S.chatId) {
    hideVitalsHud(host);
    hideVitalsHud($("#vitals-npcs"));
    return;
  }

  // Which story this refresh is FOR. It is fired without await from openChat,
  // so switching stories quickly can land an old chat's response after the new
  // one's -- which left the previous story's tracker sitting there. Same guard
  // the lorebook workspace uses for its own superseded loads.
  const wanted = S.chatId;

  let data;
  try {
    data = await api("GET", `/api/chats/${wanted}/vitals${frameQuery()}`);
  } catch (error) {
    if (S.chatId === wanted) {
      hideVitalsHud(host);        // a tracker must never break the story view
      hideVitalsHud($("#vitals-npcs"));
    }
    return;
  }

  if (S.chatId !== wanted) {
    return;                       // a newer story superseded this load
  }

  if (!data.enabled || !(data.bodies || []).length) {
    hideVitalsHud(host);
    hideVitalsHud($("#vitals-npcs"));
    return;
  }

  // Two homes, because they are two different things. YOURS sits in the gutter
  // beside the input box -- the body you act with, always in view while you
  // type. THEIRS is opt-in and rendered over the story background above it,
  // where there is room for more than one and where it can stay quiet.
  const player = (data.bodies || []).filter(b => b.is_player);
  const others = data.show_npcs
    ? (data.bodies || []).filter(b => !b.is_player)
    : [];

  if (player.length) {
    // Identical structure to the NPC panel: heading, then a labelled row per
    // vital. The two read as the same object in two places, which is the point.
    host.innerHTML = "";
    host.append(el("div", { id: "vitals-head" }, "Condition"));
    const list = el("div", { id: "vitals-list" });
    player.forEach(b => list.append(vitalsBlock(b)));
    host.append(list);
    host.classList.remove("hidden");
  } else {
    hideVitalsHud(host);
  }

  const npcHost = $("#vitals-npcs");
  if (npcHost) {
    if (others.length) {
      npcHost.innerHTML = "";
      npcHost.append(el("div", { id: "vitals-npcs-head" }, "Others"));
      others.forEach(b => npcHost.append(vitalsBlock(b)));
      npcHost.classList.remove("hidden");
    } else {
      hideVitalsHud(npcHost);
    }
  }

  syncVitalsGutter();
  requestAnimationFrame(syncVitalsGutter);
}

function clearVitalsHud() {
  hideVitalsHud($("#vitals"));
  hideVitalsHud($("#vitals-npcs"));
}

window.clearVitalsHud = clearVitalsHud;
window.refreshVitalsHud = refreshVitalsHud;

// ---- Character relocation --------------------------------------------------
// Moving someone is an authoring edit, not a story beat: it changes the scene
// and narrates nothing, exactly like the world and attire editors. The scene
// blob is the only source of truth for live positions, so this reads and
// writes there and nowhere else.

async function hydrateCastLocations(slots, sceneSlot, chatId) {
  if (!slots.size || !chatId) {
    return;
  }

  let data;
  try {
    data = await api("GET", `/api/chats/${chatId}/positions${frameQuery()}`);
  } catch (error) {
    // Relocation is an addition to this tab, not its purpose -- a failed
    // lookup must leave the rest of the cast panel working.
    return;
  }

  const rooms = data.rooms || [];

  // Where the player stands, for orientation only. Moving the player is the
  // story's business, not an authoring dropdown's.
  if (sceneSlot?.isConnected && data.persona) {
    const here = rooms.find(r => r.id === data.persona.room);
    sceneSlot.textContent = data.location
      ? `${data.location} — ${data.persona.name} is `
        + (here ? `in ${castRoomLabel(here)}.` : "not placed in a room.")
      : "";
  }

  for (const [charId, slot] of slots) {
    if (!slot.isConnected) {
      continue;
    }

    slot.innerHTML = "";

    if (!rooms.length) {
      slot.append(el("span", { class: "small dim" },
        "no scene yet — nowhere to stand"));
      continue;
    }

    const person = (data.characters || [])
      .find(c => c.id === charId);

    slot.append(castRoomSelect(charId, person, rooms, chatId));
  }
}

function castRoomLabel(room) {
  // An interior room is named with what it is inside: "Console Room" alone
  // does not say which ship.
  return room.parent_name
    ? `${room.parent_name} › ${room.name}`
    : room.name;
}

function castRoomSelect(charId, person, rooms, chatId) {
  const current = person?.room || "";
  // The last value the server accepted, which is what a failed move reverts
  // to -- not the room they were in when this dropdown was built, which goes
  // stale the moment one move succeeds.
  let settled = current;

  const select = el("select", {
    class: "cast-room-select",
    title: "Which room this character is in"
  },
    el("option", {
      value: "",
      ...(current ? {} : { selected: "" })
    }, "— offscreen —"),
    ...rooms.map(room => el("option", {
      value: room.id,
      ...(current === room.id ? { selected: "" } : {})
    }, castRoomLabel(room)))
  );

  select.onchange = async () => {
    const target = select.value;
    const room = rooms.find(r => r.id === target);

    select.disabled = true;
    try {
      await api(
        "PUT",
        `/api/chats/${chatId}/characters/${charId}/position${frameQuery()}`,
        { room: target }
      );

      if (person) {
        person.room = target || null;
      }
      settled = target;

      toast(
        target
          ? `Moved ${person?.name || "character"} to `
            + `${room ? castRoomLabel(room) : target}.`
          : `${person?.name || "Character"} is now offscreen.`,
        "ok"
      );
    } catch (error) {
      // Never leave the dropdown asserting a move the server refused (a
      // running pipeline, a room that vanished).
      select.value = settled;
      toast(error?.message || String(error), "err", 8000);
    } finally {
      select.disabled = false;
    }
  };

  return select;
}

function renderLorebooksTab(d, b, chatId) {
    // ── Lorebook tree panel ──
    const lbPanel = el("div", { class: "card" });
    lbPanel.append(el("h4", {}, "Lorebooks"));

    const refreshBooks = async () => {
      const dd = await api("GET", "/api/chats/" + chatId);
      const attached = dd.lorebooks || [];
      lbPanel.innerHTML = "";
      lbPanel.append(el("h4", {}, "Lorebooks"));

      if (!attached.length) {
        lbPanel.append(el("div", { class: "dim small" },
          "No lorebooks attached."));
      }

      // Build parent→children map for attached books
      const byParent = new Map();
      for (const lb of attached) {
        const key = lb.parent_id == null
          ? "root"
          : String(lb.parent_id);
        if (!byParent.has(key))
          byParent.set(key, []);
        byParent.get(key).push(lb);
      }
      for (const kids of byParent.values())
        kids.sort((a, b) =>
          (a.sort_order || 0) - (b.sort_order || 0)
          || a.name.localeCompare(b.name)
        );

      const treeEl = el("div", { class: "lore-side-tree" });

      function renderBookNode(lb, depth) {
        const kids = byParent.get(String(lb.id)) || [];
        const isCanon = lb.canon;
        const indent = depth * 14;

        const row = el("div", {
          class: "lore-side-row",
          style: `margin-left:${indent}px`
        },
          el("span", {
            class: "lore-side-name",
            title: lb.name
          },
            `${loreBookTypeIcon(lb.book_type)} ${lb.name}`
          ),
          el("span", { class: "lore-side-meta" },
            el("span", { class: "badge" },
              lb.book_type || "general"),
            isCanon
              ? el("span", {
                  class: "badge",
                  style: "margin-left:4px"
                }, "canon")
              : null,
            el("button", {
              title: "Open in workspace",
              onclick: () => {
                closeModal();
                openLoreWorkspace(lb.id);
              }
            }, "open"),
            el("button", {
              title: "Export",
              onclick: async () => {
                await exportLorebook(lb.id);
              }
            }, "⤓"),
            el("button", {
              title: "Generate entries",
              onclick: () =>
                generateLoreModal(lb.id)
            }, "✨"),
            // Silencing is not detaching. `chat_lorebooks.enabled` was read
            // by retrieval, checkpoints, the archive and both browser
            // payloads, and written by nothing -- so a host could only
            // remove a body of lore, never set it aside. Detaching a
            // story-owned book deletes its entries; this leaves them.
            !isCanon
              ? el("button", {
                  title: lb.enabled === false
                    ? "Let this book be retrieved again"
                    : "Keep this book but stop retrieving from it",
                  onclick: async () => {
                    await api("PUT",
                      `/api/chats/${chatId}/lorebooks/${lb.id}`,
                      { enabled: lb.enabled === false });
                    refreshBooks();
                  }
                }, lb.enabled === false ? "🔇" : "🔊")
              : null,
            !isCanon
              ? el("button", {
                  title: "Detach from story",
                  onclick: async () => {
                    await api("DELETE",
                      `/api/chats/${chatId}/lorebooks/${lb.id}`);
                    refreshBooks();
                  }
                }, "✕")
              : null
          )
        );

        const node = el("div", {
          class: "lore-side-node"
        }, row);

        for (const child of kids) {
          node.append(renderBookNode(child, depth + 1));
        }

        return node;
      }

      const roots = byParent.get("root") || [];
      for (const root of roots) {
        treeEl.append(renderBookNode(root, 0));
      }

      // Orphans (parent not in this chat)
      const rendered = new Set(attached.map(lb => lb.id));
      for (const lb of attached) {
        if (
          lb.parent_id != null
          && !rendered.has(lb.parent_id)
          && !roots.includes(lb)
        ) {
          // Skip — already rendered as descendant
        }
      }

      lbPanel.append(treeEl);

      // Attach dropdown
      const attachedIds = new Set(
        attached.map(lb => lb.id)
      );
      const addOpts = S.boot.lorebooks
        .filter(lb => !attachedIds.has(lb.id))
        .map(lb => el("option", {
          value: lb.id
        }, lb.name + (lb.book_type
          ? " [" + lb.book_type + "]"
          : "")));

      if (addOpts.length) {
        const addSel = el("select", {}, addOpts);
        lbPanel.append(
          el("div", {
            class: "row",
            style: "margin-top:8px"
          }, addSel,
            el("button", {
              onclick: async () => {
                await api("POST",
                  `/api/chats/${chatId}/lorebooks`,
                  { lorebook_id: +addSel.value });
                refreshBooks();
              }
            }, "+ attach"))
        );
      }
    };

    refreshBooks();

    b.append(lbPanel,
      el("div", {
        class: "small dim",
        style: "margin:4px 0 10px"
      },
        "Attached books are story-local duplicates; "
        + "updating them changes this story's world, "
        + "not the global library. The canon book is "
        + "updated by the mapping agent."));
}

function renderMultiplayerTab(d, b, chatId) {
  b.append(renderGuestInvitePanel(chatId));
}

// ── Frames: diegetic eras, persona stationing, and paradox settings ──
// Frames let a story visit a different point in its own timeline --
// serially (one era live at a time, switched via the frame pills in the
// header) or with genuinely simultaneous play once more than one
// attached persona is stationed to a different frame (frames.py/
// db.py's active_frame_id contextvar is what actually makes two frames'
// pipelines safe to run at once, not anything in this panel).
function renderFramesTab(d, b, chatId) {
  b.append(renderFramesListPanel(d, chatId));
  b.append(renderPersonaStationingPanel(chatId));
  b.append(renderParadoxPanel(chatId));
}

function renderFramesListPanel(d, chatId) {
  const panel = el("div", {});
  const refresh = async () => {
    panel.innerHTML = "";
    panel.append(el("div", { class: "lore-panel-head" },
      el("span", { class: "lore-panel-title" }, "Frames")));
    panel.append(el("div", { class: "small dim", style: "margin-bottom:8px" },
      "Declare a different era of this same story -- a flash-forward, a visit "
      + "to the past. Switch between them with the pills next to the story name."));

    const { frames } = await api("GET", `/api/chats/${chatId}/frames`);
    for (const f of frames) {
      if (f.id === null) continue; // the implicit present -- nothing to show
      panel.append(el("div", { class: "card row" },
        el("b", {}, f.label),
        el("span", { class: "badge" }, f.kind),
        el("span", { class: "small dim" }, `ordinal ${f.ordinal}`),
        f.travelers.length
          ? el("span", { class: "small dim" }, `${f.travelers.length} traveler(s)`)
          : null,
        f.nonexistent_cast.length
          ? el("span", { class: "small dim" }, `${f.nonexistent_cast.length} not-yet-existing`)
          : null));
    }

    const labelIn = el("input", { placeholder: "Label, e.g. \"Far future\"" });
    const ordinalIn = el("input", { type: "number", placeholder: "Ordinal (negative = past)", value: "0" });
    const kindSel = el("select", {},
      el("option", { value: "future" }, "future"),
      el("option", { value: "past" }, "past"),
      el("option", { value: "other" }, "other"));
    const castOpts = () => (d.participants || []).map(p => el("option", { value: p.id }, p.name));
    const travelersSel = el("select", { multiple: "", size: "3", title: "Characters who keep full memory continuity here" }, ...castOpts());
    const nonexistentSel = el("select", { multiple: "", size: "3", title: "Characters not yet recognized by natives of this era" }, ...castOpts());

    panel.append(
      el("div", { class: "small dim", style: "margin-top:10px" }, "New frame:"),
      el("div", { class: "row", style: "margin-top:4px;flex-wrap:wrap" }, labelIn, ordinalIn, kindSel),
      el("div", { class: "row", style: "margin-top:6px;flex-wrap:wrap" },
        el("div", {}, el("div", { class: "small dim" }, "Travelers"), travelersSel),
        el("div", {}, el("div", { class: "small dim" }, "Not yet existing"), nonexistentSel)),
      el("div", { class: "row", style: "margin-top:8px" },
        el("button", {
          class: "primary",
          onclick: async () => {
            const label = labelIn.value.trim();
            if (!label) { toast("Give the frame a label.", "warn"); return; }
            try {
              await api("POST", `/api/chats/${chatId}/frames`, {
                label, ordinal: +ordinalIn.value || 0, kind: kindSel.value,
                travelers: [...travelersSel.selectedOptions].map(o => +o.value),
                nonexistent_cast: [...nonexistentSel.selectedOptions].map(o => +o.value),
              });
              toast("Frame created.", "ok");
              if (S.chatId === chatId) {
                await openChat(chatId); // refresh the frame pills too
              }
              refresh();
            } catch (e) {
              toast(`Could not create frame: ${e.message}`, "err");
            }
          }
        }, "+ Create frame")));
  };
  refresh();
  return panel;
}

function renderPersonaStationingPanel(chatId) {
  const panel = el("div", { style: "margin-top:14px" });
  const refresh = async () => {
    panel.innerHTML = "";
    panel.append(el("div", { class: "lore-panel-head" },
      el("span", { class: "lore-panel-title" }, "Who's where")));

    const [{ personas }, { frames }] = await Promise.all([
      api("GET", `/api/chats/${chatId}/personas`),
      api("GET", `/api/chats/${chatId}/frames`),
    ]);

    if (!personas.length) {
      panel.append(el("div", { class: "small dim" },
        "No extra players attached yet -- invite one from the Multiplayer tab first."));
      return;
    }

    for (const p of personas) {
      const sel = el("select", {},
        ...frames.map(f => el("option", {
          value: f.id === null ? "" : f.id,
          ...(p.frame_id === f.id ? { selected: "" } : {}),
        }, f.id === null ? "Present" : f.label)));
      sel.onchange = async () => {
        try {
          await api("PUT", `/api/chats/${chatId}/personas/${p.id}/station`,
            { frame_id: sel.value ? +sel.value : null });
          toast(`${p.name} is now in ${sel.options[sel.selectedIndex].text}.`, "ok");
        } catch (e) {
          toast(`Could not move them: ${e.message}`, "err");
          refresh();
        }
      };
      panel.append(el("div", { class: "card row" }, el("b", {}, p.name), sel));
    }
  };
  refresh();
  return panel;
}

function renderParadoxPanel(chatId) {
  const panel = el("div", { style: "margin-top:14px" });
  const refresh = async () => {
    panel.innerHTML = "";
    panel.append(el("div", { class: "lore-panel-head" },
      el("span", { class: "lore-panel-title" }, "Time paradox resolution")));
    panel.append(el("div", { class: "small dim", style: "margin-bottom:8px" },
      "What happens if a fixed point gets altered -- not every timeline hiccup, "
      + "only ones you deliberately pin below as load-bearing."));

    const [policy, { fixed_points, paradoxes }, { frames }] = await Promise.all([
      api("GET", `/api/chats/${chatId}/paradox_policy`),
      api("GET", `/api/chats/${chatId}/fixed_points`),
      api("GET", `/api/chats/${chatId}/frames`),
    ]);

    // Each frame has its OWN independent paradox slot -- more than one
    // can genuinely be active at once under concurrent multi-frame play,
    // so this lists every active one rather than assuming just one.
    const frameLabel = new Map(frames.map(f => [f.id, f.label]));
    for (const active of (paradoxes || [])) {
      panel.append(el("div", { class: "card row", style: "border-color:var(--danger,#c0392b)" },
        el("b", {}, "⚠ Paradox active: " + active.label),
        el("span", { class: "badge" }, frameLabel.get(active.frame_id) || "Present"),
        el("span", { class: "badge" }, `severity ${Math.round((active.severity || 0) * 100)}%`),
        el("span", { class: "badge" }, active.mode)));
    }

    const modeSel = el("select", {},
      ...["dread", "hazard", "toll", "warden", "bureau"].map(m => el("option", {
        value: m, ...(policy.mode === m ? { selected: "" } : {}),
      }, m)));
    modeSel.onchange = async () => {
      await api("PUT", `/api/chats/${chatId}/paradox_policy`, { mode: modeSel.value });
      toast("Paradox policy updated.", "ok");
    };
    panel.append(el("div", { class: "row" },
      el("span", { class: "small dim" }, "Default consequence:"), modeSel));

    panel.append(el("div", { class: "small dim", style: "margin-top:10px" }, "Fixed points:"));
    if (!fixed_points.length) {
      panel.append(el("div", { class: "small dim" }, "None declared -- ordinary changes to the past are safely absorbed."));
    }
    for (const fp of fixed_points) {
      panel.append(el("div", { class: "card row" },
        el("b", {}, fp.label),
        el("span", { class: "small dim" }, fp.required_exists ? `${fp.entity_id} must exist` : `${fp.entity_id} must NOT exist`),
        el("button", {
          onclick: async () => {
            await api("DELETE", `/api/chats/${chatId}/fixed_points/${fp.anchor_id}`);
            refresh();
          }
        }, "✕")));
    }

    const entityIn = el("input", { placeholder: "Entity id, e.g. \"pete\"" });
    const labelIn = el("input", { placeholder: "What's at stake, e.g. \"Pete must die in the crash\"" });
    const requireSel = el("select", {},
      el("option", { value: "1" }, "must exist"),
      el("option", { value: "0" }, "must NOT exist"));
    panel.append(el("div", { class: "row", style: "margin-top:6px;flex-wrap:wrap" },
      entityIn, requireSel, labelIn,
      el("button", {
        class: "primary",
        onclick: async () => {
          if (!entityIn.value.trim() || !labelIn.value.trim()) {
            toast("Fill in both the entity id and the label.", "warn");
            return;
          }
          try {
            await api("POST", `/api/chats/${chatId}/fixed_points`, {
              entity_id: entityIn.value.trim(), label: labelIn.value.trim(),
              required_exists: requireSel.value === "1",
            });
            toast("Fixed point declared.", "ok");
            refresh();
          } catch (e) {
            toast(`Could not declare it: ${e.message}`, "err");
          }
        }
      }, "+ Declare")));
  };
  refresh();
  return panel;
}

// ── Background presences ──
// Suggestion chips for named entities the director has kept present and
// active without a character sheet (agents/director.py's dialogue-log
// license + commit.py's track_background_presences) -- promotion is
// always user-confirmed, never automatic, since generating a sheet costs
// a real LLM call and a permanent cast slot for what might be a one-off.
function renderBackgroundPresencesPanel(chatId) {
  const panel = el("div", {});
  panel.append(el("div", { class: "lore-panel-head" },
    el("span", { class: "lore-panel-title" }, "Background presences")));

  api("GET", `/api/chats/${chatId}/promotable`).then(({ presences }) => {
    if (!presences.length) {
      panel.append(el("div", { class: "small dim" },
        "None tracked yet -- named entities the story keeps present without a character sheet will show up here."));
      return;
    }
    for (const p of presences) {
      const row = el("div", { class: "card row" },
        el("b", {}, p.name),
        el("span", { class: "small dim" },
          `${p.dialogue_turns.length} line(s), ${p.mention_turns.length} mention(s)`));
      if (p.promotable) {
        row.append(el("button", {
          onclick: () => promoteBackgroundPresence(chatId, p.name),
        }, "✨ Promote to character"));
      } else {
        row.append(el("span", { class: "badge" }, "not yet"));
      }
      panel.append(row);
    }
  }).catch(() => {
    panel.append(el("div", { class: "small dim" }, "Could not load."));
  });

  return panel;
}

// ── Invite a friend ──
// A friend joins as an additional persona attached to this chat via the
// existing chat_personas/turn_player_inputs multiplayer mechanism
// (agents/runtime.py's _load_extra_players already folds their declared
// input into the same beat) -- this panel just adds the missing "attach
// a persona as an extra player" + "generate a join code for them" UI on
// top of plumbing that otherwise only had HTTP-level test coverage.
function renderGuestInvitePanel(chatId) {
  const panel = el("div", {});

  const refresh = async () => {
    panel.innerHTML = "";
    panel.append(el("div", { class: "lore-panel-head" },
      el("span", { class: "lore-panel-title" }, "Invite a friend")));

    const extras = await api("GET", `/api/chats/${chatId}/personas`).catch(() => ({ personas: [] }));
    const attached = extras.personas || [];

    if (attached.length) {
      const invites = (await api("GET", `/api/chats/${chatId}/guest_invites`)).grants;
      for (const p of attached) {
        const row = el("div", { class: "card row" }, el("b", {}, p.name));
        const forThisPersona = invites.filter(g => g.persona_id === p.id);
        const active = forThisPersona.find(g => g.status === "active" || g.status === "pending");
        if (active) {
          row.append(
            el("span", { class: "badge" }, active.status),
            active.status === "pending"
              ? el("code", { class: "small" }, "(code already shared)")
              : null,
            el("button", {
              title: "Revoke", onclick: async () => {
                await api("DELETE", `/api/chats/${chatId}/guest_invites/${active.id}`);
                refresh();
              }
            }, "revoke")
          );
        } else {
          row.append(el("button", {
            onclick: async () => {
              const invite = await api("POST", `/api/chats/${chatId}/guest_invites`,
                { persona_id: p.id });
              const link = `${location.origin}/guest?code=${invite.code}`;
              modal("Share this with your friend", b => b.append(
                el("div", { class: "small dim", style: "margin-bottom:8px" },
                  "This link works once, expires in 30 minutes, and only lets them play as "
                  + p.name + ". They'll need this to actually be reachable -- run a tunnel "
                  + "(e.g. cloudflared tunnel --url http://localhost:8008) and swap this "
                  + "page's origin for the tunnel's public URL before sending it. "
                  + "Start the server with SONDER_PUBLIC=1 when you do: without it the "
                  + "session cookies are sent without the Secure flag, so anything that "
                  + "reaches this origin over plain http can read them."),
                el("input", { readonly: "", value: link, style: "width:100%", onclick: e => e.target.select() }),
                el("div", { class: "row", style: "margin-top:8px" },
                  el("button", { class: "primary", onclick: () => { navigator.clipboard?.writeText(link); toast("Copied.", "ok") } }, "📋 Copy link"))));
              refresh();
            }
          }, "🔗 Generate invite"));
        }
        // Attaching was the only half with a control. `DELETE
        // /api/chats/{cid}/personas/{pid}` has always existed and marks the
        // attachment dormant AND revokes that player's live guest sessions in
        // one transaction -- the two halves of the same lifecycle. Without a
        // button, an extra player who joined once could never be removed
        // except by editing the database.
        row.append(el("button", {
          title: "Detach this player",
          style: "margin-left:auto",
          onclick: async () => {
            if (!await confirmModal(
              `Detach ${p.name}? Any invite or live session of theirs stops `
              + `working. The persona itself is kept, and you can attach them `
              + `again later.`,
              { danger: true, confirmLabel: "Detach" })) return;
            await api("DELETE", `/api/chats/${chatId}/personas/${p.id}`);
            await boot();
            refresh();
            toast(`${p.name} detached.`, "ok");
          }
        }, "detach"));
        panel.append(row);
      }
    } else {
      panel.append(el("div", { class: "small dim" }, "No extra players attached yet."));
    }

    const genOpt = el("option", { value: "generate" }, "✨ New persona for them");
    const existingOpts = S.boot.personas.map(p => el("option", { value: String(p.id) }, p.name));
    const sel = el("select", {}, genOpt, ...existingOpts);
    const nameIn = el("input", { placeholder: "Their character's name", style: "display:none" });
    sel.onchange = () => { nameIn.style.display = sel.value === "generate" ? "" : "none" };

    panel.append(
      el("div", { class: "small dim", style: "margin-top:10px" }, "Attach another player:"),
      el("div", { class: "row", style: "margin-top:4px" }, sel, nameIn,
        el("button", {
          onclick: async () => {
            let pid = sel.value === "generate" ? null : +sel.value;
            if (!pid) {
              const r = await api("POST", "/api/personas", {
                name: nameIn.value.trim() || "Guest Player",
              });
              pid = r.id;
            }
            await api("POST", `/api/chats/${chatId}/personas`, { persona_id: pid });
            await boot();
            refresh();
          }
        }, "+ attach")));
  };

  refresh();
  return panel;
}

// ── Insights: dramatic irony + promise ledger ──
// Both are meta/GM-level views across every character's private memories
// at once -- deliberately host-only (not in GUEST_ALLOWED_API_PATHS),
// since the whole point of the perception/memory layering is that no
// single character or player legitimately sees this. Neither panel
// claims to know a belief is wrong or a promise was broken/kept: that
// judgment call belongs to whoever reads it, not a keyword heuristic.
function renderInsightsTab(d, b, chatId) {
  b.append(renderDramaticIronyPanel(chatId));
  b.append(renderPromiseLedgerPanel(chatId));
}

function renderDramaticIronyPanel(chatId) {
  const panel = el("div", {});
  panel.append(el("div", { class: "lore-panel-head" },
    el("span", { class: "lore-panel-title" }, "Dramatic irony")));
  panel.append(el("div", { class: "small dim", style: "margin-bottom:6px" },
    "What each character currently believes without having witnessed it firsthand -- secondhand, told, or inferred. Whether it's actually wrong is for you to judge."));

  api("GET", `/api/chats/${chatId}/dramatic_irony`).then(({ feed }) => {
    if (!feed.length) {
      panel.append(el("div", { class: "small dim" },
        "Nothing tracked yet -- beliefs a character formed secondhand or by inference will show up here."));
      return;
    }
    for (const m of feed) {
      panel.append(el("div", { class: "card row", style: "align-items:flex-start" },
        el("div", { style: "flex:1" },
          el("div", {},
            el("b", {}, m.char_name), " ",
            el("span", { class: "badge" }, m.provenance),
            m.turn_idx != null ? el("span", { class: "small dim", style: "margin-left:6px" }, `turn ${m.turn_idx}`) : null),
          el("div", { class: "small", style: "margin-top:2px" }, m.gist || m.content))));
    }
  }).catch(() => {
    panel.append(el("div", { class: "small dim" }, "Could not load."));
  });

  return panel;
}

function renderPromiseLedgerPanel(chatId) {
  const panel = el("div", { style: "margin-top:14px" });
  panel.append(el("div", { class: "lore-panel-head" },
    el("span", { class: "lore-panel-title" }, "Promise ledger")));
  panel.append(el("div", { class: "small dim", style: "margin-bottom:6px" },
    "Every promise-category memory across the whole story, in order. Kept or broken is a judgment call this doesn't make for you."));

  api("GET", `/api/chats/${chatId}/promises`).then(({ promises }) => {
    if (!promises.length) {
      panel.append(el("div", { class: "small dim" },
        "No promises tracked yet."));
      return;
    }
    for (const m of promises) {
      panel.append(el("div", { class: "card row", style: "align-items:flex-start" },
        el("div", { style: "flex:1" },
          el("div", {},
            el("b", {}, m.char_name),
            m.turn_idx != null ? el("span", { class: "small dim", style: "margin-left:6px" }, `turn ${m.turn_idx}`) : null),
          el("div", { class: "small", style: "margin-top:2px" }, m.gist || m.content))));
    }
  }).catch(() => {
    panel.append(el("div", { class: "small dim" }, "Could not load."));
  });

  return panel;
}

// ---- API connections ----

// Concrete model names age fast, so this leads with a durable tier rule
// (what property to look for) and treats specific names as "e.g." examples
// rather than an authoritative list -- keeps it useful without overpromising
// permanence. Keyed by the same provider `kind` strings used in
// provider_presets, so it lines up with the dropdown when adding a provider.
const MODEL_RECOMMENDATIONS = {
  anthropic: "Pick the current flagship Claude (Opus or Sonnet) for narrator/character_major; a smaller Claude (Haiku) is fine for mapping/utility.",
  openai: "Pick the current flagship GPT for narrator/character_major; a 'mini'/'nano'-tier variant is fine for mapping/utility.",
  gemini: "Pick the current flagship Gemini Pro for narrator/character_major; Gemini Flash is fine for mapping/utility.",
  deepseek: "DeepSeek's main chat/reasoning model works well for narrator/character_major; it's inexpensive enough that lightening other roles matters less.",
  xai: "Pick the current flagship Grok for narrator/character_major; a smaller/faster Grok variant for mapping/utility.",
  mistral: "Pick a 'large' Mistral model for narrator/character_major; a 'small'/'nemo' variant for mapping/utility.",
  groq: "Groq hosts other labs' open-weight models at very high speed -- pick the largest Llama/Qwen/Mixtral-family model it serves for narrator/character_major, a smaller one for the rest.",
  together: "Together hosts many open-weight models -- prefer a 70B+ Llama/Qwen/DeepSeek-family model for narrator/character_major, a smaller one for mapping/utility.",
  openrouter: "Aggregates most providers above under one key -- the same per-role sizing logic applies; OpenRouter's model list shows context length and price per model to help compare.",
  nanogpt: "Also an aggregator with a large open-weight catalog -- prefer a well-known, large instruction-tuned model for narrator/character_major. Use '↻ models' to see what's actually included in your plan before picking.",
  ollama: "Whatever you've pulled locally -- larger/more recent (e.g. current Llama, Qwen, or Mistral family) for narrator/character_major, a smaller quantized model for mapping/utility so it stays responsive on your hardware.",
  koboldcpp: "Whatever GGUF model you've loaded -- same sizing logic as Ollama above.",
  lmstudio: "Whatever model you've downloaded in LM Studio -- same sizing logic as Ollama above.",
  llamacpp: "Whatever GGUF model your llama.cpp server is serving -- same sizing logic as Ollama above.",
};

// The state of the stored memory vectors, shown next to the role that decides
// it. The embeddings role is the one whose change has a consequence the panel
// cannot otherwise show: everything already written stays readable but drops
// to keyword-only matching until it is re-read through the new model. Put the
// count and the button where the decision is made, rather than leaving the
// host to discover it in a story.
function embeddingBankBlock() {
  const body = el("div", { class: "small dim" }, "Checking stored memories...");
  const wrap = el("div", { style: "margin-top:10px;padding:10px 12px;"
                                + "border:1px solid var(--bd);border-radius:9px" },
    el("div", { style: "font-weight:650;margin-bottom:5px" },
       "Stored memory vectors"),
    body);

  const render = async () => {
    let data;
    try { data = await api("GET", "/api/memory/embeddings"); }
    catch (e) { body.textContent = "Could not check: " + (e?.message || e); return; }
    const mem = data.memories || {}, sums = data.memory_summaries || {};
    const stranded = (mem.stranded || 0) + (sums.stranded || 0);
    const total = (mem.total || 0) + (sums.total || 0);
    const p = data.progress || {};
    body.textContent = "";

    if (p.running) {
      body.append(el("div", {}, `Rebuilding — ${(p.done || 0).toLocaleString()} of `
                                + `${(p.total || 0).toLocaleString()} done. `
                                + `You can close this panel; it keeps going.`));
      // The panel it draws into may be gone -- the copy above says so
      // explicitly, and a rebuild on a long story runs for minutes. Re-arming
      // unconditionally kept a 1.5s poll alive against a detached node, paying
      // a server query each time to update something nobody can see. The
      // rebuild does keep going; it simply stops being watched.
      if (body.isConnected) setTimeout(render, 1500);
      return;
    }
    body.append(el("div", {},
      `Current model: ${data.model || "unknown"}`
      + (data.is_fallback ? " — the local fallback" : "")));
    if (data.is_fallback) {
      body.append(el("div", { class: "warn-note", style: "margin-top:4px" },
        "No embeddings provider is set, so memories are matched by "
        + "spelling rather than by meaning."));
    } else if (data.live_unknown) {
      // A provider IS configured and did not answer. Two very different
      // reasons, and the provider's own sentence is what separates them —
      // "Model X does not exist" is a chat model chosen for this role (the
      // most likely mistake, since the picker lists every model a provider
      // offers), while a 429 is a rate limit that will pass on its own.
      body.append(el("div", { class: "warn-note", style: "margin-top:4px" },
        data.fallback_reason
          ? "The configured embeddings model did not answer: "
            + data.fallback_reason
          : "The configured embeddings model did not answer."));
      body.append(el("div", { style: "margin-top:3px" },
        "This role needs a model that produces embeddings, not one that "
        + "writes text — a chat model will be rejected. "
        + "`openai/text-embedding-3-small` works on OpenRouter and NanoGPT. "
        + "A rate limit will clear on its own."));
    }
    body.append(el("div", { style: "margin-top:3px" },
      data.live_unknown
        ? `${total.toLocaleString()} stored.`
        : `${total.toLocaleString()} stored, ${stranded.toLocaleString()} `
          + `written by a different model.`));

    if (data.live_unknown) {
      // NOT "nothing to do". Which rows are stale is a comparison against the
      // live model, and the live model is silent — so the honest report is
      // that the question is unanswerable right now, not that the answer is
      // zero. Saying "everything is searchable by meaning" here would be the
      // same wrong claim as the old banner, pointed the other way.
      body.append(el("div", { style: "margin-top:3px" },
        "Whether anything needs rebuilding cannot be checked until the "
        + "provider answers."));
      return;
    }
    if (!stranded) {
      body.append(el("div", { style: "margin-top:3px" },
        "Everything is searchable by meaning. Nothing to do."));
      return;
    }
    body.append(el("div", { style: "margin-top:3px" },
      stranded.toLocaleString() + " can currently be found by keyword and exact "
      + "phrase only. Rebuilding re-reads them through the current model; it "
      + "runs in the background and resumes if interrupted."));
    if (data.is_fallback) {
      body.append(el("div", { style: "margin-top:5px" },
        "Set an embeddings provider above first — rebuilding onto the local "
        + "fallback would replace real vectors with a weaker one."));
      return;
    }
    body.append(el("div", { class: "row", style: "margin-top:7px" },
      el("button", {
        class: "primary",
        onclick: async (e) => {
          e.target.disabled = true;
          try {
            await api("POST", "/api/memory/embeddings/rebuild", {});
            toast("Rebuilding memory vectors in the background.", "ok");
          } catch (err) {
            toast(`Could not start: ${(err?.message || err)}`, "err");
          }
          render();
        },
      }, "Rebuild " + stranded.toLocaleString() + " now")));
  };
  render();
  return wrap;
}

function modelRecommendationsBlock() {
  return el("div", { class: "small dim", style: "margin-top:6px" },
    el("div", {}, "The rule that matters most: ", el("b", {}, "bigger/newer for narrator and character_major"), " (this is the writing you actually read), ", el("b", {}, "smaller/cheaper for mapping and utility"), " (mechanical, rarely visible). Specific model names below are current examples, not a permanent list -- providers update their lineups often."),
    ...Object.entries(MODEL_RECOMMENDATIONS).map(([kind, text]) =>
      el("div", { style: "margin-top:6px" }, el("b", {}, kind), " — ", text)));
}

// First save creates the provider row + key; the second, separate "Save
// all" at the bottom of the full role list actually assigns a model to
// anything -- easy for a first-time user to do step one, see nothing
// change, and stop there without realizing a model still isn't assigned.
// This collapses both into one button for the specific, common case of
// "I have zero providers and just want to get to Default working."
function renderFirstRunProviderSetup(b) {
  b.innerHTML = "";
  const kindSel = el("select", {}, Object.keys(S.boot.provider_presets).map(k => el("option", { value: k }, k)));
  const keyIn = el("input", { type: "password", placeholder: "API key", style: "width:100%" });
  const connectBtn = el("button", { class: "primary", style: "margin-top:10px" }, "Connect");
  const modelBox = el("div", { style: "margin-top:12px;display:none" });

  connectBtn.onclick = async () => {
    connectBtn.disabled = true;
    let prov;
    try {
      prov = await api("POST", "/api/providers", { kind: kindSel.value, api_key: keyIn.value });
    } catch (e) {
      toast(`Could not create provider: ${e.message}`, "err");
      connectBtn.disabled = false;
      return;
    }
    await boot();
    modelBox.style.display = "";
    modelBox.innerHTML = "";
    const combo = modelCombobox(S.boot.providers, prov.id, null, null);
    const useBtn = el("button", { class: "primary", style: "margin-top:10px" }, "Use this model — start writing");
    useBtn.onclick = async () => {
      const { provider, model } = combo.read();
      if (!provider || !model) { toast("Pick a model first.", "warn"); return; }
      useBtn.disabled = true;
      try {
        await api("PUT", "/api/agent_models", { default: { provider, model } });
        await boot();
        closeModal();
        renderChat();
        toast("Provider connected — you're ready to write.", "ok");
      } catch (e) {
        // Never leave the first-run button permanently disabled with no feedback.
        toast(e?.message || String(e), "err", 8000);
      } finally {
        useBtn.disabled = false;
      }
    };
    modelBox.append(
      el("div", { class: "small dim", style: "margin-bottom:4px" },
        "Connected. Pick a default model — every role falls back to this one automatically:"),
      el("div", { class: "row" }, combo.psel, combo.mwrap),
      useBtn);
  };

  b.append(
    el("div", { class: "small dim", style: "margin-bottom:10px" },
      "Connect one provider to get started. You can add more, or fine-tune a model per role, any time from this same screen."),
    el("div", { class: "ff" }, el("label", {}, "Provider"), kindSel),
    el("div", { class: "ff", style: "margin-top:8px" }, el("label", {}, "API key"), keyIn),
    el("div", { class: "small dim", style: "margin-top:4px" },
      "Local providers (LM Studio, llama.cpp) usually don't need a key — leave it blank and edit the base URL after connecting."),
    connectBtn,
    modelBox,
    el("div", { style: "margin-top:18px" },
      el("button", { onclick: () => renderFullApiSettings(b) },
        "Skip this — show full provider settings")));
}

// The size a scene backdrop wants out of a model's own list: landscape, and
// as close as possible to the 1536x1024 the engine defaults to. Biggest would
// be wrong -- these models price per size, so "largest available" quietly
// picks the most expensive option in the list.
function preferredBackdropSize(sizes) {
  const target = 1536 * 1024;
  // Separator varies by model in the same catalogue: "1536x1024" for some,
  // "1024*1024" for others. Matching only "x" silently treated every
  // asterisk model as unparseable and fell through to sizes[0] — a square,
  // which is the one shape a backdrop should never be.
  const parsed = sizes
    .map(s => { const m = /^(\d+)\s*[x*×]\s*(\d+)$/i.exec(s); return m ? { s, w: +m[1], h: +m[2] } : null; })
    .filter(d => d && d.w > d.h);
  if (parsed.length) {
    return parsed.sort((a, b) =>
      Math.abs(a.w * a.h - target) - Math.abs(b.w * b.h - target))[0].s;
  }
  return sizes.find(s => /landscape/i.test(s)) || sizes[0];
}

function renderFullApiSettings(b) {
  const am = structuredClone(S.boot.agent_models || {});
  const ds = S.boot.default_samplers;
  b.innerHTML = "";
  b.append(el("h4", {}, "Providers"));
    const provBox = el("div"); b.append(provBox);
    const renderProv = () => {
      provBox.innerHTML = "";
      for (const p of S.boot.providers) {
        const nm = el("input", { value: p.name || "", placeholder: "name", style: "width:110px" });
        const kd = el("select", {}, Object.keys(S.boot.provider_presets).map(k => el("option", { value: k, ...(k === p.kind ? { selected: "" } : {}) }, k)));
        const bu = el("input", { value: p.base_url || "", placeholder: "base url", style: "flex:1" });
        // The server never sends the stored key back (bootstrap only says
        // has_key), so an empty field here means "leave it unchanged", not
        // "clear it" -- type a new value only to replace it.
        const ak = el("input", {
          value: "",
          placeholder: p.has_key ? "•••• (key set — leave blank to keep)" : "api key",
          type: "password", style: "width:150px"
        });
        // Prompt caching, per connection. It saves on its own click rather
        // than waiting for Save: it writes different settings rows than the
        // provider fields do, and folding it into Save would mean an untouched
        // name field could overwrite a rename typed in another tab.
        const cacheBox = el("input", {
          type: "checkbox", ...(p.prompt_cache ? { checked: "" } : {}),
          ...(p.prompt_cache_locked ? { disabled: "" } : {}),
        });
        cacheBox.onchange = async () => {
          const want = cacheBox.checked;
          try {
            const r = await api("PUT", "/api/providers/" + p.id + "/prompt_cache", { enabled: want });
            // Trust the server's answer, not the click: the deny list can
            // out-rank an opt-in, so a box that reports what it asked for
            // rather than what happened would show a state that is not real.
            cacheBox.checked = !!r.prompt_cache;
            p.prompt_cache = !!r.prompt_cache;
            await boot();
            toast(`Prompt caching ${(r.prompt_cache ? "on" : "off")
              + " for " + (p.name || p.kind) + "."}`, "ok");
          } catch (e) {
            cacheBox.checked = !want;
            toast(`Could not change caching: ${e.message}`, "err");
          }
        };
        const cacheLabel = el("label", {
          class: "small",
          title: p.prompt_cache_locked
            ? "FICTION_ENGINE_PROMPT_CACHE=0 is set, which turns caching off for every provider and outranks this box."
            : (p.prompt_cache_default
              ? "This provider caches the repeated system prompt by default (~90% cheaper on a cache hit). Untick to send it in full every call."
              : "Off by default — this provider is not known to forward a cache breakpoint, and one that rejects it fails the turn instead of just not caching. Tick to opt it in."),
        }, cacheBox, " cache");
        provBox.append(el("div", { class: "card row" }, nm, kd, bu, ak, cacheLabel,
          el("button", { onclick: async () => { await api("PUT", "/api/providers/" + p.id, { name: nm.value, kind: kd.value, base_url: bu.value, api_key: ak.value }); delete S.models[p.id]; await boot(); toast("Provider saved.", "ok"); } }, "Save"),
          el("button", { onclick: async () => { if (!await confirmModal("Delete provider?", { danger: true, confirmLabel: "Delete" })) return; await api("DELETE", "/api/providers/" + p.id); await boot(); closeModal(); $("#b-api").click(); } }, "✕"),
          el("button", { title: "Fetch models", onclick: async e => { e.target.textContent = "…"; await fetchModels(p.id); e.target.textContent = "✓"; } }, "↻ models")));
      }
    };
    renderProv();
    b.append(el("div", { class: "small", style: "margin:2px 0 8px" },
      el("b", {}, "cache"), " marks the repeated system prompt so the provider can "
      + "read it back instead of reprocessing it — much cheaper per call, and it only "
      + "applies to Claude models (the caching is Anthropic's). Untick it if you suspect "
      + "caching is costing you latency rather than saving it."));
    const nk = el("select", {}, Object.keys(S.boot.provider_presets).map(k => el("option", { value: k }, k)));
    b.append(el("div", { class: "row", style: "margin:6px 0" }, nk,
      el("button", { onclick: async () => { await api("POST", "/api/providers", { kind: nk.value }); await boot(); closeModal(); $("#b-api").click(); } }, "+ Provider")));

    // Output-token ceiling. Sits with Providers rather than Agent models
    // because what it protects against is provider-side: pay-per-use
    // aggregators reserve credit against the requested maximum, and a model
    // is rejected outright when input + max_tokens exceeds its context
    // window -- so a ceiling above what a model can actually emit locks you
    // out of it and inflates the balance you need, buying nothing.
    const motBounds = S.boot.max_output_tokens_bounds
      || { default: 20000, min: 1024, max: 128000 };
    const motInput = el("input", {
      type: "number", style: "width:110px",
      min: String(motBounds.min), max: String(motBounds.max), step: "1000",
      value: String(S.boot.max_output_tokens ?? motBounds.default),
    });
    b.append(el("h4", {}, "Response limit"),
      el("div", { class: "row", style: "margin:6px 0" },
        el("span", { class: "small" }, "Max output tokens per call"),
        motInput,
        el("button", {
          onclick: async () => {
            const r = await api("PUT", "/api/max_output_tokens", { value: motInput.value });
            motInput.value = String(r.value);
            await boot();
            toast(`Response limit saved: ${r.value + " tokens."}`, "ok");
          },
        }, "Save"),
        el("button", {
          onclick: () => { motInput.value = String(motBounds.default); },
        }, "Reset to " + motBounds.default)),
      el("div", { class: "small dim" },
        "The cap on how much any single call may generate — not your context window. ",
        el("b", {}, motBounds.default + " is the recommended default"),
        " and comfortably fits every stage; the longest thing the engine writes in one call is a narrator turn, which runs well under it. A stage asking for less keeps its own smaller budget, so raising this never makes a short call expensive."),
      el("details", { style: "margin-top:6px" },
        el("summary", {}, "When should I change this?"),
        el("div", { class: "small dim", style: "margin-top:6px" },
          el("div", {}, el("b", {}, "Raise it"), " only if you're running a model with a genuinely large output window AND you're seeing replies cut off mid-sentence. Setting it above what your model can actually emit is not free: pay-per-use providers reserve credit against the number you ask for, and a model whose context can't fit your prompt plus this number is refused outright — which reads as 'that model doesn't work' when the real cause is this setting."),
          el("div", { style: "margin-top:6px" }, el("b", {}, "Lower it"), " to hard-cap what a single call can cost, or when you're on a small local model whose output limit is well under the default."),
          el("div", { style: "margin-top:6px" }, "Values outside " + motBounds.min + "–" + motBounds.max + " are pulled into range on save."))));

    // OpenRouter upstream routing. One OpenRouter model id is served by
    // several upstreams (Anthropic direct, Bedrock, Azure, Vertex, third-party
    // hosts) whose output quality AND prompt-retention policy differ -- so
    // this is a privacy control, not only a quality preference.
    if ((S.boot.providers || []).some(p => p.kind === "openrouter")) {
      const routing = structuredClone(S.boot.openrouter_routing || {});
      const orProv = S.boot.providers.find(p => p.kind === "openrouter");
      const list = v => (v || []).join(", ");

      const onlyIn = el("input", { style: "flex:1", placeholder: "e.g. anthropic, amazon-bedrock (blank = any)", value: list(routing.only) });
      const ignoreIn = el("input", { style: "flex:1", placeholder: "e.g. some-host (blank = none)", value: list(routing.ignore) });
      const denyBox = el("input", { type: "checkbox", ...(routing.data_collection === "deny" ? { checked: "" } : {}) });
      const pinBox = el("input", { type: "checkbox", ...(routing.allow_fallbacks === false ? { checked: "" } : {}) });
      const sortSel = el("select", {}, ["", "price", "throughput", "latency"].map(v =>
        el("option", { value: v, ...(routing.sort === v ? { selected: "" } : {}) }, v || "(OpenRouter default)")));

      const epBox = el("div", { class: "small dim", style: "margin-top:4px" });
      const modelIn = el("input", { style: "flex:1", placeholder: "model id, e.g. anthropic/claude-opus-4-6" });
      const loadEps = async () => {
        epBox.innerHTML = "";
        epBox.append(el("span", {}, "Loading…"));
        try {
          const r = await api("GET", "/api/openrouter/endpoints?provider_id="
            + orProv.id + "&model=" + encodeURIComponent(modelIn.value.trim()));
          epBox.innerHTML = "";
          if (!r.endpoints.length) { epBox.append(el("span", {}, "No upstreams reported for that model id.")); return; }
          for (const e of r.endpoints) {
            const risky = e.trains_on_data || e.retains_prompts;
            epBox.append(el("div", { class: "row", style: "gap:6px;align-items:center" },
              el("code", {}, e.slug),
              el("span", {}, e.name),
              el("span", { class: "badge" }, risky
                ? (e.trains_on_data ? "trains on prompts" : "retains prompts")
                : "no retention"),
              el("button", {
                onclick: () => {
                  const cur = onlyIn.value.split(/[,\s]+/).filter(Boolean);
                  if (!cur.includes(e.slug)) cur.push(e.slug);
                  onlyIn.value = cur.join(", ");
                },
              }, "allow only"),
              el("button", {
                onclick: () => {
                  const cur = ignoreIn.value.split(/[,\s]+/).filter(Boolean);
                  if (!cur.includes(e.slug)) cur.push(e.slug);
                  ignoreIn.value = cur.join(", ");
                },
              }, "blacklist")));
          }
        } catch (err) {
          epBox.innerHTML = "";
          epBox.append(el("span", {}, "Could not list upstreams: " + err.message));
        }
      };

      b.append(el("h4", {}, "OpenRouter upstream routing"),
        el("div", { class: "small dim" },
          "One OpenRouter model is served by several upstream providers — Anthropic direct, Amazon Bedrock, Azure, Google Vertex, and third-party hosts. Output quality varies between them, and so does whether they retain or train on your prompts. Leave blank to let OpenRouter choose."),
        el("div", { class: "row", style: "margin:6px 0" }, modelIn,
          el("button", { onclick: loadEps }, "List upstreams for this model")),
        epBox,
        el("div", { class: "row", style: "margin:6px 0" },
          el("span", { class: "small", style: "width:90px" }, "Allow only"), onlyIn),
        el("div", { class: "row", style: "margin:6px 0" },
          el("span", { class: "small", style: "width:90px" }, "Blacklist"), ignoreIn),
        el("div", { class: "row", style: "margin:6px 0" },
          el("label", { class: "small" }, denyBox, " Only providers that don't retain or train on prompts"),
          el("label", { class: "small" }, pinBox, " Never fall back to another upstream")),
        el("div", { class: "row", style: "margin:6px 0" },
          el("span", { class: "small", style: "width:90px" }, "Prefer by"), sortSel,
          el("button", {
            onclick: async () => {
              const split = v => v.split(/[,\s]+/).filter(Boolean);
              const r = await api("PUT", "/api/openrouter_routing", {
                only: split(onlyIn.value),
                ignore: split(ignoreIn.value),
                data_collection: denyBox.checked ? "deny" : "allow",
                allow_fallbacks: !pinBox.checked,
                sort: sortSel.value || null,
              });
              await boot();
              toast(Object.keys(r.routing).length
                ? "Upstream routing saved." : "Upstream routing cleared — OpenRouter chooses.", "ok");
            },
          }, "Save routing")),
        el("div", { class: "small dim" },
          "Pinning one upstream without 'never fall back' still lets OpenRouter route elsewhere when that upstream is busy — tick both to guarantee it."));
    }

    // Scene backdrops. Its own picker rather than a row in Agent models
    // because image generation is a different API surface entirely (a
    // separate endpoint, and on nano-gpt a separate catalogue) -- see
    // providers.image_model().
    {
      const cfg = S.boot.image_model || {};
      const sizeIn = el("input", {
        style: "width:150px", placeholder: "1536x1024", value: cfg.size || ""
      });
      // Sizes are per-model and not always WxH: plenty of these take named
      // resolutions ("landscape_16_9", "square_hd") instead. Offering the
      // model's own list is the difference between a picker and a trap --
      // a mismatched size only fails later, at generation time.
      const showSizesFor = ({ provider, model }) => {
        const row = (S.imageModels[provider] || []).find(m => m.id === model);
        const sizes = (row && row.sizes) || [];
        if (!sizes.length) { sizeIn.placeholder = "1536x1024"; return; }
        sizeIn.placeholder = sizes.slice(0, 3).join(" · ");
        if (!sizes.includes(sizeIn.value.trim())) {
          sizeIn.value = preferredBackdropSize(sizes);
        }
      };
      const imgCombo = modelCombobox(S.boot.providers, cfg.provider ?? null,
        cfg.model ?? null, showSizesFor,
        { fetch: fetchImageModels, cache: S.imageModels });
      const enableBox = el("input", {
        type: "checkbox", ...(S.boot.backdrops_enabled ? { checked: "" } : {})
      });
      const continuityBox = el("input", {
        type: "checkbox", ...(S.boot.backdrop_continuity ? { checked: "" } : {})
      });
      b.append(el("h4", {}, "Scene backdrops"),
        el("div", { class: "small dim" },
          "Paints a generated image of the room behind the story. The picture is built from the room's spatial description only — never from who is standing in it — so no character ever appears in one. Each distinct room is generated once and cached, so revisiting a place is free."),
        el("div", { class: "row", style: "margin:6px 0" },
          imgCombo.psel, imgCombo.mwrap, sizeIn,
          el("button", {
            onclick: async () => {
              const picked = imgCombo.read();
              await api("PUT", "/api/image_model", { ...picked, size: sizeIn.value.trim() });
              await api("PUT", "/api/backdrops", { enabled: enableBox.checked,
                                                  continuity: continuityBox.checked });
              await boot();
              toast(picked.provider && picked.model
                ? "Backdrop image model saved." : "Backdrop image model cleared.", "ok");
            },
          }, "Save")),
        el("div", { class: "row", style: "margin:6px 0" },
          el("label", { class: "small" }, enableBox,
            " Generate backdrops for new rooms (costs one image per room)")),
        el("div", { class: "row", style: "margin:6px 0" },
          el("label", { class: "small" }, continuityBox,
            " Keep rooms consistent by revising the room's first image")),
        el("div", { class: "small dim" },
          "With this on, a room's later pictures — lights out, rain, mud, wreckage — are "
          + "edits of the FIRST image of that room rather than fresh generations, so the "
          + "architecture, furniture and camera angle stay put instead of being reinvented "
          + "each time. It needs a provider whose image endpoint accepts an input image; "
          + "if a request is refused the picture is generated normally instead, so the "
          + "worst case is what you have today. Off by default because the quality of an "
          + "edit depends entirely on the model, and it is worth seeing one before "
          + "trusting it with every room."),
        el("div", { class: "small dim" },
          "With this off, backdrops already generated still show — they're free — but no new ones are commissioned. Picking a model fills in a size it actually supports (they differ, and some take names like “landscape_16_9” rather than pixels); landscape is preferred because the picture sits behind a centred column in a browser window. Edit-only models are left out of the list — a backdrop is generated from text alone."));
    }

    // How a body's feeling settles. It lives HERE, beside the character
    // models it governs, for the same reason the Director's orchestration
    // toggle sits beside its specialist roles: a switch a host cannot find
    // next to the thing it changes is a switch that becomes folklore. This
    // one was live in a real story with no visible off.
    {
      const habitBox = el("input", {
        type: "checkbox",
        ...(S.boot.affect_habituation ? { checked: "" } : {})
      });
      habitBox.onchange = async () => {
        await api("PUT", "/api/affect_habituation",
                  { enabled: habitBox.checked });
        await boot();
        toast(habitBox.checked
          ? "A held peak will wear off, so a new one can land."
          : "Feeling will hold wherever the beat puts it.", "ok");
      };
      b.append(el("h4", {}, "How feeling settles"),
        el("div", { class: "small dim" },
          "Off, a mood sits wherever the beat puts it and drifts home slowly "
          + "when nothing reinforces it. On, sustained maximum feeling costs "
          + "sensitivity the way a real body's does: a long plateau sags a "
          + "little, so a genuine peak has somewhere to rise to. Measured on "
          + "a played story, a character held the top of the scale for "
          + "seventeen turns and the climax it was building to scored lower "
          + "than the plateau before it."),
        el("div", { class: "row", style: "margin:6px 0" },
          el("label", { class: "small" }, habitBox,
            " Let a held peak wear off")),
        el("div", { class: "small dim" },
          "Sensitivity builds from nothing, so switching this on part-way "
          + "through a story takes a few beats to show and will not reach "
          + "back over a plateau already behind you."));
    }

    // What a card authors beneath each clothing region. Its own small block
    // rather than a line inside another one: it governs explicit body
    // description, and a host looking for it should find it by looking.
    {
      const beneathBox = el("input", {
        type: "checkbox", ...(S.boot.attire_beneath ? { checked: "" } : {})
      });
      beneathBox.onchange = async () => {
        await api("PUT", "/api/attire_beneath", { enabled: beneathBox.checked });
        await boot();
        toast(beneathBox.checked
          ? "Underneath descriptions will be used."
          : "Underneath descriptions will be left out.", "ok");
      };
      b.append(el("h4", {}, "Clothing and the body"),
        el("div", { class: "small dim" },
          "Clothes are tracked by body region — head, torso, arms, hands, waist, "
          + "legs, feet — and come off a step at a time rather than all at once: "
          + "worn, loosened, open, off. A garment that leaves someone becomes a "
          + "real object in the room. Character and persona cards can also "
          + "describe what each region shows once nothing covers it."),
        el("div", { class: "row", style: "margin:6px 0" },
          el("label", { class: "small" }, beneathBox,
            " Use the “underneath” descriptions authored on cards")),
        el("div", { class: "small dim" },
          "Off by default. With it off a card's underneath text is left out of "
          + "every prompt — an uncovered region is still reported as uncovered, "
          + "because that is a fact about the scene, and the character's own "
          + "appearance supplies the rest."));
    }

    // Whether a story may acquire cast on its own. It lives here because the
    // per-story "turns till auto-promotion" dial in the Dialogue panel has
    // always told the host that promotion "also has to be switched on
    // globally in ⚙ API" -- and there was no such control anywhere in the
    // browser, so the sentence named a switch that did not exist.
    {
      const promoteBox = el("input", {
        type: "checkbox", ...(S.boot.auto_promote ? { checked: "" } : {})
      });
      promoteBox.onchange = async () => {
        await api("PUT", "/api/auto_promote", { enabled: promoteBox.checked });
        await boot();
        toast(promoteBox.checked
          ? "Stories may promote an extra into a full character on their own."
          : "Extras will only become characters when you promote them.", "ok");
      };
      b.append(el("h4", {}, "Acquiring cast"),
        el("div", { class: "small dim" },
          "Off by default, and deliberately: promoting an extra is not a small "
          + "event. It writes a character sheet with a model call, attaches a "
          + "permanent cast member, seeds mutual recognition with everyone "
          + "present, and starts keeping that mind's psychology every beat. "
          + "With this off you can still promote anyone by hand from the Cast "
          + "panel."),
        el("div", { class: "row", style: "margin:6px 0" },
          el("label", { class: "small" }, promoteBox,
            " Let a story promote an extra on its own")),
        el("div", { class: "small dim" },
          "This is the global permission. Each story also sets how many turns "
          + "of deliberate interaction it takes, under 💬 Dialogue — 0 there "
          + "means never, whatever this switch says."));
    }

    // Room ambience. Not an agent-model row for the same reason backdrops is
    // not: the thing being configured is a SOURCE of media (a folder, or a
    // sound library's API), not a chat model. The optional `ambience_prompt`
    // role that writes the search query does live in Agent models below.
    {
      const cfg = S.boot.ambience || {};
      const sourceSel = el("select", {},
        el("option", { value: "local", ...(cfg.source === "local" ? { selected: "" } : {}) }, "local folder"),
        el("option", { value: "freesound", ...(cfg.source === "freesound" ? { selected: "" } : {}) }, "Freesound"));
      const libIn = el("input", { style: "flex:1", placeholder: "/path/to/your/ambience/folder",
                                  value: cfg.library || "" });
      const keyIn = el("input", {
        type: "password", style: "width:190px",
        placeholder: cfg.has_key ? "•••• (key set — blank keeps it)" : "Freesound API key",
      });
      const enableBox = el("input", { type: "checkbox", ...(cfg.enabled ? { checked: "" } : {}) });
      const ncBox = el("input", {
        type: "checkbox",
        ...((cfg.licenses || []).includes("Attribution NonCommercial") ? { checked: "" } : {}),
      });
      b.append(el("h4", {}, "Room ambience"),
        el("div", { class: "small dim" },
          "Plays a looping sound bed for the room the player is standing in, chosen from the room's spatial description only — never from who is in it. It follows the room, the hour, the weather and any damage, and each distinct state is fetched once and cached. Mute, volume and reroll live beside the input box."),
        el("div", { class: "row", style: "margin:6px 0" }, sourceSel, libIn, keyIn,
          el("button", {
            onclick: async () => {
              const licenses = ["Creative Commons 0", "Attribution"];
              if (ncBox.checked) licenses.push("Attribution NonCommercial");
              await api("PUT", "/api/ambience", {
                enabled: enableBox.checked,
                source: sourceSel.value,
                library: libIn.value.trim(),
                freesound_key: keyIn.value.trim(),
                licenses,
              });
              await boot();
              if (typeof syncAmbience === "function") syncAmbience();
              toast("Ambience settings saved.", "ok");
            },
          }, "Save")),
        el("div", { class: "row", style: "margin:6px 0" },
          el("label", { class: "small" }, enableBox, " Play ambience"),
          el("label", { class: "small", style: "margin-left:14px" }, ncBox,
            " Also allow NonCommercial-licensed sounds")),
        el("div", { class: "small dim" },
          "A local folder is searched by filename — name files for what they sound like (“rain_on_tin_roof.ogg”), or drop an index.json beside them mapping a file to extra words. Freesound needs a free API key from freesound.org/apiv2/apply; it fetches CC0 and Attribution sounds by default, and whatever is playing is credited in the 🎧 panel."));
    }

    // Fan-out concurrency, switched where the specialists are configured.
    // The fan-out itself is not a choice and has no switch -- it is the
    // only Director path. Whether its specialists run AT ONCE is a choice,
    // because concurrency is not free everywhere.
    {
      const parBox = el("input", {
        type: "checkbox",
        ...(S.boot.director_fanout_parallel !== false ? { checked: "" } : {})
      });
      parBox.onchange = async () => {
        await api("PUT", "/api/director_fanout_mode",
                  { parallel: parBox.checked });
        await boot();
        toast(parBox.checked
          ? "The Director's specialists will run at once."
          : "The Director's specialists will run one at a time.", "ok");
      };
      b.append(el("h4", {}, "Director specialists"),
        el("div", { class: "small dim" },
          "The Director works as a writer plus specialists: one call writes "
          + "the beat's account, and the six roles below encode only the "
          + "kinds of change the beat actually contains — a scene with no "
          + "clothing change never loads the clothing rules at all. Most "
          + "beats need about two of the six."),
        el("div", { class: "small dim", style: "margin-top:4px" },
          "They are handed separate parts of the same finished beat and have "
          + "nothing to say to each other, so by default they run at once and "
          + "the beat costs its slowest one rather than all of them added up. "
          + "Turn this off if your provider takes one request at a time — a "
          + "key limited by concurrent connections, or a local runtime "
          + "serving one model on one GPU. Everything else is identical: the "
          + "same specialists, the same scopes, the same order."),
        el("label", { class: "row", style: "margin-top:6px" },
          parBox, el("span", {}, "Run the specialists at the same time")));
    }

    // The narrator's voice anchor. `agents/narration.py` has always read
    // `settings.exemplars` and the narrator prompt has always carried a STYLE
    // EXEMPLARS clause -- and there was no way to put anything in it, so the
    // clause referred to an empty list on every install that has ever run.
    // Placed directly above the narrator's own model picker, because those
    // are the two controls that decide how the prose reads.
    {
      const bounds = S.boot.exemplar_bounds || {};
      const maxCount = bounds.max_count || 5;
      const maxChars = bounds.max_chars || 2000;
      const areas = [];
      const rows = el("div", {});
      const addRow = text => {
        if (areas.length >= maxCount) return;
        const ta = el("textarea", {
          style: "width:100%", rows: "4", maxlength: String(maxChars),
          placeholder: "A short passage at the quality you want — anyone's "
            + "prose, or your own. Style only.",
        }, text || "");
        areas.push(ta);
        rows.append(el("div", { class: "card", style: "margin-top:6px" }, ta));
      };
      (S.boot.exemplars || []).forEach(addRow);
      if (!areas.length) addRow("");
      b.append(el("h4", {}, "Narrator voice"),
        // One string rather than three around the two numbers: a sentence
        // split at an interpolation reaches the UI catalog as fragments no
        // translator can put back together in another word order.
        el("div", { class: "small dim" },
          `Up to ${maxCount} short passages the narrator studies for voice, `
          + `rhythm and restraint. This is the one part of a turn the narrator `
          + `is told to IMITATE, so keep them to style: a passage that names `
          + `people, places or events will be read as facts about your story. `
          + `Each is capped at ${maxChars} characters, because every passage `
          + `rides every narrator call for the life of the install.`),
        rows,
        el("div", { class: "row", style: "margin-top:6px" },
          el("button", {
            onclick: () => {
              if (areas.length >= maxCount) {
                return toast(`That is the limit — ${maxCount} passages.`, "warn");
              }
              addRow("");
            },
          }, "Add a passage"),
          el("button", { class: "primary", onclick: async () => {
            const r = await api("PUT", "/api/exemplars",
                                { exemplars: areas.map(ta => ta.value) });
            await boot();
            toast(r.count
              ? `${r.count} passage(s) saved — the narrator will study them.`
              : "Cleared. The narrator writes from the prompt alone.", "ok");
          } }, "Save passages")));
    }

    b.append(el("h4", {}, "Agent models"),
      el("div", { class: "small dim" },
        "Type to search the provider's model list. Open 'advanced' for samplers and backup models."),
      el("details", { style: "margin-top:6px" },
        el("summary", {}, "What do these roles do?"),
        el("div", { class: "small dim", style: "margin-top:6px" },
          el("div", {}, el("b", {}, "Setting only Default is enough to start playing"), " — every other role falls back to it automatically, with one exception: embeddings, which needs a model of a different KIND and so is never inherited. The rest let you assign a faster or cheaper model to a specific stage of each turn without touching quality where it matters most."),
          el("div", { style: "margin-top:8px" }, el("b", {}, "director"), " — reads what you typed and decides what actually happens: whether an action succeeds, what an NPC's action resolves to. Gets this wrong and the story stops making sense, so keep it on a strong model."),
          el("div", {}, el("b", {}, "director_body / _social / _contact / _objects / _spatial / _offscreen"), " — scoped specialists that encode bodies (clothing, wounds, vitals, overlays), the scene roster, physical contact and matter, the object world, the room graph and positions, and the world's traffic (crowds, couriers, hearsay) from the beat the Director authored. An exception to the Default fallback: left unset each follows the ", el("b", {}, "director"), " model, so the engine's most failure-prone stage never silently downgrades."),
          el("div", { class: "small dim" }, "There is no ", el("b", {}, "perception"), " role any more, and that is not an omission: what each character can see, hear and know is now worked out in code rather than asked of a model, so it costs nothing, cannot be got wrong by a cheap model, and has no setting to tune."),
          el("div", {}, el("b", {}, "character_bg / character_mid / character_major"), " — generate what a character does and says, tiered by how central that character is to the scene. Quality shows up directly in dialogue, so keep major characters on a strong model even if you lighten background ones."),
          el("div", {}, el("b", {}, "narrator"), " — turns everything into the prose you actually read. This is the model whose writing style you'll notice most."),
          el("div", {}, el("b", {}, "mapping"), " — keeps track of world facts, lore, and location layout in the background. Rarely visible directly, safe to experiment with."),
          el("div", {}, el("b", {}, "repair"), " — shape, never content. When a stage's output fails validation, this model is asked about the failed fields ALONE and its answer is spliced back at exactly those paths; everything else is byte-identical, so it cannot touch the beat. Its whole job is \u201cthis fragment is the wrong shape, fix the shape, keep every fact\u201d, which a fast cheap model does well \u2014 and every success here saves a full re-author of the response on the stage's own model (measured: 4.2s on the Director for one malformed field, 36.3s on a character decision review). Left unset it follows ", el("b", {}, "utility"), ".") ,
          el("div", {}, el("b", {}, "utility"), " — background helper tasks: the autobiographical memory summaries written between turns, notice wording, off-screen activity sketches, importer fills. Never player-facing prose, so speed matters more than polish — not worth spending a premium model on. The other exception to the Default fallback: left unset it follows the ", el("b", {}, "mapping"), " model, so background summarisation lands on the fast mechanical model you already picked rather than on your most expensive one."),
          el("div", { style: "margin-top:8px" }, el("b", {}, "embeddings"), " — turns each memory into a vector so a character can recall something relevant that was worded differently 300 turns ago. Cheap per call and it is what makes memory work by MEANING rather than by keyword; leave it unset and the engine falls back to a local hash that only matches shared words."),
          el("div", { class: "warn-note", style: "margin-top:4px" }, el("b", {}, "Changing this one has a consequence the others do not."), " A memory can only be compared against a vector from the same model, so everything already stored has to be re-read through the new one. Nothing is lost and nothing breaks — until it is rebuilt, older memories are found by keyword only. The engine offers to rebuild when you next open a story, or use the button below."))),
      el("details", { style: "margin-top:6px" },
        el("summary", {}, "Which model should I pick?"),
        modelRecommendationsBlock()),
      embeddingBankBlock());

    const roleInputs = {};
    const roleMeta = {};
    const embedWas = { provider: (am.embeddings || {}).provider ?? null,
                       model: (am.embeddings || {}).model ?? null };
    let embedWarned = false;
    let defaultValues = {
      provider: (am.default || {}).provider ?? null,
      model: (am.default || {}).model ?? null,
    };

    // Any role with no saved provider/model "follows" Default: it mirrors
    // whatever Default is set to (both live in this modal and dynamically
    // at inference time, since an absent role config already falls back to
    // "default" on every request). The moment a role's own picker is
    // edited directly, it's pinned and stops following.
    function propagateToFollowers(provider, model) {
      defaultValues = { provider, model };
      // Every RENDERED row, not S.boot.roles: extension lanes follow Default
      // exactly as host roles do, and iterating the host list alone would
      // leave a following lane row displaying a stale Default.
      for (const role of Object.keys(roleMeta)) {
        const meta = roleMeta[role];
        if (meta && meta.following) meta.rebuild(provider, model);
      }
    }

    // `embeddings` first, then Default, then the rest. It is the one role
    // whose wrong setting is INVISIBLE -- a chat model here is rejected by the
    // provider, the engine silently falls back to the local hash, and play
    // continues looking fine while memory quietly stops working by meaning.
    // Everything else announces itself in the prose.
    // `embeddings` first, then Default, then the Director and — DIRECTLY
    // BENEATH IT — its six specialists, which are the roles whose meaning
    // depends on it: each is inert unless the orchestrated Director is on,
    // and each falls back to the `director` model rather than to Default.
    // Sorting them next to the stage they serve is the difference between a
    // list of seventeen roles and a list that explains itself.
    const ROLE_ORDER = {
      embeddings: -2, default: -1, director: 0,
      director_body: 1, director_social: 2, director_contact: 3,
      director_objects: 4, director_spatial: 5, director_offscreen: 6,
      repair: 7,
    };
    const orderedRoles = [...S.boot.roles].sort(
      (a, b) => (ROLE_ORDER[a] ?? 50) - (ROLE_ORDER[b] ?? 50)
    );

    // Extension-declared model lanes (`api.add_model_lane`), rendered LAST,
    // after every host role: they are guests in this panel, and their roles
    // are namespaced (`ext:<id>:<name>`) so none can collide with a host
    // row. Each gets the full generic row -- follow-Default, samplers,
    // backups, reasoning effort -- because a lane IS a role to everything
    // downstream; only the label differs, since `ext:directive:planner`
    // names a storage key, not a thing a host recognises. The list comes
    // from the bootstrap (extension_runtime.registered_model_lanes), which
    // empties with the extension's registration, so a disabled or removed
    // extension leaves no phantom row here.
    const laneByRole = {};
    for (const lane of S.boot.extension_lanes || []) {
      laneByRole[lane.role] = lane;
      orderedRoles.push(lane.role);
    }

    // Embedding models have to be OFFERED, not filtered for: a provider's
    // /models catalogue lists what it will CHAT with, and embedding models are
    // not in it. Measured against both configured providers -- 652 and 336
    // models respectively, zero embedding entries between them. So filtering
    // the catalogue produced an empty dropdown, which is how someone ends up
    // typing a chat model into this field.
    //
    // Every id below was verified live against both an OpenRouter and a
    // NanoGPT key; the dimension is shown because it decides how much a
    // rebuild costs and how big every stored vector becomes.
    // Ordered by a measured benchmark, not by size or price: 16
    // vocabulary-disjoint paraphrase queries against a real 441-memory story,
    // scoring where the correct memory ranked among all 441. Size buys
    // nothing here -- the two 4096d models finished 7th and last.
    //
    // Split BY PROVIDER because ids are not portable: OpenRouter namespaces
    // them (`openai/...`, `perplexity/...`) and is the only one carrying
    // Perplexity's models; NanoGPT wants the bare form. Every id below
    // returned a real vector from that provider when it was added.
    const EMBED_BY_KIND = {
      openrouter: [
        { id: "perplexity/pplx-embed-v1-4b", note: "2560d · best consistency (16/16 top-20) · fastest rebuild" },
        { id: "perplexity/pplx-embed-v1-0.6b", note: "1024d · best value · 40MB · ~4min rebuild" },
        { id: "openai/text-embedding-3-small", note: "1536d · best top-1 · 61MB" },
        { id: "openai/text-embedding-3-large", note: "3072d · strong · 121MB" },
        { id: "qwen/qwen3-embedding-8b", note: "4096d · good, slow, 161MB" },
        { id: "thenlper/gte-large", note: "1024d · older, mid-table" },
        { id: "intfloat/e5-large-v2", note: "1024d · older, mid-table" },
      ],
      nanogpt: [
        { id: "text-embedding-3-small", note: "1536d · best top-1 · 61MB" },
        { id: "jina-embeddings-v4", note: "2048d · 2nd overall · 81MB" },
        { id: "text-embedding-3-large", note: "3072d · strong · 121MB" },
        { id: "gemini-embedding-001", note: "3072d · strong · 121MB" },
        { id: "qwen/qwen3-embedding-8b", note: "4096d · good, slow, 161MB" },
        { id: "baai/bge-large-en-v1.5", note: "1024d · open weights · 40MB" },
        { id: "baai/bge-base-en-v1.5", note: "768d · smallest · 30MB" },
      ],
    };
    // Anything else (a local Ollama, an OpenAI-compatible endpoint) gets the
    // unprefixed ids, which is the shape those serve.
    const EMBED_FALLBACK = [
      { id: "text-embedding-3-small", note: "1536d · widely available" },
      { id: "nomic-embed-text", note: "768d · common on local Ollama" },
      { id: "mxbai-embed-large", note: "1024d · common on local Ollama" },
      { id: "bge-m3", note: "1024d · open weights" },
    ];
    const embedSuggestions = prov =>
      (prov && EMBED_BY_KIND[prov.kind]) || EMBED_FALLBACK;

    // A catalogue entry that DOES look like an embedding model is still worth
    // offering (a local Ollama provider lists nomic-embed-text properly).
    const EMBED_MODEL = /embed|^text-embedding|bge[-_]|gte[-_]|e5[-_]|voyage|nomic|mxbai|jina/i;

    for (const role of orderedRoles) {
      const cfg = am[role] || {};
      const isDefault = role === "default";
      // `embeddings` may NEVER follow Default. Default is a chat model, and a
      // chat model cannot produce an embedding -- the provider rejects it and
      // the engine degrades to the local hash without a word. Following was
      // not a convenience here, it was a guaranteed wrong answer.
      const isEmbeddings = role === "embeddings";
      const following = !isDefault && !isEmbeddings && !(cfg.provider && cfg.model);
      const meta = { following, rebuild: null };
      roleMeta[role] = meta;

      const samp = {};

      const advanced = el(
        "details",
        {},
        el("summary", {}, "advanced sampling"),
        el(
          "div",
          { class: "row" },
          ...S.boot.sampler_keys.map(key => {
            const defaultValue = ds[key];
            const currentValue = (
              cfg[key] !== undefined
                ? cfg[key]
                : defaultValue
            );

            const input = el("input", {
              type: "number",
              step: "any",
              style: "width:95px",
              placeholder: key,
              value: currentValue
            });

            samp[key] = input;

            return el(
              "label",
              { class: "tgl" },
              key,
              input
            );
          })
        )
      );

      const fallbackBox = el("div");
      const fallbackRows = [];

      const addFallback = fallback => {
        const picker = modelCombobox(
          S.boot.providers,
          fallback?.provider,
          fallback?.model
        );

        const row = el(
          "div",
          {
            class: "card row",
            style: "margin-left:24px"
          },
          el(
            "span",
            {
              class: "small dim",
              style: "width:84px"
            },
            `Backup ${fallbackRows.length + 1}`
          ),
          picker.psel,
          picker.mwrap,
          el(
            "button",
            {
              class: "danger",
              title: "Remove backup model",
              onclick: () => {
                row.remove();
                const index = fallbackRows.indexOf(row);

                if (index >= 0) {
                  fallbackRows.splice(index, 1);
                }
              }
            },
            "✕"
          )
        );

        row._picker = picker;
        fallbackRows.push(row);
        fallbackBox.append(row);
      };

      for (const fallback of cfg.fallbacks || []) {
        addFallback(fallback);
      }

      const fallbackControls = el(
        "details",
        {},
        el("summary", {}, "backup models"),
        el(
          "div",
          {
            class: "small dim",
            style: "margin:6px 0"
          },
          "Backups are tried in order after retryable API failures, "
            + "degenerate output, or failed JSON repair."
        ),
        fallbackBox,
        el(
          "button",
          {
            onclick: () => addFallback({})
          },
          "+ Backup model"
        )
      );

      roleInputs[role] = { primary: null, samp, fallbackRows };

      const primaryContainer = el(
        "span",
        { class: "row", style: "flex:1;align-items:center" }
      );

      const followChk = (isDefault || isEmbeddings) ? null : el("input", {
        type: "checkbox",
        title: "Keep this role in sync with Default until you edit it directly",
        ...(following ? { checked: "" } : {}),
      });

      // Reasoning effort for this role, sitting with its model. "(follow
      // default)" (empty) means it inherits the Default role's effort exactly
      // as the model does; "(model default)" on Default means send nothing.
      const effLevels = S.boot.reasoning_effort_levels || ["off", "minimal", "low", "medium", "high"];
      const effMap = S.boot.reasoning_effort || {};
      const effortSel = el("select", { style: "min-width:118px", title: "Reasoning effort" },
        [el("option", { value: "" }, isDefault ? "reasoning: default" : "reasoning: follow default")]
          .concat(effLevels.map(l => el("option",
            { value: l, ...(effMap[role] === l ? { selected: "" } : {}) }, "reasoning: " + l))));
      roleInputs[role] = roleInputs[role] || {};
      roleInputs[role].effort = effortSel;

      const rebuildPrimary = (provider, model) => {
        primaryContainer.innerHTML = "";
        const combo = modelCombobox(
          S.boot.providers, provider, model,
          ({ provider: p, model: m }) => {
            if (isDefault) {
              propagateToFollowers(p, m);
            } else {
              // user edited this role's own picker directly: pin it
              meta.following = false;
              if (followChk) followChk.checked = false;
            }
            // Said ONCE per panel, on the first edit rather than per
            // keystroke: changing this model orphans every vector already
            // stored, and that consequence is not visible from the control.
            if (isEmbeddings && !embedWarned
                && (String(p) !== String(embedWas.provider)
                    || String(m || "") !== String(embedWas.model || ""))) {
              embedWarned = true;
              toast(`Changing the embeddings model means every memory already ${"stored has to be re-read through it — until then those "
                  + "memories are found by keyword only. Save, and the engine "
                  + "will offer to rebuild."}`, "warn", 11000);
            }
          },
          isEmbeddings ? {
            suggest: x => EMBED_MODEL.test(x.id),
            extra: embedSuggestions,
            suggestNote: "This role needs a model that returns vectors, not "
                       + "one that writes text — providers do not list these "
                       + "in their chat catalogue, so known-good ids are "
                       + "offered here.",
          } : undefined
        );
        primaryContainer.append(combo.psel, combo.mwrap);
        roleInputs[role].primary = combo;
      };
      meta.rebuild = rebuildPrimary;

      rebuildPrimary(
        isDefault || !following ? cfg.provider : defaultValues.provider,
        isDefault || !following ? cfg.model : defaultValues.model
      );

      if (followChk) {
        followChk.onchange = () => {
          meta.following = followChk.checked;
          if (followChk.checked) {
            rebuildPrimary(defaultValues.provider, defaultValues.model);
          }
        };
      }

      const lane = laneByRole[role];
      b.append(el(
        "div",
        { class: "card" },
        // A lane row says whose it is and what it is for; the raw namespaced
        // role only appears as the tooltip, because it is a storage key.
        lane
          ? el("div", { class: "small dim" },
               `🧩 ${lane.ext_id}${lane.description ? " — " + lane.description : ""}`)
          : null,
        el(
          "div",
          { class: "row" },
          el(
            "b",
            { style: "width:130px", ...(lane ? { title: role } : {}) },
            lane ? lane.label : role
          ),
          followChk
            ? el(
                "label",
                { class: "tgl small dim", style: "margin-right:8px;white-space:nowrap" },
                followChk,
                // Reads the inheritance from the bootstrap rather than
                // hardcoding the parent's name, so the label cannot drift
                // from `providers.ROLE_FALLBACKS`. That map is empty today,
                // so every row truthfully renders default as its parent; it
                // was not empty once, and the label lied on the eight rows
                // a host is most likely to leave blank deliberately.
                "follow " + ((S.boot.role_fallbacks || {})[role] || "default")
              )
            : null,
          primaryContainer,
          effortSel
        ),
        advanced,
        fallbackControls
      ));
    }

    b.append(el("div", { class: "row", style: "margin-top:8px" },
      el("button", { class: "primary", onclick: async () => {
        const out = {};

        for (const [role, entry] of Object.entries(
          roleInputs
        )) {
          if (roleMeta[role] && roleMeta[role].following) {
            // Leave unset so it keeps dynamically deferring to Default,
            // rather than pinning today's snapshot of Default's value.
            continue;
          }

          const {
            provider,
            model
          } = entry.primary.read();

          if (!provider || !model) {
            continue;
          }

          const roleConfig = {
            provider,
            model
          };

          for (const [key, input] of Object.entries(
            entry.samp
          )) {
            if (input.value === "") {
              continue;
            }

            const value = Number(input.value);

            if (value !== ds[key]) {
              roleConfig[key] = value;
            }
          }

          const fallbacks = [];

          for (const row of entry.fallbackRows) {
            if (!row.isConnected) {
              continue;
            }

            const fallback = row._picker.read();

            if (
              fallback.provider
              && fallback.model
            ) {
              fallbacks.push(fallback);
            }
          }

          if (fallbacks.length) {
            roleConfig.fallbacks = fallbacks;
          }

          out[role] = roleConfig;
        }

        // Per-role reasoning effort travels with the models: a role whose
        // effort select is left blank (follow-default / model-default) is
        // simply omitted, so the backend's role->default->unset fallback
        // applies, exactly like the model's follow-default.
        const efforts = {};
        for (const [role, entry] of Object.entries(roleInputs)) {
          const v = entry.effort ? entry.effort.value : "";
          if (v) efforts[role] = v;
        }

        await api("PUT", "/api/agent_models", out);
        await api("PUT", "/api/reasoning_effort", { efforts });
        await boot();
        closeModal();
        toast("Agent models saved.", "ok");
      } }, "Save all")));

  // Signing out. The host cookie lasts thirty days and is SameSite=Strict,
  // `POST /api/auth/logout` has always destroyed the session row and cleared
  // the cookie -- and no page in the app offered it, so the only way off a
  // shared or borrowed machine was to clear cookies by hand. It lives at the
  // foot of this panel because this is where the host's own account settings
  // are, and because it is not a control anyone should hit by accident.
  b.append(el("h4", { style: "margin-top:18px" }, "Host sign-in"),
    el("div", { class: "small dim" },
      "Your sign-in lasts thirty days on this browser. Signing out ends it "
      + "everywhere it was issued and returns you to the sign-in page. Guest "
      + "invites are separate and are not affected."),
    el("div", { class: "row", style: "margin-top:6px" },
      el("button", {
        onclick: async () => {
          if (!await confirmModal("Sign out of this host session?",
                                  { confirmLabel: "Sign out" })) return;
          await api("POST", "/api/auth/logout", {});
          window.location.href = "/login";
        },
      }, "Sign out")));
}

$("#b-api").onclick = () => {
  modal("API connections", b => {
    if (!S.boot.providers.length) {
      renderFirstRunProviderSetup(b);
    } else {
      renderFullApiSettings(b);
    }
  });
};

// ---- Software updates (host-only; git fast-forward from GitHub origin) ----
$("#b-update").onclick = () => {
  modal("Software updates", b => renderUpdateChecking(b));
};

function renderUpdateChecking(b) {
  const ownsModal = modalOwnership(b);
  b.innerHTML = "";
  b.append(el("div", { class: "row" },
    el("span", { class: "spinner" }),
    el("span", { class: "dim" }, "Checking GitHub for updates…")));
  api("GET", "/api/updates/check")
    .then(r => {
      if (!ownsModal()) return;
      renderUpdateStatus(b, r);
    })
    .catch(e => {
      if (!ownsModal()) return;
      renderUpdateError(b, e?.message || "Update check failed.");
    });
}

function renderUpdateError(b, message, retry = renderUpdateChecking) {
  b.innerHTML = "";
  b.append(el("div", { class: "card", style: "border-color:var(--danger,#c0392b)" },
    el("b", {}, "Couldn't check for updates"),
    el("div", { class: "dim", style: "margin-top:6px;white-space:pre-wrap" }, message)));
  b.append(el("div", { class: "row", style: "margin-top:10px" },
    el("button", { onclick: () => retry(b) }, "Try again"),
    el("button", { onclick: closeModal }, "Close")));
}

// ---- Legacy checkpoint conversion (host-only maintenance) ----------------
//
// Sits in the Software updates modal because that is where a host looks after
// pulling a version whose storage format changed. Checkpoints used to carry
// every memory's embedding vectors inline, and since a checkpoint is a full
// snapshot of the bank, the same vector was re-stored on every turn: measured
// on a real database, checkpoints were 94.5% of a 4.4 GB file and the vectors
// were 96.9% of each one. Converting moves each vector into a
// content-addressed store the checkpoints reference.
//
// Never automatic. It rewrites rollback history, so the host asks for it.
function checkpointCompactionBlock() {
  const body = el("div", { class: "small dim" }, "Checking checkpoint storage…");
  const wrap = el("div", { style: "margin-top:14px;padding:10px 12px;"
                                + "border:1px solid var(--bd);border-radius:9px" },
    el("div", { style: "font-weight:650;margin-bottom:5px" },
       "Convert legacy checkpoints to the leaner format"),
    body);

  const mb = n => (Number(n || 0) / 1e6).toFixed(1) + " MB";
  let timer = null;

  const render = async () => {
    let d;
    try { d = await api("GET", "/api/maintenance/checkpoints"); }
    catch (e) {
      body.textContent = "Could not check: " + (e?.message || e);
      return;
    }
    const p = d.progress || {};
    body.textContent = "";

    if (p.running) {
      const total = p.total || 0, done = p.done || 0;
      const pct = total ? Math.min(100, Math.round((done / total) * 100)) : 0;
      body.append(el("div", {}, `Converting — ${done.toLocaleString()} of `
                              + `${total.toLocaleString()} checkpoints (${pct}%)`));
      // A determinate bar: the total is known before the run starts, so a
      // spinner would be hiding information the host already paid for.
      body.append(el("div", {
        style: "margin-top:7px;height:8px;border-radius:5px;overflow:hidden;"
             + "background:var(--bd)" },
        el("div", { style: `height:100%;width:${pct}%;background:var(--ac,#4a90d9);`
                         + "transition:width .3s ease" })));
      if (p.bytes_before) {
        body.append(el("div", { class: "small dim", style: "margin-top:6px" },
          `${mb(p.bytes_before)} → ${mb(p.bytes_after)} so far`));
      }
      if (!timer) timer = setInterval(render, 1000);
      return;
    }

    if (timer) { clearInterval(timer); timer = null; }

    if (p.error) {
      body.append(el("div", { style: "color:var(--danger,#c0392b)" },
        "Conversion stopped: " + p.error));
      body.append(el("div", { class: "small dim", style: "margin-top:4px" },
        "Nothing was lost — converted checkpoints stay converted and the rest "
        + "are untouched. Running it again resumes."));
    }

    // Stories the conversion REFUSED. Each was compacted on a duplicate,
    // failed the equivalence check, and had its original left exactly as it
    // was. Named, because "some stories were skipped" is not something a host
    // can act on.
    const skipped = p.skipped || [];
    if (skipped.length) {
      const box = el("div", { style: "margin-top:8px;padding:8px 10px;border-radius:7px;"
                                   + "border:1px solid var(--danger,#c0392b)" },
        el("div", { style: "font-weight:600" },
           `${skipped.length} ${skipped.length === 1 ? "story was" : "stories were"} `
           + "left alone to avoid losing anything"));
      for (const s of skipped) {
        box.append(el("div", { class: "small", style: "margin-top:5px" },
          el("b", {}, `Cannot compact "${s.name}"`),
          el("span", { class: "dim" }, ` — ${s.reason}`)));
      }
      box.append(el("div", { class: "small dim", style: "margin-top:6px" },
        "These keep their original checkpoints and still roll back normally. "
        + "Everything else was converted."));
      body.append(box);
    }

    const legacy = d.legacy || 0, total = d.checkpoints || 0;
    if (!total) {
      body.append(el("div", {}, "No checkpoints stored yet."));
      return;
    }
    if (!legacy) {
      body.append(el("div", {}, `✓ All ${total.toLocaleString()} checkpoints are `
                              + `in the current format (${mb(d.bytes)}).`));
      body.append(el("div", { class: "small dim", style: "margin-top:4px" },
        "There is nothing to convert. This offers itself again only if you "
        + "import a story saved by an older version."));
      return;
    }

    body.append(el("div", {},
      `${legacy.toLocaleString()} of ${total.toLocaleString()} checkpoints are in `
      + `the legacy format, using ${mb(d.legacy_bytes)}.`));
    body.append(el("div", { class: "small dim", style: "margin-top:5px" },
      "Converting stores each memory's embedding once instead of once per "
      + "checkpoint. Nothing is re-embedded and no memory is changed — only "
      + "where the vectors live. Typically shrinks them by 10× or more."));
    const go = el("button", { style: "margin-top:9px" }, "Convert now");
    go.onclick = async () => {
      go.disabled = true;
      go.textContent = "Starting…";
      try {
        const r = await api("POST", "/api/maintenance/checkpoints/compact", {});
        // The server refuses when there is nothing legacy left, which is the
        // right answer for a stale card or a direct API call. Say so rather
        // than showing a bar for a run that never started.
        if (r && r.started === false) {
          go.remove();
          body.append(el("div", { class: "small dim", style: "margin-top:6px" },
            r.reason === "nothing to convert"
              ? "Nothing to convert — every checkpoint is already in the current "
                + "format. This becomes available again if you import a story "
                + "saved by an older version."
              : `Not started: ${r.reason || "unknown reason"}`));
          return;
        }
      }
      catch (e) {
        go.disabled = false;
        go.textContent = "Convert now";
        body.append(el("div", { style: "color:var(--danger,#c0392b);margin-top:6px" },
          e?.message || String(e)));
        return;
      }
      render();
    };
    body.append(go);
  };

  render();
  return wrap;
}

function renderUpdateStatus(b, r) {
  // ok:false is an environment problem (not a git checkout, offline, no
  // remote) -- surface the server's own explanation rather than a retry loop.
  if (!r || !r.ok) return renderUpdateError(b, (r && r.error) || "Update check failed.");

  b.innerHTML = "";
  b.append(el("div", { class: "dim", style: "margin-bottom:10px" },
    `Branch ${r.branch} · current ${r.current}`
    + (r.ahead ? ` · ${r.ahead} local commit(s) ahead` : "")));

  if (r.up_to_date) {
    b.append(el("div", { class: "card" }, "✓ You're on the latest version."));
    b.append(checkpointCompactionBlock());
    b.append(el("div", { class: "row", style: "margin-top:10px" },
      el("button", { onclick: closeModal }, "Close")));
    return;
  }

  b.append(el("div", {}, el("b", {}, `${r.behind} update(s) available`)));

  // Changelog: prefer GitHub release notes for the incoming version tags;
  // fall back to raw commit subjects when there are no tagged releases in
  // range (or GitHub was unreachable -> r.releases is null).
  if (r.releases && r.releases.length) {
    const box = el("div", { class: "card", style: "margin-top:8px;max-height:320px;overflow:auto" },
      el("b", { class: "dim" }, "Release notes"));
    for (const rel of r.releases) {
      box.append(el("div", { style: "margin-top:12px;font-weight:600" }, rel.name || rel.tag));
      if (rel.body) {
        box.append(el("div", { class: "dim", style: "margin-top:4px;white-space:pre-wrap" }, rel.body));
      }
    }
    b.append(box);
  } else if (r.commits && r.commits.length) {
    b.append(el("div", { class: "card", style: "margin-top:8px;max-height:260px;overflow:auto" },
      el("b", { class: "dim" }, "Changelog"),
      ...r.commits.map(c => el("div", { style: "margin-top:6px" },
        el("code", { class: "dim" }, c.hash), " ", c.subject))));
  }

  if (r.dirty) {
    b.append(el("div", { class: "dim", style: "margin-top:10px;white-space:pre-wrap" },
      "⚠ You have local uncommitted changes. Commit or stash them before "
      + "installing an update."));
  }

  b.append(checkpointCompactionBlock());

  const installBtn = el("button", { class: "primary" }, "Install update");
  installBtn.onclick = () => runUpdateInstall(b, installBtn);
  b.append(el("div", { class: "row", style: "margin-top:12px" },
    installBtn,
    el("button", { onclick: closeModal }, "Later")));
}

function runUpdateInstall(b, btn) {
  const ownsModal = modalOwnership(b);
  btn.disabled = true;
  btn.textContent = "Installing…";
  const status = el("div", { class: "row", style: "margin-top:10px" },
    el("span", { class: "spinner" }), el("span", { class: "dim" }, "Applying update…"));
  b.append(status);
  api("POST", "/api/updates/install")
    .then(r => {
      if (!ownsModal()) return;
      status.remove();
      if (!r || !r.ok) return renderUpdateError(b, (r && r.error) || "Install failed.");
      if (!r.updated) { toast(r.message || "Already up to date.", "ok"); return renderUpdateChecking(b); }
      renderUpdateDone(b, r);
    })
    .catch(e => {
      if (!ownsModal()) return;
      status.remove();
      renderUpdateError(b, e?.message || "Install failed.");
    });
}

function renderUpdateDone(b, r) {
  b.innerHTML = "";
  b.append(el("div", { class: "card" },
    el("b", {}, "✓ Update installed"),
    el("div", { class: "dim", style: "margin-top:6px" },
      r.message || `Updated to ${r.current}.`)));
  b.append(el("div", { style: "margin-top:12px" },
    el("b", {}, "Please restart the server"),
    el("div", { class: "dim", style: "margin-top:6px;white-space:pre-wrap" },
      "The new code is on disk, but the running process is still using the "
      + "old version. Stop the server and start it again (e.g. re-run "
      + "`make run`), then reload this page.")));
  b.append(el("div", { class: "row", style: "margin-top:12px" },
    el("button", { class: "primary", onclick: closeModal }, "Got it")));
}

// ---- Prompts ----
//: Set before a language change reloads the page, so the reader lands back in
//: the menu they were in rather than on the story with the modal gone.
const REOPEN_PROMPTS_KEY = "sonder.reopenPrompts";

function openPromptsModal() {
  const names = ["Default", ...Object.keys(S.boot.prompt_presets)];
  const sel = el("select", {}, names.map(n => el("option", { value: n, ...(n === S.boot.active_preset ? { selected: "" } : {}) }, n)));
  const nameIn = el("input", { placeholder: "preset name", value: S.boot.active_preset === "Default" ? "" : S.boot.active_preset });
  // A preset overrides only the language it was authored in (prompts.py's
  // _preset_override), so the editor has to say which language it is showing
  // -- and be able to load that pack's own sheets to edit, rather than
  // offering English ones to overwrite a Japanese story with.
  const storyPacks = (S.boot.language_packs || []).filter(p => p.story);
  // The language actually in force: this story's, or the interface's when no
  // story is open. Without this the control always opened on the first pack
  // in the list and silently disagreed with the interface around it.
  const currentLanguage =
    (S.chat && S.chat.chat && S.chat.chat.story_language)
    || S.uiLanguage || "en";
  const langSel = el("select", {}, storyPacks.map(p =>
    el("option", {
      value: p.id,
      ...(p.id === currentLanguage ? { selected: "" } : {})
    }, p.native_name || p.name || p.id)));
  // Bootstrap already ships the English bodies; every other language costs
  // one fetch, once per modal.
  const baselines = { en: S.boot.default_prompts };
  const fileIn = el("input", { type: "file", accept: ".json,application/json", style: "display:none" });
  const presetOf = n => (n === "Default" ? null : S.boot.prompt_presets[n]);

  modal("Prompts", b => {
    const tas = {};
    const renderTA = () => {
      $$(".pta").forEach(x => x.remove());
      const defaults = baselines[langSel.value] || {};
      const preset = presetOf(sel.value);
      // A preset's bodies only belong on top of its own language's sheets.
      const src = (preset && preset.language === langSel.value) ? preset.prompts : {};
      for (const [k, v] of Object.entries(defaults)) {
        const ta = el("textarea", { class: "pta", style: "width:100%", rows: "6" }, src[k] || v);
        tas[k] = ta; b.append(el("div", { class: "card pta" }, el("b", {}, k), ta));
      }
    };
    const showLanguage = async () => {
      const id = langSel.value;
      if (!baselines[id]) {
        try { baselines[id] = (await api("GET", "/api/default_prompts?language=" + encodeURIComponent(id))).prompts; }
        catch (e) { return toast(e.message, "err"); }
      }
      renderTA();
    };
    b.append(el("div", { class: "row" }, "Preset: ", sel, "Language: ", langSel),
      el("div", { class: "small dim", style: "margin:-4px 0 8px 0" },
        "One switch: this picks the prompt sheets shown below and also sets the "
        + "interface language and this story's language. Existing prose and "
        + "memories are not translated."),
      el("div", { class: "row" },
      el("button", { onclick: async () => {
        await api("PUT", "/api/active_preset", { name: sel.value });
        await boot();
        // A preset applies only to its own language, so activating an English
        // one while working in Japanese is legal and does nothing -- say so,
        // rather than letting it read as the setting not having stuck.
        const chosen = presetOf(sel.value);
        if (chosen && chosen.language !== langSel.value) {
          toast(`Preset activated, but it is a ${chosen.language} preset and `
                + `this is ${langSel.value} — it will not apply here.`, "warn");
        } else {
          toast("Preset activated.", "ok");
        }
      } }, "Set active"),
      nameIn,
      el("button", { onclick: async () => {
        const nm = nameIn.value.trim(); if (!nm || nm === "Default") return toast("Pick a preset name.", "warn");
        const defaults = baselines[langSel.value] || {};
        const prompts = {}; for (const [k, ta] of Object.entries(tas)) if (ta.value !== defaults[k]) prompts[k] = ta.value;
        await api("PUT", "/api/prompt_presets", { name: nm, language: langSel.value, prompts }); await boot(); closeModal();
        toast("Preset saved.", "ok");
      } }, "Save preset"),
      el("button", { onclick: async () => {
        if (sel.value === "Default") return toast("Pick a saved preset to export.", "warn");
        try {
          const doc = await api("GET", "/api/prompt_presets/" + encodeURIComponent(sel.value) + "/export");
          downloadJSON(doc, sel.value.replace(/[^a-z0-9_-]/gi, "_") + ".prompt-preset.json");
          toast("Preset exported.", "ok");
        } catch (e) { toast(e.message, "err"); }
      } }, "Export"),
      el("button", { onclick: () => fileIn.click() }, "Import"),
      el("button", { onclick: async () => {
        if (sel.value === "Default") return;
        if (!await confirmModal("Delete this preset?", { danger: true, confirmLabel: "Delete" })) return;
        await api("DELETE", "/api/prompt_presets/" + encodeURIComponent(sel.value));
        await boot(); closeModal(); toast("Preset deleted.", "ok");
      } }, "Delete preset"), fileIn));
    fileIn.onchange = () => {
      const f = fileIn.files && fileIn.files[0];
      fileIn.value = "";
      if (!f) return;
      const reader = new FileReader();
      reader.onload = async () => {
        let doc;
        try { doc = JSON.parse(reader.result); }
        catch (e) { return toast(`Invalid JSON: ${e.message}`, "err"); }
        try {
          const r = await api("POST", "/api/prompt_presets/import", { preset: doc });
          await boot(); closeModal();
          // An import never overwrites a saved sheet, so say when it landed
          // under a different name than the file asked for.
          toast(r.renamed ? `Preset imported as "${r.name}".` : "Preset imported.", "ok");
        } catch (e) { toast(e.message, "err"); }
      };
      reader.readAsText(f);
    };
    sel.onchange = () => {
      // Following the preset to its own language is what makes its bodies
      // visible at all; leaving the selector behind would show the sheets
      // greyed back to pack defaults.
      const preset = presetOf(sel.value);
      if (preset && storyPacks.some(p => p.id === preset.language)) langSel.value = preset.language;
      showLanguage();
    };
    // The whole language change, from one control. The prompt sheets, the
    // interface and the open story all move together -- a host who picks
    // Japanese here means Japanese, not "Japanese prompts under an English
    // interface". Story language is per-chat, so it only applies to the story
    // currently open, and only when no turn is running.
    langSel.onchange = async () => {
      const id = langSel.value;
      await showLanguage();
      // The wizard reads this for the language of a NEW story, so the single
      // switch has to set it too -- otherwise new characters and personas are
      // still generated in whatever the wizard last remembered.
      try { localStorage.setItem("storyLanguage", id); } catch (e) {}
      let storyNote = "";
      if (S.chatId) {
        try {
          const out = await api("PUT", `/api/chats/${S.chatId}/language`,
                                { language: id });
          if (S.chat) S.chat.chat.story_language = out.language;
        } catch (e) {
          // A turn in flight refuses the change; the interface still moves.
          storyNote = " This story kept its language: " + e.message;
        }
      }
      if (id !== S.uiLanguage) {
        try {
          await api("PUT", "/api/ui-language", { language: id });
          toast(`Language changed.${storyNote}`, "ok");
          // Reload for the same reason the style guide does: localizeDocument
          // rewrites English source text in place, so it cannot translate a
          // second time from an already-translated DOM. Come back to this
          // menu afterwards -- the change was made FROM here, and dropping
          // the reader onto the story reads as the menu having crashed.
          try { sessionStorage.setItem(REOPEN_PROMPTS_KEY, "1"); } catch (e) {}
          return window.location.reload();
        } catch (e) { return toast(e.message, "err"); }
      }
      if (storyNote) toast(storyNote.trim(), "warn");
    };
    const active = presetOf(sel.value);
    if (active && storyPacks.some(p => p.id === active.language)) langSel.value = active.language;
    showLanguage();
  });
}

$("#b-prompts").onclick = openPromptsModal;

// Called by app.js once boot() has repopulated S.boot, which this modal reads.
function reopenPromptsIfRequested() {
  let wanted = false;
  try {
    wanted = !!sessionStorage.getItem(REOPEN_PROMPTS_KEY);
    if (wanted) sessionStorage.removeItem(REOPEN_PROMPTS_KEY);
  } catch (e) { return; }  // private mode: the menu simply does not reopen
  if (wanted) openPromptsModal();
}

// ---- Extensions ----
//
// The management surface for `extensions/`. The prototype shipped the routes
// (list / enable / disable) and the registries an extension talks to, but
// nothing that CALLED them -- so an installed extension sat at
// `enabled: false` with no way to turn it on, which reads as the extension
// system not being there at all.
//
// Deliberately honest about trust: an extension runs in-process with the
// engine's full access, and phase 1 has no review behind it. The dialog says
// so at the moment of enabling rather than deferring candour until a reviewed
// tier exists -- if the phase-1 wording is vague, a later "reviewed" badge
// means nothing by contrast.
function extensionTrustNote(ext) {
  const trust = String(ext.trust || "code");
  if (trust === "data") {
    return "Data only — content and settings. Runs no code.";
  }
  if (trust === "prompt") {
    return "Supplies prompt text. Runs no code of its own.";
  }
  return "Runs code in the engine's own process: full access to your stories, "
    + "your world state and your provider keys. Nothing has reviewed it.";
}

// What the manifest asks for, in the ENGINE's words. This used to be a
// second, hand-written list here, and it had drifted: it named six of the
// engine's ten capabilities, and the four it left out -- running code in the
// engine's process, running inside the turn's commit transaction, serving
// HTTP under the host session, and writing into a character's own state --
// are the four a host would most want named. `ext.disclosures` is computed
// from `extension_runtime.CAPABILITY_DISCLOSURES`, which is now the single
// place that vocabulary lives.
function extensionCapabilitySummary(ext) {
  return (ext && ext.disclosures) || [];
}

//: id -> the row `/api/extensions/updates` last returned for it. Held across
//: reopens of the menu so a check survives an enable or a remove redrawing
//: the list, and deliberately NOT fetched on open: a check is one network
//: round trip per installed extension, which is not something to spend every
//: time someone glances at the menu.
let EXTENSION_UPDATES = {};

function extensionSettingsSections(extId) {
  if (!window.Sonder || typeof Sonder._settingsFor !== "function") return [];
  const sections = Sonder._settingsFor(extId);
  if (!sections.length) return [];

  return sections.map(section => {
    // One class token per call rather than a space-joined literal:
    // `tools/extract_ui_catalog.py` normalises whitespace before deciding what
    // is a message, so a two-token class name reads as prose and lands in the
    // public translation catalog. A single token reads as machine vocabulary.
    const body = el("div", {});
    body.classList.add("ext-settings__body");
    body.classList.add("hidden");
    let drawn = false;
    const toggle = el("button", {}, section.label);
    toggle.classList.add("ghost");
    toggle.classList.add("ext-settings__toggle");
    toggle.onclick = () => {
      body.classList.toggle("hidden");
      if (body.classList.contains("hidden") || drawn) return;
      drawn = true;
      // Rendered on first open rather than on menu open: a section that
      // fetches would otherwise cost a round trip per installed extension
      // every time somebody glances at this list. Charged to its owner like
      // every other extension callback, and `render` may be async.
      Sonder._safe(section.owner, section.render, body);
    };
    return el("div", { class: "ext-settings", style: "margin-top:6px" },
      toggle, body);
  });
}

//: Whether the extensions dialog THIS function opened is still the one on
//: screen. Held across calls because the menu re-opens itself to show the
//: result of an enable, a disable, an install, a removal or an update check.
let extensionsDialog = null;

async function openExtensionsMenu() {
  let data;
  try { data = await api("GET", "/api/extensions"); }
  catch (e) { return toast(e.message, "err"); }

  const build = b => {
    if (data.safe_mode) {
      b.append(el("div", { class: "card" },
        el("b", {}, "Safe mode"),
        el("div", { class: "small dim", style: "margin-top:4px" },
          "Every extension is switched off for this run. Restart without the "
          + "safe-mode flag to load them again.")));
    }

    for (const err of (data.load_errors || [])) {
      b.append(el("div", { class: "card" },
        // `err.dir`, not `err.id`. No producer has ever written an `id`
        // here, and none can: a load error is very often the manifest's id
        // being missing, malformed, or a duplicate, so the DIRECTORY is the
        // only identity a failed load reliably has. Reading the field that
        // was never written meant every broken extension reported itself as
        // "an extension", with the reason attached and no way to tell which
        // one -- while the loader had the directory name in hand the whole
        // time. The empty string is the whole-listing failure, which is
        // genuinely not about one directory.
        el("b", {}, `${err.dir || "an extension"} failed to load`),
        el("div", { class: "small err", style: "margin-top:4px;white-space:pre-wrap" },
          String(err.error || err))));
    }

    if (!(data.extensions || []).length) {
      b.append(el("div", { class: "small dim" },
        "Nothing installed. Extensions live in the ", el("code", {}, "extensions/"),
        " folder — one directory each, with a manifest.json."));
    }

    for (const ext of (data.extensions || [])) {
      const enabled = !!ext.enabled;
      const caps = extensionCapabilitySummary(ext);
      const toggle = el("button", { class: enabled ? "" : "primary" },
        enabled ? "Disable" : "Enable");
      toggle.onclick = async () => {
        // Enabling is the consent moment, so the warning goes HERE rather
        // than in a page nobody reads.
        // The consent moment is the ONE moment `capabilities` exists for, and
        // it used to show the trust sentence alone while the capability
        // summary was rendered into the row BEHIND the dialog. Disclosure
        // that arrives after consent is not disclosure.
        if (!enabled && !await confirmModal(
              `Enable ${ext.name || ext.id}?\n\n${extensionTrustNote(ext)}`
              + (caps.length
                  ? `\n\nIt asks to:\n${caps.map(line => "• " + line).join("\n")}`
                  : ""),
              { confirmLabel: "Enable" })) return;
        try {
          await api("POST", `/api/extensions/${encodeURIComponent(ext.id)}/`
                    + (enabled ? "disable" : "enable"));
        } catch (e) { return toast(e.message, "err"); }
        toast(enabled ? "Extension disabled." : "Extension enabled.", "ok");
        // The server half is already live -- an enabled stage joins the next
        // turn's plan. The browser half is not: the page-load bundle is one
        // `<script>` and a script tag loads once, so a page served while this
        // extension was off holds ZERO bytes of it. `_load` fetches that one
        // extension's script and stylesheet now; `_unload` drops its
        // registrations and its injected elements. This is why enabling no
        // longer reloads the page.
        if (window.Sonder) {
          if (enabled) Sonder._unload(ext.id);
          else await Sonder._load(ext.id);
          Sonder.refresh();
        }
        openExtensionsMenu();
      };

      const remove = el("button", { class: "ghost", title: "Remove" }, "🗑");
      remove.onclick = async () => {
        if (!await confirmModal(
              `Remove ${ext.name || ext.id}?\n\nIts files are deleted. Anything `
              + `it stored in your stories is KEPT, so reinstalling picks them `
              + `back up where they left off.`,
              { danger: true, confirmLabel: "Remove" })) return;
        try { await api("DELETE", `/api/extensions/${encodeURIComponent(ext.id)}`); }
        catch (e) { return toast(e.message, "err"); }
        toast("Extension removed.", "ok");
        // Its panel is still registered in this page until we say otherwise;
        // the files being gone does not retract a sidebar tab.
        if (window.Sonder) { Sonder._unload(ext.id); Sonder.refresh(); }
        openExtensionsMenu();
      };

      // An update button appears only once a check has actually said so.
      // Offering one unconditionally would mean either checking on every open
      // (a round trip per extension, for a glance) or offering an action that
      // usually does nothing.
      const report = EXTENSION_UPDATES[ext.id];
      let update = null;
      if (report && report.update) {
        update = el("button", { class: "primary", title: report.latest || "" },
          "Update");
        update.onclick = async () => {
          await backgroundTask("Updating extension",
            () => api("POST", `/api/extensions/${encodeURIComponent(ext.id)}/update`),
            { onSuccess: async () => {
                delete EXTENSION_UPDATES[ext.id];
                // The Python half is already the new one; the browser still
                // holds the old script, so reload it the way enable does.
                if (window.Sonder && enabled) {
                  Sonder._unload(ext.id);
                  await Sonder._load(ext.id);
                  Sonder.refresh();
                }
                openExtensionsMenu();
              },
              successMessage: "Extension updated." });
        };
      }

      b.append(el("div", { class: "card" },
        el("div", { class: "row" },
          el("b", {}, ext.name || ext.id),
          el("span", { class: "small dim" }, `v${ext.version || "?"}`),
          el("span", { class: "small dim" },
            ext.provenance ? String(ext.provenance) : "local"),
          update, toggle, remove),
        report
          ? el("div", { class: "small", style: "margin-top:4px" },
              report.update
                ? el("span", { class: "ok" }, "An update is available.")
                : report.checkable
                  ? el("span", { class: "dim" }, "Up to date.")
                  : el("span", { class: "dim" },
                      "Cannot check for updates — ", txt(String(report.reason || ""))))
          : null,
        ext.description
          ? el("div", { class: "small dim", style: "margin-top:4px" }, ext.description)
          : null,
        caps.length
          ? el("div", { class: "small", style: "margin-top:6px" },
              el("span", { class: "dim" }, "Declares: "), caps.join(" · "))
          : null,
        el("div", { class: "small dim", style: "margin-top:4px" },
          extensionTrustNote(ext)),
        ext.error
          ? el("div", { class: "small err", style: "margin-top:4px" }, String(ext.error))
          : null,
        // The extension's own configuration, rendered inside its own card.
        // Only for an ENABLED one: a disabled extension's registrations are
        // cleared, so there is nothing to render and a section that survived
        // its owner would be configuring code that is not running.
        //
        // Collapsed by default. This menu is a list you scan to find one
        // extension, and a panel expanded by default would push every card
        // below it off the screen.
        ...(enabled ? extensionSettingsSections(ext.id) : [])));
    }

    // Install sits at the BOTTOM: the list is what you came for, and the
    // install field is the occasional act.
    const source = el("input", {
      placeholder: "https://github.com/…  or  https://…/extension.zip  or  /path/to/extension",
      style: "flex:1" });
    const installBtn = el("button", { class: "primary" }, "Install");
    installBtn.onclick = async () => {
      const value = source.value.trim();
      if (!value) return toast("Paste a URL or a folder path first.", "warn");
      if (!await confirmModal(
            `Install from:\n${value}\n\nNothing has reviewed this. Once you `
            + `enable it, it runs in the engine's own process with full access `
            + `to your stories, your world state and your provider keys.`,
            { confirmLabel: "Install" })) return;
      await backgroundTask("Installing extension",
        () => api("POST", "/api/extensions/install", { source: value }),
        { onSuccess: async () => {
            // A freshly installed extension arrives switched OFF, so there is
            // nothing to load yet -- only the list to rebuild from the server
            // rather than from this page's stale copy.
            openExtensionsMenu();
          },
          successMessage: "Extension installed — enable it to switch it on." });
    };
    const checkBtn = el("button", {}, "Check for updates");
    checkBtn.onclick = async () => {
      await backgroundTask("Checking for updates",
        () => api("GET", "/api/extensions/updates"),
        { onSuccess: async (result) => {
            EXTENSION_UPDATES = {};
            for (const row of (result.updates || [])) EXTENSION_UPDATES[row.id] = row;
            openExtensionsMenu();
          },
          successMessage: null });
    };

    b.append(
      el("div", { style: "margin-top:14px;border-top:1px solid var(--bd);padding-top:10px" },
        el("div", { class: "row" },
          el("div", { class: "small" }, "Install an extension"),
          el("span", { style: "flex:1" }),
          checkBtn),
        el("div", { class: "row", style: "margin-top:6px" }, source, installBtn),
        el("div", { class: "small dim", style: "margin-top:4px" },
          "A git repository, a zip from a URL, or a folder on this machine. "
          + "Add #branch or #tag to a repository URL to follow that instead of "
          + "the default branch. Installed extensions arrive switched off — "
          + "nothing runs until you enable it."),
        el("div", { class: "small dim", style: "margin-top:4px" },
          "Only what was installed from a repository can be checked for "
          + "updates: a zip would have to be downloaded in full to compare, "
          + "and a folder has no upstream.")));

    b.append(el("div", { class: "small dim", style: "margin-top:10px" },
      "A capability list is what the extension DECLARES, checked against what "
      + "it registers. It is a statement of intent for you to judge, not a "
      + "restriction the engine enforces."));
  };

  // A REFRESH REPLACES THIS DIALOG; IT DOES NOT OPEN A SECOND ONE.
  //
  // Five things inside this menu re-open it to show their result — check for
  // updates, enable, disable, install, remove — and `modal()` pushes whatever
  // is currently open onto `S.modalStack` before drawing. So each of those
  // stacked another copy of the extensions menu on top of the one the reader
  // was already looking at, and every dismissal revealed the previous copy,
  // holding data one action older each time. Reported live: enable, disable
  // and check-for-updates each yielding another instance.
  //
  // Rebuilding in place rather than closing first, because closing POPS the
  // stack and would restore whatever dialog this menu was opened over.
  //
  // Ownership rather than a marker on the shared box: a marker has to be
  // CLEARED, and every path that could clear it belongs to `modal()` and
  // `closeModal()` rather than here — so it would go stale the moment the
  // reader closed this menu and opened something else, and the refresh would
  // then rebuild the extensions list inside an unrelated dialog.
  // `modalOwnership()` already answers "is the dialog I opened still the one
  // on screen", and answers it correctly when a stacked child closes and
  // restores us.
  if (extensionsDialog && extensionsDialog()) {
    const body = $("#modalbody");
    body.innerHTML = "";
    build(body);
    return;
  }
  modal("Extensions", build);
  extensionsDialog = modalOwnership();
}

$("#b-extensions").onclick = openExtensionsMenu;

