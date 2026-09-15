# spatial_walk.py
"""Walking as a path over cells: where a body is after so many paces.

The sight and sound fields already lay every room out as a grid of cells,
one cell a pace, and place bodies on it from their stations. Movement did
not use it: a walk was a room a beat, a body arrived "in" a room and stood
nowhere in particular, and a doorway was a place only when the spatial hand
wrote a station for it. The owner's ask (2026-09-15): bodies do not have to
land at anchors. A place is a cell; an anchor is a cell with a name.

So a walk here is a path over cells, through doorways into the next room's
cells, advanced by a budget of paces. `walk` answers where a body is when
the budget runs out: the room, the cell, whether it arrived, and every room
it passed through (a body that crosses rooms has been in every one of them,
`passable_path`'s reason). It never stores anything; the caller writes the
answer into `positions` and `stations[name].cell`.

The path avoids what a body cannot walk through: an anchor at waist height
or taller (`BLOCKING_HEIGHT`) is walked round, a floor-height feature (a
rug, a hearthstone, a drain) is walked over, and a doorway's own cells
never block. Four-neighbour steps, so every step is one pace and a diagonal
costs what walking it costs; ties break on the smaller coordinates, so a
reroll walks the same line.

Two numbers are the owner's (`docs/design/DESIGN_ROOM_GEOMETRY.md` names
one cell a pace):

  PACES_PER_SECOND     an unhurried walk, 1.8 paces a second (0.75 m each)
  DEFAULT_BEAT_SECONDS what a beat covers when no span is stated, 10 s

Derived, never stored, no model anywhere.
"""

from __future__ import annotations

import heapq
from typing import Optional

from world.spatial_fov import (
    _door_cells,
    _inward,
    anchor_cells,
    body_cell,
    height_rank,
    room_grid,
)
from world.spatial_geometry import normalize_cell
from world.spatial_identity import room_of
from world.spatial_routing import passable_path

#: An unhurried walk: 1.8 paces a second, about 1.35 m/s at the 0.75 m pace
#: `spatial_routing._DISTANCE_UNIT_METERS` reads.
PACES_PER_SECOND = 1.8
#: A run: twice the walk, 3.6 paces a second (about 2.7 m/s, a steady jog).
RUN_PACES_PER_SECOND = 3.6
#: The paces a declaration may name: a walk (the default) or a run.
PACES = ("walk", "run")
#: A beat that states no span of time covers this many seconds of walking:
#: `world.mechanics.UNCLAIMED_BEAT_SECONDS`, the clock's own silent beat.
DEFAULT_BEAT_SECONDS = 10.0
#: An anchor this tall or taller is walked round; shorter is walked over.
BLOCKING_HEIGHT = "waist"

_STEPS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def paces_for(seconds=None, pace=None) -> int:
    """How many paces a beat of `seconds` covers at `pace` (walk, or run),
    at least one."""
    try:
        span = float(seconds) if seconds is not None else DEFAULT_BEAT_SECONDS
    except (TypeError, ValueError):
        span = DEFAULT_BEAT_SECONDS
    if span <= 0:
        span = DEFAULT_BEAT_SECONDS
    rate = RUN_PACES_PER_SECOND if str(pace or "").strip().casefold() == "run" \
        else PACES_PER_SECOND
    return max(1, int(round(span * rate)))


def blocked_cells(scene: dict, room_id) -> frozenset:
    """The cells a body cannot walk through in this room: every cell of an
    anchor at `BLOCKING_HEIGHT` or taller, except a doorway's."""
    blocked = set()
    floor = height_rank(BLOCKING_HEIGHT)
    for aid, placed in (anchor_cells(scene, room_id) or {}).items():
        if str(aid).startswith("door:") or placed.get("implicit"):
            continue
        if height_rank(placed.get("height")) < floor:
            continue
        blocked.update(tuple(c) for c in (placed.get("cells") or ()))
    return frozenset(blocked)


def held_cells(scene: dict, room_id, walker=None) -> frozenset:
    """The cells of `room_id` some OTHER body stands on."""
    me = str(walker or "").strip().casefold()
    held = set()
    for name, where in ((scene or {}).get("positions") or {}).items():
        if str(where) != str(room_id) or str(name).strip().casefold() == me:
            continue
        cell = body_cell(scene, name)
        if cell is not None:
            held.add(tuple(cell))
    return frozenset(held)


