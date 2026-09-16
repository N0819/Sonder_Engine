"""One typed relation may account for several objects in a causal span."""

import pytest

from agents import director
from world.causal_completion import execution_receipt
from world.spatial import merge_scene_with_diff


def _scene():
    return {"rooms": {"room": {"name": "Room", "adjacent": []}},
            "entities": {"tin": {"name": "Brass tin", "kind": "item", "state": {"open": False}},
                         "cup": {"name": "White cup", "kind": "item", "state": {"open": False}}},
            "positions": {key: "room" for key in ("tin", "cup", "Sera", "Tomas")},
            "attire": {"Sera": {"wearing": []}, "Tomas": {"wearing": []}},
            "contacts": [], "contained": {}}


def _requirements(scene, patch, items, *, hand="contact", primary=1, history=None):
    ledger = {"chrono_id": 1, "item_ids": list(range(1, len(items) + 1)),
              "item_names": items, "categories": list(patch)}
    history = history if history is not None else [{
        "chrono_id": 1, "item_id": primary, "specialist": hand, "patch": patch}]
    dispatch = {hand: {"run": True, "ledger_items": [ledger], "results": [{"status": "encoded"}]}}
    requirements = director._causal_completion_requirements(dispatch, history, scene=scene)
    return ledger, history, requirements


def test_one_contact_patch_accounts_for_actor_and_object_without_duplicate_ops():
    before = _scene()
    patch = {"contact_ops": [{"op": "add", "actor": "Sera", "actor_part": "hand",
                              "target": "tin", "target_part": "", "manner": "touch",
                              "relation": "surface"}]}
    ledger, history, requirements = _requirements(before, patch, ["Sera", "Brass tin"])
    assert [r["status"] for r in requirements] == ["proposed", "proposed", "proposed"]
    assert requirements[-1]["transform_indices"] == [0]
    after = merge_scene_with_diff(before, patch)
    receipt = execution_receipt(before, after, {"chrono_id": 1, "patch": patch,
        "transforms": history, "requirements": requirements})
    assert receipt["status"] == "applied"
    assert len(receipt["effects"]) == 1
    verdicts, missing, notes = [], [], []
    director._account_for_every_thing(ledger, {"settled": {}}, history, 1, "encoded",
                                      verdicts, missing, notes, 0, before)
    assert [v["status"] for v in verdicts] == ["encoded", "encoded"]
    assert not missing and not notes


def test_one_transfer_accounts_for_object_and_both_holders():
    before = _scene()
    before["contained"]["tin"] = {"in": "Sera", "mode": "held"}
    patch = {"inventory_ops": [{"object_id": "tin", "from_id": "Sera", "to_id": "Tomas", "relation": "held"}]}
    _, history, requirements = _requirements(before, patch, ["Brass tin", "Sera", "Tomas"], hand="objects")
    assert all(row["status"] == "proposed" for row in requirements)
    after = merge_scene_with_diff(before, patch)
    assert execution_receipt(before, after, {"chrono_id": 1, "patch": patch,
        "transforms": history, "requirements": requirements})["status"] == "applied"


def test_tin_effect_never_acquits_an_untransformed_cup_or_a_prose_mention():
    before = _scene()
    patch = {"entities": {"tin": {"state": {"open": True, "note": "beside White cup"}}}}
    _, history, requirements = _requirements(before, patch, ["Brass tin", "White cup"], hand="objects")
    assert requirements[-1]["status"] == "unresolved"
    assert requirements[-1]["transform_indices"] == []
    after = merge_scene_with_diff(before, patch)
    receipt = execution_receipt(before, after, {"chrono_id": 1, "patch": patch,
        "transforms": history, "requirements": requirements})
    assert receipt["status"] == "unresolved"
    assert any(row.get("item") == "White cup" and row["code"] == "missing_effect"
               for row in receipt["effects"] if row["status"] == "unresolved")


def test_station_near_reference_does_not_settle_the_other_subject():
    before = _scene()
    patch = {"stations": {"tin": {"near": ["Tomas"]}}}
    _, _, requirements = _requirements(before, patch, ["Brass tin", "Tomas"], hand="spatial")
    assert requirements[-1]["status"] == "unresolved"


def test_shared_relation_joins_its_exact_transform_among_several_hands():
    before = _scene()
    contact = {"contact_ops": [{"op": "add", "actor": "Sera", "target": "tin",
                               "manner": "touch", "relation": "surface"}]}
    objects = {"entities": {"tin": {"state": {"open": True}}}}
    history = [{"chrono_id": 1, "item_id": 2, "specialist": "objects", "patch": objects},
               {"chrono_id": 1, "item_id": 1, "specialist": "contact", "patch": contact}]
    _, _, requirements = _requirements(before, contact, ["Sera", "Brass tin"], history=history)
    assert [r["transform_indices"] for r in requirements if r.get("item_id") is not None] == [[1], [1]]
    after = merge_scene_with_diff(before, {**contact, **objects})
    receipt = execution_receipt(before, after, {"chrono_id": 1, "patch": {**contact, **objects},
        "transforms": history, "requirements": requirements})
    assert receipt["status"] == "applied"
    assert [effect["transform_index"] for effect in receipt["effects"]] == [0, 1]


