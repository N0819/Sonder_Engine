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


def _author(db, name, spec):
    """One card, GENERATED and then pinned to this experiment's spec.

    NEVER HAND-BUILT. The owner's ruling, 2026-09-19: the LLM generator fills
    every field and is reliable, which is why nothing in
    `story/character_schema.py` is marked required -- the schema never needed
    a notion of a critical field, because the authoring path always produced a
    whole sheet. Hand-building is the path nobody defended.

    This harness did hand-build, and not by omission: it ASSIGNED subtrees --
    `sheet["psychology"] = {drive, values, traits}`,
    `sheet["embodiment"] = {"visible": ...}` -- which deletes every sibling
    key. Three 60-beat runs were driven by cards carrying
    `psychology.stress_profile: null` and no `coping`, `self_model`,
    `learning`, `capacity`, `senses` or `interoception` at all. `stress.load`
    then read 0.0 on every beat of every run and was written up as an ENGINE
    failure to accumulate stress. It was this function.

    So: generate from a brief, then overlay only what the experiment must fix
    (the drive, the values, the goal, the look), with `update` and never
    assignment. Reading the result back and diffing it against
    `default_character_data` is how a missing subtree is caught next time.
    """
    from story.importers import generate_character
    from story.character_schema import (character_name,
                                        normalized_character_from_text)

    brief = (
        "%s. %s Appearance: %s. They live in Aldermill, a river market town: "
        "a mill that grinds for six villages, a market square, a smithy, the "
        "Wheel and Bushel inn, and a reeve who keeps the peace badly."
        % (name, spec["drive"]["essence"].capitalize() + ".", spec["look"]))
    # `generate_character` returns (id, sheet) -- it writes the row itself.
    char_id, generated = generate_character(brief)
    sheet = normalized_character_from_text(json.dumps(generated))
    sheet.setdefault("identity", {})["uid"] = \
        name.lower().replace(" ", "_") + "_uid"
    sheet["identity"]["name"] = name
    # UPDATE, NEVER ASSIGN: the generated siblings are the whole point.
    sheet.setdefault("psychology", {}).update(
        {"drive": spec["drive"], "values": spec["values"],
         "traits": spec["traits"]})
    sheet.setdefault("initial_state", {})["goals"] = [spec["goal"]]
    sheet.setdefault("simulation", {})["tier"] = "major"
    sheet.setdefault("embodiment", {}).setdefault("visible", {})["summary"] = \
        spec["look"]
    sheet["initial_outfit"] = spec["outfit"]

    missing = [k for k in ("stress_profile", "coping", "self_model",
                           "learning", "capacity")
               if not (sheet.get("psychology") or {}).get(k)]
    if missing:
        print("  WARNING %s: psychology missing %s" % (name, ", ".join(missing)),
              flush=True)
    with db.transaction():
        db.q("UPDATE characters SET name=?, sheet=? WHERE id=?",
             (name, json.dumps(sheet, ensure_ascii=False), char_id))
    print("  authored %-16s psychology=%d embodiment=%d keys" % (
        name, len(sheet.get("psychology") or {}),
        len(sheet.get("embodiment") or {})), flush=True)
    return char_id


def build_story(db):
    """The chat, the two lives, and a persona who never stands anywhere.

    A chat needs a persona row; this one is never placed in the scene and
    never plays a beat, which is what "without the player" means here. Because
    they are placed nowhere, `in_range_rooms` answers None for the present
    frame and no bubble could open by itself even if something asked.
    """
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
        char_id = _author(db, name, spec)
        db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state,sheet) "
              "VALUES(?,?,'active','{}',NULL)", (cid, char_id))
        ids[name] = char_id
    db.wset(cid, "simulation_clock", {"elapsed_seconds": 0.0})
    return cid, ids


def design_town(cid, attempts=3):
    """The Writers' Room builds Aldermill (`DESIGN_ROOM_PRELUDE.md` § 4).

    RETRIED, BECAUSE THE ENGINE RAISES SO THAT A CALLER CAN. `run_location_plan`
    ends with `ValueError: the Writers' Room did not submit a location plan`
    and says why in its own docstring -- "the caller is a location generation,
    which already has a failure path that keeps the story and offers a retry,
    and falling back to the one-shot would be keeping alive the thing this
    replaces". The app honours that. THIS FILE DID NOT, and it is mine: two
    launches died on 2026-09-20 with 11 rooms/3 institutions and 13 rooms/1
    institution already drafted, each throwing away a ~250s design over a
    Room that stopped one call short of submitting.

    Only that failure is retried. A provider error is not: an HTTP 402 for
    credit, or a rate limit, will not be cured by asking again and retrying it
    spends the little that is left.
    """
    from agents.story_planner import room_town_planner, seat
    from language_runtime import story_language_scope
    from world.charter_runtime import generate_lived_location

    seat()
    started = time.time()
    last = None
    for attempt in range(1, max(1, int(attempts)) + 1):
        try:
            return _design_once(cid)
        except ValueError as exc:
            if "did not submit" not in str(exc):
                raise
            last = exc
            print("  the Room did not submit (attempt %d/%d): %s"
                  % (attempt, attempts, str(exc)[:110]), flush=True)
    raise last


def _design_once(cid):
    """One design pass, timed. Separated so the retry above reads as a retry."""
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
            # THE FIXTURES THE PLAN FURNISHED THE ROOM WITH. A fourth
            # allowlist on one rail: `close_plan` seeds a room anchor from
            # every post that stands at one, `plant_structure` stores them
            # and `skeleton_rooms` reads them back -- and this dict, the last
            # hop before anybody stands anywhere, quietly dropped them.
            # Measured (v10, 2026-09-20): 13 of 15 planned rooms carried
            # anchors in the registry and 0 of 15 did in the scene.
            **({"anchors": dict(planned["anchors"])}
               if isinstance(planned.get("anchors"), dict) and planned["anchors"]
               else {}),
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

    def _clock(frame_id):
        # The two lives share one town (`db.ERA_WORLD_KEYS`), which runs at
        # the later of their clocks, so the one furthest behind goes first --
        # the order `offscreen_beat.live_bubbles` gives the engine's own.
        from core.db import wget_for_frame
        from world.mechanics import clock_elapsed
        return clock_elapsed(
            wget_for_frame(cid, "simulation_clock", frame_id, {}) or {})

    for rnd in range(args.rounds):
        for name in sorted(frames, key=lambda n: (_clock(frames[n]), n)):
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
