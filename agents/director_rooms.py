"""The prose contract's room designer: a tool-using agent that designs places.

A room here is not a formatting job. The designer reads the Director's prose,
studies the geometry around the place, lays the room out in pieces -- its
shape and extent in paces, its doorways on the walls that face the rooms they
join, its fixtures with their size and height, its light, surface, sound and
exposure -- then LOOKS at what it built on the engine's own cell grid, runs the
engine's own layout check, and refines until the room is detailed, true to
the prose, and geometrically sound. The owner's ruling (2026-09-17) is the
reason for the shape: a one-shot JSON answer gets one attempt and cannot be
told it was wrong; a tool loop drafts in pieces and asks the engine to check
what it has before it commits.

It runs BESIDE the encoder (`director_prose.run`), on the Writers' Room loop
protocol (`agents/story_planner.run_planner`): every step the model returns
`{"calls": [{"tool", "args"}], "done"}`, code runs the calls, and the results
come back in the next step's transcript. Its work is two kinds of place:

- a PLANNED room the beat enters (`develop`): the Writers' Room's plan says
  what the room is for and what it joins, and those stay; the designer
  develops everything in it;
- a place the Director INVENTED (`reserved_places`): the Director named it in
  three fields (name, size, shape); the designer builds the rest.

Nothing here commits. `design_rooms` returns the draft as the three room
channels; the prose contract applies it as the beat's first row, through the
same bind/validate/fold every hand's work takes.

WHAT A MODEL STEP IS NOT SPENT ON (2026-09-27). Traced whole on the betrayal
replay's yard, plain GLM 5.2 with reasoning off: 42-48 s and all eight steps,
of which two were spent inspecting the rooms around the yard, one looking
again at a plan it had just been shown, and three on contradictions the
check would have named the moment the yard was drafted -- a size word its
extent disagreed with, a doorway on a wall another doorway already held, and
a placement that laid the yard over the barracks. The step cap stopped it,
and "clean" only because the engine had quietly dropped the bearing from both
doorways on that wall. None of that needs a model, so code does it: the
standing rooms around the place arrive already inspected (`surroundings`);
for a place the Director invented, the walls where its doorway joins the world
without contradicting it arrive tried against the engine's own check, with
the floor area its size word covers (`placing`); the check runs after every
step that changes the draft; and a size word is set to the one its extent
measures. The decision model then says when the design is finished -- the
check clean, and every room holding what the prose puts in it -- so the loop
no longer waits for a step spent saying so.
"""

from __future__ import annotations

import copy
import json
import time

#: Steps the designer may take, and the wall it may spend. Named per the
#: owner's ask-before-limiting rule: this is a design job and is given room
#: to iterate; on either cap the draft it has is what is kept.
MAX_ROOM_STEPS = 8
MAX_ROOM_SECONDS = 150.0
#: Tool calls honoured per step.
MAX_ROOM_CALLS_PER_STEP = 6
#: Characters of one tool result shown back, and of the transcript overall.
ROOM_RESULT_CHARS = 6_000
ROOM_TRANSCRIPT_CHARS = 30_000
#: Characters of one `inspect_rooms` result, fitted room by room
#: (`_fit_inspection`). Since `_groundwork` the room author is no longer
#: handed the town's records, so this tool is how it reads any other room,
#: and a raw cut at `ROOM_RESULT_CHARS` mid-record was a room it could not
#: read at all. Sized to hold the largest whole record measured -- chat
#: 166's low walk, 11.5k -- beside its drawing, and under
#: `ROOM_TRANSCRIPT_CHARS`; rooms past it come back named, to ask for again.
ROOM_INSPECT_CHARS = 16_000
#: Standing rooms handed over already inspected -- `_inspect`'s own cap.
ROOM_SURROUNDINGS = 6
#: Wall seconds code may spend trying where a new place's doorway fits
#: (`_doorways_that_fit`), per search. Sized at first for "about 13 ms a try
#: on a six-room scene"; by chat 166's 33-room turn-22 checkpoint a try cost
#: 0.19 s (a copy and a merge of the town and two whole checks), and the
#: search finished 10 of its 63 tries. Measured 2026-10-08 after the search
#: was rebuilt: a wall is screened against the check's own walks in about
#: 2.6 ms there and one that passes costs one real merge (about 48 ms); the
#: slowest of the seven recorded in-beat searches -- that checkpoint, eight
#: rooms tried, thirteen walls found -- finishes in about 0.9 s and the
#: median in 0.37 s (re-measured after a wall the walks refuse on a host
#: standing on a site plan was put to the merge as well: chat 160 turn 2, one
#: such host of five, 0.32 s -> 0.37 s under one load). 1.5 s is kept, under
#: twice the slowest, and is the owner's to set; when it runs out, the rooms
#: not yet tried are named to the designer (`not_tried`), never left to read
#: as "nothing fits". A place
#: whose id sorts before its part of a large town is the slow case: every
#: wall the walks cannot judge goes to the whole check (an unbounded search
#: with every room of chat 166's town as a host took 24-25 s for such an
#: id, 8 s for one that sorts last).
ROOM_PLACEMENT_SECONDS = 1.5
#: The decision model's stop: with the check clean, every completeness
#: answer under its bar finishes the design; one at or over it keeps the
#: loop going. Keyed by the pack's question. Probed 2026-09-27 on the yard's
#: five live drafts and eight recorded designer runs, each finished and with
#: what the prose puts in it taken out: at these bars every stripped draft
#: was held and every finished one let through but the osteria (a part
#: answer of 0.50-0.54, one extra step) -- and the lighthouse rail, held
#: because its record never mentions the initials the prose cuts into it,
#: which is the question working. `room_done_unlisted` at 0.5 held a
#: finished yard three steps (0.54-0.56 on "at Anselm's shoulder") and the
#: designer wrote the body's place into a fixture to satisfy it.
ROOM_DONE_BARS = {"room_done_missing": 0.5, "room_done_unlisted": 0.6}
#: The engine's eight bearings, cardinal walls first: the order in which a
#: new place's doorways are tried and offered.
_WALLS_TRIED = ("n", "e", "s", "w", "ne", "se", "sw", "nw")
#: Jev question keys for the stop, read from the pack's prose contract.
_DONE_QUESTIONS = tuple(ROOM_DONE_BARS)

#: The designer's tools, as the manifest its sheet shows it.
ROOM_TOOLS = {
    "inspect_rooms": {
        "args": {"room_ids": "list of room ids"},
        "does": "Rooms already in the world, whole: each one's stored record "
                "exactly as the world holds it -- every field, its doorways "
                "and fixtures included -- and its cell map. The rooms around "
                "your place are already in `surroundings`, with their records "
                "in `rooms`; this is for any other room.",
    },
    "draft_room": {
        "args": {"room_id": "string", "room": "a partial room record in the "
                 "rooms shape below"},
        "does": "Build or change one room of your draft. Fields MERGE across "
                "calls: anchors merge by anchor id, adjacent by `to`, anything "
                "else is replaced; an adjacent entry `{\"to\": ..., \"drop\": "
                "true}` takes that doorway out of your draft (a standing "
                "doorway is part of the world and stays). Returns the room's "
                "floor plan as the engine now draws it, so you see every "
                "change as you make it. Several draft_room calls may share "
                "one step.",
    },
    "view_room": {
        "args": {"room_id": "string"},
        "does": "Your draft merged into the world and drawn on the engine's "
                "own cell grid, north at the top: every cell of the floor, every "
                "doorway, every fixture where the engine actually put it, and "
                "how it read each fixture's footprint and height. Look before "
                "you submit.",
    },
    "check": {
        "args": {},
        "does": "The engine's layout check over your draft merged into the "
                "world: every geometric contradiction it introduces, and any "
                "room you owe that is not drafted yet. The engine already "
                "runs it after every step that changes your draft.",
    },
    "submit": {
        "args": {},
        "does": "Finish. Runs the check first; refused, with the problems, "
                "while it is not clean.",
    },
}


def _merge_room(base, piece):
    out = dict(base or {})
    for key, value in (piece or {}).items():
        if key == "anchors" and isinstance(value, dict):
            anchors = dict(out.get("anchors") or {})
            for aid, anchor in value.items():
                if isinstance(anchor, dict) and isinstance(anchors.get(aid), dict):
                    anchors[aid] = dict(anchors[aid], **anchor)
                else:
                    anchors[aid] = anchor
            out["anchors"] = anchors
        elif key == "adjacent" and isinstance(value, list):
            edges = {str((e or {}).get("to")): e for e in (out.get("adjacent") or [])
                     if isinstance(e, dict) and e.get("to")}
            for edge in value:
                if isinstance(edge, dict) and edge.get("to"):
                    to = str(edge["to"])
                    if edge.get("drop") is True:
                        # Out of the DRAFT, never out of the world: a
                        # standing doorway is not in this record to drop
                        # (the 2026-09-27 yard: a designer that could only
                        # add doorways circled five steps round one it
                        # could not take back).
                        edges.pop(to, None)
                        continue
                    edges[to] = dict(edges.get(to) or {}, **edge)
            out["adjacent"] = list(edges.values())
        else:
            out[key] = value
    return out


def _merged(scene, draft):
    from world.spatial import merge_scene_with_diff
    rooms = {rid: room for rid, room in (draft.get("rooms") or {}).items()}
    diff = {"rooms": copy.deepcopy(rooms)} if rooms else {}
    for key in ("remove_rooms", "remove_adjacent"):
        if draft.get(key):
            diff[key] = copy.deepcopy(draft[key])
    return merge_scene_with_diff(copy.deepcopy(scene or {}), diff) if diff else copy.deepcopy(scene or {})


class _Reading:
    """ONE DESIGN RUN'S READING OF THE WORLD IT DESIGNS AGAINST: the world's
    own check rows, read once, because the world does not change while a
    design runs; the draft merged into it, merged again only when the draft
    changed; and what the run has taken back (`withdrawn`).

    Every pass of a check -- the far sides (`_derive_far_bearings`), the
    doorways (`_place_doorways`), the packing (`_pack`), the size words
    (`_agree_sizes`), the check itself (`_check`) -- asked for the same merge
    and the world's rows afresh: on chat 166's 33-room turn-22 draft a
    check's passes took 0.94 s against 0.28 s for the check alone, and a far
    side the world refused was tried again at every check, two merges and
    four whole checks each time (round one's review, 2026-10-08). A merge is
    shared by readers only; none of them writes it."""

    def __init__(self, scene):
        self.scene = scene
        self.withdrawn = set()
        self._standing = None
        self._kept = {}

    def standing(self) -> set:
        """The world's own rows, as keys (`layout_row_key`)."""
        if self._standing is None:
            from world.spatial import layout_row_key, room_layout_lint
            self._standing = {layout_row_key(row) for row in room_layout_lint(self.scene)}
        return self._standing

    def _entry(self, draft) -> dict:
        key = json.dumps(draft, sort_keys=True, ensure_ascii=False, default=str)
        entry = self._kept.pop(key, None)
        if entry is None:
            entry = {"merged": _merged(self.scene, draft), "rows": None}
        self._kept[key] = entry
        while len(self._kept) > ROOM_MERGES_KEPT:
            self._kept.pop(next(iter(self._kept)))
        return entry

    def merged(self, draft) -> dict:
        """The draft merged into the world, as `_merged` makes it."""
        return self._entry(draft)["merged"]

    def rows(self, draft) -> list:
        """The check's rows on the merged draft that the world does not
        hold: `room_layout_lint(merged, prev_scene=world)`."""
        entry = self._entry(draft)
        if entry["rows"] is None:
            from world.spatial import layout_row_key, room_layout_lint
            standing = self.standing()
            entry["rows"] = [row for row in room_layout_lint(entry["merged"])
                             if layout_row_key(row) not in standing]
        return entry["rows"]


#: Merges of the draft one design run keeps (`_Reading`), newest last: the
#: draft as it stands, the one before a trial change a pass may take back,
#: and the trial itself -- so a change taken back finds its merge still
#: there. A memory bound, not a behaviour: a merge not kept is made again.
ROOM_MERGES_KEPT = 3


def _merge_of(scene, draft, reading=None):
    return reading.merged(draft) if reading is not None else _merged(scene, draft)


def _merge_or_none(scene, draft, reading=None):
    """The draft merged into the world, or None when the merge cannot take
    it. A pass of code's own -- the far sides, the doorways, the packing --
    does nothing to such a draft, and the check names the merge's error to
    the designer, who can fix it (`_check`). Raised out of a pass, a draft
    the merge could not take ended the whole design run, and the beat lost
    every room the designer was building -- a doorway written as one object
    instead of a list of them, or a `parent_entity` written as an object
    (round two's review, 2026-10-09), where the run had always handed the
    error back and the designer redrafted."""
    try:
        return _merge_of(scene, draft, reading)
    except Exception:
        return None


def _layout_key(draft, merged) -> str:
    """The drafted rooms as the layout reads them in the merged world: each
    one's grid, its doorways, its exposure (an open side spans the wall),
    its site and its storey -- and what the draft removes. Two drafts with
    one key lay every room out alike: a fixture or a word moves no room
    (`_derive_far_bearings`, `_place_doorways`)."""
    from world.spatial import room_grid
    rooms = (merged or {}).get("rooms") or {}
    out = {}
    for rid in sorted(str(key) for key in (draft.get("rooms") or {})):
        room = rooms.get(rid)
        if not isinstance(room, dict):
            out[rid] = None
            continue
        anchors = room.get("anchors") if isinstance(room.get("anchors"), dict) else {}
        out[rid] = {"grid": room_grid(merged, rid).key(), "adjacent": room.get("adjacent"),
                    "exposure": room.get("exposure"), "site": room.get("site"),
                    "level": room.get("level"),
                    "doors": {aid: a for aid, a in anchors.items() if str(aid).startswith("door:")}}
    return json.dumps({"rooms": out, "remove_rooms": draft.get("remove_rooms"),
                       "remove_adjacent": draft.get("remove_adjacent")},
                      sort_keys=True, ensure_ascii=False, default=str)


def render_room(scene, room_id):
    """One room as a floor plan on the engine's grid, north at the top, and
    a legend of what the engine made of every fixture and doorway."""
    from world.spatial import anchor_cells, room_grid
    rooms = (scene or {}).get("rooms") or {}
    room = rooms.get(room_id)
    if not isinstance(room, dict):
        return {"refused": f"no room {room_id!r} in the draft or the world"}
    grid = room_grid(scene, room_id)
    marks, legend = {}, []
    held = {}   # (cell, height) -> the fixture already there
    letters = iter("ABCEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")
    for aid, placed in (anchor_cells(scene, room_id) or {}).items():
        cells = [tuple(c) for c in (placed.get("cells") or [])]
        if str(aid).startswith("door:"):
            mark = "D"
            to = str(aid)[5:]
            legend.append(f"D  doorway to {to} ({(rooms.get(to) or {}).get('name') or to})"
                          f" on the {placed.get('dir') or '?'} side at {cells[:1]}")
        else:
            mark = next(letters, "*")
            legend.append(
                f"{mark}  {aid}: {str(placed.get('desc') or '')[:80]} -- engine read "
                f"footprint {placed.get('footprint')}, height {placed.get('height')}, "
                f"facing {placed.get('dir')}, {len(cells)} cell(s)"
                + ("" if cells else " -- NOT PLACED"))
        height = placed.get("height")
        for cell in cells:
            other = held.get((cell, height))
            if other is not None and other != aid:
                # A collision at the same height: both things cannot stand
                # there. Drawn, never hidden by whichever came last.
                marks[cell] = "!"
                legend.append(f"!  {aid} and {other} both stand on {cell} at "
                              f"height {height}")
            else:
                marks.setdefault(cell, mark)
                held[(cell, height)] = aid
    lines = []
    for y in range(grid.d):
        lines.append("".join(marks.get((x, y)) or ("." if (x, y) in grid.cells else " ")
                             for x in range(grid.w)))
    return {
        "room": room_id,
        "name": room.get("name"),
        "grid": f"{grid.w} x {grid.d} paces, {grid.shape}; north at the top, east "
                "to the right; '.' is floor, blank is outside the shape, '!' is two "
                "fixtures at the same height on one cell",
        "map": lines,
        "legend": legend,
    }


