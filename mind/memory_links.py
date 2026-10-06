"""A newer memory that changes what an older one states: superseded links.

The concept lab (`docs/experiments/CONCEPT_LAB_2026_09_30.md` §10-13): each
new turn memory is compared with the older turn memories most like it, and the
decision model asks whether the newer changes something the older one states
as true; a yes records the link. At recall, a recalled memory brings in the
memories that changed it, unlabelled -- in the lab (round D, the chain's
newest row) 9 -> 15 of 40 answers right where recall had missed them, with
the fewest outdated answers (3) of any condition. A false link costs a recall
slot, not a falsehood: 19 of 30 links held up at p >= 0.5, and a stricter
floor lost most of the real ones. What was measured here, 2026-10-05:
`docs/experiments/SUPERSEDED_LINKS_2026_10_05.md`.

THE LINK IS A VALUE ON THE NEWER ROW, NEVER AN EDGE. `memories.supersedes`
holds the OLDER rows' `event_key`s: checkpoint restore re-mints every row id,
and a key survives it (the row-not-edge rule of `memory_read.record_dispute`).
It is written by the INSERT that mints the newer row, so it rolls back with
that row's turn, a re-commit forms it again, and a mind follows it only once
the newer row is visible to it -- the firewall's own read
(`visible_memory_rows`: turn cutoff, frame, this mind's rows alone).

NOTHING A MODEL READS NAMES THE LINK. Telling minds that two memories disagree
measured worse than letting them read both (UNBUILT_CHARACTERS §2.24), and the
grader believes a label over the text (concept lab §9). A pulled row is
projected exactly as an ordinary recalled row is.
"""

from __future__ import annotations

import contextvars
from concurrent.futures import ThreadPoolExecutor

from mind.memory_common import _UNSET, _cos, _storage_json, _vec
from mind.memory_read import visible_memory_rows
from mind.memory_write import _row_memory, _supersedes_of

#: How many of this mind's older memories, most alike first, each new turn
#: memory is compared with. Measured 2026-10-05 on the lab bank with the
#: engine's own vectors: the outdated row of a labelled superseded pair is
#: among the 5 most alike for 17 of 30 pairs (the lab's TF-IDF: 13), the 10
#: most alike for 22, the 20 for 26; of the lab's 196 confirmed links, 147
#: fall in the top 5 and 179 in the top 10 (`docs/experiments/
#: SUPERSEDED_LINKS_2026_10_05.md` § 2, `tools/concept_lab/links_candidates.py`).
#: Named to the owner.
LINK_CANDIDATES = 10

#: The answer that records a link: p(yes) at or above it. The lab's floor:
#: 0.6 kept 14 of 21 valid, 0.8 6 of 7, each losing most real links.
LINK_THRESHOLD = 0.5

#: How much of each memory a link question quotes, in characters. The lab's
#: rows averaged 888 characters and were quoted whole; a turn memory here can
#: run to thousands. Named to the owner.
LINK_QUOTE_CHARS = 1500

#: How far one recalled memory's links are followed to the newest row they reach
#: (the lab's `_chain_latest`).
CHAIN_HOPS = 6

#: How many successors one beat may bring in beside the recalled rows (the
#: lab brought 0-6 a scene, uncapped). Named to the owner.
PULL_CAP = 6

#: Minds asked side by side at commit: one request each.
_PARALLEL = 8


def _linkable(kind, category):
    """A turn memory -- the episode, or a beat's own acts where the mind
    perceived nothing else -- and a self record: the rows the lab compared,
    one per turn, what was lived and what was done. Inferences are revised
    by belief reconciliation, promises by their own ledger."""
    return str(kind or "") == "episodic" and str(category or "") in ("episode", "self")


def _quote(text):
    return " ".join(str(text or "").split())[:LINK_QUOTE_CHARS]


