"""Tests for _contextual_rooms, the payload-trimming helper used by
director_interpret, director_resolve, perception_act, and
perception_outcome to avoid serializing the entire scene.rooms dict into
every LLM call regardless of relevance.
"""

import json

from agents.common import _contextual_rooms
from character_schema import default_character_data

_CHAIN_SCENE = {
    "rooms": {
        "a": {"adjacent": [{"to": "b"}]},
        "b": {"adjacent": [{"to": "c"}]},
        "c": {"adjacent": [{"to": "d"}]},
        "d": {"adjacent": []},
    },
    "positions": {},
}

def _cast_row(name, room):
    sheet = default_character_data(name)
    return {"sheet": json.dumps(sheet)}

def test_includes_neighbors_of_every_cast_members_room():
    scene = dict(_CHAIN_SCENE, positions={"Mara": "a", "Elden": "d"})
    cast = [_cast_row("Mara", "a"), _cast_row("Elden", "d")]

    result = _contextual_rooms(scene, cast, hops=1)

    assert set(result.keys()) == {"a", "b", "c", "d"}

def test_extra_room_ids_are_included_as_centers_too():
    scene = dict(_CHAIN_SCENE, positions={"Mara": "a"})
    cast = [_cast_row("Mara", "a")]

    # e.g. the player's own room, or this turn's movement target
    result = _contextual_rooms(scene, cast, "d", hops=1)

    assert "d" in result
    assert "c" in result

def test_empty_cast_and_no_extras_returns_empty():
    result = _contextual_rooms(_CHAIN_SCENE, [], hops=1)
    assert result == {}
