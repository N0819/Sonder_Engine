"""Within-view dedupe (W12): the same sentence must not be rendered twice in
one turn's view/prose (Enterprise-D turn 7 rendered "Picard turns his head
slightly toward Troi" twice in a single beat). The pass is deterministic and
deliberately conservative -- quoted dialogue and short sentences are exempt,
and only exact normalized repeats are dropped.

Applied at every perception view's final assembly (perception_establish /
perception_act / perception_outcome, including the interaction-loop
micro-view merge) and to the narrator's final prose.
"""

from agents.common import _dedupe_view_sentences


def test_duplicate_sentence_dropped_first_kept():
    text = ("Picard turns his head slightly toward Troi. A flicker of anxiety "
            "crosses her face. Picard turns his head slightly toward Troi.")
    out = _dedupe_view_sentences(text)
    assert out.count("Picard turns his head slightly toward Troi") == 1
    assert "A flicker of anxiety crosses her face." in out
    # First occurrence survives -- the text still LEADS with it.
    assert out.startswith("Picard turns his head slightly toward Troi.")


def test_match_is_case_whitespace_and_terminal_punctuation_insensitive():
    text = ("The bridge hums with quiet tension around you. "
            "the bridge   hums with quiet tension around you!")
    out = _dedupe_view_sentences(text)
    assert out == "The bridge hums with quiet tension around you."


def test_short_intentional_repetition_survives():
    text = "No. No. The turbolift doors stay shut against your palm."
    assert _dedupe_view_sentences(text) == text


def test_quoted_dialogue_is_never_dropped():
    # A character repeating a line on purpose is legitimate, and dialogue
    # fidelity requires quotes to survive verbatim.
    text = ('"Stand down, all of you, right now." He waits a long moment. '
            '"Stand down, all of you, right now."')
    assert _dedupe_view_sentences(text) == text


def test_sentence_punctuation_inside_a_quote_does_not_eat_content():
    # The splitter mis-splits inside a quote body, but every fragment carries
    # a quote character and is exempt -- mis-splits can only under-dedupe.
    text = ('Data says: "The core log is at eighty-seven percent. Analysis '
            'will follow." Vorne watches the viewscreen without moving.')
    assert _dedupe_view_sentences(text) == text


def test_unique_text_returned_unchanged():
    text = ("You are on the bridge. Riker leans over the tactical rail. "
            "Worf checks his console twice.")
    assert _dedupe_view_sentences(text) is text


def test_duplicate_across_paragraphs_dropped_and_structure_kept():
    text = ("A muscle jumps beneath the skin of his jaw as he reads.\n\n"
            "Vale steps closer to the science station display.\n\n"
            "A muscle jumps beneath the skin of his jaw as he reads.")
    out = _dedupe_view_sentences(text)
    assert out.count("A muscle jumps beneath the skin") == 1
    assert "Vale steps closer to the science station display." in out
    assert "\n\n" in out


def test_empty_and_none_are_safe():
    assert _dedupe_view_sentences("") == ""
    assert _dedupe_view_sentences(None) == ""


def test_triple_repeat_collapses_to_one():
    text = ("The red alert klaxon pulses along the corridor wall. " * 3).strip()
    out = _dedupe_view_sentences(text)
    assert out == "The red alert klaxon pulses along the corridor wall."
