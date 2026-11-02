"""A heard tell is graded by the rules a line beside it is graded by.

`_delivered_manifest` decided a tell's reach with a bare `same_room` and a
`normal` voice, card-blind (audit agents_perception F2, 2026-11-01, three
reproductions plus a sight half):

  1. a DEAF observer in a dark cellar was delivered "a ragged breath catches
     in the dark" -- the hearing card was never asked;
  2. every tell was a normal voice, so a BREATH carried 28 paces down a dark
     hall where a whisper reaches nobody;
  3. `same_room` was required, so a VOICE tell through an open doorway was
     withheld where the speaker's normal line arrives whole;
  4. a BLIND card in a lit room was handed seen tells and the demeanor --
     `visual_level_between` spends a card only on `needs_light`.

The rule: a tell crosses by sight (the card's sight, not the room's light)
or, where its channel is heard, by the hearing rule at the loudness the tell
carries -- a breath is unvoiced (a whisper's rung), a voice tell is the
source's own voice -- through the card's ears.
"""

from types import SimpleNamespace

import pytest

from agents.perception import _delivered_manifest

BREATH = {"channel": "breath", "cue": "a ragged breath catches in the dark",
          "subtlety": 0.0}
VOICE = {"channel": "voice", "cue": "a tremor under the vowels",
         "subtlety": 0.0}
SEEN = {"channel": "seen", "cue": "a glance at the door", "subtlety": 0.0}

DEAF = {"core": {}, "embodiment": {"senses": [
    {"channel": "hearing", "acuity": "deaf"}]}}
BLIND = {"core": {}, "embodiment": {"senses": [
    {"channel": "vision", "acuity": "blind"}]}}


def _ctx(*tells, demeanor=""):
    return SimpleNamespace(character_results={1: {"manifest": {
        "surface_demeanor": demeanor, "tells": list(tells)}}})


def _cellar(light="dark"):
    return {"rooms": {"cellar": {"name": "Cellar", "light": light,
                                 "adjacent": []}},
            "positions": {"Ada": "cellar", "Bo": "cellar"},
            "entities": {}, "stations": {}}


def _long_hall():
    """A dark hall sixty paces long, Ada at the west wall, Bo at the east."""
    return {"rooms": {"hall": {
        "name": "Great Hall", "light": "dark", "extent": {"w": 60, "d": 4},
        "anchors": {
            "west": {"desc": "the west wall", "dir": "w", "height": "waist",
                     "cell": [0, 1]},
            "east": {"desc": "the east wall", "dir": "e", "height": "waist",
                     "cell": [59, 1]}},
        "adjacent": []}},
        "positions": {"Ada": "hall", "Bo": "hall"}, "entities": {},
        "stations": {"Ada": {"at": "west"}, "Bo": {"at": "east"}}}


def _two_rooms():
    """A dark kitchen and a dark yard, one open doorway between."""
    return {"rooms": {
        "kitchen": {"name": "Kitchen", "light": "dark",
                    "adjacent": [{"to": "yard", "barrier": "open_door"}]},
        "yard": {"name": "Yard", "light": "dark",
                 "adjacent": [{"to": "kitchen", "barrier": "open_door"}]}},
        "positions": {"Ada": "kitchen", "Bo": "yard"}, "entities": {},
        "stations": {}}


def _cues(ctx, scene, room, sheet=None, **kw):
    out = _delivered_manifest(ctx, scene, "Ada", [{"name": "Bo", "room": room}],
                              {}, {"Bo": 1}, sheet, **kw)
    return (out.get("Bo") or {}).get("cues") or []


def test_a_breath_in_the_dark_reaches_an_ordinary_ear():
    """The baseline the subtractions below are measured against."""
    assert _cues(_ctx(BREATH), _cellar(), "cellar") == [BREATH["cue"]]


def test_a_deaf_card_hears_no_tell():
    assert _cues(_ctx(BREATH, VOICE), _cellar(), "cellar", DEAF) == []


def test_a_breath_does_not_carry_where_a_whisper_does_not():
    assert _cues(_ctx(BREATH), _long_hall(), "hall") == []


def test_a_voice_tell_carries_where_the_voice_does():
    """Sixty paces of quiet dark carry a normal voice whole, so the voice's
    tremor goes with it -- the breath beside it does not (above)."""
    assert _cues(_ctx(VOICE), _long_hall(), "hall") == [VOICE["cue"]]


def test_a_voice_tell_crosses_an_open_doorway_with_the_voice():
    assert _cues(_ctx(VOICE), _two_rooms(), "yard") == [VOICE["cue"]]


def test_a_voice_tell_is_the_sources_own_voice():
    """A source who spoke only in a whisper this beat carries a whisper's
    tremor: across the doorway it does not arrive."""
    assert _cues(_ctx(VOICE), _two_rooms(), "yard",
                 voices={"Bo": "whisper"}) == []


@pytest.mark.parametrize("sheet", [None, BLIND])
def test_a_blind_card_is_shown_no_tell_and_no_demeanor(sheet):
    out = _delivered_manifest(
        _ctx(SEEN, demeanor="outwardly calm"), _cellar("lit"), "Ada",
        [{"name": "Bo", "room": "cellar"}], {}, {"Bo": 1}, sheet)
    if sheet is None:
        assert out == {"Bo": {"surface_demeanor": "outwardly calm",
                              "cues": [SEEN["cue"]]}}
    else:
        assert out == {}, out


def test_a_tell_is_caught_by_the_sense_that_reached_it():
    """A poor eye and a keen ear: a subtle sign only SEEN is missed, a
    subtle voice tell -- seen and heard -- is caught by the ear."""
    card = {"core": {}, "embodiment": {"senses": [
        {"channel": "vision", "acuity": "poor"},
        {"channel": "hearing", "acuity": "keen"}]}}
    lit = _cellar("lit")
    assert _cues(_ctx(dict(SEEN, subtlety=0.65)), lit, "cellar", card) == []
    assert _cues(_ctx(dict(VOICE, subtlety=0.65)), lit, "cellar", card) \
        == [VOICE["cue"]]
