"""PERCEPTION_NO_LLM: the env-gated zero-LLM perception path.

The bypass has exactly one seam -- `_per_observer_model_views` returns no
views when the flag is set, and every stage's existing deterministic
machinery (fallback views, environment backstop, injections, scrubs) does
the rest. These tests pin three things:

1. Default OFF: with the variable unset, the model fan-out runs exactly as
   before (byte-identical behaviour).
2. Flag ON: no model call is made at all -- not even the payload builder
   runs, so no per-observer prompt is ever assembled.
3. The flag is read at call time, not import time, so a benchmark or test
   can flip it without re-importing the engine.
"""

import pytest

import agents.perception as perception


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("PERCEPTION_NO_LLM", raising=False)


def test_disabled_by_default():
    assert perception.perception_llm_disabled() is False


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on", " 1 "])
def test_affirmative_values_enable(monkeypatch, value):
    monkeypatch.setenv("PERCEPTION_NO_LLM", value)
    assert perception.perception_llm_disabled() is True


@pytest.mark.parametrize("value", ["", "0", "false", "off", "no", "banana"])
def test_non_affirmative_values_stay_off(monkeypatch, value):
    monkeypatch.setenv("PERCEPTION_NO_LLM", value)
    assert perception.perception_llm_disabled() is False


def _perceiver(pid="player", name="Alice"):
    return {"id": pid, "name": name, "room": "r1", "room_name": "The Study"}


def test_flag_skips_model_and_payload_builder(monkeypatch):
    monkeypatch.setenv("PERCEPTION_NO_LLM", "1")

    def _boom(*args, **kwargs):  # pragma: no cover - the assertion
        raise AssertionError("model call attempted under PERCEPTION_NO_LLM")

    monkeypatch.setattr(perception, "_agent_json", _boom)
    views = perception._per_observer_model_views([_perceiver()], _boom)
    assert views == {}


def test_unset_flag_runs_model_path(monkeypatch):
    calls = []

    def _fake_agent_json(role, step_key, system, payload, **kwargs):
        calls.append(role)
        pid = payload["perceivers"][0]["id"]
        return {"views": {pid: "You are in the Study. Dust hangs in the light."}}

    monkeypatch.setattr(perception, "_agent_json", _fake_agent_json)
    monkeypatch.setattr(perception, "get_prompt", lambda key: "system")
    views = perception._per_observer_model_views(
        [_perceiver()], lambda p: {"scene": {}})
    assert calls == ["perception"]
    assert views == {"player": "You are in the Study. Dust hangs in the light."}


def test_flag_read_at_call_time(monkeypatch):
    """Flipping the env between calls flips the behaviour -- no import-time
    capture."""
    monkeypatch.setattr(
        perception, "_agent_json",
        lambda *a, **k: {"views": {"player": "prose"}})
    monkeypatch.setattr(perception, "get_prompt", lambda key: "system")

    monkeypatch.setenv("PERCEPTION_NO_LLM", "1")
    assert perception._per_observer_model_views(
        [_perceiver()], lambda p: {}) == {}

    monkeypatch.setenv("PERCEPTION_NO_LLM", "0")
    assert perception._per_observer_model_views(
        [_perceiver()], lambda p: {}) == {"player": "prose"}
