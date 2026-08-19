# spatial_routing.py
"""Walks over the room graph: edge distance, spatial_rel, adjacency, passable
routes, sprint reach, and corridor sightlines."""

import re
from typing import Optional

from world.spatial_orientation import normalize_bearing, opposite_bearing

from world.spatial_barriers import (_PASSABLE_BARRIERS, _SIGHT_BARRIERS,
                              neighbor_map, normalize_barrier)
from world.spatial_containment import container_of
from world.spatial_light import _LIGHT_SIGHT, effective_light, light_blocks_sight


# Edge `distance` tiers, most intimate first. Measured live (S1d): 86% of
# edges author a distance, in 29 surface forms -- `3m`, `20m`, `1 step`, bare
# numbers, `close`, `immediate` -- while the ONLY value any code consumed
# (`remote`, hear_level's dead-drop branch) appeared zero times. The exact
# inverse of the stations failure: data everyone writes and nothing can read.
# This normalizer is the read-side fix, mirroring normalize_barrier: applied
# at spatial_rel's one edge-read site so every consumer inherits it.
DISTANCE_TIERS = ("adjacent", "near", "far", "remote")

_DISTANCE_ALIASES = {
    "adjacent": "adjacent", "close": "adjacent", "immediate": "adjacent",
    "touching": "adjacent", "beside": "adjacent", "short": "adjacent",
    "step": "adjacent", "steps": "adjacent", "same": "adjacent",
    "near": "near", "nearby": "near", "mid": "near", "middle": "near",
    "moderate": "near", "medium": "near",
    "far": "far", "long": "far", "distant": "far",
    "remote": "remote",
}

# Rough meters-per-unit for the metric/imperial/stride forms the corpus
# actually writes. A bare number is read as meters -- `10` and `10m` appear
# side by side live and plainly mean the same thing.
_DISTANCE_UNIT_METERS = {
    "m": 1.0, "meter": 1.0, "meters": 1.0, "metre": 1.0, "metres": 1.0,
    "km": 1000.0, "kilometer": 1000.0, "kilometers": 1000.0,
    "ft": 0.3048, "foot": 0.3048, "feet": 0.3048,
    "yd": 0.9144, "yard": 0.9144, "yards": 0.9144,
    "mi": 1609.0, "mile": 1609.0, "miles": 1609.0,
    "step": 0.75, "pace": 0.75, "paces": 0.75, "stride": 0.75, "strides": 0.75,
}


def normalize_edge_distance(value) -> str:
    """Collapse an authored edge `distance` to one of DISTANCE_TIERS.

    Word aliases and numeric/metric parsing (<=5m adjacent, <=20m near,
    <=75m far, beyond remote -- a `200 m` gallery edge is a genuinely remote
    edge that used to read as `near` by raw passthrough). Absent or
    unparseable answers `near`, which is exactly the default every consumer
    already assumed -- the default can never masquerade as a measurement
    because only authored values can reach the other three tiers.
    """
    raw = str(value if value is not None else "").strip().casefold()
    if not raw:
        return "near"
    if raw in _DISTANCE_ALIASES:
        return _DISTANCE_ALIASES[raw]
    matched = re.match(r"^~?\s*(\d+(?:\.\d+)?)\s*([a-z]+)?\.?$", raw)
    if not matched:
        return "near"
    scale = _DISTANCE_UNIT_METERS.get(matched.group(2) or "m")
    if scale is None:
        # An unrecognized unit is not evidence of anything; refuse to guess.
        return "near"
    meters = float(matched.group(1)) * scale
    if meters <= 5:
        return "adjacent"
    if meters <= 20:
        return "near"
    if meters <= 75:
        return "far"
    return "remote"


def _one_way_edges(rooms: dict, source, target):
    """Every `one_way_window` edge `source` declares toward `target`."""
    return [edge for edge in ((rooms.get(source) or {}).get("adjacent") or [])
            if isinstance(edge, dict) and edge.get("to") == target
            and normalize_barrier(edge.get("barrier")) == "one_way_window"]


def _declares_one_way(rooms: dict, source, target) -> bool:
    """Does `source` declare a one-way window looking into `target`?"""
    return bool(_one_way_edges(rooms, source, target))


def sight_direction(rooms: dict, a_room, b_room):
    """Which room a one-way window between these two LOOKS FROM, or None.

    THE DIRECTION IS A FIELD, because as a property of which side declared
    the edge it could not survive the way scenes are actually written. Every
    other barrier is symmetric -- a door is a door from both ends -- so
    writing adjacency from both sides is the universal habit, and it is
    correct for every value except this one. `one_way_window` alone meant
    something different depending on who wrote it, so the habit silently
    cancelled it: two "sight passes this way" declarations name no direction
    at all.

    Measured live, chat 82 ("Sarah Moon -- Hinami attempt 2"): the interview
    suite declared the mirror from the annex AND from the cell, and both
    prompts had asked for `wall` on the blind side. The model wrote the edge
    the way edges are written. A deterministic floor that depends on a model
    breaking a habit every other barrier rewards is not a floor.

    `sight_from` fixes that by making the two declarations AGREE instead of
    contradict: both sides name the same watching room, so writing it twice
    is right rather than fatal, and a scene can be repaired by naming a room
    rather than by deleting a declaration from the correct side.

    Returns the room id sight passes FROM, or None when no edge says. Both
    sides are read, and a disagreement resolves to None -- two edges naming
    different watchers is the same contradiction in a new spelling, and
    picking one would be the guess this field exists to remove.
    """
    named = set()
    for source, target in ((a_room, b_room), (b_room, a_room)):
        for edge in _one_way_edges(rooms, source, target):
            room = str(edge.get("sight_from") or "").strip()
            if room:
                named.add(room)
    if len(named) != 1:
        return None
    watcher = named.pop()
    return watcher if watcher in (a_room, b_room) else None


