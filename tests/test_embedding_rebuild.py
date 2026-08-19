import json, time

import numpy as np
import pytest

from mind import memory
from llm import providers
from story.character_schema import default_character_data


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


#: The columns `_memory_vector_key` joins on, which is what a checkpoint's
#: saved memory rows have to carry for the substitution to find them.
_SAVED_COLUMNS = ("char_id", "category", "turn_idx", "location", "entities",
                  "key_phrases", "gist", "content", "provenance",
                  "emotional_context")


def _saved_rows(temp_db, chat_id, model="ancient:model", dim=99):
    """Live memories rendered as a checkpoint would have saved them BEFORE a
    rebuild: the same documents, carrying the retired model's vectors."""
    out = []
    for row in temp_db.q("SELECT * FROM memories WHERE chat_id=? ORDER BY id",
                         (chat_id,)):
        saved = {c: row[c] for c in _SAVED_COLUMNS}
        for c in ("entities", "key_phrases"):
            saved[c] = json.loads(saved[c] or "[]")
        saved["embedding"] = "OLDVECTOR"
        saved["cue_embedding"] = "OLDCUEVECTOR"
        saved["embedding_model"], saved["embedding_dim"] = model, dim
        out.append(saved)
    return out


def _rebuild_one_checkpoint(temp_db, chat_id, memories, extra=None):
    """Write one checkpoint holding `memories`, rebuild, and read it back."""
    blob = dict(extra or {})
    blob["memories"] = memories
    ckpt = temp_db.qi(
        "INSERT INTO checkpoints(chat_id,turn_idx,blob,created) "
        "VALUES(?,?,?,?)",
        (chat_id, 1, json.dumps(blob, ensure_ascii=False), time.time()))
    report = memory.rebuild_checkpoint_embeddings(chat_id, dry_run=False)
    stored = json.loads(temp_db.q("SELECT blob FROM checkpoints WHERE id=?",
                                  (ckpt,), one=True)["blob"])
    return {"report": report, "blob": stored,
            "memories": stored.get("memories") or []}


def _strand(model="ancient:model", dim=99):
    from core.db import qi
    qi("UPDATE memories SET embedding_model=?, embedding_dim=?", (model, dim))


def test_status_reports_the_split(bank):
    _seed(bank, 4)
    assert memory.embedding_bank_status()["memories"]["stranded"] == 0
    _strand()
    st = memory.embedding_bank_status()
    assert st["memories"]["total"] == 4
    assert st["memories"]["stranded"] == 4
    # Stranded by a MODEL CHANGE ("ancient:model"), not by a failed write, so
    # none of it is the engine's own to finish -- see `fallback_written`.
    assert st["memories"]["fallback_written"] == 0
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
    from core.db import qi
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
    from core.db import q
    assert q("SELECT COUNT(*) AS n FROM memories WHERE embedding_model='cheap:crc32:256'",
             (), one=True)["n"] == 0


def test_summaries_are_rebuilt_too(bank):
    memory.save_memory_summary(bank["chat"], bank["chars"][0], "She has been crossing bridges for weeks.",
                               key_phrases=["bridge"], unresolved_threads=["who follows her"])
    from core.db import qi
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


class TestARestoreDoesNotUndoARebuild:
    """Checkpoint restore puts stored vectors back byte-identically —
    deliberately, so a reroll never re-embeds a bank and never risks a
    provider hiccup downgrading it to the crc32 fallback. That is correct on
    its own terms, and it has a consequence nobody chose: a checkpoint taken
    BEFORE an embedding rebuild carries the old vectors AND the old model key,
    so restoring it silently undoes the rebuild.

    Measured live: rerolling one turn of a 642-memory story put 637 rows back
    on `cheap:crc32:256` after a completed rebuild. The host saw only the
    rebuild prompt reappearing; what was actually lost was the rebuild.

    Re-embedding inline would be the wrong fix — it is what the verbatim
    restore exists to avoid, and it would put a provider call on the reroll
    path. The reconciler already does this work in the background, resumably,
    and refuses to write a fallback over real vectors.
    """

    def test_restore_hands_the_bank_back_to_the_reconciler(self):
        import inspect

        from persist import checkpoints
        # restore_checkpoint delegates to _restore_checkpoint_body,
        # which is where the work (and the reconciliation) lives.
        src = inspect.getsource(checkpoints._restore_checkpoint_body)
        assert "start_rebuild_if_needed" in src

    def test_a_failing_reconciler_never_fails_the_restore(self):
        """A maintenance task must not be able to break a reroll."""
        import inspect

        from persist import checkpoints
        src = inspect.getsource(checkpoints._restore_checkpoint_body)
        i = src.index("start_rebuild_if_needed")
        assert "try:" in src[max(0, i - 300):i]
        assert "except Exception" in src[i:i + 300]


