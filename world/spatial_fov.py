# spatial_fov.py
"""Within-room geometry and occlusion, derived and never stored.

A room is a small grid: the square its `size` tier gives it, or -- when the
room declares an `extent` in paces and a `shape` -- the cells of that shape
within that box (`room_grid`; `docs/design/DESIGN_ROOM_FIDELITY.md`). Its
anchors are placed on the wall their compass bearing names, along that wall's
own length, with a seed keyed on (room, anchor), so a later anchor never
moves an earlier one. A body's cell is derived from its
station (`at` an anchor, `near` another body) and is never written anywhere.
From those two derivations a recursive shadowcast answers, per observer, which
features and bodies a line of sight reaches, at what egocentric sector, at
what within-room tier, and behind what. An open doorway with a bearing lays
the neighbour's grid beyond this one; the wall between them is a LINE, and the
doorway a gap in it, so a line into the next room is judged where it crosses
the wall rather than by which cells it touches there (`_wall_verdict`).

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
    _TIER_SIDE,
    effective_anchors,
    effective_facing,
    effective_room_size,
    effective_station,
    normalize_cell,
    normalize_extent,
    normalize_offset,
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

#: Cells per side, by room size tier, for a room with no `extent`. One cell is
#: roughly a pace; a `vast` hall at twelve paces is coarse on purpose (the
#: metric-space note's test: model only what changes the fiction, and a pace
#: is that grain). The ONE statement of the table is `spatial_geometry._TIER_SIDE`,
#: because `size_from_extent` there needs it too; this is that table under the
#: name the geometry note gave it.
GRID_SIDE = dict(_TIER_SIDE)

#: The shapes a room may declare (`docs/design/DESIGN_ROOM_FIDELITY.md` §2).
#: A closed set the ENGINE owns and enumerates: `rectangle` is the bounding
#: box itself; `round` keeps the cells within the inscribed ellipse; `l` and
#: `composite` are the union of the rectangles `parts` places within the box
#: -- `l` the two-part case the 2026-09-04 prototype named, kept readable
#: exactly as it was, `composite` any number of parts (a T, a U, a cross, a
#: room with a bay; the owner, trying the map editor the same day: "the room
#: editor doesn't cover the multi room shape design"). Unknown -> rectangle,
#: the shape that subtracts no cell.
SHAPES = ("rectangle", "round", "l", "composite")
DEFAULT_SHAPE = "rectangle"

#: The shapes whose cells are the union of their `parts`.
_PART_SHAPES = ("l", "composite")

#: Where a part may sit by a WORD: the four corners of the bounding box, as
#: the bearing words the rest of the engine already reads. A part may instead
#: sit at a room-local origin `at: [x, y]` -- the `cell` convention stations
#: and anchors use: two whole numbers, the west-most, north-most cell of the
#: part (`normalize_cell`). Owner-visible.
ROOM_CORNERS = ("ne", "se", "sw", "nw")

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
    if not isinstance(room, dict) or not isinstance(room.get("anchors"), dict):
        return False
    for anchor in room["anchors"].values():
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

def normalize_shape(value) -> str:
    v = str(value or "").strip().casefold()
    return v if v in SHAPES else DEFAULT_SHAPE


def normalize_part_at(value):
    """Where a part sits: a corner word of `ROOM_CORNERS`, or a room-local
    origin cell `[x, y]` as `normalize_cell` reads one (two whole numbers,
    the part's west-most, north-most cell). None for anything else -- a
    bearing that is not a corner, prose, one number."""
    if isinstance(value, str):
        at = normalize_bearing(value)
        return at if at in ROOM_CORNERS else None
    cell = normalize_cell(value)
    return [cell[0], cell[1]] if cell is not None else None


def normalize_parts(value) -> list:
    """The readable parts of an `l` or a `composite`, each `{w, d, at}` with
    both sides in paces (`normalize_extent`'s clamp) and `at` a corner word
    or an origin cell (`normalize_part_at`). A part with no place or no
    readable extent is dropped, not guessed at. An `l`'s corner parts read
    exactly as they did before `composite` existed."""
    if not isinstance(value, (list, tuple)):
        return []
    out = []
    for part in value:
        if not isinstance(part, dict):
            continue
        at = normalize_part_at(part.get("at"))
        extent = normalize_extent(part)
        if at is not None and extent:
            out.append({"w": extent["w"], "d": extent["d"], "at": at})
    return out


def part_box(part, w, d):
    """One part's rectangle within a `w` x `d` bounding box, as
    `(x0, y0, x1, y1)` half-open, clipped to the box. A corner part is laid
    into its corner (the arithmetic the `l` prototype wrote, byte for
    byte); a cell part is laid east and south from its origin. A part the
    box holds nothing of is an empty rectangle, not an error -- the route
    refuses one fresh, the reader fails open on one the extent has since
    shrunk out from under."""
    at = part["at"]
    if isinstance(at, str):
        pw, pd = min(part["w"], w), min(part["d"], d)
        x0 = w - pw if at in ("ne", "se") else 0
        y0 = d - pd if at in ("se", "sw") else 0
        return (x0, y0, x0 + pw, y0 + pd)
    x0, y0 = int(at[0]), int(at[1])
    return (max(0, x0), max(0, y0), max(0, min(w, x0 + part["w"])),
            max(0, min(d, y0 + part["d"])))


def parts_box(parts) -> tuple:
    """The bounding box the parts need when the room declares no `extent`:
    the widest by the deepest for corner parts, the far edge of the
    farthest-laid for cell parts -- `(w, d)`, each within the extent clamp.
    An `l` of two corner parts gets exactly the box it always did."""
    from world.spatial_geometry import EXTENT_MAX_PACES, EXTENT_MIN_PACES
    w = d = 0
    for part in parts:
        at = part["at"]
        if isinstance(at, str):
            w, d = max(w, part["w"]), max(d, part["d"])
        else:
            w = max(w, max(0, int(at[0])) + part["w"])
            d = max(d, max(0, int(at[1])) + part["d"])
    clamp = lambda n: int(min(EXTENT_MAX_PACES, max(EXTENT_MIN_PACES, n)))
    return clamp(w), clamp(d)


class RoomGrid:
    """One room's cells: a `w` x `d` bounding box in paces and the set of
    cells the shape keeps of it. Rectangle: every cell. Round: the cells
    whose centres lie within the inscribed ellipse. L: the union of the
    `parts`, each a rectangle placed at a corner of the box.

    A room with no `extent` is the square its size tier gives it, so `w ==
    d == GRID_SIDE[tier]` and every arithmetic below reduces to the form the
    geometry note wrote (`test_room_shapes.py` pins the reduction byte for
    byte). Derived, never stored.
    """

    __slots__ = ("w", "d", "shape", "parts", "cells", "measured")

    def __init__(self, w, d, shape=DEFAULT_SHAPE, parts=(), measured=False):
        self.w = int(w)
        self.d = int(d)
        self.shape = normalize_shape(shape)
        self.parts = list(parts or ())
        self.measured = bool(measured)
        self.cells = _shape_cells(self.shape, self.w, self.d, self.parts)

    @property
    def side(self) -> int:
        """The characteristic length: the longer side."""
        return max(self.w, self.d)

    def key(self):
        return (self.shape, self.w, self.d,
                tuple((p["w"], p["d"],
                       p["at"] if isinstance(p["at"], str) else tuple(p["at"]))
                      for p in self.parts))

    def contains(self, cell) -> bool:
        return tuple(cell) in self.cells

    def centre(self) -> tuple:
        return self.nearest((self.w // 2, self.d // 2))

    def nearest(self, cell) -> tuple:
        """The cell itself when the shape holds it, else the nearest cell it
        does (ties to the smaller coordinates, so a reroll agrees)."""
        cell = (int(cell[0]), int(cell[1]))
        if cell in self.cells:
            return cell
        return min(self.cells, key=lambda c: (
            (c[0] - cell[0]) ** 2 + (c[1] - cell[1]) ** 2, c))

    def rim(self, bearing) -> list:
        """The cells that ARE the wall the bearing names -- inside the shape
        with their neighbour in that direction outside -- ordered along the
        wall (west to east for a north or south wall, north to south for an
        east or west one). For a rectangle this is exactly the row or column
        the geometry note placed anchors on; for a round room it is the arc
        facing that way; for an L it includes the inner wall of the notch,
        which faces that way too."""
        ux, uy = _UNIT[bearing]
        along = 0 if bearing in ("n", "s") else 1
        cells = [c for c in self.cells
                 if (c[0] + ux, c[1] + uy) not in self.cells]
        return sorted(cells, key=lambda c: (c[along], c[1 - along]))

    def corner(self, bearing) -> tuple:
        """The shape's extreme cell toward a diagonal bearing: the corner of
        a rectangle, the point of an arc, the outer corner of an L."""
        ux, uy = _UNIT[bearing]
        return max(self.cells, key=lambda c: (c[0] * ux + c[1] * uy,
                                              -c[0], -c[1]))


def _shape_cells(shape, w, d, parts) -> frozenset:
    box = frozenset((x, y) for x in range(w) for y in range(d))
    if shape == "round":
        rx, ry = w / 2.0, d / 2.0
        kept = frozenset(
            (x, y) for x, y in box
            if ((x + 0.5 - rx) / rx) ** 2 + ((y + 0.5 - ry) / ry) ** 2 <= 1.0)
        return kept or box
    if shape in _PART_SHAPES and parts:
        # THE UNION OF THE PARTS. An `l`'s two corner parts land on exactly
        # the cells the prototype's arithmetic gave them (`part_box` is that
        # arithmetic); a `composite` adds cell-placed parts and any count.
        # The notch -- every cell of the box no part covers -- is not the
        # room, so a line through it meets a wall.
        kept = set()
        for part in parts:
            x0, y0, x1, y1 = part_box(part, w, d)
            kept.update((x, y) for x in range(x0, x1) for y in range(y0, y1))
        return frozenset(kept) or box
    return box


def room_grid(scene: dict, room_id) -> RoomGrid:
    """The grid a room's geometry runs over. With an `extent`, the box it
    measures and the shape it declares; without one, the size tier's square
    -- the whole of what existed before extents, unchanged."""
    room = ((scene or {}).get("rooms") or {}).get(room_id)
    room = room if isinstance(room, dict) else {}
    extent = normalize_extent(room.get("extent"))
    shape = normalize_shape(room.get("shape"))
    parts = normalize_parts(room.get("parts")) if shape in _PART_SHAPES else []
    if extent:
        return RoomGrid(extent["w"], extent["d"], shape, parts, measured=True)
    if shape in _PART_SHAPES and parts:
        # A part-shape with no box is the box its parts need: the widest by
        # the deepest for corner parts (so one part spans the width and one
        # the depth), the farthest edge for cell parts.
        bw, bd = parts_box(parts)
        return RoomGrid(bw, bd, shape, parts, measured=True)
    side = GRID_SIDE.get(effective_room_size(scene, room_id),
                         GRID_SIDE["medium"])
    return RoomGrid(side, side, shape, parts)


def grid_side(scene: dict, room_id) -> int:
    """The room's characteristic length in cells: the tier's side for a room
    with no extent, the longer side of the box for one with."""
    return room_grid(scene, room_id).side


def _seed(*parts) -> int:
    joined = "\x1f".join(str(p) for p in parts)
    return int(hashlib.sha1(joined.encode("utf-8")).hexdigest()[:8], 16)


def _wall_cells(grid: RoomGrid, bearing: str, offset: int, length: int) -> list:
    """`length` cells along the wall `bearing` names, starting at `offset`
    (wrapped along the wall's own length), or the corner cell for a diagonal
    bearing."""
    if bearing in ROOM_CORNERS:
        return [grid.corner(bearing)]
    rim = grid.rim(bearing)
    if not rim:
        return [grid.centre()]
    return [rim[(offset + i) % len(rim)] for i in range(length)]


def _inward(bearing: str) -> tuple:
    """The unit step from a wall toward the room's centre."""
    dx, dy = _UNIT.get(opposite_bearing(bearing) or "s", (0, 1))
    return dx, dy


def anchor_cells(scene: dict, room_id) -> dict:
    """{anchor_id: {cells: [(x,y)...], height, opacity, footprint, dir,
    desc, implicit}} for every effective anchor of the room.

    Placement depends on (room, anchor id, bearing, footprint) and the
    room's grid, and nothing else, so adding or removing any other anchor
    leaves this one where it was. Two anchors may share a cell; the cell
    then blocks at the taller.

    Memoised on the room's own inputs (its grid, its anchors, its edges from
    both sides), because one perception pass asks for the same room once
    per observer per pair; the derivation is pure, so a cache keyed on
    everything it reads cannot go stale.
    """
    grid = room_grid(scene, room_id)
    anchors = effective_anchors(scene, room_id)
    import json as _json
    key = _json.dumps([str(room_id), grid.key(), anchors], sort_keys=True,
                      default=str)
    cached = _ANCHOR_CACHE.get(key)
    if cached is not None:
        return {aid: dict(rec, cells=list(rec["cells"]))
                for aid, rec in cached.items()}
    out = _place_anchors(room_id, grid, anchors)
    if len(_ANCHOR_CACHE) >= _ANCHOR_CACHE_MAX:
        _ANCHOR_CACHE.clear()
    _ANCHOR_CACHE[key] = out
    return {aid: dict(rec, cells=list(rec["cells"])) for aid, rec in out.items()}


_ANCHOR_CACHE: dict = {}
_ANCHOR_CACHE_MAX = 256


def _place_anchors(room_id, grid: RoomGrid, anchors) -> dict:
    out = {}
    for aid, anchor in anchors.items():
        if not isinstance(anchor, dict):
            continue
        geo = anchor_geometry(anchor)
        bearing = normalize_bearing(anchor.get("dir"))
        seed = _seed(room_id, aid)
        fp = geo["footprint"]
        pinned = normalize_cell(anchor.get("cell"))
        source = "seed"
        if pinned is not None:
            # An authored ORIGIN cell (the World Browser's map, 2026-09-04:
            # the owner could place an anchor anywhere only by taking it
            # off its wall, and asked for any cell). The origin is the
            # anchor's west-most, north-most cell; the footprint is laid
            # from it eastward, and for `large` southward too -- the
            # arrangement a free anchor's seed already uses -- clipped to
            # the room, so a two-cell thing on the east wall is one cell
            # rather than one outside. `dir` alongside is the wall it is
            # against, for prose, and moves nothing: no inset, no wall
            # cells. `offset` is a place along a wall and a cell is a
            # place, so a cell outranks it; the route keeps the two
            # exclusive. Snapped to the nearest cell when the extent or
            # shape has since moved out from under it.
            source = "cell"
            x, y = grid.nearest(pinned)
            cells = [(x, y)]
            more = []
            if fp in ("small", "run"):
                more = [(x + 1, y)]
            elif fp == "large":
                more = [(x + 1, y), (x, y + 1), (x + 1, y + 1)]
            cells += [c for c in more if grid.contains(c)]
        elif bearing:
            # The wall's OWN length, not the grid's side: on a wide room the
            # north anchor has the long wall to sit on and the east anchor
            # the short one. For a square the two are the same number.
            along = len(grid.rim(bearing)) if bearing in ("n", "s", "e", "w") \
                else grid.side
            length = {"point": 1, "small": 2, "large": 2,
                      "run": max(2, along - 2)}[fp]
            # A doorway's `width` in paces (the passage record's,
            # `DESIGN_ROOM_FIDELITY.md` §5, copied onto the implicit door
            # anchor by `effective_anchors`) is its aperture: that many
            # cells along the wall, never more than the wall has. Absent,
            # the footprint's table above, byte for byte.
            width = anchor.get("width")
            if anchor.get("implicit") and isinstance(width, (int, float)) \
                    and not isinstance(width, bool) and width >= 1:
                length = max(1, min(int(width), max(1, along)))
            placed_at = normalize_offset(anchor.get("offset"))
            if placed_at is not None and bearing not in ROOM_CORNERS:
                # An authored place along the wall: the fraction of the
                # positions the footprint leaves, from the wall's start
                # (`RoomGrid.rim`'s order), never wrapping. Absent, the
                # seeded placement below, byte for byte.
                room_for = max(0, along - length)
                offset = min(room_for, max(0, int(round(placed_at * room_for))))
                source = "offset"
            else:
                offset = 1 + seed % max(1, along - 2 - (length - 1)) \
                    if along > 2 else 0
            cells = _wall_cells(grid, bearing, offset, length)
            # A THING stands one pace off its wall -- a counter, a table, a
            # screen, anything with a height -- leaving the lane a body
            # takes COVER in (`stations.cover`). A door, a window or a
            # hearth, which has no height of its own, is the wall itself.
            standing_thing = geo["height"] != DEFAULT_HEIGHT \
                or fp in ("run", "large")
            if standing_thing and bearing in _UNIT and min(grid.w, grid.d) > 3:
                dx, dy = _inward(bearing)
                inset = [(x + dx, y + dy) for x, y in cells
                         if grid.contains((x + dx, y + dy))]
                cells = inset or cells
            if fp == "large" and bearing in _UNIT and cells:
                dx, dy = _inward(bearing)
                cells = cells + [(x + dx, y + dy) for x, y in cells
                                 if grid.contains((x + dx, y + dy))]
        else:
            x = 1 + seed % max(1, grid.w - 2)
            y = 1 + (seed // 7) % max(1, grid.d - 2)
            x, y = grid.nearest((x, y))
            cells = [(x, y)]
            more = []
            if fp in ("small", "run"):
                more = [(min(grid.w - 1, x + 1), y)]
            elif fp == "large":
                more = [(min(grid.w - 1, x + 1), y), (x, min(grid.d - 1, y + 1)),
                        (min(grid.w - 1, x + 1), min(grid.d - 1, y + 1))]
            cells += [c for c in more if grid.contains(c)]
        out[aid] = {
            "cells": sorted(set(cells)),
            "height": geo["height"],
            "opacity": geo["opacity"],
            "footprint": fp,
            "dir": bearing,
            "desc": str(anchor.get("desc") or aid),
            "implicit": bool(anchor.get("implicit")),
            "offset": normalize_offset(anchor.get("offset")),
            # The authored origin cell as read, and what placed the anchor:
            # "cell" (that origin), "offset" (a place along its wall), or
            # "seed" (the formula, byte for byte what it always was).
            "cell": [pinned[0], pinned[1]] if pinned is not None else None,
            "source": source,
        }
    return out


def _centre(side: int) -> tuple:
    """The centre of a square grid -- kept for the one caller with no room
    to ask (`_observer_cell` on a body in no room)."""
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
    """A station is measured when it says WHERE in the room: at an anchor,
    near a body, or -- since the map editor (2026-09-04) -- pinned to a
    cell. Sight and cover subtract only between two measured bodies."""
    st = effective_station(scene, name)
    return bool(st.get("at")) or bool(st.get("near")) \
        or normalize_cell(st.get("cell")) is not None


def body_cell_source(scene: dict, name: str) -> str:
    """Where a body's cell comes from, for the map: `"cell"` (an authored
    station `cell`, the owner's pin), `"anchor"` (derived from its station
    -- `at` an anchor, or `near` a body that has a cell, which bottoms out at
    an anchor or a pin), or `"none"` (no cell: somewhere in the room)."""
    if not room_of(scene, name):
        return "none"
    if normalize_cell(effective_station(scene, name).get("cell")) is not None:
        return "cell"
    return "anchor" if body_cell(scene, name) else "none"


def body_cell(scene: dict, name: str, _seen=None) -> Optional[tuple]:
    """The cell a body stands in, or None when the station is unmeasured.

    An authored station `cell` first (the World Browser's map, 2026-09-04:
    the owner could only drop a body on an anchor, and asked for any cell),
    snapped to the nearest cell the room still holds when its extent or
    shape has moved since (`RoomGrid.nearest`, ties to the smaller
    coordinates). A body with a `cell` and an `at` keeps `at` for prose --
    "at the hearth" -- and `cell` for geometry; the two are not checked
    against each other. Without one, derived: `at` an anchor is one step
    inward from the anchor's first cell; `near` another body is beside that
    body's cell. The derivation is never stored."""
    room_id = room_of(scene, name)
    if not room_id:
        return None
    grid = room_grid(scene, room_id)
    st = effective_station(scene, name)
    pinned = normalize_cell(st.get("cell"))
    if pinned is not None:
        return grid.nearest(pinned)
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
                cx0, cy0 = grid.centre()
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
                if grid.contains((cx, cy)) and (cx, cy) not in cells:
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
            return grid.nearest((min(max(x + dx, 0), grid.w - 1),
                                 min(max(y + dy, 0), grid.d - 1)))
    return None


def _observer_cell(scene: dict, name: str) -> tuple:
    """A body's cell, or the room's centre when unmeasured -- the same
    approximation `_relative_sector` makes for an observer near centre."""
    cell = body_cell(scene, name)
    if cell:
        return cell, "measured"
    room_id = room_of(scene, name)
    if not room_id:
        return _centre(6), "centre"
    return room_grid(scene, room_id).centre(), "centre"


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
    """The supercover of the segment between two cell centres: every cell
    the straight segment touches, strictly between a and b, in order.

    Cells are unit squares centred on integer coordinates, so the segment
    crosses an x-boundary at parameter (2i+1)/(2|dx|) and a y-boundary at
    (2j+1)/(2|dy|); the walk steps whichever comes first and, when the two
    coincide EXACTLY -- the segment passes through a corner -- takes both
    cells that meet there before the diagonal one. That corner rule is what
    stops sight slipping between two occluders that touch at a corner, and
    it is the whole of what a supercover adds to a plain Bresenham walk.

    The comparison is in integers, so "exactly" means exactly. The previous
    rasteriser here stepped diagonally whenever Bresenham did and then added
    BOTH corner cells every time, which is not a supercover but a superset
    of one: for a shallow line nearly every row change added a cell the
    segment never touched. Within a room that only ever over-blocked; at a
    doorway, one open cell in a wall, it put the wall into almost every
    off-axis line (2026-09-04, the cellar-and-stove case).
    """
    x0, y0 = a
    x1, y1 = b
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    if not dx and not dy:
        return []
    sx = 1 if x1 > x0 else -1
    sy = 1 if y1 > y0 else -1
    x, y = x0, y0
    i = j = 0                 # boundaries crossed on each axis so far
    out = []
    while (x, y) != (x1, y1):
        # next x-crossing at (2i+1)/(2dx), next y-crossing at (2j+1)/(2dy);
        # cross-multiplied so the tie is exact.
        tx = (2 * i + 1) * dy if dx else None
        ty = (2 * j + 1) * dx if dy else None
        if tx is not None and (ty is None or tx < ty):
            x += sx
            i += 1
        elif ty is not None and (tx is None or ty < tx):
            y += sy
            j += 1
        else:
            for corner in ((x + sx, y), (x, y + sy)):
                if corner not in (a, b) and corner not in out:
                    out.append(corner)
            x += sx
            y += sy
            i += 1
            j += 1
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
        # THE WALLS BETWEEN PLACED ROOMS, AS LINES. Each: {axis, coord,
        # extent, aperture, to}. The wall between this room and a neighbour
        # is the line `axis == coord` (axis 1 is a row, so a north or south
        # wall; axis 0 a column) over `extent`, the union of both rooms'
        # reach along it; `aperture` is the doorway's span on that line.
        # See `_wall_verdict`.
        self.walls = []

    def add_room(self, scene, room_id, offset):
        ox, oy = offset
        self.offsets[room_id] = offset
        # The SHAPE's cells, not the box: a round room's corners and an L's
        # notch are outside `inside`, so a line through them meets a wall.
        for x, y in room_grid(scene, room_id).cells:
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


def _door_cells(scene, room_id, neighbour_id):
    """(cells, bearing) of the room's doorway onto `neighbour_id`, or
    (None, None) when the door has no bearing to place it by. The cells are
    the door anchor's whole extent along its wall: the aperture is as wide
    as the doorway, one cell for the implicit door an edge contributes. An
    edge carrying `offset` puts the doorway there along its wall
    (`effective_anchors` copies it onto the implicit anchor, and
    `_place_anchors` reads it); without one the doorway sits at the seeded
    cell it always did."""
    from world.spatial_geometry import door_anchor_id
    placed = anchor_cells(scene, room_id).get(door_anchor_id(neighbour_id))
    if not placed or not placed["cells"] or not placed.get("dir"):
        return None, None
    return list(placed["cells"]), placed["dir"]


def sight_passes(scene, room_id, edge):
    """`observer_field`'s placement rule, as a THROUGH predicate for
    `room_field`: 1.0 for a barrier an open sightline joins two grids across
    -- one a body can be walked into -- and None for everything else. Sight
    passes a window, a grille or a one-way pane, but none of those is a
    doorway a grid can be walked into; those stay with
    `visual_level_between`."""
    barrier = normalize_barrier(edge.get("barrier"))
    if barrier not in _SIGHT_BARRIERS:
        return None
    if barrier in ("window", "bars", "one_way_window"):
        return None
    return 1.0


def _sight_neighbours(scene, room_id):
    """Rooms an open sightline joins to this one, with the edge bearing."""
    return [(other, bearing) for other, bearing, _factor
            in _placed_neighbours(scene, room_id, sight_passes)]


def _placed_neighbours(scene, room_id, through):
    """`[(neighbour id, bearing, pass)]` for every edge `through` admits.

    ONE PLACEMENT FOR EVERY SENSE. `through(scene, room_id, edge)` answers
    what fraction of a sense the edge's barrier lets across -- None or 0 to
    leave the neighbour unplaced -- and the composite is laid out identically
    whatever the predicate: sight places what a body walks into
    (`sight_passes`), light places what light crosses, glass included
    (`spatial_light_field.light_passes`), sound places whatever is not a
    wall, at the aperture's drop (`spatial_sound_field.sound_passes`). The
    sound field carried its own copy of this loop until 2026-09-04
    (`_acoustic_grid`), and that copy still laid rooms out as tier squares
    after the room-shapes work had taught this one about L and round rooms
    -- the drift a second copy exists to have.
    """
    from world.spatial_barriers import effective_adjacent
    rooms = (scene or {}).get("rooms") or {}
    out = []
    for edge in effective_adjacent(scene, room_id):
        if not isinstance(edge, dict) or not edge.get("to"):
            continue
        other = str(edge["to"])
        if other not in rooms or other == str(room_id):
            continue
        factor = through(scene, room_id, edge)
        if not factor or factor <= 0:
            continue
        bearing = normalize_bearing(edge.get("dir"))
        if bearing:
            out.append((other, bearing, float(factor)))
    return out


def observer_field(scene: dict, observer: str) -> Optional[_Field]:
    """The composite field an observer's sight runs over: their own room,
    plus every neighbour an open doorway with a bearing casts into, placed
    beyond a one-cell wall band with the two door cells aligned."""
    room_id = room_of(scene, observer)
    if not room_id:
        return None
    return room_field(scene, room_id)


def room_field(scene: dict, room_id, *, through=None) -> Optional[_Field]:
    """`observer_field` by ROOM: the composite every observer standing in
    `room_id` sees over, which depends on the room alone. Split out so the
    light field (`world/spatial_light_field.py`) can be computed once per
    room and read for every body in it -- the lamp's rays do not depend on
    who is looking.

    `through` is the placement predicate (`_placed_neighbours`); absent, the
    sight rule, so every existing caller is byte-identical
    (`tests/test_one_grid_two_senses.py` pins cells, heights, occluders,
    offsets, anchors and walls on every existing scene). Each wall record
    carries the predicate's `pass` for its aperture -- 1.0 under the sight
    rule -- beside the five keys it always had.
    """
    if not room_id or room_id not in ((scene or {}).get("rooms") or {}):
        return None
    field = _Field()
    field.add_room(scene, room_id, (0, 0))
    grid = room_grid(scene, room_id)
    for other, _bearing, factor in _placed_neighbours(
            scene, room_id, through or sight_passes):
        d1s, b1 = _door_cells(scene, room_id, other)
        d2s, _b2 = _door_cells(scene, other, room_id)
        if not d1s or not d2s:
            continue
        d1, d2 = d1s[0], d2s[0]
        ux, uy = _UNIT[b1]
        band = (d1[0] + ux, d1[1] + uy)
        anchor_far = (band[0] + ux, band[1] + uy)
        offset = (anchor_far[0] - d2[0], anchor_far[1] - d2[1])
        far = room_grid(scene, other)
        # The neighbour's ACTUAL cells, so two small rooms off one long wall
        # of a wide room can both be laid out where two squares could not.
        if any((x + offset[0], y + offset[1]) in field.inside
               for x, y in far.cells):
            continue                        # two doorways on one wall overlap
        field.add_room(scene, other, offset)
        # THE WALL IS A LINE AND THE DOORWAY IS A GAP IN IT. The band of
        # cells between the two grids is where the wall stands; its midline
        # is the wall, of no thickness, and the doorway's cells give the gap
        # its width. A diagonal bearing puts the neighbour corner to corner,
        # so the doorway is a gap in both of the lines that meet there.
        aperture_cells = [(x + ux, y + uy) for x, y in d1s]
        for axis in ((1,) if b1 in ("n", "s") else
                     (0,) if b1 in ("e", "w") else (0, 1)):
            along = 1 - axis
            # The wall runs over both rooms' reach ALONG it -- each box's
            # own length on that axis, which for two squares was two sides.
            mine = (grid.w, grid.d)[along]
            theirs = (far.w, far.d)[along]
            lo = min(0, offset[along]) - 0.5
            hi = max(mine, offset[along] + theirs) - 0.5
            field.walls.append({
                "axis": axis, "coord": band[axis], "extent": (lo, hi),
                "aperture": (min(c[along] for c in aperture_cells) - 0.5,
                             max(c[along] for c in aperture_cells) + 0.5),
                "to": other,
                "pass": factor,
            })
    return field


def wall_aperture_cells(wall) -> list:
    """The cells of the wall band inside a wall record's aperture -- where
    the doorway's gap actually is, as integer cells on the wall's line. The
    light field emits a room's ambient spill from these."""
    axis = wall["axis"]
    lo, hi = wall["aperture"]
    out = []
    for along in range(int(math.ceil(lo)), int(math.floor(hi)) + 1):
        cell = [0, 0]
        cell[axis] = wall["coord"]
        cell[1 - axis] = along
        out.append(tuple(cell))
    return out


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
            # A cell on a wall line is the wall's business (`_wall_verdict`
            # on the straight line), not a solid the cast stops at: a fan
            # cast through a one-cell hole in a one-cell-thick wall admits
            # a narrower cone than any real doorway does.
            return not _on_wall_line(field, (x, y))
        h = field.height.get((x, y))
        return h is not None and _blocks(h, eye, top)
    return shadowcast(origin, side_max + 1, blocked)


def _on_wall_line(field, cell) -> bool:
    """Is this (non-interior) cell part of a wall between two placed rooms?"""
    for wall in field.walls:
        if cell[wall["axis"]] == wall["coord"] \
                and wall["extent"][0] <= cell[1 - wall["axis"]] \
                <= wall["extent"][1]:
            return True
    return False


def _wall_verdict(field, origin, target) -> bool:
    """Does the straight segment between two cell centres pass through
    every wall that stands between them? Real geometry, not a cell walk:
    the segment crosses the wall's line at one point, and it is through the
    wall if that point lies in the doorway's span and into it otherwise.

    So a doorway one cell wide admits a line at ANY angle that threads it,
    which is what a doorway does -- a real wall is a fraction of a pace
    thick and a jamb subtracts a few degrees at the extremes, not the
    forty-five a cell-thick wall did. A wall crossed outside its extent is
    no verdict: that is the corner of the room, and the cells beyond it
    are outside `field.inside` and fail on their own.
    """
    for wall in field.walls:
        axis = wall["axis"]
        o, t = origin[axis], target[axis]
        c = wall["coord"]
        if (o - c) * (t - c) >= 0:
            continue                        # both on one side, or on it
        k = (c - o) / float(t - o)
        along = origin[1 - axis] + k * (target[1 - axis] - origin[1 - axis])
        if not (wall["extent"][0] <= along <= wall["extent"][1]):
            continue
        if not (wall["aperture"][0] <= along <= wall["aperture"][1]):
            return False
    return True


def _occluders_on(field, origin, target, eye, top):
    """(blocking anchor id or None, tallest non-blocking anchor height rank)
    along the straight line between two cells. `__wall__` names a wall,
    whether the line struck one between two rooms (`_wall_verdict`) or ran
    out of the field altogether."""
    tallest = -1.0
    tallest_id = None
    if not _wall_verdict(field, origin, target):
        return "__wall__", tallest, tallest_id
    for cell in _line(origin, target):
        if cell not in field.inside:
            if _on_wall_line(field, cell):
                continue                    # the wall itself, judged above
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


def neighbour_feature_visibility(scene: dict, observer: str, to_room,
                                 *, sweep=False):
    """What the observer's eyes reach of a NEIGHBOUR room's furniture, or None
    when that room is not placeable in this observer's field.

    Same row shape as `feature_visibility`, over `field.anchors[to_room]`
    instead of the observer's own room. `observer_field` has already laid the
    neighbour out beyond the wall with the two door cells aligned and recorded
    that wall as a line with the doorway as a gap in it (`field.walls`), so
    the doorway IS the aperture: one straight line from the observer to the
    thing, and `_occluders_on` answers `__wall__` when that line crosses the
    wall anywhere but through the gap (`_wall_verdict`), and names the
    furniture on either side of it otherwise. The cone cap is therefore
    geometric rather than a second rule -- nothing here re-decides what an
    opening admits, and nothing routes the line through the door in legs
    (the 2026-09-04 form did, and let an observer beside the doorframe see
    round the corner to a thing on the far diagonal, which no straight line
    reaches).

    ONE DELIBERATE DIFFERENCE FROM THE WITHIN-ROOM FORM: the occlusion walk
    always runs, where `feature_visibility` runs it only for an observer at a
    measured station. Within a room that gate is right -- with no measured
    cell there is no line to test and the honest answer is to leave every
    verdict alone. Across a threshold it would be exactly wrong: skipping the
    walk does not withhold a subtraction, it grants the whole of the next room
    to somebody who has not been placed anywhere, which is the one thing a
    doorway must never do. Unmeasured, the walk runs from the room's centre --
    an approximation of where the observer stands, never of whether the wall
    is there.

    The neighbour's OWN doorways (implicit anchors) are left out: a way
    onward from a room you are only glancing into is not something a glance
    delivers, and the opening the observer is looking through is already the
    percept this list hangs on.
    """
    field = observer_field(scene, observer)
    if field is None or to_room not in field.offsets:
        return None
    room_id = room_of(scene, observer)
    if not room_id or str(to_room) == str(room_id):
        return None
    origin, _how = _observer_cell(scene, observer)
    facing = None if sweep else effective_facing(scene, observer)
    eye = eye_rank(scene, observer)
    ox, oy = field.offsets[to_room]
    rows = []
    for aid, rec in (field.anchors.get(to_room) or {}).items():
        if rec["implicit"] or not rec["cells"]:
            continue
        cells = [(x + ox, y + oy) for x, y in rec["cells"]]
        target = min(cells, key=lambda c: (c[0] - origin[0]) ** 2
                     + (c[1] - origin[1]) ** 2)
        dist = math.hypot(target[0] - origin[0], target[1] - origin[1])
        sector = _cone_sector(facing, origin, target) if facing else None
        if facing and _sector_verdict(sector) == "rear":
            continue
        top = max(height_rank(rec["height"]), 0.5)
        blocker, _t, _tid = _occluders_on(field, origin, target, eye, top)
        if blocker and blocker != aid:
            continue
        rows.append({
            "anchor": aid, "desc": rec["desc"], "implicit": False,
            "visible": True, "sector": sector,
            "peripheral": bool(facing) and _sector_verdict(sector) == "side",
            "side": _side_label(sector), "tier": "across",
            "occluded_by": None, "basis": "line", "distance": dist,
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
