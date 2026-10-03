"""Layout lab: one place's description -> the room designer's model SORTS what
it names, then writes RELATIONS -> `world.layout_solver` places them -> JSON
for the browse page (`render.py`).

PROTOTYPE (branch layout-solver-test, 2026-10-03). Two calls, because the
owner read the first two labs' outdoors as "throwing everything in the
lorebook together without logic" and the Genkan as a room when the lore
makes it a zone of the Main Hall: the model must first decide what each
named thing IS -- a room, a zone of a room, a fixture, an open or enclosed
stair, an outbuilding, open ground, a way, an outdoor feature, or a place
elsewhere -- before it says where anything goes.

    ENGINE_DB=<scratch db, outside the tree> python tools/layout_lab/run.py setup
    ENGINE_DB=... python tools/layout_lab/run.py run [scenario ...]
    python tools/layout_lab/run.py resolve      # re-solve saved answers, no model call

Reads the owner's engine.db READ-ONLY for providers, settings, the shrine's
own lore entries and chat 163's current engine layout; the model is the room
designer's role (`director_rooms`).
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
OUT = Path(os.environ.get("LAYOUT_LAB_OUT", "/tmp/layout_lab"))
SRC = ROOT / "engine.db"

SORT = """You read the description of ONE place and sort every thing it names by what KIND of thing it is. You do not lay anything out yet.

The kinds:
- room: a space with walls of its own, entered through a doorway or an opening.
- zone: a part of a room with no walls of its own -- a stretch of its floor where something happens or where a rule begins. It belongs to the room it is in.
- fixture: a thing in a room or a zone -- furniture, an alcove, a closet in a wall, a stove, an altar. What a room's floor, walls or ceiling are MADE of (its mats, boards, stone, paper panels) is its surface, never a fixture. Say how a fixture stands ("mount"): "floor" when it stands on the floor, against a wall or not -- and a thing built INTO a wall (an alcove, a closet, a hearth) takes floor along that wall, so it is "floor" too; "hung" only when it is fixed to a wall's face and takes no floor (a scroll, a picture); "ceiling" when it hangs from above; or in or on another fixture (a vase in an alcove, chests in a closet). List EVERY piece the description names, each its own entry even when two are named together; a thing named in the plural is several (give "count"). A room also holds what its purpose plainly requires even when the description takes it for granted -- a latrine its latrine, a bedroom its bed -- marked "implied": true.
- window: an opening in a room's wall to the outside. List every window the description gives, with the room it is in and what it faces or which wall it is on, in the description's own words.
- stair: a way between storeys. It is OPEN when it rises in the room itself, ENCLOSED when it lies behind a door in a stairwell of its own; take which from the words.
- outbuilding: a separate structure on the grounds, with a room or rooms of its own.
- area: open ground the building stands in or beside -- a garden, a yard, a courtyard.
- way: a path, approach or drive across the grounds.
- feature: a thing standing in the open -- a gate, a tree, a well, a lantern, a statue.
- elsewhere: a place the description mentions that is not part of this building or its grounds -- reached through it, seen from it, or simply somewhere else. Say what leads there.

DECIDE BY WALLS, NEVER BY NAME OR HEADING. A room has walls or a door of its own between it and the next space; a zone has none -- however it is headed, and whatever the place would be called elsewhere. When the description calls something a zone, an area or a part of a room, it is telling you it has no walls of its own: it is a zone of the room it lies in. Every room answers "own_walls" with the description's EXACT WORDS that give it walls or a door of its own -- or "" when no words do -- and "part_of": the room it lies in, for when it has none. A room whose own_walls is "" is a zone of its part_of room, and is moved there.

Every entry quotes the words it rests on ("why"). Inside any JSON string use single quotes, never double quotes -- the description's own speech included. A thing named twice is one thing. Storeys are counted from the one the entrance is on (level 0); a storey above is 1, below is -1.

