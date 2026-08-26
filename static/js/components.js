// Story text, wrapped so `el()` cannot translate it.
//
// `el()` runs every text child through `t()` BEFORE the node is inserted, so
// the `translate="no"` guard on the transcript never gets a chance -- the
// string is already Japanese by the time it lands in the DOM. 153 of the
// catalog's keys are single words, so a beat consisting of "Close", a
// character named "Cast", or a story called "Book" all collide. Worst case
// measured: the narrator-prose EDITOR translated the prose on its way in and
// then PUT it back, persisting the translation into the story.
//
// Anything with a `nodeType` is passed through untouched by the loop below,
// which is what makes this work.
function txt(value) {
  return document.createTextNode(value == null ? "" : String(value));
}

function el(tag, attrs = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (k === "value") e.value = v;
    else if (k === "selected") e.selected = true;
    else if (k === "checked") e.checked = true;
    else if (v !== null && v !== false) {
      const value = ["title", "aria-label", "placeholder", "alt"].includes(k)
        ? t(String(v)) : v;
      e.setAttribute(k, value);
    }
  }
  for (const k of kids.flat()) {
    if (k == null || k === false) continue;
    e.append(k.nodeType ? k : document.createTextNode(t(String(k))));
  }
  return e;
}

// ---- Modal ----
// #modal/#modalbody is a singleton -- calling modal() while one is
// already open (a confirm/rename/etc. triggered by a button inside an
// already-open modal, common throughout this app) used to just overwrite
// the parent's content outright, with no way back to it. S.modalStack
// makes that a real stack: opening a modal on top of another pushes the
// current one's live DOM nodes (not a stringified copy, which would
// silently drop every already-attached event listener) so closeModal()
// can restore them instead of just hiding the whole dialog.
if (!S.modalStack) S.modalStack = [];
// modalToken is a monotonic allocator: an owner id is minted once and never
// reused. modalOwnerToken is the modal instance currently mounted in the
// singleton shell; unlike the allocator, it may return to a saved parent when
// a stacked child closes.
S.modalOwnerToken = null;

// ---- Book covers ----
// Purely decorative, and only the tavern theme draws it: that theme binds
// every dialog as a book, and a dialog opened from a row in the sidebar is
// bound in THAT row's leather. The choice has to be made here rather than in
// CSS because the interesting input -- which list row you clicked -- is not
// something a stylesheet can see from #modalbox. Every other theme simply
// ignores the attribute.
const BOOK_COVERS = 5;
let pendingCover = null;

function coverOfRow(target) {
  const row = target?.closest?.("#sidelist .item, .lore-side-node");
  if (!row || !row.parentElement) return null;
  // Has to agree with themes.css, which cycles the leathers on :nth-child --
  // and that counts EVERY sibling, including a leading .empty-state, not
  // just the rows. Index from the parent's children for the same reason.
  const i = [...row.parentElement.children].indexOf(row);
  return i < 0 ? null : (i % BOOK_COVERS) + 1;
}

// Capture phase, so this runs before the row's own handler opens anything.
// A click that is not on a book clears the pending cover rather than leaving
// it set: without that, a dialog opened from the toolbar would inherit
// whichever book happened to have been clicked last, possibly minutes ago.
document.addEventListener("click", event => {
  pendingCover = coverOfRow(event.target);
}, true);

// Dialogs with no book behind them still need a cover, and it has to be the
// SAME cover every time that dialog opens -- one that changed per opening
// would read as a rendering fault rather than as a bound volume. The title
// is the only stable identity a dialog has here, so hash it.
function coverOfTitle(title) {
  let h = 0;
  for (let i = 0; i < title.length; i++) h = (h * 31 + title.charCodeAt(i)) % 1000003;
  return (h % BOOK_COVERS) + 1;
}

function modal(title, build, opts = {}) {
  const body = $("#modalbody");
  const box = $("#modalbox");
  if (!$("#modal").classList.contains("hidden")) {
    S.modalStack.push({
      title: $("#modaltitle").textContent,
      nodes: [...body.childNodes],
      wide: box.classList.contains("wide"),
      cover: box.dataset.cover,
      ownerToken: S.modalOwnerToken,
    });
  }
  S.modalOwnerToken = ++S.modalToken;
  $("#modaltitle").textContent = t(title);
  box.classList.toggle("wide", !!opts.wide);
  // Consumed, not left standing: the next dialog is only this book's if it
  // was this book that was clicked.
  box.dataset.cover = pendingCover || coverOfTitle(title);
  pendingCover = null;
  body.innerHTML = "";
  build(body);
  $("#modal").classList.remove("hidden");
  requestAnimationFrame(() => {
    const f = body.querySelector("input:not([disabled]),textarea:not([disabled]),select:not([disabled])");
    if (opts.autoFocus !== false && f) f.focus();
  });
}

// Capture ownership of the singleton modal across asynchronous work. A child
// temporarily invalidates its stacked parent, but closing that child restores
// the parent's unique owner id along with its live DOM, so the parent's pending
// work may safely finish. Closed/hidden owners and permanently superseded
// children still fail this check.
function modalOwnership(body = $("#modalbody")) {
  const ownerToken = S.modalOwnerToken;
  return () => (
    S.modalOwnerToken === ownerToken
    && body === $("#modalbody")
    && !$("#modal").classList.contains("hidden")
  );
}

function closeModal() {
  S.modalToken++;
  const body = $("#modalbody");
  if (S.modalStack.length) {
    const prev = S.modalStack.pop();
    $("#modaltitle").textContent = prev.title;
    body.innerHTML = "";
    for (const node of prev.nodes) body.append(node);
    $("#modalbox").classList.toggle("wide", prev.wide);
    // The cover belongs to the dialog, so it unwinds with it -- otherwise
    // closing a confirm re-showed the parent bound in the confirm's cover.
    $("#modalbox").dataset.cover = prev.cover || "";
    S.modalOwnerToken = prev.ownerToken;
    return;
  }
  S.modalOwnerToken = null;
  $("#modal").classList.add("hidden");
  $("#modalbox").classList.remove("wide");
  body.innerHTML = "";
}

// Closes every level of the modal stack at once, not just the top one --
// for flows (e.g. deleting the thing the parent modal was showing) where
// going back to a parent modal about to be stale/gone makes no sense.
function closeAllModals() {
  S.modalStack.length = 0;
  S.modalToken++;
  S.modalOwnerToken = null;
  $("#modal").classList.add("hidden");
  $("#modalbox").classList.remove("wide");
  $("#modalbody").innerHTML = "";
}

