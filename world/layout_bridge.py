"""A planned building laid out by the layout solver, as the plan's own geometry.

The layout lab's split, wired as a tier of the plan (survey rank 6, first
slice; the owner's choice of 2026-10-08): "a model decides what and why, code
decides where and how, and a model dresses it only when an actor comes near."
Two calls on the room designer's role say what each planned room holds and how
its contents relate (`agents/director_layout.py`); `world.layout_solver` owns
every coordinate; this module holds the answers to the plan, turns them into
the solver's spec, and turns the solve into the plan's geometry -- a `site` on
the building's plan, an `extent`, each fixture pinned to the cells it stands
on, each doorway at its place along its wall. Pure: no model, no database.

WHAT IS A BUILDING. The plan says which rooms exist, what each is for and how
they join; it does not say which share a roof. A stair does: two rooms joined
`up`/`down` are two storeys of one building -- when both are rooms a wall
can go round. A room the plan or the scene states is `open` or `sheltered`
(`weather.EXPOSURES`: no walls round it) is never a storey: a plank walk up a
flight of steps to another walk is ground on two heights, not a house, and a
stair from a storey down to such a place is an OUTSIDE stair, a way the
building opens onto (review of 2026-10-08, F4). So a building is the rooms of
one structure joined by stairs between rooms that may be storeys, grown along
level joins into rooms the plan or the scene states are `enclosed` -- the
engine's own word for a room with walls round it; a room of unstated
exposure is not guessed into a building along a level join. What the
building's rooms join outside it is the ground it opens onto. Nothing here
reads a name or a purpose for meaning.

WHAT THE PLAN FIXES, CODE KEEPS. The rooms, their ids, names and storeys;
which rooms join which (a join the model writes that the plan lacks is
dropped: a plan never gains a way between rooms); which rooms a stair joins
and whether it is a ladder (`spatial_levels.WAYS`); a side the plan's own
bearing gives; the front, when the ground the entrance opens onto states a
bearing toward it. The models say what a room holds and how its things
relate, from the closed vocabularies the solver's own tables enumerate
(`vocabulary`); a word outside them is no word, never a guess.

WHAT A SOLVE BECOMES (`planned_layout`):
* each room its rectangle -- `extent`, `shape` rectangle, `level`, and
  `site` {plan, x, y, elev_m} on the building's plan; a room in a block of
  its own keeps the shape the plan states, inside the solved box;
* each fixture placed as asked an anchor pinned to its rectangle (`cell` and
  `extent`, read by `spatial_fov.anchor_extent`), its height the solver's,
  its `dir` the wall it stands against; several alike are one anchor each,
  the first under the plan's own id when the plan named them, so no record
  of the plan is left standing beside its copies;
* each fixture the plan lists that the first call says MARKS where a stair
  or a doorway meets the room (`marks`) -- not a thing standing in it -- a
  point pinned where that way meets the room, blocking no line;
* each fixture the solver moved off the wall the model named, or could not
  place, an anchor on the wall the model named and pinned NOWHERE -- never a
  move made silently: the engine lays it along that wall as it lays every
  unpinned fixture, the designer that dresses the room sees whatever it
  crowds, and settling it is the model's (the owner: "capacity goes back to
  the model"). Both are listed in the solve's record;
* each window an anchor in its wall that blocks no line (`see_through`) --
  in the outside wall the solver found, since a window in an inside wall is
  none, and listed as moved when that is not the wall the model named;
* each doorway between two of the building's rooms, and each onto the ground
  outside, its `dir` and `offset` on the plan's edge;
* each stair the plan's own vertical edge, its `cell` where each room meets
  the stair. The solver's stair halls, stores and voids are NOT rooms: the
  plan holds no such room, and a tier that invents rooms has been refused
  once (98827d9f, reverted: "a loft space that didn't exist before").
Zones (a floor area with no walls) are not carried yet: an anchor is the
engine's only floor place, and a zone holding a cushion would read as two
fixtures on one cell to the designer's check.

THE PLAN'S OWN FIXTURES ARE HELD, as its rooms are (`hold_inventory`): one
the first call left out, or filed only as a zone, is kept as the plan holds
it -- its own record, unpinned, never handed to the solver -- and said to be
(`restored`), since what a thing is stays the model's to say; and a zone
never takes a fixture's id -- a zone is no anchor, and a fixture whose id
went to one was lost (review of 2026-10-08, F3 and R2-2).

FAILS OPEN. `refusals` names everything that stops a solve standing for the
plan -- a planned room with no floor, a stair with no hall, a join with no
doorway, a side the plan states put on another wall -- and a refused
building is written nowhere: today's designer builds its rooms exactly as it
would have. A room's SIZE is none of these. The plan's `extent` is the
Writers' Room's estimate: the solver sizes every room from what it holds,
aimed at a size only where the story's own lore states one, and the solve's
size replaces the estimate, each filed against the other (`stated`,
`described`; the owner's ruling of 2026-10-10). A room the plan states is
not a rectangle stands in a block of its own when it opens into the
building by one doorway on a side the plan states; built from `parts`, or
joined any other way, it refuses the building before any call is made: the
solver lays rectangles. So does a room already standing on the plan the
solve would be written on: placed beside an earlier solve, it stands in that
solve's frame. A side only the model chose that the solver put elsewhere is
listed in the record (`sides`), not refused.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re

from world.layout_solver import (FIXTURE_SIZES, PURPOSE_AREA, SIZE_WORD_FOOTPRINT,
                                 STAIR_FALLBACK, STAIRS, ZONE_SIZES, check, fixture_footprint,
                                 solve)
from world.structure import LAYOUT_PLAN_PREFIX

#: Rooms one building may hold for the tier to lay it out. The solver
#: divides every storey many times over (`layout_solver.QUICK`/`TRIES`): the
#: owner's preferred shrine -- eleven planned rooms on four storeys and three
#: stair halls -- took 11.1 s. Past this many rooms a group of planned rooms
#: is a quarter of a town rather than a building, which is the town-fabric
#: tier's work (survey rank 7) and not this one's. A per-solve bound on job
#: time; a building over it fails open to the designer, which builds it
#: room by room as it always has. Named per ask-before-limiting.
LAYOUT_TIER_MAX_ROOMS = 24
#: How many seeds of the solver's search one building is tried with before
#: the bridge refuses it (`solve_for`): the solver's own seed first, then the
#: next ones, each only where the one before fell short. A solve of the
#: owner's shrine takes 7 to 9 s, so this bounds the worst case near 35 s of
#: one background job, or of a launch whose opening stands in a planned
#: building (`director_layout.lay_out_opening_ground`). Named per
#: ask-before-limiting.
LAYOUT_SOLVE_SEEDS = 4
#: The one shape the solver lays. A room the plan states another shape of
#: (`spatial_fov.SHAPES`: round, l, composite) refuses its building before
#: any call is made: written back, its rectangle would square a round tower
#: room for good (review of 2026-10-08, F2).
SOLVED_SHAPE = "rectangle"
#: The exposure of a room with walls round it (`weather.EXPOSURES`).
WALLED = "enclosed"
#: The exposures a room may have and still be a STOREY of a building: walled,
#: or not stated (a stair says the room has a floor above or below it, and a
#: plan rarely states the exposure of a loft). A room stated `open` is ground
#: on a height -- a walk up a flight of steps -- and never a storey (review of
#: 2026-10-08, F4). `sheltered` -- a roof and no walls round it, a porch or a
#: covered gallery -- is kept out too, since the solver walls every storey it
#: lays; adding it here lets a stair make one a storey. The owner's call.
STOREY_EXPOSURES = ("", WALLED)
#: The most of one fixture, and of one window, an answer's `count` may ask
#: for. The solver lays no more of either (`layout_solver._sort_fixtures`
#: clamps a fixture's count to 24, `_place_windows` a window's to 8), so a
#: larger count is held to the number it would lay rather than promised and
#: lost. Named per ask-before-limiting; they follow the solver's own.
FIXTURE_COUNT_MAX = 24
WINDOW_COUNT_MAX = 8

_SIDES = ("n", "e", "s", "w")
_OPP = {"n": "s", "s": "n", "e": "w", "w": "e"}
_STEP = {"n": (0, -1), "s": (0, 1), "e": (1, 0), "w": (-1, 0)}
_CORNERS = ("corner_ne", "corner_se", "corner_sw", "corner_nw")


def vocabulary():
    """The closed sets a model picks from, enumerated from the solver's own
    tables -- engine-owned vocabularies a model chooses among, never a list
    read against its prose (CLAUDE.md, "NO WORD LISTS IN PROMPTS"). The
    quarter-turn stair is not offered: the owner withdrew it
    (`layout_solver.STAIR_FALLBACK`)."""
    return {
        "purposes": sorted(PURPOSE_AREA),
        "fixture_kinds": sorted(FIXTURE_SIZES),
        "sizes": list(SIZE_WORD_FOOTPRINT),
        "zone_sizes": list(ZONE_SIZES),
        "stair_kinds": [k for k in STAIRS if k in STAIR_FALLBACK],
        "places": list(_SIDES) + ["middle"] + list(_CORNERS),
        "mounts": ["floor", "hung", "ceiling", "in <fixture id>", "on <fixture id>"],
    }


def _text(value, limit=200):
    return str(value or "").strip()[:limit]


def _slug(value):
    return re.sub(r"[^a-z0-9_]+", "_", str(value or "").casefold()).strip("_")


def _canon(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)


# ---------------------------------------------------------------- buildings

def _edges_of(specs):
    """Every planned edge, both directions: `{(a, b): {"vertical": 'up'|
    'down'|None, "barrier", "dir", "way"}}` read from the side that declares
    it, and reversed onto the other side when only one does."""
    from world.spatial import normalize_bearing, normalize_vertical, opposite_bearing
    out = {}
    for uid, (_name, spec) in specs.items():
        for edge in (spec or {}).get("adjacent") or ():
            if not isinstance(edge, dict) or not edge.get("to"):
                continue
            to = str(edge["to"])
            if to == uid:
                continue
            out[(uid, to)] = {
                "vertical": normalize_vertical(edge.get("vertical")),
                "barrier": edge.get("barrier"),
                "dir": normalize_bearing(edge.get("dir")),
                "way": str(edge.get("way") or "").strip().casefold(),
            }
    for (a, b), rec in list(out.items()):
        if (b, a) not in out:
            out[(b, a)] = {
                "vertical": {"up": "down", "down": "up"}.get(rec["vertical"]),
                "barrier": rec["barrier"],
                "dir": opposite_bearing(rec["dir"]) if rec["dir"] else None,
                "way": rec["way"], "derived": True,
            }
    return out


def _live_bearing(rooms, frm, to):
    """The bearing the live room `frm` declares on its doorway to `to`."""
    from world.spatial import normalize_bearing
    for edge in (rooms.get(frm) or {}).get("adjacent") or ():
        if isinstance(edge, dict) and str(edge.get("to") or "") == to:
            return normalize_bearing(edge.get("dir"))
    return None


def _door_kind(barrier):
    """The solver's word for a doorway: `open` -- no leaf, the whole shared
    wall -- when the engine reads the barrier as an open way
    (`spatial.normalize_barrier`), else `door`. The plan's barrier itself is
    never rewritten; this only tells the solver which it is laying."""
    from world.spatial import normalize_barrier
    return "open" if normalize_barrier(barrier) == "open" else "door"


def _exposure(uid, specs, rooms):
    spec = (specs.get(uid) or (None, {}))[1] or {}
    word = str(spec.get("exposure") or (rooms.get(uid) or {}).get("exposure") or "")
    return word.strip().casefold()


def plan_buildings(specs, scene, *, held_open=(), max_rooms=LAYOUT_TIER_MAX_ROOMS):
    """Every planned building of two storeys or more, each with `refusal`
    None when the tier may lay it out and the reason in words when not.

    `specs` is `{uid: (name, planned)}` (`structure._planned_specs`), `scene`
    the frame's scene, `held_open` the frontier spaces the Writers' Room has
    yet to claim (`structure.provisional_room_ids`).

    One grouping, so no room is in two buildings: a room a stair touches, or
    one stated `enclosed`, may be part of a building; every stair between
    two rooms that may be storeys joins them, and a level join joins two such
    rooms of one structure. A group a stair runs through is a building. A
    room stated `open` or `sheltered` is never a storey
    (`STOREY_EXPOSURES`)."""
    from world.site_plan import normalize_site
    from world.spatial import normalize_level
    rooms = ((scene or {}).get("rooms") or {})
    edges = _edges_of(specs)
    structure_of = {uid: str((spec or {}).get("structure") or "") for uid, (_n, spec) in specs.items()}

    def may_be_storey(uid):
        return _exposure(uid, specs, rooms) in STOREY_EXPOSURES

    stair_rooms = {a for (a, b), rec in edges.items()
                   if rec["vertical"] and a in specs and b in specs
                   and structure_of[a] == structure_of[b]
                   and may_be_storey(a) and may_be_storey(b)}
    walled = {uid for uid in specs if _exposure(uid, specs, rooms) == WALLED}
    candidates = stair_rooms | walled
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for (a, b), rec in edges.items():
        if a not in candidates or b not in candidates or structure_of[a] != structure_of[b]:
            continue
        if rec["vertical"] and not (may_be_storey(a) and may_be_storey(b)):
            continue
        if rec["vertical"] or (a in walled or b in walled):
            parent[find(a)] = find(b)
    groups = {}
    for uid in list(parent):
        groups.setdefault(find(uid), set()).add(uid)
    out = []
    for members in groups.values():
        if not members & stair_rooms:
            continue
        structure = structure_of[next(iter(members))]
        out.append(_building(sorted(members), specs, rooms, edges, structure,
                             held_open=set(held_open or ()), max_rooms=max_rooms,
                             normalize_site=normalize_site, normalize_level=normalize_level))
    return sorted(out, key=lambda b: b["key"])


def _own_block(uid, joins, stairs, levels):
    """`{"beside": room, "side": side}` -- the room `uid` opens from and the
    side of it `uid` stands on -- when `uid` joins the building by exactly one
    doorway on its own storey with a side the plan states, and no stair; else
    None."""
    if any(uid in (s["low"], s["high"]) for s in stairs):
        return None
    mine = [j for j in joins if uid in (j["a"], j["b"])]
    if len(mine) != 1:
        return None
    (j,) = mine
    other = j["b"] if j["a"] == uid else j["a"]
    if levels.get(other) != levels.get(uid) or not j["side"]:
        return None
    side = j["side"] if j["a"] == other else _OPP.get(j["side"])
    return {"beside": other, "side": side} if side else None


def _on_a_plan(live, normalize_site, solved):
    """A live room's site when it stands on a plan a building may not be laid
    over: one decided -- solved, converted, placed by a host -- or one the
    derivation laid on a plan a decided site holds (`solved`), the frame of
    another building's solve. None for no site, or a derived one on a plan
    no decided site holds: the derivation's own reading of the stubs,
    recomputed every merge (`site_plan.site_is_derived`), which a solve laid
    onto the building replaces."""
    from world.site_plan import site_is_derived
    site = normalize_site(live.get("site"))
    if site is not None and site_is_derived(live.get("site")) and site["plan"] not in solved:
        return None
    return site


def _solved_plans(rooms, normalize_site) -> set:
    """The plans a decided site stands on, read off the live rooms."""
    from world.site_plan import site_is_derived
    return {normalize_site(room.get("site"))["plan"] for room in rooms.values()
            if isinstance(room, dict) and normalize_site(room.get("site"))
            and not site_is_derived(room.get("site"))}


def _building(members, specs, rooms, edges, structure, *, held_open, max_rooms,
              normalize_site, normalize_level):
    from world.spatial import opposite_bearing
    from world.spatial import WAYS
    names = {uid: str(specs[uid][0] or uid) for uid in members}
    plan = {uid: copy.deepcopy(specs[uid][1] or {}) for uid in members}
    building = {"key": "+".join(members), "rooms": members, "names": names,
                "specs": plan, "structure": structure, "refusal": None}
    solved = _solved_plans(rooms, normalize_site)
    # the storeys: stated where the plan or the scene states them, the rest
    # along the stairs from those
    levels = {}
    for uid in members:
        stated = normalize_level(plan[uid].get("level"))
        if stated is None:
            stated = normalize_level((rooms.get(uid) or {}).get("level"))
        if stated is not None:
            levels[uid] = stated
    outside = []
    for (a, b), rec in sorted(edges.items()):
        if a in members and b not in members:
            # A STAIR OUT OF THE BUILDING is a way it opens onto -- an outside
            # stair down to a walk, a ladder up to a roof -- and is laid as an
            # outside door of the storey it leaves from, like any other.
            back = edges.get((b, a)) or {}
            side = rec["dir"] if rec["dir"] in _SIDES and not rec.get("derived") else None
            if side is None and back.get("dir") in _SIDES and not back.get("derived"):
                side = opposite_bearing(back["dir"])
            if side is None:
                # the ground as the story has it: a developed street states
                # where the building stands from it in its own doorway
                side = opposite_bearing(_live_bearing(rooms, b, a))
                side = side if side in _SIDES else None
            entry = {"room": a, "to": b, "side": side, "barrier": rec["barrier"],
                     "name": str(((specs.get(b) or (None, {}))[0])
                                 or (rooms.get(b) or {}).get("name") or b)}
            if rec["vertical"]:
                entry["vertical"] = rec["vertical"]
            outside.append(entry)
    if not levels:
        start = outside[0]["room"] if outside else members[0]
        levels[start] = 0
    queue = list(levels)
    while queue:
        cur = queue.pop(0)
        for (a, b), rec in edges.items():
            if a != cur or b not in members:
                continue
            step = {"up": 1, "down": -1}.get(rec["vertical"], 0)
            want = levels[cur] + step
            if b not in levels:
                levels[b] = want
                queue.append(b)
            elif levels[b] != want:
                building["refusal"] = (f"the storeys disagree: {b} is on {levels[b]} and "
                                       f"{want} along its joins")
    building["levels"] = levels
    joins, stairs, seen = [], [], set()
    for (a, b), rec in sorted(edges.items()):
        if a not in members or b not in members or frozenset((a, b)) in seen:
            continue
        seen.add(frozenset((a, b)))
        if rec["vertical"]:
            low, high = (a, b) if levels.get(a, 0) < levels.get(b, 0) else (b, a)
            way = rec["way"] if rec["way"] in WAYS else ""
            if not way:
                way = (edges.get((b, a)) or {}).get("way") or ""
                way = way if way in WAYS else "stair"
            stairs.append({"low": low, "high": high, "way": way})
        else:
            side = rec["dir"] if rec["dir"] in _SIDES and not rec.get("derived") else None
            if side is None:
                back = edges.get((b, a)) or {}
                if back.get("dir") in _SIDES and not back.get("derived"):
                    side = opposite_bearing(back["dir"])
            joins.append({"a": a, "b": b, "side": side, "barrier": rec["barrier"]})
    building["joins"] = joins
    building["stairs"] = stairs
    building["outside"] = outside
    entrance = sorted(outside, key=lambda o: (bool(o.get("vertical")),
                                              abs(levels.get(o["room"], 0)), o["room"], o["to"]))
    building["entrance"] = entrance[0] if entrance else None
    building["plan"] = (f"{LAYOUT_PLAN_PREFIX}{entrance[0]['room']}" if entrance
                        else f"{LAYOUT_PLAN_PREFIX}{members[0]}")
    building["signature"] = hashlib.sha1(_canon(
        {"plan": plan, "outside": outside}).encode("utf-8")).hexdigest()[:16]
    refusal = building["refusal"]
    if refusal is None and len({levels.get(u) for u in members}) < 2:
        refusal = "one storey"
    if refusal is None and len(members) > max_rooms:
        refusal = f"{len(members)} rooms, over the {max_rooms} a building is laid out with"
    if refusal is None and not outside:
        refusal = "no room of it opens onto anything outside it"
    if refusal is None and any(s["way"] == "overlook" for s in stairs):
        refusal = "an overlook is a rail over a drop, not a stair the solver lays"
    if refusal is None and any(abs(levels[s["high"]] - levels[s["low"]]) != 1 for s in stairs):
        refusal = "a stair that does not join two neighbouring storeys"
    for uid in members:
        if refusal is not None:
            break
        live = rooms.get(uid)
        if uid in held_open:
            refusal = f"{uid} is a frontier space the Room has yet to claim"
        elif isinstance(live, dict) and str(live.get("desc") or live.get("description") or "").strip():
            refusal = f"{uid} is described: a room the story has seen is never re-measured"
        elif normalize_site(plan[uid].get("site")) or (isinstance(live, dict)
                                                       and _on_a_plan(live, normalize_site,
                                                                      solved)):
            # A SITE THE DERIVATION WROTE IS NO PLAN ALREADY: it is the
            # engine's reading of the stubs, recomputed every merge
            # (`site_plan.DERIVED_KEY`), and a solve laid onto the building's
            # rooms replaces it -- unless it stands in another solve's frame,
            # where a second solve would pull the ground that building opens
            # onto off its plan. A decided site -- a solve, the lab's
            # converter, a host -- keeps the building out, as before.
            refusal = f"{uid} stands on a plan already"
        elif plan[uid].get("parent_entity") or (isinstance(live, dict) and live.get("parent_entity")):
            refusal = f"{uid} is the inside of something"
        elif str(plan[uid].get("shape") or SOLVED_SHAPE).strip().casefold() != SOLVED_SHAPE:
            # A ROOM OF ANOTHER SHAPE THAT OPENS INTO THE BUILDING BY ONE
            # DOORWAY STANDS IN A BLOCK OF ITS OWN beside the room it opens
            # from, on the side the plan states -- the layout lab's own hand
            # edit to the shrine the owner liked ("Seal Cavern added as a
            # room of its own block beyond the basement's north wall"), made
            # by the engine. The solve says where it stands and how large --
            # from what it holds, like every room -- and its shape stays the
            # plan's (`planned_layout`): a round room keeps its curve inside
            # the solved box and is never squared. One built from `parts`
            # the plan places inside its box cannot be re-boxed, and one
            # joined any other way -- by a stair, or to two rooms -- still
            # keeps its building out.
            from world.spatial import normalize_parts
            block = (None if normalize_parts(plan[uid].get("parts"))
                     else _own_block(uid, joins, stairs, levels))
            if block is None:
                refusal = (f"{uid} is planned {plan[uid]['shape']}, and the solver lays "
                           f"{SOLVED_SHAPE}s")
            else:
                building.setdefault("own_blocks", {})[uid] = block
    if refusal is None:
        # A SOLVE IS WRITTEN ONLY ONTO A PLAN NOTHING ELSE STANDS ON. A room
        # outside the building standing on the plan this solve would write --
        # the street a building laid out before was re-planned from, placed
        # beside it by the engine's derivation -- stands where the OLD solve's
        # coordinates put it; a new solve's are its own, and written onto the
        # same plan the two would be read as one frame. Laying a solve onto a
        # standing plan, where its ground already stands, is the town fabric's
        # work (survey rank 7); until then the building fails open. A room
        # the derivation put on a plan no decided site holds any more is no
        # holder: since 2026-10-09 its site is recomputed every merge from
        # the decided sites, so it never keeps an old solve's coordinates
        # (`site_plan.DERIVED_KEY`) -- a re-planned building, whose stubs gave
        # their solve back, is laid out again.
        holder = next((rid for rid, live in sorted(rooms.items())
                       if rid not in building["rooms"] and isinstance(live, dict)
                       and (_on_a_plan(live, normalize_site, solved) or {}).get("plan")
                       == building["plan"]), None)
        if holder is not None:
            refusal = (f"{holder} already stands on {building['plan']}, placed beside "
                       f"an earlier solve: a new solve there would read two frames as one")
    building["refusal"] = refusal
    return building


# ---------------------------------------------------------------- payloads

def sort_payload(building):
    """What the first call reads: the building as the plan holds it."""
    rooms = []
    for uid in building["rooms"]:
        spec = building["specs"][uid]
        anchors = spec.get("anchors") if isinstance(spec.get("anchors"), dict) else {}
        joined = [j["b"] if j["a"] == uid else j["a"] for j in building["joins"]
                  if uid in (j["a"], j["b"])]
        rooms.append({
            "id": uid, "name": building["names"][uid], "level": building["levels"].get(uid, 0),
            "purpose": _text(spec.get("purpose"), 600),
            "joins": [{"to": o, "name": building["names"][o]} for o in joined]
            + [{"to": o["to"], "name": o["name"], "outside": True}
               for o in building["outside"] if o["room"] == uid],
            "stairs": [{"to": s["high"] if s["low"] == uid else s["low"],
                        "goes": "up" if s["low"] == uid else "down", "way": s["way"]}
                       for s in building["stairs"] if uid in (s["low"], s["high"])],
            "fixtures": [{"id": aid, "desc": _text((a or {}).get("desc"), 300)}
                         for aid, a in anchors.items() if isinstance(a, dict)],
        })
    out = {"building": {"name": building["names"].get((building["entrance"] or {}).get("room"))
                        or building["names"][building["rooms"][0]], "rooms": rooms}}
    # WHAT THE STORY'S LORE SAYS OF IT (`director_layout.building_description`),
    # where the tier found any: the fixtures, windows and floors a room's
    # one-line purpose leaves out, and the solver sizes a room by what it holds.
    if str(building.get("description") or "").strip():
        out["building"]["description"] = str(building["description"]).strip()
    return out


def _plan_anchors(building, uid):
    """The fixtures the plan lists for one room, `{id: record}`."""
    anchors = building["specs"][uid].get("anchors")
    return {str(aid): a for aid, a in anchors.items() if isinstance(a, dict)} \
        if isinstance(anchors, dict) else {}


def _ways_of(building, uid):
    """The rooms a way out of `uid` leads to: the building's own doorways
    and stairs, and the ground it opens onto."""
    out = {j["b"] if j["a"] == uid else j["a"] for j in building["joins"]
           if uid in (j["a"], j["b"])}
    out |= {s["high"] if s["low"] == uid else s["low"] for s in building["stairs"]
            if uid in (s["low"], s["high"])}
    out |= {o["to"] for o in building["outside"] if o["room"] == uid}
    return out


def hold_inventory(building, answer):
    """The first call's answer held to the plan: the plan's rooms only, each
    under its own id; a fixture id made an anchor id; the plan's stairs, each
    once, with what the answer said of it.

    THE PLAN'S FIXTURES ARE THE PLAN'S, as its rooms are. Each keeps its id
    as a fixture, a window or a mark, never as a zone -- a zone is no anchor,
    and a fixture whose id went to one was written nowhere; the zone takes an
    id of its own. One the answer leaves out, or files only as a zone, is
    RESTORED: kept as the plan holds it -- its own record, unpinned, and never
    handed to the solver -- and listed (`restored`), so it is counted and
    nothing about it is decided by code. Making it a floor thing of a middling
    size for the solver to place decided what it is: a gable window, or the
    place where people wait at the foot of a stair, became a waist-high
    obstacle pinned in the room (review of 2026-10-08, R2-2; F3 before it:
    a hearth the answer dropped was never placed and never counted). A
    fixture given with `marks` -- a room this one has a way to -- is no thing
    in the room but the place where that way meets it, kept apart from what
    the solver places (`marks`)."""
    answer = answer if isinstance(answer, dict) else {}
    plan_rooms = set(building["rooms"])
    plan_ids = {uid: set(_plan_anchors(building, uid)) for uid in building["rooms"]}
    rooms = {}

    def fresh(uid):
        return {"id": uid, "fixtures": [], "zones": [], "windows": [], "marks": [],
                "restored": []}

    for raw in answer.get("rooms") or ():
        if not isinstance(raw, dict) or str(raw.get("id") or "") not in plan_rooms:
            continue
        uid = str(raw["id"])
        held = rooms.setdefault(uid, fresh(uid))
        used = {item["id"] for key in ("fixtures", "zones", "windows", "marks")
                for item in held[key]}
        ways = _ways_of(building, uid)
        # fixtures and windows before zones: a plan's fixture keeps its id
        for key in ("fixtures", "windows", "zones"):
            for item in raw.get(key) or ():
                if not isinstance(item, dict):
                    continue
                given = str(item.get("id") or "")
                keep = given in plan_ids[uid] and key != "zones"
                fid = given if keep else _slug(given or item.get("name") or key)
                # only an entry given under a plan fixture's own id is that
                # fixture: a zone, or a new entry whose words fold onto one,
                # takes an id of its own
                if not fid or fid in used or (not keep and fid in plan_ids[uid]):
                    fid = f"{fid or key}_{len(used) + 1}"
                used.add(fid)
                entry = {"id": fid, "name": _text(item.get("name") or item.get("faces") or fid),
                         "why": _text(item.get("why"), 300)}
                if key == "fixtures":
                    marks = str(item.get("marks") or "").strip()
                    if marks and marks in ways:
                        held["marks"].append(dict(entry, to=marks))
                        continue
                    entry["mount"] = _text(item.get("mount") or "floor", 80)
                    entry["count"] = max(1, min(FIXTURE_COUNT_MAX, _int(item.get("count"), 1)))
                    entry["implied"] = bool(item.get("implied"))
                if key == "windows":
                    entry["faces"] = _text(item.get("faces"), 200)
                    entry["count"] = max(1, min(WINDOW_COUNT_MAX, _int(item.get("count"), 1)))
                held[key].append(entry)
    for uid in building["rooms"]:
        held = rooms.setdefault(uid, fresh(uid))
        given = {item["id"] for key in ("fixtures", "windows", "marks") for item in held[key]}
        for aid, anchor in _plan_anchors(building, uid).items():
            if aid not in given:
                held["restored"].append({"id": aid, "name": _text(anchor.get("desc") or aid)})
    said = {}
    for raw in answer.get("stairs") or ():
        if isinstance(raw, dict):
            said[frozenset((str(raw.get("from") or ""), str(raw.get("to") or "")))] = raw
    stairs = []
    for s in building["stairs"]:
        raw = said.get(frozenset((s["low"], s["high"]))) or {}
        stairs.append({"from": s["low"], "to": s["high"], "way": s["way"],
                       "enclosed": bool(raw.get("enclosed")) and s["way"] == "stair",
                       "door": _text(raw.get("door"), 80)})
    return {"rooms": [rooms[uid] for uid in building["rooms"]], "stairs": stairs}


def relate_payload(building, inventory):
    """What the second call reads: the building, what the first sorted each
    room to hold, what the plan already fixes, and the vocabularies. A mark
    is the engine's to place where its way meets the room, so the second
    call is not handed one to relate."""
    fixed = {"joins": [{"from": j["a"], "to": j["b"], "side": j["side"]}
                       for j in building["joins"] if j["side"]]
             + [{"from": o["room"], "to": o["to"], "side": o["side"], "outside": True}
                for o in building["outside"] if o["side"]]}
    entrance = building["entrance"] or {}
    if entrance.get("side"):
        fixed["front"] = entrance["side"]
    fixed["entrance"] = {"room": entrance.get("room"), "opens_onto": entrance.get("to")}
    shown = {"rooms": [{"id": r["id"],
                        "fixtures": list(r.get("fixtures") or ()),
                        "zones": list(r.get("zones") or ()),
                        "windows": list(r.get("windows") or ())}
                       for r in inventory.get("rooms") or ()],
             "stairs": list(inventory.get("stairs") or ())}
    out = sort_payload(building)
    out.update(inventory=shown, fixed=fixed, vocabulary=vocabulary())
    return out


def _area(value):
    """A floor area in square metres: a positive finite number, else None."""
    if isinstance(value, bool):
        return None
    try:
        area = float(value)
    except (TypeError, ValueError):
        return None
    return round(area, 2) if math.isfinite(area) and area > 0 else None


def _int(value, default=0):
    if isinstance(value, bool):
        return default
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def _side(value):
    word = str(value or "").strip().casefold()[:1]
    return word if word in _SIDES else None


# ---------------------------------------------------------------- the spec

def spec_from_answers(building, inventory, answer):
    """The solver's spec: the plan's rooms, storeys, joins and stairs, with
    the relations the second call wrote wherever the plan leaves them open,
    every word held to its closed set."""
    answer = answer if isinstance(answer, dict) else {}
    vocab = vocabulary()
    purposes, kinds = set(vocab["purposes"]), set(vocab["fixture_kinds"])
    sizes, zone_sizes = set(vocab["sizes"]), set(vocab["zone_sizes"])
    places = set(vocab["places"]) | {"walls"}
    stair_kinds = set(vocab["stair_kinds"])
    said = {str(r.get("id")): r for r in answer.get("rooms") or () if isinstance(r, dict)}
    held = {r["id"]: r for r in inventory.get("rooms") or ()}
    entrance = building["entrance"] or {}
    front = entrance.get("side") or _side(answer.get("front")) or "s"
    rooms = []
    for uid in building["rooms"]:
        spec = building["specs"][uid]
        mine = said.get(uid) or {}
        sorted_ = held.get(uid) or {"fixtures": [], "zones": [], "windows": []}
        purpose = str(mine.get("purpose") or "").strip().casefold().replace(" ", "_")
        room = {"id": uid, "name": building["names"][uid], "level": building["levels"].get(uid, 0),
                "purpose": purpose if purpose in purposes else "other"}
        if uid in (building.get("own_blocks") or {}):
            room["block"] = uid
        # A ROOM IS SIZED FROM WHAT IT HOLDS (`layout_solver.room_target`),
        # aimed at a size only where the story's own lore states one. The
        # plan's `extent` is the Writers' Room's estimate and never reaches
        # the solver: the owner's ruling of 2026-10-10, "size from contents,
        # like the lab" -- chat 164's Room planned the shrine at sizes no
        # compact building holds (Hinami's room 36 m2 against the lore's six
        # mats), and the quarter the solve was held to turned most real plans
        # away. With no description there is no lore to state a size, so an
        # area an answer gives then is the model's own estimate, dropped.
        described = _area(mine.get("area_m2")) if building.get("description") else None
        if described:
            room["area_m2"] = described
        # joins: the plan's, sided by the plan where it says, else by the answer
        asked = {}
        for j in mine.get("joins") or ():
            if isinstance(j, dict):
                asked[str(j.get("to") or "")] = j
        joins = []
        own_blocks = building.get("own_blocks") or {}
        for j in building["joins"]:
            if uid not in (j["a"], j["b"]):
                continue
            other = j["b"] if j["a"] == uid else j["a"]
            # each join written once: from its first room -- except a room in
            # a block of its own, which carries its own doorway (the lab's
            # shrine wrote the cavern's door on the cavern), since the solver
            # cuts a door between blocks from the block's side
            writer = j["b"] if j["b"] in own_blocks else (
                j["a"] if j["a"] in own_blocks else j["a"])
            if writer != uid:
                continue
            if j["a"] != uid:
                side = _OPP.get(j["side"]) if j["side"] else None
                side = side or _side((asked.get(other) or {}).get("side"))
                entry = {"to": other, "kind": _door_kind(j["barrier"])}
                if side:
                    entry["side"] = side
                if j["side"]:
                    entry["held"] = True
                joins.append(entry)
                continue
            side = j["side"] or _side((asked.get(other) or {}).get("side"))
            if side is None and other in said:
                back = next((x for x in said[other].get("joins") or ()
                             if isinstance(x, dict) and str(x.get("to") or "") == uid), None)
                side = _OPP.get(_side((back or {}).get("side")))
            entry = {"to": other, "kind": _door_kind(j["barrier"])}
            if side:
                entry["side"] = side
            if j["side"]:
                # the PLAN's side: the solver weighs losing it as the
                # refusal it is (`layout_solver._held`)
                entry["held"] = True
            order = _int((asked.get(other) or {}).get("order"))
            if order > 0:
                entry["order"] = order
            joins.append(entry)
        for o in building["outside"]:
            if o["room"] != uid or (entrance and o["to"] == entrance.get("to")
                                    and uid == entrance.get("room")):
                continue
            side = o["side"] or _side((asked.get(o["to"]) or {}).get("side"))
            entry = {"to": o["to"], "kind": _door_kind(o["barrier"])}
            if side:
                entry["side"] = side
            joins.append(entry)
        room["joins"] = joins
        zone_ids = {z["id"] for z in sorted_.get("zones") or ()}
        zones = []
        for z in mine.get("zones") or ():
            if not isinstance(z, dict) or str(z.get("id") or "") not in zone_ids:
                continue
            zone = {"id": str(z["id"]), "name": next((x["name"] for x in sorted_["zones"]
                                                      if x["id"] == str(z["id"])), str(z["id"]))}
            at = str(z.get("at") or "").strip().casefold()
            if at in places and at != "walls":
                zone["at"] = at
            if str(z.get("by") or "") == "entrance" and uid == entrance.get("room"):
                zone["by"] = "entrance"
            size = str(z.get("size") or "").strip().casefold()
            if size in zone_sizes:
                zone["size"] = size
            zones.append(zone)
        for z in sorted_.get("zones") or ():
            if z["id"] not in {x["id"] for x in zones}:
                # a zone the sort named is never lost: laid where it fits
                zones.append({"id": z["id"], "name": z["name"]})
        room["zones"] = zones
        window_ids = {w["id"] for w in sorted_.get("windows") or ()}
        windows = []
        for w in mine.get("windows") or ():
            if isinstance(w, dict) and str(w.get("id") or "") in window_ids:
                windows.append({"id": str(w["id"]), "side": _side(w.get("side")),
                                "count": max(1, min(WINDOW_COUNT_MAX, _int(w.get("count"), 1)))})
        for w in sorted_.get("windows") or ():
            if w["id"] not in {x["id"] for x in windows}:
                windows.append({"id": w["id"], "side": None, "count": w.get("count", 1)})
        sorted_names = {w["id"]: w.get("name") for w in sorted_.get("windows") or ()}
        for w in windows:
            w["name"] = sorted_names.get(w["id"]) or w["id"]
        room["windows"] = windows
        sorted_fx = {f["id"]: f for f in sorted_.get("fixtures") or ()}
        ids = set(sorted_fx) | {w["id"] for w in windows}
        fixtures = []
        for f in mine.get("fixtures") or ():
            if not isinstance(f, dict) or str(f.get("id") or "") not in sorted_fx:
                continue
            base = sorted_fx[str(f["id"])]
            fx = {"id": base["id"], "name": base["name"]}
            kind = str(f.get("kind") or "").strip().casefold().replace(" ", "_")
            size = str(f.get("size") or "").strip().casefold()
            if kind in kinds:
                fx["kind"] = kind
                if size in sizes:
                    fx["size"] = size
            else:
                # a thing no listed kind is: its size word, never a guess
                fx["kind"] = ""
                fx["size"] = size if size in sizes else "medium"
            at = str(f.get("at") or "").strip().casefold()
            if at in places:
                fx["at"] = at
            if str(f.get("in") or "") in zone_ids:
                fx["in"] = str(f["in"])
            mount = _mount(base.get("mount"), ids)
            if mount != "floor":
                fx["mount"] = mount
            if base.get("count", 1) > 1:
                fx["count"] = base["count"]
            for rel in ("near", "beside", "facing"):
                if str(f.get(rel) or "") in ids:
                    fx[rel] = str(f[rel])
            fixtures.append(fx)
        for fid, base in sorted_fx.items():
            if fid not in {x["id"] for x in fixtures}:
                # a thing the sort named is never lost: placed as its size
                fx = {"id": fid, "name": base["name"], "kind": "", "size": "medium"}
                mount = _mount(base.get("mount"), ids)
                if mount != "floor":
                    fx["mount"] = mount
                if base.get("count", 1) > 1:
                    fx["count"] = base["count"]
                fixtures.append(fx)
        room["fixtures"] = fixtures
        rooms.append(room)
    stairs = []
    said_stairs = {}
    for raw in answer.get("stairs") or ():
        if isinstance(raw, dict):
            said_stairs[frozenset((str(raw.get("from") or ""), str(raw.get("to") or "")))] = raw
    for s in inventory.get("stairs") or ():
        raw = said_stairs.get(frozenset((s["from"], s["to"]))) or {}
        low, high = s["from"], s["to"]
        stair = {"id": f"{low}__{high}", "name": _text(raw.get("name"), 80) or s["way"],
                 "from": low, "to": high, "enclosed": bool(s.get("enclosed")),
                 "door": s.get("door") or "door"}
        # which end is which in the answer
        if str(raw.get("from") or "") == low:
            at_low, at_high = _side(raw.get("from_at")), _side(raw.get("to_at"))
        else:
            at_low, at_high = _side(raw.get("to_at")), _side(raw.get("from_at"))
        if at_low:
            stair["from_at"] = at_low
        if at_high:
            stair["to_at"] = at_high
        if s["way"] in ("ladder", "hatch"):
            stair["kind"] = "ladder"
        else:
            kind = str(raw.get("kind") or "").strip().casefold()
            if kind in stair_kinds and kind != "ladder":
                stair["kind"] = kind
        stairs.append(stair)
    smaller = []
    for st in answer.get("storeys") or ():
        if isinstance(st, dict) and st.get("smaller") and _int(st.get("level"), 0) > 0:
            smaller.append({"level": _int(st.get("level")), "smaller": True})
    grounds = {"areas": [{"id": o["to"], "name": o["name"], "kind": "yard",
                          "where": o["side"] or "around"}
                         for o in _unique_outside(building)]}
    return {"name": building["names"].get(entrance.get("room")) or building["names"][building["rooms"][0]],
            "front": front,
            "entrance": {"room": entrance.get("room"),
                         "kind": _door_kind(entrance.get("barrier"))} if entrance else {},
            "storeys": smaller, "rooms": rooms, "stairs": stairs, "grounds": grounds,
            **({"blocks": [{"id": uid, "apart": False,
                            "beside": {"block": "main", "side": block["side"]}}
                           for uid, block in sorted((building.get("own_blocks") or {}).items())]}
               if building.get("own_blocks") else {})}


def _unique_outside(building):
    seen, out = set(), []
    for o in building["outside"]:
        if o["to"] not in seen:
            seen.add(o["to"])
            out.append(o)
    return out


def _mount(value, ids):
    word = str(value or "floor").strip().casefold()
    head, _, rest = word.partition(" ")
    if head in ("hung", "ceiling"):
        return head
    if head in ("in", "on") and rest.strip() in ids:
        return f"{head} {rest.strip()}"
    return "floor"


# ---------------------------------------------------------------- the solve

def solve_spec(spec):
    """The solver's layout for a spec (`world.layout_solver.solve`)."""
    return solve(spec)


