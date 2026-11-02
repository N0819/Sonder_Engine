"""A capture row names the model its call was SENT to.

`note_provider_exchange` filled `requested` from `agent_models()[role]`, so
every role that follows `default` recorded `""`, and a fallback candidate's
answer recorded the PRIMARY's model (review 2026-11-01, llm_providers_quality
F15: `[('repair', ''), ('narrator', 'narr-model')]`). The provider layer
already knows the model it put on the wire; the row now says that one.
"""
from __future__ import annotations

import pytest

from core.pipeline_context import current_exchange_sink
from llm import llm_quality, providers


@pytest.fixture
def rows(monkeypatch):
    got = []
    token = current_exchange_sink.set(got.append)
    monkeypatch.setattr(providers, "agent_models", lambda: {
        "default": {"provider": "p", "model": "default-model"},
        "narrator": {"provider": "p", "model": "narr-model",
                     "fallbacks": [{"provider": "p", "model": "backup-model"}]}})
    monkeypatch.setattr(providers, "provider", lambda name: {
        "id": 1, "name": name, "kind": "openai", "base_url": "http://x",
        "api_key": ""})
    yield got
    current_exchange_sink.reset(token)


def _note(role):
    llm_quality.note_provider_exchange(role=role, system="s", payload={},
                                       response="{}", ok=True, started=0.0)


def test_the_model_on_the_wire_is_the_one_recorded(rows):
    providers._note_request_shape({"model": "backup-model", "max_tokens": 9})
    _note("narrator")
    assert rows[-1]["requested"] == "backup-model"


def test_a_role_following_default_names_the_default(rows):
    providers.last_request_shape.set(None)    # nothing reached the wire
    _note("repair")
    assert rows[-1]["requested"] == "default-model"


def test_the_shape_keeps_its_four_keys():
    providers._note_request_shape({"model": "m", "max_tokens": 9})
    assert set(providers.request_shape()) == {
        "response_format", "reasoning_effort", "max_tokens", "finish_reason"}
    assert providers.request_model() == "m"
