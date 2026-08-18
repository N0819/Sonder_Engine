#!/usr/bin/env python3
"""Does the salience term in memory ranking actually change what comes back?

`search_memories` adds `0.08 * effective_importance(mem)` to every fused score.
Importance is revised on 0.14% of the corpus, so for almost every row that term
IS the salience it was minted with -- and the fire-rate harness shows that
number is compressed: mean 0.674, p10-p90 spread 0.27, 70% of all memories
between 0.6 and 0.8. A term that is nearly the same for every candidate cannot
reorder them, and a term that cannot reorder them is decoration.

"Nearly constant" is an argument, not a measurement. This replays real recall
against the real bank with the term live, removed, and spread, and reports how
much the top-k actually moves. Same shape as the aspect measurement that
refuted the claim aspect rankings were dead: run it, count top-k membership
changes, believe the count.

The first run refuted the plan it was built to serve: the term was never
silent, and both ways of "fixing" the compression moved retrieval MORE than
deleting the term did, because both were weight increases in disguise. Only
`respaced` -- rank-normalised inside the bank's own range, so ordering and
influence budget both hold -- was a distribution change and nothing else, and
that is what `memory._rank_normalized_importance` now ships.

So `live` is no longer the unrespaced term: it is the shipped behaviour, and
every arm is measured against it. `respaced` still differs from it slightly on
purpose -- this tool ranks over the whole bank while the engine ranks over the
rows a mind could actually reach at that turn, which is the correct scope and
the reason to keep both numbers visible.

    python3 tools/salience_replay.py                 # every bank, 6 probes each
    python3 tools/salience_replay.py --probes 12 -k 16
    python3 tools/salience_replay.py --json

WHY IT COPIES THE DATABASE. `search_memories` bumps `access_count` on every row
it returns, so replaying against `engine.db` would write to the live corpus --
thousands of times, since the whole point is to run the same query repeatedly.
The copy is made once and thrown away.

WHY IT NEEDS NO EMBEDDING PROVIDER. A probe's own stored vector is the query
vector, and the turn cutoff is set to the beat the probe was formed on -- so
the probe and everything after it are invisible to their own query, exactly as
audit F1 requires of live recall. That makes each probe an honest "what did
this mind have to hand when this happened", replayable offline forever.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ARMS = ("live", "off", "spread", "wide", "respaced")


def _bank_probes(con, per_bank, min_rows):
    """Evenly spaced probes from every bank big enough for ranking to mean
    something. Spaced rather than random so two runs of this tool compare."""
    banks = con.execute(
        "SELECT chat_id, char_id, COUNT(*) n FROM memories "
        "WHERE embedding IS NOT NULL GROUP BY 1,2 HAVING n >= ?",
        (min_rows,)).fetchall()
    probes = []
    for chat_id, char_id, n in banks:
        rows = con.execute(
            "SELECT id, gist, content, turn_idx FROM memories "
            "WHERE chat_id=? AND char_id=? AND embedding IS NOT NULL "
            "AND turn_idx IS NOT NULL ORDER BY turn_idx, id",
            (chat_id, char_id)).fetchall()
        # The back half only: a probe from turn 2 sees four memories and every
        # arm returns the same four, which would dilute the result with beats
        # that had no ranking to do.
        rows = rows[len(rows) // 2:]
        if not rows:
            continue
        step = max(1, len(rows) // per_bank)
        for row in rows[::step][:per_bank]:
            probes.append((chat_id, char_id, row[0],
                           (row[1] or row[2] or "")[:600], row[3]))
    return probes


def _percentiles(values):
    """Rank-normalise to [0,1]. Ties share the mean of their positions, so a
    bank where every row was minted at 0.7 stays flat rather than being handed
    a spurious ordering by row id."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    i = 0
    n = len(values)
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        rank = (i + j) / 2.0
        for k in range(i, j + 1):
            out[order[k]] = rank / max(1, n - 1)
        i = j + 1
    return out


