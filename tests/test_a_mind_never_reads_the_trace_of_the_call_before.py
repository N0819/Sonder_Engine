"""A call that brought back no trace leaves no trace standing.

`providers.last_reasoning` is the record of the LAST call's thinking on this
context, and `agents/character.py` reads it as the trace of the call the
mind just made: it goes to that mind's decision-model read-back and, with
`character_thoughts_kept`, is filed as the mind's own thought. The interaction
loop runs its minds one after another on ONE thread and one context
(`agents/loops.py`, "parallel in the FICTION, not in execution").

`_chat_complete_once` cleared three of the four "last call" records at its
start and not this one, and only `_sse_openai` ever wrote it -- the native
Anthropic stream, the blocking Anthropic read and the CLI (when it streamed no
thinking) left it alone. So mind A on an OpenAI-style thinking route, then
mind B on a native `anthropic` connection: B's "own" trace was A's private
thinking (review 2026-11-01, llm_providers_quality F1, reproduced: "A private:
I will betray B at dawn" still standing after B's call). A leak is the
engine's failure, so the record is cleared where every completion starts and
written by every transport, `None` when nothing arrived.
"""
from __future__ import annotations

import json

import pytest

from llm import providers

A_PRIVATE = "A private: I will betray B at dawn"
ANTHROPIC = {"id": 5, "name": "anthropic", "kind": "anthropic",
             "base_url": "https://api.anthropic.example", "api_key": "k"}


class _Blocking:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload
        self.text = json.dumps(payload)
        self.content = self.text.encode()

    def json(self):
        return self._payload


class _Stream:
    status_code = 200
    text = ""

    def __init__(self, events):
        self._lines = ["data: " + json.dumps(e) for e in events]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def close(self):
        pass

    def iter_lines(self):
        for line in self._lines:
            yield line.encode("utf-8")


class _Session:
    def __init__(self, blocking=None, events=None):
        self.blocking, self.events = blocking, events

    def post(self, url, **kw):
        if kw.get("stream") and self.events is not None:
            return _Stream(self.events)
        return _Blocking(self.blocking)


def _events(thinking=""):
    out = [{"type": "message_start",
            "message": {"model": "claude-x", "usage": {"input_tokens": 9}}}]
    if thinking:
        out.append({"type": "content_block_delta", "index": 0,
                    "delta": {"type": "thinking_delta", "thinking": thinking}})
    out += [{"type": "content_block_delta", "index": 1,
             "delta": {"type": "text_delta", "text": '{"say": "B speaks"}'}},
            {"type": "message_delta", "usage": {"output_tokens": 4},
             "delta": {"stop_reason": "end_turn"}}]
    return out


def _blocking(thinking=""):
    content = ([{"type": "thinking", "thinking": thinking}] if thinking else [])
    content.append({"type": "text", "text": '{"say": "B speaks"}'})
    return {"model": "claude-x", "content": content, "stop_reason": "end_turn",
            "usage": {"input_tokens": 9, "output_tokens": 4}}


def _call_b(monkeypatch, session, sink=None):
    monkeypatch.setattr(providers, "_session", lambda: session)
    token = providers.token_sink.set(sink)
    try:
        return providers._chat_complete_once(
            "character_mid", "B's sheet", "B's packet", 0.5, False, 200, None,
            resolved=(ANTHROPIC, "claude-x", {}))
    finally:
        providers.token_sink.reset(token)


class TestTheNativeAnthropicRoute:
    def test_a_blocking_answer_with_no_thinking_leaves_no_trace(self, monkeypatch):
        providers.last_reasoning.set(A_PRIVATE)
        out = _call_b(monkeypatch, _Session(blocking=_blocking()))
        assert json.loads(out) == {"say": "B speaks"}
        assert providers.last_reasoning.get() is None

    def test_a_stream_with_no_thinking_leaves_no_trace(self, monkeypatch):
        providers.last_reasoning.set(A_PRIVATE)
        seen = []
        out = _call_b(monkeypatch, _Session(events=_events()), sink=seen.append)
        assert json.loads(out) == {"say": "B speaks"}
        assert providers.last_reasoning.get() is None

    def test_the_route_s_own_thinking_is_the_trace_and_never_the_answer(
            self, monkeypatch):
        providers.last_reasoning.set(A_PRIVATE)
        seen = []
        out = _call_b(monkeypatch, _Session(events=_events("B's own reading")),
                      sink=seen.append)
        assert json.loads(out) == {"say": "B speaks"}
        assert providers.last_reasoning.get() == "B's own reading"
        assert "B's own reading" not in "".join(seen)

        providers.last_reasoning.set(A_PRIVATE)
        out = _call_b(monkeypatch, _Session(blocking=_blocking("B, blocking")))
        assert json.loads(out) == {"say": "B speaks"}
        assert providers.last_reasoning.get() == "B, blocking"


def test_a_call_that_dies_before_the_wire_leaves_no_trace(monkeypatch):
    """Cleared where the completion STARTS, beside the other three records:
    a call that never reached a provider brought back no thinking either."""
    providers.last_reasoning.set(A_PRIVATE)

    def refuse(role):
        raise RuntimeError("No model configured for role 'character_mid'")

    monkeypatch.setattr(providers, "resolve_role", refuse)
    with pytest.raises(RuntimeError):
        providers._chat_complete_once("character_mid", "s", "u", 0.5, False,
                                      200, None)
    assert providers.last_reasoning.get() is None


def test_the_cli_writes_none_when_it_streamed_no_thinking(monkeypatch):
    """`_claude_cli_complete` wrote the trace only `if reasoning:`."""
    import threading
    import time

    def line(obj):
        return (json.dumps(obj) + "\n").encode("utf-8")

    lines = [
        line({"type": "stream_event", "event": {
            "type": "message_start",
            "message": {"model": "claude-x", "usage": {"input_tokens": 3}}}}),
        line({"type": "stream_event", "event": {
            "type": "content_block_delta", "index": 0,
            "delta": {"type": "text_delta", "text": "Pineapple"}}}),
        line({"type": "result", "subtype": "success", "is_error": False,
              "result": "Pineapple", "usage": {"input_tokens": 3,
                                               "output_tokens": 2}}),
    ]

    class _Child:
        def __init__(self, argv, **kw):
            self.returncode = None
            self.stdin = self
            self.stdout = iter(lines)

        def write(self, data):
            pass

        def close(self):
            pass

        def poll(self):
            return self.returncode

        def kill(self):
            self.returncode = -9

        def wait(self, timeout=None):
            self.returncode = 0
            return 0

    monkeypatch.setattr(providers.shutil, "which", lambda name: "/bin/claude")
    monkeypatch.setattr(providers, "reasoning_effort_for", lambda role: "")
    monkeypatch.setattr(providers, "_claude_cli_popen", _Child)
    providers.last_reasoning.set(A_PRIVATE)
    out = providers._claude_cli_complete(
        {"id": 7, "name": "claude-code", "kind": "claude_cli",
         "base_url": "claude", "api_key": ""},
        "haiku", "SYSTEM", "USER", lambda piece: None, role="character_mid")
    assert out == "Pineapple"
    assert providers.last_reasoning.get() is None
