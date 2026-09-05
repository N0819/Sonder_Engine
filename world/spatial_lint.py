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
    _UNIT, _door_cells, anchor_cells, normalize_parts, normalize_shape,
    room_grid,
)
from world.spatial_geometry import (
    ROOM_SIZES, normalize_extent, size_from_extent,
)
from world.spatial_orientation import normalize_bearing, opposite_bearing


#: Every row kind this module can produce, so a reader can enumerate them.
LAYOUT_LINT_KINDS = (
    "reciprocal_bearing_disagrees",
    "openings_overlap",
    "wall_overfull",
    "corner_in_round_room",
    "l_part_redundant",
    "shape_disconnected",
    "rooms_overlap_when_placed",
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
        if shape == "l" and len(parts) >= 2:
            grid = room_grid(scene, rid)
            boxes = []
            for part in parts:
                pw, pd = min(part["w"], grid.w), min(part["d"], grid.d)
                x0 = grid.w - pw if part["at"] in ("ne", "se") else 0
                y0 = grid.d - pd if part["at"] in ("se", "sw") else 0
                boxes.append((x0, y0, x0 + pw, y0 + pd, part["at"]))
            for i, a in enumerate(boxes):
                for j, b in enumerate(boxes):
                    if i != j and a[0] >= b[0] and a[1] >= b[1] \
                            and a[2] <= b[2] and a[3] <= b[3]:
                        out.append({"kind": "l_part_redundant", "room": rid,
                                    "part": a[4], "within": b[4]})
                        break
        if shape != "rectangle" or normalize_extent(room.get("extent")):
            grid = room_grid(scene, rid)
            if not _cells_connected(grid.cells):
                out.append({"kind": "shape_disconnected", "room": rid,
                            "shape": shape})
    return out


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


def _wall_rows(scene, rooms):
    """A wall's anchors need more cells than the wall has, or two doorways
    on one wall were placed on the same cells."""
    out = []
    for rid in sorted(rooms):
        grid = room_grid(scene, rid)
        placed = anchor_cells(scene, rid)
        need = {}
        doors = {}
        for aid, rec in placed.items():
            bearing = rec.get("dir")
            if bearing not in _WALLS:
                continue
            if rec["implicit"]:
                doors.setdefault(bearing, []).append((aid, set(rec["cells"])))
                continue
            need[bearing] = need.get(bearing, 0) + len(rec["cells"])
        for bearing, cells in sorted(need.items()):
            have = len(grid.rim(bearing))
            if cells > have:
                out.append({"kind": "wall_overfull", "room": rid,
                            "wall": bearing, "needs": cells, "holds": have})
        for bearing, ways in sorted(doors.items()):
            ways.sort()
            for i, (a_id, a_cells) in enumerate(ways):
                for b_id, b_cells in ways[i + 1:]:
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


def _bearing_rows(rooms):
    out = []
    for a_id in sorted(rooms):
        for edge in (rooms[a_id].get("adjacent") or []):
            if not isinstance(edge, dict) or not edge.get("to"):
                continue
            b_id = str(edge["to"])
            if b_id <= a_id or b_id not in rooms:
                continue                    # one row per pair
            fwd = normalize_bearing(edge.get("dir"))
            back = _declared_dir(rooms, b_id, a_id)
            if fwd and back and opposite_bearing(fwd) != back:
                out.append({"kind": "reciprocal_bearing_disagrees",
                            "rooms": [a_id, b_id], "dirs": [fwd, back],
                            "names": [_name(rooms, a_id), _name(rooms, b_id)]})
    return out


def _beared_neighbours(scene, room_id, rooms):
    """(neighbour, bearing) for every edge of the room with a bearing whose
    barrier is not a wall -- a closed door has geometry too."""
    out = []
    for edge in effective_adjacent(scene, room_id):
        if not isinstance(edge, dict) or not edge.get("to"):
            continue
        if normalize_barrier(edge.get("barrier")) == "wall":
            continue
        bearing = normalize_bearing(edge.get("dir"))
        to_id = str(edge["to"])
        if bearing and to_id in rooms and to_id != str(room_id):
            out.append((to_id, bearing))
    return sorted(out)


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
    """
    rooms = _rooms(scene)
    if str(start) not in rooms:
        return {"offsets": {}, "collisions": []}
    offsets = {str(start): (0, 0)}
    occupied = {}
    for x, y in room_grid(scene, start).cells:
        occupied[(x, y)] = str(start)
    collisions = []
    frontier = [str(start)]
    while frontier:
        nxt = []
        for room_id in frontier:
            ox, oy = offsets[room_id]
            for other, bearing in _beared_neighbours(scene, room_id, rooms):
                if other in offsets:
                    continue
                d1s, b1 = _door_cells(scene, room_id, other)
                d2s, _b2 = _door_cells(scene, other, room_id)
                if not d1s or not d2s or not b1:
                    continue
                ux, uy = _UNIT[b1]
                d1, d2 = d1s[0], d2s[0]
                far = (d1[0] + ux + ux + ox, d1[1] + uy + uy + oy)
                offset = (far[0] - d2[0], far[1] - d2[1])
                cells = [(x + offset[0], y + offset[1])
                         for x, y in room_grid(scene, other).cells]
                hit = sorted({occupied[c] for c in cells if c in occupied})
                if hit:
                    collisions.append((other, hit[0], room_id))
                    continue
                offsets[other] = offset
                for c in cells:
                    occupied[c] = other
                nxt.append(other)
        frontier = sorted(nxt)
    return {"offsets": offsets, "collisions": collisions}


def _embedding_rows(scene, rooms, disagreeing=frozenset()):
    """Lay out each connected component once, from its smallest id. A
    collision across a doorway whose two bearings already disagree is that
    row's consequence, not a second fact, and is not repeated here."""
    out = []
    placed = set()
    for rid in sorted(rooms):
        if rid in placed:
            continue
        layout = layout_rooms(scene, rid)
        placed.update(layout["offsets"])
        for other, onto, via in layout["collisions"]:
            placed.add(other)
            if frozenset((other, via)) in disagreeing:
                continue
            out.append({"kind": "rooms_overlap_when_placed",
                        "rooms": [other, onto], "via": via,
                        "names": [_name(rooms, other), _name(rooms, onto)]})
    return out


# ---------------------------------------------------------------------------
# The entry point
# ---------------------------------------------------------------------------

def _row_key(row):
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
    if kind == "openings_overlap":
        return (f"Room {row['room']!r}: two doorways on the {row['wall']} wall "
                f"({', '.join(row['openings'])}) are placed on the same cells; "
                f"give the wall an extent that holds both, or move one.")
    if kind == "wall_overfull":
        return (f"Room {row['room']!r}: the {row['wall']} wall's anchors need "
                f"{row['needs']} paces and the wall has {row['holds']}; the "
                f"extent cannot hold them.")
    if kind == "corner_in_round_room":
        return (f"Room {row['room']!r} is round and carries corner parts "
                f"({', '.join(row['corners'])}); a round room has no corner.")
    if kind == "l_part_redundant":
        return (f"Room {row['room']!r}: the {row['part']} part lies within "
                f"the {row['within']} part, so the shape is a rectangle, "
                f"not an L.")
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


__all__ = ["LAYOUT_LINT_KINDS", "layout_rooms", "layout_warning",
           "room_layout_lint"]
