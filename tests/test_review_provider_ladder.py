"""One JSON-mode recovery ladder for every transport, and a typed failure
for a reasoning-only stream.

Measured 2026-09-07 (docs/experiments/REVIEW_2026-09-07.md A27/A28): the
streaming path dropped `response_format` whole on a 400 and recorded the
loss as a json_object rejection whatever the field held, so a provider
that refused grammars kept `_json_schema_supported` True and paid one dead
round trip per schema-bearing call for the life of the process; and a
stream that carried a trace and no answer returned "", so `chat_complete`'s
remedy for that case never fired for the roles the pipeline streams.
"""
from __future__ import annotations

import pytest

import llm.providers as providers
from llm.providers import LLMError, ReasoningBudgetExhausted


def _prov():
    return {"name": "test", "kind": "openrouter", "api_key": "k",
            "base_url": "https://example.invalid/api/v1"}


@pytest.fixture
def clean_json_mode_memory(monkeypatch):
    monkeypatch.setattr(providers, "_NO_JSON_SCHEMA", set())
    monkeypatch.setattr(providers, "_NO_JSON_OBJECT", set())
    monkeypatch.setattr(providers, "_SCHEMA_STALLS", {})
    monkeypatch.setattr(providers._json_schema_supported, "_loaded", True,
                        raising=False)
    # In-process only: the real note persists a setting into the shared test
    # database, which a later test's fresh load would read as this model
    # being unable to answer a schema.
    monkeypatch.setattr(providers, "_persist_schema_blacklist", lambda: None)
    monkeypatch.setattr(providers, "_load_schema_blacklist", lambda: None)
    monkeypatch.setattr(providers, "resolve_role",
                        lambda role: (_prov(), "some/model", {}))
    monkeypatch.setattr(providers, "token_sink",
                        providers.contextvars.ContextVar(
                            "t", default=lambda d: None))
    yield


def test_a_streamed_schema_rejection_climbs_to_json_object_and_records_the_schema(
        clean_json_mode_memory, monkeypatch):
    seen = []

    def fake_sse(url, headers, body, sink, role=None, model=None):
        seen.append(dict(body))
        rf = body.get("response_format") or {}
        if rf.get("type") == "json_schema":
            raise LLMError("HTTP 400: no grammars here", 400, False)
        return '{"ok": true}'

    monkeypatch.setattr(providers, "_sse_openai", fake_sse)
    out = providers._chat_complete_once(
        "director", "sys", "user", 0.5, True, 1000, None,
        json_schema={"name": "output", "schema": {"type": "object"}})

    assert out == '{"ok": true}'
    assert [b.get("response_format", {}).get("type") for b in seen] == [
        "json_schema", "json_object"], "one rung down, not straight to nothing"
    assert not providers._json_schema_supported(_prov(), "some/model")
    assert providers._json_object_supported(_prov(), "some/model"), \
        "json_object was never refused and must not be recorded as refused"


def test_a_stall_still_retries_once_with_no_response_format_and_records_nothing(
        clean_json_mode_memory, monkeypatch):
    import requests
    seen = []

    def fake_sse(url, headers, body, sink, role=None, model=None):
        seen.append(dict(body))
        if "response_format" in body:
            raise requests.exceptions.ConnectionError("RemoteDisconnected")
        return '{"ok": true}'

    monkeypatch.setattr(providers, "_sse_openai", fake_sse)
    providers._chat_complete_once(
        "director", "sys", "user", 0.5, True, 1000, None,
        json_schema={"name": "output", "schema": {"type": "object"}})
    assert len(seen) == 2 and "response_format" not in seen[1]
    assert providers._json_schema_supported(_prov(), "some/model")


def test_a_reasoning_only_stream_is_the_typed_failure_and_an_empty_one_is_empty():
    with pytest.raises(ReasoningBudgetExhausted):
        providers._stream_answer("", "thinking, thinking", "https://h/v1",
                                 "m", {"max_tokens": 4000})
    # An empty stream with no trace stays "": the caller reads the finish
    # reason the last chunk carried and says why the provider stopped.
    assert providers._stream_answer("", "", "https://h/v1", "m", {}) == ""
    assert providers._stream_answer("text", "", "https://h/v1", "m", {}) == "text"


def test_stream_reasoning_is_read_by_what_the_key_says_it_is():
    delta = {"reasoning_details": [{"text": "first"}, {"text": "second"}],
             "content": "answer"}
    assert providers._delta_reasoning(delta) == "first\nsecond"
    assert providers._delta_reasoning({"reasoning": " and"}) == " and", \
        "fragments keep their whitespace"
    assert providers._delta_reasoning({"content": "x"}) == ""
