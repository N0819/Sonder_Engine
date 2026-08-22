"""Truthful unified Library projection and reversible lifecycle state."""

from __future__ import annotations

import json
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


def _sheet(name: str, description: str = "", tags=()):
    return json.dumps({
        "name": name,
        "description": description,
        "tags": list(tags),
        "private_history": "must not enter the Library projection",
    })


def _seed_library(db):
    now = time.time()
    persona_main = db.qi(
        "INSERT INTO personas(name,sheet,source,resource_uid) VALUES(?,?,?,?)",
        ("Mira", _sheet("Mira", "Patient cartographer"), "{}", "persona-mira"),
    )
    persona_unused = db.qi(
        "INSERT INTO personas(name,sheet,source,resource_uid) VALUES(?,?,?,?)",
        ("Rowan", _sheet("Rowan", "Unassigned traveler"), "{}", "persona-rowan"),
    )
    story_a = db.qi(
        "INSERT INTO chats(name,persona_id,scenario,created) VALUES(?,?,?,?)",
        ("Lantern Archive", persona_main, "Rain on old glass", now - 20),
    )
    story_b = db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Quiet Road", "A road under snow", now - 10),
    )
    char_used = db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Asha", _sheet("Asha", "Archive keeper", ["scholar"]), "{}", now - 30, "char-asha"),
    )
    char_unused = db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Bryn", _sheet("Bryn", "Unassigned courier"), "{}", now - 5, "char-bryn"),
    )
    db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (story_a, char_used, "active", json.dumps({"secret": "runtime only"})),
    )
    db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (story_b, char_used, "dormant", "{}"),
    )
    db.qi(
        "INSERT INTO chat_personas(chat_id,persona_id,status) VALUES(?,?,?)",
        (story_b, persona_main, "active"),
    )

    lore_used = db.qi(
        "INSERT INTO lorebooks(name,summary,book_type,resource_uid) VALUES(?,?,?,?)",
        ("Shared Atlas", "Roads and archives", "world", "lore-atlas"),
    )
    lore_unused = db.qi(
        "INSERT INTO lorebooks(name,summary,book_type,resource_uid) VALUES(?,?,?,?)",
        ("Moon Notes", "Unassigned lunar notes", "general", "lore-moon"),
    )
    copied_a = db.qi(
        "INSERT INTO lorebooks(name,chat_id,origin_id,summary,book_type) "
        "VALUES(?,?,?,?,?)",
        ("Shared Atlas", story_a, lore_used, "Story copy A", "world"),
    )
    copied_b = db.qi(
        "INSERT INTO lorebooks(name,chat_id,origin_id,summary,book_type) "
        "VALUES(?,?,?,?,?)",
        ("Shared Atlas", story_b, lore_used, "Story copy B", "world"),
    )
    db.qi(
        "INSERT INTO chat_lorebooks(chat_id,lorebook_id,origin_id,enabled) "
        "VALUES(?,?,?,1)",
        (story_a, copied_a, lore_used),
    )
    db.qi(
        "INSERT INTO chat_lorebooks(chat_id,lorebook_id,origin_id,enabled) "
        "VALUES(?,?,?,0)",
        (story_b, copied_b, lore_used),
    )
    story_owned = db.qi(
        "INSERT INTO lorebooks(name,chat_id,summary,book_type) VALUES(?,?,?,?)",
        ("Lantern Canon", story_a, "This story alone", "canon"),
    )
    db.qi("UPDATE chats SET lorebook_id=? WHERE id=?", (story_owned, story_a))
    return {
        "story_a": story_a,
        "story_b": story_b,
        "char_used": char_used,
        "char_unused": char_unused,
        "persona_main": persona_main,
        "persona_unused": persona_unused,
        "lore_used": lore_used,
        "lore_unused": lore_unused,
        "story_owned": story_owned,
        "copied_a": copied_a,
        "copied_b": copied_b,
    }


def _by_key(payload):
    return {item["key"]: item for item in payload["items"]}


def test_library_projection_normalizes_real_associations_without_private_state(
    temp_db, monkeypatch,
):
    seeded = _seed_library(temp_db)
    with _client(monkeypatch) as client:
        response = client.get("/api/library?limit=100")

    assert response.status_code == 200, response.text
    payload = response.json()
    items = _by_key(payload)
    used = items[f"character:{seeded['char_used']}"]
    assert used["use_count"] == 2
    assert [(row["story_id"], row["state"]) for row in used["associations"]] == [
        (seeded["story_a"], "active"),
        (seeded["story_b"], "dormant"),
    ]
    persona = items[f"persona:{seeded['persona_main']}"]
    assert [(row["story_id"], row["state"]) for row in persona["associations"]] == [
        (seeded["story_a"], "primary"),
        (seeded["story_b"], "active"),
    ]
    lore = items[f"lore:{seeded['lore_used']}"]
    assert lore["use_count"] == 2
    assert {row["story_item_id"] for row in lore["associations"]} == {
        seeded["copied_a"], seeded["copied_b"],
    }
    assert f"lore:{seeded['story_owned']}" not in items
    serialized = json.dumps(payload)
    assert "private_history" not in serialized
    assert "runtime only" not in serialized
    assert "sheet" not in serialized
    assert payload["page"]["returned"] == len(payload["items"])
    assert payload["facets"]["types"]["story"] == 2


