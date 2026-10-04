"""Where rooms stand on one plan, and how high their floors are.

A room's geometry has always been its own: a grid of paces local to the
room, joined to its neighbours by doorways with a bearing, and laid out on
a map only by walking those bearings outward (`spatial_lint.layout_rooms`).
That cannot draw a house standing in its garden -- a room laid inside
another is a collision by construction -- and nothing knew that the window
of a third-storey bedroom is eight metres above the lawn.

A SITE PLAN IS A STORED FACT, NOT A WALK. A room may carry

    site = {"plan": <plan id>, "x": <paces>, "y": <paces>, "elev_m": <metres>}

`x`/`y` are the room grid's north-west corner on the plan, in the grid's
own unit (paces; x east, y south); `elev_m` is the height of its floor.
Rooms naming one plan share one frame, so a garden can be a composite room
whose cells surround a house's footprint and the house's rooms stand in the
hole. A room with no `site` is exactly what it was.

Built 2026-10-03 on the owner's go-ahead ("go ahead"), step 1 of three:
positions and elevations, and the map drawing them. Sight using elevation
(a window seen from the garden below) and drops as facts (a fall's height,
offered to the Director) are steps 2 and 3, and flight -- a body's own
height above its floor -- builds on the same number.
"""
from __future__ import annotations

import math
from typing import Optional

#: A storey's height when a room states a `level` and no elevation: the
#: floor-to-floor of an ordinary house, in metres. One number the engine
#: owns; a plan that knows better says `elev_m`.
STOREY_M = 3.0


def normalize_site(value) -> Optional[dict]:
    """`{plan, x, y, elev_m}` with a non-empty plan id and whole-pace x/y,
    or None when the value is not a site. `elev_m` is optional (None)."""
    if not isinstance(value, dict):
        return None
    plan = str(value.get("plan") or "").strip()
    if not plan:
        return None
    out = {"plan": plan}
    for axis in ("x", "y"):
        raw = value.get(axis)
        if raw is None or isinstance(raw, bool):
            return None
        try:
            number = float(raw)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(number):
            return None
        out[axis] = int(round(number))
    elev = value.get("elev_m")
    if elev is not None and not isinstance(elev, bool):
        try:
            elev = float(elev)
        except (TypeError, ValueError):
            elev = None
        out["elev_m"] = elev if elev is not None and math.isfinite(elev) else None
    else:
        out["elev_m"] = None
    return out


def _scene_rooms(scene) -> dict:
    rooms = (scene or {}).get("rooms") or {}
    return rooms if isinstance(rooms, dict) else {}


def room_site(scene, room_id) -> Optional[dict]:
    """The room's site on its plan, normalized, or None."""
    room = _scene_rooms(scene).get(room_id)
    return normalize_site(room.get("site")) if isinstance(room, dict) else None


def room_elevation_m(scene, room_id) -> float:
    """The height of the room's floor in metres: its site's `elev_m` when
    stated, else its storey (`level`) times `STOREY_M`, else 0 -- the
    ground, which is what every room was before elevations existed."""
    from world.spatial import normalize_level

    site = room_site(scene, room_id)
    if site and site.get("elev_m") is not None:
        return float(site["elev_m"])
    room = _scene_rooms(scene).get(room_id) or {}
    level = normalize_level(room.get("level")) if isinstance(room, dict) else None
    return float(level or 0) * STOREY_M


def room_level(scene, room_id) -> int:
    """The storey a room is drawn on: its `level`, else 0."""
    from world.spatial import normalize_level

    room = _scene_rooms(scene).get(room_id) or {}
    level = normalize_level(room.get("level")) if isinstance(room, dict) else None
    return int(level or 0)


def site_plans(scene) -> dict:
    """`{plan: {level: [room ids]}}` for every room on a plan, sorted."""
    out: dict = {}
    for rid in sorted(_scene_rooms(scene), key=str):
        site = room_site(scene, rid)
        if site:
            out.setdefault(site["plan"], {}).setdefault(
                room_level(scene, rid), []).append(str(rid))
    return out


