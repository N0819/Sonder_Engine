"""Where the rooms the charter closure invents stand along their street.

THE CLOSURE ALREADY INVENTS ROOMS, AND IT LEFT THEM NOWHERE TO STAND.
`charter_generate._spread_berths` splits a dwelling berthing more than
`BERTH_CEILING` sleepers into SIBLINGS -- same purpose, same neighbours --
and hangs a workplace's overflow off it as ANNEXES. A sibling is a copy of
its parent's doorways, so whichever wall a hand later gives the parent's
street, every sibling is laid on the same stretch of it. Chat 165's opening
put the Back Row and its four siblings on the cross walk's north wall, the
doorway spread (`spatial_orientation._spread_along_wall`) gave the five of
them five fractions of one six-pace wall, and the planar layout laid them on
one another: 8 of that town's 19 standing plane-embedding rows. One clash
then refused a whole connected group its site plan
(`site_plan.derive_site_plans`, room by room since 2026-10-09, where such a
sibling stands off the plan and is named), and none of the play database's
957 rooms carried one.

CODE FINISHES WHAT CODE STARTED, AND DECIDES ONLY WHERE. A split room stands
along the wall of the street its parent fronts, at the free stretch nearest
the parent; an annex takes a wall of its workplace that no other doorway
uses. What is written is a doorway's `offset` along its wall, and a bearing
only where nothing but the plan's own copy ever set one. Never a way between
rooms (the owner's site-plan rule), never a measurement a hand wrote, never
what a place is for.

WHAT A HAND DECLARED STAYS DECLARED. A bearing in the scene that is not the
plan's own value was written by a hand -- the opening's establish wrote every
bearing chat 165's town has -- and `spatial_orientation.derived_edge_bearings`
already states the rule kept here: a bearing anybody declared is never moved.
So a split room moves only ALONG its wall unless its bearing is still the
plan's copy, and only a room that is still the plan's prose-free stub has a
doorway written here (`structure.materialize_planned_fringe`: while a room is
the plan's stub, the plan owns its measurements) -- a street a story has
entered keeps its doors, and a split room beside it moves by its own.

WHAT DOES NOT FIT IS LEFT WHERE IT WAS AND REPORTED. A street too short for
what is split along it is short by a measurement. One nobody measured is
measured longer to hold them, on the owner's ruling
(`FRONTAGE_MEASURES_STREETS`); one the Room measured keeps its length.

AND THE PLANE IS THE JUDGE, NOT ONE WALL. A run free along the street's wall
can still be where a room laid through another doorway stands -- the side
room off the parent's flank -- so a place is taken only where the room lands
on no room at all, by both rules a plane is drawn by (the layout lint's and
the site plan's, `_Plane`); a room that stands on one is never pinned where
it is, and one a move put on one -- a sibling the pass left where it stood
included -- is put back and reported (`_take_back`). Measuring a street
longer moves every room laid through its other walls, so a measurement is
made only where every room it lays then stands clear and no other room
stands on one it did not, and is taken back whole, length and doorways,
when any room it laid is put back.

Design: `docs/design/DESIGN_CHARTER_PLACES.md`.
"""

from __future__ import annotations

import copy

from world.spatial import (
    EXTENT_MAX_PACES, ROOM_SIZES, _door_cells, effective_adjacent, layout_rooms,
    normalize_barrier, normalize_bearing, normalize_extent, normalize_offset,
    normalize_shape, normalize_vertical, opposite_bearing, room_grid)


#: The marks the closure leaves on a room it invented, naming the room it was
#: split from. A SIBLING (`split_of`) is more of a dwelling -- same purpose,
#: same neighbours; an ANNEX (`annex_of`) is a purpose-less room hung off a
#: workplace for the sleepers it could not hold. Written once, at the
#: closure, onto the planned spec; read here, by the room's own uid, because
#: the plan is where a room's provenance lives.
SPLIT_OF = "split_of"
ANNEX_OF = "annex_of"
SPLIT_MARKS = (SPLIT_OF, ANNEX_OF)

#: WHETHER A STREET NOBODY MEASURED IS MEASURED LONGER SO IT HOLDS WHAT IS
#: SPLIT ALONG IT. ON, by the owner's ruling of 2026-10-08 ("unmeasured stubs
#: only"): the six-pace square an unmeasured room is drawn as is the engine's
#: default, not anybody's fact about the street, so a street with no `extent`
#: and no `size` tier in the scene and none in its plan (a size a hand wrote is
#: a measurement too), still the plan's prose-free stub, is
#: given one -- the wall its split rooms stand on, lengthened to hold every
#: room standing on it side by side, at most `EXTENT_MAX_PACES` -- and only
#: where every room it lays then stands on no room (`_measure_street`). A
#: street the Room measured is never lengthened: its length is the Room's
#: choice, and the fringe re-applies the plan's measurement to a stub every
#: beat, so the two would fight. Measured on chat 165's town
#: (`docs/design/DESIGN_CHARTER_PLACES.md` § 4): the cross walk is measured
#: to 30 paces and holds all four of the Back Row's siblings, and the 8
#: sibling plane rows are 0; off, its six unmeasured paces hold the Back Row
#: alone and all 8 stand.
FRONTAGE_MEASURES_STREETS = True

_WALLS = ("n", "e", "s", "w")


def split_marks(raw) -> dict:
    """The split marks a planned room carries, ``{mark: parent uid}``, and
    ``{}`` for a room the plan drew itself."""
    raw = raw if isinstance(raw, dict) else {}
    return {key: str(raw[key]).strip() for key in SPLIT_MARKS
            if str(raw.get(key) or "").strip()}


def splits_from_specs(specs) -> dict:
    """``{parent: {"mode": "siblings"|"annexes", "rooms": [uid, ...]}}`` read
    off planned specs ``{uid: spec}``, each list in id order."""
    out = {}
    for uid in sorted(specs or {}, key=str):
        spec = specs[uid] if isinstance(specs[uid], dict) else {}
        for mark, mode in ((SPLIT_OF, "siblings"), (ANNEX_OF, "annexes")):
            parent = str(spec.get(mark) or "").strip()
            if not parent or parent == str(uid):
                continue
            record = out.setdefault(parent, {"mode": mode, "rooms": []})
            if record["mode"] == mode:
                record["rooms"].append(str(uid))
    return out


