"""Landscape: the far places a body sees, at the grain distance leaves them.

THE OWNER'S ASK. "For distant objects we might need something like the text
equivalent of an LOD" (2026-10-04); then, after a build that graded detail by
metres inside ordinary range was reverted (594e4f67), "all I wanted it for
was distant landscapes. like 5 or so rooms of distance or more", and "go
ahead" (2026-10-05) to this, which is UNBUILT_WORLD §2.40's plan:

1. PLACES, NOT PEOPLE. From open air, a window or a height, a far place shows
   as landscape -- open ground or buildings, what is big on it, its lights at
   night. No body, act, crowd or carried lamp is read: people at that range
   bring the causality bubbles, the beat aperture (`rooms_in_view`, which
   decides who is voiced on screen) and the seen ledger with them.
2. FAR STARTS PAST THE NEXT ROOM. The observer's room and every room one edge
   away keep today's sight exactly, and this module answers none of them.
   Detail goes by measured distance where the world measures it, otherwise by
   room count: two to four rooms off, the place and anything big on it; five
   or more, its outline.
3. A FAR PLACE IS NAMED ONLY ONCE THE MIND KNOWS IT; otherwise it is
   described.

GRAPH FIRST. Chosen by all three judges of a three-design panel (2026-10-05),
because the room graph is the one thing every world has: a far place is
reached along open ground -- rooms joined by edges sight crosses
(`sees_across`) -- from the body's outlook (the window cone `vistas.outlooks`
states). A building is the enclosed rooms fronting that ground; it is seen
where it fronts it and it ends the line, unless the eye stands over its roof.
A compass comes from edges that carry one, metres from edges and rooms that
measured them, and a line still reads without either ("past the orchard").

DECLARED, NEVER GUESSED. Ground is a room's DECLARED `exposure`, never
`weather.room_exposure`'s keyword fallback: measured over the owner's corpus,
the fallback read a tavern's staircase landing, a shrine's roost and a deep
shelter's descent as open air, and sight would have run through their walls.
An outlook is a channel, and prose may not open one. The planner declares
exposure on the places it lays out.

THE NEAR FIELD IS NEVER ANSWERED, by construction: every room joined to the
observer's by any edge declared from either side with any barrier
(`neighbor_map`), and every room directly over or under it with no way
between (`floor_edges`). No reader of sight reads this module, and it writes
nothing.
"""

from __future__ import annotations

import heapq
import math
from collections import deque

#: THE NUMBERS, every one named to the owner (ask-before-limiting).
#: The owner's: two to four rooms off is the place and what is big on it,
#: five or more its outline.
MID_HOPS = 4
#: Engine estimates.
OUTLINE_M = 250.0        # a MEASURED path under this is mid grain, at or over it outline
REACH_HOPS = 12          # the walk stops here whatever else allows it
LINES_MAX = 4            # lines in one view
SEGMENTS_PER_LINE = 3    # places one line carries: the nearest two and the farthest
BIG_PER_PLACE = 2        # big things one mid-grain place carries
PLACES_GRADED_MAX = 32   # far places graded per walk, nearest first
ROOF_CLEAR_M = 1.0       # an eye this far over a roof sees past the building
TALL_M = 7.5             # a building taller than this is "tall"
GROUND_TOP_M = 0.3       # what a line aims at on open ground
NOMINAL_SPAN_M = 8.0     # a room with no authored extent, along a line of
                         # sight -- placing what stands between, never said
SLIVER_M = 0.5           # less of a place than this over what is in front of
                         # it is not a view of it

OPEN_GROUND = ("open", "sheltered")
_LOOKS_OUT = ("window", "open", "open_door", "bars", "one_way_window")
_LIGHT_SHOWS = ("lit", "bright")


def _rooms(scene):
    rooms = (scene or {}).get("rooms")
    return rooms if isinstance(rooms, dict) else {}


def declared_ground(scene, rid):
    """"open" | "sheltered" | "building" | None, from the room's DECLARED
    exposure. The inside of a thing (`parent_entity`) is never landscape,
    whatever it declares; an undeclared room is no ground here."""
    room = _rooms(scene).get(rid)
    if not isinstance(room, dict) or str(room.get("parent_entity") or "").strip():
        return None
    from world.weather import EXPOSURES, _pick
    declared = _pick(room.get("exposure"), EXPOSURES, "")
    if not declared:
        return None
    return declared if declared in OPEN_GROUND else "building"


# ---------------------------------------------------------------------------
# The graph, read once per read pass
# ---------------------------------------------------------------------------

def _graph(scene):
    """{room: [edges]} over every declared edge, with `effective_adjacent`'s
    semantics: a room's own declaration wins, the far side's is reversed
    (bearing and vertical), and a far-side wall is never derived. Memoised
    through `scene_memo`, so only inside a read pass and never across an
    edit -- a walk that outlived a door closed in place would see through
    it."""
    from world.scene_memo import scene_memo
    return scene_memo(scene, ("landscape_graph",), lambda: _build_graph(scene))


def _build_graph(scene):
    from world.spatial import (normalize_barrier, normalize_bearing,
                               normalize_vertical, opposite_bearing,
                               opposite_vertical, resolve_edge)
    own = {}
    for rid, room in _rooms(scene).items():
        if isinstance(room, dict):
            own[str(rid)] = [resolve_edge(scene, e) for e in room.get("adjacent") or ()
                             if isinstance(e, dict) and e.get("to")]
    edges = {rid: list(es) for rid, es in own.items()}
    named = {rid: {str(e.get("to")) for e in es} for rid, es in own.items()}
    for rid, es in own.items():
        for e in es:
            to = str(e.get("to"))
            if (to not in edges or rid in named[to]
                    or normalize_barrier(e.get("barrier")) == "wall"):
                continue
            back = {k: v for k, v in e.items() if k not in ("to", "dir", "vertical")}
            back["to"], back["implicit"] = rid, True
            bearing = opposite_bearing(normalize_bearing(e.get("dir")))
            if bearing:
                back["dir"] = bearing
            vertical = opposite_vertical(normalize_vertical(e.get("vertical")))
            if vertical:
                back["vertical"] = vertical
            edges[to].append(back)
            named[to].add(rid)
    return edges


