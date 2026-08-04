// ---- The turn being read ----
// Tracks which rendered .turn element is currently most visible in #msgs, so
// the backdrop and the ambient sound follow whatever scene the reader is
// actually looking at while scrolling, not just the newest turn. One observer
// and one notion of "the current turn", so the picture and the sound can never
// disagree about which room the reader is in. Recreated on every renderChat()
// since the old DOM nodes it observes get thrown away with M.innerHTML="".
//
// It also drove a keyword-guessed "scene mood" that tinted the page. That is
// gone: it lowercased every turn's prose and ran ~60 substring scans over it
// to pick a colour, and each change wrote `body[data-mood]`, invalidating
// style for the whole document.
let _visibleTurnObserver = null;
// Only the newest story navigation may publish its response. Fetches can
// complete out of order when two sidebar rows are clicked quickly; without a
// sequence guard, the older payload could be assigned to S.chat after S.chatId
// had already moved on to the newer story.
let _chatLoadSeq = 0;

// The story/frame a stream started in is immutable for that run. The reader is
// still free to browse elsewhere while generation continues, but Stop must
// abort the pipeline that is actually running rather than whatever story is
// currently on screen.
let _activeRun = null;

// Also drives the scene backdrop (backdrops.js): the picture behind the
// transcript should be the room of whatever beat the reader is actually
// looking at, which is the same question this observer already answers --
// so it stays one observer and one notion of "the current turn" rather than
// two that can disagree while scrolling.
// Set when a run has just produced a turn, cleared by the first observer pass
// that lands on it. The scene layers read it to tell "the reader is waiting for
// this one" from "the reader is scrolling past it".
let _freshTurnPending = false;

function observeVisibleTurn(msgsEl, turnEntries) {
  if (_visibleTurnObserver) {
    _visibleTurnObserver.disconnect();
    _visibleTurnObserver = null;
  }
  if (!turnEntries.length) return;

  // IntersectionObserver callbacks only report entries whose ratio crossed
  // a threshold since the last check -- not a full snapshot of everything
  // being observed -- so visibility has to be accumulated across calls
  // rather than read fresh each time.
  const ratios = new Map();
  const turnIdByEl = new Map(turnEntries.map(e => [e.el, e.turnId]));
  const newestTurnId = turnEntries[turnEntries.length - 1].turnId;

  _visibleTurnObserver = new IntersectionObserver(entries => {
    for (const entry of entries) {
      // Dropped rather than stored as 0: a zero can never win the comparison
      // below, so keeping it only grows this map to the length of the whole
      // story and makes every later tick scan every turn ever scrolled past.
      if (entry.isIntersecting && entry.intersectionRatio > 0) {
        ratios.set(entry.target, entry.intersectionRatio);
      } else {
        ratios.delete(entry.target);
      }
    }
    let bestEl = null, bestRatio = 0;
    for (const [el, ratio] of ratios) {
      if (ratio > bestRatio) { bestRatio = ratio; bestEl = el; }
    }
    if (bestEl) {
      // A turn the reader just WAITED for is not a turn they scrolled past:
      // its picture and its sound are commissioned immediately, while every
      // other turn has to be dwelt on first. Consumed once, so scrolling away
      // and back afterwards behaves like ordinary reading.
      const fresh = _freshTurnPending && turnIdByEl.get(bestEl) === newestTurnId;
      if (fresh) _freshTurnPending = false;
      // Guarded because backdrops.js is an experimental extra: if it fails to
      // load (or a browser is holding a cached index.html without its script
      // tag), a missing function here would throw inside the observer and
      // take the transcript's own scroll behaviour down with it.
      if (typeof backdropOnVisibleTurn === "function") {
        backdropOnVisibleTurn(turnIdByEl.get(bestEl), { fresh });
      }
      // Same observer, same notion of "the turn being read", so the picture
      // and the sound can never disagree about which room the reader is in.
      if (typeof ambienceOnVisibleTurn === "function") {
        ambienceOnVisibleTurn(turnIdByEl.get(bestEl), { fresh });
      }
    }
  }, { root: msgsEl, threshold: [0, 0.1, 0.25, 0.5, 0.75, 1] });

  for (const { el } of turnEntries) _visibleTurnObserver.observe(el);
}

