"use strict";

// ---- The World Browser ----
//
// The room-centred view of the world state behind the 🌍 and 👕 buttons,
// and since 2026-09-04 its EDITOR: three tabs in one dialog.
//
//   Rooms   -- since the owner's ruling later on 2026-09-04, a MAP EDITOR on
//              the left (the selected room's grid, zoomable out to every room
//              placed by bearing -- see "The map editor" below; clicking a
//              thing on it opens that thing's editor row on the card, dragging
//              places it) with the tree of every room the story knows folded
//              open beneath it, and the selected room's card on the right.
//              Every field the card shows is edited where
//              it is shown: name, description, notes, light / size / exposure
//              (selects over the engine's own sets), the room's MEASUREMENT
//              (extent in paces, shape, and an L's parts -- size is shown as
//              derived while an extent stands), region (a datalist of the
//              map's regions) with the region's shared `look`, exits (barrier
//              and bearing per doorway, remove, add -- the far room's edge is
//              written too, because a doorway is one object), anchors under
//              the WALL their bearing names (each wall heading saying how
//              many paces it has; description, bearing, and the three
//              geometry words), the things standing here (kind, description,
//              portable, light, lit, move), and each body's station (the
//              anchor it stands at, who it stands beside, the cell the map
//              pinned it to, with a clear). The layout lint's
//              rows for the room are shown beside the field each concerns,
//              and the tree marks a room that carries one.
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
// the menus are built from: `PATCH /rooms/{id}` (changed fields only; exits,
// anchors and parts as this room's full list), `PATCH /rooms/{id}/entities/{eid}`,
// `PUT /bodies/{name}/station`, `PATCH /regions/{id}` (the region's look,
// one sentence every room in the region shares), and the two writes the app
// already had --
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
      // The layout lint names this room: the card shows each row beside the
      // field it concerns.
      row.lint ? el("span", { class: "badge warn wb-lint-mark",
                              title: "The layout lint has something to say about this room" },
                    "Layout")
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

// A station `cell` as the map writes it -- `[x, y]` in the room's own grid --
// or null: the one shape the engine keeps (`normalize_cell`).
function wbCellOf(station) {
  const c = station && station.cell;
  return Array.isArray(c) && c.length === 2 && Number.isInteger(c[0]) && Number.isInteger(c[1]) ? c : null;
}

function wbCellText(cell) {
  return el("span", { translate: "no", class: "wb-cell" }, `(${cell[0]}, ${cell[1]})`);
}