// ---- confirm()/prompt() replacements ----
// Native browser dialogs are unstyled gray chrome punching through an
// otherwise fully custom dark UI -- the single most visible "this wasn't
// designed" tell in the app. These match the native functions' calling
// convention (confirmModal resolves true/false, promptModal resolves the
// string or null on cancel) so call sites just need `await` added, not a
// rewrite. Deliberately its OWN small overlay, appended straight to
// <body> rather than reusing #modal/S.modalStack: a confirm/prompt is a
// transient decision point layered on top of whatever's currently
// showing (very often another modal, e.g. confirming a delete from
// inside an edit dialog), not a navigable view -- routing it through the
// modal stack would mean a visible flash of the parent modal restoring
// mid-flow on any call site that closes and reopens fresh afterward
// (a common pattern in this app), since that parent would still be
// sitting on the stack for the instant between this resolving and the
// caller's own close-and-reopen.
function _confirmOverlay(buildBody, onKeydown) {
  const backdrop = el("div", {
    class: "confirm-overlay",
    style: "position:fixed;inset:0;z-index:200;background:rgba(0,0,0,.5);"
      + "display:flex;align-items:center;justify-content:center;animation:fade-in .12s ease",
  });
  const box = el("div", {
    style: "width:min(380px,92vw);background:var(--bg2);border:1px solid var(--bd);"
      + "border-radius:12px;padding:16px;box-shadow:var(--shadow)",
  });
  backdrop.append(box);
  document.body.append(backdrop);

  const cleanup = () => { backdrop.remove(); document.removeEventListener("keydown", keyHandler) };
  const keyHandler = e => {
    if (e.key === "Escape") onKeydown?.dismiss();
    if (e.key === "Enter") onKeydown?.confirm();
  };
  document.addEventListener("keydown", keyHandler);
  backdrop.addEventListener("click", e => { if (e.target === backdrop) onKeydown?.dismiss() });

  buildBody(box);
  requestAnimationFrame(() => {
    const f = box.querySelector("input,textarea,select,button.primary");
    f?.focus();
  });

  return { cleanup };
}

function confirmModal(message, opts = {}) {
  return new Promise(resolve => {
    let finished = false;
    const finish = value => {
      if (finished) return;
      finished = true;
      overlay.cleanup();
      resolve(value);
    };
    const overlay = _confirmOverlay(box => {
      box.append(
        el("div", { style: "margin-bottom:14px;white-space:pre-wrap" }, message),
        el("div", { class: "row", style: "justify-content:flex-end" },
          el("button", { onclick: () => finish(false) }, opts.cancelLabel || "Cancel"),
          el("button", { class: opts.danger ? "danger primary" : "primary",
            onclick: () => finish(true) },
            opts.confirmLabel || "Confirm")));
    }, { dismiss: () => finish(false), confirm: () => finish(true) });
  });
}

function promptModal(message, defaultValue = "", opts = {}) {
  return new Promise(resolve => {
    let finished = false;
    const finish = value => {
      if (finished) return;
      finished = true;
      overlay.cleanup();
      resolve(value);
    };
    const input = el("input", { type: "text", style: "width:100%", value: defaultValue || "" });
    const overlay = _confirmOverlay(box => {
      box.append(
        el("div", { style: "margin-bottom:8px;white-space:pre-wrap" }, message),
        input,
        el("div", { class: "row", style: "justify-content:flex-end;margin-top:12px" },
          el("button", { onclick: () => finish(null) }, "Cancel"),
          el("button", { class: "primary", onclick: () => finish(input.value) },
            opts.okLabel || "OK")));
    }, { dismiss: () => finish(null), confirm: () => finish(input.value) });
  });
}

// A prompt with one extra opt-in beside it. Its own helper rather than an
// option on promptModal because it resolves to a different shape -- {text,
// checked} instead of a string -- and quietly changing what promptModal
// returns for some callers is how a null check stops working somewhere else.
function promptModalWithToggle(message, toggleLabel, opts = {}) {
  return new Promise(resolve => {
    let finished = false;
    const finish = value => {
      if (finished) return;
      finished = true;
      overlay.cleanup();
      resolve(value);
    };
    const input = el("input", { type: "text", style: "width:100%", value: opts.defaultValue || "" });
    const box = el("input", { type: "checkbox", ...(opts.checked ? { checked: "" } : {}) });
    const done = () => finish({ text: input.value, checked: box.checked });
    const overlay = _confirmOverlay(wrap => {
      wrap.append(
        el("div", { style: "margin-bottom:8px;white-space:pre-wrap" }, message),
        input,
        el("label", { class: "small", style: "display:block;margin-top:10px" },
          box, " " + toggleLabel),
        ...(opts.toggleNote
          ? [el("div", { class: "small dim", style: "margin-top:4px" }, opts.toggleNote)]
          : []),
        el("div", { class: "row", style: "justify-content:flex-end;margin-top:12px" },
          el("button", { onclick: () => finish(null) }, "Cancel"),
          el("button", { class: "primary", onclick: done }, opts.okLabel || "OK")));
    }, { dismiss: () => finish(null), confirm: done });
  });
}

// One authoring control for every seam that can create a lived location:
// the new-story wizard, hand-built stories, greeting launch, Dialogue Config,
// and the lorebook workspace. Keeping the payload here prevents those paths
// from acquiring different meanings for "pre-simulate" over time.
function livedLocationControl(options = {}) {
  const showToggle = options.showToggle !== false;
  const enabled = el("input", { type: "checkbox" });
  enabled.checked = showToggle ? !!options.enabled : true;
  const brief = el("input", {
    type: "text",
    style: "width:100%",
    value: options.brief || "",
    placeholder: "What place? e.g. a crowded orbital customs station"
  });
  const history = el("select", { style: "width:100%" },
    el("option", { value: "0" }, "Generate it without a simulated past"),
    el("option", { value: "168" }, "Simulate its last week"),
    el("option", { value: "720" }, "Simulate its last month (recommended)"));
  history.value = String(options.horizonHours ?? 720);
  const historyOptions = () => [
        el("option", { value: "auto" }, "Auto — use the card and opening"),
        el("option", { value: "resident" }, "Lives here"),
        el("option", { value: "moving_institution" },
          "Travels with this place or group"),
        el("option", { value: "visitor" },
          "Arrives with authored or canon travels"),
        el("option", { value: "generated_journey" },
          "Generate a journey before arrival"),
        el("option", { value: "authored_only" }, "Use authored history only"),
        el("option", { value: "none" }, "No generated past")];
  const routeCopy = {
    auto: "Residence is used only when the card and opening explicitly place this character here; uncertainty preserves authored history.",
    resident: "Charter simulates this character's local work, relationships, incidents, and private routines, then hands them to full cognition.",
    moving_institution: "Charter treats the ship, caravan, unit, or other bounded group as the character's continuing home.",
    visitor: "The location is simulated without giving this character a post or tenure. Authored and canon travels remain their past.",
    generated_journey: "A separate journey history may invent prior destinations and encounters. It never makes the character a local resident.",
    authored_only: "No new character events are invented. The card and greeting remain authoritative.",
    none: "Only the opening's existing mind seeds are used. The location may still have its own history."
  };
  const configuredHistories = new Map(
    (options.characterHistories || []).map(row => [String(row.key), row]));
  const requestedResidents = Array.isArray(options.featuredResidents)
    ? options.featuredResidents
    : (options.featuredResidentName
        ? [{ key: "featured", name: options.featuredResidentName }]
        : []);
  const historyControls = requestedResidents.map((resident, index) => {
    const key = String(resident.key ?? `character-${index + 1}`);
    const prior = configuredHistories.get(key) || resident;
    const select = el("select", { style: "width:100%;margin-top:5px" },
      ...historyOptions());
    select.value = prior.mode || "auto";
    const guidance = el("textarea", {
      rows: "2", style: "width:100%;margin-top:6px",
      placeholder: "Past guidance (optional): eras, places, relationships, duties, habits, or canon to emphasize"
    }, prior.brief || "");
    const preview = el("div", { class: "small dim", style: "margin-top:5px" });
    const syncRoute = () => {
      preview.textContent = routeCopy[select.value] || routeCopy.auto;
    };
    select.onchange = syncRoute;
    syncRoute();
    return {
      key, select, guidance,
      node: el("div", { class: "card", style: "margin-top:8px" },
        el("strong", {}, `How does ${resident.name || "this character"} relate to this place?`),
        select, preview, guidance)
    };
  });
  const fields = el("div", { style: "margin-top:8px" },
    brief,
    el("label", { class: "small dim", style: "display:block;margin-top:8px" },
      "How much recent history should its residents live through?"),
    history,
    el("div", { class: "small dim", style: "margin-top:6px" },
      "The simulation creates events, work history, local judgments, obligations, "
      + "stock changes, reports, and decisions. It does not invent resident memories; "
      + "a featured resident may receive a separate bounded recent-life pass below."),
    historyControls.length
      ? el("div", { class: "card", style: "margin-top:8px" },
          historyControls.length > 1
            ? el("strong", {}, "Give each story character the right kind of past")
            : null,
          ...historyControls.map(control => control.node),
          el("div", { class: "dim small", style: "margin-top:6px" },
            `The location is planned using only public card details; private card details `
            + `never enter the location planner. The recent-life pass `
            + `uses the named roster, real rooms and duties, simulation anchors, the card, `
            + `and your guidance to create 10–16 separate memories. After handoff, Charter `
            + `stops speaking or deciding for them.`))
      : null);
  const sync = () => {
    fields.style.display = enabled.checked ? "" : "none";
  };
  enabled.onchange = sync;
  sync();
  const node = el("div", { class: "card", style: "margin-top:10px" },
    showToggle
      ? el("label", { class: "row", style: "gap:7px" }, enabled,
          el("strong", {}, "Build a lived-in location before play"))
      : el("strong", {}, "Generate a lived-in location"),
    el("div", { class: "small dim", style: "margin-top:4px" },
      options.note || "Uses the selected lorebook and your description to create "
        + "stable residents, places, institutions, goods, and local history."),
    fields);
  return {
    node,
    read: () => {
      if (!enabled.checked) return null;
      const horizon = Math.max(0, Math.min(720, Number(history.value) || 0));
      return {
        enabled: true,
        brief: brief.value.trim(),
        horizon_hours: horizon,
        active_tail_hours: Math.min(96, horizon),
        generate_history: horizon > 0,
        ...(historyControls.length === 1 && options.featuredResidentName
          ? { character_history: {
              mode: historyControls[0].select.value,
              brief: historyControls[0].guidance.value.trim()
            }}
          : {}),
        ...(historyControls.length && !options.featuredResidentName
          ? { character_histories: historyControls.map(control => ({
              key: control.key,
              mode: control.select.value,
              brief: control.guidance.value.trim()
            })) }
          : {})
      };
    }
  };
}

