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
                             normalize_site=normalize_site, normalize_level=normalize_level,
                             grounds=grounds))
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


def _grounds_of(members, specs, rooms, edges, structure, outside, *, held_open, solved,
                normalize_site, normalize_level, own=()):
    """THE GROUND A BUILDING STANDS IN: `(places, specs)` -- the outdoor
    places of the building's own structure reachable from its doors through
    other such places, nearest first, at most `GROUNDS_MAX_PLACES` within
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
        if str(spec.get("structure") or "") != structure:
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
            own=own)
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
        holder = next((rid for rid, live in sorted(rooms.items())
                       if rid not in building["rooms"] and rid not in laid_again
                       and isinstance(live, dict)
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
    held = {"rooms": [rooms[uid] for uid in building["rooms"]], "stairs": stairs}
    if building.get("grounds"):
        held["grounds"] = hold_grounds(building, answer.get("grounds"))
    return held


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
    return out


def relate_payload(building, inventory):
    """What the second call reads: the building, what the first sorted each
    room to hold, what the plan already fixes, and the vocabularies. A mark
    is the engine's to place where its way meets the room, so the second
    call is not handed one to relate."""
    fixed = _fixed(building)
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
    entrance = building["entrance"] or {}
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
            if any(x["to"] == target for x in joins):
                continue
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
    blocks = [{"id": uid, "apart": False, "beside": {"block": "main", "side": block["side"]}}
              for uid, block in sorted((building.get("own_blocks") or {}).items())]
    if ground is None:
        grounds = {"areas": [{"id": o["to"], "name": o["name"], "kind": GROUND_AREA_KIND,
                              "where": o["side"] or "around"}
                             for o in _unique_outside(building)]}
    else:
        grounds = {key: ground[key] for key in ("areas", "ways", "features")}
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
    return out


def _ground_plan(building, inventory, answer, entrance):
    """The ground a building stands in, as the solver's spec takes it:
    `{areas, ways, features, rooms, blocks, is, door_to}` from what the first
    call said each place IS (`hold_grounds`) and the relations the second
    wrote, each word held to the solver's own.

    OPEN GROUND is an area on the side the answer gives it, else the side
    the plan's doorway onto it states, else the ground the building stands
    `around` -- one only; a second takes its side or nothing. A WAY runs from
    the entrance when the entrance opens onto it or the answer says so --
    the one approach -- else from the way the answer names, toward the
    feature it names. A FEATURE stands by one relation: across, flanking or
    along a way (at its `end`), by a place or the entrance -- on the side of
    it the answer gives -- or on a side of the building; else by the place
    the plan joins it to. An OUTBUILDING is
    a block of its own standing apart on its side, reached by a way between
    its door and the house's (`<id>__way`, solver geometry only).

    A door of the house onto a feature opens onto the ground the feature
    stands in -- the area the building stands around, else `GROUND_ID` --
    and one onto an outbuilding onto the way to it (`door_to`). A place the
    first call left unsaid is laid as the tier always laid it when the
    house opens straight onto it -- open ground on the side its doorway
    states -- and not at all when it lies further out."""
    answer = answer if isinstance(answer, dict) else {}
    held = {g["id"]: g for g in inventory.get("grounds") or ()}
    said = {}
    for raw in answer.get("grounds") or ():
        if isinstance(raw, dict) and str(raw.get("id") or "") in held:
            said.setdefault(str(raw["id"]), raw)
    sizes, kinds = set(SIZE_WORD_FOOTPRINT), set(FIXTURE_SIZES)
    is_of = {pid: g["is"] for pid, g in held.items()}
    way_ids = {pid for pid, what in is_of.items() if what == "way"}
    feature_ids = {pid for pid, what in is_of.items() if what == "feature"}
    entrance_to = entrance.get("to")
    plan_side = {}
    for o in building["outside"]:
        if o["side"] and o["to"] not in plan_side:
            plan_side[o["to"]] = o["side"]
    direct = {o["to"] for o in building["outside"] if not o.get("vertical")}
    areas, ways, features, rooms, blocks, door_to = [], [], [], [], [], {}
    around = None
    approach = False
    # what the answers said first: a place left unsaid never takes the
    # ground round the house from one said to lie there
    for place in sorted(building.get("grounds") or (), key=lambda g: g["id"] not in is_of):
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
            if not approach and (pid == entrance_to or frm == "entrance"):
                way["from"], approach = "entrance", True
            elif frm in way_ids and frm != pid:
                way["from"] = frm
            if str(mine.get("to") or "") in feature_ids:
                way["to"] = str(mine["to"])
            ways.append(way)
        elif what == "feature":
            feature = {"id": pid, "name": place["name"]}
            kind = held[pid].get("kind") or str(mine.get("kind") or "").strip().casefold()
            size = str(mine.get("size") or "").strip().casefold()
            if kind in kinds:
                feature["kind"] = kind
                if size in sizes:
                    feature["size"] = size
            else:
                feature["kind"], feature["size"] = "", size if size in sizes else "medium"
            placed = False
            for rel in ("across", "flank", "along"):
                if str(mine.get(rel) or "") in way_ids:
                    feature[rel], placed = str(mine[rel]), True
                    end = str(mine.get("end") or "").strip().casefold()
                    if end in ("far", "near"):
                        feature["end"] = end
                    break
            by = str(mine.get("by") or "")
            if not placed and (by == "entrance" or by in way_ids or by in feature_ids
                               or by in building["rooms"]) and by != pid:
                feature["by"], placed = by, True
                if _side(mine.get("side")):
                    # and on that side of it, where the answer says
                    feature["side"] = _side(mine.get("side"))
            if not placed and _side(mine.get("side")):
                feature["side"], placed = _side(mine.get("side")), True
            if not placed:
                joined = next((o for o in place["joins"]
                               if o in way_ids or o in feature_ids or o in building["rooms"]), None)
                if joined:
                    feature["by"] = joined
            features.append(feature)
        elif what == "outbuilding":
            side = _side(mine.get("side")) or plan_side.get(pid)
            if side is None:
                del is_of[pid]
                continue
            walk = f"{pid}__way"
            rooms.append({"id": pid, "name": place["name"], "level": 0, "block": pid,
                          "purpose": "other", "joins": [{"to": walk, "kind": "door"}],
                          "zones": [], "windows": [], "fixtures": []})
            blocks.append({"id": pid, "apart": True, "beside": {"block": "main", "side": side}})
            ways.append({"id": walk, "name": place["name"]})
            door_to[pid] = walk
    stands_in = around
    for pid in sorted(feature_ids & direct):
        if stands_in is None:
            areas.append({"id": GROUND_ID, "name": GROUND_ID, "kind": GROUND_AREA_KIND,
                          "where": "around"})
            stands_in = GROUND_ID
        door_to[pid] = stands_in
    # A DOOR OF THE HOUSE ALWAYS OPENS ONTO SOMETHING. A place it opens
    # straight onto that the answers left nowhere -- open ground with no side
    # to lie on, an outbuilding with none to stand apart on -- is open ground
    # on its doorway's side, as the tier laid it before the grounds; a door
    # onto nothing would refuse every seed.
    held_ids = {x["id"] for x in areas + ways + features + rooms} | set(door_to)
    ground_ids = {g["id"] for g in building.get("grounds") or ()}
    for o in building["outside"]:
        pid = o["to"]
        if o.get("vertical") or pid not in ground_ids or pid in held_ids:
            continue
        held_ids.add(pid)
        areas.append({"id": pid, "name": o["name"], "kind": GROUND_AREA_KIND,
                      "where": o["side"] or "around"})
        is_of[pid] = "open"
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
    door_to = spec.get("door_to") or {}
    for o in building["outside"]:
        target = "entrance" if (o["room"] == entrance.get("room") and o["to"] == entrance.get("to")) \
            else door_to.get(o["to"], o["to"])
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


def _outside_side(layout, building, o, door_to=None):
    """The wall a building room opens onto the ground outside through --
    onto what the place stands in, or the way to it, where the grounds were
    laid out with the building (`_ground_plan`)."""
    entrance = building["entrance"] or {}
    target = "entrance" if (o["room"] == entrance.get("room") and o["to"] == entrance.get("to")) \
        else (door_to or {}).get(o["to"], o["to"])
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
        if uid in (building.get("own_blocks") or {}) or uid in (building.get("boxed") or ()):
            # its own block, or a shape that names no parts: where it stands
            # and how large are the solve's, its shape word the plan's --
            # never squared
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
                tos = [entrance.get("to")]
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
            got = _outside_side(layout, building, {"room": room_id, "to": to}, door_to)
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
            earlier = (planned.get("layout") or {}).get("stated") \
                if isinstance(planned.get("layout"), dict) else None
            stated = (earlier["w"], earlier["d"]) if isinstance(earlier, dict) \
                and earlier.get("w") and earlier.get("d") else _stated_sides(planned)
            if stated is not None:
                out[pid]["record"]["stated"] = {"w": stated[0], "d": stated[1]}
                report["stated"].append({"room": pid, "stated": {"w": stated[0], "d": stated[1]},
                                         "solved": dict(geometry["extent"])})
        for door in layout.doors:
            # an outbuilding's own doorway, onto the way to the house: its
            # doorway to the rooms the plan joins it to
            a = door["a"]
            if a in laid and door.get("outside") and door["b"] == door_to.get(a):
                for o in building["outside"]:
                    if o["to"] == a and o["room"] in rects:
                        out[a]["edges"][o["room"]] = {
                            "dir": door["side"], "cell": None,
                            "offset": _offset(layout.floors[0][a][0], door["side"], door["cell"])}
        _ground_doorways(building, spec, layout, laid, out)
    for uid in out:
        record = out[uid]["record"]
        out[uid]["layout"] = {"plan": building["plan"], "turn": turn,
                              "moved": record["moved"], "unplaced": record["unplaced"],
                              "sides": record.get("sides", [])}
        for key in ("stated", "described_m2", "restored", "split", "grounds"):
            if key in record:
                out[uid]["layout"][key] = record[key]
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


def _geometry_cells(geometry):
    """A laid place's cells on its plan: its parts, else its whole box."""
    site, extent = geometry["site"], geometry["extent"]
    parts = geometry.get("parts") or [{"w": extent["w"], "d": extent["d"], "at": [0, 0]}]
    return {(site["x"] + p["at"][0] + i, site["y"] + p["at"][1] + j)
            for p in parts for i in range(p["w"]) for j in range(p["d"])}


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


