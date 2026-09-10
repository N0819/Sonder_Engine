#!/usr/bin/env python3
"""Two `interpret_beats` runs of the same beats, compared on time AND on work.

The reasoning-effort lever is only worth pulling if the hands still DO the
job. Wall clock alone would call a hand that returned `{}` on every beat a
triumph, which is the shape of mistake this document has made before
(`tools/quest_drive.py` stubbed the model and read its own stub back as
evidence about prose).

So this reports, per role, both halves:

  * what it COST   -- calls, seconds, answer chars, reasoning chars
  * what it DID    -- how many calls produced channel content at all, and
                      which channels, so a run that got quiet is visible as
                      quiet rather than as fast

Beats are matched by their player input, not by turn id, because the two runs
are separate databases with their own numbering.

    python3 tools/effort_ab.py --base BASE.db --test TEST.db

Read-only on both.
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

NOT_CHANNEL_CONTENT = frozenset({"resolved_events", "phase_sources", "notes"})


def read(db_path):
    db = sqlite3.connect("file:%s?mode=ro" % db_path, uri=True)
    try:
        blobs = dict(db.execute("select hash, body from llm_blobs"))
        inputs = dict(db.execute("select id, player_input from turns"))
        rows = list(db.execute(
            "select turn_id, role, duration, response_hash, reasoning_hash "
            "from llm_capture where ok=1 and step_key in (?, ?)",
            DIRECTOR_STEPS))
    finally:
        db.close()

    per_role = collections.defaultdict(
        lambda: {"calls": 0, "secs": 0.0, "answer": 0, "reasoning": 0,
                 "productive": 0, "channels": collections.Counter()})
    per_beat = collections.defaultdict(lambda: {"secs": 0.0, "calls": 0})
    for turn, role, duration, resp, reason in rows:
        stat = per_role[role]
        stat["calls"] += 1
        stat["secs"] += float(duration or 0)
        stat["answer"] += len(blobs.get(resp) or "")
        stat["reasoning"] += len(blobs.get(reason) or "")
        beat = str(inputs.get(turn) or turn)
        per_beat[beat]["secs"] += float(duration or 0)
        per_beat[beat]["calls"] += 1
        if role == "director":
            continue
        out = _parse(blobs.get(resp))
        if isinstance(out, dict):
            filled = [k for k, v in out.items()
                      if v and k not in NOT_CHANNEL_CONTENT]
            if filled:
                stat["productive"] += 1
                stat["channels"].update(filled)
    return per_role, per_beat


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", required=True)
    ap.add_argument("--test", required=True)
    args = ap.parse_args(argv)

    base_roles, base_beats = read(args.base)
    test_roles, test_beats = read(args.test)

    print("%-18s %-28s   %-28s" % ("", "BASE", "TEST"))
    print("%-18s %5s %6s %7s %8s   %5s %6s %7s %8s   %s"
          % ("role", "calls", "secs", "answer", "reason", "calls", "secs",
             "answer", "reason", "secs delta"))
    total = [0.0, 0.0]
    for role in sorted(set(base_roles) | set(test_roles)):
        b = base_roles.get(role) or {"calls": 0, "secs": 0.0, "answer": 0,
                                     "reasoning": 0}
        t = test_roles.get(role) or {"calls": 0, "secs": 0.0, "answer": 0,
                                     "reasoning": 0}
        total[0] += b["secs"]
        total[1] += t["secs"]
        bn, tn = max(1, b["calls"]), max(1, t["calls"])
        delta = ""
        if b["calls"] and t["calls"]:
            per_b, per_t = b["secs"] / bn, t["secs"] / tn
            delta = "%+.0f%% per call" % (100.0 * (per_t - per_b) / per_b)
        print("%-18s %5d %6.1f %7.0f %8.0f   %5d %6.1f %7.0f %8.0f   %s"
              % (role, b["calls"], b["secs"], b["answer"] / bn,
                 b["reasoning"] / bn, t["calls"], t["secs"],
                 t["answer"] / tn, t["reasoning"] / tn, delta))
    print("%-18s %5s %6.1f %7s %8s   %5s %6.1f %7s %8s   %+.0f%% total"
          % ("ALL", "", total[0], "", "", "", total[1], "", "",
             100.0 * (total[1] - total[0]) / max(0.01, total[0])))

    print()
    print("DID THE HANDS STILL DO THE WORK?  (a fast run that went quiet is")
    print("a regression, not a win)")
    print("%-18s %-18s   %-18s" % ("role", "BASE productive", "TEST productive"))
    for role in sorted(set(base_roles) | set(test_roles)):
        if role == "director":
            continue
        b = base_roles.get(role) or {"calls": 0, "productive": 0,
                                     "channels": collections.Counter()}
        t = test_roles.get(role) or {"calls": 0, "productive": 0,
                                     "channels": collections.Counter()}
        print("%-18s %2d/%-2d %-12s   %2d/%-2d %-12s"
              % (role, b["productive"], b["calls"],
                 ",".join(sorted(b["channels"]))[:12],
                 t["productive"], t["calls"],
                 ",".join(sorted(t["channels"]))[:12]))

    print()
    print("channels each hand wrote, base -> test:")
    for role in sorted(set(base_roles) | set(test_roles)):
        if role == "director":
            continue
        b = (base_roles.get(role) or {}).get("channels") or collections.Counter()
        t = (test_roles.get(role) or {}).get("channels") or collections.Counter()
        if not b and not t:
            continue
        lost = sorted(set(b) - set(t))
        gained = sorted(set(t) - set(b))
        print("  %-18s base=%s" % (role, dict(b)))
        print("  %-18s test=%s%s%s"
              % ("", dict(t),
                 "   LOST: " + ",".join(lost) if lost else "",
                 "   NEW: " + ",".join(gained) if gained else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