async function attachStoryLorebook(chatId, lorebookId) {
  if (!lorebookId) return null;
  const attached = await api("POST", `/api/chats/${chatId}/lorebooks`, {
    lorebook_id: Number(lorebookId)
  });
  return attached.lorebook_id;
}

async function generateStoryLocation(chatId, request, lorebookId = null) {
  if (!request) return null;
  const attachedId = await attachStoryLorebook(chatId, lorebookId);
  return api("POST", `/api/chats/${chatId}/charters/generate`, {
    ...request,
    ...(lorebookId ? { lorebook_id: Number(lorebookId) } : {}),
    ...(attachedId ? { owning_lorebook_id: attachedId } : {})
  });
}

function openLivedLocationDialog(chatId, options = {}) {
  if (!chatId) {
    toast("Open a story first, then choose which lore should become a location.", "warn");
    return;
  }
  if (S.chatId === chatId && S.currentFrameId != null) {
    toast("Return to the story's present before adding a lived location.", "warn");
    return;
  }
  const control = livedLocationControl({
    showToggle: false,
    brief: options.brief || "",
    horizonHours: options.horizonHours ?? 720,
    note: options.note
  });
  modal(options.title || "Generate a lived-in location", body => {
    body.append(
      control.node,
      el("div", { class: "small dim", style: "margin-top:8px" },
        "This adds a planned location and persistent residents without rewriting "
        + "the room currently on the page or giving anyone omniscient knowledge."),
      el("div", { class: "row", style: "margin-top:12px" },
        el("button", { onclick: () => closeModal() }, "Cancel"),
        el("span", { class: "spacer" }),
        el("button", { class: "primary", onclick: event => {
          const button = event.currentTarget;
          const request = control.read();
          button.disabled = true;
          backgroundTask("Generating and pre-simulating location",
            () => generateStoryLocation(
              chatId, request, options.lorebookId || null), {
              onSuccess: async result => {
                closeModal();
                await options.onSuccess?.(result);
              },
              successMessage: result =>
                `${result.town}: ${result.rooms} places and `
                + `${result.charters.length} institutions generated.`,
              errorPrefix: "Location generation failed",
              onFinally: () => {
                if (button.isConnected) button.disabled = false;
              }
            });
        } }, "Generate and add location")));
  }, { wide: false });
}

// ---- Toasts ----
// The host is declared in index.html, and `toast` still must not assume it is
// there. A toast is what the app reaches for when something ELSE has already
// gone wrong, so throwing here replaces a handled failure with an uncaught
// TypeError inside the handler that was reporting it -- the caller's remaining
// cleanup never runs, and the message the user needed is the one that is lost.
// Recreated by id, so the stylesheet dresses it identically.
function toastHost() {
  let host = $("#toasts");
  if (!host) {
    host = el("div", { id: "toasts", "aria-live": "polite",
                       "aria-atomic": "false" });
    document.body.append(host);
  }
  return host;
}

function toast(message, type = "ok", timeout = 4200) {
  const icon = { ok: "✓", err: "!", warn: "▲", info: "•" }[type] || "•";
  const node = el("div", { class: "toast " + type },
    el("span", { class: "badge " + type }, icon),
    el("div", { class: "toast-body" }, String(message)),
    el("button", { class: "ghost", title: "Dismiss", onclick: () => node.remove() }, "✕"));
  toastHost().append(node);
  if (timeout) setTimeout(() => { if (node.isConnected) node.remove() }, timeout);
  return node;
}

// ---- Background tasks ----
function renderActivity() {
  const panel = $("#activity"), list = $("#activity-list");
  const tasks = [...S.tasks.values()];
  $("#activity-count").textContent = String(tasks.length);
  panel.classList.toggle("hidden", tasks.length === 0);
  list.innerHTML = "";
  for (const task of tasks) {
    list.append(el("div", { class: "activity-row" },
      el("span", { class: "spinner" }),
      el("span", { style: "flex:1" }, task.label),
      el("span", { class: "dim" }, elapsedLabel(task.started))));
  }
}
function elapsedLabel(s) {
  const sec = Math.max(0, Math.floor((Date.now() - s) / 1000));
  return sec < 60 ? sec + "s" : Math.floor(sec / 60) + "m " + String(sec % 60).padStart(2, "0") + "s";
}
// Ticks only while something is actually running. As an unconditional
// setInterval this woke the page once a second forever, for the whole time the
// tab was open, to discover that there was nothing to redraw -- which is enough
// to keep a laptop out of its deeper idle states all evening.
let _activityTicker = null;
function activityTicking(on) {
  if (on && !_activityTicker) {
    _activityTicker = setInterval(() => {
      if (S.tasks.size) renderActivity();
      else activityTicking(false);
    }, 1000);
  } else if (!on && _activityTicker) {
    clearInterval(_activityTicker);
    _activityTicker = null;
  }
}

