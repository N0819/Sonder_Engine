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

A FAR LOOK, where the world declares one (the owner's option of
UNBUILT_WORLD §2.40, chosen 2026-10-08): how a place reads from a distance,
written by the planner as a field of its own -- `far_look` on a room, and on
a region in its registry (`world.regions`) -- never a `desc`. A place said
by its ground alone ("open ground", "a sheltered place", "a building") is
said by its look instead; a known place is still said by its name. A
region's look stands for a ground place with none of its own only at the
outline, five or more rooms off, where a place reads as the part of the map
it is in. A look is admitted to a mind only when it carries no place's
name that mind has not learned and no part of the map's name
(`_admit_look`), and a person it has not met is said as its own gate says
them. One name passes: a place's own, in its own look, where the look
writes it as the word for what the place is (`SIGHT_NAMES`), which in a
script without capitals nothing tells from a coined name; and a part of
the map's name reaches a mind that knows a place of it only where the
owner's switch says so (`REGION_NAMES_TO_LOCALS`, off).
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
CELLAR_BELOW_M = 0.5     # an enclosed room whose floor is more than this below
                         # the open ground it adjoins is a cellar under that
                         # ground, no building standing on it (`far_places`,
                         # `_building_fronts`)

#: THE LONGEST FAR LOOK KEPT, in characters (named to the owner,
#: ask-before-limiting). A look is ONE phrase spliced into a line that
#: carries up to three places (`SEGMENTS_PER_LINE`); 160 characters is about
#: twenty-five English words -- room for a phrase, not a paragraph. A longer
#: one is cut at its last comma, else its last space, before the limit
#: (`normalize_far_look`), never refused: a look kept short is still a look.
FAR_LOOK_CHARS = 160

#: A RUN OF GROUND IS SAID TOGETHER WHETHER OR NOT ITS PLACES READ ALIKE --
#: the owner's switch, OFF (review 2026-10-08, F10). Off, a run of plain,
#: unnamed ground of one kind folds as it always did, so the three-row trim
#: (`SEGMENTS_PER_LINE`) reaches no place the run covered, and the run is
#: said by its nearest place's look and its farthest's ("a reedy bank,
#: stretching on to a bare green hill"). On, every place whose look differs
#: from its neighbour's is a row of its own -- each said by its own look --
#: and the trim drops the middle rows a run used to carry: replayed on chat
#: 166 with a look on every declared place, places told fell 414 -> 347.
#: Trading places for detail is the owner's call.
LOOKS_SPLIT_RUNS = False

#: WHERE A ROOM'S NAME IS SAID AS THE WORD FOR WHAT THE PLACE IS, to a mind
#: that has not learned the place -- the owner's switch (review 2026-10-08,
#: F3 and R2-2; `_said_as_a_word`). A name is that word only where the
#: place's OWN far look uses it, written all in lower case in a script with
#: case, and with nobody inside it the observer has not met. Measured on
#: Kirinoura and Brackwater with their rooms named in Japanese, and twelve
#: looks that do carry a name a stranger lacks, plus two one-word coined
#: English names, each in its own look and another's:
#:
#: * "own" (the default): the name is said in that place's own look and
#:   nowhere else. Valid looks refused to a stranger: Kirinoura 1 of 7 (a
#:   hall "above the stone stair", 石段 being the stair's name), Brackwater
#:   0 of 20, English 0. Leaks admitted: 1 of 16 -- a Japanese inn's own
#:   coined name in its own look, which nothing in a script without capitals
#:   marks -- and it never reaches another look, alone or with the rest.
#: * "every": the name is said in every look that carries it. Valid looks
#:   refused: 0 of 7 and 0 of 20. Leaks admitted: 1 of 16 alone, 2 of 16
#:   together -- once the inn's own look names the inn, a neighbour's look
#:   naming the inn is said to every stranger as well.
#: * None: never; every room name a mind lacks refuses the look, the floor
#:   as first built. Valid looks refused: Kirinoura 6 of 7 and Brackwater 1
#:   of 20, read as their ground; leaks admitted 0 of 16.
#:
#: "own" is the default because it is the narrowest that keeps the measured
#: worlds' looks: a model's mistake costs one look, never every look that
#: names the place.
SIGHT_NAMES = "own"

