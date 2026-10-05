# spatial_range.py
"""How far a body is, and what that distance leaves of it to see.

The owner, 2026-10-04: "for distant objects we might need something like
the text equivalent of an LOD", then "Go ahead". Sight had one detail
ladder -- none < shapes < conduct < full (`spatial_light.SIGHT_LEVELS`) --
and only light moved a target down it. Distance is its second input: a
target is seen at the WEAKER of what the light allows and what the distance
allows (`spatial_senses.sight_between`).

The bands, for a person-sized target. Every number is the owner's to move:

  FACE_RANGE_M      15 m  full -- a face, an expression, a small thing in a
                          hand. Wagenaar & van der Schrier (1996), "Face
                          recognition as a function of distance and
                          illumination: a practical tool for use in the
                          courtroom", the "rule of fifteen": a stranger's
                          face is reliably identified within 15 m in at
                          least 15 lux.
  CONDUCT_RANGE_M  100 m  conduct -- posture, gait, the cut and colour of
                          what is worn, what a body does. An engine
                          estimate, approved 2026-10-04.
  beyond                  shapes -- a figure, moving or still.

A target's size scales both bands (`sight_scale`): a thing a hand carries
keeps its detail a fifth as far, a cart or a building three times as far
(engine estimates), and a body the story has grown or shrunk by its own
factor. An observer's card scales them too (`sight_reach`): keen eyes read
a face twice as far.

DISTANCE NEVER ANSWERS `none`. It costs detail, never the channel, so every
reader that asks only "seen at all?" keeps its answer -- whether a body is
in view, whether a crossing is minted, whether a step is planned -- and a
body crossing a threshold keeps the floor it has.

EVIDENCE, AND ONLY WHAT IS CERTAIN. The engine knows where a body stands
only when its station says so, and an `at` station's cell is a seat dealt
along the anchor by hash -- "a way of seating several people along one
counter, not a statement about any one of them" (`spatial_fov.body_cell`):
six bodies at one long run anchor were dealt seats 49 m apart. So a body is
a BOX of the cells it could be standing in: a pinned cell is one cell, a
body `at` an anchor is anywhere along the anchor's stand cells, a body
`near` another is within a pace of that one's box. A SUBTRACTION reads the
NEAREST two boxes can be: the true distance is at least that, so the band
it gives is never below what is really seen. A body with no station makes
no claim. The places a band replaces an older, coarser cap (an authored
`far` edge, the doorway between two big rooms) read the FARTHEST the
evidence allows, so the replacement never shows more than the far end of
the evidence would.
"""

from __future__ import annotations

import math
import re
from typing import NamedTuple, Optional

from world.spatial_geometry import effective_station, normalize_cell
from world.spatial_identity import _body_kinds, _ci_get, room_of

#: A face, an expression, a small thing in a hand -- Wagenaar & van der
#: Schrier (1996), the "rule of fifteen".
FACE_RANGE_M = 15.0
#: Posture, gait, what is worn, what a body does. Engine estimate, approved
#: by the owner 2026-10-04.
CONDUCT_RANGE_M = 100.0
#: A thing a hand carries keeps its detail this fraction as far as a person
#: does; a vehicle, a structure, a thing with rooms inside, this multiple.
#: Engine estimates.
SMALL_SCALE = 0.2
LARGE_SCALE = 3.0
#: An `extended` sight range on a card, and a `reduced` one, scale the bands
#: by these; acuity scales them by two per step (keen x2, extraordinary x4,
#: dulled x0.5). Engine estimates.
RANGE_CLASS_REACH = {"reduced": 0.5, "ordinary": 1.0, "extended": 2.0}

#: One pace of the engine's grid, in metres (`site_plan.PACE_M`).
_PACE_M = 0.75

_RANKS = {"shapes": 1, "conduct": 2, "full": 3}

# An authored edge `distance` as bounds in metres: the tier words keep the
# boundaries `spatial_routing.normalize_edge_distance` cuts them at.
_TIER_BOUNDS = {"adjacent": (None, None), "near": (None, None),
                "far": (20.0, 75.0), "remote": (75.0, None)}


def range_sight(metres, scale: float = 1.0, reach: float = 1.0) -> str:
    """What `metres` leaves of a target of `scale` to an eye of `reach`:
    full, conduct or shapes -- never none. No distance is no claim (full)."""
    if metres is None:
        return "full"
    try:
        m = float(metres)
    except (TypeError, ValueError):
        return "full"
    if m != m:
        return "full"
    k = max(0.01, float(scale or 1.0)) * max(0.01, float(reach or 1.0))
    if m <= FACE_RANGE_M * k:
        return "full"
    if m <= CONDUCT_RANGE_M * k:
        return "conduct"
    return "shapes"


