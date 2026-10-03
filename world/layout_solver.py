"""A building laid out from relations: the model says what is where, code places it.

PROTOTYPE (branch layout-solver-test, 2026-10-03). Nothing in the turn pipeline
calls this module; `tools/layout_lab` drives it and renders what it produces.

Why it exists (the owner, 2026-10-03: the room designer "is very poor about
spatial reasoning and placement", poor "at placing fixtures or guessing room
size", "stairs don't exist and stacked buildings just end up being a bunch of
rooms with no true verticality"). Measured in the owner's stories: fixtures
on the wall opposite their own description, zones minted as fixtures, size
words contradicting extents on 8 of 17 rooms, floors labelled by `level` and
never stacked over one another, stairs that are only an edge between rooms.

The split follows Holodeck (Yang et al., CVPR 2024): a language model is
good at RELATIONS and poor at coordinates -- in its ablation, constraint
placement scored 0.706 against 0.364 for model-written coordinates, no
better than random (0.369). So the model writes a spec of relations, and
this module is the solver.

SECOND DESIGN (same day). The first cut one footprint for every storey and
partitioned it; measured on three buildings it split six rooms into
disconnected pieces (the leftovers of a stair strip handed to the nearest
room), packed rooms 45-75% furniture, put a lighthouse keeper's cottage
inside its own tower, and left the shrine's stair up unreachable from the
hallway it opens into. The owner, on reading it: "it still feels...
strange". So the order is reversed -- ROOMS FIRST:

  * A room is one rectangle, sized from what it holds (furniture at about a
    third of the floor, its purpose's range a floor under that), never from
    a footprint it has to fill.
  * A storey is grown room by room, each placed against a room it joins on
    the side the spec asks, by a beam search scored on joins kept,
    compactness and size. An upper storey must STAND on the storey below
    (a cellar under the one above) and may be smaller -- a tower over its
    base, a loft under the roof.
  * A stair is a well that stands against a named wall of the room at each
    end, the same cells on both storeys, with a landing in front of it on
    each that must stay reachable from that room's doors.
  * The building stands INSIDE ITS GROUNDS (the owner: "allow outdoor rooms
    to contain buildings"): a plot around it, a path running from its door
    to the plot's edge, small outdoor places beside what they join, and the
    gardens and yards filling the rest around the walls.

THE SPEC (what the model writes; every coordinate is the solver's):

    {"name": str,
     "floors": [{"level": int, "rooms": [ROOM, ...]}, ...],
     "grounds": [ROOM + {"around"?: true}, ...],   # outdoors, around the building
     "stairs": [{"id", "from", "to", "from_at"?, "to_at"?, "side"?, "name"?}]}

    ROOM = {"id", "name", "purpose", "size"?, "over"?: room_id below,
            "joins": [{"to": room_id, "side": "n|e|s|w", "order"?: int,
                       "kind"?: "door|sliding|opening|gate"}],
            "fixtures": [{"id", "kind", "name"?, "size"?,
                          "at"?: "n|e|s|w|middle|corner_ne|corner_se|corner_sw|corner_nw",
                          "near"?: fixture_id, "beside"?: fixture_id,
                          "facing"?: fixture_id}]}

Units are paces (0.75 m), the engine's own.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

PACE_M = 0.75

#: Footprint (w x d, paces) and height of a fixture by kind -- the engine's
#: table, never the model's numbers (Holodeck takes sizes from its asset
#: catalogue for the same reason). A kind not listed takes its size word.
FIXTURE_SIZES = {
    "bed": (3, 2, "waist"), "futon": (3, 2, "floor"), "nest": (4, 4, "waist"),
    "table": (2, 2, "waist"), "low_table": (2, 2, "floor"), "chabudai": (2, 2, "floor"),
    "desk": (2, 1, "waist"), "writing_desk": (2, 1, "floor"), "chair": (1, 1, "waist"),
    "cushion": (1, 1, "floor"), "bench": (3, 1, "waist"), "sofa": (3, 1, "waist"),
    "shelf": (2, 1, "full"), "bookshelf": (2, 1, "full"), "cabinet": (2, 1, "head"),
    "chest": (2, 1, "waist"), "trunk": (2, 1, "waist"), "wardrobe": (2, 1, "full"),
    "stove": (2, 1, "waist"), "hearth": (2, 1, "waist"), "counter": (3, 1, "waist"),
    "sink": (1, 1, "waist"), "basin": (1, 1, "waist"), "bath": (2, 2, "waist"),
    "tub": (2, 2, "waist"), "toilet": (1, 1, "waist"), "altar": (2, 1, "waist"),
    "alcove": (2, 1, "full"), "tokonoma": (2, 1, "full"), "screen": (2, 1, "head"),
    "lantern": (1, 1, "head"), "statue": (1, 1, "head"), "well": (2, 2, "waist"),
    "tree": (3, 3, "full"), "gate": (3, 1, "full"), "workbench": (3, 1, "waist"),
    "barrel": (1, 1, "waist"), "crate": (1, 1, "waist"), "rack": (2, 1, "head"),
    "window_seat": (2, 1, "waist"), "fireplace": (2, 1, "head"), "bar": (4, 1, "waist"),
    "piano": (2, 2, "waist"), "pillar": (1, 1, "full"), "rug": (3, 2, "floor"),
}
SIZE_WORD_FOOTPRINT = {"tiny": (1, 1, "floor"), "small": (1, 1, "waist"),
                       "medium": (2, 1, "waist"), "large": (3, 2, "waist"),
                       "huge": (4, 3, "head")}

#: Floor area range (square paces) by what a room is for. A room's size comes
#: from what it holds; this range is a floor under that, and a ceiling only
#: on a room that holds little.
PURPOSE_AREA = {
    "entryway": (6, 16), "hallway": (8, 40), "corridor": (8, 60), "stair": (8, 16),
    "bedroom": (12, 36), "guest_room": (12, 30), "living": (24, 80), "hall": (30, 120),
    "kitchen": (12, 36), "dining": (16, 50), "bath": (6, 20), "washroom": (6, 20),
    "toilet": (3, 6), "storage": (6, 20), "closet": (2, 8), "study": (10, 28),
    "workshop": (16, 50), "cellar": (16, 60), "basement": (20, 70), "attic": (16, 60),
    "shrine": (10, 40), "meditation": (10, 30), "common_room": (40, 100),
    "office": (10, 30), "cell": (6, 14), "garden": (40, 300), "courtyard": (30, 200),
    "path": (8, 60), "yard": (30, 200), "other": (10, 30),
}
#: The share of a room's floor its furniture may cover; the rest is floor to
#: walk on. About a third is what a lived-in room holds.
COVERAGE = 0.35
#: A stairwell by the kind of stair (run x width, paces): a straight flight
#: three paces long and two wide, a spiral turning in two by two, a ladder
#: through a hatch. A stair whose kind is not said is a straight flight, or a
#: spiral where its room cannot hold a flight.
WELLS = {"straight": (3, 2), "spiral": (2, 2), "ladder": (1, 1)}
WELL = WELLS["straight"]
#: Beam width and candidates kept per room in the storey search.
BEAM, PER_ROOM = 40, 14
#: The share of an upper room's floor that may stand past the walls below.
OVERHANG = 0.1
#: What each fallback gives up, so a room tries the least first: a quarter
#: off its size costs less than moving a stair or a door to another wall,
#: and halving it costs more.
_GIVE_UP = {1.0: 0, 0.75: 1, 0.55: 3, 0.4: 5}
#: How far a path runs from its door before the plot ends, in paces.
PATH_REACH = 8

_SIDES = ("n", "e", "s", "w")
_OPP = {"n": "s", "s": "n", "e": "w", "w": "e"}
_STEP = {"n": (0, -1), "s": (0, 1), "e": (1, 0), "w": (-1, 0)}
_CORRIDORS = ("hallway", "corridor")
_THROUGHWAYS = ("path",)
_OPEN_GROUND = ("garden", "courtyard", "yard")


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

    def as_dict(self):
        return {"x": self.x, "y": self.y, "w": self.w, "d": self.d}


def _runs(cells):
    """A cell set as row runs, so an irregular outdoor area is a rect list."""
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


def _bbox(cells):
    xs = [c[0] for c in cells]
    ys = [c[1] for c in cells]
    return Rect(min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1)


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


def _landing(well: Rect, side):
    """The row of floor in front of a well standing against `side`."""
    if side == "n":
        return Rect(well.x, well.y + well.d, well.w, 1)
    if side == "s":
        return Rect(well.x, well.y - 1, well.w, 1)
    if side == "w":
        return Rect(well.x + well.w, well.y, 1, well.d)
    return Rect(well.x - 1, well.y, 1, well.d)


@dataclass
class Layout:
    name: str
    floors: dict = field(default_factory=dict)      # level -> {room_id: [Rect]}
    grounds: dict = field(default_factory=dict)     # room_id: [Rect] (level 0, outdoors)
    doors: list = field(default_factory=list)       # {a, b, level, cell, kind, side}
    stairwells: list = field(default_factory=list)  # {id, from, to, levels, rect, landings}
    fixtures: dict = field(default_factory=dict)    # room_id -> [{id, name, kind, rect, height}]
    unplaced: list = field(default_factory=list)    # {room, fixture, why}
    warnings: list = field(default_factory=list)
    names: dict = field(default_factory=dict)
    purposes: dict = field(default_factory=dict)
    site: Rect | None = None
    blocks: dict = field(default_factory=dict)       # room_id -> block
    open_ground: list = field(default_factory=list)  # [Rect] plot nobody was named for

    def as_dict(self):
        foot = None
        if self.floors.get(0):
            foot = _bbox({c for rs in self.floors[0].values() for r in rs for c in r.cells()}).as_dict()
        return {
            "name": self.name,
            "floors": {str(lv): {rid: [p.as_dict() for p in parts] for rid, parts in rooms.items()}
                       for lv, rooms in sorted(self.floors.items())},
            "grounds": {rid: [p.as_dict() for p in parts] for rid, parts in self.grounds.items()},
            "footprint": foot,
            "site": self.site.as_dict() if self.site else None,
            "open_ground": [p.as_dict() for p in self.open_ground],
            "doors": self.doors, "stairwells": self.stairwells,
            "fixtures": {rid: [dict(f, rect=f["rect"].as_dict()) for f in fx]
                         for rid, fx in self.fixtures.items()},
            "unplaced": self.unplaced, "warnings": self.warnings,
            "names": self.names, "purposes": self.purposes, "blocks": self.blocks,
        }


# ------------------------------------------------------------ room sizing

def fixture_footprint(fx):
    kind = str(fx.get("kind") or "").strip().casefold().replace(" ", "_")
    if kind in FIXTURE_SIZES:
        return FIXTURE_SIZES[kind]
    word = str(fx.get("size") or "medium").casefold()
    return SIZE_WORD_FOOTPRINT.get(word, SIZE_WORD_FOOTPRINT["medium"])


def _purpose_key(room):
    text = str(room.get("purpose") or "").casefold().replace(" ", "_")
    if text in PURPOSE_AREA:
        return text
    text = " ".join(str(room.get(k) or "") for k in ("purpose", "name", "id")).casefold()
    for key in PURPOSE_AREA:
        if key.replace("_", " ") in text or key in text:
            return key
    return "other"


def room_target(room, *, wells=0, doors=0, stair_cells=None):
    """Square paces a room needs: its furniture at COVERAGE of the floor, each
    stairwell and its landing, a step inside each door; never under its
    purpose's floor, and over its ceiling only when its contents need it."""
    lo, hi = PURPOSE_AREA[_purpose_key(room)]
    furniture = sum(w * d for w, d, _h in (fixture_footprint(f) for f in room.get("fixtures") or ()))
    stair = stair_cells if stair_cells is not None else wells * (WELL[0] * WELL[1] + WELL[0])
    need = furniture / COVERAGE + stair + 1.5 * doors
    if _purpose_key(room) in _CORRIDORS:
        # a corridor is as long as what opens off it, two paces wide
        need = 2 * max(4, 2.5 * doors + (stair or 0) / 2.5)
    hint = str(room.get("size") or "").casefold()
    need *= {"tiny": 0.7, "small": 0.85, "large": 1.25, "huge": 1.5}.get(hint, 1.0)
    return max(lo, min(max(hi, need), max(need, lo * 1.2)))


