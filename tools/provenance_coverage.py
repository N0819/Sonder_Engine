#!/usr/bin/env python3
"""Could reconciliation match on an id instead of on endpoint text?

`DESIGN_SPECIALIST_CONTRACT.md` section 4a: the Director's entry becomes four
fields -- chunk, id, note, category -- and the ten endpoint fields
(`actor_part`, `target_part`, `contact_ref` ...) go away, because the HAND
derives endpoints from the chunk and its own ledgers.

That is blocked on one thing. `agents/director_evidence.py` proves a manifest
entry was encoded by MATCHING IT AGAINST THE DIFF ON THOSE ENDPOINTS -- around
lines 1074-1098 for contacts, because "two simultaneous contacts involving the
same actor are indistinguishable" otherwise. Remove the endpoints and that
check loses its key.

There is already a candidate replacement in the protocol: `phase_sources`, a
map of `"<channel>.<subject>" -> event_id` the hand returns beside its
channels. If a hand reliably says which event produced which channel entry,
reconciliation is an ID LOOKUP -- which is what `_manifest_items` says it
wanted all along: "composition is an id lookup rather than a comparison of two
spellings of the same change (design note 21)."

So: how often does a hand actually emit it, and does it cover the events the
hand claims to have encoded? A mechanism present on a third of calls cannot
replace a text match; one present on nearly all of them can.

    python3 tools/provenance_coverage.py --db engine.db

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


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.environ.get("ENGINE_DB") or "engine.db")
    args = ap.parse_args(argv)

    db = sqlite3.connect("file:%s?mode=ro" % args.db, uri=True)
    blobs = dict(db.execute("select hash, body from llm_blobs"))
    rows = list(db.execute(
        "select role, response_hash from llm_capture where ok=1 "
        "and step_key in (?, ?) and role like 'director\\_%' escape '\\' "
        "and response_hash is not null", DIRECTOR_STEPS))
    db.close()

    stat = collections.Counter()
    per_role = collections.defaultdict(collections.Counter)
    for role, digest in rows:
        out = _parse(blobs.get(digest))
        if not isinstance(out, dict):
            continue
        wrote = {k: v for k, v in out.items()
                 if v and k not in NOT_CONTENT}
        if not wrote:
            continue                      # nothing to attribute
        stat["productive calls"] += 1
        per_role[role]["productive"] += 1

        sources = out.get("phase_sources")
        sources = sources if isinstance(sources, dict) else {}
        claimed = [e for e in (out.get("resolved_events") or [])
                   if isinstance(e, dict)
                   and str(e.get("status") or "").lower() == "encoded"]

        if sources:
            stat["with phase_sources"] += 1
            per_role[role]["with sources"] += 1
        if claimed:
            stat["claiming encoded"] += 1

        # THE QUESTION: for a call that says it encoded event N, does its
        # provenance map actually cite N? That is what an id-based
        # reconciliation would have to read.
        if claimed:
            cited = {str(v) for v in sources.values()}
            for entry in claimed:
                stat["encoded claims"] += 1
                if str(entry.get("event_id")) in cited:
                    stat["  ...cited in phase_sources"] += 1
                    per_role[role]["cited"] += 1
                else:
                    per_role[role]["uncited"] += 1

        # And is every channel it wrote attributed to some event?
        for channel in wrote:
            stat["channels written"] += 1
            if any(str(path).split(".", 1)[0] == channel for path in sources):
                stat["  ...attributed to an event"] += 1

    print("productive specialist calls : %d" % stat["productive calls"])
    print("  emitted phase_sources     : %d (%.0f%%)"
          % (stat["with phase_sources"],
             100.0 * stat["with phase_sources"] / max(1, stat["productive calls"])))
    print()
    print("`encoded` claims scored      : %d" % stat["encoded claims"])
    print("  cited in phase_sources     : %d (%.0f%%)"
          % (stat["  ...cited in phase_sources"],
             100.0 * stat["  ...cited in phase_sources"] / max(1, stat["encoded claims"])))
    print()
    print("channels written             : %d" % stat["channels written"])
    print("  attributed to an event     : %d (%.0f%%)"
          % (stat["  ...attributed to an event"],
             100.0 * stat["  ...attributed to an event"] / max(1, stat["channels written"])))
    print()
    print("%-18s %10s %12s %7s %8s" % ("role", "productive", "w/ sources",
                                       "cited", "uncited"))
    for role in sorted(per_role):
        c = per_role[role]
        print("%-18s %10d %12d %7d %8d" % (role, c["productive"],
                                           c["with sources"], c["cited"],
                                           c["uncited"]))
    print()
    pct = 100.0 * stat["  ...cited in phase_sources"] / max(1, stat["encoded claims"])
    if pct >= 90:
        print("VERDICT: provenance is dense enough to reconcile on. An id")
        print("lookup could replace the endpoint text match.")
    else:
        print("VERDICT: NOT dense enough. At %.0f%% an id-only reconciliation" % pct)
        print("would report the rest as unencoded and buy a repair for each.")
        print("The chunk id has to be carried by the OP, not by a map the hand")
        print("fills in separately -- a second thing to remember is a thing")
        print("that gets forgotten.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