# ---------------------------------------------------------------------------
# How big a thing is, against a person
# ---------------------------------------------------------------------------

def anchor_scale(anchor) -> float:
    """A fixture's size against a person, from its AUTHORED fields only.

    A large or run footprint, or full height, is LARGE; a point footprint
    on the floor, both written, is SMALL; anything else -- an unwritten
    anchor included -- is a person. The geometry's own default for an
    unwritten anchor (point, floor) is the one that subtracts LEAST for
    occlusion; read as a size it would subtract most, so an anchor nobody
    measured is never small.
    """
    rec = anchor if isinstance(anchor, dict) else {}
    footprint = str(rec.get("footprint") or "").strip().casefold()
    height = str(rec.get("height") or "").strip().casefold()
    if footprint in ("large", "run") or height == "full":
        return LARGE_SCALE
    if footprint == "point" and height == "floor":
        return SMALL_SCALE
    return 1.0


def thing_scale(entity) -> float:
    """A scene thing's size against a person, from the structural fields
    the engine owns -- never its free-text `kind`, its card prose or a
    `state.size` phrase. Something with rooms inside or under way as a
    vehicle is LARGE; something a body may pick up and carry is SMALL."""
    rec = entity if isinstance(entity, dict) else {}
    state = rec.get("state") if isinstance(rec.get("state"), dict) else {}
    if isinstance(state.get("transit"), dict) or rec.get("interior_rooms"):
        return LARGE_SCALE
    if rec.get("portable"):
        return SMALL_SCALE
    return 1.0


def sight_scale(scene: dict, name: str) -> float:
    """`name`'s size against a person: a body by the story's own factor for
    it (`scale_of`, 1.0 unstated), a thing by `thing_scale`.

    Body or thing by the two tiers of `spatial_identity.scene_names_body`
    that read only what this derivation's read set stamps (`scene_memo.
    SCENE_READS`): a size row in `scales` is a body, and an entity record
    says what it is by the engine's animate vocabulary. A name with no
    record is a body, as that predicate's third tier says. Its first tier
    also reads attire, vitals and overlays -- ledgers no sight derivation
    stamps, so a change to them inside a read pass would go unnoticed.
    """
    from world.spatial_containment import scale_of
    factor = scale_of(scene, name)           # reads scene["scales"], always
    entity = _ci_get(((scene or {}).get("entities") or {}), name)
    if not isinstance(entity, dict):
        return factor
    scales = (scene or {}).get("scales") or {}
    if isinstance(scales, dict) and _ci_get(scales, name) is not None:
        return factor
    if str(entity.get("kind") or "").strip().casefold() in _body_kinds():
        return factor
    return thing_scale(entity)


def sight_reach(senses) -> float:
    """How far this observer's eyes carry the bands: acuity two-fold a step,
    and the card's sight `range` class. 1.0 for an ordinary card or none."""
    if not senses:
        return 1.0
    from world.spatial_senses import sense_acuity_offset, sense_range_class
    offset = sense_acuity_offset(senses, "sight")
    reach = 2.0 ** offset if offset else 1.0
    return reach * RANGE_CLASS_REACH.get(sense_range_class(senses, "sight"), 1.0)


# ---------------------------------------------------------------------------
# How far apart two bodies are, as far as the engine knows for certain
# ---------------------------------------------------------------------------

def _bbox(cells):
    xs = [c[0] for c in cells]
    ys = [c[1] for c in cells]
    return (min(xs), min(ys), max(xs), max(ys))


