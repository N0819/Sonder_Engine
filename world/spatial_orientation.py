"""Allocentric bearings and observer-relative orientation policy.

This module owns the conversion between authored compass truth on room edges
and egocentric sectors derived for an observer. It deliberately has no
dependency on the larger spatial domain.
"""

import re
from typing import Optional


_BEARINGS = ("n", "ne", "e", "se", "s", "sw", "w", "nw")
_BEARING_DEG = {bearing: index * 45 for index, bearing in enumerate(_BEARINGS)}

_BEARING_ALIASES = {
    "n": "n", "north": "n",
    "ne": "ne", "northeast": "ne",
    "e": "e", "east": "e",
    "se": "se", "southeast": "se",
    "s": "s", "south": "s",
    "sw": "sw", "southwest": "sw",
    "w": "w", "west": "w",
    "nw": "nw", "northwest": "nw",
}

# Observer-relative words are not authorable allocentric truth. A model that
# emits one as a bearing gets it dropped, never coerced into a compass point.
_EGOCENTRIC_WORDS = {
    "left", "right", "ahead", "forward", "forwards", "front", "infront",
    "behind", "back", "backward", "backwards", "rear", "aside", "beside",
    "sideways", "port", "starboard", "onward", "onwards", "up", "down",
}

_OPPOSITE_BEARING = {
    "n": "s", "s": "n", "e": "w", "w": "e",
    "ne": "sw", "sw": "ne", "nw": "se", "se": "nw",
}

_REL_SECTORS = (
    "ahead", "ahead_right", "right", "behind_right",
    "behind", "behind_left", "left", "ahead_left",
)
_LEFT_SECTORS = {"left", "ahead_left", "behind_left"}
_RIGHT_SECTORS = {"right", "ahead_right", "behind_right"}


def normalize_bearing(value) -> Optional[str]:
    """Collapse an authored bearing to the 8-way compass, if valid."""
    raw = str(value or "").strip().casefold()
    if not raw:
        return None
    key = re.sub(r"[^a-z]", "", raw)
    if key in _EGOCENTRIC_WORDS:
        return None
    return _BEARING_ALIASES.get(key)


def opposite_bearing(bearing: Optional[str]) -> Optional[str]:
    return _OPPOSITE_BEARING.get(bearing)


_OPPOSITE_VERTICAL = {"up": "down", "down": "up"}


def normalize_vertical(value) -> Optional[str]:
    level = str(value or "").strip().casefold()
    if level in ("up", "upstairs", "above", "upward", "upwards", "ascend"):
        return "up"
    if level in ("down", "downstairs", "below", "downward", "downwards",
                 "descend"):
        return "down"
    return None


def opposite_vertical(vertical: Optional[str]) -> Optional[str]:
    return _OPPOSITE_VERTICAL.get(vertical)


def relative_bearing(
    facing: Optional[str],
    target: Optional[str],
) -> Optional[str]:
    """Return the egocentric sector of an absolute target bearing."""
    if facing not in _BEARING_DEG or target not in _BEARING_DEG:
        return None
    index = round(
        ((_BEARING_DEG[target] - _BEARING_DEG[facing]) % 360) / 45
    ) % 8
    return _REL_SECTORS[index]


def lateral_of(
    facing: Optional[str],
    target: Optional[str],
) -> Optional[str]:
    """Return ``left``/``right`` for a lateral target, otherwise ``None``."""
    relative = relative_bearing(facing, target)
    if relative in _LEFT_SECTORS:
        return "left"
    if relative in _RIGHT_SECTORS:
        return "right"
    return None


def _find_edge(room: Optional[dict], to_id: str) -> Optional[dict]:
    """Return the adjacency edge from ``room`` to ``to_id``, if present."""
    if not isinstance(room, dict):
        return None
    for edge in room.get("adjacent") or []:
        if isinstance(edge, dict) and edge.get("to") == to_id:
            return edge
    return None


def travel_bearing(
    scene: dict,
    from_room: str,
    to_room: str,
) -> Optional[str]:
    """Return the absolute bearing for travel between two adjacent rooms."""
    rooms = scene.get("rooms") or {}
    forward = _find_edge(rooms.get(from_room), to_room)
    if forward is not None:
        bearing = normalize_bearing(forward.get("dir"))
        if bearing:
            return bearing
    back = _find_edge(rooms.get(to_room), from_room)
    if back is not None:
        bearing = normalize_bearing(back.get("dir"))
        if bearing:
            return opposite_bearing(bearing)
    return None


