#!/usr/bin/env python3
"""A fifty-turn quest, played through the real pipeline, with a real villain.

The point is not the story. It is that the villain acts through the SAME
machinery the design argues for, rather than being narrated at: Maelor is
dormant and off-screen for most of these fifty beats, and what he does reaches
the hero as consequences that fired on a clock, as reports carried by people
who walked, and as rumours that lost a detail every time they were retold. If
the illusion works, the hero should meet the results of his plans before
meeting him -- and should sometimes be told things about him that are not
quite true.

Everything a model would produce is authored here. That is the honest limit:
this cannot tell you whether a model WOULD write these beats, only that the
engine carries them when it does. What it can show is whether the off-screen
world produces a coherent story rather than a pile of fired mechanisms.

Writes only to its own scratch database and refuses to start against anything
that looks like the author's.

    ENGINE_DB=/path/to/quest.db python3 tools/quest_drive.py --out DIR
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.offscreen_drive import _require_scratch  # noqa: E402
from tools.story_drive import Author, _base  # noqa: E402

# The Vale, west to east: the village the hero starts in, the road, the
# siege-town, and the citadel where Maelor has been all along. Sizes are real
# because crowd density derives from them.
WELL, MARKET, ROAD, TOWN, GATE, KEEP = (
    "village_well", "market_square", "old_road", "siege_town",
    "citadel_gate", "ashen_keep")

ROOMS = {
    WELL:   ("The Village Well",  "small",  [MARKET]),
    MARKET: ("Market Square",     "huge",   [WELL, ROAD]),
    ROAD:   ("The Old Road",      "large",  [MARKET, TOWN]),
    TOWN:   ("Siege Town",        "large",  [ROAD, GATE]),
    GATE:   ("The Citadel Gate",  "small",  [TOWN, KEEP]),
    KEEP:   ("The Ashen Keep",    "medium", [GATE]),
}


def scene():
    rooms = {}
    for rid, (name, size, adj) in ROOMS.items():
        rooms[rid] = {"name": name, "size": size,
                      "adjacent": [{"to": t, "barrier": "open"} for t in adj]}
    return {
        "location": "The Vale",
        "time": "morning",
        "rooms": rooms,
        "positions": {"Corin": WELL, "Sera": WELL, "Bryn": WELL,
                      "Wren": WELL, "Maelor": KEEP},
        "entities": {},
    }


def build_story(db):
    """The Vale, its people, and a villain who is somewhere else.

    Maelor is DORMANT from the first beat and opted into the agent rung. That
    is the whole experiment: an antagonist the player cannot see, who owns
    plans, learns things, and acts on a clock.
    """
    persona_id = db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        ("Corin", json.dumps({
            "name": "Corin",
            "appearance": "A young smith's apprentice with a borrowed sword.",
            "senses": "ordinary senses", "abilities": [],
            "public_history": "Nobody outside the Vale has heard of him.",
            "private_history": ""}), "{}"))
    cid = db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("The Ashen Quest",
         "Maelor the Ashen is sealing the wells of the Vale one by one. "
         "Corin sets out to stop him.", time.time(), persona_id))

    def cast(name, uid, status, drive, agent=False, tier="major"):
        sheet = {
            "identity": {"name": name, "uid": uid},
            "psychology": {"drive": {"essence": drive},
                           "traits": {"wary": 0.6}},
            "simulation": {"tier": tier,
                           **({"offscreen_agent": True} if agent else {})},
        }
        char_id = db.qi(
            "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
            (name, json.dumps(sheet), "{}", time.time()))
        db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state,sheet) "
              "VALUES(?,?,?,'{}',NULL)", (cid, char_id, status))

    cast("Sera", "sera_uid", "active", "see the Vale drink again")
    cast("Bryn", "bryn_uid", "active", "outlive his own forge")
    # THE VILLAIN. Dormant from beat one, opted in, and never once co-present
    # with the hero until the end.
    cast("Maelor", "maelor_uid", "dormant",
         "hold the Vale by its throat", agent=True)
    # THE ALLY, and she is off-screen too. Wren declares what she means to do
    # on-page -- plans must be grounded in the actor's own words, so an ally
    # who never spoke could never own one -- and then goes, and works. The
    # player never sees her again; he sees what she managed and what she did
    # not. Two absent minds, acting against each other, neither of them
    # narrated.
    cast("Wren", "wren_uid", "active", "cut every thread he pulls", agent=True)

    db.wset(cid, "scene", scene())
    db.wset(cid, "simulation_clock", {"elapsed_seconds": 0.0})
    db.wset(cid, "dialogue_config",
            {"offscreen_life": "character_agent", "max_offscreen_actors": 3})
    db.wset(cid, "living_world", {
        "routine_residue": "floor", "scheduled_consequence": "floor",
        "place_obligations": "floor", "antagonist_ladder": "ceiling",
        "rumor_ledger": "floor",
    })
    return cid


# ------------------------------------------------------------------- beats

def _room_of(cid):
    from core import db
    return ((db.wget(cid, "scene", {}) or {}).get("positions") or {}).get("Corin")


def crowd_uid(cid, room=None):
    from core import db
    for crowd in db.wget(cid, "crowds", []) or []:
        if isinstance(crowd, dict) and crowd.get("uid"):
            if room is None or str(crowd.get("room_uid")) == room:
                return str(crowd["uid"])
    return ""


def report_id(payload, who=None):
    for row in ((payload or {}).get("carried_reports") or []):
        if isinstance(row, dict) and row.get("world_event_id"):
            if who is None or row.get("who") == who:
                return str(row["world_event_id"])
    return ""


class QuestAuthor(Author):
    """The quest's own opening scene.

    `Author` is shared with `tools/story_drive.py`, whose establish default
    authors a gate hall and an inner yard. Inheriting it silently opened the
    Vale in somebody else's rooms -- the committed scene carried both worlds,
    the party moved between rooms it had never been shown, and every mechanism
    that windows on "a room you have seen before" had nothing to anchor to.
    """

    def default(self, role):
        if role == "director_establish":
            world = scene()
            out = _base("director_establish")
            out["location"] = world["location"]
            out["time"] = world["time"]
            out["scene_description"] = "The Vale, and its wells going quiet."
            out["rooms"] = {
                rid: {"name": r["name"], "adjacent": r["adjacent"],
                      "size": r["size"]}
                for rid, r in world["rooms"].items()}
            out["positions"] = dict(world["positions"])
            out["entities"] = {}
            return out
        return super().default(role)


def quest(author, cid):
    """Fifty beats. The hero moves west to east; Maelor acts the whole time."""

    def R(prose, **over):
        out = author.default("director_resolve")
        diff = out["state_diff"]
        for key, value in over.pop("diff", {}).items():
            diff[key] = value
        out["resolved_event"] = prose
        out.update(over)
        return out

    def skip(seconds, label, prose, **over):
        diff = dict(over.pop("diff", {}))
        diff["time"] = {"start_seconds": 0, "duration_seconds": seconds,
                        "end_seconds": seconds, "mode": "time_skip",
                        "explicit": True, "display_advance": label}
        return R(prose, diff=diff, **over)

    def go(room, prose, **over):
        diff = dict(over.pop("diff", {}))
        pos = dict(diff.get("positions") or {})
        pos["Corin"] = room
        diff["positions"] = pos
        return R(prose, diff=diff, **over)

    def curse(what, where, due, witnessed):
        """One of Maelor's workings, set running now and landing later."""
        return {"what": what, "where": where, "due_seconds": due,
                "witnessed": witnessed, "originator": "Maelor"}

    B = []                                   # (player input, resolve payload)

    # --- I. The village: something is wrong with the water --------------
    B += [
        ("I look into the well.",
         R("The water has gone the colour of ash and will not settle.")),
        ("I ask Sera how long it has been like this.",
         R("Sera says three days, and that the Fenwater went first.")),
        ("I ask who would do this.",
         R("Bryn says the name people are avoiding: Maelor, in the Ashen Keep.",
           diff={"consequences": [
               curse("the Fenwater well is sealed over with grey stone",
                     MARKET, 3600,
                     "the well cover cracked and knitted itself shut")]})),
        ("I draw a bucket and taste it.",
         R("It tastes of cold iron. Corin spits it out.")),
        ("I tell them I am going to the Keep.",
         R("Nobody argues, which is worse than arguing.")),
        ("We walk up to the market.",
         go(MARKET, "The square is full of people who have nowhere to draw water.",
            crowd_ops=[{"op": "set", "room": MARKET, "band": "a throng",
                        "composition": "villagers with empty pails",
                        "mood": "frightened"}])),
    ]
    # crowd_ops must live under state_diff; fix the last entry's shape.
    B[-1] = (B[-1][0], R(
        "The square is full of people who have nowhere to draw water.",
        diff={"positions": {"Corin": MARKET},
              "crowd_ops": [{"op": "set", "room": MARKET, "band": "a throng",
                             "composition": "villagers with empty pails",
                             "mood": "frightened"}]}))

    B += [
        ("I listen to what the crowd is saying.",
         R("Half of them blame Maelor. Half blame the village council.")),
        # Maelor's first working comes due, in the square, in front of everyone.
        ("I spend the morning helping carry water up from the river.",
         skip(3600, "the morning",
              "By noon Corin's shoulders are raw and the pails are still empty.")),
        ("I look at the well cover.",
         R("Grey stone, knitted shut, still warm.")),
        ("I ask Bryn if he can break it.",
         R("Bryn says his hammer would ring off it like a bell.")),
        ("I ask Wren what she means to do.",
         R("Wren says she will go ahead of him and break what he sets.",
           dialogue_log=[{"speaker": "Wren",
                          "text": "I'll go ahead of him and break what he sets."}],
           diff={"offscreen_plan_ops": [{
               "op": "open", "plan_id": "cut-his-threads", "actor": "Wren",
               "objective": "Break Maelor's workings before they set",
               "basis": "I'll go ahead of him and break what he sets.",
               "stages": [
                   {"stage_id": "the-road-well",
                    "trigger": {"after_seconds": 3600},
                    "effect": {
                        "what": "the well on the Old Road runs clear again",
                        "where": ROAD, "due_seconds": 0,
                        "witnessed": "the seal on the road well had been "
                                     "broken from above",
                        "originator": "Wren"}},
                   # The second stage fires much later -- and by then Maelor
                   # has learned she exists. She does not foil everything.
                   {"stage_id": "the-gate-ward",
                    "trigger": {"after_seconds": 43200},
                    "effect": {
                        "what": "the gate ward is cracked but holding",
                        "where": GATE, "due_seconds": 0,
                        "witnessed": "somebody had struck the gate ward and "
                                     "not finished the job",
                        "originator": "Wren"}}]}]})),
        ("I let her go.",
         R("Wren is gone before anyone thinks to thank her.",
           diff={"cast_changes": [{"who": "Wren", "status": "dormant",
                                   "reason": "gone east ahead of Corin"}]})),
        ("I ask Sera to scout the road east.",
         R("Sera says she will go as far as the Old Road and come back.",
           dialogue_log=[{"speaker": "Sera",
                          "text": "I'll go as far as the Old Road."}])),
    ]

    # --- II. The road: the villain is working while nobody watches ------
    B += [
        ("We take the Old Road east.",
         go(ROAD, "The road runs between dead hedges.")),
        ("I ask Sera what she saw when she scouted.",
         R("Sera describes riders on the ridge, going east, in no hurry.")),
        ("I look at the well beside the road.",
         R("It is running. Something broke the seal on it from above.")),
        ("We walk until dark.", skip(21600, "six hours",
         "The light goes out of the sky somewhere behind them.")),
        ("I sleep badly.", skip(28800, "the night",
         "Corin dreams of a well that answers when he calls into it.")),
        ("I ask what is ahead.",
         R("Bryn says Siege Town, and that it has held out longer than it should.")),
    ]

    # --- III. Siege Town: news arrives, already wrong -------------------
    B += [
        ("We come into the town.",
         go(TOWN, "Siege Town is standing, and that is the most that can be said.",
            diff={"positions": {"Corin": TOWN, "Sera": TOWN, "Bryn": TOWN},
                  "crowd_ops": [{"op": "set", "room": TOWN,
                                 "band": "a few dozen",
                                 "composition": "refugees and townsfolk",
                                 "mood": "watchful"}]})),
        # He answers being noticed by striking BEHIND the hero -- at the
        # market the party left hours ago. This is the one working nobody
        # watches land: it comes due during the wait for dark, in a room the
        # party is absent from, and the only witnesses are the crowd standing
        # in it. The return home is what collects it -- as destination
        # residue for Corin, and as talk the villagers carry with them.
        ("I ask the townsfolk what they know of Maelor.",
         R("They know a great deal, and most of it disagrees with itself.",
           diff={"consequences": [
               curse("Maelor's riders have passed through the market and "
                     "the grain stores stand empty",
                     MARKET, 3600,
                     "riders took the grain stores in the night")]})),
        # Bryn passes on what he saw at the village -- degraded by one mouth.
        ("I ask Bryn to tell them what happened to our well.",
         lambda p: R("Bryn tells the room about the well.",
                     dialogue_log=[{"speaker": "Bryn",
                                    "text": "It sealed itself while we watched."}],
                     diff={"telling_ops": [
                         {"speaker": "Bryn", "listener": "Sera",
                          "world_event_id": report_id(p, "Bryn")}]}
                     if report_id(p, "Bryn") else {})),
    ]

    # --- IV. The villain adapts, off-screen ----------------------------
    B += [
        ("I ask Sera to find a way to the citadel gate.",
         R("Sera says there is a culvert, and that it is watched.",
           dialogue_log=[{"speaker": "Sera",
                          "text": "There's a culvert. It's watched."}])),
        # Maelor's second working: he answers the town, not the hero.
        ("I ask what Maelor wants from a town this small.",
         R("Bryn says: obedience, and that he takes it one well at a time.",
           diff={"consequences": [
               curse("the town cistern has been sealed in the night",
                     TOWN, 3600,
                     "the cistern lid was fused shut from the inside"),
               # A working that finishes where MAELOR is standing. This is the
               # only legitimate way a remote antagonist enters the agent rung
               # in this script: he cannot own a plan (plans must be declared
               # on-page, and he has never been on-page) and nobody in this
               # story pays to send a rider to the Keep (couriers exist now --
               # see tools/courier_drive.py -- but a courier must still be
               # SENT by someone). He learns by witnessing his own work
               # complete -- which is honest, and is exactly the design's rule
               # that a mind adapts only after evidence reaches it.
               curse("the ward over the keep door has finished setting",
                     KEEP, 1800,
                     "the ward closed with a sound like a struck bell")]})),
        ("I wait for dark.", skip(5400, "an hour and a half",
         "The town goes quiet the way a held breath is quiet.")),
        ("I check the cistern.",
         R("It is fused shut. Nobody heard it happen.")),
        ("I tell them we are going to the gate.",
         R("Sera says she will go ahead. Bryn says he will hold the town.",
           dialogue_log=[{"speaker": "Sera",
                          "text": "I'll go ahead and watch the gate until dusk."}])),
    ]

    # The town's cistern is sealed, so the town starts leaving -- declared as
    # a HEADING rather than a `move`, which is the difference between a crowd
    # walking the graph everyone else walks and a crowd teleporting across it.
    # A heading is spent one beat after it is declared, so the press stands in
    # the town for exactly one beat of perception before it is at the gate.
    #
    # It has to name the `crowd_id` the payload showed. A `set` carrying only
    # a room and a heading does not steer the crowd standing there -- it tries
    # to MINT one, and is refused for having no composition. That refusal is
    # the design working (a crowd may only be named by a uid the engine
    # minted), and an earlier draft of this beat was rejected by it. It is
    # also the only beat in this story that gives "a crowd moved on the graph"
    # a denominator at all: every other crowd here stands still, and a crowd
    # with nowhere to be was never a chance to move.
    def let_sera_go(p):
        diff = {"cast_changes": [{"who": "Sera", "status": "dormant",
                                  "reason": "gone ahead to the gate"}]}
        for crowd in (p or {}).get("crowds") or []:
            if str(crowd.get("room")) == TOWN and crowd.get("crowd_id"):
                diff["crowd_ops"] = [{"op": "set",
                                      "crowd_id": crowd["crowd_id"],
                                      "heading": GATE}]
                break
        return R("Sera goes out through the culvert, and the town starts "
                 "moving toward the gate behind her.", diff=diff)

    let_sera_go.prose = ("Sera goes out through the culvert. Behind her the "
                         "square begins to drain toward the gate road.")

    # --- V. Separation: the party splits, and knowledge splits with it --
    B += [
        ("I let Sera go ahead.", let_sera_go),
        ("We move to the gate road.",
         go(GATE, "The Citadel Gate is a slot in the rock, and it is cold.")),
        ("I look for Sera.",
         R("No sign of her. The gate is watched by nobody Corin can see.")),
    ]

    # --- VI. What the villain did while nobody watched -----------------
    B += [
        ("I check the gate for a way through.",
         R("There is a seam in the rock that was not there yesterday.")),
        ("I put my hand on it.",
         R("Warm, and cracked across. Somebody got here first and did not "
           "finish.")),
        ("I look for another way.",
         R("The culvert Sera named runs under the gate.")),
        ("I take the culvert.",
         R("It is a tight, wet, and entirely unwatched way in.")),
        ("I come up inside.",
         go(KEEP, "The Ashen Keep is warm, and it is not empty.")),
    ]

    # --- VII. The Keep ------------------------------------------------
    B += [
        ("I look for him.",
         R("The hall is long and there is a figure at the end of it.")),
        ("I say his name.",
         R("Maelor answers without turning around.",
           diff={"cast_changes": [{"who": "Maelor", "status": "active",
                                   "reason": "met at last"}]},
           dialogue_log=[{"speaker": "Maelor",
                          "text": "You are the one from the Fenwater."}])),
        ("I ask him why the wells.",
         R("He says water is the only thing nobody can refuse to need.",
           dialogue_log=[{"speaker": "Maelor",
                          "text": "Water is the one thing nobody can refuse."}])),
        ("I tell him the Vale will not kneel.",
         R("He says the Vale has been kneeling for eleven days.")),
        ("I ask what he did with Sera.",
         R("He says he has not touched her, and Corin cannot tell if it is true.",
           dialogue_log=[{"speaker": "Maelor",
                          "text": "I have not touched your scout."}])),
        ("I draw the sword.",
         R("It is a smith's apprentice's sword and it is not enough.")),
    ]

    # --- VIII. The turn ----------------------------------------------
    B += [
        ("I go for the seam in the wall instead of for him.",
         R("Corin brings the hilt down on the warm seam. It rings.")),
        ("I hit it until it breaks.",
         R("The seal fails, and every sealed thing in the Vale fails with it.")),
        ("I look at him.",
         R("Maelor is not frightened. He is recalculating.",
           dialogue_log=[{"speaker": "Maelor",
                          "text": "That was well done. It changes less than you think."}])),
        ("I ask him to stop.",
         R("He says he will not, and that he does not have to win quickly.")),
    ]

    # --- IX. The end ---------------------------------------------------
    B += [
        ("I wait for him to move first.",
         R("He moves first.")),
        ("I take the blow and close the distance.",
         R("It costs Corin his shield arm and buys him three feet.")),
        ("I finish it.",
         R("It is quick, and afterwards the hall is very quiet.")),
        ("I go and find Sera.",
         go(GATE, "Sera is at the gate, cold and furious and alive.",
            diff={"positions": {"Corin": GATE},
                  "cast_changes": [{"who": "Sera", "status": "active",
                                    "reason": "found at the gate"}]})),
    ]

    # --- X. The way home runs through the square ------------------------
    # Deliberately back through a room where something happened DURING the
    # absence. Roadmap item 1's last requirement is "returns to encounter the
    # resulting state", and a quest that only ever moves forward gives
    # `destination_residue` no eligible re-entry at all. Two earlier drafts
    # of this epilogue were corrected by the engine rather than the other way
    # round: a residue ask for the well-sealing was refused because the party
    # WATCHED the well seal (a fuse that fires in front of you is not
    # absence), and a crowd telling Sera about it was refused because she had
    # just read the aftermath off the room herself ("already heard that").
    # Both refusals were the design working. What survives is the honest
    # shape: the riders' raid landed while nobody was there, so Corin meets
    # it as residue -- and Sera, who takes the stream path and never enters
    # the square, can learn of it ONLY from the villagers who walked home
    # carrying the talk.
    def through_market(p):
        diff = {"positions": {"Corin": MARKET, "Sera": WELL}}
        for crowd in (p or {}).get("crowds") or []:
            if str(crowd.get("room")) == MARKET and crowd.get("crowd_id") \
                    and "villagers" in str(crowd.get("composition") or ""):
                # The villagers give up on the square and walk home, and
                # their talk walks with them -- the anonymous carrier moving
                # because the crowd moves, exactly as designed.
                diff["crowd_ops"] = [{"op": "move",
                                      "crowd_id": crowd["crowd_id"],
                                      "room": WELL}]
                break
        return R("The square is quieter, and the stalls stand stripped. "
                 "Sera takes the stream path and does not see it.",
                 diff=diff)
    # A callable payload cannot be introspected before the turn runs, so it
    # declares its movement and its narration for the scripts here.
    through_market.moves_to = MARKET
    through_market.prose = ("The square is quieter than the morning they "
                            "left it, and the grain stalls stand stripped "
                            "bare.")

    def home_with_the_news(p):
        # The telling names only what the payload actually showed -- a
        # crowd_id and a world_event_id from that crowd's own `talk` --
        # because an id the Director was never shown is this engine's oldest
        # class of unreachable mechanism. Sera never stood where the raid's
        # surface stands, so the crowd is the only route it can reach her by.
        diff = {"positions": {"Corin": WELL}}
        for crowd in (p or {}).get("crowds") or []:
            if str(crowd.get("room")) != WELL:
                continue
            for talk in crowd.get("talk") or []:
                if "riders" in str(talk.get("gist") or "") \
                        and talk.get("world_event_id"):
                    diff["telling_ops"] = [{
                        "speaker": crowd.get("crowd_id"),
                        "listener": "Sera",
                        "world_event_id": talk["world_event_id"]}]
                    break
        return R("The Fenwater is running, and the villagers' talk of the "
                 "riders reaches Sera before Corin does.", diff=diff)
    home_with_the_news.moves_to = WELL
    home_with_the_news.prose = ("The Fenwater is running. It is the loudest "
                                "thing in the Vale, under the villagers' "
                                "talk of riders and empty grain stores.")

    B += [
        ("We come down through the market square.", through_market),
        ("We go home.", home_with_the_news),
    ]
    return B


