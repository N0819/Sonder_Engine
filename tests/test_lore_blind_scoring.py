"""Lore left behind by a retired embedding model.

`_cos` returns 0.0 when two vectors disagree in length. It cannot raise -- it
is called in a ranking loop over rows embedded at different times -- and 0.0 is
also the honest score for a genuinely unrelated entry. So an entry carrying a
vector from a model that has since been replaced is indistinguishable from one
that simply does not match the query, and it forfeits the 0.65 weight it can
never win back.

Measured on a live corpus that had run this way for months: 1,061 of 1,418 lore
entries carried 256-dimension vectors while the configured model emits 2,560.
Three quarters of the corpus was competing on the 0.35 keyword term alone. One
lorebook was 10 of 15 stale, including the single room a reader kept asking
after and could not get the agents to describe. Every symptom pointed at the
mapping agent ignoring its lorebook. Nothing anywhere reported the mismatch.
"""

from __future__ import annotations

import numpy as np

import memory


def _book(db, name="Tamamo's Shrine"):
    return db.qi("INSERT INTO lorebooks(name) VALUES(?)", (name,))


def _entry(db, book_id, title, content, dims, keys=""):
    """One lore entry carrying a vector of exactly `dims` float32s."""
    vec = np.ones(dims, dtype=np.float32) / np.sqrt(dims)
    return db.qi(
        "INSERT INTO lore_entries(lorebook_id,title,keys,content,category,"
        "embedding) VALUES(?,?,?,?,?,?)",
        (book_id, title, keys, content, "layout", vec.tobytes()))


def _stub_embedder(monkeypatch, dims):
    """The configured model, emitting `dims`-wide query vectors."""
    def embed_texts(texts):
        v = np.ones(dims, dtype=np.float32) / np.sqrt(dims)
        return [v for _ in texts]
    monkeypatch.setattr(memory, "embed_texts", embed_texts)


def test_a_stale_vector_is_counted_rather_than_silently_scoring_zero(
        temp_db, monkeypatch, caplog):
    """THE DEFECT. The entry still ranks -- on 0.35 of the score -- so nothing
    crashes, nothing is empty, and the only symptom is a lorebook the agents
    appear to ignore. The count is the whole repair at this layer.
    """
    book = _book(temp_db)
    _entry(temp_db, book, "Third Floor", "Tamamo's quarters, the roost", 256)
    _entry(temp_db, book, "Main Hall", "the shrine's first floor", 2560)
    _stub_embedder(monkeypatch, 2560)
    monkeypatch.setattr(memory, "_kw_scores", lambda table, query: {})

    with caplog.at_level("WARNING"):
        memory.search_lore([book], "where is the third floor", k=8)

    assert "scored 1 of 2 entries blind" in caplog.text


def test_a_corpus_that_matches_the_model_says_nothing(temp_db, monkeypatch,
                                                      caplog):
    """A warning on every search is a warning nobody reads. The common case
    must stay silent or the signal is worthless on the day it matters.
    """
    book = _book(temp_db)
    _entry(temp_db, book, "Main Hall", "the shrine's first floor", 2560)
    _stub_embedder(monkeypatch, 2560)
    monkeypatch.setattr(memory, "_kw_scores", lambda table, query: {})

    with caplog.at_level("WARNING"):
        memory.search_lore([book], "the main hall", k=8)

    assert "blind" not in caplog.text


def test_the_stale_entry_still_comes_back_rather_than_being_dropped(
        temp_db, monkeypatch):
    """Counting must not turn a degraded entry into a missing one. A reader
    losing the room entirely is worse than a reader getting it ranked low, and
    the migration that fixes this properly has not run yet.
    """
    book = _book(temp_db)
    stale = _entry(temp_db, book, "Third Floor", "the roost", 256)
    _stub_embedder(monkeypatch, 2560)
    monkeypatch.setattr(memory, "_kw_scores", lambda table, query: {})

    got = memory.search_lore([book], "roost", k=8)
    assert [row["id"] for row in got] == [stale]


def test_the_corpus_can_be_asked_before_it_is_trusted(temp_db, monkeypatch):
    """`search_lore`'s warning only speaks when a search runs, which makes "is
    my lore reachable" something you discover by accident mid-story. This is
    the same question asked on demand.
    """
    good = _book(temp_db, "Current Book")
    bad = _book(temp_db, "Stranded Book")
    _entry(temp_db, good, "Fine", "current", 2560)
    _entry(temp_db, bad, "Third Floor", "the roost", 256)
    _entry(temp_db, bad, "Second Floor", "meditation", 256)
    _stub_embedder(monkeypatch, 2560)

    health = memory.lore_embedding_health()
    assert health["total"] == 3
    assert health["stale"] == 2
    assert health["current_dimensions"] == 2560
    # Only the afflicted book is named, so the report is short enough to read.
    assert set(health["books"]) == {bad}
    assert health["books"][bad] == {"total": 2, "stale": 2}


def test_an_unembedded_entry_is_not_called_stale(temp_db, monkeypatch):
    """Never embedded and embedded by the wrong model need different repairs --
    one needs a first pass, the other a re-run -- so conflating them would send
    the fix to the wrong place.
    """
    book = _book(temp_db)
    temp_db.qi("INSERT INTO lore_entries(lorebook_id,title,content,category) "
               "VALUES(?,?,?,?)", (book, "No vector", "never embedded",
                                   "layout"))
    _entry(temp_db, book, "Third Floor", "the roost", 256)
    _stub_embedder(monkeypatch, 2560)

    health = memory.lore_embedding_health([book])
    assert health["stale"] == 1
    assert health["unembedded"] == 1


