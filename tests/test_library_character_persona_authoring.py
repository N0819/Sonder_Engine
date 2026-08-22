"""Lossless revision and duplicate contracts for reusable Library people."""

from __future__ import annotations

import json
import time

from fastapi.testclient import TestClient

from story.character_schema import default_character_data, default_persona_data
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


def _seed_people(db):
    character = default_character_data("Asha")
    character["extension_payload"] = {
        "kept": [1, {"nested": "exact"}], "enabled": True,
    }
    persona = default_persona_data("Mira")
    persona["extension_payload"] = {"kept": "persona-extension"}
    cid = db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Asha", json.dumps(character), json.dumps({
            "format": "imported", "original": {"name": "source Asha"},
        }), time.time(), "char-original"),
    )
    pid = db.qi(
        "INSERT INTO personas(name,sheet,source,resource_uid) VALUES(?,?,?,?)",
        ("Mira", json.dumps(persona), json.dumps({
            "format": "imported", "original": {"name": "source Mira"},
        }), "persona-original"),
    )
    story = db.qi(
        "INSERT INTO chats(name,persona_id,created) VALUES(?,?,?)",
        ("Source story", pid, time.time()),
    )
    db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (story, cid, "active", "{}"),
    )
    return {"character": cid, "persona": pid, "story": story}


def test_character_and_persona_revision_writes_preserve_unknown_fields(
    temp_db, monkeypatch,
):
    seeded = _seed_people(temp_db)
    with _client(monkeypatch) as client:
        character = client.get(
            f"/api/library/authoring/character/{seeded['character']}"
        ).json()
        persona = client.get(
            f"/api/library/authoring/persona/{seeded['persona']}"
        ).json()
        character["document"]["identity"]["name"] = "Asha Vale"
        persona["document"]["identity"]["name"] = "Mira Vale"
        char_saved = client.put(
            f"/api/characters/{seeded['character']}", json={
                "sheet": character["document"],
                "expected_revision": character["revision"],
            },
        )
        persona_saved = client.put(
            f"/api/personas/{seeded['persona']}", json={
                "sheet": persona["document"],
                "expected_revision": persona["revision"],
            },
        )

    assert char_saved.status_code == 200, char_saved.text
    assert persona_saved.status_code == 200, persona_saved.text
    assert char_saved.json()["document"]["extension_payload"] == {
        "kept": [1, {"nested": "exact"}], "enabled": True,
    }
    assert persona_saved.json()["document"]["extension_payload"] == {
        "kept": "persona-extension",
    }
    assert char_saved.json()["owner"] == f"character:{seeded['character']}"
    assert persona_saved.json()["owner"] == f"persona:{seeded['persona']}"


def test_character_stale_revision_refuses_write_and_preserves_draft_authority(
    temp_db, monkeypatch,
):
    seeded = _seed_people(temp_db)
    with _client(monkeypatch) as client:
        before = client.get(
            f"/api/library/authoring/character/{seeded['character']}"
        ).json()
        first = dict(before["document"])
        first["identity"] = {**first["identity"], "name": "First writer"}
        accepted = client.put(f"/api/characters/{seeded['character']}", json={
            "sheet": first, "expected_revision": before["revision"],
        })
        stale = dict(before["document"])
        stale["identity"] = {**stale["identity"], "name": "Stale writer"}
        conflict = client.put(f"/api/characters/{seeded['character']}", json={
            "sheet": stale, "expected_revision": before["revision"],
        })

    assert accepted.status_code == 200
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["owner"] == f"character:{seeded['character']}"
    assert temp_db.q(
        "SELECT name FROM characters WHERE id=?", (seeded["character"],), one=True,
    )["name"] == "First writer"


def test_duplicate_people_mints_new_identities_without_copying_memberships(
    temp_db, monkeypatch,
):
    seeded = _seed_people(temp_db)
    originals = {
        "character": json.loads(temp_db.q(
            "SELECT sheet FROM characters WHERE id=?", (seeded["character"],), one=True,
        )["sheet"]),
        "persona": json.loads(temp_db.q(
            "SELECT sheet FROM personas WHERE id=?", (seeded["persona"],), one=True,
        )["sheet"]),
    }
    with _client(monkeypatch) as client:
        char_copy = client.post(
            f"/api/characters/{seeded['character']}/duplicate"
        )
        persona_copy = client.post(
            f"/api/personas/{seeded['persona']}/duplicate"
        )

    assert char_copy.status_code == 200, char_copy.text
    assert persona_copy.status_code == 200, persona_copy.text
    copies = {"character": char_copy.json(), "persona": persona_copy.json()}
    for kind, original_id in (
        ("character", seeded["character"]), ("persona", seeded["persona"]),
    ):
        payload = copies[kind]
        assert payload["id"] != original_id
        assert payload["duplicate_of"] == f"{kind}:{original_id}"
        assert payload["document"]["identity"]["uid"] != originals[kind]["identity"]["uid"]
        without_uid = json.loads(json.dumps(payload["document"]))
        without_uid["identity"]["uid"] = originals[kind]["identity"]["uid"]
        assert without_uid == originals[kind]
        table = "characters" if kind == "character" else "personas"
        row = temp_db.q(
            f"SELECT resource_uid,source FROM {table} WHERE id=?",
            (payload["id"],), one=True,
        )
        assert row["resource_uid"] not in (None, f"{kind}-original")
        expected_source = "char-original" if kind == "character" else "persona-original"
        assert json.loads(row["source"])["duplicated_from"] == expected_source

    assert temp_db.q(
        "SELECT 1 FROM chat_chars WHERE char_id=?",
        (char_copy.json()["id"],), one=True,
    ) is None
    assert temp_db.q(
        "SELECT 1 FROM chats WHERE persona_id=?",
        (persona_copy.json()["id"],), one=True,
    ) is None
