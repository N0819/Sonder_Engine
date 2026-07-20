// ---- Scene mood ----
// Subtle ambient shift of the page background based on the latest turn's
// prose -- a plain keyword read of already-rendered text, entirely
// client-side. No pipeline/backend signal involved: this is intentionally
// cheap and approximate rather than a real sentiment model, since the goal
// is atmosphere, not accuracy. Keyword sets are illustrative, not
// exhaustive; ties are broken by whichever mood scores highest, and no
// signal at all (or a tie at zero) leaves the default "calm" look.
const MOOD_KEYWORDS = {
  tense: ["dark", "shadow", "fear", "afraid", "danger", "dread", "blood",
    "scream", "threat", "death", "dead", "kill", "hunt", "stalk", "wound",
    "pain", "terror", "panic", "claw", "teeth", "choke", "gasp", "cold dread"],
  warm: ["smile", "laugh", "warm", "gentle", "comfort", "embrace", "hug",
    "kind", "tender", "cozy", "safe", "relief", "grateful", "affection", "home"],
  somber: ["grief", "tears", "loss", "mourn", "sorrow", "alone", "lonely",
    "regret", "ache", "weep", "empty", "goodbye"],
  triumphant: ["victory", "triumph", "cheer", "exhilarat", "proud", "won",
    "glory", "celebrat", "joy", "success"],
};

function detectSceneMood(text) {
  const lower = String(text || "").toLowerCase();
  let best = "calm", bestScore = 0;
  for (const [mood, words] of Object.entries(MOOD_KEYWORDS)) {
    let score = 0;
    for (const w of words) if (lower.includes(w)) score++;
    if (score > bestScore) { best = mood; bestScore = score; }
  }
  return best;
}

function applySceneMood(text) {
  document.body.dataset.mood = detectSceneMood(text);
}

// Tracks which rendered .turn element is currently most visible in #msgs so
// the ambient mood follows whatever scene the user is actually looking at
// while scrolling, not just the newest turn. Recreated on every renderChat()
// since the old DOM nodes it observes get thrown away with M.innerHTML="".
let _moodObserver = null;

function observeSceneMood(msgsEl, turnEntries) {
  if (_moodObserver) {
    _moodObserver.disconnect();
    _moodObserver = null;
  }
  if (!turnEntries.length) return;

  // IntersectionObserver callbacks only report entries whose ratio crossed
  // a threshold since the last check -- not a full snapshot of everything
  // being observed -- so visibility has to be accumulated across calls
  // rather than read fresh each time.
  const ratios = new Map();
  const proseByEl = new Map(turnEntries.map(e => [e.el, e.prose]));

  _moodObserver = new IntersectionObserver(entries => {
    for (const entry of entries) {
      ratios.set(entry.target, entry.isIntersecting ? entry.intersectionRatio : 0);
    }
    let bestEl = null, bestRatio = 0;
    for (const [el, ratio] of ratios) {
      if (ratio > bestRatio) { bestRatio = ratio; bestEl = el; }
    }
    if (bestEl) applySceneMood(proseByEl.get(bestEl));
  }, { root: msgsEl, threshold: [0, 0.1, 0.25, 0.5, 0.75, 1] });

  for (const { el } of turnEntries) _moodObserver.observe(el);
}

async function openChat(id) {
  S.chatId = id;
  S.chat = await api("GET", "/api/chats/" + id);
  S.currentFrameId = null; // always reopen viewing the present
  renderSide();
  renderChat();
}

// Purely a client-side filter/view-selector -- see S.currentFrameId's
// definition in utils.js. Two browser tabs (or two different users) can
// independently pick different frames; the backend has no single
// "current" to keep in sync with.
function renderFrameBar() {
  const bar = $("#framebar");
  bar.innerHTML = "";
  if (!S.chat) return;
  const frames = S.chat.frames || [];
  if (frames.length <= 1) return; // just the implicit present -- nothing to switch between

  for (const f of frames) {
    bar.append(el("button", {
      class: "frame-pill" + (S.currentFrameId === f.id ? " on" : ""),
      title: f.id === null ? "The present" : `${f.kind} · ordinal ${f.ordinal}`,
      onclick: () => switchFrame(f.id)
    }, f.id === null ? "Present" : f.label));
  }
}

function switchFrame(frameId) {
  S.currentFrameId = frameId;
  renderFrameBar();
  renderChat();
}

// #b-world/#b-cast/#b-attire/#b-dlg all no-op with no chat open (each
// checks `if (!S.chatId) return` at the top of its own handler already) --
// disabling them when there's nothing for them to act on turns a silent
// dead click into an honest, visibly-inert control.
function updateChatScopedButtons() {
  const ready = !!S.chatId;
  for (const id of ["#b-world", "#b-cast", "#b-attire", "#b-dlg"]) {
    const btn = $(id);
    if (btn) btn.disabled = !ready;
  }
}

