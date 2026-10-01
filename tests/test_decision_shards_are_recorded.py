"""A decision battery larger than one request is asked in shards, on worker
threads -- and every shard is a request the caller's call ledger must see.

The ledger sink (`providers.call_ledger_sink`) is a ContextVar, and a
`ThreadPoolExecutor` worker does not inherit the submitting thread's context,
so each shard recorded into nothing. Measured 2026-09-27 on the bare-card
replay: a round of 20 beats made two decision passes a beat, and the ledger
held 18 requests -- the after-call battery (100-200 questions, two to four
shards) never reached it, in the replay or in a live turn's usage.
"""

from __future__ import annotations

import requests

from llm import decisions, providers


def test_every_shard_of_a_large_battery_reaches_the_callers_ledger(monkeypatch):
    posted = []

    class Response:
        status_code = 200

        def __init__(self, questions):
            self._questions = questions

        def json(self):
            return {"answers": {k: {"type": "noul", "noul": 0.5} for k in self._questions},
                    "usage": {"input_tokens": 10, "output_tokens": 1}}

    def post(url, headers=None, json=None, timeout=None):
        posted.append(len(json["questions"]))
        return Response(json["questions"])

    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setattr(decisions, "_provider",
                        lambda: {"api_key": "k", "kind": "openrouter", "base_url": "https://example.invalid/api/v1"})
    size = decisions.MAX_QUESTIONS_PER_REQUEST * 2 + 5
    questions = {f"q{i}": {"type": "noul", "instructions": "?", "criteria": ""} for i in range(size)}

    ledger = []
    token = providers.call_ledger_sink.set(ledger.append)
    try:
        answers = decisions.decide("a state", questions)
    finally:
        providers.call_ledger_sink.reset(token)

    assert len(answers) == size and len(posted) == 3
    assert [entry["role"] for entry in ledger] == ["jev"] * 3
    assert sum(entry["in"] for entry in ledger) == 30


def test_a_request_closes_at_the_options_limit_as_well_as_the_question_limit():
    """A request's output grows with its answer options: 60 questions of 55
    long options (3,300) hit Jev's output limit on 2026-09-30. Batches close
    at whichever of the two limits they reach first; one oversized question
    still goes, alone."""
    wide = {"type": "choice", "instructions": "?", "criteria": {f"o{j}": "x" for j in range(100)}}
    per = decisions.MAX_OPTIONS_PER_REQUEST // 100
    batches = decisions._batches([(f"q{i}", wide) for i in range(per * 2 + 1)])
    assert [len(b) for b in batches] == [per, per, 1]
    narrow = {"type": "choice", "instructions": "?", "criteria": {"yes": "Yes.", "no": "No."}}
    batches = decisions._batches([(f"q{i}", narrow) for i in range(decisions.MAX_QUESTIONS_PER_REQUEST + 1)])
    assert [len(b) for b in batches] == [decisions.MAX_QUESTIONS_PER_REQUEST, 1]
    huge = {"type": "choice", "instructions": "?", "criteria": {f"o{j}": "x" for j in range(3000)}}
    assert [len(b) for b in decisions._batches([("a", huge), ("b", narrow)])] == [1, 1]
