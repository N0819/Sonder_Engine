"""A repair keeps every answer it was given (`agents/director_repair.py`).

Three ways the pass threw away work it had in hand, found by the audit of
2026-11-01 (`agents_director_floors` F7-F9), each the lesson `merge_answers`
already encodes for the pieces of one answer -- MERGE BY KEY, never pick:

* a job's retry was kept INSTEAD of its first answer or not at all
  (`_fuller`), so a job that declared acts A and B, answered A first and B on
  the retry, kept A alone and then warned "no event carries declared act(s)"
  for the act the repair had produced;
* an answer in two pieces -- a `move_to` and a corrected write -- moved the
  FLAGGED value to the named event and dropped the correction (the card
  makes them alternatives, but 30 of 198 measured runs split an answer);
* one failing repair call (every rung of `complete_validated_json` raising)
  unwound the whole pass, so the other group's answers -- the recovered
  events -- went with it and the beat kept the unrepaired draft.
"""

from __future__ import annotations

import pytest

from agents import director_repair as repair
from llm.providers import Aborted

PROSE = "Ana lifts the latch. The gate creaks. She steps through."
DECLARED = [{"event_id": "t:0:latch", "by": "Ana", "act": "lifts the latch"},
            {"event_id": "t:1:through", "by": "Ana", "act": "steps through"}]
JOB = {"id": "j1", "kind": "event", "sentence": "s1", "sentences": ["s1", "s2", "s3"],
       "declared": DECLARED}


class _Ctx(dict):
    language = "en"

    def __init__(self):
        super().__init__()
        self.warnings = []

    def add_warning(self, text):
        self.warnings.append(text)


def _event(text, act=""):
    return {"source_entity_id": "character:1", "source_event_id": act,
            "event": text, "speech": False, "transforms": []}


def _group(monkeypatch, replies, jobs=(JOB,)):
    monkeypatch.setattr(repair, "repair_tools",
                        lambda *a, **k: (["poses"], [], {}))
    replies = list(replies)

    def call(*a, **k):
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return repair.merge_answers(reply, list(jobs)), []

    monkeypatch.setattr(repair, "call_repair", call)
    units = repair.sentences(PROSE)
    return repair._repair_group(_Ctx(), "resolve", {}, units, [], list(jobs),
                                ["poses"], [], {}, None, None, None, False, None,
                                {"identity_index": {}})


def test_a_retry_adds_the_act_the_first_answer_lacked(monkeypatch):
    first = [{"id": "j1", "after": "", "events": [
        _event("She lifts the latch.", "t:0:latch"), _event("The gate creaks.")]}]
    again = [{"id": "j1", "events": [_event("She steps through.", "t:1:through")]}]
    result = _group(monkeypatch, [first, again])
    (answer,) = [a for a in result["answers"] if a.get("id") == "j1"]
    assert [e["event"] for e in answer["events"]] == [
        "She lifts the latch.", "The gate creaks.", "She steps through."]
    assert result["retried"] == ["j1"]


def test_an_act_the_retry_carries_earlier_goes_before_the_kept_ones(monkeypatch):
    first = [{"id": "j1", "events": [_event("She steps through.", "t:1:through"),
                                     _event("The gate creaks.")]}]
    again = [{"id": "j1", "events": [_event("She lifts the latch.", "t:0:latch")]}]
    result = _group(monkeypatch, [first, again])
    (answer,) = [a for a in result["answers"] if a.get("id") == "j1"]
    assert [e["source_event_id"] for e in answer["events"]] == [
        "t:0:latch", "t:1:through", ""]


def test_a_failed_retry_keeps_the_first_answer(monkeypatch):
    first = [{"id": "j1", "events": [_event("She lifts the latch.", "t:0:latch")]}]
    result = _group(monkeypatch, [first, RuntimeError("every rung failed")])
    (answer,) = [a for a in result["answers"] if a.get("id") == "j1"]
    assert [e["source_event_id"] for e in answer["events"]] == ["t:0:latch"]
    assert result.get("failed")


