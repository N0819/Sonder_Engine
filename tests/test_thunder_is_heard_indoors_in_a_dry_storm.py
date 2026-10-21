"""THUNDER IS HEARD INDOORS WHETHER OR NOT RAIN IS (DESIGN_SOUND_FIELD.md
§ 16, round 2 lane B, 2026-10-20; § 14.7's question 9).

`weather.thunder_heard` required audible rain indoors, so a dry storm was
silent behind walls. Real: thunder is 100-120 dB(A) near and 60-80 a few
kilometres off, low-frequency, and an ordinary roof or wall takes 30-45 dB
of it, a shut interior door 15-25 more: it is heard, muffled, in any room
with the sky somewhere above it, and only a room shut away from the sky
altogether -- sealed by its map, or buried storeys under the ground -- does
not hear it.

The class, one test each:

  1. a dry electrical storm is heard in every room of the house: whole
     under the sky, the same one door in, muffled by the doors between
     the room and the open air;
  2. a room the map seals away from the air, and a room two storeys under
     the ground, hear nothing;
  3. the sound bed and the view a mind is given read the one rule and say
     the same thing of every room.
"""

from __future__ import annotations

from agents import composer
from world.weather import (THUNDER_BURIED_LEVEL, THUNDER_REACH_LAYERS,
                           thunder_heard, weather_for_room, weather_words)

DRY_STORM = {"sky": "storm", "cloud": "covered", "electrical": True,
             "wind": "wind"}


def _house(weather=DRY_STORM):
    """A yard; a hall off it through an open door; a parlour behind a shut
    door; a vault behind another; a cellar behind a third; a crypt behind a
    fourth; a sealed room behind the vault's wall; and a shaft two storeys
    down off the vault."""
    def room(name, adjacent, **extra):
        return {"name": name, "exposure": "enclosed",
                "adjacent": adjacent, **extra}
    return {
        "weather": dict(weather),
        "positions": {"P": "hall"},
        "rooms": {
            "yard": {"name": "the yard", "exposure": "open",
                     "adjacent": [{"to": "hall", "barrier": "open_door"}]},
            "hall": room("the hall", [{"to": "yard", "barrier": "open_door"},
                                      {"to": "parlour", "barrier": "closed_door"}]),
            "parlour": room("the parlour", [{"to": "hall", "barrier": "closed_door"},
                                            {"to": "vault", "barrier": "closed_door"}]),
            "vault": room("the vault", [{"to": "parlour", "barrier": "closed_door"},
                                        {"to": "cellar", "barrier": "closed_door"},
                                        {"to": "sealed", "barrier": "wall"},
                                        {"to": "shaft", "barrier": "closed_door"}]),
            "cellar": room("the cellar", [{"to": "vault", "barrier": "closed_door"},
                                          {"to": "crypt", "barrier": "closed_door"}]),
            "crypt": room("the crypt", [{"to": "cellar", "barrier": "closed_door"}]),
            "sealed": room("the sealed room", [{"to": "vault", "barrier": "wall"}]),
            "shaft": room("the shaft foot", [{"to": "vault", "barrier": "closed_door"}],
                          level=THUNDER_BURIED_LEVEL),
        },
    }


def _bed(sc, room):
    return weather_words(weather_for_room(sc, room), "sound")


def _view(sc, room):
    return composer.render_view(
        composer.weather_percepts(weather_for_room(sc, room, "P"))).text


def test_a_dry_storm_is_heard_in_every_room_with_the_sky_above_it():
    sc = _house()
    assert "thunder" in _bed(sc, "yard")
    assert "thunder" in _bed(sc, "hall")               # an open door is no layer
    assert "distant thunder" in _bed(sc, "parlour")    # one shut door in
    assert "muffled thunder" in _bed(sc, "vault")      # two
    assert "muffled thunder" in _bed(sc, "cellar")     # three
    assert thunder_heard(weather_for_room(sc, "hall")) == ""
    assert thunder_heard(weather_for_room(sc, "parlour")) == "muffled"
    assert thunder_heard(weather_for_room(sc, "cellar")) == "faint"
    assert "Thunder rolls somewhere beyond the walls, muffled." in _view(sc, "parlour")
    assert "A faint roll of thunder reaches you from far beyond the walls." \
        in _view(sc, "cellar")
    # Nothing of the rain is said, because there is none.
    assert not any("rain" in w for w in _bed(sc, "parlour"))
    # With rain the words are what they were.
    wet = _house({**DRY_STORM, "precipitation": "rain", "intensity": "heavy"})
    assert "distant thunder" in _bed(wet, "parlour")
    assert "muffled rain" in _bed(wet, "parlour")


def test_a_room_shut_away_from_the_sky_hears_nothing():
    """Four shut doors in (`THUNDER_REACH_LAYERS` 3 is the last that hears
    it), behind a wall the map walks no way through, or two storeys under
    the ground: no thunder, in the bed or the view."""
    sc = _house()
    assert THUNDER_REACH_LAYERS == 3 and THUNDER_BURIED_LEVEL == -2
    for room in ("crypt", "sealed", "shaft"):
        assert thunder_heard(weather_for_room(sc, room)) is None, room
        assert not any("thunder" in w for w in _bed(sc, room)), room
        assert "hunder" not in _view(sc, room), room
    # A storey under the ground still hears it: a cellar has a house above.
    one_down = _house()
    one_down["rooms"]["shaft"]["level"] = THUNDER_BURIED_LEVEL + 1
    assert thunder_heard(weather_for_room(one_down, "shaft")) == "faint"


def test_the_bed_and_the_view_read_one_rule():
    sc = _house()
    for room in sc["rooms"]:
        bed = any("thunder" in w for w in _bed(sc, room))
        view = "hunder" in _view(sc, room)
        assert bed == view, room
