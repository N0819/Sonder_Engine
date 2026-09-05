"""The World Browser in a real browser: the tree, the card, walking an exit,
the field editors, the Bodies tab's attire editor, the Raw JSON tab that
keeps the old editors -- and the map editor, gesture by gesture.

Fully mocked at the network boundary. What `node --check` cannot see is the
part worth testing here: that 🌍 opens on Rooms and 👕 on Bodies, that
clicking an exit re-selects the far room in the tree and re-renders the
card, that a room's light chosen from the select is PATCHed and the card
re-renders from the server's answer, that adding an exit sends this room's
full exit list and the far room then shows the doorway, that changing a
garment's state on the Bodies tab sends the WHOLE ledger with every copy of a
spanning garment carrying the new state (never narrowed, never reset), that
the Raw JSON tab still offers the world table for hand repair -- and, since
2026-09-05, that every drag, click-to-create and remove on the map is ONE
write through the route the card uses, with a toast naming what was written,
an Undo that re-issues the previous value, and an arrow key that is the drag
by one cell.
"""

from __future__ import annotations

import copy
import json
import re
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import Page, expect

from test_ui_smoke import BOOTSTRAP, _chat_payload


def _row(rid, name, hops, occupants=(), status="live", holder=None,
         holder_name=None, holder_room=None, region=None, lint=0):
    return {"id": rid, "name": name, "status": status, "holder": holder,
            "hops": hops, "holder_name": holder_name, "holder_room": holder_room,
            "occupants": list(occupants), "region": region, "lint": lint}


VOCAB = {
    "light": ["dark", "dim", "lit", "bright"],
    "size": ["tiny", "small", "medium", "large", "huge", "vast"],
    "exposure": ["open", "sheltered", "enclosed"],
    "barriers": ["bars", "closed_door", "membrane", "one_way_window", "open",
                 "open_door", "separated", "unknown", "wall", "window"],
    "dirs": ["n", "ne", "e", "se", "s", "sw", "w", "nw"],
    "heights": ["floor", "waist", "head", "full"],
    "footprints": ["point", "small", "large", "run"],
    "opacities": ["opaque", "see_through"],
    "shapes": ["rectangle", "round", "l", "composite"],
    "corners": ["ne", "se", "sw", "nw"],
    "part_shapes": ["l", "composite"],
    "walls": ["n", "e", "s", "w"],
    "extent": {"min": 2, "max": 24},
    "light_shapes": ["all_round", "cone"],
    "light_heights": ["floor", "waist", "head", "full"],
    "steadiness": ["steady", "flickering", "failing"],
    "sound_levels": ["faint", "audible", "loud", "deafening"],
    "pose_fields": ["posture", "support", "relative_to", "relation", "constraint", "detail"],
    "postures": ["standing", "sitting", "kneeling", "crouching", "lying"],
    "regions": [{"id": "east_wing", "name": "East Wing", "look": ""}],
    "attire_regions": ["head", "torso", "arms", "hands", "waist", "groin", "legs", "feet"],
    "garment_states": ["worn", "loosened", "open", "removed"],
}

# The size tier's square side, the browser mock's copy of `GRID_SIDE` for the
# derived geometry a PATCH hands back.
TIER_SIDE = {"": 6, "tiny": 3, "small": 4, "medium": 6, "large": 8, "huge": 10, "vast": 12}


def _geometry(record):
    """What the server's `_geometry` would say for a rectangle: the extent's
    box when one stands, else the tier's square; each straight wall's paces."""
    extent = record.get("extent")
    if extent:
        w, d = extent["w"], extent["d"]
        side = (w * d) ** 0.5
        derived = "medium" if side < 7 else "large"
    else:
        w = d = TIER_SIDE[record.get("size") or ""]
        derived = None
    return {"w": w, "d": d, "shape": record.get("shape") or "rectangle",
            "measured": bool(extent), "size_derived": derived,
            "walls": {"n": w, "s": w, "e": d, "w": d}}

# Alice's ledger AS STORED: a kimono spanning torso and legs, recorded once per
# region, and an apron on the torso alone.
KIMONO = {"name": "silk kimono", "state": "worn", "condition": "",
          "covers": ["torso", "legs"]}
ALICE_ATTIRE = {
    "wearing": ["silk kimono", "apron"], "state": ["bare at the head, arms, hands, waist, groin, feet"],
    "regions": {"torso": {"garments": [dict(KIMONO), {"name": "apron", "state": "worn",
                                                        "condition": ""}],
                          "beneath": ""},
                "legs": {"garments": [dict(KIMONO)], "beneath": ""}},
}

INDEX = {
    "frame_id": None,
    "location": "Old Manor",
    "groups": {
        "cast": [_row("kitchen", "Kitchen", 0, ["Alice"], region="east_wing", lint=2),
                 _row("study", "Study", 0, ["Nathan"])],
        "reachable": [_row("hallway", "Hallway", 1, region="east_wing"),
                      _row("console_room", "Console Room", 1, holder="tardis",
                           holder_name="The TARDIS", holder_room="study"),
                      _row("attic", "Attic", 2, status="planned")],
        "unreachable": [_row("garden", "Garden", None),
                        _row("crypt", "Crypt", None, status="planned")],
        "retired": [_row("old_wing", "Old Wing", None, status="retired")],
    },
    "bodies": [
        {"name": "Nathan", "kind": "player", "char_id": None, "room": "study",
         "room_name": "Study", "station": None, "pose": None, "attire": None},
        {"name": "Alice", "kind": "cast", "char_id": 9, "room": "kitchen",
         "room_name": "Kitchen", "station": {"at": "oak_table", "near": []},
         "pose": {"posture": "standing"}, "attire": ALICE_ATTIRE},
        # The townspeople (2026-09-05): the inn's clerk on watch at the desk
        # post, whose anchor is the hearth, and a porter dealt a cell -- rows
        # of the charter REGISTRY, with no pose and no attire, as the server
        # lists them after the scene's bodies.
        {"name": "Ysra", "kind": "charter", "char_id": None, "room": "kitchen",
         "room_name": "Kitchen", "station": {"at": "hearth"}, "pose": None, "attire": None,
         "charter": "inn", "body": "clerk", "uid": "charter:inn:clerk", "source": "post",
         "facing": "w", "posts": ["desk"], "presented": "figure", "withheld": False,
         "authored": None},
        {"name": "Oren", "kind": "charter", "char_id": None, "room": "kitchen",
         "room_name": "Kitchen", "station": {"cell": [5, 4]}, "pose": None, "attire": None,
         "charter": "inn", "body": "porter", "uid": "charter:inn:porter", "source": "dealt",
         "facing": "n", "posts": [], "presented": "figure", "withheld": False,
         "authored": None},
    ],
    "vocab": VOCAB,
}

# A lamp standing on the kitchen floor by a position row, pinned to (2, 1):
# the one thing the map drags, and the one light source it draws.
LAMP = {"id": "brass_lamp", "name": "Brass Lamp", "kind": "lamp", "plan_ref": None,
        "placed": "position", "cell": [2, 1],
        "record": {"kind": "lamp", "description": "", "portable": True, "light_source": "",
                   "light_shape": "", "light_height": "", "steadiness": "", "sound_source": "",
                   "state": {}}}


def _slice(rid, name, desc, exits, occupants=(), adjacent=None, light="",
           region="", anchors=None, lint=(), things=(), extent=None, shape="", parts=()):
    record = {"name": name, "desc": desc, "notes": "", "light": light,
              "size": "", "exposure": "", "region": region,
              "extent": extent, "shape": shape, "parts": list(parts),
              "anchors": anchors or {},
              "adjacent": adjacent if adjacent is not None else [
                  {"to": x["to"], "barrier": x["barrier"]} for x in exits
                  if x["barrier"]]}
    record["geometry"] = _geometry(record)
    return {"id": rid, "name": name, "status": "live", "holder": None,
            "holder_name": None, "description": desc, "exits": exits,
            "region": region or None,
            "region_name": "East Wing" if region == "east_wing" else None,
            "region_look": "",
            "occupants": list(occupants), "things": [copy.deepcopy(t) for t in things],
            "planned_stub": None,
            "plan_here": {"planned_entities": [], "needs": [], "package_ops": []},
            "record": record,
            # Every authored anchor is stationable, as the server lists them.
            "stationable": [{"id": aid, "desc": a.get("desc") or aid, "implicit": False,
                             "dir": a.get("dir")} for aid, a in (anchors or {}).items()],
            "lint": list(lint)}


# The kitchen's layout rows, as the server files them: a wall row under the
# north wall's anchors, a bearing row under the exits.
KITCHEN_LINT = [
    {"kind": "wall_overfull", "room": "kitchen", "rooms": ["kitchen"], "wall": "n",
     "needs": 3, "holds": 2, "field": "anchors",
     "text": "Room 'kitchen': the n wall's anchors need 3 paces and the wall has 2; "
             "the extent cannot hold them."},
    {"kind": "reciprocal_bearing_disagrees", "rooms": ["kitchen", "hallway"],
     "dirs": ["n", "e"], "names": ["Kitchen", "Hallway"], "field": "exits",
     "text": "'Kitchen' says 'Hallway' lies n, and 'Hallway' says 'Kitchen' lies e; "
             "the two bearings are not opposites, so the doorway has no one place."},
]

SLICES = {
    "kitchen": _slice("kitchen", "Kitchen", "A rustic kitchen with a heavy oak table.",
                      [{"to": "hallway", "name": "Hallway", "barrier": "open",
                        "dir": None, "status": "live"},
                       {"to": "attic", "name": "Attic", "barrier": None,
                        "dir": None, "status": "planned"}],
                      [{"name": "Alice", "station": {"at": "oak_table", "near": []},
                        "attire": ALICE_ATTIRE, "pose": {"posture": "standing"}}],
                      adjacent=[{"to": "hallway", "barrier": "open"}],
                      region="east_wing",
                      anchors={"hearth": {"desc": "the hearth", "dir": "w", "height": "waist"},
                               "oak_table": {"desc": "the oak table"}},
                      lint=KITCHEN_LINT, things=[LAMP]),
    "hallway": _slice("hallway", "Hallway", "A long, dim hallway.",
                      [{"to": "kitchen", "name": "Kitchen", "barrier": "open",
                        "dir": None, "status": "live"}],
                      region="east_wing"),
    "study": _slice("study", "Study", "A cluttered study filled with books.",
                    [], [{"name": "Nathan", "station": None, "attire": None, "pose": None}]),
    "garden": _slice("garden", "Garden", "An overgrown garden.", []),
}

POSITIONS = {
    "rooms": [], "location": "Old Manor",
    "characters": [{"id": 9, "name": "Alice", "status": "active", "room": "kitchen"},
                   {"id": 10, "name": "Bob", "status": "active", "room": "hallway"}],
    "persona": {"name": "Nathan", "room": "kitchen"},
}


# The bearings the mock's doorways stand at, where the stored edge carries
# none (the server reads a bearing from the far side's edge too; the mock
# declares the answer here). Keyed (room, far room).
DOOR_DIRS = {("kitchen", "hallway"): "e", ("hallway", "kitchen"): "w"}

# Where the mock lays a room's neighbour, as the server's `room_field` would:
# beyond a one-cell band past the doorway, the two door cells aligned.
NEIGHBOUR_OFFSETS = {("kitchen", "hallway"): [7, -1], ("hallway", "kitchen"): [-7, 1]}


def _part_box(part, w, d):
    """`spatial_fov.part_box`, the mock's copy."""
    at = part["at"]
    if isinstance(at, str):
        pw, pd = min(part["w"], w), min(part["d"], d)
        x0 = w - pw if at in ("ne", "se") else 0
        y0 = d - pd if at in ("se", "sw") else 0
        return (x0, y0, x0 + pw, y0 + pd)
    return (max(0, at[0]), max(0, at[1]), max(0, min(w, at[0] + part["w"])),
            max(0, min(d, at[1] + part["d"])))


