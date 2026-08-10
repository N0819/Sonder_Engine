#!/usr/bin/env python3
"""Read a captured run's stage payloads the way a model would, and count the
shapes a READER would trip on.

Every drive in this directory can dump what each stage was actually handed:

    ENGINE_DB=scratch.db python3 tools/quest_drive.py --out DIR --capture CAP
    python3 tools/payload_scan.py CAP

The schemas have already run by the time a payload is captured, and passed.
So this looks for what a schema cannot: context that reads as populated and is
not, and context that contradicts itself. Three defects came out of it in one
sitting, none of which failed a test --

  * a trait map written `{"wary": 0.7}` lost its name, so 42 character
    payloads carried a psychology whose `traits` list was non-empty and named
    nobody (`character_schema._as_profile_list`);
  * the capture itself shared one filename between the foreground turn and the
    off-screen daemon threads, so 209 of 505 payloads were overwritten before
    anyone read them and five were left unparseable;
  * `{"wary": 0.7}` and the empty trait it became are the same class as the
    engine's `persona_warnings` scar: an empty field fails silently, and a
    skeleton with the right shape reads as an answer.

The two counts that are NOT defects are kept and explained rather than
suppressed, because a scan whose output is all noise gets ignored and a scan
that hides its known-benign rows cannot be checked:

  * `adjacency edge with a null destination` is the information-barrier fold
    at `agents/perception.py`. An adjacency to a room the observer cannot see
    keeps its BARRIER and loses its destination -- an open doorway into
    darkness is a thing you can see without being able to see where it goes.
    The scan proves it is a fold rather than an invention by checking that the
    payload is a strict subset of the world.
  * `somebody standing in a room the payload does not carry` is
    `agents/common._contextual_rooms`, a token-cost trim. Positions are
    deliberately whole while rooms are windowed, so an off-screen villain's
    room id arrives as a label with no description. Deterministic spatial
    checks read the unfiltered scene, never this.
"""

from __future__ import annotations

import argparse
import collections
import json
import os

#: Words that look like an answer and are not. A model reads the key, believes
#: the engine had something, and writes as though it were told.
PLACEHOLDER = {"unknown", "n/a", "none", "null", "undefined", "todo", "tbd",
               "unnamed", "unnamed ability", "string", "..."}

#: Slots whose whole job is to say something.
PROSE_SLOTS = ("summary", "description", "desc", "expression", "text",
               "prose", "resolved_event", "standing", "notes")

#: Counted and explained rather than reported as defects. See the module
#: docstring for why each one is the design rather than a bug.
BENIGN = {
    "adjacency edge with a null destination":
        "perception's leak-fold: barrier kept, destination withheld",
    "somebody standing in a room the payload does not carry":
        "_contextual_rooms trims rooms for cost; positions stay whole",
}


def world_size(cap_dir):
    """How many rooms the world has, taken as the widest any payload carried.

    The establish payload carries them all, so this is exact for a captured
    run. It matters because a payload holding EVERY room has hidden nothing,
    which makes a blinded edge in one an invention rather than a fold. Without
    it the check degenerates into a guess about how many rooms counts as a lot.
    """
    widest = 0
    for fn in sorted(os.listdir(cap_dir)):
        if not fn.endswith(".payload.json"):
            continue
        try:
            blob = json.load(open(os.path.join(cap_dir, fn)))
        except ValueError:
            continue
        scene = blob.get("scene") if isinstance(blob.get("scene"), dict) else blob
        widest = max(widest, len(scene.get("rooms") or {}))
    return widest


def scan(cap_dir):
    whole_world = world_size(cap_dir)
    rows = collections.Counter()
    examples = collections.defaultdict(list)
    by_stage = collections.Counter()
    folds, inventions = 0, 0

    def note(kind, where):
        rows[kind] += 1
        if len(examples[kind]) < 3:
            examples[kind].append(where)

    files = sorted(f for f in os.listdir(cap_dir)
                   if f.endswith(".payload.json"))
    for fn in files:
        by_stage[fn.split("_", 1)[-1].replace(".payload.json", "").split(".")[0]] += 1
        try:
            blob = json.load(open(os.path.join(cap_dir, fn)))
        except ValueError as exc:
            note("payload is not valid JSON", "%s (%s)" % (fn, exc))
            continue

        scene = blob.get("scene") if isinstance(blob.get("scene"), dict) else blob
        world_rooms = set((scene.get("rooms") or {}))

        def walk(node, trail):
            where = "%s %s" % (fn, ".".join(trail))
            if isinstance(node, dict):
                for key, value in node.items():
                    if key in ("name", "room", "speaker", "id", "uid") \
                            and value in ("", None):
                        note("an identity slot left empty", where + "." + key)
                    if key in PROSE_SLOTS and isinstance(value, str) \
                            and value.strip().casefold() in PLACEHOLDER:
                        note("a placeholder word standing in for prose",
                             "%s.%s=%s" % (where, key, value))
                    if key == "adjacent" and isinstance(value, list):
                        for edge in value:
                            if isinstance(edge, dict) and not edge.get("to"):
                                note("adjacency edge with a null destination",
                                     where)
                    walk(value, trail + [str(key)])
            elif isinstance(node, list):
                for i, item in enumerate(node):
                    walk(item, trail + [str(i)])

        walk(blob, [])

        # A null edge is a FOLD when the payload is a strict subset of the
        # world, and an INVENTION when the payload already carried every room
        # and blinded an edge anyway -- there was nothing left to hide.
        if world_rooms:
            blind = sum(
                1 for room in world_rooms
                for edge in ((scene.get("rooms") or {}).get(room) or {}).get("adjacent") or []
                if isinstance(edge, dict) and not edge.get("to"))
            if blind:
                if len(world_rooms) >= whole_world:
                    inventions += blind
                else:
                    folds += blind

        positions = scene.get("positions") or {}
        if world_rooms and isinstance(positions, dict):
            for who, room in positions.items():
                if room and str(room) not in world_rooms:
                    note("somebody standing in a room the payload does not carry",
                         "%s %s -> %s" % (fn, who, room))

    return files, by_stage, rows, examples, folds, inventions


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("capture_dir", help="a --capture directory from any drive")
    args = ap.parse_args()

    files, by_stage, rows, examples, folds, inventions = scan(args.capture_dir)

    print("=== %d payloads, by stage ===" % len(files))
    for stage, n in by_stage.most_common():
        print("%5d  %s" % (n, stage))

    real = [(k, n) for k, n in rows.most_common() if k not in BENIGN]
    print()
    print("=== what a reader would trip on ===")
    if not real:
        print("  nothing")
    for kind, n in real:
        print("%5d  %s" % (n, kind))
        for example in examples[kind]:
            print("         e.g. %s" % example)

    print()
    print("=== counted, and by design ===")
    for kind, why in BENIGN.items():
        print("%5d  %s" % (rows.get(kind, 0), kind))
        print("         %s" % why)
    print()
    print("  blinded edges that were folds     : %d" % folds)
    print("  blinded edges that were inventions: %d   (must be 0)" % inventions)
    return 1 if (real or inventions) else 0


if __name__ == "__main__":
    raise SystemExit(main())
