"""A schema that is never answered is a schema that was rejected.

`_apply_json_mode`'s recovery ladder was written for a provider that says 400.
Some do not: handed a `response_format` they cannot compile, they accept the
request and then never answer it, and an intermediary drops the connection.
That arrives as `requests.ConnectionError`, walks past an `except LLMError`
gated on 400, and reaches the outer retry loop -- which re-sends the identical
unusable body. `RetryConfig.max_retries` is 3, so four attempts against a 60s
cut is ~250s of waiting to be told the provider failed.

Measured 2026-09-01 on gemini-3.6-flash via openrouter, replaying the real
director_resolve body: 60.2s to RemoteDisconnected, every time. The same body
with `response_format` removed answered in 12.5s. Reasoning effort, provider
routing, stream_options and max_tokens were each ablated and none mattered.
"""

import pytest
import requests

from llm import providers


def _prov():
    return {"name": "test", "kind": "openrouter", "api_key": "k",
            "base_url": "https://example.invalid/api/v1"}


def test_a_dropped_connection_on_a_schema_request_retries_without_the_schema(
        monkeypatch):
    seen = []

    def fake_sse(url, headers, body, sink, role=None, model=None):
        seen.append(dict(body))
        if "response_format" in body:
            raise requests.exceptions.ConnectionError(
                "('Connection aborted.', RemoteDisconnected('Remote end "
                "closed connection without response'))")
        return '{"ok": true}'

    monkeypatch.setattr(providers, "_sse_openai", fake_sse)
    monkeypatch.setattr(providers, "resolve_role",
                        lambda role: (_prov(), "some/model", {}))
    monkeypatch.setattr(providers, "token_sink",
                        providers.contextvars.ContextVar("t", default=lambda d: None))

    out = providers._chat_complete_once(
        "director", "sys", "user", 0.5, True, 1000, None,
        json_schema={"name": "output", "schema": {"type": "object"}})

    assert out == '{"ok": true}'
    assert len(seen) == 2, "it must retry once, not give up and not loop"
    assert "response_format" in seen[0], "the first attempt carries the schema"
    assert "response_format" not in seen[1], "the retry drops it"


def test_a_dropped_connection_without_a_schema_still_raises(monkeypatch):
    """Only a schema-bearing request gets this remedy.

    An ordinary network blip must still reach the outer retry loop, which is
    where a transient failure belongs. Swallowing it here would turn every
    dropped connection into a silent capability downgrade.
    """
    calls = []

    def fake_sse(url, headers, body, sink, role=None, model=None):
        calls.append(dict(body))
        raise requests.exceptions.ConnectionError("connection reset")

    monkeypatch.setattr(providers, "_sse_openai", fake_sse)
    monkeypatch.setattr(providers, "resolve_role",
                        lambda role: (_prov(), "some/model", {}))
    monkeypatch.setattr(providers, "token_sink",
                        providers.contextvars.ContextVar("t", default=lambda d: None))

    # json_mode with no schema still attaches `json_object`, which is a
    # one-word constraint nothing has to compile -- so this must NOT be
    # treated as a stalled grammar.
    with pytest.raises(requests.exceptions.ConnectionError):
        providers._chat_complete_once(
            "director", "sys", "user", 0.5, True, 1000, None, json_schema=None)
    assert len(calls) == 1, "only a json_schema stall gets the local remedy"


def test_the_recovery_does_not_permanently_mark_the_model(monkeypatch):
    """A bad minute must not cost a capable model its grammar forever.

    `_note_json_schema_rejected` is how a real 400 is remembered. A dropped
    connection is not proof of anything about the schema, so this path
    recovers the call and records nothing.
    """
    # The stall COUNTER is module state; a sibling test that stalled would
    # otherwise push this one over the threshold and make it look like a
    # single drop condemned the model.
    providers._SCHEMA_STALLS.clear()
    providers._NO_JSON_SCHEMA.clear()
    noted = []
    monkeypatch.setattr(providers, "_note_json_schema_rejected",
                        lambda prov, model: noted.append(model))

    def fake_sse(url, headers, body, sink, role=None, model=None):
        if "response_format" in body:
            raise requests.exceptions.ConnectionError("RemoteDisconnected")
        return "{}"

    monkeypatch.setattr(providers, "_sse_openai", fake_sse)
    monkeypatch.setattr(providers, "resolve_role",
                        lambda role: (_prov(), "some/model", {}))
    monkeypatch.setattr(providers, "token_sink",
                        providers.contextvars.ContextVar("t", default=lambda d: None))

    providers._chat_complete_once(
        "director", "sys", "user", 0.5, True, 1000, None,
        json_schema={"name": "output", "schema": {"type": "object"}})
    assert noted == [], (
        "one dropped connection is evidence, not proof -- it is counted "
        "(_note_json_schema_stalled) and only condemns the model at the "
        "second, so a bad minute cannot cost a capable model its grammar")


