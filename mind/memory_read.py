"""The one seam a mind reads its own memory through, and the host reads that
deliberately do not.

`visible_memory_rows` is the firewall boundary for recall; everything under
`HOST_SCOPE_READERS` crosses character lines on purpose and says so."""

import json
from core.db import q, qi
from core import frames as _frames
from core.db import active_frame_id as _active_frame_id

from mind.memory_common import (
    MEMORY_CATEGORIES, MEMORY_PROVENANCE, _UNSET, _blob, _storage_json,
)
from mind.memory_write import (
    _IMPORTANCE_CEILING, _IMPORTANCE_DISPUTE_STEP, _IMPORTANCE_STEP,
    _MAX_DISPUTE_READING, _delete_memory_fts, _dispute_of, _embed_memory,
    _replace_memory_fts, _row_memory, effective_importance, prepare_memory,
)

# ---- The one seam a mind reads its own memory through -------------------
#
# Two filters decide what a character may legitimately retrieve, and both must
# run BEFORE any ranking:
#
#   the turn cutoff   -- a mind deciding turn N must never read a memory of how
#                        turn N turned out (audit F1). Not hypothetical: a
#                        reroll or rerun-from-stage replays the onset of a turn
#                        whose outcome memories are already committed.
#   frame visibility  -- a memory formed in another era is not this mind's to
#                        have yet (frames.is_memory_visible).
#
# They used to be written out again at every read path -- search_memories,
# contrast_memory, recent_memory_buffer, list_memories,
# consolidate_character_memory -- and docs/guides/MEMORY.md claimed that repetition
# was what stopped a new path forgetting them. That reasoning is backwards:
# repetition is precisely how a sixth path forgets, because nothing makes it
# reproduce five filters it may not know exist.
#
# So the rules live here, once, and every argument that carries one is
# REQUIRED and has no default. A caller cannot omit `before_turn_idx` or
# `viewer_frame_id`; it can only state them, including stating None. Forgetting
# becomes a TypeError instead of a leak.
#
# The remaining parameters only ever NARROW the result. None of them can
# readmit a row the two filters excluded, which is what keeps this a seam
# rather than a configurable query builder.


def visible_memory_rows(chat_id, char_id, *, before_turn_idx, viewer_frame_id,
                        include_archived, since_turn_idx=None,
                        require_turn_idx=False):
    """Raw rows this character may legitimately read. The only way to get them.

    `before_turn_idx` is the turn being decided, and the cutoff is strict:
    turn N itself and every later play-order turn go. Pass None only where
    there is no turn being decided -- a host browsing the memory panel, not a
    mind deciding a beat. `turn_idx IS NULL` rows (imported or authored, with
    no place in play order) are always kept: they belong to no turn, so they
    cannot be this turn's leaked outcome.

    `viewer_frame_id` may be `_UNSET` to read the ambient contextvar, which is
    what almost every caller wants; it is still passed explicitly so the
    decision is visible at the call site. A caller on a worker thread must
    pass the real value -- contextvars do not propagate into
    ThreadPoolExecutor workers (see maybe_consolidate_character_memory).
    """
    clauses = ["chat_id=?", "char_id=?"]
    args = [chat_id, char_id]
    if not include_archived:
        clauses.append("archived=0")
    if require_turn_idx:
        clauses.append("turn_idx IS NOT NULL")
    if since_turn_idx is not None:
        clauses.append("turn_idx>=?")
        args.append(since_turn_idx)
    if before_turn_idx is not None:
        # Stated once, in SQL. An earlier draft also re-filtered in Python
        # "so the rule is an invariant, not an optimisation" -- but two copies
        # of one rule is the thing this seam exists to stop, and mutation
        # testing proved the point: deleting the Python half left all 21 seam
        # tests green, because the SQL half was already doing the work. A
        # guard nothing can observe failing is not a guard.
        #
        # NULL turn_idx is kept explicitly. Those rows are imported or
        # authored, belong to no turn, and so cannot be this turn's leaked
        # outcome -- and SQL's three-valued logic would silently drop them
        # from a bare `turn_idx < ?`.
        clauses.append("(turn_idx IS NULL OR turn_idx<?)")
        args.append(before_turn_idx)
    rows = q("SELECT * FROM memories WHERE " + " AND ".join(clauses), tuple(args))
    vf = _active_frame_id.get() if viewer_frame_id is _UNSET else viewer_frame_id
    return [r for r in rows
            if _frames.is_memory_visible(char_id, r["frame_id"], vf, r["turn_idx"])]


