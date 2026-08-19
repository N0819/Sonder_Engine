"""Rebuilding vectors after the embedding model changes.

Bank status, the rebuild itself, the checkpoint rebuild, and the host-facing
background run with its progress state."""

import hashlib
import json
import threading
import time
from core.db import q, qi, transaction
from llm.providers import embed_texts_meta, embedding_model_key
from core.logging_utils import logger

from mind.memory_common import _blob, _blob_to_b64, _summary_retrieval_text
from mind.memory_write import (
    _json_list, _memory_cues, _memory_document, _row_memory,
)
from mind.memory_retrieval import _STRANDED_REPORTED

# ---- Rebuilding vectors after the embedding model changes ----

# Rows per embedding call. Each memory costs TWO documents (its full document
# and its cue text), so a batch of 32 is 64 texts -- comfortably inside every
# provider's per-request limit while still amortising the round trip.
_REBUILD_BATCH = 32


def embedding_bank_status(chat_id=None, char_id=None):
    """How many stored rows were embedded by a model other than the live one.

    Read-only, and cheap: it is the question `_warn_stranded_embeddings`
    answers per retrieval, asked deliberately and for the whole bank so a host
    can see the split before deciding to spend on rebuilding it.

    ASKED WITHOUT RETRIES. This runs on the chat-open path, where the host is
    watching a story fail to appear, and `is_fallback` is a REPORTED state
    rather than an error to survive -- the panel says "no embeddings provider
    is answering" and says why. Spending the write path's retry budget here
    would only make a degraded provider slow to admit to.

    A COMPARISON NEEDS BOTH SIDES. The probe answers "what does the engine
    embed with right now", and when it falls back that answer is a
    PLACEHOLDER, not the live model's identity. Read as an identity it
    strands the whole bank: measured live 2026-08-11, chat 70 held 34
    memories every one of them correctly stamped
    `openrouter:3:perplexity/pplx-embed-v1-4b`, the open-chat probe hit that
    provider's rate limit, and the host was told all 34 were written by a
    different model and should go configure the provider they already had.

    So the configured role -- read from settings, no network -- separates the
    two cases the probe cannot:

      no provider configured  the hash IS this engine's embedding. Real
                              stamps genuinely are keyword-only, and a
                              rebuild onto the hash is a downgrade. Compare.
      configured, not answering
                              the live model is known and simply silent. No
                              row is classifiable, so none is reported, and
                              `live_unknown` says why rather than inventing a
                              migration out of a 429.
    """
    live = embed_texts_meta(["status"], retry=None)
    configured = embedding_model_key()
    no_provider = configured == "cheap:crc32:256"
    live_unknown = bool(live.fallback) and not no_provider
    where, args = ["1=1"], []
    if chat_id is not None:
        where.append("chat_id=?"); args.append(chat_id)
    if char_id is not None:
        where.append("char_id=?"); args.append(char_id)
    clause = " AND ".join(where)
    stale = ("(embedding_model IS NULL OR embedding_model!=? "
             "OR embedding_dim IS NULL OR embedding_dim!=?)")
    counts = {}
    for table in ("memories", "memory_summaries"):
        total = q(f"SELECT COUNT(*) AS n FROM {table} WHERE {clause}",
                  tuple(args), one=True)["n"]
        stranded = 0 if live_unknown else q(
            f"SELECT COUNT(*) AS n FROM {table} WHERE {clause} AND {stale}",
            tuple(args) + (live.model_key, live.dimensions), one=True)["n"]
        # Of those, the ones THIS ENGINE failed to write rather than the ones
        # a model change stranded. The hash stamp separates them exactly: a
        # crc32 row under a real provider is a call that fell back, which the
        # repair queue finishes on its own, while another model's key is a
        # migration a host chooses. Only the second is worth a question.
        fallback_written = 0 if live.fallback else q(
            f"SELECT COUNT(*) AS n FROM {table} WHERE {clause} "
            "AND embedding_model='cheap:crc32:256'",
            tuple(args), one=True)["n"]
        counts[table] = {"total": total, "stranded": stranded,
                         "fallback_written": fallback_written}
    # LORE, counted with the SAME predicate that repairs it. Without this the
    # bank could not see the one table it has a repair lane for, and
    # `start_rebuild_if_needed` summed a total lore never entered -- so a
    # database whose ONLY stale vectors were lore reported "nothing to
    # rebuild" forever while the lane sat behind it, working, unreachable.
    #
    # It must be the REPAIR's predicate and not the `stale` clause above.
    # Lore rows carry a NULL stamp far more often than memories do, and the
    # repair treats a NULL stamp as stale only when the vector's WIDTH is
    # wrong. Counting every unstamped row as stranded would report rows the
    # repair will never select -- live, four entries already at the correct
    # width with no stamp -- and the count could then never reach zero, which
    # turns a reconciler into something that starts a rebuild on every call
    # forever. A wrong counter here is worse than no counter.
    book_ids = _rebuild_book_ids(chat_id)
    lore_total = lore_stranded = 0
    if book_ids:
        holes = ",".join("?" * len(book_ids))
        lore_total = q(f"SELECT COUNT(*) AS n FROM lore_entries "
                       f"WHERE lorebook_id IN ({holes})",
                       tuple(book_ids), one=True)["n"]
        # Totals are a fact about the bank; staleness is a comparison, and
        # with the live model silent there is nothing to compare against.
        lore_stranded = 0 if live_unknown else q(
            f"SELECT COUNT(*) AS n FROM lore_entries "
            f"WHERE lorebook_id IN ({holes}) AND embedding IS NOT NULL "
            "AND ((embedding_model IS NOT NULL "
            "      AND (embedding_model != ? OR embedding_dim != ?)) "
            "  OR (embedding_model IS NULL AND length(embedding) != ?))",
            tuple(book_ids) + (live.model_key, live.dimensions,
                               (live.dimensions or 0) * 4), one=True)["n"]
    counts["lore_entries"] = {"total": lore_total, "stranded": lore_stranded}
    return {
        # The model the engine embeds with. When the provider is silent that
        # is still the CONFIGURED one -- reporting the hash placeholder here
        # is what told a host their Perplexity corpus was written by a
        # different model than Perplexity.
        "model": configured if live_unknown else live.model_key,
        "dimensions": live.dimensions,
        # NO EMBEDDINGS PROVIDER IS CONFIGURED -- which is the only thing
        # every consumer of this flag uses it for: the panel offers to set
        # one, the chat-open toast says to set one, and `start_rebuild_if_-
        # needed` refuses to rebuild onto the hash. It used to be
        # `live.fallback`, i.e. "the last probe failed", so one rate-limited
        # request presented as an unconfigured engine.
        "is_fallback": no_provider,
        # A provider IS configured and did not answer this probe. Nothing is
        # comparable, so every `stranded` above is 0 by construction and a
        # caller must say "cannot tell" rather than "nothing to do".
        "live_unknown": live_unknown,
        # WHY it fell back, verbatim from the provider. Without this the
        # panel can only say "no embeddings provider", which is wrong and
        # unhelpful when one IS configured and is simply not an embeddings
        # model: `embed_texts_meta` catches every failure and degrades to the
        # hash, so choosing a chat model for this role looks like success and
        # silently changes nothing. Measured live -- `inception/mercury-2`
        # selected here returned "Model inception/mercury-2 does not exist",
        # which is exactly the sentence a host needs to see.
        "fallback_reason": str(live.error or "") if live.fallback else "",
        **counts,
    }


