"""Which lore entries reach a mind at all.

`memory.knowledge_for_character` is the gate on the LORE path, the way
`agents/composer.py` is the gate on the perception path. It is called once per
character step (`agents/character.py:2572`) to build what that mind knows, and
it answers two separate questions:

  * does this character hold the entry's `knowledge_tag`, and
  * for a `local`-range entry, are they standing somewhere it applies?

It had no tests. An audit removed BOTH gates and the whole 6,611-test suite
stayed green -- every knowledge entry in every reachable book reaching every
character, regardless of what they know or where they are, with nothing to say
so. The comment at `agents/character.py:2573-2578` leans on this gate by name
when explaining why a SEPARATE identity floor was needed on top of it, so the
engine is already reasoning about lore leakage as though this were covered.

These tests are behavioural: they insert real rows and assert on what comes
back, so a change to the gating logic fails here rather than passing quietly.
"""

from __future__ import annotations

import pytest

from mind.memory import add_lore, knowledge_for_character


@pytest.fixture
def book(temp_db):
    return temp_db.qi("INSERT INTO lorebooks(name) VALUES('Test book')")


def _entry(book_id, title, *, tag=None, rng=None, where=None, content="x"):
    return add_lore(
        book_id, title, content, category="knowledge", title=title,
        knowledge_tag=tag, knowledge_range=rng, knowledge_locations=where)


def _titles(results):
    return {r["title"] for r in results}


# --- the tag gate ----------------------------------------------------------

def test_an_entry_reaches_a_mind_that_holds_its_tag(book):
    _entry(book, "Warp theory", tag="engineering")
    assert _titles(knowledge_for_character(
        [book], None, {"engineering"}, [])) == {"Warp theory"}


def test_an_entry_is_withheld_from_a_mind_without_its_tag(book):
    """The gate. Without it, specialist knowledge reaches every character."""
    _entry(book, "Warp theory", tag="engineering")
    assert knowledge_for_character([book], None, {"medicine"}, []) == []


def test_a_mind_with_no_tags_receives_nothing(book):
    _entry(book, "Warp theory", tag="engineering")
    _entry(book, "Common lore", tag="common")
    assert knowledge_for_character([book], None, set(), []) == []


def test_an_untagged_entry_counts_as_common(book):
    """`tag = row["knowledge_tag"] or "common"` -- an authored entry that
    names no tag is general knowledge, not secret knowledge."""
    _entry(book, "Everyone knows", tag=None)
    assert _titles(knowledge_for_character([book], None, {"common"}, [])) \
        == {"Everyone knows"}
    assert knowledge_for_character([book], None, {"engineering"}, []) == []


# --- the range gate --------------------------------------------------------

def test_a_local_entry_reaches_a_mind_standing_in_one_of_its_places(book):
    _entry(book, "Deck plan", tag="common", rng="local", where='["engineering"]')
    assert _titles(knowledge_for_character(
        [book], "engineering", {"common"}, [])) == {"Deck plan"}


def test_a_local_entry_is_withheld_from_a_mind_standing_elsewhere(book):
    """Local knowledge is knowledge you have because of where you ARE."""
    _entry(book, "Deck plan", tag="common", rng="local", where='["engineering"]')
    assert knowledge_for_character([book], "sickbay", {"common"}, []) == []


def test_a_local_entry_with_no_places_reaches_nobody(book):
    """An entry declared local and given nowhere to be local TO cannot be
    earned by standing anywhere, so it is withheld rather than made global."""
    _entry(book, "Nowhere", tag="common", rng="local", where="[]")
    assert knowledge_for_character([book], "engineering", {"common"}, []) == []


def test_a_global_entry_ignores_where_the_mind_is_standing(book):
    _entry(book, "Federation history", tag="common", rng="global")
    for room in ("engineering", "sickbay", None):
        assert _titles(knowledge_for_character(
            [book], room, {"common"}, [])) == {"Federation history"}


# --- the two gates are independent -----------------------------------------

def test_the_right_place_does_not_excuse_the_wrong_tag(book):
    """Both gates must hold. Standing in the room does not grant the tag."""
    _entry(book, "Reactor secrets", tag="engineering", rng="local",
           where='["engineering"]')
    assert knowledge_for_character([book], "engineering", {"medicine"}, []) == []


def test_the_right_tag_does_not_excuse_the_wrong_place(book):
    _entry(book, "Reactor secrets", tag="engineering", rng="local",
           where='["engineering"]')
    assert knowledge_for_character([book], "sickbay", {"engineering"}, []) == []


# --- the remaining filters -------------------------------------------------

def test_an_excluded_title_is_withheld(book):
    _entry(book, "Already known", tag="common")
    _entry(book, "Still new", tag="common")
    assert _titles(knowledge_for_character(
        [book], None, {"common"}, ["Already known"])) == {"Still new"}


def test_a_repeated_title_is_delivered_once(book):
    _entry(book, "Duplicated", tag="common", content="first")
    _entry(book, "Duplicated", tag="common", content="second")
    assert len(knowledge_for_character([book], None, {"common"}, [])) == 1


def test_the_limit_is_honoured(book):
    for i in range(8):
        _entry(book, f"Entry {i}", tag="common")
    assert len(knowledge_for_character([book], None, {"common"}, [], limit=3)) == 3


def test_no_books_or_no_tags_short_circuits(book):
    _entry(book, "Anything", tag="common")
    assert knowledge_for_character([], None, {"common"}, []) == []
    assert knowledge_for_character([book], None, None, []) == []


def test_only_knowledge_category_entries_are_considered(book):
    """The gate reads `category='knowledge'`; ordinary lore reaches a mind by
    a different path with different rules."""
    add_lore(book, "Place", "A room somewhere", category="location",
             title="Place", knowledge_tag="common")
    assert knowledge_for_character([book], None, {"common"}, []) == []
