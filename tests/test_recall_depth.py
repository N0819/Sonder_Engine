"""How far back a mind reached, recorded at the moment it reached.

`last_accessed` is a wall clock. It answers "when did somebody's computer touch
this row" and cannot answer the question that decides how much memory is worth
delivering at all: **how far back did the character reach?** A row recalled
while it was fresh and a row recalled three hundred beats later are
indistinguishable afterwards, because the only thing stored was a timestamp.

That gap is why "does more recall keep being useful" had to be bought with
synthetic benchmarks -- nine cases and hours of character calls -- when
ordinary play is generating the evidence continuously and discarding it. With
the turn recorded, depth is `last_accessed_turn - turn_idx` and the question
becomes a query.

Deliberately NOT backfilled from `last_accessed` in the migration: there is no
sound mapping from a wall clock to a turn index, and this column exists to
answer a measurement question. Inventing its first month would poison the
answer it was added to give.
"""

from __future__ import annotations

import time

import pytest

from mind import memory


@pytest.fixture
def _bank(temp_db):
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("T", "", time.time()))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        ("Mara", "{}", "{}", time.time()))
    for i in range(12):
        memory.add_memory(chat_id, char_id, None, "episodic", "witnessed", 0.5,
                          f"The lantern on the {i}th night by the harbour wall.",
                          turn_idx=i)
    return chat_id, char_id


def _turns(db, chat_id, char_id):
    return {r["turn_idx"]: r["last_accessed_turn"] for r in db.q(
        "SELECT turn_idx, last_accessed_turn FROM memories "
        "WHERE chat_id=? AND char_id=?", (chat_id, char_id))}


class TestTheTurnIsRecorded:
    def test_a_recall_stamps_the_turn_it_happened_on(self, _bank, temp_db):
        chat_id, char_id = _bank
        memory.search_memories(chat_id, char_id, "the lantern", k=4,
                               current_turn_idx=200, viewer_frame_id=None,
                               record_access=True)
        stamped = [v for v in _turns(temp_db, chat_id, char_id).values()
                   if v is not None]
        assert stamped, "a recall during play must record its turn"
        assert set(stamped) == {200}

    def test_depth_is_the_difference_and_it_is_now_computable(self, _bank,
                                                              temp_db):
        """The whole point: a row formed at turn 3 and reached at turn 200 is
        a reach of 197 beats, and nothing could say so before."""
        chat_id, char_id = _bank
        memory.search_memories(chat_id, char_id, "the lantern", k=4,
                               current_turn_idx=200, viewer_frame_id=None,
                               record_access=True)
        depths = [r["last_accessed_turn"] - r["turn_idx"] for r in temp_db.q(
            "SELECT turn_idx, last_accessed_turn FROM memories "
            "WHERE chat_id=? AND char_id=? AND last_accessed_turn IS NOT NULL",
            (chat_id, char_id))]
        assert depths and all(d > 0 for d in depths)
        assert max(depths) >= 188  # the oldest row in the bank is turn 0..11

    def test_not_recording_leaves_it_untouched(self, _bank, temp_db):
        """`record_access=False` is how every tool and preview reads a bank.
        None of them are a mind recalling, and none may claim to be."""
        chat_id, char_id = _bank
        memory.search_memories(chat_id, char_id, "the lantern", k=4,
                               current_turn_idx=200, viewer_frame_id=None,
                               record_access=False)
        assert all(v is None for v in _turns(temp_db, chat_id, char_id).values())

    def test_a_turnless_caller_does_not_erase_a_recorded_turn(self, _bank,
                                                              temp_db):
        """A preview endpoint has no turn. It must not overwrite a real
        recorded reach with NULL -- that would silently delete measurement
        every time somebody opened a panel."""
        chat_id, char_id = _bank
        memory.search_memories(chat_id, char_id, "the lantern", k=4,
                               current_turn_idx=200, viewer_frame_id=None,
                               record_access=True)
        memory.search_memories(chat_id, char_id, "the lantern", k=4,
                               current_turn_idx=None, viewer_frame_id=None,
                               record_access=True)
        stamped = [v for v in _turns(temp_db, chat_id, char_id).values()
                   if v is not None]
        assert stamped and set(stamped) == {200}

    def test_a_later_reach_replaces_an_earlier_one(self, _bank, temp_db):
        chat_id, char_id = _bank
        for turn in (50, 300):
            memory.search_memories(chat_id, char_id, "the lantern", k=4,
                                   current_turn_idx=turn, viewer_frame_id=None,
                                   record_access=True)
        stamped = [v for v in _turns(temp_db, chat_id, char_id).values()
                   if v is not None]
        assert 300 in stamped


class TestItSurvivesACheckpoint:
    def test_the_turn_round_trips_through_dump_and_restore(self, _bank,
                                                           temp_db):
        """A rollback that reset this would silently destroy the one record of
        how deep this mind has ever reached -- the same argument access_count
        and last_accessed are already carried on."""
        chat_id, char_id = _bank
        memory.search_memories(chat_id, char_id, "the lantern", k=4,
                               current_turn_idx=200, viewer_frame_id=None,
                               record_access=True)
        dumped = memory.dump_chat_memories(chat_id)
        assert any(m.get("last_accessed_turn") == 200 for m in dumped)
        memory.restore_chat_memories(chat_id, dumped)
        stamped = [v for v in _turns(temp_db, chat_id, char_id).values()
                   if v is not None]
        assert stamped and set(stamped) == {200}

    def test_a_pre_v32_checkpoint_restores_without_a_turn(self, _bank,
                                                          temp_db):
        """An older checkpoint's retrieval history is a two-tuple. Its rows
        have no recorded turn, which is the truthful state -- not a zero, and
        not a crash."""
        chat_id, char_id = _bank
        memory.search_memories(chat_id, char_id, "the lantern", k=4,
                               current_turn_idx=200, viewer_frame_id=None,
                               record_access=True)
        dumped = memory.dump_chat_memories(chat_id)
        for m in dumped:
            m.pop("last_accessed_turn", None)
        memory.restore_chat_memories(chat_id, dumped)
        assert all(v is None for v in _turns(temp_db, chat_id, char_id).values())
