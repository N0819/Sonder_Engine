# spatial_pack.py
"""Where code stands each NEW fixture of a room being designed: along the
wall the model chose, so that no two things share a cell at one height.

THE DIVISION OF LABOUR (the owner, 2026-10-08: a model decides what and why,
code decides where and how). The model decides which fixtures a room holds,
what each one is, the wall it stands against (`dir`), its footprint, height,
opacity and lane -- and, where the prose fixes one, its place along that wall
(`offset`) or its cell. Code decides only where along its OWN wall a new
fixture stands, or which free cell one with no wall takes, and only when the
place its seed gave it is already taken at its height. Settling a wall that
cannot hold what the prose put on it -- move a fixture, shrink it, drop it --
stays the model's: code says how far over the wall is and where each fixture
that found no place would fit, and moves nothing to another wall. Moving a
fixture off the wall the prose names contradicts the prose; the layout lab's
fallback did exactly that to 7 of the 53 fixtures on the owner's preferred
shrine.

THE RULES, in the order they bind:
- A fixture that already stands -- one the world holds where the draft
  leaves it -- is an obstacle, never moved and never given a place.
- So is a fixture already SETTLED: one a plan has shown, at the place its
  seed gave it or one code wrote for it, and a place the model wrote itself
  (`offset` or `cell`). A place is written ONCE, so a later fixture never
  moves an earlier one; the caller says which fixtures are not settled
  (`movable`), and only those are placed here.
- A new fixture keeps its seeded place (`spatial_fov._place_anchors`)
  whenever that place is free at its height, so a room that packs clean
  today is drawn exactly as it was. When two new fixtures' seeds collide,
  the one that takes more of its wall keeps its seed, because it has the
  fewest other places to go (a one-pace bench kept its seed in the middle
  of a ten-pace wall and left no eight paces for the long table drafted
  beside it, chat 165's turn 3); ties go in the order they were drafted.
- Otherwise it takes the free place nearest its seed: along its own wall
  (written as `offset`, a fraction of the places the footprint leaves); for
  a corner, the nearest cell of the two walls that meet there; for a fixture
  with no wall, the nearest free cell (each written as `cell`). Every place
  is tried by the engine's own placement, so a run, a large footprint, a
  lane, a shaped room's rim and a corner two walls share are honoured
  exactly as they will be drawn.
- When a new fixture still finds no place only because other new ones of
  its wall and height kept places that leave no gap its length, those are
  laid end to end, each still on its own wall, from whichever end of the
  wall moves them least: the inn's six-pace west wall held a two-pace long
  table and a four-pace barrel rack exactly, and the table's seed left no
  four paces anywhere (chat 165's turn 3).

WHY A WALL FIXTURE IS PINNED BY ITS OFFSET. A cell pin lays a footprint east
and south of its origin whatever its wall (`_place_anchors`), and lays no
inset: a run on an east wall pinned by its cell would be one cell, not a run.
An offset keeps the fixture on its wall and the wall's own arithmetic.

WHAT COUNTS AS TAKEN is what the room designer's check counts as two
fixtures on one cell: same cell, same height, doorways excluded (an object in
front of a door is a placement the world allows; the owner's ruling of
2026-09-16). The check and the packer read one rule, so "free" here is
"clean" there.

Pure, total, no I/O, no model.
"""

from __future__ import annotations

from world.spatial_fov import (
    ROOM_CORNERS, _place_anchors, _seed, _wall_slot, anchor_cells, room_grid,
)
from world.spatial_geometry import effective_anchors
from world.spatial_lint import wall_loads

_STRAIGHT = ("n", "e", "s", "w")
_WALL_WORDS = {"n": "north", "e": "east", "s": "south", "w": "west",
               "ne": "north-east", "se": "south-east", "sw": "south-west",
               "nw": "north-west"}


def _doorway(aid) -> bool:
    """A doorway's implicit anchor -- the check's own test (`door:<to>`)."""
    return str(aid).startswith("door:")


