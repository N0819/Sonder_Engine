"""Review 2026-09-07 C2: a checkpoint stops re-deriving what it already has,
and says exactly the same thing while it does.

Two mechanisms land here, and both can be WRONG rather than merely slow, which
is why they are tested rather than measured:

* `snapshot_blob` splices each world row's stored JSON text into the
  checkpoint document instead of parsing it into Python and re-emitting it
  (41 MB of charters on the owner's live chat 114, parsed and re-serialised
  twice a beat). The test that matters is that the document is the same one.
* `memories.vkey` (schema v38) carries the content address of a memory's two
  vector blobs, so the dump reads the address instead of reading 20 KB per row
  to hash it. A derived column can go STALE, and a stale vector address is not
  a slow answer but a wrong one -- the checkpoint would file the memory by
  reference to bytes that are no longer its own. The `memories_vkey_stale`
  trigger is the floor under that, and the invalidation is what these tests
  are for.
"""
import json
import time

import pytest

from core.db import q, qi
from mind.memory import add_memory, dump_chat_memories, vector_address
from persist.checkpoints import (ensure_checkpoint, refresh_checkpoint,
                                 snapshot_blob, snapshot_state)


def _story(temp_db, name="Snapshot", memories=3):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     (name, "", time.time()))
    ch = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (name, json.dumps({"identity": {"name": name}}), "{}", time.time(),
         "uid-" + name))
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status) "
               "VALUES(?,?,'active')", (cid, ch))
    for i in range(memories):
        add_memory(cid, ch, None, "episodic", "witnessed", 0.6,
                   "%s remembers corridor %d" % (name, i), turn_idx=i)
    return cid, ch


class TestTheBlobIsTheSameDocument:
    def test_spliced_world_text_matches_the_parsed_and_re_emitted_one(
            self, temp_db):
        cid, _ = _story(temp_db)
        # The awkward shapes a world row actually holds: nesting, non-ASCII,
        # floats, an empty container, a value that is not an object at all.
        from core.db import wset
        wset(cid, "scene", {"rooms": {"kitchen": {"props": ["匠", "pan"]}},
                            "clock": 1.5, "empty": {}})
        wset(cid, "charters", {"items": {"inn": {"level": 0.5713908242222245}}})
        wset(cid, "planning_needs", [])
        wset(cid, "room_status", "open")

        text = snapshot_blob(cid)
        assert text == json.dumps(snapshot_state(cid))
        assert json.loads(text)["world"]["scene"]["rooms"]["kitchen"]["props"] \
            == ["匠", "pan"]

    def test_a_world_row_holding_nothing_fails_here_not_at_restore(
            self, temp_db):
        cid, _ = _story(temp_db, memories=1)
        qi("INSERT INTO world(chat_id,key,value) VALUES(?,?,?)",
           (cid, "hand_edited", ""))
        with pytest.raises(ValueError):
            snapshot_blob(cid)

    def test_a_world_row_that_is_not_json_fails_here_not_at_restore(
            self, temp_db):
        """The row the blank test does not cover: non-blank text that is not
        JSON. Splicing it verbatim would write a checkpoint nothing can read
        back, so it has to stop the turn exactly where the parse it replaces
        did -- and no checkpoint row may survive the attempt."""
        cid, _ = _story(temp_db, memories=1)
        qi("INSERT INTO world(chat_id,key,value) VALUES(?,?,?)",
           (cid, "hand_edited", "not json at all"))
        with pytest.raises(ValueError):
            snapshot_blob(cid)
        with pytest.raises(ValueError):
            ensure_checkpoint(cid, 0)
        assert q("SELECT id FROM checkpoints WHERE chat_id=?", (cid,),
                 one=True) is None

    def test_a_row_python_can_parse_but_sqlite_cannot_is_still_spliced(
            self, temp_db):
        """`json.dumps` emits `Infinity` for a float the story computed, and
        `json_valid` calls that text invalid while `json.loads` reads it back.
        The validity check must not turn a row the old code round-tripped into
        a stopped turn, so a row SQLite rejects is parsed before it is judged.
        """
        cid, _ = _story(temp_db, memories=1)
        qi("INSERT INTO world(chat_id,key,value) VALUES(?,?,?)",
           (cid, "odd_float", json.dumps({"reach": float("inf")})))
        text = snapshot_blob(cid)
        assert text == json.dumps(snapshot_state(cid))
        assert json.loads(text)["world"]["odd_float"]["reach"] == float("inf")

    def test_a_chat_with_no_world_rows_still_produces_valid_json(self, temp_db):
        cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Bare", "", time.time()))
        text = snapshot_blob(cid)
        assert json.loads(text)["world"] == {}
        assert text == json.dumps(snapshot_state(cid))

    def test_the_checkpoint_row_holds_that_document(self, temp_db):
        cid, _ = _story(temp_db)
        ensure_checkpoint(cid, 0)
        row = q("SELECT blob FROM checkpoints WHERE chat_id=? AND turn_idx=0",
                (cid,), one=True)
        assert row["blob"] == json.dumps(snapshot_state(cid))


