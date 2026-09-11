#!/usr/bin/env python3
"""Was this hand given an instruction at all, or only the beat?

`DESIGN_SPECIALIST_CONTRACT.md`: a specialist should receive its scene-scoped
world state plus its work items -- dissected chunks with a chronological id and
the Director's note on how each should resolve -- and nothing of the beat's
prose. Today it receives the prose on every call and an instruction on some.

This counts the three cases that matter, per hand:

  BOTH        an event slice AND a note addressed to this hand
  NOTE ONLY   the Director said what it wants, in prose, with no numbered event
  EVENT ONLY  numbered events, with no note saying how to resolve them
  NEITHER     dispatched with no instruction whatsoever -- running on the
              beat's narrative alone, which is the case the contract exists
              to remove

NEITHER is the sharp end: the hand ran, was paid for, and was told nothing
about why. Every one of those is a dispatch decision the engine made on
evidence it then did not pass on.

    python3 tools/instruction_coverage.py --db engine.db

Read-only.
"""

from __future__ import annotations

import argparse
import collections
import json
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
            "select role, step_key, payload_hashes, response_hash "
            "from llm_capture where ok=1 and step_key in (?, ?) "
            "and role like 'director\\_%' escape '\\'", DIRECTOR_STEPS))
    finally:
        db.close()

    stat = collections.defaultdict(collections.Counter)
    for role, _step, payload_hashes, digest in rows:
        try:
            keys = json.loads(payload_hashes or "{}")
        except ValueError:
            continue
        has_event = bool(keys.get("changes_asserted"))
        has_note = bool(keys.get("director_note"))
        has_prose = bool(keys.get("resolved_event")
                         or keys.get("player_declaration"))
        bucket = ("both" if (has_event and has_note)
                  else "note only" if has_note
                  else "event only" if has_event
                  else "NEITHER")
        s = stat[role]
        s[bucket] += 1
        s["calls"] += 1
        s["prose"] += has_prose
        # Did a hand with no instruction at all still emit world state?
        if bucket == "NEITHER":
            out = _parse(blobs.get(digest))
            if isinstance(out, dict) and any(
                    v for k, v in out.items() if k not in NOT_CONTENT):
                s["NEITHER but wrote"] += 1
    return stat


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.environ.get("ENGINE_DB") or "engine.db")
    args = ap.parse_args(argv)

    stat = scan(args.db)
    order = ("both", "note only", "event only", "NEITHER")
    print("%-18s %6s %6s %10s %11s %9s %8s" % (
        "hand", "calls", "both", "note only", "event only", "NEITHER", "prose"))
    total = collections.Counter()
    for role in sorted(stat):
        s = stat[role]
        total.update(s)
        print("%-18s %6d %6d %10d %11d %9d %8d" % (
            role, s["calls"], s["both"], s["note only"], s["event only"],
            s["NEITHER"], s["prose"]))
    calls = max(1, total["calls"])
    print("%-18s %6d %6d %10d %11d %9d %8d" % (
        "TOTAL", total["calls"], total["both"], total["note only"],
        total["event only"], total["NEITHER"], total["prose"]))
    print()
    for bucket in order:
        print("  %-11s %5d  %4.0f%%" % (bucket, total[bucket],
                                        100.0 * total[bucket] / calls))
    print("  %-11s %5d  %4.0f%%  <- the beat's prose reached the hand"
          % ("prose", total["prose"], 100.0 * total["prose"] / calls))
    if total["NEITHER but wrote"]:
        print()
        print("  %d of the NEITHER calls still wrote world state -- entirely"
              % total["NEITHER but wrote"])
        print("  from the narrative, with no instruction to check it against.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
