"""Tests for LLM output preprocessing/validation in schemas.py."""

from llm.schemas import validate_llm_output_strict

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

def test_director_resolve_condition_scalar_state_is_safely_normalized():
    report = validate_llm_output_strict(
        "director_resolve",
        {
            "resolved_event": "Mara falls asleep.",
            "state_diff": {"conditions": {"sleeping_mara": [{
                "subject_id": "Mara", "kind": "awareness",
                "state": "asleep",
            }]}},
        },
    )

    assert report.valid, report.errors
    condition = report.output["state_diff"]["conditions"]["sleeping_mara"][0]
    assert condition["state"] == {}

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


def test_every_worked_example_validates_against_the_schema_it_illustrates():
    """An example is instruction, and a wrong one instructs wrongly.

    `OUTPUT_EXAMPLES[step]` is handed to the model verbatim as
    `required_json_example` on every repair and every fallback candidate -- so
    a call that just failed validation is answered with an object the same
    validator also rejects. Two were live when this test was written:
    `scene_life` omitted the required `speech.speaker` on its first entry, and
    `director_establish` failed its own semantic check with empty `rooms` and
    `positions`. Both were teaching a shape that cannot commit.

    This is the second time a wrong example has been found (the first cost a
    complete 4,000-token resolve, whose repair was handed the same broken
    example that caused the failure and could not converge), so the guard is
    the class rather than the two.
    """
    from llm.schemas import OUTPUT_EXAMPLES, validate_llm_output_strict

    broken = {}
    for step_key, example in sorted(OUTPUT_EXAMPLES.items()):
        report = validate_llm_output_strict(step_key, example)
        if not report.valid:
            broken[step_key] = report.errors[:4]
    assert not broken, (
        "worked examples that their own validator rejects: "
        + "; ".join(f"{step}: {errors}" for step, errors in broken.items()))


def test_specialist_channel_shapes_match_what_the_models_declare():
    """The empty-value coercion is chosen from a hand-kept list, and a hand-
    kept list drifts. `comms_ops` was declared `list[CommsOp]` and classified
    as a dict channel, so an empty `comms_ops: []` -- the ordinary way a model
    says "no voice channel changed this beat" -- was rewritten to `{}` on the
    way in. Inert only because `LenientModel` reversed it on the way out,
    which is a second mechanism covering for the first rather than a reason
    the first is right.
    """
    from llm import schemas

    wrong = []
    for step_key, channels in schemas.SPECIALIST_CHANNELS.items():
        fields = schemas._fields(schemas.SCHEMA_MAP[step_key])
        for channel in channels:
            declared = schemas._declared(fields[channel])
            if declared.is_list:
                expected = "list"
            elif declared.expects_object:
                expected = "dict"
            else:
                continue
            classified = (
                "dict" if channel in schemas._SPECIALIST_DICT_CHANNELS
                else "list" if channel in schemas._SPECIALIST_LIST_CHANNELS
                else "unclassified")
            if classified != expected:
                wrong.append(f"{step_key}.{channel}: declared {expected}, "
                             f"coerced as {classified}")
    assert not wrong, "; ".join(wrong)


def test_observation_defaults_are_the_values_the_compactor_omits():
    """`Observation`'s own comment says absent means the default, and names
    `composer.OBSERVATION_DEFAULTS` as the projection that omits them. They
    disagreed on all three advisory axes -- intensity 0.5 vs 0.35, suddenness
    0.0 vs 0.1, ambiguity 0.5 vs 0.15 -- so a compacted observation read back
    through the schema came out saying something the compactor never said.
    """
    from agents.composer import OBSERVATION_DEFAULTS
    from llm.schemas import Observation, _declared, _fields

    fields = _fields(Observation)
    for name, expected in OBSERVATION_DEFAULTS.items():
        assert _declared(fields[name]).default == expected, name
    # `null` and an omitted key are two spellings of "not said" and must land
    # on the same number: the pre-validator fallback is the other half.
    for name in ("intensity", "suddenness", "ambiguity"):
        parsed = Observation(**{"observation_id": "current:x:0", name: None})
        assert getattr(parsed, name) == OBSERVATION_DEFAULTS[name], name
