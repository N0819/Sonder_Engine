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

    def meta(texts, **_k):
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

    def meta(texts, **_k):
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

    def degraded(texts, **_k):
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


# --- the stamp, and the one-time retrofit that fills it in ------------------

def test_a_new_entry_records_what_embedded_it(temp_db, monkeypatch):
    """THE ROOT OF THE SILENCE. `add_lore` called `embed_texts`, which returns
    bare vectors, so the write path could not tell a real embedding from
    `cheap_embed`'s crc32 hash -- and `embed_texts_meta` degrades to that hash
    on ANY provider error. 1,061 of 1,418 entries were written that way and
    nothing recorded it, because there was nowhere to record it.
    """
    book = _book(temp_db)
    _live_embedder(monkeypatch, 2560)
    entry = memory.add_lore(book, "roost", "Tamamo's quarters")

    row = temp_db.q("SELECT embedding_model, embedding_dim FROM lore_entries "
                    "WHERE id=?", (entry,), one=True)
    assert row["embedding_model"] == "test:1:model"
    assert row["embedding_dim"] == 2560


def test_an_entry_written_during_an_outage_says_it_was(temp_db, monkeypatch):
    """The whole point. A degraded provider must leave a mark at the moment it
    happens rather than 165 turns later, when the only evidence left is a
    lorebook the agents appear to ignore.
    """
    from providers import EmbeddingBatch
    book = _book(temp_db)
    monkeypatch.setattr(memory, "embed_texts_meta", lambda texts, **_k: EmbeddingBatch(
        vectors=[np.ones(256, dtype=np.float32) / 16 for _ in texts],
        model_key="cheap:crc32:256", dimensions=256, fallback=True,
        error="provider down"))
    entry = memory.add_lore(book, "roost", "Tamamo's quarters")

    row = temp_db.q("SELECT embedding_model FROM lore_entries WHERE id=?",
                    (entry,), one=True)
    assert row["embedding_model"] == "cheap:crc32:256"


def test_the_backfill_identifies_the_fallback_from_the_bytes(temp_db):
    """PROVIDER-INDEPENDENT BY CONSTRUCTION, which is why it can be trusted.
    `cheap_embed` is a pure function of the text, so "is this the fallback" is
    answerable with the provider face-down. Width is not -- width is relative
    to whatever the provider emits right now, which is exactly how a degraded
    provider inverts the question.

    Verified against the live corpus this way: 40 of 40 sampled 1024-byte
    entries were byte-identical to `cheap_embed` of their own text.
    """
    from providers import cheap_embed
    book = _book(temp_db)
    text_keys, text_content = "roost", "Tamamo's quarters on the third floor"
    fallback_vec = np.asarray(
        cheap_embed(text_keys + " " + text_content), dtype=np.float32)
    stranded = temp_db.qi(
        "INSERT INTO lore_entries(lorebook_id,keys,content,category,embedding) "
        "VALUES(?,?,?,?,?)",
        (book, text_keys, text_content, "layout", fallback_vec.tobytes()))
    real = _entry(temp_db, book, "Main Hall", "the first floor", 2560)

    report = memory.backfill_lore_embedding_stamps()

    assert report["fallback"] == 1 and report["real"] == 1
    got = {r["id"]: r["embedding_model"] for r in
           temp_db.q("SELECT id, embedding_model FROM lore_entries")}
    assert got[stranded] == "cheap:crc32:256"
    # NOT a model name: the bytes cannot say which real model made them, and
    # inventing one would record a guess as a fact.
    assert got[real] == "unknown:2560"


def test_the_backfill_does_not_call_a_real_vector_a_fallback(temp_db):
    """A 256-wide vector that is NOT the hash of its own text is some other
    model's output, and stamping it `cheap:crc32:256` would send the rebuild
    to overwrite a real embedding.
    """
    book = _book(temp_db)
    imposter = _entry(temp_db, book, "Third Floor", "the roost", 256)

    memory.backfill_lore_embedding_stamps()

    row = temp_db.q("SELECT embedding_model FROM lore_entries WHERE id=?",
                    (imposter,), one=True)
    assert row["embedding_model"] == "unknown:256"


def test_the_backfill_is_resumable_and_does_not_rescan(temp_db):
    """It hashes a row per entry, so a corpus-sized rescan on every call is
    the difference between a one-time retrofit and a permanent mechanism.
    """
    book = _book(temp_db)
    _entry(temp_db, book, "Third Floor", "the roost", 256)

    assert memory.backfill_lore_embedding_stamps()["scanned"] == 1
    assert memory.backfill_lore_embedding_stamps()["scanned"] == 0


def test_the_rebuild_prefers_the_stamp_over_the_width(temp_db, monkeypatch):
    """Width cannot tell two models sharing a width apart. Once a row carries
    a stamp, that is the exact answer and the proxy is not consulted.
    """
    book = _book(temp_db)
    chat = temp_db.qi("INSERT INTO chats(name,lorebook_id,created) "
                      "VALUES(?,?,?)", ("A story", book, 1.0))
    # Same WIDTH as the live model, but a different model wrote it.
    wrong_model = _entry(temp_db, book, "Third Floor", "the roost", 2560)
    temp_db.qi("UPDATE lore_entries SET embedding_model=?,embedding_dim=? "
               "WHERE id=?", ("someone-else:1:model", 2560, wrong_model))
    _live_embedder(monkeypatch, 2560)

    report = memory.rebuild_embeddings(chat_id=chat)

    assert report["lore"] == 1, "a width-only check would have skipped this"
    row = temp_db.q("SELECT embedding_model FROM lore_entries WHERE id=?",
                    (wrong_model,), one=True)
    assert row["embedding_model"] == "test:1:model"