def test_a_failed_first_call_is_asked_again_and_a_stop_still_stops(monkeypatch):
    again = [{"id": "j1", "events": [_event("She lifts the latch.", "t:0:latch"),
                                     _event("She steps through.", "t:1:through")]}]
    result = _group(monkeypatch, [RuntimeError("every rung failed"), again])
    (answer,) = [a for a in result["answers"] if a.get("id") == "j1"]
    assert len(answer["events"]) == 2
    with pytest.raises(Aborted):
        _group(monkeypatch, [Aborted("user stop")])


def test_a_move_and_a_correction_in_two_pieces_moves_the_correction():
    """The audit's case: the ship's transit `to: beach` was flagged on e1
    and belonged to e2; one piece said `move_to: e2`, the other wrote the
    corrected `to: far_quay`. The move says where, the write says what."""
    draft = [_event("The ship casts off."), _event("It runs north to the far quay.")]
    draft[0]["transforms"] = [{"item": "ship", "patch": {
        "entities": {"ship": {"transit": {"to": "beach"}}}}}]
    job = {"id": "j1", "kind": "fix", "event": "e1", "index": 0, "channel": "entities",
           "write": {"ship": {"transit": {"to": "beach"}}}}
    merged = repair.merge_answers([
        {"id": "j1", "move_to": "e2"},
        {"id": "j1b", "transforms": [{"item": "ship", "patch": {
            "entities": {"ship": {"transit": {"to": "far_quay"}}}}}]}], [job])
    events, report = repair.apply_answers(draft, [], [job], merged, {})
    assert events[0]["transforms"] == []
    assert events[1]["transforms"] == [{"item": "ship", "patch": {
        "entities": {"ship": {"transit": {"to": "far_quay"}}}}}]
    assert report["applied"] == ["j1"]


def test_one_group_failing_keeps_the_other_groups_answers(monkeypatch):
    """The two groups run in parallel: the recovered events must not go
    with a fix group whose call failed."""
    from llm import decisions
    monkeypatch.setattr(decisions, "OVERRIDE", lambda state, q: {
        key: {"type": "noul", "noul": 0.02} for key in q})
    units = repair.sentences(PROSE)
    draft = [_event("Ana lifts the latch.", "t:0:latch")]
    draft[0]["transforms"] = [{"item": "Ana", "patch": {"poses": {"Ana": {"posture": "x"}}}}]
    jobs = [{"id": "j1", "kind": "event", "sentence": "s3", "sentences": ["s3"],
             "declared": [DECLARED[1]]},
            {"id": "j2", "kind": "fix", "event": "e1", "index": 0, "channel": "poses",
             "write": {"Ana": {"posture": "x"}}}]
    monkeypatch.setattr(repair, "plan_jobs", lambda *a, **k: jobs)
    monkeypatch.setattr(repair, "native_failures", lambda *a, **k: [])
    monkeypatch.setattr(repair, "repair_tools", lambda *a, **k: (["poses"], [], {}))
    monkeypatch.setattr(repair, "place", lambda ctx, units, events, groups: (
        {job_id: 0 for job_id in groups}, {}))

    def call(ctx, sc, units, events, jobs_, *a, **k):
        if jobs_[0]["kind"] == "fix":
            raise RuntimeError("every rung failed")
        return [{"id": "j1", "events": [_event("She steps through.", "t:1:through")]}], []

    monkeypatch.setattr(repair, "call_repair", call)
    ctx = _Ctx()
    events, record = repair.check_and_repair(
        ctx, "resolve", {}, units, draft, ["poses"], [], {}, None, None,
        base_payload={"identity_index": {}})
    assert "failed" not in record
    assert [e["source_event_id"] for e in events] == ["t:0:latch", "t:1:through"]
    assert any("every rung failed" in w for w in ctx.warnings)
