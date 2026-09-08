"""What one character's recall costs per beat: the bank scan, the frame
filter, and the MMR diversification pass (review 2026-09-07 item C15).

Three numbers, all measured on a real stored bank rather than a synthetic
one, because every cost here scales with bank size and with how many of the
rows carry a 20 KB pair of embedding BLOBs:

  * ``visible_memory_rows`` -- wall clock for one seam read, how many
    SELECTs ``frames.is_memory_visible`` issues on top of it (2-6 per row in
    a framed chat before C15; one per declared era after), and what the four
    reads one beat makes of the same bank cost with and without the per-beat
    memo.
  * ``search_memories`` -- wall clock for the whole ranked read at k, and how
    many ``_memory_similarity`` evaluations its MMR loop makes.
  * the ranked ids it returns, written to ``--out`` so a change that claims
    to be a pure speed-up can be diffed byte for byte against the run before
    it.

NO MODEL CALLS. The query embedding is built locally from a stored vector
plus seeded noise and stamped with the bank's own model key, so the ranking
exercises the real vector path without touching a provider; the databases
this is meant for have a blanked ``providers`` table.

Run against a READ-ONLY copy of a story database:

    python tools/bench/recall_scan_cost.py \
        --db /path/to/bench.db --chat 117 --char 78 --k 24 \
        --out /tmp/before.json

Then again after the change with a different ``--out`` and ``diff`` the two.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))


def _stub_embedding(bank_rows, model_key, dims, n_vectors, seed=0):
    """A query batch that looks like the bank's own model, built locally."""
    import numpy as np
    from llm.providers import EmbeddingBatch
    from mind.memory_common import _vec

    rng = np.random.RandomState(seed)
    seeds = [_vec(r["embedding"]) for r in bank_rows if r["embedding"]]
    vectors = []
    for i in range(n_vectors):
        base = seeds[(i * 37) % len(seeds)] if seeds else rng.randn(dims)
        v = np.asarray(base, dtype=np.float32) + 0.35 * rng.randn(dims).astype("float32")
        v = v / (np.linalg.norm(v) or 1.0)
        vectors.append(v.astype("float32"))
    return EmbeddingBatch(vectors=vectors, model_key=model_key,
                          dimensions=dims, fallback=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--chat", type=int, required=True)
    ap.add_argument("--char", type=int, required=True)
    ap.add_argument("--k", type=int, default=24)
    ap.add_argument("--repeat", type=int, default=5)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    os.environ["ENGINE_DB"] = args.db
    from core import db
    from core import frames as _frames
    db.configure(args.db)

    from mind import memory_retrieval as mr
    from mind.memory_read import memory_bank_cache, visible_memory_rows

    bank = db.q("SELECT * FROM memories WHERE chat_id=? AND char_id=?",
                (args.chat, args.char))
    if not bank:
        raise SystemExit("no memories for that chat/char")
    model_key = bank[0]["embedding_model"]
    dims = bank[0]["embedding_dim"]
    cutoff = db.q("SELECT MAX(idx)+1 AS n FROM turns WHERE chat_id=?",
                  (args.chat,), one=True)["n"]

    query = str(bank[len(bank) // 2]["content"] or "")[:900]
    aspects = [("what you are trying to do", "get to the bottom of it"),
               ("how you are feeling", "afraid and stubborn"),
               ("what is still unsettled", "the thing behind the door")]
    batch = _stub_embedding(bank, model_key, dims, 1 + len(aspects))
    mr.embed_texts_meta = lambda *a, **k: batch

    # ---- SELECT count inside the frame filter -------------------------
    frame_selects = {"n": 0}
    real_q = _frames.q

    def counting_q(*a, **k):
        frame_selects["n"] += 1
        return real_q(*a, **k)

    _frames.q = counting_q

    # ---- seam read ----------------------------------------------------
    t0 = time.perf_counter()
    for _ in range(args.repeat):
        frame_selects["n"] = 0
        rows = visible_memory_rows(
            args.chat, args.char, before_turn_idx=cutoff,
            viewer_frame_id=None, include_archived=True)
    seam_ms = (time.perf_counter() - t0) * 1000.0 / args.repeat

    # ---- the four reads one beat makes of the same bank ---------------
    def _beat(memo):
        for _ in range(4):
            visible_memory_rows(args.chat, args.char, before_turn_idx=cutoff,
                                viewer_frame_id=None, include_archived=True,
                                bank=memo)

    t0 = time.perf_counter()
    for _ in range(args.repeat):
        _beat(None)
    beat_plain_ms = (time.perf_counter() - t0) * 1000.0 / args.repeat
    t0 = time.perf_counter()
    for _ in range(args.repeat):
        _beat(memory_bank_cache())
    beat_memo_ms = (time.perf_counter() - t0) * 1000.0 / args.repeat

    # ---- similarity evaluations inside MMR ----------------------------
    sim_calls = {"n": 0}
    real_sim = mr._memory_similarity

    def counting_sim(*a, **kw):
        sim_calls["n"] += 1
        return real_sim(*a, **kw)

    mr._memory_similarity = counting_sim

    t0 = time.perf_counter()
    for _ in range(args.repeat):
        sim_calls["n"] = 0
        hits = mr.search_memories(
            args.chat, args.char, query, k=args.k, include_archived=True,
            current_turn_idx=cutoff, chronological=True, viewer_frame_id=None,
            aspects=aspects, embedded=batch, record_access=False)
    search_ms = (time.perf_counter() - t0) * 1000.0 / args.repeat

    mr._memory_similarity = real_sim
    _frames.q = real_q

    print("bank rows                 %d" % len(bank))
    print("visible_memory_rows       %8.2f ms   (%d rows, %d frame SELECTs)"
          % (seam_ms, len(rows), frame_selects["n"]))
    print("four seam reads, no memo  %8.2f ms" % beat_plain_ms)
    print("four seam reads, memo     %8.2f ms" % beat_memo_ms)
    print("search_memories k=%-3d     %8.2f ms   (%d _memory_similarity evaluations)"
          % (args.k, search_ms, sim_calls["n"]))

    if args.out:
        capture = {
            "chat": args.chat, "char": args.char, "k": args.k,
            "cutoff": cutoff, "bank": len(bank), "visible": len(rows),
            "visible_ids": sorted(r["id"] for r in rows),
            "ranked": [{"id": m["id"], "score": m["score"],
                        "reasons": m["retrieval_reasons"]} for m in hits],
        }
        with open(args.out, "w") as fh:
            json.dump(capture, fh, indent=1, sort_keys=True)
        print("answer capture -> %s" % args.out)


if __name__ == "__main__":
    main()
