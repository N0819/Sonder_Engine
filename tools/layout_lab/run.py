"""Layout lab: a building's description -> the room designer's model writes
RELATIONS -> `world.layout_solver` places them -> JSON for the browse page.

PROTOTYPE (branch layout-solver-test, 2026-10-03). The owner: "Do a test
branch and return to me an artifact to browse the layouts it outputs."

    ENGINE_DB=<scratch db, outside the tree> python tools/layout_lab/run.py setup
    ENGINE_DB=... python tools/layout_lab/run.py run [scenario ...]
    python tools/layout_lab/render.py   # the browse page

Reads the owner's engine.db READ-ONLY for providers, settings, the shrine's
lorebook and chat 163's current engine layout; the model is the room
designer's own role (`director_rooms`).
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
OUT = Path(os.environ.get("LAYOUT_LAB_OUT", "/tmp/layout_lab"))
SRC = ROOT / "engine.db"

SYSTEM = """You lay out a building as RELATIONS. You never write a coordinate, a measurement or a size in paces: an engine computes every position, every room's size and every stair from what you say. Your job is to say WHAT is there and HOW it is arranged, faithfully to the description, and plausibly where the description is silent.

Answer with one JSON object:
{"name": "<the building>",
 "floors": [{"level": <0 the ground floor, 1 the floor above, -1 below ground>, "rooms": [ROOM, ...]}, ...],
 "grounds": [OUTDOOR, ...],
 "stairs": [{"id": "<id>", "from": "<room id>", "to": "<room id on the storey directly above or below>", "from_at": "n|e|s|w", "to_at": "n|e|s|w", "kind": "straight|spiral|ladder (only when the description says, or the stair plainly must be: a tower's stair turns)", "name": "<what the stair is>"}]}

ROOM = {"id": "<snake_case>", "name": "<its name>", "purpose": "<what it is for, one or two words: entryway, hallway, bedroom, guest room, kitchen, washroom, storage, closet, living, hall, study, shrine, meditation, attic, cellar, basement, workshop, common room ...>",
        "size": "tiny|small|medium|large|huge (optional: only when the description says how big it feels)",
        "block": "<the part of the building it is in, when the building has parts that rise separately: tower, cottage, wing, keep ...; leave out for a building that is one mass>",
        "over": "<room id on the storey below>" (on an upper storey: the room it stands over, when the description says or the building's shape makes it plain),
        "joins": [{"to": "<room id>", "side": "n|e|s|w", "order": <1, 2, ... when several share one wall, counted from its north or west end>, "kind": "door|sliding|opening|gate"}],
        "fixtures": [FIXTURE, ...]}

OUTDOOR = a ROOM whose purpose is one of: garden, yard, courtyard (open ground that wraps around the building), path (a way from a door out to the edge of the grounds), or a word for a small outdoor place (well, tree, shrine, pond, gate...); add "around": true to the ONE open area the building stands in.

FIXTURE = {"id": "<snake_case>", "name": "<what it is called here>", "kind": "<one of: bed futon nest table low_table chabudai desk writing_desk chair cushion bench sofa shelf bookshelf cabinet chest trunk wardrobe stove hearth counter sink basin bath tub toilet altar alcove tokonoma screen lantern statue well tree gate workbench barrel crate rack window_seat fireplace bar piano pillar rug -- or another word, with size>",
           "size": "tiny|small|medium|large|huge (only for a kind not in that list)",
           "at": "n|e|s|w (against that wall) | middle | corner_ne|corner_se|corner_sw|corner_nw",
           "near": "<fixture id>", "beside": "<fixture id>", "facing": "<fixture id>"}

How to read the fields:
- `side` on a join is where the OTHER room lies from THIS one: {"to": "kitchen", "side": "e"} means the kitchen is through this room's east wall. Write each join once, on either room.
- Pick one compass orientation for the whole building and keep it on every storey: decide which way the entrance faces and derive front, back, left and right from it. North on the first floor is north on the attic.
- A storey is every room on that level. An upper storey stands on the one below and may be smaller. A building whose parts rise separately -- a tower beside a cottage, a two-storey wing off a one-storey hall -- names each part as a `block`: a room stands on its own block's rooms below, never on another block's.
- A stair is not a room (unless the description makes a room of it, a stair hall). It stands inside the room at each end: `from_at` is the wall of the FROM room it stands against, `to_at` the wall of the TO room where it arrives. Both rooms are the same building seen on two storeys, so the two walls must agree with each other: a stair against the back wall below arrives at the back of the room above.
- A fixture is a THING in the room that a body could stand at, use or hide behind. A stretch of floor, a view, a smell or a quality of light is not a fixture. Doors and windows are not fixtures: a door is a join; leave windows out.
- Say only what the description gives or a real building of this kind would plainly have. Keep every room the description names, on the storey the description puts it.
"""

SCENARIOS = {
    "inn": ("The Moorland Coaching Inn",
            "A two-storey coaching inn on a moorland road, entered from the road on the south. "
            "Ground floor: a common room with a long bar along its back wall, a big stone hearth on "
            "the west wall and tables; behind it the kitchen with a range and a scullery off the kitchen; "
            "a narrow stair at the back of the common room leads up, and a cellar stair leads down to a "
            "barrel cellar. Upstairs a corridor runs the length of the building with five guest rooms off "
            "it -- three on the front, two on the back -- and the landlord's room at the east end. A stable "
            "yard lies behind the inn, reached through the kitchen."),
    "lighthouse": ("Greyrock Light",
                   "A stone lighthouse on a headland with the keeper's cottage built against its foot on "
                   "the landward (east) side. The cottage is one storey: a kitchen with a range and table, "
                   "and a small bedroom. The tower's ground floor is a store room, entered from the "
                   "cottage kitchen. Above it, reached by a stair that climbs the north wall, the oil "
                   "store; above that the watch room with a desk, a chair and a logbook shelf; and at the "
                   "very top the lamp room around the great lamp. A path runs from the cottage door down "
                   "to the landing."),
}


def _src():
    con = sqlite3.connect(f"file:{SRC}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def setup():
    """A scratch database carrying only the install's providers and settings."""
    from core import db
    db.init()
    src = _src()
    cols = [r[1] for r in src.execute("pragma table_info(providers)")]
    for row in src.execute("select * from providers"):
        db.qi(f"INSERT OR REPLACE INTO providers({','.join(cols)}) VALUES({','.join('?' * len(cols))})",
              tuple(row[c] for c in cols))
    skip = {"host_pw_hash", "host_pw_salt", "host_secret", "host_secret_hash", "host_username"}
    for k, v in src.execute("select key, value from settings"):
        if k not in skip:
            db.set_setting(k, v)
    print("scratch ready:", os.environ.get("ENGINE_DB"))


def shrine_brief():
    src = _src()
    rows = src.execute("select title, content from lore_entries where lorebook_id=17").fetchall()
    keep, seen = [], set()
    for r in rows:
        text = str(r["content"] or "")
        key = text[:120]
        if key in seen or len(text) < 200:
            continue
        if not re.search(r"floor|room|hall|garden|basement|genkan|kitchen|stair|torii|path|well|roost|shrine",
                         text, re.I):
            continue
        if re.search(r"First Contact|Doctor", str(r["title"] or "") + text[:200]):
            continue
        seen.add(key)
        keep.append(f"## {r['title'] or ''}\n{text}")
    return "The Shrine of the Golden Fox", "\n\n".join(keep)[:24000]


def current_engine_layout():
    """Chat 163's live scene drawn by the World Browser's own builders: the
    structure map for where rooms stand, `grid_view` for their fixtures."""
    from web.world_routes import grid_view, map_view
    src = _src()
    row = src.execute("select value from world where chat_id=163 and key='scene'").fetchone()
    if not row:
        return None
    scene = json.loads(row["value"])
    view = map_view(scene, [])
    anchors = {}
    for rid in scene.get("rooms") or {}:
        try:
            g = grid_view(scene, rid, [])
            anchors[rid] = {aid: {"cells": rec.get("cells") or [], "dir": rec.get("dir"),
                                  "desc": str(rec.get("desc") or "")[:140],
                                  "implicit": bool(rec.get("implicit"))}
                            for aid, rec in (g.get("anchors") or {}).items()}
        except Exception:
            anchors[rid] = {}
    rooms = scene.get("rooms") or {}
    return {"map": view, "anchors": anchors,
            "levels": {rid: (room or {}).get("level") for rid, room in rooms.items()},
            "extents": {rid: (room or {}).get("extent") for rid, room in rooms.items()},
            "sizes": {rid: (room or {}).get("size") for rid, room in rooms.items()}}


def _parse(text):
    text = str(text or "")
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1])