# ---------------------------------------------------------------------------
# Reading the scene the way the planar layout reads it
# ---------------------------------------------------------------------------

def _rooms(scene) -> dict:
    rooms = (scene or {}).get("rooms")
    return rooms if isinstance(rooms, dict) else {}


def _stub(rooms, rid) -> bool:
    """Is this room still the plan's prose-free stub -- the one test
    `structure.materialize_planned_fringe` applies before it lets the plan
    write a room's measurements?"""
    room = rooms.get(rid)
    return (isinstance(room, dict) and bool(room.get("planned"))
            and not str(room.get("desc") or room.get("description")
                        or "").strip())


def _rectangular(scene, rid) -> bool:
    """A frontage is a run of cells along a straight wall, which only a
    rectangle has from end to end; a round room's arc and an L's notch are
    left to whoever drew them."""
    room = _rooms(scene).get(rid)
    return (isinstance(room, dict)
            and normalize_shape(room.get("shape")) == "rectangle")


def _own_edge(rooms, room, other):
    for edge in (rooms.get(room) or {}).get("adjacent") or ():
        if isinstance(edge, dict) and str(edge.get("to") or "") == str(other):
            return edge
    return None


def _axis(wall) -> int:
    """The coordinate a wall runs along: x for a north or south wall."""
    return 0 if wall in ("n", "s") else 1


def _run(scene, rid, wall) -> int:
    """How many cells of a wall's run this room takes, standing on it."""
    grid = room_grid(scene, rid)
    return grid.w if _axis(wall) == 0 else grid.d


def _laid_flat(scene, room, other) -> bool:
    """Is `other` laid on `room`'s floor by their doorway? The planar
    layout's own rule (`spatial_lint._beared_neighbours`): not through a
    wall, and not up or down a storey."""
    for edge in effective_adjacent(scene, room):
        if isinstance(edge, dict) and str(edge.get("to") or "") == str(other):
            return (normalize_barrier(edge.get("barrier")) != "wall"
                    and not normalize_vertical(edge.get("vertical")))
    return False


def _door(scene, room, other):
    """``(cells, wall)`` of `room`'s doorway onto `other` on a straight
    wall, or None: no bearing to place it by, or a corner."""
    cells, bearing = _door_cells(scene, room, other)
    if not cells or bearing not in _WALLS:
        return None
    return cells, bearing


def _whole_side(scene, room, other) -> bool:
    """An open side spans its whole wall (`spatial_geometry`'s `width:
    "wall"`), so no offset moves it; it is laid at the wall's start."""
    door = _door(scene, room, other)
    if door is None:
        return False
    rim = room_grid(scene, room).rim(door[1])
    return len(rim) > 1 and len(door[0]) >= len(rim)


def _span(scene, street, other):
    """``(wall, start, end)``: the run of `street`'s wall `other` covers when
    the layout lays it through their doorway -- the two doorways' first
    cells aligned across the wall, which is the rule both
    `spatial_lint.layout_rooms` and `site_plan.derive_site_plans` lay a room
    by. None when either doorway has no cell to lay it by."""
    if not _laid_flat(scene, street, other):
        return None
    mine = _door(scene, street, other)
    if mine is None:
        return None
    theirs, _bearing = _door_cells(scene, other, street)
    if not theirs:
        return None
    wall, axis = mine[1], _axis(mine[1])
    start = mine[0][0][axis] - theirs[0][axis]
    return wall, start, start + _run(scene, other, wall)


def _wall_spans(scene, street, wall, skip=()) -> list:
    """``[(start, end, room)]`` for every room laid flat through `street`'s
    `wall`, but those in `skip`, in order along the wall."""
    out, seen = [], set()
    rooms = _rooms(scene)
    for edge in effective_adjacent(scene, street):
        other = str(edge.get("to") or "") if isinstance(edge, dict) else ""
        if not other or other in seen or other in skip or other not in rooms:
            continue
        seen.add(other)
        span = _span(scene, street, other)
        if span and span[0] == wall:
            out.append((span[1], span[2], other))
    return sorted(out)


def _other_placed_doors(scene, room, beside) -> bool:
    """Does `room` stand on the plane by a doorway other than the one onto
    `beside`? Moving it along `beside` would then move it off the place the
    other doorway puts it, so it is not moved."""
    for edge in effective_adjacent(scene, room):
        other = str(edge.get("to") or "") if isinstance(edge, dict) else ""
        if not other or other == str(beside):
            continue
        if _laid_flat(scene, room, other) and _door(scene, room, other):
            return True
    return False


def _index_offset(index, along, length) -> float:
    """The `offset` fraction that puts a doorway `length` cells wide at cell
    `index` of a wall `along` cells long -- the inverse of
    `spatial_fov._place_anchors`, which rounds ``offset * (along - length)``."""
    room_for = along - length
    if room_for <= 0:
        return 0.0
    return round(min(1.0, max(0.0, index / room_for)), 4)


def _index_of(scene, room, other, wall):
    """Where along `wall` `room`'s doorway onto `other` starts now, as an
    index into the wall's cells, or None when it is not on that wall."""
    door = _door(scene, room, other)
    if door is None or door[1] != wall:
        return None
    rim = room_grid(scene, room).rim(wall)
    try:
        return rim.index(door[0][0])
    except ValueError:
        return None




def _gap(start, end, near) -> int:
    if near is None:
        return 0
    return max(0, near[0] - end, start - near[1])


# ---------------------------------------------------------------------------
# The plane: what a room lands on, by both rules a plane is drawn by
# ---------------------------------------------------------------------------

def _shifted(model, cells, shift, axis) -> frozenset:
    """`cells` moved `shift` cells along `axis` (0: x, 1: y); a site-plan cell
    carries its storey first."""
    at = axis + (1 if model == "plan" else 0)
    return frozenset(tuple(value + shift if index == at else value
                           for index, value in enumerate(cell))
                     for cell in cells)


def _held(cells) -> dict:
    held = {}
    for rid, mine in cells.items():
        for cell in mine:
            held.setdefault(cell, set()).add(rid)
    return held