class TestCarryingARebuildBackThroughSavedStates:
    """A checkpoint stores each memory's vector verbatim so a restore never
    re-embeds a bank. Correct — and it means a checkpoint written BEFORE a
    rebuild holds the old vectors and the old model key, so rolling back to it
    undoes the rebuild.

    The repair re-embeds NOTHING. A vector is a pure function of the memory's
    content, and the same memory recurs unchanged across every checkpoint:
    chat 38 held 40,224 memory copies across 118 checkpoints and only 526
    distinct by content. So it substitutes vectors already earned, joined on
    (character, content). Measured on that story: 36,392 saved memories
    repaired in 23.8 seconds and zero embedding calls, against 36,392 API
    calls for the brute-force alternative.
    """

    def test_the_join_key_is_the_content_and_the_character(self):
        """Two minds can hold word-identical memories that are still different
        rows, and a dump carries no row id to join on."""
        from mind import memory
        def mem(char_id, content):
            return {"char_id": char_id, "content": content}
        a = memory._memory_vector_key(mem(1, "she crossed the bridge"))
        b = memory._memory_vector_key(mem(2, "she crossed the bridge"))
        c = memory._memory_vector_key(mem(1, "she crossed the  bridge  "))
        assert a != b
        assert a == c, "whitespace must not make a memory a different memory"

    def test_two_memories_sharing_content_are_not_the_same_row(self):
        """The bug this key used to have. A vector is a pure function of the
        memory but NOT of its `content`: `_memory_document` also folds in turn,
        location, category, key_phrases, entities, gist, provenance and
        emotional_context. Keying on content alone let the substitution hand
        one memory the vector earned by another.

        Taken from the case that exposed it -- checkpoint 855 of chat 36 held
        "You are in Ten Forward." at turn 42 and again at turn 44, same
        character, two different embedding payloads.
        """
        from mind import memory
        base = {"char_id": 1, "content": "You are in Ten Forward.",
                "category": "episode", "location": "Ten Forward"}
        assert (memory._memory_vector_key({**base, "turn_idx": 42})
                != memory._memory_vector_key({**base, "turn_idx": 44}))
        assert (memory._memory_vector_key({**base, "turn_idx": 42})
                != memory._memory_vector_key({**base, "turn_idx": 42,
                                              "location": "Sickbay"}))

    def test_a_summary_is_keyed_on_what_was_actually_embedded(self):
        """`upsert_memory_summary` embeds `_summary_retrieval_text` -- the
        summary WITH its key phrases and unresolved threads -- so keying on the
        `summary` field alone had the same collision."""
        from mind import memory
        base = {"char_id": 1, "summary": "The courier never arrived."}
        assert (memory._summary_vector_key({**base, "key_phrases": ["dock"]})
                != memory._summary_vector_key({**base,
                                               "key_phrases": ["harbour"]}))
        assert (memory._summary_vector_key({**base, "unresolved_threads": []})
                != memory._summary_vector_key(
                    {**base, "unresolved_threads": ["who sent him"]}))

    def test_a_dry_run_writes_nothing(self, bank):
        from mind import memory
        r = memory.rebuild_checkpoint_embeddings(dry_run=True)
        assert r["dry_run"] is True and r["rewritten"] == 0

    def test_a_bank_with_nothing_rebuilt_is_a_noop(self, bank):
        """Nothing to substitute FROM means nothing to do — never a blanking."""
        from mind import memory
        r = memory.rebuild_checkpoint_embeddings(dry_run=False)
        assert r["rewritten"] == 0 and r["memories_repaired"] == 0

    def test_unmatched_rows_are_reported_not_blanked(self, bank, temp_db):
        """A saved memory since deleted has no live vector to inherit. It is
        left exactly as it was — the alternative is destroying rollback
        history to tidy a number.

        Written as behaviour rather than as a slice of the function's own
        source (MIND-F19): the old form asserted `continue` appeared within
        220 characters of `if hit is None:`, which any reordering breaks and
        no reordering that actually blanked a row would fail.
        """
        _seed(bank, 2)
        saved = _saved_rows(temp_db, bank["chat"])
        orphan = dict(saved[0])
        orphan["content"] = "A memory since deleted from the live bank."
        orphan["gist"] = "since deleted"
        orphan["embedding"] = "ORPHANVECTOR"
        after = _rebuild_one_checkpoint(temp_db, bank["chat"],
                                        [saved[0], orphan])

        assert after["report"]["memories_unmatched"] == 1
        assert after["report"]["memories_repaired"] == 1
        rewritten = {m["content"]: m for m in after["memories"]}
        gone = rewritten["A memory since deleted from the live bank."]
        assert gone["embedding"] == "ORPHANVECTOR"
        assert gone["embedding_model"] == "ancient:model"
        assert gone["embedding_dim"] == 99
        kept = rewritten[saved[0]["content"]]
        assert kept["embedding_model"] == after["report"]["model"]
        assert kept["embedding"] != "ORPHANVECTOR"

    def test_a_blob_is_proven_before_it_replaces_history(self, bank, temp_db):
        """Every checkpoint this rewrites comes back parseable, with the row
        count and the top-level keys it went in with — and a checkpoint whose
        blob cannot be read is left exactly as it was rather than replaced by
        something readable."""
        from core.db import q, qi

        _seed(bank, 2)
        saved = _saved_rows(temp_db, bank["chat"])
        after = _rebuild_one_checkpoint(
            temp_db, bank["chat"], saved,
            extra={"world": {"rooms": []}, "turn_idx": 4})
        assert after["report"]["rewritten"] == 1
        assert sorted(after["blob"]) == ["memories", "turn_idx", "world"]
        assert len(after["memories"]) == len(saved)

        unreadable = qi(
            "INSERT INTO checkpoints(chat_id,turn_idx,blob,created) "
            "VALUES(?,?,?,?)", (bank["chat"], 99, "{not json", time.time()))
        memory.rebuild_checkpoint_embeddings(bank["chat"], dry_run=False)
        assert q("SELECT blob FROM checkpoints WHERE id=?", (unreadable,),
                 one=True)["blob"] == "{not json"


