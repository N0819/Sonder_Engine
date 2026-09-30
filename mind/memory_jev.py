"""THE DECISION MODEL PICKS WHAT A MIND REMEMBERS.

Landed 2026-09-27 on the owner's word ("land the jev memory picker ... we are
fully committed to decision models on this branch"). Recall used to fuse
four rankings of the beat's words and keep the top 24 by the fused score
(`search_memories`). This asks the decision model (Jev, `llm/decisions.py`)
which rows bear on the MOMENT, for this mind, in its own state.

Measured before landing (`docs/experiments/JEV_MEMORY_PROBE_2026_09_26.md`,
21 beats of one long story, blind-graded 0-3 by GLM 5.2 and by seven Claude
graders): today's packet 1.14 / 1.16, this one 1.84 / 1.74; rows graded 2+
out of 24 went from 6.4 to 15.5, rows graded 0 from 5.3 to 0.9, and the two
packets shared 4.4 rows.

The shape is the one that was graded:

1. THE NET. Every row this mind may see (`visible_memory_rows`, the recent
   buffer excluded), ranked by reciprocal-rank fusion at EQUAL weights over
   the lanes the engine can compute: the beat's content and cue vectors and
   keywords, recency, importance, the three aspects (what you are trying to
   do, how you feel, what is unsettled), the rows this mind reached on its
   latest recall and their nearest neighbours, the rows made where it
   stands, and encoded feeling nearest to and farthest from how it feels
   now. Equal weights rather than the weights fitted to that one story:
   replayed on its labels, Jev's pick from this net is 0.992 of its pick
   from the whole bank, against 0.994 for the fitted weights and 0.983 for
   today's fused order -- the decision model does the choosing, and the net
   only has to hold the good rows. The research's lane the engine lacks, a
   stored feeling for each remembered moment, is a schema change and the
   owner's to make.
2. THE GRADE. Each row of the net asked two questions as a four-step choice
   read as its expected grade -- does it bear on the situation you are in
   right now, does it hold information that would help with what you are
   trying to do -- against one state: who you are, what you perceive, how
   you feel, what you are trying to do, what is unsettled, what drives you
   and what you value.
3. THE PACKET. Rows by the larger of the two grades, a row within cosine
   0.90 of one already kept dropped (one belief reworded), `limit` of them.

Fails toward the net: with the decision model unconfigured or unanswering,
and on every call that names no mind (the author's preview), the packet is
the net's own order -- a floor of this design, never the retrieval it
replaced.
"""

from __future__ import annotations

import time

from mind.memory_common import _UNSET, _cos, _vec
from mind.memory_read import visible_memory_rows
from mind.memory_retrieval import _lexical_memory_ranking, _rank_normalized_importance
from mind.memory_write import _row_memory

#: The net's size and its fusion constant, as graded (named per the owner's
#: ask-before-limiting rule): 100 rows, 2 questions each, about 200 decisions
#: a beat -- four concurrent requests, well under a second, $0.0016.
NET_SIZE = 100
NET_K = 30
#: At or above this cosine a pair is one belief reworded (the probe's reading;
#: 0.85-0.90 is one place at another moment, and both are kept).
NEAR_DUPLICATE = 0.90
#: How much of the view and of each memory a question carries (the probe's).
VIEW_CHARS = 3000
MEMORY_CHARS = 500
#: The two graded questions, by pack name (`character_jev.<name>`); a row's
#: grade is the larger.
QUESTIONS = ("memory_situation", "memory_useful")
#: A PONDER IS ANSWERED THE SAME WAY (the owner, 2026-09-29: "Ponder pulls up
#: 50 candidates using rrf for jev to sort on how well it answers the ponder"
#: -- the ponder lane had been `search_memories(query)` alone, which handed a
#: mind about one of the five answers the decision model would pick at k=8
#: and two at k=24; a net of 50 holds 54-60% of those five,
#: `docs/experiments/JEV_MEMORY_PROBE_2026_09_26.md`). The net is cut at
#: PONDER_NET, each candidate graded on how directly it answers the
#: question, and the best PONDER_LIMIT kept -- "the 5 memories a ponder brings
#: up", which the affect pass also looks back on (`affect_pass.PONDER_LOOKS`).
PONDER_NET = 50
PONDER_LIMIT = 5
PONDER_QUESTIONS = ("memory_ponder",)
#: A graded ponder keeps only rows that ANSWER: at or above this grade, up to
#: PONDER_LIMIT; none of them, and nothing came back. Measured 2026-09-29 on
#: the local Winnow-12B drop-in, 30 questions over two banks of the test copy
#: (chat 64's Doctor, 657 rows; chat 76's, 230), 23 whose answer rows were
#: found by reading the bank and 7 it cannot answer: asked "How directly does
#: this memory answer...", the answer was among the five on 87%, and at 0.6 an
#: answer row stayed on 17 of 23 while none of the 7 unanswerable questions
#: kept anything. The first wording, "How much does this memory help
#: answer...", found 78% and let 3 of the 7 through at every floor from 0.4 to
#: 0.7 -- a description of amber eyes read 0.87 for "what is her favourite
#: colour?". Old `search_memories` had the answer in its top five on 57%.
PONDER_FLOOR = 0.6


