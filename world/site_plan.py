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


def _stands_on(scene, a, b) -> bool:
    """Is one of two rooms open ground and the other part of a building
    standing in it? A building stands IN its grounds -- the landing under a
    tower's legs, the yard round a house -- so where their cells meet is the
    building's footprint on the ground, never a contradiction.

    ITS OWN GROUNDS, NOT ANY OPEN GROUND (2026-10-09). The ground a building
    stands in is ground it opens onto: some room of the building -- the
    rooms joined to it through rooms that are not open air, its storeys
    included (`_building_of`) -- has a way onto it. Read as any open room
    under any building, it let a laid-out town stand a chandlery on the
    drying racks beside it, and a dozen houses, sheds and an inn in the
    Blackreed channel south of the reed staithe, none of which opens onto
    the channel (chat 166, the first time its plan was derived). The Larch
    Hill tower still stands on the landing under its legs: its store room
    opens onto it, and the kitchen whose corner fell on it is the store
    room's building."""
    if _open_air(scene, a) == _open_air(scene, b):
        return False
    ground, built = (a, b) if _open_air(scene, a) else (b, a)
    from world.spatial import effective_adjacent, normalize_barrier
    for rid in _building_of(scene, built):
        for edge in effective_adjacent(scene, rid):
            if (isinstance(edge, dict) and str(edge.get("to") or "") == str(ground)
                    and normalize_barrier(edge.get("barrier")) != "wall"):
                return True
    return False


def _building_of(scene, rid) -> frozenset:
    """`rid` and every room joined to it, through any way that is not a wall
    -- a door, an arch, a stair -- by rooms that are not open air: the
    building it is a room of, every storey. Read once a pass."""
    from world.scene_memo import scene_memo

    def build():
        from world.spatial import effective_adjacent, normalize_barrier
        rooms = _scene_rooms(scene)
        seen, frontier = {str(rid)}, [str(rid)]
        while frontier:
            cur = frontier.pop()
            for edge in effective_adjacent(scene, cur):
                other = str((edge or {}).get("to") or "") if isinstance(edge, dict) else ""
                if (other and other in rooms and other not in seen
                        and not _open_air(scene, other)
                        and normalize_barrier(edge.get("barrier")) != "wall"):
                    seen.add(other)
                    frontier.append(other)
        return frozenset(seen)
    return scene_memo(scene, ("site_plan_building_of", str(rid)), build)


def site_overlaps(scene) -> list:
    """`(plan, level, room, other)` for two rooms of one plan and storey
    whose cells land on each other: a plan that does not hold together.
    A building over open ground is not one (`_stands_on`). Sorted, so a
    reroll reports the same pair."""
    out = []
    for plan, levels in sorted(site_plans(scene).items()):
        for level, ids in sorted(levels.items()):
            held: dict = {}
            for rid in ids:
                for cell in site_cells(scene, rid):
                    for other in held.get(cell, ()):
                        pair = (plan, level, other, rid)
                        if pair not in out and not _stands_on(scene, other, rid):
                            out.append(pair)
                    held.setdefault(cell, []).append(rid)
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

#: A floor's difference, in metres, below which two rooms are one level for
#: sight: a step up into a genkan is not a storey.
LEVEL_STEP_M = 1.0


def _open_air(scene, room_id) -> bool:
    room = _scene_rooms(scene).get(room_id) or {}
    return str(room.get("exposure") or "").strip().casefold() == "open"


def elevated_pair(scene, a, b) -> bool:
    """Are rooms `a` and `b` on one plan with floors a storey apart, joined
    through a WALL (a window, a door onto a drop) rather than a vertical way?
    A hatch, a stair or an overlook is looked up and down through by the
    vertical edge's own rules (`spatial_levels`); the line in three
    dimensions is for an opening in a wall a storey up."""
    sa, sb = room_site(scene, a), room_site(scene, b)
    if not sa or not sb or sa["plan"] != sb["plan"] or a == b:
        return False
    if abs(room_elevation_m(scene, a) - room_elevation_m(scene, b)) < LEVEL_STEP_M:
        return False
    from world.spatial import normalize_vertical
    edge = _direct_edge(scene, a, b)
    return not (edge is not None and normalize_vertical(edge.get("vertical")))


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

    sa, sb = room_site(scene, from_room), room_site(scene, to_room)
    if not sa or not sb or sa["plan"] != sb["plan"] or from_room == to_room:
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


# ---------------------------------------------------------------------------
# A plan derived from what the room designer already wrote (2026-10-04;
# room by room, and recomputed every merge, since 2026-10-09)
# ---------------------------------------------------------------------------
#
# The room designer writes every fact a plan needs -- a storey (`level`), a
# measured box (`extent`), doorways with bearings, stairs as vertical edges --
# and only the lab's converter ever wrote a `site`. So a building the planner
# and the designer made had no plan, and none of the height above reached it.
# Here each storey of a building is laid out by its doorways, rooms sharing
# their walls, and the storeys stacked so a stair lands over where it left;
# elevations come from the storeys.
#
# ROOM BY ROOM, NEVER ALL OR NOTHING (2026-10-09). Until then one clash
# anywhere refused the whole connected group its plan, and a town is one
# group: 0 of the 1,069 rooms in the play database's 139 stored scenes
# carried a site, every height-aware reader was dark in play, and chat 166's
# 32-room town went without a plan over five pairs -- four of them an open
# side laid at the wall's start where the side was free to sit anywhere
# along the wall, one a stair between two rooms of one storey read as a
# stack. A room that would land on a room already on the plan is left off it
# (`plan_refusals` says which and why) and everything else stands where its
# doorways put it: measured, the same database's 54 sited rooms after one
# merge became 163 with the classes below fixed and a plan written only
# where its rooms span two storeys (`DESIGN_SITE_PLAN.md`, "A plan derived
# room by room").
#
# A DERIVED SITE IS THE ENGINE'S READING, NOT A FACT. It is marked
# (`DERIVED_KEY`) and recomputed from the rooms every merge, so a stub a
# designer later measures is laid out again where its doorways now put it,
# never left at the corner a guessed square was given; a beat may re-measure
# a room whose site was derived (`spatial_merge` holds only a decided site's
# box); and the layout tier, which lays a planned building out by code,
# still may -- a derived site keeps a building from it only where it lies on
# a plan a decided site holds, the frame of another building's solve
# (`layout_bridge._on_a_plan`). A DECIDED site -- one the layout tier
# solved, the lab converter wrote or a host placed -- is kept where it
# stands, and the derivation grows from it.
#
# RECOMPUTED, NEVER RESHUFFLED. Every merge lays the plan out again, and
# what stood on it at the last merge is where that starts: a group is grown
# from the room its plan was grown from, where it stood, or from any room of
# it that stood on the plan (`_lay_group`). A room keeps the ground it stood
# on against a room that comes onto it -- one added since, or one whose own
# place moved -- while its doorway still puts it there; a room whose place
# moved, re-measured or hung from a room laid elsewhere, claims nothing and
# is laid as one reading of the rooms lays it; an open side holds its side,
# not a place along it, and slides, its storeys with it, for a room with one
# place -- never while somebody stands in it; a room no chain of doorways reaches is laid where it stood while it
# stands clear there; a room of another group on the same plan -- the far
# half of a town whose joining walk was lost -- is ground nothing may land
# on; and a room that joins two plans joins them only where both stand
# whole (`_layout`, `_lay_group`). So a room added later never takes the
# ground of a room still standing where it stood (it is the one refused, and
# named) -- save along an open side nobody stands in, which slides along its
# wall -- a group that splits keeps both halves where they stood, and the
# readers see one plan where one plan was. Played forward through the play
# database's stored checkpoints, as commits store sites, the eighteen chats
# with a plan hold 173 sited rooms where round two's ordering, which laid
# whatever stood before anything else, held 158 -- chat 165 14 of 30 rooms
# where it held 7, chat 27 10 of 13 where it held 3 -- and no room a body
# stood in moved or left the plan (2026-10-09, re-review).

