"""Typed physical changes settle their related records without reading prose."""

import copy

from core.pipeline_context import ChatData, PipelineContext, TurnData
from persist import commit
from story import attire
from world.spatial import merge_scene_with_diff, room_of


def scene():
    return {
        "rooms": {"workshop": {"name": "Workshop", "anchors": {"tray": {}}},
                  "hall": {"name": "Hall"}},
        "entities": {
            "badge": {"name": "Silver badge", "kind": "object", "portable": True},
            "jacket": {"name": "Blue jacket", "kind": "object", "portable": True},
            "Nia": {"name": "Nia", "kind": "person", "state": {}},
            "Tomas": {"name": "Tomas", "kind": "person", "state": {}},
        },
        "positions": {name: "workshop" for name in ("badge", "jacket", "Nia", "Tomas")},
        "attire": {"Nia": {}, "Tomas": {}},
        "contained": {}, "contacts": [], "stations": {},
    }


def transfer(thing="badge", source="Tomas", target="jacket", relation="mounted"):
    return {"op": "transfer", "object_id": thing, "from_id": source,
            "to_id": target, "relation": relation}


def contact(holder="Tomas", thing="badge", manner="grip", part="right hand"):
    return {"actor": holder, "actor_part": part, "target": thing,
            "target_part": "", "manner": manner, "relation": "surface",
            "motion": "settled"}


def context():
    ctx = PipelineContext(
        chat=ChatData(id=1, name="Physical operation", persona_id=None,
                      lorebook_id=None, scenario="", created=0),
        turn=TurnData(id=1, chat_id=1, idx=1, player_input="", created=0),
        cast=[], input="")
    ctx.director_resolve = {"resolved_event": "Nia puts on the blue jacket."}
    return ctx


def test_attachment_follows_worn_parent_then_detachment_stays_behind():
    sc = scene()
    sc["attire"]["Nia"] = attire.authored_entry(["Blue jacket"], [], None)
    sc["contained"]["badge"] = {"in": "Tomas", "mode": "held"}
    sc["stations"]["badge"] = {"at": "tray", "near": ["Tomas"]}
    attached = merge_scene_with_diff(sc, {"inventory_ops": [transfer()]})
    assert attached["contained"]["badge"] == {"in": "jacket", "mode": "mounted"}
    assert "badge" not in attached["stations"]
    moved = merge_scene_with_diff(attached, {"positions": {"Nia": "hall"}})
    assert room_of(moved, "badge") == room_of(moved, "jacket") == "hall"
    detached = merge_scene_with_diff(moved, {"inventory_ops": [
        transfer(source="jacket", target="hall", relation="on")]})
    walked = merge_scene_with_diff(detached, {"positions": {"Nia": "workshop"}})
    assert "badge" not in walked["contained"]
    assert room_of(walked, "badge") == "hall"
    assert room_of(walked, "jacket") == "workshop"


def test_setdown_retires_every_old_carriage_claim_but_preserves_touch():
    sc = scene()
    sc["contained"]["badge"] = {"in": "Tomas", "mode": "held"}
    sc["entities"]["badge"]["held_by"] = "Tomas"
    sc["entities"]["badge"]["state"] = {"held_by": "Tomas"}
    sc["entities"]["Tomas"]["state"]["held_items"] = ["Silver badge", "Unrelated key"]
    sc["poses"] = {"badge": {"support": "Tomas"}}
    sc["contacts"] = [contact(), contact(manner="touch", part="left finger")]
    sc["stations"]["badge"] = {"at": "tray", "near": ["Tomas"]}
    sc["stations"]["Tomas"] = {"near": ["badge"]}
    before = copy.deepcopy(sc)
    down = merge_scene_with_diff(sc, {"inventory_ops": [transfer(target="workshop", relation="on")]})
    commit.derive_borne_containment(down)
    assert "badge" not in down["contained"]
    assert "held_by" not in down["entities"]["badge"]
    assert "held_by" not in down["entities"]["badge"]["state"]
    assert down["entities"]["Tomas"]["state"]["held_items"] == ["Unrelated key"]
    assert not down.get("poses", {}).get("badge", {}).get("support")
    assert [row["manner"] for row in down["contacts"]] == ["touch"]
    assert not down.get("stations", {}).get("badge", {}).get("at")
    assert sc == before