def mutual_one_way_window(scene: dict, a_room, b_room) -> bool:
    """Do BOTH rooms declare a one-way window into each other? Then neither
    sees, and the contradiction is reported.

    `one_way_window` carries its asymmetry on ONE edge -- declared in the
    direction it looks, with the way back a wall -- so writing it from both
    sides says "sight passes each way", which is a `window`, a word the
    vocabulary already has. Nobody reaches for the asymmetric value meaning
    the symmetric one; the pair is a mistake every time, and nothing in it
    says which direction was meant.

    ADMITTING WAS TRIED FIRST AND IS WRONG. Measured live, chat 82 ("Sarah
    Moon -- Hinami attempt 2"): the interview suite declared it from the annex
    to the cell AND from the cell back, so the restrained subject watched her
    interviewer through a mirror her own room note called opaque, and the view
    said both things two sentences apart. A barrier whose entire meaning is
    asymmetry, written symmetrically by a writer who had `window` available
    and did not use it, is not evidence that everyone should see.

    Subtracting costs the other direction too, and that cost is real: the
    interviewer loses the body she is there to watch until somebody names the
    blind side. It is accepted because a gap is visible and a leak is not --
    the beat plays wrong, obviously, and the notice below tells the Director
    exactly what to fix, where showing a mind what the fiction told it it
    could not see is a thing nobody notices until it has been true for fifty
    beats.

    The RIGHT answer is neither guess. Sight through the glass belongs to the
    edge, what the glass looks like from each side belongs to the edge as
    well (so the blind side reads "a mirror" and the seeing side "transparent
    glass"), and KNOWING the glass is one-way is prior knowledge -- an
    interviewer was briefed, a subject was not -- which is not a property of a
    room at all. `docs/UNBUILT.md` 1.68 carries that design.
    """
    rooms = scene.get("rooms") or {}
    if not (_declares_one_way(rooms, a_room, b_room)
            and _declares_one_way(rooms, b_room, a_room)):
        return False
    # ...unless the pair says which way it looks, which is exactly what
    # `sight_from` is for: two declarations that AGREE are one fact written
    # twice, the way every other barrier is written.
    return sight_direction(rooms, a_room, b_room) is None


def stamp_sight_direction(scene: dict) -> list:
    """Write down which way an unambiguous one-way window looks. Idempotent.

    THIS IS WHAT MAKES THE FEATURE SURVIVE ITS OWN SCENE. A one-sided
    declaration already says the direction -- the edge looks the way it was
    written -- but it says it in a form that the next beat can destroy without
    touching it: the moment anything redeclares the far side, the pair reads as
    two contradicting claims and the mirror is gone. Nothing malicious has to
    happen. Adjacency is normally written from both rooms, because for every
    other barrier that is correct.

    So the direction is promoted to a FIELD at the merge, on the beat it is
    still knowable. After that the mirror is habit-proof: a later redeclaration
    from the blind side agrees with the stamp instead of cancelling it, because
    `sight_direction` reads the field before it reads who declared what.

    Only where exactly one side declares it and neither side has said
    otherwise. A pair already carrying `sight_from` is left alone (it has an
    author), and a bare two-sided pair is NOT stamped -- nothing in it names a
    direction, and inventing one is the guess the field exists to remove. That
    case stays a contradiction and stays reported.

    Returns [(room, other, watcher)] for what it stamped.
    """
    rooms = (scene or {}).get("rooms") or {}
    if not isinstance(rooms, dict):
        return []
    stamped = []
    for room_id, room in rooms.items():
        if not isinstance(room, dict):
            continue
        for edge in room.get("adjacent") or []:
            if not isinstance(edge, dict):
                continue
            other = edge.get("to")
            if not other or normalize_barrier(edge.get("barrier")) \
                    != "one_way_window":
                continue
            if sight_direction(rooms, room_id, other) is not None:
                continue                       # somebody already said
            if _declares_one_way(rooms, other, room_id):
                continue                       # ambiguous; report, never guess
            edge["sight_from"] = room_id
            stamped.append((str(room_id), str(other), str(room_id)))
    return stamped


