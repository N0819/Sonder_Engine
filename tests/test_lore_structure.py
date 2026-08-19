"""A World Info book is a tree its author drew in the entry titles.

The live Re:Zero book is 300 entries and 354,677 characters, and its `comment`
fields encode 6 sections, 9 subsections, 168 leaves and 116 explicit `[›]`
children. `comment` appeared NOWHERE in importers.py, so all of it was
discarded: the imported book had `title` populated on 0 of 310 rows,
`knowledge_tag` on 0, `knowledge_locations` on 1, and `importance` flat at 0.5
on 309.

The tree is worth recovering for more than navigability. It is the only
principled source for the knowledge fields — `[›] Lugunica Currency` sitting
under `[🏰] Dragon Kingdom of Lugunica` says structurally that this is LOCAL
knowledge about Lugunica, which is what lets an innkeeper there be expected to
know it while a stranger two kingdoms away is not. Asking a model that question
per entry would cost 300 calls and answer worse.
"""

from __future__ import annotations

import pytest

from story.lore_structure import (classify_title, clean_title, derive_knowledge,
                            parse_structure)


def _book():
    """The live grammar, in authored order."""
    raw = [
        "═══════[World]═══════",
        "[«»] World History [«»]",
        "[›] Great Calamity",
        "⚲────↓Kingdom Locations↓────⚲",
        "[🏰] Dragon Kingdom of Lugunica [🏰]",
        "[⤹] Dragon Kingdom of Lugunica (Lite) [⤸]",
        "[›] Lugunica Currency",
        "═══════[Abilities]═══════",
        "[⚖️]────↓Authority↓────[⚖️]",
        "[›] Authority of Sloth",
    ]
    return [{"uid": i, "displayIndex": i, "comment": t,
             "content": f"body {i}", "key": []} for i, t in enumerate(raw)]


class TestTheGrammar:
    @pytest.mark.parametrize("raw,level", [
        ("═══════[World]═══════", "section"),
        ("⚲────↓Kingdom Locations↓────⚲", "subsection"),
        ("[⚖️]────↓Authority↓────[⚖️]", "subsection"),
        ("[›] Lugunica Currency", "child"),
        ("[📍] Priestella", "leaf"),
    ])
    def test_each_title_form_is_recognised(self, raw, level):
        assert classify_title(raw) == level

    @pytest.mark.parametrize("raw,clean", [
        ("═══════[World]═══════", "World"),
        ("⚲────↓Kingdom Locations↓────⚲", "Kingdom Locations"),
        ("[›] Lugunica Currency", "Lugunica Currency"),
        ("[🏰] Dragon Kingdom of Lugunica [🏰]", "Dragon Kingdom of Lugunica"),
    ])
    def test_the_decoration_comes_off(self, raw, clean):
        assert clean_title(raw) == clean


class TestTheTree:
    def test_a_child_hangs_from_the_leaf_above_it_not_the_section(self):
        """"Lugunica Currency" is a fact ABOUT Lugunica, not a sibling of it.
        Attaching children to the section instead would lose the one relation
        that makes the knowledge fields derivable."""
        recs = {r["title"]: r for r in parse_structure(_book())}
        currency = recs["Lugunica Currency"]
        assert currency["level"] == "child"
        assert currency["section"] == "World"
        assert currency["subsection"] == "Kingdom Locations"
        assert currency["parent"] == "Dragon Kingdom of Lugunica (Lite)"

    def test_order_is_authored_order_because_the_tree_is_positional(self):
        """"The leaf above me" is meaningless in any other order, so the walk
        sorts on displayIndex rather than trusting dict order."""
        book = list(reversed(_book()))
        recs = {r["title"]: r for r in parse_structure(book)}
        assert recs["Lugunica Currency"]["section"] == "World"

    def test_a_rule_with_no_content_is_scaffolding(self):
        book = _book()
        book[0]["content"] = ""
        recs = {r["title"]: r for r in parse_structure(book)}
        assert recs["World"]["structural"] is True


