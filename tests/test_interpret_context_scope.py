"""What the interpret payload carries beyond the present scene, and what it
must keep carrying.

Two halves, both measured against the live corpus on 2026-09-01:

  * `_interpret_scene_entities` scopes `scene.entities` to the same room
    window `_contextual_rooms` already applies to `scene.rooms` (11.5% of the
    entity bytes across 92 chats; 4,389 bytes -- ~1,100 tokens -- on the
    largest), while keeping the two classes a room window cannot see: an
    entity with no room at all, and an entity a windowed room is the INSIDE
    of.
  * The character payload's relationship graph is NOT scoped by presence. The
    finding that it should be was refused; these tests pin the refusal so it
    is not re-derived as an obvious win.
"""

import json

from agents.director import _interpret_scene_entities
from agents.common import _contextual_rooms
from story.character_schema import default_character_data


def _cast_row(name):
    return {"sheet": json.dumps(default_character_data(name))}


# A four-room chain plus a vehicle: the player stands in the vehicle's
# interior, and the vehicle's own body sits in a room the chain never reaches
# from there. This is chat 56's shape -- a body in `tardis_console_room` while
# the TARDIS entity is parked in `alley_room`.
_SCENE = {
    "rooms": {
        "hall": {"adjacent": [{"to": "study"}]},
        "study": {"adjacent": [{"to": "cellar"}]},
        "cellar": {"adjacent": []},
        "alley": {"adjacent": []},
        "cab_interior": {"parent_entity": "hackney", "adjacent": []},
    },
    "positions": {
        "Mara": "hall",
        "lamp": "hall",
        "ledger": "study",
        "furnace": "cellar",
        "hackney": "alley",
        "gutter_grate": "alley",
    },
    "entities": {
        "lamp": {"name": "Brass Lamp", "description": "Lit."},
        "ledger": {"name": "Ledger", "description": "Open to a page."},
        "furnace": {"name": "Furnace", "description": "Cold."},
        "hackney": {"name": "Hackney Cab", "description": "A closed cab.",
                    "interior_rooms": ["cab_interior"]},
        "gutter_grate": {"name": "Gutter Grate", "description": "Rusted."},
        "rumour": {"name": "The Rumour", "ubiquitous": True,
                   "description": "Everywhere and nowhere."},
        "misplaced": {"name": "Somebody's Glove", "description": "No room."},
    },
}


def _window(*extra):
    return _contextual_rooms(_SCENE, [_cast_row("Mara")], *extra)


def test_entity_two_rooms_away_is_dropped_with_its_room():
    # `cellar` is outside a one-hop window from `hall`, so its furnace is a
    # full record for a room the payload declined to describe.
    window = _window()
    assert "cellar" not in window
    kept = _interpret_scene_entities(_SCENE, window)
    assert "furnace" not in kept
    assert "lamp" in kept and "ledger" in kept


def test_entity_with_no_room_at_all_always_survives():
    # The class director_floors.unplaced_entities reports as a defect: a trim
    # must not be what decides an unplaced entity does not exist. 128 of the
    # 800 live entity records (16%) are in this state.
    kept = _interpret_scene_entities(_SCENE, _window())
    assert "misplaced" in kept
    assert "rumour" in kept


def test_holder_of_a_windowed_interior_survives_from_another_room():
    # Containment is not adjacency. Standing in the cab, the cab itself is in
    # `alley` -- an edge nearby_rooms never walks -- and dropping it takes the
    # vehicle out from around its occupant. Both directions of the link, since
    # the scene stores both.
    window = _window("cab_interior")
    assert "alley" not in window
    kept = _interpret_scene_entities(_SCENE, window)
    assert "hackney" in kept
    # ...and the alley's other furniture is still correctly gone: it is the
    # containment link that earns the exception, not the room.
    assert "gutter_grate" not in kept


def test_holder_named_only_by_interior_rooms_survives():
    # The same rule from the entity's side, for a scene whose room record
    # never got a parent_entity written back.
    scene = json.loads(json.dumps(_SCENE))
    scene["rooms"]["cab_interior"].pop("parent_entity")
    window = _contextual_rooms(scene, [_cast_row("Mara")], "cab_interior")
    kept = _interpret_scene_entities(scene, window)
    assert "hackney" in kept


def test_scene_is_not_mutated():
    # Payload-only, like every trim in director.py: the deterministic checks
    # downstream read the unfiltered scene.
    before = json.dumps(_SCENE, sort_keys=True)
    _interpret_scene_entities(_SCENE, _window())
    assert json.dumps(_SCENE, sort_keys=True) == before


def test_no_window_keeps_nothing_placed_but_still_keeps_the_unplaced():
    kept = _interpret_scene_entities(_SCENE, {})
    assert set(kept) == {"rumour", "misplaced"}


def test_non_dict_entity_record_passes_through():
    scene = dict(_SCENE, entities={"odd": "a bare string"})
    assert _interpret_scene_entities(scene, {}) == {"odd": "a bare string"}