function renderChat() {
  const M = $("#msgs");
  M.innerHTML = "";
  updateChatScopedButtons();
  renderFrameBar();

  if (!S.chat) {
    $("#chatname").textContent = "No story selected";
    const ready = hasDefaultModel();
    M.append(el("div", { class: "empty-state", style: "margin:auto;max-width:440px" },
      el("div", { style: "font-size:15px;margin-bottom:14px" },
        ready ? "Ready when you are." : "Two steps and you're writing."),
      el("div", { class: "row", style: "justify-content:center;gap:10px;flex-wrap:wrap" },
        el("button", { class: ready ? "" : "primary", onclick: () => $("#b-api").click() },
          (ready ? "✓ " : "1. ") + "Connect an AI provider"),
        el("button", {
          class: ready ? "primary" : "",
          disabled: !ready,
          title: ready ? "" : "Connect a provider first",
          onclick: () => newChatWizard()
        }, "2. Start your first story")),
      S.boot && S.boot.chats && S.boot.chats.length
        ? el("div", { class: "small dim", style: "margin-top:14px" },
            "…or pick an existing story from the sidebar.")
        : null));
    applySceneMood("");
    return;
  }

  $("#chatname").textContent = S.chat.chat.name;

  // Frame-filtered: each frame is its own independent thread with its
  // own turn history -- see S.currentFrameId. A frameless chat (the
  // overwhelmingly common case) has every turn's frame_id === null,
  // so this filter is a no-op for it.
  const frameTurns = S.chat.turns.filter(t => (t.frame_id ?? null) === S.currentFrameId);

  const last = frameTurns[frameTurns.length - 1];
  applySceneMood(last ? last.prose : "");

  const turnEntries = [];

  for (const t of frameTurns) {
    const isLast = last && t.id === last.id;
    const d = el("div", {
      class: "turn" + (t.stale ? " stale" : "")
    });

    if (t.player_input) {
      d.append(el("div", { class: "pin" }, t.player_input));
    }

    d.append(el("div", { class: "prose" }, t.prose || "…"));

    const btns = el("div", { class: "tbtns" },
      el("button", {
        title: "Pipeline",
        onclick: () => openPipeline(t.id)
      }, "📖"),
      el("button", {
        title: "Edit input",
        onclick: () => editTurnInput(t)
      }, "✏"),
      el("button", {
        title: "Edit narration",
        onclick: () => editTurnProse(t)
      }, "📝"),
      el("button", {
        title: "Branch here",
        onclick: () => branchTurn(t.id)
      }, "⎇"));

    if (isLast) {
      btns.append(
        el("button", {
          title: "Reroll",
          onclick: () => rerollTurn(t.id)
        }, "🔁"),
        el("button", {
          title: "Delete",
          onclick: async event => {
            if (!await confirmModal("Delete last turn?", { danger: true, confirmLabel: "Delete" })) return;
            await buttonTask(
              event.currentTarget,
              "…",
              async () => {
                await api("DELETE", "/api/turns/" + t.id);
                await openChat(S.chatId);
              }
            );
          }
        }, "✕"));
    }

    d.append(btns);
    M.append(d);
    turnEntries.push({ el: d, prose: t.prose || "" });
  }

  M.scrollTop = M.scrollHeight;
  observeSceneMood(M, turnEntries);
}

function branchTurn(tid) {
  backgroundTask(
    "Creating story branch",
    () => api("POST", `/api/turns/${tid}/branch`),
    {
      closeModal: false,
      onSuccess: async chat => {
        await boot();
        await openChat(chat.id);
      },
      successMessage: "Story branch created.",
      errorPrefix: "Branching failed"
    }
  );
}

async function editTurnInput(t) {
  const nv = await promptModal("Edit player input:", t.player_input);
  if (nv == null) return;
  const r = await api("PUT", "/api/turns/" + t.id + "/input",
    { input: nv });
  if (r.latest && await confirmModal(
    "Recompute this turn now? This restores world state, memories, and "
    + "lorebooks back to how they were at the start of this turn -- "
    + "including any changes you've made since."
  )) {
    runReroll(t.id);
  } else {
    await openChat(S.chatId);
  }
}

function editTurnProse(t) {
  const ta = el("textarea", { style: "width:100%;height:260px" }, t.prose || "");
  modal("Edit narration", b => b.append(
    el("div", { class: "small dim", style: "margin-bottom:8px" },
      "Changes only what's shown for this beat — the events, world state, "
      + "and memory already recorded from it stay exactly as they were."),
    ta,
    el("div", { class: "row", style: "margin-top:8px" },
      el("button", { class: "primary", onclick: async () => {
        await api("PUT", `/api/turns/${t.id}/prose`, { prose: ta.value });
        closeModal();
        await openChat(S.chatId);
      } }, "Save"))));
}

function liveReset() {
  const L = $("#live");
  L.innerHTML = "";
  L.classList.toggle("hidden", !$("#streamtgl").checked);
}

// liveReset() only sets #live's visibility once, at the start of a turn --
// toggling "show technical detail" mid-run had no effect until the next
// turn started, even though step content was already being written into
// #live the whole time. Keep visibility in sync with the checkbox at any
// moment, not just at turn start.
$("#streamtgl").addEventListener("change", () => {
  $("#live").classList.toggle("hidden", !$("#streamtgl").checked);
});

// Plain-language phase names for the always-visible progress indicator.
// The technical step labels (e.g. "Director · resolve") still show in
// the detailed log below when "show technical detail" is on; this is the
// friendly-by-default view so a long-running turn never looks like nothing
// is happening, without requiring anyone to know what "perception_outcome"
// means.
const FRIENDLY_STEP_LABELS = {
  director_establish: "Setting the scene",
  director_interpret: "Reading what you did",
  mapping_stage: "Working out the surroundings",
  mapping_quick: "Checking the surroundings",
  perception_establish: "Working out what you notice",
  perception_act: "Working out who notices",
  reaction_loop: "Characters reacting",
  interaction_loop: "Characters responding",
  director_resolve: "Deciding what happens",
  perception_outcome: "Working out what everyone just saw",
  narrator: "Writing the scene",
  commit: "Saving the story",
};

function friendlyPhase(key, label) {
  if (FRIENDLY_STEP_LABELS[key]) return FRIENDLY_STEP_LABELS[key];
  if (String(key).startsWith("character:")) {
    const name = String(label || "").replace(/^Character\s*·\s*/, "").trim();
    return (name || "A character") + " is deciding what to do";
  }
  return label || "Working…";
}

let _turnStatusTimer = null;
let _turnStatusStart = 0;

function turnStatusStart() {
  const bar = $("#turnstatus");
  bar.classList.remove("hidden");
  _turnStatusStart = Date.now();
  $("#turnstatus-phase").textContent = "Getting started…";
  $("#turnstatus-elapsed").textContent = "";
  clearInterval(_turnStatusTimer);
  _turnStatusTimer = setInterval(() => {
    $("#turnstatus-elapsed").textContent = elapsedLabel(_turnStatusStart);
  }, 1000);
}

function turnStatusSet(key, label) {
  $("#turnstatus-phase").textContent = friendlyPhase(key, label);
}

function turnStatusStop() {
  $("#turnstatus").classList.add("hidden");
  clearInterval(_turnStatusTimer);
  _turnStatusTimer = null;
}

function liveStep(key, label) {
  const L = $("#live");
  const sid = safeId(key);
  L.append(el("div", { class: "lk", id: "lk-" + sid },
    "▸ " + label));
  L.append(el("pre", { id: "lt-" + sid }));
  L.scrollTop = L.scrollHeight;
}