def contradictory_sight_edges(scene: dict, prev_scene: dict = None) -> list:
    """Room pairs that both declare a one-way window into each other.

    See `mutual_one_way_window` for why this is reported rather than resolved.
    Sight is unchanged: the pair reads as an ordinary window, which is what
    two "sight passes this way" declarations literally say, and which of the
    two the author meant is not recoverable from the scene.

    Reported the beat it APPEARS -- the same subtraction `guessed_room_sizes`
    makes, because a standing condition repeated every beat is one the reader
    learns to skip. `prev_scene=None` asks for it unconditionally, which is
    how a scene that was ALREADY contradictory before this check existed gets
    told once instead of never: the appearance test compares against the
    previous beat, and for those scenes the previous beat was contradictory
    too, so the pair would sit silent forever while the rooms stayed walled
    off from each other.

    Returns rows, not warnings -- the seam that knows whose warning list to
    write to does the reporting.
    """
    rooms = (scene or {}).get("rooms") or {}
    prev_rooms = (prev_scene or {}).get("rooms") if prev_scene is not None \
        else None
    out = []
    for a_id in rooms:
        for b_id in rooms:
            if str(a_id) >= str(b_id):
                continue            # one row per pair, not two
            if not mutual_one_way_window(scene, a_id, b_id):
                continue
            if prev_rooms is not None and mutual_one_way_window(
                    prev_scene, a_id, b_id):
                continue            # already contradictory, already reported
            out.append({
                "rooms": (str(a_id), str(b_id)),
                "names": (str((rooms.get(a_id) or {}).get("name") or a_id),
                          str((rooms.get(b_id) or {}).get("name") or b_id)),
            })
    return out


def spatial_rel(
    scene: dict,
    a_room: Optional[str],
    b_room: Optional[str],
) -> dict:
    if not a_room or not b_room:
        return {
            "same_room": False,
            "barrier": "unknown",
            "distance": "remote",
            "note": "no known spatial channel between these entities",
        }

    if a_room == b_room:
        return {
            "same_room": True,
            "barrier": "open",
            "distance": "same",
            # Whether there is light to see by here. A dark room hides the
            # person standing next to you, which is why this is carried even
            # for the same-room case.
            "light": effective_light(scene, b_room),
        }

    rooms = scene.get("rooms") or {}

    for index, (source, target) in enumerate((
        (a_room, b_room),
        (b_room, a_room),
    )):
        room = rooms.get(source) or {}

        for edge in room.get("adjacent") or []:
            if not isinstance(edge, dict):
                continue

            if edge.get("to") != target:
                continue

            barrier = normalize_barrier(edge.get("barrier"))
            # `a_room` is the OBSERVER, and this loop reads their own side
            # first -- so the forward direction of a one-way window needs no
            # special case at all. Found on the SECOND pass means we are
            # standing on the far side of one, which is a wall: that is what
            # the back of a two-way mirror is, and it is why the asymmetry can
            # live on a single edge instead of two declarations that
            # contradict each other. Sound and scent land in the same place a
            # wall does either way, so nothing else is lost by saying it this
            # way.
            if barrier == "one_way_window":
                # `sight_from` names the watching room outright, so it holds
                # however many sides declared the edge -- which is the point
                # of it being a field (`sight_direction`).
                watcher = sight_direction(rooms, a_room, b_room)
                if watcher is not None:
                    if watcher != a_room:
                        barrier = "wall"
                # Nothing said which way. Fall back to the older rule: the
                # edge looks in the direction it was declared, so finding it
                # on the second pass means standing behind it -- and finding
                # it on BOTH sides is a contradiction that subtracts in both
                # directions (`mutual_one_way_window`).
                elif index == 1 or _declares_one_way(rooms, target, source):
                    barrier = "wall"

            return {
                "same_room": False,
                "barrier": barrier,
                # What the barrier is made of, carried through so hearing can
                # account for it. Absent means "ordinary", which is the
                # behaviour every existing scene already had.
                "material": edge.get("material") or "",
                "distance": normalize_edge_distance(edge.get("distance")),
                # The light in the room being LOOKED AT: seeing into a dark
                # room from a lit one is still seeing nothing.
                "light": effective_light(scene, b_room),
            }

    return {
        "same_room": False,
        "barrier": "separated",
        "distance": "far",
    }


def passable_neighbors(scene: dict) -> dict:
    """{room_id: {rooms reachable in one step}} over passable edges only.

    Undirected, following the `nearby_rooms` precedent: an open doorway
    declared from either side can be walked through either way. Lifted out of
    `passable_route_exists` when crowds needed the same graph -- a crowd moves
    on the one graph everyone else walks, and §5 of the crowd proposal asks for
    exactly no second pathfinder.
    """
    return neighbor_map(scene, _PASSABLE_BARRIERS)


def passable_route_next_step(
    scene: dict,
    from_room: Optional[str],
    to_room: Optional[str],
) -> Optional[str]:
    """The FIRST room on a shortest passable walk from one room to another,
    or None when there is no such walk.

    `passable_route_exists` answers "could they get there"; this answers
    "where does one beat of getting there put them". It exists for travel
    that CONTINUES: a walk the player declared once and did not repeat,
    which the engine advances a leg at a time rather than teleporting at the
    end or abandoning the moment a beat is spent talking.

    Deterministic by construction, which the whole feature depends on --
    reroll and resume-from-stage both require the diff to be a function of
    its inputs, so neighbours are walked in sorted order and a tie between
    two equally short routes always breaks the same way. Same passability
    rule as `passable_route_exists`: only edges already open this beat make
    a path, so a walk does not advance through a door nobody has opened.
    """
    if not from_room or not to_room or from_room == to_room:
        return None
    rooms = scene.get("rooms") or {}
    if to_room not in rooms:
        return None
    neighbors = passable_neighbors(scene)

    # BFS from the destination BACKWARDS: the graph is undirected, so the
    # first neighbour of `from_room` this reaches is a first hop on some
    # shortest route. Searching from the destination means one pass answers
    # the question rather than one pass per candidate hop.
    seen = {to_room}
    frontier = [to_room]
    while frontier:
        nxt = []
        for room_id in frontier:
            for neighbor in sorted(neighbors.get(room_id, ())):
                if neighbor in seen:
                    continue
                if neighbor == from_room:
                    return room_id
                seen.add(neighbor)
                nxt.append(neighbor)
        frontier = sorted(nxt)
    return None