def run(db_path, per_bank=6, k=16, min_rows=40, verbose=False):
    from llm import providers

    workdir = tempfile.mkdtemp(prefix="salience-replay-")
    copy = os.path.join(workdir, "replay.db")
    try:
        shutil.copy(db_path, copy)
        os.environ["ENGINE_DB"] = copy
        from core import db as db_module
        db_module.configure(copy)
        from mind import memory

        con = sqlite3.connect(copy)
        probes = _bank_probes(con, per_bank, min_rows)

        # Every bank's importance distribution, once, for the `spread` arm.
        spread_by_bank = {}
        for chat_id, char_id in {(p[0], p[1]) for p in probes}:
            rows = con.execute(
                "SELECT id, salience, importance FROM memories "
                "WHERE chat_id=? AND char_id=?", (chat_id, char_id)).fetchall()
            ids = [r[0] for r in rows]
            vals = [r[2] if r[2] is not None else (r[1] or 0.0) for r in rows]
            pct = _percentiles(vals)
            ordered = sorted(vals)
            lo = ordered[int(len(ordered) * 0.10)]
            hi = ordered[int(len(ordered) * 0.90)]
            spread_by_bank[(chat_id, char_id)] = {
                "spread": dict(zip(ids, pct)),
                # Percentile-ranked, then mapped back onto the range the bank
                # actually occupies. Ordering identical to `spread`, influence
                # budget identical to `live` -- so any movement it causes is
                # RE-SPACING and nothing else. The arm that separates "the
                # numbers are badly distributed" from "the term is too quiet".
                "respaced": dict(zip(ids, [lo + p * (hi - lo) for p in pct])),
            }

        vectors = {r[0]: r[1] for r in con.execute(
            "SELECT id, embedding FROM memories WHERE embedding IS NOT NULL")}
        model_key, dims = con.execute(
            "SELECT embedding_model, embedding_dim FROM memories "
            "WHERE embedding IS NOT NULL LIMIT 1").fetchone()

        real = memory.effective_importance
        results = {arm: {} for arm in ARMS}
        for chat_id, char_id, mid, text, turn_idx in probes:
            batch = providers.EmbeddingBatch(
                vectors=[memory._vec(vectors[mid])],
                model_key=model_key, dimensions=dims, fallback=False)
            table = spread_by_bank[(chat_id, char_id)]

            def arm_fn(arm):
                if arm == "live":
                    return real
                if arm == "off":
                    return lambda mem: 0.0
                if arm == "wide":
                    # The live number, stretched about its own mean. Isolates
                    # "the term is too flat" from "the term is wrong".
                    return lambda mem: max(0.0, min(1.0,
                                                    0.674 + (real(mem) - 0.674) * 3.0))
                return lambda mem: table[arm].get(mem["id"], 0.5)

            for arm in ARMS:
                memory.effective_importance = arm_fn(arm)
                try:
                    hits = memory.search_memories(
                        chat_id, char_id, text, k=k,
                        current_turn_idx=turn_idx, chronological=False,
                        embedded=batch)
                finally:
                    memory.effective_importance = real
                ranked = [h["id"] for h in
                          sorted(hits, key=lambda h: -h["score"])][:k]
                results[arm][(chat_id, char_id, mid)] = ranked

        con.close()
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    keys = list(results["live"])
    report = {"probes": len(keys), "k": k, "arms": {}}
    for arm in ARMS:
        if arm == "live":
            continue
        changed = moved = 0
        overlaps = []
        top1 = 0
        for key in keys:
            a, b = results["live"][key], results[arm][key]
            same = len(set(a) & set(b))
            overlaps.append(same / max(1, len(a)))
            if set(a) != set(b):
                changed += 1
            if a != b:
                moved += 1
            if a[:1] != b[:1]:
                top1 += 1
        report["arms"][arm] = {
            "membership_changed": changed,
            "order_changed": moved,
            "top1_changed": top1,
            "mean_overlap": sum(overlaps) / max(1, len(overlaps)),
        }
    if verbose:
        report["per_probe"] = {
            f"{c}:{ch}:{m}": {arm: results[arm][(c, ch, m)] for arm in ARMS}
            for c, ch, m in keys}
    return report


def render(report):
    lines = [f"{report['probes']} probes, top-{report['k']} compared against "
             f"the live term", ""]
    n = report["probes"] or 1
    for arm, stats in report["arms"].items():
        lines += [
            f"  {arm}",
            f"    top-{report['k']} membership changed  "
            f"{stats['membership_changed']:>4}/{n}  "
            f"({stats['membership_changed']/n*100:.1f}%)",
            f"    order changed                {stats['order_changed']:>4}/{n}  "
            f"({stats['order_changed']/n*100:.1f}%)",
            f"    top result changed           {stats['top1_changed']:>4}/{n}  "
            f"({stats['top1_changed']/n*100:.1f}%)",
            f"    mean overlap                 {stats['mean_overlap']*100:.1f}%",
        ]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default=os.environ.get("ENGINE_DB", "engine.db"))
    ap.add_argument("--probes", type=int, default=6, help="per bank")
    ap.add_argument("-k", type=int, default=16)
    ap.add_argument("--min-rows", type=int, default=40)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)
    if not os.path.exists(args.db):
        sys.exit(f"no database at {args.db}")
    report = run(args.db, per_bank=args.probes, k=args.k,
                 min_rows=args.min_rows, verbose=args.verbose)
    print(json.dumps(report, indent=2) if args.json else render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