# --- the rebuild, and why it has to live in the rebuild ---------------------

def _live_embedder(monkeypatch, dims=2560):
    """A provider that answers, at `dims` wide."""
    from providers import EmbeddingBatch

    def meta(texts):
        v = np.ones(dims, dtype=np.float32) / np.sqrt(dims)
        return EmbeddingBatch(vectors=[v for _ in texts],
                              model_key="test:1:model", dimensions=dims,
                              fallback=False)
    monkeypatch.setattr(memory, "embed_texts_meta", meta)
    monkeypatch.setattr(memory, "embed_texts",
                        lambda texts: meta(texts).vectors)


def test_the_rebuild_now_covers_lorebooks(temp_db, monkeypatch):
    """THE SETTINGS TOOL DID NOT REACH LORE. `rebuild_embeddings` repaired
    memories and summaries and left `lore_entries` alone, so the one control a
    host has for "my embedding model changed" silently fixed half the corpus.
    """
    book = _book(temp_db)
    chat = temp_db.qi("INSERT INTO chats(name,lorebook_id,created) "
                      "VALUES(?,?,?)", ("A story", book, 1.0))
    stale = _entry(temp_db, book, "Third Floor", "the roost", 256)
    fresh = _entry(temp_db, book, "Main Hall", "the first floor", 2560)
    _live_embedder(monkeypatch, 2560)

    report = memory.rebuild_embeddings(chat_id=chat)

    assert report["lore"] == 1, report
    got = {r["id"]: len(memory._vec(r["embedding"]))
           for r in temp_db.q("SELECT id, embedding FROM lore_entries")}
    assert got[stale] == 2560, "the stranded entry was not rebuilt"
    assert got[fresh] == 2560


def test_a_rebuild_uses_the_same_document_update_lore_builds(temp_db,
                                                             monkeypatch):
    """A vector built from different text is not comparable with one built
    from the same text, so a rebuild that quietly changed the recipe would be
    a subtler version of the bug it fixes. `update_lore` embeds
    `keys + " " + content` and so must this.
    """
    book = _book(temp_db)
    chat = temp_db.qi("INSERT INTO chats(name,lorebook_id,created) "
                      "VALUES(?,?,?)", ("A story", book, 1.0))
    _entry(temp_db, book, "Third Floor", "the roost", 256, keys="roost, third")
    seen = []
    from providers import EmbeddingBatch

    def meta(texts):
        seen.extend(texts)
        v = np.ones(2560, dtype=np.float32) / np.sqrt(2560)
        return EmbeddingBatch(vectors=[v for _ in texts],
                              model_key="test:1:model", dimensions=2560,
                              fallback=False)
    monkeypatch.setattr(memory, "embed_texts_meta", meta)

    memory.rebuild_embeddings(chat_id=chat)

    assert "roost, third the roost" in seen, seen


def test_a_provider_hiccup_never_writes_a_fallback_over_lore(temp_db,
                                                             monkeypatch):
    """A DEGRADED PROVIDER INVERTS THE STALENESS TEST, and this reconciler
    fires on every checkpoint restore. Lore has no `embedding_model` column,
    so "stale" means the wrong WIDTH -- and against a 256-wide crc32 fallback
    every real 2,560-wide entry reads as stale. Without this guard, one reroll
    during a provider hiccup downgrades the whole corpus the pass exists to
    protect.
    """
    book = _book(temp_db)
    chat = temp_db.qi("INSERT INTO chats(name,lorebook_id,created) "
                      "VALUES(?,?,?)", ("A story", book, 1.0))
    stale = _entry(temp_db, book, "Third Floor", "the roost", 256)
    from providers import EmbeddingBatch

    def degraded(texts):
        v = np.ones(256, dtype=np.float32) / np.sqrt(256)
        return EmbeddingBatch(vectors=[v for _ in texts],
                              model_key="cheap:crc32:256", dimensions=256,
                              fallback=True, error="provider down")
    monkeypatch.setattr(memory, "embed_texts_meta", degraded)

    report = memory.rebuild_embeddings(chat_id=chat)

    # Nothing rebuilt, and nothing downgraded. Lore staleness is measured by
    # WIDTH, so a degraded provider inverts the test -- every real 2,560-wide
    # entry would read as stale against a 256-wide fallback target. The pass
    # declines rather than "migrating" a corpus into the crc32 hash.
    assert report["lore"] == 0
    row = temp_db.q("SELECT embedding FROM lore_entries WHERE id=?", (stale,),
                    one=True)
    assert len(memory._vec(row["embedding"])) == 256, "downgraded a real vector"


def test_a_rebuild_scoped_to_one_chat_leaves_other_books_alone(temp_db,
                                                               monkeypatch):
    """The reconciler runs on every checkpoint restore. Re-embedding an
    unrelated 300-entry lorebook on somebody's reroll would be a surprise bill.
    """
    mine = _book(temp_db, "Mine")
    theirs = _book(temp_db, "Somebody else's")
    chat = temp_db.qi("INSERT INTO chats(name,lorebook_id,created) "
                      "VALUES(?,?,?)", ("A story", mine, 1.0))
    _entry(temp_db, mine, "Third Floor", "the roost", 256)
    untouched = _entry(temp_db, theirs, "Elsewhere", "not in this story", 256)
    _live_embedder(monkeypatch, 2560)

    report = memory.rebuild_embeddings(chat_id=chat)

    assert report["lore"] == 1
    row = temp_db.q("SELECT embedding FROM lore_entries WHERE id=?",
                    (untouched,), one=True)
    assert len(memory._vec(row["embedding"])) == 256
