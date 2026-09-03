"""Lore ENTRIES: the text inside a book, and how a mind finds it.

Add/update/delete, embedding stamps and their health, `search_lore`, and the
knowledge scoping that decides which entries a character may draw on."""

import json
import time
import numpy as np
from core.db import q, qi, transaction
from llm.providers import embed_texts, embed_texts_meta
from core.logging_utils import logger

from mind.memory_common import (
    LORE_CATEGORIES, _blob, _cos, _ids, _kw_scores, _storage_json, _vec,
)
from mind.memory_lorebooks import (
    dump_lorebook_links, lorebook_descendants, restore_lorebook_links,
)
from mind.memory_write import _json_list

# ---- Lorebook Entries ----

def ensure_chat_canon_book(chat_id):
    """The chat's own canon lorebook, minted on demand.

    Canon written DURING play -- facts the Director established this run --
    lives in one book per chat, hung off `chats.lorebook_id`. It used to be
    minted inline by `commit.commit_mapping` and nowhere else, so a second
    writer could only spell the same book into existence again; a ratified
    background claim (`background_claims.settle_claims`) is exactly that second
    writer, and it lands on beats where mapping is skipped entirely. One
    spelling, folded here, rather than a rule each new writer must remember.

    Returns the lorebook id, or None if the chat does not exist.
    """
    row = q("SELECT name, lorebook_id FROM chats WHERE id=?", (chat_id,), one=True)
    if not row:
        return None
    if row["lorebook_id"]:
        return row["lorebook_id"]
    lb = qi(
        "INSERT INTO lorebooks(name,chat_id,book_type,summary) VALUES(?,?,?,?)",
        (
            f"{row['name']} — canon", chat_id, "general",
            "Chat canon: facts, events and specifics established during this chat.",
        ),
    )
    qi("UPDATE chats SET lorebook_id=? WHERE id=?", (lb, chat_id))
    return lb


def _embed_lore_document(keys, content):
    """The vector for one lore entry, WITH the model that made it.

    THE WRITE PATH USED TO THROW THAT AWAY. `add_lore` and `update_lore` both
    called `embed_texts`, which returns bare vectors, so neither could tell a
    real embedding from `cheap_embed`'s crc32 hash -- and `embed_texts_meta`
    degrades to that hash on ANY provider error. 1,061 of 1,418 entries on a
    live corpus were written that way, byte-identical to the fallback,
    semantically meaningless, and nothing recorded it because there was
    nowhere to record it and nothing asking.

    Returns `(vector, model_key, dimensions)`. The caller stores all three, so
    the question "what embedded this row" is answered at the moment of writing
    rather than reconstructed by hashing every entry in the table afterwards.
    """
    got = embed_texts_meta([(keys or "") + " " + (content or "")])
    return got.vectors[0], got.model_key, got.dimensions


def _carried_stamp(vec, embedding_model, embedding_dim):
    """What a caller-supplied lore vector may claim about its own provenance.

    A vector arriving from a restore, an import or a branch is reused verbatim
    rather than recomputed, so the stamp has to travel with it or be lost. It
    used to be lost: the dump carried only the bytes, and this returned a NULL
    model for every restored entry -- which was the RIGHT answer to the
    question it was being asked, since inventing a model name from bytes would
    be a guess written down as a measurement. The fix is upstream, in what the
    dump carries; here the rule is only that a claim is honoured when one was
    made and never manufactured when it was not.

    The WIDTH still comes from the bytes when they disagree with a claimed
    dimension: the vector is the artefact, the number is a description of it.
    """
    try:
        dims = len(vec)
    except TypeError:
        dims = None
    if dims is None:
        try:
            dims = int(embedding_dim)
        except (TypeError, ValueError):
            dims = None
    model_key = str(embedding_model).strip() if embedding_model else None
    return (model_key or None), dims


