"""Regression test for the second-round character-result overwrite
(AUDIT_FINDINGS #19 / MEDIUM).

agents/loops.py's interaction_loop did `ctx.character_results[speaker_id] =
result` each round, so a character who spoke in more than one micro-round had
its earlier round's result (sequence, mind_model_updates, relationship_updates,
etc.) silently discarded before commit -- which reads
ctx.character_results[id] as that character's single result.

Fix: agents.common._merge_character_results concatenates the sequence and
unions the accumulating update fields, keeping the latest active_state.
"""

from __future__ import annotations

from agents.common import _merge_character_results


def _round0():
    return {
        "sequence": [{"type": "action", "attempt": "draws a blade"}],
        "mind_model_updates": [{"about_entity": "Kael", "kind": "goal", "claim": "flee"}],
        "relationship_updates": [{"target": "Kael", "trust": -0.1}],
        "active_state": {"mood": "tense"},
    }


def _round1():
    return {
        "sequence": [{"type": "speech", "text": "Stand down."}],
        "mind_model_updates": [{"about_entity": "Mara", "kind": "goal", "claim": "help"}],
        "relationship_updates": [{"target": "Mara", "trust": 0.2}],
        "active_state": {"mood": "resolved"},
    }


def test_merge_preserves_round0_sequence_and_updates():
    merged = _merge_character_results(_round0(), _round1())

    attempts = [e.get("attempt") for e in merged["sequence"] if e.get("type") == "action"]
    texts = [e.get("text") for e in merged["sequence"] if e.get("type") == "speech"]
    assert "draws a blade" in attempts  # round-0 action survived
    assert "Stand down." in texts       # round-1 speech present

    about = {u["about_entity"] for u in merged["mind_model_updates"]}
    assert about == {"Kael", "Mara"}    # both rounds' inferences kept

    targets = {u["target"] for u in merged["relationship_updates"]}
    assert targets == {"Kael", "Mara"}

    # Latest active_state wins.
    assert merged["active_state"] == {"mood": "resolved"}


def test_merge_dedupes_identical_repeated_updates():
    a = {"sequence": [], "mind_model_updates": [{"about_entity": "Kael", "kind": "goal", "claim": "flee"}]}
    b = {"sequence": [], "mind_model_updates": [{"about_entity": "Kael", "kind": "goal", "claim": "flee"}]}

    merged = _merge_character_results(a, b)

    assert len(merged["mind_model_updates"]) == 1


def test_merge_falls_back_to_existing_active_state_when_new_lacks_it():
    a = {"sequence": [], "active_state": {"mood": "tense"}}
    b = {"sequence": []}

    merged = _merge_character_results(a, b)

    assert merged["active_state"] == {"mood": "tense"}


def test_merge_tolerates_missing_existing():
    b = {"sequence": [{"type": "speech", "text": "hi"}]}
    assert _merge_character_results(None, b) == b
