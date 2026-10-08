"""A tracked presence whose name is a description is not named by its words.

`_background_name_mentioned` falls back to any significant word of a tracked
name, because the prose says "Crusher" once "Dr. Crusher" is established.
A presence's name can be a description, though -- "a hunched man in an
oilskin coat" -- and its words are common nouns. Scratch story 166 idx
15-17: the player spoke of the coat on the stake, the word "coat" named the
man, and a presence standing in no room was counted as addressed and voiced
on four beats running.
"""

from persist.commit import _background_name_mentioned


def test_a_description_is_not_named_by_its_nouns():
    name = "a hunched man in an oilskin coat"
    assert not _background_name_mentioned(name, "She draws the paper from the coat's open pocket.")
    assert not _background_name_mentioned("broad man", "A man at the rail looks up.")


def test_the_whole_description_still_names_him():
    assert _background_name_mentioned(
        "a hunched man in an oilskin coat", "She nods to a hunched man in an oilskin coat.")


def test_a_proper_names_part_still_names_its_owner():
    assert _background_name_mentioned("Dr. Crusher", "Crusher turns from the bed.")
    assert _background_name_mentioned("Reeve Cuthon Hurster", "Hurster nods.")


def test_a_script_without_case_keeps_every_part():
    """No case to mark a name, so every part counts as it always did (parts
    under three characters were never counted, in any script)."""
    assert _background_name_mentioned("高橋 美智子", "美智子 が 頷く。")