async function openChat(id) {
  const switching = S.chatId !== id;
  const loadSeq = ++_chatLoadSeq;
  // Clear the outgoing story's condition panel BEFORE the awaits below. It
  // belongs to that story, and leaving it up while the next one loads showed
  // the previous character's bars against the new story's prose. Story-bound
  // dialogs have the same ownership rule: dismiss the whole modal stack before
  // S.chatId can make an old control act on the newly selected story.
  if (switching) {
    closeAllModals();
    window.clearVitalsHud?.();
  }
  S.chatId = id;
  let chat;
  try {
    chat = await api("GET", "/api/chats/" + id);
  } catch (error) {
    // A superseded request failing after a newer navigation succeeded is no
    // longer actionable and must not produce a misleading global error toast.
    if (loadSeq !== _chatLoadSeq || S.chatId !== id) return false;
    throw error;
  }
  if (loadSeq !== _chatLoadSeq || S.chatId !== id) return false;

  S.chat = chat;
  // A genuine story switch starts in that story's present. Ordinary refreshes
  // (turn completion, edit, reroll, delete) preserve the frame the reader was
  // already viewing, unless that frame no longer exists.
  const frameStillExists = (chat.frames || []).some(
    frame => (frame.id ?? null) === S.currentFrameId
  );
  if (switching || !frameStillExists) S.currentFrameId = null;
  renderSide();
  renderChat();
  // Then populate for the story now open -- including the case where it does
  // not track condition at all and the panel simply stays away.
  window.refreshVitalsHud?.();
  // Offered here rather than at boot: opening a story is the moment its own
  // memory bank is about to be read, and the moment the answer is about
  // something the host recognises. `embedding_bank` is null unless this
  // story's memories were embedded by a different model than the live one.
  if (chat.embedding_bank) window.erOfferRebuild?.(id, chat.embedding_bank);
  return true;
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
  if (typeof backdropResetForRender === "function") backdropResetForRender();
  if (typeof ambienceResetForRender === "function") ambienceResetForRender();

  if (!S.chat) {
    $("#chatname").textContent = "No story selected";
    $("#chatname").title = "No story selected";
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
    return;
  }

  $("#chatname").textContent = S.chat.chat.name;
  $("#chatname").title = S.chat.chat.name;

  // Frame-filtered: each frame is its own independent thread with its
  // own turn history -- see S.currentFrameId. A frameless chat (the
  // overwhelmingly common case) has every turn's frame_id === null,
  // so this filter is a no-op for it.
  const frameTurns = S.chat.turns.filter(t => (t.frame_id ?? null) === S.currentFrameId);

  const last = frameTurns[frameTurns.length - 1];

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
      // The rerolls of THIS beat, browsable in place. Rendered empty and
      // filled asynchronously: the count needs a request, and blocking the
      // transcript on it would make every story load wait for a control most
      // turns do not need.
      d.append(el("div", { class: "rerollnav hidden" }));
      _mountRerollNav(t.id, d);
      btns.append(
        el("button", {
          title: "Reroll",
          onclick: () => rerollTurn(t.id)
        }, "🔁"),
        el("button", {
          title: "Delete",
          onclick: async event => {
            // Capture the button NOW: event.currentTarget is reset to null
            // once click dispatch ends, and this handler suspends across
            // `await confirmModal`, so reading it afterward would be null.
            const btn = event.currentTarget;
            if (!await confirmModal("Delete last turn?", { danger: true, confirmLabel: "Delete" })) return;
            await buttonTask(
              btn,
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
    turnEntries.push({ el: d, prose: t.prose || "", turnId: t.id });
  }

  // Explicitly instant. #msgs has scroll-behavior:smooth for the reader's own
  // scrolling and for the scrollIntoView calls further down, but a rebuild
  // leaves scrollTop at 0, so honouring it here ANIMATES from the top of the
  // story to the bottom -- dragging every turn in between through a real
  // layout and paint, which is exactly the work `content-visibility` is here
  // to avoid. The jump is meant to be a jump.
  M.scrollTo({ top: M.scrollHeight, behavior: "instant" });
  // Re-asserted once layout has settled. Turns off screen are skipped by
  // `content-visibility` and contribute an ESTIMATED height until they have
  // been rendered at least once, so the first scrollHeight of a long story is
  // an approximation -- close, but not the bottom.
  requestAnimationFrame(() => {
    M.scrollTo({ top: M.scrollHeight, behavior: "instant" });
  });
  observeVisibleTurn(M, turnEntries);
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
  // background_react was missing entirely, so it fell through to the raw
  // technical label. It covers two very different paths, named at plan time.
  background_react: "Bringing the room to life",
};

// Sub-agents that run INSIDE a stage rather than as their own step. They can
// dominate a stage's wall-clock (a blurb mint for a new cohort, an image
// prompt), so the progress line names them instead of leaving the stage
// looking stuck.
const FRIENDLY_SUBAGENTS = {
  blurb_mint: "Giving the extras personalities",
  scene_life: "Voicing the room",
  backdrop_prompt: "Describing the room for a picture",
  ambience_prompt: "Describing the room's sound",
  background_react: "A bystander reacts",
};

function friendlyPhase(key, label) {
  // A stage whose plan label already names the mode (the scene manager) should
  // keep that name rather than be flattened back to a generic one.
  if (/^Scene life/.test(String(label || ""))) return "Bringing the room to life";
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

function turnStatusSet(key, label, running = 1) {
  // The suffix is added AFTER friendlyPhase, not folded into the label: the
  // label is pattern-matched in there (the scene-manager prefix, the
  // character-name strip), so decorating it first would corrupt the match.
  const phase = friendlyPhase(key, label);
  $("#turnstatus-phase").textContent = running > 1
    ? `${phase}  (+${running - 1} running alongside)`
    : phase;
}

function turnStatusStop() {
  $("#turnstatus").classList.add("hidden");
  clearInterval(_turnStatusTimer);
  _turnStatusTimer = null;
}

// Reading scrollHeight straight after writing text into #live forces a
// synchronous layout, and the token path used to do that PER TOKEN for the
// whole length of a run. It is now one write per painted frame, inside
// `liveFlush` below: the log still sits at the bottom of every frame anyone
// sees, and stops re-laying-out between the frames nobody does.

// The toggle is a fixed element in the document, so looking it up once beats
// a `querySelector` per token.
let _streamTgl = null;
function _streamOn() {
  if (!_streamTgl) _streamTgl = $("#streamtgl");
  return !!(_streamTgl && _streamTgl.checked);
}

// Token deltas arrive far faster than a screen can show them, and the naive
// spelling of this did three things PER TOKEN: a `$("#streamtgl")` document
// query, a `getElementById`, and `p.textContent += delta`.
//
// The last is the expensive one, and it is not linear. Reading `textContent`
// serialises the node, and assigning it destroys the text node and builds a
// new one -- so appending the Nth token copies the whole transcript again,
// making the visible cost of streaming grow as the square of its length, with
// a layout invalidation on every single token. On a fast local model emitting
// hundreds of tokens a second that is the most expensive thing the page does.
//
// Deltas are buffered per step and flushed once per animation frame instead,
// which caps DOM work at the refresh rate no matter how fast tokens arrive,
// and appends a text node rather than rewriting the whole string. The scroll
// pin rides along in the same frame, so it stops being a second rAF per token.
// Nothing reads this element's text back -- it is display-only -- so adjacent
// text nodes are as good as one, and `generation_reset` clears both the node
// and any deltas still buffered behind it.
const _liveBuf = new Map();
let _liveFlushQueued = false;

function liveFlush() {
  _liveFlushQueued = false;
  for (const [key, text] of _liveBuf) {
    const p = document.getElementById("lt-" + safeId(key));
    if (p) p.append(text);
  }
  _liveBuf.clear();
  const L = $("#live");
  if (L) L.scrollTop = L.scrollHeight;
}

function liveAppend(key, delta) {
  _liveBuf.set(key, (_liveBuf.get(key) || "") + delta);
  if (_liveFlushQueued) return;
  _liveFlushQueued = true;
  requestAnimationFrame(liveFlush);
}

// `group` is the set of step keys starting together on this beat. Steps that
// genuinely overlap were rendering as an ordinary flat list, so a concurrent
// pair read as two sequential steps that happened to be fast -- which is why
// the parallelism was reported as missing when it was running.
function liveStep(key, label, group) {
  const L = $("#live");
  const sid = safeId(key);
  const parallel = Array.isArray(group) && group.length > 1;
  L.append(el("div", { class: "lk" + (parallel ? " lk-parallel" : ""),
                       id: "lk-" + sid },
    (parallel ? "⇉ " : "▸ ") + label));
  L.append(el("pre", { id: "lt-" + sid }));
  L.scrollTop = L.scrollHeight;
}

function handleEvt(ev) {
  if (ev.type === "step_start") {
    liveStep(ev.key, ev.label, ev.group);
    // A concurrent group fires several step_starts back to back, and the
    // one-line status showed whichever landed last -- naming one member of a
    // pair as though the other were not running. Say how many are up.
    turnStatusSet(
      ev.key, ev.label,
      Array.isArray(ev.group) ? ev.group.length : 1
    );
  } else if (ev.type === "token") {
    if (_streamOn()) liveAppend(ev.key, ev.delta);
  } else if (ev.type === "generation_reset") {
    _liveBuf.delete(ev.key);
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

// ---- Flipping between rerolls of the newest beat ----
//
// A full reroll appends a variant to every step and activates the newest, so a
// turn rerolled three times holds four renderings and the reader could only
// ever see the last one -- or open the technical panel, find the narrator step,
// and use its per-step arrows. This is that, in the place people actually look
// for it.
//
// Only the newest turn, and the server enforces it too. An earlier turn's
// alternate rendering is a different question: every turn after it was
// generated against the prose that IS active, so swapping one silently would
// leave the story describing a beat nobody downstream ever read.
//
// Selecting a variant does NOT mark anything stale. That is the same position
// `edit_prose` takes on the server and for the same reason -- the mechanical
// record of the beat is the director/perception/commit steps, which already
// ran and already applied side effects that are not idempotent. Which
// rendering the reader sees is presentation.
const RR = {
  turnId: null,     // the turn the arrows currently belong to
  variants: [],     // [{id, active, prose}] oldest first
  index: 0,
  // Held rather than re-queried. The transcript is rebuilt wholesale on every
  // render, so a selector resolved at press time can land on a node from a
  // story the reader has already navigated away from.
  proseEl: null,
  countEl: null,
};

async function _mountRerollNav(turnId, turnEl) {
  RR.turnId = null;
  RR.variants = [];
  RR.proseEl = null;
  RR.countEl = null;
  let payload;
  try {
    payload = await api("GET", `/api/turns/${turnId}/narration`);
  } catch (e) {
    return;   // No arrows is a fine outcome; the beat still reads.
  }
  // The transcript may have been rebuilt under us while that request was in
  // flight (a reroll finishing, a different story opened).
  if (!turnEl.isConnected) return;
  const variants = (payload && payload.variants) || [];
  if (variants.length < 2) return;

  RR.turnId = turnId;
  RR.variants = variants;
  RR.index = Math.max(0, variants.findIndex(v => v.active));
  RR.proseEl = turnEl.querySelector(".prose");

  const nav = turnEl.querySelector(".rerollnav");
  if (!nav) return;
  nav.classList.remove("hidden");
  nav.replaceChildren(
    el("button", {
      class: "rr-arrow",
      title: "Previous version of this beat (←)",
      "aria-label": "Previous version of this beat",
      onclick: () => showRerollVariant(RR.index - 1)
    }, "◀"),
    RR.countEl = el("span", { class: "rr-count" }, ""),
    el("button", {
      class: "rr-arrow",
      title: "Next version of this beat (→)",
      "aria-label": "Next version of this beat",
      onclick: () => showRerollVariant(RR.index + 1)
    }, "▶")
  );
  _paintRerollCount();
}

function _paintRerollCount() {
  if (RR.countEl) {
    RR.countEl.textContent = `${RR.index + 1}/${RR.variants.length}`;
  }
}

// Wraps, because with two or three versions the reader is comparing rather
// than seeking, and hitting a wall mid-comparison is the annoying part.
async function showRerollVariant(next) {
  if (S.busy || RR.variants.length < 2) return false;
  const total = RR.variants.length;
  const index = ((next % total) + total) % total;
  if (index === RR.index) return false;
  const variant = RR.variants[index];

  // Paint first, then persist. The prose is already in hand, so the flip is
  // instant and the request rides behind it; a round trip per arrow press
  // would make browsing feel like loading.
  if (RR.proseEl && RR.proseEl.isConnected) {
    RR.proseEl.textContent = variant.prose || "…";
  }
  RR.index = index;
  _paintRerollCount();

  try {
    await api("POST", `/api/turns/${RR.turnId}/narration`,
              { variant_id: variant.id });
    RR.variants.forEach((v, i) => { v.active = i === index; });
  } catch (e) {
    toast("Could not switch version: " + e.message, "err");
  }
  return true;
}

// ← and → anywhere that is not a text field. Guarded on the composer and on
// any input/textarea/contenteditable, because arrow keys move a caret there
// and stealing them would be the kind of shortcut people disable.
document.addEventListener("keydown", event => {
  if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
  if (event.ctrlKey || event.metaKey || event.altKey) return;
  if (!$("#modal").classList.contains("hidden")) return;
  if (document.querySelector(".confirm-overlay")) return;
  const active = document.activeElement;
  if (active && (active.isContentEditable
      || /^(INPUT|TEXTAREA|SELECT)$/.test(active.tagName))) return;
  if (RR.variants.length < 2) return;
  // Only claim the key once there is something to do with it, so ordinary
  // horizontal scrolling still works on a story with no rerolls.
  event.preventDefault();
  showRerollVariant(RR.index + (event.key === "ArrowLeft" ? -1 : 1));
});

async function abortActiveRun() {
  const run = _activeRun;
  if (!run || !run.chatId) return false;
  const query = run.frameId != null ? `?frame_id=${run.frameId}` : "";
  return api("POST", `/api/chats/${run.chatId}/abort${query}`);
}

async function runStream(url, body, context = {}) {
  if (S.busy) return false;
  const run = {
    chatId: context.chatId !== undefined ? context.chatId : S.chatId,
    frameId: context.frameId !== undefined ? context.frameId : S.currentFrameId,
  };
  _activeRun = run;
  S.busy = true;
  $("#send").disabled = true;
  $("#stop").classList.remove("hidden");
  liveReset();
  turnStatusStart();
  // Unlock the audio context on the gesture that STARTS the wait, not on the
  // one that ends it -- by then the reader is in another tab and there is no
  // gesture left to spend. See chime.js.
  if (typeof chimeArm === "function") chimeArm();

  let ok = true;
  try {
    await streamPost(url, body, handleEvt);
  } catch (e) {
    ok = false;
    toast("Pipeline failed: " + e.message, "err", 9000);
  } finally {
    if (_activeRun === run) _activeRun = null;
    S.busy = false;
    $("#send").disabled = false;
    $("#stop").classList.add("hidden");
    $("#live").classList.add("hidden");
    turnStatusStop();
    if (S.chatId) {
      try {
        // The re-render below lands the reader on a brand-new turn. Mark it so
        // its picture and sound are fetched at once rather than after a dwell:
        // waiting two seconds for a beat you just watched arrive is a stall.
        if (ok) _freshTurnPending = true;
        await openChat(S.chatId);
        // After the re-render, so the beat is on screen when it sounds. Only
        // on success: a failure already raised a toast, and a chime that means
        // "ready" must not also mean "gone wrong".
        if (ok && typeof chimePlay === "function") chimePlay();
      } catch (e) {
        toast("Could not refresh story.", "err");
      }
    }
  }
  return ok;
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

// ---- Pipeline drawer: reading a step through a lens ----
//
// Every step is stored as one JSON blob, and a blob is the wrong shape for the
// two questions a stored step is usually opened to answer.
//
// "What did THIS mind get?" — the perception stages emit one view per
// perceiver and the loops one round per character, all keyed by bare cast id.
// Read as raw JSON that is a wall of escaped prose with the reader doing the
// id-to-name join in their head, and a view missing an entire sensory channel
// looks exactly like a view that is merely shorter. Live (chat 38 t140): one
// character's view of an embrace happening six feet away had no sight in it at
// all, and nothing about the blob said so.
//
// "What did this step say about X?" — `director_resolve` alone carries
// thirteen top-level keys, several of them long, and finding `resolved_event`
// means scrolling past `state_diff`.
//
// So a step is read through a LENS: one facet on its own, with the whole thing
// as stored always one click away. Which facets exist is derived from the
// content rather than declared per step key, so a stage that grows a field
// gets a button for it without anyone remembering to add one.

function perceiverViews(content) {
  const views = content && content.views;
  if (!views || typeof views !== "object" || Array.isArray(views)) return null;
  return Object.keys(views).length ? views : null;
}

// The cast ids a loop step ran a round for, in the order it ran them. Both
// loops carry the same shape under different field names, which is also the
// pair `_rehydrate_loop_results` has to keep in step.
function loopMindIds(content) {
  const rounds = content && content.rounds;
  if (!Array.isArray(rounds) || !rounds.length) return [];
  const ids = [];
  for (const r of rounds) {
    if (!r || typeof r !== "object") continue;
    const id = r.speaker_id ?? r.reactor_id ?? r.character_id;
    if (id === null || id === undefined) continue;
    if (!ids.includes(String(id))) ids.push(String(id));
  }
  return ids;
}

// What this step can be read one-of-at-a-time. Per mind where the step IS
// per-mind; otherwise per top-level key, which is the generic fallback and the
// reason an unfamiliar step still gets a usable bar.
function stepLenses(content) {
  if (!content || typeof content !== "object" || Array.isArray(content)) {
    return null;
  }
  if (perceiverViews(content)) {
    return { kind: "perceiver", label: "Seen by",
             ids: Object.keys(content.views) };
  }
  const minds = loopMindIds(content);
  if (minds.length) {
    return { kind: "mind", label: "Decided by", ids: minds };
  }
  const keys = Object.keys(content).filter(k => k !== "_engine_notes");
  if (!keys.length) return null;
  return { kind: "key", label: "Show", ids: keys };
}

function perceiverLabel(id, names) {
  const name = names[id];
  if (id === "player") return name ? `${name} (player)` : "player";
  return name ? `${name} (${id})` : `#${id}`;
}

// How much is in a facet, so the shape of a step is readable from the bar
// without opening anything. An empty list and a missing key are different
// answers and are marked differently.
function facetBadge(value) {
  if (value === null || value === undefined || value === "") return "∅";
  if (Array.isArray(value)) return String(value.length);
  if (typeof value === "object") return String(Object.keys(value).length);
  return "";
}

function lensLabel(lenses, id, content, names) {
  if (lenses.kind === "key") {
    const badge = facetBadge(content[id]);
    return badge ? `${id} ·${badge}` : id;
  }
  return perceiverLabel(id, names);
}

function renderLensBar(bar, lenses, lens, content, names, onPick) {
  bar.innerHTML = "";
  bar.append(el("span", { class: "dim" }, lenses.label));
  for (const id of lenses.ids) {
    bar.append(el(
      "button",
      {
        class: lens === id ? "primary" : "",
        onclick: () => onPick(id)
      },
      lensLabel(lenses, id, content, names)
    ));
  }
  bar.append(
    el("span", { class: "spacer" }),
    el(
      "button",
      {
        class: lens === "" ? "primary" : "",
        title: "The whole step as stored",
        onclick: () => onPick("")
      },
      "{ } JSON"
    )
  );
}

function lensSlice(lenses, content, id, names) {
  if (lenses.kind === "perceiver") return perceiverSlice(content, id, names);
  if (lenses.kind === "mind") return mindSlice(content, id, names);
  return keySlice(content, id);
}

// One perceiver's slice: the prose they received, then the structured
// observations derived from it. A null view is shown as the answer it is --
// this mind registered nothing -- rather than as an absent key.
function perceiverSlice(content, id, names) {
  const view = (content.views || {})[id];
  const out = [perceiverLabel(id, names), ""];
  out.push(
    view === null || view === undefined || view === ""
      ? "(no view — nothing registered, or this mind was not asked)"
      : String(view)
  );
  const observations = (content.observations || {})[id];
  if (Array.isArray(observations) && observations.length) {
    out.push("", `— observations (${observations.length}) —`, "");
    for (const o of observations) {
      const channel = o.channel || "?";
      const text = (o.observed && o.observed.text) || "";
      const flags = o.directed_at_self ? "  ← at them" : "";
      out.push(`[${channel}] ${text}${flags}`);
    }
  }
  return out.join("\n");
}

// One mind's slice of a loop: the rounds it actually spoke or reacted in, then
// the result stored under its id. Both, deliberately, even though the round
// carries a `result` of its own -- a loop's rounds and its results map are
// written separately and rehydrated separately on a rerun, so the two
// disagreeing is a bug class, and it is invisible if the view shows one.
function mindSlice(content, id, names) {
  const out = [perceiverLabel(id, names), ""];
  const rounds = (content.rounds || []).filter(
    r => String(r && (r.speaker_id ?? r.reactor_id ?? r.character_id)) === id
  );
  if (!rounds.length) out.push("(no round — this mind did not act in the loop)");
  for (const r of rounds) {
    out.push(`— round ${r.round} —`, JSON.stringify(r, null, 2), "");
  }
  const results = content.character_results || content.reaction_results || {};
  if (results && Object.prototype.hasOwnProperty.call(results, id)) {
    out.push("— stored result —", JSON.stringify(results[id], null, 2));
  }
  return out.join("\n");
}

// One field on its own. A string field is shown as the prose it is rather than
// as an escaped JSON scalar -- `resolved_event`, `summary` and the narrator's
// `text` are the whole reason to open most steps, and they are unreadable with
// their newlines spelled \n.
function keySlice(content, key) {
  const value = content[key];
  if (typeof value === "string") return value || "(empty)";
  if (value === null || value === undefined) return "(null)";
  return JSON.stringify(value, null, 2);
}

// What the deterministic layer did to this step's output. Written by
// agents/runtime.py into the saved content under `_engine_notes`; steps that
// needed no repair carry no key and get no block.
function renderEngineNotes(box, content) {
  box.innerHTML = "";
  const notes = content && content._engine_notes;
  if (!notes) return;
  if (Array.isArray(notes.parallel_with) && notes.parallel_with.length) {
    box.append(el("div", { class: "dim" },
      "⇉ ran concurrently with " + notes.parallel_with.join(", ")));
  }
  for (const w of notes.warnings || []) {
    box.append(el("div", { class: "engine-warning" }, "⚠ " + w));
  }
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
              // Capture before the await: event.currentTarget is null once
              // click dispatch ends (same bug as the turn Delete button).
              const btn = event.currentTarget;
              if (!await confirmCheckpointRestore()) return;
              await buttonTask(
                btn,
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
    const perspectives = el("div", { class: "row perspectives" });
    const notes = el("div", { class: "engine-notes" });
    const reasoning = el("pre", { class: "reasoning" }, "");
    const reasoningWrap = el(
      "details",
      { class: "reasoning-wrap" },
      el("summary", {}, "Expand reasoning"),
      reasoning
    );
    const cnt = el(
      "span",
      { class: "badge" },
      variants.length
        ? `${cur + 1}/${variants.length}`
        : "0/0"
    );

    // Which facet this step is being read through, or "" for the raw JSON.
    // Kept across variant switches so flipping between rerolls compares the
    // SAME perceiver or the SAME field rather than resetting to the first --
    // comparing rerolls is most of what this drawer is for.
    let lens = null;

    const show = index => {
      if (!variants.length) {
        cur = 0;
        cnt.textContent = "0/0";
        pre.textContent = "(no active variant)";
        perspectives.innerHTML = "";
        notes.innerHTML = "";
        return;
      }

      cur = Math.max(
        0,
        Math.min(index, variants.length - 1)
      );
      cnt.textContent =
        `${cur + 1}/${variants.length}`;

      const variant = variants[cur];
      let content = null;
      try {
        content = JSON.parse(variant.content);
      } catch (error) {
        content = null;
      }

      renderEngineNotes(notes, content);

      const lenses = stepLenses(content);
      if (!lenses) {
        perspectives.innerHTML = "";
        pre.textContent = content === null
          ? variant.content
          : JSON.stringify(content, null, 2);
      } else {
        // A per-mind step opens on a mind, because "which one" is the whole
        // question there. Everything else opens on the stored JSON, so the
        // habit of reading a step whole is unchanged and the facets are an
        // addition rather than a redirection.
        if (lens === null) {
          lens = lenses.kind === "key" ? "" : lenses.ids[0];
        } else if (lens !== "" && !lenses.ids.includes(lens)) {
          lens = lenses.kind === "key" ? "" : lenses.ids[0];
        }
        renderLensBar(
          perspectives, lenses, lens, content, p.perceivers || {},
          picked => { lens = picked; show(cur); }
        );
        pre.textContent = lens === ""
          ? JSON.stringify(content, null, 2)
          : lensSlice(lenses, content, lens, p.perceivers || {});
      }

      // A thinking model's own trace, when it exposed one. Collapsed by
      // default and kept visibly apart from the output: it is the model
      // talking to itself, it has been through none of the validation the
      // output has, and nothing in the fiction has ratified it.
      const think = (variant.reasoning || "").trim();
      reasoning.textContent = think;
      reasoningWrap.style.display = think ? "" : "none";
      reasoningWrap.open = false;
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
      notes,
      controls,
      perspectives,
      reasoningWrap,
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

async function relationshipModal(p, boundChatId = null) {
  const chatId = boundChatId ?? S.chatId;
  if (!chatId || S.chatId !== chatId) return;
  modal("Relationships — " + p.name, async body => {
    const ownsModal = modalOwnership(body);
    body.innerHTML = "";
    body.append(loadingBlock("Loading…"));
    let rels;
    try {
      rels = await api("GET", `/api/chats/${chatId}/characters/${p.id}/relationships`);
    } catch (e) {
      if (S.chatId !== chatId) {
        if (ownsModal()) closeAllModals();
        return;
      }
      if (!ownsModal()) return;
      body.innerHTML = "";
      body.append(el("div", { class: "dim" }, "Could not load relationships: " + e.message));
      return;
    }
    if (S.chatId !== chatId) {
      if (ownsModal()) closeAllModals();
      return;
    }
    if (!ownsModal()) return;
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
    // Hidden until the coverage check says there is a hole. A bank whose
    // windows already reach its first memory has nothing to rebuild, and a
    // button that does nothing teaches the wrong thing about the one that does.
    const backfillButton = el("button", {
      style: "display:none",
      title: "Rebuild the earlier summaries this story lost"
    }, "⟲ Rebuild earlier eras");
    const backfillNote = el("div", {
      class: "small dim", style: "margin-top:6px; display:none"
    });
    backfillButton.onclick = () => backfillMemoryEras();
    checkMemoryCoverage(backfillButton, backfillNote);

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
        consolidateButton, contextButton, backfillButton),
      el("div", {
        class: "small dim",
        style: "margin-top:8px"
      }, "Consolidation updates the character's subjective "
        + "long-term summary. Context preview shows what the "
        + "agent receives."),
      backfillNote);
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
  const encValIn = el("input", {
    type: "number", min: "-1", max: "1", step: "0.05",
    value: m.encoding_valence ?? 0
  });
  const encAroIn = el("input", {
    type: "number", min: "0", max: "1", step: "0.05",
    value: m.encoding_arousal ?? 0
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
          encoding_valence: numOr(encValIn.value, 0),
          encoding_arousal: numOr(encAroIn.value, 0),
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
      fieldWrap("Affect before — valence", valIn),
      fieldWrap("Affect before — arousal", aroIn),
      fieldWrap("Affect after — valence", encValIn),
      fieldWrap("Affect after — arousal", encAroIn),
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

async function checkMemoryCoverage(button, note) {
  // Before schema v23 a scope held one summary row and every consolidation
  // overwrote it, so a long story kept a summary of its last ten turns and
  // lost the rest. The raw memories survived, so the eras are rebuildable —
  // but only where there is a hole, which this asks.
  const cid = memCharId();
  if (!cid) return;
  let cov;
  try {
    cov = await api("GET",
      `/api/chats/${S.chatId}/characters/${cid}/memories/coverage`);
  } catch (e) { return; }
  if (!cov || !cov.missing_windows) return;
  const pct = cov.total
    ? Math.round((cov.covered / cov.total) * 100) : 0;
  button.style.display = "";
  note.style.display = "";
  note.textContent =
    `${cov.uncovered} of ${cov.total} memories sit under no summary `
    + `(${pct}% covered). Rebuilding costs about ${cov.missing_windows} `
    + `model calls.`;
}

function backfillMemoryEras() {
  const cid = memCharId();
  if (!cid) return;
  const name = S.memoryCharacter?.name || "character";
  // backgroundTask closes the modal and onSuccess reopens it, exactly as
  // Consolidate does -- one long model job, the panel rebuilt from the result.
  backgroundTask("Rebuilding " + name + "'s earlier eras",
    () => api("POST",
      `/api/chats/${S.chatId}/characters/${cid}/memories/backfill`, {}),
    {
      onSuccess: async () => {
        if (S.memoryCharacter)
          await memModal(S.memoryCharacter);
      },
      successMessage: r =>
        r?.windows
          ? `Rebuilt ${r.windows} earlier ${r.windows === 1 ? "era" : "eras"}.`
          : "Nothing to rebuild — every era already has a summary.",
      errorPrefix: "Rebuild failed"
    });
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
          // Pop back to the browser modal already on the stack instead of
          // pushing a fresh one (which grew the stack on every round trip).
          onclick: () => closeModal()
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
async function chatPH(p, boundChatId = null) {
  const chatId = boundChatId ?? S.chatId;
  if (!chatId || S.chatId !== chatId) return;
  const d = await api("GET",
    `/api/chats/${chatId}/characters/${p.id}/private_history`);
  if (S.chatId !== chatId) return;
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
              `/api/chats/${chatId}/characters/${p.id}/private_history`,
              { entries: ph.read() });
            closeModal();
            toast("Private history saved.", "ok");
          }
        }, "Save")));
  });
}

async function personaPH(boundChatId = null) {
  const chatId = boundChatId ?? S.chatId;
  if (!chatId || S.chatId !== chatId) return;
  const d = await api("GET",
    `/api/chats/${chatId}/persona_private_history`);
  if (S.chatId !== chatId) return;
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
              `/api/chats/${chatId}/persona_private_history`,
              { entries: ph.read() });
            closeModal();
            toast("Saved.", "ok");
          }
        }, "Save")));
  });
}
