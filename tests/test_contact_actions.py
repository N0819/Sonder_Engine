"""Durable, observer-safe effects attached to standing contacts."""

from world.spatial import (
    apply_contact_action_ops,
    apply_contact_ops,
    contact_action_clause,
    contact_actions_for_observer,
    contact_id,
    merge_scene_with_diff,
)
from agents.narration import _sensory_channels_manifest


def _scene():
    return {
        "rooms": {"workshop": {"name": "Workshop", "adjacent": []}},
        "positions": {"Ada": "workshop", "Bex": "workshop"},
        "entities": {},
        "contacts": [],
        "contact_actions": [],
    }


def _selector():
    return {"actor": "Ada", "actor_part": "hand",
            "target": "Bex", "target_part": "shoulder"}


def _add_contact(scene):
    apply_contact_ops(scene, [{
        "op": "add", **_selector(), "manner": "rest",
        "relation": "surface", "motion": "settled",
    }])
    return scene["contacts"][0]


def _add_effect(scene, **updates):
    op = {"op": "add", "actor": "Ada", "contact_ref": _selector(),
          "action": "steady pressure", "intensity": "light",
          "rhythm": "constant"}
    op.update(updates)
    apply_contact_action_ops(scene, [op])


def test_contact_id_is_symmetric_and_stable():
    contact = {**_selector(), "relation": "surface", "manner": "rest"}
    mirrored = {"actor": "Bex", "actor_part": "shoulder",
                "target": "Ada", "target_part": "hand",
                "relation": "surface", "manner": "press"}
    assert contact_id(contact) == contact_id(mirrored)
    assert contact_id(contact).startswith("contact:")


def test_whole_body_contact_also_has_an_id():
    assert contact_id({"actor": "Ada", "target": "Bex"}).startswith(
        "contact:")


def test_same_beat_contact_and_effect_resolve_by_exact_selector():
    scene = merge_scene_with_diff(_scene(), {
        "contact_ops": [{"op": "add", **_selector(), "manner": "rest",
                         "relation": "surface", "motion": "settled"}],
        "contact_action_ops": [{
            "op": "add", "actor": "Ada", "contact_ref": _selector(),
            "action": "steady pressure", "intensity": "light",
        }],
    })
    [effect] = scene["contact_actions"]
    assert effect["contact_id"] == scene["contacts"][0]["contact_id"]


def test_effect_persists_through_model_silence():
    scene = _scene()
    _add_contact(scene)
    _add_effect(scene)
    apply_contact_action_ops(scene, [])
    assert len(scene["contact_actions"]) == 1


def test_change_can_address_the_stable_action_id():
    scene = _scene()
    _add_contact(scene)
    _add_effect(scene)
    action_id = scene["contact_actions"][0]["action_id"]
    apply_contact_action_ops(scene, [{
        "op": "change", "action_id": action_id, "intensity": "firm"}])
    [effect] = scene["contact_actions"]
    assert effect["intensity"] == "firm"
    assert effect["rhythm"] == "constant"


def test_only_a_contact_participant_can_perform_the_effect():
    scene = _scene()
    _add_contact(scene)
    _add_effect(scene, actor="Observer")
    assert scene["contact_actions"] == []


def test_both_participants_receive_the_effect_but_a_bystander_does_not():
    scene = _scene()
    _add_contact(scene)
    _add_effect(scene)
    assert len(contact_actions_for_observer(scene, "Ada")) == 1
    assert len(contact_actions_for_observer(scene, "Bex")) == 1
    assert contact_actions_for_observer(scene, "Observer") == []


def test_recipient_clause_does_not_leak_the_actors_name():
    scene = _scene()
    _add_contact(scene)
    _add_effect(scene)
    [effect] = contact_actions_for_observer(scene, "Bex")
    clause = contact_action_clause(effect, observer="Bex", scene=scene)
    assert clause == "You feel light steady pressure, constant through the contact"
    assert "Ada" not in clause


def test_narrator_manifest_keeps_the_standing_effect_on_touch():
    scene = _scene()
    _add_contact(scene)
    _add_effect(scene)
    manifest = _sensory_channels_manifest(
        scene, "Bex", "", [], set(), {}, "workshop")
    standing = manifest["touch"]["standing"]
    assert any("light steady pressure" in clause for clause in standing)


def test_ending_the_parent_contact_ends_the_effect():
    scene = _scene()
    _add_contact(scene)
    _add_effect(scene)
    apply_contact_ops(scene, [{"op": "remove", "actor": "Ada",
                               "target": "Bex"}])
    apply_contact_action_ops(scene, [])
    assert scene["contacts"] == []
    assert scene["contact_actions"] == []


def test_unknown_bounded_reference_cannot_clear_other_effects():
    scene = _scene()
    contact = _add_contact(scene)
    _add_effect(scene)
    apply_contact_action_ops(scene, [{
        "op": "remove", "actor": "Ada", "contact_ref": "contact:missing",
    }])
    assert len(scene["contact_actions"]) == 1
    assert scene["contact_actions"][0]["contact_id"] == contact["contact_id"]
