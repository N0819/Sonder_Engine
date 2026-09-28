"""A broken answer's JSON is mended locally before a model is asked.

Every case here is DESIGNED: a correct answer, broken in exactly one of the
ways the owner's capture showed models breaking JSON (2026-09-28: 8 answers
today's parser cannot read -- brackets six times, a key's quotes twice; the
encoder's one failure in 470 calls was two closers in the wrong order). The
mend must give back the correct answer, and must refuse the two things it may
never do: change what the model said, and close an answer that stopped short.
"""

from __future__ import annotations

import json

import pytest

from core.pipeline_context import current_warning_sink
from llm import json_mend, llm_quality

EVENTS = {"events": [
    {"event": "Mara lifts the key", "transforms": [
        {"item": "key", "patch": {"inventory_ops": [{"op": "transfer"}]}}]},
    {"event": "Mara unlocks the door", "transforms": []},
]}


def _mends_to(broken, expected):
    found = list(json_mend.mend_candidates(broken))
    assert found, f"no mend for {broken!r}"
    assert expected in [value for value, _edits in found], found
    return found


@pytest.mark.parametrize("name, broken, expected", [
    ("two closers in the wrong order",
     '{"events": [{"event": "Mara lifts the key", "transforms": [{"item": "key", '
     '"patch": {"inventory_ops": [{"op": "transfer"}]}}}], {"event": '
     '"Mara unlocks the door", "transforms": []}]}', EVENTS),
    ("one closer too many",
     '{"a": [{"b": 1}}], "c": 2}', {"a": [{"b": 1}], "c": 2}),
    ("a closer that ends the answer early",
     '{"a": [{"b": 1}]}], "c": 2}', {"a": [{"b": 1}], "c": 2}),
    ("an inner container never closed",
     '{"a": [{"b": [1, 2}], "n": []}', {"a": [{"b": [1, 2]}], "n": []}),
    ("a keyed map closed like a list",
     '{"room": {"anchors": {"shore": {"dir": "n"}]}, "size": "large"}',
     {"room": {"anchors": {"shore": {"dir": "n"}}}, "size": "large"}),
    ("an unquoted key",
     '{"valence": -0.2, arousal: 0.6}', {"valence": -0.2, "arousal": 0.6}),
    ("a key that lost its closing quote",
     '{\n  "operation": "reinforce",\n  "amount: 0.15,\n  "evidence": []\n}',
     {"operation": "reinforce", "amount": 0.15, "evidence": []}),
    ("a raw line break inside a string",
     '{"prose": "first line\nsecond line"}', {"prose": "first line\nsecond line"}),
    ("a trailing comma", '{"a": [1, 2], "b": 3,}', {"a": [1, 2], "b": 3}),
    ("a comma missing between two elements",
     '{"a": [{"x": 1} {"x": 2}]}', {"a": [{"x": 1}, {"x": 2}]}),
])
def test_each_measured_slip_is_mended(name, broken, expected):
    _mends_to(broken, expected)


def test_a_slip_made_by_habit_is_mended_everywhere_it_recurs():
    """An establish answer closed each of its rooms' keyed maps with `]`,
    eleven times over (capture 1920): more than any edit budget, one slip."""
    rooms = ", ".join(
        f'"r{i}": {{"anchors": {{"a{i}": {{"dir": "n"}}]}}' for i in range(12))
    broken = '{"rooms": {' + rooms + "}}"
    expected = {"rooms": {f"r{i}": {"anchors": {f"a{i}": {"dir": "n"}}}
                          for i in range(12)}}
    found = _mends_to(broken, expected)
    assert any("(x12)" in edit for _value, edits in found for edit in edits), found


def test_a_cut_off_answer_is_never_closed():
    """Brackets left open at the END are what a truncated answer looks like;
    closing them would pass a lost tail off as a whole beat."""
    assert list(json_mend.mend_candidates(
        '{"events": [{"event": "A"}, {"event": "B"')) == []


def test_what_the_model_said_is_never_changed():
    """Brackets and quotes inside a string are its words, not punctuation."""
    broken = '{"said": "a } and a ] and a {\\" too", "list": [1, 2}'
    found = _mends_to(broken, {"said": 'a } and a ] and a {" too', "list": [1, 2]})
    for value, _edits in found:
        assert value["said"] == 'a } and a ] and a {" too'


def test_nothing_to_mend_in_a_valid_answer_or_prose():
    assert list(json_mend.mend_candidates(json.dumps(EVENTS))) == []
    assert list(json_mend.mend_candidates("The lamp gutters and goes out.")) == []


