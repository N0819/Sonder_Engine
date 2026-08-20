"""Autobiographical, hearsay and surmise summaries.

What a mind has consolidated out of individual memories, the evidence each
summary still points at, and the windowed consolidation that produces them."""

import hashlib
import json
import re
import time
import numpy as np
from collections import defaultdict
from core.db import q, qi, transaction
from llm.providers import embed_texts_meta, chat_complete
from llm.prompts import get_prompt
from core.db import active_frame_id as _active_frame_id

from mind.memory_common import (
    SUMMARY_SCOPE_FIRSTHAND, _SUMMARY_SCOPES, _UNSET, _blob, _cos, _ling,
    _summary_retrieval_text, _vec, summary_scope_for,
)
from mind.memory_write import (
    _json_list, _row_memory, effective_importance,
    note_failed_embedding_write,
)
from mind.memory_read import visible_memory_rows
from mind.memory_retrieval import provenance_context_label

# ---- Memory Summaries ----

def get_memory_summary(chat_id, char_id, scope="autobiographical", *,
                       before_turn_idx=None):
    """The character's CURRENT summary for this scope: the latest window.

    Since v23 a scope holds one row per window rather than one row overall, so
    this orders. Behaviour is unchanged for every bank that existed at the
    migration -- each had exactly one row, which is trivially the latest.

    What this does NOT return is the character's life. The consolidator is told
    to merge the previous summary forward, but it is told just as firmly to shed
    low-salience detail, and measurement says shedding wins: successive live
    windows share 3-16% of their text. So the latest window is the latest
    CHAPTER, and under the pre-v23 singleton the chapters before it were
    overwritten -- 53 of the 67 live banks have no summary covering their
    opening turns, and never will. The windows behind the latest are what
    `search_memory_summaries` reaches and what
    `build_character_memory_context` now sends alongside this one.

    `end_turn_idx` first, `id` as the tiebreak: two windows can legitimately
    close on the same turn (different scopes are separate rows, but a rerun
    that lands on the same boundary updates in place, and a restore renumbers
    ids), so the later row wins.
    """
    cutoff_sql = ""
    args = [chat_id, char_id, scope]
    if before_turn_idx is not None:
        cutoff_sql = " AND end_turn_idx < ?"
        args.append(int(before_turn_idx))
    row = q("SELECT * FROM memory_summaries WHERE chat_id=? AND char_id=? "
            "AND scope=?" + cutoff_sql +
            " ORDER BY end_turn_idx DESC, id DESC LIMIT 1",
            tuple(args), one=True)
    if not row:
        return {"scope": scope, "start_turn_idx": 0, "end_turn_idx": 0, "summary": "",
                "key_phrases": [], "unresolved_threads": [], "updated": None}
    return {"scope": row["scope"], "start_turn_idx": row["start_turn_idx"], "end_turn_idx": row["end_turn_idx"],
            "summary": row["summary"], "key_phrases": _json_list(row["key_phrases"]),
            "unresolved_threads": _json_list(row["unresolved_threads"]), "updated": row["updated"]}

