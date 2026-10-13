"""One storey of a site plan, as the layout lab draws it, for the World Browser.

The owner, reading the shrine of chat 168 (2026-10-12): "perhaps in the in
engine ui should be adjusted to look kind of like the layout lab we made" --
and chose the lab's own plan view, fed from the live scene, over a lighter
touch on the grid. The layout lab (`tools/layout_lab/page.html`, `drawPlan`)
draws one storey of a solve: each room filled by what it is for, walls broken
where its doorways are, a window a thin line in its wall, a stair by its
shape, fixtures by their kind, the ground and its ways about the house, and
the storey beneath as a ghost. This is that drawing's data, read off the
world the way every other view reads it -- the scene through its solved
plans (`structure.apply_solved_plans`), each room's cells on its plan
(`site_plan.site_cells`), every doorway and window where the engine places it
(`anchor_cells`) -- so the plan cannot show a wall the cast is not judged by.
Pure over the scene and the plans; it writes nothing.

    storey_plan(scene, plan, level=None, specs=None) -> {
        plan, level, levels: [storey, ...],
        rooms: [{id, name, level, purpose, ground, cells, rects}],
        doors: [{a, b, cells, side, barrier, outside}],
        windows: [{room, cells, side, name}],
        stairs: [{room, kind, up, down, name, rects}],
        fixtures: [{room, id, name, kind, rect, height, front}],
        bodies: [{name, room, cell}],
        below: [{id, rects}],
    }

Cells and rectangles are on the plan (paces; x east, y south), so the
drawing lays every room on one frame, as the lab does.
"""
from __future__ import annotations

from typing import Optional

#: The ground's own kinds, as the layout tier's first call sorts them
#: (`layout_bridge.GROUND_IS`): what a plan draws as grass and as gravel.
_GROUND_FILL = {"open": "ground", "feature": "ground", "way": "way"}


def _runs(cells) -> list:
    """Cells as rectangles: each row's runs, merged downward while the run
    below matches (the layout lab converter's `_parts`)."""
    rows = {}
    for x, y in cells:
        rows.setdefault(y, []).append(x)
    runs = []
    for y in sorted(rows):
        xs = sorted(rows[y])
        start = prev = xs[0]
        for x in xs[1:] + [None]:
            if x is not None and x == prev + 1:
                prev = x
                continue
            runs.append([start, y, prev - start + 1, 1])
            if x is not None:
                start = prev = x
    merged = []
    for run in runs:
        for m in merged:
            if m[0] == run[0] and m[2] == run[2] and m[1] + m[3] == run[1]:
                m[3] += 1
                break
        else:
            merged.append(list(run))
    return [{"x": x, "y": y, "w": w, "d": d} for x, y, w, d in merged]


def _plan_of(specs, rid) -> dict:
    entry = (specs or {}).get(rid)
    spec = entry[1] if isinstance(entry, tuple) and len(entry) > 1 else entry
    return spec if isinstance(spec, dict) else {}


def room_look(scene, rid, spec=None) -> dict:
    """What the lab's drawing needs of one room beyond its cells: what it is
    for (``purpose``: the solve's record; a stair hall the layout tier made is
    a ``stair``, open ground its kind of ground), whether it is open
    ``ground``, and for a stair hall its ``stair`` (``kind``, ``up``,
    ``down``). The ONE reading the storey plan and the room editor draw by
    (the owner, 2026-10-12: the editor should look like the lab too), so the
    two cannot fill a room differently. `spec` is the room's planned
    registry record, when it has one."""
    from world.landscape import OPEN_GROUND, declared_ground
    from world.spatial import effective_adjacent, normalize_vertical
    from world.structure import LAYOUT_MADE_KEY
    room = ((scene or {}).get("rooms") or {}).get(rid)
    room = room if isinstance(room, dict) else {}
    spec = spec if isinstance(spec, dict) else {}
    record = spec.get("layout") if isinstance(spec.get("layout"), dict) else {}
    ground = declared_ground(scene, rid) in OPEN_GROUND
    purpose = str(record.get("purpose") or "")
    made = bool(spec.get(LAYOUT_MADE_KEY) or room.get(LAYOUT_MADE_KEY))
    if made:
        purpose = "stair"
    if ground:
        purpose = _GROUND_FILL.get(str(record.get("grounds") or ""), "ground")
    out = {"purpose": purpose, "ground": ground}
    if made:
        ways = {normalize_vertical(e.get("vertical")) for e in effective_adjacent(scene, rid)
                if isinstance(e, dict) and e.get("to")}
        out["stair"] = {"kind": str(spec.get("stair_kind") or ""),
                        "up": "up" in ways, "down": "down" in ways}
    return out


