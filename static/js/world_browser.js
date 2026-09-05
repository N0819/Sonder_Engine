"use strict";

// ---- The World Browser ----
//
// The room-centred view of the world state behind the 🌍 and 👕 buttons,
// and since 2026-09-04 its EDITOR: three tabs in one dialog.
//
//   Rooms   -- a tree of every room the story knows on the left, the selected
//              room on the right. Every field the card shows is edited where
//              it is shown: name, description, notes, light / size / exposure
//              (selects over the engine's own sets), region (a datalist of
//              the map's regions), exits (barrier and bearing per doorway,
//              remove, add -- the far room's edge is written too, because a
//              doorway is one object), anchors (description, bearing, and the
//              three geometry words), the things standing here (kind,
//              description, portable, light, lit, move), and each body's
//              station (the anchor it stands at, who it stands beside).
//   Bodies  -- every body the scene knows -- cast, player, promoted presence
//              -- with its room, station, pose, and its FULL attire ledger,
//              editable: a garment's state and condition, add and remove,
//              the region a garment is worn under, the free notes.
//   Raw JSON -- the two editors that used to be the whole of these buttons,
//              unchanged: the world table (🌍) or the attire ledger (👕),
//              whole-body PUTs. The REPAIR path, kept because hand repair of
//              a drifted scene is how the owner fixes one.
//
// Reads `web/world_routes.py`: the index (`groups`, `bodies`, `vocab`) and
// the slice (`record`, `stationable`), both transport over
// `story/room_slice.py` -- the ONE reader the Writers' Room's `inspect_rooms`
// and the frontier also use, so the host and the Planner see one world.
//
// Writes, each narrow and each validated by the server against the SAME sets
// the menus are built from: `PATCH /rooms/{id}` (changed fields only; exits
// and anchors as this room's full list), `PATCH /rooms/{id}/entities/{eid}`,
// `PUT /bodies/{name}/station`, and the two writes the app already had --
// "Move here" is the cast editor's `PUT /characters/{ch}/position`, and every
// attire edit sends the WHOLE ledger to `PUT /attire`, which re-derives each
// entry (`story.attire.rederive_entry`). The ledger stores a garment
// covering several regions ONCE PER REGION; this editor groups the copies
// by name into one garment (`wbGroupGarments`), edits that, and writes every
// copy back with the same state (`wbLedgerEntry`) -- so a kimono loosened at
// the torso is loosened at the legs, and a garment is never narrowed to the
// region it happened to be edited under, nor its state reset to "worn". Those
// two were the faults that made the card editor (`fAttireGarments`) unusable
// here (`docs/UNBUILT.md` § 2.26, now closed).
//
// NO CLOSED SET IS TYPED INTO THIS FILE. Every select reads `index.vocab`,
// which the route builds from the engine's constants, so a menu cannot drift
// from the code.
//
// Edits are EXPLICIT: a text input commits on blur or Enter (Escape reverts
// the unsaved text), a select on change, a checkbox on change; a toast says
// "Saved." on success and repeats the server's refusal on failure, and the
// card is re-rendered from the server's answer either way -- never a silent
// revert.
//
// Reads the story-view globals it needs (S.chatId, S.currentFrameId) and the
// shared helpers ($, el, txt, api, t, toast, modal, closeModal,
// modalOwnership). `frameQuery` and `castRoomLabel` are settings.js's and
// are only ever reached from a click, after every script has loaded.

// The tree's groups, in display order, with their headings. `retired` is
// collapsed under its heading: the ids are spent and are listed so a reader
// knows they are, never as places.
const WB_GROUPS = [
  ["cast", "Where the cast stands"],
  ["reachable", "Reachable from the cast"],
  ["unreachable", "Not yet reachable"],
  ["retired", "Retired"],
];

function wbStatusBadge(status) {
  // Only the two statuses that change what a room IS. A live room needs no
  // badge; an id known to nothing (an exit pointing off the map) says so.
  if (status === "planned") return el("span", { class: "badge warn" }, "Planned");
  if (status === "retired") return el("span", { class: "badge err" }, "Retired");
  if (status == null) return el("span", { class: "badge" }, "Unknown");
  return null;
}

function wbRoomLabel(row) {
  // An interior room is named with what it is inside, as the cast editor
  // names it: "Console Room" alone does not say which ship.
  return castRoomLabel({ name: row.name, parent_name: row.holder_name || null });
}

// ---- Edit controls -----------------------------------------------------------

// A select over one of the engine's closed sets. `blank` adds a first option
// whose value is "" -- "leave unset", which the server reads as "clear".
function wbSelect(options, value, { blank = null, title = null, onchange, labels = null } = {}) {
  const select = el("select", { class: "wb-select", ...(title ? { title } : {}),
                                onchange: e => onchange(e.target.value) });
  if (blank !== null) select.append(el("option", { value: "" }, blank));
  for (const option of options || []) {
    const opt = el("option", { value: String(option), translate: "no" },
      txt(labels ? labels(option) : option));
    if (String(option) === String(value ?? "")) opt.selected = true;
    select.append(opt);
  }
  if (blank !== null && !(options || []).some(o => String(o) === String(value ?? ""))) {
    select.value = "";
  }
  return select;
}

// A text control that commits on blur or Enter and reverts on Escape. Only a
// CHANGED value is sent: tabbing through a field is not an edit.
function wbText(value, save, { multiline = false, placeholder = "", title = null } = {}) {
  const attrs = { class: multiline ? "wb-textarea" : "wb-input", translate: "no",
                  ...(placeholder ? { placeholder } : {}), ...(title ? { title } : {}) };
  const input = multiline ? el("textarea", attrs) : el("input", { type: "text", ...attrs });
  input.value = value == null ? "" : String(value);
  let settled = input.value;
  const commit = async () => {
    if (input.value === settled) return;
    const next = input.value;
    settled = next;
    await save(next);
  };
  input.addEventListener("blur", commit);
  input.addEventListener("keydown", e => {
    if (e.key === "Enter" && !multiline) { e.preventDefault(); input.blur(); }
    if (e.key === "Escape") { input.value = settled; input.blur(); }
  });
  return input;
}