function backgroundTask(label, work, opts = {}) {
  const id = ++S.taskSeq;
  S.tasks.set(id, { id, label, started: Date.now() });
  if (opts.closeModal !== false) closeModal();
  renderActivity();
  activityTicking(true);          // stops itself once the last task finishes
  Promise.resolve().then(work)
    .then(async r => {
      if (opts.onSuccess) await opts.onSuccess(r);
      if (opts.successMessage) {
        const msg = typeof opts.successMessage === "function" ? opts.successMessage(r) : opts.successMessage;
        toast(msg, "ok");
      }
      return r;
    })
    .catch(e => {
      console.error(e);
      toast((opts.errorPrefix ? opts.errorPrefix + ": " : "") + (e?.message || String(e)), "err", 8000);
      if (opts.onError) opts.onError(e);
    })
    .finally(() => {
      S.tasks.delete(id); renderActivity();
      if (opts.onFinally) opts.onFinally();
    });
  return id;
}

async function buttonTask(btn, label, work) {
  // Null-safe: a caller that reads event.currentTarget after an await hands
  // us null (currentTarget is reset when dispatch ends). Never let that crash
  // BEFORE the work runs -- the action should still fire and errors still toast.
  const old = btn ? btn.textContent : null;
  if (btn) { btn.disabled = true; btn.textContent = label; }
  try { return await work() }
  catch (e) {
    // Surface the failure -- without this, a rejected work() (e.g. a 409
    // from a delete/reroll) becomes a silent unhandled rejection and the
    // button just quietly reverts, reading to the user as "nothing happened."
    // Mark it handled so the global unhandledrejection net doesn't re-toast.
    if (e && typeof e === "object") e.__handled = true;
    toast(e?.message || String(e), "err", 8000);
    throw e;
  }
  finally { if (btn && btn.isConnected) { btn.disabled = false; btn.textContent = old } }
}

function loadingBlock(label = "Loading…") {
  return el("div", { class: "loading-block" }, el("span", { class: "spinner" }), el("span", {}, label));
}
function emptyState(msg) { return el("div", { class: "empty-state" }, msg) }

// ---- Form helpers ----
function fText(label, val, ph) {
  const i = el("input", { value: val || "", placeholder: ph || "", style: "width:100%" });
  return { node: el("div", { class: "ff" }, el("label", {}, label), i), read: () => i.value };
}
function fArea(label, val, rows) {
  const t = el("textarea", { style: "width:100%", rows: String(rows || 3) }, val || "");
  return { node: el("div", { class: "ff" }, el("label", {}, label), t), read: () => t.value };
}
function fSelect(label, opts, val) {
  const s = el("select", {}, opts.map(o => {
    const [v, t] = Array.isArray(o) ? o : [o, o];
    return el("option", { value: v, ...(v === val ? { selected: "" } : {}) }, t);
  }));
  return { node: el("div", { class: "ff" }, el("label", {}, label), s), read: () => s.value };
}
function fNum(label, val, step) {
  const i = el("input", { type: "number", step: step || "any", value: val !== undefined && val !== null ? val : "", style: "width:100%" });
  return { node: el("div", { class: "ff" }, el("label", {}, label), i), read: () => i.value === "" ? undefined : +i.value };
}
// One entry per LINE, for lists whose entries are prose and therefore contain
// commas. `fStrList` splits on commas, which silently fragments them: a
// generated "Nine golden tails from the lower back, shifting with mood" was
// saved back as two features, and "vermillion, white, and gold" as three.
function fLineList(label, vals) {
  const t = el("textarea", {
    style: "width:100%", rows: "4",
    placeholder: "one per line"
  }, (vals || []).join("\n"));
  return {
    node: el("div", { class: "ff" }, el("label", {}, label), t),
    read: () => t.value.split("\n").map(s => s.trim()).filter(Boolean)
  };
}

function fStrList(label, vals) {
  const i = el("input", { value: (vals || []).join(", "), placeholder: "comma-separated", style: "width:100%" });
  return { node: el("div", { class: "ff" }, el("label", {}, label), i), read: () => i.value.split(",").map(s => s.trim()).filter(Boolean) };
}

// The closed set from attire.py. `waist` and `groin` are separate on purpose:
// a sash covers the belt line and nothing else, so conflating them would
// report a body wearing only an obi as covered where it matters most.
const ATTIRE_REGIONS = ["head", "torso", "arms", "hands", "waist", "groin",
                        "legs", "feet"];
const ATTIRE_REGION_ZONES = { torso: ["chest", "midriff"] };

// Coverage presets, offered as one-click shortcuts inside the picker. Not the
// only way to answer -- the checkboxes are -- but the four spans real clothing
// actually has, because ticking five boxes for every kimono is a chore an
// author should not have to repeat.
const ATTIRE_COVERAGE = [
  ["whole body (kimono, toga, jumpsuit)", ["torso", "arms", "waist", "groin", "legs"]],
  ["shoulders to ankles (dress, gown, sari)", ["torso", "waist", "groin", "legs"]],
  ["over the shoulders (coat, cloak, jacket)", ["torso", "arms", "waist"]],
  ["legwear (trousers, skirt)", ["legs", "groin"]],
];