def _fraction(offset: int, room_for: int) -> float:
    """An offset in places as the fraction `_wall_slot` reads back to it."""
    return round(offset / room_for, 4) if room_for > 0 else 0.0


def _trial(room_id, grid, aid, anchor, **place) -> list:
    """The cells the engine gives `anchor` at `place` (an `offset` or a
    `cell`), and nothing else of it changed."""
    trial = {k: v for k, v in anchor.items() if k not in ("offset", "cell")}
    trial.update(place)
    return [tuple(c) for c in _place_anchors(room_id, grid, {aid: trial})[aid]["cells"]]


def _along_wall(room_id, grid, aid, anchor, wall, footprint):
    """`({"offset": fraction}, cells)` for every place along `wall` the
    anchor could stand, its seeded place first and then outward from it --
    nearest first, never the leftmost, so packed rooms do not line up
    against one end of every wall."""
    probe = {k: v for k, v in anchor.items() if k not in ("offset", "cell")}
    probe["dir"] = wall
    along, length, seeded, _source = _wall_slot(grid, wall, probe, footprint,
                                                _seed(room_id, aid))
    room_for = max(0, along - length)
    for offset in sorted(range(room_for + 1), key=lambda o: (abs(o - seeded), o)):
        frac = _fraction(offset, room_for)
        yield {"offset": frac}, _trial(room_id, grid, aid, probe, offset=frac)


def _near(room_id, grid, aid, anchor, origin, cells):
    """`(cell pin, cells)` for each of `cells`, nearest `origin` first."""
    ox, oy = origin
    for x, y in sorted(cells, key=lambda c: ((c[0] - ox) ** 2 + (c[1] - oy) ** 2, c)):
        yield {"cell": [x, y]}, _trial(room_id, grid, aid, anchor, cell=[x, y])


def _places(room_id, grid, aid, anchor, rec):
    """Where the anchor may stand without leaving what the model chose: its
    own wall, its own corner's two walls, or -- with no wall -- the floor."""
    bearing = rec.get("dir")
    if bearing in _STRAIGHT:
        return _along_wall(room_id, grid, aid, anchor, bearing, rec["footprint"])
    if bearing in ROOM_CORNERS:
        rim = {cell for wall in bearing for cell in grid.rim(wall)}
        return _near(room_id, grid, aid, anchor, grid.corner(bearing), rim)
    return _near(room_id, grid, aid, anchor, tuple(rec["cells"][0]), grid.cells)


def _reach(room_id, grid, aid, anchor, rec) -> int:
    """How much of its wall a fixture takes -- the length `_wall_slot` lays
    it at -- or, for a corner or a fixture with no wall, its cells."""
    if rec.get("dir") in _STRAIGHT:
        return _wall_slot(grid, rec["dir"], anchor, rec["footprint"],
                          _seed(room_id, aid))[1]
    return len(rec["cells"])


