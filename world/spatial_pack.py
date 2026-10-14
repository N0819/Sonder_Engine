# spatial_pack.py
"""Where code stands each NEW fixture of a room being designed: along the
wall the model chose, so that no two things standing on the floor share a
cell, and nothing shares one with another at its height.

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

WHAT COUNTS AS TAKEN: a cell held at the fixture's height, or -- for a
fixture standing on the floor -- by anything else standing there at any
height (the owner, 2026-10-13; `spatial_fov.stands_on_floor`: only what is
hung, from the ceiling, on or in another fixture is off the floor), doorways
excluded (an object in front of a door is a placement the world allows; the
owner's ruling of 2026-09-16). That is the read-time placement's own rule
and the room designer's check's (`director_rooms._check`), so "free" here
is "clean" there; and where no free place is left, the check says so --
two standing things on one cell are an overlap it names, and the wall gets
its line (`_full_lines`). But a place the packer CHOOSES keeps clear of every doorway's
step and the pace inside it where its wall allows (the owner, reading Home 9
on 2026-10-12: furniture placed in front of doors is an oddity;
`spatial_fov.doorway_clearance`): a fixture whose seed stands in a way in or
out moves to the nearest place on its wall clear of it, and stands where its
seed put it when none is -- a doorway never makes a wall crowded; the map
then gives up a shared cell before the doorway, and the designer's check
names the pair that makes. The packer reads every fixture by its seed
(`anchor_cells(raw=True)`), since a fixture code placed gives way to a place
written; its lines count where the map stands each thing, and a fixture it
finds no place for is stuck only when the map, its pins written, cannot
stand it clear without moving another (the reviews of 2026-10-13: read
where the map stood them, world fixtures barred places they would have
left, 30 of 4,080 drafts on the play db's rooms).

Pure, total, no I/O, no model.
"""

from __future__ import annotations

