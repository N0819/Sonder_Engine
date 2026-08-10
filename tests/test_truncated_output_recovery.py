"""A beat must not be lost because the model ran out of room to answer in.

Two of fourteen beats of a real-model playthrough died outright, both the same
shape: the JSON was cut off mid-object and the whole turn raised.

    beat 10: RuntimeError: mapping_stage failed JSON validation:
             LLM returned invalid JSON: Expecting ',' delimiter at position 5042
    beat 14: RuntimeError: character failed JSON validation:
             LLM returned invalid JSON: Expecting ',' delimiter at position 10054

Nothing was wrong with either answer. The model was part-way through a long
per-lore-entry `why_relevant` field when its output budget ended, and the
recovery ladder in `complete_validated_json` then spent a temperature-0 repair
and every fallback candidate re-asking the SAME model for the SAME object on
the SAME budget -- with the truncated 5k-character attempt added to the prompt,
so the second attempt had strictly less room than the first. It could not
succeed, and the error it finally raised named a JSON delimiter, which reads as
a model that cannot write JSON rather than one that was not given space to.

The signal was available the whole time and thrown away: every provider states
`finish_reason: length` / `stop_reason: max_tokens` on the response, and
`providers` dropped it at the response boundary.
"""

import json

import pytest

import llm_quality
import providers


# A cut-off object in each of the two shapes json.decoder produces, both taken
# from the real failure: one stopping inside a string, one stopping just after
# a complete value.
TRUNCATED_MID_STRING = (
    '{"sequence": [{"kind": "speech", "text": "the lantern at the cellar '
    'stair was still'
)
TRUNCATED_AFTER_VALUE = (
    '{"sequence": [{"kind": "speech", "text": "the lantern was warm."'
)
# Malformed for a different reason: an unescaped quote a third of the way in,
# with the rest of the object still following it. Same exception class, same
# message, and more room fixes nothing.
BAD_ESCAPING = '{"sequence": [], "interaction": {"note": "he said "hi" here"}}'

VALID_CHARACTER = json.dumps({"sequence": [], "interaction": {}})


