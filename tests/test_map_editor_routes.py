"""The map editor's create/remove/move routes (`web/world_routes.py`,
2026-09-05; the owner: "this room editor feels very incomplete").

Every new route and every refusal: a room minted from the map through a
chosen wall (and refused removal while anything stands in it, the registry
retiring the id); a doorway opened, edited as ONE object from either room
and closed (the passage record); a thing minted, given light and sound, and
removed; a presence placed and removed; any body moved between rooms and
posed; a region created and renamed; composite parts through the room
PATCH, refused outside the box; and the overlays the grid carries. Each
refusal names its reason. The fixtures are `tests/test_world_routes.py`'s.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from web import app as app_module
from web import guest_access as guest

from test_world_routes import _lay_out, _registry, _scene, story  # noqa: F401


@pytest.fixture
def client(temp_db):
    guest.reset_host_account()
    with TestClient(app_module.app) as c:
        response = c.post("/api/auth/setup",
                          json={"username": "host", "password": "pw12345"})
        assert response.status_code == 200, response.text
        yield c
    guest.reset_host_account()


# ---------------------------------------------------------------------------
# Rooms
# ---------------------------------------------------------------------------

class TestRoomCreateAndRemove:
    def test_a_room_is_minted_off_a_wall_with_one_doorway_and_inherits_the_region(
            self, client, story, temp_db):
        cid = story["chat_id"]
        scene = _scene(temp_db, cid)
        scene["rooms"]["kitchen"]["region"] = "east_wing"
        temp_db.wset(cid, "scene", scene)
        r = client.post(f"/api/chats/{cid}/rooms",
                        json={"name": "Scullery", "from": "kitchen", "dir": "s",
                              "barrier": "closed_door", "extent": {"w": 4, "d": 4}})
        assert r.status_code == 200, r.text
        rid = r.json()["id"]
        assert rid == "scullery" and r.json()["name"] == "Scullery"
        scene = _scene(temp_db, cid)
        room = scene["rooms"][rid]
        assert room["region"] == "east_wing"
        # The size word follows the measurement, as the room PATCH's does.
        assert room["extent"] == {"w": 4, "d": 4} and room["size"] == "small"
        # ONE doorway: a passage record, both edges naming it, the bearing
        # from the kitchen and its opposite back.
        pid = [e for e in scene["rooms"]["kitchen"]["adjacent"] if e["to"] == rid][0]["passage"]
        assert scene["passages"][pid]["rooms"] == ["kitchen", rid]
        assert scene["passages"][pid]["barrier"] == "closed_door"
        back = [e for e in room["adjacent"] if e["to"] == "kitchen"][0]
        assert back["dir"] == "n" and back["barrier"] == "closed_door" and back["passage"] == pid
        # The registry projection registered it.
        assert rid in _registry(temp_db, cid)
        # The map lays it south of the kitchen.
        data = client.get(f"/api/chats/{cid}/map").json()
        rows = {row["id"]: row for comp in data["components"] for row in comp["rooms"]}
        assert rows[rid]["placed_via"] == "kitchen"
        assert rows[rid]["offset"][1] > rows["kitchen"]["offset"][1]

    def test_a_name_is_required_the_id_never_reuses_a_spent_one_and_the_wall_is_checked(
            self, client, story, temp_db):
        cid = story["chat_id"]
        r = client.post(f"/api/chats/{cid}/rooms", json={"name": "  "})
        assert r.status_code == 400 and "needs a name" in r.text
        # `old_wing` is retired in the registry: the id is spent.
        r = client.post(f"/api/chats/{cid}/rooms", json={"name": "Old Wing"})
        assert r.status_code == 200 and r.json()["id"] == "old_wing_2"
        r = client.post(f"/api/chats/{cid}/rooms",
                        json={"name": "Loft", "from": "nowhere"})
        assert r.status_code == 400 and "Known rooms" in r.text
        r = client.post(f"/api/chats/{cid}/rooms",
                        json={"name": "Loft", "from": "kitchen", "dir": "up"})
        assert r.status_code == 400 and "dir must be one of" in r.text
        r = client.post(f"/api/chats/{cid}/rooms",
                        json={"name": "Loft", "from": "kitchen", "barrier": "portcullis"})
        assert r.status_code == 400 and "barrier must be one of" in r.text
        # No `from`: an unjoined room, in no region.
        r = client.post(f"/api/chats/{cid}/rooms", json={"name": "Loft", "shape": "round"})
        assert r.status_code == 200
        assert _scene(temp_db, cid)["rooms"]["loft"].get("shape") == "round"
        assert "region" not in _scene(temp_db, cid)["rooms"]["loft"]

    def test_a_room_is_refused_removal_while_anything_stands_in_it_naming_them(
            self, client, story, temp_db):
        cid = story["chat_id"]
        r = client.delete(f"/api/chats/{cid}/rooms/kitchen")
        assert r.status_code == 400
        assert "bodies: Alice" in r.text and "move them out" in r.text
        # The study holds the player AND a thing (the TARDIS).
        r = client.delete(f"/api/chats/{cid}/rooms/study")
        assert r.status_code == 400 and "bodies: Nathan" in r.text and "things: tardis" in r.text
        r = client.delete(f"/api/chats/{cid}/rooms/attic")
        assert r.status_code == 400 and "No room 'attic'" in r.text

    def test_an_empty_room_is_removed_with_its_edges_and_passage_and_retired(
            self, client, story, temp_db):
        cid = story["chat_id"]
        # Give the garden a doorway with a passage first.
        r = client.post(f"/api/chats/{cid}/doorways",
                        json={"room": "garden", "to": "cellar", "dir": "s"})
        assert r.status_code == 200, r.text
        pid = r.json()["passage"]
        # Move Diana out of the cellar? The GARDEN is the empty one.
        r = client.delete(f"/api/chats/{cid}/rooms/garden")
        assert r.status_code == 200 and r.json() == {"removed": "garden", "retired": True}
        scene = _scene(temp_db, cid)
        assert "garden" not in scene["rooms"]
        assert not any(e["to"] == "garden" for e in scene["rooms"]["cellar"]["adjacent"])
        assert pid not in (scene.get("passages") or {})
        assert _registry(temp_db, cid)["garden"]["retired_turn_id"] is not None
        # And the index lists it as spent.
        groups = client.get(f"/api/chats/{cid}/rooms").json()["groups"]
        assert "garden" in [row["id"] for row in groups["retired"]]


class TestCompositeParts:
    def test_cell_parts_land_through_the_room_patch_and_the_grid_is_the_union(
            self, client, story, temp_db):
        cid = story["chat_id"]
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen",
                         json={"extent": {"w": 9, "d": 6}, "shape": "composite",
                               "parts": [{"w": 9, "d": 2, "at": "nw"},
                                         {"w": 3, "d": 6, "at": [3, 0]}]})
        assert r.status_code == 200, r.text
        record = r.json()["record"]
        assert record["shape"] == "composite"
        assert record["parts"] == [{"w": 9, "d": 2, "at": "nw"}, {"w": 3, "d": 6, "at": [3, 0]}]
        view = client.get(f"/api/chats/{cid}/rooms/kitchen/grid").json()
        assert len(view["room"]["cells"]) == 18 + 12
        assert [0, 3] not in view["room"]["cells"] and [4, 5] in view["room"]["cells"]
        # The lint is quiet: the stem touches the bar.
        assert r.json()["lint"] == []

    def test_a_part_outside_the_box_is_refused_naming_the_box_and_apart_parts_are_a_row(
            self, client, story, temp_db):
        cid = story["chat_id"]
        client.patch(f"/api/chats/{cid}/rooms/kitchen",
                     json={"extent": {"w": 8, "d": 4}, "shape": "composite"})
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen",
                         json={"parts": [{"w": 3, "d": 3, "at": [6, 2]}]})
        assert r.status_code == 400
        assert "box of 8 by 4 paces" in r.text and "x in 0..7" in r.text
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen",
                         json={"parts": [{"w": 3, "d": 3, "at": [-1, 0]}]})
        assert r.status_code == 400 and "starts outside" in r.text
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen",
                         json={"parts": [{"w": 3, "d": 3, "at": "middle"}]})
        assert r.status_code == 400 and "corner of the box" in r.text and "[x, y]" in r.text
        # Two parts that do not touch: a row beside the shape, not a refusal.
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen",
                         json={"parts": [{"w": 2, "d": 2, "at": "nw"}, {"w": 2, "d": 2, "at": "se"}]})
        assert r.status_code == 200
        kinds = [row["kind"] for row in r.json()["lint"]]
        assert kinds == ["parts_disconnected"]
        assert r.json()["lint"][0]["field"] == "shape"
        assert "vocab" not in r.json()
        assert "composite" in client.get(f"/api/chats/{cid}/rooms").json()["vocab"]["shapes"]
        assert client.get(f"/api/chats/{cid}/rooms").json()["vocab"]["part_shapes"] == ["l", "composite"]


# ---------------------------------------------------------------------------
# Doorways: one object from either room
# ---------------------------------------------------------------------------

class TestDoorways:
    def test_a_doorway_is_opened_edited_from_either_room_and_closed(
            self, client, story, temp_db):
        cid = story["chat_id"]
        r = client.post(f"/api/chats/{cid}/doorways",
                        json={"room": "kitchen", "to": "garden", "barrier": "open_door",
                              "dir": "n", "offset": 0.25, "name": "the back door"})
        assert r.status_code == 200, r.text
        pid = r.json()["passage"]
        scene = _scene(temp_db, cid)
        assert scene["passages"][pid] == {"rooms": ["kitchen", "garden"], "barrier": "open_door",
                                          "name": "the back door"}
        k = [e for e in scene["rooms"]["kitchen"]["adjacent"] if e["to"] == "garden"][0]
        g = [e for e in scene["rooms"]["garden"]["adjacent"] if e["to"] == "kitchen"][0]
        assert (k["dir"], g["dir"]) == ("n", "s")
        assert k["offset"] == 0.25 == g["offset"]
        assert k["name"] == "the back door" == g["name"]
        # Edited FROM THE GARDEN: the same object changes on both sides.
        r = client.patch(f"/api/chats/{cid}/doorways/garden/kitchen",
                         json={"barrier": "closed_door", "material": "oak", "width": 2,
                               "offset": 0.75})
        assert r.status_code == 200, r.text
        scene = _scene(temp_db, cid)
        assert scene["passages"][pid]["barrier"] == "closed_door"
        assert scene["passages"][pid]["material"] == "oak" and scene["passages"][pid]["width"] == 2
        for room, to in (("kitchen", "garden"), ("garden", "kitchen")):
            edge = [e for e in scene["rooms"][room]["adjacent"] if e["to"] == to][0]
            assert edge["barrier"] == "closed_door" and edge["material"] == "oak"
            assert edge["width"] == 2 and edge["offset"] == 0.75
        # The grid says so from either side, two cells wide.
        for room, to in (("kitchen", "garden"), ("garden", "kitchen")):
            view = client.get(f"/api/chats/{cid}/rooms/{room}/grid").json()
            door = [d for d in view["doorways"] if d["to"] == to][0]
            assert door["passage"] == pid and door["barrier"] == "closed_door"
            assert door["label"] == "the back door" and door["material"] == "oak"
            assert door["width"] == 2 and len(door["cells"]) == 2
        # A doorway already standing is not opened twice.
        r = client.post(f"/api/chats/{cid}/doorways", json={"room": "garden", "to": "kitchen"})
        assert r.status_code == 400 and "already stands" in r.text
        # Closed: both edges and the record.
        r = client.delete(f"/api/chats/{cid}/doorways/garden/kitchen")
        assert r.status_code == 200 and r.json()["removed"] == ["garden", "kitchen"]
        scene = _scene(temp_db, cid)
        assert pid not in (scene.get("passages") or {})
        assert not any(e["to"] == "garden" for e in scene["rooms"]["kitchen"]["adjacent"])
        assert not any(e["to"] == "kitchen" for e in scene["rooms"]["garden"]["adjacent"])
        r = client.delete(f"/api/chats/{cid}/doorways/garden/kitchen")
        assert r.status_code == 400 and "no doorway stands" in r.text

    def test_a_far_declared_doorway_is_edited_and_dragged_from_this_room(
            self, client, story, temp_db):
        """The kitchen's edge to the cellar stands on the kitchen's side
        alone; the cellar can now edit it -- a passage is minted from the
        standing edge and the cellar's edge with it."""
        cid = story["chat_id"]
        scene = _scene(temp_db, cid)
        scene["rooms"]["cellar"]["adjacent"] = []
        for edge in scene["rooms"]["kitchen"]["adjacent"]:
            if edge["to"] == "cellar":
                edge["dir"] = "s"
        temp_db.wset(cid, "scene", scene)
        view = client.get(f"/api/chats/{cid}/rooms/cellar/grid").json()
        door = [d for d in view["doorways"] if d["to"] == "kitchen"][0]
        assert door["declared_here"] is False and door["passage"] is None
        r = client.patch(f"/api/chats/{cid}/doorways/cellar/kitchen",
                         json={"offset": 1.0, "barrier": "open_door"})
        assert r.status_code == 200, r.text
        scene = _scene(temp_db, cid)
        c = [e for e in scene["rooms"]["cellar"]["adjacent"] if e["to"] == "kitchen"][0]
        k = [e for e in scene["rooms"]["kitchen"]["adjacent"] if e["to"] == "cellar"][0]
        assert c["dir"] == "n" and c["offset"] == 1.0 == k["offset"]
        assert c["barrier"] == "open_door" == k["barrier"]
        assert c["passage"] == k["passage"] == "cellar|kitchen"
        assert scene["passages"]["cellar|kitchen"]["barrier"] == "open_door"

    def test_the_refusals_name_their_reason(self, client, story):
        cid = story["chat_id"]
        r = client.post(f"/api/chats/{cid}/doorways", json={"room": "kitchen", "to": "kitchen"})
        assert r.status_code == 400 and "into itself" in r.text
        r = client.post(f"/api/chats/{cid}/doorways", json={"room": "kitchen", "to": "attic"})
        assert r.status_code == 400 and "No room 'attic'" in r.text
        r = client.post(f"/api/chats/{cid}/doorways", json={"room": "kitchen"})
        assert r.status_code == 400 and "joins two rooms" in r.text
        r = client.patch(f"/api/chats/{cid}/doorways/kitchen/garden", json={"barrier": "open"})
        assert r.status_code == 400 and "no doorway stands" in r.text
        r = client.patch(f"/api/chats/{cid}/doorways/kitchen/hallway", json={"colour": "red"})
        assert r.status_code == 400 and "a doorway has the fields" in r.text
        r = client.patch(f"/api/chats/{cid}/doorways/kitchen/hallway", json={"width": 40})
        assert r.status_code == 400 and "between 1 and 24" in r.text
        r = client.patch(f"/api/chats/{cid}/doorways/kitchen/hallway", json={"offset": 1.5})
        assert r.status_code == 400 and "between 0 and 1" in r.text
        r = client.patch(f"/api/chats/{cid}/doorways/kitchen/hallway", json={"vertical": "sideways"})
        assert r.status_code == 400 and "up or down" in r.text
        r = client.patch(f"/api/chats/{cid}/doorways/kitchen/hallway", json={"barrier": "gate"})
        assert r.status_code == 400 and "barrier must be one of" in r.text

    def test_the_room_patchs_exit_barrier_still_speaks_for_the_passage(
            self, client, story, temp_db):
        cid = story["chat_id"]
        client.patch(f"/api/chats/{cid}/doorways/kitchen/hallway", json={"barrier": "open_door"})
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen",
                         json={"exits": [{"to": "hallway", "barrier": "closed_door"},
                                         {"to": "cellar", "barrier": "closed_door"}]})
        assert r.status_code == 200, r.text
        scene = _scene(temp_db, cid)
        assert scene["passages"]["hallway|kitchen"]["barrier"] == "closed_door"
        h = [e for e in scene["rooms"]["hallway"]["adjacent"] if e["to"] == "kitchen"][0]
        assert h["barrier"] == "closed_door"
        # Removing the exit removes the record.
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen",
                         json={"exits": [{"to": "cellar", "barrier": "closed_door"}]})
        assert r.status_code == 200
        assert "hallway|kitchen" not in (_scene(temp_db, cid).get("passages") or {})


