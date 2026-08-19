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
from tests.helpers import patch_embedding_seam


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


def _crossable_chat(db):
    """A chat holding one row of every id-bearing kind the remap must answer
    for, and two characters -- one that will map to the target install and one
    that will not.

    Built and then SNAPSHOTTED rather than hand-written. The blob this test
    used to declare was a six-key literal that never called `snapshot_state`:
    it could not notice a new table joining the checkpoint, and it had not --
    `relationship_events` shipped with checkpoint, archive and delete support
    and was absent here, so the fail-closed rule that DROPS a stance whose
    character does not map was asserted by nothing.
    """
    chat_id = _chat(db, "Crossing")
    kept = _character(db, "Kept", "uid_kept")
    dropped = _character(db, "Dropped", "uid_dropped")
    for char_id in (kept, dropped):
        db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
              "VALUES(?,?,?,?)", (chat_id, char_id, "active", "{}"))
    frame_id = create_frame(chat_id, label="Past", ordinal=-10, kind="past")
    db.qi("UPDATE frames SET travelers=?, nonexistent_cast=? WHERE id=?",
          (json.dumps([kept, dropped]), json.dumps([dropped]), frame_id))
    turn_id = db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
        "VALUES(?,?,?,?,?)", (chat_id, 0, "", time.time(), frame_id))
    persona_id = db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        ("Player", "{}", "{}"))
    db.qi("INSERT INTO chat_personas(chat_id,persona_id,status,frame_id) "
          "VALUES(?,?,?,?)", (chat_id, persona_id, "active", frame_id))
    for char_id, content in ((kept, "kept"), (dropped, "drop")):
        db.qi("INSERT INTO memories(chat_id,char_id,turn_id,turn_idx,content,"
              "frame_id) VALUES(?,?,?,?,?,?)",
              (chat_id, char_id, turn_id, 0, content, frame_id))
        db.qi("INSERT INTO memory_summaries(chat_id,char_id,scope,summary,"
              "updated) VALUES(?,?,?,?,?)",
              (chat_id, char_id, "autobiographical", content, time.time()))
        db.qi("INSERT INTO chat_char_frames(chat_id,char_id,frame_id,state) "
              "VALUES(?,?,?,?)", (chat_id, char_id, frame_id, "{}"))
        db.qi("INSERT INTO relationship_events(chat_id,frame_id,char_id,target,"
              "axis,delta,turn_idx,created) VALUES(?,?,?,?,?,?,?,?)",
              (chat_id, frame_id, char_id, "Someone", "trust", -0.2, 0,
               time.time()))
    return chat_id, kept, dropped, frame_id, turn_id, persona_id


def test_checkpoint_cross_install_ids_are_remapped_fail_closed(temp_db):
    from persist.checkpoints import snapshot_state

    chat_id, kept, dropped, frame_id, turn_id, persona_id = _crossable_chat(
        temp_db)
    blob = snapshot_state(chat_id)

    # Every id-bearing collection this remap is responsible for is present
    # because the snapshot produced it, not because this test typed it.
    for key in ("memories", "memory_summaries", "chars", "char_frames",
                "frames", "chat_personas", "relationship_events"):
        assert blob.get(key), f"{key} missing from the snapshot"

    app._remap_cp_blob(
        blob,
        {turn_id: 200},
        {},
        None,
        char_idmap={kept: 100},
        persona_idmap={persona_id: 400},
        frame_idmap={frame_id: 300},
    )

    assert [(m["char_id"], m["turn_id"], m["frame_id"], m["content"])
            for m in blob["memories"]] == [(100, 200, 300, "kept")]
    assert [(s["char_id"], s["summary"]) for s in blob["memory_summaries"]] \
        == [(100, "kept")]
    assert list(blob["chars"]) == ["100"]
    assert [(cf["char_id"], cf["frame_id"]) for cf in blob["char_frames"]] \
        == [(100, 300)]
    assert json.loads(blob["frames"][0]["travelers"]) == [100]
    assert json.loads(blob["frames"][0]["nonexistent_cast"]) == []
    assert [(p["persona_id"], p["frame_id"]) for p in blob["chat_personas"]] \
        == [(400, 300)]
    # The stance whose character did not cross is gone rather than reattached
    # to whoever inherited the number.
    assert [(r["char_id"], r["frame_id"]) for r in blob["relationship_events"]] \
        == [(100, 300)]


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