Answer with one JSON object:
{"name": "<the place>",
 "storeys": [{"level": 0, "name": "<what the description calls it>", "smaller": true when the description says it is smaller}],
 "rooms": [{"id": "<snake_case>", "name": "...", "level": 0, "own_walls": "<exact words, or empty>", "part_of": "<room id, or empty>", "why": "..."}],
 "zones": [{"id", "name", "room": "<room id>", "why"}],
 "fixtures": [{"id", "name", "in": "<room, zone, outbuilding room or feature id>", "mount": "floor|hung|ceiling|in <fixture id>|on <fixture id>", "count": <how many, when several>, "implied": true|false, "why"}],
 "windows": [{"room": "<room id>", "faces": "<what it faces, or which wall>", "count": <how many>, "why"}],
 "stairs": [{"id", "name", "from": "<room id>", "to": "<room id>", "enclosed": true|false, "door": "<the door, when enclosed>", "why"}],
 "outbuildings": [{"id", "name", "rooms": ["<room id>", ...], "why"}],
 "areas": [{"id", "name", "why"}],
 "ways": [{"id", "name", "why"}],
 "features": [{"id", "name", "why"}],
 "elsewhere": [{"name", "via": "<the door, stair or way that leads there, if any>", "why"}]}
Rooms of an outbuilding go in "rooms" too, at level 0."""

RELATE = """You lay out ONE place as RELATIONS. You never write a coordinate, a measurement or a size in paces: an engine computes every position, every room's size, every stair and every distance from what you say. You are given the description and an inventory that has already sorted what the description names; keep every id from the inventory and the kind it was sorted into. Inside any JSON string use single quotes, never double quotes.

Answer with one JSON object:
{"name": "...",
 "front": "n|e|s|w -- the side the entrance faces",
 "entrance": {"room": "<the room the entrance opens into>", "zone": "<the zone at the door, if the description puts one there>", "kind": "<the door>"},
 "storeys": [{"level": <n>, "smaller": true}]  (only the storeys the inventory marks smaller),
 "blocks": [{"id": "<snake_case>", "apart": true|false, "beside": {"block": "<block id, or main>", "side": "n|e|s|w"}}],
 "rooms": [ROOM, ...],
 "stairs": [{"id", "name", "from", "to", "enclosed": true|false, "door": "<when enclosed>", "from_at": "n|e|s|w", "to_at": "n|e|s|w", "kind": "straight|l|u|spiral|ladder -- a straight flight, a quarter turn, a half turn with a landing between two flights, a spiral, a ladder; only when the description says, or the stair plainly must be"}],
 "grounds": {"areas": [{"id", "name", "kind": "garden|yard|courtyard|field", "where": "around | n|e|s|w"}],
             "ways": [{"id", "name", "from": "entrance | <way id>", "to": "<feature id, for a way that leads to one>"}],
             "features": [FEATURE, ...]},
 "elsewhere": [{"name", "via", "why"}]}

ROOM = {"id", "name", "level", "block": "<only for a room not in the main building>", "purpose": "<one or two words: entryway, hallway, bedroom, guest room, kitchen, washroom, latrine, storage, closet, living, hall, study, shrine, meditation, attic, cellar, basement, workshop, common room ...>",
        "joins": [{"to": "<room id, or the id of an area or way it opens onto>", "side": "n|e|s|w", "order": <1, 2 ... when several share one wall, counted from its north or west end>, "kind": "<the door>"}],
        "zones": [{"id", "name", "at": "n|e|s|w|middle|corner_ne|corner_se|corner_sw|corner_nw", "by": "entrance (for the zone at the entrance door)", "size": "small|medium|large"}],
        "windows": [{"id", "side": "n|e|s|w -- the wall it is in, from what it faces", "count": <how many>}],
        "fixtures": [{"id", "name", "kind": "<one of: bed futon nest table low_table chabudai desk writing_desk chair cushion bench sofa shelf bookshelf cabinet closet chest trunk wardrobe stove hearth counter sink basin bath tub toilet altar alcove tokonoma screen lantern statue well tree gate workbench barrel crate rack window_seat fireplace bar piano pillar rug boulder pond lamp -- or another word, with size>", "size": "tiny|small|medium|large|huge (only for another word)", "at": "<a wall, middle or a corner>", "in": "<zone id, when it stands in a zone>", "mount": "floor|hung|ceiling|in <fixture id>|on <fixture id> (from the inventory)", "count": <how many, when the description gives several alike>, "near"|"beside"|"facing": "<fixture or window id>"}]}
        A fixture's "size" also scales a kind from the list: a large tub is larger than a tub. "at": "walls" spreads several alike round the room's walls.

