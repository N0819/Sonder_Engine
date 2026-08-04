"""Why importance was revised on 9 memories out of 6,460.

`_cited_memory_ids` decides which memories a beat proved load-bearing, and
`raise_importance(only_unrevised=True)` lifts each of them once, ever. It read
one field: evidence attached to `mind_model_updates`. Measured over the beats
whose stored result could have supplied any candidate signal at all
(`tools/fire_rates.py`, 83 results):

    mind_model_updates evidence citing a stored memory     6 of 83   (7%)
    belief_updates evidence citing a stored memory         1 of 83   (1%)
    memory_effects, disposition `integrated`              74 of 83  (89%)

So importance was not failing to fire because consequences are rare. It was
reading the rarest thing a character emits and ignoring the field that says
precisely what it is looking for -- the character stating that a recalled
memory changed their recognition, appraisal, choice or speech.

This is the second time this exact function has been wrong in the same way. Its
first version required a numeric row id and matched nothing across a whole live
run, because characters cite `event:<hash>`. The format was fixed and the
question was never re-asked: is it reading all the places that answer it?

What must NOT change is the reason the function is careful. Retrieval alone
still moves nothing -- a memory that gets recalled would rank higher and get
recalled more, which is a popularity loop wearing the word "importance".
`memory_effects` is admissible because it is a stated consequence, and its own
prompt forbids emitting one merely because a row was present; `resisted` and
`dismissed` are not, because a memory the character pushed away influenced the
beat without turning out to matter.
"""

from __future__ import annotations

import time

import pytest

from commit import _cited_memory_ids
from memory import add_memory, effective_importance, raise_importance

REF = "event:1a2b3c"
OTHER = "event:9z8y7x"


def _effect(ref=REF, disposition="integrated"):
    return {"memory_ref": ref, "use": "recognition",
            "disposition": disposition, "changed": "she knew the voice"}


class TestTheSignalThatWasMissing:
    def test_an_integrated_memory_effect_counts(self):
        assert _cited_memory_ids({"memory_effects": [_effect()]}) == [REF]

    def test_it_is_the_field_that_actually_fires(self):
        """The whole diagnosis in one case: a beat that emits a memory effect
        and no belief at all -- 74 of the 83 measured results -- used to move
        nothing."""
        result = {"mind_model_updates": [], "belief_updates": [],
                  "memory_effects": [_effect()]}
        assert _cited_memory_ids(result) == [REF]

    def test_belief_evidence_counts_as_the_docstring_always_claimed(self):
        result = {"belief_updates": [
            {"belief": "he was never a merchant", "confidence": 0.7,
             "evidence": [{"event_id": REF, "fact": "the ledger"}]}]}
        assert _cited_memory_ids(result) == [REF]

    def test_the_original_signal_still_works(self):
        result = {"mind_model_updates": [
            {"about_entity": "Bram", "kind": "intent", "claim": "he is lying",
             "evidence": [{"event_id": REF, "fact": "the ledger"}]}]}
        assert _cited_memory_ids(result) == [REF]

    def test_several_signals_about_one_memory_lift_it_once(self):
        result = {"memory_effects": [_effect()],
                  "belief_updates": [
                      {"belief": "x", "evidence": [{"event_id": REF}]}]}
        assert _cited_memory_ids(result) == [REF]


