"""An encoded positional receipt must survive the channel schema round trip."""

import pytest

from llm.schemas import (
    semantic_output_errors, validate_llm_output_strict,
    validated_specialist_patch_channels, normalize_causal_patch_shape,
)


def _output(patch):
    return {"results": [{"status": "encoded", "transforms": [{
        "item": "Mara", "patch": patch,
    }]}]}


def _payload(*categories, **extra):
    return {"ledgers": [{"item_names": ["Mara", "Chair"],
                         "categories": list(categories)}], **extra}


def test_nested_pose_table_is_lifted_without_losing_the_station():
    payload = _payload("stations", "poses")
    output = _output({"stations": {
        "Mara": {"at": "chair"}, "poses": {"Mara": {"posture": "seated"}},
    }})
    notes = []
    errors = semantic_output_errors(
        "director_spatial", output, source_payload=payload, notes=notes)
    assert not errors
    assert any("lifted poses table" in note for note in notes)
    clean, dropped = validated_specialist_patch_channels(
        "director_spatial", output["results"][0]["transforms"][0]["patch"])
    assert not dropped
    assert clean == {"stations": {"Mara": {"at": "chair"}},
                     "poses": {"Mara": {"posture": "seated"}}}

    report = validate_llm_output_strict(
        "director_spatial", _output({
            "stations": {"Mara": {"at": "chair"}},
            "poses": {"Mara": {"posture": "seated", "support": "chair"}},
        }), source_payload=payload)
    assert report.valid, report.errors
    assert report.output["results"][0]["transforms"][0]["patch"]["poses"]["Mara"][
        "posture"] == "seated"


@pytest.mark.parametrize("patch", [
    {"stations": {"poses": {"Mara": {"posture": "seated"}}}, "poses": {}},
    {"stations": {"poses": {"Mara": {"posture": "seated", "bogus": True}}}},
    {"stations": {"poses": {"Mara": {"posture": {"seated": True}}}}},
    {"stations": {"poses": {"Mara": "seated"}}},
    {"stations": {"poses": {"Mara": {}}}},
    {"stations": {"poses": {"at": "chair"}}},
    {"stations": {"poses": {"at": {"posture": "seated"}}}},
])
def test_pose_lift_refuses_ambiguous_shapes_and_competing_outer_table(patch):
    assert normalize_causal_patch_shape(patch) is patch


def test_nested_pose_with_competing_outer_table_still_requires_repair():
    errors = semantic_output_errors("director_spatial", _output({
        "stations": {"poses": {"Mara": {"posture": "seated"}}},
        "poses": {"Mara": {"posture": "standing"}},
    }), source_payload=_payload("poses"))
    assert any("stations.poses is not a station" in error for error in errors)


@pytest.mark.parametrize("patch", [
    {},
    {"stations": {}},
    {"stations": {"Mara": {"seated": True}}},
    {"poses": {"Mara": {"stations": {"at": "chair"}}}},
    {"positions": ["office"]},
    {"entities": {"box": {"state": {"hatch": "open"}}}},
    {"state_assertions": {"poses": {"Mara": "seated"}}},
])
def test_encoded_empty_malformed_or_unowned_patches_fail(patch):
    assert semantic_output_errors(
        "director_spatial", _output(patch),
        source_payload=_payload("stations"))


def test_unknown_only_entity_record_cannot_count_as_encoded():
    errors = semantic_output_errors(
        "director_objects", _output({"entities": {"box": {"bogus": True}}}),
        source_payload=_payload("entities"))
    assert any("no surviving owned state write" in error for error in errors)


def test_outer_public_evidence_channel_counts_as_an_owned_write():
    assert not semantic_output_errors(
        "director_social", _output({"public_evidence": [{
            "source_id": "line:1", "speech_acts": [{
                "kind": "promise", "content": "I will return.",
            }], "salience": 0.5,
        }]}), source_payload=_payload("public_evidence"))


def test_patch_validator_keeps_outer_and_state_channels_together():
    patch = {"public_evidence": [{"source_id": "line:1", "salience": 0.5}],
             "world_facts": ["The gate is open."]}
    clean, dropped = validated_specialist_patch_channels("director_social", patch)
    assert not dropped
    assert clean == patch


def test_patch_validator_prunes_bad_outer_channel_without_losing_state():
    clean, dropped = validated_specialist_patch_channels("director_social", {
        "public_evidence": 23,
        "world_facts": ["The gate is open."],
    })
    assert dropped == ["public_evidence"]
    assert clean == {"world_facts": ["The gate is open."]}