function handleEvt(ev) {
  if (ev.type === "step_start") {
    liveStep(ev.key, ev.label);
    turnStatusSet(ev.key, ev.label);
  } else if (ev.type === "token") {
    const p = document.getElementById("lt-" + safeId(ev.key));
    if (p && $("#streamtgl").checked) {
      p.textContent += ev.delta;
      $("#live").scrollTop = $("#live").scrollHeight;
    }
  } else if (ev.type === "generation_reset") {
    const pre = document.getElementById(
      "lt-" + safeId(ev.key)
    );

    if (pre) {
      pre.textContent = "";
    }

    const reason = ev.reason
      ? ` (${ev.reason})`
      : "";

    toast(
      `Retrying ${ev.key} with another attempt or model${reason}.`,
      "warn",
      5000
    );
  } else if (ev.type === "step") {
    const h = document.getElementById("lk-" + safeId(ev.key));
    if (h) h.textContent = "✓ " + ev.label;
  } else if (ev.type === "error") {
    toast("Pipeline error: " + ev.error, "err", 9000);
  } else if (ev.type === "aborted") {
    toast("Generation stopped.", "warn");
  }
}

async function runStream(url, body) {
  if (S.busy) return;
  S.busy = true;
  $("#send").disabled = true;
  $("#stop").classList.remove("hidden");
  liveReset();
  turnStatusStart();

  try {
    await streamPost(url, body, handleEvt);
  } catch (e) {
    toast("Pipeline failed: " + e.message, "err", 9000);
  } finally {
    S.busy = false;
    $("#send").disabled = false;
    $("#stop").classList.add("hidden");
    $("#live").classList.add("hidden");
    turnStatusStop();
    if (S.chatId) {
      try {
        await openChat(S.chatId);
      } catch (e) {
        toast("Could not refresh story.", "err");
      }
    }
  }
}

// Rerolling/resuming/rerunning-from-a-stage all restore world/memory/lore
// state back to a snapshot taken at the START of this turn -- so anything
// changed since this turn originally committed (a manual world-state fix,
// a lorebook edit, a character added to the cast) gets silently reverted
// along with it. There's no diffing to preserve just the deliberate
// changes, so the honest fix is warning before it happens rather than
// letting it happen invisibly.
function confirmCheckpointRestore() {
  return confirmModal(
    "This restores world state, memories, and lorebooks back to how they "
    + "were at the start of this turn -- including any changes you've made "
    + "since (world-state edits, lorebook edits, characters added to the "
    + "cast). Continue?",
    { confirmLabel: "Continue" }
  );
}

function runReroll(tid) {
  return runStream(`/api/turns/${tid}/reroll`, {});
}

async function rerollTurn(tid) {
  if (!await confirmCheckpointRestore()) return;
  runReroll(tid);
}

async function exportChat(id) {
  try {
    const d = await api("GET", `/api/chats/${id}/export`);
    downloadJSON(
      d,
      (d.chat.name || "story")
        .replace(/[^a-z0-9_-]/gi, "_") + ".json"
    );
    toast("Story exported.", "ok");
  } catch (e) {
    toast("Export failed: " + e.message, "err");
  }
}

function importChatModal() {
  let fileContent = null;
  const status = el("div", {
    class: "small dim",
    style: "margin-top:8px"
  }, "No file selected");

  const fileIn = el("input", {
    type: "file",
    accept: ".json,application/json",
    style: "display:none"
  });

  const drop = el("div", {
    class: "filedrop",
    onclick: () => fileIn.click()
  }, "Choose a story export",
    el("div", {
      class: "small",
      style: "margin-top:5px"
    }, "Turns, pipeline variants, memories, summaries, "
      + "lorebooks and world state"));

  fileIn.onchange = () => {
    const f = fileIn.files[0];
    if (!f) return;
    status.textContent = "Reading " + f.name + "…";
    status.className = "small dim";
    const r = new FileReader();
    r.onload = () => {
      try {
        fileContent = JSON.parse(r.result);
        status.textContent = "Loaded " + f.name + " ✓";
        status.className = "small";
      } catch (e) {
        fileContent = null;
        status.textContent = "Invalid JSON: " + e.message;
        status.className = "small err";
      }
    };
    r.readAsText(f);
  };

  modal("Import story", b => {
    b.append(drop, fileIn, status,
      el("div", {
        class: "small dim",
        style: "margin-top:9px"
      }, "A new story will be created. Referenced characters "
        + "and personas must already exist or be embedded "
        + "in the archive."),
      el("div", {
        class: "row",
        style: "margin-top:12px"
      },
        el("button", {
          class: "primary",
          onclick: () => {
            if (!fileContent) {
              toast("Choose a valid story JSON file first.", "warn");
              return;
            }
            backgroundTask("Importing story",
              () => api("POST", "/api/chats/import",
                { data: fileContent }),
              {
                onSuccess: async c => {
                  await boot();
                  await openChat(c.id);
                },
                successMessage: "Story imported.",
                errorPrefix: "Story import failed"
              });
          }
        }, "Import")));
  });
}

