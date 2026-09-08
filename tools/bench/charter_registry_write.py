"""What one Charter registry save costs, stage by stage (review C1).

The locked commit lands the registry ONCE (`charter_runtime.registry_session`,
flushed by `persist.commit`), so the whole per-beat registry bill is: parse the
stored row, normalize it, mint under the story's identity reservation,
reduce to the stored split shape, dump, write. This measures each stage
against a REAL stored registry, read-only, and checks that the split shape's
bytes are identical whether the split copies the person stores or shares them.

Run it against a copy of a database (never a live one -- it only reads, but
the point is to be sure):

    .venv/bin/python tools/bench/charter_registry_write.py \
        --db /path/to/copy.db --chat 114

``--bytes`` inflates the registry by replicating its institutions until the
stored row reaches roughly that many bytes, so a small town can be measured
at the size of a large one (the review's case was 41 MB / 307 bodies).
"""
import argparse
import copy
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))


def _best(fn, rounds):
    best, out = None, None
    for _ in range(rounds):
        started = time.perf_counter()
        out = fn()
        spent = time.perf_counter() - started
        best = spent if best is None else min(best, spent)
    return best, out


def _inflate(stored, target_bytes):
    """Replicate the institutions until the stored blob is ~target_bytes."""
    items = dict(stored.get("items") or {})
    people = dict(stored.get("people") or {})
    if not items:
        return stored
    size = len(json.dumps(stored))
    copies = max(1, int(round(target_bytes / max(1, size))) - 1)
    for n in range(copies):
        for key, item in list((stored.get("items") or {}).items()):
            items["%s~%d" % (key, n)] = copy.deepcopy(item)
        for pid, person in list((stored.get("people") or {}).items()):
            charter, _, body = str(pid).partition("/")
            people["%s~%d/%s" % (charter, n, body)] = copy.deepcopy(person)
    return {"version": stored.get("version"), "items": items, "people": people}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="database copy to read")
    parser.add_argument("--chat", type=int, required=True)
    parser.add_argument("--bytes", type=int, default=0,
                        help="inflate the registry to about this many bytes")
    parser.add_argument("--rounds", type=int, default=3)
    args = parser.parse_args(argv)

    os.environ["ENGINE_DB"] = args.db
    from core import db
    db.configure(args.db)
    from story.naming import story_identity_reservation
    from world import charter_runtime as cr

    row = db.q("SELECT value FROM world WHERE chat_id=? AND key=?",
               (args.chat, cr.CHARTERS_KEY), one=True)
    if not row:
        print("chat %d has no stored charter registry" % args.chat)
        return 1
    raw = row["value"]
    stored = json.loads(raw)
    if args.bytes:
        stored = _inflate(stored, args.bytes)
        raw = json.dumps(stored)
    print("stored bytes %d" % len(raw))

    t_parse, stored = _best(lambda: json.loads(raw), args.rounds)
    t_norm, joined = _best(lambda: cr.normalize_registry(stored), args.rounds)
    bodies = sum(len(i["state"].get("bodies") or {})
                 for i in joined["items"].values())
    print("institutions %d  bodies %d  unemployed %d"
          % (len(joined["items"]), bodies, len(joined["people"])))
    laws = cr._stored_naming_laws(stored)
    t_res, reservation = _best(
        lambda: story_identity_reservation(args.chat, laws), args.rounds)
    t_renorm, normalized = _best(
        lambda: cr.normalize_registry(joined, reservation), args.rounds)
    t_split_copy, copied = _best(
        lambda: cr._stored_shape(normalized), args.rounds)
    t_split_share, shared = _best(
        lambda: cr._stored_shape(normalized, copy_people=False), args.rounds)
    t_dump, dumped = _best(lambda: json.dumps(shared), args.rounds)

    same = json.dumps(copied, sort_keys=True) == json.dumps(shared,
                                                            sort_keys=True)
    print("json.loads            %6.3fs" % t_parse)
    print("normalize (from disk) %6.3fs" % t_norm)
    print("reservation           %6.3fs" % t_res)
    print("normalize (at flush)  %6.3fs" % t_renorm)
    print("_stored_shape copying %6.3fs" % t_split_copy)
    print("_stored_shape sharing %6.3fs" % t_split_share)
    print("json.dumps            %6.3fs  (%d bytes)" % (t_dump, len(dumped)))
    print("save total, copying   %6.3fs"
          % (t_renorm + t_res + t_split_copy + t_dump))
    print("save total, sharing   %6.3fs"
          % (t_renorm + t_res + t_split_share + t_dump))
    print("split shape identical:", same)
    return 0 if same else 2


if __name__ == "__main__":
    raise SystemExit(main())
