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

    # Judge inferred bearings in the same pass by resolving collisions after
    # reciprocity.
    for room_id, room in rooms.items():
        if not isinstance(room, dict):
            continue
        by_bearing: dict[str, list] = {}
        for edge in room.get("adjacent") or []:
            if isinstance(edge, dict) and edge.get("dir"):
                by_bearing.setdefault(edge["dir"], []).append(edge)
        for colliding in by_bearing.values():
            if len(colliding) < 2:
                continue
            for edge in colliding:
                edge.pop("dir", None)
                back = _find_edge(rooms.get(edge.get("to")), room_id)
                if back is not None:
                    back.pop("dir", None)

    return scene
