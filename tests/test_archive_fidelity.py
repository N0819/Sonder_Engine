"""Exact and atomic archive/lorebook round-trip regressions."""

from __future__ import annotations

import json
import time

import pytest

from web import app
from story import importers
from story.character_schema import default_character_data
from persist.checkpoints import ensure_checkpoint, restore_checkpoint
from core.frames import create_frame


def _chat(db, name="Archive"):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        (name, "", time.time()),
    )


def _character(db, name="Alice", uid="archive_alice"):
    return db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (
            name,
            json.dumps(default_character_data(name)),
            "{}",
            time.time(),
            uid,
        ),
    )


def test_chat_archive_preserves_lorebook_hierarchy_and_scope(temp_db):
    chat_id = _chat(temp_db)
    alice = _character(temp_db)
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, alice, "active", "{}"),
    )

    canon = temp_db.qi(
        "INSERT INTO lorebooks("
        "name,chat_id,book_type,scope_world_id,inheritance_mode,sort_order"
        ") VALUES(?,?,?,?,?,?)",
        ("World", chat_id, "world", "world_prime", "inherit", 4),
    )
    child = temp_db.qi(
        "INSERT INTO lorebooks("
        "name,chat_id,book_type,parent_id,scope_world_id,scope_location_id,"
        "inheritance_mode,sort_order,anchor_entity_id"
        ") VALUES(?,?,?,?,?,?,?,?,?)",
        (
            "Harbor",
            chat_id,
            "location",
            canon,
            "world_prime",
            "harbor",
            "isolated",
            9,
            "harbor_entity",
        ),
    )
    temp_db.qi("UPDATE chats SET lorebook_id=? WHERE id=?", (canon, chat_id))
    # Child-before-parent ordering in the payload exercises the import's
    # deferred parent pass rather than relying on the export's row order.
    ensure_checkpoint(chat_id, 0)
    exported = app.chat_export(chat_id)
    exported["lorebooks"].sort(
        key=lambda item: 0 if item["book"]["id"] == child else 1
    )

    imported = app.chat_import({"data": exported})
    new_chat_id = imported["id"]
    books = {
        row["name"]: dict(row)
        for row in temp_db.q(
            "SELECT * FROM lorebooks WHERE chat_id=?", (new_chat_id,)
        )
    }
    assert books["Harbor"]["parent_id"] == books["World"]["id"]
    assert books["Harbor"]["book_type"] == "location"
    assert books["Harbor"]["scope_world_id"] == "world_prime"
    assert books["Harbor"]["scope_location_id"] == "harbor"
    assert books["Harbor"]["inheritance_mode"] == "isolated"
    assert books["Harbor"]["sort_order"] == 9
    assert books["Harbor"]["anchor_entity_id"] == "harbor_entity"

    # The imported checkpoint carries the remapped hierarchy too, and remains
    # restorable rather than reintroducing source-install book ids.
    blob = json.loads(
        temp_db.q(
            "SELECT blob FROM checkpoints WHERE chat_id=? AND turn_idx=0",
            (new_chat_id,),
            one=True,
        )["blob"]
    )
    by_name = {book["name"]: book for book in blob["lorebooks"]}
    assert by_name["Harbor"]["parent_id"] == by_name["World"]["lorebook_id"]
    restore_checkpoint(new_chat_id, 0)
    restored = temp_db.q(
        "SELECT parent_id FROM lorebooks WHERE chat_id=? AND name='Harbor'",
        (new_chat_id,),
        one=True,
    )
    assert restored["parent_id"] == books["World"]["id"]


def test_checkpoint_cross_install_ids_are_remapped_fail_closed():
    blob = {
        "memories": [
            {"char_id": 10, "turn_id": 20, "frame_id": 30, "content": "kept"},
            {"char_id": 11, "turn_id": 20, "frame_id": 30, "content": "drop"},
        ],
        "memory_summaries": [
            {"char_id": 10, "summary": "kept"},
            {"char_id": 11, "summary": "drop"},
        ],
        "chars": {"10": {"state": {}}, "11": {"state": {}}},
        "char_frames": [
            {"char_id": 10, "frame_id": 30},
            {"char_id": 11, "frame_id": 30},
        ],
        "frames": [
            {
                "id": 30,
                "parent_frame_id": None,
                "travelers": "[10, 11]",
                "nonexistent_cast": "[11]",
            }
        ],
        "chat_personas": [
            {"persona_id": 40, "frame_id": 30},
            {"persona_id": 41, "frame_id": 30},
        ],
    }

    app._remap_cp_blob(
        blob,
        {20: 200},
        {},
        None,
        char_idmap={10: 100},
        persona_idmap={40: 400},
        frame_idmap={30: 300},
    )

    assert blob["memories"] == [
        {
            "char_id": 100,
            "turn_id": 200,
            "frame_id": 300,
            "content": "kept",
        }
    ]
    assert blob["memory_summaries"] == [{"char_id": 100, "summary": "kept"}]
    assert list(blob["chars"]) == ["100"]
    assert blob["char_frames"] == [{"char_id": 100, "frame_id": 300}]
    assert json.loads(blob["frames"][0]["travelers"]) == [100]
    assert json.loads(blob["frames"][0]["nonexistent_cast"]) == []
    assert blob["chat_personas"] == [{"persona_id": 400, "frame_id": 300}]


