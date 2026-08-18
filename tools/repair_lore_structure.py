#!/usr/bin/env python3
"""Backfill title and the knowledge fields on an already-imported lorebook.

A book imported before `lore_structure` landed has none of what its titles
encoded: no `title`, no `knowledge_tag`, no `knowledge_range`, no
`knowledge_locations`, and a flat `importance`. The text is fine; the structure
was thrown away at the door, because `comment` was never read.

Re-importing would fix it and would also mint a NEW book, orphaning every
`chat_lorebooks` link, every `entry_uid` a story has already cited, and any
edit made since. So this repairs in place instead, matching each stored entry
back to its source by content prefix -- the same handle the importer uses, and
for the same reason: the rewrite splits entries, so position cannot be trusted.

ONLY EVER FILLS WHAT IS EMPTY. An entry that already carries a title or a
knowledge tag is left exactly as it is: a host who has curated one is a better
authority than this heuristic, and the whole value here is recovering what was
lost rather than overwriting what was chosen.

    python3 tools/repair_lore_structure.py 183 "/path/to/book.json"
    python3 tools/repair_lore_structure.py 183 "/path/to/book.json" --apply
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from story.lore_structure import derive_knowledge, parse_structure  # noqa: E402


_WORD_RE = re.compile(r"[a-z0-9']{3,}")


def _tokens(text):
    return frozenset(_WORD_RE.findall(str(text or "").casefold()))


def _similarity(a, b):
    left, right = _tokens(a), _tokens(b)
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def source_records(source_path):
    raw = json.load(open(source_path, encoding="utf-8"))
    entries = raw.get("entries") if isinstance(raw, dict) else raw
    if isinstance(entries, dict):
        entries = list(entries.values())
    return [r for r in parse_structure(entries or [])
            if str(r.get("content") or "").strip()]


def facts_for(record):
    tag, rng, locations = derive_knowledge(record)
    return {
        "title": record.get("title") or None,
        "knowledge_tag": tag,
        "knowledge_range": rng,
        "knowledge_locations": (json.dumps(locations, ensure_ascii=False)
                                if locations else None),
        "importance": 0.9 if record.get("constant") else None,
        "parent_title": (record.get("parent") or "").strip() or None,
    }


def align(rows, records, window=4, floor=0.25):
    """Row -> source record, by MONOTONIC SEQUENCE ALIGNMENT.

    Content-prefix matching was tried first and reached 32 of 310. It cannot
    work here: these books were imported with `reinterpret=True`, so the model
    rewrote the prose (stripping `<world_setting>` tags, reflowing sentences)
    and invented keys where the source had none. Key-set matching did no better
    at 12.9%.

    What DID survive is order. The importer walks the source in order and
    appends in order, and so does the batch rewrite, so stored row n tracks
    source entry n -- drifting only where the rewrite SPLIT one entry into two
    (310 rows from 292 sources with content). So the pointer only ever moves
    forward, looks a few ahead for the best token overlap, and is left in place
    after a match so consecutive rows may share a source: which is exactly what
    a split is, and both halves inherit the same structural facts correctly.

    Measured on book 183: 85.8% aligned at or above the floor, median
    similarity 1.00. Anything below the floor is reported unmatched and left
    alone rather than guessed at.
    """
    cursor = 0
    for row in rows:
        # One step BACK so a split can re-match the record its first half took,
        # and `window` forward so a source entry the rewrite dropped entirely
        # can be skipped past. The cursor then advances past what was matched,
        # which is what stops one record absorbing every remaining row --
        # measured: without the advance this matched 112 rows, with it 245.
        low = max(0, cursor - 1)
        best_index, best_score = cursor, 0.0
        for index in range(low, min(cursor + window, len(records))):
            score = _similarity(row["content"], records[index]["content"])
            if score > best_score:
                best_index, best_score = index, score
        if best_score < floor:
            yield row, None, best_score
            continue
        cursor = best_index + 1
        yield row, records[best_index], best_score


def plan(con, book_id, records):
    """[(row_id, {column: value})] for rows with something recoverable."""
    con.row_factory = sqlite3.Row
    rows = list(con.execute(
        "SELECT * FROM lore_entries WHERE lorebook_id=? ORDER BY id", (book_id,)))
    steps, unmatched = [], 0
    titles, parents, existing = {}, {}, {}
    for row in rows:
        existing[row["id"]] = row["relations"]
    for row, record, _score in align(rows, records):
        if record is None:
            unmatched += 1
            continue
        meta = facts_for(record)
        titles[row["id"]] = meta.get("title")
        parents[row["id"]] = meta.get("parent_title")
        updates = {}
        for column in ("title", "knowledge_tag", "knowledge_range",
                       "knowledge_locations", "importance"):
            value = meta.get(column)
            if value is None:
                continue
            current = row[column]
            # Never overwrite. `importance` is the one that needs care: 0.5 is
            # the DEFAULT rather than a choice, so raising it off the default
            # is a fill, while anything else the host set is theirs.
            if column == "importance":
                if current in (None, 0.5) and value != current:
                    updates[column] = value
            elif current in (None, "", "[]", "{}"):
                updates[column] = value
        if updates:
            steps.append((row["id"], updates))

    # THE `[>]` TREE, resolved in a second pass now that every row's title is
    # known. `relations.refines_entry_ids` already means exactly this, so the
    # hierarchy needs no new column and moves no entry between books. Only an
    # entry with no relations of its own is linked -- a `refines` or
    # `contradicts` a host or the engine already recorded is a real claim about
    # this book, and outranks a structural guess.
    by_title = {}
    for row_id, title in titles.items():
        if title and title not in by_title:
            by_title[title] = row_id
    for row_id, parent_title in parents.items():
        parent_id = by_title.get(parent_title or "")
        if not parent_id or parent_id == row_id:
            continue
        current = existing.get(row_id)
        if current not in (None, "", "{}", "[]"):
            continue
        merged = dict(dict(steps).get(row_id) or {})
        merged["relations"] = json.dumps({"supersedes_entry_id": None,
                                          "refines_entry_ids": [parent_id],
                                          "contradicts_entry_ids": []})
        steps = [(rid, upd) for rid, upd in steps if rid != row_id]
        steps.append((row_id, merged))
    return steps, unmatched


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("book_id", type=int)
    ap.add_argument("source", help="the original SillyTavern lorebook JSON")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--db", default=os.environ.get("ENGINE_DB", "engine.db"))
    args = ap.parse_args()

    records = source_records(args.source)
    mode = "" if args.apply else "?mode=ro"
    con = sqlite3.connect("file:%s%s" % (args.db, mode), uri=True)
    steps, unmatched = plan(con, args.book_id, records)

    total = con.execute("SELECT COUNT(*) FROM lore_entries WHERE lorebook_id=?",
                        (args.book_id,)).fetchone()[0]
    filled = {}
    for _rid, updates in steps:
        for column in updates:
            filled[column] = filled.get(column, 0) + 1
    print(f"book {args.book_id}: {total} entries, {len(steps)} repairable, "
          f"{unmatched} unmatched against the source")
    for column, n in sorted(filled.items()):
        print(f"    {column:<22} {n}")

    if not args.apply:
        print("\nDry run. Nothing written. Re-run with --apply.")
        return 0

    with con:
        for row_id, updates in steps:
            sets = ", ".join(f"{c}=?" for c in updates)
            con.execute(f"UPDATE lore_entries SET {sets} WHERE id=?",
                        (*updates.values(), row_id))
    print(f"\nApplied to {len(steps)} entries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