# ---------------------------------------------------------------------------
# Things
# ---------------------------------------------------------------------------

class TestThings:
    def test_a_thing_is_minted_lit_pointed_run_and_removed(self, client, story, temp_db):
        cid = story["chat_id"]
        _lay_out(temp_db, cid)
        r = client.post(f"/api/chats/{cid}/rooms/kitchen/entities",
                        json={"name": "Brass Lamp", "kind": "lamp", "cell": [2, 1]})
        assert r.status_code == 200, r.text
        eid = r.json()["id"]
        assert eid == "brass_lamp"
        scene = _scene(temp_db, cid)
        assert scene["entities"][eid] == {"name": "Brass Lamp", "kind": "lamp", "description": ""}
        assert scene["positions"][eid] == "kitchen"
        assert scene["stations"][eid]["cell"] == [2, 1]
        # The grid draws it at its cell, placed by the cell.
        view = client.get(f"/api/chats/{cid}/rooms/kitchen/grid").json()
        thing = [t for t in view["things"] if t["id"] == eid][0]
        assert thing["cell"] == [2, 1] and thing["source"] == "cell"
        # Light and sound: the engine's vocabularies, `state` flags, a cone
        # pointed at an anchor.
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen/entities/{eid}",
                         json={"light_source": "lit", "light_shape": "cone",
                               "light_height": "full", "steadiness": "flickering",
                               "pointed_at": "hearth", "sound_source": "faint",
                               "running": False})
        assert r.status_code == 200, r.text
        ent = _scene(temp_db, cid)["entities"][eid]
        assert ent["light_source"] == "lit" and ent["light_shape"] == "cone"
        assert ent["light_height"] == "full" and ent["steadiness"] == "flickering"
        assert ent["sound_source"] == "faint"
        assert ent["state"] == {"pointed_at": "hearth", "running": False}
        record = [t for t in r.json()["things"] if t["id"] == eid][0]["record"]
        assert record["light_shape"] == "cone" and record["sound_source"] == "faint"
        # The map's light sources carry the engine's height word, so a
        # full-height source draws as a ring.
        view = client.get(f"/api/chats/{cid}/rooms/kitchen/grid").json()
        source = [s for s in view["light_sources"] if s["id"] == eid][0]
        assert source["height"] == "full" and source["shape"] == "cone"
        assert "light" in view["overlays"]
        # A bearing and an entity id are pointable too; prose is not.
        for target in ("ne", "oak_table", "tardis"):
            r = client.patch(f"/api/chats/{cid}/rooms/kitchen/entities/{eid}",
                             json={"pointed_at": target})
            assert r.status_code == 200, (target, r.text)
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen/entities/{eid}",
                         json={"pointed_at": "the far corner"})
        assert r.status_code == 400 and "pointed_at must be a bearing" in r.text
        for field, bad in (("light_shape", "beam"), ("light_height", "ceiling"),
                           ("steadiness", "guttering"), ("sound_source", "roar")):
            r = client.patch(f"/api/chats/{cid}/rooms/kitchen/entities/{eid}", json={field: bad})
            assert r.status_code == 400 and f"{field} must be one of" in r.text, field
        # Moved to another room, the station (a cell in the OLD grid) goes.
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen/entities/{eid}", json={"room": "hallway"})
        assert r.status_code == 200
        assert eid not in _scene(temp_db, cid).get("stations", {})
        # Removed: entity, position, station.
        r = client.delete(f"/api/chats/{cid}/rooms/hallway/entities/{eid}")
        assert r.status_code == 200
        scene = _scene(temp_db, cid)
        assert eid not in scene["entities"] and eid not in scene["positions"]

    def test_the_refusals(self, client, story, temp_db):
        cid = story["chat_id"]
        r = client.post(f"/api/chats/{cid}/rooms/kitchen/entities", json={"name": ""})
        assert r.status_code == 400 and "needs a name" in r.text
        r = client.post(f"/api/chats/{cid}/rooms/kitchen/entities",
                        json={"name": "Jar", "cell": [40, 0]})
        assert r.status_code == 400 and "outside the room" in r.text
        # An anchor-placed thing is the anchor editor's; a body is not a thing.
        r = client.delete(f"/api/chats/{cid}/rooms/kitchen/entities/oak_table")
        assert r.status_code == 400 and "placed as an anchor" in r.text
        scene = _scene(temp_db, cid)
        scene["entities"]["Alice"] = {"name": "Alice", "kind": "person"}
        temp_db.wset(cid, "scene", scene)
        r = client.delete(f"/api/chats/{cid}/rooms/kitchen/entities/Alice")
        assert r.status_code == 400 and "is a body" in r.text
        r = client.delete(f"/api/chats/{cid}/rooms/kitchen/entities/tardis")
        assert r.status_code == 400 and "does not stand in 'kitchen'" in r.text
        r = client.delete(f"/api/chats/{cid}/rooms/kitchen/entities/ghost")
        assert r.status_code == 404

    def test_a_thing_is_pinned_by_the_station_route_like_a_body(self, client, story, temp_db):
        cid = story["chat_id"]
        _lay_out(temp_db, cid)
        r = client.put(f"/api/chats/{cid}/bodies/tardis/station", json={"cell": [1, 1]})
        assert r.status_code == 200, r.text
        assert _scene(temp_db, cid)["stations"]["tardis"]["cell"] == [1, 1]
        view = client.get(f"/api/chats/{cid}/rooms/study/grid").json()
        assert [t for t in view["things"] if t["id"] == "tardis"][0]["cell"] == [1, 1]