#: A REGION'S NAME IS SAID TO A MIND THAT KNOWS A PLACE OF IT -- the owner's
#: switch, OFF (review 2026-10-08, R2-9). No engine channel carries a
#: region's name to a mind, so a look that carries one -- a region's own, or
#: a room's naming its town -- is withheld from every mind by default, and
#: the place reads by its ground as it did before far looks. On, a mind
#: that knows some room of the region is taken to know what that part of the
#: map is called, and is told it. Measured: no valid look in either replay
#: names a region (the card asks for none), so off withholds nothing a plan
#: wrote by the card.
REGION_NAMES_TO_LOCALS = False

#: HOW MANY BUILDINGS OF ONE ROW ARE DESCRIBED BY THEIR LOOKS -- the owner's
#: cap, NONE until they set one (review 2026-10-08, F6).
#: Buildings that share a look are said once with their count whatever this
#: is ("a few buildings alike, each a narrow house of tarred board"); with
#: a number, the nearest that many looks of a row are said and the rest of
#: its buildings are said as if they had no look -- counted where they are
#: plain ("and two buildings"), by their height, their lights and their top
#: where they are not (review R2-8: counted as plain, a lit one lost its
#: light) -- which bounds a row's looks by `FAR_LOOK_CHARS` times this.
#: None describes every one.
DESCRIBED_BUILDINGS_PER_ROW = None


class _UnreadRegions(dict):
    """A region registry a stage could not read: it vouches for no region,
    so no far look is said at all (`REGIONS_UNREAD`)."""


#: What a stage hands the far layer when the frame's region registry could
#: not be read (`perception._far_regions`): every far look is withheld for
#: that view and its places read by their ground, because the floor cannot
#: tell which names are regions' (review 2026-10-08, R2-3: read as "no
#: regions", a look naming the town was said to a stranger).
REGIONS_UNREAD = _UnreadRegions()

OPEN_GROUND = ("open", "sheltered")
_LOOKS_OUT = ("window", "open", "open_door", "bars", "one_way_window")
_LIGHT_SHOWS = ("lit", "bright")
#: Where a too-long look is cut first: a clause break, in either script.
_LOOK_BREAKS = (", ", "、", "，", "; ")


def normalize_far_look(value):
    """A far look as stored and read: whitespace collapsed, at most
    `FAR_LOOK_CHARS` characters -- cut at the last clause break, else the
    last space, before the limit -- and "" for anything that is not text.
    The one spelling every writer and the reader share (the plan, the
    sketch, a beat's room write, the World Browser, the region registry)."""
    if not isinstance(value, str):
        return ""
    text = " ".join(value.split())
    if len(text) <= FAR_LOOK_CHARS:
        return text
    head = text[:FAR_LOOK_CHARS]
    cut = max(head.rfind(b) for b in _LOOK_BREAKS)
    if cut <= 0:
        cut = head.rfind(" ")
    head = head[:cut] if cut > 0 else head
    return head.rstrip(" ,;:、，-–—")


def far_look_of(scene, rid):
    """The far look a room declares, normalized; "" when it declares none."""
    return normalize_far_look((_rooms(scene).get(rid) or {}).get("far_look"))


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


