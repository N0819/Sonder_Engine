"""Checkpoint and archive: dumping memory out and putting it back.

Vector addressing, the prepare/apply restore split, and the lorebook restore
that rebuilds a book with its entries and links."""

import hashlib
import re
import time
from core.db import q, qi, transaction
from llm.providers import embed_texts, embed_texts_meta, embedding_model_key
from dataclasses import dataclass

from mind.memory_common import (
    _b64_to_blob, _blob, _blob_to_b64, _storage_json, _summary_retrieval_text,
    _vec,
)
from mind.memory_write import (
    _delete_memory_fts, _json_list, _upsert_memory, add_memories_batch,
    prepare_memories_batch, prepare_memory,
)
from mind.memory_summaries import save_memory_summary
from mind.memory_lore_entries import add_lore, delete_lore, update_lore

# ---- Snapshot dump/restore ----

def vector_address(embedding, cue_embedding) -> str:
    """Address a vector pair by ITS OWN BYTES.

    The first version of this addressed on `(char_id, content)` -- reusing
    `_memory_vector_key` on the reasoning that a vector is a pure function of
    the memory. It is, but not of its CONTENT: `_memory_document` also folds in
    `turn`, `location`, `category`, `key_phrases`, `entities`, `gist`,
    `provenance` and `emotional_context`. Two memories can therefore share
    content and hold different vectors, and that address collapses them.

    Found in production, by the compaction verifier refusing four stories:
    checkpoint 855 of chat 36 held "You are in Ten Forward." at turn 42 and
    again at turn 44 -- same character, same content, two different embedding
    payloads. Addressing on bytes makes a collision impossible by construction
    rather than by assumption, and costs almost nothing: across chat 38's
    40,224 stored entries, content-addressing found 529 distinct and
    byte-addressing finds 583, still 69x deduplication.

    The `v1:` prefix distinguishes these from addresses written by the earlier
    scheme. Those rows stay in `memory_vectors` and keep resolving, so already
    converted checkpoints are unaffected -- and they are known-good, because a
    story whose entries collided could not have passed verification.

    `_memory_vector_key` carried the same old assumption for a while longer
    and `rebuild_checkpoint_embeddings` joined on it, which is the same bug
    one layer over: it could substitute one memory's vector onto another. That
    key now hashes the whole `_memory_document` (and a summary's whole
    `_summary_retrieval_text`), so both addresses are computed from the text
    the vector was actually built from.
    """
    digest = hashlib.sha1()
    digest.update(embedding or b"")
    digest.update(b"|")
    digest.update(cue_embedding or b"")
    return "v1:" + digest.hexdigest()


def put_memory_vector(vkey, embedding, cue_embedding, model, dim):
    """File a vector pair under its content address. Idempotent, append-only.

    `INSERT OR IGNORE`, not upsert: the address IS the content, so a second
    write for the same key is the same vector. If it somehow is not -- a model
    change without a rekey -- the FIRST one wins, because that is the one the
    existing checkpoints were written against and a rollback has to reproduce
    what it saved, not what is current.
    """
    if not vkey or embedding is None or cue_embedding is None:
        return False
    qi("INSERT OR IGNORE INTO memory_vectors"
       "(vkey,embedding,cue_embedding,embedding_model,embedding_dim,created) "
       "VALUES(?,?,?,?,?,?)",
       (vkey, embedding, cue_embedding, model or "", dim, time.time()))
    return True


def get_memory_vectors(vkeys):
    """{vkey: (embedding_blob, cue_blob, model, dim)} for the keys that exist."""
    keys = [str(k) for k in (vkeys or []) if str(k or "").strip()]
    if not keys:
        return {}
    out = {}
    # Chunked: a long story's restore can ask for hundreds of keys at once and
    # SQLite caps host parameters.
    for i in range(0, len(keys), 400):
        part = keys[i:i + 400]
        marks = ",".join("?" for _ in part)
        for r in q("SELECT * FROM memory_vectors WHERE vkey IN (%s)" % marks,
                   tuple(part)):
            out[r["vkey"]] = (r["embedding"], r["cue_embedding"],
                              r["embedding_model"], r["embedding_dim"])
    return out


