"""Checkpoints store each embedding once, and never lose one doing it.

A checkpoint is a full pre-turn snapshot of the memory bank, and it used to
carry every memory's two float32 vectors inline -- so the same vector was
re-stored on every turn for the life of the story. Measured on a live database:
checkpoints were 94.5% of a 4.4 GB file, `memories` was 98.9% of each
checkpoint, and the vectors were 96.9% of that. One story held 40,224 memory
copies across 118 checkpoints and 529 distinct by content: a 76x duplication of
1.00 GB that needs 13 MB.

The conversion moves each vector into `memory_vectors` under its content
address (`sha1(char_id, normalised content)`) and leaves the checkpoint a
reference. Nothing is re-embedded -- a vector is a pure function of content, so
this changes where bytes live, not what they are.

**Loss is not accepted.** The work happens per story on a duplicate, and the
original is not touched until the duplicate has been proved equivalent. These
tests hold that guarantee, including the case where it has to refuse.
"""
from __future__ import annotations

import json
import time

import pytest

from persist import checkpoints
from mind import memory
from persist.checkpoints import (checkpoint_storage_status, compact_checkpoints,
                         ensure_checkpoint, restore_checkpoint,
                         start_compaction)
from persist.checkpoints import _verify_no_loss


def _story(temp_db, name, n=6):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     (name, "", time.time()))
    ch = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        (name + "-c", json.dumps({"identity": {"name": name}}), "{}", time.time()))
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status) VALUES(?,?,'active')",
               (cid, ch))
    temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
               (cid, 0, "", time.time()))
    for i in range(n):
        memory.add_memory(cid, ch, None, "episodic", "witnessed", 0.6,
                          "%s corridor %d" % (name, i), turn_idx=i)
    return cid, ch


def _make_legacy(temp_db, cid):
    """Rewrite this chat's checkpoints into the pre-compaction inline shape."""
    for r in temp_db.q("SELECT id, blob FROM checkpoints WHERE chat_id=?", (cid,)):
        blob = json.loads(r["blob"])
        for m in blob.get("memories") or []:
            row = temp_db.q("SELECT embedding, cue_embedding FROM memories "
                            "WHERE chat_id=? AND content=?",
                            (cid, m["content"]), one=True)
            if not row:
                continue
            m.pop("vkey", None)
            m["embedding"] = memory._blob_to_b64(row["embedding"])
            m["cue_embedding"] = memory._blob_to_b64(row["cue_embedding"])
        temp_db.qi("UPDATE checkpoints SET blob=? WHERE id=?",
                   (json.dumps(blob), r["id"]))
    temp_db.qi("DELETE FROM memory_vectors")


# --- the conversion itself -------------------------------------------------

def test_a_checkpoint_stops_carrying_vectors(temp_db):
    cid, _ = _story(temp_db, "Alpha")
    ensure_checkpoint(cid, 0)
    blob = json.loads(temp_db.q("SELECT blob FROM checkpoints WHERE chat_id=?",
                                (cid,), one=True)["blob"])
    entry = (blob.get("memories") or [{}])[0]
    assert entry.get("vkey"), "a fresh checkpoint references its vectors"
    assert "embedding" not in entry
    assert temp_db.q("SELECT COUNT(*) n FROM memory_vectors", one=True)["n"] == 6


def test_restoring_a_referenced_checkpoint_is_byte_identical(temp_db):
    """The only thing a checkpoint is for. Vectors included."""
    cid, ch = _story(temp_db, "Beta")
    memory.record_dispute(temp_db and cid, ch, "Beta corridor 2", "a mask", 4)
    before = {(r["char_id"], r["content"]): dict(r)
              for r in temp_db.q("SELECT * FROM memories WHERE chat_id=?", (cid,))}
    ensure_checkpoint(cid, 0)
    temp_db.qi("UPDATE memories SET embedding=NULL, cue_embedding=NULL, "
               "importance=NULL, disputed='' WHERE chat_id=?", (cid,))
    restore_checkpoint(cid, 0)
    after = {(r["char_id"], r["content"]): dict(r)
             for r in temp_db.q("SELECT * FROM memories WHERE chat_id=?", (cid,))}
    assert set(before) == set(after)
    for key, b in before.items():
        for field in ("embedding", "cue_embedding", "embedding_model",
                      "embedding_dim", "salience", "importance", "disputed",
                      "confidence", "turn_idx", "archived"):
            assert after[key][field] == b[field], field


