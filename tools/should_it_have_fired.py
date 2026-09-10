#!/usr/bin/env python3
"""Did this specialist call CHANGE anything, or restate what it was shown?

Every "productive call" number in `DESIGN_NARROW_MODEL_INTERFACE.md` and in
`DESIGN_SPECIALIST_CONTRACT.md` counts a call as productive when any channel
came back non-empty. That is the wrong test, and it is the one
`dispatch_replay._produced` uses: a hand that re-emits a pose record
byte-identically scores exactly like a hand that encoded a new one.

So the empty-call rates, the "12 of 13 entries were committed" verdict that
REJECTED section 3c, and the 82% saving attributed to reasoning effort were all
measured against a definition of work that COULD include doing nothing.

MEASURED 2026-09-10, AND THE WORRY WAS UNFOUNDED: of 484 calls that returned
something, 197 could be compared against what the hand was shown, and 197 of
197 changed the world. Zero no-ops. Entry-level, 40 new and 318 changed against
5 byte-identical (1.4%). The other 287 emitted only op-shaped channels, where
the question does not arise -- an op IS an action, and cannot be "re-asserted"
the way a record can be restated.

Which means a hand that returns content is doing real work, section 3c's
rejection stands on firmer ground than it was given, and the waste is entirely
in the calls that return NOTHING. Kept as a standing check rather than deleted:
the definition of "productive" it corrects is one every other tool here uses.

This asks the right question. For each channel a hand emitted, compare it
against THE SAME CHANNEL IN ITS OWN PAYLOAD -- what it was shown before it
answered -- and classify every entry:

  NEW        a key the shown ledger did not have
  CHANGED    the same key, a different value
  IDENTICAL  byte-for-byte what it was already looking at

A call whose every entry is IDENTICAL did no work. It was dispatched, paid
for, and returned the world unchanged -- and under any dispatch rule, a hand
that would only restate what it was shown should not have fired.

Payload comparison, not diff comparison, deliberately: it is the rule this
session arrived at the hard way -- "the hand emitted something its ruling did
not announce" is not evidence of waste, because on a record-shaped channel the
ruling and the ledger are not counting the same things. What the hand was
SHOWN is the only fair baseline.

    python3 tools/should_it_have_fired.py --db engine.db [--show 12]

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
from tools.narrow_interface_coverage import RECORD_SHAPED  # noqa: E402

NOT_CONTENT = frozenset({"resolved_events", "phase_sources", "notes"})

#: Where a hand's OUTPUT channel lives in its INPUT payload, when the two are
#: not spelled the same. A hand emits operations (`contact_ops`) against a
#: ledger shown under its own name (`contacts`); an op list and a record list
#: are not like for like, so only genuinely same-shaped pairs belong here.
#: Anything unlisted scores as UNSCORED rather than as work.
_PAYLOAD_LEDGER = {
    "conditions": "active_conditions",
}


def _entries(value):
    """A channel's content as comparable (key, entry) pairs."""
    if isinstance(value, dict):
        return [(str(k), v) for k, v in value.items()]
    if isinstance(value, list):
        return [(json.dumps(v, sort_keys=True, ensure_ascii=False,
                            default=str), v) for v in value]
    return [("", value)]


def _canon(entry):
    return json.dumps(entry, sort_keys=True, ensure_ascii=False, default=str)


