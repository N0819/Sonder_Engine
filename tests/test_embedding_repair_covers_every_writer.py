"""Every embedding writer checks `fallback` and queues (review 2026-09-07 A60).

`embed_texts_meta` degrades to a crc32 hash on any provider error and SAYS SO
on the batch. `_upsert_memory` and the summary writer read that flag and hand
the row to the repair lane (`note_failed_embedding_write`), which waits out the
rate-limit window and finishes the write. Two writers of the same columns did
not:

* `_embed_lore_document` -- the whole lore write path, `add_lore`,
  `update_lore` and `set_lore_overlay` -- discarded `got.fallback` entirely,
  and `_REPAIR_PENDING` had exactly two tables, so a lore entry written during
  a depleted window stayed a hash. It then competed on the 0.35 keyword term
  alone (`search_lore`'s "scored blind" count) until a host chose a
  whole-corpus rebuild, which is the remedy the lane exists to avoid;
* `update_memory` -- the host's own Memories-tab edit -- re-embedded and
  stored the result without ever asking whether it was real, so an edit made
  in a bad window replaced a good vector with a hash and queued nothing.

The rule that now holds: a writer that stores an embedding reads `fallback`
and queues, and the lane's table registry is what says which tables it knows.
"""

from __future__ import annotations

import json
import time

import numpy as np
import pytest

from mind import memory
from mind import memory_write
from tests.helpers import patch_provider_seam
from llm.providers import EmbeddingBatch
from story.character_schema import default_character_data


REAL = "openrouter:3:perplexity/pplx-embed-v1-4b"


def _real_batch(texts, **_kw):
    v = np.ones(2560, dtype=np.float32) / np.sqrt(2560)
    return EmbeddingBatch(vectors=[v for _ in texts], model_key=REAL,
                          dimensions=2560, fallback=False)


def _fallen_back(texts, **_kw):
    v = np.ones(256, dtype=np.float32) / np.sqrt(256)
    return EmbeddingBatch(vectors=[v for _ in texts],
                          model_key="cheap:crc32:256", dimensions=256,
                          fallback=True, error="429 rate limited")


@pytest.fixture
def bank(temp_db, monkeypatch):
    monkeypatch.setattr(memory_write, "_ensure_repair_thread", lambda: None)
    patch_provider_seam(monkeypatch, "embedding_model_key", lambda: REAL)
    for pending in memory._REPAIR_PENDING.values():
        pending.clear()
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Repair", "", time.time()))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Hinami", json.dumps(default_character_data("Hinami")), "{}",
         time.time(), "char_hinami"))
    book = temp_db.qi(
        "INSERT INTO lorebooks(name,chat_id,book_type,summary) "
        "VALUES(?,?,?,?)", ("Canon", chat_id, "general", ""))
    temp_db.qi("UPDATE chats SET lorebook_id=? WHERE id=?", (book, chat_id))
    return {"chat": chat_id, "char": char_id, "book": book}


def _stamp(temp_db, table, row_id):
    return temp_db.q(f"SELECT embedding_model FROM {table} WHERE id=?",
                     (row_id,), one=True)["embedding_model"]


def test_a_lore_write_that_fell_back_is_queued_and_then_finished(
        temp_db, bank, monkeypatch):
    patch_provider_seam(monkeypatch, "embed_texts_meta", _fallen_back)
    entry = memory.add_lore(bank["book"], "granary",
                            "The granary is kept by the miller.", turn_added=1)
    assert _stamp(temp_db, "lore_entries", entry) == "cheap:crc32:256"
    assert memory._REPAIR_PENDING["lore_entries"] == {entry}

    patch_provider_seam(monkeypatch, "embed_texts_meta", _real_batch)
    assert memory.repair_pending_embeddings()["lore_entries"] == 1
    assert _stamp(temp_db, "lore_entries", entry) == REAL
    assert memory._REPAIR_PENDING["lore_entries"] == set()


def test_a_lore_edit_that_fell_back_is_queued_too(temp_db, bank, monkeypatch):
    patch_provider_seam(monkeypatch, "embed_texts_meta", _real_batch)
    entry = memory.add_lore(bank["book"], "granary", "The granary.",
                            turn_added=1)
    assert not memory._REPAIR_PENDING["lore_entries"]

    patch_provider_seam(monkeypatch, "embed_texts_meta", _fallen_back)
    memory.update_lore(entry, "granary", "The granary is kept by the miller.")

    assert memory._REPAIR_PENDING["lore_entries"] == {entry}


def test_a_host_memory_edit_that_fell_back_is_queued(temp_db, bank,
                                                     monkeypatch):
    patch_provider_seam(monkeypatch, "embed_texts_meta", _real_batch)
    mid = memory.add_memory(bank["chat"], bank["char"], None, "episodic",
                            "witnessed", 0.6, "The route was fine.",
                            turn_idx=0)
    assert _stamp(temp_db, "memories", mid) == REAL

    patch_provider_seam(monkeypatch, "embed_texts_meta", _fallen_back)
    assert memory.update_memory(mid, content="The route was NOT fine.") is True

    assert _stamp(temp_db, "memories", mid) == "cheap:crc32:256"
    assert memory._REPAIR_PENDING["memories"] == {mid}


