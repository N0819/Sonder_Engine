"""Deterministic narration-hygiene fixes from the Fable adversarial review.

A2 (empty-quote debris): stripping a player echo could leave a bare '' pair
(Fable, DW t12: "I can't hold her eyes. ''").
A4 (overused phrases): the narrator leaned on the same set-dressing across turns
("the clock ticks" ×7, "thumps her tail once" ×5 verbatim in a 10-turn run);
its own recurring phrases are now fed back as a ban list.
"""

from __future__ import annotations

from agents.common import (
    _strip_player_echo, _collapse_empty_quote_debris, _overused_phrases,
)


# ---- A2: empty-quote debris ----

def test_bare_empty_quote_pair_is_collapsed():
    assert _collapse_empty_quote_debris("I can't hold her eyes. ''").strip() \
        == "I can't hold her eyes."
    assert "''" not in _collapse_empty_quote_debris('The hum wavers. ""')
    assert "“”" not in _collapse_empty_quote_debris("She turned. “” The rain fell.")


def test_real_quoted_dialogue_survives_debris_collapse():
    prose = 'She said, "Stop." He froze.'
    assert _collapse_empty_quote_debris(prose) == prose


def test_strip_leaves_no_empty_pair_when_a_whole_quote_is_removed():
    # A player line rendered as the ONLY content of a quote, then stripped.
    prose = 'The hum wavers, the wrong note lingering. \'\''
    assert "''" not in _strip_player_echo(prose, ["irrelevant"])


# ---- A4: overused-phrase detection ----

RECENT = [
    "The clock ticks. The fire settles. Nell thumps her tail once by the fender.",
    "The clock ticks again in the quiet. Nell thumps her tail once and sleeps.",
    "He speaks at last. The clock ticks through the silence.",
]


def test_recurring_set_dressing_is_flagged():
    over = _overused_phrases(RECENT)
    assert "the clock ticks" in over
    assert any("thumps her tail" in p for p in over)


def test_a_one_off_phrase_is_not_flagged():
    over = _overused_phrases([
        "The candle gutters once.",
        "Rain on the black glass.",
        "He looked away.",
    ])
    assert over == []


def test_pure_function_word_runs_are_not_flagged():
    # A phrase of ONLY stopwords ("was in the", "and then he") is not a tic and
    # must never be flagged, however often it recurs.
    over = _overused_phrases([
        "He was in the and.", "She was in the and.", "It was in the and.",
    ])
    assert "was in the" not in over
    # But a phrase carrying a content word ("room") IS a legitimate tic.
    over2 = _overused_phrases([
        "He was in the room.", "She was in the room.", "It was in the room.",
    ])
    assert "in the room" in over2


def test_within_block_repeat_is_not_double_counted():
    # "the clock ticks" twice in ONE block, once elsewhere -> 2 blocks, flagged.
    over = _overused_phrases([
        "The clock ticks. The clock ticks. The clock ticks.",
        "The clock ticks once more.",
    ])
    assert "the clock ticks" in over
    # But a phrase in only ONE block (however many times) is not overused.
    single = _overused_phrases([
        "The owl hoots. The owl hoots. The owl hoots.",
        "Silence.",
    ])
    assert "the owl hoots" not in single


def test_empty_or_short_history_yields_nothing():
    assert _overused_phrases([]) == []
    assert _overused_phrases(["one block only, nothing to compare"]) == []
