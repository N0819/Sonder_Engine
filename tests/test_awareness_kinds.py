"""Four spellings of unconsciousness, and the gate read one.

`awareness_map` selected `kind='awareness'` only. Measured read-only against
the owner's live engine.db (2026-08-18): 9 active rows carry a KIND of
`unconscious` (6), `asleep` (1), `sleep` (1) or `consciousness` (1) with an
EMPTY state -- the model filed the level in the kind slot, exactly the
spelling-drift class the restraint selector had (`physical_restraint` vs
`restraint`). Chats 24 and 25 hold `unconscious` rows on subjects with no
canonical awareness row at all, so those minds read as awake against a story
that knocked them out.

The previous agent declined to widen this, reasoning that reading the level
off the kind word is an inference and that gating a mind wrongly costs more
than not gating it. Both halves deserve an answer:

* It is not an inference when the kind IS a level word. `unconscious` names
  exactly one awareness level; reading it is reading, the same way
  `physical_restraint` is a restraint. What would be inference -- and stays
  unread -- is a kind that merely orbits the topic: `consciousness` names
  the faculty, not a state of it (the live row is `partial_consciousness`,
  a body coming to), and `preparing_for_sleep` is a body still awake
  arranging a futon. Hence WHOLE-KIND matching, never word-splitting:
  `preparing_for_sleep` contains the word `sleep` and must not match.
* The cost asymmetry was real when a gate had no exit. The exits landed
  first (`_awareness_exits`): a wrongly-gated player is freed by their own
  next declaration, a sleeper by a rouse or the clock, and every widened
  row now reaches the Director each beat with the condition_id an ending
  must re-emit.

Measured impact of widening, row by row: chats 23/27 unchanged (their
kind-spelled rows are OLDER than canonical dazed rows, and newest-wins
keeps dazed); chats 24/25 unchanged today (their subjects are branch uids
no perceiver name matches -- a separate identity gap, not this one's to
widen into); chat 40 gates the player one beat until their next input ends
it; chat 44 the same. Nothing else in the corpus matches.
"""

from __future__ import annotations

import json
import time

from agents.director import (
    _awareness_exits,
    _unsupported_player_awareness,
    _untracked_unconsciousness_subjects,
)
from persist.commit_entities import _is_gated_awareness
from story.scene import (
    apply_awareness_diff,
    awareness_conditions,
    awareness_kind_level,
    awareness_map,
    awareness_of,
)

SUBJECT = "Hinami"


def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Kinds", "", time.time()))


def _insert(db, chat_id, cond_id, kind, state, subject=SUBJECT,
            started=100.0, active=1, extra=None):
    payload = {"condition_id": cond_id, "subject_id": subject, "kind": kind,
               "state": state, "started_at_seconds": started}
    payload.update(extra or {})
    db.qi(
        "INSERT INTO world_conditions(condition_id,chat_id,subject_id,kind,"
        "started_at,expires_at,next_tick,payload,active) "
        "VALUES(?,?,?,?,?,?,?,?,?)",
        (cond_id, chat_id, subject, kind, started, None, None,
         json.dumps(payload), active))


# --- the predicate ----------------------------------------------------------

class TestAwarenessKindLevel:
    def test_a_kind_that_is_a_level_word_asserts_that_level(self):
        assert awareness_kind_level("unconscious") == "unconscious"
        assert awareness_kind_level("asleep") == "asleep"
        assert awareness_kind_level("sleep") == "asleep"
        assert awareness_kind_level("sleeping") == "asleep"
        assert awareness_kind_level("sedated") == "sedated"
        assert awareness_kind_level("knocked_out") == "unconscious"

    def test_the_canonical_kind_defers_to_state(self):
        assert awareness_kind_level("awareness") == ""

    def test_a_kind_that_orbits_the_topic_is_not_a_level(self):
        """`consciousness` names the faculty (the live row records a body
        COMING TO); `preparing_for_sleep` is a body awake at a futon. A
        word-split match would read the second as asleep."""
        assert awareness_kind_level("consciousness") is None
        assert awareness_kind_level("preparing_for_sleep") is None
        assert awareness_kind_level("posture") is None
        assert awareness_kind_level("") is None


# --- the readers ------------------------------------------------------------