function wbStationText(station) {
  // `scene.stations[name]` is `{at: anchor|null, near: [names], cell?: [x, y]}`:
  // what the body stands at, who it stands beside, and -- since the map
  // editor let a body be dropped on any cell (the owner, 2026-09-04) -- the
  // cell it is pinned to, in the room's own grid.
  if (!station || typeof station !== "object") return null;
  const near = Array.isArray(station.near) ? station.near.filter(Boolean) : [];
  const cell = wbCellOf(station);
  if (!station.at && !near.length && !cell) return null;
  return el("span", { class: "small dim" }, " · ",
    station.at ? el("span", { translate: "no" }, txt(station.at)) : null,
    near.length ? [station.at ? ", " : "", "Near", " ",
                   el("span", { translate: "no" }, txt(near.join(", ")))] : null,
    cell ? [station.at || near.length ? ", " : "", "Cell", " ", wbCellText(cell)] : null);
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

// A whole-number control in paces, clamped by the engine's own range
// (`vocab.extent`), committing on blur or Enter like `wbText` and reverting on
// Escape. `save` gets the number, or null when the box was emptied.
function wbNumber(value, save, { min, max, title = null, placeholder = "" } = {}) {
  const input = el("input", { type: "number", class: "wb-input wb-paces", min: String(min),
                              max: String(max), step: "1", translate: "no",
                              ...(title ? { title } : {}),
                              ...(placeholder ? { placeholder } : {}) });
  input.value = value == null || value === "" ? "" : String(value);
  let settled = input.value;
  const commit = async () => {
    if (input.value === settled) return;
    settled = input.value;
    await save(input.value === "" ? null : Number(input.value));
  };
  input.addEventListener("blur", commit);
  input.addEventListener("keydown", e => {
    if (e.key === "Enter") { e.preventDefault(); input.blur(); }
    if (e.key === "Escape") { input.value = settled; input.blur(); }
  });
  return input;
}

// The layout lint's rows naming this room that concern one card field
// (`field`, the server's `LINT_FIELDS` word), and -- for the anchor editor --
// one wall of it. Each row is the sentence the commit's warning list would
// carry (`layout_warning`), rendered where the field it is about is edited,
// so a host reads "the north wall cannot hold them" under the north wall.
function wbLintRows(slice, field, { wall = undefined } = {}) {
  return (slice.lint || [])
    .filter(row => row.field === field && (wall === undefined || (row.wall || "") === wall))
    .map(row => el("div", { class: "wb-lint", "data-kind": row.kind },
      el("span", { class: "badge warn", title: "The layout lint: where this room's geometry cannot all be true" },
        "Layout"),
      el("span", { class: "small", translate: "no" }, txt(row.text))));
}

// The room's fields: a PATCH of just the one that changed, the card rebuilt
// from the slice the server hands back. Since the room grew a measurement
// (`docs/design/DESIGN_ROOM_FIDELITY.md` §2): the extent in paces, the shape,
// and for an L its parts, with size shown as DERIVED while an extent stands
// -- `size` is the word for the floor and `extent` its measurement, so the
// word is not edited apart from the number.
function wbRoomFields(slice, ctx) {
  const record = slice.record;
  const vocab = ctx.vocab;
  const geometry = record.geometry || {};
  const range = vocab.extent || {};
  const patch = fields => wbWrite(ctx, async () => {
    const fresh = await api("PATCH",
      `/api/chats/${ctx.chatId}/rooms/${encodeURIComponent(slice.id)}${frameQuery()}`,
      fields);
    await ctx.replaceCard(fresh);
    return fresh;
  });
  const field = (label, control, cls = "") => el("label", { class: "wb-field " + cls },
    el("span", { class: "small dim" }, label), control);

  // Size: the tier as authored, or -- while an extent stands -- the tier the
  // extent gives (`size_from_extent`), shown and not offered.
  const measured = !!record.extent;
  const size = wbSelect(vocab.size, measured ? geometry.size_derived : record.size,
    { blank: "—", onchange: v => patch({ size: v }) });
  if (measured) {
    size.disabled = true;
    size.title = t("Derived from the extent: the measurement decides how much floor there is, so the word follows it. Clear the extent to choose a size.");
  }

  // Extent: both sides in paces. A pair commits when both boxes hold a
  // number (one side alone is not a measurement -- the engine refuses to
  // guess the other); the clear button withdraws the measurement.
  const extent = record.extent || {};
  let w = extent.w ?? null, d = extent.d ?? null;
  const commitExtent = () => {
    if (w == null || d == null) return;
    if (record.extent && record.extent.w === w && record.extent.d === d) return;
    return patch({ extent: { w, d } });
  };
  const wInput = wbNumber(w, v => { w = v; return commitExtent(); },
    { min: range.min, max: range.max, title: "Paces east to west", placeholder: "w" });
  const dInput = wbNumber(d, v => { d = v; return commitExtent(); },
    { min: range.min, max: range.max, title: "Paces north to south", placeholder: "d" });
  const extentControl = el("span", { class: "wb-extent" }, wInput,
    el("span", { class: "small dim" }, "×"), dInput,
    measured ? el("button", { class: "small wb-remove", title: "Clear the extent; the room is its size tier's square again",
                              onclick: () => patch({ extent: null }) }, "✕") : null,
    !measured ? el("span", { class: "small dim", title: "With no extent the room is the square its size tier gives it" },
                    `${geometry.w ?? "?"} × ${geometry.d ?? "?"} from the tier`) : null);

  // Shape, and the parts of an L. The parts editor shows for an `l`, and for
  // any shape that still carries parts, so a `corner_in_round_room` row can
  // be fixed here rather than in Raw JSON.
  const shape = wbSelect(vocab.shapes, record.shape || "",
    { blank: "—", title: "Rectangle when unset", onchange: v => patch({ shape: v }) });
  const parts = (record.parts || []).map(p => ({ ...p }));
  const patchParts = () => patch({ parts: parts.map(p => ({ w: p.w, d: p.d, at: p.at })) });
  let partsEditor = null;
  if (record.shape === "l" || parts.length) {
    const rows = parts.map((part, i) => el("div", { class: "wb-exit wb-part" },
      el("span", { class: "small dim" }, "Corner"),
      wbSelect(vocab.corners, part.at, { title: "Which corner of the box this part fills",
                                         onchange: v => { part.at = v; return patchParts(); } }),
      wbNumber(part.w, v => { if (v == null) return; part.w = v; return patchParts(); },
        { min: range.min, max: range.max, title: "Paces east to west" }),
      el("span", { class: "small dim" }, "×"),
      wbNumber(part.d, v => { if (v == null) return; part.d = v; return patchParts(); },
        { min: range.min, max: range.max, title: "Paces north to south" }),
      el("button", { class: "small wb-remove", title: "Remove this part",
                     onclick: () => { parts.splice(i, 1); return patchParts(); } }, "✕")));
    const used = new Set(parts.map(p => p.at));
    const corner = wbSelect(vocab.corners,
      (vocab.corners || []).find(c => !used.has(c)) || (vocab.corners || [])[0],
      { title: "Which corner of the box the new part fills", onchange: () => {} });
    const newW = wbNumber("", () => {}, { min: range.min, max: range.max, placeholder: "w",
                                          title: "Paces east to west" });
    const newD = wbNumber("", () => {}, { min: range.min, max: range.max, placeholder: "d",
                                          title: "Paces north to south" });
    const add = () => {
      if (newW.value === "" || newD.value === "") return toast(t("A part needs both sides in paces"), "err");
      parts.push({ w: Number(newW.value), d: Number(newD.value), at: corner.value });
      return patchParts();
    };
    partsEditor = el("div", { class: "wb-parts" },
      rows.length ? el("div", {}, ...rows)
                  : el("div", { class: "small dim" }, "An L is the union of two rectangles, each placed at a corner of the box."),
      el("div", { class: "wb-exit wb-add" }, el("span", { class: "small dim" }, "Corner"), corner,
        newW, el("span", { class: "small dim" }, "×"), newD,
        el("button", { class: "small", onclick: add }, "Add part")));
  }

  // The region, and the look every room in it shares.
  const regionsList = el("datalist", { id: "wb-regions-list" },
    ...(vocab.regions || []).map(r => el("option", { value: r.id, translate: "no" },
      txt(r.name && r.name !== r.id ? r.name : ""))));
  const regionInput = wbText(record.region, value => patch({ region: value }),
    { placeholder: "Which part of the map" });
  regionInput.setAttribute("list", "wb-regions-list");

  return el("div", {},
    el("div", { class: "wb-fields" },
      field("Light", wbSelect(vocab.light, record.light,
        { blank: "—", onchange: v => patch({ light: v }) })),
      field("Size", el("span", { class: "wb-size" }, size,
        measured ? el("span", { class: "small dim wb-derived" }, "derived from the extent") : null), "wb-field-size"),
      field("Extent (paces)", extentControl, "wb-field-extent"),
      field("Shape", shape, "wb-field-shape"),
      field("Exposure", wbSelect(vocab.exposure, record.exposure,
        { blank: "—", onchange: v => patch({ exposure: v }) })),
      field("Region", el("span", {}, regionInput, regionsList))),
    ...wbLintRows(slice, "extent"),
    partsEditor,
    ...wbLintRows(slice, "shape"),
    wbRegionLook(slice, ctx));
}

// The region's `look`: the visual register a picture of any room in the
// region shares (`world/regions.py`, the registry record). It is the
// REGION's field, so the write is the regions route and the card says how
// far the sentence reaches; a room in no region has no look to edit.
function wbRegionLook(slice, ctx) {
  const region = slice.record ? slice.record.region : slice.region;
  if (!region) return null;
  const siblings = wbIndexRows(ctx.index).filter(r => r.region === region && r.status !== "retired");
  const name = slice.region_name && slice.region_name !== region ? slice.region_name : region;
  const save = look => wbWrite(ctx, async () => {
    await api("PATCH",
      `/api/chats/${ctx.chatId}/regions/${encodeURIComponent(region)}${frameQuery()}`,
      { look });
    await ctx.refresh();
    return true;
  });
  return el("div", { class: "wb-look" },
    el("label", { class: "wb-field" },
      el("span", { class: "small dim" }, "Look of the region"),
      wbText(slice.region_look || "", save,
        { placeholder: "What every picture of this part of the map shares — brick and iron under sodium lamps" })),
    el("div", { class: "small dim" },
      "Shared by every room in", " ", el("b", { translate: "no" }, txt(name)),
      siblings.length ? [" ", el("span", { translate: "no" },
        txt(`(${siblings.length})`))] : null));
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
      rows.push(el("div", { class: "wb-exit", "data-exit": edge.to },
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
  kids.push(...wbLintRows(slice, "exits"));
  return wbSection("Exits", ...kids);
}

// Anchors: the room's named features, each with a wall and its geometry --
// listed UNDER their wall. The four straight walls always head a group,
// each saying how many paces it has (`record.geometry.walls`, the engine's
// own rim count, from the extent or the size tier), so a wall that cannot
// hold what stands on it is visible before the lint says so; the doorways
// the wall carries are shown there too, read-only, because they take wall
// as well. A corner heads a group only when an anchor sits in it; anchors
// with no bearing are listed last. Moving an anchor to another wall is
// changing its bearing.
function wbAnchors(slice, ctx) {
  if (!slice.record) return null;
  const vocab = ctx.vocab;
  const anchors = slice.record.anchors || {};
  const walls = (slice.record.geometry || {}).walls || {};
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
  const row = (aid, a) => el("div", { class: "wb-exit wb-anchor", "data-anchor": aid },
    el("span", { class: "small dim", translate: "no", title: "Anchor id" }, txt(aid)),
    wbText(a.desc || "", v => update(aid, { desc: v }), { placeholder: "Description" }),
    wbSelect(vocab.dirs, a.dir || "", { blank: "—", title: "Bearing — the wall this anchor stands on; change it to move the anchor",
                                        onchange: v => update(aid, { dir: v }) }),
    // The origin cell the map pinned it to (its west-most, north-most cell;
    // the footprint runs east and south from it). Beside the wall, because
    // with a cell the wall is prose -- "against the north wall" -- and moves
    // nothing; clearing the cell hands the anchor back to its wall or seed.
    wbCellOf(a) ? el("span", { class: "small dim wb-anchor-cell" }, "Cell", " ", wbCellText(wbCellOf(a)),
      el("button", { class: "small wb-remove wb-clear-cell",
                     title: "Clear the cell — the anchor is placed by its wall again, or by seed",
                     onclick: () => update(aid, { cell: null }) }, "✕")) : null,
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
    } }, "✕"));

  // Group by bearing: the straight walls in the engine's order, then the
  // corners that hold something, then no bearing at all.
  const byDir = new Map();
  for (const [aid, a] of Object.entries(anchors)) {
    const key = a.dir || "";
    if (!byDir.has(key)) byDir.set(key, []);
    byDir.get(key).push([aid, a]);
  }
  const doors = (slice.stationable || []).filter(a => a.implicit);
  const groups = [];
  for (const wall of vocab.walls || []) {
    const paces = walls[wall];
    const here = byDir.get(wall) || [];
    const hereDoors = doors.filter(a => a.dir === wall);
    groups.push(el("div", { class: "wb-wall", "data-wall": wall },
      el("div", { class: "wb-wall-head" },
        el("span", { class: "wb-wall-name", translate: "no" }, txt(wall.toUpperCase())),
        el("span", {}, "wall"),
        paces != null ? el("span", { class: "dim wb-wall-paces", title: "How many paces this wall has, from the extent or the size tier" },
          `${paces} paces`) : null),
      ...hereDoors.map(a => el("div", { class: "wb-exit wb-doorway small dim" },
        el("span", {}, "Doorway"), el("span", { translate: "no" }, txt(a.desc)),
        el("span", { translate: "no" }, txt(`(${a.id})`)))),
      ...here.map(([aid, a]) => row(aid, a)),
      ...wbLintRows(slice, "anchors", { wall })));
  }
  for (const corner of vocab.corners || []) {
    const here = byDir.get(corner) || [];
    if (!here.length) continue;
    groups.push(el("div", { class: "wb-wall", "data-wall": corner },
      el("div", { class: "wb-wall-head" },
        el("span", { class: "wb-wall-name", translate: "no" }, txt(corner.toUpperCase())),
        el("span", {}, "corner")),
      ...here.map(([aid, a]) => row(aid, a))));
  }
  const free = byDir.get("") || [];
  if (free.length) {
    groups.push(el("div", { class: "wb-wall", "data-wall": "" },
      el("div", { class: "wb-wall-head" }, el("span", {}, "No wall"),
        el("span", { class: "dim" }, "— placed somewhere in the room")),
      ...free.map(([aid, a]) => row(aid, a))));
  }
  // An anchor row naming no wall (none of today's kinds, kept so a new kind
  // is shown rather than lost).
  const stray = wbLintRows(slice, "anchors", { wall: "" });

  const desc = el("input", { type: "text", class: "wb-input", translate: "no",
                             placeholder: "A feature prose refers to — the hearth, the bar" });
  const dir = wbSelect(vocab.dirs, "", { blank: "—", title: "Bearing — which wall the new anchor stands on",
                                         onchange: () => {} });
  const add = () => {
    const text = desc.value.trim();
    if (!text) return;
    const next = copy();
    next[""] = dir.value ? { desc: text, dir: dir.value } : { desc: text };
    return patchAnchors(next);
  };
  desc.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); add(); } });
  return wbSection("Anchors",
    Object.keys(anchors).length || doors.length ? null
      : el("div", { class: "small dim" }, "No anchors recorded."),
    ...groups,
    ...stray,
    el("div", { class: "wb-exit wb-add" }, desc, dir,
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
  const cell = wbCellOf(station);
  const garments = o.attire && Array.isArray(o.attire.wearing) ? o.attire.wearing.length : null;
  return el("div", { class: "wb-body", "data-body": o.name },
    el("div", { class: "row wb-body-head" },
      el("b", { translate: "no" }, txt(o.name)),
      garments != null ? el("span", { class: "small dim" }, `Garments: ${garments}`) : null,
      el("button", { class: "wb-link", onclick: () => ctx.showBody(o.name) }, "Attire")),
    slice.status === "live" ? el("div", { class: "wb-exit" },
      el("span", { class: "small dim" }, "At"),
      // Choosing an anchor by name is "stand at it": the anchor places the
      // body, so a pinned cell is let go. Dropping the body on the map
      // writes both -- `at` for prose, `cell` for geometry.
      wbSelect(stationable.map(a => a.id), station.at || "",
        { blank: "—", title: "The anchor this body stands at",
          labels: id => {
            const a = stationable.find(x => x.id === id);
            return a && a.desc && a.desc !== id ? `${a.desc} (${id})` : id;
          },
          onchange: v => put({ at: v || null, near: [...near], cell: null }) }),
      cell ? el("span", { class: "small dim wb-station-cell" }, "Cell", " ", wbCellText(cell),
        el("button", { class: "small wb-remove wb-clear-cell",
                       title: "Clear the cell — the body stands at its anchor, or somewhere in the room",
                       onclick: () => put({ at: station.at || null, near: [...near], cell: null }) },
          "✕")) : null,
      others.length ? el("span", { class: "small dim" }, "Near") : null,
      ...others.map(name => el("label", { class: "wb-check" },
        el("input", { type: "checkbox", ...(near.has(name) ? { checked: true } : {}),
                      onchange: e => {
                        const next = new Set(near);
                        if (e.target.checked) next.add(name); else next.delete(name);
                        return put({ at: station.at || null, near: [...next], cell });
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
  return el("div", { class: "wb-thing", "data-thing": th.id },
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
        // The pin is let go here too: the Bodies tab is where a host reads
        // a body's whole record, and the map's cell is part of it.
        wbCellOf(body.station) && body.room
          ? el("button", { class: "small wb-remove wb-clear-cell",
                           title: "Clear the cell — the body stands at its anchor, or somewhere in the room",
                           onclick: async e => {
                             e.preventDefault();
                             await wbWrite(ctx, async () => {
                               await api("PUT",
                                 `/api/chats/${ctx.chatId}/bodies/${encodeURIComponent(body.name)}/station${frameQuery()}`,
                                 { at: body.station.at || null,
                                   near: Array.isArray(body.station.near) ? body.station.near : [],
                                   cell: null });
                               await ctx.refresh();
                               return true;
                             });
                           } }, "✕")
          : null,
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

// ---- The map editor ---------------------------------------------------------------
//
// The Rooms tab's left pane, since the owner's ruling of 2026-09-04: THE GRID
// IS THE SURFACE, AND CLICKING OPENS THE FIELDS. Two zoom levels over two
// read-only routes that are pure over the engine's own geometry
// (`web/world_routes.py`: `GET /rooms/{id}/grid` and `GET /map`), so the map
// cannot draw a wall the cast is not judged by:
//
//   the room   -- its cells to scale with the shape's boundary; anchors as
//                 their footprint cells labelled by id with a height mark;
//                 bodies as marked cells with a facing tick (a body with no
//                 station stands in the lane below the room -- "somewhere in
//                 the room" is not a cell); doorways as gaps in the wall line
//                 with the neighbour's name beyond; the neighbours' cells
//                 faintly beyond their doors, exactly where `room_field` lays
//                 them; the layout lint's rows drawn AT the thing they concern.
//   the scene  -- every room as its box placed by bearing (`layout_rooms`,
//                 the lint's own embedding), exits as ticks on the wall they
//                 open in, a room the bearings land on another drawn on it
//                 and flagged, never hidden. Click a room to zoom in.
//
// Click opens the fields: an anchor focuses its editor row on the card, a
// doorway its exit row, a body its station row, a thing its entity row, a
// lint marker the row's sentence beside its field. The card is the panel;
// nothing here duplicates an editor.
//
// Drag places: an anchor dragged to a wall gets that wall's bearing and an
// `offset` along it (a fraction from the wall's start -- west for a north or
// south wall, north for an east or west one; the engine's
// `normalize_offset`); dragged onto any other cell it is PINNED there
// (`cell`, its origin cell in the room's own grid; the wall and the offset
// cleared -- the owner, 2026-09-04). A doorway dragged along its wall sets
// the exit's `offset`, on both rooms' edges, since a doorway is one object.
// A body dropped on ANY cell is pinned to it (`cell`), and stationed `at`
// the anchor whose cell it is when it is one, for prose; dropped in a
// neighbour's cells it MOVES there (the cast editor's position route, then
// its station with the cell in the neighbour's grid). An authored fact, like
// every edit here: no Director call, no memory of a step.
//
// Overlays: the grid route's `overlays` slot (`{name: {"x,y": word}}`) is
// painted as a tint per cell with a legend whenever a sibling fills it --
// light, sound; this file computes none of them and knows no word in advance.
//
// SVG, no library; every colour a page token, so the theme carries it. The
// tree the tab used to be is kept under the map, folded open, so a planned or
// a retired room -- which has no grid -- is still a click away.

const WB_CELL = 24;        // one pace, in SVG units, on the room map
const WB_MINI = 10;        // one pace on the structure map
const WB_SVG_NS = "http://www.w3.org/2000/svg";
// Compass geometry, not a vocabulary: the unit step each bearing names.
const WB_UNIT = { n: [0, -1], ne: [1, -1], e: [1, 0], se: [1, 1],
                  s: [0, 1], sw: [-1, 1], w: [-1, 0], nw: [-1, -1] };

// An SVG-namespace sibling of `el()`. Text children are NOT translated (they
// are ids and names); a label that is English goes through `t()` by hand.
function wbSvg(tag, attrs = {}, ...kids) {
  const node = document.createElementNS(WB_SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, String(v));
  }
  for (const kid of kids.flat()) {
    if (kid == null || kid === false) continue;
    node.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return node;
}

function wbSvgPoint(svg, event) {
  const ctm = svg.getScreenCTM();
  const point = new DOMPoint(event.clientX, event.clientY);
  return ctm ? point.matrixTransform(ctm.inverse()) : point;
}

// Pointer drag on an SVG node. A press that never moved a third of a cell is
// a click (`onClick`); one that did ends in `onDrop(point)`. Enter or Space
// on the focused node is the click, so the keyboard reaches every editor.
function wbDraggable(svg, node, { onDrop, onClick }) {
  node.addEventListener("pointerdown", event => {
    if (event.button !== 0) return;
    event.preventDefault();
    event.stopPropagation();
    const start = wbSvgPoint(svg, event);
    let moved = false;
    const move = ev => {
      const p = wbSvgPoint(svg, ev);
      if (!moved && Math.hypot(p.x - start.x, p.y - start.y) < WB_CELL / 3) return;
      moved = true;
      node.classList.add("dragging");
    };
    const up = ev => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      window.removeEventListener("pointercancel", up);
      node.classList.remove("dragging");
      if (ev.type === "pointercancel") return;
      if (moved) onDrop(wbSvgPoint(svg, ev)); else onClick();
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    window.addEventListener("pointercancel", up);
  });
  node.addEventListener("keydown", event => {
    if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onClick(); }
  });
}

function wbActivatable(node, onClick) {
  node.addEventListener("click", event => { event.stopPropagation(); onClick(); });
  node.addEventListener("keydown", event => {
    if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onClick(); }
  });
}

// The boundary of a cell set: one segment per cell edge whose neighbour is
// outside, as [x1, y1, x2, y2, side, cell] in cell units. A round room's arc
// and an L's notch fall out of this without a special case.
function wbBoundary(cells) {
  const has = new Set(cells.map(c => c[0] + "," + c[1]));
  const out = [];
  for (const [x, y] of cells) {
    if (!has.has(x + "," + (y - 1))) out.push([x, y, x + 1, y, "n", [x, y]]);
    if (!has.has((x + 1) + "," + y)) out.push([x + 1, y, x + 1, y + 1, "e", [x, y]]);
    if (!has.has(x + "," + (y + 1))) out.push([x, y + 1, x + 1, y + 1, "s", [x, y]]);
    if (!has.has((x - 1) + "," + y)) out.push([x, y, x, y + 1, "w", [x, y]]);
  }
  return out;
}

// Scroll the card to one editor row and put the focus in it: the click on
// the map is the click on the field.
function wbFocusRow(card, selector) {
  const row = card.querySelector(selector);
  if (!row) return false;
  row.scrollIntoView({ block: "center", behavior: "smooth" });
  row.classList.add("wb-focus");
  setTimeout(() => row.classList.remove("wb-focus"), 1800);
  const control = row.querySelector("input, select, textarea, button");
  if (control) control.focus({ preventScroll: true });
  return true;
}

// How many cells an anchor of this footprint takes along a wall of `along`
// cells -- the engine's table (`spatial_fov._place_anchors`), so a dropped
// anchor's FIRST cell is the cell it was dropped on.
function wbFootprintLength(footprint, along) {
  if (footprint === "run") return Math.max(2, along - 2);
  if (footprint === "small" || footprint === "large") return 2;
  return 1;
}

// The room map: one room's field as `GET /rooms/{id}/grid` returns it.
function wbRenderRoomMap(host, view, ctx, { overlay = null } = {}) {
  host.innerHTML = "";
  const S = WB_CELL;
  const room = view.room;
  const cells = room.cells || [];
  const cellSet = new Set(cells.map(c => c.join(",")));
  const far = view.neighbours || [];
  const bodies = Object.entries(view.bodies || {});
  const unplaced = bodies.filter(([, b]) => !b.cell);
  const laneY = room.d + 1;

  // Bounds over everything drawn, in cells, then a margin for the names.
  let minX = 0, minY = 0, maxX = room.w, maxY = room.d;
  for (const n of far) {
    for (const [x, y] of n.cells) {
      minX = Math.min(minX, x + n.offset[0]); minY = Math.min(minY, y + n.offset[1]);
      maxX = Math.max(maxX, x + n.offset[0] + 1); maxY = Math.max(maxY, y + n.offset[1] + 1);
    }
  }
  for (const d of view.doorways || []) {
    const u = WB_UNIT[d.dir];
    if (!u) continue;
    for (const [x, y] of d.cells) {
      minX = Math.min(minX, x + u[0] * 2); minY = Math.min(minY, y + u[1] * 2);
      maxX = Math.max(maxX, x + u[0] * 2 + 1); maxY = Math.max(maxY, y + u[1] * 2 + 1);
    }
  }
  if (unplaced.length) { maxY = Math.max(maxY, laneY + 1); maxX = Math.max(maxX, unplaced.length); }
  minX -= 1.5; minY -= 1.5; maxX += 1.5; maxY += 1.5;

  const svg = wbSvg("svg", {
    class: "wb-map-svg wb-room-map", role: "group",
    "aria-label": t(`Map of ${room.name}`),
    viewBox: [minX * S, minY * S, (maxX - minX) * S, (maxY - minY) * S].join(" "),
  });
  const layer = name => { const g = wbSvg("g", { class: name }); svg.append(g); return g; };
  const gFar = layer("wb-m-far"), gCells = layer("wb-m-cells"), gTint = layer("wb-m-tints"),
        gWalls = layer("wb-m-walls"), gAnchors = layer("wb-m-anchors"), gThings = layer("wb-m-things"),
        gBodies = layer("wb-m-bodies"), gLint = layer("wb-m-lint"), gLabels = layer("wb-m-labels");

  const cellOf = p => [Math.floor(p.x / S), Math.floor(p.y / S)];
  const inRoom = c => cellSet.has(c.join(","));
  const same = (a, b) => a[0] === b[0] && a[1] === b[1];

  // Which wall a cell of the room is part of (it may be two, at a corner):
  // the rims the server sent, the nearer box side breaking the tie.
  const wallOf = (c, p) => {
    const found = [];
    for (const wall of ctx.vocab.walls || []) {
      const rim = view.rims[wall] || [];
      const idx = rim.findIndex(r => same(r, c));
      if (idx < 0) continue;
      const dist = wall === "n" ? p.y : wall === "s" ? room.d * S - p.y
        : wall === "w" ? p.x : room.w * S - p.x;
      found.push({ wall, idx, len: rim.length, dist });
    }
    found.sort((a, b) => a.dist - b.dist);
    return found[0] || null;
  };

  // The hints, translated once each; the titles below join them to names
  // with punctuation only, so the catalog carries the words and not the
  // joins.
  const openHint = t("open this room");
  const anchorHint = t("click to edit, drag onto a wall or any cell to move");
  const doorwayTo = t("Doorway to");
  const doorHint = t("click for the exit, drag along the wall to move it");
  const thingHint = t("click to edit");
  const bodyHint = t("click for the station, drag onto any cell to place");
  const atWord = t("at");
  const pinnedWord = t("pinned to this cell");

  // -- the neighbours, faintly, where the field lays them ------------------
  for (const n of far) {
    const g = wbSvg("g", { class: "wb-m-neighbour", "data-room": n.id, tabindex: "0", role: "button" },
      wbSvg("title", {}, `${n.name} — ${openHint}`));
    for (const [x, y] of n.cells) {
      g.append(wbSvg("rect", { x: (x + n.offset[0]) * S, y: (y + n.offset[1]) * S,
                               width: S, height: S, class: "wb-m-far-cell" }));
    }
    for (const seg of wbBoundary(n.cells)) {
      g.append(wbSvg("line", { x1: (seg[0] + n.offset[0]) * S, y1: (seg[1] + n.offset[1]) * S,
                               x2: (seg[2] + n.offset[0]) * S, y2: (seg[3] + n.offset[1]) * S,
                               class: "wb-m-far-edge" }));
    }
    for (const [aid, a] of Object.entries(n.anchors || {})) {
      if (a.implicit) continue;
      for (const [x, y] of a.cells) {
        g.append(wbSvg("rect", { x: (x + n.offset[0]) * S + 2, y: (y + n.offset[1]) * S + 2,
                                 width: S - 4, height: S - 4, rx: 3, class: "wb-m-far-anchor" },
          wbSvg("title", {}, `${a.desc} (${aid})`)));
      }
    }
    if (n.cells.length) {
      const cx = n.cells.reduce((s, c) => s + c[0], 0) / n.cells.length + n.offset[0] + 0.5;
      const cy = n.cells.reduce((s, c) => s + c[1], 0) / n.cells.length + n.offset[1] + 0.5;
      g.append(wbSvg("text", { x: cx * S, y: cy * S + 3, "text-anchor": "middle",
                               class: "wb-m-far-name" }, n.name));
    }
    wbActivatable(g, () => ctx.select(n.id));
    gFar.append(g);
  }

  // -- the room's cells, and the overlay's tint over them ----------------
  for (const [x, y] of cells) {
    gCells.append(wbSvg("rect", { x: x * S, y: y * S, width: S, height: S, class: "wb-m-cell" }));
  }
  const readings = overlay && view.overlays && view.overlays[overlay];
  if (readings && typeof readings === "object") {
    const words = [];
    for (const word of Object.values(readings)) if (!words.includes(word)) words.push(word);
    for (const [key, word] of Object.entries(readings)) {
      const [x, y] = key.split(",").map(Number);
      if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
      const i = words.indexOf(word);
      const pct = words.length > 1 ? 12 + 70 * (i / (words.length - 1)) : 45;
      gTint.append(wbSvg("rect", { x: x * S, y: y * S, width: S, height: S, class: "wb-m-tint",
                                   style: `fill:color-mix(in srgb,var(--acc) ${pct}%,transparent)` },
        wbSvg("title", {}, `${overlay}: ${word}`)));
    }
  }

  // -- the boundary as a line, with each doorway a gap in it -------------
  const doorAt = new Map();
  for (const d of view.doorways || []) {
    for (const c of d.cells) doorAt.set(`${c[0]},${c[1]}|${d.dir}`, d);
  }
  for (const seg of wbBoundary(cells)) {
    if (doorAt.has(`${seg[5][0]},${seg[5][1]}|${seg[4]}`)) continue;
    gWalls.append(wbSvg("line", { x1: seg[0] * S, y1: seg[1] * S, x2: seg[2] * S, y2: seg[3] * S,
                                  class: "wb-m-edge" }));
  }
  const placedFar = new Set(far.map(n => n.id));
  for (const d of view.doorways || []) {
    if (!d.cells.length || !WB_UNIT[d.dir]) continue;
    const u = WB_UNIT[d.dir];
    const g = wbSvg("g", { class: "wb-m-doorway", "data-exit": d.to, tabindex: "0", role: "button" },
      wbSvg("title", {}, `${doorwayTo} ${d.name} (${d.barrier}) — ${doorHint}`));
    for (const [x, y] of d.cells) {
      if (u[0] && u[1]) {
        g.append(wbSvg("circle", { cx: (x + 0.5 + u[0] * 0.5) * S, cy: (y + 0.5 + u[1] * 0.5) * S,
                                   r: S * 0.22, class: "wb-m-door-corner" }));
        continue;
      }
      const x1 = u[0] === 1 ? x + 1 : x, x2 = u[0] === -1 ? x : x + 1;
      const y1 = u[1] === 1 ? y + 1 : y, y2 = u[1] === -1 ? y : y + 1;
      g.append(wbSvg("line", { x1: (u[0] ? x1 : x) * S, y1: (u[1] ? y1 : y) * S,
                               x2: (u[0] ? x1 : x2) * S, y2: (u[1] ? y1 : y2) * S,
                               class: "wb-m-door" }));
      // A line has no area to press on; the hit rect straddling it does.
      g.append(wbSvg("rect", {
        x: u[0] ? x1 * S - 5 : x * S, y: u[1] ? y1 * S - 5 : y * S,
        width: u[0] ? 10 : S, height: u[1] ? 10 : S, class: "wb-m-door-hit" }));
    }
    // The neighbour's name beyond the door, when its cells are not drawn
    // there already (its own label says it then).
    if (!placedFar.has(d.to)) {
      const [x, y] = d.cells[0];
      g.append(wbSvg("text", { x: (x + 0.5 + u[0] * 1.6) * S, y: (y + 0.5 + u[1] * 1.6) * S + 3,
                               "text-anchor": "middle", class: "wb-m-far-name" }, d.name));
    }
    wbDraggable(svg, g, {
      onClick: () => ctx.focusRow(`.wb-exit[data-exit="${CSS.escape(d.to)}"]`),
      onDrop: p => dropDoorway(d, p),
    });
    gWalls.append(g);
  }

  // -- anchors: footprint cells, the id, a height mark -------------------
  // The heights in the engine's order give the mark its rank; the first
  // opacity word is the engine's default (the one that blocks sight), so an
  // anchor carrying any other is drawn as one a line passes through. Both
  // read from `vocab`; no word is typed here.
  const heights = ctx.vocab.heights || [];
  const opaque = (ctx.vocab.opacities || [])[0];
  for (const [aid, a] of Object.entries(view.anchors || {})) {
    if (!a.cells.length) continue;
    const g = wbSvg("g", { class: "wb-m-anchor", "data-anchor": aid, tabindex: "0", role: "button" },
      wbSvg("title", {}, `${a.desc} (${aid}) — ${anchorHint}`));
    const passes = opaque && a.opacity && a.opacity !== opaque;
    for (const [x, y] of a.cells) {
      g.append(wbSvg("rect", { x: x * S + 1, y: y * S + 1, width: S - 2, height: S - 2, rx: 3,
                               class: "wb-m-anchor-cell" + (passes ? " see-through" : "") }));
    }
    const [x0, y0] = a.cells[0];
    const rank = Math.max(0, heights.indexOf(a.height));
    const top = Math.max(1, heights.length - 1);
    if (rank > 0) {
      const h = (S - 6) * rank / top;
      g.append(wbSvg("rect", { x: x0 * S + S - 6, y: y0 * S + S - 3 - h, width: 3, height: h,
                               class: "wb-m-height" }, wbSvg("title", {}, a.height)));
    }
    g.append(wbSvg("text", { x: x0 * S + 3, y: y0 * S + 10, class: "wb-m-label" },
      aid.length > 9 ? aid.slice(0, 8) + "…" : aid));
    wbDraggable(svg, g, {
      onClick: () => ctx.focusRow(`.wb-anchor[data-anchor="${CSS.escape(aid)}"]`),
      onDrop: p => dropAnchor(aid, a, p),
    });
    gAnchors.append(g);
  }

  // -- things placed by a position and a station ---------------------------
  for (const th of view.things || []) {
    if (!th.cell) continue;
    const cx = (th.cell[0] + 0.5) * S, cy = (th.cell[1] + 0.5) * S, r = S * 0.3;
    const g = wbSvg("g", { class: "wb-m-thing", "data-thing": th.id, tabindex: "0", role: "button" },
      wbSvg("title", {}, `${th.name}${th.kind ? " (" + th.kind + ")" : ""} — ${thingHint}`),
      wbSvg("polygon", { points: [[cx, cy - r], [cx + r, cy], [cx, cy + r], [cx - r, cy]]
                                    .map(pt => pt.join(",")).join(" ") }),
      wbSvg("text", { x: cx, y: cy + r + 9, "text-anchor": "middle", class: "wb-m-name" }, th.name));
    wbActivatable(g, () => ctx.focusRow(`.wb-thing[data-thing="${CSS.escape(th.id)}"]`));
    gThings.append(g);
  }

  // -- bodies: a marked cell with a facing tick; the unstationed in a lane --
  let lane = 0;
  for (const [name, b] of bodies) {
    const cell = b.cell || [lane++, laneY];
    const cx = (cell[0] + 0.5) * S, cy = (cell[1] + 0.5) * S;
    // `source` says what placed the body: its own pinned cell, its
    // anchor, or nothing -- the server's word, never re-derived here.
    const where = b.cell
      ? [b.at ? `${atWord} ${b.at}` : t("free in the room"),
         b.source === "cell" ? pinnedWord : null].filter(Boolean).join(", ")
      : t("somewhere in the room — no station");
    const g = wbSvg("g", { class: "wb-m-body " + b.kind + (b.cell ? "" : " unplaced")
                                  + (b.source === "cell" ? " pinned" : ""),
                           "data-body": name, tabindex: "0", role: "button" },
      wbSvg("title", {}, `${name} — ${where} — ${bodyHint}`),
      wbSvg("circle", { cx, cy, r: S * 0.34, class: "wb-m-body-dot" }));
    const u = WB_UNIT[b.facing];
    if (u) {
      const len = Math.hypot(u[0], u[1]);
      g.append(wbSvg("line", { x1: cx, y1: cy, x2: cx + u[0] / len * S * 0.48, y2: cy + u[1] / len * S * 0.48,
                               class: "wb-m-facing" }));
    }
    g.append(wbSvg("text", { x: cx, y: cy + S * 0.34 + 9, "text-anchor": "middle", class: "wb-m-name" }, name));
    wbDraggable(svg, g, {
      onClick: () => ctx.focusRow(`.wb-body[data-body="${CSS.escape(name)}"]`),
      onDrop: p => dropBody(name, b, p),
    });
    gBodies.append(g);
  }
  if (unplaced.length) {
    gLabels.append(wbSvg("text", { x: 0, y: laneY * S - 5, class: "wb-m-lane" },
      t("No station — somewhere in the room:")));
  }

  // -- the lint, drawn at the thing each row concerns ---------------------
  let slot = 0;
  const mark = (x, y, row) => {
    const g = wbSvg("g", { class: "wb-m-lint-mark", "data-kind": row.kind, tabindex: "0", role: "button" },
      wbSvg("title", {}, row.text),
      wbSvg("circle", { cx: x, cy: y, r: 7 }),
      wbSvg("text", { x, y: y + 3.5, "text-anchor": "middle" }, "!"));
    wbActivatable(g, () => ctx.focusRow(`.wb-lint[data-kind="${CSS.escape(row.kind)}"]`));
    gLint.append(g);
  };
  const cornerMark = row => { mark((0.5 + slot++) * S, -S * 0.5, row); };
  // Where a row is drawn follows what the row NAMES -- `openings` (anchor
  // ids), `wall`, a `rooms` pair -- never its kind by name: the kinds are the
  // lint's own closed set and this file types none of them.
  for (const row of view.lint || []) {
    const rim = row.wall ? view.rims[row.wall] || [] : [];
    if (Array.isArray(row.openings) && row.openings.length) {
      let drawn = false;
      for (const id of row.openings) {
        const d = (view.doorways || []).find(x => x.id === id);
        if (!d || !d.cells.length) continue;
        const u = WB_UNIT[d.dir] || [0, 0];
        mark((d.cells[0][0] + 0.5 + u[0] * 0.8) * S, (d.cells[0][1] + 0.5 + u[1] * 0.8) * S, row);
        drawn = true;
      }
      if (!drawn) cornerMark(row);
    } else if (rim.length) {
      const u = WB_UNIT[row.wall];
      for (const [x, y] of rim) {
        const x1 = u[0] === 1 ? x + 1 : x, x2 = u[0] === -1 ? x : x + 1;
        const y1 = u[1] === 1 ? y + 1 : y, y2 = u[1] === -1 ? y : y + 1;
        gLint.append(wbSvg("line", { x1: (u[0] ? x1 : x) * S, y1: (u[1] ? y1 : y) * S,
                                     x2: (u[0] ? x1 : x2) * S, y2: (u[1] ? y1 : y2) * S,
                                     class: "wb-m-lint-wall" }, wbSvg("title", {}, row.text)));
      }
      const mid = rim[Math.floor(rim.length / 2)];
      mark((mid[0] + 0.5 + u[0] * 0.5) * S, (mid[1] + 0.5 + u[1] * 0.5) * S, row);
    } else if (Array.isArray(row.rooms) && row.rooms.length > 1) {
      const other = row.rooms.find(r => r !== room.id);
      const n = far.find(x => x.id === other);
      const d = (view.doorways || []).find(x => x.to === other);
      if (n && n.cells.length) {
        const cx = n.cells.reduce((s, c) => s + c[0], 0) / n.cells.length + n.offset[0] + 0.5;
        const cy = n.cells.reduce((s, c) => s + c[1], 0) / n.cells.length + n.offset[1] + 0.5;
        mark(cx * S, cy * S - 12, row);
      } else if (d && d.cells.length) {
        const u = WB_UNIT[d.dir] || [0, 0];
        mark((d.cells[0][0] + 0.5 + u[0] * 0.8) * S, (d.cells[0][1] + 0.5 + u[1] * 0.8) * S, row);
      } else {
        cornerMark(row);
      }
    } else {
      cornerMark(row);
    }
  }

  // -- the drops --------------------------------------------------------------
  async function dropAnchor(aid, a, p) {
    const slice = ctx.currentSlice();
    if (!slice || !slice.record || !slice.record.anchors || !slice.record.anchors[aid]) return;
    const c = cellOf(p);
    if (!inRoom(c)) return toast(t("Drop the anchor on a wall of this room, or inside it."), "warn");
    const anchors = {};
    for (const [id, rec] of Object.entries(slice.record.anchors)) anchors[id] = { ...rec };
    // A wall cell writes the wall and a place along it (`dir` + `offset`)
    // and lets the pin go; any other cell PINS the anchor there (`cell`,
    // its origin -- the owner, 2026-09-04: "I can only place anchors at
    // stations when I don't wall-attach them") and clears the wall and the
    // offset. The two placements are exclusive on the server too.
    const wall = wallOf(c, p);
    if (wall) {
      const length = wbFootprintLength(a.footprint, wall.len);
      const offset = Math.min(1, Math.max(0, wall.idx / Math.max(1, wall.len - length)));
      anchors[aid] = { ...anchors[aid], dir: wall.wall, offset, cell: null };
    } else {
      anchors[aid] = { ...anchors[aid], dir: "", offset: null, cell: c };
    }
    await ctx.patchRoom({ anchors });
  }

  async function dropDoorway(d, p) {
    const slice = ctx.currentSlice();
    if (!slice || !slice.record) return;
    const stored = slice.record.adjacent || [];
    if (!stored.some(e => e.to === d.to)) {
      return toast(t("This doorway is declared from the far room; open that room to move it."), "warn", 6000);
    }
    const rim = view.rims[d.dir] || [];
    if (rim.length < 2) return;
    const axis = d.dir === "n" || d.dir === "s" ? 0 : 1;
    const c = cellOf(p);
    let idx = rim.findIndex(r => r[axis] === c[axis]);
    if (idx < 0) idx = c[axis] < rim[0][axis] ? 0 : rim.length - 1;
    const width = Math.max(1, d.cells.length);
    const offset = Math.min(1, Math.max(0, idx / Math.max(1, rim.length - width)));
    await ctx.patchRoom({ exits: stored.map(e => ({
      to: e.to, barrier: e.barrier || "", dir: e.dir || "",
      ...(e.to === d.to ? { offset } : {}) })) });
  }

  // A body dropped on ANY cell of its room is pinned to it (`cell`, in the
  // room's own grid -- the owner, 2026-09-04: "why are characters and
  // personas locked to stations?"); when the cell is an anchor's, `at` is
  // written too, for prose, else cleared. Dropped in a neighbour's cells it
  // moves rooms and is pinned to the cell in the NEIGHBOUR's coordinates.
  async function dropBody(name, b, p) {
    const c = cellOf(p);
    if (inRoom(c)) {
      const anchor = Object.entries(view.anchors || {}).find(([, a]) => a.cells.some(k => same(k, c)));
      const door = (view.doorways || []).find(d => d.cells.some(k => same(k, c)));
      await ctx.putStation(name, { at: anchor ? anchor[0] : door ? door.id : null, near: b.near || [], cell: c });
      return;
    }
    const n = far.find(nb => nb.cells.some(k => same([k[0] + nb.offset[0], k[1] + nb.offset[1]], c)));
    if (!n) return toast(t("Drop the body on a cell of this room, or of a neighbour to move it there."), "warn", 6000);
    const anchor = Object.entries(n.anchors || {}).find(([, a]) =>
      a.cells.some(k => same([k[0] + n.offset[0], k[1] + n.offset[1]], c)));
    await ctx.moveBody(name, n, anchor ? anchor[0] : null, [c[0] - n.offset[0], c[1] - n.offset[1]]);
  }

  host.append(svg);
  return svg;
}

// The structure map: every room as its box placed by bearing, as `GET /map`
// returns it; one connected component after another, left to right.
function wbRenderStructureMap(host, data, ctx, selectedId) {
  host.innerHTML = "";
  const S = WB_MINI;
  const laid = [];
  let cursor = 0, tallest = 0;
  for (const comp of data.components || []) {
    if (!comp.rooms.length) continue;
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const r of comp.rooms) {
      minX = Math.min(minX, r.offset[0]); minY = Math.min(minY, r.offset[1]);
      maxX = Math.max(maxX, r.offset[0] + r.w); maxY = Math.max(maxY, r.offset[1] + r.d);
    }
    laid.push({ comp, dx: cursor - minX, dy: -minY });
    cursor += maxX - minX + 3;
    tallest = Math.max(tallest, maxY - minY);
  }
  if (!laid.length) {
    host.append(el("div", { class: "small dim" }, "No rooms yet — the scene has not been laid out."));
    return null;
  }
  const svg = wbSvg("svg", {
    class: "wb-map-svg wb-structure-map", role: "group",
    "aria-label": t("Every room, placed by bearing"),
    viewBox: [-S, -S, (cursor - 1) * S, (tallest + 2) * S].join(" "),
  });
  const onTopOf = t("placed on top of");
  const reachedThrough = t("reached through");
  const toWord = t("to");
  const noBearing = t("Exits with no bearing:");
  const openGrid = t("click to open its grid");
  for (const { comp, dx, dy } of laid) {
    for (const r of comp.rooms) {
      const ox = (r.offset[0] + dx) * S, oy = (r.offset[1] + dy) * S;
      const w = r.w * S, d = r.d * S;
      const notes = [r.name];
      if (r.collided) notes.push(`${onTopOf} ${r.onto} (${reachedThrough} ${r.via})`);
      if (r.lint) notes.push(t(`${r.lint} layout rows`));
      const g = wbSvg("g", {
        class: "wb-sm-room" + (r.collided ? " collided" : "") + (r.occupants.length ? " occupied" : "")
          + (r.id === selectedId ? " on" : ""),
        "data-room": r.id, tabindex: "0", role: "button",
      }, wbSvg("title", {}, notes.join(" — ") + " — " + openGrid));
      // A room whose cells fill its box is one rectangle; any other shape is
      // its cells with their boundary (no shape word is typed here).
      if (!r.cells || !r.cells.length || r.cells.length === r.w * r.d) {
        g.append(wbSvg("rect", { x: ox, y: oy, width: w, height: d, class: "wb-sm-box" }));
      } else {
        for (const [x, y] of r.cells) {
          g.append(wbSvg("rect", { x: ox + x * S, y: oy + y * S, width: S, height: S, class: "wb-sm-box-cell" }));
        }
        for (const seg of wbBoundary(r.cells)) {
          g.append(wbSvg("line", { x1: ox + seg[0] * S, y1: oy + seg[1] * S,
                                   x2: ox + seg[2] * S, y2: oy + seg[3] * S, class: "wb-sm-edge" }));
        }
      }
      // Exits as ticks on the wall they open in; the unbeared counted.
      let unbeared = [];
      for (const x of r.exits || []) {
        const u = WB_UNIT[x.dir];
        if (!u) { unbeared.push(x.name); continue; }
        const mx = ox + w / 2 + u[0] * w / 2, my = oy + d / 2 + u[1] * d / 2;
        const title = wbSvg("title", {}, `${toWord} ${x.name} (${x.barrier})`);
        if (u[0] && u[1]) {
          g.append(wbSvg("circle", { cx: mx, cy: my, r: S * 0.3, class: "wb-sm-exit" + (x.placed ? "" : " far-unplaced") }, title));
        } else {
          const half = S * 0.6;
          g.append(wbSvg("line", {
            x1: u[0] ? mx : mx - half, y1: u[1] ? my : my - half,
            x2: u[0] ? mx : mx + half, y2: u[1] ? my : my + half,
            class: "wb-sm-exit" + (x.placed ? "" : " far-unplaced") }, title));
        }
      }
      g.append(wbSvg("text", { x: ox + w / 2, y: oy + d / 2 + (r.occupants.length ? 0 : 3),
                               "text-anchor": "middle", class: "wb-sm-name" },
        r.name.length > Math.max(6, r.w * 1.6) ? r.name.slice(0, Math.max(5, Math.floor(r.w * 1.6)) - 1) + "…" : r.name));
      if (r.occupants.length) {
        const who = r.occupants.join(", ");
        g.append(wbSvg("text", { x: ox + w / 2, y: oy + d / 2 + 8, "text-anchor": "middle", class: "wb-sm-who" },
          who.length > Math.max(8, r.w * 2.2) ? who.slice(0, Math.max(7, Math.floor(r.w * 2.2)) - 1) + "…" : who));
      }
      if (unbeared.length) {
        g.append(wbSvg("g", {}, wbSvg("title", {}, `${noBearing} ${unbeared.join(", ")}`),
          wbSvg("text", { x: ox + w - 2, y: oy + d - 2, "text-anchor": "end", class: "wb-sm-unbeared" },
            "?" + unbeared.length)));
      }
      if (r.lint) {
        g.append(wbSvg("circle", { cx: ox + w - 4, cy: oy + 4, r: 3.5, class: "wb-sm-lint" },
          wbSvg("title", {}, t(`${r.lint} layout rows`))));
      }
      wbActivatable(g, () => ctx.select(r.id));
      svg.append(g);
    }
  }
  host.append(svg);
  return svg;
}

// The pane: the map's bar, the canvas, the overlay legend, the notes, and
// the tree folded open beneath.
function wbMapPane() {
  const bar = el("div", { class: "wb-map-bar" });
  const canvas = el("div", { class: "wb-map" });
  const legend = el("div", { class: "wb-map-legend small" });
  const notes = el("div", { class: "wb-map-notes small dim" });
  const tree = el("div", { class: "wb-tree" });
  const pane = el("div", { class: "wb-map-pane" }, bar, canvas, legend, notes,
    el("details", { class: "wb-list", open: "" },
      el("summary", { class: "wb-group" }, "Every room as a list"), tree));
  return { pane, bar, canvas, legend, notes, tree };
}

// What the room map cannot draw, said in words under it: a doorway with no
// bearing, a thing standing here with no station.
function wbMapNotes(host, view) {
  host.innerHTML = "";
  const rows = [];
  for (const d of view.doorways || []) {
    if (!d.cells.length) {
      rows.push(el("div", {}, "Doorway to", " ", el("b", { translate: "no" }, txt(d.name)),
        " ", "has no bearing, so no wall to stand in."));
    }
  }
  const loose = (view.things || []).filter(th => th.placed === "position" && !th.cell).map(th => th.name);
  if (loose.length) {
    rows.push(el("div", {}, "Here with no station:", " ", el("span", { translate: "no" }, txt(loose.join(", ")))));
  }
  host.append(...rows);
}

// The overlay legend: one swatch per word, in the order the readings came.
function wbMapLegend(host, view, overlay) {
  host.innerHTML = "";
  const readings = overlay && view.overlays && view.overlays[overlay];
  if (!readings || typeof readings !== "object") return;
  const words = [];
  for (const word of Object.values(readings)) if (!words.includes(word)) words.push(word);
  host.append(el("span", { class: "dim", translate: "no" }, txt(overlay + ":")));
  words.forEach((word, i) => {
    const pct = words.length > 1 ? 12 + 70 * (i / (words.length - 1)) : 45;
    host.append(el("span", { translate: "no" },
      el("span", { class: "wb-swatch", style: `background:color-mix(in srgb,var(--acc) ${pct}%,transparent)` }),
      txt(word)));
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
    // The map's zoom: "room" (the selected room's grid) or "map" (every
    // room placed by bearing); the grid last drawn; the overlay chosen.
    zoom: "room",
    slice: null,
    grid: null,
    overlay: null,
  };

  modal(rawKind === "attire" ? "Attire" : "World state", b => {
    const alive = modalOwnership(b);
    const tabBar = el("div", { class: "lore-inspector-tabs" });
    const content = el("div", { class: "lore-inspector-content" });

    const map = wbMapPane();
    const tree = map.tree;
    const card = el("div", { class: "wb-card" });
    const location = el("div", { class: "small dim", style: "margin-bottom:6px", translate: "no" });
    const browse = el("div", {}, location, el("div", { class: "wb" }, map.pane, card));
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
      // The card rebuilt from a write's fresh slice, the grid re-read (an
      // anchor moved is a cell moved), the tree re-read, since a rename or
      // an exit changes it too.
      replaceCard: async fresh => {
        if (!alive() || S.chatId !== chatId) return;
        if (fresh && fresh.id === state.selected) {
          state.slice = fresh;
          wbRenderCard(card, fresh, ctx);
        }
        await Promise.all([refreshIndex(), loadGrid(state.selected)]);
      },
      refresh: async () => {
        await refreshIndex();
        if (!alive() || S.chatId !== chatId) return;
        if (state.tab === "rooms") {
          if (state.zoom === "map") await Promise.all([showStructure(), loadCard(state.selected)]);
          else await loadRoom(state.selected);
        } else if (state.tab === "bodies") {
          wbRenderBodies(bodies, ctx);
        }
      },
      // What the map needs of the card and the routes: the slice it edits
      // from, the row a click lands on, and the three writes a drop makes.
      currentSlice: () => state.slice,
      focusRow: selector => wbFocusRow(card, selector),
      patchRoom: fields => wbWrite(ctx, async () => {
        const fresh = await api("PATCH",
          `/api/chats/${chatId}/rooms/${encodeURIComponent(state.selected)}${frameQuery()}`, fields);
        await ctx.replaceCard(fresh);
        return fresh;
      }),
      putStation: (name, body) => wbWrite(ctx, async () => {
        await api("PUT",
          `/api/chats/${chatId}/bodies/${encodeURIComponent(name)}/station${frameQuery()}`, body);
        await ctx.refresh();
        return true;
      }),
      // A body dropped in a neighbour's cells: the cast editor's relocation
      // (only the registered cast has a position route -- the player's
      // place is the story's business, as that editor also holds), then its
      // station there, so nothing stale from the old room survives.
      moveBody: async (name, neighbour, at, cell = null) => {
        const who = (state.positions?.characters || []).find(c => c.name === name);
        if (!who) {
          toast(t("Only a registered cast member can be moved between rooms here; the player's place is the story's business."), "warn", 7000);
          return;
        }
        const done = await wbWrite(ctx, async () => {
          await api("PUT", `/api/chats/${chatId}/characters/${who.id}/position${frameQuery()}`,
            { room: neighbour.id });
          // `cell` is in the NEIGHBOUR's grid: the position route dropped
          // the old room's pin, and this writes the new one.
          await api("PUT",
            `/api/chats/${chatId}/bodies/${encodeURIComponent(name)}/station${frameQuery()}`,
            { at, near: [], cell });
          return true;
        }, { quiet: true });
        if (done) {
          toast(`Moved ${name} to ${neighbour.name}.`, "ok");
          await ctx.refresh();
        }
      },
    };

    // The bar over the map: where the zoom stands, the way up, the overlay.
    function renderMapBar() {
      map.bar.innerHTML = "";
      if (state.zoom === "map") {
        map.bar.append(el("b", {}, "Every room, placed by bearing"),
          el("span", { class: "dim" }, "— click a room to open its grid"));
        return;
      }
      const name = state.grid && state.grid.room ? state.grid.room.name
        : (state.slice ? state.slice.name : state.selected || "");
      map.bar.append(
        el("button", { class: "wb-link wb-map-up", onclick: () => showStructure() }, "All rooms"),
        el("span", { class: "dim" }, "›"),
        el("b", { translate: "no" }, txt(name)));
      const overlays = Object.keys((state.grid && state.grid.overlays) || {});
      if (overlays.length) {
        map.bar.append(wbSelect(overlays, state.overlay || "", {
          blank: "No overlay", title: "Paint a per-cell reading over the grid",
          onchange: v => { state.overlay = v || null; if (state.grid) drawGrid(); } }));
      }
      map.bar.append(el("span", { class: "dim wb-map-hint" }, "Click a thing to edit it; drag to place it."));
    }

    function drawGrid() {
      const view = state.grid;
      if (!view || view.error) return;
      wbRenderRoomMap(map.canvas, view, ctx, { overlay: state.overlay });
      wbMapLegend(map.legend, view, state.overlay);
      wbMapNotes(map.notes, view);
    }

    async function loadGrid(id) {
      if (!id || state.zoom !== "room") return;
      let view;
      try {
        view = await api("GET", `/api/chats/${chatId}/rooms/${encodeURIComponent(id)}/grid${frameQuery()}`);
      } catch (error) {
        view = { error: error?.message || String(error) };
      }
      if (!alive() || S.chatId !== chatId || state.selected !== id || state.zoom !== "room") return;
      state.grid = view;
      renderMapBar();
      if (view.error) {
        map.canvas.innerHTML = "";
        map.canvas.append(el("div", { class: "small dim" }, txt(view.error)));
        map.legend.innerHTML = "";
        map.notes.innerHTML = "";
        return;
      }
      drawGrid();
    }

    async function showStructure() {
      state.zoom = "map";
      renderMapBar();
      map.canvas.innerHTML = "";
      map.canvas.append(el("div", { class: "small dim" }, "Loading…"));
      map.legend.innerHTML = "";
      map.notes.innerHTML = "";
      let data;
      try {
        data = await api("GET", `/api/chats/${chatId}/map${frameQuery()}`);
      } catch (error) {
        if (!alive() || S.chatId !== chatId) return;
        map.canvas.innerHTML = "";
        map.canvas.append(el("div", { class: "err small" }, txt(error?.message || String(error))));
        return;
      }
      if (!alive() || S.chatId !== chatId || state.zoom !== "map") return;
      wbRenderStructureMap(map.canvas, data, ctx, state.selected);
    }

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

    async function loadCard(id) {
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
      state.slice = slice;
      wbRenderCard(card, slice, ctx);
    }

    // Selecting a room: the card on the right, and the map zoomed to its
    // grid on the left, both from the server.
    async function loadRoom(id) {
      state.selected = id;
      state.zoom = "room";
      state.grid = null;
      for (const button of tree.querySelectorAll(".wb-room")) {
        button.classList.toggle("on", button.dataset.room === id);
      }
      renderMapBar();
      if (!id) {
        map.canvas.innerHTML = "";
        map.legend.innerHTML = "";
        map.notes.innerHTML = "";
        return wbRenderCard(card, null, ctx);
      }
      await Promise.all([loadCard(id), loadGrid(id)]);
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