def _rebuild_book_ids(chat_id):
    """Which lorebooks a rebuild covers.

    Scoped to the chat when one is named, because that is how the reconciler
    is called after a restore and re-embedding an unrelated 300-entry book on
    somebody's reroll would be a surprise bill. Every book when it is not.
    """
    if chat_id is None:
        return [r["id"] for r in q("SELECT id FROM lorebooks") or []]
    ids = []
    row = q("SELECT lorebook_id FROM chats WHERE id=?", (chat_id,), one=True)
    if row and row["lorebook_id"]:
        ids.append(row["lorebook_id"])
    for r in q("SELECT lorebook_id FROM chat_lorebooks WHERE chat_id=?",
               (chat_id,)) or []:
        if r["lorebook_id"] not in ids:
            ids.append(r["lorebook_id"])
    for r in q("SELECT id FROM lorebooks WHERE chat_id=?", (chat_id,)) or []:
        if r["id"] not in ids:
            ids.append(r["id"])
    return ids


def rebuild_embeddings(chat_id=None, char_id=None, *, batch=_REBUILD_BATCH,
                       limit=None, progress=None):
    """Re-embed every row whose vectors were made by a different model.

    Configuring an `embeddings` provider on a story with history does not
    re-embed anything, and `search_memories` scores a row 0.0 on BOTH vector
    rankings when its `embedding_model`/`embedding_dim` do not match the live
    ones. Without this pass, the upgrade silently splits a memory bank into
    two eras -- everything written before it reachable only by keyword and
    exact match, forever. See docs/UNBUILT.md §1.15.

    Rebuilt with the SAME document construction `_embed_memory` uses, because
    a vector built from different text is not comparable with one built from
    the same text, and a rebuild that quietly changed the recipe would be a
    subtler version of the bug it fixes.

    **Resumable by construction**: the selection is "rows that do not match
    the live model", so a run that dies halfway simply has less to do next
    time. Each batch commits on its own for that reason.

    **Refuses to write a fallback over a real vector.** `embed_texts_meta`
    degrades to the crc32 hash on any provider error, and stamps the batch as
    `cheap:crc32:256`. Writing that would mark the rows migrated while
    downgrading them -- the one outcome worse than not running. A batch that
    comes back `fallback` when the caller is not deliberately rebuilding TO
    the fallback aborts the run and reports what it managed.

    Never call this on the turn path: it is O(bank) and it talks to a provider.
    """
    live = embed_texts_meta(["status"])
    target_key, target_dim = live.model_key, live.dimensions
    # A fallback batch may be WRITTEN only when the hash is what this run is
    # migrating onto -- the run's own target, not a fact about one request.
    # It must also be the target, not merely a failed probe: writing crc32
    # while `target_key` is a real model marks rows migrated that the `stale`
    # predicate will select again forever, which is a rebuild that never
    # terminates.
    want_fallback = target_key == "cheap:crc32:256"
    report = {"model": target_key, "dimensions": target_dim,
              "memories": 0, "summaries": 0, "lore": 0, "batches": 0,
              "stopped_early": False, "error": ""}
    if live.fallback and embedding_model_key() != "cheap:crc32:256":
        # A provider IS configured and did not answer this probe, so there is
        # nothing to rebuild ONTO: `target_key` is the hash placeholder, it
        # matches no stored row, and proceeding would either select the whole
        # bank to overwrite with hashes or stop on the first batch. Whether
        # the host has an embeddings provider is a settings fact; read as
        # `live.fallback` instead, one rate-limited request would have turned
        # the guard above off and licensed a real corpus to be overwritten.
        report["stopped_early"] = True
        report["error"] = ("embedding provider unavailable (%s); nothing "
                           "rebuilt" % (live.error or "unknown"))
        return report

    where, args = ["1=1"], []
    if chat_id is not None:
        where.append("chat_id=?"); args.append(chat_id)
    if char_id is not None:
        where.append("char_id=?"); args.append(char_id)
    clause = " AND ".join(where)
    stale = ("(embedding_model IS NULL OR embedding_model!=? "
             "OR embedding_dim IS NULL OR embedding_dim!=?)")
    stale_args = tuple(args) + (target_key, target_dim)

    def _embed(texts):
        """Embed, or raise so the run stops with the bank still coherent."""
        got = embed_texts_meta(texts)
        if got.fallback and not want_fallback:
            raise RuntimeError(
                "embedding provider unavailable (%s); refusing to write "
                "fallback vectors over real ones" % (got.error or "unknown"))
        return got

    done = 0
    try:
        while limit is None or done < limit:
            take = batch if limit is None else min(batch, limit - done)
            rows = q(f"SELECT * FROM memories WHERE {clause} AND {stale} "
                     "ORDER BY id LIMIT ?", stale_args + (take,))
            if not rows:
                break
            mems = [_row_memory(r) for r in rows]
            docs = []
            for mem in mems:
                docs.append(_memory_document(mem))
                docs.append(_memory_cues(mem) or _memory_document(mem))
            got = _embed(docs)
            with transaction():
                for index, mem in enumerate(mems):
                    qi("UPDATE memories SET embedding=?,cue_embedding=?,"
                       "embedding_model=?,embedding_dim=? WHERE id=?",
                       (_blob(got.vectors[index * 2]),
                        _blob(got.vectors[index * 2 + 1]),
                        got.model_key, got.dimensions, mem["id"]))
            done += len(rows)
            report["memories"] += len(rows)
            report["batches"] += 1
            if progress:
                progress(report["memories"], "memories")

        while True:
            rows = q(f"SELECT * FROM memory_summaries WHERE {clause} AND {stale} "
                     "ORDER BY id LIMIT ?", stale_args + (batch,))
            if not rows:
                break
            texts = [_summary_retrieval_text(
                r["summary"], _json_list(r["key_phrases"]),
                _json_list(r["unresolved_threads"])) for r in rows]
            got = _embed(texts)
            with transaction():
                for index, row in enumerate(rows):
                    qi("UPDATE memory_summaries SET embedding=?,"
                       "embedding_model=?,embedding_dim=? WHERE id=?",
                       (_blob(got.vectors[index]), got.model_key,
                        got.dimensions, row["id"]))
            report["summaries"] += len(rows)
            report["batches"] += 1
            if progress:
                progress(report["summaries"], "summaries")

        # LORE WAS LEFT OUT OF THIS, and it has the same disease with none of
        # the cure. `search_lore` scores an entry 0.0 on its 0.65 vector term
        # when the dimensions disagree, so a lorebook embedded before the
        # provider changed goes on ranking by keyword alone and simply looks
        # like a lorebook the agents ignore. Measured live: 1,061 of 1,418
        # entries stranded, one book 10 of 15, and the one room a reader kept
        # asking after was among them.
        #
        # It also has to be here rather than in a tool of its own, because
        # `checkpoints.restore_state` calls `start_rebuild_if_needed` to undo
        # exactly this damage after a restore -- a checkpoint carries lore
        # vectors verbatim, so rewinding past a migration silently reverts it.
        # A repair that lives outside this function is a repair a reroll
        # quietly discards.
        #
        # `lore_entries` has no `embedding_model`/`embedding_dim` columns, so
        # staleness is the vector's WIDTH rather than a recorded model key.
        # That is weaker -- two models sharing a width are indistinguishable --
        # and it is what the schema supports.
        # NOT WHEN THE TARGET IS THE FALLBACK. Lore staleness is measured by
        # the vector's WIDTH, so a degraded provider inverts the test: the
        # crc32 fallback is 256 wide, every real 2,560-wide entry then reads as
        # stale, and a background reconciler firing on a reroll during a
        # provider hiccup would quietly downgrade the entire corpus it was
        # called to protect. The memory pass survives this because it compares
        # model KEYS and a caller can legitimately rebuild onto the fallback;
        # lore has no key to compare, so the only safe answer is to wait.
        book_ids = _rebuild_book_ids(chat_id)
        if want_fallback and book_ids:
            # NO REPAIR IS AVAILABLE IN THIS STATE, which is a stronger reason
            # than the one this guard was first written for. Every write the
            # pass could make while the provider is degraded is a fallback
            # write -- overwriting a crc32 vector with a freshly computed
            # crc32 vector -- so "refuse to write a fallback" and "decline the
            # pass" are the same instruction. It is the decision the memories
            # path already makes; see the stopped_early test.
            logger.info("memory: skipping the lore pass, the embedding "
                        "provider is degraded -- every write it could make "
                        "would be another fallback")
            book_ids = []
        if book_ids and target_dim:
            book_ph = ",".join("?" * len(book_ids))
            while True:
                # STAMP FIRST, WIDTH ONLY WHERE THERE IS NO STAMP. A recorded
                # model key answers "is this row current" exactly; width is a
                # proxy that cannot tell two models sharing a width apart, and
                # it is only still here for rows the backfill has not reached.
                rows = q(
                    f"SELECT id, keys, content FROM lore_entries "
                    f"WHERE lorebook_id IN ({book_ph}) AND embedding IS NOT NULL "
                    f"AND ((embedding_model IS NOT NULL "
                    f"      AND (embedding_model != ? OR embedding_dim != ?)) "
                    f"  OR (embedding_model IS NULL "
                    f"      AND length(embedding) != ?)) "
                    f"ORDER BY id LIMIT ?",
                    tuple(book_ids) + (target_key, target_dim,
                                       target_dim * 4, batch))
                if not rows:
                    break
                # EXACTLY the document `update_lore` builds. A vector made from
                # different text is not comparable with one made from the same
                # text, and a rebuild that quietly changed the recipe would be a
                # subtler version of the bug it fixes.
                texts = [(r["keys"] or "") + " " + (r["content"] or "")
                         for r in rows]
                got = _embed(texts)
                with transaction():
                    for index, row in enumerate(rows):
                        qi("UPDATE lore_entries SET embedding=?,"
                           "embedding_model=?,embedding_dim=? WHERE id=?",
                           (_blob(got.vectors[index]), got.model_key,
                            got.dimensions, row["id"]))
                report["lore"] += len(rows)
                report["batches"] += 1
                if progress:
                    progress(report["lore"], "lore")
    except Exception as exc:
        # Everything committed so far stands, and re-running resumes.
        report["stopped_early"] = True
        report["error"] = str(exc)
        logger.warning("memory: embedding rebuild stopped early after "
                       "%d memories, %d summaries and %d lore entries: %s",
                       report["memories"], report["summaries"],
                       report["lore"], exc)
        return report

    # A rebuilt row is no longer stranded, so let the per-retrieval warning
    # speak again if it ever becomes true a second time.
    _STRANDED_REPORTED.clear()
    logger.info("memory: rebuilt %d memories, %d summaries and %d lore "
                "entries onto %s", report["memories"], report["summaries"],
                report["lore"], target_key)
    return report