def test_chat_import_keeps_every_column_the_memory_dump_carried(
    temp_db, monkeypatch,
):
    """An archive's memory rows survive the import with what the dump carried.

    `dump_chat_memories` inlines the vectors precisely so an import does not
    have to re-embed, and carries the encoding affect because it is not
    re-derivable from the row's text. Both are worth nothing if the import
    re-lists the columns by hand: a hand-written projection is what decides
    which of the dump's keys reach the new database, and it silently drops
    whichever key the dump grew last.
    """
    from mind import memory as memory_mod
    from llm.providers import EmbeddingBatch

    calls = {"n": 0}

    def fake_meta(texts):
        calls["n"] += 1
        return EmbeddingBatch(
            vectors=[[0.25 + i] * 8 for i, _ in enumerate(texts)],
            model_key="openai:1:text-embedding-real",
            dimensions=8,
        )

    patch_embedding_seam(monkeypatch, "embed_texts_meta", fake_meta)
    monkeypatch.setattr(
        memory_mod, "embed_texts", lambda texts: fake_meta(texts).vectors
    )

    chat_id = _chat(temp_db, "Fidelity")
    alice = _character(temp_db, "Alice", "fidelity_alice")
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, alice, "active", "{}"),
    )
    memory_mod.add_memory(
        chat_id, alice, None, "episodic", "witnessed", 0.7,
        "Alice watched the cellar door swing open.",
        turn_idx=1, valence=-0.4, arousal=0.6,
        encoding_valence=-0.8, encoding_arousal=0.9,
    )
    columns = (
        "embedding,cue_embedding,embedding_model,embedding_dim,"
        "encoding_valence,encoding_arousal"
    )
    before = temp_db.q(
        f"SELECT {columns} FROM memories WHERE chat_id=?",
        (chat_id,), one=True,
    )
    assert before["embedding_model"] == "openai:1:text-embedding-real"

    archive = app.chat_export(chat_id)
    calls["n"] = 0
    result = app.chat_import({"data": json.loads(json.dumps(archive))})

    after = temp_db.q(
        f"SELECT {columns} FROM memories WHERE chat_id=?",
        (result["id"],), one=True,
    )
    assert after is not None
    # The carried vectors were used, not paid for again.
    assert calls["n"] == 0
    assert bytes(after["embedding"]) == bytes(before["embedding"])
    assert bytes(after["cue_embedding"]) == bytes(before["cue_embedding"])
    assert after["embedding_model"] == before["embedding_model"]
    assert after["embedding_dim"] == before["embedding_dim"]
    assert after["encoding_valence"] == before["encoding_valence"]
    assert after["encoding_arousal"] == before["encoding_arousal"]


class TestASecretDoesNotRideAnArchive:
    """WEB-19. The presence-id namespace is a per-install secret.

    Anonymous presence ids are a hash of canonical data a `story_view` caller
    can read for itself, salted with a random namespace; the salt is the whole
    reason a guessed identity cannot be confirmed by enumeration. An archive
    is a file a host hands to somebody else, so a namespace inside one hands
    over the ability to invert every anonymous body in that story.

    It rode out TWICE, which is why the guard is asserted in both places: once
    as a plain `world` row (the export is `SELECT *`), and again inside every
    checkpoint blob, which is `snapshot_state`'s copy of the same table.
    """

    def _exported(self, db, chat_id):
        from web.story_view import PRESENCE_NAMESPACE_KEY

        db.wset(chat_id, PRESENCE_NAMESPACE_KEY, "deadbeef" * 4)
        ensure_checkpoint(chat_id, 0)
        return json.loads(json.dumps(app.chat_export(chat_id)))

    def test_the_namespace_is_not_a_world_row_in_the_archive(self, temp_db):
        from web.story_view import PRESENCE_NAMESPACE_KEY

        chat_id = _chat(temp_db)
        export = self._exported(temp_db, chat_id)
        assert PRESENCE_NAMESPACE_KEY not in (export["world"] or {})

    def test_the_namespace_is_not_inside_a_carried_checkpoint(self, temp_db):
        chat_id = _chat(temp_db)
        export = self._exported(temp_db, chat_id)
        assert export["checkpoints"], "the checkpoint half needs a checkpoint"
        for row in export["checkpoints"]:
            assert "deadbeef" not in row["blob"]

    def test_the_stripped_key_is_the_one_story_view_mints(self):
        """The two modules must not drift: `persist` cannot import `web`, so
        the name is spelled twice and this is what keeps the copies honest."""
        from persist.chat_archive import UNEXPORTED_WORLD_KEYS
        from web.story_view import PRESENCE_NAMESPACE_KEY

        assert PRESENCE_NAMESPACE_KEY in UNEXPORTED_WORLD_KEYS

    def test_the_story_itself_still_exports(self, temp_db):
        """Stripping one key is not a licence to drop the world."""
        chat_id = _chat(temp_db)
        temp_db.wset(chat_id, "simulation_clock", {"elapsed_seconds": 12.0})
        export = self._exported(temp_db, chat_id)
        assert export["world"]["simulation_clock"] == {"elapsed_seconds": 12.0}
        assert "simulation_clock" in export["checkpoints"][0]["blob"]
