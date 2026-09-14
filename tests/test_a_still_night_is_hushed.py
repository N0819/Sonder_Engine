"""A still night in the open is hushed, and a sound is made where its
source stands.

Owner's retune, 2026-09-14 (`docs/UNBUILT_PERCEPTION.md` § 1.159): a "faint"
creature dragging itself a few paces off in a dead fen night was refused at
the open air's day floor, priced from the yard's centre seven cells away.
"""
from world.spatial import AMBIENT, QUIET_SCALE, body_cell
from world.spatial import _ambient_floor, sound_sources


def _yard(*, phase=None, wind=None, exposure="open"):
    sc = {"rooms": {"yard": {"name": "Farmyard", "size": "large",
                             "exposure": exposure, "adjacent": [],
                             "anchors": {"well": {"desc": "the well-house door",
                                                  "dir": "n"}}}},
          "positions": {"A": "yard", "B": "yard"},
          "stations": {"A": {"cell": [1, 4]}, "B": {"cell": [4, 4]}},
          "orientation": {}, "poses": {}, "entities": {}, "contained": {}}
    if phase:
        sc["day_phase"] = phase
    if wind:
        sc["weather"] = {"sky": "clear", "wind": wind}
    return sc


class TestTheNightFloor:
    def test_a_still_night_in_the_open_is_six_decibels_quieter(self):
        day = _ambient_floor(_yard(phase="afternoon"), "yard")
        night = _ambient_floor(_yard(phase="night"), "yard")
        assert day == AMBIENT["open"]
        assert night == AMBIENT["open"] * QUIET_SCALE["hushed"]

    def test_a_scene_with_no_phase_is_not_a_night(self):
        assert _ambient_floor(_yard(), "yard") == AMBIENT["open"]

    def test_wind_on_the_room_is_not_still(self):
        assert _ambient_floor(_yard(phase="night", wind="wind"), "yard") \
            > AMBIENT["open"]

    def test_a_room_indoors_keeps_its_own_floor(self):
        assert _ambient_floor(_yard(phase="night", exposure="enclosed"),
                              "yard") == AMBIENT["enclosed"]


class TestWhereASoundIsMade:
    EVENT = {"kind": "sound", "room": "yard", "level": "faint",
             "source": "A", "detail": "a wet dragging"}

    def test_an_event_from_a_placed_body_starts_at_its_cell(self):
        sc = _yard()
        sources, _ = sound_sources(sc, events=[self.EVENT])
        event = next(s for s in sources if s["kind"] == "event")
        assert event["cell"] == body_cell(sc, "A")

    def test_an_event_from_nobody_the_scene_places_starts_at_the_centre(self):
        sc = _yard()
        sources, _ = sound_sources(sc, events=[dict(self.EVENT, source="the fen")])
        event = next(s for s in sources if s["kind"] == "event")
        assert event["cell"] != body_cell(sc, "A")

    def test_a_source_standing_in_another_room_does_not_move_the_sound(self):
        sc = _yard()
        sc["rooms"]["lane"] = {"name": "Lane", "size": "large",
                               "exposure": "open", "adjacent": [], "anchors": {}}
        sc["positions"]["A"] = "lane"
        sources, _ = sound_sources(sc, events=[self.EVENT])
        event = next(s for s in sources if s["kind"] == "event")
        assert event["room"] == "yard" and event["cell"] != (1, 4)