def building_height(rise):
    """How high a mass stands to a far eye -- "one", "two" or "tall" -- from
    `building_of`'s ``{room: metres over the front's floor}``: its highest
    room's floor plus a storey, over `TALL_M` tall, over a storey two. What
    the far layer says a building by when it has no look of its own
    (`landscape_building_<height>`), and what the planting sketch is shown
    of a standing building, whose look is said in its place."""
    from world.site_plan import STOREY_M
    height_m = max((rise or {}).values() or [0.0]) + STOREY_M
    return "tall" if height_m > TALL_M else "two" if height_m > STOREY_M + 0.1 else "one"


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
               gate=None, hidden=None, regions=None):
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

    `regions` is the frame's region registry, {region id: {name, far_look,
    ...}} (`world.regions.region_registry`, planted structures included): a
    ground place with no look of its own reads by its region's `far_look`
    at the outline, and a region's `name` is one a look may not carry
    (`_place_forms`; `REGION_NAMES_TO_LOCALS`). `REGIONS_UNREAD`, a registry
    the stage could not read, withholds every look. Each record's `look` is
    the far look this mind may receive (`_admit_look`), "" where there is
    none.

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
                             < room_elevation_m(scene, src) - CELLAR_BELOW_M)):
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
    place_forms = None

    def look_for(look, own_rooms=()):
        """`look` as this mind may receive it, the place names read once a
        walk and only when some place declares a look; `own_rooms` the rooms
        whose own look it is. A registry the stage could not read vouches
        for no name, so nothing is said (`REGIONS_UNREAD`)."""
        nonlocal place_forms
        if not look or isinstance(regions, _UnreadRegions):
            return ""
        if place_forms is None:
            place_forms = _place_forms(scene, known, regions=regions) or False
        return _admit_look(look, place_forms or None, gate, own=own_rooms, scene=scene)
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
            place = {"ground": "building", "lights": len(lit_rooms),
                     "high": any(rise.get(m, 0.0) > 0.0 for m in lit_rooms),
                     "height": building_height(rise),
                     "dark": not seen_mass}
            # Named from the front the eye sees first, then the nearest room
            # in from it (`building_of` keeps that order) -- never the first
            # in the alphabet.
            named = next((known_name(m) for m in [rid, *rise] if known_name(m)), "")
            # ITS LOOK, by the same order: the planner writes a far look on
            # the room it plans, and any room of the mass may carry it -- the
            # mass's own look, whichever of its rooms carries it.
            place["look"] = look_for(next(
                (far_look_of(scene, m) for m in [rid, *rise] if far_look_of(scene, m)), ""),
                own_rooms=tuple(sorted(members)))
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
            # ITS LOOK: its own, else -- at the outline only, where a place
            # reads as the part of the map it is in -- its region's.
            look, looks_own = far_look_of(scene, rid), (rid,)
            if not look and tier == "outline":
                region = str((rooms.get(rid) or {}).get("region") or "")
                look = normalize_far_look(
                    ((regions or {}).get(region) or {}).get("far_look")) if region else ""
                looks_own = ()                # the region's, no room's own
            place["look"] = look_for(look, own_rooms=looks_own)
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
               gate=None, regions=None):
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
                        via_names=via_names, gate=gate, hidden=hidden,
                        regions=regions)

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


class _Floor:
    """One mind's place-name floor for one walk (`_place_forms`): the
    alternation over every name a place of this world goes by, the folded
    names this mind lacks, and what it needs to ask whether a room's name is
    said as the word for what the place is (`_said_as_a_word`)."""
    __slots__ = ("pattern", "unknown", "rooms_named", "scene", "memo")

    def __init__(self, pattern, unknown, rooms_named, scene):
        self.pattern = pattern
        self.unknown = unknown
        self.rooms_named = rooms_named      # folded room name -> its room ids
        self.scene = scene
        self.memo = {}