def _dims(room, area, wells=0, ends=(), run=WELL[0]):
    """Rectangles near `area`: no side under the longest fixture, no room
    more than twice as long as wide -- a corridor excepted, which runs along
    the axis of the walls its stairs stand at, so they stand at its ENDS."""
    if _purpose_key(room) in _CORRIDORS:
        out = []
        axis = {("ns" if e in "ns" else "ew") for e in ends if e}
        for wide in (2, 3):
            for long in range(max(4, run * wells + 2), 19):
                if axis != {"ns"}:
                    out.append((long, wide))
                if axis != {"ew"}:
                    out.append((wide, long))
        return out
    longest = max((max(w, d) for w, d, _h in (fixture_footprint(f) for f in room.get("fixtures") or ())),
                  default=2)
    floor_side = max(2, longest, run if wells else 2)
    out = []
    for w in range(floor_side, 26):
        for d in range(floor_side if wells else 2, 26):
            a = w * d
            if 0.9 * area <= a <= 1.3 * area and max(w, d) <= 2 * min(w, d):
                out.append((w, d))
    if not out:
        side = max(floor_side, round(math.sqrt(area)))
        out = [(side, side)]
    out.sort(key=lambda t: (abs(t[0] * t[1] - area), abs(t[0] - t[1])))
    return out[:10]


# ------------------------------------------------------------ stairs