def passable_route_exists(
    scene: dict,
    from_room: Optional[str],
    to_room: Optional[str],
) -> bool:
    """True when to_room is reachable from from_room by walking only
    through passable doorways (barrier open / open_door), across any
    number of intermediate rooms.

    spatial_rel answers the DIRECT-adjacency question; this answers the
    traversal question the director_resolve movement backstop needs for a
    legitimate multi-room walk ("cross the corridor into the far office").
    Adjacency is treated as traversable in BOTH directions -- an open
    doorway declared from either side can be walked through either way
    (the nearby_rooms undirected-reachability precedent).

    A route requiring a still-closed door, wall, or unknown barrier does
    NOT count: only edges already passable this beat make a path. Callers
    that want a door opened this beat to count must pass a scene that
    already carries the beat's diff.
    """
    if not from_room or not to_room:
        return False
    if from_room == to_room:
        return True

    neighbors = passable_neighbors(scene)

    seen = {from_room}
    frontier = [from_room]
    while frontier:
        room_id = frontier.pop()
        for nxt in neighbors.get(room_id, ()):
            if nxt == to_room:
                return True
            if nxt not in seen:
                seen.add(nxt)
                frontier.append(nxt)
    return False


def nearby_rooms(
    scene: dict,
    center_room_ids,
    hops: int = 1,
) -> dict:
    """Rooms within `hops` adjacency steps of any of center_room_ids.

    Stage payloads currently serialize the entire scene.rooms dict into
    every LLM call regardless of relevance, so a large, mostly-explored
    building bloats every turn's context even though only the handful of
    rooms near where characters actually are matters for that turn's
    reasoning. This only trims what gets sent to a model -- deterministic
    checks (spatial_rel, hear_level, the passable-route validation in
    director_resolve) operate on the full, unfiltered scene in-process
    and must keep doing so; callers must filter only the payload copy,
    never the scene used for those checks.

    Adjacency is treated as undirected for this purpose (an edge declared
    from either side counts), since asymmetric declarations do happen and
    the question here is reachability for context purposes, not the
    perception-specific forward/reverse distinction visible_adjacent_rooms
    makes for what's visible through an open doorway.
    """
    rooms = scene.get("rooms") or {}
    # No barrier allowlist: this trims a PAYLOAD, and a room behind a locked
    # door is still a room the beat may be about.
    neighbors = neighbor_map(scene)

    included = {r for r in (center_room_ids or []) if r}
    frontier = set(included)

    for _ in range(max(0, hops)):
        next_frontier = set()
        for room_id in frontier:
            next_frontier |= neighbors.get(room_id, set()) - included
        if not next_frontier:
            break
        included |= next_frontier
        frontier = next_frontier

    return {rid: rooms[rid] for rid in included if rid in rooms}

def rooms_adjacent(scene, room_a, room_b):
    """Undirected: is room_b a declared neighbor of room_a (edge from either
    side)? Used to tell a real step (A->adjacent B) from a teleport/gap-cross."""
    if not room_a or not room_b:
        return False
    rooms = scene.get("rooms") or {}
    for a, b in ((room_a, room_b), (room_b, room_a)):
        room = rooms.get(a) or {}
        for edge in room.get("adjacent") or []:
            if isinstance(edge, dict) and edge.get("to") == b:
                return True
    return False


def _is_carried_interior(scene, room_id):
    """Is `room_id` the inside of something a body is carrying.

    You do not take in the inside of a bag, a case, a jar or a pocket as part
    of taking in the room it is being carried through -- looking in is an act,
    not ambience. Without this, every interior attached to a carried entity was
    permanently in its owner's field of view, so a character stood there
    perpetually perceiving the inside of their own belongings.

    Deliberately keyed on the CARRIER relation (or portability), not on any
    notion of smallness: a ship's hold you are walking through is an interior
    too, and it stays visible because nobody is carrying the ship.
    """
    rooms = (scene or {}).get("rooms") or {}
    room = rooms.get(room_id)
    if not isinstance(room, dict):
        return False
    parent = room.get("parent_entity")
    if not parent:
        return False

    entities = (scene or {}).get("entities") or {}
    entity = entities.get(parent)
    if not isinstance(entity, dict):
        entity = next(
            (e for e in entities.values()
             if isinstance(e, dict)
             and str(e.get("name") or "").strip().casefold()
             == str(parent).strip().casefold()),
            {},
        )
    if entity.get("portable"):
        return True
    # Carried right now, by a hand or inside another container.
    return container_of(scene, parent) is not None or \
        container_of(scene, str(entity.get("name") or "")) is not None


# How far a straight passage can be read, and how the reading coarsens. Sight
# down a corridor is real -- you see that it ends before you walk it -- but it
# degrades with distance into "somewhere along there", which is the form worth
# handing a character.
CORRIDOR_SIGHT_LIMIT = 6
_CORRIDOR_VAGUENESS = ((1, "just ahead"), (2, "a short way"),
                       (4, "some way"), (99, "far"))