def position_box(scene: dict, name: str, _seen=frozenset()):
    """`(room_id, (x0, y0, x1, y1), exact)`: every cell `name` could be
    standing in by its own station, or None when the station says nowhere.

    A pinned `cell` is that cell (exact). A body `at` an anchor is anywhere
    along the anchor's stand cells -- never the seat `body_cell` deals it.
    A body `near` another is within a pace of that one's box, and along
    their shared anchor when they stand at one.
    """
    from world.spatial_fov import _anchor_stand_cells, room_grid
    room = room_of(scene, name)
    if not room:
        return None
    grid = room_grid(scene, room)
    st = effective_station(scene, name)
    pinned = normalize_cell(st.get("cell"))
    if pinned is not None:
        x, y = grid.nearest(pinned)
        return room, (x, y, x, y), True
    at = str(st.get("at") or "").strip()
    along = _anchor_stand_cells(scene, room, grid, at, st) if at else []
    key = str(name).strip().casefold()
    for other in st.get("near") or []:
        okey = str(other).strip().casefold()
        if not okey or okey == key or okey in _seen:
            continue
        if room_of(scene, other) != room:
            continue
        found = position_box(scene, other, _seen | {key})
        if not found:
            continue
        x0, y0, x1, y1 = found[1]
        cells = [(max(0, x0 - 1), max(0, y0 - 1)),
                 (min(grid.w - 1, x1 + 1), min(grid.d - 1, y1 + 1))]
        return room, _bbox(cells + list(along)), False
    if along:
        return room, _bbox(along), False
    return None


def _room_box(scene, room):
    from world.spatial_fov import room_grid
    grid = room_grid(scene, room)
    return (0, 0, grid.w - 1, grid.d - 1)


def _gap(a, b):
    """(nearest, farthest) distance in paces between two boxes."""
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    dx_lo = max(0, bx0 - ax1, ax0 - bx1)
    dy_lo = max(0, by0 - ay1, ay0 - by1)
    dx_hi = max(abs(bx1 - ax0), abs(ax1 - bx0))
    dy_hi = max(abs(by1 - ay0), abs(ay1 - by0))
    return math.hypot(dx_lo, dy_lo), math.hypot(dx_hi, dy_hi)


def _shifted(field, room, box):
    x0, y0 = field.cell_of(room, (box[0], box[1]))
    x1, y1 = field.cell_of(room, (box[2], box[3]))
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def edge_bounds(value):
    """An authored edge `distance` as (low, high) metres; high None means
    unbounded (a bare `remote`), (None, None) no claim."""
    raw = str(value if value is not None else "").strip().casefold()
    if not raw:
        return None, None
    from world.spatial_routing import _DISTANCE_ALIASES, _DISTANCE_UNIT_METERS
    if raw in _DISTANCE_ALIASES:
        return _TIER_BOUNDS.get(_DISTANCE_ALIASES[raw], (None, None))
    matched = re.match(r"^~?\s*(\d+(?:\.\d+)?)\s*([a-z]+)?\.?$", raw)
    if not matched:
        return None, None
    unit = _DISTANCE_UNIT_METERS.get(matched.group(2) or "m")
    if unit is None:
        return None, None
    metres = float(matched.group(1)) * unit
    return metres, metres


def _edge_distance(scene, a_room, b_room):
    """The authored `distance` of the edge joining two rooms, read the way
    `spatial_routing.spatial_rel` reads it: the FIRST edge that joins them,
    from the observer's side, empty or not. A distance written on the far
    side only is not this direction's (the oracle against the old cap,
    2026-10-04: 127 pairs a one-sided "far" capped one way and not the
    other)."""
    from world.spatial_barriers import resolve_edge
    rooms = (scene or {}).get("rooms") or {}
    for source, target in ((a_room, b_room), (b_room, a_room)):
        for edge in (rooms.get(source) or {}).get("adjacent") or []:
            if isinstance(edge, dict) and edge.get("to") == target:
                value = resolve_edge(scene, edge).get("distance")
                return value if value not in ("",) else None
    return None


class RangeEvidence(NamedTuple):
    """What the engine holds for certain about how far apart two bodies are.

    `low` is the nearest they can be (what a subtraction reads); `exact`
    says both ends are pinned, so `low` is THE distance. `edge_high` is the
    far end of an authored edge distance and `edge_unbounded` a bare
    `remote` -- the evidence the old far/remote cap is replaced by -- and
    `far` the FARTHEST the two can be across that edge: its far end, plus
    as far as each body can stand inside its own room. A replaced cap is
    read there, never at the edge alone: two bodies at the back walls of
    two big rooms joined by a "far" edge can be well past a hundred metres.
    """
    low: Optional[float] = None
    exact: bool = False
    edge_high: Optional[float] = None
    edge_unbounded: bool = False
    basis: str = ""
    far: Optional[float] = None
    #: The edge was one the old flat cap applied to (`far` or `remote` by
    #: `spatial_routing.normalize_edge_distance`): the only edges whose
    #: replacement is read at `far`. A near edge never had a cap, so only
    #: its certain lower bound may subtract.
    capped: bool = False


