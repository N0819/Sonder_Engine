"""Sentence dedupe may not reach inside a delivered quotation.

`_dedupe_view_sentences` has always documented "sentences containing quoted
dialogue are never dropped -- quotes must survive verbatim (dialogue
fidelity)". That guard was defeated by the sentence splitter: the check is
per-SENTENCE, and a spoken line carrying its own terminal punctuation is cut
into several fragments. Only the two on the ends keep a quote mark; every
fragment between them is judged naked and dropped if it echoes anything earlier
in the view.

Live, chat 58 "Run! ⎇10 ⎇20" t30. The player answered a direct question with
"Seven? I think? There might have been more... they began to spread out..." --
four terminators, so four fragments. This function runs LAST in
`perception_act`, after the deterministic delivery, and ate the interior of the
quotation. The Doctor then asked "How many? Where exactly?" -- the question that
had just been answered.

That is the worst place for it to happen: `perception_act` is the view a
character DECIDES from, so unlike a narrator-side drop nothing is visible in
play. It surfaces only as a character answering something nobody asked, which
reads like a model failure.

The fix masks quoted spans into opaque tokens before splitting, so a quotation
cannot be cut apart in the first place.
"""

from __future__ import annotations

import pytest

from agents.common import (
    _dedupe_view_sentences,
    _mask_quoted_spans,
    _unmask_quoted_spans,
)

LINE = "Seven? I think? There might have been more... they began to spread out..."


def test_the_live_failure_the_quote_survives_verbatim():
    view = ("The air hums with energy and the whole chamber vibrates faintly. "
            "I think? There might have been more... "
            f'Hinami says: "{LINE}"')
    out = _dedupe_view_sentences(view)
    assert LINE in out, "dedupe edited the inside of a delivered quotation"


def test_the_echoed_unquoted_prose_is_still_deduped():
    """The function still does its job on ordinary prose: only the quotation is
    protected, not everything near it."""
    view = ("The console room hums with a steady mechanical breath. "
            "The console room hums with a steady mechanical breath. "
            f'Hinami says: "{LINE}"')
    out = _dedupe_view_sentences(view)
    assert out.count("The console room hums with a steady mechanical breath.") == 1
    assert LINE in out


def test_a_quote_repeated_on_purpose_is_kept_twice():
    """A character really can say the same thing twice, and each delivery is a
    separate fact about the beat."""
    view = (f'Mara says: "{LINE}" '
            f'Mara says it again, louder: "{LINE}"')
    out = _dedupe_view_sentences(view)
    assert out.count(LINE) == 2


def test_an_unterminated_quote_is_still_protected():
    """The span regex cannot match a quote with no closing mark, so the raw
    quote-character check stays alongside the mask for exactly this case."""
    view = ('The lamp gutters in the draft from the door. '
            'The lamp gutters in the draft from the door. '
            'She starts to say "I never meant for any of it')
    out = _dedupe_view_sentences(view)
    assert 'I never meant for any of it' in out
    assert out.count("The lamp gutters in the draft from the door.") == 1


def test_single_quoted_spans_are_protected_too():
    line = "Seven? I think? Maybe more."
    view = (f"I think? Maybe more. Mara says: '{line}'")
    assert line in _dedupe_view_sentences(view)


def test_an_apostrophe_is_not_read_as_a_quote():
    view = ("The Doctor's coat is soaked through and dripping. "
            "The Doctor's coat is soaked through and dripping. "
            "Rain runs off the console housing.")
    out = _dedupe_view_sentences(view)
    assert out.count("The Doctor's coat is soaked through and dripping.") == 1


def test_unchanged_text_is_returned_as_the_same_object():
    view = f'A quiet room. Mara says: "{LINE}"'
    assert _dedupe_view_sentences(view) is view


def test_masking_round_trips_exactly():
    view = f'She waits. Mara says: "{LINE}" Then silence.'
    masked, spans = _mask_quoted_spans(view)
    assert LINE not in masked            # the quote is opaque while split
    assert "?" not in masked.split("Mara says:")[1].split("Then")[0]
    assert _unmask_quoted_spans(masked, spans) == view


def test_no_quotes_at_all_behaves_as_before():
    view = ("She crosses the yard and opens the gate. "
            "She crosses the yard and opens the gate. "
            "Rain beads on the latch.")
    out = _dedupe_view_sentences(view)
    assert out.count("She crosses the yard and opens the gate.") == 1
    assert "Rain beads on the latch." in out


def test_empty_and_blank_are_noops():
    assert _dedupe_view_sentences("") == ""
    assert _dedupe_view_sentences("   ") == "   "
    assert _dedupe_view_sentences(None) == ""