def _grid(rid, slices, charter=()):
    """A mock of `GET /rooms/{rid}/grid` over the mocked slice: the tier's
    square (or the extent's box, cut to a part shape's parts), each anchor on
    the wall its bearing names (one pace in when it has a height, at its
    `offset` along the wall when it has one), the doorways with a bearing as
    one cell of their wall, the occupants beside the anchor they stand at,
    the beared neighbour laid beyond its door, the things at their cells and
    a light source's height word. `charter` is the index's townspeople rows:
    the ones standing here and in the laid neighbour join `bodies` as the
    server lays them, each with its `room`."""
    room = slices[rid]
    record = room["record"]
    geometry = record["geometry"]
    w, d = geometry["w"], geometry["d"]
    cells = [[x, y] for x in range(w) for y in range(d)]
    if record.get("shape") in VOCAB["part_shapes"] and record.get("parts"):
        kept = set()
        for part in record["parts"]:
            x0, y0, x1, y1 = _part_box(part, w, d)
            kept.update((x, y) for x in range(x0, x1) for y in range(y0, y1))
        cells = sorted([list(c) for c in kept]) or cells
    has = {tuple(c) for c in cells}
    unit = {"n": (0, -1), "e": (1, 0), "s": (0, 1), "w": (-1, 0)}
    rims = {}
    for wall, (ux, uy) in unit.items():
        along = 0 if wall in ("n", "s") else 1
        rim = [c for c in has if (c[0] + ux, c[1] + uy) not in has]
        rims[wall] = [list(c) for c in sorted(rim, key=lambda c: (c[along], c[1 - along]))]

    def on_wall(wall, offset, inset):
        rim = rims[wall]
        idx = round((offset if offset is not None else 0.5) * (len(rim) - 1))
        x, y = rim[idx]
        dx, dy = {"n": (0, 1), "s": (0, -1), "e": (-1, 0), "w": (1, 0)}[wall]
        return [[x + dx * inset, y + dy * inset]]

    anchors = {}
    for aid, a in (record.get("anchors") or {}).items():
        wall = a.get("dir") or ""
        cell = a.get("cell") if isinstance(a.get("cell"), list) else None
        # The server's order: a pinned origin cell first, then a place along
        # the wall, then the seed (the middle stands in for the seed here).
        if cell:
            placed, source = [list(cell)], "cell"
        elif wall in rims:
            placed = on_wall(wall, a.get("offset"), 1 if a.get("height") else 0)
            source = "offset" if a.get("offset") is not None else "seed"
        else:
            placed, source = [[w // 2, d // 2]], "seed"
        anchors[aid] = {"cells": placed, "dir": wall or None, "height": a.get("height") or "floor",
                        "footprint": a.get("footprint") or "point",
                        "opacity": a.get("opacity") or "opaque", "desc": a.get("desc") or aid,
                        "implicit": False, "offset": a.get("offset"),
                        "cell": cell, "source": source}
    doorways, neighbours, walls = [], [], []
    for x in room["exits"]:
        edge = next((e for e in record["adjacent"] if e["to"] == x["to"]), {})
        wall = edge.get("dir") or DOOR_DIRS.get((rid, x["to"]))
        placed = on_wall(wall, edge.get("offset"), 0) if wall in rims else []
        doorways.append({"id": "door:" + x["to"], "to": x["to"], "name": x["name"], "dir": wall,
                         "cells": placed, "barrier": x["barrier"] or "open",
                         "offset": edge.get("offset"), "status": x["status"],
                         "passage": edge.get("passage"), "label": edge.get("name", ""),
                         "material": edge.get("material", ""), "width": edge.get("width"),
                         "state": {}, "declared_here": bool(edge)})
        offset = NEIGHBOUR_OFFSETS.get((rid, x["to"]))
        if offset and x["to"] in slices and placed:
            far = slices[x["to"]]["record"]["geometry"]
            neighbours.append({
                "id": x["to"], "name": x["name"], "offset": offset, "w": far["w"], "d": far["d"],
                "shape": "rectangle",
                "cells": [[fx, fy] for fx in range(far["w"]) for fy in range(far["d"])],
                "anchors": {aid: {"cells": [[1, 1]], "desc": a.get("desc") or aid, "implicit": False}
                            for aid, a in (slices[x["to"]]["record"].get("anchors") or {}).items()}})
            axis = 0 if wall in ("e", "w") else 1
            coord = placed[0][axis] + (1 if wall in ("e", "s") else -1)
            along = placed[0][1 - axis]
            walls.append({"axis": axis, "coord": coord, "extent": [-0.5, 12.5],
                          "aperture": [along - 0.5, along + 0.5], "to": x["to"], "name": x["name"]})
    bodies = {}
    for o in room["occupants"]:
        station = o.get("station") or {}
        at = station.get("at")
        cell, source = None, "none"
        # The server's order: the station's own pin first, else the anchor.
        if isinstance(station.get("cell"), list) and len(station["cell"]) == 2:
            cell, source = list(station["cell"]), "cell"
        elif at and at in anchors:
            ax, ay = anchors[at]["cells"][0]
            cell, source = [min(w - 1, ax + 1), ay], "anchor"
        kind = next((b["kind"] for b in INDEX["bodies"] if b["name"] == o["name"]), "presence")
        bodies[o["name"]] = {"cell": cell, "facing": "e" if cell else None, "kind": kind,
                             "at": at, "near": list(station.get("near") or []),
                             "measured": cell is not None, "source": source}
    laid = {rid} | {n["id"] for n in neighbours}
    for b in charter:
        if b["room"] not in laid:
            continue
        station = b.get("station") or {}
        # The server's placement: the station's cell, else a cell beside the
        # anchor (one pace south here, where a cast body's is one pace east,
        # so a townsperson at a fixture never covers the cast member at it),
        # else -- in a neighbour, whose anchors the mock does not place -- a
        # cell of that room.
        if isinstance(station.get("cell"), list) and len(station["cell"]) == 2:
            cell = list(station["cell"])
        elif station.get("at") and b["room"] == rid and station["at"] in anchors:
            ax, ay = anchors[station["at"]]["cells"][0]
            cell = [ax, min(d - 1, ay + 1)]
        else:
            cell = [1, 1]
        bodies[b["name"]] = {"cell": cell, "facing": b.get("facing"), "kind": "charter",
                             "at": station.get("at"), "near": [], "measured": True,
                             "source": b["source"], "room": b["room"], "charter": b["charter"],
                             "body": b["body"], "uid": b["uid"], "withheld": False,
                             "posts": list(b.get("posts") or []), "presented": "figure",
                             "station": dict(station), "authored": b.get("authored")}
    things, light_sources = [], []
    for th in room.get("things") or []:
        things.append({"id": th["id"], "name": th["name"], "kind": th.get("kind") or "",
                       "cell": th.get("cell"), "anchor": None, "placed": th.get("placed", "position"),
                       "source": "cell" if th.get("cell") else "none",
                       "light_source": th["record"].get("light_source", ""),
                       "sound_source": th["record"].get("sound_source", "")})
        if th["record"].get("light_source") and th.get("cell"):
            # The engine's rule: a declared height, else `full` for a fixture
            # and `head` for a free portable thing.
            height = th["record"].get("light_height") or ("head" if th["record"].get("portable") else "full")
            light_sources.append({"id": th["id"], "label": th["name"], "cell": th["cell"],
                                  "height": height, "shape": th["record"].get("light_shape") or "all_round"})
    # The overlays the readers would fill: a light word per cell for a room
    # that carries geometry (every mocked room has anchors or a size).
    overlays = {"light": {f"{x},{y}": "lit" if x < w // 2 else "dim" for x, y in cells},
                "noise": {f"{x},{y}": "quiet" for x, y in cells}}
    return {"frame_id": None,
            "room": {"id": rid, "name": room["name"], "w": w, "d": d, "shape": geometry["shape"],
                     "measured": geometry["measured"], "cells": cells},
            "rims": rims, "anchors": anchors, "doorways": doorways, "bodies": bodies,
            "things": things, "walls": walls, "neighbours": neighbours,
            "lint": list(room.get("lint") or []), "overlays": overlays,
            "sound_sources": [], "light_sources": light_sources}


def _map(slices):
    """A mock of `GET /map`: the kitchen and the hallway one component (the
    hallway east of the kitchen, the study north of the hallway), the garden
    its own, and a pantry the bearings land on the kitchen -- drawn, flagged.
    Each placed room names the room it was placed FROM and its doorways' cells."""
    def row(rid, name, offset, w=6, d=6, exits=(), occupants=(), lint=0, collided=False,
            onto=None, via=None, placed_via=None, region=None):
        return {"id": rid, "name": name, "offset": offset, "w": w, "d": d, "shape": "rectangle",
                "measured": False, "cells": [[x, y] for x in range(w) for y in range(d)],
                "exits": list(exits), "occupants": list(occupants), "lint": lint, "holder": None,
                "region": region, "collided": collided, "onto": onto, "via": via,
                "placed_via": placed_via}
    exit_ = lambda to, dir_, placed=True, barrier="open", cells=(): {
        "to": to, "name": slices.get(to, {}).get("name", to), "dir": dir_, "barrier": barrier,
        "placed": placed, "cells": [list(c) for c in cells], "passage": None}
    return {"frame_id": None, "location": "Old Manor", "components": [
        {"start": "hallway", "rooms": [
            row("hallway", "Hallway", [0, 0], exits=[exit_("kitchen", "w", cells=[(0, 2)]),
                                                    exit_("study", "n", barrier="closed_door", cells=[(3, 0)]),
                                                    exit_("pantry", "w", cells=[(0, 5)])],
                occupants=["Bob"], region="east_wing"),
            row("kitchen", "Kitchen", [-7, 1], exits=[exit_("hallway", "e", cells=[(5, 1)]),
                                                     exit_("attic", None, False)],
                occupants=["Alice"], lint=2, placed_via="hallway", region="east_wing"),
            row("study", "Study", [0, -7], exits=[exit_("hallway", "s", barrier="closed_door", cells=[(3, 5)])],
                occupants=["Nathan"], placed_via="hallway"),
            row("pantry", "Pantry", [-4, 3], w=4, d=4, exits=[exit_("hallway", "e", cells=[(3, 2)])], lint=1,
                collided=True, onto="kitchen", via="hallway", placed_via="hallway")],
         "collisions": [{"room": "pantry", "onto": "kitchen", "via": "hallway"}]},
        {"start": "garden", "rooms": [row("garden", "Garden", [0, 0])], "collisions": []},
    ]}


def _mount(page: Page):
    """Mock the API. A write MUTATES the mocked state the way the server
    would, so the re-render after a save shows what was saved."""
    bootstrap = {**BOOTSTRAP, "chats": [{"id": 1, "name": "First"}]}
    seen: list[str] = []
    writes: list[tuple[str, str, dict]] = []
    slices = copy.deepcopy(SLICES)
    index = copy.deepcopy(INDEX)
    attire = {"Alice": copy.deepcopy(ALICE_ATTIRE)}
    looks: dict[str, str] = {}

    def edge_of(rid, to):
        return next((e for e in slices[rid]["record"]["adjacent"] if e["to"] == to), None)

    def ensure_edge(rid, to, barrier="open", dir_=None):
        if edge_of(rid, to) is None:
            slices[rid]["record"]["adjacent"].append({"to": to, "barrier": barrier})
        if not any(x["to"] == to for x in slices[rid]["exits"]):
            slices[rid]["exits"].append({"to": to, "name": slices[to]["name"], "barrier": barrier,
                                         "dir": dir_, "status": "live"})
        if dir_:
            edge_of(rid, to)["dir"] = dir_

    def handle(route) -> None:
        request = route.request
        url = urlparse(request.url)
        path = url.path
        seen.append(path)
        body = {}
        status = 200
        if request.method in ("PATCH", "PUT", "POST", "DELETE") and not path.endswith("/bootstrap"):
            payload = json.loads(request.post_data) if request.post_data else {}
            writes.append((request.method, path, payload))
            parts = path.split("/")
            if request.method == "PUT" and path.startswith("/api/chats/1/bodies/") and path.endswith("/station"):
                name = parts[5]
                station = {"at": payload.get("at"), "near": list(payload.get("near") or [])}
                # The server keeps a `cell` only as two whole numbers, and
                # only when one was sent (null or absent is no pin).
                if isinstance(payload.get("cell"), list) and len(payload["cell"]) == 2:
                    station["cell"] = [int(payload["cell"][0]), int(payload["cell"][1])]
                for room in slices.values():
                    for o in room["occupants"]:
                        if o["name"] == name:
                            o["station"] = station
                    for th in room["things"]:
                        if th["id"] == name:
                            th["cell"] = station.get("cell")
                for b in index["bodies"]:
                    if b["name"] == name:
                        b["station"] = station
                body = {"name": name, "station": station}
            elif request.method == "PUT" and path.startswith("/api/chats/1/bodies/") and path.endswith("/room"):
                name, target = parts[5], payload["room"]
                for room in slices.values():
                    room["occupants"] = [o for o in room["occupants"] if o["name"] != name]
                slices[target]["occupants"].append({"name": name, "station": None, "attire": None, "pose": None})
                for b in index["bodies"]:
                    if b["name"] == name:
                        b["room"], b["room_name"], b["station"] = target, slices[target]["name"], None
                body = {"name": name, "room": target}
            elif request.method == "PUT" and path.startswith("/api/chats/1/bodies/") and path.endswith("/pose"):
                name = parts[5]
                pose = {k: v for k, v in payload.items() if v}
                for b in index["bodies"]:
                    if b["name"] == name:
                        b["pose"] = pose or None
                for room in slices.values():
                    for o in room["occupants"]:
                        if o["name"] == name:
                            o["pose"] = pose or None
                body = {"name": name, "pose": pose or None}
            elif request.method == "DELETE" and path.startswith("/api/chats/1/bodies/"):
                name = parts[5]
                for room in slices.values():
                    room["occupants"] = [o for o in room["occupants"] if o["name"] != name]
                index["bodies"] = [b for b in index["bodies"] if b["name"] != name]
                body = {"removed": name}
            elif request.method == "PUT" and path.startswith("/api/chats/1/characters/"):
                body = {"ok": True}
            elif request.method == "POST" and path == "/api/chats/1/regions":
                rid = payload["name"].strip().lower().replace(" ", "_")
                if not any(r["id"] == rid for r in index["vocab"]["regions"]):
                    index["vocab"]["regions"].append({"id": rid, "name": payload["name"], "look": ""})
                body = {"id": rid, "name": payload["name"], "brief": "", "look": "", "rooms": []}
            elif request.method == "PATCH" and path.startswith("/api/chats/1/regions/"):
                rid = path.rsplit("/", 1)[1]
                if "look" in payload:
                    looks[rid] = payload["look"]
                if "name" in payload:
                    for r in index["vocab"]["regions"]:
                        if r["id"] == rid:
                            r["name"] = payload["name"]
                    for s in slices.values():
                        if s["region"] == rid:
                            s["region_name"] = payload["name"]
                body = {"id": rid, "name": payload.get("name", rid), "brief": "", "look": looks.get(rid, ""),
                        "rooms": [s for s in slices if slices[s]["region"] == rid]}
            elif request.method == "POST" and path == "/api/chats/1/doorways":
                rid, to = payload["room"], payload["to"]
                barrier = payload.get("barrier") or "open"
                ensure_edge(rid, to, barrier, payload.get("dir"))
                opposite = {"n": "s", "s": "n", "e": "w", "w": "e"}.get(payload.get("dir"))
                ensure_edge(to, rid, barrier, opposite)
                pid = "|".join(sorted([rid, to]))
                for a, b in ((rid, to), (to, rid)):
                    edge_of(a, b)["passage"] = pid
                    if payload.get("offset") is not None:
                        edge_of(a, b)["offset"] = payload["offset"]
                body = {"passage": pid, "room": rid, "to": to, "slice": slices[rid]}
            elif request.method == "PATCH" and path.startswith("/api/chats/1/doorways/"):
                rid, to = parts[5], parts[6]
                ensure_edge(rid, to)
                ensure_edge(to, rid)
                pid = "|".join(sorted([rid, to]))
                for a, b in ((rid, to), (to, rid)):
                    edge = edge_of(a, b)
                    edge["passage"] = pid
                    for key in ("offset", "barrier", "name", "material", "width"):
                        if key in payload:
                            edge[key] = payload[key]
                    if "dir" in payload:
                        opposite = {"n": "s", "s": "n", "e": "w", "w": "e", "ne": "sw", "sw": "ne",
                                    "nw": "se", "se": "nw"}
                        edge["dir"] = payload["dir"] if a == rid else opposite.get(payload["dir"])
                    for x in slices[a]["exits"]:
                        if x["to"] == b:
                            if "barrier" in payload:
                                x["barrier"] = payload["barrier"]
                            if "dir" in payload:
                                x["dir"] = edge["dir"]
                body = {"passage": pid, "room": rid, "to": to, "slice": slices[rid]}
            elif request.method == "DELETE" and path.startswith("/api/chats/1/doorways/"):
                rid, to = parts[5], parts[6]
                for a, b in ((rid, to), (to, rid)):
                    slices[a]["record"]["adjacent"] = [e for e in slices[a]["record"]["adjacent"] if e["to"] != b]
                    slices[a]["exits"] = [x for x in slices[a]["exits"] if x["to"] != b]
                body = {"removed": [rid, to], "slice": slices[rid]}
            elif request.method == "POST" and path == "/api/chats/1/rooms":
                rid = payload["name"].strip().lower().replace(" ", "_")
                slices[rid] = _slice(rid, payload["name"], "", [])
                index["groups"]["reachable"].append(_row(rid, payload["name"], 1))
                if payload.get("from"):
                    src = payload["from"]
                    ensure_edge(src, rid, payload.get("barrier") or "open", payload.get("dir"))
                    opposite = {"n": "s", "s": "n", "e": "w", "w": "e"}.get(payload.get("dir"))
                    ensure_edge(rid, src, payload.get("barrier") or "open", opposite)
                body = dict(slices[rid], id=rid)
            elif request.method == "DELETE" and re.fullmatch(r"/api/chats/1/rooms/[^/]+", path):
                rid = parts[5]
                if slices[rid]["occupants"] or slices[rid]["things"]:
                    who = ", ".join(o["name"] for o in slices[rid]["occupants"])
                    status, body = 400, {"detail": f"'{rid}' is not empty (bodies: {who}); move them out before removing the room"}
                else:
                    slices.pop(rid)
                    for key in index["groups"]:
                        index["groups"][key] = [r for r in index["groups"][key] if r["id"] != rid]
                    body = {"removed": rid, "retired": True}
            elif request.method == "POST" and path.endswith("/entities"):
                rid = parts[5]
                eid = payload["name"].strip().lower().replace(" ", "_")
                thing = {"id": eid, "name": payload["name"], "kind": payload.get("kind") or "object",
                         "plan_ref": None, "placed": "position", "cell": payload.get("cell"),
                         "record": {"kind": payload.get("kind") or "object", "description": "",
                                    "portable": False, "light_source": "", "light_shape": "",
                                    "light_height": "", "steadiness": "", "sound_source": "", "state": {}}}
                slices[rid]["things"].append(thing)
                body = dict(slices[rid], id=eid)
            elif request.method == "DELETE" and "/entities/" in path:
                rid, eid = parts[5], parts[7]
                slices[rid]["things"] = [th for th in slices[rid]["things"] if th["id"] != eid]
                body = slices[rid]
            elif request.method == "PATCH" and "/entities/" in path:
                rid, eid = parts[5], parts[7]
                thing = next(th for th in slices[rid]["things"] if th["id"] == eid)
                for key in ("kind", "description", "portable", "light_source", "light_shape",
                            "light_height", "steadiness", "sound_source"):
                    if key in payload:
                        thing["record"][key] = payload[key]
                        if key == "kind":
                            thing["kind"] = payload[key]
                for flag in ("lit", "running", "pointed_at"):
                    if flag in payload:
                        thing["record"]["state"][flag] = payload[flag]
                if "room" in payload:
                    slices[rid]["things"].remove(thing)
                    thing["cell"] = None
                    slices[payload["room"]]["things"].append(thing)
                body = slices[rid]
            elif request.method == "POST" and path.endswith("/presences"):
                rid = parts[5]
                station = {"at": None, "near": []}
                if payload.get("cell"):
                    station["cell"] = payload["cell"]
                slices[rid]["occupants"].append({"name": payload["name"], "station": station,
                                                 "attire": None, "pose": None})
                index["bodies"].append({"name": payload["name"], "kind": "presence", "char_id": None,
                                        "room": rid, "room_name": slices[rid]["name"],
                                        "station": station, "pose": None, "attire": None})
                body = slices[rid]
            elif request.method == "PATCH" and path.startswith("/api/chats/1/rooms/"):
                rid = path.rsplit("/", 1)[1]
                room = slices[rid]
                for key in ("light", "size", "exposure", "name", "desc", "notes", "region",
                            "shape", "parts", "anchors"):
                    if key in payload:
                        room["record"][key] = payload[key]
                if "region" in payload:
                    room["region"] = payload["region"] or None
                if "extent" in payload:
                    # The server's rule: the size word follows the measurement.
                    room["record"]["extent"] = payload["extent"]
                    if payload["extent"]:
                        room["record"]["size"] = _geometry(room["record"])["size_derived"]
                room["record"]["geometry"] = _geometry(room["record"])
                if "name" in payload:
                    room["name"] = payload["name"]
                if "exits" in payload:
                    # An edge keeps its `offset` unless the exit says otherwise,
                    # as the server's `_apply_exits` keeps it.
                    prior = {e["to"]: e for e in room["record"]["adjacent"]}
                    room["record"]["adjacent"] = [
                        {**{k: v for k, v in prior.get(x["to"], {}).items() if k == "offset"},
                         "to": x["to"], "barrier": x["barrier"],
                         **({"dir": x["dir"]} if x.get("dir") else {}),
                         **({"offset": x["offset"]} if x.get("offset") is not None else {})}
                        for x in payload["exits"]]
                    room["exits"] = [{"to": x["to"], "name": slices.get(x["to"], {}).get(
                        "name", x["to"]), "barrier": x["barrier"], "dir": x.get("dir") or None,
                        "status": "live" if x["to"] in slices else "planned"}
                        for x in payload["exits"]]
                    for x in payload["exits"]:
                        far = slices.get(x["to"])
                        if far and not any(e["to"] == rid for e in far["exits"]):
                            far["exits"].append({"to": rid, "name": room["name"],
                                                 "barrier": x["barrier"], "dir": None,
                                                 "status": "live"})
                            far["record"]["adjacent"].append({"to": rid, "barrier": x["barrier"]})
                body = room
            elif request.method == "PUT" and path == "/api/chats/1/attire":
                attire.clear()
                attire.update(payload)
                for b in index["bodies"]:
                    if b["name"] in attire:
                        b["attire"] = attire[b["name"]]
                body = {"ok": True}
            elif "/charters/" in path and path.endswith("/station"):
                # A townsperson's place: the charter REGISTRY's row, never a
                # slice's occupant. A PUT with `at` or `cell` authors the
                # station (`source` authored); a PUT with the room alone moves
                # the body to the dealt rule there; a DELETE hands it back to
                # its post's anchor or a dealt cell.
                charter, body_key = parts[5], parts[7]
                row = next(b for b in index["bodies"]
                           if b.get("charter") == charter and b.get("body") == body_key)
                if request.method == "PUT":
                    room = payload["room"]
                    moved = room != row["room"]
                    row["room"], row["room_name"] = room, slices[room]["name"]
                    if "at" in payload or "cell" in payload:
                        station = {k: payload[k] for k in ("at", "cell", "facing")
                                   if payload.get(k) is not None}
                        row["station"], row["authored"], row["source"] = station, dict(station), "authored"
                    elif moved:
                        row["station"], row["authored"], row["source"] = {"cell": [1, 1]}, None, "dealt"
                else:
                    row["authored"] = None
                    if row["posts"] and row["room"] == "kitchen":
                        row["station"], row["source"] = {"at": "hearth"}, "post"
                    else:
                        row["station"], row["source"] = {"cell": [5, 4]}, "dealt"
                body = dict(row)
            else:
                body = {"ok": True}
        elif path == "/api/bootstrap":
            body = bootstrap
        elif path == "/api/chats/1":
            body = _chat_payload(1, "First", "settled prose")
        elif path == "/api/chats/1/vitals":
            body = {"enabled": False, "bodies": []}
        elif path == "/api/chats/1/rooms":
            body = index
        elif path == "/api/chats/1/map":
            body = _map(slices)
        elif path.startswith("/api/chats/1/rooms/") and path.endswith("/grid"):
            rid = path.split("/")[5]
            if rid in slices:
                body = _grid(rid, slices, [b for b in index["bodies"] if b["kind"] == "charter"])
                if parse_qs(url.query).get("sound_from"):
                    body["overlays"]["sound"] = {k: "full" for k in body["overlays"]["noise"]}
            else:
                status, body = 404, {"detail": f"No room '{rid}' in this scene"}
        elif path.startswith("/api/chats/1/rooms/"):
            rid = path.rsplit("/", 1)[1]
            if rid in slices:
                body = dict(slices[rid])
                body["region_look"] = looks.get(body.get("region") or "", "")
            else:
                status, body = 404, {"detail": f"No room '{rid}' in this story"}
        elif path == "/api/chats/1/positions":
            body = POSITIONS
        elif path == "/api/chats/1/world":
            body = {"scene": {"location": "Old Manor"}}
        elif path == "/api/chats/1/attire":
            body = attire
        route.fulfill(status=status, content_type="application/json",
                      body=json.dumps(body))

    page.route("**/api/**", handle)
    return seen, writes


def _open_story(page: Page, ui_base_url: str):
    seen, writes = _mount(page)
    page.goto(f"{ui_base_url}/static/index.html")
    page.get_by_label("Open First").click()
    expect(page.locator("#chatname")).to_have_text("First")
    return seen, writes


def _open_map(page: Page, ui_base_url: str):
    seen, writes = _open_story(page, ui_base_url)
    page.locator("#b-world").click()
    modal = page.locator("#modal")
    expect(modal.locator(".wb-room-map")).to_be_visible()
    return seen, writes, modal


def test_the_world_button_opens_on_the_room_tree_and_the_players_room(
        page: Page, ui_base_url: str) -> None:
    page_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    _open_story(page, ui_base_url)

    page.locator("#b-world").click()
    modal = page.locator("#modal")
    expect(modal).to_be_visible()
    expect(page.locator("#modaltitle")).to_have_text("World state")
    # Rooms is the first tab and the one 🌍 opens.
    expect(modal.locator(".lore-inspector-tabs button.on")).to_have_text("Rooms")
    expect(modal.locator(".lore-inspector-tabs button")).to_have_text(["Rooms", "Bodies", "Raw JSON"])
    # The tree: the cast's rooms with the occupants beside them, the plan's
    # rooms badged, the retired ids folded away, the interior nested.
    tree = modal.locator(".wb-tree")
    expect(tree).to_contain_text("Where the cast stands")
    expect(tree.locator(".wb-room[data-room=kitchen]")).to_contain_text("Alice")
    expect(tree.locator(".wb-room[data-room=attic] .badge")).to_have_text("Planned")
    expect(tree.locator(".wb-nested .wb-room[data-room=console_room]")).to_have_count(1)
    expect(tree.locator("details.wb-retired")).not_to_have_attribute("open", "")
    expect(tree.locator(".wb-room[data-room=old_wing]")).to_be_hidden()
    # The card: the player's room, its prose in an editor, its exits.
    card = modal.locator(".wb-card")
    expect(tree.locator(".wb-room.on")).to_have_attribute("data-room", "kitchen")
    expect(card.locator("textarea").first).to_have_value("A rustic kitchen with a heavy oak table.")
    expect(card).to_contain_text("Move here")
    assert page_errors == []


def test_an_exit_walks_to_the_far_room(page: Page, ui_base_url: str) -> None:
    seen, _ = _open_story(page, ui_base_url)
    page.locator("#b-world").click()
    modal = page.locator("#modal")
    card = modal.locator(".wb-card")
    expect(card.locator("textarea").first).to_have_value("A rustic kitchen with a heavy oak table.")

    card.locator(".wb-exit .wb-link", has_text="Hallway").click()
    expect(card.locator("textarea").first).to_have_value("A long, dim hallway.")
    expect(modal.locator(".wb-tree .wb-room.on")).to_have_attribute("data-room", "hallway")
    assert "/api/chats/1/rooms/hallway" in seen
    # A planned far room is badged on its exit row, and is still a link.
    card.locator(".wb-exit .wb-link", has_text="Kitchen").click()
    expect(card.locator(".wb-exit", has_text="Attic").locator(".badge")).to_have_text("Planned")


def test_a_rooms_light_is_edited_through_the_select(page: Page, ui_base_url: str) -> None:
    _, writes = _open_story(page, ui_base_url)
    page.locator("#b-world").click()
    card = page.locator("#modal .wb-card")
    light = card.locator(".wb-field", has_text="Light").locator("select")
    # The menu is the engine's set, with a blank for "unset".
    expect(light.locator("option")).to_have_text(["—", "dark", "dim", "lit", "bright"])
    light.select_option("dim")
    expect(page.locator("#toasts")).to_contain_text("Saved.")
    patches = [w for w in writes if w[0] == "PATCH" and w[1] == "/api/chats/1/rooms/kitchen"]
    assert patches and patches[-1][2] == {"light": "dim"}
    # The card re-rendered from the server's answer.
    expect(card.locator(".wb-field", has_text="Light").locator("select")).to_have_value("dim")


def test_adding_an_exit_shows_the_doorway_from_both_rooms(page: Page, ui_base_url: str) -> None:
    _, writes = _open_story(page, ui_base_url)
    page.locator("#b-world").click()
    modal = page.locator("#modal")
    card = modal.locator(".wb-card")
    add = card.locator(".wb-exit.wb-add").first
    add.locator("select").nth(0).select_option("garden")
    add.locator("select").nth(1).select_option("closed_door")
    add.get_by_role("button", name="Add exit").click()
    expect(card.locator(".wb-exit[data-exit=garden]")).to_have_count(1)
    patches = [w for w in writes if w[0] == "PATCH" and w[1] == "/api/chats/1/rooms/kitchen"]
    # This room's FULL exit list, the standing doorway kept, the new one added.
    assert patches[-1][2]["exits"] == [
        {"to": "hallway", "barrier": "open", "dir": ""},
        {"to": "garden", "barrier": "closed_door", "dir": ""}]
    # Walk through it: the far room shows the doorway back.
    card.locator(".wb-exit .wb-link", has_text="Garden").click()
    expect(card.locator("textarea").first).to_have_value("An overgrown garden.")
    expect(card.locator(".wb-exit[data-exit=kitchen]")).to_have_count(1)


def test_a_doorways_name_material_and_width_are_one_object_from_either_room(
        page: Page, ui_base_url: str) -> None:
    """The passage record: the doorway's fields go through the doorways PATCH
    from whichever room is open, and the far room reads the same."""
    _, writes = _open_story(page, ui_base_url)
    page.locator("#b-world").click()
    card = page.locator("#modal .wb-card")
    fields = card.locator(".wb-doorway-fields[data-doorway=hallway]")
    expect(fields).to_have_count(1)
    fields.locator("input").nth(0).fill("the arch")
    fields.locator("input").nth(0).press("Enter")
    expect(page.locator("#toasts")).to_contain_text("Saved.")
    assert ("PATCH", "/api/chats/1/doorways/kitchen/hallway", {"name": "the arch"}) in writes
    fields = card.locator(".wb-doorway-fields[data-doorway=hallway]")
    fields.locator("input").nth(2).fill("2")
    fields.locator("input").nth(2).press("Enter")
    assert ("PATCH", "/api/chats/1/doorways/kitchen/hallway", {"width": 2}) in writes
    # From the hallway the same doorway carries the same name.
    card.locator(".wb-exit .wb-link", has_text="Hallway").click()
    expect(card.locator(".wb-doorway-fields[data-doorway=kitchen] input").nth(0)).to_have_value("the arch")


def test_setting_an_extent_disables_size_and_shows_the_derived_tier(
        page: Page, ui_base_url: str) -> None:
    _, writes = _open_story(page, ui_base_url)
    page.locator("#b-world").click()
    card = page.locator("#modal .wb-card")
    size = card.locator(".wb-field-size select")
    extent = card.locator(".wb-field-extent")
    # No extent: the size word is the host's to choose, and the card says
    # what square the tier gives.
    expect(size).to_be_enabled()
    expect(extent).to_contain_text("6 × 6 from the tier")
    # One side alone is not a measurement and sends nothing.
    extent.locator("input").nth(0).fill("3")
    extent.locator("input").nth(0).blur()
    assert not [w for w in writes if "extent" in w[2]]
    extent.locator("input").nth(1).fill("12")
    extent.locator("input").nth(1).press("Enter")
    expect(page.locator("#toasts")).to_contain_text("Saved.")
    patches = [w for w in writes if w[0] == "PATCH" and w[1] == "/api/chats/1/rooms/kitchen"]
    assert patches[-1][2] == {"extent": {"w": 3, "d": 12}}
    # Re-rendered from the server's answer: size is the derived tier, shown
    # and not offered; the walls read the extent.
    size = card.locator(".wb-field-size select")
    expect(size).to_be_disabled()
    expect(size).to_have_value("medium")
    expect(card.locator(".wb-field-size")).to_contain_text("derived from the extent")
    expect(card.locator(".wb-wall[data-wall=n] .wb-wall-paces")).to_have_text("3 paces")
    expect(card.locator(".wb-wall[data-wall=e] .wb-wall-paces")).to_have_text("12 paces")
    # Clearing the extent re-enables the word.
    card.locator(".wb-field-extent .wb-remove").click()
    patches = [w for w in writes if w[0] == "PATCH" and w[1] == "/api/chats/1/rooms/kitchen"]
    assert patches[-1][2] == {"extent": None}
    expect(card.locator(".wb-field-size select")).to_be_enabled()


def test_anchors_are_listed_under_their_wall(page: Page, ui_base_url: str) -> None:
    _, writes = _open_story(page, ui_base_url)
    page.locator("#b-world").click()
    card = page.locator("#modal .wb-card")
    anchors = card.locator(".wb-section", has_text="Anchors")
    # Four straight walls always head a group, each with its paces from the
    # tier; the hearth is under the west wall, the bearingless table last.
    expect(anchors.locator(".wb-wall[data-wall=n], .wb-wall[data-wall=e], "
                           ".wb-wall[data-wall=s], .wb-wall[data-wall=w]")).to_have_count(4)
    expect(anchors.locator(".wb-wall[data-wall=w] .wb-wall-paces")).to_have_text("6 paces")
    expect(anchors.locator(".wb-wall[data-wall=w] .wb-anchor[data-anchor=hearth]")).to_have_count(1)
    expect(anchors.locator(".wb-wall[data-wall=''] .wb-anchor[data-anchor=oak_table]")).to_have_count(1)
    expect(anchors.locator(".wb-wall[data-wall='']")).to_contain_text("No wall")
    # Moving the hearth to the north wall is changing its bearing: the whole
    # anchor map is sent, the hearth's dir changed and the table untouched.
    anchors.locator(".wb-anchor[data-anchor=hearth] select").nth(0).select_option("n")
    expect(page.locator("#toasts")).to_contain_text("Saved.")
    patches = [w for w in writes if w[0] == "PATCH" and "anchors" in w[2]]
    assert patches[-1][2]["anchors"] == {
        "hearth": {"desc": "the hearth", "dir": "n", "height": "waist"},
        "oak_table": {"desc": "the oak table"}}
    expect(card.locator(".wb-wall[data-wall=n] .wb-anchor[data-anchor=hearth]")).to_have_count(1)


def test_editing_the_region_look_persists_and_shows_on_a_sibling_room(
        page: Page, ui_base_url: str) -> None:
    _, writes = _open_story(page, ui_base_url)
    page.locator("#b-world").click()
    card = page.locator("#modal .wb-card")
    look = card.locator(".wb-look .wb-field input")
    expect(card.locator(".wb-look")).to_contain_text("Shared by every room in")
    expect(card.locator(".wb-look")).to_contain_text("East Wing")
    look.fill("brick and iron under sodium lamps")
    look.press("Enter")
    expect(page.locator("#toasts")).to_contain_text("Saved.")
    assert ("PATCH", "/api/chats/1/regions/east_wing",
            {"look": "brick and iron under sodium lamps"}) in writes
    # The room PATCH never carried it: the look is the region's.
    assert not [w for w in writes if w[1].startswith("/api/chats/1/rooms/") and "look" in w[2]]
    # A sibling room in the same region reads the one sentence.
    card.locator(".wb-exit .wb-link", has_text="Hallway").click()
    expect(card.locator("textarea").first).to_have_value("A long, dim hallway.")
    expect(card.locator(".wb-look .wb-field input")).to_have_value("brick and iron under sodium lamps")
    # A room in no region has no look to edit.
    page.locator("#modal .wb-tree .wb-room[data-room=garden]").click()
    expect(card.locator("textarea").first).to_have_value("An overgrown garden.")
    expect(card.locator(".wb-look")).to_have_count(0)


def test_a_region_is_created_from_the_card_and_renamed(page: Page, ui_base_url: str) -> None:
    _, writes = _open_story(page, ui_base_url)
    page.locator("#b-world").click()
    card = page.locator("#modal .wb-card")
    # The region box with a new name and "New region": the regions POST,
    # then the room moved into the region it made.
    box = card.locator(".wb-region-field input")
    box.fill("West Wing")
    card.locator(".wb-new-region").click()
    expect(page.locator("#toasts")).to_contain_text("Saved.")
    assert ("POST", "/api/chats/1/regions", {"name": "West Wing"}) in writes
    patches = [w for w in writes if w[0] == "PATCH" and w[1] == "/api/chats/1/rooms/kitchen"]
    assert patches[-1][2] == {"region": "west_wing"}
    # Renamed: the regions PATCH with `name`; the room's field untouched.
    rename = card.locator(".wb-region-rename")
    rename.fill("The West Wing")
    rename.press("Enter")
    assert ("PATCH", "/api/chats/1/regions/west_wing", {"name": "The West Wing"}) in writes
    assert not [w for w in writes if w[1].startswith("/api/chats/1/rooms/") and "name" in w[2]]
    expect(card.locator(".wb-look")).to_contain_text("The West Wing")


def test_a_lint_row_renders_beside_its_field_and_the_tree_marks_the_room(
        page: Page, ui_base_url: str) -> None:
    _open_story(page, ui_base_url)
    page.locator("#b-world").click()
    modal = page.locator("#modal")
    card = modal.locator(".wb-card")
    # The tree marks the room the lint names, and only that one.
    expect(modal.locator(".wb-tree .wb-room[data-room=kitchen] .wb-lint-mark")).to_have_text("Layout")
    expect(modal.locator(".wb-tree .wb-room[data-room=study] .wb-lint-mark")).to_have_count(0)
    # The wall row sits under the north wall; the bearing row under the exits;
    # nothing under the fields that carry no row.
    north = card.locator(".wb-wall[data-wall=n] .wb-lint")
    expect(north).to_have_count(1)
    expect(north).to_contain_text("the wall has 2")
    expect(card.locator(".wb-wall[data-wall=w] .wb-lint")).to_have_count(0)
    exits = card.locator(".wb-section", has_text="Exits").locator(".wb-lint")
    expect(exits).to_have_count(1)
    expect(exits).to_contain_text("not opposites")
    expect(card.locator(".wb-lint")).to_have_count(2)


def test_the_raw_tab_keeps_the_world_editor(page: Page, ui_base_url: str) -> None:
    seen, _ = _open_story(page, ui_base_url)
    page.locator("#b-world").click()
    modal = page.locator("#modal")
    modal.locator(".lore-inspector-tabs button", has_text="Raw JSON").click()
    textarea = modal.locator("textarea")
    expect(textarea).to_be_visible()
    expect(textarea).to_have_value(json.dumps({"scene": {"location": "Old Manor"}}, indent=2))
    expect(modal.get_by_role("button", name="Save")).to_be_visible()
    assert "/api/chats/1/world" in seen


def test_the_attire_button_opens_on_the_bodies_tab_with_the_ledgers_unfolded(
        page: Page, ui_base_url: str) -> None:
    seen, _ = _open_story(page, ui_base_url)
    page.locator("#b-attire").click()
    modal = page.locator("#modal")
    expect(page.locator("#modaltitle")).to_have_text("Attire")
    expect(modal.locator(".lore-inspector-tabs button.on")).to_have_text("Bodies")
    body = modal.locator("details.wb-body[data-body=Alice]")
    expect(body).to_have_attribute("open", "")
    expect(body).to_contain_text("Cast")
    expect(body).to_contain_text("Kitchen")
    # The kimono is ONE garment shown under both regions it covers.
    torso = body.locator(".wb-region[data-region=torso]")
    legs = body.locator(".wb-region[data-region=legs]")
    expect(torso.locator(".wb-garment")).to_have_count(2)
    expect(legs.locator(".wb-garment")).to_have_count(1)
    expect(legs.locator(".wb-garment")).to_contain_text("Also:")
    # A bare region says so.
    expect(body.locator(".wb-region[data-region=head]")).to_contain_text("bare")
    # Its Raw JSON tab is the attire ledger, not the world table.
    modal.locator(".lore-inspector-tabs button", has_text="Raw JSON").click()
    expect(modal.locator("textarea")).to_contain_text('"silk kimono"')
    assert "/api/chats/1/attire" in seen and "/api/chats/1/world" not in seen


def test_changing_a_garments_state_carries_every_region_and_never_narrows_it(
        page: Page, ui_base_url: str) -> None:
    _, writes = _open_story(page, ui_base_url)
    page.locator("#b-attire").click()
    body = page.locator("#modal details.wb-body[data-body=Alice]")
    legs = body.locator(".wb-region[data-region=legs]")
    legs.locator(".wb-garment select").select_option("loosened")
    expect(page.locator("#toasts")).to_contain_text("Saved.")

    puts = [w for w in writes if w[0] == "PUT" and w[1] == "/api/chats/1/attire"]
    assert len(puts) == 1
    ledger = puts[0][2]
    # The whole ledger, this body rebuilt.
    assert set(ledger) == {"Alice"}
    regions = ledger["Alice"]["regions"]
    torso = {g["name"]: g for g in regions["torso"]["garments"]}
    legs_ = {g["name"]: g for g in regions["legs"]["garments"]}
    # Edited under the legs, loosened at the torso too: one garment.
    assert torso["silk kimono"]["state"] == "loosened"
    assert legs_["silk kimono"]["state"] == "loosened"
    assert set(torso["silk kimono"]["covers"]) == {"torso", "legs"}
    # The apron, untouched, is still worn -- not reset, not dropped.
    assert torso["apron"]["state"] == "worn"
    assert "apron" not in legs_
    # The authored note list rides along for the server to re-derive.
    assert ledger["Alice"]["state"] == ALICE_ATTIRE["state"]
    # The tab re-rendered from the saved ledger.
    expect(body.locator(".wb-region[data-region=torso]").locator(".wb-garment select").first) \
        .to_have_value("loosened")


def test_the_bodies_tab_moves_the_player_and_writes_a_pose(page: Page, ui_base_url: str) -> None:
    """The bodies route the cast editor lacked: the player moved by name;
    the pose's fields written whole; the Bodies tab and the card agree."""
    _, writes = _open_story(page, ui_base_url)
    page.locator("#b-attire").click()
    # The attire button unfolds every body, Nathan's included.
    nathan = page.locator("#modal details.wb-body[data-body=Nathan]")
    expect(nathan).to_have_attribute("open", "")
    nathan.locator(".wb-body-place select").select_option("kitchen")
    expect(page.locator("#toasts")).to_contain_text("Moved Nathan to Kitchen.")
    assert ("PUT", "/api/chats/1/bodies/Nathan/room", {"room": "kitchen"}) in writes
    # No character route: the player has no character id.
    assert not [w for w in writes if "/characters/" in w[1]]
    nathan = page.locator("#modal details.wb-body[data-body=Nathan]")
    expect(nathan.locator("summary")).to_contain_text("Kitchen")
    # The pose: posture from the engine's words, support free text.
    posture = nathan.locator(".wb-pose .wb-pose-posture")
    posture.fill("sitting")
    posture.press("Enter")
    expect(page.locator("#toasts")).to_contain_text("Saved.")
    puts = [w for w in writes if w[0] == "PUT" and w[1] == "/api/chats/1/bodies/Nathan/pose"]
    assert puts and puts[-1][2] == {"posture": "sitting", "support": "", "relative_to": "",
                                    "relation": "", "constraint": "", "detail": ""}
    expect(page.locator("#modal details.wb-body[data-body=Nathan] summary")).to_contain_text("sitting")
    # The card's row for Nathan agrees after a re-fetch.
    page.locator("#modal .lore-inspector-tabs button", has_text="Rooms").click()
    expect(page.locator("#modal .wb-card .wb-body[data-body=Nathan] .wb-pose-posture")).to_have_value("sitting")


# ---- The map editor -----------------------------------------------------------

def test_the_map_renders_the_rooms_cells_anchors_doorway_neighbour_and_bodies(
        page: Page, ui_base_url: str) -> None:
    page_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    seen, _, modal = _open_map(page, ui_base_url)
    svg = modal.locator(".wb-room-map")
    assert "/api/chats/1/rooms/kitchen/grid" in seen
    # The bar says where the zoom stands; the tree is still there beneath.
    expect(modal.locator(".wb-map-bar")).to_contain_text("Kitchen")
    expect(modal.locator(".wb-map-bar .wb-map-up")).to_have_text("All rooms")
    expect(modal.locator(".wb-list .wb-tree .wb-room[data-room=kitchen]")).to_be_visible()
    # Six by six cells, the two anchors, the beared doorway, the neighbour
    # laid beyond it, the one body with her facing tick, the lamp.
    expect(svg.locator(".wb-m-cell")).to_have_count(36)
    expect(svg.locator(".wb-m-anchor")).to_have_count(2)
    expect(svg.locator(".wb-m-anchor[data-anchor=hearth] .wb-m-height")).to_have_count(1)
    expect(svg.locator(".wb-m-anchor[data-anchor=oak_table] .wb-m-height")).to_have_count(0)
    expect(svg.locator(".wb-m-doorway[data-exit=hallway] .wb-m-door")).to_have_count(1)
    expect(svg.locator(".wb-m-neighbour[data-room=hallway]")).to_have_count(1)
    expect(svg.locator(".wb-m-neighbour[data-room=hallway] .wb-m-far-cell")).to_have_count(36)
    expect(svg.locator(".wb-m-neighbour[data-room=hallway] .wb-m-far-name")).to_have_text("Hallway")
    expect(svg.locator(".wb-m-body[data-body=Alice] .wb-m-facing")).to_have_count(1)
    expect(svg.locator(".wb-m-body[data-body=Alice] .wb-m-name")).to_have_text("Alice")
    expect(svg.locator(".wb-m-thing[data-thing=brass_lamp]")).to_have_count(1)
    # The lint drawn at the thing it concerns: the wall row along the north
    # wall, the bearing row at the doorway (the far room is drawn, so at it).
    expect(svg.locator(".wb-m-lint-wall")).to_have_count(6)
    expect(svg.locator(".wb-m-lint-mark[data-kind=wall_overfull]")).to_have_count(1)
    expect(svg.locator(".wb-m-lint-mark[data-kind=reciprocal_bearing_disagrees]")).to_have_count(1)
    # Four resize handles, one per side; blank wall segments and empty cells
    # as targets; the legend names every mark.
    expect(svg.locator(".wb-m-handle")).to_have_count(4)
    expect(svg.locator(".wb-m-wall-hit").first).to_be_attached()
    expect(svg.locator(".wb-m-cell.free").first).to_be_attached()
    expect(modal.locator(".wb-map-marks")).to_contain_text("Ceiling light")
    # The doorway the mock cannot place is said in words under the map.
    expect(modal.locator(".wb-map-notes")).to_contain_text("Attic")
    # Overlays are OFF by default: toggles offered, nothing painted.
    expect(modal.locator(".wb-map-bar .wb-overlay")).to_have_count(2)
    expect(svg.locator(".wb-m-tint")).to_have_count(0)
    assert page_errors == []


def test_clicking_an_anchor_on_the_map_focuses_its_editor_row(
        page: Page, ui_base_url: str) -> None:
    _, _, modal = _open_map(page, ui_base_url)
    modal.locator(".wb-room-map .wb-m-anchor[data-anchor=hearth]").click()
    row = modal.locator(".wb-card .wb-anchor[data-anchor=hearth]")
    expect(row).to_have_class(re.compile(r"\bwb-focus\b"))
    expect(row.locator("input").first).to_be_focused()
    # A doorway opens its exit row; a body its station row; a thing its
    # editor; Enter on a focused anchor does what the click does.
    modal.locator(".wb-room-map .wb-m-doorway[data-exit=hallway]").click()
    expect(modal.locator(".wb-card .wb-exit[data-exit=hallway]")).to_have_class(re.compile(r"\bwb-focus\b"))
    modal.locator(".wb-room-map .wb-m-body[data-body=Alice]").click()
    expect(modal.locator(".wb-card .wb-body[data-body=Alice]")).to_have_class(re.compile(r"\bwb-focus\b"))
    modal.locator(".wb-room-map .wb-m-thing[data-thing=brass_lamp]").click()
    expect(modal.locator(".wb-card .wb-thing[data-thing=brass_lamp]")).to_have_class(re.compile(r"\bwb-focus\b"))
    modal.locator(".wb-room-map .wb-m-anchor[data-anchor=oak_table]").focus()
    page.keyboard.press("Enter")
    expect(modal.locator(".wb-card .wb-anchor[data-anchor=oak_table]")).to_have_class(re.compile(r"\bwb-focus\b"))


def test_dragging_an_anchor_to_another_wall_changes_its_bearing_and_offset(
        page: Page, ui_base_url: str) -> None:
    _, writes, modal = _open_map(page, ui_base_url)
    svg = modal.locator(".wb-room-map")
    # The hearth stands on the west wall; drop it on cell (3, 0) -- the
    # north wall, three paces from its west end. Cells are listed x-major.
    hearth = svg.locator(".wb-m-anchor[data-anchor=hearth]")
    target = svg.locator(".wb-m-cell").nth(3 * 6 + 0)
    hearth.drag_to(target)
    # The toast names what was written.
    expect(page.locator("#toasts")).to_contain_text("Moved hearth to the N wall")
    patches = [w for w in writes if w[0] == "PATCH" and "anchors" in w[2]]
    assert patches, writes
    sent = patches[-1][2]["anchors"]
    # The whole anchor map, the hearth re-beared with a place along the wall
    # (3 of the 5 positions a one-cell anchor has on six), the table untouched.
    assert sent["hearth"]["dir"] == "n" and sent["hearth"]["height"] == "waist"
    assert abs(sent["hearth"]["offset"] - 0.6) < 1e-9
    assert sent["oak_table"] == {"desc": "the oak table"}
    # Re-rendered from the server's answer: the card lists it under the north
    # wall, and the map draws it there (one pace in, as a standing thing).
    expect(modal.locator(".wb-card .wb-wall[data-wall=n] .wb-anchor[data-anchor=hearth]")).to_have_count(1)
    moved = modal.locator(".wb-room-map .wb-m-anchor[data-anchor=hearth] .wb-m-anchor-cell")
    expect(moved).to_have_attribute("y", "25")
    # Dropped into the room, an anchor loses its wall and its offset and is
    # PINNED to the cell it landed on (the owner, 2026-09-04).
    modal.locator(".wb-room-map .wb-m-anchor[data-anchor=hearth]").drag_to(
        modal.locator(".wb-room-map .wb-m-cell").nth(2 * 6 + 2))
    expect(page.locator("#toasts")).to_contain_text("Pinned hearth to (2, 2)")
    patches = [w for w in writes if w[0] == "PATCH" and "anchors" in w[2]]
    assert patches[-1][2]["anchors"]["hearth"]["dir"] == ""
    assert patches[-1][2]["anchors"]["hearth"]["offset"] is None
    assert patches[-1][2]["anchors"]["hearth"]["cell"] == [2, 2]
    # And dragged back onto a wall, the pin is let go with the wall written.
    modal.locator(".wb-room-map .wb-m-anchor[data-anchor=hearth]").drag_to(
        modal.locator(".wb-room-map .wb-m-cell").nth(0 * 6 + 4))
    expect(page.locator("#toasts")).to_contain_text("Moved hearth to the W wall")
    patches = [w for w in writes if w[0] == "PATCH" and "anchors" in w[2]]
    sent = patches[-1][2]["anchors"]["hearth"]
    assert sent["dir"] == "w" and sent["cell"] is None and sent["offset"] is not None


def test_undo_reissues_the_previous_anchor_map_and_an_arrow_key_nudges(
        page: Page, ui_base_url: str) -> None:
    _, writes, modal = _open_map(page, ui_base_url)
    svg = modal.locator(".wb-room-map")
    svg.locator(".wb-m-anchor[data-anchor=hearth]").drag_to(svg.locator(".wb-m-cell").nth(2 * 6 + 2))
    expect(page.locator("#toasts")).to_contain_text("Pinned hearth to (2, 2)")
    # Undo: the previous anchor map through the same route, and it is gone
    # from the bar once used.
    undo = modal.locator(".wb-map-bar .wb-undo")
    expect(undo).to_have_count(1)
    undo.click()
    expect(page.locator("#toasts")).to_contain_text("Undid: Pinned hearth to (2, 2)")
    patches = [w for w in writes if w[0] == "PATCH" and "anchors" in w[2]]
    assert patches[-1][2]["anchors"]["hearth"] == {"desc": "the hearth", "dir": "w", "height": "waist"}
    expect(modal.locator(".wb-map-bar .wb-undo")).to_have_count(0)
    # The arrow key is the drag by one cell: Alice stands at (1, 2) beside
    # the oak table? No -- at the table's cell +1: the mock puts her at (4, 3).
    body = modal.locator(".wb-room-map .wb-m-body[data-body=Alice]")
    body.focus()
    page.keyboard.press("ArrowRight")
    expect(page.locator("#toasts")).to_contain_text("Placed Alice at (5, 3)")
    puts = [w for w in writes if w[0] == "PUT" and w[1] == "/api/chats/1/bodies/Alice/station"]
    assert puts[-1][2] == {"at": None, "near": [], "cell": [5, 3]}
    # The focus came back to the mark, so a second press goes on nudging.
    expect(modal.locator(".wb-room-map .wb-m-body[data-body=Alice]")).to_be_focused()


def test_dragging_a_doorway_along_its_wall_sets_the_exits_offset_as_one_object(
        page: Page, ui_base_url: str) -> None:
    _, writes, modal = _open_map(page, ui_base_url)
    svg = modal.locator(".wb-room-map")
    # The doorway to the hallway is on the east wall; drop it beside cell
    # (5, 5), the wall's south end. The write is the doorways PATCH -- the
    # doorway is one object -- and lands on both rooms' edges.
    svg.locator(".wb-m-doorway[data-exit=hallway]").drag_to(svg.locator(".wb-m-cell").nth(5 * 6 + 5))
    expect(page.locator("#toasts")).to_contain_text("Moved the doorway to Hallway along the wall")
    patches = [w for w in writes if w[1] == "/api/chats/1/doorways/kitchen/hallway"]
    assert patches and patches[-1] == ("PATCH", "/api/chats/1/doorways/kitchen/hallway", {"offset": 1.0})
    # From the hallway, the same doorway is dragged too -- its edge on the
    # hallway's side was minted by the route.
    modal.locator(".wb-card .wb-exit .wb-link", has_text="Hallway").click()
    expect(modal.locator(".wb-map-bar")).to_contain_text("Hallway")
    svg = modal.locator(".wb-room-map")
    svg.locator(".wb-m-doorway[data-exit=kitchen]").drag_to(svg.locator(".wb-m-cell").nth(0 * 6 + 0))
    expect(page.locator("#toasts")).to_contain_text("Moved the doorway to Kitchen along the wall")
    assert ("PATCH", "/api/chats/1/doorways/hallway/kitchen", {"offset": 0.0}) in writes


def test_dragging_a_body_onto_an_anchor_sets_its_station(page: Page, ui_base_url: str) -> None:
    _, writes, modal = _open_map(page, ui_base_url)
    svg = modal.locator(".wb-room-map")
    # Alice stands at the oak table; drop her on the hearth: `at` for prose
    # AND the cell she landed on (the hearth's cell (1, 2): one pace in from
    # the west wall's middle, as the mock lays a standing thing).
    svg.locator(".wb-m-body[data-body=Alice]").drag_to(svg.locator(".wb-m-anchor[data-anchor=hearth]"))
    expect(page.locator("#toasts")).to_contain_text("Placed Alice at hearth")
    puts = [w for w in writes if w[0] == "PUT" and w[1] == "/api/chats/1/bodies/Alice/station"]
    assert puts and puts[-1][2] == {"at": "hearth", "near": [], "cell": [1, 2]}
    # The card's station row and the map agree with the server's answer.
    expect(modal.locator(".wb-card .wb-body[data-body=Alice] .wb-exit select")).to_have_value("hearth")
    expect(modal.locator(".wb-card .wb-body[data-body=Alice] .wb-station-cell")).to_contain_text("(1, 2)")
    expect(svg.locator(".wb-m-body[data-body=Alice]")).to_have_count(1)
    expect(svg.locator(".wb-m-body[data-body=Alice]")).to_have_class(re.compile(r"\bpinned\b"))
    # Dropped on a plain cell, she is pinned to it and `at` is cleared (the
    # owner, 2026-09-04: "why are characters and personas locked to
    # stations?").
    svg.locator(".wb-m-body[data-body=Alice]").drag_to(svg.locator(".wb-m-cell").nth(4 * 6 + 4))
    expect(page.locator("#toasts")).to_contain_text("Placed Alice at (4, 4)")
    puts = [w for w in writes if w[0] == "PUT" and w[1] == "/api/chats/1/bodies/Alice/station"]
    assert puts[-1][2] == {"at": None, "near": [], "cell": [4, 4]}
    dot = svg.locator(".wb-m-body[data-body=Alice] .wb-m-body-dot")
    expect(dot).to_have_attribute("cx", "108")           # (4 + 0.5) * 24
    expect(dot).to_have_attribute("cy", "108")
    # She stays there after a reload of the browser: close it, open it again.
    page.locator("#modalx").click()
    page.locator("#b-world").click()
    dot = page.locator("#modal .wb-room-map .wb-m-body[data-body=Alice] .wb-m-body-dot")
    expect(dot).to_have_attribute("cx", "108")
    expect(dot).to_have_attribute("cy", "108")
    # The card shows the cell with a clear; clearing sends no cell.
    page.locator("#modal .wb-card .wb-body[data-body=Alice] .wb-clear-cell").click()
    expect(page.locator("#toasts")).to_contain_text("Saved.")
    puts = [w for w in writes if w[0] == "PUT" and w[1] == "/api/chats/1/bodies/Alice/station"]
    assert puts[-1][2] == {"at": None, "near": [], "cell": None}
    expect(page.locator("#modal .wb-room-map .wb-m-body[data-body=Alice]")).to_have_class(
        re.compile(r"\bunplaced\b"))


def test_dragging_an_anchor_into_the_room_pins_it_to_that_cell(page: Page, ui_base_url: str) -> None:
    """The owner, 2026-09-04: "I can only place anchors at stations when I
    don't wall-attach them, which is quite limiting." The hearth, on the
    west wall, dropped in the middle of the room, stays where it was
    dropped after a reload, and the card shows the cell with a clear."""
    _, writes, modal = _open_map(page, ui_base_url)
    svg = modal.locator(".wb-room-map")
    # Cell (2, 4): inside the room, off every wall, not under the table
    # (which the mock stands in the middle). Cells are listed x-major.
    svg.locator(".wb-m-anchor[data-anchor=hearth]").drag_to(svg.locator(".wb-m-cell").nth(2 * 6 + 4))
    expect(page.locator("#toasts")).to_contain_text("Pinned hearth to (2, 4)")
    patches = [w for w in writes if w[0] == "PATCH" and "anchors" in w[2]]
    sent = patches[-1][2]["anchors"]["hearth"]
    assert sent == {"desc": "the hearth", "dir": "", "height": "waist", "offset": None, "cell": [2, 4]}
    cell = modal.locator(".wb-room-map .wb-m-anchor[data-anchor=hearth] .wb-m-anchor-cell")
    expect(cell).to_have_attribute("x", "49")            # 2 * 24 + 1
    expect(cell).to_have_attribute("y", "97")            # 4 * 24 + 1
    # Listed under "No wall" now, with the cell beside the wall select.
    expect(modal.locator(".wb-card .wb-wall[data-wall=''] .wb-anchor[data-anchor=hearth]")).to_have_count(1)
    expect(modal.locator(".wb-card .wb-anchor[data-anchor=hearth] .wb-anchor-cell")).to_contain_text("(2, 4)")
    # Still there after a reload.
    page.locator("#modalx").click()
    page.locator("#b-world").click()
    cell = page.locator("#modal .wb-room-map .wb-m-anchor[data-anchor=hearth] .wb-m-anchor-cell")
    expect(cell).to_have_attribute("x", "49")
    expect(cell).to_have_attribute("y", "97")
    # Clearing the cell sends the anchor map with the hearth's cell null.
    page.locator("#modal .wb-card .wb-anchor[data-anchor=hearth] .wb-clear-cell").click()
    expect(page.locator("#toasts")).to_contain_text("Saved.")
    patches = [w for w in writes if w[0] == "PATCH" and "anchors" in w[2]]
    assert patches[-1][2]["anchors"]["hearth"]["cell"] is None


def test_dragging_a_thing_pins_it_and_a_ceiling_light_draws_as_a_ring(
        page: Page, ui_base_url: str) -> None:
    _, writes, modal = _open_map(page, ui_base_url)
    svg = modal.locator(".wb-room-map")
    lamp = svg.locator(".wb-m-thing[data-thing=brass_lamp]")
    expect(lamp.locator(".wb-m-light-ring")).to_have_count(0)
    # Dragged to (4, 2): the station route, the same rule as a body.
    lamp.drag_to(svg.locator(".wb-m-cell").nth(4 * 6 + 2))
    expect(page.locator("#toasts")).to_contain_text("Placed Brass Lamp at (4, 2)")
    puts = [w for w in writes if w[0] == "PUT" and w[1] == "/api/chats/1/bodies/brass_lamp/station"]
    assert puts and puts[-1][2] == {"at": None, "near": [], "cell": [4, 2]}
    # Lit, from the card, at full height: the engine's vocabularies, and the
    # map draws a ring -- a ceiling light casts no shadow.
    card = modal.locator(".wb-card .wb-thing[data-thing=brass_lamp]")
    card.locator(".wb-thing-light select").nth(0).select_option("lit")
    expect(page.locator("#toasts")).to_contain_text("Saved.")
    assert ("PATCH", "/api/chats/1/rooms/kitchen/entities/brass_lamp", {"light_source": "lit"}) in writes
    # Each select re-renders the card from the server's answer, so waiting
    # for the value to show is waiting for the write to have landed.
    card = modal.locator(".wb-card .wb-thing[data-thing=brass_lamp]")
    light = card.locator(".wb-thing-light select")
    expect(light.nth(1).locator("option")).to_have_text(["—", "all_round", "cone"])
    light.nth(2).select_option("full")
    expect(modal.locator(".wb-card .wb-thing[data-thing=brass_lamp] .wb-thing-light select").nth(2)).to_have_value("full")
    assert ("PATCH", "/api/chats/1/rooms/kitchen/entities/brass_lamp", {"light_height": "full"}) in writes
    expect(modal.locator(".wb-room-map .wb-m-thing[data-thing=brass_lamp] .wb-m-light-ring")).to_have_count(1)
    # A cone offers what it may point at: bearings, anchors, things.
    modal.locator(".wb-card .wb-thing[data-thing=brass_lamp] .wb-thing-light select").nth(1).select_option("cone")
    pointed = modal.locator(".wb-card .wb-thing[data-thing=brass_lamp] .wb-thing-light select").nth(4)
    expect(pointed.locator("option", has_text="hearth")).to_have_count(1)
    pointed.select_option("hearth")
    expect(modal.locator(".wb-card .wb-thing[data-thing=brass_lamp] .wb-thing-light select").nth(4)).to_have_value("hearth")
    assert ("PATCH", "/api/chats/1/rooms/kitchen/entities/brass_lamp", {"pointed_at": "hearth"}) in writes
    # Sound: the level, then the running flag appears.
    modal.locator(".wb-card .wb-thing[data-thing=brass_lamp] .wb-thing-sound select").select_option("faint")
    expect(modal.locator(".wb-card .wb-thing[data-thing=brass_lamp] .wb-thing-sound input[type=checkbox]")).to_have_count(1)
    assert ("PATCH", "/api/chats/1/rooms/kitchen/entities/brass_lamp", {"sound_source": "faint"}) in writes
    # Removed from the card.
    modal.locator(".wb-card .wb-thing[data-thing=brass_lamp] .wb-remove-thing").click()
    assert ("DELETE", "/api/chats/1/rooms/kitchen/entities/brass_lamp", {}) in writes
    expect(modal.locator(".wb-room-map .wb-m-thing[data-thing=brass_lamp]")).to_have_count(0)


def test_a_side_handle_resizes_the_room_and_the_shape_is_chosen_on_the_map(
        page: Page, ui_base_url: str) -> None:
    _, writes, modal = _open_map(page, ui_base_url)
    svg = modal.locator(".wb-room-map")
    # The east handle dragged two cells out: an 8 x 6 extent, the size word
    # following on the card. The pointer moves by two cells' worth of pixels
    # (the SVG is scaled to the pane, so a cell's on-screen width is read).
    px = svg.locator(".wb-m-cell").first.bounding_box()["width"]
    handle = svg.locator(".wb-m-handle-e").bounding_box()
    page.mouse.move(handle["x"] + handle["width"] / 2, handle["y"] + handle["height"] / 2)
    page.mouse.down()
    page.mouse.move(handle["x"] + handle["width"] / 2 + px, handle["y"] + handle["height"] / 2, steps=4)
    page.mouse.move(handle["x"] + handle["width"] / 2 + 2 * px, handle["y"] + handle["height"] / 2, steps=4)
    page.mouse.up()
    expect(page.locator("#toasts")).to_contain_text("Resized the room to 8 × 6 paces")
    patches = [w for w in writes if w[0] == "PATCH" and "extent" in w[2]]
    assert patches and patches[-1][2] == {"extent": {"w": 8, "d": 6}}
    expect(modal.locator(".wb-card .wb-field-size select")).to_be_disabled()
    expect(modal.locator(".wb-room-map .wb-m-cell")).to_have_count(48)
    # The shape from the map's own select: the room PATCH.
    modal.locator(".wb-map-bar .wb-map-shape").select_option("composite")
    expect(page.locator("#toasts")).to_contain_text("Shape: composite")
    assert ("PATCH", "/api/chats/1/rooms/kitchen", {"shape": "composite"}) in writes
    # The card's parts editor offers a cell-placed part; add one by cell.
    card = modal.locator(".wb-card")
    add = card.locator(".wb-parts .wb-add")
    add.locator("select").select_option("cell")
    inputs = add.locator("input")
    inputs.nth(0).fill("0"); inputs.nth(1).fill("0"); inputs.nth(2).fill("8"); inputs.nth(3).fill("2")
    add.get_by_role("button", name="Add part").click()
    patches = [w for w in writes if w[0] == "PATCH" and "parts" in w[2]]
    assert patches[-1][2] == {"parts": [{"w": 8, "d": 2, "at": [0, 0]}]}
    # Drawn as a part on the map, with a knob; the room's cells are the
    # part's now (the mock cuts the box to the parts as the engine does).
    expect(modal.locator(".wb-room-map .wb-m-part[data-part='0']")).to_have_count(1)
    expect(modal.locator(".wb-room-map .wb-m-cell")).to_have_count(16)
    # Dragged one cell down, the part is re-placed by its origin cell.
    part = modal.locator(".wb-room-map .wb-m-part[data-part='0']")
    box = part.bounding_box()
    page.mouse.move(box["x"] + 20, box["y"] + 20)
    page.mouse.down()
    page.mouse.move(box["x"] + 20, box["y"] + 20 + box["height"] / 2, steps=4)
    page.mouse.move(box["x"] + 20, box["y"] + 20 + box["height"], steps=4)
    page.mouse.up()
    expect(page.locator("#toasts")).to_contain_text("Moved part to (0, 2)")
    patches = [w for w in writes if w[0] == "PATCH" and "parts" in w[2]]
    assert patches[-1][2] == {"parts": [{"w": 8, "d": 2, "at": [0, 2]}]}


def test_a_blank_wall_opens_a_doorway_or_adds_a_room_and_empty_floor_places(
        page: Page, ui_base_url: str) -> None:
    _, writes, modal = _open_map(page, ui_base_url)
    svg = modal.locator(".wb-room-map")
    # A segment of the south wall: the form names the wall and the place.
    svg.locator(".wb-m-wall-hit[data-wall=s][data-cell='2,5']").click()
    form = modal.locator(".wb-map-forms .wb-wall-form")
    expect(form).to_contain_text("S")
    expect(form).to_contain_text("40%")
    form.locator("select").nth(0).select_option("closed_door")
    form.locator("select").nth(1).select_option("garden")
    form.locator(".wb-open-doorway").click()
    expect(page.locator("#toasts")).to_contain_text("Opened a doorway to Garden on the S wall.")
    assert ("POST", "/api/chats/1/doorways",
            {"room": "kitchen", "to": "garden", "barrier": "closed_door", "dir": "s", "offset": 0.4}) in writes
    expect(modal.locator(".wb-room-map .wb-m-doorway[data-exit=garden]")).to_have_count(1)
    expect(modal.locator(".wb-card .wb-exit[data-exit=garden]")).to_have_count(1)
    # A new room through the north wall.
    modal.locator(".wb-room-map .wb-m-wall-hit[data-wall=n][data-cell='1,0']").click()
    form = modal.locator(".wb-map-forms .wb-wall-form")
    form.locator("input").fill("Scullery")
    form.locator(".wb-add-room").click()
    expect(page.locator("#toasts")).to_contain_text("Added Scullery through the N wall.")
    posts = [w for w in writes if w[0] == "POST" and w[1] == "/api/chats/1/rooms"]
    assert posts[-1][2] == {"name": "Scullery", "from": "kitchen", "dir": "n", "barrier": "open"}
    # The new room is selected, its grid drawn.
    expect(modal.locator(".wb-map-bar")).to_contain_text("Scullery")
    expect(modal.locator(".wb-tree .wb-room.on")).to_have_attribute("data-room", "scullery")
    # Back in the kitchen: empty floor places a thing, then a presence, then
    # an anchor, each at the clicked cell.
    modal.locator(".wb-tree .wb-room[data-room=kitchen]").click()
    expect(modal.locator(".wb-map-bar")).to_contain_text("Kitchen")
    # (1, 4): empty floor -- the table stands at (3, 3) and Alice beside it,
    # so those cells are theirs and take no click of their own.
    expect(modal.locator(".wb-room-map .wb-m-cell.free[data-cell='3,3']")).to_have_count(0)
    modal.locator(".wb-room-map .wb-m-cell.free[data-cell='1,4']").click()
    form = modal.locator(".wb-map-forms .wb-cell-form")
    expect(form).to_contain_text("(1, 4)")
    form.locator("input").fill("Crate")
    form.locator(".wb-place-thing").click()
    expect(page.locator("#toasts")).to_contain_text("Added Crate.")
    assert ("POST", "/api/chats/1/rooms/kitchen/entities", {"name": "Crate", "kind": "", "cell": [1, 4]}) in writes
    expect(modal.locator(".wb-room-map .wb-m-thing[data-thing=crate]")).to_have_count(1)
    modal.locator(".wb-room-map .wb-m-cell.free[data-cell='0,5']").click()
    form = modal.locator(".wb-map-forms .wb-cell-form")
    form.locator("input").fill("The Cook")
    form.locator(".wb-place-presence").click()
    expect(page.locator("#toasts")).to_contain_text("Placed The Cook.")
    assert ("POST", "/api/chats/1/rooms/kitchen/presences", {"name": "The Cook", "cell": [0, 5]}) in writes
    expect(modal.locator(".wb-room-map .wb-m-body[data-body='The Cook']")).to_have_class(re.compile(r"\bpresence\b"))
    modal.locator(".wb-room-map .wb-m-cell.free[data-cell='4,0']").click()
    form = modal.locator(".wb-map-forms .wb-cell-form")
    form.locator("input").fill("the dresser")
    form.locator(".wb-place-anchor").click()
    expect(page.locator("#toasts")).to_contain_text("Added the dresser at (4, 0)")
    patches = [w for w in writes if w[0] == "PATCH" and "anchors" in w[2]]
    assert patches[-1][2]["anchors"][""] == {"desc": "the dresser", "cell": [4, 0]}
    # The presence is removed from its card row.
    modal.locator(".wb-card .wb-body[data-body='The Cook'] .wb-remove-presence").click()
    expect(page.locator("#toasts")).to_contain_text("Removed The Cook.")
    assert ("DELETE", "/api/chats/1/bodies/The%20Cook", {}) in writes or \
        ("DELETE", "/api/chats/1/bodies/The Cook", {}) in writes


def test_removing_a_room_is_refused_while_occupied_and_lands_when_empty(
        page: Page, ui_base_url: str) -> None:
    _, writes, modal = _open_map(page, ui_base_url)
    modal.locator(".wb-map-bar .wb-remove-room").click()
    # The server's refusal is the toast, naming who stands there.
    expect(page.locator("#toasts")).to_contain_text("bodies: Alice")
    assert ("DELETE", "/api/chats/1/rooms/kitchen", {}) in writes
    expect(modal.locator(".wb-map-bar")).to_contain_text("Kitchen")
    modal.locator(".wb-tree .wb-room[data-room=garden]").click()
    expect(modal.locator(".wb-map-bar")).to_contain_text("Garden")
    modal.locator(".wb-map-bar .wb-remove-room").click()
    expect(page.locator("#toasts")).to_contain_text("Removed Garden; its id is retired.")
    assert ("DELETE", "/api/chats/1/rooms/garden", {}) in writes
    expect(modal.locator(".wb-tree .wb-room[data-room=garden]")).to_have_count(0)
    expect(modal.locator(".wb-map-bar")).to_contain_text("Kitchen")


def test_an_overlay_toggle_paints_the_readers_words_and_a_source_can_be_heard_from(
        page: Page, ui_base_url: str) -> None:
    seen, _, modal = _open_map(page, ui_base_url)
    svg = modal.locator(".wb-room-map")
    expect(svg.locator(".wb-m-tint")).to_have_count(0)
    modal.locator(".wb-map-bar .wb-overlay[data-overlay=light]").click()
    expect(modal.locator(".wb-map-bar .wb-overlay[data-overlay=light]")).to_have_attribute("aria-pressed", "true")
    expect(modal.locator(".wb-room-map .wb-m-tint")).to_have_count(36)
    expect(modal.locator(".wb-map-legend")).to_contain_text("light:")
    expect(modal.locator(".wb-map-legend")).to_contain_text("lit")
    expect(modal.locator(".wb-map-legend")).to_contain_text("dim")
    # Off again with a second click; the noise toggle paints its own words.
    modal.locator(".wb-map-bar .wb-overlay[data-overlay=light]").click()
    expect(modal.locator(".wb-room-map .wb-m-tint")).to_have_count(0)
    modal.locator(".wb-map-bar .wb-overlay[data-overlay=noise]").click()
    expect(modal.locator(".wb-map-legend")).to_contain_text("quiet")


def test_the_structure_map_draws_doors_where_they_stand_and_a_drag_re_bears(
        page: Page, ui_base_url: str) -> None:
    seen, writes, modal = _open_map(page, ui_base_url)
    modal.locator(".wb-map-bar .wb-map-up").click()
    structure = modal.locator(".wb-structure-map")
    expect(structure).to_be_visible()
    assert "/api/chats/1/map" in seen
    expect(modal.locator(".wb-map-bar")).to_contain_text("Every room, placed by bearing")
    # Every room as a box: the two components side by side, the occupied
    # rooms marked, the exits at their DOOR CELLS, and the pantry DRAWN on
    # the kitchen; the collision said in words; the regions in the legend.
    expect(structure.locator(".wb-sm-room")).to_have_count(5)
    expect(structure.locator(".wb-sm-room[data-room=kitchen]")).to_have_class(re.compile(r"\boccupied\b"))
    expect(structure.locator(".wb-sm-room[data-room=kitchen] .wb-sm-who")).to_have_text("Alice")
    expect(structure.locator(".wb-sm-room[data-room=hallway] .wb-sm-exit.at-door")).to_have_count(3)
    expect(structure.locator(".wb-sm-room[data-room=pantry]")).to_have_class(re.compile(r"\bcollided\b"))
    expect(structure.locator(".wb-sm-room[data-room=kitchen] .wb-sm-lint")).to_have_count(1)
    expect(structure.locator(".wb-sm-room[data-room=kitchen] .wb-sm-unbeared")).to_have_text("?1")
    expect(structure.locator(".wb-sm-room[data-room=kitchen]")).to_have_class(re.compile(r"\bregion-0\b"))
    expect(modal.locator(".wb-map-legend")).to_contain_text("East Wing")
    expect(modal.locator(".wb-map-notes")).to_contain_text("Pantry")
    expect(modal.locator(".wb-map-notes")).to_contain_text("lands on")
    # Drag the study (placed north of the hallway) to the hallway's east:
    # the doorway that placed it is re-beared from the hallway, both edges.
    study = structure.locator(".wb-sm-room[data-room=study]")
    hallway = structure.locator(".wb-sm-room[data-room=hallway]")
    sb, hb = study.bounding_box(), hallway.bounding_box()
    page.mouse.move(sb["x"] + sb["width"] / 2, sb["y"] + sb["height"] / 2)
    page.mouse.down()
    page.mouse.move(hb["x"] + hb["width"] * 1.5, hb["y"] + hb["height"] / 2, steps=6)
    page.mouse.move(hb["x"] + hb["width"] * 1.6, hb["y"] + hb["height"] / 2, steps=3)
    page.mouse.up()
    expect(page.locator("#toasts")).to_contain_text("Placed Study E of Hallway")
    assert ("PATCH", "/api/chats/1/doorways/hallway/study", {"dir": "e"}) in writes
    # Undo re-bears it back through the same route.
    modal.locator(".wb-map-bar .wb-undo").click()
    assert ("PATCH", "/api/chats/1/doorways/hallway/study", {"dir": "n"}) in writes
    # Click the hallway: its grid on the left, its card on the right.
    structure = modal.locator(".wb-structure-map")
    structure.locator(".wb-sm-room[data-room=hallway]").click()
    expect(modal.locator(".wb-room-map")).to_be_visible()
    expect(modal.locator(".wb-map-bar")).to_contain_text("Hallway")
    expect(modal.locator(".wb-card textarea").first).to_have_value("A long, dim hallway.")
    expect(modal.locator(".wb-tree .wb-room.on")).to_have_attribute("data-room", "hallway")
    assert "/api/chats/1/rooms/hallway/grid" in seen
    # A neighbour drawn on the room map opens the same way.
    modal.locator(".wb-room-map .wb-m-neighbour[data-room=kitchen]").click()
    expect(modal.locator(".wb-map-bar")).to_contain_text("Kitchen")
    expect(modal.locator(".wb-card textarea").first).to_have_value("A rustic kitchen with a heavy oak table.")


# ---- Townspeople on the map (2026-09-05, DESIGN_CHARTER_PLACEMENT § the map) --

CLERK = "/api/chats/1/charters/inn/bodies/clerk/station"
PORTER = "/api/chats/1/charters/inn/bodies/porter/station"


def _square_x(cell_x):
    """Where the mock's square mark for a townsperson starts: the cell's
    centre less the half-side the map draws (`S * 0.32`)."""
    return f"{(cell_x + 0.5) * 24 - 24 * 0.32:g}"


def test_townspeople_are_drawn_with_their_own_mark_and_a_click_opens_the_row(
        page: Page, ui_base_url: str) -> None:
    page_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    _, _, modal = _open_map(page, ui_base_url)
    svg = modal.locator(".wb-room-map")
    # A square where the cast are dots; the clause that placed each is its
    # class, so the dealt one draws lighter than the one at her post.
    ysra = svg.locator(".wb-m-body.charter[data-body=Ysra]")
    oren = svg.locator(".wb-m-body.charter[data-body=Oren]")
    expect(ysra).to_have_count(1)
    expect(ysra.locator("rect.wb-m-body-dot")).to_have_count(1)
    expect(ysra).to_have_class(re.compile(r"\bpost\b"))
    expect(oren).to_have_class(re.compile(r"\bdealt\b"))
    expect(svg.locator(".wb-m-body[data-body=Alice] circle.wb-m-body-dot")).to_have_count(1)
    # Beside the hearth (1, 3), as the mock lays a townsperson at an anchor.
    expect(ysra.locator(".wb-m-body-dot")).to_have_attribute("x", _square_x(1))
    expect(oren.locator(".wb-m-body-dot")).to_have_attribute("x", _square_x(5))
    expect(ysra.locator(".wb-m-facing")).to_have_count(1)
    expect(modal.locator(".wb-map-marks")).to_contain_text("Townsperson")
    expect(modal.locator(".wb-map-marks")).to_contain_text("dealt a cell")
    # Click opens the row under "Who is here" with the focus every mark has.
    ysra.click()
    row = modal.locator(".wb-card .wb-charter[data-body=Ysra]")
    expect(row).to_have_class(re.compile(r"\bwb-focus\b"))
    expect(row).to_contain_text("Townsperson")
    expect(row).to_contain_text("desk")
    expect(row).to_contain_text("hearth")
    expect(row.locator(".wb-charter-source")).to_have_attribute("data-source", "post")
    expect(row.locator(".wb-clear-station")).to_have_count(0)      # nothing authored to clear
    expect(row.locator("select").first).to_be_focused()
    # Enter on a focused mark does what the click does.
    oren.focus()
    page.keyboard.press("Enter")
    expect(modal.locator(".wb-card .wb-charter[data-body=Oren]")).to_have_class(re.compile(r"\bwb-focus\b"))
    # The Bodies tab lists them under their own heading, room and post shown.
    page.locator("#modal .lore-inspector-tabs button", has_text="Bodies").click()
    expect(page.locator("#modal .wb-townsfolk-heading")).to_have_text("Townspeople")
    details = page.locator("#modal details.wb-charter[data-body=Ysra]")
    expect(details.locator("summary")).to_contain_text("Townsperson")
    expect(details.locator("summary")).to_contain_text("Kitchen")
    expect(details.locator("summary")).to_contain_text("desk")
    expect(details.locator("summary")).to_contain_text("at the post's anchor")
    # The scene's bodies keep their own rows, with attire and pose.
    expect(page.locator("#modal details.wb-body[data-body=Alice] .wb-attire")).to_have_count(1)
    expect(details.locator(".wb-attire")).to_have_count(0)
    assert page_errors == []


def test_dragging_a_townsperson_in_its_room_writes_the_charter_station(
        page: Page, ui_base_url: str) -> None:
    _, writes, modal = _open_map(page, ui_base_url)
    svg = modal.locator(".wb-room-map")
    # Onto an anchor: she stands AT it -- the one route, the registry's.
    svg.locator(".wb-m-body[data-body=Ysra]").drag_to(svg.locator(".wb-m-anchor[data-anchor=oak_table]"))
    expect(page.locator("#toasts")).to_contain_text("Placed Ysra at oak_table")
    puts = [w for w in writes if w[1] == CLERK]
    assert puts[-1] == ("PUT", CLERK, {"room": "kitchen", "at": "oak_table"})
    assert not [w for w in writes if w[1].startswith("/api/chats/1/bodies/")]
    ysra = svg.locator(".wb-m-body[data-body=Ysra]")
    expect(ysra).to_have_class(re.compile(r"\bauthored\b"))
    row = modal.locator(".wb-card .wb-charter[data-body=Ysra]")
    expect(row.locator(".wb-charter-source")).to_have_attribute("data-source", "authored")
    expect(row.locator(".wb-clear-station")).to_have_count(1)
    # Onto a plain cell: pinned to it; no `at` is sent.
    ysra.drag_to(svg.locator(".wb-m-cell").nth(1 * 6 + 5))
    expect(page.locator("#toasts")).to_contain_text("Placed Ysra at (1, 5)")
    puts = [w for w in writes if w[1] == CLERK]
    assert puts[-1] == ("PUT", CLERK, {"room": "kitchen", "cell": [1, 5]})
    expect(svg.locator(".wb-m-body[data-body=Ysra] .wb-m-body-dot")).to_have_attribute("x", _square_x(1))
    # Undo re-issues the station the record held before the drop.
    modal.locator(".wb-map-bar .wb-undo").click()
    expect(page.locator("#toasts")).to_contain_text("Undid")
    puts = [w for w in writes if w[1] == CLERK]
    assert puts[-1] == ("PUT", CLERK, {"room": "kitchen", "at": "oak_table"})
    expect(modal.locator(".wb-card .wb-charter[data-body=Ysra] .wb-charter-where")).to_contain_text("oak_table")
    # An arrow key is the drag by one cell, from where the mark stands: the
    # cell beside the table (3, 4), one to the east.
    svg.locator(".wb-m-body[data-body=Ysra]").focus()
    page.keyboard.press("ArrowRight")
    puts = [w for w in writes if w[1] == CLERK]
    assert puts[-1] == ("PUT", CLERK, {"room": "kitchen", "cell": [4, 4]})
    expect(page.locator("#toasts")).to_contain_text("Placed Ysra at (4, 4)")


def test_dragging_a_townsperson_into_a_neighbour_moves_it_there(
        page: Page, ui_base_url: str) -> None:
    _, writes, modal = _open_map(page, ui_base_url)
    svg = modal.locator(".wb-room-map")
    target = svg.locator(".wb-m-neighbour[data-room=hallway] .wb-m-far-cell").nth(2 * 6 + 2)
    svg.locator(".wb-m-body[data-body=Oren]").drag_to(target)
    expect(page.locator("#toasts")).to_contain_text("Moved Oren to Hallway.")
    puts = [w for w in writes if w[1] == PORTER]
    assert puts[-1] == ("PUT", PORTER, {"room": "hallway", "cell": [2, 2]})
    # No longer one of this room's marks; drawn faintly where the neighbour
    # is, in its own frame.
    expect(svg.locator(".wb-m-body[data-body=Oren]")).to_have_count(0)
    expect(svg.locator(".wb-m-far-body[data-body=Oren]")).to_have_count(1)
    expect(modal.locator(".wb-card .wb-charter[data-body=Oren]")).to_have_count(0)
    # The Bodies tab agrees about the room, and its select moves him back
    # through the same route with the room alone (the dealt rule there).
    page.locator("#modal .lore-inspector-tabs button", has_text="Bodies").click()
    oren = page.locator("#modal details.wb-charter[data-body=Oren]")
    expect(oren.locator("summary")).to_contain_text("Hallway")
    oren.locator("summary").click()
    oren.locator(".wb-body-place select").select_option("kitchen")
    expect(page.locator("#toasts")).to_contain_text("Moved Oren to Kitchen.")
    puts = [w for w in writes if w[1] == PORTER]
    assert puts[-1] == ("PUT", PORTER, {"room": "kitchen"})
    expect(page.locator("#modal details.wb-charter[data-body=Oren] summary")).to_contain_text("Kitchen")
    expect(page.locator("#modal details.wb-charter[data-body=Oren] summary")).to_contain_text("dealt a cell")


def test_clearing_a_townspersons_station_returns_it_to_the_rule(
        page: Page, ui_base_url: str) -> None:
    _, writes, modal = _open_map(page, ui_base_url)
    svg = modal.locator(".wb-room-map")
    svg.locator(".wb-m-body[data-body=Ysra]").drag_to(svg.locator(".wb-m-cell").nth(0 * 6 + 5))
    expect(page.locator("#toasts")).to_contain_text("Placed Ysra at (0, 5)")
    expect(svg.locator(".wb-m-body[data-body=Ysra]")).to_have_class(re.compile(r"\bauthored\b"))
    modal.locator(".wb-card .wb-charter[data-body=Ysra] .wb-clear-station").click()
    expect(page.locator("#toasts")).to_contain_text("Cleared the station")
    assert ("DELETE", CLERK, {}) in writes
    # Back at her post's anchor: the mark's clause, the row's, and no clear.
    expect(svg.locator(".wb-m-body[data-body=Ysra]")).to_have_class(re.compile(r"\bpost\b"))
    row = modal.locator(".wb-card .wb-charter[data-body=Ysra]")
    expect(row.locator(".wb-charter-source")).to_have_attribute("data-source", "post")
    expect(row.locator(".wb-clear-station")).to_have_count(0)
    expect(row).to_contain_text("hearth")
