#!/usr/bin/env python3
"""A layout lab plan as engine rooms on a site plan (`world/site_plan`).

The layout lab (branch `layout-solver-test`) solves a place's description
into storeys of rectangular rooms, stair halls, doorways, fixtures and the
grounds around the buildings, all on one frame of paces. This writes that
frame into the engine's own vocabulary, so a solved place can be opened in
the World Browser and played:

* each room at its storey, `extent` its rectangle, `site` its corner on the
  plan and its floor's height (`level` x `STOREY_M`);
* each fixture, zone and window an anchor pinned to its cell (a zone and a
  way keep a lane: they are floor, not furniture);
* each doorway an edge on both sides, bearing and offset along the wall;
* each stair a vertical edge between its halls on consecutive storeys;
* the grounds ONE open-air room whose cells are the site less every
  ground-floor footprint -- the garden round the house, the house in its
  hole -- carrying the features and the ways as anchors.

Read-only on its input; it writes JSON and touches no database.

    python tools/site_plan_from_layout.py LAYOUT.json --plan shrine > rooms.json

LAYOUT.json is a lab result (`{"layout": ...}`) or a bare layout.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from world.site_plan import STOREY_M  # noqa: E402
from world.spatial import normalize_barrier  # noqa: E402

_UNIT = {"n": (0, -1), "s": (0, 1), "e": (1, 0), "w": (-1, 0)}
_OPPOSITE = {"n": "s", "s": "n", "e": "w", "w": "e"}
GROUNDS = "grounds"


def room_id(lab_id) -> str:
    """An engine room id for a lab id: a stair hall `x@-1` is `x_m1`."""
    rid = str(lab_id)
    if "@" in rid:
        base, level = rid.split("@", 1)
        rid = f"{base}_{level.replace('-', 'm')}"
    return re.sub(r"[^a-z0-9_]+", "_", rid.casefold()).strip("_")


def _rect(r):
    return int(r["x"]), int(r["y"]), int(r["w"]), int(r["d"])


def _cells(rects):
    out = set()
    for r in rects:
        x, y, w, d = _rect(r)
        out.update((cx, cy) for cx in range(x, x + w) for cy in range(y, y + d))
    return out


def _parts(cells, ox, oy):
    """Cells as rectangles: each row's runs, merged downward while the run
    below matches -- a composite room's parts, at room-local cells."""
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
    return [{"w": w, "d": d, "at": [x - ox, y - oy]} for x, y, w, d in merged]


def _footprint(w, d):
    if max(w, d) >= 3 and min(w, d) == 1:
        return "run"
    if w * d >= 4:
        return "large"
    return "small" if w * d > 1 else "point"


def _offset(rect, side, cell):
    """Where along its wall a one-cell doorway stands, as the fraction
    `normalize_offset` reads: from the wall's start (west for a north or
    south wall, north for an east or west one) over the places it leaves."""
    x, y, w, d = rect
    if side in ("n", "s"):
        return round((cell[0] - x) / max(1, w - 1), 4)
    return round((cell[1] - y) / max(1, d - 1), 4)


def _barrier(kind):
    word = normalize_barrier(kind)
    text = str(kind or "").casefold()
    if word == "wall":
        # an unread word is a doorway someone drew, not a wall
        return "warded_door" if "ward" in text else (
            "closed_door" if "door" in text else "open")
    return word


