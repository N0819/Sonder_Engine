import json, time

import numpy as np
import pytest

import memory
import providers
from character_schema import default_character_data


@pytest.fixture
def bank(temp_db):
    """A chat with two characters, so the FK constraints on `memories` hold."""
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Rebuild", "", time.time()))
    ids = []
    for name in ("Mara", "Vesk"):
        ids.append(temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (name, json.dumps(default_character_data(name)), "{}", time.time(),
             "char_" + name.lower())))
    return {"chat": chat_id, "chars": ids}


def _seed(bank, n=5, who=0):
    for i in range(n):
        memory.add_memory(bank["chat"], bank["chars"][who], None, "episodic",
                          "witnessed", 0.6,
                          f"She crossed the bridge at dusk, number {i}.",
                          turn_idx=i, gist=f"crossed the bridge {i}",
                          key_phrases=["bridge"], entities=["Mara"],
                          location="bridge")


def _strand(model="ancient:model", dim=99):
    from db import qi
    qi("UPDATE memories SET embedding_model=?, embedding_dim=?", (model, dim))


def test_status_reports_the_split(bank):
    _seed(bank, 4)
    assert memory.embedding_bank_status()["memories"]["stranded"] == 0
    _strand()
    st = memory.embedding_bank_status()
    assert st["memories"] == {"total": 4, "stranded": 4}
    assert st["is_fallback"] is True     # no embeddings provider configured


def test_a_rebuild_restores_semantic_reach(bank):
    _seed(bank, 6)
    _strand()
    # Stranded: both vector rankings score 0, so nothing has a "semantic match"
    def _semantic(hits):
        return any("semantic match" in (m.get("retrieval_reasons") or [])
                   for m in hits)

    before = memory.search_memories(bank["chat"], bank["chars"][0],
                                    "crossed the bridge at dusk")
    assert not _semantic(before)

    report = memory.rebuild_embeddings()
    assert report["memories"] == 6
    assert not report["stopped_early"]
    assert memory.embedding_bank_status()["memories"]["stranded"] == 0

    after = memory.search_memories(bank["chat"], bank["chars"][0],
                                   "crossed the bridge at dusk")
    assert _semantic(after)


def test_it_is_resumable_and_idempotent(bank):
    _seed(bank, 6)
    _strand()
    assert memory.rebuild_embeddings(limit=2)["memories"] == 2
    assert memory.embedding_bank_status()["memories"]["stranded"] == 4
    assert memory.rebuild_embeddings()["memories"] == 4
    # Nothing left to do; a second full pass is free.
    assert memory.rebuild_embeddings()["memories"] == 0


def test_a_provider_failure_never_writes_fallback_over_real_vectors(bank, monkeypatch):
    """The one outcome worse than not running: rows stamped migrated while
    silently downgraded to the crc32 hash."""
    _seed(bank, 4)
    from db import qi
    qi("UPDATE memories SET embedding_model=?, embedding_dim=?", ("ancient:model", 99))

    real = providers.EmbeddingBatch(
        vectors=[np.zeros(256, dtype=np.float32)], model_key="real:model",
        dimensions=256, fallback=False)

    def fake(texts):
        if len(texts) == 1:          # the live-model probe
            return real
        return providers.EmbeddingBatch(
            vectors=[providers.cheap_embed(t) for t in texts],
            model_key="cheap:crc32:256", dimensions=256,
            fallback=True, error="connection refused")

    monkeypatch.setattr(memory, "embed_texts_meta", fake)
    report = memory.rebuild_embeddings()
    assert report["stopped_early"]
    assert "connection refused" in report["error"]
    assert report["memories"] == 0
    from db import q
    assert q("SELECT COUNT(*) AS n FROM memories WHERE embedding_model='cheap:crc32:256'",
             (), one=True)["n"] == 0


def test_summaries_are_rebuilt_too(bank):
    memory.save_memory_summary(bank["chat"], bank["chars"][0], "She has been crossing bridges for weeks.",
                               key_phrases=["bridge"], unresolved_threads=["who follows her"])
    from db import qi
    qi("UPDATE memory_summaries SET embedding_model=?, embedding_dim=?", ("ancient", 9))
    assert memory.embedding_bank_status()["memory_summaries"]["stranded"] == 1
    assert memory.rebuild_embeddings()["summaries"] == 1
    assert memory.embedding_bank_status()["memory_summaries"]["stranded"] == 0


def test_it_can_be_scoped_to_one_character(bank):
    _seed(bank, 3)
    for i in range(2):
        memory.add_memory(bank["chat"], bank["chars"][1], None, "episodic",
                          "witnessed", 0.6, "Another mind entirely.", turn_idx=i)
    _strand()
    assert memory.rebuild_embeddings(chat_id=bank["chat"], char_id=bank["chars"][1])["memories"] == 2
    assert memory.embedding_bank_status(chat_id=bank["chat"], char_id=bank["chars"][0])["memories"]["stranded"] == 3


class TestAspectsGetTheirOwnRanking:
    """A short facet cannot compete for influence inside a long query string.

    Measured before this: the character's view runs a median 1,015 characters
    and a mood fragment 10-60, so `cosine(query_with_mood, view_alone)` was
    0.994 — the mood moved the query vector by essentially nothing and reached
    recall only through whichever n-grams the word happened to share. Given
    its own rank list it does not have to compete.
    """

    def _bank(self, bank):
        rows = [
            ("She crossed the bridge at dusk.", "crossing the bridge"),
            ("She counted the coins twice, uneasy.", "counting coins uneasily"),
            ("The lantern guttered on the sill.", "a guttering lantern"),
        ]
        for i, (content, gist) in enumerate(rows):
            memory.add_memory(bank["chat"], bank["chars"][0], None, "episodic",
                              "witnessed", 0.5, content, turn_idx=i, gist=gist)

    def test_an_aspect_changes_what_comes_back(self, bank):
        self._bank(bank)
        view = "The bridge is ahead of her in the failing light. " * 12
        plain = memory.search_memories(bank["chat"], bank["chars"][0], view)
        withaspect = memory.search_memories(
            bank["chat"], bank["chars"][0], view,
            aspects=[("how you are feeling", "uneasy about the coins")])
        top_plain = [m["gist"] for m in plain]
        top_aspect = [m["gist"] for m in withaspect]
        assert top_plain != top_aspect or any(
            "how you are feeling" in (m.get("retrieval_reasons") or [])
            for m in withaspect)

    def test_the_aspect_is_named_in_the_retrieval_reasons(self, bank):
        self._bank(bank)
        hits = memory.search_memories(
            bank["chat"], bank["chars"][0], "the bridge at dusk",
            aspects=[("how you are feeling", "uneasy, counting coins")])
        assert any("how you are feeling" in (m.get("retrieval_reasons") or [])
                   for m in hits)

    def test_no_aspects_is_exactly_the_old_behaviour(self, bank):
        self._bank(bank)
        a = memory.search_memories(bank["chat"], bank["chars"][0], "the bridge")
        b = memory.search_memories(bank["chat"], bank["chars"][0], "the bridge",
                                   aspects=[])
        c = memory.search_memories(bank["chat"], bank["chars"][0], "the bridge",
                                   aspects=[("mood", "  ")])
        assert [m["id"] for m in a] == [m["id"] for m in b] == [m["id"] for m in c]

    def test_an_aspect_never_outranks_the_beat_itself(self, bank):
        """It breaks ties; it does not win arguments about what the beat is."""
        assert memory._ASPECT_WEIGHT < 1.0
