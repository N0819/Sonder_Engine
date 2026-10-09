# spatial_lint.py
"""The layout lint: where a scene's rooms cannot all be true at once.

Deterministic, pure over the scene dict, and IT READS NO PROSE -- not
`desc`, not `name`, not `notes` (CLAUDE.md forbids a guard that reads free
text, and every check here reads a bearing, an extent, a shape or a placed
cell). Rows, never fixes: the `contradictory_sight_edges` precedent. The
commit surfaces a row once, the beat it appears (`persist/commit_scene_state.py`,
under the `layout_lint_told` flag), and the Room's `inspect_contradictions`
always shows every standing row under `layout`.

Why it exists (`docs/experiments/DEBUG_RUN_2026_09_04.md`): F3 minted a room
called "West" from a bare compass word and nothing between the plan and the
scene asked whether the geometry it implied could be drawn; F27 read anchor
ids scene-wide when every writer scopes them to a room. The embedding check
here lays the rooms out by their bearings with the same rule the observer's
field uses (`spatial_fov.observer_field`: a neighbour beyond a one-cell band
with the two door cells aligned) and names the pair that lands on the same
cells -- a set of bearings that cannot be embedded on a plane is a room in
the wrong place, whatever its name says.

Design: `docs/design/DESIGN_ROOM_FIDELITY.md` §3.
"""

from __future__ import annotations

from world.spatial_barriers import effective_adjacent, normalize_barrier
from world.spatial_fov import (
    _PART_SHAPES, _UNIT, _door_cells, anchor_cells, normalize_parts,
    normalize_shape, part_box, room_grid,
)
from world.spatial_geometry import (
    ROOM_SIZES, normalize_extent, size_from_extent,
)
from world.spatial_orientation import (
    normalize_bearing, normalize_vertical, opposite_bearing,
)


#: Every row kind this module can produce, so a reader can enumerate them.
LAYOUT_LINT_KINDS = (
    "reciprocal_bearing_disagrees",
    "openings_overlap",
    "wall_overfull",
    "corner_in_round_room",
    "l_part_redundant",
    "parts_disconnected",
    "shape_disconnected",
    "rooms_overlap_when_placed",
    "site_plan_overlap",
    "size_disagrees_with_extent",
    "extent_unreadable",
)

_WALLS = ("n", "e", "s", "w")


def _rooms(scene):
    return {str(rid): room for rid, room in
            ((scene or {}).get("rooms") or {}).items()
            if isinstance(room, dict)}


def _name(rooms, rid):
    return str((rooms.get(rid) or {}).get("name") or rid)


# ---------------------------------------------------------------------------
# One room at a time
# ---------------------------------------------------------------------------

def _extent_rows(scene, rooms):
    out = []
    for rid, room in sorted(rooms.items()):
        raw = room.get("extent")
        if raw not in (None, "", {}, []) and normalize_extent(raw) is None:
            out.append({"kind": "extent_unreadable", "room": rid,
                        "extent": raw})
            continue
        extent = normalize_extent(raw)
        authored = str(room.get("size") or "").strip().casefold()
        if extent and authored in ROOM_SIZES:
            measured = size_from_extent(extent)
            if measured != authored:
                out.append({"kind": "size_disagrees_with_extent", "room": rid,
                            "size": authored, "extent": extent,
                            "measured": measured})
    return out


def _shape_rows(scene, rooms):
    out = []
    for rid, room in sorted(rooms.items()):
        shape = normalize_shape(room.get("shape"))
        parts = normalize_parts(room.get("parts"))
        if shape == "round" and parts:
            out.append({"kind": "corner_in_round_room", "room": rid,
                        "corners": [p["at"] for p in parts]})
        pieces = False
        if shape in _PART_SHAPES and len(parts) >= 2:
            grid = room_grid(scene, rid)
            boxes = [(*part_box(part, grid.w, grid.d), _part_label(part))
                     for part in parts]
            if shape == "l":
                for i, a in enumerate(boxes):
                    for j, b in enumerate(boxes):
                        if i != j and a[0] >= b[0] and a[1] >= b[1] \
                                and a[2] <= b[2] and a[3] <= b[3]:
                            out.append({"kind": "l_part_redundant", "room": rid,
                                        "part": a[4], "within": b[4]})
                            break
            # THE PARTS MUST TOUCH. A composite whose rectangles share no
            # edge and no cell is two floors wearing one id -- a row, never
            # a refusal (the owner's map lets a host lay the parts down one
            # at a time, and the second may well not touch until the third
            # arrives). Named at the part level, so the row says which
            # pieces stand apart; the cell-level `shape_disconnected` below
            # is then the same fact and is not repeated.
            groups = _part_components(boxes)
            if len(groups) > 1:
                pieces = True
                out.append({"kind": "parts_disconnected", "room": rid,
                            "pieces": [[b[4] for b in g] for g in groups]})
        if not pieces and (shape != "rectangle"
                           or normalize_extent(room.get("extent"))):
            grid = room_grid(scene, rid)
            if not _cells_connected(grid.cells):
                out.append({"kind": "shape_disconnected", "room": rid,
                            "shape": shape})
    return out


