# spatial_fov.py
"""Within-room geometry and occlusion, derived and never stored.

A room is a small grid sized from its `size` tier. Its anchors are placed on
that grid from their compass bearing with a seed keyed on (room, anchor), so a
later anchor never moves an earlier one. A body's cell is derived from its
station (`at` an anchor, `near` another body) and is never written anywhere.
From those two derivations a recursive shadowcast answers, per observer, which
features and bodies a line of sight reaches, at what egocentric sector, at
what within-room tier, and behind what.

Pure, total, no I/O, no model -- the same shape as `agents/perception`, and
for the same reason: the Director cannot argue with a line, and a mind cannot
be handed a body its eyes have no line to.

THE LAYER MAY ONLY SUBTRACT ON EVIDENCE IT HAS. That is the whole contract,
and it is stated as data rather than as a rule a caller has to remember:
every answer carries a `basis`.

  * The CONE needs a facing. No facing -> no cone -> every feature of the room
    is in view, exactly as today.
  * OCCLUSION between two bodies needs BOTH bodies to hold a measured station
    (`at`, or a `near` link), the same evidence bar `measured_proximity_rel`
    already applies to proximity: a body with no station is somewhere in the
    room, and "somewhere" is not behind the counter.
  * Occlusion of a FEATURE needs the observer to hold a measured station.
  * A room with no anchors has nothing to occlude with, and a room whose
    anchors carry no `height` occludes with nothing (the default height is
    `floor`, which blocks no line).

Measured before this was written (2026-09-02, 104 live scenes): 796 of 827
anchors carry a bearing, 145 of 243 occupied rooms carry anchors, 212 of 785
positioned bodies resolve a facing and 86 hold a station -- so the cone bites
on roughly a quarter of views today and body occlusion on about a tenth, and
both only grow as the Director writes stations.

Schema, additive and optional, on each room anchor beside `desc` and `dir`:

    footprint   point | small | large | run     how many cells it takes
    height      floor | waist | head | full     what it blocks a line at
    opacity     opaque | see_through            whether it blocks sight at all

Three closed sets the ENGINE owns and can enumerate -- a schema, not a
vocabulary table (CLAUDE.md's distinction). Unknown values fall to the
default that subtracts least.
"""

from __future__ import annotations

import hashlib
import math
from typing import Optional

from world.spatial_barriers import _SIGHT_BARRIERS, normalize_barrier
from world.spatial_geometry import (
    effective_anchors,
    effective_facing,
    effective_room_size,
    effective_station,
    proximity_rel,
)
from world.spatial_identity import _ci_get, room_of
from world.spatial_orientation import (
    _BEARINGS,
    _LEFT_SECTORS,
    _RIGHT_SECTORS,
    normalize_bearing,
    opposite_bearing,
    relative_bearing,
)


# ---------------------------------------------------------------------------
# The closed vocabularies
# ---------------------------------------------------------------------------

FOOTPRINTS = ("point", "small", "large", "run")
DEFAULT_FOOTPRINT = "point"

HEIGHTS = ("floor", "waist", "head", "full")
DEFAULT_HEIGHT = "floor"
_HEIGHT_RANK = {"floor": 0.0, "waist": 1.0, "head": 2.0, "full": 3.0}

OPACITIES = ("opaque", "see_through")
DEFAULT_OPACITY = "opaque"

#: Cells per side, by room size tier. One cell is roughly a pace; a `vast`
#: hall at twelve paces is coarse on purpose (the metric-space note's test:
#: model only what changes the fiction, and a pace is that grain).
GRID_SIDE = {"tiny": 3, "small": 4, "medium": 6, "large": 8, "huge": 10,
             "vast": 12}

#: Eye height, and equally the top of the body, by the body's own posture.
#: The vocabulary is `world/comfort`'s -- the one place the engine already
#: reads a posture token -- with `crouching` added because it is the posture
#: this layer exists for. Unknown -> standing: the tallest eye sees most and
#: the tallest body is most visible, which is the direction that subtracts
#: least.
_EYE_RANK = {"standing": 2.0, "sitting": 1.5, "kneeling": 1.5,
             "crouching": 1.0, "lying": 0.5}
