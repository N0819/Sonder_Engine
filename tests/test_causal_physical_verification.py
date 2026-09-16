"""Scene completion reads normalized physical facts, not model assurances."""

from copy import deepcopy

import pytest

from persist import commit
from world.causal_completion import execution_receipt
from world.causal_verification import verify_patch
from world.spatial import merge_scene_with_diff


def scene():
    return {"rooms": {
        "hall": {"name": "Hall", "adjacent": [{"to": "study", "barrier": "closed_door"},
                                                     {"to": "yard", "barrier": "open"}],
                 "anchors": {"shelf": {}, "table": {}}},
        "study": {"name": "Study", "adjacent": [{"to": "hall", "barrier": "closed_door"}]},
        "yard": {"name": "Yard", "adjacent": [{"to": "hall", "barrier": "open"}]}},
        "positions": {"Ada": "hall", "Jun": "hall", "shelf": "hall", "tin": "hall"},
        "entities": {"tin": {"name": "Tin", "kind": "object", "portable": True},
                     "shelf": {"name": "Shelf", "kind": "fixture"}},
        "stations": {}, "attire": {"Ada": {}, "Jun": {}}, "contacts": []}


def test_partial_door_edit_verifies_changed_edge_without_losing_other_edges():
    before = scene()
    patch = {"rooms": {"hall": {"adjacent": [{"to": "study", "barrier": "open_door"}]}}}
    after = merge_scene_with_diff(before, patch)
    row, = verify_patch(before, after, patch)
    assert row["status"] == "applied"
    assert len(after["rooms"]["hall"]["adjacent"]) == 2
    assert verify_patch(before, before, patch)[0]["status"] == "unresolved"
    assert verify_patch(after, after, patch)[0]["status"] == "unchanged"


def test_barrier_receipt_reads_shared_passage_instead_of_stale_edge():
    before = scene()
    before["passages"] = {"door": {"rooms": ["hall", "study"], "barrier": "closed_door"}}
    before["rooms"]["hall"]["adjacent"][0]["passage"] = "door"
    false_after = deepcopy(before)
    false_after["rooms"]["hall"]["adjacent"][0]["barrier"] = "open_door"
    patch = {"rooms": {"hall": {"adjacent": [{"to": "study", "barrier": "open_door"}]}}}
    assert verify_patch(before, false_after, patch)[0]["status"] == "unresolved"
    after = merge_scene_with_diff(before, patch)
    assert verify_patch(before, after, patch)[0]["status"] == "applied"


def test_room_anchor_removal_and_adjacency_removal_verify_both_ends():
    before = scene()
    patch = {"rooms": {"hall": {"remove_anchors": ["table"]}},
             "remove_adjacent": [{"room": "hall", "to": "study"}]}
    after = merge_scene_with_diff(before, patch)
    assert [row["status"] for row in verify_patch(before, after, patch)] == ["applied", "applied"]
    after["rooms"]["study"]["adjacent"] = [{"to": "hall", "barrier": "open"}]
    assert verify_patch(before, after, patch)[1]["status"] == "unresolved"


def test_protected_room_geometry_is_unresolved_when_applier_keeps_the_plan():
    before = scene()
    before["rooms"]["hall"].update(planned=True, extent={"w": 10, "d": 10})
    patch = {"rooms": {"hall": {"extent": {"w": 20, "d": 20}}}}
    after = merge_scene_with_diff(before, patch)
    assert verify_patch(before, after, patch)[0]["status"] == "unresolved"


def test_scale_receipt_matches_normalization_and_baseline_removal():
    before = scene()
    patch = {"scales": {"Ada": 0.2}}
    after = merge_scene_with_diff(before, patch)
    assert verify_patch(before, after, patch)[0]["status"] == "applied"
    assert verify_patch(before, before, patch)[0]["status"] == "unresolved"
    restored = merge_scene_with_diff(after, {"scales": {"Ada": 1.0}})
    assert "Ada" not in restored["scales"]
    assert verify_patch(after, restored, {"scales": {"Ada": 1.0}})[0]["status"] == "applied"


