"""How often a room's sound key is stranded with no successor (review D3).

The premise of D3 ("silence where there was sound"). A room the sound field
grades unevenly composes a `soundscape` percept and files its dedupe key in
the observer's standing ledger; the beat its one source stops the room goes
EVEN, no percept is built, and the key is simply gone. Nothing then says the
noise stopped -- there is no key left to compare against -- so the composer
has to be told the sound ceased rather than shown a missing key.

This counts the stranded beats in a stored chat and splits them by the one
question the fix turns on: was the observer still in the same ROOM. The
`env:` standing key hashes the room as its subject, so an `env:` subject the
two beats share is the same room, read without touching the scene.

Read-only: it opens the database with `mode=ro` and reads `steps`, `turns`
and `variants` only.

Usage:

    python tools/bench/stranded_soundscape_keys.py <db path> <chat id>

Measured 2026-09-08 on the sanitised descent copy (chat 117, 123 beats): 5
beats stranded a soundscape key, 2 of them with the player still in the room.
BUT ALL FIVE ARE ONE-BEAT EVENTS, not standing sounds -- turn 115's "deck
slab" crash and its like -- so every one of them is a key minted by the
beat's own noise and gone the next beat, which is precisely the false
positive the `ceased` trigger must not fire on. The true count of STANDING
sounds stranded in this corpus is ZERO. So this tool measures how often the
question comes up, not how often the fix helps: the corpus that motivated D3
contains no instance the feature would have served, and the case for it is
the generator in `tests/test_sound_that_stopped.py` rather than anything on
disk here.
"""
from __future__ import annotations

import json
import sqlite3
import sys


def _state(content):
    """(soundscape keys, env subjects) from one perception step's player
    ledger. Both empty where the step stored none."""
    data = json.loads(content)
    keys = ((data.get("composer_ledger") or {}).get("player") or {}).get(
        "standing") or []
    sound = {k for k in keys if str(k).startswith("soundscape:")}
    env = {":".join(str(k).split(":")[:2]) for k in keys
           if str(k).startswith("env:")}
    return sound, env


def main(path, chat_id, stage="perception_outcome"):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT t.idx, v.content FROM steps s "
        "JOIN turns t ON t.id = s.turn_id "
        "JOIN variants v ON v.step_id = s.id AND v.active = 1 "
        "WHERE t.chat_id = ? AND s.key = ? ORDER BY t.idx",
        (int(chat_id), stage)).fetchall()
    print(f"{stage} steps: {len(rows)}")

    prev, stranded, same_room = None, 0, 0
    for row in rows:
        try:
            cur = _state(row["content"])
        except (TypeError, ValueError):
            continue
        if prev and prev[0] and not cur[0]:
            held = bool(prev[1] & cur[1])
            stranded += 1
            same_room += int(held)
            print(f"  turn {row['idx']}: sound key stranded; "
                  f"same room = {held}")
        prev = cur
    print(f"stranded: {stranded}; still in the room: {same_room}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(*sys.argv[1:4])
