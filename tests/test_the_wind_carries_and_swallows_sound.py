"""THE WIND (DESIGN_SOUND_FIELD.md § 14.2, wave B2, 2026-10-20).

Outdoors the wind does two things to sound, and the engine did neither:

  1. WIND AT THE EAR IS NOISE. The air moving round the head and the outer
     ear is roughly 50-70 dB(A) in a strong wind. `WIND_NOISE` priced a gale
     at 40 dB, under a quiet room's talk. Now a strong wind is a din at the
     ear, with what a din does (§ 12.1): a bystander beyond conversational
     reach catches pieces of a conversation a few paces off; the people
     talking to each other follow it; rain is still never a din.
  2. WIND BENDS A SOUND'S REACH BY DIRECTION. Wind blows faster a few metres
     up, so a sound going with it is bent down and carried, one going
     against it bent up into a shadow that swallows it -- 10-20 dB upwind at
     long range, a few decibels downwind, nothing across the wind. The
     weather record had no quarter for the wind; it now has one,
     `wind_from`, on the engine's own compass.

And one hole the build found on the way: two places under the sky joined by
an opening -- a square and the street beside it -- were graded by the
opening row, whole at any distance, while one place of the same length
fell off with distance. They are one stretch of open air.

A call across a street in a gale is untouched: a path that short is not
bent, and a line spoken to its listener is never capped by a din.
"""

from __future__ import annotations

from world.causal_verification import _weather_receipts
from world.spatial import (DIN_DB, WIND_NOISE_DB, db_of_power, distant_sounds,
                           hear_level, hearing_reason, noise_word_db,
                           sound_field, spatial_rel_between, wind_bend_db)
from world.weather import WIND_FROM_KEY, advance_weather, normalize_weather

VOLUMES = ("normal", "loud", "shout")


def _field(cells, weather=None, exposure="open"):
    """One field ninety-six paces long, the bodies stationed where the test
    says."""
    sc = {"rooms": {"field": {"name": "the field", "exposure": exposure,
                              "extent": {"w": 96, "d": 6}, "anchors": {},
                              "adjacent": []}},
          "positions": {k: "field" for k in cells},
          "stations": {k: {"cell": list(v)} for k, v in cells.items()},
          "entities": {}, "poses": {}, "orientation": {}, "contained": {}}
    if weather:
        sc["weather"] = weather
    return sc


def _two_fields(a, b, weather=None, *, meadow="open"):
    """A meadow and, east of it through a gap in the hedge, a pasture --
    each ninety-six paces long. `a` and `b` are (room, cell) for the
    speaker A and the listener B."""
    def room(name, exposure, adjacent):
        return {"name": name, "exposure": exposure, "extent": {"w": 96, "d": 6},
                "anchors": {}, "adjacent": adjacent}
    sc = {"rooms": {"meadow": room("the meadow", meadow,
                                   [{"to": "pasture", "barrier": "open",
                                     "dir": "e"}]),
                    "pasture": room("the pasture", "open",
                                    [{"to": "meadow", "barrier": "open",
                                      "dir": "w"}])},
          "positions": {"A": a[0], "B": b[0]},
          "stations": {"A": {"cell": list(a[1])}, "B": {"cell": list(b[1])}},
          "entities": {}, "poses": {}, "orientation": {}, "contained": {}}
    if weather:
        sc["weather"] = weather
    return sc


def _rel(sc, listener="B", speaker="A"):
    return spatial_rel_between(sc, listener, speaker,
                               sound=sound_field(sc, listener))


GALE = {"sky": "overcast", "cloud": "covered", "wind": "gale"}
WIND = {"sky": "overcast", "cloud": "covered", "wind": "wind"}
DOWNPOUR = {"precipitation": "rain", "precipitation_kind": "liquid",
            "intensity": "heavy", "sky": "storm", "cloud": "covered",
            "wind": "still"}


def test_a_strong_wind_is_a_din_at_the_ear():
    """In a gale a bystander six paces off catches pieces of a conversation
    not meant for them; the one it is said to, and the body at the speaker's
    elbow, follow it whole. A strong wind is a din too, and heavy rain in
    still air is still never one (the owner's rain ruling)."""
    cells = {"A": (10, 3), "E": (12, 3), "B": (16, 3)}
    gale = _field(cells, GALE)
    at_b = sound_field(gale, "B").noise_at("B")
    assert db_of_power(at_b) >= DIN_DB
    assert noise_word_db(db_of_power(at_b)) == "din"
    rel = _rel(gale)
    assert rel.get("din_db") is not None
    assert hear_level(rel, "normal", addressed=False) == "fragment"
    assert hearing_reason(rel, "normal", addressed=False) == "din_bystander"
    assert {v: hear_level(rel, v, addressed=True) for v in VOLUMES} == \
        {v: "full" for v in VOLUMES}
    elbow = _rel(gale, "E")
    assert {v: hear_level(elbow, v, addressed=False) for v in VOLUMES} == \
        {v: "full" for v in VOLUMES}
    assert WIND_NOISE_DB["wind"] >= DIN_DB
    assert _rel(_field(cells, WIND)).get("din_db") is not None
    rain = _rel(_field(cells, DOWNPOUR))
    assert "din_db" not in rain
    assert hear_level(rain, "normal", addressed=False) == "full"


