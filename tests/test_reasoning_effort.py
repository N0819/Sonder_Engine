"""Per-role reasoning-effort setting (with an 'off' level), for models that
expose it. A role falls back to the 'default' role, then to unset. 'off'
disables reasoning; unset sends nothing."""

from __future__ import annotations

import json
import providers


def test_coercion_levels():
    for lvl in ("off", "minimal", "low", "medium", "high"):
        assert providers._coerce_reasoning_effort(lvl) == lvl
    assert providers._coerce_reasoning_effort("HIGH") == "high"
    assert providers._coerce_reasoning_effort("") == ""
    assert providers._coerce_reasoning_effort("default") == ""
    assert providers._coerce_reasoning_effort("turbo") == ""


def test_per_role_map_and_fallback(temp_db):
    import db
    assert providers.reasoning_efforts() == {}
    assert providers.reasoning_effort_for("director") == ""

    db.set_setting("reasoning_effort", json.dumps(
        {"default": "low", "director": "high", "junk": "nonsense"}))
    # junk value dropped
    assert providers.reasoning_efforts() == {"default": "low", "director": "high"}
    # director has its own; perception falls back to default; a role in neither
    # also falls back to default.
    assert providers.reasoning_effort_for("director") == "high"
    assert providers.reasoning_effort_for("perception") == "low"
    assert providers.reasoning_effort_for("narrator") == "low"


def test_no_default_means_unset_for_unlisted_roles(temp_db):
    import db
    db.set_setting("reasoning_effort", json.dumps({"narrator": "high"}))
    assert providers.reasoning_effort_for("narrator") == "high"
    assert providers.reasoning_effort_for("mapping") == ""   # no default entry


def test_apply_per_provider_dialect(temp_db):
    import db
    db.set_setting("reasoning_effort", json.dumps({"default": "low"}))
    assert providers._apply_reasoning_effort({}, {"kind": "nanogpt"}, "director") \
        == {"reasoning_effort": "low"}
    assert providers._apply_reasoning_effort({}, {"kind": "openrouter"}, "director") \
        == {"reasoning": {"effort": "low"}}


def test_off_disables_reasoning(temp_db):
    import db
    db.set_setting("reasoning_effort", json.dumps({"perception": "off"}))
    assert providers._apply_reasoning_effort({}, {"kind": "nanogpt"}, "perception") \
        == {"reasoning_effort": "none"}
    body = providers._apply_reasoning_effort({}, {"kind": "openrouter"}, "perception")
    assert body["reasoning"] == {"enabled": False}


def test_unset_role_adds_nothing(temp_db):
    import db
    db.set_setting("reasoning_effort", json.dumps({"director": "high"}))
    assert providers._apply_reasoning_effort({"model": "x"}, {"kind": "nanogpt"}, "mapping") \
        == {"model": "x"}


def test_legacy_global_string_becomes_default_role(temp_db):
    import db
    db.set_setting("reasoning_effort", "low")   # old single-string format
    assert providers.reasoning_efforts() == {"default": "low"}
    assert providers.reasoning_effort_for("anything") == "low"


def test_endpoint_single_role_and_full_map(temp_db):
    import app as app_module
    # single-role update
    out = app_module.put_reasoning_effort({"role": "narrator", "value": "high"})
    assert out["reasoning_effort"] == {"narrator": "high"}
    # add another, clearing narrator via ""
    app_module.put_reasoning_effort({"role": "director", "value": "off"})
    app_module.put_reasoning_effort({"role": "narrator", "value": ""})
    assert app_module.reasoning_efforts() == {"director": "off"}
    # full-map replace
    out = app_module.put_reasoning_effort({"efforts": {"default": "low", "x": "bad"}})
    assert out["reasoning_effort"] == {"default": "low"}
    assert app_module.bootstrap()["reasoning_effort"] == {"default": "low"}


def test_strip_extended_drops_reasoning_for_400_retry():
    """A provider that 400s on an unsupported reasoning_effort (nanogpt's GLM
    rejects 'none'/'low', supporting only high/max) must have it stripped on the
    retry, not kill the turn."""
    body = {"model": "glm", "reasoning_effort": "none", "top_k": 5,
            "reasoning": {"effort": "low"}, "temperature": 0.7}
    out = providers._strip_extended(body)
    assert "reasoning_effort" not in out and "reasoning" not in out
    assert out["temperature"] == 0.7  # non-optional params survive
