#!/usr/bin/env python3
"""Two lives in one town, with nobody watching either of them.

Every run so far has had a player in it, and the bubble has been the thing
that happens to a character who leaves them. This asks the question with the
player subtracted: a town the Writers' Room builds, two major characters in
two causality bubbles, thirty rounds each, and then each one's own perspective
and interiority rendered as a story from ONLY what that character holds.

THE DETECTOR CANNOT FIRE HERE, and that is correct rather than a limitation.
`bubble_split_decision`'s third refusal is "no reference frame": with nobody
the party answers for standing anywhere, there is no range to be outside of.
So the frames are made directly -- `perform_split(bubble=True, away_names=...)`
never needed a player, only `detect_split` did -- and each character gets one.

WHAT MAKES THE TWO STORIES HONEST. Each is rendered from that character's own
ledger and nothing else: `visible_memory_rows` under their own frame, their
own interior state, their own place graph. Neither generator is handed the
other's rows, the scene, or the run's log. If the two stories agree about
something, it is because both of them were there.

    ENGINE_DB=scratch.db python3 tools/two_lives_drive.py --rounds 30 --out DIR
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.bubble_drive import MODEL, _require_scratch, seed_providers  # noqa: E402

SCENARIO = (
    "Aldermill, a market town on the river road: a mill that grinds for six "
    "villages, a market square that fills every third morning, a smithy, an "
    "inn called the Wheel and Bushel, and a reeve who keeps the peace badly. "
    "Two hundred people live here and most of them have somewhere to be."
)

#: The two lives. Drives rather than goals, for the reason CLAUDE.md spends a
#: section on: a goal is completable and decays, and a character whose only
#: motivation was today's errand stops being a person the moment it is done.
#: They are given no reason to meet and no reason not to.
CAST = {
    "Sal Weatherby": {
        "drive": {"essence": "know how a place really works before she trusts it",
                  "expression": "asks the people nobody asks, and remembers "
                                "what they say",
                  "taboo": "being handled, or told a comfortable version"},
        "values": {"the quiet word over the official one":
                   "she will believe a stablehand over a reeve",
                   "her own errand over company":
                   "she leaves a conversation to keep an appointment, and "
                   "says so plainly rather than slipping away"},
        "traits": {"curious": 0.8, "wary": 0.4, "blunt": 0.6},
        "goal": "find out who actually decides things in Aldermill",
        "look": "A weathered woman in a carter's coat, grey at the temples.",
        "outfit": {"torso": "a carter's oiled coat", "legs": "hard trousers",
                   "feet": "scuffed boots"},
        "start": "market",
    },
    "Emory Vane": {
        "drive": {"essence": "leave a place better kept than he found it",
                  "expression": "fixes what is broken in front of him without "
                               "being asked, and resents being thanked for it",
                  "taboo": "walking past something failing"},
        "values": {"the work over the credit":
                   "he will hand a finished job to whoever is standing there",
                   "a thing done properly over a thing done now":
                   "he will refuse a bodge and say why"},
        "traits": {"dogged": 0.8, "prickly": 0.5, "exacting": 0.7},
        "goal": "get the mill race running clean before the rains",
        "look": "A short, thick-forearmed man with a tool roll under his arm.",
        "outfit": {"torso": "a leather apron over a linen shirt",
                   "legs": "canvas trousers", "feet": "clogs"},
        "start": "mill",
    },
}


def build_story(db):
    """The chat, the two lives, and a persona who never stands anywhere.

    A chat needs a persona row; this one is never placed in the scene and
    never plays a beat, which is what "without the player" means here. Because
    they are placed nowhere, `in_range_rooms` answers None for the present
    frame and no bubble could open by itself even if something asked.
    """
    from story.character_schema import default_character_data

    persona_id = db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        ("Nobody", json.dumps({
            "name": "Nobody", "appearance": "", "senses": "ordinary senses",
            "abilities": [], "public_history": "", "private_history": ""}),
         "{}"))
    cid = db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Two lives in Aldermill", SCENARIO, time.time(), persona_id))

    ids = {}
    for name, spec in CAST.items():
        sheet = default_character_data(name)
        sheet["identity"]["uid"] = name.lower().replace(" ", "_") + "_uid"
        sheet["psychology"] = {"drive": spec["drive"], "values": spec["values"],
                               "traits": spec["traits"]}
        sheet["initial_state"] = {"goals": [spec["goal"]]}
        sheet["simulation"] = {"tier": "major"}
        sheet["embodiment"] = {"visible": {"summary": spec["look"]}}
        sheet["initial_outfit"] = spec["outfit"]
        char_id = db.qi(
            "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
            (name, json.dumps(sheet), "{}", time.time()))
        db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state,sheet) "
              "VALUES(?,?,'active','{}',NULL)", (cid, char_id))
        ids[name] = char_id
    db.wset(cid, "simulation_clock", {"elapsed_seconds": 0.0})
    return cid, ids


def design_town(cid):
    """The Writers' Room builds Aldermill (`DESIGN_ROOM_PRELUDE.md` § 4)."""
    from agents.story_planner import room_town_planner, seat
    from language_runtime import story_language_scope
    from world.charter_runtime import generate_lived_location

    seat()
    started = time.time()
    built = generate_lived_location(
        cid,
        {"lore": [SCENARIO],
         "brief": "Aldermill itself: the mill and its race, the market square, "
                  "the smithy, the inn, the reeve's hall, and the people who "
                  "keep them",
         "scale": "village", "population": 40,
         "generate_history": True, "horizon_hours": 72.0},
        town_planner=room_town_planner(cid))
    return built, round(time.time() - started, 1)


