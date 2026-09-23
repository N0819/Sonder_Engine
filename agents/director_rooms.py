"""The prose contract's room designer: a tool-using agent that designs places.

A room here is not a formatting job. The designer reads the Director's prose,
studies the geometry around the place, lays the room out in pieces -- its
shape and extent in paces, its doorways on the walls that face the rooms they
join, its fixtures with their size and height, its light, surface, sound and
exposure -- then LOOKS at what it built on the engine's own cell grid, runs the
engine's own layout check, and refines until the room is detailed, true to
the prose, and geometrically sound. The owner's ruling (2026-09-17) is the
reason for the shape: a one-shot JSON answer gets one attempt and cannot be
told it was wrong; a tool loop drafts in pieces and asks the engine to check
what it has before it commits.

It runs BESIDE the encoder (`director_prose.run`), on the Writers' Room loop
protocol (`agents/story_planner.run_planner`): every step the model returns
`{"calls": [{"tool", "args"}], "done"}`, code runs the calls, and the results
come back in the next step's transcript. Its work is two kinds of place:

- a PLANNED room the beat enters (`develop`): the Writers' Room's plan says
  what the room is for and what it joins, and those stay; the designer
  develops everything in it;
- a place the Director INVENTED (`reserved_places`): the Director named it in
  three fields (name, size, shape); the designer builds the rest.

Nothing here commits. `design_rooms` returns the draft as the three room
channels; the prose contract applies it as the beat's first row, through the
same bind/validate/fold every hand's work takes.
"""

from __future__ import annotations

import copy
import json
import time

#: Steps the designer may take, and the wall it may spend. Named per the
#: owner's ask-before-limiting rule: this is a design job and is given room
#: to iterate; on either cap the draft it has is what is kept.
MAX_ROOM_STEPS = 8
MAX_ROOM_SECONDS = 150.0
#: Tool calls honoured per step.
MAX_ROOM_CALLS_PER_STEP = 6
#: Characters of one tool result shown back, and of the transcript overall.
ROOM_RESULT_CHARS = 6_000
ROOM_TRANSCRIPT_CHARS = 30_000

#: The designer's tools, as the manifest its sheet shows it.
ROOM_TOOLS = {
    "inspect_rooms": {
        "args": {"room_ids": "list of room ids"},
        "does": "The standing geometry of rooms already in the world: name, "
                "description, size, extent, shape, doorways with their bearing "
                "and barrier, fixtures, and the cell map. Look at the rooms "
                "your place joins before you place its doors.",
    },
    "draft_room": {
        "args": {"room_id": "string", "room": "a partial room record in the "
                 "rooms shape below"},
        "does": "Build or change one room of your draft. Fields MERGE across "
                "calls: anchors merge by anchor id, adjacent by `to`, anything "
                "else is replaced. Draft in pieces -- geometry, then doorways, "
                "then fixtures, then the rest.",
    },
    "view_room": {
        "args": {"room_id": "string"},
        "does": "Your draft merged into the world and drawn on the engine's "
                "own cell grid, north at the top: every cell of the floor, every "
                "doorway, every fixture where the engine actually put it, and "
                "how it read each fixture's footprint and height. Look before "
                "you submit.",
    },
    "check": {
        "args": {},
        "does": "The engine's layout check over your draft merged into the "
                "world: every geometric contradiction it introduces, and any "
                "room you owe that is not drafted yet.",
    },
    "submit": {
        "args": {},
        "does": "Finish. Submit when the rooms are complete and the check is "
                "clean.",
    },
}


def _merge_room(base, piece):
    out = dict(base or {})
    for key, value in (piece or {}).items():
        if key == "anchors" and isinstance(value, dict):
            anchors = dict(out.get("anchors") or {})
            for aid, anchor in value.items():
                if isinstance(anchor, dict) and isinstance(anchors.get(aid), dict):
                    anchors[aid] = dict(anchors[aid], **anchor)
                else:
                    anchors[aid] = anchor
            out["anchors"] = anchors
        elif key == "adjacent" and isinstance(value, list):
            edges = {str((e or {}).get("to")): e for e in (out.get("adjacent") or [])
                     if isinstance(e, dict) and e.get("to")}
            for edge in value:
                if isinstance(edge, dict) and edge.get("to"):
                    to = str(edge["to"])
                    edges[to] = dict(edges.get(to) or {}, **edge)
            out["adjacent"] = list(edges.values())
        else:
            out[key] = value
    return out


