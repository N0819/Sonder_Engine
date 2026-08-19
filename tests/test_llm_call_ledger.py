"""Every provider call a turn pays for, durable on the step that paid it.

The defect: per-call timing lived only in stderr (`_log_usage` ->
`log_llm_call`) and died with the process, so the only durable record of a
live turn was its stage-total timestamps. Three slow-stage investigations in
one day (2026-08-11/12) each began with a wrong guess because of it: a 41s
commit was blamed on embeddings (it was a mapping call), then on corpus size
(2,152 lore entries -- the chat had 7), then on a stale server (it was not).
docs/UNBUILT.md §1.34 records the gap.

The fix is a ledger, not a log line: providers._log_usage offers every
finished call to a contextvar sink; `compute_step` points the sink at the
running PipelineContext, which stamps the step key exactly the way
StepTaggedWarnings stamps warnings; `_with_engine_notes` persists each
step's slice under `_engine_notes.llm_calls` on the saved variant, where it
rides archives, branches and traces like every other engine note --
diagnostic metadata only (roles, models, token counts, durations), never
content.
"""

from __future__ import annotations

import contextvars
import threading
import time

from llm import providers
from agents.runtime import _with_engine_notes
from agents.storage import ENGINE_NOTES_KEY
from core.pipeline_context import (
    ChatData, PipelineContext, TurnData, current_step_key,
)


def make_context(chat_id=1, turn_id=1):
    return PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                      player_input="test", created=time.time()),
        cast=[],
        input="test",
    )


class TestTheProvidersSideOfTheLedger:
    def test_log_usage_offers_the_normalized_entry_to_the_sink(self):
        """One entry per finished call, both provider dialects folded to one
        shape, `served` falling back to the requested model when the
        provider does not name one."""
        entries = []
        token = providers.call_ledger_sink.set(entries.append)
        try:
            providers._log_usage(
                "narrator", "glm-latest", time.time() - 1.5,
                {"prompt_tokens": 1200, "completion_tokens": 340,
                 "prompt_tokens_details": {"cached_tokens": 1000}},
                served="glm-4.7-served")
            providers._log_usage(
                "director_body", "small", time.time() - 0.4,
                {"input_tokens": 90, "output_tokens": 20,
                 "cache_read_input_tokens": 64},
                kind="stream")
        finally:
            providers.call_ledger_sink.reset(token)

        first, second = entries
        assert first["role"] == "narrator"
        assert first["requested"] == "glm-latest"
        assert first["served"] == "glm-4.7-served"
        assert (first["in"], first["out"], first["cached"]) == (1200, 340,
                                                                1000)
        assert 1.0 < first["duration"] < 3.0
        assert first["kind"] == "chat"
        # Anthropic dialect, streaming transport, served falls back.
        assert second["served"] == "small"
        assert (second["in"], second["out"], second["cached"]) == (90, 20,
                                                                   64)
        assert second["kind"] == "stream"

    def test_no_sink_and_a_raising_sink_are_both_harmless(self):
        """A diagnostic must never fail the call it describes: outside a
        pipeline step the sink is None, and a sink that raises is
        swallowed."""
        providers._log_usage("narrator", "m", time.time(), {})

        def bomb(entry):
            raise RuntimeError("sink exploded")

        token = providers.call_ledger_sink.set(bomb)
        try:
            providers._log_usage("narrator", "m", time.time(), {})
        finally:
            providers.call_ledger_sink.reset(token)

    def test_streaming_paths_report_the_stream_kind(self):
        """All four SSE completion paths mark their entries 'stream' -- the
        pipeline runs on the streaming path (the live UI's token sink), so
        a ledger that only covered the blocking path would miss nearly
        every call the player actually waits on."""
        import inspect

        for fn in (providers._sse_openai, providers._sse_anthropic):
            src = inspect.getsource(fn)
            assert 'kind="stream"' in src, fn.__name__


class TestTheContextSideOfTheLedger:
    def test_entries_are_stamped_with_the_running_step(self):
        ctx = make_context()
        token = current_step_key.set("director_resolve")
        try:
            ctx.note_llm_call({"role": "director", "duration": 2.0})
        finally:
            current_step_key.reset(token)
        ctx.note_llm_call({"role": "utility", "duration": 1.0})

        calls = ctx.llm_calls_for_step("director_resolve")
        assert len(calls) == 1
        assert calls[0]["role"] == "director"
        assert calls[0]["step_key"] == "director_resolve"
        assert ctx.llm_calls_for_step("narrator") == []

    def test_siblings_do_not_collect_each_others_calls(self):
        """The parallel groups and the specialist fan-out run on copied
        contexts; attribution is by contextvar, so a thread's calls land on
        its own step whatever order the threads finish in."""
        ctx = make_context()

        def run(key, role):
            current_step_key.set(key)
            ctx.note_llm_call({"role": role})

        threads = []
        for key, role in (("mapping_stage", "mapping"),
                          ("perception_act", "narrator")):
            cv = contextvars.copy_context()
            threads.append(threading.Thread(
                target=lambda cv=cv, k=key, r=role: cv.run(run, k, r)))
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert [c["role"] for c in ctx.llm_calls_for_step("mapping_stage")] \
            == ["mapping"]
        assert [c["role"]
                for c in ctx.llm_calls_for_step("perception_act")] \
            == ["narrator"]

    def test_compute_step_wires_the_sink_to_the_context(self, monkeypatch):
        """End to end through the single step funnel: a provider call made
        anywhere beneath compute_step -- here, straight from _log_usage --
        lands on the context, stamped with the step, without the producer
        knowing whose step it is under. And the funnel resets the sink on
        the way out, so a call made between steps is not misfiled."""
        from agents import runtime

        ctx = make_context()

        def fake_handler(ctx_, nonce):
            providers._log_usage(
                "narrator", "m1", time.time() - 0.2,
                {"prompt_tokens": 10, "completion_tokens": 5})
            return {"prose": "done"}

        monkeypatch.setitem(runtime.STEP_HANDLERS, "narrator", fake_handler)
        runtime.compute_step("narrator", ctx, nonce=0)

        calls = ctx.llm_calls_for_step("narrator")
        assert len(calls) == 1
        assert calls[0]["requested"] == "m1"
        assert calls[0]["in"] == 10
        assert providers.call_ledger_sink.get() is None
        providers._log_usage("narrator", "m2", time.time(), {})
        assert len(ctx.llm_calls_for_step("narrator")) == 1


