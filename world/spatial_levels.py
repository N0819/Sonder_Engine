"""Storeys: which level a room is on, what lies over and under it, and the
shaft a stair runs up.

A room ABOVE another is a fact the engine had only as an edge: a stair,
ladder or hatch carrying `vertical: up|down`. That is enough to climb by
and nothing else -- two rooms with no stair between them were never above
or below each other, so no footfall crossed a ceiling and no frame could
say "the room overhead". The level is the number everything vertical
hangs on:

  * `level` on a room is its storey: 0 the ground, +1 the floor above, -1
    the floor below. Declared by the planner or the spatial hand where they
    know it, INFERRED here along vertical edges where they do not
    (`infer_room_levels`): the far end of an `up` edge is one level higher,
    of a `down` edge one lower, and the first room with no declared level
    in a scene that declares none is the ground.
  * `over` on a room names rooms it lies directly above with NO way
    between them -- a bedroom over a parlour, a loft over a byre. The
    engine derives the floor between them (`floor_edges`): a wall that is
    also a floor, crossed by sound at the floor's loss and by nothing else.
    `floor` on the upper room is the material of that floor, which sets
    the loss (`FLOOR_LOSS_DB`).
  * `way` on a vertical edge says what the way is: `stair`, `ladder`,
    `hatch`, or `overlook` -- a gallery rail, a balcony, a hole in the
    floor: a vertical opening a body looks and shouts through and does not
    walk through.
  * The shaft (`stack_of`) is the column of rooms one stair joins, ordered
    by level; a flight between two of them costs the storeys between them.

Built 2026-09-15 on the owner's go-ahead, after Skerry Light: four floors
on one stair were a chain of edges, and nothing knew they were a tower.
"""
from __future__ import annotations

from typing import Optional

from world.spatial_orientation import normalize_vertical

#: What a vertical edge may be. A closed engine vocabulary: anything else
#: is read as a stair, the fail-open answer a walker can use.
WAYS = ("stair", "ladder", "hatch", "overlook")

#: Transmission loss of a floor between two stacked rooms, by the upper
#: room's `floor` word, in dB. A timber floor lets a shout and a heavy
#: footfall through; masonry lets almost nothing. The owner's numbers
#: (2026-09-15); a floor with no word takes the sound field's
#: `FLOOR_CEILING_LOSS_DB` (50).
FLOOR_LOSS_DB = {"timber": 30.0, "board": 30.0, "plank": 30.0,
                 "stone": 50.0, "concrete": 50.0, "masonry": 50.0}


def _rooms(scene) -> dict:
    rooms = (scene or {}).get("rooms") or {}
    return rooms if isinstance(rooms, dict) else {}


def normalize_level(value) -> Optional[int]:
    """A storey number, or None for anything that is not one."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def edge_way(edge) -> str:
    """What a vertical edge is: one of `WAYS`, `stair` when it says nothing
    readable, `""` for an edge that is not vertical."""
    if not isinstance(edge, dict) or not normalize_vertical(edge.get("vertical")):
        return ""
    way = str(edge.get("way") or "").strip().casefold()
    return way if way in WAYS else "stair"


def declared_way(edge) -> str:
    """The way an edge DECLARES, or "" -- `edge_way` fails open to a stair;
    this does not, for the reader that must not guess (sight through an
    unmarked vertical opening keeps the open answer it always had)."""
    if not isinstance(edge, dict):
        return ""
    way = str(edge.get("way") or "").strip().casefold()
    return way if way in WAYS else ""


def is_overlook(edge) -> bool:
    return edge_way(edge) == "overlook"


def room_level(scene, room_id) -> Optional[int]:
    room = _rooms(scene).get(room_id)
    return normalize_level((room or {}).get("level")) if isinstance(room, dict) else None


def _edges(scene, room_id):
    """(other_id, 'up'|'down'|'level') for every edge this room has, its
    own and its neighbours' declared toward it: a door joins two rooms on
    one storey, a stair joins two a storey apart."""
    rooms = _rooms(scene)
    out = []
    room = rooms.get(room_id) or {}
    for edge in room.get("adjacent") or []:
        if isinstance(edge, dict) and edge.get("to") in rooms:
            out.append((str(edge["to"]), normalize_vertical(edge.get("vertical")) or "level"))
    seen = {o for o, _ in out}
    for other_id, other in rooms.items():
        if str(other_id) == str(room_id) or str(other_id) in seen or not isinstance(other, dict):
            continue
        for edge in other.get("adjacent") or []:
            if isinstance(edge, dict) and str(edge.get("to")) == str(room_id):
                v = normalize_vertical(edge.get("vertical"))
                out.append((str(other_id), ("down" if v == "up" else "up") if v else "level"))
                seen.add(str(other_id))
                break
    return out


def _vertical_edges(scene, room_id):
    """(other_id, 'up'|'down') for every vertical edge this room has."""
    return [(o, v) for o, v in _edges(scene, room_id) if v != "level"]


def _over_pairs(scene):
    """{(upper, lower)} from every room's declared `over`."""
    rooms = _rooms(scene)
    pairs = set()
    for rid, room in rooms.items():
        if not isinstance(room, dict):
            continue
        for under in room.get("over") or []:
            under = str(under or "").strip()
            if under and under in rooms and under != str(rid):
                pairs.add((str(rid), under))
    return pairs


