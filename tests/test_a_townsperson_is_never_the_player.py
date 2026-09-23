"""A body the charter owns is never the player the scene failed to place.

Playerless Aldermill round 5 (2026-09-23): once the scene stood charter bodies
under their display names, the player-room resolver took the one townsperson
on screen for the absent persona, and with two in two rooms bought a model
call on both perception stages to choose between them -- 35 calls and 196s
over the run, none in the round before.
"""
import json

import agents.common as common
from story.character_schema import default_character_data


def _scene(*bodies):
    positions = {"Sal Weatherby": "smithy"}
    entities = {}
    for name, room in bodies:
        positions[name] = room
        entities[name] = {"name": name, "kind": "person",
                          "charter_ref": {"charter": "smiths", "body": name.lower()}}
    return {"rooms": {"smithy": {"name": "Smithy"}, "weir": {"name": "Weir"}},
            "positions": positions, "entities": entities}


CAST = [{"id": 1, "sheet": json.dumps(default_character_data("Sal Weatherby"))}]


def test_two_townspeople_in_two_rooms_ask_no_model(monkeypatch):
    monkeypatch.setattr(common, "_llm_resolve_player_room",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("asked a model to place a townsperson")))
    sc = _scene(("Walrice Ironforder", "smithy"), ("Robelon Wateringer", "weir"))
    assert common._resolve_player_room(sc, {"name": "Nobody"}, None, CAST) is None


def test_one_townsperson_does_not_place_the_absent_persona():
    sc = _scene(("Walrice Ironforder", "weir"))
    assert common._resolve_player_room(sc, {"name": "Nobody"}, None, CAST) is None


def test_an_unidentified_lone_body_is_still_the_guess():
    sc = {"rooms": {"smithy": {}}, "positions": {"Sal Weatherby": "smithy",
                                                 "the stranger": "smithy"},
          "entities": {}}
    assert common._resolve_player_room(sc, {"name": "Nobody"}, None, CAST) == "smithy"
