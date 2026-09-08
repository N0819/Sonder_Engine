#!/usr/bin/env python3
"""What one turn's `room_registry` reads cost (review item C16).

A normal turn asks the plan the same question about nineteen times -- the
Director's payload builders, the room slice, the region readers and four
commit domains -- and before C16 every one of them re-ran
``SELECT ... FROM room_registry WHERE chat_id=? AND retired_turn_id IS NULL``
and re-parsed every row's ``payload`` JSON. This replays that sequence
against a stored story and reports the scan count and the wall clock, so the
saving (and its absence, on a story with no plan) is measurable rather than
argued.

Run it against a COPY of a database, never a live one -- it only reads, but
the readers it drives are the ones a commit calls::

    python tools/bench/room_registry_scan.py <db path> <chat id> [repeats]

The sequence below is the per-turn call graph as of 2026-09-07; each line
names the site it stands for, so a reader can check it has not drifted.
"""
import copy
import json
import os
import sys
import time


def _sequence(cid, scene):
    """One turn's registry questions, in call-site order."""
    from world import regions, structure

    # agents/director.py:561 -- the rooms the player's line names
    structure.planned_rooms_named_in(cid, "the market square and the lane")
    # agents/director.py:581,584 -- every planned room's brief
    ids = sorted(structure.planned_room_ids(cid))
    structure.planned_room_brief(cid, scene, ids)
    # agents/director.py:621 -- the plan's edges by id
    structure.planned_topology(cid)
    # agents/director_movement.py:180,199 -- the beat's brief and the index
    structure.planned_room_brief(cid, scene, ids[:4])
    structure.planned_room_index(cid, scene)
    # story/room_slice.py:272,466 -- the slice's topology and briefs
    structure.planned_topology(cid)
    structure.planned_room_brief(cid, scene, ids[:4])
    # world/regions.py:317,475 and world/region_events.py:162,179
    regions.planned_structure_of(cid)
    structure.planned_topology(cid)
    structure.planned_topology(cid)
    structure.planned_room_ids(cid)
    # story/room_frontier.py:94
    structure.planned_topology(cid)
    # persist/commit_scene_state.py:1634,1985,1992,1993
    structure.planned_room_ids(cid)
    structure.protect_planned_edges(cid, copy.deepcopy(scene))
    structure.prepare_frontier_expansion(cid, copy.deepcopy(scene))
    structure.materialize_planned_fringe(cid, copy.deepcopy(scene))
    # persist/commit_room_registry.py:229,546
    structure.planned_room_spellings(cid)
    structure.planned_room_ids(cid)


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    path, cid = argv[1], int(argv[2])
    repeats = int(argv[3]) if len(argv) > 3 else 5
    os.environ["ENGINE_DB"] = path
    sys.path.insert(0, os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))

    from core import db

    scans = [0]
    real_q = db.q

    def counting_q(sql, args=(), one=False):
        if "room_registry" in sql:
            scans[0] += 1
        return real_q(sql, args, one=one)

    db.q = counting_q
    try:
        scene = db.wget(cid, "scene", {}) or {}
        rows = real_q("SELECT COUNT(*) c FROM room_registry WHERE chat_id=? "
                      "AND retired_turn_id IS NULL", (cid,), one=True)
        _sequence(cid, scene)          # warm the page cache, then measure
        scans[0] = 0
        started = time.perf_counter()
        for _ in range(repeats):
            _sequence(cid, scene)
        elapsed = time.perf_counter() - started
    finally:
        db.q = real_q
    print(json.dumps({
        "db": os.path.basename(path), "chat": cid,
        "live_registry_rows": rows["c"] if rows else 0,
        "repeats": repeats,
        "registry_scans_per_turn": scans[0] / repeats,
        "ms_per_turn": round(elapsed * 1000.0 / repeats, 3),
    }, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
