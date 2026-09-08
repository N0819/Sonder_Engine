"""An FTS sync trigger fires on the columns its index holds, and no others.

Found 2026-09-07 while testing A60, in `core/db.py`. `memories_fts` is an
external-content FTS5 index over ONE column, `memories.content`, kept in sync
by `memories_au` -- which fired on `AFTER UPDATE ON memories`, every column of
it. Since review C2 landed `memories_vkey_stale` -- an `AFTER UPDATE OF
embedding, cue_embedding` trigger that answers an embedding write with a
second `UPDATE memories SET vkey=NULL` -- one logical write ran the sync pair
TWICE:

    delete(old text) + insert(new text)      -- the caller's UPDATE
    delete(new text) + insert(new text)      -- the vkey trigger's UPDATE

REPRODUCED 2026-09-08 against this schema through `core.db.init()`: the single
statement `update_memory` issues -- `UPDATE memories SET content=?,
embedding=? WHERE id=?` -- raises `database disk image is malformed` from
inside the UPDATE, so the host's Memories-tab edit, the one path a person uses
to correct a memory by hand, fails outright. What the reproduction needs,
stated because each condition is ordinary and each one matters:

* the two triggers in the schema's own creation order -- `memories_au` in
  SCHEMA, `memories_vkey_stale` in LATE_SCHEMA. Created the other way round
  the pairs balance and nothing raises, which is why this is a narrowing and
  not a reordering: the order that fails is the order the engine ships;
* an embedding blob that actually CHANGES, so the vkey trigger's `WHEN` holds.
  A re-embed that returns the same bytes under a new model key does not fire
  it, and this file's own fixture made exactly that mistake at first -- which
  is how a version of it passed against the un-narrowed trigger;
* a replacement text that shares a token with the text it replaces, which is
  what an edit normally does. A rewrite sharing no token succeeds.

`PRAGMA recursive_triggers` makes no difference: reproduced at 0 and at 1. The
statement is rolled back with the index still passing `integrity-check`, so
this loses the edit and never the file -- which is also why the v38 -> v39
migration replaces the triggers and does NOT rebuild the indexes.

The rule that now holds: `memories_au` is `AFTER UPDATE OF content` and
`lore_au` is `AFTER UPDATE OF content, keys`. Stated for both, though only the
memories one has a second trigger beside it -- an index that resyncs on writes
it does not index is one trigger away from this every time.
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


def _batch(model_key, dims, tilt=0.0):
    """`tilt` is the part that matters, and it has to survive normalisation:
    two batches differing only in `model_key` -- or only in a scalar the unit
    vector divides straight back out -- write the SAME blob,
    `memories_vkey_stale`'s `WHEN` is false, and the second sync pair never
    runs."""
    def _make(texts, **_kw):
        v = np.ones(dims, dtype=np.float32)
        v[0] += tilt
        v = v / np.linalg.norm(v)
        return EmbeddingBatch(vectors=[v for _ in texts], model_key=model_key,
                              dimensions=dims, fallback=False)
    return _make


@pytest.fixture
def bank(temp_db, monkeypatch):
    monkeypatch.setattr(memory_write, "_ensure_repair_thread", lambda: None)
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Edits", "", time.time()))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Hinami", json.dumps(default_character_data("Hinami")), "{}",
         time.time(), "char_hinami"))
    return {"chat": chat_id, "char": char_id}


def _integrity(temp_db, table):
    temp_db.qi(f"INSERT INTO {table}({table}) VALUES('integrity-check')")


def _edited(bank, monkeypatch):
    """One memory, then a provider that returns DIFFERENT bytes, so the edit
    that follows is the shape a real host edit has."""
    patch_provider_seam(monkeypatch, "embed_texts_meta", _batch("real:a", 8))
    mid = memory.add_memory(bank["chat"], bank["char"], None, "episodic",
                            "witnessed", 0.6, "The route was fine.",
                            turn_idx=0)
    patch_provider_seam(monkeypatch, "embed_texts_meta",
                        _batch("real:b", 8, tilt=3.0))
    return mid


def test_the_two_triggers_are_created_in_the_order_that_fails(temp_db):
    """The precondition the reproduction rests on, pinned so a later schema
    edit cannot quietly move `memories_vkey_stale` above `memories_au` and
    leave the tests below passing for a reason nobody chose."""
    names = [r["name"] for r in temp_db.q(
        "SELECT name FROM sqlite_master WHERE type='trigger' "
        "AND tbl_name='memories' ORDER BY rowid")]

    assert names.index("memories_au") < names.index("memories_vkey_stale")


def test_a_host_edit_that_rewrites_a_memory_does_not_corrupt_the_index(
        temp_db, bank, monkeypatch):
    """The replacement text SHARES TOKENS with what it replaced, which is what
    an edit normally does and is exactly the shape that raised."""
    mid = _edited(bank, monkeypatch)

    assert memory.update_memory(mid, content="The route was NOT fine.") is True

    _integrity(temp_db, "memories_fts")
    assert temp_db.q("SELECT content FROM memories WHERE id=?", (mid,),
                     one=True)["content"] == "The route was NOT fine."


def test_the_edit_really_rewrites_the_embedding_the_vkey_trigger_watches(
        temp_db, bank, monkeypatch):
    """Without this the test above proves nothing: a fixture whose re-embed
    returns identical bytes leaves `memories_vkey_stale`'s `WHEN` false, the
    second sync pair never runs, and the un-narrowed trigger passes.

    Two halves, because `update_memory` re-files the address afterwards
    (`memory_snapshot.file_memory_vector`) and so cannot be read for whether
    the trigger fired: the edit changes the blob, and a blob change is what
    fires the trigger."""
    mid = _edited(bank, monkeypatch)
    before = temp_db.q("SELECT embedding FROM memories WHERE id=?", (mid,),
                       one=True)["embedding"]

    memory.update_memory(mid, content="The route was NOT fine.")

    after = temp_db.q("SELECT embedding FROM memories WHERE id=?", (mid,),
                      one=True)["embedding"]
    assert bytes(after) != bytes(before)

    temp_db.qi("UPDATE memories SET vkey='addressed' WHERE id=?", (mid,))
    temp_db.qi("UPDATE memories SET embedding=? WHERE id=?", (b"different",
                                                              mid))
    assert temp_db.q("SELECT vkey FROM memories WHERE id=?", (mid,),
                     one=True)["vkey"] is None


def test_the_index_holds_the_new_text_once(temp_db, bank, monkeypatch):
    mid = _edited(bank, monkeypatch)

    memory.update_memory(mid, content="The route was NOT fine.")

    rows = temp_db.q("SELECT rowid FROM memories_fts WHERE memories_fts "
                     "MATCH ?", ('"route"',))
    assert [r["rowid"] for r in rows] == [mid]


def test_a_write_that_touches_no_indexed_column_leaves_the_index_alone(
        temp_db, bank, monkeypatch):
    """The narrowing itself: the repair lane rewrites embeddings and nothing
    else, and that must not put the FTS through a delete/insert cycle."""
    patch_provider_seam(monkeypatch, "embed_texts_meta", _batch("real:a", 8))
    mid = memory.add_memory(bank["chat"], bank["char"], None, "episodic",
                            "witnessed", 0.6, "The route was fine.",
                            turn_idx=0)

    temp_db.qi("UPDATE memories SET embedding=? WHERE id=?", (b"other", mid))

    _integrity(temp_db, "memories_fts")
    rows = temp_db.q("SELECT rowid FROM memories_fts WHERE memories_fts "
                     "MATCH ?", ('"route"',))
    assert [r["rowid"] for r in rows] == [mid]


def test_an_existing_file_gets_the_narrowed_triggers_when_it_crosses_v39(
        temp_db):
    """A fresh file takes the narrowed definitions from SCHEMA; every file
    written before 2026-09-08 carries the wide ones, and `CREATE TRIGGER IF
    NOT EXISTS` in SCHEMA will not replace them. The v38 -> v39 migration is
    what does -- and it rebuilds neither index, because no file is carrying a
    duplicate to repair (see the migration's own note)."""
    for name, ddl in (
            ("memories_au", """CREATE TRIGGER memories_au
                AFTER UPDATE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, content)
                VALUES ('delete', old.id, old.content);
                INSERT INTO memories_fts(rowid, content)
                VALUES (new.id, new.content); END"""),
            ("lore_au", """CREATE TRIGGER lore_au
                AFTER UPDATE ON lore_entries BEGIN
                INSERT INTO lore_fts(lore_fts, rowid, content, keys)
                VALUES ('delete', old.id, old.content, old.keys);
                INSERT INTO lore_fts(rowid, content, keys)
                VALUES (new.id, new.content, new.keys); END""")):
        temp_db.qi(f"DROP TRIGGER {name}")
        temp_db.qi(ddl)
    temp_db.qi("INSERT OR REPLACE INTO schema_meta(key,value) "
               "VALUES('version','38')")
    temp_db.close_connection()

    temp_db.init()

    sql = {r["name"]: r["sql"] for r in temp_db.q(
        "SELECT name, sql FROM sqlite_master WHERE type='trigger' "
        "AND name IN ('memories_au','lore_au')")}
    assert "AFTER UPDATE OF content ON memories" in sql["memories_au"]
    assert "AFTER UPDATE OF content, keys ON lore_entries" in sql["lore_au"]


def test_a_lore_edit_keeps_its_index_consistent(temp_db):
    """The same rule on the other index, where nothing yet makes it a fault."""
    book = temp_db.qi(
        "INSERT INTO lorebooks(name,chat_id,book_type,summary) "
        "VALUES(?,?,?,?)", ("Canon", None, "general", ""))
    entry = memory.add_lore(book, "granary", "The granary is kept.",
                            turn_added=1)

    memory.update_lore(entry, "granary", "The granary is NOT kept.")

    _integrity(temp_db, "lore_fts")
    rows = temp_db.q("SELECT rowid FROM lore_fts WHERE lore_fts MATCH ?",
                     ('"granary"',))
    assert [r["rowid"] for r in rows] == [entry]