def test_converting_a_legacy_checkpoint_shrinks_it(temp_db):
    cid, _ = _story(temp_db, "Gamma")
    ensure_checkpoint(cid, 0)
    _make_legacy(temp_db, cid)
    rep = compact_checkpoints(dry_run=False)
    assert rep["rewritten"] == 1
    assert rep["bytes_after"] < rep["bytes_before"] / 2
    assert checkpoint_storage_status()["legacy"] == 0


def test_conversion_is_resumable(temp_db):
    """An already-converted checkpoint has nothing left to move."""
    cid, _ = _story(temp_db, "Delta")
    ensure_checkpoint(cid, 0)
    _make_legacy(temp_db, cid)
    compact_checkpoints(dry_run=False)
    again = compact_checkpoints(dry_run=False)
    assert again["rewritten"] == 0 and again["skipped"] == []


def test_dry_run_writes_nothing(temp_db):
    cid, _ = _story(temp_db, "Epsilon")
    ensure_checkpoint(cid, 0)
    _make_legacy(temp_db, cid)
    before = temp_db.q("SELECT blob FROM checkpoints WHERE chat_id=?", (cid,),
                       one=True)["blob"]
    rep = compact_checkpoints()          # dry_run defaults True
    assert rep["dry_run"] and rep["rewritten"] == 1
    assert temp_db.q("SELECT blob FROM checkpoints WHERE chat_id=?", (cid,),
                     one=True)["blob"] == before
    assert temp_db.q("SELECT COUNT(*) n FROM memory_vectors", one=True)["n"] == 0


# --- loss is refused, per story --------------------------------------------

def _corrupt_candidate_for(monkeypatch, chat_name):
    """Make the compacted candidate for one story silently wrong.

    The verifier's job is to catch a candidate that does not restore to its
    original, whatever produced it. Injecting the fault at the candidate --
    rather than in the stored data -- tests the refusal machinery without
    depending on any particular way of being wrong, which matters because the
    ORIGINAL way (two memories sharing content but not vectors) is now handled
    rather than refused: addresses are the vector's own bytes.
    """
    from persist import checkpoints as C
    real = C._candidate_blob

    def fake(blob):
        candidate, pending, moved = real(blob)
        mems = candidate.get("memories") or []
        if moved and mems and blob.get("_story") == chat_name:
            mems[0]["salience"] = 0.123456          # a value the original lacks
        return candidate, pending, moved

    monkeypatch.setattr(C, "_candidate_blob", fake)


def test_a_story_that_cannot_be_proved_lossless_is_left_alone(temp_db, monkeypatch):
    """The story is named, its originals stand byte-identical, and the stories
    either side of it still convert."""
    good1, _ = _story(temp_db, "Good One")
    bad, _ = _story(temp_db, "Bad Story")
    good2, _ = _story(temp_db, "Good Two")
    for cid in (good1, bad, good2):
        ensure_checkpoint(cid, 0)
        _make_legacy(temp_db, cid)
    # Tag the bad story's blob so the injected fault lands only on it.
    for r in temp_db.q("SELECT id, blob FROM checkpoints WHERE chat_id=?", (bad,)):
        blob = json.loads(r["blob"]); blob["_story"] = "Bad Story"
        temp_db.qi("UPDATE checkpoints SET blob=? WHERE id=?",
                   (json.dumps(blob), r["id"]))
    _corrupt_candidate_for(monkeypatch, "Bad Story")

    before = {x["id"]: x["blob"] for x in temp_db.q("SELECT id, blob FROM checkpoints")}
    rep = compact_checkpoints(dry_run=False)
    after = {x["id"]: x["blob"] for x in temp_db.q("SELECT id, blob FROM checkpoints")}

    assert [s["name"] for s in rep["skipped"]] == ["Bad Story"]
    assert "salience changed" in rep["skipped"][0]["reason"]
    # And named ONCE. A report field that is initialized and never assigned
    # reads as "no failure" on exactly the run that had one.
    assert "error" not in rep
    bad_ids = {x["id"] for x in temp_db.q(
        "SELECT id FROM checkpoints WHERE chat_id=?", (bad,))}
    assert all(before[i] == after[i] for i in bad_ids), "the original must be untouched"
    ok_ids = {x["id"] for x in temp_db.q(
        "SELECT id FROM checkpoints WHERE chat_id IN (?,?)", (good1, good2))}
    assert all(before[i] != after[i] for i in ok_ids), "other stories still convert"