def _part_label(part) -> str:
    """A part named for a row: its corner word, or its origin as `x,y`."""
    at = part["at"]
    return at if isinstance(at, str) else "%d,%d" % (at[0], at[1])


def _boxes_touch(a, b) -> bool:
    """Two half-open rectangles share a cell, or an edge of positive length."""
    ox = min(a[2], b[2]) - max(a[0], b[0])
    oy = min(a[3], b[3]) - max(a[1], b[1])
    return (ox > 0 and oy > 0) or (ox > 0 and oy == 0) or (oy > 0 and ox == 0)


def _part_components(boxes) -> list:
    """The boxes grouped by touching, in the order given; a box the bounding
    box clipped to nothing holds no floor and joins nothing."""
    groups, seen = [], set()
    for i in range(len(boxes)):
        if i in seen:
            continue
        group, stack = [], [i]
        seen.add(i)
        while stack:
            k = stack.pop()
            group.append(boxes[k])
            if boxes[k][2] <= boxes[k][0] or boxes[k][3] <= boxes[k][1]:
                continue
            for j, other in enumerate(boxes):
                if j not in seen and other[2] > other[0] and other[3] > other[1] \
                        and _boxes_touch(boxes[k], other):
                    seen.add(j)
                    stack.append(j)
        groups.append(group)
    return groups


def _cells_connected(cells) -> bool:
    cells = set(cells)
    if not cells:
        return True
    start = min(cells)
    seen = {start}
    stack = [start]
    while stack:
        x, y = stack.pop()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if (nx, ny) in cells and (nx, ny) not in seen:
                seen.add((nx, ny))
                stack.append((nx, ny))
    return len(seen) == len(cells)


def wall_loads(scene, room_id) -> dict:
    """`{(wall, height): {anchor_id: paces}}`: what each fixture of the room
    takes along each straight wall, at its own height.

    A WALL IS COUNTED PER HEIGHT, ALONG ITS RIM. Two fixtures that stand at
    different heights do not compete for a wall -- a head-height shelf over
    a waist-height bartop is one stretch of wall holding two things -- and a
    `large` fixture's inward row is floor in front of the wall, not more of
    it. So a fixture laid along its wall (`spatial_fov._wall_slot`: seeded,
    or at an authored `offset`) takes the length it was laid at, whether it
    stands on the rim or one pace out in its `lane`; one pinned to a cell
    takes the cells of that wall's rim it covers, whatever its `dir` says,
    since a cell pin lays it where the cell is (`spatial_fov._place_anchors`).
    Counted over every cell until 2026-10-08: of the 12 over-full walls the
    31 in-beat first drafts of that day's play database were told of, 9 fit
    counted this way (the elevator shaft's walls, the inn's west wall over
    its bar, the main walk's east side), and so does the standing
    `co_op_office` row -- a chair at floor height under a desk at waist
    height on a four-pace wall -- copied into six chats. Doorways are not
    counted: they are openings, `openings_overlap`'s."""
    from world.spatial_fov import _seed, _wall_slot
    from world.spatial_geometry import effective_anchors
    grid = room_grid(scene, room_id)
    placed = anchor_cells(scene, room_id)
    anchors = effective_anchors(scene, room_id)
    rims = {wall: set(grid.rim(wall)) for wall in _WALLS}
    out = {}
    for aid, rec in placed.items():
        if rec["implicit"]:
            continue
        height = rec["height"]
        bearing = rec.get("dir")
        if bearing in _WALLS and rec.get("source") in ("seed", "offset"):
            anchor = anchors.get(aid) if isinstance(anchors.get(aid), dict) else {}
            _along, length, _offset, _source = _wall_slot(
                grid, bearing, anchor, rec["footprint"], _seed(room_id, aid))
            paces = min(length, len(rec["cells"]))
            if paces:
                out.setdefault((bearing, height), {})[aid] = paces
            continue
        if rec.get("source") == "cell":
            for wall in _WALLS:
                on = sum(1 for cell in rec["cells"] if tuple(cell) in rims[wall])
                if on:
                    out.setdefault((wall, height), {})[aid] = on
    return out