class TestTheAddressIsFiledWithTheBytes:
    def test_a_minted_memory_carries_its_vector_address(self, temp_db):
        cid, _ = _story(temp_db, memories=1)
        row = q("SELECT vkey, embedding, cue_embedding FROM memories "
                "WHERE chat_id=?", (cid,), one=True)
        assert row["vkey"] == vector_address(row["embedding"],
                                             row["cue_embedding"])

    def test_the_dump_reads_the_column_and_the_blobs_agree(self, temp_db):
        cid, _ = _story(temp_db, memories=4)
        dumped = {m["content"]: m["vkey"]
                  for m in dump_chat_memories(cid, inline_vectors=False)}
        for r in q("SELECT content, embedding, cue_embedding FROM memories "
                   "WHERE chat_id=?", (cid,)):
            assert dumped[r["content"]] == vector_address(r["embedding"],
                                                          r["cue_embedding"])

    def test_an_unstamped_row_dumps_the_same_address(self, temp_db):
        """The fallback IS the old behaviour: a bank written before v38, or a
        row whose stamp was cleared, must dump the address it always did."""
        cid, _ = _story(temp_db, memories=3)
        stamped = dump_chat_memories(cid, inline_vectors=False)
        qi("UPDATE memories SET vkey=NULL WHERE chat_id=?", (cid,))
        assert dump_chat_memories(cid, inline_vectors=False) == stamped

    def test_a_row_stamped_between_the_read_and_the_fallback_keeps_its_address(
            self, temp_db, monkeypatch):
        """The fallback is addressed by the ids that came back unstamped, not
        by re-filtering on the predicate (second C2 skeptic, 2026-09-08):
        `_upsert_memory`'s INSERT and its stamp are two statements, so the
        out-of-band consolidation job publishes a NULL-vkey row for a moment,
        and a row stamped between the checkpoint's read and its fallback query
        matched neither and fell out of the map -- `KeyError` out of
        `dump_chat_memories` in the middle of `turn_new`. The stamp is landed
        from inside the dump's own first query, which is the window.
        """
        from mind import memory_snapshot

        cid, _ = _story(temp_db, memories=3)
        qi("UPDATE memories SET vkey=NULL WHERE chat_id=?", (cid,))
        victim = q("SELECT id, content, embedding, cue_embedding FROM memories "
                   "WHERE chat_id=?", (cid,), one=True)
        address = vector_address(victim["embedding"], victim["cue_embedding"])
        real_q, landed = memory_snapshot.q, []

        def q_then_stamp(sql, *a, **k):
            rows = real_q(sql, *a, **k)
            if not landed and "FROM memories" in sql:
                landed.append(True)
                qi("UPDATE memories SET vkey=? WHERE id=?", (address, victim["id"]))
            return rows
        monkeypatch.setattr(memory_snapshot, "q", q_then_stamp)

        dumped = {m["content"]: m["vkey"]
                  for m in dump_chat_memories(cid, inline_vectors=False)}
        assert landed, "the stamp never landed inside the window"
        assert set(dumped) == {r["content"] for r in q(
            "SELECT content FROM memories WHERE chat_id=?", (cid,))}
        assert dumped[victim["content"]] == address

    def test_a_row_with_no_vectors_at_all_dumps_what_it_always_did(self, temp_db):
        cid, _ = _story(temp_db, memories=1)
        qi("UPDATE memories SET embedding=NULL, cue_embedding=NULL "
           "WHERE chat_id=?", (cid,))
        dumped = dump_chat_memories(cid, inline_vectors=False)
        assert dumped[0]["vkey"] == vector_address(None, None)

    def test_the_archive_dump_still_carries_the_blobs(self, temp_db):
        cid, _ = _story(temp_db, memories=2)
        for m in dump_chat_memories(cid, inline_vectors=True):
            assert m["embedding"] and m["cue_embedding"]
            assert "vkey" not in m


