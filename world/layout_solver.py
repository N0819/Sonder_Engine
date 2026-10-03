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
     sized from its largest storey; every storey of the block divides that
     same outline, a storey under the roof an inset of it. Ragged outlines
     cannot occur.
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
     something (a well by the entryway), on a side of the building (a tree
     behind it) -- never a fenced room. An outbuilding is a block of its
     own, standing apart.

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
                 "ways": [{"id", "name", "from": "entrance" | way_id, "to"?: feature_id}],
                 "features": [{"id", "name", "kind", "size"?, "count"?,
                               "across"?: way_id, "flank"?: way_id, "along"?: way_id,
                               "end"?: "far|near", "by"?: id | "entrance",
                               "side"?: "n|e|s|w"}]},
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
#: A stairwell by kind of stair (run x width, paces).
WELLS = {"straight": (3, 2), "spiral": (2, 2), "ladder": (1, 1)}
#: Width of a way across the grounds, how far the approach runs before the
#: plot's edge, and the open ground left on the other sides of the building.
WAY_WIDTH = 3
FRONT_REACH = 10
SIDE_MARGIN = 5
#: A storey above or below the ground that needs less than PART_SHARE of its
#: block's outline (its need taken at PART_SLACK, room to move) covers only
#: part of the building.
PART_SHARE = 0.7
PART_SLACK = 1.25
#: Search sizes: divisions tried per storey, and layouts kept across storeys.
TREES = 1200
KEEP = 6
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

def fixture_footprint(fx):
    kind = str(fx.get("kind") or "").strip().casefold().replace(" ", "_")
    if kind in FIXTURE_SIZES:
        return FIXTURE_SIZES[kind]
    word = str(fx.get("size") or "medium").casefold()
    return SIZE_WORD_FOOTPRINT.get(word, SIZE_WORD_FOOTPRINT["medium"])


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


def room_target(room, stair_cells=0):
    """Square paces a room needs: its furniture at COVERAGE of the floor, its
    zones' floor, its stairwells, a step inside each door; never under its
    purpose's floor."""
    key = purpose_key(room)
    lo, _hi = PURPOSE_AREA[key]
    furniture = sum(w * d for w, d, _h in (fixture_footprint(f) for f in room.get("fixtures") or ()))
    zones = sum(a * b for a, b in (_zone_size(z) for z in room.get("zones") or ()))
    doors = len(room.get("joins") or ())
    if key in CORRIDORS:
        return max(lo, 2 * max(4, 2.5 * doors) + stair_cells)
    hint = {"tiny": 0.7, "small": 0.85, "large": 1.25, "huge": 1.5}.get(
        str(room.get("size") or "").casefold(), 1.0)
    return max(lo, hint * (furniture / COVERAGE + 0.6 * zones + 1.5 * doors) + stair_cells)


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
    shapes: tuple


def _read(spec, layout):
    """Rooms by id (each with its level and block), the stairs, the blocks."""
    rooms = {}
    for r in spec.get("rooms") or ():
        if isinstance(r, dict) and r.get("id"):
            r = dict(r)
            fx = []
            for f in r.get("fixtures") or ():
                if not isinstance(f, dict) or not f.get("id"):
                    continue
                n = max(1, min(24, int(f.get("count") or 1)))
                # several alike are that many things, each standing somewhere
                fx += [f] if n == 1 else [dict(f, id=f"{f['id']}_{i + 1}", count=1) for i in range(n)]
            r["fixtures"] = fx
            r["level"] = int(r.get("level") or 0)
            r["block"] = str(r.get("block") or "main")
            rooms[r["id"]] = r
    for r in rooms.values():
        layout.names[r["id"]] = r.get("name") or r["id"]
        layout.purposes[r["id"]] = purpose_key(r)
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
        kind = str(st.get("kind") or "").casefold()
        shapes = (WELLS[kind],) if kind in WELLS else (WELLS["straight"], WELLS["spiral"])
        stairs.append(_Stair(str(st.get("id") or f"{a}-{b}"), str(st.get("name") or "stair"),
                             low, high, bool(st.get("enclosed")), str(st.get("door") or "door"),
                             at, shapes))
    return rooms, stairs


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