def solve_for(building, spec):
    """`(layout, refusals)`: the solve that stands for the plan, over
    `LAYOUT_SOLVE_SEEDS` seeds of the solver's search taken in order from its
    own (`layout_solver.SEED`). One whose every stair lands in each room it
    joins (`unlanded`) is taken at once; failing that, the first the bridge
    does not refuse; failing every seed, the first seed's solve and its
    refusals, the building failing open as before. Each seed is
    deterministic, so a building solves the same way every time, and a seed
    after the first is tried only where the first fell short.

    The owner's shrine (chat 164, 2026-10-10), replicated: of twenty seeds,
    one answer set laid out with no refusal on fifteen, another on thirteen
    and a third, after its cross-block door was weighed as the refusal it
    is, on fifteen -- the solver's own seed among the failures more than
    once. A building refused on one seed but not on most is a building the
    search missed, not one the plan cannot hold."""
    from world.layout_solver import SEED
    first = standing = None
    for k in range(LAYOUT_SOLVE_SEEDS):
        layout = solve(spec, seed=SEED + k)
        refused = refusals(building, spec, layout)
        first = first or (layout, refused)
        if refused:
            continue
        if not unlanded(spec, layout):
            return layout, refused
        standing = standing or (layout, refused)
    return standing or first


def unlanded(spec, layout):
    """`[(stair id, room)]` for every end of a stair whose hall the solve
    gave no doorway onto the room it joins: the plan's stair then has no
    landing there (`planned_layout` pins none, and the room's designer
    places it). Read off the layout's doors, never its warnings."""
    halls_of = {}
    for well in layout.stairwells:
        for flight in well.get("flights") or ():
            halls_of[flight] = set((well.get("halls") or {}).values())
    pairs = {frozenset((d["a"], d["b"])) for d in layout.doors if not d.get("outside")}
    return [(st["id"], room) for st in spec.get("stairs") or () for room in (st["from"], st["to"])
            if not any(frozenset((hall, room)) in pairs for hall in halls_of.get(st["id"], ()))]


