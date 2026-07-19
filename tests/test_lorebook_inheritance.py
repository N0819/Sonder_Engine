"""Regression tests for lorebook parent/child inheritance actually being
respected. Before this fix, inheritance_mode was stored, edited, copied
on duplication, and snapshotted -- but never once consulted at read
time: resolve_lorebook_graph climbed every ancestor and expanded every
child unconditionally regardless of mode, so 'isolated' behaved
identically to 'inherit'. search_lore also scored every resolved book's
entries as equals regardless of how many hops up/down the hierarchy they
came from."""

from __future__ import annotations

import time

import memory


def _make_book(db, name, parent_id=None, inheritance_mode="inherit", chat_id=None):
    return db.qi(
        "INSERT INTO lorebooks(name,chat_id,parent_id,inheritance_mode) VALUES(?,?,?,?)",
        (name, chat_id, parent_id, inheritance_mode),
    )


class TestResolveLorebookGraphInheritanceMode:
    def test_isolated_child_is_excluded_entirely(self, temp_db):
        region = _make_book(temp_db, "Region")
        _make_book(temp_db, "Isolated Location", parent_id=region, inheritance_mode="isolated")

        resolved = {r["id"] for r in memory.resolve_lorebook_graph([region])}

        assert region in resolved
        assert len(resolved) == 1

    def test_inherit_child_is_included_at_full_weight(self, temp_db):
        region = _make_book(temp_db, "Region")
        location = _make_book(temp_db, "Location", parent_id=region, inheritance_mode="inherit")

        resolved = {r["id"]: r for r in memory.resolve_lorebook_graph([region])}

        assert location in resolved
        assert resolved[location]["weight"] == 0.95

    def test_reference_only_child_is_included_at_reduced_weight(self, temp_db):
        region = _make_book(temp_db, "Region")
        ref_book = _make_book(temp_db, "Reference Location", parent_id=region, inheritance_mode="reference_only")

        resolved = {r["id"]: r for r in memory.resolve_lorebook_graph([region])}

        assert ref_book in resolved
        assert resolved[ref_book]["weight"] == 0.5

    def test_ancestor_climb_stops_at_a_non_inherit_hop(self, temp_db):
        # Region -> (isolated) -> Location: starting from Location, the
        # ancestor climb must NOT surface Region, since Location's own
        # edge to its parent is isolated.
        region = _make_book(temp_db, "Region")
        location = _make_book(temp_db, "Location", parent_id=region, inheritance_mode="isolated")

        resolved = {r["id"] for r in memory.resolve_lorebook_graph([location])}

        assert location in resolved
        assert region not in resolved

    def test_ancestor_climb_continues_through_inherit_hops(self, temp_db):
        continent = _make_book(temp_db, "Continent")
        region = _make_book(temp_db, "Region", parent_id=continent, inheritance_mode="inherit")
        location = _make_book(temp_db, "Location", parent_id=region, inheritance_mode="inherit")

        resolved = {r["id"] for r in memory.resolve_lorebook_graph([location])}

        assert region in resolved
        assert continent in resolved


class TestChatLorebookWeights:
    def test_matches_chat_lorebook_ids_membership(self, temp_db):
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Test", "", time.time()),
        )
        region = _make_book(temp_db, "Region", chat_id=chat_id)
        location = _make_book(temp_db, "Location", parent_id=region, chat_id=chat_id)
        temp_db.qi(
            "INSERT INTO chat_lorebooks(chat_id,lorebook_id,enabled) VALUES(?,?,1)",
            (chat_id, location),
        )

        ids = set(memory.chat_lorebook_ids(chat_id))
        weights = memory.chat_lorebook_weights(chat_id)

        assert set(weights.keys()) == ids
        assert weights[location] == 1.0
        assert weights[region] < 1.0


class TestSearchLoreWeighting:
    def test_weighted_dict_can_override_ranking(self, temp_db):
        continent = _make_book(temp_db, "Continent")
        location = _make_book(temp_db, "Location", parent_id=continent)

        # Near-identical content in both books -- the base relevance score
        # for each is close enough that ordinary per-row scoring noise
        # (FTS5's ranking accounts for corpus-wide term stats, so two
        # separate rows with the "same" text don't score bit-for-bit
        # identically) can go either way on its own. A decisive weight
        # gap must be able to override that noise deterministically --
        # this is the actual thing being tested, not a specific realistic
        # production weight value (chat_lorebook_weights' real gaps, e.g.
        # 1.0 vs ~0.81 for a two-hop ancestor, are deliberately a gentle
        # nudge rather than a hard override).
        memory.add_lore(continent, "old lore", "The ancient tale repeats.")
        memory.add_lore(location, "old lore", "The ancient tale repeats.")

        weights = {continent: 0.01, location: 1.0}
        results = memory.search_lore(weights, "the ancient tale repeats", k=2)

        assert results[0]["book_id"] == location

    def test_unweighted_list_still_works_exactly_as_before(self, temp_db):
        book = _make_book(temp_db, "Plain Book")
        memory.add_lore(book, "castle", "A stone castle on the hill.")

        results = memory.search_lore([book], "castle", k=5)

        assert len(results) == 1
        assert results[0]["book_id"] == book
