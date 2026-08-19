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

from story.scene import RESTRAINT_LEVELS, _normalize_restraint_level


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
