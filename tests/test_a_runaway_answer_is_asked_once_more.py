"""AN ANSWER THAT RAN AWAY IS ASKED ONCE MORE, NOT LOST WITH THE BEAT.

O27 of the Cwm Du validation run (chat 167, turn 4630): the character model
ran away into a repeated phrase, the stream guard killed it as
`DegenerateOutput` -- an LLMError -- and the validated-JSON ladder filed it
as the provider's failure, which bars the one fresh ask a malformed answer
gets (D5, `test_a_malformed_repair_gets_one_fresh_attempt.py`). The beat
aborted: "character_bare: all providers failed (last provider error:
Degenerate model output: repeating 26-character phrase)". The owner: an
aborted beat is the worst break.

Now a runaway is kept apart from an outage (`llm_quality` `runaway`): it
leaves no draft to repair, and earns the fresh ask, which goes out ONCE --
the transport does not re-ask its runaway again
(`providers.RetryConfig.degenerate_retries`) -- and a beat lost after it
says it ran away. An outage is what it was.
"""

from __future__ import annotations

import pytest

from core.pipeline_context import current_warning_sink
from llm import llm_quality, providers
from llm.providers import DegenerateOutput, LLMError
from tests.test_a_malformed_repair_gets_one_fresh_attempt import GOOD, _invalid


class _Scripted:
    """chat_complete, scripted: a string is the answer, an exception is raised."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, role, system, user, **kwargs):
        self.calls.append({"system": system, "user": user, **kwargs})
        if not self.responses:
            raise AssertionError("chat_complete called more times than scripted")
        out = self.responses.pop(0)
        if isinstance(out, Exception):
            raise out
        return out


@pytest.fixture
def warnings():
    seen = []
    token = current_warning_sink.set(seen.append)
    yield seen
    current_warning_sink.reset(token)


def _ladder(monkeypatch, responses):
    llm = _Scripted(responses)
    monkeypatch.setattr(llm_quality, "chat_complete", llm)
    monkeypatch.setattr(llm_quality, "role_candidate_count", lambda role: 1)
    monkeypatch.setattr(llm_quality, "_targeted_field_patch", lambda *a, **k: None)
    return llm


def _run():
    return llm_quality.complete_validated_json(
        role="encoder", step_key="director_specialist",
        system="THE ENCODER SHEET", payload={"prose": "Mara lifts the key."},
        temperature=0.2)


def _runaway():
    return DegenerateOutput("repeating 26-character phrase")


def test_an_answer_that_ran_away_is_asked_afresh_once(monkeypatch, warnings):
    llm = _ladder(monkeypatch, [_runaway(), GOOD])
    out = _run()
    assert out["events"][0]["event"] == "Mara lifts the key"
    assert len(llm.calls) == 2
    first, fresh = llm.calls
    assert fresh["system"] == first["system"] and fresh["user"] == first["user"]
    assert llm_quality.answered_by.get() == "fresh"
    # the fresh ask goes out once: the transport never re-asks its runaway
    assert fresh["retry_config"].degenerate_retries == 0
    assert any("the answer ran away (repeating 26-character phrase); asked the "
               "original request afresh" in w for w in warnings), warnings


def test_a_fresh_ask_that_runs_away_too_loses_the_beat_and_says_why(monkeypatch, warnings):
    llm = _ladder(monkeypatch, [_runaway(), _runaway()])
    with pytest.raises(RuntimeError) as err:
        _run()
    assert len(llm.calls) == 2
    assert "ran away (repeating 26-character phrase)" in str(err.value)
    assert "all providers failed" not in str(err.value)


def test_an_outage_is_not_a_runaway_and_is_not_asked_afresh(monkeypatch, warnings):
    llm = _ladder(monkeypatch, [LLMError("HTTP 503: unavailable", 503, True)])
    with pytest.raises(RuntimeError) as err:
        _run()
    assert len(llm.calls) == 1
    assert "all providers failed" in str(err.value)


def test_a_repair_that_runs_away_still_earns_the_fresh_ask(monkeypatch, warnings):
    llm = _ladder(monkeypatch, [_invalid(), _runaway(), GOOD])
    out = _run()
    assert out["events"][0]["event"] == "Mara lifts the key"
    assert len(llm.calls) == 3
    assert llm_quality.answered_by.get() == "fresh"


def test_the_transport_asks_a_runaway_again_unless_told_not_to():
    runaway = _runaway()
    assert providers._should_retry(runaway, 0, providers.RetryConfig())
    assert not providers._should_retry(runaway, 0, providers.RetryConfig(degenerate_retries=0))
    outage = LLMError("HTTP 503", 503, True)
    assert providers._should_retry(outage, 0, providers.RetryConfig(degenerate_retries=0))