def search_memory_summaries(chat_id, char_id, query, k=3, *,
                            scope="autobiographical", before_turn_idx=None,
                            exclude_latest=True, embedded=None):
    """Rank a character's summary WINDOWS by semantic similarity to `query`.

    The layer above raw recall: which ERA of my life is this beat about. Every
    summary has carried a maintained embedding since summaries existed -- built
    from `_summary_retrieval_text`, re-embedded on a model change, carried
    verbatim through every archive and checkpoint -- and until v23 no retrieval
    path read a single one of them, because the table held exactly one row per
    character per scope and there was nothing to rank.

    Scoped exactly like `search_memories`:

    - **char_id** is the bank. A summary is one character's autobiography and
      is never comparable across characters.
    - **before_turn_idx** is the same exclusive cutoff the read seam applies.
      A window that closed at or after the deciding turn describes how this
      beat turned out, and a mind deciding turn N must not read it. Windows
      are ranked on `end_turn_idx` because that is when the window's knowledge
      became complete.
    - **exclude_latest** drops the window `get_memory_summary` already returns,
      so a caller that sends both does not send it twice. Turn it off to rank
      the whole history.

    A window whose vector was built by a different embedding model scores 0.0
    and is skipped rather than compared -- the same rule the memory rankings
    follow, for the same reason: a cross-model cosine is noise wearing the
    shape of a score.

    Returns [{...window..., "score": float}], best first, `k` at most.
    """
    rows = q("SELECT * FROM memory_summaries WHERE chat_id=? AND char_id=? "
             "AND scope=? ORDER BY end_turn_idx DESC, id DESC",
             (chat_id, char_id, scope))
    if not rows:
        return []
    if before_turn_idx is not None:
        cutoff = int(before_turn_idx)
        rows = [r for r in rows if (r["end_turn_idx"] or 0) < cutoff]
    # "Latest" means latest VISIBLE window. Applying this before the temporal
    # cutoff drops the wrong row on a rerun: the future global latest vanishes
    # at the cutoff and the visible latest is then returned twice.
    if exclude_latest:
        rows = rows[1:]
    rows = [r for r in rows if (r["summary"] or "").strip()]
    if not rows:
        return []
    # `embedded` lets a caller that already vectorised this same query hand the
    # batch over; vectors[0] is the query in both this function's own call and
    # in search_memories', which is what makes them shareable.
    if embedded is None or not (getattr(embedded, "vectors", None) or ()):
        embedded = embed_texts_meta([str(query or "")])
    # A crc32 batch is NOT refused here, unlike `search_memories` and
    # `contrast_memory`, and the asymmetry is deliberate.
    #
    # There the hash competed against BM25 and exact-cue for a fixed number of
    # payload slots, so its noise displaced better candidates and cost 49
    # probes of 470. This lane has no second ranker: refusing the hash returns
    # no windows at all. What the hash costs here is the ORDER of a set of the
    # character's own summaries, each carrying its own turn range -- arbitrary
    # selection of real autobiography, rather than real material pushed out by
    # noise. Losing the lane entirely is the worse trade, so the sketch keeps
    # this job until something measures the alternative.
    qv = np.asarray(embedded.vectors[0], dtype=np.float32)
    live_model = embedded.model_key
    scored = []
    for r in rows:
        if (r["embedding_model"] or "") != live_model:
            continue
        v = _vec(r["embedding"])
        if v is None or v.shape != qv.shape:
            continue
        scored.append((_cos(qv, v), r))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    out = []
    for score, r in scored[:k]:
        out.append({
            "scope": r["scope"],
            "start_turn_idx": r["start_turn_idx"],
            "end_turn_idx": r["end_turn_idx"],
            "summary": r["summary"],
            "key_phrases": _json_list(r["key_phrases"]),
            "unresolved_threads": _json_list(r["unresolved_threads"]),
            "updated": r["updated"],
            "score": float(score),
        })
    return out


# Clause boundary, content-word regex and stopwords all come from the pack
# (`mind.memory.*`): "a sentence ends at a full stop followed by a capital"
# is an English typographic rule, and against Japanese punctuation it found
# one clause per summary and therefore one undifferentiated support set.
# Two shared content words is coincidence in prose this dense; three is a
# claim about the same thing. Calibrated against the live corpus rather than
# guessed -- at two, every clause matched every memory in its own window.
_SUPPORT_MIN_OVERLAP = 3
_SUPPORT_MAX_REFS = 3


def _content_words(text):
    return {w for w in _ling("_SUPPORT_WORD_RE").findall(
                str(text or "").casefold())
            if w not in _ling("_SUPPORT_STOPWORDS")}