def fixture_kinds(scene, rid, spec=None) -> dict:
    """``{anchor id: kind}`` -- what each fixture of the room is, as the
    solve recorded it (the planned record's anchors), else as the room's own
    anchor says; a fixture with neither has no kind and is drawn as a plain
    body (`wbPlanFixture`)."""
    spec = spec if isinstance(spec, dict) else {}
    planned = spec.get("anchors") if isinstance(spec.get("anchors"), dict) else {}
    room = ((scene or {}).get("rooms") or {}).get(rid)
    authored = room.get("anchors") if isinstance(room, dict) and isinstance(room.get("anchors"), dict) else {}
    out = {}
    for aid in set(planned) | set(authored):
        kind = str((planned.get(aid) or {}).get("kind") or (authored.get(aid) or {}).get("kind") or "")
        if kind:
            out[str(aid)] = kind
    return out


def plan_scene(cid, scene, plan) -> dict:
    """The live scene with every planned room that stands on `plan` beneath
    it (`structure.composed_scene`), read through the solved plans: the whole
    building as the plan holds it, so a storey is drawn with the rooms nobody
    has come near yet, as the layout lab draws the whole solve. A room the
    live scene holds is drawn as the scene holds it."""
    import copy
    from world.site_plan import normalize_site
    from world.structure import (apply_solved_plans, composed_scene, planned_anchors,
                                 planned_geometry, registry_rows)
    skeleton = {}
    for uid, entry in registry_rows(cid).items():
        planned = entry["planned"]
        if not isinstance(planned, dict):
            continue
        site = normalize_site(planned.get("site"))
        if not site or site["plan"] != plan:
            continue
        skeleton[uid] = {"name": str(entry["name"] or uid), "planned": True,
                         "adjacent": [dict(e) for e in planned.get("adjacent") or ()
                                      if isinstance(e, dict) and e.get("to")],
                         **planned_geometry(planned), **planned_anchors(planned)}
    out = composed_scene({"rooms": skeleton}, copy.deepcopy(scene or {}))
    apply_solved_plans(cid, out)
    return out


def plan_levels(scene, plan) -> list:
    """The storeys the scene holds on `plan`, lowest first."""
    from world.site_plan import site_plans
    return sorted(int(lv) for lv in (site_plans(scene).get(plan) or {}))