def test_health_answers_correctly_with_no_provider_at_all(temp_db,
                                                          monkeypatch):
    """MEASUREMENT MUST NOT DECLINE DURING AN OUTAGE -- that is exactly when
    somebody is looking. `embed_texts` degrades silently to a 256-wide hash,
    so asking IT what the live width is turns every real 2,560-wide entry into
    a "stale" one and reports the corpus backwards.

    This is not hypothetical: a dry run built that way named the 357 CURRENT
    entries as the stale ones, and would have overwritten the only good
    vectors in the corpus had it been believed.
    """
    book = _book(temp_db)
    # The engine's own record of what it embeds with.
    chat = temp_db.qi("INSERT INTO chats(name,created) VALUES(?,?)",
                      ("A story", 1.0))
    char = temp_db.qi("INSERT INTO characters(name,sheet,source,created) "
                      "VALUES(?,?,?,?)", ("Someone", "{}", "{}", 1.0))
    temp_db.qi("INSERT INTO memories(chat_id,char_id,kind,content,"
               "embedding_dim,embedding_model) VALUES(?,?,?,?,?,?)",
               (chat, char, "episodic", "x", 2560, "real:1:model"))
    stranded = _entry(temp_db, book, "Third Floor", "the roost", 256)
    temp_db.qi("UPDATE lore_entries SET embedding_model=?,embedding_dim=? "
               "WHERE id=?", ("cheap:crc32:256", 256, stranded))
    live = _entry(temp_db, book, "Main Hall", "the first floor", 2560)
    temp_db.qi("UPDATE lore_entries SET embedding_model=?,embedding_dim=? "
               "WHERE id=?", ("real:1:model", 2560, live))

    def no_provider(texts):
        raise RuntimeError("provider down")
    monkeypatch.setattr(memory, "embed_texts", no_provider)

    health = memory.lore_embedding_health([book])

    assert health["current_dimensions"] == 2560
    assert health["probed_provider"] is False
    assert health["stale"] == 1 and health["fallback"] == 1


def test_health_never_calls_the_fallback_the_live_model(temp_db):
    """`cheap:crc32:256` is easily the MAJORITY on a corpus that needs
    repairing -- 1,031 of 1,418 on the one that prompted this. Taking the most
    common stamp as "live" would report a wholly broken corpus as healthy.
    """
    book = _book(temp_db)
    for i in range(5):
        eid = _entry(temp_db, book, "Stale %d" % i, "text", 256)
        temp_db.qi("UPDATE lore_entries SET embedding_model=?,embedding_dim=? "
                   "WHERE id=?", ("cheap:crc32:256", 256, eid))
    good = _entry(temp_db, book, "Real", "text", 2560)
    temp_db.qi("UPDATE lore_entries SET embedding_model=?,embedding_dim=? "
               "WHERE id=?", ("real:1:model", 2560, good))

    health = memory.lore_embedding_health([book])

    assert health["current_dimensions"] == 2560, "the fallback won the vote"
    assert health["stale"] == 5


def test_a_narrower_live_model_does_not_invert_the_reference(temp_db,
                                                             monkeypatch):
    """WIDEST-REAL-STAMP IS RIGHT TODAY AND WRONG ONE MODEL CHANGE FROM NOW.

    It holds only while the live space is the widest one. The moment a
    genuinely current model is NARROWER than a retired one -- 1,024 real
    against stranded 2,560 -- widest picks the stranded space as the reference
    and reports every correct row as needing repair. The healthy probe is
    authoritative precisely so that cannot happen.
    """
    from providers import EmbeddingBatch
    book = _book(temp_db)
    narrow_but_live = _entry(temp_db, book, "Current", "text", 1024)
    temp_db.qi("UPDATE lore_entries SET embedding_model=?,embedding_dim=? "
               "WHERE id=?", ("new-narrow:1:model", 1024, narrow_but_live))
    wide_but_retired = _entry(temp_db, book, "Retired", "text", 2560)
    temp_db.qi("UPDATE lore_entries SET embedding_model=?,embedding_dim=? "
               "WHERE id=?", ("old-wide:1:model", 2560, wide_but_retired))

    monkeypatch.setattr(memory, "embed_texts_meta", lambda texts, **_k: EmbeddingBatch(
        vectors=[np.ones(1024, dtype=np.float32) / 32 for _ in texts],
        model_key="new-narrow:1:model", dimensions=1024, fallback=False))

    health = memory.lore_embedding_health([book])

    assert health["current_dimensions"] == 1024
    # The retired wide entry is the stale one, not the live narrow one.
    assert health["stale"] == 1


def test_a_degraded_probe_is_not_mistaken_for_the_live_model(temp_db,
                                                             monkeypatch):
    """`embed_texts_meta` reports `fallback`; `embed_texts` cannot. Trusting a
    degraded probe is how an earlier version of this reported the corpus
    backwards and would have overwritten every good vector in it.
    """
    from providers import EmbeddingBatch
    book = _book(temp_db)
    good = _entry(temp_db, book, "Real", "text", 2560)
    temp_db.qi("UPDATE lore_entries SET embedding_model=?,embedding_dim=? "
               "WHERE id=?", ("real:1:model", 2560, good))

    monkeypatch.setattr(memory, "embed_texts_meta", lambda texts, **_k: EmbeddingBatch(
        vectors=[np.ones(256, dtype=np.float32) / 16 for _ in texts],
        model_key="cheap:crc32:256", dimensions=256, fallback=True,
        error="down"))

    health = memory.lore_embedding_health([book])

    assert health["current_dimensions"] == 2560, "believed the fallback probe"
    assert health["stale"] == 0
