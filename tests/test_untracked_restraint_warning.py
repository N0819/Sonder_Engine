"""Regression test for the director_resolve restraint/duress backstop.

Bug: a physically consequential state (a character held at gunpoint) got
established via narration but was never written to state_diff.conditions,
despite director_resolve's own prompt instructing conditions to be
recorded -- because the prompt's example list never named restraint/duress,
and nothing deterministic caught the omission.

Fix: agents/director.py's _scan_for_untracked_restraint is a deterministic,
WARN-ONLY backstop -- it never synthesizes a condition (a wrongly invented
restraint tag lingering is worse than a stale missing one), it only flags
the mismatch via ctx.warnings so a human/downstream pass can notice.
"""

from __future__ import annotations

from agents.director import _scan_for_untracked_restraint


def test_warns_when_restraint_mentioned_but_no_matching_condition():
    resolved_event = "The guard pins Reya against the wall, held at gunpoint."
    dialogue_log = [
        {"speaker": "Guard", "exact_quote": '"Don\'t move."'},
    ]
    conditions = {}
    tracked_names = ["Reya", "Player"]

    warnings = _scan_for_untracked_restraint(
        resolved_event, dialogue_log, conditions, tracked_names,
    )

    assert len(warnings) == 1
    assert "Reya" in warnings[0]


def test_no_warning_when_matching_condition_already_recorded():
    resolved_event = "The guard pins Reya against the wall, held at gunpoint."
    dialogue_log = []
    conditions = {
        "cond_1": {
            "subject_id": "Reya",
            "kind": "restrained",
            "severity": "moderate",
        },
    }
    tracked_names = ["Reya", "Player"]

    warnings = _scan_for_untracked_restraint(
        resolved_event, dialogue_log, conditions, tracked_names,
    )

    assert warnings == []


def test_no_warning_on_clean_text_with_no_restraint_keywords():
    resolved_event = "Reya crosses the room and opens the hatch."
    dialogue_log = [
        {"speaker": "Reya", "exact_quote": '"Almost there."'},
    ]
    conditions = {}
    tracked_names = ["Reya", "Player"]

    warnings = _scan_for_untracked_restraint(
        resolved_event, dialogue_log, conditions, tracked_names,
    )

    assert warnings == []


def test_warning_detected_from_dialogue_log_quote_not_just_resolved_event():
    resolved_event = "The confrontation escalates."
    dialogue_log = [
        {"speaker": "Guard", "exact_quote": '"Reya is my hostage now."'},
    ]
    conditions = {}
    tracked_names = ["Reya", "Player"]

    warnings = _scan_for_untracked_restraint(
        resolved_event, dialogue_log, conditions, tracked_names,
    )

    assert len(warnings) == 1
    assert "Reya" in warnings[0]


# --- the level ladder, and the words a model actually writes ----------------
#
# `RESTRAINT_LEVELS` is `held | bound | pinned | encased`, and no prompt
# anywhere publishes it. What the body specialist is told is a parenthetical
# of EXAMPLES -- "physical restraint (bound, held hostage, grappled, pinned)"
# -- with no `level in {...}` clause of the kind awareness gets one paragraph
# later in the same sheet. `encased` appears in no prompt at all.
#
# `_normalize_restraint_level` then folded anything it could not read to
# `held`, the mildest rung, so two of the prompt's own examples ("grappled",
# "held hostage") arrived as the weakest reading of themselves. AGENTS.md
# states the rule for exactly this shape, in the weather vocabulary: extend
# the synonyms rather than widening the enum, because a silent fall to the
# default inverts the meaning of the beat.

import json
import time

from story.scene import (
    IMMOBILIZING_RESTRAINTS,
    RESTRAINT_LEVELS,
    _normalize_restraint_level,
    apply_restraint_diff,
    restraint_map,
    restraint_of,
)


class TestRestraintWordsTheEnumCannotRead:
    def test_the_prompts_own_examples_are_readable(self):
        assert _normalize_restraint_level("grappled") == "pinned"
        assert _normalize_restraint_level("held hostage") == "held"

    def test_a_binding_by_any_of_its_names(self):
        for word in ("tied", "tied up", "roped", "shackled", "manacled",
                     "handcuffed", "cuffed", "chained", "fettered", "trussed",
                     "restrained"):
            assert _normalize_restraint_level(word) == "bound", word

    def test_a_body_held_down_by_another_body(self):
        for word in ("pinned down", "straddled", "immobilised", "immobilized",
                     "trapped", "crushed"):
            assert _normalize_restraint_level(word) == "pinned", word

    def test_a_body_closed_inside_something(self):
        for word in ("encased", "entombed", "sealed", "cocooned", "engulfed",
                     "swallowed", "buried"):
            assert _normalize_restraint_level(word) == "encased", word

    def test_a_hand_on_an_arm(self):
        for word in ("grabbed", "grasped", "gripped", "clutched", "clamped"):
            assert _normalize_restraint_level(word) == "held", word

    def test_a_phrase_is_read_by_the_word_it_contains(self):
        """A model writes a sentence where the schema asked for a token."""
        assert _normalize_restraint_level("bound hand and foot") == "bound"
        assert _normalize_restraint_level("pinned beneath the beam") == "pinned"
        assert _normalize_restraint_level("sealed inside the sarcophagus") == "encased"

    def test_the_enum_itself_still_answers_for_itself(self):
        for level in RESTRAINT_LEVELS:
            assert _normalize_restraint_level(level) == level

    def test_a_word_nothing_recognises_still_restrains(self):
        """Fail-mild, deliberately: a body the story says is restrained stays
        restrained. Only the RUNG is guessed, and the mildest rung is the
        one that claims least."""
        assert _normalize_restraint_level("flabbergasted") == "held"
        assert _normalize_restraint_level("") == "bound"