def infer_room_levels(scene) -> dict:
    """Write `level` on every room that can be reached from a levelled one
    along its edges -- a door keeps the storey, a stair changes it -- or
    `over` declarations; return {room_id: level}
    for the rooms this call levelled. A declared level is never moved. A
    scene with no declared level at all takes its first room (sorted id,
    the player's room first when one is placed) as the ground."""
    rooms = _rooms(scene)
    if not rooms:
        return {}
    known = {rid: normalize_level(r.get("level")) for rid, r in rooms.items()
             if isinstance(r, dict) and normalize_level(r.get("level")) is not None}
    over = _over_pairs(scene)
    if not known and not over and not any(_vertical_edges(scene, rid) for rid in rooms):
        return {}          # a flat scene has no storeys to speak of
    if not known:
        p_room = None
        positions = (scene or {}).get("positions") or {}
        for name, rid in positions.items():
            if rid in rooms:
                p_room = str(rid)
                break
        seed = p_room or sorted(rooms)[0]
        known = {seed: 0}
    written = {}
    frontier = list(known)
    while frontier:
        rid = frontier.pop()
        here = known[rid]
        steps = [(other, here + {"up": 1, "down": -1, "level": 0}[v])
                 for other, v in _edges(scene, rid)]
        steps += [(lower, here - 1) for upper, lower in over if upper == rid]
        steps += [(upper, here + 1) for upper, lower in over if lower == rid]
        for other, level in steps:
            if other in known:
                continue
            known[other] = level
            written[other] = level
            frontier.append(other)
    for rid, level in known.items():
        room = rooms.get(rid)
        if isinstance(room, dict) and normalize_level(room.get("level")) != level:
            room["level"] = level
    return written


def rooms_over(scene, room_id) -> list:
    """Rooms directly above this one: the far end of every `up` edge, and
    every room declaring itself `over` this one."""
    out = [other for other, v in _vertical_edges(scene, room_id) if v == "up"]
    out += [upper for upper, lower in sorted(_over_pairs(scene)) if lower == str(room_id)]
    return list(dict.fromkeys(out))


def rooms_under(scene, room_id) -> list:
    out = [other for other, v in _vertical_edges(scene, room_id) if v == "down"]
    out += [lower for upper, lower in sorted(_over_pairs(scene)) if upper == str(room_id)]
    return list(dict.fromkeys(out))


def stack_of(scene, room_id) -> list:
    """The column this room stands in: every room reachable by vertical
    edges, lowest first (by level where levels are known)."""
    seen = {str(room_id)}
    frontier = [str(room_id)]
    while frontier:
        rid = frontier.pop()
        for other, _v in _vertical_edges(scene, rid):
            if other not in seen:
                seen.add(other)
                frontier.append(other)
    return sorted(seen, key=lambda r: (room_level(scene, r) if room_level(scene, r) is not None else 0, r))


def level_span(scene, a, b) -> int:
    """How many storeys lie between two rooms: the difference of their
    levels, or one where either is unknown."""
    la, lb = room_level(scene, a), room_level(scene, b)
    if la is None or lb is None:
        return 1
    return max(1, abs(la - lb))


def floor_edges(scene, room_id) -> list:
    """The floors this room shares with a room it lies over or under and
    has no way to: `{to, barrier: 'wall', vertical, floor: True,
    loss_db}`. Never written to the scene; the far sound field reads
    them."""
    rooms = _rooms(scene)
    out = []
    for upper, lower in sorted(_over_pairs(scene)):
        if str(room_id) not in (upper, lower):
            continue
        other = lower if str(room_id) == upper else upper
        if any(isinstance(e, dict) and str(e.get("to")) == other
               for e in (rooms.get(room_id) or {}).get("adjacent") or []):
            continue
        material = str((rooms.get(upper) or {}).get("floor") or "").strip().casefold()
        out.append({"to": other, "barrier": "wall",
                    "vertical": "down" if str(room_id) == upper else "up",
                    "floor": True, "implicit": True,
                    "loss_db": FLOOR_LOSS_DB.get(material)})
    return out


__all__ = ["WAYS", "FLOOR_LOSS_DB", "normalize_level", "edge_way", "is_overlook",
           "room_level", "infer_room_levels", "rooms_over", "rooms_under",
           "stack_of", "level_span", "floor_edges"]
