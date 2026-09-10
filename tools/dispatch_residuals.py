#!/usr/bin/env python3
"""The false negatives `dispatch_replay` counts, read one at a time.

`tools/dispatch_replay.py` answers "how many productive calls would a narrower
dispatch lose". It cannot answer "and were they worth keeping", because its
`_produced` counts any non-empty channel as productive -- so a hand that
encoded a genuinely new change and a hand that re-asserted a fact already in
the ledger score identically.

That distinction is the whole of section 3c's remaining risk. Measured
2026-09-09 on the live corpus, the 8 filed-only false negatives were mostly
the second kind: a `ledger_notes` line carrying a CONTINUING state, which the
manifest correctly omits because a continuing state is not a change, followed
by a hand encoding it anyway. Two of the eight were a note that says in words
that nothing changed beside a hand that emitted a channel regardless.

This prints each one -- the note, the manifest's categories, and the channels
the hand filled -- so the judgement is made on the rulings rather than on the
count. It does NOT decide anything: settling section 3c means comparing each
hand's output against the committed `state_diff`, which is a harness that does
not exist yet.

    python3 tools/dispatch_residuals.py --db engine.db

Read-only on whatever `--db` names.
"""

from __future__ import annotations

import argparse
import collections
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.dispatch_replay import (BUCKET_SECONDS, DIRECTOR_STEPS,  # noqa: E402
                                   NOT_CHANNEL_CONTENT, _parse, _produced)


def residuals(db_path):
    from agents.director import _ruling_for
    from agents.director_scopes import SPECIALISTS
    try:
        from agents.director_evidence import _normalize_omission_category as norm
    except ImportError:                                   # pragma: no cover
        def norm(value):
            return str(value or "").strip().lower()

    db = sqlite3.connect("file:%s?mode=ro" % db_path, uri=True)
    try:
        blobs = dict(db.execute("select hash, body from llm_blobs"))
        rows = db.execute(
            "select turn_id, step_key, role, started, response_hash "
            "from llm_capture where ok=1 and step_key in (?, ?) "
            "and response_hash is not null", DIRECTOR_STEPS)
        beats = collections.defaultdict(list)
        where = {}
        for turn, step, role, started, digest in rows:
            key = (turn, step, round((started or 0) / BUCKET_SECONDS))
            beats[key].append((role, digest))
            where[key] = (turn, step)
    finally:
        db.close()

    by_role = {spec["role"]: name for name, spec in SPECIALISTS.items()}
    found = []
    for key, calls in beats.items():
        author = [d for role, d in calls if role == "director"]
        if not author:
            continue
        ruling = _parse(blobs.get(author[0]))
        if not isinstance(ruling, dict):
            continue
        manifest = [dict(item, category=norm(item.get("category")))
                    for item in (ruling.get("changes_asserted") or [])
                    if isinstance(item, dict)]
        if not manifest:
            continue                       # `--filed-only`, which is the case
        notes = ruling.get("ledger_notes") or {}
        today = {"ledger_notes": notes, "manifest": manifest}
        categories_only = {"ledger_notes": {}, "manifest": manifest}
        for role, digest in calls:
            name = by_role.get(role)
            if name is None:
                continue
            if not _ruling_for(name, today)[0]:
                continue
            if _ruling_for(name, categories_only)[0]:
                continue
            parsed = _parse(blobs.get(digest))
            if not _produced(parsed):
                continue                   # skipped, and empty anyway: a save
            found.append({
                "turn": where[key][0], "step": where[key][1], "hand": name,
                "note": str((notes or {}).get(name) or ""),
                "note_keys": sorted(notes) if isinstance(notes, dict) else [],
                "categories": sorted({str(i.get("category"))
                                      for i in manifest}),
                "filled": sorted(k for k, v in (parsed or {}).items()
                                 if v and k not in NOT_CHANNEL_CONTENT),
            })
    return found


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.environ.get("ENGINE_DB") or "engine.db")
    args = ap.parse_args(argv)

    found = residuals(args.db)
    print("filed-only false negatives: %d\n" % len(found))
    for case in found:
        print("turn %s  %s  hand=%s" % (case["turn"], case["step"],
                                        case["hand"]))
        print("   manifest categories : %s" % ", ".join(case["categories"]))
        print("   note keys           : %s" % ", ".join(case["note_keys"]))
        print("   this hand's note    : %s" % case["note"][:150])
        print("   channels it filled  : %s" % ", ".join(case["filled"][:6]))
        print()
    print("by hand:", dict(collections.Counter(c["hand"] for c in found)))
    print("channels at stake:", dict(collections.Counter(
        ch for c in found for ch in c["filled"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
