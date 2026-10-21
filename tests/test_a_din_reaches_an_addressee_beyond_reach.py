"""THE DIN REACHES AN ADDRESSEE BEYOND CONVERSATIONAL REACH
(DESIGN_SOUND_FIELD.md § 16, round 2 lane B, 2026-10-20; the owner's
answer to § 14.7's question 5).

Wave A (§ 12.1) spared a line's addressee at ANY range: a din capped only a
bystander beyond conversational reach. In the world a shout to someone a
hundred metres off in a gale is lost, and across a busy hall a line to
someone nine paces off is lost too -- being the one spoken to does not put
a voice in your ear. What being spoken to DOES do is put the two of you
within reach: people who talk to each other in a din close up.

The class, one test (or more) each:

  1. noise never stops people talking to each other WITHIN conversational
     reach (`CONVERSATION_REACH_PACES`): the addressee beside the speaker,
     and anyone that near, hear the line as the rule's table says;
  2. beyond it, the addressee is graded against the din at their ear like
     anyone else -- with the Lombard rise of the speaker's voice and the
     watched-face benefit they already had;
  3. a line whose addressee nobody can name (None) still caps nothing;
  4. under the sky a gale is the same din: a shout to someone a hundred
     metres off is lost, a shout across a street caught in pieces; in rain
     and still air a call across a street is whole (the owner's rain
     ruling holds by construction -- rain is never a din).
"""

from __future__ import annotations

from world.spatial import (CONVERSATION_REACH_PACES, DIN_DB, hear_level,
                           hearing_reason, sound_field, spatial_rel_between,
                           voice_carries)

VOLUMES = ("normal", "loud", "shout")


def _tavern(cells=None, *, room_sound=None):
    """A taproom ten paces by eight: A speaking, B beside A, E at A's elbow,
    C at the far table nine paces off."""
    cells = cells or {"A": (1, 1), "B": (2, 1), "E": (2, 2), "C": (8, 6)}
    room = {"name": "the taproom", "exposure": "enclosed",
            "extent": {"w": 10, "d": 8}, "anchors": {}, "adjacent": []}
    if room_sound:
        room["sound"] = room_sound
    return {"rooms": {"tap": room},
            "positions": {k: "tap" for k in cells},
            "stations": {k: {"cell": list(v)} for k, v in cells.items()},
            "entities": {}, "poses": {}, "orientation": {}, "contained": {}}


def _field(cells, weather=None):
    """One open field ninety-six paces long -- and east of it, through a gap
    in the hedge, a pasture of the same length, one stretch of open air
    (§ 14.2). `cells` is {name: (x, y)} on the field, or {name: ("pasture",
    (x, y))} on the pasture."""
    def room(name, adjacent):
        return {"name": name, "exposure": "open", "extent": {"w": 96, "d": 6},
                "anchors": {}, "adjacent": adjacent}
    sc = {"rooms": {"field": room("the field", [{"to": "pasture", "barrier": "open",
                                                 "dir": "e"}]),
                    "pasture": room("the pasture", [{"to": "field", "barrier": "open",
                                                     "dir": "w"}])},
          "positions": {}, "stations": {},
          "entities": {}, "poses": {}, "orientation": {}, "contained": {}}
    for name, cell in cells.items():
        room_id, at = (cell if isinstance(cell[0], str) else ("field", cell))
        sc["positions"][name] = room_id
        sc["stations"][name] = {"cell": list(at)}
    if weather:
        sc["weather"] = weather
    return sc


def _crowd(band):
    return [{"uid": "drinkers", "room_uid": "tap", "band": band}]


def _rel(sc, listener, speaker="A", crowds=()):
    field = sound_field(sc, listener, crowds=list(crowds))
    return spatial_rel_between(sc, listener, speaker, sound=field)


def _heard(rel, addressed, **kwargs):
    return {v: hear_level(rel, v, addressed=addressed, **kwargs) for v in VOLUMES}


GALE = {"sky": "overcast", "cloud": "covered", "wind": "gale"}
DOWNPOUR = {"precipitation": "rain", "precipitation_kind": "liquid",
            "intensity": "heavy", "sky": "storm", "cloud": "covered",
            "wind": "still"}