_UNIT4 = {"n": (0, -1), "s": (0, 1), "e": (1, 0), "w": (-1, 0)}

#: The key a site the derivation wrote carries, True. A site without it was
#: decided -- solved by the layout tier, converted from the lab, placed by a
#: host -- and stands where it was put; one with it is recomputed every
#: merge (`derive_site_plans`). Every reader of where a room stands
#: (`room_site`, `normalize_site`) reads both alike: a derived site is a
#: site. Sites stored before 2026-10-09 carry no mark and are kept as
#: decided, which is what the derivation then made of them.
DERIVED_KEY = "derived"
#: The key naming the room a derived plan was laid out from, on every site
#: of that plan. Recomputed every merge, a plan is grown from that room
#: again, where it stood: a room added since -- a shed drafted off the yard,
#: whose id sorts first -- never becomes the room the plan starts from
#: (measured on the doorway search's own two-storey fixture: grown from the
#: new shed, the whole plan was refused and two collisions it had made good
#: came back). The start alone is not the whole of it: a room still standing
#: where it stood is laid before any room that comes onto its ground
#: (`_layout`), so a newcomer that lands on a room of the plan is the one
#: left off it -- or, along an open side nobody stands in, the room slides.
ORIGIN_KEY = "origin"


def site_is_derived(value) -> bool:
    """Is `value`, a room's stored `site`, one the derivation wrote?"""
    return isinstance(value, dict) and value.get(DERIVED_KEY) is True


def decided_site(scene, room_id) -> Optional[dict]:
    """The room's site when it was decided rather than derived
    (`DERIVED_KEY`), normalized; None for a derived site or none."""
    room = _scene_rooms(scene).get(room_id)
    if not isinstance(room, dict) or site_is_derived(room.get("site")):
        return None
    return normalize_site(room.get("site"))


def _placeable(scene, rid) -> bool:
    room = _scene_rooms(scene).get(rid)
    return isinstance(room, dict) and not room.get("parent_entity")


def _neighbour_offset(scene, a, a_xy, b):
    """Where `b` stands if its doorway onto `a` meets `a`'s across the wall,
    or None when the doorway has no placed cell on a straight wall."""
    from world.spatial import _door_cells
    da, ba = _door_cells(scene, a, b)
    db, _bb = _door_cells(scene, b, a)
    if not da or not db or ba not in _UNIT4:
        return None
    ux, uy = _UNIT4[ba]
    target = (a_xy[0] + da[0][0] + ux, a_xy[1] + da[0][1] + uy)
    return (target[0] - db[0][0], target[1] - db[0][1])


def _open_side(scene, room, other):
    """``(cells, wall)`` of `room`'s opening onto `other` when it is an open
    side -- the whole wall (`spatial_geometry`'s `width: "wall"`: an open way
    between two unenclosed rooms, a rail) -- else None."""
    from world.spatial import anchor_cells, door_anchor_id
    rec = anchor_cells(scene, room).get(door_anchor_id(other)) or {}
    if rec.get("source") != "side" or rec.get("dir") not in _UNIT4 or not rec.get("cells"):
        return None
    return list(rec["cells"]), rec["dir"]


def _spots(scene, a, a_xy, b) -> list:
    """Where `b` may stand on the plan through its doorway onto `a`, nearest
    the doorways' own placement first.

    A DOORWAY HAS ONE PLACE; AN OPEN SIDE DOES NOT. A doorway's two cells meet
    across the wall, and that is one place (`_neighbour_offset`). An open side
    is the whole of its wall, so the two walls need only touch: every reader
    lays the far room flush with the wall's start because something had to be
    chosen, and nothing in the world chose it. Live, chat 166 (2026-10-07):
    the reed staithe's open east side laid the twelve-pace boat sheds flush
    with its north end, onto the Gale house that fronts the low walk beside
    it; the drying racks, seven paces deep, hung four paces south of the
    three-pace high walk they open off, onto the low walk and the market walk;
    and the reed flats' sixty-pace side sat one row onto the landing stage.
    Each could stand clear further along its side. So past the first, an
    open side offers every place along it where the two walls still meet,
    nearest first; the plan takes the first where the room lands on no room, and the
    readers that lay a room beside its neighbour follow the plan there
    (`plan_offset`)."""
    base = _neighbour_offset(scene, a, a_xy, b)
    if base is None:
        return []
    mine, theirs = _open_side(scene, a, b), _open_side(scene, b, a)
    if mine is None and theirs is None:
        return [base]
    from world.spatial import _door_cells
    da, wall = _door_cells(scene, a, b)
    db, _wall = _door_cells(scene, b, a)
    axis = 0 if wall in ("n", "s") else 1
    a_lo = min(c[axis] for c in da) + a_xy[axis]
    a_hi = max(c[axis] for c in da) + a_xy[axis]
    b_lo = min(c[axis] for c in db) + base[axis]
    b_hi = max(c[axis] for c in db) + base[axis]
    shifts = sorted(range(a_lo - b_hi, a_hi - b_lo + 1), key=lambda s: (abs(s), s))
    return [(base[0] + s, base[1]) if axis == 0 else (base[0], base[1] + s)
            for s in shifts]