def _inspect(scene, room_ids, whole=False):
    """Standing rooms drawn on the engine's grid. `whole` is the tool's
    reading: the room's stored record exactly as the world holds it, then
    the drawing. Without it (`surroundings`) a room is a short projection
    beside the drawing, its record travelling in the payload's `rooms`."""
    rooms = (scene or {}).get("rooms") or {}
    out = {}
    for rid in list(room_ids or [])[:6]:
        room = rooms.get(str(rid))
        if not isinstance(room, dict):
            out[str(rid)] = {"refused": "no such room"}
            continue
        view = render_room(scene, str(rid))
        if whole:
            out[str(rid)] = {"record": copy.deepcopy(room),
                             "map": view.get("map"), "legend": view.get("legend")}
            continue
        out[str(rid)] = {
            "name": room.get("name"), "desc": str(room.get("desc") or "")[:400],
            "size": room.get("size"), "extent": room.get("extent"),
            "shape": room.get("shape"), "parent_entity": room.get("parent_entity"),
            "adjacent": [{k: e.get(k) for k in ("to", "barrier", "dir", "distance")}
                         for e in room.get("adjacent") or [] if isinstance(e, dict)],
            "map": view.get("map"), "legend": view.get("legend"),
        }
    return out


def _check(scene, draft, owed, rows_out=None, settled=(), reading=None):
    """The layout check over the draft merged into the world. `rows_out`, a
    list, receives the check's raw rows for code; the model reads only the
    sentences. `settled` is the `(room, anchor)` pairs the design loop has
    settled (`_pack`): a wall's report never fits a fixture by moving one.
    `reading` is the design run's (`_Reading`), whose merge and world rows
    the check reads instead of making its own."""
    from world.spatial import layout_warning, room_layout_lint
    try:
        if reading is not None:
            merged = reading.merged(draft)
            rows = list(reading.rows(draft))
        else:
            merged = _merged(scene, draft)
            rows = room_layout_lint(merged, prev_scene=scene)
        ways = _ways_both_ways(draft)
        # The merge drops a way's direction when its two ends contradict each
        # other, which leaves the pair level -- and the bearing row the check
        # then holds about it is that contradiction's consequence, not a
        # second fact (`_embedding_rows`' rule), so it is not repeated.
        rows = [row for row in rows if not (
            row.get("kind") == "reciprocal_bearing_disagrees"
            and frozenset(row.get("rooms") or ()) in {frozenset(w[:2]) for w in ways})]
        errors = [_way_sentence(merged, *way) for way in ways] \
            + [layout_warning(row) for row in rows]
    except Exception as exc:
        return {"errors": [f"the draft could not be merged into the world: {exc}"]}
    if rows_out is not None:
        rows_out.extend(rows)
    drafted = set((draft.get("rooms") or {}))
    missing = [rid for rid in owed if rid not in drafted]
    unplaced, overlapping = [], []
    clashing = {}
    try:
        from world.spatial import anchor_cells
        for rid in drafted:
            held = {}
            for aid, placed in (anchor_cells(merged, rid) or {}).items():
                if str(aid).startswith("door:"):
                    continue
                if not placed.get("cells"):
                    unplaced.append(f"{rid}.{aid}")
                for cell in placed.get("cells") or []:
                    key = (tuple(cell), placed.get("height"))
                    if key in held and held[key] != aid:
                        overlapping.append(f"{rid}: {held[key]} and {aid} share "
                                           f"{tuple(cell)} at height {key[1]}")
                        clashing.setdefault(rid, set()).update((held[key], aid))
                    held.setdefault(key, aid)
    except Exception:
        pass
    overlapping = list(dict.fromkeys(overlapping))
    unjoined = _no_way_in(scene, draft, owed)
    out = {"errors": errors, "owed_not_drafted": missing,
           "fixtures_not_placed": unplaced, "fixtures_overlapping": overlapping,
           "clean": not (errors or missing or unplaced or overlapping or unjoined)}
    if unjoined:
        out["no_way_in"] = {
            "places": unjoined,
            "why": "a place the prose puts people in is reached from somewhere: join it "
                   "where it lies, building the way there if the world has none, or give "
                   "it a zone if no walk from here could reach it. Left joined to "
                   "nothing, the engine opens it onto the room the bodies stood in"}
    crowded = _crowded_walls(scene, draft, merged, rows, drafted, clashing, settled)
    if crowded:
        out["crowded_walls"] = crowded
    return out


def _ways_both_ways(draft):
    """`(a, b, way)` for every way the DRAFT writes from both of its rooms
    with the same direction up or down at both ends -- each room saying the
    other lies up, or both down. A way up from one room is a way down from
    the other, so the merge keeps neither direction ("dropped rather than
    guessed", `normalize_scene_bearings`), the way becomes level, and the
    check then asked for opposite bearings: one designer flipped the Gale
    house landing's stair between n and s for four steps over a direction it
    had written twice (the 2026-10-08 replay of chat 166, turn 22). Which end
    is right is the prose's, never code's -- there the landing's own end had
    it backwards -- so it is named, not resolved."""
    from world.spatial import normalize_vertical, opposite_vertical
    rooms = draft.get("rooms") or {}
    out = []
    for a in sorted(rooms):
        for edge in (rooms[a] or {}).get("adjacent") or () if isinstance(rooms[a], dict) else ():
            if not isinstance(edge, dict) or not edge.get("to"):
                continue
            b = str(edge["to"])
            if b <= a or not isinstance(rooms.get(b), dict):
                continue
            back = next((e for e in rooms[b].get("adjacent") or ()
                         if isinstance(e, dict) and str(e.get("to")) == a), None)
            mine = normalize_vertical(edge.get("vertical"))
            theirs = normalize_vertical((back or {}).get("vertical"))
            if mine and theirs and opposite_vertical(mine) != theirs:
                out.append((a, b, mine))
    return out


def _way_sentence(merged, a, b, way):
    rooms = (merged or {}).get("rooms") or {}
    name = lambda rid: (rooms.get(rid) or {}).get("name") or rid
    return (f"{name(a)!r} and {name(b)!r} each say the other lies {way}: a way up "
            f"from one room is a way down from the other, so the engine keeps "
            f"neither direction. Write the way once, on the place you are designing, "
            f"and its far end follows.")


def _no_way_in(scene, draft, owed):
    """The new places this draft owes that the DRAFT joins to nothing: no
    doorway but a wall on the place or pointing at it, not the inside of
    anything (`parent_entity`, whose way in is derived), and no `zone`
    saying it lies where no walk reaches. Read off the draft, not the merge:
    the merge heals an island by opening it onto the room the bodies stood
    in (`connect_orphan_new_rooms`), which is the engine's floor and the
    wrong street -- told a place joins the world where it lies, a designer
    drafted a harbour café joined to nothing, and the merge would have
    opened it onto the theatre's rehearsal room (2026-09-27)."""
    from world.spatial import normalize_barrier
    standing = (scene or {}).get("rooms") or {}
    drafted = draft.get("rooms") or {}

    def opens(edge):
        return isinstance(edge, dict) and normalize_barrier(edge.get("barrier")) != "wall"

    out = []
    for rid in owed or ():
        room = drafted.get(rid)
        if rid in standing or not isinstance(room, dict):
            continue
        if room.get("parent_entity") or room.get("zone"):
            continue
        if any(opens(e) and e.get("to") for e in room.get("adjacent") or ()):
            continue
        if any(opens(e) and str(e.get("to")) == rid
               for other, r in drafted.items() if other != rid and isinstance(r, dict)
               for e in r.get("adjacent") or ()):
            continue
        out.append(rid)
    return out


def _new_anchor_ids(scene, draft, rid, merged) -> list:
    """The fixtures the draft PLACES in `rid`, in the order they were
    drafted: every drafted anchor the world does not already hold where the
    draft leaves it -- a new one, or one the draft gives another wall, size,
    height or room. A fixture the world holds on the same cells at the same
    height is STANDING: an obstacle to the packer, never moved by it.

    By the cells, not by the id: a planned room's stub carries the plan's
    fixtures with a name and a desc and no wall at all, so the designer
    developing the room places each of them for the first time -- the inn's
    hearth, long table and barrel rack in chat 165's turn 3, all seven
    rerolls of it."""
    from world.spatial import anchor_cells
    room = (draft.get("rooms") or {}).get(rid)
    anchors = room.get("anchors") if isinstance(room, dict) else None
    if not isinstance(anchors, dict):
        return []
    world = (scene or {}).get("rooms") or {}
    before = anchor_cells(scene, rid) if isinstance(world.get(rid), dict) else {}
    after = anchor_cells(merged, rid)
    out = []
    for aid, anchor in anchors.items():
        if not isinstance(anchor, dict):
            continue
        was, now = before.get(aid), after.get(aid)
        if was is None or now is None or was["cells"] != now["cells"] \
                or was["height"] != now["height"]:
            out.append(aid)
    return out


def _crowded_walls(scene, draft, merged, rows, drafted, clashing=None, settled=()):
    """ONE line for each wall of a drafted room that cannot hold its fixtures
    at one height (`spatial_pack.pack_anchors`): the wall's length and which
    side of the extent that is, what each fixture against it takes at that
    height, which found no place along it, and where each of those would fit.
    A designer handed only "needs 7, has 5" widened the wrong side twice (the
    2026-09-27 yard: its west wall runs north-south, so it is the extent's
    `d`). A wall gets its line when the check's count calls it overfull this
    draft, or when a new fixture sharing a cell at its height (`clashing`)
    finds no free place on it; moving a fixture to another wall is the
    designer's call, never code's."""
    from world.spatial import pack_anchors
    out = []
    for rid in sorted(drafted):
        overfull = [(row.get("wall"), row.get("height")) for row in rows or ()
                    if row.get("kind") == "wall_overfull" and row.get("room") == rid]
        try:
            stuck = [aid for aid in _new_anchor_ids(scene, draft, rid, merged)
                     if aid in (clashing or {}).get(rid, ()) and (rid, aid) not in settled]
            out += pack_anchors(merged, rid, stuck, overfull=overfull)["full"]
        except Exception:
            continue
    return out


def _pin_shape(merged, rid, anchor):
    """What a place code wrote was found FOR: the room's grid and the
    fixture's wall, footprint, height and lane. Changed, the place no longer
    answers the question it answered (`_pack`)."""
    from world.spatial import anchor_geometry, normalize_bearing, room_grid
    geo = anchor_geometry(anchor)
    return (room_grid(merged, rid).key(), normalize_bearing(anchor.get("dir")),
            geo["footprint"], geo["height"], geo["lane"])


def _pack(scene, draft, placed_by_code, rooms=None, settle=False, reading=None):
    """CODE STANDS EACH NEW FIXTURE ALONG THE WALL THE MODEL CHOSE
    (`world/spatial_pack.py`, the owner's choice of 2026-10-08): a fixture
    the draft adds keeps its seeded place when that place is free at its
    height, and otherwise takes the nearest free place along its own wall --
    written into the draft as `offset` (or `cell`, for a corner or a fixture
    with no wall) ONCE, so a later fixture never moves an earlier one. The
    world's standing fixtures and every place the model wrote are obstacles,
    never moved. Returns what it placed, in words for the designer.

    `placed_by_code` is this run's record of every fixture SETTLED --
    `{(room, anchor): (field, value, shape)}`: each place code wrote, and,
    with `settle` (a pass whose plan the designer is about to be shown: a
    `draft_room` or `view_room` result), each new fixture that kept its
    seeded place (`field` None) -- because a fixture a plan has shown is
    where the designer believes it is, and is never moved for a later one. A
    fixture only a check has read is not settled: the prepared design a
    beat starts from was drawn for another run, and the low walk's doorstep,
    kept at its seed by the first look, would have barred the twenty-two
    pace drain drafted beside it (chat 166's turn 3). A settled
    place stands only for the fixture it was found for: redrafted onto
    another wall or at another size, or its room re-measured, the fixture is
    placed again (`_pin_shape`); given a place the designer wrote itself,
    that place wins and the record is dropped."""
    from world.spatial import pack_anchors
    drafted = draft.get("rooms") or {}
    wanted = [rid for rid in (rooms if rooms is not None else list(drafted))
              if isinstance(drafted.get(rid), dict)
              and isinstance(drafted[rid].get("anchors"), dict)]
    if not wanted:
        return []
    merged = _merge_or_none(scene, draft, reading)
    if merged is None:
        return []
    retaken = False
    settled = set()
    for (rid, aid), (field, value, shape) in list(placed_by_code.items()):
        if rid not in wanted or str(aid).startswith("edge:"):
            continue                        # a doorway's place is `_place_doorways`'
        anchor = drafted[rid]["anchors"].get(aid)
        if not isinstance(anchor, dict) or (field and anchor.get(field) != value):
            placed_by_code.pop((rid, aid))
            continue
        try:
            same = _pin_shape(merged, rid, anchor) == shape
        except Exception:
            same = True
        if same:
            settled.add((rid, aid))
            continue
        if field:
            drafted[rid]["anchors"][aid] = {k: v for k, v in anchor.items() if k != field}
            retaken = True
        placed_by_code.pop((rid, aid))
    if retaken:
        merged = _merge_or_none(scene, draft, reading)
        if merged is None:
            return []
    notes = []
    for rid in wanted:
        movable = [aid for aid in _new_anchor_ids(scene, draft, rid, merged)
                   if (rid, aid) not in settled]
        if not movable:
            continue
        try:
            result = pack_anchors(merged, rid, movable)
        except Exception:
            continue
        anchors = drafted[rid]["anchors"]
        for aid in result["kept"] if settle else ():
            try:
                placed_by_code[(rid, aid)] = (None, None,
                                              _pin_shape(merged, rid, anchors[aid]))
            except Exception:
                pass
        for aid, pin in result["pins"].items():
            (field, value), = pin.items()
            # A NEW record, never the model's own object: that one is the
            # transcript's record of what the model wrote.
            anchors[aid] = dict(anchors[aid], **pin)
            try:
                placed_by_code[(rid, aid)] = (field, value,
                                              _pin_shape(merged, rid, anchors[aid]))
            except Exception:
                placed_by_code[(rid, aid)] = (field, value, None)
            notes.append(f"{rid}: {aid}'s place was taken at its height, so the engine "
                         f"set its {field} to {value}" + (
                             " -- the same wall, the nearest free place along it"
                             if field == "offset" else " -- the nearest free cell"))
    return notes


