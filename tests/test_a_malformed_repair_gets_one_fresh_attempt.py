"""A MALFORMED REPAIR GETS ONE FRESH ATTEMPT BEFORE THE BEAT ABORTS.

The owner's ruling of 2026-10-09, D5 of the Brackwater run
(`docs/experiments/PLAY_2026_10_07_brackwater.md`, F93): "one fresh encoder
attempt before a beat with a malformed repair aborts" -- an aborted beat is
the worst break in immersion, and the attempt costs one call only on a beat
that would otherwise fail.

The fresh ask landed 2026-10-08 (`llm_quality.MALFORMED_REASKS`, see
`tests/test_a_malformed_answer_is_asked_afresh.py`) for the shape turn 4601
had -- NOTHING the ladder held ever parsed. It left three shapes of the
ruled case losing the beat with no fresh attempt:

* an answer that parsed and failed validation, whose rebuild came back
  malformed -- the repair itself malformed;
* a malformed answer whose rebuild parsed and still failed -- including the
  answer a cut request gave when asked again with room;
* a malformed answer whose repair -- the rebuild, or the last fallback
  candidate -- was cut off for want of room: the gate read the LAST rung's
  cut, where only the request's own answer being cut means asking it again
  would repeat a request that ran out of room.

And the record of a kept beat could not say which attempt its encoding came
from: every rung after the first spoke as an unattributed "llm second call"
warning. Now `llm_quality.answered_by` names the attempt -- `first_pruned`
when the first answer, its failing fields taken out, is kept over a thinner
repair -- and the encoder files it on the stage's prose-contract record
(`encoder.attempt`). The fresh ask's warning says why it fired, read across
every rung: "no answer parsed" only when none did.

A beat with a VALID first answer is also never lost to its widening: when
the widened request's own ladder fails to the end, the first answer stands.

Measured before this landed: 2 of 464 captured encoder answers in the
scratch play database failed to parse, both turn 4601's, and that beat was
lost; no kept prose-contract beat of either database (338 and 236) reached
the ladder at all.
"""

from __future__ import annotations

import json

import pytest

import agents.common as common
import agents.director as director
from core.pipeline_context import current_warning_sink
from llm import decisions, llm_quality
from tests.director_fakes import _make_ctx, encoder_event

GOOD_EVENTS = [{
    "source_entity_id": "character:1", "source_event_id": "",
    "event": "Mara lifts the key", "observable": "", "speech": False,
    "targets": [], "movement": None, "commitment": "asserted",
    "item_names": ["key"],
    "transforms": [{"item": "key", "patch": {"inventory_ops": [
        {"op": "transfer", "object_id": "key", "from_id": "table",
         "to_id": "Mara", "relation": "held"}]}}]}]

GOOD = json.dumps({"events": GOOD_EVENTS, "missing_tools": [],
                   "missing_referents": [], "notes": []})

#: Two events: the key, as in GOOD, and a coin lifted the same way.
TWO_EVENTS = GOOD_EVENTS + [{
    "source_entity_id": "character:1", "source_event_id": "",
    "event": "Mara lifts the coin", "observable": "", "speech": False,
    "targets": [], "movement": None, "commitment": "asserted",
    "item_names": ["coin"],
    "transforms": [{"item": "coin", "patch": {"inventory_ops": [
        {"op": "transfer", "object_id": "coin", "from_id": "table",
         "to_id": "Mara", "relation": "held"}]}}]}]

#: Unparseable, and nothing a mend may touch: a value without its quotes.
UNMENDABLE = ('{"events": [{"event": Mara lifts the key}], '
              '"missing_tools": [], "missing_referents": [], "notes": []}')


def _invalid(events=None):
    """An answer that PARSES and fails validation: its first event's
    `seconds` is a word."""
    answer = json.loads(GOOD)
    if events is not None:
        answer["events"] = json.loads(json.dumps(events))
    answer["events"][0]["seconds"] = "soon"
    assert not llm_quality.validate_llm_output_strict(
        "director_specialist", answer).valid
    return json.dumps(answer)


class _Scripted:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, role, system, user, **kwargs):
        self.calls.append({"system": system, "user": user, **kwargs})
        if not self.responses:
            raise AssertionError("chat_complete called more times than scripted")
        return self.responses.pop(0)


@pytest.fixture
def warnings():
    seen = []
    token = current_warning_sink.set(seen.append)
    yield seen
    current_warning_sink.reset(token)