def refusals(building, spec, layout):
    """Why this solve cannot stand for the plan, in words; empty when it can.
    Read off the layout's structure, never its warning sentences."""
    out = list(check(layout))
    placed = {}
    for lv, floor in layout.floors.items():
        for rid, rects in floor.items():
            placed[rid] = (lv, rects[0])
    for uid in building["rooms"]:
        if uid not in placed:
            out.append(f"{uid} found no floor")
        elif placed[uid][0] != building["levels"].get(uid, 0):
            out.append(f"{uid} stands on storey {placed[uid][0]}, not {building['levels'].get(uid, 0)}")
    halls = {}
    for well in layout.stairwells:
        for flight in well.get("flights") or ():
            halls[flight] = well
    for st in spec.get("stairs") or ():
        if st["id"] not in halls:
            out.append(f"the stair between {st['from']} and {st['to']} found no room")
    pairs = {frozenset((d["a"], d["b"])) for d in layout.doors}
    for j in building["joins"]:
        if building["levels"].get(j["a"]) == building["levels"].get(j["b"]) \
                and frozenset((j["a"], j["b"])) not in pairs:
            out.append(f"{j['a']} and {j['b']} were to join and share no doorway")
    entrance = building["entrance"] or {}
    outs = {(d["a"], d["b"]) for d in layout.doors if d.get("outside")}
    for o in building["outside"]:
        target = "entrance" if (o["room"] == entrance.get("room") and o["to"] == entrance.get("to")) \
            else o["to"]
        if (o["room"], target) not in outs:
            out.append(f"{o['room']} has no doorway onto {o['to']}")
    # A ROOM'S SIZE IS NEVER A REFUSAL: the plan's `extent` is the Writers'
    # Room's estimate, which the solve replaces, filed beside it
    # (`planned_layout`; the owner's ruling of 2026-10-10). Until then a
    # solve a quarter off a planned size or side was refused (F47, review of
    # 2026-10-08 F2), and on the owner's shrine that was nearly every room.
    # A SIDE THE PLAN STATES IS A FACT THE PLAN MADE: the
    # solver may put a doorway on another wall when its arrangement cannot
    # honour the one asked (it records a warning and goes on), and written
    # back that would re-bear the plan's own edge without a word
    for j in building["joins"]:
        if not j["side"] or building["levels"].get(j["a"]) != building["levels"].get(j["b"]):
            continue
        got = _door_side(layout, j["a"], j["b"])
        if got and got != j["side"]:
            out.append(f"{j['b']} was planned through the {j['side']} wall of {j['a']} "
                       f"and the solve put it through the {got}")
    for o in building["outside"]:
        if not o["side"]:
            continue
        got = _outside_side(layout, building, o)
        if got and got != o["side"]:
            out.append(f"{o['room']} was planned to open onto {o['to']} through its "
                       f"{o['side']} wall and the solve opened it through the {got}")
    return out


