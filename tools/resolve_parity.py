#!/usr/bin/env python3
"""Does the RESOLVE half emit work items, the way interpret does?

`DESIGN_SPECIALIST_CONTRACT.md` 4a, and the owner's framing: "resolve would
mostly do the same but for characters." The two Director stages are structural
twins, and the twin has been the one left behind twice now -- `ledger_notes`
was built on the resolve half only and interpret ran its hands with nothing to
transcribe (2026-09-09), and then the chunk migration built `sequence` on the
interpret half only, leaving the resolve author a sheet block asking for spans
and no field to write them into (2026-09-10).

So this asks the same question of both halves at once and prints them side by
side. `tools/chunk_coverage.py` answers it for interpret alone; this is the
parity check.

    python3 tools/resolve_parity.py --db RUN.db

Read-only.
"""

from __future__ import annotations

import argparse
import collections
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.dispatch_replay import _parse  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.environ.get("ENGINE_DB") or "engine.db")
    ap.add_argument("--show", type=int, default=8)
    args = ap.parse_args(argv)

    from agents.director import manifest_category_targets

    db = sqlite3.connect("file:%s?mode=ro" % args.db, uri=True)
    blobs = dict(db.execute("select hash, body from llm_blobs"))
    rows = list(db.execute(
        "select step_key, response_hash from llm_capture where ok=1 "
        "and role='director' and response_hash is not null"))
    db.close()

    stat = collections.defaultdict(collections.Counter)
    cats = collections.defaultdict(collections.Counter)
    examples = collections.defaultdict(list)
    for step, digest in rows:
        out = _parse(blobs.get(digest))
        if not isinstance(out, dict):
            continue
        half = "interpret" if step.endswith("interpret") else "resolve"
        seq = [e for e in (out.get("sequence") or []) if isinstance(e, dict)]
        stat[half]["calls"] += 1
        stat[half]["spans"] += len(seq)
        stat[half]["manifest"] += len(out.get("changes_asserted") or [])
        stat[half]["notes"] += len(out.get("ledger_notes") or {})
        for element in seq:
            category = str(element.get("category") or "").strip()
            note = str(element.get("note") or "").strip()
            if category:
                stat[half]["categorized"] += 1
                cats[half][category] += 1
                if not manifest_category_targets(category):
                    stat[half]["UNROUTABLE"] += 1
            if note:
                stat[half]["noted"] += 1
            if category and note and len(examples[half]) < args.show:
                examples[half].append((
                    element.get("actor") or "",
                    element.get("attempt") or element.get("text") or "",
                    category, note))

    print("%-12s %6s %6s %11s %6s %6s %11s %9s" % (
        "half", "calls", "spans", "categorized", "noted", "notes",
        "manifest", "UNROUTABLE"))
    for half in ("interpret", "resolve"):
        c = stat[half]
        if not c["calls"]:
            print("%-12s %6s  -- no calls of this half in this database --"
                  % (half, 0))
            continue
        print("%-12s %6d %6d %11d %6d %6d %11d %9d" % (
            half, c["calls"], c["spans"], c["categorized"], c["noted"],
            c["notes"], c["manifest"], c["UNROUTABLE"]))
    print()
    for half in ("interpret", "resolve"):
        if cats[half]:
            print("%s categories: %s" % (half, dict(cats[half].most_common())))
    for half in ("interpret", "resolve"):
        if examples[half]:
            print()
            print("%s spans:" % half)
            for actor, what, category, note in examples[half]:
                print("  %-12s %-40s %-10s %s"
                      % (str(actor)[:12], str(what)[:40], category, note[:44]))

    if stat["resolve"]["calls"] and not stat["resolve"]["spans"]:
        print()
        print("PARITY FAILURE: the resolve half ran and emitted no spans. Its "
              "hands\nhave only `director_note` to work from.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