def _place_forms(scene, known, *, regions=None):
    """The floor (`_Floor`) a far look must pass for this mind: one
    alternation over every name a place of this world goes by -- each
    room's, and each region's (`regions`, the frame's registry, planted
    structures included) -- longest first, and the folded names among them a
    look may not carry to this mind: the closed sets of place names the
    world holds, never a list of words. None when this mind lacks none. ONE
    alternation so the longest name wins at every position, as
    `common._scrub_unknown_identities` does for people: a known "The Mill
    Field" is matched whole and shields the unknown "The Mill" inside it.

    WHAT A MIND LACKS. A room's name, unless it knows the room; where the
    room's own look uses its name as the word for what the place is, the
    look may still say it (`_said_as_a_word`). A region's name, always,
    unless the owner's switch takes a mind that knows a room of that region
    to know what that part of the map is called (`REGION_NAMES_TO_LOCALS`,
    off): no engine channel carries a region's name to a mind (review
    2026-10-08, F4: "the tarred roofs of Saltmarsh" was said to a mind that
    knew no place there). A region's name is never a sight word: of the 39
    region and structure names the two scratch dbs hold, 26 are engine ids
    and 12 proper names ("Brackwater", "Minase", "Site-17"); the one common
    word, chat 94's structure "apartment", is a word a look in that story
    then may not carry at all."""
    import re
    from story.character_schema import name_boundary_pattern
    known = known or {}
    rooms = _rooms(scene)
    names, unknown, rooms_named = {}, set(), {}
    for rid, room in rooms.items():
        if not isinstance(room, dict):
            continue
        name = " ".join(str(room.get("name") or "").split())
        if not name:
            continue
        folded = name.casefold()
        names.setdefault(folded, name)
        rooms_named.setdefault(folded, []).append(str(rid))
        if str(rid) not in known:
            unknown.add(folded)
    known_regions = ({str((rooms.get(rid) or {}).get("region") or "") for rid in known}
                     if REGION_NAMES_TO_LOCALS else set())
    for region_id, entry in (regions or {}).items():
        name = " ".join(str((entry or {}).get("name") or "").split()) \
            if isinstance(entry, dict) else ""
        if not name:
            continue
        names.setdefault(name.casefold(), name)
        if str(region_id) not in known_regions:
            unknown.add(name.casefold())
    for rid in known:
        own = " ".join(str((rooms.get(rid) or {}).get("name") or "").split())
        unknown.discard(own.casefold())
        learned = " ".join(str(known.get(rid) or "").split())
        if learned:
            names.setdefault(learned.casefold(), learned)
    if not unknown:
        return None
    forms = sorted(names.values(), key=lambda f: (-len(f), f))
    pattern = re.compile("|".join(name_boundary_pattern(f) for f in forms), re.IGNORECASE)
    return _Floor(pattern, frozenset(unknown), rooms_named, scene)


def _said_as_a_word(floor, written, own, gated):
    """Is a room's name, matched in a look as `written`, said there as the
    word for what the place IS -- never a spelling of its identity?
    `gated()` is the look through the observer's people gate.

    THE CLASS, MEASURED (review 2026-10-08, F3). A story names a place by
    what it is as readily as by whose it is, and in a script with no spaces
    nothing tells the name from the word: Kirinoura named in Japanese (広場
    the square, 石段 the stone stair, 船着き場 the landing) refused six of
    the seven looks written for it to a stranger -- five for carrying the
    place's own name ("...丘のふもとの小さな広場") and one for carrying the
    stair's ("石段の上に建つ...堂") -- so the far layer said "open ground"
    where the plan had said what stood there. The name of a place nobody
    has learned is withheld because it is learned by a channel; the word for
    what a thing is, is what an eye meets.

    A name is that word only where the place's OWN far look uses it -- the
    plan, saying how the place reads from far off, said it with that word --
    and only as far as the owner's switch reaches (`SIGHT_NAMES`): "own", in
    that look alone; "every", in every look that carries it. Two things keep
    a name a name all the same:

    * A CAPITAL WHERE THE LOOK WRITES IT. Running text is how a script with
      case marks a proper name ("the Turned Tide", "the mill of Thornby"),
      so a look that writes the name with a capital anywhere -- the place's
      own look or this one -- uses it as a name. A script without case has
      no such mark, and there the card alone keeps a place's own coined name
      out of its look: the one leak measured, kept to that one look by
      "own" (review R2-2: under "every" it was said in a neighbour's look
      too, and a one-word English name with only its initial capital passed
      the old mark, which read the room's name and not the look).
    * A STRANGER INSIDE IT: the observer's people gate changes it, so it is
      no longer in the look the gate hands back ("the Gale house" is a
      family's, whatever its look says). That is the gate call the look
      pays to be said at all, so asking costs nothing more (review R2-4:
      asked of every self-naming room on every walk, the gate cost 80-335 ms
      a walk in a world named in Japanese)."""
    folded = written.casefold()
    if not SIGHT_NAMES or folded not in floor.rooms_named:
        return False                   # a region's name is never a word
    if any(ch.isupper() for ch in written):
        return False
    carriers = floor.rooms_named[folded]
    if not any(str(r) in carriers for r in own):
        if SIGHT_NAMES != "every" or not any(
                _writes_as_a_word(floor, rid, folded) for rid in carriers):
            return False
    return written in gated()


