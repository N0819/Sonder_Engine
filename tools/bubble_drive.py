#!/usr/bin/env python3
"""Does a character who walks away get a continuous, full-resolution life?

The causality bubble (`world/spatial_bubbles.py`,
`docs/design/DESIGN_OFFSCREEN_SUPERSEDED.md` § 3) gives a major character who
leaves the player's zone a frame of their own. This harness plays a real story
with a real model and measures three separate things, because they have three
separate answers and running them together is how the question gets fudged:

  1. DOES SHE LEAVE SEAMLESSLY?  Does the bubble open by itself, at commit,
     from an ordinary beat -- no persona attached, nothing authored, the
     player never told about a mechanism.
  2. DOES THE BUBBLE ADVANCE ON ITS OWN?  While the player goes on playing
     their own frame, does hers move? This is the question § 6 of that note
     says is a claim to measure rather than assume.
  3. CAN THE BUBBLE BE PLAYED AT FULL RESOLUTION?  Given a beat of its own,
     does her frame run the whole pipeline -- her perception, her declaration,
     the Director, a narrator -- on a scene the player is not in.

Every stage after the opening is the model's. Only `director_establish` is
authored, because building the world a story starts in is what a user does
before play begins, and two DECLARED ZONES have to exist for anyone to walk
between them.

    python3 tools/bubble_drive.py --out DIR [--beats N] [--model ID]

Writes only to a scratch database outside the tree. The OpenRouter credential
is read from the local engine database read-only and is never written into any
artefact this harness produces.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MODEL = "google/gemini-3.8-flash"
EMBEDDING_MODEL = "perplexity/pplx-embed-v1-4b"

TAP, LANE, ROAD, LANDING, YARD = (
    "tap_room", "mill_lane", "north_road", "ferry_landing", "harrow_yard")


def scene():
    """Two declared zones with a road between them.

    ZONES, NOT DISTANCE, is the whole trigger (`spatial_frames.py`'s module
    docstring): `distance:"far"` only means no edge happens to join two rooms,
    which is true of any two unmapped rooms in one building. So the opening
    declares the two locales outright -- a mill village and a harbour across
    the water -- exactly as the Director is asked to when a scene genuinely
    introduces a disconnected place.

    The road between them carries no zone of its own, which is what a road
    between two places is, and is also the case that matters: an unzoned room
    goes to BOTH frames when a split happens, so the story walks over the
    overlap rather than around it.
    """
    return {
        "location": "Millbrook and the Harrow shore",
        "time": "evening",
        "rooms": {
            TAP: {"name": "The Drowned Wheel tap room", "size": "medium",
                  "zone": "millbrook",
                  "adjacent": [{"to": LANE, "barrier": "closed_door",
                                "distance": "near"}]},
            LANE: {"name": "Mill Lane, and the ferry steps at the end of it",
                   "size": "medium", "zone": "millbrook",
                   "adjacent": [{"to": TAP, "barrier": "closed_door",
                                 "distance": "near"},
                                {"to": ROAD, "barrier": "open",
                                 "distance": "near"},
                                # THE CROSSING ITSELF. One step, because the
                                # first run of this harness spent eight beats
                                # with her agreeing to go and never going: an
                                # errand three rooms long needs somebody to
                                # walk her down it beat by beat, and on the
                                # player's own frame nobody does. That is a
                                # finding about the off-screen gap, not about
                                # the bubble, so the geography here is made
                                # short enough that the bubble's own question
                                # can be reached.
                                {"to": LANDING, "barrier": "open",
                                 "distance": "far"}]},
            ROAD: {"name": "The north road", "size": "large",
                   "adjacent": [{"to": LANE, "barrier": "open",
                                 "distance": "near"}]},
            LANDING: {"name": "Harrow ferry landing", "size": "medium",
                      "zone": "harrowmere",
                      "adjacent": [{"to": LANE, "barrier": "open",
                                    "distance": "far"},
                                   {"to": YARD, "barrier": "open",
                                    "distance": "near"}]},
            YARD: {"name": "The harbourmaster's yard", "size": "medium",
                   "zone": "harrowmere",
                   "adjacent": [{"to": LANDING, "barrier": "open",
                                 "distance": "near"}]},
        },
        "positions": {"Aleth": TAP, "Lysa Fen": TAP},
        "entities": {}, "attire": {}, "overlays": {}, "comms": {},
        "contacts": [],
    }


#: Player inputs. Ordinary things to type. The first three give her a reason
#: and an errand; the rest are the player staying put and getting on with their
#: own evening, which is the condition question 2 is asked under -- if the
#: bubble only moves when the player mentions her, it is not a life.
BEATS = [
    "I sit down across from Lysa and ask what has her looking at the door "
    "every few minutes.",
    "I tell her the harbourmaster at Harrowmere owes me an answer, and ask "
    "if she will carry my letter over and bring back whatever he says.",
    "I hand her the letter and the ferry fare. \"Tonight, if the ferryman "
    "will still take you. I'll be here when you're back.\"",
    "I walk her out to the ferry steps at the end of the lane and stand "
    "there while she goes over.",
    "I go back into the tap room and sit down by the fire.",
    "I ask the taverner whether the north road floods this time of year.",
    "I turn the day over in my head and think about what the harbourmaster "
    "will say to her.",
    "I stay by the fire and let the evening go.",
]

#: Beats for HER frame, once she has one. Written the way a player writes for
#: a character they are playing, because that is what playing her frame is.
HER_BEATS = [
    "Lysa keeps walking, and looks for the ferryman's light.",
    "Lysa finds whoever is still awake at the landing and asks after the "
    "harbourmaster.",
]


def _require_scratch(path):
    if not path:
        raise SystemExit("set ENGINE_DB to a scratch database path")
    real = os.path.realpath(path)
    tree = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if real.startswith(os.path.realpath(tree) + os.sep):
        raise SystemExit("refusing to run against a database inside the tree")
    if os.path.basename(real) in ("engine.db",):
        raise SystemExit("refusing to run against engine.db")


def openrouter_key():
    """The local install's own OpenRouter credential, read-only.

    Read from the engine database rather than taken as an argument so it never
    reaches a shell history, and never written into an artefact.
    """
    env = os.environ.get("OPENROUTER_API_KEY", "")
    if env:
        return env
    tree = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(tree, "engine.db")
    if not os.path.exists(src):
        raise SystemExit("no OPENROUTER_API_KEY and no local engine.db to read one from")
    con = sqlite3.connect("file:%s?mode=ro" % src, uri=True)
    con.row_factory = sqlite3.Row
    row = con.execute(
        "SELECT api_key FROM providers WHERE kind='openrouter' AND api_key<>'' "
        "ORDER BY id LIMIT 1").fetchone()
    con.close()
    if not row:
        raise SystemExit("no OpenRouter provider with a key in engine.db")
    return row["api_key"]


def seed_providers(db, model):
    from llm.providers import ROLES

    pid = db.qi(
        "INSERT INTO providers(name,kind,base_url,api_key,enabled) "
        "VALUES(?,?,?,?,1)",
        ("openrouter", "openrouter", "https://openrouter.ai/api/v1",
         openrouter_key()))
    models = {role: {"provider": pid, "model": model} for role in ROLES}
    models["embeddings"] = {"provider": pid, "model": EMBEDDING_MODEL}
    db.set_setting("agent_models", json.dumps(models))
    return models


def build_story(db):
    persona_id = db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        ("Aleth", json.dumps({
            "name": "Aleth",
            "appearance": "A traveller in a wet coat, too old to be on the "
                          "road in this weather.",
            "senses": "ordinary senses", "abilities": [],
            "public_history": "Nobody in Millbrook knows him.",
            "private_history": ""}), "{}"))
    cid = db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("The Harrow Letter",
         "Rain on Millbrook, and a letter that has to cross the water "
         "tonight.", time.time(), persona_id))

    sheet = {
        "identity": {"name": "Lysa Fen", "uid": "lysa_fen_uid"},
        "psychology": {
            # A DRIVE, not a goal, and the distinction is the one CLAUDE.md
            # spends a section on: a goal is completable and decays, a drive
            # cannot be satisfied and therefore survives the errand it is
            # spent on. A courier whose only motivation was the letter would
            # stop being a person the moment she delivered it.
            "drive": {"essence": "be the one who gets there when nobody else "
                                 "would",
                      "expression": "takes the crossing everyone else calls "
                                    "off, and says little about it",
                      "taboo": "being sent back with the thing undelivered"},
            "values": {"arriving over arriving unhurt":
                       "she will take the night crossing rather than wait "
                       "for a safe morning",
                       "the errand over the errand's owner":
                       "she keeps a confidence, and will not be talked out "
                       "of a delivery by the person who gave it to her"},
            "traits": {"wary": 0.5, "stubborn": 0.7, "warm": 0.4},
        },
        "initial_state": {"goals": ["earn enough to winter indoors"]},
        "simulation": {"tier": "major"},
        "embodiment": {"visible": {"summary": "A short, rope-muscled woman in "
                                              "an oiled coat, hair plastered "
                                              "flat by the rain."}},
        "initial_outfit": {"torso": "an oiled canvas coat over a wool jersey",
                           "legs": "heavy wet trousers", "feet": "laced boots"},
    }
    char_id = db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        ("Lysa Fen", json.dumps(sheet), "{}", time.time()))
    db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state,sheet) "
          "VALUES(?,?,'active','{}',NULL)", (cid, char_id))

    db.wset(cid, "scene", scene())
    db.wset(cid, "simulation_clock", {"elapsed_seconds": 0.0})
    return cid, char_id


def install_establish():
    """Author the opening and nothing else."""
    from llm import llm_quality
    from tools.story_drive import _base

    real = llm_quality.complete_validated_json

    def routed(*, role, step_key, system, payload, **kw):
        if step_key.split(":")[0] == "director_establish":
            world = scene()
            out = _base("director_establish")
            out["location"] = world["location"]
            out["time"] = world["time"]
            out["scene_description"] = (
                "Rain on Millbrook, the tap room full, and the Harrow shore "
                "an hour off across the water.")
            out["rooms"] = {
                rid: {"name": r["name"], "adjacent": r["adjacent"],
                      "size": r["size"], **({"zone": r["zone"]} if r.get("zone") else {})}
                for rid, r in world["rooms"].items()}
            out["positions"] = dict(world["positions"])
            out["entities"] = {}
            return out
        return real(role=role, step_key=step_key, system=system,
                    payload=payload, **kw)

    llm_quality.complete_validated_json = routed
    for mod in list(sys.modules.values()):
        if getattr(mod, "complete_validated_json", None) is not None \
                and mod is not llm_quality:
            mod.complete_validated_json = routed


# ------------------------------------------------------------------ measuring

def frame_rows(db, cid):
    return [dict(r) for r in db.q(
        "SELECT id,label,kind,parent_frame_id,split_turn_idx,merged_turn_idx "
        "FROM frames WHERE chat_id=? ORDER BY id", (cid,))]


def observe(db, cid, char_id):
    """Everything this question turns on, off the live rows."""
    from core.db import wget_for_frame
    from world import spatial_frames

    frames = frame_rows(db, cid)
    out = {"frames": frames, "where": {}, "turns_per_frame": {}, "bubble": None}
    ids = [None] + [f["id"] for f in frames]
    for fid in ids:
        sc = wget_for_frame(cid, "scene", fid, None)
        if isinstance(sc, dict):
            out["where"][str(fid)] = dict(sc.get("positions") or {})
        row = db.q("SELECT COUNT(*) AS n FROM turns WHERE chat_id=? AND frame_id IS ?",
                   (cid, fid), one=True)
        out["turns_per_frame"][str(fid)] = row["n"]
    for f in frames:
        if f["kind"] == "spatial" and f["merged_turn_idx"] is None \
                and spatial_frames.is_bubble_frame(cid, f["id"]):
            out["bubble"] = f["id"]
    out["turn_rows"] = [
        {"id": r["id"], "idx": r["idx"], "frame": r["frame_id"],
         "input": (r["player_input"] or "")[:40]}
        for r in db.q("SELECT id,idx,frame_id,player_input FROM turns "
                      "WHERE chat_id=? ORDER BY idx", (cid,))]
    out["memories_per_frame"] = {
        str(r["frame_id"]): r["n"] for r in db.q(
            "SELECT frame_id, COUNT(*) AS n FROM memories WHERE chat_id=? AND char_id=? "
            "GROUP BY frame_id", (cid, char_id))}
    return out


def send_her(cid, room=LANDING):
    """Put the courier across the water, as a Director that agreed would.

    WHY A HARNESS MAY DO THIS. Whether a model CHOOSES to send her is a claim
    about the prompts and the story, and it varies run to run -- measured
    three times on 2026-09-17: once she agreed and then waited for coin that
    had been handed to her (see the possession defect), once she went, once
    she stayed by the fire. The ENGINE question underneath is separate and
    deterministic: given a body out of the beat's reach, does a bubble open,
    and does it then live? This writes only the one fact the Director would
    have written -- a position -- and nothing else.
    """
    from core.db import wget_for_frame, wset_for_frame

    scene = wget_for_frame(cid, "scene", None, {}) or {}
    scene.setdefault("positions", {})["Lysa Fen"] = room
    wset_for_frame(cid, "scene", scene, None)


def play(db, cid, char_id, inputs, frame_id=None, first_idx=0, away_at=None):
    """Beats through the real pipeline, with `turn_new`'s couple redirect.

    The redirect is reproduced rather than imported because it lives in the
    route; every other line here is the engine's own.
    """
    from agents.runtime import run_pipeline
    from world import spatial_frames

    played = []
    for offset, text in enumerate(inputs):
        idx = first_idx + offset
        if away_at is not None and idx == away_at:
            send_her(cid)
        target = spatial_frames.live_couple_for(cid, frame_id)
        target = target if target is not None else frame_id
        # IDX IS CHAT-GLOBAL PLAY ORDER ACROSS EVERY FRAME, so a bubble's own
        # beat consumes one and the player's next index is not its own count.
        # Allocated the way `turn_new` allocates it -- max + 1 -- because a
        # naive counter collided the moment offscreen beats started running
        # (run 4, 2026-09-17: UNIQUE constraint failed on turns.chat_id,idx).
        last = db.q("SELECT idx FROM turns WHERE chat_id=? ORDER BY idx DESC "
                    "LIMIT 1", (cid,), one=True)
        idx = (last["idx"] + 1) if last else idx
        tid = db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
            "VALUES(?,?,?,?,?)", (cid, idx, text, time.time(), target))
        error, started = "", time.time()
        try:
            for _ in run_pipeline(cid, tid, frame_id=target):
                pass
        except Exception as exc:                # noqa: BLE001 - reported
            error = "%s: %s" % (type(exc).__name__, exc)
        # The bubble's own beats are scheduled OUT OF BAND (`commit`'s tail),
        # so a harness that measured immediately would measure the moment
        # before they ran. Drain them, then look.
        try:
            from core import jobs
            jobs.drain(timeout=600.0)
        except Exception:
            pass
        snap = observe(db, cid, char_id)
        played.append({"idx": idx, "input": text, "turn_id": tid,
                       "ran_in_frame": target, "error": error,
                       "seconds": round(time.time() - started, 1),
                       "after": snap})
        print("  beat %2d  frame %-5s %6.1fs  %s%s" % (
            idx, str(target), played[-1]["seconds"], text[:52],
            "  ERROR " + error[:80] if error else ""), flush=True)
        if snap["bubble"] is not None:
            print("           bubble=%s  where=%s" % (
                snap["bubble"], json.dumps(snap["where"])), flush=True)
    return played


def narration(db, turn_id):
    row = db.q(
        "SELECT v.content FROM variants v JOIN steps s ON s.id=v.step_id "
        "WHERE s.turn_id=? AND s.key='narrator' AND v.active=1", (turn_id,),
        one=True)
    if not row:
        return ""
    try:
        out = json.loads(row["content"]) or {}
        return out.get("prose") or out.get("text") or ""
    except (json.JSONDecodeError, TypeError, AttributeError):
        return str(row["content"])[:2000]


def step_keys(db, turn_id):
    return [r["key"] for r in db.q(
        "SELECT key FROM steps WHERE turn_id=? ORDER BY id", (turn_id,))]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="", help="where to write the artefacts")
    ap.add_argument("--beats", type=int, default=len(BEATS))
    ap.add_argument("--her-beats", type=int, default=len(HER_BEATS))
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--away-at", type=int, default=None,
                    help="put her across the water before this beat, so the "
                         "engine question can be asked without waiting for a "
                         "model to choose to send her")
    args = ap.parse_args()

    _require_scratch(os.environ.get("ENGINE_DB", ""))
    from core import db

    db.init()
    seed_providers(db, args.model)
    cid, char_id = build_story(db)
    install_establish()

    print("chat %s, model %s" % (cid, args.model), flush=True)
    print("-- the player's frame " + "-" * 40, flush=True)
    played = play(db, cid, char_id, BEATS[:args.beats], away_at=args.away_at)

    bubble = played[-1]["after"]["bubble"] if played else None
    her = []
    if bubble is not None and args.her_beats:
        print("-- her frame (%s) %s" % (bubble, "-" * 34), flush=True)
        her = play(db, cid, char_id, HER_BEATS[:args.her_beats],
                   frame_id=bubble, first_idx=len(played))

    report = {
        "model": args.model, "chat_id": cid, "character_id": char_id,
        "player_beats": played, "her_beats": her,
        "final": observe(db, cid, char_id),
        "narration": {str(b["turn_id"]): narration(db, b["turn_id"])
                      for b in played + her},
        "steps": {str(b["turn_id"]): step_keys(db, b["turn_id"])
                  for b in played + her},
    }
    if args.out:
        os.makedirs(args.out, exist_ok=True)
        path = os.path.join(args.out, "bubble_drive.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, ensure_ascii=False)
        print("wrote %s" % path, flush=True)
    return report


if __name__ == "__main__":
    main()
