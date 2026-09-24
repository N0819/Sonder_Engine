"""A body the Director moves stands in a room that stands.

The owner's chat 137 idx 47 (round 5, 2026-09-23): the encoder placed the
player in `char_mirelle_sulmirath_stomach`, a room it named itself and
nothing built -- the prose author's place list was empty after a runaway --
and perception_outcome crashed on a body standing in no room, both attempts,
losing the beat. A room nothing holds is a new place for the room author;
a place still unbuilt holds no one; and perception never falls over a
station it cannot measure.
"""

from __future__ import annotations

from agents import director_prose
from world import spatial as fov


def _scene():
    return {
        "rooms": {
            "treatment_room": {"name": "Treatment Room", "adjacent": []},
            "char_mirelle_sulmirath_throat": {
                "name": "Throat", "parent_entity": "char_mirelle_sulmirath",
                "adjacent": [{"to": "treatment_room", "barrier": "membrane"}]},
        },
        "entities": {"char_mirelle_sulmirath": {"name": "Mirelle Sulmirath"}},
        "positions": {"Hinami": "char_mirelle_sulmirath_throat",
                      "Mirelle Sulmirath": "treatment_room"},
    }


def _placed(room):
    return {"source_entity_id": "persona:10", "event": "She slides down.",
            "transforms": [{"item": "Hinami", "patch": {"positions": {"Hinami": room}}}]}


def _rooms_of(events):
    out = []
    for event in events:
        for transform in event.get("transforms") or []:
            out.extend((transform.get("patch") or {}).get("positions", {}).values())
        if isinstance(event.get("movement"), dict):
            out.append(event["movement"]["to_room"])
    return out


def test_a_room_nothing_holds_is_a_new_place():
    warned = []
    events = [_placed("char_mirelle_sulmirath_stomach"),
              _placed("char_mirelle_sulmirath_throat"),       # held
              _placed("Throat"),                              # held, by its words
              _placed("Mirelle Sulmirath"),                   # a holder
              _placed("new:the stomach"),                     # already new
              {"event": "She walks.", "movement": {"to_room": "back_garden"}}]
    out = director_prose.unheld_places_are_new(events, _scene(), warn=warned.append)
    assert _rooms_of(out) == ["new:char mirelle sulmirath stomach",
                              "char_mirelle_sulmirath_throat", "Throat",
                              "Mirelle Sulmirath", "new:the stomach",
                              "new:back garden"]
    assert director_prose.new_place_refs(out) == [
        "char mirelle sulmirath stomach", "the stomach", "back garden"]
    assert warned and "char_mirelle_sulmirath_stomach" in warned[0]
    assert _rooms_of(events)[0] == "char_mirelle_sulmirath_stomach"   # copied


def test_a_reserved_place_is_not_new_again():
    out = director_prose.unheld_places_are_new(
        [_placed("stomach")], _scene(), new_ids={"stomach"})
    assert _rooms_of(out) == ["stomach"]


def test_a_place_nothing_built_holds_no_one():
    warned = []
    events = [_placed("new:char mirelle sulmirath stomach"),
              _placed("char_mirelle_sulmirath_throat"),
              _placed("stomach_built_now"),
              {"event": "She walks.", "movement": {"to_room": "new:back garden"}}]
    out = director_prose.bodies_stand_in_rooms(
        events, _scene(), built={"stomach_built_now": {}}, warn=warned.append)
    assert _rooms_of(out) == ["char_mirelle_sulmirath_throat",
                              "stomach_built_now", "new:back garden"]
    assert out[0]["transforms"] == []
    assert warned and "stay where they stood" in warned[0]


def test_a_room_the_encoder_writes_this_beat_stands():
    events = [{"event": "A hatch opens onto a crawlspace.", "transforms": [
        {"item": "crawlspace", "patch": {"rooms": {"crawlspace": {"name": "Crawlspace"}}}},
        {"item": "Hinami", "patch": {"positions": {"Hinami": "crawlspace"}}}]}]
    out = director_prose.bodies_stand_in_rooms(events, _scene())
    assert _rooms_of(out) == ["crawlspace"]


def test_perception_keeps_its_verdict_for_a_station_in_no_room():
    sc = {
        "rooms": {"hall": {"name": "Hall", "extent": {"w": 4, "d": 4},
                           "shape": "rectangle", "adjacent": []}},
        "positions": {"Ann": "stomach_never_built", "Bo": "stomach_never_built"},
        "stations": {"Ann": {"cell": [1, 1]}, "Bo": {"cell": [2, 2]}},
        "entities": {}, "contacts": [],
    }
    view = fov.body_visibility(sc, "Ann", "Bo")
    assert view["visible"] is True and view["basis"] == "open"