def _stairs(spec, level_of, by_id, layout):
    """Each stair with the room it rises from (`low`) and opens into (`high`)
    and the wall of each it stands against. A join that names the stair --
    or one of its ends, `attic_stair_bottom` -- says where it stands in that
    room, which is how a model says "at the end of the hallway"."""
    out = []
    for st in spec.get("stairs") or ():
        if not isinstance(st, dict):
            continue
        a, b = st.get("from"), st.get("to")
        if a not in level_of or b not in level_of:
            layout.warnings.append(f"stair {st.get('id')} joins a room no storey holds")
            continue
        if level_of[a] == level_of[b]:
            layout.warnings.append(f"stair {st.get('id')} joins two rooms on one storey "
                                   f"({layout.names.get(a, a)}, {layout.names.get(b, b)})")
            continue
        if abs(level_of[a] - level_of[b]) != 1:
            layout.warnings.append(f"stair {st.get('id')} skips a storey")
            continue
        sid = str(st.get("id") or f"{a}-{b}")
        side = str(st.get("side") or "")[:1]
        at = {a: str(st.get("from_at") or side)[:1], b: str(st.get("to_at") or side)[:1]}
        for rid in (a, b):
            for j in by_id[rid].get("joins") or ():
                to = str(j.get("to") or "")
                if to == sid or to.startswith(sid + "_"):
                    at[rid] = str(j.get("side") or "")[:1]
        low, high = (a, b) if level_of[a] < level_of[b] else (b, a)
        kind = str(st.get("kind") or "").casefold()
        out.append({"id": sid, "name": st.get("name") or "stair", "from": a, "to": b,
                    "kind": kind if kind in WELLS else None,
                    "low": low, "high": high,
                    "at": {rid: (v if v in _SIDES else None) for rid, v in at.items()}})
    return out


def _well_spots(room: Rect, at, taken, shapes=(WELL,)):
    """Every place a well can stand against `at` (any wall if None) inside
    `room`, with the landing in front of it, touching nothing in `taken`;
    the middle of the wall first."""
    out = []
    for side in ([at] if at else list(_SIDES)):
        along = room.w if side in "ns" else room.d
        across = room.d if side in "ns" else room.w
        for run, wide in [o for sh in shapes for o in (sh, sh[::-1])]:
            if run > along or wide >= across:
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
                if not room.contains(land):
                    continue
                if any(well.overlaps(t) or land.overlaps(t) for t in taken):
                    continue
                out.append((well, land, (shapes.index((run, wide)) if (run, wide) in shapes
                                         else shapes.index((wide, run))), abs(k - (along - run) / 2)))
    out.sort(key=lambda t: t[2:])
    return [(w, l) for w, l, _s, _k in out]


def _shapes(st, room=None):
    """The wells a stair may take: its kind's when the spec says; else a
    straight flight where its room can spare the floor, and a spiral where a
    flight and its landing would take more than half of what the room needs
    for everything else -- a tower's rooms, a closet stair."""
    if st.get("kind"):
        return (WELLS[st["kind"]],)
    run, wide = WELLS["straight"]
    if room is not None and run * wide + run > 0.5 * room_target(room, doors=len(room.get("joins") or ())):
        return (WELLS["spiral"], WELLS["straight"])
    return (WELLS["straight"], WELLS["spiral"])


# ------------------------------------------------------------ storeys

def _side_of(rid, other, by_id):
    """The side of `rid` on which `other` lies, if either room's joins say."""
    for j in by_id[rid].get("joins") or ():
        if j.get("to") == other and str(j.get("side") or "")[:1] in _SIDES:
            return str(j["side"])[:1]
    for j in by_id[other].get("joins") or ():
        if j.get("to") == rid and str(j.get("side") or "")[:1] in _SIDES:
            return _OPP[str(j["side"])[:1]]
    return None


def _joined(a, b, by_id):
    return any(j.get("to") == b for j in by_id[a].get("joins") or ()) or \
        any(j.get("to") == a for j in by_id[b].get("joins") or ())


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


def _walls_between(parts_a, parts_b, avoid=frozenset()):
    """The longest wall two rooms share, less the cells a doorway may not
    open from -- a stairwell on either side of the wall."""
    best = (None, [])
    for a in parts_a:
        for b in parts_b:
            side, cells = _shared_wall(a, b)
            if side is None:
                continue
            dx, dy = _STEP[side]
            cells = [c for c in cells if c not in avoid and (c[0] + dx, c[1] + dy) not in avoid]
            if len(cells) > len(best[1]):
                best = (side, cells)
    return best


def _pairs(rooms, by_id):
    ids = {r["id"] for r in rooms}
    seen = set()
    for r in rooms:
        for j in r.get("joins") or ():
            to = j.get("to")
            if to in ids and to != r["id"]:
                key = tuple(sorted((r["id"], to)))
                if key not in seen:
                    seen.add(key)
                    yield key


def _score(state, pairs, by_id, targets, prefer, outward, pending=()):
    """Lower is better: a join with no wall to open in, a join on the wrong
    side, a sprawling outline, a room far from its size, a room off what it
    stands over, a room that opens outdoors with no outside wall."""
    placed = state["rooms"]
    avoid = set()
    for well, _land in state["wells"].values():
        avoid |= well.cells()
    s = 0.0
    for a, b in pairs:
        if a not in placed or b not in placed:
            continue
        side, cells = _walls_between([placed[a]], [placed[b]], avoid)
        if not cells:
            s += 40
            continue
        asked = _side_of(a, b, by_id)
        if asked and asked != side:
            s += 6
    cells = set()
    for r in placed.values():
        cells |= r.cells()
    if cells:
        bb = _bbox(cells)
        s += 0.6 * (bb.w + bb.d) + 0.35 * (bb.w * bb.d - len(cells))
    for rid, r in placed.items():
        t = targets[rid]
        s += 6 * abs(r.w * r.d - t) / t
        over = prefer.get(rid)
        if over is not None:
            s += 0.4 * len(r.cells() - over.cells())
    for rid, side in outward.items():
        r = placed.get(rid)
        if r is None:
            continue
        steps = [_STEP[side]] if side else list(_STEP.values())
        if not any((x + dx, y + dy) not in cells for x, y in r.cells() for dx, dy in steps):
            s += 12
    # LOOK AHEAD: a wall must have room for the rooms still to come against it
    # -- three paces of open wall each, wells and placed neighbours excluded.
    for rid, r in placed.items():
        want = {}
        for o in pending:
            sd = _side_of(rid, o, by_id)
            if sd:
                want[sd] = want.get(sd, 0) + 3
        for sd, need in want.items():
            dx, dy = _STEP[sd]
            if sd in "ns":
                row = r.y if sd == "n" else r.y + r.d - 1
                wall = [(x, row) for x in range(r.x, r.x + r.w)]
            else:
                col = r.x if sd == "w" else r.x + r.w - 1
                wall = [(col, y) for y in range(r.y, r.y + r.d)]
            open_ = sum(1 for c in wall if c not in avoid and (c[0] + dx, c[1] + dy) not in cells)
            s += 5 * max(0, need - open_)
    return s


def _storey_order(rooms, by_id, first):
    adj = {r["id"]: [] for r in rooms}
    for a, b in _pairs(rooms, by_id):
        adj[a].append(b)
        adj[b].append(a)
    order, seen = [], set()
    queue = [rid for rid in first if rid in adj]
    if not queue and rooms:
        queue = [max(rooms, key=lambda r: len(adj[r["id"]]))["id"]]
    while len(order) < len(adj):
        if not queue:
            queue = [next(rid for rid in adj if rid not in seen)]
        rid = queue.pop(0)
        if rid in seen:
            continue
        seen.add(rid)
        order.append(rid)
        queue.extend(sorted(adj[rid], key=lambda o: -len(adj[o])))
    return order


