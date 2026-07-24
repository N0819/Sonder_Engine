"""Regression tests for cache/usage telemetry.

Caching is invisible without reading `usage` back, and an unread field looks
exactly like a genuine cache miss. Two concrete gaps this pins:

- `_log_usage` read only the OpenAI-compatible dialect, so an Anthropic
  response's cache_read_input_tokens / cache_creation_input_tokens were
  reported as zero — "caching isn't working" and "we never looked" were
  indistinguishable, which is how the original report was framed.
- Both Anthropic paths (streaming and not) logged nothing at all.

Pure parsing/shaping — no network.
"""

from __future__ import annotations

import inspect

import providers


# ---- Dialect normalization ----

def test_openai_dialect():
    counts = providers._normalize_usage({
        "prompt_tokens": 5000,
        "completion_tokens": 400,
        "prompt_tokens_details": {"cached_tokens": 4096},
    })
    assert counts == {"input": 5000, "output": 400,
                      "cache_read": 4096, "cache_write": 0}


def test_anthropic_dialect():
    """The fields the old reader was blind to."""
    counts = providers._normalize_usage({
        "input_tokens": 900,
        "output_tokens": 400,
        "cache_read_input_tokens": 4096,
        "cache_creation_input_tokens": 0,
    })
    assert counts == {"input": 900, "output": 400,
                      "cache_read": 4096, "cache_write": 0}


def test_cache_write_is_reported_separately():
    """A first call writes the prefix; later calls read it. Writes with no
    reads means the prefix is changing between calls (or is under the model's
    minimum cacheable length) — which costs more than not caching."""
    counts = providers._normalize_usage({
        "input_tokens": 5000,
        "cache_creation_input_tokens": 4096,
        "cache_read_input_tokens": 0,
    })
    assert counts["cache_write"] == 4096
    assert counts["cache_read"] == 0


def test_aggregator_mixed_dialect():
    """An aggregator fronting Anthropic may pass either dialect through, so
    both are always checked."""
    counts = providers._normalize_usage({
        "prompt_tokens": 5000,
        "completion_tokens": 400,
        "cache_read_input_tokens": 4096,
    })
    assert counts["input"] == 5000
    assert counts["cache_read"] == 4096


def test_missing_or_malformed_usage_is_all_zero():
    zero = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
    assert providers._normalize_usage(None) == zero
    assert providers._normalize_usage({}) == zero
    assert providers._normalize_usage("nonsense") == zero
    assert providers._normalize_usage(
        {"prompt_tokens": None, "prompt_tokens_details": None}) == zero
    assert providers._normalize_usage({"prompt_tokens": "x"}) == zero


# ---- Anthropic streams usage across two events ----

def test_streamed_usage_merges_start_and_delta():
    """input/cache counts arrive on message_start, the final output count on
    message_delta — neither event alone is the whole picture."""
    usage = providers._merge_usage(
        None,
        {"input_tokens": 900, "cache_read_input_tokens": 4096,
         "output_tokens": 1},
    )
    usage = providers._merge_usage(usage, {"output_tokens": 412})
    counts = providers._normalize_usage(usage)
    assert counts["input"] == 900
    assert counts["cache_read"] == 4096
    assert counts["output"] == 412


def test_merge_ignores_empty_later_reports():
    usage = providers._merge_usage({"input_tokens": 900}, {"input_tokens": 0})
    assert usage["input_tokens"] == 900
    assert providers._merge_usage({"a": 1}, None) == {"a": 1}
    assert providers._merge_usage(None, None) == {}


# ---- Every response path reports ----

def test_log_usage_forwards_both_cache_directions(monkeypatch):
    seen = {}

    def fake_log(role, model, **kw):
        seen.update(kw)
        seen["role"], seen["model"] = role, model

    import logging_utils
    monkeypatch.setattr(logging_utils, "log_llm_call", fake_log)

    providers._log_usage("narrator", "claude", 0.0, {
        "input_tokens": 5000, "output_tokens": 400,
        "cache_read_input_tokens": 4096,
        "cache_creation_input_tokens": 128,
    })
    assert seen["role"] == "narrator"
    assert seen["system_tokens"] == 5000
    assert seen["response_tokens"] == 400
    assert seen["cached_tokens"] == 4096
    assert seen["cache_write_tokens"] == 128


def test_log_usage_never_raises(monkeypatch):
    """Telemetry must never be able to fail a generation."""
    import logging_utils

    def boom(*a, **kw):
        raise RuntimeError("logging backend down")

    monkeypatch.setattr(logging_utils, "log_llm_call", boom)
    providers._log_usage("narrator", "claude", 0.0, {"input_tokens": 1})


def test_every_streaming_path_can_report_usage():
    """All four stream readers take role/model so they have something to
    report against — the Anthropic pair previously did not."""
    for fn in (providers._sse_openai, providers._sse_anthropic,
               providers._sse_openai_async, providers._sse_anthropic_async):
        params = inspect.signature(fn).parameters
        assert "role" in params and "model" in params, fn.__name__


def test_streaming_requests_ask_for_usage():
    """OpenAI-compatible streams report no token counts at all unless the
    request opts in, and streaming is the path a live pipeline run uses."""
    for fn in (providers._sse_openai, providers._sse_openai_async):
        assert "include_usage" in inspect.getsource(fn), fn.__name__