def test_an_answer_past_the_ceiling_is_left_to_the_model_rungs(monkeypatch):
    monkeypatch.setattr(json_mend, "MAX_CHARS", 10)
    assert list(json_mend.mend_candidates('{"a": [1, 2}')) == []


# --- through the ladder -----------------------------------------------------

class _Scripted:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, role, system, user, **kwargs):
        self.calls.append({"system": system, "user": user})
        if not self.responses:
            raise AssertionError("chat_complete called more times than scripted")
        return self.responses.pop(0)


@pytest.fixture
def warnings():
    seen = []
    token = current_warning_sink.set(seen.append)
    yield seen
    current_warning_sink.reset(token)


def _encoder_answer(events_text):
    return ('{"events": ' + events_text + ', "missing_tools": [], '
            '"missing_referents": [], "notes": []}')


GOOD_EVENTS = json.dumps([{
    "source_entity_id": "character:1", "source_event_id": "", "event": "Mara lifts the key",
    "observable": "", "speech": False, "targets": [], "movement": None,
    "commitment": "asserted", "item_names": ["key"],
    "transforms": [{"item": "key", "patch": {"inventory_ops": [
        {"op": "transfer", "object_id": "key", "from_id": "table", "to_id": "Mara",
         "relation": "held"}]}}]}])


def test_the_encoder_answer_is_mended_with_no_model_call(monkeypatch, warnings):
    """The encoder's measured failure, end to end: closers swapped, mended
    here, and the rebuild rung never asked."""
    broken = _encoder_answer(GOOD_EVENTS.replace("}]}]", "}}]]", 1))
    assert broken != _encoder_answer(GOOD_EVENTS)
    llm = _Scripted([broken])
    monkeypatch.setattr(llm_quality, "chat_complete", llm)
    monkeypatch.setattr(llm_quality, "role_candidate_count", lambda role: 1)

    out = llm_quality.complete_validated_json(
        role="encoder", step_key="director_specialist", system="THE ENCODER SHEET",
        payload={"prose": "Mara lifts the key."})

    assert len(llm.calls) == 1
    assert out["events"][0]["transforms"][0]["patch"]["inventory_ops"][0]["to_id"] == "Mara"
    assert any("mended locally" in w and "no model call" in w for w in warnings), warnings


#: The designed fault: a duration no reader can use, on the second event.
TWO_EVENTS = json.dumps({"events": [
    json.loads(GOOD_EVENTS)[0],
    dict(json.loads(GOOD_EVENTS)[0], event="Mara sets the key down",
         seconds="soon"),
], "missing_tools": [], "missing_referents": [], "notes": []})


def _shrinking_rebuild(monkeypatch, rebuilt):
    """A first answer whose second event carries one invalid field, then a
    rebuild that makes it valid by returning `rebuilt`."""
    llm = _Scripted([TWO_EVENTS, rebuilt])
    monkeypatch.setattr(llm_quality, "chat_complete", llm)
    monkeypatch.setattr(llm_quality, "role_candidate_count", lambda role: 1)
    monkeypatch.setattr(llm_quality, "_targeted_field_patch", lambda *a, **k: None)
    return llm


def test_a_rebuild_that_repairs_by_deleting_is_refused(monkeypatch, warnings):
    """FIXING BY DELETION, designed: the rebuild drops the event it could not
    fix. The original minus its one failing field still validates and keeps
    both events, so that is what the beat gets."""
    first = json.loads(TWO_EVENTS)
    assert not llm_quality.validate_llm_output_strict("director_specialist", first).valid
    llm = _shrinking_rebuild(monkeypatch, _encoder_answer(GOOD_EVENTS))
    out = llm_quality.complete_validated_json(
        role="encoder", step_key="director_specialist", system="THE ENCODER SHEET",
        payload={"prose": "Mara lifts the key and sets it down."})
    assert len(llm.calls) == 2
    assert [e["event"] for e in out["events"]] == [
        "Mara lifts the key", "Mara sets the key down"], out
    assert out["events"][1].get("seconds") is None
    assert any("answered with less" in w and "failing fields taken out" in w
               for w in warnings), warnings


def test_a_shrunken_rebuild_stands_when_nothing_else_validates(monkeypatch, warnings):
    """When the original minus its failing fields is still invalid, the
    shrunken rebuild is accepted -- said out loud, never silent."""
    monkeypatch.setattr(llm_quality, "_error_paths", lambda errors: [])
    _shrinking_rebuild(monkeypatch, _encoder_answer(GOOD_EVENTS))
    out = llm_quality.complete_validated_json(
        role="encoder", step_key="director_specialist", system="THE ENCODER SHEET",
        payload={"prose": "Mara lifts the key and sets it down."})
    assert len(out["events"]) == 1
    assert any("answered with less" in w and "accepted" in w for w in warnings), warnings