class TestTheLedgerRidesTheSavedVariant:
    def test_the_steps_calls_land_under_engine_notes(self):
        ctx = make_context()
        token = current_step_key.set("director_resolve")
        try:
            ctx.note_llm_call({"role": "director", "requested": "big",
                               "served": "big", "in": 6154, "out": 900,
                               "cached": 6000, "duration": 22.4,
                               "kind": "stream"})
        finally:
            current_step_key.reset(token)

        out = _with_engine_notes({"state_diff": {}}, ctx, "director_resolve")
        ledger = out[ENGINE_NOTES_KEY]["llm_calls"]
        assert ledger == [{
            "step_key": "director_resolve", "role": "director",
            "requested": "big", "served": "big", "in": 6154, "out": 900,
            "cached": 6000, "duration": 22.4, "kind": "stream"}]
        # The content itself is untouched beside the notes.
        assert out["state_diff"] == {}

    def test_a_step_with_no_calls_grows_no_key(self):
        """The byte-identical rule: an unchanged pipeline must produce
        byte-identical content, so a step that made no provider calls (and
        raised no warnings) carries no notes at all."""
        ctx = make_context()
        content = {"views": {}}
        assert _with_engine_notes(content, ctx, "perception_act") is content

    def test_the_ledger_carries_no_content(self):
        """Engine notes ride every archive, branch and trace as opaque
        content, so the ledger must stay counts and identifiers -- assert
        the entry shape has no field that could carry prose."""
        entries = []
        token = providers.call_ledger_sink.set(entries.append)
        try:
            providers._log_usage("narrator", "m", time.time(), {
                "prompt_tokens": 1, "completion_tokens": 1})
        finally:
            providers.call_ledger_sink.reset(token)
        assert set(entries[0]) == {"role", "requested", "served", "in",
                                   "out", "cached", "duration", "kind"}


def test_a_reasoning_only_reply_is_a_retryable_failure_not_a_keyerror():
    """Live, on a specialist call: "all providers failed (last provider
    error: 'content')". A reasoning model returned a message carrying
    `reasoning` and NO `content` key, and reading it as message["content"]
    raised KeyError('content') -- whose str() is the bare word 'content'.

    A model that spent its whole budget thinking and never wrote the answer
    is an ordinary, retryable outcome. It must never surface looking like a
    parser bug, and the message must say what actually happened."""
    import pytest

    from llm import providers

    parsed = {"choices": [{"message": {
        "reasoning": "1. Analyze the request. " * 40}}]}
    with pytest.raises(providers.LLMError) as caught:
        providers._message_content(parsed, "nano", "glm-5p2")
    assert caught.value.retryable is True
    text = str(caught.value)
    assert "reasoning but no answer" in text
    assert "glm-5p2" in text


def test_an_ordinary_reply_still_comes_straight_back():
    from llm import providers

    parsed = {"choices": [{"message": {"content": '{"ok": true}'}}]}
    assert providers._message_content(parsed, "nano", "m") == '{"ok": true}'


class TestTheModelThatActuallyAnswered:
    """`_note_served_model` exists because a router alias is not a model: the
    engine can be served a materially different backing model per request,
    and every wall-clock number in the corpus is a mixture over that unrecorded
    variable. Both Anthropic SSE readers assigned `served = ""` once and never
    again, so the note could not fire on the transport the pipeline runs on --
    and the ledger recorded served == requested by fallback, which is
    indistinguishable from no substitution having happened.
    """

    class _FakeStream:
        def __init__(self, lines):
            self.status_code = 200
            self._lines = lines

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def iter_lines(self):
            for line in self._lines:
                yield line.encode("utf-8")

    def _anthropic_stream(self, monkeypatch, served_model):
        import json as _json

        lines = [
            "data: " + _json.dumps({
                "type": "message_start",
                "message": {"model": served_model,
                            "usage": {"input_tokens": 10}}}),
            "data: " + _json.dumps({
                "type": "content_block_delta",
                "delta": {"text": "hello"}}),
            "data: " + _json.dumps({
                "type": "message_delta", "usage": {"output_tokens": 3},
                "delta": {"stop_reason": "end_turn"}}),
        ]

        class _Session:
            def post(_self, *a, **k):
                return TestTheModelThatActuallyAnswered._FakeStream(lines)

        monkeypatch.setattr(providers, "_session", lambda: _Session())

    def test_the_anthropic_stream_records_the_model_that_answered(
            self, monkeypatch):
        self._anthropic_stream(monkeypatch, "claude-backing-model")
        entries = []
        token = providers.call_ledger_sink.set(entries.append)
        try:
            text = providers._sse_anthropic(
                "https://example.invalid", {}, {}, lambda _chunk: None,
                role="director", model="router-alias")
        finally:
            providers.call_ledger_sink.reset(token)

        assert text == "hello"
        assert entries and entries[0]["requested"] == "router-alias"
        assert entries[0]["served"] == "claude-backing-model", (
            "the substitution is invisible: served fell back to requested")
