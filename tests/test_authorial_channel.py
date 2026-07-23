"""Regression tests for the authorial channel (P3).

Live bug (Elevator Adventure, turn 20): the player typed "Dr. Moon remembers
she has her smartphone." The Director encoded it as an ASSERTED action
attributed to Dr. Moon (verb 'remember', targets [25]) -- the player authoring
an NPC's interior cognition, accepted as objective truth, pre-scripting her
agency. Fix: a mental-verb beat whose grammatical SUBJECT is a sheeted cast
member is rerouted to an OFFER handed to that character's own agent, and
dropped from the resolved sequence.
"""

from __future__ import annotations

import json
import types

from agents.director import _route_authorial_npc_cognition


def _ctx(cast):
    warnings = []
    return types.SimpleNamespace(
        cast=cast, add_warning=warnings.append, _warnings=warnings)


def _cast(names_ids):
    rows = []
    for name, cid in names_ids:
        rows.append({"id": cid, "sheet": json.dumps(
            {"core": {"name": name}, "identity": {"name": name}})})
    return rows


def _act(attempt, verb, targets=()):
    # Normalized action element shape (norm_sequence runs before the router).
    return {"type": "action", "attempt": attempt, "verb": verb,
            "observable": attempt, "visibility": "overt", "conceal_from": [],
            "targets": list(targets), "commitment": "asserted",
            "stage": "immediate", "intended_effects": [], "asserted_effects": []}


def test_npc_cognition_rerouted_to_offer():
    cast = _cast([("Dr. Moon", 25)])
    ctx = _ctx(cast)
    out = {"sequence": [
        _act("Dr. Moon remembers she has her smartphone", "remember", [25])]}
    _route_authorial_npc_cognition(ctx, out)
    # dropped from the enacted sequence...
    assert out["sequence"] == []
    # ...and delivered as an offer for cast 25
    assert out["authorial_offers"] == [
        {"subject_id": 25, "proposition": "Dr. Moon remembers she has her smartphone",
         "source": "player"}]
    assert ctx._warnings  # surfaced


def test_player_self_recall_untouched():
    """'remember the runes her mother taught her' -- the PLAYER's own recall,
    subject is the player, not a cast member: must stay a pc_action."""
    cast = _cast([("Dr. Moon", 25)])
    ctx = _ctx(cast)
    out = {"sequence": [
        _act("remember the runes her mother taught her", "recall")]}
    _route_authorial_npc_cognition(ctx, out)
    assert len(out["sequence"]) == 1
    assert out.get("authorial_offers", []) == []


def test_physical_npc_action_not_an_offer():
    """A physical beat about an NPC ('Dr. Moon steps back') is not interior
    cognition -- it is not rerouted (world/perception handle it normally)."""
    cast = _cast([("Dr. Moon", 25)])
    ctx = _ctx(cast)
    out = {"sequence": [
        _act("Dr. Moon steps back from the panel", "step", [25])]}
    _route_authorial_npc_cognition(ctx, out)
    assert len(out["sequence"]) == 1
    assert out.get("authorial_offers", []) == []


def test_recall_about_npc_not_rerouted():
    """'I remember Dr. Moon's face' -- subject is the player recalling something
    ABOUT the NPC; the NPC is not the subject, so it is not an offer."""
    cast = _cast([("Dr. Moon", 25)])
    ctx = _ctx(cast)
    out = {"sequence": [
        _act("I remember Dr. Moon's face from the file", "recall", [25])]}
    _route_authorial_npc_cognition(ctx, out)
    assert len(out["sequence"]) == 1
    assert out.get("authorial_offers", []) == []