def test_within_conversational_reach_the_din_takes_nothing():
    """The one spoken to beside the speaker, and the body at the speaker's
    elbow, follow every volume in the loudest crowd."""
    for band in ("a few dozen", "a throng"):
        sc = _tavern()
        beside = _rel(sc, "B", crowds=_crowd(band))
        assert beside.get("din_db") is not None
        assert float(beside["paces"]) <= CONVERSATION_REACH_PACES
        assert _heard(beside, True) == {v: "full" for v in VOLUMES}, band
        elbow = _rel(sc, "E", crowds=_crowd(band))
        assert _heard(elbow, True) == _heard(elbow, False) \
            == {v: "full" for v in VOLUMES}, band


def test_the_addressee_at_the_far_table_meets_the_din():
    """Nine paces across a few dozen people's talk, a line spoken TO the far
    table arrives in pieces however it is raised; across a throng an
    ordinary voice is lost to the one it was for and a shout caught in
    pieces. The speaker's voice rises over the din (Lombard) and a watched
    face is worth its decibels: across the busy tavern a watched raised
    voice is whole. The reason says who the listener is."""
    sc = _tavern()
    far = _rel(sc, "C", crowds=_crowd("a few dozen"))
    assert far.get("din_db") is not None and far.get("paces") == 9.0
    assert float(far["din_db"]) >= DIN_DB
    assert _heard(far, True) == {v: "fragment" for v in VOLUMES}
    assert hearing_reason(far, "normal", addressed=True) == "din_beyond_reach"
    assert hearing_reason(far, "normal", addressed=False) == "din_bystander"
    assert _heard(far, True, seen=True)["loud"] == "full"
    assert _heard(far, True, seen=True)["normal"] == "fragment"
    throng = _rel(sc, "C", crowds=_crowd("a throng"))
    assert hear_level(throng, "normal", addressed=True) == "none"
    assert hear_level(throng, "shout", addressed=True) == "fragment"
    assert voice_carries(throng, "normal", addressed=True)
    # The addressee is graded as the bystander is: the same budget.
    assert _heard(far, True) == _heard(far, False)
    assert _heard(throng, True) == _heard(throng, False)


def test_a_line_to_nobody_still_caps_nothing():
    """A reader that cannot say whom the line was for caps nothing (§ 14.8):
    a line naming nobody reaches the far table whole in a throng."""
    rel = _rel(_tavern(), "C", crowds=_crowd("a throng"))
    assert _heard(rel, None) == {v: "full" for v in VOLUMES}
    assert hearing_reason(rel, "normal", addressed=None) == ""


def test_under_the_sky_a_gale_takes_a_shout_from_the_one_it_is_for():
    """In a gale a shout to someone a hundred metres (133 paces) off is
    lost and the voice does not carry; a shout across a sixteen-pace street
    is caught in pieces; six paces off, in pieces still; a pace off, whole.
    In a downpour in still air the call across the street is whole: rain is
    never a din."""
    far = _rel(_field({"A": (40, 3), "B": ("pasture", (77, 3))}, GALE), "B")
    assert far.get("din_db") is not None and far["paces"] == 133.0
    assert hear_level(far, "shout", addressed=True) == "none"
    assert not voice_carries(far, "shout", addressed=True)
    street = _rel(_field({"A": (1, 3), "B": (17, 3)}, GALE), "B")
    assert hear_level(street, "shout", addressed=True) == "fragment"
    assert hearing_reason(street, "shout", addressed=True) == "din_beyond_reach"
    near = _rel(_field({"A": (10, 3), "B": (16, 3)}, GALE), "B")
    assert hear_level(near, "shout", addressed=True) == "fragment"
    beside = _rel(_field({"A": (10, 3), "B": (11, 3)}, GALE), "B")
    assert _heard(beside, True) == {v: "full" for v in VOLUMES}
    rain = _rel(_field({"A": (1, 3), "B": (17, 3)}, DOWNPOUR), "B")
    assert "din_db" not in rain
    assert _heard(rain, True) == {v: "full" for v in VOLUMES}