def seed_scene(cid, ids):
    """Stand the two of them in the town the Room built. No player, no beat.

    THE ROOMS COME FROM `room_registry`, which is where `plant_structure`
    leaves them: one row per room, carrying the plan's own `name`, `purpose`
    and `adjacent`. Every other path into a scene is an establish, and an
    establish is a BEAT -- it wants a player whose beat it is, and the whole
    premise here is that there is not one. The registry is the engine's
    cross-frame ledger of room identity, so building the scene from it is
    reading the town rather than authoring one.

    Positions are the only thing this file writes, and they are the only
    thing it should: where two people happen to start.
    """
    from core.db import wget_for_frame, wset_for_frame

    rooms = {}
    for row in db_rows(cid):
        planned = (row["payload"] or {}).get("planned") or {}
        rooms[row["room_uid"]] = {
            "name": planned.get("name") or row["name"] or row["room_uid"],
            "desc": planned.get("purpose") or "",
            "adjacent": [e for e in (planned.get("adjacent") or [])
                         if isinstance(e, dict)],
        }
    if not rooms:
        raise SystemExit("the Room planted no rooms; nothing to stand in")
    # An edge is walkable from both ends: the plan states each from one side,
    # and a body walking back the way it came needs the other.
    for rid, room in rooms.items():
        for edge in list(room["adjacent"]):
            other = rooms.get(str(edge.get("to") or ""))
            if other is None:
                continue
            if not any(str(e.get("to")) == rid for e in other["adjacent"]):
                other["adjacent"].append({"to": rid,
                                          "barrier": edge.get("barrier") or "open"})
    # Drop edges to rooms the plant did not land, or a body walks at a wall.
    for room in rooms.values():
        room["adjacent"] = [e for e in room["adjacent"]
                            if str(e.get("to") or "") in rooms]

    # THE ROOM NAMES ITS OWN ROOMS, so a start is a WORD to look for rather
    # than an id to assume: the first run asked for `grist_mill_floor`, got
    # nothing, and stood a millwright in the town lockup. Matched against the
    # id and the name, and the best-connected hit wins so "mill" takes the
    # working floor rather than the loft off it.
    positions = {}
    taken = set()
    for name, spec in CAST.items():
        want = str(spec["start"]).casefold()
        hits = [rid for rid in sorted(rooms)
                if want in rid.casefold()
                or want in str(rooms[rid].get("name") or "").casefold()]
        hits = [r for r in hits if r not in taken] or sorted(rooms)
        hits.sort(key=lambda r: -len(rooms[r].get("adjacent") or []))
        positions[name] = hits[0]
        taken.add(hits[0])
    wset_for_frame(cid, "scene", {
        "location": "Aldermill", "time": "morning",
        "rooms": rooms, "positions": positions,
        "entities": {}, "attire": {}, "overlays": {}, "comms": {},
        "contacts": [],
    }, None)
    return rooms, positions


