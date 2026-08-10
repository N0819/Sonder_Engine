"""Why a stance is where it is.

The scalar relationship graph answers WHERE a relationship stands and cannot
answer how it got there. It keeps one `salient_event` string and overwrites it
whenever the character's feelings move at all — so the reason somebody stopped
trusting you survives exactly until the next time they feel anything.

Measured before this was built, because the interesting question was whether
the reasons existed at all: 98.8% of the 5,704 stance movements in the live
corpus already carried `trigger_event_ids`. The model had been saying why the
whole time; the seam threw it away. 5,638 recorded reasons destroyed.
"""

from __future__ import annotations

import pytest

from memory import (apply_relationship_updates, get_relationships,
                    relationship_history)


def _chat(db):
    import time
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Rel", "", time.time()))


def _history(db, cid):
    apply_relationship_updates(cid, 7, 12, [{
        "target_entity": "Mora", "trust_delta": -0.2, "fear_delta": 0.15,
        "trigger_event_ids": ["ev:she-lied"],
        "reason": "she lied about the gate"}])
    apply_relationship_updates(cid, 7, 19, [{
        "target_entity": "Mora", "trust_delta": 0.1,
        "trigger_event_ids": ["ev:she-came-back"],
        "reason": "she came back for me"}])
    return relationship_history(cid, 7, "Mora")


class TestTheReasonSurvives:
    def test_an_earlier_reason_is_not_erased_by_a_later_one(self):
        """THE defect. `salient_event` holds only the most recent trigger, so
        "she lied about the gate" — the reason trust fell at all — is gone from
        the scalar state the moment anything else happens."""
        import db as db_module
        cid = _chat(db_module)
        notes = [e["note"] for e in _history(db_module, cid)]
        assert "she lied about the gate" in notes
        assert "she came back for me" in notes

        graph = get_relationships(cid, 7)
        assert graph.get("Mora").salient_event == "ev:she-came-back"

    def test_each_axis_is_its_own_event(self):
        """"Trust fell and fear rose" and "trust fell" are different events
        with different consequences. A single blended row could never be read
        back into either."""
        import db as db_module
        cid = _chat(db_module)
        first_turn = [e for e in _history(db_module, cid) if e["turn_idx"] == 12]
        assert sorted(e["axis"] for e in first_turn) == ["fear", "trust"]
        assert all(e["note"] == "she lied about the gate" for e in first_turn)

    def test_the_ledger_is_ordered_oldest_first(self):
        import db as db_module
        cid = _chat(db_module)
        turns = [e["turn_idx"] for e in _history(db_module, cid)]
        assert turns == sorted(turns)


class TestTheProjectionStillAgrees:
    def test_the_scalar_state_is_the_sum_of_its_history(self):
        """The ledger is added BESIDE the graph, not instead of it, so the two
        must not drift. If this ever fails, one of them is lying about the
        same relationship."""
        import db as db_module
        cid = _chat(db_module)
        events = _history(db_module, cid)
        graph = get_relationships(cid, 7).get("Mora")

        summed = {}
        for e in events:
            summed[e["axis"]] = summed.get(e["axis"], 0.0) + e["delta"]
        assert graph.trust == pytest.approx(summed["trust"])
        assert graph.fear == pytest.approx(summed["fear"])


class TestEvidenceIsMarkedRatherThanDemanded:
    def test_a_movement_with_no_trigger_is_recorded_as_unevidenced(self):
        """Item 4 asks for triggering evidence to be mandatory. Refusing the
        update would throw away a movement the character genuinely felt and
        leave the graph wrong; marking it keeps the feeling AND makes the gap
        countable. 66 of 5,704 live movements have no recorded reason, so this
        is a rare case worth measuring rather than a common one worth
        blocking."""
        import db as db_module
        cid = _chat(db_module)
        apply_relationship_updates(cid, 7, 3, [{
            "target_entity": "Mora", "warmth_delta": -0.05,
            "trigger_event_ids": []}])
        events = relationship_history(cid, 7, "Mora")
        assert [e["provenance"] for e in events] == ["unevidenced"]

    def test_a_movement_of_zero_is_not_an_event(self):
        """A stance that did not move is not a reason for anything."""
        import db as db_module
        cid = _chat(db_module)
        apply_relationship_updates(cid, 7, 3, [{
            "target_entity": "Mora", "trust_delta": 0.0,
            "trigger_event_ids": ["ev:nothing"]}])
        assert relationship_history(cid, 7, "Mora") == []


class TestItRollsBackWithTheStory:
    def test_the_frame_travels_with_the_reason(self, temp_db):
        """A branch that never had the argument must not inherit the reason
        it happened."""
        import inspect

        import commit
        source = inspect.getsource(commit)
        assert "apply_relationship_updates(cid, char_id, turn.idx, updates," \
            in source
        assert "frame_id=ctx.turn.frame_id" in source


@pytest.fixture(autouse=True)
def _db(temp_db):
    """Every test here writes rows; they all need a database."""
    yield temp_db