#: What a character says out loud on a given beat, by TURN INDEX. Grounding for
#: plans and tellings is read from `dialogue_log`, which the interaction loop
#: builds from character output -- not from the Director's own payload.
SPEECH = {}


def build_speech(beats):
    """Mirror each beat's authored dialogue into character speech.

    A telling and a plan are both refused unless the speaker actually spoke,
    and the log the guard reads is assembled from CHARACTER output. Deriving
    this from the beats rather than hand-keying turn numbers means inserting a
    beat cannot silently un-ground every plan after it -- which is exactly what
    happened the first time this was hand-keyed.
    """
    out = {}
    for idx, (_input, payload) in enumerate(beats):
        if callable(payload):
            continue
        for line in (payload.get("dialogue_log") or []):
            if isinstance(line, dict) and line.get("text"):
                out[idx] = str(line["text"])
                break
    return out


def play(db, cid, author, beats):
    from agents.runtime import run_pipeline

    speech = build_speech(beats)
    # The narrator receives the player's perceptual slice and NOT the
    # Director's resolved_event -- that separation is the whole point of the
    # stage. So the beat's prose is scripted for it directly, the way a model
    # reading that slice would have written it.
    played = []
    for idx, (player_input, payload) in enumerate(beats):
        author.script(idx, "director_resolve", payload)
        prose = (payload.get("resolved_event") if isinstance(payload, dict)
                 else getattr(payload, "prose", None))
        if prose:
            author.script(idx, "narrator", {"prose": prose})
        # A beat that moves the player must SAY so at the interpret stage.
        # `destination_residue` -- how a room stands after an absence, which is
        # the whole "the hearth is cold and the crowd is thinner" mechanism --
        # is computed from `interpret.movement.to_room`, never from the
        # positions the resolve happens to write. A harness that moved people
        # only in `state_diff.positions` got room residue exactly zero times in
        # fifty beats, and the engine was right every time.
        moved_to = ((payload.get("state_diff") or {}).get("positions") or {}
                    ).get("Corin") if isinstance(payload, dict) \
            else getattr(payload, "moves_to", None)
        if moved_to:
            interp = author.default("director_interpret")
            if callable(interp):
                interp = interp({"player_input": player_input})
            interp["movement"] = {"to_room": moved_to, "manner": "walk"}
            author.script(idx, "director_interpret", interp)
        line = speech.get(idx)
        if line:
            spoken = dict(author.default("character"))
            spoken["sequence"] = [{"type": "speech", "text": line}]
            author.script(idx, "character", spoken)
        author.current_turn(idx)
        tid = db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
            "VALUES(?,?,?,?,?)", (cid, idx, player_input, time.time(), None))
        error = ""
        try:
            for _ in run_pipeline(cid, tid):
                pass
        except Exception as exc:                # noqa: BLE001 - reported
            error = "%s: %s" % (type(exc).__name__, exc)
        played.append({"turn": idx, "input": player_input, "error": error,
                       "turn_id": tid})
    return played