def _vector_key(char_id, text):
    """Address a saved row by whose it is and the exact text that was embedded.

    Checkpoint dumps carry no row id, so the join has to be on content. What
    counts as "the content" is the whole point: it must be the string the
    vector was actually computed FROM, or the join can hand a row someone
    else's vector.

    The first version keyed a memory on its `content` field alone, reasoning
    that a vector is a pure function of the memory. It is -- but not of its
    content: `_memory_document` also folds in turn, location, category,
    key_phrases, entities, gist, provenance and emotional_context, and a
    summary's vector comes from `_summary_retrieval_text`, not its `summary`
    field. Two rows can therefore agree on the keyed field and hold genuinely
    different vectors. `vector_address` hit exactly this in production --
    checkpoint 855 of chat 36 held "You are in Ten Forward." at turn 42 and
    again at turn 44, same character, two different embedding payloads -- and
    was moved to byte-addressing; the note it left said this join still
    carried the old assumption. It no longer does.
    """
    body = " ".join(str(text or "").split())
    return (char_id, hashlib.sha1(body.encode("utf-8", "ignore")).hexdigest())


def _memory_vector_key(data):
    """Address a memory by the document its vector is computed from."""
    return _vector_key(data.get("char_id"), _memory_document(data))


def _summary_vector_key(data):
    """Address a summary by the retrieval text its vector is computed from."""
    return _vector_key(data.get("char_id"),
                       _summary_retrieval_text(data.get("summary"),
                                               data.get("key_phrases"),
                                               data.get("unresolved_threads")))