def add_lore(lorebook_id, keys, content, turn_added=None, locked=0, category="other",
             title=None, knowledge_tag=None, knowledge_range=None,
             knowledge_locations=None, entry_uid=None,
             importance=0.5, aliases=None, scope=None, relations=None,
             source_notes="", embedding=None, embedding_model=None,
             embedding_dim=None, circles=None):
    """One lore entry, written with its GATE FIELDS stated.

    Lore is an author's reference and the Director's setting rulebook, and
    it is the ONE channel by which a mind knows something by standing rather
    than by living (`knowledge_for_character`). The three gate fields decide
    who that is: `knowledge_tag` (depth -- common, scholarly, esoteric),
    `circles` (compartment; NULL inherits the book, `[]` is public) and
    `knowledge_range` + `knowledge_locations` (where it applies). An entry
    with NO depth tag reaches no mind: it is Director-only, by design, and
    every writer that leaves the tag empty is choosing that. Say so where
    you call this.
    """
    import uuid
    entry_uid = entry_uid or f"entry_{uuid.uuid4().hex}"
    vec = embedding
    model_key, dims = None, None
    if vec is None:
        vec, model_key, dims = _embed_lore_document(keys, content)
    else:
        model_key, dims = _carried_stamp(vec, embedding_model, embedding_dim)
    return qi("""INSERT INTO lore_entries(
            lorebook_id, keys, content, category, canon_locked, turn_added,
            embedding, title, knowledge_tag, knowledge_range,
            knowledge_locations, entry_uid, importance, aliases, scope,
            relations, source_notes, embedding_model, embedding_dim, circles
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (lorebook_id, keys or "", content or "",
         category if category in LORE_CATEGORIES else "other",
         locked, turn_added, _blob(vec), title, knowledge_tag,
         knowledge_range, _storage_json(knowledge_locations), entry_uid,
         float(importance),
         _storage_json(aliases or []),
         _storage_json(scope or {}),
         _storage_json(relations or {}),
         source_notes, model_key, dims,
         # NULL, not '[]': an entry that never answered the compartment
         # question INHERITS its book, and only an explicit empty list means
         # "public". Passing a default here would silently make every new
         # entry a deliberate exception to its own book.
         None if circles is None else _storage_json(circles)))

def update_lore(entry_id, keys, content, category=None, title=None,
                knowledge_tag=None, knowledge_range=None, knowledge_locations=None,
                importance=None, aliases=None, scope=None, relations=None,
                source_notes=None, embedding=None, embedding_model=None,
                embedding_dim=None, circles=None):
    vec = embedding
    model_key, dims = None, None
    if vec is None:
        vec, model_key, dims = _embed_lore_document(keys, content)
    else:
        model_key, dims = _carried_stamp(vec, embedding_model, embedding_dim)
    fields = ["keys=?", "content=?", "embedding=?", "title=?",
              "knowledge_tag=?", "knowledge_range=?", "knowledge_locations=?",
              "embedding_model=?", "embedding_dim=?"]
    values = [keys or "", content or "", _blob(vec), title,
              knowledge_tag, knowledge_range, knowledge_locations,
              model_key, dims]
    
    if category and category in LORE_CATEGORIES:
        fields.append("category=?")
        values.append(category)
    if importance is not None:
        fields.append("importance=?")
        values.append(float(importance))
    if aliases is not None:
        fields.append("aliases=?")
        values.append(_storage_json(aliases))
    if scope is not None:
        fields.append("scope=?")
        values.append(_storage_json(scope))
    if relations is not None:
        fields.append("relations=?")
        values.append(_storage_json(relations))
    # Only when the caller actually supplied one -- see add_lore: leaving it
    # alone preserves "inherit the book", which is what NULL means.
    if circles is not None:
        fields.append("circles=?")
        values.append(_storage_json(circles))
    if source_notes is not None:
        fields.append("source_notes=?")
        values.append(source_notes)
    
    values.append(entry_id)
    qi(f"UPDATE lore_entries SET {','.join(fields)} WHERE id=?", tuple(values))

def duplicate_lorebook_tree_for_chat(root_id, chat_id, include_links=True):
    """Duplicate a lorebook subtree for a chat, preserving hierarchy and links.

    NOT the attach path for a library book any more (2026-09-03): a library
    book is attached by reference and a story's deviations are overlays
    (`set_lore_overlay`). This survives for the one case that is a genuine
    fork -- taking another STORY's book into this one, which has no shared
    origin to overlay -- and for the tests that pin its embedding stamps.
    """
    book_ids = lorebook_descendants(root_id)
    if not book_ids:
        return {}
    
    old_to_new = {}
    
    # Pass 1: Create all books
    for old_id in book_ids:
        src = q("SELECT * FROM lorebooks WHERE id=?", (old_id,), one=True)
        if not src:
            continue
        new_id = qi("""INSERT INTO lorebooks(name,chat_id,origin_id,book_type,summary,
                      parent_id,scope_world_id,scope_location_id,inheritance_mode,sort_order,
                      resource_uid)
                      VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                    ((src["name"] or "book") + " (chat copy)", chat_id, old_id,
                     src["book_type"] or "general", src["summary"] or "",
                     src["parent_id"], src["scope_world_id"],
                     src["scope_location_id"], src["inheritance_mode"] or "inherit",
                     src["sort_order"] or 0,
                     None))
        old_to_new[old_id] = new_id
        for e in q("SELECT * FROM lore_entries WHERE lorebook_id=?", (old_id,)):
            add_lore(new_id, e["keys"], e["content"], e["turn_added"], e["canon_locked"],
                     e["category"] or "other", title=e["title"],
                     knowledge_tag=e["knowledge_tag"],
                     knowledge_range=e["knowledge_range"],
                     knowledge_locations=e["knowledge_locations"],
                     importance=e["importance"],
                     aliases=_json_list(e["aliases"]),
                     scope=json.loads(e["scope"] or "{}"),
                     relations=json.loads(e["relations"] or "{}"),
                     source_notes=e["source_notes"],
                     # The clone's keys/content are identical to the
                     # source row's, so its stored vector is reused
                     # verbatim instead of re-embedding every entry
                     # (falls back to embedding only if the source row
                     # never had a vector). Same row, same bytes, so the
                     # same stamp -- dropping it here turned every cloned
                     # book into one judged on width alone.
                     embedding=_vec(e["embedding"]),
                     embedding_model=e["embedding_model"],
                     embedding_dim=e["embedding_dim"])
    
    # Pass 2: Remap parent IDs
    for old_id, new_id in old_to_new.items():
        src = q("SELECT parent_id FROM lorebooks WHERE id=?", (old_id,), one=True)
        if src and src["parent_id"] and src["parent_id"] in old_to_new:
            qi("UPDATE lorebooks SET parent_id=? WHERE id=?",
               (old_to_new[src["parent_id"]], new_id))
        elif src and src["parent_id"]:
            # Parent was outside the subtree, null it out
            qi("UPDATE lorebooks SET parent_id=NULL WHERE id=?", (new_id,))
    
    # Pass 3: Copy links
    if include_links:
        links = dump_lorebook_links(book_ids)
        restore_lorebook_links(chat_id, old_to_new, links)
    
    return old_to_new

