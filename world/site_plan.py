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