def _whole_side(rec) -> bool:
    """An opening that is a whole open side (`width: "wall"`): an open way
    between two unenclosed rooms, or a rail, spans the wall it is on."""
    return rec.get("source") == "side"


def _wall_rows(scene, rooms):
    """A wall's anchors need more paces at one height than the wall has, or
    two doorways on one wall were placed on the same cells."""
    out = []
    for rid in sorted(rooms):
        grid = room_grid(scene, rid)
        placed = anchor_cells(scene, rid)
        doors = {}
        for aid, rec in placed.items():
            bearing = rec.get("dir")
            if bearing in _WALLS and rec["implicit"]:
                doors.setdefault(bearing, []).append(
                    (aid, set(rec["cells"]), _whole_side(rec)))
        for (bearing, height), paces in sorted(wall_loads(scene, rid).items()):
            have = len(grid.rim(bearing))
            needs = sum(paces.values())
            if needs > have:
                out.append({"kind": "wall_overfull", "room": rid,
                            "wall": bearing, "height": height,
                            "needs": needs, "holds": have})
        for bearing, ways in sorted(doors.items()):
            ways.sort(key=lambda way: way[0])
            for i, (a_id, a_cells, a_side) in enumerate(ways):
                for b_id, b_cells, b_side in ways[i + 1:]:
                    # A WHOLE OPEN SIDE HOLDS ANY OTHER OPENING. Under the
                    # owner's 2026-09-15 rule an open way between two
                    # unenclosed rooms spans the wall, so any other way out
                    # through that wall stands within it, and no offset can
                    # move either one off the other: the Gale house landing's
                    # open stair and the reed staithe's open side each span
                    # the low walk's south wall, and a designer spent the
                    # last of its eight steps on a row nothing could clear
                    # (chat 166, turn 22). Two narrow doorways on the same
                    # cells are still two doors in one place.
                    if a_side or b_side:
                        continue
                    if a_cells & b_cells:
                        out.append({"kind": "openings_overlap", "room": rid,
                                    "wall": bearing,
                                    "openings": [a_id, b_id]})
    return out


# ---------------------------------------------------------------------------
# Between rooms
# ---------------------------------------------------------------------------

def _declared_dir(rooms, room_id, to_id):
    room = rooms.get(room_id) or {}
    for edge in room.get("adjacent") or []:
        if isinstance(edge, dict) and str(edge.get("to")) == str(to_id):
            return normalize_bearing(edge.get("dir"))
    return None


def _declared_vertical(rooms, room_id, to_id):
    room = rooms.get(room_id) or {}
    for edge in room.get("adjacent") or []:
        if isinstance(edge, dict) and str(edge.get("to")) == str(to_id):
            return normalize_vertical(edge.get("vertical"))
    return None


def _bearing_rows(rooms):
    out = []
    for a_id in sorted(rooms):
        for edge in (rooms[a_id].get("adjacent") or []):
            if not isinstance(edge, dict) or not edge.get("to"):
                continue
            b_id = str(edge["to"])
            if b_id <= a_id or b_id not in rooms:
                continue                    # one row per pair
            # A WAY UP OR DOWN IS NOT A DOOR SEEN FROM TWO SIDES. Each end's
            # bearing is the wall that floor's end of the stair, ladder or
            # hatch sits on -- the same wall on every floor of a tower, or two
            # different walls for a straight flight -- so the two need not be
            # opposites, and the engine keeps both and gives a silent floor
            # the other's (`spatial_orientation.normalize_scene_bearings`, the
            # card's WHICH WALL A WAY OUT IS IN). Read as a door's, the pair
            # was a row no answer could clear: the merge gives the far floor
            # the same wall, and the row demanded its opposite -- a designer
            # flipped the Gale house landing's stair between n and s for
            # seven steps (chat 166, turn 22).
            if normalize_vertical(edge.get("vertical")) \
                    or _declared_vertical(rooms, b_id, a_id):
                continue
            fwd = normalize_bearing(edge.get("dir"))
            back = _declared_dir(rooms, b_id, a_id)
            if fwd and back and opposite_bearing(fwd) != back:
                out.append({"kind": "reciprocal_bearing_disagrees",
                            "rooms": [a_id, b_id], "dirs": [fwd, back],
                            "names": [_name(rooms, a_id), _name(rooms, b_id)]})
    return out


