"""WHICH WAY THE SPEAKER FACES (DESIGN_SOUND_FIELD.md § 14.1, wave B2,
2026-10-20).

A voice is directional. The mouth radiates forward and the head shades what
goes behind it: directly behind a talker the level is some 6-8 dB under the
level in front, and the band the consonants carry the words in falls most,
10-15 dB, while the vowels and the tune below 1 kHz lose only a few. Nothing
in the engine read the SPEAKER's facing for hearing -- `entity_arc` and
`sound_bearing` read the listener's.

The class, and where it bites. The hearing rule's table is used because its
entries sit far from either threshold, so facing matters only where a
line's budget is the voice's DIRECT sound and marginal:

  1. under the open sky at range (`open_air_loss_db`), and rooms away from a
     speaker standing under the sky;
  2. a bystander in a din (§ 12.1), whose budget is the direct sound because
     the room's ring is under the din;
  3. the voice rung (§ 12.2), which loses only the voice's low half;
  4. never within conversational reach, and never where a room's ring
     carries the voice -- across an enclosed room, through an opening or to
     a door nobody stands at: the ring faces nowhere.

Facing is the engine's own record (`effective_facing`); where it says
nothing, nothing changes. And the record is where the speaker ends the beat,
not where the head turned while the words were said: a speaker turns to the
one they talk to, so the shadow falls on a BYSTANDER -- a listener the line
is not spoken to (`addressed=False`) -- and never on its addressee or on a
listener nobody can say it was for (`spatial_senses._facing_its_addressee`,
the main session's answer to the lane's question 2, 2026-10-20).
"""

from __future__ import annotations

from world.spatial import (FACING_AWAY_VOICE_DB, FACING_AWAY_WORDS_DB,
                           hear_level, hearing_reason, sound_field,
                           spatial_rel_between, voice_carries, voice_margin_db)

VOLUMES = ("normal", "loud", "shout")


def _field(paces, facing=None, *, exposure="open", weather=None):
    """An open field ninety-six paces long: A speaks from the west end, B
    stands `paces` east of A along it. `facing` is where A faces."""
    sc = {"rooms": {"field": {"name": "the field", "exposure": exposure,
                              "extent": {"w": 96, "d": 6}, "anchors": {},
                              "adjacent": []}},
          "positions": {"A": "field", "B": "field"},
          "stations": {"A": {"cell": [1, 3]}, "B": {"cell": [1 + paces, 3]}},
          "entities": {}, "poses": {}, "orientation": {}, "contained": {}}
    if facing:
        sc["orientation"]["A"] = {"facing": facing}
    if weather:
        sc["weather"] = weather
    return sc


def _rel(sc, listener="B", speaker="A", crowds=()):
    field = sound_field(sc, listener, crowds=list(crowds))
    return spatial_rel_between(sc, listener, speaker, sound=field)


def test_a_voice_turned_away_carries_less_far_under_the_sky():
    """Forty paces of open field: an ordinary voice facing a bystander is
    followed whole, the same voice turned away is caught in pieces; at ninety
    a raised voice is whole in front and in pieces behind. A shout carries
    either way."""
    front = _rel(_field(40, "e"))
    behind = _rel(_field(40, "w"))
    assert "speaker_turned_away" not in front
    assert behind.get("speaker_turned_away") is True
    assert hear_level(front, "normal", addressed=False) == "full"
    assert hear_level(behind, "normal", addressed=False) == "fragment"
    assert hearing_reason(behind, "normal", addressed=False) \
        == "speaker_turned_away"
    far_front, far_behind = _rel(_field(90, "e")), _rel(_field(90, "w"))
    assert hear_level(far_front, "loud", addressed=False) == "full"
    assert hear_level(far_behind, "loud", addressed=False) == "fragment"
    assert hear_level(far_behind, "shout", addressed=False) == "full"
    # Side on, the head shades nothing the words need.
    assert "speaker_turned_away" not in _rel(_field(40, "n"))


def test_within_conversational_reach_a_turned_back_takes_nothing():
    """Two paces apart a turned back is still heard whole, by anyone at
    the speaker's shoulder, while forty paces off the same back costs a
    bystander the words."""
    near = _rel(_field(2, "w"))
    assert "speaker_turned_away" not in near
    assert {v: hear_level(near, v, addressed=False) for v in VOLUMES} == \
        {v: "full" for v in VOLUMES}
    assert hear_level(_rel(_field(40, "w")), "normal", addressed=False) \
        == "fragment"


def test_a_facing_nobody_recorded_changes_nothing():
    """With no facing on the record the relation is exactly what it was:
    the rule never guesses which way a body faces. Recorded, it bites."""
    unknown = _rel(_field(40))
    assert "speaker_turned_away" not in unknown
    assert hear_level(unknown, "normal", addressed=False) == "full"
    assert hear_level(_rel(_field(40, "w")), "normal", addressed=False) \
        == "fragment"


def test_indoors_the_ring_faces_nowhere():
    """The same forty paces under a roof are a hall, and its ring carries a
    voice to every corner whichever way the speaker faces: no stamp, every
    word whole. The difference from the open field is the whole rule."""
    hall = _rel(_field(40, "w", exposure="enclosed"))
    assert "speaker_turned_away" not in hall
    assert hear_level(hall, "normal", addressed=False) == "full"
    assert hear_level(_rel(_field(40, "w")), "normal", addressed=False) \
        != "full"