def _place_blocks(spec, rooms, stairs, front, layout):
    """{block: {level: outline Rect}}: each block sized from its largest
    storey, placed beside (or apart from) the block it names."""
    blocks = {}
    for r in rooms.values():
        blocks.setdefault(r["block"], set()).add(r["level"])
    smaller = {int(s.get("level") or 0) for s in spec.get("storeys") or ()
               if isinstance(s, dict) and s.get("smaller")}
    declared = {str(b.get("id")): b for b in spec.get("blocks") or () if isinstance(b, dict) and b.get("id")}
    stair_cells = _stair_cells(rooms, stairs)
    dims = {}
    for b, levels in blocks.items():
        need = {}
        for r in rooms.values():
            if r["block"] == b:
                need[r["level"]] = need.get(r["level"], 0) + room_target(r, stair_cells.get(r["id"], 0))
        full = [n * (1.25 if lv in smaller and lv > 0 else 1.0) for lv, n in need.items()]
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
            # a block attached on the front or back keeps the building's front line
            placed[b] = r
            pending.remove(b)
    out = {}
    for b, levels in blocks.items():
        base = placed[b]
        out[b] = {}
        need = {}
        for r in rooms.values():
            if r["block"] == b:
                need[r["level"]] = need.get(r["level"], 0) + room_target(r, stair_cells.get(r["id"], 0))
        # a storey carries the storeys above it: it covers at least what they need
        carried = dict(need)
        for lv in sorted((lv for lv in levels if lv > 0), reverse=True):
            carried[lv] = max(need.get(lv, 0), carried.get(lv + 1, 0))
        for lv in sorted(levels, key=lambda v: (v < 0, abs(v))):
            o = base
            if lv != 0 and carried.get(lv, 0) * PART_SLACK < PART_SHARE * base.w * base.d:
                # A STOREY THAT HOLDS LESS COVERS PART OF THE BUILDING -- an
                # upper floor over part of the house, the rest of it roof; a
                # cellar under part of it. Full depth, centred along the front.
                if front in "ns":
                    w = max(3, min(base.w, math.ceil(carried[lv] * PART_SLACK / base.d)))
                    o = Rect(base.x + (base.w - w) // 2, base.y, w, base.d)
                else:
                    d = max(3, min(base.d, math.ceil(carried[lv] * PART_SLACK / base.w)))
                    o = Rect(base.x, base.y + (base.d - d) // 2, base.w, d)
                base_lv = o
            else:
                base_lv = base
            o = base_lv
            if lv in smaller and lv > 0 and min(o.w, o.d) >= 6:
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


def _stair_cells(rooms, stairs):
    """Floor each room gives its stairwells: the well and its landing."""
    out = {}
    for st in stairs:
        run, wide = st.shapes[0]
        for rid in (st.low, st.high):
            out[rid] = out.get(rid, 0) + run * (wide + 1)
    return out


# ------------------------------------------------------------ dividing a storey

def _slice(rect, items, out, rng):
    """Guillotine: split `rect` among `items` [(id, weight)] in order, the
    list halved near its weight midpoint and the rectangle cut to match."""
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
    near = [k for k, sh in shares if 0.3 <= sh <= 0.7] or [min(shares, key=lambda t: abs(t[1] - 0.5))[0]]
    k = rng.choice(near)
    share = dict(shares)[k]
    # cut across the long side more often than not, but not always: a hall
    # across the whole front with the service rooms behind it is a cut the
    # other way
    across = rng.random() < (0.7 if rect.w >= rect.d else 0.3)
    # the cut wanders a pace either side of where the weights put it, so a
    # small room against a long wall can be offered two paces deep, not one
    jitter = rng.choice((-1, 0, 0, 1))
    if across and rect.w >= 2:
        cut = _cut(rect.w, share, jitter)
        _slice(Rect(rect.x, rect.y, cut, rect.d), items[:k], out, rng)
        _slice(Rect(rect.x + cut, rect.y, rect.w - cut, rect.d), items[k:], out, rng)
    elif rect.d >= 2:
        cut = _cut(rect.d, share, jitter)
        _slice(Rect(rect.x, rect.y, rect.w, cut), items[:k], out, rng)
        _slice(Rect(rect.x, rect.y + cut, rect.w, rect.d - cut), items[k:], out, rng)
    else:
        out[items[0][0]] = rect


def _cut(length, share, jitter):
    """Where to cut a side of `length`: at the weights' share, wandered by
    `jitter`, and never leaving a piece thinner than three paces when the
    side can afford two such pieces -- a room is not a sliver."""
    cut = round(length * share) + jitter
    if length >= 6:
        cut = max(3, min(length - 3, cut))
    return max(1, min(length - 1, cut))


def _mirror(rect, frame, fx, fy):
    x = frame.x + frame.w - (rect.x - frame.x) - rect.w if fx else rect.x
    y = frame.y + frame.d - (rect.y - frame.y) - rect.d if fy else rect.y
    return Rect(x, y, rect.w, rect.d)


def _bfs_order(ids, rooms, start, rng):
    seen, order, queue = set(), [], [start]
    while queue or len(order) < len(ids):
        if not queue:
            queue = [next(i for i in ids if i not in seen)]
        rid = queue.pop(0)
        if rid in seen:
            continue
        seen.add(rid)
        order.append(rid)
        nxt = [o for o in _joins(rid, rooms) if o in ids and o not in seen]
        rng.shuffle(nxt)
        queue.extend(nxt)
    return order


def _spine(outline, ids, rooms, weights, rng):
    """A corridor down the outline's long axis, rooms in bands either side of
    it and across its ends, each band divided along its length in the order
    the corridor's joins give."""
    hubs = [i for i in ids if purpose_key(rooms[i]) in CORRIDORS]
    if not hubs:
        return None
    hub = max(hubs, key=lambda i: len(_joins(i, rooms)))
    horiz = outline.w >= outline.d
    if rng.random() < 0.15:
        horiz = not horiz
    band_sides = ("n", "s") if horiz else ("w", "e")
    end_sides = ("w", "e") if horiz else ("n", "s")
    js = _joins(hub, rooms)
    bands = {s: [] for s in band_sides + end_sides}
    unplaced = []
    for rid in ids:
        if rid == hub:
            continue
        if rid in js and js[rid][0] in bands:
            bands[js[rid][0]].append(rid)
        else:
            unplaced.append(rid)
    for rid in unplaced:
        # beside the band room it joins, else the lighter band
        home = next((s for s in band_sides for o in bands[s] if o in _joins(rid, rooms)), None)
        if home is None:
            home = min(band_sides, key=lambda s: sum(weights[o] for o in bands[s]))
        bands[home].append(rid)
    for s in bands:
        bands[s].sort(key=lambda o: (js.get(o, (None, None, None))[1] or 99, rng.random()))
    width = 2 if min(outline.w, outline.d) < 10 else rng.choice((2, 3))
    out = {}
    # ends first: full-depth slabs across the corridor's ends
    inner = outline
    for s in end_sides:
        if not bands[s]:
            continue
        wsum = sum(weights[o] for o in bands[s])
        depth = outline.d if horiz else outline.w
        length = max(3, round(wsum / max(1, depth)))
        if s == "w":
            slab, inner = Rect(inner.x, inner.y, length, inner.d), Rect(inner.x + length, inner.y, inner.w - length, inner.d)
        elif s == "e":
            slab, inner = Rect(inner.x + inner.w - length, inner.y, length, inner.d), Rect(inner.x, inner.y, inner.w - length, inner.d)
        elif s == "n":
            slab, inner = Rect(inner.x, inner.y, inner.w, length), Rect(inner.x, inner.y + length, inner.w, inner.d - length)
        else:
            slab, inner = Rect(inner.x, inner.y + inner.d - length, inner.w, length), Rect(inner.x, inner.y, inner.w, inner.d - length)
        _slice_band(slab, bands[s], weights, out, along_x=not horiz)
    if inner.w < 2 or inner.d < 2:
        return None
    a, b = band_sides
    wa = sum(weights[o] for o in bands[a])
    wb = sum(weights[o] for o in bands[b])
    across = inner.d if horiz else inner.w
    if not bands[a] and not bands[b]:
        out[hub] = inner
        return out
    room_depth = across - width
    if not bands[a]:
        da, db = 0, room_depth
    elif not bands[b]:
        da, db = room_depth, 0
    else:
        da = max(2, min(room_depth - 2, round(room_depth * wa / max(1e-9, wa + wb))))
        db = room_depth - da
    if horiz:
        ra = Rect(inner.x, inner.y, inner.w, da)
        hall = Rect(inner.x, inner.y + da, inner.w, width)
        rb = Rect(inner.x, inner.y + da + width, inner.w, db)
    else:
        ra = Rect(inner.x, inner.y, da, inner.d)
        hall = Rect(inner.x + da, inner.y, width, inner.d)
        rb = Rect(inner.x + da + width, inner.y, db, inner.d)
    out[hub] = hall
    if bands[a]:
        _slice_band(ra, bands[a], weights, out, along_x=horiz)
    if bands[b]:
        _slice_band(rb, bands[b], weights, out, along_x=horiz)
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


def _divisions(outline, ids, rooms, weights, rng):
    """Candidate divisions of one storey's outline among its rooms."""
    seen = set()
    for t in range(TREES):
        if t % 4 == 0:
            parts = _spine(outline, ids, rooms, weights, rng)
            if parts is None:
                parts = {}
        else:
            parts = {}
        if not parts:
            order = _bfs_order(ids, rooms, rng.choice(ids), rng)
            _slice(outline, [(i, weights[i]) for i in order], parts, rng)
            fx, fy = rng.random() < 0.5, rng.random() < 0.5
            parts = {i: _mirror(r, outline, fx, fy) for i, r in parts.items()}
        key = tuple(sorted((i, r.x, r.y, r.w, r.d) for i, r in parts.items()))
        if key in seen:
            continue
        seen.add(key)
        yield parts


# ------------------------------------------------------------ stairs in rooms

def _landing(well, side):
    """The row of floor in front of a well standing against `side`."""
    if side == "n":
        return Rect(well.x, well.y + well.d, well.w, 1)
    if side == "s":
        return Rect(well.x, well.y - 1, well.w, 1)
    if side == "w":
        return Rect(well.x + well.w, well.y, 1, well.d)
    return Rect(well.x - 1, well.y, 1, well.d)


def _stair_spots(room, at, taken, shapes):
    """(well, landing, side) places in `room` against `at` (else any wall),
    the landing in front of the well, touching nothing in `taken`; the wall
    asked first, then nearest the middle of the wall."""
    out = []
    for side in list(_SIDES):
        along = room.w if side in "ns" else room.d
        across = room.d if side in "ns" else room.w
        for si, shape in enumerate(shapes):
            for run, wide in (shape, shape[::-1]):
                if run > along or wide + 1 > across:
                    continue
                w, d = (run, wide) if side in "ns" else (wide, run)
                for k in range(along - run + 1):
                    if side == "n":
                        well = Rect(room.x + k, room.y, w, d)
                    elif side == "s":
                        well = Rect(room.x + k, room.y + room.d - d, w, d)
                    elif side == "w":
                        well = Rect(room.x, room.y + k, w, d)
                    else:
                        well = Rect(room.x + room.w - w, room.y + k, w, d)
                    land = _landing(well, side)
                    if any(well.overlaps(t) or land.overlaps(t) for t in taken):
                        continue
                    out.append(((0 if side == at or at is None else 1), si,
                                abs(k - (along - run) / 2), well, land, side))
    out.sort(key=lambda t: t[:3])
    return [(w, l, s) for _a, _s, _k, w, l, s in out]


def _pinned_fit(room, well, at):
    """How a well cut through another storey sits in `room` here: (penalty,
    landing, side). It must lie inside the room with floor before it;
    against the wall asked is best, against another wall next, and standing
    free in the room -- a stair rising in the middle of a hall -- last."""
    if not room.contains(well):
        return 200, None, None
    best = (100, None, None)
    for side in _SIDES:
        land = _landing(well, side)
        if not room.contains(land):
            continue
        if room.flush(well, side):
            pen = 0 if (at is None or side == at) else 6
        else:
            pen = 10
        if pen < best[0]:
            best = (pen, land, side)
    return best


# ------------------------------------------------------------ scoring

def _score(parts, ids, rooms, weights, outline, fixed, ctx, rank=0):
    """Lower is better. Returns (score, {stair id: (well, landing, side)}).
    `rank` picks which of a free stair's places along its wall to take, so
    the storeys solved after this one get a choice."""
    s = 0.0
    for rid in ids:
        if rid not in parts:
            s += 300
    stairs_here = {}
    taken = []
    # stairs pinned from a storey already built
    for st, rid, well in ctx["pinned"]:
        r = parts.get(rid)
        if r is None:
            continue
        same = next((v for v in stairs_here.values() if v[0] == well), None)
        if same is not None:          # two flights of one shaft, cut on two other storeys
            stairs_here[st.id] = same
            continue
        pen, land, side = _pinned_fit(r, well, st.at.get(rid))
        s += pen
        if land is not None:
            stairs_here[st.id] = (well, land, side)
            taken += [well, land]
    # stairs first cut on this storey
    for st, rid, within in ctx["free"]:
        r = parts.get(rid)
        if r is None:
            continue
        # A STAIR THAT CLIMBS ON takes the shaft it arrived by -- a tower's
        # spiral, flights stacked in a stair hall -- where the shapes agree
        # and no other wall was asked
        # -- a flight of the same kind (open over open, enclosed over
        # enclosed) that leaves this room the other way vertically
        by_id = {x.id: x for x in ctx["stairs"]}
        shaft = next(((w, l, sd) for sid, (w, l, sd) in stairs_here.items()
                      if r.contains(w) and (w.w, w.d) in [o for sh in st.shapes for o in (sh, sh[::-1])]
                      and (st.at.get(rid) in (None, sd))
                      and by_id[sid].enclosed == st.enclosed
                      and (by_id[sid].high == rid) == (st.low == rid)
                      and sum(1 for v in stairs_here.values() if v[0] == w) == 1), None)
        if shaft is not None and within.contains(shaft[0]):
            stairs_here[st.id] = shaft
            continue
        # the well must stand inside the other storey's outline too
        spots = [sp for sp in _stair_spots(r, st.at.get(rid), taken, st.shapes) if within.contains(sp[0])]
        if not spots:
            s += 80
            continue
        best_wall = [sp for sp in spots if sp[2] == spots[0][2]]
        well, land, side = best_wall[min(rank * max(1, len(best_wall) // 3), len(best_wall) - 1)]
        if st.at.get(rid) and side != st.at[rid]:
            s += 6
        stairs_here[st.id] = (well, land, side)
        taken += [well, land]
    avoid = set()
    for well, _land, _side in stairs_here.values():
        avoid |= well.cells()
    for st in ctx["enclosed"]:
        if st.id in stairs_here:
            well, land, _side = stairs_here[st.id]
            avoid |= land.cells()
    every = dict(fixed)
    every.update(parts)
    for rid in ids:
        r = parts.get(rid)
        if r is None:
            continue
        key = purpose_key(rooms[rid])
        lo_side, hi_side = sorted((r.w, r.d))
        if lo_side < 2:
            s += 80
        elif lo_side < 3 and key not in CORRIDORS and key not in ("closet", "toilet", "latrine"):
            s += 12
        longest = max((max(w, d) for w, d, _h in (fixture_footprint(f) for f in rooms[rid].get("fixtures") or ())),
                      default=1)
        if hi_side < longest:
            s += 20
        if key not in CORRIDORS and hi_side / lo_side > 2.5:
            s += (hi_side / lo_side - 2.5) * 8
        if key in CORRIDORS and lo_side > 3:
            # a corridor is a way through, not a room
            s += (lo_side - 3) * 10
        s += 3 * abs(math.log((r.w * r.d) / max(1.0, weights[rid])))
        for other, (side, _o, _k) in _joins(rid, rooms).items():
            if other not in every or (other in parts and other < rid):
                continue
            got, cells = _door_cells(r, every[other], avoid)
            if not cells:
                s += 60
            elif side and side != got:
                s += 20
        # a room that opens outdoors must have that wall on the outside
        want = ctx["outward"].get(rid)
        if want is not None:
            sides = [want] if want in _SIDES else list(_SIDES)
            if not any(_on_edge(r, outline, sd) for sd in sides):
                s += ctx["outward_weight"].get(rid, 15)
    return s, stairs_here


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
    outlines = _place_blocks(spec, rooms, stairs, front, layout)
    layout.outlines = outlines
    grounds = spec.get("grounds") or {}
    outdoor_ids = {str(x.get("id")) for key in ("areas", "ways") for x in grounds.get(key) or ()
                   if isinstance(x, dict)}

    # rooms that open outdoors, and on which side: the entrance on the front
    outward, outward_weight = {}, {}
    for rid, r in rooms.items():
        for j in r.get("joins") or ():
            if j.get("to") in outdoor_ids:
                sd = str(j.get("side") or "")[:1]
                outward[rid] = sd if sd in _SIDES else outward.get(rid, "any")
    if entrance:
        outward[entrance["room"]] = front
        outward_weight[entrance["room"]] = 40
    stair_cells = _stair_cells(rooms, stairs)

    # THE ORDER STOREYS ARE SOLVED IN: the one whose stair rooms are
    # tightest first -- a corridor decides where its stairs can stand, and
    # the roomy hall at the other end takes them wherever they land. A storey
    # of one room can take a stair anywhere, so it never decides: it goes
    # last. Ties go ground first, then up, then down.
    order = []
    for b in outlines:
        for lv in outlines[b]:
            here = [rid for rid, r in rooms.items() if r["block"] == b and r["level"] == lv]
            tight = min((room_target(rooms[rid], stair_cells.get(rid, 0)) for st in stairs
                         for rid in (st.low, st.high) if rid in here), default=1e9)
            order.append((len(here) <= 1, tight, abs(lv) + (0.5 if lv < 0 else 0), b, lv))
    order = [(b, lv) for _one, _t, _r, b, lv in sorted(order)]

    def weights_for(ids, outline):
        t = {i: room_target(rooms[i], stair_cells.get(i, 0)) for i in ids}
        spare = outline.w * outline.d - sum(t.values())
        flex = [i for i in ids if purpose_key(rooms[i]) in FLEXIBLE] or list(ids)
        tf = sum(t[i] for i in flex) or 1.0
        if spare > 0:
            for i in flex:
                t[i] += spare * t[i] / tf
        return t

    candidates = {}
    for b, lv in order:
        ids = [rid for rid, r in rooms.items() if r["block"] == b and r["level"] == lv]
        outline = outlines[b][lv]
        weights = weights_for(ids, outline)
        candidates[(b, lv)] = (ids, outline, weights, list(_divisions(outline, ids, rooms, weights, rng)))

    # BEAM ACROSS STOREYS: keep the layouts whose stairs line up
    states = [(0.0, {}, {})]   # (score, {(b, lv): parts}, {stair id: well})
    stairs_by_room = {}
    for st in stairs:
        stairs_by_room.setdefault(st.low, []).append(st)
        stairs_by_room.setdefault(st.high, []).append(st)
    for b, lv in order:
        ids, outline, weights, divs = candidates[(b, lv)]
        grown = []
        for score, done, wells in states:
            fixed = {}
            for (b2, lv2), parts in done.items():
                if lv2 == lv:
                    fixed.update(parts)
            ctx = {"pinned": [], "free": [], "enclosed": [s for s in stairs if s.enclosed], "stairs": stairs,
                   "outward": outward if lv == 0 else {}, "outward_weight": outward_weight}
            for rid in ids:
                for st in stairs_by_room.get(rid, ()):
                    if st.id in wells:
                        ctx["pinned"].append((st, rid, wells[st.id]))
                    else:
                        other = st.high if rid == st.low else st.low
                        ctx["free"].append((st, rid, outlines[rooms[other]["block"]][rooms[other]["level"]]))
            scored = []
            for parts in divs:
                for rank in ((0, 1, 2) if ctx["free"] else (0,)):
                    sc, here = _score(parts, ids, rooms, weights, outline, fixed, ctx, rank)
                    scored.append((sc + 0.5 * rank, parts, here))
            scored.sort(key=lambda t: t[0])
            for sc, parts, here in scored[:KEEP]:
                nd = dict(done)
                nd[(b, lv)] = parts
                nw = dict(wells)
                for sid, (well, _land, _side) in here.items():
                    nw.setdefault(sid, well)
                grown.append((score + sc, nd, nw, here, lv))
        grown.sort(key=lambda t: t[0])
        states = [(sc, nd, nw) for sc, nd, nw, _h, _lv in grown[:KEEP]]
    best_score, done, wells = states[0]

    for (b, lv), parts in done.items():
        layout.floors.setdefault(lv, {}).update({rid: [r] for rid, r in parts.items()})
    for (b, lv) in order:
        for rid in candidates[(b, lv)][0]:
            if rid not in done[(b, lv)]:
                layout.warnings.append(f"{layout.names[rid]} found no floor on storey {lv}")

    _finish_stairs(layout, rooms, stairs, wells)
    approaches = {str(w.get("id")) for w in grounds.get("ways") or ()
                  if isinstance(w, dict) and str(w.get("from") or "entrance") == "entrance"}
    _place_doors(layout, rooms, stairs, outdoor_ids, approaches)
    _place_zones(layout, rooms)
    _furnish(layout, rooms)
    _grounds(layout, rooms, grounds)
    return layout


# ------------------------------------------------------------ stairs, doors

def _finish_stairs(layout, rooms, stairs, wells):
    for st in stairs:
        if st.id not in wells:
            layout.warnings.append(f"{st.name} found no place in "
                                   f"{layout.names[st.low]} or {layout.names[st.high]}")
            continue
        well = wells[st.id]
        landings, sides = {}, {}
        for rid in (st.low, st.high):
            lv = rooms[rid]["level"]
            room = layout.floors.get(lv, {}).get(rid)
            if not room:
                continue
            shared = next((x for x in layout.stairwells if x["rect"] == well.as_dict()
                           and str(lv) in x["landings"]), None)
            if shared is not None:
                landings[str(lv)] = shared["landings"][str(lv)]
                sides[str(lv)] = shared["sides"][str(lv)]
                continue
            pen, land, side = _pinned_fit(room[0], well, st.at.get(rid))
            if land is None:
                layout.warnings.append(f"{st.name} has no floor before it in {layout.names[rid]}")
                continue
            if pen >= 10:
                layout.warnings.append(f"{st.name} stands free in {layout.names[rid]}, "
                                       f"not against its {st.at.get(rid) or 'any'} wall")
            elif pen:
                layout.warnings.append(f"{st.name} stands at the {side} wall of {layout.names[rid]}, "
                                       f"not the {st.at.get(rid)} wall asked")
            landings[str(lv)] = land.as_dict()
            sides[str(lv)] = side
        if len(landings) < 2:
            continue
        shaft = None
        if st.enclosed:
            # an enclosed stair is its well walled off from the room, a door
            # in the wall that faces its landing; the landing is the room's
            # own floor, the place a body stands to open that door
            shaft = {lv: well.as_dict() for lv in landings}
        layout.stairwells.append({
            "id": st.id, "name": st.name, "low": st.low, "high": st.high,
            "levels": [rooms[st.low]["level"], rooms[st.high]["level"]],
            "rect": well.as_dict(), "landings": landings, "sides": sides,
            "enclosed": st.enclosed, "door": st.door, "shaft": shaft})


def _solid(layout, lv):
    """Cells on storey `lv` no doorway may open from and no fixture may take:
    every well, and the whole of every enclosed stairwell."""
    out = set()
    for s in layout.stairwells:
        if lv in s["levels"]:
            out |= Rect(**s["rect"]).cells()
            if s["shaft"] and str(lv) in s["shaft"]:
                out |= Rect(**s["shaft"][str(lv)]).cells()
    return out


def _room_cells(layout, rid, lv):
    cells = set()
    for r in layout.floors.get(lv, {}).get(rid, ()):
        cells |= r.cells()
    return cells


def _place_doors(layout, rooms, stairs, outdoor_ids, approaches=frozenset()):
    """One doorway per join between rooms, spread along a shared wall in
    declared order; a doorway onto every enclosed stairwell; the entrance
    and every other outside door on the outside wall asked."""
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
    for (lv, rid, side), items in per_wall.items():
        items.sort(key=lambda t: t[0])
        n = len(items)
        for k, (_o, other, cells, kind) in enumerate(items):
            pos = cells[min(len(cells) - 1, int((k + 1) * len(cells) / (n + 1)))]
            layout.doors.append({"a": rid, "b": other, "level": lv, "side": side,
                                 "cell": list(pos), "kind": kind})
    # enclosed stairwells: a doorway in the well's wall facing its landing
    for s in layout.stairwells:
        if not s["shaft"]:
            continue
        well = Rect(**s["rect"])
        for rid in (s["low"], s["high"]):
            lv = rooms[rid]["level"]
            side = s["sides"][str(lv)]          # the room wall the well stands against
            face = _OPP[side]                   # the well's wall that looks at the landing
            dx, dy = _STEP[face]
            land = Rect(**s["landings"][str(lv)]).cells()
            cells = [c for c in sorted(well.cells()) if (c[0] + dx, c[1] + dy) in land]
            if not cells:
                layout.warnings.append(f"{s['name']} has no wall facing its landing in {layout.names[rid]}")
                continue
            pos = cells[len(cells) // 2]
            layout.doors.append({"a": s["id"], "b": rid, "level": lv, "side": face,
                                 "cell": list(pos), "kind": s["door"], "stair": True})
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
        seen_sides = set()
        for target, side, kind in items:
            for sd in ([side] if side else []) + [x for x in _SIDES if x != side]:
                dx, dy = _STEP[sd]
                cells = [c for c in sorted(r.cells()) if (c[0] + dx, c[1] + dy) not in house
                         and (c[0] + dx, c[1] + dy) not in r.cells()]
                cells = [c for c in cells if c not in _solid(layout, lv)]
                if sd in seen_sides or not cells:
                    continue
                pos = cells[len(cells) // 2]
                if side and sd != side:
                    layout.warnings.append(f"{layout.names[rid]} opens to {target} on its {sd} side, "
                                           f"not the {side} asked")
                layout.doors.append({"a": rid, "b": target, "level": lv, "side": sd,
                                     "cell": list(pos), "kind": kind, "outside": True})
                seen_sides.add(sd)
                break
            else:
                layout.warnings.append(f"{layout.names[rid]} has no outside wall to open to {target}")


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
        clear = set()
        for d in layout.doors:
            if d["level"] != lv:
                continue
            x, y = d["cell"]
            dx, dy = _STEP[d["side"]]
            if d["a"] == rid:
                clear |= {c for c in ((x, y),) if c in cells}
            if d["b"] == rid:
                clear |= {c for c in ((x + dx, y + dy),) if c in cells}
        for s in layout.stairwells:
            land = s["landings"].get(str(lv))
            if land:
                clear |= Rect(**land).cells() & cells
        zones = {z["id"]: z["rect"].cells() & cells for z in layout.zones.get(rid, ())}
        _place_fixtures(rid, r, cells, layout, clear=clear, zones=zones)


def _place_fixtures(room_id, room, cells, layout, *, clear=frozenset(), zones=None):
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
    placed = {}
    box = _bbox(cells)
    centre = (box.x + box.w / 2, box.y + box.d / 2)

    def candidates(fx, at):
        w, d, _h = fixture_footprint(fx)
        zone = zones.get(fx.get("in"))
        allowed = zone if zone else cells - reserved
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
                    if at in _SIDES and not _flush_room(rc, cells, at):
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
        return s

    def fits(r):
        rc = r.cells()
        return not (rc & furniture) and not (rc & clear) and _connected(cells - furniture - rc, clear)

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
        cands = [r for r in candidates(fx, at) if fits(r)]
        if not cands and at:
            for alt in [s for s in _SIDES if s != at] + [""]:
                cands = [r for r in candidates(fx, alt) if fits(r)]
                if cands:
                    moved.append((fx.get("name") or fx.get("id"), at, alt or "where it fits"))
                    break
        cands.sort(key=lambda r: -score(fx, r))
        for r in cands[:10]:
            placed[fx["id"]] = r
            furniture.update(r.cells())
            if go(i + 1):
                return True
            furniture.difference_update(r.cells())
            del placed[fx["id"]]
        layout.unplaced.append({"room": room_id, "fixture": fx.get("name") or fx.get("id"),
                                "why": "no free place" + (f" at {fx.get('at')}" if fx.get("at") else "")})
        return go(i + 1)

    go(0)
    for name, was, now in {m[0]: m for m in moved}.values():
        layout.warnings.append(f"{layout.names.get(room_id, room_id)}: {name} could not stand at {was}; "
                               f"moved to {('the ' + now + ' wall') if now in _SIDES else now}")
    layout.fixtures[room_id] = [
        {"id": f["id"], "name": f.get("name") or f["id"], "kind": f.get("kind"), "at": f.get("at"),
         "in": f.get("in"), "rect": placed[f["id"]], "height": fixture_footprint(f)[2]}
        for f in fixtures if f["id"] in placed]


# ------------------------------------------------------------ the grounds

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
    margin = {s: SIDE_MARGIN for s in _SIDES}
    margin[front] = FRONT_REACH + 2
    for f in grounds.get("features") or ():
        if isinstance(f, dict) and str(f.get("side") or "")[:1] in _SIDES:
            w, d, _h = fixture_footprint(f)
            sd = str(f["side"])[:1]
            margin[sd] = max(margin[sd], max(w, d) + 4)
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
    for w in ways:
        start = str(w.get("from") or "entrance")
        if start == "entrance" and door is not None:
            side = door["side"]
            dx, dy = _STEP[side]
            x, y = door["cell"]
            out = (x + dx, y + dy)
            if side in "ns":
                row = [(out[0] + k, out[1]) for k in (-1, 0, 1)]
            else:
                row = [(out[0], out[1] + k) for k in (-1, 0, 1)]
            cells, rows = set(), []
            while True:
                row = [c for c in row if c in open_ground]
                if not row:
                    break
                cells.update(row)
                rows.append(row)
                row = [(a + dx, b + dy) for a, b in row]
            layout.ways[w["id"]] = {"cells": cells, "side": side, "rows": rows}
            taken |= cells
        elif start in layout.ways:
            pass   # a branch: laid once its target stands (below)
        else:
            layout.warnings.append(f"{layout.names[w['id']]} has nothing to run from")

    # FEATURES: objects in the open, by plain relations
    def free(rc):
        rcs = rc.cells()
        return rcs <= open_ground and not (rcs & taken)

    def place(f, rect):
        layout.features.append({"id": f["id"], "name": f.get("name") or f["id"], "kind": f.get("kind"),
                                "rect": rect, "height": fixture_footprint(f)[2]})
        taken.update(rect.cells())

    for f in feats:
        w, d, _h = fixture_footprint(f)
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
        led_to = next((wid for wid, w in ((x["id"], x) for x in ways)
                       if w.get("to") == f["id"] and wid in layout.ways and layout.ways[wid].get("rows")), None)
        if led_to is None and str(f.get("by") or "") in layout.ways and layout.ways[f["by"]].get("rows"):
            led_to = f["by"]
        if led_to is not None:
            # where a way leads: just past its far end, across its line
            way = layout.ways[led_to]
            row, side = way["rows"][-1], way["side"]
            dx, dy = _STEP[side]
            spot = None
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
        elif any(x["id"] == target for x in layout.features):
            anchor = next(x["rect"] for x in layout.features if x["id"] == target).cells()
        side = str(f.get("side") or "")[:1]
        best = None
        for ww, dd in {(w, d), (d, w)}:
            for x in range(site.x, site.x + site.w - ww + 1):
                for y in range(site.y, site.y + site.d - dd + 1):
                    rect = Rect(x, y, ww, dd)
                    if not free(rect):
                        continue
                    # keep a pace of open ground round it from the walls
                    halo = {(a + dx, b + dy) for a, b in rect.cells() for dx, dy in _STEP.values()}
                    if halo & house:
                        continue
                    cx, cy = x + ww / 2, y + dd / 2
                    if anchor is not None:
                        sc = min(abs(cx - a - 0.5) + abs(cy - b - 0.5) for a, b in anchor)
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
                        best = (sc, rect)
        if best is None:
            layout.warnings.append(f"{layout.names[f['id']]} found no open ground")
            continue
        place(f, best[1])

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

    # AREAS: open ground. One on a named side takes the plot beyond the
    # building on that side; the one it stands `around` takes the rest.
    areas = [a for a in grounds.get("areas") or () if isinstance(a, dict) and a.get("id")]
    for a in areas:
        layout.names[a["id"]] = a.get("name") or a["id"]
    rest = set(open_ground)
    around = next((a for a in areas if str(a.get("where") or "") == "around"), None)
    for a in areas:
        sd = str(a.get("where") or "")[:1]
        if a is around or sd not in _SIDES:
            continue
        band = {c for c in rest if (sd == "n" and c[1] < hb.y) or (sd == "s" and c[1] >= hb.y + hb.d)
                or (sd == "w" and c[0] < hb.x) or (sd == "e" and c[0] >= hb.x + hb.w)}
        layout.areas[a["id"]] = band
        rest -= band
    if around is None and areas:
        around = next((a for a in areas if a["id"] not in layout.areas), None)
    if around is not None:
        layout.areas[around["id"]] = rest


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
            if ids and covered != o.cells():
                out.append(f"block {b} storey {lv}: rooms leave {len(o.cells() - covered)} cells of the outline empty")
    for s in layout.stairwells:
        for lv in s["levels"]:
            rid = s["low"] if lv == s["levels"][0] else s["high"]
            room = layout.floors.get(lv, {}).get(rid)
            if not room or not room[0].contains(Rect(**s["rect"])):
                out.append(f"{s['id']}: the well is not inside {rid} on storey {lv}")
    return out