def db_rows(cid):
    """Every live room the plant left in the registry."""
    import json as _json

    from core.db import q

    out = []
    for row in q("SELECT room_uid, name, payload FROM room_registry "
                 "WHERE chat_id=? AND retired_turn_id IS NULL ORDER BY room_uid",
                 (cid,)):
        try:
            payload = _json.loads(row["payload"] or "{}")
        except (ValueError, TypeError):
            payload = {}
        out.append({"room_uid": row["room_uid"], "name": row["name"],
                    "payload": payload})
    return out


def open_two_bubbles(cid, ids):
    """One frame per life, made directly.

    `perform_split` never required a player -- only `detect_split` did -- so
    two calls give two sibling frames off the present, each holding one body.
    The second split runs against the scene the first one left, which is why
    each is given its own name list and the parent keeps everyone else.
    """
    from world.spatial_frames import perform_split

    frames = {}
    for turn, name in enumerate(sorted(CAST), start=1):
        frames[name] = perform_split(
            cid, None, turn, bubble=True, away_names=[name])
    return frames


def observe(cid, ids, frames):
    from core.db import wget_for_frame

    out = {}
    for name, frame_id in frames.items():
        scene = wget_for_frame(cid, "scene", frame_id, {}) or {}
        out[name] = {
            "frame": frame_id,
            "room": (scene.get("positions") or {}).get(name),
            "rooms_held": len(scene.get("rooms") or {}),
            "bodies": sorted(scene.get("positions") or {}),
        }
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rounds", type=int, default=30)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    _require_scratch(os.environ.get("ENGINE_DB", ""))
    from core import db
    from agents.offscreen_beat import run_offscreen_beat

    db.init()
    seed_providers(db, args.model)
    cid, ids = build_story(db)
    print("chat %s, model %s" % (cid, args.model), flush=True)

    print("the Room is designing Aldermill...", flush=True)
    built, secs = design_town(cid)
    print("  designed in %.1fs (built=%s)" % (secs, bool(built)), flush=True)
    rooms, positions = seed_scene(cid, ids)
    print("  %d rooms; %s" % (len(rooms), json.dumps(positions)), flush=True)

    frames = open_two_bubbles(cid, ids)
    print("  frames: %s" % json.dumps(frames), flush=True)

    log = []
    for rnd in range(args.rounds):
        for name in sorted(frames):
            started = time.time()
            error = ""
            try:
                run_offscreen_beat(cid, frames[name])
            except Exception as exc:            # noqa: BLE001 - reported
                error = "%s: %s" % (type(exc).__name__, exc)
            seen = observe(cid, ids, frames)
            log.append({"round": rnd + 1, "who": name, "error": error,
                        "seconds": round(time.time() - started, 1),
                        "where": {k: v["room"] for k, v in seen.items()}})
            print("  r%-3d %-14s %6.1fs  %s%s" % (
                rnd + 1, name, log[-1]["seconds"],
                json.dumps(log[-1]["where"]),
                "  ERR " + error[:70] if error else ""), flush=True)

    report = {"chat_id": cid, "model": args.model, "frames": frames,
              "characters": ids, "design_seconds": secs, "rounds": log,
              "final": observe(cid, ids, frames)}
    if args.out:
        os.makedirs(args.out, exist_ok=True)
        path = os.path.join(args.out, "two_lives.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, ensure_ascii=False)
        print("wrote %s" % path, flush=True)
    return report


if __name__ == "__main__":
    main()
