#!/usr/bin/env python3
"""What does a companion get up to in a town, while the player is elsewhere?

`tools/bubble_drive.py` asks whether a causality bubble OPENS and RUNS. This
asks the question after that one: with the bubble running, in a town the Story
Planner built and Charter populates, **what does an absent major character
actually do -- and who does she do it with?**

That last clause is the whole point. A bubble's beat composes her perception
from her own frame, and the people in a town are CHARTER bodies: unpromoted
figures the institutions stand at their posts. If they are not in her frame she
is alone in an empty village, which is what a split used to do to her -- it
seeded eight frame-scoped keys and every one was about the PARTY, so
`charters`, `crowds`, `couriers` and `artifacts` were dropped on the floor
(fixed 2026-09-17; `spatial_frames.perform_split`).

THE PLAYER DOES CHORES, deliberately. Every beat below is the player's own
errand and none of them is about her: the measurement is what she does when
nobody is looking at her and nothing in the beat is addressed to her. A story
where the player keeps asking after her would measure the prompt's politeness.

    python3 tools/bubble_town_drive.py --out DIR [--beats N]

Writes only to a scratch database outside the tree. The OpenRouter credential
is read from the local engine database read-only and never written into any
artefact this harness produces.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.bubble_drive import (MODEL, _require_scratch,  # noqa: E402
                                observe, seed_providers)

SCENARIO = (
    "Aldermill, a market town on the river road: a mill that grinds for six "
    "villages, a market square that fills every third morning, a smithy, an "
    "inn called the Wheel and Bushel, and a reeve who keeps the peace badly. "
    "Two hundred people live here and most of them have somewhere to be. "
    "Sal Weatherby has walked in with a traveller she met on the road, and "
    "she has business of her own in the town before the day is out."
)

#: The player's own errands, and not one of them is about her. Each is an
#: ordinary thing to type on a day in a town.
BEATS = [
    "I stand in the market square and get my bearings.",
    "I find the miller and ask what he charges to grind a sack.",
    "I take my boots to the smith and ask him to put a new nail in the sole.",
    "I sit on the wall outside the smithy and wait while he works.",
    "I go to the inn and order something to eat.",
    "I ask the innkeeper what the road east is like this time of year.",
    "I count out what I have left and work out what I can afford.",
    "I walk back across the square to see if the grain stalls are still up.",
    "I fill my flask at the pump and sit down in the sun.",
    "I watch the town go about its afternoon.",
]


def build_story(db):
    from story.character_schema import default_character_data

    persona_id = db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        ("Corm", json.dumps({
            "name": "Corm",
            "appearance": "A traveller with a bad pair of boots and a light purse.",
            "senses": "ordinary senses", "abilities": [],
            "public_history": "Nobody in Aldermill knows him.",
            "private_history": ""}), "{}"))
    cid = db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Aldermill", SCENARIO, time.time(), persona_id))

    sheet = default_character_data("Sal Weatherby")
    sheet["identity"]["uid"] = "sal_weatherby_uid"
    sheet["psychology"] = {
        # A DRIVE, not a goal: a goal is completable and decays, and a
        # companion whose only motivation was today's errand would stop being
        # a person the moment it was done. CLAUDE.md spends a section on this.
        "drive": {"essence": "know how a place really works before she trusts it",
                  "expression": "asks the people nobody asks, and remembers "
                                "what they say",
                  "taboo": "being handled, or told a comfortable version"},
        "values": {"the quiet word over the official one":
                   "she will believe a stablehand over a reeve",
                   "her own errand over company":
                   "she will leave a conversation to keep an appointment, and "
                   "say so plainly rather than slip away"},
        "traits": {"curious": 0.8, "wary": 0.4, "blunt": 0.6},
    }
    sheet["initial_state"] = {"goals": ["settle what she is owed at the mill"]}
    sheet["simulation"] = {"tier": "major"}
    sheet["embodiment"] = {"visible": {"summary":
        "A weathered woman in a carter's coat, grey at the temples."}}
    sheet["initial_outfit"] = {"torso": "a carter's oiled coat",
                               "legs": "hard-wearing trousers",
                               "feet": "scuffed boots"}
    char_id = db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        ("Sal Weatherby", json.dumps(sheet), "{}", time.time()))
    db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state,sheet) "
          "VALUES(?,?,'active','{}',NULL)", (cid, char_id))
    db.wset(cid, "simulation_clock", {"elapsed_seconds": 0.0})
    return cid, char_id


def charter_view(cid, frame_id):
    """Who Charter stands in this frame's rooms, and what the town is."""
    from agents.common import present_charter_figures
    from core.db import wget_for_frame

    scene = wget_for_frame(cid, "scene", frame_id, {}) or {}
    rooms = list((scene.get("rooms") or {}).keys())
    try:
        figures = present_charter_figures(cid, scene, rooms, frame_id=frame_id)
    except Exception as exc:                       # noqa: BLE001 - reported
        return {"error": str(exc)[:200]}
    charters = wget_for_frame(cid, "charters", frame_id, {}) or {}
    return {
        "institutions": sorted((charters.get("items") or charters or {}).keys())[:12],
        "figures": [{"name": f.get("name"), "room": f.get("room"),
                     "role": f.get("role")} for f in (figures or [])][:20],
        "crowds": sorted((wget_for_frame(cid, "crowds", frame_id, {}) or {}).keys())[:8],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="")
    ap.add_argument("--beats", type=int, default=len(BEATS))
    ap.add_argument("--model", default=MODEL)
    args = ap.parse_args()

    _require_scratch(os.environ.get("ENGINE_DB", ""))
    from core import db

    db.init()
    seed_providers(db, args.model)
    cid, char_id = build_story(db)

    # THE ROOM DESIGNS THE TOWN, which is what `room-plans-the-opening`
    # rebuilt and what this branch exists to measure. `run_location_plan`
    # drafts the map, each institution and the prehistory across multiple tool
    # calls, closes the draft against the real `close_plan`, and submits --
    # replacing the single `utility` call that produced, on `writers-room`,
    # one institution with eight posts and zero bodies in 309 seconds.
    #
    # It is also §7's owed measurement: nothing here had run against a real
    # launch, so the wall clock and the round-trip count below are the first
    # of them.
    from agents.story_planner import room_town_planner, seat
    from language_runtime import story_language_scope
    from story import room_conversation as room
    from world.charter_runtime import generate_lived_location

    seat()
    assert room.planner_seated(), "the planner must be seated to answer"

    print("the Room is designing Aldermill...", flush=True)
    started = time.time()
    built = None
    try:
        with story_language_scope(cid):
            built = generate_lived_location(
                cid,
                {"lore": [SCENARIO],
                 "brief": "Aldermill itself: the mill, the market square, the "
                          "smithy, the inn, and the people who keep them",
                 "scale": "village", "population": 40,
                 "generate_history": True, "horizon_hours": 72.0},
                town_planner=room_town_planner(cid))
    except Exception as exc:                       # noqa: BLE001 - reported
        print("  the design FAILED: %s: %s" % (type(exc).__name__,
                                               str(exc)[:200]), flush=True)
    design_seconds = round(time.time() - started, 1)
    print("  designed in %.1fs (built=%s)" % (design_seconds, bool(built)),
          flush=True)
    print("  town:", json.dumps(charter_view(cid, None))[:900], flush=True)

    # THE STORY PLANNER PLANS THE GROUND the story opens on, which is the
    # half of "a town made by the planner" that works today.
    from agents.story_planner import run_opening_plan

    print("planning the opening...", flush=True)
    started = time.time()
    plan = run_opening_plan(cid, None, passage=SCENARIO + "\n\n" + BEATS[0])
    opening = {k: v for k, v in (plan or {}).items()
               if k in ("calls", "steps", "notes", "error")}
    print("  planned in %.1fs: %s calls, %s published, %s" % (
        time.time() - started, (plan or {}).get("calls"),
        len((plan or {}).get("published") or []),
        ((plan or {}).get("error") or "")[:120]), flush=True)

    from tools.bubble_drive import play

    played = play(db, cid, char_id, BEATS[:args.beats])
    for beat in played:
        bubble = beat["after"]["bubble"]
        beat["charter_home"] = charter_view(cid, None)
        beat["charter_away"] = charter_view(cid, bubble) if bubble else None

    report = {"model": args.model, "chat_id": cid, "character_id": char_id,
              "town": charter_view(cid, None),
              "design_seconds": design_seconds,
              "opening_plan": opening,
              "beats": played, "final": observe(db, cid, char_id)}
    if args.out:
        os.makedirs(args.out, exist_ok=True)
        path = os.path.join(args.out, "bubble_town.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, ensure_ascii=False)
        print("wrote %s" % path, flush=True)
    return report


if __name__ == "__main__":
    main()
