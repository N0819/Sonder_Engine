"""A question loses the names it says, in whatever script it says them.

`memory_jev.without_names` rewrites a question with the people it names taken
out before it is embedded for the ABOUT lane (and `memory_routes`' subject
lane): the rows share the person and not the name, and the name only pulls the
vector toward whatever else says it. Measured 2026-09-29: the row of the
Doctor first meeting Hinami sat 48th of 267 against the question as asked and
15th against "...first met them?".

It found a name only between `\\w` boundaries and put the English "them" in
its place (review 2026-11-01, mind_memory F16, reproduced). In a script that
does not space its words a name is never between such boundaries -- the
particle after it is a word character -- so "オレンに初めて会ったのはいつ？"
came back unchanged and the measured gain never applied; and where a boundary
did fall, inside the name, the question became "初めて会ったのはオレン・them".
`named_in`, beside it, was fixed for unspaced scripts on 2026-10-06; this was
not.
"""

from __future__ import annotations

import re

from mind.memory import without_names

OREN = "オレン・ダスク"


def test_english_questions_read_as_they_always_did():
    assert without_names("When did I first meet Hinami?", ["Hinami"]) == \
        "When did I first meet them?"
    assert without_names("Where is Hinami's mother?", ["Hinami"]) == "Where is their mother?"
    assert without_names("What did Picard say?", ["Jean-Luc Picard"]) == "What did them say?"
    assert without_names("Was it Picard or Data?", ["Jean-Luc Picard", "Data"]) == \
        "Was it them or them?"


def test_a_japanese_question_loses_a_name_said_with_a_particle():
    out = without_names("オレンに初めて会ったのはいつ？", [OREN])
    assert "オレン" not in out
    assert out == "に初めて会ったのはいつ？"


def test_no_english_word_lands_in_a_japanese_question():
    out = without_names("初めて会ったのはオレン・ダスク", [OREN])
    assert out == "初めて会ったのは"
    assert not re.search(r"[A-Za-z]", without_names("ヒナミの母はどこ？", ["ヒナミ"]))


def test_a_latin_name_inside_a_japanese_question_is_found_too():
    assert without_names("Hinamiに初めて会ったのはいつ？", ["Hinami"]) == \
        "に初めて会ったのはいつ？"


def test_a_longer_word_that_merely_contains_the_name_is_left_alone():
    assert without_names("オレンジを一つ買った。", [OREN]) == "オレンジを一つ買った。"
    assert without_names("The Orenstein ledger", ["Oren"]) == "The Orenstein ledger"


def test_the_question_s_own_words_decide_not_the_name_s_script():
    """An English question about someone whose name is written in kana is
    still an English question: "them" stands in for her."""
    assert without_names("When did I first meet ヒナミ?", ["ヒナミ"]) == \
        "When did I first meet them?"