def _facing(cells, target):
    """`(cell, side)`: the cell of `cells` nearest `target`, and the side of
    it `target` lies on."""
    cell = min(cells, key=lambda c: (abs(c[0] - target[0]) + abs(c[1] - target[1]), c))
    dx, dy = target[0] - cell[0], target[1] - cell[1]
    if abs(dx) >= abs(dy) and dx:
        return cell, ("e" if dx > 0 else "w")
    return cell, ("s" if dy > 0 else "n")


def _ground_doorways(building, spec, layout, laid, out):
    """EVERY DOORWAY ONTO THE GROUND MEETS ITS OTHER SIDE ACROSS THE WALL --
    the layout lab converter's measure of a plan that holds together
    (`tools/site_plan_from_layout.py`), written onto each laid place's
    joins in `out`.

    A door of the house: on the place it opens straight onto, the cell
    across its threshold; on a place standing by the ground it opens onto
    -- a well by the kitchen door -- the cell of that place nearest the
    threshold, on its side facing it. Two places of the ground the plan
    joins: where they touch, on the side the plan states where they touch
    there, else the side they share most, at the middle of it. Places that
    do not touch keep the doorway the plan gave them."""
    door_to = spec.get("door_to") or {}
    entrance = building["entrance"] or {}
    cells = {pid: _geometry_cells(g) for pid, g in laid.items()}
    for door in layout.doors:
        a, b, side, cell = door["a"], door["b"], door["side"], door["cell"]
        if not door.get("outside") or a not in building["rooms"] or side not in _UNIT:
            continue
        threshold = (cell[0] + _UNIT[side][0], cell[1] + _UNIT[side][1])
        places = [entrance.get("to")] if b == "entrance" else [
            o["to"] for o in building["outside"]
            if o["room"] == a and door_to.get(o["to"], o["to"]) == b]
        for pid in places:
            if pid not in laid or a in out[pid]["edges"]:
                continue
            if threshold in cells[pid]:
                at, facing = threshold, _OPP[side]
            else:
                at, facing = _facing(cells[pid], threshold)
            out[pid]["edges"][a] = _ground_pin(laid[pid], at, facing)
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
