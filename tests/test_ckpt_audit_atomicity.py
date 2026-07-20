"""Checkpoint audit finding 3: _restore_checkpoint_body must be atomic.
Previously it ran ~15 autocommitting statements (with an embedding call
mid-way), so a crash partway left world state restored but memories and
entity tables half-gone. Now the whole restore runs in one transaction:
any failure rolls everything back and the chat stays exactly as it was."""

import json
import time

import pytest

import memory
from character_schema import default_character_data
from checkpoints import ensure_checkpoint, restore_checkpoint
from memory import add_memory
from providers import EmbeddingBatch


def _install_stub(monkeypatch):
    def fake_meta(texts):
        return EmbeddingBatch(vectors=[[1.0] * 8 for _ in texts],
                              model_key="test:model", dimensions=8)

    monkeypatch.setattr(memory, "embed_texts_meta", fake_meta)
    monkeypatch.setattr(memory, "embed_texts", lambda texts: fake_meta(texts).vectors)


def _chat_and_character(db):
    chat_id = db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    char_id = db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) VALUES(?,?,?,?,?)",
        ("Alice", json.dumps(default_character_data("Alice")), "{}", time.time(), "char_alice"),
    )
    db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"),
    )
    return chat_id, char_id


def test_failed_restore_rolls_back_all_state(temp_db, monkeypatch):
    _install_stub(monkeypatch)
    chat_id, char_id = _chat_and_character(temp_db)

    temp_db.wset(chat_id, "scene", {"v": 1})
    add_memory(chat_id, char_id, None, "episodic", "witnessed", 0.6,
               "First memory before the checkpoint.", turn_idx=1)
    ensure_checkpoint(chat_id, 2)

    # State moves on after the checkpoint...
    temp_db.wset(chat_id, "scene", {"v": 2})
    add_memory(chat_id, char_id, None, "episodic", "witnessed", 0.6,
               "Second memory after the checkpoint.", turn_idx=2)

    # ...and the checkpoint blob is corrupted so the restore blows up in
    # one of its LAST stages (fiction_locations insert -> KeyError),
    # i.e. after world/memories would already have been rewritten.
    row = temp_db.q(
        "SELECT * FROM checkpoints WHERE chat_id=? AND turn_idx=?",
        (chat_id, 2), one=True,
    )
    blob = json.loads(row["blob"])
    blob["fiction_locations"] = [{"location_id": 1}]  # missing world_id/name
    temp_db.qi("UPDATE checkpoints SET blob=? WHERE id=?", (json.dumps(blob), row["id"]))

    with pytest.raises(KeyError):
        restore_checkpoint(chat_id, 2)

    # Nothing may have changed: not the world blob...
    assert temp_db.wget(chat_id, "scene") == {"v": 2}
    # ...and not the memory bank (previously deleted before the crash point).
    rows = temp_db.q(
        "SELECT id,content FROM memories WHERE chat_id=? ORDER BY turn_idx", (chat_id,)
    )
    assert [r["content"] for r in rows] == [
        "First memory before the checkpoint.",
        "Second memory after the checkpoint.",
    ]
    # The FTS side of the bank must have survived the rollback too.
    for r in rows:
        assert len(temp_db.q(
            "SELECT * FROM memory_retrieval_fts WHERE memory_id=?", (str(r["id"]),)
        )) == 1


def test_successful_restore_behavior_is_unchanged(temp_db, monkeypatch):
    _install_stub(monkeypatch)
    chat_id, char_id = _chat_and_character(temp_db)

    temp_db.wset(chat_id, "scene", {"v": 1})
    add_memory(chat_id, char_id, None, "episodic", "witnessed", 0.6,
               "First memory before the checkpoint.", turn_idx=1)
    ensure_checkpoint(chat_id, 2)

    temp_db.wset(chat_id, "scene", {"v": 2})
    add_memory(chat_id, char_id, None, "episodic", "witnessed", 0.6,
               "Second memory after the checkpoint.", turn_idx=2)

    restore_checkpoint(chat_id, 2)

    assert temp_db.wget(chat_id, "scene") == {"v": 1}
    rows = temp_db.q("SELECT content FROM memories WHERE chat_id=?", (chat_id,))
    assert [r["content"] for r in rows] == ["First memory before the checkpoint."]
