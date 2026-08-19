"""A restraint is a RELATION -- someone or something holding a body -- not a flag.

Measured against the owner's live database (engine.db, read-only, 2026-08-18),
the 24 active restraint-family rows are not one situation:

* 11 are genuine unattended bindings -- metal cuffs to a bolted interview
  chair (chats 77-80, one scenario family, six of them redescribing the same
  cuffs on one body).
* 6 are live grips by a named body: a hand pinning an arm ("restrained_by":
  "Dr. Moon", chats 23/27), an arm barring a doorway ("blocked_by": "The
  Doctor", chat 32), a body enveloped and held ("enveloped_by", chats
  52/60/61).
* 4 are intimate embraces, one of whose own description says "no actual
  restraint on Elyndra beyond the intimate proximity of the embrace"
  (chats 50/51).
* 2 record the SUBJECT doing the gripping -- "Both hands gripping the brass
  lever" (chats 57/58, `type: "grip"`).
* 1 carries no state at all (`state: "active"`, chat 44).

A reader that collapses all of that to restrained-yes/no immobilises the
embraced and the lever-holder alongside the cuffed. The physics the rungs
name: a HOLD (`held`, or `pinned` by a body) is a live relation -- it cannot
outlive its holder's presence and consciousness, and a hold that names no
holder is a description, not a mechanism, so it blocks nobody. A STANDING
restraint (`bound`, `encased`, or `pinned` by a mass) holds with nobody
attending it and blocks until something ends it.
"""

from __future__ import annotations

import json
import time

from agents.director import _restraint_blocked_moves
from story.scene import (
    STANDING_RESTRAINTS,
    apply_restraint_records_diff,
    restraint_conditions,
    restraint_map,
    restraint_of,
)

SUBJECT = "Hinami"


def _cond(cond_id, state, subject=SUBJECT, kind="restraint", active=1,
          started=100.0):
    return {
        "condition_id": cond_id, "subject_id": subject, "kind": kind,
        "active": active, "started_at_seconds": started, "state": state,
    }


def _insert(db, chat_id, cond):
    db.qi(
        "INSERT INTO world_conditions(condition_id,chat_id,subject_id,kind,"
        "started_at,expires_at,next_tick,payload,active) "
        "VALUES(?,?,?,?,?,?,?,?,?)",
        (cond["condition_id"], chat_id, cond["subject_id"], cond["kind"],
         cond.get("started_at_seconds", 0.0), None, None,
         json.dumps(cond), int(cond.get("active", 1))))


def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Restraint", "", time.time()))


# --- the record: id, holder, clock ------------------------------------------

