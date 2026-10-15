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
* each fixture the solver moved off the wall the model named, pinned where
  the solver stood it, with the wall it stands against -- what the layout lab
  draws (the owner, 2026-10-13: "match layout lab ... stop overlapping
  furnitures"; it replaced "capacity goes back to the model", under which a
  moved fixture went back unpinned to the wall that could not hold it and was
  laid on a doorway or another fixture). Never a move made silently: it is
  listed in the solve's record, and a designer dressing the room re-settles
  it by its `cell`. One the solver could not place at all is written on the
  wall the model named and pinned nowhere, listed as unplaced;
* each fixture the plan lists that the first call says is off the floor --
  hung on a wall, from the ceiling, on or in another fixture -- its `mount`
  on the plan's record, so a place code chooses for it shares the floor with
  what stands beneath (`spatial_fov.stands_on_floor`);
* each window in its wall, the room's own and never an anchor among its
  furniture (chat 168, 2026-10-12: the owner's shrine had every window laid
  as a fixture, and no view ever looked out of one) -- in the outside wall
  the solver found, since a window in an inside wall is none, and listed as
  moved when that is not the wall the model named. One with open ground the
  solve laid beyond it -- the garden below, past the roof of a lower wing --
  is a `window` edge to that ground, pinned on both sides, so sight crosses
  it with height (`site_plan.plan_sight`) and a fall from it lands there
  (`drop_m`): the lab converter's rule. Every other one is a record in the
  room's `windows` (`spatial_geometry.room_windows`), where it stands in the
  wall. A record of the plan that IS a window is taken off the plan's
  anchors when the window is laid;
* each doorway between two of the building's rooms, and each onto the ground
  outside, its `dir` and `offset` on the plan's edge;
* EACH STAIR A ROOM OF ITS OWN ON EVERY STOREY IT JOINS (the owner's
  choice of 2026-10-12, asked against a stair standing in its room: "there
  are no genned stairs as far as i can tell" -- the solver's stair halls,
  rooms in the layout lab and its converter, were left off the plan, and a
  stair was one vertical edge with a landing cell). Each hall is a planned
  room the tier makes (`LAYOUT_MADE_KEY`), on its storey and the solver's
  rectangle, named for its stair: joined to the room it serves by the
  solver's doorway -- the whole run of their shared wall open for an open
  stair, its door for an enclosed one -- and to the hall above or below by
  the flight itself. The plan's own stair between the two rooms is replaced
  by that way through, where every piece of it was laid; where one was not,
  the stair stays the plan's edge, its `cell` where each room meets it. The
  solver's stores and voids are still no rooms: 98827d9f (reverted, "a loft
  space that didn't exist before") made one of a void where a window
  belonged. Each way the tier makes -- a hall's, or a window's onto the
  ground -- is the solve's own (`made_edges`) to move or take back.
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
doorway -- and a refused building is written nowhere: today's designer
builds its rooms exactly as it would have. A room's SIZE is none of these,
and nor is a SIDE: a side the Room planned is a wish, as in the lab, which
the solve may turn, the plan's doorway moving with it (the owner's ruling
of 2026-10-10). The plan's `extent` is the
Writers' Room's estimate: the solver sizes every room from what it holds,
aimed at a size only where the story's own lore states one, and the solve's
size replaces the estimate, each filed against the other (`stated`,
`described`; the owner's ruling of 2026-10-10). A room the plan states is
not a rectangle stands in a block of its own when it opens into the
building by one doorway on a side the plan states; an `l` or a `composite`
that names no parts is its box, and is solved as the rectangle it is;
built from `parts`, or round and joined any other way, it refuses the
building before any call is made: the solver lays rectangles. So does a room already standing on the plan the
solve would be written on: placed beside an earlier solve, it stands in that
solve's frame. A side the solver put elsewhere -- the Room's, marked
`planned`, or one only the model chose -- is listed in the record (`sides`),
never refused.
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
from world.structure import LAYOUT_MADE_KEY, LAYOUT_PLAN_PREFIX

#: Rooms one building may hold for the tier to lay it out. The solver
#: divides every storey many times over (`layout_solver.QUICK`/`TRIES`): the
#: owner's preferred shrine -- eleven planned rooms on four storeys and three
#: stair halls -- took 11.1 s. Past this many rooms a group of planned rooms
#: is a quarter of a town rather than a building, which is the town-fabric
#: tier's work (survey rank 7) and not this one's. A per-solve bound on job
#: time; a building over it fails open to the designer, which builds it
#: room by room as it always has. Named per ask-before-limiting.
LAYOUT_TIER_MAX_ROOMS = 24
#: How many seeds of the solver's search one building is solved with
#: (`solve_for`): the solver's own seed and the next ones, EVERY one solved,
#: since the first that stands is not the best that does. A solve of the
#: owner's shrine takes 7 to 9 s, so every building now costs what only the
#: worst case did, near 35 s of one background job, or of a launch whose
#: opening stands in a planned building
#: (`director_layout.lay_out_opening_ground`). Named per ask-before-limiting.
LAYOUT_SOLVE_SEEDS = 4
#: How many times a building whose grounds do not hold is solved again with
#: only the places that failed taken out (`agents.director_layout.lay_out`,
#: the owner's ruling of 2026-10-13: drop only the failing places), before
#: the house is laid alone. Each round is up to `LAYOUT_SOLVE_SEEDS` solves.
#: Named per ask-before-limiting.
GROUND_DROP_ROUNDS = 2
#: The one shape the solver lays. A room the plan states another shape of
#: (`spatial_fov.SHAPES`: round, l, composite) refuses its building before
#: any call is made: written back, its rectangle would square a round tower
#: room for good (review of 2026-10-08, F2).
SOLVED_SHAPE = "rectangle"
#: The exposure of a room with walls round it (`weather.EXPOSURES`).
WALLED = "enclosed"
#: The first call's one word for a planned room that stands beyond the
#: building's own walls (`hold_inventory`, `stand_beyond`).
STANDS_BEYOND = "beyond"
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
#: THE GROUNDS A BUILDING STANDS IN (2026-10-11, the owner: "Tier lays out
#: the grounds"). How many outdoor places of the building's own structure
#: are laid out with it, and how far from its doors they reach in joins:
#: the ground the plan gives one house -- its garden, its approach, the
#: things standing on them, a privy apart -- and no further, since past that
#: the places are the town's. Home 5's plan held six, every one within
#: three joins of a door. Named per ask-before-limiting.
GROUNDS_MAX_PLACES = 12
GROUNDS_MAX_HOPS = 3
#: What one outdoor place IS on the ground the building stands in -- the
#: solver's own four (`layout_solver`, rule 5): open ground, a way across
#: it, one thing standing on it, a small building of its own standing apart.
GROUND_IS = ("open", "way", "feature", "outbuilding")
#: The solver's word for open ground; it reads nothing from an area's kind.
GROUND_AREA_KIND = "yard"
#: The ground the building's doors open onto when the grounds name no open
#: ground it stands `around`: solver geometry only, never written back.
GROUND_ID = "__grounds__"

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
        "ground_is": list(GROUND_IS),
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
    it, and reversed onto the other side when only one does -- never one an
    earlier solve made (`made_edges`)."""
    from world.spatial import normalize_bearing, normalize_vertical, opposite_bearing
    out = {}
    for uid, (_name, spec) in specs.items():
        # NOT A WAY AN EARLIER SOLVE MADE (`planned_layout`'s `made_edges`):
        # that is the solve's own, to make again or take back -- read as the
        # plan's, a window the first solve made onto the ground had the
        # re-solve lay a door for it, and the room was written two windows on
        # one wall (a review of 2026-10-14)
        record = (spec or {}).get("layout")
        made = {str(t) for t in (record.get("made_edges") or ())} \
            if isinstance(record, dict) else set()
        for edge in (spec or {}).get("adjacent") or ():
            if not isinstance(edge, dict) or not edge.get("to"):
                continue
            to = str(edge["to"])
            if to == uid or to in made:
                continue
            out[(uid, to)] = {
                "vertical": normalize_vertical(edge.get("vertical")),
                "barrier": edge.get("barrier"),
                "dir": normalize_bearing(edge.get("dir")),
                "way": str(edge.get("way") or "").strip().casefold(),
                "distance": edge.get("distance"),
            }
    for (a, b), rec in list(out.items()):
        if (b, a) not in out:
            out[(b, a)] = {
                "vertical": {"up": "down", "down": "up"}.get(rec["vertical"]),
                "barrier": rec["barrier"],
                "dir": opposite_bearing(rec["dir"]) if rec["dir"] else None,
                "way": rec["way"], "derived": True,
                "distance": rec.get("distance"),
            }
    return out


def _authored_apart(value):
    """Whether a distance the plan AUTHORED on a join puts ground between
    the two rooms: a word or a measurement the engine reads
    (`spatial.normalize_edge_distance`) past `adjacent`. Nothing written, or
    a word it cannot read, says nothing -- the reader's own default `near`
    is no measurement."""
    from world.spatial import _DISTANCE_ALIASES, edge_metres, normalize_edge_distance
    raw = str(value if value is not None else "").strip().casefold()
    if not raw or (raw not in _DISTANCE_ALIASES and edge_metres(raw) is None):
        return False
    return normalize_edge_distance(raw) != "adjacent"


#: The share of a structure's joins between walled rooms that may be
#: written across ground before the word is the plan's HABIT, not a fact of
#: any one room (`_apart_habit`): past it, no room stands apart and no thing
#: stands off a wall for it. The owner's shrines wrote it on one such join
#: in about ten (the latrine's); a live plan of 2026-10-15 wrote `near` on
#: every join between its rooms and `far` on one out of doors, and read as
#: a fact it took the kitchen, the store, two halls and both bedrooms out of
#: the house. Named per ask-before-limiting.
APART_HABIT_SHARE = 0.5


def _apart_habit(planned, structure):
    """Whether the plan writes a distance past `adjacent` as its HABIT on
    the joins between the walled rooms of `structure`: on more than
    `APART_HABIT_SHARE` of them, each pair counted once and apart when
    either side says so. `planned` is `{uid: planned spec}`. The outdoors is
    no part of it -- a way's `far` says how far the road runs, never how the
    house's rooms meet -- and neither is a stair room an earlier solve made
    (`LAYOUT_MADE_KEY`), which carries no distance of the Room's."""
    from world.spatial import normalize_vertical

    def walled(uid):
        spec = planned.get(uid)
        return isinstance(spec, dict) and not spec.get(LAYOUT_MADE_KEY) \
            and str(spec.get("structure") or "") == structure \
            and str(spec.get("exposure") or "").strip().casefold() == WALLED

    pairs = {}
    for uid, spec in planned.items():
        if not walled(uid):
            continue
        for edge in spec.get("adjacent") or ():
            to = str((edge or {}).get("to") or "") if isinstance(edge, dict) else ""
            if to == uid or not walled(to) or normalize_vertical(edge.get("vertical")):
                continue
            key = frozenset((uid, to))
            pairs[key] = pairs.get(key, False) or _authored_apart(edge.get("distance"))
    return bool(pairs) and sum(pairs.values()) > APART_HABIT_SHARE * len(pairs)


def _stated_apart(edges, structure_of, planned):
    """`{room: [the rooms it joins]}` for every walled room the plan states
    STANDS APART from the rooms it joins on its storey: each such join
    carries an authored distance past `adjacent` (`_authored_apart`), on
    either side -- the Room's own word that there is ground in between, so
    the two share no wall. Not where that word is the plan's habit on the
    joins between its walled rooms (`_apart_habit`): it then says how the
    plan writes joins, and nothing of one. `planned` is `{uid: planned
    spec}`."""
    level = {}
    for (a, b), rec in edges.items():
        if rec["vertical"]:
            continue
        apart = _authored_apart(rec.get("distance")) or \
            _authored_apart((edges.get((b, a)) or {}).get("distance"))
        level.setdefault(a, []).append((b, apart))
    habit = {}
    out = {}
    for room, joins in level.items():
        structure = structure_of.get(room)
        if structure not in habit:
            habit[structure] = _apart_habit(planned, structure)
        if habit[structure]:
            continue        # the plan writes the word on most of its joins
        if joins and all(apart for _other, apart in joins):
            out[room] = sorted(other for other, _apart in joins)
    return out


def _joined_apart(building, room, pid):
    """Whether the plan joins the building's room `room` and the place `pid`
    of its ground ACROSS GROUND: the join, on either side, carries an
    authored distance past `adjacent` (`_authored_apart`) -- the Room's own
    word that ground lies between them, so the place stands off the room's
    wall rather than across its door (`_ground_plan`, `ground_breaches`).
    Not where that word is the plan's habit on the joins between the
    building's walled rooms (`_apart_habit`, `_stated_apart`'s rule): it
    then says how the plan writes joins, and nothing of one."""
    from world.spatial import normalize_vertical
    plans = dict(building.get("ground_specs") or {})
    plans.update(building.get("specs") or {})
    said = []
    for uid, planned in plans.items():
        for edge in (planned.get("adjacent") or ()) if isinstance(planned, dict) else ():
            if not isinstance(edge, dict) or normalize_vertical(edge.get("vertical")):
                continue
            if {uid, str(edge.get("to") or "")} == {room, pid}:
                said.append(edge.get("distance"))
    if _apart_habit(building.get("specs") or {}, str(building.get("structure") or "")):
        return False        # the plan writes the word on most of its joins
    return any(_authored_apart(distance) for distance in said)


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


def plan_buildings(specs, scene, *, held_open=(), max_rooms=LAYOUT_TIER_MAX_ROOMS,
                   grounds=False):
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
    # A ROOM THE TIER MADE is no room of a building to lay out: a stair's
    # hall is the solve's, made again by the next one (`LAYOUT_MADE_KEY`)
    specs = {uid: entry for uid, entry in (specs or {}).items()
             if not (isinstance(entry[1], dict) and entry[1].get(LAYOUT_MADE_KEY))}
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
    # A ROOM THE PLAN STATES APART -- ground in between, the Room's own
    # authored distance (`_stated_apart`) -- shares no wall with the rooms it
    # joins on its storey: on the ground it is a building apart, laid as one
    # (`_grounds_of`, `hold_grounds`); below it, a space of its own beyond the
    # wall it is entered through (`_building`'s own blocks). Joined in, the
    # latrine the plan put across the ground behind the house was laid as a
    # room inside it in every shrine the engine laid (2026-10-15).
    planned = {uid: spec for uid, (_name, spec) in specs.items()}
    apart = {uid: others for uid, others in _stated_apart(edges, structure_of, planned).items()
             if uid in walled and uid not in stair_rooms}
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
        if not rec["vertical"] and (a in apart or b in apart) and not _below_ground(a, specs) \
                and not _below_ground(b, specs):
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
                             normalize_site=normalize_site, normalize_level=normalize_level,
                             grounds=grounds))
    return sorted(out, key=lambda b: b["key"])


def _below_ground(uid, specs):
    """Whether the plan states `uid` on a storey below the ground."""
    from world.spatial import normalize_level
    level = normalize_level(((specs.get(uid) or (None, {}))[1] or {}).get("level"))
    return level is not None and level < 0


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