def _place_storey(lv, rooms, by_id, stairs, pinned, below, support, outward, layout, carry=None):
    """Grow one storey room by room (a beam search). `pinned` holds the wells
    already cut through the storey this one was built from: their room here
    must hold each flush against the wall the spec names, with its landing.
    A well first cut on this storey is chosen with its room. Returns (rooms
    {id: Rect}, wells {stair id: (well, landing on this storey)})."""
    here = {r["id"] for r in rooms}
    free_wells, pins = {}, {}
    for st in stairs:
        for end in ("low", "high"):
            rid = st[end]
            if rid in here:
                (pins if st["id"] in pinned else free_wells).setdefault(rid, []).append(st)
    def stair_cells(rid):
        n = 0
        for st in free_wells.get(rid, ()):
            run, wide = _shapes(st, by_id[rid])[0]
            n += run * wide + run
        for st in pins.get(rid, ()):
            w = pinned[st["id"]]
            n += w.w * w.d + max(w.w, w.d)
        return n

    def run_of(rid):
        runs = [min(sh[0] for sh in _shapes(st, by_id[rid])) for st in free_wells.get(rid, ())] + \
            [max(pinned[st["id"]].w, pinned[st["id"]].d) for st in pins.get(rid, ())]
        return max(runs, default=WELL[0])

    # A storey carries the storeys above it: when they need more floor than
    # it does, its rooms grow (`carry`) -- a building is as wide as the
    # widest storey it holds up.
    carry = carry or {}
    targets = {r["id"]: carry.get(r["id"], 1.0) * room_target(r, wells=len(free_wells.get(r["id"], ())) + len(pins.get(r["id"], ())),
                                            doors=len(r.get("joins") or ()), stair_cells=stair_cells(r["id"]))
               for r in rooms}
    # what a room stands over: the room it names, else the far end of its stair
    prefer = {}
    for r in rooms:
        if r.get("over") in below:
            prefer[r["id"]] = below[r["over"]]
    for rid, sts in pins.items():
        for st in sts:
            other = st["low"] if st["high"] == rid else st["high"]
            if rid not in prefer and other in below:
                prefer[rid] = below[other]
    pairs = list(_pairs(rooms, by_id))
    order = _storey_order(rooms, by_id, list(pins))

    def rects_for(state, rid):
        room = by_id[rid]
        placed = state["rooms"]
        n_wells = len(free_wells.get(rid, ())) + len(pins.get(rid, ()))
        ends = [st["at"].get(rid) for st in free_wells.get(rid, ())]
        if rid not in relaxed:
            ends += [st["at"].get(rid) for st in pins.get(rid, ())]
        dims = _dims(room, targets[rid] * shrink.get(rid, 1.0), n_wells, ends, run_of(rid))
        if pins.get(rid):
            well = pinned[pins[rid][0]["id"]]
            for w, d in dims:
                for x in range(well.x + well.w - w, well.x + 1):
                    for y in range(well.y + well.d - d, well.y + 1):
                        yield Rect(x, y, w, d)
            return
        anchors = [o for o in placed if _joined(rid, o, by_id)] or list(placed)
        if not placed:
            if support.get(rid):
                c = _bbox(support[rid])
                for w, d in dims:
                    for x in range(c.x, c.x + c.w - w + 1):
                        for y in range(c.y, c.y + c.d - d + 1):
                            yield Rect(x, y, w, d)
            else:
                for w, d in dims:
                    yield Rect(0, 0, w, d)
            return
        for o in anchors:
            a = placed[o]
            asked = None if rid in loose else _side_of(o, rid, by_id)   # side of o where rid lies
            for side in ([asked] if asked else list(_SIDES)):
                for w, d in dims:
                    if side in "ns":
                        y = a.y - d if side == "n" else a.y + a.d
                        for x in range(a.x - w + 2, a.x + a.w - 1):
                            yield Rect(x, y, w, d)
                    else:
                        x = a.x - w if side == "w" else a.x + a.w
                        for y in range(a.y - d + 2, a.y + a.d - 1):
                            yield Rect(x, y, w, d)

    def grow(state, rid):
        placed = state["rooms"]
        out = []
        for r in rects_for(state, rid):
            if any(r.overlaps(o) for o in placed.values()):
                continue
            if support.get(rid) is not None:
                # a storey stands on the one below; it may overhang a notch in
                # the walls beneath by a tenth of its floor, as jettied upper
                # floors and eaves do, never more
                off = len(r.cells() - support[rid])
                if off > OVERHANG * r.w * r.d or (off and not support[rid] & r.cells()):
                    continue
            mine, ok = {}, True
            for st in pins.get(rid, ()):
                well = pinned[st["id"]]
                at = None if rid in relaxed else st["at"].get(rid)
                if not r.contains(well):
                    ok = False
                    break
                # a well as wide as its room touches three walls: the landing
                # lies in front of whichever one leaves floor before it
                lands = [_landing(well, sd) for sd in ([at] if at else _SIDES) if r.flush(well, sd)]
                lands = [ld for ld in lands
                         if r.contains(ld) and not any(ld.overlaps(m[0]) for m in mine.values())]
                if not lands:
                    ok = False
                    break
                mine[st["id"]] = (well, lands[0])
            if not ok:
                continue
            # A room above that gave way on its stair's wall turns as a whole:
            # what the spec stood at each of its walls turns with it.
            turn = 0
            if rid in relaxed:
                for st in pins.get(rid, ()):
                    asked, got = st["at"].get(rid), mine.get(st["id"])
                    if asked and got:
                        well, land = got
                        side = next(sd for sd in _SIDES if _landing(well, sd) == land)
                        turn = (_SIDES.index(side) - _SIDES.index(asked)) % 4
                        break
            for st in free_wells.get(rid, ()):
                at = st["at"].get(rid)
                if at and turn:
                    at = _SIDES[(_SIDES.index(at) + turn) % 4]
                # A STAIR THAT CLIMBS ON takes the shaft it arrived by: a
                # tower's spiral, a stair hall's flights stacked one over the
                # next. Only where the walls asked agree, or none was asked.
                shaft = None
                for pin in pins.get(rid, ()):
                    well, land = mine[pin["id"]]
                    side = next(sd for sd in _SIDES if _landing(well, sd) == land)
                    same = (well.w, well.d) in [o for sh in _shapes(st, by_id[rid]) for o in (sh, sh[::-1])]
                    if same and (at is None or at == side) and not any(
                            m[0] == well for k, m in mine.items() if k != pin["id"]):
                        shaft = (well, land)
                        break
                if shaft:
                    mine[st["id"]] = shaft
                    continue
                taken = [m[0] for m in mine.values()] + [m[1] for m in mine.values()]
                spots = _well_spots(r, None if rid in loose_wells else at, taken,
                                    _shapes(st, by_id[rid]))
                if not spots:
                    ok = False
                    break
                mine[st["id"]] = spots[0]
            if not ok:
                continue
            out.append({"rooms": dict(placed, **{rid: r}), "wells": dict(state["wells"], **mine)})
        return out

    relaxed, loose, shrink, loose_wells = set(), set(), {}, set()
    beam = [{"rooms": {}, "wells": {}}]
    for k, rid in enumerate(order):
        pending = order[k + 1:]
        grown = []
        # Each fallback is a real designer's: the room above a stair gives
        # way on the wall it arrives at (the two ends' walls can contradict
        # each other), a room whose asked side is full goes on another, and
        # a room that cannot stand on the storey below at full size shrinks.
        # Fallbacks in order of what they give up: the room shrinks to stand
        # on the storey below; the room above a stair gives way on the wall
        # it arrives at (the two ends' walls can contradict each other); a
        # stair stands where it fits; a room whose asked side is full goes on
        # another. Only the fallbacks a room needed are reported.
        tries = sorted(((f, rl, wl, lo) for rl, wl, lo in ((0, 0, 0), (1, 0, 0), (1, 1, 0), (1, 1, 1))
                        for f in (1.0, 0.75, 0.55, 0.4)),
                       key=lambda t: _GIVE_UP[t[0]] + 2 * (t[1] + t[2] + t[3]))
        for f, rl, wl, lo in tries:
            if (rl and not pins.get(rid)) and (wl and not free_wells.get(rid)) and not lo:
                continue
            shrink[rid] = f
            for flag, bag in ((rl and pins.get(rid), relaxed), (wl and free_wells.get(rid), loose_wells),
                              (lo and not pins.get(rid), loose)):
                (bag.add if flag else bag.discard)(rid)
            for state in beam:
                scored = sorted(((_score(c, pairs, by_id, targets, prefer, outward, pending), i, c)
                                 for i, c in enumerate(grow(state, rid))), key=lambda t: t[:2])
                grown.extend(scored[:PER_ROOM])
            if grown:
                break
        if shrink.get(rid) == 1.0:
            del shrink[rid]
        if grown and rid in relaxed:
            for st in pins[rid]:
                if st["at"].get(rid):
                    layout.warnings.append(
                        f"{st['name']} could not arrive at the {st['at'][rid]} wall of "
                        f"{layout.names.get(rid, rid)}; it arrives where it fits")
        if grown and rid in loose_wells:
            layout.warnings.append(f"{layout.names.get(rid, rid)}: a stair could not stand at the wall "
                                   f"asked and stands where it fits")
        if grown and rid in loose:
            layout.warnings.append(f"{layout.names.get(rid, rid)} found its asked side taken "
                                   f"and went on another")
        if grown and rid in shrink:
            layout.warnings.append(f"{layout.names.get(rid, rid)} shrank to "
                                   f"{round(shrink[rid] * 100)}% to stand on the storey "
                                   f"{'below' if lv > 0 else 'above'}")
        if not grown:
            layout.warnings.append(
                f"{layout.names.get(rid, rid)} found no floor on storey {lv}"
                + ("" if support.get(rid) is None else
                   f" standing on the storey {'below' if lv > 0 else 'above'}"))
            continue
        grown.sort(key=lambda t: t[:2])
        seen, beam = set(), []
        for _sc, _i, st in grown:
            key = tuple(sorted((k, v.x, v.y, v.w, v.d) for k, v in st["rooms"].items()))
            if key not in seen:
                seen.add(key)
                beam.append(st)
            if len(beam) >= BEAM:
                break
    return beam[0]["rooms"], beam[0]["wells"]


