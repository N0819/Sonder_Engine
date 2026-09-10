#!/usr/bin/env python3
"""How often does a hand claim `encoded` and write nothing?

The shared specialist core asks each hand to answer every routed event with
`encoded` / `already_true` / `not_mine`, and warns in as many words that
"answering honestly is always cheaper than answering agreeably". A hand that
returns EMPTY channels and still says `encoded` is the worst available answer:
the reconciliation seam believes it, buys no repair, and the change is lost
without a warning anywhere.

This counts that exact shape, per role, from captured calls. It needs no
committed diff and no manifest join -- the claim and the channels are both in
the same response, which is what makes it a clean comparison between two runs
of the same beats.

Measured 2026-09-09: it is the failure mode that reasoning effort `low`
introduces on `director_objects`, on beats where a thing comes into being or
is broken.

    python3 tools/false_encoded.py --db RUN.db [--db OTHER.db]

Read-only.
"""

from __future__ import annotations

import argparse
import collections
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.dispatch_replay import DIRECTOR_STEPS, _parse  # noqa: E402

NOT_CONTENT = frozenset({"resolved_events", "phase_sources", "notes"})


def scan(db_path):
    db = sqlite3.connect("file:%s?mode=ro" % db_path, uri=True)
    try:
        blobs = dict(db.execute("select hash, body from llm_blobs"))
        rows = list(db.execute(
            "select turn_id, role, response_hash from llm_capture "
            "where ok=1 and step_key in (?, ?) and response_hash is not null",
            DIRECTOR_STEPS))
    finally:
        db.close()

    stat = collections.defaultdict(
        lambda: {"claims": 0, "false": 0, "calls_with_claims": 0,
                 "false_calls": 0})
    for _turn, role, digest in rows:
        if role == "director":
            continue
        out = _parse(blobs.get(digest))
        if not isinstance(out, dict):
            continue
        echoed = out.get("resolved_events")
        if not isinstance(echoed, list) or not echoed:
            continue
        wrote = any(v for k, v in out.items() if k not in NOT_CONTENT)
        claimed = [e for e in echoed if isinstance(e, dict)
                   and str(e.get("status") or "").lower() == "encoded"]
        if not claimed:
            continue
        s = stat[role]
        s["claims"] += len(claimed)
        s["calls_with_claims"] += 1
        if not wrote:
            # Claimed to have encoded something, and every channel is empty.
            s["false"] += len(claimed)
            s["false_calls"] += 1
    return stat


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", action="append", required=True,
                    help="a run database; repeat to compare runs")
    args = ap.parse_args(argv)

    for path in args.db:
        stat = scan(path)
        total_claims = sum(s["claims"] for s in stat.values())
        total_false = sum(s["false"] for s in stat.values())
        print("=== %s" % os.path.basename(path))
        print("    %-18s %8s %8s %9s" % ("role", "claims", "false",
                                         "false calls"))
        for role in sorted(stat):
            s = stat[role]
            print("    %-18s %8d %8d %9d" % (role, s["claims"], s["false"],
                                             s["false_calls"]))
        print("    %-18s %8d %8d   <- %.0f%% of `encoded` claims wrote NOTHING"
              % ("TOTAL", total_claims, total_false,
                 100.0 * total_false / max(1, total_claims)))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
