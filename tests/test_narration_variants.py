"""Flipping between the rerolls of the newest beat.

A full reroll re-runs the pipeline against the same turn and appends a variant
to every step, activating the newest -- so a turn rerolled three times holds
four renderings of itself and the reader could only ever see the last one, or
open the technical panel, find the narrator step, and use its per-step arrows.
These two routes are the affordance in the place people look for it.

The design question they answer is whether selecting a rendering marks the rest
of the turn stale. It does not, and that is `edit_prose`'s position taken
consistently: the mechanical record of a beat is the director/perception/commit
steps, which already ran and already applied side effects that are not
idempotent. Which rendering the reader sees is presentation. Selecting a
variant the engine itself produced is strictly less arbitrary than the
free-text prose edit that route already permits without staleness.

Restricted to the LATEST turn, because an earlier turn's alternate rendering is
a different question -- every turn after it was generated against the prose
that IS active.
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
    with TestClient(app_module.app) as test_client:
        response = test_client.post(
            "/api/auth/setup",
            json={"username": "host", "password": "pw12345"},
        )
        assert response.status_code == 200, response.text
        yield test_client
    guest.reset_host_account()


def _narrated_turn(temp_db, chat_id, idx, prose_versions):
    """One turn whose narrator step carries several renderings, newest active
    -- the shape a sequence of rerolls leaves behind."""
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, idx, "look around", time.time()),
    )
    step_id = temp_db.qi(
        "INSERT INTO steps(turn_id,key,label,ord,stale) VALUES(?,?,?,?,0)",
        (turn_id, "narrator", "Narrator", 8),
    )
    # A later step, so staleness has somewhere to show up if anything sets it.
    commit_id = temp_db.qi(
        "INSERT INTO steps(turn_id,key,label,ord,stale) VALUES(?,?,?,?,0)",
        (turn_id, "commit", "Commit", 9),
    )
    variant_ids = []
    for position, prose in enumerate(prose_versions):
        variant_ids.append(temp_db.qi(
            "INSERT INTO variants(step_id,content,created,active) "
            "VALUES(?,?,?,?)",
            (step_id, json.dumps({"prose": prose}), time.time(),
             1 if position == len(prose_versions) - 1 else 0),
        ))
    return turn_id, step_id, commit_id, variant_ids


@pytest.fixture
def story(temp_db):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    older = _narrated_turn(temp_db, chat_id, 0, ["An older beat."])
    latest = _narrated_turn(temp_db, chat_id, 1, [
        "The door is shut.",
        "The door stands shut, and has for some time.",
        "Nobody has opened the door.",
    ])
    return {"chat": chat_id, "older": older, "latest": latest}


class TestListing:

    def test_every_rendering_comes_back_oldest_first_with_its_prose(
            self, client, story):
        turn_id = story["latest"][0]
        body = client.get(f"/api/turns/{turn_id}/narration").json()

        assert [v["prose"] for v in body["variants"]] == [
            "The door is shut.",
            "The door stands shut, and has for some time.",
            "Nobody has opened the door.",
        ]
        assert [v["active"] for v in body["variants"]] == [False, False, True]

    def test_a_turn_with_no_narration_lists_nothing_rather_than_failing(
            self, client, temp_db):
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Bare", "", time.time()),
        )
        turn_id = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) "
            "VALUES(?,?,?,?)", (chat_id, 0, "", time.time()),
        )
        response = client.get(f"/api/turns/{turn_id}/narration")

        assert response.status_code == 200
        assert response.json() == {"variants": []}

    def test_an_unknown_turn_is_a_404(self, client):
        assert client.get("/api/turns/999999/narration").status_code == 404


class TestSelecting:

    def test_selecting_an_older_rendering_makes_it_the_one_on_the_page(
            self, client, temp_db, story):
        turn_id, step_id, _commit, variants = story["latest"]
        response = client.post(f"/api/turns/{turn_id}/narration",
                               json={"variant_id": variants[0]})

        assert response.status_code == 200
        assert response.json()["prose"] == "The door is shut."
        active = temp_db.q(
            "SELECT id FROM variants WHERE step_id=? AND active=1",
            (step_id,), one=True)
        assert active["id"] == variants[0]

    def test_exactly_one_rendering_is_ever_active(
            self, client, temp_db, story):
        turn_id, step_id, _commit, variants = story["latest"]
        for variant_id in variants:
            client.post(f"/api/turns/{turn_id}/narration",
                        json={"variant_id": variant_id})
            count = temp_db.q(
                "SELECT COUNT(*) c FROM variants WHERE step_id=? AND active=1",
                (step_id,), one=True)["c"]
            assert count == 1

    def test_it_marks_nothing_stale(self, client, temp_db, story):
        """The whole design decision, in one assertion. `/api/steps/{id}/
        activate` stales everything downstream; this must not, because commit
        has already applied side effects that are not idempotent and choosing
        a rendering is presentation."""
        turn_id, _step, commit_id, variants = story["latest"]
        client.post(f"/api/turns/{turn_id}/narration",
                    json={"variant_id": variants[0]})

        stale = temp_db.q("SELECT stale FROM steps WHERE id=?",
                          (commit_id,), one=True)["stale"]
        assert not stale

    def test_an_earlier_turn_refuses(self, client, story):
        """Every turn after it was generated against the prose that IS active,
        so swapping one silently would leave the story describing a beat
        nobody downstream ever read."""
        turn_id, _step, _commit, variants = story["older"]
        response = client.post(f"/api/turns/{turn_id}/narration",
                               json={"variant_id": variants[0]})

        assert response.status_code >= 400

    def test_a_variant_from_a_different_turn_is_refused(
            self, client, story):
        latest_turn = story["latest"][0]
        foreign = story["older"][3][0]
        response = client.post(f"/api/turns/{latest_turn}/narration",
                               json={"variant_id": foreign})

        assert response.status_code == 404

    def test_a_missing_variant_id_is_refused(self, client, story):
        turn_id = story["latest"][0]
        response = client.post(f"/api/turns/{turn_id}/narration", json={})

        assert response.status_code == 404
