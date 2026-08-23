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

import json

import pytest

from mind.memory import (
    add_lore, declared_circles, dump_lorebook, knowledge_for_character,
    restore_lorebook,
)


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


def test_an_untagged_entry_is_director_material_not_character_knowledge(book):
    """An explicit depth tag is what OFFERS an entry to minds at all.

    This used to read `tag = row["knowledge_tag"] or "common"`, which was safe
    only because a category gate stood in front of it. With reachability moved
    off the category (see below), that default would hand every character
    every entry in every reachable book -- 2,671 of them across the stories on
    disk. Untagged now means what the mapping stage already treats it as:
    retrieval material for the Director, not something a mind holds.
    """
    _entry(book, "Everyone knows", tag=None)
    assert knowledge_for_character([book], None, {"common"}, []) == []


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


def test_reachability_is_a_property_not_a_category(book):
    """A tagged entry reaches a mind whatever it is FILED as.

    The gate used to select `category='knowledge'` and nothing else. Measured
    across every story on disk: 25 of 2,671 entries were in that category
    (0.9%), while 974 entries in other categories already carried an explicit
    depth tag and reached nobody because of their filing. A fact is routinely
    both -- "a Scranton Reality Anchor nullifies reality-bending" is
    `mechanic` by the authored category vocabulary AND something a Foundation
    researcher knows -- so the taxonomy forced a choice in which filing it
    correctly removed it from every mind (chat 84: the entry was selected into
    `relevant_lore` on every turn and the doctor's world_knowledge was empty
    on all of them).
    """
    add_lore(book, "Anchor", "It nullifies reality-bending",
             category="mechanic", title="Anchor", knowledge_tag="scholarly")
    assert _titles(knowledge_for_character(
        [book], None, {"scholarly"}, [])) == {"Anchor"}


# --- the compartment gate --------------------------------------------------
#
# Depth says how hard a thing is to know. It cannot say that a clandestine
# organisation's existence is withheld from everyone outside it -- and authors
# had already noticed, writing compartment names INTO the depth field:
# `site-17`, `starfleet_protocol`, `priya_private`, `concord_boarders` and
# `blackwood_sanatorium/west_wing/access` all appear as `knowledge_tag` values
# on disk, and every one of them granted nothing to anybody, silently.


def _circled_book(db, name, circles):
    return db.qi("INSERT INTO lorebooks(name,default_circles) VALUES(?,?)",
                 (name, json.dumps(circles)))


def test_a_books_compartment_withholds_it_from_outsiders(temp_db):
    """The public does not know a secret organisation exists, however
    scholarly they are. This is the property depth alone cannot state."""
    secret = _circled_book(temp_db, "Foundation", ["SCP Foundation"])
    _entry(secret, "Anchors", tag="common")
    assert knowledge_for_character([secret], None, {"common"}, []) == []
    assert knowledge_for_character(
        [secret], None, {"common", "scholarly", "esoteric"}, []) == []


def test_a_member_of_the_circle_receives_it(temp_db):
    secret = _circled_book(temp_db, "Foundation", ["SCP Foundation"])
    _entry(secret, "Anchors", tag="common")
    assert _titles(knowledge_for_character(
        [secret], None, {"common"}, [], circles=["SCP Foundation"])) \
        == {"Anchors"}


def test_the_compartment_is_set_once_at_the_book_and_inherited(temp_db):
    """One decision in one place. Per-entry tagging means one forgotten entry
    tells a barista the Foundation exists -- an empty field fails silently,
    and this is the field where that costs the most."""
    secret = _circled_book(temp_db, "Foundation", ["SCP Foundation"])
    for i in range(5):
        _entry(secret, f"Secret {i}", tag="common")
    assert knowledge_for_character([secret], None, {"common"}, []) == []
    assert len(knowledge_for_character(
        [secret], None, {"common"}, [], circles=["SCP Foundation"])) == 5


def test_an_entry_may_override_its_books_compartment(temp_db):
    """A secret that has leaked into public rumour is a deliberate exception,
    and it is the entry's to declare -- not the book's."""
    secret = _circled_book(temp_db, "Foundation", ["SCP Foundation"])
    _entry(secret, "Kept", tag="common")
    public = _entry(secret, "Rumoured", tag="common")
    temp_db.qi("UPDATE lore_entries SET circles='[]' WHERE id=?", (public,))
    # An explicit empty override does NOT fall back to the book: the entry
    # answered the question, and the answer was "public".
    assert _titles(knowledge_for_character(
        [secret], None, {"common"}, [])) == {"Rumoured"}


def test_depth_and_compartment_are_independent(temp_db):
    """Being inside the circle is not the same as being deep enough, and a
    single axis could not express the conjunction -- which is exactly why a
    Foundation researcher and a scholarly civilian both hold 'scholarly' and
    only one of them may read the file."""
    secret = _circled_book(temp_db, "Foundation", ["SCP Foundation"])
    _entry(secret, "Deep file", tag="esoteric")
    assert knowledge_for_character(
        [secret], None, {"common"}, [], circles=["SCP Foundation"]) == []
    assert _titles(knowledge_for_character(
        [secret], None, {"esoteric"}, [], circles=["SCP Foundation"])) \
        == {"Deep file"}


def test_circle_matching_ignores_case_and_padding(temp_db):
    secret = _circled_book(temp_db, "Foundation", ["SCP Foundation"])
    _entry(secret, "Anchors", tag="common")
    assert _titles(knowledge_for_character(
        [secret], None, {"common"}, [], circles=["  scp foundation "])) \
        == {"Anchors"}


def test_declared_circles_sees_book_and_entry_level(temp_db):
    """What the warning path reads. An outsider BY DECLARATION is fine; an
    outsider by omission is an unfinished sheet, and the two look identical in
    the payload -- both are a mind holding only public knowledge."""
    plain = temp_db.qi("INSERT INTO lorebooks(name) VALUES('Public')")
    secret = _circled_book(temp_db, "Foundation", ["SCP Foundation"])
    _entry(plain, "Weather", tag="common")
    one_off = _entry(plain, "Cell rumour", tag="common")
    temp_db.qi("UPDATE lore_entries SET circles=? WHERE id=?",
               ('["Site Staff"]', one_off))
    assert declared_circles([plain, secret]) == {"scp foundation", "site staff"}
    assert declared_circles([]) == set()


def test_a_compartment_survives_a_dump_and_restore(temp_db):
    """The compartment is the difference between a secret and a leak, so it
    has to survive export/checkpoint/branch. A round trip that drops it
    republishes the organisation's existence to everybody."""
    secret = _circled_book(temp_db, "Foundation", ["SCP Foundation"])
    _entry(secret, "Kept", tag="common")
    leaked = _entry(secret, "Rumoured", tag="common")
    temp_db.qi("UPDATE lore_entries SET circles='[]' WHERE id=?", (leaked,))

    dumped = dump_lorebook(secret)
    assert {e["title"]: e["circles"] for e in dumped} == {
        "Kept": None, "Rumoured": "[]"}

    target = _circled_book(temp_db, "Foundation (restored)", ["SCP Foundation"])
    restore_lorebook(target, dumped)
    # Inherit vs explicit-public survives the trip, so an outsider still gets
    # exactly the one entry that was deliberately made public.
    assert _titles(knowledge_for_character(
        [target], None, {"common"}, [])) == {"Rumoured"}
    assert _titles(knowledge_for_character(
        [target], None, {"common"}, [], circles=["SCP Foundation"])) \
        == {"Kept", "Rumoured"}