def form_memory_links(chat_id, memory_batch, *, turn_idx, names, language=None,
                      record=None, viewer_frame_id=_UNSET):
    """Write `supersedes` onto this beat's new turn memories, in place, from
    one decision-model request per mind, the minds asked side by side.

    `memory_batch` is `prepare_memories_batch`'s result: the prepared rows and
    their vectors, two per row (content, then cue). `names` maps a char id to
    the mind's name, for the state the lab asked under. Fail-open: no
    comparable vectors, no decision model, a refused request -- no links,
    never a failed commit; `record` says which, and is returned."""
    record = record if record is not None else {}
    prepared = memory_batch.get("prepared") or []
    embedded = memory_batch.get("embedded")
    newer = {}
    for i, data in enumerate(prepared):
        if (_linkable(data.get("kind"), data.get("category"))
                and str(data.get("event_key") or "").strip()
                and str(data.get("content") or "").strip()):
            newer.setdefault(data["char_id"], []).append(i)
    if not newer:
        return record
    if (embedded is None or getattr(embedded, "fallback", False)
            or len(embedded.vectors) != 2 * len(prepared)):
        record["unasked"] = "no comparable vectors"
        return record
    from llm import decisions
    if not decisions.configured():
        record["unasked"] = "no decision model is configured"
        return record
    from llm.prompts import character_jev_options, character_jev_text
    text = character_jev_text("memory_supersedes", language)
    options = character_jev_options("yesno", language)
    asks = {}
    for char_id, idxs in newer.items():
        # The firewall's own read, at the beat being committed: this mind's
        # rows, in its frame, from before this turn -- so a re-commit never
        # compares a turn with its own earlier minting.
        older = []
        for row in visible_memory_rows(chat_id, char_id, before_turn_idx=turn_idx,
                                       viewer_frame_id=viewer_frame_id,
                                       include_archived=True):
            if (not _linkable(row["kind"], row["category"])
                    or not str(row["event_key"] or "").strip()
                    or row["embedding_model"] != embedded.model_key
                    or row["embedding_dim"] != embedded.dimensions):
                continue
            vec = _vec(row["embedding"])
            if vec is not None:
                older.append((row, vec))
        questions, keys = {}, {}
        for i in idxs:
            new_vec = embedded.vectors[2 * i]
            alike = sorted(older, key=lambda rv: -_cos(new_vec, rv[1]))[:LINK_CANDIDATES]
            newer_text = _quote(prepared[i].get("content"))
            for m, (row, _vec_) in enumerate(alike):
                qid = f"supersedes:{i}:{m}"
                questions[qid] = {
                    "type": "choice", "criteria": dict(options),
                    "instructions": text.replace("{older}", _quote(row["content"]))
                                        .replace("{newer}", newer_text)}
                keys[qid] = (i, str(row["event_key"]))
        if questions:
            asks[char_id] = (questions, keys)
    record["asked"] = sum(len(qs) for qs, _keys in asks.values())
    if not asks:
        return record
    from mind import character_jev as jev
    from mind.affect_appraisal import _probabilities

    def _ask(char_id, questions):
        return jev.ask("YOU ARE %s." % (str(names.get(char_id) or "").strip() or "yourself"),
                       questions)

    with ThreadPoolExecutor(max_workers=min(len(asks), _PARALLEL)) as pool:
        # Each in a copy of this thread's context: the call ledger is a
        # ContextVar a worker does not inherit (`decisions.decide`).
        futures = {cid: pool.submit(contextvars.copy_context().run, _ask, cid, qs)
                   for cid, (qs, _keys) in asks.items()}
        answered = {}
        for cid, future in futures.items():
            try:
                answered[cid] = future.result()
            except Exception as exc:  # the floor: a commit is never lost to a link
                record.setdefault("failed", {})[str(cid)] = \
                    f"{type(exc).__name__}: {str(exc)[:160]}"
    linked = 0
    for cid, answers in answered.items():
        if not isinstance(answers, dict):
            record.setdefault("failed", {})[str(cid)] = "the answers were not a mapping"
            continue
        for qid, (i, older_key) in asks[cid][1].items():
            # An answer off its shape is a "no", never an exception: reading
            # one raised out of the commit and lost the beat (review round 5).
            answer = answers.get(qid)
            try:
                p_yes = _probabilities(answer).get("yes", 0.0) if isinstance(answer, dict) else 0.0
            except Exception:
                p_yes = 0.0
            if p_yes < LINK_THRESHOLD:
                continue
            links = _supersedes_of(prepared[i].get("supersedes"))
            if older_key not in links:
                links.append(older_key)
                linked += 1
            prepared[i]["supersedes"] = _storage_json(links)
    record["linked"] = linked
    return record


