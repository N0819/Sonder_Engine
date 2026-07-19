import json
from agents import normalize_character_refs, cap_mind_model_updates

def test_name_tom_trigger_becomes_id():
    cast = [
        {
            "id": 7,
            "sheet": json.dumps({
                "identity": {"name": "Alex"},
                "psychology": {"traits": []},
            }),
        }
    ]

    assert normalize_character_refs(["Alex"], cast) == [7]
    assert normalize_character_refs([7], cast) == [7]
    assert normalize_character_refs(["Unknown"], cast) == []

def test_identity_inference_is_capped():
    updates = [{
        "about_entity": "unknown:1",
        "kind": "identity",
        "claim": "This person belongs to a specific group.",
        "confidence": 0.95,
        "evidence": [],
    }]

    capped = cap_mind_model_updates(updates)
    assert capped[0]["confidence"] == 0.35

def test_observation_confidence_is_preserved():
    updates = [{
        "about_entity": "unknown:1",
        "kind": "observation",
        "claim": "They are holding a sword.",
        "confidence": 1.0,
        "evidence": [],
    }]

    capped = cap_mind_model_updates(updates)
    assert capped[0]["confidence"] == 1.0