_POSTURE_TOKENS = {
    "standing": "standing", "stands": "standing", "upright": "standing",
    "sitting": "sitting", "seated": "sitting", "sits": "sitting",
    "kneeling": "kneeling", "kneels": "kneeling",
    "crouching": "crouching", "crouched": "crouching", "squatting":
    "crouching", "ducking": "crouching", "ducked": "crouching",
    "lying": "lying", "prone": "lying", "supine": "lying", "lies": "lying",
    "sprawled": "lying",
}

#: The egocentric sectors sight reaches: full in front, an impression to the
#: side, nothing behind. `_REAR_SECTORS` in `spatial_geometry` is the same
#: rear arc; the peripheral band is this module's addition.
_FRONT_SECTORS = frozenset({"ahead", "ahead_left", "ahead_right"})
_SIDE_SECTORS = frozenset({"left", "right"})

_UNIT = {"n": (0, -1), "ne": (1, -1), "e": (1, 0), "se": (1, 1),
         "s": (0, 1), "sw": (-1, 1), "w": (-1, 0), "nw": (-1, -1)}


def normalize_footprint(value) -> str:
    v = str(value or "").strip().casefold()
    return v if v in FOOTPRINTS else DEFAULT_FOOTPRINT


def normalize_height(value) -> str:
    v = str(value or "").strip().casefold()
    return v if v in HEIGHTS else DEFAULT_HEIGHT


def normalize_opacity(value) -> str:
    v = str(value or "").strip().casefold().replace("-", "_")
    return v if v in OPACITIES else DEFAULT_OPACITY


def anchor_geometry(anchor: dict) -> dict:
    """One anchor's geometry fields, normalized to the closed sets."""
    anchor = anchor if isinstance(anchor, dict) else {}
    return {
        "footprint": normalize_footprint(anchor.get("footprint")),
        "height": normalize_height(anchor.get("height")),
        "opacity": normalize_opacity(anchor.get("opacity")),
    }


def height_rank(height) -> float:
    return _HEIGHT_RANK.get(normalize_height(height), 0.0)


_GEOMETRY_KEYS = ("footprint", "height", "opacity")


def room_has_geometry(scene: dict, room_id) -> bool:
    """Has anyone authored geometry on this room's anchors at all?

    The opt-in for the per-observer furniture sentence: a room whose anchors
    carry only `desc` and `dir` was composed one way for every story before
    this layer existed, and keeps composing that way byte for byte. A room
    that says how tall its counter is has asked to be seen from somewhere.
    """
    room = ((scene or {}).get("rooms") or {}).get(room_id)
    if not isinstance(room, dict):
        return False
    for anchor in (room.get("anchors") or {}).values():
        if isinstance(anchor, dict) and any(
                str(anchor.get(k) or "").strip() for k in _GEOMETRY_KEYS):
            return True
    return False


def _tokens(text):
    import re
    return [t for t in re.split(r"[^a-z]+", str(text or "").casefold()) if t]


def posture_class(scene: dict, name: str) -> str:
    """standing | sitting | kneeling | crouching | lying, from the body's
    own pose record, then its entity state -- exact tokens, never prose."""
    poses = (scene or {}).get("poses") or {}
    pose = _ci_get(poses, name) if isinstance(poses, dict) else None
    fields = []
    if isinstance(pose, dict):
        fields.append(pose.get("posture"))
    entities = (scene or {}).get("entities") or {}
    ent = _ci_get(entities, name) if isinstance(entities, dict) else None
    if isinstance(ent, dict):
        state = ent.get("state") if isinstance(ent.get("state"), dict) else {}
        fields.extend([state.get("posture"), state.get("position")])
    for field in fields:
        for token in _tokens(field):
            if token in _POSTURE_TOKENS:
                return _POSTURE_TOKENS[token]
    return "standing"


def eye_rank(scene: dict, name: str) -> float:
    return _EYE_RANK.get(posture_class(scene, name), 2.0)


# ---------------------------------------------------------------------------
# Placement
# ---------------------------------------------------------------------------

