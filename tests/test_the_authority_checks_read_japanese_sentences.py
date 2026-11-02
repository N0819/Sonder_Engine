"""The authority checks read a Japanese beat sentence by sentence.

`_sentence_subjects` is the primitive under the four authority checks (who
is the subject of each sentence, a pronoun continuing the last name). Its
default splitter was `(?<=[.!?])\\s+`, ASCII only, so a Japanese paragraph was
ONE sentence whose subject was its first name, and `_predicate_heads` joined
an unspaced clause's script runs with spaces ("話 す") and counted its verb
window from the subject, where Japanese puts the verb last. Every check read
nothing (agents_common audit F14: `ドクターは黙っている。ヒナミは「行こう」と言った。`
-> `[]` where the English beat warned).

English is unchanged and pinned here: the splitter on text with no unspaced
stop is the same pattern, and a spaced clause's head is its first tokens
joined by single spaces, exactly as before.
"""

from __future__ import annotations

from language_runtime import language_scope

from agents import common



def test_a_japanese_paragraph_is_several_sentences_with_their_subjects():
    with language_scope("ja"):
        got = list(common._sentence_subjects(
            "ヒナミは立ち上がる。ドクターは静かに笑う。彼は扉を開ける。",
            ["ヒナミ", "ドクター"]))
    assert got == [("ヒナミは立ち上がる。", "ヒナミ"),
                   ("ドクターは静かに笑う。", "ドクター"),
                   ("彼は扉を開ける。", "ドクター")], got


def test_a_closing_bracket_stays_with_its_sentence_and_a_quotative_carries_on():
    with language_scope("ja"):
        got = common.split_sentences(
            "「行こう。」と彼は言った。ヒナミは扉を開ける。")
    assert got == ["「行こう。」と彼は言った。", "ヒナミは扉を開ける。"], got


def test_english_sentences_split_exactly_as_before():
    # A closing quote before the next sentence has always kept the two
    # together in this splitter; its guards were measured against that.
    text = 'It is late." Mellisande holds out a hand. Dr. Moon waits.'
    assert common.split_sentences(text) == [
        'It is late." Mellisande holds out a hand.', "Dr. Moon waits."]
    got = list(common._sentence_subjects(
        "The Doctor draws it. Hinami flinches. She says nothing.",
        ["The Doctor", "Hinami"]))
    assert [s for _, s in got] == ["The Doctor", "Hinami", "Hinami"]


def test_a_japanese_head_is_read_as_written_from_the_clause_end():
    with language_scope("ja"):
        heads = common._predicate_heads("は静かに話す。", 3)
    assert heads == [("かに話す", "は静かに話す。")], heads
    assert common._predicate_heads(
        "takes a half-step closer, hands open at his sides, and speaks low", 3
    ) == [("takes a half", "takes a half-step closer"),
          ("hands open at", "hands open at his sides"),
          ("speaks low", "speaks low")]


def test_a_silent_characters_invented_speech_is_caught_in_japanese():
    with language_scope("ja"):
        caught = common._check_character_speech_authority(
            "ドクターは黙っている。ヒナミは静かに話す。", ["ヒナミ"],
            other_names=["ドクター"])
        quiet = common._check_character_speech_authority(
            "ドクターは静かに話す。ヒナミは窓の外を見ている。", ["ヒナミ"],
            other_names=["ドクター"])
    assert caught and "ヒナミ" in caught[0], caught
    assert quiet == [], quiet
    assert common._check_character_speech_authority(
        "The Doctor stays silent. Hinami adds a further comment.", ["Hinami"],
        other_names=["The Doctor"])


def test_an_undeclared_act_is_caught_in_japanese():
    with language_scope("ja"):
        caught = common._check_character_act_authority(
            "ドクターは黙っている。ヒナミは扉を開ける。", [], "ヒナミ",
            other_names=["ドクター"])
    assert caught and "ヒナミ" in caught[0], caught
