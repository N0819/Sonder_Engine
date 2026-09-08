"""Per-story character-card overrides and their information boundaries."""

from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient

from web import app as app_module
from web import guest_access as guest
from story.character_schema import default_character_data
from story.scene import active_cast


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


@pytest.fixture
def stories(temp_db):
    base = default_character_data("Mara")
    base["psychology"]["drive"]["essence"] = "Protect the archive"
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (
            "Mara", json.dumps(base), "{}", time.time(),
            base["identity"]["uid"],
        ),
    )
    other = default_character_data("Outsider")
    outsider_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (
            "Outsider", json.dumps(other), "{}", time.time(),
            other["identity"]["uid"],
        ),
    )
    chat_ids = []
    for name in ("Story A", "Story B"):
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            (name, "", time.time()),
        )
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) "
            "VALUES(?,?,?,?)",
            (
                chat_id, char_id, "active",
                json.dumps({
                    "active_state": {"mood": "watchful", "stress": {"load": 0.7}},
                    "interior": {"beliefs": [{"belief": "earned at runtime"}]},
                    "private_history": [{
                        "fact_id": f"private-{name}",
                        "content": f"{name} private marker",
                        "known_by": [],
                    }],
                }),
            ),
        )
        chat_ids.append(chat_id)
    return {
        "char_id": char_id,
        "outsider_id": outsider_id,
        "chat_a": chat_ids[0],
        "chat_b": chat_ids[1],
        "base": base,
    }


def _participant(client, chat_id):
    response = client.get(f"/api/chats/{chat_id}")
    assert response.status_code == 200, response.text
    return response.json()["participants"][0]


