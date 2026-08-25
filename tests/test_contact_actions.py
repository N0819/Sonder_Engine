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


class TestOneDynamicPerParticipantPerContact:
    """The action TEXT describes the dynamic; it does not identify it.

    Identity used to hash the text, so a rewording minted a new row on the
    same (actor, contact) and the ledger stacked synonyms of one effect.
    Measured 2026-08-25 across the stored corpus: 12 contact-effect rows
    under 3 distinct contact ids across 4 chats, in four groups of three,
    and every one of those groups is one dynamic reworded --
    chat 88's contact:8a4058a942b38470dbb4 carried "steady peristaltic
    wave", "slow steady peristaltic wave", and "steady pressure" whose
    rhythm restated the first. The composer renders one sentence per row, so
    a contained observer's whole view was four sentences with three of them
    saying the same thing, and the narrator's own fidelity check flagged it
    reusing a previous turn's content on 5 of 15 turns. Zero legitimate
    multi-effect contacts exist in the corpus.
    """

    def test_a_reworded_add_redescribes_rather_than_stacks(self):
        scene = _scene()
        _add_contact(scene)
        _add_effect(scene, action="steady pressure")
        _add_effect(scene, action="slow steady pressure")

        [effect] = scene["contact_actions"]
        assert effect["action"] == "slow steady pressure"

    def test_an_add_re_describes_the_effect_WHOLE(self):
        """The other half of "one effect": a re-description replaces the
        row, it does not patch it. A qualifier the new account leaves out
        goes with the words it qualified -- keeping it would leave the
        ledger holding half of one description and half of another, which is
        the stacking this identity rule exists to end. `change` is the op
        that inherits omitted fields from the standing row."""
        scene = _scene()
        _add_contact(scene)
        _add_effect(scene, action="steady pressure",
                    intensity="light", rhythm="constant")
        _add_effect(scene, action="slow steady pressure",
                    intensity="", rhythm="")

        [effect] = scene["contact_actions"]
        assert effect["action"] == "slow steady pressure"
        assert effect["intensity"] == ""
        assert effect["rhythm"] == ""

    def test_change_is_the_op_that_keeps_what_it_does_not_restate(self):
        scene = _scene()
        _add_contact(scene)
        _add_effect(scene, action="steady pressure",
                    intensity="light", rhythm="constant")
        [standing] = scene["contact_actions"]
        apply_contact_action_ops(scene, [{
            "op": "change", "action_id": standing["action_id"],
            "actor": "Ada", "action": "slow steady pressure"}])

        [effect] = scene["contact_actions"]
        assert effect["action"] == "slow steady pressure"
        assert effect["intensity"] == "light"
        assert effect["rhythm"] == "constant"

    def test_the_action_id_is_stable_across_the_redescription(self):
        scene = _scene()
        _add_contact(scene)
        _add_effect(scene, action="steady pressure")
        first = scene["contact_actions"][0]["action_id"]
        _add_effect(scene, action="slow steady pressure")

        [effect] = scene["contact_actions"]
        assert effect["action_id"] == first

    def test_each_participant_may_drive_its_own_effect(self):
        """One dynamic per participant, not one per contact: both sides of a
        contact can be doing something through it at once."""
        scene = _scene()
        _add_contact(scene)
        _add_effect(scene, actor="Ada", action="steady pressure")
        _add_effect(scene, actor="Bex", action="answering pressure")

        assert len(scene["contact_actions"]) == 2
        assert {row["actor"] for row in scene["contact_actions"]} == {"Ada",
                                                                     "Bex"}

    def test_a_saved_ledger_of_rewordings_collapses_to_the_newest(self):
        """Saved rows re-clean into the new identity on every read, so the
        stored triples heal on the next beat with no migration."""
        scene = _scene()
        contact = _add_contact(scene)
        scene["contact_actions"] = [
            {"action_id": f"contact-action:stale{i}", "actor": "Ada",
             "contact_id": contact["contact_id"], "action": text,
             "intensity": "", "rhythm": "", "detail": ""}
            for i, text in enumerate(("steady pressure",
                                      "slow steady pressure",
                                      "rolling pressure"))]
        apply_contact_action_ops(scene, [])

        [effect] = scene["contact_actions"]
        assert effect["action"] == "rolling pressure"

    def test_a_second_contact_between_the_same_bodies_keeps_its_own(self):
        """Identity is still per CONTACT: a different part-pair is a
        different relation and carries its own effect."""
        scene = _scene()
        _add_contact(scene)
        other = {"actor": "Ada", "actor_part": "palm",
                 "target": "Bex", "target_part": "wrist"}
        apply_contact_ops(scene, [{"op": "add", **other, "manner": "rest",
                                   "relation": "surface", "motion": "settled"}])
        _add_effect(scene, action="steady pressure")
        _add_effect(scene, contact_ref=other, action="steady pressure")

        assert len(scene["contact_actions"]) == 2


def test_unknown_bounded_reference_cannot_clear_other_effects():
    scene = _scene()
    contact = _add_contact(scene)
    _add_effect(scene)
    apply_contact_action_ops(scene, [{
        "op": "remove", "actor": "Ada", "contact_ref": "contact:missing",
    }])
    assert len(scene["contact_actions"]) == 1
    assert scene["contact_actions"][0]["contact_id"] == contact["contact_id"]
