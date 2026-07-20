function el(tag, attrs = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (k === "value") e.value = v;
    else if (k === "selected") e.selected = true;
    else if (k === "checked") e.checked = true;
    else if (v !== null && v !== false) e.setAttribute(k, v);
  }
  for (const k of kids.flat()) {
    if (k == null || k === false) continue;
    e.append(k.nodeType ? k : document.createTextNode(String(k)));
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

function modal(title, build, opts = {}) {
  const body = $("#modalbody");
  const box = $("#modalbox");
  if (!$("#modal").classList.contains("hidden")) {
    S.modalStack.push({
      title: $("#modaltitle").textContent,
      nodes: [...body.childNodes],
      wide: box.classList.contains("wide"),
    });
  }
  S.modalToken++;
  $("#modaltitle").textContent = title;
  box.classList.toggle("wide", !!opts.wide);
  body.innerHTML = "";
  build(body);
  $("#modal").classList.remove("hidden");
  requestAnimationFrame(() => {
    const f = body.querySelector("input:not([disabled]),textarea:not([disabled]),select:not([disabled])");
    if (opts.autoFocus !== false && f) f.focus();
  });
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
    return;
  }
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

  let resolved = false;
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

  return { cleanup, isResolved: () => resolved, markResolved: () => { resolved = true } };
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

// ---- Toasts ----
function toast(message, type = "ok", timeout = 4200) {
  const icon = { ok: "✓", err: "!", warn: "▲", info: "•" }[type] || "•";
  const node = el("div", { class: "toast " + type },
    el("span", { class: "badge " + type }, icon),
    el("div", { class: "toast-body" }, String(message)),
    el("button", { class: "ghost", title: "Dismiss", onclick: () => node.remove() }, "✕"));
  $("#toasts").append(node);
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
setInterval(() => { if (S.tasks.size) renderActivity() }, 1000);

function backgroundTask(label, work, opts = {}) {
  const id = ++S.taskSeq;
  S.tasks.set(id, { id, label, started: Date.now() });
  if (opts.closeModal !== false) closeModal();
  renderActivity();
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
function fStrList(label, vals) {
  const i = el("input", { value: (vals || []).join(", "), placeholder: "comma-separated", style: "width:100%" });
  return { node: el("div", { class: "ff" }, el("label", {}, label), i), read: () => i.value.split(",").map(s => s.trim()).filter(Boolean) };
}

function fList(label, items, addLabel, buildRow, newItem) {
  const wrap = el("div"), rows = [];
  const addRow = item => {
    const { node, read, remove } = buildRow(item);
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
    return { node: [n, s, e], read: () => ({ name: n.value, strength: +s.value || 0, expression: e.value }) };
  }, () => ({ name: "", strength: 0.5, expression: "" }));
}

function fValues(label, values) {
  return fList(label, values, "+ value", v => {
    const n = el("input", { value: v.name || "", placeholder: "name", style: "flex:1" });
    const p = el("input", { type: "number", step: "0.1", value: v.priority ?? 0.5, placeholder: "pri", style: "width:60px" });
    return { node: [n, p], read: () => ({ name: n.value, priority: +p.value || 0 }) };
  }, () => ({ name: "", priority: 0.5 }));
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
    const k = el("input", { style: "flex:1", placeholder: "known_by (comma-separated; empty = only owner)", value: (e.known_by || []).join(", ") });
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
function modelCombobox(providers, cp, cm, onChange) {
  const psel = el("select", {}, [el("option", { value: "" }, "(provider)"),
  ...providers.map(p => el("option", { value: p.id, ...(String(p.id) === String(cp) ? { selected: "" } : {}) }, p.name))]);
  const minput = el("input", { style: "flex:1", placeholder: "search models…", value: cm || "", autocomplete: "off" });
  const dd = el("div", { class: "dd-panel" });
  const mwrap = el("div", { style: "position:relative;flex:1" }, minput, dd);
  let models = [];
  let onlyIncluded = false;
  function emitChange() {
    if (onChange) onChange({ provider: psel.value ? +psel.value : null, model: minput.value || null });
  }
  async function load(pid) {
    if (!pid) { models = []; return }
    dd.innerHTML = ""; dd.style.display = "block"; dd.append(el("div", { class: "dd-opt dim" }, "Loading…"));
    models = await fetchModels(pid); showDD();
  }
  function showDD() {
    const q = minput.value.toLowerCase();
    let m = models.filter(x => x.id.toLowerCase().includes(q));
    if (onlyIncluded) m = m.filter(x => x.included);
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
    if (!m.length) {
      dd.append(el("div", { class: "dd-opt dim" }, "No matching models."));
      return;
    }
    for (const x of m) {
      const o = el("div", { class: "dd-opt", onclick: () => { minput.value = x.id; dd.style.display = "none"; emitChange() } },
        el("span", { style: "flex:1" }, x.id), el("span", { class: "badge" }, x.badge),
        x.ctx ? el("span", { class: "small dim" }, x.ctx + " ctx") : null);
      dd.append(o);
    }
  }
  minput.onfocus = async () => { if (psel.value && !S.models[psel.value]) await load(+psel.value); showDD() };
  minput.oninput = () => { showDD(); emitChange() };
  const onDocClick = e => {
    // Self-remove once this combobox's DOM is detached (modal closed/rebuilt),
    // so we don't accumulate a document listener per instantiation.
    if (!mwrap.isConnected) { document.removeEventListener("click", onDocClick); return; }
    if (!mwrap.contains(e.target)) dd.style.display = "none";
  };
  document.addEventListener("click", onDocClick);
  psel.onchange = () => { minput.value = ""; if (psel.value) load(+psel.value); emitChange() };
  if (cp) load(+cp);
  return { psel, mwrap, minput, read: () => ({ provider: psel.value ? +psel.value : null, model: minput.value || null }) };
}