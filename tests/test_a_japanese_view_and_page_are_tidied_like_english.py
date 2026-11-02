"""Two tidying passes measured their unit in whitespace, so in Japanese they
never ran (agents_common audit F14's table):

* `_dedupe_view_sentences` split sentences on ASCII `.!?` + whitespace and
  floored a droppable sentence at five `.split()` words, so a Japanese view --
  whose sentences end in 。 with nothing after it -- was ONE sentence and a
  repeated sentence was never dropped;
* `_strip_player_echo`'s tidied-echo pass floored the player's line at three
  `.split()` words, so a Japanese line the narrator re-punctuated was always
  "one word" and its echo stayed on the page.

Each now counts in the text's own script: an unspaced sentence ends at its
own stop, and an unspaced line is measured in the A2 unit
(`_countable_word_units`, one per character) that every other "long enough
to be an utterance" floor in these files uses. English is byte-identical.
"""

from __future__ import annotations

from language_runtime import language_scope

from agents.common import _dedupe_view_sentences, _strip_player_echo


def test_a_repeated_japanese_sentence_is_dropped_once():
    view = ("扉がゆっくりと開いていく。廊下の奥で灯りが揺れている。"
            "扉がゆっくりと開いていく。")
    with language_scope("ja"):
        out = _dedupe_view_sentences(view)
    assert out == "扉がゆっくりと開いていく。廊下の奥で灯りが揺れている。", out


def test_a_short_japanese_beat_and_a_quote_are_kept():
    with language_scope("ja"):
        short = _dedupe_view_sentences("いいえ。いいえ。")
        quoted = _dedupe_view_sentences(
            "ヒナミは「行こう、もう遅い」と言う。ヒナミは「行こう、もう遅い」と言う。")
    assert short == "いいえ。いいえ。"
    assert quoted.count("行こう") == 2


def test_a_retidied_japanese_echo_is_stripped():
    with language_scope("ja"):
        out = _strip_player_echo("あなたは「行こうよ」と言った。ドクターが頷く。",
                                 ["行こうよ。"])
    assert "行こうよ" not in out, out
    assert "ドクターが頷く。" in out


def test_english_is_unchanged():
    text = ("The hall is quiet tonight here. The lamp gutters. "
            "The hall is quiet tonight here.")
    assert _dedupe_view_sentences(text) == (
        "The hall is quiet tonight here. The lamp gutters.")
    assert _strip_player_echo('You say, "Wait for me, please." The door shuts.',
                              ["Wait for me please"]) == "You say it. The door shuts."