from world.spatial_fov import (
    ROOM_CORNERS, STANDING, _place_anchors, _seed, _wall_slot, anchor_cells,
    doorway_clearance, room_grid, stands_on_floor, whole_cells,
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
    return [tuple(c) for c in _place_anchors(room_id, grid, {aid: trial},
                                             clear=False)[aid]["cells"]]


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


def pack_anchors(scene: dict, room_id, movable, *, overfull=None, pin_kept=False) -> dict:
    """Where each of `movable` -- the fixtures of `room_id` a design has
    drafted and no plan has shown yet, in the order they were drafted --
    stands, so that no two things of the room share a cell at one height
    (the rules: module docstring). Every other fixture of the room is an
    obstacle.

    Returns `{"pins": {anchor_id: {"offset": f} | {"cell": [x, y]}}, "kept":
    [anchor_id], "in_way": [anchor_id], "stuck": [anchor_id], "full":
    [line]}`: the place written for each fixture that had to move, the ones
    that kept their seeded place (`in_way`: those of them standing in a
    doorway's way, no place clear of it and of what stands there being free),
    the ones no place on their own wall (or corner, or floor) holds at their
    height -- left where their seed put them -- and ONE line for each wall
    and height that cannot hold its fixtures, with the arithmetic and where
    each stuck fixture would fit. `scene` is the draft merged into the
    world; nothing in it is changed. `overfull`, when given, is the
    `(wall, height)` pairs whose count-overfull wall gets a line even with
    nothing stuck on it (the check passes the rows the draft brought); None
    describes every one. `pin_kept` also writes the place of each fixture
    that kept its seeded one, along a straight wall or on the floor, so that
    a caller with no designer after it (the opening, `structure.
    hold_planned_fixtures`) leaves no place for the seed to choose again."""
    grid = room_grid(scene, room_id)
    anchors = effective_anchors(scene, room_id)
    placed = anchor_cells(scene, room_id, raw=True)
    doors = doorway_clearance(grid, anchors, placed)
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
            if stands_on_floor(anchors.get(aid)):
                held.setdefault((tuple(cell), STANDING), aid)

    def free(cells, height, aid=None):
        standing = aid is not None and stands_on_floor(anchors.get(aid))
        return all((tuple(cell), height) not in held
                   and not (standing and (tuple(cell), STANDING) in held)
                   for cell in cells)

    def clear(cells):
        return not any(tuple(cell) in doors for cell in cells)

    def nearest(aid, rec, *, keep_clear):
        # the nearest free place that holds the fixture whole, else the
        # nearest the room's edge clips (`spatial_fov.whole_cells`): a
        # clipped place has fewer cells, so it is free more often, and is
        # the fixture drawn smaller than it is
        whole = whole_cells(anchors[aid], rec["footprint"])
        clipped = None
        for pin, cells in _places(room_id, grid, aid, anchors[aid], rec):
            if cells and free(cells, rec["height"], aid) and (not keep_clear or clear(cells)):
                if len(set(cells)) >= whole:
                    return pin, cells
                if clipped is None:
                    clipped = (pin, cells)
        return clipped

    for aid, rec in placed.items():
        if _doorway(aid) or rec["implicit"] or aid in mine:
            continue
        take(aid, rec["cells"], rec["height"])
    pins, kept, later = {}, [], []
    for aid in order:
        rec = placed[aid]
        if free(rec["cells"], rec["height"], aid):
            # free, but standing in a way in or out: the nearest place on
            # what the model chose that is clear of both, where one is; a
            # doorway is never crowding (the check's rule), so where none
            # is it stands where its seed put it
            spot = None if clear(rec["cells"]) else nearest(aid, rec, keep_clear=True)
            if spot is None:
                take(aid, rec["cells"], rec["height"])
                kept.append(aid)
            else:
                pins[aid], cells = spot
                take(aid, cells, rec["height"])
        else:
            later.append(aid)
    stuck = []
    for aid in later:
        rec = placed[aid]
        spot = nearest(aid, rec, keep_clear=True) or nearest(aid, rec, keep_clear=False)
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
        # one wall's fixtures that would share a cell: of its height, or --
        # standing on the floor -- every other one standing there
        group = [x for x in order if placed[x].get("dir") == wall
                 and (placed[x]["height"] == height
                      or (stands_on_floor(anchors.get(aid))
                          and stands_on_floor(anchors.get(x))))]
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
    if pin_kept:
        for aid in kept:
            rec = placed[aid]
            if aid in pins or rec.get("dir") in ROOM_CORNERS:
                continue
            first = next(iter(_places(room_id, grid, aid, anchors[aid], rec)), None)
            if first is not None and [tuple(c) for c in first[1]] == \
                    [tuple(c) for c in rec["cells"]]:
                pins[aid] = first[0]
    # STUCK IS THE MAP'S WORD: a fixture no place of the packer's reading
    # holds may yet stand clear where read-time placement stands it, with
    # these pins written, and moving nothing else -- a world fixture's seed
    # the map never drew is no obstacle -- and one that does is not stuck
    # (the fourth and fifth reviews of 2026-10-13: chat 173's shrine hall
    # was refused for a chest the map stood clear). One that stands clear
    # only by moving another stays stuck: a fixture a plan has shown is
    # never moved for a later one.
    if stuck:
        pinned = _with_pins(scene, room_id, pins)
        drawn_after = anchor_cells(pinned, room_id) or {}
        for aid in list(stuck):
            if aid not in drawn_after or not _clear_on_the_map(aid, drawn_after, anchors):
                continue
            alone = anchor_cells(_without(pinned, room_id, {aid}), room_id) or {}
            if all([tuple(c) for c in drawn_after[x]["cells"]] == [tuple(c) for c in rec["cells"]]
                   for x, rec in alone.items() if x in drawn_after):
                stuck.remove(aid)
                kept.append(aid)
    # the lines count every thing where the map stands it, this call's own
    # included: a line counting a new one by its seed read "takes 3" of a
    # three-pace wall the map had five on (fourth review of 2026-10-13)
    drawn = {aid: rec["cells"] for aid, rec in (anchor_cells(scene, room_id) or {}).items()}
    return {"pins": pins, "kept": kept, "stuck": stuck,
            "full": _full_lines(scene, room_id, grid, anchors, placed, stuck, free,
                                overfull, drawn=drawn)}


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
            if not rec.get("implicit") or not _doorway(aid) \
                    or rec.get("dir") not in _STRAIGHT:
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
    """`{anchor: (pin, cells)}` laying `group` -- fixtures of one wall that
    would share a cell, in drafting order: of one height, or all standing on
    the floor -- end to end around everything else the wall holds, from
    whichever end of the wall moves them least from their seeds (the nearest
    place, as everywhere here); None when neither end holds them all. Each is
    checked and recorded at its OWN height (a stuck fixture's height laid a
    waist-high table over a waist-high chest hung there, review of
    2026-10-13). On success `held` is updated in place."""
    best = None
    for reverse in (False, True):
        trial = {key: owner for key, owner in held.items() if owner not in group}
        laid, moved = {}, 0
        for aid in group:
            own = placed[aid]["height"]
            probe = {k: v for k, v in anchors[aid].items() if k not in ("offset", "cell")}
            probe["dir"] = wall
            along, length, seeded, _source = _wall_slot(
                grid, wall, probe, placed[aid]["footprint"], _seed(room_id, aid))
            room_for = max(0, along - length)
            spots = range(room_for, -1, -1) if reverse else range(room_for + 1)
            for offset in spots:
                frac = _fraction(offset, room_for)
                cells = _trial(room_id, grid, aid, probe, offset=frac)
                standing = stands_on_floor(anchors.get(aid))
                if cells and all((cell, own) not in trial
                                 and not (standing and (cell, STANDING) in trial)
                                 for cell in cells):
                    laid[aid] = ({"offset": frac}, cells)
                    moved += abs(offset - seeded)
                    for cell in cells:
                        trial[(cell, own)] = aid
                        if standing:
                            trial[(cell, STANDING)] = aid
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
                 and any(cells and free(cells, height, aid) for _pin, cells
                         in _along_wall(room_id, grid, aid, anchor, wall,
                                        rec["footprint"]))]
        if not walls:
            return ""
        named = walls[0] if len(walls) == 1 else \
            ", ".join(walls[:-1]) + " or " + walls[-1]
        return f"on the {named} wall"
    origin = grid.corner(bearing) if bearing in ROOM_CORNERS else tuple(rec["cells"][0])
    for pin, cells in _near(room_id, grid, aid, anchor, origin, grid.cells):
        if cells and free(cells, height, aid):
            return "at cell [%d, %d]" % tuple(pin["cell"])
    return ""


