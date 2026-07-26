"""Moving a cast member to another room from the cast panel.

Positions live in one place -- the frame-scoped `world.scene` blob, the single
runtime source of truth for who is standing where (docs/DATABASE.md, Phase 3a).
So the properties worth defending are about not corrupting that blob:

* a room id is validated against the scene, never trusted, because a position
  naming a room that does not exist puts a character somewhere perception,
  adjacency and the narrator cannot reason about,
* the write lands on the key the scene ALREADY uses for that person, since
  `spatial.room_of` matches names loosely and a second spelling would put one
  character in two rooms at once, and
* it refuses to edit positions underneath a running pipeline, which reads and
  rewrites them throughout a turn.

Relocation is deliberately silent: it queues nothing for the narrator, unlike
adding or dismissing a character, which push an arrival/departure beat.
"""

from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient

import app as app_module
import guest_access as guest


@pytest.fixture
def client(temp_db):
    guest.reset_host_account()
    with TestClient(app_module.app) as c:
        response = c.post(
            "/api/auth/setup",
            json={"username": "host", "password": "pw12345"},
        )
        assert response.status_code == 200, response.text
        yield c
    guest.reset_host_account()


@pytest.fixture
def story(temp_db, sample_scene):
    """A chat with a four-room scene and two cast members standing in it."""
    persona = temp_db.qi(
        "INSERT INTO personas(name,sheet) VALUES(?,?)",
        ("Nathan", json.dumps({"identity": {"name": "Nathan"}})),
    )
    cid = temp_db.qi(
        "INSERT INTO chats(name,persona_id,scenario,created) VALUES(?,?,?,?)",
        ("Old Manor", persona, "", time.time()),
    )

    ids = {}
    for name in ("Alice", "Bob"):
        ids[name] = temp_db.qi(
            "INSERT INTO characters(name,sheet,created) VALUES(?,?,?)",
            (name, json.dumps({"identity": {"name": name}}), time.time()),
        )
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status) VALUES(?,?,'active')",
            (cid, ids[name]),
        )

    scene = dict(sample_scene)
    scene["positions"] = {"Alice": "kitchen", "Bob": "hallway", "Nathan": "study"}
    # A vehicle interior, which is an ordinary room carrying parent_entity.
    scene["rooms"] = dict(scene["rooms"])
    scene["rooms"]["console_room"] = {
        "name": "Console Room", "desc": "Humming.", "parent_entity": "tardis",
        "adjacent": [],
    }
    scene["entities"] = {"tardis": {"name": "The TARDIS", "kind": "vehicle"}}
    temp_db.wset(cid, "scene", scene)

    return {"chat_id": cid, "persona_id": persona, **ids}


def _positions(temp_db, cid):
    return (temp_db.wget(cid, "scene") or {}).get("positions") or {}


class TestReadingPositions:
    def test_it_reports_where_everyone_stands(self, client, story):
        response = client.get(f"/api/chats/{story['chat_id']}/positions")

        assert response.status_code == 200, response.text
        data = response.json()
        rooms = {c["name"]: c["room"] for c in data["characters"]}
        assert rooms == {"Alice": "kitchen", "Bob": "hallway"}
        assert data["persona"] == {"name": "Nathan", "room": "study"}

    def test_it_offers_every_room_in_the_scene(self, client, story):
        data = client.get(f"/api/chats/{story['chat_id']}/positions").json()

        assert {r["id"] for r in data["rooms"]} == {
            "kitchen", "hallway", "study", "cellar", "garden", "console_room",
        }

    def test_an_interior_room_names_what_it_is_inside(self, client, story):
        data = client.get(f"/api/chats/{story['chat_id']}/positions").json()
        console = next(r for r in data["rooms"] if r["id"] == "console_room")

        # "Console Room" alone does not say which ship.
        assert console["parent_entity"] == "tardis"
        assert console["parent_name"] == "The TARDIS"

    def test_a_character_standing_nowhere_reads_as_offscreen(
        self, client, story, temp_db,
    ):
        scene = temp_db.wget(story["chat_id"], "scene")
        scene["positions"].pop("Bob")
        temp_db.wset(story["chat_id"], "scene", scene)

        data = client.get(f"/api/chats/{story['chat_id']}/positions").json()
        bob = next(c for c in data["characters"] if c["name"] == "Bob")
        assert bob["room"] is None

    def test_a_chat_with_no_scene_offers_no_rooms(self, client, temp_db):
        cid = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Unstarted", "", time.time()),
        )
        data = client.get(f"/api/chats/{cid}/positions").json()

        assert data["rooms"] == []
        assert data["characters"] == []

    def test_a_missing_chat_is_a_404(self, client):
        assert client.get("/api/chats/999999/positions").status_code == 404