def _beared_neighbours(scene, room_id, rooms):
    """(neighbour, bearing) for every edge of the room with a bearing whose
    barrier is not a wall -- a closed door has geometry too.

    A ROOM YOU REACH BY GOING UP OR DOWN IS NOT BESIDE YOU, so it is not
    laid out on this floor and cannot collide with anything on it. The
    bearing on a vertical edge says which way the flight leans, not which
    stretch of wall it takes; embedding the far room at it puts a storey on
    the plane and then reports the overlap as a contradiction the author
    must fix. `spatial_fov.sight_passes` keeps the same rule for the sight
    field, and `spatial_orientation.normalize_scene_bearings` for the
    collision that strips a bearing (2026-09-05, PM1, and F67 of
    `DEBUG_RUN_2026_09_04.md`, which is this confusion in the lint).
    """
    out = []
    for edge in effective_adjacent(scene, room_id):
        if not isinstance(edge, dict) or not edge.get("to"):
            continue
        if normalize_barrier(edge.get("barrier")) == "wall":
            continue
        if normalize_vertical(edge.get("vertical")):
            continue
        bearing = normalize_bearing(edge.get("dir"))
        to_id = str(edge["to"])
        if bearing and to_id in rooms and to_id != str(room_id):
            out.append((to_id, bearing))
    return sorted(out)


def _laid_beside(scene, room_id, other, at):
    """`(offset, cells)` where `other` lands when laid out from `room_id`
    standing at `at`, by the observer field's rule -- beyond a one-cell band,
    the two door cells aligned -- or None when the doorway has no cells to
    lay it by (no bearing on either side). The ONE statement of the rule, for
    `layout_rooms` and for `leaf_rows`, which lays a single new room against
    the layouts `layout_rooms` already made."""
    d1s, b1 = _door_cells(scene, room_id, other)
    d2s, _b2 = _door_cells(scene, other, room_id)
    if not d1s or not d2s or not b1:
        return None
    ux, uy = _UNIT[b1]
    d1, d2 = d1s[0], d2s[0]
    far = (d1[0] + ux + ux + at[0], d1[1] + uy + uy + at[1])
    offset = (far[0] - d2[0], far[1] - d2[1])
    return offset, [(x + offset[0], y + offset[1])
                    for x, y in room_grid(scene, other).cells]


def layout_rooms(scene, start) -> dict:
    """Place every room reachable from `start` over beared, non-wall edges
    with the observer field's rule -- the neighbour laid beyond a one-cell
    band with the two door cells aligned -- and report
    ``{"offsets": {room: (ox, oy)}, "collisions": [(room, other, via)]}``.

    A collision is a room whose cells, placed, land on cells another placed
    room already holds: the bearings from `start` outward cannot all be
    drawn on one plane. Breadth-first in sorted order, so a reroll lays the
    same rooms out the same way and names the same pair. A room whose door
    onto a neighbour has no placeable cell (no bearing on either side) is not
    reached through that door.

    ``collided`` (added 2026-09-04 for the World Browser's structure map) is
    where each colliding room WOULD have landed -- the offset the rule gave
    it before the collision refused it -- so a map can draw the two rooms on
    one another rather than hide the one that lost. It is never an entry of
    ``offsets`` and places nothing.

    ``expanded`` and ``blocked`` (added 2026-10-08 for `leaf_rows`) say WHEN
    each thing happened: the rooms in the order the walk laid their
    neighbours out, and for each entry of ``collisions`` the bearing it was
    tried across and the offset it would have taken. A room added beside
    one already laid out can change which room a later collision names, and
    only the walk's order says whether it was there in time.
    """
    rooms = _rooms(scene)
    if str(start) not in rooms:
        return {"offsets": {}, "collisions": [], "collided": {}, "parents": {},
                "expanded": [], "blocked": []}
    offsets = {str(start): (0, 0)}
    collided = {}
    # `parents` (2026-09-05, the structure map's drag): the room each placed
    # room was laid out FROM -- the edge a drop re-bears. Additive; the
    # start has none.
    parents = {}
    occupied = {}
    for x, y in room_grid(scene, start).cells:
        occupied[(x, y)] = str(start)
    collisions = []
    expanded, blocked = [], []
    frontier = [str(start)]
    while frontier:
        nxt = []
        for room_id in frontier:
            expanded.append(room_id)
            ox, oy = offsets[room_id]
            for other, bearing in _beared_neighbours(scene, room_id, rooms):
                if other in offsets:
                    continue
                laid = _laid_beside(scene, room_id, other, (ox, oy))
                if laid is None:
                    continue
                offset, cells = laid
                hit = sorted({occupied[c] for c in cells if c in occupied})
                if hit:
                    collisions.append((other, hit[0], room_id))
                    blocked.append((bearing, offset))
                    collided.setdefault(other, offset)
                    parents.setdefault(other, room_id)
                    continue
                offsets[other] = offset
                parents[other] = room_id
                for c in cells:
                    occupied[c] = other
                nxt.append(other)
        frontier = sorted(nxt)
    return {"offsets": offsets, "collisions": collisions, "collided": collided,
            "parents": parents, "expanded": expanded, "blocked": blocked}


