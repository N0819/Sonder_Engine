"""Half-hearing is typeset by the language, in both places it happens.

`_muffled_fragment` (the composer's) and `_muffle_middle` (the interaction
loop's) already share `_muffle_tokens`, so there is one rule for WHAT survives
a muffled line. How the survivors are set out was two rules: the composer
reads the pack's `muffle_join`, and the loop joined with a hardcoded ASCII
space -- so a Japanese story got 「小瓶 捨」 where every other muffled line in
the same story reads 「……小瓶……捨……」.

A separator is not punctuation-flavoured decoration: Japanese sets an ellipsis
as the doubled three-dot leader with no spaces, and a half-width gap between
two kanji runs reads as broken typesetting rather than as a gap in hearing.
"""

from __future__ import annotations

import pytest

from language_runtime import compositor_value, language_scope

from agents.common import _muffle_middle, _muffled_fragment


LINES = {
    "en": "the ledger is going to sink you",
    "ja": "棚の上の小瓶を捨てろ",
}


@pytest.mark.parametrize("language_id", sorted(LINES))
def test_the_loop_muffler_joins_the_way_its_pack_does(language_id):
    with language_scope(language_id):
        join = str(compositor_value("muffle_join"))
        fragment = _muffle_middle(LINES[language_id])
    assert join in fragment, (language_id, fragment)


@pytest.mark.parametrize("language_id", sorted(LINES))
def test_both_mufflers_use_the_same_separator(language_id):
    """One feature, one typesetting rule -- the property the shared
    `_muffle_tokens` was introduced for, applied to the rendering half."""
    with language_scope(language_id):
        join = str(compositor_value("muffle_join"))
        assert join in _muffled_fragment(LINES[language_id])
        assert join in _muffle_middle(LINES[language_id])


def test_an_unspaced_script_gets_no_spaces_from_the_engine():
    """The concrete wrong output: a half-width gap between two kanji runs."""
    with language_scope("ja"):
        assert " " not in _muffle_middle(LINES["ja"])