# How many rooms down a line are NAMED. Beyond this the passage is reported as
# running on, without contents -- which is both what sight gives you and what
# keeps this from becoming a page per beat.
_CORRIDOR_NAMED = 2


def corridor_sightlines(scene, room_id):
    """What can be seen looking STRAIGHT along each passage out of a room.

    A character could previously see one room and no further, so a corridor
    ending three rooms north was indistinguishable from one running on -- he
    had to walk it. But you can see down a straight passage, and that you
    cannot see round the corner is what makes it worth having: sight follows
    the line until the passage turns, a door blocks it, or the dark swallows
    it.

    Deliberately coarse, and coarser with distance. The useful percept is "some
    way north the passage comes to an end", not a room count -- so `distance`
    is carried for ordering and `vagueness` for rendering, and a caller should
    prefer the latter.

    Returns [] when the scene's edges carry no `dir`, since without direction
    there is no line to follow and guessing one would invent a sense.
    """
    rooms = (scene or {}).get("rooms") or {}
    start = rooms.get(room_id)
    if not isinstance(start, dict):
        return []
    out = []
    for edge in start.get("adjacent") or []:
        if not isinstance(edge, dict) or not edge.get("dir"):
            continue
        heading = str(edge["dir"]).lower()
        if normalize_barrier(edge.get("barrier")) not in _SIGHT_BARRIERS:
            continue
        cur, prev, dist, terminus = edge.get("to"), room_id, 1, None
        # What is made out ALONG the line, not merely where it ends. Detail
        # decays the way sight does: the near chamber is read plainly, the next
        # by its one memorable feature, past that only that something is there.
        # Capped at _CORRIDOR_NAMED because a full description per room per
        # direction would be a page of prose every beat -- and because nobody
        # reads the far end of a corridor in that much detail anyway.
        along = []
        while cur and dist <= CORRIDOR_SIGHT_LIMIT:
            room = rooms.get(cur)
            if not isinstance(room, dict):
                terminus = None
                break
            # Anything short of full sight stops the line. Light spills
            # through an open doorway, so a dark room beside a lit one reads
            # `dim` -- and shapes are enough to know something is there, not
            # enough to read whether a passage ends. Reporting a terminus
            # through gloom would be inventing detail.
            if _LIGHT_SIGHT.get(effective_light(scene, cur), "full") != "full":
                terminus = "darkness"
                break
            onward = [
                e for e in (room.get("adjacent") or [])
                if isinstance(e, dict) and str(e.get("to")) != str(prev)
                and normalize_barrier(e.get("barrier")) not in ("wall",)
            ]
            if not onward:
                terminus = "dead_end"
                break
            if len(along) < _CORRIDOR_NAMED:
                along.append({
                    "room": room.get("name") or cur,
                    "detail": "clear" if dist == 1 else "landmark",
                })
            straight = [e for e in onward
                        if str(e.get("dir") or "").lower() == heading
                        and normalize_barrier(e.get("barrier")) in _SIGHT_BARRIERS]
            if len(onward) > 1:
                terminus = "opening"      # a junction: the line stops being one line
                break
            if not straight:
                # The passage bends. You cannot see ROUND a corner, but you can
                # see that it goes on rather than stopping -- which is the
                # difference between "bends and continues" and "bends into
                # who knows what". Nothing beyond the corner is claimed.
                terminus = "turn"
                break
            prev, cur, dist = cur, straight[0].get("to"), dist + 1
        if terminus:
            out.append({
                "dir": heading, "distance": dist, "terminus": terminus,
                "vagueness": next(v for lim, v in _CORRIDOR_VAGUENESS
                                  if dist <= lim),
                "along": along,
            })
    return out


# What one beat of running buys, in small-room units. A pace of three ordinary
# chambers is brisk without being a teleport; a large hall eats two of them and
# a vast one the whole budget, so a run crosses distance rather than room COUNT.
# Deliberately coarse: the engine is not simulating gait, it is answering "does
# a body cross this much ground in one beat" well enough that the answer is
# never absurd.
SPRINT_BUDGET = 3
_ROOM_COST = {"tiny": 1, "small": 1, "": 1, "medium": 1,
              "large": 2, "huge": 3, "vast": 3}


def passable_path(scene, from_room, to_room, limit=12):
    """The shortest walk of passable doorways from one room to another, as a
    list of rooms EXCLUDING the start and ending at `to_room` -- or [] when
    there is none.

    `passable_route_exists` answers whether; this answers which rooms. A body
    that crosses several rooms in one beat has been in every one of them, and
    a caller recording only where they stopped leaves holes in their memory
    exactly where their feet went. Adjacent rooms give a one-element path, so
    an ordinary step needs no special case.

    `limit` bounds the search: past a dozen rooms a single-beat "walk" is a
    teleport wearing a route, and reconstructing a path for it would dress the
    teleport up as ground covered.
    """
    if not from_room or not to_room or from_room == to_room:
        return []
    rooms = scene.get("rooms") or {}
    neighbors: dict[str, set] = {}
    for room_id, room in rooms.items():
        if not isinstance(room, dict):
            continue
        for edge in room.get("adjacent") or []:
            if not isinstance(edge, dict) or not edge.get("to"):
                continue
            if normalize_barrier(edge.get("barrier")) not in _PASSABLE_BARRIERS:
                continue
            neighbors.setdefault(str(room_id), set()).add(str(edge["to"]))
            neighbors.setdefault(str(edge["to"]), set()).add(str(room_id))

    from collections import deque
    prev = {str(from_room): None}
    queue = deque([(str(from_room), 0)])
    while queue:
        cur, depth = queue.popleft()
        if cur == str(to_room):
            path = []
            while cur is not None and prev[cur] is not None:
                path.append(cur)
                cur = prev[cur]
            return list(reversed(path))
        if depth >= limit:
            continue
        for nxt in sorted(neighbors.get(cur, ())):
            if nxt not in prev:
                prev[nxt] = cur
                queue.append((nxt, depth + 1))
    return []


