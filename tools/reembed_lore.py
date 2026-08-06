"""Re-embed lore entries left behind by a retired embedding model.

WHY THIS EXISTS. `memory._cos` returns 0.0 when two vectors disagree in length.
It cannot raise -- it is called in a ranking loop over rows embedded at
different times -- and 0.0 is also the honest score for a genuinely unrelated
entry. So an entry carrying a vector from a model that has since been replaced
is indistinguishable from one that does not match the query, and it forfeits
the 0.65 weight `search_lore` gives the vector term. It still ranks on the 0.35
keyword term, which is why nothing ever looked broken: the lorebook simply
appeared to be ignored.

Measured on a live corpus that had run this way for months: 1,061 of 1,418 lore
entries carried 256-dimension vectors while the configured model emits 2,560.
One lorebook was 10 of 15 stale, and the single room a reader kept asking after
was among them.

DRY RUN BY DEFAULT. This walks a database that is somebody's ongoing fiction,
and re-embedding costs provider calls. It prints what it would do and changes
nothing until `--apply` is passed. `--limit` bounds a first real pass so the
cost of the whole migration can be estimated from a small one that actually ran.

  python3 tools/reembed_lore.py                   # count, per book, no writes
  python3 tools/reembed_lore.py --book 174        # scope to one lorebook
  python3 tools/reembed_lore.py --apply --limit 20
  python3 tools/reembed_lore.py --apply

WHAT IT DOES NOT TOUCH. Entries with no embedding at all are reported and
skipped: never embedded and embedded-by-the-wrong-model need different repairs,
and conflating them sends the fix to the wrong place. Nothing else in the row
is written -- not content, not keys, not `turn_added` -- so a failure part-way
leaves a corpus that is half re-embedded and wholly readable.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db  # noqa: E402
import memory  # noqa: E402
from db import q, qi  # noqa: E402

BATCH = 32


def engine_dimensions():
    """The width the ENGINE's own embedder produces, read from what it wrote.

    THIS TOOL INVERTED ITS OWN ANSWER WITHOUT IT. Run from a shell with no
    embedding provider configured, `embed_texts` falls back to a small local
    embedder -- 256 dimensions where the engine's provider emits 2,560 -- and
    every judgement flips: the 357 entries carrying CURRENT vectors get
    reported as the stale ones, and `--apply` would overwrite the only good
    vectors in the corpus with degraded ones. The dry run printed that
    confidently and was believed for about a minute.

    `memories.embedding_dim` is the engine's own record of what it embedded
    with, written by the configured provider over thousands of rows. If this
    process disagrees with it, this process is the one that is wrong.
    """
    row = q("SELECT embedding_dim AS dim, COUNT(*) AS n FROM memories "
            "WHERE embedding_dim IS NOT NULL "
            "GROUP BY embedding_dim ORDER BY n DESC LIMIT 1", one=True)
    return int(row["dim"]) if row and row["dim"] else None


def _report(scope_ids):
    health = memory.lore_embedding_health(scope_ids)
    print("current model emits %s dimensions" % health["current_dimensions"])
    print("lore entries in scope: %d" % health["total"])
    print("  stale (wrong dimension): %d" % health["stale"])
    print("  never embedded:          %d" % health["unembedded"])
    if health["books"]:
        print("\naffected lorebooks:")
        for book_id, counts in sorted(health["books"].items()):
            row = q("SELECT name FROM lorebooks WHERE id=?", (book_id,),
                    one=True)
            print("  book %-6s %-40s %d of %d stale" % (
                book_id, (row["name"] if row else "?")[:40],
                counts["stale"], counts["total"]))
    return health


def _stale_ids(scope_ids, live_dims):
    """Entry ids whose vector cannot be compared against the current model."""
    if scope_ids:
        placeholders = ",".join("?" * len(scope_ids))
        rows = q("SELECT id, embedding FROM lore_entries "
                 "WHERE lorebook_id IN (%s) ORDER BY id" % placeholders,
                 tuple(scope_ids))
    else:
        rows = q("SELECT id, embedding FROM lore_entries ORDER BY id")
    out = []
    for row in rows or []:
        vec = memory._vec(row["embedding"])
        if vec is not None and len(vec) != live_dims:
            out.append(row["id"])
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=os.environ.get("ENGINE_DB", "engine.db"))
    parser.add_argument("--book", type=int, action="append",
                        help="restrict to a lorebook id; repeatable")
    parser.add_argument("--limit", type=int, default=0,
                        help="stop after this many entries (0 = all)")
    parser.add_argument("--apply", action="store_true",
                        help="actually write. Without it, nothing changes.")
    args = parser.parse_args()

    db.configure(args.db)
    scope = args.book or None
    health = _report(scope)
    if not health["stale"]:
        print("\nnothing to do.")
        return 0

    live = health["current_dimensions"]
    if not live:
        print("\nno embedding provider is reachable, so the current dimension "
              "is unknown and nothing can be judged stale against it. "
              "Refusing to guess.")
        return 2

    # THE GUARD THAT MAKES THIS SAFE TO RUN. See engine_dimensions().
    engine = engine_dimensions()
    if engine is not None and engine != live:
        print("\nREFUSING: this process embeds at %d dimensions, but the "
              "engine's own rows were written at %d.\n"
              "That means this shell is not configured the way the engine is "
              "-- usually no embedding provider, falling back to the local\n"
              "one -- and every judgement above is inverted: the entries "
              "named stale are the current ones. Applying would overwrite\n"
              "the only good vectors in the corpus.\n"
              "Run this where the engine's provider is configured."
              % (live, engine))
        return 3

    targets = _stale_ids(scope, live)
    if args.limit:
        targets = targets[:args.limit]

    if not args.apply:
        print("\nDRY RUN. Would re-embed %d entries. Nothing has been "
              "written. Re-run with --apply." % len(targets))
        return 0

    print("\nre-embedding %d entries in batches of %d..." % (len(targets),
                                                             BATCH))
    done = 0
    for start in range(0, len(targets), BATCH):
        chunk = targets[start:start + BATCH]
        rows = q("SELECT id, title, keys, content FROM lore_entries "
                 "WHERE id IN (%s)" % ",".join("?" * len(chunk)), tuple(chunk))
        texts, ids = [], []
        for row in rows or []:
            # Same shape the original embedding was built from, so a re-embed
            # is a re-run and not a redefinition.
            texts.append("\n".join(x for x in (row["title"], row["keys"],
                                               row["content"]) if x))
            ids.append(row["id"])
        if not texts:
            continue
        vectors = memory.embed_texts(texts)
        for entry_id, vector in zip(ids, vectors):
            qi("UPDATE lore_entries SET embedding=? WHERE id=?",
               (vector.astype("float32").tobytes(), entry_id))
            done += 1
        print("  %d/%d" % (done, len(targets)))

    print("\ndone. Re-checking:")
    _report(scope)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