def _ladder(monkeypatch, responses):
    llm = _Scripted(responses)
    monkeypatch.setattr(llm_quality, "chat_complete", llm)
    monkeypatch.setattr(llm_quality, "role_candidate_count", lambda role: 1)
    monkeypatch.setattr(llm_quality, "_targeted_field_patch",
                        lambda *a, **k: None)
    return llm


def _run():
    return llm_quality.complete_validated_json(
        role="encoder", step_key="director_specialist",
        system="THE ENCODER SHEET", payload={"prose": "Mara lifts the key."},
        temperature=0.2)


# ---------------------------------------------------------------------------
# The ladder
# ---------------------------------------------------------------------------

class TestAMalformedRepair:
    def test_a_parsed_answer_whose_repair_comes_back_malformed_is_asked_afresh(
            self, monkeypatch, warnings):
        llm = _ladder(monkeypatch, [_invalid(), UNMENDABLE, GOOD])
        out = _run()
        assert out["events"][0]["event"] == "Mara lifts the key"
        assert len(llm.calls) == 3
        first, rebuild, fresh = llm.calls
        # The rebuild is handed the broken draft; the fresh ask is the
        # original request, as itself.
        assert "previous_raw_output" in json.loads(rebuild["user"])
        assert fresh["system"] == first["system"] == "THE ENCODER SHEET"
        assert fresh["user"] == first["user"]
        assert fresh.get("temperature") == 0.2
        assert any("the repair came back malformed; asked the original "
                   "request afresh" in w and "director_specialist" in w
                   for w in warnings), warnings

    def test_a_malformed_answer_whose_repair_parses_and_fails_is_asked_afresh(
            self, monkeypatch, warnings):
        llm = _ladder(monkeypatch, [UNMENDABLE, _invalid(), GOOD])
        out = _run()
        assert out["events"][0]["event"] == "Mara lifts the key"
        assert len(llm.calls) == 3
        assert any("came back malformed and its repair did not validate; "
                   "asked the original request afresh" in w
                   for w in warnings), warnings

    def test_a_cut_answer_is_not_a_malformed_one_and_a_malformed_repair_is(
            self, monkeypatch, warnings):
        """An answer cut off for want of room fails to parse too, and is the
        re-ask with room's case. Asked again with room, it parsed and failed:
        a rebuild that ALSO parsed and failed leaves a content failure with
        nothing malformed in it, and no fresh ask; a rebuild that came back
        malformed is the owner's case, and earns one."""
        cut = GOOD[:-60]
        monkeypatch.setattr(llm_quality, "output_ran_out_of_room",
                            lambda raw: raw == cut)
        monkeypatch.setattr(llm_quality, "escalated_max_tokens",
                            lambda max_tokens: 30000)
        llm = _ladder(monkeypatch, [cut, _invalid(), _invalid()])
        with pytest.raises(RuntimeError):
            _run()
        assert len(llm.calls) == 3
        assert not any("asked the original request afresh" in w
                       for w in warnings), warnings

        llm = _ladder(monkeypatch, [cut, _invalid(), UNMENDABLE, GOOD])
        out = _run()
        assert out["events"][0]["event"] == "Mara lifts the key"
        assert len(llm.calls) == 4
        assert any("the repair came back malformed; asked the original "
                   "request afresh" in w for w in warnings), warnings

    def test_a_malformed_answer_from_the_re_ask_with_room_is_asked_afresh(
            self, monkeypatch, warnings):
        """The first answer was cut for want of room; the re-ask with room
        came back malformed, and not cut; its rebuild parsed and failed. A
        malformed answer is in the failure, and the request is asked afresh
        -- with the room the re-ask was given -- before the beat is lost."""
        cut = GOOD[:-60]
        monkeypatch.setattr(llm_quality, "output_ran_out_of_room",
                            lambda raw: raw == cut)
        monkeypatch.setattr(llm_quality, "escalated_max_tokens",
                            lambda max_tokens: 30000)
        llm = _ladder(monkeypatch, [cut, UNMENDABLE, _invalid(), GOOD])
        out = _run()
        assert out["events"][0]["event"] == "Mara lifts the key"
        assert len(llm.calls) == 4
        first, again, _rebuild, fresh = llm.calls
        assert fresh["user"] == first["user"]
        assert fresh.get("max_tokens") == again.get("max_tokens") == 30000
        assert any("the answer came back malformed and its repair did not "
                   "validate; asked the original request afresh" in w
                   for w in warnings), warnings

    @pytest.mark.parametrize("candidates, responses, why", [
        # An unmendable first answer, whole; its rebuild cut for want of room.
        (1, [UNMENDABLE, GOOD[:-60], GOOD], "no answer parsed"),
        # A first answer that parsed and failed, a malformed rebuild, and the
        # last fallback candidate cut for want of room.
        (2, [_invalid(), UNMENDABLE, GOOD[:-60], GOOD],
         "the repair came back malformed"),
    ], ids=["the_rebuild_cut", "the_last_fallback_cut"])
    def test_a_malformed_answer_is_asked_afresh_though_its_repair_ran_out_of_room(
            self, monkeypatch, warnings, candidates, responses, why):
        """A REPAIR cut off for want of room says nothing about the request:
        the request's own answer came back whole, and a malformed answer is
        in the failure, so the request is asked afresh at its own budget --
        the owner's D5 case. Only an answer the request ITSELF gave cut off
        stops the fresh ask, which would repeat a request that ran out of
        room (`test_a_request_that_ran_out_of_room_is_not_asked_again_afresh`).
        The gate used to read the LAST rung's cut as well, so both shapes
        lost the beat after their repair with no fresh attempt (scripted on
        the D5 landing's second round, 2026-10-09)."""
        cut = GOOD[:-60]
        monkeypatch.setattr(llm_quality, "output_ran_out_of_room",
                            lambda raw: raw == cut)
        llm = _ladder(monkeypatch, responses)
        monkeypatch.setattr(llm_quality, "role_candidate_count",
                            lambda role: candidates)
        token = llm_quality.answered_by.set("")
        try:
            out = _run()
            assert llm_quality.answered_by.get() == "fresh"
        finally:
            llm_quality.answered_by.reset(token)
        assert out["events"][0]["event"] == "Mara lifts the key"
        assert len(llm.calls) == len(responses)
        first, fresh = llm.calls[0], llm.calls[-1]
        assert fresh["system"] == first["system"] == "THE ENCODER SHEET"
        assert fresh["user"] == first["user"]
        assert fresh.get("max_tokens") == first.get("max_tokens")
        assert any(f"{why}; asked the original request afresh" in w
                   for w in warnings), warnings

    def test_the_warning_says_an_answer_parsed_when_one_did(
            self, monkeypatch, warnings):
        """A malformed answer, a rebuild that parsed and failed, then a
        fallback candidate that came back malformed: the fresh ask is earned,
        and its warning names the malformed repair -- never "no answer
        parsed", which the last rung alone would have said."""
        llm = _ladder(monkeypatch, [UNMENDABLE, _invalid(), UNMENDABLE, GOOD])
        monkeypatch.setattr(llm_quality, "role_candidate_count", lambda role: 2)
        out = _run()
        assert out["events"][0]["event"] == "Mara lifts the key"
        assert len(llm.calls) == 4
        fresh_warnings = [w for w in warnings
                          if "asked the original request afresh" in w]
        assert fresh_warnings and all(
            "the repair came back malformed" in w for w in fresh_warnings), \
            warnings
        assert not any("no answer parsed" in w for w in warnings), warnings

    def test_one_fresh_attempt_and_then_the_stage_fails(
            self, monkeypatch, warnings):
        assert llm_quality.MALFORMED_REASKS == 1
        llm = _ladder(monkeypatch, [_invalid(), UNMENDABLE, UNMENDABLE])
        with pytest.raises(RuntimeError, match="failed JSON validation"):
            _run()
        assert len(llm.calls) == 2 + llm_quality.MALFORMED_REASKS