def sprint_reach(scene, room_id, known_rooms=None):
    """How far a body could RUN out of this room, per passage, bends allowed.

    A character could only ever move one room per beat, which makes a courier
    whose whole craft is speed indistinguishable from someone strolling, and
    turns any distance into a queue of identical beats. Running is the obvious
    missing verb.

    The bound is DECISION, not sight -- and the first version got that wrong.
    It stopped a run at every bend on the reasoning that you cannot see round
    a corner, and the measurement said what that reasoning was worth: in a
    live 7x7 perfect maze, 39 of 49 rooms were two-exit corridor cells and
    almost every corridor cell was a bend, so 72 of 96 runnable passages
    offered exactly one room, the mean offer was 1.3 rooms, and the
    SPRINT_BUDGET never once bound. Winding is what makes a maze a maze;
    a sight-bounded run cannot exist in one. The worry sight was standing in
    for was never the corner itself -- a body enters a room it has not seen
    every time it walks through a doorway, and perceives it by being in it.
    The thing that genuinely costs a beat is a CHOICE: a junction run through
    at speed is a route picked without looking. So the run follows a corridor
    round its bends for as long as there is exactly one passable way onward,
    and stops where a decision (junction), the world (door, darkness,
    dead end), or the beat (full_reach) stops it. Decision-bounded, the same
    maze offers a mean of 2.48 rooms and the budget binds 64 times.

    A see-through side opening (window, bars) is not a junction: it offers no
    route, so it forces no choice. And the run itself still follows only
    PASSABLE doorways -- you can see through bars and you cannot run through
    them.

    `known_rooms` is the OFFER-side firewall, and it is why this function has
    two modes. Objectively (known_rooms=None, the Director's resolve ceiling)
    the reach reports the scene as it is -- the Director owns objective
    causality and may see it. But handed to a deciding character, that same
    report would smuggle unearned map: a mind standing still would learn that
    an unvisited passage winds on for three rooms and ends at a junction,
    geometry it never perceived. Running through ground teaches it; being
    TOLD the reach does not. So a character-facing caller passes the rooms
    that character has legitimately been in, and the offer extends only
    through what can be vouched for: the straight sightline from here (looking
    down a passage is ordinary sight, and it ends at the first bend), plus
    remembered rooms beyond it. Where the passage runs on into ground the
    view cannot vouch for, the offer stops with `stops: "unknown"` -- the run
    itself may still be declared open-ended, and resolves against the
    objective reach. One residue is documented rather than hidden: within
    remembered ground beyond the sightline, `door`/`darkness` stops read the
    room's CURRENT state, which anticipates by one beat what the run would
    discover anyway.

    Returns one entry per runnable passage:

        {"bearing": "n", "path": [rid, ...], "rooms": 2,
         "stops": "junction"|"dead_end"|"darkness"|"door"|"full_reach"|"unknown"}

    `bearing` is ABSENT when the doorway carries no `dir` -- the world gives
    no compass there, and the run is declared by destination instead. Such a
    passage's sightline ends at its first room: with no heading there is no
    straight line to certify, so everything beyond is remembered ground only.

    `full_reach` is the budget stop, and its name is deliberately about
    DISTANCE, not physiology. It was `winded` first, and the word beat its
    own documentation -- third label in this engine to do so (`closed` read
    as "no way through" kept a shrine unentered for five runs; `spent` read
    as "do not go" turned a courier off his own proven route). Observed
    verbatim: "he would be winded? But he might not want to be winded if he
    needs to assess contents" -- the best offer a run can get, the passage
    outlasting the beat, read as a penalty for taking it. A MARGINAL
    deterrent, measured precisely: the same character took one such run in
    full (beat 1 of the same arm) and then reasoned against later ones, so
    the label tipped close decisions rather than forbidding anything --
    which is how a mislabel does its damage. Worse, the penalty
    reading was FALSE as a distinguishing fact: every hard run arrives
    winded (the Director applies that cost whatever ends the run), so the
    label implied a consequence specific to maximal runs that is not
    specific at all. The stop reason names why the run ENDED; what running
    COSTS is the Director's to narrate, and the two must not share a word.

    `bearing` is the doorway taken OUT of this room; the path beyond it may
    bend. `path` is every room crossed, in order, ENDING at the room they
    finish in -- callers need the whole list, not the destination: a body
    that runs through three chambers has been in three chambers, and
    recording only where they stopped would leave holes in their map where
    their feet went. Empty list when nothing is runnable that way, and the
    passage is omitted.
    """
    rooms = (scene or {}).get("rooms") or {}
    start = rooms.get(room_id)
    if not isinstance(start, dict):
        return []
    known = None if known_rooms is None else {str(r) for r in known_rooms}
    out = []
    for edge in start.get("adjacent") or []:
        if not isinstance(edge, dict) or not edge.get("to"):
            continue
        if normalize_barrier(edge.get("barrier")) not in _PASSABLE_BARRIERS:
            continue
        # A doorway with no bearing is still a doorway, and a run through it
        # is still a run. Requiring `dir` here silently deleted the passage
        # from every run offer -- measured live (maze arm) as a shrine whose
        # ONLY approach could never be run, and beats of "fails to move east
        # due to missing bearing" while the character re-declared a compass
        # the world could not bind. The offer carries no `bearing` key
        # (absent means the world gives no compass here, per the
        # _onward_exits convention); `run_ends_at`/`path` still name it, so
        # a run is declared by its destination instead of a heading.
        heading = normalize_bearing(edge.get("dir"))
        cur, prev, spent, path, stops = edge.get("to"), room_id, 0, [], None
        # Whether `cur` is still on the straight line of sight from where the
        # body stands. The first room always is (you see it through the
        # doorway); a bend ends the line for good, even if the passage later
        # resumes the original heading.
        on_sightline = True
        while cur:
            cur = str(cur)
            room = rooms.get(cur)
            if not isinstance(room, dict):
                stops = "unknown"
                break
            # The offer-side firewall: past the sightline, only remembered
            # ground can be vouched for. Checked before light, because the
            # current darkness of a room you cannot see and have never
            # entered is exactly the kind of fact this gate exists to hold
            # back.
            if known is not None and not on_sightline and cur not in known:
                stops = "unknown"
                break
            # Running into a room you cannot see into is how a body breaks an
            # ankle. The world stopping you, not a decision.
            if _LIGHT_SIGHT.get(effective_light(scene, cur), "full") != "full":
                stops = "darkness"
                break
            cost = _ROOM_COST.get(
                str(room.get("size") or "").strip().lower(), 1)
            if spent + cost > SPRINT_BUDGET:
                stops = "full_reach"
                break
            spent += cost
            path.append(cur)
            onward = [
                e for e in (room.get("adjacent") or [])
                if isinstance(e, dict) and str(e.get("to")) != str(prev)
                and e.get("to")
            ]
            if not onward:
                stops = "dead_end"
                break
            passable = [e for e in onward if normalize_barrier(
                e.get("barrier")) in _PASSABLE_BARRIERS]
            if len(passable) > 1:
                # A junction is a decision, and a decision is a beat. Running
                # blind through one would be choosing without looking.
                stops = "junction"
                break
            if not passable:
                # The only way on is shut. The world stopping you.
                stops = "door"
                break
            nxt = passable[0]
            # No heading means no straight line to certify: the first room
            # is vouched by ordinary sight through the doorway, everything
            # beyond it must be remembered ground. Without this, a chain of
            # bearingless edges would hold `on_sightline` open forever and
            # walk the offer through ground the character never earned.
            if on_sightline and (heading is None
                                 or normalize_bearing(nxt.get("dir"))
                                 != heading):
                on_sightline = False
            prev, cur = cur, nxt.get("to")
        if path:
            entry = {"path": path, "rooms": len(path),
                     "stops": stops or "full_reach"}
            if heading:
                entry["bearing"] = heading
            out.append(entry)
    return out