def _without(scene: dict, room_id, ids) -> dict:
    """`scene` with the anchors `ids` taken out of `room_id`, nothing else
    copied."""
    rooms = dict((scene or {}).get("rooms") or {})
    room = dict(rooms.get(room_id) or {})
    room["anchors"] = {aid: a for aid, a in (room.get("anchors") or {}).items()
                       if aid not in ids}
    rooms[room_id] = room
    return {**scene, "rooms": rooms}


def _with_pins(scene: dict, room_id, pins) -> dict:
    """`scene` with each of `pins` written onto its anchor in `room_id`,
    nothing else copied: the room as the map will stand it once they are."""
    if not pins:
        return scene
    rooms = dict((scene or {}).get("rooms") or {})
    room = dict(rooms.get(room_id) or {})
    room["anchors"] = {aid: (dict(a, **pins[aid]) if aid in pins and isinstance(a, dict) else a)
                       for aid, a in (room.get("anchors") or {}).items()}
    rooms[room_id] = room
    return {**scene, "rooms": rooms}


def _clear_on_the_map(aid, drawn, anchors) -> bool:
    """Does `aid` stand where the map (`drawn`, `anchor_cells`) stands it
    sharing no cell with anything at its height, nor -- standing on the
    floor -- with anything else standing there? A doorway is never one."""
    mine = {tuple(c) for c in drawn[aid]["cells"]}
    height, standing = drawn[aid]["height"], stands_on_floor(anchors.get(aid))
    for other, rec in drawn.items():
        if other == aid or _doorway(other) or not mine & {tuple(c) for c in rec["cells"]}:
            continue
        if rec["height"] == height:
            return False
        if standing and not rec["implicit"] and not str(other).startswith("window:") \
                and stands_on_floor(anchors.get(other)):
            return False
    return True