// A dropdown of checkboxes: what this garment covers, any combination of it.
// `auto` is the default and means "work it out from the name" -- resolved in
// attire.py, so the cue table has exactly one implementation.
function fCoveragePicker(covers, auto, attaches, coveredZones = {}) {
  const boxes = new Map(ATTIRE_REGIONS.map(region => [region, el("input", {
    type: "checkbox", ...((covers || []).includes(region) ? { checked: "" } : {})
  })]));
  const autoBox = el("input", { type: "checkbox", ...(auto ? { checked: "" } : {}) });
  // Worn AT a place rather than over it. Same question as coverage, so it
  // lives in the same control: a ribbon sits in the hair and covers no head.
  const attachBox = el("input", {
    type: "checkbox", ...(attaches ? { checked: "" } : {}) });
  // Every covered region is displaceable-or-not (the displacement axis,
  // design note 17): an unzoned region is its own single zone, so unchecking
  // it writes {region: []} — worn, pushed off that place. Hand-editing this
  // matters: a host fixing a ledger by hand is a first-class path, and a
  // field the editor cannot express is a field the editor will silently
  // erase.
  const zonesFor = region => ATTIRE_REGION_ZONES[region] || [region];
  const zoneBoxes = new Map();
  ATTIRE_REGIONS.forEach(region => {
    const zones = zonesFor(region);
    const explicit = Object.prototype.hasOwnProperty.call(coveredZones || {}, region);
    const selected = explicit ? (coveredZones[region] || []) : zones;
    zoneBoxes.set(region, new Map(zones.map(zone => [zone, el("input", {
      type: "checkbox", ...(selected.includes(zone) ? { checked: "" } : {})
    })])));
  });
  const summary = el("summary", { style: "cursor:pointer;font-size:12px" });

  const picked = () => ATTIRE_REGIONS.filter(r => boxes.get(r).checked);
  const sync = () => {
    const on = picked();
    boxes.forEach(b => { b.disabled = autoBox.checked; });
    zoneBoxes.forEach((zoneMap, region) => zoneMap.forEach(b => {
      b.disabled = autoBox.checked || !boxes.get(region).checked;
    }));
    summary.textContent = (attachBox.checked ? "worn at: " : "covers: ") + (
      autoBox.checked ? "auto" : (on.length ? on.join(", ") : "nothing yet"));
  };
  autoBox.onchange = sync;
  attachBox.onchange = sync;
  boxes.forEach(b => { b.onchange = () => { autoBox.checked = false; sync(); }; });
  zoneBoxes.forEach(zoneMap => zoneMap.forEach(b => {
    b.onchange = () => { autoBox.checked = false; sync(); };
  }));

  const preset = (label, regions) => el("button", {
    type: "button", class: "ghost", style: "font-size:11px;padding:2px 6px",
    onclick: () => {
      autoBox.checked = false;
      boxes.forEach((b, r) => { b.checked = regions.includes(r); });
      sync();
    }
  }, label);

  const node = el("details", { class: "card", style: "flex:1;min-width:0;padding:4px 8px" },
    summary,
    el("label", { class: "small", style: "display:block;margin:6px 0" },
      autoBox, " auto — work it out from the garment's name"),
    el("label", { class: "small", style: "display:block;margin:6px 0" },
      attachBox, " worn at, covers nothing (ribbon, necklace, ring)"),
    el("div", { class: "row", style: "flex-wrap:wrap;gap:8px" },
      ...ATTIRE_REGIONS.map(region =>
        el("label", { class: "small" }, boxes.get(region), " " + region))),
    el("div", { class: "small dim", style: "margin-top:6px" },
      "waist is the belt line; groin is covered separately, so a sash alone "
      + "leaves it bare."),
    ...[...zoneBoxes.entries()].map(([region, zoneMap]) =>
      el("div", { class: "row small", style: "flex-wrap:wrap;gap:8px;margin-top:6px" },
        el("span", { class: "dim" },
          (ATTIRE_REGION_ZONES[region]
            ? region + " zones still covered:"
            : "still covering:")),
        ...[...zoneMap.entries()].map(([zone, box]) =>
          el("label", {}, box, " " + zone)))),
    el("div", { class: "row", style: "flex-wrap:wrap;gap:4px;margin-top:6px" },
      ...ATTIRE_COVERAGE.map(([label, regions]) => preset(label, regions))));

  sync();
  return {
    node,
    read: () => (autoBox.checked ? null : picked()),
    coveredZones: () => {
      const result = {};
      zoneBoxes.forEach((zoneMap, region) => {
        if (autoBox.checked || !boxes.get(region).checked) return;
        const all = zonesFor(region);
        const selected = all.filter(zone => zoneMap.get(zone).checked);
        if (selected.length !== all.length) result[region] = selected;
      });
      return result;
    },
    attaches: () => attachBox.checked
  };
}

function fAttireGarments(label, regions) {
  // One flat list of garments, each with what it covers -- rather than a box
  // per region, which cannot express a garment that spans several and made
  // the author place the same kimono four times.
  const seen = new Map();
  ATTIRE_REGIONS.forEach(region => {
    ((regions || {})[region] || {}).garments?.forEach(g => {
      const name = (typeof g === "string" ? g : g?.name || "").trim();
      if (!name || seen.has(name.toLowerCase())) return;
      const covers = (g.covers && g.covers.length ? g.covers : [region]);
      seen.set(name.toLowerCase(), {
        name, covers, description: g.description || "",
        coveredZones: { ...(g.covered_zones || {}) },
        attaches: !!g.attaches, condition: g.condition || "" });
    });
  });

  const list = fList(label, [...seen.values()], "+ garment", g => {
    // Name and description are separate because the NAME is the matching key:
    // "take off the kimono" has to find it, and a paragraph cannot be matched.
    const name = el("input", { value: g.name || "", placeholder: "name",
                               style: "flex:1;min-width:0" });
    const description = el("input", {
      value: g.description || "", placeholder: "what it looks like (optional)",
      style: "flex:2;min-width:0" });
    const covers = fCoveragePicker(
      g.covers, !!g.auto, !!g.attaches, g.coveredZones || {});
    return {
      node: [name, description, covers.node],
      read: () => {
        if (!name.value.trim()) return null;
        const picked = covers.read();
        return { name: name.value.trim(), description: description.value.trim(),
                 covers: picked || [], auto: picked === null,
                 covered_zones: covers.coveredZones(),
                 attaches: covers.attaches(), condition: g.condition || "" };
      }
    };
  }, () => ({ name: "", description: "", covers: [], auto: true,
              attaches: false, condition: "" }));

  // "Underneath" stays per region: it describes a body part, not a garment.
  const beneath = ATTIRE_REGIONS.map(region => {
    const input = el("input", {
      value: ((regions || {})[region] || {}).beneath || "",
      placeholder: "underneath (optional)", style: "flex:2;min-width:0"
    });
    const zoneInputs = (ATTIRE_REGION_ZONES[region] || []).map(zone => ({
      zone,
      input: el("input", {
        value: (((regions || {})[region] || {}).beneath_zones || {})[zone] || "",
        placeholder: zone + " underneath (optional)", style: "flex:2;min-width:0"
      })
    }));
    return {
      region,
      read: () => ({
        beneath: input.value.trim(),
        zones: Object.fromEntries(zoneInputs
          .map(z => [z.zone, z.input.value.trim()]).filter(([, text]) => text))
      }),
      node: el("div", { style: "margin-bottom:6px" },
        el("div", { class: "row", style: "gap:6px;margin-bottom:4px" },
          el("span", { class: "small dim", style: "flex:none;width:52px" }, region),
          input),
        ...zoneInputs.map(z => el("div", { class: "row", style: "gap:6px;margin:2px 0 2px 58px" },
          el("span", { class: "small dim", style: "width:48px" }, z.zone), z.input)))
    };
  });

  return {
    node: el("div", {}, list.node,
      el("label", { style: "margin-top:10px" }, "Underneath, by region"),
      ...beneath.map(b => b.node)),
    read: () => {
      const out = {};
      list.read().filter(Boolean).forEach(g => {
        // "auto" is sent as a flag rather than resolved here: attire.py owns
        // the cue table, and a second copy of it in the browser would drift.
        const anchor = g.covers[0] || "torso";
        const entry = out[anchor] || (out[anchor] = { garments: [], beneath: "" });
        entry.garments.push({
          name: g.name, description: g.description, state: "worn",
          attaches: g.attaches, condition: g.condition,
          ...(Object.keys(g.covered_zones || {}).length
            ? { covered_zones: g.covered_zones } : {}),
          ...(g.auto ? { auto: true }
                     : (g.covers.length > 1 ? { covers: g.covers.slice(1) } : {}))
        });
      });
      beneath.forEach(b => {
        const value = b.read();
        if (!value.beneath && !Object.keys(value.zones).length) return;
        const entry = out[b.region] || (out[b.region] = { garments: [], beneath: "" });
        entry.beneath = value.beneath;
        if (Object.keys(value.zones).length) entry.beneath_zones = value.zones;
      });
      return out;
    }
  };
}

