"""How a memory becomes a row, and what to do when the embedding fails.

Normalisation, extraction, FTS mirroring, importance, the upsert, and the
background repair thread that finishes a write the provider could not."""

import json
import re
import threading
import time
from collections import defaultdict
from core.db import q, qi, transaction
from llm.providers import embed_texts_meta, embedding_model_key
from core.logging_utils import logger
from core.db import active_frame_id as _active_frame_id

from mind.memory_common import (
    MEMORY_CATEGORIES, MEMORY_PROVENANCE, _UNSET, _blob, _ling, _storage_json,
    _summary_retrieval_text,
)

# ---- Memory normalization and storage helpers ----

# The stopword set, the word regex and the two temporal cue tables all live
# in the pack (`mind.memory.*`). They decide FTS query terms, key phrases and
# whether a recall leans old or recent; word regexes anchored on `[A-Za-z]`
# return nothing at all on unspaced Japanese, so every query there was empty
# and every recall neutral, with no error anywhere to say so.

def _json_list(value) -> list:
    if isinstance(value, list):
        return value
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []

def _clamp(value, lo=0.0, hi=1.0):
    try:
        return max(lo, min(hi, float(value)))
    except Exception:
        return lo

def _clamp_signed(value, lo=-1.0, hi=1.0):
    try:
        return max(lo, min(hi, float(value)))
    except Exception:
        return 0.0

def _turn_idx_for(turn_id):
    if turn_id is None:
        return None
    row = q("SELECT idx FROM turns WHERE id=?", (turn_id,), one=True)
    return row["idx"] if row else None

def _default_category(kind: str) -> str:
    mapping = {
        "episodic": "episode", "episode": "episode",
        "dialogue": "dialogue", "inference": "inference",
        "semantic": "semantic", "relationship": "relationship",
        "promise": "promise", "intention": "intention",
    }
    return mapping.get(str(kind or "").lower(), "episode")

def _gist(text: str, limit: int = 240) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(text) <= limit:
        return text
    parts = re.split(r"(?<=[.!?])\s+", text)
    out = ""
    for part in parts:
        candidate = (out + " " + part).strip()
        if len(candidate) > limit:
            break
        out = candidate
    if out:
        return out
    clipped = text[:max(1, limit - 1)].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return (clipped or text[:max(1, limit - 1)]) + "…"

def _extract_entities(text: str, limit: int = 12) -> list[str]:
    text = str(text or "")
    # Capitalisation is an English convention for marking a name, and the
    # block list is English function words wearing it. Both live in the pack:
    # a script with no letter case has to recognise its names some other way,
    # and against this pattern found none at all.
    matches = list(_ling("_ENTITY_CANDIDATE_RE").finditer(text))
    blocked = _ling("_ENTITY_BLOCKED")
    stopwords = _ling("_STOPWORDS")
    sentence_end = _ling("_SENTENCE_END_CHARS")
    quote_chars = _ling("_QUOTE_CHARS")
    word_re = _ling("_WORD_RE")
    # Legacy inference rows encode their subject explicitly as
    # ``About <subject>: <claim>``.  Preserve that semantic handle even when
    # the subject is a lower-case role ("the stranger"), which capitalization
    # heuristics can never recover and confidence reconciliation requires.
    out = []
    for subject in re.findall(r"(?:^|[.!?]\s+)About\s+([^:\n]{1,80}):", text):
        subject = " ".join(subject.split()).strip()
        if subject and subject not in out:
            out.append(subject)
    for match in matches:
        c = match.group(0).strip()
        if c in blocked or c in out:
            continue
        # A stopword wearing a capital is never a name. The block list is a
        # hand-picked subset of this rule; the pack's stopword set closes the
        # words it happens not to spell ("About", "Because", "Said").
        if c.casefold() in stopwords:
            continue
        # And a candidate with no content word at all is not a retrieval
        # handle: entity matching is substring matching, so a stamped "Dr"
        # (the period splits it from its name, which survives on its own)
        # fires inside "drink" and "dragon", and "No"/"Ok"/"But She" fire
        # everywhere. Measured on the live corpus, this gate plus the two
        # above take re-extraction junk-stamping from 16.7% of rows to zero
        # at the cost of standalone two-letter names, which the pack word
        # regex already treats as below the token floor.
        if not any(tok not in stopwords
                   for tok in word_re.findall(c.lower())):
            continue
        # Capitalization alone does not make a sentence's first word an
        # entity.  A one-off single token at a sentence boundary is ambiguous
        # and was the source of labels such as adjectives, imperatives and
        # exclamations.  Keep multi-word proper forms and names that recur;
        # otherwise decline to invent an entity from typography alone.
        #
        # A quote mark opens an utterance, so a word right after one is
        # sentence-initial for this rule even though the preceding character
        # is not a sentence end. That bypass -- the guard read only ".!?" --
        # was junk-stamping quote-initial interjections ("Oh", "Uhmm") on
        # 9.9% of live rows re-extracted through this function
        # (docs/experiments/AUDIT_MEMORY.md 1.3). Both character classes come
        # from the language pack, like the rest of this recognizer.
        prefix = text[:match.start()].rstrip()
        at_sentence_start = (not prefix or prefix[-1] in sentence_end
                             or prefix[-1] in quote_chars)
        if at_sentence_start and " " not in c and not re.search(
                rf"\b{re.escape(c)}\b", text[match.end():]):
            continue
        out.append(c)
        if len(out) >= limit:
            break
    return out

