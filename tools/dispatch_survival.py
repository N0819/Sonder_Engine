#!/usr/bin/env python3
"""Did the content a narrower dispatch would skip actually reach the world?

This is the measurement design note `DESIGN_NARROW_MODEL_INTERFACE.md` section
3c-ter said did not exist, and it is the one that decides section 3c.

`tools/dispatch_replay.py` counts the productive calls a categories-only
dispatch would skip. `tools/dispatch_residuals.py` prints them. Neither can say
whether the skipped output MATTERED, because `_produced` counts any non-empty
channel and cannot tell a newly encoded change from a re-assertion of something
already true.

This compares each skipped hand's own output against the MERGED `state_diff`
the turn actually committed -- the `director_resolve` step's active variant,
which is what `persist/commit.py` reads. Content present there is content that
reached the world, so losing the call that produced it is a real loss and not
a saving.

WHY THE ANSWER SPLITS BY CHANNEL SHAPE, which is the finding: a hand's ledgers
are either EVENT-shaped (`contact_ops`, `inventory_ops`, `substance_ops` -- a
thing that happened) or RECORD-shaped (`poses`, `overlays`, `conditions`,
`entities`, `rooms` -- the whole current state of a subject, re-emitted every
beat). `changes_asserted` counts CHANGES, so it can only ever address the
first kind. A pose record is re-stated every beat whether or not the pose
changed, and the Director is right to file no manifest entry for it -- which
means the manifest can never be the thing that dispatches the hand that keeps
it.

    python3 tools/dispatch_survival.py --db engine.db

Read-only on whatever `--db` names.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.dispatch_replay import BUCKET_SECONDS, DIRECTOR_STEPS, _parse  # noqa: E402
from tools.dispatch_residuals import residuals  # noqa: E402
from tools.narrow_interface_coverage import RECORD_SHAPED  # noqa: E402


def _entries(value):
    """One channel's content as comparable (key, entry) pairs.

    A channel is a dict keyed by subject (`poses`, `overlays`) or a list of
    events (`contact_ops`). Both reduce to pairs so one comparison serves.
    """
    if isinstance(value, dict):
        return [(str(k), v) for k, v in value.items()]
    if isinstance(value, list):
        return [(str(i), v) for i, v in enumerate(value)]
    return [("", value)]


def _canon(entry):
    return json.dumps(entry, sort_keys=True, ensure_ascii=False, default=str)


def _committed_diff(db, turn_id):
    row = db.execute(
        "SELECT v.content FROM variants v JOIN steps s ON s.id = v.step_id "
        "WHERE v.active=1 AND s.key='director_resolve' AND s.turn_id=?",
        (turn_id,)).fetchone()
    if not row:
        return None
    try:
        return json.loads(row[0]).get("state_diff") or {}
    except (TypeError, ValueError):
        return None


def _hand_output(db, blobs, turn_id, role):
    row = db.execute(
        "SELECT response_hash FROM llm_capture WHERE ok=1 AND turn_id=? "
        "AND step_key='director_resolve' AND role=? "
        "AND response_hash IS NOT NULL", (turn_id, role)).fetchone()
    return _parse(blobs.get(row[0])) if row else None


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.environ.get("ENGINE_DB") or "engine.db")
    args = ap.parse_args(argv)

    from agents.director_scopes import SPECIALISTS
    role_of = {name: spec["role"] for name, spec in SPECIALISTS.items()}

    found = residuals(args.db)
    db = sqlite3.connect("file:%s?mode=ro" % args.db, uri=True)
    blobs = dict(db.execute("select hash, body from llm_blobs"))

    survived = collections.Counter()
    produced = collections.Counter()
    by_shape = collections.Counter()
    unknown = 0

    print("would a categories-only dispatch have lost committed content?\n")
    for case in found:
        diff = _committed_diff(db, case["turn"])
        out = _hand_output(db, blobs, case["turn"], role_of[case["hand"]])
        if diff is None or not isinstance(out, dict):
            unknown += 1
            continue
        lines = []
        for channel in case["filled"]:
            mine = _entries(out.get(channel))
            theirs = {_canon(v) for _, v in _entries(diff.get(channel))}
            kept = [k for k, v in mine if _canon(v) in theirs]
            shape = "record" if channel in RECORD_SHAPED else "event"
            produced[shape] += len(mine)
            survived[shape] += len(kept)
            by_shape[(shape, channel)] += len(kept)
            lines.append("      %-18s %-6s %d/%d entries reached the commit%s"
                         % (channel, shape, len(kept), len(mine),
                            "  <- " + ", ".join(k for k in kept[:3])
                            if kept else ""))
        print("   turn %s  hand=%s" % (case["turn"], case["hand"]))
        print("      note: %s" % case["note"][:110])
        for line in lines:
            print(line)
        print()

    db.close()
    total_p = sum(produced.values())
    total_s = sum(survived.values())
    print("cases examined      : %d (%d unreadable)" % (len(found) - unknown,
                                                        unknown))
    print("entries produced    : %d" % total_p)
    print("entries COMMITTED   : %d (%.0f%%)"
          % (total_s, 100.0 * total_s / max(1, total_p)))
    print()
    for shape in ("record", "event"):
        print("  %-7s channels : %d of %d entries committed"
              % (shape, survived[shape], produced[shape]))
    print()
    print("  committed, by channel:")
    for (shape, channel), n in sorted(by_shape.items(), key=lambda kv: -kv[1]):
        print("    %-18s %-6s %d" % (channel, shape, n))

    if total_s:
        print("\n  VERDICT: dropping the `ledger_notes` trigger would lose "
              "%d entries\n  that this corpus actually committed. It is not a "
              "saving." % total_s)
    else:
        print("\n  VERDICT: nothing the skipped hands produced reached the "
              "commit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
