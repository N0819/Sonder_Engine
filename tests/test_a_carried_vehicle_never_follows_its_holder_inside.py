"""A thing carried by a body that walks into the thing's own interior is
released, not taken in after them.

Audit world_spatial_truth F6 (2026-11-01, CONFIRMED CORRUPTION): with the
police box recorded `held` by the Doctor (chat 151's shape), a Doctor who
steps through its doors left `positions == {'tardis': 'console', 'Doctor':
'console'}` on every merge: `evict_self_contained_entities` runs BEFORE
`derive_contained_positions`, which puts the box back where its holder is, and
the containment cycle check walks the ledger form only, so a cycle that runs
through the place form (`parent_entity`) was refused by nothing.
`tests/test_nothing_is_inside_itself.py` builds its fixture with
`contained: {}`, the one shape where the eviction sticks.
"""

from world.spatial import merge_scene_with_diff


def _scene():
    return {
        "rooms": {
            "beach": {"name": "Beach", "adjacent": []},
            "console": {"name": "Console Room", "parent_entity": "ship",
                        "adjacent": [{"to": "beach", "barrier": "open_door"}]},
        },
        "positions": {"Doc": "beach", "ship": "beach"},
        "entities": {"ship": {"name": "The Ship", "container": True,
                              "interior_rooms": ["console"],
                              "state": {"hatch": "open"}}},
        "attire": {"Doc": {}},
        "stations": {}, "contained": {"ship": {"in": "Doc", "mode": "held"}},
        "contacts": [],
    }


def test_walking_into_a_carried_thing_does_not_take_it_inside():
    merged = merge_scene_with_diff(_scene(), {"positions": {"Doc": "console"}})
    assert merged["positions"]["Doc"] == "console"
    assert merged["positions"].get("ship") != "console"
    assert "ship" not in merged["contained"]
    again = merge_scene_with_diff(merged, {})
    assert again["positions"].get("ship") != "console"


def test_a_stored_paradox_heals_on_the_next_merge():
    sc = _scene()
    sc["positions"] = {"Doc": "console", "ship": "console"}
    merged = merge_scene_with_diff(sc, {})
    assert merged["positions"].get("ship") == "beach"
    assert "ship" not in merged["contained"]


def test_a_holder_outside_keeps_carrying_it():
    merged = merge_scene_with_diff(_scene(), {})
    assert merged["contained"]["ship"]["in"] == "Doc"
    assert merged["positions"]["ship"] == "beach"
