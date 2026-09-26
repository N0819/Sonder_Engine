"""How good a net is retrieval, when Jev judges what it catches?

An experiment instrument for `docs/design/DESIGN_JEV_CHARACTER_PASS.md`
(2026-09-26). The owner: "I feel that our RRF MMR Lexical hybrid system might
not be as good as it can be if we are shifting its role from primary recall
to... recall net with filtering by jev."

For one beat on a bank of any size:

1. Jev grades the WHOLE visible bank on two channels (`situation`, `useful`,
   graded form from `jev_memory_probe.py`). The top `--reference` rows by the
   larger of the two grades are the reference set: what the judge would keep.
2. Two nets are built over the same rows and the same query:
   - `fused`: today's reciprocal-rank-fusion ranking in fused order (the
     production seam, the diversity pass replaced for this process only);
   - `union`: a round-robin over separate candidate generators -- meaning,
     cue, keyword, each aspect, recency, importance -- each contributing its
     next best row in turn, so no single scoring decides coverage.
3. recall@N for each net: the share of the reference set inside its first N.

The query is the character's perception view at that turn (`perception_act`),
the aspects its goal, mood and concerns (`chat_chars.state.active_state` when
no capture exists). Read-only; Jev and the embedding provider are called.

Usage:
    ENGINE_DB=<a copy of engine.db> python tools/jev_net_recall.py \\
        --chat 63 --char 35 --out net_63.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

NETS_AT = (50, 100, 150, 200, 300)


def beat(chat_id, char_id, turn_id=None):
    """Query, aspects and the character state for the given (or latest) turn
    that has a perception view for this character."""
    from core.db import q

    turns = q("SELECT id, idx FROM turns WHERE chat_id=? ORDER BY idx DESC", (chat_id,))
    for turn in turns:
        if turn_id and turn["id"] != turn_id:
            continue
        row = q("SELECT v.content FROM steps s JOIN variants v ON v.step_id=s.id "
                "WHERE s.turn_id=? AND s.key='perception_act' AND v.active=1",
                (turn["id"],), one=True)
        view = ((json.loads(row["content"]).get("views") or {}).get(str(char_id))
                if row else None)
        if view:
            break
    else:
        raise SystemExit(f"no perception view for char {char_id} in chat {chat_id}")
    state = q("SELECT state FROM chat_chars WHERE chat_id=? AND char_id=?",
              (chat_id, char_id), one=True)
    active = (json.loads(state["state"]).get("active_state") or {}) if state and state["state"] else {}
    concerns = active.get("active_concerns") or []
    concerns = " ".join(str(c.get("text") if isinstance(c, dict) else c) for c in concerns)
    sheet = q("SELECT name, sheet FROM characters WHERE id=?", (char_id,), one=True)
    card = json.loads(sheet["sheet"]) if sheet and sheet["sheet"] else {}
    psychology = card.get("psychology") or {}
    drive = psychology.get("drive") or {}
    return {
        "chat_id": chat_id, "char_id": char_id, "turn_id": turn["id"], "turn_idx": turn["idx"],
        "name": sheet["name"] if sheet else str(char_id), "view": view,
        "goal": str(active.get("goal") or ""), "mood": str(active.get("mood") or ""),
        "concerns": concerns,
        "drive": str(drive.get("essence") or "") if isinstance(drive, dict) else str(drive),
        "values": psychology.get("values") or [],
    }


def generators(inputs, aspects):
    """Every visible row, and one ranking per candidate generator."""
    from llm.providers import embed_texts_meta
    from mind.memory_common import _cos, _vec
    from mind.memory_read import visible_memory_rows
    from mind.memory_retrieval import _lexical_memory_ranking, _rank_normalized_importance
    from mind.memory_write import _row_memory

    rows = visible_memory_rows(inputs["chat_id"], inputs["char_id"],
                               before_turn_idx=inputs["turn_idx"], viewer_frame_id=None,
                               include_archived=True)
    memories = {}
    vectors = {}
    texts = [inputs["view"]] + [text for _label, text in aspects]
    embedded = embed_texts_meta(texts)
    qv, avs = embedded.vectors[0], embedded.vectors[1:]
    for row in rows:
        mem = _row_memory(row)
        memories[mem["id"]] = mem
        ok = (row["embedding_model"] == embedded.model_key
              and row["embedding_dim"] == embedded.dimensions)
        vectors[mem["id"]] = ((_vec(row["embedding"]), _vec(row["cue_embedding"]))
                              if ok else (None, None))

    def by(score):
        scored = [(score(mid), mid) for mid in memories]
        return [mid for s, mid in sorted(scored, reverse=True) if s is not None and s > 0]

    ranks = {
        "semantic": by(lambda mid: _cos(qv, vectors[mid][0]) if vectors[mid][0] is not None else None),
        "cue": by(lambda mid: _cos(qv, vectors[mid][1]) if vectors[mid][1] is not None else None),
        "keyword": [mid for mid in _lexical_memory_ranking(
            inputs["chat_id"], inputs["char_id"], inputs["view"], limit=len(memories))
            if mid in memories],
        "recency": [m["id"] for m in sorted(memories.values(),
                                            key=lambda m: -(m["turn_idx"] or -1))],
    }
    importance = _rank_normalized_importance(memories)
    ranks["importance"] = sorted(memories, key=lambda mid: -importance.get(mid, 0.0))
    for (label, _text), av in zip(aspects, avs):
        ranks["aspect:" + label] = by(lambda mid, av=av: max(
            _cos(av, vectors[mid][0]) if vectors[mid][0] is not None else 0.0,
            _cos(av, vectors[mid][1]) if vectors[mid][1] is not None else 0.0))
    return memories, ranks


def union_net(ranks, size):
    """Round-robin over the generators: each contributes its next row not yet
    taken, in turn, until the net holds `size` rows."""
    taken, order = set(), []
    cursors = {name: 0 for name in ranks}
    while len(order) < size and any(cursors[n] < len(ranks[n]) for n in ranks):
        for name, ranking in ranks.items():
            while cursors[name] < len(ranking) and ranking[cursors[name]] in taken:
                cursors[name] += 1
            if cursors[name] < len(ranking):
                mid = ranking[cursors[name]]
                taken.add(mid)
                order.append(mid)
                cursors[name] += 1
                if len(order) >= size:
                    break
    return order


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--chat", type=int, required=True)
    parser.add_argument("--char", type=int, required=True)
    parser.add_argument("--turn", type=int, default=None, help="turn id; default the latest")
    parser.add_argument("--reference", type=int, default=30)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    import jev_memory_probe as probe

    inputs = beat(args.chat, args.char, args.turn)
    aspects = [(label, text) for label, text in (
        ("what you are trying to do", inputs["goal"]),
        ("how you are feeling", inputs["mood"]),
        ("what is still unsettled", inputs["concerns"])) if str(text or "").strip()]
    memories, ranks = generators(inputs, aspects)

    # 1. The judge over the whole bank.
    state = probe.state_for(inputs)
    questions = {}
    for mid, mem in memories.items():
        body = "\n\n" + probe.memory_text(mem, inputs["turn_idx"])
        for channel in ("situation", "useful"):
            questions[f"{channel}__{mid}"] = {
                "type": "choice", "instructions": probe.GRADED_CHANNELS[channel] + body,
                "criteria": {key: label for key, (label, _w) in probe.SCALE.items()}}
    grades, seconds, _raw = probe.ask_jev(state, questions)
    judged = {mid: max(grades.get(f"situation__{mid}") or 0.0,
                       grades.get(f"useful__{mid}") or 0.0) for mid in memories}
    reference = sorted(memories, key=lambda mid: -judged[mid])[:args.reference]

    # 2. The nets.
    fused_rows = probe.net(dict(inputs), inputs["view"], len(memories), aspects)
    fused = [row["id"] for row in fused_rows]
    union = union_net(ranks, len(memories))
    table = {}
    for name, order in (("fused", fused), ("union", union)):
        table[name] = {n: sum(1 for mid in reference if mid in set(order[:n])) / len(reference)
                       for n in NETS_AT if n <= len(memories)}
    # 3. Where each reference row sits, per generator.
    position = {name: {mid: i + 1 for i, mid in enumerate(r)} for name, r in ranks.items()}
    position["fused"] = {mid: i + 1 for i, mid in enumerate(fused)}
    rows = [{"id": mid, "judged": round(judged[mid], 3),
             "text": probe.memory_text(memories[mid], inputs["turn_idx"]),
             "ranks": {name: pos.get(mid) for name, pos in position.items()}}
            for mid in reference]

    result = {"inputs": {k: v for k, v in inputs.items() if k != "view"},
              "bank": len(memories), "jev_questions": len(questions), "jev_seconds": seconds,
              "recall": table, "reference": rows,
              "generators": {name: len(r) for name, r in ranks.items()}}
    Path(args.out).write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(f"chat {args.chat} char {args.char}: bank {len(memories)}, {len(questions)} Jev "
          f"questions in {seconds}s")
    for name, row in table.items():
        print(f"  {name:6} " + "  ".join(f"@{n}: {v:.0%}" for n, v in row.items()))


if __name__ == "__main__":
    main()
