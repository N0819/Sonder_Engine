"""Two things a background voice did on one page, each a different stage's.

Found in play on 2026-10-06 (scratch story 165, turns 4581-4582).

* A VOICE FROM ANOTHER ROOM SAYS WHERE IT CAME FROM. The market's reeve
  answered a shout through the inn's open door. The player's view said only
  'You hear a voice say: "Bell's not mine to answer ..."', and the narrator
  put him "on the far side of the room" -- where the player turned, the next
  beat, to question nobody. An unseen ACT was already placed by the
  listener's own sector (`sound_bearing`: "through the doorway to your
  right"); a line was not, though it is the same fact a channel route is.
* A BACKGROUND VOICE DOES NOT SAY AGAIN WHAT IT SAID. The house hand by the
  fire said "Search bell's been pulling all evening. Three and three. Nobody's
  said who yet." and the next beat said it again, with the same wrist-rolling
  gesture: his own call was handed `beat.recent_interaction` -- his last line
  and act -- by a card that never said what the field was.
"""

from __future__ import annotations

import pathlib

from agents import composer
from agents.composer import render_view
from agents.perception import _speech_bearing

ROOT = pathlib.Path(__file__).resolve().parents[1]
LINE = {"speaker": "Barelum Marleyburn", "volume": "loud",
        "text": "Bell's not mine to answer."}
DOORWAY = "through the doorway to your right"


def _heard(bearing="", rel=None, can_see=False):
    p = composer.speech_percept(
        dict(LINE), rel or {"same_room": False, "barrier": "open_door"},
        "Tamsin Coyle", display="a voice", can_see=can_see, bearing=bearing)
    return render_view([p], mode="player", language="en").text


def test_an_unseen_voice_from_another_room_is_placed():
    text = _heard(bearing=DOORWAY)
    assert text.startswith("You hear a voice")
    assert text.rstrip(".").endswith(DOORWAY)


def test_without_a_bearing_the_line_is_as_it_was():
    assert _heard() == 'You hear a voice say: "Bell\'s not mine to answer."'


def test_a_channel_route_outranks_the_bearing():
    p = composer.speech_percept(
        dict(LINE), {"same_room": False, "barrier": "wall",
                     "comm_channel": {"id": "pa", "name": "the speaker grille"}},
        "Tamsin Coyle", display="a voice", can_see=False, bearing=DOORWAY)
    text = render_view([p], mode="player", language="en").text
    assert "the speaker grille" in text and DOORWAY not in text


def test_the_bearing_is_asked_only_of_an_unseen_voice_in_another_room():
    scene = {"rooms": {"inn": {"name": "Taproom", "adjacent": [
                          {"to": "market", "barrier": "open_door"}]},
                      "market": {"name": "Market", "adjacent": [
                          {"to": "inn", "barrier": "open_door"}]}},
             "positions": {"Tamsin Coyle": "inn", "Barelum Marleyburn": "market",
                           "Hester Gale": "inn"}}
    beyond = {"same_room": False, "barrier": "open_door"}
    assert _speech_bearing(scene, "Tamsin Coyle", "Hester Gale", False,
                           {"same_room": True}) == ""
    assert _speech_bearing(scene, "Tamsin Coyle", "Barelum Marleyburn", True,
                           beyond) == "", "a speaker in sight needs no bearing"


def test_both_packs_tell_a_background_voice_its_last_line_is_not_its_next():
    for lang in ("en", "ja"):
        card = (ROOT / "language_packs" / lang
                / "cards/system_prompts/prompts/background_react.txt"
                ).read_text(encoding="utf-8")
        assert "`beat.recent_interaction`" in card, lang