class TestTheTraceSaysWhichAttemptLanded:
    @pytest.mark.parametrize("responses, attempt", [
        ([GOOD], "first"),
        ([UNMENDABLE, GOOD], "rebuild"),
        ([UNMENDABLE, UNMENDABLE, GOOD], "fresh"),
        ([_invalid(), UNMENDABLE, GOOD], "fresh"),
    ])
    def test_the_accepted_answer_names_its_attempt(
            self, monkeypatch, warnings, responses, attempt):
        _ladder(monkeypatch, responses)
        token = llm_quality.answered_by.set("")
        try:
            _run()
            assert llm_quality.answered_by.get() == attempt
        finally:
            llm_quality.answered_by.reset(token)

    def test_a_first_answer_kept_over_a_thinner_rebuild_is_named_first_pruned(
            self, monkeypatch, warnings):
        """The first answer parsed with two events, one carrying a bad field;
        the rebuild validated with only one. The ladder keeps the FIRST
        answer with its failing field taken out (`_unshrunk`) -- both events
        reach the beat -- and the record says so, rather than naming the
        rebuild whose answer was refused."""
        llm = _ladder(monkeypatch, [_invalid(TWO_EVENTS), GOOD])
        token = llm_quality.answered_by.set("")
        try:
            out = _run()
            assert llm_quality.answered_by.get() == "first_pruned"
        finally:
            llm_quality.answered_by.reset(token)
        assert [e["event"] for e in out["events"]] == [
            "Mara lifts the key", "Mara lifts the coin"]
        assert "seconds" not in out["events"][0]
        assert len(llm.calls) == 2
        assert any("kept that answer with only its failing fields taken out"
                   in w for w in warnings), warnings

    def test_a_mended_answer_names_the_mend(self, monkeypatch, warnings):
        """Turn 4601's own slip -- an object left open before its next
        sibling -- mends locally with no call, and says so."""
        answer = json.loads(GOOD)
        answer["events"][0]["item_names"] = ["key", "coin"]
        answer["events"][0]["transforms"].append(
            {"item": "coin", "patch": {"inventory_ops": [
                {"op": "transfer", "object_id": "coin", "from_id": "table",
                 "to_id": "Mara", "relation": "held"}]}})
        text = json.dumps(answer, separators=(",", ":"))
        broken = text.replace('"held"}]}},{"item":"coin"',
                              '"held"}]},{"item":"coin"', 1)
        assert broken != text
        llm = _ladder(monkeypatch, [broken])
        token = llm_quality.answered_by.set("")
        try:
            _run()
            assert llm_quality.answered_by.get() == "mended"
        finally:
            llm_quality.answered_by.reset(token)
        assert len(llm.calls) == 1


