"""Cutting the player's line out of a sentence must leave a sentence.

`_strip_player_echo` removes the player's own declared speech from narrator
prose -- the narrator is not meant to echo it back. The removal is span-level,
and the heal that tidied up after it only fired where the stranded speech verb
ENDED the sentence. A mid-sentence attribution is the ordinary way to write
one, so the case it did not cover was the common case.

Live, chat 76 turn 73. The narrator wrote a well-formed sentence; this
function took the quote out of the middle of it and put a lowercase fragment
on the page:

    '"How long have you been waiting?" you ask, your voice clear over the
     fading hum of the ventilation.'
        -> 'you ask, your voice clear over the fading hum of the ventilation.'

Two neighbours were wrong in the same seam and had never been caught, because
the only shape under test was the one the heal handled:

    '"Q?" you ask.'            -> 'you ask it..'      the heal appended a stop
                                                      without consuming the one
                                                      already there
    'You ask, "Q?", quietly.'  -> 'You ask,, quietly.' the commas on both sides
                                                      of the quote survived it

The model was not at fault for any of the three.
"""

from __future__ import annotations

from agents.common import _strip_player_echo

LINE = "How long have you been waiting?"


def _strip(prose, lines=None):
    return _strip_player_echo(prose, lines if lines is not None else [LINE])


# -- the three shapes a cut leaves ------------------------------------------

def test_a_mid_sentence_attribution_keeps_its_sentence():
    """THE regression. The attribution carries a free modifier after it, so
    the sentence must continue, not end."""
    out = _strip(f'"{LINE}" you ask, your voice clear over the fading hum.')
    assert out == "You ask it, your voice clear over the fading hum.", out


def test_a_sentence_final_attribution_does_not_double_its_full_stop():
    out = _strip(f'"{LINE}" you ask.')
    assert out == "You ask it.", out
    assert ".." not in out


def test_an_attribution_before_the_quote_does_not_double_its_comma():
    out = _strip(f'You ask, "{LINE}", your voice clear.')
    assert ",," not in out
    assert out == "You ask it, your voice clear.", out


def test_a_paragraph_that_began_with_the_quote_is_recapitalised():
    """The cut takes the head off a sentence; nothing else in the function can
    see that, and a lowercase paragraph start is the last visible seam."""
    out = _strip(f'The room stills.\n\n"{LINE}" you ask, quietly.')
    assert out.split("\n")[-1].startswith("You ask it,"), out


# -- and it must not damage anything it did not cut -------------------------

def test_prose_without_the_player_line_is_untouched():
    prose = ("The latch does not give. “Leave it,” Vessel says, "
             "already turning away.")
    assert _strip(prose) == prose


def test_an_npc_line_that_merely_resembles_the_player_is_protected():
    """`protect_quotes` masks a non-player quote out of reach for the strip;
    the heal must not reach it either."""
    prose = f'“{LINE}” Vessel asks, and waits.'
    out = _strip_player_echo(prose, [LINE], protect_quotes=[LINE])
    assert LINE in out, out


def test_paragraph_breaks_survive_the_heal():
    """The whitespace collapse here once ate every paragraph break in the
    story; the heal must not reintroduce that."""
    out = _strip(f'The room stills.\n\n"{LINE}" you ask.\n\nNothing answers.')
    assert out.count("\n\n") == 2, repr(out)


def test_an_already_capital_start_is_left_alone():
    prose = "You ask it, your voice clear."
    assert _strip(prose, lines=[]) == prose


def test_a_verb_that_is_not_an_attribution_is_not_given_an_object():
    """`ask` is a speech cue; `asks after` and ordinary verbs are not the
    target. Nothing may be healed where nothing was cut."""
    prose = "You cross to the window and test the latch."
    assert _strip(prose, lines=[]) == prose