def _extract_key_phrases(text: str, entities: list[str] | None = None, limit: int = 12) -> list[str]:
    """Key phrases from content: quoted spans, then frequent content words.

    `entities` is accepted for caller compatibility and deliberately UNUSED:
    key phrases used to append the entity list wholesale, which is how entity
    junk became key-phrase junk (docs/experiments/AUDIT_MEMORY.md 1.3) --
    and it was pure duplication even when clean, because `_memory_cues`, the
    FTS mirror and `_exact_cue_score` all already read entities as their own
    channel beside key phrases.
    """
    text = str(text or "")
    stopwords = _ling("_STOPWORDS")
    word_re = _ling("_WORD_RE")

    def _substantive(candidate):
        # A phrase must carry at least one content word to be a retrieval
        # cue; a quoted "Oh." or "'; said '" matches queries by punctuation
        # and function words alone, which is the exact-match poison the
        # audit measured firing on 71% of a live bank.
        return any(tok not in stopwords
                   for tok in word_re.findall(candidate.lower()))

    phrases = []
    # The quote pair(s) come from the language pack -- \u300c...\u300d is a quote in
    # a script this regex's ASCII pair would never match.
    for match in _ling("_QUOTED_SPAN_RE").finditer(text):
        # The pack patterns capture nothing (lookaround-delimited), so every
        # language reads the same way: the whole match is the span.
        quote = re.sub(r"\s+", " ", match.group(0) or "").strip()
        if (quote and _substantive(quote)
                and quote.lower() not in {p.lower() for p in phrases}):
            phrases.append(quote)
    words = word_re.findall(text.lower())
    counts = defaultdict(int)
    for i, w in enumerate(words):
        if w in stopwords:
            continue
        counts[w] += 1
        if i + 1 < len(words) and words[i + 1] not in stopwords:
            counts[f"{w} {words[i + 1]}"] += 1.5
    ranked = sorted(counts, key=lambda item: (-counts[item], -len(item.split()), item))
    for p in ranked:
        if p.lower() in {x.lower() for x in phrases}:
            continue
        phrases.append(p)
        if len(phrases) >= limit:
            break
    return phrases[:limit]

def _memory_document(data: dict) -> str:
    phrases = ", ".join(data.get("key_phrases") or [])
    entities = ", ".join(data.get("entities") or [])
    return "\n".join(p for p in (
        f"category: {data.get('category', 'episode')}",
        f"turn: {data.get('turn_idx', '')}",
        f"location: {data.get('location', '')}",
        f"people: {entities}",
        f"key phrases: {phrases}",
        f"gist: {data.get('gist', '')}",
        f"details: {data.get('content', '')}",
        f"source: {data.get('provenance', 'witnessed')}",
        f"emotion: {data.get('emotional_context', '')}",
    ) if not p.endswith(": "))