def duplicate_lorebook_for_chat(src_id, chat_id):
    """Legacy single-book duplication for backward compatibility."""
    return list(duplicate_lorebook_tree_for_chat(src_id, chat_id, include_links=False).values())[0]

def delete_lore(entry_id):
    qi("DELETE FROM lore_entries WHERE id=?", (entry_id,))


# ---- Overlays: one story's deviation from a library entry -----------------

#: The fields a story may override on a library entry. NULL inherits.
OVERLAY_FIELDS = ("keys", "content", "category", "title", "knowledge_tag",
                  "knowledge_range", "knowledge_locations", "circles",
                  "canon_locked")

#: Why an overlay exists. A closed set the engine owns: a hand edit made from
#: inside a story, the Writers' Room superseding an entry through a package,
#: or the one-time conversion of a pre-2026-09 chat copy.
OVERLAY_DISPOSITIONS = ("story_edit", "room_supersession", "migrated_copy")


def _row_dict(row):
    return dict(row) if not isinstance(row, dict) else dict(row)


def lore_overlays(chat_id, frame_id=None, entry_ids=None):
    """``{entry_id: overlay row}`` for one story and era. Empty when the
    story has never deviated from its library."""
    if chat_id is None:
        return {}
    sql = "SELECT * FROM lore_overlays WHERE chat_id=? AND frame_id IS ?"
    args = [chat_id, frame_id]
    if entry_ids is not None:
        ids = [int(i) for i in entry_ids]
        if not ids:
            return {}
        sql += " AND entry_id IN (%s)" % ",".join("?" * len(ids))
        args += ids
    return {r["entry_id"]: dict(r) for r in q(sql, tuple(args))}


def merge_overlay(row, overlay):
    """The library row as this story reads it. A NULL overlay field inherits
    the library value; a set one overrides it. The merged row carries
    `overlay_id` and `overlay_disposition` so a reader can say so."""
    out = _row_dict(row)
    if not overlay:
        out["overlay_id"] = None
        return out
    for field in OVERLAY_FIELDS + ("embedding", "embedding_model", "embedding_dim"):
        value = overlay.get(field)
        if value is not None:
            out[field] = value
    out["overlay_id"] = overlay["id"]
    out["overlay_disposition"] = overlay.get("disposition")
    out["overlay_source_notes"] = overlay.get("source_notes") or ""
    return out


def lore_rows(lorebook_ids, *, chat_id=None, frame_id=None,
              exclude_categories=None, order="lorebook_id, id"):
    """Every entry of the given books, as ``chat_id`` reads them: the library
    rows with the story's overlays merged. ``chat_id`` None reads the library
    as written."""
    ids = _ids(lorebook_ids)
    if not ids:
        return []
    ph = ",".join("?" * len(ids))
    rows = q(f"SELECT * FROM lore_entries WHERE lorebook_id IN ({ph}) "
             f"ORDER BY {order}", tuple(ids))
    overlays = lore_overlays(chat_id, frame_id) if chat_id is not None else {}
    merged = [merge_overlay(r, overlays.get(r["id"])) for r in rows]
    if exclude_categories:
        merged = [r for r in merged
                  if (r.get("category") or "other") not in exclude_categories]
    return merged