def _edge_shape(merged, rid, edge):
    """What a doorway place code wrote was found FOR: the wall the edge
    names and the two rooms' grids (`_place_doorways`)."""
    from world.spatial import normalize_bearing, room_grid
    to = str(edge.get("to"))
    rooms = (merged or {}).get("rooms") or {}
    return (room_grid(merged, rid).key(), normalize_bearing(edge.get("dir")),
            room_grid(merged, to).key() if isinstance(rooms.get(to), dict) else None)


def _world_holds_doorway(scene, a, b) -> bool:
    """Whether the world already holds a doorway between `a` and `b`,
    declared from either side. Code never moves one -- not along its wall
    (`_place_doorways`), not to another wall (`_derive_far_bearings`) --
    whatever the draft re-mentions of it: changing settled geometry is the
    designer's, written from both sides (`_shield_standing_bearings`)."""
    return bool(_held_doorway_edges(scene, a, b))


def _held_doorway_edges(scene, a, b) -> list:
    """The world's own edges between `a` and `b`, from either side."""
    world = (scene or {}).get("rooms") or {}
    return [edge for x, y in ((str(a), str(b)), (str(b), str(a)))
            for edge in ((world.get(x) or {}).get("adjacent") or ())
            if isinstance(edge, dict) and str(edge.get("to")) == y]


#: THE OWNER'S, NOT YET ANSWERED (round two's review, 2026-10-09): whether code may
#: give a doorway the world already holds WITH NO BEARING its first wall,
#: when the designer writes it again from both rooms on walls that are not
#: opposites (chat 166's turn 26: the Gale house door, held bearingless since
#: turn 22, written `s` from the house and from its landing again). Off --
#: today's rule -- the far-side derivation never touches a doorway the world
#: holds, bearing or none (`_world_holds_doorway`), and the merge leaves it
#: as it was. On, it skips only a held doorway that carries a bearing from
#: either side, so a held bearingless one is derived like a new one -- and
#: taken back, like any derivation, when that lays one room onto another.
DERIVE_FAR_SIDE_OF_A_HELD_BEARINGLESS_DOORWAY = False


def _settled_for_the_far_side(scene, a, b) -> bool:
    """Whether the far-side derivation leaves the doorway between `a` and
    `b` as the world holds it (`_derive_far_bearings`): any doorway the
    world holds, or -- with `DERIVE_FAR_SIDE_OF_A_HELD_BEARINGLESS_DOORWAY`
    -- only one the world holds with a bearing."""
    from world.spatial import normalize_bearing
    held = _held_doorway_edges(scene, a, b)
    if not held or not DERIVE_FAR_SIDE_OF_A_HELD_BEARINGLESS_DOORWAY:
        return bool(held)
    return any(normalize_bearing(edge.get("dir")) for edge in held)


def _placed_by_the_designer(edge, code_wrote=None) -> bool:
    """Whether a doorway's place along its wall is the designer's own: an
    `offset` or a `cell` on the edge that code did not write. `code_wrote`
    is the `(field, value, shape)` `_place_doorways` recorded for this edge,
    if any."""
    from world.spatial import normalize_cell, normalize_offset
    if normalize_cell(edge.get("cell")) is not None:
        return True                     # code writes an offset, never a cell
    if normalize_offset(edge.get("offset")) is None:
        return False
    return not (code_wrote and code_wrote[0] == "offset"
                and edge.get("offset") == code_wrote[1])


def _place_doorways(scene, draft, placed_by_code, reading=None):
    """TWO DOORWAYS NEVER STAND ON ONE PLACE OF A WALL BY ACCIDENT. A doorway
    the draft writes with no place of the designer's own sits at a seeded
    cell of its wall, and two seeded onto the same cells were a check row the
    designer spent a step moving (chat 166's turn 26: the Gale house
    landing's door to the house and its stair to the low walk, one north
    wall). Code gives the later one the free place along its wall nearest
    where it stood (`spatial_pack.doorway_places`), written as the edge's
    `offset` ONCE; an `offset` or `cell` the designer wrote always wins, a
    doorway the world already holds is never moved, a whole open side holds
    any other opening, and a place that would lay one room onto another is
    not written. Recorded in `placed_by_code` under
    `edge:<to>` and taken back when the edge's wall or either room's extent
    changes. Returns what it placed, in words for the designer."""
    from world.spatial import doorway_places, normalize_cell, normalize_offset
    rooms = draft.get("rooms") or {}

    def edge_at(rid, to):
        for i, edge in enumerate((rooms.get(rid) or {}).get("adjacent") or ()):
            if isinstance(edge, dict) and str(edge.get("to")) == to:
                return i, edge
        return None, None

    merged = _merge_or_none(scene, draft, reading)
    if merged is None:
        return []
    for (rid, key), (field, value, shape) in list(placed_by_code.items()):
        if not str(key).startswith("edge:"):
            continue
        i, edge = edge_at(rid, str(key)[5:])
        if edge is None or edge.get(field) != value:
            placed_by_code.pop((rid, key))
            continue
        try:
            same = _edge_shape(merged, rid, edge) == shape
        except Exception:
            same = True
        if not same:
            rooms[rid]["adjacent"][i] = {k: v for k, v in edge.items() if k != field}
            placed_by_code.pop((rid, key))
    movable = [(rid, str(edge["to"])) for rid, room in rooms.items() if isinstance(room, dict)
               for edge in room.get("adjacent") or ()
               if isinstance(edge, dict) and edge.get("to") and edge.get("drop") is not True
               and normalize_offset(edge.get("offset")) is None
               and normalize_cell(edge.get("cell")) is None
               and not _world_holds_doorway(scene, rid, str(edge["to"]))]
    if not movable:
        return []
    merged = _merge_or_none(scene, draft, reading)
    if merged is None:
        return []
    try:
        places = doorway_places(merged, movable)
    except Exception:
        return []
    if not places:
        return []
    # TAKEN BACK ONCE, NOT AT EVERY CHECK: places the world refused are not
    # tried again until the draft's layout changes (`_layout_key`).
    tried = None
    if reading is not None:
        tried = ("doorways", tuple(sorted(places.items())), _layout_key(draft, merged))
        if tried in reading.withdrawn:
            return []
    before = _plane_rows(scene, draft, reading)
    applied = []
    for (rid, to), frac in places.items():
        i, edge = edge_at(rid, to)
        if edge is None:
            continue
        rooms[rid]["adjacent"][i] = dict(edge, offset=frac)
        applied.append((rid, to, i, edge))
    merged = None if _plane_rows(scene, draft, reading) - before \
        else _merge_or_none(scene, draft, reading)
    if merged is None:
        for rid, _to, i, edge in applied:
            rooms[rid]["adjacent"][i] = edge
        if tried is not None:
            reading.withdrawn.add(tried)
        return []
    notes = []
    for rid, to, i, _edge in applied:
        edge = rooms[rid]["adjacent"][i]
        try:
            shape = _edge_shape(merged, rid, edge)
        except Exception:
            shape = None
        placed_by_code[(rid, "edge:" + to)] = ("offset", edge["offset"], shape)
        notes.append(f"{rid}: its doorway to {to} stood on the same cells as another "
                     f"doorway of its wall, so the engine set that edge's offset to "
                     f"{edge['offset']} -- the same wall, the nearest free place")
    return notes


#: Check rows that say rooms land on one another when laid out by their
#: bearings: a far side's derived bearing that brings one is not written
#: (`_derive_far_bearings`).
_PLANE_ROWS = frozenset({"rooms_overlap_when_placed", "site_plan_overlap"})


def _plane_rows(scene, draft, reading=None) -> set:
    """The check's rows that lay a room onto another, as comparable keys."""
    from world.spatial import room_layout_lint
    try:
        rows = reading.rows(draft) if reading is not None \
            else room_layout_lint(_merged(scene, draft), prev_scene=scene)
    except Exception:
        return set()
    return {json.dumps(row, sort_keys=True, default=str) for row in rows
            if row.get("kind") in _PLANE_ROWS}


def _derive_far_bearings(scene, draft, owed, reading=None, placed_by_code=None):
    """THE FAR SIDE OF A DOORWAY FOLLOWS THE PLACE BEING DESIGNED. The card
    says a doorway is written on the place being designed and never again on
    the room it joins, because the engine derives the far side. When the draft
    writes it on both, on a level way, with bearings that are not opposites,
    the merge drops BOTH ("dropped rather than guessed",
    `spatial_orientation.normalize_scene_bearings`) and the doorway has no
    wall. So the far room's copy is set to the opposite of the owed place's
    own, and the designer is told. A way up or down keeps each floor's wall
    (the lint's rule), and a pair where both rooms or neither is owed is left
    as written.

    NEVER A DOORWAY THE WORLD ALREADY HOLDS (`_world_holds_doorway`). Re-bearing
    the far copy turns a one-sided re-declaration of a settled doorway into a
    matching two-sided one, which the merge's shield then lets through
    (`_shield_standing_bearings` refuses only the one-sided kind): a parlour's
    east door to the hall, drafted `s` from both rooms, became a south door
    on the parlour and a north one on the hall -- every heading, sight line
    and layout through it moved, even where the designer's own copy of the
    far side agreed with the world (round one's review, 2026-10-08). Settled
    geometry is the shield's to arbitrate. (Whether a doorway the world holds
    with no bearing at all may be given its first wall this way is the
    owner's: `DERIVE_FAR_SIDE_OF_A_HELD_BEARINGLESS_DOORWAY`, off.)

    NEVER A FAR COPY THE DESIGNER PLACED. An `offset` or a `cell` the
    designer wrote on the far room's copy is a place on THAT wall; turning
    the copy to another wall carried it there, so a doorway placed a fifth of
    the way along a house's east wall became one a fifth of the way along its
    north wall (round two's review, 2026-10-09). Such a pair is left as
    written, as `_place_doorways` leaves every place the designer wrote --
    and the merge keeps neither bearing, as it always did. An offset code
    wrote itself (`placed_by_code`) is no such place: it follows the wall.

    NOT WHERE IT LAYS ONE ROOM ONTO ANOTHER. The Gale house's door, written
    `s` from the house and from its landing in chat 166's turns 22 and 26,
    was merged bearingless; given its wall, the one-plane layout puts the
    landing -- up a stair from the low walk, though written on the walk's
    storey -- onto the walk, a row the designer cannot clear while the lint
    lays every storey on one plane. So a derivation that brings such a row is
    taken back, and the doorway stays as the merge leaves it -- ONCE: with
    the design run's `reading`, what was taken back is not tried again until
    the draft's layout changes (`_layout_key`), where it had cost two merges
    and four whole checks at every check of those two beats, about 0.6 s
    each on the 33-room town. Returns what it set.

    A draft the merge cannot take is left alone: the check names why
    (`_merge_or_none`)."""
    from world.spatial import normalize_bearing, normalize_vertical, opposite_bearing
    rooms = draft.get("rooms") or {}
    owed = {str(rid) for rid in owed or ()}
    placed_by_code = placed_by_code if placed_by_code is not None else {}
    changes = []
    for rid in sorted(owed):
        room = rooms.get(rid)
        if not isinstance(room, dict):
            continue
        for edge in room.get("adjacent") or ():
            if not isinstance(edge, dict) or not edge.get("to"):
                continue
            to = str(edge["to"])
            far = rooms.get(to)
            mine = normalize_bearing(edge.get("dir"))
            if to in owed or not isinstance(far, dict) or not mine \
                    or normalize_vertical(edge.get("vertical")) \
                    or _settled_for_the_far_side(scene, rid, to):
                continue
            edges = far.get("adjacent") or []
            for i, back in enumerate(edges):
                if not isinstance(back, dict) or str(back.get("to")) != rid:
                    continue
                theirs = normalize_bearing(back.get("dir"))
                want = opposite_bearing(mine)
                if theirs and want and theirs != want \
                        and not normalize_vertical(back.get("vertical")) \
                        and not _placed_by_the_designer(
                            back, placed_by_code.get((to, "edge:" + rid))):
                    changes.append((edges, i, back, dict(back, dir=want),
                                    f"{to}'s doorway to {rid} set to {want}, opposite the "
                                    f"{mine} that {rid} gives it: a doorway is written on "
                                    f"the place being designed, and its far side follows",
                                    (rid, to, mine, theirs)))
                break
    if not changes:
        return []
    merged = _merge_or_none(scene, draft, reading)
    if merged is None:
        return []
    tried = None
    if reading is not None:
        tried = ("far sides", tuple(change[-1] for change in changes),
                 _layout_key(draft, merged))
        if tried in reading.withdrawn:
            return []
    before = _plane_rows(scene, draft, reading)
    for edges, i, _old, new, _note, _pair in changes:
        edges[i] = new
    if _plane_rows(scene, draft, reading) - before:
        for edges, i, old, _new, _note, _pair in changes:
            edges[i] = old
        if tried is not None:
            reading.withdrawn.add(tried)
        return []
    return [note for _edges, _i, _old, _new, note, _pair in changes]


def _fit(value, limit):
    text = json.dumps(value, ensure_ascii=False, default=str)
    if len(text) <= limit:
        return value
    return {"truncated": text[:limit]}


def _fit_inspection(result, limit=ROOM_INSPECT_CHARS):
    """An `inspect_rooms` result fitted ROOM BY ROOM: whole records in the
    order asked while they fit, the first always -- its drawing dropped
    before its record is cut -- and the rest named under `not_shown`, to ask
    for in a later call. One raw prefix of the whole result cut a record
    mid-field and silently lost every room after it (review of the
    2026-10-08 landing: six whole records past 6,000 characters)."""
    def size(value):
        return len(json.dumps(value, ensure_ascii=False, default=str))
    shown, later = {}, []
    for rid, entry in (result or {}).items():
        if not shown:
            if size({rid: entry}) > limit and isinstance(entry, dict):
                entry = {k: v for k, v in entry.items()
                         if k not in ("map", "legend")}
            shown[rid] = entry if size({rid: entry}) <= limit else _fit(entry, limit)
        elif size(dict(shown, **{rid: entry})) <= limit:
            shown[rid] = entry
        else:
            later.append(rid)
    if later:
        shown["not_shown"] = {"rooms": later,
                              "why": "past this result's size; ask for these "
                                     "in a later call"}
    return shown


def _shown(transcript):
    """The transcript, newest kept whole, oldest cut first to fit."""
    shown, total = [], 0
    for entry in reversed(transcript):
        size = len(json.dumps(entry, ensure_ascii=False, default=str))
        if total + size > ROOM_TRANSCRIPT_CHARS and shown:
            shown.append({"step": entry["step"], "tool": entry["tool"],
                          "result": "(earlier result omitted)"})
            continue
        shown.append(entry)
        total += size
    return list(reversed(shown))


# ---- what code hands over before the first step ------------------------------

def _exit_targets(brief):
    """The room ids a planned room's brief names as exits (a list of edges
    from `planned_room_brief`, or a map of them)."""
    exits = (brief or {}).get("exits") if isinstance(brief, dict) else None
    if isinstance(exits, dict):
        exits = list(exits.values())
    return [str(e.get("to")) for e in exits or () if isinstance(e, dict) and e.get("to")]