def test_handover_preserves_receiver_grip_and_fresh_deliberate_grip():
    sc = scene()
    sc["contained"]["badge"] = {"in": "Tomas", "mode": "held"}
    sc["contacts"] = [contact(), contact(holder="Nia")]
    handed = merge_scene_with_diff(sc, {"inventory_ops": [transfer(target="Nia", relation="held")]})
    assert [row["actor"] for row in handed["contacts"]] == ["Nia"]
    fresh = merge_scene_with_diff(sc, {
        "inventory_ops": [transfer(target="workshop", relation="on")],
        "contact_ops": [{"op": "add", **contact()}],
    })
    assert any(row["manner"] == "grip" for row in fresh["contacts"])


def test_compatible_position_and_new_station_supplement_setdown():
    sc = scene()
    sc["contained"]["badge"] = {"in": "Tomas", "mode": "held"}
    sc["contacts"] = [contact()]
    down = merge_scene_with_diff(sc, {
        "positions": {"badge": "workshop"},
        "stations": {"badge": {"at": "tray"}},
        "inventory_ops": [transfer(target="workshop", relation="on")],
    })
    assert "badge" not in down["contained"]
    assert down["contacts"] == []
    assert down["stations"]["badge"]["at"] == "tray"


def test_conflicting_explicit_room_refuses_transfer_without_side_effects():
    sc = scene()
    sc["contacts"] = [contact()]
    notes = []
    after = merge_scene_with_diff(sc, {
        "positions": {"badge": "hall"},
        "inventory_ops": [transfer(target="Nia", relation="held")],
    }, inventory_report=notes)
    assert "badge" not in after["contained"]
    assert room_of(after, "badge") == "hall"
    assert any("conflicts" in note for note in notes)


def test_conflicting_containment_is_reported_and_retains_authority():
    notes = []
    after = merge_scene_with_diff(scene(), {
        "containment": {"badge": {"in": "Nia", "mode": "held"}},
        "inventory_ops": [transfer()],
    }, inventory_report=notes)
    assert after["contained"]["badge"] == {"in": "Nia", "mode": "held"}
    assert any("conflicts" in note for note in notes)


def test_repeated_transfers_in_one_span_execute_in_array_order():
    sc = scene()
    sc["contained"]["badge"] = {"in": "Tomas", "mode": "held"}
    after = merge_scene_with_diff(sc, {"inventory_ops": [
        transfer(target="workshop", relation="on"),
        transfer(source="workshop", target="Nia", relation="held"),
        transfer(source="Nia", target="hall", relation="on"),
    ]})
    assert "badge" not in after["contained"]
    assert room_of(after, "badge") == "hall"


def test_cyclic_attachment_refused_before_other_ledgers_are_changed():
    sc = scene()
    sc["contained"]["jacket"] = {"in": "badge", "mode": "mounted"}
    sc["contained"]["badge"] = {"in": "Tomas", "mode": "held"}
    sc["contacts"] = [contact()]
    notes = []
    after = merge_scene_with_diff(sc, {"inventory_ops": [transfer()]}, inventory_report=notes)
    assert after["contained"]["badge"]["in"] == "Tomas"
    assert any(row["manner"] == "grip" for row in after["contacts"])
    assert any("cycle" in note for note in notes)


def test_rewear_keeps_referenced_shed_parent_and_ends_its_free_grip():
    sc = scene()
    sc["entities"]["jacket"]["state"] = {
        "clothing": True, "worn_by": "Nia", "shed": True, "garment": "Blue jacket"}
    sc["contained"] = {"badge": {"in": "jacket", "mode": "mounted"},
                       "jacket": {"in": "Nia", "mode": "held"}}
    sc["contacts"] = [contact("Nia", "jacket"), contact("Nia", "jacket", "touch", "left finger")]
    sc["stations"]["jacket"] = {"at": "tray"}
    ctx = context()
    commit.apply_attire_diff(sc, {"attire": {"Nia": {"add": ["Blue jacket"]}}}, ctx, ctx.director_resolve)
    assert "jacket" in sc["entities"]
    assert sc["entities"]["jacket"]["state"]["shed"] is False
    assert sc["contained"]["jacket"]["mode"] == "worn"
    assert [row["manner"] for row in sc["contacts"]] == ["touch"]
    assert "jacket" not in sc["stations"]
    # Another attire pass must not fold away the still-referenced parent.
    commit.apply_attire_diff(sc, {}, ctx, ctx.director_resolve)
    moved = merge_scene_with_diff(sc, {"positions": {"Nia": "hall"}})
    assert "jacket" in moved["entities"]
    assert room_of(moved, "badge") == "hall"