def fired_by_turn(db, cid):
    """What each beat's commit actually reported, in reading order."""
    rows = db.q("SELECT s.turn_id, v.content FROM variants v "
                "JOIN steps s ON s.id = v.step_id "
                "WHERE v.active=1 AND s.key='commit' ORDER BY s.turn_id") or []
    out = {}
    for row in rows:
        try:
            results = (json.loads(row["content"]) or {}).get("results") or {}
        except (TypeError, ValueError):
            continue
        ep = results.get("offscreen_epoch") or {}
        ic = results.get("information_carriers") or {}
        cr = results.get("crowds") or {}
        pl = results.get("offscreen_plans") or {}
        we = results.get("world_events") or {}
        events = []
        if cr.get("offered"):
            events.append("crowd declared")
        if cr.get("moved"):
            events.append("a crowd moved")
        if pl.get("applied"):
            events.append("a plan opened")
        if we.get("written"):
            events.append("world event recorded")
        if ic.get("public_surfaces"):
            events.append("a public surface")
        if ic.get("acquired"):
            events.append("somebody witnessed it")
        if ic.get("crowd_acquired"):
            events.append("the crowd took it up")
        if ic.get("told"):
            events.append("somebody was told")
        if (results.get("routine_residue") or {}).get("delivered"):
            events.append("the room remembered the absence")
        if ep.get("reactive_fired"):
            events.append("a plan's stage fired")
        if ep.get("stochastic_fired"):
            events.append("an absent mind stirred")
        if ep.get("agent_scheduled"):
            events.append("MAELOR THINKS")
        if ep.get("opportunity"):
            events.append("epoch: %s" % ", ".join(ep.get("reasons") or []))
        out[row["turn_id"]] = events
    return out


