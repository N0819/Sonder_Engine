"""A name a speaker uses of somebody standing there is a name they know.

`known` was learned by hearing alone: the player who shouted "Abel! Abel,
the bar" at her own patient (scratch play 2026-09-14, chat 4 turn 10) went on
seeing "the gaunt old man" for the rest of the story. The speaker's test is
the hearer's own: the named body must stand in the speaker's room.
"""
from persist.commit import _address_index, _names_spoken_by

ROSTER = ["Abel Trask", "Iris Vale"]
SCENE = {
    "positions": {"Iris Vale": "yard", "Abel Trask": "yard", "Mara": "lane"},
    "rooms": {"yard": {"name": "Farmyard"}, "lane": {"name": "Lane"}},
    "entities": {},
}


def _learned(quote, scene=SCENE, known=None, speaker="Iris Vale"):
    return _names_spoken_by(
        [{"speaker": speaker, "exact_quote": quote}], scene, ROSTER,
        known or {}, {}, address_index=_address_index(ROSTER))


def test_naming_the_body_beside_you_is_knowing_it():
    assert _learned('"Trask! Trask, the bar -- get the bar on the front door!"') \
        == {"Iris Vale": ["Abel Trask"]}


def test_a_bare_given_name_is_not_an_address_form():
    """The address forms are the hearer's own (`_address_index`: full name
    and family name), and this rule widens nothing."""
    assert _learned('"Abel! Abel, the bar!"') == {}


def test_a_speaker_outside_the_minds_with_a_map_teaches_nobody():
    learned = _names_spoken_by(
        [{"speaker": "Iris Vale", "exact_quote": '"Trask."'}], SCENE, ROSTER,
        {}, {}, speakers={"Abel Trask"},
        address_index=_address_index(ROSTER))
    assert learned == {}


def test_a_name_used_of_somebody_elsewhere_teaches_nothing():
    scene = dict(SCENE, positions={"Iris Vale": "yard", "Abel Trask": "lane"})
    assert _learned('"Trask, the door!"', scene=scene) == {}


def test_a_name_already_known_is_not_learned_twice():
    assert _learned('"Trask."', known={"Iris Vale": ["Abel Trask"]}) == {}


def test_the_speakers_own_name_is_not_a_lesson():
    assert _learned('"Iris Vale will do it herself."') == {}
