#!/usr/bin/env python3
"""Would a narrower specialist dispatch skip a hand that actually did work?

`docs/design/DESIGN_NARROW_MODEL_INTERFACE.md` section 3c proposes that the
Director stop addressing its hands and that code route `changes_asserted`
categories instead, deleting the `ledger_notes` dispatch trigger. That change is
cheap to make and expensive to get wrong: a hand not dispatched produces no
prompt, no payload and no output surface, so a wrongly-skipped hand is a change
that silently never happened.

This replays every captured Director ruling through the REAL dispatch predicate
(`director_scopes._ruling_for`) twice -- once as it runs today, once with the
`ledger_notes` trigger removed -- and scores each decision against what the hand
that ran actually returned.

**The acceptance criterion is FALSE NEGATIVES == 0.** A saved call is only worth
having if no productive call is lost with it. Run this before and after any
change to `_ruling_for`, `_CATEGORY_CHANNELS`, or either Director schema's
manifest field.

    python tools/dispatch_replay.py                    # against $ENGINE_DB
    python tools/dispatch_replay.py --db copy.db --filed-only

`--filed-only` restricts to beats where the author actually filed a manifest,
which is the question "is the manifest COMPLETE?" as distinct from "is it
PRESENT?". Measured 2026-09-09 those are very different numbers, and conflating
them is what made section 3c look safe.

KNOWN LIMIT, and it bounds every number below. The `view` this reconstructs from
captured output carries `ledger_notes` and `changes_asserted` only; the live
view also carries `pressure_ticks` and whatever `_specialist_views` adds. So
this UNDERSTATES dispatch: a call the engine made for a reason not reconstructed
here scores as addressed-by-nothing and is excluded rather than counted. Read
the outputs as a lower bound on today's dispatch and a directional read on the
alternative -- not as an audit.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

DIRECTOR_STEPS = ("director_interpret", "director_resolve")
NOT_CHANNEL_CONTENT = frozenset({"resolved_events", "phase_sources", "notes"})
#: Reruns of one turn can sit hours apart under the same `turn_id`, so calls are
#: bucketed by start time before being read as one beat's fan-out.
BUCKET_SECONDS = 300


def _parse(body):
    if not body:
        return None
    text = body.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1)
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return None


def _produced(parsed):
    """Did this hand return anything in its own channels?"""
    if not isinstance(parsed, dict):
        return False
    return any(v for k, v in parsed.items() if k not in NOT_CHANNEL_CONTENT)


def replay(db_path, filed_only=False):
    """Retired with the causal dispatch; the module's helpers stay, because
    other tools read captured causal steps through them."""
    raise SystemExit(
        "this replays the causal Director's ruling-keyed dispatch "
        "(`director_scopes._ruling_for`), deleted with it on 2026-09-27; "
        "run it from a checkout of an earlier commit (e.g. a8c41fde) "
        "against a copy of the database")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.environ.get("ENGINE_DB", "engine.db"))
    ap.add_argument("--filed-only", action="store_true",
                    help="only beats where the author actually filed a manifest")
    args = ap.parse_args(argv)

    if not os.path.exists(args.db):
        print("no such database: %s" % args.db, file=sys.stderr)
        return 2

    stats, lost, saved, no_manifest = replay(args.db, args.filed_only)
    if not stats["calls"]:
        print("no reconstructable specialist calls in %s" % args.db, file=sys.stderr)
        return 1

    scope = "beats where a manifest was filed" if args.filed_only else "all beats"
    print("dispatch replay -- %s" % scope)
    print("  specialist calls scored:     %5d" % stats["calls"])
    print("  of which produced content:   %5d  (%.0f%%)"
          % (stats["produced"], 100.0 * stats["produced"] / stats["calls"]))
    if not args.filed_only:
        print("  beats with NO manifest:      %5d" % no_manifest)
    print()
    print("  under categories-only dispatch:")
    print("    still dispatched:          %5d  (empty anyway: %d)"
          % (stats["kept"], stats["kept_but_empty"]))
    print("    skipped, hand was empty:   %5d   <- saved" % stats["saved"])
    print("    skipped, hand HAD content: %5d   <- FALSE NEGATIVES"
          % stats["false_negative"])
    if stats["unreconstructed"]:
        print("    addressed by something this replay cannot see: %d (excluded; see"
              " the module docstring)" % stats["unreconstructed"])
    print()
    if stats["false_negative"]:
        rate = 100.0 * stats["false_negative"] / max(stats["produced"], 1)
        print("  FAIL: %d false negatives, %.1f%% of productive calls. Each is a"
              % (stats["false_negative"], rate))
        print("  change some mind could have observed that no ledger would carry.")
        print("  by hand: %s" % dict(lost.most_common()))
        return 1
    print("  PASS: no productive call would have been skipped.")
    print("  saved by hand: %s" % dict(saved.most_common()))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    raise SystemExit(main())