def plan_offset(scene, a, b) -> Optional[tuple]:
    """``(dx, dy)`` from room `a`'s grid to room `b`'s on their plan, when
    both stand on one plan and one storey and their doorway meets across the
    wall there; None otherwise.

    THE READERS THAT LAY A ROOM BESIDE ITS NEIGHBOUR FOLLOW THE PLAN. The
    sight, light and sound fields (`spatial_fov.room_field`) and the layout
    lint (`spatial_lint.layout_rooms`) lay a neighbour where the two doorways'
    first cells meet; where the plan put it somewhere else that the doorway
    still reaches -- an open side the derivation slid along (`_spots`) -- the
    field and the plan would be two answers to where the room is. Where the
    plan lays a room by its doorway, this is exactly the offset the doorway
    gives, so a reader that follows it is unchanged; where the doorway does
    not meet on the plan, the plan does not say how the two rooms touch and
    the reader keeps its own rule."""
    from world.spatial import _door_cells
    sa, sb = room_site(scene, a), room_site(scene, b)
    if not sa or not sb or sa["plan"] != sb["plan"] or str(a) == str(b):
        return None
    if room_level(scene, a) != room_level(scene, b):
        return None
    da, wall = _door_cells(scene, a, b)
    db, _wall = _door_cells(scene, b, a)
    if not da or not db or wall not in _UNIT4:
        return None
    rel = (sb["x"] - sa["x"], sb["y"] - sa["y"])
    ux, uy = _UNIT4[wall]
    front = {(x + ux, y + uy) for x, y in da}
    if not front & {(x + rel[0], y + rel[1]) for x, y in db}:
        return None
    return rel


def _links(scene) -> dict:
    """``{room: {other: vertical}}``: every room joined to each room by an
    edge EITHER of the two declares, a wall included, and whether that way
    is vertical -- the room's own edge deciding where both declare one.
    Read once a pass.

    BOTH WAYS, WALLS INCLUDED. `effective_adjacent` derives a far side's edge
    onto a room for every barrier but a wall, which is right for passage --
    a wall is no way through -- and wrong for a plan: a wall the far room
    declares is still where the two stand side by side. Live, chat 27's
    deep-shelter corridor declared the wall it shares with the lobby on its
    own side only; grown from the lobby, where the plan stood, the plan
    never reached it nor the six rooms past it -- played forward through
    the stored checkpoints, 3 of 13 rooms sited where a fresh reading, which
    happens to start from the corridor, sites 10 (review of 2026-10-09)."""
    from world.scene_memo import scene_memo

    def build():
        from world.spatial import effective_adjacent, normalize_vertical
        rooms = _scene_rooms(scene)
        out = {str(rid): {} for rid in rooms}
        for rid in rooms:
            for edge in effective_adjacent(scene, rid):
                other = str((edge or {}).get("to") or "") if isinstance(edge, dict) else ""
                if not other or other not in out or other == str(rid):
                    continue
                vertical = bool(normalize_vertical(edge.get("vertical")))
                if not edge.get("implicit"):
                    out[str(rid)][other] = vertical
                else:
                    out[str(rid)].setdefault(other, vertical)
                out[other].setdefault(str(rid), vertical)
        return out
    return scene_memo(scene, ("site_plan_links",), build)


def _site_group(scene, start) -> set:
    """Every placeable room joined to `start` by any edge, vertical
    included, declared on either side (`_links`): one building and its
    grounds, as the derivation groups them."""
    links = _links(scene)
    group, frontier = {str(start)}, [str(start)]
    while frontier:
        cur = frontier.pop()
        for to in links.get(cur, {}):
            if to not in group and _placeable(scene, to):
                group.add(to)
                frontier.append(to)
    return group


def _measured(scene, rid) -> bool:
    from world.spatial import room_grid
    return room_grid(scene, rid).measured


def _laying_key(scene, rid) -> tuple:
    """Where two rooms cannot both stand, the one the plan keeps: the
    measured before the guessed (a room with no `extent` is its size tier's
    square, nobody's measurement), a building before open ground, whose
    loose rectangle is the likelier to be wrong, then id."""
    return (not _measured(scene, rid), _open_air(scene, rid), str(rid))


def _laying_order(scene, rooms) -> list:
    """`rooms` in the order the layout lays the rooms its frontier reaches
    at once (`_laying_key`)."""
    return sorted(rooms, key=lambda rid: _laying_key(scene, rid))


def _prior(scene) -> dict:
    """``{room: (plan, (x, y), origin, elev_m)}``: where each room the
    derivation placed stood at the last merge -- its derived site
    (`DERIVED_KEY`, `ORIGIN_KEY`), read before the derivation recomputes it
    -- and the height of the storey it stood on."""
    out = {}
    for rid, room in _scene_rooms(scene).items():
        site = room.get("site") if isinstance(room, dict) else None
        if not site_is_derived(site):
            continue
        norm = normalize_site(site)
        if norm:
            out[str(rid)] = (norm["plan"], (norm["x"], norm["y"]),
                             str(site.get(ORIGIN_KEY) or ""), norm["elev_m"])
    return out


def _storey_kept(scene, rid, prior) -> bool:
    """Is `rid` on the storey it stood on at the last merge? A beat can put
    a room on another storey -- chat 160's crash site, moved onto the
    elevator shaft's storey where the shaft stands -- and where it stood is
    then only its column, never its place (review of 2026-10-09)."""
    elev = prior[rid][3]
    return elev is None or abs(float(elev) - room_level(scene, rid) * STOREY_M) < 1e-6


def _groups(scene) -> list:
    """Every group the derivation lays out -- the placeable rooms joined by
    any edge, vertical included (`_site_group`) -- each a set, in the order
    of its first room's id."""
    rooms = _scene_rooms(scene)
    seen, out = set(), []
    for first in sorted(rooms, key=str):
        if first in seen or not _placeable(scene, first):
            continue
        group = _site_group(scene, first)
        seen |= group
        out.append(group)
    return out


def _carries(scene, a, b, vertical) -> bool:
    """Can the derivation lay `b` from `a` alone -- a doorway with a cell on
    a straight wall on both sides, between two rooms of one storey, or a
    stair between two storeys?"""
    same = room_level(scene, a) == room_level(scene, b)
    if vertical:
        return not same
    return same and _neighbour_offset(scene, a, (0, 0), b) is not None


