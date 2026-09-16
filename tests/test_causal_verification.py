"""Completion is proved by an actual typed postcondition at its own span."""

from copy import deepcopy

from world.causal_verification import verify_causal_worlds, verify_patch
from world.spatial import merge_scene_with_diff


def _scene():
    return {"rooms": {"workshop": {"name": "Workshop", "adjacent": []},
                      "yard": {"name": "Yard", "adjacent": []}},
            "entities": {"tin": {"name": "Tin", "kind": "item", "state": {"open": True}},
                         "badge": {"name": "Badge", "kind": "item"},
                         "jacket": {"name": "Jacket", "kind": "item"}},
            "positions": {"tin": "workshop", "badge": "workshop", "jacket": "workshop",
                          "Sera": "workshop", "Tomas": "workshop"},
            "attire": {"Sera": {"wearing": []}, "Tomas": {"wearing": []}},
            "contained": {}, "contacts": []}


def _statuses(receipts):
    return [receipt["status"] for receipt in receipts]


def test_empty_already_true_claim_cannot_settle_narrated_tin_closure():
    initial = _scene()
    receipt, = verify_patch(initial, initial, {}, item_id=4, chrono_id=3)
    assert receipt["status"] == "unresolved"
    assert receipt["code"] == "missing_desired_state"
    assert receipt["item_id"] == 4 and receipt["chrono_id"] == 3


def test_tin_closure_requires_the_requested_state_not_just_any_changed_key():
    initial = _scene()
    actual = deepcopy(initial)
    actual["entities"]["tin"]["state"]["description"] = "dented"
    patch = {"entities": {"tin": {"state": {"open": False, "description": "dented"}}}}
    assert _statuses(verify_patch(initial, actual, patch)) == ["unresolved"]
    actual["entities"]["tin"]["state"]["open"] = False
    assert _statuses(verify_patch(initial, actual, patch)) == ["applied"]


def test_unchanged_is_engine_derived_and_ignores_attribution_metadata():
    initial = _scene()
    patch = {"entities": {"tin": {"state": {"open": True}, "from_event": 11}}}
    actual = deepcopy(initial)
    actual["entities"]["tin"]["from_event"] = 11
    assert _statuses(verify_patch(initial, actual, patch)) == ["unchanged"]
    assert _statuses(verify_patch(initial, actual, {"entities": {"tin": {"from_event": 11}}})) == ["unresolved"]


def test_verify_adjacent_worlds_instead_of_initial_state_or_final_state():
    closed = _scene()
    closed["entities"]["tin"]["state"]["open"] = False
    opened = _scene()
    patch = {"entities": {"tin": {"state": {"open": False}}}}
    rows = [{"chrono_id": 1, "patch": {"entities": {"tin": {"state": {"open": True}}}},
             "before": closed, "after": opened},
            {"chrono_id": 2, "patch": patch, "before": opened, "after": opened},
            {"chrono_id": 3, "patch": patch, "before": opened, "after": closed}]
    assert _statuses(verify_causal_worlds(rows)) == ["applied", "unresolved", "applied"]


def test_setdown_in_same_room_is_not_complete_while_carriage_survives():
    initial = _scene()
    initial["contained"]["tin"] = {"in": "Sera", "mode": "held"}
    patch = {"inventory_ops": [{"object_id": "tin", "from_id": "Sera", "to_id": "workshop"}]}
    assert _statuses(verify_patch(initial, initial, patch)) == ["unresolved"]
    placed = deepcopy(initial)
    placed["contained"] = {}
    assert _statuses(verify_patch(initial, placed, patch)) == ["applied"]


def test_setdown_cannot_leave_previous_grip_or_held_by_bookkeeping():
    initial = _scene()
    grip = {"actor": "Sera", "actor_part": "hand", "target": "tin", "target_part": "",
            "relation": "surface", "manner": "grip"}
    initial["contacts"] = [grip]
    initial["entities"]["tin"]["state"]["held_by"] = "Sera"
    patch = {"inventory_ops": [{"object_id": "tin", "to_id": "workshop"}]}
    assert _statuses(verify_patch(initial, initial, patch)) == ["unresolved"]
    placed = deepcopy(initial)
    placed["contacts"] = []
    assert _statuses(verify_patch(initial, placed, patch)) == ["unresolved"]
    placed["entities"]["tin"]["state"].pop("held_by")
    assert _statuses(verify_patch(initial, placed, patch)) == ["applied"]


def test_same_span_reasserted_touch_is_allowed_after_setdown():
    initial = _scene()
    patch = {"inventory_ops": [{"object_id": "tin", "to_id": "workshop"}],
             "contact_ops": [{"op": "add", "actor": "Sera", "actor_part": "hand",
                              "target": "tin", "target_part": "", "relation": "surface",
                              "manner": "grip"}]}
    actual = deepcopy(initial)
    actual["contacts"] = [{k: v for k, v in patch["contact_ops"][0].items() if k != "op"}]
    assert _statuses(verify_patch(initial, actual, patch)) == ["unchanged", "applied"]


def test_badge_attachment_requires_a_durable_parent_not_merely_same_room():
    initial = _scene()
    patch = {"inventory_ops": [{"object_id": "badge", "to_id": "jacket", "relation": "mounted"}]}
    assert _statuses(verify_patch(initial, initial, patch)) == ["unresolved"]
    attached = deepcopy(initial)
    attached["contained"]["badge"] = {"in": "jacket", "mode": "mounted"}
    assert _statuses(verify_patch(initial, attached, patch)) == ["applied"]
    moved = merge_scene_with_diff(attached, {"positions": {"jacket": "yard"}})
    assert moved["positions"]["badge"] == "yard"