class TestMoving:
    def test_it_moves_the_character(self, client, story, temp_db):
        response = client.put(
            f"/api/chats/{story['chat_id']}/characters/{story['Alice']}/position",
            json={"room": "cellar"},
        )

        assert response.status_code == 200, response.text
        assert response.json()["room"] == "cellar"
        assert _positions(temp_db, story["chat_id"])["Alice"] == "cellar"

    def test_it_leaves_everyone_else_where_they_were(
        self, client, story, temp_db,
    ):
        client.put(
            f"/api/chats/{story['chat_id']}/characters/{story['Alice']}/position",
            json={"room": "garden"},
        )

        positions = _positions(temp_db, story["chat_id"])
        assert positions["Bob"] == "hallway"
        assert positions["Nathan"] == "study"

    def test_it_can_move_someone_into_a_vehicle_interior(
        self, client, story, temp_db,
    ):
        client.put(
            f"/api/chats/{story['chat_id']}/characters/{story['Bob']}/position",
            json={"room": "console_room"},
        )

        assert _positions(temp_db, story["chat_id"])["Bob"] == "console_room"

    def test_an_empty_room_means_offscreen(self, client, story, temp_db):
        response = client.put(
            f"/api/chats/{story['chat_id']}/characters/{story['Bob']}/position",
            json={"room": ""},
        )

        assert response.status_code == 200, response.text
        assert response.json()["room"] is None
        # Absent, not present-and-empty: room_of answers None either way, but
        # a "" position is a room id that does not exist.
        assert "Bob" not in _positions(temp_db, story["chat_id"])

    def test_it_preserves_the_rest_of_the_scene(self, client, story, temp_db):
        before = temp_db.wget(story["chat_id"], "scene")
        client.put(
            f"/api/chats/{story['chat_id']}/characters/{story['Alice']}/position",
            json={"room": "cellar"},
        )
        after = temp_db.wget(story["chat_id"], "scene")

        assert after["rooms"] == before["rooms"]
        assert after["entities"] == before["entities"]
        assert after["location"] == before["location"]

    def test_it_narrates_nothing(self, client, story, temp_db):
        client.put(
            f"/api/chats/{story['chat_id']}/characters/{story['Alice']}/position",
            json={"room": "garden"},
        )

        # Adding or dismissing a character queues an arrival/departure beat;
        # an authoring relocation deliberately does not.
        assert temp_db.wget(story["chat_id"], "pending", []) == []


