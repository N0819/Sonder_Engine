// ---- Chat tool modals ----
$("#b-world").onclick = async () => {
  if (!S.chatId) return;
  const w = await api("GET", `/api/chats/${S.chatId}/world`);
  const ta = el("textarea", { style: "width:100%;height:420px" }, JSON.stringify(w, null, 2));
  modal("World state", b => b.append(
    el("div", { class: "small dim", style: "margin-bottom:8px" },
      "The raw internal record of the scene — rooms, positions, objects, standing facts — that every stage of "
      + "a turn reads from and writes to. The story keeps this updated on its own; you don't need to touch it "
      + "to play. Edit it only to hand-correct something that's drifted wrong (a character in the wrong room, "
      + "a fact that should no longer be true)."),
    ta,
    el("div", { class: "row", style: "margin-top:8px" },
      el("button", { class: "primary", onclick: async () => { let j; try { j = JSON.parse(ta.value) } catch (e) { return toast("Invalid JSON", "err") } await api("PUT", `/api/chats/${S.chatId}/world`, j); closeModal(); toast("World state saved.", "ok"); } }, "Save"))));
};

$("#b-attire").onclick = async () => {
  if (!S.chatId) return;
  const a = await api("GET", `/api/chats/${S.chatId}/attire`);
  const ta = el("textarea", { style: "width:100%;height:340px" }, JSON.stringify(a, null, 2));
  modal("Attire — {name:{wearing:[],state:[]}}", b => b.append(
    el("div", { class: "small dim", style: "margin-bottom:8px" },
      "What each character is currently wearing and any visible physical state (injuries, disguises, damage) "
      + "the story should keep consistent going forward. Updates automatically as the story progresses; edit "
      + "directly only to correct something or set up a scene's starting appearance by hand."),
    ta,
    el("div", { class: "row", style: "margin-top:8px" },
      el("button", { class: "primary", onclick: async () => { let j; try { j = JSON.parse(ta.value) } catch (e) { return toast("Invalid JSON", "err") } await api("PUT", `/api/chats/${S.chatId}/attire`, j); closeModal(); toast("Attire saved.", "ok"); } }, "Save"))));
};

// Genre & style: the author's standing instruction for anything the engine
// INVENTS. Self-determination is the default and stays first-class -- a blank
// genre means "you work it out", which is what the engine did before this
// existed, not "this world has no style".
$("#b-style").onclick = async () => {
  if (!S.chatId) return;
  const r = await api("GET", `/api/chats/${S.chatId}/style_guide`);
  const g = r.style_guide || {};

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

  modal("Genre & style", b => b.append(
    el("div", { class: "small dim" },
      "Applies to what the engine ", el("b", {}, "invents"),
      " — new rooms, objects, lore, and the register of resolved events. It never overrides canon, an established room, or something you declared yourself, and it is never quoted back into the prose."),
    el("div", { class: "row", style: "margin-top:10px" },
      el("span", { class: "small", style: "width:70px" }, "Genre"), genre, datalist, selfBtn),
    el("div", { class: "row", style: "margin-top:6px" },
      el("span", { class: "small", style: "width:70px" }, "Tone"), tone),
    el("div", { style: "margin-top:10px" },
      el("div", { class: "small" }, "Director notes"), dirNotes),
    el("div", { style: "margin-top:8px" },
      el("div", { class: "small" }, "Mapping notes ", el("span", { class: "dim" }, "— shapes newly generated rooms")), mapNotes),
    el("div", { style: "margin-top:8px" },
      el("div", { class: "small" }, "Avoid"), avoid),
    el("div", { class: "row", style: "margin-top:10px" },
      el("button", { class: "primary", onclick: async () => {
        const out = await api("PUT", `/api/chats/${S.chatId}/style_guide`, {
          style_guide: {
            genre: genre.value, tone: tone.value,
            director_notes: dirNotes.value, mapping_notes: mapNotes.value,
            avoid: avoid.value,
          },
        });
        closeModal();
        toast(Object.keys(out.style_guide).length
          ? "Style guide saved." : "Style guide cleared — the engine self-determines.", "ok");
      } }, "Save"),
      el("button", { onclick: async () => {
        await api("PUT", `/api/chats/${S.chatId}/style_guide`, { style_guide: {} });
        closeModal(); toast("Style guide cleared — the engine self-determines.", "ok");
      } }, "Clear all"))));
};