class _Plane:
    """WHERE EVERY ROOM STANDS ON THE PLANE, read the two ways a plane is
    drawn, and what each room lands on there.

    * The layout lint's (`layout_rooms`): each connected group laid once from
      its smallest unplaced id, as `spatial_lint._embedding_rows` lays them,
      the neighbour beyond a one-cell wall band; a room the layout refused
      stands where it WOULD have landed. Its overlaps are the
      `rooms_overlap_when_placed` rows the owner reads.
    * The site plan's (`site_plan.plan_frames`): the layout
      `derive_site_plans` writes a plan with, doorways meeting across the
      wall, storeys stacked, a room it refuses standing where its first
      doorway would have put it; its overlaps are the rooms the plan leaves
      off (one storey, and a building standing in ground it opens onto is
      none -- `site_plan._stands_on`).

    Review 2026-10-08, M4: the frontage compared runs along the street's one
    wall, so a sibling was moved off its parent onto the side room laid
    through the parent's flank, reported placed, and pinned there for good.

    Read the first time a run along a wall is free to be judged -- never
    before, so a pass that finds no free run reads nothing (review
    2026-10-08, N3: it was read before every change of wall and marked
    stale on the next line, twelve reads and half a second a commit on chat
    165 for nothing placed) -- and again when a write moves a room in a way
    the reader cannot follow (onto another wall, or put back). A room
    the frontage moves stands by ONE doorway (`_other_placed_doors` refuses
    the rest), so moving it along its street's wall moves nothing else, and
    where it would stand at another start is where it stands now, moved
    along the wall by the difference: both rules meet the two doorways'
    first cells across the wall, so the run's start is the room's offset
    along it (`_span`).
    """

    def __init__(self, scene):
        self.scene = scene
        self.frames = None
        self.stale = False

    def _read(self):
        from world.site_plan import plan_frames, room_level
        scene = self.scene
        frames, placed = [], set()
        for rid in sorted(_rooms(scene)):
            if rid in placed:
                continue
            lay = layout_rooms(scene, rid)
            where = dict(lay.get("collided") or {})
            where.update(lay.get("offsets") or {})
            placed.update(where)
            frames.append(("lint", {
                room: frozenset((x + ox, y + oy)
                                for x, y in room_grid(scene, room).cells)
                for room, (ox, oy) in where.items()}))
        for xy in plan_frames(scene):
            frames.append(("plan", {
                room: frozenset((room_level(scene, room), x + ox, y + oy)
                                for x, y in room_grid(scene, room).cells)
                for room, (ox, oy) in xy.items()}))
        self.frames = [(model, cells, _held(cells)) for model, cells in frames]
        self.stale = False

    def ensure(self):
        """Read the plane if it has not been, or a write left it behind."""
        if self.frames is None or self.stale:
            self._read()

    def rooms(self) -> set:
        return {rid for _m, cells, _h in self.frames or () for rid in cells}

    def knows(self, rid) -> bool:
        return any(rid in cells for _m, cells, _h in self.frames or ())

    def hits(self, rid, shift=0, axis=0, ignore=()) -> set:
        """The rooms `rid` lands on -- moved `shift` cells along `axis` when
        asked -- in any frame either rule lays it in, but those in
        `ignore`."""
        from world.site_plan import _stands_on
        out = set()
        for model, cells, held in self.frames or ():
            mine = cells.get(rid)
            if not mine:
                continue
            if shift:
                mine = _shifted(model, mine, shift, axis)
            for cell in mine:
                for other in held.get(cell, ()):
                    if other == rid or other in ignore or other in out:
                        continue
                    if model == "plan" and _stands_on(self.scene, other, rid):
                        continue
                    out.add(other)
        return out

    def clear(self, rid, shift, axis, ignore) -> bool:
        """Would `rid`, moved `shift` along `axis`, land on no room at all
        but those in `ignore`? A place the frontage gives is a place of the
        room's own: one already touching the side room by a column is not
        moved fully onto it because the touch was there before."""
        return not self.hits(rid, shift, axis, ignore)

    def move(self, rid, shift, axis):
        """`rid` now stands `shift` cells further along `axis`."""
        if not shift:
            return
        for model, cells, held in self.frames or ():
            mine = cells.get(rid)
            if not mine:
                continue
            for cell in mine:
                held[cell].discard(rid)
            moved = _shifted(model, mine, shift, axis)
            cells[rid] = moved
            for cell in moved:
                held.setdefault(cell, set()).add(rid)


