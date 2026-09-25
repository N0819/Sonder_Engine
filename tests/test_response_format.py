"""A role may choose its response format, and the prose encoder's is measured.

The engine prefers an enforced grammar, then the advisory flag, then nothing
(`tests/test_json_schema_preference.py`). For the prose contract's encoder
the preference is reversed by measurement: its answer is the longest
open-ended list in the pipeline, and under the grammar GLM 5.2 closed it
early. The same captured payloads re-sent 78 times each way (chat 154 and
the time-travel test story, OpenRouter, reasoning off, 2026-09-25): with the
grammar 18 answers stopped under half of what the beat's best answer covered
and 11 left a declared act with no event; with no format, 2 and 0.

So a role can name its format -- `json_schema`, `json_object` or `none` --
and `director_specialist` defaults to `none`. The host's choice still wins,
and the panel shows the inherited one.
"""

from __future__ import annotations

import json

import pytest

from llm import providers
from tests.test_json_schema_preference import PROV, SCHEMA, _install, _ok


@pytest.fixture(autouse=True)
def _clear_memos():
    providers._NO_JSON_OBJECT.clear()
    providers._NO_JSON_SCHEMA.clear()
    yield
    providers._NO_JSON_OBJECT.clear()
    providers._NO_JSON_SCHEMA.clear()


@pytest.fixture
def _settings(temp_db):
    from core import db
    db.set_setting("reasoning_effort", json.dumps({"default": "off"}))
    return db


def _call(role):
    return providers._chat_complete_once(
        role, "sys", "usr", None, True, 1000, None,
        resolved=(PROV, "some-model", {}), json_schema=SCHEMA)


def test_the_encoder_sends_no_format_and_other_roles_keep_the_grammar(_settings, monkeypatch):
    bodies = []
    _install(monkeypatch, bodies, lambda b: _ok())
    _call("director_specialist")
    _call("narrator")
    assert "response_format" not in bodies[0]
    assert bodies[1]["response_format"]["type"] == "json_schema"


def test_the_hosts_choice_wins_and_default_reaches_every_unset_role(_settings, monkeypatch):
    _settings.set_setting("response_format", json.dumps(
        {"director_specialist": "json_schema", "default": "json_object", "narrator": "bogus"}))
    assert providers.response_format_for("director_specialist") == "json_schema"
    # A value the engine does not know is unset, and unset follows default.
    assert providers.response_format_for("narrator") == "json_object"
    bodies = []
    _install(monkeypatch, bodies, lambda b: _ok())
    _call("director_specialist")
    _call("narrator")
    assert bodies[0]["response_format"]["type"] == "json_schema"
    assert bodies[1]["response_format"] == {"type": "json_object"}


def test_unset_everywhere_is_the_engines_choice(_settings):
    assert providers.response_format_for("narrator") == ""
    assert providers.response_format_for("director_specialist") == "none"
    assert providers._role_json_mode("narrator", True, SCHEMA) == (True, SCHEMA)
    assert providers._role_json_mode("director_specialist", True, SCHEMA) == (False, None)


def test_a_calls_own_format_wins_over_the_roles(_settings):
    """The repair keeps the grammar its role's draft call goes without: its
    answers bind to jobs by id, and sent free GLM 5.2 re-encoded the whole
    beat in the draft's shape instead."""
    assert providers._role_json_mode("director_specialist", True, SCHEMA,
                                     "json_schema") == (True, SCHEMA)
    _settings.set_setting("response_format", json.dumps({"narrator": "json_schema"}))
    assert providers._role_json_mode("narrator", True, SCHEMA, "none") == (False, None)


def test_a_broken_answer_is_rebuilt_under_the_grammar(_settings, monkeypatch):
    """The request goes as its role chose; the rung that rebuilds a broken
    answer asks for a valid one (a brace dropped seven levels into a transit
    patch, twice, on one long beat)."""
    from llm import llm_quality
    calls = []

    def llm(role, system, user, **kw):
        calls.append(kw.get("response_format"))
        if len(calls) == 1:
            return '{"events": [{"event": "x", "transforms": [{"patch": {"a": {}}]}]}'
        return json.dumps({"events": [], "missing_tools": [], "missing_referents": [],
                           "notes": []})

    monkeypatch.setattr(llm_quality, "chat_complete", llm)
    monkeypatch.setattr(llm_quality, "role_candidate_count", lambda role: 1)
    llm_quality.complete_validated_json(
        role="director_specialist", step_key="director_specialist", system="s",
        payload={"prose": "p"})
    assert calls[0] is None
    assert calls[-1] == llm_quality.REBUILD_FORMAT == "json_schema"


@pytest.fixture
def client(temp_db):
    from fastapi.testclient import TestClient

    from web import app as app_module
    from web import guest_access as guest
    guest.reset_host_account()
    with TestClient(app_module.app) as c:
        r = c.post("/api/auth/setup", json={"username": "host", "password": "pw12345"})
        assert r.status_code == 200, r.text
        yield c
    guest.reset_host_account()


def test_the_panel_saves_and_shows_the_format(client):
    saved = client.put("/api/response_format",
                       json={"formats": {"narrator": "none", "character": "nonsense"}}).json()
    assert saved["response_format"] == {"narrator": "none"}
    client.put("/api/response_format", json={"role": "narrator", "value": ""})
    boot = client.get("/api/bootstrap").json()
    assert boot["response_format"] == {}
    assert boot["response_format_levels"] == ["json_schema", "json_object", "none"]
    assert boot["response_format_defaults"] == {"director_specialist": "none"}