def rooms_from_layout(layout: dict, plan: str, region: str = "") -> dict:
    """`{room id: room}` for every room of a lab layout on one site plan."""
    region = region or plan
    names = layout.get("names") or {}
    purposes = layout.get("purposes") or {}
    rooms, rects = {}, {}
    for lv_key, floor in (layout.get("floors") or {}).items():
        level = int(lv_key)
        for lab_id, parts in floor.items():
            if not parts:
                continue
            rid = room_id(lab_id)
            x, y, w, d = _rect(parts[0])
            rects[lab_id] = (x, y, w, d)
            purpose = purposes.get(lab_id) or ""
            name = names.get(lab_id) or lab_id
            room = {"name": name,
                    "desc": f"{name}{', the ' + purpose if purpose and purpose not in name.casefold() else ''}.",
                    "level": level, "extent": {"w": w, "d": d}, "shape": "rectangle",
                    "exposure": "enclosed", "region": region, "adjacent": [], "anchors": {},
                    "site": {"plan": plan, "x": x, "y": y, "elev_m": level * STOREY_M}}
            if len(parts) > 1:
                cells = _cells(parts)
                bx, by = min(c[0] for c in cells), min(c[1] for c in cells)
                room.update(shape="composite", parts=_parts(cells, bx, by),
                            extent={"w": max(c[0] for c in cells) - bx + 1,
                                    "d": max(c[1] for c in cells) - by + 1})
                room["site"].update(x=bx, y=by)
                rects[lab_id] = (bx, by, room["extent"]["w"], room["extent"]["d"])
            rooms[rid] = room

    def anchor(lab_room, aid, desc, r, height=None, lane=False):
        rid = room_id(lab_room)
        if rid not in rooms:
            return
        ox, oy = rooms[rid]["site"]["x"], rooms[rid]["site"]["y"]
        x, y, w, d = _rect(r)
        rec = {"desc": desc, "cell": [x - ox, y - oy], "footprint": _footprint(w, d)}
        if height:
            rec["height"] = height
        if lane:
            rec["lane"] = True
        rooms[rid]["anchors"][re.sub(r"[^a-z0-9_]+", "_", str(aid).casefold())] = rec

    for lab_room, fixtures in (layout.get("fixtures") or {}).items():
        for f in fixtures:
            if f.get("rect"):
                anchor(lab_room, f.get("id") or f.get("name"), f.get("name") or f.get("kind"),
                       f["rect"], f.get("height"))
    for lab_room, zones in (layout.get("zones") or {}).items():
        for z in zones:
            anchor(lab_room, z.get("id"), z.get("name"), z["rect"], lane=True)

    # the grounds: the site less every ground-floor footprint
    site = layout.get("site")
    if site:
        footprint = set()
        for levels in (layout.get("outlines") or {}).values():
            if levels.get("0"):
                footprint |= _cells([levels["0"]])
        cells = _cells([site]) - footprint
        if cells:
            sx, sy, sw, sd = _rect(site)
            rooms[GROUNDS] = {
                "name": f"{layout.get('name') or plan} grounds",
                "desc": "Open ground round the buildings.", "level": 0,
                "extent": {"w": sw, "d": sd}, "shape": "composite",
                "parts": _parts(cells, sx, sy), "exposure": "open", "region": region,
                "adjacent": [], "anchors": {},
                "site": {"plan": plan, "x": sx, "y": sy, "elev_m": 0.0}}
            rects[GROUNDS] = (sx, sy, sw, sd)
            for f in layout.get("features") or ():
                if f.get("rect"):
                    anchor(GROUNDS, f.get("id"), f.get("name") or f.get("kind"),
                           f["rect"], f.get("height"))
            for wid, way in (layout.get("ways") or {}).items():
                first = (way.get("rects") or [None])[0]
                if first:
                    anchor(GROUNDS, wid, way.get("name") or wid.replace("_", " "),
                           first, lane=True)

    for win in layout.get("windows") or ():
        rect = rects.get(win["room"])
        if rect:
            rid = room_id(win["room"])
            ox, oy = rooms[rid]["site"]["x"], rooms[rid]["site"]["y"]
            rooms[rid]["anchors"][room_id(win["id"])] = {
                "desc": "a window", "dir": win["side"],
                "offset": _offset(rect, win["side"], win["cell"]),
                "footprint": "small", "height": "head"}

    def edge(a, b, side, cell, barrier):
        ra, rb = room_id(a), room_id(b)
        if ra not in rooms or rb not in rooms or ra == rb:
            return
        ux, uy = _UNIT[side]

        def side_of(rid, lab, bearing, at):
            rec = {"to": rb if rid == ra else ra, "barrier": barrier, "dir": bearing}
            if rooms[rid].get("shape") == "composite":
                # a wall of a ring is several walls: pin the doorway's cell
                rec["cell"] = [at[0] - rooms[rid]["site"]["x"], at[1] - rooms[rid]["site"]["y"]]
            else:
                rec["offset"] = _offset(rects[lab], bearing, at)
            return rec

        rooms[ra]["adjacent"].append(side_of(ra, a, side, cell))
        rooms[rb]["adjacent"].append(side_of(rb, b, _OPPOSITE[side], (cell[0] + ux, cell[1] + uy)))

    joined = set()
    for door in layout.get("doors") or ():
        b = GROUNDS if door.get("outside") else door["b"]
        key = frozenset((room_id(door["a"]), room_id(b)))
        if key in joined:
            continue              # one edge per pair of rooms
        joined.add(key)
        edge(door["a"], b, door["side"], door["cell"], _barrier(door.get("kind")))

    for well in layout.get("stairwells") or ():
        halls = {int(k): v for k, v in (well.get("halls") or {}).items()}
        for lo in sorted(halls):
            hi = lo + 1
            if hi in halls and room_id(halls[lo]) in rooms and room_id(halls[hi]) in rooms:
                way = "ladder" if well.get("kind") == "ladder" else "stair"
                rooms[room_id(halls[lo])]["adjacent"].append(
                    {"to": room_id(halls[hi]), "barrier": "open", "vertical": "up", "way": way})
                rooms[room_id(halls[hi])]["adjacent"].append(
                    {"to": room_id(halls[lo]), "barrier": "open", "vertical": "down", "way": way})
    return rooms


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("layout")
    ap.add_argument("--plan", required=True)
    ap.add_argument("--region", default="")
    args = ap.parse_args()
    data = json.load(open(args.layout, encoding="utf-8"))
    layout = data.get("layout") or data
    json.dump(rooms_from_layout(layout, args.plan, args.region), sys.stdout,
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