def pack_anchors(scene: dict, room_id, movable, *, overfull=None) -> dict:
    """Where each of `movable` -- the fixtures of `room_id` a design has
    drafted and no plan has shown yet, in the order they were drafted --
    stands, so that no two things of the room share a cell at one height
    (the rules: module docstring). Every other fixture of the room is an
    obstacle.

    Returns `{"pins": {anchor_id: {"offset": f} | {"cell": [x, y]}}, "kept":
    [anchor_id], "stuck": [anchor_id], "full": [line]}`: the place written
    for each fixture that had to move, the ones that kept their seeded place,
    the ones no place on their own wall (or corner, or floor) holds at their
    height -- left where their seed put them -- and ONE line for each wall
    and height that cannot hold its fixtures, with the arithmetic and where
    each stuck fixture would fit. `scene` is the draft merged into the
    world; nothing in it is changed. `overfull`, when given, is the
    `(wall, height)` pairs whose count-overfull wall gets a line even with
    nothing stuck on it (the check passes the rows the draft brought); None
    describes every one."""
    grid = room_grid(scene, room_id)
    anchors = effective_anchors(scene, room_id)
    placed = anchor_cells(scene, room_id)
    drafted = [aid for aid in dict.fromkeys(movable or ())
               if aid in placed and not _doorway(aid) and not placed[aid]["implicit"]
               and isinstance(anchors.get(aid), dict)
               and placed[aid].get("source") not in ("cell", "offset")]
    rank = {aid: i for i, aid in enumerate(drafted)}
    order = sorted(drafted, key=lambda aid: (
        -_reach(room_id, grid, aid, anchors[aid], placed[aid]), rank[aid]))
    mine = set(order)
    held = {}

    def take(aid, cells, height):
        for cell in cells:
            held.setdefault((tuple(cell), height), aid)

    def free(cells, height):
        return all((tuple(cell), height) not in held for cell in cells)

    for aid, rec in placed.items():
        if _doorway(aid) or rec["implicit"] or aid in mine:
            continue
        take(aid, rec["cells"], rec["height"])
    kept, later = [], []
    for aid in order:
        rec = placed[aid]
        if free(rec["cells"], rec["height"]):
            take(aid, rec["cells"], rec["height"])
            kept.append(aid)
        else:
            later.append(aid)
    pins, stuck = {}, []
    for aid in later:
        rec = placed[aid]
        spot = next(((pin, cells) for pin, cells
                     in _places(room_id, grid, aid, anchors[aid], rec)
                     if cells and free(cells, rec["height"])), None)
        if spot is None:
            stuck.append(aid)
            take(aid, rec["cells"], rec["height"])
            continue
        pins[aid], cells = spot
        take(aid, cells, rec["height"])
    for aid in list(stuck):
        rec = placed[aid]
        wall, height = rec.get("dir"), rec["height"]
        if aid not in stuck or wall not in _STRAIGHT:
            continue
        group = [x for x in order if placed[x].get("dir") == wall
                 and placed[x]["height"] == height]
        laid = _end_to_end(room_id, grid, anchors, placed, group, wall, height,
                           held)
        if laid is None:
            continue
        for x, (pin, cells) in laid.items():
            if [tuple(c) for c in placed[x]["cells"]] == cells:
                pins.pop(x, None)          # back on its own seed: nothing to write
                if x not in kept:
                    kept.append(x)
            else:
                pins[x] = pin
                if x in kept:
                    kept.remove(x)
            if x in stuck:
                stuck.remove(x)
    return {"pins": pins, "kept": kept, "stuck": stuck,
            "full": _full_lines(scene, room_id, grid, anchors, placed, stuck, free,
                                overfull)}