class TestAStaleAddressCannotSurvive:
    def test_rewriting_the_vectors_without_restamping_clears_the_address(
            self, temp_db):
        cid, _ = _story(temp_db, memories=1)
        mid = q("SELECT id FROM memories WHERE chat_id=?", (cid,), one=True)["id"]
        qi("UPDATE memories SET embedding=?, cue_embedding=? WHERE id=?",
           (b"\x01" * 16, b"\x02" * 16, mid))
        assert q("SELECT vkey FROM memories WHERE id=?", (mid,),
                 one=True)["vkey"] is None
        dumped = dump_chat_memories(cid, inline_vectors=False)
        assert dumped[0]["vkey"] == vector_address(b"\x01" * 16, b"\x02" * 16)

    def test_restamping_in_the_same_write_keeps_the_address(self, temp_db):
        cid, _ = _story(temp_db, memories=1)
        mid = q("SELECT id FROM memories WHERE chat_id=?", (cid,), one=True)["id"]
        fresh = vector_address(b"\x03" * 16, b"\x04" * 16)
        qi("UPDATE memories SET embedding=?, cue_embedding=?, vkey=? WHERE id=?",
           (b"\x03" * 16, b"\x04" * 16, fresh, mid))
        assert q("SELECT vkey FROM memories WHERE id=?", (mid,),
                 one=True)["vkey"] == fresh

    def test_a_write_that_leaves_the_vectors_alone_keeps_the_address(
            self, temp_db):
        cid, _ = _story(temp_db, memories=1)
        row = q("SELECT id, vkey, embedding, cue_embedding FROM memories "
                "WHERE chat_id=?", (cid,), one=True)
        qi("UPDATE memories SET salience=0.9, embedding=?, cue_embedding=? "
           "WHERE id=?", (row["embedding"], row["cue_embedding"], row["id"]))
        assert q("SELECT vkey FROM memories WHERE id=?", (row["id"],),
                 one=True)["vkey"] == row["vkey"]

    def test_the_engines_own_rewrite_path_restamps(self, temp_db):
        """`file_memory_vector(memory_id=...)` is the one seam every writer
        that touches the blobs goes through, so the stamp follows the bytes."""
        from mind.memory import file_memory_vector

        cid, _ = _story(temp_db, memories=1)
        mid = q("SELECT id FROM memories WHERE chat_id=?", (cid,), one=True)["id"]
        full, cue = b"\x05" * 16, b"\x06" * 16
        qi("UPDATE memories SET embedding=?, cue_embedding=? WHERE id=?",
           (full, cue, mid))
        file_memory_vector(full, cue, "test:model", 4, memory_id=mid)
        assert q("SELECT vkey FROM memories WHERE id=?", (mid,),
                 one=True)["vkey"] == vector_address(full, cue)
        assert q("SELECT 1 FROM memory_vectors WHERE vkey=?",
                 (vector_address(full, cue),), one=True)


class TestRefreshTouchesOnlyTheBooks:
    def test_a_refresh_rewrites_the_book_sections_and_nothing_else(
            self, temp_db):
        from core.db import wset

        cid, ch = _story(temp_db, memories=2)
        wset(cid, "scene", {"rooms": {"hall": {}}})
        ensure_checkpoint(cid, 0)
        before = json.loads(q("SELECT blob FROM checkpoints WHERE chat_id=? "
                              "AND turn_idx=0", (cid,), one=True)["blob"])
        # State that a refresh must NOT pick up: the checkpoint is a PRE-turn
        # snapshot, so a later world write belongs to no checkpoint yet.
        wset(cid, "scene", {"rooms": {"hall": {}, "cellar": {}}})
        add_memory(cid, ch, None, "episodic", "witnessed", 0.5,
                   "after the checkpoint", turn_idx=9)
        refresh_checkpoint(cid, 0)
        after = json.loads(q("SELECT blob FROM checkpoints WHERE chat_id=? "
                             "AND turn_idx=0", (cid,), one=True)["blob"])
        assert after["world"] == before["world"]
        assert after["memories"] == before["memories"]
        for key in ("lore", "lorebooks", "lorebook_links", "lore_overlays"):
            assert after[key] == snapshot_state(cid)[key]

    def test_a_refresh_with_no_checkpoint_writes_the_whole_snapshot(
            self, temp_db):
        cid, _ = _story(temp_db, memories=2)
        refresh_checkpoint(cid, 3)
        row = q("SELECT blob FROM checkpoints WHERE chat_id=? AND turn_idx=3",
                (cid,), one=True)
        assert row is not None
        assert json.loads(row["blob"]) == snapshot_state(cid)


class TestTheMigrationStampsAnExistingBank:
    def test_a_file_crossing_v38_gets_every_address_filed(self, temp_db):
        from mind.memory import backfill_memory_vectors

        cid, _ = _story(temp_db, memories=3)
        qi("UPDATE memories SET vkey=NULL WHERE chat_id=?", (cid,))
        qi("DELETE FROM memory_vectors")
        from core import db
        filed = backfill_memory_vectors(db.conn())
        assert filed >= 3
        rows = q("SELECT vkey, embedding, cue_embedding FROM memories "
                 "WHERE chat_id=?", (cid,))
        for r in rows:
            assert r["vkey"] == vector_address(r["embedding"], r["cue_embedding"])
            assert q("SELECT 1 FROM memory_vectors WHERE vkey=?",
                     (r["vkey"],), one=True)