def _ground_parts(members, specs, edges, structure, structure_of, normalize_level):
    """THE GROUND FILED AS A PART OF THE MAP OF ITS OWN: the structures,
    besides the building's, whose places the walk may collect as its ground
    (`_grounds_of`).

    To the Room a structure is "the part of the map the rooms make", and a
    building's yard is a fair part of its own: the live shrines of
    2026-10-15 filed the torii, the lantern path, the well, the garden, the
    camphor and the latrine as `shrine_grounds` beside the house's own
    structure in two runs of two -- where the owner's three plans had filed
    all of it with the house -- and the walk, reading the house's structure
    alone, laid none of it. Such a part is the building's ground when one of
    the building's own rooms opens onto it; when no walled room of any other
    part of the map does -- a street another building's door opens onto is
    the town's; and when it holds no building of its own -- no place off the
    ground storey, no stair, no walled place joined to another walled place:
    a latrine standing alone in the yard is ground, an inn is not. A part of
    the map the building's rooms do not open onto is never entered, so the
    walk goes no further into the world than it went before."""
    member_set = set(members)

    def walled(uid):
        return str(((specs.get(uid) or (None, None))[1] or {}).get("exposure") or "") \
            .strip().casefold() == WALLED

    reached = {structure_of.get(b) for (a, b), rec in edges.items()
               if a in member_set and b in specs and b not in member_set and not rec["vertical"]
               and structure_of.get(b) != structure}
    parts = set()
    for part in sorted(p for p in reached if p):
        places = {uid for uid in specs if structure_of.get(uid) == part}
        foreign = any(
            ((a in places) != (b in places))
            and any(w not in places and w not in member_set and walled(w)
                    and structure_of.get(w) != structure for w in (a, b) if w in specs)
            for (a, b), _rec in edges.items())
        # a stair between the yard and the building is one of its ways out
        # (an outside stair, a ladder to a roof), never a storey of the yard
        holds = any(normalize_level((specs[uid][1] or {}).get("level")) not in (None, 0)
                    for uid in places) or \
            any((rec["vertical"] and b not in member_set)
                or (b in places and walled(a) and walled(b))
                for (a, b), rec in edges.items() if a in places)
        if not foreign and not holds:
            parts.add(part)
    return parts


def _grounds_of(members, specs, rooms, edges, structure, outside, *, held_open, solved,
                normalize_site, normalize_level, own=(), parts=()):
    """THE GROUND A BUILDING STANDS IN: `(places, specs)` -- the outdoor
    places of the building's own structure, or of a part of the map that is
    its ground alone (`parts`, `_ground_parts`), reachable from its doors
    through other such places, nearest first, at most `GROUNDS_MAX_PLACES` within
    `GROUNDS_MAX_HOPS` joins, and each one's plan as read.

    The layout lab's liked shrine stood in its garden, its approach running
    from the front door to the torii, its well by the entryway and its
    latrine apart behind it; the engine laid out the house and left every one of
    those where the Room's own estimates put them -- a 60 by 60 garden beside
    a house a fraction its size (the owner's chat 167, 2026-10-11). The
    places stay the plan's rooms -- the tier never invents a room or takes
    one away, and a body can stand at a tree -- and the solve says only
    where each lies and how large.

    A place is ground only when nothing else decides it: not one of the
    building's rooms, not a frontier space the Room has yet to claim, not a
    room the story has described (it is never re-measured), not standing on
    a plan already decided (`_on_a_plan`) -- save the ground an earlier solve
    of this building laid (`own`, `_own_grounds`), laid again with it -- not
    the inside of something, and on the ground storey. Every place met stops
    there: the walk goes on only through the ground it collects."""
    member_set = set(members)
    held = set(held_open or ())
    own = set(own or ())

    def eligible(uid):
        if uid in member_set or uid in held or uid not in specs:
            return False
        spec = specs[uid][1] or {}
        if str(spec.get("structure") or "") not in ({structure} | set(parts)):
            return False
        level = normalize_level(spec.get("level"))
        if level not in (None, 0):
            return False
        if spec.get("parent_entity"):
            return False
        live = rooms.get(uid)
        if isinstance(live, dict):
            if str(live.get("desc") or live.get("description") or "").strip():
                return False
            if live.get("parent_entity"):
                return False
            if uid not in own and _on_a_plan(live, normalize_site, solved):
                return False
        return uid in own or not normalize_site(spec.get("site"))

    order, hops, queue = [], {}, []
    for o in outside:
        if not o.get("vertical") and o["to"] not in [q[0] for q in queue]:
            queue.append((o["to"], 1))
    while queue and len(order) < GROUNDS_MAX_PLACES:
        uid, hop = queue.pop(0)
        if uid in hops or not eligible(uid):
            continue
        hops[uid] = hop
        order.append(uid)
        if hop >= GROUNDS_MAX_HOPS:
            continue
        for (a, b), rec in sorted(edges.items()):
            if a == uid and not rec["vertical"] and b not in hops:
                queue.append((b, hop + 1))
    places = []
    for uid in order:
        name, spec = specs[uid]
        spec = spec or {}
        joins = sorted({b for (a, b), rec in edges.items()
                        if a == uid and not rec["vertical"] and (b in hops or b in member_set)})
        places.append({"id": uid, "name": str(name or uid), "purpose": _text(spec.get("purpose"), 400),
                       "shape": str(spec.get("shape") or "").strip().casefold(),
                       "joins": joins, "hop": hops[uid]})
    return places, {uid: copy.deepcopy(specs[uid][1] or {}) for uid in order}


def _own_grounds(specs, members, plan, normalize_site) -> set:
    """The places an earlier solve of the building on `plan` laid as its
    ground and that stand there still: each one's row carries the solve's
    record saying so (`layout.grounds`, `planned_layout`) and its site on
    that plan. Only the tier writes either, so no plan the Room or a host
    wrote is read as one."""
    out = set()
    for uid, (_name, spec) in specs.items():
        if uid in members or not isinstance(spec, dict):
            continue
        record = spec.get("layout") if isinstance(spec.get("layout"), dict) else {}
        site = normalize_site(spec.get("site"))
        if record.get("grounds") and site and site["plan"] == plan:
            out.add(uid)
    return out