def site_cells(scene, room_id) -> frozenset:
    """The room's cells on its plan (its grid's cells moved to its site), or
    an empty set for a room on no plan."""
    from world.spatial import room_grid

    site = room_site(scene, room_id)
    if not site:
        return frozenset()
    ox, oy = site["x"], site["y"]
    return frozenset((x + ox, y + oy) for x, y in room_grid(scene, room_id).cells)


def site_overlaps(scene) -> list:
    """`(plan, level, room, other)` for two rooms of one plan and storey
    whose cells land on each other: a plan that does not hold together.
    Sorted, so a reroll reports the same pair."""
    out = []
    for plan, levels in sorted(site_plans(scene).items()):
        for level, ids in sorted(levels.items()):
            held: dict = {}
            for rid in ids:
                for cell in site_cells(scene, rid):
                    other = held.get(cell)
                    if other is not None:
                        pair = (plan, level, other, rid)
                        if pair not in out:
                            out.append(pair)
                    else:
                        held[cell] = rid
    return out


# ---------------------------------------------------------------------------
# Sight with height (step 2, 2026-10-04)
# ---------------------------------------------------------------------------
#
# Two rooms of one plan whose floors stand at different heights -- a garden
# and the third-storey bedroom whose window looks down on it -- are seen
# between by a line in three dimensions, never by laying the upper room flat
# beside the lower one. The line runs from the observer's eye to the top of
# the other body; it must leave the upper room THROUGH the window (between
# its sill and its lintel) and pass over every building mass it crosses on
# the plan -- the roof of a lower wing hides the foot of the wall below a
# window. A body with no measured station stands at its room's centre: the
# one place the room as a whole says it is.

#: How far one pace is, in metres -- the room grid's unit
#: (`spatial_walk`: 0.75 m a pace).
PACE_M = 0.75

#: A body's eye above its floor, and the top of it, by posture class
#: (`spatial_fov.posture_class`), in metres. Engine numbers for an adult.
EYE_M = {"standing": 1.6, "sitting": 1.2, "kneeling": 1.0, "crouching": 0.9,
         "lying": 0.3}
TOP_M = {"standing": 1.7, "sitting": 1.3, "kneeling": 1.1, "crouching": 1.0,
         "lying": 0.4}
#: How far below the top of a body still says who it is: head and shoulders.
#: A line that reaches the top and not this far down sees the body above the
#: sill only (`hidden_below: "waist"`).
CHEST_BELOW_TOP_M = 0.5

#: A window's sill and lintel above its own floor, in metres.
SILL_M = 0.9
LINTEL_M = 2.1

#: How far a face is read across open air, in metres; beyond it a body
#: seen through a window a storey away is a shape. An engine number.
FACE_READ_M = 25.0

#: A floor's difference, in metres, below which two rooms are one level for
#: sight: a step up into a genkan is not a storey.
LEVEL_STEP_M = 1.0


def _open_air(scene, room_id) -> bool:
    room = _scene_rooms(scene).get(room_id) or {}
    return str(room.get("exposure") or "").strip().casefold() == "open"


def elevated_pair(scene, a, b) -> bool:
    """Are rooms `a` and `b` on one plan with floors a storey apart?"""
    sa, sb = room_site(scene, a), room_site(scene, b)
    if not sa or not sb or sa["plan"] != sb["plan"] or a == b:
        return False
    return abs(room_elevation_m(scene, a) - room_elevation_m(scene, b)) >= LEVEL_STEP_M


def plan_point(scene, name) -> Optional[tuple]:
    """(x, y, floor metres) of a body on its room's plan: its measured cell's
    centre, or its room's centre when it has none. None off any plan."""
    from world.spatial import body_cell, room_grid, room_of

    rid = room_of(scene, name)
    site = room_site(scene, rid) if rid else None
    if not site:
        return None
    cell = body_cell(scene, name)
    if cell is None:
        cell = room_grid(scene, rid).centre()
    return (site["x"] + cell[0] + 0.5, site["y"] + cell[1] + 0.5,
            room_elevation_m(scene, rid) + body_altitude_m(scene, name))