def _stated_sides(planned):
    """`(w, d)` in paces the plan stated for a room, or None."""
    stated = planned.get("extent") if isinstance(planned, dict) else None
    if not isinstance(stated, dict):
        return None
    w, d = _int(stated.get("w")), _int(stated.get("d"))
    return (w, d) if w > 0 and d > 0 else None


def _door_side(layout, a, b):
    """The wall of `a` its doorway into `b` is in, or None when there is
    none (`layout_solver._place_doors`)."""
    for d in layout.doors:
        if d.get("outside"):
            continue
        if d["a"] == a and d["b"] == b:
            return d["side"]
        if d["a"] == b and d["b"] == a:
            return _OPP[d["side"]]
    return None


def _outside_side(layout, building, o):
    """The wall a building room opens onto the ground outside through."""
    entrance = building["entrance"] or {}
    target = "entrance" if (o["room"] == entrance.get("room") and o["to"] == entrance.get("to")) \
        else o["to"]
    for d in layout.doors:
        if d.get("outside") and d["a"] == o["room"] and d["b"] == target:
            return d["side"]
    return None


def _flush(room, rect, side):
    return {"n": rect.y == room.y, "s": rect.y + rect.d == room.y + room.d,
            "w": rect.x == room.x, "e": rect.x + rect.w == room.x + room.w}[side]