// One write, one outcome the host can see. On success the card re-renders
// from the server's fresh answer; on failure the refusal is the toast and the
// card re-renders from what the server still holds. Nothing reverts silently.
async function wbWrite(ctx, call, { quiet = false } = {}) {
  try {
    const result = await call();
    if (!quiet) toast("Saved.", "ok");
    return result;
  } catch (error) {
    toast(error?.message || String(error), "err", 8000);
    await ctx.refresh();
    return null;
  }
}

// ---- The tree -------------------------------------------------------------

function wbRenderTree(host, index, selectedId, onSelect) {
  host.innerHTML = "";
  const groups = index.groups || {};
  const rows = new Map();
  for (const key of Object.keys(groups)) {
    for (const row of groups[key] || []) rows.set(row.id, row);
  }
  // An interior room nests under the room its holder stands in, when that
  // room is listed. Nesting is one level deep by construction (a room is the
  // inside of a body, and a body stands in a room), but the guard against a
  // self-reference costs nothing.
  const children = new Map();
  const nested = new Set();
  for (const row of rows.values()) {
    const parent = row.holder_room;
    if (!parent || parent === row.id || !rows.has(parent)
        || row.status === "retired") continue;
    if (!children.has(parent)) children.set(parent, []);
    children.get(parent).push(row);
    nested.add(row.id);
  }

  const button = (row, depth) => {
    const b = el("button", {
      class: "wb-room" + (row.id === selectedId ? " on" : "")
        + (row.status === "planned" ? " planned" : "")
        + (row.status === "retired" ? " retired" : ""),
      "data-room": row.id,
      title: row.id,
      onclick: () => onSelect(row.id),
    },
      el("span", { class: "wb-name", translate: "no" },
        txt(depth ? "› " + row.name : wbRoomLabel(row))),
      row.occupants && row.occupants.length
        ? el("span", { class: "wb-occupants dim", translate: "no" },
            txt(row.occupants.join(", ")))
        : null,
      row.hops != null && row.hops > 0
        ? el("span", { class: "small dim",
                       title: "Rooms between here and the nearest cast member" },
            `${row.hops} hops`)
        : null,
      wbStatusBadge(row.status));
    const wrap = el("div", { class: depth ? "wb-nested" : "" }, b);
    for (const child of children.get(row.id) || []) {
      if (child.id === row.id) continue;
      wrap.append(button(child, depth + 1));
    }
    return wrap;
  };

  let any = false;
  for (const [key, heading] of WB_GROUPS) {
    const listed = (groups[key] || []).filter(r => !nested.has(r.id));
    if (!listed.length) continue;
    any = true;
    const body = el("div", {}, ...listed.map(row => button(row, 0)));
    if (key === "retired") {
      host.append(el("details", { class: "wb-retired" },
        el("summary", { class: "wb-group" }, heading, " ",
          el("span", { class: "badge" }, txt(String(listed.length)))),
        body));
    } else {
      host.append(el("div", { class: "wb-group" }, heading), body);
    }
  }
  if (!any) {
    host.append(el("div", { class: "small dim" },
      "No rooms yet — the scene has not been laid out."));
  }
}

// ---- The room card --------------------------------------------------------

function wbSection(title, ...kids) {
  return el("div", { class: "wb-section" }, el("h4", {}, title), ...kids);
}

function wbIndexRows(index) {
  const out = [];
  for (const key of Object.keys(index.groups || {})) {
    for (const row of index.groups[key] || []) out.push(row);
  }
  return out;
}

function wbStationText(station) {
  // `scene.stations[name]` is `{at: anchor|null, near: [names]}`: what the
  // body stands at, and who it stands beside.
  if (!station || typeof station !== "object") return null;
  const near = Array.isArray(station.near) ? station.near.filter(Boolean) : [];
  if (!station.at && !near.length) return null;
  return el("span", { class: "small dim" }, " · ",
    station.at ? el("span", { translate: "no" }, txt(station.at)) : null,
    near.length ? [station.at ? ", " : "", "Near", " ",
                   el("span", { translate: "no" }, txt(near.join(", ")))] : null);
}

function wbPoseText(pose) {
  if (!pose || typeof pose !== "object") return "";
  return ["posture", "support", "relation", "relative_to", "constraint", "detail"]
    .map(k => pose[k]).filter(v => v && String(v).trim()).join(" · ");
}

function wbMoveControl(slice, positions, chatId, ctx) {
  // "Move here": the cast editor's relocation, aimed at this room. Only a
  // LIVE room can receive a body (the route validates the id against the
  // scene), and only the registered cast can be moved -- the player's own
  // position is the story's business, as the cast editor also holds.
  if (slice.status !== "live" || !positions) return null;
  const here = new Set((slice.occupants || []).map(o => o.name));
  const movable = (positions.characters || []).filter(c => !here.has(c.name));
  if (!movable.length) return null;
  const select = el("select", { class: "cast-room-select", title: "Who to move into this room" },
    ...movable.map(c => el("option", { value: String(c.id), translate: "no" }, txt(c.name))));
  const button = el("button", { class: "small", onclick: async () => {
    const who = movable.find(c => String(c.id) === select.value);
    if (!who) return;
    button.disabled = true;
    try {
      const done = await wbWrite(ctx, () => api("PUT",
        `/api/chats/${chatId}/characters/${who.id}/position${frameQuery()}`,
        { room: slice.id }), { quiet: true });
      if (done) {
        toast(`Moved ${who.name} here.`, "ok");
        await ctx.refresh();
      }
    } finally {
      button.disabled = false;
    }
  } }, "Move here");
  return el("div", { class: "row", style: "margin-top:6px" }, select, button);
}