def dump_memory_vectors(vkeys):
    """Content-addressed vectors, base64'd, for a portable archive."""
    out = []
    for vkey, (full, cue, model, dim) in sorted(get_memory_vectors(vkeys).items()):
        out.append({"vkey": vkey, "embedding": _blob_to_b64(full),
                    "cue_embedding": _blob_to_b64(cue),
                    "embedding_model": model, "embedding_dim": dim})
    return out


def restore_memory_vectors(entries):
    """File an archive's vectors into this database's store.

    Additive and idempotent -- the address is the content, so an entry that is
    already here is the same vector. Never deletes: another chat's checkpoints
    may reference the same address.

    VERIFIED, not trusted: this used to file the archive's `vkey` straight
    through with no recomputation and no length check, while
    `persist/checkpoints.py`'s restore recomputed. That broke the store's
    premise -- `put_memory_vector` is INSERT OR IGNORE with first-writer-wins
    because the address IS the content, so one mislabeled archive entry could
    park wrong bytes under a true address and shadow the real vector for
    every checkpoint that later referenced it. A violation RAISES rather than
    skipping, so the enclosing import transaction rolls the whole restore
    back: a partially-restored vector bank is a silent retrieval downgrade,
    which is the failure mode the model stamps were added to end. Pre-`v1:`
    keys were addressed on the memory document, not the bytes, so they cannot
    be recomputed here and restore on the well-formedness checks alone.
    """
    n = 0
    with transaction():
        for e in entries or []:
            if not isinstance(e, dict):
                continue
            vkey = str(e.get("vkey") or "").strip()
            if not vkey:
                continue
            full = _b64_to_blob(e.get("embedding"))
            cue = _b64_to_blob(e.get("cue_embedding"))
            if full is None or cue is None:
                raise ValueError(
                    f"memory vector {vkey!r}: payload is not a well-formed "
                    "float32 blob"
                )
            try:
                dim = int(e.get("embedding_dim"))
            except (TypeError, ValueError):
                dim = None
            if dim and len(full) != dim * 4:
                raise ValueError(
                    f"memory vector {vkey!r}: blob holds {len(full) // 4} "
                    f"floats but claims dimension {dim}"
                )
            if vkey.startswith("v1:") and vector_address(full, cue) != vkey:
                raise ValueError(
                    f"memory vector {vkey!r}: bytes do not hash to their own "
                    "address"
                )
            if put_memory_vector(vkey, full, cue,
                                 e.get("embedding_model"),
                                 dim if dim else e.get("embedding_dim")):
                n += 1
    return n


def dump_chat_memories(chat_id, *, inline_vectors=True):
    """The chat's memory bank, for a checkpoint or a portable archive.

    `inline_vectors` is the difference between the two callers, and it matters:

    * a CHECKPOINT lives in the same database as the vector store, so it can
      reference vectors by content address and carry none of the payload.
      That is the whole compaction -- the two vector fields are 96.9% of a
      checkpoint, re-stored on every turn for the life of the story.
    * a portable ARCHIVE is imported into a DIFFERENT database, where no such
      store exists, so it must carry the vectors with it or the import
      re-embeds the whole bank (expensive, and a provider hiccup during it
      silently downgrades every vector to the crc32 fallback).

    The restore path accepts either shape, so an old checkpoint written before
    this existed still restores from its inline vectors unchanged.
    """
    rows = q("SELECT * FROM memories WHERE chat_id=? ORDER BY CASE WHEN turn_idx IS NULL THEN 1 ELSE 0 END, turn_idx, id", (chat_id,))
    if not inline_vectors:
        with transaction():
            for r in rows:
                if r["embedding"] is None or r["cue_embedding"] is None:
                    continue
                put_memory_vector(
                    vector_address(r["embedding"], r["cue_embedding"]),
                    r["embedding"], r["cue_embedding"],
                    r["embedding_model"], r["embedding_dim"])
    return [
        {"char_id": r["char_id"], "turn_id": r["turn_id"], "turn_idx": r["turn_idx"],
         "frame_id": r["frame_id"],
         "kind": r["kind"], "category": r["category"], "provenance": r["provenance"],
         "salience": r["salience"], "content": r["content"], "gist": r["gist"],
         "key_phrases": _json_list(r["key_phrases"]), "entities": _json_list(r["entities"]),
         "location": r["location"], "emotional_context": r["emotional_context"],
         "valence": r["valence"], "arousal": r["arousal"], "confidence": r["confidence"],
         "encoding_valence": r["encoding_valence"],
         "encoding_arousal": r["encoding_arousal"],
         "archived": bool(r["archived"]), "event_key": r["event_key"],
         "importance": r["importance"], "disputed": r["disputed"] or "",
         # How often this memory came back to the character, and when it last
         # did. The engine never reads either column; `tools/remember_lines.py`
         # and `tools/salience_replay.py` read them as their whole answer, so a
         # bank that forgets them on every reroll, branch or import has a
         # denominator that silently resets to zero. Neither is re-derivable
         # from anything -- the same argument `importance` and `disputed` are
         # carried on, one line up.
         "access_count": r["access_count"] or 0,
         "last_accessed": r["last_accessed"],
         # The TURN a recall reached this row on. Travels for the same reason
         # the two above do: it is the record of the memory being read, not of
         # it being formed, and it is re-derivable from nothing. Losing it on a
         # checkpoint rollback would silently reset the one measurement that
         # says how far back this mind actually reaches.
         "last_accessed_turn": r["last_accessed_turn"],
         # Stored vectors travel with the dump so restore can put them
         # back byte-identically instead of re-embedding the entire
         # memory bank on every checkpoint restore (expensive, and a
         # provider hiccup during it silently downgrades every vector
         # to the crc32 fallback, which then scores 0.0 forever).
         **({"embedding": _blob_to_b64(r["embedding"]),
             "cue_embedding": _blob_to_b64(r["cue_embedding"])}
            if inline_vectors else
            {"vkey": vector_address(r["embedding"], r["cue_embedding"])}),
         "embedding_model": r["embedding_model"],
         "embedding_dim": r["embedding_dim"]}
        for r in rows
    ]