def _stands_at(room, rect, at, kind):
    """Does a fixture placed at `rect` stand where the model put it (`at`):
    against that wall, or one pace off it where it keeps an aisle behind
    (`layout_solver.USE_SPACE`); in that corner; clear of every wall for
    `middle`; anywhere when it was given no place."""
    from world.layout_solver import USE_SPACE
    if at in _SIDES:
        back = USE_SPACE.get(kind, (0, 0))[1]
        if _flush(room, rect, at):
            return True
        if back:
            dx, dy = _STEP[at]
            grown = type(rect)(rect.x + min(0, dx * back), rect.y + min(0, dy * back),
                               rect.w + abs(dx) * back, rect.d + abs(dy) * back)
            return _flush(room, grown, at)
        return False
    if at in _CORNERS:
        return _flush(room, rect, at[7]) and _flush(room, rect, at[8])
    if at == "middle":
        # standing free is a place too: the solver's own move when it puts a
        # thing asked for the middle against a wall (`_place_fixtures`)
        return not any(_flush(room, rect, s) for s in _SIDES)
    return True


def _offset(rect, side, cell):
    """A one-cell doorway's place along its wall as `normalize_offset`
    reads it -- the cell's distance from the wall's start (west for a north
    or south wall, north for an east or west one) over the places the wall
    leaves (`tools/site_plan_from_layout._offset`)."""
    if side in ("n", "s"):
        return round((cell[0] - rect.x) / max(1, rect.w - 1), 4)
    return round((cell[1] - rect.y) / max(1, rect.d - 1), 4)