class TestWhatTheTreeSaysAboutKnowledge:
    def test_the_innkeeper_case(self):
        """The whole reason this module exists. Currency under a kingdom is
        local knowledge about that kingdom."""
        recs = {r["title"]: r for r in parse_structure(_book())}
        tag, rng, locs = derive_knowledge(recs["Lugunica Currency"])
        assert (tag, rng) == ("common", "local")
        assert locs == ["Dragon Kingdom of Lugunica"]

    def test_a_variant_suffix_is_the_same_place(self):
        """Live: the child followed "Dragon Kingdom of Lugunica (Lite)", an
        abridged alternate — so the place resolved to a name no scene will ever
        be standing in."""
        recs = {r["title"]: r for r in parse_structure(_book())}
        _, _, locs = derive_knowledge(recs["Lugunica Currency"])
        assert "(Lite)" not in locs[0]

    def test_a_power_system_is_not_common_knowledge(self):
        recs = {r["title"]: r for r in parse_structure(_book())}
        tag, rng, _ = derive_knowledge(recs["Authority of Sloth"])
        assert tag == "esoteric"
        assert rng == "global"

    def test_authoring_instructions_are_excluded_entirely(self):
        """The most valuable thing the tree buys. A "Writing Style" entry is an
        instruction to the ENGINE and must never reach a character as something
        their world knows — and that is invisible in a flat import."""
        book = [{"uid": 0, "displayIndex": 0, "comment": "═══════[Setting]═══════",
                 "content": "x", "key": []},
                {"uid": 1, "displayIndex": 1, "comment": "[☰] Writing Style [☰]",
                 "content": "Write in past tense.", "key": []}]
        recs = {r["title"]: r for r in parse_structure(book)}
        assert derive_knowledge(recs["Writing Style"]) == (None, None, None)

    def test_an_unmatched_section_defaults_to_common_and_global(self):
        """The honest default for a published setting book, whose whole purpose
        is describing what is true and known in that world."""
        book = [{"uid": 0, "displayIndex": 0, "comment": "═══════[Cuisine]═══════",
                 "content": "x", "key": []},
                {"uid": 1, "displayIndex": 1, "comment": "[🍲] Stew", "content": "y",
                 "key": []}]
        recs = {r["title"]: r for r in parse_structure(book)}
        assert derive_knowledge(recs["Stew"]) == ("common", "global", None)


def test_the_import_carries_all_of_it_through(temp_db):
    """End to end, on the shape the live book actually has. Before this, an
    imported book had a title on 0 of 310 rows."""
    from story import importers
    book = {"entries": {str(i): e for i, e in enumerate(_book())}}
    lb, _n = importers.import_lorebook(book, name="tree", reinterpret=False)
    rows = temp_db.q("SELECT * FROM lore_entries WHERE lorebook_id=?", (lb,))
    by_title = {r["title"]: r for r in rows}
    assert all(r["title"] for r in rows), "every entry must carry its title"
    currency = by_title["Lugunica Currency"]
    assert currency["knowledge_tag"] == "common"
    assert currency["knowledge_range"] == "local"
    assert "Dragon Kingdom of Lugunica" in (currency["knowledge_locations"] or "")


def test_the_child_tree_lands_as_refines_entry_ids(temp_db):
    """`[›]` is a parent link, and `relations.refines_entry_ids` already means
    exactly that -- "Lugunica Currency" refines "Dragon Kingdom of Lugunica".

    Using the existing vocabulary is the point: the hierarchy needs no new
    column and moves no entry between books, which would have orphaned every
    `chat_lorebooks` link and every `entry_uid` a story has already cited.
    """
    import json

    from story import importers
    book = {"entries": {str(i): e for i, e in enumerate(_book())}}
    lb, _n = importers.import_lorebook(book, name="tree", reinterpret=False)
    rows = {r["id"]: r for r in
            temp_db.q("SELECT * FROM lore_entries WHERE lorebook_id=?", (lb,))}
    by_title = {r["title"]: r for r in rows.values()}

    calamity = by_title["Great Calamity"]
    parent_ids = json.loads(calamity["relations"])["refines_entry_ids"]
    assert rows[parent_ids[0]]["title"] == "World History"


def test_a_leaf_has_no_parent_link(temp_db):
    """Only `[›]` children hang from anything. A leaf linking to whatever
    preceded it would invent a hierarchy the author did not draw."""
    import json

    from story import importers
    book = {"entries": {str(i): e for i, e in enumerate(_book())}}
    lb, _n = importers.import_lorebook(book, name="tree", reinterpret=False)
    rows = temp_db.q("SELECT * FROM lore_entries WHERE lorebook_id=?", (lb,))
    history = next(r for r in rows if r["title"] == "World History")
    assert not json.loads(history["relations"] or "{}").get("refines_entry_ids")


def test_world_mechanics_do_not_become_local_knowledge(temp_db):
    """Knowing the local currency is a different claim from knowing how souls
    reincarnate. Sections that describe the world's machinery resolve global,
    and only what the author filed under a Locations heading is ever local."""
    recs = {r["title"]: r for r in parse_structure(_book())}
    assert derive_knowledge(recs["Authority of Sloth"])[1] == "global"
    assert derive_knowledge(recs["Lugunica Currency"])[1] == "local"


def test_a_category_cannot_be_handed_to_derive_knowledge(sample_records=None):
    """`derive_knowledge(record, category=None)` accepted a category and never
    mentioned it again -- while the twenty-line comment directly above it
    argues at length that using the entry's category as a second signal was
    tried and MEASURED WORSE (`guess_category` calls four real places
    `mechanic`/`myth`, and calls `Lugunica Currency` a `mechanic`, which is
    the one case the whole feature exists to serve).

    So a reader who supplied one got the behaviour the comment says was
    rejected -- which is to say, no behaviour at all, silently. The parameter
    is gone; supplying one is now an error rather than a quiet no-op.
    """
    import pytest

    with pytest.raises(TypeError):
        derive_knowledge({"title": "Lugunica Currency"}, "mechanic")
