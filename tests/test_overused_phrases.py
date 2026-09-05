"""The anti-repetition channel: what the narrator is told it overused.

Two findings from campaign 3 (2026-09-05C), both about the same list.

`quiet` turn 20 (PQ8): `overused_phrases` was
`["through the doorway", "toward the kitchen", "though there was", "was too
little", "there was too", "empty in the", "to make out", "he said in", "in a
flat", "said in a"]` -- seven of ten overlapping thirds of ONE phrase, "there
was too little to make out", which the narrator was paraphrasing because the
composed view said "Tobin Renn moves, too little of it to make out" on every
single beat. The window is fixed at three words, so the containment filter
that was meant to prefer whole phrases could never fire.

`multitude` turn 3 (PM18): `overused_phrases: ["bench ilsabet roon", "corin
ashe froze", "out on the"]`. The first spans the comma in "Behind the bench,
Ilsabet Roon...", and both of the first two ask the narrator to stop naming
the people in the room -- in a run that also fired two `Proper noun from view
missing in narrator prose` warnings.

Fast tier: no database, no model.
"""

from __future__ import annotations

from agents.common import _overused_phrases, _phrase_ngrams


def test_overlapping_windows_are_reported_as_the_phrase_they_came_from():
    """PQ8: one recurring sentence must cost one slot, not seven."""
    blocks = [
        "Close on her left, Tobin moved, though there was too little to "
        "make out.",
        "On her right, Tobin moved, though there was too little to make out.",
        "Tobin moved again, though there was too little to make out.",
    ]
    over = _overused_phrases(blocks)
    assert over == ["though there was too little to make out"]


def test_no_phrase_spans_a_punctuation_boundary():
    """PM18: "bench ilsabet roon" is two half-phrases welded at a comma."""
    assert "bench ilsabet" not in " | ".join(
        _phrase_ngrams("Behind the bench, Ilsabet Roon stood.", 3))
    assert "the bench" in " | ".join(
        _phrase_ngrams("Behind the bench, Ilsabet Roon stood.", 3))


def test_a_name_is_not_a_tic():
    """PM18: with six named bodies the frequent runs are name-adjacent, and
    the channel ends up asking the narrator to stop naming the room."""
    blocks = [
        "Behind the bench, Ilsabet Roon stood. Corin Ashe froze out on the "
        "step.",
        "Behind the bench, Ilsabet Roon stood again. Corin Ashe froze out on "
        "the step.",
    ]
    over = _overused_phrases(blocks)
    joined = " | ".join(over)
    for name in ("ilsabet", "roon", "corin", "ashe"):
        assert name not in joined, over
    # And the genuine tics still land.
    assert "behind the bench" in over
    assert any("froze out on the step" in phrase for phrase in over), over


def test_a_capital_a_sentence_explains_is_not_a_name():
    """The complement: "The" opening a sentence is capitalised because the
    sentence started, so a tic that begins one is still a tic."""
    blocks = ["The clock ticks. The fire settles.",
              "The clock ticks again.",
              "He waits. The clock ticks on."]
    assert "the clock ticks" in _overused_phrases(blocks)