def narration_by_turn(db, cid):
    rows = db.q("SELECT s.turn_id, v.content FROM variants v "
                "JOIN steps s ON s.id = v.step_id "
                "WHERE v.active=1 AND s.key='narrator' ORDER BY s.turn_id") or []
    out = {}
    for row in rows:
        try:
            blob = json.loads(row["content"])
        except (TypeError, ValueError):
            continue
        if isinstance(blob, dict):
            out[row["turn_id"]] = str(blob.get("prose") or "")
    return out


def who_knows_what(db, cid):
    rows = db.q("SELECT ch.name, cc.status, cc.state FROM chat_chars cc "
                "JOIN characters ch ON ch.id = cc.char_id "
                "WHERE cc.chat_id=?", (cid,)) or []
    out = []
    for row in rows:
        try:
            state = json.loads(row["state"] or "{}")
        except (TypeError, ValueError):
            state = {}
        out.append({
            "who": row["name"], "status": row["status"],
            "knows": [{"claim": r.get("claim"),
                       "how": r.get("provenance"),
                       "retellings": r.get("retellings"),
                       "from": r.get("told_by")}
                      for r in (state.get("carried_reports") or [])],
        })
    return out


def transcript(cid, played, fired, prose, knowledge):
    lines = [
        "# The Ashen Quest",
        "",
        "Fifty beats through the real Sonder pipeline. Every model output is",
        "authored by hand; every mechanism that fires is the engine's own.",
        "",
        "Maelor is **dormant and off-screen** for almost the whole quest, and",
        "so is Wren, who went east to break his workings before they set. The",
        "player never watches either of them. What they do reaches Corin as",
        "consequences that fired on a clock and as things other people saw.",
        "",
        "Neither of them foils the other completely, and neither is narrated.",
        "",
        "Lines in **bold** are what the engine did, not what was narrated.",
        "",
        "---",
        "",
    ]
    for row in played:
        tid = row["turn_id"]
        lines.append("### %d. %s" % (row["turn"] + 1, row["input"]))
        lines.append("")
        text = prose.get(tid) or ""
        if text:
            lines.append(text)
            lines.append("")
        for event in fired.get(tid) or []:
            lines.append("> **%s**" % event)
        if fired.get(tid):
            lines.append("")
        if row["error"]:
            lines.append("> `ERROR: %s`" % row["error"])
            lines.append("")

    lines += ["---", "", "## What each mind ended up believing", ""]
    for entry in knowledge:
        if not entry["knows"]:
            lines.append("- **%s** (%s) — knows nothing about the wells."
                         % (entry["who"], entry["status"]))
            continue
        for item in entry["knows"]:
            how = item["how"]
            if how == "told":
                how = "told by %s, %d retelling(s) from the truth" % (
                    item["from"], item["retellings"] or 0)
            lines.append("- **%s** (%s) — %r *(%s)*"
                         % (entry["who"], entry["status"], item["claim"], how))
    lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=".", help="where to write the artefacts")
    ap.add_argument("--capture", default="", help="dump stage prompts/payloads")
    args = ap.parse_args()

    _require_scratch()
    from core import db as db_module
    from llm import llm_quality
    from llm import providers

    db_module.init()
    author = QuestAuthor()
    author.capture_dir = args.capture
    llm_quality.complete_validated_json = author
    for mod in list(sys.modules.values()):
        if getattr(mod, "complete_validated_json", None) is not None \
                and mod is not llm_quality:
            mod.complete_validated_json = author
    # The off-screen rungs call the provider directly rather than through the
    # validated seam, so the villain needs a voice of his own.
    providers.chat_complete = _offscreen_voice

    cid = build_story(db_module)
    beats = quest(author, cid)
    played = play(db_module, cid, author, beats)
    # Out-of-band jobs are daemon threads; give the villain a moment to think.
    _settle()

    fired = fired_by_turn(db_module, cid)
    prose = narration_by_turn(db_module, cid)
    knowledge = who_knows_what(db_module, cid)

    os.makedirs(args.out, exist_ok=True)
    from persist.chat_archive import ChatArchiveService

    story_path = os.path.join(args.out, "story.json")
    with open(story_path, "w") as fh:
        json.dump(ChatArchiveService.export_chat(None, cid), fh, indent=1,
                  default=str)
    md_path = os.path.join(args.out, "transcript.md")
    with open(md_path, "w") as fh:
        fh.write(transcript(cid, played, fired, prose, knowledge))

    errors = [p for p in played if p["error"]]
    print("beats played : %d" % len(played))
    print("errors       : %d" % len(errors))
    for e in errors[:3]:
        print("   turn %d: %s" % (e["turn"], e["error"][:110]))
    print("story.json   : %s" % story_path)
    print("transcript   : %s" % md_path)
    print()
    print("what fired:")
    for row in played:
        events = fired.get(row["turn_id"]) or []
        if events:
            print("  turn %2d  %s" % (row["turn"] + 1, " | ".join(events)))
    return 0