# ---- Host-facing reads, which deliberately cross character boundaries ----
#
# These answer a question ABOUT the cast rather than a question a character
# asks itself, so they are not scoped to one char_id and must never feed a
# character's context. They are named here so the crossing is a listed
# exception rather than an oversight, and
# tests/test_memory_read_seam.py::test_no_unlisted_cross_character_reader
# fails if the list grows without a decision.
HOST_SCOPE_READERS = ("dramatic_irony_feed", "promise_ledger")


def dramatic_irony_feed(chat_id, limit=100):
    """Every character's memories that did NOT come from directly
    witnessing the thing themselves (heard/told/inferred/read) -- a
    transparency window into what each character currently believes on
    secondhand or inferred grounds, for a reader to judge for themselves
    whether it's actually wrong. Deliberately does not claim to know
    a belief IS false (that would need comparing it against objective
    world state with its own LLM call); it surfaces exactly the
    provenance distinction the engine already tracks per memory and
    leaves the judgment to whoever's reading it -- the same distinction
    that already gates what a character legitimately knows.
    """
    rows = q(
        """SELECT m.*, ch.name AS char_name FROM memories m
        JOIN characters ch ON ch.id = m.char_id
        WHERE m.chat_id=? AND m.archived=0 AND m.provenance != 'witnessed'
        ORDER BY CASE WHEN m.turn_idx IS NULL THEN 1 ELSE 0 END, m.turn_idx DESC, m.id DESC
        LIMIT ?""",
        (chat_id, max(1, min(int(limit), 500))),
    )
    out = []
    for r in rows:
        entry = _row_memory(r)
        entry["char_name"] = r["char_name"]
        out.append(entry)
    return out

def promise_ledger(chat_id, limit=200):
    """Every promise-category memory across the whole chat (any
    character, not one at a time like list_memories), in chronological
    order -- a running ledger of what's been promised, to whom, without
    claiming to auto-detect kept/broken status (that's a real judgment
    call left to whoever reads it, not something to fabricate from a
    keyword match).
    """
    rows = q(
        """SELECT m.*, ch.name AS char_name FROM memories m
        JOIN characters ch ON ch.id = m.char_id
        WHERE m.chat_id=? AND m.category='promise' AND m.archived=0
        ORDER BY CASE WHEN m.turn_idx IS NULL THEN 1 ELSE 0 END, m.turn_idx ASC, m.id ASC
        LIMIT ?""",
        (chat_id, max(1, min(int(limit), 500))),
    )
    out = []
    for r in rows:
        entry = _row_memory(r)
        entry["char_name"] = r["char_name"]
        out.append(entry)
    return out

def list_memories(chat_id, char_id, *, include_archived=False, category=None,
                  provenance=None, limit=500, offset=0, viewer_frame_id=_UNSET):
    """The host's memory panel for one character. No turn cutoff, deliberately:
    nobody is deciding a beat here, so there is no future to withhold.

    Paging now happens AFTER frame filtering. It used to be `LIMIT ? OFFSET ?`
    in SQL with the visibility pass applied to whatever came back, so a page
    could return fewer rows than asked for -- or none -- while plenty of
    visible memories sat behind it, and the panel had no way to tell "the end"
    from "this page happened to be another era's".
    """
    rows = visible_memory_rows(
        chat_id, char_id,
        before_turn_idx=None,
        viewer_frame_id=viewer_frame_id,
        include_archived=include_archived,
    )
    if category in MEMORY_CATEGORIES:
        rows = [r for r in rows if r["category"] == category]
    if provenance in MEMORY_PROVENANCE:
        rows = [r for r in rows if r["provenance"] == provenance]
    rows.sort(key=lambda r: (r["turn_idx"] is None,
                            -(r["turn_idx"] if r["turn_idx"] is not None else 0),
                            -r["id"]))
    start = max(0, int(offset))
    stop = start + max(1, min(int(limit), 1000))
    return [_row_memory(r) for r in rows[start:stop]]

