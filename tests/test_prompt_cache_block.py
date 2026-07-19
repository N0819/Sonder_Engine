"""Regression tests for Anthropic prompt-cache breakpoint shaping.

The per-role system prompt is the large stable prefix repeated on every call;
_anthropic_system marks it with ephemeral cache_control so Anthropic can read
it from cache instead of reprocessing it. Pure request-shaping — no network.
"""

from __future__ import annotations

import importlib

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