// The room's fields: a PATCH of just the one that changed, the card rebuilt
// from the slice the server hands back.
function wbRoomFields(slice, ctx) {
  const record = slice.record;
  const vocab = ctx.vocab;
  const patch = fields => wbWrite(ctx, async () => {
    const fresh = await api("PATCH",
      `/api/chats/${ctx.chatId}/rooms/${encodeURIComponent(slice.id)}${frameQuery()}`,
      fields);
    await ctx.replaceCard(fresh);
    return fresh;
  });
  const field = (label, control) => el("label", { class: "wb-field" },
    el("span", { class: "small dim" }, label), control);
  const regionsList = el("datalist", { id: "wb-regions-list" },
    ...(vocab.regions || []).map(r => el("option", { value: r.id, translate: "no" },
      txt(r.name && r.name !== r.id ? r.name : ""))));
  const regionInput = wbText(record.region, value => patch({ region: value }),
    { placeholder: "Which part of the map" });
  regionInput.setAttribute("list", "wb-regions-list");
  return el("div", { class: "wb-fields" },
    field("Light", wbSelect(vocab.light, record.light,
      { blank: "—", onchange: v => patch({ light: v }) })),
    field("Size", wbSelect(vocab.size, record.size,
      { blank: "—", onchange: v => patch({ size: v }) })),
    field("Exposure", wbSelect(vocab.exposure, record.exposure,
      { blank: "—", onchange: v => patch({ exposure: v }) })),
    field("Region", el("span", {}, regionInput, regionsList)));
}

// Exits: the way the world is walked, and now the way a doorway is authored.
// The editable rows are this room's STORED edges (`record.adjacent`); an exit
// the slice derives from the far side's declaration, or from the plan's stub,
// is shown as a link with where it came from.
function wbExits(slice, ctx) {
  const vocab = ctx.vocab;
  const stored = slice.record ? slice.record.adjacent || [] : null;
  const patchExits = exits => wbWrite(ctx, async () => {
    const fresh = await api("PATCH",
      `/api/chats/${ctx.chatId}/rooms/${encodeURIComponent(slice.id)}${frameQuery()}`,
      { exits });
    await ctx.replaceCard(fresh);
    return fresh;
  });
  const asExit = e => ({ to: e.to, barrier: e.barrier || "", dir: e.dir || "" });
  const byTo = new Map((slice.exits || []).map(x => [x.to, x]));
  const rows = [];
  if (stored) {
    for (const edge of stored) {
      const far = byTo.get(edge.to) || { to: edge.to, name: edge.to, status: null };
      const mine = stored.map(asExit);
      const update = (changes) => patchExits(
        mine.map(x => x.to === edge.to ? { ...x, ...changes } : x));
      rows.push(el("div", { class: "wb-exit" },
        el("button", { class: "wb-link", translate: "no",
                       onclick: () => ctx.select(edge.to) }, txt(far.name || edge.to)),
        wbStatusBadge(far.status),
        wbSelect(vocab.barriers, edge.barrier || "",
          { title: "Barrier", onchange: v => update({ barrier: v }) }),
        wbSelect(vocab.dirs, edge.dir || "",
          { blank: "—", title: "Bearing", onchange: v => update({ dir: v }) }),
        el("button", { class: "small wb-remove", title: "Remove this exit",
                       onclick: () => patchExits(mine.filter(x => x.to !== edge.to)) },
          "✕")));
    }
  }
  const storedTo = new Set((stored || []).map(e => e.to));
  for (const x of slice.exits || []) {
    if (storedTo.has(x.to)) continue;
    rows.push(el("div", { class: "wb-exit" },
      el("button", { class: "wb-link", translate: "no",
                     onclick: () => ctx.select(x.to) }, txt(x.name || x.to)),
      (x.barrier || x.dir)
        ? el("span", { class: "small dim", translate: "no" },
            txt([x.barrier, x.dir].filter(Boolean).join(", ")))
        : null,
      wbStatusBadge(x.status),
      stored ? el("span", { class: "small dim" },
        slice.planned_stub ? "From the plan" : "Declared from the far side") : null));
  }
  const kids = [rows.length ? el("div", {}, ...rows)
                            : el("div", { class: "small dim" }, "No exits recorded.")];
  if (stored) {
    // Add an exit: any room the story knows that is not this one and is not
    // already a doorway of it -- live or planned.
    const candidates = wbIndexRows(ctx.index)
      .filter(r => r.id !== slice.id && r.status !== "retired" && !storedTo.has(r.id));
    if (candidates.length) {
      const target = el("select", { class: "wb-select", title: "Where the new exit leads" },
        ...candidates.map(r => el("option", { value: r.id, translate: "no" },
          txt(r.status === "planned" ? `${wbRoomLabel(r)} (${t("Planned")})` : wbRoomLabel(r)))));
      const barrier = wbSelect(vocab.barriers, (vocab.barriers || [])[0] || "",
        { title: "Barrier", onchange: () => {} });
      const dir = wbSelect(vocab.dirs, "", { blank: "—", title: "Bearing", onchange: () => {} });
      kids.push(el("div", { class: "wb-exit wb-add" },
        target, barrier, dir,
        el("button", { class: "small", onclick: () => patchExits(
          stored.map(asExit).concat([{ to: target.value, barrier: barrier.value,
                                       dir: dir.value }])) },
          "Add exit")));
    }
  }
  return wbSection("Exits", ...kids);
}

