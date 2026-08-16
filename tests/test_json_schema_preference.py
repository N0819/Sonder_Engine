"""An enforced schema beats an advisory flag, and a refusal falls back once.

`response_format: {"type": "json_object"}` is not a guarantee. The hosted APIs
honour it; a llama.cpp-family server accepts it with NO 400 and then samples
freely, so the staged retry -- which only fires on a 400 -- never learns that
anything is wrong. Measured on llama.cpp 2.28.2 against a local dense 27B, five
trials per mode, validating with the real schemas:

    narrator    none 2/5 valid   json_object 0/5   json_schema 5/5
    character   none 4/5 valid   json_object 4/5   json_schema 5/5

`json_object` was WORSE THAN SENDING NOTHING on the narrator, whose prompt
leads with prose formatting. And enforcement is faster, because a constrained
model cannot pad: `character` went 53.4s/2029 tokens to 15.3s/587.

LM Studio's own 400 names the remedy -- "must be 'json_schema' or 'text'" -- so
the preference is schema, then json_object, then nothing.
"""

from __future__ import annotations

import json

import pytest

import providers

PROV = {"id": 7, "kind": "generic", "base_url": "http://x/v1",
        "api_key": "k", "name": "lmstudio-local"}
MODEL = "qwen3.8-27b"
RESOLVED = (PROV, MODEL, {})

SCHEMA = {"type": "object", "properties": {"prose": {"type": "string"}},
          "required": ["prose"]}


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def _ok(content='{"prose": "x"}'):
    return FakeResponse(200, {
        "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 4},
    })


@pytest.fixture(autouse=True)
def _clear_memos():
    providers._NO_JSON_OBJECT.clear()
    providers._NO_JSON_SCHEMA.clear()
    yield
    providers._NO_JSON_OBJECT.clear()
    providers._NO_JSON_SCHEMA.clear()


@pytest.fixture
def _reasoning_off(temp_db):
    import db
    db.set_setting("reasoning_effort", json.dumps({"default": "off"}))
    return temp_db


def _install(monkeypatch, bodies, responder):
    class FakeSession:
        def post(self, url, headers=None, json=None, timeout=None):
            bodies.append(json)
            return responder(json)

    monkeypatch.setattr(providers, "_session", lambda: FakeSession())


def _call(json_schema=SCHEMA, json_mode=True):
    return providers._chat_complete_once(
        "narrator", "sys", "usr", None, json_mode, 1000, None,
        resolved=RESOLVED, json_schema=json_schema)


# -- the preference ---------------------------------------------------------

def test_a_schema_is_sent_in_preference_to_the_advisory_flag(_reasoning_off,
                                                             monkeypatch):
    bodies = []
    _install(monkeypatch, bodies, lambda b: _ok())
    _call()
    rf = bodies[0]["response_format"]
    assert rf["type"] == "json_schema"
    assert rf["json_schema"]["schema"] == SCHEMA


def test_without_a_schema_the_flag_is_still_sent(_reasoning_off, monkeypatch):
    """Every provider that has no schema to offer keeps exactly what it had."""
    bodies = []
    _install(monkeypatch, bodies, lambda b: _ok())
    _call(json_schema=None)
    assert bodies[0]["response_format"] == {"type": "json_object"}


def test_json_mode_off_sends_neither(_reasoning_off, monkeypatch):
    bodies = []
    _install(monkeypatch, bodies, lambda b: _ok())
    _call(json_mode=False)
    assert "response_format" not in bodies[0]


# -- the fallback ladder ----------------------------------------------------

def test_a_refused_schema_falls_back_to_json_object_not_to_nothing(
        _reasoning_off, monkeypatch):
    """A host that cannot compile a grammar usually still honours the flag.
    Dropping both at once would cost every later call its only constraint."""
    bodies = []

    def responder(body):
        rf = (body.get("response_format") or {})
        if rf.get("type") == "json_schema":
            return FakeResponse(400, {"error": "unsupported schema"})
        return _ok()

    _install(monkeypatch, bodies, responder)
    _call()
    assert len(bodies) == 2
    assert bodies[1]["response_format"] == {"type": "json_object"}


def test_reasoning_control_survives_a_schema_400(_reasoning_off, monkeypatch):
    """The whole point of staging: a 400 the reasoning controls did not cause
    must never turn a role configured 'off' back into a thinking model."""
    bodies = []

    def responder(body):
        rf = (body.get("response_format") or {})
        if rf.get("type") == "json_schema":
            return FakeResponse(400, {"error": "nope"})
        return _ok()

    _install(monkeypatch, bodies, responder)
    _call()
    assert bodies[-1].get("reasoning_effort") == "none"


def test_a_host_refusing_both_ends_with_no_response_format(_reasoning_off,
                                                           monkeypatch):
    bodies = []

    def responder(body):
        if "response_format" in body:
            return FakeResponse(400, {"error": "no structured output here"})
        return _ok()

    _install(monkeypatch, bodies, responder)
    _call()
    assert "response_format" not in bodies[-1]
    assert bodies[-1].get("reasoning_effort") == "none"


def test_a_schema_rejection_is_remembered(_reasoning_off, monkeypatch):
    """Paid once per process, not once per call."""
    bodies = []

    def responder(body):
        rf = (body.get("response_format") or {})
        if rf.get("type") == "json_schema":
            return FakeResponse(400, {"error": "nope"})
        return _ok()

    _install(monkeypatch, bodies, responder)
    _call()
    assert not providers._json_schema_supported(PROV, MODEL)
    bodies.clear()
    _call()
    assert len(bodies) == 1, "second call must not re-pay the 400"
    assert bodies[0]["response_format"] == {"type": "json_object"}


# -- the seam that supplies it ---------------------------------------------

def test_every_pipeline_step_can_offer_a_schema():
    """complete_validated_json derives this from the step's own Pydantic model,
    which is the same one it validates the reply against."""
    import llm_quality
    import schemas

    for step in ("narrator", "character", "director_interpret", "director_body"):
        assert step in schemas.SCHEMA_MAP
        schema = llm_quality._step_json_schema(step)
        assert isinstance(schema, dict) and schema, step


def test_an_unknown_step_offers_none_rather_than_raising():
    """None is a first-class answer -- the caller then sends the flag."""
    import llm_quality

    assert llm_quality._step_json_schema("not_a_real_step") is None