class TestWidenedReaders:
    def test_the_live_spelling_gates_and_is_endable(self, temp_db):
        """The chat-24 shape: kind='unconscious', state={}, no canonical
        row anywhere. The mind must gate, and the record must carry the
        condition_id an ending re-emits."""
        chat_id = _chat(temp_db)
        _insert(temp_db, chat_id, "c1", "unconscious", {},
                extra={"severity": "moderate"})
        records = awareness_conditions(chat_id)
        assert len(records) == 1
        assert records[0]["level"] == "unconscious"
        assert records[0]["condition_id"] == "c1"
        assert awareness_of(awareness_map(chat_id), SUBJECT) == "unconscious"

    def test_an_explicit_state_level_outranks_the_kind_word(self, temp_db):
        chat_id = _chat(temp_db)
        _insert(temp_db, chat_id, "c1", "unconscious", {"level": "dazed"})
        assert awareness_conditions(chat_id)[0]["level"] == "dazed"

    def test_a_newer_canonical_row_still_wins(self, temp_db):
        """The chat-23/27 shape: a kind-spelled `unconscious` row at 130s
        under canonical rows ending in dazed at 185s. Newest-wins already
        answered this body; widening must not change it."""
        chat_id = _chat(temp_db)
        _insert(temp_db, chat_id, "c1", "unconscious", {}, started=130.0)
        _insert(temp_db, chat_id, "c2", "awareness",
                {"level": "dazed", "cause": "recovery"}, started=185.0)
        assert awareness_of(awareness_map(chat_id), SUBJECT) == "dazed"

    def test_the_diff_side_reads_the_same_family(self):
        diff = {"conditions": {"c1": [{
            "condition_id": "c1", "subject_id": SUBJECT,
            "kind": "unconscious", "state": {}}]}}
        assert awareness_of(apply_awareness_diff({}, diff), SUBJECT) \
            == "unconscious"

    def test_preparing_for_sleep_gates_nothing(self, temp_db):
        """The live chat-59 row, verbatim shape."""
        chat_id = _chat(temp_db)
        _insert(temp_db, chat_id, "sleep_preparation", "preparing_for_sleep",
                {"status": "beginning",
                 "detail": "preparing for sleep on futon"})
        assert awareness_conditions(chat_id) == []
        assert awareness_of(awareness_map(chat_id), SUBJECT) == "awake"

    def test_consciousness_gates_nothing(self, temp_db):
        """The live chat-44 row: `hinami_partial_consciousness`, empty
        state. Whether that body is under is not decidable from the word,
        so the mind stays present (fail-open)."""
        chat_id = _chat(temp_db)
        _insert(temp_db, chat_id, "hinami_partial_consciousness",
                "consciousness", {})
        assert awareness_conditions(chat_id) == []


# --- the floors run on the widened family -----------------------------------

class TestFloorsOnWidenedKinds:
    def test_the_player_floor_drops_an_unsupported_kind_spelled_gate(self):
        """The chat-40 shape, onset side: a diff putting the player under
        as kind='asleep' with nothing in the beat supporting it."""
        conditions = {"c1": [{
            "condition_id": "c1", "subject_id": SUBJECT, "kind": "asleep",
            "state": {}}]}
        dropped = _unsupported_player_awareness(
            conditions, SUBJECT, "I look around the room.", "", [])
        assert dropped == [("c1", "asleep")]

    def test_a_kind_spelled_row_covers_its_subject_in_the_omission_scan(self):
        """A diff that DID record the knockout, spelled `unconscious`, must
        not be flagged as an omission of itself."""
        conditions = {"c1": [{
            "condition_id": "c1", "subject_id": SUBJECT,
            "kind": "unconscious", "state": {}}]}
        flagged = _untracked_unconsciousness_subjects(
            f"{SUBJECT} is knocked out cold by the blast.", [], conditions,
            [SUBJECT])
        assert flagged == []

    def test_the_player_declaration_exit_ends_a_kind_spelled_sleep(self, temp_db):
        """The chat-40 escape hatch, end to end: the row that has gated the
        player for turns is spelled kind='asleep'; their next declaration
        ends it under its own condition_id, and the ending -- which keeps
        the row's own kind -- reads back as awake."""
        chat_id = _chat(temp_db)
        _insert(temp_db, chat_id, "hinami_asleep", "asleep", {},
                subject="hinami")
        records = awareness_conditions(chat_id)
        endings, warnings = _awareness_exits(
            chat_id, records, "hinami", "I get up and look around.",
            {}, {}, "", {}, None)
        assert "hinami_asleep" in endings
        assert endings["hinami_asleep"][0]["active"] == 0
        assert endings["hinami_asleep"][0]["kind"] == "asleep"
        amap = apply_awareness_diff(awareness_map(chat_id),
                                    {"conditions": endings})
        assert awareness_of(amap, "hinami") == "awake"
        assert warnings

    def test_commit_side_gate_recognises_the_family(self):
        assert _is_gated_awareness({
            "kind": "unconscious", "active": 1, "state": {}}) is True
        assert _is_gated_awareness({
            "kind": "preparing_for_sleep", "active": 1, "state": {}}) is False
        assert _is_gated_awareness({
            "kind": "awareness", "active": 1,
            "state": {"level": "dazed"}}) is False
