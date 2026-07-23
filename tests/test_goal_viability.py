"""Regression tests for goal viability (P5).

Live bug (Elevator Adventure, turns 20-22): Dr. Moon kept serving intention i1
'reach the auxiliary shelter' even after she observed every corridor was
condemned and boarded (i1 now impossible). Nothing could mark an active goal
non-viable, so it steered her wants forever. Fix: a guarded `nonviable` intent
op sets a goal aside; engagement revives it.
"""

from __future__ import annotations

from affect import apply_intent_ops


def _intents():
    return [{"id": "i1", "intent": "reach the auxiliary shelter", "status": "active",
             "formed_turn": 0, "last_progress_turn": 0, "progress": 0.3}]


def _always_ok(op):
    return True


def test_nonviable_blocks_goal_with_why():
    ops = [{"op": "nonviable", "id": "i1",
            "why": "every corridor off the lobby is condemned and boarded"}]
    out, warns = apply_intent_ops(_intents(), ops, turn_idx=21, evidence_ok=_always_ok)
    i1 = next(i for i in out if i["id"] == "i1")
    assert i1["status"] == "blocked"
    assert "condemned" in i1["blocked_why"]


def test_nonviable_rejected_without_evidence():
    ops = [{"op": "nonviable", "id": "i1", "why": ""}]
    # evidence_ok mirrors commit's: no evidence and no why -> reject
    out, warns = apply_intent_ops(_intents(), ops, turn_idx=21,
                                  evidence_ok=lambda op: bool(op.get("why")))
    i1 = next(i for i in out if i["id"] == "i1")
    assert i1["status"] == "active"  # not blocked
    assert any("nonviable rejected" in w for w in warns)


def test_progress_revives_blocked_goal():
    blocked = [{"id": "i1", "intent": "reach the shelter", "status": "blocked",
                "blocked_why": "corridors boarded", "formed_turn": 0,
                "last_progress_turn": 21, "progress": 0.3}]
    ops = [{"op": "progress", "id": "i1"}]
    out, _ = apply_intent_ops(blocked, ops, turn_idx=25, evidence_ok=_always_ok)
    i1 = next(i for i in out if i["id"] == "i1")
    assert i1["status"] == "active"
    assert "blocked_why" not in i1


def test_blocked_goal_does_not_go_dormant_or_steer():
    blocked = [{"id": "i1", "intent": "x", "status": "blocked",
                "formed_turn": 0, "last_progress_turn": 0, "progress": 0.0}]
    out, _ = apply_intent_ops(blocked, [], turn_idx=100, evidence_ok=_always_ok)
    i1 = next(i for i in out if i["id"] == "i1")
    # stays blocked (not active), so it no longer steers; the dormant sweep
    # only touches active goals
    assert i1["status"] == "blocked"