def _memory_cues(data: dict) -> str:
    return "\n".join(p for p in (
        data.get("gist") or "",
        ", ".join(data.get("key_phrases") or []),
        ", ".join(data.get("entities") or []),
        data.get("location") or "",
        data.get("category") or "",
    ) if p)

def _replace_memory_fts(memory_id: int, data: dict):
    qi("DELETE FROM memory_retrieval_fts WHERE memory_id=?", (str(memory_id),))
    qi(
        "INSERT INTO memory_retrieval_fts(memory_id,chat_id,char_id,gist,content,key_phrases,entities) VALUES(?,?,?,?,?,?,?)",
        (str(memory_id), str(data.get("chat_id") or ""), str(data.get("char_id") or ""),
         data.get("gist") or "", data.get("content") or "",
         ", ".join(data.get("key_phrases") or []), ", ".join(data.get("entities") or [])),
    )

def _delete_memory_fts(memory_id: int):
    qi("DELETE FROM memory_retrieval_fts WHERE memory_id=?", (str(memory_id),))

# How far one consequence moves a memory's importance, and the ceiling it
# climbs toward. Deliberately small and asymptotic: importance is evidence
# accumulating that a memory mattered, and one relationship change is evidence,
# not proof. Nothing here is driven by RETRIEVAL -- a memory that gets recalled
# a lot would then get recalled more, which is a popularity loop wearing the
# word "importance". Only consequences the engine can point at move it, which
# is also why `access_count` stays written and unread.
_IMPORTANCE_STEP = 0.12
_IMPORTANCE_CEILING = 0.97
# A memory the character has re-read moves further, because being wrong about
# something is a bigger fact about it than being cited once.
_IMPORTANCE_DISPUTE_STEP = 0.2
_MAX_DISPUTE_READING = 300


def _dispute_of(raw):
    """The stored re-reading, or None. Never raises on a malformed blob -- a
    corrupt dispute must not make a memory unreadable."""
    if not raw:
        return None
    try:
        out = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return out if isinstance(out, dict) and out.get("reading") else None


def effective_importance(mem) -> float:
    """How much this memory matters NOW: its revised importance if it has one,
    else the salience it was minted with. The single place that fallback is
    decided, so a reader cannot accidentally rank on the raw column and see
    NULL for every row that has never been revised."""
    if isinstance(mem, dict):
        value = mem.get("importance")
        if value is None:
            value = mem.get("salience")
    else:
        value = mem["importance"]
        if value is None:
            value = mem["salience"]
    return _clamp(value)


def _row_memory(row) -> dict:
    return {
        "id": row["id"], "chat_id": row["chat_id"], "char_id": row["char_id"],
        "turn_id": row["turn_id"], "turn_idx": row["turn_idx"],
        "frame_id": row["frame_id"],
        "kind": row["kind"],
        "category": row["category"] or _default_category(row["kind"]),
        "provenance": row["provenance"], "salience": row["salience"],
        "content": row["content"], "gist": row["gist"] or _gist(row["content"]),
        "key_phrases": _json_list(row["key_phrases"]),
        "entities": _json_list(row["entities"]),
        "location": row["location"] or "",
        "emotional_context": row["emotional_context"] or "",
        "valence": row["valence"] or 0.0, "arousal": row["arousal"] or 0.0,
        "encoding_valence": row["encoding_valence"] or 0.0,
        "encoding_arousal": row["encoding_arousal"] or 0.0,
        "confidence": row["confidence"] or 0.0,
        "access_count": row["access_count"] or 0,
        "last_accessed": row["last_accessed"],
        # How central it BECAME. Distinct from salience, which records how much
        # it mattered when formed and is never revised -- a minor moment can
        # turn out to have been the important one, and the two facts are
        # different. NULL (never revised) reads as the salience, so an
        # untouched bank behaves exactly as it did.
        "importance": (row["salience"] if row["importance"] is None
                       else row["importance"]),
        "importance_revised": row["importance"] is not None,
        # The character's own later re-reading, if they have made one.
        "disputed": _dispute_of(row["disputed"]),
        "archived": bool(row["archived"]),
        "event_key": row["event_key"] or "",
        "embedding_model": row["embedding_model"] or "",
        "embedding_dim": row["embedding_dim"],
    }