// Anchors: the room's named features, each with a wall and its geometry.
function wbAnchors(slice, ctx) {
  if (!slice.record) return null;
  const vocab = ctx.vocab;
  const anchors = slice.record.anchors || {};
  const patchAnchors = next => wbWrite(ctx, async () => {
    const fresh = await api("PATCH",
      `/api/chats/${ctx.chatId}/rooms/${encodeURIComponent(slice.id)}${frameQuery()}`,
      { anchors: next });
    await ctx.replaceCard(fresh);
    return fresh;
  });
  const copy = () => {
    const out = {};
    for (const [aid, a] of Object.entries(anchors)) out[aid] = { ...a };
    return out;
  };
  const update = (aid, changes) => {
    const next = copy();
    next[aid] = { ...next[aid], ...changes };
    return patchAnchors(next);
  };
  const rows = Object.entries(anchors).map(([aid, a]) => el("div", { class: "wb-exit" },
    el("span", { class: "small dim", translate: "no", title: "Anchor id" }, txt(aid)),
    wbText(a.desc || "", v => update(aid, { desc: v }), { placeholder: "Description" }),
    wbSelect(vocab.dirs, a.dir || "", { blank: "—", title: "Bearing",
                                        onchange: v => update(aid, { dir: v }) }),
    wbSelect(vocab.heights, a.height || "", { blank: "—", title: "Height",
                                              onchange: v => update(aid, { height: v }) }),
    wbSelect(vocab.footprints, a.footprint || "", { blank: "—", title: "Footprint",
                                                    onchange: v => update(aid, { footprint: v }) }),
    wbSelect(vocab.opacities, a.opacity || "", { blank: "—", title: "Opacity",
                                                 onchange: v => update(aid, { opacity: v }) }),
    el("button", { class: "small wb-remove", title: "Remove this anchor", onclick: () => {
      const next = copy();
      delete next[aid];
      return patchAnchors(next);
    } }, "✕")));
  const desc = el("input", { type: "text", class: "wb-input", translate: "no",
                             placeholder: "A feature prose refers to — the hearth, the bar" });
  const add = () => {
    const text = desc.value.trim();
    if (!text) return;
    const next = copy();
    next[""] = { desc: text };
    return patchAnchors(next);
  };
  desc.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); add(); } });
  return wbSection("Anchors",
    rows.length ? el("div", {}, ...rows)
                : el("div", { class: "small dim" }, "No anchors recorded."),
    el("div", { class: "wb-exit wb-add" }, desc,
      el("button", { class: "small", onclick: add }, "Add anchor")));
}

// A body in the room: its station edited here, its attire on the Bodies tab.
function wbOccupant(o, slice, ctx) {
  const stationable = slice.stationable || [];
  const station = o.station || { at: null, near: [] };
  const others = (slice.occupants || []).map(x => x.name).filter(n => n !== o.name);
  const put = body => wbWrite(ctx, async () => {
    await api("PUT",
      `/api/chats/${ctx.chatId}/bodies/${encodeURIComponent(o.name)}/station${frameQuery()}`,
      body);
    await ctx.refresh();
    return true;
  });
  const near = new Set(Array.isArray(station.near) ? station.near : []);
  const garments = o.attire && Array.isArray(o.attire.wearing) ? o.attire.wearing.length : null;
  return el("div", { class: "wb-body" },
    el("div", { class: "row wb-body-head" },
      el("b", { translate: "no" }, txt(o.name)),
      garments != null ? el("span", { class: "small dim" }, `Garments: ${garments}`) : null,
      el("button", { class: "wb-link", onclick: () => ctx.showBody(o.name) }, "Attire")),
    slice.status === "live" ? el("div", { class: "wb-exit" },
      el("span", { class: "small dim" }, "At"),
      wbSelect(stationable.map(a => a.id), station.at || "",
        { blank: "—", title: "The anchor this body stands at",
          labels: id => {
            const a = stationable.find(x => x.id === id);
            return a && a.desc && a.desc !== id ? `${a.desc} (${id})` : id;
          },
          onchange: v => put({ at: v || null, near: [...near] }) }),
      others.length ? el("span", { class: "small dim" }, "Near") : null,
      ...others.map(name => el("label", { class: "wb-check" },
        el("input", { type: "checkbox", ...(near.has(name) ? { checked: true } : {}),
                      onchange: e => {
                        const next = new Set(near);
                        if (e.target.checked) next.add(name); else next.delete(name);
                        return put({ at: station.at || null, near: [...next] });
                      } }),
        el("span", { translate: "no" }, txt(name))))) : null);
}

// A thing in the room: its fields, and a move.
function wbThing(th, slice, ctx) {
  const vocab = ctx.vocab;
  const patch = fields => wbWrite(ctx, async () => {
    const fresh = await api("PATCH",
      `/api/chats/${ctx.chatId}/rooms/${encodeURIComponent(slice.id)}/entities/${encodeURIComponent(th.id)}${frameQuery()}`,
      fields);
    await ctx.replaceCard(fresh);
    return fresh;
  });
  const record = th.record || {};
  const lit = record.state && typeof record.state === "object" ? record.state.lit : undefined;
  const liveRooms = wbIndexRows(ctx.index).filter(r => r.status === "live" && r.id !== slice.id);
  const moveTo = el("select", { class: "wb-select", title: "Move this thing to another room" },
    ...liveRooms.map(r => el("option", { value: r.id, translate: "no" }, txt(wbRoomLabel(r)))));
  return el("div", { class: "wb-thing" },
    el("div", { class: "wb-exit" },
      el("b", { translate: "no" }, txt(th.name)),
      th.plan_ref ? el("span", { class: "badge", title: th.plan_ref }, "From the plan") : null,
      wbText(th.kind || "", v => patch({ kind: v }), { placeholder: "Kind" }),
      el("label", { class: "wb-check" },
        el("input", { type: "checkbox", ...(record.portable ? { checked: true } : {}),
                      onchange: e => patch({ portable: e.target.checked }) }),
        "Portable"),
      el("span", { class: "small dim" }, "Light"),
      wbSelect(vocab.light, record.light_source || "",
        { blank: "—", title: "The light this thing gives off",
          onchange: v => patch({ light_source: v }) }),
      record.light_source ? el("label", { class: "wb-check" },
        el("input", { type: "checkbox", ...(lit !== false ? { checked: true } : {}),
                      onchange: e => patch({ lit: e.target.checked }) }),
        "Lit") : null),
    el("div", { class: "wb-exit" },
      wbText(record.description || "", v => patch({ description: v }),
        { placeholder: "Description", multiline: true }),
      th.placed === "position" && liveRooms.length ? [moveTo,
        el("button", { class: "small", onclick: () => patch({ room: moveTo.value }) }, "Move")]
        : null));
}