def derive_summary_support(summary, memories):
    """Which of this window's memories stand behind each clause of a summary.

    Summaries move appraisal and speech. They are deliberately barred from
    reinforcing durable belief -- which contains most of the danger -- but a
    consolidator sentence that no memory supports still reaches the character
    and currently leaves no trace when it does. This is the trace.

    Derived HOST-SIDE, from the same window the consolidator was given, by
    content-word overlap. Deliberately not a model call and deliberately not
    embeddings: the question is "which stored rows does this sentence actually
    talk about", a lexical question with a checkable answer, and an
    audit trail produced by the same kind of process it audits is not one.

    An empty `support_refs` is a RESULT, not a failure -- it says this clause
    generalises, compresses across several rows, or was invented. The three
    are not distinguished here, because distinguishing them is a judgement and
    this is a measurement. What matters is that the clause is now countable.

    Refs are `event_key`s rather than row ids, so they survive checkpoint
    restore (delete-and-reinsert changes every id) and chat branching without
    remapping -- the same reasoning that keeps disputes off id-keyed edges.
    """
    text = " ".join(str(summary or "").split())
    if not text:
        return []
    rows = []
    for mem in memories or []:
        if not isinstance(mem, dict):
            continue
        ref = str(mem.get("event_key") or "").strip()
        if not ref:
            continue
        words = _content_words(mem.get("gist")) | _content_words(mem.get("content"))
        for phrase in (mem.get("key_phrases") or []):
            words |= _content_words(phrase)
        for entity in (mem.get("entities") or []):
            words |= _content_words(entity)
        rows.append((ref, words, mem.get("provenance")))
    out = []
    for clause in [c.strip() for c in _ling("_CLAUSE_SPLIT").split(text)
                   if c.strip()]:
        cw = _content_words(clause)
        scored = sorted(
            ((len(cw & words), ref, prov) for ref, words, prov in rows
             if len(cw & words) >= _SUPPORT_MIN_OVERLAP),
            key=lambda item: (-item[0], item[1]))[:_SUPPORT_MAX_REFS]
        out.append({
            "claim": clause,
            "support_refs": [ref for _n, ref, _p in scored],
            # The epistemic class of the STRONGEST supporter. A clause built
            # on what the character was told must not read as something they
            # saw, and with no supporter at all it is left blank rather than
            # defaulted to first-hand -- the safest wrong answer here is the
            # one that claims the least.
            "epistemic_origin": (provenance_context_label(scored[0][2])
                                 if scored else ""),
        })
    return out


