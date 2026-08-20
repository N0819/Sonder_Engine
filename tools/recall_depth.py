#!/usr/bin/env python3
"""How far back do characters actually reach, and does more recall keep paying?

The question this exists for: retrieval recall rises monotonically with `k` --
at k = bank size it is 100% -- so no probe curve can say where to stop
delivering memories. Only conduct can, and conduct was costing nine synthetic
cases and hours of character calls per arm.

Ordinary play answers it for free once the engine records the TURN a recall
reached a row on (`memories.last_accessed_turn`, schema v32). Depth of reach is
`last_accessed_turn - turn_idx`. If nothing beyond a certain depth is ever
reached for, delivering more is spending payload on rows no mind wants.

Read-only. Safe against the live database.

Usage:
    python3 tools/recall_depth.py [--db engine.db] [--chat N]
"""

from __future__ import annotations

import argparse
import sqlite3
import statistics
import sys
from pathlib import Path


def _pct(values, p):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(p * len(ordered)))]


def report(db_path, chat_id=None):
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    # The column arrives with schema v32, and a database only migrates when
    # the engine next opens it -- so the first person to run this is, by
    # construction, on a database that predates it. Say so instead of raising
    # `no such column` at them.
    if "last_accessed_turn" not in {
            r["name"] for r in con.execute("PRAGMA table_info(memories)")}:
        print(f"{db_path} predates schema v32 and has no "
              "`last_accessed_turn`.\n\nStart the engine once against it -- "
              "the migration runs on open -- then play a few\nbeats so real "
              "recalls have something to record.")
        return
    where = ["last_accessed_turn IS NOT NULL", "turn_idx IS NOT NULL"]
    args = []
    if chat_id is not None:
        where.append("chat_id=?")
        args.append(chat_id)
    rows = con.execute(
        "SELECT chat_id, char_id, turn_idx, last_accessed_turn, access_count, "
        "salience FROM memories WHERE " + " AND ".join(where), args).fetchall()

    total = con.execute(
        "SELECT COUNT(*) n FROM memories"
        + (" WHERE chat_id=?" if chat_id is not None else ""), args).fetchone()["n"]

    if not rows:
        print(f"No rows carry a recorded recall turn yet ({total:,} memories).")
        print("\n`last_accessed_turn` is written only by a real recall during")
        print("play (record_access=True with a turn). It is deliberately NOT")
        print("backfilled: `last_accessed` is a wall clock and there is no")
        print("sound mapping from it to a turn index, so an invented depth")
        print("would poison the measurement this column exists to give.")
        print("\nPlay a few beats and run this again.")
        return

    depths = [r["last_accessed_turn"] - r["turn_idx"] for r in rows
              if r["last_accessed_turn"] >= r["turn_idx"]]
    print(f"{len(rows):,} of {total:,} memories have been reached during play "
          f"({len(rows)/max(1,total):.1%})\n")
    print("DEPTH OF REACH, in beats between forming and being recalled")
    print(f"   median {statistics.median(depths):>6.0f}")
    print(f"   p75    {_pct(depths, 0.75):>6}")
    print(f"   p90    {_pct(depths, 0.90):>6}")
    print(f"   p99    {_pct(depths, 0.99):>6}")
    print(f"   max    {max(depths):>6}")

    # The decision this is for: if almost nothing is reached from far back,
    # a larger payload is buying rows no mind asks for.
    print("\nSHARE OF REACHES BEYOND A GIVEN DEPTH")
    for cut in (10, 25, 50, 100, 200, 400):
        n = sum(1 for d in depths if d > cut)
        print(f"   deeper than {cut:>4} beats: {n:>6,}  ({n/len(depths):>5.1%})")

    print("\nPER CHARACTER (top 8 by reaches)")
    per = {}
    for r in rows:
        per.setdefault((r["chat_id"], r["char_id"]), []).append(
            r["last_accessed_turn"] - r["turn_idx"])
    for (cid, chid), ds in sorted(per.items(), key=lambda kv: -len(kv[1]))[:8]:
        print(f"   chat {cid:>3}/char {chid:<4} n={len(ds):>5}  "
              f"median {statistics.median(ds):>5.0f}  max {max(ds):>5}")

    print("\nHOW TO READ THIS")
    print("  A payload of k rows is worth its tokens only if rows that deep")
    print("  are actually reached. This says nothing about RANK -- a row's")
    print("  position in the payload is not recorded -- so it answers 'how far")
    print("  back' and not yet 'how far down'. The second needs rank at")
    print("  access, which is a larger change and is not built.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(Path(__file__).resolve().parents[1]
                                        / "engine.db"))
    ap.add_argument("--chat", type=int)
    args = ap.parse_args()
    report(args.db, args.chat)


if __name__ == "__main__":
    main()