def rebuild_checkpoint_embeddings(chat_id=None, *, dry_run=True, progress=None):
    """Carry a completed rebuild back through a story's saved states.

    A checkpoint stores each memory's vector verbatim so that restoring one
    never re-embeds a bank (see `_blob_to_b64`). That is right, and it means a
    checkpoint written BEFORE a rebuild holds the old vectors and the old model
    key -- so rolling back to it silently undoes the rebuild. Measured live:
    one reroll put 637 of 642 rows back on the crc32 fallback.

    **This re-embeds nothing.** A vector is a pure function of the memory's
    content, and the same memory appears in dozens of checkpoints unchanged --
    chat 38 held 40,224 memory copies across its checkpoints and only 526
    distinct by content, 90.7% of which already had a rebuilt vector in the
    live table. So the fix is substitution, not computation: look each saved
    memory up by (character, content) and write in the vector already earned.

    Deliberately conservative, because this rewrites rollback history:

    * a saved row with no live match is left EXACTLY as it was, never blanked
      and never guessed at (those are memories since deleted; if one is ever
      restored, `start_rebuild_if_needed` picks it up);
    * a blob is rewritten only if something actually changed, and only after
      re-parsing to prove it is still valid JSON with the same row count;
    * `dry_run` is the default -- it reports what it would do and writes
      nothing.

    Resumable by construction: a checkpoint already carrying the live model
    key has nothing to substitute and is skipped on the next pass.
    """
    live = embed_texts_meta(["status"])
    key, dim = live.model_key, live.dimensions
    where, args = ["1=1"], []
    if chat_id is not None:
        where.append("chat_id=?"); args.append(chat_id)
    clause = " AND ".join(where)

    # Every column `_memory_document` reads, because the key is that document
    # and not the `content` slice of it.
    vectors = {}
    for row in q(f"SELECT char_id, category, turn_idx, location, entities, "
                 f"key_phrases, gist, content, provenance, emotional_context, "
                 f"embedding, cue_embedding "
                 f"FROM memories WHERE {clause} AND embedding_model=? "
                 f"AND embedding_dim=?", tuple(args) + (key, dim)):
        vectors[_memory_vector_key({
            "char_id": row["char_id"], "category": row["category"],
            "turn_idx": row["turn_idx"], "location": row["location"],
            "entities": _json_list(row["entities"]),
            "key_phrases": _json_list(row["key_phrases"]),
            "gist": row["gist"], "content": row["content"],
            "provenance": row["provenance"],
            "emotional_context": row["emotional_context"],
        })] = (_blob_to_b64(row["embedding"]),
               _blob_to_b64(row["cue_embedding"]))
    summaries = {}
    for row in q(f"SELECT char_id, summary, key_phrases, unresolved_threads, "
                 f"embedding FROM memory_summaries "
                 f"WHERE {clause} AND embedding_model=? AND embedding_dim=?",
                 tuple(args) + (key, dim)):
        summaries[_summary_vector_key({
            "char_id": row["char_id"], "summary": row["summary"],
            "key_phrases": _json_list(row["key_phrases"]),
            "unresolved_threads": _json_list(row["unresolved_threads"]),
        })] = _blob_to_b64(row["embedding"])

    report = {"model": key, "checkpoints": 0, "rewritten": 0,
              "memories_repaired": 0, "summaries_repaired": 0,
              "memories_unmatched": 0, "dry_run": bool(dry_run)}
    if not vectors and not summaries:
        return report

    rows = q(f"SELECT id, chat_id, turn_idx, blob FROM checkpoints "
             f"WHERE {clause} ORDER BY id", tuple(args))
    for row in rows:
        report["checkpoints"] += 1
        try:
            blob = json.loads(row["blob"])
        except (TypeError, ValueError):
            continue          # an unreadable checkpoint is left untouched
        changed = 0
        for mem in (blob.get("memories") or []):
            if not isinstance(mem, dict):
                continue
            if mem.get("embedding_model") == key and mem.get("embedding_dim") == dim:
                continue
            hit = vectors.get(_memory_vector_key(mem))
            if hit is None:
                report["memories_unmatched"] += 1
                continue
            mem["embedding"], mem["cue_embedding"] = hit
            mem["embedding_model"], mem["embedding_dim"] = key, dim
            changed += 1
            report["memories_repaired"] += 1
        for summ in (blob.get("memory_summaries") or []):
            if not isinstance(summ, dict):
                continue
            if summ.get("embedding_model") == key and summ.get("embedding_dim") == dim:
                continue
            hit = summaries.get(_summary_vector_key(summ))
            if hit is None:
                continue
            summ["embedding"] = hit
            summ["embedding_model"], summ["embedding_dim"] = key, dim
            changed += 1
            report["summaries_repaired"] += 1
        if not changed or dry_run:
            continue
        text = json.dumps(blob, ensure_ascii=False)
        # Prove it before it replaces rollback history: parseable, and the
        # same number of rows it went in with.
        check = json.loads(text)
        if (len(check.get("memories") or []) != len(blob.get("memories") or [])
                or sorted(check) != sorted(blob)):
            continue
        qi("UPDATE checkpoints SET blob=? WHERE id=?", (text, row["id"]))
        report["rewritten"] += 1
        if progress:
            progress(report["rewritten"], report["checkpoints"])
    if not dry_run and report["rewritten"]:
        logger.info("memory: carried the rebuild into %d checkpoint(s); "
                    "%d saved memories repaired, %d left unmatched",
                    report["rewritten"], report["memories_repaired"],
                    report["memories_unmatched"])
    return report


