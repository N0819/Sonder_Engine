"""Regression tests for authored standing intentions + drive authoring.

Diagnosed from the Enterprise-D demo: NPC Captain Picard was passive because his
card gave the decision procedure nothing to be proactive with -- and, more
broadly, `drive` was authored by neither character generation nor the editor,
and authored standing goals (initial_state.goals) never reached the runtime
`intentions` the wants-derivation reads. Fix: character_standing_intentions
projects initial_state.goals into intention context, always present (merged with
emergent runtime intentions), so an authored character pursues its goals.
"""

from __future__ import annotations

from agents.character import _merge_standing_intentions
from character_schema import character_standing_intentions, default_character_data


def test_authored_goals_become_standing_intentions():
    sheet = default_character_data("Captain")
    sheet["initial_state"]["goals"] = [
        {"goal": "hold command of the crisis", "priority": 0.9},
        {"goal": "protect the ship", "priority": 0.8},
    ]
    si = character_standing_intentions(sheet)
    assert [i["intent"] for i in si] == ["hold command of the crisis", "protect the ship"]
    assert all(i["status"] == "active" and i["authored"] for i in si)
    assert si[0]["id"] == "ia1" and si[1]["id"] == "ia2"  # namespaced, no collision


def test_empty_goals_yield_no_intentions():
    sheet = default_character_data("Nobody")
    assert character_standing_intentions(sheet) == []


def test_merge_authored_and_emergent():
    authored = [{"id": "ia1", "intent": "hold command", "status": "active", "authored": True}]
    emergent = [{"id": "i1", "intent": "warn the away team", "status": "active"}]
    merged = _merge_standing_intentions(authored, emergent)
    assert [m["intent"] for m in merged] == ["hold command", "warn the away team"]


def test_emergent_supersedes_restated_authored():
    """An emergent intention restating an authored one wins -- it carries live
    status (e.g. blocked/nonviable), so a goal the world closed does not
    reappear as freshly active."""
    authored = [{"id": "ia1", "intent": "Reach the shelter", "status": "active", "authored": True}]
    emergent = [{"id": "i1", "intent": "reach the shelter", "status": "blocked"}]
    merged = _merge_standing_intentions(authored, emergent)
    assert len(merged) == 1
    assert merged[0]["status"] == "blocked"  # emergent copy wins
