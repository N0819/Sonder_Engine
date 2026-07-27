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

from agents.director import _route_authorial_npc_beat


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
    _route_authorial_npc_beat(ctx, out)
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
    _route_authorial_npc_beat(ctx, out)
    assert len(out["sequence"]) == 1
    assert out.get("authorial_offers", []) == []


def test_physical_npc_action_not_an_offer():
    """A physical beat about an NPC ('Dr. Moon steps back') is not interior
    cognition -- it is not rerouted (world/perception handle it normally)."""
    cast = _cast([("Dr. Moon", 25)])
    ctx = _ctx(cast)
    out = {"sequence": [
        _act("Dr. Moon steps back from the panel", "step", [25])]}
    _route_authorial_npc_beat(ctx, out)
    assert len(out["sequence"]) == 1
    assert out.get("authorial_offers", []) == []


def test_recall_about_npc_not_rerouted():
    """'I remember Dr. Moon's face' -- subject is the player recalling something
    ABOUT the NPC; the NPC is not the subject, so it is not an offer."""
    cast = _cast([("Dr. Moon", 25)])
    ctx = _ctx(cast)
    out = {"sequence": [
        _act("I remember Dr. Moon's face from the file", "recall", [25])]}
    _route_authorial_npc_beat(ctx, out)
    assert len(out["sequence"]) == 1
    assert out.get("authorial_offers", []) == []


def test_npc_autonomous_response_rerouted_to_offer():
    """A character giving in is theirs to decide, exactly like a memory: an
    autonomous response authored FOR them is an offer, not an enacted fact."""
    cast = _cast([("Dr. Moon", 25)])
    ctx = _ctx(cast)
    out = {"sequence": [_act("Dr. Moon gives in and lowers the gun", "yield")]}
    _route_authorial_npc_beat(ctx, out)
    assert out["sequence"] == []
    assert out["authorial_offers"][0]["subject_id"] == 25


def test_indirectly_authored_npc_response_rerouted():
    """The same puppeting written with the character as OBJECT rather than
    leading subject -- the shape the leading-subject rule alone missed. Left in
    the player's sequence it would inherit the player as its actor, and be
    delivered to every observer as the PLAYER's own response."""
    cast = _cast([("Dr. Moon", 25)])
    ctx = _ctx(cast)
    out = {"sequence": [
        _act("the mounting strain finally pushes Dr. Moon over the edge",
             "break")]}
    _route_authorial_npc_beat(ctx, out, ["Ash"])
    assert out["sequence"] == []
    assert out["authorial_offers"][0]["subject_id"] == 25


def test_player_act_causing_a_response_is_still_the_players():
    """'shoves Dr. Moon until she gives in' names an autonomous outcome, but
    the PLAYER is its agent: it stays a pc_action and the character's response
    is adjudicated in the reaction phase, not pre-empted by an offer."""
    cast = _cast([("Dr. Moon", 25)])
    ctx = _ctx(cast)
    out = {"sequence": [
        _act("shoves Dr. Moon until she gives in", "shove", [25])]}
    _route_authorial_npc_beat(ctx, out, ["Ash"])
    assert len(out["sequence"]) == 1
    assert out.get("authorial_offers", []) == []


def test_player_named_subject_is_never_rerouted():
    """An attempt the player leads by their OWN name is theirs even when it
    names a character and an autonomous outcome."""
    cast = _cast([("Dr. Moon", 25)])
    ctx = _ctx(cast)
    out = {"sequence": [
        _act("Ash gives in and hands Dr. Moon the file", "yield")]}
    _route_authorial_npc_beat(ctx, out, ["ash"])
    assert len(out["sequence"]) == 1
    assert out.get("authorial_offers", []) == []


class TestAuthoredSubjectDoesNotEatPlayerActs:
    """The autonomy vocabulary is made of ordinary words on purpose ('relax',
    'agree', 'enjoy'), so scanning a whole attempt for them turned any sentence
    containing one into puppeting and DROPPED the player's declared act from
    the sequence -- the one thing AGENTS.md forbids the Director to do
    silently. The test is the clause the character is the subject of."""

    FORMS = {7: ["sarah"], 9: ["dr. moon", "moon"]}
    ACTOR = ["vorne"]

    def _subject(self, attempt, verb=None, **kw):
        from agents.common import authored_other_subject
        elem = {"type": "action", "attempt": attempt, "verb": verb, **kw}
        return authored_other_subject(elem, self.FORMS, self.ACTOR)

    # --- still caught: the cases the reroute exists for -------------------
    def test_name_led_cognition_is_rerouted(self):
        assert self._subject(
            "Dr. Moon remembers she has her smartphone") == 9

    def test_name_led_volition_is_rerouted(self):
        assert self._subject("Dr. Moon gives in") == 9

    def test_indirect_autonomous_outcome_is_rerouted(self):
        assert self._subject(
            "the strain finally pushes Dr. Moon over the edge") == 9

    def test_declared_mental_verb_on_a_name_led_beat_is_rerouted(self):
        assert self._subject("Sarah stares at the wall", verb="remember") == 7

    # --- no longer eaten: ordinary player acts ----------------------------
    def test_a_later_clause_about_the_player_does_not_reroute(self):
        """'enjoy' belongs to the player's clause, not Sarah's."""
        assert self._subject("Sarah steps back and I enjoy the view") is None

    def test_an_autonomy_word_before_the_name_does_not_reroute(self):
        assert self._subject(
            "her grip on the knife doesn't yield as I push against Sarah"
        ) is None

    def test_player_recall_about_a_character_is_not_rerouted(self):
        """The declared verb belongs to the leading noun here, not to Sarah --
        this is the player's own memory, and rerouting it handed Sarah an
        offer to have the player's thought."""
        assert self._subject("the way Sarah smiled", verb="remember") is None

    def test_a_physical_npc_beat_is_left_alone(self):
        assert self._subject("Dr. Moon steps back") is None

    def test_acting_on_someone_stays_the_players_act(self):
        assert self._subject("stabs Sarah") is None

    def test_an_unnamed_clause_is_left_alone(self):
        assert self._subject("the door swings shut and the lock catches") is None