def _place(scene, street, room, wall, occupied, near, *, street_writable,
           start_at=None, plane=None, skip=()):
    """Lay `room` on `street`'s `wall` at the free run nearest `near`, by
    the two doorways' offsets. Returns the run ``(start, end)`` it took, or
    None and nothing written.

    The run is kept inside the wall (``0 <= start``, ``end <= wall length``),
    so a room fronts the street it is laid along and never overhangs its end
    into whatever stands round the corner. `start_at` asks for that one
    start and no other. With a `plane`, a run is taken only where the room
    lands on no room at all (`_Plane.clear`), the rooms in `skip` -- those
    still to be laid this pass, which may yet move -- aside; one of them
    that does not move is in the way after all, and `_take_back` judges
    that once the pass is done."""
    rooms = _rooms(scene)
    out_edge, back_edge = _own_edge(rooms, street, room), _own_edge(rooms, room, street)
    if back_edge is None or out_edge is None:
        # A doorway declared from one side only is ONE offset read from both
        # sides (`spatial_geometry.effective_anchors`), so its two ends cannot
        # be set apart; it is left as it is.
        return None
    own_wall = opposite_bearing(wall)
    along = len(room_grid(scene, street).rim(wall))
    own_along = len(room_grid(scene, room).rim(own_wall))
    width = _run(scene, room, wall)
    if along <= 0 or own_along <= 0 or width > along:
        return None
    street_door = _door(scene, street, room)
    room_door = _door(scene, room, street)
    street_len = len(street_door[0]) if street_door else 1
    room_len = len(room_door[0]) if room_door else 1
    room_last = own_along - room_len
    street_last = along - street_len
    if room_last < 0 or street_last < 0:
        return None
    current = None
    if not street_writable:
        current = _index_of(scene, street, room, wall)
        if current is None:
            return None
    centre = room_last // 2
    candidates = []
    starts = range(0, along - width + 1) if start_at is None \
        else [start_at] if 0 <= start_at <= along - width else []
    for start in starts:
        end = start + width
        if any(start < b and a < end for a, b, _r in occupied):
            continue
        # The two doorways' first cells meet across the wall, so the run
        # starts at (street index - room index); prefer the room's door at
        # the middle of its own wall.
        if current is None:
            low, high = max(0, -start), min(room_last, street_last - start)
            if low > high:
                continue
            room_index = min(max(centre, low), high)
            street_index = start + room_index
        else:
            street_index, room_index = current, current - start
            if not 0 <= room_index <= room_last:
                continue
        candidates.append(((_gap(start, end, near), start),
                           street_index, room_index, start, end))
    if not candidates:
        return None
    candidates.sort()
    axis = _axis(wall)
    ignore = {str(rid) for rid in skip} - {str(room)}
    ref = None
    if plane is not None:
        plane.ensure()
        here = _span(scene, street, room)
        if here is not None and here[0] == wall and plane.knows(room):
            ref = here[1]
    reread = False
    for _key, street_index, room_index, start, end in candidates:
        if ref is not None and not plane.clear(room, start - ref, axis, ignore):
            continue
        saved = (dict(out_edge), dict(back_edge))
        if street_writable:
            out_edge["offset"] = _index_offset(street_index, along, street_len)
        back_edge["offset"] = _index_offset(room_index, own_along, room_len)
        # THE ENGINE IS THE JUDGE, not this arithmetic: read the run back
        # through the same placement every layout uses, and undo what does
        # not land.
        if _span(scene, street, room) != (wall, start, end):
            _restore_edges(out_edge, back_edge, saved)
            continue
        if plane is not None:
            if ref is None:
                # Nowhere to read this room from until it stands somewhere
                # on this wall: it does now, so the plane is read with it
                # here, and every other start is this one moved along.
                plane.stale = True
                plane.ensure()
                ref, reread = start, True
                if not plane.clear(room, 0, axis, ignore):
                    _restore_edges(out_edge, back_edge, saved)
                    continue
            else:
                plane.move(room, start - ref, axis)
        return start, end
    if reread:
        plane.stale = True
    return None


def _restore_edges(out_edge, back_edge, saved) -> None:
    out_edge.clear()
    out_edge.update(saved[0])
    back_edge.clear()
    back_edge.update(saved[1])


def _set_wall(rooms, street, room, wall) -> tuple:
    """Put `room` on `street`'s `wall`: the bearing on both of their
    doorways, and no offset left from the wall it stood on. Returns what it
    replaced, for `_restore`."""
    out_edge, back_edge = _own_edge(rooms, street, room), _own_edge(rooms, room, street)
    saved = (dict(out_edge), dict(back_edge))
    out_edge["dir"] = wall
    back_edge["dir"] = opposite_bearing(wall)
    out_edge.pop("offset", None)
    back_edge.pop("offset", None)
    return saved


def _restore(rooms, street, room, saved) -> None:
    _restore_edges(_own_edge(rooms, street, room), _own_edge(rooms, room, street),
                   saved)


def _planned_bearing(specs, room, other):
    spec = (specs or {}).get(room)
    for edge in (spec or {}).get("adjacent") or () if isinstance(spec, dict) else ():
        if isinstance(edge, dict) and str(edge.get("to") or "") == str(other):
            return normalize_bearing(edge.get("dir"))
    return None


def _bearing_is_the_plans(scene, specs, room, other) -> bool:
    """Is the bearing `room`'s doorway onto `other` carries still the plan's
    own value -- the closure's copy, or none at all? A bearing the scene holds
    that the plan never wrote is a hand's declaration, and stays."""
    edge = _own_edge(_rooms(scene), room, other)
    if edge is None:
        return False
    here = normalize_bearing(edge.get("dir"))
    return here is None or here == _planned_bearing(specs, room, other)


def _laid_already(rooms, room, other) -> bool:
    """A split room whose own doorway onto its street carries an offset has
    been given its place -- by this module, or by a hand -- and keeps it."""
    edge = _own_edge(rooms, room, other)
    return edge is not None and normalize_offset(edge.get("offset")) is not None


# ---------------------------------------------------------------------------
# Siblings: more of a dwelling, along the street it fronts
# ---------------------------------------------------------------------------

def _alone(scene, street, rid) -> bool:
    """Does `rid`'s run along its wall of `street` overlap no other room's?"""
    here = _span(scene, street, rid)
    if here is None:
        return False
    return not any(here[1] < b and a < here[2]
                   for a, b, other in _wall_spans(scene, street, here[0])
                   if other != rid)


def _freeze(scene, street, rid, *, street_writable, plane=None) -> bool:
    """Write the place a room already stands at as its doorways' offsets, so
    the doorway spread (`spatial_orientation._spread_along_wall`) cannot move
    it when the wall gains a door. Nothing moves; True when it held.

    NEVER WHERE IT LANDS ON A ROOM. Alone along its wall is not alone on the
    plane: a room standing on the side room off its parent's flank was
    pinned there, and a pinned room is never revisited (review 2026-10-08,
    M4). With a `plane`, a room that lands on anything is left for `_place`
    to move, or to leave where it stands and report."""
    rooms = _rooms(scene)
    out_edge, back_edge = _own_edge(rooms, street, rid), _own_edge(rooms, rid, street)
    span = _span(scene, street, rid)
    if out_edge is None or back_edge is None or span is None:
        return False
    if plane is not None:
        plane.ensure()
        if plane.hits(rid):
            return False
    wall = span[0]
    own_wall = opposite_bearing(wall)
    street_index = _index_of(scene, street, rid, wall)
    room_index = _index_of(scene, rid, street, own_wall)
    if street_index is None or room_index is None:
        return False
    saved = (dict(out_edge), dict(back_edge))
    along = len(room_grid(scene, street).rim(wall))
    own_along = len(room_grid(scene, rid).rim(own_wall))
    if street_writable:
        out_edge["offset"] = _index_offset(
            street_index, along, len(_door(scene, street, rid)[0]))
    back_edge["offset"] = _index_offset(
        room_index, own_along, len(_door(scene, rid, street)[0]))
    if _span(scene, street, rid) != span:
        _restore_edges(out_edge, back_edge, saved)
        return False
    return True