function fList(label, items, addLabel, buildRow, newItem) {
  const wrap = el("div"), rows = [];
  const addRow = item => {
    const { node, read } = buildRow(item);
    const card = el("div", { class: "card row" }, node, el("button", { onclick: () => { card.remove(); rows.splice(rows.indexOf(card), 1) } }, "✕"));
    card._read = read;
    rows.push(card); wrap.append(card);
  };
  (items || []).forEach(addRow);
  const add = el("button", { onclick: () => addRow(newItem()) }, addLabel);
  return { node: el("div", { class: "ff" }, el("label", {}, label), wrap, add), read: () => rows.map(r => r._read()).filter(Boolean) };
}

function fAbilities(label, abilities) {
  return fList(label, abilities, "+ ability", a => {
    const n = el("input", { value: a.name || "", placeholder: "name", style: "flex:1" });
    const l = el("select", {}, ["novice", "competent", "expert", "master"].map(x => el("option", { value: x, ...(x === a.level ? { selected: "" } : {}) }, x)));
    const s = el("input", { value: a.scope || "", placeholder: "scope", style: "flex:1" });
    const lim = el("input", { value: a.limits || "", placeholder: "limits", style: "flex:1" });
    const no = el("input", { value: a.notes || "", placeholder: "notes", style: "flex:1" });
    return { node: [n, l, s, lim, no], read: () => ({ name: n.value, level: l.value, scope: s.value, limits: lim.value, notes: no.value }) };
  }, () => ({ name: "", level: "competent", scope: "", limits: "", notes: "" }));
}

function fTraits(label, traits) {
  return fList(label, traits, "+ trait", t => {
    const n = el("input", { value: t.name || "", placeholder: "name", style: "flex:1" });
    const s = el("input", { type: "number", step: "0.1", value: t.strength ?? 0.5, placeholder: "str", style: "width:60px" });
    const e = el("input", { value: t.expression || "", placeholder: "expression", style: "flex:1" });
    const ac = el("input", { value: (t.activation_cues || []).join(", "), placeholder: "activation cues", style: "flex:1" });
    const ib = el("input", { value: (t.inhibited_by || []).join(", "), placeholder: "inhibited by", style: "flex:1" });
    return { node: [n, s, e, ac, ib], read: () => ({
      name: n.value, strength: +s.value || 0, expression: e.value,
      activation_cues: splitCL(ac.value), inhibited_by: splitCL(ib.value)
    }) };
  }, () => ({ name: "", strength: 0.5, expression: "", activation_cues: [], inhibited_by: [] }));
}

function fValues(label, values) {
  return fList(label, values, "+ value", v => {
    const n = el("input", { value: v.name || "", placeholder: "name", style: "flex:1" });
    const p = el("input", { type: "number", step: "0.1", value: v.priority ?? 0.5, placeholder: "pri", style: "width:60px" });
    const e = el("input", { value: v.expression || "", placeholder: "behavioral expression", style: "flex:1" });
    const c = el("input", { value: (v.conflicts_with || []).join(", "), placeholder: "conflicts with", style: "flex:1" });
    return { node: [n, p, e, c], read: () => ({
      name: n.value, priority: +p.value || 0, expression: e.value,
      conflicts_with: splitCL(c.value)
    }) };
  }, () => ({ name: "", priority: 0.5, expression: "", conflicts_with: [] }));
}

function fBeliefs(label, beliefs) {
  return fList(label, beliefs, "+ belief", b => {
    const belief = el("input", { value: b.belief || "", placeholder: "self/world belief", style: "flex:2" });
    const confidence = el("input", { type: "number", min: "0", max: "1", step: "0.1", value: b.confidence ?? 0.5, title: "confidence", style: "width:70px" });
    const protectedBelief = el("input", { type: "checkbox", ...(b.protected ? { checked: "" } : {}), title: "Protected identity belief" });
    const charge = el("input", { type: "number", min: "-1", max: "1", step: "0.1", value: b.emotional_charge ?? 0, title: "emotional charge", style: "width:70px" });
    const source = el("input", { value: b.source || "", placeholder: "source/formative evidence", style: "flex:1" });
    return { node: [belief, confidence, el("label", { class: "tgl small" }, protectedBelief, " protected"), charge, source], read: () => ({
      belief: belief.value, confidence: +confidence.value || 0,
      protected: protectedBelief.checked, emotional_charge: +charge.value || 0,
      source: source.value
    }) };
  }, () => ({ belief: "", confidence: 0.5, protected: false, emotional_charge: 0, source: "" }));
}

function fCopingStrategies(label, strategies) {
  return fList(label, strategies, "+ coping strategy", s => {
    const name = el("input", { value: s.name || "", placeholder: "strategy", style: "flex:1" });
    const trigger = el("input", { value: s.trigger || "", placeholder: "trigger", style: "flex:1" });
    const response = el("input", { value: s.response || "", placeholder: "typical response", style: "flex:2" });
    const effectiveness = el("input", { type: "number", min: "0", max: "1", step: "0.1", value: s.effectiveness ?? 0.5, title: "effectiveness", style: "width:70px" });
    const costs = el("input", { value: s.costs || "", placeholder: "costs/tradeoffs", style: "flex:1" });
    return { node: [name, trigger, response, effectiveness, costs], read: () => ({
      name: name.value, trigger: trigger.value, response: response.value,
      effectiveness: +effectiveness.value || 0, costs: costs.value
    }) };
  }, () => ({ name: "", trigger: "", response: "", effectiveness: 0.5, costs: "" }));
}

function fAssociations(label, associations) {
  return fList(label, associations, "+ learned association", a => {
    const cue = el("input", { value: a.cue || "", placeholder: "cue", style: "flex:1" });
    const bias = el("input", { value: a.appraisal_bias || "", placeholder: "appraisal bias", style: "flex:1" });
    const response = el("input", { value: a.response_tendency || "", placeholder: "response tendency", style: "flex:1" });
    const strength = el("input", { type: "number", min: "0", max: "1", step: "0.1", value: a.strength ?? 0.5, title: "strength", style: "width:70px" });
    const tags = el("input", { value: (a.generalization_tags || []).join(", "), placeholder: "generalization tags", style: "flex:1" });
    return { node: [cue, bias, response, strength, tags], read: () => ({
      cue: cue.value, appraisal_bias: bias.value,
      response_tendency: response.value, strength: +strength.value || 0,
      generalization_tags: splitCL(tags.value)
    }) };
  }, () => ({ cue: "", appraisal_bias: "", response_tendency: "", strength: 0.5, generalization_tags: [] }));
}

function fGoals(label, goals) {
  return fList(label, goals, "+ goal", g => {
    const n = el("input", { value: g.goal || "", placeholder: "goal", style: "flex:1" });
    const p = el("input", { type: "number", step: "0.1", value: g.priority ?? 0.5, placeholder: "pri", style: "width:60px" });
    return { node: [n, p], read: () => ({ goal: n.value, priority: +p.value || 0 }) };
  }, () => ({ goal: "", priority: 0.5 }));
}

function fSenses(label, senses) {
  return fList(label, senses, "+ sense", s => {
    const ch = el("input", { value: s.channel || "", placeholder: "channel (vision, hearing…)", style: "flex:1" });
    const ac = el("input", { value: s.acuity || "", placeholder: "acuity (ordinary, keen…)", style: "flex:1" });
    const rg = el("input", { value: s.range || "", placeholder: "range (ordinary, long…)", style: "flex:1" });
    const no = el("input", { value: s.notes || "", placeholder: "notes", style: "flex:2" });
    return {
      node: [ch, ac, rg, no],
      read: () => ({ channel: ch.value, acuity: ac.value, range: rg.value, notes: no.value }),
    };
  }, () => ({ channel: "", acuity: "ordinary", range: "ordinary", notes: "" }));
}