def test_a_refused_story_leaves_no_vectors_behind(temp_db, monkeypatch):
    """Vectors are written in the same transaction as the blobs, so a story
    that fails verification contributes nothing at all."""
    bad, _ = _story(temp_db, "Only Bad", n=5)
    ensure_checkpoint(bad, 0)
    _make_legacy(temp_db, bad)
    for r in temp_db.q("SELECT id, blob FROM checkpoints"):
        blob = json.loads(r["blob"]); blob["_story"] = "Only Bad"
        temp_db.qi("UPDATE checkpoints SET blob=? WHERE id=?",
                   (json.dumps(blob), r["id"]))
    _corrupt_candidate_for(monkeypatch, "Only Bad")
    compact_checkpoints(dry_run=False)
    assert temp_db.q("SELECT COUNT(*) n FROM memory_vectors", one=True)["n"] == 0


def test_two_memories_with_one_content_and_two_vectors_now_convert(temp_db):
    """The production failure that forced byte-addressing.

    Chat 36 held "You are in Ten Forward." at turn 42 and again at turn 44 --
    same character, same content, different embedding payloads, because a
    vector is built from `_memory_document` (which folds in turn, location,
    category, key phrases) and not from content alone. Addressing on
    `(char_id, content)` collapsed the two, the verifier refused the story, and
    the four largest stories in the database went unconverted.
    """
    cid, ch = _story(temp_db, "Ten Forward", n=4)
    ensure_checkpoint(cid, 0)
    _make_legacy(temp_db, cid)
    r = temp_db.q("SELECT id, blob FROM checkpoints WHERE chat_id=?", (cid,), one=True)
    blob = json.loads(r["blob"])
    a, b = blob["memories"][0], blob["memories"][1]
    b["content"] = a["content"]                     # same content...
    assert b["embedding"] != a["embedding"]         # ...different vectors
    temp_db.qi("UPDATE checkpoints SET blob=? WHERE id=?",
               (json.dumps(blob), r["id"]))

    rep = compact_checkpoints(dry_run=False)
    assert rep["skipped"] == [], rep["skipped"]
    assert rep["rewritten"] == 1
    stored = json.loads(temp_db.q("SELECT blob FROM checkpoints WHERE id=?",
                                  (r["id"],), one=True)["blob"])["memories"]
    assert stored[0]["vkey"] != stored[1]["vkey"], "distinct vectors need distinct addresses"


def test_an_unreadable_checkpoint_is_left_exactly_as_it_is(temp_db):
    cid, _ = _story(temp_db, "Zeta")
    ensure_checkpoint(cid, 0)
    temp_db.qi("UPDATE checkpoints SET blob='{not json' WHERE chat_id=?", (cid,))
    compact_checkpoints(dry_run=False)
    assert temp_db.q("SELECT blob FROM checkpoints WHERE chat_id=?", (cid,),
                     one=True)["blob"] == "{not json"


# --- the verifier, directly ------------------------------------------------

def _vec(fill):
    """A real float32 blob. A hand-written base64 string will not do: it has to
    decode to a whole number of float32s or `_b64_to_blob` rejects it, and the
    verifier then reads the entry as having had no vectors to move -- which is
    how the first draft of these tests passed for the wrong reason."""
    import numpy as np
    return memory._blob(np.full(4, fill, dtype=np.float32))


def _pair():
    full, cue = _vec(1.0), _vec(2.0)
    original = {"memories": [{"char_id": 1, "content": "a", "salience": 0.5,
                              "embedding": memory._blob_to_b64(full),
                              "cue_embedding": memory._blob_to_b64(cue)}],
                "world": {"k": 1}}
    candidate = {"memories": [{"char_id": 1, "content": "a", "salience": 0.5,
                               "vkey": "1:abc"}],
                 "world": {"k": 1}}
    vectors = {"1:abc": (full, cue)}
    return original, candidate, vectors


def test_the_verifier_accepts_an_equivalent_candidate():
    assert _verify_no_loss(*_pair()) is None