def test_destruction_cannot_verify_while_an_established_interior_remains(temp_db):
    before = scene()
    before["entities"]["ship"] = {"name": "Ship", "kind": "vehicle", "interior_rooms": ["cabin"]}
    before["rooms"]["cabin"] = {"name": "Cabin", "parent_entity": "ship", "adjacent": []}
    desired = {"destruction": {"target_id": "ship", "scale": "vehicle", "kind": "destroyed"}}
    partial = deepcopy(before)
    partial["entities"].pop("ship")
    assert verify_patch(before, partial, desired)[0]["status"] == "unresolved"
    projected = deepcopy(desired)
    assert commit._prepare_destruction(1, before, projected)
    after = merge_scene_with_diff(before, projected)
    receipt = execution_receipt(before, after, {"patch": desired})
    assert receipt["status"] == "pending"
    assert receipt["action_status"] == "applied"
    assert [(row["scope"], row["status"]) for row in receipt["effects"]] == [
        ("scene", "applied"), ("commit", "unresolved")]


def test_regional_destruction_needs_the_cascade_receipt_even_if_target_disappears():
    before = scene()
    patch = {"destruction": {"target_id": "tin", "scale": "region"}}
    after = deepcopy(before)
    after["entities"].pop("tin")
    receipt = execution_receipt(before, after, {"patch": patch})
    assert receipt["status"] == receipt["action_status"] == "unresolved"


def test_symmetric_station_proximity_counts_as_normalized_desired_state():
    before = scene()
    patch = {"stations": {"Jun": {"at": "shelf", "near": []},
                          "shelf": {"at": "shelf", "near": ["Jun"]}}}
    after = merge_scene_with_diff(before, patch)
    assert after["stations"]["Jun"]["near"] == ["shelf"]
    assert all(row["status"] == "applied" for row in verify_patch(before, after, patch))
    invented = deepcopy(after)
    invented["stations"]["Jun"]["near"].append("Ada")
    assert verify_patch(before, invented, patch)[0]["status"] == "unresolved"


def test_station_near_clear_still_requires_clearing_both_declared_sides():
    before = scene()
    before["stations"] = {"Ada": {"near": ["Jun"]}, "Jun": {"near": ["Ada"]}}
    patch = {"stations": {"Ada": {"near": []}, "Jun": {"near": []}}}
    after = merge_scene_with_diff(before, patch)
    assert all(row["status"] == "applied" for row in verify_patch(before, after, patch))
    assert all(row["status"] == "unresolved" for row in verify_patch(before, before, patch))


def test_same_span_other_owners_explicit_grip_is_context_not_credit():
    before = scene()
    before["contained"] = {"tin": {"in": "Ada", "mode": "held"}}
    inventory = {"inventory_ops": [{"object_id": "tin", "to_id": "hall"}]}
    contact = {"contact_ops": [{"op": "add", "actor": "Ada", "actor_part": "hand",
                                "target": "tin", "target_part": "", "manner": "grip",
                                "relation": "surface"}]}
    patch = {**inventory, **contact}
    after = merge_scene_with_diff(before, patch)
    receipt = execution_receipt(before, after, {"patch": patch, "transforms": [
        {"specialist": "objects", "item_id": 1, "patch": inventory},
        {"specialist": "contact", "item_id": 1, "patch": contact}]})
    assert receipt["action_status"] == "applied"
    assert [(row["specialist"], row["channel"]) for row in receipt["effects"]] == [
        ("objects", "inventory_ops"), ("contact", "contact_ops")]


@pytest.mark.parametrize("channel", ["substance_ops", "artifact_ops", "conditions", "unknown_physical_effect"])
def test_unverified_physical_channel_blocks_action_without_claiming_execution(channel):
    receipt = execution_receipt(scene(), scene(), {"patch": {channel: [{"target": "tin"}]}})
    assert receipt["status"] == "pending"
    assert receipt["action_status"] == "unresolved"


def test_pending_social_record_does_not_erase_a_proven_physical_act():
    before = scene()
    patch = {"entities": {"tin": {"state": {"open": False}}},
             "public_evidence": [{"kind": "act", "description": "closes the tin"}]}
    after = merge_scene_with_diff(before, patch)
    receipt = execution_receipt(before, after, {"patch": patch})
    assert receipt["status"] == "pending"
    assert receipt["action_status"] == "applied"


