"""A decision the model left unanswered is unanswered -- never a confident "no".

The decision model answers each keyed question of a request on its own, and an
answer can come back without a key the request asked (models split and drop
keys: "first-wins binding dropped 192 of 844 repair events"). Read through
`.get("yes", 0.0)`, a missing key is a certain no. Where that only means one
action fewer -- a memory not disputed, a line not taken for a question, a link
not formed -- it is the same branch a request that could not be asked takes,
and it stays. Where the ORDER of the answers is the question, it is not the
same (review 2026-11-01, the decisions `missing key -> 0.0` class,
llm_schemas_prompts F7, on the mind side):

* the routed "first time" walk takes the FIRST row the model is sure of, in
  time order (`memory_routes._first_sure`): an earlier row left unanswered
  read as "no", the walk went on, and a later moment was marked as the first
  -- the wrong mark the walk's own comments call worse than none ("a wrong
  mark points a mind away from what it holds");
* the surest-row pick (`_surest`) chose among the rows that were answered as
  if they were all there were.

Unanswered, the routed search now finds nothing and the graded ponder stands,
which is what a router or search that cannot finish already does.
"""

from __future__ import annotations

from mind import character_jev as jev
from mind import memory_routes


def _yes(p):
    return {"probabilities": {"yes": p, "no": 1.0 - p}}


def test_a_missing_key_reads_as_unanswered():
    answers = {"moment:1": _yes(0.9), "moment:2": {"probabilities": {}}}
    assert jev.yes_share(answers, "moment:0") is None
    assert jev.yes_share(answers, "moment:2") is None
    assert jev.yes_share(answers, "moment:1") == 0.9
    assert jev.yes_share({"k": {"probabilities": {"no": 1.0}}}, "k") == 0.0


def test_a_first_time_walk_never_steps_past_an_unanswered_row(monkeypatch):
    rows = [{"id": 1, "turn_idx": 3, "content": "The first crossing with Oren."},
            {"id": 2, "turn_idx": 9, "content": "Crossing again with Oren."}]
    monkeypatch.setattr(jev, "ask", lambda state, qs: {"moment:1": _yes(0.97)})
    record = {}
    shares = memory_routes._yes_shares(rows, "memory_moment", "STATE", 20, set(), None, record)
    assert shares == [None, 0.97]
    assert memory_routes._first_sure(rows, shares) is None, \
        "row 1 may be the first time; the walk cannot say row 2 is"
    assert record.get("unanswered") == 1


def test_a_walk_answered_in_full_reads_as_before():
    rows = [{"id": 1, "turn_idx": 3}, {"id": 2, "turn_idx": 9}]
    assert memory_routes._first_sure(rows, [0.1, 0.97]) == rows[1]
    assert memory_routes._first_sure(rows, [0.97, None]) == rows[0], \
        "an unanswered row AFTER the first sure one changes nothing"


def test_the_surest_is_not_chosen_from_a_partial_answer():
    rows = [{"id": 1, "turn_idx": 3}, {"id": 2, "turn_idx": 40}]
    assert memory_routes._surest(rows, [None, 0.9]) == (None, 0.0)
    assert memory_routes._surest(rows, [0.2, 0.9])[0] == rows[1]