// ---- Pipeline drawer ----
async function openPipeline(tid) {
  const D = $("#drawer");
  D.classList.remove("hidden");
  D.innerHTML = "";

  const p = await api(
    "GET",
    `/api/turns/${tid}/pipeline`
  );

  const headerRow = el(
    "div",
    { class: "row" },
    el("b", {}, "Pipeline"),
    p.resumable
      ? el(
          "span",
          { class: "badge warn" },
          `next: ${p.resume_key}`
        )
      : null,
    el("span", { class: "spacer" }),
    p.editable && p.resumable
      ? el(
          "button",
          {
            class: "primary",
            title:
              "Continue from the first incomplete or stale "
              + "step without regenerating valid earlier outputs",
            onclick: async event => {
              if (!await confirmCheckpointRestore()) return;
              await buttonTask(
                event.currentTarget,
                "Resuming…",
                async () => {
                  await runStream(
                    `/api/turns/${tid}/resume`,
                    {}
                  );
                  await openPipeline(tid);
                }
              );
            }
          },
          "▶ Resume"
        )
      : null,
    el(
      "button",
      {
        title: "Close pipeline",
        onclick: () => D.classList.add("hidden")
      },
      "✕"
    )
  );

  D.append(headerRow);

  for (const s of p.steps) {
    const variants = s.variants || [];
    const activeIndex = variants.findIndex(
      variant => variant.active
    );
    let cur = activeIndex >= 0
      ? activeIndex
      : Math.max(0, variants.length - 1);

    const pre = el("pre", {}, "");
    const cnt = el(
      "span",
      { class: "badge" },
      variants.length
        ? `${cur + 1}/${variants.length}`
        : "0/0"
    );

    const show = index => {
      if (!variants.length) {
        cur = 0;
        cnt.textContent = "0/0";
        pre.textContent = "(no active variant)";
        return;
      }

      cur = Math.max(
        0,
        Math.min(index, variants.length - 1)
      );
      cnt.textContent =
        `${cur + 1}/${variants.length}`;

      const variant = variants[cur];

      try {
        pre.textContent = JSON.stringify(
          JSON.parse(variant.content),
          null,
          2
        );
      } catch (error) {
        pre.textContent = variant.content;
      }
    };

    const controls = el(
      "div",
      { class: "row" },
      el(
        "button",
        {
          disabled: !variants.length,
          onclick: () => show(cur - 1)
        },
        "◀"
      ),
      cnt,
      el(
        "button",
        {
          disabled: !variants.length,
          onclick: () => show(cur + 1)
        },
        "▶"
      )
    );

    if (p.editable && variants.length) {
      controls.append(
        el(
          "button",
          {
            title: "Activate",
            onclick: async () => {
              await api(
                "POST",
                `/api/steps/${s.id}/activate`,
                {
                  variant_id: variants[cur].id
                }
              );
              await openPipeline(tid);
            }
          },
          "✔ use"
        )
      );
    }

    if (p.editable) {
      controls.append(
        el(
          "button",
          {
            title:
              "Generate a new variant for only this step",
            onclick: async () => {
              // Every step's own reroll restores the checkpoint too when
              // the step IS commit -- everything else leaves world/memory
              // state alone (only that one step's saved content changes).
              if (s.key === "commit" && !await confirmCheckpointRestore()) return;
              await runStream(
                `/api/steps/${s.id}/reroll`,
                {}
              );
              await openPipeline(tid);
            }
          },
          "🔁 Reroll only"
        ),
        el(
          "button",
          {
            title:
              "Recompute this step and finish the workflow",
            onclick: async () => {
              if (!await confirmCheckpointRestore()) return;
              await runStream(
                `/api/turns/${tid}/rerun`,
                { from_key: s.key }
              );
              await openPipeline(tid);
            }
          },
          "▶ Run from here"
        )
      );
    }

    if (p.editable && variants.length) {
      controls.append(
        el(
          "button",
          {
            title: "Edit JSON",
            onclick: () => {
              const ta = el(
                "textarea",
                {
                  style:
                    "width:100%;height:300px"
                },
                pre.textContent
              );

              modal(
                "Edit step — " + s.label,
                body => {
                  body.append(
                    ta,
                    el(
                      "div",
                      {
                        class: "row",
                        style: "margin-top:8px"
                      },
                      el(
                        "button",
                        {
                          onclick: async () => {
                            let content;

                            try {
                              content = JSON.parse(
                                ta.value
                              );
                            } catch (error) {
                              toast(
                                "Invalid JSON",
                                "err"
                              );
                              return;
                            }

                            await api(
                              "POST",
                              `/api/steps/${s.id}/edit`,
                              { content }
                            );

                            closeModal();
                            await openPipeline(tid);
                          }
                        },
                        "Save"
                      )
                    )
                  );
                }
              );
            }
          },
          "✎"
        )
      );
    }

    const box = el(
      "div",
      {
        class:
          "step"
          + (s.stale ? " stale" : "")
      },
      el(
        "h4",
        {},
        s.label
          + (s.stale ? "  (stale)" : "")
      ),
      controls,
      pre
    );

    show(cur);
    D.append(box);
  }
}

// ---- Relationship viewer ----
// Surfaces the same trust/familiarity/emotional_valence/fear graph the
// character agent itself reads each turn -- this is a read-only window
// onto existing machinery, not a new computed feature.
function relMeter(label, value, centered) {
  const v = Number(value) || 0;
  const pct = centered
    ? Math.max(0, Math.min(100, (v + 1) / 2 * 100))
    : Math.max(0, Math.min(100, v * 100));
  const fillColor = centered && v < 0 ? "var(--err)" : "var(--acc)";
  return el("div", { style: "margin:4px 0" },
    el("div", { class: "row", style: "justify-content:space-between;font-size:11px" },
      el("span", { class: "dim" }, label), el("span", {}, v.toFixed(2))),
    el("div", { style: "background:var(--bg);border-radius:4px;height:6px;position:relative;overflow:hidden" },
      centered ? el("div", { style: "position:absolute;left:50%;top:0;bottom:0;width:1px;background:var(--bd)" }) : null,
      el("div", { style: `height:100%;width:${pct}%;background:${fillColor};border-radius:4px` })));
}

async function relationshipModal(p) {
  modal("Relationships — " + p.name, async body => {
    body.innerHTML = "";
    body.append(loadingBlock("Loading…"));
    let rels;
    try {
      rels = await api("GET", `/api/chats/${S.chatId}/characters/${p.id}/relationships`);
    } catch (e) {
      body.innerHTML = "";
      body.append(el("div", { class: "dim" }, "Could not load relationships: " + e.message));
      return;
    }
    body.innerHTML = "";
    const names = Object.keys(rels || {});
    if (!names.length) {
      body.append(emptyState(p.name + " hasn't formed any tracked opinions of anyone yet."));
      return;
    }
    body.append(el("div", { class: "small dim", style: "margin-bottom:10px" },
      "How " + p.name + " currently feels about each character they've interacted with — read-only, drawn from the same data the character agent itself sees each turn."));
    for (const name of names) {
      const r = rels[name];
      body.append(el("div", { class: "card" },
        el("div", { class: "row" },
          el("b", {}, name.replace(/_/g, " ")),
          el("span", { class: "spacer" }),
          r.last_interaction_turn != null
            ? el("span", { class: "badge" }, "last: turn " + r.last_interaction_turn)
            : null),
        relMeter("trust", r.trust, true),
        relMeter("familiarity", r.familiarity, false),
        relMeter("warmth (emotional valence)", r.emotional_valence, true),
        relMeter("fear", r.fear, false),
        (r.salient_event || r.notes)
          ? el("div", { class: "small dim", style: "margin-top:4px" },
              r.notes || ("last shift triggered by event " + r.salient_event))
          : null));
    }
  });
}