def normalize_scene_bearings(scene: dict) -> dict:
    """Normalize and reconcile optional bearings on room adjacency edges.

    Reciprocal edges must be opposites. Contradictions and same-bearing
    collisions are dropped rather than guessed; the doorway remains intact.
    """
    if not isinstance(scene, dict):
        return scene
    rooms = scene.get("rooms") or {}

    for room in rooms.values():
        if not isinstance(room, dict):
            continue
        for edge in room.get("adjacent") or []:
            if not isinstance(edge, dict) or "dir" not in edge:
                continue
            bearing = normalize_bearing(edge.get("dir"))
            if bearing:
                edge["dir"] = bearing
            else:
                edge.pop("dir", None)

    for room_id, room in rooms.items():
        if not isinstance(room, dict):
            continue
        for edge in room.get("adjacent") or []:
            if not isinstance(edge, dict):
                continue
            neighbor_id = edge.get("to")
            if (
                not neighbor_id
                or neighbor_id == room_id
                or neighbor_id not in rooms
            ):
                continue
            back = _find_edge(rooms.get(neighbor_id), room_id)
            if back is None:
                continue
            forward_dir, back_dir = edge.get("dir"), back.get("dir")
            if forward_dir and back_dir:
                if opposite_bearing(forward_dir) != back_dir:
                    edge.pop("dir", None)
                    back.pop("dir", None)
            elif forward_dir and not back_dir:
                back["dir"] = opposite_bearing(forward_dir)
            elif back_dir and not forward_dir:
                edge["dir"] = opposite_bearing(back_dir)

    # `vertical` gets the same treatment `dir` has always had, and for a
    # sharper reason. A staircase's two ends are not the same direction: if the
    # hall says the upstairs is UP and the upstairs says the hall is UP too,
    # then from up there the hall is above you. Live (chat 63) both ends of one
    # staircase read `up`, and the room it joined had a SECOND staircase going
    # down to a basement -- with both edges reading the same way there is
    # nothing left to tell one flight from the other.
    for room_id, room in rooms.items():
        if not isinstance(room, dict):
            continue
        for edge in room.get("adjacent") or []:
            if not isinstance(edge, dict) or "vertical" not in edge:
                continue
            level = normalize_vertical(edge.get("vertical"))
            if level:
                edge["vertical"] = level
            else:
                edge.pop("vertical", None)

    for room_id, room in rooms.items():
        if not isinstance(room, dict):
            continue
        for edge in room.get("adjacent") or []:
            if not isinstance(edge, dict):
                continue
            neighbor_id = edge.get("to")
            if (not neighbor_id or neighbor_id == room_id
                    or neighbor_id not in rooms):
                continue
            back = _find_edge(rooms.get(neighbor_id), room_id)
            if back is None:
                continue
            forward_v, back_v = edge.get("vertical"), back.get("vertical")
            if forward_v and back_v:
                if opposite_vertical(forward_v) != back_v:
                    # Same rule as `dir`: a contradiction is dropped rather
                    # than guessed. The edge itself survives -- a staircase
                    # nobody can agree the direction of is still a way through.
                    edge.pop("vertical", None)
                    back.pop("vertical", None)
            elif forward_v and not back_v:
                back["vertical"] = opposite_vertical(forward_v)
            elif back_v and not forward_v:
                edge["vertical"] = opposite_vertical(back_v)

    # Judge inferred bearings in the same pass by resolving collisions after
    # reciprocity.
    #
    # A WAY THAT GOES UP OR DOWN DOES NOT STAND ON A WALL, SO IT CANNOT
    # OCCUPY ONE. This loop exists for two ways out competing for the same
    # stretch of wall; a stair, a ladder, a hatch or a gallery opening is not
    # on the wall at all -- it is in the floor or the ceiling, and the compass
    # word on it says which way it LEANS, not which wall it takes up. Grouping
    # by `dir` alone made a vertical edge collide with the horizontal one
    # beside it and stripped the bearing from BOTH, and from both reciprocals,
    # so the doorway that really was on that wall lost the one fact placing
    # it.
    #
    # Live, the hearing at Vaunt's Yard (2026-09-05, PM1): the establish
    # authored `guild_hall -> gallery {dir: "s", vertical: "up"}` (a narrow
    # wooden stair) beside `guild_hall -> yard {dir: "s"}` (the tall yard
    # doors). Both left this loop bearingless while the anchors
    # `gallery_stair` and `hall_doors` kept theirs -- and with no bearing on
    # the stair edge nothing could work out that the gallery looks down on the
    # floor it overlooks (PM2).
    #
    # Two verticals the same way up the same wall still collide with each
    # other: two flights of stairs up the south wall are exactly the ambiguity
    # this loop is for.
    for room_id, room in rooms.items():
        if not isinstance(room, dict):
            continue
        by_bearing: dict[str, list] = {}
        for edge in room.get("adjacent") or []:
            if isinstance(edge, dict) and edge.get("dir"):
                key = edge["dir"]
                if edge.get("vertical"):
                    key = "%s|%s" % (key, edge["vertical"])
                by_bearing.setdefault(key, []).append(edge)
        for colliding in by_bearing.values():
            if len(colliding) < 2:
                continue
            for edge in colliding:
                edge.pop("dir", None)
                back = _find_edge(rooms.get(edge.get("to")), room_id)
                if back is not None:
                    back.pop("dir", None)

    return scene


