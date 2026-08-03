"""Two things a memory row could not say, and one a character could not.

**How central it BECAME.** `salience` is set at mint by a length term and a
fifteen-word keyword list, is never revised, and then governs ranking,
archiving and unbidden recall for the life of the story. That is a fine
encoding-time estimate and a poor permanent answer: an apparently minor moment
routinely turns out to have been the important one. `importance` records the
second fact without disturbing the first.

**That the character now reads it differently.** `reconcile_inference_confidence`
moves what a mind CONCLUDED. But this engine exists so a character can be
deceived -- and when they learn the face was a disguise, the memory of seeing
it stays true while its meaning does not. A dispute is recorded beside the
memory, never over it.

**Which spoken lines this particular mind keeps.** Durable dialogue was a fixed
phrase list, which is why the live corpus holds 15 dialogue rows against 2,028
episodes. The character now says, so one mind keeps an insult another shrugs
off.
"""
from __future__ import annotations

import json
import time

import pytest

import memory
from memory import (
    _IMPORTANCE_CEILING,
    add_memory,
    effective_importance,
    list_memories,
    raise_importance,
    record_dispute,
    search_memories,
)


def _fixture(temp_db):
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("T", "", time.time()))
    mine = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        ("Mara", "{}", "{}", time.time()))
    theirs = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        ("Bram", "{}", "{}", time.time()))
    return chat_id, mine, theirs


def _row(temp_db, mid):
    return temp_db.q("SELECT * FROM memories WHERE id=?", (mid,), one=True)


# --- importance defaults to salience, so an untouched bank is unchanged ----

def test_a_new_memory_has_no_revised_importance(temp_db):
    chat_id, mine, _ = _fixture(temp_db)
    mid = add_memory(chat_id, mine, None, "episodic", "witnessed", 0.61,
                     "the lantern guttered", turn_idx=1)
    assert _row(temp_db, mid)["importance"] is None
    got = list_memories(chat_id, mine, viewer_frame_id=None)[0]
    assert got["importance"] == pytest.approx(0.61)
    assert got["importance_revised"] is False


def test_effective_importance_falls_back_to_salience():
    assert effective_importance({"salience": 0.4, "importance": None}) == pytest.approx(0.4)
    assert effective_importance({"salience": 0.4, "importance": 0.9}) == pytest.approx(0.9)


# --- consequences raise it, and cannot run away ---------------------------

def test_a_consequence_raises_importance_without_touching_salience(temp_db):
    chat_id, mine, _ = _fixture(temp_db)
    mid = add_memory(chat_id, mine, None, "episodic", "witnessed", 0.5,
                     "the lantern guttered", turn_idx=1)
    raise_importance(chat_id, mine, [mid])
    row = _row(temp_db, mid)
    assert row["salience"] == pytest.approx(0.5), "salience records the past"
    assert row["importance"] > 0.5


def test_importance_is_asymptotic_and_never_exceeds_the_ceiling(temp_db):
    chat_id, mine, _ = _fixture(temp_db)
    mid = add_memory(chat_id, mine, None, "episodic", "witnessed", 0.5,
                     "the lantern guttered", turn_idx=1)
    seen = []
    for _ in range(60):
        raise_importance(chat_id, mine, [mid])
        seen.append(_row(temp_db, mid)["importance"])
    assert seen == sorted(seen), "importance never falls"
    assert seen[-1] <= _IMPORTANCE_CEILING
    # Each step closes a fraction of what remains, so the steps shrink.
    assert (seen[1] - seen[0]) > (seen[-1] - seen[-2])


def test_only_unrevised_bumps_exactly_once(temp_db):
    """Citation is downstream of retrieval, so it could compound into a
    popularity loop. The loop is closed structurally rather than hoped away."""
    chat_id, mine, _ = _fixture(temp_db)
    mid = add_memory(chat_id, mine, None, "episodic", "witnessed", 0.5,
                     "the lantern guttered", turn_idx=1)
    raise_importance(chat_id, mine, [mid], only_unrevised=True)
    once = _row(temp_db, mid)["importance"]
    for _ in range(10):
        raise_importance(chat_id, mine, [mid], only_unrevised=True)
    assert _row(temp_db, mid)["importance"] == pytest.approx(once)


def test_importance_cannot_be_raised_on_another_mind_s_memory(temp_db):
    """The ids arrive from model output. Ownership is in the WHERE clause, not
    in whoever remembers to check first."""
    chat_id, mine, theirs = _fixture(temp_db)
    mid = add_memory(chat_id, theirs, None, "episodic", "witnessed", 0.5,
                     "not yours", turn_idx=1)
    assert raise_importance(chat_id, mine, [mid]) == 0
    assert _row(temp_db, mid)["importance"] is None


