"""Regression tests for Anthropic prompt-cache breakpoint shaping.

The per-role system prompt is the large stable prefix repeated on every call;
_anthropic_system marks it with ephemeral cache_control so Anthropic can read
it from cache instead of reprocessing it. Pure request-shaping — no network.
"""

from __future__ import annotations

import importlib
import json

import providers


def test_system_prompt_marked_cacheable_when_enabled():
    providers.PROMPT_CACHE_ENABLED = True
    block = providers._anthropic_system("You are the DIRECTOR. Long stable prompt.")
    assert isinstance(block, list) and len(block) == 1
    assert block[0]["type"] == "text"
    assert block[0]["text"].startswith("You are the DIRECTOR")
    assert block[0]["cache_control"] == {"type": "ephemeral"}


def test_empty_system_is_passthrough():
    providers.PROMPT_CACHE_ENABLED = True
    # Nothing to cache -> don't emit an empty cache block.
    assert providers._anthropic_system("") == ""
    assert providers._anthropic_system(None) is None


def test_kill_switch_disables_marking():
    original = providers.PROMPT_CACHE_ENABLED
    try:
        providers.PROMPT_CACHE_ENABLED = False
        assert providers._anthropic_system("stable prompt") == "stable prompt"
    finally:
        providers.PROMPT_CACHE_ENABLED = original


# ---- Anthropic models reached through an OpenAI-compatible aggregator ----
#
# The caching is Anthropic's, not the aggregator's: routing Claude through
# OpenRouter took the OpenAI-compatible branch, which sent a plain-string
# system message, so no breakpoint was ever set and nothing cached. Reported
# from live use ("with claude, I didn't see it even try to use caching").

OPENROUTER = {"kind": "openrouter"}
DIRECT_OPENAI = {"kind": "openai"}


def _system_content(system, prov, model):
    return providers._openai_system_message(system, prov, model)["content"]


def test_claude_via_openrouter_gets_a_cache_breakpoint():
    providers.PROMPT_CACHE_ENABLED = True
    content = _system_content(
        "You are the NARRATOR. Long stable prompt.",
        OPENROUTER, "anthropic/claude-opus-4-8")
    assert isinstance(content, list) and len(content) == 1
    assert content[0]["type"] == "text"
    assert content[0]["cache_control"] == {"type": "ephemeral"}


def test_non_anthropic_model_keeps_the_plain_string():
    """Every other provider expects a plain string; only Anthropic reads a
    cache_control breakpoint, so don't reshape requests that can't use one."""
    providers.PROMPT_CACHE_ENABLED = True
    assert _system_content("stable prompt", OPENROUTER,
                           "deepseek/deepseek-v4-flash") == "stable prompt"
    assert _system_content("stable prompt", DIRECT_OPENAI,
                           "anthropic/claude-opus-4-8") == "stable prompt"


def test_openai_compatible_empty_and_kill_switch():
    original = providers.PROMPT_CACHE_ENABLED
    try:
        providers.PROMPT_CACHE_ENABLED = True
        assert _system_content("", OPENROUTER, "anthropic/claude-opus-4-8") == ""
        providers.PROMPT_CACHE_ENABLED = False
        assert _system_content("stable prompt", OPENROUTER,
                               "anthropic/claude-opus-4-8") == "stable prompt"
    finally:
        providers.PROMPT_CACHE_ENABLED = original


def test_model_family_detection():
    assert providers._model_is_anthropic("anthropic/claude-opus-4-8")
    assert providers._model_is_anthropic("claude-sonnet-5")
    assert not providers._model_is_anthropic("deepseek/deepseek-v4-flash")
    assert not providers._model_is_anthropic("")
    assert not providers._model_is_anthropic(None)


# ---- End to end: does the breakpoint actually reach the wire? ----
#
# The unit tests above check the shaping helpers in isolation. These drive
# chat_complete itself and inspect the request body that would be sent, which
# is the only thing that proves a real call carries the breakpoint.

class _FakeResponse:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload
        self.text = ""

    def json(self):
        return self._payload


class _FakeSession:
    """Captures the outgoing request body instead of sending it."""

    def __init__(self, payload):
        self.payload = payload
        self.bodies = []

    def post(self, url, headers=None, json=None, timeout=None, **kw):
        self.bodies.append(json)
        return _FakeResponse(self.payload)


def _capture(monkeypatch, prov, model, payload):
    session = _FakeSession(payload)
    monkeypatch.setattr(providers, "_session", lambda: session)
    monkeypatch.setattr(providers, "resolve_role_candidates",
                        lambda role: [(prov, model, {})])
    monkeypatch.setattr(providers, "max_output_tokens", lambda: 20000)
    monkeypatch.setattr(providers, "_log_usage",
                        lambda *a, **kw: None)
    providers.chat_complete("narrator", "You are the NARRATOR. Stable prefix.",
                            "the varying user payload")
    assert len(session.bodies) == 1
    return session.bodies[0]


ANTHROPIC_PROV = {"kind": "anthropic", "name": "anthropic",
                  "api_key": "k", "base_url": "https://api.anthropic.com"}
OPENROUTER_PROV = {"kind": "openrouter", "name": "openrouter",
                   "api_key": "k", "base_url": "https://openrouter.ai/api/v1"}
ANTHROPIC_REPLY = {"content": [{"text": "ok"}], "usage": {}}
OPENAI_REPLY = {"choices": [{"message": {"content": "ok"}}], "usage": {}}


def test_direct_anthropic_request_carries_the_breakpoint(monkeypatch):
    providers.PROMPT_CACHE_ENABLED = True
    body = _capture(monkeypatch, ANTHROPIC_PROV, "claude-opus-4-8",
                    ANTHROPIC_REPLY)
    assert body["system"][0]["cache_control"] == {"type": "ephemeral"}
    # The varying half must stay OUTSIDE the cached prefix, or the prefix
    # changes every call and nothing is ever read back.
    assert "cache_control" not in json.dumps(body["messages"])


def test_claude_via_openrouter_request_carries_the_breakpoint(monkeypatch):
    providers.PROMPT_CACHE_ENABLED = True
    body = _capture(monkeypatch, OPENROUTER_PROV, "anthropic/claude-opus-4-8",
                    OPENAI_REPLY)
    system = body["messages"][0]
    assert system["role"] == "system"
    assert system["content"][0]["cache_control"] == {"type": "ephemeral"}
    assert system["content"][0]["text"].startswith("You are the NARRATOR")
    user = body["messages"][1]
    assert user["content"] == "the varying user payload"
    assert "cache_control" not in json.dumps(user)


def test_non_anthropic_request_is_shaped_normally(monkeypatch):
    providers.PROMPT_CACHE_ENABLED = True
    body = _capture(monkeypatch, OPENROUTER_PROV, "deepseek/deepseek-v4-flash",
                    OPENAI_REPLY)
    assert body["messages"][0] == {
        "role": "system", "content": "You are the NARRATOR. Stable prefix."}


def test_the_cached_prefix_is_byte_stable_across_calls(monkeypatch):
    """A prefix that differs between calls is written every time and read
    never — the failure mode that looks like caching is on but costs more."""
    providers.PROMPT_CACHE_ENABLED = True
    first = _capture(monkeypatch, OPENROUTER_PROV, "anthropic/claude-opus-4-8",
                     OPENAI_REPLY)
    second = _capture(monkeypatch, OPENROUTER_PROV, "anthropic/claude-opus-4-8",
                      OPENAI_REPLY)
    assert first["messages"][0] == second["messages"][0]
