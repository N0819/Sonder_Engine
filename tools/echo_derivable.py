#!/usr/bin/env python3
"""Could code work out `resolved_events` instead of asking for it?

Sixteen of the forty sentences shared by all five specialist cores -- about
3,300 characters, 39% of the shared core, carried by every dispatched hand --
teach the `resolved_events` echo and the `not_mine`/`reroute_to` reroute
protocol. Design note section 3d listed these among the terms that "should not
reach a model at all", on the assumption they die with section 3c. Section
3c-quater rejected 3c, so they do not die on their own, and the question has to
be asked directly.

Section 4's test governs: a sentence may be deleted only if the engine does
the job without it. The engine already treats an unanswered id as unaddressed
and repairs it, so deleting the echo loses no DATA -- it costs repair calls.
Deleting it is therefore worth it only if code can derive the same verdict.

`_evidence_present` is the candidate, because it already does exactly this job
one step later: it checks a claimed encoding against the merged `state_diff`
before believing it. This replays every captured specialist call and asks how
often the code-derived verdict agrees with the hand's own answer.

READ THE DISAGREEMENTS, NOT THE PERCENTAGE. The two answers are not
symmetrical. Code saying "encoded" where the hand said `not_mine` is a hand
being modest about work it did. Code saying "not encoded" where the hand said
`encoded` is the expensive direction: it buys a repair call for a change that
was already carried.

    python3 tools/echo_derivable.py --db engine.db

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

#: The statuses a hand may answer with, per the shared core.
STATUSES = ("encoded", "already_true", "not_mine")


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


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.environ.get("ENGINE_DB") or "engine.db")
    ap.add_argument("--show", type=int, default=8,
                    help="how many disagreements of each kind to print")
    args = ap.parse_args(argv)

    from agents.director_evidence import (_evidence_present,
                                          _normalize_omission_category as norm)
    from agents.director_scopes import SPECIALISTS

    by_role = {spec["role"]: name for name, spec in SPECIALISTS.items()}

    db = sqlite3.connect("file:%s?mode=ro" % args.db, uri=True)
    blobs = dict(db.execute("select hash, body from llm_blobs"))
    rows = list(db.execute(
        "select turn_id, role, payload_hashes, response_hash "
        "from llm_capture where ok=1 and step_key in (?, ?) "
        "and response_hash is not null", DIRECTOR_STEPS))

    agree = collections.Counter()
    disagree = collections.Counter()
    examples = collections.defaultdict(list)
    diffs = {}

    # THE MANIFEST IS READ FROM THE HAND'S OWN PAYLOAD, not reconstructed from
    # the author's output. The model writes `event_id: 0` on every entry and
    # the ENGINE numbers them (`_manifest_items`), so the author's raw ids are
    # not the ids the hand answers with -- scored against the author's copy,
    # all 316 echoed ids missed, which looked like "no data" and was a join on
    # the wrong key. `payload_hashes['changes_asserted']` is what the hand was
    # actually shown, already numbered, and every one of the 172 echoing calls
    # carries it.
    for turn, role, payload_hashes, digest in rows:
        if role not in by_role:
            continue
        out = _parse(blobs.get(digest))
        if not isinstance(out, dict):
            continue
        echoed = out.get("resolved_events")
        if not isinstance(echoed, list) or not echoed:
            continue
        try:
            shown = json.loads(blobs.get(
                json.loads(payload_hashes or "{}").get("changes_asserted"))
                or "[]")
        except (TypeError, ValueError):
            continue
        manifest = {str(i.get("event_id")): dict(i, category=norm(i.get("category")))
                    for i in shown if isinstance(i, dict)}
        if not manifest:
            continue
        if turn not in diffs:
            diffs[turn] = _committed_diff(db, turn)
        sd = diffs[turn]
        if sd is None:
            continue
        for entry in echoed:
            if not isinstance(entry, dict):
                continue
            said = str(entry.get("status") or "").strip().lower()
            item = manifest.get(str(entry.get("event_id")))
            if said not in STATUSES or not item:
                continue
            try:
                derived = bool(_evidence_present(sd, item))
            except Exception:                 # noqa: BLE001 - measured, not run
                continue
            # What code would conclude, in the hand's own vocabulary:
            # present in the committed diff == the change is carried.
            code_says = "carried" if derived else "not carried"
            hand_says = "carried" if said in ("encoded", "already_true") \
                else "not carried"
            if code_says == hand_says:
                agree[(said, code_says)] += 1
            else:
                disagree[(said, code_says)] += 1
                if len(examples[(said, code_says)]) < args.show:
                    examples[(said, code_says)].append(
                        (turn, by_role[role], item.get("category"),
                         str(item.get("subject"))[:40],
                         str(item.get("change"))[:90]))
    db.close()

    total = sum(agree.values()) + sum(disagree.values())
    print("echoed events scored : %d" % total)
    if not total:
        print("nothing to score -- no captured call carried both a manifest "
              "and a resolved_events echo.")
        return 0
    print("code agrees with hand: %d (%.1f%%)"
          % (sum(agree.values()), 100.0 * sum(agree.values()) / total))
    print("code disagrees       : %d (%.1f%%)"
          % (sum(disagree.values()), 100.0 * sum(disagree.values()) / total))
    print()
    print("agreement by what the hand said:")
    for said in STATUSES:
        ok = sum(n for (s, _), n in agree.items() if s == said)
        no = sum(n for (s, _), n in disagree.items() if s == said)
        if ok + no:
            print("  %-13s %4d agree / %4d disagree  (%.0f%%)"
                  % (said, ok, no, 100.0 * ok / (ok + no)))
    print()

    # The expensive direction, named as such.
    costly = sum(n for (said, code), n in disagree.items()
                 if said == "encoded" and code == "not carried")
    print("THE EXPENSIVE DISAGREEMENT -- hand said `encoded`, the committed")
    print("diff does not show it: %d. Each would buy a repair call for a" % costly)
    print("change that was already carried, if code replaced the echo.")
    print()
    for key, rows_ in sorted(examples.items()):
        said, code = key
        print("  hand said %-12s code says %-12s (%d shown)"
              % (said, code, len(rows_)))
        for turn, hand, cat, subj, change in rows_:
            print("     turn %-6s %-8s %-14s %-24s %s"
                  % (turn, hand, cat, subj, change))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