# --- what importance changes downstream -----------------------------------

def test_a_memory_that_became_important_is_not_archived(temp_db):
    """Archiving reads the HIGHER of the two, which is the whole reason they
    are separate numbers: a memory that turned out to matter must not be
    retired on the strength of how ordinary it looked at the time."""
    ordinary = {"salience": 0.4, "importance": None, "turn_idx": 1,
                "id": 1, "category": "episode"}
    became = {"salience": 0.4, "importance": 0.9, "turn_idx": 1,
              "id": 2, "category": "episode"}
    keep = lambda m: max(float(m["salience"]), effective_importance(m)) < 0.72
    assert keep(ordinary) is True
    assert keep(became) is False


def test_ranking_prefers_the_memory_that_became_important(temp_db):
    chat_id, mine, _ = _fixture(temp_db)
    a = add_memory(chat_id, mine, None, "episodic", "witnessed", 0.5,
                   "the lantern guttered in the west corridor", turn_idx=1)
    b = add_memory(chat_id, mine, None, "episodic", "witnessed", 0.5,
                   "the lantern guttered in the east corridor", turn_idx=1)
    raise_importance(chat_id, mine, [b], step=0.9)
    got = search_memories(chat_id, mine, "the lantern guttered corridor", k=2,
                          current_turn_idx=9, chronological=False,
                          viewer_frame_id=None)
    scores = {m["id"]: m["score"] for m in got}
    assert scores[b] > scores[a]


# --- a dispute records a re-reading and leaves the memory alone -----------

def test_a_dispute_leaves_the_memory_itself_untouched(temp_db):
    chat_id, mine, _ = _fixture(temp_db)
    mid = add_memory(chat_id, mine, None, "episodic", "witnessed", 0.6,
                     "Dr Moon handed me the vial", gist="Dr Moon handed me the vial",
                     turn_idx=3)
    before = dict(_row(temp_db, mid))
    record_dispute(chat_id, mine, "Dr Moon handed me the vial",
                   "the face was a mask; I do not know who that was", 11)
    after = _row(temp_db, mid)
    for field in ("content", "gist", "provenance", "salience", "turn_idx",
                  "valence", "kind", "category"):
        assert after[field] == before[field], field
    assert after["disputed"], "the re-reading is recorded beside it"


def test_a_dispute_is_readable_and_carries_its_reading(temp_db):
    chat_id, mine, _ = _fixture(temp_db)
    add_memory(chat_id, mine, None, "episodic", "witnessed", 0.6,
               "Dr Moon handed me the vial", gist="Dr Moon handed me the vial",
               turn_idx=3)
    record_dispute(chat_id, mine, "Dr Moon handed me the vial",
                   "the face was a mask", 11)
    got = list_memories(chat_id, mine, viewer_frame_id=None)[0]
    assert got["disputed"]["reading"] == "the face was a mask"
    assert got["disputed"]["turn_idx"] == 11
    assert got["disputed"]["count"] == 1


def test_reconsidering_twice_is_counted(temp_db):
    chat_id, mine, _ = _fixture(temp_db)
    add_memory(chat_id, mine, None, "episodic", "witnessed", 0.6,
               "Dr Moon handed me the vial", gist="Dr Moon handed me the vial",
               turn_idx=3)
    record_dispute(chat_id, mine, "Dr Moon handed me the vial", "a mask", 11)
    record_dispute(chat_id, mine, "Dr Moon handed me the vial", "not a mask", 19)
    got = list_memories(chat_id, mine, viewer_frame_id=None)[0]
    assert got["disputed"]["count"] == 2
    assert got["disputed"]["reading"] == "not a mask"


def test_a_dispute_raises_importance(temp_db):
    """Being wrong about something is a bigger fact about it than being cited
    once, and it makes the memory MORE central, not less."""
    chat_id, mine, _ = _fixture(temp_db)
    mid = add_memory(chat_id, mine, None, "episodic", "witnessed", 0.5,
                     "Dr Moon handed me the vial", gist="Dr Moon handed me the vial",
                     turn_idx=3)
    record_dispute(chat_id, mine, "Dr Moon handed me the vial", "a mask", 11)
    assert _row(temp_db, mid)["importance"] > 0.5


def test_a_dispute_cannot_touch_another_mind_s_memory(temp_db):
    chat_id, mine, theirs = _fixture(temp_db)
    mid = add_memory(chat_id, theirs, None, "episodic", "witnessed", 0.6,
                     "Dr Moon handed me the vial", gist="Dr Moon handed me the vial",
                     turn_idx=3)
    assert record_dispute(chat_id, mine, "Dr Moon handed me the vial",
                          "a mask", 11) == []
    assert not _row(temp_db, mid)["disputed"]