def _surroundings(scene, payload, owed):
    """The standing rooms a place being designed joins or could join, most
    relevant first: the exits its plan names, the rooms with a doorway into
    it, the rooms the beat's bodies and things stand in, and their
    neighbours past anything but a wall. Rooms being designed are not
    surroundings. Capped at `ROOM_SURROUNDINGS`."""
    from world.spatial import effective_adjacent, normalize_barrier
    rooms = (scene or {}).get("rooms") or {}
    owed = {str(rid) for rid in owed or ()}
    order = []

    def add(rid):
        rid = str(rid or "")
        if rid and rid in rooms and rid not in owed and rid not in order:
            order.append(rid)

    develop = payload.get("develop") if isinstance(payload.get("develop"), dict) else {}
    for rid in sorted(owed):
        for to in _exit_targets(develop.get(rid)):
            add(to)
        for other, room in rooms.items():
            edges = room.get("adjacent") if isinstance(room, dict) else None
            for edge in edges or ():
                if isinstance(edge, dict) and str(edge.get("to")) == rid:
                    add(other)
    positions = payload.get("positions") if isinstance(payload.get("positions"), dict) else {}
    held = [str(v) for v in positions.values() if isinstance(v, str) and v in rooms]
    for rid in held:
        add(rid)
    for rid in list(dict.fromkeys(held)):
        for edge in effective_adjacent(scene, rid):
            if isinstance(edge, dict) and normalize_barrier(edge.get("barrier")) != "wall":
                add(edge.get("to"))
    return order[:ROOM_SURROUNDINGS]


def _bearings(scene):
    """`{(room, to): bearing}` for every declared edge of the scene."""
    from world.spatial import normalize_bearing
    out = {}
    for rid, room in ((scene or {}).get("rooms") or {}).items():
        edges = room.get("adjacent") if isinstance(room, dict) else None
        for edge in edges or ():
            if isinstance(edge, dict) and edge.get("to"):
                out[(str(rid), str(edge["to"]))] = normalize_bearing(edge.get("dir"))
    return out


def _taken_walls(scene, host):
    """The walls of `host` that already hold a doorway or a neighbour: its
    own edges' bearings, and the far side of every edge naming it. A wall
    edge counts -- the room behind a wall still stands on that side, which
    the layout check cannot see, because it lays out only what a body can
    pass through."""
    from world.spatial import normalize_bearing, opposite_bearing
    rooms = (scene or {}).get("rooms") or {}
    taken = set()
    for edge in (rooms.get(host) or {}).get("adjacent") or ():
        if isinstance(edge, dict) and normalize_bearing(edge.get("dir")):
            taken.add(normalize_bearing(edge.get("dir")))
    for rid, room in rooms.items():
        if rid == host or not isinstance(room, dict):
            continue
        for edge in room.get("adjacent") or ():
            if isinstance(edge, dict) and str(edge.get("to")) == host:
                back = opposite_bearing(normalize_bearing(edge.get("dir")))
                if back:
                    taken.add(back)
    return taken


