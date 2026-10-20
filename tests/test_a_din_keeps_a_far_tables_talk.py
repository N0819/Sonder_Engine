"""PRIVACY IN A DIN (DESIGN_SOUND_FIELD.md § 12, wave A, 2026-10-20).

The hearing rule of 2026-10-20 let no noise below `deafening` touch a line,
so a bystander anywhere in a busy tavern followed every word of a
conversation at another table. In the world a din cuts both ways: the
people talking TO EACH OTHER raise their voices and, a pace or two apart,
follow one another; a bystander a few paces off has the same voice's direct
sound 10-15 dB down against the same din, and catches pieces of it or only
the fact that people are talking.

The class, one test (or more) each:

  1. noise never stops people talking to each other: the line's addressee,
     and anyone within conversational reach of its speaker, hear it as the
     rule's table says, din or none;
  2. a din at a bystander's ear, beyond conversational reach, limits what
     the bystander follows -- by real levels: a crowd's babble by its band,
     music, any source loud enough to make the room a din;
  3. rain and a quiet house are not a din (the owner's rain ruling);
  4. a watched face is followed further;
  5. the composer reads who a line was spoken to; a line that does not say
     caps nothing.
"""

from __future__ import annotations

from agents import composer
from world.spatial import (CROWD_BABBLE_DB, DIN_DB, db_of_power, hear_level,
                           hearing_reason, sound_field, spatial_rel_between,
                           voice_carries)

VOLUMES = ("normal", "loud", "shout")


def _tavern(cells=None, *, room_sound=None):
    """A taproom ten paces by eight, the bodies stationed where the test
    says: A speaking, B the one spoken to beside A, E at A's elbow, C at
    the far table."""
    cells = cells or {"A": (1, 1), "B": (2, 1), "E": (2, 2), "C": (8, 6)}
    room = {"name": "the taproom", "exposure": "enclosed",
            "extent": {"w": 10, "d": 8}, "anchors": {}, "adjacent": []}
    if room_sound:
        room["sound"] = room_sound
    return {"rooms": {"tap": room},
            "positions": {k: "tap" for k in cells},
            "stations": {k: {"cell": list(v)} for k, v in cells.items()},
            "entities": {}, "poses": {}, "orientation": {}, "contained": {}}


def _crowd(band):
    return [{"uid": "drinkers", "room_uid": "tap", "band": band}]


def _rel(sc, listener, speaker="A", crowds=()):
    field = sound_field(sc, listener, crowds=list(crowds))
    return spatial_rel_between(sc, listener, speaker, sound=field)


def _heard(rel, addressed, **kwargs):
    return {v: hear_level(rel, v, addressed=addressed, **kwargs) for v in VOLUMES}


def test_a_crowd_fills_the_room_it_stands_in():
    """A few dozen people talking are a busy tavern's babble wherever one
    stands in it -- not a 50 dB hearth fire at the room's centre, which left
    every table but the middle one in a quiet room."""
    sc = _tavern()
    for who in ("A", "C"):
        noise = sound_field(sc, who, crowds=_crowd("a few dozen")).noise_at(who)
        assert abs(db_of_power(noise) - CROWD_BABBLE_DB["a few dozen"]) < 0.1
    assert CROWD_BABBLE_DB["a few dozen"] >= DIN_DB > CROWD_BABBLE_DB["a handful"]


def test_a_bystander_across_a_busy_tavern_catches_pieces():
    """Nine paces off, in a few dozen people's talk, a conversation at the
    far table arrives in pieces however it is raised -- a shout is the
    ceiling a voice rises to -- and the fact of it still arrives whole."""
    sc = _tavern()
    rel = _rel(sc, "C", crowds=_crowd("a few dozen"))
    assert rel.get("din_db") is not None and rel.get("paces") == 9.0
    assert _heard(rel, False) == {v: "fragment" for v in VOLUMES}
    assert hearing_reason(rel, "normal", addressed=False) == "din_bystander"
    assert voice_carries(rel, "normal", addressed=False)
    # In a throng an ordinary voice at the far table is only talk.
    rel = _rel(sc, "C", crowds=_crowd("a throng"))
    assert hear_level(rel, "normal", addressed=False) == "none"
    assert voice_carries(rel, "normal", addressed=False)