def _onward_exits(scene, all_rooms, target_id, from_room):
    """How many ways out of `target_id` lead somewhere other than back here.

    Looking through a doorway into a chamber, you see whether it has another
    way out -- that is ordinary sight, not deduction. Without it a character
    has to physically walk into a dead end to discover it is one, which is
    exactly what was observed: a maze runner entered the same one-exit chamber
    six times, having never been given the one fact that would have told him.

    Requires FULL sight of the chamber, not merely some sight. Light spilling
    through an open doorway makes a dark room read `dim`, which is enough for
    bulk and movement and nowhere near enough to count doorways or tell which
    wall they are in -- `corridor_sightlines` already stops its line at
    anything short of full sight for exactly that reason, and the two must not
    disagree about what gloom can be read through. Absent means "could not
    tell", never "none" -- a caller must not read a missing key as a dead end.

    `onward_bearings` names WHICH ways those are, and it is not decoration. A
    bare count is read as a promise to continue: observed live, a runner given
    `onward_exits: 1` for the chamber to his west walked west into it four
    times over nine beats hunting a west exit that never existed -- the one
    other way out went north. He was not reasoning badly; he was told a number
    where he needed a bearing. Omitted per-edge when an edge carries no `dir`,
    and omitted entirely when none do, because a scene without directions has
    no bearings to give and inventing them would be inventing a sense.
    """
    if _LIGHT_SIGHT.get(effective_light(scene, target_id), "full") != "full":
        return {}
    # Counted by DESTINATION, and over reverse-declared edges too. A doorway
    # is one doorway whichever room's `adjacent` list happens to name it, and
    # the director routinely declares only one side: counting `target`'s own
    # edges alone reported nought for chambers that plainly had a way on, and
    # nought is what raises `visibly_no_way_through`. Inventing a dead end is
    # the worse error of the two -- it argues against a real route.
    ways = {}
    for edge in (all_rooms.get(target_id) or {}).get("adjacent") or []:
        if not isinstance(edge, dict):
            continue
        if normalize_barrier(edge.get("barrier")) == "wall":
            continue
        dest = str(edge.get("to") or "")
        if dest and dest != str(from_room):
            ways.setdefault(dest, normalize_bearing(edge.get("dir")))
    for other_id, other in all_rooms.items():
        if str(other_id) in (str(target_id), str(from_room)):
            continue
        if not isinstance(other, dict) or str(other_id) in ways:
            continue
        for edge in other.get("adjacent") or []:
            if not isinstance(edge, dict) or str(edge.get("to")) != str(target_id):
                continue
            if normalize_barrier(edge.get("barrier")) == "wall":
                continue
            # Seen from the far side, so the bearing is the far side's,
            # reversed. Same doorway, opposite wall.
            ways[str(other_id)] = opposite_bearing(
                normalize_bearing(edge.get("dir")))
            break
    out = {"onward_exits": len(ways)}
    bearings = []
    for heading in ways.values():
        if heading and heading not in bearings:
            bearings.append(heading)
    if bearings:
        out["onward_bearings"] = bearings
    return out