# ---------------------------------------------------------------------------
# The beat: the record, and a widening that fails
# ---------------------------------------------------------------------------

PROSE = "Mara lights the lamp."


def _encoder_answer(*, missing=()):
    return {"events": [encoder_event(PROSE, source="character:mara")],
            "missing_tools": list(missing), "missing_referents": [],
            "notes": []}


def _decide_all(state, questions):
    from agents.director_prose import WALK_PREFIX
    return {key: {"type": "noul",
                  "noul": 0.01 if key.startswith((WALK_PREFIX, "ended:")) else 0.99}
            for key in questions}


def test_the_beats_record_names_the_attempt_its_events_came_from(
        temp_db, prose_director, monkeypatch):
    """The encoder answered malformed, its repair came back malformed, and
    the fresh asking landed: the beat is kept, and its record says so."""
    ctx = _make_ctx(temp_db, interp={"sequence": []})
    scripted = _ladder(monkeypatch, [UNMENDABLE, UNMENDABLE,
                                     json.dumps(_encoder_answer())])

    def agent(role, step_key, system, payload, **kw):
        if step_key == "director_specialist":
            return common._agent_json(role, step_key, system, payload, **kw)
        if step_key == "director_prose":
            return {"prose": PROSE}
        return {}

    monkeypatch.setattr(director, "_agent_json", agent)
    out = director.director_resolve(ctx, nonce=0)
    encoder = out["orchestration"]["prose_contract"]["encoder"]
    assert encoder["attempt"] == "fresh"
    assert len(scripted.calls) == 3


def test_a_widening_that_fails_keeps_the_first_answer(
        temp_db, prose_director, monkeypatch):
    """The first answer validated and named a tool it lacked; the widened
    request's own ladder failed to the end. The beat stands on the first
    answer instead of aborting."""
    ctx = _make_ctx(temp_db, interp={"sequence": []})

    def deny_positions(state, questions):
        answers = _decide_all(state, questions)
        if "positions" in answers:
            answers["positions"] = {"type": "noul", "noul": 0.01}
        return answers

    monkeypatch.setattr(decisions, "OVERRIDE", deny_positions)
    asked = []

    def agent(role, step_key, system, payload, **kw):
        if step_key == "director_prose":
            return {"prose": PROSE}
        if step_key == "director_specialist":
            asked.append(payload)
            if len(asked) == 1:
                return _encoder_answer(missing=["positions"])
            raise RuntimeError("director_specialist failed JSON validation: "
                               "Expecting ',' delimiter")
        return {}

    monkeypatch.setattr(director, "_agent_json", agent)
    out = director.director_resolve(ctx, nonce=0)
    encoder = out["orchestration"]["prose_contract"]["encoder"]
    assert len(asked) == 2
    assert "failed JSON validation" in encoder["widen_failed"]
    assert out["orchestration"]["prose_contract"]["events"]
    assert any("widened encoder request failed" in w for w in ctx.warnings), \
        ctx.warnings