def lore_overlay(chat_id, entry_id, frame_id=None):
    row = q("SELECT * FROM lore_overlays WHERE chat_id=? AND entry_id=? "
            "AND frame_id IS ?", (chat_id, entry_id, frame_id), one=True)
    return dict(row) if row else None


def set_lore_overlay(chat_id, entry_id, *, frame_id=None, turn_idx=None,
                     disposition="story_edit", source_notes="",
                     embedding=None, embedding_model=None, embedding_dim=None,
                     **fields):
    """Record what one story changes about one LIBRARY entry.

    Refused for an entry of a book the story OWNS (edit the entry itself --
    an overlay on one's own row is a copy wearing a new name) and for an
    entry of another story's book (that story's canon is not this one's to
    read, let alone amend). Fields not passed are left as they were; a field
    passed as None is cleared back to inheriting the library. When the text
    changes and no vector is handed in, the merged text is embedded so
    retrieval ranks the story's reading, not the library's.
    """
    entry = q("SELECT e.*, b.chat_id AS book_chat FROM lore_entries e "
              "JOIN lorebooks b ON b.id=e.lorebook_id WHERE e.id=?",
              (entry_id,), one=True)
    if entry is None:
        raise ValueError("no lore entry %r" % entry_id)
    if entry["book_chat"] is not None:
        if entry["book_chat"] == chat_id:
            raise ValueError("the story owns this entry; edit it directly "
                             "rather than overlaying it")
        raise ValueError("this entry belongs to another story's book")
    if disposition not in OVERLAY_DISPOSITIONS:
        raise ValueError("overlay disposition %r is not one of %s"
                         % (disposition, ", ".join(OVERLAY_DISPOSITIONS)))
    unknown = [k for k in fields if k not in OVERLAY_FIELDS]
    if unknown:
        raise ValueError("an overlay may not set %s" % ", ".join(sorted(unknown)))
    existing = lore_overlay(chat_id, entry_id, frame_id) or {}
    values = {f: existing.get(f) for f in OVERLAY_FIELDS}
    for key, value in fields.items():
        if key in ("knowledge_locations", "circles") and isinstance(value, (list, tuple, set)):
            value = _storage_json(list(value))
        if key == "canon_locked" and value is not None:
            value = int(bool(value))
        values[key] = value
    text_changed = ("keys" in fields or "content" in fields)
    vec, model_key, dims = existing.get("embedding"), existing.get("embedding_model"), existing.get("embedding_dim")
    if embedding is not None:
        model_key, dims = _carried_stamp(embedding, embedding_model, embedding_dim)
        vec = _blob(embedding)
    elif text_changed and (values.get("keys") is not None or values.get("content") is not None):
        merged_keys = values["keys"] if values.get("keys") is not None else entry["keys"]
        merged_content = values["content"] if values.get("content") is not None else entry["content"]
        v, model_key, dims = _embed_lore_document(merged_keys, merged_content)
        vec = _blob(v)
    elif text_changed:
        vec, model_key, dims = None, None, None
    with transaction():
        qi("DELETE FROM lore_overlays WHERE chat_id=? AND entry_id=? AND frame_id IS ?",
           (chat_id, entry_id, frame_id))
        qi("""INSERT INTO lore_overlays(
                chat_id, frame_id, entry_id, keys, content, category, title,
                knowledge_tag, knowledge_range, knowledge_locations, circles,
                canon_locked, embedding, embedding_model, embedding_dim,
                disposition, source_notes, turn_idx, created
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
           (chat_id, frame_id, entry_id, values["keys"], values["content"],
            values["category"], values["title"], values["knowledge_tag"],
            values["knowledge_range"], values["knowledge_locations"],
            values["circles"], values["canon_locked"], vec, model_key, dims,
            disposition, source_notes or "", turn_idx, time.time()))
    return lore_overlay(chat_id, entry_id, frame_id)


def clear_lore_overlay(chat_id, entry_id, frame_id=None):
    """Back to the library's reading. True when a row was removed."""
    before = lore_overlay(chat_id, entry_id, frame_id)
    if before is None:
        return False
    qi("DELETE FROM lore_overlays WHERE chat_id=? AND entry_id=? AND frame_id IS ?",
       (chat_id, entry_id, frame_id))
    return True

def search_lore(lorebook_ids, query, k=6, exclude_categories=None, *,
                chat_id=None, frame_id=None):
    """Rank the books' entries against ``query``. With ``chat_id``, the
    entries are read as that story reads them -- library rows with the
    story's overlays merged (`lore_rows`), the overlay's own vector ranking
    where the story changed the text. Without it, the library as written.
    The keyword term always scores the library text (the FTS index holds
    the entry, not its overlays); an overlay that rewrote an entry ranks by
    meaning alone on that term."""
    # lorebook_ids may be a plain list/int (existing callers, unweighted --
    # every book competes as an equal) or a {book_id: weight} dict as
    # returned by chat_lorebook_weights -- _ids() already extracts the id
    # list correctly from either (iterating a dict yields its keys), so
    # this only changes behavior for callers that opt in by passing the
    # richer shape. Previously an ancestor several hops up the lorebook
    # tree, or a reference_only-linked book, scored identically to a
    # book the chat is actually attached to -- resolve_lorebook_graph
    # computed a meaningful per-book weight for exactly this and it was
    # discarded the moment chat_lorebook_ids flattened it to bare ids.
    weights = lorebook_ids if isinstance(lorebook_ids, dict) else None
    ids = _ids(lorebook_ids)
    if not ids:
        return []
    rows = lore_rows(ids, chat_id=chat_id, frame_id=frame_id,
                     exclude_categories=exclude_categories, order="id")
    if not rows:
        return []
    _batch = embed_texts_meta([query or ""])
    qv = _batch.vectors[0] if _batch.vectors else None
    kw = _kw_scores("lore_fts", query)
    scored = []
    # HOW MANY ROWS AM I SCORING BLIND? `_cos` returns 0.0 when the vectors
    # are incomparable -- it cannot raise, because it is called in a ranking
    # loop over rows embedded at different times -- and 0.0 is also the honest
    # score for a genuinely unrelated entry. So an entry left behind by a
    # retired embedding model is INDISTINGUISHABLE from one that simply does
    # not match, and it silently forfeits the 0.65 it can never win back.
    #
    # Measured on a corpus that had run this way for months: 1,061 of 1,418
    # lore entries carried 256-dimension vectors while the configured model
    # emits 2,560, so three quarters of the corpus was competing on the 0.35
    # keyword term alone. One lorebook was 10 of 15 stale, and the entry a
    # reader kept asking after -- a room nobody could get the agents to
    # describe -- was among them. Nothing anywhere said so.
    #
    # Compatibility is model key AND length, matching `search_memories`' rule
    # -- length alone would cosine-compare two different models that happen to
    # share a dimension and produce garbage similarity with no warning
    # (docs/experiments/AUDIT_MEMORY.md 1.2). One legacy carve-out, and it is
    # the SAME one the rebuild machinery holds: a NULL stamp at the live
    # width predates stamping and is trusted, because the rebuild's stale
    # predicate deliberately never selects those rows -- blinding them here
    # would be a hole nothing in the engine ever heals. A WRONG stamp (which
    # includes the backfill's `unknown:<dims>`) is blind and rebuild-selected,
    # so the stamped world converges to the strict rule. The residual is
    # stated: a NULL-stamped row whose vector came from a RETIRED model at
    # the live width still cosine-compares as garbage, uncounted -- closable
    # only by running the stamp backfill plus a rebuild, which is a host
    # decision, not an ambient one.
    #
    # Counted, not repaired: re-embedding is a migration and this is a ranking
    # loop. What this owes its caller is the number.
    blind = 0
    for r in rows:
        vec = _vec(r["embedding"])
        compatible = (qv is not None and vec is not None
                      and len(qv) == len(vec)
                      and (r["embedding_model"] == _batch.model_key
                           or r["embedding_model"] is None))
        if qv is not None and vec is not None and not compatible:
            blind += 1
        s = (0.65 * (_cos(qv, vec) if compatible else 0.0)
             + 0.35 * kw.get(r["id"], 0.0)
             + (0.1 if r["canon_locked"] else 0.0)
             + (0.05 * (r["importance"] or 0.5)))
        if weights is not None:
            s *= (0.7 + 0.3 * weights.get(r["lorebook_id"], 1.0))
        scored.append((s, r))
    if blind:
        logger.warning(
            "lore search scored %d of %d entries blind: their embedding "
            "model or dimension does not match the configured model, so "
            "only the keyword term ranked them. Re-embed to restore them.",
            blind, len(rows))
    scored.sort(key=lambda x: -x[0])
    return [
        {"id": row["id"], "entry_uid": row["entry_uid"],
         "book_id": row["lorebook_id"], "keys": row["keys"],
         "content": row["content"], "category": row["category"] or "other",
         "locked": bool(row["canon_locked"]),
         "overlay": bool(row.get("overlay_id"))}
        for _, row in scored[:k]
    ]

def backfill_lore_embedding_stamps(batch=500):
    """Decide what embedded each unstamped lore entry, once, and record it.

    `lore_entries` gained `embedding_model`/`embedding_dim` long after it
    gained vectors, so every row written before that carries bytes and no
    provenance. This is the one-time retrofit that puts lore into the same
    reconciliation system `memories` has always been in -- after it, the
    column carries the answer and nothing ever hashes a corpus again.

    THE TEST IS PROVIDER-INDEPENDENT, which is the whole reason it can be
    trusted. `cheap_embed` is a pure function of the text, so "is this row the
    crc32 fallback" is answerable with the provider face-down: recompute it
    and compare bytes. Width alone cannot answer that -- width is relative to
    whatever the provider happens to be emitting right now, which is exactly
    how a degraded provider inverts the question.

    A row that is not the fallback is stamped with its WIDTH and a model of
    `unknown:<dims>`. That is deliberately not a model name: the bytes cannot
    say which real model made them, and inventing one would record a guess as
    a fact. It is enough for the rebuild, which only needs to know whether a
    row matches what the live provider emits.

    ONE CAVEAT, WORTH KEEPING BESIDE IT. This proves "produced by the CURRENT
    `cheap_embed`". Change its bucket count or its hash and old fallback rows
    silently stop matching and read as real -- the same class of defect as the
    one this repairs, a comparison whose premise moved. That is an argument
    for stamping once and never asking again, which is what this does.
    """
    from llm.providers import cheap_embed
    report = {"scanned": 0, "fallback": 0, "real": 0, "unembedded": 0}
    while True:
        rows = q("SELECT id, keys, content, embedding FROM lore_entries "
                 "WHERE embedding_model IS NULL LIMIT ?", (batch,))
        if not rows:
            break
        with transaction():
            for row in rows:
                report["scanned"] += 1
                vec = _vec(row["embedding"])
                if vec is None:
                    # Never embedded is not the same as embedded badly, and
                    # they need different repairs. Stamped so the scan does
                    # not revisit it forever.
                    qi("UPDATE lore_entries SET embedding_model=?, "
                       "embedding_dim=? WHERE id=?",
                       ("none:unembedded", None, row["id"]))
                    report["unembedded"] += 1
                    continue
                text = (row["keys"] or "") + " " + (row["content"] or "")
                is_fallback = False
                if len(vec) == 256:
                    try:
                        want = np.asarray(cheap_embed(text), dtype=np.float32)
                        is_fallback = (len(want) == len(vec)
                                       and np.allclose(want, vec))
                    except Exception:  # noqa: BLE001 - cannot hash, cannot claim
                        is_fallback = False
                if is_fallback:
                    qi("UPDATE lore_entries SET embedding_model=?, "
                       "embedding_dim=? WHERE id=?",
                       ("cheap:crc32:256", 256, row["id"]))
                    report["fallback"] += 1
                else:
                    qi("UPDATE lore_entries SET embedding_model=?, "
                       "embedding_dim=? WHERE id=?",
                       ("unknown:%d" % len(vec), len(vec), row["id"]))
                    report["real"] += 1
    logger.info("memory: stamped %d lore entries (%d fallback, %d real, "
                "%d unembedded)", report["scanned"], report["fallback"],
                report["real"], report["unembedded"])
    return report


def lore_embedding_health(lorebook_ids=None):
    """How much of the lore corpus can still be ranked by meaning.

    THE QUESTION HAD NO ANSWER BEFORE THIS. The warning in `search_lore` only
    speaks when a search runs, which makes "is my lore reachable" a thing you
    discover by accident mid-story. This answers it on demand, per book when
    asked, so a corpus can be checked before it is trusted.

    `stale` counts entries whose vector cannot be compared against the current
    model's output at all. They are not gone -- the keyword term still ranks
    them -- but they compete for 0.35 against rivals playing for 1.0, which in
    practice means they never surface.
    """
    # MEASUREMENT MUST NOT DECLINE WHEN THE PROVIDER IS DOWN -- that is
    # precisely when somebody is looking. `embed_texts` degrades silently to a
    # 256-wide hash, so asking IT what the live width is turns every real
    # 2,560-wide entry into a "stale" one and reports the corpus backwards.
    # The stamp on the rows is provider-independent, so it is read first and
    # the probe is only a fallback for a corpus the backfill has not reached.
    live = _stamped_live_dimensions()
    probed = False
    if live is None:
        try:
            live = len(embed_texts([""])[0])
            probed = True
        except Exception:  # noqa: BLE001 - no provider is not a corpus finding
            live = None
    ids = _ids(lorebook_ids) if lorebook_ids is not None else None
    if ids:
        ph = ",".join("?" * len(ids))
        rows = q(f"SELECT lorebook_id, embedding, embedding_model, "
                 f"embedding_dim FROM lore_entries "
                 f"WHERE lorebook_id IN ({ph})", tuple(ids))
    else:
        rows = q("SELECT lorebook_id, embedding, embedding_model, "
                 "embedding_dim FROM lore_entries")
    total = stale = unembedded = unstamped = 0
    fallback = 0
    by_book = {}
    for r in rows or []:
        total += 1
        vec = _vec(r["embedding"])
        book = by_book.setdefault(r["lorebook_id"], {"total": 0, "stale": 0})
        book["total"] += 1
        if vec is None:
            unembedded += 1
            continue
        if r["embedding_model"] == "cheap:crc32:256":
            # Proven, not inferred: the backfill matched these against
            # `cheap_embed` of their own text. They were never embedded
            # semantically at all.
            fallback += 1
        if r["embedding_model"] is None:
            unstamped += 1
        width = r["embedding_dim"] or len(vec)
        if live is not None and width != live:
            stale += 1
            book["stale"] += 1
    return {"total": total, "stale": stale, "unembedded": unembedded,
            "fallback": fallback, "unstamped": unstamped,
            "current_dimensions": live, "probed_provider": probed,
            "books": {k: v for k, v in by_book.items() if v["stale"]}}


def _stamped_live_dimensions():
    """The width the engine's writes use: asked of the provider when it is
    answering, and of what it recorded when it is not.

    THE PROBE IS AUTHORITATIVE WHEN IT IS HEALTHY, and `embed_texts_meta` says
    which it is -- `fallback` is exactly that flag. Asking `embed_texts`
    instead cannot tell the two apart, which is how an earlier version of this
    reported a corpus backwards during an outage.

    STAMPS ARE THE FALLBACK, NOT THE FIRST ANSWER, because reading them alone
    inverts the moment a genuinely current model is NARROWER than a retired
    one: "widest real stamp" would then pick the stranded space as the
    reference and report every correct row as needing repair. That has not
    happened here -- the live space is the wider one -- and it is one model
    change away.

    Within the stamps, widest-real rather than most-common: `cheap:crc32:256`
    is easily the majority on a corpus that needs repairing, and a majority
    vote would call a wholly broken corpus healthy.
    """
    try:
        # No retry: this is a MEASUREMENT, and it runs while a host is
        # waiting. A degraded provider is an answer here, not a failure to
        # work around -- the stamps below are the fallback that matters.
        probe = embed_texts_meta([""], retry=None)
        if probe.dimensions and not probe.fallback:
            return int(probe.dimensions)
    except Exception:  # noqa: BLE001 - an unreachable provider is not an answer
        pass
    rows = q("SELECT embedding_dim AS dim FROM memories "
             "WHERE embedding_dim IS NOT NULL "
             "AND embedding_model IS NOT NULL "
             "AND embedding_model != 'cheap:crc32:256' "
             "ORDER BY embedding_dim DESC LIMIT 1")
    if rows and rows[0]["dim"]:
        return int(rows[0]["dim"])
    rows = q("SELECT MAX(embedding_dim) AS dim FROM lore_entries "
             "WHERE embedding_model IS NOT NULL "
             "AND embedding_model != 'cheap:crc32:256'")
    if rows and rows[0]["dim"]:
        return int(rows[0]["dim"])
    return None


def knowledge_circles(value):
    """Circle names, normalised for comparison. Accepts a JSON list (how the
    columns store it), a real list, or a blank."""
    if not value:
        return set()
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            value = [value]
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple, set)):
        return set()
    return {str(v).strip().casefold() for v in value if str(v or "").strip()}


