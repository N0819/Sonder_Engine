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
#: Standing rooms handed over already inspected -- `_inspect`'s own cap.
ROOM_SURROUNDINGS = 6
#: Wall seconds code may spend trying where a new place's doorway fits
#: (about 13 ms a try on a six-room scene; each try is one merge and one
#: layout check).
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
        "does": "The standing geometry of rooms already in the world: name, "
                "description, size, extent, shape, doorways with their bearing "
                "and barrier, fixtures, and the cell map. The rooms around "
                "your place are already in `surroundings`; this is for any "
                "other room.",
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


def _inspect(scene, room_ids):
    rooms = (scene or {}).get("rooms") or {}
    out = {}
    for rid in list(room_ids or [])[:6]:
        room = rooms.get(str(rid))
        if not isinstance(room, dict):
            out[str(rid)] = {"refused": "no such room"}
            continue
        view = render_room(scene, str(rid))
        out[str(rid)] = {
            "name": room.get("name"), "desc": str(room.get("desc") or "")[:400],
            "size": room.get("size"), "extent": room.get("extent"),
            "shape": room.get("shape"), "parent_entity": room.get("parent_entity"),
            "adjacent": [{k: e.get(k) for k in ("to", "barrier", "dir", "distance")}
                         for e in room.get("adjacent") or [] if isinstance(e, dict)],
            "map": view.get("map"), "legend": view.get("legend"),
        }
    return out


def _check(scene, draft, owed, rows_out=None):
    """The layout check over the draft merged into the world. `rows_out`, a
    list, receives the check's raw rows for code; the model reads only the
    sentences."""
    from world.spatial import layout_warning, room_layout_lint
    try:
        merged = _merged(scene, draft)
        rows = room_layout_lint(merged, prev_scene=scene)
        errors = [layout_warning(row) for row in rows]
    except Exception as exc:
        return {"errors": [f"the draft could not be merged into the world: {exc}"]}
    if rows_out is not None:
        rows_out.extend(rows)
    drafted = set((draft.get("rooms") or {}))
    missing = [rid for rid in owed if rid not in drafted]
    unplaced, overlapping = [], []
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
    crowded = _crowded_walls(merged, rows, drafted)
    if crowded:
        out["crowded_walls"] = crowded
    return out


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


def _crowded_walls(merged, rows, drafted):
    """The arithmetic behind each overfull wall of a drafted room, the way
    the check counted it: the wall's length and which side of the extent
    that is, and the paces each fixture on it takes. A designer handed only
    "needs 7, has 5" widened the wrong side twice (the 2026-09-27 yard: its
    west wall runs north-south, so it is the extent's `d`)."""
    from world.spatial import anchor_cells, room_grid
    out = []
    for row in rows or ():
        if row.get("kind") != "wall_overfull" or row.get("room") not in drafted:
            continue
        rid, wall = row["room"], row.get("wall")
        try:
            placed = anchor_cells(merged, rid) or {}
            length = len(room_grid(merged, rid).rim(wall))
        except Exception:
            continue
        out.append({
            "room": rid, "wall": wall, "length_paces": length,
            "length_is": ("the extent's w (east-west)" if wall in ("n", "s")
                          else "the extent's d (north-south)"),
            "fixtures_paces": {aid: len(rec.get("cells") or ()) for aid, rec in placed.items()
                               if rec.get("dir") == wall and not rec.get("implicit")},
        })
    return out


def _fit(value, limit):
    text = json.dumps(value, ensure_ascii=False, default=str)
    if len(text) <= limit:
        return value
    return {"truncated": text[:limit]}


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