def _measure_street(scene, specs, street, wall, order, plane=None) -> list:
    """Lengthen an unmeasured stub street's `wall` to hold `order` -- every
    room standing on it -- side by side, and lay them so. Only under
    `FRONTAGE_MEASURES_STREETS`; see there for why only these streets.
    Returns the rooms it laid, and ``[]`` when it measured nothing.

    A MEASUREMENT THAT PUTS ANY ROOM ON A ROOM IS TAKEN BACK WHOLE: the
    street's length and every doorway it wrote. With a `plane`, the whole
    plane is read again after, and it holds only where every room it laid
    stands on no room at all and no other room -- one laid through the
    street's other walls, which a longer street moves too -- stands on one
    it did not stand on before. Comparing the laid rooms with where they
    stood was not enough: a stranded sibling that already touched a side
    room by a column was laid fully onto it, counted as no new touch, then
    put back by `_take_back` while the street kept its new length and its
    parent the place the measurement gave it (review 2026-10-08, N5)."""
    rooms = _rooms(scene)
    room = rooms.get(street)
    spec = (specs or {}).get(street)
    if not _stub(rooms, street) or not _rectangular(scene, street):
        return []
    if normalize_extent(room.get("extent")) or (
            isinstance(spec, dict) and normalize_extent(spec.get("extent"))):
        return []
    # A SIZE TIER SOMEBODY WROTE IS A MEASUREMENT TOO (review B3, 2026-10-08):
    # a street drawn by its own `size` is drawn by a fact, and lengthening it
    # overrode that fact and stood a lint row on it ("written size 'small'
    # and extent 18x4 paces"). A plan carries no size to a stub, so such a
    # size is a hand's.
    if any(str(rec.get("size") or "").strip().casefold() in ROOM_SIZES
           for rec in (room, spec) if isinstance(rec, dict)):
        return []
    grid = room_grid(scene, street)
    need = sum(_run(scene, rid, wall) for rid in order)
    have = grid.w if _axis(wall) == 0 else grid.d
    length = min(EXTENT_MAX_PACES, need)
    if length <= have:
        return []
    before = None
    if plane is not None:
        plane.ensure()
        before = {rid: frozenset(plane.hits(rid)) for rid in plane.rooms()}
    saved = {"extent": copy.deepcopy(room.get("extent")),
             "had_extent": "extent" in room,
             "edges": {rid: (dict(_own_edge(rooms, street, rid) or {}),
                             dict(_own_edge(rooms, rid, street) or {}))
                       for rid in order}}
    room["extent"] = ({"w": length, "d": grid.d} if _axis(wall) == 0
                      else {"w": grid.w, "d": length})
    own_wall = opposite_bearing(wall)
    cursor, laid = 0, []
    for rid in order:
        width = _run(scene, rid, wall)
        if cursor + width > length:
            break
        out_edge, back_edge = _own_edge(rooms, street, rid), _own_edge(rooms, rid, street)
        if out_edge is None or back_edge is None:
            cursor += width
            continue
        own_along = len(room_grid(scene, rid).rim(own_wall))
        room_door = _door(scene, rid, street)
        room_len = len(room_door[0]) if room_door else 1
        if _stub(rooms, rid):
            room_index = (own_along - room_len) // 2
            back_edge["offset"] = _index_offset(room_index, own_along, room_len)
        else:
            room_index = _index_of(scene, rid, street, own_wall) or 0
        street_door = _door(scene, street, rid)
        street_len = len(street_door[0]) if street_door else 1
        out_edge["offset"] = _index_offset(cursor + room_index, length, street_len)
        laid.append(rid)
        cursor += width
    if plane is None:
        return laid
    plane.stale = True
    plane.ensure()
    if any(plane.hits(rid) for rid in laid) or any(
            plane.hits(rid) - before.get(rid, frozenset())
            for rid in plane.rooms()):
        if saved["had_extent"]:
            room["extent"] = saved["extent"]
        else:
            room.pop("extent", None)
        for rid, (out_saved, back_saved) in saved["edges"].items():
            out_edge, back_edge = _own_edge(rooms, street, rid), _own_edge(rooms, rid, street)
            if out_edge is not None and back_edge is not None:
                _restore_edges(out_edge, back_edge, (out_saved, back_saved))
        plane.stale = True
        return []
    return laid


def _free_runs(along, occupied) -> list:
    """The stretches ``(start, end)`` of a wall `along` cells long that no
    run in `occupied` covers."""
    runs, cursor = [], 0
    for a, b, _r in sorted(occupied):
        if a > cursor:
            runs.append((cursor, min(a, along)))
        cursor = max(cursor, b)
    if cursor < along:
        runs.append((cursor, along))
    return [(a, b) for a, b in runs if b > a]


def _lay_block(scene, street, wall, block, occupied, near_start,
               plane=None, skip=()) -> list:
    """Lay `block` -- a parent the engine alone placed, then its siblings --
    side by side in one free stretch of `street`'s `wall`: the longest run of
    the block that fits anywhere, nearest where the parent stood. Returns the
    rooms laid, in order; nothing is written for a room that is not, and the
    parent is not moved at all unless a sibling is laid beside it."""
    rooms = _rooms(scene)
    along = len(room_grid(scene, street).rim(wall))
    widths = [_run(scene, rid, wall) for rid in block]
    for count in range(len(block), 1, -1):
        total = sum(widths[:count])
        best = None
        for a, b in _free_runs(along, occupied):
            if b - a < total:
                continue
            start = min(max(near_start, a), b - total)
            key = (abs(start - near_start), start)
            if best is None or key < best[0]:
                best = (key, start)
        if best is None:
            continue
        cursor, laid, taken = best[1], [], list(occupied)
        saved = {rid: (dict(_own_edge(rooms, street, rid)),
                       dict(_own_edge(rooms, rid, street)))
                 for rid in block[:count]}
        for rid, width in zip(block[:count], widths[:count]):
            if not _place(scene, street, rid, wall, taken, None,
                          street_writable=True, start_at=cursor,
                          plane=plane, skip=set(skip) | set(block)):
                break
            taken.append((cursor, cursor + width, rid))
            laid.append(rid)
            cursor += width
        if len(laid) == count:
            return laid
        for rid, (out_saved, back_saved) in saved.items():
            _restore(rooms, street, rid, (out_saved, back_saved))
        if plane is not None:
            plane.stale = True
    return []