// ---- Memory browser ----
function memModal(p) {
  S.memoryCharacter = p;
  modal("Memory browser — " + p.name, body => {
    const layout = el("div", { class: "memory-layout" });
    const sidebar = el("div", { class: "memory-sidebar" });
    const main = el("div", { class: "memory-main" });
    const summaryBox = el("div", { class: "memory-summary" },
      loadingBlock("Loading summary…"));
    const searchInput = el("input", {
      type: "search",
      placeholder: "Recall a name, phrase, place, promise…"
    });
    const categorySelect = el("select", {},
      el("option", { value: "" }, "All categories"),
      ...MEM_CATS.map(c => el("option", { value: c }, c)));
    const provenanceSelect = el("select", {},
      el("option", { value: "" }, "All sources"),
      ...MEM_PROV.map(s => el("option", { value: s }, s)));
    const archivedToggle = el("input", { type: "checkbox" });
    const sortSelect = el("select", {},
      el("option", { value: "newest" }, "Newest first"),
      el("option", { value: "oldest" }, "Oldest first"),
      el("option", { value: "salience" }, "Highest salience"),
      el("option", { value: "relevance" }, "Highest relevance"));
    const searchButton = el("button", {
      class: "primary",
      onclick: () => runMemorySearch()
    }, "Recall");
    const clearButton = el("button", {
      onclick: () => {
        searchInput.value = "";
        layout._mode = "browse";
        sortSelect.value = "newest";
        loadMemoryBrowse();
      }
    }, "Clear");
    const addButton = el("button", {
      onclick: () => showNewMemoryForm(layout)
    }, "+ Memory");
    const exportMemButton = el("button", {
      title: "Download this character's memories as a file",
      onclick: () => exportCharacterMemories()
    }, "⤓ Export");
    const importMemButton = el("button", {
      title: "Add memories from a previously exported file",
      onclick: () => importCharacterMemoriesModal()
    }, "⤒ Import");
    const contextButton = el("button", {
      onclick: () => previewMemoryContext()
    }, "Preview context");
    const consolidateButton = el("button", {
      onclick: () => consolidateMemories()
    }, "✨ Consolidate");

    const toolbar = el("div", { class: "toolbar" },
      searchInput, searchButton, clearButton,
      categorySelect, provenanceSelect, sortSelect,
      el("label", { class: "tgl" },
        archivedToggle, " archived"),
      addButton, exportMemButton, importMemButton);

    const resultLabel = el("div", { class: "small dim" });
    const listBox = el("div", { class: "memory-list" },
      loadingBlock("Loading memories…"));

    // Consolidate controls on top, autobiography summary directly beneath —
    // both wrapped in one sticky block so they stay scroll-locked in view
    // while the memory list in the main column scrolls. (Previously the
    // summary alone was sticky and, sitting first, painted over the
    // consolidate card as it scrolled up beneath it.)
    const consolidateCard = el("div", { class: "card memory-consolidate" },
      el("div", { class: "section-title", style: "margin-top:0" },
        "Memory tools"),
      el("div", { class: "row" },
        consolidateButton, contextButton),
      el("div", {
        class: "small dim",
        style: "margin-top:8px"
      }, "Consolidation updates the character's subjective "
        + "long-term summary. Context preview shows what the "
        + "agent receives."));
    sidebar.append(el("div", { class: "memory-sidebar-sticky" },
      consolidateCard, summaryBox));

    main.append(toolbar, resultLabel, listBox);
    layout.append(sidebar, main);
    body.append(layout);

    layout._memories = [];
    layout._summary = {};
    layout._mode = "browse";

    searchInput.addEventListener("keydown", e => {
      if (e.key === "Enter") {
        e.preventDefault();
        runMemorySearch();
      }
    });

    categorySelect.onchange = () => {
      layout._mode = "browse";
      loadMemoryBrowse();
    };
    provenanceSelect.onchange = () => {
      layout._mode = "browse";
      loadMemoryBrowse();
    };
    archivedToggle.onchange = () => {
      layout._mode = "browse";
      loadMemoryBrowse();
    };
    sortSelect.onchange = () => renderMemoryList();

    loadMemoryBrowse();
  }, { wide: true });
}

async function exportCharacterMemories() {
  const p = S.memoryCharacter;
  if (!p) return;
  try {
    const d = await api("GET", `/api/chats/${S.chatId}/characters/${p.id}/memories/export`);
    downloadJSON(d, (p.name || "character").replace(/[^a-z0-9_-]/gi, "_") + "_memories.json");
    toast("Memories exported.", "ok");
  } catch (e) {
    toast("Export failed: " + e.message, "err");
  }
}

