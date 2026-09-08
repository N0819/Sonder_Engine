"""What `positions` holds, and what the one body predicate says about it.

Review 2026-09-07 A56 and its rework. `scene.positions` is the map of WHERE,
so every fixture, tool, docked vehicle and derived vehicle zone is in it
beside the bodies -- and four readers used to ask "is this a body" in four
spellings, two of which disagreed. This counts, on a real stored scene, how
many position keys each tier of `spatial.scene_names_body` answers for, and
prints the ones the readers used to fight over.

Run it against a COPY of a db (never the live one):

    ENGINE_DB=/path/to/copy.db .venv/bin/python \\
        tools/bench/body_predicate_on_positions.py 117

Measured 2026-09-08 on the bench copies: chat 117's live scene held 22
position keys, 2 bodies, 19 things with an entity record and 1 (`iron_bung`)
with none; chat 114's held 3 keys, 2 bodies and one vehicle.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from core import db
from world.spatial import scene_names_body


def report(chat_id):
    rows = db.q("SELECT value FROM world WHERE chat_id=? AND key='scene'",
                (chat_id,))
    if not rows:
        print("chat %s has no scene" % chat_id)
        return
    scene = json.loads(rows[0]["value"])
    positions = scene.get("positions") or {}
    entities = scene.get("entities") or {}
    bodies, recorded_things, unrecorded = [], [], []
    for name in positions:
        if scene_names_body(scene, name):
            (bodies if name in entities or _ledgered(scene, name)
             else unrecorded).append(name)
        else:
            recorded_things.append(name)
    print("chat %s: %d position keys" % (chat_id, len(positions)))
    print("  bodies (a body ledger names them): %d %s"
          % (len(bodies), bodies))
    print("  things (the scene records what they are): %d %s"
          % (len(recorded_things), recorded_things))
    print("  neither -- counted as bodies, tier 3: %d %s"
          % (len(unrecorded), unrecorded))


def _ledgered(scene, name):
    folded = str(name).strip().casefold()
    return any(any(str(k).strip().casefold() == folded for k in
                   (scene.get(table) or {}))
               for table in ("attire", "scales", "vitals", "overlays",
                             "poses"))


if __name__ == "__main__":
    db.configure(os.environ.get("ENGINE_DB") or "engine.db")
    for arg in sys.argv[1:] or ["1"]:
        report(int(arg))