def _doorways_that_fit(scene, rid, place, hosts, deadline, draft=None):
    """Where a NEW place's doorway can go: each free wall of each host,
    tried by laying the place there alone and asking the engine's own
    layout check. A wall is kept when the check names nothing new between
    rooms and no bearing anywhere is lost (a doorway laid on a wall another
    doorway holds can drop both bearings, and the check then reads clean).

    Without `draft`, the place is tried at every shape `_trial_shapes`
    gives it. With `draft`, it is tried as DRAFTED -- its own extent and
    fixtures, every other drafted room in place, and none of its drafted
    doorways -- which is what the check hands back when the place stopped
    fitting where its doorways put it.

    Returns `[{"to", "dir", "their_wall"}]`, `dir` being the place's own
    wall -- the edge exactly as the place writes it."""
    from world.spatial import merge_scene_with_diff, opposite_bearing, room_layout_lint
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
        shapes = [None]             # the drafted record is already in `base`
    else:
        base = scene or {}
        shapes = _trial_shapes(place)
    before = _bearings(base)
    fits = []
    for host in hosts:
        taken = _taken_walls(base, host)
        for wall in _WALLS_TRIED:
            if time.time() > deadline:
                return fits
            if wall in taken:
                continue
            mine = opposite_bearing(wall)
            edge = {"to": host, "barrier": "open", "dir": mine}
            ok = True
            for shape in shapes:
                trial = dict(shape or {}, adjacent=[edge])
                try:
                    merged = merge_scene_with_diff(copy.deepcopy(base), {"rooms": {rid: trial}})
                    rows = room_layout_lint(merged, prev_scene=base)
                except Exception:
                    ok = False
                    break
                # The place's own interior is the designer's to arrange; a
                # row about it alone says nothing about where it stands.
                rows = [row for row in rows if row.get("room") != rid]
                after = _bearings(merged)
                if rows or after.get((rid, host)) != mine \
                        or any(was and not after.get(key) for key, was in before.items()):
                    ok = False
                    break
            if ok:
                fits.append({"to": host, "dir": mine, "their_wall": wall})
    # A straight wall before a corner, whichever room it is on.
    return sorted(fits, key=lambda f: len(f["their_wall"]) > 1)


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
    the standing rooms around its places drawn as `inspect_rooms` draws
    them, and `placing`, for each place the Director invented, the floor
    area its size word covers and the doorways that fit."""
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
    reserved = payload.get("reserved_places") if isinstance(payload.get("reserved_places"), dict) else {}
    placing = {}
    deadline = t0 + ROOM_PLACEMENT_SECONDS
    for rid, place in reserved.items():
        if rid in rooms:
            continue                        # standing: its doorways are in the world
        entry = {}
        floor = _floor_for_size((place or {}).get("size"))
        if floor:
            entry["size"] = str(place.get("size")).strip().casefold()
            entry["floor_square_paces"] = floor
        try:
            entry["doorways_that_fit"] = _doorways_that_fit(
                scene, rid, place, around, deadline)
        except Exception:
            entry["doorways_that_fit"] = []
        placing[rid] = entry
    if placing:
        out["placing"] = placing
    record["groundwork"] = {
        "surroundings": around, "drawn": drawn,
        "doorways_that_fit": {rid: len(e.get("doorways_that_fit") or ()) for rid, e in placing.items()},
        "seconds": round(time.time() - t0, 3)}
    return out


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


def _refit(scene, draft, rows, places, hosts):
    """`{place: doorways that fit it as drafted}` for each new place the
    check says stands where it cannot -- the concrete way out of a
    contradiction a designer otherwise circles (the 2026-09-27 yard: five
    steps round a placement the barracks already held)."""
    out = {}
    deadline = time.time() + ROOM_PLACEMENT_SECONDS
    for rid in places:
        if rid not in (draft.get("rooms") or {}):
            continue
        own = [str(e.get("to")) for e in (draft["rooms"][rid].get("adjacent") or ())
               if isinstance(e, dict) and e.get("to")]
        near = list(dict.fromkeys(list(hosts) + [to for to in own
                                                 if to in ((scene or {}).get("rooms") or {})]))
        if not _misplaced(rows, rid, near):
            continue
        try:
            out[rid] = _doorways_that_fit(scene, rid, None, near, deadline, draft=draft)
        except Exception:
            continue
    return out


# ---- what code does after every step -------------------------------------------

def _agree_sizes(scene, draft):
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
        held_rooms = _merged(scene, draft).get("rooms") or {}
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


def _finished(prose, scene, draft, owed, language, record):
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
    merged = _merged(scene, draft)
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


def design_rooms(ctx, scene, payload, sheet, owed, call, record=None, seed=None):
    """Run the designer. `payload` is its standing input (prose, plans,
    reserved places, the spatial slice); `owed` the room ids it must draft;
    `call(system, payload)` one model step. Returns the draft as
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
    owed_names = _owed_names(scene, payload, owed)

    def checked():
        # Every check sets the size words first: the extent decides a
        # room's size, so a disagreement is only ever the label's.
        agreed = _agree_sizes(scene, draft)
        rows = []
        result = _check(scene, draft, owed, rows_out=rows)
        if agreed:
            result = dict(result, sizes_agreed=agreed)
        # A new place that stands where it cannot gets the walls where it
        # would stand, as drafted -- the way out, not only the problem.
        refit = _refit(scene, draft, rows, new_places, hosts) if rows else {}
        if refit:
            result = dict(result, doorways_that_fit=refit)
            record["refits"] = record.get("refits", 0) + 1
        return result

    # A PREPARED design may already be the answer: checked and read against
    # this beat's prose before any model step is spent on it.
    if seed and prose:
        last_check = checked()
        if last_check.get("clean") and _finished(prose, scene, draft, owed,
                                                 language, record)[0]:
            record.update(steps=0, calls=0, stopped="complete",
                          seconds=round(time.time() - started, 3),
                          final_check=_check(scene, draft, owed))
            return draft
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
                    # The plan comes back with every draft: seeing the room is
                    # part of drafting it, not a step spent asking to look.
                    try:
                        plan = render_room(_merged(scene, draft), rid)
                    except Exception as exc:
                        plan = {"refused": f"could not draw the room: {exc}"}
                    result = {"drafted": rid, "fields": sorted(draft["rooms"][rid]),
                              "plan": plan}
                    if renamed:
                        result["drafted_as"] = (f"{renamed!r} is the place you owe as {rid!r}: "
                                                f"the id you were given is fixed")
            elif tool == "view_room":
                result = render_room(_merged(scene, draft), str(args.get("room_id") or ""))
            elif tool == "inspect_rooms":
                result = _inspect(_merged(scene, draft), args.get("room_ids") or [])
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
                               "result": _fit(result, ROOM_RESULT_CHARS)})
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
            finished, notes = _finished(prose, scene, draft, owed, language, record)
            if finished:
                stopped = "complete"
                break
            # SAID ONCE. The reader can be wrong, and a designer told the
            # same thing every step chases it: the 2026-09-27 yard wrote
            # "this is where Luca stands" into a fixture to satisfy a
            # reading the grave already answered.
            if notes and not record.get("still_missing_said"):
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
    final = _check(scene, draft, owed)
    record.update(steps=step, calls=sum(1 for entry in transcript if not entry.get("by")),
                  stopped=stopped, seconds=round(time.time() - started, 3),
                  final_check=final)
    return draft


