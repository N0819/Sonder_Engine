"""Regression tests for who an authored outcome is attributed to.

Live bug: a player input mixing their own act with an outcome authored for
another character ("...braces herself. <Character> is finally pushed over the
edge") produced a second action element in the PLAYER's sequence with empty
`targets` and null effect `target_id`. Three seams then failed together:

  * every seam that asks "does this act land on another body?" reads `targets`,
    so the unbound element was invisible to all of them -- no reaction phase
    ran for the character whose body the outcome was asserted on;
  * the claim-subject fallback reads "no targets" as "self-directed" and
    stamped the PLAYER as the subject of the other character's outcome;
  * `observable` is authored subject-free because the engine prepends the actor
    label, and the actor of a player-sequence element is the player -- so the
    outcome was delivered to every observer, and to the narrator, as the
    player's own.

These cover the deterministic repairs; the reroute itself lives in
tests/test_authorial_channel.py.
"""

from __future__ import annotations

from agents.common import (
    _extract_authority_claims,
    _requires_reaction_phase,
    bind_sequence_targets,
)

FORMS = {"Dr. Moon": ["dr. moon", "moon"]}


def _act(attempt, **over):
    elem = {"type": "action", "attempt": attempt, "verb": "",
            "observable": attempt, "targets": [], "commitment": "contestable",
            "stage": "immediate", "intended_effects": [],
            "asserted_effects": []}
    elem.update(over)
    return elem


# --- target binding ---------------------------------------------------------

def test_unbound_act_binds_the_character_its_text_names():
    seq = [_act("the mounting strain finally pushes Dr. Moon over the edge",
                intended_effects=[{"target_id": None, "kind": "she breaks"}])]
    assert bind_sequence_targets(seq, FORMS) == 1
    assert seq[0]["targets"] == ["Dr. Moon"]
    # The effect's null target_id is deliberately LEFT null. A name in the text
    # is evidence the act concerns that character, which is all `targets`
    # claims; `target_id` is the stronger claim that the outcome LANDS on them,
    # and inferring it from the same mention manufactured authority claims the
    # director never authored -- 'dodge away from Sarah' does not put an effect
    # on Sarah, but the mirroring said it did, and _requires_reaction_phase then
    # spent a reaction step contesting it. _extract_authority_claims reads the
    # same name evidence through its own target_forms guard instead.
    assert seq[0]["intended_effects"][0]["target_id"] is None


def test_binding_never_overwrites_what_the_director_bound():
    seq = [_act("shoves Dr. Moon", targets=["Someone Else"])]
    assert bind_sequence_targets(seq, FORMS) == 0
    assert seq[0]["targets"] == ["Someone Else"]


def test_binding_ignores_acts_naming_nobody():
    seq = [_act("braces rigidly against the wall")]
    assert bind_sequence_targets(seq, FORMS) == 0
    assert seq[0]["targets"] == []


def test_effect_target_is_not_guessed_when_two_characters_are_named():
    seq = [_act("steps between Dr. Moon and Vale",
                intended_effects=[{"target_id": None, "kind": "separated"}])]
    forms = dict(FORMS, Vale=["vale"])
    assert bind_sequence_targets(seq, forms) == 1
    assert sorted(seq[0]["targets"]) == ["Dr. Moon", "Vale"]
    assert seq[0]["intended_effects"][0]["target_id"] is None


# --- reaction gate ----------------------------------------------------------

def test_non_violent_contested_outcome_earns_a_reaction():
    """The gate used to require a verb from a combat whitelist, so a character
    could not contest anything that was not an attack."""
    event = _act("presses the grip tighter", targets=["Dr. Moon"],
                 intended_effects=[{"target_id": "Dr. Moon", "kind": "held"}])
    assert _requires_reaction_phase(event, {25}, {"dr. moon"}) is True


def test_asserted_acts_still_skip_the_reaction_phase():
    event = _act("presses the grip tighter", targets=["Dr. Moon"],
                 commitment="asserted",
                 intended_effects=[{"target_id": "Dr. Moon", "kind": "held"}])
    assert _requires_reaction_phase(event, {25}, {"dr. moon"}) is False


def test_untargeted_acts_still_skip_the_reaction_phase():
    event = _act("braces rigidly against the wall",
                 intended_effects=[{"target_id": None, "kind": "steady"}])
    assert _requires_reaction_phase(event, {25}, {"dr. moon"}) is False


def test_effectless_gesture_at_a_character_does_not_summon_a_reaction():
    event = _act("waves at Dr. Moon", targets=["Dr. Moon"])
    assert _requires_reaction_phase(event, {25}, {"dr. moon"}) is False


# --- claim subject ----------------------------------------------------------

def test_outcome_about_another_character_is_not_claimed_for_the_player():
    seq = [_act("the mounting strain finally pushes Dr. Moon over the edge",
                intended_effects=[{"target_id": None, "kind": "she breaks"}])]
    claims = _extract_authority_claims(
        seq, "raw", actor_name="Ash", target_forms=FORMS)
    assert [c["subject_id"] for c in claims] == ["Dr. Moon"]


def test_the_players_own_body_still_resolves_to_the_player():
    seq = [_act("goes rigid",
                intended_effects=[{"target_id": None, "kind": "braced"}])]
    claims = _extract_authority_claims(
        seq, "raw", actor_name="Ash", target_forms=FORMS)
    assert [c["subject_id"] for c in claims] == ["Ash"]


def test_an_explicit_effect_target_always_wins():
    seq = [_act("goes rigid",
                intended_effects=[{"target_id": "Vale", "kind": "braced"}])]
    claims = _extract_authority_claims(
        seq, "raw", actor_name="Ash", target_forms=FORMS)
    assert [c["subject_id"] for c in claims] == ["Vale"]
