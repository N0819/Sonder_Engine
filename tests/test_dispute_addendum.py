"""A re-reading is added to a memory, never written over the last one.

`record_dispute` states its own premise: the event stays exactly as it was.
Being deceived does not unmake what you saw. The READING was not held to that
rule -- a second re-reading replaced the first and only bumped a counter, so
the mechanism built to preserve a memory's history destroyed the history of
how that memory had been read.

A mind that read one moment three ways across two hundred beats has a shape,
and the shape is the interesting thing about it.

**And this is the watch.** Grounding was widened on 2026-08-20 so a dispute may
cite a later memory rather than only the present beat (UNBUILT 2.24) -- which
is how a mind revises when nothing new has happened, and is the commoner half
of how people actually do it. The risk that comes with it is RUMINATION: a mind
re-reading its past off its own memories, round and round, drifting from what
happened.

Nothing here forbids that, deliberately. A mind is allowed to keep thinking.
What these tests guarantee is that it cannot happen INVISIBLY: every superseded
reading is kept with the evidence that produced it, so eight readings of one
row citing one source is legible as a loop rather than as eight discoveries. A
counter alone cannot tell those apart, which is why the counter alone was not
enough.
"""

from __future__ import annotations

import json
import time

import pytest

from mind import memory


@pytest.fixture
def _row(temp_db):
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("T", "", time.time()))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        ("Mara", "{}", "{}", time.time()))
    mid = memory.add_memory(
        chat_id, char_id, None, "episodic", "witnessed", 0.5,
        "He carried my basket up the hill and would not take anything for it.",
        turn_idx=10)
    return chat_id, char_id, mid


def _blob(db, mid):
    row = db.q("SELECT disputed FROM memories WHERE id=?", (mid,), one=True)
    return json.loads(row["disputed"]) if row and row["disputed"] else {}


class TestTheTrailIsKept:
    def test_a_second_reading_does_not_erase_the_first(self, _row, temp_db):
        chat_id, char_id, mid = _row
        memory.record_dispute(chat_id, char_id, "carried my basket",
                              "he wanted me in his debt", 40,
                              sources=["event:aaa"])
        memory.record_dispute(chat_id, char_id, "carried my basket",
                              "he was being kind and I was wrong to doubt", 180,
                              sources=["event:bbb"])
        blob = _blob(temp_db, mid)
        assert blob["reading"].startswith("he was being kind"), "latest on top"
        readings = [h["reading"] for h in blob.get("history") or []]
        assert any(r.startswith("he wanted me in his debt") for r in readings), \
            "the superseded reading must survive"

    def test_the_latest_reading_stays_where_readers_expect_it(self, _row,
                                                              temp_db):
        """`memory_context` renders `i_now_read_this_differently` from the top
        level. The addendum must not move it, or every existing reader
        silently shows nothing."""
        chat_id, char_id, mid = _row
        memory.record_dispute(chat_id, char_id, "carried my basket",
                              "he wanted me in his debt", 40)
        blob = _blob(temp_db, mid)
        assert blob.get("reading")
        assert blob.get("turn_idx") == 40
        assert blob.get("count") == 1

    def test_each_reading_keeps_what_changed_it(self, _row, temp_db):
        """Without the source, a loop and a discovery look identical."""
        chat_id, char_id, mid = _row
        memory.record_dispute(chat_id, char_id, "carried my basket",
                              "a manoeuvre", 40, sources=["event:aaa"])
        memory.record_dispute(chat_id, char_id, "carried my basket",
                              "kindness after all", 90, sources=["event:bbb"])
        blob = _blob(temp_db, mid)
        assert blob["sources"] == ["event:bbb"]
        assert (blob["history"][0].get("sources") or []) == ["event:aaa"]

    def test_the_trail_is_bounded(self, _row, temp_db):
        """It rides every checkpoint and archive of the row, and a mind that
        has re-read one moment twelve times is not saying more with the
        twelfth."""
        chat_id, char_id, mid = _row
        for turn in range(1, 16):
            memory.record_dispute(chat_id, char_id, "carried my basket",
                                  "reading number %d" % turn, turn * 10,
                                  sources=["event:%d" % turn])
        blob = _blob(temp_db, mid)
        assert len(blob["history"]) <= memory._MAX_DISPUTE_HISTORY
        assert blob["count"] == 15, "the count still says how often, in full"


class TestRuminationIsVisible:
    """The failure mode the widened grounding could produce. Not forbidden --
    detectable."""

    def test_a_loop_on_one_source_is_distinguishable_from_discovery(
            self, _row, temp_db):
        chat_id, char_id, mid = _row
        for turn in (30, 60, 90, 120):
            memory.record_dispute(chat_id, char_id, "carried my basket",
                                  "he wanted me in his debt, I am sure of it",
                                  turn, sources=["event:same"])
        blob = _blob(temp_db, mid)
        seen = {tuple(h.get("sources") or []) for h in blob["history"]}
        seen.add(tuple(blob.get("sources") or []))
        assert seen == {("event:same",)}, (
            "four re-readings off one source is a loop, and the data says so")
        assert blob["count"] == 4

    def test_genuine_revision_shows_distinct_sources(self, _row, temp_db):
        chat_id, char_id, mid = _row
        for turn, src in ((30, "event:a"), (60, "event:b"), (90, "event:c")):
            memory.record_dispute(chat_id, char_id, "carried my basket",
                                  "reading at %d" % turn, turn, sources=[src])
        blob = _blob(temp_db, mid)
        seen = {tuple(h.get("sources") or []) for h in blob["history"]}
        seen.add(tuple(blob.get("sources") or []))
        assert len(seen) == 3, "three different reasons is not rumination"


class TestOldBlobsStillWork:
    def test_a_pre_addendum_dispute_reads_and_extends(self, _row, temp_db):
        """A row disputed before this existed carries a bare
        {turn_idx, reading, count}. It must parse, render, and gain a trail on
        its next re-reading rather than raising."""
        chat_id, char_id, mid = _row
        temp_db.qi("UPDATE memories SET disputed=? WHERE id=?",
                   (json.dumps({"turn_idx": 5, "reading": "an old reading",
                                "count": 1}), mid))
        assert memory._dispute_of(
            temp_db.q("SELECT disputed FROM memories WHERE id=?", (mid,),
                      one=True)["disputed"])
        memory.record_dispute(chat_id, char_id, "carried my basket",
                              "a newer reading", 50, sources=["event:new"])
        blob = _blob(temp_db, mid)
        assert blob["reading"] == "a newer reading"
        assert blob["count"] == 2
        assert any(h.get("reading") == "an old reading"
                   for h in blob["history"]), \
            "the pre-addendum reading must be carried forward, not dropped"


def test_background_tension_review_accepts_actual_database_rows(
        temp_db, monkeypatch):
    """The out-of-band worker passes q() rows, not hand-built dictionaries."""
    from mind import memory_judge

    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Tension", "", time.time()))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        ("Mara", "{}", "{}", time.time()))
    memory.add_memory(
        chat_id, char_id, None, "episodic", "remembered", 0.5,
        "The gate was open.", gist="open gate", turn_idx=0,
        event_key="event:gate")
    minted = temp_db.q(
        "SELECT event_key,gist,content,provenance,turn_idx FROM memories "
        "WHERE chat_id=? AND char_id=?", (chat_id, char_id))
    monkeypatch.setattr(
        memory_judge, "review_recall",
        lambda *a, **k: {"available": False, "tensions": []})

    assert memory_judge.review_minted_memories(
        chat_id, char_id, "Mara", minted, current_turn_idx=0) == 0
