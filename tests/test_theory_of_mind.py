"""Tests for character reference and mind-model normalization."""

import json

from agents import cap_mind_model_updates, normalize_character_refs
from story.character_schema import default_character_data

def test_name_tom_trigger_becomes_id():
    sheet = default_character_data("Alex")

    cast = [{
        "id": 7,
        "sheet": json.dumps(sheet),
    }]

    assert normalize_character_refs(["Alex"], cast) == [7]
    assert normalize_character_refs(["alex"], cast) == [7]
    assert normalize_character_refs(["7"], cast) == [7]
    assert normalize_character_refs([7], cast) == [7]
    assert normalize_character_refs(["Unknown"], cast) == []

def test_duplicate_character_references_are_removed():
    sheet = default_character_data("Alex")
    cast = [{
        "id": 7,
        "sheet": json.dumps(sheet),
    }]

    assert normalize_character_refs(
        ["Alex", "alex", "7", 7],
        cast,
    ) == [7]

def test_invalid_confidence_uses_default():
    updates = [{
        "about_entity": "unknown:1",
        "kind": "goal",
        "claim": "They may want to leave.",
        "confidence": "invalid",
        "evidence": [],
    }]

    capped = cap_mind_model_updates(updates)

    assert capped[0]["confidence"] == 0.5