#!/usr/bin/env python3
"""Does the Director categorize and annotate its own spans?

`DESIGN_SPECIALIST_CONTRACT.md` section 4a: `sequence` becomes the four-field
work item -- the chunk, a chronological id, the Director's note on how it
should resolve, and a category. The id is the engine's. The other two are the
model's, and this measures whether it writes them.

Read it against `tools/instruction_coverage.py`, which asks the same question
of the OLD channels. The migration is finished when every work item is a chunk
and `changes_asserted` is empty on every beat.

    python3 tools/chunk_coverage.py --db RUN.db

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


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.environ.get("ENGINE_DB") or "engine.db")
    ap.add_argument("--show", type=int, default=10)
    args = ap.parse_args(argv)

    db = sqlite3.connect("file:%s?mode=ro" % args.db, uri=True)
    blobs = dict(db.execute("select hash, body from llm_blobs"))
    rows = list(db.execute(
        "select response_hash from llm_capture where ok=1 and role='director' "
        "and step_key in (?, ?) and response_hash is not null", DIRECTOR_STEPS))
    db.close()

    from agents.director import manifest_category_targets

    beats = spans = categorized = noted = 0
    manifest_entries = 0
    cats = collections.Counter()
    unroutable = collections.Counter()
    examples = []
    for (digest,) in rows:
        out = _parse(blobs.get(digest))
        if not isinstance(out, dict):
            continue
        seq = [e for e in (out.get("sequence") or []) if isinstance(e, dict)]
        if not seq:
            continue
        beats += 1
        manifest_entries += len(out.get("changes_asserted") or [])
        for element in seq:
            spans += 1
            category = str(element.get("category") or "").strip()
            note = str(element.get("note") or "").strip()
            if category:
                categorized += 1
                cats[category] += 1
                if not manifest_category_targets(category):
                    unroutable[category] += 1
            if note:
                noted += 1
            if category and note and len(examples) < args.show:
                examples.append((element.get("attempt")
                                 or element.get("text") or "", category, note))

    print("author calls with a sequence : %d" % beats)
    print("spans                        : %d" % spans)
    print("  carrying a category        : %d (%.0f%%)"
          % (categorized, 100.0 * categorized / max(1, spans)))
    print("  carrying a note            : %d (%.0f%%)"
          % (noted, 100.0 * noted / max(1, spans)))
    print("changes_asserted entries     : %d  <- goes to 0 when the migration"
          % manifest_entries)
    print("                                    finishes")
    print()
    print("categories used:", dict(cats.most_common()))
    print("UNROUTABLE      :", dict(unroutable) or "none")
    if examples:
        print()
        print("chunks the Director filed:")
        for span, category, note in examples:
            print("  %-46s %-14s %s" % (str(span)[:46], category, note[:52]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