# ---------------------------------------------------------------------------
# Bodies: presences, rooms, poses
# ---------------------------------------------------------------------------

class TestBodies:
    def test_a_presence_is_placed_moved_posed_and_removed(self, client, story, temp_db):
        cid = story["chat_id"]
        _lay_out(temp_db, cid)
        r = client.post(f"/api/chats/{cid}/rooms/kitchen/presences",
                        json={"name": "The Cook", "cell": [3, 2]})
        assert r.status_code == 200, r.text
        scene = _scene(temp_db, cid)
        assert scene["positions"]["The Cook"] == "kitchen"
        assert scene["stations"]["The Cook"]["cell"] == [3, 2]
        assert "The Cook" not in scene["entities"]
        bodies = {b["name"]: b for b in client.get(f"/api/chats/{cid}/rooms").json()["bodies"]}
        assert bodies["The Cook"]["kind"] == "presence"
        # Twice is refused, as is anyone already standing somewhere; and the
        # player's or a cast member's name is refused even when nothing
        # places them -- they are moved, not created.
        r = client.post(f"/api/chats/{cid}/rooms/hallway/presences", json={"name": "the cook"})
        assert r.status_code == 400 and "already stands in 'kitchen'" in r.text
        r = client.post(f"/api/chats/{cid}/rooms/hallway/presences", json={"name": "Alice"})
        assert r.status_code == 400 and "already stands in 'kitchen'" in r.text
        scene = _scene(temp_db, cid)
        scene["positions"].pop("Nathan")
        scene["positions"].pop("Bob")
        temp_db.wset(cid, "scene", scene)
        r = client.post(f"/api/chats/{cid}/rooms/hallway/presences", json={"name": "Nathan"})
        assert r.status_code == 400 and "is the player" in r.text
        r = client.post(f"/api/chats/{cid}/rooms/hallway/presences", json={"name": "Bob"})
        assert r.status_code == 400 and "is the cast" in r.text
        scene = _scene(temp_db, cid)
        scene["positions"].update({"Nathan": "study", "Bob": "hallway"})
        temp_db.wset(cid, "scene", scene)
        # Posed: the engine's own cleaning; a null idiom is empty.
        r = client.put(f"/api/chats/{cid}/bodies/The Cook/pose",
                       json={"posture": "sitting", "support": "hearth", "constraint": "none"})
        assert r.status_code == 200, r.text
        pose = _scene(temp_db, cid)["poses"]["The Cook"]
        assert pose["posture"] == "sitting" and pose["support"] == "hearth"
        assert pose["constraint"] == ""
        assert r.json()["pose"]["posture"] == "sitting"
        r = client.put(f"/api/chats/{cid}/bodies/The Cook/pose", json={"stance": "wide"})
        assert r.status_code == 400 and "a pose has the fields" in r.text
        r = client.put(f"/api/chats/{cid}/bodies/The Cook/pose", json={"posture": ""})
        assert r.status_code == 200 and "The Cook" not in _scene(temp_db, cid).get("poses", {})
        # Moved between rooms: the cell (a place in the old grid) goes.
        r = client.put(f"/api/chats/{cid}/bodies/The Cook/room", json={"room": "hallway"})
        assert r.status_code == 200 and r.json()["room"] == "hallway"
        scene = _scene(temp_db, cid)
        assert scene["positions"]["The Cook"] == "hallway"
        assert "cell" not in (scene["stations"].get("The Cook") or {})
        r = client.put(f"/api/chats/{cid}/bodies/The Cook/room", json={"room": "attic"})
        assert r.status_code == 400 and "Known rooms" in r.text
        r = client.put(f"/api/chats/{cid}/bodies/The Cook/room", json={"room": ""})
        assert r.status_code == 400 and "needs a room" in r.text
        # Removed: only a presence can be.
        r = client.delete(f"/api/chats/{cid}/bodies/Nathan")
        assert r.status_code == 400 and "is the player" in r.text
        r = client.delete(f"/api/chats/{cid}/bodies/Alice")
        assert r.status_code == 400 and "is the cast" in r.text
        r = client.delete(f"/api/chats/{cid}/bodies/tardis")
        assert r.status_code == 400 and "is a thing" in r.text
        r = client.delete(f"/api/chats/{cid}/bodies/The Cook")
        assert r.status_code == 200 and r.json() == {"removed": "The Cook"}
        scene = _scene(temp_db, cid)
        assert "The Cook" not in scene["positions"] and "The Cook" not in scene["stations"]
        r = client.delete(f"/api/chats/{cid}/bodies/The Cook")
        assert r.status_code == 400 and "stands in no room" in r.text

    def test_the_player_and_the_cast_move_by_name_and_a_pinned_pose_detail_is_dropped(
            self, client, story, temp_db):
        cid = story["chat_id"]
        scene = _lay_out(temp_db, cid)
        scene["stations"]["Alice"]["cell"] = [2, 2]
        scene["poses"] = {"Bob": {"posture": "standing", "detail": "holding Alice by the arm"}}
        temp_db.wset(cid, "scene", scene)
        r = client.put(f"/api/chats/{cid}/bodies/Nathan/room", json={"room": "kitchen"})
        assert r.status_code == 200 and r.json()["kind"] == "player"
        assert _scene(temp_db, cid)["positions"]["Nathan"] == "kitchen"
        r = client.put(f"/api/chats/{cid}/bodies/alice/room", json={"room": "hallway"})
        assert r.status_code == 200
        scene = _scene(temp_db, cid)
        assert scene["positions"]["Alice"] == "hallway"
        assert "cell" not in scene["stations"].get("Alice", {})
        # Bob's pose detail held Alice, who moved: the clause is dropped
        # (`invalidate_moved_body_pose_details`, the cast route's sibling).
        assert "Alice" not in (scene["poses"]["Bob"]["detail"] or "")
        r = client.put(f"/api/chats/{cid}/bodies/Nobody/room", json={"room": "kitchen"})
        assert r.status_code == 400 and "stands in no room" in r.text
        r = client.put(f"/api/chats/{cid}/bodies/Nobody/pose", json={"posture": "sitting"})
        assert r.status_code == 400 and "no pose" in r.text

    def test_the_vocab_carries_the_pose_fields_and_the_source_sets(self, client, story):
        vocab = client.get(f"/api/chats/{story['chat_id']}/rooms").json()["vocab"]
        from world.spatial import (_EYE_RANK, _POSE_FIELDS, LIGHT_HEIGHTS, LIGHT_SHAPES,
                                   SOUND_LEVELS, STEADINESS)
        assert vocab["pose_fields"] == list(_POSE_FIELDS)
        assert vocab["postures"] == list(_EYE_RANK)
        assert vocab["light_shapes"] == list(LIGHT_SHAPES)
        assert vocab["light_heights"] == list(LIGHT_HEIGHTS)
        assert vocab["steadiness"] == list(STEADINESS)
        assert vocab["sound_levels"] == list(SOUND_LEVELS)


