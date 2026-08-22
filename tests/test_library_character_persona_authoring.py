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


def test_generation_preview_writes_nothing_until_explicit_acceptance(
    temp_db, monkeypatch,
):
    character = default_character_data("Preview character")
    character["extension_payload"] = {"generated": [1, 2, 3]}
    persona = default_persona_data("Preview persona")
    persona["extension_payload"] = {"generated": True}
    monkeypatch.setattr(
        app_module, "generate_character_preview",
        lambda brief, language="en": character,
    )
    monkeypatch.setattr(
        app_module, "generate_persona_preview",
        lambda brief, language="en": persona,
    )
    before = {
        "characters": temp_db.q("SELECT COUNT(*) AS n FROM characters", one=True)["n"],
        "personas": temp_db.q("SELECT COUNT(*) AS n FROM personas", one=True)["n"],
    }

    with _client(monkeypatch) as client:
        char_preview = client.post(
            "/api/characters/generate-preview", json={"brief": "storm guide"},
        )
        persona_preview = client.post(
            "/api/personas/generate-preview", json={"brief": "quiet witness"},
        )
        assert temp_db.q("SELECT COUNT(*) AS n FROM characters", one=True)["n"] == before["characters"]
        assert temp_db.q("SELECT COUNT(*) AS n FROM personas", one=True)["n"] == before["personas"]
        accepted = client.post("/api/characters", json={"sheet": char_preview.json()["sheet"]})

    assert char_preview.status_code == 200, char_preview.text
    assert persona_preview.status_code == 200, persona_preview.text
    assert char_preview.json()["sheet"] == character
    assert persona_preview.json()["sheet"] == persona
    assert accepted.status_code == 200
    assert temp_db.q("SELECT COUNT(*) AS n FROM characters", one=True)["n"] == before["characters"] + 1
    stored = json.loads(temp_db.q(
        "SELECT sheet FROM characters WHERE id=?", (accepted.json()["id"],), one=True,
    )["sheet"])
    assert stored["extension_payload"] == {"generated": [1, 2, 3]}


def test_new_document_templates_are_complete_and_do_not_create_rows(
    temp_db, monkeypatch,
):
    before_characters = temp_db.q(
        "SELECT COUNT(*) AS n FROM characters", one=True,
    )["n"]
    before_personas = temp_db.q(
        "SELECT COUNT(*) AS n FROM personas", one=True,
    )["n"]
    with _client(monkeypatch) as client:
        character = client.get("/api/characters/new-document")
        persona = client.get("/api/personas/new-document")

    assert character.status_code == 200
    assert persona.status_code == 200
    character_sheet = character.json()["sheet"]
    persona_sheet = persona.json()["sheet"]
    expected_character = default_character_data("Unnamed")
    expected_persona = default_persona_data("Player")
    assert set(character_sheet) == set(expected_character)
    assert set(persona_sheet) == set(expected_persona)
    assert character_sheet["identity"]["name"] == "Unnamed"
    assert persona_sheet["identity"]["name"] == "Player"
    assert character_sheet["identity"]["uid"].startswith("char_")
    assert persona_sheet["identity"]["uid"].startswith("persona_")
    assert temp_db.q("SELECT COUNT(*) AS n FROM characters", one=True)["n"] == before_characters
    assert temp_db.q("SELECT COUNT(*) AS n FROM personas", one=True)["n"] == before_personas


def test_fill_and_greeting_recovery_preview_use_current_draft_without_writing(
    temp_db, monkeypatch,
):
    seeded = _seed_people(temp_db)
    saved_before = temp_db.q(
        "SELECT sheet FROM characters WHERE id=?", (seeded["character"],), one=True,
    )["sheet"]
    draft = json.loads(saved_before)
    draft["identity"]["name"] = "Unsaved draft name"
    draft["draft_only"] = {"kept": True}
    filled = json.loads(json.dumps(draft))
    filled["psychology"]["drive"]["want"] = "Protect the crossing"
    recovered = json.loads(json.dumps(draft))
    recovered["opening"]["greetings"] = [{"prose": "Recovered hello"}]
    seen = {}

    def fake_fill(cid, brief, draft=None):
        seen["fill"] = draft
        return filled

    def fake_recover(cid, *, persist=True, draft=None):
        seen["recover"] = {"persist": persist, "draft": draft}
        return recovered

    monkeypatch.setattr(app_module, "fill_character_psychology", fake_fill)
    monkeypatch.setattr(app_module, "recover_greetings_from_source", fake_recover)
    with _client(monkeypatch) as client:
        fill = client.post(
            f"/api/characters/{seeded['character']}/fill_psychology",
            json={"brief": "complete gaps", "draft": draft},
        )
        recovery = client.post(
            f"/api/characters/{seeded['character']}/recover_greetings_preview",
            json={"draft": draft},
        )

    assert fill.status_code == 200, fill.text
    assert recovery.status_code == 200, recovery.text
    assert seen["fill"] == draft
    assert seen["recover"] == {"persist": False, "draft": draft}
    assert fill.json()["sheet"]["draft_only"] == {"kept": True}
    assert recovery.json()["sheet"]["opening"]["greetings"][0]["prose"] == "Recovered hello"
    assert temp_db.q(
        "SELECT sheet FROM characters WHERE id=?", (seeded["character"],), one=True,
    )["sheet"] == saved_before