def near_field(scene, rid):
    """The rooms today's sight answers for a body in `rid`: its own, every
    room joined to it by an edge declared from EITHER side with ANY barrier
    -- a wall included, so a field behind a wall declared only from the
    field's side is still near -- and every room straight over or under it
    with no way between."""
    from world.scene_memo import scene_memo
    from world.spatial import floor_edges, neighbor_map
    neighbours = scene_memo(scene, ("landscape_neighbours",),
                            lambda: neighbor_map(scene))
    near = {str(rid)} | {str(r) for r in (neighbours.get(rid) or ())}
    near |= {str(e.get("to")) for e in floor_edges(scene, rid) if e.get("to")}
    return near


def outlook(scene, rid, graph=None):
    """The bearings a body in `rid` looks out along: None for every way
    (it stands on declared open ground); else each window, opening or
    see-through edge onto open ground that sight crosses FROM here, and each
    of the room's own `windows`, with the bearings either side; an empty set
    when it looks out nowhere. `vistas.outlooks`' rule, on declared ground."""
    from world.spatial import normalize_barrier, sees_across
    from world.vistas import BEARINGS, normalize_bearing8
    rooms = _rooms(scene)
    if declared_ground(scene, rid) in OPEN_GROUND:
        return None
    graph = graph if graph is not None else _graph(scene)
    out = set()

    def widen(bearing):
        i = BEARINGS.index(bearing)
        out.update({BEARINGS[(i - 1) % 8], bearing, BEARINGS[(i + 1) % 8]})

    for edge in graph.get(str(rid)) or ():
        to = str(edge.get("to"))
        if (normalize_barrier(edge.get("barrier")) not in _LOOKS_OUT
                or declared_ground(scene, to) not in OPEN_GROUND
                or not sees_across(rooms, rid, to, edge.get("barrier"))):
            continue
        bearing = normalize_bearing8(edge.get("dir"))
        if bearing:
            widen(bearing)
    for raw in (rooms.get(rid) or {}).get("windows") or ():
        bearing = normalize_bearing8(raw)
        if bearing:
            widen(bearing)
    return out


# ---------------------------------------------------------------------------
# Buildings, lights and what is big
# ---------------------------------------------------------------------------

def building_of(scene, front, graph=None):
    """The mass an enclosed room fronting open ground belongs to: every room
    joined to it by doors and stairs (never a wall) at or above its floor,
    and what stands on top by a vertical way (a lantern room, a roof walk).
    Never below its floor: a cellar passage does not make two outbuildings
    one mass. -> (rooms, {room: metres over the front's floor})."""
    from world.site_plan import STOREY_M
    from world.spatial import edge_metres, normalize_barrier, normalize_vertical
    if declared_ground(scene, front) != "building":
        return set(), {}
    graph = graph if graph is not None else _graph(scene)
    height = {front: 0.0}
    queue = deque([front])
    while queue:
        cur = queue.popleft()
        for edge in graph.get(cur) or ():
            other = str(edge.get("to"))
            if other in height or normalize_barrier(edge.get("barrier")) == "wall":
                continue
            vertical = normalize_vertical(edge.get("vertical"))
            ground = declared_ground(scene, other)
            if ground != "building" and not (vertical == "up" and ground is not None):
                continue
            rise = (edge_metres(edge) or STOREY_M) if vertical else 0.0
            h = height[cur] + (rise if vertical == "up" else -rise if vertical == "down" else 0.0)
            if h < 0.0:
                continue
            height[other] = h
            queue.append(other)
    return set(height), height


def _whole_building(scene, room, graph):
    """Every enclosed room joined to `room` by doors and stairs, any floor:
    the body's OWN building, the one it looks out of from a height."""
    from world.spatial import normalize_barrier, normalize_vertical
    seen = {room}
    queue = deque([room])
    while queue:
        cur = queue.popleft()
        for edge in graph.get(cur) or ():
            other = str(edge.get("to"))
            if other in seen or normalize_barrier(edge.get("barrier")) == "wall":
                continue
            if (declared_ground(scene, other) == "building"
                    or normalize_vertical(edge.get("vertical"))):
                seen.add(other)
                queue.append(other)
    return seen


def fixed_lights(scene, rid):
    """How many lights stand in `rid` that a far eye could pick out: an
    entity whose `light_source` is lit or bright, lit now, filling the room
    it is in, and nobody's. A lamp a body carries is that body's, and people
    are not read at this range; a body that gives light is a body; a
    celestial entity is the sky, which the ground's own light already holds
    -- eleven of the owner's scenes stand "The Moon" on a beach."""
    from world.spatial import (_is_body_entity, _light_radius, container_of,
                               normalize_light, room_of_record)
    count = 0
    for eid, entity in ((scene or {}).get("entities") or {}).items():
        if not isinstance(entity, dict) or not entity.get("light_source"):
            continue
        state = entity.get("state") if isinstance(entity.get("state"), dict) else {}
        if state.get("lit", True) in (False, 0, "off", "false", "no", "doused", "out"):
            continue
        if normalize_light(entity.get("light_source")) not in _LIGHT_SHOWS:
            continue
        if str(entity.get("kind") or "").strip().casefold() == "celestial":
            continue
        if _is_body_entity(scene, eid, entity) or _light_radius(entity) != "room":
            continue
        if any(container_of(scene, str(key)) for key in (eid, entity.get("name")) if key):
            continue
        if room_of_record(scene, eid, entity) == rid:
            count += 1
    return count