# ---- The rebuild, run for the host instead of by the host ----------------
#
# Nobody should have to know that changing an embeddings provider silently
# halves their retrieval, notice that it happened, find a maintenance command
# and run it. The engine knows the model it is embedding with and the model
# every stored row was embedded with; where those disagree it can simply fix
# it. This is the standing reconciler that does.
#
# NOT a one-time upgrade migration, and that distinction is the whole design:
# a mismatch appears whenever the embedding model changes -- configuring a
# provider, switching providers, a provider changing its default model or its
# dimensions, or falling back to the crc32 hash because a key expired. So this
# is a condition to be reconciled whenever it holds, checked at startup and
# again whenever provider settings are written, rather than a migration that
# runs once and is never thought about again.

_REBUILD_LOCK = threading.Lock()
_REBUILD_STATE = {
    "running": False, "done": 0, "total": 0, "model": "",
    "finished_at": 0.0, "error": "", "stopped_early": False,
}


def rebuild_progress():
    """A snapshot of the reconciler, for the status endpoint."""
    with _REBUILD_LOCK:
        return dict(_REBUILD_STATE)


def _run_rebuild(chat_id=None, char_id=None):
    status = embedding_bank_status(chat_id, char_id)
    total = (status["memories"]["stranded"]
             + status["memory_summaries"]["stranded"])
    with _REBUILD_LOCK:
        _REBUILD_STATE.update(running=True, done=0, total=total,
                              model=status["model"], error="",
                              stopped_early=False, finished_at=0.0)
    try:
        def _tick(count, _kind):
            with _REBUILD_LOCK:
                # Memories are rebuilt before summaries, so the summary pass
                # continues the same count rather than restarting it.
                _REBUILD_STATE["done"] = max(_REBUILD_STATE["done"], count)
        report = rebuild_embeddings(chat_id, char_id, progress=_tick)
        with _REBUILD_LOCK:
            _REBUILD_STATE.update(
                done=report["memories"] + report["summaries"],
                error=report["error"], stopped_early=report["stopped_early"])
    except Exception as exc:           # never take the server down for this
        logger.warning("memory: embedding rebuild failed: %s", exc)
        with _REBUILD_LOCK:
            _REBUILD_STATE.update(error=str(exc), stopped_early=True)
    finally:
        with _REBUILD_LOCK:
            _REBUILD_STATE.update(running=False, finished_at=time.time())


