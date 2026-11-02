"""A ledger entry says how much of `out` was thinking, where the provider says.

`_reasoning_tokens(usage)` was computed for `last_output_spend` and left off
the call's ledger entry, so a turn's stored record could not tell an answer
from the thinking billed with it -- and the owner prices turns from these
records (review 2026-11-01, llm_providers_quality F14). `None` is the honest
answer for a provider that does not say, and it is not zero, so the key is
written only when reported.
"""
from __future__ import annotations

from llm import providers


def test_reported_reasoning_reaches_the_ledger_and_silence_does_not():
    seen = []
    token = providers.call_ledger_sink.set(seen.append)
    try:
        providers._log_usage("narrator", "m", 0.0, {
            "prompt_tokens": 10, "completion_tokens": 500,
            "completion_tokens_details": {"reasoning_tokens": 420}})
        providers._log_usage("narrator", "m", 0.0, {
            "prompt_tokens": 10, "completion_tokens": 5})
    finally:
        providers.call_ledger_sink.reset(token)
    assert seen[0]["reasoning"] == 420
    assert "reasoning" not in seen[1], "unmeasured is not zero"