def _writes_as_a_word(floor, rid, folded):
    """Does room `rid`'s own far look write its name `folded`, and only in
    lower case?"""
    key = ("own-look", rid, folded)
    if key not in floor.memo:
        look = far_look_of(floor.scene, rid)
        written = [m.group(0) for m in floor.pattern.finditer(look)
                   if m.group(0).casefold() == folded] if look else []
        floor.memo[key] = bool(written) and not any(
            ch.isupper() for w in written for ch in w)
    return floor.memo[key]


def _through_gate(scene, gate, look):
    """`look` through the observer's people gate, as written (not yet cut to
    length): once per look per read pass, so a stage's two walks over the
    same view -- the standing one and a look's own (`looked_far`) -- pay one
    gate call between them. `gate` is the observer's own, built once per
    observer per stage, and is held by the pass's key, so no other mind's
    gate can answer for it."""
    if not gate:
        return look
    from world.scene_memo import scene_memo
    try:
        hash(gate)
    except TypeError:                 # a gate that cannot key a memo is asked
        return str(gate(look) or "")
    return scene_memo(scene, ("landscape-look-gate", gate, look),
                      lambda: str(gate(look) or ""))


def _admit_look(look, forms, gate, own=(), scene=None):
    """A far look as THIS mind may receive it, or "" when it may not.

    TWO SUBTRACTIONS, both deterministic, because a leak is the engine's
    failure and never a model's (`CLAUDE.md`, the firewall):

    * a PERSON the mind has not met is said as the observer's own gate says
      every authored prose about them (`gate`, `perception._authored_prose_
      gate`: an unknown identity becomes its descriptor), as a big thing's
      desc already is;
    * a PLACE the mind has not learned is never named at range (ruling 3),
      so a look that carries the name of a room this mind does not know --
      matched whole, as the room is called, in whatever script it is
      written, the longest name first (`_place_forms`) -- or of a region, is
      not said at all, and the place reads by its ground as before. A look
      says what an eye meets ("a footbridge of rope"); the name a place is
      CALLED by ("the rope bridge") is what the mind learns by a channel,
      and the planner is told so (`plan_rooms.far_look`). The one exception
      is a room's name its own look uses as the word for what the place is
      (`_said_as_a_word`, `SIGHT_NAMES`).

    `forms` is `_place_forms`' floor, or None when this mind lacks no name;
    `own` the rooms whose own look this is (a building's: every room of the
    mass), empty for a region's; `scene` the scene the read pass is open
    over (`_through_gate`)."""
    if not look:
        return ""
    gated = []

    def through_gate():
        if not gated:
            gated.append(_through_gate(scene, gate, look))
        return gated[0]
    # The place names first, on the look AS WRITTEN: the people gate
    # rewrites a name's own parts into a descriptor, and a place called
    # after somebody ("the Gale house") would then slip past as a phrase
    # that names no place at all.
    if isinstance(forms, _Floor):
        for m in forms.pattern.finditer(look):
            if m.group(0).casefold() in forms.unknown \
                    and not _said_as_a_word(forms, m.group(0), own, through_gate):
                return ""
    return normalize_far_look(through_gate())


def _breadth(scene, rid):
    """"wide" for open ground whose AUTHORED extent or size is large or
    more -- never the size the engine guesses from a room's name."""
    from world.spatial import size_from_extent
    room = _rooms(scene).get(rid) or {}
    tier = size_from_extent(room.get("extent")) or str(room.get("size") or "").strip().casefold()
    return "wide" if tier in ("large", "huge", "vast") else ""


# ---------------------------------------------------------------------------
# Places that already stand, read by their ground (2026-10-09)
# ---------------------------------------------------------------------------
#
# THE OWNER'S GO-AHEAD (2026-10-09, "far looks everywhere"): only places a
# plan wrote since 2026-10-08 had a far look, so a room the Director minted
# in a beat and every place of an older story read by their ground. The Room
# now writes a look onto a place that already stands
# (`plot_packages.set_far_looks`), and the planting sketch is handed the
# places that want one (`standing_looks_wanted`, through the fill's frontier
# report). What may be written is decided HERE, once, for the operation, the
# sketch and the fill alike: a look fills a place that reads by its ground,
# or replaces the Room's own word that nobody has changed since -- and a
# look the plan seeded, a beat wrote, the opening wrote or a host edited or
# cleared stands, as the plan's own rule keeps it (`structure.
# PLAN_SEEDED_FIELDS`, `regions.lay_planned_region_far_look`).

