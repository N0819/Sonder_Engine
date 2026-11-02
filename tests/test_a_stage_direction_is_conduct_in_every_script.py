"""A stage direction written into a spoken line is CONDUCT in every script.

`split_stage_directions` cuts `*...*` spans out of speech and promotes them to
action elements, because a body movement left in `text` goes down the
acoustic channel -- a listener behind a door is told what the speaker's body
did, a flow the engine owns. It kept a ONE-WORD span as markdown emphasis, and
measured the word with `.split()`: every Japanese span was "one word", so in a
Japanese story nothing was ever cut (agents_common audit F4:
'*身を乗り出して彼女の肩に手を置く* 座ったほうがいい。' came back with the
conduct still in the spoken text and no action).

A word is now counted in its own script: a spaced span by whitespace, as
before; an unspaced span by its CONTENT runs (`fold_words` minus the hiragana
runs, the particles and inflection), so 本当 or 本当に stays emphasis the way
"*really*" does, and a phrase of several content words is conduct the way
"*leans in*" is.
"""

from __future__ import annotations

import pytest

from language_runtime import language_scope

from agents import common



def test_a_japanese_stage_direction_becomes_an_action():
    with language_scope("ja"):
        spoken, spans = common.split_stage_directions(
            "*身を乗り出して彼女の肩に手を置く* 座ったほうがいい。")
        out = common.norm_sequence({"sequence": [
            {"type": "speech",
             "text": "*身を乗り出して彼女の肩に手を置く* 座ったほうがいい。"}]})
    assert spoken == "座ったほうがいい。", spoken
    assert spans == ["身を乗り出して彼女の肩に手を置く"]
    kinds = [(e["type"], e.get("attempt") or e.get("text"))
             for e in out["sequence"]]
    assert kinds == [("action", "身を乗り出して彼女の肩に手を置く"),
                     ("speech", "座ったほうがいい。")], kinds


@pytest.mark.parametrize("line, spoken", [
    ("それは*本当*なの？", "それは本当なの？"),
    ("*本当に*行くの？", "本当に行くの？"),
    ("*はい*、わかりました。", "はい、わかりました。"),
])
def test_a_japanese_emphasised_word_stays_spoken(line, spoken):
    with language_scope("ja"):
        got, spans = common.split_stage_directions(line)
    assert (got, spans) == (spoken, [])


def test_the_mark_the_cut_strands_goes_with_it():
    with language_scope("ja"):
        got, spans = common.split_stage_directions(
            "*彼女の手を取って*、行こう。")
    assert (got, spans) == ("行こう。", ["彼女の手を取って"])


def test_english_is_unchanged():
    assert common.split_stage_directions(
        "*leans in and sets a hand on her shoulder* You will want to sit down."
    ) == ("You will want to sit down.",
          ["leans in and sets a hand on her shoulder"])
    assert common.split_stage_directions(
        "What does it *feel* like?") == ("What does it feel like?", [])
    assert common.split_stage_directions(
        "It is *well-known* here.") == ("It is well-known here.", [])