function importCharacterMemoriesModal() {
  const p = S.memoryCharacter;
  if (!p) return;
  let fileContent = null;
  const status = el("div", { class: "small dim", style: "margin-top:8px" }, "No file selected");
  const fileIn = el("input", { type: "file", accept: ".json,application/json", style: "display:none" });
  const drop = el("div", { class: "filedrop", onclick: () => fileIn.click() },
    "Choose a memories export",
    el("div", { class: "small", style: "margin-top:5px" },
      "Adds to " + p.name + "'s existing memories -- never replaces or deletes anything."));

  fileIn.onchange = () => {
    const f = fileIn.files[0];
    if (!f) return;
    status.textContent = "Reading " + f.name + "…";
    status.className = "small dim";
    const r = new FileReader();
    r.onload = () => {
      try {
        const parsed = JSON.parse(r.result);
        if (!Array.isArray(parsed.memories)) throw new Error("no memories array found");
        fileContent = parsed;
        status.textContent = `${f.name} — ${parsed.memories.length} memories`;
      } catch (e) {
        fileContent = null;
        status.textContent = "Could not read this file: " + e.message;
        status.className = "small err";
      }
    };
    r.readAsText(f);
  };

  modal("Import memories — " + p.name, b => {
    b.append(drop, fileIn, status,
      el("div", { class: "row", style: "margin-top:12px" },
        el("button", {
          class: "primary",
          onclick: async () => {
            if (!fileContent) {
              toast("Choose a valid memories JSON file first.", "warn");
              return;
            }
            try {
              const r = await api("POST",
                `/api/chats/${S.chatId}/characters/${p.id}/memories/import`,
                { memories: fileContent.memories });
              toast(`Imported ${r.imported} memories.`, "ok");
              closeModal();
              loadMemoryBrowse();
            } catch (e) {
              toast("Import failed: " + e.message, "err");
            }
          }
        }, "Import")));
  });
}

function memQS(vals) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(vals)) {
    if (v !== undefined && v !== null && v !== "") {
      p.set(k, String(v));
    }
  }
  const q = p.toString();
  return q ? "?" + q : "";
}

function memCharId() {
  return S.memoryCharacter?.id || null;
}

async function loadMemoryBrowse() {
  const layout = $("#modalbody").querySelector(".memory-layout");
  if (!layout) return;
  const cid = memCharId();
  if (!cid) return;
  const ui = getMemUI();
  if (!ui) return;

  ui.listBox.innerHTML = "";
  ui.listBox.append(loadingBlock("Loading memories…"));
  ui.resultLabel.textContent = "";

  try {
    const r = await api("GET",
      `/api/chats/${S.chatId}/characters/${cid}/memories`
      + memQS({
        include_archived: ui.archivedToggle.checked,
        category: ui.categorySelect.value,
        provenance: ui.provenanceSelect.value,
        limit: 1000
      }));

    layout._memories = r.memories || [];
    layout._summary = r.summary || {};
    layout._mode = "browse";
    renderMemorySummary();
    renderMemoryList();
  } catch (e) {
    ui.listBox.innerHTML = "";
    ui.listBox.append(
      emptyState("Load error: " + e.message));
    toast("Could not load memories.", "err");
  }
}

function getMemUI() {
  const layout = $("#modalbody")
    .querySelector(".memory-layout");
  if (!layout) return null;
  return {
    layout,
    summaryBox: layout.querySelector(".memory-summary"),
    listBox: layout.querySelector(".memory-list"),
    resultLabel: layout.querySelector(".memory-main > .small.dim"),
    searchInput: layout.querySelector('input[type="search"]'),
    categorySelect: layout.querySelectorAll(".toolbar select")[0],
    provenanceSelect: layout.querySelectorAll(".toolbar select")[1],
    sortSelect: layout.querySelectorAll(".toolbar select")[2],
    archivedToggle: layout.querySelector(
      '.toolbar input[type="checkbox"]')
  };
}

function renderMemorySummary() {
  const ui = getMemUI();
  if (!ui) return;
  const s = ui.layout._summary || {};
  ui.summaryBox.innerHTML = "";
  ui.summaryBox.append(
    el("div", {
      class: "section-title",
      style: "margin-top:0"
    }, "Long-term autobiographical summary"),
    el("div", { class: "memory-summary-text" },
      s.summary || "No autobiographical summary yet."),
    (s.key_phrases || []).length
      ? el("div", { style: "margin-top:9px" },
          el("div", { class: "small dim" }, "Retrieval cues"),
          el("div", { class: "mem-scroll" },
            ...(s.key_phrases || []).map(p =>
              el("span", { class: "chip" }, p))))
      : null,
    (s.unresolved_threads || []).length
      ? el("div", { style: "margin-top:9px" },
          el("div", { class: "small dim" }, "Unresolved threads"),
          el("div", { class: "mem-scroll" },
            ...(s.unresolved_threads || []).map(t =>
              el("div", {
                class: "small",
                style: "margin-top:4px"
              }, "• " + t))))
      : null,
    el("div", {
      class: "small dim",
      style: "margin-top:10px"
    }, s.updated
      ? "Summary through turn "
        + (s.end_turn_idx ?? 0)
      : "Not consolidated"));
}

function sortedMems(mems, sort) {
  const c = [...(mems || [])];
  if (sort === "oldest") {
    c.sort((a, b) =>
      (a.turn_idx ?? 9e15) - (b.turn_idx ?? 9e15)
      || a.id - b.id);
  } else if (sort === "salience") {
    c.sort((a, b) =>
      (b.salience ?? 0) - (a.salience ?? 0));
  } else if (sort === "relevance") {
    c.sort((a, b) =>
      (b.score ?? 0) - (a.score ?? 0));
  } else {
    c.sort((a, b) =>
      (b.turn_idx ?? -1) - (a.turn_idx ?? -1)
      || b.id - a.id);
  }
  return c;
}

function renderMemoryList() {
  const ui = getMemUI();
  if (!ui) return;
  const mems = sortedMems(
    ui.layout._memories || [],
    ui.sortSelect.value
  );
  ui.listBox.innerHTML = "";
  const mode = ui.layout._mode || "browse";
  ui.resultLabel.textContent =
    `${mems.length} `
    + (mems.length === 1 ? "memory" : "memories")
    + (mode === "search" ? " recalled" : "");

  if (!mems.length) {
    ui.listBox.append(emptyState(
      mode === "search"
        ? "No memory matched those cues."
        : "No memories match these filters."));
    return;
  }

  let lastTurn = Symbol("none");
  for (const m of mems) {
    const t = m.turn_idx ?? null;
    if (t !== lastTurn) {
      ui.listBox.append(el("div",
        { class: "memory-turn-group" },
        t === null ? "Unplaced" : "Turn " + t));
      lastTurn = t;
    }
    ui.listBox.append(memoryCard(m));
  }
}

