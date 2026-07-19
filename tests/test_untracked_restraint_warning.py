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