class TestWhatStillMovesNothing:
    def test_a_resisted_memory_does_not_count(self):
        """It influenced the beat -- that is what `resisted` means -- but
        being pushed away is not turning out to matter, and counting it would
        make importance a measure of how loudly a memory arrived."""
        assert _cited_memory_ids({"memory_effects": [
            _effect(disposition="resisted")]}) == []

    def test_a_dismissed_memory_does_not_count(self):
        assert _cited_memory_ids({"memory_effects": [
            _effect(disposition="dismissed")]}) == []

    def test_an_effect_with_no_disposition_does_not_count(self):
        """Absent is not `integrated`. The schema defaults it, so a missing
        one means the model never made the claim."""
        assert _cited_memory_ids({"memory_effects": [
            {"memory_ref": REF, "changed": "something"}]}) == []

    def test_bare_retrieval_still_moves_nothing(self):
        """The invariant the whole function exists to protect. Recalling a
        memory, and even citing it while describing the beat, must never lift
        it -- that is the feedback loop."""
        result = {"observations_used": [{"event_id": REF, "fact": "recalled"}],
                  "memory_evidence_used": [{"event_id": REF, "fact": "x"}]}
        assert _cited_memory_ids(result) == []

    def test_the_present_beat_is_not_a_stored_memory(self):
        result = {"memory_effects": [_effect(ref="current:Mara:0")],
                  "mind_model_updates": [
                      {"about_entity": "x", "kind": "y", "claim": "z",
                       "evidence": [{"event_id": "current"}]}]}
        assert _cited_memory_ids(result) == []

    def test_a_turn_handle_is_not_a_stored_memory(self):
        assert _cited_memory_ids({"memory_effects": [
            _effect(ref="turn:2:character:39:0:action")]}) == []

    def test_malformed_input_is_survivable(self):
        assert _cited_memory_ids(None) == []
        assert _cited_memory_ids({"memory_effects": ["not a dict", None]}) == []
        assert _cited_memory_ids({"belief_updates": [{"evidence": "no"}]}) == []


class TestTheCeilingHolds:
    """Widening the inputs widens which memories can be lifted once, never how
    far any of them travels."""

    def test_a_memory_is_still_lifted_exactly_once_ever(self, temp_db):
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("T", "", time.time()))
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
            ("Mara", "{}", "{}", time.time()))
        mid = add_memory(chat_id, char_id, None, "episodic", "witnessed", 0.50,
                         "the ledger", gist="the ledger", turn_idx=1,
                         event_key=REF)
        raise_importance(chat_id, char_id, event_keys=[REF], only_unrevised=True)
        first = effective_importance(
            temp_db.q("SELECT * FROM memories WHERE id=?", (mid,), one=True))
        for _ in range(5):
            raise_importance(chat_id, char_id, event_keys=[REF],
                             only_unrevised=True)
        after = effective_importance(
            temp_db.q("SELECT * FROM memories WHERE id=?", (mid,), one=True))
        assert first > 0.50
        assert after == first

    def test_salience_is_never_touched(self, temp_db):
        """How much it mattered when it was FORMED is a different fact, and
        the one archiving and consolidation still read."""
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("T", "", time.time()))
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
            ("Mara", "{}", "{}", time.time()))
        mid = add_memory(chat_id, char_id, None, "episodic", "witnessed", 0.50,
                         "the ledger", gist="the ledger", turn_idx=1,
                         event_key=REF)
        raise_importance(chat_id, char_id, event_keys=[REF], only_unrevised=True)
        row = temp_db.q("SELECT * FROM memories WHERE id=?", (mid,), one=True)
        assert row["salience"] == pytest.approx(0.50)
        assert row["importance"] > 0.50

    def test_it_cannot_reach_another_mind_s_memory(self, temp_db):
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("T", "", time.time()))
        mine = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
            ("Mara", "{}", "{}", time.time()))
        theirs = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
            ("Bram", "{}", "{}", time.time()))
        mid = add_memory(chat_id, mine, None, "episodic", "witnessed", 0.50,
                         "the ledger", gist="the ledger", turn_idx=1,
                         event_key=REF)
        raise_importance(chat_id, theirs, event_keys=[REF], only_unrevised=True)
        row = temp_db.q("SELECT * FROM memories WHERE id=?", (mid,), one=True)
        assert row["importance"] is None


def test_only_grounded_effects_ever_reach_this_function():
    """The firewall this relies on and does not itself enforce: a
    `memory_effects` entry naming a memory that was never delivered to this
    mind is dropped in `agents.character._ground_observation_citations` before
    commit sees it. Without that, a model could lift any row it guessed the
    key of."""
    import inspect

    from agents import character
    src = inspect.getsource(character._ground_observation_citations)
    block = src[src.index('for index, effect in enumerate('):]
    assert 'if ref in memories:' in block
    assert 'dropped ungrounded memory_effects' in block