# ------------------------------------------------------------ doors

def _doors(level, rooms, parts, layout, avoid=frozenset()):
    """One doorway per declared join, in the wall the two rooms share,
    spread along it in declared order."""
    per_wall = {}
    done = {tuple(sorted((d["a"], d["b"]))) for d in layout.doors if d["level"] == level}
    for r in rooms:
        for j in r.get("joins") or ():
            to = j.get("to")
            key = tuple(sorted((r["id"], str(to))))
            if key in done or r["id"] not in parts or to not in parts:
                continue
            done.add(key)
            side, cells = _walls_between(parts[r["id"]], parts[to], avoid)
            if not cells:
                layout.warnings.append(f"{layout.names.get(r['id'], r['id'])} and "
                                       f"{layout.names.get(to, to)} were to join but share no wall")
                continue
            asked = str(j.get("side") or "").casefold()[:1]
            if asked in _SIDES and asked != side:
                layout.warnings.append(f"{layout.names.get(to, to)} was asked on the {asked} side of "
                                       f"{layout.names.get(r['id'], r['id'])} and landed on the {side}")
            per_wall.setdefault((r["id"], side), []).append(
                (int(j.get("order") or 0), to, cells, j.get("kind") or "door"))
    for (rid, side), items in per_wall.items():
        items.sort(key=lambda t: t[0])
        n = len(items)
        for k, (_o, to, cells, kind) in enumerate(items):
            pos = cells[min(len(cells) - 1, int((k + 1) * len(cells) / (n + 1)))]
            layout.doors.append({"a": rid, "b": to, "level": level, "side": side,
                                 "cell": list(pos), "kind": kind})


# ------------------------------------------------------------ fixtures

def _place_fixtures(room_id, room, parts, layout, *, solid=frozenset(), clear=frozenset(),
                    required=frozenset()):
    """Fixtures by relation (Holodeck's split), backtracking. Hard: inside
    the room, no overlap, never on `solid` (a stairwell) or `clear` (a
    doorway's step, a stair's landing), against the wall it names, and never
    cutting one `required` cell off from another -- a room whose door cannot
    reach its stair is not a room. Soft: near / beside / facing the fixture
    named. A fixture no cell takes is reported, never silently dropped."""
    cells = set()
    for r in parts:
        cells |= r.cells()
    if not cells:
        return
    walkable = cells - set(solid)
    fixtures = sorted(room.get("fixtures") or (),
                      key=lambda f: -(fixture_footprint(f)[0] * fixture_footprint(f)[1]))
    occupied = set(solid) | set(clear)
    furniture = set()
    placed = {}
    xs = [c[0] for c in cells]
    ys = [c[1] for c in cells]
    centre = ((min(xs) + max(xs) + 1) / 2, (min(ys) + max(ys) + 1) / 2)

    def on_wall(r, side):
        edge = {"n": [(x, r.y - 1) for x in range(r.x, r.x + r.w)],
                "s": [(x, r.y + r.d) for x in range(r.x, r.x + r.w)],
                "w": [(r.x - 1, y) for y in range(r.y, r.y + r.d)],
                "e": [(r.x + r.w, y) for y in range(r.y, r.y + r.d)]}[side]
        return all(c not in cells for c in edge)

    def candidates(fx):
        w, d, _h = fixture_footprint(fx)
        at = str(fx.get("at") or "").casefold()
        out = []
        for ww, dd in {(w, d), (d, w)}:
            if at in _SIDES and ((at in "ns" and ww < dd) or (at in "ew" and dd < ww)):
                continue
            for x in range(min(xs), max(xs) - ww + 2):
                for y in range(min(ys), max(ys) - dd + 2):
                    r = Rect(x, y, ww, dd)
                    if not r.cells() <= cells:
                        continue
                    if at in _SIDES and not on_wall(r, at):
                        continue
                    if at.startswith("corner_") and not (on_wall(r, at[7]) and on_wall(r, at[8])):
                        continue
                    if at == "middle" and any(on_wall(r, s) for s in _SIDES):
                        continue
                    out.append(r)
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
        return not (rc & occupied) and _connected(walkable - furniture - rc, required)

    budget = [3000]
    moved = []

    def go(i):
        if i == len(fixtures):
            return True
        budget[0] -= 1
        if budget[0] < 0:
            return False
        fx = fixtures[i]
        cands = [r for r in candidates(fx) if fits(r)]
        if not cands and fx.get("at"):
            # A real designer moves it to another wall, then anywhere it fits.
            loose = dict(fx)
            for alt in [sd for sd in _SIDES if sd != fx.get("at")] + [None]:
                loose["at"] = alt
                cands = [r for r in candidates(loose) if fits(r)]
                if cands:
                    moved.append((fx.get("name") or fx.get("id"), fx.get("at"), alt or "anywhere"))
                    break
        cands.sort(key=lambda r: -score(fx, r))
        for r in cands[:10]:
            placed[fx["id"]] = r
            occupied.update(r.cells())
            furniture.update(r.cells())
            if go(i + 1):
                return True
            occupied.difference_update(r.cells())
            furniture.difference_update(r.cells())
            del placed[fx["id"]]
        layout.unplaced.append({"room": room_id, "fixture": fx.get("name") or fx.get("id"),
                                "why": "no free place " + (f"at {fx.get('at')}" if fx.get("at") else "in the room")})
        return go(i + 1)

    go(0)
    for name, was, now in dict(((m[0], m) for m in moved)).values():
        layout.warnings.append(f"{layout.names.get(room_id, room_id)}: {name} could not stand at {was}; "
                               f"moved {('to the ' + now + ' wall') if now != 'anywhere' else 'to where it fits'}")
    layout.fixtures[room_id] = [
        {"id": f["id"], "name": f.get("name") or f["id"], "kind": f.get("kind"),
         "at": f.get("at"), "rect": placed[f["id"]], "height": fixture_footprint(f)[2]}
        for f in fixtures if f["id"] in placed]