def test_a_rebuild_that_keeps_everything_is_taken_as_it_came(monkeypatch, warnings):
    fixed = json.loads(TWO_EVENTS)
    fixed["events"][1]["seconds"] = 3
    _shrinking_rebuild(monkeypatch, json.dumps(fixed))
    out = llm_quality.complete_validated_json(
        role="encoder", step_key="director_specialist", system="THE ENCODER SHEET",
        payload={"prose": "Mara lifts the key and sets it down."})
    assert out["events"][1]["seconds"] == 3
    assert not any("answered with less" in w for w in warnings), warnings


def test_the_rebuild_is_sent_the_encoders_own_sheet(monkeypatch, warnings):
    llm = _Scripted(["not JSON at all", _encoder_answer(GOOD_EVENTS)])
    monkeypatch.setattr(llm_quality, "chat_complete", llm)
    monkeypatch.setattr(llm_quality, "role_candidate_count", lambda role: 1)
    llm_quality.complete_validated_json(
        role="encoder", step_key="director_specialist", system="THE ENCODER SHEET",
        payload={"prose": "Mara lifts the key."})
    assert llm.calls[1]["system"].startswith("THE ENCODER SHEET")
    assert json.loads(llm.calls[1]["user"])["required_json_example"]["events"]


def test_a_fenced_answer_is_mended_too(monkeypatch, warnings):
    """The live encoder answers inside a ```json fence; the first live
    designed-failure run sent both of its swapped-closer answers to a model
    rebuild, because the mend read the fence as part of the JSON."""
    broken = "```json\n" + _encoder_answer(GOOD_EVENTS.replace("}]}]", "}}]]", 1)) + "\n```"
    llm = _Scripted([broken])
    monkeypatch.setattr(llm_quality, "chat_complete", llm)
    monkeypatch.setattr(llm_quality, "role_candidate_count", lambda role: 1)

    out = llm_quality.complete_validated_json(
        role="encoder", step_key="director_specialist", system="THE ENCODER SHEET",
        payload={"prose": "Mara lifts the key."})

    assert len(llm.calls) == 1 and out["events"]
    assert any("mended locally" in w for w in warnings), warnings


def test_a_cut_answer_ending_on_an_inner_object_is_not_the_answer(monkeypatch, warnings):
    """Found live (chat 154's departure, the encoder's interpret answer cut
    at 60%): the cut fell right after one inner object closed, salvage read
    that object as the whole answer, and it validated with ZERO events. The
    cut is the re-ask's, not salvage's."""
    whole = _encoder_answer(GOOD_EVENTS)
    close = whole.index('"relation": "held"}') + len('"relation": "held"}')
    cut = whole[:close]
    fragment = llm_quality.strict_json_parse(cut)
    assert "events" not in fragment      # what salvage alone makes of it
    llm = _Scripted([cut, whole])
    monkeypatch.setattr(llm_quality, "chat_complete", llm)
    monkeypatch.setattr(llm_quality, "role_candidate_count", lambda role: 1)

    out = llm_quality.complete_validated_json(
        role="encoder", step_key="director_specialist", system="THE ENCODER SHEET",
        payload={"prose": "Mara lifts the key."})

    assert len(llm.calls) == 2
    assert out["events"][0]["event"] == "Mara lifts the key"
    assert any("re-asked once" in w for w in warnings), warnings


def test_a_cut_off_encoder_answer_goes_to_the_re_ask_not_the_mend(monkeypatch, warnings):
    cut = _encoder_answer(GOOD_EVENTS)[:-40]
    llm = _Scripted([cut, _encoder_answer(GOOD_EVENTS)])
    monkeypatch.setattr(llm_quality, "chat_complete", llm)
    monkeypatch.setattr(llm_quality, "role_candidate_count", lambda role: 1)
    monkeypatch.setattr(llm_quality, "output_ran_out_of_room", lambda raw: raw == cut)

    out = llm_quality.complete_validated_json(
        role="encoder", step_key="director_specialist", system="THE ENCODER SHEET",
        payload={"prose": "Mara lifts the key."})

    assert len(llm.calls) == 2 and out["events"]
    assert not any("mended locally" in w for w in warnings), warnings