def update_memory(mid, content=None, salience=None, kind=None, provenance=None, *,
                  category=None, gist=None, key_phrases=None, entities=None,
                  location=None, emotional_context=None, valence=None,
                  arousal=None, encoding_valence=None,
                  encoding_arousal=None, confidence=None, archived=None):
    row = q("SELECT * FROM memories WHERE id=?", (mid,), one=True)
    if not row:
        return False
    current = _row_memory(row)
    data = prepare_memory(
        current["chat_id"], current["char_id"], current["turn_id"],
        kind if kind is not None else current["kind"],
        provenance if provenance is not None else current["provenance"],
        salience if salience is not None else current["salience"],
        content if content is not None else current["content"],
        turn_idx=current["turn_idx"],
        category=category if category is not None else current["category"],
        gist=gist if gist is not None else current["gist"],
        key_phrases=key_phrases if key_phrases is not None else current["key_phrases"],
        entities=entities if entities is not None else current["entities"],
        location=location if location is not None else current["location"],
        emotional_context=emotional_context if emotional_context is not None else current["emotional_context"],
        valence=valence if valence is not None else current["valence"],
        arousal=arousal if arousal is not None else current["arousal"],
        encoding_valence=(encoding_valence if encoding_valence is not None
                          else current["encoding_valence"]),
        encoding_arousal=(encoding_arousal if encoding_arousal is not None
                          else current["encoding_arousal"]),
        confidence=confidence if confidence is not None else current["confidence"],
        event_key=current["event_key"],
        frame_id=current["frame_id"],
    )
    full_vec, cue_vec, embedded = _embed_memory(data)
    qi("""UPDATE memories SET kind=?,category=?,provenance=?,salience=?,content=?,gist=?,
        key_phrases=?,entities=?,location=?,emotional_context=?,valence=?,arousal=?,
        encoding_valence=?,encoding_arousal=?,confidence=?,embedding=?,
        cue_embedding=?,embedding_model=?,embedding_dim=?,archived=?
        WHERE id=?""",
       (data["kind"], data["category"], data["provenance"], data["salience"],
        data["content"], data["gist"],
        json.dumps(data["key_phrases"], ensure_ascii=False),
        json.dumps(data["entities"], ensure_ascii=False),
        data["location"], data["emotional_context"], data["valence"],
        data["arousal"], data["encoding_valence"],
        data["encoding_arousal"], data["confidence"],
        _blob(full_vec), _blob(cue_vec),
        embedded.model_key, embedded.dimensions,
        int(bool(archived)) if archived is not None else int(current["archived"]),
        mid))
    _replace_memory_fts(mid, data)
    return True

