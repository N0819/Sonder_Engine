"""A building laid out from relations: the model says what is where, code places it.

PROTOTYPE (branch layout-solver-test, 2026-10-03). Nothing in the turn pipeline
calls this module; `tools/layout_lab` drives it and renders what it produces.

WHY. The owner, 2026-10-03: the room designer "is very poor about spatial
reasoning and placement", poor "at placing fixtures or guessing room size",
and "stairs don't exist and stacked buildings just end up being a bunch of
rooms with no true verticality". Holodeck (Yang et al., CVPR 2024) measured
the split this module makes: a language model is good at RELATIONS and poor
at coordinates (constraint placement 0.706 against 0.364 for model-written
coordinates, no better than random at 0.369). The model writes relations;
this module owns every coordinate.

THIRD DESIGN. Two earlier solvers on this branch taught what not to do. The
first cut one footprint per storey and handed a stair strip's leftovers to
the nearest room, splitting rooms into pieces. The second grew rooms one at
a time and patched every failure (shrink, overhang, turn, fallback sides);
the owner read its output as "cobbled together", outlines ragged, the
outdoors "a jumbled together mess". So, written once from this design:

  1. OUTLINE FIRST. A building is one or more BLOCKS (a tower beside a
     cottage, an outbuilding apart from the house). A block's outline is
     sized from its largest storey that stands full; every storey of the
     block divides that same outline, a storey under the roof an inset of
     it that never sizes it. Ragged outlines cannot occur.
  2. DIVIDE THE OUTLINE. Guillotine cuts -- every cut splits a rectangle in
     two -- so every room is ONE rectangle by construction; where a storey
     has a corridor, a spine layout runs it down the block's long axis with
     rooms in bands either side and at its ends. Many divisions are scored
     (joins sharing a wall, asked sides, proportions, size) and a beam
     search across storeys keeps the ones whose stairs line up.
  3. STAIRS STAND IN THEIR ROOMS. A stair is a well against a named wall of
     the room at each end, the same cells on both storeys. An OPEN stair
     rises in the room, its landing the room's own floor; an ENCLOSED stair
     (behind a door) is carved from the room as its own stairwell with a
     doorway onto it.
  4. ZONES ARE FLOOR, NOT ROOMS. A part of a room with no walls of its own
     -- an entry step where shoes come off, a sitting area -- is a zone:
     an area of the room's floor holding its own fixtures.
  5. THE GROUNDS ARE OPEN GROUND WITH THINGS IN IT. The building stands in
     a plot; the approach runs from the entrance door out the front; an
     outdoor feature is an object placed by a plain relation -- across a
     way (a gate), flanking it (guardians), along it (lanterns), by
     something (a well by the entryway) and on a side of it where one is
     given, on a side of the building (a tree behind it) -- never a fenced
     room. An outbuilding is a block of its own, standing apart.

THE SPEC (what the model writes; `tools/layout_lab/run.py` holds the prompt):

    {"name", "front": "n|e|s|w",
     "entrance": {"room": id, "zone"?: id, "kind"?: str},
     "storeys"?: [{"level", "smaller"?: bool}],
     "blocks"?: [{"id", "beside"?: {"block", "side"}, "apart"?: bool}],
     "rooms": [{"id", "name", "level", "block"?, "purpose", "size"?,
                "joins": [{"to": room_id | area_id | way_id, "side"?, "order"?, "kind"?}],
                "zones": [{"id", "name", "at"?, "by"?: "entrance", "size"?}],
                "fixtures": [{"id", "name", "kind", "size"?, "at"?, "in"?: zone_id,
                              "near"?, "beside"?, "facing"?}]}],
     "stairs": [{"id", "name", "from", "to", "enclosed": bool, "door"?: str,
                 "from_at"?, "to_at"?, "kind"?: "straight|spiral|ladder"}],
     "grounds": {"areas": [{"id", "name", "kind", "where": "around|n|e|s|w"}],
                 "ways": [{"id", "name", "from"?: "entrance" | "door" | way_id | area_id,
                           "side"?: "n|e|s|w", "to"?: feature_id}],
                 "features": [{"id", "name", "kind", "size"?, "count"?,
                               "across"?: way_id, "flank"?: way_id, "along"?: way_id,
                               "end"?: "far|near", "by"?: id | "entrance",
                               "side"?: "n|e|s|w", "in"?: area_id, "round"?: bool,
                               "at_door"?: {"room", "onto"}, "reach"?: [way_id]}],
                 "narrowest"?: paces},
     "elsewhere": [{"name", "why", "via"?}]}

Units are paces (0.75 m), the engine's own.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

PACE_M = 0.75

#: Footprint (w x d, paces) and height of a fixture by kind -- the engine's
#: table, never the model's numbers. A kind not listed takes its size word.
FIXTURE_SIZES = {
    "bed": (3, 2, "waist"), "futon": (3, 2, "floor"), "nest": (4, 4, "waist"),
    "table": (2, 2, "waist"), "low_table": (2, 2, "floor"), "chabudai": (2, 2, "floor"),
    "desk": (2, 1, "waist"), "writing_desk": (2, 1, "floor"), "chair": (1, 1, "waist"),
    "cushion": (1, 1, "floor"), "bench": (3, 1, "waist"), "sofa": (3, 1, "waist"),
    "shelf": (2, 1, "full"), "bookshelf": (2, 1, "full"), "cabinet": (2, 1, "head"),
    "closet": (3, 1, "full"), "chest": (2, 1, "waist"), "trunk": (2, 1, "waist"),
    "wardrobe": (2, 1, "full"), "stove": (2, 1, "waist"), "hearth": (2, 1, "waist"),
    "counter": (3, 1, "waist"), "sink": (1, 1, "waist"), "basin": (1, 1, "waist"),
    "bath": (2, 2, "waist"), "tub": (2, 2, "waist"), "toilet": (1, 1, "waist"),
    "altar": (2, 1, "waist"), "alcove": (2, 1, "full"), "tokonoma": (2, 1, "full"),
    "screen": (2, 1, "head"), "lantern": (1, 1, "head"), "statue": (1, 1, "head"),
    "well": (2, 2, "waist"), "tree": (3, 3, "full"), "gate": (3, 1, "full"),
    "workbench": (3, 1, "waist"), "barrel": (1, 1, "waist"), "crate": (1, 1, "waist"),
    "rack": (2, 1, "head"), "window_seat": (2, 1, "waist"), "fireplace": (2, 1, "head"),
    "bar": (4, 1, "waist"), "piano": (2, 2, "waist"), "pillar": (1, 1, "full"),
    "rug": (3, 2, "floor"), "boulder": (2, 2, "waist"), "pond": (3, 3, "floor"),
    "lamp": (2, 2, "head"),
}
SIZE_WORD_FOOTPRINT = {"tiny": (1, 1, "floor"), "small": (1, 1, "waist"),
                       "medium": (2, 1, "waist"), "large": (3, 2, "waist"),
                       "huge": (4, 3, "head")}
ZONE_SIZES = {"small": (2, 2), "medium": (3, 2), "large": (4, 3)}

#: Floor area range (square paces) by what a room is for. A room's size comes
#: from what it holds; this range is a floor under that.
PURPOSE_AREA = {
    "entryway": (6, 16), "hallway": (8, 40), "corridor": (8, 60), "stair": (8, 16),
    "bedroom": (12, 36), "guest_room": (12, 30), "living": (24, 80), "hall": (30, 120),
    "kitchen": (12, 36), "dining": (16, 50), "bath": (6, 20), "washroom": (6, 20),
    "toilet": (3, 8), "latrine": (3, 8), "storage": (6, 20), "closet": (2, 8),
    "study": (10, 28), "workshop": (16, 50), "cellar": (16, 60), "basement": (20, 70),
    "attic": (16, 60), "shrine": (10, 40), "meditation": (10, 30),
    "common_room": (40, 100), "office": (10, 30), "cell": (6, 14), "other": (10, 30),
}
#: Rooms that take a storey's spare floor when its outline is wider than its
#: rooms need: the open, general rooms. A service room keeps its size.
FLEXIBLE = frozenset({"living", "hall", "common_room", "dining", "storage", "workshop",
                      "cellar", "basement", "attic", "bedroom", "guest_room", "shrine",
                      "study", "other"})
CORRIDORS = ("hallway", "corridor")
#: The share of a room's floor its furniture may cover.
COVERAGE = 0.35
#: A stair hall by the shape of its stair (width x length, paces, its
#: landings inside it): a straight flight, a quarter turn (L), a half turn
#: with a landing between two flights side by side (U, the compact stair of
#: a house of several storeys), a spiral, a ladder through a hatch.
STAIRS = {"straight": (2, 5), "l": (3, 3), "u": (4, 4), "spiral": (2, 2), "ladder": (1, 2)}
#: A shape that does not fit gives way to the next, more compact one -- and
#: the quarter turn (L) is never one of them. The owner withdrew it on
#: 2026-10-03 ("I was wrong recommending l shaped stairs") after the wrapping
#: L of 98827d9f was reverted, but this fallback went on offering an L right
#: after a straight flight, so the solver chose one where nobody asked: both
#: stairs of the lab's inn were L halls. An L now stands only where a spec
#: names one (`_stair_shapes`).
STAIR_FALLBACK = ("straight", "u", "spiral", "ladder")
#: The words a spec may use for each shape -- the engine's own closed set.
_STAIR_WORDS = {"straight": "straight", "l": "l", "l-shaped": "l", "l_shaped": "l", "quarter": "l",
                "quarter-turn": "l", "u": "u", "u-shaped": "u", "u_shaped": "u", "dogleg": "u",
                "switchback": "u", "half-turn": "u", "spiral": "spiral", "winding": "spiral",
                "ladder": "ladder"}
#: Each room's ceiling, from its purpose's range: a room grows past what it
#: holds to fill its storey, but not past this; floor left over becomes a
#: store or loft space.
MAX_GROWTH = 1.4
#: Divisions tried per storey while comparing stair placements, and for the
#: placement kept.
QUICK = 100
TRIES = 600
#: Width of a way across the grounds, how far the approach runs before the
#: plot's edge, and the open ground left on the other sides of the building.
WAY_WIDTH = 3
FRONT_REACH = 10
SIDE_MARGIN = 5
#: How far a way that leaves the grounds -- one the plan joins to open
#: ground and not to the house -- is laid past their edge: the approach's
#: own reach (`FRONT_REACH`). Named per ask-before-limiting.
WAY_BEYOND = 10
#: How far a thing standing at a door may reach over open ground to the way
#: the plan also joins it to, its door turning to bring it within (Home 9's
#: well, from the kitchen's back door to the path). Named per
#: ask-before-limiting.
REACH_MAX = 2
#: How far apart, in paces along a room's outside wall, a thing's own door
#: stands from the room's other outside doors (`_place_doors`): at two the
#: thing's step lies outside the other door's ground (`_grounds`' aprons).
#: Named per ask-before-limiting.
THING_DOOR_GAP = 2
#: Paces between two outbuildings the plan bears the same way
#: (`_place_blocks`): one pace between them is ground no place is read to
#: hold, and a door opening into it opened onto nothing (a review of
#: 2026-10-14). Named per ask-before-limiting.
BLOCK_GAP = 2
#: How far round a way that leaves the grounds the ground is opened, for
#: what stands across it, by it or at its end -- the room a pair of posts or
#: a lantern needs beside a three-pace way. Named per ask-before-limiting.
LEAVING_GROUND = 3
#: A storey above or below the ground that needs less than PART_SHARE of its
#: block's outline (its need taken at PART_SLACK, room to move) covers only
#: part of the building.
PART_SHARE = 0.7
PART_SLACK = 1.25
SEED = 7

_SIDES = ("n", "e", "s", "w")
_OPP = {"n": "s", "s": "n", "e": "w", "w": "e"}
_STEP = {"n": (0, -1), "s": (0, 1), "e": (1, 0), "w": (-1, 0)}


# ---------------------------------------------------------------- geometry

@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    d: int

    def cells(self):
        return {(self.x + i, self.y + j) for i in range(self.w) for j in range(self.d)}

    def overlaps(self, other):
        return not (self.x + self.w <= other.x or other.x + other.w <= self.x
                    or self.y + self.d <= other.y or other.y + other.d <= self.y)

    def contains(self, other):
        return (self.x <= other.x and self.y <= other.y
                and other.x + other.w <= self.x + self.w
                and other.y + other.d <= self.y + self.d)

    def flush(self, other, side):
        """Is `other` (inside self) against self's `side` wall?"""
        return {"n": other.y == self.y, "s": other.y + other.d == self.y + self.d,
                "w": other.x == self.x, "e": other.x + other.w == self.x + self.w}[side]

    def inset(self, k):
        return Rect(self.x + k, self.y + k, self.w - 2 * k, self.d - 2 * k)

    def as_dict(self):
        return {"x": self.x, "y": self.y, "w": self.w, "d": self.d}


def _bbox(cells):
    xs = [c[0] for c in cells]
    ys = [c[1] for c in cells]
    return Rect(min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1)


def _runs(cells):
    """A cell set as row runs, so an irregular area is a rect list."""
    out = []
    for y in sorted({c[1] for c in cells}):
        xs = sorted(c[0] for c in cells if c[1] == y)
        start = prev = xs[0]
        for x in xs[1:] + [None]:
            if x is not None and x == prev + 1:
                prev = x
                continue
            out.append(Rect(start, y, prev - start + 1, 1))
            if x is not None:
                start = prev = x
    return out


def _connected(free, required):
    """Can a body walk between every cell of `required` through `free`?"""
    required = list(required)
    if any(c not in free for c in required):
        return False
    if len(required) < 2:
        return True
    seen, stack = set(), [required[0]]
    while stack:
        c = stack.pop()
        if c in seen or c not in free:
            continue
        seen.add(c)
        x, y = c
        stack.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    return all(c in seen for c in required)


def _block(o):
    """The two-by-two block whose top-left cell is `o`."""
    return {(o[0], o[1]), (o[0] + 1, o[1]), (o[0], o[1] + 1), (o[0] + 1, o[1] + 1)}


def _round_cells(w, d):
    """The cells of a round thing `w` by `d` paces, as the world reads it --
    the world's own reader (`spatial_fov.room_grid`, the round shape: the
    inscribed ellipse), asked of a box with no site. Read only for a thing
    the bridge marks round; the lab marks none."""
    key = (int(w), int(d))
    if key not in _ROUND_CELLS:
        from world.spatial import room_grid
        stub = {"name": "_", "shape": "round", "extent": {"w": key[0], "d": key[1]}}
        _ROUND_CELLS[key] = frozenset(room_grid({"rooms": {"_": stub}}, "_").cells)
    return _ROUND_CELLS[key]


_ROUND_CELLS = {}


def _wide_route(walk, starts, goal):
    """The shortest route two paces wide through `walk`: a chain of
    two-by-two blocks, each a pace on from the last, from one whose origin
    is in `starts` to one `goal` accepts (it is handed the origin) -- the
    union of those blocks, or an empty set. The world reads no part of a
    place narrower than two paces (`layout_bridge._cover`), so a way laid a
    pace wide was written as nothing: every branch way, and a walk wherever
    it ran between a wall and a thing (a review of 2026-10-14)."""
    starts = sorted(o for o in set(starts) if _block(o) <= walk)
    prev = {o: None for o in starts}
    frontier, hit = starts, None
    while frontier and hit is None:
        nxt = []
        for o in frontier:
            if goal(o):
                hit = o
                break
            for dx, dy in _STEP.values():
                n = (o[0] + dx, o[1] + dy)
                if n not in prev and _block(n) <= walk:
                    prev[n] = o
                    nxt.append(n)
        frontier = nxt
    cells = set()
    while hit is not None:
        cells |= _block(hit)
        hit = prev[hit]
    return cells


def _shared_wall(a: Rect, b: Rect):
    """(side of a, [cells of a along the wall touching b]) or (None, [])."""
    if a.y + a.d == b.y or b.y + b.d == a.y:
        lo, hi = max(a.x, b.x), min(a.x + a.w, b.x + b.w)
        if hi > lo:
            side = "s" if a.y + a.d == b.y else "n"
            row = a.y + a.d - 1 if side == "s" else a.y
            return side, [(x, row) for x in range(lo, hi)]
    if a.x + a.w == b.x or b.x + b.w == a.x:
        lo, hi = max(a.y, b.y), min(a.y + a.d, b.y + b.d)
        if hi > lo:
            side = "e" if a.x + a.w == b.x else "w"
            col = a.x + a.w - 1 if side == "e" else a.x
            return side, [(col, y) for y in range(lo, hi)]
    return None, []


def _door_cells(a: Rect, b: Rect, avoid=frozenset()):
    """(side of a, cells of a a doorway into b may open from): the shared
    wall less any cell with a stairwell on either side of it."""
    side, cells = _shared_wall(a, b)
    if side is None:
        return None, []
    dx, dy = _STEP[side]
    return side, [c for c in cells if c not in avoid and (c[0] + dx, c[1] + dy) not in avoid]


# ------------------------------------------------------------ sizing

#: How a size word scales a kind the table knows: a large tub is larger than
#: a tub.
SIZE_SCALE = {"tiny": 0.6, "small": 0.8, "medium": 1.0, "large": 1.5, "huge": 2.0}


def fixture_footprint(fx):
    kind = str(fx.get("kind") or "").strip().casefold().replace(" ", "_")
    word = str(fx.get("size") or "").casefold()
    if kind in FIXTURE_SIZES:
        w, d, h = FIXTURE_SIZES[kind]
        k = SIZE_SCALE.get(word, 1.0)
        return max(1, round(w * k)), max(1, round(d * k)), h
    return SIZE_WORD_FOOTPRINT.get(word or "medium", SIZE_WORD_FOOTPRINT["medium"])