def test_a_dispute_of_nothing_records_nothing(temp_db):
    chat_id, mine, _ = _fixture(temp_db)
    add_memory(chat_id, mine, None, "episodic", "witnessed", 0.6,
               "the lantern guttered", turn_idx=3)
    assert record_dispute(chat_id, mine, "a memory I never had", "x", 5) == []
    assert record_dispute(chat_id, mine, "", "x", 5) == []
    assert record_dispute(chat_id, mine, "the lantern guttered", "", 5) == []


def test_a_malformed_dispute_blob_does_not_break_reading(temp_db):
    chat_id, mine, _ = _fixture(temp_db)
    mid = add_memory(chat_id, mine, None, "episodic", "witnessed", 0.6,
                     "the lantern guttered", turn_idx=3)
    temp_db.qi("UPDATE memories SET disputed=? WHERE id=?", ("{not json", mid))
    got = list_memories(chat_id, mine, viewer_frame_id=None)[0]
    assert got["disputed"] is None


def test_the_character_sees_the_reading_beside_the_memory(temp_db):
    """Handed over unchanged, with the revision under its own key. Collapsing
    them would either erase the experience or hide the correction, and a mind
    that has been deceived holds both."""
    entry = memory._with_reading({
        "id": 1, "gist": "Dr Moon handed me the vial",
        "disputed": {"reading": "the face was a mask", "count": 1},
    })
    assert entry["gist"] == "Dr Moon handed me the vial"
    assert entry["i_now_read_this_differently"] == "the face was a mask"
    assert "disputed" not in entry


def test_an_undisputed_memory_is_projected_without_mutating_storage():
    mem = {"id": 1, "event_key": "event:stable", "gist": "g",
           "disputed": None}
    projected = memory._with_reading(mem, current_turn_idx=4)
    assert projected is not mem
    assert mem == {"id": 1, "event_key": "event:stable", "gist": "g",
                   "disputed": None}
    assert projected["memory_ref"] == "event:stable"
    assert projected["temporal_status"] == "remembered_past"
    assert projected["when"] == "before this story's recorded turns"


# --- both survive the round-trips -----------------------------------------

def test_importance_and_dispute_survive_dump_and_restore(temp_db):
    chat_id, mine, _ = _fixture(temp_db)
    mid = add_memory(chat_id, mine, None, "episodic", "witnessed", 0.5,
                     "Dr Moon handed me the vial", gist="Dr Moon handed me the vial",
                     turn_idx=3)
    raise_importance(chat_id, mine, [mid], step=0.6)
    record_dispute(chat_id, mine, "Dr Moon handed me the vial", "a mask", 11)
    before = list_memories(chat_id, mine, viewer_frame_id=None)[0]

    dump = memory.dump_chat_memories(chat_id)
    assert dump[0]["importance"] is not None
    assert dump[0]["disputed"]
    memory.restore_chat_memories(chat_id, dump)

    after = list_memories(chat_id, mine, viewer_frame_id=None)[0]
    assert after["importance"] == pytest.approx(before["importance"])
    assert after["disputed"] == before["disputed"]


def test_legacy_memory_citation_ref_survives_dump_and_restore(temp_db):
    chat_id, mine, _ = _fixture(temp_db)
    add_memory(chat_id, mine, None, "episodic", "witnessed", 0.5,
               "The brass door opened.", gist="the brass door opened",
               turn_idx=3)
    assert memory.backfill_missing_memory_event_keys(chat_id, mine) == 1
    before = list_memories(chat_id, mine, viewer_frame_id=None)[0]["event_key"]
    assert before.startswith("event:")
    dump = memory.dump_chat_memories(chat_id)
    memory.restore_chat_memories(chat_id, dump)
    after = list_memories(chat_id, mine, viewer_frame_id=None)[0]["event_key"]
    assert after == before


def test_they_survive_a_character_bank_export(temp_db):
    chat_id, mine, theirs = _fixture(temp_db)
    mid = add_memory(chat_id, mine, None, "episodic", "witnessed", 0.5,
                     "Dr Moon handed me the vial", gist="Dr Moon handed me the vial",
                     turn_idx=3)
    raise_importance(chat_id, mine, [mid], step=0.6)
    record_dispute(chat_id, mine, "Dr Moon handed me the vial", "a mask", 11)
    carried = memory.dump_character_memories(chat_id, mine)
    memory.import_character_memories(chat_id, theirs, carried)
    got = list_memories(chat_id, theirs, viewer_frame_id=None)[0]
    assert got["importance_revised"] is True
    assert got["disputed"]["reading"] == "a mask"