@pytest.mark.parametrize("patch", [
    {"entities": {"box": {"state": {"hatch": "open"}}}},
    {"entities": {"box": {"state": {"hatch": "closed", "lit": False}}}},
    {"entities": {"box": '{"state":{"hatch":"open"}}'}},
    {"remove_entities": ["box"]},
])
def test_partial_entity_changes_survive_without_repeating_the_name(patch):
    assert not semantic_output_errors(
        "director_objects", _output(patch),
        source_payload=_payload("entities"))


@pytest.mark.parametrize("role,patch", [
    ("director_spatial", {"stations": {"Mara": {"at": None, "near": []}}}),
    ("director_spatial", {"poses": {"Mara": {}}}),
    ("director_spatial", {"poses": {"Mara": {"posture": ""}}}),
    ("director_spatial", {"poses": {"Mara": "seated"}}),
    ("director_spatial", {"state_diff": {"poses": {"Mara": "seated"}}}),
    ("director_contact", {"containment": {"key": None}}),
    ("director_body", {"attire": {"Mara": {"wearing": []}}}),
    ("director_body", {"conditions": {"Mara": []}}),
])
def test_explicit_clears_and_supported_short_shapes_remain_valid(role, patch):
    assert not semantic_output_errors(
        role, _output(patch), source_payload=_payload())


def test_sole_pose_route_cannot_be_acquitted_by_a_station_write():
    output = _output({"stations": {"Mara": {"at": "chair"}}})
    errors = semantic_output_errors(
        "director_spatial", output, source_payload=_payload("poses"))
    assert any("routes poses but writes no poses" in error for error in errors)


def test_mixed_route_allows_an_already_true_pose_alongside_a_changed_station():
    notes = []
    assert not semantic_output_errors(
        "director_spatial", _output({"stations": {"Mara": {"at": "chair"}}}),
        source_payload=_payload("stations", "poses"), notes=notes)
    assert any("verify whether the pose was already true" in note for note in notes)


def test_worn_garment_is_not_an_attire_subject_but_new_bodies_are_permitted():
    payload = _payload(
        "attire", worn_garments=[{"name": "Orange work jacket", "worn_by": "Nia"}],
        identity_index={"persona:1": "Nia"}, attire={"Nia": {"wearing": [
            "Orange work jacket"]}})
    errors = semantic_output_errors(
        "director_body", _output({"attire": {
            "Orange work jacket": {"remove": ["Orange work jacket"]},
        }}), source_payload=payload)
    assert any("key attire by its wearer" in error for error in errors)
    for subject in ("Nia", "New body"):
        assert not semantic_output_errors(
            "director_body", _output({"attire": {subject: {
                "remove": ["Orange work jacket"],
            }}}), source_payload=payload)


@pytest.mark.parametrize("known", [
    {"identity_index": {"character:2": "Orange work jacket"}},
    {"attire": {"Orange work jacket": {"wearing": []}}},
])
def test_known_body_may_share_a_worn_garment_name(known):
    assert not semantic_output_errors(
        "director_body", _output({"attire": {
            "Orange work jacket": {"add": ["Hat"]},
        }}), source_payload=_payload("attire", worn_garments=[{
            "name": "Orange work jacket", "worn_by": "Nia",
        }], **known))


@pytest.mark.parametrize("status", ["already_true", "not_mine", "no_referent"])
def test_nonencoded_verdicts_do_not_require_a_write(status):
    assert not semantic_output_errors(
        "director_spatial", {"results": [{"status": status, "transforms": []}]},
        source_payload=_payload("poses"))


def test_contact_with_identical_endpoints_is_repaired_before_engine_drops_it():
    from llm.schemas import semantic_output_errors
    payload = {"completion_contract": "verified_effects_v1", "identity_index": {"persona:1": "Noa"},
               "ledgers": [{"item_names": ["Violet coat"], "categories": ["contact_ops"]}]}
    result = {"results": [{"status": "encoded", "settled": {}, "transforms": [
        {"item": "Violet coat", "patch": {"contact_ops": [{"op": "add", "actor": "persona:1",
          "target": "Noa", "actor_part": "hands", "manner": "hold"}]}}]}]}
    errors = semantic_output_errors("director_contact", result, source_payload=payload)
    assert any("identical actor and target" in error for error in errors)