def _tavern(a_cell, c_cell, facing):
    room = {"name": "the taproom", "exposure": "enclosed",
            "extent": {"w": 10, "d": 8}, "anchors": {}, "adjacent": []}
    return {"rooms": {"tap": room},
            "positions": {"A": "tap", "C": "tap"},
            "stations": {"A": {"cell": list(a_cell)},
                         "C": {"cell": list(c_cell)}},
            "entities": {}, "poses": {}, "orientation": {"A": {"facing": facing}},
            "contained": {}}


CROWD = [{"uid": "drinkers", "room_uid": "tap", "band": "a few dozen"}]


def test_a_bystander_behind_the_speaker_in_a_din_loses_more():
    """In a busy tavern a raised voice four paces off is followed whole by
    a bystander the speaker faces and caught in pieces by one behind: the
    room's ring is under the din, so what a bystander has is the direct
    sound, and the direct sound has a front. The one it is said to follows
    it either way."""
    front = _rel(_tavern((1, 1), (5, 1), "e"), "C", crowds=CROWD)
    behind = _rel(_tavern((5, 1), (1, 1), "e"), "C", crowds=CROWD)
    assert front.get("din_db") is not None and front.get("paces") == 4.0
    assert behind.get("speaker_turned_away") is True
    assert hear_level(front, "loud", addressed=False) == "full"
    assert hear_level(behind, "loud", addressed=False) == "fragment"
    assert hearing_reason(behind, "loud", addressed=False) \
        == "speaker_turned_away"
    assert hear_level(behind, "loud", addressed=True) == "full"


def test_the_voice_behind_a_speaker_loses_only_its_low_half():
    """The whole length of the field, ninety-four paces: behind the speaker
    the words of an ordinary voice are lost, the voice itself still
    carries, and its budget fell by the low half's few decibels, not the
    words'."""
    front, behind = _rel(_field(94, "e")), _rel(_field(94, "w"))
    assert hear_level(front, "normal", addressed=False) == "fragment"
    assert hear_level(behind, "normal", addressed=False) == "none"
    assert voice_carries(behind, "normal", addressed=False)
    drop = voice_margin_db(front, "normal") - voice_margin_db(behind, "normal")
    assert abs(drop - FACING_AWAY_VOICE_DB) < 1e-9
    assert FACING_AWAY_VOICE_DB < FACING_AWAY_WORDS_DB


def _square_and_lanes(facing):
    """A square, a lane east of it and a yard east of that, all under the
    sky: A speaks in the square, B listens in the yard two rooms off."""
    def room(name, w, adjacent):
        return {"name": name, "exposure": "open", "extent": {"w": w, "d": 6},
                "anchors": {}, "adjacent": adjacent}
    rooms = {
        "square": room("the square", 10, [{"to": "lane", "barrier": "open",
                                            "dir": "e"}]),
        "lane": room("the lane", 6, [{"to": "square", "barrier": "open",
                                      "dir": "w"},
                                     {"to": "yard", "barrier": "open",
                                      "dir": "e"}]),
        "yard": room("the yard", 6, [{"to": "lane", "barrier": "open",
                                      "dir": "w"}]),
    }
    return {"rooms": rooms, "positions": {"A": "square", "B": "yard"},
            "stations": {"A": {"cell": [8, 3]}, "B": {"cell": [3, 3]}},
            "entities": {}, "poses": {}, "orientation": {"A": {"facing": facing}},
            "contained": {}}


def test_rooms_away_a_speaker_under_the_sky_faces_the_way_out():
    """Rooms away, a voice spoken under the sky leaves by the way out
    toward the listener as its direct sound: turned toward that way, it
    reaches the yard two rooms off as it always did; turned away from it,
    every word it carries arrives a few decibels lower."""
    toward = _rel(_square_and_lanes("e"))
    away = _rel(_square_and_lanes("w"))
    assert toward.get("far_loss_db") is not None
    assert "speaker_turned_away" not in toward
    assert away.get("speaker_turned_away") is True
    ladder = {"none": 0, "fragment": 1, "full": 2}

    def heard(rel, v):
        return ladder[hear_level(rel, v, addressed=False)]
    assert all(heard(away, v) <= heard(toward, v) for v in VOLUMES)
    assert any(heard(away, v) < heard(toward, v) for v in VOLUMES), (
        {v: (hear_level(toward, v, addressed=False),
             hear_level(away, v, addressed=False)) for v in VOLUMES})


def test_the_one_it_is_spoken_to_is_faced():
    """Forty paces of open field, the speaker's back to the listener. The
    record says where she ends the beat, not where she turned to speak, and
    a speaker turns to the one she talks to: the line's addressee follows
    every word, and so does a listener nobody can say the line was for (a
    line naming no one -- the harbour story's quay, turns 1-3, where seven
    lines between two people fell to pieces on the end-of-beat facing). Only
    a bystander the line is not spoken to stands in the head's shadow."""
    behind = _rel(_field(40, "w"))
    assert behind.get("speaker_turned_away") is True
    for addressed in (True, None):
        assert hear_level(behind, "normal", addressed=addressed) == "full"
        assert hearing_reason(behind, "normal", addressed=addressed) == ""
    assert hear_level(behind, "normal", addressed=False) == "fragment"
    # The voice rung follows the words: the far end of the field, where the
    # words are gone, the voice still reaches its addressee unshaded.
    far = _rel(_field(94, "w"))
    assert voice_carries(far, "normal", addressed=True)
    assert hear_level(far, "normal", addressed=True) \
        == hear_level(_rel(_field(94, "e")), "normal", addressed=True)