def _rise(scene, observer, target) -> float:
    """How far apart in HEIGHT two bodies are for certain: each one's floor
    (`site_plan.room_elevation_m`) plus how far off it the body is
    (`stations[body].altitude_m`) -- both written facts. A flier ninety
    metres over the gateway is ninety metres off, whatever the cells say."""
    from world.site_plan import body_altitude_m, room_elevation_m
    try:
        here = room_elevation_m(scene, room_of(scene, observer)) + body_altitude_m(scene, observer)
        there = room_elevation_m(scene, room_of(scene, target)) + body_altitude_m(scene, target)
    except Exception:
        return 0.0
    return abs(float(here) - float(there))


def _room_reach_m(scene, room) -> float:
    """The farthest a body can stand from anywhere else in its own room."""
    x0, y0, x1, y1 = _room_box(scene, room)
    return math.hypot(x1 - x0, y1 - y0) * _PACE_M


def pair_range(scene: dict, observer: str, target: str) -> RangeEvidence:
    """How far `target` is from `observer`, as far as is certain."""
    o_room = room_of(scene, observer)
    t_room = room_of(scene, target)
    if not o_room or not t_room:
        return RangeEvidence()
    low = None
    exact = False
    basis = ""
    o_box = position_box(scene, observer)
    t_box = position_box(scene, target)
    rise = _rise(scene, observer, target)
    if o_room == t_room:
        if o_box and t_box:
            low = math.hypot(_gap(o_box[1], t_box[1])[0] * _PACE_M, rise)
            exact = o_box[2] and t_box[2]
            basis = "cells"
        return RangeEvidence(low, exact, None, False, basis)
    # A storey apart on one plan: the plan's own three-dimensional line,
    # exact only where both ends are pinned (an unmeasured end stands at
    # its room's centre there, which is no certain distance).
    from world.site_plan import plan_sight
    raised = plan_sight(scene, observer, target)
    if raised is not None:
        if o_box and t_box and o_box[2] and t_box[2]:
            return RangeEvidence(raised["distance_m"], True, None, False, "plan")
        return RangeEvidence(None, False, None, False, "plan")
    # Through a doorway the observer's own field lays: boxes in one frame.
    # An end with no station is anywhere in its room -- still a certain
    # bound once the other end is measured.
    box_far = None
    if o_box or t_box:
        from world.spatial_fov import observer_field
        field = observer_field(scene, observer)
        if field is not None and t_room in field.offsets and o_room in field.offsets:
            a = _shifted(field, o_room, o_box[1] if o_box else _room_box(scene, o_room))
            b = _shifted(field, t_room, t_box[1] if t_box else _room_box(scene, t_room))
            near_gap, far_gap = _gap(a, b)
            low = math.hypot(near_gap * _PACE_M, rise)
            box_far = math.hypot(far_gap * _PACE_M, rise)
            exact = bool(o_box and t_box and o_box[2] and t_box[2])
            basis = "field"
    # An authored edge distance is evidence of separation the wall-to-wall
    # layout does not model: a lower bound for subtraction, and -- with as
    # far as each body can stand in its room -- the far end for the cap it
    # replaces.
    raw_edge = _edge_distance(scene, o_room, t_room)
    e_low, e_high = edge_bounds(raw_edge)
    unbounded = e_low is not None and e_high is None
    far = None
    from world.spatial_routing import normalize_edge_distance
    capped = raw_edge is not None and normalize_edge_distance(raw_edge) in ("far", "remote")
    if e_low is not None:
        low = max(low or 0.0, e_low)
        exact = exact and e_low == e_high
        basis = basis or "edge"
        if e_high is not None:
            within = (box_far if box_far is not None
                      else _room_reach_m(scene, o_room) + _room_reach_m(scene, t_room))
            far = math.hypot(e_high + within, rise)
    return RangeEvidence(low, exact, e_high, unbounded, basis, far, capped)


def range_of(evidence: RangeEvidence, scale: float = 1.0, reach: float = 1.0) -> str:
    """The band the evidence earns, for one target size and one eye."""
    band = range_sight(evidence.low, scale, reach)
    if evidence.edge_unbounded:
        band = _weaker(band, "shapes")
    elif evidence.capped and evidence.edge_high is not None:
        band = _weaker(band, range_sight(
            evidence.far if evidence.far is not None else evidence.edge_high,
            scale, reach))
    return band


def _weaker(a: str, b: str) -> str:
    return a if _RANKS.get(a, 3) <= _RANKS.get(b, 3) else b