def doorway_places(scene: dict, movable) -> dict:
    """`{(room, to): offset}`: a place along its wall for each doorway in
    `movable` -- `(room, to)`, the edges a design writes on `room`'s side
    with no place of the model's, in the order they were drafted -- that
    stands on the same cells as another doorway of that wall, on either side
    of it. The doorway keeps its wall; only where along it changes, to the
    free place nearest where it stood, and the far room's side is checked
    too when it reads its place from this edge (`effective_anchors`: a
    doorway is one object, and an edge declared from one side places it on
    both). A doorway that is a whole open side takes no place and is no
    obstacle -- it holds any other opening on its wall (the layout check's
    rule). Doorways nobody may move are obstacles: the world's, the ones
    with a place already, and any `movable` one that stands free."""
    rooms = (scene or {}).get("rooms") or {}
    narrow = {}                  # (room, wall) -> {cell}
    doors = {}                   # (room, anchor id) -> placed record

    def declares(room_id, to):
        room = rooms.get(room_id)
        return isinstance(room, dict) and any(
            isinstance(edge, dict) and str(edge.get("to")) == str(to)
            for edge in room.get("adjacent") or ())

    moving = set()
    for room_id, to in movable or ():
        moving.add((room_id, "door:" + str(to)))
        if not declares(to, room_id):
            moving.add((to, "door:" + str(room_id)))
    for room_id in {r for pair in (movable or ()) for r in pair if r in rooms}:
        for aid, rec in anchor_cells(scene, room_id).items():
            if not rec.get("implicit") or rec.get("dir") not in _STRAIGHT:
                continue
            doors[(room_id, aid)] = rec
            if rec.get("source") == "side" or (room_id, aid) in moving:
                continue
            narrow.setdefault((room_id, rec["dir"]), set()).update(
                tuple(c) for c in rec["cells"])
    out = {}
    for room_id, to in movable or ():
        near = doors.get((room_id, "door:" + str(to)))
        if near is None or near.get("source") == "side":
            continue
        if near.get("source") in ("cell", "offset"):
            narrow.setdefault((room_id, near["dir"]), set()).update(
                tuple(c) for c in near["cells"])
            continue
        sides = [(room_id, "door:" + str(to), near)]
        if not declares(to, room_id) and (to, "door:" + str(room_id)) in doors:
            sides.append((to, "door:" + str(room_id), doors[(to, "door:" + str(room_id))]))

        def clear(cells_by_side):
            return all(not (set(cells) & narrow.get((rid, rec["dir"]), set()))
                       for (rid, _aid, rec), cells in zip(sides, cells_by_side))

        current = [[tuple(c) for c in rec["cells"]] for _rid, _aid, rec in sides]
        if not clear(current):
            grid = room_grid(scene, room_id)
            anchor = effective_anchors(scene, room_id).get("door:" + str(to)) or {}
            probe = {k: v for k, v in anchor.items() if k not in ("offset", "cell")}
            along, length, seeded, _source = _wall_slot(
                grid, near["dir"], probe, near["footprint"],
                _seed(room_id, "door:" + str(to)))
            room_for = max(0, along - length)
            current = None
            for offset in sorted(range(room_for + 1), key=lambda o: (abs(o - seeded), o)):
                frac = _fraction(offset, room_for)
                trial = []
                for rid, aid, rec in sides:
                    held = effective_anchors(scene, rid).get(aid) or {}
                    held = {k: v for k, v in held.items() if k not in ("offset", "cell")}
                    held["offset"] = frac
                    trial.append([tuple(c) for c in _place_anchors(
                        rid, room_grid(scene, rid), {aid: held})[aid]["cells"]])
                if all(trial) and clear(trial):
                    out[(room_id, str(to))] = frac
                    current = trial
                    break
            if current is None:
                continue
        for (rid, _aid, rec), cells in zip(sides, current):
            narrow.setdefault((rid, rec["dir"]), set()).update(cells)
    return out


def _end_to_end(room_id, grid, anchors, placed, group, wall, height, held):
    """`{anchor: (pin, cells)}` laying `group` -- fixtures of one wall and
    height, in drafting order -- end to end around everything else the wall
    holds, from whichever end of the wall moves them least from their seeds
    (the nearest place, as everywhere here); None when neither end holds
    them all. On success `held` is updated in place."""
    best = None
    for reverse in (False, True):
        trial = {key: owner for key, owner in held.items() if owner not in group}
        laid, moved = {}, 0
        for aid in group:
            probe = {k: v for k, v in anchors[aid].items() if k not in ("offset", "cell")}
            probe["dir"] = wall
            along, length, seeded, _source = _wall_slot(
                grid, wall, probe, placed[aid]["footprint"], _seed(room_id, aid))
            room_for = max(0, along - length)
            spots = range(room_for, -1, -1) if reverse else range(room_for + 1)
            for offset in spots:
                frac = _fraction(offset, room_for)
                cells = _trial(room_id, grid, aid, probe, offset=frac)
                if cells and all((cell, height) not in trial for cell in cells):
                    laid[aid] = ({"offset": frac}, cells)
                    moved += abs(offset - seeded)
                    for cell in cells:
                        trial[(cell, height)] = aid
                    break
            else:
                break
        if len(laid) == len(group) and (best is None or moved < best[0]):
            best = (moved, laid, trial)
    if best is None:
        return None
    held.clear()
    held.update(best[2])
    return best[1]


