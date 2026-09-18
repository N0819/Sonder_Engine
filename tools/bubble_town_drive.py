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

    # WHY THE POPULATION IS NOT THE PLANNER'S, and it was meant to be.
    #
    # Measured here, 2026-09-17, three attempts:
    #   * The OPENING plan cannot make people. `opening_plan.OPENING_CAPABILITIES`
    #     is ("plan_rooms", "place_at_opening", "director_note") -- the rooms
    #     the passage needs and where each present body stands, and nothing
    #     about who else lives here. Eleven planner calls, one package, and a
    #     town with no institutions, no figures and no crowd.
    #   * Asked the ordinary way -- the host talking to the Writers' Room, with
    #     a granted mandate covering `create_people`, `author_prehistory` and
    #     `presimulate` -- the Room worked for 309 seconds and produced ONE
    #     institution with EIGHT POSTS AND ZERO BODIES. Jobs, and nobody in
    #     them.
    #   * (And before that, 0.0 seconds and an empty reply, because the planner
    #     is seated by `web/app.py` at import and a harness that never imports
    #     the app is talking to `unseated_planner`.)
    #
    # So the population comes from the engine's own generated world instead
    # (`tests/charter_worlds.small_town`), which exists for exactly this: "a
    # dozen rooms a body can be watched walking across... every charter place
    # IS a room id, so `charter_move` takes its scene branch". The town is
    # therefore ENGINE-made, not Room-made, and the finding above is the
    # honest reason. What this run measures is unaffected: the question is what
    # an absent character does among charter bodies, not who authored them.
    sys.path.insert(0, os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests"))
    from charter_worlds import small_town
    from world.charter import normalize_charter, seed_needs, seed_roster
    from world.charter_runtime import save_registry

    town = small_town()
    state = normalize_charter(json.loads(json.dumps(town)))
    # `seed_roster`/`seed_needs` take the BODIES, not the charter
    # (`tests/test_charter_authored_hours` is the working order).
    state["roster"] = seed_roster(state["bodies"])
    state["needs"] = seed_needs(state["bodies"])
    save_registry(cid, {"items": {"aldermill": {"state": state}}})
    db.wset(cid, "scene", {
        "location": "Aldermill",
        "time": "morning",
        "rooms": json.loads(json.dumps(town["scene"]["rooms"])),
        # The player in the square, the companion in the market beside it --
        # one room apart, so she is IN the beat until she walks.
        "positions": {"Corm": "square", "Sal Weatherby": "market"},
        "entities": {}, "attire": {}, "overlays": {}, "comms": {},
        "contacts": [],
    })
    print("  populated town:", json.dumps(charter_view(cid, None))[:900], flush=True)

    from tools.bubble_drive import play

    played = play(db, cid, char_id, BEATS[:args.beats])
    for beat in played:
        bubble = beat["after"]["bubble"]
        beat["charter_home"] = charter_view(cid, None)
        beat["charter_away"] = charter_view(cid, bubble) if bubble else None

    report = {"model": args.model, "chat_id": cid, "character_id": char_id,
              "town": charter_view(cid, None),
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