#: The order a doorway with no stated bearing is offered a wall in. Walls
#: before corners, because a doorway is a gap in a wall and a room set
#: corner-to-corner with its neighbour is the stranger arrangement of the
#: two; the four cardinals first, then the four diagonals.
DERIVED_BEARING_ORDER = ("n", "e", "s", "w", "ne", "se", "sw", "nw")

#: How many doorways one room can be laid out with: the eight points, one
#: apiece. A room with a ninth way through is not a room this can draw, and
#: the ninth stays unplaced rather than sharing a wall with the eighth --
#: sharing is the collision `normalize_scene_bearings` already drops both
#: sides of. Named because every cap in this engine is named.
DERIVED_BEARING_LIMIT = len(DERIVED_BEARING_ORDER)


def derived_edge_bearings(scene: dict) -> dict:
    """``{(room_id, to_id): bearing}`` for every doorway NEITHER side gave a
    bearing to -- a guess at which wall it is in, so the sense composites
    have somewhere to lay the neighbour out.

    WHY THERE HAS TO BE A GUESS. `spatial_fov.room_field` places a
    neighbour only where the edge carries a bearing, and a bearing is
    written by a hand that stood in the room and said which way the door
    was. A room the Writers' Room planned has never been stood in: the plan
    writes `{to, barrier, distance}` and the schema asks for no bearing at
    all. Measured across the two stories in play on 2026-09-06, chats 115,
    116 and the descent copy: 4 of 54 edges carried a bearing, and 0 of the
    38 that belong to a planned room. So every composite was an ISLAND --
    one room, no neighbours -- and the near sound field, switched on for the
    world the same day, answered `none` to a loud noise through an open door
    in the next room because the next room was not on the field at all.

    WHAT THE GUESS IS AND IS NOT. It is the same KIND of estimate the field
    already makes: `_place_anchors` seeds an anchor's place along its wall
    from a hash, and every reader has always used that. It decides which
    wall a doorway is in, and nothing else -- not that a room lies north in
    the world, not what a body would learn by walking it. A bearing anyone
    DECLARED is never moved, never reassigned, and never contradicted here;
    only a doorway both sides left silent about is given one.

    Pairwise and reciprocal by construction: the pair is keyed by its two
    sorted ids and assigned from one place, so the two rooms receive
    opposite bearings and each lays the other out against the same wall.
    A point already spoken for at either end is skipped, so a derived
    doorway never collides with a declared one or with another derived one.
    """
    rooms = (scene or {}).get("rooms") or {}
    if not isinstance(rooms, dict):
        return {}
    used: dict = {}
    spoken = set()
    pairs = set()
    for room_id, room in rooms.items():
        if not isinstance(room, dict):
            continue
        for edge in room.get("adjacent") or []:
            if not isinstance(edge, dict) or not edge.get("to"):
                continue
            other = str(edge["to"])
            if other == str(room_id) or other not in rooms:
                continue
            pair = tuple(sorted((str(room_id), other)))
            pairs.add(pair)
            bearing = normalize_bearing(edge.get("dir"))
            if not bearing:
                continue
            spoken.add(pair)
            used.setdefault(str(room_id), set()).add(bearing)
            opposite = opposite_bearing(bearing)
            if opposite:
                used.setdefault(other, set()).add(opposite)
    silent = pairs - spoken
    out = {}
    for near, far in sorted(silent):
        taken_near = used.setdefault(near, set())
        taken_far = used.setdefault(far, set())
        for bearing in DERIVED_BEARING_ORDER:
            opposite = opposite_bearing(bearing)
            if bearing in taken_near or not opposite or opposite in taken_far:
                continue
            taken_near.add(bearing)
            taken_far.add(opposite)
            out[(near, far)] = bearing
            out[(far, near)] = opposite
            break
    return out