def _engine_placed(scene, parent, street) -> bool:
    """Was the parent's doorway onto `street` placed by the engine alone --
    a stub's door whose own side carries no offset, standing nowhere else on
    the plane -- so that sliding it along the wall moves nothing a hand
    chose? The street side's offset is the doorway spread's
    (`spatial_orientation._spread_along_wall`), never an author's."""
    rooms = _rooms(scene)
    return (_stub(rooms, parent) and _stub(rooms, street)
            and _own_edge(rooms, parent, street) is not None
            and _own_edge(rooms, street, parent) is not None
            and not _laid_already(rooms, parent, street)
            and not _other_placed_doors(scene, parent, street)
            and not _whole_side(scene, street, parent))


def _streets_of(scene, parent, siblings) -> dict:
    """``{street: span}``: every flat, rectangular neighbour of the parent
    that the parent is laid along -- the streets it fronts."""
    rooms = _rooms(scene)
    out = {}
    for edge in effective_adjacent(scene, parent):
        street = str(edge.get("to") or "") if isinstance(edge, dict) else ""
        if street and street in rooms and street not in siblings \
                and _rectangular(scene, street):
            span = _span(scene, street, parent)
            if span:
                out[street] = span
    return out


def _street_for(scene, rid, streets):
    """``(street, None)`` for the one street of its parent's a sibling
    fronts, or ``(None, candidates)`` when that is not the closure's to say.

    A SIBLING FRONTS THE STREET ITS OWN DOORWAY IS WALLED ONTO. It copied
    every one of its parent's doorways, so it shares every street its parent
    fronts; where a hand walled one of them on the sibling's side, that is
    the street, and where its parent fronts exactly one, the closure's "same
    neighbours" is that one. Where the parent fronts several and the sibling
    is walled onto none, which it stands on is not a measurement but a
    choice, and the frontage leaves it and says so: it used to take the
    first street in id order, and a house whose parent fronted a lane and a
    garden was laid across the garden, its lane door unwalled (review
    2026-10-08, L1)."""
    rooms = _rooms(scene)
    shared = [street for street in sorted(streets)
              if _own_edge(rooms, rid, street) is not None
              and _own_edge(rooms, street, rid) is not None
              and _laid_flat(scene, street, rid)]
    walled = [street for street in shared if _door(scene, rid, street)]
    if len(walled) == 1:
        return walled[0], None
    if not walled and len(shared) == 1:
        return shared[0], None
    return None, (walled or shared)


def _lay_siblings(scene, specs, parent, siblings, measure, plane) -> list:
    rooms = _rooms(scene)
    if parent not in rooms:
        return []
    pending = [rid for rid in siblings
               if rid in rooms and _stub(rooms, rid) and _rectangular(scene, rid)]
    streets = _streets_of(scene, parent, siblings)
    assigned, undecided = {}, {}
    for rid in pending:
        street, candidates = _street_for(scene, rid, streets)
        if street:
            assigned[rid] = street
        elif candidates:
            undecided[rid] = candidates
    report = []
    for street, (wall, p_start, p_end) in sorted(streets.items()):
        near = (p_start, p_end)
        mine = [rid for rid in pending
                if assigned.get(rid) == street
                and not _other_placed_doors(scene, rid, street)
                and not _whole_side(scene, street, rid)]
        waiting = [rid for rid in mine
                   if not (_laid_already(rooms, rid, street)
                           and _span(scene, street, rid))]
        if not waiting:
            continue
        street_writable = _stub(rooms, street)
        placed, far, left = [], [], []

        def unplaced():
            return [rid for rid in waiting if rid not in placed and rid not in far]

        # THE PARENT AND ITS SIBLINGS AS ONE BLOCK, when nothing but the
        # engine ever put the parent's door where it is: the doorway spread
        # sets a door mid-wall, and the free stretch either side of it is
        # then too short for a house that the whole wall would hold.
        moved_parent = False
        if _engine_placed(scene, parent, street):
            walled, block = {}, []
            for rid in waiting:
                here = _span(scene, street, rid)
                if here is None:
                    if _bearing_is_the_plans(scene, specs, rid, street):
                        # No read here: `_place` reads the plane itself, and
                        # only once a run along the wall is free (N3).
                        walled[rid] = _set_wall(rooms, street, rid, wall)
                        plane.stale = True
                        block.append(rid)
                elif here[0] == wall:
                    block.append(rid)
            if block:
                laid = _lay_block(
                    scene, street, wall, [parent] + block,
                    _wall_spans(scene, street, wall, skip=[parent] + block),
                    p_start, plane=plane, skip=waiting)
                placed.extend(rid for rid in laid if rid != parent)
                for rid, saved in walled.items():
                    if rid not in laid:
                        _restore(rooms, street, rid, saved)
                        plane.stale = True
                if parent in laid:
                    moved_parent = True
                    moved = _span(scene, street, parent)
                    near = (moved[1], moved[2])
        for rid in waiting:
            if rid in placed:
                continue
            here = _span(scene, street, rid)
            if here is None:
                # A DOORWAY NOBODY GAVE A WALL is still the plan's copy of the
                # parent's, so the sibling takes the parent's wall -- the
                # closure's "same neighbours", finished.
                if not (street_writable
                        and _bearing_is_the_plans(scene, specs, rid, street)):
                    left.append(rid)
                    continue
                saved = _set_wall(rooms, street, rid, wall)
                plane.stale = True
                if _place(scene, street, rid, wall,
                          _wall_spans(scene, street, wall, skip=unplaced()),
                          near, street_writable=True, plane=plane,
                          skip=unplaced()):
                    placed.append(rid)
                else:
                    _restore(rooms, street, rid, saved)
                    plane.stale = True
                    left.append(rid)
                continue
            if _alone(scene, street, rid) and _freeze(
                    scene, street, rid, street_writable=street_writable,
                    plane=plane):
                placed.append(rid)
                continue
            on = here[0]
            if _place(scene, street, rid, on,
                      _wall_spans(scene, street, on, skip=unplaced()),
                      near if on == wall else None,
                      street_writable=street_writable, plane=plane,
                      skip=unplaced()):
                placed.append(rid)
            else:
                left.append(rid)
        # THE FAR SIDE, when the near one is full. A bearing nobody but the
        # plan ever set, between two of the plan's stubs, is the closure's
        # own, so it may be the other side of the street.
        for rid in list(left):
            if not (street_writable
                    and _bearing_is_the_plans(scene, specs, rid, street)):
                continue
            far_wall = opposite_bearing(wall)
            saved = _set_wall(rooms, street, rid, far_wall)
            plane.stale = True
            if _place(scene, street, rid, far_wall,
                      _wall_spans(scene, street, far_wall, skip=unplaced()),
                      None, street_writable=True, plane=plane,
                      skip=unplaced()):
                far.append(rid)
                left.remove(rid)
            else:
                _restore(rooms, street, rid, saved)
                plane.stale = True
        laid_by_measure = []
        if left and measure:
            stranded = [rid for rid in left
                        if (_span(scene, street, rid) or ("",))[0] == wall]
            if stranded:
                on_wall = [r for _a, _b, r in
                           _wall_spans(scene, street, wall, skip=stranded)]
                laid_by_measure = _measure_street(
                    scene, specs, street, wall, on_wall + stranded, plane)
                for rid in stranded:
                    if rid in laid_by_measure and _alone(scene, street, rid):
                        placed.append(rid)
                        left.remove(rid)
        report.append({
            "parent": parent, "mode": "siblings", "street": street,
            "wall": wall, "placed": placed, "far_side": far,
            "measured": bool(laid_by_measure), "unplaced": left,
            "short": sum(_run(scene, rid, wall) for rid in left),
            # Every room this row moved, for `_take_back`: a measurement
            # relays every room on the wall, the parent's and any other's.
            "moved": list(dict.fromkeys(
                ([parent] if moved_parent else []) + placed + far
                + laid_by_measure)),
            "laid_by_measure": list(laid_by_measure)})
    if undecided:
        report.append({
            "parent": parent, "mode": "siblings", "street": "", "wall": "",
            "placed": [], "far_side": [], "measured": False,
            "unplaced": sorted(undecided), "short": 0, "moved": [],
            "streets": {rid: list(c) for rid, c in sorted(undecided.items())}})
    return report