#: USE-SPACE: the clear floor a fixture needs to be used, in paces -- the
#: engine's table, like FIXTURE_SIZES. (front, back): standing room before it,
#: and an aisle behind it (a bar is served from behind). A table needs a ring
#: of floor all round, where its seats go; a bed needs one long side free.
#: A kind not listed needs a pace before it when it is bigger than a pace.
USE_SPACE = {
    "bar": (1, 1), "counter": (1, 0), "stove": (1, 0), "hearth": (1, 0), "fireplace": (1, 0),
    "range": (1, 0), "kamado": (1, 0), "oven": (1, 0), "sink": (1, 0), "basin": (1, 0),
    "altar": (1, 0), "alcove": (1, 0), "tokonoma": (1, 0), "shelf": (1, 0), "bookshelf": (1, 0),
    "cabinet": (1, 0), "closet": (1, 0), "wardrobe": (1, 0), "chest": (1, 0), "trunk": (1, 0),
    "rack": (1, 0), "workbench": (1, 0), "desk": (1, 0), "writing_desk": (1, 0), "piano": (1, 0),
    "bath": (1, 0), "tub": (1, 0), "toilet": (1, 0), "latrine": (1, 0), "screen": (0, 0),
    "chair": (0, 0), "cushion": (0, 0), "stool": (0, 0), "barrel": (0, 0), "crate": (0, 0),
    "lantern": (0, 0), "statue": (0, 0), "pillar": (0, 0), "rug": (0, 0), "box": (0, 0),
}
_TABLES = ("table", "low_table", "chabudai", "dining_table")
_SEATS = ("chair", "cushion", "stool", "zabuton", "bench")
_BEDS = ("bed", "futon", "nest")


def _kind(fx):
    return str(fx.get("kind") or "").strip().casefold().replace(" ", "_")


#: Mounts that take no floor: a thing hung on a wall's face or from the
#: ceiling. A thing that stands AGAINST a wall stands on the floor (its wall
#: is its "at"); "wall" alone is read that way, since a model writes it for
#: a bar along the back wall as readily as for a scroll on it.
_OFF_FLOOR = ("hung", "ceiling")


def _sort_fixtures(r):
    """A room's fixtures split by how they stand: (floor, details, contents).
    Only a floor thing takes floor. A thing on a wall or hung from the
    ceiling is a DETAIL of the room; a thing in or on another fixture is that
    fixture's CONTENTS. Several alike are that many things; several asked
    along the walls go round the walls."""
    raw = [f for f in r.get("fixtures") or () if isinstance(f, dict) and f.get("id")]
    ids = {f["id"] for f in raw}
    zones = {z.get("id") for z in r.get("zones") or ()}
    floor, details, contents = [], [], {}
    for f in raw:
        mount = str(f.get("mount") or "floor").casefold()
        host = str(f.get("on") or f.get("in") or "")
        if mount.split()[0] in ("in", "on") and len(mount.split()) > 1:
            host = mount.split()[1]
        n = max(1, min(24, int(f.get("count") or 1)))
        if mount.split()[0] in _OFF_FLOOR:
            details.append({"id": f["id"], "name": f.get("name") or f["id"], "mount": mount.split()[0], "count": n})
            continue
        if host in ids and host not in zones and host != f["id"]:
            contents.setdefault(host, []).append({"id": f["id"], "name": f.get("name") or f["id"], "count": n})
            continue
        if n == 1:
            floor.append(f)
            continue
        around = str(f.get("at") or "").casefold() == "walls"
        for i in range(n):
            copy = dict(f, id=f"{f['id']}_{i + 1}", count=1)
            if around:
                copy["at"] = _SIDES[i % 4]
            floor.append(copy)
    return floor, details, contents


def purpose_key(room):
    text = str(room.get("purpose") or "").casefold().replace(" ", "_")
    if text in PURPOSE_AREA:
        return text
    text = " ".join(str(room.get(k) or "") for k in ("purpose", "name", "id")).casefold()
    for key in PURPOSE_AREA:
        if key.replace("_", " ") in text or key in text:
            return key
    return "other"


def _zone_size(z):
    return ZONE_SIZES.get(str(z.get("size") or "medium").casefold(), ZONE_SIZES["medium"])


def _stated_area(room):
    """The floor area the description gives a room, in square paces, or None:
    a six-mat room is a six-mat room, whatever floor is spare around it."""
    try:
        m2 = float(room.get("area_m2") or 0)
    except (TypeError, ValueError):
        return None
    return m2 / (PACE_M * PACE_M) if m2 > 0 else None


def room_target(room, stated=True):
    """Square paces a room needs: its furniture at COVERAGE of the floor, its
    zones' floor, a step inside each door; never under its purpose's floor."""
    key = purpose_key(room)
    lo, _hi = PURPOSE_AREA[key]
    area = _stated_area(room) if stated else None
    furniture = sum(w * d for w, d, _h in (fixture_footprint(f) for f in room.get("fixtures") or ()))
    zones = sum(a * b for a, b in (_zone_size(z) for z in room.get("zones") or ()))
    doors = len(room.get("joins") or ())
    if area:
        # a stated size never squeezes a room below what it is said to hold
        return max(area, furniture / COVERAGE + 0.6 * zones + 1.5 * doors)
    if key in CORRIDORS:
        return max(lo, 2 * max(4, 2.5 * doors))
    hint = {"tiny": 0.7, "small": 0.85, "large": 1.25, "huge": 1.5}.get(
        str(room.get("size") or "").casefold(), 1.0)
    return max(lo, hint * (furniture / COVERAGE + 0.6 * zones + 1.5 * doors))


# ------------------------------------------------------------ the spec

@dataclass
class _Stair:
    id: str
    name: str
    low: str
    high: str
    enclosed: bool
    door: str
    at: dict
    kind: str | None


@dataclass
class _Shaft:
    """One or more flights climbing the same way through consecutive
    storeys: one stair hall, at the same cells on every storey it spans."""
    id: str
    name: str
    flights: list
    levels: list
    block: str
    enclosed: bool
    door: str
    kind: str
    asked: bool = False   # the spec named the shape: no other is tried unless it cannot fit


def _read(spec, layout):
    """Rooms by id (each with its level and block), and the stairs."""
    rooms = {}
    for r in spec.get("rooms") or ():
        if isinstance(r, dict) and r.get("id"):
            r = dict(r)
            r["fixtures"], r["details"], r["contents"] = _sort_fixtures(r)
            r["level"] = int(r.get("level") or 0)
            r["block"] = str(r.get("block") or "main")
            rooms[r["id"]] = r
    for r in rooms.values():
        layout.names[r["id"]] = r.get("name") or r["id"]
        layout.purposes[r["id"]] = purpose_key(r)
        if r["details"]:
            layout.details[r["id"]] = r["details"]
        if r["contents"]:
            layout.contents[r["id"]] = r["contents"]
    stairs = []
    for st in spec.get("stairs") or ():
        if not isinstance(st, dict):
            continue
        a, b = st.get("from"), st.get("to")
        if a not in rooms or b not in rooms:
            layout.warnings.append(f"stair {st.get('id')} names a room the building does not hold")
            continue
        if abs(rooms[a]["level"] - rooms[b]["level"]) != 1:
            layout.warnings.append(f"stair {st.get('id')} does not join two neighbouring storeys")
            continue
        low, high = (a, b) if rooms[a]["level"] < rooms[b]["level"] else (b, a)
        at = {}
        for rid, key in ((a, "from_at"), (b, "to_at")):
            v = str(st.get(key) or "")[:1]
            at[rid] = v if v in _SIDES else None
        kind = _STAIR_WORDS.get(str(st.get("kind") or "").casefold().strip())
        stairs.append(_Stair(str(st.get("id") or f"{a}-{b}"), str(st.get("name") or "stair"),
                             low, high, bool(st.get("enclosed")), str(st.get("door") or "door"),
                             at, kind))
    return rooms, stairs


def _shafts(rooms, stairs, layout):
    """Group flights into shafts: a flight that climbs on from the room the
    last one arrived in, of the same kind (open over open, enclosed over
    enclosed), in the same block and read as the same stair, stacks over it. Each shaft takes the
    shape its spec names, else the engine's rule: a tower (every storey one
    room) turns in a spiral; flights stacked through three storeys or more
    double back in a U; steps into a cellar run straight; anything else is a
    straight flight."""
    parent = {st.id: st.id for st in stairs}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a in stairs:
        for b in stairs:
            if a is b or a.high != b.low or a.enclosed != b.enclosed:
                continue
            if rooms[a.low]["block"] != rooms[b.high]["block"]:
                continue
            if a.kind and b.kind and a.kind != b.kind:
                continue
            # only flights that read as ONE stair stack: the same name (a
            # tower's "tower stair" floor after floor), or a spiral; a box
            # staircase up and stone stairs down are two stairs, two places
            same_name = a.name.strip().casefold() == b.name.strip().casefold()
            if not same_name and "spiral" not in (a.kind, b.kind):
                continue
            parent[find(b.id)] = find(a.id)
    groups = {}
    for st in stairs:
        groups.setdefault(find(st.id), []).append(st)
    shafts = []
    for gid, flights in groups.items():
        flights.sort(key=lambda st: rooms[st.low]["level"])
        levels = sorted({rooms[st.low]["level"] for st in flights} | {rooms[st.high]["level"] for st in flights})
        block = rooms[flights[0].low]["block"]
        kind = next((st.kind for st in flights if st.kind), None)
        if kind is None:
            counts = [sum(1 for r in rooms.values() if r["block"] == block and r["level"] == lv) for lv in levels]
            if max(counts) <= 1:
                kind = "spiral"
            elif len(levels) >= 3:
                kind = "u"
            else:
                kind = "straight"
        shafts.append(_Shaft(flights[0].id, flights[0].name, flights, levels, block,
                             flights[0].enclosed, flights[0].door, kind,
                             asked=any(st.kind for st in flights)))
    for sh in shafts:
        for lv in sh.levels:
            hid = f"{sh.id}@{lv}"
            layout.names[hid] = sh.name
            layout.purposes[hid] = "stair"
    return shafts


def _hall_rooms(shafts, rooms):
    """Each shaft's stair hall on each storey, as a room joined to the rooms
    its flights serve there: through its door when enclosed, open when not."""
    halls = {}
    for sh in shafts:
        for lv in sh.levels:
            joins = []
            for st in sh.flights:
                for rid in (st.low, st.high):
                    if rooms[rid]["level"] == lv and all(j["to"] != rid for j in joins):
                        at = st.at.get(rid)
                        joins.append({"to": rid, "side": _OPP[at] if at else None,
                                      "kind": sh.door if sh.enclosed else "open"})
            halls[f"{sh.id}@{lv}"] = {"id": f"{sh.id}@{lv}", "name": sh.name, "level": lv, "block": sh.block,
                                      "purpose": "stair", "joins": joins, "fixtures": [], "zones": [],
                                      "details": [], "contents": {}, "shaft": sh.id, "synthetic": True}
    return halls


def _joins(rid, rooms):
    """(other room, side of rid where it lies, order, kind) for every join
    between two rooms, whichever room wrote it."""
    out = {}
    for j in rooms[rid].get("joins") or ():
        to = j.get("to")
        if to in rooms and to != rid:
            sd = str(j.get("side") or "")[:1]
            out[to] = (sd if sd in _SIDES else None, j.get("order"), j.get("kind") or "door")
    for other, r in rooms.items():
        if other == rid:
            continue
        for j in r.get("joins") or ():
            if j.get("to") == rid and other not in out:
                sd = str(j.get("side") or "")[:1]
                out[other] = (_OPP[sd] if sd in _SIDES else None, j.get("order"), j.get("kind") or "door")
    return out


# ------------------------------------------------------------ outlines

def _outline_dims(area, front, rooms_here):
    """An outline near `area`, its long side across the front; a block of
    one room per storey (a tower) is as near square as its room is."""
    aspect = 1.0 if rooms_here <= 1 else 1.4
    long_ = max(3, round(math.sqrt(area * aspect)))
    short = max(3, math.ceil(area / long_))
    return (long_, short) if front in "ns" else (short, long_)


def _level_need(b, rooms, shafts):
    """Square paces each storey of block `b` needs: its rooms and the stair
    halls through it."""
    need = {}
    for r in rooms.values():
        if r["block"] == b:
            # a stated size sets its room, not the building: the outline
            # comes from what each storey holds
            need[r["level"]] = need.get(r["level"], 0) + room_target(r, stated=False)
    for sh in shafts:
        if sh.block == b:
            w, d = STAIRS[sh.kind]
            for lv in sh.levels:
                need[lv] = need.get(lv, 0) + w * d
    return need


