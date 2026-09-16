"""Current learning and decision fields must carry usable, bounded content."""

from copy import deepcopy

import pytest

from agents.character_kernel import compile_character_kernel
from llm.schemas import output_example, validate_llm_output_strict


def _answer(update=None):
    raw = deepcopy(output_example("character_kernel"))
    if update is not None:
        raw["updates"]["beliefs"] = [update]
    return raw


def _revision(**extra):
    return {
        "belief": "The north stair is unsafe to use.",
        "operation": "revise", "target_belief": "The north stair is safe to use.",
        "confidence": 0.9, "evidence": [{"event_id": "o1"}], **extra,
    }


def test_live_incomplete_revision_fails_at_the_current_kernel_boundary():
    # The model contradicted this conviction in speech but supplied only
    # these three learning fields. Legacy defaults made the row validate,
    # after which grounding dropped it and the old conviction survived.
    raw = _answer({"belief": "The north stair is safe to use.",
                   "operation": "revise", "emotional_charge": 0.1})
    raw["sequence"] = [{"type": "speech", "text": "The north stair is not safe."}]

    report = validate_llm_output_strict("character_kernel", raw)

    assert not report.valid
    for field in ("target_belief", "confidence", "evidence"):
        assert any(field in error for error in report.errors), report.errors


@pytest.mark.parametrize("missing", [
    "belief", "operation", "target_belief", "confidence", "evidence",
])
def test_every_current_belief_update_requires_its_learning_contract(missing):
    update = _revision()
    del update[missing]

    report = validate_llm_output_strict("character_kernel", _answer(update))

    assert not report.valid
    assert any(missing in error for error in report.errors), report.errors


@pytest.mark.parametrize("replacement", [
    {"target_belief": ""}, {"target_belief": "   "}, {"target_belief": None},
    {"confidence": None}, {"operation": None}, {"operation": "replace"},
    {"evidence": None}, {"evidence": []}, {"evidence": [{}]},
    {"evidence": [{"fact": "The stair collapsed."}]},
    {"evidence": [{"event_id": "   "}]},
])
def test_current_revision_refuses_absent_values_disguised_as_filled_fields(replacement):
    report = validate_llm_output_strict(
        "character_kernel", _answer(_revision(**replacement)))

    assert not report.valid, report.output


@pytest.mark.parametrize("operation", ["reinforce", "weaken", "contradict"])
def test_other_operations_require_an_explicitly_empty_target(operation):
    invalid = validate_llm_output_strict(
        "character_kernel", _answer(_revision(operation=operation)))
    valid = validate_llm_output_strict(
        "character_kernel", _answer(_revision(operation=operation, target_belief="")))

    assert not invalid.valid
    assert valid.valid, valid.errors
    assert valid.output["updates"]["beliefs"][0]["target_belief"] == ""


@pytest.mark.parametrize("confidence", [0.0, 0.9])
def test_complete_revision_preserves_the_requested_result_through_compilation(confidence):
    raw = _answer(_revision(confidence=confidence))

    report = validate_llm_output_strict("character_kernel", raw)
    assert report.valid, report.errors
    compiled, warnings = compile_character_kernel(report.output)
    assert not warnings
    legacy = validate_llm_output_strict("character", compiled)

    assert legacy.valid, legacy.errors
    update = legacy.output["belief_updates"][0]
    assert update["target_belief"] == raw["updates"]["beliefs"][0]["target_belief"]
    assert update["confidence"] == confidence
    assert update["evidence"][0]["event_id"] == "o1"


def test_legacy_belief_update_defaults_still_read_archived_partial_rows():
    report = validate_llm_output_strict("character", {"belief_updates": [{
        "belief": "The north stair is safe to use.", "operation": "revise",
        "emotional_charge": 0.1,
    }]})

    assert report.valid, report.errors
    update = report.output["belief_updates"][0]
    assert update["confidence"] == 0.5
    assert update["target_belief"] == ""
    assert update["evidence"] == []


@pytest.mark.parametrize("field", ["want", "hinge", "uncertainty"])
@pytest.mark.parametrize("length,valid", [(240, True), (241, False), (8000, False)])
def test_current_choice_fields_reject_runaway_text_without_clipping(field, length, valid):
    raw = _answer()
    text = "x" * length
    if field == "want":
        raw["state"]["active"]["wants"] = [{"id": "w1", "want": text}]
    else:
        raw["state"]["decision"][field] = text

    report = validate_llm_output_strict("character_kernel", raw)

    assert report.valid is valid, report.errors
    if valid:
        actual = (report.output["state"]["active"]["wants"][0]["want"]
                  if field == "want" else report.output["state"]["decision"][field])
        assert actual == text
    else:
        assert any(field in error for error in report.errors), report.errors


def test_legacy_wants_keep_their_existing_text_acceptance():
    text = "A legacy desire. " * 100
    report = validate_llm_output_strict("character", {
        "active_state": {"wants": [{"want": text}]},
    })

    assert report.valid, report.errors
    assert report.output["active_state"]["wants"][0]["want"] == text


def test_kernel_examples_omit_mood_but_the_local_reader_accepts_the_legacy_alias():
    raw = _answer()
    assert "mood" not in raw["state"]["active"]
    raw["state"]["active"]["mood"] = "wary"

    report = validate_llm_output_strict("character_kernel", raw)

    assert report.valid, report.errors
    assert report.output["state"]["active"]["mood"] == "wary"
