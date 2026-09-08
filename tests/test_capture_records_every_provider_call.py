"""One capture row per PROVIDER CALL (review 2026-09-07 A84).

`complete_validated_json` is a ladder: the first call, a truncation re-ask, a
targeted field patch on the cheap `repair` model, a temperature-0 rebuild, and
one call per fallback candidate. Debug capture saw three of those five, and
saw them wrong -- `_captured` was a closure over the OUTER `system` and
`payload` with `ok: True` hardcoded, so:

* a beat rebuilt by the temperature-0 repair recorded the step's own sheet and
  payload against the repair's answer, an exchange that never happened;
* the targeted field patch and the fallback candidates answered through
  `_accepted` and recorded nothing at all -- the cheap model's whole rung was
  invisible, cost included;
* no failed attempt was recorded ever, so a provider error, a parse failure
  and a validation failure were indistinguishable from a call that was never
  made. The invisible-second-call rate the 2026-08-11 audit could not measure
  is exactly this.

The rule that now holds: every `chat_complete` in this module reports what it
actually sent, what came back verbatim, and whether that attempt stood.
"""

from __future__ import annotations

import json

import pytest

from llm import llm_quality
from llm.providers import LLMError
from agents.common import _agent_json
from core.pipeline_context import current_exchange_sink


class _ScriptedLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, role, system, user, **kwargs):
        self.calls.append({"role": role, "system": system, "user": user})
        if not self.responses:
            raise AssertionError("chat_complete called more times than scripted")
        answer = self.responses.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


@pytest.fixture
def captured(monkeypatch):
    """Arm the exchange sink the way `runtime._run_step` does."""
    seen = []
    token = current_exchange_sink.set(seen.append)
    monkeypatch.setattr(llm_quality, "role_candidate_count", lambda role: 1)
    yield seen
    current_exchange_sink.reset(token)


def _candidates(monkeypatch, n):
    monkeypatch.setattr(llm_quality, "role_candidate_count", lambda role: n)


def _script(monkeypatch, responses):
    llm = _ScriptedLLM(responses)
    monkeypatch.setattr(llm_quality, "chat_complete", llm)
    return llm


def _resolve(event="The door creaks open."):
    return json.dumps({"resolved_event": event, "summary": "door opened",
                       "state_diff": {}})


def test_an_accepted_first_call_is_one_row_carrying_what_came_back(
        monkeypatch, captured):
    _script(monkeypatch, [_resolve()])

    _agent_json("director", "director_resolve", "THE DIRECTOR SHEET", {"x": 1})

    assert len(captured) == 1
    row = captured[0]
    assert row["ok"] is True and not row["error"]
    assert row["system"] == "THE DIRECTOR SHEET"
    assert row["payload"] == {"x": 1}
    # Verbatim, not the validated object: a truncation or a prose preamble is
    # only visible in what the provider actually sent.
    assert row["response"] == _resolve()


def test_a_failed_attempt_and_the_repair_that_followed_are_two_rows(
        monkeypatch, captured):
    """The repair rung sends a DIFFERENT sheet and a DIFFERENT payload, and
    the row for it used to claim the step's own."""
    _script(monkeypatch, ["this is not JSON at all", _resolve()])

    out = _agent_json("director", "director_resolve", "THE DIRECTOR SHEET",
                      {"x": 1})

    assert out["resolved_event"] == "The door creaks open."
    assert len(captured) == 2, captured
    failed, repaired = captured
    assert failed["ok"] is False and failed["error"]
    assert failed["system"] == "THE DIRECTOR SHEET"
    assert repaired["ok"] is True
    assert repaired["system"] != "THE DIRECTOR SHEET"
    assert set(repaired["payload"]) >= {"original_request",
                                        "validation_errors"}
    assert repaired["payload"]["original_request"] == {"x": 1}


def test_a_provider_error_is_recorded_rather_than_left_as_silence(
        monkeypatch, captured):
    """A down provider produced no row at all, so a beat that died on auth
    and a beat that was never attempted read identically."""
    _script(monkeypatch, [LLMError("model not found")])

    with pytest.raises(RuntimeError):
        _agent_json("director", "director_resolve", "THE DIRECTOR SHEET",
                    {"x": 1})

    assert [r["ok"] for r in captured] == [False]
    assert "model not found" in captured[0]["error"]
    assert captured[0]["response"] == ""


def test_a_fallback_candidate_that_saves_the_beat_is_recorded(
        monkeypatch, captured):
    """The rung that answers on a DIFFERENT provider, and the one whose
    success used to leave the turn looking like a clean first call."""
    _candidates(monkeypatch, 2)
    _script(monkeypatch, [LLMError("model not found"), _resolve()])

    out = _agent_json("director", "director_resolve", "THE DIRECTOR SHEET",
                      {"x": 1})

    assert out["resolved_event"] == "The door creaks open."
    assert [r["ok"] for r in captured] == [False, True]
    assert captured[1]["system"].startswith("THE DIRECTOR SHEET")
    assert set(captured[1]["payload"]) >= {"original_request", "failed_output"}


def test_the_cheap_patch_rung_is_no_longer_invisible(monkeypatch, captured):
    """`_targeted_field_patch` makes its own provider call on the `repair`
    role and answers with the corrected FIELDS, so it returned through
    `_accepted` and nothing recorded that a model had been asked anything."""
    _script(monkeypatch, [json.dumps({"summary": "s", "state_diff": {}})])

    llm_quality._targeted_field_patch(
        {"resolved_event": 4, "summary": "s"},
        ["resolved_event: str type expected"])

    assert [r["role"] for r in captured] == ["repair"]
    assert captured[0]["system"] and captured[0]["payload"]["invalid_fragments"]


def test_a_patch_that_touched_fields_and_still_failed_is_recorded_ok_false(
        monkeypatch, captured):
    """`ok` is whether the exchange STOOD, and acceptance is the caller's to
    decide: this rung splices fields and hands the object back for
    revalidation. It used to log `ok=bool(touched)`, so a patch that changed
    a field and still failed validation was recorded as the one thing the
    column is for saying it was not."""
    _script(monkeypatch, [json.dumps({"resolved_event": "still wrong"})])

    out = llm_quality._targeted_field_patch(
        {"resolved_event": 4, "summary": "s"},
        ["resolved_event: str type expected"],
        validate=lambda obj: False)

    assert out is not None, "the splice happened; only the verdict differs"
    assert [r["ok"] for r in captured] == [False]
    assert "still failed validation" in captured[0]["error"]


def test_a_patch_that_stood_is_recorded_ok_true(monkeypatch, captured):
    _script(monkeypatch, [json.dumps({"resolved_event": "The door opens."})])

    llm_quality._targeted_field_patch(
        {"resolved_event": 4, "summary": "s"},
        ["resolved_event: str type expected"],
        validate=lambda obj: obj["resolved_event"] == "The door opens.")

    assert [r["ok"] for r in captured] == [True]
    assert captured[0]["error"] == ""
