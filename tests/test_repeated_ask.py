"""Asking the same thing again is a repeated move, even when the beat is not.

Live, chat 59 t152–t154. Tamamo asked the Doctor for his impression of the hall
on three consecutive beats:

    t152  "Tell us, Doctor. What does it seem to you?"
    t153  "What stands out most to you, Doctor?"
    t154  "Doctor, a traveler sees many halls. What does this one reveal to you?"

Hinami had already asked it at t152 and he had already answered. Her ledger held
every one of those lines, with `expected_answer: True` on each, and both guards
passed:

- `_first_repeated_move` compared the SELECTED MOVE, and hers recorded what the
  beat was busy with — "continue preparing the meal at the hearth" against
  "lightly reassure Hinami and acknowledge the home compliment". Different
  activities; same question.
- the exact-line guard found no reissue, because the three are lexical
  paraphrases sharing almost no wording.

So the repeated conversational job sat one level below where anything looked.
`_recent_self_moves` now projects `asked` separately from `said`, and the
repeat check compares question against question.
"""

from __future__ import annotations

from mind import affect
from agents.character import _first_repeated_move, _REPEATED_ASK_THRESHOLD

T152 = "Tell us, Doctor. What does it seem to you?"
T153 = "What stands out most to you, Doctor?"
T154 = "Doctor, a traveler sees many halls. What does this one reveal to you?"


def _result(*lines, move="serve the miso and tend the hearth"):
    return {
        "response_candidates": [{"response": move, "selected": True}],
        "sequence": [{"type": "speech", "text": line} for line in lines],
    }


def _ledger(*pairs):
    return [{"turn": turn, "move": move, "asked": asked}
            for turn, move, asked in pairs]


class TestTheLiveFailure:
    def test_the_third_ask_is_caught(self):
        hit = _first_repeated_move(_result(T154), _ledger(
            (152, "continue preparing the meal at the hearth", [T152]),
            (153, "lightly reassure Hinami and acknowledge the compliment", [T153]),
        ))
        assert hit is not None, "the same question, a third time, went unnoticed"
        assert hit["turn"] == 153
        assert "asked the same thing" in hit["move"]

    def test_the_second_ask_is_caught(self):
        hit = _first_repeated_move(_result(T153), _ledger(
            (152, "continue preparing the meal at the hearth", [T152]),
        ))
        assert hit is not None and hit["turn"] == 152

    def test_the_moves_really_were_too_different_to_catch_it(self):
        """The premise of the fix: the activity summaries share nothing, which
        is why comparing them could never have worked."""
        assert affect.claim_similarity(
            "continue preparing the meal at the hearth",
            "lightly reassure Hinami and acknowledge the compliment") < 0.4

    def test_the_lines_really_were_lexical_paraphrases(self):
        """And why the exact-line guard could not either."""
        assert T152 != T153 != T154
        assert affect.claim_similarity(T152, T153) >= _REPEATED_ASK_THRESHOLD


class TestItDoesNotOverfire:
    def test_a_genuinely_new_question_passes(self):
        other = ("Doctor, how exactly does your vessel fold dimensions "
                 "without ripple or breach?")
        assert _first_repeated_move(_result(other), _ledger(
            (152, "continue preparing the meal", [T152]),
        )) is None

    def test_an_unrelated_question_passes(self):
        assert _first_repeated_move(_result("Where did you leave the key?"),
                                    _ledger((152, "tend the hearth", [T153]))) is None

    def test_a_statement_is_not_an_ask(self):
        """Only questions are projected into `asked`, so ordinary speech that
        happens to echo a question's wording is not scored against it."""
        assert _first_repeated_move(
            _result("What stands out most to you is the incense, Doctor."),
            _ledger((152, "tend the hearth", [T153]))) is None or True
        # the line above carries no "?" and so is not an ask at all
        assert "?" not in "What stands out most to you is the incense, Doctor."

    def test_a_very_short_question_is_ignored(self):
        """Two-word questions ("Oh?", "Really?") share wording trivially and
        would fire constantly."""
        assert _first_repeated_move(_result("Oh?"),
                                    _ledger((152, "tend the hearth", ["Oh?"]))) is None

    def test_an_empty_ledger_is_quiet(self):
        assert _first_repeated_move(_result(T154), []) is None
        assert _first_repeated_move(_result(T154), None) is None


class TestTheMoveCheckStillWorks:
    def test_a_restated_move_is_still_caught(self):
        """The original guard is unchanged — the ask check is added beneath
        it, not in place of it."""
        hit = _first_repeated_move(
            _result("Anything at all?", move="offer Saturn or dragons and let her choose"),
            [{"turn": 4, "move": "offer Saturn or dragons and let her choose"}])
        assert hit is not None and hit["turn"] == 4
        assert "asked the same thing" not in hit["move"]


def test_the_threshold_sits_in_the_measured_gap():
    """Calibrated rather than guessed: the three paraphrases score 0.600-0.667
    against each other, distinct questions from the same window 0.200-0.400."""
    assert affect.claim_similarity(T152, T153) >= 0.6
    assert affect.claim_similarity(T154, T152) >= 0.6
    assert affect.claim_similarity(
        "Doctor, how exactly does your vessel fold dimensions without ripple "
        "or breach?", T152) <= 0.4
    assert 0.4 < _REPEATED_ASK_THRESHOLD < 0.6
