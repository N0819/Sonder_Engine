"""Native tool rounds in the provider layer (2026-10-05).

A character may look things up mid-thought (`agents/character_tools.py`): the
model reasons, stops with `finish_reason: tool_calls`, is handed the results,
and goes on. Probed on the owner's character route (NanoGPT glm-5.3:thinking):
the call arrives streamed as ONE delta carrying its index, id, name and whole
arguments, after the reasoning deltas. Other hosts stream the arguments in
chunks. Before this, the stream reader read only reasoning and content, and a
round that called a tool -- reasoning, no content -- was the reasoning-only
failure: reasoning turned off, then the next model.
"""

from __future__ import annotations

import json

import pytest

from llm import providers

PROV = {"id": 1, "kind": "nanogpt", "base_url": "http://x/v1", "api_key": "k",
        "name": "nanogpt"}
MODEL = "z-ai/glm-5.3:thinking"
RESOLVED = (PROV, MODEL, {})
TOOLS = [{"type": "function", "function": {
    "name": "ponder", "description": "Search your own memory.",
    "parameters": {"type": "object", "properties": {"query": {"type": "string"}},
                   "required": ["query"]}}}]


class Chunks:
    """A streamed response of exactly these SSE chunks."""

    def __init__(self, chunks, status=200):
        self.chunks = chunks
        self.status_code = status
        self.text = json.dumps(chunks)[:300]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def close(self):
        pass

    def iter_lines(self):
        for chunk in self.chunks:
            yield ("data: " + json.dumps(chunk)).encode("utf-8")
        yield b"data: [DONE]"


def _delta(**delta):
    return {"choices": [{"delta": delta}]}


def _tool_round():
    return [
        _delta(reasoning="I should look before I answer."),
        _delta(tool_calls=[{"index": 0, "id": "c1", "type": "function",
                            "function": {"name": "ponder", "arguments": '{"qu'}}]),
        _delta(tool_calls=[{"index": 0, "function": {"arguments": 'ery": "the brass key"}'}}]),
        {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]},
        {"choices": [], "usage": {"prompt_tokens": 10, "completion_tokens": 5}},
    ]


@pytest.fixture(autouse=True)
def _clear_memos(temp_db):
    providers._NO_TOOLS.clear()
    providers._NO_JSON_SCHEMA.clear()
    providers._NO_JSON_OBJECT.clear()
    yield
    providers._NO_TOOLS.clear()
    providers._NO_JSON_SCHEMA.clear()
    providers._NO_JSON_OBJECT.clear()


def _install(monkeypatch, bodies, responses):
    queue = iter(responses)

    class Session:
        def post(self, url, headers=None, json=None, timeout=None, stream=None, **kw):
            bodies.append(json)
            return next(queue)

    monkeypatch.setattr(providers, "_session", lambda: Session())


def test_a_tool_round_comes_back_as_its_calls_not_as_a_reasoning_failure(monkeypatch):
    bodies, turn = [], {}
    _install(monkeypatch, bodies, [Chunks(_tool_round())])
    history = [{"role": "assistant", "content": "", "tool_calls": []}]
    out = providers._chat_complete_once(
        "character_major", "sys", "usr", None, False, 1000, None, resolved=RESOLVED,
        history=history, tools=TOOLS, turn=turn)
    assert out == ""
    assert turn["tool_calls"] == [{"id": "c1", "name": "ponder",
                                   "arguments": '{"query": "the brass key"}'}]
    assert turn["reasoning"] == "I should look before I answer."
    assert turn["finish_reason"] == "tool_calls"
    body = bodies[0]
    assert body["tools"] == TOOLS and body["tool_choice"] == "auto"
    assert body["messages"][2:] == history
    assert "response_format" not in body


def test_a_round_that_answers_returns_its_content(monkeypatch):
    bodies, turn = [], {}
    _install(monkeypatch, bodies, [Chunks([_delta(content='{"sequence": []}')])])
    out = providers._chat_complete_once(
        "character_major", "sys", "usr", None, False, 1000, None, resolved=RESOLVED,
        tools=TOOLS, turn=turn)
    assert out == '{"sequence": []}' and turn["tool_calls"] == []


@pytest.mark.parametrize("kind", ["anthropic", "claude_cli"])
def test_no_tool_round_reaches_a_backend_that_would_drop_it(monkeypatch, kind):
    bodies = []
    _install(monkeypatch, bodies, [])
    prov = dict(PROV, kind=kind)
    with pytest.raises(providers.ToolsUnsupported):
        providers._chat_complete_once(
            "character_major", "sys", "usr", None, False, 1000, None,
            resolved=(prov, MODEL, {}), tools=TOOLS)
    assert bodies == []


def _refusal(text):
    response = Chunks([], status=400)
    response.text = text
    return response


