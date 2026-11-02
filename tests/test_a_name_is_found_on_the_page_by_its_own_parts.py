"""Two page checks find a name the way a reader does: by its own parts, in
its own script.

* `_check_narrator_fidelity`'s proper-noun arm took a name's parts from
  `.split()` with a three-character floor, so "The" was a part of "The
  Doctor" -- matched case-insensitively, any page containing the word *the*
  had "mentioned" him (agents_common audit F15) -- and "Dr." a part of
  "Dr. Moon". Its parts are now the name's significant tokens (titles and
  articles out, `_significant_name_tokens`). And it bounded every form with
  `(?<!\\w)…(?!\\w)`, which a Japanese particle defeats, so a Japanese name
  was never in the view, never on the page, and never a pronoun (F14).
* `_check_player_person` bounded the player's name the same way, so a
  Japanese page that named the player in the third person was never caught
  (F14: ja `[]`, en warns).
"""

from __future__ import annotations

from language_runtime import language_scope

from agents.common import _check_narrator_fidelity, _check_player_person

HE = {"subject": "he", "object": "him", "possessive": "his"}
SHE_JA = {"subject": "彼女", "object": "彼女", "possessive": "彼女の"}


def _missing(prose, view, roster):
    return [w for w in _check_narrator_fidelity(
        {"prose": prose}, view, cast_pronouns=roster)
        if w.startswith("Proper noun from view missing")]


def test_an_article_is_not_a_part_of_the_name_it_leads():
    roster = {"The Doctor": HE}
    assert _missing("A door opened quietly.",
                    "The Doctor stands at the door.", roster)
    assert _missing("The door opened quietly.",
                    "The Doctor stands at the door.", roster)
    assert not _missing("The Doctor opens the door.",
                        "The Doctor stands at the door.", roster)
    assert not _missing("He opens the door.",
                        "The Doctor stands at the door.", roster)
    # A surname still answers for the whole name.
    assert not _missing("Voss waits.", "Elyra Voss waits.",
                        {"Elyra Voss": HE})


def test_a_japanese_name_is_found_in_the_view_and_on_the_page():
    roster = {"佐藤ヒナミ": SHE_JA}
    view = "佐藤ヒナミが窓辺に立っている。"
    with language_scope("ja"):
        dropped = _missing("部屋は静かだ。", view, roster)
        named = _missing("ヒナミは窓辺に立っている。", view, roster)
        pronoun = _missing("彼女は窓辺に立っている。", view, roster)
    assert dropped, "the view named her and the page never did"
    assert named == [] and pronoun == []


def test_a_japanese_page_naming_the_player_in_the_third_person_is_caught():
    with language_scope("ja"):
        caught = _check_player_person("ヒナミは扉を開ける。", "ヒナミ", "second")
        quoted = _check_player_person("ドクターが「ヒナミ」と呼ぶ。", "ヒナミ", "second")
        longer = _check_player_person("ヒナミコは扉を開ける。", "ヒナミ", "second")
    assert caught and quoted == [] and longer == []
    assert _check_player_person("Hinami opens the door.", "Hinami", "second")
