"""Tests for LLM output preprocessing/validation in schemas.py."""

from schemas import validate_llm_output_strict

def _base_character_output(considered_responses):
    return {
        "sequence": [],
        "considered_responses": considered_responses,
    }

def test_character_considered_responses_accepts_plain_strings():
    report = validate_llm_output_strict(
        "character",
        _base_character_output(["Stay quiet.", "Speak up."]),
    )

    assert report.valid
    assert report.output["considered_responses"] == [
        "Stay quiet.", "Speak up.",
    ]

def test_character_considered_responses_coerces_structured_entries():
    # considered_responses is internal deliberation scratch with no
    # downstream reader (see schemas.py::_coerce_considered_responses).
    # Some models emit structured {"response": ..., "score": ...} entries
    # instead of the declared list[str]; this used to hard-fail the whole
    # character step (and therefore the whole turn) on a field nothing
    # actually consumes.
    report = validate_llm_output_strict(
        "character",
        _base_character_output([
            {"response": "Stay quiet.", "score": 0.4},
            {"text": "Speak up."},
            {"content": ""},
            42,
        ]),
    )

    assert report.valid, report.errors
    assert report.output["considered_responses"] == [
        "Stay quiet. (score: 0.4)",
        "Speak up.",
        "42",
    ]

def test_director_resolve_conditions_as_empty_list_is_coerced():
    # Live crash: state_diff.conditions is typed dict[str, list[dict]],
    # but a model reporting "nothing persistent happened" returned []
    # instead of {} -- both mean "empty" to a model, but pydantic rejects
    # the type mismatch outright, hard-failing the whole turn.
    report = validate_llm_output_strict(
        "director_resolve",
        {
            "resolved_event": "Nothing persistent occurs.",
            "state_diff": {"conditions": []},
        },
    )

    assert report.valid, report.errors
    assert report.output["state_diff"]["conditions"] == {}

def test_director_resolve_conditions_as_list_of_dicts_is_grouped():
    report = validate_llm_output_strict(
        "director_resolve",
        {
            "resolved_event": "Mara is wounded.",
            "state_diff": {
                "conditions": [
                    {"condition_id": "bleeding_mara", "subject_id": "Mara", "kind": "wound"},
                ],
            },
        },
    )

    assert report.valid, report.errors
    assert report.output["state_diff"]["conditions"] == {
        "bleeding_mara": [
            {"condition_id": "bleeding_mara", "subject_id": "Mara", "kind": "wound"},
        ],
    }

def test_director_resolve_state_diff_dict_fields_as_empty_lists_are_coerced():
    report = validate_llm_output_strict(
        "director_resolve",
        {
            "resolved_event": "Nothing changes.",
            "state_diff": {
                "positions": [], "rooms": [], "entities": [],
                "overlays": [], "attire": [],
            },
        },
    )

    assert report.valid, report.errors
    sd = report.output["state_diff"]
    assert sd["positions"] == {} and sd["rooms"] == {}
    assert sd["entities"] == {} and sd["overlays"] == {}
    assert sd["attire"] == {}

def test_director_establish_dict_fields_as_empty_lists_are_coerced():
    report = validate_llm_output_strict(
        "director_establish",
        {
            "rooms": {"hall": {"name": "Hall", "adjacent": []}},
            "positions": {"Mara": "hall"},
            "entities": [],
            "attire": [],
            "entity_states": [],
        },
    )

    assert report.valid, report.errors
    assert report.output["entities"] == {}
    assert report.output["attire"] == {}
    assert report.output["entity_states"] == {}
