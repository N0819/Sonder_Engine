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

from mind.memory import (apply_relationship_updates, get_relationships,
                         relationship_history,
                         update_relationships_from_inference)


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
        from core import db as db_module
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
        from core import db as db_module
        cid = _chat(db_module)
        first_turn = [e for e in _history(db_module, cid) if e["turn_idx"] == 12]
        assert sorted(e["axis"] for e in first_turn) == ["fear", "trust"]
        assert all(e["note"] == "she lied about the gate" for e in first_turn)

    def test_the_ledger_is_ordered_oldest_first(self):
        from core import db as db_module
        cid = _chat(db_module)
        turns = [e["turn_idx"] for e in _history(db_module, cid)]
        assert turns == sorted(turns)


class TestEveryPathThatMovesAStanceLeavesAReason:
    """There are two of them, and only one was writing rows.

    `apply_relationship_updates` carries a declared stance change and records
    an event per axis. `update_relationships_from_inference` moves trust from
    what a character CONCLUDED about someone -- the same scalar, the same
    graph, saved by the same call -- and wrote nothing at all. A whole class of
    trust movement was missing from a ledger whose entire purpose is that it is
    never updated and never deleted, so the gap does not show as a wrong row;
    it shows as a stance the history cannot explain.
    """

    def test_an_inferred_trust_move_is_recorded(self):
        from core import db as db_module
        cid = _chat(db_module)

        update_relationships_from_inference(cid, 7, 12, [{
            "about": "Mora", "confidence": 0.8,
            "conclusion": "she lied about the gate"}])

        history = relationship_history(cid, 7, "Mora")
        assert [e["axis"] for e in history] == ["trust"]
        assert history[0]["delta"] < 0
        assert "lied" in history[0]["note"]

    def test_the_reason_is_marked_as_inferred_not_declared(self):
        """Concluding someone is dangerous and being TOLD you distrust them are
        different provenances, and the ledger already distinguishes evidenced
        from unevidenced for exactly this reason."""
        from core import db as db_module
        cid = _chat(db_module)

        update_relationships_from_inference(cid, 7, 12, [{
            "about": "Mora", "confidence": 0.9,
            "conclusion": "she saved me from the water"}])

        history = relationship_history(cid, 7, "Mora")
        assert history[0]["provenance"] == "inference"
        assert history[0]["delta"] > 0

    def test_a_conclusion_that_moves_nothing_writes_nothing(self):
        """Familiarity creeps up on every mention; that is not a reason for
        anything and must not fill the ledger with rows carrying no delta."""
        from core import db as db_module
        cid = _chat(db_module)

        update_relationships_from_inference(cid, 7, 12, [{
            "about": "Mora", "confidence": 0.5,
            "conclusion": "she is standing by the window"}])

        assert relationship_history(cid, 7, "Mora") == []


class TestTheProjectionStillAgrees:
    def test_the_scalar_state_is_the_sum_of_its_history(self):
        """The ledger is added BESIDE the graph, not instead of it, so the two
        must not drift. If this ever fails, one of them is lying about the
        same relationship."""
        from core import db as db_module
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
        from core import db as db_module
        cid = _chat(db_module)
        apply_relationship_updates(cid, 7, 3, [{
            "target_entity": "Mora", "warmth_delta": -0.05,
            "trigger_event_ids": []}])
        events = relationship_history(cid, 7, "Mora")
        assert [e["provenance"] for e in events] == ["unevidenced"]

    def test_a_movement_of_zero_is_not_an_event(self):
        """A stance that did not move is not a reason for anything."""
        from core import db as db_module
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

        from persist import commit
        # The applier call lives in commit_memories (commit_memory_write
        # since the split); the function source survives the move.
        source = inspect.getsource(commit.commit_memories)
        assert "apply_relationship_updates(cid, char_id, turn.idx, updates," \
            in source
        assert "frame_id=ctx.turn.frame_id" in source