def _room_lit(scene, rid):
    """A room of a building that shows light: a far light standing in it, or
    -- for a room with walls -- a DECLARED lit or bright light. An undeclared
    room's fail-open `lit` is no claim that anything burns there; and an
    open-sided room's word only darkens the sky it stands under, so what it
    shows is what burns in it (a doused beacon in a lantern room is dark,
    review 2026-10-05)."""
    from world.spatial import normalize_light
    if fixed_lights(scene, rid):
        return True
    if declared_ground(scene, rid) in OPEN_GROUND:
        return False
    raw = str((_rooms(scene).get(rid) or {}).get("light") or "").strip()
    return bool(raw) and normalize_light(raw) in _LIGHT_SHOWS


def _openings_toward(scene, rid, graph, back):
    """Does `rid` open out where a far eye could see its light: open onto
    ground by a window, an opening or its own `windows` -- and, where both
    bearings are known, in a wall the eye is in front of (within a right
    angle of `back`, the bearing from the place to the eye: a lit window is
    seen obliquely from anywhere before its wall, and never through the
    house from behind it)? Unknown bearings do not refuse: nothing says
    which wall the light is behind."""
    from world.spatial import normalize_barrier
    from world.vistas import BEARINGS, bearing_gap, normalize_bearing8
    if declared_ground(scene, rid) in OPEN_GROUND:
        return True                  # open-sided: a lantern room, a loggia
    bearings, any_opening = [], False
    room = _rooms(scene).get(rid) or {}
    for raw in room.get("windows") or ():
        any_opening = True
        bearings.append(normalize_bearing8(raw))
    for edge in graph.get(rid) or ():
        if (normalize_barrier(edge.get("barrier")) in _LOOKS_OUT
                and declared_ground(scene, str(edge.get("to"))) in OPEN_GROUND):
            any_opening = True
            bearings.append(normalize_bearing8(edge.get("dir")))
    if not any_opening:
        return False
    if back not in BEARINGS or any(b is None for b in bearings):
        return True
    return any(bearing_gap(b, back) <= 2 for b in bearings)


def big_things(scene, rid, gate=None):
    """What on far open ground is big enough to be made out, at most
    BIG_PER_PLACE: an anchor the room declares full height, or head height
    over a large or running footprint; and a thing with an inside of its own
    (`interior_rooms`) that is not carried and is not a body. Read off the
    structural fields the engine owns -- never a word in a desc."""
    from world.spatial import (_is_body_entity, normalize_footprint,
                               normalize_height, room_of_record)
    room = _rooms(scene).get(rid) or {}
    out = []
    for _key, anchor in sorted((room.get("anchors") or {}).items()):
        if not isinstance(anchor, dict) or not str(anchor.get("desc") or "").strip():
            continue
        height = normalize_height(anchor.get("height"))
        footprint = normalize_footprint(anchor.get("footprint"))
        if height == "full" or (height == "head" and footprint in ("large", "run")):
            desc = str(anchor["desc"]).strip()
            out.append(gate(desc) if gate else desc)
    for eid, entity in sorted(((scene or {}).get("entities") or {}).items()):
        if (not isinstance(entity, dict) or entity.get("portable")
                or not entity.get("interior_rooms") or _is_body_entity(scene, eid, entity)):
            continue
        if room_of_record(scene, eid, entity) != rid:
            continue
        label = str(entity.get("name") or "").strip()
        if label:
            out.append(gate(label) if gate else label)
    return [t for t in out if t][:BIG_PER_PLACE]


# ---------------------------------------------------------------------------
# Where a far place is
# ---------------------------------------------------------------------------

#: A step that climbs or descends: it covers no ground and turns no compass.
CLIMB = ""