@pytest.mark.parametrize("break_it,expect", [
    (lambda o, c, v: c["memories"].pop(), "memory count"),
    (lambda o, c, v: c["memories"][0].update(salience=0.9), "salience changed"),
    (lambda o, c, v: c.update(world={"k": 2}), "world changed"),
    (lambda o, c, v: c.update(extra=1), "top-level keys differ"),
    (lambda o, c, v: v.clear(), "not stored"),
    (lambda o, c, v: c["memories"][0].pop("vkey"), "lost its vectors"),
])
def test_the_verifier_catches_every_way_a_memory_could_change(break_it, expect):
    original, candidate, vectors = _pair()
    break_it(original, candidate, vectors)
    reason = _verify_no_loss(original, candidate, vectors)
    assert reason and expect in reason, reason


def test_the_verifier_catches_a_reference_to_different_bytes():
    original, candidate, vectors = _pair()
    vectors["1:abc"] = (_vec(9.0), _vec(2.0))
    reason = _verify_no_loss(original, candidate, vectors)
    assert "different vector bytes" in reason


# --- it refuses to run when there is nothing to do -------------------------

def test_it_refuses_on_an_empty_database(temp_db):
    r = start_compaction()
    assert r["started"] is False and r["reason"] == "no checkpoints stored"


def test_it_refuses_when_everything_is_already_converted(temp_db):
    cid, _ = _story(temp_db, "Eta")
    ensure_checkpoint(cid, 0)
    r = start_compaction()
    assert r["started"] is False and r["reason"] == "nothing to convert"


def test_it_becomes_available_again_when_legacy_data_arrives(temp_db):
    """The only thing that should re-enable it."""
    cid, _ = _story(temp_db, "Theta")
    ensure_checkpoint(cid, 0)
    assert start_compaction()["started"] is False
    _make_legacy(temp_db, cid)
    assert checkpoint_storage_status()["legacy"] == 1
    r = start_compaction()
    assert r["started"] is True
    # Started a thread; let it settle so it cannot bleed into another test.
    for _ in range(100):
        if not checkpoints.compaction_progress()["running"]:
            break
        time.sleep(0.05)


# --- the panel and the mover have to be asking the same question -----------

def _rewrite_first_checkpoint(temp_db, cid, mutate):
    row = temp_db.q("SELECT id, blob FROM checkpoints WHERE chat_id=?",
                    (cid,), one=True)
    blob = json.loads(row["blob"])
    mutate(blob)
    temp_db.qi("UPDATE checkpoints SET blob=? WHERE id=?",
               (json.dumps(blob), row["id"]))


def test_inline_vectors_past_the_first_entry_are_still_counted(temp_db):
    """A probe of entry zero answers about entry zero.

    The checkpoint's memories are ordered by turn, not by storage format, so
    "does this checkpoint still carry payload" is a question about all of
    them. Reported done, the panel offers no conversion and the inline
    vectors stand -- which on the corpus this module exists for is the whole
    reason it exists.
    """
    cid, _ = _story(temp_db, "Iota")
    ensure_checkpoint(cid, 0)
    _make_legacy(temp_db, cid)

    def only_the_first_is_compacted(blob):
        first = blob["memories"][0]
        first.pop("embedding", None)
        first.pop("cue_embedding", None)
        first["vkey"] = "vec_already_moved"

    _rewrite_first_checkpoint(temp_db, cid, only_the_first_is_compacted)

    assert checkpoint_storage_status()["legacy"] == 1


def test_a_checkpoint_the_mover_would_skip_is_not_reported_as_legacy(temp_db):
    """The panel must not promise work compaction will never do.

    `_candidate_blob` moves an entry only when BOTH vectors decode -- the
    store is addressed by the pair, so half of one has no address. Counting
    it legacy leaves the panel reporting the same outstanding bytes after
    every completed run, for a checkpoint no run will ever touch.
    """
    cid, _ = _story(temp_db, "Kappa")
    ensure_checkpoint(cid, 0)
    _make_legacy(temp_db, cid)

    def drop_every_cue(blob):
        for m in blob["memories"]:
            m.pop("cue_embedding", None)

    _rewrite_first_checkpoint(temp_db, cid, drop_every_cue)

    status = checkpoint_storage_status()
    rep = compact_checkpoints(dry_run=False)
    assert rep["rewritten"] == 0
    assert status["legacy"] == 0