function memoryCard(m) {
  const cat = m.category || m.kind || "episode";
  const prov = m.provenance || "witnessed";
  const gist = m.gist || m.content || "(empty)";

  const catSel = el("select", {},
    MEM_CATS.map(c => el("option", {
      value: c,
      ...(c === cat ? { selected: "" } : {})
    }, c)));
  const provSel = el("select", {},
    MEM_PROV.map(p => el("option", {
      value: p,
      ...(p === prov ? { selected: "" } : {})
    }, p)));
  const gistIn = el("textarea", { rows: "2" }, m.gist || "");
  const detIn = el("textarea", {
    rows: "5",
    class: "memory-details"
  }, m.content || "");
  const phIn = el("input", {
    value: (m.key_phrases || []).join(", "),
    placeholder: "key phrases"
  });
  const enIn = el("input", {
    value: (m.entities || []).join(", "),
    placeholder: "entities"
  });
  const locIn = el("input", {
    value: m.location || "",
    placeholder: "location"
  });
  const emoIn = el("input", {
    value: m.emotional_context || "",
    placeholder: "emotional context"
  });
  const salIn = el("input", {
    type: "number", min: "0", max: "1", step: "0.05",
    value: m.salience ?? 0.5
  });
  const conIn = el("input", {
    type: "number", min: "0", max: "1", step: "0.05",
    value: m.confidence ?? 1
  });
  const valIn = el("input", {
    type: "number", min: "-1", max: "1", step: "0.05",
    value: m.valence ?? 0
  });
  const aroIn = el("input", {
    type: "number", min: "0", max: "1", step: "0.05",
    value: m.arousal ?? 0
  });
  const archIn = el("input", {
    type: "checkbox",
    ...(m.archived ? { checked: "" } : {})
  });

  const reasons = m.retrieval_reasons || [];

  const saveBtn = el("button", {
    class: "primary",
    onclick: async e => {
      await buttonTask(e.currentTarget, "Saving…", async () => {
        await api("PUT", "/api/memories/" + m.id, {
          content: detIn.value,
          gist: gistIn.value,
          category: catSel.value,
          kind: catSel.value === "episode"
            ? "episodic" : catSel.value,
          provenance: provSel.value,
          key_phrases: splitCL(phIn.value),
          entities: splitCL(enIn.value),
          location: locIn.value,
          emotional_context: emoIn.value,
          salience: numOr(salIn.value, 0.5),
          confidence: numOr(conIn.value, 1),
          valence: numOr(valIn.value, 0),
          arousal: numOr(aroIn.value, 0),
          archived: archIn.checked
        });
        toast("Memory saved.", "ok");
        await reloadMemView();
      });
    }
  }, "Save");

  const delBtn = el("button", {
    class: "danger",
    onclick: async () => {
      if (!await confirmModal("Permanently delete this memory?", { danger: true, confirmLabel: "Delete" })) return;
      try {
        await api("DELETE", "/api/memories/" + m.id);
        toast("Memory deleted.", "ok");
        await reloadMemView();
      } catch (e) {
        toast("Could not delete: " + e.message, "err");
      }
    }
  }, "Delete");

  const archBtn = el("button", {
    onclick: async () => {
      try {
        await api("PUT", "/api/memories/" + m.id,
          { archived: !m.archived });
        toast(m.archived
          ? "Memory restored."
          : "Memory archived.", "ok");
        await reloadMemView();
      } catch (e) {
        toast("Could not update: " + e.message, "err");
      }
    }
  }, m.archived ? "Restore" : "Archive");

  return el("details", {
    class: "memory-card card"
      + (m.archived ? " archived" : "")
  },
    el("summary", {},
      el("span", { class: "badge" }, cat),
      el("span", { class: "badge" }, prov),
      el("span", {
        class: "memory-gist-line",
        title: gist
      }, gist),
      m.score !== undefined
        ? el("span", { class: "memory-score" },
            Number(m.score).toFixed(3))
        : el("span", { class: "small dim" },
            "s " + Number(m.salience ?? 0).toFixed(2))),
    reasons.length
      ? el("div", { style: "margin-top:9px" },
          el("div", { class: "small dim" }, "Why recalled"),
          ...reasons.map(r =>
            el("span", { class: "retrieval-reason" }, r)))
      : null,
    el("div", { class: "memory-fields" },
      fieldWrap("Category", catSel),
      fieldWrap("Source provenance", provSel),
      fieldWrap("Gist", gistIn, "full"),
      fieldWrap("Vivid details", detIn, "full"),
      fieldWrap("Key phrases", phIn, "full"),
      fieldWrap("Entities", enIn, "full"),
      fieldWrap("Location", locIn),
      fieldWrap("Emotional context", emoIn),
      fieldWrap("Salience", salIn),
      fieldWrap("Confidence", conIn),
      fieldWrap("Valence", valIn),
      fieldWrap("Arousal", aroIn),
      el("div", { class: "full row" },
        el("label", { class: "tgl" },
          archIn, " archived"),
        m.event_key
          ? el("span", { class: "small dim" },
              "key: " + m.event_key)
          : null),
      el("div", { class: "full row" },
        saveBtn, archBtn, delBtn,
        el("span", { class: "spacer" }),
        el("span", { class: "small dim" },
          `ID ${m.id} · accessed ${m.access_count || 0}×`))));
}

function fieldWrap(label, node, className = "") {
  return el("div", { class: className },
    el("label", {}, label), node);
}

async function reloadMemView() {
  const ui = getMemUI();
  if (!ui) return;
  if (ui.layout._mode === "search"
    && ui.searchInput.value.trim()) {
    await runMemorySearch();
  } else {
    await loadMemoryBrowse();
  }
}

async function runMemorySearch() {
  const ui = getMemUI();
  if (!ui) return;
  const cid = memCharId();
  if (!cid) return;
  const q = ui.searchInput.value.trim();
  if (!q) {
    ui.layout._mode = "browse";
    await loadMemoryBrowse();
    return;
  }

  ui.listBox.innerHTML = "";
  ui.listBox.append(loadingBlock("Searching memory…"));

  try {
    const r = await api("GET",
      `/api/chats/${S.chatId}/characters/${cid}/memories/search`
      + memQS({ query: q, limit: 30 }));
    ui.layout._memories = r.results || [];
    ui.layout._mode = "search";
    ui.sortSelect.value = "relevance";
    renderMemoryList();
  } catch (e) {
    ui.listBox.innerHTML = "";
    ui.listBox.append(
      emptyState("Search error: " + e.message));
    toast("Search failed.", "err");
  }
}