function wbRenderCard(host, slice, ctx) {
  host.innerHTML = "";
  if (!slice) {
    host.append(el("div", { class: "small dim" }, "Pick a room on the left."));
    return;
  }
  const record = slice.record;
  const patch = fields => wbWrite(ctx, async () => {
    const fresh = await api("PATCH",
      `/api/chats/${ctx.chatId}/rooms/${encodeURIComponent(slice.id)}${frameQuery()}`,
      fields);
    await ctx.replaceCard(fresh);
    return fresh;
  });
  const head = el("div", { class: "row", style: "align-items:baseline" },
    record
      ? (() => { const n = wbText(slice.name, v => patch({ name: v }), { title: "Room name" });
                 n.classList.add("wb-title"); return n; })()
      : el("h3", { style: "margin:0", translate: "no" }, txt(slice.name)),
    wbStatusBadge(slice.status),
    el("span", { class: "small dim", translate: "no" }, txt(slice.id)));
  host.append(head);
  if (slice.holder) {
    host.append(el("div", { class: "small dim" }, "Inside", " ",
      el("b", { translate: "no" }, txt(slice.holder_name || slice.holder))));
  }
  const move = wbMoveControl(slice, ctx.positions, ctx.chatId, ctx);
  if (move) host.append(move);

  if (record) {
    host.append(wbRoomFields(slice, ctx));
    host.append(wbText(record.desc, v => patch({ desc: v }),
      { multiline: true, placeholder: "No description yet." }));
    host.append(wbSection("Notes", wbText(record.notes, v => patch({ notes: v }),
      { multiline: true, placeholder: "Standing facts about this room" })));
  } else {
    host.append(slice.description
      ? el("p", { class: "wb-desc", translate: "no" }, txt(slice.description))
      : el("p", { class: "small dim" }, "No description yet."));
  }

  host.append(wbExits(slice, ctx));
  const anchors = wbAnchors(slice, ctx);
  if (anchors) host.append(anchors);

  // Who is here, each row with its station; attire is the Bodies tab's.
  const occupants = slice.occupants || [];
  host.append(wbSection("Who is here",
    occupants.length
      ? el("div", {}, ...occupants.map(o => wbOccupant(o, slice, ctx)))
      : el("div", { class: "small dim" }, "Nobody is here.")));

  const things = slice.things || [];
  host.append(wbSection("Things",
    things.length
      ? el("div", {}, ...things.map(th => record ? wbThing(th, slice, ctx)
          : el("div", { class: "wb-exit" },
              el("span", { translate: "no" }, txt(th.name)),
              th.kind ? el("span", { class: "small dim", translate: "no" }, txt(th.kind)) : null)))
      : el("div", { class: "small dim" }, "Nothing else here.")));

  const stub = slice.planned_stub;
  if (stub) {
    host.append(wbSection("Still the plan's stub",
      el("div", { class: "small" },
        el("span", { class: "dim" }, "Purpose:"), " ",
        el("span", { translate: "no" }, txt(stub.purpose || "—"))),
      el("div", { class: "small" },
        el("span", { class: "dim" }, "Access:"), " ",
        el("span", { translate: "no" }, txt(stub.access || "—"))),
      (stub.exits || []).length
        ? el("div", { class: "small" },
            el("span", { class: "dim" }, "Planned exits:"), " ",
            el("span", { translate: "no" },
              txt(stub.exits.map(x => x.name || x.to).join(", "))))
        : null));
  }

  // The author layer's claims on the room: planned bodies whose brief puts
  // them here, open planning needs naming it, and every unsealed package
  // operation that does. Sealed packages contribute nothing by design.
  const plan = slice.plan_here || {};
  const planned = plan.planned_entities || [];
  const needs = plan.needs || [];
  const ops = plan.package_ops || [];
  host.append(wbSection("The plan here",
    (planned.length || needs.length || ops.length)
      ? el("div", {},
          ...planned.map(p => el("div", { class: "wb-exit" },
            el("span", { class: "small dim", translate: "no" }, txt(p.kind)),
            el("span", { translate: "no" }, txt(p.name)),
            el("span", { class: "badge " + (p.rendered ? "ok" : "") },
              p.rendered ? "Rendered" : "Not yet rendered"))),
          ...needs.map(n => el("div", { class: "wb-exit" },
            el("span", { class: "badge warn" }, "Open need"),
            el("span", { class: "small dim", translate: "no" }, txt(n.kind)),
            el("span", { translate: "no" }, txt(n.subject)))),
          ...ops.map(o => el("div", { class: "wb-exit" },
            el("span", { class: "badge" }, txt(o.status)),
            el("span", { translate: "no" }, txt(o.title)),
            el("span", { class: "small dim", translate: "no" },
              txt(`${o.op} #${o.index + 1}`)))))
      : el("div", { class: "small dim" }, "The plan makes no claim on this room.")));
}

