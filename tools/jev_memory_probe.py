"""Jev as a memory judge: what five questions surface from a character's net.

An experiment instrument for `docs/design/DESIGN_JEV_CHARACTER_PASS.md`
(2026-09-26). For one captured character call it rebuilds that beat's
retrieval inputs from the capture itself -- the character's perception view
(the query), its goal, mood and concerns (the aspects), the turn cutoff --
takes the reciprocal-rank-fusion NET through the production `search_memories`
seam (the top `--pool` rows by fused score, before the diversity pass), and
asks Jev five questions of every memory in it:

    situation      does it bear on the situation you are in now
    senses         does it share a sensation with this moment
    mood_match     did that moment feel the way you feel now
    mood_contrast  did it feel the opposite
    useful         does it hold information that helps with what you are doing

`--ask` adds deliberate recall: the question itself is the query, a pool of
`--ask-pool` comes from the same net, and Jev asks of each row whether it
helps answer the question.

Read-only against the database it is pointed at, apart from nothing: the
character stage's own `record_access=False` path is used, and no row is
written. Jev and the embedding provider are called over the network.

Usage:
    ENGINE_DB=<a copy of engine.db> python tools/jev_memory_probe.py \\
        --turn 4482 --char 58 --pool 200 --out probe_4482.json \\
        --ask "What went wrong with the TARDIS?"
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

CHANNELS = {
    "situation": "Does this memory bear on the situation you are in right now?",
    "senses": ("Does this memory share a particular sensation with this moment "
               "-- something you perceive now that you also perceived then?"),
    "mood_match": "Did the moment in this memory feel the way you feel right now?",
    "mood_contrast": ("Did the moment in this memory feel the opposite of how "
                      "you feel right now?"),
    "useful": ("Does this memory hold information that would help with what "
               "you are trying to do right now?"),
}
ASK = "Does this memory help answer the question: {question}"

#: `--variants`: sharper forms of the situation question, measured beside it.
#: `next` asks for consequence rather than topic; `graded` is a choice whose
#: distribution is read as an expected grade (none 0 .. central 1).
VARIANT_NEXT = "Would remembering this change what you do or say next?"
VARIANT_GRADED = "How much does this memory bear on this moment?"
GRADES = {
    "none": ("It has nothing to do with this moment.", 0.0),
    "slight": ("It touches this moment only in passing.", 1 / 3),
    "clear": ("It clearly bears on this moment.", 2 / 3),
    "central": ("It is what this moment is about.", 1.0),
}

#: `--graded`: every channel asked as "how much", answered on one neutral
#: scale and read as the distribution's expected grade -- the form that spread
#: the situation channel (p10 0.20 against 0.44 as a yes/no) on beat 4482.
GRADED_CHANNELS = {
    "situation": "How much does this memory bear on the situation you are in right now?",
    "senses": ("How much does this memory share a particular sensation with this moment "
               "-- something you perceive now that you also perceived then?"),
    "mood_match": "How much did the moment in this memory feel the way you feel right now?",
    "mood_contrast": ("How much did the moment in this memory feel the opposite of how "
                      "you feel right now?"),
    "useful": ("How much does this memory hold information that would help with what "
               "you are trying to do right now?"),
}
SCALE = {
    "not_at_all": ("Not at all.", 0.0),
    "slightly": ("Slightly.", 1 / 3),
    "clearly": ("Clearly.", 2 / 3),
    "strongly": ("Strongly.", 1.0),
}

#: How much of the view and of each memory a question carries. The state is
#: shared by every question in a request; the memory is per question.
VIEW_CHARS = 3000
MEMORY_CHARS = 500


def _blob(q, key_hash):
    row = q("SELECT body FROM llm_blobs WHERE hash=?", (key_hash,), one=True)
    if not row:
        return None
    body = row["body"]
    return json.loads(body.decode() if isinstance(body, bytes) else body)


def beat_inputs(turn_id, char_id):
    """The retrieval inputs of the FIRST captured call of this character on
    this turn, as the character stage built them."""
    from core.db import q

    turn = q("SELECT id, chat_id, idx FROM turns WHERE id=?", (turn_id,), one=True)
    caps = q("SELECT payload_hashes FROM llm_capture WHERE turn_id=? AND role='character_major' "
             "ORDER BY started", (turn_id,))
    chosen = None
    for cap in caps:
        hashes = json.loads(cap["payload_hashes"] or "{}")
        self_ = _blob(q, hashes.get("self")) if hashes.get("self") else None
        if isinstance(self_, dict) and str(self_.get("entity_id") or "") in (str(char_id), ""):
            chosen = (hashes, self_)
            break
        if chosen is None and isinstance(self_, dict):
            chosen = (hashes, self_)
    if chosen is None:
        raise SystemExit(f"no captured character call on turn {turn_id}")
    hashes, self_ = chosen
    memory = _blob(q, hashes.get("memory")) or {}
    view_row = q("SELECT v.content FROM steps s JOIN variants v ON v.step_id=s.id "
                 "WHERE s.turn_id=? AND s.key='perception_act' AND v.active=1",
                 (turn_id,), one=True)
    views = (json.loads(view_row["content"]).get("views") or {}) if view_row else {}
    view = str(views.get(str(char_id)) or "")
    active = self_.get("active_state") or {}
    concerns = active.get("active_concerns") or []
    concerns = " ".join(str(c.get("text") if isinstance(c, dict) else c) for c in concerns)
    psychology = self_.get("psychology") or {}
    drive = psychology.get("drive") or {}
    # What happened THIS beat, apart from the standing scene the view also
    # describes: the perception's own events, in order.
    perception = _blob(q, hashes.get("perception")) if hashes.get("perception") else {}
    events = sorted((e for e in (perception or {}).get("events") or [] if isinstance(e, dict)),
                    key=lambda e: e.get("order") or 0)
    happened = " ".join(str((e.get("observed") or {}).get("text") or "") for e in events).strip()
    return {
        "chat_id": turn["chat_id"], "turn_idx": turn["idx"], "char_id": char_id,
        "name": self_.get("name") or str(char_id),
        "view": view,
        "goal": str(active.get("goal") or ""),
        "mood": str(active.get("mood") or ""),
        "concerns": concerns,
        "drive": str(drive.get("essence") or "") if isinstance(drive, dict) else str(drive),
        "happened": happened,
        "values": psychology.get("values") or [],
        # The packet labels rows per payload (`m9`), not by id, so a delivered
        # row is matched back to its memory by its own text.
        "delivered_texts": [str(m.get("details") or m.get("gist") or "")
                            for m in memory.get("recalled_old_memories") or []],
    }


def net(inputs, query, pool, aspects):
    """The top `pool` rows by fused score, through the production seam, with
    the diversity pass replaced by plain fused order for this process only."""
    from mind import memory_retrieval as retrieval

    original = retrieval._mmr_select
    # Only rows this beat may see: the keyword lane can score ids the turn
    # cutoff or the frame rule removed, which the real selection never picks.
    retrieval._mmr_select = lambda memories, fused, k: sorted(
        (mid for mid in fused if mid in memories),
        key=lambda mid: fused[mid], reverse=True)[:k]
    try:
        rows = retrieval.search_memories(
            inputs["chat_id"], inputs["char_id"], query, k=pool,
            current_turn_idx=inputs["turn_idx"], viewer_frame_id=None,
            chronological=False, aspects=aspects, record_access=False)
    finally:
        retrieval._mmr_select = original
    rows = sorted(rows, key=lambda m: m["score"], reverse=True)[:pool]
    for rank, row in enumerate(rows, 1):
        row["net_rank"] = rank
    return rows


def memory_text(row, turn_idx):
    body = " ".join(str(row.get("content") or row.get("gist") or "").split())[:MEMORY_CHARS]
    when = row.get("turn_idx")
    ago = f"{turn_idx - when} beats ago" if isinstance(when, int) else "some time ago"
    return f"MEMORY ({ago}): {body}"


def state_for(inputs):
    values = inputs["values"]
    values = "; ".join(str(v) for v in values) if isinstance(values, list) else str(values)
    return "\n\n".join(part for part in (
        f"YOU ARE {inputs['name']}.",
        "WHAT YOU PERCEIVE RIGHT NOW:\n" + inputs["view"][:VIEW_CHARS],
        "HOW YOU FEEL RIGHT NOW: " + (inputs["mood"] or "unremarkable"),
        "WHAT YOU ARE TRYING TO DO: " + (inputs["goal"] or "nothing in particular"),
        ("WHAT IS STILL UNSETTLED FOR YOU: " + inputs["concerns"]) if inputs["concerns"] else "",
        ("WHAT DRIVES YOU: " + inputs["drive"]) if inputs["drive"] else "",
        ("WHAT YOU VALUE: " + values) if values else "",
    ) if part)


def _expected_grade(answer):
    """A graded `choice` read as its expected grade, from the distribution Jev
    returns beside the chosen key (`probabilities`); the chosen key's grade
    when no distribution is readable. None when nothing is. Reads either
    scale -- `GRADES` or `SCALE` -- by key."""
    if not isinstance(answer, dict):
        return None
    weights = {key: w for table in (GRADES, SCALE) for key, (_t, w) in table.items()}
    dist = next((answer[k] for k in ("probabilities", "distribution", "scores")
                 if isinstance(answer.get(k), dict)), None)
    if dist:
        total = sum(float(v) for k, v in dist.items()
                    if k in weights and isinstance(v, (int, float)))
        if total > 0:
            return sum(weights[k] * float(v) for k, v in dist.items()
                       if k in weights and isinstance(v, (int, float))) / total
    choice = answer.get("choice")
    return weights.get(choice)


def ask_jev(state, questions):
    """`{key: value or None}` and the raw answers -- None where Jev returned no
    readable answer, kept apart from a real 0 (decisions.probability reads a
    missing answer as 0). A `noul` reads as its probability, a graded `choice`
    as its expected grade."""
    from llm import decisions

    t0 = time.time()
    answers = decisions.decide(state, questions)
    out = {}
    for key, question in questions.items():
        answer = answers.get(key)
        if question.get("type") == "choice":
            out[key] = _expected_grade(answer)
            continue
        value = answer.get("noul") if isinstance(answer, dict) else None
        try:
            out[key] = float(value) if value is not None else None
        except (TypeError, ValueError):
            out[key] = None
    return out, round(time.time() - t0, 2), answers


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--turn", type=int, required=True)
    parser.add_argument("--char", type=int, required=True)
    parser.add_argument("--pool", type=int, default=200)
    parser.add_argument("--ask", action="append", default=[])
    parser.add_argument("--ask-pool", type=int, default=50)
    parser.add_argument("--events-lane", action="store_true",
                        help="add this beat's events as their own aspect lane")
    parser.add_argument("--variants", action="store_true",
                        help="also ask the `next` and `graded` situation variants")
    parser.add_argument("--graded", action="store_true",
                        help="ask every channel as a graded choice (`GRADED_CHANNELS`)")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    from core.db import q

    inputs = beat_inputs(args.turn, args.char)
    aspects = [("what you are trying to do", inputs["goal"]),
               ("how you are feeling", inputs["mood"]),
               ("what is still unsettled", inputs["concerns"])]
    if args.events_lane:
        aspects.append(("what just happened", inputs["happened"]))
    rows = net(inputs, inputs["view"] or inputs["goal"], args.pool, aspects)
    def fold(text):
        return " ".join(str(text or "").split()).casefold()[:160]

    by_text = {}
    for r in q("SELECT id, content, gist FROM memories WHERE chat_id=? AND char_id=?",
               (inputs["chat_id"], inputs["char_id"])):
        for text in (r["content"], r["gist"]):
            if text:
                by_text.setdefault(fold(text), r["id"])
    delivered = [by_text.get(fold(text)) for text in inputs["delivered_texts"]]

    state = state_for(inputs)
    channels = dict(GRADED_CHANNELS if args.graded else CHANNELS)
    if args.graded:
        questions = {f"{channel}__{row['id']}": {
            "type": "choice",
            "instructions": text + "\n\n" + memory_text(row, inputs["turn_idx"]),
            "criteria": {key: label for key, (label, _w) in SCALE.items()}}
            for channel, text in GRADED_CHANNELS.items() for row in rows}
    else:
        questions = {f"{channel}__{row['id']}": {
            "type": "noul",
            "instructions": text + "\n\n" + memory_text(row, inputs["turn_idx"])}
            for channel, text in CHANNELS.items() for row in rows}
    if args.variants:
        channels["situation_next"] = VARIANT_NEXT
        channels["situation_graded"] = VARIANT_GRADED
        for row in rows:
            body = "\n\n" + memory_text(row, inputs["turn_idx"])
            questions[f"situation_next__{row['id']}"] = {
                "type": "noul", "instructions": VARIANT_NEXT + body}
            questions[f"situation_graded__{row['id']}"] = {
                "type": "choice", "instructions": VARIANT_GRADED + body,
                "criteria": {key: text for key, (text, _w) in GRADES.items()}}
    scores, seconds, raw = ask_jev(state, questions)
    sample_graded = next((raw.get(k) for k in questions if k.startswith("situation_graded__")), None)

    asked = []
    for question in args.ask:
        pool_rows = net(inputs, question, args.ask_pool, aspects=None)
        ask_questions = {f"ask__{row['id']}": {
            "type": "noul",
            "instructions": ASK.format(question=question) + "\n\n"
                            + memory_text(row, inputs["turn_idx"])} for row in pool_rows}
        ask_scores, ask_seconds, _raw = ask_jev(state, ask_questions)
        asked.append({"question": question, "seconds": ask_seconds, "rows": [
            {"id": row["id"], "net_rank": row["net_rank"],
             "p": ask_scores.get(f"ask__{row['id']}"),
             "text": memory_text(row, inputs["turn_idx"])} for row in pool_rows]})

    result = {
        "inputs": {k: v for k, v in inputs.items() if k != "view"},
        "view_chars": len(inputs["view"]), "state_chars": len(state),
        "pool": len(rows), "questions": len(questions), "jev_seconds": seconds,
        "delivered_ids": delivered,
        "aspects": [label for label, text in aspects if str(text or "").strip()],
        "sample_graded_answer": sample_graded,
        "rows": [{"id": row["id"], "net_rank": row["net_rank"],
                  "score": row["score"], "reasons": row.get("retrieval_reasons"),
                  "text": memory_text(row, inputs["turn_idx"]),
                  "jev": {channel: scores.get(f"{channel}__{row['id']}")
                          for channel in channels}} for row in rows],
        "asked": asked,
    }
    Path(args.out).write_text(json.dumps(result, indent=1), encoding="utf-8")
    missing = sum(1 for v in scores.values() if v is None)
    print(f"turn {args.turn}: pool {len(rows)}, {len(questions)} questions in "
          f"{seconds}s ({missing} unanswered); delivered {len(delivered)}; "
          f"asked {len(asked)} -> {args.out}")


if __name__ == "__main__":
    main()