class TestRestraintRecords:
    def test_a_record_carries_the_id_an_ending_must_reemit(self, temp_db):
        chat_id = _chat(temp_db)
        _insert(temp_db, chat_id, _cond("c1", {"level": "bound", "by": "Tamamo",
                                               "means": "rope"}))
        records = restraint_conditions(chat_id)
        assert len(records) == 1
        assert records[0]["condition_id"] == "c1"
        assert records[0]["subject"] == SUBJECT
        assert records[0]["started_at_seconds"] == 100.0
        assert records[0]["payload"]["state"]["means"] == "rope"

    def test_the_rung_is_read_from_the_field_the_beat_used(self, temp_db):
        """No live row carries `state.level`. They carry `restraint_type`
        ("metal_cuffs", "chair_restraints") or `type` ("grip",
        "held_in_embrace")."""
        chat_id = _chat(temp_db)
        _insert(temp_db, chat_id,
                _cond("c1", {"restraint_type": "metal_cuffs"}))
        assert restraint_conditions(chat_id)[0]["level"] == "bound"

        chat_two = _chat(temp_db)
        _insert(temp_db, chat_two, _cond("c2", {"type": "held_in_embrace"}))
        assert restraint_conditions(chat_two)[0]["level"] == "held"

    def test_the_holder_is_read_from_the_field_the_beat_used(self, temp_db):
        """Live rows name the holder as `restrained_by`, `blocked_by`,
        `held_by` or `enveloped_by` as often as `by`."""
        chat_id = _chat(temp_db)
        _insert(temp_db, chat_id,
                _cond("c1", {"restrained_by": "Dr. Moon"}))
        _insert(temp_db, chat_id,
                _cond("c2", {"blocked_by": "The Doctor"}, subject="Kaede"))
        records = restraint_conditions(chat_id)
        by = {r["subject"]: r["by"] for r in records}
        assert by == {SUBJECT: "Dr. Moon", "Kaede": "The Doctor"}

    def test_no_evidence_reads_as_the_rung_that_claims_least(self, temp_db):
        """Live chat 44 carries `state: "active"` -- a string, no fields at
        all. The old default handed the strongest reading (`bound`) to the
        weakest evidence; now that the rung decides whether a body can move
        with nobody holding it, a record that says nothing about what holds
        the body must claim least: `held`, with no holder."""
        chat_id = _chat(temp_db)
        temp_db.qi(
            "INSERT INTO world_conditions(condition_id,chat_id,subject_id,kind,"
            "started_at,expires_at,next_tick,payload,active) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            ("c1", chat_id, SUBJECT, "restraint", 100.0, None, None,
             json.dumps({"condition_id": "c1", "subject_id": SUBJECT,
                         "kind": "restraint", "state": "active"}), 1))
        record = restraint_conditions(chat_id)[0]
        assert record["level"] == "held"
        assert record["by"] == ""
        assert record["standing"] is False

    def test_standing_is_the_physics_of_the_rung(self, temp_db):
        """A knot stays tied when the tier walks away; a grip does not
        outlive the gripper. `pinned` is either -- a body bearing down or a
        fallen mass -- so which it is is the record's holder field."""
        chat_id = _chat(temp_db)
        _insert(temp_db, chat_id, _cond("c1", {"level": "bound"}))
        _insert(temp_db, chat_id, _cond("c2", {"level": "held",
                                               "by": "Tamamo"},
                                        subject="A"))
        _insert(temp_db, chat_id, _cond("c3", {"level": "pinned",
                                               "by": "Tamamo"},
                                        subject="B"))
        _insert(temp_db, chat_id, _cond("c4", {"level": "pinned"},
                                        subject="C"))
        standing = {r["subject"]: r["standing"]
                    for r in restraint_conditions(chat_id)}
        assert standing == {SUBJECT: True, "A": False, "B": False, "C": True}
        assert STANDING_RESTRAINTS == frozenset({"bound", "encased"})

    def test_several_rows_collapse_to_the_strongest(self, temp_db):
        """Live chat 80 carries six active restraint rows on one body --
        redescriptions of the same cuffs, one of which (`restraint_type:
        "bolted_chair"`, the NEWEST) has no readable rung. Restraints are
        additive facts, not exclusive states like awareness levels: a body
        is as restrained as the strongest thing on it, so a vague late
        redescription must not mask the cuffs."""
        chat_id = _chat(temp_db)
        _insert(temp_db, chat_id,
                _cond("early", {"restraint_type": "metal_cuffs"}, started=50.0))
        _insert(temp_db, chat_id,
                _cond("late", {"restraint_type": "bolted_chair"}, started=145.0))
        assert restraint_map(chat_id)["hinami"]["level"] == "bound"

    def test_the_beats_own_diff_is_in_force_the_same_beat(self, temp_db):
        records = apply_restraint_records_diff([], {"conditions": {"c1": [
            _cond("c1", {"level": "bound", "by": "Tamamo"})]}})
        assert len(records) == 1
        assert records[0]["level"] == "bound"
        assert restraint_of(records, SUBJECT)["by"] == "Tamamo"

    def test_an_ending_in_the_diff_releases_that_record_only(self, temp_db):
        chat_id = _chat(temp_db)
        _insert(temp_db, chat_id, _cond("c1", {"level": "bound"}))
        _insert(temp_db, chat_id, _cond("c2", {"level": "held", "by": "X"}))
        records = apply_restraint_records_diff(
            restraint_conditions(chat_id),
            {"conditions": {"c1": [_cond("c1", {"level": "bound"}, active=0)]}})
        assert [r["condition_id"] for r in records] == ["c2"]

    def test_readers_fail_open(self, temp_db):
        chat_id = _chat(temp_db)
        assert restraint_conditions(chat_id) == []
        assert restraint_map(chat_id) == {}
        assert restraint_of([], "Anyone") is None


