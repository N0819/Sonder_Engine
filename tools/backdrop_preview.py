"""Dry-run the backdrop prompt builder over a real chat.

Generates no images and spends nothing: it prints, for every distinct room the
player has occupied, exactly the material an image prompt would be written
from — so the occupant-exclusion rule can be eyeballed on real data before any
generator is wired up.

    python3 tools/backdrop_preview.py 34
    python3 tools/backdrop_preview.py 34 --player Hinami
    ENGINE_DB=engine.test.db python3 tools/backdrop_preview.py 34

It reads and never writes, but it reads THROUGH `core.db`, whose connection is
read-write by construction (it sets `journal_mode=WAL` on open). There is no
`mode=ro` to reach from here, so point it at a copy rather than at a database
somebody is playing.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import db  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("chat_id", type=int)
    parser.add_argument("--player", default=None,
                        help="player display name as it appears in scene.positions")
    # Defaulted to an absolute path in a directory this repository was renamed
    # out of, so every default invocation read a database that no longer
    # exists. The default is the engine's own: `ENGINE_DB`, else `engine.db`
    # beside the repository root, which is what every other driver uses.
    parser.add_argument("--db", default=os.environ.get("ENGINE_DB") or "engine.db")
    args = parser.parse_args(argv)

    db.configure(args.db)
    from core.db import q  # noqa: E402
    from dressing.backdrops import (  # noqa: E402
        build_backdrop_request, scene_after_turn, _room_of_player)

    player = args.player
    if not player:
        chat = q("SELECT persona_id FROM chats WHERE id=?", (args.chat_id,),
                 one=True)
        if chat and chat["persona_id"]:
            row = q("SELECT sheet FROM personas WHERE id=?",
                    (chat["persona_id"],), one=True)
            if row:
                try:
                    sheet = json.loads(row["sheet"])
                    player = (sheet.get("identity") or {}).get("name")
                except (ValueError, TypeError):
                    pass

    turns = [r["idx"] for r in
             q("SELECT idx FROM turns WHERE chat_id=? ORDER BY idx",
               (args.chat_id,))]
    if not turns:
        return "chat %d has no turns" % args.chat_id

    print("db %s | chat %d | player %r | %d turns\n" % (
        args.db, args.chat_id, player, len(turns)))

    seen = {}
    for idx in turns:
        room = _room_of_player(scene_after_turn(args.chat_id, idx), player)
        if room and room not in seen:
            seen[room] = idx

    if not seen:
        return "could not resolve the player's room — pass --player NAME"

    for room, first_turn in seen.items():
        req = build_backdrop_request(args.chat_id, first_turn, player_name=player)
        if not req:
            continue
        print("=" * 72)
        print("%s   (first entered on turn %d)" % (req["room_name"], first_turn))
        print("  cache signature : %s" % req["signature"])
        print("  already cached  : %s" % (req["cached"] or "no"))
        print("  -- image-prompt source (occupants excluded by construction) --")
        for key, value in req["place"].items():
            text = value if isinstance(value, str) else json.dumps(value)
            print("   %-10s %s" % (key + ":", text[:300]))
        if req["flavour"]:
            print("   %-10s %s" % ("flavour:", req["flavour"][:200]))
        print()

    print("=" * 72)
    print("%d distinct rooms -> %d images to generate, then cached." % (
        len(seen), len(seen)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
