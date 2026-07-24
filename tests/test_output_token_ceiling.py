"""Regression tests for the output-token ceiling.

Four stages (director_establish / _interpret / _resolve, narrator) requested
max_tokens=200000 — a figure no model can produce, but which providers still
act on: OpenRouter reserves credit against the requested maximum and rejects a
model outright when input + max_tokens exceeds its context window. The result
was a caller silently locked out of models and required to hold a balance
sized to an output that could never happen.

The clamp lives in providers so no single call site can reintroduce it. Pure
request-shaping — no network.
"""

from __future__ import annotations

import ast
from pathlib import Path

import providers

REPO = Path(__file__).resolve().parent.parent


def test_ceiling_caps_an_absurd_request():
    ceiling = providers.max_output_tokens()
    assert providers._clamp_max_tokens(200000) == ceiling
    assert ceiling <= 32000


def test_clamp_only_ever_lowers():
    """A utility call asking for 1000 keeps its own smaller budget."""
    ceiling = providers.max_output_tokens()
    assert providers._clamp_max_tokens(1000) == 1000
    assert providers._clamp_max_tokens(ceiling) == ceiling


def test_garbage_falls_back_to_the_ceiling():
    ceiling = providers.max_output_tokens()
    assert providers._clamp_max_tokens(None) == ceiling
    assert providers._clamp_max_tokens("nonsense") == ceiling
    assert providers._clamp_max_tokens(0) == 1
    assert providers._clamp_max_tokens(-5) == 1


def test_recommended_default():
    assert providers.MAX_OUTPUT_TOKENS_DEFAULT == 20000


def test_coercion_pulls_values_into_range():
    """This value gates every LLM call, so a bad one must degrade to a usable
    number rather than break generation."""
    coerce = providers._coerce_max_output_tokens
    assert coerce(24000) == 24000
    assert coerce("24000") == 24000
    assert coerce(999999) == providers.MAX_OUTPUT_TOKENS_MAX
    assert coerce(10) == providers.MAX_OUTPUT_TOKENS_MIN
    assert coerce(None) == providers.MAX_OUTPUT_TOKENS_DEFAULT
    assert coerce("") == providers.MAX_OUTPUT_TOKENS_DEFAULT
    assert coerce("nonsense") == providers.MAX_OUTPUT_TOKENS_DEFAULT


def test_saved_setting_wins_and_applies_without_restart(temp_db, monkeypatch):
    """Read per call, not cached at import — a change in the settings UI takes
    effect on the next turn."""
    monkeypatch.delenv("FICTION_ENGINE_MAX_OUTPUT_TOKENS", raising=False)
    import db

    assert providers.max_output_tokens() == providers.MAX_OUTPUT_TOKENS_DEFAULT

    db.set_setting("max_output_tokens", "24000")
    assert providers.max_output_tokens() == 24000
    assert providers._clamp_max_tokens(200000) == 24000

    db.set_setting("max_output_tokens", "8000")
    assert providers._clamp_max_tokens(200000) == 8000

    # An out-of-range stored value is still coerced, never trusted raw.
    db.set_setting("max_output_tokens", "999999")
    assert providers.max_output_tokens() == providers.MAX_OUTPUT_TOKENS_MAX


def test_env_override_is_the_fallback_when_unset(temp_db, monkeypatch):
    """What a headless/CI run has; the saved setting still outranks it."""
    import db

    monkeypatch.setenv("FICTION_ENGINE_MAX_OUTPUT_TOKENS", "12000")
    assert providers.max_output_tokens() == 12000

    db.set_setting("max_output_tokens", "24000")
    assert providers.max_output_tokens() == 24000


def test_no_call_site_requests_an_unreachable_budget():
    """The clamp is the floor, but a call site asking for 200k is still a bug
    worth catching at source — it misreports intent to anyone reading it."""
    offenders = []
    for path in REPO.rglob("*.py"):
        if "__pycache__" in path.parts or path.parts[-2:-1] == ("tests",):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for kw in node.keywords:
                if kw.arg != "max_tokens":
                    continue
                if isinstance(kw.value, ast.Constant) and \
                        isinstance(kw.value.value, int) and \
                        kw.value.value > 64000:
                    offenders.append(
                        f"{path.relative_to(REPO)}:{node.lineno} "
                        f"max_tokens={kw.value.value}")
    assert not offenders, "unreachable output budgets: " + "; ".join(offenders)


# ---- The settings surface ----

def test_endpoint_saves_and_bootstrap_reports_it(temp_db, monkeypatch):
    """The UI reads the ceiling from bootstrap and writes it through the
    endpoint; a round trip has to agree with what the clamp then enforces.
    Calls the route functions directly — the HTTP layer's auth is covered by
    tests/test_guest_middleware.py and isn't what's under test here."""
    monkeypatch.delenv("FICTION_ENGINE_MAX_OUTPUT_TOKENS", raising=False)
    import app as app_module

    boot = app_module.bootstrap()
    assert boot["max_output_tokens"] == providers.MAX_OUTPUT_TOKENS_DEFAULT
    assert boot["max_output_tokens_bounds"] == {
        "default": providers.MAX_OUTPUT_TOKENS_DEFAULT,
        "min": providers.MAX_OUTPUT_TOKENS_MIN,
        "max": providers.MAX_OUTPUT_TOKENS_MAX,
    }

    assert app_module.put_max_output_tokens({"value": 24000})["value"] == 24000
    assert app_module.bootstrap()["max_output_tokens"] == 24000
    assert providers._clamp_max_tokens(200000) == 24000

    # A nonsense or out-of-range value must not be able to break generation --
    # it is coerced, and the response reports what was actually stored.
    assert app_module.put_max_output_tokens({"value": "nonsense"})["value"] == \
        providers.MAX_OUTPUT_TOKENS_DEFAULT
    assert app_module.put_max_output_tokens({"value": 999999})["value"] == \
        providers.MAX_OUTPUT_TOKENS_MAX
    assert app_module.put_max_output_tokens({})["value"] == \
        providers.MAX_OUTPUT_TOKENS_DEFAULT
