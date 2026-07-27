"""Quality of the structured observations perception derives from its views.

The leak properties of this projection are covered by
tests/test_perception_intent_leak.py; this file covers whether the projection
says anything TRUE. It shipped as a single atom holding the whole view, with
unanchored substring cues that made the metadata near-constant: 'paint' matched
'pain', one quoted line relabelled a page of body sensation as hearing, and
'something' pinned fidelity to ambiguous on any view long enough to contain it.
The character agent is told these atoms are a structured projection of its own
perception, so constant-wrong metadata is an instruction to doubt what it
plainly perceived.
"""

from __future__ import annotations

from agents.perception import _observations_from_clean_views


def _atoms(text, pid="7"):
    return _observations_from_clean_views({pid: text})[pid]


def test_a_view_decomposes_into_per_channel_atoms():
    atoms = _atoms(
        "The lantern light gutters against the far wall. "
        "You hear footsteps on the gravel outside. "
        "The scent of woodsmoke thickens."
    )
    assert len(atoms) == 3
    assert [a["channel"] for a in atoms] == ["sight", "hearing", "smell"]
    assert [a["observation_id"] for a in atoms] == [
        "current:7:0", "current:7:1", "current:7:2"]


def test_atoms_are_capped_but_never_collapse_to_one():
    atoms = _atoms(" ".join(f"Sentence number {i} lands." for i in range(40)))
    assert 1 < len(atoms) <= 8


def test_one_quoted_line_no_longer_relabels_a_whole_view():
    """A body-sensation view carrying a single line of dialogue keeps its own
    channel for the body sentences."""
    atoms = _atoms(
        "Your chest aches with every breath you draw. "
        'She says, "hold still." '
        "Your pulse hammers in your throat."
    )
    channels = [a["channel"] for a in atoms]
    assert channels.count("interoception") == 2
    assert "hearing" in channels


def test_word_boundaries_stop_the_paint_for_pain_class_of_hit():
    atoms = _atoms("The paint on the fireplace has blistered and wound around "
                   "the mantel.")
    assert len(atoms) == 1
    assert atoms[0]["channel"] != "interoception"
    assert atoms[0]["intensity"] < 0.5


def test_a_single_hedge_word_is_not_an_ambiguous_perception():
    atoms = _atoms("Something heavy settles onto the boards beside you.")
    assert atoms[0]["fidelity"] == "rendered"
    assert atoms[0]["ambiguity"] < 0.5


def test_genuinely_hedged_perception_still_reads_ambiguous():
    atoms = _atoms("A muffled voice, barely audible, says something you cannot "
                   "make out.")
    assert atoms[0]["fidelity"] == "ambiguous"
    assert atoms[0]["ambiguity"] >= 0.5


def test_contact_with_the_perceiver_is_directed_at_self():
    for line in (
        "A hand closes on your shoulder.",
        "The blast throws grit against your face.",
        "You are struck from behind.",
        "He turns toward you.",
    ):
        assert _atoms(line)[0]["directed_at_self"] is True, line


def test_own_body_state_is_directed_at_self_without_a_cue():
    atoms = _atoms("Your chest aches and your pulse will not steady.")
    assert atoms[0]["channel"] == "interoception"
    assert atoms[0]["directed_at_self"] is True


def test_an_event_across_the_room_is_not_directed_at_self():
    atoms = _atoms("Two dockhands argue over a crate at the far end of the "
                   "pier.")
    assert atoms[0]["directed_at_self"] is False


def test_an_empty_view_yields_no_atoms():
    assert _observations_from_clean_views({"7": ""}) == {"7": []}
    assert _observations_from_clean_views({"7": None}) == {"7": []}