FEATURE = {"id", "name", "kind": "<a kind from the fixture list, or another word with size>", "size", "count": <how many, when there are several alike>,
           and exactly ONE placement:
           "across": "<way id>" (spans the way: a gate), or
           "flank": "<way id>" (one on each side of the way), or
           "along": "<way id>" (beside the way along its length),
           each with "end": "far|near" -- the far end is the end away from the building; or
           "by": "<id of a room, feature or way, or entrance>", or
           "side": "n|e|s|w" (on that side of the building)}

How to read the fields:
- Pick ONE compass for the whole place and keep it on every storey. Decide the front first; a person entering faces the opposite way, so with the front on the south, their left is west and their right is east; "the back" or "behind" is north.
- `side` on a join is where the OTHER room lies from THIS one: {"to": "kitchen", "side": "e"} means the kitchen is through this room's east wall. Write each join once.
- An outbuilding is a block of its own, "apart": true, beside the main building on the side the description gives (or a plausible one); its rooms join the area or way they open onto.
- A building whose parts rise separately -- a tower beside a cottage -- names each part a block, "apart": false.
- A stair stands inside the room at each end: `from_at` is the wall of the FROM room it stands against, `to_at` the wall of the TO room where it arrives; the two must agree, since both rooms are the same building seen on two storeys.
- The approach to the entrance is a way "from": "entrance". A gate on it is "across" it at its far end; things that flank it or line it say so; a thing the way leads to is its "to".
- Keep every fixture and window of the inventory, with its mount and count. A thing made of several parts (a nest of futons and quilts, a bed and its bedding) is ONE fixture whose parts are its contents; "count" is for separate things alike. A window's side follows from what it faces once the compass is fixed (the moon and sun rise in the east); a window "on the left wall" is on the left of a person walking in.
- Say only what the description gives, or what a real place of this kind plainly has. Nothing from "elsewhere" is laid out."""

SCENARIOS = {
    "inn": ("The Moorland Coaching Inn",
            "A two-storey coaching inn on a moorland road, entered from the road on the south. "
            "Ground floor: a common room with a long bar along its back wall, a big stone hearth on "
            "the west wall and tables; behind it the kitchen with a range and a scullery off the kitchen; "
            "a narrow stair at the back of the common room leads up, and behind a low door a cellar stair "
            "leads down to a barrel cellar. Upstairs a corridor runs the length of the building with five "
            "guest rooms off it -- three on the front, two on the back -- and the landlord's room at the east "
            "end. A stable yard lies behind the inn, reached through the kitchen; across the yard stands "
            "the stable, a long low building with stalls for six horses. The road runs on west to the "
            "market town of Hallow, a day's ride."),
    "lighthouse": ("Greyrock Light",
                   "A stone lighthouse on a headland with the keeper's cottage built against its foot on "
                   "the landward (east) side. The cottage is one storey: a kitchen with a range and table, "
                   "and a small bedroom. The tower's ground floor is a store room, entered from the "
                   "cottage kitchen. Above it, reached by a stair that turns up inside the tower wall, the oil "
                   "store; above that the watch room with a desk, a chair and a logbook shelf; and at the "
                   "very top the lamp room around the great lamp. A path runs from the cottage door down "
                   "to the landing stage, where the supply boat ties up."),
}

#: The shrine's OWN lore entries, in reading order: the place, its three
#: floors and basement, its grounds, and the cavern beneath it (kept so the
#: sort has an "elsewhere" to find). The entries about the realm beyond the
#: seal are not this place and are left out.
SHRINE_ENTRIES = (231, 230, 229, 228, 227, 232, 233, 225)


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
    parts = []
    for i in SHRINE_ENTRIES:
        row = src.execute("select content from lore_entries where id=?", (i,)).fetchone()
        if row:
            parts.append(str(row["content"]).strip())
    return "The Shrine of the Golden Fox", "\n\n".join(parts)


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
            "levels": {rid: (room or {}).get("level") for rid, room in rooms.items()}}


def _parse(text):
    text = str(text or "")
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1])


def _demote_wall_less(inv):
    """A room the description gives no walls of its own -- no words quoted in
    `own_walls` -- and that lies in another room is a ZONE of that room. The
    sort is asked to decide this itself; this holds it to its own answer."""
    rooms = {r.get("id"): r for r in inv.get("rooms") or () if isinstance(r, dict)}
    for rid, r in list(rooms.items()):
        parent = r.get("part_of")
        if str(r.get("own_walls") or "").strip() or parent not in rooms or parent == rid:
            continue
        inv["rooms"] = [x for x in inv["rooms"] if x.get("id") != rid]
        inv.setdefault("zones", []).append({"id": rid, "name": r.get("name"), "room": parent,
                                           "why": r.get("why"), "demoted": True})
        for f in inv.get("fixtures") or ():
            if f.get("in") == rid:
                f["in"] = rid       # still names the zone; the zone is in its parent
        for st in inv.get("stairs") or ():
            for end in ("from", "to"):
                if st.get(end) == rid:
                    st[end] = parent
    return inv


def _ask(system, user, tries=3):
    """One JSON answer; a malformed or silent one is asked again."""
    from llm.providers import chat_complete
    last = None
    for k in range(tries):
        raw = ""
        try:
            raw = chat_complete("director_rooms", system, user, max_tokens=48000)
            return _parse(raw)
        except Exception as exc:
            last = exc
            print("  retrying:", str(exc)[:120])
            if raw:
                OUT.mkdir(parents=True, exist_ok=True)
                (OUT / f"failed_{int(time.time())}_{k}.txt").write_text(str(raw))
    raise last


def run(names):
    from world.layout_solver import check, solve
    OUT.mkdir(parents=True, exist_ok=True)
    briefs = dict(SCENARIOS)
    briefs["shrine"] = shrine_brief()
    for name in names or ["shrine", "inn", "lighthouse"]:
        title, brief = briefs[name]
        t0 = time.time()
        try:
            inventory = _demote_wall_less(_ask(SORT, f"PLACE: {title}\n\nDESCRIPTION:\n{brief}\n\nSort it."))
            spec = _ask(RELATE, f"PLACE: {title}\n\nDESCRIPTION:\n{brief}\n\nINVENTORY:\n"
                        f"{json.dumps(inventory, ensure_ascii=False, indent=1)}\n\nLay it out.")
        except Exception as exc:
            print(name, "failed:", exc)
            continue
        layout = solve(spec)
        record = {"scenario": name, "title": title, "brief": brief, "inventory": inventory,
                  "spec": spec, "layout": layout.as_dict(), "breaches": check(layout),
                  "model_seconds": round(time.time() - t0, 1)}
        if name == "shrine":
            record["current"] = current_engine_layout()
        (OUT / f"{name}.json").write_text(json.dumps(record, ensure_ascii=False, indent=1))
        _report(record)


def resolve():
    """Re-solve every saved spec with the current solver (no model call)."""
    from world.layout_solver import check, solve
    for path in sorted(OUT.glob("*.json")):
        record = json.loads(path.read_text())
        layout = solve(record["spec"])
        record["layout"] = layout.as_dict()
        record["breaches"] = check(layout)
        path.write_text(json.dumps(record, ensure_ascii=False, indent=1))
        _report(record)


def _report(record):
    L = record["layout"]
    inv = record.get("inventory") or {}
    print(f"{record['scenario']}: sorted {len(inv.get('rooms') or [])} rooms, {len(inv.get('zones') or [])} zones, "
          f"{len(inv.get('outbuildings') or [])} outbuildings, {len(inv.get('features') or [])} features, "
          f"{len(inv.get('elsewhere') or [])} elsewhere; laid out {len(L['stairwells'])} stairwells, "
          f"{len(L['features'])} features, {len(L['unplaced'])} unplaced, {len(L['warnings'])} warnings, "
          f"{len(record['breaches'])} breaches")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "setup":
        setup()
    elif cmd == "run":
        run(sys.argv[2:])
    elif cmd == "resolve":
        resolve()