def _would_fit(room_id, grid, aid, anchor, rec, free) -> str:
    """Where else a stuck fixture would stand at its height: the other
    straight walls that hold it, or -- for a corner or a fixture with no
    wall -- the nearest free cell."""
    height = rec["height"]
    bearing = rec.get("dir")
    if bearing in _STRAIGHT:
        walls = [_WALL_WORDS[wall] for wall in _STRAIGHT if wall != bearing
                 and any(cells and free(cells, height) for _pin, cells
                         in _along_wall(room_id, grid, aid, anchor, wall,
                                        rec["footprint"]))]
        if not walls:
            return ""
        named = walls[0] if len(walls) == 1 else \
            ", ".join(walls[:-1]) + " or " + walls[-1]
        return f"on the {named} wall"
    origin = grid.corner(bearing) if bearing in ROOM_CORNERS else tuple(rec["cells"][0])
    for pin, cells in _near(room_id, grid, aid, anchor, origin, grid.cells):
        if cells and free(cells, height):
            return "at cell [%d, %d]" % tuple(pin["cell"])
    return ""


def _full_lines(scene, room_id, grid, anchors, placed, stuck, free,
                overfull=None) -> list:
    """ONE line per wall and height that cannot hold its fixtures: the
    wall's length and which side of the extent that is, what each fixture
    against it at that height takes, which found no place, and where each of
    those would fit -- "needs 7, has 5" alone had a designer widen the wrong
    side twice (the 2026-09-27 yard: its west wall runs north-south, so it
    is the extent's `d`). A wall the count calls overfull gets its line even
    when every fixture found a cell, so the arithmetic is never missing."""
    loads = wall_loads(scene, room_id)
    groups = {}
    wanted = None if overfull is None else {tuple(key) for key in overfull}
    for (wall, height), paces in loads.items():
        if sum(paces.values()) > len(grid.rim(wall)) \
                and (wanted is None or (wall, height) in wanted):
            groups.setdefault((wall, height), [])
    for aid in stuck:
        rec = placed[aid]
        groups.setdefault((rec.get("dir") or "", rec["height"]), []).append(aid)
    lines = []
    for (wall, height), names in sorted(groups.items()):
        listed = " and ".join(names)
        if wall in _STRAIGHT:
            holds = len(grid.rim(wall))
            paces = loads.get((wall, height)) or {}
            side = ("the extent's w, east-west" if wall in ("n", "s")
                    else "the extent's d, north-south")
            taken = ", ".join(f"{aid} {n}" for aid, n in paces.items())
            line = (f"{room_id}: the {_WALL_WORDS[wall]} wall is {holds} paces "
                    f"long ({side}), and at {height} height its fixtures take "
                    f"{sum(paces.values())} ({taken})")
            if names:
                line += f"; no place along it holds {listed} at that height"
        elif wall in ROOM_CORNERS:
            line = (f"{room_id}: at {height} height no place in the "
                    f"{_WALL_WORDS[wall]} corner, or along the two walls that "
                    f"meet there, holds {listed}")
        else:
            line = f"{room_id}: at {height} height no free cell holds {listed}"
        fits = []
        for aid in names:
            where = _would_fit(room_id, grid, aid, anchors[aid], placed[aid], free)
            fits.append(f"{aid} would fit {where}" if where
                        else f"no other wall and no free cell of the room holds "
                             f"{aid} at {height} height")
        if fits:
            line += ". " + "; ".join(fits)
        lines.append(line + ". Which wall each fixture stands against, its size, "
                     "and whether it stays are yours to choose.")
    return lines


__all__ = ["doorway_places", "pack_anchors"]
