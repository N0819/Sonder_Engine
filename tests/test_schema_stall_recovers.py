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

    def test_a_ruling_survives_case_and_a_plural(self):
        """Measured: gemini keyed one note `pose`, and the channel is `poses`.

        A correct ruling about the very ledger whose staleness motivated this
        channel, dropped over one letter. Case and a trailing plural are the
        only looseness allowed -- the channels are a closed set the engine
        owns, so matching their own names loosely is schema-shaped. Guessing
        that `transit` means `positions` would be the engine inventing
        vocabulary for the Director and getting it wrong silently.
        """
        from agents.director import _note_for
        assert _note_for({"pose": "she slumps"}, "spatial") == "she slumps"
        assert _note_for({"Positions": "he moved"}, "spatial") == "he moved"
        assert _note_for({"vitals": "she came"}, "body") == "she came"
        assert _note_for({"contact": "ended"}, "contact") == "ended"
        assert _note_for({"transit": "uncoupled"}, "spatial") is None, (
            "an unknown word must reach nobody rather than the nearest guess")

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


class TestAStallVerdictHeals:
    """A stall is an INFERENCE and expires; a 400 is a FACT and does not.

    The gap this closes, measured 2026-09-09 on the owner's database:
    `_NO_JSON_SCHEMA` was only ever added to -- no discard, no expiry, no
    re-test anywhere in the module -- so two slow minutes disabled a model's
    grammar permanently. `google/gemini-3.8-flash` sat in that set while every
    Director role inherited it from `default`, so the prose author and all five
    specialists ran with no grammar and fell back to `json_object`, which
    `_apply_json_mode`'s own docstring measures as WORSE than sending nothing
    on a prose-leading prompt. A provider fixing its endpoint could never be
    noticed.

    The asymmetry is the whole design: being wrong in the healing direction
    costs one re-test per window, being wrong the other way costs every call
    the model ever makes.
    """

    def setup_method(self):
        providers._NO_JSON_SCHEMA.clear()
        providers._SCHEMA_STALLS.clear()
        providers._SCHEMA_SUSPENDED.clear()
        providers._json_schema_supported._loaded = True

    def _quiet(self, monkeypatch):
        monkeypatch.setattr(providers, "_persist_schema_blacklist", lambda: None)
        monkeypatch.setattr(providers, "_persist_schema_suspensions", lambda: None)

    def test_the_stall_verdict_lapses_and_the_grammar_is_sent_again(
            self, monkeypatch):
        self._quiet(monkeypatch)
        providers._note_json_schema_stalled(_prov(), "m")
        providers._note_json_schema_stalled(_prov(), "m")
        assert not providers._json_schema_supported(_prov(), "m")
        # ...one window later, without anything else changing.
        now = [providers.time.time() + providers._SCHEMA_SUSPEND_SECONDS + 1]
        monkeypatch.setattr(providers.time, "time", lambda: now[0])
        assert providers._json_schema_supported(_prov(), "m"), (
            "a latency symptom must not be a permanent capability verdict")

    def test_a_400_still_never_lapses(self, monkeypatch):
        """The provider described itself. Time does not change that."""
        self._quiet(monkeypatch)
        providers._note_json_schema_rejected(_prov(), "m")
        now = [providers.time.time() + providers._SCHEMA_SUSPEND_SECONDS * 100]
        monkeypatch.setattr(providers.time, "time", lambda: now[0])
        assert not providers._json_schema_supported(_prov(), "m")

    def test_a_lapsed_suspension_is_dropped_rather_than_re_decided(
            self, monkeypatch):
        self._quiet(monkeypatch)
        providers._note_json_schema_stalled(_prov(), "m")
        providers._note_json_schema_stalled(_prov(), "m")
        key = providers._json_object_key(_prov(), "m")
        assert key in providers._SCHEMA_SUSPENDED
        monkeypatch.setattr(
            providers.time, "time",
            lambda: 1e12 + providers._SCHEMA_SUSPEND_SECONDS)
        providers._json_schema_supported(_prov(), "m")
        assert key not in providers._SCHEMA_SUSPENDED

    def test_the_stall_count_resets_with_the_suspension(self, monkeypatch):
        """A model that comes back healthy is not one bad minute from its old
        verdict: crossing the line clears the tally it crossed."""
        self._quiet(monkeypatch)
        providers._note_json_schema_stalled(_prov(), "m")
        providers._note_json_schema_stalled(_prov(), "m")
        assert providers._json_object_key(_prov(), "m") not in providers._SCHEMA_STALLS

    def test_suspensions_are_written_to_their_own_row(self, monkeypatch):
        """Separate from `providers_no_json_schema` on purpose: one row is what
        a provider REFUSED, the other is what the engine INFERRED."""
        written = {}
        monkeypatch.setattr(providers, "set_setting",
                            lambda k, v: written.update({k: v}), raising=False)
        providers._note_json_schema_stalled(_prov(), "m")
        providers._note_json_schema_stalled(_prov(), "m")
        assert providers._SCHEMA_SUSPEND_SETTING in written
        assert providers._NO_JSON_SCHEMA_SETTING not in written, (
            "an inference must not be filed as a refusal")

    def test_rows_written_before_suspensions_existed_rehydrate_as_suspensions(
            self, monkeypatch):
        """The old row cannot say which verdict it recorded, and the two
        errors are not symmetrical -- so it heals."""
        providers._SCHEMA_SUSPENDED.clear()
        providers._NO_JSON_SCHEMA.clear()
        # the JSON TEXT must carry the escape, not a raw NUL: json rejects a
        # control character inside a string, and the early return there
        # would have made this test pass for the wrong reason.
        legacy = '["3\\u0000google/gemini-3.8-flash"]'
        monkeypatch.setattr(
            providers, "get_setting",
            lambda k, *a: legacy if k == providers._NO_JSON_SCHEMA_SETTING else "",
            raising=False)
        providers._load_schema_blacklist()
        assert ("3", "google/gemini-3.8-flash") in providers._SCHEMA_SUSPENDED
        assert not providers._NO_JSON_SCHEMA, (
            "a legacy row must not be promoted to a permanent refusal")

    def test_bookkeeping_never_fails_the_call(self, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError("no database")
        monkeypatch.setattr(providers, "set_setting", boom, raising=False)
        providers._note_json_schema_stalled(_prov(), "m")
        providers._note_json_schema_stalled(_prov(), "m")   # must not raise
        assert not providers._json_schema_supported(_prov(), "m")


class TestARejectionInAStreamFrameIsStillARejection:
    """A provider that rejects a request does not always get an HTTP status.

    Once the response body has begun, the rejection arrives as an
    `{"error": {...}}` frame instead, and the status sits INSIDE it. All four
    in-stream raise sites hardcoded 0 -- so the recovery ladder above, gated on
    `status_code != 400`, could never fire on the streaming path. The blocking
    path recovered and the streaming path died.

    Measured 2026-09-01 on google/gemini-3.7-flash, which rejects
    `response_format` and answers perfectly without it. Live, running the whole
    engine on it:

        RuntimeError: director_interpret: all providers failed (last provider
        error: provider stream error: Request contains an invalid argument.)

    The rule is about the transport and not the model: a rejection is the same
    event whether a status line or a frame carried it, so whether recovery is
    available must not depend on which one did. Reading the code the frame
    already states is the entire fix -- matching on the message text would work
    only until a provider reworded it.
    """

    @staticmethod
    def _frame(code):
        return {"error": {"message": "Request contains an invalid argument.",
                          "code": code}}

    def test_the_status_is_read_out_of_the_frame(self):
        assert providers._stream_error_status(self._frame(400)["error"]) == 400
        assert providers._stream_error_status(self._frame("400")["error"]) == 400

    def test_a_frame_with_no_usable_status_still_reports_zero(self):
        """An overload frame is not a rejection and must not claim to be one."""
        assert providers._stream_error_status({"message": "overloaded"}) == 0
        assert providers._stream_error_status(
            {"code": "invalid_argument"}) == 0
        assert providers._stream_error_status({"code": True}) == 0
        assert providers._stream_error_status(None) == 0

    def test_a_400_in_a_stream_frame_reaches_the_recovery(self, monkeypatch):
        # `_NO_JSON_OBJECT` is process-wide and keyed by (provider, model),
        # which every test in this file shares. Run after one that marks the
        # key, `_apply_json_mode` sends no response_format at all, there is
        # nothing to recover from, and this passes alone and fails in the
        # suite. Clear the key rather than inventing a unique model: the
        # sharing is the hazard worth pinning against.
        key = providers._json_object_key(_prov(), "some/model")
        for store, lock in ((providers._NO_JSON_OBJECT,
                             providers._NO_JSON_OBJECT_LOCK),
                            (providers._NO_JSON_SCHEMA,
                             providers._NO_JSON_SCHEMA_LOCK)):
            with lock:
                store.discard(key)
        seen = []

        def fake_sse(url, headers, body, sink, role=None, model=None):
            seen.append(dict(body))
            if "response_format" in body:
                raise providers.LLMError(
                    "provider stream error: Request contains an invalid "
                    "argument.", 400, True)
            return '{"ok": true}'

        monkeypatch.setattr(providers, "_sse_openai", fake_sse)
        monkeypatch.setattr(providers, "resolve_role",
                            lambda role: (_prov(), "some/model", {}))
        monkeypatch.setattr(
            providers, "token_sink",
            providers.contextvars.ContextVar("t", default=lambda d: None))

        # json_mode is the 5th positional: this request carries a
        # response_format, which is what the provider is rejecting.
        out = providers._chat_complete_once(
            "director", "sys", "user", 0.5, True, 1000, None)

        assert out == '{"ok": true}'
        assert len(seen) == 2
        assert "response_format" in seen[0]
        assert "response_format" not in seen[1], (
            "a rejection carried by a stream frame must reach the same "
            "downgrade an HTTP 400 reaches")

    def test_a_status_zero_stream_error_without_a_schema_still_raises(
            self, monkeypatch):
        """The widening must not swallow an ordinary overload."""
        def fake_sse(url, headers, body, sink, role=None, model=None):
            raise providers.LLMError("provider stream error: overloaded",
                                     0, True)

        monkeypatch.setattr(providers, "_sse_openai", fake_sse)
        monkeypatch.setattr(providers, "resolve_role",
                            lambda role: (_prov(), "some/model", {}))
        monkeypatch.setattr(
            providers, "token_sink",
            providers.contextvars.ContextVar("t", default=lambda d: None))

        with pytest.raises(providers.LLMError):
            providers._chat_complete_once(
                "director", "sys", "user", 0.5, True, 1000, None)


class _Ctx:
    """The two fields `_interpret_beat_view` reads. Deliberately not a real
    PipelineContext: this pins the ruling channel, not scene assembly."""
    cast = ()
    input = ""


class TestBothDirectorInvocationsCarryOneCausalLedger:
    """Both invocation points share one live model contract."""

    def test_both_schemas_accept_the_ledger(self):
        from llm.schemas import DirectorInterpret, DirectorResolve, _fields

        for model in (DirectorInterpret, DirectorResolve):
            assert "ledgers" in _fields(model), model.__name__

    def test_both_prompts_publish_only_the_causal_work_item(self):
        from llm.prompts import prose_author_prompt

        text = prose_author_prompt(None)
        for name in ("director_interpret", "director_resolve"):
            assert '"ledgers"' in text, name
            assert "resolution_notes" in text, name
            assert "object_name" in text, name
            assert "item_id" in text, name
            assert "categories" in text, name
            assert "state_diff" not in text, name
            assert "changes_asserted" not in text, name
            assert "ledger_notes" not in text, name

    def test_one_span_can_address_several_hands(self):
        from agents import director

        out = {"ledgers": [{
            "chrono_id": 1,
            "item_id": 1,
            "object_name": "coat",
            "source_entity_id": "entity:1",
            "kind": "action",
            "event": "The entity removes and drops its coat.",
            "resolution_notes": "The coat is no longer worn and is in room:1.",
            "categories": ["attire", "entities", "positions"],
        }]}
        director.normalize_causal_ledger(out)
        view = director._interpret_beat_view(_Ctx(), out, "entity:1")
        assert set(view["spans"][0]["categories"]) == {
            "attire", "entities", "positions"}
