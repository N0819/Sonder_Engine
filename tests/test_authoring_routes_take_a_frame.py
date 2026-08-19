"""The scene-authoring routes can say which era they mean.

WEB-8: six routes read and write frame-scoped world state (the scene blob)
through the ambient `active_frame_id` contextvar, which no route ever sets --
so every read landed on the PRESENT frame, and a multi-frame story had no
spelling of "edit the era we are playing". The turn route already had the
right shape (`turn_new` takes an optional `frame_id`, None meaning the
present), so these routes take the same optional parameter with the same
meaning and the same validation. The default is unchanged behavior: a caller
who says nothing edits the present, exactly as before.

`frame_id` rides as a QUERY parameter on every one of the six, PUTs
included, because two of the PUT bodies (`attire_put`, `world_put`) are open
dicts keyed by fiction names -- a reserved body key there would collide with
a character who happens to be called "frame_id".

`world_get`/`world_put` are the two audit-listed routes that deliberately do
NOT take one: they operate on raw storage rows below the frame abstraction,
where every era's keys (`scene<sep>frN`) are already visible and writable
verbatim. Giving them a frame parameter would make one era's rows special in
a surface whose whole point is that none are.
"""

from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient

from core.db import _FRAME_KEY_SEP
from web import app as app_module
from web import guest_access as guest


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
def eras(temp_db, client):
    """A chat playing in two eras: the present, and a past frame with its
    own scene -- different rooms, different positions, different attire."""
    persona = temp_db.qi(
        "INSERT INTO personas(name,sheet) VALUES(?,?)",
        ("Nathan", json.dumps({"identity": {"name": "Nathan"}})),
    )
    cid = temp_db.qi(
        "INSERT INTO chats(name,persona_id,scenario,created) VALUES(?,?,?,?)",
        ("Two Eras", persona, "", time.time()),
    )
    ch = temp_db.qi(
        "INSERT INTO characters(name,sheet,created) VALUES(?,?,?)",
        ("Alice", json.dumps({"identity": {"name": "Alice"}}), time.time()),
    )
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status) VALUES(?,?,'active')",
        (cid, ch),
    )

    present = {
        "location": "the manor, now",
        "rooms": {"kitchen": {"name": "Kitchen", "adjacent": []},
                  "hallway": {"name": "Hallway", "adjacent": []}},
        "positions": {"Alice": "kitchen", "Nathan": "hallway"},
        "entities": {}, "attire": {
            "Alice": {"wearing": ["apron"], "state": {}, "regions": {}}},
    }
    past = {
        "location": "the manor, decades ago",
        "rooms": {"ballroom": {"name": "Ballroom", "adjacent": []},
                  "terrace": {"name": "Terrace", "adjacent": []}},
        "positions": {"Alice": "ballroom", "Nathan": "ballroom"},
        "entities": {}, "attire": {
            "Alice": {"wearing": ["gown"], "state": {}, "regions": {}}},
    }
    temp_db.wset(cid, "scene", present)

    response = client.post(f"/api/chats/{cid}/frames",
                           json={"label": "Decades Ago", "ordinal": -10,
                                 "kind": "past"})
    assert response.status_code == 200, response.text
    fid = response.json()["id"]
    temp_db.wset_for_frame(cid, "scene", past, fid)

    return {"chat_id": cid, "char_id": ch, "frame_id": fid}


def _scene(temp_db, cid, frame_id=None):
    if frame_id is None:
        return temp_db.wget(cid, "scene") or {}
    return temp_db.wget_for_frame(cid, "scene", frame_id) or {}


class TestReadsAreEraScoped:
    def test_positions_answer_for_the_frame_asked_about(self, client, eras):
        cid, fid = eras["chat_id"], eras["frame_id"]

        present = client.get(f"/api/chats/{cid}/positions").json()
        past = client.get(
            f"/api/chats/{cid}/positions?frame_id={fid}").json()

        assert {r["id"] for r in present["rooms"]} == {"kitchen", "hallway"}
        assert {r["id"] for r in past["rooms"]} == {"ballroom", "terrace"}
        assert past["characters"][0]["room"] == "ballroom"
        assert past["persona"]["room"] == "ballroom"

    def test_attire_answers_for_the_frame_asked_about(self, client, eras):
        cid, fid = eras["chat_id"], eras["frame_id"]

        present = client.get(f"/api/chats/{cid}/attire").json()
        past = client.get(f"/api/chats/{cid}/attire?frame_id={fid}").json()

        assert present["Alice"]["wearing"] == ["apron"]
        assert past["Alice"]["wearing"] == ["gown"]

    def test_vitals_answer_for_the_frame_asked_about(self, client, eras,
                                                     temp_db):
        cid, fid = eras["chat_id"], eras["frame_id"]
        past = _scene(temp_db, cid, fid)
        past["vitals"] = {"Alice": {"air": 1.0, "stamina": 0.25,
                                    "nourishment": 1.0, "injury": 0.0}}
        temp_db.wset_for_frame(cid, "scene", past, fid)

        present = client.get(f"/api/chats/{cid}/vitals").json()
        era = client.get(f"/api/chats/{cid}/vitals?frame_id={fid}").json()

        assert present["bodies"] == []
        assert [b["name"] for b in era["bodies"]] == ["Alice"]
        assert era["bodies"][0]["vitals"]["stamina"] == 0.25