def grid_side(scene: dict, room_id) -> int:
    size = effective_room_size(scene, room_id)
    return GRID_SIDE.get(size, GRID_SIDE["medium"])


def _seed(*parts) -> int:
    joined = "\x1f".join(str(p) for p in parts)
    return int(hashlib.sha1(joined.encode("utf-8")).hexdigest()[:8], 16)


def _wall_cells(side: int, bearing: str, offset: int, length: int) -> list:
    """`length` cells along the wall `bearing` names, starting at `offset`
    (wrapped), or the corner cell for a diagonal bearing."""
    last = side - 1
    if bearing in ("ne", "se", "sw", "nw"):
        x = last if bearing in ("ne", "se") else 0
        y = 0 if bearing in ("ne", "nw") else last
        return [(x, y)]
    cells = []
    for i in range(length):
        k = (offset + i) % side
        if bearing == "n":
            cells.append((k, 0))
        elif bearing == "s":
            cells.append((k, last))
        elif bearing == "e":
            cells.append((last, k))
        else:
            cells.append((0, k))
    return cells


def _inward(bearing: str) -> tuple:
    """The unit step from a wall toward the room's centre."""
    dx, dy = _UNIT.get(opposite_bearing(bearing) or "s", (0, 1))
    return dx, dy


def anchor_cells(scene: dict, room_id) -> dict:
    """{anchor_id: {cells: [(x,y)...], height, opacity, footprint, dir,
    desc, implicit}} for every effective anchor of the room.

    Placement depends on (room, anchor id, bearing, footprint) and nothing
    else, so adding or removing any other anchor leaves this one where it
    was. Two anchors may share a cell; the cell then blocks at the taller.

    Memoised on the room's own inputs (its size, its anchors, its edges from
    both sides), because one perception pass asks for the same room once
    per observer per pair; the derivation is pure, so a cache keyed on
    everything it reads cannot go stale.
    """
    side = grid_side(scene, room_id)
    anchors = effective_anchors(scene, room_id)
    import json as _json
    key = _json.dumps([str(room_id), side, anchors], sort_keys=True,
                      default=str)
    cached = _ANCHOR_CACHE.get(key)
    if cached is not None:
        return {aid: dict(rec, cells=list(rec["cells"]))
                for aid, rec in cached.items()}
    out = _place_anchors(room_id, side, anchors)
    if len(_ANCHOR_CACHE) >= _ANCHOR_CACHE_MAX:
        _ANCHOR_CACHE.clear()
    _ANCHOR_CACHE[key] = out
    return {aid: dict(rec, cells=list(rec["cells"])) for aid, rec in out.items()}


_ANCHOR_CACHE: dict = {}
_ANCHOR_CACHE_MAX = 256