def test_story_card_update_is_scoped_and_preserves_live_state(
        client, temp_db, stories):
    participant = _participant(client, stories["chat_a"])
    assert participant["card_source"] == "library"
    sheet = json.loads(participant["sheet"])
    sheet["psychology"]["drive"]["essence"] = "Expose the archive's corruption"
    sheet["social"]["voice"]["cadence"] = "clipped when cornered"
    sheet["knowledge"]["private_history"] = [{
        "fact_id": "story-a-secret",
        "content": "Only Story A earned this secret.",
        "known_by": [],
    }]

    response = client.put(
        f"/api/chats/{stories['chat_a']}/characters/{stories['char_id']}/card",
        json={
            "sheet": sheet,
            # Hostile extra input must not become live state.
            "state": {"active_state": {"mood": "REMOTE_CONTROLLED"}},
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["card_source"] == "chat"
    row = temp_db.q(
        "SELECT sheet,state FROM chat_chars WHERE chat_id=? AND char_id=?",
        (stories["chat_a"], stories["char_id"]), one=True,
    )
    override = json.loads(row["sheet"])
    state = json.loads(row["state"])
    assert override["psychology"]["drive"]["essence"] == (
        "Expose the archive's corruption"
    )
    assert state["active_state"]["mood"] == "watchful"
    assert state["active_state"]["stress"]["load"] == 0.7
    assert state["interior"]["beliefs"] == [{"belief": "earned at runtime"}]
    assert state["private_history"][0]["fact_id"] == "story-a-secret"

    base = json.loads(temp_db.q(
        "SELECT sheet FROM characters WHERE id=?",
        (stories["char_id"],), one=True,
    )["sheet"])
    assert base["psychology"]["drive"]["essence"] == "Protect the archive"
    assert json.loads(active_cast(stories["chat_a"])[0]["sheet"])[
        "psychology"
    ]["drive"]["essence"] == "Expose the archive's corruption"
    assert json.loads(active_cast(stories["chat_b"])[0]["sheet"])[
        "psychology"
    ]["drive"]["essence"] == "Protect the archive"

    chat_b = _participant(client, stories["chat_b"])
    assert chat_b["card_source"] == "library"
    assert "Only Story A earned this secret" not in chat_b["sheet"]
    assert "Story B private marker" in chat_b["sheet"]


def test_story_card_rejects_identity_rekey_and_cross_chat_target(
        client, temp_db, stories):
    participant = _participant(client, stories["chat_a"])
    sheet = json.loads(participant["sheet"])

    renamed = json.loads(json.dumps(sheet))
    renamed["identity"]["name"] = "Not Mara"
    response = client.put(
        f"/api/chats/{stories['chat_a']}/characters/{stories['char_id']}/card",
        json={"sheet": renamed},
    )
    assert response.status_code == 400

    rekeyed = json.loads(json.dumps(sheet))
    rekeyed["identity"]["uid"] = "char_attacker_controlled"
    response = client.put(
        f"/api/chats/{stories['chat_a']}/characters/{stories['char_id']}/card",
        json={"sheet": rekeyed},
    )
    assert response.status_code == 400

    outsider_before = temp_db.q(
        "SELECT sheet FROM characters WHERE id=?",
        (stories["outsider_id"],), one=True,
    )["sheet"]
    response = client.put(
        f"/api/chats/{stories['chat_a']}/characters/{stories['outsider_id']}/card",
        json={"sheet": default_character_data("Outsider")},
    )
    assert response.status_code == 404
    assert temp_db.q(
        "SELECT sheet FROM characters WHERE id=?",
        (stories["outsider_id"],), one=True,
    )["sheet"] == outsider_before


def test_renaming_the_library_card_cannot_rekey_a_story_already_played(
        client, temp_db, stories):
    """A19 (review 2026-09-07), closed by ad260f1d and pinned here.

    The reusable card is a TEMPLATE. `chat_character_sheet` resolves
    `COALESCE(cc.sheet, ch.sheet)` and attaching writes no `chat_chars.sheet`,
    so a story with no per-story card reads the library sheet live -- and the
    in-story identity is keyed by NAME (positions, `known`, memories, the
    dialogue log). Renaming the library card therefore rekeyed every one of
    those stories at once: the exact rekey the per-story card route above
    refuses with a 400. Measured at review time: 103 of 116 attachments had no
    card of their own.

    So an identity change hands every such attachment the card it has been
    playing under, before the library row moves. An edit that keeps the name
    and the uid must NOT do that -- freezing a copy onto every story would
    make the library card stop being a template.
    """
    renamed = json.loads(json.dumps(stories["base"]))
    renamed["identity"]["name"] = "Mara Vell"
    response = client.put(
        f"/api/characters/{stories['char_id']}", json={"sheet": renamed})
    assert response.status_code == 200, response.text

    assert temp_db.q(
        "SELECT name FROM characters WHERE id=?",
        (stories["char_id"],), one=True,
    )["name"] == "Mara Vell"
    for chat_id in (stories["chat_a"], stories["chat_b"]):
        cast = active_cast(chat_id)
        assert json.loads(cast[0]["sheet"])["identity"]["name"] == "Mara"


def test_an_edit_that_keeps_the_identity_leaves_the_card_a_template(
        client, temp_db, stories):
    """A19's other half. Nothing is snapshotted unless the identity moves, so
    an ordinary library edit still reaches every story that has no card of its
    own -- which is what makes it a library."""
    edited = json.loads(json.dumps(stories["base"]))
    edited["psychology"]["drive"]["essence"] = "Keep the archive honest"
    response = client.put(
        f"/api/characters/{stories['char_id']}", json={"sheet": edited})
    assert response.status_code == 200, response.text

    assert not temp_db.q(
        "SELECT 1 FROM chat_chars WHERE char_id=? "
        "AND sheet IS NOT NULL AND TRIM(sheet)!=''",
        (stories["char_id"],),
    )
    for chat_id in (stories["chat_a"], stories["chat_b"]):
        assert json.loads(active_cast(chat_id)[0]["sheet"])[
            "psychology"]["drive"]["essence"] == "Keep the archive honest"


def test_story_card_refuses_to_race_a_running_pipeline(client, stories):
    participant = _participant(client, stories["chat_a"])
    key = (stories["chat_a"], None)
    app_module.ABORTS[key] = object()
    try:
        response = client.put(
            f"/api/chats/{stories['chat_a']}/characters/"
            f"{stories['char_id']}/card",
            json={"sheet": json.loads(participant["sheet"])},
        )
    finally:
        app_module.ABORTS.pop(key, None)

    assert response.status_code == 409


def test_story_card_survives_portable_archive_round_trip(
        client, temp_db, stories):
    participant = _participant(client, stories["chat_a"])
    sheet = json.loads(participant["sheet"])
    sheet["psychology"]["drive"]["essence"] = "A story-only drive"
    saved = client.put(
        f"/api/chats/{stories['chat_a']}/characters/{stories['char_id']}/card",
        json={"sheet": sheet},
    )
    assert saved.status_code == 200, saved.text

    archive = client.get(f"/api/chats/{stories['chat_a']}/export")
    assert archive.status_code == 200, archive.text
    imported = client.post("/api/chats/import", json={"data": archive.json()})
    assert imported.status_code == 200, imported.text
    imported_chat_id = imported.json()["id"]

    row = temp_db.q(
        "SELECT sheet FROM chat_chars WHERE chat_id=?",
        (imported_chat_id,), one=True,
    )
    assert json.loads(row["sheet"])["psychology"]["drive"]["essence"] == (
        "A story-only drive"
    )


def test_cast_ui_offers_story_card_editor():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    settings = (root / "static/js/settings.js").read_text(encoding="utf-8")
    editors = (root / "static/js/editors.js").read_text(encoding="utf-8")

    assert "Edit this character card for this story only" in settings
    assert "charEditor(p, { chatId })" in settings
    assert "/characters/${c.id}/card" in editors
    assert "Live mood, stress, memories, relationships" in editors