def _merged(scene, draft):
    from world.spatial import merge_scene_with_diff
    rooms = {rid: room for rid, room in (draft.get("rooms") or {}).items()}
    diff = {"rooms": copy.deepcopy(rooms)} if rooms else {}
    for key in ("remove_rooms", "remove_adjacent"):
        if draft.get(key):
            diff[key] = copy.deepcopy(draft[key])
    return merge_scene_with_diff(copy.deepcopy(scene or {}), diff) if diff else copy.deepcopy(scene or {})


def render_room(scene, room_id):
    """One room as a floor plan on the engine's grid, north at the top, and
    a legend of what the engine made of every fixture and doorway."""
    from world.spatial import anchor_cells, room_grid
    rooms = (scene or {}).get("rooms") or {}
    room = rooms.get(room_id)
    if not isinstance(room, dict):
        return {"refused": f"no room {room_id!r} in the draft or the world"}
    grid = room_grid(scene, room_id)
    marks, legend = {}, []
    held = {}   # (cell, height) -> the fixture already there
    letters = iter("ABCEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")
    for aid, placed in (anchor_cells(scene, room_id) or {}).items():
        cells = [tuple(c) for c in (placed.get("cells") or [])]
        if str(aid).startswith("door:"):
            mark = "D"
            to = str(aid)[5:]
            legend.append(f"D  doorway to {to} ({(rooms.get(to) or {}).get('name') or to})"
                          f" on the {placed.get('dir') or '?'} side at {cells[:1]}")
        else:
            mark = next(letters, "*")
            legend.append(
                f"{mark}  {aid}: {str(placed.get('desc') or '')[:80]} -- engine read "
                f"footprint {placed.get('footprint')}, height {placed.get('height')}, "
                f"facing {placed.get('dir')}, {len(cells)} cell(s)"
                + ("" if cells else " -- NOT PLACED"))
        height = placed.get("height")
        for cell in cells:
            other = held.get((cell, height))
            if other is not None and other != aid:
                # A collision at the same height: both things cannot stand
                # there. Drawn, never hidden by whichever came last.
                marks[cell] = "!"
                legend.append(f"!  {aid} and {other} both stand on {cell} at "
                              f"height {height}")
            else:
                marks.setdefault(cell, mark)
                held[(cell, height)] = aid
    lines = []
    for y in range(grid.d):
        lines.append("".join(marks.get((x, y)) or ("." if (x, y) in grid.cells else " ")
                             for x in range(grid.w)))
    return {
        "room": room_id,
        "name": room.get("name"),
        "grid": f"{grid.w} x {grid.d} paces, {grid.shape}; north at the top, east "
                "to the right; '.' is floor, blank is outside the shape, '!' is two "
                "fixtures at the same height on one cell",
        "map": lines,
        "legend": legend,
    }


def _inspect(scene, room_ids):
    rooms = (scene or {}).get("rooms") or {}
    out = {}
    for rid in list(room_ids or [])[:6]:
        room = rooms.get(str(rid))
        if not isinstance(room, dict):
            out[str(rid)] = {"refused": "no such room"}
            continue
        view = render_room(scene, str(rid))
        out[str(rid)] = {
            "name": room.get("name"), "desc": str(room.get("desc") or "")[:400],
            "size": room.get("size"), "extent": room.get("extent"),
            "shape": room.get("shape"), "parent_entity": room.get("parent_entity"),
            "adjacent": [{k: e.get(k) for k in ("to", "barrier", "dir", "distance")}
                         for e in room.get("adjacent") or [] if isinstance(e, dict)],
            "map": view.get("map"), "legend": view.get("legend"),
        }
    return out


def _check(scene, draft, owed):
    from world.spatial import layout_warning, room_layout_lint
    try:
        merged = _merged(scene, draft)
        errors = [layout_warning(row) for row in room_layout_lint(merged, prev_scene=scene)]
    except Exception as exc:
        return {"errors": [f"the draft could not be merged into the world: {exc}"]}
    drafted = set((draft.get("rooms") or {}))
    missing = [rid for rid in owed if rid not in drafted]
    unplaced, overlapping = [], []
    try:
        from world.spatial import anchor_cells
        for rid in drafted:
            held = {}
            for aid, placed in (anchor_cells(merged, rid) or {}).items():
                if str(aid).startswith("door:"):
                    continue
                if not placed.get("cells"):
                    unplaced.append(f"{rid}.{aid}")
                for cell in placed.get("cells") or []:
                    key = (tuple(cell), placed.get("height"))
                    if key in held and held[key] != aid:
                        overlapping.append(f"{rid}: {held[key]} and {aid} share "
                                           f"{tuple(cell)} at height {key[1]}")
                    held.setdefault(key, aid)
    except Exception:
        pass
    overlapping = list(dict.fromkeys(overlapping))
    return {"errors": errors, "owed_not_drafted": missing,
            "fixtures_not_placed": unplaced, "fixtures_overlapping": overlapping,
            "clean": not (errors or missing or unplaced or overlapping)}