def test_noise_never_stops_people_talking_to_each_other():
    """The one spoken to follows the line in the loudest crowd -- beside the
    speaker or across the room -- and so does the body at the speaker's
    elbow it was not spoken to. Only a bystander beyond conversational
    reach loses it."""
    for band in ("a dozen or so", "a few dozen", "a throng"):
        sc = _tavern()
        to_b = _rel(sc, "B", crowds=_crowd(band))
        assert _heard(to_b, True) == {v: "full" for v in VOLUMES}, band
        elbow = _rel(sc, "E", crowds=_crowd(band))
        assert elbow.get("din_db") is not None
        assert _heard(elbow, False) == {v: "full" for v in VOLUMES}, band
        far = _rel(sc, "C", crowds=_crowd(band))
        assert _heard(far, True) == {v: "full" for v in VOLUMES}, band
        assert _heard(far, False)["normal"] != "full", band
    # The complement, the owner's rain ruling: the same room empty, and a
    # street in a downpour -- a far bystander follows every word, as the
    # hearing rule has it. Rain is never a din.
    #
    # RESTATED 2026-10-20 (wave B2): the downpour here also blew a gale,
    # and a gale is wind, not rain -- 70 dB(A) at the ear, a din, which a
    # bystander sixteen paces off in it now catches pieces through
    # (`WIND_NOISE_DB`, `test_the_wind_carries_and_swallows_sound.py`). The
    # rain the ruling is about falls here in still air.
    rel = _rel(_tavern(), "C")
    assert "din_db" not in rel and _heard(rel, False)["normal"] == "full"
    street = {"rooms": {"street": {"name": "the street", "exposure": "open",
                                   "extent": {"w": 40, "d": 6}, "anchors": {},
                                   "adjacent": []}},
              "positions": {"A": "street", "B": "street"},
              "stations": {"A": {"cell": [1, 3]}, "B": {"cell": [17, 3]}},
              "weather": {"precipitation": "rain", "precipitation_kind": "liquid",
                          "intensity": "heavy", "wind": "still", "sky": "storm",
                          "cloud": "covered"},
              "entities": {}, "poses": {}, "orientation": {}, "contained": {}}
    rel = spatial_rel_between(street, "B", "A", sound=sound_field(street, "B"))
    assert "din_db" not in rel
    assert hear_level(rel, "normal", addressed=False) == "full"


def test_music_is_a_din_by_its_level():
    """A room's own sound at a level that makes the room a din -- a band
    playing, a soprano and a piano -- keeps a far conversation from a
    bystander standing in it, and not from the one it is for."""
    music = {"level": "loud", "detail": "a fiddle and a drum"}
    sc = _tavern({"A": (1, 1), "B": (2, 1), "C": (5, 4)}, room_sound=music)
    rel = _rel(sc, "C")
    assert rel.get("din_db") is not None
    assert hear_level(rel, "normal", addressed=False) != "full"
    assert hear_level(rel, "normal", addressed=True) == "full"


def test_a_watched_speaker_is_followed_further():
    """Lips and face follow the voice: across a throng, an unwatched
    ordinary voice is only talk, a watched one is caught in pieces."""
    rel = _rel(_tavern(), "C", crowds=_crowd("a throng"))
    assert hear_level(rel, "normal", addressed=False) == "none"
    assert hear_level(rel, "normal", addressed=False, seen=True) == "fragment"


def test_the_composer_reads_whom_the_line_was_spoken_to():
    """`line_hear_level` passes the line's own addressee: B, named, follows
    it; C, at the far table, catches pieces. A line that carries no
    addressee field at all caps nothing -- the rule cannot tell."""
    sc = _tavern()
    line = {"speaker": "A", "exact_quote": "Meet me at the mill at dusk.",
            "volume": "normal", "intended_target": "B"}
    to_b = _rel(sc, "B", crowds=_crowd("a few dozen"))
    far = _rel(sc, "C", crowds=_crowd("a few dozen"))
    assert composer.line_hear_level(line, to_b, "B") == "full"
    assert composer.line_hear_level(line, far, "C") == "fragment"
    bare = {k: v for k, v in line.items() if k != "intended_target"}
    assert composer.line_hear_level(bare, far, "C") == "full"
    # ...and what reaches the far table is pieces, never the sentence.
    p = composer.speech_percept(line, far, "C", display="the speaker",
                                can_see=False)
    assert p.fidelity == "fragment" and "body" not in p.data
    assert "Meet me at the mill at dusk." not in str(p.data)