def visible_adjacent_rooms(
    scene: dict,
    room_id: str,
    extra_rooms: dict | None = None,
) -> list[dict]:
    if not room_id:
        return []

    all_rooms = dict(
        scene.get("rooms") or {}
    )

    if extra_rooms:
        all_rooms.update(extra_rooms)

    visible = []
    seen = set()

    # Forward adjacency: the current room explicitly points to another.
    current_room = all_rooms.get(room_id) or {}

    for edge in current_room.get("adjacent") or []:
        if not isinstance(edge, dict):
            continue

        barrier = normalize_barrier(
            edge.get("barrier")
        )

        if barrier not in _SIGHT_BARRIERS:
            continue

        adjacent_id = edge.get("to")
        if _is_carried_interior(scene, adjacent_id):
            continue

        if (
            not adjacent_id
            or adjacent_id not in all_rooms
            or adjacent_id in seen
        ):
            continue

        # The room record and the sightline have to agree, or the blind side
        # is refused a view and handed the neighbour's whole room anyway.
        if barrier == "one_way_window":
            _watcher = sight_direction(all_rooms, room_id, adjacent_id)
            if _watcher is not None:
                if _watcher != room_id:
                    continue
            elif _declares_one_way(all_rooms, adjacent_id, room_id):
                continue

        # This list is delivered as literal sight -- a perceiver's
        # `visible_rooms` admits the whole room record into their payload --
        # and an unlit room shows an opening full of nothing. The doorway
        # itself survives elsewhere (the current room's edge keeps its
        # barrier; only the destination is withheld, the same shape as the
        # F6 projection). `effective_light` already accounts for spill, so a
        # dark cellar behind a lit doorway reads dim and stays visible as
        # shapes; only total dark is withheld.
        if light_blocks_sight(effective_light(scene, adjacent_id)):
            continue

        room_data = all_rooms[adjacent_id]
        notes = (
            room_data.get("notes")
            or room_data.get("desc")
            or ""
        )

        # No prose does NOT mean no room. The reverse loop below has always
        # kept a descriptionless neighbour (test_reverse_adjacency exercises
        # exactly that), so skipping it here made visibility depend on which
        # side happened to declare the edge and on whether anyone had written
        # notes yet -- a bidirectional edge to the same undescribed room was
        # already included via the reverse pass. Sight is physical: an
        # unwritten room is still visibly THERE, and the deterministic
        # consumers of this list (commit.py's dead-end ledger, character.py's
        # seen_onward, narration.py's portal gating) read absence as "cannot
        # see", not as "nothing authored yet".
        visible.append({
            "room_id": adjacent_id,
            "room_name": (
                room_data.get("name")
                or adjacent_id
            ),
            "barrier": barrier,
            "description": notes[:800],
            **_onward_exits(scene, all_rooms, adjacent_id, room_id),
        })
        seen.add(adjacent_id)

    # Reverse adjacency: another room explicitly points back to the
    # current room. Do not include unrelated rooms with arbitrary open
    # edges.
    for other_id, room_data in all_rooms.items():
        if (
            other_id == room_id
            or other_id in seen
            or not isinstance(room_data, dict)
        ):
            continue

        for edge in room_data.get("adjacent") or []:
            if not isinstance(edge, dict):
                continue

            barrier = normalize_barrier(
                edge.get("barrier")
            )

            if (
                edge.get("to") != room_id
                # The reverse pass exists so a bidirectional doorway declared
                # from one side is visible from both. A one-way window is the
                # one edge where that generosity is wrong: it is declared in
                # the direction it looks, and looking back is what it refuses.
                or barrier == "one_way_window"
                or barrier not in _SIGHT_BARRIERS
                or _is_carried_interior(scene, other_id)
                # Same light gate as the forward loop: sight does not care
                # which room declared the edge, and neither does the dark.
                or light_blocks_sight(effective_light(scene, other_id))
            ):
                continue

            notes = (
                room_data.get("notes")
                or room_data.get("desc")
                or ""
            )

            visible.append({
                "room_id": other_id,
                "room_name": (
                    room_data.get("name")
                    or other_id
                ),
                "barrier": barrier,
                "description": notes[:800],
                # Sight does not care which room declared the edge. Omitting
                # this here made a whole class of neighbour permanently
                # opaque -- absent reads as "cannot tell from here", so a
                # visibly closed chamber that happened to be reverse-declared
                # had to be walked into to be ruled out.
                **_onward_exits(scene, all_rooms, other_id, room_id),
            })
            seen.add(other_id)

            break

    return visible