// ---- The Bodies tab: every body, and the attire editor -----------------------

// The ledger's per-region copies of a garment, grouped back into ONE garment
// with the regions it covers, in the ledger's region order. The copies are
// one garment by name (`story.attire._sync_spanning_garments` keeps them in
// step by the same key), so the first copy's fields stand for all.
function wbGroupGarments(entry, regionOrder) {
  const regions = entry && entry.regions && typeof entry.regions === "object" ? entry.regions : {};
  const order = regionOrder.concat(Object.keys(regions).filter(r => !regionOrder.includes(r)));
  const garments = [];
  const byKey = new Map();
  for (const region of order) {
    const slot = regions[region];
    if (!slot || typeof slot !== "object") continue;
    for (const raw of slot.garments || []) {
      const g = typeof raw === "string" ? { name: raw } : raw;
      if (!g || typeof g !== "object" || !g.name) continue;
      const key = String(g.name).trim().toLowerCase();
      let garment = byKey.get(key);
      if (!garment) {
        garment = { ...g, name: String(g.name).trim(), regions: [] };
        delete garment.covers;
        byKey.set(key, garment);
        garments.push(garment);
      }
      if (!garment.regions.includes(region)) garment.regions.push(region);
    }
  }
  return { order, garments };
}

// The ledger entry rebuilt from the edited garments: every garment written
// under EVERY region it covers, each copy carrying the same state and
// condition and the `covers` list, so the server's re-derivation sees one
// garment and never a narrowed one. Per-region facts the editor does not
// touch (`beneath_zones`, `uncovered`) survive from the stored slot.
function wbLedgerEntry(entry, garments, beneath, notes) {
  const stored = entry && entry.regions && typeof entry.regions === "object" ? entry.regions : {};
  const regions = {};
  for (const g of garments) {
    const copy = { ...g };
    delete copy.regions;
    copy.covers = g.regions.length > 1 ? [...g.regions] : [];
    for (const region of g.regions) {
      if (!regions[region]) {
        const slot = stored[region] && typeof stored[region] === "object" ? stored[region] : {};
        regions[region] = { ...slot, garments: [], beneath: beneath[region] ?? slot.beneath ?? "" };
      }
      regions[region].garments.push({ ...copy });
    }
  }
  for (const [region, text] of Object.entries(beneath)) {
    if (!regions[region] && text) {
      const slot = stored[region] && typeof stored[region] === "object" ? stored[region] : {};
      regions[region] = { ...slot, garments: [], beneath: text };
    }
  }
  return { ...(entry || {}), regions, state: notes.filter(n => n && n.trim()) };
}

function wbAttireEditor(body, ctx) {
  const vocab = ctx.vocab;
  const regionOrder = vocab.attire_regions || [];
  const entry = body.attire && typeof body.attire === "object" ? body.attire : null;
  const { order, garments } = wbGroupGarments(entry, regionOrder);
  const beneath = {};
  for (const region of order) {
    const slot = entry && entry.regions ? entry.regions[region] : null;
    if (slot && typeof slot === "object" && slot.beneath) beneath[region] = String(slot.beneath);
  }
  const notes = entry && Array.isArray(entry.state) ? entry.state.map(String) : [];

  // Every write is the WHOLE ledger -- every body's entry as the index last
  // read it, this body's rebuilt -- through the one route that re-derives.
  const save = () => wbWrite(ctx, async () => {
    const ledger = {};
    for (const b of ctx.index.bodies || []) {
      if (b.attire && typeof b.attire === "object") ledger[b.name] = b.attire;
    }
    ledger[body.name] = wbLedgerEntry(entry, garments, beneath, notes);
    await api("PUT", `/api/chats/${ctx.chatId}/attire${frameQuery()}`, ledger);
    await ctx.refresh();
    return true;
  });

  const garmentRow = (g, region) => el("div", { class: "wb-garment" },
    wbText(g.name, v => { if (v.trim()) { g.name = v.trim(); save(); } },
      { placeholder: "Garment", title: "Garment name" }),
    wbSelect(vocab.garment_states, g.state || (vocab.garment_states || [])[0],
      { title: "How far off the body it is", onchange: v => { g.state = v; save(); } }),
    wbText(g.condition || "", v => { g.condition = v; save(); },
      { placeholder: "Condition — stained, torn, wet" }),
    g.regions.length > 1
      ? el("span", { class: "small dim", title: "One garment, worn across these regions" },
          "Also:", " ", el("span", { translate: "no" },
            txt(g.regions.filter(r => r !== region).join(", "))))
      : null,
    el("button", { class: "small wb-remove", title: "Take this garment off the ledger entirely",
                   onclick: () => { garments.splice(garments.indexOf(g), 1); save(); } }, "✕"));

  const regionRows = order.map(region => {
    const here = garments.filter(g => g.regions.includes(region));
    return el("div", { class: "wb-region", "data-region": region },
      el("div", { class: "wb-region-head" },
        el("span", { class: "wb-region-name", translate: "no" }, txt(region)),
        here.length ? null : el("span", { class: "small dim" }, "bare")),
      ...here.map(g => garmentRow(g, region)),
      el("div", { class: "wb-exit" },
        el("span", { class: "small dim" }, "Underneath:"),
        wbText(beneath[region] || "", v => { beneath[region] = v; save(); },
          { placeholder: "What shows when this region is uncovered" })));
  });

  // Add a garment: a name, the regions it covers, its state.
  const name = el("input", { type: "text", class: "wb-input", translate: "no",
                             placeholder: "Garment" });
  const checks = regionOrder.map(region => {
    const box = el("input", { type: "checkbox", value: region });
    return el("label", { class: "wb-check" }, box, el("span", { translate: "no" }, txt(region)));
  });
  const state = wbSelect(vocab.garment_states, (vocab.garment_states || [])[0],
    { title: "How far off the body it is", onchange: () => {} });
  const add = () => {
    const text = name.value.trim();
    const regions = checks.map(l => l.querySelector("input")).filter(b => b.checked).map(b => b.value);
    if (!text) return toast("A garment needs a name", "err");
    if (!regions.length) return toast("Pick at least one region the garment covers", "err");
    garments.push({ name: text, state: state.value, condition: "", regions });
    save();
  };
  name.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); add(); } });

  // The free notes: authored prose about the body's state. The derived
  // bareness notes are the server's to rebuild, so sending them back is
  // harmless and removing one is undone by re-derivation.
  const noteRows = notes.map((note, i) => el("div", { class: "wb-exit" },
    el("span", { translate: "no" }, txt(note)),
    el("button", { class: "small wb-remove", title: "Remove this note",
                   onclick: () => { notes.splice(i, 1); save(); } }, "✕")));
  const noteInput = el("input", { type: "text", class: "wb-input", translate: "no",
                                  placeholder: "A note about this body's appearance" });
  const addNote = () => {
    const text = noteInput.value.trim();
    if (!text) return;
    notes.push(text);
    save();
  };
  noteInput.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); addNote(); } });

  const wearing = entry && Array.isArray(entry.wearing) ? entry.wearing : [];
  return el("div", { class: "wb-attire" },
    el("div", {},
      el("span", { class: "dim" }, "Wearing:"), " ",
      el("span", { translate: "no" }, txt(wearing.length ? wearing.join(", ") : "—")),
      " ", el("span", { class: "small dim" }, "(derived from the regions below)")),
    ...regionRows,
    el("div", { class: "wb-exit wb-add" }, name, ...checks, state,
      el("button", { class: "small", onclick: add }, "Add garment")),
    wbSection("Notes",
      noteRows.length ? el("div", {}, ...noteRows) : null,
      el("div", { class: "wb-exit wb-add" }, noteInput,
        el("button", { class: "small", onclick: addNote }, "Add note"))));
}