# ---------------------------------------------------------------------------
# Annexes: off the workplace, on a wall nothing else uses
# ---------------------------------------------------------------------------

def _lay_annexes(scene, specs, parent, annexes, plane) -> list:
    rooms = _rooms(scene)
    if parent not in rooms or not _rectangular(scene, parent):
        return []
    mine = [rid for rid in annexes
            if rid in rooms and _stub(rooms, rid) and _rectangular(scene, rid)
            and _own_edge(rooms, rid, parent) is not None
            and _own_edge(rooms, parent, rid) is not None
            and _laid_flat(scene, parent, rid)
            and not _other_placed_doors(scene, rid, parent)
            and not _whole_side(scene, parent, rid)]
    waiting = [rid for rid in mine
               if not (_laid_already(rooms, rid, parent)
                       and _span(scene, parent, rid))]
    if not waiting:
        return []
    parent_writable = _stub(rooms, parent)
    # A WALL IS FREE WHEN NO DOORWAY BUT AN ANNEX'S IS ON IT. Whether the
    # workplace's walls are known at all is a question about its OTHER
    # doorways: one nobody has given a wall yet could be on any of them, so
    # an annex with no wall of its own waits until each of them has one.
    used, unknown = set(), False
    annex_set = {str(rid) for rid in annexes}
    for edge in effective_adjacent(scene, parent):
        other = str(edge.get("to") or "") if isinstance(edge, dict) else ""
        if not other or other in annex_set or other not in rooms \
                or not _laid_flat(scene, parent, other):
            continue
        cells, bearing = _door_cells(scene, parent, other)
        if not cells or not bearing:
            unknown = True
        elif bearing in _WALLS:
            used.add(bearing)
        else:
            # A corner doorway stands where two walls meet, and a room laid
            # through it stands off both.
            used.update(wall for wall in _WALLS if wall in bearing)
    grid = room_grid(scene, parent)
    free = sorted((wall for wall in _WALLS if wall not in used),
                  key=lambda wall: (-len(grid.rim(wall)), _WALLS.index(wall)))
    placed, left = [], []
    # Each wall's runs, read once and kept as annexes land on it: a workplace
    # with dozens of annexes (chat 164's walk had 29) is laid in one pass
    # over its walls, not one per annex.
    held = {wall: _wall_spans(scene, parent, wall, skip=waiting)
            for wall in _WALLS}
    full = {}
    for rid in waiting:
        rest = [r for r in waiting if r not in placed and r != rid]
        here = _span(scene, parent, rid)
        if here is not None:
            if _alone(scene, parent, rid) and _freeze(
                    scene, parent, rid, street_writable=parent_writable,
                    plane=plane):
                placed.append(rid)
            elif _place(scene, parent, rid, here[0], held[here[0]], None,
                        street_writable=parent_writable, plane=plane,
                        skip=rest):
                placed.append(rid)
            else:
                left.append(rid)
                continue
            laid = _span(scene, parent, rid)
            held[laid[0]].append((laid[1], laid[2], rid))
            continue
        if unknown or not parent_writable \
                or not _bearing_is_the_plans(scene, specs, rid, parent):
            left.append(rid)
            continue
        for wall in free:
            width = _run(scene, rid, wall)
            if width >= full.get(wall, width + 1):
                continue
            saved = _set_wall(rooms, parent, rid, wall)
            plane.stale = True
            run = _place(scene, parent, rid, wall, held[wall], None,
                         street_writable=True, plane=plane, skip=rest)
            if run:
                placed.append(rid)
                held[wall].append((run[0], run[1], rid))
                break
            _restore(rooms, parent, rid, saved)
            plane.stale = True
            # A wall that cannot take this annex takes none as wide.
            if not any(b - a >= width
                       for a, b in _free_runs(len(grid.rim(wall)), held[wall])):
                full[wall] = min(width, full.get(wall, width))
        else:
            left.append(rid)
    return [{"parent": parent, "mode": "annexes", "walls": free,
             "placed": placed, "unplaced": left,
             "waiting_on_walls": bool(unknown), "moved": list(placed)}]


