"""AN ANSWER THAT NEVER PARSED IS ASKED FOR AFRESH BEFORE THE STAGE FAILS.

Measured, scratch story 166 turn 4601 (the Brackwater run, 2026-10-07): the
encoder's resolve answer left one object open before its next sibling --
`}}}}` for `}}}}}` at char 2778 of 4,482 -- the local mend had no edit for
that shape, the temperature-0 rebuild was handed the broken text and came
back with the same fault at the same character, and the causal stage aborted
the beat. Two of the run's 386 encoder answers failed to parse; both were
that beat's.

Two rungs answer it, each in its own place:

* the mend (`llm/json_mend.py`) closes an object left open before its next
  sibling -- the stored answer mends and validates with no model call;
* a malformed answer nothing could mend or rebuild is asked for AFRESH --
  the original request, its own sheet and sampler, no broken draft attached
  -- `llm_quality.MALFORMED_REASKS` times before the stage fails. A content
  failure (an answer that parsed and failed validation) is not.
"""

from __future__ import annotations

import json

import pytest

from core.pipeline_context import current_warning_sink
from llm import json_mend, llm_quality

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

#: Unparseable, and nothing a mend may touch: a value without its quotes.
UNMENDABLE = ('{"events": [{"event": Mara lifts the key}], '
              '"missing_tools": [], "missing_referents": [], "notes": []}')


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
    return llm


def _run(**kwargs):
    return llm_quality.complete_validated_json(
        role="encoder", step_key="director_specialist",
        system="THE ENCODER SHEET", payload={"prose": "Mara lifts the key."},
        temperature=0.2, **kwargs)


class TestTheMend:
    def test_an_object_left_open_before_its_next_sibling_is_closed(self):
        """Turn 4601's shape, compact: the first transform's patch closed
        one level short, so its sibling opened where a key was wanted."""
        whole = {"events": [{"transforms": [
            {"item": "coat", "patch": {"attire": {"Tam": {"lapels": "brass"}}}},
            {"item": "stake", "patch": {"entities": {"stake": {"split": True}}}},
        ]}]}
        text = json.dumps(whole, separators=(",", ":"))
        broken = text.replace('}}}},{"item":"stake"', '}}},{"item":"stake"', 1)
        assert broken != text
        found = list(json_mend.mend_candidates(broken))
        assert [value for value, _edits in found][:1] == [whole], found
        assert found[0][1] == [
            "closed an object left open before its next sibling"]

    def test_the_encoder_answer_of_that_shape_costs_no_model_call(
            self, monkeypatch, warnings):
        """End to end: the first transform's patch one closer short before
        its sibling transform, as at char 2778 -- mended, validated, and the
        rebuild rung (which copied the slip live) never asked."""
        answer = json.loads(GOOD)
        answer["events"][0]["item_names"] = ["key", "coin"]
        answer["events"][0]["transforms"].append(
            {"item": "coin", "patch": {"inventory_ops": [
                {"op": "transfer", "object_id": "coin", "from_id": "table",
                 "to_id": "Mara", "relation": "held"}]}})
        assert llm_quality.validate_llm_output_strict(
            "director_specialist", answer).valid
        text = json.dumps(answer, separators=(",", ":"))
        broken = text.replace('"held"}]}},{"item":"coin"',
                              '"held"}]},{"item":"coin"', 1)
        assert broken != text
        llm = _ladder(monkeypatch, [broken])
        out = _run()
        assert len(llm.calls) == 1
        assert [t["item"] for t in out["events"][0]["transforms"]] == [
            "key", "coin"]
        assert any("closed an object left open before its next sibling" in w
                   and "no model call" in w for w in warnings), warnings


class TestTheFreshAsk:
    def test_an_answer_that_never_parsed_is_asked_afresh(
            self, monkeypatch, warnings):
        """The 4601 ladder: a malformed answer, a rebuild that copies the
        slip, then the original request asked again -- as itself."""
        llm = _ladder(monkeypatch, [UNMENDABLE, UNMENDABLE, GOOD])
        out = _run()
        assert out["events"][0]["event"] == "Mara lifts the key"
        assert len(llm.calls) == 3
        first, rebuild, fresh = llm.calls
        # The rebuild is handed the broken draft; the fresh ask is not.
        assert "previous_raw_output" in json.loads(rebuild["user"])
        assert fresh["system"] == first["system"] == "THE ENCODER SHEET"
        assert fresh["user"] == first["user"]
        assert fresh.get("temperature") == 0.2
        assert any("no answer parsed; asked the original request afresh" in w
                   for w in warnings), warnings

    def test_it_is_asked_once_and_then_the_stage_fails(
            self, monkeypatch, warnings):
        assert llm_quality.MALFORMED_REASKS == 1
        llm = _ladder(monkeypatch, [UNMENDABLE, UNMENDABLE, UNMENDABLE])
        with pytest.raises(RuntimeError, match="failed JSON validation"):
            _run()
        assert len(llm.calls) == 2 + llm_quality.MALFORMED_REASKS

    def test_an_empty_object_is_no_fresh_answer(self, monkeypatch, warnings):
        """A `{}` is a stall, not an answer, whatever it validates as: the
        malformed answer stands as the failure, never an empty beat."""
        llm = _ladder(monkeypatch, [UNMENDABLE, UNMENDABLE, "{}"])
        with pytest.raises(RuntimeError, match="invalid JSON"):
            _run()
        assert len(llm.calls) == 3

    def test_a_content_failure_is_not_asked_afresh(
            self, monkeypatch, warnings):
        """An answer that PARSED and failed validation is the repair rungs'
        own case: re-asked from scratch it would only fail the same way."""
        invalid = json.loads(GOOD)
        invalid["events"][0]["seconds"] = "soon"
        assert not llm_quality.validate_llm_output_strict(
            "director_specialist", invalid).valid
        monkeypatch.setattr(llm_quality, "_targeted_field_patch",
                            lambda *a, **k: None)
        llm = _ladder(monkeypatch, [json.dumps(invalid), UNMENDABLE])
        with pytest.raises(RuntimeError):
            _run()
        assert len(llm.calls) == 2
        assert not any("asked the original request afresh" in w
                       for w in warnings), warnings

    def test_a_cut_off_answer_is_the_room_re_asks_not_this_one(
            self, monkeypatch, warnings):
        cut = GOOD[:-60]
        monkeypatch.setattr(llm_quality, "output_ran_out_of_room",
                            lambda raw: raw == cut)
        monkeypatch.setattr(llm_quality, "escalated_max_tokens",
                            lambda max_tokens: 0)
        llm = _ladder(monkeypatch, [cut, cut])
        with pytest.raises(RuntimeError):
            _run()
        assert not any("asked the original request afresh" in w
                       for w in warnings), warnings
        assert len(llm.calls) == 2
