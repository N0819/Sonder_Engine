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
    return {
        "chat_id": turn["chat_id"], "turn_idx": turn["idx"], "char_id": char_id,
        "name": self_.get("name") or str(char_id),
        "view": view,
        "goal": str(active.get("goal") or ""),
        "mood": str(active.get("mood") or ""),
        "concerns": concerns,
        "drive": str(drive.get("essence") or "") if isinstance(drive, dict) else str(drive),
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


def ask_jev(state, questions):
    """`{key: p or None}` -- None where Jev returned no readable answer, kept
    apart from a real 0 (decisions.probability reads a missing answer as 0)."""
    from llm import decisions

    t0 = time.time()
    answers = decisions.decide(state, questions)
    out = {}
    for key in questions:
        answer = answers.get(key)
        value = answer.get("noul") if isinstance(answer, dict) else None
        try:
            out[key] = float(value) if value is not None else None
        except (TypeError, ValueError):
            out[key] = None
    return out, round(time.time() - t0, 2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--turn", type=int, required=True)
    parser.add_argument("--char", type=int, required=True)
    parser.add_argument("--pool", type=int, default=200)
    parser.add_argument("--ask", action="append", default=[])
    parser.add_argument("--ask-pool", type=int, default=50)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    from core.db import q

    inputs = beat_inputs(args.turn, args.char)
    aspects = [("what you are trying to do", inputs["goal"]),
               ("how you are feeling", inputs["mood"]),
               ("what is still unsettled", inputs["concerns"])]
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
    questions = {f"{channel}__{row['id']}": {
        "type": "noul",
        "instructions": text + "\n\n" + memory_text(row, inputs["turn_idx"])}
        for channel, text in CHANNELS.items() for row in rows}
    scores, seconds = ask_jev(state, questions)

    asked = []
    for question in args.ask:
        pool_rows = net(inputs, question, args.ask_pool, aspects=None)
        ask_questions = {f"ask__{row['id']}": {
            "type": "noul",
            "instructions": ASK.format(question=question) + "\n\n"
                            + memory_text(row, inputs["turn_idx"])} for row in pool_rows}
        ask_scores, ask_seconds = ask_jev(state, ask_questions)
        asked.append({"question": question, "seconds": ask_seconds, "rows": [
            {"id": row["id"], "net_rank": row["net_rank"],
             "p": ask_scores.get(f"ask__{row['id']}"),
             "text": memory_text(row, inputs["turn_idx"])} for row in pool_rows]})

    result = {
        "inputs": {k: v for k, v in inputs.items() if k != "view"},
        "view_chars": len(inputs["view"]), "state_chars": len(state),
        "pool": len(rows), "questions": len(questions), "jev_seconds": seconds,
        "delivered_ids": delivered,
        "rows": [{"id": row["id"], "net_rank": row["net_rank"],
                  "score": row["score"], "reasons": row.get("retrieval_reasons"),
                  "text": memory_text(row, inputs["turn_idx"]),
                  "jev": {channel: scores.get(f"{channel}__{row['id']}")
                          for channel in CHANNELS}} for row in rows],
        "asked": asked,
    }
    Path(args.out).write_text(json.dumps(result, indent=1), encoding="utf-8")
    missing = sum(1 for v in scores.values() if v is None)
    print(f"turn {args.turn}: pool {len(rows)}, {len(questions)} questions in "
          f"{seconds}s ({missing} unanswered); delivered {len(delivered)}; "
          f"asked {len(asked)} -> {args.out}")


if __name__ == "__main__":
    main()
