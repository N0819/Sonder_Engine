"""An act the record gives to one body is not rendered as another's.

Scratch play 2026-09-14: chat 9 turn 14 gave Reen's letting go of the bell
rope to Edith ("Edith let the hemp drop"), chat 7 turn 1 gave the captain's
line to a footman. Perception's record names the actor of every act it
delivered (`observations[*].actor`); the sentence that renders an act is the
one sharing most of its content words, and the body that sentence names first
is who the page says did it. Reported, never edited.
"""

from agents.common import _check_action_attribution


OBS = [{"observation_id": "current:player:0", "channel": "sight", "kind": "action",
        "actor": "Tobias Reen",
        "observed": {"text": "Tobias Reen lets the bell rope go slack and leans against the wall with his chest heaving."}},
       {"observation_id": "current:player:1", "channel": "hearing", "kind": "speech",
        "actor": "Tobias Reen", "observed": {"text": "Tobias Reen says: \"Against the spring-tide.\""}}]
PLAYER = ["Edith", "Edith Marrow", "you", "your"]
PRESENT = ["Tobias Reen"]


def test_an_act_given_to_the_player_is_reported():
    prose = ("Edith let the hemp go slack and leaned back against the wall, "
             "her chest heaving. \"Against the spring-tide,\" he said.")
    out = _check_action_attribution(prose, OBS, PLAYER, PRESENT)
    assert len(out) == 1 and "the player" in out[0] and "Tobias Reen" in out[0]


def test_an_act_rendered_under_its_own_actor_passes():
    prose = ("Reen let the rope go slack and leaned against the wall, chest heaving. "
             "Edith held the lantern up.")
    assert _check_action_attribution(prose, OBS, PLAYER, PRESENT) == []


def test_a_thin_match_names_nobody():
    prose = "The wall was cold. Edith waited."
    assert _check_action_attribution(prose, OBS, PLAYER, PRESENT) == []