# ---------------------------------------------------------------------------
# Regions
# ---------------------------------------------------------------------------

class TestRegions:
    def test_a_region_is_created_renamed_and_a_room_moved_into_it_survives_commit(
            self, client, story, temp_db):
        cid = story["chat_id"]
        r = client.post(f"/api/chats/{cid}/regions", json={"name": "The East Wing"})
        assert r.status_code == 200, r.text
        assert r.json()["id"] == "the_east_wing" and r.json()["name"] == "The East Wing"
        assert r.json()["rooms"] == []
        # Idempotent: the same name again is the same region.
        r2 = client.post(f"/api/chats/{cid}/regions", json={"name": "the east wing"})
        assert r2.status_code == 200 and r2.json()["id"] == "the_east_wing"
        r = client.post(f"/api/chats/{cid}/regions", json={"name": ""})
        assert r.status_code == 400 and "needs a name" in r.text
        # The vocab offers it; a room moves into it through its own field.
        vocab = client.get(f"/api/chats/{cid}/rooms").json()["vocab"]
        assert {"id": "the_east_wing", "name": "The East Wing", "look": ""} in vocab["regions"]
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen", json={"region": "the_east_wing"})
        assert r.status_code == 200 and r.json()["record"]["region"] == "the_east_wing"
        # Renamed: the display name alone; the room's field is untouched.
        r = client.patch(f"/api/chats/{cid}/regions/the_east_wing", json={"name": "East Wing"})
        assert r.status_code == 200 and r.json()["name"] == "East Wing"
        assert r.json()["rooms"] == ["kitchen"]
        assert _scene(temp_db, cid)["rooms"]["kitchen"]["region"] == "the_east_wing"
        r = client.patch(f"/api/chats/{cid}/regions/the_east_wing", json={"name": " "})
        assert r.status_code == 400 and "needs a name" in r.text
        r = client.patch(f"/api/chats/{cid}/regions/the_east_wing", json={})
        assert r.status_code == 400
        # An authored region survives the commit's derivation: the merge and
        # `assign_regions` keep a declared region as written.
        from world.regions import assign_regions
        scene = _scene(temp_db, cid)
        result = assign_regions(scene, structures={}, minted=[], occupied=["kitchen"])
        assert scene["rooms"]["kitchen"]["region"] == "the_east_wing"
        assert result["dropped"] == []
        # The structure map carries the region per room.
        data = client.get(f"/api/chats/{cid}/map").json()
        rows = {row["id"]: row for comp in data["components"] for row in comp["rooms"]}
        assert rows["kitchen"]["region"] == "the_east_wing"


