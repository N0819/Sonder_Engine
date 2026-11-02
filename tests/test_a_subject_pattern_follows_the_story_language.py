"""A compiled subject pattern follows the story language it was asked in.

`_subject_opener(form)` compiles the ACTIVE pack's title alternation into its
pattern ("Dr." before an English name; 博士/隊長 in the Japanese table), but its
LRU cache was keyed by the form alone: whichever language first compiled a
form won for every later story in the process (agents_common audit F9). The
server runs stories in both packs concurrently, and
`language_runtime.linguistic`'s own docstring forbids exactly this. The
readers are `_sentence_subjects` -- the four authority checks -- and
`_strip_subject`.
"""

from __future__ import annotations

from language_runtime import language_scope

from agents import common



def test_the_same_form_compiles_per_language_in_either_order():
    with language_scope("en"):
        en_first = common._subject_opener("ヒナミ").pattern
    with language_scope("ja"):
        ja_second = common._subject_opener("ヒナミ").pattern
        ja_again = common._subject_opener("ヒナミ").pattern
    with language_scope("en"):
        en_again = common._subject_opener("ヒナミ").pattern
    assert en_first != ja_second, "the ja story read the en pack's titles"
    assert ja_again == ja_second and en_again == en_first


def test_a_title_only_the_japanese_pack_holds_opens_a_japanese_sentence():
    with language_scope("en"):
        common._subject_opener("ヒナミ")      # an English story first
    with language_scope("ja"):
        assert common._subject_opener("ヒナミ").match("博士 ヒナミは扉を開ける。")
