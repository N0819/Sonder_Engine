"""A decision the model left unanswered is said, never silently a "no".

`decide` merged what came back and returned it; a key the model left out
was simply absent, and `probability(None)` is 0.0 -- a confident "no". So
`director_prose.select_channels`, which FAILS OPEN (every channel granted)
when the decision model raises, read a missing channel as not touched, with
no warning (review 2026-11-01, llm_schemas_prompts F7). Which way an
unanswered question fails is the caller's to say -- "is this channel
touched?" fails open, "does she strike?" must not -- so the engine's part is
that it is never silent: `unanswered()` names them for a caller, and the
step is told.
"""
from __future__ import annotations

import pytest

from core.pipeline_context import current_warning_sink
from llm import decisions


@pytest.fixture
def said():
    seen = []
    token = current_warning_sink.set(seen.append)
    yield seen
    current_warning_sink.reset(token)


QUESTIONS = {
    "attire": {"type": "noul", "instructions": "Does the passage change clothing?"},
    "positions": {"type": "noul", "instructions": "Does anyone move?"},
}


def _wire(monkeypatch, answers):
    monkeypatch.setattr(decisions, "OVERRIDE", None)
    monkeypatch.setattr(decisions, "_provider", lambda: {"api_key": "k"})
    monkeypatch.setattr(decisions, "_explicit_url", lambda: "")
    monkeypatch.setattr(decisions, "_post",
                        lambda prov, model, state, questions: dict(answers))


def test_a_missing_key_is_named_and_said(monkeypatch, said):
    _wire(monkeypatch, {"attire": {"type": "noul", "noul": 0.9}})
    got = decisions.decide("PASSAGE: she steps out.", QUESTIONS)
    assert decisions.unanswered(QUESTIONS, got) == ["positions"]
    assert any("positions" in w and "unanswered" in w for w in said), said


def test_a_whole_answer_says_nothing(monkeypatch, said):
    _wire(monkeypatch, {"attire": {"type": "noul", "noul": 0.9},
                        "positions": {"type": "noul", "noul": 0.1}})
    got = decisions.decide("PASSAGE", QUESTIONS)
    assert decisions.unanswered(QUESTIONS, got) == []
    assert said == []


def test_a_reply_that_is_not_an_object_is_a_decision_error(monkeypatch):
    """`_post` read `body.get` on whatever came back; a JSON list raised
    AttributeError rather than the typed failure callers expect."""
    class _Resp:
        status_code = 200
        text = "[]"

        def json(self):
            return []

    class _Http:
        def post(self, *a, **k):
            return _Resp()

    monkeypatch.setattr(decisions, "_http", lambda: _Http())
    monkeypatch.setattr(decisions, "_url", lambda prov: "http://x")
    with pytest.raises(decisions.DecisionError):
        decisions._post({"api_key": "k", "kind": "openrouter"}, "m", "s", QUESTIONS)