def prepare_memory(chat_id, char_id, turn_id, kind, provenance, salience, content, *,
                   turn_idx=None, category=None, gist=None, key_phrases=None,
                   entities=None, location="", emotional_context="",
                   valence=0.0, arousal=0.0, confidence=1.0, event_key="",
                   encoding_valence=0.0, encoding_arousal=0.0,
                   frame_id=_UNSET, importance=None, disputed="") -> dict:
    content = re.sub(r"\s+", " ", str(content or "")).strip()
    entities = list(dict.fromkeys(entities if entities is not None else _extract_entities(content)))
    key_phrases = list(dict.fromkeys(key_phrases if key_phrases is not None else _extract_key_phrases(content, entities)))
    # frame_id defaults to whatever era this chat is CURRENTLY being
    # portrayed at -- almost always None (the present), so ordinary chats
    # that never time-travel see zero behavior change. _UNSET (not None)
    # is the "caller didn't specify" sentinel, since None is itself the
    # valid, meaningful "present" value a caller might deliberately pass.
    resolved_frame_id = _active_frame_id.get() if frame_id is _UNSET else frame_id
    return {
        "chat_id": chat_id, "char_id": char_id, "turn_id": turn_id,
        "turn_idx": turn_idx if turn_idx is not None else _turn_idx_for(turn_id),
        "frame_id": resolved_frame_id,
        "kind": kind or "episodic",
        "category": category if category in MEMORY_CATEGORIES else _default_category(kind),
        "provenance": provenance if provenance in MEMORY_PROVENANCE else "witnessed",
        "salience": _clamp(salience), "content": content,
        "gist": (gist or _gist(content)).strip(),
        "key_phrases": key_phrases[:16], "entities": entities[:16],
        "location": str(location or "").strip(),
        "emotional_context": str(emotional_context or "").strip(),
        "valence": _clamp(valence, -1.0, 1.0), "arousal": _clamp(arousal),
        "encoding_valence": _clamp(encoding_valence, -1.0, 1.0),
        "encoding_arousal": _clamp(encoding_arousal),
        "confidence": _clamp(confidence),
        "event_key": str(event_key or "").strip(),
        # None, not 0.0: NULL is "never revised" and reads as the salience.
        # Defaulting to a number here would freeze every new memory at its
        # mint value and silently kill the fallback.
        "importance": None if importance is None else _clamp(importance),
        "disputed": _storage_json(disputed) if isinstance(disputed, dict)
                    else str(disputed or ""),
    }

def _embed_memory(data: dict):
    docs = [_memory_document(data), _memory_cues(data) or _memory_document(data)]
    embedded = embed_texts_meta(docs)
    return embedded.vectors[0], embedded.vectors[1], embedded