def door_cell(scene: dict, room_id, neighbour_id, near=None,
              avoid=()) -> Optional[tuple]:
    """The cell of this room's doorway onto `neighbour_id`: the aperture
    cell nearest `near` (the middle when no `near` is given), skipping the
    cells in `avoid` -- an open side is crossed where the walker reaches
    it, and a doorway another body fills is not crossed (None when every
    cell of it is filled). None when the edge has no bearing to place it
    by."""
    cells, _bearing = _door_cells(scene, room_id, neighbour_id)
    if not cells:
        return None
    cells = [tuple(c) for c in cells]
    free = [c for c in cells if c not in set(avoid)]
    if not free:
        return None
    if near is None:
        return free[len(free) // 2]
    nx, ny = tuple(near)
    return min(free, key=lambda c: ((c[0] - nx) ** 2 + (c[1] - ny) ** 2, c))


def entry_cell(scene: dict, room_id, from_room, near_index=None) -> tuple:
    """Where a body stands the moment it has come into `room_id` from
    `from_room`: the doorway cell it came through -- for an open side, the
    cell across from where it crossed (`near_index` along the side) -- or
    the room's centre when the doorway cannot be placed."""
    cells, _bearing = _door_cells(scene, room_id, from_room)
    if not cells:
        return room_grid(scene, room_id).centre()
    cells = [tuple(c) for c in cells]
    if near_index is not None and len(cells) > 1:
        return cells[max(0, min(len(cells) - 1, int(near_index)))]
    return cells[len(cells) // 2]


def inside_the_door(scene: dict, room_id, from_room, entered_at=None) -> tuple:
    """One pace into the room from its doorway onto `from_room`: where a
    walk that names no destination in the room ends, so the body is in the
    room and not standing in its door. `entered_at` is the doorway cell the
    body actually came through -- on an open side that is wherever it
    crossed, not the side's middle."""
    grid = room_grid(scene, room_id)
    cells, bearing = _door_cells(scene, room_id, from_room)
    if not cells or not bearing:
        return grid.centre()
    cells = [tuple(c) for c in cells]
    x, y = (tuple(entered_at) if entered_at is not None and tuple(entered_at) in cells
            else cells[len(cells) // 2])
    dx, dy = _inward(bearing)
    return grid.nearest((x + dx, y + dy))


def cell_path(scene: dict, room_id, start, goal) -> list:
    """The shortest four-neighbour path of cells from `start` to `goal`
    inside one room, both ends included, round what blocks; [] when the
    goal cannot be reached. Start and goal are always walkable -- a body
    stands where it stands. Ties break on the smaller coordinates."""
    grid = room_grid(scene, room_id)
    start = grid.nearest(tuple(start))
    goal = grid.nearest(tuple(goal))
    if start == goal:
        return [start]
    blocked = blocked_cells(scene, room_id) - {start, goal}
    frontier = [(0, start, (start,))]
    seen = {start}
    while frontier:
        cost, cell, path = heapq.heappop(frontier)
        for dx, dy in _STEPS:
            nxt = (cell[0] + dx, cell[1] + dy)
            if nxt in seen or nxt in blocked or not grid.contains(nxt):
                continue
            if nxt == goal:
                return list(path) + [nxt]
            seen.add(nxt)
            heapq.heappush(frontier, (cost + 1, nxt, path + (nxt,)))
    return []


# One storey of stair, in paces of the beat's budget: fifteen or so risers
# and the landings, walked at a walk. The owner's number (2026-09-15).
FLIGHT_PACES = 6


def _edge_is_vertical(scene: dict, from_room, to_room) -> bool:
    for room_id, other in ((from_room, to_room), (to_room, from_room)):
        room = ((scene or {}).get("rooms") or {}).get(room_id) or {}
        for edge in room.get("adjacent") or []:
            if isinstance(edge, dict) and edge.get("to") == other and edge.get("vertical"):
                return True
    return False


def free_cell_near(scene: dict, room_id, cell, walker=None) -> tuple:
    """`cell`, or the nearest cell of the room that neither furniture
    (`blocked_cells`) nor another body holds. Nobody lands in a shed: the
    yard's east door opened one pace from a head-high shed and the arrival
    cell was inside its footprint (Skerry Light, 2026-09-15)."""
    grid = room_grid(scene, room_id)
    cell = grid.nearest(tuple(cell))
    taken = blocked_cells(scene, room_id) | held_cells(scene, room_id, walker)
    if cell not in taken:
        return cell
    free = [c for c in grid.cells if c not in taken]
    if not free:
        return cell
    return min(free, key=lambda c: ((c[0] - cell[0]) ** 2 + (c[1] - cell[1]) ** 2, c))


def anchor_stand_cell(scene: dict, room_id, anchor_id, near=None):
    """Where a body stands when it goes TO a fixture: the cells a station
    `at` it would seat a body on (`spatial_fov._anchor_stand_cells`), the
    one nearest `near`; None when the room has no such anchor."""
    from world.spatial_fov import _anchor_stand_cells
    grid = room_grid(scene, room_id)
    cells = _anchor_stand_cells(scene, room_id, grid, str(anchor_id), {"at": str(anchor_id)})
    cells = [tuple(c) for c in (cells or ()) if grid.contains(tuple(c))]
    if not cells:
        return None
    if near is None:
        return cells[0]
    nx, ny = tuple(near)
    return min(cells, key=lambda c: ((c[0] - nx) ** 2 + (c[1] - ny) ** 2, c))


def standing_cell(scene: dict, name: str) -> tuple:
    """The cell a body walks from: its measured cell, or the room's centre
    when it stands nowhere in particular."""
    cell = body_cell(scene, name)
    if cell is not None:
        return tuple(cell)
    room_id = room_of(scene, name)
    return room_grid(scene, room_id).centre()


def walk(scene: dict, name: str, to_room, to_cell=None, *, paces,
         to_anchor=None, from_room=None, from_cell=None) -> Optional[dict]:
    """Where `name` is after walking up to `paces` paces toward `to_room`
    (and `to_cell` or `to_anchor` in it): {room, cell, arrived, crossed,
    paces} -- or None when the body has no room, the destination is no
    room, or no passable route joins them.

    A leg at a time inside each room, the doorway's cell as each leg's end,
    one pace to cross into the next room at its own doorway, and the walk
    goes on in the new room's cells with what budget is left. With no cell
    or anchor named in the destination, the walk ends one pace inside its
    door; a room that is the body's own is walked within.

    `from_room` / `from_cell` say where the walk STARTS when the scene
    handed in already carries this beat's diff (a route scene): the body's
    room and cell as the beat began, not where the diff put it.
    """
    here = str(from_room or "").strip() or room_of(scene, name)
    rooms = (scene or {}).get("rooms") or {}
    to_room = str(to_room or "").strip()
    if not here or to_room not in rooms:
        return None
    if to_anchor and to_cell is None:
        stand = anchor_stand_cell(scene, to_room, to_anchor)
        if stand is not None:
            to_cell = stand
    goal_cell = normalize_cell(list(to_cell)) if to_cell is not None else None
    if goal_cell is not None:
        goal_cell = free_cell_near(scene, to_room, goal_cell, name)
    route = [] if here == to_room else passable_path(scene, here, to_room, limit=None)
    if here != to_room and not route:
        return None
    budget = max(0, int(paces))
    room_id = here
    cell = (room_grid(scene, here).nearest(tuple(from_cell))
            if from_cell is not None else standing_cell(scene, name))
    crossed = []
    came_from = None
    entered_at = None
    walked = 0
    legs = list(route)
    while True:
        final = not legs
        if final:
            goal = goal_cell
            if goal is None:
                goal = (inside_the_door(scene, room_id, came_from, entered_at)
                        if came_from else cell)
                goal = free_cell_near(scene, room_id, goal, name)
        else:
            taken = held_cells(scene, room_id, name)
            goal = door_cell(scene, room_id, legs[0], near=cell, avoid=taken)
            all_cells, _b = _door_cells(scene, room_id, legs[0])
            if goal is None and all_cells:
                # THE DOORWAY IS FILLED: another body stands in every cell of
                # it, and a body in a doorway is the door. The walk ends
                # where it stands.
                return {"room": room_id, "cell": cell, "arrived": False,
                        "crossed": crossed, "paces": walked, "blocked": True,
                        "held_by": "doorway"}
            if goal is None:
                # A DOOR WITH NO BEARING CANNOT BE PLACED, but the room is
                # still as wide as it is: reaching it costs half the grid's
                # side from wherever the body stands, and the body stays
                # where it stood until the budget covers that.
                needed = max(1, room_grid(scene, room_id).side // 2)
                if budget < needed:
                    return {"room": room_id, "cell": cell, "arrived": False,
                            "crossed": crossed, "paces": walked + budget}
                budget -= needed
                walked += needed
                goal = cell
        path = cell_path(scene, room_id, cell, goal)
        if not path:
            return {"room": room_id, "cell": cell, "arrived": False,
                    "crossed": crossed, "paces": walked, "blocked": True}
        steps = min(len(path) - 1, budget)
        cell = path[steps]
        budget -= steps
        walked += steps
        if cell != path[-1]:
            return {"room": room_id, "cell": cell, "arrived": False,
                    "crossed": crossed, "paces": walked}
        if final:
            # NOBODY STANDS ON ANYBODY: an arrival cell another body holds
            # puts this one on the nearest free cell beside it.
            taken = held_cells(scene, room_id, name)
            if cell in taken:
                grid = room_grid(scene, room_id)
                free = [c for c in ((cell[0] + dx, cell[1] + dy) for dx, dy in _STEPS)
                        if grid.contains(c) and c not in taken
                        and c not in blocked_cells(scene, room_id)]
                if free:
                    cell = min(free)
            return {"room": room_id, "cell": cell, "arrived": True,
                    "crossed": crossed, "paces": walked}
        if budget <= 0:
            return {"room": room_id, "cell": cell, "arrived": False,
                    "crossed": crossed, "paces": walked}
        nxt = legs.pop(0)
        prev = room_id
        # A DOORWAY IS ONE OPENING SEEN FROM TWO ROOMS. A body standing in
        # the far room's door cell fills it as surely as one in this
        # room's; the check above saw only this side, so a keeper planted
        # in the stairhead was stepped past and the climber seated beside
        # her one pace inside (Skerry Light turn 8, 2026-09-15).
        far_cells, _fb = _door_cells(scene, nxt, prev)
        far_cells = [tuple(c) for c in far_cells] if far_cells else []
        if far_cells and all(c in held_cells(scene, nxt, name) for c in far_cells):
            return {"room": room_id, "cell": cell, "arrived": False,
                    "crossed": crossed, "paces": walked, "blocked": True,
                    "held_by": "doorway"}
        # A FLIGHT OF STAIRS IS NOT A DOORWAY. Crossing a vertical edge
        # costs `FLIGHT_PACES` of the budget on top of the doorway pace; a
        # body whose paces run out on the stair holds the stairfoot cell
        # and the walk carries on next beat. Without it a body climbed
        # three storeys of a tower in six paces, because each floor's
        # stairhead sat on the wall its stairfoot did (Skerry Light,
        # 2026-09-15).
        if _edge_is_vertical(scene, prev, nxt):
            # As many flights as there are storeys between the two rooms
            # (`spatial_levels.level_span`), one where levels are unknown.
            from world.spatial_levels import level_span
            flights = FLIGHT_PACES * level_span(scene, prev, nxt)
            if budget < flights + 1:
                return {"room": room_id, "cell": cell, "arrived": False,
                        "crossed": crossed, "paces": walked + budget}
            budget -= flights
            walked += flights
        exit_cells, _b = _door_cells(scene, prev, nxt)
        exit_cells = [tuple(c) for c in exit_cells] if exit_cells else []
        near_index = exit_cells.index(cell) if cell in exit_cells else None
        room_id = nxt
        came_from = prev
        cell = entry_cell(scene, room_id, prev, near_index=near_index)
        entered_at = cell
        taken = held_cells(scene, room_id, name)
        if cell in taken:
            # Somebody stands just inside; step in beside them.
            grid = room_grid(scene, room_id)
            free = [c for c in ((cell[0] + dx, cell[1] + dy) for dx, dy in _STEPS)
                    if grid.contains(c) and c not in taken]
            if free:
                cell = min(free)
        budget -= 1
        walked += 1
        crossed.append(room_id)


__all__ = [
    "BLOCKING_HEIGHT", "DEFAULT_BEAT_SECONDS", "PACES", "PACES_PER_SECOND",
    "RUN_PACES_PER_SECOND", "blocked_cells", "cell_path", "door_cell",
    "entry_cell", "free_cell_near", "anchor_stand_cell", "held_cells", "FLIGHT_PACES",
    "inside_the_door", "paces_for", "standing_cell", "walk",
]