def _trial_shapes(place):
    """The footprints a new place is tried at. An extent it already has is
    the only one; otherwise the square its size word gives it and the two
    longest shapes of that size -- a designer free to choose the proportion
    must find the doorway still fits whichever way it runs."""
    import math
    base = {k: v for k, v in (place or {}).items()
            if k in ("name", "size", "shape", "extent", "parts") and v}
    if base.get("extent"):
        return [base]
    floor = _floor_for_size(base.get("size"))
    if not floor:
        return [base]
    from world.spatial import normalize_extent
    most = floor[1]
    long_side = max(2, round(math.sqrt(most * 1.5)))
    long_side = normalize_extent({"w": long_side, "d": 2})["w"]
    short_side = max(2, most // long_side)
    shapes = [base]
    for w, d in ((long_side, short_side), (short_side, long_side)):
        if w != d:
            shapes.append(dict(base, extent={"w": w, "d": d}))
    return shapes


def _doorways_that_fit(scene, rid, place, hosts, deadline, draft=None, left=None,
                       named=()):
    """Where a NEW place's doorway can go: each free wall of each host,
    tried by laying the place there alone and asking the engine's own
    layout check. A wall is kept when the check holds no row the world does
    not, but about the place's own interior, and no bearing anywhere is lost
    (a doorway laid on a wall another doorway holds can drop both bearings,
    and the check then reads clean) -- so every wall offered is one the
    designer's own check (`_check`) passes, the place standing there alone.

    Without `draft`, the place is tried at every shape `_trial_shapes`
    gives it. With `draft`, it is tried as DRAFTED -- its own extent and
    fixtures, every other drafted room in place, and none of its drafted
    doorways -- which is what the check hands back when the place stopped
    fitting where its doorways put it.

    A TRY COSTS ONE ROOM, NOT A TOWN, WHERE THE CHECK'S OWN WALKS SAY SO. The
    check's walks of the scene are read ONCE a search (`layout_index`), and
    each shape is laid against them with nothing but the place added
    (`leaf_rows`), which answers exactly as the whole check would -- or says
    it cannot, and the whole check answers instead: when the place would
    start a walk of its own and re-lay its host's part of the world (its id
    sorts first, or the host is a room the walk could not place), or it is
    not a leaf. A wall that passes is put through the REAL merge, whose rules
    have the last word -- a doorway the merge strips (onto the inside of a
    body or a boat, whose way in is derived), or whose bearing it drops, is
    no fit -- and judged on the merged world the same way: by the walks
    where the merge changed nothing but the place, by the whole check
    otherwise. On chat 166's 33-room turn-22 checkpoint the old try -- a
    copy and a merge of the town and two whole checks -- cost about 0.19 s,
    so the 1.5 s search finished 10 of its 63 tries and offered 2 of the 12
    walls that fit. Taking every row naming the place for the whole of what
    it adds (round one of 2026-10-08) offered walls the check then refused:
    7 of chat 160 turn 13's 33, each a standing collision re-reported once a
    doorway onto a room the walk never placed re-laid its corridors.

    `hosts` is tried in order -- the caller puts the rooms the draft and the
    prose name first -- and fits on a room in `named` come first, then a
    straight wall before a corner. When the time runs out the rooms not yet
    tried go into `left` (a list), so the search says it stopped instead of
    reading as "nothing fits".

    Returns `[{"to", "dir", "their_wall"}]`, `dir` being the place's own
    wall -- the edge exactly as the place writes it."""
    from world.site_plan import room_site
    from world.spatial import (layout_index, layout_row_key, leaf_rows,
                               merge_scene_with_diff, opposite_bearing,
                               room_layout_lint)
    if draft is not None:
        alone = copy.deepcopy(draft)
        record = dict(alone["rooms"].get(rid) or {})
        record.pop("adjacent", None)
        alone["rooms"][rid] = record
        for other_id, other in alone["rooms"].items():
            if other_id != rid and isinstance(other, dict) and other.get("adjacent"):
                other["adjacent"] = [e for e in other["adjacent"] if not (
                    isinstance(e, dict) and str(e.get("to")) == rid)]
        base = _merged(scene, alone)
        drafted = dict((base.get("rooms") or {}).get(rid) or {})
        shapes = [None]
    else:
        # THE WORLD AS THE MERGE HOLDS IT. What the merge does to the world
        # itself -- deriving a room's site, stripping a doorway written onto
        # the inside of a body or a thing -- it does to every trial alike,
        # so every trial is judged against the world it merges into. Judged
        # against the world as stored, a bearing the merge drops on its own
        # was a bearing "lost" by every wall: chat 160's turn-2 world held a
        # doorway onto the lift car's inside, and the search offered no wall
        # anywhere for either place it was asked about.
        base = merge_scene_with_diff(scene or {}, {"rooms": {}})
        drafted = None
        shapes = _trial_shapes(place)
    rooms = base.get("rooms") or {}
    before = _bearings(base)
    index = layout_index(base)
    standing = []           # the world's rows as keys, read once, when first needed
    fits = []
    hosts = [h for h in dict.fromkeys(hosts or ()) if h in rooms and h != rid]

    def added(trial):
        """The whole check's rows on `trial` that the world does not hold,
        but those about the place's own interior: the designer's to arrange,
        saying nothing about where it stands."""
        if not standing:
            standing.append({layout_row_key(row) for row in room_layout_lint(base)})
        return [row for row in room_layout_lint(trial)
                if row.get("room") != rid and layout_row_key(row) not in standing[0]]

    def refused(trial, host):
        """`(refused, by_the_walks)`: the check's verdict on `trial`, from the
        walks when `leaf_rows` can give it, else from the whole check."""
        rows = leaf_rows(trial, rid, host, index)
        if rows is None:
            return bool(added(trial)), False
        return any(row.get("room") != rid for row in rows), True

    def lost(merged, host, mine):
        after = _bearings(merged)
        return after.get((rid, host)) != mine \
            or any(was and not after.get(key) for key, was in before.items())

    def merge(record):
        return merge_scene_with_diff(base, {"rooms": {rid: record}})

    for i, host in enumerate(hosts):
        # AN INSIDE HOLDS NO NEW DOORWAY: its way in is derived from the body
        # or thing around it, and the merge strips any edge written onto it
        # (the card's A ROOM PARENTED TO AN ENTITY). Its walls are not tried.
        if (rooms.get(host) or {}).get("parent_entity"):
            continue
        taken = _taken_walls(base, host)
        # A HOST ON A SITE PLAN (`world/site_plan`): the merge may stand the
        # place on that plan as well, and two rooms one plan places are where
        # it put them, never a collision (`spatial_lint._collision_rows`).
        # The screen lays the place out unmerged, with no site, so a wall it
        # refuses there is put to the merge before it is refused: judged
        # unmerged, a few walls the designer's check passes were lost (round
        # two's review, 2026-10-09: 2 of 1,482 on seeded towns with storeys,
        # 4 of 848 on the refit path). A site only ever spares a collision,
        # so a wall the screen passes stands either way.
        sited = bool(room_site(base, host))
        for wall in _WALLS_TRIED:
            if time.time() > deadline:
                if left is not None:
                    left.extend(hosts[i:])
                return _ordered_fits(fits, named)
            if wall in taken:
                continue
            mine = opposite_bearing(wall)
            edge = {"to": host, "barrier": "open", "dir": mine}
            records = [dict(drafted if drafted is not None else shape or {},
                            adjacent=[edge]) for shape in shapes]
            merges = {}

            def merged_trial(n):
                if n not in merges:
                    merges[n] = merge({"adjacent": [edge]} if drafted is not None
                                      else records[n])
                return merges[n]

            try:
                # Every shape laid against the check's walks first. Then ONE
                # real merge, whose rules on the doorway itself -- stripped,
                # or its bearing dropped -- do not depend on the shape; where
                # it changed any room but the place, the walks the screen read
                # are not the merged world's, and every shape is merged and
                # put to the whole check.
                ok, walked = True, True
                for n, record in enumerate(records):
                    no, by_walks = refused(dict(base, rooms=dict(rooms, **{rid: record})), host)
                    if no and sited:
                        trial = merged_trial(n)
                        no, by_walks = lost(trial, host, mine) or bool(added(trial)), False
                    walked = walked and by_walks
                    if no:
                        ok = False
                        break
                if ok:
                    merged = merged_trial(0)
                    if lost(merged, host, mine):
                        ok = False
                    elif walked and _only_the_place_changed(base, merged, rid):
                        ok = not refused(merged, host)[0]
                    else:
                        ok = not added(merged)
                        if ok and not _only_the_place_changed(base, merged, rid):
                            for n in range(1, len(records)):
                                other = merged_trial(n)
                                if lost(other, host, mine) or added(other):
                                    ok = False
                                    break
            except Exception:
                ok = False
            if ok:
                fits.append({"to": host, "dir": mine, "their_wall": wall})
    return _ordered_fits(fits, named)


def _only_the_place_changed(base, merged, rid) -> bool:
    """Whether the merge left every room but `rid`, and the passages the
    rooms' doorways read through, as `base` holds them: the walks of `base`
    are then the merged world's, but for the place."""
    was = (base or {}).get("rooms") or {}
    now = (merged or {}).get("rooms") or {}
    if set(was) - {rid} != set(now) - {rid}:
        return False
    if (base or {}).get("passages") != (merged or {}).get("passages"):
        return False
    return all(now[key] == room for key, room in was.items() if key != rid)


def _ordered_fits(fits, named=()):
    """The rooms the draft and the prose name first, then -- whichever room
    it is on -- a straight wall before a corner."""
    named = set(named or ())
    return sorted(fits, key=lambda f: (f["to"] not in named, len(f["their_wall"]) > 1))


def _named_in_prose(scene, prose, owed=()):
    """The standing rooms the prose names, by their name or their id, in the
    order it first names them -- matched as the engine's own names, the way
    `_owed_names` matches an owed place, never as words with a meaning. The
    landing in chat 166's turn 22 stood between the low walk and the Gale
    house, both named in the prose and neither among the six rooms the bodies'
    positions put in `surroundings`, so neither was tried."""
    import re
    import unicodedata

    def words(text):
        text = unicodedata.normalize("NFKC", str(text or "")).casefold()
        return re.findall(r"[^\W_]+", text)

    said = words(prose)
    if not said:
        return []
    flat = "".join(said)
    owed = {str(rid) for rid in owed or ()}
    found = {}
    for rid, room in ((scene or {}).get("rooms") or {}).items():
        if str(rid) in owed or not isinstance(room, dict):
            continue
        for name in (room.get("name"), str(rid).replace("_", " ")):
            tokens = words(name)
            if not tokens:
                continue
            if all(t.isascii() for t in tokens):
                runs = [i for i in range(len(said) - len(tokens) + 1)
                        if said[i:i + len(tokens)] == tokens]
                at = len("".join(said[:runs[0]])) if runs else -1
            else:
                # A script written without spaces is one run of letters.
                at = flat.find("".join(tokens))
            if at >= 0:
                found[str(rid)] = min(at, found.get(str(rid), at))
    return sorted(found, key=lambda rid: (found[rid], rid))


def _fold_name(text):
    """A place's name for comparison: accents off, case folded, letters and
    digits only -- so "Harbour Café" and "harbour cafe" are one name."""
    import unicodedata
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()
    return "".join(ch for ch in text if ch.isalnum())


def _owed_names(scene, payload, owed):
    """`{folded name: owed room id}` for the rooms the designer owes, named
    as the Director reserved them, the plan briefed them, or the scene
    holds them."""
    rooms = (scene or {}).get("rooms") or {}
    sources = [payload.get("reserved_places"), payload.get("develop")]
    out = {}
    for rid in owed or ():
        names = [rid] + [((src or {}).get(rid) or {}).get("name")
                         for src in sources if isinstance(src, dict)
                         and isinstance((src or {}).get(rid), dict)]
        names.append((rooms.get(rid) or {}).get("name") if isinstance(rooms.get(rid), dict) else None)
        for name in names:
            folded = _fold_name(name)
            if folded:
                out.setdefault(folded, rid)
    return out


def _undesigned_plan(room):
    """A planned room no beat has described yet: the plan's stub."""
    return isinstance(room, dict) and bool(room.get("planned")) \
        and not str(room.get("desc") or "").strip()


def _floor_for_size(size):
    """`[least, most]` square paces of floor the engine reads as this size
    word (`size_from_extent` takes the tier whose square is nearest in
    area; the largest tier has no ceiling but the extent clamp), or None
    for a word that is not a size."""
    import math
    from world.spatial import GRID_SIDE, ROOM_SIZES
    word = str(size or "").strip().casefold()
    if word not in ROOM_SIZES:
        return None
    i = ROOM_SIZES.index(word)
    least = 4 if i == 0 else math.ceil(((GRID_SIDE[ROOM_SIZES[i - 1]] + GRID_SIDE[word]) / 2.0) ** 2)
    most = 576 if i == len(ROOM_SIZES) - 1 else \
        math.ceil(((GRID_SIDE[word] + GRID_SIDE[ROOM_SIZES[i + 1]]) / 2.0) ** 2) - 1
    return [least, most]


def _groundwork(scene, payload, owed, record):
    """What the designer is handed before its first step: `surroundings`,
    the standing rooms around its places drawn on the engine's grid;
    `rooms`, when the payload carried the world's whole ledger, cut to the
    stored records of those rooms and of the owed rooms that already stand;
    and `placing`, for each place the Director invented, the floor area its
    size word covers and the doorways that fit."""
    t0 = time.time()
    out = {}
    try:
        around = _surroundings(scene, payload, owed)
    except Exception:
        around = []
    rooms = (scene or {}).get("rooms") or {}
    # A planned room nobody has entered is drawn for no one: it has no
    # design to look at, and shown empty it reads as work -- one run on the
    # lighthouse rail developed seven of them in its first step (81.7 s,
    # then the wall). It still stands in the doorway search: it takes space.
    drawn = [rid for rid in around if not _undesigned_plan(rooms.get(rid))]
    if drawn:
        out["surroundings"] = _inspect(scene, drawn)
    # THE RECORDS OF THE ROOMS IN QUESTION, NOT THE TOWN. The spatial slice
    # hands over every room the world holds, and the designer is building
    # one place. Measured on chat 166's 50 captured in-beat calls: the ledger
    # was 26.2k chars of a 75.3k payload and `inspect_rooms` was called 0
    # times in 49 steps; every room id a design wrote was already on
    # `world_index`, in `surroundings`, owed, or named by a plan's exits; and
    # of the 91 field values its drafts wrote, 65 are in the records kept
    # here, 25 are new, and the one found only in a room left out is `dark`,
    # a word of the engine's own light ladder. So the records kept are
    # exactly those: each drawn room's (its drawing leaves out the storey,
    # light, surface, exposure, region and the way and name of each doorway,
    # which the record holds) and each owed room's that already stands (a
    # plan's stub holds the plan's own measurements, which the merge keeps
    # whatever the draft says) -- 7.3k chars on average, against 26.2k.
    # Every other room stays on `world_index` (`elsewhere`: its name,
    # storey, exits and ways), and `inspect_rooms` hands any of them over
    # whole. An unentered stub is left out here as it is from the drawing,
    # for the same reason; its plan reaches the designer as `planned_rooms`.
    # The whole ledger is also what one discarded turn-4 step answered,
    # owing one room, by writing draft_room calls for twenty-seven rooms of
    # the town at once (15.6k output tokens, 153.5 s, the wall).
    ledger = payload.get("rooms")
    if isinstance(ledger, dict):
        wanted = set(drawn) | {str(rid) for rid in owed or ()}
        out["rooms"] = {rid: room for rid, room in ledger.items() if str(rid) in wanted}
    reserved = payload.get("reserved_places") if isinstance(payload.get("reserved_places"), dict) else {}
    placing = {}
    deadline = t0 + ROOM_PLACEMENT_SECONDS
    named = _named_in_prose(scene, payload.get("prose"), owed)
    hosts = list(dict.fromkeys(named + list(around)))
    untried = {}
    for rid, place in reserved.items():
        if rid in rooms:
            continue                        # standing: its doorways are in the world
        entry = {}
        floor = _floor_for_size((place or {}).get("size"))
        if floor:
            entry["size"] = str(place.get("size")).strip().casefold()
            entry["floor_square_paces"] = floor
        left = []
        try:
            entry["doorways_that_fit"] = _doorways_that_fit(
                scene, rid, place, hosts, deadline, left=left, named=named)
        except Exception:
            entry["doorways_that_fit"] = []
        if left:
            entry["not_tried"] = {"rooms": left, "why": _NOT_TRIED}
            untried[rid] = len(left)
        placing[rid] = entry
    if placing:
        out["placing"] = placing
    record["groundwork"] = {
        "surroundings": around, "drawn": drawn, "named": named,
        "doorways_that_fit": {rid: len(e.get("doorways_that_fit") or ()) for rid, e in placing.items()},
        "seconds": round(time.time() - t0, 3)}
    if untried:
        record["groundwork"]["rooms_not_tried"] = untried
    if "rooms" in out:
        record["groundwork"]["records"] = sorted(out["rooms"])
        record["groundwork"]["records_left_on_the_map"] = len(ledger) - len(out["rooms"])
    return out


#: What the designer is told when the doorway search stopped before trying
#: every room: an untried room may hold a doorway as well as any offered.
_NOT_TRIED = ("the engine's time for trying walls ran out before these rooms; "
              "a doorway may fit on them too, so the walls offered are not all "
              "the walls there are")

#: Check rows about where rooms stand relative to one another -- the kinds a
#: doorway in the wrong place produces.
_PLACEMENT_ROWS = frozenset({"rooms_overlap_when_placed", "reciprocal_bearing_disagrees",
                             "openings_overlap", "wall_overfull"})


def _misplaced(rows, rid, hosts):
    """Whether any check row says the new place `rid` stands where it
    cannot: laid over another room, a doorway whose two sides disagree, or
    its doorway crowding a neighbour's wall."""
    for row in rows or ():
        if row.get("kind") not in _PLACEMENT_ROWS:
            continue
        if rid in [str(r) for r in row.get("rooms") or ()] or str(row.get("via")) == rid:
            return True
        if f"door:{rid}" in [str(o) for o in row.get("openings") or ()]:
            return True
        if row.get("kind") == "wall_overfull" and row.get("room") in hosts:
            return True
    return False


def _refit(scene, draft, rows, places, hosts, named=(), left=None):
    """`{place: doorways that fit it as drafted}` for each new place the
    check says stands where it cannot -- the concrete way out of a
    contradiction a designer otherwise circles (the 2026-09-27 yard: five
    steps round a placement the barracks already held). The rooms the draft
    joins the place to are tried first, then the ones the prose names, then
    the surroundings; `left`, a dict, receives the rooms a search ran out of
    time before trying."""
    out = {}
    deadline = time.time() + ROOM_PLACEMENT_SECONDS
    standing = (scene or {}).get("rooms") or {}
    for rid in places:
        if rid not in (draft.get("rooms") or {}):
            continue
        own = [str(e.get("to")) for e in (draft["rooms"][rid].get("adjacent") or ())
               if isinstance(e, dict) and e.get("to") and str(e.get("to")) in standing]
        near = list(dict.fromkeys(own + list(named or ()) + list(hosts)))
        if not _misplaced(rows, rid, near):
            continue
        untried = []
        try:
            out[rid] = _doorways_that_fit(scene, rid, None, near, deadline, draft=draft,
                                          left=untried, named=own + list(named or ()))
        except Exception:
            continue
        if untried and left is not None:
            left[rid] = untried
    return out


# ---- what code does after every step -------------------------------------------

def _agree_sizes(scene, draft, reading=None):
    """Set each drafted room's size word to the one its extent measures --
    the extent the WORLD will hold, read off the merge. The engine derives a
    room's size from its extent (`size_from_extent`), so the word is only
    ever the extent's; a disagreement is a check row and a step spent
    correcting a label. A planned room keeps the plan's measurements
    whatever the draft says (`spatial_merge`), so its drafted extent is set
    back to the plan's and said so: measured off the draft instead, code
    wrote 'huge' for a 12x10 the merge never took while the designer wrote
    'large' for the 10x8 it did, four steps running (the stage, 2026-09-27).
    Returns what changed."""
    from world.spatial import normalize_extent, size_from_extent
    changed = []
    rooms = draft.get("rooms") or {}
    if not any(isinstance(r, dict) and (r.get("size") or r.get("extent")) for r in rooms.values()):
        return changed
    try:
        held_rooms = _merge_of(scene, draft, reading).get("rooms") or {}
    except Exception:
        return changed
    for rid, room in rooms.items():
        if not isinstance(room, dict):
            continue
        held = held_rooms.get(rid) if isinstance(held_rooms.get(rid), dict) else {}
        extent = normalize_extent(held.get("extent"))
        if not extent:
            continue
        mine = normalize_extent(room.get("extent"))
        if mine and mine != extent:
            room["extent"] = dict(extent)
            changed.append(f"{rid}: the plan's extent {extent['w']}x{extent['d']} "
                           f"stands; a planned room keeps the plan's measurements")
        if room.get("size"):
            measured = size_from_extent(extent)
            written = str(room["size"]).strip().casefold()
            if measured and written != measured:
                room["size"] = measured
                changed.append(f"{rid}: size set from {written!r} to {measured!r}, "
                               f"which its extent measures")
    return changed


def _record_text(scene, rid):
    """One room as the decision model reads it: its name, description,
    fixtures, ways out, and the words for its light and surfaces."""
    from world.spatial import effective_adjacent, normalize_barrier
    rooms = (scene or {}).get("rooms") or {}
    room = rooms.get(rid) if isinstance(rooms.get(rid), dict) else {}
    lines = [f"PLACE: {room.get('name') or rid}"]
    if room.get("desc"):
        lines.append(f"Description: {room['desc']}")
    fixtures = room.get("anchors") if isinstance(room.get("anchors"), dict) else {}
    if fixtures:
        lines.append("Fixtures:")
        for aid, anchor in fixtures.items():
            desc = anchor.get("desc") if isinstance(anchor, dict) else ""
            lines.append(f"- {aid}: {desc}" if desc else f"- {aid}")
    else:
        lines.append("Fixtures: none")
    ways = []
    for edge in effective_adjacent(scene, rid):
        if not isinstance(edge, dict) or not edge.get("to"):
            continue
        to = str(edge["to"])
        what = edge.get("name") or normalize_barrier(edge.get("barrier"))
        side = f", {edge['dir']} wall" if edge.get("dir") else ""
        ways.append(f"- to {(rooms.get(to) or {}).get('name') or to}: {what}{side}")
    if ways:
        lines += ["Ways out:"] + ways
    for key in ("light", "surface", "exposure", "quiet"):
        if room.get(key):
            lines.append(f"{key.capitalize()}: {room[key]}")
    return "\n".join(lines)


def _finished(prose, scene, draft, owed, language, record, reading=None):
    """`(finished, notes)`: the decision model's reading of whether every
    owed room holds what the prose puts in it -- a part of the place the
    record never mentions, or a feature someone is placed at that is not
    one of its fixtures. Asked only of drafts the check passes, with a
    description for every owed room. Fails toward the model: unanswered,
    the design is not finished and the loop goes on."""
    from llm import decisions
    from llm.prompts import prose_contract_text
    try:
        if not decisions.configured():
            return False, []
        texts = {key: prose_contract_text(key, language) for key in _DONE_QUESTIONS}
    except Exception:
        return False, []
    merged = _merge_or_none(scene, draft, reading)
    if merged is None:
        return False, []
    rooms = merged.get("rooms") or {}
    if not owed or any(not str((rooms.get(rid) or {}).get("desc") or "").strip() for rid in owed):
        return False, []
    asked, notes = {}, []
    t0 = time.time()
    for rid in owed:
        state = "PASSAGE:\n" + prose + "\n\n" + _record_text(merged, rid)
        try:
            got = decisions.decide(state, {key: {"type": "noul", "instructions": text}
                                           for key, text in texts.items()})
        except Exception as exc:
            record.setdefault("jev", []).append({"failed": str(exc)[:200]})
            return False, []
        answers = {key: round(decisions.probability(got.get(key)), 3) for key in texts}
        asked[rid] = answers
        name = (rooms.get(rid) or {}).get("name") or rid
        if answers["room_done_missing"] >= ROOM_DONE_BARS["room_done_missing"]:
            notes.append(f"the prose may mention a part of {name} that its record "
                         f"does not mention anywhere")
        if answers["room_done_unlisted"] >= ROOM_DONE_BARS["room_done_unlisted"]:
            notes.append(f"the prose may place someone at a feature of {name} "
                         f"that is not one of its fixtures")
    record.setdefault("jev", []).append({"answers": asked, "finished": not notes,
                                         "seconds": round(time.time() - t0, 3)})
    return not notes, notes


def design_rooms(ctx, scene, payload, sheet, owed, call, record=None, seed=None,
                 seed_check=None):
    """Run the designer. `payload` is its standing input (prose, plans,
    reserved places, the spatial slice); `owed` the room ids it must draft;
    `call(system, payload)` one model step; `seed` designs that start in the
    draft, and `seed_check` a check the seed already failed elsewhere -- the
    install's (`_install_test`). Returns the draft as
    `{rooms, remove_rooms, remove_adjacent}` and fills `record`."""
    record = record if record is not None else {}
    # A PREPARED design (`schedule_room_predevelopment`) starts in the draft:
    # the designer adapts it to this beat's prose instead of building it.
    draft = {"rooms": copy.deepcopy(dict(seed or {})), "remove_rooms": [],
             "remove_adjacent": []}
    if seed:
        record["prepared"] = sorted(seed)
    prose = str(payload.get("prose") or "").strip()
    language = getattr(ctx, "language", None)
    payload = dict(payload, **_groundwork(scene, payload, owed, record))
    transcript = []
    started = time.time()
    stopped = "steps"
    step = 0

    standing = (scene or {}).get("rooms") or {}
    new_places = [rid for rid in owed if rid not in standing]
    hosts = list((record.get("groundwork") or {}).get("surroundings") or [])
    named = list((record.get("groundwork") or {}).get("named") or [])
    owed_names = _owed_names(scene, payload, owed)
    # The places code wrote for new fixtures this run (`_pack`).
    placed_by_code = {}
    # The world's rows and the draft's merge, shared by every pass of every
    # check of this run (`_Reading`).
    reading = _Reading(scene)

    def packed(rooms=None, settle=False):
        notes = _pack(scene, draft, placed_by_code, rooms, settle, reading=reading)
        if notes:
            record["packed"] = record.get("packed", 0) + len(notes)
        return notes

    def checked():
        # Every check sets the size words first: the extent decides a
        # room's size, so a disagreement is only ever the label's.
        agreed = _agree_sizes(scene, draft, reading)
        derived = _derive_far_bearings(scene, draft, owed, reading, placed_by_code)
        if derived:
            record["bearings_derived"] = record.get("bearings_derived", 0) + len(derived)
        doorways = _place_doorways(scene, draft, placed_by_code, reading)
        if doorways:
            record["doorways_placed"] = record.get("doorways_placed", 0) + len(doorways)
        placed = packed() + doorways
        rows = []
        result = _check(scene, draft, owed, rows_out=rows, settled={
            key for key in placed_by_code if not str(key[1]).startswith("edge:")},
            reading=reading)
        if agreed:
            result = dict(result, sizes_agreed=agreed)
        if derived:
            result = dict(result, bearings_derived=derived)
        if placed:
            result = dict(result, placed_by_the_engine=placed)
        # A new place that stands where it cannot gets the walls where it
        # would stand, as drafted -- the way out, not only the problem.
        untried = {}
        refit = _refit(scene, draft, rows, new_places, hosts, named, untried) if rows else {}
        if refit:
            result = dict(result, doorways_that_fit=refit)
            record["refits"] = record.get("refits", 0) + 1
        if untried:
            result = dict(result, doorways_not_tried={
                rid: {"rooms": left, "why": _NOT_TRIED} for rid, left in untried.items()})
        return result

    # A PREPARED design may already be the answer: checked and read against
    # this beat's prose before any model step is spent on it.
    #
    # When it is not, WHAT THAT FIRST LOOK FOUND IS THE FIRST THING THE
    # DESIGNER READS -- the check's problems, or what the prose puts in the
    # room that its record does not hold -- instead of being thrown away and
    # found again a step later. Measured on chat 166: every seeded design
    # was judged unfinished on that first look, and seeded runs averaged 5.8
    # steps against 3.4 for unseeded ones (7 and 6 against 3 on the one
    # matched pair). A design whose check failed between turns is kept as a
    # seed too (`schedule_room_predevelopment`), and its check arrives here --
    # with no prose as well, when the job between turns takes up its own
    # unclean design again (`PREDEVELOP_CONTINUATIONS`).
    #
    # A SEED THE INSTALL REFUSED ARRIVES WITH THE REFUSAL (`seed_check`).
    # Drafted beside the rooms that will stand, a layout refusal shows up in
    # this look as well; the state schema's does not -- no layout check
    # reads it -- and a clean look would leave the designer nothing to fix.
    if seed:
        last_check = checked()
        if seed_check and last_check.get("clean"):
            last_check = dict(seed_check, clean=False)
        if last_check.get("clean") and prose:
            finished, notes = _finished(prose, scene, draft, owed, language, record,
                                        reading)
            if finished:
                record.update(steps=0, calls=0, stopped="complete",
                              seconds=round(time.time() - started, 3),
                              final_check=_check(scene, draft, owed, reading=reading))
                return draft
            if notes:
                record["still_missing_said"] = 0
                transcript.append({"step": 0, "tool": "complete", "by": "engine",
                                   "args": {}, "result": {
                                       "finished": False, "still_missing": notes,
                                       "if_not": "if the record already holds it, submit; "
                                                 "where a person stands is never written "
                                                 "into a room's text"}})
        elif not last_check.get("clean"):
            transcript.append({"step": 0, "tool": "check", "by": "engine", "args": {},
                               "result": _fit(last_check, ROOM_RESULT_CHARS)})
    last_check = None
    for step in range(1, MAX_ROOM_STEPS + 1):
        if time.time() - started > MAX_ROOM_SECONDS:
            stopped = "wall"
            break
        answer = call(sheet, dict(payload, tools=ROOM_TOOLS, draft=draft,
                                  transcript=_shown(transcript), step=step,
                                  steps_left=MAX_ROOM_STEPS - step)) or {}
        calls = [c for c in (answer.get("calls") or []) if isinstance(c, dict)]
        submitted = False
        touched = False     # the draft changed during this step
        unchecked = False   # ...and has not been checked since
        for item in calls[:MAX_ROOM_CALLS_PER_STEP]:
            tool, args = str(item.get("tool") or ""), item.get("args") or {}
            args = args if isinstance(args, dict) else {}
            if tool == "draft_room":
                rid = str(args.get("room_id") or "").strip()
                if not rid or not isinstance(args.get("room"), dict):
                    result = {"refused": "draft_room needs room_id and a room object"}
                else:
                    # A NEW id carrying an owed place's name IS that place:
                    # the ids given are fixed. Drafted as `harbour_cafe`
                    # against the reserved `harbour_caf`, the café was built
                    # twice and the stray joined to nothing (2026-09-27).
                    renamed = None
                    if rid not in standing and rid not in owed and rid not in draft["rooms"]:
                        same = owed_names.get(_fold_name(args["room"].get("name"))) \
                            or owed_names.get(_fold_name(rid))
                        if same:
                            renamed, rid = rid, same
                    draft["rooms"][rid] = _merge_room(draft["rooms"].get(rid), args["room"])
                    touched = unchecked = True
                    # Each new fixture stands along its own wall before the
                    # plan is drawn, so the plan shows where it will stand.
                    placed = packed([rid], settle=True)
                    # The plan comes back with every draft: seeing the room is
                    # part of drafting it, not a step spent asking to look.
                    try:
                        plan = render_room(reading.merged(draft), rid)
                    except Exception as exc:
                        plan = {"refused": f"could not draw the room: {exc}"}
                    result = {"drafted": rid, "fields": sorted(draft["rooms"][rid]),
                              "plan": plan}
                    if placed:
                        result["placed_by_the_engine"] = placed
                    if renamed:
                        result["drafted_as"] = (f"{renamed!r} is the place you owe as {rid!r}: "
                                                f"the id you were given is fixed")
            elif tool == "view_room":
                packed([str(args.get("room_id") or "")], settle=True)
                try:
                    result = render_room(reading.merged(draft), str(args.get("room_id") or ""))
                except Exception as exc:
                    result = {"refused": f"could not draw the room: {exc}"}
            elif tool == "inspect_rooms":
                # A draft the merge cannot take is the designer's to fix, never
                # the end of the run: the check says why (`_merge_or_none`).
                try:
                    result = _fit_inspection(_inspect(
                        reading.merged(draft), args.get("room_ids") or [],
                        whole=True))
                except Exception as exc:
                    result = {"refused": f"the draft could not be merged into the "
                                         f"world: {exc}"}
            elif tool == "check":
                result = last_check = checked()
                unchecked = False
            elif tool == "submit":
                result = last_check = checked()
                unchecked = False
                if result.get("clean") or step >= MAX_ROOM_STEPS:
                    submitted = True
                else:
                    # A design is finished when it is right. The problems
                    # come back instead, and the loop goes on.
                    result = dict(result, refused="not submitted: fix these first")
            elif tool in ("remove_rooms", "remove_adjacent") and isinstance(args.get("items"), list):
                draft[tool].extend(args["items"])
                touched = unchecked = True
                result = {"recorded": tool}
            else:
                result = {"refused": f"unknown tool {tool!r}"}
            transcript.append({"step": step, "tool": tool, "args": args,
                               "result": result if tool == "inspect_rooms"
                               else _fit(result, ROOM_RESULT_CHARS)})
        # A call past the step's cap was never run, and a designer not told
        # so believes it drafted the room (2026-09-27: the stage beat's 7th
        # and 8th draft_room calls, the corridor and the auditorium).
        if len(calls) > MAX_ROOM_CALLS_PER_STEP:
            transcript.append({"step": step, "tool": "calls", "by": "engine", "args": {},
                               "result": {"not_run": [
                                   {"tool": str(c.get("tool") or ""),
                                    "room_id": (c.get("args") or {}).get("room_id")
                                    if isinstance(c.get("args"), dict) else None}
                                   for c in calls[MAX_ROOM_CALLS_PER_STEP:]],
                                   "why": f"a step runs its first {MAX_ROOM_CALLS_PER_STEP} "
                                          f"calls; these were not run"}})
        # THE CHECK RUNS ITSELF after a step that changed the draft: a
        # contradiction is named the step it is made, never at a submit
        # three steps later.
        if unchecked:
            last_check = checked()
            record["auto_checks"] = record.get("auto_checks", 0) + 1
            transcript.append({"step": step, "tool": "check", "by": "engine", "args": {},
                               "result": _fit(last_check, ROOM_RESULT_CHARS)})
        refused = any((entry.get("result") or {}).get("refused", "").startswith("not submitted")
                      for entry in transcript if entry["step"] == step
                      and isinstance(entry.get("result"), dict))
        if submitted:
            stopped = "submitted"
            break
        if not calls:
            stopped = "submitted" if answer.get("done") else "no_calls"
            break
        clean = bool(last_check and last_check.get("clean"))
        # FINISHED IS THE DECISION MODEL'S CALL once the check is clean: no
        # step is spent saying so. Unfinished, what is missing comes back.
        if touched and clean and prose:
            finished, notes = _finished(prose, scene, draft, owed, language, record,
                                        reading)
            if finished:
                stopped = "complete"
                break
            # SAID ONCE. The reader can be wrong, and a designer told the
            # same thing every step chases it: the 2026-09-27 yard wrote
            # "this is where Luca stands" into a fixture to satisfy a
            # reading the grave already answered.
            if notes and record.get("still_missing_said") is None:
                record["still_missing_said"] = step
                transcript.append({"step": step, "tool": "complete", "by": "engine",
                                   "args": {}, "result": {
                                       "finished": False, "still_missing": notes,
                                       "if_not": "if the record already holds it, submit; "
                                                 "where a person stands is never written "
                                                 "into a room's text"}})
        if answer.get("done") and not refused:
            if last_check is None:
                last_check = checked()
                clean = bool(last_check.get("clean"))
            if clean:
                stopped = "submitted"
                break
            transcript.append({"step": step, "tool": "done", "by": "engine", "args": {},
                               "result": dict(last_check, refused="not finished: the "
                                              "check is not clean")})
    final = _check(scene, draft, owed, reading=reading)
    record.update(steps=step, calls=sum(1 for entry in transcript if not entry.get("by")),
                  stopped=stopped, seconds=round(time.time() - started, 3),
                  final_check=final)
    return draft


# ---- between turns: build the planned rooms the player can see into or is
# heading for, so they stand before anyone arrives -------------------------

#: The world key holding designs made before anyone arrived, by room id.
#: A reconstructible cache: lost, the in-turn designer simply does the work.
#: ONE ROW FOR THE CHAT, not one per frame: a room id is the registry's,
#: the same room in every frame of an era, so a design made where one frame
#: saw the stub is the design another frame builds when its own body comes
#: near it (`_wanted_elsewhere`).
PREPARED_KEY = "prose_contract_prepared_rooms"
#: The design job's key: the present's, and `<key>:<frame id>` for any
#: other frame (`predevelop_job_key`) -- each frame's commits design the
#: rooms ahead of the bodies in that frame's scene, and a run reads one scene.
PREDEVELOP_JOB_KEY = "room_predevelopment"
#: Planned rooms designed per RUN of one frame's job at most, and a run is
#: one commit's -- or one for every run of commits that landed while the
#: last run was designing (`core.jobs.submit_latest`). Named per the owner's
#: ask-before-limiting rule: each is a full designer run on the room role
#: (chat 166, OpenRouter plain GLM 5.2: 131 calls, 1.76M prompt and 51k
#: response tokens and 964 s for 25 designs -- about five calls, 70k prompt
#: tokens and 40 s a design). FOUR because that is the most rooms in view or
#: ahead the Brackwater run ever stood beside (`rooms_in_reach` over its 30
#: pre-beat checkpoints: the low walk's four open neighbours at turns 4-5,
#: every other beat three or fewer), so arriving anywhere in that town builds
#: every room in sight in one pass. A brief is designed ONCE, so this bounds a
#: burst, not the run: those 30 beats hold 10 distinct stubs in view or
#: ahead, where the old neighbour set (closed doors included) held 16 and the
#: old job made 25 designs.
#:
#: PER FRAME, NOT FOR THE CHAT, since the rooms ahead of every cast member
#: are built and not only the player's (owner, 2026-10-08: "Rooms in view
#: of, or ahead of, ANY cast member get built, bubble travellers included").
#: A causality bubble's beat is a committed turn of its own, so a bound per
#: committed turn is already a bound per frame; one shared bound would make
#: a bubble traveller's rooms wait behind every beat the player's view had
#: work, which is a freeze wearing a number -- the thing the owner ruled
#: out for bubbles (`offscreen_beat.OFFSCREEN_BEATS_ARE_UNCAPPED`). Within a
#: frame the players' rooms come first, then the cast's, so the bound never
#: costs the player a room it spends on a bystander's.
PREDEVELOP_PER_TURN = 4
#: How many times the job takes up its own design of a room still in reach
#: again, from where it stopped -- seeded with itself, the check's problems
#: the first thing the designer reads -- before leaving it as a seed for the
#: beat that enters the room. Two kinds of design are taken up: one whose
#: own final check was not clean, and a clean one the install refuses
#: (`_install_test`: a neighbour built since, or a design beside it that
#: takes the same wall). Named per ask-before-limiting; 0 is "designed once,
#: an unclean design waits for the beat" as it stood. ONE, on the turn-26
#: replay of chat 166 (2026-10-08): the Gale house, in view through an open
#: door for three beats, reached the 8-step cap with one fixture overlap
#: left (a chair and the bed on one cell) and so was not built in; a second
#: run of the same brief converged at step 6, five steps of it spent moving
#: one table off one bench. A fixture overlap is what a design spends its
#: last steps on, and a continuation starts there. Each costs at most one
#: more designer run per brief.
PREDEVELOP_CONTINUATIONS = 1
#: THE BACK-OFF OF A ROOM WHOSE DESIGN RUN FAILED, in beats (the chat's
#: turns). A run that raises -- `_agent_json` finding nothing that validates
#: after its repair and candidates, a transcript grown past the model's
#: context, a provider that is down -- is filed (`failed`, `failed_turn`),
#: and the room is not designed again until this many beats have passed,
#: doubling for each further failure in a row (`predevelop_retry_beats`),
#: never past `PREDEVELOP_RETRY_BEATS_CAP`; a run that finishes clears it.
#: Unfiled, a failing room was designed again from nothing on every commit:
#: a designer that raised at its third step made 12 calls over 4 commits and
#: filed nothing (review of the 2026-10-08 landing). The numbers are the
#: Writers' Room's own back-off on an unchanged question
#: (`story.room_frontier.FILL_RETRY_BEATS` and `_CAP`, owner's ruling
#: 2026-10-08), so a provider down for a beat costs two beats' wait and a
#: room that can never be designed costs one run in sixteen beats. Named per
#: ask-before-limiting.
PREDEVELOP_RETRY_BEATS = 2
PREDEVELOP_RETRY_BEATS_CAP = 16
#: The host's switch for building rooms in view between turns. ON unless set
#: to `0`/`off`/`false` -- the owner's ruling of 2026-10-08: "Between turns,
#: each planned room the player can see into or is heading for is designed
#: once and put into the world, so it exists before they walk in and the view
#: through a doorway has something real in it. This replaces the hidden-draft
#: predevelopment and is on by default." What it replaced was off by default
#: since that morning, on the Brackwater run's measurement (chat 166, 30
#: beats): 131 designer calls for 25 hidden designs, at least 19 of which
#: never reached a beat, because a design was read only when a beat ENTERED
#: its room and was then judged unfinished against that beat's prose. Built
#: rooms are read by the beat that sees them, from its first stage on.
PREDEVELOP_SETTING = "prose_contract_room_predevelopment"


def predevelopment_enabled() -> bool:
    """Whether rooms in view are built between turns: on unless the host
    turned it off (`PREDEVELOP_SETTING`)."""
    from core.db import get_setting
    try:
        raw = get_setting(PREDEVELOP_SETTING)
    except Exception:
        return True
    return str(raw or "").strip().casefold() not in ("0", "off", "false")


def _brief_signature(brief):
    """What a prepared design was made FROM, as a short stable fingerprint:
    the plan's brief for the room. The same brief is the same job."""
    import hashlib
    text = json.dumps(brief, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def predevelop_retry_beats(failed):
    """Beats a room waits after `failed` design runs in a row raised:
    `PREDEVELOP_RETRY_BEATS` after the first, doubling for each further one,
    never past `PREDEVELOP_RETRY_BEATS_CAP`."""
    failed = max(1, int(failed or 0))
    return min(PREDEVELOP_RETRY_BEATS_CAP,
               PREDEVELOP_RETRY_BEATS * (2 ** (failed - 1)))


def _backing_off(entry, turn_idx):
    """Whether the room a cache entry files still waits on its last design
    run's failure: fewer than `predevelop_retry_beats` beats since it. A
    story rewound past the failure waits on nothing."""
    from core.jobs import story_rewound_past
    if not isinstance(entry, dict) or not int(entry.get("failed") or 0):
        return False
    at = entry.get("failed_turn")
    if at is None or turn_idx is None or story_rewound_past(at, turn_idx):
        return False
    return int(turn_idx) - int(at) < predevelop_retry_beats(entry.get("failed"))


def _heading(scene, body):
    """`(next_leg, destination)` of the walk `body` is on: the scene's own
    standing approach record (`approach`, keyed by mover; the older
    scene-global `{who, to_room}` shape is read as the movement code reads
    it) and the next room on the passable route there. `(None, None)` when
    the body is on no walk."""
    from world.spatial import passable_route_next_step, room_of
    pending = (scene or {}).get("approach") or {}
    if isinstance(pending, dict) and "who" in pending:
        pending = ({pending["who"]: {"to_room": pending.get("to_room")}}
                   if pending.get("who") else {})
    leg = pending.get(body) if isinstance(pending, dict) else None
    destination = (str(leg.get("to_room") or "").strip()
                   if isinstance(leg, dict) else "")
    here = room_of(scene, body)
    if not destination or not here or destination == here:
        return None, None
    try:
        step = passable_route_next_step(scene, here, destination)
    except Exception:
        step = None
    return (str(step) if step else None), destination


def rooms_in_reach(scene, body):
    """The rooms `body` can see into or is heading for, in the order it
    meets them (`structure.rooms_in_view_or_ahead`): the set the world
    builds before anyone arrives. Every such room, stub or not --
    `planned_room_brief` keeps the stubs."""
    from world.spatial import room_of
    from world.structure import rooms_in_view_or_ahead
    here = room_of(scene, body) if body else None
    if not here:
        return []
    next_leg, destination = _heading(scene, body)
    return rooms_in_view_or_ahead(scene, here, next_leg=next_leg,
                                  bound_for=destination)


def actors_ahead(cid, frame_id, scene, cast_rows=None):
    """`(players, cast)`: the bodies in this frame's scene whose rooms in
    view or ahead the world builds before anyone arrives, by name, in the
    order their rooms are wanted -- the players first (the primary player,
    then any other persona stationed in the frame), then every cast member
    the scene places, in cast order. A body the scene does not place has no
    reach and is left out.

    ANY ACTOR, NOT ONLY THE PLAYER (owner, 2026-10-08: "Rooms in view of, or
    ahead of, ANY cast member get built, bubble travellers included, not just
    the player's" -- heavy plans for when the actors near them). A live
    causality bubble's scene places no player by construction
    (`spatial_frames.is_bubble_frame`), so its actors are its travellers, and
    its own commits design their rooms. `cast_rows` defaults to the frame's
    active cast -- the rows its beats run on (`story.scene.active_cast`)."""
    from agents.common import _present_cast_bodies
    from story.scene import active_cast
    from world.spatial import room_of
    from world.spatial_frames import _all_party_names

    players = []
    for name in _all_party_names(cid, frame_id) or ():
        name = str(name or "")
        if name and name not in players and room_of(scene, name):
            players.append(name)
    rows = active_cast(cid, frame_id) if cast_rows is None else cast_rows
    taken = {name.casefold() for name in players}
    cast = []
    for body in _present_cast_bodies(scene, rows) or ():
        name = str(body.get("name") or "")
        if name and name.casefold() not in taken:
            taken.add(name.casefold())
            cast.append(name)
    return players, cast


def rooms_to_build(cid, scene, bodies):
    """The rooms the world builds before `bodies` arrive, in the order they
    are wanted: for each body in turn, `rooms_in_reach` -- what it can see
    into or is heading for, in the order it meets them -- less every
    frontier space the plan holds open (`structure.provisional_room_ids`).
    `bodies` is one name or names in priority order (`actors_ahead`). One
    answer for both readers: the job between turns designs these rooms and
    the install builds them.

    A SPACE HELD OPEN IS THE WRITERS' ROOM'S TO CLAIM. A provisional stub is
    the name the structure's grammar gave a frontier axis -- chat 166's
    `the_open_water`, purpose empty, open onto the landing stage the player
    stood on -- standing in until a plan says what the space is
    (`claim_frontier_spaces`). Built from that name, the space is spent: a
    room with prose is a room somebody has seen, so a claim keeps its name
    and its purpose and geometry reach the registry and never the room, and
    the Room plants ahead exactly there (owner's ruling 2026-10-08). So it
    stays a stub until the Room claims it -- a claimed room is planned like
    any other and built when in view -- and a beat that enters it first
    still designs it in the beat (review of the 2026-10-08 landing)."""
    from world.structure import provisional_room_ids
    if isinstance(bodies, str):
        bodies = [bodies]
    reach = []
    for body in bodies or ():
        for rid in (rooms_in_reach(scene, body) if body else ()):
            if rid not in reach:
                reach.append(rid)
    if not reach:
        return []
    held_open = provisional_room_ids(cid)
    return [rid for rid in reach if rid not in held_open]


def prepared_rooms(chat_id, room_ids):
    """`{room_id: room}` for the prepared designs among `room_ids`: the
    SEEDS a beat that enters one of them hands its designer -- none while
    predevelopment is off, so a cache an earlier run left behind does not go
    on seeding beats after the host turned the job off. A design the install
    built never gets here: it went in when the beat opened
    (`install_prepared_rooms`), and the room is no stub to develop. What
    does is a design that is not clean, one the install refused, and one of
    a room the install does not build."""
    from core.db import wget
    if not predevelopment_enabled():
        return {}
    cache = wget(chat_id, PREPARED_KEY) or {}
    if not isinstance(cache, dict):
        return {}
    out = {}
    for rid in room_ids or ():
        entry = cache.get(rid)
        if not isinstance(entry, dict):
            continue
        # A DESIGN SEEDS ONLY THE BRIEF IT WAS MADE FROM. Given the beat's own
        # briefs (`{room_id: brief}`), a design whose brief has since changed
        # -- a re-plan landing after the last commit tail -- is no seed.
        if isinstance(room_ids, dict) and entry.get("brief") != _brief_signature(
                room_ids[rid]):
            continue
        room = entry.get("room")
        if isinstance(room, dict):
            out[rid] = room
    return out


def _installable(rid, room, why=None):
    """The design as the beat's spatial owner will carry it, or None when
    the state schema refuses it: what the beat opens on and what it commits
    must be the same record. `why`, a list, receives the refusal in words:
    no layout check sees it, so it is what a designer taking the design up
    again reads first (`design_rooms`' `seed_check`)."""
    from llm.schemas import StateDiff, validated_state_diff_channels
    why = why if why is not None else []
    if not isinstance(room, dict):
        why.append(f"{rid}: there is no record to build")
        return None
    if not str(room.get("desc") or "").strip():
        why.append(f"{rid}: the record has no desc, and a room stands in the "
                   f"world described")
        return None
    refused = f"{rid}: the world's state schema refuses the record"
    try:
        clean, dropped = validated_state_diff_channels(
            {"rooms": {rid: copy.deepcopy(room)}})
    except Exception as exc:
        why.append(f"{refused}: {' '.join(str(exc).split())[:400]}")
        return None
    record = ((clean.get("rooms") or {}).get(rid))
    if "rooms" in dropped or not isinstance(record, dict):
        try:
            StateDiff(rooms={rid: copy.deepcopy(room)})
        except Exception as exc:
            refused = f"{refused}: {' '.join(str(exc).split())[:400]}"
        why.append(refused)
        return None
    return record


def _install_test(scene, cache, targets, briefs):
    """`(installed, refused)`: THE INSTALL'S TEST, one rule for both of its
    readers -- `install_prepared_rooms`, which builds `installed`
    (`{room_id: record}`) into the scene a beat opens on, and the job
    between turns, which runs it first and takes each design in `refused`
    (`{room_id: the check that refused it}`) up again, rather than leave a
    refusal standing for good (review of the 2026-10-08 landing).

    A CANDIDATE is a design filed clean (`clean` True) from the brief the
    plan holds for its room now (`_brief_signature`), for a stub among
    `targets`, taken in their order -- the order the player meets them. It
    is built in when the state schema takes it (`_installable`) and the
    engine's layout check is clean against `scene` with every room built
    beside it: all together first, one check on the common beat; otherwise
    one by one, each kept only if the rooms built so far still check clean
    beside it. A candidate that fails is refused with what failed it --
    the schema's words, or the layout check's result. Anything that is no
    candidate -- no design, an unclean one, one made from an older brief --
    is neither installed nor refused."""
    candidates, refused = {}, {}
    for rid in targets or ():
        entry = cache.get(rid)
        if not (isinstance(entry, dict) and entry.get("clean") is True
                and rid in briefs
                and entry.get("brief") == _brief_signature(briefs[rid])):
            continue
        why = []
        record = _installable(rid, entry.get("room"), why)
        if record is None:
            refused[rid] = {"clean": False, "errors": why}
        else:
            candidates[rid] = record
    if not candidates:
        return {}, refused

    def check(rooms):
        return _check(scene, {"rooms": copy.deepcopy(rooms), "remove_rooms": [],
                              "remove_adjacent": []}, list(rooms))

    together = check(candidates)
    if together.get("clean"):
        return candidates, refused
    if len(candidates) == 1:
        refused.update((rid, together) for rid in candidates)
        return {}, refused
    installed = {}
    for rid, record in candidates.items():
        trial = dict(installed, **{rid: record})
        result = check(trial)
        if result.get("clean"):
            installed = trial
        else:
            refused[rid] = result
    return installed, refused


def install_prepared_rooms(cid, scene, body=None, *, cast=None, frame_id=None):
    """`(scene, installed)`: the scene a beat opens on, with every finished
    design for a planned room an actor of the beat can see into or is
    heading for built into it, and `{room_id: record}` of the designs built.

    THE ACTORS are `body` -- the player -- and, given the beat's `cast` rows,
    every body `actors_ahead` finds in this frame's scene: the players, then
    each cast member the scene places, in the order their rooms are wanted,
    so where two designs fight over one wall the player's is the one built.
    Any actor and not only the player (owner, 2026-10-08: "Rooms in view of,
    or ahead of, ANY cast member get built, bubble travellers included").

    PREPARED OUT OF BAND, INSTALLED IN BAND. The job that designs rooms
    between turns (`schedule_room_predevelopment`) never writes the scene,
    and neither does this: the commit stays its one writer. The beat's first
    stage, `director_interpret`, opens on the returned scene -- the
    Director, its encoder and any room author read the built rooms -- and
    its prose contract puts them into the beat as its first event
    (`director_prose.with_installed_rooms`, `room_event`); a bubble's own
    beat, which runs no prose contract at interpret, and a silent beat,
    whose places row goes with its declarations, carry them in their
    assertions instead (`carry_installed_rooms`). So perception previews
    them like any of the beat's own writes, the view through a doorway holds
    the built room, and the commit persists them through its ordinary path:
    the registry projection, the checkpoint, the archive. A reroll restores
    the pre-turn checkpoint, where the room is a stub again, and installs it
    again rather than twice.

    A design is built in when every one of these holds (`_install_test`):
    its room is one the world builds now (`rooms_to_build`: in reach, and no
    frontier space held open for the Writers' Room) and still the plan's
    stub -- a beat that developed it meanwhile wins; it was made from the
    brief the plan holds for the room now (`_brief_signature`); its final
    check came back clean; the state schema takes it; and the engine's
    layout check is still clean against THIS scene together with every room
    built beside it. A design that fails any of them stays where it was: a
    seed for the beat that enters the room (`prepared_rooms`), and the next
    commit's job, running the same test, takes a refused one up again
    (`PREDEVELOP_CONTINUATIONS`). Deterministic and model-free; off with
    predevelopment or the room author."""
    from agents import director_prose
    from core.db import wget
    from world.spatial import merge_scene_with_diff
    from world.structure import planned_room_brief
    if not (director_prose.room_agent_enabled() and predevelopment_enabled()):
        return scene, {}
    cache = wget(cid, PREPARED_KEY) or {}
    if not isinstance(cache, dict) or not cache:
        return scene, {}
    bodies = [body] if body else []
    if cast is not None:
        players, members = actors_ahead(cid, frame_id, scene, cast)
        bodies = list(dict.fromkeys(bodies + players + members))
    targets = [rid for rid in rooms_to_build(cid, scene, bodies) if rid in cache]
    if not targets:
        return scene, {}
    briefs = planned_room_brief(cid, scene, targets) or {}
    installed, _refused = _install_test(scene, cache, targets, briefs)
    if not installed:
        return scene, {}
    return (merge_scene_with_diff(copy.deepcopy(scene),
                                  {"rooms": copy.deepcopy(installed)},
                                  age_contacts=False),
            installed)


def carry_installed_rooms(out, installed):
    """An interpretation carrying the rooms its beat opened on where no
    prose contract ran to carry them -- a causality bubble's own beat
    (`offscreen_beat.offscreen_interpretation`), which declares nothing --
    or where the row that carried them went with everything the stage's
    prose made: a silent beat (`director_interpret`'s empty-input guard).
    On a played beat they ride the prose contract's first event; here they
    go into the stage's assertions and their onset, exactly as the install
    built them, so perception previews them, the resolve reads them off
    `resolve_sc` and carries them into the beat's diff
    (`merge_player_state_assertions`), and the commit persists them in the
    frame's own scene. Recorded under `orchestration.installed_rooms`, as on
    a played beat."""
    if not installed:
        return out
    for key in ("state_assertions", "onset_state_assertions"):
        held = out.get(key)
        held = dict(held) if isinstance(held, dict) else {}
        rooms = dict(held.get("rooms") or {})
        for rid, room in installed.items():
            rooms.setdefault(rid, copy.deepcopy(room))
        held["rooms"] = rooms
        # AS A PLAYED BEAT CARRIES THEM: a leading causal step, so the built
        # rooms stand before anything the beat does to them. Carried at the
        # top level alone they yielded to any resolve write naming the same
        # room and applied after the resolve's steps, so a room shown built
        # -- its door pulled to, its rail leaned on -- was committed as its
        # stub (review of the 2026-10-08 landing, silent and bubble beats).
        steps = [step for step in (held.get("causal_steps") or ())
                 if isinstance(step, dict) and not step.get("installed_rooms")]
        held["causal_steps"] = [{
            "stage": "interpret", "chrono_id": 0, "events": [],
            "installed_rooms": sorted(installed),
            "patch": {"rooms": {rid: copy.deepcopy(room)
                                for rid, room in installed.items()}},
        }] + steps
        out[key] = held
    orchestration = out.get("orchestration")
    orchestration = orchestration if isinstance(orchestration, dict) else {}
    orchestration["installed_rooms"] = sorted(installed)
    out["orchestration"] = orchestration
    return out


def installed_rooms_kept(out, installed):
    """The ids among `installed` that a stage's own assertions still carry
    (`state_assertions`, its causal steps included): what the beat will
    commit, and so what its record may say was built in."""
    held = out.get("state_assertions") if isinstance(out, dict) else None
    held = held if isinstance(held, dict) else {}
    rooms = set(held.get("rooms") or {})
    for step in held.get("causal_steps") or ():
        patch = step.get("patch") if isinstance(step, dict) else None
        if isinstance(patch, dict):
            rooms.update(patch.get("rooms") or {})
    return sorted(rid for rid in (installed or {}) if rid in rooms)


def predevelop_job_key(frame_id):
    """The design job's key for one frame (`PREDEVELOP_JOB_KEY`)."""
    return (PREDEVELOP_JOB_KEY if frame_id is None
            else f"{PREDEVELOP_JOB_KEY}:{frame_id}")


def is_predevelop_job_key(key):
    """Whether a job key is some frame's design job."""
    key = str(key or "")
    return key == PREDEVELOP_JOB_KEY or key.startswith(PREDEVELOP_JOB_KEY + ":")


def cancel_discarded_predevelopment(chat_id, turn_idx):
    """Stop every frame's design run that read a beat a restore to
    `turn_idx` discards (`core.jobs.cancel_from`), and return the runs
    stopped. A run that read only beats the restore keeps goes on: what it
    designs is still the world's, and every write it makes re-reads the row
    the restore put back (`_file_prepared`)."""
    from core import jobs
    stopped = []
    for job in jobs.active_jobs(chat_id):
        if is_predevelop_job_key(job.key) and jobs.cancel_from(
                chat_id, job.key, turn_idx) is not None:
            stopped.append(job)
    return stopped


def _read_prepared(cid):
    """The design cache as the row stands now."""
    from core.db import wget
    stored = wget(cid, PREPARED_KEY) or {}
    return stored if isinstance(stored, dict) else {}


def _file_prepared(cid, job, updates=None, stale=None):
    """File one run's work into the design cache, and say whether it was
    filed.

    RE-READ, NEVER WRITTEN FROM MEMORY. A run writes only the rooms it made
    (`updates`) and drops only the entries it judged stale that nobody has
    refiled since (`stale`, `{room_id: the entry judged}`), onto the row as
    it stands, in one transaction -- so a restore, another frame's run or a
    later run of its own cannot land between the read and the write. A run
    used to write its whole in-memory cache over the row, and a restore
    while it designed lost the restored designs (review of the 2026-10-08
    landing: restored `['lamp_gallery']`, after the run `['watch_room']`).

    NOTHING ONCE CANCELLED (`core.jobs.is_cancelled`, asked inside that
    transaction): a restore cancels a run that read a beat it discards
    before it rolls the row back, so a run whose model call was already
    under way writes nothing that call returned."""
    from core import jobs
    from core.db import transaction, wget, wset
    with transaction():
        if jobs.is_cancelled(job):
            return False
        stored = wget(cid, PREPARED_KEY) or {}
        stored = dict(stored) if isinstance(stored, dict) else {}
        for rid, entry in (stale or {}).items():
            if stored.get(rid) == entry:
                stored.pop(rid, None)
        stored.update(updates or {})
        wset(cid, PREPARED_KEY, stored)
    return True


def _filed_for(entry, brief):
    """Whether a cache entry was made from `brief` (`_brief_signature`)."""
    return isinstance(entry, dict) and entry.get("brief") == _brief_signature(brief)


def _wanted_elsewhere(cid, frame_id, entries):
    """The ids among `entries` (`{room_id: cache entry}`) that another live
    frame's scene still holds as the stub its design was made for.

    The cache is the chat's and every frame's run prunes it. A run that
    dropped each design its own frame no longer needs would drop the one a
    bubble beside it is about to build -- the player's frame builds the
    gallery and its next run drops the design, the bubble whose traveller
    sees the same stub designs it again, and the player's next run drops
    that too, every beat. So a design is kept while ANY live frame (one not
    merged back) holds its room as the stub it was made for."""
    from core.db import wget_for_frame
    from core.frames import frame_index
    from world.structure import planned_room_brief
    wanted = set()
    for other, frame in frame_index(cid).items():
        if other == frame_id or (frame or {}).get("merged_turn_idx") is not None:
            continue
        left = [rid for rid in entries if rid not in wanted]
        if not left:
            break
        scene = wget_for_frame(cid, "scene", other, {}) or {}
        briefs = planned_room_brief(cid, scene, left) or {}
        wanted.update(rid for rid in left
                      if rid in briefs and _filed_for(entries[rid], briefs[rid]))
    return wanted


def _frame_is_live(frame_id):
    """Whether a frame can still hold a beat: the present, or a frame not
    merged back into its parent. A run for a frame that merged while it
    waited designs nothing."""
    if frame_id is None:
        return True
    from core.frames import get_frame
    frame = get_frame(frame_id)
    return bool(frame) and frame.get("merged_turn_idx") is None


def schedule_room_predevelopment(ctx):
    """After a prose-contract turn commits, in any frame, design the
    planned rooms ahead of that frame's actors (`actors_ahead`,
    `rooms_to_build`) out of band, so its next beat opens with them built
    (`install_prepared_rooms`). On unless the host turned it off
    (`PREDEVELOP_SETTING`). One job per frame (`predevelop_job_key`); never
    inside the turn's wall clock; it writes its cache and never the scene; a
    failure is logged, never raised.

    A LIVE BUBBLE'S COMMIT DESIGNS ITS TRAVELLERS' ROOMS. It used to design
    nothing ("the player is not in its frame"), so a cast member who walked
    away from the player looked through every doorway at a bare name. A
    bubble's beats run the pipeline like a played one, so what its commit
    designs is built in at its next beat, in its own scene
    (`carry_installed_rooms`).

    A COMMIT DURING A RUN ASKS FOR ONE MORE (`core.jobs.submit_latest`). A
    run reads the scene once and a design takes about 40 s, so a sub-minute
    beat's commit used to join a run that never saw its view, and the room
    that beat brought into view waited for the first commit after the run
    ended (review of the 2026-10-08 landing). The next run reads the scene,
    the actors, the plan and the cache afresh and files under the newest
    turn that asked; the asks made during one run fold into one more run, so
    the work stays bounded by the commits.

    A BRIEF IS DESIGNED ONCE. Every attempt is filed under the fingerprint
    of the brief it was made from (`_brief_signature`) -- a design whose
    final check came back clean (the next beat in reach of its room builds
    it in), one whose check did not (kept as a seed: the in-turn designer
    is handed its check and fixes it, rather than building the room again
    from nothing), an attempt that drafted nothing, and a run that FAILED
    (tried again only after `predevelop_retry_beats`) -- and a room is
    designed afresh only when its plan's brief changes. Measured on chat
    166: a design was kept only on a clean final check and a failed attempt
    left nothing behind, so four design runs opened on the identical
    8,558-token first call (14:36, 20:34, 20:39 and 20:58). A design is kept
    while some live frame still holds its room as the plan's stub, wherever
    the actors stand, and is filed the moment it is made, so the next beat
    finds every design finished before it opened; it is dropped when no
    frame needs it any more or the plan stops holding it.

    A DESIGN IS TAKEN UP AGAIN, NEVER BEGUN AGAIN, at most
    `PREDEVELOP_CONTINUATIONS` times: one whose own check was not clean, and
    a clean one the install refuses. The job runs the install's own test
    first (`_install_test`) on every clean design in reach, against the
    scene it designs on. What would stand is merged into that scene before
    anything is drafted, so every design and continuation is drafted beside
    the rooms the next beat builds; a refused design is taken up with the
    check that refused it as the first thing its designer reads. Filed
    clean once and refused after -- a neighbour built since, or two designs
    each clean alone taking the same wall -- a design used to stay refused
    for good and its room a name through the doorway (review of the
    2026-10-08 landing). Refused with its continuations spent, it is filed
    not clean: it waits as a seed for the beat that enters its room, and no
    beat's install checks it again."""
    from core import jobs
    from language_runtime import story_language
    from agents import director_prose

    if not (director_prose.room_agent_enabled() and predevelopment_enabled()):
        return None
    chat = ctx.chat
    cid = chat["id"] if isinstance(chat, dict) else chat.id
    frame_id = ctx.turn.frame_id
    language_id = story_language(cid)

    def _produce(job):
        from core.db import active_frame_id
        from language_runtime import current_language_id
        token = active_frame_id.set(frame_id)
        language_token = current_language_id.set(language_id)
        try:
            return _predevelop_run(job, cid, frame_id, language_id)
        finally:
            current_language_id.reset(language_token)
            active_frame_id.reset(token)

    return jobs.submit_latest(cid, predevelop_job_key(frame_id), _produce,
                              base_turn=ctx.turn.idx)


def _predevelop_run(job, cid, frame_id, language_id):
    """One run of a frame's design job, on the world as it stands NOW: the
    frame's scene, its actors, the plan and the cache, all read afresh, and
    every filing stamped with `job.base_turn` -- the newest turn that asked
    for this run. Returns what it did, in words."""
    from core import jobs
    from core.db import wget
    from core.logging_utils import logger
    from llm.prompts import prose_contract_text, room_author_prompt
    from world.structure import planned_room_brief
    from agents.common import _agent_json

    turn_idx = job.base_turn
    if not _frame_is_live(frame_id):
        return []
    current = wget(cid, "scene") or {}
    players, cast = actors_ahead(cid, frame_id, current)
    # THE PLAYERS' ROOMS FIRST, then the cast's; a room both reach is the
    # players'. Within the bound a bystander's room never costs the player
    # one of theirs.
    tiers, seen = [], set()
    for bodies in (players, cast):
        tier = [rid for rid in rooms_to_build(cid, current, bodies)
                if rid not in seen]
        seen.update(tier)
        tiers.append(tier)
    near = [rid for tier in tiers for rid in tier]
    stored = _read_prepared(cid)
    if not near and not stored:
        return []
    briefs = planned_room_brief(
        cid, current, list(dict.fromkeys(near + list(stored)))) or {}
    # A design is kept only while its room is a stub AND the plan's brief
    # for it is the one it was made from, near or far: a far stub's old
    # design otherwise outlived its re-plan and seeded the beat that finally
    # entered it (review, 2026-10-08). A room a beat built is no stub here --
    # and is kept while another live frame still holds it as one.
    stale = {rid: entry for rid, entry in stored.items()
             if not (rid in briefs and _filed_for(entry, briefs[rid]))}
    for rid in (_wanted_elsewhere(cid, frame_id, stale) if stale else ()):
        stale.pop(rid, None)
    cache = {rid: entry for rid, entry in stored.items() if rid not in stale}
    # THE INSTALL'S OWN TEST, FIRST, on the scene the next beat opens on:
    # what would stand is merged into the scene everything below is drafted
    # on, and a refused design is taken up again beside it -- or, its
    # continuations spent, filed not clean.
    standing, refused = _install_test(current, cache, near, briefs)
    if standing:
        current = _merged(current, {"rooms": standing})
    spent = {rid: dict(cache[rid], clean=False, refused_turn=turn_idx)
             for rid in refused
             if int(cache[rid].get("continued") or 0) >= PREDEVELOP_CONTINUATIONS}
    cache.update(spent)
    if (stale or spent) and not _file_prepared(cid, job, spent, stale):
        return []

    def owed(rid):
        """What this run owes the room: a "fresh" design, an "again"
        continuation of the one filed, or nothing."""
        entry = cache.get(rid)
        if rid not in briefs:
            return None
        if entry is None:
            return "fresh"
        if not _filed_for(entry, briefs[rid]):
            # MADE FROM ANOTHER FRAME'S BRIEF for this room, and kept because
            # that frame still holds the stub it was made for
            # (`_wanted_elsewhere`): one cache row holds one design a room,
            # so it is that frame's to build. Taken up here, the two frames'
            # runs would trade the room back and forth. This frame's beat
            # that enters the room still designs it in the beat.
            return None
        if _backing_off(entry, turn_idx):
            return None
        if not isinstance(entry.get("room"), dict):
            # A run that FAILED drafted nothing, and is tried again once its
            # back-off is over; a run that finished having drafted nothing
            # was the brief's one design.
            return "fresh" if entry.get("failed") else None
        if int(entry.get("continued") or 0) >= PREDEVELOP_CONTINUATIONS:
            return None
        if rid in refused or not entry.get("clean"):
            return "again"
        return None

    kind = {rid: owed(rid) for rid in near}
    todo = []
    for tier in tiers:
        todo += [rid for rid in tier if kind[rid] == "fresh"]
        todo += [rid for rid in tier if kind[rid] == "again"]
    todo = todo[:PREDEVELOP_PER_TURN]
    if not todo:
        return []
    sheet = room_author_prompt(language_id)
    note = prose_contract_text("room_prepare_note", language_id)
    done = []
    for rid in todo:
        if jobs.is_cancelled(job):
            break
        # ANOTHER FRAME'S RUN MAY HAVE FILED THIS ROOM since this run read
        # the cache: the same stub in two frames' views. Its filing stands.
        if _read_prepared(cid).get(rid) != cache.get(rid):
            done.append(f"left {rid}: filed by another run")
            continue
        record = {}
        entry = cache.get(rid) or {}
        earlier = entry if kind[rid] == "again" else None
        # NOT `prepared`: the room author's card reads that field as a
        # design to keep except where a beat's prose says otherwise, and
        # between turns there is no prose. The pack's note says what a draft
        # already holding the room is.
        payload = {"prose": "", "note": note, "develop": {rid: briefs[rid]}}
        try:
            draft = design_rooms(
                None, current, payload, sheet, [rid],
                lambda system, payload: _agent_json(
                    "director_rooms", "director_rooms", system, payload,
                    temperature=0.4, max_tokens=None),
                record,
                seed={rid: copy.deepcopy(earlier["room"])} if earlier else None,
                seed_check=refused.get(rid) if earlier else None)
        except Exception as exc:
            # A FAILED RUN IS FILED, and the room waits
            # (`predevelop_retry_beats`): unfiled, it was designed again from
            # nothing on every commit. What the entry held stays -- a seed is
            # still a seed.
            failed = int(entry.get("failed") or 0) + 1
            room = entry.get("room")
            filed = dict(entry, brief=_brief_signature(briefs[rid]),
                         room=room if isinstance(room, dict) else None,
                         clean=entry.get("clean") is True,
                         failed=failed, failed_turn=turn_idx,
                         error=str(exc)[:300])
            if not _file_prepared(cid, job, {rid: filed}):
                break
            cache[rid] = filed
            wait = predevelop_retry_beats(failed)
            logger.info("room predevelopment failed: chat=%s room=%s "
                        "failures=%d wait=%d error=%s",
                        cid, rid, failed, wait, str(exc)[:300])
            done.append(f"failed {rid} ({failed} in a row; tried again "
                        f"after {wait} beats)")
            continue
        designed = (draft.get("rooms") or {}).get(rid)
        clean = bool((record.get("final_check") or {}).get("clean"))
        filed = {"room": designed if isinstance(designed, dict) else None,
                 "turn": turn_idx, "steps": record.get("steps"),
                 "brief": _brief_signature(briefs[rid]),
                 "clean": clean and isinstance(designed, dict),
                 "continued": (int(earlier.get("continued") or 0) + 1
                               if earlier else 0)}
        # FILED THE MOMENT IT IS MADE: a beat that opens while a later room
        # is still being designed builds this one in.
        if not _file_prepared(cid, job, {rid: filed}):
            break
        cache[rid] = filed
        # Rooms in view of one another are designed in view of one another:
        # the next design's surroundings and check hold this one, as the
        # beat that builds both will.
        built = _installable(rid, designed) if filed["clean"] else None
        if built is not None:
            current = _merged(current, {"rooms": {rid: built}})
        if isinstance(designed, dict):
            done.append(f"prepared {rid}" if clean
                        else f"prepared {rid} (its check not clean)")
        else:
            done.append(f"drafted nothing for {rid}")
    return done