# ---- Finishing a write that failed ----
#
# A memory whose embedding call failed is stored anyway, stamped
# `cheap:crc32:256`, and is then reachable by keyword only until somebody
# accepts a rebuild. That is the right call at write time -- a memory is worth
# more than its vector, and the turn must not wait -- but leaving it there
# makes a provider's bad second permanent, and the cure on offer (walk the
# whole bank) is wildly out of proportion to the four rows that actually
# failed.
#
# So the engine finishes its own write instead. THIS IS NOT A REBUILD: it
# re-embeds exactly the rows whose own write fell back, by id, and touches
# nothing else -- not the historical corpus, not lore, not another chat. The
# distinction matters because the two have different justifications. Walking
# the bank is a migration a host should choose and pay for; re-doing a write
# the engine failed seconds ago is the engine finishing its job.
#
# Measured provocation (2026-08-11): the configured OpenRouter/Perplexity
# route serves a bucket of roughly 3 requests refilling at 1-2/s, and a turn
# makes several embedding calls, so a beat can exhaust its whole retry budget
# inside one depleted window -- live, chat 70 turn 6 lost all four of its
# memories that way with every retry and pacing fix already running. Waiting
# and trying again a moment later costs four requests and fixes it.
_REPAIR_LOCK = threading.Lock()
_REPAIR_PENDING: dict[str, set[int]] = {"memories": set(), "memory_summaries": set()}
_REPAIR_THREAD = None
# Long enough for a rate-limit window to refill, and far enough from the beat
# that the repair is not competing with the next turn's own embedding calls.
_REPAIR_DELAY = 30.0
# A bound, so a provider that is down for an hour cannot accumulate an
# unbounded backlog in memory. Past this the rows stay stranded and the
# ordinary rebuild offer is the honest remedy -- which is exactly the
# situation that offer was written for.
_REPAIR_MAX_PENDING = 500
# Waiting out a rate limit is the job, so the pass comes back -- backing off
# each round, and stopping eventually, because a provider that has refused for
# this long is not busy, it is gone.
_REPAIR_MAX_DELAY = 300.0
_REPAIR_MAX_ROUNDS = 12


def note_failed_embedding_write(table: str, row_ids):
    """Remember rows stored with a fallback vector, to finish later.

    No-op when the crc32 hash IS the configured embedding: there is nothing
    to finish, and scheduling a repair would mean re-hashing the same text
    forever.
    """
    if not row_ids or table not in _REPAIR_PENDING:
        return
    if embedding_model_key() == "cheap:crc32:256":
        return
    with _REPAIR_LOCK:
        pending = _REPAIR_PENDING[table]
        if sum(len(v) for v in _REPAIR_PENDING.values()) >= _REPAIR_MAX_PENDING:
            return
        pending.update(int(r) for r in row_ids)
    _ensure_repair_thread()


def _ensure_repair_thread():
    global _REPAIR_THREAD
    with _REPAIR_LOCK:
        if _REPAIR_THREAD is not None and _REPAIR_THREAD.is_alive():
            return
        _REPAIR_THREAD = threading.Thread(target=_repair_loop,
                                          name="embedding-repair", daemon=True)
        _REPAIR_THREAD.start()


def _repair_loop():
    """Keep trying until the rows are done or the rounds run out.

    ONE PASS WAS NOT ENOUGH, and the first version of this made exactly that
    mistake: a pass that found the provider still refusing returned, leaving
    the rows queued with nothing scheduled to come back for them. That is the
    opposite of what the queue is for -- a rate limit is a thing you WAIT OUT,
    and the whole point of repairing off the turn path is that waiting is
    free here. Nobody is watching this thread.

    Backs off between rounds so a long outage is not a busy-wait, and gives up
    after a bounded number of them: past that the provider is not rate
    limiting, it is gone, and the ordinary rebuild offer is the honest remedy.
    """
    delay = _REPAIR_DELAY
    for _ in range(_REPAIR_MAX_ROUNDS):
        time.sleep(delay)
        try:
            repair_pending_embeddings()
        except Exception as exc:  # noqa: BLE001 - never take a turn down
            logger.warning("memory: embedding repair pass failed: %s", exc)
            return
        with _REPAIR_LOCK:
            if not any(_REPAIR_PENDING.values()):
                return
        delay = min(delay * 2, _REPAIR_MAX_DELAY)


