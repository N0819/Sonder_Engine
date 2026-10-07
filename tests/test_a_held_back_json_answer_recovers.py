"""A JSON-mode answer a provider holds back until it is whole.

Measured 2026-10-06 on NanoGPT's z-ai/glm-5.2, one prompt asking for ~5k
characters of JSON, reasoning off: with `response_format: json_object` the
first content arrived at 23.1s -- the whole answer at once, at the end; with
`response_format` removed, the same request streamed from 2.0s. The provider
does not stream JSON mode. Under the 30s first-token clock
(`PROVIDER_FIRST_TOKEN_SECONDS`) any json_object answer that takes longer than
that to write is therefore cut before it can begin, every time: the engine's
own card generator (12k-character prompt, a card's worth of JSON) went silent
four attempts running and failed after 137s, and the Writers' Room's
`prepare_package` died the same way, leaving a story's whole ground unlaid.

The schema ladder already had the remedy -- a JSON mode the provider will not
answer is retried with no `response_format`, and counted -- but it was
narrowed to `json_schema` on the reasoning that `json_object` "is a one-word
constraint no provider has to compile, so a connection death alongside it is
far likelier to be an ordinary blip". A silence BEFORE THE FIRST TOKEN on a
json_object request is not a blip; it is that provider's JSON mode.
"""

import pytest
import requests

from llm import providers


def _prov():
    return {"id": 1, "name": "test", "kind": "nanogpt", "api_key": "k",
            "base_url": "https://example.invalid/api/v1"}


def _silent(before_first_token):
    exc = providers.ProviderSilent(
        "provider silent for 31s (%s)" % (
            "before any token" if before_first_token
            else "after 200 chars of reasoning and 0 of content"), 0, True)
    exc.before_first_token = before_first_token
    return exc


@pytest.fixture(autouse=True)
def _fresh_json_mode_memory(monkeypatch):
    providers._NO_JSON_OBJECT.clear()
    providers._JSON_OBJECT_HELD_BACK.clear()
    monkeypatch.setattr(providers, "resolve_role",
                        lambda role: (_prov(), "some/model", {}))
    monkeypatch.setattr(providers, "token_sink",
                        providers.contextvars.ContextVar("t", default=lambda d: None))
    yield
    providers._NO_JSON_OBJECT.clear()
    providers._JSON_OBJECT_HELD_BACK.clear()


def _complete():
    return providers._chat_complete_once(
        "utility", "sys", "user", 0.5, True, 1000, None, json_schema=None)


def test_a_json_object_answer_held_back_is_asked_again_without_the_flag(monkeypatch):
    seen = []

    def fake_sse(url, headers, body, sink, role=None, model=None):
        seen.append(dict(body))
        if (body.get("response_format") or {}).get("type") == "json_object":
            raise _silent(before_first_token=True)
        return '{"ok": true}'

    monkeypatch.setattr(providers, "_sse_openai", fake_sse)
    assert _complete() == '{"ok": true}'
    assert len(seen) == 2, "one retry within the call, not the outer loop's four"
    assert seen[0]["response_format"] == {"type": "json_object"}
    assert "response_format" not in seen[1], "the retry streams without JSON mode"


def test_a_silence_after_the_first_token_is_still_the_outer_loops(monkeypatch):
    """A stream that began and then stopped has stopped; that is not a JSON
    mode held back, and it keeps going to the outer retry loop."""
    seen = []

    def fake_sse(url, headers, body, sink, role=None, model=None):
        seen.append(dict(body))
        raise _silent(before_first_token=False)

    monkeypatch.setattr(providers, "_sse_openai", fake_sse)
    with pytest.raises(providers.ProviderSilent):
        _complete()
    assert len(seen) == 1


def test_a_dropped_connection_on_json_object_is_still_a_blip(monkeypatch):
    seen = []

    def fake_sse(url, headers, body, sink, role=None, model=None):
        seen.append(dict(body))
        raise requests.exceptions.ConnectionError("connection reset")

    monkeypatch.setattr(providers, "_sse_openai", fake_sse)
    with pytest.raises(requests.exceptions.ConnectionError):
        _complete()
    assert len(seen) == 1


def test_the_second_held_back_answer_drops_the_flag_for_the_pair(monkeypatch):
    """Paid twice, then not again until a restart re-asks -- the same count a
    schema gets (`_SCHEMA_STALL_LIMIT`), and the same process-local memory a
    400 on json_object writes to (`_NO_JSON_OBJECT`)."""
    def fake_sse(url, headers, body, sink, role=None, model=None):
        if (body.get("response_format") or {}).get("type") == "json_object":
            raise _silent(before_first_token=True)
        return "{}"

    monkeypatch.setattr(providers, "_sse_openai", fake_sse)
    _complete()
    assert providers._json_object_supported(_prov(), "some/model"), (
        "one held-back answer is counted, not yet believed")
    _complete()
    assert not providers._json_object_supported(_prov(), "some/model")

    later = []

    def recording(url, headers, body, sink, role=None, model=None):
        later.append(dict(body))
        return "{}"

    monkeypatch.setattr(providers, "_sse_openai", recording)
    _complete()
    assert len(later) == 1 and "response_format" not in later[0], (
        "once learned, the next call streams from its first byte")


def test_the_clock_says_whether_the_stream_had_begun():
    t = [0.0]
    clock = providers._ActivityClock(now=lambda: t[0])
    t[0] = providers.PROVIDER_FIRST_TOKEN_SECONDS + 1
    with pytest.raises(providers.ProviderSilent) as before:
        clock.tick()
    assert before.value.before_first_token is True

    t[0] = 0.0
    clock = providers._ActivityClock(now=lambda: t[0])
    clock.tick(content="{")
    t[0] = providers.PROVIDER_SILENCE_SECONDS + 1
    with pytest.raises(providers.ProviderSilent) as after:
        clock.tick()
    assert after.value.before_first_token is False