# --- the movement floor: who a standing record actually stops ----------------

def _scene(**positions):
    rooms = {"cell": {"name": "Cell"}, "hall": {"name": "Hall"}}
    return {"rooms": rooms, "positions": dict(positions), "entities": {},
            "contained": {}}


class TestHolderAwareBlocking:
    def _blocked(self, sd, sc, records, amap=None, tracked=(SUBJECT, "Tamamo")):
        return [who for who, _record in _restraint_blocked_moves(
            sd, sc, records, amap or {}, list(tracked))]

    def _records(self, state, **kw):
        return apply_restraint_records_diff(
            [], {"conditions": {"c1": [_cond("c1", state, **kw)]}})

    def test_a_binding_blocks_with_nobody_attending_it(self):
        sc = _scene(Hinami="cell")
        records = self._records({"restraint_type": "metal_cuffs"})
        sd = {"positions": {SUBJECT: "hall"}}
        assert self._blocked(sd, sc, records) == [SUBJECT]

    def test_a_live_hold_blocks_while_the_holder_is_there(self):
        sc = _scene(Hinami="cell", Tamamo="cell")
        records = self._records({"level": "held", "by": "Tamamo"})
        sd = {"positions": {SUBJECT: "hall"}}
        assert self._blocked(sd, sc, records) == [SUBJECT]

    def test_a_hold_whose_holder_left_blocks_nobody(self):
        sc = _scene(Hinami="cell", Tamamo="hall")
        records = self._records({"level": "held", "by": "Tamamo"})
        sd = {"positions": {SUBJECT: "hall"}}
        assert self._blocked(sd, sc, records) == []

    def test_a_hold_whose_holder_is_out_cold_blocks_nobody(self):
        sc = _scene(Hinami="cell", Tamamo="cell")
        records = self._records({"level": "held", "by": "Tamamo"})
        sd = {"positions": {SUBJECT: "hall"}}
        amap = {"tamamo": {"subject": "Tamamo", "level": "unconscious",
                           "cause": "", "rousable_by": "",
                           "condition_id": "a1"}}
        assert self._blocked(sd, sc, records, amap=amap) == []

    def test_a_hold_naming_no_holder_blocks_nobody(self):
        """The live embrace rows (chats 50/51) and the lever grip (57/58)
        name no holder in any holder field. A hold is a two-body relation;
        missing its other endpoint, the record is context for the Director,
        never a floor."""
        sc = _scene(Hinami="cell")
        records = self._records({"type": "held_in_embrace"})
        sd = {"positions": {SUBJECT: "hall"}}
        assert self._blocked(sd, sc, records) == []

    def test_the_holder_is_found_inside_a_longer_phrase(self):
        """Live rows write `enveloped_by: "Elyndra's entrance"` and
        `restrained_by: "Dr. Moon's hand"` -- the holder is named inside a
        phrase, not as a bare name."""
        sc = _scene(Hinami="cell", Elyndra="cell")
        records = self._records({"type": "held", "enveloped_by":
                                 "Elyndra's entrance"})
        sd = {"positions": {SUBJECT: "hall"}}
        assert self._blocked(sd, sc, records,
                             tracked=(SUBJECT, "Elyndra")) == [SUBJECT]

    def test_being_carried_while_bound_is_the_restrainer_moving_them(self):
        sc = _scene(Hinami="cell")
        sc["contained"] = {SUBJECT: {"holder": "Tamamo"}}
        records = self._records({"level": "bound"})
        sd = {"positions": {SUBJECT: "hall"}}
        assert self._blocked(sd, sc, records) == []

    def test_a_move_that_is_no_move_is_not_blocked(self):
        sc = _scene(Hinami="cell")
        records = self._records({"level": "bound"})
        sd = {"positions": {SUBJECT: "cell"}}
        assert self._blocked(sd, sc, records) == []

    def test_a_record_ended_this_beat_no_longer_blocks(self):
        sc = _scene(Hinami="cell")
        sd = {"positions": {SUBJECT: "hall"},
              "conditions": {"c1": [_cond("c1", {"level": "bound"},
                                          active=0)]}}
        chat_records = self._records({"level": "bound"})
        records = apply_restraint_records_diff(chat_records, sd)
        assert self._blocked(sd, sc, records) == []