function wbBodyKind(kind) {
  if (kind === "player") return el("span", { class: "badge ok" }, "Player");
  if (kind === "cast") return el("span", { class: "badge" }, "Cast");
  return el("span", { class: "badge warn" }, "Presence");
}

function wbRenderBodies(host, ctx) {
  host.innerHTML = "";
  const bodies = ctx.index.bodies || [];
  if (!bodies.length) {
    host.append(el("div", { class: "small dim" }, "No bodies yet — nobody stands in the scene."));
    return;
  }
  for (const body of bodies) {
    const open = ctx.openBodies.has(body.name);
    const details = el("details", { class: "wb-body", "data-body": body.name,
                                    ...(open ? { open: "" } : {}) },
      el("summary", {},
        el("b", { translate: "no" }, txt(body.name)),
        wbBodyKind(body.kind),
        body.room
          ? el("button", { class: "wb-link", translate: "no",
                           onclick: e => { e.preventDefault(); ctx.showRoom(body.room); } },
              txt(body.room_name || body.room))
          : el("span", { class: "small dim" }, "Offscreen"),
        wbStationText(body.station),
        body.pose && wbPoseText(body.pose)
          ? el("span", { class: "small dim", translate: "no" }, txt(" · " + wbPoseText(body.pose)))
          : null,
        body.attire && Array.isArray(body.attire.wearing)
          ? el("span", { class: "small dim" }, " · ", `Garments: ${body.attire.wearing.length}`)
          : null),
      wbAttireEditor(body, ctx));
    details.addEventListener("toggle", () => {
      if (details.open) ctx.openBodies.add(body.name); else ctx.openBodies.delete(body.name);
    });
    host.append(details);
  }
}

// ---- The Raw JSON tab: the two editors, unchanged --------------------------

function wbRenderRaw(host, chatId, kind, cache) {
  host.innerHTML = "";
  const isAttire = kind === "attire";
  const path = isAttire
    ? `/api/chats/${chatId}/attire${frameQuery()}`
    : `/api/chats/${chatId}/world`;
  const render = data => {
    host.innerHTML = "";
    const ta = el("textarea",
      { style: isAttire ? "width:100%;height:340px" : "width:100%;height:420px" },
      JSON.stringify(data, null, 2));
    host.append(
      el("div", { class: "small dim", style: "margin-bottom:8px" }, isAttire
        ? "What each character is currently wearing and any visible physical state (injuries, disguises, damage) "
          + "the story should keep consistent going forward. Updates automatically as the story progresses; edit "
          + "directly only to correct something or set up a scene's starting appearance by hand."
        : "The raw internal record of the scene — rooms, positions, objects, standing facts — that every stage of "
          + "a turn reads from and writes to. The story keeps this updated on its own; you don't need to touch it "
          + "to play. Edit it only to hand-correct something that's drifted wrong (a character in the wrong room, "
          + "a fact that should no longer be true)."),
      ta,
      el("div", { class: "row", style: "margin-top:8px" },
        el("button", { class: "primary", onclick: async () => {
          let j;
          try { j = JSON.parse(ta.value); } catch (e) { return toast("Invalid JSON", "err"); }
          await api("PUT", path, j);
          closeModal();
          toast(isAttire ? "Attire saved." : "World state saved.", "ok");
        } }, "Save")));
  };
  if (cache.raw) return render(cache.raw);
  host.append(el("div", { class: "small dim" }, "Loading…"));
  api("GET", path).then(data => {
    if (S.chatId !== chatId || !host.isConnected) return;
    cache.raw = data;
    render(data);
  });
}

// ---- The dialog -------------------------------------------------------------