def _ranked(scores):
    """Ids by score, highest first; a score of 0 or less ranks nothing."""
    return [mid for mid, s in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0])) if s > 0]


def _newest_first(memories):
    def key(mid):
        turn = memories[mid].get("turn_idx")
        return (turn is None, -(turn if turn is not None else 0), -mid)
    return key


def memory_net(chat_id, char_id, query_text, *, current_turn_idx, embedded, aspects=(),
               here=None, exclude_ids=(), feeling_valence=None, bank=None,
               viewer_frame_id=_UNSET, size=NET_SIZE):
    """`(memories, net, lanes, vectors)`: every row this mind may see except
    `exclude_ids`, as memory dicts by id; the first `size` ids (`NET_SIZE`;
    a ponder's `PONDER_NET`) by equal-weight RRF; the rankings that went into
    it by lane; and each row's (content, cue) vectors where they are
    comparable with `embedded`.

    `aspects` is `[(label, text)]` for exactly the texts `embedded` carries
    after the query, in order -- the batch `build_character_memory_context`
    embeds once for everything it ranks."""
    rows = visible_memory_rows(chat_id, char_id, before_turn_idx=current_turn_idx,
                               viewer_frame_id=viewer_frame_id, include_archived=True,
                               bank=bank)
    exclude = {int(x) for x in exclude_ids or () if x is not None}
    memories, vectors, touched = {}, {}, {}
    rank_by_vector = embedded is not None and not getattr(embedded, "fallback", False)
    for row in rows:
        if row["id"] in exclude:
            continue
        mem = _row_memory(row)
        memories[mem["id"]] = mem
        keys = row.keys() if hasattr(row, "keys") else ()
        touched[mem["id"]] = row["last_accessed_turn"] if "last_accessed_turn" in keys else None
        if (embedded is not None and row["embedding_model"] == embedded.model_key
                and row["embedding_dim"] == embedded.dimensions):
            vectors[mem["id"]] = (_vec(row["embedding"]), _vec(row["cue_embedding"]))
    if not memories:
        return {}, [], {}, {}
    newest = _newest_first(memories)
    lanes = {}
    if rank_by_vector:
        qv = embedded.vectors[0]
        lanes["semantic"] = _ranked({mid: _cos(qv, fv) for mid, (fv, _cv) in vectors.items()
                                     if fv is not None})
        lanes["cue"] = _ranked({mid: _cos(qv, cv) for mid, (_fv, cv) in vectors.items()
                                if cv is not None})
        for (label, _text), av in zip(aspects or (), embedded.vectors[1:]):
            lanes["aspect:" + str(label)] = _ranked({
                mid: max(_cos(av, fv) if fv is not None else 0.0,
                         _cos(av, cv) if cv is not None else 0.0)
                for mid, (fv, cv) in vectors.items()})
    lanes["keyword"] = [mid for mid in _lexical_memory_ranking(
        chat_id, char_id, query_text, limit=max(60, len(memories))) if mid in memories]
    lanes["recency"] = sorted(memories, key=newest)
    lanes["importance"] = _ranked(_rank_normalized_importance(memories))
    # PRIMED: what this mind reached on its latest recall before now, and
    # what lies nearest it. A train of thought carries from beat to beat; the
    # probe's fit weighted the neighbours of the previous picks highest of
    # every lane. `last_accessed_turn` is the turn a recall last reached a
    # row, so the previous packet is read off the bank, not kept beside it.
    reached = [t for t in touched.values()
               if t is not None and (current_turn_idx is None or t < current_turn_idx)]
    if reached:
        latest = max(reached)
        primed = sorted((mid for mid, t in touched.items() if t == latest), key=newest)
        lanes["primed"] = primed
        seeds = [vectors[mid][0] for mid in primed
                 if mid in vectors and vectors[mid][0] is not None]
        if seeds:
            lanes["primed_nb"] = _ranked({
                mid: max(_cos(fv, seed) for seed in seeds)
                for mid, (fv, _cv) in vectors.items() if fv is not None})
    spot = str(here or "").strip().casefold()
    if spot:
        lanes["here"] = sorted((mid for mid, m in memories.items()
                                if str(m.get("location") or "").strip().casefold() == spot),
                               key=newest)
    if feeling_valence is not None:
        try:
            now = float(feeling_valence)
        except (TypeError, ValueError):
            now = None
        if now is not None:
            gap = {mid: abs(float(m.get("encoding_valence") or 0.0) - now)
                   for mid, m in memories.items()}
            lanes["valence_match"] = sorted(gap, key=lambda mid: (gap[mid], mid))
            lanes["valence_contrast"] = sorted(gap, key=lambda mid: (-gap[mid], mid))
    fused = {}
    for ranking in lanes.values():
        for rank, mid in enumerate(ranking, 1):
            fused[mid] = fused.get(mid, 0.0) + 1.0 / (NET_K + rank)
    net = sorted(fused, key=lambda mid: (-fused[mid], mid))[:max(0, int(size))]
    for mid in net:
        memories[mid]["net_score"] = round(fused[mid], 6)
    return memories, net, lanes, vectors