class TestRefusals:
    def test_a_room_that_is_not_in_the_scene_is_refused(
        self, client, story, temp_db,
    ):
        response = client.put(
            f"/api/chats/{story['chat_id']}/characters/{story['Alice']}/position",
            json={"room": "throne_room"},
        )

        assert response.status_code == 400
        assert "throne_room" in response.json()["detail"]
        # Unmoved, not moved-to-nowhere.
        assert _positions(temp_db, story["chat_id"])["Alice"] == "kitchen"

    def test_a_character_outside_this_story_is_refused(
        self, client, story, temp_db,
    ):
        outsider = temp_db.qi(
            "INSERT INTO characters(name,sheet,created) VALUES(?,?,?)",
            ("Stranger", json.dumps({"identity": {"name": "Stranger"}}),
             time.time()),
        )

        response = client.put(
            f"/api/chats/{story['chat_id']}/characters/{outsider}/position",
            json={"room": "cellar"},
        )

        assert response.status_code == 404
        assert "Stranger" not in _positions(temp_db, story["chat_id"])

    def test_a_character_that_does_not_exist_is_refused(self, client, story):
        response = client.put(
            f"/api/chats/{story['chat_id']}/characters/999999/position",
            json={"room": "cellar"},
        )
        assert response.status_code == 404

    def test_a_missing_chat_is_refused(self, client, story):
        response = client.put(
            f"/api/chats/999999/characters/{story['Alice']}/position",
            json={"room": "cellar"},
        )
        assert response.status_code == 404

    def test_it_refuses_while_a_pipeline_is_running(self, client, story):
        key = (story["chat_id"], None)
        app_module.ABORTS[key] = object()
        try:
            response = client.put(
                f"/api/chats/{story['chat_id']}/characters/{story['Alice']}"
                "/position",
                json={"room": "cellar"},
            )
        finally:
            app_module.ABORTS.pop(key, None)

        # A running turn reads and rewrites positions; editing underneath it
        # would either corrupt the scene or be silently overwritten.
        assert response.status_code == 409


class TestSceneHelperTolerance:
    """`scene.get_scene` took `(chat or {}).get("scenario")`, which raises
    AttributeError on a sqlite3.Row -- and the app's scene routes pass the row
    straight from `q()`. It only fired on the no-scene path, so an unstarted
    chat 500'd instead of reporting an empty scene."""

    def test_reading_positions_survives_an_unstarted_chat(self, client, temp_db):
        cid = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Unstarted", "A quiet room.", time.time()),
        )
        assert client.get(f"/api/chats/{cid}/positions").status_code == 200

    def test_reading_attire_survives_an_unstarted_chat(self, client, temp_db):
        cid = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Unstarted", "A quiet room.", time.time()),
        )
        response = client.get(f"/api/chats/{cid}/attire")
        assert response.status_code == 200, response.text
        assert response.json() == {}


class TestNameKeying:
    def test_it_rewrites_the_spelling_the_scene_already_uses(
        self, client, story, temp_db,
    ):
        scene = temp_db.wget(story["chat_id"], "scene")
        scene["positions"].pop("Alice")
        # room_of matches loosely, so this IS Alice's position as far as every
        # reader is concerned.
        scene["positions"]["alice "] = "kitchen"
        temp_db.wset(story["chat_id"], "scene", scene)

        client.put(
            f"/api/chats/{story['chat_id']}/characters/{story['Alice']}/position",
            json={"room": "cellar"},
        )

        positions = _positions(temp_db, story["chat_id"])
        # One entry, not two: a second spelling would put her in two rooms at
        # once for anything that walks positions to find a room's occupants.
        assert [k for k in positions if k.strip().lower() == "alice"] == ["Alice"]
        assert positions["Alice"] == "cellar"

    def test_going_offscreen_clears_a_loosely_matching_key_too(
        self, client, story, temp_db,
    ):
        scene = temp_db.wget(story["chat_id"], "scene")
        scene["positions"].pop("Bob")
        scene["positions"]["BOB"] = "hallway"
        temp_db.wset(story["chat_id"], "scene", scene)

        client.put(
            f"/api/chats/{story['chat_id']}/characters/{story['Bob']}/position",
            json={"room": ""},
        )

        positions = _positions(temp_db, story["chat_id"])
        assert not [k for k in positions if k.strip().lower() == "bob"]

    def test_a_move_is_visible_to_the_spatial_reader(self, client, story, temp_db):
        from spatial import room_of

        client.put(
            f"/api/chats/{story['chat_id']}/characters/{story['Alice']}/position",
            json={"room": "garden"},
        )

        scene = temp_db.wget(story["chat_id"], "scene")
        assert room_of(scene, "Alice") == "garden"

    def test_the_move_round_trips_through_the_read_route(self, client, story):
        client.put(
            f"/api/chats/{story['chat_id']}/characters/{story['Bob']}/position",
            json={"room": "cellar"},
        )

        data = client.get(f"/api/chats/{story['chat_id']}/positions").json()
        bob = next(c for c in data["characters"] if c["name"] == "Bob")
        assert bob["room"] == "cellar"
