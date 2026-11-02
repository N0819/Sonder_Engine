"""A perceiver's own name in its own view becomes the second person in
Japanese too.

`_self_second_person` rewrites the perceiver's name forms inside engine-
supplied prose ("Dr. Moon steps toward Hinami" in Hinami's own view ->
"...toward you"). Its pattern bounded a name with `(?<!\\w)`/`(?!\\w)`, and a
Japanese particle is a word character, so ヒナミの / ヒナミは never matched and
the perceiver read herself in the third person inside her own view
(agents_common audit F8). The replacement is the pack's own word for the
perceiver (`compositor.self_label`: あなた), and the particle the name carried
stays where it was, which is how Japanese writes the case.
"""

from __future__ import annotations

from language_runtime import language_scope

from agents.common import _self_second_person


def test_a_japanese_name_with_its_particle_becomes_anata():
    with language_scope("ja"):
        out = _self_second_person(
            "ドクターがヒナミの肩に手を置く。ヒナミは扉を開ける。", ["ヒナミ"])
    assert out == "ドクターがあなたの肩に手を置く。あなたは扉を開ける。", out


def test_the_full_name_goes_whole_and_a_longer_name_and_a_quote_are_left():
    with language_scope("ja"):
        whole = _self_second_person("佐藤ヒナミは立ち上がる。", ["佐藤ヒナミ", "ヒナミ"])
        other = _self_second_person("ヒナミコが笑う。", ["ヒナミ"])
        quoted = _self_second_person("ドクターが「ヒナミ、来て」と言う。", ["ヒナミ"])
    assert whole == "あなたは立ち上がる。", whole
    assert other == "ヒナミコが笑う。"
    assert quoted == "ドクターが「ヒナミ、来て」と言う。"


def test_english_is_unchanged():
    assert _self_second_person(
        "Dr. Moon sets a hand on Hinami's shoulder. Hinami opens the door.",
        ["Hinami"]) == "Dr. Moon sets a hand on your shoulder. You open the door."
