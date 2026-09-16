"""The `claude_cli` provider kind: `claude -p` as a completion backend.

Every shape a scripted child emits below is a trimmed copy of what Claude
Code 2.1.273 printed on 2026-09-15 under `--output-format stream-json
--include-partial-messages`: a `stream_event` line per raw Anthropic SSE
event, and one `result` line at the end. The bad-model result and the
structured-output stream (a `StructuredOutput` tool call whose input arrives
as `input_json_delta`) are likewise copied from live runs, not guessed.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time

import pytest

from llm import providers
from llm.providers import (
    Aborted, LLMError, ProviderSilent, cancel_event, call_ledger_sink,
    chat_complete, chat_complete_async, list_models, token_sink,
)


PROV = {"id": 7, "name": "claude-code", "kind": "claude_cli",
        "base_url": "claude", "api_key": ""}


def _line(obj):
    return (json.dumps(obj) + "\n").encode("utf-8")


def _event(ev):
    return _line({"type": "stream_event", "event": ev, "session_id": "s"})


def _usage(**over):
    base = {"input_tokens": 743, "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0, "output_tokens": 7}
    base.update(over)
    return base


def _text_stream(pieces=("Pine", "apple"), model="claude-haiku-4-5-20251001"):
    lines = [
        _line({"type": "system", "subtype": "init", "model": model}),
        _event({"type": "message_start",
                "message": {"model": model, "usage": _usage()}}),
        _event({"type": "content_block_start", "index": 0,
                "content_block": {"type": "thinking", "thinking": ""}}),
        _event({"type": "content_block_delta", "index": 0,
                "delta": {"type": "thinking_delta", "thinking": "private"}}),
        _event({"type": "content_block_stop", "index": 0}),
    ]
    for piece in pieces:
        lines.append(_event({"type": "content_block_delta", "index": 1,
                             "delta": {"type": "text_delta", "text": piece}}))
    lines += [
        _event({"type": "message_delta",
                "delta": {"stop_reason": "end_turn"},
                "usage": _usage(output_tokens=97, cache_read_input_tokens=500)}),
        _event({"type": "message_stop"}),
        _line({"type": "result", "subtype": "success", "is_error": False,
               "stop_reason": "end_turn", "result": "".join(pieces),
               "usage": _usage(output_tokens=97, cache_read_input_tokens=500),
               "total_cost_usd": 0.002,
               "modelUsage": {model: {"inputTokens": 743}}}),
    ]
    return lines


class _FakePopen:
    """A scripted child. `lines` are emitted in order; a callable entry is
    run in the pump thread instead (to stall, or to block until killed)."""

    spawned = []

    def __init__(self, argv, cwd=None, stdin=None, stdout=None, stderr=None,
                 lines=(), returncode=0):
        self.argv = list(argv)
        self.cwd = cwd
        self.returncode = None
        self._rc = returncode
        self.killed = threading.Event()
        self.stdin = self
        self.written = b""
        self.stdout = self._iter(list(lines))
        _FakePopen.spawned.append(self)

    # -- stdin
    def write(self, data):
        self.written += data

    def close(self):
        pass

    # -- stdout
    def _iter(self, lines):
        for item in lines:
            if callable(item):
                item(self)
                continue
            if self.killed.is_set():
                break
            yield item
        self.returncode = self._rc

    # -- process
    def poll(self):
        return self.returncode

    def kill(self):
        self.killed.set()
        self.returncode = -9

    def wait(self, timeout=None):
        deadline = time.monotonic() + (timeout or 5)
        while self.returncode is None and time.monotonic() < deadline:
            time.sleep(0.005)
        if self.returncode is None:
            self.returncode = self._rc
        return self.returncode


@pytest.fixture
def scripted(monkeypatch):
    """Install a scripted child and a found binary; returns the installer."""
    _FakePopen.spawned.clear()
    monkeypatch.setattr(providers.shutil, "which",
                        lambda name: "/usr/local/bin/claude"
                        if name in ("claude", "/opt/claude") else None)
    monkeypatch.setattr(providers, "reasoning_effort_for", lambda role: "")

    def install(lines, returncode=0):
        monkeypatch.setattr(
            providers, "_claude_cli_popen",
            lambda argv, **kw: _FakePopen(argv, lines=lines,
                                          returncode=returncode, **kw))
        return _FakePopen.spawned

    return install


def _complete(sink=None, **kw):
    return providers._claude_cli_complete(
        PROV, kw.pop("model", "haiku"), kw.pop("system", "SYSTEM PROMPT"),
        kw.pop("user", "USER PAYLOAD"), sink or (lambda piece: None),
        role=kw.pop("role", "narrator"), **kw)


# ---- the command line ----

def test_command_disables_tools_and_carries_system_prompt_as_an_argument(scripted):
    spawned = scripted(_text_stream())
    _complete(system="You are the NARRATOR.", user="the varying payload")
    argv = spawned[0].argv
    assert argv[0] == "/usr/local/bin/claude"
    assert argv[1] == "-p"
    assert argv[argv.index("--output-format") + 1] == "stream-json"
    assert "--include-partial-messages" in argv
    assert argv[argv.index("--tools") + 1] == ""
    assert "--no-session-persistence" in argv
    assert "--disable-slash-commands" in argv
    assert "--strict-mcp-config" in argv
    assert argv[argv.index("--model") + 1] == "haiku"
    assert argv[argv.index("--system-prompt") + 1] == "You are the NARRATOR."
    # The user payload is NOT an argument: it goes on stdin.
    assert "the varying payload" not in argv
    assert spawned[0].written == b"the varying payload"
    # Unset effort sends no flag; no schema sends none.
    assert "--effort" not in argv
    assert "--json-schema" not in argv


def test_child_runs_in_a_scratch_directory_not_the_repository(scripted, tmp_path, monkeypatch):
    monkeypatch.setattr(providers.tempfile, "gettempdir", lambda: str(tmp_path))
    spawned = scripted(_text_stream())
    _complete()
    assert spawned[0].cwd == str(tmp_path / "sonder-claude-cli")
    assert (tmp_path / "sonder-claude-cli").is_dir()


def test_effort_maps_onto_the_cli_and_off_lands_on_low(scripted, monkeypatch):
    spawned = scripted(_text_stream())
    monkeypatch.setattr(providers, "reasoning_effort_for", lambda role: "high")
    _complete()
    argv = spawned[-1].argv
    assert argv[argv.index("--effort") + 1] == "high"
    # The per-call override wins over the role, and `off` cannot be
    # expressed on the CLI: it lands on the lowest rung.
    _complete(effort_override="off")
    argv = spawned[-1].argv
    assert argv[argv.index("--effort") + 1] == "low"
    assert providers.request_shape()["reasoning_effort"] == "low"


def test_a_schema_is_sent_and_its_structured_output_is_the_answer(scripted):
    schema = {"type": "object", "properties": {"word": {"type": "string"}},
              "required": ["word"]}
    model = "claude-haiku-4-5-20251001"
    lines = [
        _event({"type": "message_start",
                "message": {"model": model, "usage": _usage()}}),
        _event({"type": "content_block_start", "index": 1,
                "content_block": {"type": "tool_use", "name": "StructuredOutput",
                                  "input": {}}}),
        _event({"type": "content_block_delta", "index": 1,
                "delta": {"type": "input_json_delta",
                          "partial_json": "{\"word\": \"pine"}}),
        _event({"type": "content_block_delta", "index": 1,
                "delta": {"type": "input_json_delta",
                          "partial_json": "apple\"}"}}),
        _event({"type": "message_delta", "delta": {"stop_reason": "tool_use"},
                "usage": _usage(output_tokens=150)}),
        _line({"type": "result", "subtype": "success", "is_error": False,
               "stop_reason": "tool_use",
               "result": "{\"word\":\"pineapple\"}",
               "structured_output": {"word": "pineapple"},
               "usage": _usage(output_tokens=150)}),
    ]
    spawned = scripted(lines)
    seen = []
    out = _complete(sink=seen.append, json_schema=schema)
    argv = spawned[0].argv
    assert json.loads(argv[argv.index("--json-schema") + 1]) == schema
    assert json.loads(out) == {"word": "pineapple"}
    # The live UI watched the object form.
    assert "".join(seen) == "{\"word\": \"pineapple\"}"
    assert providers.request_shape()["response_format"] == "json_schema"


def test_an_oversized_system_prompt_is_refused_before_spawning(scripted):
    spawned = scripted(_text_stream())
    with pytest.raises(LLMError) as err:
        _complete(system="x" * (providers.CLAUDE_CLI_ARG_LIMIT + 1))
    assert not err.value.retryable
    assert spawned == []


def test_a_missing_binary_names_the_provider_and_does_not_retry(scripted, monkeypatch):
    scripted(_text_stream())
    monkeypatch.setattr(providers.shutil, "which", lambda name: None)
    with pytest.raises(LLMError) as err:
        _complete()
    assert "claude-code" in str(err.value)
    assert "not found" in str(err.value)
    assert not err.value.retryable


def test_base_url_is_the_executable(scripted):
    spawned = scripted(_text_stream())
    prov = dict(PROV, base_url="/opt/claude")
    providers._claude_cli_complete(prov, "opus", "s", "u", lambda p: None)
    assert spawned[0].argv[0] == "/usr/local/bin/claude"


# ---- the stream ----

def test_text_deltas_reach_the_sink_and_thinking_does_not(scripted):
    scripted(_text_stream())
    seen = []
    out = _complete(sink=seen.append)
    assert out == "Pineapple"
    assert seen == ["Pine", "apple"]
    assert providers.request_shape()["finish_reason"] == "end_turn"
    assert providers.last_reasoning.get() == "private"


def test_usage_and_served_model_are_logged_from_the_stream(scripted):
    scripted(_text_stream())
    entries = []
    token = call_ledger_sink.set(entries.append)
    try:
        _complete(role="narrator")
    finally:
        call_ledger_sink.reset(token)
    assert len(entries) == 1
    entry = entries[0]
    assert entry["role"] == "narrator"
    assert entry["requested"] == "haiku"
    assert entry["served"] == "claude-haiku-4-5-20251001"
    assert entry["in"] == 743
    assert entry["out"] == 97
    assert entry["cached"] == 500
    assert entry["kind"] == "stream"


def test_a_result_that_did_not_stream_is_still_the_answer(scripted):
    # Partial messages off, or a CLI that forwards none: the `result` line
    # alone carries the reply.
    scripted([_line({"type": "result", "subtype": "success",
                     "is_error": False, "result": "Only here",
                     "usage": _usage()})])
    assert _complete() == "Only here"


def test_the_cli_error_result_is_a_typed_failure(scripted):
    scripted([
        _line({"type": "system", "subtype": "init"}),
        b"[claude-code:unrecognized_model] {\"model\":\"claude-nonexistent-9\"}\n",
        _line({"type": "result", "subtype": "success", "is_error": True,
               "api_error_status": 404, "terminal_reason": "api_error",
               "result": "There's an issue with the selected model "
                         "(claude-nonexistent-9). It may not exist."}),
    ], returncode=1)
    with pytest.raises(LLMError) as err:
        _complete(model="claude-nonexistent-9")
    assert "claude-nonexistent-9" in str(err.value)
    assert err.value.status_code == 404
    assert not err.value.retryable


def test_an_overloaded_error_result_is_retryable(scripted):
    scripted([_line({"type": "result", "is_error": True,
                     "api_error_status": 503, "result": "overloaded"})],
             returncode=1)
    with pytest.raises(LLMError) as err:
        _complete()
    assert err.value.retryable


def test_a_child_that_dies_without_a_result_reports_its_own_words(scripted):
    scripted([b"error: unknown option '--effort'\n"], returncode=1)
    with pytest.raises(LLMError) as err:
        _complete()
    assert "exited 1" in str(err.value)
    assert "unknown option" in str(err.value)
    assert err.value.retryable


def test_silence_past_the_read_deadline_kills_the_child(scripted, monkeypatch):
    monkeypatch.setattr(providers, "_request_timeout",
                        lambda streaming=True: (30, 0.05))
    released = threading.Event()

    def stall(proc):
        released.wait(2)

    spawned = scripted([_line({"type": "system", "subtype": "init"}), stall])
    try:
        with pytest.raises(ProviderSilent) as err:
            _complete()
    finally:
        released.set()
    assert "after 1 events" in str(err.value)
    assert spawned[0].killed.is_set()


def test_an_abort_kills_the_child_and_raises_aborted(scripted):
    ev = threading.Event()

    def abort_midway(proc):
        ev.set()
        providers.abort_live_requests(ev)

    def until_killed(proc):
        # A live child does not end on its own; it ends when killed. Without
        # this the scripted child could finish before the reader had even
        # registered it, and the abort would find nothing left to kill --
        # a fact about the fake, not about the reader.
        proc.killed.wait(2)

    spawned = scripted([
        _event({"type": "content_block_delta", "index": 1,
                "delta": {"type": "text_delta", "text": "Pine"}}),
        abort_midway,
        until_killed,
        _event({"type": "content_block_delta", "index": 1,
                "delta": {"type": "text_delta", "text": "apple"}}),
    ])
    token = cancel_event.set(ev)
    try:
        with pytest.raises(Aborted):
            _complete()
    finally:
        cancel_event.reset(token)
    assert spawned[0].killed.is_set()


# ---- through the role ladder ----

def _route_to_cli(monkeypatch):
    monkeypatch.setattr(providers, "resolve_role_candidates",
                        lambda role: [(PROV, "opus", {})])


def test_chat_complete_dispatches_by_kind(scripted, monkeypatch):
    spawned = scripted(_text_stream())
    _route_to_cli(monkeypatch)
    seen = []
    token = token_sink.set(seen.append)
    try:
        out = chat_complete("narrator", "You are the NARRATOR.", "payload",
                            temperature=0.2, json_mode=False)
    finally:
        token_sink.reset(token)
    assert out == "Pineapple"
    assert seen == ["Pine", "apple"]
    argv = spawned[0].argv
    assert argv[argv.index("--model") + 1] == "opus"
    # The engine's policy suffix rides the system prompt like any transport.
    assert argv[argv.index("--system-prompt") + 1].startswith(
        "You are the NARRATOR.")


def test_chat_complete_async_dispatches_by_kind(scripted, monkeypatch):
    scripted(_text_stream())
    _route_to_cli(monkeypatch)
    out = asyncio.run(chat_complete_async("narrator", "s", "u",
                                          json_mode=False))
    assert out == "Pineapple"


def test_list_models_offers_the_aliases_without_a_network(monkeypatch):
    import requests as requests_module

    def boom(self, *a, **k):
        raise AssertionError("no catalogue endpoint exists for the CLI")

    monkeypatch.setattr(requests_module.Session, "get", boom)
    rows = list_models(PROV)
    assert [r["id"] for r in rows] == list(providers.CLAUDE_CLI_MODELS)
    assert all(r["included"] for r in rows)


def test_the_preset_names_the_executable_not_a_url():
    assert providers.DEFAULT_BASES["claude_cli"] == "claude"