def _fit(value, limit):
    text = json.dumps(value, ensure_ascii=False, default=str)
    if len(text) <= limit:
        return value
    return {"truncated": text[:limit]}


def _shown(transcript):
    """The transcript, newest kept whole, oldest cut first to fit."""
    shown, total = [], 0
    for entry in reversed(transcript):
        size = len(json.dumps(entry, ensure_ascii=False, default=str))
        if total + size > ROOM_TRANSCRIPT_CHARS and shown:
            shown.append({"step": entry["step"], "tool": entry["tool"],
                          "result": "(earlier result omitted)"})
            continue
        shown.append(entry)
        total += size
    return list(reversed(shown))


def design_rooms(ctx, scene, payload, sheet, owed, call, record=None):
    """Run the designer. `payload` is its standing input (prose, plans,
    reserved places, the spatial slice); `owed` the room ids it must draft;
    `call(system, payload)` one model step. Returns the draft as
    `{rooms, remove_rooms, remove_adjacent}` and fills `record`."""
    record = record if record is not None else {}
    draft = {"rooms": {}, "remove_rooms": [], "remove_adjacent": []}
    transcript = []
    started = time.time()
    stopped = "steps"
    step = 0
    for step in range(1, MAX_ROOM_STEPS + 1):
        if time.time() - started > MAX_ROOM_SECONDS:
            stopped = "wall"
            break
        answer = call(sheet, dict(payload, tools=ROOM_TOOLS, draft=draft,
                                  transcript=_shown(transcript), step=step,
                                  steps_left=MAX_ROOM_STEPS - step)) or {}
        calls = [c for c in (answer.get("calls") or []) if isinstance(c, dict)]
        submitted = False
        for item in calls[:MAX_ROOM_CALLS_PER_STEP]:
            tool, args = str(item.get("tool") or ""), item.get("args") or {}
            args = args if isinstance(args, dict) else {}
            if tool == "draft_room":
                rid = str(args.get("room_id") or "").strip()
                if not rid or not isinstance(args.get("room"), dict):
                    result = {"refused": "draft_room needs room_id and a room object"}
                else:
                    draft["rooms"][rid] = _merge_room(draft["rooms"].get(rid), args["room"])
                    result = {"drafted": rid, "fields": sorted(draft["rooms"][rid])}
            elif tool == "view_room":
                result = render_room(_merged(scene, draft), str(args.get("room_id") or ""))
            elif tool == "inspect_rooms":
                result = _inspect(_merged(scene, draft), args.get("room_ids") or [])
            elif tool == "check":
                result = _check(scene, draft, owed)
            elif tool == "submit":
                result = _check(scene, draft, owed)
                if result.get("clean") or step >= MAX_ROOM_STEPS:
                    submitted = True
                else:
                    # A design is finished when it is right. The problems
                    # come back instead, and the loop goes on.
                    result = dict(result, refused="not submitted: fix these first")
            elif tool in ("remove_rooms", "remove_adjacent") and isinstance(args.get("items"), list):
                draft[tool].extend(args["items"])
                result = {"recorded": tool}
            else:
                result = {"refused": f"unknown tool {tool!r}"}
            transcript.append({"step": step, "tool": tool, "args": args,
                               "result": _fit(result, ROOM_RESULT_CHARS)})
        refused = any((entry.get("result") or {}).get("refused", "").startswith("not submitted")
                      for entry in transcript if entry["step"] == step
                      and isinstance(entry.get("result"), dict))
        if submitted or not calls or (answer.get("done") and not refused):
            stopped = "submitted" if submitted or answer.get("done") else "no_calls"
            break
    final = _check(scene, draft, owed)
    record.update(steps=step, calls=len(transcript), stopped=stopped,
                  seconds=round(time.time() - started, 3), final_check=final)
    return draft