def summary_support(chat_id, char_id, scope="autobiographical", *,
                    end_turn_idx=None):
    """The stored per-clause support for a summary, or []. Never raises on a
    malformed blob -- an unreadable audit trail must not make the summary it
    describes unreadable."""
    sql = ("SELECT support FROM memory_summaries WHERE chat_id=? AND char_id=? "
           "AND scope=?")
    params = [chat_id, char_id, scope]
    if end_turn_idx is not None:
        sql += " AND end_turn_idx=?"
        params.append(int(end_turn_idx))
    row = q(sql + " ORDER BY end_turn_idx DESC, id DESC", tuple(params), one=True)
    if not row:
        return []
    try:
        parsed = json.loads(row["support"] or "[]")
    except (TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


def save_memory_summary(chat_id, char_id, summary, *, scope="autobiographical", start_turn_idx=0,
                        end_turn_idx=0, key_phrases=None, unresolved_threads=None,
                        embedding=None, embedding_model=None, embedding_dim=None,
                        support=None):
    key_phrases = key_phrases or []
    unresolved_threads = unresolved_threads or []
    support = support or []
    # Checkpoint/export restore passes the previously stored vector back
    # in verbatim (raw bytes) so a restore never re-embeds -- every
    # normal caller omits it and embeds exactly as before.
    if embedding is None or not embedding_model:
        retrieval_text = _summary_retrieval_text(summary, key_phrases, unresolved_threads)
        embedded = embed_texts_meta([retrieval_text])
        embedding = _blob(embedded.vectors[0])
        embedding_model = embedded.model_key
        embedding_dim = embedded.dimensions
    qi("""INSERT INTO memory_summaries(chat_id,char_id,scope,start_turn_idx,end_turn_idx,summary,
        key_phrases,unresolved_threads,support,embedding,embedding_model,embedding_dim,updated)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(chat_id,char_id,scope,end_turn_idx) DO UPDATE SET
        start_turn_idx=excluded.start_turn_idx, end_turn_idx=excluded.end_turn_idx,
        summary=excluded.summary, key_phrases=excluded.key_phrases,
        unresolved_threads=excluded.unresolved_threads, support=excluded.support,
        embedding=excluded.embedding,
        embedding_model=excluded.embedding_model, embedding_dim=excluded.embedding_dim,
        updated=excluded.updated""",
       (chat_id, char_id, scope, start_turn_idx, end_turn_idx, summary or "",
        json.dumps(key_phrases, ensure_ascii=False), json.dumps(unresolved_threads, ensure_ascii=False),
        json.dumps(support, ensure_ascii=False),
        embedding, embedding_model, embedding_dim, time.time()))
    if embedding_model == "cheap:crc32:256":
        # Queued by identity rather than rowid: this statement UPSERTs on
        # (chat, char, scope, end_turn_idx), so `qi`'s lastrowid is not
        # reliably this row's id on the conflict path.
        row = q("SELECT id FROM memory_summaries WHERE chat_id=? AND char_id=? "
                "AND scope=? AND end_turn_idx=?",
                (chat_id, char_id, scope, end_turn_idx), one=True)
        if row:
            note_failed_embedding_write("memory_summaries", [row["id"]])


def _portable_memory_event_key(mem):
    """A deterministic event handle for a legacy row that has none.

    Row ids are database-local and change on archive/checkpoint restore.  The
    fields below are the portable identity of the remembered event; once
    written, the resulting key travels in every existing dump format.
    """
    document = {
        "turn_idx": mem.get("turn_idx"),
        "kind": mem.get("kind") or "episodic",
        "category": mem.get("category") or "episode",
        "provenance": mem.get("provenance") or "witnessed",
        "content": " ".join(str(mem.get("content") or "").split()),
        "gist": " ".join(str(mem.get("gist") or "").split()),
        "key_phrases": list(mem.get("key_phrases") or []),
        "entities": list(mem.get("entities") or []),
        "location": str(mem.get("location") or ""),
        "emotional_context": str(mem.get("emotional_context") or ""),
    }
    raw = json.dumps(document, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":"))
    return "event:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def backfill_missing_memory_event_keys(chat_id, char_id=None):
    """Give legacy memories stable, portable citation handles.

    Exact duplicate legacy rows receive deterministic occurrence suffixes in
    row order.  Once assigned, dumps/restores carry the key verbatim, so the
    suffix is never recomputed from a new database's row ids.
    """
    args = [chat_id]
    scope = "chat_id=? AND event_key=''"
    if char_id is not None:
        scope += " AND char_id=?"
        args.append(char_id)
    rows = q("SELECT * FROM memories WHERE " + scope +
             " ORDER BY char_id, id", tuple(args))
    if not rows:
        return 0
    used = defaultdict(int)
    repaired = 0
    with transaction():
        for row in rows:
            mem = _row_memory(row)
            base = _portable_memory_event_key(mem)
            used[(row["char_id"], base)] += 1
            ordinal = used[(row["char_id"], base)]
            key = base if ordinal == 1 else f"{base}:{ordinal}"
            # A generated key can collide with an already-keyed identical
            # import. Keep the handle stable and advance only the suffix.
            while q("SELECT 1 FROM memories WHERE chat_id=? AND char_id=? "
                    "AND event_key=?", (chat_id, row["char_id"], key), one=True):
                ordinal += 1
                key = f"{base}:{ordinal}"
            qi("UPDATE memories SET event_key=? WHERE id=? AND event_key=''",
               (key, row["id"]))
            repaired += 1
    return repaired