def declared_circles(lorebook_ids, chat_id=None, frame_id=None):
    """Every compartment the given books declare, at book or entry level --
    and, with ``chat_id``, at the story's overlay level too.

    Exists so a mind can be told it is an OUTSIDER on purpose rather than by
    omission. `knowledge.circles` is a field, and an empty field fails
    silently: a character sheet written before the story's books were
    compartmented reads as complete and quietly receives the public world
    only, which looks exactly like a model that has forgotten its own
    expertise. The engine can see the difference, so it should say so.
    """
    ids = _ids(lorebook_ids)
    if not ids:
        return set()
    ph = ",".join("?" * len(ids))
    out = set()
    for r in q(f"SELECT default_circles AS c FROM lorebooks WHERE id IN ({ph})",
               tuple(ids)):
        out |= knowledge_circles(r["c"])
    for r in q(f"SELECT circles AS c FROM lore_entries "
               f"WHERE lorebook_id IN ({ph}) AND circles IS NOT NULL", tuple(ids)):
        out |= knowledge_circles(r["c"])
    if chat_id is not None:
        for overlay in lore_overlays(chat_id, frame_id).values():
            if overlay.get("circles") is not None:
                out |= knowledge_circles(overlay["circles"])
    return out


def knowledge_for_character(lorebook_ids, char_room, known_tags,
                            excluded_titles, circles=None, limit=30, *,
                            chat_id=None, frame_id=None):
    """World knowledge this mind may hold, on three ORTHOGONAL axes.

    With ``chat_id``, the entries are read as that story reads them: the
    library rows with the story's overlays merged, so a fact the story
    amended reaches its minds amended, and a compartment the story opened
    or closed on an entry is the compartment that gates it.

    DEPTH (`knowledge_tag`) -- how hard the fact is to know: common,
    scholarly, esoteric, matched against the character's own access tags. An
    entry with NO depth tag is not character knowledge at all; it is
    retrieval material the mapping stage selects for the Director
    (`agents.common.lore_for`).

    COMPARTMENT (`circles`, inherited from the book's `default_circles`) --
    WHO may know it. Empty is public. Non-empty admits only a character who
    belongs to one of the named circles. This is the axis depth cannot
    express: a clandestine organisation's existence is not hard to
    understand, it is KEPT, and a villager two miles from the site must read
    exactly the public world however scholarly they are.

    RANGE (`knowledge_range` + `knowledge_locations`) -- where it applies.

    Reachability used to be a CATEGORY: the query selected
    `category='knowledge'` and nothing else. Measured across every story on
    disk, 25 of 2,671 entries were in that category (0.9%), while 974 entries
    in OTHER categories already carried an explicit depth tag and reached
    nobody because of their filing. A fact is routinely both things at once
    -- "a Scranton Reality Anchor nullifies reality-bending" is `mechanic` by
    the authored vocabulary AND something a Foundation researcher knows -- so
    the taxonomy forced a choice in which filing it correctly removed it from
    every mind. Live, chat 84: the entry was selected into `relevant_lore` on
    every turn, the Director held it, and Dr. Moon's `world_knowledge` was
    empty on all of them.
    """
    ids = _ids(lorebook_ids)
    if not ids or not known_tags:
        return []
    ph = ",".join("?" * len(ids))
    book_circles = {
        r["id"]: knowledge_circles(r["default_circles"])
        for r in q(f"SELECT id, default_circles FROM lorebooks "
                   f"WHERE id IN ({ph})", tuple(ids))
    }
    rows = lore_rows(ids, chat_id=chat_id, frame_id=frame_id)
    mine = knowledge_circles(circles)
    excl = set(excluded_titles or [])
    seen_titles = set()
    results = []
    for r in rows:
        # An explicit depth tag is what OFFERS an entry to minds at all. The
        # old `or "common"` default cannot be kept here: with the category
        # filter gone it would hand every character all 2,671 entries.
        tag = str(r["knowledge_tag"] or "").strip().casefold()
        if not tag or tag not in known_tags:
            continue
        # The entry's own compartment, else the book's. A book is one setting
        # or one organisation, which is why the answer belongs there.
        #
        # UNSET is not EMPTY. NULL means the entry never answered and
        # inherits; an explicit `[]` means it did answer and the answer was
        # "public" -- a secret that has leaked into rumour. Folding the two
        # together (`circles or book_circles`) lets an entry join a different
        # compartment but never leave its book's, which makes the deliberate
        # exception unwritable.
        raw = r["circles"]
        needed = (book_circles.get(r["lorebook_id"]) or set()
                  if raw is None or not str(raw).strip()
                  else knowledge_circles(raw))
        if needed and not (needed & mine):
            continue
        title = r["title"] or ""
        if title and (title in excl or title in seen_titles):
            continue
        range_type = r["knowledge_range"] or "global"
        if range_type == "local":
            try:
                locations = json.loads(r["knowledge_locations"] or "[]")
            except Exception:
                locations = []
            if not locations:
                continue
            if char_room and char_room not in locations:
                continue
        results.append({"title": title, "content": r["content"],
                        "tag": tag, "range": range_type})
        if title:
            seen_titles.add(title)
        if len(results) >= limit:
            break
    return results