def test_setdown_at_named_surface_requires_its_anchor_station():
    initial = _scene()
    initial["entities"]["table"] = {"name": "Table", "kind": "furniture"}
    initial["positions"]["table"] = "workshop"
    initial["rooms"]["workshop"]["anchors"] = {"table": {"name": "Table"}}
    patch = {"inventory_ops": [{"object_id": "tin", "to_id": "table", "relation": "on"}]}
    assert _statuses(verify_patch(initial, initial, patch)) == ["unresolved"]
    placed = deepcopy(initial)
    placed["stations"] = {"tin": {"at": "table"}}
    assert _statuses(verify_patch(initial, placed, patch)) == ["applied"]


def test_entity_without_an_anchor_cannot_prove_precise_setdown():
    initial = _scene()
    patch = {"inventory_ops": [{"object_id": "tin", "to_id": "jacket", "relation": "on"}]}
    assert _statuses(verify_patch(initial, initial, patch)) == ["unresolved"]


def test_nonexistent_transfer_target_and_ignored_placement_are_unresolved():
    initial = _scene()
    for patch in ({"inventory_ops": [{"object_id": "unknown", "to_id": "Sera"}]},
                  {"inventory_ops": [{"object_id": "tin", "to_id": "imaginary room"}]},
                  {"positions": {"Sera": "imaginary room"}},
                  {"containment": {"missing": None}}, {"remove_entities": ["missing"]}):
        assert _statuses(verify_patch(initial, initial, patch)) == ["unresolved"]


def test_partial_channel_success_preserves_outstanding_effect():
    initial = _scene()
    patch = {"positions": {"tin": "yard"}, "containment": {"tin": None}}
    actual = deepcopy(initial)
    actual["positions"]["tin"] = "yard"
    actual["contained"]["tin"] = {"in": "Sera", "mode": "held"}
    receipts = verify_patch(initial, actual, patch)
    assert _statuses(receipts) == ["applied", "unresolved"]
    assert [r["channel"] for r in receipts] == ["positions", "containment"]


def test_contact_removal_checks_mirrored_endpoints_and_actual_parts():
    initial = _scene()
    initial["contacts"] = [{"actor": "Sera", "actor_part": "hand", "target": "tin",
                             "target_part": "rim", "manner": "grip", "relation": "surface"}]
    patch = {"contact_ops": [{"op": "remove", "actor": "tin", "actor_part": "rim",
                              "target": "Sera", "target_part": "hand"}]}
    assert _statuses(verify_patch(initial, initial, patch)) == ["unresolved"]
    actual = deepcopy(initial)
    actual["contacts"] = []
    assert _statuses(verify_patch(initial, actual, patch)) == ["applied"]


def test_contact_add_requires_whole_body_endpoint_when_no_part_requested():
    initial = _scene()
    actual = deepcopy(initial)
    actual["contacts"] = [{"actor": "Sera", "actor_part": "hand", "target": "tin",
                             "target_part": "rim", "manner": "touch"}]
    patch = {"contact_ops": [{"actor": "Sera", "target": "tin", "manner": "touch"}]}
    assert _statuses(verify_patch(initial, actual, patch)) == ["unresolved"]


def test_wearing_removal_checks_actual_wardrobe():
    initial = _scene()
    initial["attire"]["Sera"]["wearing"] = ["Jacket"]
    patch = {"attire": {"Sera": {"remove": ["Jacket"]}}}
    assert _statuses(verify_patch(initial, initial, patch)) == ["unresolved"]
    actual = deepcopy(initial)
    actual["attire"]["Sera"]["wearing"] = []
    assert _statuses(verify_patch(initial, actual, patch)) == ["applied"]


def test_wearing_removal_cannot_hide_a_still_worn_regional_record():
    initial = _scene()
    initial["attire"]["Sera"] = {"wearing": [], "regions": {
        "torso": {"garments": [{"name": "Jacket", "state": "worn"}]}}}
    patch = {"attire": {"Sera": {"remove": ["Jacket"]}}}
    assert _statuses(verify_patch(initial, initial, patch)) == ["unresolved"]


def test_transfer_cannot_leave_a_source_body_still_listing_the_object_as_held():
    initial = _scene()
    initial["entities"]["Sera"] = {"name": "Sera", "kind": "person", "state": {"held_items": ["tin"]}}
    patch = {"inventory_ops": [{"object_id": "tin", "to_id": "workshop"}]}
    assert _statuses(verify_patch(initial, initial, patch)) == ["unresolved"]


def test_phase_sources_never_counts_as_an_effect_or_a_pending_channel():
    initial = _scene()
    patch = {"entities": {"tin": {"state": {"open": True}}}, "phase_sources": {"entities": {"tin": 1}}}
    assert _statuses(verify_patch(initial, initial, patch)) == ["unchanged"]


def test_non_scene_channels_stay_explicitly_unverified_and_inputs_are_unchanged():
    initial = _scene()
    patch = {"world_facts": ["The bell rang."], "public_evidence": [{"kind": "promise"}]}
    saved = deepcopy((initial, patch))
    receipts = verify_patch(initial, initial, patch)
    assert _statuses(receipts) == ["unresolved", "unresolved"]
    assert all(r["code"] == "unsupported_channel" for r in receipts)
    assert (initial, patch) == saved