@dataclass
class _StoredEmbeddingMeta:
    """Stands in for providers.EmbeddingBatch when the vectors came out
    of a dump instead of a live embedding call -- _upsert_memory only
    reads model_key/dimensions off it."""
    model_key: str
    dimensions: int

def prepare_chat_memory_restore(chat_id, mems):
    """Build a write-free restore plan for restore_chat_memories.

    All normalization and any embedding calls happen here, BEFORE any
    row is touched, so apply_chat_memory_restore is pure writes and can
    run inside an outer transaction (checkpoint restore) without a
    remote provider call ever holding SQLite's write lock. Dumps that
    carry their stored vectors (see dump_chat_memories) are restored
    verbatim; only legacy dumps without them are re-embedded."""
    entries = []
    legacy_items = []
    # One lookup for every address in the dump, before the loop: a restore
    # should not issue a query per memory.
    vector_store = get_memory_vectors(
        [m.get("vkey") for m in (mems or []) if isinstance(m, dict) and m.get("vkey")])
    for m in mems or []:
        if not m.get("content"):
            continue
        item = {
            "chat_id": chat_id, "char_id": m.get("char_id"), "turn_id": m.get("turn_id"),
            "turn_idx": m.get("turn_idx"), "kind": m.get("kind", "episodic"),
            # Preserved verbatim, never re-stamped with whatever frame
            # happens to be active during the restore -- a checkpoint
            # restore means "put it back exactly as it was," and a
            # branch clone is expected to have already remapped this to
            # the new chat's own frame ids before calling this function.
            "frame_id": m.get("frame_id"),
            "category": m.get("category"), "provenance": m.get("provenance", "witnessed"),
            "salience": m.get("salience", 0.5), "content": m["content"],
            "gist": m.get("gist"), "key_phrases": m.get("key_phrases"),
            "entities": m.get("entities"), "location": m.get("location", ""),
            "emotional_context": m.get("emotional_context", ""),
            "valence": m.get("valence", 0.0), "arousal": m.get("arousal", 0.0),
            "encoding_valence": m.get("encoding_valence", 0.0),
            "encoding_arousal": m.get("encoding_arousal", 0.0),
            "confidence": m.get("confidence", 1.0), "event_key": m.get("event_key", ""),
            # Carried verbatim. A revised importance and a recorded re-reading
            # are things the character earned; a rollback restores the bank as
            # it was, and neither is re-derivable from the row's own text.
            "importance": m.get("importance"),
            "disputed": m.get("disputed") or "",
        }
        # Restored after the insert, beside `archived`: `prepare_memory`
        # describes a memory as it was FORMED, and neither of these is part of
        # that -- they are the record of it being read since.
        history = (int(m.get("access_count") or 0), m.get("last_accessed"),
                   m.get("last_accessed_turn"))
        full_blob = _b64_to_blob(m.get("embedding"))
        cue_blob = _b64_to_blob(m.get("cue_embedding"))
        model = m.get("embedding_model") or ""
        # A compacted checkpoint carries a content address instead of the
        # payload. Resolve it here, in the same read-only phase the inline
        # shape is handled in, so the write phase stays identical for both.
        if (full_blob is None or cue_blob is None) and m.get("vkey"):
            hit = vector_store.get(m["vkey"])
            if hit:
                full_blob, cue_blob = hit[0], hit[1]
                model = model or hit[2]
                if not m.get("embedding_dim"):
                    m = {**m, "embedding_dim": hit[3]}
        if full_blob is not None and cue_blob is not None and model:
            full_vec = _vec(full_blob)
            cue_vec = _vec(cue_blob)
            dim = m.get("embedding_dim") or len(full_vec)
            entries.append({
                "mode": "direct", "source": m, "data": prepare_memory(**item),
                "full_vec": full_vec, "cue_vec": cue_vec,
                "meta": _StoredEmbeddingMeta(model, int(dim)),
                "retrieval_history": history,
            })
        else:
            entries.append({"mode": "legacy", "source": m,
                            "retrieval_history": history})
            legacy_items.append(item)
    legacy_batch = prepare_memories_batch(legacy_items) if legacy_items else None
    return {"entries": entries, "legacy_batch": legacy_batch}