def _fresh_start(scene, group):
    """The room a plan laid out for the first time is grown from, in the
    order the layout lays rooms (`_laying_order`): the group's first that
    reaches another room -- a measured building before a guessed square or
    open ground, so neither claims the ground a measured building stands
    on -- else its first."""
    ordered = _laying_order(scene, group)
    return next((rid for rid in ordered if _reaches(scene, group, rid)), ordered[0])


def _fresh_name(scene, start, reserved) -> str:
    """The name a plan laid out for the first time carries: the region of
    the room it is grown from, else that room's id -- and, where a plan of
    the scene already carries that name, the two together, so two frames
    never share one name. Two buildings of one region, each of two storeys
    and joined by no room, were each laid out from (0, 0) under the region's
    name, one on the other (review of 2026-10-09)."""
    base = str(_scene_rooms(scene)[start].get("region") or start)
    name, n = base, 1
    while name in reserved:
        n += 1
        name = f"{base}:{start}" if n == 2 else f"{base}:{start}:{n - 1}"
    return name


def _reaches(scene, group, rid) -> bool:
    """Does the derivation reach another room of `group` from `rid` alone
    (`_carries`), through an edge either of the two declares?"""
    return any(other in group and other != rid and _carries(scene, rid, other, vertical)
               for other, vertical in _links(scene).get(str(rid), {}).items())


def _cells_at(scene, rid, at) -> set:
    """`rid`'s cells, storey first, with its grid's corner at `at`."""
    from world.spatial import room_grid
    level = room_level(scene, rid)
    return {(level, x + at[0], y + at[1]) for x, y in room_grid(scene, rid).cells}


