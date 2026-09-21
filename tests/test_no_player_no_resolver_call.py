"""A scene that places nobody but the cast has not placed the player.

`_resolve_player_room` walks a ladder and, where it cannot answer, pays a
utility model call to pick the player's body out of the scene. The last rung
asked "are there any positions at all" rather than "is there anything here
that could BE the player", so a frame holding only cast bodies -- every beat
of a causality bubble, and every playerless story -- bought a model call per
perception stage to look for somebody who is not in it.

Measured (Aldermill, two causality bubbles, 2026-09-19): 120 calls, 274
seconds and 185,618 input tokens across 60 beats, every answer empty.

It is not only waste. `_llm_resolve_player_room` offers the scene's BODIES as
the keys to choose from, and a cast body is a body: the only thing standing
between "which of these is the player" and the answer "Emory Vane" was the
model declining to pick one. A question with no right answer should not be
asked.
"""

import agents.common as common


def _no_call(*_a, **_k):
    raise AssertionError(
        "the player-room resolver asked a model to find a player in a scene "
        "that places only cast bodies")


def test_a_cast_only_scene_resolves_to_none_without_a_call(monkeypatch):
    monkeypatch.setattr(common, "_llm_resolve_player_room", _no_call)
    scene = {
        "positions": {"Emory Vane": "mill_floor"},
        "entities": {"char_emory_vane": {"name": "Emory Vane",
                                         "kind": "person"}},
        "rooms": {"mill_floor": {"name": "Aldermill Grinding Floor"}},
    }
    cast = [{"id": 2, "sheet": '{"identity": {"name": "Emory Vane"}}'}]
    assert common._resolve_player_room(
        scene, {"name": "Nobody"}, {}, cast) is None


def test_two_candidate_bodies_still_reach_the_resolver(monkeypatch):
    """The narrowing must not close the question the resolver exists for:
    a scene really standing two non-cast bodies in two rooms is ambiguous,
    and that is the case the call was bought for."""
    asked = []

    def _spy(sc, pers, cast, interp, player_input):
        asked.append(True)
        return "study"

    monkeypatch.setattr(common, "_llm_resolve_player_room", _spy)
    scene = {
        "positions": {"Emory Vane": "mill_floor", "stove": "kitchen",
                      "boat": "study"},
        "entities": {
            "char_emory_vane": {"name": "Emory Vane", "kind": "person"},
            "stove": {"name": "stove", "kind": "person"},
            "boat": {"name": "boat", "kind": "person"}},
        "rooms": {"mill_floor": {}, "kitchen": {}, "study": {}},
    }
    cast = [{"id": 2, "sheet": '{"identity": {"name": "Emory Vane"}}'}]
    assert common._resolve_player_room(
        scene, {"name": "Nobody"}, {}, cast) == "study"
    assert asked, "two candidates is the ambiguity the resolver is for"