def storey_plan(scene, plan, level: Optional[int] = None, specs=None,
                live=None) -> Optional[dict]:
    """The drawing data for storey `level` of site plan `plan` (module
    docstring); the ground storey, else the highest, when `level` is not one
    the plan holds. None when no room of the scene stands on `plan`.
    `specs` is the registry's planned rooms (`structure._planned_specs`),
    read for what the solve recorded of each: what it took a room for, a
    stair's shape, a fixture's kind. `live` is the ids of the rooms the
    live scene holds, when `scene` is `plan_scene`'s: every other room is
    marked `planned`, a room nobody has come near yet."""
    from world.site_plan import room_level, room_site, site_cells, site_plans
    from world.spatial import (anchor_cells, body_cell, effective_adjacent,
                               normalize_barrier, normalize_vertical, room_of,
                               scene_names_body)
    from world.structure import LAYOUT_MADE_KEY
    from world.landscape import OPEN_GROUND, declared_ground

    by_level = site_plans(scene).get(plan) or {}
    if not by_level:
        return None
    levels = sorted(int(lv) for lv in by_level)
    if level not in levels:
        level = 0 if 0 in levels else levels[-1]
    rooms_ = (scene or {}).get("rooms") or {}
    here = [str(rid) for rid in by_level.get(level) or ()]
    on_storey = set(here)
    out = {"plan": plan, "level": level, "levels": levels, "rooms": [], "doors": [],
           "windows": [], "stairs": [], "fixtures": [], "bodies": [], "below": []}
    seen_doors = set()
    for rid in here:
        room = rooms_.get(rid) or {}
        spec = _plan_of(specs, rid)
        record = spec.get("layout") if isinstance(spec.get("layout"), dict) else {}
        site = room_site(scene, rid) or {"x": 0, "y": 0}
        cells = sorted(site_cells(scene, rid))
        look = room_look(scene, rid, spec)
        ground, purpose = look["ground"], look["purpose"]
        out["rooms"].append({"id": rid, "name": str(room.get("name") or rid),
                             "level": room_level(scene, rid), "purpose": purpose,
                             "ground": ground, "cells": [list(c) for c in cells],
                             "rects": _runs(cells),
                             "planned": live is not None and rid not in live})
        placed = anchor_cells(scene, rid) or {}
        ox, oy = site["x"], site["y"]
        # DOORWAYS AND WINDOWS IN THE WALL: where the engine places each
        # (`anchor_cells`), moved onto the plan
        edges = {str(e.get("to")): e for e in effective_adjacent(scene, rid)
                 if isinstance(e, dict) and e.get("to")}
        for aid, rec in placed.items():
            if not rec.get("implicit"):
                continue
            wall = rec.get("dir")
            cells_on = [[c[0] + ox, c[1] + oy] for c in rec.get("cells") or ()]
            if wall not in ("n", "e", "s", "w") or not cells_on:
                continue
            if str(aid).startswith("window:"):
                out["windows"].append({"room": rid, "cells": cells_on, "side": wall,
                                       "name": str(rec.get("desc") or "")})
                continue
            if not str(aid).startswith("door:"):
                continue
            to = str(aid)[5:]
            edge = edges.get(to) or {}
            if normalize_vertical(edge.get("vertical")):
                continue                      # a way up or down has no wall
            barrier = normalize_barrier(edge.get("barrier"))
            if barrier == "wall":
                continue
            if barrier in ("window", "one_way_window"):
                out["windows"].append({"room": rid, "cells": cells_on, "side": wall,
                                       "name": str(edge.get("name") or "")})
                continue
            key = frozenset((rid, to))
            if key in seen_doors and to in on_storey:
                continue
            seen_doors.add(key)
            out["doors"].append({"a": rid, "b": to, "cells": cells_on, "side": wall,
                                 "barrier": barrier, "name": str(edge.get("name") or ""),
                                 "outside": to not in on_storey})
        # THE STAIR, by its shape, in its hall
        if look.get("stair"):
            out["stairs"].append({"room": rid, **look["stair"],
                                  "name": str(room.get("name") or rid),
                                  "rects": _runs(cells)})
        # FIXTURES by their kind where the solve recorded one
        kinds = fixture_kinds(scene, rid, spec)
        for aid, rec in placed.items():
            if rec.get("implicit") or not rec.get("cells"):
                continue
            xs = [c[0] + ox for c in rec["cells"]]
            ys = [c[1] + oy for c in rec["cells"]]
            out["fixtures"].append({
                "room": rid, "id": str(aid), "name": str(rec.get("desc") or aid),
                "kind": kinds.get(str(aid), ""),
                "rect": {"x": min(xs), "y": min(ys), "w": max(xs) - min(xs) + 1,
                         "d": max(ys) - min(ys) + 1},
                "height": rec.get("height"), "front": rec.get("dir")})
    # WHO STANDS WHERE, on the plan
    for name, where in sorted(((scene or {}).get("positions") or {}).items(), key=str):
        rid = room_of(scene, name)
        if rid not in on_storey or not scene_names_body(scene, str(name)):
            continue                    # a thing a position places is no body
        cell = body_cell(scene, name)
        site = room_site(scene, rid) or {"x": 0, "y": 0}
        if cell is None:
            continue
        out["bodies"].append({"name": str(name), "room": rid,
                              "cell": [cell[0] + site["x"], cell[1] + site["y"]]})
    # THE STOREY BENEATH, as a ghost
    for rid in by_level.get(level - 1) or ():
        out["below"].append({"id": str(rid), "rects": _runs(sorted(site_cells(scene, rid)))})
    return out