# --- the kind a beat actually writes ---------------------------------------
#
# THE FLOOR HAS NEVER FIRED. `restraint_map` selects
# `kind='restraint'`; measured over the live database, no beat has ever
# written that word. What the Director writes is `physical_restraint` (21
# active rows) or `restrained` (3), across fifteen chats -- so the
# enforcement built because "a character recorded as bound hand and foot
# could still walk across the room" has not blocked a single move since it
# landed.
#
# `world_conditions.kind` is free model text: no prompt publishes a
# vocabulary for it, and what the body specialist is told is "physical
# restraint (bound, held hostage, grappled, pinned)" -- prose, from which
# `physical_restraint` is the obvious token, and which matches the engine's
# own `physical_disguise` / `physical_transformation` besides. The model
# wrote the consistent name; the reader asked for the inconsistent one.
#
# Nor do those rows carry `state.level`. They carry `restraint_type`
# ("metal_cuffs", "chair_restraints") or `type` ("grip", "held_in_embrace"),
# which is where the rung has to be read from.

class TestTheKindsRestraintIsActuallyRecordedUnder:
    def _chat(self, db):
        return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Restraint", "", time.time()))

    def _row(self, db, chat_id, cond_id, kind, state, started_at=100.0,
             subject="Hinami"):
        db.qi(
            "INSERT INTO world_conditions(condition_id,chat_id,subject_id,kind,"
            "started_at,expires_at,next_tick,payload,active) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (cond_id, chat_id, subject, kind, started_at, None, None,
             json.dumps({"subject_id": subject, "kind": kind, "state": state}), 1))

    def test_the_spelling_every_live_row_uses_is_read(self, temp_db):
        chat_id = self._chat(temp_db)
        self._row(temp_db, chat_id, "c1", "physical_restraint",
                  {"restraint_type": "metal_cuffs"})

        record = restraint_of(restraint_map(chat_id), "Hinami")
        assert record is not None
        assert record["level"] in IMMOBILIZING_RESTRAINTS

    def test_the_other_live_spelling_too(self, temp_db):
        chat_id = self._chat(temp_db)
        self._row(temp_db, chat_id, "c1", "restrained",
                  {"description": "Pinned to her side by a hand on her arm"})

        assert restraint_of(restraint_map(chat_id), "Hinami") is not None

    def test_a_condition_that_is_not_restraint_is_not_read_as_one(self, temp_db):
        """The predicate widens to a family of spellings, not to anything
        that has a body in it. Containment and contact are their own
        systems with their own consequences."""
        chat_id = self._chat(temp_db)
        self._row(temp_db, chat_id, "c1", "containment", {"level": "bound"})
        self._row(temp_db, chat_id, "c2", "contact", {}, subject="Kaede")
        self._row(temp_db, chat_id, "c3", "wound", {}, subject="Moon")

        assert restraint_map(chat_id) == {}

    def test_the_rung_is_read_from_the_field_the_beat_used(self, temp_db):
        chat_id = self._chat(temp_db)
        self._row(temp_db, chat_id, "c1", "physical_restraint",
                  {"restraint_type": "metal_cuffs"})
        assert restraint_map(chat_id)["hinami"]["level"] == "bound"

        chat_two = self._chat(temp_db)
        self._row(temp_db, chat_two, "c2", "physical_restraint",
                  {"type": "grip"})
        assert restraint_map(chat_two)["hinami"]["level"] == "held"

    def test_an_underscored_token_is_still_words(self, temp_db):
        """Models write `wrist_and_ankle_restraints_on_metal_chair`. An
        underscore is a word character to a regex, so a cue table matching
        on word boundaries reads that as one unknown word."""
        assert _normalize_restraint_level(
            "wrist_and_ankle_restraints_on_metal_chair") == "bound"
        assert _normalize_restraint_level("held_in_embrace") == "held"

    def test_several_rows_collapse_in_the_story_order(self, temp_db):
        """Live chat 80 carries six active restraint rows on one body. With
        no ORDER BY at all, which one described the subject was the scan's
        choice."""
        chat_id = self._chat(temp_db)
        self._row(temp_db, chat_id, "late", "physical_restraint",
                  {"restraint_type": "metal_cuffs"}, started_at=500.0)
        self._row(temp_db, chat_id, "early", "physical_restraint",
                  {"type": "grip"}, started_at=100.0)

        assert restraint_map(chat_id)["hinami"]["level"] == "bound"

    def test_the_same_beats_own_diff_is_read_the_same_way(self, temp_db):
        """`apply_restraint_diff` overlays this beat's not-yet-committed
        conditions, and asked for the same one token the query did."""
        diff = {"conditions": {"c1": [{
            "condition_id": "c1", "subject_id": "Hinami",
            "kind": "physical_restraint",
            "state": {"restraint_type": "chair_restraints"}}]}}
        assert restraint_of(apply_restraint_diff({}, diff), "Hinami") is not None