def memory_line(mem, current_turn_idx):
    """One remembered row as a question carries it."""
    body = " ".join(str(mem.get("content") or mem.get("gist") or "").split())[:MEMORY_CHARS]
    when = mem.get("turn_idx")
    ago = (f"{current_turn_idx - when} beats ago"
           if isinstance(when, int) and isinstance(current_turn_idx, int) else "some time ago")
    return f"MEMORY ({ago}): {body}"


def memory_state(person, view, active_state, unsettled):
    """The one state every row is graded against: who this mind is, what it
    perceives, how it feels, what it is trying to do, what is unsettled for
    it, what drives it and what it values -- the probe's state, field for
    field."""
    person = person or {}
    active_state = active_state or {}
    values = person.get("values")
    values = "; ".join(str(v) for v in values if str(v).strip()) \
        if isinstance(values, (list, tuple)) else str(values or "")
    unsettled = " ".join(str(u) for u in unsettled or () if str(u).strip())
    return "\n\n".join(part for part in (
        f"YOU ARE {person.get('name') or 'yourself'}.",
        "WHAT YOU PERCEIVE RIGHT NOW:\n" + str(view or "")[:VIEW_CHARS],
        "HOW YOU FEEL RIGHT NOW: " + (str(active_state.get("mood") or "").strip() or "unremarkable"),
        "WHAT YOU ARE TRYING TO DO: " + (str(active_state.get("goal") or "").strip()
                                         or "nothing in particular"),
        ("WHAT IS STILL UNSETTLED FOR YOU: " + unsettled) if unsettled else "",
        ("WHAT DRIVES YOU: " + str(person.get("drive"))) if str(person.get("drive") or "").strip() else "",
        ("WHAT YOU VALUE: " + values) if values else "",
    ) if part)


def grade_net(net, memories, state, current_turn_idx, language=None, questions=QUESTIONS):
    """`{id: grade or None}`: the larger of the graded `questions` per row
    (the picker's two; a ponder's one), None where none came back. Raises
    `decisions.DecisionError` when nothing could be asked."""
    from llm.prompts import character_jev_options, character_jev_text
    from mind import character_jev as jev

    names = tuple(questions)
    scale = character_jev_options("grade", language)
    texts = {name: character_jev_text(name, language) for name in names}
    asked = {}
    for mid in net:
        line = memory_line(memories[mid], current_turn_idx)
        for name in names:
            asked[f"{name}__{mid}"] = {"type": "choice",
                                       "instructions": texts[name].replace("{memory}", line),
                                       "criteria": dict(scale)}
    answers = jev.ask(state, asked)
    out = {}
    for mid in net:
        known = [g for g in (jev.graded(answers, f"{name}__{mid}", jev.GRADE) for name in names)
                 if g is not None]
        out[mid] = max(known) if known else None
    return out


def ponder_state(person, view, active_state, unsettled, query, why=""):
    """The picker's state, and what the mind went looking for: the question
    it is asking its own memory and why, which every candidate is graded
    against."""
    parts = [memory_state(person, view, active_state, unsettled),
             "THE QUESTION YOU ARE ASKING YOUR OWN MEMORY: " + " ".join(str(query or "").split())]
    why = " ".join(str(why or "").split())
    if why:
        parts.append("WHY YOU ARE ASKING: " + why)
    return "\n\n".join(parts)