# ---------------------------------------------------------------------------
# Overlays
# ---------------------------------------------------------------------------

class TestOverlays:
    def test_light_noise_and_a_chosen_sources_hearing_are_the_engines_own_words(
            self, client, story, temp_db):
        from world.spatial import (LIGHT_LEVELS, NOISE_WORDS, light_field, noise_word,
                                   quantise_hearing, sound_field)
        cid = story["chat_id"]
        scene = _lay_out(temp_db, cid)
        scene["rooms"]["kitchen"]["light"] = "dark"
        scene["entities"]["lamp"] = {"name": "the lamp", "light_source": "lit", "portable": True}
        scene["entities"]["generator"] = {"name": "the generator", "sound_source": "loud"}
        scene["positions"]["lamp"] = "kitchen"
        scene["positions"]["generator"] = "kitchen"
        scene["stations"]["lamp"] = {"at": None, "near": [], "cell": [1, 1]}
        scene["stations"]["generator"] = {"at": None, "near": [], "cell": [6, 2]}
        temp_db.wset(cid, "scene", scene)
        view = client.get(f"/api/chats/{cid}/rooms/kitchen/grid").json()
        assert set(view["overlays"]) == {"light", "noise"}
        lf = light_field(scene, "kitchen")
        assert view["overlays"]["light"]["1,1"] == lf.level((1, 1))
        assert view["overlays"]["light"]["1,1"] in LIGHT_LEVELS
        assert view["overlays"]["light"]["1,1"] != view["overlays"]["light"]["7,3"]
        sf = sound_field(scene, "", room="kitchen")
        gen = [s for s in sf.sources if s["id"] == "generator"][0]
        assert view["overlays"]["noise"]["6,2"] == noise_word(
            sf.ambient["kitchen"] + sf.intensity_at(gen, (6, 2)))
        assert set(view["overlays"]["noise"].values()) <= set(NOISE_WORDS)
        assert [s["id"] for s in view["sound_sources"]] == ["generator"]
        assert [s["id"] for s in view["light_sources"]] == ["lamp"]
        # A chosen source: its hearing word per cell, the ladder's own.
        view = client.get(f"/api/chats/{cid}/rooms/kitchen/grid?sound_from=generator").json()
        heard = view["overlays"]["sound"]
        assert heard["6,2"] == quantise_hearing(sf.intensity_at(gen, (6, 2)), sf.ambient["kitchen"])
        assert heard["6,2"] == "full"
        assert set(heard.values()) <= {"none", "fragment", "full"}
        # An unknown source paints nothing extra.
        view = client.get(f"/api/chats/{cid}/rooms/kitchen/grid?sound_from=ghost").json()
        assert "sound" not in view["overlays"]

    def test_a_room_with_no_geometry_has_no_overlays(self, client, story, temp_db):
        cid = story["chat_id"]
        scene = _scene(temp_db, cid)
        scene["rooms"]["garden"].pop("size", None)
        scene["rooms"]["garden"].pop("anchors", None)
        temp_db.wset(cid, "scene", scene)
        view = client.get(f"/api/chats/{cid}/rooms/garden/grid").json()
        assert view["overlays"] == {} and view["sound_sources"] == []