#: THE ROOM'S WORD ON A STANDING PLACE, per frame: ``{room id: the far look
#: the Room's look operation last wrote there}``, and "" where a HOST has
#: written or cleared that room's look by hand (the World Browser's room
#: card) -- a host's word the operation never writes over. Read and written
#: by `plot_packages.set_far_looks` and the World Browser alone; a scene
#: whose places nobody looked at carries none. Room-keyed, like
#: `structure.LAID_LOOKS_KEY` beside it, so the entity-rename walk leaves it
#: alone (`commit_scene_state._ENTITY_RENAME_SKIP`).
WRITTEN_LOOKS_KEY = "far_looks_written"

#: Why a look may or may not be written, as `room_look_writable` and
#: `region_look_writable` answer it: the first two may be written, the rest
#: stand. Engine words for a reader to explain, never said to a mind.
LOOK_WRITE_REASONS = ("none", "own", "host", "changed", "standing", "cleared",
                      "undeclared", "inside", "absent")


def _written_ledger(scene):
    ledger = (scene or {}).get(WRITTEN_LOOKS_KEY)
    return ledger if isinstance(ledger, dict) else {}


def _look_verdict(current, written, has_written, laid):
    """The one rule for a room and a region alike: ``(may, why)``.

    * the Room's operation wrote here before: it may replace its own word
      while the place still reads by it ("own"); a host's mark ("host") and
      any other word since ("changed") stand;
    * the place reads by a look nobody recorded -- the plan's, a beat's, the
      opening's or a host's -- and it stands ("standing");
    * the plan laid a look and the place reads by none now: somebody cleared
      it, and the clear stands ("cleared");
    * otherwise the place reads by its ground and a look may be written
      ("none")."""
    if has_written:
        written = normalize_far_look(written)
        if not written:
            return False, "host"
        return (True, "own") if current == written else (False, "changed")
    if current:
        return False, "standing"
    if laid:
        return False, "cleared"
    return True, "none"


def room_look_writable(scene, rid):
    """``(may, why)``: whether the Room's look operation may write room
    `rid`'s far look in this scene now (`_look_verdict`). A room the scene
    does not hold ("absent"), the inside of a body ("inside") and a room
    declaring no exposure ("undeclared": the far layer reads declared
    ground only, so no far eye sees it) take none."""
    rid = str(rid)
    room = _rooms(scene).get(rid)
    if not isinstance(room, dict):
        return False, "absent"
    if str(room.get("parent_entity") or "").strip():
        return False, "inside"
    if declared_ground(scene, rid) is None:
        return False, "undeclared"
    ledger = _written_ledger(scene)
    from world.structure import LAID_LOOKS_KEY
    laid = (scene or {}).get(LAID_LOOKS_KEY)
    laid = laid.get(rid) if isinstance(laid, dict) else None
    return _look_verdict(normalize_far_look(room.get("far_look")),
                         ledger.get(rid), rid in ledger, laid)


def region_look_writable(entry):
    """``(may, why)`` for a region's registry entry (`regions.
    region_registry`): the same rule, read off the entry's own records --
    `far_look_written` (the Room's word, "" a host's) and `far_look_laid`
    (the plan's)."""
    entry = entry if isinstance(entry, dict) else {}
    return _look_verdict(normalize_far_look(entry.get("far_look")),
                         entry.get("far_look_written"),
                         isinstance(entry.get("far_look_written"), str),
                         normalize_far_look(entry.get("far_look_laid")))