def without_grounds(building):
    """The building as the tier laid it before the grounds: its rooms, and
    the ground it opens onto as open ground beside them (`spec_from_answers`).
    What a solve falls back to where the grounds make every seed refuse
    (`agents.director_layout.lay_out`)."""
    return {key: value for key, value in building.items()
            if key not in ("grounds", "ground_specs")}


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
              normalize_site, normalize_level, grounds=False):
    from world.spatial import opposite_bearing
    from world.spatial import WAYS
    names = {uid: str(specs[uid][0] or uid) for uid in members}
    plan = {uid: copy.deepcopy(specs[uid][1] or {}) for uid in members}
    building = {"key": "+".join(members), "rooms": members, "names": names,
                "specs": plan, "structure": structure, "refusal": None}
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
    # A SPACE BELOW GROUND THE PLAN STATES APART (`_stated_apart`) is entered
    # through one wall and lies past it, under no roof of the building: a
    # block of its own beside the room it opens from, as a room of another
    # shape is (below) and as the layout lab's liked shrine has its cavern
    structure_of = {uid: str((spec or {}).get("structure") or "") for uid, (_n, spec) in specs.items()}
    planned = {uid: spec for uid, (_name, spec) in specs.items()}
    for uid in sorted(set(_stated_apart(edges, structure_of, planned)) & set(members)):
        if levels.get(uid, 0) < 0 and uid not in (building.get("own_blocks") or {}):
            block = _own_block(uid, joins, stairs, levels)
            if block is not None:
                building.setdefault("own_blocks", {})[uid] = block
    entrance = sorted(outside, key=lambda o: (bool(o.get("vertical")),
                                              abs(levels.get(o["room"], 0)), o["room"], o["to"]))
    building["entrance"] = entrance[0] if entrance else None
    building["plan"] = (f"{LAYOUT_PLAN_PREFIX}{entrance[0]['room']}" if entrance
                        else f"{LAYOUT_PLAN_PREFIX}{members[0]}")
    # THE GROUND AN EARLIER SOLVE OF THIS BUILDING LAID (`_own_grounds`) is
    # laid again with it, so it is no plan already decided: a house the Room
    # re-planned gives its rooms' solve back, and the ground it stood in goes
    # with it rather than keeping the house off its own plan
    own = _own_grounds(specs, set(members), building["plan"], normalize_site) \
        if grounds else set()
    solved = _solved_plans({rid: live for rid, live in rooms.items() if rid not in own},
                           normalize_site)
    ground_specs = {}
    if grounds:
        building["grounds"], ground_specs = _grounds_of(
            members, specs, rooms, edges, structure, outside, held_open=held_open,
            solved=solved, normalize_site=normalize_site, normalize_level=normalize_level,
            own=own, parts=_ground_parts(members, specs, edges, structure, structure_of,
                                         normalize_level))
        building["ground_specs"] = ground_specs
    building["signature"] = hashlib.sha1(_canon(
        {"plan": plan, "outside": outside,
         **({"grounds": ground_specs} if ground_specs else {})}).encode("utf-8")).hexdigest()[:16]
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
            from world.spatial import _PART_SHAPES, normalize_parts
            parts = normalize_parts(plan[uid].get("parts"))
            block = None if parts else _own_block(uid, joins, stairs, levels)
            if block is not None:
                building.setdefault("own_blocks", {})[uid] = block
            elif str(plan[uid]["shape"]).strip().casefold() in _PART_SHAPES and not parts:
                # A SHAPE BUILT FROM PARTS THAT NAMES NONE IS ITS BOX: its
                # cells are the whole of its extent (`spatial_fov._shape_cells`),
                # so it is solved as the rectangle it already is, its shape
                # word kept (`planned_layout`). The Writers' Room planned the
                # shrine of the owner's refined lore (scratch chat 169,
                # 2026-10-10) with its basement `composite` and its roof room
                # an `l`, neither with a part, and the whole building was
                # refused for rooms it could lay.
                building.setdefault("boxed", []).append(uid)
            else:
                refusal = (f"{uid} is planned {plan[uid]['shape']}, and the solver lays "
                           f"{SOLVED_SHAPE}s")
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
        laid_again = {g["id"] for g in building.get("grounds") or ()}
        # ...and a stair hall an earlier solve of this building made, which
        # this one makes again or withdraws (`LAYOUT_MADE_KEY`)
        holder = next((rid for rid, live in sorted(rooms.items())
                       if rid not in building["rooms"] and rid not in laid_again
                       and isinstance(live, dict) and not live.get(LAYOUT_MADE_KEY)
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
    # THE GROUND IT STANDS IN (`_grounds_of`), where the tier lays it out
    if building.get("grounds"):
        out["building"]["grounds"] = [
            {"id": g["id"], "name": g["name"], "purpose": g["purpose"],
             "joins": [{"to": o, "name": (building["names"].get(o)
                                          or next((x["name"] for x in building["grounds"]
                                                   if x["id"] == o), o))}
                       for o in g["joins"]]}
            for g in building["grounds"]]
    # WHAT THE STORY'S LORE SAYS OF IT (`director_layout.building_description`),
    # where the tier found any: the fixtures, windows and floors a room's
    # one-line purpose leaves out, and the solver sizes a room by what it holds.
    if str(building.get("description") or "").strip():
        out["building"]["description"] = str(building["description"]).strip()
    # THE ARCHITECT'S BRIEF (`director_layout._briefed`), where one was
    # written: how the building stands as a whole, which both calls follow
    if str(building.get("brief") or "").strip():
        out["building"]["brief"] = str(building["brief"]).strip()
    return out


def brief_payload(building):
    """What the architect's brief is written from: the building as the plan
    holds it, what the plan fixes, and the story's lore of it -- never a
    brief already written."""
    out = sort_payload(dict(building, brief=None))
    out["fixed"] = _fixed(building)
    return out


def _fixed(building):
    """What the plan already fixes: the sides it states for its joins and the
    doorways out, the front, and the entrance."""
    fixed = {"joins": [{"from": j["a"], "to": j["b"], "side": j["side"]}
                       for j in building["joins"] if j["side"]]
             + [{"from": o["room"], "to": o["to"], "side": o["side"], "outside": True}
                for o in building["outside"] if o["side"]]}
    entrance = building["entrance"] or {}
    if entrance.get("side"):
        fixed["front"] = entrance["side"]
    fixed["entrance"] = {"room": entrance.get("room"), "opens_onto": entrance.get("to")}
    return fixed


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
        # WHAT COVERS THE FLOOR WALL TO WALL IS THE FLOOR (chat 168,
        # 2026-10-12: the shrine's tatami was sorted as a fixture, and every
        # view read "Tatami mats within arm's reach"): the room's word for
        # it, as a plan's own `floor` is read (`plot_packages._plan_geometry`)
        floor = _floor_word(raw.get("floor"))
        if floor and not held.get("floor"):
            held["floor"] = floor
        # WHERE IT STANDS against the building's own walls, in the engine's
        # one word for it: `beyond` -- a space of its own entered through one
        # outer wall (`stand_beyond`); every other room stands within
        if str(raw.get("stands") or "").strip().casefold() == STANDS_BEYOND:
            held["stands"] = STANDS_BEYOND
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
                        # A MARK THE PLAN NEVER LISTED IS THE DOORWAY ITSELF.
                        # `marks` pins a fixture the plan lists where its way
                        # meets the room (the live inn's `stair_foot`); one
                        # the answer made up is the way through, which is
                        # its edge and already stands where it meets the
                        # room -- never a second thing on it (room
                        # vocabulary: "A DOORWAY IS ITS EDGE, NEVER ALSO AN
                        # ANCHOR"). Chat 168 (2026-10-12): all nine door and
                        # stair anchors were the answer's own, each on its
                        # door's cell, and the one a body stood at stayed
                        # shut when the door it copied was opened.
                        if keep:
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
    held = {"rooms": [rooms[uid] for uid in building["rooms"]], "stairs": stairs}
    if building.get("grounds"):
        held["grounds"] = hold_grounds(building, answer.get("grounds"))
    return held


def stand_beyond(building, inventory):
    """The building with a block of its own for every room the first call
    says stands BEYOND its walls (`hold_inventory`'s `stands`), beside the
    room it opens from, on the side the plan states -- the same block a room
    of another shape is given (`_own_block`), so the second call and the
    solve read one building. Only a room joined by one doorway on its own
    storey and by no stair can stand so; any other keeps its place within
    the walls and is named under `stands_within`. The lab's liked shrine has
    its Seal Cavern so, past the basement's far wall; the engine laid it
    inside the basement's storey, and the stair halls swelled round it
    (2026-10-15)."""
    out = dict(building)
    own = dict(building.get("own_blocks") or {})
    kept = []
    for room in (inventory or {}).get("rooms") or ():
        uid = room.get("id")
        if room.get("stands") != STANDS_BEYOND or uid not in building["rooms"] or uid in own:
            continue
        block = _own_block(uid, building["joins"], building["stairs"], building["levels"])
        if block is None:
            kept.append(uid)
            continue
        own[uid] = block
    if own:
        out["own_blocks"] = own
    if kept:
        out["stands_within"] = sorted(kept)
    return out


def _ordered(said, room, other):
    """Whether `room`'s answer gives its join to `other` an order."""
    for j in (said.get(room) or {}).get("joins") or ():
        if isinstance(j, dict) and str(j.get("to") or "") == other:
            return _int(j.get("order")) > 0
    return False


def _floor_word(value) -> str:
    """A floor is a word: what a room's floor is made of, or covered with
    from wall to wall -- the engine's sound reads it (`spatial_levels`,
    `spatial_sound_field.FLOOR_IMPACT_DB`). Anything that is not a string is
    no word, and a word is held as a plan holds one."""
    word = value.strip().casefold() if isinstance(value, str) else ""
    return " ".join(word.split())[:20]


def hold_grounds(building, answer):
    """What the first call said each outdoor place IS, held to the plan's
    places and the solver's words: `[{id, name, is, kind?}]`. A place it
    left out, or called something the solver has no word for, is not
    listed -- and a place left unsaid is laid out no further than the
    tier ever laid it (`spec_from_answers`)."""
    places = {g["id"]: g for g in building.get("grounds") or ()}
    kinds = set(FIXTURE_SIZES)
    out, seen = [], set()
    for raw in answer or ():
        if not isinstance(raw, dict):
            continue
        pid = str(raw.get("id") or "")
        what = str(raw.get("is") or "").strip().casefold()
        if pid not in places or pid in seen or what not in GROUND_IS:
            continue
        seen.add(pid)
        entry = {"id": pid, "name": places[pid]["name"], "is": what}
        kind = str(raw.get("kind") or "").strip().casefold().replace(" ", "_")
        if what == "feature" and kind in kinds:
            entry["kind"] = kind
        out.append(entry)
    # A WALLED PLACE IS NEVER OPEN GROUND: one the plan states `enclosed`
    # that the answer leaves unsaid is a building apart, as the sort card
    # defines an outbuilding -- read as open ground, the latrine the plan
    # put apart from the house would be a band of the garden
    for pid, place in places.items():
        planned = (building.get("ground_specs") or {}).get(pid) or {}
        if pid not in seen and str(planned.get("exposure") or "").strip().casefold() == WALLED:
            out.append({"id": pid, "name": place["name"], "is": "outbuilding"})
    return out


def relate_payload(building, inventory):
    """What the second call reads: the building, what the first sorted each
    room to hold, what the plan already fixes, and the vocabularies. A mark
    is the engine's to place where its way meets the room, so the second
    call is not handed one to relate."""
    fixed = _fixed(building)
    entrance = entrance_of(building, inventory=inventory)
    if entrance:
        # the entrance and the front the solve will lay, one compass: told
        # the plan's first front beside another entrance, the call answered
        # against a front the spec then turned (a review of 2026-10-14)
        fixed["entrance"] = {"room": entrance.get("room"), "opens_onto": entrance.get("to")}
        if entrance.get("side"):
            fixed["front"] = entrance["side"]
        else:
            fixed.pop("front", None)
    shown = {"rooms": [{"id": r["id"],
                        "fixtures": list(r.get("fixtures") or ()),
                        "zones": list(r.get("zones") or ()),
                        "windows": list(r.get("windows") or ())}
                       for r in inventory.get("rooms") or ()],
             "stairs": list(inventory.get("stairs") or ())}
    if inventory.get("grounds"):
        shown["grounds"] = list(inventory["grounds"])
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
    entrance = entrance_of(building, inventory=inventory)
    front = entrance.get("side") or _side(answer.get("front")) or "s"
    ground = _ground_plan(building, inventory, answer, entrance) \
        if building.get("grounds") else None
    door_to = (ground or {}).get("door_to") or {}
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
            # cuts a door between blocks from the block's side -- and except
            # a join the other room's answer ORDERED along its wall and the
            # first room's did not: an order counts the doorways of the wall
            # it is written on, so it is written from the room whose wall
            # that is (Home 9's hallway ordered its two east rooms, and the
            # order was dropped because 'hinami_room' sorts first)
            writer = j["b"] if j["b"] in own_blocks else (
                j["a"] if j["a"] in own_blocks else (
                    j["b"] if _ordered(said, j["b"], j["a"]) and not _ordered(said, j["a"], j["b"])
                    else j["a"]))
            if writer != uid:
                continue
            if j["a"] != uid:
                side = _OPP.get(j["side"]) if j["side"] else None
                side = side or _side((asked.get(other) or {}).get("side"))
                entry = {"to": other, "kind": _door_kind(j["barrier"])}
                if side:
                    entry["side"] = side
                order = _int((asked.get(other) or {}).get("order"))
                if order > 0:
                    entry["order"] = order
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
            order = _int((asked.get(other) or {}).get("order"))
            if order > 0:
                entry["order"] = order
            joins.append(entry)
        for o in building["outside"]:
            if o["room"] != uid or (entrance and o["to"] == entrance.get("to")
                                    and uid == entrance.get("room")):
                continue
            side = o["side"] or _side((asked.get(o["to"]) or {}).get("side"))
            # a door onto the ground opens onto what the place stands in or
            # the way to it (`_ground_plan`), once for each such target
            target = door_to.get(o["to"], o["to"])
            if target == "entrance" or any(x["to"] == target for x in joins) or (
                    entrance and uid == entrance.get("room") and target == entrance.get("to")):
                continue            # through a door the room has already
            entry = {"to": target, "kind": _door_kind(o["barrier"])}
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
        # HOW MANY is the first call's, which quoted the words for them; the
        # second only places them -- its template's count stood at one for
        # every window of every shrine (2026-10-15)
        window_counts = {w["id"]: w.get("count", 1) for w in sorted_.get("windows") or ()}
        windows = []
        for w in mine.get("windows") or ():
            if isinstance(w, dict) and str(w.get("id") or "") in window_ids:
                windows.append({"id": str(w["id"]), "side": _side(w.get("side")),
                                "count": max(1, min(WINDOW_COUNT_MAX,
                                                    _int(window_counts.get(str(w["id"])), 1)))})
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
    blocks = [{"id": uid, "apart": False, "beside": {"block": "main", "side": block["side"]}}
              for uid, block in sorted((building.get("own_blocks") or {}).items())]
    if ground is None:
        grounds = {"areas": [{"id": o["to"], "name": o["name"], "kind": GROUND_AREA_KIND,
                              "where": o["side"] or "around"}
                             for o in _unique_outside(building)]}
    else:
        from world.spatial import EXTENT_MIN_PACES
        grounds = {key: ground[key] for key in ("areas", "ways", "features")}
        # every way is written to the world, which reads no place narrower
        # than this: a walk or a branch way laid a pace wide was written as
        # nothing (the solver's `narrowest`)
        grounds["narrowest"] = EXTENT_MIN_PACES
        rooms.extend(ground["rooms"])
        blocks.extend(ground["blocks"])
    out = {"name": building["names"].get(entrance.get("room")) or building["names"][building["rooms"][0]],
           "front": front,
           "entrance": {"room": entrance.get("room"),
                        "kind": _door_kind(entrance.get("barrier"))} if entrance else {},
           "storeys": smaller, "rooms": rooms, "stairs": stairs, "grounds": grounds,
           **({"blocks": blocks} if blocks else {})}
    if ground is not None:
        # what each outdoor place is, and what a door onto it opens onto:
        # read back by `refusals` and `planned_layout`, never by the solver
        out["ground_is"], out["door_to"] = ground["is"], door_to
    if entrance and entrance.get("to") != (building.get("entrance") or {}).get("to"):
        out["entrance_to"] = entrance.get("to")
    return out


def _ground_plan(building, inventory, answer, entrance):
    """The ground a building stands in, as the solver's spec takes it:
    `{areas, ways, features, rooms, blocks, is, door_to}` from what the first
    call said each place IS (`hold_grounds`) and the relations the second
    wrote, each word held to the solver's own.

    OPEN GROUND is an area on the side the answer gives it, else the side
    the plan's doorway onto it states, else the ground the building stands
    `around` -- one only; a second takes its side or nothing. A WAY runs from
    the entrance when the entrance opens onto it -- the one approach -- else,
    joined to a room of the house and to an outbuilding, between their doors
    (a walk, whatever open ground it crosses); else from the way the answer
    names, else out past the open ground the plan joins it to where it is
    joined to no room of the house, else out of the one door of the house
    that opens onto it;
    toward the feature the answer names. A FEATURE stands by one relation:
    across, flanking or along a way (at its `end`), by a place or the
    entrance -- on the side of it the answer gives -- or on a side of the
    building; else by the place the plan joins it to. The relation is held
    to the plan's joins: one naming a place the plan does not join it to
    gives way to the join, save where it is joined to open ground alone,
    which it then stands IN (`in`), by what the answer names. An OUTBUILDING
    is a block of its own standing apart on its side, toward the end of it
    its room lies, never centred before the entrance, reached by a way
    between its door and the house's -- the plan's own walk where the plan
    joins it to one, else one of its own (`<id>__way`, solver geometry only).

    A feature the plan joins to a room of the house stands across that
    room's door (`at_door`) -- save one the plan joins to every such room
    across ground (`_joined_apart`), which keeps the answer's relation while
    the room's door opens onto the open ground it stands in; a door onto an
    outbuilding opens onto the way to it (`door_to`). A place the
    first call left unsaid is laid as the tier always laid it when the
    house opens straight onto it -- open ground on the side its doorway
    states -- and not at all when it lies further out."""
    answer = answer if isinstance(answer, dict) else {}
    # the building's places alone: one taken out of it (`without_places`)
    # is no place of this ground, whatever the first call said it was
    present = {g["id"] for g in building.get("grounds") or ()}
    held = {g["id"]: g for g in inventory.get("grounds") or () if g["id"] in present}
    said = {}
    for raw in answer.get("grounds") or ():
        if isinstance(raw, dict) and str(raw.get("id") or "") in held:
            said.setdefault(str(raw["id"]), raw)
    sizes, kinds = set(SIZE_WORD_FOOTPRINT), set(FIXTURE_SIZES)
    is_of = {pid: g["is"] for pid, g in held.items()}
    way_ids = {pid for pid, what in is_of.items() if what == "way"}
    feature_ids = {pid for pid, what in is_of.items() if what == "feature"}
    entrance_to = entrance.get("to")
    front = entrance.get("side") or _side(answer.get("front")) or "s"
    plan_side = {}
    for o in building["outside"]:
        if o["side"] and o["to"] not in plan_side:
            plan_side[o["to"]] = o["side"]
    direct = {o["to"] for o in building["outside"] if not o.get("vertical")}
    areas, ways, features, rooms, blocks, door_to = [], [], [], [], [], {}
    around = None
    approach = False
    # WHAT IS OPEN GROUND, before anything is laid on it (Home 10, chat 173):
    # what the first call said is open, and a place it left unsaid that the
    # house opens straight onto, which is laid as open ground below
    ground_ids = {g["id"] for g in building.get("grounds") or ()}
    open_ids = {pid for pid, what in is_of.items() if what == "open"} | \
        {pid for pid in direct & ground_ids if pid not in is_of}
    planned = building.get("ground_specs") or {}

    def bearing(a, b):
        """The side of `a` that `b` lies on, as the plan states it on either
        side; None where it states none."""
        for one, other, flip in ((a, b, False), (b, a, True)):
            for edge in (planned.get(one) or {}).get("adjacent") or ():
                if isinstance(edge, dict) and str(edge.get("to") or "") == other:
                    side = _side(edge.get("dir"))
                    if side and len(str(edge.get("dir") or "").strip()) == 1:
                        return _OPP[side] if flip else side
        return None

    def apart_side(pid, walk=None):
        """The side of the house a building apart stands on: the side the
        plan's way to it faces -- a room's door onto it, else the room's
        door onto the walk to it -- the answer's only where the plan states
        none."""
        return plan_side.get(pid) or (plan_side.get(walk) if walk else None) or \
            _side((said.get(pid) or {}).get("side"))

    # A WAY WITH A DOOR AT EACH END IS THE WALK BETWEEN THEM: one the plan
    # joins to a room of the house and to a building apart no room opens
    # onto -- a roofed walkway from a washroom's back door to a latrine --
    # runs from the one door to the other, and the building's own door opens
    # onto it, whatever open ground the plan also joins it to. Sent out past
    # the far edge of the garden it was also joined to, with the latrine
    # given a walk of its own beside it, neither door met it, and the floor
    # dropped the latrine, the walkway and the gate charged beside them (a
    # relay of the owner's shrine, 2026-10-15). `{way: the room it leaves}`
    ground_joins = {g["id"]: g.get("joins") or () for g in building.get("grounds") or ()}
    walks = {}
    for pid in sorted(way_ids - {entrance_to}):
        houses = [o for o in ground_joins.get(pid) or () if o in building["rooms"]]
        if houses and any(is_of.get(o) == "outbuilding" and apart_side(o, pid)
                          and not any(x in building["rooms"] for x in ground_joins.get(o) or ())
                          for o in ground_joins[pid]):
            walks[pid] = houses[0]

    # what the answers said first, open ground before what stands on it: a
    # place left unsaid never takes the ground round the house from one said
    # to lie there
    for place in sorted(building.get("grounds") or (),
                        key=lambda g: (g["id"] not in is_of, is_of.get(g["id"]) != "open")):
        pid, mine = place["id"], said.get(place["id"]) or {}
        what = is_of.get(pid)
        if what is None:
            if pid in direct:
                where = plan_side.get(pid) or ("around" if around is None else None)
                if where is not None:
                    around = around or (pid if where == "around" else None)
                    areas.append({"id": pid, "name": place["name"], "kind": GROUND_AREA_KIND,
                                  "where": where})
                    is_of[pid] = "open"
            continue
        if what == "open":
            where = str(mine.get("where") or "").strip().casefold()
            if where not in ("around",) + _SIDES:
                where = plan_side.get(pid) or "around"
            if where == "around" and around is not None:
                where = plan_side.get(pid)
            if where is None:
                del is_of[pid]
                continue
            if where == "around":
                around = pid
            areas.append({"id": pid, "name": place["name"], "kind": GROUND_AREA_KIND,
                          "where": where})
        elif what == "way":
            way = {"id": pid, "name": place["name"]}
            frm = str(mine.get("from") or "").strip()
            opens = [o for o in place["joins"] if o in open_ids]
            houses = [o for o in place["joins"] if o in building["rooms"]]
            # THE APPROACH IS THE WAY THE ENTRANCE OPENS ONTO: never one the
            # plan joins only to other ground, whatever an answer says --
            # laid out of the front door, Home 10's path ran through the
            # court the entrance opens onto and cut it in two
            if not approach and pid == entrance_to:
                way["from"], approach = "entrance", True
            elif pid in walks:
                # THE WALK BETWEEN TWO DOORS (above) has no start of its own:
                # the solver lays it from the room's door to the building's
                pass
            elif frm in way_ids and frm != pid:
                way["from"] = frm
            elif opens and not houses:
                # A WAY THE PLAN JOINS TO OPEN GROUND ALONE LEAVES IT, on the
                # side the plan states, past its far edge (the solver's
                # `WAY_BEYOND`) -- never one a door of the house opens onto,
                # whose door would open a plot's width from it
                way["from"] = opens[0]
                side = bearing(opens[0], pid)
                if side:
                    way["side"] = side
            elif len(houses) == 1:
                # A WAY ONE ROOM OF THE HOUSE OPENS ONTO, AND NO OTHER, LEAVES
                # FROM THAT DOOR, as the approach leaves the entrance's: a
                # path the plan joins to the hall's south wall, the entrance
                # opening onto the garden, had nothing to run from or between
                # and was dropped (a review of 2026-10-14)
                way["from"] = "door"
            if str(mine.get("to") or "") in feature_ids:
                way["to"] = str(mine["to"])
            ways.append(way)
        elif what == "feature":
            feature = {"id": pid, "name": place["name"]}
            if place.get("shape") == "round":
                # read as the world reads it: its box's corners are no part
                # of it (`spatial_fov`'s round shape), so a door's step on one
                # opened onto nothing (a review of 2026-10-14)
                feature["round"] = True
            kind = held[pid].get("kind") or str(mine.get("kind") or "").strip().casefold()
            size = str(mine.get("size") or "").strip().casefold()
            if kind in kinds:
                feature["kind"] = kind
                if size in sizes:
                    feature["size"] = size
            else:
                feature["kind"], feature["size"] = "", size if size in sizes else "medium"
            # WHAT IT STANDS BY IS WHAT THE PLAN JOINS IT TO: an answer's
            # relation to something the plan does not join it to gives way
            # to the plan's join -- a lantern the plan joins to the path,
            # answered by the entrance, stood where it touched no path, and
            # was dropped (a review of 2026-10-14); one the plan joins to
            # nothing it could stand by keeps the answer's
            usable = [o for o in place["joins"]
                      if o in way_ids or o in feature_ids or o in building["rooms"]] + \
                [o for o in place["joins"] if o in open_ids]
            # JOINED TO OPEN GROUND ALONE, IT STANDS IN THAT GROUND (`in`), by
            # whatever the answer relates it to: standing by the kitchen or
            # the lane's mouth keeps a join to the garden or the court it
            # stands in, where a relation thrown away for the join sent a
            # bench to the plot's far corner, and a side of the building
            # answered stood a lantern outside its court (a review of
            # 2026-10-14)
            ground_in = usable[0] if usable and all(o in open_ids for o in usable) else None

            def tied(target, across=False):
                return target in place["joins"] or not usable or (ground_in is not None and not across)

            placed = False
            for rel in ("across", "flank", "along"):
                if str(mine.get(rel) or "") in way_ids and tied(str(mine[rel]), rel == "across"):
                    # A PLACE IS ONE THING: the pair or the row the solver
                    # lays for `flank` and `along` would be one place of
                    # floors that do not touch (Home 6's torii, two posts
                    # apart); the thing stands by the way, at its end
                    feature[rel if rel == "across" else "by"], placed = str(mine[rel]), True
                    end = str(mine.get("end") or "").strip().casefold()
                    if end in ("far", "near"):
                        feature["end"] = end
                    if rel != "across" and _side(mine.get("side")):
                        feature["side"] = _side(mine.get("side"))
                    break
            by = str(mine.get("by") or "")
            if not placed and by == "entrance" and entrance_to in place["joins"] \
                    and entrance_to in way_ids and entrance_to != pid:
                # by the entrance, and joined to the way it opens onto: by
                # that way, at its near end. By the entrance where it opens
                # onto open ground: the ground at its step is kept clear
                # (`layout_solver._grounds`' aprons), and stood by the ground
                # instead a lantern went nineteen paces off (a review of
                # 2026-10-14)
                feature["by"], placed = entrance_to, True
                feature["end"] = "near"
            if not placed and by != pid and (
                    # by the entrance where its step can lie in the thing's
                    # ground: the entrance opens onto that ground, or onto a
                    # way -- never where it opens onto other open ground, which
                    # pulled a lantern to the garden's corner nearest a door
                    # onto the court, and it was dropped (the fuzz's seed 135)
                    (by == "entrance" and (not usable or entrance_to in place["joins"]
                                           or (ground_in is not None
                                               and entrance_to not in open_ids)))
                    or ((by in way_ids or by in feature_ids or by in building["rooms"]) and tied(by))):
                feature["by"], placed = by, True
            if placed and _side(mine.get("side")) and "by" in feature:
                # and on that side of it, where the answer says
                feature["side"] = _side(mine.get("side"))
            if not placed and _side(mine.get("side")):
                joined = next((o for o in usable if o in way_ids or o in feature_ids), None)
                if joined:
                    # a side of the building, answered of a thing the plan
                    # joins to a way or a thing: on that side of what it is
                    # joined to
                    feature["by"] = joined
                feature["side"], placed = _side(mine.get("side")), True
            if not placed and usable:
                # by what the plan joins it to -- open ground last, which it
                # then stands in: with no relation, a lantern joined to the
                # garden alone stood as far from everything as the plot
                # allowed, touching no garden (a review of 2026-10-14)
                feature["by"] = usable[0]
            if ground_in is not None:
                feature["in"] = ground_in
            features.append(feature)
        elif what == "outbuilding":
            joined_rooms = [o for o in place["joins"] if o in building["rooms"]]
            # the plan's walk to it from a room's door, where no room opens
            # onto it (`walks`): its own door opens onto that walk
            walk_in = None if joined_rooms else next(
                (o for o in place["joins"] if o in walks), None)
            # THE PLAN'S WAY TO IT IS THE FACT: an outbuilding a room opens
            # onto stands on the side the plan's way faces, the answer's side
            # only where the plan states none -- stood on the answer's other
            # side, its walk ran round the house and cut the ground in two (a
            # review of 2026-10-14)
            side = apart_side(pid, walk_in)
            opens = [o for o in place["joins"] if o in open_ids]
            if opens and not joined_rooms and walk_in is None:
                # AN OUTBUILDING STANDS ON THE OPEN GROUND THE PLAN JOINS IT
                # TO, on the side of the building that ground lies, toward
                # the end the plan bears it to, and opens onto it -- joined
                # to a walk the solver never laid, Home 10's storehouse stood
                # apart with no doorway at all
                area = opens[0]
                where = next((a["where"] for a in areas if a["id"] == area), None) \
                    or _side((said.get(area) or {}).get("where")) or plan_side.get(area)
                if where in _SIDES:
                    side = where
                if side is None:
                    del is_of[pid]
                    continue
                toward = bearing(area, pid)
                door_side = bearing(pid, area) or (_OPP[toward] if toward else None)
                join = {"to": area, "kind": "door"}
                if door_side:
                    join["side"] = door_side
                rooms.append({"id": pid, "name": place["name"], "level": 0, "block": pid,
                              "purpose": "other", "joins": [join],
                              "zones": [], "windows": [], "fixtures": []})
                block = {"id": pid, "apart": True, "beside": {"block": "main", "side": side}}
                if toward and toward not in (side, _OPP[side]):
                    block["toward"] = toward
                blocks.append(block)
                continue
            if side is None:
                del is_of[pid]
                continue
            walk = walk_in or f"{pid}__way"
            join = {"to": walk, "kind": "door"}
            if walk_in and bearing(pid, walk_in):
                # on the wall the plan states the walk meets it
                join["side"] = bearing(pid, walk_in)
            rooms.append({"id": pid, "name": place["name"], "level": 0, "block": pid,
                          "purpose": "other", "joins": [join],
                          "zones": [], "windows": [], "fixtures": []})
            block = {"id": pid, "apart": True, "beside": {"block": "main", "side": side}}
            # TOWARD ITS ROOM'S END OF THAT SIDE, as the plan lays the rooms
            # out from the entrance's: centred on its side, a privy south of
            # the washroom stood before the entrance, across the path, and
            # the gate at the path's foot was dropped (a review of 2026-10-14)
            # -- the room it is reached from, through the walk where it is
            reached_from = joined_rooms[0] if joined_rooms else walks.get(walk_in)
            toward = _toward_room(building, reached_from, side, answer)
            asked = _side(mine.get("side"))
            if not toward and side == front:
                # NEVER BEFORE THE ENTRANCE: with no end either way, one on
                # the entrance's side stands toward the end the answer names
                # across that side, else the end of the house its room stands
                # at, else past a corner -- centred there, a privy the plan
                # joins to the hall stood three paces before the entrance
                # door, and the floor dropped it (a review of 2026-10-14).
                # Elsewhere it stands centred, as before: at the end an
                # answer named, a privy crowded the byre at the corner, and
                # one of them was dropped (the fuzz's seeds 45 and 125)
                toward = (asked if asked and asked not in (side, _OPP[side]) else None) \
                    or _toward_room(building, reached_from, side, answer, middle=True) \
                    or _PAST_THE_CORNER[side]
            if toward:
                block["toward"] = toward
            blocks.append(block)
            if walk_in is None:
                ways.append({"id": walk, "name": place["name"]})
                door_to[pid] = walk
    stands_in = around
    if stands_in is None and feature_ids & direct and areas:
        # NO GROUND NO PLACE HOLDS: a thing at a door stands in the open
        # ground the plan joins to the most places, which then lies round
        # the building, never in solver ground no row is written for
        joins_of = {g["id"]: len(g["joins"]) for g in building.get("grounds") or ()}
        ranked = sorted(areas, key=lambda a: (-joins_of.get(a["id"], 0), a["id"]))
        ranked[0]["where"] = "around"
        stands_in = around = ranked[0]["id"]
    for pid in sorted(feature_ids & direct):
        if stands_in is None:
            areas.append({"id": GROUND_ID, "name": GROUND_ID, "kind": GROUND_AREA_KIND,
                          "where": "around"})
            stands_in = GROUND_ID
        # A THING THE PLAN JOINS TO A ROOM OF THE BUILDING STANDS AT A DOOR
        # OF THAT ROOM -- the plan's join is the fact, and wins over the
        # answer's relation: a well the plan joins to the kitchen stood a
        # pace off its threshold (the farm) or eighteen paces from it (Home
        # 11). THE DOOR IS ITS OWN: one door carrying two of the plan's ways
        # meets only one of them, so a second thing joined to the room, or
        # the room's own way onto the ground the thing stands in, cost the
        # other its doorway (a review of 2026-10-14)
        joined = sorted({o["room"] for o in building["outside"]
                         if o["to"] == pid and not o.get("vertical")})
        apart = [r for r in joined if _joined_apart(building, r, pid)]
        feature = next((f for f in features if f["id"] == pid), None)
        if feature is not None and joined and apart == joined and stands_in != GROUND_ID:
            # SAVE A THING THE PLAN JOINS TO ITS ROOMS ACROSS GROUND
            # (`_joined_apart`): it stands off their walls, where the
            # answer's relation puts it, and each room's door opens onto the
            # open ground it stands in, which reaches it (`ground_breaches`).
            # Pinned at the kitchen's door, the well the plan put `near` it
            # -- by the entrance, east of the path, the lore says, as the
            # answers did -- touched no path, and the floor dropped it. Where
            # the plan names no open ground (`GROUND_ID`, solver geometry
            # only) it stands at the door as before: a door onto ground no
            # row holds meets nothing.
            door_to[pid] = stands_in
            continue
        room = next((r for r in joined if r not in apart), joined[0] if joined else None)
        if not room or feature is None:
            door_to[pid] = stands_in
            continue
        for rel in ("across", "flank", "along", "by", "side", "end", "in"):
            feature.pop(rel, None)
        feature["at_door"] = {"room": room, "onto": stands_in}
        place = next(g for g in building.get("grounds") or () if g["id"] == pid)
        reach = [o for o in place["joins"] if o in way_ids]
        if reach:
            # and its door may turn so it reaches the way the plan also
            # joins it to (the solver's `REACH_MAX`)
            feature["reach"] = reach
    # A DOOR OF THE HOUSE ALWAYS OPENS ONTO SOMETHING. A place it opens
    # straight onto that the answers left nowhere -- open ground with no side
    # to lie on, an outbuilding with none to stand apart on -- is open ground
    # on its doorway's side, as the tier laid it before the grounds; a door
    # onto nothing would refuse every seed.
    held_ids = {x["id"] for x in areas + ways + features + rooms} | set(door_to)
    dropped = set(building.get("dropped_places") or ())
    for o in building["outside"]:
        pid = o["to"]
        if o.get("vertical") or pid in held_ids:
            continue
        held_ids.add(pid)
        if pid in dropped:
            # A PLACE TAKEN OUT OF THE GROUND (`without_places`) takes no
            # ground from the places left and asks no door of its own: the
            # room's way onto it is a door the room has already -- the
            # entrance, or its door onto another place -- and only a room
            # with none opens onto the ground the building stands in, or the
            # first ground left. Given a band of its own, Home 6's dropped
            # well took the garden's whole south side, and the path it ran
            # through then failed too; given a door of its own, a thing
            # dropped for want of a wall asked for one more, and the house was
            # refused (a review of 2026-10-14)
            target = _door_already(building, pid, dropped, door_to, entrance)
            target = target or stands_in or next((a["id"] for a in areas), None)
            if target:
                door_to[pid] = target
                continue
        areas.append({"id": pid, "name": o["name"], "kind": GROUND_AREA_KIND,
                      "where": o["side"] or "around"})
        if pid in ground_ids:
            is_of[pid] = "open"
        # a place that is no ground of this building, with no open ground the
        # building stands in, is ground in the solve alone, as every place was
        # before the grounds (`without_grounds`): its door opens onto
        # something, and nothing of it is written
    return {"areas": areas, "ways": ways, "features": features, "rooms": rooms,
            "blocks": blocks, "is": is_of, "door_to": door_to}


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


def solve_for(building, spec, attempts=None):
    """`(layout, refusals)`: the solve that stands for the plan, of
    `LAYOUT_SOLVE_SEEDS` seeds of the solver's search taken in order from its
    own (`layout_solver.SEED`), every one solved. Of the seeds the bridge
    does not refuse, one whose every stair lands in each room it joins
    (`unlanded`) is taken -- the one that turned the fewest of the sides
    asked of its joins (`turned_sides`), the earlier seed on a tie; failing
    that, the first the bridge does not refuse; failing every seed, the
    first seed's solve and its refusals, the building failing open as
    before. Each seed is deterministic, so a building solves the same way
    every time.

    The owner's shrine (chat 164, 2026-10-10), replicated: of twenty seeds,
    one answer set laid out with no refusal on fifteen, another on thirteen
    and a third, after its cross-block door was weighed as the refusal it
    is, on fifteen -- the solver's own seed among the failures more than
    once. A building refused on one seed but not on most is a building the
    search missed, not one the plan cannot hold.

    THE FIRST THAT STANDS IS NOT THE BEST THAT DOES. A side is a wish (the
    owner's ruling of 2026-10-10, "sides are wishes, like the lab"), so no
    seed is refused for turning one -- and the search took the first seed
    that stood whatever it turned, a later seed keeping more of what the
    plan and the answers asked never looked at. Measured on nine recorded
    answer sets of the owner's shrine (2026-10-15, relayed with no model):
    six stood on more than one seed with every stair landed, and on two the
    seed taken changed -- asked sides turned 5 of 6 to 1, rubric claims 23
    to 31 of 53, and 4 of 6 to 1, 21 to 23; none fell. Over the nine, 26 of
    58 asked sides turned to 19, for 60 solves where 44 were."""
    from world.layout_solver import SEED
    first = standing = best = None
    for k in range(LAYOUT_SOLVE_SEEDS):
        layout = solve(spec, seed=SEED + k)
        found = []
        refused = refusals(building, spec, layout, breaches=found)
        if attempts is not None:
            # every seed tried, with the floor's findings on it, for a caller
            # that chooses among the refused (`places_to_drop`)
            attempts.append((layout, refused, found))
        first = first or (layout, refused)
        if refused:
            continue
        standing = standing or (layout, refused)
        if unlanded(spec, layout):
            continue
        turned = turned_sides(spec, layout)
        if best is None or turned < best[0]:
            best = (turned, (layout, refused))
    return best[1] if best else standing or first


def turned_sides(spec, layout):
    """How many of the sides the spec asks of its joins -- the plan's
    stated, else the answer's -- this solve turned: a join whose doorway
    stands in another wall of its room than the side asked. Read off the
    layout's doors (`_door_side`), never its warnings; a join with no side
    asked, or with no doorway between its rooms, turns nothing."""
    n = 0
    for room in spec.get("rooms") or ():
        for j in room.get("joins") or ():
            asked = _side(j.get("side"))
            got = _door_side(layout, room["id"], j.get("to")) if asked else None
            n += got is not None and got != asked
    return n


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


def refusals(building, spec, layout, breaches=None):
    """Why this solve cannot stand for the plan, in words; empty when it can.
    Read off the layout's structure, never its warning sentences. The
    grounds floor's own findings, `(words, place)`, are added to `breaches`
    where a list is handed in, so a caller choosing places to take out
    never runs the floor twice on one seed (`places_to_drop`)."""
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
    entrance = entrance_of(building, spec=spec)
    outs = {(d["a"], d["b"]) for d in layout.doors if d.get("outside")}
    door_to = spec.get("door_to") or {}
    judged = set(spec.get("ground_is") or ()) if building.get("grounds") else set()
    for o in building["outside"]:
        target = door_to.get(o["to"], o["to"])
        if o["room"] == entrance.get("room") and entrance.get("to") in (o["to"], target):
            target = "entrance"
        if target != "entrance" and o["to"] in judged:
            # a doorway onto a place of the ground is the grounds floor's to
            # judge, which charges the place that fails, never the house
            # (`ground_breaches`): a thing whose own door found no wall
            # refused every seed for the house, and cost the whole ground
            continue
        if (o["room"], target) not in outs:
            out.append(f"{o['room']} has no doorway onto {o['to']}")
    # A ROOM'S SIZE IS NEVER A REFUSAL: the plan's `extent` is the Writers'
    # Room's estimate, which the solve replaces, filed beside it
    # (`planned_layout`; the owner's ruling of 2026-10-10). Until then a
    # solve a quarter off a planned size or side was refused (F47, review of
    # 2026-10-08 F2), and on the owner's shrine that was nearly every room.
    # NOR IS A SIDE: the owner's ruling of 2026-10-10, "sides are wishes,
    # like the lab". Before any room is described a side the Room planned is
    # weighed as the lab weighed every side, the solve may turn it, the turn
    # is filed beside the solve (`planned_layout`, `sides`, marked
    # `planned`), and the plan's own doorway moves to the wall the solve
    # chose (`structure.write_planned_layout`). Held as a fact, it refused all
    # three of the owner's refined shrine's answer sets, two for a washroom
    # the lab's own liked shrine had turned too.
    # AND THE GROUND HOLDS TOGETHER (`ground_breaches`): a solve whose ground
    # does not is refused like any other, so the search takes the next seed --
    # asked only of a house that stands, since the plan the floor reads needs
    # every room laid, and a solve it cannot read is refused, never raised
    # (a review of 2026-10-14: a floorless room aborted the seed search)
    if building.get("grounds") and not out:
        try:
            found = ground_breaches(building, spec, layout)
        except Exception as exc:
            out.append(f"the ground could not be read: {' '.join(str(exc).split())[:200]}")
        else:
            out += [words for words, _place in found]
            if breaches is not None:
                breaches.extend(found)
    return out


#: Which of two places of the ground that fail to meet gives way, where only
#: the failing places are dropped (`ground_breaches`): the thing, then the
#: building apart, then the way, then the open ground the rest stand on.
_GIVES_WAY = ("feature", "outbuilding", "way", "open")


def ground_breaches(building, spec, layout):
    """`[(words, place)]`: why the ground this solve would write does not
    hold together, each with the place of the ground that gives way for it
    (`_GIVES_WAY`); empty when it holds (design A6, Home 10's court cut in two
    and its storehouse standing apart with no doorway, chat 173).

    Read off the scene the solve WOULD write -- the very plan rows
    `structure.write_planned_layout` writes (`solved_plan_row`,
    `made_plan_row`), laid on the fringe's own stubs (`solved_scene`) -- through
    the world's own readers, never the solver's geometry: every ground place
    handed to the solver is laid; each is one floor; and every level way
    between two places laid on the plan with a ground place on either side
    has its two doorways on opposite walls, the cell beyond one being a
    doorway cell of the other -- save a join the plan states across ground
    between a room and a place (`_joined_apart`), whose room's doorway opens
    onto ground the place stands on. A window onto the ground is a
    sightline, no doorway. The building's own rooms and halls are the
    solver's to join and are not judged here."""
    from world.site_plan import room_level, room_site
    from world.spatial import _cells_connected, _door_cells, opposite_bearing, room_grid
    from world.structure import made_plan_row, solved_plan_row, solved_scene
    solved, report = planned_layout(building, spec, layout)
    is_of = spec.get("ground_is") or {}
    out = [(f"{pid} was given no ground", pid) for pid in report.get("grounds_unplaced") or ()]
    plan = dict(building.get("ground_specs") or {})
    plan.update(building.get("specs") or {})
    names = {g["id"]: g["name"] for g in building.get("grounds") or ()}
    names.update(building.get("names") or {})
    rows = {}
    for uid, solve in solved.items():
        if solve.get("room") is not None:
            row = made_plan_row(solve)
            rows[uid] = (str(row.get("name") or uid), row)
        elif uid in plan:
            rows[uid] = (names.get(uid, uid), solved_plan_row(plan[uid], solve))
    scene = solved_scene(rows)
    rooms = scene["rooms"]
    ground = {g["id"] for g in building.get("grounds") or ()} & set(rows) & set(is_of)
    laid = {uid for uid in rooms
            if (room_site(scene, uid) or {}).get("plan") == building["plan"]}
    on_plan = {}
    for uid in laid:
        site = room_site(scene, uid)
        on_plan[uid] = {(site["x"] + x, site["y"] + y) for x, y in room_grid(scene, uid).cells}

    def rank(p):
        return _GIVES_WAY.index(is_of[p]) if is_of.get(p) in _GIVES_WAY else len(_GIVES_WAY)

    # WHAT HANGS ON A PLACE: the places of the ground no chain of joins from
    # a room of the building would reach without it. Of two equally
    # particular places the one less hangs on gives way -- by id, the court
    # the entrance opens onto was charged for an orchard behind the house,
    # and taken out with everything reached through it (a review of
    # 2026-10-14)
    joins_of = {g["id"]: set(g.get("joins") or ()) for g in building.get("grounds") or ()}
    hung = {}

    def hung_on(p):
        """The places of the ground no chain of joins from a room reaches
        without `p`."""
        if p not in hung:
            got = set(building.get("rooms") or ())
            grew = True
            while grew:
                grew = False
                for q, js in joins_of.items():
                    if q != p and q not in got and js & got:
                        got.add(q)
                        grew = True
            hung[p] = {q for q in joins_of if q != p and q not in got}
        return hung[p]

    def hanging(p):
        return len(hung_on(p))

    # and the ground the entrance opens onto weighs most of all: by what hung
    # on them alone, the court the entrance opens onto was charged for a
    # yard's door it held (a review of 2026-10-14)
    entrance_to = entrance_of(building, spec=spec).get("to")

    def key(p):
        return (rank(p), hanging(p) + (len(joins_of) + 1 if p == entrance_to else 0), p)

    def particular(places):
        return min(places, key=key)

    def touches(p, q):
        return any((x + dx, y + dy) in on_plan.get(q, ()) for x, y in on_plan.get(p, ())
                   for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))

    # A CHARGE TO A THIRD PLACE -- the one standing on a door's ground,
    # between two places, or cutting one -- is void where a place the breach
    # is about is charged for a breach of its own: it goes, and the breach
    # with it (a court not one floor, and its step taken by a garden band:
    # both were dropped, though the court's going answered both; a review of
    # 2026-10-14). The breach still refuses the seed.
    third = {}
    apart = {}      # breaches a building apart is charged for, with its own place

    def charge(words, place, about):
        if place is not None and place not in about:
            third[len(out)] = tuple(about)
        elif place is not None and is_of.get(place) == "outbuilding" and len(about) == 2:
            apart[len(out)] = (place, next(x for x in about if x != place))
        out.append((words, place))

    def occupiers(room, there):
        """The places of the ground standing on the ground at the room's
        doorway onto `there` -- its step, the pace past it, and the paces
        either side of both, the ground the solver keeps for a door
        (`layout_solver._grounds`' aprons) -- that give way before `there`:
        more particular, or as particular with no more hanging on them (a
        band of open ground on the entrance's step was never charged, and
        the court the entrance opens onto was, with everything reached
        through it; a review of 2026-10-14)."""
        cells, wall = _door_cells(scene, room, there)
        site = room_site(scene, room)
        if not cells or wall not in _UNIT or not site:
            return []
        ux, uy = _UNIT[wall]
        lx, ly = (1, 0) if wall in "ns" else (0, 1)
        apron = {(site["x"] + x + ux * (1 + k) + lx * m, site["y"] + y + uy * (1 + k) + ly * m)
                 for x, y in cells for k in (0, 1) for m in (-1, 0, 1)}
        return [q for q in sorted(ground & laid) if q not in (room, there)
                and key(q)[:2] <= key(there)[:2] and on_plan.get(q, set()) & apron]

    area_ids = {a.get("id") for a in (spec.get("grounds") or {}).get("areas") or ()}
    on_line = {}        # a thing: the ways it stands across, or that lead to it
    for f in (spec.get("grounds") or {}).get("features") or ():
        if isinstance(f, dict) and f.get("across"):
            on_line.setdefault(f["id"], []).append(f["across"])
    for w in (spec.get("grounds") or {}).get("ways") or ():
        if isinstance(w, dict) and w.get("to"):
            on_line.setdefault(w["to"], []).append(w["id"])
    # the ways the ground is laid round: the approach, and a way leaving it
    first = {w["id"] for w in (spec.get("grounds") or {}).get("ways") or ()
             if isinstance(w, dict) and (w.get("from") in ("entrance", "door")
                                         or w.get("from") in area_ids)}
    for pid in sorted(ground & laid):
        cells = room_grid(scene, pid).cells
        if _cells_connected(cells):
            continue
        # A PLACE CUT IN TWO is charged to what cut it: a way, a walk, a
        # thing whose cells touch two of its parts (a review of 2026-10-14:
        # a privy's walk fenced off a pocket of garden, and the garden was
        # dropped with everything reached through it)
        parts = []
        left = set(on_plan[pid])
        while left:
            stack, part = [left.pop()], set()
            while stack:
                c = stack.pop()
                part.add(c)
                for n in ((c[0] + 1, c[1]), (c[0] - 1, c[1]), (c[0], c[1] + 1), (c[0], c[1] - 1)):
                    if n in left:
                        left.discard(n)
                        stack.append(n)
            parts.append(part)
        # WHAT CUT IT is the place whose own cells, given back, join its
        # parts up -- most of them, then the one laid last, then the most
        # particular; against a way, a building it was laid over gives back
        # nothing. A gate at the path's foot was charged for a walk that cut
        # the garden round the back of the house, and a storehouse for a lane
        # laid through it (a review of 2026-10-14).
        def block_of(q):
            cells = set()
            for rect in (layout.floors.get(0) or {}).get(q) or ():
                cells |= rect.cells()
            return cells

        def cells_of(q):
            if is_of.get(pid) == "way" and is_of.get(q) == "outbuilding":
                return on_plan[q] - block_of(q)
            if is_of.get(q) == "feature":
                # A THING ON A WAY'S LINE -- across it, or where it leads --
                # gets no credit for the cells on its lanes: they carry on
                # the way's own cut, and a gate at the path's foot was
                # charged for it before the path, spending a round (a review
                # of 2026-10-14)
                got = set(on_plan[q])
                for wid in on_line.get(q) or ():
                    w = layout.ways.get(wid)
                    if w and str(w.get("side") or "") in _UNIT:
                        k = 0 if w["side"] in ("n", "s") else 1
                        lanes = {c[k] for c in w["cells"]}
                        got = {c for c in got if c[k] not in lanes}
                return got
            return on_plan[q]

        def laid_late(q):
            # the solver's order: a building's block first, then the ways the
            # ground is laid round, the things, and last the walks and the
            # ways that branch: of two whose cells would join it up, the one
            # laid later cut it
            what = is_of.get(q)
            if what == "outbuilding":
                return 3 if components(on_plan[pid] | (on_plan[q] - block_of(q))) < len(parts) else 0
            if what == "way":
                return 1 if q in first else 3
            return 2

        def components(cells):
            left, n = set(cells), 0
            while left:
                n += 1
                stack = [left.pop()]
                while stack:
                    c = stack.pop()
                    for nb in ((c[0] + 1, c[1]), (c[0] - 1, c[1]), (c[0], c[1] + 1), (c[0], c[1] - 1)):
                        if nb in left:
                            left.discard(nb)
                            stack.append(nb)
            return n

        # never a cutter the cut place hangs on: taking it out takes the
        # place too, with everything hung on it -- a path cutting off a
        # pocket of the garden it alone reaches was charged, and the garden
        # and the oak went with it (a review of 2026-10-14)
        cutters = [q for q in sorted(ground & laid) if q != pid
                   and is_of.get(q) != "open" and pid not in hung_on(q)
                   and components(on_plan[pid] | cells_of(q)) < len(parts)]
        cutter = min(cutters, key=lambda q: (components(on_plan[pid] | cells_of(q)), -laid_late(q),
                                             key(q))) if cutters else pid
        charge(f"{pid} is not one floor", cutter, (pid,))

    def giving_way(a, b):
        return particular([p for p in (a, b) if p in ground])

    pairs, met = set(), []
    for uid in sorted(rooms):
        for edge in rooms[uid].get("adjacent") or ():
            if not isinstance(edge, dict) or edge.get("vertical"):
                continue
            to = str(edge.get("to") or "")
            if to in rooms and {uid, to} & ground and uid in laid and to in laid \
                    and str(edge.get("barrier") or "") != "window":
                pairs.add(tuple(sorted((uid, to))))
    for a, b in sorted(pairs):
        place = giving_way(a, b)
        if not ({a, b} <= ground):
            # A ROOM'S DOOR ONTO A PLACE OF THE GROUND keeps the ground at
            # its step for that place, and a more particular place standing on
            # it is charged -- the thing that took the open ground's step
            # gives way, never the open ground round the house (a review of
            # 2026-10-14: a lantern a pace below the entrance's step left it a
            # sliver no block held, and the court was charged)
            room, there = (a, b) if b in ground else (b, a)
            holders = occupiers(room, there)
            if holders:
                place = particular(holders)
        elif not touches(a, b):
            # TWO PLACES OF THE GROUND THAT DO NOT TOUCH, with a thing, a way
            # or a building between them that touches both: it gives way -- a
            # lantern on a way's mouth cost the way its meeting, and the way
            # was charged. Never open ground: a band beside the house touches
            # the ground before and behind it at the corners, stands between
            # nothing, and was charged round after round (two reviews of
            # 2026-10-14)
            between = [q for q in sorted(ground & laid) if q not in (a, b)
                       and is_of.get(q) != "open"
                       and key(q) < key(place) and touches(q, a) and touches(q, b)]
            if between:
                place = particular(between)
        if room_level(scene, a) != room_level(scene, b):
            charge(f"{a} and {b} are joined and do not stand on one storey", place, (a, b))
            continue
        if not ({a, b} <= ground) and _joined_apart(building, room, there):
            # A JOIN THE PLAN STATES ACROSS GROUND (`_joined_apart`) IS NO
            # WALL THE TWO SHARE: the room's doorway meets the ground across
            # its threshold -- the place itself, or open ground or a way the
            # place stands on -- and the place is reached across it. Judged
            # as a shared wall, a well the plan put `near` the kitchen held
            # only where it stood across the kitchen's door (2026-10-15)
            cells, wall = _door_cells(scene, room, there)
            site = room_site(scene, room)
            if not cells or wall not in _UNIT or not site:
                charge(f"{room} has no placed doorway onto {there}", place, (a, b))
                continue
            ux, uy = _UNIT[wall]
            steps = {(site["x"] + x + ux, site["y"] + y + uy) for x, y in cells}
            onto = [q for q in sorted(ground & laid) if on_plan.get(q, set()) & steps
                    and (q == there or is_of.get(q) in ("open", "way"))]
            if not any(q == there or touches(q, there) for q in onto):
                charge(f"{room}'s doorway onto {there} opens onto no ground {there} "
                       f"stands on", place, (a, b))
                continue
            met.append((a, b))
            continue
        da, wa = _door_cells(scene, a, b)
        db, wb = _door_cells(scene, b, a)
        if not da or wa not in _UNIT or not db or wb not in _UNIT:
            charge(f"{a} and {b} are joined and one has no placed doorway", place, (a, b))
            continue
        if wb != opposite_bearing(wa):
            charge(f"{a}'s doorway onto {b} is in its {wa} wall and {b}'s in its "
                   f"{wb} wall", place, (a, b))
            continue
        sa, sb = room_site(scene, a), room_site(scene, b)
        ux, uy = _UNIT[wa]
        front = {(x + ux, y + uy) for x, y in da}
        rel = (sb["x"] - sa["x"], sb["y"] - sa["y"])
        if not front & {(x + rel[0], y + rel[1]) for x, y in db}:
            charge(f"{a}'s doorway onto {b} does not meet {b}'s across the wall", place, (a, b))
            continue
        met.append((a, b))
    # A BUILDING APART CHARGED FOR ITS OWN DOORWAY goes with the place
    # standing on its step, where another breach of the seed charges that
    # place already: the yard band holding the court's step was charged, and
    # the byre whose door stepped into it was dropped beside it, though the
    # yard's going answered both. Never where nothing else charges it: a
    # band charged for every building whose door it held cost places a
    # building alone would not have (a review of 2026-10-14)
    charged = {p for _w, p in out if p is not None}
    for i, (p, there) in sorted(apart.items()):
        holders = (set(occupiers(p, there)) & charged) - {p} if there in ground else set()
        if holders:
            out[i] = (out[i][0], particular(holders))
            third[i] = (p, there)
    own = {p for i, (_w, p) in enumerate(out) if p is not None and i not in third}
    charged_away = []       # pairs that failed for a place neither of them is
    for i, about in third.items():
        if own & set(about):
            out[i] = (out[i][0], None)
        elif len(about) == 2:
            charged_away.append(about)
    # AND EVERY PLACE IS REACHED from a room of the building through doorways
    # that meet: a place whose ways all failed, or lead only to places that
    # are not laid, stands where nothing reaches it. Charged to itself only
    # where nothing else explains it: a place reached once the places
    # charged for a failing pair it does not belong to are taken out is
    # refused here, and taken out by nobody (place None) -- the court whose
    # step a lantern took left the lane and the shed reached from no room,
    # and both were dropped beside the lantern (a review of 2026-10-14)
    def reach(ways):
        got = set(building.get("rooms") or ()) & laid
        grew = True
        while grew:
            grew = False
            for a, b in ways:
                if (a in got) != (b in got):
                    got |= {a, b}
                    grew = True
        return got

    reached, assumed = reach(met), reach(met + charged_away)
    failed = {place for _words, place in out}
    for pid in sorted((ground & laid) - reached - failed):
        out.append((f"{pid} is reached from no room of the building",
                    None if pid in assumed else pid))
    return out


def places_to_drop(building, spec, attempts):
    """`(places, words)`: the places of the ground to take out after every
    seed in `attempts` (`solve_for`'s) was refused -- those of the seed whose
    refusals are the ground's alone and that fails on the fewest places, the
    earliest such seed on a tie; nothing where every seed is refused for the
    house itself. A first seed refused for the house cost the whole ground,
    and one failing more places than another dropped places another lays (a
    review of 2026-10-14)."""
    best = None
    for k, attempt in enumerate(attempts or ()):
        layout, refused = attempt[0], attempt[1]
        if len(attempt) > 2:
            breaches = attempt[2]       # the floor's findings `solve_for` kept
        else:
            try:
                breaches = ground_breaches(building, spec, layout)
            except Exception:
                continue
        words = [w for w, _p in breaches]
        places = sorted({p for _w, p in breaches if p})
        if not places or any(r not in words for r in refused):
            continue
        key = (len(places), len(breaches), k)
        if best is None or key < best[0]:
            best = (key, places, words)
    return (best[1], best[2]) if best else ([], [])


# the end of a side of the house an outbuilding stands toward where nothing
# names one: the solver's own order for blocks that would crowd
# (`layout_solver`'s apart blocks)
_PAST_THE_CORNER = {"n": "e", "s": "e", "e": "s", "w": "s"}


def _toward_room(building, room, side, answer=None, middle=False):
    """The end of the house's `side` that `room` lies toward, as the plan's
    own bearings lay the rooms out from the entrance's room -- each join a
    pace on its stated side, the answer's where the plan states none, as the
    spec reads it (`spec_from_answers`) -- or None where neither says either
    way. With `middle`, a room in line with the entrance's lies toward the
    end of the house it stands at, measured from the middle of the rooms."""
    start = (building.get("entrance") or {}).get("room")
    if not room or not start or side not in _SIDES:
        return None
    asked = {}
    for raw in (answer or {}).get("rooms") or ():
        if isinstance(raw, dict):
            for j in raw.get("joins") or ():
                if isinstance(j, dict) and _side(j.get("side")):
                    asked.setdefault((str(raw.get("id") or ""), str(j.get("to") or "")),
                                     _side(j.get("side")))
    at, queue = {start: (0, 0)}, [start]
    while queue:
        a = queue.pop(0)
        for j in building.get("joins") or ():
            if a not in (j["a"], j["b"]):
                continue
            stated = j.get("side") if j.get("side") in _UNIT else None
            if stated is None:
                back = asked.get((j["b"], j["a"]))
                stated = asked.get((j["a"], j["b"])) or (_OPP[back] if back else None)
            if stated is None:
                continue
            b = j["b"] if j["a"] == a else j["a"]
            if b in at:
                continue
            ux, uy = _UNIT[stated] if j["a"] == a else _UNIT[_OPP[stated]]
            at[b] = (at[a][0] + ux, at[a][1] + uy)
            queue.append(b)
    axis = 0 if side in ("n", "s") else 1
    off = at.get(room, (0, 0))[axis]
    if off == 0 and middle and room in at:
        # in line with the entrance's room -- most often the entrance's room
        # itself: the end of the house it lies at, from the middle of the
        # rooms laid out: a privy the hall opens onto, stood past the far
        # corner, had its walk run round the whole front from the hall's
        # other wall and cut the court off from the door (a review of
        # 2026-10-14)
        off = at[room][axis] - sum(p[axis] for p in at.values()) / len(at)
    if axis == 0:
        return "e" if off > 0 else ("w" if off < 0 else None)
    return "s" if off > 0 else ("n" if off < 0 else None)


def _door_already(building, pid, dropped, door_to, entrance):
    """The door a room already has that its way onto `pid`, a place taken out
    of the ground, opens through: the entrance, for the entrance's own room;
    else its door onto another place it is joined to. None where `pid` is
    joined to more rooms than one, or its room has no other door."""
    rooms = sorted({o["room"] for o in building["outside"]
                    if o["to"] == pid and not o.get("vertical")})
    if len(rooms) != 1:
        return None
    room = rooms[0]
    if entrance and room == entrance.get("room"):
        return "entrance"
    for o in sorted(building["outside"], key=lambda x: x["to"]):
        if o["room"] == room and o["to"] != pid and o["to"] not in dropped \
                and not o.get("vertical"):
            return door_to.get(o["to"], o["to"])
    return None


def without_places(building, places):
    """The building with the places `places` taken out of its grounds -- and
    out of every other place's joins -- and every door of the house onto one
    kept: each such place stays as the plan had it, as every place did before
    the grounds (`without_grounds`, for all of them at once). A place of the
    ground no chain of joins from a room of the building reaches any more
    goes with them: nothing would reach it (Home 6's torii, joined to the
    lantern path alone, was laid in the plot's far corner once the path was
    taken out)."""
    gone = set(places)
    # what no chain of joins from a room of the building reaches any more:
    # a pair of places joined only to each other stood stranded together
    joins = {g["id"]: set(g.get("joins") or ()) for g in building.get("grounds") or ()}
    reached = set(building.get("rooms") or ())
    grew = True
    while grew:
        grew = False
        for pid in set(joins) - gone - reached:
            if joins[pid] & reached:
                reached.add(pid)
                grew = True
    gone |= set(joins) - reached
    out = dict(building)
    # what was taken out, for the door onto it (`_ground_plan`)
    out["dropped_places"] = sorted(set(building.get("dropped_places") or ()) | gone)
    out["grounds"] = [dict(g, joins=[o for o in g.get("joins") or () if o not in gone])
                      for g in building.get("grounds") or () if g["id"] not in gone]
    out["ground_specs"] = {pid: spec for pid, spec in (building.get("ground_specs") or {}).items()
                           if pid not in gone}
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


def _outside_side(layout, building, o, door_to=None, entrance=None):
    """The wall a building room opens onto the ground outside through --
    onto what the place stands in, or the way to it, where the grounds were
    laid out with the building (`_ground_plan`)."""
    entrance = entrance if entrance is not None else (building["entrance"] or {})
    target = (door_to or {}).get(o["to"], o["to"])
    if o["room"] == entrance.get("room") and entrance.get("to") in (o["to"], target):
        target = "entrance"
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
    held_floors = {str(r.get("id")): r["floor"] for r in (inventory or {}).get("rooms") or ()
                   if isinstance(r, dict) and r.get("floor")}
    for uid in building["rooms"]:
        r = rects[uid]
        geometry = {"extent": {"w": r.w, "d": r.d}, "shape": SOLVED_SHAPE, "level": levels[uid],
                    "site": {"plan": building["plan"], "x": r.x, "y": r.y,
                             "elev_m": round(levels[uid] * STOREY_M, 2)}}
        if uid in (building.get("own_blocks") or {}) or uid in (building.get("boxed") or ()):
            # its own block, or a shape that names no parts: where it stands
            # and how large are the solve's, its shape word the plan's --
            # never squared
            geometry.pop("shape")
        out[uid] = {"geometry": geometry, "anchors": {}, "edges": {},
                    "record": {"moved": [], "unplaced": []}}
        # THE FLOOR THE FIRST CALL READ IN THE LORE, where the plan states
        # none: never a fixture standing on it (`hold_inventory`)
        floor = held_floors.get(uid)
        if floor and not str(building["specs"][uid].get("floor") or "").strip():
            geometry["floor"] = floor
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
    # FIXTURES: pinned where the solver stood them, the ones it moved off the
    # place the model named included -- the map draws what the layout lab
    # draws (owner, 2026-10-13: "match layout lab ... stop overlapping
    # furnitures"). A move is never silent: it is listed in the record. Only
    # a fixture the solver could not place at all has no place to pin.
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
            # WHAT THE SOLVER TOOK IT FOR, kept on the anchor so a plan of the
            # building can draw it as the layout lab does (a bed with its
            # pillow, a stove with its burners); never read as what it IS --
            # that is its `desc`, the plan's word
            drawn = kind or str(f.get("kind") or "").strip().casefold().replace(" ", "_")
            flush = [s for s in _SIDES if _flush(room, rect, s)]
            if at and at != "walls" and not _stands_at(room, rect, at, kind):
                # MOVED, AND PINNED WHERE THE SOLVER STOOD IT. Written back
                # unpinned on the wall that could not hold it, the engine's
                # read-time placement found no clear place there either, and
                # laid it on a doorway or another fixture: Home 11's closet on
                # the genkan's doorway, its stove in the tub, its futon under
                # the trunk (review of 2026-10-13). Its `dir` is the wall it
                # stands against, never the one that was asked; the record
                # keeps both, and a designer re-settles it by its `cell`.
                moved = {"room": uid, "anchor": aid, "name": f.get("name") or aid,
                         "asked": at, "solver_put_it": "/".join(flush or ["middle"])}
                report["moved"].append(moved)
                out[uid]["record"]["moved"].append(moved)
                side = flush[0] if len(flush) == 1 else None
            elif at in _SIDES:
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
            if drawn:
                anchor["kind"] = drawn
            if side:
                anchor["dir"] = side
            out[uid]["anchors"][aid] = anchor
        for f in (spec_rooms.get(uid) or {}).get("fixtures") or ():
            mount = str(f.get("mount") or "floor")
            if mount != "floor":
                # on a wall, from the ceiling, in a fixture: the solver lays
                # none of these. One the plan lists keeps its record, which
                # read time would otherwise lay as a thing standing on the
                # floor; its mount says it is not one
                for fid in ([f["id"]] if int(f.get("count") or 1) == 1
                            else [f"{f['id']}_{i + 1}" for i in range(int(f.get("count") or 1))]):
                    aid = _written_id(uid, fid, asked, plan_ids[uid])
                    if aid in plan_ids[uid]:
                        out[uid]["anchors"][aid] = {"mount": mount}
                continue
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
                drawn = str(f.get("kind") or "").strip().casefold().replace(" ", "_")
                if drawn:
                    anchor["kind"] = drawn
                if at in _SIDES:
                    anchor["dir"] = at
                elif at in _CORNERS:
                    anchor["dir"] = at[7:]
                out[uid]["anchors"][aid] = anchor
                left = {"room": uid, "anchor": aid, "name": f.get("name") or aid, "asked": at or ""}
                report["unplaced"].append(left)
                out[uid]["record"]["unplaced"].append(left)
    # WINDOWS: each in its wall, the room's own (module docstring) -- laid
    # below, once the ground beyond them is (ONTO THE GROUND)
    names = {}
    for uid, sroom in spec_rooms.items():
        for w in sroom.get("windows") or ():
            names[(uid, w["id"])] = w
    laid_windows = []
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
            # the plan named them under one record, whose words for the
            # group go to the solve's record (`SPLIT`, below)
            if base_id in plan_ids[uid]:
                if aid == _slug(f"{base_id}_1"):
                    aid = base_id
                splits.setdefault((uid, base_id), []).append(aid)
            desc = str(base.get("name") or base_id or "window")
        else:
            desc = _window_desc(building, uid, base_id, base)
        if base_id in plan_ids[uid]:
            # A RECORD OF THE PLAN THAT IS A WINDOW is no anchor once the
            # window is laid: taken off the plan, and off its stub
            # (`structure._lay_stub_on_its_plan`), never left standing
            # among the furniture beside the window it was
            out[uid].setdefault("windows_from", set()).add(base_id)
        laid_windows.append({"room": uid, "id": aid, "dir": win["side"],
                             "cell": (int(win["cell"][0]), int(win["cell"][1])),
                             "name": desc})
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
    entrance = entrance_of(building, spec=spec)
    door_to = spec.get("door_to") or {}
    for door in layout.doors:
        a, b, side, cell = door["a"], door["b"], door["side"], door["cell"]
        if a in out and b in out:
            out[a]["edges"][b] = {"dir": side, "offset": _offset(rects[a], side, cell)}
            dx, dy = _STEP[side]
            there = (cell[0] + dx, cell[1] + dy)
            out[b]["edges"][a] = {"dir": opposite_bearing(side),
                                  "offset": _offset(rects[b], opposite_bearing(side), there)}
        elif a in out and door.get("outside"):
            if b == "entrance":
                # and to a place taken out whose way opens through it
                # (`_door_already`)
                tos = [entrance.get("to")] + [
                    o["to"] for o in building["outside"]
                    if o["room"] == a and o["to"] != entrance.get("to")
                    and door_to.get(o["to"]) in ("entrance", entrance.get("to"))]
            else:
                # a door onto the ground the place stands in, or the way to
                # it (`_ground_plan`), is the doorway to the place the plan
                # names
                tos = [o["to"] for o in building["outside"]
                       if o["room"] == a and door_to.get(o["to"], o["to"]) == b] or [b]
            for to in tos:
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
    made_halls = _stair_halls(building, layout, rects, levels, halls, out)
    report["halls"] = [{"hall": entry["uid"], "serves": sorted(entry["serves"])}
                       for _hall, entry in sorted(made_halls.items())]
    for st in spec.get("stairs") or ():
        well = next((w for w in layout.stairwells
                     if w["id"] == shaft_of.get(st["id"])), None)
        through = [made_halls.get((well or {}).get("halls", {}).get(str(levels.get(r))), {})
                   for r in (st["from"], st["to"])]
        if all(room in hall.get("serves", ()) for room, hall in zip((st["from"], st["to"]), through)) \
                and st["from"] in out and st["to"] in out:
            # the way through the halls, every piece laid: the plan's own
            # stair between the two rooms is replaced by it
            out[st["from"]].setdefault("replaced", set()).add(st["to"])
            out[st["to"]].setdefault("replaced", set()).add(st["from"])
            continue
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
    # DOORWAYS ON ANOTHER WALL THAN ASKED: the solver's arrangement to
    # settle, a side the Room planned as much as one the model chose (the
    # owner's ruling of 2026-10-10), and said rather than made silently --
    # the Room's own marked `planned`, its doorway written on the wall the
    # solve chose
    report["sides"] = []
    planned_sides = {}
    for j in building["joins"]:
        if j["side"]:
            planned_sides[(j["a"], j["b"])] = j["side"]
            planned_sides[(j["b"], j["a"])] = _OPP[j["side"]]
    for o in building["outside"]:
        if o["side"]:
            planned_sides[(o["room"], o["to"])] = o["side"]
    asked_sides = [(sroom["id"], j["to"], j.get("side")) for sroom in spec.get("rooms") or ()
                   for j in sroom.get("joins") or () if j.get("side")]
    if entrance:
        asked_sides.append((entrance["room"], entrance["to"], spec.get("front")))
    plan_outside = {o["to"] for o in building["outside"]} | {entrance.get("to")}
    # a join onto what a place stands in, or the way to it (`_ground_plan`),
    # is the doorway to the place the plan names
    plan_to = {}
    for o in building["outside"]:
        plan_to.setdefault((o["room"], door_to.get(o["to"], o["to"])), o["to"])
    for room_id, to, asked_side in asked_sides:
        if to in out:
            got = _door_side(layout, room_id, to)
        else:
            to = plan_to.get((room_id, to), to)
            if to not in plan_outside:
                continue
            got = _outside_side(layout, building, {"room": room_id, "to": to}, door_to, entrance)
        if got and asked_side and got != asked_side:
            entry = {"room": room_id, "to": to, "asked": asked_side, "solved": got}
            if planned_sides.get((room_id, to)) == asked_side:
                entry["planned"] = True
            report["sides"].append(entry)
            if room_id in out:
                out[room_id]["record"].setdefault("sides", []).append(entry)
    # THE GROUNDS (`_ground_geometry`): each place where the solve laid it
    if building.get("grounds"):
        laid, missed = _ground_geometry(building, spec, layout)
        report["grounds"], report["grounds_unplaced"] = [], missed
        for pid, geometry in laid.items():
            what = (spec.get("ground_is") or {}).get(pid)
            out[pid] = {"geometry": geometry, "anchors": {}, "edges": {},
                        "record": {"moved": [], "unplaced": [], "grounds": what}}
            report["grounds"].append({"place": pid, "is": what, "extent": geometry["extent"]})
            # THE ROOM'S ESTIMATE IS FILED AGAINST THE SOLVE, as a room's
            # is -- and carried from the record an earlier solve of this
            # ground filed, since the row it reads now holds that solve
            planned = (building.get("ground_specs") or {}).get(pid) or {}
            record = planned.get("layout") if isinstance(planned.get("layout"), dict) else None
            if record is not None:
                # a row an earlier solve wrote holds that solve's extent: the
                # Room's estimate is the record's, or none was stated -- read
                # off the row, every re-solve filed the last solve's extent as
                # the Room's (a review of 2026-10-14)
                earlier = record.get("stated")
                stated = (earlier["w"], earlier["d"]) if isinstance(earlier, dict) \
                    and earlier.get("w") and earlier.get("d") else None
            else:
                stated = _stated_sides(planned)
            if stated is not None:
                out[pid]["record"]["stated"] = {"w": stated[0], "d": stated[1]}
                report["stated"].append({"room": pid, "stated": {"w": stated[0], "d": stated[1]},
                                         "solved": dict(geometry["extent"])})
        for door in layout.doors:
            # AN OUTBUILDING'S OWN DOOR ONTO THE OPEN GROUND IT STANDS ON is
            # its doorway to that ground. Its door onto its walk to the house
            # is no doorway: the walk is its own floor (`_ground_geometry`),
            # and its doorway to the house room is that room's door, across
            # its threshold (`_ground_doorways`)
            a = door["a"]
            if a in laid and door.get("outside") and door["b"] in laid and door["side"] in _UNIT:
                out[a]["edges"][door["b"]] = _ground_pin(laid[a], tuple(door["cell"]), door["side"])
        _ground_doorways(building, spec, layout, laid, out)
    # ONTO THE GROUND: a window with open ground the solve laid beyond it is
    # that ground's window edge; every other window a record in its room's
    # `windows` (module docstring). ONE EDGE A PAIR OF ROOMS: a room with a
    # way to that ground already -- a door out, in the plan or the solve --
    # or a window onto it laid first keeps this one in its wall.
    beyond = _ground_cells(building, spec, laid) if building.get("grounds") else {}
    joined = _plan_joins(building)
    report["windows"] = []
    for window in laid_windows:
        uid, side, cell = window["room"], window["dir"], window["cell"]
        hit = _ground_beyond(window, rects, levels, beyond)
        onto = hit[0] if hit else None
        mine = out[uid].setdefault("made_edges", {})
        if onto and onto in out and onto not in out[uid]["edges"] \
                and uid not in out[onto]["edges"] and onto not in mine \
                and frozenset((uid, onto)) not in joined:
            mine[onto] = {"barrier": "window", "dir": side,
                          "offset": _offset(rects[uid], side, cell), "name": window["name"]}
            pin = _ground_pin(laid[onto], hit[1], _OPP[side])
            out[onto].setdefault("made_edges", {})[uid] = dict(
                {"barrier": "window", "name": window["name"]}, **pin)
            report["windows"].append({"room": uid, "window": window["id"], "onto": onto})
            continue
        room = rects[uid]
        out[uid]["geometry"].setdefault("windows", []).append({
            "id": window["id"], "dir": side,
            "cell": [cell[0] - room.x, cell[1] - room.y], "name": window["name"]})
        report["windows"].append({"room": uid, "window": window["id"], "onto": None})
    for uid in building["rooms"]:
        # none laid is none held: an earlier solve's go with it
        out[uid]["geometry"].setdefault("windows", None)
    # A WAY ONE SIDE ALONE DECLARES is one doorway however many sides declare
    # it: the solve's place for it on the side that declares nothing is a way
    # of the solve's own, written beside the plan's (`made_edges`, so a
    # re-solve takes it back) with the declaring side's barrier -- written as
    # a move onto an edge the row lacks, it was thrown away, and the place
    # stood with a bare doorway that met nothing (a review of 2026-10-14)
    plans = dict(building.get("ground_specs") or {})
    plans.update(building.get("specs") or {})
    def made_before(uid):
        record = (plans.get(uid) or {}).get("layout")
        return {str(t) for t in (record.get("made_edges") or ())} \
            if isinstance(record, dict) else set()

    for uid in out:
        if out[uid].get("room") is not None or not isinstance(plans.get(uid), dict):
            continue
        # an edge an earlier solve made declares nothing: read as declared,
        # the re-solve wrote its pin as a move, the merge took the earlier
        # way back, and the place was dropped on every other solve
        mine = made_before(uid)
        declared = {str(e.get("to") or "") for e in plans[uid].get("adjacent") or ()
                    if isinstance(e, dict) and str(e.get("to") or "") not in mine}
        for to in [t for t in out[uid]["edges"] if t not in declared]:
            fields = out[uid]["edges"].pop(to)
            back = next((e for e in (plans.get(to) or {}).get("adjacent") or ()
                         if isinstance(e, dict) and str(e.get("to") or "") == uid
                         and uid not in made_before(to)), {})
            # its pin as the solve gives it, a field None included: a way
            # made again over an earlier solve's pin replaces it (a review of
            # 2026-10-14: the old cell stayed beside the new offset)
            out[uid].setdefault("made_edges", {})[to] = dict(
                {k: back[k] for k in ("barrier", "material") if back.get(k)}, **fields)
    for uid in out:
        record = out[uid]["record"]
        out[uid]["layout"] = {"plan": building["plan"], "turn": turn,
                              "moved": record["moved"], "unplaced": record["unplaced"],
                              "sides": record.get("sides", [])}
        # what the solver took the room for, from its closed set -- a hall a
        # stair -- so a plan of the building can colour it as the lab does
        purpose = "stair" if out[uid].get("room") else str(
            (spec_rooms.get(uid) or {}).get("purpose") or "")
        if purpose:
            out[uid]["layout"]["purpose"] = purpose
        for key in ("stated", "described_m2", "restored", "split", "grounds"):
            if key in record:
                out[uid]["layout"][key] = record[key]
        # the ways the solve itself made -- a hall's, a window's onto the
        # ground -- the plan's own stairs those replace, and the records of
        # the plan it laid as windows, so a re-solve and a re-plan take back
        # exactly these (`structure.write_planned_layout`,
        # `structure._take_the_solve_off`)
        if out[uid].get("made_edges"):
            out[uid]["layout"]["made_edges"] = sorted(out[uid]["made_edges"])
        if out[uid].get("replaced"):
            out[uid]["layout"]["replaced"] = sorted(out[uid].pop("replaced"))
        if out[uid].get("windows_from"):
            out[uid]["layout"]["windows_from"] = sorted(out[uid].pop("windows_from"))
        del out[uid]["record"]
    return out, report


def _cover(cells):
    """`(kept, rects)`: the cells of `cells` some two-by-two block of them
    holds, and rectangles none narrower than two paces whose union is
    exactly those cells -- each row's run of block origins, merged downward
    while the run below matches; rectangles may overlap, as a composite's
    parts may.

    THE WORLD READS NO PART NARROWER THAN TWO PACES. A part's sides take the
    extent clamp (`spatial_fov.normalize_parts`, `EXTENT_MIN_PACES`), so a
    one-pace band of garden written as a part is read two deep -- over the
    house beside it, and the garden's grid then sees across the house's
    floor. A cell no block holds is a sliver between two places and is no
    place's: left off, never read as something it is not."""
    origins = {(x, y) for x, y in cells
               if {(x + 1, y), (x, y + 1), (x + 1, y + 1)} <= cells}
    kept = set()
    for x, y in origins:
        kept |= {(x, y), (x + 1, y), (x, y + 1), (x + 1, y + 1)}
    rows = {}
    for x, y in origins:
        rows.setdefault(y, []).append(x)
    rects = []
    for y in sorted(rows):
        xs = sorted(rows[y])
        start = prev = xs[0]
        for x in xs[1:] + [None]:
            if x is not None and x == prev + 1:
                prev = x
                continue
            w = prev - start + 2
            above = next((r for r in rects if r["x"] == start and r["w"] == w
                          and r["y"] + r["d"] - 1 == y), None)
            if above is not None:
                above["d"] += 1
            else:
                rects.append({"x": start, "y": y, "w": w, "d": 2})
            if x is not None:
                start = prev = x
    return kept, sorted(rects, key=lambda r: (r["y"], r["x"]))


def _widened(x, y, w, d, blocked):
    """The cells of a rectangle one pace thick made two, over the row or
    column beside it that no other place holds (`blocked`): east or south
    first, then west or north. A thing the solver lays a pace across -- a
    lantern, a statue, a gate -- is a place a body stands at here, and the
    world reads no place narrower than two paces (`EXTENT_MIN_PACES`)."""
    cells = {(x + i, y + j) for i in range(w) for j in range(d)}
    if w < 2:
        for nx in (x + w, x - 1):
            add = {(nx, y + j) for j in range(d)}
            if not add & blocked:
                cells |= add
                x, w = min(x, nx), w + 1
                break
    if d < 2:
        for ny in (y + d, y - 1):
            add = {(x + i, ny) for i in range(w)}
            if not add & blocked:
                cells |= add
                d += 1
                break
    return cells


def _rect_cells(x, y, w, d):
    return {(x + i, y + j) for i in range(w) for j in range(d)}


#: Which place a cell is, where the solve laid two on it: the solver's open
#: ground is the ground its ways and features stand on, and as rooms each
#: cell is one place's -- the privy, then the tree, then the path, then the
#: garden round them.
_GROUND_CLAIMS = ("outbuilding", "feature", "way", "open")


def _ground_geometry(building, spec, layout):
    """`({place id: geometry}, [ids not laid])`: each outdoor place where the
    solve laid it, on the building's plan, on the ground storey. Open
    ground and a way are the cells the solve gave them -- one rectangle, or a
    composite whose parts are those cells, the house standing in its hole
    (`site_plan`: "a garden can be a composite room whose cells surround a
    house's footprint"); a feature the rectangle it stands on, and a planned
    round one keeps its shape in it; an outbuilding its block's room.

    ONE PLACE A CELL. The solver lays its ways and features ON its open
    ground, as the lab converter's one grounds room carried them; laid as
    rooms of their own they are taken out of the ground they stand on
    (`_GROUND_CLAIMS`), so a body at the oak stands at the oak and not in
    the garden too. AND EVERY PLACE AS THE WORLD READS IT: no side or part
    narrower than two paces (`_widened`, `_cover`). A place the solve gave
    no ground of its own is not written: it stays where the plan had it."""
    is_of = spec.get("ground_is") or {}
    drawn = layout.as_dict()
    places = {g["id"] for g in building.get("grounds") or ()}
    raw = {}
    for place in building.get("grounds") or ():
        pid = place["id"]
        what = is_of.get(pid)
        if what == "open":
            rects = drawn["areas"].get(pid) or []
        elif what == "way":
            rects = (drawn["ways"].get(pid) or {}).get("rects") or []
        elif what == "feature":
            # one thing, or the pair or row the solver lays for `flank` and
            # `along` under `<id>_<n>` -- never another place's own id
            rects = [f["rect"] for f in drawn["features"]
                     if f["id"] == pid or (f["id"] not in places
                                           and re.fullmatch(re.escape(pid) + r"_\d+", str(f["id"])))]
        elif what == "outbuilding":
            rects = [r.as_dict() for r in (layout.floors.get(0) or {}).get(pid) or ()]
            # ITS WALK TO THE HOUSE IS ITS OWN FLOOR: the roofed way from a
            # back door to a privy apart, which no row was ever written for,
            # so the house door opened onto ground and the privy's own
            # doorway faced away from it (the farm's privy, n against n)
            rects += (drawn["ways"].get(f"{pid}__way") or {}).get("rects") or []
        else:
            continue
        raw[pid] = [(int(r["x"]), int(r["y"]), int(r["w"]), int(r["d"])) for r in rects
                    if int(r.get("w") or 0) > 0 and int(r.get("d") or 0) > 0]
    # the building's own rooms and stair halls on the ground storey
    solid = set()
    for rid, rs in (layout.floors.get(0) or {}).items():
        if rid not in places:
            for r in rs:
                solid |= _rect_cells(r.x, r.y, r.w, r.d)
    drawn_of = {pid: set().union(*(_rect_cells(*r) for r in rs)) if rs else set()
                for pid, rs in raw.items()}
    claimed, laid, missed = set(), {}, []
    for pid in sorted(raw, key=lambda q: _GROUND_CLAIMS.index(is_of[q])):
        what = is_of[pid]
        others = set().union(*(cells for q, cells in drawn_of.items()
                               if q != pid and is_of[q] != "open")) if drawn_of else set()
        cells = set()
        for rect in raw[pid]:
            if what in ("feature", "outbuilding"):
                cells |= _widened(*rect, blocked=claimed | solid | others)
            else:
                cells |= _rect_cells(*rect)
        kept, rects = _cover(cells - claimed - solid)
        if not kept:
            missed.append(pid)
            continue
        claimed |= kept
        x0, y0 = min(r["x"] for r in rects), min(r["y"] for r in rects)
        x1 = max(r["x"] + r["w"] for r in rects)
        y1 = max(r["y"] + r["d"] for r in rects)
        geometry = {"extent": {"w": x1 - x0, "d": y1 - y0}, "level": 0,
                    "site": {"plan": building["plan"], "x": x0, "y": y0, "elev_m": 0.0}}
        if len(rects) > 1:
            geometry["shape"] = "composite"
            geometry["parts"] = [{"w": r["w"], "d": r["d"], "at": [r["x"] - x0, r["y"] - y0]}
                                 for r in rects]
        else:
            # one rectangle has no parts: None takes any an earlier solve
            # wrote off the row (`structure.write_planned_layout`)
            geometry["parts"] = None
            shape = next((g["shape"] for g in building["grounds"] if g["id"] == pid), "")
            if shape in ("", SOLVED_SHAPE, "composite", "l"):
                geometry["shape"] = SOLVED_SHAPE
        laid[pid] = geometry
    order = [g["id"] for g in building.get("grounds") or ()]
    return {pid: laid[pid] for pid in order if pid in laid}, missed


_UNIT = {"n": (0, -1), "s": (0, 1), "e": (1, 0), "w": (-1, 0)}


def _world_cells(building, pid, geometry):
    """A laid place's cells on its plan AS THE WORLD READS THEM
    (`spatial_fov.room_grid` over the stub the plan lays): a round thing's
    circle in its solved box, never the box's corners -- Home 6's camphor
    tree had its doorway pinned on a corner its circle does not hold."""
    from world.spatial import room_grid
    planned = (building.get("ground_specs") or {}).get(pid) or {}
    stub = {"name": pid, **{k: v for k, v in geometry.items() if v is not None}}
    if "shape" not in stub:
        stub["shape"] = str(planned.get("shape") or SOLVED_SHAPE)
    site = geometry["site"]
    grid = room_grid({"rooms": {pid: stub}}, pid)
    return {(site["x"] + x, site["y"] + y) for x, y in grid.cells}


def _ground_pin(geometry, cell, side):
    """A doorway of a laid place at plan cell `cell` on its `side`: a place
    along that wall on a rectangle, as every doorway of the building's rooms
    is written; its cell on anything else, where "the north wall" is several
    walls (`spatial_geometry`'s doorway pinned to its cell, the lab
    converter's rule). The other field is None, so a doorway an earlier
    solve pinned the other way keeps neither."""
    site = geometry["site"]
    if geometry.get("shape") == SOLVED_SHAPE:
        from world.layout_solver import Rect
        rect = Rect(site["x"], site["y"], geometry["extent"]["w"], geometry["extent"]["d"])
        return {"dir": side, "offset": _offset(rect, side, cell), "cell": None}
    return {"dir": side, "cell": [cell[0] - site["x"], cell[1] - site["y"]], "offset": None}


def hall_room_id(hall) -> str:
    """The room a stair hall is on the plan: the solver's `<shaft>@<level>`,
    its storey spelled `m1` below the ground as the layout lab's converter
    spells it (`tools/site_plan_from_layout.room_id`)."""
    base, _at, level = str(hall).partition("@")
    return _slug(f"{base}_stair_{level.replace('-', 'm')}")


def _door_words(text) -> str:
    """The first call's words for a stair's door, as a doorway's name: an
    answer that gave an id for it (`stone_stair_door`) is spelled out, and
    the bare word for any door says nothing a barrier does not."""
    words = _text(text, 80)
    if words and not any(ch.isspace() for ch in words):
        words = words.replace("_", " ").strip()
    return "" if words.casefold() in ("door", "a door", "the door") else words


def _stair_halls(building, layout, rects, levels, halls, out):
    """Each stair hall the solver laid, as a room of the plan (module
    docstring): written into `out` under `hall_room_id`, with its ways --
    to each room it serves through the solver's doorway, and to the hall
    above or below by the flight. `{hall: {"uid", "serves": {room}}}` for
    every hall laid; a hall the solver gave no doorway to a room of the
    building serves nothing and is not made."""
    from world.site_plan import STOREY_M
    made = {}
    for door in layout.doors:
        for hall, room, side_of_hall in ((door["a"], door["b"], door["side"]),
                                         (door["b"], door["a"], _OPP[door["side"]])):
            if hall not in halls or room not in out or room in halls:
                continue
            cells = [tuple(c) for c in door.get("span") or [door["cell"]]]
            cell = cells[len(cells) // 2]
            dx, dy = _STEP[door["side"]]
            beyond = (cell[0] + dx, cell[1] + dy)
            hall_cell, room_cell = (cell, beyond) if door["a"] == hall else (beyond, cell)
            well = halls[hall]
            uid = hall_room_id(hall)
            entry = made.setdefault(hall, {"uid": uid, "serves": set(), "well": well})
            entry["serves"].add(room)
            way = {"barrier": "closed_door"}
            if str(door.get("kind") or "") == "open":
                # an open stair has no wall to its room: the whole run of
                # wall the two share stands open
                way = {"barrier": "open", "width": len(cells)}
            elif _door_words(door.get("kind")):
                way["name"] = _door_words(door.get("kind"))
            out[room].setdefault("made_edges", {})[uid] = dict(
                way, dir=_OPP[side_of_hall], offset=_offset(rects[room], _OPP[side_of_hall], room_cell))
            out.setdefault(uid, {"made_edges": {}})["made_edges"][room] = dict(
                way, dir=side_of_hall, offset=_offset(rects[hall], side_of_hall, hall_cell))
    for hall, entry in made.items():
        r, lv, well = rects[hall], levels[hall], entry["well"]
        name = _text(well.get("name"), 80) or "stair"
        # THE FLIGHT IN ITS HALL: the stairwell's rectangle, the same cells on
        # every storey it joins, in the hall's own cells -- a hall takes the
        # landing beside it as well, so its treads are drawn on the flight,
        # never over the whole hall (Home 11's basement hall was ten by five
        # round a two-by-five flight) -- and the flight's foot and head where
        # the solver set them (`layout_solver._stair_doorways`)
        flight = {}
        rect = well.get("rect")
        if isinstance(rect, dict) and all(isinstance(rect.get(k), int) for k in ("x", "y", "w", "d")):
            flight["flight"] = {"x": rect["x"] - r.x, "y": rect["y"] - r.y,
                                "w": rect["w"], "d": rect["d"]}
            for end in ("foot", "head"):
                cells = [c for c in well.get(end) or () if isinstance(c, (list, tuple)) and len(c) == 2]
                if cells:
                    flight[end] = [[int(c[0]) - r.x, int(c[1]) - r.y] for c in cells]
        out[entry["uid"]].update({
            "geometry": {"extent": {"w": r.w, "d": r.d}, "shape": SOLVED_SHAPE, "level": lv,
                         "exposure": "enclosed",
                         "site": {"plan": building["plan"], "x": r.x, "y": r.y,
                                  "elev_m": round(lv * STOREY_M, 2)}},
            "anchors": {}, "edges": {}, "record": {"moved": [], "unplaced": []},
            "room": {"name": name, "purpose": name, "structure": building["structure"],
                     LAYOUT_MADE_KEY: True, "stair_of": sorted(entry["serves"]),
                     # its shape, which a plan of it draws: a straight flight,
                     # an L, a U, a spiral, a ladder (`layout_solver`)
                     "stair_kind": str(well.get("kind") or ""), **flight}})
    # THE FLIGHT: each hall to the one a storey above it in its stairwell
    way = {"ladder": "ladder"}
    for well in layout.stairwells:
        mine = sorted((int(lv), hall) for lv, hall in (well.get("halls") or {}).items()
                      if hall in made)
        for (lo, low), (hi, high) in zip(mine, mine[1:]):
            if hi != lo + 1:
                continue
            kind = way.get(str(well.get("kind") or ""), "stair")
            name = _text(well.get("name"), 80)
            up = {"barrier": "open", "vertical": "up", "way": kind}
            if name:
                up["name"] = name
            out[made[low]["uid"]]["made_edges"][made[high]["uid"]] = up
            out[made[high]["uid"]]["made_edges"][made[low]["uid"]] = dict(up, vertical="down")
    return made


def _ground_cells(building, spec, laid):
    """`{plan cell: place id}` for every cell of open ground, a way or a
    feature the solve laid (`_ground_geometry`) -- the ground a window can
    look out onto. An outbuilding is a roofed room, never ground."""
    is_of = spec.get("ground_is") or {}
    out = {}
    for pid, geometry in sorted(laid.items()):
        if is_of.get(pid) not in ("open", "way", "feature"):
            continue
        for cell in sorted(_world_cells(building, pid, geometry)):
            out.setdefault(cell, pid)
    return out


def _ground_beyond(window, rects, levels, ground):
    """`(place id, plan cell)`: the first ground (`_ground_cells`) a window
    looks out onto, walking straight out of its wall -- over the roof of
    any room of the building lower than its own floor, and never through a
    wall at its own height or above, which is a wall in front of it. None
    where the walk leaves the plan with no ground met."""
    side, (x, y), level = window["dir"], window["cell"], levels[window["room"]]
    dx, dy = _STEP[side]
    xs = [r.x for r in rects.values()] + [r.x + r.w for r in rects.values()] \
        + [c[0] for c in ground]
    ys = [r.y for r in rects.values()] + [r.y + r.d for r in rects.values()] \
        + [c[1] for c in ground]
    lo_x, hi_x, lo_y, hi_y = min(xs), max(xs), min(ys), max(ys)
    while True:
        x, y = x + dx, y + dy
        if not (lo_x <= x <= hi_x and lo_y <= y <= hi_y):
            return None
        if any(rid != window["room"] and levels[rid] >= level
               and r.x <= x < r.x + r.w and r.y <= y < r.y + r.d
               for rid, r in rects.items()):
            return None
        if (x, y) in ground:
            return ground[(x, y)], (x, y)


def entrance_of(building, inventory=None, spec=None):
    """The way the building's entrance opens onto, as the solve lays it.
    Chosen with the plan (`plan_buildings`: the first outside way by storey,
    room and place); once the first answer says what each place of the
    ground is, a door opens onto a way or open ground before a thing, which
    stands AT a door, or a building apart, reached by its own walk: a
    lantern joined to the hall, whose id sorted before the path's, took the
    entrance, and the whole building was refused (two reviews of
    2026-10-14). Decided before the second call is asked, which is told it,
    so the call and the solve read one front; a place taken out of the
    ground keeps it, its way opening through the entrance door
    (`_door_already`) -- moved onto the garden beside it, the entrance faced
    a band the garden lay on the far side of, and the whole ground went
    (the fuzz's seed 66, 2026-10-14). Read back off the spec (`entrance_to`)
    wherever the spec is in hand."""
    entrance = building.get("entrance") or {}
    if not entrance:
        return entrance
    want = None
    if spec is not None:
        want = spec.get("entrance_to")
    elif inventory is not None:
        is_of = {g["id"]: g.get("is") for g in inventory.get("grounds") or ()}
        if is_of.get(entrance.get("to")) in ("feature", "outbuilding"):
            for kind in ("way", "open"):
                want = next((o["to"] for o in sorted(building["outside"], key=lambda x: x["to"])
                             if o["room"] == entrance["room"] and not o.get("vertical")
                             and is_of.get(o["to"]) == kind), None)
                if want:
                    break
    if not want or want == entrance.get("to"):
        return entrance
    return next((o for o in building["outside"] if o["room"] == entrance["room"]
                 and o["to"] == want and not o.get("vertical")), entrance)


def _plan_joins(building):
    """Every pair of rooms the plan joins by a way, either side declaring
    it, as frozensets -- save a way an earlier solve made, which is this
    solve's to make again or take back (`structure.write_planned_layout`)."""
    out = set()
    specs = dict(building.get("ground_specs") or {})
    specs.update(building.get("specs") or {})
    for uid, planned in specs.items():
        planned = planned if isinstance(planned, dict) else {}
        record = planned.get("layout") if isinstance(planned.get("layout"), dict) else {}
        solved = {str(t) for t in record.get("made_edges") or ()}
        for edge in planned.get("adjacent") or ():
            if isinstance(edge, dict) and edge.get("to") and str(edge["to"]) not in solved:
                out.add(frozenset((str(uid), str(edge["to"]))))
    return out


def _ground_doorways(building, spec, layout, laid, out):
    """EVERY DOORWAY ONTO THE GROUND MEETS ITS OTHER SIDE ACROSS THE WALL --
    the layout lab converter's measure of a plan that holds together
    (`tools/site_plan_from_layout.py`), written onto each laid place's
    joins in `out`.

    A door of the house, or of an outbuilding onto the ground it stands on:
    on whatever place it opens onto, the cell across its threshold, on the
    wall facing it -- a place whose cells do not hold the threshold gets no
    pin, and the grounds floor refuses the pair (`ground_refusals`): a pin
    "on its nearest cell, facing it" put a doorway a pace off its other side
    (the farm's well) or across a gap (Home 9's, e against e). Two places of
    the ground the plan joins: where they touch, on the side the plan
    states where they touch there, else the side they share most, at the
    middle of it. Every place's cells are the world's (`_world_cells`)."""
    door_to = spec.get("door_to") or {}
    entrance = entrance_of(building, spec=spec)
    cells = {pid: _world_cells(building, pid, g) for pid, g in laid.items()}
    for door in layout.doors:
        a, b, side, cell = door["a"], door["b"], door["side"], door["cell"]
        if not door.get("outside") or side not in _UNIT:
            continue
        threshold = (cell[0] + _UNIT[side][0], cell[1] + _UNIT[side][1])
        if a in building["rooms"]:
            places = [entrance.get("to")] if b == "entrance" else [
                o["to"] for o in building["outside"]
                if o["room"] == a and door_to.get(o["to"], o["to"]) == b]
        elif a in laid and b in laid:
            places = [b]        # an outbuilding's door onto the ground it stands on
        else:
            continue
        for pid in places:
            if pid not in laid or a in out[pid]["edges"]:
                continue
            if threshold in cells[pid]:
                out[pid]["edges"][a] = _ground_pin(laid[pid], threshold, _OPP[side])
    stated = {}
    for pid, planned in (building.get("ground_specs") or {}).items():
        for edge in planned.get("adjacent") or ():
            if isinstance(edge, dict) and edge.get("dir") in _UNIT:
                stated.setdefault((pid, str(edge.get("to") or "")), edge["dir"])
    seen = set()
    for g in building.get("grounds") or ():
        a = g["id"]
        for b in g["joins"]:
            if a not in laid or b not in laid or frozenset((a, b)) in seen:
                continue
            seen.add(frozenset((a, b)))
            by_side = {}
            for c in sorted(cells[a]):
                for side, (ux, uy) in _UNIT.items():
                    if (c[0] + ux, c[1] + uy) in cells[b]:
                        by_side.setdefault(side, []).append(c)
            if not by_side:
                continue
            side = stated.get((a, b))
            if side not in by_side:
                side = max(_SIDES, key=lambda s: (len(by_side.get(s, ())), -_SIDES.index(s)))
            row = by_side[side]
            c = row[len(row) // 2]
            ux, uy = _UNIT[side]
            out[a]["edges"].setdefault(b, _ground_pin(laid[a], c, side))
            out[b]["edges"].setdefault(a, _ground_pin(laid[b], (c[0] + ux, c[1] + uy), _OPP[side]))


def _window_desc(building, uid, base, window):
    anchors = building["specs"][uid].get("anchors")
    if isinstance(anchors, dict) and isinstance(anchors.get(base), dict) \
            and str(anchors[base].get("desc") or "").strip():
        return str(anchors[base]["desc"])
    return str(window.get("name") or base or "window")
