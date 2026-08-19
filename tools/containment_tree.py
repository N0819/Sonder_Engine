#!/usr/bin/env python3
"""What is aboard what, right now, and who is inside it.

Two kinds of edge hang off a location or vehicle lorebook and they answer
different questions:

  * `parent_id` children are canonical containment -- "belongs to". A ferry's
    crew log belongs to the ferry whether the ferry is at sea or in dry dock.
  * inbound `currently_within` links are live presence -- "is at, right now".
    `commit_scene_state.sync_anchored_books` rewrites them from positions at
    every commit, so a van aboard a ferry docked at a port nests three deep
    and stops nesting the moment the van drives off.

`memory.monitoring_subtree` walks both, joined against the live scene so each
anchored book also reports its interior rooms and their occupants. It is
reporting ONLY: this graph must never feed perception -- what an observer
aboard can perceive is scoped by `spatial.ambient_scope` over scene
containment, never by these links -- and printing it is exactly the use the
walk was written for and never got.

Why it matters when a turn goes wrong: presence here is DERIVED, so a
disagreement between this tree and the scene is a commit that did not run, and
it is invisible from either side alone. `CLAUDE.md`'s worked example -- two
characters conversing from different rooms for a whole beat because a declared
step into a lift never committed -- is this shape.

    python3 tools/containment_tree.py 74                 # every location book
    python3 tools/containment_tree.py 74 --book 312      # one subtree
    python3 tools/containment_tree.py 74 --json

Read-only. It never writes, but it does import the engine (the walk and the
scene decode are the engine's), so point it at a copy if the server is mid-turn
and you want a stable read: `ENGINE_DB=/path/to/copy.db`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.db import q, wget  # noqa: E402
from mind import memory  # noqa: E402

#: Book types that can hold something. A character or lore book has no
#: interior, so walking one prints a leaf and says nothing.
ROOT_BOOK_TYPES = ("location", "vehicle")


def _roots(chat_id, book_id=None):
    """The books to start a walk from.

    A book that is currently aboard something, or belongs to something, gets
    printed inside its holder -- starting a second walk at it would print the
    same ferry twice and read as two ferries.
    """
    if book_id is not None:
        return [book_id]
    ph = ",".join("?" * len(ROOT_BOOK_TYPES))
    rows = q(f"SELECT id FROM lorebooks WHERE chat_id=? "
             f"AND book_type IN ({ph}) AND parent_id IS NULL ORDER BY id",
             (chat_id, *ROOT_BOOK_TYPES))
    held = {r["source_book_id"] for r in q(
        "SELECT l.source_book_id FROM lorebook_links l "
        "JOIN lorebooks b ON b.id = l.source_book_id "
        "WHERE b.chat_id=? AND l.relation_type='currently_within'",
        (chat_id,))}
    return [r["id"] for r in rows if r["id"] not in held]


def _print(node, depth=0):
    pad = "  " * depth
    anchor = node.get("anchor_entity_id")
    print(f"{pad}{node['name']} [{node['book_type']}"
          + (f" -> {anchor}" if anchor else "") + "]")
    if node.get("rooms"):
        print(f"{pad}  rooms: {', '.join(node['rooms'])}")
    if node.get("occupants"):
        print(f"{pad}  occupants: {', '.join(node['occupants'])}")
    for child in node.get("children") or []:
        print(f"{pad}  belongs to it:")
        _print(child, depth + 2)
    for present in node.get("present") or []:
        print(f"{pad}  aboard right now:")
        _print(present, depth + 2)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("chat_id", type=int)
    parser.add_argument("--book", type=int, default=None,
                        help="one lorebook id; omit for every location book")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    scene = wget(args.chat_id, "scene", {}) or {}
    trees = [t for t in (memory.monitoring_subtree(args.chat_id, book,
                                                   scene=scene)
                         for book in _roots(args.chat_id, args.book))
             if t]
    if args.json:
        print(json.dumps(trees, indent=2, ensure_ascii=False, default=str))
        return 0
    if not trees:
        print("no location or vehicle lorebooks in chat %d" % args.chat_id,
              file=sys.stderr)
        return 0
    for tree in trees:
        _print(tree)
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