def _building_fronts(scene, graph):
    """Every enclosed room a far walk enters a building by, as `far_places`
    does: joined to open ground by an edge that does not go DOWN into it
    from the ground, and not standing under that ground -- "a cellar under
    the ground is no building on it". Each is a front the far layer builds a
    mass from (`building_of`), which takes in no room below that front's
    floor: a building on a slope, or fronting a street and a terrace above
    it, is a different mass from each side.

    GROUND THAT OPENS ONTO THIS ROOM ALONE is no way in for a far eye: a
    far walk reaches ground from a room beside it, and a body beside this
    room has it in its near field, which the far layer never answers. So a
    room fronts only ground that touches some other room too -- a street,
    a terrace with a hill beyond it, a courtyard another wing looks across
    -- and never a balcony or a landing off it alone. Measured on the live
    play db (2026-10-09): a watchtower's top cabin fronting its own balcony
    was offered in three scenes, and no stored view, 56 walks in all, ever
    read a look there."""
    from world.site_plan import room_elevation_m
    from world.spatial import normalize_vertical
    fronts = set()
    for ground in _rooms(scene):
        if declared_ground(scene, ground) not in OPEN_GROUND:
            continue
        floor = room_elevation_m(scene, ground)
        for edge in graph.get(ground) or ():
            other = str(edge.get("to"))
            if declared_ground(scene, other) != "building" \
                    or normalize_vertical(edge.get("vertical")) == "down" \
                    or room_elevation_m(scene, other) < floor - CELLAR_BELOW_M \
                    or not any(str(e.get("to")) != other for e in graph.get(ground) or ()):
                continue
            fronts.add(other)
    return fronts


def _first_look_at(scene, order):
    """Where in a mass's reading order (`far_places`: its front, then each
    room in from it) the first room carrying a far look stands; None when
    none does and the mass reads by its ground."""
    return next((i for i, rid in enumerate(order) if far_look_of(scene, rid)), None)


def _made_for_another_side(scene, front, rid, fronts, mass):
    """Whether the far look on `rid`, which the view from `front` reads, was
    made for ANOTHER side of the building: the Room's own unchanged word
    (`room_look_writable` "own") on another front whose own view does not
    take `front` in -- a terrace front's look, read from the street below
    for want of the street front's own, said of a mass it was never written
    for. A look somebody else wrote stands as what the view reads, and one
    the Room wrote on a front that builds this same mass -- another door
    onto the street -- was made for this very view (review 2026-10-09,
    N1)."""
    return (rid != front and rid in fronts and front not in mass(rid)[0]
            and room_look_writable(scene, rid) == (True, "own"))


def _look_lands_clear(scene, front, graph, fronts, mass):
    """Whether a look written on `front` changes no OTHER view of its
    building but one that reads by its ground with nobody's word on it. A
    front's look is read from every front whose mass takes it in, wherever
    it stands in that mass's reading order: it must not come before a look
    already written on another of its rooms, the Room's own included (that
    view would read the new word in place of the one it reads), and it may
    fill a view that reads by its ground only where no room of that mass
    carries a cleared or host's mark (`room_look_writable`). A look made for
    ANOTHER side (`_made_for_another_side`) is not one this protects: a door
    that reads the terrace's one-storey word for a two-storey mass is a view
    owed its own, and a look written for it lands (review B1, 2026-10-09: two
    street doors that each reached the other before the stair read the
    terrace look for good)."""
    for other in fronts & _whole_building(scene, front, graph):
        if other == front:
            continue
        members, order = mass(other)
        if front not in members:
            continue
        first = _first_look_at(scene, order)
        if first is not None:
            if first > order.index(front) and not _made_for_another_side(
                    scene, other, order[first], fronts, mass):
                return False
        elif not all(room_look_writable(scene, m) == (True, "none") for m in members):
            return False
    return True


