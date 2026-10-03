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
this module is the solver. Three things Holodeck did not do are done here:
room size from what the room holds, floors stacked inside the floor below,
and stairs that are a real stairwell occupying the same cells on both floors.

THE SPEC (what the model writes; every coordinate is the solver's):

    {"name": str,
     "floors": [{"level": int, "rooms": [ROOM, ...]}, ...],
     "grounds": [ROOM, ...],                    # outdoors, never stacked
     "stairs": [{"id", "from", "to", "side"?}]} # rooms on adjacent levels

    ROOM = {"id", "name", "purpose", "size"?, "smaller_than"?: room_id,
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
import random
from dataclasses import dataclass, field
from typing import Optional

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

#: Floor area range (square paces) by what a room is for, and the share of
#: it a room keeps clear to walk in. A room's size comes from what it holds
#: and this range -- never from a word the model guessed.
PURPOSE_AREA = {
    "entryway": (6, 16), "hallway": (8, 40), "corridor": (8, 60), "stair": (4, 10),
    "bedroom": (12, 36), "guest_room": (12, 30), "living": (24, 80), "hall": (30, 120),
    "kitchen": (12, 36), "dining": (16, 50), "bath": (6, 20), "washroom": (6, 20),
    "toilet": (3, 6), "storage": (3, 16), "closet": (2, 8), "study": (10, 28),
    "workshop": (16, 50), "cellar": (16, 80), "basement": (20, 100), "attic": (16, 70),
    "shrine": (10, 40), "meditation": (10, 30), "common_room": (40, 120),
    "office": (10, 30), "cell": (6, 14), "garden": (60, 400), "courtyard": (40, 300),
    "path": (12, 120), "yard": (40, 300), "other": (10, 40),
}
CLEARANCE_SHARE = 0.55
_SIDES = ("n", "e", "s", "w")
_OPP = {"n": "s", "s": "n", "e": "w", "w": "e"}


# ---------------------------------------------------------------- geometry

@dataclass
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

    def as_dict(self):
        return {"x": self.x, "y": self.y, "w": self.w, "d": self.d}


@dataclass
class Layout:
    name: str
    floors: dict = field(default_factory=dict)      # level -> {room_id: Rect}
    grounds: dict = field(default_factory=dict)     # room_id: Rect (level 0, outdoors)
    doors: list = field(default_factory=list)       # {a, b, level, cells, kind, side}
    stairwells: list = field(default_factory=list)  # {id, from, to, levels, rect}
    fixtures: dict = field(default_factory=dict)    # room_id -> [{id, name, kind, rect, height}]
    unplaced: list = field(default_factory=list)    # {room, fixture, why}
    warnings: list = field(default_factory=list)
    names: dict = field(default_factory=dict)
    purposes: dict = field(default_factory=dict)

    def as_dict(self):
        return {
            "name": self.name,
            "floors": {str(lv): {rid: [p.as_dict() for p in parts] for rid, parts in rooms.items()}
                       for lv, rooms in sorted(self.floors.items())},
            "grounds": {rid: [p.as_dict() for p in parts] for rid, parts in self.grounds.items()},
            "footprint": getattr(self, "footprint", None),
            "doors": self.doors, "stairwells": self.stairwells,
            "fixtures": {rid: [dict(f, rect=f["rect"].as_dict()) for f in fx]
                         for rid, fx in self.fixtures.items()},
            "unplaced": self.unplaced, "warnings": self.warnings,
            "names": self.names, "purposes": self.purposes,
        }


# ------------------------------------------------------------ room sizing

def fixture_footprint(fx):
    kind = str(fx.get("kind") or "").strip().casefold().replace(" ", "_")
    if kind in FIXTURE_SIZES:
        return FIXTURE_SIZES[kind]
    word = str(fx.get("size") or "medium").casefold()
    return SIZE_WORD_FOOTPRINT.get(word, SIZE_WORD_FOOTPRINT["medium"])


def _purpose_key(room):
    text = " ".join(str(room.get(k) or "") for k in ("purpose", "name", "id")).casefold()
    for key in PURPOSE_AREA:
        if key.replace("_", " ") in text or key in text:
            return key
    return "other"


def room_size(room, *, stair_cells=0):
    """(w, d) in paces from what the room holds: its fixtures' footprints over
    the share it keeps clear, inside the range its purpose allows."""
    lo, hi = PURPOSE_AREA[_purpose_key(room)]
    furniture = sum(w * d for w, d, _h in (fixture_footprint(f) for f in room.get("fixtures") or ()))
    area = max(lo, min(hi, (furniture + stair_cells) / (1.0 - CLEARANCE_SHARE)))
    hint = str(room.get("size") or "").casefold()
    area *= {"tiny": 0.7, "small": 0.85, "large": 1.25, "huge": 1.5}.get(hint, 1.0)
    area = max(lo, min(hi * 1.2, area))
    long_side = max((w for w, _d, _h in (fixture_footprint(f) for f in room.get("fixtures") or ())),
                    default=2)
    if _purpose_key(room) in ("hallway", "corridor", "path"):
        d = 3 if _purpose_key(room) != "path" else 4
        return max(4, round(area / d)), d
    w = max(long_side + 1, round(math.sqrt(area * 1.25)))
    d = max(2, round(area / w))
    return w, d


# ------------------------------------------------------------ floor layout
#
# ONE FOOTPRINT, EVERY STOREY. A building is laid out from the outside in:
# its footprint is sized to the storey that needs the most floor, and each
# storey partitions that same footprint (a storey under the roof a smaller one
# centred in it). A stair is a WELL -- the same cells on both storeys it joins,
# cut into a strip along the side the spec names -- so a body climbs through a
# real place and arrives above where it started. The rest of a storey is cut
# by recursive slicing in an order that keeps joined rooms beside each other
# (squarified-treemap floor plans, after Marson & Musse 2010).

def _slice(rect: Rect, items, out, rng=None):
    """Partition `rect` among `items` [(room_id, area)] in order, by halving
    the list near its area midpoint and cutting the longer side to match --
    with `rng`, a split point among the near-balanced ones and, for a
    near-square piece, either cut, so a search can try many."""
    if not items:
        return
    if len(items) == 1:
        out[items[0][0]] = [rect]
        return
    total = sum(a for _r, a in items) or 1.0
    shares, acc = [], 0.0
    for k in range(1, len(items)):
        acc += items[k - 1][1]
        shares.append((k, acc / total))
    near = [k for k, sh in shares if 0.3 <= sh <= 0.7] or \
        [min(shares, key=lambda t: abs(t[1] - 0.5))[0]]
    k = rng.choice(near) if rng else min(near, key=lambda kk: abs(dict(shares)[kk] - 0.5))
    first, rest = items[:k], items[k:]
    share = sum(a for _r, a in first) / total
    across = rect.w >= rect.d
    if rng and 0.67 <= rect.w / max(1, rect.d) <= 1.5:
        across = rng.random() < 0.5
    if across:
        cut = max(1, min(rect.w - 1, round(rect.w * share)))
        _slice(Rect(rect.x, rect.y, cut, rect.d), first, out, rng)
        _slice(Rect(rect.x + cut, rect.y, rect.w - cut, rect.d), rest, out, rng)
    else:
        cut = max(1, min(rect.d - 1, round(rect.d * share)))
        _slice(Rect(rect.x, rect.y, rect.w, cut), first, out, rng)
        _slice(Rect(rect.x, rect.y + cut, rect.w, rect.d - cut), rest, out, rng)


def _join_order(rooms, start, rng=None):
    """Rooms in breadth-first order of their joins from `start`, so a room
    is sliced next to the one it joins; unjoined rooms last."""
    by_id = {r["id"]: r for r in rooms}
    adj = {rid: [] for rid in by_id}
    for r in rooms:
        for j in r.get("joins") or ():
            if j.get("to") in by_id:
                adj[r["id"]].append(j["to"])
                adj[j["to"]].append(r["id"])
    seen, order, queue = set(), [], [start] if start in by_id else []
    while queue:
        rid = queue.pop(0)
        if rid in seen:
            continue
        seen.add(rid)
        order.append(rid)
        nxt = list(adj[rid])
        if rng:
            rng.shuffle(nxt)
        queue.extend(nxt)
    return order + [rid for rid in by_id if rid not in seen]


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


def _walls_between(parts_a, parts_b):
    best = (None, [])
    for a in parts_a:
        for b in parts_b:
            side, cells = _shared_wall(a, b)
            if len(cells) > len(best[1]):
                best = (side, cells)
    return best


def _strip(foot: Rect, side, depth=2):
    """(strip along `side` of the footprint, the rest)."""
    if side == "n":
        return Rect(foot.x, foot.y, foot.w, depth), Rect(foot.x, foot.y + depth, foot.w, foot.d - depth)
    if side == "s":
        return Rect(foot.x, foot.y + foot.d - depth, foot.w, depth), Rect(foot.x, foot.y, foot.w, foot.d - depth)
    if side == "w":
        return Rect(foot.x, foot.y, depth, foot.d), Rect(foot.x + depth, foot.y, foot.w - depth, foot.d)
    return Rect(foot.x + foot.w - depth, foot.y, depth, foot.d), Rect(foot.x, foot.y, foot.w - depth, foot.d)


def _strip_parts(strip: Rect, well: Rect):
    """The strip less the well, as up to two rects."""
    parts = []
    if strip.w >= strip.d:
        if well.x > strip.x:
            parts.append(Rect(strip.x, strip.y, well.x - strip.x, strip.d))
        if well.x + well.w < strip.x + strip.w:
            parts.append(Rect(well.x + well.w, strip.y, strip.x + strip.w - well.x - well.w, strip.d))
    else:
        if well.y > strip.y:
            parts.append(Rect(strip.x, strip.y, strip.w, well.y - strip.y))
        if well.y + well.d < strip.y + strip.d:
            parts.append(Rect(strip.x, well.y + well.d, strip.w, strip.y + strip.d - well.y - well.d))
    return parts


def _doors(level, rooms, parts, layout):
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
            side, cells = _walls_between(parts[r["id"]], parts[to])
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


def _place_fixtures(room_id, room, parts, layout, blocked=()):
    """Fixtures by relation (Holodeck's split), backtracking: hard -- inside
    the room's cells, no overlap, clear of doors and the stairwell, against
    the wall it names; soft -- near / beside / facing the fixture named. A
    fixture no cell takes is reported, never silently dropped."""
    cells = set()
    for r in parts:
        cells |= r.cells()
    if not cells:
        return
    fixtures = sorted(room.get("fixtures") or (),
                      key=lambda f: -(fixture_footprint(f)[0] * fixture_footprint(f)[1]))
    occupied = set(blocked)
    placed = {}
    xs = [c[0] for c in cells]; ys = [c[1] for c in cells]
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
                    rc = r.cells()
                    if not rc <= cells:
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

    budget = [3000]
    moved = []

    def go(i):
        if i == len(fixtures):
            return True
        budget[0] -= 1
        if budget[0] < 0:
            return False
        fx = fixtures[i]
        cands = [r for r in candidates(fx) if not (r.cells() & occupied)]
        if not cands and fx.get("at"):
            # A real designer moves it to another wall, then anywhere it fits.
            loose = dict(fx)
            for alt in [sd for sd in _SIDES if sd != fx.get("at")] + [None]:
                loose["at"] = alt
                cands = [r for r in candidates(loose) if not (r.cells() & occupied)]
                if cands:
                    moved.append((fx.get("name") or fx.get("id"), fx.get("at"), alt or "anywhere"))
                    break
        cands.sort(key=lambda r: -score(fx, r))
        for r in cands[:10]:
            placed[fx["id"]] = r
            occupied.update(r.cells())
            if go(i + 1):
                return True
            occupied.difference_update(r.cells())
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


def _neighbour_rect(anchor: Rect, side, w, d, slide):
    if side == "n":
        return Rect(anchor.x + slide, anchor.y - d, w, d)
    if side == "s":
        return Rect(anchor.x + slide, anchor.y + anchor.d, w, d)
    if side == "e":
        return Rect(anchor.x + anchor.w, anchor.y + slide, w, d)
    return Rect(anchor.x - w, anchor.y + slide, w, d)


def _mirror(rect: Rect, frame: Rect, fx: bool, fy: bool) -> Rect:
    x = frame.x + frame.w - (rect.x - frame.x) - rect.w if fx else rect.x
    y = frame.y + frame.d - (rect.y - frame.y) - rect.d if fy else rect.y
    return Rect(x, y, rect.w, rect.d)


def _partition_score(parts, rooms, stair_room, strip_bits, outward=(), storey=None):
    """Lower is better: a stair room cut off from its stairwell, a join with
    no shared wall, a join on the wrong side, a room that opens on the
    grounds with no outside wall, and thin rooms."""
    score = 0.0
    if storey is not None:
        for rid in outward:
            if rid in parts and not any(
                    p.x == storey.x or p.y == storey.y or p.x + p.w == storey.x + storey.w
                    or p.y + p.d == storey.y + storey.d for p in parts[rid]):
                score += 15
    # the stair room must reach its WELLS -- the strip's leftover is only floor
    for owner, _bits, wells in strip_bits:
        if owner in parts and wells and not _walls_between(parts[owner], wells)[1]:
            score += 100
    # floor nobody was given is a hole in the building
    if storey is not None:
        covered = set()
        for rects in parts.values():
            for p in rects:
                covered |= p.cells()
        for _o, _b, wells in strip_bits:
            for w in wells:
                covered |= w.cells()
        score += 0.5 * max(0, storey.w * storey.d - len(covered & storey.cells()))
    for r in rooms:
        for j in r.get("joins") or ():
            to = j.get("to")
            if r["id"] in parts and to in parts:
                side, cells = _walls_between(parts[r["id"]], parts[to])
                if not cells:
                    score += 20
                elif str(j.get("side") or "")[:1] in _SIDES and side != str(j["side"])[:1]:
                    score += 6
    for rects in parts.values():
        for p in rects:
            score += max(0.0, max(p.w, p.d) / max(1, min(p.w, p.d)) - 2.5)
    return score


def _spine_partitions(main: Rect, rooms, sizes):
    """A HALLWAY THROUGH THE STOREY: for each hallway-like room joined to
    two or more rooms, a corridor two paces wide down the long axis of the
    storey, with the rooms it joins sliced on either side -- a room asked on
    one side on that side, the rest where the area balances."""
    out = []
    for hub in rooms:
        if _purpose_key(hub) not in ("hallway", "corridor") or \
                sum(j.get("to") in {r["id"] for r in rooms} for j in hub.get("joins") or ()) < 2:
            continue
        here = {r["id"] for r in rooms}
        asked = [str(j.get("side") or "")[:1] for j in hub.get("joins") or () if j.get("to") in here]
        ns, ew = sum(a in "ns" for a in asked if a), sum(a in "ew" for a in asked if a)
        # The corridor runs ALONG the walls its rooms open from: rooms asked
        # north and south of it make it run east-west, east and west north-south.
        horizontal = ns > ew if ns != ew else main.w >= main.d
        width = 2 if min(main.w, main.d) <= 9 else 3
        if horizontal:
            off = (main.d - width) // 2
            spine = Rect(main.x, main.y + off, main.w, width)
            halves = {"n": Rect(main.x, main.y, main.w, off),
                      "s": Rect(main.x, spine.y + width, main.w, main.d - off - width)}
        else:
            off = (main.w - width) // 2
            spine = Rect(main.x + off, main.y, width, main.d)
            halves = {"w": Rect(main.x, main.y, off, main.d),
                      "e": Rect(spine.x + width, main.y, main.w - off - width, main.d)}
        keys = list(halves)
        side_of = {}
        for j in hub.get("joins") or ():
            asked = str(j.get("side") or "")[:1]
            if asked in keys:
                side_of[j.get("to")] = (asked, int(j.get("order") or 0))
        groups = {k: [] for k in keys}
        others = [r["id"] for r in rooms if r["id"] != hub["id"]]
        one_side = {side_of[r][0] for r in others if r in side_of}
        if len(one_side) == 1 and all(r in side_of for r in others):
            # A CORRIDOR WITH ROOMS ON ONE SIDE runs along the building's
            # edge, the rooms filling the rest: no dead half.
            only = one_side.pop()
            if horizontal:
                spine = Rect(main.x, main.y + (main.d - width if only == "n" else 0), main.w, width)
                halves = {only: Rect(main.x, main.y + (width if only == "s" else 0), main.w, main.d - width)}
            else:
                spine = Rect(main.x + (main.w - width if only == "w" else 0), main.y, width, main.d)
                halves = {only: Rect(main.x + (width if only == "e" else 0), main.y, main.w - width, main.d)}
            keys = [only]
            groups = {only: []}
        for rid in sorted(others, key=lambda r: side_of.get(r, ("", 0))[1]):
            if rid in side_of:
                groups[side_of[rid][0]].append(rid)
        for rid in others:
            if rid not in side_of:
                light = min(keys, key=lambda k: sum(sizes[x][0] * sizes[x][1] for x in groups[k]))
                groups[light].append(rid)
        parts = {hub["id"]: [spine]}
        for k in keys:
            if groups[k] and halves[k].w > 0 and halves[k].d > 0:
                # rooms along a corridor sit side by side: cut across it only
                total = sum(sizes[r][0] * sizes[r][1] for r in groups[k]) or 1.0
                h = halves[k]
                cursor = h.x if horizontal else h.y
                for i, rid in enumerate(groups[k]):
                    share = sizes[rid][0] * sizes[rid][1] / total
                    if horizontal:
                        w = (h.x + h.w - cursor) if i == len(groups[k]) - 1 else max(2, round(h.w * share))
                        parts[rid] = [Rect(cursor, h.y, w, h.d)]
                        cursor += w
                    else:
                        d = (h.y + h.d - cursor) if i == len(groups[k]) - 1 else max(2, round(h.d * share))
                        parts[rid] = [Rect(h.x, cursor, h.w, d)]
                        cursor += d
        out.append(parts)
    return out


def _best_partition(main: Rect, rooms, sizes, stair_room, strip_bits, outward=(), storey=None,
                    trials=400, seed=0):
    """Try orders from each room (the stair room alone when there is one),
    forward and reversed, mirrored each way, and a corridor spine where a
    hallway joins several rooms; keep the best-scoring cut."""
    starts = [stair_room] if stair_room else [r["id"] for r in rooms]
    best, best_score = None, float("inf")
    for spine in _spine_partitions(main, rooms, sizes):
        for fx in (False, True):
            for fy in (False, True):
                parts = {rid: [_mirror(p, main, fx, fy) for p in rects] for rid, rects in spine.items()}
                trial = {rid: list(rects) for rid, rects in parts.items()}
                for owner, bits, _wells in strip_bits:
                    if owner in trial:
                        trial[owner] = trial[owner] + bits
                sc = _partition_score(trial, rooms, stair_room, strip_bits, outward, storey)
                if sc < best_score:
                    best, best_score = parts, sc
    for start in starts:
        base = _join_order(rooms, start)
        for order in (base, list(reversed(base))):
            raw = {}
            _slice(main, [(rid, float(sizes[rid][0] * sizes[rid][1])) for rid in order], raw)
            for fx in (False, True):
                for fy in (False, True):
                    parts = {rid: [_mirror(p, main, fx, fy) for p in rects] for rid, rects in raw.items()}
                    trial = {rid: list(rects) for rid, rects in parts.items()}
                    for owner, bits, _wells in strip_bits:
                        if owner in trial:
                            trial[owner] = trial[owner] + bits
                    sc = _partition_score(trial, rooms, stair_room, strip_bits, outward, storey)
                    if sc < best_score:
                        best, best_score = parts, sc
    # A SEARCH, seeded so a layout is reproducible: many orders, split
    # points and cuts, each scored the same way.
    rng = random.Random(seed)
    ids = [r["id"] for r in rooms]
    for _t in range(trials):
        start = stair_room or rng.choice(ids)
        order = _join_order(rooms, start, rng)
        if rng.random() < 0.5:
            order = list(reversed(order))
        raw = {}
        _slice(main, [(rid, float(sizes[rid][0] * sizes[rid][1])) for rid in order], raw, rng)
        fx, fy = rng.random() < 0.5, rng.random() < 0.5
        parts = {rid: [_mirror(p, main, fx, fy) for p in rects] for rid, rects in raw.items()}
        trial = {rid: list(rects) for rid, rects in parts.items()}
        for owner, bits, _wells in strip_bits:
            if owner in trial:
                trial[owner] = trial[owner] + bits
        sc = _partition_score(trial, rooms, stair_room, strip_bits, outward, storey)
        if sc < best_score:
            best, best_score = parts, sc
    return best or {}


# ---------------------------------------------------------------- solve

def solve(spec) -> Layout:
    layout = Layout(name=str(spec.get("name") or "building"))
    floors = sorted(spec.get("floors") or [], key=lambda f: int(f.get("level") or 0))
    rooms_at = {int(f.get("level") or 0): list(f.get("rooms") or ()) for f in floors}
    all_rooms = {r["id"]: r for rs in rooms_at.values() for r in rs}
    level_of = {r["id"]: lv for lv, rs in rooms_at.items() for r in rs}
    grounds = [g for g in spec.get("grounds") or () if isinstance(g, dict) and g.get("id")]
    ground_ids = {g["id"] for g in grounds}
    for r in list(all_rooms.values()) + grounds:
        layout.names[r["id"]] = r.get("name") or r["id"]
        layout.purposes[r["id"]] = _purpose_key(r)
    if not all_rooms:
        layout.warnings.append("no storey holds a room")
        return layout

    # THE FOOTPRINT: the storey that needs the most floor sizes the building.
    need = {lv: sum(room_size(r)[0] * room_size(r)[1] for r in rs) + 8
            for lv, rs in rooms_at.items() if rs}
    area = max(need.values())
    W = max(6, round(math.sqrt(area * 1.4)))
    D = max(5, math.ceil(area / W))
    foot = Rect(0, 0, W, D)
    under_roof = {lv for lv, rs in rooms_at.items()
                  if any(r.get("smaller_than") or _purpose_key(r) == "attic" for r in rs)}

    # THE STAIRWELLS: one per stair, the same cells on both storeys it joins.
    # Each cuts a strip along the side it names; a second well on a side
    # already cut sits further along the same strip.
    stairs = [dict(st) for st in spec.get("stairs") or ()
              if isinstance(st, dict) and st.get("from") in level_of and st.get("to") in level_of]
    wells_on_level = {}    # level -> [well rects] cut through that storey
    per_level = {}         # level -> [(side, well, owner_room)]
    for st in stairs:
        a, b = st["from"], st["to"]
        side = str(st.get("side") or "n").casefold()[:1]
        side = side if side in _SIDES else "n"
        strip, _rest = _strip(foot, side)
        ww, dd = (3, 2) if side in "ns" else (2, 3)
        levels = (level_of[a], level_of[b])
        taken = [w for lv in levels for w in wells_on_level.get(lv, ())]
        slots = ([Rect(strip.x + x, strip.y, ww, dd) for x in range(0, strip.w - ww + 1, ww + 1)]
                 if side in "ns" else
                 [Rect(strip.x, strip.y + y, ww, dd) for y in range(0, strip.d - dd + 1, dd + 1)])
        mid = (len(slots) - 1) // 2
        slots = [r for _i, r in sorted(enumerate(slots), key=lambda t: abs(t[0] - mid))]
        well = next((r for r in slots if all(not r.overlaps(t) for t in taken)), None)
        if well is None:
            layout.warnings.append(f"no room for a stairwell {a} -> {b} on the {side} side")
            continue
        for lv in levels:
            wells_on_level.setdefault(lv, []).append(well)
        for room_id in (a, b):
            per_level.setdefault(level_of[room_id], []).append((side, well, room_id))
        layout.stairwells.append({"id": st.get("id") or f"{a}-{b}", "from": a, "to": b,
                                  "levels": sorted({level_of[a], level_of[b]}),
                                  "rect": well.as_dict(), "name": st.get("name") or "stair",
                                  "side": side})

    def clip(r: Rect, to: Rect):
        x0, y0 = max(r.x, to.x), max(r.y, to.y)
        x1, y1 = min(r.x + r.w, to.x + to.w), min(r.y + r.d, to.y + to.d)
        return Rect(x0, y0, x1 - x0, y1 - y0) if x1 > x0 and y1 > y0 else None

    for lv, rooms in sorted(rooms_at.items()):
        if not rooms:
            continue
        storey = Rect(foot.x + 1, foot.y + 1, foot.w - 2, foot.d - 2) if lv in under_roof and lv != 0 \
            else Rect(foot.x, foot.y, foot.w, foot.d)
        main = storey
        strip_bits = []    # (owner room, strip part rects)
        for side in dict.fromkeys(sd for sd, _w, _o in per_level.get(lv, ())):
            strip, main = _strip(main, side)
            strip = clip(strip, storey)
            wells = [w for sd, w, _o in per_level[lv] if sd == side]
            owner = next(o for sd, _w, o in per_level[lv] if sd == side)
            rest = [strip] if strip else []
            for w in wells:
                nxt = []
                for piece in rest:
                    if piece.overlaps(w):
                        nxt.extend(_strip_parts(piece, w))
                    else:
                        nxt.append(piece)
                rest = nxt
            strip_bits.append((owner, rest, wells))
        stair_room = next((o for _sd, _w, o in per_level.get(lv, ())), None)
        sizes = {r["id"]: room_size(r) for r in rooms}
        outward = {r["id"] for r in rooms
                   if any(j.get("to") in ground_ids for j in r.get("joins") or ())} | \
            {j.get("to") for g in grounds for j in g.get("joins") or () if j.get("to") in level_of}
        parts = _best_partition(main, rooms, sizes, stair_room, strip_bits, outward, storey)
        for owner, bits, _wells in strip_bits:
            if owner in parts:
                parts[owner] = parts[owner] + bits
        layout.floors[lv] = parts
        _doors(lv, rooms, parts, layout)
        for r in rooms:
            if r["id"] not in parts:
                layout.warnings.append(f"{layout.names[r['id']]} found no floor on storey {lv}")

    # GROUNDS: outdoors around the building, each placed once what it joins
    # stands -- against the joined room's OWN outside wall, the side the
    # spec asks first, then any side where that room meets the outside.
    base = layout.floors.get(0) or next(iter(layout.floors.values()))
    occupied = [foot]
    ground_parts = {}

    def joined_sides(g):
        """[(anchor id, side this ground stands on)] for what it joins."""
        out = []
        for j in g.get("joins") or ():
            to = j.get("to")
            asked = str(j.get("side") or "")[:1]
            out.append((to, _OPP.get(asked)))
        for r in rooms_at.get(0, ()) + grounds:
            for j in r.get("joins") or ():
                if j.get("to") == g["id"]:
                    asked = str(j.get("side") or "")[:1]
                    out.append((r["id"], asked if asked in _SIDES else None))
        return out

    pending = list(grounds)
    for _round in range(len(grounds) + 1):
        progress = False
        for g in list(pending):
            links = [(to, sd) for to, sd in joined_sides(g) if to in base or to in ground_parts]
            if not links:
                continue
            w, d = room_size(g)
            spot = None
            for to, sd in links:
                rects = base.get(to) or ground_parts.get(to) or []
                for anchor in rects:
                    for side in ([sd] if sd in _SIDES else []) + [x for x in _SIDES if x != sd]:
                        along = anchor.w if side in "ns" else anchor.d
                        for ww, dd in ((w, d), (d, w)):
                            own = ww if side in "ns" else dd
                            for slide in sorted(range(-(own - 1), along),
                                                key=lambda v: abs(v - (along - own) // 2)):
                                r = _neighbour_rect(anchor, side, ww, dd, slide)
                                if all(not r.overlaps(o) for o in occupied):
                                    spot = r
                                    break
                            if spot:
                                break
                        if spot:
                            break
                    if spot:
                        break
                if spot:
                    break
            pending.remove(g)
            progress = True
            if spot is None:
                layout.warnings.append(f"{layout.names[g['id']]} found no ground beside what it joins")
                continue
            ground_parts[g["id"]] = [spot]
            occupied.append(spot)
        if not progress:
            break
    for g in pending:
        layout.warnings.append(f"{layout.names[g['id']]} joins nothing that stands")
    layout.grounds = ground_parts
    _doors(0, grounds + list(rooms_at.get(0, ())), {**base, **ground_parts}, layout)

    # FIXTURES last, clear of doorways and stairwells.
    for lv, parts in layout.floors.items():
        for rid, rects in parts.items():
            blocked = set()
            for dr in layout.doors:
                if dr["level"] == lv and rid in (dr["a"], dr["b"]):
                    # the doorway's cell and the step inside it stay clear
                    x, y = dr["cell"]
                    step = {"n": (0, 1), "s": (0, -1), "e": (-1, 0), "w": (1, 0)}.get(dr["side"], (0, 0))
                    for cx, cy in ((x, y), (x + step[0], y + step[1]), (x - step[0], y - step[1])):
                        blocked.add((cx, cy))
            for s in layout.stairwells:
                if lv in s["levels"]:
                    blocked |= Rect(**s["rect"]).cells()
            _place_fixtures(rid, all_rooms[rid], rects, layout, blocked)
    for g in grounds:
        if g["id"] in ground_parts:
            _place_fixtures(g["id"], g, ground_parts[g["id"]], layout)
    layout.footprint = foot.as_dict()
    return layout