class TestWritesLandInTheEraNamed:
    def test_a_relocation_moves_the_character_in_that_era_only(
        self, client, eras, temp_db,
    ):
        cid, ch, fid = eras["chat_id"], eras["char_id"], eras["frame_id"]

        response = client.put(
            f"/api/chats/{cid}/characters/{ch}/position?frame_id={fid}",
            json={"room": "terrace"},
        )
        assert response.status_code == 200, response.text

        assert _scene(temp_db, cid, fid)["positions"]["Alice"] == "terrace"
        assert _scene(temp_db, cid)["positions"]["Alice"] == "kitchen"

    def test_the_room_is_validated_against_that_era_scene(
        self, client, eras,
    ):
        cid, ch, fid = eras["chat_id"], eras["char_id"], eras["frame_id"]

        # "kitchen" exists in the present and not in the past; naming the
        # era must mean the era's rooms are the ones that count.
        response = client.put(
            f"/api/chats/{cid}/characters/{ch}/position?frame_id={fid}",
            json={"room": "kitchen"},
        )
        assert response.status_code == 400, response.text

    def test_an_attire_edit_lands_in_that_era_only(self, client, eras,
                                                   temp_db):
        cid, fid = eras["chat_id"], eras["frame_id"]

        response = client.put(
            f"/api/chats/{cid}/attire?frame_id={fid}",
            json={"Alice": {"wearing": ["travel cloak"], "state": {},
                            "regions": {}}},
        )
        assert response.status_code == 200, response.text

        assert _scene(temp_db, cid, fid)["attire"]["Alice"]["wearing"] == [
            "travel cloak"]
        assert _scene(temp_db, cid)["attire"]["Alice"]["wearing"] == ["apron"]

    def test_survival_seeding_lands_in_that_era_only(self, client, eras,
                                                     temp_db):
        cid, fid = eras["chat_id"], eras["frame_id"]

        response = client.put(
            f"/api/chats/{cid}/survival?frame_id={fid}",
            json={"enabled": True},
        )
        assert response.status_code == 200, response.text

        # The toggle itself is chat-global -- one story either tracks bodies
        # or does not, whatever era the panel was open on...
        assert temp_db.wget(cid, "survival_enabled") is True
        # ...while the seeded bodies belong to the era whose scene they
        # stand in.
        assert "Alice" in (_scene(temp_db, cid, fid).get("vitals") or {})
        assert _scene(temp_db, cid).get("vitals") is None


class TestTheParameterIsValidated:
    def test_a_frame_from_another_chat_is_a_404(self, client, eras,
                                                temp_db):
        other = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Other", "", time.time()),
        )
        response = client.post(f"/api/chats/{other}/frames",
                               json={"label": "Elsewhere", "ordinal": 1,
                                     "kind": "future"})
        foreign = response.json()["id"]

        cid = eras["chat_id"]
        response = client.get(
            f"/api/chats/{cid}/positions?frame_id={foreign}")
        assert response.status_code == 404, response.text

    def test_a_frame_that_does_not_exist_is_a_404(self, client, eras):
        cid = eras["chat_id"]
        response = client.get(f"/api/chats/{cid}/attire?frame_id=99999")
        assert response.status_code == 404, response.text


class TestTheWorldEditorStaysBelowTheFrames:
    def test_world_get_already_carries_every_era_raw(self, client, eras):
        """The deliberate exemption: `world_get`/`world_put` operate on raw
        storage rows, so an era's scene is already visible (and writable
        back) under its scoped key. A frame parameter here would make one
        era's rows special in a surface whose point is that none are."""
        cid, fid = eras["chat_id"], eras["frame_id"]

        world = client.get(f"/api/chats/{cid}/world").json()

        scoped = f"scene{_FRAME_KEY_SEP}{fid}"
        assert "scene" in world
        assert scoped in world
        assert world[scoped]["location"] == "the manor, decades ago"
