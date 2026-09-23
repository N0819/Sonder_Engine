"""Some models (nemotron:thinking) honour response_format=json_object by
returning a valid SKELETON with every string value set to '...', which parses
and validates fine so '...' reaches the player. _is_placeholder_json detects it
so the provider can retry without json_mode (where the same model writes real
content)."""

from __future__ import annotations

from llm import providers
from llm.providers import _is_placeholder_json, token_sink


def test_all_placeholder_strings_is_a_skeleton():
    assert _is_placeholder_json('{"views":{"player":"...","1":"...","2":"..."}}')
    assert _is_placeholder_json('{"prose":"..."}')
    assert _is_placeholder_json('{"prose":"…"}')
    assert _is_placeholder_json('{"prose":"...","note":""}')  # a mark among empties


#: A townsperson's voice declining to react, exactly as gemini-3.8-flash wrote
#: it under json_object (playerless Aldermill round 6, idx 3, replayed).
VOICE_DECLINES = ('{"reacts": false, "dialogue_log_entry": null, "action": "", '
                  '"charter_act": null, "goes_to": "", "hands_over": null, '
                  '"still_owes": null}')


def test_an_empty_answer_is_not_a_skeleton():
    """Empty is an answer: the decline above was re-sent whole, without JSON
    mode, on every silent beat -- 21, 28 and 7 extra calls in rounds 5-7."""
    assert not _is_placeholder_json('{"a":"","b":"   "}')
    assert not _is_placeholder_json(VOICE_DECLINES)


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


def test_a_decline_is_taken_in_one_call(monkeypatch):
    """The streaming path, where the voices run: a decline under json_object
    is the answer, not a reason to ask again without it."""
    calls = []

    def fake_sse(url, headers, body, sink, role=None, model=None):
        calls.append(body)
        return VOICE_DECLINES

    monkeypatch.setattr(providers, "_sse_openai", fake_sse)
    resolved = (
        {"kind": "openrouter", "base_url": "http://x/v1", "api_key": "k", "name": "or"},
        "google/gemini-3.8-flash",
        {},
    )
    tok = token_sink.set(lambda _chunk: None)
    try:
        out = providers._chat_complete_once(
            "character_bg", "sys", "usr", None, True, 1000, None, resolved=resolved
        )
    finally:
        token_sink.reset(tok)

    assert out == VOICE_DECLINES
    assert len(calls) == 1