def _place_anchors(room_id, side, anchors) -> dict:
    out = {}
    for aid, anchor in anchors.items():
        if not isinstance(anchor, dict):
            continue
        geo = anchor_geometry(anchor)
        bearing = normalize_bearing(anchor.get("dir"))
        seed = _seed(room_id, aid)
        fp = geo["footprint"]
        if bearing:
            length = {"point": 1, "small": 2, "large": 2,
                      "run": max(2, side - 2)}[fp]
            offset = 1 + seed % max(1, side - 2 - (length - 1)) \
                if side > 2 else 0
            cells = _wall_cells(side, bearing, offset, length)
            # A THING stands one pace off its wall -- a counter, a table, a
            # screen, anything with a height -- leaving the lane a body
            # takes COVER in (`stations.cover`). A door, a window or a
            # hearth, which has no height of its own, is the wall itself.
            standing_thing = geo["height"] != DEFAULT_HEIGHT \
                or fp in ("run", "large")
            if standing_thing and bearing in _UNIT and side > 3:
                dx, dy = _inward(bearing)
                cells = [(x + dx, y + dy) for x, y in cells]
            if fp == "large" and bearing in _UNIT and cells:
                dx, dy = _inward(bearing)
                cells = cells + [(x + dx, y + dy) for x, y in cells
                                 if 0 <= x + dx < side and 0 <= y + dy < side]
        else:
            inner = max(1, side - 2)
            x = 1 + seed % inner
            y = 1 + (seed // 7) % inner
            cells = [(x, y)]
            if fp in ("small", "run"):
                cells.append((min(side - 1, x + 1), y))
            elif fp == "large":
                cells += [(min(side - 1, x + 1), y), (x, min(side - 1, y + 1)),
                          (min(side - 1, x + 1), min(side - 1, y + 1))]
        out[aid] = {
            "cells": sorted(set(cells)),
            "height": geo["height"],
            "opacity": geo["opacity"],
            "footprint": fp,
            "dir": bearing,
            "desc": str(anchor.get("desc") or aid),
            "implicit": bool(anchor.get("implicit")),
        }
    return out


def _centre(side: int) -> tuple:
    return (side // 2, side // 2)


def _takes_cover(station: dict, anchor_id) -> bool:
    """Does this station put its body on the far side of `anchor_id`?
    `cover` is either the anchor's id or a bare true against `at`."""
    cover = (station or {}).get("cover")
    if cover in (True, 1):
        return True
    return bool(cover) and str(cover).strip().casefold() == str(
        anchor_id or "").strip().casefold()


def _has_measured_station(scene: dict, name: str) -> bool:
    st = effective_station(scene, name)
    return bool(st.get("at")) or bool(st.get("near"))


def body_cell(scene: dict, name: str, _seen=None) -> Optional[tuple]:
    """The cell a body stands in, derived from its station, or None when
    the station is unmeasured. `at` an anchor: one step inward from the
    anchor's first cell. `near` another body: beside that body's cell.
    Never stored."""
    room_id = room_of(scene, name)
    if not room_id:
        return None
    side = grid_side(scene, room_id)
    st = effective_station(scene, name)
    at = st.get("at")
    if at:
        placed = anchor_cells(scene, room_id).get(at)
        if placed and placed["cells"]:
            # Two bodies at one anchor stand beside each other along it,
            # not in each other: each takes a cell of the anchor's extent
            # by its own seed, so a long bar seats several.
            cells = placed["cells"]
            x, y = cells[_seed(room_id, at, str(name).casefold()) % len(cells)]
            bearing = placed.get("dir")
            if bearing:
                dx, dy = _inward(bearing)
            else:
                cx0, cy0 = _centre(side)
                dx = (1 if cx0 > x else -1) if cx0 != x else 0
                dy = (1 if cy0 > y else -1) if cy0 != y else 0
                if dx and dy:
                    dy = 0
                if not dx and not dy:
                    dx = 1
            # `cover`: the body is on the FAR side of its anchor -- between
            # a counter and the wall, on the blind side of a screen -- so
            # the anchor stands between it and the room. Declared by the
            # station's owner, never inferred from prose.
            if _takes_cover(st, at):
                dx, dy = -dx, -dy
            # The preferred side first, then round the anchor, so a body
            # never stands IN the feature it is stationed at.
            for ddx, ddy in ((dx, dy), (-dx, -dy), (dy, dx), (-dy, -dx)):
                cx = x + ddx
                cy = y + ddy
                if 0 <= cx < side and 0 <= cy < side \
                        and (cx, cy) not in cells:
                    return (cx, cy)
            return (x, y)
    _seen = set(_seen or ())
    for other in st.get("near") or []:
        key = str(other).casefold()
        if key in _seen:
            continue
        cell = body_cell(scene, other, _seen | {str(name).casefold()})
        if cell:
            x, y = cell
            k = _seed(room_id, str(name).casefold(), key) % 4
            dx, dy = ((1, 0), (-1, 0), (0, 1), (0, -1))[k]
            return (min(max(x + dx, 0), side - 1),
                    min(max(y + dy, 0), side - 1))
    return None


def _observer_cell(scene: dict, name: str) -> tuple:
    """A body's cell, or the room's centre when unmeasured -- the same
    approximation `_relative_sector` makes for an observer near centre."""
    cell = body_cell(scene, name)
    if cell:
        return cell, "measured"
    room_id = room_of(scene, name)
    return _centre(grid_side(scene, room_id) if room_id else 6), "centre"


# ---------------------------------------------------------------------------
# Lines
# ---------------------------------------------------------------------------

def bearing_between(a: tuple, b: tuple) -> Optional[str]:
    """Compass bearing from cell a to cell b; None when they coincide."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    if dx == 0 and dy == 0:
        return None
    angle = math.degrees(math.atan2(dx, -dy)) % 360
    return _BEARINGS[int(round(angle / 45.0)) % 8]


def _blocks(cell_height: float, eye: float, top: float) -> bool:
    """Does an occluder of this height cut the line from an eye at `eye`
    to a target whose top is `top`? It cuts when it is level with the eye
    (you cannot see over it) or level with the target's top (the target is
    below it)."""
    return cell_height >= eye or cell_height >= top


def _line(a: tuple, b: tuple) -> list:
    """Supercover cells strictly between a and b: every cell the straight
    segment touches, so a line cannot slip between two occluders that meet
    at a corner (a plain Bresenham walk does exactly that)."""
    x0, y0 = a
    x1, y1 = b
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    sx = 1 if x1 > x0 else -1
    sy = 1 if y1 > y0 else -1
    err = dx - dy
    x, y = x0, y0
    out = []
    while (x, y) != (x1, y1):
        e2 = 2 * err
        moved_x = moved_y = False
        if e2 > -dy:
            err -= dy
            x += sx
            moved_x = True
        if e2 < dx:
            err += dx
            y += sy
            moved_y = True
        if moved_x and moved_y:
            for corner in ((x - sx, y), (x, y - sy)):
                if corner not in (a, b) and corner not in out:
                    out.append(corner)
        if (x, y) != (x1, y1):
            out.append((x, y))
    return out


def shadowcast(origin: tuple, radius: int, blocked) -> set:
    """Recursive shadowcasting over eight octants.

    `blocked(x, y)` answers whether a cell stops the line. Returns every
    cell the origin can see, the origin included. Cells outside the shape
    are the caller's business: `blocked` should answer True for them.
    """
    ox, oy = origin
    visible = {origin}
    mult = ((1, 0, 0, 1), (0, 1, 1, 0), (0, -1, 1, 0), (-1, 0, 0, 1),
            (-1, 0, 0, -1), (0, -1, -1, 0), (0, 1, -1, 0), (1, 0, 0, -1))

    def cast(row, start, end, xx, xy, yx, yy):
        if start < end:
            return
        for j in range(row, radius + 1):
            dx, dy = -j - 1, -j
            blocked_prev = False
            new_start = start
            while dx <= 0:
                dx += 1
                X = ox + dx * xx + dy * xy
                Y = oy + dx * yx + dy * yy
                l_slope = (dx - 0.5) / (dy + 0.5)
                r_slope = (dx + 0.5) / (dy - 0.5)
                if start < r_slope:
                    continue
                if end > l_slope:
                    break
                if dx * dx + dy * dy <= radius * radius + radius:
                    visible.add((X, Y))
                if blocked_prev:
                    if blocked(X, Y):
                        new_start = r_slope
                        continue
                    blocked_prev = False
                    start = new_start
                elif blocked(X, Y) and j < radius:
                    blocked_prev = True
                    cast(j + 1, start, l_slope, xx, xy, yx, yy)
                    new_start = r_slope
            if blocked_prev:
                break

    for xx, xy, yx, yy in mult:
        cast(1, 1.0, 0.0, xx, xy, yx, yy)
    return visible


# ---------------------------------------------------------------------------
# The composite: this room, and what an open doorway shows of the next
# ---------------------------------------------------------------------------

class _Field:
    """One observer's field: cells, occluder heights, and which room each
    cell belongs to, in a shared coordinate frame."""

    def __init__(self):
        self.inside = {}        # (x, y) -> room_id
        self.height = {}        # (x, y) -> occluder rank (opaque only)
        self.occluder = {}      # (x, y) -> anchor id of the tallest opaque
        self.offsets = {}       # room_id -> (ox, oy)
        self.anchors = {}       # room_id -> anchor_cells()

    def add_room(self, scene, room_id, offset):
        ox, oy = offset
        side = grid_side(scene, room_id)
        self.offsets[room_id] = offset
        for x in range(side):
            for y in range(side):
                self.inside[(x + ox, y + oy)] = room_id
        placed = anchor_cells(scene, room_id)
        self.anchors[room_id] = placed
        for aid, rec in placed.items():
            if rec["opacity"] != "opaque" or rec["implicit"]:
                continue
            rank = height_rank(rec["height"])
            for x, y in rec["cells"]:
                cell = (x + ox, y + oy)
                if rank > self.height.get(cell, -1.0):
                    self.height[cell] = rank
                    self.occluder[cell] = aid

    def cell_of(self, room_id, cell):
        ox, oy = self.offsets.get(room_id, (0, 0))
        return (cell[0] + ox, cell[1] + oy)


def _door_cell(scene, room_id, neighbour_id):
    from world.spatial_geometry import door_anchor_id
    placed = anchor_cells(scene, room_id).get(door_anchor_id(neighbour_id))
    if not placed or not placed["cells"] or not placed.get("dir"):
        return None, None
    return placed["cells"][0], placed["dir"]


def _sight_neighbours(scene, room_id):
    """Rooms an open sightline joins to this one, with the edge bearing."""
    from world.spatial_barriers import effective_adjacent
    out = []
    for edge in effective_adjacent(scene, room_id):
        if not isinstance(edge, dict) or not edge.get("to"):
            continue
        if normalize_barrier(edge.get("barrier")) not in _SIGHT_BARRIERS:
            continue
        if normalize_barrier(edge.get("barrier")) in ("window", "bars",
                                                      "one_way_window"):
            # Sight passes, but a grille or glass is not a doorway a grid
            # can be walked into; those stay with `visual_level_between`.
            continue
        bearing = normalize_bearing(edge.get("dir"))
        if bearing and edge.get("to") in (scene.get("rooms") or {}):
            out.append((str(edge["to"]), bearing))
    return out


def observer_field(scene: dict, observer: str) -> Optional[_Field]:
    """The composite field an observer's sight runs over: their own room,
    plus every neighbour an open doorway with a bearing casts into, placed
    beyond a one-cell wall band with the two door cells aligned."""
    room_id = room_of(scene, observer)
    if not room_id:
        return None
    field = _Field()
    field.add_room(scene, room_id, (0, 0))
    field.doors = {}
    for other, bearing in _sight_neighbours(scene, room_id):
        d1, b1 = _door_cell(scene, room_id, other)
        d2, _b2 = _door_cell(scene, other, room_id)
        if not d1 or not d2:
            continue
        ux, uy = _UNIT[b1]
        band = (d1[0] + ux, d1[1] + uy)
        anchor_far = (band[0] + ux, band[1] + uy)
        offset = (anchor_far[0] - d2[0], anchor_far[1] - d2[1])
        if any(cell in field.inside for cell in (
                (x + offset[0], y + offset[1])
                for x in range(grid_side(scene, other))
                for y in range(grid_side(scene, other)))):
            continue                        # two doorways on one wall overlap
        field.add_room(scene, other, offset)
        field.inside[band] = room_id        # the doorway itself
        field.doors[other] = band
    return field


# ---------------------------------------------------------------------------
# Answers
# ---------------------------------------------------------------------------

def _cone_sector(facing, origin, target):
    bearing = bearing_between(origin, target)
    if not bearing or not facing:
        return None
    return relative_bearing(facing, bearing)


def _sector_verdict(sector) -> str:
    """front | side | rear | unknown for one egocentric sector."""
    if sector is None:
        return "unknown"
    if sector in _FRONT_SECTORS:
        return "front"
    if sector in _SIDE_SECTORS:
        return "side"
    return "rear"


def _side_label(sector):
    if sector in _LEFT_SECTORS:
        return "left"
    if sector in _RIGHT_SECTORS:
        return "right"
    return None


def _visible_set(field, origin, eye, top):
    side_max = max(max(abs(x - origin[0]), abs(y - origin[1]))
                   for x, y in field.inside) if field.inside else 0

    def blocked(x, y):
        if (x, y) not in field.inside:
            return True
        h = field.height.get((x, y))
        return h is not None and _blocks(h, eye, top)
    return shadowcast(origin, side_max + 1, blocked)


def _occluders_on(field, origin, target, eye, top):
    """(blocking anchor id or None, tallest non-blocking anchor height rank)
    along the straight line between two cells."""
    tallest = -1.0
    tallest_id = None
    for cell in _line(origin, target):
        if cell not in field.inside:
            return "__wall__", tallest, tallest_id
        h = field.height.get(cell)
        if h is None:
            continue
        if _blocks(h, eye, top):
            return field.occluder.get(cell), tallest, tallest_id
        if h > tallest:
            tallest, tallest_id = h, field.occluder.get(cell)
    return None, tallest, tallest_id


def _tier(scene, observer, target):
    return proximity_rel(scene, observer, target)


def feature_visibility(scene: dict, observer: str, *, sweep=False) -> list:
    """Every anchor of the observer's room, as the observer's eyes have it.

    Returns rows sorted near-to-far:
      {anchor, desc, implicit, visible (bool), sector, side, tier,
       occluded_by (desc or None), basis}

    `basis` names the evidence the answer stands on -- "cone" when a facing
    subtracted, "line" when the observer's measured cell and an opaque
    anchor did, "open" when nothing could. A `sweep` (a deliberate look
    around) ignores the facing: the observer turns to see the whole room.
    """
    room_id = room_of(scene, observer)
    if not room_id:
        return []
    field = observer_field(scene, observer)
    origin, how = _observer_cell(scene, observer)
    facing = None if sweep else effective_facing(scene, observer)
    eye = eye_rank(scene, observer)
    placed = field.anchors.get(room_id) or {}
    rows = []
    for aid, rec in placed.items():
        cells = rec["cells"]
        if not cells:
            continue
        target = min(cells, key=lambda c: (c[0] - origin[0]) ** 2
                     + (c[1] - origin[1]) ** 2)
        dist = math.hypot(target[0] - origin[0], target[1] - origin[1])
        sector = _cone_sector(facing, origin, target) if facing else None
        verdict = _sector_verdict(sector)
        visible = True
        basis = "open"
        occluded_by = None
        if facing and verdict == "rear" and dist > 1.5:
            visible = False
            basis = "cone"
        elif how == "measured" and dist > 1.0:
            top = height_rank(rec["height"])
            blocker, _t, _tid = _occluders_on(
                field, origin, target, eye, max(top, 0.5))
            if blocker and blocker != aid:
                visible = False
                basis = "line"
                occluded_by = (placed.get(blocker) or {}).get("desc") \
                    if blocker != "__wall__" else None
        rows.append({
            "anchor": aid, "desc": rec["desc"], "implicit": rec["implicit"],
            "visible": visible, "sector": sector,
            "peripheral": bool(facing) and verdict == "side",
            "side": _side_label(sector),
            "tier": ("within_reach" if dist <= 1.5 else
                     "near" if dist <= max(2.5, grid_side(scene, room_id) / 2.0)
                     else "across"),
            "occluded_by": occluded_by, "basis": basis, "distance": dist,
        })
    rows.sort(key=lambda r: (r["distance"], r["anchor"]))
    return rows


def body_visibility(scene: dict, observer: str, target: str) -> dict:
    """How one body's line reaches another, or does not.

    {visible: bool, fraction: 0.0|0.5|1.0, sector, side, tier, occluded_by,
     hidden_below (height word or None), through (neighbour room id when
     seen through its doorway), basis}

    Subtracts ONLY when both bodies hold a measured station (`basis`
    "line"); otherwise `visible` is True with basis "open" and the caller
    keeps every verdict it had. The rear arc is NOT decided here --
    `entity_arc` owns it and `presence_percepts` already asks it.
    """
    open_answer = {"visible": True, "fraction": 1.0, "sector": None,
                   "side": None, "tier": _tier(scene, observer, target),
                   "occluded_by": None, "hidden_below": None,
                   "through": None, "basis": "open"}
    o_room = room_of(scene, observer)
    t_room = room_of(scene, target)
    if not o_room or not t_room:
        return open_answer
    if not (_has_measured_station(scene, observer)
            and _has_measured_station(scene, target)):
        return open_answer
    field = observer_field(scene, observer)
    if t_room != o_room and t_room not in field.offsets:
        return open_answer                 # no doorway casts that far
    o_cell = body_cell(scene, observer)
    t_cell = body_cell(scene, target)
    if not o_cell or not t_cell:
        return open_answer
    origin = field.cell_of(o_room, o_cell)
    goal = field.cell_of(t_room, t_cell)
    eye = eye_rank(scene, observer)
    top = eye_rank(scene, target)
    facing = effective_facing(scene, observer)
    sector = _cone_sector(facing, origin, goal) if facing else None
    if origin == goal:
        return {**open_answer, "basis": "line", "sector": sector,
                "side": _side_label(sector)}
    seen = _visible_set(field, origin, eye, top)
    blocker, tallest, tallest_id = _occluders_on(field, origin, goal, eye, top)
    visible = goal in seen and blocker is None
    if not visible and blocker is None:
        # The shadowcast closed the line at a corner the straight walk
        # slipped past; name the tallest thing the walk did touch.
        blocker = tallest_id or "__wall__"
    hidden_below = None
    if visible and tallest >= _HEIGHT_RANK["waist"] and top > tallest:
        hidden_below = "waist" if tallest < _HEIGHT_RANK["head"] else "head"
    placed = field.anchors.get(o_room, {})
    placed_t = field.anchors.get(t_room, {})
    occluder_desc = None
    if not visible:
        rec = placed.get(blocker) or placed_t.get(blocker) or {}
        occluder_desc = rec.get("desc") or (None if blocker in (None, "__wall__")
                                            else str(blocker))
    elif hidden_below and tallest_id:
        rec = placed.get(tallest_id) or placed_t.get(tallest_id) or {}
        occluder_desc = rec.get("desc") or str(tallest_id)
    return {
        "visible": visible,
        "fraction": 1.0 if visible and not hidden_below else (
            0.5 if visible else 0.0),
        "sector": sector, "side": _side_label(sector),
        "tier": _tier(scene, observer, target),
        "occluded_by": occluder_desc,
        "hidden_below": hidden_below,
        "through": t_room if t_room != o_room else None,
        "basis": "line",
    }


def cover_between(scene: dict, a: str, b: str) -> Optional[str]:
    """The feature that hides body `b` from body `a`, by its description,
    or None when the line is open or unmeasured."""
    rec = body_visibility(scene, a, b)
    return rec["occluded_by"] if not rec["visible"] else None


def sight_digest(scene: dict, names) -> dict:
    """The Director's deterministic spatial digest: who can see whom, what
    is within reach of whom, and what cover stands between named parties.

    Names only -- this is an objective-causality surface, so no identity
    gate applies, and no prose. Every answer is one the layer could stand
    on: a pair with no measured station reads as `open`, never as hidden.
    """
    names = [str(n) for n in (names or []) if str(n or "").strip()]
    sees = {}
    hidden = []
    cover = []
    reach = {}
    for a in names:
        room = room_of(scene, a)
        if not room:
            continue
        seen = []
        near = []
        for b in names:
            if a == b or room_of(scene, b) is None:
                continue
            rec = body_visibility(scene, a, b)
            if rec["basis"] != "line":
                if room_of(scene, b) == room:
                    seen.append(b)
                continue
            if rec["visible"]:
                seen.append(b)
                if rec["hidden_below"]:
                    cover.append({"observer": a, "subject": b,
                                  "behind": rec["occluded_by"],
                                  "shows": f"{rec['hidden_below']} up"})
            else:
                hidden.append({"observer": a, "subject": b,
                               "behind": rec["occluded_by"] or "the wall"})
            if rec["tier"] == "within_reach":
                near.append(b)
        sees[a] = seen
        if near:
            reach[a] = near
    return {"sees": sees, "hidden": hidden, "cover": cover,
            "within_reach": reach}