def apply_chat_memory_restore(chat_id, plan):
    """Write phase of restore_chat_memories: delete-and-reinsert the
    chat's memory bank from a plan built by prepare_chat_memory_restore.
    One transaction, no provider calls; FTS rows are maintained through
    the exact same _upsert_memory path the normal add path uses."""
    entries = plan.get("entries") or []
    legacy_batch = plan.get("legacy_batch")
    legacy_prepared = (legacy_batch or {}).get("prepared") or []
    legacy_embedded = (legacy_batch or {}).get("embedded")
    legacy_count = sum(1 for e in entries if e["mode"] == "legacy")
    if legacy_count and (legacy_embedded is None
                         or len(legacy_embedded.vectors) != legacy_count * 2
                         or len(legacy_prepared) != legacy_count):
        raise ValueError("Invalid prepared memory embedding batch")
    with transaction():
        for r in q("SELECT id FROM memories WHERE chat_id=?", (chat_id,)):
            _delete_memory_fts(r["id"])
        qi("DELETE FROM memories WHERE chat_id=?", (chat_id,))
        li = 0
        for entry in entries:
            if entry["mode"] == "direct":
                mid = _upsert_memory(entry["data"], entry["full_vec"],
                                     entry["cue_vec"], entry["meta"])
            else:
                mid = _upsert_memory(legacy_prepared[li],
                                     legacy_embedded.vectors[li * 2],
                                     legacy_embedded.vectors[li * 2 + 1],
                                     legacy_embedded)
                li += 1
            if entry["source"].get("archived"):
                qi("UPDATE memories SET archived=1 WHERE id=?", (mid,))
            # Three-tuple since v32; an older checkpoint carries two and its
            # rows simply have no recorded turn, which is the truthful state
            # rather than a zero.
            hist = entry.get("retrieval_history") or (0, None, None)
            count, last, last_turn = (tuple(hist) + (None, None))[:3]
            if count or last is not None or last_turn is not None:
                qi("UPDATE memories SET access_count=?, last_accessed=?, "
                   "last_accessed_turn=? WHERE id=?",
                   (int(count or 0), last, last_turn, mid))

def restore_chat_memories(chat_id, mems):
    apply_chat_memory_restore(chat_id, prepare_chat_memory_restore(chat_id, mems))

