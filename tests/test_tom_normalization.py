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


# --- Cross-LLM robustness: mind_model_updates[].alternatives coercion ---
# Smaller / cheaper models routinely emit objects (or nested lists, or a bare
# string) where the schema wants list[str]. Before the coercion validator this
# hard-failed the whole character step ("alternatives.0: str type expected"),
# crashing the turn. It must now normalize instead, preserving the text.

from schemas import validate_llm_output_strict, _coerce_str_list, MindHypothesis


def _character_payload(alternatives):
    return {
        "sequence": [],
        "interaction": {},
        "mind_model_updates": [{
            "about_entity": "char_7",
            "kind": "goal",
            "claim": "She is hiding what she knows.",
            "confidence": 0.6,
            "evidence": [],
            "alternatives": alternatives,
        }],
    }


def test_alternatives_object_items_are_coerced_not_rejected():
    report = validate_llm_output_strict("character", _character_payload(
        [{"claim": "She is simply cautious.", "confidence": 0.3}]))
    assert report.valid, report.errors
    alts = report.output["mind_model_updates"][0]["alternatives"]
    assert alts == ["She is simply cautious."]


def test_alternatives_bare_string_and_nested_list_are_coerced():
    report = validate_llm_output_strict("character", _character_payload("She is loyal"))
    assert report.valid, report.errors
    assert report.output["mind_model_updates"][0]["alternatives"] == ["She is loyal"]

    report2 = validate_llm_output_strict("character", _character_payload([["a", "b"], "c"]))
    assert report2.valid, report2.errors
    assert report2.output["mind_model_updates"][0]["alternatives"] == ["a; b", "c"]


def test_coerce_str_list_helper_shapes():
    assert _coerce_str_list(None) == []
    assert _coerce_str_list("x") == ["x"]
    assert _coerce_str_list({"text": "hi"}) == ["hi"]
    assert _coerce_str_list([{"label": "L"}, 3]) == ["L", "3"]
    # object with no known text field falls back to stable JSON, never crashes
    assert _coerce_str_list([{"weird": 1}]) == ['{"weird": 1}']


def test_mind_hypothesis_model_accepts_object_alternatives():
    h = MindHypothesis(about_entity="char_7", kind="goal", claim="c",
                       alternatives=[{"claim": "alt"}])
    assert h.alternatives == ["alt"]