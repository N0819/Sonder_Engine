"""Reasoning-effort setting: a global effort level applied to every role for
models that expose it, mirroring the max_output_tokens setting."""

from __future__ import annotations

import providers


def test_coercion():
    assert providers._coerce_reasoning_effort("low") == "low"
    assert providers._coerce_reasoning_effort("HIGH") == "high"
    assert providers._coerce_reasoning_effort("") == ""
    assert providers._coerce_reasoning_effort("default") == ""
    assert providers._coerce_reasoning_effort("nonsense") == ""
    assert providers._coerce_reasoning_effort(None) == ""


def test_setting_read_and_apply(temp_db):
    import db
    assert providers.reasoning_effort() == ""

    db.set_setting("reasoning_effort", "low")
    assert providers.reasoning_effort() == "low"

    # OpenAI-compatible providers get the flat field.
    body = providers._apply_reasoning_effort({}, {"kind": "nanogpt"})
    assert body["reasoning_effort"] == "low"

    # OpenRouter gets the nested reasoning block.
    body = providers._apply_reasoning_effort({}, {"kind": "openrouter"})
    assert body["reasoning"] == {"effort": "low"}


def test_unset_adds_nothing(temp_db):
    body = providers._apply_reasoning_effort({"model": "x"}, {"kind": "nanogpt"})
    assert "reasoning_effort" not in body and "reasoning" not in body


def test_bad_stored_value_degrades_to_unset(temp_db):
    import db
    db.set_setting("reasoning_effort", "turbo")
    assert providers.reasoning_effort() == ""
    assert providers._apply_reasoning_effort({}, {"kind": "nanogpt"}) == {}


def test_endpoint_round_trip(temp_db):
    import app as app_module
    assert app_module.put_reasoning_effort({"value": "low"})["value"] == "low"
    assert app_module.bootstrap()["reasoning_effort"] == "low"
    assert app_module.put_reasoning_effort({"value": "bogus"})["value"] == ""