def start_rebuild_if_needed(chat_id=None, char_id=None, *, force=False):
    """Reconcile stored vectors with the live embedding model, in the
    background. Returns what it decided, having already started if it started.

    Safe to call on every startup and every settings write: it costs one
    COUNT per table when there is nothing to do, and it will not start a
    second run while one is going.
    """
    with _REBUILD_LOCK:
        if _REBUILD_STATE["running"]:
            return {"started": False, "reason": "already running"}
    try:
        status = embedding_bank_status(chat_id, char_id)
    except Exception as exc:
        logger.warning("memory: could not check embedding bank: %s", exc)
        return {"started": False, "reason": "status check failed: %s" % exc}
    if status.get("live_unknown"):
        # The configured provider did not answer, so every count below is 0
        # by construction and "nothing to rebuild" would be a guess wearing a
        # fact's clothes. Say what happened; the next call re-checks.
        return {"started": False,
                "reason": "embedding provider not answering", **status}
    # Lore counts. It did not, and `rebuild_embeddings` has had a working lore
    # lane behind this gate the whole time -- so a database whose only stale
    # vectors were lore was told "nothing to rebuild" on every startup and
    # every settings write, forever, while the repair sat one call away.
    # Measured live: 1,087 lore rows selected by the repair's own predicate,
    # and this function returning `nothing to rebuild`.
    stranded = (status["memories"]["stranded"]
                + status["memory_summaries"]["stranded"]
                + status.get("lore_entries", {}).get("stranded", 0))
    if not stranded:
        return {"started": False, "reason": "nothing to rebuild", **status}
    if status["is_fallback"] and not force:
        # The live "model" is the crc32 hash, which means no embeddings
        # provider is configured. Rebuilding onto it would overwrite real
        # vectors with the fallback -- a downgrade, and one the host never
        # asked for. Wait for a provider, or for an explicit force.
        logger.info("memory: %d rows do not match the live embedding model, "
                    "but no embeddings provider is configured -- not "
                    "rebuilding onto the fallback.", stranded)
        return {"started": False, "reason": "no embeddings provider", **status}
    logger.info("memory: rebuilding %d rows onto %s in the background",
                stranded, status["model"])
    thread = threading.Thread(target=_run_rebuild, args=(chat_id, char_id),
                              name="embedding-rebuild", daemon=True)
    thread.start()
    return {"started": True, "stranded": stranded, **status}