function showNewMemoryForm(layout) {
  const existing = layout.querySelector(".memory-add");
  if (existing) {
    existing.scrollIntoView({
      behavior: "smooth",
      block: "center"
    });
    return;
  }

  const gist = el("input", { placeholder: "Concise gist" });
  const det = el("textarea", {
    rows: "4",
    placeholder: "What this character remembers…"
  });
  const cat = el("select", {},
    MEM_CATS.map(c => el("option", {
      value: c,
      ...(c === "episode" ? { selected: "" } : {})
    }, c)));
  const prov = el("select", {},
    MEM_PROV.map(p => el("option", {
      value: p,
      ...(p === "told" ? { selected: "" } : {})
    }, p)));
  const ph = el("input", {
    placeholder: "key phrases, comma-separated"
  });
  const en = el("input", {
    placeholder: "entities, comma-separated"
  });
  const loc = el("input", { placeholder: "location" });
  const sal = el("input", {
    type: "number", min: "0", max: "1", step: "0.05",
    value: "0.5"
  });

  const form = el("div", { class: "memory-add" },
    el("div", {
      class: "section-title",
      style: "margin-top:0"
    }, "Add memory"),
    el("div", { class: "memory-fields" },
      fieldWrap("Category", cat),
      fieldWrap("Source provenance", prov),
      fieldWrap("Gist", gist, "full"),
      fieldWrap("Details", det, "full"),
      fieldWrap("Key phrases", ph, "full"),
      fieldWrap("Entities", en, "full"),
      fieldWrap("Location", loc),
      fieldWrap("Salience", sal),
      el("div", { class: "full row" },
        el("button", {
          class: "primary",
          onclick: async e => {
            if (!det.value.trim()) {
              toast("Details cannot be empty.", "warn");
              return;
            }
            await buttonTask(e.currentTarget, "Adding…",
              async () => {
                const cid = memCharId();
                await api("POST",
                  `/api/chats/${S.chatId}/characters/${cid}/memories`,
                  {
                    content: det.value.trim(),
                    gist: gist.value.trim(),
                    category: cat.value,
                    kind: cat.value === "episode"
                      ? "episodic" : cat.value,
                    provenance: prov.value,
                    salience: numOr(sal.value, 0.5),
                    key_phrases: splitCL(ph.value),
                    entities: splitCL(en.value),
                    location: loc.value.trim()
                  });
                toast("Memory added.", "ok");
                await loadMemoryBrowse();
              });
          }
        }, "Add memory"),
        el("button", {
          onclick: () => form.remove()
        }, "Cancel"))));

  const ui = getMemUI();
  if (ui) ui.listBox.prepend(form);
  form.scrollIntoView({
    behavior: "smooth",
    block: "start"
  });
  det.focus();
}

function consolidateMemories() {
  const cid = memCharId();
  if (!cid) return;
  const name = S.memoryCharacter?.name || "character";
  backgroundTask("Consolidating " + name + "'s memory",
    () => api("POST",
      `/api/chats/${S.chatId}/characters/${cid}/memories/consolidate`,
      { archive_old: true }),
    {
      onSuccess: async () => {
        if (S.memoryCharacter)
          await memModal(S.memoryCharacter);
      },
      successMessage: r =>
        `Consolidated ${r?.memory_count || 0} memories.`,
      errorPrefix: "Consolidation failed"
    });
}

async function previewMemoryContext() {
  const ui = getMemUI();
  if (!ui) return;
  const cid = memCharId();
  if (!cid) return;
  const q = ui.searchInput.value.trim();

  const preview = el("div", { class: "memory-preview" },
    loadingBlock("Building context…"));

  modal("Character memory context", b => {
    b.append(
      el("div", {
        class: "row",
        style: "margin-bottom:9px"
      },
        el("button", {
          onclick: () => {
            if (S.memoryCharacter)
              memModal(S.memoryCharacter);
          }
        }, "← Back to browser"),
        el("span", { class: "spacer" }),
        el("span", { class: "small dim" },
          "Exact agent payload")),
      el("div", {
        class: "small dim",
        style: "margin-bottom:9px"
      }, "Tiered memory: working memory, recent "
        + "chronology, recalled old episodes, "
        + "autobiographical summary."),
      preview);
  }, { wide: true });

  try {
    const ctx = await api("GET",
      `/api/chats/${S.chatId}/characters/${cid}/memory-context`
      + memQS({ query: q }));
    preview.innerHTML = "";
    preview.append(el("pre", {},
      JSON.stringify(ctx, null, 2)));
  } catch (e) {
    preview.innerHTML = "";
    preview.append(emptyState("Error: " + e.message));
  }
}

// ---- Private history ----
async function chatPH(p) {
  const d = await api("GET",
    `/api/chats/${S.chatId}/characters/${p.id}/private_history`);
  const ph = phEditor(d.entries, true);
  modal(`Private history (this story) — ${p.name}`, b => {
    b.append(
      el("div", { class: "small dim" },
        "Source: " + d.source
        + ". Saving stores a story-local override."),
      ph.node,
      el("div", {
        class: "row",
        style: "margin-top:8px"
      },
        el("button", {
          class: "primary",
          onclick: async () => {
            await api("PUT",
              `/api/chats/${S.chatId}/characters/${p.id}/private_history`,
              { entries: ph.read() });
            closeModal();
            toast("Private history saved.", "ok");
          }
        }, "Save")));
  });
}

async function personaPH() {
  const d = await api("GET",
    `/api/chats/${S.chatId}/persona_private_history`);
  const ph = phEditor(d.entries, false);
  modal("Persona private history (this story)", b => {
    b.append(
      el("div", { class: "small dim" },
        "Source: " + d.source + "."),
      ph.node,
      el("div", {
        class: "row",
        style: "margin-top:8px"
      },
        el("button", {
          class: "primary",
          onclick: async () => {
            await api("PUT",
              `/api/chats/${S.chatId}/persona_private_history`,
              { entries: ph.read() });
            closeModal();
            toast("Saved.", "ok");
          }
        }, "Save")));
  });
}