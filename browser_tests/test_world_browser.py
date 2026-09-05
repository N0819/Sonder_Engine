"""The World Browser in a real browser: the tree, the card, walking an exit,
the field editors, the Bodies tab's attire editor, and the Raw JSON tab that
keeps the old editors.

Fully mocked at the network boundary. What `node --check` cannot see is the
part worth testing here: that 🌍 opens on Rooms and 👕 on Bodies, that
clicking an exit re-selects the far room in the tree and re-renders the
card, that a room's light chosen from the select is PATCHed and the card
re-renders from the server's answer, that adding an exit sends this room's
full exit list and the far room then shows the doorway, that changing a
garment's state on the Bodies tab sends the WHOLE ledger with every copy of a
spanning garment carrying the new state (never narrowed, never reset), and
that the Raw JSON tab still offers the world table for hand repair.
"""

from __future__ import annotations

import copy
import json
import re
from urllib.parse import urlparse

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
    "shapes": ["rectangle", "round", "l"],
    "corners": ["ne", "se", "sw", "nw"],
    "walls": ["n", "e", "s", "w"],
    "extent": {"min": 2, "max": 24},
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
    ],
    "vocab": VOCAB,
}


def _slice(rid, name, desc, exits, occupants=(), adjacent=None, light="",
           region="", anchors=None, lint=()):
    record = {"name": name, "desc": desc, "notes": "", "light": light,
              "size": "", "exposure": "", "region": region,
              "extent": None, "shape": "", "parts": [],
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
            "occupants": list(occupants), "things": [], "planned_stub": None,
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
                        "attire": ALICE_ATTIRE}],
                      adjacent=[{"to": "hallway", "barrier": "open"}],
                      region="east_wing",
                      anchors={"hearth": {"desc": "the hearth", "dir": "w", "height": "waist"},
                               "oak_table": {"desc": "the oak table"}},
                      lint=KITCHEN_LINT),
    "hallway": _slice("hallway", "Hallway", "A long, dim hallway.",
                      [{"to": "kitchen", "name": "Kitchen", "barrier": "open",
                        "dir": None, "status": "live"}],
                      region="east_wing"),
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


def _grid(rid, slices):
    """A mock of `GET /rooms/{rid}/grid` over the mocked slice: the tier's
    square, each anchor on the wall its bearing names (one pace in when it
    has a height, at its `offset` along the wall when it has one), the
    doorways with a bearing as one cell of their wall, the occupants beside
    the anchor they stand at, the beared neighbour laid beyond its door."""
    room = slices[rid]
    record = room["record"]
    geometry = record["geometry"]
    w, d = geometry["w"], geometry["d"]
    cells = [[x, y] for x in range(w) for y in range(d)]
    rims = {"n": [[x, 0] for x in range(w)], "e": [[w - 1, y] for y in range(d)],
            "s": [[x, d - 1] for x in range(w)], "w": [[0, y] for y in range(d)]}

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
                         "offset": edge.get("offset"), "status": x["status"]})
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
        bodies[o["name"]] = {"cell": cell, "facing": "e" if cell else None, "kind": "cast",
                             "at": at, "near": list(station.get("near") or []),
                             "measured": cell is not None, "source": source}
    return {"frame_id": None,
            "room": {"id": rid, "name": room["name"], "w": w, "d": d, "shape": geometry["shape"],
                     "measured": geometry["measured"], "cells": cells},
            "rims": rims, "anchors": anchors, "doorways": doorways, "bodies": bodies,
            "things": [], "walls": walls, "neighbours": neighbours,
            "lint": list(room.get("lint") or []), "overlays": {}}