# --- character-marked dialogue --------------------------------------------

def test_a_marked_line_is_matched_loosely_in_both_directions():
    from commit import _marked_for_memory
    own = {"remember_lines": [{"quote": "the seal drops at midnight",
                               "why": "I have to be gone by then"}]}
    assert _marked_for_memory(own, "the seal drops at midnight")
    assert _marked_for_memory(own, "the seal drops at midnight, remember")
    assert _marked_for_memory(own, '"the seal drops at midnight"')
    assert not _marked_for_memory(own, "the kettle is on")


def test_an_empty_or_malformed_mark_marks_nothing():
    from commit import _marked_for_memory
    assert not _marked_for_memory({}, "anything")
    assert not _marked_for_memory({"remember_lines": []}, "anything")
    assert not _marked_for_memory({"remember_lines": ["not a dict"]}, "anything")
    assert not _marked_for_memory({"remember_lines": [{"quote": "  "}]}, "anything")
    assert not _marked_for_memory({"remember_lines": [{"quote": "x"}]}, "")


def test_the_schema_keeps_marks_and_disputes_and_drops_the_useless():
    from schemas import validate_llm_output
    out, _w = validate_llm_output("character", {
        "sequence": [],
        "remember_lines": [
            {"quote": "the seal drops at midnight", "why": "I must go"},
            {"quote": "   "},                      # nothing to match on
            "not a dict",
        ],
        "memory_disputes": [
            {"gist": "Dr Moon handed me the vial", "now_reads": "a mask"},
            {"gist": "half an entry"},             # no reading
            {"now_reads": "no memory named"},
        ],
    })
    assert out["remember_lines"] == [
        {"quote": "the seal drops at midnight", "why": "I must go",
         "evidence": []}]
    assert out["memory_disputes"] == [
        {"memory_ref": "", "gist": "Dr Moon handed me the vial",
         "now_reads": "a mask", "evidence": []}]


def test_both_fields_default_empty():
    from schemas import validate_llm_output
    out, _w = validate_llm_output("character", {"sequence": []})
    assert out["remember_lines"] == []
    assert out["memory_disputes"] == []


def test_only_belief_evidence_counts_as_a_citation():
    """Bare observations_used deliberately does not: citing a memory while
    describing the beat is not building a belief on it, and the weaker signal
    fires on nearly every turn."""
    from commit import _cited_memory_ids
    assert _cited_memory_ids({
        "observations_used": [{"event_id": "event:abc123", "fact": "x"}],
    }) == []
    assert _cited_memory_ids({
        "mind_model_updates": [
            {"about_entity": "Bram", "claim": "lying",
             "evidence": [{"event_id": "event:abc123"}, {"event_id": "current"},
                          {"event_id": "turn:2:character:39:0:action"}]},
        ],
    }) == ["event:abc123"]


def test_a_citation_is_an_event_key_not_a_row_id():
    """This assertion used to require a numeric ROW id, which is a format no
    character has ever produced. Across a 10-turn live run the handles emitted
    were `current` (x66), `current:39:4`, `turn:2:character:39:0:action` and
    `event:<hash>` -- and the last of those IS `memories.event_key`, with all
    five distinct ones resolving to a real row. The reader was looking for the
    wrong thing, the test agreed with it, and 3733 tests passed over a feature
    that could never fire.
    """
    from commit import _cited_memory_ids
    assert _cited_memory_ids({
        "mind_model_updates": [{"evidence": [{"event_id": "41"}]}],
    }) == [], "a bare number is not a memory handle"


def test_importance_rises_through_an_event_key(temp_db):
    """The end-to-end shape of the repaired path: what the character cites is
    what gets raised."""
    chat_id, mine, _ = _fixture(temp_db)
    mid = add_memory(chat_id, mine, None, "episodic", "witnessed", 0.5,
                     "the lantern guttered", turn_idx=1,
                     event_key="event:deadbeef")
    raise_importance(chat_id, mine, event_keys=["event:deadbeef"],
                     only_unrevised=True)
    assert _row(temp_db, mid)["importance"] > 0.5


def test_an_event_key_belonging_to_another_mind_moves_nothing(temp_db):
    chat_id, mine, theirs = _fixture(temp_db)
    mid = add_memory(chat_id, theirs, None, "episodic", "witnessed", 0.5,
                     "not yours", turn_idx=1, event_key="event:deadbeef")
    assert raise_importance(chat_id, mine, event_keys=["event:deadbeef"]) == 0
    assert _row(temp_db, mid)["importance"] is None