def record_dispute(chat_id, char_id, gist, reading, turn_idx, *,
                   memory_ref=""):
    """The character has re-read one of their own memories.

    The event stays exactly as it was -- "I saw this" is still true, and the
    row's `content`, `gist`, `provenance` and `salience` are untouched. What is
    recorded beside it is that the character no longer reads it the way they
    first did, which is what deception, disguise, staging and plain
    misidentification actually do to a mind: they do not delete the
    experience, they change what it meant.

    Deliberately NOT an edge to the memory that superseded it. Checkpoint
    restore is delete-and-reinsert, so every row id changes and an id-keyed
    edge would be shredded by the first rollback; stored on the row it rides
    the existing round-trip verbatim.

    A delivered stable ``memory_ref`` is the primary locator. Legacy callers
    may still supply a gist, resolved exactly-then-loosely inside this mind's
    own bank. Returns the ids updated.
    """
    needle = " ".join(str(gist or "").split()).casefold()
    reading = " ".join(str(reading or "").split())[:_MAX_DISPUTE_READING]
    memory_ref = str(memory_ref or "").strip()
    if not (needle or memory_ref) or not reading:
        return []
    rows = q("SELECT id, event_key, gist, content, disputed, salience, importance "
             "FROM memories WHERE chat_id=? AND char_id=?", (chat_id, char_id))
    hits = ([r for r in rows if str(r["event_key"] or "") == memory_ref]
            if memory_ref else [])
    if not hits and needle:
        hits = [r for r in rows
                if " ".join((r["gist"] or "").split()).casefold() == needle]
    if not hits and needle:
        hits = [r for r in rows
                if needle in " ".join((r["gist"] or "").split()).casefold()
                or needle in " ".join((r["content"] or "").split()).casefold()]
    updated = []
    for row in hits:
        prior = _dispute_of(row["disputed"]) or {}
        blob = _storage_json({
            "turn_idx": turn_idx,
            "reading": reading,
            # A memory re-read twice has been genuinely unstable, and that is
            # worth being able to see.
            "count": int(prior.get("count") or 0) + 1,
        })
        # Being wrong about something is a larger fact about it than being
        # cited once, so a dispute moves importance further than an ordinary
        # consequence -- and it moves UP: a memory whose meaning changed is
        # more central to this mind, not less.
        base = effective_importance(row)
        raised = min(_IMPORTANCE_CEILING, base + _IMPORTANCE_DISPUTE_STEP)
        qi("UPDATE memories SET disputed=?, importance=? WHERE id=?",
           (blob, raised, row["id"]))
        updated.append(row["id"])
    return updated


def raise_importance(chat_id, char_id, memory_ids=(), *, event_keys=(),
                     only_unrevised=False, step=_IMPORTANCE_STEP):
    """Nudge memories toward the ceiling because something happened that they
    turned out to matter for.

    Asymptotic rather than additive so repetition cannot run away: each
    consequence closes a fraction of the remaining distance. Never lowers, and
    never touches `salience` -- how much it mattered when it was FORMED is a
    different fact, and the one consolidation and archiving still read.

    `chat_id`/`char_id` are required and are applied in the WHERE clause, so a
    model that cites a memory id belonging to another mind moves nothing. The
    ids arrive from model output; ownership is not negotiable, and the same
    lesson as the read seam applies -- the scoping belongs in the query, not
    in whoever remembers to check first.

    `only_unrevised` bumps a row exactly once ever, which is how a signal that
    is itself downstream of retrieval is stopped from compounding.
    """
    ids = [int(i) for i in (memory_ids or []) if i is not None]
    keys = [str(k) for k in (event_keys or []) if str(k or "").strip()]
    if not ids and not keys:
        return 0
    # Either handle resolves the same rows. `event_key` is what a character
    # actually cites (see commit._cited_memory_ids); the row id is what
    # internal callers have.
    where, args = [], [chat_id, char_id]
    if ids:
        where.append("id IN (%s)" % ",".join("?" for _ in ids)); args += ids
    if keys:
        where.append("event_key IN (%s)" % ",".join("?" for _ in keys)); args += keys
    clause = "chat_id=? AND char_id=? AND (%s)" % " OR ".join(where)
    args = tuple(args)
    if only_unrevised:
        clause += " AND importance IS NULL"
    rows = q(f"SELECT id, salience, importance FROM memories WHERE {clause}", args)
    changed = 0
    for row in rows:
        base = effective_importance(row)
        raised = min(_IMPORTANCE_CEILING, base + step * (1.0 - base))
        if raised - base > 1e-6:
            qi("UPDATE memories SET importance=? WHERE id=?", (raised, row["id"]))
            changed += 1
    return changed


def delete_memory(mid):
    _delete_memory_fts(mid)
    qi("DELETE FROM memories WHERE id=?", (mid,))