def _map(slices):
    """A mock of `GET /map`: the kitchen and the hallway one component (the
    hallway east of the kitchen, the study north of the hallway), the garden
    its own, and a pantry the bearings land on the kitchen -- drawn, flagged."""
    def row(rid, name, offset, w=6, d=6, exits=(), occupants=(), lint=0, collided=False,
            onto=None, via=None):
        return {"id": rid, "name": name, "offset": offset, "w": w, "d": d, "shape": "rectangle",
                "measured": False, "cells": [[x, y] for x in range(w) for y in range(d)],
                "exits": list(exits), "occupants": list(occupants), "lint": lint, "holder": None,
                "collided": collided, "onto": onto, "via": via}
    exit_ = lambda to, dir_, placed=True, barrier="open": {
        "to": to, "name": slices.get(to, {}).get("name", to), "dir": dir_, "barrier": barrier,
        "placed": placed}
    return {"frame_id": None, "location": "Old Manor", "components": [
        {"start": "hallway", "rooms": [
            row("hallway", "Hallway", [0, 0], exits=[exit_("kitchen", "w"), exit_("study", "n", barrier="closed_door"),
                                                    exit_("pantry", "w")], occupants=["Bob"]),
            row("kitchen", "Kitchen", [-7, 1], exits=[exit_("hallway", "e"), exit_("attic", None, False)],
                occupants=["Alice"], lint=2),
            row("study", "Study", [0, -7], exits=[exit_("hallway", "s", barrier="closed_door")],
                occupants=["Nathan"]),
            row("pantry", "Pantry", [-4, 3], w=4, d=4, exits=[exit_("hallway", "e")], lint=1,
                collided=True, onto="kitchen", via="hallway")],
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

    def handle(route) -> None:
        request = route.request
        path = urlparse(request.url).path
        seen.append(path)
        body = {}
        status = 200
        if request.method in ("PATCH", "PUT") and request.post_data:
            payload = json.loads(request.post_data)
            writes.append((request.method, path, payload))
            if request.method == "PUT" and path.startswith("/api/chats/1/bodies/"):
                name = path.split("/")[5]
                station = {"at": payload.get("at"), "near": list(payload.get("near") or [])}
                # The server keeps a `cell` only as two whole numbers, and
                # only when one was sent (null or absent is no pin).
                if isinstance(payload.get("cell"), list) and len(payload["cell"]) == 2:
                    station["cell"] = [int(payload["cell"][0]), int(payload["cell"][1])]
                for room in slices.values():
                    for o in room["occupants"]:
                        if o["name"] == name:
                            o["station"] = station
                for b in index["bodies"]:
                    if b["name"] == name:
                        b["station"] = station
                body = {"name": name, "station": station}
            elif request.method == "PATCH" and path.startswith("/api/chats/1/regions/"):
                rid = path.rsplit("/", 1)[1]
                looks[rid] = payload["look"]
                body = {"id": rid, "name": rid, "brief": "", "look": payload["look"],
                        "rooms": [s for s in slices if slices[s]["region"] == rid]}
            elif request.method == "PATCH" and path.startswith("/api/chats/1/rooms/"):
                rid = path.rsplit("/", 1)[1]
                room = slices[rid]
                for key in ("light", "size", "exposure", "name", "desc", "notes", "region",
                            "shape", "parts", "anchors"):
                    if key in payload:
                        room["record"][key] = payload[key]
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
                body = _grid(rid, slices)
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
    expect(card.locator(".wb-exit", has_text="Garden")).to_have_count(1)
    patches = [w for w in writes if w[0] == "PATCH" and w[1] == "/api/chats/1/rooms/kitchen"]
    # This room's FULL exit list, the standing doorway kept, the new one added.
    assert patches[-1][2]["exits"] == [
        {"to": "hallway", "barrier": "open", "dir": ""},
        {"to": "garden", "barrier": "closed_door", "dir": ""}]
    # Walk through it: the far room shows the doorway back.
    card.locator(".wb-exit .wb-link", has_text="Garden").click()
    expect(card.locator("textarea").first).to_have_value("An overgrown garden.")
    expect(card.locator(".wb-exit", has_text="Kitchen")).to_have_count(1)


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
    look = card.locator(".wb-look input")
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
    expect(card.locator(".wb-look input")).to_have_value("brick and iron under sodium lamps")
    # A room in no region has no look to edit.
    page.locator("#modal .wb-tree .wb-room[data-room=garden]").click()
    expect(card.locator("textarea").first).to_have_value("An overgrown garden.")
    expect(card.locator(".wb-look")).to_have_count(0)


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


# ---- The map editor -----------------------------------------------------------

def test_the_map_renders_the_rooms_cells_anchors_doorway_neighbour_and_bodies(
        page: Page, ui_base_url: str) -> None:
    page_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    seen, _ = _open_story(page, ui_base_url)
    page.locator("#b-world").click()
    modal = page.locator("#modal")
    svg = modal.locator(".wb-room-map")
    expect(svg).to_be_visible()
    assert "/api/chats/1/rooms/kitchen/grid" in seen
    # The bar says where the zoom stands; the tree is still there beneath.
    expect(modal.locator(".wb-map-bar")).to_contain_text("Kitchen")
    expect(modal.locator(".wb-map-bar .wb-map-up")).to_have_text("All rooms")
    expect(modal.locator(".wb-list .wb-tree .wb-room[data-room=kitchen]")).to_be_visible()
    # Six by six cells, the two anchors, the beared doorway, the neighbour
    # laid beyond it, the one body with her facing tick.
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
    # The lint drawn at the thing it concerns: the wall row along the north
    # wall, the bearing row at the doorway (the far room is drawn, so at it).
    expect(svg.locator(".wb-m-lint-wall")).to_have_count(6)
    expect(svg.locator(".wb-m-lint-mark[data-kind=wall_overfull]")).to_have_count(1)
    expect(svg.locator(".wb-m-lint-mark[data-kind=reciprocal_bearing_disagrees]")).to_have_count(1)
    # The doorway the mock cannot place is said in words under the map.
    expect(modal.locator(".wb-map-notes")).to_contain_text("Attic")
    assert page_errors == []


def test_clicking_an_anchor_on_the_map_focuses_its_editor_row(
        page: Page, ui_base_url: str) -> None:
    _open_story(page, ui_base_url)
    page.locator("#b-world").click()
    modal = page.locator("#modal")
    modal.locator(".wb-room-map .wb-m-anchor[data-anchor=hearth]").click()
    row = modal.locator(".wb-card .wb-anchor[data-anchor=hearth]")
    expect(row).to_have_class(re.compile(r"\bwb-focus\b"))
    expect(row.locator("input").first).to_be_focused()
    # A doorway opens its exit row; a body its station row; Enter on a focused
    # anchor does what the click does.
    modal.locator(".wb-room-map .wb-m-doorway[data-exit=hallway]").click()
    expect(modal.locator(".wb-card .wb-exit[data-exit=hallway]")).to_have_class(re.compile(r"\bwb-focus\b"))
    modal.locator(".wb-room-map .wb-m-body[data-body=Alice]").click()
    expect(modal.locator(".wb-card .wb-body[data-body=Alice]")).to_have_class(re.compile(r"\bwb-focus\b"))
    modal.locator(".wb-room-map .wb-m-anchor[data-anchor=oak_table]").focus()
    page.keyboard.press("Enter")
    expect(modal.locator(".wb-card .wb-anchor[data-anchor=oak_table]")).to_have_class(re.compile(r"\bwb-focus\b"))


def test_dragging_an_anchor_to_another_wall_changes_its_bearing_and_offset(
        page: Page, ui_base_url: str) -> None:
    _, writes = _open_story(page, ui_base_url)
    page.locator("#b-world").click()
    modal = page.locator("#modal")
    svg = modal.locator(".wb-room-map")
    # The hearth stands on the west wall; drop it on cell (3, 0) -- the
    # north wall, three paces from its west end. Cells are listed x-major.
    hearth = svg.locator(".wb-m-anchor[data-anchor=hearth]")
    target = svg.locator(".wb-m-cell").nth(3 * 6 + 0)
    hearth.drag_to(target)
    expect(page.locator("#toasts")).to_contain_text("Saved.")
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
    expect(page.locator("#toasts")).to_contain_text("Saved.")
    patches = [w for w in writes if w[0] == "PATCH" and "anchors" in w[2]]
    assert patches[-1][2]["anchors"]["hearth"]["dir"] == ""
    assert patches[-1][2]["anchors"]["hearth"]["offset"] is None
    assert patches[-1][2]["anchors"]["hearth"]["cell"] == [2, 2]
    # And dragged back onto a wall, the pin is let go with the wall written.
    modal.locator(".wb-room-map .wb-m-anchor[data-anchor=hearth]").drag_to(
        modal.locator(".wb-room-map .wb-m-cell").nth(0 * 6 + 4))
    expect(page.locator("#toasts")).to_contain_text("Saved.")
    patches = [w for w in writes if w[0] == "PATCH" and "anchors" in w[2]]
    sent = patches[-1][2]["anchors"]["hearth"]
    assert sent["dir"] == "w" and sent["cell"] is None and sent["offset"] is not None


def test_dragging_a_doorway_along_its_wall_sets_the_exits_offset(
        page: Page, ui_base_url: str) -> None:
    _, writes = _open_story(page, ui_base_url)
    page.locator("#b-world").click()
    modal = page.locator("#modal")
    svg = modal.locator(".wb-room-map")
    # The doorway to the hallway is on the east wall; drop it beside cell
    # (5, 5), the wall's south end.
    svg.locator(".wb-m-doorway[data-exit=hallway]").drag_to(svg.locator(".wb-m-cell").nth(5 * 6 + 5))
    expect(page.locator("#toasts")).to_contain_text("Saved.")
    patches = [w for w in writes if w[0] == "PATCH" and "exits" in w[2]]
    assert patches, writes
    # This room's full exit list, the one doorway carrying its place along
    # the wall -- and only that one, so the others keep whatever they had.
    assert patches[-1][2]["exits"] == [{"to": "hallway", "barrier": "open", "dir": "", "offset": 1.0}]


def test_dragging_a_body_onto_an_anchor_sets_its_station(page: Page, ui_base_url: str) -> None:
    _, writes = _open_story(page, ui_base_url)
    page.locator("#b-world").click()
    modal = page.locator("#modal")
    svg = modal.locator(".wb-room-map")
    # Alice stands at the oak table; drop her on the hearth: `at` for prose
    # AND the cell she landed on (the hearth's cell (1, 2): one pace in from
    # the west wall's middle, as the mock lays a standing thing).
    svg.locator(".wb-m-body[data-body=Alice]").drag_to(svg.locator(".wb-m-anchor[data-anchor=hearth]"))
    expect(page.locator("#toasts")).to_contain_text("Saved.")
    puts = [w for w in writes if w[0] == "PUT" and w[1] == "/api/chats/1/bodies/Alice/station"]
    assert puts and puts[-1][2] == {"at": "hearth", "near": [], "cell": [1, 2]}
    # The card's station row and the map agree with the server's answer.
    expect(modal.locator(".wb-card .wb-body[data-body=Alice] select")).to_have_value("hearth")
    expect(modal.locator(".wb-card .wb-body[data-body=Alice] .wb-station-cell")).to_contain_text("(1, 2)")
    expect(svg.locator(".wb-m-body[data-body=Alice]")).to_have_count(1)
    expect(svg.locator(".wb-m-body[data-body=Alice]")).to_have_class(re.compile(r"\bpinned\b"))
    # Dropped on a plain cell, she is pinned to it and `at` is cleared (the
    # owner, 2026-09-04: "why are characters and personas locked to
    # stations?").
    svg.locator(".wb-m-body[data-body=Alice]").drag_to(svg.locator(".wb-m-cell").nth(4 * 6 + 4))
    expect(page.locator("#toasts")).to_contain_text("Saved.")
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
    _, writes = _open_story(page, ui_base_url)
    page.locator("#b-world").click()
    modal = page.locator("#modal")
    svg = modal.locator(".wb-room-map")
    # Cell (2, 4): inside the room, off every wall, not under the table
    # (which the mock stands in the middle). Cells are listed x-major.
    svg.locator(".wb-m-anchor[data-anchor=hearth]").drag_to(svg.locator(".wb-m-cell").nth(2 * 6 + 4))
    expect(page.locator("#toasts")).to_contain_text("Saved.")
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


def test_zooming_out_to_the_structure_map_and_into_another_room(
        page: Page, ui_base_url: str) -> None:
    seen, _ = _open_story(page, ui_base_url)
    page.locator("#b-world").click()
    modal = page.locator("#modal")
    modal.locator(".wb-map-bar .wb-map-up").click()
    structure = modal.locator(".wb-structure-map")
    expect(structure).to_be_visible()
    assert "/api/chats/1/map" in seen
    expect(modal.locator(".wb-map-bar")).to_contain_text("Every room, placed by bearing")
    # Every room as a box: the two components side by side, the occupied
    # rooms marked, the exits as ticks, and the pantry DRAWN on the kitchen.
    expect(structure.locator(".wb-sm-room")).to_have_count(5)
    expect(structure.locator(".wb-sm-room[data-room=kitchen]")).to_have_class(re.compile(r"\boccupied\b"))
    expect(structure.locator(".wb-sm-room[data-room=kitchen] .wb-sm-who")).to_have_text("Alice")
    expect(structure.locator(".wb-sm-room[data-room=hallway] .wb-sm-exit")).to_have_count(3)
    expect(structure.locator(".wb-sm-room[data-room=pantry]")).to_have_class(re.compile(r"\bcollided\b"))
    expect(structure.locator(".wb-sm-room[data-room=kitchen] .wb-sm-lint")).to_have_count(1)
    # The kitchen's exit to the attic has no bearing: counted, not drawn.
    expect(structure.locator(".wb-sm-room[data-room=kitchen] .wb-sm-unbeared")).to_have_text("?1")
    # Click the hallway: its grid on the left, its card on the right.
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
