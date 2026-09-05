"use strict";

// ---- The World Browser ----
//
// The room-centred view of the world state behind the 🌍 and 👕 buttons: a
// tree of every room the story knows on the left, the selected room on the
// right -- its prose, its exits (clickable, so the world is walked rather
// than scrolled), who stands in it and what they wear, what else is here,
// the plan's stub if it is still one, and what the author layer has claimed
// about it. Both read `web/world_routes.py`, which is transport over
// `story/room_slice.py` -- the ONE reader the Writers' Room's `inspect_rooms`
// and the frontier also use, so the host and the Planner see one world.
//
// READ-ONLY, with two exceptions that reuse writes the app already has:
// "Move here" is the cast editor's `PUT /characters/{ch}/position` (idle
// only, room validated against the scene, narrates nothing), and the Raw
// JSON tab IS the two editors that used to be the whole of these buttons --
// the world table and the attire ledger, whole-body PUTs, behaviour
// unchanged -- because hand repair of a drifted scene is how the owner fixes
// one, and a structured view must not take that away.
//
// Attire is shown per body and NOT edited here. `fAttireGarments` (the card
// editor) was considered and does not fit the live ledger: a stored garment
// spanning several regions is recorded once per region without a `covers`
// list, so the editor would read a kimono as torso-only and write it back
// narrowed, and its `read()` writes `state: "worn"` unconditionally, so a
// loosened or open garment would be re-fastened by opening the dialog. Until
// there is a ledger editor that carries `state`, `condition` and the spanning
// copies, the honest control is a link to Raw JSON.
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

// The regions in the ledger's own order (attire.REGIONS), for the per-body
// table. Display order only; the ledger decides what exists.
const WB_REGIONS = ["head", "torso", "arms", "hands", "waist", "groin", "legs", "feet"];

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

function wbStation(station) {
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

function wbGarmentLine(g) {
  if (typeof g === "string") return g;
  if (!g || typeof g !== "object") return "";
  const parts = [g.name || ""];
  if (g.state && g.state !== "worn") parts.push(`(${g.state})`);
  if (g.condition) parts.push(`— ${g.condition}`);
  return parts.join(" ");
}

function wbAttire(entry, showRaw) {
  // The ledger AS STORED (the slice's contract): `wearing` and `state` are
  // its own summary of itself, `regions` the per-region table. Shown, not
  // edited -- see the file comment for why the card editor does not fit.
  if (!entry || typeof entry !== "object") {
    return el("div", { class: "small dim" }, "No attire recorded for this body.");
  }
  const wearing = Array.isArray(entry.wearing) ? entry.wearing : [];
  const state = Array.isArray(entry.state) ? entry.state : [];
  const regions = entry.regions && typeof entry.regions === "object" ? entry.regions : {};
  const regionRows = WB_REGIONS
    .concat(Object.keys(regions).filter(r => !WB_REGIONS.includes(r)))
    .filter(r => regions[r] && typeof regions[r] === "object")
    .map(r => {
      const entryFor = regions[r];
      const garments = (entryFor.garments || []).map(wbGarmentLine).filter(Boolean);
      return el("tr", {},
        el("td", { class: "dim" }, r),
        el("td", {},
          el("span", { translate: "no" }, txt(garments.length ? garments.join("; ") : "—")),
          entryFor.beneath
            ? el("span", { class: "dim" }, " (", "Underneath:", " ",
                el("span", { translate: "no" }, txt(entryFor.beneath)), ")")
            : null));
    });
  return el("div", { class: "wb-attire" },
    el("div", {},
      el("span", { class: "dim" }, "Wearing:"), " ",
      el("span", { translate: "no" }, txt(wearing.length ? wearing.join(", ") : "—"))),
    state.length
      ? el("div", {},
          el("span", { class: "dim" }, "State:"), " ",
          el("span", { translate: "no" }, txt(state.join("; "))))
      : null,
    regionRows.length ? el("table", {}, ...regionRows) : null,
    el("div", { class: "small dim", style: "margin-top:4px" },
      "Attire is read-only here; hand-correct it under ",
      el("button", { class: "wb-link", onclick: showRaw }, "Raw JSON"),
      "."));
}

function wbMoveControl(slice, positions, chatId, onMoved) {
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
      await api("PUT",
        `/api/chats/${chatId}/characters/${who.id}/position${frameQuery()}`,
        { room: slice.id });
      toast(`Moved ${who.name} here.`, "ok");
      await onMoved();
    } catch (error) {
      toast(error?.message || String(error), "err", 8000);
    } finally {
      button.disabled = false;
    }
  } }, "Move here");
  return el("div", { class: "row", style: "margin-top:6px" }, select, button);
}