def _layout(scene, group, starts, *, plan=None, prior=None, obstacles=None):
    """``(placed, refused)``: where the derivation lays `group` out on
    `plan`, and the rooms it could not lay.

    `placed` is ``{room: (x, y)}``, grown from `starts` (``{room: (x, y)}``:
    the plan's decided sites, or the room it is grown from where it stands)
    across doorways on a storey -- an open side at the nearest place along
    it where the room lands on nothing (`_spots`) -- and up or down a stair
    between two storeys, landing over where it left, through an edge either
    room declares (`_links`). A room is placed only where it lands on no
    room already placed and on none of `obstacles` (``{room: (x, y)}``:
    rooms of other groups standing on the same plan) -- a building standing
    in ground it opens onto is no clash (`_stands_on`). `refused` is
    ``{room: {"at": (x, y), "lands_on": [rooms], "misses": [rooms], "via":
    room}}`` for each room no doorway tried onto it could lay -- where its
    first doorway would have put it, what it would have stood on there, and
    the rooms on the plan whose doorway onto it would not have met its own.

    A ROOM KEEPS THE GROUND IT STOOD ON AGAINST A ROOM THAT COMES ONTO IT.
    `prior` (`_prior`) is where the derived rooms stood at the last merge. A
    room that stood on THIS plan, on the storey it stands on now, and that
    the doorway it is offered through still puts exactly where it stood,
    has a claim, and every claim is laid before any room without one: the
    part of the plan that stands where it stood is laid first, as it stood.
    So a room added since -- a measured bakery drafted onto the street, its
    door a tenth of the way along the wall the chandler's opens off -- comes
    onto the chandler's ground and is the one refused and named, merge after
    merge; laid by measurement and id alone it took the chandler's place, a
    body standing in it (review of 2026-10-09). A room whose place MOVED --
    its box re-measured, a doorway moved, a room it hangs from laid
    elsewhere -- claims nothing, and is laid as a fresh reading lays it,
    after the claims, by `_laying_key`, a room that stood before one that
    did not where the two are otherwise alike. Ordered by what stood alone,
    a guessed boat-shed square laid against a six-pace main walk kept its
    first claim after the walk was measured at fourteen: the chandlery and
    the rope bridge were refused, and the whole cross-walk side of the town
    never reached the plan -- played forward through chat 165's stored
    checkpoints, 7 of 30 rooms where a fresh reading sites 14.

    AN OPEN SIDE HOLDS ITS SIDE, NOT A PLACE ALONG IT. Where along an open
    side a room stands is nobody's measurement (`_spots`). A room with one
    place -- a doorway's, a stair's -- that would land on rooms laid along
    an open side has each of them slide along it, with the storeys stacked
    on it, to the nearest place clear of the room, where every doorway onto
    a room that stays still meets -- so a room laid from it by a doorway
    holds it where it is -- and is refused only where they cannot; a room
    with many places takes one that is clear, or is the one refused. Played forward, chat 166's boat sheds, laid at the reed
    staithe's north end before the Gale house was written onto the low walk
    beside it, refused the house; one reading stands both, the sheds and the
    loft over them five paces down the staithe, which is the case the slide
    exists for. Only a stack slides: carrying the rooms laid from it too,
    the main walk of chat 165, laid along the landing stage with the town
    hanging off it, slid the whole town three to six paces at five of its
    six checkpoints played forward.

    WHAT STOOD AND NOTHING REACHES IS LAID WHERE IT STOOD. A room that stood
    on this plan and that no chain of doorways from the rooms placed can
    reach any more -- the far half of a town whose joining walk was lost, a
    stretch whose doorway lost its bearing -- is laid where it stood, before
    any room without a claim, while it lands on nothing there and every
    doorway of it onto a room on the plan meets; one a chain still reaches,
    through a room added since included, is laid by that chain (a lane
    replaced by a longer bridge, a porch put between a street and a shop:
    the far room follows the doorways the beat wrote, never the ones it
    replaced). What stood and is reached by no chain that could lay it is
    tried where it stood once the frontier is spent. A room on the storey
    it stood on is tried before one a beat moved to another, so which of two
    rooms a beat puts on one spot keeps it never turns on their ids. One
    not clear where it stood is left off, and -- no doorway having been
    tried for it -- is not among `refused`.

    EVERY DOORWAY MEETS, OR THE ROOM IS NOT ON THE PLAN. A room is laid by
    one doorway; its others onto rooms already on the plan must meet theirs
    across the wall too, or the plan holds two places for one doorway and
    the readers that follow it (`plan_offset`) have none. Live, chat 27's
    shelter: a descent declared to lie east of the chamber whose east is the
    passage -- bearings no plane draws -- was laid by one doorway with two
    left unmet, and the layout lint's rows naming it fell silent once it
    stood on the plan.

    A STAIR BETWEEN TWO ROOMS OF ONE STOREY IS NO STACK. Stacking was the
    reading of a stair that joins two storeys; where both rooms are one
    storey -- chat 166's Gale house landing, up a stair from the low walk and
    written on the walk's own storey -- it laid the landing on the walk.
    Such a stair places nothing; the room is placed by another doorway, or
    not at all."""
    import heapq
    from world.spatial import _door_cells, room_grid
    links = _links(scene)
    prior = prior or {}
    placed = {rid: tuple(at) for rid, at in starts.items()}
    fixed = frozenset(placed)
    held, shapes, boxes, standing, via = {}, {}, {}, {}, {}
    own_sets, free_at, state = {}, {}, [0]
    here = {rid: prior[rid] for rid in group
            if plan is not None and rid in prior and prior[rid][0] == plan}
    claims = {rid: tuple(rec[1]) for rid, rec in here.items() if _storey_kept(scene, rid, prior)}
    stood = frozenset(rid for rid in group if rid in prior)
    seeds = sorted(here, key=lambda rid: (rid not in claims,) + _laying_key(scene, rid))
    tried = set()

    def shape(rid):
        if rid not in shapes:
            shapes[rid] = (room_level(scene, rid), tuple(room_grid(scene, rid).cells))
        return shapes[rid]

    def box(rid, at):
        """`rid`'s storey and the box round its cells standing `at`."""
        if rid not in boxes:
            own = shape(rid)[1] or ((0, 0),)
            boxes[rid] = (min(x for x, _y in own), min(y for _x, y in own),
                          max(x for x, _y in own), max(y for _x, y in own))
        x0, y0, x1, y1 = boxes[rid]
        return (shape(rid)[0], x0 + at[0], y0 + at[1], x1 + at[0], y1 + at[1])

    def meets_box(a, b):
        return a[0] == b[0] and a[1] <= b[3] and b[1] <= a[3] and a[2] <= b[4] and b[2] <= a[4]

    def cells(rid, at):
        level, own = shape(rid)
        return [(level, x + at[0], y + at[1]) for x, y in own]

    def lands(rid, at, every=True):
        """The rooms on the plan `rid` lands on standing `at`; with `every`
        False, at most the first -- a spot past the first is only asked
        whether it is clear. A pair's verdict (`_stands_on`) is read once."""
        level, own = shape(rid)
        out, met = set(), set()
        for x, y in own:
            for other in held.get((level, x + at[0], y + at[1]), ()):
                if other == rid or other in met:
                    continue
                met.add(other)
                if (other, rid) not in standing:
                    standing[(other, rid)] = _stands_on(scene, other, rid)
                if not standing[(other, rid)]:
                    out.add(other)
                    if not every:
                        return out
        return out

    def misses(rid, at):
        """The rooms on the plan, on `rid`'s storey, whose doorway onto `rid`
        would not meet `rid`'s across the wall with `rid` standing `at`."""
        out = []
        for other, vertical in links.get(rid, {}).items():
            if other not in placed or other == rid or vertical:
                continue
            if room_level(scene, other) != room_level(scene, rid):
                continue
            mine, wall = _door_cells(scene, rid, other)
            theirs, _wall = _door_cells(scene, other, rid)
            if not mine or not theirs or wall not in _UNIT4:
                continue                    # a doorway with no place claims none
            ux, uy = _UNIT4[wall]
            front = {(x + at[0] + ux, y + at[1] + uy) for x, y in mine}
            if not front & {(x + placed[other][0], y + placed[other][1]) for x, y in theirs}:
                out.append(other)
        return out

    def clear(rid, at):
        return not misses(rid, at) and not lands(rid, at, every=False)

    def put(rid, at):
        placed[rid] = tuple(at)
        for cell in cells(rid, at):
            held.setdefault(cell, []).append(rid)

    def lift(rid):
        for cell in cells(rid, placed[rid]):
            held[cell].remove(rid)
        return placed.pop(rid)

    def spots(a, b, vertical):
        if room_level(scene, a) == room_level(scene, b):
            return [] if vertical else _spots(scene, a, placed[a], b)
        return [placed[a]] if vertical else []

    def entry(b, a, vertical):
        claim = b in claims and claims[b] in spots(a, b, vertical)
        return (not claim,) + _laying_key(scene, b)[:2] + (b not in stood, b, a, vertical)

    def offer(a):
        for b, vertical in sorted(links.get(a, {}).items()):
            if b in group and b not in placed:
                heapq.heappush(frontier, entry(b, a, vertical))

    def stand(rid, at, frm=None):
        put(rid, at)
        state[0] += 1
        refused.pop(rid, None)
        if frm is not None:
            via[rid] = frm
        offer(rid)

    def stacked(a, b):
        """Was `b` laid over or under `a`, by a stair between two storeys?"""
        return links.get(a, {}).get(b) and room_level(scene, a) != room_level(scene, b)

    # The rooms a body stands in now: the one ground a slide never moves.
    occupied = {str(room) for room in ((scene or {}).get("positions") or {}).values()
                if isinstance(room, str) and room}

    def unit(rid):
        """`rid` and every room stacked over or under it, at any remove: one
        building's storeys, which stand on one footprint."""
        out, todo = [rid], [rid]
        while todo:
            cur = todo.pop()
            for child in sorted(r for r, frm in via.items()
                                if frm == cur and r in placed and stacked(cur, r)):
                out.append(child)
                todo.append(child)
        return out

    def side_root(rid):
        """The room `rid` stands on -- itself, or the room its storey is
        stacked on -- when that room was laid along an open side; else None.
        Only a stack slides: a room laid from it by a doorway stays, and the
        doorway onto it then refuses the slide (`clear`)."""
        cur = rid
        while cur in via and stacked(via[cur], cur):
            cur = via[cur]
        frm = via.get(cur)
        if cur in fixed or frm is None or room_level(scene, frm) != room_level(scene, cur):
            return None
        if _open_side(scene, frm, cur) is None and _open_side(scene, cur, frm) is None:
            return None
        return cur

    def free(root, members, was):
        """The places along its open side `root` -- with `members`, lifted --
        may stand, every doorway onto a room that stays meeting and nothing
        landed on, nearest first: what a slide may choose from, whichever
        room it makes room for. Read once a state of the plan (`state`), so
        a dozen rooms refused against one stretch of open ground -- chat
        166's Blackreed channel, 3,200 cells along 89 places -- ask once."""
        key = (root, state[0])
        if key not in free_at:
            out = []
            for spot in spots(via[root], root, False):
                if spot == was[root]:
                    continue
                dx, dy = spot[0] - was[root][0], spot[1] - was[root][1]
                new = {rid: (was[rid][0] + dx, was[rid][1] + dy) for rid in members}
                if any(misses(rid, new[rid]) for rid in members):
                    continue
                if any(lands(rid, new[rid], every=False) for rid in members):
                    continue
                out.append(new)
            free_at[key] = out
        return free_at[key]

    def make_room(b, at, hit):
        """Slide each room of `hit` -- with the storeys stacked on it, as a
        shed and its loft move as one -- along the open side it was laid by,
        to the nearest place clear of `b` standing `at`, every doorway onto a
        room that stays still meeting and no stair onto one broken: all of
        them, or none. A stack with a body standing in any of its rooms never
        slides (`occupied`)."""
        roots = []
        for rid in sorted(hit, key=str):
            root = side_root(rid)
            if root is None:
                return False
            if root not in roots:
                roots.append(root)
        keep, moved = [(box(b, at), set(cells(b, at)))], []

        def kept(rid, at_):
            """Does `rid` standing `at_` land on what the slide keeps clear --
            the room it makes room for, and what it has slid already?"""
            mine = box(rid, at_)
            level, own = shape(rid)
            for edge, taken in keep:
                if not meets_box(mine, edge):
                    continue
                if len(taken) < len(own):
                    if rid not in own_sets:
                        own_sets[rid] = frozenset(own)
                    if any(lv == level and (x - at_[0], y - at_[1]) in own_sets[rid]
                           for lv, x, y in taken):
                        return True
                elif any((level, x + at_[0], y + at_[1]) in taken for x, y in own):
                    return True
            return False

        def undo():
            for members, was in reversed(moved):
                for rid in members:
                    lift(rid)
                for rid in members:
                    put(rid, was[rid])
            if moved:                       # back as it was, under a state of its own
                state[0] += 1
            return False

        for root in roots:
            members = unit(root)
            inside = set(members)
            # A ROOM SOMEBODY STANDS IN NEVER SLIDES (review V3-2, 2026-10-09):
            # where along an open side a room stands is nobody's measurement,
            # but the ground a mind stands on is the stability the plan owes
            # it -- slid, the sheds moved three paces with Mara in them and her
            # place on the plan with them. The newcomer is refused and named.
            if inside & occupied or inside & fixed or any(
                    vertical and other in placed and other not in inside
                    for rid in members for other, vertical in links.get(rid, {}).items()):
                return undo()
            was = {rid: placed[rid] for rid in members}
            for rid in members:
                lift(rid)
            if moved:                       # the plan has moved under it
                state[0] += 1
            for new in free(root, members, was):
                if any(kept(rid, new[rid]) for rid in members):
                    continue
                for rid in members:
                    put(rid, new[rid])
                    keep.append((box(rid, new[rid]), set(cells(rid, new[rid]))))
                moved.append((members, was))
                break
            else:
                for rid in members:
                    put(rid, was[rid])
                return undo()
        state[0] += 1
        return True

    def reachable():
        """The rooms of `group` a chain of doorways and stairs that could lay
        them reaches from the rooms placed, through rooms not yet placed."""
        seen = set(placed)
        frontier_ = list(placed)
        while frontier_:
            cur = frontier_.pop()
            for other, vertical in links.get(cur, {}).items():
                if other in group and other not in seen and _carries(scene, cur, other, vertical):
                    seen.add(other)
                    frontier_.append(other)
        return seen

    def seed(only_unreached):
        """Lay the first room that stood on this plan, where it stood, if it
        is clear there; with `only_unreached`, only one no chain reaches. A
        room is tried once each way: what a chain reaches stays reached as
        the plan fills, and ground taken stays taken."""
        waiting = [rid for rid in seeds
                   if rid not in placed and (rid, only_unreached) not in tried]
        if not waiting:
            return False
        reached = reachable() if only_unreached else frozenset()
        for rid in waiting:
            tried.add((rid, only_unreached))
            if rid in reached:
                continue
            at = tuple(here[rid][1])
            if clear(rid, at):
                stand(rid, at)
                return True
        return False

    for rid, at in sorted((obstacles or {}).items(), key=lambda kv: str(kv[0])):
        for cell in cells(rid, tuple(at)):
            held.setdefault(cell, []).append(rid)
    for rid in sorted(placed, key=str):
        for cell in cells(rid, placed[rid]):
            held.setdefault(cell, []).append(rid)
    frontier, refused = [], {}
    for rid in sorted(placed, key=str):
        offer(rid)
    while True:
        if (not frontier or frontier[0][0]) and seed(only_unreached=True):
            continue
        if not frontier:
            if seed(only_unreached=False):
                continue
            break
        key = heapq.heappop(frontier)
        b, a, vertical = key[-3:]
        if b in placed:
            continue
        now = entry(b, a, vertical)
        if now[0] != key[0]:
            heapq.heappush(frontier, now)  # the room it hangs from slid since
            continue
        offered = spots(a, b, vertical)
        if not now[0]:
            offered = [claims[b]] + [spot for spot in offered if spot != claims[b]]
        first = None
        for at in offered:
            hit = lands(b, at, every=first is None)
            astray = misses(b, at) if (first is None or not hit) else ()
            if not hit and not astray:
                stand(b, at, a)
                break
            if first is None:
                first = (at, hit, astray)
        else:
            # A ROOM WITH ONE PLACE MAKES ROOM; one with many takes any that
            # is clear, and where none is, it is the one refused.
            if (len(offered) == 1 and first is not None and first[1] and not first[2]
                    and make_room(b, offered[0], first[1])):
                stand(b, offered[0], a)
            elif first is not None and b not in refused:
                refused[b] = {"at": first[0], "lands_on": sorted(first[1], key=str),
                              "misses": sorted(first[2], key=str), "via": a}
    return placed, refused