def _mass_heights(scene, plan, exclude) -> dict:
    """{plan cell: [(floor m, ceiling m), ...]} -- the building standing on
    each cell of a plan, a slab per enclosed room over it, floor to ceiling.
    Open-air rooms are ground, not mass; the rooms a line starts and ends in
    are its air, not an obstacle (`exclude`). A slab, not a column: the
    bedroom under a roost is air at the bedroom's height, whatever stands
    over it."""
    slabs: dict = {}
    for levels in site_plans(scene).get(plan, {}).values():
        for rid in levels:
            if rid in exclude or _open_air(scene, rid):
                continue
            floor = room_elevation_m(scene, rid)
            for cell in site_cells(scene, rid):
                slabs.setdefault(cell, []).append((floor, floor + STOREY_M))
    return slabs


def _window_on_line(scene, upper, lower, p, q):
    """Where the line p->q crosses the upper room's wall, and whether it is
    in a window there: (height at the crossing, True/False), or None when
    the two rooms share no window edge with a placed opening."""
    from world.spatial import _door_cells, normalize_barrier, effective_adjacent

    edge = next((e for e in effective_adjacent(scene, upper)
                 if isinstance(e, dict) and str(e.get("to")) == str(lower)), None)
    if edge is None or normalize_barrier(edge.get("barrier")) not in (
            "window", "one_way_window", "bars", "open"):
        return None
    cells, bearing = _door_cells(scene, upper, lower)
    site = room_site(scene, upper)
    if not cells or bearing not in ("n", "s", "e", "w"):
        return None
    xs = [site["x"] + c[0] for c in cells]
    ys = [site["y"] + c[1] for c in cells]
    if bearing in ("e", "w"):
        plane = (max(xs) + 1) if bearing == "e" else min(xs)
        if p[0] == q[0]:
            return (None, False)
        t = (plane - p[0]) / (q[0] - p[0])
        lateral, lo, hi = p[1] + t * (q[1] - p[1]), min(ys), max(ys) + 1
    else:
        plane = (max(ys) + 1) if bearing == "s" else min(ys)
        if p[1] == q[1]:
            return (None, False)
        t = (plane - p[1]) / (q[1] - p[1])
        lateral, lo, hi = p[0] + t * (q[0] - p[0]), min(xs), max(xs) + 1
    if not 0.0 <= t <= 1.0:
        return (None, False)
    z = p[2] + t * (q[2] - p[2])
    floor = room_elevation_m(scene, upper)
    inside = lo <= lateral <= hi and floor + SILL_M <= z <= floor + LINTEL_M
    return (z, inside)


