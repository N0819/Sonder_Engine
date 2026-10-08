"""A JSON-mode answer an upstream holds back is held back in either mode.

The format ladder sends the grammar first, the advisory `json_object` flag
when the grammar is suspended, and nothing last. Some upstreams do not stream
a JSON-mode answer at all: they hold it back until it is whole, so any answer
longer than the 30 s first-token clock to write is cut before it begins.
Every one measured did it in both modes. On the Brackwater run (2026-10-07,
OpenRouter `z-ai/glm-5.3`, `character_major`) two json_schema holds (21:52,
21:55) suspended the grammar, "sending json_object instead" -- and the next
beat's call paid two json_object holds (21:58, 21:59), 118 s in all, before
it went out with no format; the beat after took 7 s. NanoGPT's `z-ai/glm-5.2`
held json_object back the day before (the whole answer at 23.1 s, 2.0 s
without it) and stalled on json_schema too.

So a grammar's answer held back before its first token counts against the
flag as well, and a grammar suspended for holding its answers back falls back
to no format. The complement is pinned beside it: a connection death on a
grammar (gemini-3.6-flash, 2026-09-01: 60.2 s to a dropped connection while
json_object answered in 2-3 s) and a stream that began and then stopped are
not holds, and leave the flag alone.
"""

import pytest
import requests

from llm import providers


def _prov():
    return {"id": 3, "name": "openrouter", "kind": "openrouter", "api_key": "k",
            "base_url": "https://example.invalid/api/v1"}


MODEL = "z-ai/some-glm"


@pytest.fixture(autouse=True)
def _fresh_format_memory(monkeypatch):
    def clear():
        providers._NO_JSON_OBJECT.clear()
        providers._JSON_OBJECT_HELD_BACK.clear()
        providers._NO_JSON_SCHEMA.clear()
        providers._SCHEMA_STALLS.clear()
        providers._SCHEMA_SUSPENDED.clear()
    clear()
    providers._json_schema_supported._loaded = True
    monkeypatch.setattr(providers, "_persist_schema_suspensions", lambda: None)
    monkeypatch.setattr(providers, "_persist_schema_blacklist", lambda: None)
    monkeypatch.setattr(providers, "resolve_role", lambda role: (_prov(), MODEL, {}))
    monkeypatch.setattr(providers, "token_sink",
                        providers.contextvars.ContextVar("t", default=lambda d: None))
    yield
    clear()


def _silent(before_first_token):
    exc = providers.ProviderSilent("provider silent for 31s", 0, True)
    exc.before_first_token = before_first_token
    return exc


def _complete():
    return providers._chat_complete_once(
        "director", "sys", "user", 0.5, True, 1000, None,
        json_schema={"type": "object"})


def _formats_sent(monkeypatch, failure):
    """Three calls whose grammar-bearing requests fail with `failure()` and
    whose other requests answer -- the flag included, so whether it is still
    SENT is what the third call shows; returns the format each call sent
    first."""
    attempts = []

    def fake_sse(url, headers, body, sink, role=None, model=None):
        rf = (body.get("response_format") or {}).get("type")
        attempts.append(rf)
        if rf == "json_schema":
            raise failure()
        return "{}"

    monkeypatch.setattr(providers, "_sse_openai", fake_sse)
    first = []
    for _ in range(3):
        attempts.clear()
        assert _complete() == "{}"
        first.append(attempts[0])
    return first


def test_a_grammar_held_back_twice_takes_the_flag_with_it(monkeypatch):
    sent = _formats_sent(monkeypatch, lambda: _silent(before_first_token=True))
    assert sent[:2] == ["json_schema", "json_schema"]
    assert not providers._json_schema_supported(_prov(), MODEL)
    assert not providers._json_object_supported(_prov(), MODEL)
    assert sent[2] is None, (
        "a grammar suspended for holding its answers back falls back to no "
        "format, not to a flag the same upstream holds back")


def test_one_held_grammar_answer_is_counted_not_believed(monkeypatch):
    def fake_sse(url, headers, body, sink, role=None, model=None):
        if body.get("response_format"):
            raise _silent(before_first_token=True)
        return "{}"

    monkeypatch.setattr(providers, "_sse_openai", fake_sse)
    _complete()
    assert providers._json_object_supported(_prov(), MODEL)
    assert providers._JSON_OBJECT_HELD_BACK[providers._json_object_key(_prov(), MODEL)] == 1


def test_a_grammar_whose_connection_dies_keeps_the_flag(monkeypatch):
    """Not a hold: the grammar is suspended, the flag is still sent."""
    sent = _formats_sent(
        monkeypatch, lambda: requests.exceptions.ConnectionError("RemoteDisconnected"))
    assert sent[:2] == ["json_schema", "json_schema"]
    assert not providers._json_schema_supported(_prov(), MODEL)
    assert providers._json_object_supported(_prov(), MODEL)
    assert sent[2] == "json_object"


def test_a_grammar_stream_that_began_and_stopped_keeps_the_flag(monkeypatch):
    """A stream that began has not held its answer back; it stopped."""
    sent = _formats_sent(monkeypatch, lambda: _silent(before_first_token=False))
    assert not providers._json_schema_supported(_prov(), MODEL)
    assert providers._json_object_supported(_prov(), MODEL)
    assert sent[2] == "json_object"
