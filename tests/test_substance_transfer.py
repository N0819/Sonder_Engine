"""Non-discrete matter is state, not a body part pretending to be contact.

The Director may name material established by any fiction.  Code only resolves
where it went, using standing interior contact as topology when available, and
keeps the resulting residue until an explicit bounded removal.
"""

from __future__ import annotations

from agents.director import (_evidence_present, _manifest_items,
                             _normalize_diff_shape)
from agents.perception import (_deliver_substance_events,
                               _observer_scene_payload)
from prompts import DEFAULT_PROMPTS
from schemas import StateDiff, validate_llm_output_strict
from spatial import (apply_substance_ops, merge_scene_with_diff,
                     resolve_substance_ops, substance_event_clause,
                     substances_for)


def _scene():
    return {
        "rooms": {"lab": {"name": "Lab", "adjacent": []}},
        "positions": {
            "Emitter": "lab", "Vessel": "lab", "Witness": "lab",
        },
        "entities": {},
        "contacts": [{
            "actor": "Emitter",
            "actor_part": "nozzle",
            "target": "Vessel",
            "target_interior": "reservoir",
            "target_part": "inlet",
            "manner": "insert",
            "relation": "interior",
            "motion": "settled",
        }],
    }


def _release(**overrides):
    op = {
        "op": "release",
        "source": "Emitter",
        "source_part": "nozzle",
        "substance": "coolant",
        "amount": "a measured dose",
    }
    op.update(overrides)
    return op


class TestSchemaAndPromptContract:
    def test_state_diff_keeps_substance_operations(self):
        op = _release()
        assert StateDiff(substance_ops=[op]).dict()["substance_ops"] == [op]

        report = validate_llm_output_strict("director_resolve", {
            "resolved_event": "The emitter releases coolant.",
            "state_diff": {"substance_ops": [op]},
        })
        assert report.valid, report.errors
        assert report.output["state_diff"]["substance_ops"] == [op]

    def test_contract_is_material_generic_and_keeps_it_out_of_contact(self):
        resolve = DEFAULT_PROMPTS["director_resolve"]
        perception = DEFAULT_PROMPTS["perception"]
        assert "MATERIAL TRANSFER — MATTER HAS ITS OWN LEDGER" in resolve
        assert "A material is NOT a body part" in resolve
        assert "exactly one standing relation:'interior' contact" in resolve
        assert "scene.substances lists distinct non-discrete matter" in perception
        assert "STANDING STATE" in perception

    def test_diff_normalization_and_manifest_evidence_include_material(self):
        normalized = _normalize_diff_shape({"substance_ops": "bad"})
        assert normalized["substance_ops"] == []

        op = _release(target="Vessel", placement="interior",
                      target_interior="reservoir", target_part="inlet")
        omission = _manifest_items({"changes_asserted": [{
            "category": "substance", "subject": "Emitter",
            "change": "Coolant remains in the reservoir.",
            "actor": "Emitter", "actor_part": "nozzle",
            "target": "Vessel", "substance": "coolant",
            "placement": "interior", "target_interior": "reservoir",
        }]})[0]
        assert _evidence_present({"substance_ops": [op]}, omission)
        wrong = dict(omission, target_interior="feed line")
        assert not _evidence_present({"substance_ops": [op]}, wrong)