def test_a_host_that_refuses_tools_is_remembered_and_no_grammar_is_blamed(monkeypatch):
    """A 400 on a tools body never climbs the format ladder, which would
    record json_schema as refused for this model in every role."""
    bodies = []
    _install(monkeypatch, bodies, [_refusal('{"error": {"message": "tools are not supported"}}')])
    with pytest.raises(providers.ToolsUnsupported):
        providers._chat_complete_once(
            "character_major", "sys", "usr", None, True, 1000, None, resolved=RESOLVED,
            json_schema={"type": "object"}, tools=TOOLS, tool_choice="none")
    assert (1, MODEL) in providers._NO_TOOLS
    assert not providers._NO_JSON_SCHEMA and not providers._NO_JSON_OBJECT
    assert len(bodies) == 1
    with pytest.raises(providers.ToolsUnsupported):
        providers._chat_complete_once(
            "character_major", "sys", "usr", None, False, 1000, None, resolved=RESOLVED,
            tools=TOOLS)
    assert len(bodies) == 1


def test_chat_complete_passes_a_round_on_only_when_one_is_asked_for(monkeypatch):
    seen = []

    def fake_once(role, system, user, temperature, json_mode, max_tokens, sampler, **kw):
        seen.append(kw)
        return "{}"

    monkeypatch.setattr(providers, "_chat_complete_once", fake_once)
    monkeypatch.setattr(providers, "resolve_role_candidates", lambda role: [RESOLVED])
    providers.chat_complete("character_major", "sys", "usr")
    assert not {"history", "tools", "tool_choice", "turn"} & set(seen[-1])
    providers.chat_complete("character_major", "sys", "usr", tools=TOOLS, turn={})
    assert seen[-1]["tools"] == TOOLS and seen[-1]["turn"] == {}


def test_a_refusal_is_never_retried(monkeypatch):
    calls = []

    def refuse(*a, **kw):
        calls.append(1)
        raise providers.ToolsUnsupported("no tools here")

    monkeypatch.setattr(providers, "_chat_complete_once", refuse)
    monkeypatch.setattr(providers, "resolve_role_candidates", lambda role: [RESOLVED])
    with pytest.raises(providers.ToolsUnsupported):
        providers.chat_complete("character_major", "sys", "usr", tools=TOOLS)
    assert calls == [1]


def test_tool_call_pieces_merge_by_index_or_by_id():
    calls = []
    seen = providers._merge_tool_call_deltas(calls, [
        {"id": "a", "function": {"name": "ponder", "arguments": {"query": "x"}}}])
    providers._merge_tool_call_deltas(calls, [{"id": "b", "function": {"name": "notebook"}}])
    providers._merge_tool_call_deltas(calls, [{"id": "b", "function": {"arguments": "{}"}}])
    assert calls == [{"id": "a", "name": "ponder", "arguments": '{"query": "x"}'},
                     {"id": "b", "name": "notebook", "arguments": "{}"}]
    assert seen == '{"query": "x"}'


def test_a_400_that_names_no_tools_is_this_beats_failure_not_the_routes(monkeypatch):
    """Measured cascade (review 2026-10-05): a round that only thought, the
    reasoning-off resend, and a host that takes only high or max -- the 400
    says nothing about tools, and must not switch them off for the process."""
    bodies = []
    _install(monkeypatch, bodies, [_refusal(
        '{"error": "Invalid value for reasoning_effort: none. Supported values are: high, max"}')])
    with pytest.raises(providers.LLMError) as caught:
        providers._chat_complete_once(
            "character_major", "sys", "usr", None, False, 1000, None, resolved=RESOLVED,
            tools=TOOLS)
    assert not isinstance(caught.value, providers.ToolsUnsupported)
    assert not providers._NO_TOOLS and not providers._NO_JSON_SCHEMA


def test_a_tool_round_that_only_thought_is_not_retried_with_reasoning_off(monkeypatch):
    calls = []

    def thought_only(*a, **kw):
        calls.append(kw.get("reasoning_effort_override"))
        raise providers.ReasoningBudgetExhausted("reasoning only")

    monkeypatch.setattr(providers, "_chat_complete_once", thought_only)
    monkeypatch.setattr(providers, "resolve_role_candidates", lambda role: [RESOLVED])
    with pytest.raises(providers.ReasoningBudgetExhausted):
        providers.chat_complete("character_major", "sys", "usr", tools=TOOLS,
                                retry_config=providers.RetryConfig(max_retries=3))
    assert len(calls) == 1, "the caller's single call has the remedy; a round does not"


def test_whole_calls_numbered_alike_stay_separate_calls():
    """Hosts that send each whole call as `index: 0` with its own id, and
    hosts that send neither: a call is its id, then its name."""
    calls = []
    providers._merge_tool_call_deltas(calls, [
        {"index": 0, "id": "c1", "function": {"name": "ponder", "arguments": '{"query": "the key"}'}}])
    providers._merge_tool_call_deltas(calls, [
        {"index": 0, "id": "c2", "function": {"name": "notebook", "arguments": "{}"}}])
    assert calls == [{"id": "c1", "name": "ponder", "arguments": '{"query": "the key"}'},
                     {"id": "c2", "name": "notebook", "arguments": "{}"}]
    bare = []
    providers._merge_tool_call_deltas(bare, [{"function": {"name": "ponder", "arguments": '{"qu'}}])
    providers._merge_tool_call_deltas(bare, [{"function": {"arguments": 'ery": "x"}'}}])
    providers._merge_tool_call_deltas(bare, [{"function": {"name": "notebook", "arguments": "{}"}}])
    assert [(c["name"], c["arguments"]) for c in bare] == [("ponder", '{"query": "x"}'),
                                                           ("notebook", "{}")]