# ------------------------------------------------------------ the grounds

def _ground_anchors(g, by_id):
    """(what an outdoor place joins, the side of that thing it lies on)."""
    for j in g.get("joins") or ():
        sd = str(j.get("side") or "")[:1]
        yield j.get("to"), (_OPP.get(sd) if sd in _SIDES else None)
    for r in by_id.values():
        for j in r.get("joins") or ():
            if j.get("to") == g["id"]:
                sd = str(j.get("side") or "")[:1]
                yield r["id"], (sd if sd in _SIDES else None)


def _path_side(rect, asked, house):
    """The side a path leaves `rect` from: the side asked when two paces of
    its wall face the open, else the side with the most wall outside."""
    def open_wall(side):
        dx, dy = _STEP[side]
        return sum((x + dx, y + dy) not in house for x, y in rect.cells()
                   if (x + dx, y + dy) not in rect.cells())
    if asked and open_wall(asked) >= 2:
        return asked
    return max(_SIDES, key=open_wall)


def _open_side(rect, house):
    """The side of `rect` with the most wall on the outside of `house`."""
    def outside(side):
        dx, dy = _STEP[side]
        return sum((x + dx, y + dy) not in house for x, y in rect.cells()
                   if (x + dx, y + dy) not in rect.cells())
    return max(_SIDES, key=outside)