function wbRenderCard(host, slice, ctx) {
  host.innerHTML = "";
  if (!slice) {
    host.append(el("div", { class: "small dim" }, "Pick a room on the left."));
    return;
  }
  const head = el("div", { class: "row", style: "align-items:baseline" },
    el("h3", { style: "margin:0", translate: "no" }, txt(slice.name)),
    wbStatusBadge(slice.status),
    el("span", { class: "small dim", translate: "no" }, txt(slice.id)));
  host.append(head);
  if (slice.holder) {
    host.append(el("div", { class: "small dim" }, "Inside", " ",
      el("b", { translate: "no" }, txt(slice.holder_name || slice.holder))));
  }
  const move = wbMoveControl(slice, ctx.positions, ctx.chatId, ctx.refresh);
  if (move) host.append(move);

  host.append(slice.description
    ? el("p", { class: "wb-desc", translate: "no" }, txt(slice.description))
    : el("p", { class: "small dim" }, "No description yet."));

  // Exits: the way the world is walked. A link per far room, with what is
  // between (barrier, direction) and a badge when the far room is not live.
  const exits = slice.exits || [];
  host.append(wbSection("Exits",
    exits.length
      ? el("div", {}, ...exits.map(x => el("div", { class: "wb-exit" },
          el("button", { class: "wb-link", translate: "no",
                         onclick: () => ctx.select(x.to) }, txt(x.name || x.to)),
          (x.barrier || x.dir)
            ? el("span", { class: "small dim", translate: "no" },
                txt([x.barrier, x.dir].filter(Boolean).join(", ")))
            : null,
          wbStatusBadge(x.status))))
      : el("div", { class: "small dim" }, "No exits recorded.")));

  // Who is here, each row opening onto the body's attire.
  const occupants = slice.occupants || [];
  host.append(wbSection("Who is here",
    occupants.length
      ? el("div", {}, ...occupants.map(o => el("details",
          { class: "wb-body", ...(ctx.expandAttire ? { open: "" } : {}) },
          el("summary", {},
            el("b", { translate: "no" }, txt(o.name)),
            wbStation(o.station),
            o.attire && Array.isArray(o.attire.wearing)
              ? el("span", { class: "small dim" }, " · ",
                  `Garments: ${o.attire.wearing.length}`)
              : null),
          wbAttire(o.attire, ctx.showRaw))))
      : el("div", { class: "small dim" }, "Nobody is here.")));

  const things = slice.things || [];
  host.append(wbSection("Things",
    things.length
      ? el("div", {}, ...things.map(th => el("div", { class: "wb-exit" },
          el("span", { translate: "no" }, txt(th.name)),
          th.kind ? el("span", { class: "small dim", translate: "no" }, txt(th.kind)) : null,
          th.plan_ref
            ? el("span", { class: "badge", title: th.plan_ref }, "From the plan")
            : null)))
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
  const state = {
    index,
    positions,
    selected: opts.room || positions?.persona?.room || firstRoom(index),
    tab: opts.tab === "raw" ? "raw" : "browse",
    cache: {},
  };

  modal(rawKind === "attire" ? "Attire" : "World state", b => {
    const alive = modalOwnership(b);
    const tabBar = el("div", { class: "lore-inspector-tabs" });
    const content = el("div", { class: "lore-inspector-content" });
    const tabs = [["browse", "Browse"], ["raw", "Raw JSON"]];

    const tree = el("div", { class: "wb-tree" });
    const card = el("div", { class: "wb-card" });
    const browse = el("div", {},
      index.location
        ? el("div", { class: "small dim", style: "margin-bottom:6px", translate: "no" },
            txt(index.location))
        : null,
      el("div", { class: "wb" }, tree, card));

    const ctx = {
      chatId,
      positions: state.positions,
      expandAttire: !!opts.expandAttire,
      select: id => loadRoom(id),
      showRaw: () => selectTab("raw"),
      refresh: async () => {
        const [idx, pos] = await Promise.all([
          api("GET", `/api/chats/${chatId}/rooms${frameQuery()}`),
          api("GET", `/api/chats/${chatId}/positions${frameQuery()}`).catch(() => null),
        ]);
        if (!alive() || S.chatId !== chatId) return;
        state.index = idx;
        state.positions = pos;
        ctx.positions = pos;
        wbRenderTree(tree, state.index, state.selected, loadRoom);
        await loadRoom(state.selected);
      },
    };

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
      // The opening request may ask for the attire rows open; a room chosen
      // afterwards opens closed, as a list of bodies normally does.
      ctx.expandAttire = false;
    }

    function selectTab(tabId) {
      state.tab = tabId;
      for (const button of tabBar.querySelectorAll("button")) {
        button.classList.toggle("on", button.dataset.tab === tabId);
      }
      content.innerHTML = "";
      if (tabId === "raw") {
        wbRenderRaw(content, chatId, rawKind, state.cache);
      } else {
        content.append(browse);
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
    wbRenderTree(tree, state.index, state.selected, loadRoom);
    selectTab(state.tab);
    loadRoom(state.selected);
  }, { wide: true, autoFocus: false });
}

// Both handlers carry the chat guard in the shape chat.js's
// `updateChatScopedButtons` is derived from, so the buttons are disabled
// with no story open rather than being a dead click.
$("#b-world").onclick = async () => {
  if (!S.chatId) return;
  await openWorldBrowser({ raw: "world" });
};
// The attire button opens the same browser on the player's room with every
// body's attire unfolded; its Raw JSON tab is the attire ledger.
$("#b-attire").onclick = async () => {
  if (!S.chatId) return;
  await openWorldBrowser({ raw: "attire", expandAttire: true });
};

window.openWorldBrowser = openWorldBrowser;