def test_story_unassigned_multiple_and_search_scopes_follow_database_truth(
    temp_db, monkeypatch,
):
    seeded = _seed_library(temp_db)
    with _client(monkeypatch) as client:
        story = client.get(
            f"/api/library?scope=story&story_id={seeded['story_a']}&limit=100"
        ).json()
        unassigned = client.get(
            "/api/library?scope=unassigned&limit=100"
        ).json()
        multiple = client.get(
            "/api/library?scope=multiple&limit=100"
        ).json()
        searched = client.get(
            "/api/library?q=Quiet%20Road&types=character,persona,lore&limit=100"
        ).json()

    story_keys = set(_by_key(story))
    assert f"story:{seeded['story_a']}" in story_keys
    assert f"story:{seeded['story_b']}" not in story_keys
    assert f"character:{seeded['char_used']}" in story_keys
    assert f"persona:{seeded['persona_main']}" in story_keys
    assert f"lore:{seeded['lore_used']}" in story_keys
    assert f"lore:{seeded['story_owned']}" in story_keys
    owned = _by_key(story)[f"lore:{seeded['story_owned']}"]
    assert owned["reusable"] is False
    assert owned["associations"][0]["state"] == "owned"

    assert set(_by_key(unassigned)) == {
        f"character:{seeded['char_unused']}",
        f"persona:{seeded['persona_unused']}",
        f"lore:{seeded['lore_unused']}",
    }
    assert set(_by_key(multiple)) == {
        f"character:{seeded['char_used']}",
        f"persona:{seeded['persona_main']}",
        f"lore:{seeded['lore_used']}",
    }
    assert set(_by_key(searched)) == {
        f"character:{seeded['char_used']}",
        f"persona:{seeded['persona_main']}",
        f"lore:{seeded['lore_used']}",
    }


def test_archive_is_reversible_idempotent_and_separate_from_delete(
    temp_db, monkeypatch,
):
    seeded = _seed_library(temp_db)
    key = f"character:{seeded['char_used']}"
    with _client(monkeypatch) as client:
        archived = client.put(
            f"/api/library/character/{seeded['char_used']}/archive"
        )
        again = client.put(
            f"/api/library/character/{seeded['char_used']}/archive"
        )
        active = client.get("/api/library?types=character&limit=100").json()
        archive = client.get(
            "/api/library?types=character&visibility=archived&limit=100"
        ).json()
        restored = client.delete(
            f"/api/library/character/{seeded['char_used']}/archive"
        )
        visible = client.get("/api/library?types=character&limit=100").json()
        missing = client.put("/api/library/persona/999999/archive")

    assert archived.status_code == 200
    assert archived.json() == {"key": key, "archived": True, "changed": True}
    assert again.json() == {"key": key, "archived": True, "changed": False}
    assert key not in _by_key(active)
    assert key in _by_key(archive)
    assert restored.json() == {"key": key, "archived": False, "changed": True}
    assert key in _by_key(visible)
    assert missing.status_code == 404
    assert temp_db.q(
        "SELECT COUNT(*) AS n FROM characters WHERE id=?",
        (seeded["char_used"],), one=True,
    )["n"] == 1


def test_delete_cleans_library_lifecycle_metadata(temp_db, monkeypatch):
    seeded = _seed_library(temp_db)
    with _client(monkeypatch) as client:
        assert client.put(
            f"/api/library/character/{seeded['char_unused']}/archive"
        ).status_code == 200
        assert client.delete(
            f"/api/characters/{seeded['char_unused']}"
        ).status_code == 200

    assert temp_db.q(
        "SELECT 1 FROM library_item_state WHERE item_type='character' AND item_id=?",
        (seeded["char_unused"],), one=True,
    ) is None


def test_archive_metadata_never_enters_story_snapshots_or_exports(
    temp_db, monkeypatch,
):
    from persist.checkpoints import snapshot_state

    seeded = _seed_library(temp_db)
    with _client(monkeypatch) as client:
        assert client.put(
            f"/api/library/story/{seeded['story_a']}/archive"
        ).status_code == 200
        exported = client.get(f"/api/chats/{seeded['story_a']}/export")

    assert exported.status_code == 200
    assert "library_item_state" not in snapshot_state(seeded["story_a"])
    assert "library_item_state" not in exported.json()
    assert "library_item_state" not in json.dumps(exported.json())


def test_projection_validation_and_pagination_are_bounded_and_deterministic(
    temp_db, monkeypatch,
):
    now = time.time()
    for index in range(1005):
        name = f"Scale {index:04d}"
        temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (name, _sheet(name), "{}", now + index, f"scale-{index}"),
        )

    with _client(monkeypatch) as client:
        first = client.get(
            "/api/library?types=character&sort=name&offset=50&limit=50"
        )
        repeated = client.get(
            "/api/library?types=character&sort=name&offset=50&limit=50"
        )
        repeated_types = client.get(
            "/api/library?types=character&types=persona&limit=50"
        )
        capped = client.get("/api/library?types=character&limit=999")
        invalid_scope = client.get("/api/library?scope=folder")
        invalid_story = client.get("/api/library?scope=story")
        unsafe_query = client.get("/api/library?q=" + ("x" * 241))

    assert first.status_code == 200
    assert first.json() == repeated.json()
    page = first.json()["page"]
    assert page == {"offset": 50, "limit": 50, "returned": 50, "total": 1005}
    assert first.json()["items"][0]["name"] == "Scale 0050"
    assert repeated_types.status_code == 200
    assert repeated_types.json()["query"]["types"] == ["character", "persona"]
    assert capped.status_code == 422
    assert invalid_scope.status_code == 422
    assert invalid_story.status_code == 422
    assert unsafe_query.status_code == 422