def _walks(scene, rooms):
    """`(start, layout)` for each walk the whole check makes: each connected
    part laid out once, from its smallest id no earlier walk reached. A room
    a walk could not place (a collision) is reached all the same, and starts
    no walk of its own. The ONE statement of the order, for `_embedding_rows`
    and for `layout_index`, which `leaf_rows` reads in its place."""
    placed = set()
    for rid in sorted(rooms):
        if rid in placed:
            continue
        layout = layout_rooms(scene, rid)
        placed.update(layout["offsets"])
        placed.update(other for other, _onto, _via in layout["collisions"])
        yield rid, layout


def _collision_rows(scene, rooms, layout, disagreeing=frozenset()):
    """One walk's collisions as rows. A collision across a doorway whose two
    bearings already disagree is that row's consequence, not a second fact,
    and is not repeated here."""
    from world.site_plan import room_site
    out = []
    for other, onto, via in layout["collisions"]:
        if frozenset((other, via)) in disagreeing:
            continue
        # Two rooms ONE SITE PLAN places are where the plan put them: a
        # house in the hole of its garden is no contradiction, and the
        # walk's one-cell wall band would call it one every time. The
        # plan's own overlaps are `site_plan_overlap`.
        a_site, b_site = room_site(scene, other), room_site(scene, onto)
        if a_site and b_site and a_site["plan"] == b_site["plan"]:
            continue
        out.append({"kind": "rooms_overlap_when_placed",
                    "rooms": [other, onto], "via": via,
                    "names": [_name(rooms, other), _name(rooms, onto)]})
    return out


def _embedding_rows(scene, rooms, disagreeing=frozenset()):
    """Lay out each connected component once, from its smallest id."""
    out = []
    for _start, layout in _walks(scene, rooms):
        out += _collision_rows(scene, rooms, layout, disagreeing)
    return out


def layout_index(scene: dict) -> dict:
    """The whole check's walks of the scene, as it walks them (`_walks`),
    read ONCE by a caller that tries one new room in many places
    (`leaf_rows`): for each walk its start, the offset of each room it
    placed and the cells each holds, the order it laid rooms out in, and
    each collision with the cells the colliding room would have taken; and
    the rows those walks hold, as keys, so a row a new room brings can be
    told from one already standing."""
    rooms = _rooms(scene)
    bearing_rows = _bearing_rows(rooms)
    disagreeing = frozenset(frozenset(r["rooms"]) for r in bearing_rows)
    walks, keys = [], set()
    for start, layout in _walks(scene, rooms):
        occupied = {}
        for room_id, (ox, oy) in layout["offsets"].items():
            for x, y in room_grid(scene, room_id).cells:
                occupied.setdefault((x + ox, y + oy), room_id)
        blocked = []
        for (other, onto, via), (bearing, (ox, oy)) in zip(layout["collisions"],
                                                           layout["blocked"]):
            blocked.append((other, onto, via, bearing,
                            {(x + ox, y + oy) for x, y in room_grid(scene, other).cells}))
        walks.append({"start": start, "offsets": dict(layout["offsets"]),
                      "occupied": occupied, "blocked": blocked,
                      "rank": {rid: i for i, rid in enumerate(layout["expanded"])},
                      "reach": set(layout["offsets"]) | {other for other, _onto, _via
                                                         in layout["collisions"]}})
        keys.update(_row_key(row) for row in
                    _collision_rows(scene, rooms, layout, disagreeing))
    return {"scene": scene, "walks": walks, "keys": keys,
            "disagreeing": disagreeing, "from_host": {}}


