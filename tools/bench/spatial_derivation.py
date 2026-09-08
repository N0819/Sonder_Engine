"""What one stage's spatial derivation costs on a real stored scene (review C12).

The finding: `visual_level_between` runs 5-9x per (observer, body) per stage,
`effective_station` has 15 callers and `effective_anchors` 21, and the light
and sound fields serialise the whole scene into their cache key on every
lookup, hit or miss. None of those derivations depends on anything but the
scene object, so a stage pays for the same answer many times over.

This measures each of them separately, in the multiplicity a stage actually
asks for, so a change can be shown to give the same answer faster.

Run it against a copy of a story database (never the live one):

    ENGINE_DB=/path/to/copy.db \
      .venv/bin/python tools/bench/spatial_derivation.py --chat 117

or straight off a scene blob already on disk:

    .venv/bin/python tools/bench/spatial_derivation.py --scene tmp/scene.json

Measured 2026-09-07 on chat 117's 38-room, 22-body descent scene, three runs
each -- before the C12 read pass: sight 0.78-1.10 s, stations 0.004-0.005 s,
anchors 0.030-0.033 s, fields 0.46-0.48 s, total 1.27-1.61 s. After: sight
0.082-0.094 s, stations 0.003-0.004 s, anchors 0.015-0.017 s, fields
0.11-0.15 s, total 0.21-0.27 s. Every derived answer was byte-identical
across the change, composed views included.
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

#: How many times one stage asks each derivation for the same pair. Not a cap
#: on anything -- it is the multiplicity the review counted at the call sites
#: (composer.py:512/1056/1820, perception.py:861/1783/1902/3670/4000/5358),
#: reproduced here so the bench measures a stage rather than a single call.
SIGHT_ASKS_PER_PAIR = 6
STATION_ASKS_PER_BODY = 15


def _load_scene(args):
    if args.scene:
        with open(args.scene, encoding="utf-8") as fh:
            return json.load(fh)
    from core import db
    db.configure(os.environ["ENGINE_DB"])
    return db.wget(args.chat, "scene") or {}


def _timed(scene, label, fn):
    """One section, timed inside one read pass -- the shape a composer region
    runs in (`agents/perception.py`'s `_composer_*`). Falls back to no pass
    where `world/scene_memo.py` does not exist, so the same script measures a
    tree from before review C12."""
    try:
        from world.scene_memo import scene_read_pass
    except ImportError:
        import contextlib
        scene_read_pass = lambda _sc: contextlib.nullcontext()   # noqa: E731
    start = time.perf_counter()
    with scene_read_pass(scene):
        fn()
    elapsed = time.perf_counter() - start
    print("%-10s %8.3f s" % (label, elapsed))
    return elapsed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chat", type=int, default=117)
    ap.add_argument("--scene", help="a scene JSON blob instead of a database")
    args = ap.parse_args()
    scene = _load_scene(args)

    from world.spatial import (anchor_cells, effective_anchors,
                               effective_station, light_field, sound_field,
                               visual_level_between)

    rooms = sorted((scene.get("rooms") or {}).keys())
    bodies = sorted((scene.get("positions") or {}).keys())
    print("rooms %d  bodies %d" % (len(rooms), len(bodies)))

    def sight():
        for _ in range(SIGHT_ASKS_PER_PAIR):
            for observer in bodies:
                for target in bodies:
                    if observer != target:
                        visual_level_between(scene, observer, target)

    def stations():
        for _ in range(STATION_ASKS_PER_BODY):
            for body in bodies:
                effective_station(scene, body)

    def anchors():
        for _ in range(SIGHT_ASKS_PER_PAIR):
            for room in rooms:
                effective_anchors(scene, room)
                anchor_cells(scene, room)

    def fields():
        for _ in range(SIGHT_ASKS_PER_PAIR):
            for room in rooms:
                light_field(scene, room)
            for body in bodies:
                sound_field(scene, body, turn_idx=3)

    total = 0.0
    for label, fn in (("sight", sight), ("stations", stations),
                      ("anchors", anchors), ("fields", fields)):
        total += _timed(scene, label, fn)
    print("%-10s %8.3f s" % ("total", total))


if __name__ == "__main__":
    main()
