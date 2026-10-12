"""A stranger's label never says its words twice.

Hollowmere (scratch chat 196, turn 4685, 2026-10-12): the lineman's own
payload named the woman beside him "the grey-haired solid grey-haired medium
solid ruddy heavy person, with cropped grey with cropped grey", and he
addressed her by it. Two writers file a minted body's appearance as its
`role_hint`; with a structured surface the label is the surface's adjectives
followed by the role as its noun, so the appearance was said after the words
it repeats. A hint that restates the surface's own words is an appearance,
not a role (`background._restates_surface`); a post stays the noun.
"""
from __future__ import annotations

from agents.background import _restates_surface
from agents.common import _unknown_actor_label

SURFACE = {"age": "grey-haired", "build": "solid", "stature": "medium",
           "complexion": "ruddy", "hair": "cropped grey"}
SEEN = "grey-haired medium solid ruddy heavy person, with cropped grey"


def test_an_appearance_filed_as_a_role_restates_the_surface():
    assert _restates_surface(SEEN, SURFACE)
    assert not _restates_surface("telegraph keeper", SURFACE)
    assert not _restates_surface("", SURFACE)


def test_without_it_the_label_says_each_word_once():
    label = _unknown_actor_label("Agathe Brenn", "", role="", surface=SURFACE)
    assert label == "the grey-haired solid person with cropped grey"
    words = label.replace(",", "").split()
    assert len(words) == len(set(words)) + words.count("the") - 1


def test_a_post_is_still_the_noun():
    assert _unknown_actor_label("Agathe Brenn", "", role="telegraph keeper",
                                surface=SURFACE) == \
        "the grey-haired solid telegraph keeper with cropped grey"