def jev_memory_packet(chat_id, char_id, query_text, *, current_turn_idx, embedded,
                      aspects=(), here=None, exclude_ids=(), limit=24, person=None,
                      view="", active_state=None, unsettled=(), language=None,
                      bank=None, record=None, net_size=NET_SIZE, questions=QUESTIONS,
                      state=None):
    """The rows this mind recalls this beat, best first, each carrying its
    `score` (its grade, or its net score when no grade came back). `person`
    (`{name, drive, values}`) names the mind the decision model grades for;
    without one -- the author's preview, which must not pay for a model call
    -- the packet is the net's own order. `record` receives what happened.
    `net_size`, `questions` and a ready `state` are a ponder's
    (`jev_ponder_packet`); the defaults are recall's."""
    record = record if record is not None else {}
    t0 = time.time()
    active_state = active_state or {}
    surface = ((active_state.get("affect") or {}).get("surface") or {}) \
        if isinstance(active_state.get("affect"), dict) else {}
    memories, net, lanes, vectors = memory_net(
        chat_id, char_id, query_text, current_turn_idx=current_turn_idx, embedded=embedded,
        aspects=aspects, here=here, exclude_ids=exclude_ids,
        feeling_valence=surface.get("valence") if isinstance(surface, dict) else None,
        bank=bank, size=net_size)
    record.update(bank=len(memories), net=len(net),
                  lanes=sorted(name for name, ranking in lanes.items() if ranking))
    grades = {}
    if person is not None and net:
        try:
            from llm import decisions
            if decisions.configured():
                if state is None:
                    state = memory_state(person, view, active_state, unsettled)
                grades = grade_net(net, memories, state, current_turn_idx, language, questions)
                record["asked"] = len(tuple(questions)) * len(net)
                record["answered"] = sum(1 for g in grades.values() if g is not None)
            else:
                record["unasked"] = "no decision model is configured"
        except Exception as exc:  # the floor: a beat is never lost to a grade
            grades = {}
            record["unasked"] = f"{type(exc).__name__}: {str(exc)[:200]}"
    elif person is None:
        record["unasked"] = "no mind named (preview)"
    graded = any(g is not None for g in grades.values())
    position = {mid: i for i, mid in enumerate(net)}
    order = sorted(net, key=lambda mid: (
        -(grades.get(mid) if grades.get(mid) is not None else -1.0), position[mid])) \
        if graded else list(net)
    kept, kept_vectors, dropped = [], [], 0
    for mid in order:
        fv = (vectors.get(mid) or (None, None))[0]
        if fv is not None and any(_cos(fv, other) >= NEAR_DUPLICATE for other in kept_vectors):
            dropped += 1
            continue
        kept.append(mid)
        if fv is not None:
            kept_vectors.append(fv)
        if len(kept) >= max(0, int(limit)):
            break
    out = []
    for mid in kept:
        mem = dict(memories[mid])
        grade = grades.get(mid)
        mem["score"] = round(float(grade), 6) if grade is not None else mem.get("net_score", 0.0)
        mem["picked_by"] = "decision model" if grade is not None else "net"
        out.append(mem)
    record.update(picked=len(out), near_duplicates_dropped=dropped,
                  seconds=round(time.time() - t0, 3))
    return out


def jev_ponder_packet(chat_id, char_id, query, *, why="", current_turn_idx, embedded,
                      here=None, limit=PONDER_LIMIT, person=None, view="",
                      active_state=None, unsettled=(), language=None, bank=None,
                      record=None):
    """What a ponder brings up (the owner, 2026-09-29: "Ponder pulls up 50
    candidates using rrf for jev to sort on how well it answers the ponder"):
    a net of `PONDER_NET` by the picker's equal-weight RRF over the question
    the mind asked its own memory (`embedded` carries that question alone),
    each candidate graded on how directly it answers it
    (`character_jev.memory_ponder`, with the question and why in the state),
    the best `limit` kept that reach `PONDER_FLOOR` -- near-duplicates
    dropped, as recall drops them. None reach it, and the ponder brings back
    nothing: a mind that went looking and did not find it is told so by an
    empty lane, not handed five unrelated rows. Rows already in this beat's
    packet are candidates too: a ponder may bring back what recall also did,
    and the payload says so. Without a named mind, or a decision model to
    ask, it is the net's own order, ungraded and uncut."""
    active_state = active_state or {}
    record = record if record is not None else {}
    picks = jev_memory_packet(
        chat_id, char_id, query, current_turn_idx=current_turn_idx, embedded=embedded,
        here=here, limit=limit, person=person, view=view, active_state=active_state,
        unsettled=unsettled, language=language, bank=bank, record=record,
        net_size=PONDER_NET, questions=PONDER_QUESTIONS,
        state=(ponder_state(person, view, active_state, unsettled, query, why)
               if person is not None else None))
    if not any(m.get("picked_by") == "decision model" for m in picks):
        return picks
    kept = [m for m in picks
            if m.get("picked_by") == "decision model" and float(m.get("score") or 0.0) >= PONDER_FLOOR]
    record.update(below_floor=len(picks) - len(kept), nothing_came_back=not kept)
    return kept