def dump_character_memories(chat_id, char_id):
    """Same shape as dump_chat_memories, but scoped to one character --
    the unit a user actually wants to carry around (export a character's
    accumulated memory bank, import it into a different story with the
    same character, or back it up separately from the whole chat)."""
    rows = q(
        "SELECT * FROM memories WHERE chat_id=? AND char_id=? "
        "ORDER BY CASE WHEN turn_idx IS NULL THEN 1 ELSE 0 END, turn_idx, id",
        (chat_id, char_id),
    )
    return [
        {"turn_idx": r["turn_idx"],
         "kind": r["kind"], "category": r["category"], "provenance": r["provenance"],
         "salience": r["salience"], "content": r["content"], "gist": r["gist"],
         "key_phrases": _json_list(r["key_phrases"]), "entities": _json_list(r["entities"]),
         "location": r["location"], "emotional_context": r["emotional_context"],
         "valence": r["valence"], "arousal": r["arousal"], "confidence": r["confidence"],
         "encoding_valence": r["encoding_valence"],
         "encoding_arousal": r["encoding_arousal"],
         "archived": bool(r["archived"]), "event_key": r["event_key"],
         "importance": r["importance"], "disputed": r["disputed"] or ""}
        for r in rows
    ]

def import_character_memories(chat_id, char_id, memories):
    """Additive import for one character's memories -- unlike
    restore_chat_memories (which wipes and replaces, only ever used for
    checkpoint restore), this never deletes anything: it's for a user
    bringing a character's memory bank INTO a chat, possibly a different
    one than it was exported from. turn_id/turn_idx are always dropped
    even on a same-chat re-import, since an old export's turn numbering
    can't be trusted to still line up with this chat's actual turns --
    the same treatment already used for background-promotion memory
    seeds, which also arrive with no real turn to anchor to."""
    prepared = []
    for m in memories or []:
        content = str(m.get("content") or "").strip()
        if not content:
            continue
        prepared.append({
            "chat_id": chat_id, "char_id": char_id, "turn_id": None, "turn_idx": None,
            "kind": m.get("kind", "episodic"), "category": m.get("category"),
            "provenance": m.get("provenance", "told"),
            "salience": m.get("salience", 0.5), "content": content,
            "gist": m.get("gist"), "key_phrases": m.get("key_phrases"),
            "entities": m.get("entities"), "location": m.get("location", ""),
            "emotional_context": m.get("emotional_context", ""),
            "valence": m.get("valence", 0.0), "arousal": m.get("arousal", 0.0),
            "encoding_valence": m.get("encoding_valence", 0.0),
            "encoding_arousal": m.get("encoding_arousal", 0.0),
            "confidence": m.get("confidence", 1.0), "event_key": "",
            # Both travel with a portable character bank: they are the
            # character's own history with these memories, not facts about the
            # chat they were formed in.
            "importance": m.get("importance"),
            "disputed": m.get("disputed") or "",
        })
    if not prepared:
        return 0
    # Refuse a hashed bank rather than storing one (UNBUILT 1.75). The shared
    # writer deliberately does NOT do this: a turn whose provider is briefly
    # down should keep its memory and have it rebuilt later, because losing
    # the beat is worse. An import is the opposite case -- it is one host
    # action, retryable in full, and a whole bank stamped `cheap:crc32:256`
    # measures 0% paraphrase recall while reporting success. Measured: the
    # three largest banks in the live corpus each exceed the provider's
    # request ceiling on their own.
    #
    # The discriminator is `rebuild_embeddings`', restated: a fallback batch is
    # only a FAILURE when the hash is not what this install is embedding onto.
    # Running with no embeddings provider is a supported configuration, and
    # there crc32 is the target rather than a degradation -- refusing it would
    # break import for everyone who has not configured one.
    batch = prepare_memories_batch(prepared)
    embedded = batch.get("embedded")
    if (embedded is not None and embedded.fallback
            and embedding_model_key() != "cheap:crc32:256"):
        # %-formatted, like the sibling refusal in `rebuild_embeddings`: an
        # f-string here is collected by `tools/extract_ui_catalog.py` as a
        # translatable UI string, and this is an engine diagnostic for a host
        # reading an API error, not screen copy for a player.
        raise ValueError(
            "refusing to import: embeddings fell back to the crc32 hash, so "
            "every imported memory would be reachable by keyword only while "
            "%s is configured. Provider error: %s"
            % (embedding_model_key(), embedded.error or "unknown"))
    return len(add_memories_batch(prepared_batch=batch))