def test_a_previous_process_lore_row_is_adopted_when_the_chat_opens(
        temp_db, bank, monkeypatch):
    """The in-memory queue dies with the process, so `queue_fallback_rows_for
    _repair` picks the strays back up. An entry has no `chat_id`: it is
    reachable through its book's attachment, or by being the chat's canon."""
    patch_provider_seam(monkeypatch, "embed_texts_meta", _fallen_back)
    entry = memory.add_lore(bank["book"], "granary", "The granary.",
                            turn_added=1)
    for pending in memory._REPAIR_PENDING.values():
        pending.clear()

    found = memory.queue_fallback_rows_for_repair(bank["chat"])

    assert found["lore_entries"] == 1
    assert memory._REPAIR_PENDING["lore_entries"] == {entry}


def test_another_storys_lore_is_not_adopted(temp_db, bank, monkeypatch):
    """The narrowness the lane is built on: finishing a write this engine
    failed for THIS story, never re-embedding a corpus."""
    patch_provider_seam(monkeypatch, "embed_texts_meta", _fallen_back)
    other_chat = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Elsewhere", "", time.time()))
    other_book = temp_db.qi(
        "INSERT INTO lorebooks(name,chat_id,book_type,summary) "
        "VALUES(?,?,?,?)", ("Their canon", other_chat, "general", ""))
    temp_db.qi("UPDATE chats SET lorebook_id=? WHERE id=?",
               (other_book, other_chat))
    theirs = memory.add_lore(other_book, "granary", "Their granary.",
                             turn_added=1)
    mine = memory.add_lore(bank["book"], "granary", "My granary.",
                           turn_added=1)
    for pending in memory._REPAIR_PENDING.values():
        pending.clear()

    memory.queue_fallback_rows_for_repair(bank["chat"])

    assert memory._REPAIR_PENDING["lore_entries"] == {mine}
    assert theirs not in memory._REPAIR_PENDING["lore_entries"]


def _library_entry(temp_db, bank, keys="granary",
                   content="The granary is kept by the miller."):
    """A LIBRARY book (`chat_id` NULL) attached to the story -- the only shape
    an overlay is legal on: a story may not overlay its own book, nor another
    story's."""
    book = temp_db.qi(
        "INSERT INTO lorebooks(name,chat_id,book_type,summary) "
        "VALUES(?,?,?,?)", ("The library", None, "general", ""))
    temp_db.qi("INSERT INTO chat_lorebooks(chat_id,lorebook_id,enabled) "
               "VALUES(?,?,1)", (bank["chat"], book))
    return book, memory.add_lore(book, keys, content, turn_added=1)


def test_an_overlay_write_that_fell_back_is_queued(temp_db, bank, monkeypatch):
    """The third lore writer. `set_lore_overlay` embeds the story's own
    reading of a library entry, and that call falls back like any other."""
    patch_provider_seam(monkeypatch, "embed_texts_meta", _real_batch)
    _book, entry = _library_entry(temp_db, bank)

    patch_provider_seam(monkeypatch, "embed_texts_meta", _fallen_back)
    memory.set_lore_overlay(bank["chat"], entry,
                            content="The granary burned in the spring.")

    row = temp_db.q("SELECT id FROM lore_overlays WHERE chat_id=? AND "
                    "entry_id=?", (bank["chat"], entry), one=True)
    assert memory._REPAIR_PENDING["lore_overlays"] == {row["id"]}


def test_an_overlay_is_repaired_with_the_merged_document(temp_db, bank,
                                                         monkeypatch):
    """An overlay that overrides ONLY the content stores `keys` NULL, because
    both overlay text columns are nullable and NULL means "inherit". The
    writer embedded keys-from-the-library plus content-from-the-story; a
    repair that re-embedded the overlay row alone would file a vector for a
    text nobody ever reads -- the same fact stored twice and free to
    disagree."""
    patch_provider_seam(monkeypatch, "embed_texts_meta", _real_batch)
    _book, entry = _library_entry(temp_db, bank, keys="granary, miller")

    patch_provider_seam(monkeypatch, "embed_texts_meta", _fallen_back)
    memory.set_lore_overlay(bank["chat"], entry,
                            content="The granary burned in the spring.")
    assert temp_db.q("SELECT keys FROM lore_overlays WHERE chat_id=? AND "
                     "entry_id=?", (bank["chat"], entry),
                     one=True)["keys"] is None

    seen = []

    def _record(texts, **kw):
        seen.extend(texts)
        return _real_batch(texts, **kw)

    patch_provider_seam(monkeypatch, "embed_texts_meta", _record)
    assert memory.repair_pending_embeddings()["lore_overlays"] == 1

    assert seen == ["granary, miller The granary burned in the spring."], seen
