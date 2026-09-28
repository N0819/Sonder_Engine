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
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))



def residuals(db_path):
    """Retired with the causal dispatch (see `dispatch_replay.replay`)."""
    raise SystemExit(
        "this replays the causal Director's ruling-keyed dispatch "
        "(`director_scopes._ruling_for`), deleted with it on 2026-09-27; "
        "run it from a checkout of an earlier commit (e.g. a8c41fde) "
        "against a copy of the database")


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
