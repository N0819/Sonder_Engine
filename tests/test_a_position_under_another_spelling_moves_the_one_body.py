"""A position written under another spelling of a standing body moves THAT
body -- the fresh write wins, as it already does for `stations` and `poses`.

Audit world_spatial_truth F9 (2026-11-01, CONFIRMED WRONG-SCENE): the merge
`update`d `positions` blind, and `normalize_scene_subjects` keeps the record
already standing under the canonical spelling. So with a cast entity
`mel_01` named Mellisande (alias Mel) standing in the hall,
`{'positions': {'Mel': 'kitchen'}}` came back `{'Mellisande': 'hall'}` -- the
move discarded -- and `{'positions': {'HINAMI': 'yard'}}` came back
`{'Hinami': 'hall', 'HINAMI': 'yard'}`: one body in two rooms.
`_onto_standing_spellings` already fixed this for stations and poses.
"""

from world.spatial import merge_scene_with_diff, room_of


def _scene():
    return {
        "rooms": {"hall": {"name": "Hall", "adjacent": [
                      {"to": "kitchen", "barrier": "open_door"},
                      {"to": "yard", "barrier": "open_door"}]},
                  "kitchen": {"name": "Kitchen", "adjacent": [
                      {"to": "hall", "barrier": "open_door"}]},
                  "yard": {"name": "Yard", "adjacent": [
                      {"to": "hall", "barrier": "open_door"}]}},
        "positions": {"Mellisande": "hall", "Hinami": "hall", "Ann": "hall"},
        "entities": {"mel_01": {"name": "Mellisande", "kind": "person",
                                "aliases": ["Mel"]},
                     "hin_01": {"name": "Hinami", "kind": "person"}},
        "attire": {"Mellisande": {}, "Hinami": {}, "Ann": {}},
        "contained": {}, "contacts": [],
    }


def test_an_alias_moves_the_body_it_names():
    merged = merge_scene_with_diff(_scene(), {"positions": {"Mel": "kitchen"}})
    assert room_of(merged, "Mellisande") == "kitchen"
    assert [k for k, v in merged["positions"].items()
            if k.casefold() in ("mel", "mellisande")] == ["Mellisande"]


def test_a_case_variant_moves_the_one_body_and_leaves_no_twin():
    merged = merge_scene_with_diff(_scene(), {"positions": {"HINAMI": "yard"}})
    keys = [k for k in merged["positions"] if k.casefold() == "hinami"]
    assert keys == ["Hinami"]
    assert merged["positions"]["Hinami"] == "yard"


def test_a_case_variant_of_a_body_with_no_entity_moves_it_too():
    merged = merge_scene_with_diff(_scene(), {"positions": {"ann": "yard"}})
    keys = [k for k in merged["positions"] if k.casefold() == "ann"]
    assert keys == ["Ann"]
    assert merged["positions"]["Ann"] == "yard"


def test_the_entity_key_spelling_still_works():
    merged = merge_scene_with_diff(_scene(), {"positions": {"mel_01": "kitchen"}})
    assert room_of(merged, "Mellisande") == "kitchen"