function fLatent(label, latent) {
  return fList(label, latent, "+ latent capability", c => {
    const cap = el("input", { value: c.capability || "", placeholder: "capability", style: "flex:1" });
    const vw = el("input", { value: c.visible_when || "", placeholder: "visible when…", style: "flex:1" });
    const lim = el("input", { value: c.limits || "", placeholder: "limits", style: "flex:1" });
    return {
      node: [cap, vw, lim],
      read: () => ({ capability: cap.value, visible_when: vw.value, limits: lim.value }),
    };
  }, () => ({ capability: "", visible_when: "", limits: "" }));
}

// Structured extra body parts (tails, wings, horns, extra arms). WHERE is
// chosen from closed menus -- the attachment region reuses ATTIRE_REGIONS and
// the aspect names which face of it the part emerges from -- so the engine
// gates and renders the part deterministically instead of re-reading prose.
// The part noun itself stays free text: anatomy is open-ended, and the noun
// is also the handle contacts use ("her tail" grabs THIS tail).
const EXTRA_PART_ASPECTS = ["front", "back", "top", "underside", "left", "right", "sides"];
function fExtraParts(label, parts) {
  return fList(label, parts, "+ body part", x => {
    const kind = el("input", { value: x.kind || "", placeholder: "part (tail, wings, horns…)", style: "flex:1" });
    const count = el("input", { type: "number", min: "1", max: "12", step: "1", value: x.count ?? 1, title: "how many", style: "width:60px" });
    const at = el("select", { title: "emerges from which body region" },
      ATTIRE_REGIONS.map(r => el("option", { value: r, ...(r === (x.at || "waist") ? { selected: "" } : {}) }, r)));
    const aspect = el("select", { title: "which face of that region: front (in front) / back (behind) / top (above) / underside (below) / left / right / sides (one per side)" },
      EXTRA_PART_ASPECTS.map(a => el("option", { value: a, ...(a === (x.aspect || "back") ? { selected: "" } : {}) }, a)));
    const through = el("label", { class: "small", title: "clothing over that region is worn around the part (a tail through a skirt). Unchecked: the part is tucked beneath clothing and hidden while the region is covered." },
      el("input", { type: "checkbox" }), " through clothing");
    through.querySelector("input").checked = x.through_clothing !== false;
    const desc = el("input", { value: x.description || "", placeholder: "description (look, motion)", style: "flex:2" });
    return { node: [kind, count, at, aspect, through, desc], read: () => (kind.value.trim() ? {
      kind: kind.value.trim(), count: +count.value || 1, at: at.value, aspect: aspect.value,
      through_clothing: through.querySelector("input").checked, description: desc.value
    } : null) };
  }, () => ({ kind: "", count: 1, at: "waist", aspect: "back", through_clothing: true, description: "" }));
}

// The stations of a body's inside, OUTERMOST FIRST. The list ORDER is the
// topology -- the engine chains each station to the one before it and walks
// strictly deeper from the derived way in -- so dragging a row is an anatomy
// edit, not a display preference, and the up/down controls say so.
//
// `transit_seconds` blank means the station HOLDS its occupant until the story
// moves them, which is what a place to stay in is. A number means the clock
// carries them onward by itself once it is spent. The way in and out is never
// a station: it is derived from the body.
const INTERIOR_LIGHTS = ["dark", "dim", "lit", "bright"];
function fInteriorStations(label, stations) {
  const wrap = el("div"), rows = [];
  const move = (card, by) => {
    const at = rows.indexOf(card), to = at + by;
    if (at < 0 || to < 0 || to >= rows.length) return;
    rows.splice(at, 1); rows.splice(to, 0, card);
    wrap.replaceChildren(...rows);
  };
  const addRow = x => {
    x = x || {};
    const name = el("input", { value: x.name || "", placeholder: "station name (the handle the story says out loud)", style: "flex:1" });
    const desc = el("input", { value: x.desc || "", placeholder: "what standing there is like", style: "flex:2" });
    const light = el("select", { title: "how much can be seen there; unstated reads as dark" },
      INTERIOR_LIGHTS.map(v => el("option", { value: v, ...(v === (x.light || "dark") ? { selected: "" } : {}) }, v)));
    const barrier = el("input", { value: x.barrier || "", placeholder: "passage in (membrane)", style: "width:130px", title: "the passage from the station before this one. Blank means membrane — a body passes through, nothing sees through. The first station has none: the way in is derived from the body." });
    const transit = el("input", { type: "number", min: "0", step: "1", value: x.transit_seconds ?? "", placeholder: "crossing s", style: "width:110px", title: "how long passing through this station takes, in story seconds. Blank = the station holds its occupant until the story moves them." });
    const up = el("button", { title: "move outward (earlier in the chain)", onclick: () => move(card, -1) }, "↑");
    const down = el("button", { title: "move deeper (later in the chain)", onclick: () => move(card, +1) }, "↓");
    const card = el("div", { class: "card row" }, name, desc, light, barrier, transit, up, down,
      el("button", { title: "remove this station", onclick: () => { card.remove(); rows.splice(rows.indexOf(card), 1) } }, "✕"));
    card._read = () => {
      if (!name.value.trim()) return null;
      const row = { name: name.value.trim(), desc: desc.value, light: light.value, barrier: barrier.value.trim() };
      // Blank is "declares no crossing time", which is a different claim from
      // zero -- the engine reads 0 as unset and the editor must not spell one
      // as the other.
      const seconds = parseFloat(transit.value);
      if (transit.value !== "" && isFinite(seconds) && seconds > 0) row.transit_seconds = seconds;
      return row;
    };
    rows.push(card); wrap.append(card);
  };
  (stations || []).forEach(addRow);
  const add = el("button", { onclick: () => addRow({ light: "dark" }) }, "+ station");
  return {
    node: el("div", { class: "ff" }, el("label", {}, label), wrap, add),
    read: () => rows.map(r => r._read()).filter(Boolean),
  };
}

function fPronouns(label, pronouns) {
  const subj = el("input", { value: pronouns?.subject || "they", placeholder: "subject", style: "flex:1" });
  const obj = el("input", { value: pronouns?.object || "them", placeholder: "object", style: "flex:1" });
  const poss = el("input", { value: pronouns?.possessive || "their", placeholder: "possessive", style: "flex:1" });
  return {
    node: el("div", { class: "ff" }, el("label", {}, label), el("div", { class: "row" }, subj, obj, poss)),
    read: () => ({
      subject: subj.value || "they",
      object: obj.value || "them",
      possessive: poss.value || "their",
    }),
  };
}

function phEditor(entries, withAbout) {
  const wrap = el("div"), rows = [];
  const addRow = e => {
    const c = el("textarea", { style: "width:100%", rows: "2" }, e.content || "");
    const k = el("input", { style: "flex:1", placeholder: "known_by (comma-separated NAMES, matched exactly; empty = only owner)", value: (e.known_by || []).join(", ") });
    const a = withAbout ? el("input", { placeholder: "about (optional)", value: e.about || "" }) : null;
    const row = el("div", { class: "card" }, c, el("div", { class: "row" }, k, a, el("button", { onclick: () => { row.remove(); rows.splice(rows.indexOf(row), 1) } }, "✕")));
    row._read = () => ({ content: c.value, about: a ? a.value : undefined, known_by: k.value.split(",").map(s => s.trim()).filter(Boolean) });
    rows.push(row); wrap.append(row);
  };
  (entries || []).forEach(addRow);
  const add = el("button", { onclick: () => addRow({}) }, "+ private entry");
  return { node: el("div", {}, wrap, add), read: () => rows.map(r => r._read()).filter(e => e.content) };
}