def _order(row):
    """Oldest first: by turn, then by the fiction clock, then by mint -- a
    stored row or `_row_memory`'s dict alike. Seeded rows tie at one turn."""
    turn = row["turn_idx"]
    return (turn if turn is not None else -10 ** 9,
            row["encoded_at_seconds"] or 0.0, row["id"] or 0)


#: How far a pulled successor outranks the row it changes. The unbidden swap
#: (`agents/character._attach_unbidden`) gives up the lowest score first, and
#: a tie fell to whichever came first -- a turnless predecessor sorts last, so
#: its correction went first (review round 5, 2026-10-05). A hair above, and
#: the outdated row is always the one given up.
_SUCCESSOR_EDGE = 1e-6


def successors_of(mem, newer_of):
    """What changed `mem`, by the links on this mind's rows (`newer_of`:
    older event_key -> the newer rows naming it): every row whose
    `supersedes` names it, newest first -- the rows that changed THAT memory
    -- then the newest row its links reach at all, on any branch, if it is not
    one of those. Only rows newer than `mem`; cycle-safe.

    The direct rows first, because a link says a newer memory changes
    something the older one states, never WHICH thing: following a chain to
    its end handed a mind the fare from turn 3 and Anna's walk to the inn from
    turn 8, and the turn-7 row that changed the fare went by no lane at all
    (review round 5, 2026-10-05: on the lab's own graph the direct successors
    held an answer for 12 of 23 outdated rows, the chain's end for 10)."""
    key = str(mem.get("event_key") or "")
    start = _order(mem)
    direct = sorted((r for r in newer_of.get(key, ()) if _order(r) > start),
                    key=_order, reverse=True)
    seen, frontier, reach = {key}, [key], []
    for _hop in range(CHAIN_HOPS):
        nxt = []
        for k in frontier:
            for r in newer_of.get(k, ()):
                rk = str(r["event_key"] or "")
                if rk and rk not in seen and _order(r) > start:
                    seen.add(rk)
                    nxt.append(rk)
                    reach.append(r)
        if not nxt:
            break
        frontier = nxt
    out = list(direct)
    if reach:
        end = max(reach, key=_order)
        if all(str(end["event_key"]) != str(r["event_key"]) for r in out):
            out.append(end)
    return out


def pull_successors(chat_id, char_id, recalled, *, current_turn_idx, delivered=(),
                    bank=None, record=None, cap=PULL_CAP, viewer_frame_id=_UNSET):
    """`recalled` (best first) with the memories that changed each recalled
    row (`successors_of`) set in after it, where the payload does not carry
    them already: unlabelled, and scored a hair above the row they change
    (`_SUCCESSOR_EDGE`), so an unbidden swap gives up the outdated row, never
    its correction. The payload then reads in time order like every recalled
    row.

    Among THIS mind's visible rows only -- the read recall made
    (`visible_memory_rows`; a memo hit on `bank`). `delivered` are the rows
    the payload carries already (the recent turns); a successor already
    there is not brought twice, and does not stop the others. Past `cap` a
    successor is left out and counted in `record`, never dropped unsaid."""
    record = record if record is not None else {}
    rows = visible_memory_rows(chat_id, char_id, before_turn_idx=current_turn_idx,
                               viewer_frame_id=viewer_frame_id, include_archived=True,
                               bank=bank)
    newer_of = {}
    for row in rows:
        for older in _supersedes_of(row["supersedes"]):
            newer_of.setdefault(older, []).append(row)
    if not newer_of:
        return recalled
    have = {str(m.get("event_key") or "") for m in (*recalled, *delivered)}
    out, pulled, capped = [], 0, 0
    for mem in recalled:
        out.append(mem)
        key = str(mem.get("event_key") or "")
        if not key or key not in newer_of:
            continue
        for successor in successors_of(mem, newer_of):
            skey = str(successor["event_key"] or "")
            if not skey or skey in have:
                continue
            if pulled >= cap:
                capped += 1
                continue
            pulled_mem = _row_memory(successor)
            pulled_mem["score"] = float(mem.get("score") or 0.0) + _SUCCESSOR_EDGE
            pulled_mem["picked_by"] = "link"
            out.append(pulled_mem)
            have.add(skey)
            pulled += 1
    if pulled or capped:
        record.update(links_pulled=pulled, links_capped=capped)
    return out