class TestStartupHandsTheBankBackToo:
    """A degraded WRITE is permanent, so the reconciler has to run without
    being asked. Measured across the live corpus: 39 embedding fallbacks,
    every one an HTTP 429, each leaving its rows stamped `cheap:crc32:256` --
    keyword-reachable and invisible to semantic recall. `start_rebuild_if_needed`
    documents itself as "safe to call on every startup"; startup did not call
    it, so the only reconcilers were a checkpoint restore and the host clicking
    the button.
    """

    def test_startup_reconciles_the_embedding_bank(self):
        import inspect

        from web import app
        src = inspect.getsource(app._startup_engine)
        assert "_reconcile_embedding_bank" in src

    def test_it_never_waits_on_the_network_or_breaks_startup(self):
        """The decision costs a provider round trip, so it runs on its own
        thread; and a maintenance task must never break the thing it maintains
        -- the same rule the checkpoint path follows."""
        import inspect

        from web import app
        src = inspect.getsource(app._reconcile_embedding_bank)
        assert "Thread(" in src and "daemon=True" in src
        # The CALL, not the docstring's mention of it.
        i = src.index("start_rebuild_if_needed()")
        assert "try:" in src[max(0, i - 400):i]
        assert "except Exception" in src[i:i + 400]


class TestTheMaintenanceRepairsHaveAWayIn:
    """MIND-F7. `rebuild_checkpoint_embeddings` was built, documented in
    `docs/guides/MEMORY.md`, claimed as shipped in `Design.md` and tested --
    and had no caller anywhere in the tree. A repair nobody can run is a repair
    that has not happened: 1,040 checkpoints on the owner's own corpus sat
    holding a rebuild's worth of retired vectors, one restore away from putting
    them back.

    A `tools/` script rather than a route, deliberately. It rewrites rollback
    history and should not be one click away from a story in progress.
    """

    def _tool(self):
        import importlib
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
        return importlib.import_module("embedding_maintenance")

    def test_the_checkpoint_rebuild_is_reachable_from_a_command(
            self, bank, capsys):
        tool = self._tool()
        _seed(bank, 2)
        assert tool.main(["checkpoints", "--chat", str(bank["chat"])]) == 0
        out = capsys.readouterr().out
        assert "dry_run" in out and "True" in out

    def test_a_dry_run_is_the_default_of_the_command_too(self, bank,
                                                         monkeypatch):
        """The function defaults to `dry_run=True`; a command line that
        silently inverted that would be worse than no command line."""
        tool = self._tool()
        seen = {}

        def _fake(chat_id=None, *, dry_run=True, progress=None):
            seen.update(chat_id=chat_id, dry_run=dry_run)
            return {"dry_run": dry_run}

        monkeypatch.setattr(tool.memory, "rebuild_checkpoint_embeddings",
                            _fake)
        tool.main(["checkpoints"])
        assert seen == {"chat_id": None, "dry_run": True}
        tool.main(["checkpoints", "--chat", "7", "--apply"])
        assert seen == {"chat_id": 7, "dry_run": False}

    def test_status_answers_without_writing(self, bank, temp_db):
        tool = self._tool()
        _seed(bank, 2)
        before = temp_db.q("SELECT COUNT(*) n FROM checkpoints", one=True)["n"]
        assert tool.main(["status", "--json"]) == 0
        assert temp_db.q(
            "SELECT COUNT(*) n FROM checkpoints", one=True)["n"] == before