# ---------------------------------------------------------------------------
# Scoping
# ---------------------------------------------------------------------------

def test_the_new_writes_are_host_only_and_idle_guarded(client, story, monkeypatch):
    cid = story["chat_id"]
    from agents import runtime
    monkeypatch.setitem(runtime.ABORTS, (cid, None), object())
    for method, path, body in (
            ("POST", f"/api/chats/{cid}/rooms", {"name": "X"}),
            ("DELETE", f"/api/chats/{cid}/rooms/garden", None),
            ("POST", f"/api/chats/{cid}/doorways", {"room": "kitchen", "to": "garden"}),
            ("PATCH", f"/api/chats/{cid}/doorways/kitchen/hallway", {"barrier": "open"}),
            ("DELETE", f"/api/chats/{cid}/doorways/kitchen/hallway", None),
            ("POST", f"/api/chats/{cid}/rooms/kitchen/entities", {"name": "Jar"}),
            ("DELETE", f"/api/chats/{cid}/rooms/study/entities/tardis", None),
            ("POST", f"/api/chats/{cid}/rooms/kitchen/presences", {"name": "Cook"}),
            ("DELETE", f"/api/chats/{cid}/bodies/Alice", None),
            ("PUT", f"/api/chats/{cid}/bodies/Alice/room", {"room": "hallway"}),
            ("PUT", f"/api/chats/{cid}/bodies/Alice/pose", {"posture": "sitting"}),
            ("POST", f"/api/chats/{cid}/regions", {"name": "Wing"}),
    ):
        r = client.request(method, path, json=body) if body is not None else client.request(method, path)
        assert r.status_code == 409, (method, path, r.text)
    monkeypatch.delitem(runtime.ABORTS, (cid, None))
    from web.auth_routes import GUEST_ALLOWED_API_PATHS
    for path in (f"/api/chats/{cid}/doorways", f"/api/chats/{cid}/rooms",
                 f"/api/chats/{cid}/regions", f"/api/chats/{cid}/bodies/Alice/room",
                 f"/api/chats/{cid}/bodies/Alice/pose"):
        assert path not in GUEST_ALLOWED_API_PATHS
    anonymous = TestClient(app_module.app)
    assert anonymous.post(f"/api/chats/{cid}/doorways",
                          json={"room": "kitchen", "to": "garden"}).status_code in (401, 403)
    assert anonymous.delete(f"/api/chats/{cid}/rooms/garden").status_code in (401, 403)