_EMPTY_VIEW_MARKERS = (
    "you are in an unspecified area",
    "you register nothing new",
)


def _empty_view_markers():
    """The phrases that mean "nothing happened", in every installed language.

    The literals above are English, so a Japanese empty view matched none of
    them and was consolidated into autobiography -- an absence written up as
    something the character lived through, which is the exact failure this
    guard exists to prevent. The English strings are KEPT rather than
    replaced: rows written before packs existed still carry them.
    """
    from language_runtime import compositor_value, installed_language_packs

    markers = list(_EMPTY_VIEW_MARKERS)
    for language_id in installed_language_packs():
        try:
            templates = compositor_value("templates", language_id)
        except Exception:
            continue
        phrase = str(templates.get("narrator_nothing") or "").strip()
        if phrase:
            markers.append(phrase.casefold().rstrip("。."))
    return tuple(dict.fromkeys(markers))


def _is_empty_view(text):
    """True when a perception view records no event worth remembering."""
    body = " ".join(str(text or "").split()).strip().casefold().rstrip("。.")
    if not body:
        return True
    return any(body == m or body.startswith(m) and len(body) < len(m) + 25
               for m in _empty_view_markers())


def _substantive(memories):
    """The memories in this window that record something that happened."""
    return [m for m in memories
            if not _is_empty_view(m.get("content") or m.get("gist") or "")]


def _write_consolidated_window(chat_id, char_id, char_name, memories, previous_summary):
    """The consolidator call and the rows it produces, for ONE window.

    Shared by the forward path (`consolidate_character_memory`, which then
    archives) and the backward one (`backfill_memory_summary_windows`, which
    must not). Factored out when the second caller arrived rather than
    duplicated: the epistemic-scope rule below is the kind of thing that gets
    fixed in one copy.

    Returns the parsed consolidator result.
    """
    payload = {
        "character": char_name,
        "previous_summary": previous_summary,
        "memories_chronological": [
            {"id": m["id"], "turn_idx": m["turn_idx"], "category": m["category"],
             "provenance": m["provenance"], "salience": m["salience"], "confidence": m["confidence"],
             "gist": m["gist"], "details": m["content"], "key_phrases": m["key_phrases"],
             "entities": m["entities"], "location": m["location"], "emotional_context": m["emotional_context"]}
            for m in memories
        ],
    }
    raw = chat_complete("utility", get_prompt("memory_consolidate"),
                        json.dumps(payload, ensure_ascii=False), temperature=0.1, max_tokens=5000)
    try:
        result = json.loads(raw)
    except Exception:
        match = re.search(r"\{.*\}", raw or "", re.S)
        if not match:
            raise RuntimeError("Memory consolidator returned invalid JSON")
        result = json.loads(re.sub(r",\s*([}\]])", r"\1", match.group(0)))
    start_turn = min(m["turn_idx"] for m in memories)
    end_turn = max(m["turn_idx"] for m in memories)
    # One row per epistemic class. The first-hand row is written
    # unconditionally, even when this window produced nothing first-hand,
    # because maybe_consolidate_character_memory reads ITS end_turn_idx as the
    # cursor -- skip it on a hearsay-only window and the same memories
    # re-consolidate forever.
    present = {summary_scope_for(m.get("provenance")) for m in memories}
    for scope, field, _label in _SUMMARY_SCOPES:
        text = str(result.get(field) or "").strip()
        if scope != SUMMARY_SCOPE_FIRSTHAND and not text and scope not in present:
            continue
        save_memory_summary(
            chat_id, char_id, text, scope=scope,
            start_turn_idx=start_turn, end_turn_idx=end_turn,
            key_phrases=(result.get("key_phrases") or []
                         if scope == SUMMARY_SCOPE_FIRSTHAND else []),
            unresolved_threads=(result.get("unresolved_threads") or []
                                if scope == SUMMARY_SCOPE_FIRSTHAND else []),
            # Scoped to the memories of THIS epistemic class: a first-hand
            # clause supported by something the character was only told would
            # be an audit trail that launders hearsay into experience.
            support=derive_summary_support(
                text, [m for m in memories
                       if summary_scope_for(m.get("provenance")) == scope]))
    return result