def _leaf_in_walk(scene, rooms, room_id, host, toward, walk, first, disagreeing):
    """The rows one walk holds about `room_id`, a leaf on `host`, laid beside
    the host where that walk put it: every room it lands on, and every later
    collision whose room it now meets first. `first` is a walk that lays it
    out before any other room (it starts there); otherwise it is laid out
    with the host's other neighbours, in the walk's order."""
    from world.site_plan import room_site
    at = walk["offsets"].get(host)
    laid = _laid_beside(scene, host, room_id, at) if at is not None else None
    if laid is None:
        return []
    cells = set(laid[1])
    site = room_site(scene, room_id)

    def one_plan(other):
        other_site = room_site(scene, other)
        return bool(site and other_site and site["plan"] == other_site["plan"])

    def row(a, b, via):
        return {"kind": "rooms_overlap_when_placed", "rooms": [a, b], "via": via,
                "names": [_name(rooms, a), _name(rooms, b)]}

    # A room it lands on collides with it, whichever of the two the walk
    # reaches first: either way a row names it.
    out = [row(room_id, onto, host)
           for onto in sorted({walk["occupied"][c] for c in cells if c in walk["occupied"]})
           if not one_plan(onto)]
    # A collision names the FIRST room in sorted order of those its room
    # would land on (`layout_rooms`), so a room tried after this one is laid
    # and landing on it as well now names it, when it sorts before the
    # room the collision named.
    rank = walk["rank"]
    for other, onto, via, bearing, would in walk["blocked"]:
        if not (cells & would) or not room_id < onto:
            continue
        if not first and not (rank.get(via, -1) > rank.get(host, -1) or (
                via == host and (other, bearing) > (room_id, toward))):
            continue
        if frozenset((other, via)) in disagreeing or one_plan(other):
            continue
        out.append(row(other, room_id, via))
    return out