def run(names):
    from llm.providers import chat_complete
    from world.layout_solver import solve
    OUT.mkdir(parents=True, exist_ok=True)
    briefs = dict(SCENARIOS)
    briefs["shrine"] = shrine_brief()
    for name in names or ["shrine", "inn", "lighthouse"]:
        title, brief = briefs[name]
        t0 = time.time()
        raw = chat_complete("director_rooms", SYSTEM,
                            f"BUILDING: {title}\n\nDESCRIPTION:\n{brief}\n\nLay it out.",
                            max_tokens=16000)
        try:
            spec = _parse(raw)
        except Exception as exc:
            print(name, "unparseable:", exc, str(raw)[:400])
            continue
        layout = solve(spec).as_dict()
        record = {"scenario": name, "title": title, "brief": brief, "spec": spec, "layout": layout,
                  "model_seconds": round(time.time() - t0, 1)}
        if name == "shrine":
            record["current"] = current_engine_layout()
        (OUT / f"{name}.json").write_text(json.dumps(record, ensure_ascii=False, indent=1))
        print(f"{name}: {sum(len(f['rooms']) for f in spec.get('floors') or [])} rooms over "
              f"{len(spec.get('floors') or [])} storeys, {len(spec.get('grounds') or [])} grounds, "
              f"{len(layout['stairwells'])} stairwells, {len(layout['unplaced'])} fixtures unplaced, "
              f"{len(layout['warnings'])} warnings ({record['model_seconds']} s)")


def resolve():
    """Re-solve every saved spec with the current solver (no model call)."""
    from world.layout_solver import solve
    for path in sorted(OUT.glob("*.json")):
        record = json.loads(path.read_text())
        record["layout"] = solve(record["spec"]).as_dict()
        if record["scenario"] == "shrine":
            record["current"] = current_engine_layout()
        path.write_text(json.dumps(record, ensure_ascii=False, indent=1))
        L = record["layout"]
        print(f"{record['scenario']}: {len(L['stairwells'])} stairwells, {len(L['unplaced'])} unplaced, "
              f"{len(L['warnings'])} warnings")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "resolve":
        resolve()
    if cmd == "setup":
        setup()
    elif cmd == "run":
        run(sys.argv[2:])
