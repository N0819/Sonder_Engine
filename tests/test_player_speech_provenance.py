"""Regression tests for the player-speech provenance floor.

`discard_unanchored_player_speech` exists so a model cannot put words in the
player's mouth: an interpret result may carry an exact player line only when
the player actually wrote those words. It enforced that by asking whether the
line was a CONTIGUOUS run of the raw input, and that question has a wrong
answer for the ordinary way a turn is written.

Measured (15-beat run, the beat whose question no character ever answered): the
player wrote two quoted spans with narration between them, interpret correctly
merged them into one `speech` element, and the merge -- being a run of neither
span alone -- was dropped whole, nulling `out["speech"]`. The question reached
no mind. A neighbouring beat whose speech happened to be one unbroken quote
survived and was answered. That was the entire difference.

The floor is now COVERAGE: a line is the player's when its words can be read
off the input's quoted spans, in the order written. Both halves are tested
here, because a provenance guard that stops refusing invented speech has not
been fixed, it has been deleted.
"""

import pytest

from agents.common import (
    discard_unanchored_player_speech,
    player_speech_anchored,
)


# The shape under test: quoted speech, narration, more quoted speech. No story
# noun -- this is how anyone writes a turn.
TWO_SPAN_INPUT = (
    '"What is our current heading?" I lean over the console and tap the '
    'display, waiting. "And how long until we are clear?"'
)
MERGED_LINE = "What is our current heading? And how long until we are clear?"


def _interpreted(line):
    """One interpret result carrying `line` in both representations."""
    return {"sequence": [{"type": "speech", "text": line}], "speech": line}


# ---- half one: the player's own words must survive -------------------------

def test_merged_quoted_spans_survive_the_provenance_floor():
    # The merge is a contiguous run of neither span, so this cannot pass on
    # the containment path -- it is the shape the substring rule dropped.
    assert MERGED_LINE.casefold() not in TWO_SPAN_INPUT.casefold()
    out = _interpreted(MERGED_LINE)

    assert discard_unanchored_player_speech(out, TWO_SPAN_INPUT) == []
    assert out["speech"] == MERGED_LINE
    assert [event["type"] for event in out["sequence"]] == ["speech"]


def test_each_span_alone_is_anchored_too():
    """The predicate that was already true per span stays true per span."""
    for span in ("What is our current heading?",
                 "And how long until we are clear?"):
        assert player_speech_anchored(span, TWO_SPAN_INPUT)


def test_three_spans_merge_across_two_narration_clauses():
    raw = ('"Hold." I raise a hand. "Say that again." She waits. '
           '"Slowly this time."')
    assert player_speech_anchored("Hold. Say that again. Slowly this time.",
                                  raw)


def test_a_span_may_be_trimmed_but_not_reassembled():
    """Interpret may drop a trailing span; it may not stitch one back up."""
    raw = '"Open the outer door." I step back. "Then seal it behind me."'
    assert player_speech_anchored("Open the outer door.", raw)
    # Words from inside one span, rejoined across a hole it left behind.
    assert not player_speech_anchored("Open the door.", raw)


def test_contiguous_single_quote_still_survives():
    out = _interpreted("Hold still, please.")
    assert discard_unanchored_player_speech(
        out, 'I say, "Hold still, please."') == []
    assert out["speech"] == "Hold still, please."


def test_corner_bracket_spans_merge_in_a_pack_that_uses_them():
    """The quote vocabulary is the language pack's, not a literal."""
    from language_runtime import language_scope

    raw = "「聞こえるか」私は身を乗り出した。「返事をしてくれ」"
    with language_scope("ja"):
        assert player_speech_anchored("聞こえるか。返事をしてくれ", raw)
        assert not player_speech_anchored("扉を開けてくれ", raw)


# ---- half two: invented speech must still be dropped -----------------------

def test_invented_line_is_dropped_though_the_input_quotes():
    out = _interpreted("Prepare to abandon the station.")

    dropped = discard_unanchored_player_speech(out, TWO_SPAN_INPUT)

    assert dropped == ["Prepare to abandon the station."]
    assert out["speech"] is None
    assert out["sequence"] == []


def test_a_merge_with_one_invented_clause_is_dropped_whole():
    invented = MERGED_LINE + " Prepare to abandon the station."
    out = _interpreted(invented)

    assert discard_unanchored_player_speech(out, TWO_SPAN_INPUT) == [invented]
    assert out["speech"] is None


def test_spans_reordered_are_not_the_line_the_player_wrote():
    reordered = ("And how long until we are clear? "
                 "What is our current heading?")
    assert not player_speech_anchored(reordered, TWO_SPAN_INPUT)


def test_narration_between_the_spans_anchors_nothing():
    """The prose around a quote is not speech, so it cannot cover speech.

    This is the failure `repair_narrated_speech` addresses upstream; the
    provenance floor must not start waving it through because every character
    of it appears somewhere in the input.
    """
    swallowed = (
        "What is our current heading? I lean over the console and tap the "
        "display, waiting. And how long until we are clear?")
    assert not player_speech_anchored(swallowed, TWO_SPAN_INPUT)


def test_described_speech_still_cannot_become_exact_words():
    out = {
        "sequence": [
            {"type": "action", "attempt": "apply a dressing"},
            {"type": "speech", "text": "Watch for redness or fever."},
        ],
        "speech": "Watch for redness or fever.",
    }

    dropped = discard_unanchored_player_speech(
        out, "I apply a dressing and explain the infection warning signs.")

    assert dropped == ["Watch for redness or fever."]
    assert out["speech"] is None
    assert [event["type"] for event in out["sequence"]] == ["action"]


def test_an_input_with_no_quotes_grants_no_spans():
    raw = "I ask the duty officer for our heading and our time to clear."
    assert not player_speech_anchored("What is our heading? Are we clear?",
                                      raw)


# ---- totality --------------------------------------------------------------

@pytest.mark.parametrize("junk", [None, "", "   ", 17, {"text": "x"}])
def test_empty_or_malformed_lines_are_not_refused(junk):
    """An empty line is not an invention; refusing it would drop a shape the
    guard never owned."""
    assert player_speech_anchored(junk if isinstance(junk, str) else "", "")


def test_guard_is_total_on_malformed_results():
    assert discard_unanchored_player_speech(None, "anything") == []
    assert discard_unanchored_player_speech({}, "anything") == []
    out = {"sequence": [{"type": "speech"}, "not a dict"], "speech": ""}
    assert discard_unanchored_player_speech(out, "") == []


def test_a_long_line_does_not_hang_the_search():
    """Coverage is bounded: recursion consumes a span per step, and an
    implausibly long line is refused rather than searched."""
    raw = " ".join('"span %d words here"' % i for i in range(40))
    line = " ".join("span %d words here" % i for i in range(40))
    assert player_speech_anchored(line, raw)
    assert not player_speech_anchored(line + " x" * 4000, raw)