# ---- between turns: prepare the planned rooms the player could enter next --

#: The world key holding designs prepared before anyone arrived, by room id.
#: A reconstructible cache: lost, the in-turn designer simply does the work.
PREPARED_KEY = "prose_contract_prepared_rooms"
#: Planned rooms prepared per committed turn at most. Named per the owner's
#: ask-before-limiting rule: each is a full designer run on the room role.
PREDEVELOP_PER_TURN = 2
PREPARE_NOTE = ("No beat is happening. These planned rooms lie next to where the "
                "player is and have not been entered yet: design each at full "
                "fidelity from its plan now, so it is ready when someone arrives.")


def prepared_rooms(chat_id, room_ids):
    """`{room_id: room}` for the prepared designs among `room_ids`."""
    from core.db import wget
    cache = wget(chat_id, PREPARED_KEY) or {}
    if not isinstance(cache, dict):
        return {}
    out = {}
    for rid in room_ids or ():
        room = (cache.get(rid) or {}).get("room") if isinstance(cache.get(rid), dict) else None
        if isinstance(room, dict):
            out[rid] = room
    return out


def schedule_room_predevelopment(ctx):
    """After a prose-contract turn commits, design the planned rooms beside
    the player out of band, so a beat that enters one starts from a finished
    design and only adapts it to its own prose. Deduped per chat by
    `jobs.submit`; never inside the turn's wall clock; a failure is logged,
    never raised."""
    from core import jobs
    from core.db import wget
    from language_runtime import story_language
    from story.character_schema import persona_name
    from story.scene import persona_of
    from world.spatial import room_of
    from agents import director_prose

    if not director_prose.room_agent_enabled():
        return None
    chat = ctx.chat
    cid = chat["id"] if isinstance(chat, dict) else chat.id
    pers = persona_of(chat) or {}
    p_name = pers.get("name") or persona_name(pers)
    scene = wget(cid, "scene") or {}
    room = room_of(scene, p_name)
    if not room:
        return None
    frame_id = ctx.turn.frame_id
    turn_idx = ctx.turn.idx
    language_id = story_language(cid)

    def _produce(job):
        from core.db import active_frame_id, wget as _wget, wset
        from core.logging_utils import logger
        from language_runtime import current_language_id
        from llm.prompts import room_author_prompt
        from world.structure import planned_room_brief, rooms_to_develop
        from agents.common import _agent_json
        token = active_frame_id.set(frame_id)
        language_token = current_language_id.set(language_id)
        try:
            current = _wget(cid, "scene") or {}
            briefs = planned_room_brief(cid, current, rooms_to_develop(current, room)) or {}
            cache = _wget(cid, PREPARED_KEY) or {}
            cache = ({rid: entry for rid, entry in cache.items() if rid in briefs}
                     if isinstance(cache, dict) else {})
            todo = [rid for rid in briefs if rid not in cache][:PREDEVELOP_PER_TURN]
            sheet = room_author_prompt(language_id)
            done = []
            for rid in todo:
                if job.cancelled.is_set():
                    break
                record = {}
                try:
                    draft = design_rooms(
                        None, current,
                        {"prose": "", "note": PREPARE_NOTE,
                         "develop": {rid: briefs[rid]}},
                        sheet, [rid],
                        lambda system, payload: _agent_json(
                            "director_rooms", "director_rooms", system, payload,
                            temperature=0.4, max_tokens=None),
                        record)
                except Exception as exc:
                    logger.info("room predevelopment failed: chat=%s room=%s "
                                "error=%s", cid, rid, str(exc)[:300])
                    continue
                designed = (draft.get("rooms") or {}).get(rid)
                if isinstance(designed, dict) and (record.get("final_check") or {}).get("clean"):
                    cache[rid] = {"room": designed, "turn": turn_idx,
                                  "steps": record.get("steps")}
                    done.append(rid)
            wset(cid, PREPARED_KEY, cache)
            return [f"prepared {rid}" for rid in done]
        finally:
            current_language_id.reset(language_token)
            active_frame_id.reset(token)

    return jobs.submit(cid, "room_predevelopment", _produce, base_turn=turn_idx)
