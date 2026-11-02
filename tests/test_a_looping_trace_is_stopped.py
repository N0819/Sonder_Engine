"""A thinking model locked in a loop is stopped, as a looping answer is.

`OutputGuard` was fed only the CONTENT sink; reasoning deltas went to the
trace and to the activity clock, which counts them as healthy activity. So a
thinking model that locked into "Wait, let me reconsider..." was never
judged and billed reasoning to `max_tokens` -- 20,000 by default, more after
an escalation -- before usually ending as `ReasoningBudgetExhausted` and
being retried (review 2026-11-01, llm_providers_quality F12).

Measured before arming it, as the owner's rule for any guard on valid output
asks: the guard's battery run over every stored trace in the owner's
database fired on 0 of 3,036 per-call traces (`llm_capture`) and on 5 of
7,174 step traces (`variants.reasoning`) -- two distinct texts, each a
6-7k-character block said twice back to back and running to the 20,000-
character storage cap: loops, not prose.
"""
from __future__ import annotations

import json

import pytest

from llm import providers


class _Stream:
    status_code = 200
    text = ""

    def __init__(self, deltas):
        self._lines = ["data: " + json.dumps({"choices": [{"delta": d}]})
                       for d in deltas] + ["data: [DONE]"]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def close(self):
        pass

    def iter_lines(self):
        for line in self._lines:
            yield line.encode("utf-8")


def _sse(monkeypatch, deltas):
    class _Session:
        def post(self, url, **kw):
            return _Stream(deltas)

    monkeypatch.setattr(providers, "_session", lambda: _Session())
    return providers._sse_openai("http://x/v1/chat/completions", {},
                                 {"model": "m", "messages": []},
                                 lambda _piece: None)


def test_a_trace_repeating_one_thought_is_degenerate(monkeypatch):
    loop = [{"reasoning": "Wait, let me reconsider the north door. "}] * 2000
    with pytest.raises(providers.DegenerateOutput):
        _sse(monkeypatch, loop + [{"content": '{"ok": true}'}])


def test_an_ordinary_trace_is_left_alone(monkeypatch):
    thinking = [{"reasoning": f"Step {i}: the lamp at {i * 7 % 13} paces, "
                              f"the door {'open' if i % 3 else 'shut'}. "}
                for i in range(600)]
    out = _sse(monkeypatch, thinking + [{"content": '{"ok": true}'}])
    assert json.loads(out) == {"ok": True}


def test_the_trace_is_judged_apart_from_the_answer(monkeypatch):
    """Two guards, not one: a trace and an answer that each repeat a little
    are not one stream repeating a lot."""
    half = [{"reasoning": "ha "}] * 60 + [{"content": "ha "}] * 60
    out = _sse(monkeypatch, half + [{"content": "done"}])
    assert out.endswith("done")
