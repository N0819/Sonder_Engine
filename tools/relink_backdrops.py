#!/usr/bin/env python3
"""Reattach backdrops orphaned by a style-guide change.

WHY THIS EXISTS. A backdrop's cache key is a function of what reaches the image
prompt, and `genre`, `tone` and `avoid` reach it. So setting or editing a house
style mid-story genuinely moves every signature: the engine reports the pictures
you already have as absent and pays to draw them again. That is correct — a room
drawn without a genre really is a different picture — but it is not always what
the host wants, and nothing in the engine can decide that for them.

This tool is the other choice, made explicitly. It finds, for each turn, the
image that WOULD have been served under a different style (usually none at all)
and copies it to the signature the current style asks for.

WHAT IT ASSERTS, AND WHY IT IS OPT-IN. Relinking says the existing picture is
the picture this style would have produced. That is a claim about content the
engine cannot check, and it is mildly untrue by construction — the file was
drawn without the genre. Judge it per story: worth it for "the genre says
RE:Zero and the plaza still looks like the plaza", not worth it for a style
change that should visibly repaint the world.

NON-DESTRUCTIVE. It only ever COPIES, never moves or deletes, so the originals
stay exactly where they are and the operation is undone with `rm` on the new
names. It refuses to overwrite an existing file.

The database is opened READ-ONLY. Nothing here writes to `engine.db`.

    python3 tools/relink_backdrops.py 67            # dry run, prints the plan
    python3 tools/relink_backdrops.py 67 --apply    # copy the files
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backdrops  # noqa: E402


def _connect(db_path):
    return sqlite3.connect("file:%s?mode=ro" % db_path, uri=True)


def _scene_after(con, chat_id, turn_idx):
    """The scene AFTER `turn_idx`, which is checkpoint turn_idx + 1.

    Mirrors `backdrops.scene_after_turn` rather than importing it, because that
    one reaches for the live database through `db.q` and this tool must stay
    read-only. A turn with no next checkpoint (the latest one) is skipped
    instead of falling through to the live scene: it is a single turn, and
    guessing is worse than leaving it to regenerate.
    """
    row = con.execute(
        "SELECT json_extract(blob,'$.world.scene') AS scene "
        "FROM checkpoints WHERE chat_id=? AND turn_idx=?",
        (chat_id, turn_idx + 1)).fetchone()
    if not row or row[0] is None:
        return None
    scene = row[0]
    if isinstance(scene, str):
        try:
            scene = json.loads(scene)
        except ValueError:
            return None
    return scene if isinstance(scene, dict) else None


def _style_guide(con, chat_id):
    row = con.execute(
        "SELECT value FROM world WHERE chat_id=? AND key='style_guide'",
        (chat_id,)).fetchone()
    if not row:
        return {}
    try:
        return json.loads(row[0]) or {}
    except (ValueError, TypeError):
        return {}


def _player_name(con, chat_id):
    """The persona name, which is how `backdrops` finds the player's room.

    From the SHEET's `identity.name`, the same pair `app._backdrop_player` uses
    — deliberately not the denormalised `personas.name` column, which diverges
    from the sheet and would silently resolve a different room.
    """
    row = con.execute("SELECT persona_id FROM chats WHERE id=?",
                      (chat_id,)).fetchone()
    if not row:
        raise SystemExit("No chat %s" % chat_id)
    if not row[0]:
        return None
    prow = con.execute("SELECT sheet FROM personas WHERE id=?",
                       (row[0],)).fetchone()
    if not prow:
        return None
    try:
        sheet = json.loads(prow[0] or "{}")
    except ValueError:
        return None
    return ((sheet.get("identity") or {}).get("name")
            or sheet.get("name") or None)


def plan(con, chat_id, player):
    """[(turn, room, wanted_sig, source_path)] for turns that could be relinked.

    A turn is a candidate only when the CURRENT style misses and some earlier
    style hits: that is the shape of a style change orphaning a picture, and
    nothing else is touched.
    """
    guide = _style_guide(con, chat_id)
    # Candidate historical styles, most likely first. Stripping the guide
    # entirely covers the common case (a story that had no style guide when its
    # rooms were drawn); dropping `avoid` alone covers a guide that gained one.
    candidates = [{}, {k: v for k, v in guide.items() if k != "avoid"}]
    out = []
    turns = [r[0] for r in con.execute(
        "SELECT idx FROM turns WHERE chat_id=? ORDER BY idx", (chat_id,))]
    seen = set()
    for idx in turns:
        scene = _scene_after(con, chat_id, idx)
        if not scene:
            continue
        room = backdrops._room_of_player(scene, player)
        if not room:
            continue
        wanted = backdrops.visual_signature(scene, room, guide, viewer=player)
        if wanted in seen or backdrops.cached_backdrop(chat_id, wanted):
            seen.add(wanted)
            continue
        for old_style in candidates:
            if old_style == guide:
                continue
            was = backdrops.visual_signature(scene, room, old_style, viewer=player)
            source = backdrops.cached_backdrop(chat_id, was)
            if source:
                out.append((idx, room, wanted, source))
                seen.add(wanted)
                break
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("chat_id", type=int)
    ap.add_argument("--apply", action="store_true",
                    help="actually copy; without it this only prints the plan")
    ap.add_argument("--db", default=os.environ.get("ENGINE_DB", "engine.db"))
    args = ap.parse_args()

    con = _connect(args.db)
    player = _player_name(con, args.chat_id)
    if not player:
        print("No persona name for chat %s — backdrops cannot resolve a room."
              % args.chat_id)
        return 1
    steps = plan(con, args.chat_id, player)
    if not steps:
        print("Nothing to relink: every turn either has its picture already or "
              "has none under any style this tool knows to try.")
        return 0

    for idx, room, wanted, source in steps:
        dest = backdrops.backdrop_path(args.chat_id, wanted, room)
        print("t%-4d %-20s %s\n        <- %s" % (idx, room, dest, source))
        if not args.apply:
            continue
        if os.path.exists(dest):
            print("        SKIPPED, already exists")
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(source, dest)
        print("        copied")

    if not args.apply:
        print("\n%d image(s) would be relinked. Re-run with --apply to copy "
              "them. Nothing has been changed." % len(steps))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