def memory_summary_coverage(chat_id, char_id, *, window=10):
    """How much of this character's life has a summary above it.

    The question the backfill button asks before offering itself. Counts only
    memories that record something -- a bank of empty-view placeholders has
    nothing to summarise and offering to rebuild it would burn a call per
    window to describe an absence.

    Returns {total, covered, uncovered, first_turn, floor, windows,
    missing_windows}.
    """
    rows = q("SELECT turn_idx, content, gist FROM memories WHERE chat_id=? AND "
             "char_id=? AND turn_idx IS NOT NULL", (chat_id, char_id))
    mems = [dict(r) for r in rows]
    real = _substantive(mems)
    spans = q("SELECT start_turn_idx s, end_turn_idx e FROM memory_summaries "
              "WHERE chat_id=? AND char_id=? AND scope=?",
              (chat_id, char_id, SUMMARY_SCOPE_FIRSTHAND))
    spans = [(r["s"], r["e"]) for r in spans]
    covered = sum(1 for m in real
                  if any(s <= m["turn_idx"] <= e for s, e in spans))
    first = min((m["turn_idx"] for m in real), default=None)
    floor = min((s for s, _e in spans), default=None)
    missing = 0
    if first is not None and floor is not None and floor > first:
        below = sorted({m["turn_idx"] for m in real if m["turn_idx"] < floor})
        edges = set()
        for t in below:
            edges.add(floor - ((floor - t + int(window) - 1) // int(window)) * int(window))
        missing = len(edges)
    return {
        "total": len(real), "covered": covered,
        "uncovered": len(real) - covered,
        "placeholders": len(mems) - len(real),
        "first_turn": first, "floor": floor,
        "windows": len(spans), "missing_windows": missing,
    }


def backfill_memory_summary_windows(chat_id, char_id, *, window=10,
                                    viewer_frame_id=_UNSET, on_window=None):
    """Rebuild the summary windows the pre-v23 singleton destroyed.

    Until schema v23 a scope held one row and each consolidation overwrote it,
    so a long story ends up with a summary of its most recent ten turns and
    nothing behind it. Measured on the live bank: 53 of 67 banks have no
    summary over their opening turns, and in the longest story (chat 38, 118
    turns) 82-87% of every character's memories sit under no summary at all.

    The raw memories survive -- nothing was ever deleted -- so the era is
    recoverable by consolidating it again. This walks FORWARD from the
    character's first memory to the earliest surviving window, in `window`-turn
    steps aligned to that window's boundary so the reconstructed cadence
    matches the live one, chaining each result into the next as
    `previous_summary` exactly as the forward path would have.

    Two things it deliberately does not do:

    - **It does not archive.** The forward path archives low-salience memories
      it has just folded in; doing that here would retire hundreds of rows at
      once on the strength of a summary written years after the fact.
    - **It does not move the consolidation cursor.**
      `maybe_consolidate_character_memory` reads the first-hand row's
      `end_turn_idx` as its cursor, and `get_memory_summary` orders by
      `end_turn_idx DESC` -- so writing OLDER windows leaves the cursor on the
      newest row, untouched. That is load-bearing, and tested.

    `on_window(start, end, count)` is called before each consolidator request,
    for progress on a long run.

    Returns {"windows": n_written, "turns": (lo, hi), "skipped": n_empty}.
    """
    char = q("SELECT name FROM characters WHERE id=?", (char_id,), one=True)
    if not char:
        raise ValueError("Character not found")
    row = q("SELECT MIN(start_turn_idx) AS s FROM memory_summaries "
            "WHERE chat_id=? AND char_id=?", (chat_id, char_id), one=True)
    floor = row["s"] if row else None
    if floor is None:
        # Nothing has ever been consolidated; the forward path is the right
        # tool and will produce the same windows without this one guessing.
        return {"windows": 0, "turns": None, "skipped": 0}
    rows = visible_memory_rows(
        chat_id, char_id, before_turn_idx=int(floor),
        viewer_frame_id=viewer_frame_id, include_archived=False,
        require_turn_idx=True)
    if not rows:
        return {"windows": 0, "turns": None, "skipped": 0}
    rows.sort(key=lambda r: (r["turn_idx"], r["id"]))
    memories = [_row_memory(r) for r in rows]
    lo, hi = memories[0]["turn_idx"], memories[-1]["turn_idx"]
    # Aligned to the SURVIVING window's boundary and counted backwards, so the
    # reconstructed windows abut it instead of overlapping it by a few turns.
    edges = []
    edge = int(floor)
    while edge > lo:
        edges.append(edge)
        edge -= int(window)
    edges.append(min(edge, lo))
    edges.reverse()
    previous = {"scope": SUMMARY_SCOPE_FIRSTHAND, "start_turn_idx": 0,
                "end_turn_idx": 0, "summary": "", "key_phrases": [],
                "unresolved_threads": []}
    written = skipped = 0
    for start, stop in zip(edges, edges[1:]):
        chunk = _substantive([m for m in memories
                              if start <= m["turn_idx"] < stop])
        if not chunk:
            # Either nobody was there, or every row is the engine's own
            # "unspecified area" placeholder from an off-screen beat. Neither
            # is an era, and summarising one writes a character fifty turns of
            # authored amnesia they never lived.
            skipped += 1
            continue
        if on_window:
            on_window(start, stop - 1, len(chunk))
        result = _write_consolidated_window(chat_id, char_id, char["name"],
                                            chunk, previous)
        written += 1
        previous = {
            "scope": SUMMARY_SCOPE_FIRSTHAND,
            "start_turn_idx": chunk[0]["turn_idx"],
            "end_turn_idx": chunk[-1]["turn_idx"],
            "summary": str(result.get("summary") or ""),
            "key_phrases": result.get("key_phrases") or [],
            "unresolved_threads": result.get("unresolved_threads") or [],
        }
    return {"windows": written, "turns": (lo, hi), "skipped": skipped}


def consolidate_character_memory(chat_id, char_id, *, through_turn_idx=None, archive_old=True,
                                 viewer_frame_id=_UNSET):
    char = q("SELECT name FROM characters WHERE id=?", (char_id,), one=True)
    if not char:
        raise ValueError("Character not found")
    old_summary = get_memory_summary(chat_id, char_id)
    # Everything up to old_summary["end_turn_idx"] is already folded into
    # old_summary (sent below as previous_summary) and archived rows were
    # already folded into some still-earlier summary -- resending either
    # gets the consolidator no new information but made the payload (and
    # its cost) grow without bound across a long chat's repeated
    # consolidation passes, since every call previously re-sent the
    # complete history since turn 0 regardless of what had already been
    # summarized.
    # turn_idx is GLOBAL play order shared by every frame, not per-era -- so
    # without the seam's frame filter, memories formed during a
    # flash-forward/-back would be folded into the singleton autobiographical
    # summary the moment play returns to the present and turn_idx catches up,
    # handing a character knowledge of events they have not diegetically
    # reached. `before_turn_idx` is exclusive and this window is inclusive of
    # `through_turn_idx`, hence the +1.
    rows = visible_memory_rows(
        chat_id, char_id,
        before_turn_idx=(None if through_turn_idx is None
                         else int(through_turn_idx) + 1),
        viewer_frame_id=viewer_frame_id,
        include_archived=False,
        since_turn_idx=(old_summary.get("end_turn_idx") or 0) + 1,
        require_turn_idx=True,
    )
    rows.sort(key=lambda r: (r["turn_idx"], r["id"]))
    memories = [_row_memory(r) for r in rows]
    if not memories:
        return old_summary
    start_turn = min(m["turn_idx"] for m in memories)
    end_turn = max(m["turn_idx"] for m in memories)
    substantive = _substantive(memories)
    if not substantive:
        # Every row in this window is the engine's own empty-view placeholder
        # (an off-screen character), so there is nothing to consolidate. The
        # cursor still has to advance -- maybe_consolidate reads THIS row's
        # end_turn_idx, and stalling it re-consolidates the same rows every
        # ten turns forever -- so carry the previous account forward unchanged
        # rather than asking a model to summarise an absence. No LLM call.
        save_memory_summary(
            chat_id, char_id, old_summary.get("summary") or "",
            scope=SUMMARY_SCOPE_FIRSTHAND,
            start_turn_idx=start_turn, end_turn_idx=end_turn,
            key_phrases=old_summary.get("key_phrases") or [],
            unresolved_threads=old_summary.get("unresolved_threads") or [])
        return get_memory_summary(chat_id, char_id)
    result = _write_consolidated_window(chat_id, char_id, char["name"],
                                        substantive, old_summary)
    if archive_old:
        cutoff = max(start_turn, end_turn - 12)
        # Archive ONLY memories that were part of THIS (frame-visible)
        # consolidation set. turn_idx is global play order, so the old
        # blanket UPDATE also archived another era's memories that were
        # correctly excluded from this summary (is_memory_visible filtered
        # them out of `memories`) and never folded into any summary.
        archivable = [
            m["id"] for m in memories
            if m.get("id") is not None
            and (m.get("turn_idx") or 0) < cutoff
            # The HIGHER of the two. A memory that turned out to matter is
            # not archived on the strength of how ordinary it looked at the
            # time -- which is the entire reason the two numbers are separate.
            and max(float(m.get("salience") or 0),
                    effective_importance(m)) < 0.72
            and m.get("category") not in ("promise", "relationship", "intention")
        ]
        if archivable:
            marks = ",".join("?" for _ in archivable)
            qi(f"UPDATE memories SET archived=1 WHERE id IN ({marks})", tuple(archivable))
    return {**get_memory_summary(chat_id, char_id), "stable_facts": result.get("stable_facts") or [], "memory_count": len(memories)}

def maybe_consolidate_character_memory(chat_id, char_id, current_turn_idx, *, frame_id=_UNSET):
    # A singleton per-character summary has nowhere to put "as of the
    # present era" vs. "as of the future flash-forward" -- consolidating
    # outside the present would permanently blend eras into one
    # autobiography with no way to un-blend it. Frozen to present only;
    # a frame visited away from the present just accumulates raw memories
    # (still correctly filtered by is_memory_visible) until play returns.
    #
    # frame_id is accepted explicitly (falling back to the ambient
    # contextvar only when the caller doesn't have it on hand) rather
    # than always trusting the contextvar, because the one real caller
    # that matters -- commit.py's per-character consolidation loop --
    # runs each character's check on a concurrent.futures.ThreadPoolExecutor
    # worker thread, and THAT does not propagate contextvars the way
    # agents/runtime.py's own bespoke thread-spawning helpers do (they
    # explicitly contextvars.copy_context() first). Reading the
    # contextvar from inside the worker thread would silently see the
    # default None on every call regardless of which frame's turn is
    # actually being committed, defeating this guard exactly the way
    # app.py's old streaming path defeated active_frame_id.
    fid = _active_frame_id.get() if frame_id is _UNSET else frame_id
    if fid is not None:
        return None
    summary = get_memory_summary(chat_id, char_id)
    last_turn = summary.get("end_turn_idx") or 0
    count = q("SELECT COUNT(*) AS c FROM memories WHERE chat_id=? AND char_id=? AND archived=0 AND turn_idx>?",
              (chat_id, char_id, last_turn), one=True)["c"]
    if current_turn_idx - last_turn < 10 and count < 40:
        return None
    return consolidate_character_memory(chat_id, char_id, through_turn_idx=current_turn_idx,
                                        viewer_frame_id=fid)