def repair_pending_embeddings(batch=32):
    """Re-embed the rows whose own write fell back. Returns what it fixed.

    Split from the thread so a test can run it synchronously, and so the
    decision to run one is separable from the decision to wait 30 seconds.
    """
    fixed = {"memories": 0, "memory_summaries": 0}
    with _REPAIR_LOCK:
        pending = {t: sorted(ids)[:batch] for t, ids in _REPAIR_PENDING.items()}
    if not any(pending.values()):
        return fixed
    for table, ids in pending.items():
        if not ids:
            continue
        holes = ",".join("?" * len(ids))
        # Only rows STILL on the fallback: a rebuild, a restore or a later
        # rewrite may have fixed them already, and re-embedding a good row
        # spends a request to change nothing.
        rows = q(f"SELECT * FROM {table} WHERE id IN ({holes}) "
                 "AND embedding_model='cheap:crc32:256'", tuple(ids))
        if rows:
            if table == "memories":
                mems = [_row_memory(r) for r in rows]
                docs = []
                for mem in mems:
                    docs.append(_memory_document(mem))
                    docs.append(_memory_cues(mem) or _memory_document(mem))
                got = embed_texts_meta(docs)
                if got.fallback:
                    return fixed  # still degraded; leave everything queued
                with transaction():
                    for index, mem in enumerate(mems):
                        qi("UPDATE memories SET embedding=?,cue_embedding=?,"
                           "embedding_model=?,embedding_dim=? WHERE id=?",
                           (_blob(got.vectors[index * 2]),
                            _blob(got.vectors[index * 2 + 1]),
                            got.model_key, got.dimensions, mem["id"]))
                fixed["memories"] += len(rows)
            else:
                texts = [_summary_retrieval_text(
                    r["summary"], _json_list(r["key_phrases"]),
                    _json_list(r["unresolved_threads"])) for r in rows]
                got = embed_texts_meta(texts)
                if got.fallback:
                    return fixed
                with transaction():
                    for index, row in enumerate(rows):
                        qi("UPDATE memory_summaries SET embedding=?,"
                           "embedding_model=?,embedding_dim=? WHERE id=?",
                           (_blob(got.vectors[index]), got.model_key,
                            got.dimensions, row["id"]))
                fixed["memory_summaries"] += len(rows)
        with _REPAIR_LOCK:
            _REPAIR_PENDING[table].difference_update(ids)
    if any(fixed.values()):
        logger.info("memory: finished %d memory and %d summary embedding "
                    "write(s) that had fallen back to the hash",
                    fixed["memories"], fixed["memory_summaries"])
    return fixed


def queue_fallback_rows_for_repair(chat_id=None, limit=_REPAIR_MAX_PENDING):
    """Adopt rows a PREVIOUS process wrote on the fallback.

    The in-memory queue dies with the process, so a story whose memories were
    stranded before a restart had nobody left to finish them -- it could only
    be offered the rebuild. Called when a chat is opened, this picks those
    rows back up so the repair happens quietly instead of as a question.

    Scoped to `cheap:crc32:256` deliberately, and that stamp is the whole
    discriminator: a row carrying the hash while a real provider is configured
    is a write THIS ENGINE failed, which it may finish on its own. A row
    carrying some other model's key is a host who changed embedding model, and
    re-embedding that is a migration nobody asked this code to start.
    """
    if embedding_model_key() == "cheap:crc32:256":
        return {"memories": 0, "memory_summaries": 0}
    found = {}
    for table in ("memories", "memory_summaries"):
        where, args = ["embedding_model='cheap:crc32:256'"], []
        if chat_id is not None:
            where.append("chat_id=?")
            args.append(chat_id)
        rows = q(f"SELECT id FROM {table} WHERE {' AND '.join(where)} "
                 "ORDER BY id DESC LIMIT ?", tuple(args) + (limit,)) or []
        found[table] = len(rows)
        if rows:
            note_failed_embedding_write(table, [r["id"] for r in rows])
    return found