def test_engine_default_projection_is_silent_but_empty_model_patch_is_not():
    receipt = execution_receipt(scene(), scene(), {
        "stage": "engine", "patch": {"attire": {}, "rooms": {}, "substance_ops": [], "location": ""}})
    assert receipt == {"status": "recorded", "action_status": "recorded", "effects": []}
    model = execution_receipt(scene(), scene(), {"transforms": [{"patch": {}}]})
    assert model["status"] == model["action_status"] == "unresolved"


def test_scene_location_requires_observed_label_not_only_requested_relocation():
    before = {**scene(), "location": "Old Quay"}
    patch = {"location": "New Quay"}
    assert verify_patch(before, before, patch)[0]["status"] == "unresolved"
    after = {**before, "location": "New Quay"}
    assert verify_patch(before, after, patch)[0]["status"] == "applied"
    assert verify_patch(after, after, patch)[0]["status"] == "unchanged"


def test_weather_requires_actual_normalized_record_and_refuses_unreadable_defaults():
    from world.weather import normalize_weather
    before = {**scene(), "weather": normalize_weather({"wind": "breeze", "sky": "clear"})}
    patch = {"weather": {"wind": "gale-force"}}
    after = {**before, "weather": normalize_weather(patch["weather"], before["weather"])}
    assert verify_patch(before, after, patch)[0]["status"] == "applied"
    assert verify_patch(before, before, patch)[0]["status"] == "unresolved"
    assert verify_patch(after, after, patch)[0]["status"] == "unchanged"
    for desired in ({"wind": "unreadable"}, {"nonexistent_axis": "value"}, {"electrical": "yes"}):
        assert verify_patch(before, before, {"weather": desired})[0]["status"] == "unresolved"
    assert verify_patch(scene(), scene(), {"weather": {"sky": "clear"}})[0]["status"] == "unresolved"


def test_time_only_verifies_authoritative_label_or_clock_endpoint_in_snapshot():
    before = {**scene(), "time_of_day": "morning", "simulation_clock": {"elapsed_seconds": 100}}
    after = {**before, "time_of_day": "noon", "simulation_clock": {"elapsed_seconds": 130}}
    assert verify_patch(before, after, {"time": "noon"})[0]["status"] == "applied"
    assert verify_patch(before, before, {"time": "noon"})[0]["status"] == "unresolved"
    assert verify_patch(before, after, {"time": {"end_seconds": 130}})[0]["status"] == "applied"
    assert verify_patch(scene(), scene(), {"time": {"end_seconds": 130}})[0]["status"] == "unresolved"
    for desired in ({"display": "noon"}, {"display_advance": "half an hour later"},
                    {"duration_seconds": 30}, {"end_seconds": 130, "duration_seconds": 30}):
        assert execution_receipt(before, after, {"patch": {"time": desired}})["action_status"] == "unresolved"


@pytest.mark.parametrize("evidence", ["clothing", "garment", "wardrobe"])
def test_known_garment_worn_transfer_also_requires_destination_wardrobe(evidence):
    before = scene()
    before["entities"]["coat"] = {"name": "Violet coat", "kind": "object", "portable": True,
                                    "state": {evidence: True if evidence == "clothing" else "Violet coat"}}
    before["positions"]["coat"] = "hall"
    before["contained"] = {"coat": {"in": "Ada", "mode": "held"}}
    if evidence == "wardrobe":
        before["entities"]["coat"]["state"] = {}
        before["attire"]["Ada"] = {"wearing": ["Violet coat"]}
    patch = {"inventory_ops": [{"object_id": "coat", "to_id": "Jun", "relation": "worn"}]}
    after = deepcopy(before)
    after["contained"]["coat"] = {"in": "Jun", "mode": "worn"}
    after["attire"]["Ada"] = {"wearing": []}
    assert verify_patch(before, after, patch)[0]["status"] == "unresolved"
    after["attire"]["Jun"] = {"wearing": ["Violet coat"]}
    assert verify_patch(before, after, patch)[0]["status"] == "applied"
    after["entities"]["other_coat"] = {"name": "Violet coat", "kind": "object"}
    assert verify_patch(before, after, patch)[0]["status"] == "unresolved"


def test_worn_non_garment_object_does_not_invent_a_wardrobe_requirement():
    before = scene()
    patch = {"inventory_ops": [{"object_id": "tin", "to_id": "Ada", "relation": "worn"}]}
    after = merge_scene_with_diff(before, patch)
    assert verify_patch(before, after, patch)[0]["status"] == "applied"