@pytest.fixture(autouse=True)
def _db(temp_db):
    """Every test here writes rows; they all need a database."""
    yield temp_db


class TestItSurvivesTheThingsTheGateRequires:
    """The architectural completion gate asks that relationships "survive
    checkpoint, reroll, branch, archive/import and deletion as applicable".

    Both paths enumerate their tables BY NAME, so a new one is invisible to
    them until it is listed — an export would silently lose the whole ledger
    and a rewind would leave a character holding a grudge about a thing that
    no longer happened. Neither failure raises anything.
    """

    def test_a_rewind_takes_the_reason_with_it(self, temp_db):
        from persist.checkpoints import insert_world_tables, snapshot_state

        cid = _chat(temp_db)
        before = snapshot_state(cid)
        assert before["relationship_events"] == []

        apply_relationship_updates(cid, 7, 12, [{
            "target_entity": "Mora", "trust_delta": -0.2,
            "trigger_event_ids": ["ev:she-lied"],
            "reason": "she lied about the gate"}])
        assert len(relationship_history(cid, 7, "Mora")) == 1

        insert_world_tables(cid, before, delete_first=True)
        assert relationship_history(cid, 7, "Mora") == []

    def test_a_snapshot_carries_it_back(self, temp_db):
        from persist.checkpoints import insert_world_tables, snapshot_state

        cid = _chat(temp_db)
        apply_relationship_updates(cid, 7, 12, [{
            "target_entity": "Mora", "trust_delta": -0.2,
            "trigger_event_ids": ["ev:she-lied"],
            "reason": "she lied about the gate"}])
        blob = snapshot_state(cid)
        assert len(blob["relationship_events"]) == 1

        insert_world_tables(cid, {"relationship_events": []}, delete_first=True)
        insert_world_tables(cid, blob)
        restored = relationship_history(cid, 7, "Mora")
        assert [e["note"] for e in restored] == ["she lied about the gate"]

    def test_the_archive_declares_it(self):
        """An undeclared field validates cleanly and is then silently dropped
        by `extra="ignore"` — the failure that kept `stations` inert for 45
        scenes. The model's own comment says so."""
        from persist.chat_archive import ChatArchiveData

        assert "relationship_events" in ChatArchiveData.__fields__

    def test_the_archive_exports_and_imports_it(self, temp_db):
        """Asked of the round trip, not of the source text.

        Counting `"relationship_events",` in the module answered a question
        about how the two table tuples were SPELLED, which stops being true
        the moment they are named once instead of twice -- and was never
        evidence that the ledger arrives, only that the string appears.
        """
        import json
        import time

        from web import app

        cid = _chat(temp_db)
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            ("Mora", json.dumps({"identity": {"name": "Mora"}}), "{}",
             time.time(), "rel_mora"),
        )
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) "
            "VALUES(?,?,'active','{}')", (cid, char_id))
        apply_relationship_updates(cid, char_id, 12, [{
            "target_entity": "Mora", "trust_delta": -0.2,
            "trigger_event_ids": ["ev:she-lied"],
            "reason": "she lied about the gate"}])

        archive = json.loads(json.dumps(app.chat_export(cid)))
        assert len(archive["relationship_events"]) == 1

        # A stance whose character does not remap is dropped rather than
        # reattached to whoever inherited the number in the new chat.
        archive["relationship_events"].append(
            dict(archive["relationship_events"][0], char_id=999999,
                 note="belongs to nobody here"))

        new_cid = app.chat_import({"data": archive})["id"]
        new_char = temp_db.q(
            "SELECT char_id FROM chat_chars WHERE chat_id=?",
            (new_cid,), one=True)["char_id"]
        restored = relationship_history(new_cid, new_char, "Mora")
        assert [e["note"] for e in restored] == ["she lied about the gate"]
        assert temp_db.q(
            "SELECT COUNT(*) n FROM relationship_events WHERE chat_id=?",
            (new_cid,), one=True)["n"] == 1
