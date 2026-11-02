"""A conflict or attempt cue is a WHOLE word of the act, never a piece of one.

`acts_awaiting_resolution` (behind `_requires_director_resolution`, which ENDS
THE BEAT in both interaction loops) and `_classify_action_commitment` (which
makes an act `contestable` wherever the Director omitted `commitment` -- every
promoted stage direction) tested their pack tables with `term in text`: a
SUBSTRING of free prose. "enter" fired inside "center", "stab" inside
"stable", "restrain" inside "restraint", "break" inside "breakfast", "rush"
inside "brushing", "try" inside "pastry".

Measured (agents_common audit F5, the owner's db read-only, 2,554 action
elements of the 2,500 most recent interaction_loop variants): 153 asserted,
overt acts ended the beat through `_CONFLICT_VERBS`, at least 52 of them (34%)
inside a longer word; the attempt cues' hosts were "brushing"/"brush"/"brushes"
36, "pastry" 10, "entry" 6, "claim" 6, "recharge"/"discharges" 4.

The cue tables are unchanged. The match is now a subset of the old one: the
cue must stand at a word's start, and a cue ending in a spaced script may
carry an inflection ("grabbing", "breaks", "casts" still fire) but no other
letters. An unspaced-script cue keeps its open edges, so Japanese is exactly
as before.
"""

from __future__ import annotations

import pytest

from language_runtime import language_scope

from agents import common



def _act(attempt, **extra):
    return {"sequence": [{"type": "action", "attempt": attempt, **extra}]}


IN_WORD_CONFLICT = [
    "eats breakfast by the window",
    "points to the center of the map",
    "reads the forecast aloud",
    "nods toward the castle",
    "keeps a stable footing on the deck",
    "shows the restraint of a soldier",
    "settles into an established routine",
    "keeps the guests entertaining themselves",
    "gives a forceful nod",
    "sits with interleaved fingers",
]


@pytest.mark.parametrize("attempt", IN_WORD_CONFLICT)
def test_a_cue_inside_a_longer_word_does_not_end_the_beat(attempt):
    assert not common._requires_director_resolution(_act(attempt)), attempt
    assert common.acts_awaiting_resolution(_act(attempt)) == []


WORD_CONFLICT = [
    "grab the guard",
    "grabbing the guard's wrist",
    "breaks the lock",
    "casts a spell at the door",
    "enters the vault",
    "leaves the room",
    "stabs at the shadow",
    "re-enters the hall",
]


@pytest.mark.parametrize("attempt", WORD_CONFLICT)
def test_a_cue_that_is_the_word_or_its_inflection_still_ends_it(attempt):
    assert common._requires_director_resolution(_act(attempt)), attempt


IN_WORD_ATTEMPT = [
    "brushes the crumbs from her sleeve",
    "brushing the hair from her eyes",
    "walks to the pantry",
    "sets a pastry on the plate",
    "smiles and claims a seat",
    "pauses at the entry",
    "recharges the lamp",
]


@pytest.mark.parametrize("text", IN_WORD_ATTEMPT)
def test_an_attempt_cue_inside_a_longer_word_keeps_the_act_asserted(text):
    assert common._classify_action_commitment(text) == "asserted", text


WORD_ATTEMPT = [
    "trying to pry the panel loose",
    "attempts to climb the wall",
    "aims the pistol at the door",
    "rushes the door",
    "reach for the pistol",
    "charges across the deck",
]


@pytest.mark.parametrize("text", WORD_ATTEMPT)
def test_an_attempt_cue_that_is_the_word_still_contests(text):
    assert common._classify_action_commitment(text) == "contestable", text


def test_a_reactive_verb_inside_a_longer_word_earns_no_reaction_phase():
    """The third substring test of the same tables, the reaction-phase gate's
    whitelist: a contestable act on a cast member with no declared effect.
    "steal" inside "stealthily" asked the target to contest a walk."""
    base = {"type": "action", "commitment": "contestable", "targets": [7]}
    walk = dict(base, attempt="moves stealthily toward Mira")
    assert not common._requires_reaction_phase(walk, {7}, {"mira"})
    steal = dict(base, attempt="steals the purse from Mira")
    assert common._requires_reaction_phase(steal, {7}, {"mira"})


def test_japanese_cues_fire_exactly_as_before():
    """An unspaced-script cue keeps its open edges: a Japanese verb is
    written straight onto its object's particle and carries its inflection
    on the same run, and nothing here says where a Japanese word ends."""
    with language_scope("ja"):
        assert common._requires_director_resolution(_act("衛兵を掴む"))
        assert common._requires_director_resolution(_act("扉を壊して中に入る"))
        assert common._classify_action_commitment("剣に手を伸ばす") == "contestable"
        assert not common._requires_director_resolution(_act("窓の外を眺める"))
        # The English alternatives the ja pack keeps for code-switched text
        # take the same whole-word edge as in an English story.
        assert not common._requires_director_resolution(
            _act("breakfastを食べる"))
        assert common._requires_director_resolution(_act("ドアをbreakする"))
