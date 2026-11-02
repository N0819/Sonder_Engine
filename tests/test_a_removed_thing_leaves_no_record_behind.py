"""`remove_entities` takes a thing out of the world, and every record that
stood it somewhere goes with it.

Audit world_spatial_truth (2026-11-01):

* F3 (CONFIRMED CORRUPTION): removing a coin Hinami carried left
  `contained['coin'] = {in: Hinami, mode: held}`, so `derive_contained_positions`
  re-placed it in the hall on every later merge and every reader of
  `contained` went on listing it as held. Its `scales` and `following` rows
  stood too.
* F4 (CONFIRMED CORRUPTION): removing an unoccupied vehicle left its interior
  room standing with its doorway: `spatial_rel(beach, console)` read
  `open_door/near` and `passable_route_exists(beach, console)` was True.
* F21 (CONFIRMED SILENT-NOOP): `remove_entities: ["brass lamp"]` for `lamp_7`
  named "brass lamp" removed nothing and said nothing.
"""

from world.spatial import (merge_scene_with_diff, passable_route_exists,
                           spatial_rel)


def _scene():
    return {
        "rooms": {"hall": {"name": "Hall", "adjacent": []}},
        "positions": {"Hinami": "hall", "coin": "hall", "lamp_7": "hall"},
        "entities": {
            "coin": {"name": "silver coin", "kind": "object", "portable": True},
            "lamp_7": {"name": "brass lamp", "kind": "object"},
        },
        "attire": {"Hinami": {}},
        "contained": {"coin": {"in": "Hinami", "mode": "held"}},
        "scales": {"coin": 0.5},
        "contacts": [],
    }


def test_a_consumed_carried_thing_is_nowhere_after_one_and_two_merges():
    merged = merge_scene_with_diff(_scene(), {"remove_entities": ["coin"]})
    assert "coin" not in merged["entities"]
    assert "coin" not in merged["positions"]
    assert "coin" not in (merged.get("contained") or {})
    assert "coin" not in (merged.get("scales") or {})
    again = merge_scene_with_diff(merged, {})
    assert "coin" not in again["positions"]
    assert "coin" not in (again.get("contained") or {})


def test_what_a_removed_holder_carried_is_released_not_left_inside_nobody():
    sc = _scene()
    sc["entities"]["satchel"] = {"name": "satchel", "kind": "object",
                                 "container": True}
    sc["positions"]["satchel"] = "hall"
    sc["contained"] = {"coin": {"in": "satchel", "mode": "container"},
                       "satchel": {"in": "Hinami", "mode": "carried"}}
    merged = merge_scene_with_diff(sc, {"remove_entities": ["satchel"]})
    assert "satchel" not in (merged.get("contained") or {})
    assert all(str((rec or {}).get("in")) != "satchel"
               for rec in (merged.get("contained") or {}).values())


def test_a_removed_follower_and_followed_leave_no_following_row():
    sc = _scene()
    sc["entities"]["dog"] = {"name": "dog", "kind": "animal"}
    sc["positions"]["dog"] = "hall"
    sc["following"] = {"dog": {"target": "Hinami"}}
    merged = merge_scene_with_diff(sc, {"remove_entities": ["dog"]})
    assert "dog" not in (merged.get("following") or {})


def test_a_removed_vehicle_takes_its_unoccupied_interior_with_it():
    sc = {
        "rooms": {
            "beach": {"name": "Beach", "adjacent": []},
            "console": {"name": "Console Room", "parent_entity": "tardis",
                        "adjacent": [{"to": "beach", "barrier": "open_door"}]},
        },
        "positions": {"Rose": "beach", "tardis": "beach"},
        "entities": {"tardis": {"name": "TARDIS", "kind": "vehicle",
                                "container": True, "interior_rooms": ["console"]}},
        "contained": {}, "contacts": [],
    }
    merged = merge_scene_with_diff(sc, {"remove_entities": ["tardis"]})
    assert "console" not in merged["rooms"]
    assert all(e.get("to") != "console"
               for e in merged["rooms"]["beach"].get("adjacent") or [])
    assert not passable_route_exists(merged, "beach", "console")


def test_an_occupied_interior_is_kept_and_the_beat_is_told():
    sc = {
        "rooms": {
            "beach": {"name": "Beach", "adjacent": []},
            "console": {"name": "Console Room", "parent_entity": "tardis",
                        "adjacent": [{"to": "beach", "barrier": "open_door"}]},
        },
        "positions": {"Rose": "console", "tardis": "beach"},
        "entities": {"tardis": {"name": "TARDIS", "kind": "vehicle",
                                "interior_rooms": ["console"]}},
        "contained": {}, "contacts": [],
    }
    report = []
    merged = merge_scene_with_diff(sc, {"remove_entities": ["tardis"]},
                                   crossing_report=report)
    assert "console" in merged["rooms"]
    assert merged["positions"]["Rose"] == "console"
    assert any("console" in note for note in report)


def test_a_thing_removed_by_its_display_name_is_removed():
    merged = merge_scene_with_diff(_scene(), {"remove_entities": ["brass lamp"]})
    assert "lamp_7" not in merged["entities"]
    assert "lamp_7" not in merged["positions"]


def test_a_removal_naming_nothing_is_reported():
    report = []
    merged = merge_scene_with_diff(_scene(), {"remove_entities": ["unicorn"]},
                                   crossing_report=report)
    assert set(merged["entities"]) == {"coin", "lamp_7"}
    assert any("unicorn" in note for note in report)


def test_an_ambiguous_name_removes_nothing_and_is_reported():
    sc = _scene()
    sc["entities"]["lamp_8"] = {"name": "brass lamp", "kind": "object"}
    report = []
    merged = merge_scene_with_diff(sc, {"remove_entities": ["brass lamp"]},
                                   crossing_report=report)
    assert {"lamp_7", "lamp_8"} <= set(merged["entities"])
    assert any("brass lamp" in note for note in report)
