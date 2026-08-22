"""Authoritative Library authoring projections and conflict protection."""

from __future__ import annotations

import json
import re
import time

from fastapi.testclient import TestClient

from web import app as app_module


def _client(monkeypatch):
    monkeypatch.setattr(
        app_module.guest,
        "verify_host_session",
        lambda token: token == "valid-host-session",
    )
    client = TestClient(app_module.app)
    client.cookies.set(app_module.HOST_COOKIE, "valid-host-session")
    return client


def _seed_story(db):
    persona = db.qi(
        "INSERT INTO personas(name,sheet,source,resource_uid) VALUES(?,?,?,?)",
        (
            "Mira",
            json.dumps({"identity": {"name": "Mira"}}),
            json.dumps({"private_import": "must stay private"}),
            "persona-authoring-mira",
        ),
    )
    character = db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (
            "Asha",
            json.dumps({
                "identity": {"name": "Asha"},
                "knowledge": {"private_history": ["private runtime history"]},
            }),
            json.dumps({"raw_card": "must stay private"}),
            time.time() - 50,
            "character-authoring-asha",
        ),
    )
    story = db.qi(
        "INSERT INTO chats(name,persona_id,scenario,created) VALUES(?,?,?,?)",
        ("Lantern Archive", persona, "Rain on old glass", time.time() - 40),
    )
    db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (story, character, "dormant", json.dumps({"secret": "runtime only"})),
    )
    lore = db.qi(
        "INSERT INTO lorebooks(name,chat_id,origin_id,summary,book_type) "
        "VALUES(?,?,?,?,?)",
        ("Archive Copy", story, 999999, "Story-visible summary", "world"),
    )
    db.qi(
        "INSERT INTO chat_lorebooks(chat_id,lorebook_id,origin_id,enabled) "
        "VALUES(?,?,?,0)",
        (story, lore, 999999),
    )
    turn_ids = []
    for index in range(4):
        turn_ids.append(db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
            (story, index, f"private player input {index}", time.time() - 10 + index),
        ))
    return {
        "story": story, "persona": persona, "character": character,
        "lore": lore, "turn_ids": turn_ids,
    }


def test_story_authoring_projection_is_bounded_and_reports_real_overview(
    temp_db, monkeypatch,
):
    seeded = _seed_story(temp_db)
    with _client(monkeypatch) as client:
        response = client.get(
            f"/api/library/authoring/story/{seeded['story']}"
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["kind"] == "story"
    assert payload["id"] == seeded["story"]
    assert payload["owner"] == f"story:{seeded['story']}"
    assert payload["document"] == {
        "name": "Lantern Archive",
        "scenario": "Rain on old glass",
        "persona_id": seeded["persona"],
    }
    assert re.fullmatch(r"[0-9a-f]{64}", payload["revision"])
    assert payload["overview"]["cast"] == [{
        "id": seeded["character"],
        "name": "Asha",
        "state": "dormant",
        "card_source": "library",
    }]
    assert payload["overview"]["personas"] == [{
        "id": seeded["persona"],
        "name": "Mira",
        "state": "primary",
    }]
    assert payload["overview"]["lore"] == [{
        "id": seeded["lore"],
        "name": "Archive Copy",
        "state": "disabled",
        "origin_id": 999999,
    }]
    assert payload["overview"]["activity"]["turn_count"] == 4
    assert [row["idx"] for row in payload["overview"]["activity"]["recent"]] == [3, 2, 1]
    assert [row["id"] for row in payload["overview"]["activity"]["recent"]] == [
        seeded["turn_ids"][3], seeded["turn_ids"][2], seeded["turn_ids"][1],
    ]
    assert payload["overview"]["issues"] == [{
        "code": "missing-lore-origin",
        "item_id": seeded["lore"],
        "origin_id": 999999,
    }]
    serialized = json.dumps(payload)
    assert "private player input" not in serialized
    assert "private runtime history" not in serialized
    assert "runtime only" not in serialized
    assert "raw_card" not in serialized
    assert "private_import" not in serialized


def test_story_write_accepts_matching_revision_and_returns_new_authority(
    temp_db, monkeypatch,
):
    seeded = _seed_story(temp_db)
    with _client(monkeypatch) as client:
        before = client.get(
            f"/api/library/authoring/story/{seeded['story']}"
        ).json()
        response = client.put(
            f"/api/chats/{seeded['story']}",
            json={
                "name": "Lantern Index",
                "scenario": "Sun through repaired glass",
                "expected_revision": before["revision"],
            },
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["ok"] is True
    assert payload["revision"] != before["revision"]
    assert payload["document"] == {
        "name": "Lantern Index",
        "scenario": "Sun through repaired glass",
        "persona_id": seeded["persona"],
    }
    stored = temp_db.q(
        "SELECT name,scenario,persona_id FROM chats WHERE id=?",
        (seeded["story"],), one=True,
    )
    assert dict(stored) == payload["document"]


def test_story_write_refuses_a_stale_revision_without_changing_the_story(
    temp_db, monkeypatch,
):
    seeded = _seed_story(temp_db)
    with _client(monkeypatch) as client:
        before = client.get(
            f"/api/library/authoring/story/{seeded['story']}"
        ).json()
        accepted = client.put(
            f"/api/chats/{seeded['story']}",
            json={"name": "Newer title", "expected_revision": before["revision"]},
        )
        conflict = client.put(
            f"/api/chats/{seeded['story']}",
            json={"name": "Stale title", "expected_revision": before["revision"]},
        )

    assert accepted.status_code == 200
    assert conflict.status_code == 409, conflict.text
    detail = conflict.json()["detail"]
    assert detail["code"] == "edit-conflict"
    assert detail["owner"] == f"story:{seeded['story']}"
    assert detail["revision"] == accepted.json()["revision"]
    assert detail["document"]["name"] == "Newer title"
    assert temp_db.q(
        "SELECT name FROM chats WHERE id=?", (seeded["story"],), one=True,
    )["name"] == "Newer title"


def test_legacy_story_write_without_revision_remains_compatible(
    temp_db, monkeypatch,
):
    seeded = _seed_story(temp_db)
    with _client(monkeypatch) as client:
        response = client.put(
            f"/api/chats/{seeded['story']}", json={"name": "Legacy rename"}
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert temp_db.q(
        "SELECT name FROM chats WHERE id=?", (seeded["story"],), one=True,
    )["name"] == "Legacy rename"


def test_reusable_authoring_read_normalizes_sheet_but_never_exposes_source(
    temp_db, monkeypatch,
):
    seeded = _seed_story(temp_db)
    with _client(monkeypatch) as client:
        character = client.get(
            f"/api/library/authoring/character/{seeded['character']}"
        )
        persona = client.get(
            f"/api/library/authoring/persona/{seeded['persona']}"
        )

    assert character.status_code == 200, character.text
    assert persona.status_code == 200, persona.text
    assert character.json()["document"]["identity"]["name"] == "Asha"
    assert persona.json()["document"]["identity"]["name"] == "Mira"
    assert "source" not in character.json()
    assert "source" not in persona.json()
    assert "raw_card" not in character.text
    assert "private_import" not in persona.text


def test_authoring_read_rejects_unknown_kind_and_missing_item(temp_db, monkeypatch):
    with _client(monkeypatch) as client:
        unknown = client.get("/api/library/authoring/widget/1")
        missing = client.get("/api/library/authoring/story/999999")

    assert unknown.status_code == 404
    assert missing.status_code == 404