def _written_id(uid, fid, asked, plan_ids):
    """The anchor id a solved fixture is written under. The solver names
    several alike `<id>_1`, `<id>_2`... (`layout_solver._sort_fixtures`);
    when the plan named them under `<id>`, the first is written under the
    plan's own id, so the plan's record is that fixture rather than a
    stand-in left beside its copies (review of 2026-10-08, F3: the Rooms to
    Let held four box-bed anchors for three beds)."""
    if (uid, fid) in asked:
        return fid
    base, _, index = fid.rpartition("_")
    if index == "1" and base in plan_ids and int((asked.get((uid, base)) or {}).get("count") or 1) > 1:
        return base
    return fid


def _split_base(uid, fid, asked, plan_ids):
    """The plan's id when the solved fixture `fid` is one of several alike
    the plan named under that one record (`count` above 1), else None."""
    if (uid, fid) in asked:
        return None
    base, _, index = fid.rpartition("_")
    if index.isdigit() and base in plan_ids \
            and int((asked.get((uid, base)) or {}).get("count") or 1) > 1:
        return base
    return None


def _way_cells(layout, rects, landing, shaft_of, spec, uid, to, entrance_to=None):
    """`(cell, wall)` where the way from `uid` to `to` meets `uid`, in the
    room's own cells -- the stair's landing (`landing`), the doorway's cell
    -- or None when the solve holds no such way. The entrance door is the
    solver's `entrance`, the way onto `entrance_to`."""
    for st in spec.get("stairs") or ():
        if {st["from"], st["to"]} == {uid, to}:
            spot = landing.get((shaft_of.get(st["id"]), uid))
            if spot is not None:
                return spot
    room = rects[uid]
    for door in layout.doors:
        a, b, side, cell = door["a"], door["b"], door["side"], door["cell"]
        if door.get("outside"):
            if a != uid or (entrance_to if b == "entrance" else b) != to:
                continue
        elif b == uid and a == to:
            dx, dy = _STEP[side]
            side, cell = _OPP[side], (cell[0] + dx, cell[1] + dy)
        elif not (a == uid and b == to):
            continue
        return [cell[0] - room.x, cell[1] - room.y], side
    return None