$("#b-dlg").onclick = async () => {
  if (!S.chatId) return;
  const c = await api("GET", `/api/chats/${S.chatId}/dialogue_config`);
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
    el("div", { class: "small dim", style: "margin-top:10px" },
      "Prose pacing for NPC dialogue — how much NPCs tend to say, independent of autonomy above."),
    el("table", { class: "grid" },
      el("tr", {}, el("td", {}, "style"), el("td", {}, st)),
      el("tr", {}, el("td", {}, "min lines"), el("td", {}, mn)),
      el("tr", {}, el("td", {}, "max lines"), el("td", {}, mx)),
      el("tr", {}, el("td", {}, "variance"), el("td", {}, va))),
    el("div", { class: "row", style: "margin-top:8px" },
      el("button", { class: "primary", onclick: async () => {
        await api("PUT", `/api/chats/${S.chatId}/dialogue_config`, {
          style: st.value, min_lines: mn.value, max_lines: mx.value, variance: va.value,
          autonomy: +auto.value, allow_npc_initiative: npcInit.checked, allow_npc_to_npc_dialogue: npcNpc.checked,
          stop_on_player_address: stopAddr.checked, stop_on_question_to_player: stopQ.checked, silence_ends_exchange: silence.checked
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
  const d = await api("GET", "/api/chats/" + S.chatId);

  const tabs = [
    { id: "cast", label: "Cast", render: renderCastTab },
    { id: "lorebooks", label: "Lorebooks", render: renderLorebooksTab },
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
      tabs.find(t => t.id === tabId).render(d, content);
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

function renderCastTab(d, b) {
  const ps = el("select", {}, [
    el("option", { value: "" }, "(no persona)"),
    ...S.boot.personas.map(p => el("option", {
      value: p.id,
      ...(p.id === d.chat.persona_id ? { selected: "" } : {})
    }, p.name))
  ]);
  ps.onchange = () =>
    api("PUT", "/api/chats/" + S.chatId, {
      persona_id: ps.value ? +ps.value : null
    });

  b.append(
    el("div", { class: "row" },
      "Persona: ", ps,
      el("button", {
        onclick: () => personaPH()
      }, "🔒 persona secrets")
    )
  );

  b.append(el("h4", {}, "Participants"));
  for (const p of d.participants) {
    b.append(el("div", { class: "card row" },
      el("b", {}, p.name),
      el("span", { class: "badge" }, p.status),
      el("span", { class: "spacer" }),
      el("button", {
        onclick: async () => {
          if (p.status === "active")
            await api("DELETE",
              `/api/chats/${S.chatId}/characters/${p.id}`);
          else
            await api("POST",
              `/api/chats/${S.chatId}/characters`,
              { char_id: p.id });
          closeModal();
          $("#b-cast").click();
        }
      }, p.status === "active"
        ? "→ dormant" : "→ active"),
      el("button", {
        title: "Memory browser",
        onclick: () => memModal(p)
      }, "🧠"),
      el("button", {
        title: "How this character feels about everyone else",
        onclick: () => relationshipModal(p)
      }, "💞"),
      el("button", {
        title: "Per-story private history",
        onclick: () => chatPH(p)
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
              `/api/chats/${S.chatId}/characters`,
              { char_id: +addSel.value });
            closeModal();
            $("#b-cast").click();
          }
        }, "+ add to story")));
  }

  b.append(renderBackgroundPresencesPanel());
}

function renderLorebooksTab(d, b) {
    // ── Lorebook tree panel ──
    const lbPanel = el("div", { class: "card" });
    lbPanel.append(el("h4", {}, "Lorebooks"));

    const refreshBooks = async () => {
      const dd = await api("GET", "/api/chats/" + S.chatId);
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
                loreModal(lb.id);
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
                generateLoreModal(lb.id, true)
            }, "✨"),
            !isCanon
              ? el("button", {
                  title: "Detach from story",
                  onclick: async () => {
                    await api("DELETE",
                      `/api/chats/${S.chatId}/lorebooks/${lb.id}`);
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
                  `/api/chats/${S.chatId}/lorebooks`,
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

function renderMultiplayerTab(d, b) {
  b.append(renderGuestInvitePanel());
}

// ── Frames: diegetic eras, persona stationing, and paradox settings ──
// Frames let a story visit a different point in its own timeline --
// serially (one era live at a time, switched via the frame pills in the
// header) or with genuinely simultaneous play once more than one
// attached persona is stationed to a different frame (frames.py/
// db.py's active_frame_id contextvar is what actually makes two frames'
// pipelines safe to run at once, not anything in this panel).
function renderFramesTab(d, b) {
  b.append(renderFramesListPanel());
  b.append(renderPersonaStationingPanel());
  b.append(renderParadoxPanel());
}

function renderFramesListPanel() {
  const panel = el("div", {});
  const refresh = async () => {
    panel.innerHTML = "";
    panel.append(el("div", { class: "lore-panel-head" },
      el("span", { class: "lore-panel-title" }, "Frames")));
    panel.append(el("div", { class: "small dim", style: "margin-bottom:8px" },
      "Declare a different era of this same story -- a flash-forward, a visit "
      + "to the past. Switch between them with the pills next to the story name."));

    const { frames } = await api("GET", `/api/chats/${S.chatId}/frames`);
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
              await api("POST", `/api/chats/${S.chatId}/frames`, {
                label, ordinal: +ordinalIn.value || 0, kind: kindSel.value,
                travelers: [...travelersSel.selectedOptions].map(o => +o.value),
                nonexistent_cast: [...nonexistentSel.selectedOptions].map(o => +o.value),
              });
              toast("Frame created.", "ok");
              await openChat(S.chatId); // refresh the frame pills too
              refresh();
            } catch (e) {
              toast("Could not create frame: " + e.message, "err");
            }
          }
        }, "+ Create frame")));
  };
  refresh();
  return panel;
}

function renderPersonaStationingPanel() {
  const panel = el("div", { style: "margin-top:14px" });
  const refresh = async () => {
    panel.innerHTML = "";
    panel.append(el("div", { class: "lore-panel-head" },
      el("span", { class: "lore-panel-title" }, "Who's where")));

    const [{ personas }, { frames }] = await Promise.all([
      api("GET", `/api/chats/${S.chatId}/personas`),
      api("GET", `/api/chats/${S.chatId}/frames`),
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
          await api("PUT", `/api/chats/${S.chatId}/personas/${p.id}/station`,
            { frame_id: sel.value ? +sel.value : null });
          toast(`${p.name} is now in ${sel.options[sel.selectedIndex].text}.`, "ok");
        } catch (e) {
          toast("Could not move them: " + e.message, "err");
          refresh();
        }
      };
      panel.append(el("div", { class: "card row" }, el("b", {}, p.name), sel));
    }
  };
  refresh();
  return panel;
}

function renderParadoxPanel() {
  const panel = el("div", { style: "margin-top:14px" });
  const refresh = async () => {
    panel.innerHTML = "";
    panel.append(el("div", { class: "lore-panel-head" },
      el("span", { class: "lore-panel-title" }, "Time paradox resolution")));
    panel.append(el("div", { class: "small dim", style: "margin-bottom:8px" },
      "What happens if a fixed point gets altered -- not every timeline hiccup, "
      + "only ones you deliberately pin below as load-bearing."));

    const [policy, { fixed_points, paradoxes }, { frames }] = await Promise.all([
      api("GET", `/api/chats/${S.chatId}/paradox_policy`),
      api("GET", `/api/chats/${S.chatId}/fixed_points`),
      api("GET", `/api/chats/${S.chatId}/frames`),
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
      await api("PUT", `/api/chats/${S.chatId}/paradox_policy`, { mode: modeSel.value });
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
            await api("DELETE", `/api/chats/${S.chatId}/fixed_points/${fp.anchor_id}`);
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
            await api("POST", `/api/chats/${S.chatId}/fixed_points`, {
              entity_id: entityIn.value.trim(), label: labelIn.value.trim(),
              required_exists: requireSel.value === "1",
            });
            toast("Fixed point declared.", "ok");
            refresh();
          } catch (e) {
            toast("Could not declare it: " + e.message, "err");
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
function renderBackgroundPresencesPanel() {
  const panel = el("div", {});
  panel.append(el("div", { class: "lore-panel-head" },
    el("span", { class: "lore-panel-title" }, "Background presences")));

  api("GET", `/api/chats/${S.chatId}/promotable`).then(({ presences }) => {
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
          onclick: () => promoteBackgroundPresence(S.chatId, p.name),
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
function renderGuestInvitePanel() {
  const panel = el("div", {});

  const refresh = async () => {
    panel.innerHTML = "";
    panel.append(el("div", { class: "lore-panel-head" },
      el("span", { class: "lore-panel-title" }, "Invite a friend")));

    const extras = await api("GET", `/api/chats/${S.chatId}/personas`).catch(() => ({ personas: [] }));
    const attached = extras.personas || [];

    if (attached.length) {
      const invites = (await api("GET", `/api/chats/${S.chatId}/guest_invites`)).grants;
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
                await api("DELETE", `/api/chats/${S.chatId}/guest_invites/${active.id}`);
                refresh();
              }
            }, "revoke")
          );
        } else {
          row.append(el("button", {
            onclick: async () => {
              const invite = await api("POST", `/api/chats/${S.chatId}/guest_invites`,
                { persona_id: p.id });
              const link = `${location.origin}/guest?code=${invite.code}`;
              modal("Share this with your friend", b => b.append(
                el("div", { class: "small dim", style: "margin-bottom:8px" },
                  "This link works once, expires in 30 minutes, and only lets them play as "
                  + p.name + ". They'll need this to actually be reachable -- run a tunnel "
                  + "(e.g. cloudflared tunnel --url http://localhost:8008) and swap this "
                  + "page's origin for the tunnel's public URL before sending it."),
                el("input", { readonly: "", value: link, style: "width:100%", onclick: e => e.target.select() }),
                el("div", { class: "row", style: "margin-top:8px" },
                  el("button", { class: "primary", onclick: () => { navigator.clipboard?.writeText(link); toast("Copied.", "ok") } }, "📋 Copy link"))));
              refresh();
            }
          }, "🔗 Generate invite"));
        }
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
            await api("POST", `/api/chats/${S.chatId}/personas`, { persona_id: pid });
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
function renderInsightsTab(d, b) {
  b.append(renderDramaticIronyPanel());
  b.append(renderPromiseLedgerPanel());
}

function renderDramaticIronyPanel() {
  const panel = el("div", {});
  panel.append(el("div", { class: "lore-panel-head" },
    el("span", { class: "lore-panel-title" }, "Dramatic irony")));
  panel.append(el("div", { class: "small dim", style: "margin-bottom:6px" },
    "What each character currently believes without having witnessed it firsthand -- secondhand, told, or inferred. Whether it's actually wrong is for you to judge."));

  api("GET", `/api/chats/${S.chatId}/dramatic_irony`).then(({ feed }) => {
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

function renderPromiseLedgerPanel() {
  const panel = el("div", { style: "margin-top:14px" });
  panel.append(el("div", { class: "lore-panel-head" },
    el("span", { class: "lore-panel-title" }, "Promise ledger")));
  panel.append(el("div", { class: "small dim", style: "margin-bottom:6px" },
    "Every promise-category memory across the whole story, in order. Kept or broken is a judgment call this doesn't make for you."));

  api("GET", `/api/chats/${S.chatId}/promises`).then(({ promises }) => {
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
  anthropic: "Pick the current flagship Claude (Opus or Sonnet) for narrator/character_major; a smaller Claude (Haiku) is fine for perception/mapping/utility.",
  openai: "Pick the current flagship GPT for narrator/character_major; a 'mini'/'nano'-tier variant is fine for perception/mapping/utility.",
  gemini: "Pick the current flagship Gemini Pro for narrator/character_major; Gemini Flash is fine for perception/mapping/utility.",
  deepseek: "DeepSeek's main chat/reasoning model works well for narrator/character_major; it's inexpensive enough that lightening other roles matters less.",
  xai: "Pick the current flagship Grok for narrator/character_major; a smaller/faster Grok variant for perception/mapping/utility.",
  mistral: "Pick a 'large' Mistral model for narrator/character_major; a 'small'/'nemo' variant for perception/mapping/utility.",
  groq: "Groq hosts other labs' open-weight models at very high speed -- pick the largest Llama/Qwen/Mixtral-family model it serves for narrator/character_major, a smaller one for the rest.",
  together: "Together hosts many open-weight models -- prefer a 70B+ Llama/Qwen/DeepSeek-family model for narrator/character_major, a smaller one for perception/mapping/utility.",
  openrouter: "Aggregates most providers above under one key -- the same per-role sizing logic applies; OpenRouter's model list shows context length and price per model to help compare.",
  nanogpt: "Also an aggregator with a large open-weight catalog -- prefer a well-known, large instruction-tuned model for narrator/character_major. Use '↻ models' to see what's actually included in your plan before picking.",
  ollama: "Whatever you've pulled locally -- larger/more recent (e.g. current Llama, Qwen, or Mistral family) for narrator/character_major, a smaller quantized model for perception/mapping/utility so it stays responsive on your hardware.",
  koboldcpp: "Whatever GGUF model you've loaded -- same sizing logic as Ollama above.",
  lmstudio: "Whatever model you've downloaded in LM Studio -- same sizing logic as Ollama above.",
  llamacpp: "Whatever GGUF model your llama.cpp server is serving -- same sizing logic as Ollama above.",
};

function modelRecommendationsBlock() {
  return el("div", { class: "small dim", style: "margin-top:6px" },
    el("div", {}, "The rule that matters most: ", el("b", {}, "bigger/newer for narrator and character_major"), " (this is the writing you actually read), ", el("b", {}, "smaller/cheaper for perception, mapping, and utility"), " (mechanical, rarely visible). Specific model names below are current examples, not a permanent list -- providers update their lineups often."),
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
      toast("Could not create provider: " + e.message, "err");
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
        provBox.append(el("div", { class: "card row" }, nm, kd, bu, ak,
          el("button", { onclick: async () => { await api("PUT", "/api/providers/" + p.id, { name: nm.value, kind: kd.value, base_url: bu.value, api_key: ak.value }); delete S.models[p.id]; await boot(); toast("Provider saved.", "ok"); } }, "Save"),
          el("button", { onclick: async () => { if (!await confirmModal("Delete provider?", { danger: true, confirmLabel: "Delete" })) return; await api("DELETE", "/api/providers/" + p.id); await boot(); closeModal(); $("#b-api").click(); } }, "✕"),
          el("button", { title: "Fetch models", onclick: async e => { e.target.textContent = "…"; await fetchModels(p.id); e.target.textContent = "✓"; } }, "↻ models")));
      }
    };
    renderProv();
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
            toast("Response limit saved: " + r.value + " tokens.", "ok");
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

    b.append(el("h4", {}, "Agent models"),
      el("div", { class: "small dim" },
        "Type to search the provider's model list. Open 'advanced' for samplers and backup models."),
      el("details", { style: "margin-top:6px" },
        el("summary", {}, "What do these roles do?"),
        el("div", { class: "small dim", style: "margin-top:6px" },
          el("div", {}, el("b", {}, "Setting only Default is enough to start playing"), " — every other role falls back to it automatically. The rest let you assign a faster or cheaper model to a specific stage of each turn without touching quality where it matters most."),
          el("div", { style: "margin-top:8px" }, el("b", {}, "director"), " — reads what you typed and decides what actually happens: whether an action succeeds, what an NPC's action resolves to. Gets this wrong and the story stops making sense, so keep it on a strong model."),
          el("div", {}, el("b", {}, "perception"), " — filters what each character can actually see/hear/know this turn, based on where they are and what their senses allow. Mechanical, not creative — a good candidate for a lighter model."),
          el("div", {}, el("b", {}, "character_bg / character_mid / character_major"), " — generate what a character does and says, tiered by how central that character is to the scene. Quality shows up directly in dialogue, so keep major characters on a strong model even if you lighten background ones."),
          el("div", {}, el("b", {}, "narrator"), " — turns everything into the prose you actually read. This is the model whose writing style you'll notice most."),
          el("div", {}, el("b", {}, "mapping"), " — keeps track of world facts, lore, and location layout in the background. Rarely visible directly, safe to experiment with."),
          el("div", {}, el("b", {}, "utility / embeddings"), " — small internal helper tasks (search, quick classification). Not worth spending a premium model on."))),
      el("details", { style: "margin-top:6px" },
        el("summary", {}, "Which model should I pick?"),
        modelRecommendationsBlock()));

    const roleInputs = {};
    const roleMeta = {};
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
      for (const role of S.boot.roles) {
        const meta = roleMeta[role];
        if (meta && meta.following) meta.rebuild(provider, model);
      }
    }

    const orderedRoles = [...S.boot.roles].sort(
      (a, b) => (a === "default" ? -1 : b === "default" ? 1 : 0)
    );

    for (const role of orderedRoles) {
      const cfg = am[role] || {};
      const isDefault = role === "default";
      const following = !isDefault && !(cfg.provider && cfg.model);
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

      const followChk = isDefault ? null : el("input", {
        type: "checkbox",
        title: "Keep this role in sync with Default until you edit it directly",
        ...(following ? { checked: "" } : {}),
      });

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
          }
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

      b.append(el(
        "div",
        { class: "card" },
        el(
          "div",
          { class: "row" },
          el(
            "b",
            { style: "width:130px" },
            role
          ),
          followChk
            ? el(
                "label",
                { class: "tgl small dim", style: "margin-right:8px;white-space:nowrap" },
                followChk,
                "follow default"
              )
            : null,
          primaryContainer
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

        await api("PUT", "/api/agent_models", out);
        await boot();
        closeModal();
        toast("Agent models saved.", "ok");
      } }, "Save all")));
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
  b.innerHTML = "";
  b.append(el("div", { class: "row" },
    el("span", { class: "spinner" }),
    el("span", { class: "dim" }, "Checking GitHub for updates…")));
  api("GET", "/api/updates/check")
    .then(r => renderUpdateStatus(b, r))
    .catch(e => renderUpdateError(b, e?.message || "Update check failed."));
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
      "⚠ You have local uncommitted changes. The update only fast-forwards, "
      + "so it will refuse to run if those edits would be overwritten."));
  }

  const installBtn = el("button", { class: "primary" }, "Install update");
  installBtn.onclick = () => runUpdateInstall(b, installBtn);
  b.append(el("div", { class: "row", style: "margin-top:12px" },
    installBtn,
    el("button", { onclick: closeModal }, "Later")));
}

function runUpdateInstall(b, btn) {
  btn.disabled = true;
  btn.textContent = "Installing…";
  const status = el("div", { class: "row", style: "margin-top:10px" },
    el("span", { class: "spinner" }), el("span", { class: "dim" }, "Applying update…"));
  b.append(status);
  api("POST", "/api/updates/install")
    .then(r => {
      status.remove();
      if (!r || !r.ok) return renderUpdateError(b, (r && r.error) || "Install failed.");
      if (!r.updated) { toast(r.message || "Already up to date.", "ok"); return renderUpdateChecking(b); }
      renderUpdateDone(b, r);
    })
    .catch(e => { status.remove(); renderUpdateError(b, e?.message || "Install failed."); });
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
$("#b-prompts").onclick = () => {
  const names = ["Default", ...Object.keys(S.boot.prompt_presets)];
  const sel = el("select", {}, names.map(n => el("option", { value: n, ...(n === S.boot.active_preset ? { selected: "" } : {}) }, n)));
  const nameIn = el("input", { placeholder: "preset name", value: S.boot.active_preset === "Default" ? "" : S.boot.active_preset });
  modal("Prompts", b => {
    const tas = {};
    const renderTA = () => {
      $$(".pta").forEach(x => x.remove());
      const src = sel.value === "Default" ? {} : (S.boot.prompt_presets[sel.value] || {});
      for (const [k, v] of Object.entries(S.boot.default_prompts)) {
        const ta = el("textarea", { class: "pta", style: "width:100%", rows: "6" }, src[k] || v);
        tas[k] = ta; b.append(el("div", { class: "card pta" }, el("b", {}, k), ta));
      }
    };
    b.append(el("div", { class: "row" }, "Preset: ", sel,
      el("button", { onclick: async () => { await api("PUT", "/api/active_preset", { name: sel.value }); await boot(); toast("Preset activated.", "ok"); } }, "Set active"),
      nameIn,
      el("button", { onclick: async () => {
        const nm = nameIn.value.trim(); if (!nm || nm === "Default") return toast("Pick a preset name.", "warn");
        const prompts = {}; for (const [k, ta] of Object.entries(tas)) if (ta.value !== S.boot.default_prompts[k]) prompts[k] = ta.value;
        await api("PUT", "/api/prompt_presets", { name: nm, prompts }); await boot(); closeModal();
        toast("Preset saved.", "ok");
      } }, "Save preset"),
      el("button", { onclick: async () => {
        if (sel.value === "Default") return;
        if (!await confirmModal("Delete this preset?", { danger: true, confirmLabel: "Delete" })) return;
        await api("DELETE", "/api/prompt_presets/" + encodeURIComponent(sel.value));
        await boot(); closeModal(); toast("Preset deleted.", "ok");
      } }, "Delete preset")));
    sel.onchange = renderTA; renderTA();
  });
};