def leaf_rows(scene: dict, room_id, host, index=None):
    """The whole check's VERDICT on `scene` -- the scene `index` was made of
    (`layout_index`) with ONE room more, `room_id`, joined to it by one
    doorway onto `host` -- read off the index's walks, or None when they
    cannot say and only the whole check can.

    A VERDICT, NOT THE CHECK'S ROWS. What comes back is None or a list, and
    the list holds a row not about the room's own interior (`row["room"] !=
    room_id`) exactly when the whole check holds one the index's scene does
    not. Its rows are the walks' evidence for that verdict -- a collision as
    the new room meets it, a standing collision as the room's own walk
    re-reports it -- and may name a pair the other way round, or by another
    room, or leave one of the check's rows out: on 1,184 judged trials of
    random towns the two sets of rows differed on 326, and the verdict on
    none (round two's review, 2026-10-09). A caller that wants the check's
    own rows runs the check.

    A LEAF ADDS ITSELF AND NOTHING ELSE, BUT ONLY WHERE THE WALK SAYS SO. Its
    own walls and doorways and the host's doorway onto it are rows about it;
    its bearing pair with the host is one more. Where the rooms land, the
    check's walks decide (`_walks`: each connected part from its smallest id
    nothing earlier reached), and there are three cases:
    - THE HOST'S WALK STARTS BEFORE IT, or at the host itself: the leaf is
      laid beside the host as that walk lays the host's other neighbours out
      -- or first of all, the host's walk then being its own shifted by one
      room -- and every room it lands on, and every LATER collision that now
      lands on it first, refuses it, as a row naming it. Each walk that
      re-lays the host does the same. Nothing else moves: a leaf leads
      nowhere. (Laid out first, it also runs ahead of every walk that started
      between it and the host; where one of those started from a room the
      host's walk reaches, that walk would not run at all: None.)
    - IT SORTS BEFORE A HOST'S WALK THAT STARTS ELSEWHERE, OR THE HOST STANDS
      IN NO WALK (it collided where it was reached): the leaf starts a walk of
      its own, and through the host re-lays the host's whole part in another
      order, which can report a standing collision afresh -- reversed, or via
      another room. That re-laying is the host's own walk shifted by one
      room, the same for every wall and every shape the leaf could take, so
      a standing collision it re-reports refuses all of them, its rows the
      re-reported ones (`from_host`, read once per host). When it re-reports
      none, which rooms the walks after it still reach is not the index's to
      say: None.
    - It is NOT A LEAF -- another room's doorway names it, it names a room
      besides the host, or it stands on a site plan: None.

    Measured on the 2026-10-08 play database: the search that took this for
    exact in every case offered 7 walls of chat 160 turn 13's collided
    corridor and 20 of the three rooms chat 166's town never places, each a
    standing collision re-reported that the designer's own check then held
    against it. For the doorway search (`director_rooms._doorways_that_fit`):
    on chat 166's 33-room turn-22 checkpoint a whole check cost 53 ms, and
    each try of the old search ran two of them beside a merge."""
    from world.site_plan import room_site
    from world.spatial_barriers import effective_adjacent
    rooms = _rooms(scene)
    room_id, host = str(room_id), str(host)
    if room_id not in rooms:
        return []
    if index is None:
        index = layout_index(dict(scene, rooms={rid: room for rid, room in rooms.items()
                                                 if rid != room_id}))
    ways = {str(e["to"]) for e in effective_adjacent(scene, room_id)
            if isinstance(e, dict) and e.get("to")}
    if ways != {host} or host not in rooms or room_site(scene, room_id):
        return None
    near = {rid: rooms[rid] for rid in (room_id, host)}
    rows = [row for row in _wall_rows(scene, near)
            if row.get("room") == room_id
            or f"door:{room_id}" in (row.get("openings") or ())]
    rows += _bearing_rows(near)
    toward = next((bearing for other, bearing in _beared_neighbours(scene, host, rooms)
                   if other == room_id), None)
    if toward is None:
        return rows                         # not laid out: it lands on nothing
    walks = index["walks"]
    first = next((i for i, walk in enumerate(walks) if host in walk["offsets"]), None)
    if first is None or (room_id < walks[first]["start"] != host):
        known = index["from_host"]
        if host not in known:
            base = index["scene"]
            known[host] = [row for row in _collision_rows(
                base, _rooms(base), layout_rooms(base, host), index["disagreeing"])
                if _row_key(row) not in index["keys"]]
        return rows + known[host] if known[host] else None
    leads = room_id < walks[first]["start"]
    if leads and any(room_id < walk["start"] < host and walk["start"] in walks[first]["reach"]
                     for walk in walks):
        # Laid out first, it takes the host's walk ahead of one that ran
        # before it, from a room the host's walk reaches: that walk would not
        # run, and what only it reached would be walked again from elsewhere.
        return None
    for i, walk in enumerate(walks[first:], start=first):
        if host in walk["offsets"]:
            rows += _leaf_in_walk(scene, rooms, room_id, host, toward, walk,
                                  leads and i == first, index["disagreeing"])
    return rows


def layout_row_key(row) -> tuple:
    """A row as a comparable key -- what `room_layout_lint`'s `prev_scene`
    compares, for a caller comparing rows itself: the whole row, or for a
    collision only its pair while `LAYOUT_COLLISIONS_COMPARED_BY_PAIR` is
    on."""
    return _row_key(row)


# ---------------------------------------------------------------------------
# The entry point
# ---------------------------------------------------------------------------

#: THE OWNER'S, NOT YET ANSWERED (round one's review, 2026-10-08): whether a
#: collision found again is the SAME collision when it names the same two
#: rooms -- either way round, and laid out through any room -- or, as today,
#: only when the whole row is the same. A room added where the walks start
#: anew (its id sorts first, or its host is a room the walk could not place)
#: re-lays its part of the world in another order, and a collision the world
#: already holds comes back reversed or via another room: a row about two
#: rooms the draft does not hold, which the designer cannot clear and the
#: commit's once-told warning reports as new (1 of 33 recorded final drafts
#: of 2026-10-08: chat 165 turn 1). On, every comparison the check makes --
#: the commit's (`prev_scene`), the designer's (`director_rooms._Reading`),
#: the doorway search's and `leaf_rows`' -- keys a collision by its pair
#: alone. A walk laid in another order can also move a standing collision
#: onto another pair, which the pair does not catch. Off, the whole row.
LAYOUT_COLLISIONS_COMPARED_BY_PAIR = False


def _row_key(row):
    if LAYOUT_COLLISIONS_COMPARED_BY_PAIR and row.get("kind") == "rooms_overlap_when_placed":
        return (("kind", "rooms_overlap_when_placed"),
                ("pair", tuple(sorted(str(rid) for rid in row.get("rooms") or ()))))
    return tuple(sorted((k, str(v)) for k, v in row.items()))