class TestTopologyAndPersistence:
    def test_unique_interior_contact_derives_the_destination(self):
        events = resolve_substance_ops(_scene(), [_release()])
        assert len(events) == 1
        event = events[0]
        assert event["op"] == "add"
        assert event["target"] == "Vessel"
        assert event["placement"] == "interior"
        assert event["target_interior"] == "reservoir"
        assert event["target_part"] == "inlet"

    def test_release_resolves_before_same_beat_contact_removal(self):
        merged = merge_scene_with_diff(_scene(), {
            "substance_ops": [_release()],
            "contact_ops": [{
                "op": "remove", "actor": "Emitter", "actor_part": "nozzle",
                "target": "Vessel", "target_part": "inlet",
            }],
        })
        assert merged["contacts"] == []
        assert merged["substances"][0]["target_interior"] == "reservoir"

    def test_persistent_record_is_upserted_not_duplicated(self):
        scene = apply_substance_ops(_scene(), [_release()])
        first_id = scene["substances"][0]["substance_id"]
        scene = apply_substance_ops(scene, [_release(amount="a larger dose")])
        assert len(scene["substances"]) == 1
        assert scene["substances"][0]["substance_id"] == first_id
        assert scene["substances"][0]["amount"] == "a larger dose"
        assert substances_for(scene, "Vessel") == scene["substances"]

    def test_explicit_surface_destination_needs_no_contact(self):
        scene = _scene()
        scene["contacts"] = []
        result = apply_substance_ops(scene, [_release(
            source_part="vent", target="Vessel", placement="surface",
            target_part="casing")])
        assert result["substances"][0]["placement"] == "surface"
        assert result["substances"][0]["target_part"] == "casing"

    def test_no_contact_and_no_target_is_not_inferred_from_prose(self):
        scene = _scene()
        scene["contacts"] = []
        warnings = []
        result = apply_substance_ops(scene, [_release()], report=warnings.append)
        assert result["substances"] == []
        assert any("without a target" in warning for warning in warnings)

    def test_contradicting_standing_topology_is_rejected(self):
        warnings = []
        result = apply_substance_ops(_scene(), [_release(
            target="Witness", placement="surface")], report=warnings.append)
        assert result["substances"] == []
        assert any("contradicted" in warning for warning in warnings)

    def test_unbounded_removal_is_rejected_but_bounded_removal_works(self):
        warnings = []
        scene = apply_substance_ops(_scene(), [_release()])
        unchanged = apply_substance_ops(scene, [{"op": "clear"}],
                                        report=warnings.append)
        assert len(unchanged["substances"]) == 1
        assert any("unbounded" in warning for warning in warnings)

        removed = apply_substance_ops(unchanged, [{
            "op": "remove", "target": "Vessel", "substance": "coolant",
        }])
        assert removed["substances"] == []

    def test_removing_the_destination_prunes_its_material(self):
        scene = _scene()
        scene["entities"] = {
            "vessel": {"name": "Vessel", "aliases": [], "state": {}},
        }
        scene = apply_substance_ops(scene, [_release()])
        merged = merge_scene_with_diff(scene, {"remove_entities": ["vessel"]})
        assert merged["substances"] == []


class TestPerceptionBoundary:
    def _event(self):
        return resolve_substance_ops(_scene(), [_release(detail="noticeably cool")])[0]

    def test_recipient_clause_names_consequence_not_source(self):
        clause = substance_event_clause(self._event(), you="Vessel", scene=_scene())
        assert "reservoir" in clause
        assert "coolant" in clause
        assert "Emitter" not in clause

    def test_source_gets_its_own_delta_and_bystander_gets_none(self):
        event = self._event()
        source_clause = substance_event_clause(
            event, you="Emitter", scene=_scene())
        assert "releasing" in source_clause
        assert "coolant" in source_clause
        assert substance_event_clause(event, you="Witness", scene=_scene()) == ""

    def test_deterministic_floor_delivers_once(self):
        event = self._event()
        view = _deliver_substance_events(
            "The reservoir shudders.", "Vessel", _scene(), [event])
        assert "coolant" in view
        assert _deliver_substance_events(
            view, "Vessel", _scene(), [event]) == view

    def test_persistent_interior_state_is_cause_blind_and_not_for_bystanders(self):
        scene = apply_substance_ops(_scene(), [_release()])
        vessel = _observer_scene_payload(
            scene, {"name": "Vessel", "room": "lab", "visible_rooms": []},
            {"Emitter": "Emitter", "Vessel": "you", "Witness": "Witness"})
        record = vessel["substances"][0]
        assert record["target"] == "you"
        assert "source" not in record
        assert "source_part" not in record

        emitter = _observer_scene_payload(
            scene, {"name": "Emitter", "room": "lab", "visible_rooms": []},
            {"Emitter": "you", "Vessel": "Vessel", "Witness": "Witness"})
        # The source received the add event when it happened; persistent
        # interior state is not a remote telemetry feed on later beats.
        assert emitter["substances"] == []

        witness = _observer_scene_payload(
            scene, {"name": "Witness", "room": "lab", "visible_rooms": []},
            {"Emitter": "Emitter", "Vessel": "Vessel", "Witness": "you"})
        assert witness["substances"] == []

    def test_visible_surface_residue_does_not_reveal_an_unseen_source(self):
        scene = _scene()
        scene["contacts"] = []
        scene["positions"]["Emitter"] = "elsewhere"
        scene = apply_substance_ops(scene, [_release(
            source_part="vent", target="Vessel", placement="surface",
            target_part="casing")])
        witness = _observer_scene_payload(
            scene, {"name": "Witness", "room": "lab", "visible_rooms": []},
            {"Vessel": "Vessel", "Witness": "you"})
        record = witness["substances"][0]
        assert record["target"] == "Vessel"
        assert "source" not in record
