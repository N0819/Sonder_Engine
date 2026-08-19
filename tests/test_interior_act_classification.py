"""What `_is_mental_action` may blank, and what it may not.

Blanking an action's `observable` surface is unrecoverable: the element is
skipped by every deterministic delivery site, so the act reaches no perceiver's
view, no composer percept and no witness's memory, and the only trace left is
an empty string in a stored variant. It does not error and it did not warn.
That is the engine's signature failure shape -- it shows up fifty beats later
as a character who did not react to something that plainly happened.

Measured over the 4,000 most recent stored `director_interpret` /
`director_establish` active variants in the owner's `engine.db` (read-only):
2,195 action elements, 14 of them led by one of the five verbs that name an
interior state AND an ordinary physical act (`feel`, `focus`, `reflect`,
`resolve`, `sense`). The one that shows the defect whole:

    verb:     "search"
    attempt:  "feel along the desk surface in total darkness, searching by
               touch for anything resembling a radio unit or switch"

The Director declared the verb `search`. `_is_mental_action` checked it, found
it was not a mental verb, and then went on to guess from the attempt's leading
token anyway -- `feel` -- and blanked a search of a desk by touch.
"""

from __future__ import annotations

from agents.common import _is_mental_action, norm_sequence


def test_a_declared_verb_is_not_overruled_by_the_attempts_first_word():
    """The leading-token scan exists "for a weak model that left verb unset"
    -- its own docstring's words. A Director that declared a verb has already
    answered the question, and a guess must not overturn an answer."""
    assert not _is_mental_action(
        "search",
        "feel along the desk surface in total darkness, searching by touch "
        "for anything resembling a radio unit or switch")
    # The declared verb still decides in the other direction.
    assert _is_mental_action("remember", "walk to the door")


def test_a_verb_that_names_both_an_act_and_a_state_needs_an_inward_object():
    """`feel`, `focus`, `reflect`, `resolve` and `sense` lead ordinary
    interactive-fiction conduct as often as they lead a thought. Which one is
    meant is decided by what the act reaches for, not by the verb."""
    for attempt in ("feel along the wall for the light switch",
                    "focus the lantern beam on the lock",
                    "reflect the beam down the corridor",
                    "focuses on the TARDIS",
                    "resolve the jammed latch"):
        assert not _is_mental_action("", attempt), attempt


def test_a_body_part_used_as_an_instrument_still_reads_inward():
    """The known limit of the marker, recorded rather than left to be
    rediscovered: `_OWN_BODY_NOUNS` cannot tell the act's OBJECT from its
    INSTRUMENT, so "focuses her ears on the Doctor" is still classified
    interior. That is where it already was, so nothing regressed -- but it is
    the residue of this row, not a property anyone chose."""
    assert _is_mental_action("focus", "focuses her ears on the Doctor")


def test_an_inward_object_still_reads_as_interior():
    """Turned on the actor's own body or on a state they are in, the same five
    verbs are interior, and blanking them is right. Both of these are live
    lines from the corpus."""
    for attempt in ("feel heart hammering in chest from nervousness while "
                    "mustering the words",
                    "feel Lustara's warmth and weight on top of her",
                    "reflect on the shame of it"):
        assert _is_mental_action("", attempt), attempt


def test_the_unambiguous_interior_verbs_are_untouched():
    for attempt in ("remember the runes her mother taught her",
                    "decide against saying anything",
                    "wonder whether the door was ever locked"):
        assert _is_mental_action("", attempt), attempt


def test_blanking_an_act_to_imperceptible_says_so():
    """The whole cost of this class is that it is silent. A blank is a
    decision that nobody will ever perceive this act; it belongs in the
    step's warnings beside every other decision of that weight."""
    warnings = []
    out = norm_sequence(
        {"sequence": [{"type": "action",
                       "attempt": "remember the runes her mother taught her"}]},
        warn=warnings.append)
    assert out["sequence"][0]["observable"] == ""
    assert any("perceive" in w or "interior" in w for w in warnings), warnings


def test_half_a_ponder_is_dropped_out_loud():
    """The same failure shape one branch over. A ponder is by design not in the
    public sequence, so nothing downstream can notice it went missing -- there
    is no view, no percept and no prose it would have shown up in. Dropping one
    for want of a `why` was silent."""
    warnings = []
    out = norm_sequence(
        {"sequence": [{"type": "ponder",
                       "query": "did she recognise the sigil"}]},
        warn=warnings.append)
    assert "ponder" not in out
    assert any("ponder" in w for w in warnings), warnings


def test_a_complete_ponder_is_kept_quietly():
    warnings = []
    out = norm_sequence(
        {"sequence": [{"type": "ponder", "query": "who sent the letter",
                       "why": "the seal was not the one she uses"}]},
        warn=warnings.append)
    assert out["ponder"]["query"] == "who sent the letter"
    assert not warnings


def test_a_director_authored_surface_is_never_second_guessed():
    warnings = []
    out = norm_sequence(
        {"sequence": [{"type": "action",
                       "attempt": "remember the runes",
                       "observable": "her lips move soundlessly"}]},
        warn=warnings.append)
    assert out["sequence"][0]["observable"] == "her lips move soundlessly"
    assert not warnings