def _lay_group(scene, group, prior, standing) -> list:
    """One group laid out: ``[{"rooms", "plan", "placed", "refused",
    "anchors", "origin"}]`` -- one record, or one a plan where a join is
    refused (below); `plan` None for a plan laid out for the first time,
    which is named once it is written (`_fresh_name`); `origin` the room a
    plan with no decided site is grown from.

    ONE PLAN A GROUP. Where decided sites name several plans -- two buildings
    the layout tier solved off one street -- the group is laid on the plan
    holding the most of them (`anchors`), and a room decided onto another
    plan stands on that one: two frames are never read as one (each solve's
    coordinates are its own).

    GROWN FROM WHERE IT STOOD. A group no decided site holds is grown from
    what stood on its plan at the last merge (`prior`, `_prior`): the room
    its plan was grown from (`ORIGIN_KEY`), else the first room of it that
    stood, a room on the storey it stood on before one a beat moved to
    another, in the order the layout lays rooms -- each where it stood, on
    the plan it stood on, where it lands on none of the rooms other groups
    hold on that plan (`standing`). So the half of a town whose joining walk
    was lost, holding no origin, is grown from a room of its own, where it
    stood, under the plan's name: started afresh from (0, 0) under the
    region's name, it was laid on the other half -- two storeys of
    `site_plan_overlap` rows nobody could clear, and a far tower down the
    road said hidden behind a hall that really stood across the lane (review
    of 2026-10-09). Only a group with nothing that stood, or nothing that
    stood still clear, is laid out afresh (`_fresh_start`).

    A JOIN STANDS WHOLE, OR NOT AT ALL. A room added later can join two
    groups that stood on two plans -- an alley between two buildings, each
    of two storeys. The group is laid on the plan more of its rooms stood
    on; where that layout lays every room that stood on the other plan, on
    the storey it stood on, the two are one plan from then on, as the
    doorways the beat wrote put them. Where it does not, each plan's rooms
    are laid where they stood, on their own plan, and the room the beat
    added stays with the first: laid into the first plan's frame, the
    second building's hall landed on the alley, or the alley on the first
    building's hall, and the second building -- a body upstairs in it --
    lost every site, named nowhere (review of 2026-10-09)."""
    by_plan = {}
    for rid in group:
        site = decided_site(scene, rid)
        if site:
            by_plan.setdefault(site["plan"], {})[rid] = (site["x"], site["y"])

    def others(plan, rooms):
        return {rid: at for rid, at in (standing.get(plan) or {}).items() if rid not in rooms}

    def record(rooms, plan, placed, refused, anchors, origin):
        return {"rooms": rooms, "plan": plan, "placed": placed, "refused": refused,
                "anchors": anchors, "origin": origin}

    def grown(rooms, plan):
        """`rooms` laid on `plan` from the first of them that stood there and
        is clear where it stood, or None."""
        starts = sorted((rid for rid in rooms if rid in prior and prior[rid][0] == plan),
                        key=lambda rid: (not _storey_kept(scene, rid, prior),
                                         prior[rid][2] != rid) + _laying_key(scene, rid))
        for start in starts:
            at = prior[start][1]
            blocking = others(plan, rooms)
            mine = _cells_at(scene, start, at)
            if any(mine & _cells_at(scene, rid, xy) for rid, xy in blocking.items()):
                continue
            placed, refused = _layout(scene, rooms, {start: at}, plan=plan, prior=prior,
                                      obstacles=blocking)
            if len(placed) >= min(2, len(rooms)):
                return record(rooms, plan, placed, refused, {}, start)
        return None

    def anchored(rooms, plan, anchors):
        placed, refused = _layout(scene, rooms, anchors, plan=plan, prior=prior,
                                  obstacles=others(plan, rooms))
        return record(rooms, plan, placed, refused, anchors, None)

    def fresh(rooms):
        start = _fresh_start(scene, rooms)
        placed, refused = _layout(scene, rooms, {start: (0, 0)})
        return record(rooms, None, placed, refused, {}, start)

    if by_plan:
        plan = sorted(by_plan, key=lambda p: (-len(by_plan[p]), p))[0]
        anchors = by_plan[plan]
        group = group - {rid for p, held in by_plan.items() if p != plan for rid in held}
        main = anchored(group, plan, anchors)
    else:
        counts = {}
        for rid in group:
            if rid in prior:
                counts[prior[rid][0]] = counts.get(prior[rid][0], 0) + 1
        main = None
        for plan in sorted(counts, key=lambda p: (-counts[p], p)):
            main = grown(group, plan)
            if main is not None:
                break
        if main is None:
            return [fresh(group)]
    joined = {}
    for rid in main["rooms"]:
        if rid in prior and prior[rid][0] != main["plan"] and rid not in main["anchors"]:
            joined.setdefault(prior[rid][0], set()).add(rid)
    if all(rid in main["placed"] for rooms in joined.values() for rid in rooms
           if _storey_kept(scene, rid, prior)):
        return [main]
    keep = main["rooms"] - set().union(*joined.values())
    if main["anchors"]:
        out = [anchored(keep, main["plan"], main["anchors"])]
    else:
        out = [grown(keep, main["plan"]) or fresh(keep)] if keep else []
    for plan in sorted(joined):
        out.append(grown(joined[plan], plan) or fresh(joined[plan]))
    return out