def _take_back(scene, plane, report, snapshot, extents) -> None:
    """THE PLANE, READ AGAIN AFTER EVERYTHING MOVED, IS THE LAST WORD. A room
    this pass moved that now lands on a room -- its run free along its wall,
    and something laid through another doorway standing there, or a move the
    reader could not follow -- is put back where it stood (`snapshot`, its
    doorways as the pass found them) and reported unplaced.

    A ROOM THE PASS LEFT UNPLACED IS AN OBSTACLE WHERE IT STANDS. A choice
    looks past the rooms still waiting to be laid (`_place`'s `skip`),
    because they may yet move; one that did not move stands where the merge's
    doorway spread put it, which is anywhere along the wall, not on its
    parent. It used to be passed over here too, so a sibling was laid onto
    the one beside it, reported placed and pinned there (review 2026-10-08,
    N2: a six-pace lane, the House and two siblings three paces wide, and
    house_2 moved from (1,4) onto house_3 at (3,6)). Only a room with no
    place on the plane at all is passed over, and that is no room
    `_Plane.hits` can name.

    WHAT WAS MOVED FOR A ROOM GOES BACK WITH IT. A measurement is taken back
    whole when any room it laid is: the street's length (`extents`, as the
    pass found it) and every doorway it wrote, so a street is never left
    lengthened for a room that no longer stands on it (N5). And a parent
    slid along its wall to make room for a block of its siblings
    (`_lay_block`) goes back once no sibling of its stands placed: it was
    moved for them, not for itself.

    Putting one back can put another on it, so this reads again until
    nothing more is taken back."""
    owners = {}
    for row in report:
        for rid in row.get("moved") or ():
            owners.setdefault(rid, []).append(row)
    if not owners:
        return
    rooms = _rooms(scene)
    taken_back = set()
    while True:
        plane.stale = True
        plane.ensure()
        landed = {rid for rid in owners if rid not in taken_back
                  and plane.hits(rid)}
        bad = set(landed)
        for row in report:
            laid = row.get("laid_by_measure") or ()
            if row.get("measured") and any(
                    rid in bad or rid in taken_back for rid in laid):
                row["measured"] = False
                had, extent = extents.get(row["street"], (False, None))
                if had:
                    rooms[row["street"]]["extent"] = copy.deepcopy(extent)
                else:
                    rooms[row["street"]].pop("extent", None)
                bad.update(rid for rid in laid if rid not in taken_back)
        for row in report:
            parent = row.get("parent")
            if row.get("mode") == "siblings" and parent in owners \
                    and parent not in taken_back \
                    and parent in (row.get("moved") or ()) \
                    and all(rid in bad for rid in (row.get("placed") or [])
                            + (row.get("far_side") or [])):
                bad.add(parent)
        if not bad:
            return
        for rid in sorted(bad):
            taken_back.add(rid)
            for other, edges in snapshot.items():
                if other == rid:
                    rooms[rid]["adjacent"] = copy.deepcopy(edges)
                    continue
                for edge in edges:
                    if str(edge.get("to") or "") != rid:
                        continue
                    for live in rooms.get(other, {}).get("adjacent") or ():
                        if isinstance(live, dict) and str(live.get("to") or "") == rid:
                            live.clear()
                            live.update(copy.deepcopy(edge))
            for row in owners.get(rid, ()):
                # Only a split room this row laid is reported unplaced; a
                # parent or a room a measurement relaid is not one of them.
                was = [key for key in ("placed", "far_side")
                       if rid in (row.get(key) or ())]
                for key in was:
                    row[key].remove(rid)
                if was and rid not in row["unplaced"]:
                    row["unplaced"].append(rid)
                    if row.get("wall"):
                        row["short"] = row.get("short", 0) + _run(
                            scene, rid, row["wall"])
                if rid in landed:
                    row.setdefault("lands_on_a_room", []).append(rid)


def lay_frontages(scene, specs, *, measure_streets=None) -> list:
    """Give every split room in `scene` its frontage, in place.

    `specs` is the plan, ``{uid: planned spec}``: it says which rooms the
    closure split from which (`splits_from_specs`) and what each doorway's
    bearing was in the plan, which is how a hand's bearing is told from the
    plan's copy. Returns one report row per street a dwelling's siblings
    were laid along and per workplace whose annexes were, each naming what
    was placed, what went to the street's far side, what was left where it
    stood because the wall had no room for it, and what was put back because
    it landed on a room (`lands_on_a_room`); and one row per parent whose
    siblings could front more than one of its streets (`streets`). A scene
    with no split room is returned untouched and the report is empty.
    """
    measure = FRONTAGE_MEASURES_STREETS if measure_streets is None \
        else bool(measure_streets)
    splits = splits_from_specs(specs)
    if not splits:
        return []
    plane = _Plane(scene)
    snapshot = {rid: copy.deepcopy(room.get("adjacent") or [])
                for rid, room in _rooms(scene).items() if isinstance(room, dict)}
    extents = {rid: ("extent" in room, copy.deepcopy(room.get("extent")))
               for rid, room in _rooms(scene).items() if isinstance(room, dict)}
    report = []
    for parent, record in sorted(splits.items()):
        if record["mode"] == "siblings":
            report.extend(_lay_siblings(scene, specs, parent,
                                        record["rooms"], measure, plane))
        else:
            report.extend(_lay_annexes(scene, specs, parent, record["rooms"],
                                       plane))
    _take_back(scene, plane, report, snapshot, extents)
    for row in report:
        row.pop("moved", None)
        row.pop("laid_by_measure", None)
    return report


__all__ = [
    "ANNEX_OF", "FRONTAGE_MEASURES_STREETS", "SPLIT_MARKS", "SPLIT_OF",
    "lay_frontages", "split_marks", "splits_from_specs",
]