def planned_layout(building, spec, layout, *, turn=None, inventory=None):
    """The solve as the plan's own geometry: `({uid: {"geometry", "anchors",
    "edges", "layout"}}, report)` for `structure.write_planned_layout`, and
    the report of what was moved, left unplaced and measured. `inventory`
    (`hold_inventory`) gives the marks to pin where their ways meet their
    rooms."""
    from world.site_plan import STOREY_M
    from world.spatial import footprint_for_extent, opposite_bearing
    rects, levels = {}, {}
    for lv, floor in layout.floors.items():
        for rid, rs in floor.items():
            rects[rid], levels[rid] = rs[0], lv
    out, report = {}, {"plan": building["plan"], "moved": [], "unplaced": [],
                       "stated": [], "described": [], "marks": [], "restored": [],
                       "split": [], "warnings": list(layout.warnings)}
    spec_rooms = {r["id"]: r for r in spec.get("rooms") or ()}
    for uid in building["rooms"]:
        r = rects[uid]
        geometry = {"extent": {"w": r.w, "d": r.d}, "shape": SOLVED_SHAPE, "level": levels[uid],
                    "site": {"plan": building["plan"], "x": r.x, "y": r.y,
                             "elev_m": round(levels[uid] * STOREY_M, 2)}}
        if uid in (building.get("own_blocks") or {}):
            # its own block: where it stands and how large are the solve's,
            # its shape the plan's -- never squared
            geometry.pop("shape")
        out[uid] = {"geometry": geometry, "anchors": {}, "edges": {},
                    "record": {"moved": [], "unplaced": []}}
        stated = _stated_sides(building["specs"][uid])
        if stated is not None:
            # THE PLAN'S ESTIMATE IS FILED AGAINST THE SOLVE: the Room's own
            # numbers are written over by the solve's (the owner's ruling of
            # 2026-10-10), and this is where they are still read.
            entry = {"room": uid, "stated": {"w": stated[0], "d": stated[1]},
                     "solved": {"w": r.w, "d": r.d}}
            report["stated"].append(entry)
            out[uid]["record"]["stated"] = {"w": stated[0], "d": stated[1]}
        described = (spec_rooms.get(uid) or {}).get("area_m2")
        if described:
            # a size the lore states: aimed at, and filed against the solve
            # however near it came -- the solver never sizes a room below
            # what it holds (`layout_solver.room_target`)
            report["described"].append({"room": uid, "area_m2": described,
                                        "solved": {"w": r.w, "d": r.d}})
            out[uid]["record"]["described_m2"] = described
    # FIXTURES: pinned where they stand as asked; never pinned where the
    # solver moved them or could not place them
    asked = {}
    for uid, sroom in spec_rooms.items():
        for f in sroom.get("fixtures") or ():
            asked[(uid, f["id"])] = f
    plan_ids = {uid: set(_plan_anchors(building, uid)) for uid in building["rooms"]}
    placed_ids = set()
    # SEVERAL ALIKE THE PLAN NAMED UNDER ONE RECORD: {(room, plan id): the
    # anchor ids its copies are written under}
    splits = {}
    for uid in building["rooms"]:
        room = rects[uid]
        for f in layout.fixtures.get(uid) or ():
            fid = str(f["id"])
            base_id = fid.rpartition("_")[0] if (uid, fid) not in asked and "_" in fid else fid
            src = asked.get((uid, fid)) or asked.get((uid, base_id)) or {}
            aid = _written_id(uid, fid, asked, plan_ids[uid])
            split_of = _split_base(uid, fid, asked, plan_ids[uid])
            if split_of:
                splits.setdefault((uid, split_of), []).append(aid)
            # the solver's own record of where each copy was asked: several
            # alike round the walls are each given one (`_sort_fixtures`)
            at = str(f.get("at") or src.get("at") or "").casefold()
            rect = f["rect"]
            placed_ids.add((uid, fid))
            kind = str(src.get("kind") or "").strip().casefold().replace(" ", "_")
            if at and at != "walls" and not _stands_at(room, rect, at, kind):
                stands = [s for s in _SIDES if _flush(room, rect, s)] or ["middle"]
                anchor = {"desc": f.get("name") or aid,
                          "footprint": footprint_for_extent(rect.w, rect.d), "height": f["height"]}
                if at in _SIDES:
                    anchor["dir"] = at
                elif at in _CORNERS:
                    anchor["dir"] = at[7:]
                out[uid]["anchors"][aid] = anchor
                moved = {"room": uid, "anchor": aid, "name": f.get("name") or aid,
                         "asked": at, "solver_put_it": "/".join(stands)}
                report["moved"].append(moved)
                out[uid]["record"]["moved"].append(moved)
                continue
            flush = [s for s in _SIDES if _flush(room, rect, s)]
            if at in _SIDES:
                side = at
            elif at in _CORNERS:
                side = at[7:]
            else:
                side = flush[0] if len(flush) == 1 else None
            anchor = {"desc": f.get("name") or aid,
                      "cell": [rect.x - room.x, rect.y - room.y],
                      "extent": {"w": rect.w, "d": rect.d},
                      "footprint": footprint_for_extent(rect.w, rect.d),
                      "height": f["height"]}
            if side:
                anchor["dir"] = side
            out[uid]["anchors"][aid] = anchor
        for f in (spec_rooms.get(uid) or {}).get("fixtures") or ():
            mount = str(f.get("mount") or "floor")
            if mount != "floor":
                continue                     # on a wall, from the ceiling, in a fixture
            count = int(f.get("count") or 1)
            copies = [f["id"]] if count == 1 else [f"{f['id']}_{i + 1}" for i in range(count)]
            for fid in copies:
                if (uid, fid) in placed_ids:
                    continue
                aid = _written_id(uid, fid, asked, plan_ids[uid])
                split_of = _split_base(uid, fid, asked, plan_ids[uid])
                if split_of:
                    splits.setdefault((uid, split_of), []).append(aid)
                at = str(f.get("at") or "").casefold()
                w, d, height = fixture_footprint(f)
                anchor = {"desc": f.get("name") or aid, "footprint": footprint_for_extent(w, d),
                          "height": height}
                if at in _SIDES:
                    anchor["dir"] = at
                elif at in _CORNERS:
                    anchor["dir"] = at[7:]
                out[uid]["anchors"][aid] = anchor
                left = {"room": uid, "anchor": aid, "name": f.get("name") or aid, "asked": at or ""}
                report["unplaced"].append(left)
                out[uid]["record"]["unplaced"].append(left)
    # WINDOWS: in their wall, blocking no line
    names = {}
    for uid, sroom in spec_rooms.items():
        for w in sroom.get("windows") or ():
            names[(uid, w["id"])] = w
    for win in layout.windows:
        uid = win["room"]
        if uid not in out:
            continue
        room = rects[uid]
        base_id = str(win.get("base") or "")
        base = names.get((uid, base_id)) or {}
        aid = _slug(win["id"]) or "window"
        if int(base.get("count") or 1) > 1:
            # SEVERAL ALIKE, as fixtures are: each a window of its own,
            # named as one of them, the first under the plan's own id when
            # the plan named them under one record (`SPLIT`, below)
            if base_id in plan_ids[uid]:
                if aid == _slug(f"{base_id}_1"):
                    aid = base_id
                splits.setdefault((uid, base_id), []).append(aid)
            desc = str(base.get("name") or base_id or "window")
        else:
            desc = _window_desc(building, uid, base_id, base)
        out[uid]["anchors"][aid] = {
            "desc": desc, "dir": win["side"],
            "cell": [win["cell"][0] - room.x, win["cell"][1] - room.y],
            "footprint": "point", "height": "head", "opacity": "see_through"}
        if base.get("side") in _SIDES and base["side"] != win["side"]:
            # A WINDOW IS IN AN OUTSIDE WALL OR IT IS NO WINDOW, so it keeps
            # the wall the solver found -- and the move is said, never made
            # silently: the wall asked for was inside the building.
            moved = {"room": uid, "anchor": aid, "name": desc, "asked": base["side"],
                     "solver_put_it": win["side"]}
            report["moved"].append(moved)
            out[uid]["record"]["moved"].append(moved)
    # SPLIT: a record of the plan that named several alike -- "three box beds
    # along the wall" -- is laid as one anchor each, the first under the
    # plan's own id. The plan's words for the GROUP stay in the solve's
    # record, never on that first copy: left there, every mind that saw the
    # room read three box beds in one place and two more beside them (review
    # of 2026-10-08, R2-6). Each copy carries the first call's name for one
    # of them (`write_planned_layout` lets it stand on the plan's record).
    for (uid, base), copies in sorted(splits.items()):
        words = str((_plan_anchors(building, uid).get(base) or {}).get("desc") or "")
        entry = {"anchor": base, "desc": words, "copies": copies}
        report["split"].append(dict(entry, room=uid))
        out[uid]["record"].setdefault("split", []).append(entry)
    # DOORWAYS: between two of the building's rooms, and onto the ground
    entrance = building["entrance"] or {}
    for door in layout.doors:
        a, b, side, cell = door["a"], door["b"], door["side"], door["cell"]
        if a in out and b in out:
            out[a]["edges"][b] = {"dir": side, "offset": _offset(rects[a], side, cell)}
            dx, dy = _STEP[side]
            there = (cell[0] + dx, cell[1] + dy)
            out[b]["edges"][a] = {"dir": opposite_bearing(side),
                                  "offset": _offset(rects[b], opposite_bearing(side), there)}
        elif a in out and door.get("outside"):
            to = entrance.get("to") if b == "entrance" else b
            if to and to not in out[a]["edges"]:
                out[a]["edges"][to] = {"dir": side, "offset": _offset(rects[a], side, cell)}
    # STAIRS: the plan's vertical edge, pinned where each room meets its stair
    halls, shaft_of = {}, {}
    for well in layout.stairwells:
        for lv, hall in (well.get("halls") or {}).items():
            halls[hall] = well
        for flight in well.get("flights") or ():
            # flights that stack into one stairwell share its id
            # (`layout_solver._shafts`): each flight is found by its own
            shaft_of[flight] = well["id"]
    landing = {}
    for door in layout.doors:
        for hall_id, room_id in ((door["a"], door["b"]), (door["b"], door["a"])):
            if hall_id not in halls or room_id not in out:
                continue
            cells = [tuple(c) for c in door.get("span") or [door["cell"]]]
            cell = cells[len(cells) // 2]
            wall = _OPP[door["side"]] if door["a"] == hall_id else door["side"]
            if door["a"] == hall_id:
                dx, dy = _STEP[door["side"]]
                cell = (cell[0] + dx, cell[1] + dy)
            room = rects[room_id]
            landing[(halls[hall_id]["id"], room_id)] = ([cell[0] - room.x, cell[1] - room.y], wall)
    for st in spec.get("stairs") or ():
        for here, there in ((st["from"], st["to"]), (st["to"], st["from"])):
            spot = landing.get((shaft_of.get(st["id"]), here))
            if spot is not None and here in out:
                out[here]["edges"][there] = {"cell": spot[0]}
    # RESTORED: a fixture the plan lists that the first call left out, or
    # filed only as a zone, kept as the plan holds it (`hold_inventory`):
    # nothing is written for it, so the plan's own record stands, unpinned,
    # and the room's designer meets it as the plan named it. Said, so it is
    # counted -- and an answer that gave the plan's thing a new id shows as
    # two of it rather than as one
    for held in (inventory or {}).get("rooms") or ():
        if held.get("id") not in out:
            continue
        for f in held.get("restored") or ():
            entry = {"room": held["id"], "anchor": f["id"], "name": f.get("name") or f["id"]}
            report["restored"].append(entry)
            out[held["id"]]["record"].setdefault("restored", []).append(entry)
    # MARKS: a fixture the plan lists that is where a way meets the room,
    # pinned there -- a place, blocking no line -- and listed when the solve
    # holds no such way
    for held in (inventory or {}).get("rooms") or ():
        uid = held.get("id")
        if uid not in out:
            continue
        for mark in held.get("marks") or ():
            found = _way_cells(layout, rects, landing, shaft_of, spec, uid, mark["to"],
                               entrance_to=entrance.get("to"))
            anchor = {"desc": mark.get("name") or mark["id"], "footprint": "point",
                      "height": "floor", "opacity": "see_through"}
            if found is None:
                out[uid]["anchors"][mark["id"]] = anchor
                left = {"room": uid, "anchor": mark["id"], "name": anchor["desc"],
                        "asked": f"where the way to {mark['to']} meets the room"}
                report["unplaced"].append(left)
                out[uid]["record"]["unplaced"].append(left)
                continue
            cell, wall = found
            anchor.update(cell=list(cell), dir=wall)
            out[uid]["anchors"][mark["id"]] = anchor
            report["marks"].append({"room": uid, "anchor": mark["id"], "way": mark["to"],
                                    "cell": list(cell)})
    # DOORWAYS ON ANOTHER WALL THAN ASKED: a side the plan stated refuses the
    # solve (`refusals`); one the model chose is the solver's arrangement to
    # settle, and is said rather than made silently
    report["sides"] = []
    asked_sides = [(sroom["id"], j["to"], j.get("side")) for sroom in spec.get("rooms") or ()
                   for j in sroom.get("joins") or () if j.get("side")]
    if entrance:
        asked_sides.append((entrance["room"], entrance["to"], spec.get("front")))
    for room_id, to, asked_side in asked_sides:
        if to in out:
            got = _door_side(layout, room_id, to)
        else:
            got = _outside_side(layout, building, {"room": room_id, "to": to})
        if got and asked_side and got != asked_side:
            entry = {"room": room_id, "to": to, "asked": asked_side, "solved": got}
            report["sides"].append(entry)
            if room_id in out:
                out[room_id]["record"].setdefault("sides", []).append(entry)
    for uid in out:
        record = out[uid]["record"]
        out[uid]["layout"] = {"plan": building["plan"], "turn": turn,
                              "moved": record["moved"], "unplaced": record["unplaced"],
                              "sides": record.get("sides", [])}
        for key in ("stated", "described_m2", "restored", "split"):
            if key in record:
                out[uid]["layout"][key] = record[key]
        del out[uid]["record"]
    return out, report


def _window_desc(building, uid, base, window):
    anchors = building["specs"][uid].get("anchors")
    if isinstance(anchors, dict) and isinstance(anchors.get(base), dict) \
            and str(anchors[base].get("desc") or "").strip():
        return str(anchors[base]["desc"])
    return str(window.get("name") or base or "window")