async function openWorldBrowser(opts = {}) {
  if (!S.chatId) return;
  const chatId = S.chatId;
  const rawKind = opts.raw === "attire" ? "attire" : "world";
  const [index, positions] = await Promise.all([
    api("GET", `/api/chats/${chatId}/rooms${frameQuery()}`),
    // Relocation is an addition to the browser, not its purpose: a failed
    // positions lookup hides "Move here" and leaves the rest working.
    api("GET", `/api/chats/${chatId}/positions${frameQuery()}`).catch(() => null),
  ]);
  if (S.chatId !== chatId) return;

  const firstRoom = idx => {
    for (const [key] of WB_GROUPS) {
      const rows = (idx.groups || {})[key] || [];
      if (rows.length && key !== "retired") return rows[0].id;
    }
    return null;
  };
  const tabs = [["rooms", "Rooms"], ["bodies", "Bodies"], ["raw", "Raw JSON"]];
  const state = {
    index,
    positions,
    selected: opts.room || positions?.persona?.room || firstRoom(index),
    tab: tabs.some(([id]) => id === opts.tab) ? opts.tab : "rooms",
    cache: {},
  };

  modal(rawKind === "attire" ? "Attire" : "World state", b => {
    const alive = modalOwnership(b);
    const tabBar = el("div", { class: "lore-inspector-tabs" });
    const content = el("div", { class: "lore-inspector-content" });

    const tree = el("div", { class: "wb-tree" });
    const card = el("div", { class: "wb-card" });
    const location = el("div", { class: "small dim", style: "margin-bottom:6px", translate: "no" });
    const browse = el("div", {}, location, el("div", { class: "wb" }, tree, card));
    const bodies = el("div", { class: "wb-bodies" });

    const ctx = {
      chatId,
      index: state.index,
      vocab: state.index.vocab || {},
      positions: state.positions,
      // The Bodies tab opens every body when the attire button opened the
      // dialog, and remembers what the host folded since.
      openBodies: new Set(opts.expandAttire ? (index.bodies || []).map(b => b.name) : []),
      select: id => loadRoom(id),
      showRoom: id => { state.selected = id; selectTab("rooms"); },
      showBody: name => { ctx.openBodies.add(name); selectTab("bodies"); },
      // The card rebuilt from a write's fresh slice; the tree re-read, since
      // a rename or an exit changes it too.
      replaceCard: async fresh => {
        if (!alive() || S.chatId !== chatId) return;
        if (fresh && fresh.id === state.selected) wbRenderCard(card, fresh, ctx);
        await refreshIndex();
      },
      refresh: async () => {
        await refreshIndex();
        if (!alive() || S.chatId !== chatId) return;
        if (state.tab === "rooms") await loadRoom(state.selected);
        else if (state.tab === "bodies") wbRenderBodies(bodies, ctx);
      },
    };

    async function refreshIndex() {
      const [idx, pos] = await Promise.all([
        api("GET", `/api/chats/${chatId}/rooms${frameQuery()}`),
        api("GET", `/api/chats/${chatId}/positions${frameQuery()}`).catch(() => null),
      ]);
      if (!alive() || S.chatId !== chatId) return;
      state.index = idx;
      state.positions = pos;
      ctx.index = idx;
      ctx.vocab = idx.vocab || ctx.vocab;
      ctx.positions = pos;
      location.textContent = idx.location || "";
      location.hidden = !idx.location;
      wbRenderTree(tree, state.index, state.selected, loadRoom);
    }

    async function loadRoom(id) {
      state.selected = id;
      for (const button of tree.querySelectorAll(".wb-room")) {
        button.classList.toggle("on", button.dataset.room === id);
      }
      if (!id) return wbRenderCard(card, null, ctx);
      card.innerHTML = "";
      card.append(el("div", { class: "small dim" }, "Loading…"));
      let slice = null;
      try {
        slice = await api("GET",
          `/api/chats/${chatId}/rooms/${encodeURIComponent(id)}${frameQuery()}`);
      } catch (error) {
        if (!alive() || S.chatId !== chatId) return;
        card.innerHTML = "";
        card.append(el("div", { class: "err small" }, txt(error?.message || String(error))));
        return;
      }
      if (!alive() || S.chatId !== chatId || state.selected !== id) return;
      wbRenderCard(card, slice, ctx);
    }

    function selectTab(tabId) {
      state.tab = tabId;
      for (const button of tabBar.querySelectorAll("button")) {
        button.classList.toggle("on", button.dataset.tab === tabId);
      }
      content.innerHTML = "";
      if (tabId === "raw") {
        wbRenderRaw(content, chatId, rawKind, state.cache);
      } else if (tabId === "bodies") {
        wbRenderBodies(bodies, ctx);
        content.append(bodies);
      } else {
        content.append(browse);
        loadRoom(state.selected);
      }
    }

    for (const [id, label] of tabs) {
      tabBar.append(el("button", {
        "data-tab": id,
        class: id === state.tab ? "on" : "",
        onclick: () => selectTab(id),
      }, label));
    }

    b.append(tabBar, content);
    location.textContent = index.location || "";
    location.hidden = !index.location;
    wbRenderTree(tree, state.index, state.selected, loadRoom);
    selectTab(state.tab);
  }, { wide: true, autoFocus: false });
}

// Both handlers carry the chat guard in the shape chat.js's
// `updateChatScopedButtons` is derived from, so the buttons are disabled
// with no story open rather than being a dead click.
$("#b-world").onclick = async () => {
  if (!S.chatId) return;
  await openWorldBrowser({ raw: "world", tab: "rooms" });
};
// The attire button opens the same dialog on the Bodies tab with every
// body's ledger unfolded; its Raw JSON tab is the attire ledger.
$("#b-attire").onclick = async () => {
  if (!S.chatId) return;
  await openWorldBrowser({ raw: "attire", tab: "bodies", expandAttire: true });
};

window.openWorldBrowser = openWorldBrowser;
