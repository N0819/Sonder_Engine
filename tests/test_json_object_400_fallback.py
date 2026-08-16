"""A 400 caused by response_format must not disable reasoning control.

LM Studio hard-400s `response_format: {"type": "json_object"}` ("must be
'json_schema' or 'text'"). The 400 retry used to drop every optional field at
once, so that rejection also stripped `reasoning_effort` -- and a role
configured "off" silently went back to thinking, at 3.6-8x the latency, with
nothing reporting why.

The retry is staged instead: response_format first, the blanket strip only if
the provider is still unhappy. The rejection is then remembered so later calls
skip the field rather than paying the same 400 every turn.
"""

from __future__ import annotations

import json

import pytest

import providers
from providers import token_sink

PROV = {"id": 7, "kind": "generic", "base_url": "http://x/v1",
        "api_key": "k", "name": "lmstudio-local"}
MODEL = "qwen3.6-35b-a3b"
RESOLVED = (PROV, MODEL, {})

REJECT = {"error": "'response_format.type' must be 'json_schema' or 'text'"}


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def _ok(content='{"ok": true}'):
    return FakeResponse(200, {
        "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 4},
    })


@pytest.fixture(autouse=True)
def _clear_json_object_memo():
    """Module-level memo -- clear it so tests do not leak into each other."""
    providers._NO_JSON_OBJECT.clear()
    yield
    providers._NO_JSON_OBJECT.clear()


@pytest.fixture
def _reasoning_off(temp_db):
    import db
    db.set_setting("reasoning_effort", json.dumps({"default": "off"}))
    return temp_db


def _install_session(monkeypatch, bodies, responder):
    class FakeSession:
        def post(self, url, headers=None, json=None, timeout=None):
            bodies.append(json)
            return responder(json)

    monkeypatch.setattr(providers, "_session", lambda: FakeSession())


def _call(json_mode=True):
    return providers._chat_complete_once(
        "director", "sys", "usr", None, json_mode, 1000, None, resolved=RESOLVED)


def test_reasoning_effort_survives_a_response_format_400(_reasoning_off,
                                                         monkeypatch):
    bodies = []

    def responder(body):
        if "response_format" in body:
            return FakeResponse(400, REJECT)
        return _ok()

    _install_session(monkeypatch, bodies, responder)
    assert _call() == '{"ok": true}'

    assert len(bodies) == 2, "expected one rejected call then one staged retry"
    assert bodies[0]["response_format"] == {"type": "json_object"}
    assert bodies[0]["reasoning_effort"] == "none"

    # The whole point: the retry drops the field that was rejected and KEEPS
    # the reasoning control, which the old blanket strip discarded.
    assert "response_format" not in bodies[1]
    assert bodies[1]["reasoning_effort"] == "none"


def test_rejection_is_remembered_so_later_calls_skip_the_field(_reasoning_off,
                                                               monkeypatch):
    bodies = []

    def responder(body):
        if "response_format" in body:
            return FakeResponse(400, REJECT)
        return _ok()

    _install_session(monkeypatch, bodies, responder)
    _call()
    first_round = len(bodies)
    _call()

    # The second call must cost ONE request, not another 400 plus a retry.
    assert len(bodies) == first_round + 1
    assert "response_format" not in bodies[-1]
    assert bodies[-1]["reasoning_effort"] == "none"


def test_a_400_that_is_not_about_json_still_strips_extended(_reasoning_off,
                                                            monkeypatch):
    """Stage 2 must remain intact: a provider that rejects the effort VALUE
    (nanogpt's GLM 400s on 'none') still needs the blanket strip, or the turn
    dies. Every attempt 400s here, so we should see stage 1 and then stage 2."""
    bodies = []
    _install_session(monkeypatch, bodies,
                     lambda body: FakeResponse(400, {"error": "nope"}))

    with pytest.raises(providers.LLMError):
        _call()

    assert len(bodies) == 3, "original, stage-1, stage-2"
    assert "reasoning_effort" in bodies[1], "stage 1 keeps the reasoning control"
    assert "reasoning_effort" not in bodies[2], "stage 2 strips it, as before"
    # A model that never accepted the retry must NOT be memoised as refusing
    # json_object -- the 400 was about something else.
    assert providers._json_object_supported(PROV, MODEL)


def test_streaming_path_stages_the_same_way(_reasoning_off, monkeypatch):
    """The live UI runs on the streaming path, so it needs the same staging."""
    bodies = []

    def fake_sse(url, headers, body, sink, role=None, model=None):
        bodies.append(body)
        if "response_format" in body:
            raise providers.LLMError("400: response_format", 400, False)
        return '{"ok": true}'

    monkeypatch.setattr(providers, "_sse_openai", fake_sse)
    tok = token_sink.set(lambda _chunk: None)
    try:
        out = _call()
    finally:
        token_sink.reset(tok)

    assert out == '{"ok": true}'
    assert len(bodies) == 2
    assert "response_format" not in bodies[1]
    assert bodies[1]["reasoning_effort"] == "none"
    assert not providers._json_object_supported(PROV, MODEL)


def test_json_mode_off_sends_no_response_format(_reasoning_off, monkeypatch):
    bodies = []
    _install_session(monkeypatch, bodies, lambda body: _ok())
    _call(json_mode=False)
    assert len(bodies) == 1
    assert "response_format" not in bodies[0]