def scan(db_path):
    db = sqlite3.connect("file:%s?mode=ro" % db_path, uri=True)
    try:
        blobs = dict(db.execute("select hash, body from llm_blobs"))
        rows = list(db.execute(
            "select turn_id, role, payload_hashes, response_hash "
            "from llm_capture where ok=1 and step_key in (?, ?) "
            "and role like 'director\\_%' escape '\\' "
            "and response_hash is not null", DIRECTOR_STEPS))
    finally:
        db.close()

    per_role = collections.defaultdict(collections.Counter)
    verdicts = collections.Counter()
    noop_examples = []

    for turn, role, payload_hashes, digest in rows:
        out = _parse(blobs.get(digest))
        if not isinstance(out, dict):
            continue
        wrote = {k: v for k, v in out.items() if v and k not in NOT_CONTENT}
        if not wrote:
            per_role[role]["empty"] += 1
            verdicts["empty"] += 1
            continue
        try:
            keys = json.loads(payload_hashes or "{}")
        except ValueError:
            continue

        new = changed = identical = unscored = 0
        touched = []
        for channel, value in wrote.items():
            shown_blob = blobs.get(keys.get(channel)
                                   or _PAYLOAD_LEDGER.get(channel, ""))
            try:
                shown = json.loads(shown_blob) if shown_blob else None
            except ValueError:
                shown = None
            if shown is None:
                # UNSCORED, not new. The first cut counted these as new, which
                # made every event-shaped channel look like pure fresh work:
                # a hand emits `contact_ops` while its payload ledger is
                # `contacts`, so the lookup missed and 467 contact entries and
                # 291 social ones scored as new without ever being compared.
                # A channel we cannot line up against what the hand saw is a
                # channel this tool has nothing to say about.
                unscored += len(_entries(value))
                touched.append(channel + "?")
                continue
            shown_map = dict(_entries(shown))
            for key, entry in _entries(value):
                if key not in shown_map:
                    new += 1
                elif _canon(shown_map[key]) != _canon(entry):
                    changed += 1
                else:
                    identical += 1
            touched.append(channel)

        per_role[role]["calls"] += 1
        per_role[role]["new"] += new
        per_role[role]["changed"] += changed
        per_role[role]["identical"] += identical
        per_role[role]["unscored"] += unscored
        if new or changed:
            per_role[role]["did work"] += 1
            verdicts["did work"] += 1
        elif identical:
            per_role[role]["NO-OP"] += 1
            verdicts["NO-OP"] += 1
        else:
            per_role[role]["unjudged"] += 1
            verdicts["unjudged"] += 1
            if len(noop_examples) < 40:
                noop_examples.append((turn, role, touched, identical))
    return per_role, verdicts, noop_examples


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.environ.get("ENGINE_DB") or "engine.db")
    ap.add_argument("--show", type=int, default=12)
    args = ap.parse_args(argv)

    per_role, verdicts, noops = scan(args.db)

    print("%-18s %7s %8s %6s %9s %6s %8s %10s" % (
        "hand", "calls", "did work", "NO-OP", "unjudged", "new", "changed",
        "identical"))
    tot = collections.Counter()
    for role in sorted(per_role):
        c = per_role[role]
        tot.update(c)
        print("%-18s %7d %8d %6d %9d %6d %8d %10d" % (
            role, c["calls"], c["did work"], c["NO-OP"], c["unjudged"],
            c["new"], c["changed"], c["identical"]))
    print("%-18s %7d %8d %6d %9d %6d %8d %10d" % (
        "TOTAL", tot["calls"], tot["did work"], tot["NO-OP"], tot["unjudged"],
        tot["new"], tot["changed"], tot["identical"]))

    scored = max(1, tot["did work"] + tot["NO-OP"])
    print()
    print("Of the %d calls this tool could actually JUDGE (of %d that "
          "returned\nsomething -- the rest emitted only channels with no "
          "comparable ledger):" % (scored, tot["calls"]))
    print("  actually changed the world : %d (%.0f%%)"
          % (tot["did work"], 100.0 * tot["did work"] / scored))
    print("  restated what they saw     : %d (%.0f%%)  <- should not have fired"
          % (tot["NO-OP"], 100.0 * tot["NO-OP"] / scored))
    print("  (plus %d calls that returned nothing at all)" % tot["empty"])

    entries = max(1, tot["new"] + tot["changed"] + tot["identical"])
    print("  unscored entries           : %d (channel/ledger names differ)"
          % tot["unscored"])
    print()
    print("Entry-level: %d new, %d changed, %d IDENTICAL (%.0f%% of all "
          "entries written)" % (tot["new"], tot["changed"], tot["identical"],
                                100.0 * tot["identical"] / entries))

    if noops:
        print()
        print("no-op calls (turn, hand, channels restated):")
        for turn, role, touched, identical in noops[:args.show]:
            shapes = ",".join(
                "%s(%s)" % (c, "record" if c in RECORD_SHAPED else "event")
                for c in touched)
            print("  turn %-7s %-18s %2d entries  %s"
                  % (turn, role, identical, shapes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
