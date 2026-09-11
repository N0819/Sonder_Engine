#!/usr/bin/env python3
"""Every payload key and output field a Director sheet names -- does it exist?

Three leftovers were found by hand on 2026-09-10 and every one was the same
shape: the sheet naming something the engine no longer sends, or asking for a
field nothing reads. `world_books` was still on the wire but the job it was
sent for had become code's; `needs_mapping` was "read by no reader (E9)" while
the sheet still asked for it; two clauses instructed a mapping AGENT retired in
2026-09.

Finding those by reading is not repeatable, so this asks the two questions
mechanically, per identifier the sheet mentions:

  IN   -- does the payload actually carry this key? (from captured calls)
  OUT  -- does any non-test module read this field off the stage's output?

An identifier the sheet names that fails BOTH is a reference to something that
is not there. One that fails only OUT may still be doing work -- the model
reads a payload key without ever writing it back -- so the two columns are
reported separately rather than folded into a verdict.

    python3 tools/sheet_references.py --db RUN.db

Read-only. `--db` wants a database with recent captured Director calls; with
none, the IN column is reported as unknown rather than guessed.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Words that look like identifiers but are prose or JSON scaffolding.
_NOISE = frozenset({
    "true", "false", "null", "int", "str", "bool", "list", "dict", "json",
    "a_z", "e_g", "i_e", "id", "ids", "the_", "and_", "or_",
})


def _identifiers(text):
    """snake_case tokens the sheet names, which is what a payload key or an
    output field looks like. Single words are excluded: they are far more
    often prose than a key, and every real one in these sheets has an
    underscore."""
    found = collections.Counter()
    for token in re.findall(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b", text):
        if token not in _NOISE:
            found[token] += 1
    return found


def _payload_keys(db_path):
    """Every key any captured Director call actually carried."""
    if not db_path or not os.path.exists(db_path):
        return None
    import sqlite3
    db = sqlite3.connect("file:%s?mode=ro" % db_path, uri=True)
    try:
        rows = db.execute(
            "select payload_hashes from llm_capture where ok=1 "
            "and role like 'director%'")
        keys = collections.Counter()
        for (raw,) in rows:
            try:
                keys.update(json.loads(raw or "{}").keys())
            except ValueError:
                continue
    finally:
        db.close()
    return keys


def _read_by_code(token):
    """Does any non-test module read this name? `git grep` over the tree,
    excluding the language packs (where the sheet itself lives) and tests."""
    try:
        out = subprocess.run(
            ["git", "grep", "-l", "-w", token, "--",
             "*.py", ":!tests/*", ":!tools/*"],
            cwd=ROOT, capture_output=True, text=True, timeout=60)
    except Exception:                                    # noqa: BLE001
        return None
    return [f for f in out.stdout.split() if f]


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default="")
    ap.add_argument("--min", type=int, default=1,
                    help="ignore identifiers mentioned fewer times than this")
    args = ap.parse_args(argv)

    from llm.prompts import DEFAULT_PROMPTS

    sent = _payload_keys(args.db)
    sheets = {
        "interpret": DEFAULT_PROMPTS["director_interpret"],
        "resolve": DEFAULT_PROMPTS["director_resolve_lean"],
    }

    for label, text in sheets.items():
        names = _identifiers(text)
        rows = []
        for token, mentions in names.items():
            if mentions < args.min:
                continue
            in_payload = None if sent is None else (token in sent)
            readers = _read_by_code(token)
            rows.append((token, mentions, in_payload, readers))

        orphans = [r for r in rows if not r[3] and r[2] is not True]
        print("=== %s: %d distinct identifiers named, %d with no reader and "
              "not on the wire" % (label, len(rows), len(orphans)))
        for token, mentions, in_payload, readers in sorted(orphans):
            print("    %-28s mentioned %dx   payload=%s"
                  % (token, mentions,
                     "?" if in_payload is None else in_payload))
        print()

        weak = [r for r in rows if not r[3] and r[2] is True]
        if weak:
            print("    on the wire but read by no module (the model is told "
                  "about it and\n    nothing acts on what it writes back):")
            for token, mentions, _in, _r in sorted(weak):
                print("      %-26s mentioned %dx" % (token, mentions))
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
