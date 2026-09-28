"""An encoder transform's patch must survive its channel owner's schema.

The encoder's transforms are split by channel owner and validated against the
owner's model (`schemas.validated_specialist_patch_channels`) before they are
folded. The causal hands' semantic check on their positional receipts went
with them (2026-09-27); what it caught -- a garment-keyed attire patch, a
contact whose two endpoints are one body -- is now card text only
(`docs/UNBUILT_PIPELINE.md` § 1.1)."""

import pytest

from llm.schemas import (
    validated_specialist_patch_channels, normalize_causal_patch_shape,
)


def test_nested_pose_table_is_lifted_without_losing_the_station():
    clean, dropped = validated_specialist_patch_channels("director_spatial", {
        "stations": {"Mara": {"at": "chair"},
                     "poses": {"Mara": {"posture": "seated"}}}})
    assert not dropped
    assert clean == {"stations": {"Mara": {"at": "chair"}},
                     "poses": {"Mara": {"posture": "seated"}}}


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


def test_patch_validator_keeps_outer_and_state_channels_together():
    patch = {"public_evidence": [{"source_id": "line:1", "salience": 0.5}],
             "introductions": [{"who": "Sera", "learns": "Tomas"}]}
    clean, dropped = validated_specialist_patch_channels("director_social", patch)
    assert not dropped
    assert clean == patch


def test_patch_validator_prunes_bad_outer_channel_without_losing_state():
    clean, dropped = validated_specialist_patch_channels("director_social", {
        "public_evidence": 23,
        "introductions": [{"who": "Sera", "learns": "Tomas"}],
    })
    assert dropped == ["public_evidence"]
    assert clean == {"introductions": [{"who": "Sera", "learns": "Tomas"}]}


@pytest.mark.parametrize("role,patch", [
    ("director_spatial", {"stations": {"Mara": {"at": None, "near": []}}}),
    ("director_spatial", {"poses": {"Mara": {}}}),
    ("director_spatial", {"poses": {"Mara": {"posture": ""}}}),
    ("director_spatial", {"poses": {"Mara": "seated"}}),
    ("director_contact", {"containment": {"key": None}}),
    ("director_body", {"attire": {"Mara": {"wearing": []}}}),
    ("director_body", {"conditions": {"Mara": []}}),
])
def test_explicit_clears_and_supported_short_shapes_remain_valid(role, patch):
    _clean, dropped = validated_specialist_patch_channels(role, patch)
    assert dropped == []

