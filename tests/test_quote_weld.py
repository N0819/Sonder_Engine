"""Empty-quote debris collapse must never join two quoted spans.

`_EMPTY_QUOTE_RE` exists to remove an orphan pair of quote marks with NOTHING
between them, left where a stripped line used to sit. Two of its alternatives
were `"\\s*"` and `'\\s*'`, which accept any two marks separated only by
whitespace -- and `\\s` matches a newline, so the pair could span a paragraph
break.

That is exactly the shape of two consecutive speakers once
`narration._substitute_dialogue_tokens` has wrapped each delivered line in its
own straight quotes: one line's close-quote, the break, the next line's
open-quote. `_collapse_empty_quote_debris` deleted both marks and put a space
in their place, welding one speaker's line and another's reply into a single
quoted string attributed to one voice -- and it is called unconditionally by
`_strip_player_echo`, so no player line and no removal were needed to trigger
it. Measured on a 15-beat run: the model's own output (`{{L2}}</p><p>{{L3}}`)
and the dialogue_log record were both correct; only the rendered page was
wrong.

These are the class, not the case: any two speakers, any pack, any quote pair.
"""

from __future__ import annotations

import re

import pytest

from agents.common import _collapse_empty_quote_debris, _strip_player_echo
from language_runtime import installed_language_packs, linguistic


#: Two delivered lines, each in its own paragraph and its own quote marks --
#: what `_substitute_dialogue_tokens` produces from `{{L1}}</p><p>{{L2}}`.
TWO_SPEAKERS = (
    'The first one straightens.\n\n'
    '"Say it again."\n\n'
    '"I will not," the second answers.'
)


def _quote_marks(text):
    return re.findall(r'["\'“”‘’]', text)


def test_two_speakers_across_a_paragraph_break_keep_their_own_quotes():
    assert _collapse_empty_quote_debris(TWO_SPEAKERS) == TWO_SPEAKERS


def test_the_echo_strip_does_not_weld_when_it_strips_nothing():
    """The collapse runs unconditionally, so a beat where the player declared
    no speech at all still went through it."""
    assert _strip_player_echo(TWO_SPEAKERS, []) == TWO_SPEAKERS


def test_two_speakers_survive_a_real_player_echo_removal():
    prose = (
        '"Hold there," you say.\n\n'
        '"Say it again."\n\n'
        '"I will not," the second answers.'
    )
    out = _strip_player_echo(prose, ["Hold there,"])
    assert "Hold there" not in out
    # Both remaining lines still carry an opening AND a closing mark.
    assert out.count('"') == 4, out
    assert '"Say it again."' in out, out
    assert '"I will not,"' in out, out


def test_two_quoted_spans_separated_by_a_space_keep_their_marks():
    """A newline is the measured case; a plain space is the same defect."""
    prose = 'She reads it aloud. "Say it again." "I will not."'
    assert _collapse_empty_quote_debris(prose) == prose


@pytest.mark.parametrize("pair", ["''", '""', "“”", "‘’"])
def test_a_genuinely_empty_pair_is_still_collapsed(pair):
    """The documented referent -- zero characters between the marks -- must
    keep being removed. (Fable review, DW t12.)"""
    out = _collapse_empty_quote_debris("The room settles. %s" % pair)
    assert not _quote_marks(out), out


def test_an_empty_pair_between_two_speakers_is_collapsed_without_welding():
    prose = 'A. ""\n\n"Say it again."\n\n"I will not."'
    out = _collapse_empty_quote_debris(prose)
    assert out.count('"') == 4, out
    assert '"Say it again."' in out and '"I will not."' in out, out


@pytest.mark.parametrize("language_id", sorted(installed_language_packs()))
def test_no_pack_treats_a_gap_between_marks_as_an_empty_pair(language_id):
    """The `ja` pattern was a byte-for-byte copy of the `en` one, and any
    future pack seeded from English inherits the shape. The invariant belongs
    to every pack: an empty pair has ZERO characters between its marks, so
    collapsing debris can never join two quoted spans."""
    pattern = linguistic("agents.common", "_EMPTY_QUOTE_RE", language_id)
    pairs = linguistic("agents.common", "_QUOTE_PAIRS", language_id)
    for open_mark, close_mark in pairs:
        for gap in (" ", "\n\n", "\t", "　"):
            probe = "%sone%s%s%stwo%s" % (
                open_mark, close_mark, gap, open_mark, close_mark)
            assert pattern.sub(" ", probe) == probe, (language_id, repr(probe))