def _full_lines(scene, room_id, grid, anchors, placed, stuck, free,
                overfull=None, drawn=None) -> list:
    """ONE line per wall and height that cannot hold its fixtures: the
    wall's length and which side of the extent that is, what each fixture
    against it at that height takes, which found no place, and where each of
    those would fit -- "needs 7, has 5" alone had a designer widen the wrong
    side twice (the 2026-09-27 yard: its west wall runs north-south, so it
    is the extent's `d`). A wall the count calls overfull gets its line even
    when every fixture found a cell, so the arithmetic is never missing. A
    stuck fixture standing on the floor is counted with everything standing
    on its wall, at every height (2026-10-13): counted at its own height
    alone, the line read "2 of 4 paces taken" beside "no place holds it"."""
    loads = wall_loads(scene, room_id)
    groups = {}
    wanted = None if overfull is None else {tuple(key) for key in overfull}
    for (wall, height), paces in loads.items():
        if sum(paces.values()) > len(grid.rim(wall)) \
                and (wanted is None or (wall, height) in wanted):
            groups.setdefault((wall, height), [])
    def standing_paces(names, wall=None):
        """What blocks `names` on the cells the wall offers them (`_places`)
        -- every thing standing on the floor there, and anything else at a
        height of theirs, whatever wall it names or none -- and how many of
        those cells each holds; with no names, what stands on `wall`'s own
        rim (second review of 2026-10-13: counted by `dir`, a thing flush
        with two walls or with no wall at all was missing from the
        arithmetic, and a shelf hung at the stuck thing's height went
        unnamed)."""
        line, heights = set(), {placed[aid]["height"] for aid in names}
        for aid in names:
            for _pin, cells in _places(room_id, grid, aid, anchors[aid], placed[aid]):
                line.update(tuple(c) for c in cells)
        if not names and wall in _STRAIGHT:
            line = {tuple(c) for c in grid.rim(wall)}
        # paces ALONG the wall, never the cells of a two-deep band (third
        # review of 2026-10-13); each thing where the map stands it
        along = 0 if wall in ("n", "s") else 1
        out = {}
        for x, rec in placed.items():
            if rec["implicit"] or not (stands_on_floor(anchors.get(x))
                                       or rec["height"] in heights):
                continue
            cells = (drawn or {}).get(x, rec["cells"])
            n = len({c[along] for c in map(tuple, cells) if c in line})
            if n:
                out[x] = n
        return out

    for aid in stuck:
        rec = placed[aid]
        wall, key = rec.get("dir") or "", rec["height"]
        blockers = standing_paces([aid], wall) if wall in _STRAIGHT else {}
        if stands_on_floor(anchors.get(aid)) and (
                len({placed[x]["height"] for x in blockers}) > 1
                or any(placed[x].get("dir") != wall for x in blockers)):
            # what stands where it would go is of more than one height, or
            # names another wall or none: it is counted together, by what
            # blocks it (third review of 2026-10-13), and the line for any
            # one height of it is that count's
            key = STANDING
        groups.setdefault((wall, key), []).append(aid)
    for key in wanted or ():
        if key[1] == STANDING:
            groups.setdefault(tuple(key), [])
    for wall in [w for w, k in list(groups) if k == STANDING]:
        for other in [g for g in list(groups) if g[0] == wall and g[1] != STANDING
                      and not groups[g]]:
            if all(stands_on_floor(anchors.get(x)) for x in (loads.get(other) or {})):
                groups.pop(other)

    lines = []
    for (wall, height), names in sorted(groups.items()):
        listed = " and ".join(names)
        where_held = ("standing on the floor" if height == STANDING
                      else f"at {height} height")
        if wall in _STRAIGHT:
            holds = len(grid.rim(wall))
            paces = (standing_paces(names, wall) if height == STANDING
                     else loads.get((wall, height)) or {})
            side = ("the extent's w, east-west" if wall in ("n", "s")
                    else "the extent's d, north-south")
            taken = ", ".join(f"{aid} {n}" for aid, n in paces.items())
            line = (f"{room_id}: the {_WALL_WORDS[wall]} wall is {holds} paces "
                    f"long ({side}), and {where_held} its fixtures take "
                    f"{sum(paces.values())} ({taken})")
            if names:
                line += (f"; no place along it holds {listed} clear of them"
                         if height == STANDING
                         else f"; no place along it holds {listed} at that height")
        elif wall in ROOM_CORNERS:
            line = (f"{room_id}: {where_held}, no place in the "
                    f"{_WALL_WORDS[wall]} corner, or along the two walls that "
                    f"meet there, holds {listed}")
        else:
            line = f"{room_id}: {where_held}, no free cell holds {listed}"
        fits = []
        for aid in names:
            fit = _would_fit(room_id, grid, aid, anchors[aid], placed[aid], free)
            fits.append(f"{aid} would fit {fit}" if fit
                        else f"no other wall and no free cell of the room holds "
                             f"{aid} " + ("clear of what stands there"
                                          if height == STANDING else f"at {height} height"))
        if fits:
            line += ". " + "; ".join(fits)
        lines.append(line + ". Which wall each fixture stands against, its size, "
                     "and whether it stays are yours to choose.")
    return lines


__all__ = ["doorway_places", "pack_anchors"]