def test_live_frame_membership_uses_remapped_character_ids(temp_db):
    chat_id = _chat(temp_db)
    alice = _character(temp_db)
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, alice, "active", "{}"),
    )
    create_frame(
        chat_id,
        label="Past",
        ordinal=-1,
        kind="past",
        travelers=[alice],
        nonexistent_cast=[alice],
    )
    exported = app.chat_export(chat_id)
    fake_source_id = alice + 10_000
    exported["resources"]["characters"][0]["old_id"] = fake_source_id
    exported["participants"][0]["char_id"] = fake_source_id
    exported["frames"][0]["travelers"] = json.dumps([fake_source_id])
    exported["frames"][0]["nonexistent_cast"] = json.dumps([fake_source_id])

    imported = app.chat_import({"data": exported})
    frame = temp_db.q(
        "SELECT travelers,nonexistent_cast FROM frames WHERE chat_id=?",
        (imported["id"],),
        one=True,
    )
    assert json.loads(frame["travelers"]) == [alice]
    assert json.loads(frame["nonexistent_cast"]) == [alice]


def test_chat_import_failure_rolls_back_new_resources_and_chat(temp_db):
    archive = {
        "version": 4,
        "chat": {"id": 90, "name": "Broken", "scenario": ""},
        "resources": {
            "characters": [
                {
                    "old_id": 900,
                    "resource_uid": "atomic_import_character",
                    "sheet": default_character_data("Atomic"),
                    "source": {},
                }
            ]
        },
        "participants": [
            {"char_id": 900, "status": "active", "state": "{}"}
        ],
        # Duplicate turn indexes violate the per-chat unique constraint after
        # both the resource and chats row have already been inserted.
        "turns": [
            {"id": 1, "idx": 0, "player_input": "one"},
            {"id": 2, "idx": 0, "player_input": "two"},
        ],
    }

    with pytest.raises(Exception):
        app.chat_import({"data": archive})

    assert temp_db.q(
        "SELECT id FROM characters WHERE resource_uid='atomic_import_character'",
        one=True,
    ) is None
    assert temp_db.q(
        "SELECT id FROM chats WHERE name='Broken (import)'", one=True
    ) is None


def test_native_lorebook_import_is_atomic_and_preserves_metadata(
    temp_db, monkeypatch
):
    payload = {
        "name": "Scoped",
        "book_type": "location",
        "summary": "A scoped book",
        "scope_world_id": "world_a",
        "scope_location_id": "room_a",
        "inheritance_mode": "reference_only",
        "sort_order": 7,
        "anchor_entity_id": "ship_a",
        "entries": [
            {"entry_uid": "source_1", "keys": "one", "content": "First"},
            {"entry_uid": "source_2", "keys": "two", "content": "Second"},
        ],
    }
    monkeypatch.setattr(
        importers,
        "_prepared_lore_embeddings",
        lambda entries: [[0.0, 0.0] for _ in entries],
    )
    original_add = importers.add_lore
    calls = 0

    def fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("second entry failed")
        return original_add(*args, **kwargs)

    monkeypatch.setattr(importers, "add_lore", fail_second)
    with pytest.raises(RuntimeError, match="second entry failed"):
        importers.import_lorebook(payload)
    assert temp_db.q(
        "SELECT id FROM lorebooks WHERE name='Scoped'", one=True
    ) is None

    monkeypatch.setattr(importers, "add_lore", original_add)
    book_id, count = importers.import_lorebook(payload)
    assert count == 2
    row = temp_db.q(
        "SELECT * FROM lorebooks WHERE id=?", (book_id,), one=True
    )
    assert row["scope_world_id"] == "world_a"
    assert row["scope_location_id"] == "room_a"
    assert row["inheritance_mode"] == "reference_only"
    assert row["sort_order"] == 7
    assert row["anchor_entity_id"] == "ship_a"


def test_standalone_lore_export_round_trips_scope_metadata(
    temp_db, monkeypatch,
):
    book_id = temp_db.qi(
        "INSERT INTO lorebooks("
        "name,book_type,summary,scope_world_id,scope_location_id,"
        "inheritance_mode,sort_order,anchor_entity_id"
        ") VALUES(?,?,?,?,?,?,?,?)",
        (
            "Scoped export",
            "location",
            "Harbor notes",
            "world_a",
            "harbor",
            "reference_only",
            12,
            "harbor_entity",
        ),
    )
    temp_db.qi(
        "INSERT INTO lore_entries("
        "lorebook_id,keys,content,entry_uid,embedding"
        ") VALUES(?,?,?,?,?)",
        (book_id, "harbor", "Stone quays.", "scope_export_entry", b""),
    )
    monkeypatch.setattr(
        importers,
        "_prepared_lore_embeddings",
        lambda entries: [[0.0, 0.0] for _ in entries],
    )

    exported = app.lore_export(book_id)
    imported_id, count = importers.import_lorebook(exported)

    assert count == 1
    imported = temp_db.q(
        "SELECT * FROM lorebooks WHERE id=?", (imported_id,), one=True
    )
    assert imported["book_type"] == "location"
    assert imported["summary"] == "Harbor notes"
    assert imported["scope_world_id"] == "world_a"
    assert imported["scope_location_id"] == "harbor"
    assert imported["inheritance_mode"] == "reference_only"
    assert imported["sort_order"] == 12
    assert imported["anchor_entity_id"] == "harbor_entity"


def test_native_entry_list_import_does_not_require_book_metadata(
    temp_db, monkeypatch,
):
    monkeypatch.setattr(
        importers,
        "_prepared_lore_embeddings",
        lambda entries: [[0.0, 0.0] for _ in entries],
    )

    book_id, count = importers.import_lorebook([
        {
            "entry_uid": "list_native_entry",
            "keys": "key",
            "content": "Portable entry",
        }
    ])

    assert count == 1
    assert temp_db.q(
        "SELECT id FROM lorebooks WHERE id=?", (book_id,), one=True
    ) is not None