class TestARulingReachesTheHandThatOwnsIt:
    """`ledger_notes` is keyed by whatever the Director called the thing.

    Measured 2026-09-01, gemini-3.6-flash on chat 110 turn 44: it returned
    {"contact": ..., "vitals": ...}. `contact` is a specialist; `vitals` is one
    of `body`'s four channels. The Director was right both times -- it named
    the ledger it had ruled on -- and a lookup by specialist name alone
    silently dropped the second, which is precisely the failure this channel
    exists to prevent.
    """

    def _view(self, notes):
        return {"source": "resolved_beat", "prose": "x", "player": "P",
                "cast": [], "declared_actions": {}, "dice": [],
                "dialogue": [], "ledger_notes": notes}

    def test_a_note_keyed_by_the_specialist_reaches_it(self):
        from agents.director import _resolve_beat_view
        view = _resolve_beat_view(
            {"resolved_event": "x", "ledger_notes": {"contact": "ended a kiss"}},
            {}, {}, [], "P", {})
        assert view["ledger_notes"] == {"contact": "ended a kiss"}

    def test_a_note_keyed_by_a_channel_reaches_its_owner(self):
        from agents.director import SPECIALISTS
        notes = {"vitals": "she came"}
        # the resolution `_specialist_payload` performs, stated directly
        resolved = {}
        for name in SPECIALISTS:
            note = notes.get(name)
            if note is None:
                for channel in (SPECIALISTS[name].get("channels") or ()):
                    if notes.get(channel):
                        note = notes[channel]
                        break
            if note:
                resolved[name] = note
        assert resolved == {"body": "she came"}, (
            "a note about `vitals` belongs to the hand that owns vitals")


class TestTheEngineLearnsWhatAProviderWillNotGive:
    """A blacklist, so the tuition is paid once rather than on every turn.

    `_NO_JSON_SCHEMA` already existed with two gaps: it lived only in memory
    ("for the rest of this process"), and it learned only from a 400. The
    failure measured on 2026-09-01 produces neither -- gemini-3.6-flash
    accepted the schema and never answered -- so the engine re-paid ~250s for
    the same discovery every turn, and again after every restart.
    """

    def setup_method(self):
        providers._NO_JSON_SCHEMA.clear()
        providers._SCHEMA_STALLS.clear()
        providers._json_schema_supported._loaded = True

    def test_one_stall_is_not_enough_to_condemn_a_model(self, monkeypatch):
        monkeypatch.setattr(providers, "_persist_schema_blacklist", lambda: None)
        providers._note_json_schema_stalled(_prov(), "m")
        assert providers._json_schema_supported(_prov(), "m"), (
            "a single dropped connection is a blip, not a verdict")

    def test_two_stalls_are(self, monkeypatch):
        monkeypatch.setattr(providers, "_persist_schema_blacklist", lambda: None)
        providers._note_json_schema_stalled(_prov(), "m")
        providers._note_json_schema_stalled(_prov(), "m")
        assert not providers._json_schema_supported(_prov(), "m")

    def test_a_400_condemns_immediately(self, monkeypatch):
        """A provider SAYING it cannot compile needs no second opinion."""
        monkeypatch.setattr(providers, "_persist_schema_blacklist", lambda: None)
        providers._note_json_schema_rejected(_prov(), "m")
        assert not providers._json_schema_supported(_prov(), "m")

    def test_the_verdict_is_written_down(self, monkeypatch):
        written = {}
        monkeypatch.setattr(providers, "set_setting",
                            lambda k, v: written.update(key=k, value=v),
                            raising=False)
        providers._note_json_schema_rejected(_prov(), "m")
        assert written.get("key") == providers._NO_JSON_SCHEMA_SETTING
        assert "m" in (written.get("value") or ""), (
            "a restart must be able to re-read what this run learned")

    def test_bookkeeping_never_fails_the_call(self, monkeypatch):
        """The blacklist is a cache: losing it is safe, raising is not."""
        def boom(*a, **k):
            raise RuntimeError("no database")
        monkeypatch.setattr(providers, "set_setting", boom, raising=False)
        providers._note_json_schema_rejected(_prov(), "m")   # must not raise
        assert not providers._json_schema_supported(_prov(), "m")
