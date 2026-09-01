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


class TestBothHalvesOfTheDirectorCarryTheRuling:
    """`director_interpret` is a structural mirror of `director_resolve`.

    Both fan out to the same six specialists through
    `director._run_specialists`. The ruling channel was built into the resolve
    half only, so for a release the interpret half ran its hands with nothing
    to transcribe -- the exact gap `ledger_notes` exists to close, on half the
    Director's specialist work, and it was invisible because an absent ruling
    is indistinguishable from "this beat settled nothing".

    Pinned as a MIRROR rather than as two separate facts: the failure mode is
    drift between the halves, so the assertion has to be that they agree.
    """

    def test_both_schemas_carry_the_field(self):
        from llm.schemas import DirectorInterpret, DirectorResolve
        for model in (DirectorInterpret, DirectorResolve):
            assert "ledger_notes" in model.model_fields, model.__name__

    def test_both_beat_views_expose_it_under_the_key_routing_reads(self):
        """`_note_for` reads `view["ledger_notes"]`; if a view omits the key
        the routing silently finds nothing for every hand."""
        from agents import director
        notes = {"spatial": "the player's step is a transit"}
        interpret = director._interpret_beat_view(
            _Ctx(), {"ledger_notes": notes, "sequence": []}, "Player")
        assert interpret.get("ledger_notes") == notes
        assert director._note_for(interpret["ledger_notes"], "spatial")

    def test_blank_rulings_are_dropped_on_both_sides_by_one_normalizer(self):
        from agents import director
        raw = {"spatial": "  ", "body": "", "social": " a real ruling "}
        view = director._interpret_beat_view(
            _Ctx(), {"ledger_notes": raw, "sequence": []}, "Player")
        assert view["ledger_notes"] == {"social": "a real ruling"}

    def test_both_prompts_declare_the_field_in_the_shape_they_hand_over(self):
        """The measured lesson: a field asked for in prose and absent from the
        OUTPUT SHAPE does not exist as far as the model is concerned. On the
        resolve side that cost every ruling on a live replay."""
        from llm.prompts import DEFAULT_PROMPTS, prose_author_prompt
        interpret = DEFAULT_PROMPTS["director_interpret"]
        resolve = prose_author_prompt(None)
        for name, text in (("director_interpret", interpret),
                           ("prose_author_sheet", resolve)):
            assert "ledger_notes:{specialist:line}" in text, name
            # and the six names, which the model otherwise guesses at
            assert "body|social|contact|objects|spatial|offscreen" in text, name