def test_two_places_under_the_sky_are_one_stretch_of_air():
    """A hundred and forty paces from the meadow into the pasture through
    the gap: an ordinary voice is in pieces, as it is across one field of
    that length; a barn's doorway onto the same pasture is still a room's
    opening, and its ring carries a voice through whole."""
    across = _rel(_two_fields(("meadow", (40, 3)), ("pasture", (84, 3))))
    assert across.get("paces") == 140.0
    assert across.get("open_air_loss_db") is not None
    one_field = _rel(_field({"A": (1, 3), "B": (95, 3)}))
    assert hear_level(across, "normal") == hear_level(one_field, "normal") \
        == "fragment"
    assert hearing_reason(across, "normal") == "open_air_distance"
    barn = _rel(_two_fields(("meadow", (40, 3)), ("pasture", (84, 3)),
                            meadow="enclosed"))
    assert "open_air_loss_db" not in barn
    assert hear_level(barn, "normal") == "full"


def test_the_wind_carries_a_voice_downwind_and_swallows_it_upwind():
    """The same hundred and forty paces in a westerly gale: a raised voice
    going east, with the wind, is followed whole; the same voice coming
    west, into it, is caught in pieces; with the wind blowing across the
    path, or no quarter named, nothing bends. A street's width upwind is
    too short a path to bend at all: a call across it carries."""
    westerly = dict(GALE, **{WIND_FROM_KEY: "w"})
    downwind = _rel(_two_fields(("meadow", (40, 3)), ("pasture", (84, 3)),
                                westerly))
    upwind = _rel(_two_fields(("pasture", (84, 3)), ("meadow", (40, 3)),
                              westerly))
    assert downwind.get("wind_bend_db", 0.0) > 0.0
    assert upwind.get("wind_bend_db", 0.0) < 0.0
    assert hear_level(downwind, "loud", addressed=True) == "full"
    assert hear_level(upwind, "loud", addressed=True) == "fragment"
    assert hearing_reason(upwind, "loud", addressed=True) == "upwind"
    assert hear_level(upwind, "shout", addressed=True) == "full"
    across = _rel(_two_fields(("meadow", (40, 3)), ("pasture", (84, 3)),
                              dict(GALE, **{WIND_FROM_KEY: "n"})))
    assert "wind_bend_db" not in across
    nameless = _rel(_two_fields(("pasture", (84, 3)), ("meadow", (40, 3)),
                                GALE))
    assert "wind_bend_db" not in nameless
    assert hear_level(nameless, "loud", addressed=True) == "full"
    street = _rel(_field({"A": (20, 3), "B": (4, 3)}, westerly))
    assert wind_bend_db(_field({}, westerly), "w", 12.0) == 0.0
    assert "wind_bend_db" not in street
    assert {v: hear_level(street, v, addressed=True) for v in VOLUMES} == \
        {v: "full" for v in VOLUMES}


def _open_chain(weather):
    """Four open fields in a row west to east, a bell rung in the first and
    a listener at the far end of the fourth."""
    rooms = {}
    for i in range(4):
        adjacent = []
        if i:
            adjacent.append({"to": "r%d" % (i - 1), "barrier": "open",
                             "dir": "w"})
        if i < 3:
            adjacent.append({"to": "r%d" % (i + 1), "barrier": "open",
                             "dir": "e"})
        rooms["r%d" % i] = {"name": "field %d" % i, "exposure": "open",
                            "extent": {"w": 96, "d": 6}, "anchors": {},
                            "adjacent": adjacent}
    return {"rooms": rooms, "positions": {"L": "r3"},
            "stations": {"L": {"cell": [90, 3]}}, "weather": weather,
            "entities": {}, "poses": {}, "orientation": {}, "contained": {}}


BELL = [{"kind": "sound", "source_room": "r0", "level": "thunderous",
         "detail": "a great bell tolling"}]


def test_a_far_bell_carries_downwind_and_falls_into_the_shadow_upwind():
    """Three hundred metres of open fields in a strong wind: a great bell
    rung with the wind behind it reaches the far field plainly; rung into
    the wind it arrives faint; and with no quarter named it is as it was."""
    def heard(quarter):
        weather = dict(WIND, **({WIND_FROM_KEY: quarter} if quarter else {}))
        out = distant_sounds(_open_chain(weather), "L", room="r3",
                             events=BELL)
        assert out, quarter
        return out[0]
    still, down, up = heard(None), heard("w"), heard("e")
    assert down["db"] > still["db"] > up["db"]
    assert down["level"] == still["level"] == "plain"
    assert up["level"] == "faint"


def test_the_wind_keeps_its_quarter():
    """`wind_from` is an axis on the engine's own compass: read as a bearing
    is read anywhere, carried by a later record that does not restate it
    and by the drift, which walks the wind's strength and never its
    quarter; absent from a record that never named it, so an old sky
    serializes exactly as it did; and a beat that names it is not refused
    as an unknown field."""
    assert normalize_weather({"wind": "gale", WIND_FROM_KEY: "West"})[
        WIND_FROM_KEY] == "w"
    assert WIND_FROM_KEY not in normalize_weather({"wind": "gale",
                                                   WIND_FROM_KEY: "behind"})
    assert WIND_FROM_KEY not in normalize_weather({"wind": "gale"})
    carried = normalize_weather({"wind": "wind"},
                                base={"wind": "gale", WIND_FROM_KEY: "sw"})
    assert carried[WIND_FROM_KEY] == "sw"
    drifted = advance_weather({"wind": "gale", WIND_FROM_KEY: "ne"},
                              3 * 3600, "seed")
    assert drifted[WIND_FROM_KEY] == "ne"
    receipts = _weather_receipts({"weather": {"wind": "gale"}},
                                 {"weather": {"wind": "gale",
                                              WIND_FROM_KEY: "n"}},
                                 {WIND_FROM_KEY: "n"})
    assert receipts and not receipts[0].get("ignored"), receipts
