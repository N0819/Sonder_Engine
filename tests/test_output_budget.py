"""max_output_tokens must be a knob that turns BOTH ways.

`_clamp_max_tokens` only ever lowers, by design -- a caller asking for a small
budget keeps it. But every state-mutating stage passed a hardcoded 16000, so
raising the configured ceiling above 16000 changed nothing: the setting could
cap spend and could not grant room.

That is not theoretical. Maze arm A11 beat 36 died on

    LLM returned invalid JSON: Unterminated string starting at position 8380

with response_tokens=16000 -- exactly the hardcoded value. A reasoning model's
thinking is billed as output, and trinity spent 11-13k tokens deliberating
before emitting any JSON, so the answer was truncated mid-string. The engine's
own comment invites raising the ceiling "for a model with a genuinely larger
usable output window AND a reason to fill it". The invitation did not work.

Database-independent: the env override is the headless path, so no settings
row is needed.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import providers


@pytest.fixture
def ceiling(monkeypatch):
    """Set the ceiling via the env override and clear any cached setting."""
    def _set(value):
        monkeypatch.setenv("FICTION_ENGINE_MAX_OUTPUT_TOKENS", str(value))
        monkeypatch.setattr(providers, "get_setting", lambda *a, **k: None)
    return _set


def test_none_means_the_configured_ceiling(ceiling):
    """The fix in one assertion. A stage that states no budget gets whatever
    the operator configured -- so configuring it is what has the effect."""
    ceiling(32000)
    assert providers._clamp_max_tokens(None) == 32000


def test_raising_the_ceiling_actually_grants_room(ceiling):
    """What the hardcoded 16000 made impossible."""
    ceiling(16000)
    low = providers._clamp_max_tokens(None)
    ceiling(40000)
    assert providers._clamp_max_tokens(None) > low


def test_it_still_only_ever_lowers_an_explicit_request(ceiling):
    """The deliberate small budgets (utility calls at 1000, the director's
    8000 sub-calls) must keep their own caps. Making None mean the ceiling
    must not turn every stage into a maximal request."""
    ceiling(32000)
    assert providers._clamp_max_tokens(1000) == 1000
    assert providers._clamp_max_tokens(8000) == 8000


def test_a_request_above_the_ceiling_is_capped(ceiling):
    """The original reason the clamp exists: OpenRouter reserves credit
    against the requested maximum and rejects a model outright when input +
    max_tokens exceeds its context window, so an unreachable ceiling silently
    locked callers out of models."""
    ceiling(20000)
    assert providers._clamp_max_tokens(200000) == 20000


def test_garbage_falls_back_to_the_ceiling_not_to_zero(ceiling):
    """A budget of 0 or a negative one would make every call fail with an
    empty completion, which presents as the model refusing rather than as a
    configuration error."""
    ceiling(20000)
    for junk in ("", "lots", None, [], {}):
        assert providers._clamp_max_tokens(junk) == 20000
    assert providers._clamp_max_tokens(0) >= 1
    assert providers._clamp_max_tokens(-5) >= 1


def test_no_stage_hardcodes_a_budget_the_ceiling_cannot_raise():
    """Pins the actual defect shut. A future stage reintroducing
    `max_tokens=16000` would silently opt out of the setting again, and the
    symptom -- a truncated JSON body on one model at one reasoning level --
    looks like a model problem, not a configuration one."""
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    offenders = []
    for path in list((root / "agents").glob("*.py")) + [root / "llm_quality.py"]:
        for n, line in enumerate(path.read_text().splitlines(), 1):
            if "max_tokens" not in line or line.lstrip().startswith("#"):
                continue
            if "16000" in line:
                offenders.append(f"{path.name}:{n}: {line.strip()}")
    assert not offenders, (
        "these opt out of max_output_tokens:\n  " + "\n  ".join(offenders))