// ---- Model picker ----
async function fetchModels(pid) {
  if (S.models[pid]) return S.models[pid];
  try { const r = await api("GET", `/api/providers/${pid}/models`); S.models[pid] = r.models; return r.models }
  catch (e) { return [] }
}
async function fetchImageModels(pid) {
  if (S.imageModels[pid]) return S.imageModels[pid];
  try { const r = await api("GET", `/api/providers/${pid}/image_models`); S.imageModels[pid] = r.models; return r.models }
  catch (e) { return [] }
}
// `opts.fetch`/`opts.cache` let the same widget drive a different catalogue
// (image models) without duplicating the dropdown, filtering and
// click-outside handling.
function modelCombobox(providers, cp, cm, onChange, opts) {
  const fetchList = (opts && opts.fetch) || fetchModels;
  const cache = (opts && opts.cache) || S.models;
  const psel = el("select", {}, [el("option", { value: "" }, "(provider)"),
  ...providers.map(p => el("option", { value: p.id, ...(String(p.id) === String(cp) ? { selected: "" } : {}) }, p.name))]);
  const minput = el("input", { style: "flex:1", placeholder: "search models…", value: cm || "", autocomplete: "off" });
  const dd = el("div", { class: "dd-panel" });
  const mwrap = el("div", { style: "position:relative;flex:1" }, minput, dd);
  let models = [];
  let onlyIncluded = false;
  let loadSeq = 0;
  function emitChange() {
    if (onChange) onChange({ provider: psel.value ? +psel.value : null, model: minput.value || null });
  }
  // `open` separates FETCHING the catalogue from SHOWING it. They used to be
  // the same act, which meant the priming call at the bottom of this function
  // -- made for every combobox that already has a provider saved -- opened its
  // dropdown as a side effect. Agent models builds one per role, so opening
  // API settings expanded a dozen model lists that nobody had clicked on, each
  // covering the rows beneath it.
  async function load(pid, { open = true } = {}) {
    if (!pid) { models = []; return }
    const seq = ++loadSeq;
    if (open) {
      dd.innerHTML = ""; dd.style.display = "block";
      dd.append(el("div", { class: "dd-opt dim" }, "Loading…"));
    }
    let loaded = [];
    try {
      loaded = await fetchList(pid);
    } catch {
      // A catalogue that will not load must not take the dropdown with it.
      // For the embeddings role the useful entries are `opts.extra` anyway --
      // providers do not list embedding models in /models at all -- so
      // rendering with an empty catalogue is strictly better than rendering
      // nothing and looking broken.
      loaded = [];
    }
    // Provider changes can overlap slow catalogue requests. Only the newest
    // request for the provider still selected may replace the dropdown.
    if (seq !== loadSeq || String(psel.value) !== String(pid)) return;
    models = loaded;
    if (open) showDD();
  }
  function showDD() {
    const q = minput.value.toLowerCase();
    let m = models.filter(x => x.id.toLowerCase().includes(q));
    if (onlyIncluded) m = m.filter(x => x.included);
    // A role may narrow the catalogue to the kind of model it can actually
    // use. Only the SUGGESTIONS are narrowed -- the field stays free text, so
    // a model the pattern does not recognise can still be typed in.
    let narrowed = false;
    if (opts && opts.suggest) {
      m = m.filter(opts.suggest);
      narrowed = true;
    }
    // Ids a role knows are good but the provider does not advertise. Merged
    // ahead of the catalogue and de-duplicated against it, and searched by
    // the same typed query so the field still behaves like one box.
    if (opts && opts.extra) {
      // Resolved against the SELECTED provider, because model ids are not
      // portable between them: OpenRouter wants `openai/text-embedding-3-small`
      // and `perplexity/pplx-embed-v1-4b`, NanoGPT wants the bare form and has
      // no Perplexity models at all. A single flat list showed NanoGPT ids
      // while OpenRouter was selected, which is worse than showing none.
      const chosen = providers.find(p => String(p.id) === String(psel.value));
      const list = typeof opts.extra === "function"
        ? (opts.extra(chosen) || []) : opts.extra;
      const have = new Set(m.map(x => x.id.toLowerCase()));
      const add = list
        .filter(x => x.id.toLowerCase().includes(q) && !have.has(x.id.toLowerCase()))
        .map(x => ({ id: x.id, badge: x.note || "suggested", included: false }));
      m = add.concat(m);
      narrowed = true;
    }
    m = m.slice(0, 80);
    dd.innerHTML = ""; dd.style.display = "block";
    const toggle = el("label", { class: "dd-opt dim", style: "cursor:pointer" },
      el("input", {
        type: "checkbox", style: "margin-right:6px",
        ...(onlyIncluded ? { checked: "" } : {}),
        onclick: e => { onlyIncluded = e.target.checked; showDD(); },
      }),
      "Show only models included in subscription");
    dd.append(toggle);
    if (opts && opts.suggestNote && narrowed) {
      dd.append(el("div", { class: "dd-opt dim" }, opts.suggestNote));
    }
    if (!m.length) {
      dd.append(el("div", { class: "dd-opt dim" },
        opts && opts.suggest
          ? "No matching models of this kind — you can still type an id."
          : "No matching models."));
      return;
    }
    for (const x of m) {
      const o = el("div", { class: "dd-opt", onclick: () => { minput.value = x.id; dd.style.display = "none"; emitChange() } },
        el("span", { style: "flex:1" }, x.id), el("span", { class: "badge" }, x.badge),
        x.ctx ? el("span", { class: "small dim" }, x.ctx + " ctx") : null);
      dd.append(o);
    }
  }
  minput.onfocus = async () => {
    if (psel.value && !cache[psel.value]) {
      // load() renders only if this request still owns the selected provider.
      // Do not unconditionally reopen the dropdown after a stale load returns.
      await load(+psel.value);
    } else {
      showDD();
    }
  };
  minput.oninput = () => { showDD(); emitChange() };
  const onDocClick = e => {
    // Self-remove once this combobox's DOM is detached (modal closed/rebuilt),
    // so we don't accumulate a document listener per instantiation.
    if (!mwrap.isConnected) { document.removeEventListener("click", onDocClick); return; }
    if (!mwrap.contains(e.target)) dd.style.display = "none";
  };
  document.addEventListener("click", onDocClick);
  psel.onchange = () => {
    minput.value = "";
    models = [];
    if (psel.value) {
      load(+psel.value);
    } else {
      // Clearing the provider also supersedes any catalogue still in flight.
      loadSeq++;
      dd.innerHTML = "";
      dd.style.display = "none";
    }
    emitChange();
  };
  // Primed, not opened: the catalogue is warmed so the first focus is instant,
  // and the dropdown stays shut until someone asks for it.
  if (cp) load(+cp, { open: false });
  return { psel, mwrap, minput, read: () => ({ provider: psel.value ? +psel.value : null, model: minput.value || null }) };
}