def standing_looks_wanted(scene, starts, *, regions=None):
    """The standing places, and parts of the map, a far eye near `starts`
    could be told about that read by their ground alone: ``{"places":
    [...], "regions": [...]}``, nearest first. [] lists when none.

    WITHIN REACH is the far layer's own: every room the scene holds within
    `REACH_HOPS` of a start over any declared edge, in a start's locale --
    the places a far line from where the story stands, or a step from it,
    could carry. Not only what an eye sees this beat: a body indoors looks
    out on nothing, and the street it steps into should not read as "open
    ground" for want of the beat it stood inside.

    A PLACE is declared open or sheltered ground, or a BUILDING seen from
    outside, read as the far layer reads it: FROM EACH FRONT (`_building_
    fronts`), the mass `building_of` builds from that front, offered by the
    front while that view reads by its ground -- the far layer says a
    building by the first room of the mass, in its reading order, that
    carries a look -- or by a look made for another side of it
    (`_made_for_another_side`; the place then says whose, `reads_look_of`).
    A building fronting a street and a terrace above it is two views, and a
    look on its street front never reaches the terrace side, whose mass
    holds no room below its own floor (review 2026-10-09, F3: claimed by the
    first front reached, the terrace side read as "a building" for good).
    The terrace side's look does reach the street side, and is read there
    until the street front has its own -- a one-storey side's word said of
    a two-storey mass -- so each side is offered whichever the story stands
    nearer, and a side reading another side's look stays wanted (N1: the
    street front, skipped as reached by the terrace front's look, was never
    offered from the hill). A front that builds the same mass as a front
    already offered -- another door onto the same street -- is not offered
    again: that front's look was made for this view too. Nor is one whose
    look would be read from another side in place of a look already
    written there (`_look_lands_clear`). Each is offered only where
    `room_look_writable` lets the Room write every room of its mass
    ("none", or its own word): a place that reads by a look somebody else
    wrote, or whose look somebody cleared, is not wanted.

    A PART OF THE MAP (`regions`, the frame's registry) is wanted where some
    ground of it in reach reads by its ground and the region has no far look
    the operation may write over (`region_look_writable` "none"): its look
    is what that ground reads by at the outline. A registry the stage could
    not read offers no region (`REGIONS_UNREAD`)."""
    from world.spatial import room_locale
    rooms = _rooms(scene)
    graph = _graph(scene)
    starts = [str(s) for s in starts or () if str(s) in rooms]
    locales = {room_locale(rooms.get(s)) for s in starts}
    hops = {s: 0 for s in starts}
    queue = deque(starts)
    while queue:
        cur = queue.popleft()
        if hops[cur] >= REACH_HOPS:
            continue
        for edge in graph.get(cur) or ():
            other = str(edge.get("to"))
            if other in hops or other not in rooms:
                continue
            hops[other] = hops[cur] + 1
            queue.append(other)
    fronts = _building_fronts(scene, graph)
    masses = {}

    def mass(front):
        """A front's mass and its reading order, as `far_places` reads it."""
        if front not in masses:
            members, rise = building_of(scene, front, graph)
            masses[front] = (members, [front, *rise])
        return masses[front]

    places, offered, region_ground = [], [], {}
    for rid in sorted(hops, key=lambda r: (hops[r], r)):
        if room_locale(rooms.get(rid)) not in locales:
            continue
        ground = declared_ground(scene, rid)
        if ground in OPEN_GROUND:
            if far_look_of(scene, rid):
                continue
            region = str((rooms.get(rid) or {}).get("region") or "")
            if region:
                region_ground.setdefault(region, []).append(rid)
            if room_look_writable(scene, rid) == (True, "none"):
                places.append({"room": rid, "ground": ground, "hops": hops[rid]})
        elif ground == "building" and rid in fronts:
            members, order = mass(rid)
            first = _first_look_at(scene, order)
            reads = order[first] if first is not None else None
            if (reads is not None
                    and not _made_for_another_side(scene, rid, reads, fronts, mass)) \
                    or any(mass(front)[0] == members for front in offered) \
                    or not all(room_look_writable(scene, m)[0] for m in members) \
                    or not _look_lands_clear(scene, rid, graph, fronts, mass):
                continue
            offered.append(rid)
            place = {"room": rid, "ground": "building", "hops": hops[rid],
                     "members": sorted(members)}
            if reads is not None:
                place["reads_look_of"] = reads
            places.append(place)
    wanted_regions = []
    if not isinstance(regions, _UnreadRegions):
        for region, ground_rooms in sorted(
                region_ground.items(), key=lambda kv: (min(hops[r] for r in kv[1]), kv[0])):
            entry = (regions or {}).get(region)
            if isinstance(entry, dict) and region_look_writable(entry) == (True, "none"):
                wanted_regions.append({"region": region,
                                       "hops": min(hops[r] for r in ground_rooms),
                                       "rooms": list(ground_rooms)})
    return {"places": places, "regions": wanted_regions}