def _compose_bearing(dirs, weights=None):
    """The compass point a path's level steps add up to, or None when any
    level step carries none -- a heading made of guesses is not a heading.
    A climb (`CLIMB`) is skipped: a stair turns nobody."""
    from world.vistas import BEARINGS
    weights = list(weights) if weights else [1.0] * len(dirs or ())
    level = [(d, w) for d, w in zip(dirs or (), weights) if d != CLIMB]
    if not level or any(d is None for d, _w in level):
        return None
    vx = vy = 0.0
    for d, w in level:
        i = BEARINGS.index(d)
        vx += w * math.sin(math.radians(45 * i))
        vy -= w * math.cos(math.radians(45 * i))
    if abs(vx) < 1e-9 and abs(vy) < 1e-9:
        return None
    angle = (math.degrees(math.atan2(vx, -vy)) + 360.0) % 360.0
    return BEARINGS[int((angle + 22.5) // 45) % 8]


def _span_m(scene, rid, bearing):
    """How far a room runs along a bearing, in metres, from its AUTHORED
    extent; None when it has none -- a size word is not a measurement."""
    from world.site_plan import PACE_M
    extent = (_rooms(scene).get(rid) or {}).get("extent")
    if not isinstance(extent, dict):
        return None
    try:
        w, d = float(extent.get("w")), float(extent.get("d"))
    except (TypeError, ValueError):
        return None
    if bearing in ("e", "w"):
        paces = w
    elif bearing in ("n", "s"):
        paces = d
    else:
        paces = math.hypot(w, d) / math.sqrt(2.0)
    return paces * PACE_M


def _path_metres(scene, path, steps, dirs):
    """A path's length when the world MEASURED every part of it: every edge a
    number and every room crossed an authored extent -- half the room the eye
    stands in, the whole of each room between, to the near side of the
    place. (None, False) otherwise; then the room count decides the grain."""
    if not steps or any(m is None for m in steps) or len(dirs) != len(steps):
        return None, False
    total = sum(steps)
    first = _span_m(scene, path[0], dirs[0])
    if first is None:
        return None, False
    total += first / 2.0
    for k, rid in enumerate(path[1:-1], start=1):
        span = _span_m(scene, rid, dirs[k] if k < len(dirs) else dirs[-1])
        if span is None:
            return None, False
        total += span
    return total, True


def _plan_centre(scene, rid):
    from world.site_plan import room_site
    from world.spatial import room_grid
    site = room_site(scene, rid)
    if not site:
        return None
    cx, cy = room_grid(scene, rid).centre()
    return (site["x"] + cx + 0.5, site["y"] + cy + 0.5)


def _plan_aims(scene, rid):
    """The points a line from a far eye is aimed at on a plan: the room's
    centre and its four corner cells."""
    from world.site_plan import site_cells
    cells = site_cells(scene, rid)
    centre = _plan_centre(scene, rid)
    aims = [centre] if centre else []
    if cells:
        xs = [c[0] for c in cells]
        ys = [c[1] for c in cells]
        aims += [(min(xs) + 0.5, min(ys) + 0.5), (max(xs) + 0.5, min(ys) + 0.5),
                 (min(xs) + 0.5, max(ys) + 0.5), (max(xs) + 0.5, max(ys) + 0.5)]
    return aims


def _plan_slabs(scene, plan):
    """{plan cell: [(floor m, ceiling m, room)]} for a plan's buildings,
    built once a read pass (`scene_memo`) -- `site_plan._mass_heights`' rule
    with the room kept, so one map serves every place a walk grades and the
    rooms a line starts and ends in are left out by name (rebuilt per place
    it cost 12-19x the off-plan walk, review 2026-10-05)."""
    from world.scene_memo import scene_memo
    from world.site_plan import (STOREY_M, _open_air, room_elevation_m,
                                 site_cells, site_plans)

    def build():
        slabs = {}
        for levels in site_plans(scene).get(plan, {}).values():
            for rid in levels:
                floor = room_elevation_m(scene, rid)
                # OPEN GROUND IS SOLID BELOW ITS SURFACE: a ridge standing
                # higher than the line hides what lies behind it, as a roof
                # does (owner, 2026-10-07: "occlusion by both landscape and
                # buildings"). Flat ground at the datum hides nothing a line
                # from an eye could pass under.
                if _open_air(scene, rid):
                    for cell in site_cells(scene, rid):
                        slabs.setdefault(cell, []).append((-1.0e9, floor, rid))
                    continue
                for cell in site_cells(scene, rid):
                    slabs.setdefault(cell, []).append((floor, floor + STOREY_M, rid))
        top = max((hi for spans in slabs.values() for _lo, hi, _r in spans), default=0.0)
        return {"cells": slabs, "top": top}
    return scene_memo(scene, ("landscape_slabs", str(plan)), build)


def _line_block(p, q, slabs, exclude):
    """The room whose mass -- a building's storeys, or the ground under an
    open place -- first cuts the line from `p` to `q`, or None when the line
    clears everything: `site_plan._clears_mass` over room-tagged slabs, the
    rooms in `exclude` being the line's own air. A line that stays over
    every roof and every rise on the plan is clear without walking it."""
    if min(p[2], q[2]) > slabs["top"]:
        return None
    slabs = slabs["cells"]
    dx, dy = q[0] - p[0], q[1] - p[1]
    steps = max(1, int(math.ceil(max(abs(dx), abs(dy)) * 4)))
    for i in range(1, steps):
        t = i / steps
        cell = (math.floor(p[0] + t * dx), math.floor(p[1] + t * dy))
        z = p[2] + t * (q[2] - p[2])
        for lo, hi, rid in slabs.get(cell, ()):
            if lo <= z <= hi and rid not in exclude:
                return rid
    return None


def _line_clear(p, q, slabs, exclude):
    return _line_block(p, q, slabs, exclude) is None


def _centres_along(scene, path, dirs, metres):
    """[metres from the eye to the middle of each room on `path`]: every part
    the world measured as measured, and `NOMINAL_SPAN_M` for a room with no
    authored extent -- an estimate for PLACING what stands between the eye
    and a far place, never a distance anyone is told. A climb covers no
    ground."""
    out = [0.0]
    for j in range(len(path) - 1):
        d = dirs[j] if j < len(dirs) else None
        if d == CLIMB:
            out.append(out[-1])
            continue
        spans = [_span_m(scene, path[j], d) if d else None,
                 _span_m(scene, path[j + 1], d) if d else None]
        edge = metres[j] if j < len(metres) and metres[j] is not None else 0.0
        out.append(out[-1] + edge + sum(
            (NOMINAL_SPAN_M if span is None else span) / 2.0 for span in spans))
    return out


def _cover(scene, rid, kind, known_name):
    return {"kind": kind, "room": rid, "name": known_name(rid) if rid else ""}


def _between(scene, graph, path, dirs, centres, skip, known_name):
    """[(top m, metres from the eye, cover)] of what stands between the eye
    and the last room of `path`, off a site plan:

    * GROUND THAT RISES -- every open place the line crosses, at its floor's
      height (`room_elevation_m`: a declared storey, or a site's elevation);
      flat ground hides nothing a line from an eye passes over;
    * THE BUILDINGS ON THE INSIDE OF A CORNER -- where the way turns by an
      eighth or a quarter of a circle, the line from the eye to what lies
      past the turn cuts across the buildings that stand in the angle, and
      it is those the edge's compass places there. A building whose edge
      carries no compass is placed nowhere and hides nothing: what the world
      does not say stands between, does not."""
    from world.site_plan import STOREY_M, room_elevation_m
    from world.vistas import BEARINGS, bearing_gap
    out = []
    for j in range(1, len(path) - 1):
        rid, dist = path[j], centres[j]
        if rid in skip or dist <= 0.0:
            continue
        if declared_ground(scene, rid) in OPEN_GROUND:
            out.append((room_elevation_m(scene, rid), dist,
                        _cover(scene, rid, "ground", known_name)))
        d_in = dirs[j - 1] if j - 1 < len(dirs) else None
        d_out = dirs[j] if j < len(dirs) else None
        if d_in not in BEARINGS or d_out not in BEARINGS:
            continue
        back = BEARINGS.index(BEARINGS[(BEARINGS.index(d_in) + 4) % 8])
        gap = bearing_gap(BEARINGS[back], d_out)
        if gap not in (2, 3):
            continue                       # straight on, or doubled back
        step = 1 if (BEARINGS.index(d_out) - back) % 8 == gap else -1
        inside = {BEARINGS[(back + step * k) % 8] for k in range(1, gap)}
        for edge in graph.get(rid) or ():
            other = str(edge.get("to"))
            if other in skip or other in path or declared_ground(scene, other) != "building":
                continue
            if str(edge.get("dir") or "") not in inside:
                continue
            members, rise = building_of(scene, other, graph)
            if members & skip:
                continue
            top = room_elevation_m(scene, other) + max(rise.values() or [0.0]) + STOREY_M
            out.append((top, dist, _cover(scene, other, "building", known_name)))
    return out


def _seen_part(eye, base, top, dist, between):
    """("whole" | "top" | None, cover): how much of a far place, from its
    `base` to its `top`, shows over what stands `between`, and what stands
    highest in the way. The line from the eye over each thing in the way,
    carried on to the place's distance, is the height below which the place
    is hidden; the place shows whole when every such line passes under its
    foot, its top when some of it still clears the highest, and not at all
    when less than `SLIVER_M` does."""
    worst, cover = None, None
    for c_top, c_dist, what in between or ():
        if c_dist <= 0.0 or c_dist >= dist:
            continue
        h = eye + (c_top - eye) * dist / c_dist
        if worst is None or h > worst:
            worst, cover = h, what
    if worst is None or worst <= base + 0.05:
        return "whole", None
    if top - worst < SLIVER_M:
        return None, cover
    return "top", cover


def _eye_on_plan(scene, observer, here, toward):
    """Where the eye is on the plan: the body's own measured cell, else the
    cell of its room nearest the place it looks at -- a body known only to
    be on a balcony that runs round a tower looks from the side facing the
    view, not out of the tower's middle."""
    from world.site_plan import plan_point, site_cells
    from world.spatial import body_cell
    point = plan_point(scene, observer)
    if not point:
        return None
    if body_cell(scene, observer) is not None or not toward:
        return point[:2]
    cells = site_cells(scene, here)
    if not cells:
        return point[:2]
    best = min(cells, key=lambda c: math.dist((c[0] + 0.5, c[1] + 0.5), toward))
    return (best[0] + 0.5, best[1] + 0.5)


# ---------------------------------------------------------------------------
# The walk
# ---------------------------------------------------------------------------

def far_places(scene, observer, *, known=None, senses=None, via_names=None,
               gate=None, hidden=None):
    """The far places one body sees now, nearest first, each a record the
    composer words (`composer.landscape_percepts`). [] when none qualifies,
    which is every body in a closed room and almost every body in the
    owner's corpus as it stands.

    `known` is {room id: the name this mind knows it by} -- a character's
    place graph, the player's own stamps (ruling 3). `via_names` is {room id:
    name} for the rooms the near field NAMED in this same view (the doorway
    rows `perception._visible_openings` filled): a line leaving through any
    other room leads with its compass or nothing. `gate` is the observer's
    authored-prose gate, applied to every desc this hands on.

    `hidden`, when a list, collects every far place the walk reached and
    sight did not deliver, each with what hid it (`hidden_by`): the window's
    cone, the weather, the dark, or the roofs or the ground standing between
    -- what a LOOK at that place finds instead (`looked_far`).
    """
    from world.day_cycle import SUN_LIGHT
    from world.site_plan import (EYE_M, PACE_M, STOREY_M, body_altitude_m,
                                 room_elevation_m, room_site)
    from world.spatial import (bearing_between, edge_metres, normalize_light,
                               normalize_vertical, posture_class, room_light,
                               room_locale, room_of, sees_across, sense_adjusted)
    from world.vistas import (BEARINGS, air_from_weather, bearing_gap,
                              normalize_bearing8, visibility_km)

    sight = sense_adjusted("full", "sight", senses)
    if sight == "none":
        return []
    rooms = _rooms(scene)
    here = room_of(scene, observer)
    if not here or here not in rooms:
        return []
    here = str(here)
    graph = _graph(scene)
    ways = outlook(scene, here, graph)
    if ways is not None and not ways:
        return []
    known = dict(known or {})

    def known_name(rid):
        """The name this mind knows a place by: the one it learned, else
        the room's own -- "" for a place it does not know."""
        if rid not in known:
            return ""
        return str(known.get(rid) or (rooms.get(rid) or {}).get("name") or "").strip()

    floor = room_elevation_m(scene, here)
    eye = floor + body_altitude_m(scene, observer) + EYE_M.get(
        posture_class(scene, observer), EYE_M["standing"])
    near = near_field(scene, here)
    locale = room_locale(rooms.get(here))

    # ---- seeds: the near open ground the body looks out over, never itself answered
    seeds = []
    for edge in graph.get(here) or ():
        first = str(edge.get("to"))
        if (declared_ground(scene, first) not in OPEN_GROUND
                or not sees_across(rooms, here, first, edge.get("barrier"))):
            continue
        bearing = normalize_bearing8(edge.get("dir"))
        if ways is not None and (bearing is None or bearing not in ways):
            continue
        seeds.append({"room": first, "hops": 1, "path": [here, first],
                      "dirs": [bearing], "metres": [edge_metres(edge)],
                      "via": first, "via_dir": bearing, "front": None,
                      "below": False})
    # A HEIGHT: an eye a storey or more up looks out over the ground its own
    # building fronts, reached through the building.
    own = {here}
    side = None
    if eye >= STOREY_M:
        starts = ([here] if declared_ground(scene, here) == "building" else
                  [str(e.get("to")) for e in graph.get(here) or ()
                   if declared_ground(scene, str(e.get("to"))) == "building"])
        for start in starts:
            own |= _whole_building(scene, start, graph)
        # WHICH SIDE OF ITS BUILDING THE EYE IS ON, for a body on open ground
        # beside it -- a balcony, a roof walk: the bearing from the building
        # to here. Off a plan nothing else says what the building hides, so
        # ground on its far side is seen only by an eye over its roof
        # (review 2026-10-05: a balcony saw the ground behind its tower).
        if ways is None and declared_ground(scene, here) in OPEN_GROUND:
            for edge in graph.get(here) or ():
                if str(edge.get("to")) in own and normalize_bearing8(edge.get("dir")):
                    side = BEARINGS[(BEARINGS.index(normalize_bearing8(edge["dir"])) + 4) % 8]
                    break
        own_top = max((room_elevation_m(scene, r) + STOREY_M for r in own if r != here),
                      default=0.0)
        over_roof = eye >= own_top + ROOF_CLEAR_M
        reached = {here: {"hops": 0, "path": [here], "dirs": [], "metres": []}}
        queue = deque([here])
        while queue:
            cur = queue.popleft()
            rec = reached[cur]
            for edge in graph.get(cur) or ():
                other = str(edge.get("to"))
                if other in reached:
                    continue
                step = {"hops": rec["hops"] + 1, "path": rec["path"] + [other],
                        "dirs": rec["dirs"], "metres": rec["metres"]}
                if not normalize_vertical(edge.get("vertical")):
                    step["dirs"] = rec["dirs"] + [normalize_bearing8(edge.get("dir"))]
                    step["metres"] = rec["metres"] + [edge_metres(edge)]
                else:
                    step["metres"] = rec["metres"] + [None]   # a climb is no ground covered
                    step["dirs"] = rec["dirs"] + [CLIMB]
                if other in own:
                    reached[other] = step
                    queue.append(other)
                elif (declared_ground(scene, other) in OPEN_GROUND and other not in near
                      and room_locale(rooms.get(other)) == locale):
                    if ways is None and not over_roof and declared_ground(scene, here) in OPEN_GROUND:
                        exit_dir = normalize_bearing8(edge.get("dir"))
                        if side is None or exit_dir is None or bearing_gap(exit_dir, side) > 2:
                            continue
                    reached[other] = step
                    seeds.append({"room": other, **step, "via": "@" + other,
                                  "via_dir": None, "front": cur, "below": True})

    # ---- the walk, nearest first
    best, order = {}, 0
    queue = []
    for seed in seeds:
        heapq.heappush(queue, (seed["hops"], order, seed))
        order += 1
    while queue:
        hops, _n, rec = heapq.heappop(queue)
        rid = rec["room"]
        if hops > REACH_HOPS or rid in best:
            continue
        best[rid] = rec
        ground = declared_ground(scene, rid)
        if ground == "building":
            members, rise = building_of(scene, rid, graph)
            top = room_elevation_m(scene, rid) + max(rise.values() or [0.0]) + STOREY_M
            if eye < top + ROOF_CLEAR_M:
                continue                     # the mass ends the line
            sources = sorted(members)
        elif ground in OPEN_GROUND:
            sources = [rid]
        else:
            continue
        for src in sources:
            for edge in graph.get(src) or ():
                other = str(edge.get("to"))
                if other in near or other in own or other in best or other == rid:
                    continue
                if room_locale(rooms.get(other)) != locale:
                    continue
                other_ground = declared_ground(scene, other)
                if other_ground is None:
                    continue
                if (ground in OPEN_GROUND and other_ground in OPEN_GROUND
                        and not sees_across(rooms, src, other, edge.get("barrier"))):
                    continue                 # open ground behind a wall or a shut gate
                if ground == "building" and other_ground == "building":
                    continue
                vertical = normalize_vertical(edge.get("vertical"))
                if (ground in OPEN_GROUND and other_ground == "building"
                        and (vertical == "down" or room_elevation_m(scene, other)
                             < room_elevation_m(scene, src) - 0.5)):
                    continue                 # a cellar under the ground is no building on it
                nxt = {"room": other, "hops": hops + 1, "path": rec["path"] + [other],
                       "dirs": rec["dirs"] + [CLIMB if vertical else
                                              normalize_bearing8(edge.get("dir"))],
                       "metres": rec["metres"] + [None if vertical else edge_metres(edge)],
                       "via": rec["via"], "via_dir": rec["via_dir"], "front": rid,
                       "below": rec["below"]}
                heapq.heappush(queue, (hops + 1, order, nxt))
                order += 1

    # ---- grade
    weather = (scene or {}).get("weather") or {}
    air_word = air_from_weather(weather)
    air_m = visibility_km(air_word) * 1000.0
    phase = str((scene or {}).get("day_phase") or "").strip().casefold()
    night = SUN_LIGHT.get(phase) == "dark"
    twilight = SUN_LIGHT.get(phase) == "dim"
    obs_site = room_site(scene, here)
    places, claimed, graded = [], set(), 0
    for rid, rec in sorted(best.items(), key=lambda kv: (kv[1]["hops"], kv[0])):
        if rid in near or rid in own:
            continue
        graded += 1
        if graded > PLACES_GRADED_MAX:
            break
        ground = declared_ground(scene, rid)
        if ground == "building":
            members, rise = building_of(scene, rid, graph)
        else:
            members, rise = {rid}, {rid: 0.0}
        if members & claimed:
            continue                         # one mass, seen once, from its nearest front
        base = min(room_elevation_m(scene, m) for m in members)
        top = base + (max(rise.values() or [0.0]) + STOREY_M
                      if ground == "building" else GROUND_TOP_M)
        rise_word = "below" if rec["below"] else ""
        label = (next((known_name(m) for m in [rid, *rise] if known_name(m)), "")
                 if ground == "building" else known_name(rid))

        def hide(cover, bearing=None):
            """A place the walk reached and sight did not deliver, kept for
            a look aimed at it, with what stands in the way."""
            if isinstance(hidden, list):
                hidden.append({"room": rid, "members": sorted(members),
                               "ground": ground, "hidden_by": cover,
                               "bearing": bearing, "via": rec["via"],
                               "via_dir": rec["via_dir"], "hops": rec["hops"],
                               "name": str(label or "")})

        shows, cover = "whole", None
        site = room_site(scene, rid)
        if obs_site and site and site["plan"] == obs_site["plan"]:
            aims = _plan_aims(scene, rid)
            centre = aims[0] if aims else None
            eye_xy = _eye_on_plan(scene, observer, here, centre)
            if not eye_xy or not centre:
                continue
            metres = math.hypot(math.dist(eye_xy, centre) * PACE_M, eye - base)
            measured = True
            bearing = bearing_between(eye_xy, centre)
            rise_word = ("below" if base < eye - EYE_M["standing"] - 1.0 else
                         "above" if base > eye + 1.0 else "")
            # THE LINE OVER EVERYTHING BETWEEN: a subtraction where the plan
            # places what stands between -- roofs, and since 2026-10-07 the
            # ground of an open place standing higher -- never a grant of
            # what the walk did not reach. A line to the place's FOOT says
            # whether it shows whole; one to its TOP whether any of it does.
            slabs = _plan_slabs(scene, site["plan"])
            eye_at = (eye_xy[0], eye_xy[1], eye)
            to_top = [_line_block(eye_at, (a[0], a[1], top), slabs, {here} | members)
                      for a in aims]
            if all(b is not None for b in to_top):
                blocker = next(b for b in to_top if b is not None)
                hide(_cover(scene, blocker, "ground" if declared_ground(
                    scene, blocker) in OPEN_GROUND else "building", known_name),
                    bearing)
                continue
            foot = min(top, base + GROUND_TOP_M)
            to_foot = [_line_block(eye_at, (a[0], a[1], foot), slabs, {here} | members)
                       for a in aims]
            if all(b is not None for b in to_foot) and top - base >= SLIVER_M:
                blocker = next(b for b in to_foot if b is not None)
                shows, cover = "top", _cover(scene, blocker, "ground" if declared_ground(
                    scene, blocker) in OPEN_GROUND else "building", known_name)
        else:
            metres, measured = _path_metres(scene, rec["path"], rec["metres"], rec["dirs"])
            bearing = _compose_bearing(rec["dirs"], rec["metres"] if measured else None)
            # OFF A PLAN, WHAT STANDS BETWEEN IS PLACED ALONG THE WAY ITSELF
            # (`_between`): ground that rises, and the buildings in the angle
            # of a corner the way turns -- by height, so a tower behind low
            # roofs shows its top over them (owner, 2026-10-07: "we need to
            # handle occlusion by both landscape and buildings").
            centres = _centres_along(scene, rec["path"], rec["dirs"], rec["metres"])
            reach_m = metres if measured else centres[-1]
            shows, cover = _seen_part(
                eye, base, top, reach_m,
                _between(scene, graph, rec["path"], rec["dirs"], centres,
                         members | own, known_name))
            if shows is None:
                hide(cover, bearing)
                continue
            if not measured and reach_m > air_m:
                hide({"kind": "air", "air": air_word, "room": "", "name": ""}, bearing)
                continue
        if ways is not None and (bearing is None or bearing not in ways):
            hide({"kind": "walls", "room": "", "name": ""}, bearing)
            continue                         # the window's cone: unknown is refused
        if measured and metres > air_m:
            hide({"kind": "air", "air": air_word, "room": "", "name": ""}, bearing)
            continue
        if measured:
            tier = "mid" if metres < OUTLINE_M else "outline"
        else:
            tier = "mid" if rec["hops"] <= MID_HOPS else "outline"
        dusk = night or twilight
        if ground == "building":
            front_light = (normalize_light(room_light(scene, rec["front"]))
                           if rec["front"] else "lit")
            seen_mass = not (night and front_light == "dark")
            back = None
            if bearing in BEARINGS:
                back = BEARINGS[(BEARINGS.index(bearing) + 4) % 8]
            lit_rooms = ([m for m in sorted(members) if _room_lit(scene, m)
                          and _openings_toward(scene, m, graph, back)]
                         if dusk else [])
            if not seen_mass and not lit_rooms:
                hide({"kind": "dark", "room": "", "name": ""}, bearing)
                continue
            height_m = max(rise.values() or [0.0]) + STOREY_M
            place = {"ground": "building", "lights": len(lit_rooms),
                     "high": any(rise.get(m, 0.0) > 0.0 for m in lit_rooms),
                     "height": ("tall" if height_m > TALL_M else
                                "two" if height_m > STOREY_M + 0.1 else "one"),
                     "dark": not seen_mass}
            # Named from the front the eye sees first, then the nearest room
            # in from it (`building_of` keeps that order) -- never the first
            # in the alphabet.
            named = next((known_name(m) for m in [rid, *rise] if known_name(m)), "")
        else:
            light = normalize_light(room_light(scene, rid))
            seen_mass = not (night and light == "dark")
            lights = fixed_lights(scene, rid) if dusk else 0
            if not seen_mass and not lights:
                hide({"kind": "dark", "room": "", "name": ""}, bearing)
                continue
            place = {"ground": ground, "lights": lights, "high": False,
                     "breadth": _breadth(scene, rid), "dark": not seen_mass}
            named = known_name(rid)
        grain = ("outline" if (tier == "outline" or dusk or not seen_mass
                               or sight != "full") else "mid")
        claimed |= members
        place.update({
            "room": rid, "line": rec["via"], "hops": rec["hops"],
            # ONE KEY PER MASS, whichever front the walk reached first: a step
            # that reaches a building by its other door is not a new building.
            "key_room": min(members) if ground == "building" else rid,
            "front": rec["front"] if ground == "building" else None,
            "tier": tier, "grain": grain, "name": str(named or ""),
            "big": (big_things(scene, rid, gate)
                    if grain == "mid" and ground != "building" else []),
            "bearing": bearing, "rise": rise_word, "via_dir": rec["via_dir"],
            # HOW MUCH OF IT, and over what: its top over the roofs or the
            # rise in front of it, or the whole of it.
            "shows": shows, "over": (cover or {}).get("kind") if shows == "top" else "",
            "members": sorted(members),
        })
        places.append(place)

    # ---- lines: one per way out, nearest first
    by_line = {}
    for place in places:
        by_line.setdefault(place["line"], []).append(place)
    lines = sorted(by_line.items(), key=lambda kv: (kv[1][0]["hops"], kv[0]))
    out = []
    for key, members in lines[:LINES_MAX]:
        members.sort(key=lambda p: (p["hops"], p["room"]))
        head = members[0]
        via = "" if key.startswith("@") else key
        lead = {"compass": head["via_dir"] if via else head["bearing"],
                "via": (via_names or {}).get(via, "") if via else "",
                "rise": "below" if key.startswith("@") else head["rise"],
                "via_room": via}
        for n, place in enumerate(members):
            place["lead"] = lead
            place["order"] = n
            out.append(place)
    return out


def looked_far(scene, observer, looks, *, known=None, senses=None, via_names=None,
               gate=None):
    """What each far place this body's own act LOOKED AT this beat shows it:
    `[{"room", "label", "place": <far_places record> | None,
       "hidden_by": <cover> | None}]`.

    ONE MATCHER FOR THE FAR LAYER AS FOR THE HORIZON (`vistas.looked_vistas`,
    UNBUILT_WORLD 2.40: "one matcher would serve both"): a look names a place
    by the id of ANY room of its mass -- a look at a bell loft is a look at
    the building it tops -- or by the name this mind knows it by, or by its
    own name, which the actor used and so may hear back; a compass word
    finds only what is in view that way. A place named that the walk never
    reached stands behind what surrounds the looker: the walls of a closed
    room, the buildings round open ground. What a look finds is ALWAYS
    something -- the place, its top over what is nearer, or what stands in
    the way (owner, 2026-10-07: "nothing can be made out and similar place
    holders are quite frustrating")."""
    from world.spatial import room_of
    from world.vistas import normalize_bearing8
    rooms = _rooms(scene)
    words = [str(v or "").strip() for v in looks or () if str(v or "").strip()]
    if not words:
        return []

    def fold(value):
        return " ".join(str(value or "").replace("_", " ").casefold().split())

    wanted = {fold(w) for w in words}
    bearings = {b for b in (normalize_bearing8(w) for w in words) if b}
    hidden = []
    places = far_places(scene, observer, known=known, senses=senses,
                        via_names=via_names, gate=gate, hidden=hidden)

    def named_in(members):
        """The member a look named, by id or by its own name, or None."""
        for m in members:
            if fold(m) in wanted or fold((rooms.get(m) or {}).get("name")) in wanted:
                return m
        return None

    out, answered = [], set()
    for place in places:
        members = place.get("members") or [place["room"]]
        hit = named_in(members)
        by_name = bool(place.get("name")) and fold(place["name"]) in wanted
        by_compass = place.get("bearing") in bearings
        if hit is None and not by_name and not by_compass:
            continue
        key = place.get("key_room") or place["room"]
        if key in answered:
            continue
        answered.add(key)
        label = place.get("name") or (
            str((rooms.get(hit) or {}).get("name") or "") if hit else "")
        out.append({"room": key, "label": str(label or ""), "place": place, "hidden_by": None})
    for rec in hidden:
        members = rec.get("members") or [rec["room"]]
        hit = named_in(members)
        if hit is None and not (rec.get("name") and fold(rec["name"]) in wanted):
            continue
        key = min(members)
        if key in answered:
            continue
        answered.add(key)
        label = rec.get("name") or str((rooms.get(hit) or {}).get("name") or "")
        out.append({"room": key, "label": str(label or ""), "place": None,
                    "hidden_by": rec.get("hidden_by") or {}})
    # NAMED, AND NEVER REACHED. A room that declares no ground is part of
    # what it opens onto: a loft up a ladder from a chapel is seen where the
    # chapel is (scratch story 166: the bell loft, planned without an
    # exposure, sat off every walk) -- so a look at it is answered by the
    # far place a neighbour of it belongs to. Only past that is what
    # surrounds the looker what stands in the way: a room's own walls, or
    # the buildings round open ground.
    here = room_of(scene, observer)
    near = near_field(scene, here) if here else set()
    graph = _graph(scene)
    for word in words:
        target = next((rid for rid, room in rooms.items()
                       if fold(rid) == fold(word)
                       or fold((room or {}).get("name")) == fold(word)), None)
        if (not target or target == here or target in near
                or any(target in ((f["place"] or {}).get("members") or ()) or target == f["room"]
                       for f in out)):
            continue
        if any(target in (r.get("members") or ()) for r in hidden):
            continue
        label = str((rooms.get(target) or {}).get("name") or target)
        neighbours = {str(e.get("to")) for e in graph.get(target) or ()}
        place = next((p for p in places
                      if neighbours & set(p.get("members") or [p["room"]])), None)
        if place is not None:
            key = place.get("key_room") or place["room"]
            if key not in answered:
                answered.add(key)
                out.append({"room": key, "label": place.get("name") or label,
                            "place": place, "hidden_by": None})
            continue
        cover = next((r for r in hidden
                      if neighbours & set(r.get("members") or [r["room"]])), None)
        if cover is not None:
            out.append({"room": min(cover.get("members") or [cover["room"]]),
                        "label": cover.get("name") or label, "place": None,
                        "hidden_by": cover.get("hidden_by") or {}})
            continue
        out.append({"room": target, "label": label, "place": None,
                    "hidden_by": {"kind": ("around" if declared_ground(scene, here)
                                           in OPEN_GROUND else "walls"),
                                  "room": "", "name": ""}})
    return out


def _breadth(scene, rid):
    """"wide" for open ground whose AUTHORED extent or size is large or
    more -- never the size the engine guesses from a room's name."""
    from world.spatial import size_from_extent
    room = _rooms(scene).get(rid) or {}
    tier = size_from_extent(room.get("extent")) or str(room.get("size") or "").strip().casefold()
    return "wide" if tier in ("large", "huge", "vast") else ""
