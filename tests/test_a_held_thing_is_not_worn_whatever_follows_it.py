"""A thing in a wearing list is refused for what it IS -- the noun the phrase
is about -- and a phrase's tail does not get to be that noun.

`sanitize_attire_items` read the head as the LAST word of the first clause.
Any prepositional tail made the location or the contents the "head": "a cup
of tea" was tea, "the cup in her hand" -- the module's own example of what
must never be worn -- was a hand, "a glass of wine" was wine, so each was kept
as a garment and the body reported wearing it forever (story_attire_import
audit F13). `attaches_only` already cut the garment phrase at a placement
preposition; this reader did not, so two readers of "what is this thing"
used two rules.

The head is now the last word before a placement preposition or an "of" --
English names the thing first in "N of N" and "N in/at/on ...". What the
table refuses is unchanged: a sword at the hip is carried gear on a belt,
and whether that is worn is the table's question, not this reader's.
"""

from __future__ import annotations

from story.attire import sanitize_attire_items


def test_a_thing_followed_by_its_contents_or_its_place_is_refused():
    assert sanitize_attire_items([
        "a cup of tea", "the cup in her hand", "a glass of wine",
        "a mug on the table", "a bottle of rum"]) == []


def test_garments_that_carry_those_words_stay():
    kept = ["tinted glass goggles, pushed up on the hat brim",
            "bottle green coat", "glasses", "a coat of many colours",
            "a ring of keys", "a silk sash with pouches"]
    assert sanitize_attire_items(kept) == kept


def test_the_bare_things_are_still_refused():
    assert sanitize_attire_items(["a cup", "the wooden chair", "a glass"]) \
        == []