def test_shared_identical_names_do_not_collapse_two_item_handles():
    before = _scene()
    patch = {"entities": {"cup": {"state": {"open": True}}}}
    _, _, requirements = _requirements(before, patch, ["White cup", "White cup"], hand="objects")
    assert requirements[1]["status"] == "proposed"
    assert requirements[2]["status"] == "unresolved"


def test_cross_hand_reasserted_same_span_contact_is_visible_to_inventory_check():
    before = _scene()
    before["contained"]["tin"] = {"in": "Sera", "mode": "held"}
    inventory = {"inventory_ops": [{"object_id": "tin", "from_id": "Sera", "to_id": "room"}]}
    contact = {"contact_ops": [{"op": "add", "actor": "Sera", "actor_part": "hand",
                               "target": "tin", "target_part": "", "manner": "grip",
                               "relation": "surface"}]}
    patch = {**inventory, **contact}
    after = merge_scene_with_diff(before, patch)
    receipt = execution_receipt(before, after, {"chrono_id": 1, "patch": patch, "transforms": [
        {"item_id": 1, "specialist": "objects", "patch": inventory},
        {"item_id": 1, "specialist": "contact", "patch": contact}]})
    assert receipt["status"] == "applied"
    assert receipt["action_status"] == "applied"


@pytest.mark.parametrize("standing", [
    {"positions": {"Ivo": "room"}},
    {"attire": {"Ivo": {"wearing": []}}},
    {"scales": {"Ivo": {"height_ratio": 1}}},
    {"entities": {"ivo": {"name": "Ivo", "kind": "person"}}},
    {"rooms": {"ivo": {"name": "Ivo"}}},
])
def test_known_primary_cannot_be_settled_by_an_unrelated_tag_mint(standing):
    patch = {"entities": {"tag": {"name": "Yellow tag", "kind": "item"}}}
    _, _, requirements = _requirements(standing, patch, ["Ivo", "Yellow tag"], hand="objects")
    assert requirements[1]["item"] == "Ivo"
    assert requirements[1]["status"] == "unresolved"
    assert requirements[1]["transform_indices"] == []
    assert requirements[2]["status"] == "proposed"


def test_primary_descriptive_mapping_still_binds_without_a_standing_match():
    scene = {"entities": {"tag": {"name": "Yellow tag", "kind": "item"}}}
    patch = {"entities": {"tag": {"state": {"torn": True}}}}
    _, _, requirements = _requirements(scene, patch, ["the marker clipped to his sleeve"], hand="objects")
    assert requirements[1]["status"] == "proposed"


def test_known_primary_requires_its_unique_identity_not_an_ambiguous_alias():
    scene = {"entities": {"left": {"name": "Case", "aliases": ["left case"]},
                          "right": {"name": "Case", "aliases": ["right case"]}}}
    patch = {"entities": {"left": {"state": {"open": True}}}}
    _, _, requirements = _requirements(scene, patch, ["Case"], hand="objects")
    assert requirements[1]["status"] == "unresolved"
    _, _, requirements = _requirements(scene, patch, ["left case"], hand="objects")
    assert requirements[1]["status"] == "proposed"


def test_known_primary_does_not_claim_readonly_near_or_pose_references():
    scene = _scene()
    patch = {"stations": {"tin": {"near": ["Sera"]}},
             "poses": {"tin": {"relative_to": "Sera", "posture": "upright"}}}
    _, _, requirements = _requirements(scene, patch, ["Sera", "Brass tin"], hand="spatial")
    assert requirements[1]["status"] == "unresolved"
    assert requirements[2]["status"] == "proposed"


def test_known_wearer_and_garment_share_the_typed_attire_change():
    scene = _scene()
    scene["entities"]["coat"] = {"name": "Green coat", "kind": "garment"}
    patch = {"attire": {"Sera": {"add": ["Green coat"]}}}
    for primary in (1, 2):
        _, _, requirements = _requirements(scene, patch, ["Sera", "Green coat"],
                                           hand="body", primary=primary)
        assert all(row["status"] == "proposed" for row in requirements)


def test_room_interior_parent_is_a_typed_mutable_relation_endpoint():
    scene = {"entities": {"cabinet": {"name": "Blue cabinet", "kind": "container"}}}
    patch = {"rooms": {"inside": {"name": "Cabinet interior", "parent_entity": "cabinet"}}}
    _, _, requirements = _requirements(scene, patch, ["Blue cabinet", "Cabinet interior"], hand="spatial")
    assert all(row["status"] == "proposed" for row in requirements)