def _derive(scene, prior=None, *, every=False) -> list:
    """The derivation's whole answer: ``[{"rooms", "plan", "placed",
    "refused", "anchors", "origin", "written", "stands"}]``, one record a
    group (`_lay_group`; one a plan where a join is refused), in the order
    of each group's first room, the groups of two storeys first. A group of
    one storey that never stood on a plan is laid out only when `every`
    asks -- the frontage's plane -- from a fresh start, and never written.
    `prior` is where the derived rooms stood (`_prior`), read off the scene
    when not given. `stands` is whether the record's plan stands once the
    pass is done -- decided sites and written ones spanning two storeys --
    whether or not this record wrote any of it.

    A PLAN IS WRITTEN WHERE ITS ROOMS SPAN TWO STOREYS: at least two rooms
    laid out, one of them not decided already, on two storeys or more. A
    group whose rooms on another storey the plan refused or could not reach
    is, on the plan, a group of one storey, and a plan of one storey gives
    height nothing to do while it changes far sight -- the owner's call for
    every one-storey group (review of 2026-10-09: chat 40's roost stair
    refused, a plan of three rooms at -3 m was written for its room). A
    group of one storey that stood on a plan -- the half of a town without a
    loft, cut off when the lane between was lost -- is laid where it stood,
    on that plan, while the plan still spans two storeys: it is part of a
    plan that stands, never a plan of its own.

    WHAT STANDS ON A PLAN, AS THE PASS GOES (`standing`, ``{plan: {room: (x,
    y)}}``): every decided site, and every derived room where it stood until
    its own group is laid again -- then where that group laid it, or nowhere
    if its plan is not written. Each group is laid with the rooms other
    groups hold on its plan as ground nothing may land on. A plan laid out
    for the first time takes a name no plan of the scene carries, or carried
    at the last merge (`_fresh_name`)."""
    rooms = _scene_rooms(scene)
    prior = _prior(scene) if prior is None else prior
    groups = _groups(scene)
    many = [len({room_level(scene, rid) for rid in group}) >= 2 for group in groups]
    standing, written_on = {}, {}
    reserved = {rec[0] for rec in prior.values()}
    for rid in rooms:
        site = decided_site(scene, rid)
        if site:
            standing.setdefault(site["plan"], {})[str(rid)] = (site["x"], site["y"])
            written_on.setdefault(site["plan"], set()).add(room_level(scene, rid))
            reserved.add(site["plan"])
    for rid, rec in prior.items():
        if rid in rooms and _placeable(scene, rid):
            standing.setdefault(rec[0], {})[rid] = rec[1]
    out = []

    def settle(group, recs, written):
        for held in standing.values():
            for rid in group:
                if rid in prior:
                    held.pop(rid, None)
        for rec in recs:
            rec["written"] = written(rec)
            if rec["written"]:
                if rec["plan"] is None:
                    rec["plan"] = _fresh_name(scene, rec["origin"], reserved)
                    reserved.add(rec["plan"])
                laid = {rid: at for rid, at in rec["placed"].items() if rid not in rec["anchors"]}
                standing.setdefault(rec["plan"], {}).update(laid)
                written_on.setdefault(rec["plan"], set()).update(
                    room_level(scene, rid) for rid in laid)
            out.append(rec)

    def spans(rec):
        placed, anchors = rec["placed"], rec["anchors"]
        return bool(len(placed) >= 2 and set(placed) - set(anchors)
                    and len({room_level(scene, rid) for rid in placed}) >= 2)

    def joins(rec):
        levels = written_on.get(rec["plan"], set()) | {
            room_level(scene, rid) for rid in rec["placed"]}
        return bool(rec["plan"] is not None and set(rec["placed"]) - set(rec["anchors"])
                    and len(levels) >= 2)

    for group, storeys in zip(groups, many):
        if storeys:
            settle(group, _lay_group(scene, group, prior, standing), spans)
    for group, storeys in zip(groups, many):
        if storeys:
            continue
        if any(rid in prior for rid in group):
            settle(group, _lay_group(scene, group, prior, standing), joins)
        elif every:
            start = _fresh_start(scene, group)
            placed, refused = _layout(scene, group, {start: (0, 0)})
            out.append({"rooms": group, "plan": None, "placed": placed, "refused": refused,
                        "anchors": {}, "origin": start, "written": False})
    for rec in out:
        rec["stands"] = bool(rec["plan"] is not None
                             and len(written_on.get(rec["plan"], ())) >= 2)
    return out