def dump_memory_summaries(chat_id):
    return [
        {"char_id": r["char_id"], "scope": r["scope"], "start_turn_idx": r["start_turn_idx"],
         "end_turn_idx": r["end_turn_idx"], "summary": r["summary"],
         "key_phrases": _json_list(r["key_phrases"]), "unresolved_threads": _json_list(r["unresolved_threads"]),
         # Per-clause support travels with the summary. Refs are event_keys,
         # which restore preserves verbatim, so this needs no id remapping on
         # branch, clone or checkpoint rollback -- the reason it was built out
         # of event_keys rather than row ids.
         "support": _json_list(r["support"]),
         "updated": r["updated"],
         # Same rationale as dump_chat_memories: carry the stored vector
         # so restore is verbatim instead of a provider round trip.
         "embedding": _blob_to_b64(r["embedding"]),
         "embedding_model": r["embedding_model"],
         "embedding_dim": r["embedding_dim"]}
        # end_turn_idx joins the ordering since v23: a scope holds one row per
        # WINDOW, so (char_id, scope) alone no longer identifies a row and an
        # export's order would depend on rowid.
        for r in q("SELECT * FROM memory_summaries WHERE chat_id=? "
                   "ORDER BY char_id, scope, end_turn_idx, id", (chat_id,))
    ]

def prepare_memory_summary_restore(summaries):
    """Embedding phase of restore_memory_summaries: resolves each
    summary's vector (verbatim from the dump when present, one embed
    call per legacy item otherwise) with zero writes, so the apply
    phase never makes a provider call while holding the write lock."""
    prepared = []
    for item in summaries or []:
        emb = _b64_to_blob(item.get("embedding"))
        model = item.get("embedding_model") or ""
        dim = item.get("embedding_dim")
        if emb is None or not model:
            embedded = embed_texts_meta([_summary_retrieval_text(
                item.get("summary"), item.get("key_phrases") or [],
                item.get("unresolved_threads") or [])])
            emb = _blob(embedded.vectors[0])
            model = embedded.model_key
            dim = embedded.dimensions
        prepared.append((item, emb, model, dim))
    return prepared

def apply_memory_summary_restore(chat_id, prepared):
    with transaction():
        qi("DELETE FROM memory_summaries WHERE chat_id=?", (chat_id,))
        for item, emb, model, dim in prepared:
            save_memory_summary(chat_id, item["char_id"], item.get("summary", ""),
                                scope=item.get("scope", "autobiographical"),
                                start_turn_idx=item.get("start_turn_idx", 0),
                                end_turn_idx=item.get("end_turn_idx", 0),
                                key_phrases=item.get("key_phrases") or [],
                                unresolved_threads=item.get("unresolved_threads") or [],
                                support=item.get("support") or [],
                                embedding=emb, embedding_model=model, embedding_dim=dim)

def restore_memory_summaries(chat_id, summaries):
    apply_memory_summary_restore(chat_id, prepare_memory_summary_restore(summaries))

def dump_lorebook(lb_id):
    return [
        {
            "entry_uid": r["entry_uid"], "keys": r["keys"], "content": r["content"],
            "category": r["category"] or "other", "locked": r["canon_locked"],
            "turn_added": r["turn_added"], "title": r["title"],
            "knowledge_tag": r["knowledge_tag"], "knowledge_range": r["knowledge_range"],
            "knowledge_locations": r["knowledge_locations"],
            "importance": r["importance"], "aliases": r["aliases"],
            "scope": r["scope"], "relations": r["relations"],
            "source_notes": r["source_notes"],
            # Stored vector travels with the dump so restore/import can
            # reuse it verbatim instead of re-embedding every entry -- and
            # with the stamp that says what produced it, because a vector
            # whose provenance was dropped in transit is one every later
            # reader has to judge on width alone.
            "embedding": _blob_to_b64(r["embedding"]),
            "embedding_model": r["embedding_model"],
            "embedding_dim": r["embedding_dim"],
        }
        for r in q("SELECT * FROM lore_entries WHERE lorebook_id=? ORDER BY id", (lb_id,))
    ]