def room_layout_lint(scene: dict, prev_scene: dict = None) -> list:
    """Every layout row the scene holds, or -- with `prev_scene` -- only the
    rows that were not already standing there, which is how the commit
    reports a contradiction the beat it APPEARS rather than every beat it
    stands (`contradictory_sight_edges`' rule). `prev_scene=None` asks for
    everything, which is what the Room's `inspect_contradictions` wants.
    """
    rooms = _rooms(scene)
    rows = []
    rows += _extent_rows(scene, rooms)
    rows += _shape_rows(scene, rooms)
    rows += _wall_rows(scene, rooms)
    bearing_rows = _bearing_rows(rooms)
    rows += bearing_rows
    rows += _embedding_rows(scene, rooms, frozenset(
        frozenset(r["rooms"]) for r in bearing_rows))
    from world.site_plan import site_overlaps
    rows += [{"kind": "site_plan_overlap", "plan": plan, "level": level,
              "rooms": [a, b], "names": [_name(rooms, a), _name(rooms, b)]}
             for plan, level, a, b in site_overlaps(scene)]
    if prev_scene is not None:
        standing = {_row_key(r) for r in room_layout_lint(prev_scene)}
        rows = [r for r in rows if _row_key(r) not in standing]
    return rows


def layout_warning(row) -> str:
    """One row as the sentence the commit's warning list carries."""
    kind = row.get("kind")
    if kind == "reciprocal_bearing_disagrees":
        a, b = row["names"]
        fa, fb = row["dirs"]
        return (f"{a!r} says {b!r} lies {fa}, and {b!r} says {a!r} lies {fb}; "
                f"the two bearings are not opposites, so the doorway has no "
                f"one place. Redeclare the edge from both sides with "
                f"opposite bearings.")
    if kind == "rooms_overlap_when_placed":
        a, b = row["names"]
        return (f"Placing the rooms by their bearings puts {a!r} on top of "
                f"{b!r} (reached through {row['via']!r}); this set of "
                f"bearings cannot be drawn on one plane. One of the bearings "
                f"is wrong, or a room is missing between them.")
    if kind == "site_plan_overlap":
        a, b = row["names"]
        return (f"On the site plan {row.get('plan')!r}, storey {row.get('level')}, "
                f"{a!r} and {b!r} stand on the same ground; move one, or "
                f"shrink it, so the plan holds together.")
    if kind == "openings_overlap":
        return (f"Room {row['room']!r}: two doorways on the {row['wall']} wall "
                f"({', '.join(row['openings'])}) are placed on the same cells; "
                f"give the wall an extent that holds both, or move one.")
    if kind == "wall_overfull":
        at = f" at {row['height']} height" if row.get("height") else ""
        return (f"Room {row['room']!r}: the {row['wall']} wall's anchors{at} "
                f"need {row['needs']} paces and the wall has {row['holds']}; "
                f"the extent cannot hold them.")
    if kind == "corner_in_round_room":
        return (f"Room {row['room']!r} is round and carries corner parts "
                f"({', '.join(row['corners'])}); a round room has no corner.")
    if kind == "l_part_redundant":
        return (f"Room {row['room']!r}: the {row['part']} part lies within "
                f"the {row['within']} part, so the shape is a rectangle, "
                f"not an L.")
    if kind == "parts_disconnected":
        pieces = "; ".join(", ".join(piece) for piece in row.get("pieces") or [])
        return (f"Room {row['room']!r}: its parts stand apart ({pieces}) and "
                f"do not make one floor; move a part until the pieces touch, "
                f"or make them two rooms.")
    if kind == "shape_disconnected":
        return (f"Room {row['room']!r}: its {row['shape']} shape is not one "
                f"connected floor.")
    if kind == "size_disagrees_with_extent":
        return (f"Room {row['room']!r} is written size {row['size']!r} and "
                f"extent {row['extent']['w']}x{row['extent']['d']} paces, "
                f"which is {row['measured']!r} floor; the extent decides, "
                f"and the size word should agree with it.")
    if kind == "extent_unreadable":
        return (f"Room {row['room']!r}: extent {row['extent']!r} is not "
                f"{{w, d}} in paces and was ignored.")
    return f"layout: {row!r}"


__all__ = ["LAYOUT_LINT_KINDS", "layout_index", "layout_row_key", "layout_rooms",
           "layout_warning", "leaf_rows", "room_layout_lint", "wall_loads"]
