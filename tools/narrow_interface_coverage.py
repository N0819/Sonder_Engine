#!/usr/bin/env python3
"""Does a narrowed model interface still carry everything real output used?

`docs/design/DESIGN_NARROW_MODEL_INTERFACE.md` proposes replacing the Director's
five per-channel specialist shapes with one flat categorized ledger entry that
code routes. The binding constraint on that reduction is the owner's: **the full
feature set has to survive it.**

"Survive" is checkable without a single API call, because `llm_capture` and
`llm_blobs` hold what the models ACTUALLY emitted across thousands of real
beats. Every (channel, field) pair that ever appeared there is a capability some
beat needed. A proposed entry shape that cannot carry one of them loses a
feature, and this says which -- weighted by how often the pair actually
occurred, so a field used on 211 beats and a field used once are not reported as
equals.

The direction matters: this can only find what a reduction DROPS. A pair absent
from the corpus is not proof the engine never needs it -- it is proof no
captured beat asked. Read a zero as "unmeasured here", never as "unused".

Usage:
    python tools/narrow_interface_coverage.py                 # against the default entry shape
    python tools/narrow_interface_coverage.py --spec x.json   # against a proposed one
    python tools/narrow_interface_coverage.py --db other.db --min 3

The spec is a JSON object: {"fields": [...], "per_category": {"contact": [...]}}
-- `fields` are carried on every entry, `per_category` adds fields only that
category's entries carry. Absent, the default is what `AssertedChange` declares
today plus the shared extras the design note's section 3 identified.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sqlite3
import sys

# What an AssertedChange entry carries today (llm/schemas.py). Kept as a literal
# rather than imported: this tool has to be runnable against a database from an
# engine at a different revision than the checkout it is run from, and importing
# the live class would silently measure the checkout instead of the corpus.
LEDGER_TODAY = (
    "category", "event_id", "subject", "change",
    "actor", "actor_part", "target", "target_part", "target_interior",
    "contact_ref", "action", "intensity", "rhythm", "detail",
    "substance", "placement",
)

# The shared extras section 3 of the design note found: fields several channels
# want that the entry does not yet carry. Adding them is the cheap half of the
# reduction; this is here so the default run reports the reduction as PROPOSED
# rather than as it stands today.
LEDGER_PROPOSED_EXTRAS = ("op", "relation", "motion", "manner", "source",
                          "source_part", "kind")

# Bookkeeping a specialist returns that is not channel content. Under the target
# design none of it survives -- resolved_events and phase_sources are the
# event-id echo the Director's own ledger makes unnecessary, and `notes` is the
# out-of-lane reporting that a hand which cannot be addressed cannot do.
NOT_CHANNEL_CONTENT = frozenset({"resolved_events", "phase_sources", "notes"})

# The channels the ledger would route into: `StateDiff`, plus `public_evidence`,
# which is step metadata the social hand owns rather than a StateDiff field.
#
# Scoping matters more than it looks. A captured response also carries the
# CHARACTER stage's own shapes -- `appraisal`, `sequence`, `active_state`,
# `mind_model_updates` -- and the Director's `dialogue_log` and `orchestration`.
# None of those are state_diff channels and none are the ledger's to carry, so
# counting them reports a reduction as losing three quarters of the engine when
# what it lost was three quarters of a corpus it was never asked about.
DELEGATED_CHANNELS = frozenset("""
positions rooms entities remove_entities remove_rooms remove_adjacent
charter_ops movement_refused conditions inventory_ops contact_ops
contact_action_ops substance_ops sensory_events following_ops stations poses
comms_ops scales containment vitals overlays attire cast_changes world_facts
introductions ratified_claims contradicted_claims location time weather
claim_dispositions consequences crowd_ops telling_ops courier_ops artifact_ops
destruction public_evidence
""".split())

# Channels that are not world CHANGES at all, and so are not the change-ledger's
# to carry. `public_evidence` is what a mind could later cite; `claim_dispositions`
# is adjudication of claims already made. Routing either through a ledger of
# "persistent physical changes this beat asserts" is a category error, not a
# reduction -- and they are 79% of the apparent event-shaped loss, so leaving
# them mis-scoped makes the design look far worse than it is.
NOT_A_CHANGE = frozenset({"public_evidence", "claim_dispositions",
                          "movement_refused"})

# Channels whose value is a map keyed by subject rather than a list of events.
# The design note calls these record-shaped: a flat entry cannot carry a whole
# record, so they reduce as a subject/field/value triple instead. Reported
# separately because "carried" means something different for them.
RECORD_SHAPED = frozenset({
    "rooms", "entities", "conditions", "attire", "poses", "stations",
    "overlays", "vitals", "containment", "scales", "time", "weather",
    "positions", "destruction",
})


def _load_spec(path):
    if not path:
        return set(LEDGER_TODAY) | set(LEDGER_PROPOSED_EXTRAS), {}
    with open(path) as fh:
        spec = json.load(fh)
    fields = set(spec.get("fields") or LEDGER_TODAY)
    per_cat = {k: set(v) for k, v in (spec.get("per_category") or {}).items()}
    return fields, per_cat


def _json_from_response(body):
    """Parse a captured response, tolerating the fence models wrap JSON in."""
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


def _walk_items(value):
    """Yield the dicts that carry a channel's fields, whatever its shape.

    A channel is a list of ops, a map keyed by subject, or a map keyed by
    subject holding a list. All three are flattened to the dicts whose keys are
    field names -- the subject keys themselves are ids, not fields, and counting
    them as fields is how an earlier pass reported every character's name as a
    field of `poses`.
    """
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                yield item
    elif isinstance(value, dict):
        for inner in value.values():
            if isinstance(inner, dict):
                yield inner
            elif isinstance(inner, list):
                for item in inner:
                    if isinstance(item, dict):
                        yield item


def observed_fields(db_path):
    """(channel, field) -> how many captured responses carried it."""
    uri = "file:%s?mode=ro" % db_path
    db = sqlite3.connect(uri, uri=True)
    try:
        blobs = dict(db.execute("select hash, body from llm_blobs"))
        rows = db.execute(
            "select role, response_hash from llm_capture "
            "where ok=1 and response_hash is not null")
        counts = collections.Counter()
        channels = collections.Counter()
        roles = collections.defaultdict(set)
        seen = 0
        for role, response_hash in rows:
            parsed = _json_from_response(blobs.get(response_hash))
            if not isinstance(parsed, dict):
                continue
            seen += 1
            scopes = [parsed]
            nested = parsed.get("state_diff")
            if isinstance(nested, dict):
                scopes.append(nested)
            for scope in scopes:
                for channel, value in scope.items():
                    if channel in NOT_CHANNEL_CONTENT:
                        continue
                    if channel not in DELEGATED_CHANNELS:
                        continue
                    if value in (None, "", [], {}):
                        continue
                    channels[channel] += 1
                    roles[channel].add(role)
                    for item in _walk_items(value):
                        for field in item:
                            counts[(channel, field)] += 1
        return counts, channels, roles, seen
    finally:
        db.close()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.environ.get("ENGINE_DB", "engine.db"),
                    help="database holding llm_capture/llm_blobs (default: $ENGINE_DB or engine.db)")
    ap.add_argument("--spec", default="",
                    help="JSON file describing the proposed entry shape")
    ap.add_argument("--min", type=int, default=1,
                    help="ignore (channel, field) pairs seen fewer than this many times")
    args = ap.parse_args(argv)

    if not os.path.exists(args.db):
        print("no such database: %s" % args.db, file=sys.stderr)
        return 2

    carried, per_category = _load_spec(args.spec)
    counts, channels, roles, seen = observed_fields(args.db)
    if not seen:
        print("no parseable captured responses in %s" % args.db, file=sys.stderr)
        return 1

    lost = collections.Counter()
    kept_weight = lost_weight = 0
    for (channel, field), n in counts.items():
        if n < args.min:
            continue
        allowed = carried | per_category.get(channel, set())
        if field in allowed:
            kept_weight += n
        else:
            lost[(channel, field)] += n
            lost_weight += n

    total = kept_weight + lost_weight
    print("corpus: %d parseable responses, %d channels, %d distinct (channel, field) pairs"
          % (seen, len(channels), len(counts)))
    print("entry shape carries %d fields%s"
          % (len(carried), " plus per-category additions" if per_category else ""))
    print("weighted coverage: %.1f%% of observed field occurrences carried, %.1f%% lost"
          % (100.0 * kept_weight / total if total else 0.0,
             100.0 * lost_weight / total if total else 0.0))

    if not lost:
        print("\nnothing observed in real output would be dropped.")
        return 0

    print("\nWOULD BE LOST (a capability some beat used and the entry cannot carry):")
    print("%-22s %-24s %7s  %s" % ("channel", "field", "beats", "shape"))
    for (channel, field), n in lost.most_common():
        shape = "record" if channel in RECORD_SHAPED else "event"
        print("%-22s %-24s %7d  %s" % (channel, field, n, shape))

    # The split that decides the design. Record-shaped losses are not an
    # argument for a wider entry -- the design answers them with a
    # subject/field/value triple, and a triple carries any field by
    # construction. What must be judged is the EVENT-shaped remainder, because
    # that is the list of fields a flat entry genuinely has to grow.
    record_lost = sum(n for (c, _f), n in lost.items() if c in RECORD_SHAPED)
    event_lost = lost_weight - record_lost
    event_total = sum(n for (c, _f), n in counts.items()
                      if c not in RECORD_SHAPED and n >= args.min)
    print("\n--- the split that decides the design ---")
    print("record-shaped losses: %d occurrences across %d fields. Not an argument for a wider"
          % (record_lost, sum(1 for (c, _f) in lost if c in RECORD_SHAPED)))
    print("  entry -- the design answers these with a subject/field/value triple, which carries")
    print("  any field by construction. A room's anchors and light need the triple, not a column.")
    print("event-shaped losses: %d of %d occurrences (%.1f%% of event traffic uncarried)."
          % (event_lost, event_total,
             100.0 * event_lost / event_total if event_total else 0.0))

    nonchange_lost = sum(n for (c, _f), n in lost.items() if c in NOT_A_CHANGE)
    if nonchange_lost:
        rest = event_lost - nonchange_lost
        print("  of that, %d (%.0f%% of the loss) is %s -- evidence and adjudication, which are"
              % (nonchange_lost, 100.0 * nonchange_lost / event_lost,
                 "/".join(sorted({c for (c, _f) in lost if c in NOT_A_CHANGE}))))
        print("  not world changes and so are not a change-ledger's to carry. Keeping their own")
        print("  shape leaves %d occurrences (%.1f%% of event traffic) genuinely uncarried."
              % (rest, 100.0 * rest / event_total if event_total else 0.0))

    to_add = collections.Counter()
    for (channel, field), n in lost.items():
        if channel not in RECORD_SHAPED:
            to_add[field] += n
    if to_add:
        print("\nFIELDS A FLAT ENTRY MUST GROW to carry every event-shaped channel observed:")
        for field, n in to_add.most_common():
            where = sorted({c for (c, f) in lost if f == field and c not in RECORD_SHAPED})
            print("  %-22s %6d beats   %s" % (field, n, ", ".join(where)))
        print("\n%d fields. Adding them takes event-shaped coverage to 100%% of what the corpus"
              % len(to_add))
        print("observed. Judge each against the naming test before adding it: a field whose")
        print("meaning needs a paragraph is a field that wants a better name.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