def _offscreen_voice(role, system, user, **kw):
    """The two absent minds, answering for themselves.

    Branching on WHO is asking, not just on which stage. The first version
    returned one payload to every caller, so Wren's tick dutifully carried out
    Maelor's scheme and the objective ledger recorded her sealing a well she
    had gone east to break. A stub that answers the same thing to everybody is
    not standing in for two characters; it is standing in for one.
    """
    who = "wren" if "wren" in str(user).casefold() else "maelor"
    if role.startswith("character"):
        if who == "wren":
            return json.dumps({
                "attempt": "break the next seal before it finishes setting",
                "plan_op": "keep", "toward": "ahead of him, eastward"})
        return json.dumps({
            "attempt": "seal another well before the boy reaches the gate",
            "plan_op": "keep", "toward": "the wells below the town"})
    if who == "wren":
        # She foils some and not all: a partial verdict on a working that was
        # already half-set is a crack, not a clean break.
        return json.dumps({
            "outcome": "partial", "moved_to": "",
            "consequence": {
                "what": "one of the sealed wells has been forced part-open",
                "where": TOWN, "due_seconds": 3600,
                "witnessed": "a seal had been prised at and left cracked",
                "originator": "Wren"},
            "note": "she is one step behind him and closing"})
    return json.dumps({
        "outcome": "partial", "moved_to": "",
        "consequence": {
            "what": "another well in the Vale has been sealed",
            "where": TOWN, "due_seconds": 3600,
            "witnessed": "the well cover was fused shut overnight",
            "originator": "Maelor"},
        "note": "he works faster now that he has been noticed"})


def _settle(seconds=3.0):
    import threading
    deadline = time.time() + seconds
    while time.time() < deadline:
        if not any(t.name.startswith("job-") for t in threading.enumerate()):
            return
        time.sleep(0.1)


if __name__ == "__main__":
    raise SystemExit(main())