def _upsert_memory(data: dict, full_vec, cue_vec, embedded):
    existing = None
    if data["event_key"]:
        existing = q("SELECT id FROM memories WHERE chat_id=? AND char_id=? AND event_key=?",
                     (data["chat_id"], data["char_id"], data["event_key"]), one=True)
    values = (
        data["turn_id"], data["turn_idx"], data["kind"], data["category"],
        data["provenance"], data["salience"], data["content"], data["gist"],
        json.dumps(data["key_phrases"], ensure_ascii=False),
        json.dumps(data["entities"], ensure_ascii=False),
        data["location"], data["emotional_context"], data["valence"],
        data["arousal"], data["encoding_valence"],
        data["encoding_arousal"], data["confidence"],
        _blob(full_vec), _blob(cue_vec),
        embedded.model_key, embedded.dimensions, data.get("frame_id"),
        data.get("importance"), data.get("disputed") or "",
    )
    if existing:
        mid = existing["id"]
        qi("""UPDATE memories SET turn_id=?,turn_idx=?,kind=?,category=?,provenance=?,
            salience=?,content=?,gist=?,key_phrases=?,entities=?,location=?,
            emotional_context=?,valence=?,arousal=?,encoding_valence=?,
            encoding_arousal=?,confidence=?,embedding=?,cue_embedding=?,
            embedding_model=?,embedding_dim=?,frame_id=?,
            importance=?,disputed=?,archived=0 WHERE id=?""",
           values + (mid,))
    else:
        mid = qi("""INSERT INTO memories(chat_id,char_id,turn_id,turn_idx,kind,category,
            provenance,salience,content,gist,key_phrases,entities,location,
            emotional_context,valence,arousal,encoding_valence,encoding_arousal,
            confidence,embedding,cue_embedding,
            embedding_model,embedding_dim,frame_id,importance,disputed,event_key)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
           (data["chat_id"], data["char_id"]) + values + (data["event_key"],))
    _replace_memory_fts(mid, data)
    if getattr(embedded, "fallback", False):
        note_failed_embedding_write("memories", [mid])
    return mid

def add_memory(chat_id, char_id, turn_id, kind, provenance, salience, content, *,
               turn_idx=None, category=None, gist=None, key_phrases=None,
               entities=None, location="", emotional_context="",
               valence=0.0, arousal=0.0, confidence=1.0, event_key="",
               encoding_valence=0.0, encoding_arousal=0.0,
               frame_id=_UNSET):
    data = prepare_memory(chat_id, char_id, turn_id, kind, provenance, salience, content,
                          turn_idx=turn_idx, category=category, gist=gist,
                          key_phrases=key_phrases, entities=entities, location=location,
                          emotional_context=emotional_context, valence=valence,
                          arousal=arousal, encoding_valence=encoding_valence,
                          encoding_arousal=encoding_arousal,
                          confidence=confidence, event_key=event_key,
                          frame_id=frame_id)
    full_vec, cue_vec, embedded = _embed_memory(data)
    return _upsert_memory(data, full_vec, cue_vec, embedded)

def prepare_memories_batch(memories: list[dict]) -> dict:
    """Normalize and embed a memory batch without mutating the database.

    Turn commit uses this before opening its outer write transaction so a
    remote embedding request can never hold SQLite's write lock.  The result
    is intentionally opaque to callers outside this module; pass it back to
    :func:`add_memories_batch` through ``prepared_batch``.
    """
    prepared = [prepare_memory(**item) for item in memories]
    if not prepared:
        return {"prepared": [], "embedded": None}
    texts = []
    for data in prepared:
        texts.extend([_memory_document(data), _memory_cues(data) or _memory_document(data)])
    embedded = embed_texts_meta(texts)
    return {"prepared": prepared, "embedded": embedded}


def add_memories_batch(
    memories: list[dict] | None = None,
    *,
    prepared_batch: dict | None = None,
) -> list[int]:
    if prepared_batch is None:
        prepared_batch = prepare_memories_batch(memories or [])
    prepared = prepared_batch.get("prepared") or []
    embedded = prepared_batch.get("embedded")
    if not prepared:
        return []
    if embedded is None or len(embedded.vectors) != len(prepared) * 2:
        raise ValueError("Invalid prepared memory embedding batch")
    ids = []
    with transaction():
        for i, data in enumerate(prepared):
            full_vec = embedded.vectors[i * 2]
            cue_vec = embedded.vectors[i * 2 + 1]
            ids.append(_upsert_memory(data, full_vec, cue_vec, embedded))
    return ids

def delete_turn_memories(turn_id):
    for r in q("SELECT id FROM memories WHERE turn_id=?", (turn_id,)):
        _delete_memory_fts(r["id"])
    qi("DELETE FROM memories WHERE turn_id=?", (turn_id,))

