"""Non-discrete matter is state, not a body part pretending to be contact.

The Director may name material established by any fiction.  Code only resolves
where it went, using standing interior contact as topology when available, and
keeps the resulting residue until an explicit bounded removal.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from agents.director import (_character_material_effects, _evidence_present,
                             _manifest_items,
                             _merge_character_material_effects,
                             _normalize_diff_shape)
from agents.perception import (_deliver_substance_events,
                               _observer_scene_payload)
from character_schema import character_embodiment_capabilities
from prompts import DEFAULT_PROMPTS
from schemas import CharacterOutput, StateDiff, validate_llm_output_strict
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

    def test_character_keeps_completed_actor_owned_material_effects(self):
        effect = {
            "op": "release", "source_part": "nozzle",
            "substance": "coolant", "amount": "a measured dose",
        }
        assert CharacterOutput(
            material_effects=[effect]).dict()["material_effects"] == [effect]

    def test_contract_is_material_generic_and_keeps_it_out_of_contact(self):
        # The two `perception` assertions that were here asserted a prompt no
        # model reads; it is gone from the packs. Everything below is a live
        # model call and can still regress.
        resolve = DEFAULT_PROMPTS["director_contact"]
        assert "MATERIAL TRANSFER — MATTER HAS ITS OWN LEDGER" in resolve
        assert "A material is NOT a body part" in resolve
        assert "exactly one standing relation:'interior' contact" in resolve
        character = DEFAULT_PROMPTS["character"]
        assert "MATERIAL EFFECTS YOU COMPLETE" in character
        assert "active_state.hedonic.released" in character
        assert "character_material_effects" in resolve

    def test_embodiment_capabilities_are_available_to_their_owner(self):
        capability = {
            "capability": "A condenser releases coolant when its cycle completes.",
            "visible_when": "during venting", "limits": "one dose",
        }
        sheet = {"identity": {"name": "Emitter"},
                 "embodiment": {"latent": [capability]}}
        assert character_embodiment_capabilities(sheet) == [capability]

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

    def test_a_surface_deposit_cannot_carry_an_enclosure(self):
        """An enclosure named beside a SURFACE placement is a cavity on some
        other body. Live (chat 69 ⎇49, turn 78): saliva recorded
        `target: Hinami, placement: surface, target_interior: mouth` while
        Hinami was inside Elyra Voss -- the mouth was Elyra's, and every
        consumer reads target_interior as a structure of the TARGET, so the
        recipient was handed her own mouth as the place it landed."""
        scene = _scene()
        scene["contacts"] = []
        warnings = []
        result = apply_substance_ops(scene, [_release(
            source_part="vent", target="Vessel", placement="surface",
            target_part="casing", target_interior="reservoir")],
            report=warnings.append)

        [record] = result["substances"]
        assert record["placement"] == "surface"
        assert record["target_interior"] == ""
        assert any("enclosure" in warning for warning in warnings)

    def test_a_saved_surface_record_sheds_its_enclosure_on_the_next_apply(self):
        """The live scene already carries the stray enclosure, and a fix that
        only catches new ops leaves it standing forever. Worse, it keeps the
        row out of the pool it belongs to: `_record_region` prefers the
        enclosure, so one coating of saliva filed under someone else's mouth
        never meets the identical coating filed under the body it is on."""
        scene = _scene()
        scene["contacts"] = []
        apply_substance_ops(scene, [_release(
            source_part="vent", target="Vessel", placement="surface",
            target_part="casing")])
        scene["substances"][0]["target_interior"] = "reservoir"
        apply_substance_ops(scene, [])

        assert scene["substances"][0]["target_interior"] == ""

    def test_an_interior_deposit_still_keeps_its_enclosure(self):
        """The carve-out the clear must not eat: target_interior is required
        for an interior placement and is the only thing locating it."""
        scene = _scene()
        scene["contacts"] = []
        result = apply_substance_ops(scene, [_release(
            source_part="vent", target="Vessel", placement="interior",
            target_interior="reservoir", target_part="inlet")])

        assert result["substances"][0]["target_interior"] == "reservoir"

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


class TestActorOwnedMaterialProjection:
    @staticmethod
    def _ctx(effect, *, result_map="reaction_results"):
        ctx = SimpleNamespace(
            cast=[{"id": 7, "sheet": json.dumps({
                "identity": {"name": "Emitter"},
            })}],
            reaction_results={}, character_results={},
        )
        getattr(ctx, result_map)[7] = {"material_effects": [effect]}
        return ctx

    def test_character_source_is_canonical_and_cannot_be_forged(self):
        effects = _character_material_effects(self._ctx({
            "op": "release", "source": "Someone Else",
            "source_part": "nozzle", "substance": "coolant",
        }))
        assert effects == [{
            "op": "release", "source": "Emitter",
            "source_part": "nozzle", "substance": "coolant",
        }]

    def test_completed_effect_survives_director_omission(self):
        effects = _character_material_effects(self._ctx({
            "op": "release", "source_part": "nozzle",
            "substance": "coolant", "amount": "a measured dose",
        }))
        ops = _merge_character_material_effects(_scene(), [], effects)
        merged = merge_scene_with_diff(_scene(), {"substance_ops": ops})
        assert merged["substances"][0]["target"] == "Vessel"
        assert merged["substances"][0]["target_interior"] == "reservoir"

    def test_explicit_destination_works_without_interior_contact(self):
        scene = _scene()
        scene["contacts"] = []
        effects = _character_material_effects(self._ctx({
            "op": "release", "source_part": "nozzle",
            "substance": "coolant", "target": "Vessel",
            "placement": "interior", "target_interior": "reservoir",
        }))
        ops = _merge_character_material_effects(scene, [], effects)
        assert resolve_substance_ops(scene, ops)[0]["target"] == "Vessel"

    def test_matching_director_op_is_not_duplicated(self):
        effect = _release()
        ops = _merge_character_material_effects(
            _scene(), [effect], [effect])
        assert ops == [effect]

    def test_character_cannot_clear_or_remove_world_material(self):
        warnings = []
        effects = _character_material_effects(self._ctx({
            "op": "clear", "source_part": "nozzle", "substance": "coolant",
        }), report=warnings.append)
        assert effects == []
        assert "non-additive" in warnings[0]


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


class TestOneReleaseIsOneRecord:
    """A release the Director wrote twice at two part-precisions is one event.

    Live (chat 69 "Horny Story. ⎇49", turn 34): one release arrived as an
    `add` naming the endpoint part and a `deposit` omitting it, in the same
    beat, otherwise word-for-word identical. `_substance_id` hashes the part
    slots, so the pair minted two standing records, and the saved scene still
    carried both verbatim-identical rows at the end of the story.
    """

    def _doubled(self):
        # The measured shape: identical everywhere except one op's silence
        # about target_part.
        precise = _release(op="add", target="Vessel", placement="interior",
                           target_interior="reservoir", target_part="inlet",
                           detail="a second measured release")
        blurred = _release(op="deposit", target="Vessel",
                           placement="interior", target_interior="reservoir",
                           detail="a second measured release")
        return precise, blurred

    def test_the_blurred_twin_does_not_mint_a_second_record(self):
        precise, blurred = self._doubled()
        scene = _scene()
        apply_substance_ops(scene, [precise, blurred])

        assert len(scene["substances"]) == 1

    def test_the_surviving_record_keeps_the_precise_endpoint(self):
        precise, blurred = self._doubled()
        scene = _scene()
        apply_substance_ops(scene, [blurred, precise])

        [record] = scene["substances"]
        assert record["target_part"] == "inlet"

    def test_a_scene_saved_with_the_twin_pair_heals_on_the_next_apply(self):
        precise, blurred = self._doubled()
        scene = _scene()
        apply_substance_ops(scene, [precise])
        [kept] = scene["substances"]
        twin = dict(kept, target_part="", substance_id="substance:legacytwin")
        scene["substances"].append(twin)
        apply_substance_ops(scene, [])

        assert len(scene["substances"]) == 1

    def test_a_second_release_along_the_route_updates_rather_than_stacks(self):
        """The boundary the dedupe must not move: identity has never included
        `detail`, so a later release along the same route UPDATES the standing
        record (its account wins) rather than stacking a second row. The
        blurred-twin fold only ever fires on rows that agree word for word."""
        first = _release(op="add", target="Vessel", placement="interior",
                         target_interior="reservoir",
                         detail="the first release")
        second = _release(op="add", target="Vessel", placement="interior",
                          target_interior="reservoir",
                          detail="a later, larger release")
        scene = _scene()
        apply_substance_ops(scene, [first, second])

        [record] = scene["substances"]
        assert record["detail"] == "a later, larger release"

    def test_one_cavity_spelled_two_ways_is_one_place(self):
        """Live (chat 69 ⎇49, turns 61-62): two deposits into one cavity, one
        writing `mouth` and the next `oral cavity`, stood as two rows for the
        rest of the story. Every region comparison in this ledger was raw
        casefolded text, so a re-spelling minted a second place on a body that
        has one."""
        first = _release(op="add", target="Vessel", placement="interior",
                         target_interior="reservoir", detail="one release")
        respelled = _release(op="add", target="Vessel", placement="interior",
                             target_interior="holding reservoir",
                             detail="one release")
        scene = _scene()
        # No standing interior contact: the topology check would otherwise
        # reject the second spelling outright and prove nothing about folding.
        scene["contacts"] = []
        apply_substance_ops(scene, [first, respelled])

        assert len(scene["substances"]) == 1

    def test_spelling_noise_alone_does_not_make_a_second_place(self):
        """Underscores, case and plurals are how the same slot arrives from
        two stages, not two places on a body."""
        first = _release(op="add", target="Vessel", placement="surface",
                         target_part="Intake_Ports", detail="one release")
        noisy = _release(op="add", target="Vessel", placement="surface",
                         target_part="intake port", detail="one release")
        scene = _scene()
        scene["contacts"] = []
        apply_substance_ops(scene, [first, noisy])

        assert len(scene["substances"]) == 1

    def test_two_genuinely_different_places_stay_two(self):
        """The boundary: folding spellings must never blur two places a body
        really has, which is why this reuses the structural refinement rule
        rather than a synonym vocabulary."""
        first = _release(op="add", target="Vessel", placement="surface",
                         target_part="casing", detail="one release")
        other = _release(op="add", target="Vessel", placement="surface",
                         target_part="inlet", detail="one release")
        scene = _scene()
        scene["contacts"] = []
        apply_substance_ops(scene, [first, other])

        assert len(scene["substances"]) == 2

    def test_the_contract_names_the_wrong_body_part_failure(self):
        """Live (turn 63 of the same story): matter recorded on the TARGET
        with the SOURCE's own part in target_part -- a part the target's body
        does not have."""
        resolve = DEFAULT_PROMPTS["director_contact"]
        assert "places on the TARGET's own body" in resolve
        assert "One release is ONE op" in resolve


class TestARegionIsABodyAndAPlaceOnIt:
    """A region name is not an identity: one body's mouth is not another's.

    Every comparison in this ledger asked "same region?" against a bare
    string, and answered it beside a separate, ad-hoc check of who the body
    was -- when it checked at all. `_same_pool` compared `target` as raw
    casefolded text, which is the exact `==` that `same_subject` exists to
    replace: a being routinely carries a cast display name and a scene entity
    id at once, and five separate live defects were that one comparison.
    """

    def _two_spellings(self):
        # One being, two spellings: the entity id and the display name.
        scene = _scene()
        scene["contacts"] = []
        scene["entities"] = {
            "vessel_01": {"name": "Vessel", "aliases": [], "state": {}},
        }
        scene["substances"] = [{
            "source": "Emitter", "source_part": "nozzle",
            "substance": "coolant", "target": "vessel_01",
            "placement": "surface", "target_interior": "",
            "target_part": "casing", "amount": "a film", "detail": "thin",
            "substance_id": "substance:stored",
        }]
        return scene

    def test_one_body_under_two_spellings_is_one_body(self):
        scene = self._two_spellings()
        apply_substance_ops(scene, [{
            "op": "add", "source": "Emitter", "source_part": "nozzle",
            "substance": "coolant", "target": "Vessel",
            "placement": "surface", "target_part": "casing",
            "amount": "a layer", "detail": "thick"}])

        assert len(scene["substances"]) == 1

    def test_the_surviving_row_keeps_the_stored_identity(self):
        """Nothing may be re-keyed by the fold: a selector the Director minted
        from an earlier payload has to keep finding this row."""
        scene = self._two_spellings()
        apply_substance_ops(scene, [{
            "op": "add", "source": "Emitter", "source_part": "nozzle",
            "substance": "coolant", "target": "Vessel",
            "placement": "surface", "target_part": "casing",
            "amount": "a layer", "detail": "thick"}])

        [record] = scene["substances"]
        assert record["substance_id"] == "substance:stored"
        assert record["amount"] == "a layer"

    def test_the_same_region_on_a_different_body_is_a_different_place(self):
        """The whole point: two bodies each having a casing is two places, and
        no comparison anywhere may collapse them."""
        scene = _scene()
        scene["contacts"] = []
        apply_substance_ops(scene, [
            {"op": "add", "source": "Emitter", "source_part": "nozzle",
             "substance": "coolant", "target": "Vessel",
             "placement": "surface", "target_part": "casing"},
            {"op": "add", "source": "Emitter", "source_part": "nozzle",
             "substance": "coolant", "target": "Witness",
             "placement": "surface", "target_part": "casing"}])

        assert len(scene["substances"]) == 2

    def test_matter_leaves_the_region_of_the_body_that_moved_it(self):
        """Conservation asks the same qualified question: matter leaves the
        moving body's OWN region, never the same-named region on somebody
        else standing in the room."""
        scene = _scene()
        scene["contacts"] = []
        apply_substance_ops(scene, [
            {"op": "add", "source": "Emitter", "source_part": "nozzle",
             "substance": "coolant", "target": "Vessel",
             "placement": "interior", "target_interior": "reservoir"},
            {"op": "add", "source": "Emitter", "source_part": "nozzle",
             "substance": "coolant", "target": "Witness",
             "placement": "interior", "target_interior": "reservoir"}])
        # Vessel moves what is in ITS reservoir; Witness's is not its to spend.
        apply_substance_ops(scene, [{
            "op": "add", "source": "Vessel", "source_part": "reservoir",
            "substance": "coolant", "target": "Vessel",
            "placement": "interior", "target_interior": "sump"}])

        held = {(record["target"], record["target_interior"])
                for record in scene["substances"]}
        assert held == {("Witness", "reservoir"), ("Vessel", "sump")}


class TestOneSubstanceOnOneRegionIsOneDeposit:
    """The same matter re-applied to the same place stacked instead of pooling.

    Live (chat 69 ⎇49): nine saliva rows targeting Hinami, three of them on
    the region `body` -- turns 74, 78 and 80 -- kept apart only by which part
    of the source delivered them (`tongue`, then `mouth`) and by their wording.
    Saliva on her body is saliva on her body; `_substance_id` hashing
    `source_part` made it three puddles, and every one of them was read back
    to her every beat.

    The contact ledger has had this rule since it was built (`_displaces`: an
    unqualified part noun is a definite description, so re-asserting it MOVES
    the limb). The substance ledger never grew the equivalent.
    """

    def _coat(self, **over):
        op = {"op": "add", "source": "Emitter", "source_part": "nozzle",
              "substance": "coolant", "target": "Vessel",
              "placement": "surface", "target_part": "casing",
              "amount": "a film", "detail": "thin"}
        op.update(over)
        return op

    def test_the_same_matter_on_one_region_pools_rather_than_stacks(self):
        scene = _scene()
        scene["contacts"] = []
        apply_substance_ops(scene, [
            self._coat(),
            self._coat(source_part="vent", amount="a layer", detail="thick")])

        assert len(scene["substances"]) == 1

    def test_the_later_account_of_the_pool_wins(self):
        """Same boundary the route update already held: a later release
        describes the pool as it now is, so its amount and detail replace the
        earlier ones rather than being discarded."""
        scene = _scene()
        scene["contacts"] = []
        apply_substance_ops(scene, [
            self._coat(),
            self._coat(source_part="vent", amount="a layer", detail="thick")])

        [record] = scene["substances"]
        assert record["amount"] == "a layer"
        assert record["detail"] == "thick"

    def test_a_different_substance_on_the_same_region_stays_separate(self):
        scene = _scene()
        scene["contacts"] = []
        apply_substance_ops(scene, [
            self._coat(), self._coat(substance="lubricant")])

        assert len(scene["substances"]) == 2

    def test_a_different_source_stays_separate(self):
        """Provenance is not decoration: perception strips `source` per
        observer, so two bodies' matter in one place is two facts about who
        was there."""
        scene = _scene()
        scene["contacts"] = []
        apply_substance_ops(scene, [
            self._coat(), self._coat(source="Witness")])

        assert len(scene["substances"]) == 2

    def test_a_different_region_stays_separate(self):
        scene = _scene()
        scene["contacts"] = []
        apply_substance_ops(scene, [
            self._coat(), self._coat(target_part="inlet")])

        assert len(scene["substances"]) == 2

    def test_a_saved_scene_of_stacked_rows_heals_on_the_next_apply(self):
        """The live scene already carries the stack; a fix that only catches
        new ops leaves nine rows standing forever."""
        scene = _scene()
        scene["contacts"] = []
        apply_substance_ops(scene, [self._coat()])
        stale = dict(scene["substances"][0], source_part="vent",
                     detail="thick", substance_id="substance:legacystack")
        scene["substances"].append(stale)
        apply_substance_ops(scene, [])

        assert len(scene["substances"]) == 1


class TestMatterMovedLeavesWhereItWas:
    """Matter arriving somewhere never left where it came from.

    Live (chat 69 ⎇49, turn 70): "You gulp the remainder of her seed still in
    her mouth" produced exactly one op -- an `add` into the stomach -- and no
    removal, because the vocabulary has no way to say where matter LEFT. Ten
    turns later the mouth deposits were still standing and still being fed to
    the recipient every beat, by which point she was elsewhere entirely. The
    same shape swallowed twice more at turns 67 and 68.

    The floor cannot depend on the Director emitting the paired removal: it
    emitted 5 removals against 38 deposits across the whole stored corpus, and
    none at all after turn 38.
    """

    def _holding(self, **over):
        # Foreign matter standing in Vessel's reservoir, put there by Emitter.
        scene = _scene()
        apply_substance_ops(scene, [_release(
            target="Vessel", placement="interior",
            target_interior="reservoir", **over)])
        return scene

    def _move(self, **over):
        op = {"op": "add", "source": "Vessel", "source_part": "reservoir",
              # Deliberately a DIFFERENT name for the same matter: the
              # Director renamed one substance three times across turns
              # 61/66/70 ("fluid", "seed", "Elyra Voss seed"), so a rule keyed
              # on the substance name would never once have fired.
              "substance": "settled coolant", "target": "Vessel",
              "placement": "interior", "target_interior": "sump",
              "amount": "the remainder"}
        op.update(over)
        return op

    def test_moving_matter_out_of_a_region_empties_it(self):
        scene = self._holding()
        apply_substance_ops(scene, [self._move()])

        interiors = {record["target_interior"]
                     for record in scene["substances"]}
        assert interiors == {"sump"}

    def test_the_destination_still_receives_it(self):
        scene = self._holding()
        apply_substance_ops(scene, [self._move()])

        [record] = scene["substances"]
        assert record["substance"] == "settled coolant"
        assert record["target_interior"] == "sump"

    def test_the_consumption_is_reported(self):
        scene = self._holding()
        warnings = []
        apply_substance_ops(scene, [self._move()], report=warnings.append)

        assert any("reservoir" in warning for warning in warnings)

    def test_a_body_own_product_at_that_region_is_not_consumed(self):
        """The discriminator that keeps this from eating a gland: matter a
        body produced AT that region is a source, not a stock, and it does not
        stop existing because some of it was moved. Only foreign matter --
        deposited there by something else -- is a quantity that can be used
        up."""
        scene = self._holding(source="Vessel")
        apply_substance_ops(scene, [self._move()])

        interiors = {record["target_interior"]
                     for record in scene["substances"]}
        assert interiors == {"reservoir", "sump"}

    def test_matter_in_a_different_region_is_untouched(self):
        scene = self._holding()
        apply_substance_ops(scene, [self._move(source_part="intake")])

        interiors = {record["target_interior"]
                     for record in scene["substances"]}
        assert interiors == {"reservoir", "sump"}

    def test_another_body_matter_is_untouched(self):
        """Conservation is per body. Emitter releasing from its own nozzle
        must not empty the reservoir of whoever it last filled."""
        scene = self._holding()
        apply_substance_ops(scene, [{
            "op": "add", "source": "Emitter", "source_part": "reservoir",
            "substance": "settled coolant", "target": "Witness",
            "placement": "surface", "target_part": "shell"}])

        interiors = {record.get("target_interior")
                     for record in scene["substances"]}
        assert "reservoir" in interiors

    def test_matter_still_leaves_when_the_destination_already_holds_a_pool(self):
        """Found by replaying the live ledger: pooling ran first and returned
        early, so a swallow into a stomach that had already received some
        never emptied the mouth. Matter moved is matter moved -- whether the
        destination is a fresh row or one already standing there says nothing
        about the origin."""
        scene = self._holding()
        apply_substance_ops(scene, [self._move()])
        apply_substance_ops(scene, [_release(
            target="Vessel", placement="interior",
            target_interior="reservoir")])
        apply_substance_ops(scene, [self._move()])

        interiors = {record["target_interior"]
                     for record in scene["substances"]}
        assert interiors == {"sump"}

    def test_an_ordinary_release_still_deposits_normally(self):
        """The common case has no standing stock at the source region at all,
        and must not become a special case."""
        scene = _scene()
        apply_substance_ops(scene, [_release()])

        assert len(scene["substances"]) == 1