def plan_frames(scene) -> list:
    """``[{room: (x, y)}]``: where the derivation lays the scene's rooms out,
    one frame per plan it writes -- every group laid on that plan, in its one
    frame -- and one per group it writes no plan for, one storey or several:
    each room it places where it placed it, and each room it refused where
    its first doorway would have put it (`_layout`'s `refused`), so a reader
    sees what that room lands on; a room reached only through a refused one
    is in no frame, as the layout lint's walk does not lay a room out past a
    collision. A reader that moves a room asks this whether it would make a
    plan clash (`world/frontage.py`), by the same layout `derive_site_plans`
    writes a plan with: grown from the decided sites, else from where the
    derived rooms stood at the last merge, which it recomputes
    (`_lay_group`), else afresh."""
    from world.scene_memo import scene_read_pass
    frames, on_plan = [], {}
    with scene_read_pass(scene):
        for rec in _derive(scene, every=True):
            frame = dict(rec["placed"])
            for rid, refusal in rec["refused"].items():
                frame.setdefault(rid, refusal["at"])
            if rec["written"] and rec["plan"] in on_plan:
                on_plan[rec["plan"]].update(frame)
                continue
            if rec["written"]:
                on_plan[rec["plan"]] = frame
            frames.append(frame)
    return frames


def derive_site_plans(scene) -> list:
    """Lay out every group of two storeys or more on a plan, in place, room
    by room (`_layout`), and return the ids of the rooms whose site this
    wrote, moved or took off. Every derived site is recomputed from the
    rooms as they stand, starting from where they stood (`_lay_group`); a
    decided site is kept. Idempotent: a second call on the same rooms writes
    the same sites and returns []."""
    from world.scene_memo import scene_read_pass
    rooms = _scene_rooms(scene)
    prior = _prior(scene)
    before = {}
    for rid, room in rooms.items():
        if isinstance(room, dict) and site_is_derived(room.get("site")):
            before[str(rid)] = room.pop("site")
    with scene_read_pass(scene):
        records = _derive(scene, prior)
    changed, written = [], set()
    for rec in records:
        if not rec["written"]:
            continue
        for rid in sorted(rec["placed"], key=str):
            if rid in rec["anchors"]:
                continue
            site = {"plan": rec["plan"], "x": int(rec["placed"][rid][0]),
                    "y": int(rec["placed"][rid][1]),
                    "elev_m": room_level(scene, rid) * STOREY_M, DERIVED_KEY: True}
            if rec["origin"] is not None:
                site[ORIGIN_KEY] = rec["origin"]
            rooms[rid]["site"] = site
            written.add(rid)
            if before.get(rid) != site:
                changed.append(rid)
    return changed + sorted((rid for rid in before if rid not in written), key=str)


def plan_refused(scene) -> list:
    """``[{"plan", "stands", "room", "level", "at", "lands_on", "misses",
    "via"}]`` for every room the derivation could not lay out: it would land
    on a room the plan holds, or a doorway of it onto a room on the plan
    would not meet. `stands` is whether the plan it was refused from stands
    -- decided sites or written ones spanning two storeys (`_derive`); where
    what was laid out without it stands on one storey, no plan is written at
    all, and `plan` is then the plan it stood on, or None -- and `at` where
    the room's first doorway would have put it, which the World Browser
    draws. The clashes the derivation could not resolve, said where the
    Room and the host read the world's contradictions (`spatial_lint`'s
    `site_plan_unplaced`, which the designer's own check never reads). A
    room on no plan for want of a bearing is not here: nothing placed it
    anywhere to clash."""
    from world.scene_memo import scene_read_pass
    out = []
    with scene_read_pass(scene):
        for rec in _derive(scene):
            for rid in sorted(rec["refused"], key=str):
                refusal = rec["refused"][rid]
                out.append({"plan": rec["plan"], "stands": rec["stands"], "room": rid,
                            "level": room_level(scene, rid), "at": tuple(refusal["at"]),
                            "lands_on": tuple(refusal["lands_on"]),
                            "misses": tuple(refusal.get("misses") or ()),
                            "via": refusal["via"]})
    return out


def plan_refusals(scene) -> list:
    """``[(plan, room, lands_on, misses, via)]``: `plan_refused`, as a
    reader that needs only who and why reads it."""
    return [(r["plan"], r["room"], r["lands_on"], r["misses"], r["via"])
            for r in plan_refused(scene)]