def restore_lorebook(lb_id, entries):
    import hashlib, uuid

    def legacy_entry_uid(entry):
        raw = "\x1f".join([
            str(entry.get("keys") or "").strip().casefold(),
            re.sub(r"\s+", " ", str(entry.get("content") or "").strip().casefold()),
            str(entry.get("category") or "other"),
        ])
        return f"legacy_entry_{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"

    incoming = [entry for entry in (entries or []) if isinstance(entry, dict) and entry.get("content")]
    incoming_uids = set()

    # Resolve every entry's embedding up front, before any row is
    # touched: entries dumped by dump_lorebook carry their stored vector
    # (reused verbatim -- the snapshot's vector matches the snapshot's
    # keys/content by construction), and only legacy dumps without one
    # are re-embedded, in a single batch so no per-entry provider call
    # ever runs between writes.
    entry_vecs = {}
    entry_stamps = {}
    legacy_entries = []
    for entry in incoming:
        raw = entry.get("embedding")
        if isinstance(raw, str):
            raw = _b64_to_blob(raw)
        elif not isinstance(raw, (bytes, bytearray, memoryview)):
            raw = None
        vec = _vec(bytes(raw)) if raw and len(raw) % 4 == 0 else None
        if vec is None:
            legacy_entries.append(entry)
        entry_vecs[id(entry)] = vec
        # The stamp belongs to the vector that arrived, so a snapshot old
        # enough to carry bytes without one stays unstamped, and an entry
        # re-embedded below is stamped by the embedder rather than by the
        # snapshot it came from.
        entry_stamps[id(entry)] = (
            entry.get("embedding_model") if vec is not None else None)
    if legacy_entries:
        texts = [(e.get("keys") or "") + " " + (e.get("content") or "") for e in legacy_entries]
        for e, vec in zip(legacy_entries, embed_texts(texts)):
            entry_vecs[id(e)] = vec
            # NOT stamped with the live model key: `embed_texts` returns bare
            # vectors and degrades to the crc32 fallback on any provider
            # error, so the name would be a guess. Unstamped is the true
            # answer, and what the backfill exists to settle.
            entry_stamps[id(e)] = None

    for entry in incoming:
        uid = entry.get("entry_uid") or legacy_entry_uid(entry)
        existing = q("SELECT id FROM lore_entries WHERE lorebook_id=? AND entry_uid=?", (lb_id, uid), one=True)
        if existing:
            incoming_uids.add(uid)
            update_lore(existing["id"], entry.get("keys", ""), entry["content"],
                        entry.get("category", "other"), title=entry.get("title"),
                        knowledge_tag=entry.get("knowledge_tag"),
                        knowledge_range=entry.get("knowledge_range"),
                        knowledge_locations=_storage_json(entry.get("knowledge_locations")),
                        importance=entry.get("importance", 0.5),
                        aliases=entry.get("aliases", []),
                        scope=entry.get("scope", {}),
                        relations=entry.get("relations", {}),
                        source_notes=entry.get("source_notes", ""),
                        embedding=entry_vecs.get(id(entry)),
                        embedding_model=entry_stamps.get(id(entry)),
                        embedding_dim=entry.get("embedding_dim"))
            qi("UPDATE lore_entries SET canon_locked=?, turn_added=? WHERE id=?",
               (int(bool(entry.get("locked", 0))), entry.get("turn_added"), existing["id"]))
            continue

        # UID might exist in a different lorebook (global UNIQUE constraint)
        global_existing = q("SELECT id FROM lore_entries WHERE entry_uid=?", (uid,), one=True)
        if global_existing:
            uid = f"entry_{uuid.uuid4().hex}"

        incoming_uids.add(uid)
        add_lore(lb_id, entry.get("keys", ""), entry["content"],
                 turn_added=entry.get("turn_added"), locked=int(bool(entry.get("locked", 0))),
                 category=entry.get("category", "other"), title=entry.get("title"),
                 knowledge_tag=entry.get("knowledge_tag"), knowledge_range=entry.get("knowledge_range"),
                 knowledge_locations=_storage_json(entry.get("knowledge_locations")),
                 entry_uid=uid,
                 importance=entry.get("importance", 0.5),
                 aliases=entry.get("aliases", []),
                 scope=entry.get("scope", {}),
                 relations=entry.get("relations", {}),
                 source_notes=entry.get("source_notes", ""),
                 embedding=entry_vecs.get(id(entry)),
                 embedding_model=entry_stamps.get(id(entry)),
                 embedding_dim=entry.get("embedding_dim"))

    for row in q("SELECT id,entry_uid FROM lore_entries WHERE lorebook_id=?", (lb_id,)):
        if row["entry_uid"] not in incoming_uids:
            delete_lore(row["id"])

