"""Some models (nemotron:thinking) honour response_format=json_object by
returning a valid SKELETON with every string value set to '...', which parses
and validates fine so '...' reaches the player. _is_placeholder_json detects it
so the provider can retry without json_mode (where the same model writes real
content)."""

from __future__ import annotations

import providers
from providers import _is_placeholder_json, token_sink


def test_all_placeholder_strings_is_a_skeleton():
    assert _is_placeholder_json('{"views":{"player":"...","1":"...","2":"..."}}')
    assert _is_placeholder_json('{"prose":"..."}')
    assert _is_placeholder_json('{"a":"","b":"   "}')  # all empty counts too


def test_any_real_string_is_not_a_skeleton():
    assert not _is_placeholder_json('{"prose":"You step onto the pad."}')
    assert not _is_placeholder_json('{"prose":"real","x":"..."}')


def test_non_string_or_non_json_is_not_a_skeleton():
    assert not _is_placeholder_json('{"n": 5, "ok": true}')
    assert not _is_placeholder_json("not json at all")
    assert not _is_placeholder_json("")
    assert not _is_placeholder_json(None)


def test_streaming_path_retries_skeleton_without_json_mode(monkeypatch):
    """The pipeline runs on the STREAMING path (token_sink set for the live UI),
    so the skeleton guard must fire there too -- not only on the non-streaming
    path. First stream returns an all-'...' skeleton; the guard must retry once
    WITHOUT response_format and stream the real prose."""
    calls = []

    def fake_sse(url, headers, body, sink, role=None, model=None):
        calls.append(body)
        if "response_format" in body:
            return '{"prose":"..."}'          # skeleton under json_object
        return '{"prose":"You step onto the pad."}'  # real prose ungated

    monkeypatch.setattr(providers, "_sse_openai", fake_sse)
    resolved = (
        {"kind": "nanogpt", "base_url": "http://x/v1", "api_key": "k", "name": "nano"},
        "nemotron:thinking",
        {},
    )
    tok = token_sink.set(lambda _chunk: None)
    try:
        out = providers._chat_complete_once(
            "narrator", "sys", "usr", None, True, 1000, None, resolved=resolved
        )
    finally:
        token_sink.reset(tok)

    assert out == '{"prose":"You step onto the pad."}'
    assert len(calls) == 2                     # skeleton, then retry
    assert "response_format" in calls[0]
    assert "response_format" not in calls[1]