def _place_blocks(spec, rooms, shafts, front, layout):
    """{block: {level: outline Rect}}: each block sized from its largest
    full storey, placed beside (or apart from) the block it names."""
    blocks = {}
    for r in rooms.values():
        blocks.setdefault(r["block"], set()).add(r["level"])
    smaller = {int(s.get("level") or 0) for s in spec.get("storeys") or ()
               if isinstance(s, dict) and s.get("smaller")}
    declared = {str(b.get("id")): b for b in spec.get("blocks") or () if isinstance(b, dict) and b.get("id")}
    dims = {}
    for b, levels in blocks.items():
        need = _level_need(b, rooms, shafts)
        # A STOREY UNDER THE ROOF NEVER SIZES ITS BLOCK: it fits itself to
        # the floor below (`carried`, below), so the outline comes from the
        # storeys that stand full. Until 2026-10-10 a smaller storey's need,
        # taken at a quarter more for its inset, could: the roof room of the
        # owner's shrine (chat 164), its nest asked huge, grew the whole
        # building to 20 by 14 and left the ground floor's spare to its stair
        # halls, one a 20 by 5 band. A block of none but smaller storeys is
        # sized from them as before.
        full = ([n for lv, n in need.items() if not (lv in smaller and lv > 0)]
                or [n * 1.25 for n in need.values()])
        count = max(sum(1 for r in rooms.values() if r["block"] == b and r["level"] == lv) for lv in levels)
        dims[b] = _outline_dims(max(full) * 1.05, front, count)
    # the entrance's block stands first, at the origin
    entrance = (spec.get("entrance") or {}).get("room")
    first = rooms[entrance]["block"] if entrance in rooms else max(dims, key=lambda b: dims[b][0] * dims[b][1])
    placed = {first: Rect(0, 0, *dims[first])}
    pending = [b for b in dims if b != first]
    for _round in range(len(pending) + 1):
        for b in list(pending):
            decl = declared.get(b, {})
            beside = decl.get("beside") or {}
            anchor = beside.get("block") if beside.get("block") in placed else first
            side = str(beside.get("side") or "")[:1]
            if not beside:
                # a block placed already may say it stands beside this one:
                # this one stands on the other side of it
                for pb, pdecl in declared.items():
                    pbes = pdecl.get("beside") or {}
                    if pb in placed and pbes.get("block") == b and str(pbes.get("side") or "")[:1] in _SIDES:
                        anchor, side = pb, _OPP[str(pbes["side"])[:1]]
                        decl = dict(decl, apart=pdecl.get("apart"))
                        break
            if anchor not in placed:
                continue
            a = placed[anchor]
            w, d = dims[b]
            gap = 3 if decl.get("apart") else 0
            if side not in _SIDES:
                side = {"n": "e", "s": "e", "e": "n", "w": "n"}[front]
            if side == "n":
                r = Rect(a.x + (a.w - w) // 2, a.y - d - gap, w, d)
            elif side == "s":
                r = Rect(a.x + (a.w - w) // 2, a.y + a.d + gap, w, d)
            elif side == "e":
                r = Rect(a.x + a.w + gap, a.y + (a.d - d) // 2, w, d)
            else:
                r = Rect(a.x - w - gap, a.y + (a.d - d) // 2, w, d)
            # TOWARD ONE END OF THAT SIDE: an outbuilding the plan joins to
            # open ground on this side stands toward the end the plan bears
            # it to, past the anchor's corner, never across its front
            toward = str(decl.get("toward") or "")[:1]
            if toward in _SIDES and toward not in (side, _OPP[side]):
                if toward == "w":
                    r = Rect(a.x - w, r.y, w, d)
                elif toward == "e":
                    r = Rect(a.x + a.w, r.y, w, d)
                elif toward == "n":
                    r = Rect(r.x, a.y - d, w, d)
                else:
                    r = Rect(r.x, a.y + a.d, w, d)
            # TWO BLOCKS NEVER STAND ON ONE RECTANGLE: one the plan bears the
            # same way as another stands on past it (a review of 2026-10-14:
            # two outbuildings on one bearing were laid on one rectangle and
            # one was always dropped)
            if decl.get("apart"):
                way = toward if toward in _SIDES and toward not in (side, _OPP[side]) \
                    else {"n": "e", "s": "e", "e": "s", "w": "s"}[side]
                sx, sy = _STEP[way]

                def crowds(p, r):
                    # on it, or one pace off it face to face: ground no place
                    # is read to hold, and a door into it opened onto nothing
                    if r.cells() & p.cells():
                        return True
                    gx = max(p.x - (r.x + r.w), r.x - (p.x + p.w))
                    gy = max(p.y - (r.y + r.d), r.y - (p.y + p.d))
                    return (gx == 1 and gy < 0) or (gy == 1 and gx < 0)

                # a block standing only below ground crowds nothing on it:
                # an outbuilding over a cavern's footprint was moved off it,
                # and the lab's shrine with it, by the order its rooms came
                # in (a review of 2026-10-14)
                standing = [p for pb, p in placed.items()
                            if any(lv >= 0 for lv in blocks.get(pb) or (0,))]
                for _step in range(len(placed) + 1):
                    if not any(crowds(p, r) for p in standing):
                        break
                    r = Rect(r.x + sx * (w + BLOCK_GAP), r.y + sy * (d + BLOCK_GAP), w, d)
            # a block attached on the front or back keeps the building's front line
            placed[b] = r
            pending.remove(b)
    out = {}
    for b, levels in blocks.items():
        base = placed[b]
        out[b] = {}
        need = _level_need(b, rooms, shafts)
        # a storey carries the storeys above it: it covers at least what they need
        carried = dict(need)
        for lv in sorted((lv for lv in levels if lv > 0), reverse=True):
            # a storey under the roof (smaller by the roofline) fits itself to
            # the floor below; it never makes that floor grow
            above = 0 if (lv + 1) in smaller else carried.get(lv + 1, 0)
            carried[lv] = max(need.get(lv, 0), above)
        # a tower -- every storey one room -- keeps one cross-section
        tower = all(sum(1 for r in rooms.values() if r["block"] == b and r["level"] == lv) <= 1
                    for lv in levels)
        if tower:
            layout.towers.add(b)
        for lv in sorted(levels, key=lambda v: (v < 0, abs(v))):
            o = base
            if lv != 0 and not tower and carried.get(lv, 0) * PART_SLACK < PART_SHARE * base.w * base.d:
                # A STOREY THAT HOLDS LESS COVERS PART OF THE BUILDING -- an
                # upper floor over part of the house, the rest of it roof; a
                # cellar under part of it. A compact part, as near square as
                # the building allows, centred in it.
                area = carried[lv] * PART_SLACK
                side = math.sqrt(area)
                w = max(3, min(base.w, math.ceil(side)))
                d = max(3, min(base.d, math.ceil(area / w)))
                w = max(3, min(base.w, math.ceil(area / d)))
                o = Rect(base.x + (base.w - w) // 2, base.y + (base.d - d) // 2, w, d)
                # it sits toward the wall its stairs are asked to climb from on
                # the storey it opens from, so they can stand there
                toward = [st.at.get(rid) for sh in shafts if sh.block == b for st in sh.flights
                          for rid in (st.low, st.high)
                          if rooms[rid]["level"] == (lv - 1 if lv > 0 else lv + 1)
                          and lv in (rooms[st.low]["level"], rooms[st.high]["level"]) and st.at.get(rid)]
                if toward:
                    side_to = max(set(toward), key=toward.count)
                    if side_to == "n":
                        o = Rect(o.x, base.y, o.w, o.d)
                    elif side_to == "s":
                        o = Rect(o.x, base.y + base.d - o.d, o.w, o.d)
                    elif side_to == "w":
                        o = Rect(base.x, o.y, o.w, o.d)
                    else:
                        o = Rect(base.x + base.w - o.w, o.y, o.w, o.d)
                base_lv = o
            else:
                base_lv = base
            o = base_lv
            if lv in smaller and lv > 0 and not tower and min(o.w, o.d) >= 6:
                # under the roof: the eaves along the front and back take a
                # pace of floor each; the gable ends keep their height
                o = (Rect(o.x, o.y + 1, o.w, o.d - 2) if front in "ns"
                     else Rect(o.x + 1, o.y, o.w - 2, o.d))
            # an upper storey stands within the one below it
            if lv > 0 and (lv - 1) in out[b]:
                lo = out[b][lv - 1]
                x0, y0 = max(o.x, lo.x), max(o.y, lo.y)
                x1, y1 = min(o.x + o.w, lo.x + lo.w), min(o.y + o.d, lo.y + lo.d)
                o = Rect(x0, y0, max(1, x1 - x0), max(1, y1 - y0))
            out[b][lv] = o
    layout.blocks = {rid: r["block"] for rid, r in rooms.items()}
    layout.apart = {b for b, decl in declared.items() if decl.get("apart")}
    return out


# ------------------------------------------------------------ dividing a storey
#
# After Marson & Musse (squarified treemaps) and Lopes et al. (zones before
# rooms), with the stair halls placed first as Hahn et al. place everything
# that spans storeys: a storey is the outline LESS its stair halls, cut into
# pieces around them, the pieces shared among the rooms in zone order, and
# each piece cut by squarified guillotine -- every cut chosen to keep its
# pieces near square, so a room is never a strip.

#: Zones a room belongs to by purpose: what is public lies toward the
#: entrance, what is private away from it (the privacy gradient).
_ZONE = {"living": 0, "hall": 0, "common_room": 0, "dining": 0, "entryway": 0, "shrine": 0,
         "kitchen": 1, "washroom": 1, "bath": 1, "toilet": 1, "latrine": 1, "storage": 1,
         "closet": 1, "cellar": 1, "basement": 1, "workshop": 1,
         "bedroom": 2, "guest_room": 2, "study": 2, "meditation": 2, "office": 2, "attic": 2,
         "cell": 2, "hallway": 1, "corridor": 1, "stair": 1, "other": 0}
_PRIVATE = 2


def _aspect(r):
    return max(r.w, r.d) / max(1, min(r.w, r.d))


def _cut(length, share, jitter):
    """Where to cut a side of `length`: at the weights' share, wandered by
    `jitter`, and never leaving a piece thinner than three paces when the
    side can afford two such pieces -- a room is not a sliver."""
    cut = round(length * share) + jitter
    if length >= 6:
        cut = max(3, min(length - 3, cut))
    return max(1, min(length - 1, cut))


def _slice(rect, items, out, rng):
    """Squarified guillotine: split `rect` among `items` [(id, weight)] in
    order. Of the split points and cut directions that keep the weights
    near balanced, the one whose two pieces are nearest square is taken
    (most of the time: the search wants variety too)."""
    if not items:
        return
    if len(items) == 1:
        out[items[0][0]] = rect
        return
    total = sum(w for _i, w in items) or 1.0
    shares, acc = [], 0.0
    for k in range(1, len(items)):
        acc += items[k - 1][1]
        shares.append((k, acc / total))
    near = [k for k, sh in shares if 0.25 <= sh <= 0.75] or [min(shares, key=lambda t: abs(t[1] - 0.5))[0]]
    share_of = dict(shares)
    options = []
    for k in near:
        for across in (True, False):
            length = rect.w if across else rect.d
            if length < 2:
                continue
            cut = _cut(length, share_of[k], 0)
            if across:
                a, b = Rect(rect.x, rect.y, cut, rect.d), Rect(rect.x + cut, rect.y, rect.w - cut, rect.d)
            else:
                a, b = Rect(rect.x, rect.y, rect.w, cut), Rect(rect.x, rect.y + cut, rect.w, rect.d - cut)
            # a piece holding n rooms is fine n times as long as it is wide
            worst = max(_aspect(a) / max(1, k), _aspect(b) / max(1, len(items) - k))
            options.append((worst, k, across))
    if not options:
        out[items[0][0]] = rect
        return
    options.sort()
    _w, k, across = options[0] if rng.random() < 0.65 else rng.choice(options)
    jitter = rng.choice((-1, 0, 0, 1))
    length = rect.w if across else rect.d
    cut = _cut(length, share_of[k], jitter)
    if across:
        _slice(Rect(rect.x, rect.y, cut, rect.d), items[:k], out, rng)
        _slice(Rect(rect.x + cut, rect.y, rect.w - cut, rect.d), items[k:], out, rng)
    else:
        _slice(Rect(rect.x, rect.y, rect.w, cut), items[:k], out, rng)
        _slice(Rect(rect.x, rect.y + cut, rect.w, rect.d - cut), items[k:], out, rng)


def _mirror(rect, frame, fx, fy):
    x = frame.x + frame.w - (rect.x - frame.x) - rect.w if fx else rect.x
    y = frame.y + frame.d - (rect.y - frame.y) - rect.d if fy else rect.y
    return Rect(x, y, rect.w, rect.d)


def _order(ids, rooms, rng):
    """Rooms in zone order -- public, service, private, the public zone
    first most of the time -- each zone in breadth-first order of its joins,
    so a cut tends to fall between zones and joined rooms stay together."""
    zones = {}
    for i in ids:
        zones.setdefault(_ZONE.get(purpose_key(rooms[i]) if i in rooms else "other", 0), []).append(i)
    keys = sorted(zones)
    if rng.random() < 0.3:
        rng.shuffle(keys)
    out = []
    for z in keys:
        group = zones[z]
        seen, queue = set(), [rng.choice(group)]
        while len(seen) < len(group):
            if not queue:
                queue = [next(i for i in group if i not in seen)]
            rid = queue.pop(0)
            if rid in seen:
                continue
            seen.add(rid)
            out.append(rid)
            nxt = [o for o in (_joins(rid, rooms) if rid in rooms else {}) if o in group and o not in seen]
            rng.shuffle(nxt)
            queue.extend(nxt)
    return out


def _carve(rect, holes, rng):
    """`rect` less the stair halls in it, as rectangles: the first hall cut
    out by two cuts each way, the rest carved from the pieces."""
    inside = [h for h in holes if h.overlaps(rect)]
    if not inside:
        return [rect]
    h = inside[0]
    hx0, hy0 = max(h.x, rect.x), max(h.y, rect.y)
    hx1, hy1 = min(h.x + h.w, rect.x + rect.w), min(h.y + h.d, rect.y + rect.d)
    if rng.random() < 0.5:
        pieces = [Rect(rect.x, rect.y, hx0 - rect.x, rect.d), Rect(hx1, rect.y, rect.x + rect.w - hx1, rect.d),
                  Rect(hx0, rect.y, hx1 - hx0, hy0 - rect.y), Rect(hx0, hy1, hx1 - hx0, rect.y + rect.d - hy1)]
    else:
        pieces = [Rect(rect.x, rect.y, rect.w, hy0 - rect.y), Rect(rect.x, hy1, rect.w, rect.y + rect.d - hy1),
                  Rect(rect.x, hy0, hx0 - rect.x, hy1 - hy0), Rect(hx1, hy0, rect.x + rect.w - hx1, hy1 - hy0)]
    out = []
    for p in pieces:
        if p.w > 0 and p.d > 0:
            out += _carve(p, inside[1:], rng)
    return out


def _spare_name(level, area):
    if area < 6:
        return "Cupboard"
    return "Store" if level == 0 else ("Loft space" if level > 0 else "Undercroft")


def _fill(pieces, order, weights, out, rng, level):
    """Share the pieces among the rooms like packing bins: the largest room
    first, each into the piece with the most of its share left; then each
    piece cut among its rooms in zone order. A piece no room takes is floor
    left over -- absorbed by a neighbour afterwards where it can be."""
    total_w = sum(weights[i] for i in order) or 1.0
    total_a = sum(p.w * p.d for p in pieces) or 1
    scale = total_w / total_a
    left = {n: p.w * p.d * scale for n, p in enumerate(pieces)}
    holds = {n: [] for n in left}
    if rng.random() < 0.5:
        # as bins: the largest room first, into the piece with most room left
        for rid in sorted(order, key=lambda i: (-weights[i], rng.random())):
            n = max(left, key=lambda k: (left[k], rng.random()))
            holds[n].append(rid)
            left[n] -= weights[rid]
    else:
        # in order: joined rooms stay together, the pieces taken in turn
        ranked = sorted(left, key=lambda k: ((pieces[k].x, pieces[k].y) if rng.random() < 0.5
                                             else (pieces[k].y, pieces[k].x)))
        k = 0
        for n in ranked:
            acc = 0.0
            while k < len(order) and (n == ranked[-1] or acc + weights[order[k]] / 2 <= left[n]):
                holds[n].append(order[k])
                acc += weights[order[k]]
                k += 1
    rank = {rid: k for k, rid in enumerate(order)}
    for n, p in enumerate(pieces):
        take = sorted(holds[n], key=lambda i: rank[i])
        if take:
            _slice(p, [(i, weights[i]) for i in take], out, rng)
        else:
            out[f"spare:{level}:{p.x}:{p.y}"] = p


def _transpose(r):
    return Rect(r.y, r.x, r.d, r.w)


def _spine(outline, holes, ids, rooms, weights, rng):
    """A corridor down the outline's long axis, rooms in bands either side
    of it. A stair hall either ends the corridor (it spans the corridor's
    width at one end) or stands in a band as a slot of the band's full
    depth; positions where the halls fit neither way are not offered."""
    hubs = [i for i in ids if purpose_key(rooms[i]) in CORRIDORS]
    if not hubs:
        return None
    horiz = outline.w >= outline.d
    if rng.random() < 0.15:
        horiz = not horiz
    if not horiz:
        parts = _spine_h(_transpose(outline), [_transpose(h) for h in holes], ids, rooms, weights, rng,
                         flip=True)
        return None if parts is None else {i: _transpose(r) for i, r in parts.items()}
    return _spine_h(outline, holes, ids, rooms, weights, rng)


def _spine_h(o, holes, ids, rooms, weights, rng, flip=False):
    hub = max((i for i in ids if purpose_key(rooms[i]) in CORRIDORS), key=lambda i: len(_joins(i, rooms)))
    js = _joins(hub, rooms)
    # in transposed space north/south became west/east
    a_side, b_side = ("w", "e") if flip else ("n", "s")
    bands = {"a": [], "b": []}
    rest = []
    for rid in ids:
        if rid == hub:
            continue
        side = js.get(rid, (None,))[0]
        if side == a_side:
            bands["a"].append(rid)
        elif side == b_side:
            bands["b"].append(rid)
        else:
            rest.append(rid)
    for rid in rest:
        home = next((k for k in bands for x in bands[k] if x in _joins(rid, rooms)), None)
        if home is None:
            home = min(bands, key=lambda k: sum(weights[x] for x in bands[k]))
        bands[home].append(rid)
    for k in bands:
        bands[k].sort(key=lambda x: (js.get(x, (None, None))[1] or 99, rng.random()))
    W, D = o.w, o.d
    valid = []
    for width in ((2, 3) if D >= 10 else (2,)):
        for off in range(0, D - width + 1):
            da, db = off, D - width - off
            if (bands["a"] and da < 3) or (bands["b"] and db < 3):
                continue
            if (not bands["a"] and da) or (not bands["b"] and db):
                continue
            strips = [(0, da), (da, da + width), (da + width, D)]
            fixed = {0: [], 1: [], 2: []}
            ok = True
            for h in holes:
                rx0, rx1, ry0, ry1 = h.x - o.x, h.x + h.w - o.x, h.y - o.y, h.y + h.d - o.y
                touched = [n for n, (s0, s1) in enumerate(strips) if s1 > s0 and ry0 < s1 and ry1 > s0]
                if not touched or ry0 != strips[touched[0]][0] or ry1 != strips[touched[-1]][1]:
                    ok = False
                    break
                if 1 in touched and not (rx0 == 0 or rx1 == W):
                    ok = False
                    break
                for n in touched:
                    fixed[n].append((rx0, rx1))
            if ok:
                valid.append((width, off, fixed))
    if not valid:
        return None
    width, off, fixed = rng.choice(valid)
    da = off
    out = {}
    # the corridor: its strip less the halls that end it
    cx0, cx1 = 0, W
    for x0, x1 in sorted(fixed[1]):
        if x0 == 0:
            cx0 = max(cx0, x1)
        if x1 == W:
            cx1 = min(cx1, x0)
    if cx1 - cx0 < 2:
        return None
    out[hub] = Rect(o.x + cx0, o.y + da, cx1 - cx0, width)
    for key, n, y0, depth in (("a", 0, 0, da), ("b", 2, da + width, D - da - width)):
        if not bands[key]:
            continue
        free, x = [], 0
        for x0, x1 in sorted(fixed[n]):
            if x0 > x:
                free.append((x, x0))
            x = max(x, x1)
        if x < W:
            free.append((x, W))
        total = sum(x1 - x0 for x0, x1 in free) or 1
        rooms_left = list(bands[key])
        wsum = sum(weights[r] for r in rooms_left) or 1
        for m, (x0, x1) in enumerate(free):
            seg = Rect(o.x + x0, o.y + y0, x1 - x0, depth)
            share = (x1 - x0) / total
            take, acc = [], 0.0
            while rooms_left and (m == len(free) - 1 or not take or acc + weights[rooms_left[0]] / 2 <= share * wsum):
                take.append(rooms_left.pop(0))
                acc += weights[take[-1]]
                if m < len(free) - 1 and acc >= share * wsum:
                    break
            if take:
                _slice_band(seg, take, weights, out, along_x=True)
            else:
                out[f"spare:0:{seg.x}:{seg.y}"] = seg
    return out


def _slice_band(band, ids, weights, out, along_x):
    total = sum(weights[i] for i in ids) or 1.0
    length = band.w if along_x else band.d
    pos = 0
    for k, rid in enumerate(ids):
        if k == len(ids) - 1:
            n = length - pos
        else:
            n = max(3, round(length * weights[rid] / total))
            n = min(n, length - pos - 3 * (len(ids) - k - 1))
        if n < 1:
            return
        out[rid] = (Rect(band.x + pos, band.y, n, band.d) if along_x
                    else Rect(band.x, band.y + pos, band.w, n))
        pos += n


def _absorb(out, rooms, halls=None):
    """A leftover piece joins the room beside it when the two together are
    still a rectangle -- the room takes the floor; only a piece no room can
    take whole stays a store. Stair halls and corridors take none."""
    changed = True
    while changed:
        changed = False
        for sid in [k for k in out if k.startswith("spare:") and ":x" not in k[6:]]:
            p = out[sid]
            # a room takes it first; failing that a stair hall, as landing
            cands = sorted(out.items(), key=lambda t: purpose_key(rooms.get(t[0], {})) == "stair")
            for rid, r in cands:
                if rid.startswith("spare:") or purpose_key(rooms.get(rid, {})) in CORRIDORS:
                    continue
                # a landing is at most about the size of its stair -- measured
                # against the stair as placed, so landings never chain
                if purpose_key(rooms.get(rid, {})) == "stair":
                    own = (halls or {}).get(rid, r)
                    upper = sid.split(":")[1].lstrip("-").isdigit() and int(sid.split(":")[1]) > 0
                    if upper and r.w * r.d + p.w * p.d > own.w * own.d + max(4, own.w * own.d // 2):
                        continue
                merged = None
                if r.y == p.y and r.d == p.d and (r.x + r.w == p.x or p.x + p.w == r.x):
                    merged = Rect(min(r.x, p.x), r.y, r.w + p.w, r.d)
                elif r.x == p.x and r.w == p.w and (r.y + r.d == p.y or p.y + p.d == r.y):
                    merged = Rect(r.x, min(r.y, p.y), r.w, r.d + p.d)
                if merged is not None:
                    out[rid] = merged
                    del out[sid]
                    changed = True
                    break
            if changed:
                break
    return out


def _divide(outline, halls, ids, rooms, weights, rng, level):
    """One division of a storey's outline among its rooms around its stair
    halls ({hall id: Rect}). A hall may grow by a landing in _absorb; the
    stair itself stays where it was put, the same on every storey."""
    holes = list(halls.values())
    if any(purpose_key(rooms[i]) in CORRIDORS for i in ids) and rng.random() < 0.6:
        parts = _spine(outline, holes, ids, rooms, weights, rng)
        if parts is not None:
            parts.update(halls)
            return _absorb(parts, rooms, halls)
    out = {}
    pieces = _carve(outline, holes, rng)
    _fill(pieces, _order(ids, rooms, rng), weights, out, rng, level)
    out.update(halls)
    _absorb(out, rooms, halls)
    if not holes:
        fx, fy = rng.random() < 0.5, rng.random() < 0.5
        out = {i: _mirror(r, outline, fx, fy) for i, r in out.items()}
    return out


# ------------------------------------------------------------ stair halls first

def _stair_shapes(kind):
    """The shapes a shaft's hall is tried at, in order: its own, then the
    fallback's shapes that come after it in `STAIRS` (longest run first).
    A shape the fallback does not hold -- an L a spec asked for by name --
    is still tried first and still gives way as it always did; it is only
    never reached FROM another shape."""
    order = list(STAIRS)
    later = order[order.index(kind) + 1:] if kind in order else []
    return (kind,) + tuple(k for k in later if k in STAIR_FALLBACK)


def _shaft_spots(shaft, outlines, rng):
    """Where a shaft's hall may stand: inside every storey it spans, against
    a wall of the space they share (stairs climb beside a wall), or on the
    middle line of that space (a stair hall at the core)."""
    region = None
    for lv in shaft.levels:
        o = outlines[shaft.block][lv]
        region = o if region is None else Rect(
            max(region.x, o.x), max(region.y, o.y),
            min(region.x + region.w, o.x + o.w) - max(region.x, o.x),
            min(region.y + region.d, o.y + o.d) - max(region.y, o.y))
    out = set()
    # the shape asked or ruled first; when the rule chose it, the next more
    # compact shape is offered too (a turning stair where a straight run
    # crowds the storey), at a small cost in the scoring
    tried = 0
    for kind in _stair_shapes(shaft.kind):
        w0, d0 = STAIRS[kind]
        for w, d in {(w0, d0), (d0, w0)}:
            if w > region.w or d > region.d:
                continue
            # along each wall: its two ends and its middle
            xs = sorted({region.x, region.x + (region.w - w) // 2, region.x + region.w - w})
            ys = sorted({region.y, region.y + (region.d - d) // 2, region.y + region.d - d})
            for x in xs:
                out.add((kind, Rect(x, region.y, w, d)))
                out.add((kind, Rect(x, region.y + region.d - d, w, d)))
            for y in ys:
                out.add((kind, Rect(region.x, y, w, d)))
                out.add((kind, Rect(region.x + region.w - w, y, w, d)))
            out.add((kind, Rect(region.x + (region.w - w) // 2, region.y + (region.d - d) // 2, w, d)))
        if out:
            tried += 1
            if shaft.asked or tried >= 2:
                break
    return sorted(out, key=lambda t: (t[1].x, t[1].y, t[1].w))


# ------------------------------------------------------------ scoring

def _score(parts, ids, rooms, weights, outline, fixed, outward, outward_weight, level, sheer=False):
    """Lower is better: a room missing, a join with no wall to open in, a
    join on the wrong side, a room too thin or too long, a room far from its
    size, a room that opens outdoors with no outside wall, a private room on
    the front, a store with no room beside it to open from."""
    s = 0.0
    for rid in ids:
        if rid not in parts:
            s += 300
    every = dict(fixed)
    every.update(parts)
    roof = set() if sheer else _roof_cells(parts, outline, level)

    def on_edge(r, side):
        if _on_edge(r, outline, side):
            return True
        if not roof:
            return False
        dx, dy = _STEP[side]
        own = r.cells()
        return all((c[0] + dx, c[1] + dy) in roof or (c[0] + dx, c[1] + dy) in own for c in own)

    for rid, r in parts.items():
        if rid.startswith("spare:"):
            lo_side = min(r.w, r.d)
            # a store is floor no room asked for: tolerated, never sought --
            # and a sliver nobody can stand in is waste
            s += (25 if lo_side < 2 else (8 if lo_side < 3 else 4)) + 0.25 * r.w * r.d
            if not any(_shared_wall(r, o)[0] for oid, o in parts.items()
                       if oid != rid and not oid.startswith("spare:") and purpose_key(rooms[oid]) != "stair"):
                s += 25
            continue
        key = purpose_key(rooms[rid])
        lo_side, hi_side = sorted((r.w, r.d))
        if key != "stair":
            if lo_side < 2:
                s += 80
            elif lo_side < 3 and key not in CORRIDORS and key not in ("closet", "toilet", "latrine"):
                s += 12
            longest = max((max(w, d) for w, d, _h in (fixture_footprint(f) for f in rooms[rid].get("fixtures") or ())),
                          default=1)
            if hi_side < longest:
                s += 20
            if key not in CORRIDORS and hi_side / lo_side > 2.0:
                s += (hi_side / lo_side - 2.0) * 18
            if key in CORRIDORS and lo_side > 3:
                s += (lo_side - 3) * 10
            s += 3 * abs(math.log((r.w * r.d) / max(1.0, weights.get(rid, r.w * r.d))))
            if level == 0 and _ZONE.get(key) == _PRIVATE and _on_edge(r, outline, outward.get("_front", "s")):
                s += 5
        for other, (side, _o, _k) in _joins(rid, rooms).items():
            if other not in every or (other in parts and other < rid):
                continue
            got, cells = _door_cells(r, every[other])
            if not cells:
                s += 60
            elif side and side != got:
                # a stair on the wrong wall is the fault a reader sees first
                stair = "stair" in (key, purpose_key(rooms[other]) if other in rooms else "")
                s += 45 if stair else 20
        want = outward.get(rid)
        if want is not None:
            sides = [want] if want in _SIDES else list(_SIDES)
            if not any(on_edge(r, sd) for sd in sides):
                s += outward_weight.get(rid, 15)
    return s


def _roof_cells(parts, outline, level):
    """Above the ground, floor no room takes that reaches the outline's edge
    is not floor at all: it is roof over the storey below, outside this
    storey's walls."""
    if level <= 0:
        return set()
    cells = set()
    for rid, r in parts.items():
        if rid.startswith("spare:") and any(_on_edge(r, outline, sd) for sd in _SIDES):
            cells |= r.cells()
    return cells


def _on_edge(r, outline, side):
    return {"n": r.y == outline.y, "s": r.y + r.d == outline.y + outline.d,
            "w": r.x == outline.x, "e": r.x + r.w == outline.x + outline.w}[side]


# ------------------------------------------------------------ the layout

@dataclass
class Layout:
    name: str
    front: str = "s"
    floors: dict = field(default_factory=dict)       # level -> {room_id: [Rect]}
    outlines: dict = field(default_factory=dict)     # block -> {level: Rect}
    stairwells: list = field(default_factory=list)
    zones: dict = field(default_factory=dict)        # room_id -> [{id, name, rect}]
    doors: list = field(default_factory=list)
    fixtures: dict = field(default_factory=dict)
    unplaced: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    names: dict = field(default_factory=dict)
    purposes: dict = field(default_factory=dict)
    blocks: dict = field(default_factory=dict)
    apart: set = field(default_factory=set)
    site: Rect | None = None
    areas: dict = field(default_factory=dict)        # area id -> set of cells
    ways: dict = field(default_factory=dict)         # way id -> {"cells", "side", ...}
    features: list = field(default_factory=list)
    elsewhere: list = field(default_factory=list)
    entrance: dict = field(default_factory=dict)
    details: dict = field(default_factory=dict)      # room_id -> [things on its walls or ceiling]
    windows: list = field(default_factory=list)      # {id, room, level, side, cell}
    voids: dict = field(default_factory=dict)        # level -> [Rect] open to the storey below
    roofs: dict = field(default_factory=dict)        # level -> [Rect] roof of the storey below, outside this one
    towers: set = field(default_factory=set)         # blocks whose walls rise sheer: no storey has roof beside it
    contents: dict = field(default_factory=dict)     # room_id -> {fixture_id: [things in or on it]}

    def as_dict(self):
        return {
            "name": self.name, "front": self.front,
            "floors": {str(lv): {rid: [r.as_dict() for r in rs] for rid, rs in rooms.items()}
                       for lv, rooms in sorted(self.floors.items())},
            "outlines": {b: {str(lv): r.as_dict() for lv, r in levels.items()}
                         for b, levels in self.outlines.items()},
            "stairwells": self.stairwells,
            "zones": {rid: [dict(z, rect=z["rect"].as_dict()) for z in zs] for rid, zs in self.zones.items()},
            "doors": self.doors,
            "fixtures": {rid: [dict(f, rect=f["rect"].as_dict()) for f in fx]
                         for rid, fx in self.fixtures.items()},
            "unplaced": self.unplaced, "warnings": self.warnings,
            "names": self.names, "purposes": self.purposes,
            "blocks": self.blocks, "apart": sorted(self.apart),
            "site": self.site.as_dict() if self.site else None,
            "areas": {a: [r.as_dict() for r in _runs(cs)] for a, cs in self.areas.items() if cs},
            "ways": {w: {"rects": [r.as_dict() for r in _runs(v["cells"])], "side": v.get("side")}
                     for w, v in self.ways.items() if v.get("cells")},
            "features": [dict(f, rect=f["rect"].as_dict()) for f in self.features],
            "elsewhere": self.elsewhere, "entrance": self.entrance,
            "details": self.details, "contents": self.contents, "windows": self.windows,
            "voids": {str(lv): [r.as_dict() for r in rs] for lv, rs in self.voids.items()},
            "roofs": {str(lv): [r.as_dict() for r in rs] for lv, rs in self.roofs.items()},
        }


def solve(spec, seed=SEED) -> Layout:
    rng = random.Random(seed)
    front = str(spec.get("front") or "s")[:1]
    front = front if front in _SIDES else "s"
    layout = Layout(name=str(spec.get("name") or "building"), front=front)
    layout.elsewhere = [e for e in spec.get("elsewhere") or () if isinstance(e, dict)]
    rooms, stairs = _read(spec, layout)
    if not rooms:
        layout.warnings.append("the spec holds no room")
        return layout
    entrance = dict(spec.get("entrance") or {})
    if entrance.get("room") not in rooms:
        entrance = {}
        layout.warnings.append("the spec names no entrance room")
    layout.entrance = entrance
    shafts = _shafts(rooms, stairs, layout)
    outlines = _place_blocks(spec, rooms, shafts, front, layout)
    layout.outlines = outlines
    halls = _hall_rooms(shafts, rooms)
    every = dict(rooms)
    every.update(halls)
    grounds = spec.get("grounds") or {}
    # a thing at a door (`at_door`) is opened onto by a door of its own
    things = {str(f.get("id")) for f in grounds.get("features") or ()
              if isinstance(f, dict) and isinstance(f.get("at_door"), dict)}
    outdoor_ids = {str(x.get("id")) for key in ("areas", "ways") for x in grounds.get(key) or ()
                   if isinstance(x, dict)} | things

    # rooms that open outdoors, and on which side: the entrance on the front
    outward, outward_weight = {"_front": front}, {}
    for rid, r in rooms.items():
        for j in r.get("joins") or ():
            if j.get("to") in outdoor_ids:
                sd = str(j.get("side") or "")[:1]
                outward[rid] = sd if sd in _SIDES else outward.get(rid, "any")
    if entrance:
        outward[entrance["room"]] = front
        outward_weight[entrance["room"]] = 40
    # a room joined to a room of another block stands on the wall facing it
    facing = {}
    for rid, r in rooms.items():
        for other, _j in _joins(rid, rooms).items():
            ob = rooms[other]["block"]
            if ob == r["block"]:
                continue
            a = outlines[r["block"]].get(r["level"])
            c = outlines[ob].get(rooms[other]["level"])
            if a is None or c is None:
                continue
            side = ("e" if a.x + a.w <= c.x else "w" if c.x + c.w <= a.x else
                    "s" if a.y + a.d <= c.y else "n" if c.y + c.d <= a.y else None)
            if side:
                facing.setdefault(r["level"], {})[rid] = side
                # standing off that wall, the join has no doorway and the
                # building is refused for it (`layout_bridge.refusals`), so it
                # costs what a missing doorway costs, not an outward room's 15:
                # at 15 the owner's shrine (chat 164, 2026-10-10) set its
                # basement off the wall its Seal Cavern stands beyond, in every
                # one of 20 seeds
                outward_weight[rid] = max(outward_weight.get(rid, 0), 60)

    def weights_for(ids, free_area):
        """Each room's share: what it needs, grown toward its ceiling when the
        storey has floor to spare; floor beyond every ceiling is a store."""
        t = {i: room_target(rooms[i]) for i in ids}
        cap = {i: (t[i] * 1.15 if _stated_area(rooms[i]) else
                   max(PURPOSE_AREA[purpose_key(rooms[i])][1], t[i]) * MAX_GROWTH) for i in ids}
        spare = free_area - sum(t.values())
        flex = [i for i in ids if purpose_key(rooms[i]) in FLEXIBLE] or list(ids)
        for _round in range(3):
            room_for = [i for i in flex if t[i] < cap[i]]
            if spare <= 0.5 or not room_for:
                break
            tf = sum(t[i] for i in room_for) or 1.0
            given = 0.0
            for i in room_for:
                add = min(cap[i] - t[i], spare * t[i] / tf)
                t[i] += add
                given += add
            spare -= given
        if spare > 0.5:
            # past every ceiling: the floor still goes to the rooms the
            # description names -- never to a room it does not
            # a room whose size the description states keeps it
            share = [i for i in ids if purpose_key(rooms[i]) not in CORRIDORS and not _stated_area(rooms[i])]
            if not share:
                return t, spare
            ts = sum(t[i] for i in share) or 1.0
            for i in share:
                t[i] += spare * t[i] / ts
        return t, 0.0

    # BLOCK BY BLOCK -- the entrance's first -- the stair halls are placed
    # first (several placements tried), every storey divided around them, and
    # the placement whose storeys score best kept.
    block_order = sorted(outlines, key=lambda b: (b != (rooms[entrance["room"]]["block"] if entrance else b)))
    chosen = {}          # (block, level) -> parts
    hall_at = {}         # shaft id -> (kind, Rect)
    for b in block_order:
        mine = [sh for sh in shafts if sh.block == b]
        spots = {sh.id: _shaft_spots(sh, outlines, rng) for sh in mine}

        def evaluate(pick, tries):
            # every placement is judged by the same sequence of divisions
            # (common random numbers), so comparing two placements compares
            # them, not their luck
            rng = random.Random(seed * 7919 + len(b))
            total, parts_by_level = 0.0, {}
            for lv in sorted(outlines[b]):
                outline = outlines[b][lv]
                ids = [rid for rid, r in rooms.items() if r["block"] == b and r["level"] == lv]
                holes = {f"{sid}@{lv}": rect for sid, (kind, rect) in pick.items()
                         if lv in next(sh.levels for sh in mine if sh.id == sid)}
                free_area = outline.w * outline.d - sum(h.w * h.d for h in holes.values())
                weights, spare = weights_for(ids, free_area)
                items = list(ids)
                if spare > max(6.0, 0.12 * free_area):
                    weights[f"spare:{lv}:x"] = spare
                    items.append(f"spare:{lv}:x")
                    every.setdefault(f"spare:{lv}:x", {"id": f"spare:{lv}:x", "purpose": "storage",
                                                       "level": lv, "block": b, "joins": [], "fixtures": []})
                # a shape other than the one asked or ruled costs a little
                for sid, (kind, _r) in pick.items():
                    if lv == min(next(sh.levels for sh in mine if sh.id == sid)) and \
                            kind != next(sh.kind for sh in mine if sh.id == sid):
                        total += 4
                # a hall leaving a sliver of one or two paces to the wall wastes it
                for h in holes.values():
                    for gap in (h.x - outline.x, outline.x + outline.w - h.x - h.w,
                                h.y - outline.y, outline.y + outline.d - h.y - h.d):
                        if gap in (1, 2):
                            total += 10
                fixed = {}
                for (b2, lv2), prts in chosen.items():
                    if lv2 == lv:
                        fixed.update(prts)
                ids_all = ids + list(holes)
                best_lv = None
                for _t in range(tries):
                    prts = _divide(outline, holes, items, every, weights, rng, lv)
                    out_here = dict(outward if lv == 0 else {"_front": front})
                    out_here.update(facing.get(lv, {}))
                    sc = _score(prts, ids_all, every, weights, outline, fixed, out_here, outward_weight, lv,
                                b in layout.towers)
                    if best_lv is None or sc < best_lv[0]:
                        best_lv = (sc, prts)
                total += best_lv[0]
                parts_by_level[lv] = best_lv[1]
            return total, parts_by_level

        def clashes(sh, spot, pick):
            return any(spot[1].overlaps(pick[o.id][1]) and set(o.levels) & set(sh.levels)
                       for o in mine if o.id in pick and o.id != sh.id)

        # START from a placement that fits, then IMPROVE one shaft at a time
        # against the others (coordinate descent), quickly; the best gets a
        # full search
        # the shafts with the fewest places go first; a start that blocks one
        # is tried again with other choices
        pick = {}
        ordered = sorted(mine, key=lambda sh: len(spots[sh.id]))
        for attempt in range(60):
            trial = {}
            for sh in ordered:
                options = [sp for sp in spots[sh.id] if not clashes(sh, sp, trial)]
                if options:
                    trial[sh.id] = options[len(options) // 2] if attempt == 0 else rng.choice(options)
            if len(trial) > len(pick):
                pick = trial
            if len(pick) == len(mine):
                break
        for sh in mine:
            if sh.id not in pick:
                layout.warnings.append(f"{sh.name} found no room for its stair hall")
        quick = QUICK
        current = evaluate(pick, quick)[0]
        for _round in range(2):
            for sh in mine:
                if sh.id not in pick:
                    continue
                for spot in spots[sh.id]:
                    if spot == pick[sh.id] or clashes(sh, spot, pick):
                        continue
                    trial = dict(pick)
                    trial[sh.id] = spot
                    sc = evaluate(trial, quick)[0]
                    if sc < current:
                        current, pick = sc, trial
        total, parts_by_level = evaluate(pick, TRIES)
        best = (total, parts_by_level, pick)
        _total, parts_by_level, pick = best
        for lv, prts in parts_by_level.items():
            chosen[(b, lv)] = prts
        hall_at.update(pick)

    # the layout's rooms: the spec's, the stair halls, and the stores left over
    for (b, lv), prts in chosen.items():
        # a tower's walls rise sheer: beside its stair is a well, never roof
        roof = set() if b in layout.towers else _roof_cells(prts, outlines[b][lv], lv)
        for rid, r in prts.items():
            if rid.startswith("spare:") and lv > 0 and r.cells() <= roof:
                layout.roofs.setdefault(lv, []).append(r)
                continue
            if rid.startswith("spare:") and lv > 0:
                # floor above the ground no named room can take whole is not a
                # room: it is open to the storey below
                layout.voids.setdefault(lv, []).append(r)
                continue
            if rid.startswith("spare:"):
                sid = f"store_{lv}_{r.x}_{r.y}".replace("-", "m")
                every[sid] = {"id": sid, "name": _spare_name(lv, r.w * r.d), "level": lv, "block": b,
                              "purpose": "storage", "joins": [], "fixtures": [], "zones": [],
                              "details": [], "contents": {}, "synthetic": True}
                layout.names[sid] = every[sid]["name"]
                layout.purposes[sid] = "storage"
                rid = sid
            layout.floors.setdefault(lv, {})[rid] = [r]
            layout.blocks[rid] = b
    for (b, lv), prts in chosen.items():
        for rid in [r for r, x in rooms.items() if x["block"] == b and x["level"] == lv]:
            if rid not in prts:
                layout.warnings.append(f"{layout.names[rid]} found no floor on storey {lv}")
    for k in [k for k in every if k.startswith("spare:")]:
        del every[k]
    # a store opens from the largest room beside it
    for sid, r in every.items():
        if not sid.startswith("store_"):
            continue
        rect = layout.floors[r["level"]][sid][0]
        beside = [(o[0].w * o[0].d, oid) for oid, o in layout.floors[r["level"]].items()
                  if oid != sid and every[oid].get("purpose") != "stair" and _door_cells(rect, o[0])[1]]
        if beside:
            r["joins"] = [{"to": max(beside)[1], "kind": "door"}]

    for sh in shafts:
        if sh.id not in hall_at:
            continue
        kind, rect = hall_at[sh.id]
        if kind != sh.kind:
            layout.warnings.append(f"{sh.name}: a {sh.kind} stair would not fit; it is a {kind} stair")
        layout.stairwells.append({
            "id": sh.id, "name": sh.name, "kind": kind, "levels": sh.levels, "rect": rect.as_dict(),
            "enclosed": sh.enclosed, "door": sh.door, "flights": [st.id for st in sh.flights],
            "halls": {str(lv): f"{sh.id}@{lv}" for lv in sh.levels}})

    approaches = {str(w.get("id")) for w in grounds.get("ways") or ()
                  if isinstance(w, dict) and str(w.get("from") or "") == "entrance"}
    _place_doors(layout, every, outdoor_ids, approaches, things)
    _place_windows(layout, every)
    _place_zones(layout, every)
    _furnish(layout, every)
    _grounds(layout, every, grounds)
    return layout


# ------------------------------------------------------------ doors

def _solid(layout, lv):
    """Cells no doorway may open from and no fixture may take. Stairs are
    rooms of their own now, so a room holds none."""
    return set()


def _room_cells(layout, rid, lv):
    cells = set()
    for r in layout.floors.get(lv, {}).get(rid, ()):
        cells |= r.cells()
    return cells


def _flight_ends(rect):
    """The two short ends of a straight flight's rectangle, `(a, b)`: each
    the row or column of cells a body steps onto or off it from, `a` the
    north or the west one."""
    r = Rect(**rect)
    if r.w >= r.d:
        return ({(r.x, r.y + j) for j in range(r.d)},
                {(r.x + r.w - 1, r.y + j) for j in range(r.d)})
    return ({(r.x + i, r.y) for i in range(r.w)},
            {(r.x + i, r.y + r.d - 1) for i in range(r.w)})


def _stair_doorways(layout, per_wall):
    """Where each doorway into the hall of an ENCLOSED STRAIGHT stair opens:
    `{(level, rid, other): cell of rid}`. A flight is climbed from its foot
    on the lowest storey it joins and left at its head on the top one, so a
    hall's doorway opens off the flight, or onto it only at the end its
    storey takes -- the foot below, the head above, either end on a storey
    between -- at the allowed cell nearest that end. The foot is whichever
    end of the flight costs the well's doorways fewer paces to reach it
    (ties: the north or west end), and is recorded on the stairwell as
    `foot` and `head`. Home 11 (2026-10-13): a doorway spread evenly along
    the shared wall opened onto the middle of a flight on 12 of the 29
    enclosed stair doorways over the lab's four baselines, Home 11 and the
    solver's test house; Home 11's brief has its stair "arrive at the north
    end of the Hallway". A doorway no cell
    allows keeps its even-spread cell, with a warning: never a refusal, and
    no room rectangle or seed depends on it. Open stairs and every other
    shape keep their placement."""
    out = {}
    for well in layout.stairwells:
        if well.get("kind") != "straight" or not well.get("enclosed"):
            continue
        a, b = _flight_ends(well["rect"])
        flight = Rect(**well["rect"]).cells()
        halls = {hall: int(lv) for lv, hall in (well.get("halls") or {}).items()}
        if not halls:
            continue
        low, top = min(halls.values()), max(halls.values())
        doors = []
        for (lv, rid, side), items in per_wall.items():
            for _o, other, cells, kind in items:
                if kind == "open":
                    continue
                if rid in halls:
                    doors.append(((lv, rid, other), lv, [tuple(c) for c in cells], None))
                elif other in halls:
                    dx, dy = _STEP[side]
                    doors.append(((lv, rid, other), lv,
                                  [(c[0] + dx, c[1] + dy) for c in cells], (dx, dy)))
        if not doors:
            continue

        def end_of(lv, foot, head):
            if lv == low and lv != top:
                return foot
            if lv == top and lv != low:
                return head
            return foot | head

        def allowed(lv, cells, foot, head):
            end = end_of(lv, foot, head)
            return [c for c in cells if c not in flight or c in end]

        def paces(c, end):
            return min(abs(c[0] - e[0]) + abs(c[1] - e[1]) for e in end)

        best = None
        for foot, head in ((a, b), (b, a)):
            cost = 0
            for _key, lv, cells, _step in doors:
                ok = allowed(lv, cells, foot, head)
                cost += min(paces(c, end_of(lv, foot, head)) for c in ok) if ok else 10 ** 6
            if best is None or cost < best[0]:
                best = (cost, foot, head)
        _cost, foot, head = best
        well["foot"] = [list(c) for c in sorted(foot)]
        well["head"] = [list(c) for c in sorted(head)]
        taken = set()                   # (storey, hall cell): each storey's hall its own
        for key, lv, cells, step in sorted(doors, key=lambda d: (d[1], str(d[0][1]), str(d[0][2]))):
            ok = [c for c in allowed(lv, cells, foot, head) if (lv, c) not in taken]
            if not ok:
                layout.warnings.append(
                    f"{layout.names.get(key[1], key[1])}: its doorway into {well.get('name') or 'the stair'} "
                    f"could not open at the end of the flight its storey is reached by")
                continue
            end = end_of(lv, foot, head)
            cell = min(ok, key=lambda c: (paces(c, end), c[1], c[0]))
            taken.add((lv, cell))
            out[key] = cell if step is None else (cell[0] - step[0], cell[1] - step[1])
    return out


def _place_doors(layout, rooms, outdoor_ids, approaches=frozenset(), things=frozenset()):
    """One doorway per join between rooms, spread along a shared wall in
    declared order; a doorway onto every enclosed stairwell; the entrance
    and every other outside door on the outside wall asked, one a wall --
    save a door onto a thing at a door (`things`), laid after the rest on the
    wall asked where a cell of it stands `THING_DOOR_GAP` paces clear of the
    room's other outside doors, else on another wall."""
    per_wall = {}
    done = set()
    for lv, parts in layout.floors.items():
        avoid = _solid(layout, lv)
        for rid in parts:
            for other, (side, order, kind) in _joins(rid, rooms).items():
                key = tuple(sorted((rid, other)))
                if key in done or other not in parts:
                    continue
                done.add(key)
                got, cells = _door_cells(parts[rid][0], parts[other][0], avoid)
                if not cells:
                    layout.warnings.append(f"{layout.names[rid]} and {layout.names[other]} "
                                           f"were to join but share no wall")
                    continue
                if side and side != got:
                    layout.warnings.append(f"{layout.names[other]} was asked on the {side} side of "
                                           f"{layout.names[rid]} and stands on the {got}")
                per_wall.setdefault((lv, rid, got), []).append((order or 0, other, cells, kind))
    for items in per_wall.values():
        items.sort(key=lambda t: t[0])
    # a doorway into a straight stair's hall opens at the end of the flight
    # its storey takes (`_stair_doorways`); every other doorway of the wall
    # is spread evenly over the cells left, as every doorway was before
    at_stair = _stair_doorways(layout, per_wall)
    for (lv, rid, side), items in per_wall.items():
        fixed = {k: at_stair[(lv, rid, other)] for k, (_o, other, _c, _kind) in enumerate(items)
                 if (lv, rid, other) in at_stair}
        rest = [k for k in range(len(items)) if k not in fixed]
        spread = {}
        for j, k in enumerate(rest):
            cells = items[k][2]
            free = [c for c in cells if tuple(c) not in set(fixed.values())] or cells
            spread[k] = free[min(len(free) - 1, int((j + 1) * len(free) / (len(rest) + 1)))]
        for k, (_o, other, cells, kind) in enumerate(items):
            pos = fixed[k] if k in fixed else spread[k]
            door = {"a": rid, "b": other, "level": lv, "side": side, "cell": list(pos), "kind": kind}
            if kind == "open":
                # an open stair: no wall between it and its room, the whole
                # shared wall open
                door["span"] = [list(c) for c in cells]
            if "stair" in (rooms.get(rid, {}).get("purpose"), rooms.get(other, {}).get("purpose")):
                door["stair"] = True
            layout.doors.append(door)
    # outside doors
    outside = {}
    for b, levels in layout.outlines.items():
        for lv, o in levels.items():
            outside.setdefault(lv, set()).update(o.cells())
    ent = layout.entrance.get("room")
    wants = {}
    for rid, r in rooms.items():
        for j in r.get("joins") or ():
            if j.get("to") in outdoor_ids:
                sd = str(j.get("side") or "")[:1]
                wants.setdefault(rid, []).append((j["to"], sd if sd in _SIDES else None, j.get("kind") or "door"))
    if ent:
        # the way the entrance opens onto is reached by the entrance door itself
        wants[ent] = [w for w in wants.get(ent, []) if w[0] not in approaches]
        wants[ent].insert(0, ("entrance", layout.front, layout.entrance.get("kind") or "door"))
    for rid, items in wants.items():
        lv = rooms[rid]["level"]
        room = layout.floors.get(lv, {}).get(rid)
        if not room:
            continue
        r = room[0]
        house = outside.get(lv, set())
        seen_sides, used = set(), []
        for target, side, kind in sorted(items, key=lambda t: t[0] in things):
            for sd in ([side] if side else []) + [x for x in _SIDES if x != side]:
                dx, dy = _STEP[sd]
                cells = [c for c in sorted(r.cells()) if (c[0] + dx, c[1] + dy) not in house
                         and (c[0] + dx, c[1] + dy) not in r.cells()]
                cells = [c for c in cells if c not in _solid(layout, lv)]
                if target in things:
                    # A THING AT A DOOR HAS A DOOR OF ITS OWN, clear of the
                    # room's other doors' ground: one door carrying two of the
                    # plan's ways met only one of them (a review of 2026-10-14)
                    def gap(c):
                        return min((abs(c[0] - u[0]) + abs(c[1] - u[1]) for u in used),
                                   default=THING_DOOR_GAP)
                    clear = [c for c in cells if gap(c) >= THING_DOOR_GAP]
                    if not clear:
                        continue
                    mid = len(cells) // 2
                    pos = min(clear, key=lambda c: abs(cells.index(c) - mid))
                elif sd in seen_sides or not cells:
                    continue
                else:
                    pos = cells[len(cells) // 2]
                if side and sd != side:
                    layout.warnings.append(f"{layout.names[rid]} opens to {target} on its {sd} side, "
                                           f"not the {side} asked")
                layout.doors.append({"a": rid, "b": target, "level": lv, "side": sd,
                                     "cell": list(pos), "kind": kind, "outside": True})
                seen_sides.add(sd)
                used.append(tuple(pos))
                break
            else:
                layout.warnings.append(f"{layout.names[rid]} has no outside wall to open to {target}")


# ------------------------------------------------------------ windows

def _place_windows(layout, rooms):
    """A window is an opening in a room's OUTSIDE wall, on the side asked --
    another outside side when that wall is inside the building -- spread
    along the wall, never where a doorway is."""
    for rid, r in rooms.items():
        lv = r["level"]
        room = layout.floors.get(lv, {}).get(rid)
        if not room or not r.get("windows"):
            continue
        rect = room[0]
        inside = set()
        for b, levels in layout.outlines.items():
            if lv in levels:
                inside |= levels[lv].cells()
        for rf in layout.roofs.get(lv, ()):
            inside -= rf.cells()
        doors = {tuple(d["cell"]) for d in layout.doors if d["level"] == lv and rid in (d["a"], d["b"])}
        solid = _solid(layout, lv)

        def outside_cells(side):
            dx, dy = _STEP[side]
            return [c for c in sorted(rect.cells())
                    if (c[0] + dx, c[1] + dy) not in inside and (c[0] + dx, c[1] + dy) not in rect.cells()
                    and c not in doors and c not in solid]

        for k, wdef in enumerate(r["windows"]):
            if not isinstance(wdef, dict):
                continue
            asked = str(wdef.get("side") or "")[:1]
            n = max(1, min(8, int(wdef.get("count") or 1)))
            sides = ([asked] if asked in _SIDES else []) + [s for s in _SIDES if s != asked]
            side = next((sd for sd in sides if outside_cells(sd)), None)
            if side is None:
                layout.warnings.append(f"{layout.names[rid]} has no outside wall for its window")
                continue
            if asked in _SIDES and side != asked:
                layout.warnings.append(f"{layout.names[rid]}: its window could not face {asked} "
                                       f"(that wall is inside the building) and faces {side}")
            cells = outside_cells(side)
            n = min(n, len(cells))
            for i in range(n):
                cell = cells[min(len(cells) - 1, int((i + 0.5) * len(cells) / n))]
                wid = str(wdef.get("id") or f"{rid}_window_{k + 1}") + (f"_{i + 1}" if n > 1 else "")
                layout.windows.append({"id": wid, "base": wdef.get("id"), "room": rid, "level": lv,
                                       "side": side, "cell": list(cell)})


# ------------------------------------------------------------ zones, fixtures

def _place_zones(layout, rooms):
    """A zone is an area of a room's floor: against the wall it names, or at
    the doorway it is `by` (an entry step at the entrance)."""
    for rid, r in rooms.items():
        lv = r["level"]
        cells = _room_cells(layout, rid, lv) - _solid(layout, lv)
        if not cells:
            continue
        box = _bbox(cells)
        taken = set()
        out = []
        for z in r.get("zones") or ():
            zw, zd = _zone_size(z)
            # a zone holds what stands in it: grown to its fixtures at about
            # half its floor, never below its size word
            held = sum(w * d for w, d, _h in (fixture_footprint(f) for f in r["fixtures"]
                                              if f.get("in") == z.get("id")))
            if held / 0.5 > zw * zd:
                k = math.sqrt(held / 0.5 / (zw * zd))
                zw, zd = math.ceil(zw * k), math.ceil(zd * k)
            by = str(z.get("by") or "")
            door = None
            if by:
                door = next((d for d in layout.doors if d["level"] == lv and d["a"] == rid
                             and (d["b"] == by or (by == "entrance" and d["b"] == "entrance"))), None)
            at = str(z.get("at") or "").casefold()
            best = None
            for w, d in {(zw, zd), (zd, zw)}:
                for x in range(box.x, box.x + box.w - w + 1):
                    for y in range(box.y, box.y + box.d - d + 1):
                        rc = Rect(x, y, w, d)
                        rcs = rc.cells()
                        if not rcs <= cells or rcs & taken:
                            continue
                        if door is not None:
                            if tuple(door["cell"]) not in rcs:
                                continue
                            if not _flush_room(rc, cells, door["side"]):
                                continue
                            score = abs((x + w / 2) - (door["cell"][0] + 0.5)) + abs((y + d / 2) - (door["cell"][1] + 0.5))
                        elif at in _SIDES:
                            if not _flush_room(rc, cells, at):
                                continue
                            score = 0
                        elif at.startswith("corner_"):
                            if not (_flush_room(rc, cells, at[7]) and _flush_room(rc, cells, at[8])):
                                continue
                            score = 0
                        else:
                            cx, cy = box.x + box.w / 2, box.y + box.d / 2
                            score = abs(x + w / 2 - cx) + abs(y + d / 2 - cy)
                        if best is None or score < best[0]:
                            best = (score, rc)
            if best is None:
                layout.warnings.append(f"{layout.names[rid]}: no floor for the zone {z.get('name') or z.get('id')}")
                continue
            taken |= best[1].cells()
            out.append({"id": z.get("id"), "name": z.get("name") or z.get("id"), "rect": best[1]})
        if out:
            layout.zones[rid] = out


def _grow(r, side, n):
    """`r` grown by n paces on `side`."""
    if not n:
        return r
    return {"n": Rect(r.x, r.y - n, r.w, r.d + n), "s": Rect(r.x, r.y, r.w, r.d + n),
            "w": Rect(r.x - n, r.y, r.w + n, r.d), "e": Rect(r.x, r.y, r.w + n, r.d)}[side]


def _strip_beside(r, side, n):
    """The cells of a strip n paces deep along `side` of `r`, outside it."""
    if not n:
        return set()
    return _grow(r, side, n).cells() - r.cells()


def _front_of(r, use):
    """The side of `r` its use-space lies on most -- where it is used from."""
    best, side = 0, None
    for sd in _SIDES:
        k = len(_strip_beside(r, sd, 1) & set(use))
        if k > best:
            best, side = k, sd
    return side


def _flush_room(rect, cells, side):
    """Is `rect` against the room's `side` wall (nothing of the room beyond)?"""
    dx, dy = _STEP[side]
    if side in "ns":
        row = rect.y if side == "n" else rect.y + rect.d - 1
        edge = [(x, row) for x in range(rect.x, rect.x + rect.w)]
    else:
        col = rect.x if side == "w" else rect.x + rect.w - 1
        edge = [(col, y) for y in range(rect.y, rect.y + rect.d)]
    return all((x + dx, y + dy) not in cells for x, y in edge)


def _furnish(layout, rooms):
    for rid, r in rooms.items():
        lv = r["level"]
        if not layout.floors.get(lv, {}).get(rid):
            continue
        solid = _solid(layout, lv)
        cells = _room_cells(layout, rid, lv) - solid
        # A DOORWAY'S STEP AND THE PACE INSIDE IT are the room's to walk
        # through, never a fixture's: a stove one pace in from the kitchen
        # door, cushions across the genkan's step (the owner, reading Home 9
        # on 2026-10-12: "furniture being placed in front of doors"; the
        # solve had kept only the step itself clear)
        clear = set()
        for d in layout.doors:
            if d["level"] != lv:
                continue
            x, y = d["cell"]
            dx, dy = _STEP[d["side"]]
            # a stair open to its room along the whole wall they share (a
            # `span` on a stair's door, laid as a doorway that wide) is
            # walked onto anywhere along it: its one cell stands for it and
            # keeps no pace. Every other doorway is laid at its cell, open
            # joins included, and keeps the pace inside it.
            inner = not (d.get("span") and d.get("stair"))
            if d["a"] == rid:
                clear |= {c for c in ((x, y),) + (((x - dx, y - dy),) if inner else ())
                          if c in cells}
            if d["b"] == rid:
                clear |= {c for c in ((x + dx, y + dy),) + (((x + 2 * dx, y + 2 * dy),) if inner else ())
                          if c in cells}
        zones = {z["id"]: z["rect"].cells() & cells for z in layout.zones.get(rid, ())}
        windows = {}
        for w in layout.windows:
            if w["room"] == rid:
                windows[w["id"]] = Rect(w["cell"][0], w["cell"][1], 1, 1)
                if w.get("base"):
                    windows.setdefault(w["base"], windows[w["id"]])
        _place_fixtures(rid, r, cells, layout, clear=clear, zones=zones, landmarks=windows)


def _place_fixtures(room_id, room, cells, layout, *, clear=frozenset(), zones=None, landmarks=None):
    """Fixtures by relation, backtracking. Hard: inside the room (inside its
    zone when it names one, out of every zone when it does not), no overlap,
    never on a doorway's step or a landing, against the wall it names, and
    never cutting the doorways and landings off from each other. Soft: near
    / beside / facing. A fixture no cell takes is reported."""
    if not cells:
        return
    zones = zones or {}
    reserved = set().union(*zones.values()) if zones else set()
    fixtures = sorted(room.get("fixtures") or (),
                      key=lambda f: (f.get("in") not in zones, -fixture_footprint(f)[0] * fixture_footprint(f)[1]))
    furniture = set()
    placed = dict(landmarks or {})   # a fixture may be near or facing a window
    box = _bbox(cells)
    centre = (box.x + box.w / 2, box.y + box.d / 2)

    def candidates(fx, at, into_zones=False):
        w, d, _h = fixture_footprint(fx)
        zone = zones.get(fx.get("in"))
        allowed = zone if zone else (cells if into_zones else cells - reserved)
        out = []
        for ww, dd in {(w, d), (d, w)}:
            if at in _SIDES and ((at in "ns" and ww < dd) or (at in "ew" and dd < ww)):
                continue
            for x in range(box.x, box.x + box.w - ww + 1):
                for y in range(box.y, box.y + box.d - dd + 1):
                    rc = Rect(x, y, ww, dd)
                    rcs = rc.cells()
                    if not rcs <= allowed:
                        continue
                    back = USE_SPACE.get(_kind(fx), (0, 0))[1]
                    if at in _SIDES and not _flush_room(_grow(rc, at, back), cells, at):
                        continue
                    if at.startswith("corner_") and not (_flush_room(rc, cells, at[7]) and _flush_room(rc, cells, at[8])):
                        continue
                    if at == "middle" and any(_flush_room(rc, cells, s) for s in _SIDES):
                        continue
                    out.append(rc)
        return out

    def score(fx, r):
        s = 0.0
        cx, cy = r.x + r.w / 2, r.y + r.d / 2
        for rel, want in (("near", 1.5), ("beside", 1.0), ("facing", 3.0)):
            other = fx.get(rel)
            if other in placed:
                o = placed[other]
                s -= abs(math.hypot(cx - (o.x + o.w / 2), cy - (o.y + o.d / 2)) - want)
        if str(fx.get("at") or "") == "middle":
            s -= 0.3 * math.hypot(cx - centre[0], cy - centre[1])
        # SEVERAL ALIKE STAND IN A ROW: a copy beside the one before it, in
        # line with it -- stalls along a wall, jars on a shelf's length
        base, _, n = str(fx["id"]).rpartition("_")
        if base and n.isdigit() and int(n) > 1 and f"{base}_{int(n) - 1}" in placed \
                and str(fx.get("at") or "") != "walls":
            o = placed[f"{base}_{int(n) - 1}"]
            side, _cells = _shared_wall(r, o)
            if side:
                s += 4
                if (side in "ew" and r.y == o.y) or (side in "ns" and r.x == o.x):
                    s += 2
        return s

    use_of = {}          # fixture id -> the floor it keeps clear to be used

    def table_for(fx):
        """The table a seat belongs to: the one it is near, else the one in
        its zone, else the room's only table."""
        if _kind(fx) not in _SEATS:
            return None
        tables = {f["id"]: f for f in fixtures if _kind(f) in _TABLES}
        if fx.get("near") in tables:
            return fx["near"]
        inzone = [t for t, f in tables.items() if fx.get("in") and f.get("in") == fx.get("in")]
        if inzone:
            return inzone[0]
        return next(iter(tables)) if len(tables) == 1 else None

    def use_space(fx, r):
        """The cells `fx` at `r` keeps clear, or None when its use-space would
        fall outside the room."""
        kind = _kind(fx)
        rc = r.cells()
        if kind in _TABLES:
            ring = {(x + dx, y + dy) for x, y in rc for dx, dy in _STEP.values()} - rc
            return ring & cells if len(ring & cells) >= len(ring) // 2 else None
        if kind in _BEDS:
            long_sides = ("n", "s") if r.w >= r.d else ("e", "w")
            for side in long_sides:
                strip = _strip_beside(r, side, 1)
                if strip <= cells and not (strip & furniture):
                    return strip
            return None
        front, back = USE_SPACE.get(kind, (1 if r.w * r.d > 1 else 0, 0))
        if not front and not back:
            return set()
        walls = [sd for sd in _SIDES if _flush_room(_grow(r, sd, back), cells, sd)]
        if walls:
            wall = walls[0]
            out = _strip_beside(r, _OPP[wall], front)
            if back:
                out |= _strip_beside(r, wall, back)
        else:
            # standing free: its front faces the middle of the room
            cx, cy = r.x + r.w / 2, r.y + r.d / 2
            face = (("e" if centre[0] > cx else "w") if abs(centre[0] - cx) > abs(centre[1] - cy)
                    else ("s" if centre[1] > cy else "n"))
            out = _strip_beside(r, face, front)
        return out if out <= cells else None

    def fits(r, fx=None):
        rc = r.cells()
        if rc & furniture or rc & clear:
            return False
        mine = table_for(fx) if fx is not None else None
        others = set()
        for fid, u in use_of.items():
            if fid != mine:
                others |= u
        if rc & others:
            return False
        if fx is not None:
            u = use_space(fx, r)
            if u is None or u & furniture:
                return False
            # A TABLE STANDS WHERE ITS SEATS FIT ROUND IT: its ring, less the
            # ways in and out of the room and the floor other fixtures need,
            # holds every seat that belongs to it. With the pace inside a
            # doorway kept clear, a tavern's fourth chair had gone to its
            # table's corner (2026-10-12).
            need = seats_of.get(str(fx.get("id"))) if _kind(fx) in _TABLES else 0
            if need and len(u - clear - others) < need:
                return False
        return _connected(cells - furniture - rc, clear)

    seats_of = {}
    for f in fixtures:
        t = table_for(f)
        if t is not None:
            seats_of[str(t)] = seats_of.get(str(t), 0) + 1

    budget = [3000]
    moved = []

    def go(i):
        if i == len(fixtures):
            return True
        budget[0] -= 1
        if budget[0] < 0:
            return False
        fx = fixtures[i]
        at = str(fx.get("at") or "").casefold()
        table = table_for(fx)
        if table in placed:
            # a seat stands in its table's ring -- and at one of its corners
            # when the ring is spent, as when a way in takes a side of it
            ring = use_of.get(table, set())
            cands = [Rect(x, y, 1, 1) for x, y in sorted(ring) if fits(Rect(x, y, 1, 1), fx)]
            if not cands:
                t = placed[table]
                corners = {(t.x - 1, t.y - 1), (t.x + t.w, t.y - 1),
                           (t.x - 1, t.y + t.d), (t.x + t.w, t.y + t.d)} & cells
                cands = [Rect(x, y, 1, 1) for x, y in sorted(corners) if fits(Rect(x, y, 1, 1), fx)]
        else:
            cands = [r for r in candidates(fx, at) if fits(r, fx)]
        if not cands and not zones.get(fx.get("in")):
            # nowhere outside the zones: it may stand in one -- a cushion by
            # the table in the sitting area, where its relation puts it
            cands = [r for r in candidates(fx, at, True) if fits(r, fx)]
        if not cands and at:
            for alt in [s for s in _SIDES if s != at] + [""]:
                cands = [r for r in candidates(fx, alt) if fits(r, fx)]
                if cands:
                    moved.append((fx.get("name") or fx.get("id"), at, alt or "where it fits"))
                    break
        if not cands and fx.get("size"):
            # a size word cannot make a thing larger than its room can hold:
            # at its plain size, then, where the room allows
            plain = dict(fx, size=None)
            for alt in [at] + [s for s in _SIDES if s != at] + [""]:
                cands = [r for r in candidates(plain, alt) if fits(r, plain)]
                if cands:
                    fixtures[i] = fx = plain
                    break
        cands.sort(key=lambda r: -score(fx, r))
        for r in cands[:10]:
            placed[fx["id"]] = r
            furniture.update(r.cells())
            use_of[fx["id"]] = use_space(fx, r) or set()
            if go(i + 1):
                return True
            furniture.difference_update(r.cells())
            del placed[fx["id"]]
            del use_of[fx["id"]]
        layout.unplaced.append({"room": room_id, "fixture": fx.get("name") or fx.get("id"),
                                "why": "no free place" + (f" at {fx.get('at')}" if fx.get("at") else "")})
        return go(i + 1)

    go(0)
    for name, was, now in {m[0]: m for m in moved}.values():
        layout.warnings.append(f"{layout.names.get(room_id, room_id)}: {name} could not stand at {was}; "
                               f"moved to {('the ' + now + ' wall') if now in _SIDES else now}")
    layout.fixtures[room_id] = [
        {"id": f["id"], "name": f.get("name") or f["id"], "kind": f.get("kind"), "at": f.get("at"),
         "in": f.get("in"), "rect": placed[f["id"]], "height": fixture_footprint(f)[2],
         "front": _front_of(placed[f["id"]], use_of.get(f["id"], set())),
         "use": sorted(use_of.get(f["id"], set()))}
        for f in fixtures if f["id"] in placed]


# ------------------------------------------------------------ the grounds

def _things_at_doors(layout, rooms, feats, free, place, foot=fixture_footprint):
    """THINGS AT DOORS: each feature the plan joins to a room of the building
    (`at_door`, the bridge's) stands across that room's door onto it -- a
    door of its own (`_place_doors`), the cell outside it one of its cells --
    clear of every other door's step and ground. Where the plan also joins it to a way (`reach`), the
    door may move along its room's outside walls, or turn to another wall
    no fixture, window or other doorway holds, so the thing stands within
    `REACH_MAX` paces of the way, its own ground laid over the gap (Home 9's
    well, from the kitchen's back door to the path). A turned wall is a
    wish the solve answered (`layout_bridge.planned_layout`'s `sides`).
    Returns the ids it placed, or found no room for."""
    done = set()
    steps = {}
    for door in layout.doors:
        if door.get("outside") and door["side"] in _STEP:
            sx, sy = _STEP[door["side"]]
            steps[id(door)] = (door["cell"][0] + sx, door["cell"][1] + sy)
    house = set()
    for _block, levels in layout.outlines.items():
        if 0 in levels:
            house |= levels[0].cells()
    for f in feats:
        at = f.get("at_door") if isinstance(f.get("at_door"), dict) else None
        if not at:
            continue
        done.add(f["id"])
        door = next((x for x in layout.doors if x.get("outside") and x["a"] == at.get("room")
                     and x["b"] == f["id"]), None)
        floor = (layout.floors.get((rooms.get(at.get("room")) or {}).get("level", 0)) or {}) \
            .get(at.get("room"))
        if door is None or not floor or door["side"] not in _STEP:
            layout.warnings.append(f"{layout.names[f['id']]}: no door of {at.get('room')} opens onto it")
            continue
        room = floor[0]
        w, d, _h = foot(f)
        reach = [layout.ways[k]["cells"] for k in (f.get("reach") or ())
                 if k in layout.ways and layout.ways[k].get("cells")]
        held = set()
        for fx in layout.fixtures.get(at["room"]) or ():
            held |= fx["rect"].cells()
        lit = {tuple(wn["cell"]) for wn in layout.windows if wn["room"] == at["room"]}
        # each other doorway of the room by the cell on THIS room's side of it
        # (a doorway the neighbour wrote stands in the neighbour's cell)
        others = set()
        for x in layout.doors:
            if x is door or at["room"] not in (x["a"], x["b"]) or x["side"] not in _STEP:
                continue
            if x["a"] == at["room"]:
                others.add(tuple(x["cell"]))
            else:
                ox, oy = _STEP[x["side"]]
                others.add((x["cell"][0] + ox, x["cell"][1] + oy))
        other_steps = {s for k, s in steps.items() if k != id(door)}
        floor_left = set(room.cells()) - held

        def gap(cells):
            if not reach:
                return 0
            return min(min(abs(a - c) + abs(b - e) for a, b in cells for c, e in way) - 1
                       for way in reach)

        def run(rect):
            """The straight run of the thing's own ground from its nearest
            cell toward the way's nearest -- what bridges the gap."""
            (x0, y0), goal = min(((a, b) for a in rect.cells() for way in reach for b in way),
                                 key=lambda q: (abs(q[0][0] - q[1][0]) + abs(q[0][1] - q[1][1]), q))
            cells = []
            while abs(x0 - goal[0]) + abs(y0 - goal[1]) > 1:
                if x0 != goal[0]:
                    x0 += 1 if goal[0] > x0 else -1
                else:
                    y0 += 1 if goal[1] > y0 else -1
                cells.append((x0, y0))
            return cells

        def search(sides):
            best = None
            for side in sides:
                turned = side != door["side"]
                sx, sy = _STEP[side]
                for c in sorted(room.cells()):
                    if (c[0] + sx, c[1] + sy) in house:
                        continue            # no outside wall there
                    mine = side == door["side"] and tuple(c) == tuple(door["cell"])
                    if not mine and (c in held or (c[0] - sx, c[1] - sy) in held
                                     or c in lit or c in others
                                     or not _connected(floor_left, [c] + sorted(others))):
                        # a door moved never opens into a pocket the room's
                        # furniture walls off from its other doorways
                        continue
                    t = (c[0] + sx, c[1] + sy)
                    for ww, dd in sorted({(w, d), (d, w)}):
                        for x in range(t[0] - ww + 1, t[0] + 1):
                            for y in range(t[1] - dd + 1, t[1] + 1):
                                rect = Rect(x, y, ww, dd)
                                cells = rect.cells()
                                if not free(rect, door) or cells & other_steps:
                                    continue
                                if f.get("round") and (t[0] - x, t[1] - y) not in _round_cells(ww, dd):
                                    # A ROUND THING'S STEP IS A CELL ITS CIRCLE
                                    # HOLDS: a corner of its box is no part of
                                    # it as the world reads it, and a door
                                    # onto one opened onto nothing (a review
                                    # of 2026-10-14)
                                    continue
                                g = gap(cells)
                                if 0 < g <= REACH_MAX and not all(
                                        free(Rect(a, b, 1, 1), door) for a, b in run(rect)):
                                    g += REACH_MAX      # a run through the house bridges nothing
                                along = abs(x + ww / 2 - (t[0] + 0.5)) if side in "ns" \
                                    else abs(y + dd / 2 - (t[1] + 0.5))
                                score = (g > REACH_MAX, g, turned, 0 if mine else 1, along)
                                if best is None or score < best[0]:
                                    best = (score, rect, c, side, g)
            return best

        best = search([door["side"]] + [s for s in _SIDES if s != door["side"]]
                      if reach else [door["side"]])
        if best is None:
            # NOTHING FITS AT THE DOOR ON ITS WALL: the door turns to another
            # wall of its room, as a door for reach does -- with its own door
            # beside another on one wall, a large round thing found no place
            # its step was its own (a review of 2026-10-14)
            best = search([s for s in _SIDES if s != door["side"]])
        if best is None:
            layout.warnings.append(f"{layout.names[f['id']]} found no room at the door of "
                                   f"{layout.names.get(at['room'], at['room'])}")
            continue
        _score, rect, c, side, g = best
        if (side, tuple(c)) != (door["side"], tuple(door["cell"])):
            door["cell"], door["side"] = list(c), side
            steps[id(door)] = (c[0] + _STEP[side][0], c[1] + _STEP[side][1])
        place(f, rect)
        if reach and 0 < g <= REACH_MAX:
            # its own ground over the gap: a straight run of it from its
            # nearest cell toward the way's
            for a, b in run(rect):
                cell = Rect(a, b, 1, 1)
                if free(cell, door):
                    place(dict(f), cell)
    return done


def _parts(cells):
    """How many pieces `cells` falls into, side by side."""
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


def _doors_onto_their_ground(layout, rooms, open_cells, around=None):
    """A DOOR ONTO OPEN GROUND OPENS ONTO IT. A room whose wall facing its
    ground is another room's -- a stair hall along the whole back of the
    house -- had its door turned to a wall that faces some other ground, or
    none: the hall's door onto the yard behind it opened beside the house
    onto ground no area held, and the floor dropped the yard (a review of
    2026-10-14). Where the step is ground no area holds, that ground beside
    the house is the area's, reaching it round the corner; where it is
    another area's, the door moves to a wall cell of its room whose step is
    its own ground -- no fixture's, window's or other doorway's, joined to
    the room's other doorways through its floor -- nearest where it stood.
    And where no wall of its room faces its ground and the step is the ground
    round the house (`around`), the strip of that ground beside the house on
    the door's side is its ground, reaching its band round the corner --
    where the ground round the house stays one floor without it (a garden
    behind a hall whose back wall is a stair hall was dropped, the hall's
    door onto it opening into the court; a review of 2026-10-14)."""
    held_by = {}
    for aid, cells in layout.areas.items():
        for c in cells:
            held_by[c] = aid
    house = set()
    for _block, levels in layout.outlines.items():
        if 0 in levels:
            house |= levels[0].cells()
    for door in layout.doors:
        aid = door.get("b")
        if not door.get("outside") or aid not in layout.areas or door["side"] not in _STEP \
                or door.get("level", 0) != 0:
            continue
        sx, sy = _STEP[door["side"]]
        t = (door["cell"][0] + sx, door["cell"][1] + sy)
        if held_by.get(t) == aid:
            continue
        if t not in held_by and t in open_cells:
            # the ground beside the house no area holds, as far as it runs
            part, stack = set(), [t]
            while stack:
                c = stack.pop()
                if c in part or c not in open_cells or c in held_by:
                    continue
                part.add(c)
                stack.extend((c[0] + dx, c[1] + dy) for dx, dy in _STEP.values())
            if any((c[0] + dx, c[1] + dy) in layout.areas[aid] for c in part
                   for dx, dy in _STEP.values()):
                layout.areas[aid] |= part
                for c in part:
                    held_by[c] = aid
                continue
        room_id = door["a"]
        floor = (layout.floors.get(0) or {}).get(room_id)
        if not floor:
            continue
        room = floor[0]
        held = set()
        for fx in layout.fixtures.get(room_id) or ():
            held |= fx["rect"].cells()
        lit = {tuple(wn["cell"]) for wn in layout.windows if wn["room"] == room_id}
        others = set()
        for x in layout.doors:
            if x is door or room_id not in (x["a"], x["b"]) or x["side"] not in _STEP:
                continue
            if x["a"] == room_id:
                others.add(tuple(x["cell"]))
            else:
                ox, oy = _STEP[x["side"]]
                others.add((x["cell"][0] + ox, x["cell"][1] + oy))
        steps = set()
        for x in layout.doors:
            if x is not door and x.get("outside") and x["side"] in _STEP:
                steps.add((x["cell"][0] + _STEP[x["side"]][0], x["cell"][1] + _STEP[x["side"]][1]))
        floor_left = set(room.cells()) - held
        outside_doors = {tuple(x["cell"]) for x in layout.doors
                         if x is not door and x.get("outside") and x["a"] == room_id}
        best = None
        for side in _SIDES:
            dx, dy = _STEP[side]
            for c in sorted(room.cells()):
                step = (c[0] + dx, c[1] + dy)
                if held_by.get(step) != aid or step in house or step in steps:
                    continue
                if c in held or (c[0] - dx, c[1] - dy) in held or c in lit or c in others \
                        or not _connected(floor_left, [c] + sorted(others)):
                    continue
                # never beside the room's other outside doors where a cell
                # further off will do: moved a pace from a thing's own door,
                # its step fell in this door's ground (a review of 2026-10-14)
                near = any(abs(c[0] - u[0]) + abs(c[1] - u[1]) < THING_DOOR_GAP
                           for u in outside_doors)
                score = (near, side != door["side"],
                         abs(c[0] - door["cell"][0]) + abs(c[1] - door["cell"][1]))
                if best is None or score < best[0]:
                    best = (score, c, side)
        if best is not None:
            _score, c, side = best
            if side != door["side"]:
                layout.warnings.append(f"{layout.names.get(room_id, room_id)} opens to "
                                       f"{layout.names.get(aid, aid)} on its {side} side, "
                                       f"the side its ground lies")
            door["cell"], door["side"] = list(c), side
            continue
        block = (layout.outlines.get((rooms.get(room_id) or {}).get("block")) or {}).get(0)
        if around and held_by.get(t) == around and around in layout.areas and block is not None:
            hb = block          # beside the door's own building, never an outbuilding's
            side = door["side"]

            def beside(c):
                if side in ("w", "e"):
                    out = c[0] < hb.x if side == "w" else c[0] >= hb.x + hb.w
                    return out and hb.y <= c[1] < hb.y + hb.d
                out = c[1] < hb.y if side == "n" else c[1] >= hb.y + hb.d
                return out and hb.x <= c[0] < hb.x + hb.w

            strip, stack = set(), [t]
            while stack:
                c = stack.pop()
                if c in strip or held_by.get(c) != around or not beside(c):
                    continue
                strip.add(c)
                stack.extend((c[0] + dx, c[1] + dy) for dx, dy in _STEP.values())
            rest = layout.areas[around] - strip
            if strip and rest and _parts(rest) <= _parts(layout.areas[around]) and any(
                    (c[0] + dx, c[1] + dy) in layout.areas[aid] for c in strip
                    for dx, dy in _STEP.values()):
                layout.areas[around] = rest
                layout.areas[aid] |= strip
                for c in strip:
                    held_by[c] = aid


def _grounds(layout, rooms, grounds):
    """The building stands in a plot. The approach runs from the entrance
    out of the front; features stand in the open by their relation; areas
    of ground take the side they are asked for, and the one the building
    stands `around` takes the rest."""
    house = set()
    for b, levels in layout.outlines.items():
        if 0 in levels:
            house |= levels[0].cells()
    if not house:
        return
    hb = _bbox(house)
    front = layout.front
    # THE NARROWEST A PLACE IS LAID: the world reads no place narrower than
    # two paces, and asks for every thing and walk and branch way at least
    # that wide (`narrowest`, the bridge's) -- a thing laid a pace deep was
    # widened on writing onto the ground the solver kept at a door, and the
    # thing was dropped (a review of 2026-10-14); the lab lays them as it
    # always has
    narrowest = max(1, int(grounds.get("narrowest") or 1))
    wide = narrowest >= 2

    def foot(f):
        w, d, h = fixture_footprint(f)
        return max(w, narrowest), max(d, narrowest), h

    margin = {s: SIDE_MARGIN for s in _SIDES}
    margin[front] = FRONT_REACH + 2
    for f in grounds.get("features") or ():
        if isinstance(f, dict) and str(f.get("side") or "")[:1] in _SIDES:
            w, d, _h = foot(f)
            sd = str(f["side"])[:1]
            margin[sd] = max(margin[sd], max(w, d) + 4)
        at = f.get("at_door") if isinstance(f, dict) and isinstance(f.get("at_door"), dict) else None
        if at:
            # room on the door's side for the thing that stands at it, and
            # two paces past it -- and on every outside wall of its room,
            # which its door may turn to (`_things_at_doors`): turned to a
            # wall the plot reached five paces past, a round yew six across
            # found no room (a review of 2026-10-14)
            dr = next((x for x in layout.doors if x.get("outside") and x["a"] == at.get("room")
                       and x["b"] == f.get("id")), None)
            if dr is not None:
                w, d, _h = foot(f)
                walls = {dr["side"]}
                fl = (layout.floors.get((rooms.get(at.get("room")) or {}).get("level", 0)) or {}) \
                    .get(at.get("room"))
                if fl:
                    walls |= {sd for sd in _SIDES if any(
                        (c[0] + _STEP[sd][0], c[1] + _STEP[sd][1]) not in house for c in fl[0].cells())}
                for sd in walls:
                    margin[sd] = max(margin[sd], max(w, d) + 2)
    site = Rect(hb.x - margin["w"], hb.y - margin["n"], hb.w + margin["w"] + margin["e"],
                hb.d + margin["n"] + margin["s"])
    layout.site = site
    plot = site.cells()
    open_ground = plot - house
    taken = set()

    # WAYS: the approach from the entrance door out of the front, three wide
    door = next((d for d in layout.doors if d.get("b") == "entrance"), None)
    ways = [w for w in grounds.get("ways") or () if isinstance(w, dict) and w.get("id")]
    for w in ways:
        layout.names[w["id"]] = w.get("name") or w["id"]
    feats = [f for f in grounds.get("features") or () if isinstance(f, dict) and f.get("id")]
    for f in feats:
        layout.names[f["id"]] = f.get("name") or f["id"]
    area_ids = {str(a.get("id")) for a in grounds.get("areas") or () if isinstance(a, dict)}
    def out_of(dr, clear=frozenset()):
        """A way three wide straight out of a door, to the plot's edge."""
        side = dr["side"]
        dx, dy = _STEP[side]
        x, y = dr["cell"]
        out = (x + dx, y + dy)
        if side in "ns":
            row = [(out[0] + k, out[1]) for k in (-1, 0, 1)]
        else:
            row = [(out[0], out[1] + k) for k in (-1, 0, 1)]
        cells, rows = set(), []
        while True:
            row = [c for c in row if c in open_ground and c not in clear]
            if not row:
                break
            cells.update(row)
            rows.append(row)
            row = [(a + dx, b + dy) for a, b in row]
        return {"cells": cells, "side": side, "rows": rows}

    from_doors = []
    for w in ways:
        joined_by = [d for d in layout.doors if d.get("outside") and d["b"] == w["id"]]
        # a way with no start is no approach: one the plan joins only to
        # open ground leaves it (below, once the ground is laid)
        start = str(w.get("from") or "")
        if start == "entrance" and joined_by and any(v.get("rows") for v in layout.ways.values()):
            # the entrance has its approach already; a way rooms open onto
            # runs between their doors
            start = ""
        if start == "entrance" and door is not None:
            layout.ways[w["id"]] = out_of(door)
            taken |= layout.ways[w["id"]]["cells"]
        elif start == "door" and len(joined_by) == 1 and joined_by[0]["side"] in _STEP:
            from_doors.append((w, joined_by[0]))
        elif start in layout.ways or joined_by or start in area_ids:
            pass   # a branch, a way between doors, or one leaving open ground: laid below
        else:
            layout.warnings.append(f"{layout.names[w['id']]} has nothing to run from")
    # A WAY ONE DOOR OPENS ONTO, AND NO OTHER (`from: door`, the bridge's):
    # out of that door as the approach runs out of the entrance's, after it
    # and clear of it
    for w, dr in from_doors:
        laid = out_of(dr, clear=taken | house)
        if not laid["rows"]:
            layout.warnings.append(f"{layout.names[w['id']]} has no ground to run out of its door")
            continue
        layout.ways[w["id"]] = laid
        taken |= laid["cells"]

    # AREAS: open ground. One on a named side takes the plot beyond the
    # building on that side; the one it stands `around` takes the rest.
    areas = [a for a in grounds.get("areas") or () if isinstance(a, dict) and a.get("id")]
    for a in areas:
        layout.names[a["id"]] = a.get("name") or a["id"]
    rest = set(open_ground)
    around = next((a for a in areas if str(a.get("where") or "") == "around"), None)
    # A BAND IS MEASURED FROM THE BUILDING THE ENTRANCE IS IN: an outbuilding
    # standing apart on that side stands in it, never past it (Home 10's
    # storehouse, at the court's west end)
    entrance_block = layout.blocks.get((layout.entrance or {}).get("room"))
    mb = (layout.outlines.get(entrance_block) or {}).get(0) or hb
    for a in areas:
        sd = str(a.get("where") or "")[:1]
        if a is around or sd not in _SIDES:
            continue
        band = {c for c in rest if (sd == "n" and c[1] < mb.y) or (sd == "s" and c[1] >= mb.y + mb.d)
                or (sd == "w" and c[0] < mb.x) or (sd == "e" and c[0] >= mb.x + mb.w)}
        layout.areas[a["id"]] = band
        rest -= band
    if around is None and areas:
        around = next((a for a in areas if a["id"] not in layout.areas), None)
    if around is not None:
        layout.areas[around["id"]] = rest
    _doors_onto_their_ground(layout, rooms, open_ground - taken,
                             around=around["id"] if around is not None else None)

    # A WAY THAT LEAVES OPEN GROUND -- one the plan joins to open ground and
    # not to the house -- runs on from that ground's far edge on its side,
    # WAY_BEYOND paces past the plot, never through the ground it leaves, in
    # line with the entrance where the entrance opens onto that ground (Home
    # 10's path, south of its court in line with the great doors)
    mouths = set()
    for w in ways:
        area = str(w.get("from") or "")
        if area not in layout.areas or w["id"] in layout.ways or not layout.areas[area]:
            continue
        cells_a = layout.areas[area]
        asked = str(w.get("side") or "")[:1]
        if asked not in _SIDES:
            # unsaid, it leaves on the side its ground lies, the front only
            # for ground round the building (a review of 2026-10-14: a band
            # behind the house was left toward the front, through the house)
            asked = str(next((a.get("where") for a in areas if a["id"] == area), "") or "")[:1]
        if asked not in _SIDES:
            asked = front
        # NEVER OVER A BUILDING, ANOTHER WAY OR ANOTHER GROUND: from the place
        # on its ground's far edge nearest the one asked whose rows run clear,
        # on the side asked where one does, else on another side of its ground
        # -- run straight on, a lane went through a storehouse standing in the
        # band beyond its ground, and one through the court beyond the garden
        # it left (two reviews of 2026-10-14)
        elsewhere = set().union(*(c for a, c in layout.areas.items() if a != area)) \
            if len(layout.areas) > 1 else set()
        chosen = None
        for side in [asked] + [x for x in _SIDES if x not in (asked, _OPP[asked])] + [_OPP[asked]]:
            dx, dy = _STEP[side]
            key = {"s": lambda c: c[1], "n": lambda c: -c[1], "e": lambda c: c[0],
                   "w": lambda c: -c[0]}[side]
            far = max(key(c) for c in cells_a)
            edge = sorted(c for c in cells_a if key(c) == far)
            along = 0 if side in "ns" else 1
            mid = None
            if door is not None and side == asked:
                t = (door["cell"][0] + _STEP[door["side"]][0], door["cell"][1] + _STEP[door["side"]][1])
                # in line with an entrance whose step is this ground -- never
                # one whose step is a way across it, which the lane then ran on
                # from (a review of 2026-10-14)
                if t in cells_a and t not in taken:
                    mid = t[along]
            if mid is None:
                mid = edge[len(edge) // 2][along]
            for m in [mid] + sorted({c[along] for c in edge} - {mid}, key=lambda v: (abs(v - mid), v)):
                span = [c for c in edge if abs(c[along] - m) <= WAY_WIDTH // 2]
                if len(span) < 2:
                    continue
                rows = [[(c[0] + dx * k, c[1] + dy * k) for c in span]
                        for k in range(1, WAY_BEYOND + 1)]
                cells = {c for row in rows for c in row}
                if not cells & (house | taken | elsewhere):
                    chosen = (side, span, rows, cells)
                    break
            if chosen:
                break
        if chosen is None:
            layout.warnings.append(f"{layout.names[w['id']]} has no edge of "
                                   f"{layout.names[area]} to leave from clear of the buildings")
            continue
        side, span, rows, cells = chosen
        dx, dy = _STEP[side]
        if side != asked:
            layout.warnings.append(f"{layout.names[w['id']]} leaves {layout.names[area]} on its "
                                   f"{side} side, not the {asked} asked")
        layout.ways[w["id"]] = {"cells": cells, "side": side, "rows": rows}
        taken |= cells
        # ITS MOUTH -- the edge it leaves from and the pace inside it -- is
        # no thing's: a lantern by the way stood on it, the ground and the
        # way no longer touched, and the way was dropped (a review of
        # 2026-10-14)
        mouths |= set(span) | {(c[0] - dx, c[1] - dy) for c in span}
        # and ground round it, for what stands across it, by it or at its
        # end: laid before every thing, so what the answers relate to it has
        # it to stand by (a review of 2026-10-14: laid last, a gate across
        # its end and a lantern by it stood with nothing to stand by, and
        # the floor dropped them)
        beside = {(c[0] + i, c[1] + j) for c in cells
                  for i in range(-LEAVING_GROUND, LEAVING_GROUND + 1)
                  for j in range(-LEAVING_GROUND, LEAVING_GROUND + 1)} - house
        open_ground |= beside
        xs = [c[0] for c in beside] + [layout.site.x, layout.site.x + layout.site.w - 1]
        ys = [c[1] for c in beside] + [layout.site.y, layout.site.y + layout.site.d - 1]
        layout.site = Rect(min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1)

    # THE GROUND AT A DOOR: the threshold of every door onto open ground,
    # and the cells that keep it in a two-pace block of that ground (the
    # world reads no part narrower), are no thing's -- save the thing that
    # stands at that very door (a review of 2026-10-14: a lantern below the
    # entrance's threshold left it a sliver no block held, and the court
    # lost its doorway, and with it every place reached through it)
    # -- every door whose step is open ground, the entrance's among them; a
    # step on a way is the way's
    area_cells = set().union(*layout.areas.values()) if layout.areas else set()
    way_cells = set().union(*(w["cells"] for w in layout.ways.values())) if layout.ways else set()

    def aprons(but=None, keep=()):
        """The ground kept at the doors -- every door's but `but` and those in
        `keep` (ids) -- and at the mouths of the ways that leave the ground."""
        out = set(mouths)
        for dr in layout.doors:
            if dr is but or id(dr) in keep or not dr.get("outside") or dr["side"] not in _STEP:
                continue
            sx, sy = _STEP[dr["side"]]
            t = (dr["cell"][0] + sx, dr["cell"][1] + sy)
            if dr["b"] not in layout.areas and (t not in area_cells or t in way_cells):
                continue
            lx, ly = (1, 0) if dr["side"] in "ns" else (0, 1)
            out |= {(t[0] + sx * k + lx * m, t[1] + sy * k + ly * m)
                    for k in (0, 1) for m in (-1, 0, 1)}
        return out

    # FEATURES: objects in the open, by plain relations
    def free(rc, door=None):
        rcs = rc.cells()
        return rcs <= open_ground and not (rcs & taken) and not (rcs & aprons(door))

    def place(f, rect):
        layout.features.append({"id": f["id"], "name": f.get("name") or f["id"], "kind": f.get("kind"),
                                "rect": rect, "height": fixture_footprint(f)[2]})
        taken.update(rect.cells())

    at_door = _things_at_doors(layout, rooms, feats, free, place, foot=foot)

    for f in feats:
        if f["id"] in at_door:
            continue
        w, d, _h = foot(f)
        count = max(1, int(f.get("count") or 1))
        end = str(f.get("end") or "far")
        way = next((layout.ways[k] for k in (f.get("across"), f.get("flank"), f.get("along"))
                    if k in layout.ways), None)
        if f.get("across") and way:
            rows = way["rows"]
            row = rows[-1] if end == "far" else rows[0]
            side = way["side"]
            # across the way: spans it, one pace thick, its posts outside it
            if side in "ns":
                xs = [c[0] for c in row]
                rect = Rect(min(xs) - 1, row[0][1], max(xs) - min(xs) + 3, 1)
            else:
                ys = [c[1] for c in row]
                rect = Rect(row[0][0], min(ys) - 1, 1, max(ys) - min(ys) + 3)
            rcs = rect.cells()
            if rcs <= open_ground:
                place(f, rect)
                # the gate stands across the way: the way runs under it
            else:
                layout.warnings.append(f"{layout.names[f['id']]} has no room across {layout.names[f['across']]}")
            continue
        if f.get("flank") and way:
            rows = way["rows"]
            k = min(len(rows) - 1, 2)
            row = rows[-1 - k] if end == "far" else rows[k]
            side = way["side"]
            spots = []
            if side in "ns":
                xs = [c[0] for c in row]
                spots = [Rect(min(xs) - w, row[0][1], w, d), Rect(max(xs) + 1, row[0][1], w, d)]
            else:
                ys = [c[1] for c in row]
                spots = [Rect(row[0][0], min(ys) - d, w, d), Rect(row[0][0], max(ys) + 1, w, d)]
            for i, rect in enumerate(spots[:max(2, count)]):
                if free(rect):
                    place(dict(f, id=f"{f['id']}_{i + 1}"), rect)
                else:
                    layout.warnings.append(f"{layout.names[f['id']]}: no room beside the way")
            continue
        if f.get("along") and way:
            rows = way["rows"]
            n = max(2, count)
            side = way["side"]
            for i in range(n):
                k = 1 + round(i * (len(rows) - 3) / max(1, n - 1))
                k = min(len(rows) - 1, max(0, k))
                row = rows[k]
                if side in "ns":
                    xs = [c[0] for c in row]
                    rect = Rect(min(xs) - w if i % 2 == 0 else max(xs) + 1, row[0][1], w, d)
                else:
                    ys = [c[1] for c in row]
                    rect = Rect(row[0][0], min(ys) - d if i % 2 == 0 else max(ys) + 1, w, d)
                if free(rect):
                    place(dict(f, id=f"{f['id']}_{i + 1}"), rect)
            continue
        # WHERE A WAY LEADS: the thing it leads `to`. A thing `by` a way is
        # beside it, on the side the answer gives (below) -- read as the way's
        # far end, Home 11's well stood across the path's foot with its side
        # dropped
        led_to = next((wid for wid, w in ((x["id"], x) for x in ways)
                       if w.get("to") == f["id"] and wid in layout.ways and layout.ways[wid].get("rows")), None)
        if led_to is not None:
            # where a way leads: just past its far end, across its line
            way = layout.ways[led_to]
            row, side = way["rows"][-1], way["side"]
            dx, dy = _STEP[side]
            spot = None
            given = []
            for back in range(0, len(way["rows"])):
                row = way["rows"][-1 - back]
                cx = sum(c[0] for c in row) / len(row)
                cy = sum(c[1] for c in row) / len(row)
                for ww, dd in {(w, d), (d, w)}:
                    x0 = round(cx - ww / 2 + 0.5) if side in "ns" else (row[0][0] + dx if dx > 0 else row[0][0] - ww)
                    y0 = round(cy - dd / 2 + 0.5) if side in "ew" else (row[0][1] + dy if dy > 0 else row[0][1] - dd)
                    rect = Rect(x0, y0, ww, dd)
                    if free(rect):
                        spot = rect
                        break
                if spot:
                    break
                # the plot ends there: the way gives up its last row to it
                layout.ways[led_to]["cells"] -= set(row)
                taken.difference_update(row)
                given.append(row)
            # ...and its rows with it: left in `rows`, a thing laid across the
            # way's far end stood on a row that was no longer the way (Home
            # 11's torii, off the path's line and half outside the plot)
            way["rows"] = [r for r in way["rows"] if not any(r is g for g in given)]
            if spot is None:
                layout.warnings.append(f"{layout.names[f['id']]} found no room at the end of {layout.names[led_to]}")
            else:
                place(f, spot)
            continue
        target = str(f.get("by") or "")
        anchor = None
        if target == "entrance" and door is not None:
            anchor = {(door["cell"][0] + _STEP[door["side"]][0], door["cell"][1] + _STEP[door["side"]][1])}
        elif target in rooms and layout.floors.get(rooms[target]["level"], {}).get(target):
            anchor = layout.floors[rooms[target]["level"]][target][0].cells()
        elif target in layout.ways:
            anchor = layout.ways[target]["cells"]
            rows = layout.ways[target].get("rows") or []
            end = str(f.get("end") or "")
            if end in ("far", "near") and rows:
                # by the way at one end of it: those rows are where it stands
                ends = rows[-3:] if end == "far" else rows[:3]
                anchor = {c for row in ends for c in row} or anchor
        elif any(x["id"] == target for x in layout.features):
            anchor = next(x["rect"] for x in layout.features if x["id"] == target).cells()
        side = str(f.get("side") or "")[:1]
        # BY OPEN GROUND: in it, placed as a thing by nothing is -- as far
        # from everything as that ground allows; anywhere, where no room in
        # it is free (a lantern joined to a garden alone stood where no garden
        # was; a review of 2026-10-14). A thing the plan joins to open ground
        # alone stands IN it (`in`, the bridge's), by whatever it stands by,
        # on the side asked where that ground lies there and anywhere in it
        # where it does not
        inside = layout.areas.get(str(f.get("in") or "")) or (
            layout.areas.get(target) if anchor is None and target in layout.areas else None)
        tries = [(inside, side)] + ([(inside, "")] if inside and side in _SIDES else []) + \
            ([(None, side)] if inside else [])
        best = None
        # a thing by something may stand on the ground a way leaving the plot
        # opened round it (`LEAVING_GROUND`); one by nothing keeps to the plot
        scan = layout.site if anchor is not None else site
        run = str((layout.ways.get(target) or {}).get("side") or "")[:1]

        def beside(sd):
            """Whether standing on side `sd` of the anchor means beside it,
            within its length: across a way's line (along it is past an
            end), by a room or a thing -- never by a doorstep, which stands
            against the wall"""
            if target in layout.ways:
                return run in _SIDES and sd not in (run, _OPP[run])
            return target != "entrance"
        for ww, dd, within, side in [(ww, dd, within, sd) for within, sd in tries
                                     for ww, dd in {(w, d), (d, w)}]:
            if best is not None and (within, side) != best[2]:
                break
            for x in range(scan.x, scan.x + scan.w - ww + 1):
                for y in range(scan.y, scan.y + scan.d - dd + 1):
                    rect = Rect(x, y, ww, dd)
                    if not free(rect) or (within is not None and not rect.cells() <= within):
                        continue
                    # keep a pace of open ground round it from the walls
                    halo = {(a + dx, b + dy) for a, b in rect.cells() for dx, dy in _STEP.values()}
                    if halo & house:
                        continue
                    cx, cy = x + ww / 2, y + dd / 2
                    if anchor is not None:
                        sc = min(abs(cx - a - 0.5) + abs(cy - b - 0.5) for a, b in anchor)
                        if side in _SIDES:
                            # BY SOMETHING, ON A SIDE OF IT -- a well by the
                            # entryway east of the path: ground on the other
                            # side is taken only where that side has none --
                            # and BESIDE IT where it can, never past its end:
                            # a lantern by a lane's far end, east of it, stood
                            # beyond the lane half a pace east of its line,
                            # and the gate across that end was dropped (a
                            # review of 2026-10-14)
                            ax = sum(a for a, _ in anchor) / len(anchor) + 0.5
                            ay = sum(b for _, b in anchor) / len(anchor) + 0.5
                            ahead = {"e": cx - ax, "w": ax - cx, "s": cy - ay, "n": ay - cy}[side]
                            along = [b for _, b in anchor] if side in "ew" else [a for a, _ in anchor]
                            lo, hi = (y, y + dd) if side in "ew" else (x, x + ww)
                            if ahead <= 0:
                                sc += site.w + site.d
                            if beside(side) and not (lo <= max(along) and hi > min(along)):
                                sc += site.w + site.d
                    elif side in _SIDES:
                        # on that side of the building, centred on it
                        if side == "n" and y + dd > hb.y:
                            continue
                        if side == "s" and y < hb.y + hb.d:
                            continue
                        if side == "w" and x + ww > hb.x:
                            continue
                        if side == "e" and x < hb.x + hb.w:
                            continue
                        mid = (hb.x + hb.w / 2, hb.y + hb.d / 2)
                        sc = (abs(cx - mid[0]) if side in "ns" else abs(cy - mid[1])) + \
                            0.5 * (abs(cy - mid[1]) if side in "ns" else abs(cx - mid[0]))
                    else:
                        sc = -min((abs(cx - t[0]) + abs(cy - t[1]) for t in taken | house), default=0)
                    if best is None or sc < best[0]:
                        best = (sc, rect, (within, side))
        if best is None:
            layout.warnings.append(f"{layout.names[f['id']]} found no open ground")
            continue
        place(f, best[1])

    # A WAY BETWEEN DOORS -- one the rooms opening onto it define, with no
    # start of its own: the shortest walk through open ground from the first
    # such door to the others (a roofed walkway from a back door to an
    # outbuilding's door)
    # WALKS AND BRANCH WAYS are laid two paces wide where the world asks
    # (`narrowest`); the lab draws them a pace wide, as it always has
    def walk_between(src, goals, keep_off=frozenset()):
        things = {c for f in layout.features for c in f["rect"].cells()}
        # two paces wide where it fits, clear of the other ways first, and
        # of the ground at every other door's step (a review of 2026-10-14:
        # two wide, a walk past the entrance left its step a one-pace sliver
        # no place held, and the court lost its doorway)
        for walk in ((open_ground - taken - keep_off, open_ground - things - keep_off)
                     if wide else ()):
            starts = [(s[0] - i, s[1] - j) for s in src for i in (0, 1) for j in (0, 1)]
            cells = _wide_route(walk, starts, lambda o: bool(_block(o) & goals))
            if cells:
                return cells
        walk = open_ground - things
        prev = {c: None for c in src}
        frontier, hit = list(src), None
        while frontier and hit is None:
            nxt = []
            for c in frontier:
                if c in goals:
                    hit = c
                    break
                for dx, dy in _STEP.values():
                    n = (c[0] + dx, c[1] + dy)
                    if n in walk and n not in prev:
                        prev[n] = c
                        nxt.append(n)
            frontier = nxt
        cells = set()
        while hit is not None:
            cells.add(hit)
            hit = prev[hit]
        return cells

    for w in ways:
        if w["id"] in layout.ways or (w.get("from") and w.get("from") != "entrance"):
            continue
        outs = []
        for d in layout.doors:
            if d.get("outside") and d["b"] == w["id"]:
                dx, dy = _STEP[d["side"]]
                outs.append((d["cell"][0] + dx, d["cell"][1] + dy))
        outs = [c for c in outs if c in open_ground]
        if len(outs) >= 2:
            cells = set()
            own = {id(d) for d in layout.doors if d.get("outside") and d["b"] == w["id"]}
            for goal in outs[1:]:
                cells |= walk_between({outs[0]}, {goal}, keep_off=aprons(keep=own))
            layout.ways[w["id"]] = {"cells": cells, "side": None, "rows": []}
            taken.update(cells)
        elif outs:
            layout.warnings.append(f"{layout.names[w['id']]}: only one door opens onto it")

    # branch ways: the shortest walk from the way they leave to their target
    for w in ways:
        start = str(w.get("from") or "")
        if start not in layout.ways or w["id"] in layout.ways:
            continue
        goal = next((x["rect"] for x in layout.features if x["id"] == w.get("to")), None)
        if goal is None:
            layout.warnings.append(f"{layout.names[w['id']]} leads nowhere the grounds hold")
            continue
        goal_cells = {(a + dx, b + dy) for a, b in goal.cells() for dx, dy in _STEP.values()} - goal.cells()
        src = layout.ways[start]["cells"]
        walk = open_ground - {c for f in layout.features for c in f["rect"].cells()}
        # two paces wide where it fits, clear of the other ways first, off
        # the way it leaves -- and none where the thing stands beside that
        # way already, as a pace-wide one lays none
        ring = {(a + dx, b + dy) for a, b in src for dx, dy in _STEP.values()} - src
        starts = [(c[0] - i, c[1] - j) for c in ring for i in (0, 1) for j in (0, 1)]
        cells = set()
        for room_for in ((walk - taken, walk - src) if wide and not src & goal_cells else ()):
            cells = _wide_route(room_for, starts, lambda o: bool(_block(o) & goal_cells))
            if cells:
                break
        if cells:
            layout.ways[w["id"]] = {"cells": cells, "side": None, "rows": []}
            taken.update(cells)
            continue
        prev = {c: None for c in src}
        frontier, hit = list(src), None
        while frontier and hit is None:
            nxt = []
            for c in frontier:
                if c in goal_cells:
                    hit = c
                    break
                for dx, dy in _STEP.values():
                    n = (c[0] + dx, c[1] + dy)
                    if n in walk and n not in prev:
                        prev[n] = c
                        nxt.append(n)
            frontier = nxt
        cells = set()
        while hit is not None and hit not in src:
            cells.add(hit)
            hit = prev[hit]
        layout.ways[w["id"]] = {"cells": cells, "side": None, "rows": []}


# ------------------------------------------------------------ checks

def check(layout: Layout):
    """The invariants the design promises, as a list of breaches (empty when
    the layout keeps them). Tests and the lab both read this."""
    out = []
    for b, levels in layout.outlines.items():
        for lv, o in levels.items():
            ids = [rid for rid, blk in layout.blocks.items() if blk == b and rid in layout.floors.get(lv, {})]
            covered = set()
            for rid in ids:
                rects = layout.floors[lv][rid]
                if len(rects) != 1:
                    out.append(f"{rid} is not one rectangle")
                cs = rects[0].cells()
                if cs & covered:
                    out.append(f"{rid} overlaps another room on storey {lv}")
                covered |= cs
                if not cs <= o.cells():
                    out.append(f"{rid} stands outside its block's outline on storey {lv}")
            for v in list(layout.voids.get(lv, ())) + list(layout.roofs.get(lv, ())):
                if v.cells() <= o.cells():
                    covered |= v.cells()
            if ids and covered != o.cells():
                out.append(f"block {b} storey {lv}: rooms leave {len(o.cells() - covered)} cells of the outline empty")
    for s in layout.stairwells:
        rect = Rect(**s["rect"])
        for lv in s["levels"]:
            hall = layout.floors.get(lv, {}).get(s["halls"][str(lv)])
            if not hall or not hall[0].contains(rect):
                out.append(f"{s['id']}: its stair is not inside its hall on storey {lv}")
    return out
