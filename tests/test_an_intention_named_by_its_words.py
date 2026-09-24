"""An op that names its goal by its words is read as that goal.

The character agent names an existing intention by id, and sometimes by its
text instead -- `{"op": "progress", "intent": "..."}`. The kernel check made
that fatal, and it bought a 41 s repair on the owner's chat 137 idx 46, a
94 s one on chat 120 idx 8, and on one replay of that beat the whole turn
(rounds 5-7, 2026-09-23). Commit reads the row by the fold an `add` already
uses to read a rephrased goal as the goal, and drops and says anything it
cannot read.
"""

from __future__ import annotations

from mind import affect


def _ledger(*texts):
    return [{"id": f"ia{n}", "intent": text, "status": "active",
             "progress": 0.2, "last_progress_turn": 1, "formed_turn": 1}
            for n, text in enumerate(texts, start=1)]


def test_a_progress_naming_its_goal_by_its_words_moves_that_goal():
    ledger = _ledger("Get Hinami to relax enough to begin",
                     "Close the shop before the storm breaks")
    out, warnings = affect.apply_intent_ops(
        ledger, [{"op": "progress", "intent": "get Hinami to relax enough to begin",
                  "why": "she breathed out and lay back"}],
        5, lambda op: True)
    assert out[0]["progress"] > 0.2
    assert out[1]["progress"] == 0.2
    assert any("named its goal by text" in w and "'ia1'" in w for w in warnings)
    assert not any("restated text" in w for w in warnings)


def test_words_that_name_nothing_or_two_goals_move_nothing_and_say_so():
    ledger = _ledger("Keep watch on the door", "Keep watch on the door")
    out, warnings = affect.apply_intent_ops(
        ledger, [{"op": "progress", "intent": "Keep watch on the door"},
                 {"op": "progress", "intent": "sail for the southern isles"},
                 {"op": "progress"}],
        5, lambda op: True)
    assert [i["progress"] for i in out] == [0.2, 0.2]
    assert sum("on unknown id" in w for w in warnings) == 3


def test_an_id_still_wins_over_the_words():
    ledger = _ledger("Get Hinami to relax enough to begin",
                     "Close the shop before the storm breaks")
    out, warnings = affect.apply_intent_ops(
        ledger, [{"op": "progress", "id": "ia2",
                  "intent": "Get Hinami to relax enough to begin"}],
        5, lambda op: True)
    assert out[0]["progress"] == 0.2 and out[1]["progress"] > 0.2
    assert any("restated text" in w for w in warnings)