def _grounds(grounds, base, by_id, layout):
    """The building stands inside its grounds. The plot is the ground floor's
    outline with a margin wide enough for every outdoor area; a path runs
    from the door of what it joins to the plot's edge, a gate stands at a
    path's far end, a small outdoor place takes a patch beside what it
    joins, and the gardens and yards fill the rest -- each the part of the
    plot nearest what it opens from, and the one the building stands
    `around` whatever is left."""
    house = set()
    for r in base.values():
        house |= r.cells()
    if not house or not grounds:
        return {}
    hb = _bbox(house)
    kinds = {g["id"]: _purpose_key(g) for g in grounds}
    need = sum(room_target(g) for g in grounds)
    m = 3
    while (hb.w + 2 * m) * (hb.d + 2 * m) - len(house) < need * 1.1 and m < 30:
        m += 1
    # a path needs room to be a path: the plot reaches further on the side
    # it leaves the building from, as far as the chain of paths and gates
    # that runs out from that door
    def chain_from(g):
        seen, queue, length = {g["id"]}, [g], 0
        while queue:
            cur = queue.pop()
            length += PATH_REACH if kinds[cur["id"]] in _THROUGHWAYS else 2
            for to, _sd in _ground_anchors(cur, by_id):
                nxt = next((x for x in grounds if x["id"] == to), None)
                if nxt is not None and nxt["id"] not in seen and kinds[to] not in _OPEN_GROUND:
                    seen.add(to)
                    queue.append(nxt)
        return length

    extra = {s: 0 for s in _SIDES}
    for g in grounds:
        if kinds[g["id"]] not in _THROUGHWAYS:
            continue
        for to, sd in _ground_anchors(g, by_id):
            if to in base:
                side = _path_side(base[to], sd, house)
                extra[side] = max(extra[side], max(0, chain_from(g) - m + 2))
                break
    site = Rect(hb.x - m - extra["w"], hb.y - m - extra["n"],
                hb.w + 2 * m + extra["w"] + extra["e"], hb.d + 2 * m + extra["n"] + extra["s"])
    layout.site = site
    plot = site.cells()
    free = plot - house
    parts = {}

    def own(gid, cells):
        cells = set(cells) & free
        free.difference_update(cells)
        return cells

    def anchors_of(g):
        return _ground_anchors(g, by_id)

    def rect_of(to):
        if to in base:
            return base[to]
        if parts.get(to):
            return _bbox(parts[to])
        return None

    def exposed(rect, side):
        """Open plot just outside `rect`'s `side` wall."""
        if side in "ns":
            row = rect.y - 1 if side == "n" else rect.y + rect.d
            return [(x, row) for x in range(rect.x, rect.x + rect.w) if (x, row) in free]
        col = rect.x - 1 if side == "w" else rect.x + rect.w
        return [(col, y) for y in range(rect.y, rect.y + rect.d) if (col, y) in free]

    paths = [g for g in grounds if kinds[g["id"]] in _THROUGHWAYS]
    gates = [g for g in grounds if g not in paths and kinds[g["id"]] not in _OPEN_GROUND
             and any(kinds.get(to) in _THROUGHWAYS for to, _s in anchors_of(g))]
    open_ = [g for g in grounds if kinds[g["id"]] in _OPEN_GROUND]
    small = [g for g in grounds if g not in paths and g not in gates and g not in open_]
    within = [g for g in small if not any(to in base or kinds.get(to) in _THROUGHWAYS
                                          for to, _s in anchors_of(g))]
    small = [g for g in small if g not in within]
    heading, ends = {}, {}   # path id -> direction it runs; its far row of cells

    def run(gid, start, side, reach):
        """Cells from `start` (a row across the way) onward toward `side`."""
        dx, dy = _STEP[side]
        cells, row = set(), list(start)
        for _k in range(reach or 10 ** 6):
            row = [c for c in row if c in free]
            if not row:
                break
            cells.update(row)
            last = row
            row = [(x + dx, y + dy) for x, y in row]
        if cells:
            heading[gid] = side
            ends[gid] = last
        return cells

    def chained(gid):
        """Does a further path or gate continue from this one?"""
        return any(to == gid for g in paths + gates if g["id"] != gid for to, _s in anchors_of(g))

    # PATHS: three paces wide, from the door outward -- or on from the end of
    # the path they continue -- PATH_REACH paces, or to the edge of the plot
    # when nothing continues from them.
    pending = list(paths)
    for _round in range(len(paths) + 1):
        for g in list(pending):
            cells = set()
            for to, sd in anchors_of(g):
                if to in ends:
                    side = heading[to]
                    dx, dy = _STEP[side]
                    cells = run(g["id"], [(x + dx, y + dy) for x, y in ends[to]], side,
                                PATH_REACH if chained(g["id"]) else 0)
                elif to in base:
                    rect = base[to]
                    side = _path_side(rect, sd, house)
                    front = exposed(rect, side)
                    if len(front) >= 2:
                        mid = len(front) // 2
                        cells = run(g["id"], front[max(0, mid - 1): mid + 2], side,
                                    PATH_REACH if chained(g["id"]) else 0)
                else:
                    continue
                break
            if cells:
                parts[g["id"]] = own(g["id"], cells)
                pending.remove(g)
        if not pending:
            break
    late_paths = list(pending)   # tried again once the gardens hold their gates

    # GATES: across the way just beyond the end of the path they stand on --
    # or its last two rows, where the plot ends there.
    for g in gates:
        path = next((to for to, _s in anchors_of(g) if to in ends), None)
        if path is None:
            # a gate no laid path ends at stands in the garden it opens on
            within.append(g)
            continue
        side = heading[path]
        dx, dy = _STEP[side]
        beyond = [(x + dx, y + dy) for x, y in ends[path]]
        cut = set()
        for step in range(2):
            row = [(x + dx * step, y + dy * step) for x, y in beyond]
            cut |= {c for c in row if c in free}
        if len(cut) >= len(beyond):
            parts[g["id"]] = own(g["id"], cut)
            last = [c for c in ((x + dx, y + dy) for x, y in beyond) if c in parts[g["id"]]] or beyond
        else:
            pc = parts[path]
            back = set(ends[path]) | {(x - dx, y - dy) for x, y in ends[path]}
            parts[path] = pc - back
            parts[g["id"]] = back & pc
            last = list(ends[path])
        heading[g["id"]], ends[g["id"]] = side, last

    # SMALL PLACES beside the building or a path: a patch of their own size.
    for g in small:
        side_len = max(2, round(math.sqrt(room_target(g) * 0.6)))
        spot = None
        for to, sd in anchors_of(g):
            anchor = rect_of(to)
            if anchor is None:
                continue
            for side in ([sd] if sd else []) + [s for s in _SIDES if s != sd]:
                along = anchor.w if side in "ns" else anchor.d
                for w, d in ((side_len, side_len), (side_len + 1, side_len - 1),
                             (side_len - 1, side_len + 1)):
                    own_len = w if side in "ns" else d
                    for slide in sorted(range(-(own_len - 1), along),
                                        key=lambda v: abs(v - (along - own_len) // 2)):
                        if side == "n":
                            r = Rect(anchor.x + slide, anchor.y - d, w, d)
                        elif side == "s":
                            r = Rect(anchor.x + slide, anchor.y + anchor.d, w, d)
                        elif side == "e":
                            r = Rect(anchor.x + anchor.w, anchor.y + slide, w, d)
                        else:
                            r = Rect(anchor.x - w, anchor.y + slide, w, d)
                        if r.cells() <= free:
                            spot = r
                            break
                    if spot:
                        break
                if spot:
                    break
            if spot:
                break
        if spot is None:
            layout.warnings.append(f"{layout.names[g['id']]} found no patch beside what it joins")
            continue
        parts[g["id"]] = own(g["id"], spot.cells())

    # GARDENS AND YARDS: the rest of the plot, each growing outward from what
    # it opens on, so each is the part of the plot nearest its own door.
    seeds = {}
    for g in open_:
        for to, sd in anchors_of(g):
            rect = rect_of(to)
            if rect is None:
                continue
            for side in ([sd] if sd else []) + [s for s in _SIDES if s != sd]:
                front = exposed(rect, side)
                if front:
                    seeds[g["id"]] = set(front)
                    break
            if g["id"] in seeds:
                break
    around = next((g["id"] for g in open_ if g.get("around")), None)
    frontier = [(c, gid) for gid, cs in seeds.items() for c in cs]
    grown = {gid: set() for gid in seeds}
    while frontier:
        nxt = []
        for c, gid in frontier:
            if c not in free:
                continue
            free.discard(c)
            grown[gid].add(c)
            for dx, dy in _STEP.values():
                n = (c[0] + dx, c[1] + dy)
                if n in free:
                    nxt.append((n, gid))
        frontier = nxt
    for gid, cs in grown.items():
        if cs:
            parts[gid] = cs
    if around and free:
        parts[around] = parts.get(around, set()) | free
        free = set()
    for g in open_:
        if not parts.get(g["id"]):
            layout.warnings.append(f"{layout.names[g['id']]} found no ground beside what it joins")

    # PLACES WITHIN a garden or yard: carved from inside it, toward the side
    # the spec names, else as far from the building as the area reaches.
    cx, cy = hb.x + hb.w / 2, hb.y + hb.d / 2
    for g in within:
        side_len = max(2, round(math.sqrt(room_target(g) * 0.6)))
        host, toward = None, None
        for to, sd in anchors_of(g):
            if parts.get(to):
                host, toward = to, sd
                break
        if host is None:
            layout.warnings.append(f"{layout.names[g['id']]} found nothing it stands in")
            continue
        area = parts[host]
        box = _bbox(area)
        best = None
        for x in range(box.x, box.x + box.w - side_len + 1):
            for y in range(box.y, box.y + box.d - side_len + 1):
                r = Rect(x, y, side_len, side_len)
                rc = r.cells()
                if not rc <= area:
                    continue
                # keep a step of the host's ground round it on every side
                ring = {(a + dx, b + dy) for a, b in rc for dx, dy in _STEP.values()} - rc
                if not ring <= area | house:
                    continue
                mx, my = x + side_len / 2, y + side_len / 2
                if toward:
                    # `toward` is the side of the host where the place lies
                    key = {"n": my, "s": -my, "w": mx, "e": -mx}[toward]
                else:
                    key = -math.hypot(mx - cx, my - cy)
                if best is None or key < best[0]:
                    best = (key, r)
        if best is None:
            layout.warnings.append(f"{layout.names[g['id']]} found no room inside {layout.names[host]}")
            continue
        cells = best[1].cells()
        parts[host] = area - cells
        parts[g["id"]] = cells

    # PATHS THAT HANG FROM A GATE (or another place in the garden) rather
    # than the building: from that place toward the building, across the
    # garden, until they reach a wall or a laid path.
    open_ids = {g["id"] for g in open_}
    for g in late_paths:
        start = next((to for to, _s in anchors_of(g) if parts.get(to) and to not in open_ids), None)
        if start is None:
            layout.warnings.append(f"{layout.names[g['id']]} found no door, path or gate to run from")
            continue
        # the shortest walk through the gardens from that place to the
        # building room the gardens open from (else any wall), two wide
        garden = set()
        for h in open_ids:
            garden |= parts.get(h, set())
        doors = {to for h in open_ids for to, _s in anchors_of(by_id[h]) if to in base}
        goal_cells = set()
        for rid in (doors or base):
            r = base[rid]
            goal_cells |= {(x + dx, y + dy) for x, y in r.cells() for dx, dy in _STEP.values()}
        goal_cells &= garden
        src = {(x + dx, y + dy) for x, y in parts[start] for dx, dy in _STEP.values()} & garden
        prev, frontier, hit = {c: None for c in src}, list(src), None
        while frontier and hit is None:
            nxt = []
            for c in frontier:
                if c in goal_cells:
                    hit = c
                    break
                for dx, dy in _STEP.values():
                    n = (c[0] + dx, c[1] + dy)
                    if n in garden and n not in prev:
                        prev[n] = c
                        nxt.append(n)
            frontier = nxt
        cells = set()
        while hit is not None:
            cells.add(hit)
            hit = prev[hit]
        # widen to two paces, inside the garden
        cells |= {(x + 1, y) for x, y in cells if (x + 1, y) in garden} if len({c[0] for c in cells}) <= \
            len({c[1] for c in cells}) else {(x, y + 1) for x, y in cells if (x, y + 1) in garden}
        if not cells:
            layout.warnings.append(f"{layout.names[g['id']]} found no garden to cross")
            continue
        for h in open_ids:
            if parts.get(h):
                parts[h] = parts[h] - cells
        parts[g["id"]] = cells
    layout.open_ground = _runs(free) if free else []
    return {gid: _runs(cs) for gid, cs in parts.items() if cs}


# ---------------------------------------------------------------- solve

def solve(spec) -> Layout:
    layout = Layout(name=str(spec.get("name") or "building"))
    rooms_at = {}
    for f in spec.get("floors") or ():
        rooms_at.setdefault(int(f.get("level") or 0), []).extend(
            r for r in f.get("rooms") or () if isinstance(r, dict) and r.get("id"))
    grounds = [g for g in spec.get("grounds") or () if isinstance(g, dict) and g.get("id")]
    by_id = {r["id"]: r for rs in rooms_at.values() for r in rs}
    by_id.update({g["id"]: g for g in grounds})
    level_of = {r["id"]: lv for lv, rs in rooms_at.items() for r in rs}
    ground_ids = {g["id"] for g in grounds}
    for r in by_id.values():
        layout.names[r["id"]] = r.get("name") or r["id"]
        layout.purposes[r["id"]] = _purpose_key(r)
    if not level_of:
        layout.warnings.append("no storey holds a room")
        return layout

    stairs = _stairs(spec, level_of, by_id, layout)
    # a room that opens onto the grounds: the wall it opens from must be outside
    outward = {}
    for r in rooms_at.get(0, ()):
        for j in r.get("joins") or ():
            if j.get("to") in ground_ids:
                sd = str(j.get("side") or "")[:1]
                outward[r["id"]] = sd if sd in _SIDES else outward.get(r["id"])
    for g in grounds:
        for j in g.get("joins") or ():
            if level_of.get(j.get("to")) == 0:
                sd = str(j.get("side") or "")[:1]
                outward.setdefault(j["to"], _OPP[sd] if sd in _SIDES else None)

    # The ground floor first, then up storey by storey, then down: each
    # storey stands on (or under) one already built, and a well cut through
    # one is pinned at the same cells on the next.
    levels = sorted(rooms_at)
    first = 0 if 0 in rooms_at else levels[0]
    order = [lv for lv in levels if lv >= first] + sorted((lv for lv in levels if lv < first), reverse=True)
    # BLOCKS: the parts of a building that stand on themselves -- a tower
    # beside a cottage, a wing off a hall. A room's storey stands on its own
    # block's rooms below; a block's lower storeys carry its upper ones, so
    # the block is as wide as the widest storey it holds up. Rooms naming no
    # block are one block.
    block = {rid: str(by_id[rid].get("block") or "main").casefold() for rid in level_of}
    need = {}
    for rid, lv in level_of.items():
        key = (block[rid], lv)
        need[key] = need.get(key, 0) + room_target(by_id[rid], doors=len(by_id[rid].get("joins") or ()))
    carry_block = {}
    for b in set(block.values()):
        above = 0.0
        for lv in sorted((lv for lv in levels if lv >= first), reverse=True):
            n = need.get((b, lv), 0)
            if n and above > n:
                carry_block[(b, lv)] = above / n
            if n:
                above = max(above, n) * 1.15
    carry = {rid: carry_block.get((block[rid], lv), 1.0) for rid, lv in level_of.items()}
    wells, landings = {}, {}
    for lv in order:
        rooms = rooms_at[lv]
        if not rooms:
            continue
        ref = lv - 1 if lv > first else lv + 1
        support, below = {}, {}
        if lv != first and not layout.floors.get(ref):
            support = {r["id"]: set() for r in rooms}
        elif lv != first:
            whole = set()
            by_block = {}
            for rid, rs in layout.floors[ref].items():
                for r in rs:
                    whole |= r.cells()
                    by_block.setdefault(block[rid], set()).update(r.cells())
                below[rid] = rs[0]
            for r in rooms:
                support[r["id"]] = by_block.get(block[r["id"]]) or whole
        placed, cut = _place_storey(lv, rooms, by_id, stairs, dict(wells), below, support,
                                    outward if lv == 0 else {}, layout, carry)
        layout.floors[lv] = {rid: [r] for rid, r in placed.items()}
        for sid, (well, land) in cut.items():
            wells.setdefault(sid, well)
            landings.setdefault(sid, {})[lv] = land
    layout.blocks = {rid: block[rid] for rid in level_of}

    for st in stairs:
        sid = st["id"]
        lv_lo, lv_hi = level_of[st["low"]], level_of[st["high"]]
        if sid not in wells or set(landings.get(sid, {})) != {lv_lo, lv_hi}:
            layout.warnings.append(f"no stairwell for {st['name']} "
                                   f"({layout.names[st['low']]} up to {layout.names[st['high']]})")
            continue
        layout.stairwells.append({"id": sid, "from": st["from"], "to": st["to"],
                                  "low": st["low"], "high": st["high"],
                                  "levels": [lv_lo, lv_hi], "rect": wells[sid].as_dict(),
                                  "landings": {str(lv): r.as_dict() for lv, r in landings[sid].items()},
                                  "name": st["name"], "at": st["at"]})

    def wells_on(lv):
        out = set()
        for s in layout.stairwells:
            if lv in s["levels"]:
                out |= Rect(**s["rect"]).cells()
        return out

    for lv, parts in layout.floors.items():
        _doors(lv, rooms_at[lv], parts, layout, wells_on(lv))

    base = {rid: rs[0] for rid, rs in layout.floors.get(0, {}).items()}
    layout.grounds = _grounds(grounds, base, by_id, layout)
    _doors(0, grounds + list(rooms_at.get(0, ())), {**layout.floors.get(0, {}), **layout.grounds},
           layout, wells_on(0))

    # FIXTURES last: never on a stairwell, a landing or a doorway's step, and
    # never cutting a room's doors and landings off from each other.
    for lv, parts in layout.floors.items():
        solid = wells_on(lv)
        for rid, rects in parts.items():
            cells = set()
            for r in rects:
                cells |= r.cells()
            clear = set()
            for dr in layout.doors:
                if dr["level"] != lv or rid not in (dr["a"], dr["b"]):
                    continue
                x, y = dr["cell"]
                dx, dy = _STEP.get(dr["side"], (0, 0))
                clear |= {c for c in ((x, y), (x + dx, y + dy)) if c in cells}
            for s in layout.stairwells:
                land = s["landings"].get(str(lv))
                if land:
                    clear |= Rect(**land).cells() & cells
            _place_fixtures(rid, by_id[rid], rects, layout, solid=solid & cells,
                            clear=clear, required=clear)
    for gid, rects in layout.grounds.items():
        _place_fixtures(gid, by_id[gid], rects, layout)
    return layout
