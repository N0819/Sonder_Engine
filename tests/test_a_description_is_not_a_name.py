"""A word that names a thing the scene holds does not name a person.

`_background_name_mentioned` falls back to any significant word of a tracked
name, because the prose says "Crusher" once "Dr. Crusher" is established, and
a lone holder of a post is reached by its title ("the night clerk" by
"clerk", `test_who_you_talk_to`). A presence's name can also hold the name
of a THING: scratch story 166 idx 15-17, the player's every line about the
coat on a stake named "a hunched man in an oilskin coat", and a presence
standing in no room was counted addressed and voiced on four beats running.
A word naming something else the scene holds joins the excluded set
(`_thing_name_words`); the whole name still names its holder.
"""

from persist.commit import _background_name_mentioned, _thing_name_words

SCENE = {"entities": {
    "waterlogged_coat": {"name": "a waterlogged coat caught on the stake",
                         "kind": "object", "aliases": ["coat", "waterlogged coat"]},
    "oilskin_man": {"name": "a hunched man in an oilskin coat", "kind": "person"}}}


def test_a_thing_s_word_is_the_thing_s():
    words = _thing_name_words(SCENE)
    assert "coat" in words and "waterlogged" in words
    assert "hunched" not in words, "a person is not a thing"


def test_the_coat_on_the_stake_does_not_name_the_man():
    name = "a hunched man in an oilskin coat"
    shared = _thing_name_words(SCENE)
    assert not _background_name_mentioned(
        name, "She draws the paper from the coat's open pocket.", shared=shared)
    assert _background_name_mentioned(
        name, "She nods to a hunched man in an oilskin coat.", shared=shared)


def test_a_lone_title_still_reaches_its_holder():
    assert _background_name_mentioned("the night clerk", "Ask the clerk.",
                                      shared=_thing_name_words(SCENE))