class _ScriptedLLM:
    """Stands in for llm_quality.chat_complete, recording every call."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, role, system, user, **kwargs):
        self.calls.append({"role": role, "system": system,
                           "user": user, **kwargs})
        if not self.responses:
            raise AssertionError(
                "chat_complete called more times than scripted")
        return self.responses.pop(0)


def _script(monkeypatch, responses, candidates=1, ceiling=20000):
    llm = _ScriptedLLM(responses)
    monkeypatch.setattr(llm_quality, "chat_complete", llm)
    monkeypatch.setattr(
        llm_quality, "role_candidate_count", lambda role: candidates)
    # The ceiling is read from the settings table, and a fast-tier test must
    # not depend on a database having been initialized by another test.
    monkeypatch.setattr(providers, "max_output_tokens", lambda: ceiling)
    return llm


class TestTruncationIsDistinguishableFromNonsense:
    """"Ran out of room" and "wrote nonsense" arrive as the same exception and
    need opposite responses, so telling them apart is the whole fix.

    Both real failures were `Expecting ',' delimiter`, which is also what bad
    escaping raises. What separates them is not the message but whether
    anything follows the failure: a truncation dies at the last character it
    has, a malformed object dies with its remainder still ahead of it.
    """

    def test_an_object_cut_off_inside_a_string_is_a_length_failure(self):
        assert llm_quality.output_ran_out_of_room(TRUNCATED_MID_STRING)

    def test_an_object_cut_off_after_a_complete_value_is_one_too(self):
        assert llm_quality.output_ran_out_of_room(TRUNCATED_AFTER_VALUE)

    def test_bad_escaping_in_the_middle_is_not(self):
        """The discriminator that carries the whole design: this raises the
        same message the playthrough did, and escalating its budget would
        spend a second call to be told the same thing."""
        assert not llm_quality.output_ran_out_of_room(BAD_ESCAPING)

    def test_a_whole_object_is_not(self):
        assert not llm_quality.output_ran_out_of_room(VALID_CHARACTER)

    def test_an_empty_response_is_not_evidence_either_way(self):
        """A provider returning an empty body looks identical to a reasoning
        model that spent every token thinking; only the finish reason tells
        them apart, so the text check must not guess."""
        assert not llm_quality.output_ran_out_of_room("")

    def test_a_fence_is_stripped_before_the_end_is_measured(self):
        """The check compares the failure position against the length of the
        text, so measuring a fenced response unstripped would be wrong by
        exactly the length of the fence."""
        assert llm_quality.output_ran_out_of_room(
            "```json\n" + TRUNCATED_AFTER_VALUE)

    def test_the_provider_saying_length_outranks_the_text(self, monkeypatch):
        """A truncated response can still PARSE: _extract_balanced_object
        recovers the first complete inner object out of a cut-off outer one,
        which then fails validation on the fields that never arrived. The text
        has nothing left to show, and only the finish reason does."""
        monkeypatch.setattr(llm_quality, "response_truncated", lambda: True)
        assert llm_quality.output_ran_out_of_room(VALID_CHARACTER)


class TestABeatIsNotLostToALengthProblem:
    """The reproduction, and what it now does instead of dying."""

    def test_a_truncated_beat_is_retried_with_room_and_survives(
            self, monkeypatch):
        llm = _script(monkeypatch, [TRUNCATED_MID_STRING, VALID_CHARACTER])

        out = llm_quality.complete_validated_json(
            role="character_mid", step_key="character", system="sys",
            payload={"x": 1})

        assert out["sequence"] == []
        assert len(llm.calls) == 2, "one retry, not a ladder of them"
        assert llm.calls[0]["max_tokens"] is None, (
            "the stage asks for the configured ceiling")
        assert llm.calls[1]["max_tokens"] == 40000, (
            "the retry must carry MORE room than the call that ran out of it")

    def test_the_retry_carries_a_ceiling_that_can_exceed_the_configured_one(
            self, monkeypatch):
        """`_clamp_max_tokens` only ever lowers, so a bare `max_tokens` above
        the configured ceiling would be clamped straight back onto the wall the
        response just hit."""
        llm = _script(monkeypatch, [TRUNCATED_MID_STRING, VALID_CHARACTER])

        llm_quality.complete_validated_json(
            role="character_mid", step_key="character", system="sys",
            payload={"x": 1})

        assert llm.calls[1]["token_ceiling"] == 40000

    def test_the_retry_is_the_original_request_not_a_repair_prompt(
            self, monkeypatch):
        """The model had the right answer and nowhere to put it. Handing back
        its own truncated 5k-character attempt only makes the input bigger,
        which is what the repair path was doing and why it could not win."""
        llm = _script(monkeypatch, [TRUNCATED_MID_STRING, VALID_CHARACTER])

        llm_quality.complete_validated_json(
            role="character_mid", step_key="character", system="sys",
            payload={"x": 1})

        assert llm.calls[1]["system"] == "sys"
        assert llm.calls[1]["user"] == llm.calls[0]["user"]
        assert "repair" not in llm.calls[1]["system"].lower()

    def test_a_merely_malformed_response_still_goes_to_repair_unescalated(
            self, monkeypatch):
        """A content failure must not buy a bigger budget: the escalation is
        an extra paid call, and spending it on an output that was wrong rather
        than short is exactly the cost this guard is meant to avoid."""
        llm = _script(monkeypatch, [BAD_ESCAPING, VALID_CHARACTER])

        llm_quality.complete_validated_json(
            role="character_mid", step_key="character", system="sys",
            payload={"x": 1})

        assert len(llm.calls) == 2
        assert llm.calls[1]["max_tokens"] is None, "budget unchanged"
        assert llm.calls[1]["token_ceiling"] is None
        assert "repair" in llm.calls[1]["system"].lower()

    def test_the_room_is_inherited_by_the_repair_and_the_fallbacks(
            self, monkeypatch):
        """Once the budget is known to have been short, every later attempt in
        this call needs the same room -- a repair rebuilding the same object on
        the old budget re-creates the failure it is repairing."""
        llm = _script(
            monkeypatch,
            [TRUNCATED_MID_STRING, TRUNCATED_MID_STRING,
             TRUNCATED_MID_STRING, VALID_CHARACTER],
            candidates=2)

        llm_quality.complete_validated_json(
            role="character_mid", step_key="character", system="sys",
            payload={"x": 1})

        assert [c["max_tokens"] for c in llm.calls] == [
            None, 40000, 40000, 40000]


class TestTheEscalationIsBounded:
    """A retry that can raise its own budget is a spend loop unless the bound
    is structural. There is no counter here: the escalation is straight-line
    code that runs at most once, and the size it asks for is one stage's worth
    of headroom rather than a multiplier that compounds."""

    def test_a_response_that_keeps_truncating_is_escalated_only_once(
            self, monkeypatch):
        llm = _script(
            monkeypatch,
            [TRUNCATED_MID_STRING] * 4,
            candidates=2)

        with pytest.raises(RuntimeError):
            llm_quality.complete_validated_json(
                role="character_mid", step_key="character", system="sys",
                payload={"x": 1})

        budgets = [c["max_tokens"] for c in llm.calls]
        assert budgets == [None, 40000, 40000, 40000], (
            "the whole ladder, and one size above the ceiling in it")

    def test_the_headroom_is_fixed_rather_than_a_multiplier(self, monkeypatch):
        """Doubling scales the retry with the SETTING instead of with the miss,
        so a host who has already raised the ceiling to 40000 gets an
        80000-token request -- and an unreachable max_tokens is precisely what
        the ceiling exists to prevent (providers reject a model outright when
        input + max_tokens exceeds its context window)."""
        monkeypatch.setattr(providers, "max_output_tokens", lambda: 40000)
        assert providers.escalated_max_tokens(None) == 60000

    def test_a_call_already_at_the_absolute_cap_gets_no_retry(
            self, monkeypatch):
        monkeypatch.setattr(
            providers, "max_output_tokens",
            lambda: providers.MAX_OUTPUT_TOKENS_MAX)
        assert providers.escalated_max_tokens(None) == 0

    def test_a_deliberately_small_budget_escalates_only_to_the_ceiling(
            self, monkeypatch):
        """"Lower it to hard-cap spend per call" has to keep meaning that. A
        1000-token utility call asked for less on purpose."""
        monkeypatch.setattr(providers, "max_output_tokens", lambda: 20000)
        assert providers.escalated_max_tokens(1000) == 20000

    def test_the_ceiling_override_only_ever_raises(self, monkeypatch):
        monkeypatch.setattr(providers, "max_output_tokens", lambda: 20000)
        assert providers._clamp_max_tokens(50000, ceiling=40000) == 40000
        assert providers._clamp_max_tokens(50000, ceiling=None) == 20000
        assert providers._clamp_max_tokens(50000, ceiling=5000) == 20000, (
            "a lower override must not shrink the configured ceiling")
        assert providers._clamp_max_tokens(
            999999, ceiling=999999) == providers.MAX_OUTPUT_TOKENS_MAX


class TestTheRetryIsVisible:
    """This repo's worst recurring defect is a mechanism that runs and says
    nothing. A model that never fits its budget would otherwise look like a
    slow one, and the extra call would be invisible on the bill."""

    def test_a_truncation_retry_reaches_the_live_turn_view(self, monkeypatch):
        _script(monkeypatch, [TRUNCATED_MID_STRING, VALID_CHARACTER])
        seen = []
        token = providers.generation_event_sink.set(seen.append)
        try:
            llm_quality.complete_validated_json(
                role="character_mid", step_key="character", system="sys",
                payload={"x": 1})
        finally:
            providers.generation_event_sink.reset(token)

        assert len(seen) == 1
        assert seen[0]["type"] == "generation_reset", (
            "the browser already understands this event, and it also clears "
            "the truncated half-sentence left in the stream pane")
        assert "truncated" in seen[0]["reason"]
        assert "40000" in seen[0]["reason"]

    def test_a_lost_beat_names_truncation_rather_than_a_delimiter(
            self, monkeypatch):
        """`Expecting ',' delimiter at position 5042` sent the last
        investigation of this to the schema instead of to the budget."""
        _script(monkeypatch, [TRUNCATED_MID_STRING] * 3)

        with pytest.raises(RuntimeError) as exc:
            llm_quality.complete_validated_json(
                role="character_mid", step_key="character", system="sys",
                payload={"x": 1})

        msg = str(exc.value)
        assert "RESPONSE TRUNCATED" in msg
        assert "Max output tokens" in msg

    def test_and_says_so_when_there_was_no_larger_retry_to_make(
            self, monkeypatch):
        _script(monkeypatch, [TRUNCATED_MID_STRING] * 2,
                ceiling=providers.MAX_OUTPUT_TOKENS_MAX)

        with pytest.raises(RuntimeError) as exc:
            llm_quality.complete_validated_json(
                role="character_mid", step_key="character", system="sys",
                payload={"x": 1})

        assert "no larger retry" in str(exc.value)

    def test_a_content_failure_is_not_reported_as_a_truncation(
            self, monkeypatch):
        _script(monkeypatch, [BAD_ESCAPING] * 3)

        with pytest.raises(RuntimeError) as exc:
            llm_quality.complete_validated_json(
                role="character_mid", step_key="character", system="sys",
                payload={"x": 1})

        assert "RESPONSE TRUNCATED" not in str(exc.value)


class TestTheProviderSaysWhyItStopped:
    """The finish reason was on every response and read by nothing.

    Captured on the streaming path first: the pipeline sets a token sink for
    the live UI and therefore streams, so a capture added only to the
    non-streaming branch is dead exactly where it is needed -- which is what
    happened to reasoning capture for a release.
    """

    def _stream(self, chunks):
        return [b"data: " + json.dumps(c).encode()
                for c in chunks] + [b"data: [DONE]"]

    def _fake_session(self, monkeypatch, lines):
        class FakeResp:
            status_code = 200

            def iter_lines(self):
                return iter(lines)

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        resp = FakeResp()
        monkeypatch.setattr(
            providers, "_session",
            lambda: type("S", (), {"post": lambda *a, **k: resp})())

    def test_the_openai_stream_records_a_length_stop(self, monkeypatch):
        self._fake_session(monkeypatch, self._stream([
            {"choices": [{"delta": {"content": '{"ok":'}}]},
            {"choices": [{"delta": {}, "finish_reason": "length"}]},
        ]))
        token = providers.last_finish_reason.set(None)
        try:
            providers._sse_openai("u", {}, {}, lambda d: None)
            assert providers.response_truncated()
        finally:
            providers.last_finish_reason.reset(token)

    def test_a_normal_stop_on_the_same_path_is_not_a_truncation(
            self, monkeypatch):
        self._fake_session(monkeypatch, self._stream([
            {"choices": [{"delta": {"content": '{"ok":1}'}}]},
            {"choices": [{"delta": {}, "finish_reason": "stop"}]},
        ]))
        token = providers.last_finish_reason.set(None)
        try:
            providers._sse_openai("u", {}, {}, lambda d: None)
            assert not providers.response_truncated()
        finally:
            providers.last_finish_reason.reset(token)

    def test_openrouters_native_reason_counts_too(self, monkeypatch):
        """An aggregator normalizes the upstream's reason into
        `finish_reason` and passes the verbatim one through beside it; either
        saying length is length."""
        self._fake_session(monkeypatch, self._stream([
            {"choices": [{"delta": {}, "finish_reason": "stop",
                          "native_finish_reason": "MAX_TOKENS"}]},
        ]))
        token = providers.last_finish_reason.set(None)
        try:
            providers._sse_openai("u", {}, {}, lambda d: None)
            assert providers.response_truncated()
        finally:
            providers.last_finish_reason.reset(token)

    def test_the_anthropic_stream_records_its_own_spelling(self, monkeypatch):
        """Anthropic reports `max_tokens` on message_delta, not a choice."""
        self._fake_session(monkeypatch, self._stream([
            {"type": "content_block_delta", "delta": {"text": "{"}},
            {"type": "message_delta", "delta": {"stop_reason": "max_tokens"}},
        ]))
        token = providers.last_finish_reason.set(None)
        try:
            providers._sse_anthropic("b", {}, {}, lambda d: None)
            assert providers.response_truncated()
        finally:
            providers.last_finish_reason.reset(token)

    def test_a_stale_reason_cannot_be_read_as_the_next_calls_truncation(
            self, monkeypatch):
        """A leftover `length` from an earlier call on this thread would spend
        a whole escalated retry on a response that was merely wrong."""
        recorded = []
        monkeypatch.setattr(providers, "resolve_role_candidates",
                            lambda role: [({"kind": "openai",
                                            "base_url": "http://x",
                                            "api_key": "",
                                            "name": "p"}, "m", {})])

        class FakeResp:
            status_code = 200

            def json(self):
                return {"choices": [{"message": {"content": "{}"}}],
                        "usage": {}}

        monkeypatch.setattr(
            providers, "_session",
            lambda: type("S", (), {"post": lambda *a, **k: FakeResp()})())

        token = providers.last_finish_reason.set("length")
        try:
            providers._chat_complete_once(
                "character_mid", "sys", "user", None, True, 100, None)
            recorded.append(providers.response_truncated())
        finally:
            providers.last_finish_reason.reset(token)

        assert recorded == [False], (
            "a response that says nothing about why it stopped is unknown, "
            "not truncated")