def test_repeated_desired_transfer_to_current_holder_is_not_refused():
    sc = scene()
    sc["positions"]["Tomas"] = "hall"
    sc["contained"]["badge"] = {"in": "Nia", "mode": "held"}
    ctx = context()
    desired = {"inventory_ops": [transfer(target="Nia", relation="held")]}
    assert commit._refuse_unheld_transfers(ctx, sc, desired) == []
    different = {"inventory_ops": [transfer(target="Nia", relation="pocket")]}
    assert commit._refuse_unheld_transfers(ctx, sc, different)
    assert different["inventory_ops"] == []


def test_transfer_of_worn_entity_retires_wardrobe_and_does_not_rewear_next_merge():
    sc = scene()
    sc["attire"]["Nia"] = attire.authored_entry(["Blue jacket"], [], None)
    sc = merge_scene_with_diff(sc, {})
    down = merge_scene_with_diff(sc, {"inventory_ops": [
        transfer("jacket", "Nia", "workshop", "on")]})
    assert "jacket" not in down["contained"]
    assert down["attire"]["Nia"]["wearing"] == []
    assert down["entities"]["jacket"]["state"]["shed"] is True
    moved = merge_scene_with_diff(down, {"positions": {"Nia": "hall"}})
    assert room_of(moved, "jacket") == "workshop"


def test_identical_garment_names_do_not_remove_another_wearers_clothing():
    sc = scene()
    sc["entities"]["other_jacket"] = {"name": "Blue jacket", "kind": "object", "portable": True}
    sc["attire"]["Nia"] = attire.authored_entry(["Blue jacket"], [], None)
    sc["attire"]["Tomas"] = attire.authored_entry(["Blue jacket"], [], None)
    sc["contained"] = {"jacket": {"in": "Nia", "mode": "worn"},
                       "other_jacket": {"in": "Tomas", "mode": "worn"}}
    down = merge_scene_with_diff(sc, {"inventory_ops": [transfer("jacket", "Nia", "workshop", "on")]})
    assert down["attire"]["Tomas"]["wearing"] == ["Blue jacket"]
    assert down["contained"]["other_jacket"]["in"] == "Tomas"


def test_entity_setdown_sets_matching_room_anchor_and_reports_missing_anchor():
    sc = scene()
    sc["entities"]["tray"] = {"name": "Tray", "kind": "object"}
    sc["positions"]["tray"] = "workshop"
    down = merge_scene_with_diff(sc, {"inventory_ops": [transfer(target="tray", relation="on")]})
    assert down["stations"]["badge"]["at"] == "tray"
    sc["rooms"]["workshop"]["anchors"] = {}
    notes = []
    partial = merge_scene_with_diff(sc, {"inventory_ops": [transfer(target="tray", relation="on")]}, inventory_report=notes)
    assert room_of(partial, "badge") == "workshop"
    assert any("exact placement" in note for note in notes)


def test_source_guard_checks_each_transfer_against_its_preceding_transfer():
    sc = scene()
    sc["positions"]["Nia"] = "hall"
    sc["contained"]["badge"] = {"in": "Tomas", "mode": "held"}
    ctx = context()
    patch = {"inventory_ops": [transfer(target="Nia", relation="held"),
                               transfer(source="Nia", target="hall", relation="on")]}
    assert commit._refuse_unheld_transfers(ctx, sc, patch) == []
    after = merge_scene_with_diff(sc, patch)
    assert room_of(after, "badge") == "hall"
    assert "badge" not in after["contained"]
    assert sc["contained"]["badge"]["in"] == "Tomas"


def test_desired_wearing_repairs_an_already_listed_garments_conflicting_grip():
    sc = scene()
    sc["attire"]["Nia"] = attire.authored_entry(["Blue jacket"], [], None)
    sc["contained"]["jacket"] = {"in": "Tomas", "mode": "held"}
    sc["contacts"] = [contact("Tomas", "jacket")]
    ctx = context()
    commit.apply_attire_diff(sc, {"attire": {"Nia": {"add": ["Blue jacket"]}}}, ctx, ctx.director_resolve)
    assert sc["contained"]["jacket"] == {"in": "Nia", "mode": "worn", "by": "attire"}
    assert sc["contacts"] == []
