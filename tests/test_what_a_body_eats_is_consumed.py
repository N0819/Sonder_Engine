"""What a body eats or drinks is consumed.

Measured on the owner's chat 177 (2026-10-19): at turn 17 the encoder wrote
Mellisande's supper as `substance_ops add {source: second_soup_bowl, target:
Mellisande, placement: interior, target_interior: mouth}` -- the only shape
the op vocabulary has -- and "a spoonful of soup" stood in her mouth through
turn 22, in bed; her memory kept "My mouth registers a spoonful of soup of
soup being deposited within it".

The rule is structural (`spatial_substance.taken_in`): matter placed INSIDE a
body from a source that is no body is taken in. It leaves its origin, it is
the beat's event, and nothing of it stands afterwards. Matter one body leaves
inside another stands, as it always did.
"""

from __future__ import annotations

import copy

from world.spatial import (apply_substance_ops, merge_scene_with_diff,
                           resolve_substance_ops, substance_ledger_index)


def _supper():
    """Chat 177's kitchen at turn 17, cut to what the soup touches."""
    scene = {
        "rooms": {"cottage_kitchen": {"name": "The Kitchen", "adjacent": []}},
        "positions": {"Mellisande": "cottage_kitchen", "Hinami": "cottage_kitchen",
                      "second_soup_bowl": "cottage_kitchen"},
        "attire": {"Mellisande": {"garments": []}, "Hinami": {"garments": []}},
        "entities": {"second_soup_bowl": {
            "name": "the second earthenware bowl of soup", "kind": "object",
            "portable": True, "container": True, "state": {}}},
        "contacts": [],
        "substances": [],
    }
    soup = {"op": "add", "source": "the range", "substance": "soup",
            "target": "second_soup_bowl", "placement": "contained",
            "amount": "a bowlful", "amount_band": "moderate"}
    scene = apply_substance_ops(scene, [soup])
    return scene


def _eat(scene, **overrides):
    pool = next(row for row in substance_ledger_index(scene)
                if row.get("target") == "second_soup_bowl")
    op = {"op": "add", "source": "second_soup_bowl", "source_part": "interior",
          "source_substance_id": pool["substance_id"], "portion": "some",
          "substance": "soup", "target": "Mellisande", "placement": "interior",
          "target_interior": "mouth", "amount": "a spoonful of soup",
          "amount_band": "small", "detail": "eaten slow and unhurried"}
    op.update(overrides)
    return op


def _inside(scene, body):
    return [row for row in scene.get("substances") or []
            if row.get("target") == body and row.get("placement") == "interior"]


def test_a_spoonful_eaten_leaves_the_bowl_and_stands_nowhere():
    scene = _supper()
    op = _eat(scene)
    # Matter one body leaves inside another is a deposit, and still stands.
    deposit = {"op": "add", "source": "Hinami", "source_part": "mouth",
               "substance": "breath-warmed tea", "target": "Mellisande",
               "placement": "interior", "target_interior": "mouth",
               "amount": "a mouthful", "amount_band": "small"}
    # The beat's own event is still delivered to the eater.
    events = resolve_substance_ops(scene, [op])
    assert len(events) == 1 and events[0]["target"] == "Mellisande"
    after = merge_scene_with_diff(copy.deepcopy(scene), {"substance_ops": [op, deposit]})
    assert [row["substance"] for row in _inside(after, "Mellisande")] == ["breath-warmed tea"]
    bowl = [row for row in after["substances"] if row.get("target") == "second_soup_bowl"]
    assert len(bowl) == 1 and bowl[0]["amount_band"] == "small"   # some of it went
    # ...and no soup reaches the next beat's encoder as standing in her mouth.
    assert [row["substance"] for row in substance_ledger_index(after)
            if row.get("target") == "Mellisande"] == ["breath-warmed tea"]


def test_a_scene_saved_with_an_eaten_mouthful_heals_on_the_next_merge():
    """Chat 177's own stored row, from turn 18 on."""
    scene = _supper()
    scene["substances"].append({
        "source": "second_soup_bowl", "source_part": "interior", "substance": "soup",
        "target": "Mellisande", "placement": "interior", "target_interior": "mouth",
        "amount": "spoonfuls and soaked scone", "amount_band": "small",
        "substance_id": "substance:5d0f0f0f0f0f0f0f0f0f"})
    after = merge_scene_with_diff(copy.deepcopy(scene), {})
    assert _inside(after, "Mellisande") == []
    assert any(row.get("target") == "second_soup_bowl" for row in after["substances"])
