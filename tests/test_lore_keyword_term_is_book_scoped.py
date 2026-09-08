"""The keyword half of lore ranking reads only the books this story may read
(review 2026-09-07 A59).

`lore_fts` is ONE index over every lorebook in the library and carries no book
column, so `search_lore`'s `_kw_scores("lore_fts", query)` matched the whole
table with `LIMIT 50`. Two things followed on any library with more than one
story in it: the fifty slots were spent on entries the calling chat cannot
read, and the `best` normaliser -- which is what puts the term on the scale
the 0.65/0.35 blend was tuned for -- was computed from those same foreign
rows. An in-scope entry that matched perfectly could therefore score a
fraction of 1.0, or fall out of the window entirely and take 0.0.

Measured on the 2026-09 bench copy of chat 114 (`bench.db`): the chat reads 1
of 196 books, 5 of 1,237 entries. Across five ordinary queries the unscoped
window held 0, 1, 0, 4 and 0 in-scope entries -- three of the five queries
handed the mapping stage a keyword term of exactly 0.0 for every entry the
story owns.

The rule that now holds: `_kw_scores` takes a `scope` predicate, and
`search_lore` scopes to the entry ids of the books it was asked about -- the
same predicate `_lexical_memory_ranking` has always had, expressed the only
way an external-content FTS with no columns of its own allows.
"""

from __future__ import annotations

from mind import memory_lore_entries
from mind.memory import _kw_scores, add_lore, search_lore


def _book(temp_db, name, chat_id=None):
    return temp_db.qi(
        "INSERT INTO lorebooks(name,chat_id,book_type,summary) "
        "VALUES(?,?,?,?)", (name, chat_id, "general", ""))


def _library(temp_db, *, mine_entries, theirs_entries):
    """One book this story reads, and one crowded book it does not."""
    mine = _book(temp_db, "My canon")
    theirs = _book(temp_db, "Another story's canon")
    mine_ids = [add_lore(mine, keys, content, turn_added=1)
                for keys, content in mine_entries]
    for keys, content in theirs_entries:
        add_lore(theirs, keys, content, turn_added=1)
    return mine, theirs, mine_ids


#: One long entry that says "granary" once -- an ordinary story note -- against
#: short foreign entries that say nothing else. BM25 prefers the short ones, so
#: the story's own entry is both out-scored and, at sixty of them, out of the
#: fifty-slot window entirely.
_MINE = ("The granary is kept by the miller, and the account of it runs on "
         "at some length about the roof, the rats, the ledger, the tithe, "
         "the seasons, the doors, the carts, the sacks and the men. " * 6)


def test_a_crowded_foreign_book_no_longer_eats_the_window(temp_db):
    """Sixty foreign entries all matching the query filled every one of the
    fifty slots, leaving nothing for the one entry the story owns."""
    mine, theirs, mine_ids = _library(
        temp_db,
        mine_entries=[("granary", _MINE)],
        theirs_entries=[("granary", "granary %d" % n) for n in range(60)])

    unscoped = _kw_scores("lore_fts", "granary")
    assert mine_ids[0] not in unscoped, (
        "the fixture must reproduce the defect: the in-scope entry has to be "
        "crowded out of the unscoped window")

    scoped = _kw_scores(
        "lore_fts", "granary",
        scope=("rowid IN (SELECT id FROM lore_entries WHERE lorebook_id IN "
               "(?))", [mine]))

    assert set(scoped) == {mine_ids[0]}
    assert scoped[mine_ids[0]] == 1.0, (
        "the normaliser is the best IN-SCOPE match, so the story's own best "
        "entry gets the full weight the blend was tuned for")


def test_a_foreign_best_match_no_longer_sets_the_scale(temp_db):
    """The half that bites even when nothing is evicted: `best` is what puts
    the term on the 0.35 scale, and it was the best match in the LIBRARY."""
    mine, theirs, mine_ids = _library(
        temp_db,
        mine_entries=[("granary", _MINE)],
        theirs_entries=[("granary", "granary")])

    unscoped = _kw_scores("lore_fts", "granary")
    assert unscoped[mine_ids[0]] < 1.0, unscoped

    scoped = _kw_scores(
        "lore_fts", "granary",
        scope=("rowid IN (SELECT id FROM lore_entries WHERE lorebook_id IN "
               "(?))", [mine]))

    assert scoped[mine_ids[0]] == 1.0


def test_search_lore_ranks_the_story_it_was_asked_about(temp_db):
    mine, theirs, mine_ids = _library(
        temp_db,
        mine_entries=[("granary", "The granary is kept by the miller."),
                      ("smith", "The smith works the forge by the bridge.")],
        theirs_entries=[("granary", "A granary in another story, number %d." % n)
                        for n in range(60)])

    hits = search_lore([mine], "granary", k=5)

    assert [h["id"] for h in hits][:1] == mine_ids[:1]
    assert all(h["book_id"] == mine for h in hits)


def test_the_unscoped_call_is_unchanged_for_every_other_caller(temp_db):
    """`scope` is opt-in: a caller that reads a whole index still does."""
    mine, theirs, mine_ids = _library(
        temp_db,
        mine_entries=[("bridge", "A bridge over the river.")],
        theirs_entries=[("bridge", "Another bridge entirely.")])

    both = _kw_scores("lore_fts", "bridge")

    assert mine_ids[0] in both and len(both) == 2


def test_search_lore_passes_a_scope_and_gets_a_real_keyword_term(
        temp_db, monkeypatch):
    """The wiring, not the parameter. The three tests above build the scope
    tuple themselves, so they pin `_kw_scores`' new argument and would pass
    against a `search_lore` that never uses it; this one records what
    `search_lore` ACTUALLY computes for the entry the story owns.

    Patched on `mind.memory_lore_entries`, which is where `search_lore`
    resolves the name -- `memory_common` defines it, but the import at the top
    of `memory_lore_entries` bound it into that module's globals, so a patch
    on the definer (or on the `mind.memory` facade) is inert here.
    """
    mine, theirs, mine_ids = _library(
        temp_db,
        mine_entries=[("granary", _MINE)],
        theirs_entries=[("granary", "granary %d" % n) for n in range(60)])
    seen = {}
    real = memory_lore_entries._kw_scores

    def _spy(fts_table, query, limit=50, *, scope=None):
        got = real(fts_table, query, limit, scope=scope)
        seen["scope"] = scope
        seen["scores"] = got
        return got

    monkeypatch.setattr(memory_lore_entries, "_kw_scores", _spy)

    search_lore([mine], "granary", k=5)

    assert seen["scope"] is not None, (
        "search_lore asked for the whole library index")
    assert seen["scores"].get(mine_ids[0]) == 1.0, (
        "the story's own entry took the full keyword term; unscoped it was "
        "crowded out of the fifty-slot window and took 0.0")
