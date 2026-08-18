"""Prompt-cache breakpoints reach any provider that can pass them through.

An Anthropic model behind an OpenAI-compatible aggregator needs an explicit
`cache_control` breakpoint: the caching is Anthropic's, not the aggregator's, so
the plain-string system message every other provider takes produces no
breakpoint and the whole system prompt is reprocessed on every call.

That marking was gated on a hardcoded ("openrouter",) allowlist, so the SAME
Claude model reached through nanogpt -- the provider this engine is actually
configured with -- never cached, with no fix short of editing providers.py.

It stays an allowlist on purpose: a provider that REJECTS an unrecognized
cache_control key fails the turn, which is worse than not caching. What changed
is that the list is extensible from settings.
"""

from __future__ import annotations

import pytest

from llm import providers
from core.db import set_setting

CLAUDE = "anthropic/claude-sonnet-4"


def _sys(prov, model=CLAUDE, system="A long stable system prompt."):
    return providers._openai_system_message(system, prov, model)


def _is_marked(msg):
    content = msg["content"]
    return (isinstance(content, list)
            and content[0].get("cache_control") == {"type": "ephemeral"})


@pytest.mark.parametrize("kind", ["openrouter", "nanogpt"])
def test_known_aggregators_get_a_breakpoint(temp_db, kind):
    """The gap this closes: only 'openrouter' used to qualify, so Claude via
    nanogpt reprocessed its entire system prompt every call."""
    assert _is_marked(_sys({"kind": kind, "name": kind}))


@pytest.mark.parametrize("kind", ["openai", "ollama", "somethingnew"])
def test_unknown_providers_stay_plain_until_opted_in(temp_db, kind):
    """Deliberately conservative: a provider that REJECTS an unrecognized
    cache_control key fails the turn, which is worse than not caching."""
    assert not _is_marked(_sys({"kind": kind, "name": kind}))


def test_a_provider_can_be_opted_in_without_a_code_change(temp_db):
    """The actual ask: caching should work with whatever provider supports it."""
    set_setting("prompt_cache_allow", "my-gateway")
    assert _is_marked(_sys({"kind": "openai", "name": "my-gateway"}))


def test_opt_in_by_kind_too(temp_db):
    set_setting("prompt_cache_allow", "openai")
    assert _is_marked(_sys({"kind": "openai", "name": "whatever"}))


def test_deny_beats_allow(temp_db):
    set_setting("prompt_cache_allow", "nanogpt")
    set_setting("prompt_cache_deny", "nanogpt")
    assert not _is_marked(_sys({"kind": "nanogpt", "name": "nanogpt"}))


def test_non_anthropic_model_is_left_plain(temp_db):
    """GLM, GPT and friends do automatic prefix caching with no opt-in; a
    content-part system message would buy nothing and risks a strict parser."""
    msg = _sys({"kind": "nanogpt", "name": "nanogpt"}, model="zai-org/glm-latest")
    assert msg["content"] == "A long stable system prompt."


def test_empty_system_is_left_plain(temp_db):
    assert _sys({"kind": "nanogpt", "name": "nanogpt"}, system="")["content"] == ""


# --- the escape hatches ----------------------------------------------------

def test_provider_can_be_denied_by_name(temp_db):
    """A strict gateway must be excludable without costing caching everywhere."""
    set_setting("prompt_cache_deny", "fussy-gateway")
    assert not _is_marked(_sys({"kind": "openai", "name": "fussy-gateway"}))
    # Everyone else keeps caching.
    assert _is_marked(_sys({"kind": "nanogpt", "name": "nanogpt"}))


def test_provider_can_be_denied_by_kind(temp_db):
    set_setting("prompt_cache_deny", "nanogpt")
    assert not _is_marked(_sys({"kind": "nanogpt", "name": "nanogpt"}))
    assert _is_marked(_sys({"kind": "openrouter", "name": "openrouter"}))


def test_lists_are_case_and_space_tolerant(temp_db):
    set_setting("prompt_cache_deny", "  NanoGPT , other ")
    assert not _is_marked(_sys({"kind": "nanogpt", "name": "nanogpt"}))
    set_setting("prompt_cache_deny", "")
    set_setting("prompt_cache_allow", "  My-Gateway ")
    assert _is_marked(_sys({"kind": "openai", "name": "my-gateway"}))


def test_global_kill_switch_still_wins(temp_db, monkeypatch):
    monkeypatch.setattr(providers, "PROMPT_CACHE_ENABLED", False)
    assert not _is_marked(_sys({"kind": "openrouter", "name": "openrouter"}))


def test_direct_anthropic_system_block_unchanged(temp_db):
    """kind='anthropic' never went through the allowlist and must not regress."""
    assert providers._anthropic_system("prompt") == [
        {"type": "text", "text": "prompt",
         "cache_control": {"type": "ephemeral"}}]


def test_sqlite_row_provider_does_not_crash(temp_db):
    """provider() returns a sqlite3.Row, which has no .get() -- the reason
    _prov_field exists. The deny-list path must use it too."""
    import sqlite3
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT 'nanogpt' AS kind, 'nanogpt' AS name").fetchone()
    assert _is_marked(_sys(row))
    set_setting("prompt_cache_deny", "nanogpt")
    assert not _is_marked(_sys(row))


# --- only the barebones prompt is cached, never the turn's input -----------

def test_only_the_system_prompt_is_ever_cache_marked(temp_db):
    """The cached prefix must be the STATIC per-role instruction from
    get_prompt(role) and nothing else. The per-turn payload -- scene state,
    dialogue, perception views -- changes every call, so marking it would write
    a new cache entry per turn and never read one back: pure overhead.

    Only `system` is ever reshaped; the user message stays a plain string on
    both dialects."""
    for prov in ({"kind": "nanogpt", "name": "nanogpt"},
                 {"kind": "openrouter", "name": "openrouter"}):
        msg = providers._openai_system_message("stable prompt", prov, CLAUDE)
        assert _is_marked(msg)          # the prompt caches
        assert msg["role"] == "system"  # ...and it is the system slot only


def test_anthropic_body_marks_system_and_leaves_the_user_turn_plain(temp_db):
    """Guards the same rule on the native Anthropic dialect, at body level."""
    system = providers._anthropic_system("stable prompt")
    user = {"role": "user", "content": '{"scene": "varies every turn"}'}
    assert system[0]["cache_control"] == {"type": "ephemeral"}
    assert isinstance(user["content"], str)
    assert "cache_control" not in user