def _clears_mass(p, q, slabs) -> bool:
    """Does the line p->q pass through no building slab on any plan cell it
    crosses? Sampled four times a pace, which no wall a pace thick slips."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    steps = max(1, int(math.ceil(max(abs(dx), abs(dy)) * 4)))
    for i in range(1, steps):
        t = i / steps
        cell = (math.floor(p[0] + t * dx), math.floor(p[1] + t * dy))
        z = p[2] + t * (q[2] - p[2])
        if any(lo <= z <= hi for lo, hi in slabs.get(cell, ())):
            return False
    return True


def plan_sight(scene, observer, target) -> Optional[dict]:
    """The line between two bodies in rooms a storey apart on one plan, or
    None when that is not the question (another plan, the same level, no
    plan). `{visible, fraction, hidden_below, distance_m, origin, goal,
    occluded_by}` -- `occluded_by` is "the sill" or "the building" when the
    line is refused, and `origin`/`goal` are plan cells for a cone reader."""
    from world.spatial import posture_class, room_of

    o_room, t_room = room_of(scene, observer), room_of(scene, target)
    if not o_room or not t_room or not elevated_pair(scene, o_room, t_room):
        return None
    p0, q0 = plan_point(scene, observer), plan_point(scene, target)
    if p0 is None or q0 is None:
        return None
    o_post, t_post = posture_class(scene, observer), posture_class(scene, target)
    eye = (p0[0], p0[1], p0[2] + EYE_M.get(o_post, EYE_M["standing"]))
    # SIGHT IS ONE LINE, BOTH WAYS. Whether two bodies see each other is the
    # line between their EYES, which is the same line from either end; only
    # how much of the other shows (above the sill or whole) is the
    # observer's own. Eye to head-top one way and head-top to eye the other
    # let one see without being seen at the sill's edge -- Cataclysm: DDA's
    # zombies on the roof, in miniature (prior-art survey, 2026-10-04).
    their_eye = q0[2] + EYE_M.get(t_post, EYE_M["standing"])
    top_z = q0[2] + TOP_M.get(t_post, TOP_M["standing"])
    upper, lower = (o_room, t_room) if room_elevation_m(scene, o_room) > \
        room_elevation_m(scene, t_room) else (t_room, o_room)
    plan = room_site(scene, upper)["plan"]
    tops = _mass_heights(scene, plan, {o_room, t_room})

    def reaches(z):
        q = (q0[0], q0[1], z)
        crossing = _window_on_line(scene, upper, lower, eye, q)
        if crossing is None or not crossing[1]:
            return False, "the sill" if crossing else "the wall"
        if not _clears_mass(eye, q, tops):
            return False, "the building"
        return True, None

    top_ok, why = reaches(their_eye)
    chest_ok = reaches(top_z - CHEST_BELOW_TOP_M)[0] if top_ok else False
    horizontal = math.hypot(q0[0] - p0[0], q0[1] - p0[1]) * PACE_M
    distance = math.hypot(horizontal, top_z - eye[2])
    return {
        "visible": top_ok,
        "fraction": 1.0 if chest_ok else (0.5 if top_ok else 0.0),
        "hidden_below": "waist" if top_ok and not chest_ok else None,
        "occluded_by": None if top_ok else why,
        "distance_m": round(distance, 1),
        "origin": (int(math.floor(p0[0])), int(math.floor(p0[1]))),
        "goal": (int(math.floor(q0[0])), int(math.floor(q0[1]))),
    }


def interior_hidden_from_below(scene, observer_room, other_room) -> bool:
    """From a lower room the inside of an upper one is not seen through its
    window -- the window is, and what stands at it (`plan_sight`). True when
    `other_room` is a storey or more above `observer_room` on one plan."""
    return (elevated_pair(scene, observer_room, other_room)
            and room_elevation_m(scene, other_room) > room_elevation_m(scene, observer_room))


# ---------------------------------------------------------------------------
# Drops as facts (step 3, 2026-10-04)
# ---------------------------------------------------------------------------
#
# Geometry proposes, the Director disposes (DESIGN_METRIC_SPACE §4). A way
# out of a room that is not a stair and opens onto a room a storey or more
# below -- a window over the garden, a balcony, the lip of a bank -- is a
# drop of a stated height onto a stated place. The Director is shown that
# height before it writes (`causal_world_index`'s `drops`), and told after
# the beat when a body went that way (`report_drops`). What the fall does is
# its judgement; how far it was is not.

def _direct_edge(scene, a, b):
    from world.spatial import effective_adjacent

    return next((e for e in effective_adjacent(scene, a)
                 if isinstance(e, dict) and str(e.get("to")) == str(b)), None)


def drop_m(scene, from_room, to_room) -> Optional[float]:
    """How far a body falls going from `from_room` straight to `to_room`, in
    metres, or None when that way is no drop: the rooms are not a storey
    apart on one plan, the far room is not below, there is no way between
    them, or the way is a stair, a ladder or a hatch (`vertical` + `way`)."""
    from world.spatial import normalize_vertical

    if not elevated_pair(scene, from_room, to_room):
        return None
    height = room_elevation_m(scene, from_room) - room_elevation_m(scene, to_room)
    if height < LEVEL_STEP_M:
        return None
    edge = _direct_edge(scene, from_room, to_room)
    if edge is None:
        return None
    if normalize_vertical(edge.get("vertical")) and str(edge.get("way") or "stair") != "overlook":
        return None
    return round(height, 1)


def drops_from(scene, room_id) -> dict:
    """{exit room id: metres} for every way out of `room_id` that is a drop."""
    from world.spatial import effective_adjacent

    out = {}
    for edge in effective_adjacent(scene, room_id):
        if isinstance(edge, dict) and edge.get("to"):
            height = drop_m(scene, room_id, str(edge["to"]))
            if height is not None:
                out[str(edge["to"])] = height
    return out


def report_drops(before, after, report=None) -> list:
    """`(body, from room, to room, metres)` for every body the beat took
    straight from a room down a drop -- through a way it can pass this beat
    (an opened window, a balcony's open side), never down a stair -- with
    one Director-facing sentence each on `report`. A shut window is passed
    by nobody, so nobody falls through one by accident."""
    from world.spatial import edge_passable, room_of

    out = []
    names = (after or {}).get("positions") or {}
    for body in sorted(names, key=str):
        a, b = room_of(before or {}, body), room_of(after or {}, body)
        if not a or not b or a == b:
            continue
        height = drop_m(after, a, b)
        edge = _direct_edge(after, a, b) if height is not None else None
        if edge is None or not edge_passable(edge, a, body):
            continue
        out.append((str(body), a, b, height))
        if report is not None:
            rooms = _scene_rooms(after)
            onto = rooms.get(b) or {}
            surface = str(onto.get("surface") or "").strip()
            report.append(
                f"{body} went from {(rooms.get(a) or {}).get('name') or a} to "
                f"{onto.get('name') or b} by a way that is a drop of "
                f"{height:g} m" + (f" onto {surface}" if surface else "")
                + ": a fall of that height, whatever the beat makes of it.")
    return out


# ---------------------------------------------------------------------------
# Flight (2026-10-04)
# ---------------------------------------------------------------------------
#
# A body's own height above its floor -- flying, levitating, hanging from a
# rafter, perched on the eaves -- is `stations[body].altitude_m`. Outdoors
# the air over a room is that room, and no ceiling bounds it; indoors the
# ceiling does (`STOREY_M` less a body's own height). Sight and reach read
# it; whether a body coming down landed or fell is the Director's to say.

#: Two bodies this far apart in height, in metres, are not within reach of
#: each other, whatever their cells say.
REACH_ALTITUDE_M = 1.5

#: Off the ground by this much, a body's eye is over every fixture a room
#: holds (`spatial_fov`'s `full` height), and it is seen over them.
CLEAR_ALTITUDE_M = 1.0


def normalize_altitude(scene, room_id, value) -> Optional[float]:
    """A body's altitude in metres, or None for the ground and anything that
    is not a height: a positive number, capped under the ceiling when the
    room is enclosed (`exposure` not `open`)."""
    if value is None or isinstance(value, bool):
        return None
    try:
        height = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(height) or height <= 0:
        return None
    if not _open_air(scene, room_id):
        height = min(height, max(0.0, STOREY_M - TOP_M["standing"]))
    return round(height, 2) if height > 0 else None


def body_altitude_m(scene, name) -> float:
    """How far above its floor a body is, in metres; 0 on the ground."""
    from world.spatial import room_of
    from world.spatial import _ci_get

    station = _ci_get((scene or {}).get("stations") or {}, name)
    if not isinstance(station, dict):
        return 0.0
    return normalize_altitude(scene, room_of(scene, name), station.get("altitude_m")) or 0.0
