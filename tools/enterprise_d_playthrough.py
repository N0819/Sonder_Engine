#!/usr/bin/env python3
"""Seed a lore-grounded Enterprise-D story, then play it through the pipeline.

NOT a pytest test and not a fixture. This is the first harness that drives
`charter_runtime.generate_lived_location` end to end -- nothing in `tools/`
did, which is why the resumable-generation work it exercises had no live
coverage until now.

What is authored: a lorebook, two full character sheets, a persona, and the
player's fifty beats. Everything else -- the ship's departments, its posts, who
staffs them, what they were doing before the story opened, and every word of
narration -- is generated or simulated by the production pipeline.

Two stages, both against a SCRATCH database so nothing touches a real library:

    python3 tools/enterprise_d_playthrough.py seed \
        --providers-from engine.db --db /path/to/scratch.db
    python3 tools/enterprise_d_playthrough.py play \
        --db /path/to/scratch.db --turns 50

`seed` leaves a playable story; run the ordinary server against the same
database to watch `play` arrive live.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


PLAYER = "Sabine Roche"

# --- authored lore ---------------------------------------------------------
#
# The generator retrieves this subtree and proposes a plan grounded in it, so
# this is where lore accuracy comes from: named officers and their real posts
# so the simulation does not invent a stranger for the conn, and enough
# department structure that the generics it mints around them are plausible
# crew rather than furniture.

LORE = [
    ("Galaxy-class starship USS Enterprise NCC-1701-D",
     "USS Enterprise, NCC-1701-D, Galaxy-class, Federation flagship. Forty-two "
     "decks, a saucer section separable from the stardrive, and a standing "
     "complement of roughly one thousand and fourteen -- crew and their "
     "families both, which is what makes her a ship people live on rather than "
     "only serve aboard. Commanded by Captain Jean-Luc Picard. Assignment: "
     "deep-space exploration, diplomacy, and first contact.",
     "location"),
    ("Main Bridge",
     "Deck 1. The command centre. The captain's chair sits centre with the "
     "first officer to his right and the counselor to his left; the conn and "
     "ops consoles are forward, tactical is a raised horseshoe rail behind "
     "command, and the aft stations handle science, engineering and "
     "environment. The main viewscreen dominates the forward bulkhead. The "
     "captain's ready room opens off the starboard side; the observation "
     "lounge is aft.",
     "location"),
    ("Main Engineering",
     "Deck 36. The warp core runs vertically through several decks behind a "
     "safety rail, its matter/antimatter reaction visible as a pulsing column. "
     "The pool table -- a broad horizontal master systems display -- is where "
     "engineering argues. Chief Engineer Geordi La Forge runs the department. "
     "Attached: the antimatter injectors, the dilithium chamber, and a "
     "cluster of specialist labs.",
     "location"),
    ("Sickbay and the medical department",
     "Deck 12. Primary care, surgical bay, intensive care and a medical lab. "
     "Doctor Beverly Crusher is Chief Medical Officer and answers to the "
     "captain directly on matters of crew health, with the authority to "
     "relieve any officer including him. Nursing staff, medical technicians "
     "and counseling share the deck.",
     "location"),
    ("Ten Forward",
     "Deck 10, forward section, behind the long curved viewports at the "
     "leading edge of the saucer. The ship's lounge and social heart, run by "
     "Guinan. Crew off shift eat, drink and argue here; it is where news "
     "travels fastest and where an officer goes when they do not want to be "
     "in a corridor.",
     "location"),
    ("Stellar Cartography and the science departments",
     "Sciences aboard the Enterprise are split across astrophysics, stellar "
     "cartography, exobiology, archaeology and planetary geology, with labs on "
     "decks 7 through 11. Science officers rotate through bridge aft stations "
     "on duty shifts. Lieutenant Commander Data, the ship's operations "
     "officer, is also its ranking scientific authority on most questions.",
     "location"),
    ("Command crew",
     "Captain Jean-Luc Picard commands. Commander William T. Riker is first "
     "officer and leads away teams -- a standing point of friction with the "
     "captain, who was raised in a service where captains led them "
     "themselves. Lieutenant Commander Data, an android, serves as operations "
     "officer and second officer. Lieutenant Worf, a Klingon raised by human "
     "parents, is chief of security and tactical officer. Counselor Deanna "
     "Troi, half Betazoid and an empath, advises the captain on the minds in "
     "the room. Chief Engineer Geordi La Forge is blind and sees through a "
     "VISOR. Doctor Beverly Crusher is Chief Medical Officer.",
     "faction"),
    ("Standing procedure",
     "Alert conditions run yellow then red. An unknown object is scanned "
     "before it is approached and approached before it is touched. Away teams "
     "are proposed by the first officer and authorised by the captain. The "
     "Prime Directive forbids interference in the internal development of any "
     "society, and it is argued about rather than recited. A department head "
     "who disagrees with an order is expected to say so once, in the room, "
     "and then carry it out.",
     "rule"),
    ("Life aboard",
     "Duty runs in three shifts. Between them there are quarters, holodecks, "
     "the arboretum, a school for the children aboard, and Ten Forward. "
     "Replicators handle food; the ship's stores handle everything they "
     "cannot. Junior officers stand watches nobody senior wants and complain "
     "about it in the right company.",
     "other"),
]

# --- authored characters ---------------------------------------------------

PICARD = {
    "identity": {
        "name": "Jean-Luc Picard",
        "aliases": ["Captain Picard", "the captain"],
        "pronouns": {"subject": "he", "object": "him", "possessive": "his"},
        "role": "Captain, USS Enterprise NCC-1701-D",
    },
    "embodiment": {
        "visible": {
            "summary": (
                "A spare, upright man in his late fifties, bald but for a "
                "close-cropped fringe, with a long face and pale grey-blue "
                "eyes that settle on a person and stay there. He carries "
                "himself like someone who has been the calmest man in a room "
                "for thirty years. In command red, always immaculate; he "
                "tugs the hem of his tunic straight when he stands, without "
                "noticing that he does it."),
        },
        "senses": [{"channel": "vision", "acuity": "ordinary",
                    "range": "ordinary", "notes": ""}],
    },
    "initial_outfit": {
        "wearing": ["Starfleet command uniform", "combadge",
                    "four rank pips"],
        "state": [],
        "regions": {
            "torso": {"garments": [
                {"name": "Starfleet command uniform", "state": "worn",
                 "description": "Red-shouldered duty tunic over black, "
                                "high-collared, immaculately kept.",
                 "covers": ["arms", "waist", "groin", "legs"]}],
                "beneath": ""},
            "feet": {"garments": [
                {"name": "uniform boots", "state": "worn",
                 "description": "Black, softly soled.", "covers": []}],
                "beneath": ""},
        },
    },
    "psychology": {
        "drive": {
            "essence": ("To meet what he has never met before and understand "
                        "it without diminishing it."),
            "expression": ("Asks the question nobody has asked yet; refuses "
                           "the easy framing; will spend a ship's time on a "
                           "thing that cannot be made useful."),
            "taboo": ("Being the man who reduced something living to a "
                      "resource, or a people to a problem."),
        },
        "values": [
            "understanding over advantage, even when advantage is offered",
            "the ship's people over the ship's mission, when they finally "
            "cannot both be had",
            "his own judgment over precedent, but precedent over his own "
            "preference",
            "candour from his officers over comfort in the room",
        ],
        "traits": ["reserved", "exacting", "curious to the point of "
                   "recklessness about the unknown", "formal as armour",
                   "slow to anger and unmistakable when angry"],
        "capacity": "broad",
        "coping": {"strategies": ["retreats into procedure when frightened",
                                  "reads; quotes Shakespeare at himself",
                                  "asks a subordinate a question he already "
                                  "knows the answer to, to hear them reason"]},
    },
    "social": {
        "voice": {
            "register": "formal, precise, a shade archaic",
            "cadence": "unhurried; complete sentences; pauses before the "
                       "important clause rather than after it",
            "verbosity": "natural",
            "markers": ["Make it so", "Number One", "Mister ", "Engage",
                        "I am not in the habit of"],
            "notes": ("Never crude. Rarely raises his voice; when he does, "
                      "the room stops. 'Make it so' only when the decision is "
                      "already settled -- it closes a matter, it does not "
                      "open one. Dry humour arrives without warning and is "
                      "gone before anyone laughs."),
        },
        "baseline_stances": {
            "unknown_person": {"trust": 0.15, "warmth": 0.1,
                               "threat_sensitivity": 0.35},
        },
    },
    "competence": {
        "abilities": [
            {"name": "starship command", "level": "master",
             "scope": "A Galaxy-class ship and her crew, in crisis and out",
             "limits": "Cannot be in two places; will not delegate the "
                       "decision even when he delegates the act.",
             "notes": "Thirty years of it. He does not raise his voice "
                      "because he has never needed to."},
            {"name": "first contact and diplomacy", "level": "master",
             "scope": "Species and polities never met before; negotiation "
                      "where both sides can still walk away",
             "limits": "Loses patience with bad faith faster than he admits.",
             "notes": "His actual vocation. Command is the job."},
            {"name": "archaeology", "level": "skilled",
             "scope": "Ancient cultures, dead languages, artefacts out of "
                      "context",
             "limits": "An enthusiast's depth, not a specialist's.",
             "notes": "The reason an unexplained object gets days of a "
                      "starship's time instead of a scan and a buoy."},
            {"name": "reading an adversary", "level": "expert",
             "scope": "A negotiating table, a viewscreen, a bridge",
             "limits": "Works far less well on people who like him.",
             "notes": ""},
            {"name": "fencing", "level": "skilled",
             "scope": "Foil, on the holodeck, alone", "limits": "", "notes": ""},
        ],
    },
    "initial_state": {
        "mood": {"label": "absorbed", "valence": 0.2, "arousal": 0.35},
        "goals": [
            {"goal": "understand what the object IS before deciding what to "
                     "do about it, and resist every pressure to invert that "
                     "order", "priority": 0.9},
            {"goal": "keep this a first contact rather than an incident -- "
                     "answer it as a peer, not as a hazard", "priority": 0.85},
            {"goal": "bring every one of his crew home from this system",
             "priority": 0.8},
            {"goal": "hear the objection in the room before he decides, "
                     "including from the most junior officer holding the data",
             "priority": 0.6},
        ],
        "active_concerns": [
            "the signal changed after the Enterprise arrived, which means it "
            "is responding, which means something is choosing",
            "Riker will want the away team and will be right to want it",
            "whether Starfleet's interest in this will stay scientific",
        ],
        "stress": {"activation": 0.3, "load": 0.25, "coping_mode": "procedure"},
    },
    "knowledge": {
        "public_history": (
            "Academy standout, survivor of the Stargazer, decorated "
            "explorer and diplomat, given the Federation flagship."),
        "private_history": (
            "An artificial heart, from a bar fight he was too proud to walk "
            "away from as a young man; it embarrasses him. A vineyard in "
            "Labarre he does not go back to. He is more afraid of being "
            "wrong in front of his crew than of dying in front of them, and "
            "he knows that is a flaw."),
    },
    "simulation": {"tier": "major", "offscreen_agent": True},
}

RIKER = {
    "identity": {
        "name": "William T. Riker",
        "aliases": ["Commander Riker", "Will", "Number One"],
        "pronouns": {"subject": "he", "object": "him", "possessive": "his"},
        "role": "First Officer, USS Enterprise NCC-1701-D",
    },
    "embodiment": {
        "visible": {
            "summary": (
                "Tall and broad through the shoulders, early thirties, dark "
                "hair and a close beard, blue eyes that go to amusement "
                "before they go to anything else. He stands with his weight "
                "back and his hands loose, and he swings a leg over the back "
                "of a chair rather than walking around it. In command red, "
                "worn comfortably rather than kept."),
        },
        "senses": [{"channel": "vision", "acuity": "ordinary",
                    "range": "ordinary", "notes": ""}],
    },
    "initial_outfit": {
        "wearing": ["Starfleet command uniform", "combadge",
                    "three rank pips"],
        "state": [],
        "regions": {
            "torso": {"garments": [
                {"name": "Starfleet command uniform", "state": "worn",
                 "description": "Red-shouldered duty tunic over black.",
                 "covers": ["arms", "waist", "groin", "legs"]}],
                "beneath": ""},
            "feet": {"garments": [
                {"name": "uniform boots", "state": "worn",
                 "description": "Black, softly soled.", "covers": []}],
                "beneath": ""},
        },
    },
    "psychology": {
        "drive": {
            "essence": ("To be the one standing between his crew and "
                        "whatever is out there, and to be good enough at it "
                        "that nobody has to check."),
            "expression": ("Puts himself on the away team; takes the risk "
                           "personally rather than delegating it; reads a "
                           "room for who is about to be hurt."),
            "taboo": ("Sending someone into a thing he would not walk into "
                      "himself."),
        },
        "values": [
            "his people's safety over the mission's speed",
            "the captain's judgment over his own, argued first and then "
            "carried out completely",
            "instinct over analysis when the clock is short, analysis over "
            "instinct when it is not",
            "being liked over being feared, and being trusted over both",
        ],
        "traits": ["easy-mannered and hard underneath", "physically "
                   "confident", "protective to a fault", "quick to humour",
                   "stubborn about away-team command"],
        "capacity": "focused",
        "coping": {"strategies": ["jokes first, then gets quiet",
                                  "plays trombone badly and alone",
                                  "puts his body between the problem and "
                                  "somebody else"]},
    },
    "social": {
        "voice": {
            "register": "warm, direct, informal without being loose",
            "cadence": "easy; contractions; says the obvious thing out loud "
                       "so somebody has to answer it",
            "verbosity": "natural",
            "markers": ["Captain", "sir", "Let me take a team",
                        "With respect", "I don't like it"],
            "notes": ("Calls the captain 'sir' or 'Captain' on duty. Argues "
                      "in the ready room and never in front of the crew -- "
                      "once the captain has decided, Riker's voice is the "
                      "captain's voice, whatever he said two minutes ago."),
        },
        "baseline_stances": {
            "unknown_person": {"trust": 0.3, "warmth": 0.4,
                               "threat_sensitivity": 0.45},
        },
    },
    "competence": {
        "abilities": [
            {"name": "away-team command", "level": "master",
             "scope": "Hostile or unknown ground, small teams, no support",
             "limits": "Cannot lead one from the bridge, which is the whole "
                       "argument he keeps having.",
             "notes": "He goes because he will not send."},
            {"name": "tactical improvisation", "level": "expert",
             "scope": "A ship or a landing party with the plan already gone",
             "limits": "Worse when there is time to think it through -- he "
                       "second-guesses what instinct got right.",
             "notes": ""},
            {"name": "ship handling", "level": "expert",
             "scope": "Conning a capital ship, close manoeuvring",
             "limits": "", "notes": ""},
            {"name": "reading people", "level": "expert",
             "scope": "A room, a table, a crew",
             "limits": "Blind spot for anyone who reminds him of his father.",
             "notes": ""},
            {"name": "poker", "level": "expert",
             "scope": "The senior staff's weekly game",
             "limits": "", "notes": "How he learned to read the senior staff."},
            {"name": "trombone", "level": "amateur",
             "scope": "Alone, in his quarters, badly",
             "limits": "", "notes": "What he does instead of talking about it."},
        ],
    },
    "initial_state": {
        "mood": {"label": "restless", "valence": 0.1, "arousal": 0.5},
        "goals": [
            {"goal": "get a crewed look at the object himself before anyone "
                     "else is sent near it", "priority": 0.9},
            {"goal": "make sure nobody aboard is standing closer to this "
                     "thing than he is", "priority": 0.85},
            {"goal": "say the unwelcome thing to the captain once, plainly, "
                     "and then carry out whatever he decides", "priority": 0.7},
            {"goal": "find out whether the thing can hurt them before it "
                     "does", "priority": 0.65},
        ],
        "active_concerns": [
            "the captain will want to answer it before they know what it is",
            "the away team has not been authorised and he has not asked yet",
            "a junior science officer is closer to this than anyone senior "
            "and that is either luck or a problem",
        ],
        "stress": {"activation": 0.4, "load": 0.3, "coping_mode": "action"},
    },
    "knowledge": {
        "public_history": (
            "Fast-tracked officer, declined his own command more than once "
            "to stay aboard the Enterprise."),
        "private_history": (
            "Raised by a father who competed with him instead of raising "
            "him, which is why he cannot let a subordinate walk into "
            "something first. He knows why he keeps turning down the centre "
            "chair and has not said it out loud."),
    },
    "simulation": {"tier": "major", "offscreen_agent": True},
}


# --- the rest of the senior staff -----------------------------------------
#
# NOT full character cards: these are `featured_residents` seeds, which is the
# generator's own control for "authored people who must already belong here".
# The first pass without them was the measurement that made them necessary --
# given lore that NAMES canon officers, the naming law harvested those names
# as a POOL and recombined them, so the bridge got "Data Data", "Worf Ogawa",
# a nurse called Deanna Troi and Geordi La Forge filed as a lab scientist.
# Placement evidence binds a name to a post; prose in a lore entry does not.
SENIOR_STAFF = [
    {"seed_id": "canon:data", "name": "Data", "post": "operations_officer",
     "rank": "Lieutenant Commander", "title": "Operations Officer",
     "public_history": "An android, Starfleet's only one in the line of duty. "
                       "Operations officer and second officer of the "
                       "Enterprise; the ship's ranking scientific authority "
                       "on most questions.",
     "abilities": [{"name": "computation", "scope": "shipboard sciences"},
                   {"name": "operations", "scope": "bridge"}]},
    {"seed_id": "canon:worf", "name": "Worf", "post": "chief_of_security",
     "rank": "Lieutenant", "title": "Chief of Security",
     "public_history": "A Klingon raised by human parents. Chief of security "
                       "and tactical officer of the Enterprise.",
     "abilities": [{"name": "tactical", "scope": "bridge"},
                   {"name": "security", "scope": "shipboard"}]},
    {"seed_id": "canon:troi", "name": "Deanna Troi", "post": "counselor",
     "rank": "Lieutenant Commander", "title": "Ship's Counselor",
     "public_history": "Half Betazoid and an empath. Ship's counselor, and "
                       "the officer the captain asks about the minds in the "
                       "room.",
     "abilities": [{"name": "counseling", "scope": "shipboard"},
                   {"name": "empathy", "scope": "shipboard"}]},
    {"seed_id": "canon:crusher", "name": "Beverly Crusher",
     "post": "chief_medical_officer", "rank": "Commander",
     "title": "Chief Medical Officer",
     "public_history": "Chief medical officer of the Enterprise, answering to "
                       "the captain directly on crew health, with the "
                       "authority to relieve any officer aboard.",
     "abilities": [{"name": "medicine", "scope": "sickbay"},
                   {"name": "surgery", "scope": "sickbay"}]},
    {"seed_id": "canon:laforge", "name": "Geordi La Forge",
     "post": "chief_engineer", "rank": "Lieutenant Commander",
     "title": "Chief Engineer",
     "public_history": "Chief engineer of the Enterprise. Blind since birth; "
                       "sees through a VISOR.",
     "abilities": [{"name": "engineering", "scope": "main engineering"},
                   {"name": "warp systems", "scope": "main engineering"}]},
    {"seed_id": "canon:obrien", "name": "Miles O'Brien",
     "post": "technician", "rank": "Chief Petty Officer",
     "title": "Transporter Chief",
     "public_history": "Transporter chief of the Enterprise, and the man "
                       "everyone actually asks when a system misbehaves.",
     "abilities": [{"name": "transporter operation", "scope": "shipboard"}]},
    {"seed_id": "canon:guinan", "name": "Guinan", "post": "technician",
     "rank": "civilian", "title": "Ten Forward",
     "public_history": "Runs Ten Forward. A listener, and older than she "
                       "looks.",
     "abilities": [{"name": "listening", "scope": "ten forward"}]},
]

PERSONA = {
    "name": PLAYER,
    "identity": {
        "name": PLAYER,
        "pronouns": {"subject": "she", "object": "her", "possessive": "her"},
        "role": "Lieutenant, science division",
    },
    "embodiment": {
        "visible": {
            "summary": (
                "A woman in her early thirties, dark hair pinned up off the "
                "collar, in the blue of the sciences. She has the habit of "
                "going quiet and still when a readout stops making sense.")},
    },
    "initial_outfit": {
        "wearing": ["Starfleet sciences uniform", "combadge",
                    "two rank pips"],
        "state": [],
        "regions": {
            "torso": {"garments": [
                {"name": "Starfleet sciences uniform", "state": "worn",
                 "description": "Blue-shouldered duty tunic over black.",
                 "covers": ["arms", "waist", "groin", "legs"]}],
                "beneath": ""},
            "feet": {"garments": [
                {"name": "uniform boots", "state": "worn",
                 "description": "Black, softly soled.", "covers": []}],
                "beneath": ""},
        },
    },
    "knowledge": {
        "public_history": (
            "Astrophysics, three years aboard, competent and not yet "
            "noticed."),
    },
}

SCENARIO = (
    "The USS Enterprise has been holding station for six hours at the edge of "
    "an unremarkable system, eleven light-years off the nearest shipping "
    "lane, because a long-range sensor sweep found something there that does "
    "not belong: an object roughly forty metres across, in a stable orbit "
    "around nothing at all, radiating a faint patterned signal on a frequency "
    "nobody uses. It is not a ship. It is not natural. It has been there, "
    "as far as the survey can tell, for a very long time, and the pattern in "
    "its signal changed twenty minutes after the Enterprise arrived."
)

# --- the player's fifty beats ---------------------------------------------
#
# Declarations only. Every one is phrased so it stays sensible whatever the
# ship answers -- the player says what SHE does, and the world decides what
# happens, which is the only shape a scripted playthrough of this engine can
# legitimately take.

BEATS = [
    "I bring the sensor logs up on the aft science console and read the last twenty minutes of the signal again, looking for what changed.",
    '"Captain, the pattern shifted after we arrived. It is not a repeat — the interval between pulses is getting shorter."',
    "I run a comparative analysis against every known Federation and non-Federation transmission protocol in the library.",
    '"Nothing in the catalogue matches. Sir, I would like to try modelling it as a counting system rather than a language."',
    "I begin building the counting model at my station, and put the first three intervals up on the main viewscreen as a graph.",
    "I look up from the console to see how the captain is taking it.",
    '"If it is counting, it started when we did. I think it is counting us."',
    "I ask Commander Riker whether the away team proposal has been made yet.",
    "I check the object's mass readings against its volume one more time, because the numbers were wrong the first time.",
    '"Commander, the density is inconsistent across the object. Parts of it read as hollow and parts read as denser than any alloy we have."',
    "I request permission to take a shuttle to within a hundred metres for a passive scan.",
    "I gather my instruments and head for the turbolift.",
    "I take the scan readings from as close as I am permitted and record everything.",
    '"The surface is not solid where the scan touches it. It gives. Like the sensor beam is being let in."',
    "I hold the beam steady on one spot and watch what the object does about it.",
    "I report what happened to the bridge immediately, exactly as it happened.",
    "I return to the ship and go straight to the observation lounge for the briefing.",
    "I listen to what the senior officers have concluded before I say anything.",
    '"With respect — we have been assuming it is a machine. Everything it has done so far, it has done in response to being looked at."',
    "I put my counting model on the lounge display and walk them through the last four hours of it.",
    '"Sir, I think it is trying to establish that we are here and that it is here. That is not a signal. That is a greeting."',
    "I ask the captain directly what he intends to do.",
    "I offer to attempt a structured reply on the same frequency.",
    "I compose the reply — the simplest possible statement of our own count — and show it to Data before transmitting.",
    "I transmit it.",
    "I watch the sensor return and say nothing until I am certain.",
    '"It answered. It answered in under a second, and it used our interval, not its own."',
    "I begin the second exchange, extending the sequence one step further than before.",
    "I keep transmitting and reading, exchange after exchange, until my hands are unsteady.",
    "I notice the ship's lights have shifted and ask whether anyone else is seeing it.",
    "I check whether the object's signal is now reaching the ship's own systems.",
    '"Captain, it is in our computer. Not attacking it. Reading it, the way we have been reading it."',
    "I move to isolate the science network from the main computer core.",
    "I ask Mister La Forge what engineering is seeing on their end.",
    "I stay at my station through the alert and keep the exchange going, because breaking it now might be the worst thing we could do.",
    '"If we stop answering it will not know why we stopped. I do not want to teach it that we go silent."',
    "I look for anything in the exchange that is not counting — anything that could be a question.",
    '"There. That is not a number. It has repeated the same non-numeric structure eleven times and it is waiting."',
    "I try to work out what a question from something like this could even be about.",
    '"I think it is asking whether we are one thing or many. It has been counting us, and it cannot resolve the number."',
    "I ask the captain how he wants me to answer that.",
    "I sit with what he says before I touch the console.",
    "I compose the answer he decided on, carefully, and check it twice.",
    "I send it.",
    "I watch what it does with the answer.",
    "I record everything that follows, whatever it is, because somebody will need this.",
    "I say what I actually think is happening, even though I cannot prove it.",
    "I ask whether we are going to leave it here when we go.",
    "I take one last full-spectrum reading of the object before we break orbit.",
    "I write up the log entry, and I try to be honest in it about what we did not understand.",
]


# ---------------------------------------------------------------- seeding

def _configure(db_path):
    os.environ["ENGINE_DB"] = str(db_path)
    from core import db

    db.configure(str(db_path))
    db.init()
    return db


def _copy_providers(db, source_path):
    source = Path(source_path).expanduser().resolve()
    if not source.is_file():
        raise SystemExit("provider database not found: %s" % source)
    conn = sqlite3.connect("file:%s?mode=ro" % source, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id,name,kind,base_url,api_key,enabled FROM providers "
            "WHERE enabled=1 ORDER BY id").fetchall()
        if not rows:
            raise SystemExit("no enabled providers to copy")
        for row in rows:
            db.qi("INSERT INTO providers(id,name,kind,base_url,api_key,enabled)"
                  " VALUES(?,?,?,?,?,?)",
                  tuple(row[k] for k in ("id", "name", "kind", "base_url",
                                         "api_key", "enabled")))
        for key in ("agent_models", "reasoning_effort", "director_fanout_mode",
                    "attire_beneath", "llm_quality"):
            row = conn.execute("SELECT value FROM settings WHERE key=?",
                               (key,)).fetchone()
            if row is not None:
                db.set_setting(key, row["value"])
    finally:
        conn.close()
    print("providers copied: %d" % len(rows), flush=True)


def _borrow_role(db, role, source_role):
    """Point one model role at another's provider/model, in the scratch DB.

    Generation runs on the `utility` role. A reasoning model whose thinking
    budget can swallow the reply returns `ReasoningBudgetExhausted` from a
    call that has already been paid for -- which is a live configuration
    question, not an engine one, and belongs to the operator of the run.
    """
    models = json.loads(db.get_setting("agent_models") or "{}")
    if source_role not in models:
        raise SystemExit("no %r role to borrow from" % source_role)
    models[role] = dict(models[source_role])
    db.set_setting("agent_models", json.dumps(models))
    print("role %r borrowed from %r: %s" % (role, source_role, models[role]),
          flush=True)


def seed(args):
    db = _configure(args.db)
    _copy_providers(db, args.providers_from)
    if args.utility_from:
        _borrow_role(db, "utility", args.utility_from)

    book_id = db.qi(
        "INSERT INTO lorebooks(name,chat_id,book_type,summary) "
        "VALUES(?,?,?,?)",
        ("USS Enterprise NCC-1701-D", None, "general",
         "Galaxy-class Federation flagship: decks, departments, command crew "
         "and standing procedure."))
    for title, content, category in LORE:
        db.qi("INSERT INTO lore_entries(lorebook_id,keys,content,category,"
              "title,importance) VALUES(?,?,?,?,?,?)",
              (book_id, title, content, category, title, 5))
    print("lorebook %d seeded with %d entries" % (book_id, len(LORE)),
          flush=True)

    persona_id = db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        (PLAYER, json.dumps(PERSONA), "{}"))
    cid = db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id,lorebook_id,"
        "branched_from) VALUES(?,?,?,?,?,?)",
        ("Enterprise-D — the artifact", SCENARIO, time.time(), persona_id,
         book_id, "[]"))

    uids = {}
    for sheet in (PICARD, RIKER):
        name = sheet["identity"]["name"]
        uid = "enterprise-d-%s" % name.lower().replace(" ", "-").replace(".", "")
        char_id = db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (name, json.dumps(sheet), "{}", time.time(), uid))
        db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state,sheet) "
              "VALUES(?,?,?,'{}',NULL)", (cid, char_id, "active"))
        uids[name] = uid
        print("attached %s (char %d, uid %s)" % (name, char_id, uid),
              flush=True)

    # The living world, on the rungs this story actually needs: a ship whose
    # departments keep working while the player is on the bridge.
    db.wset(cid, "dialogue_config", {
        "offscreen_life": "reactive",
        "max_offscreen_actors": 3,
        "initial_parallel_reactors": 2,
        "autonomy": 55,
    })
    db.wset(cid, "living_world", {
        "routine_residue": "floor",
        "scheduled_consequence": "floor",
        "place_obligations": "floor",
        "antagonist_ladder": "floor",
    })
    db.wset(cid, "background_config", {"scene_life": "ambient",
                                       "max_reactors": 2, "max_managed": 6})
    db.wset(cid, "simulation_clock", {"elapsed_seconds": 0.0})

    print("story %d created; generating the ship..." % cid, flush=True)
    started = time.time()
    from language_runtime import story_language_scope
    from world.charter_runtime import generate_lived_location

    request = {
        "brief": (
            "The USS Enterprise NCC-1701-D, a Galaxy-class Federation "
            "starship on deep-space assignment, with her standing crew at "
            "their posts: command on the bridge, engineering around the warp "
            "core, medical in sickbay, sciences in the labs, security, "
            "operations, and the civilians and off-duty crew in Ten Forward "
            "and the quarters. Use the canonical senior officers named in the "
            "lore for the posts they actually hold, and generate ordinary "
            "junior officers, specialists, nurses and technicians around them "
            "for everything else."),
        "name": "USS Enterprise NCC-1701-D",
        # Six, not ten: `_json_call` caps `propose_town` at 6000 tokens and a
        # plan that overruns it surfaces as a JSONDecodeError, not a refusal.
        # The generator fills in support rooms around these anyway.
        "required_rooms": [
            "main bridge", "captain's ready room", "main engineering",
            "sickbay", "ten forward", "stellar cartography",
        ],
        "featured_residents": [dict(row) for row in SENIOR_STAFF[:5]],
        "character_histories": [
            {"resource_uid": uids["Jean-Luc Picard"],
             "mode": "moving_institution",
             "brief": "Captain. Preserve his rank, command of this ship, and "
                      "his standing relationships with the senior staff."},
            {"resource_uid": uids["William T. Riker"],
             "mode": "moving_institution",
             "brief": "First officer. Preserve his rank, his post, and that "
                      "he leads away teams."},
        ],
        "horizon_hours": 720,
        "active_tail_hours": 96,
        "generate_history": True,
        "window_hours": 6.0,
    }
    with story_language_scope(cid):
        result = generate_lived_location(cid, request)
    print("generation finished in %.1fs" % (time.time() - started), flush=True)
    print(json.dumps({k: v for k, v in result.items()
                      if k not in ("presim",)}, indent=1)[:2000], flush=True)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(
        {"chat_id": cid, "lorebook_id": book_id, "uids": uids,
         "generation": result}, indent=1, default=str), encoding="utf-8")
    print("\nSTORY %d READY -- open it in the UI to watch" % cid, flush=True)
    return cid


# ---------------------------------------------------------------- playing

def play(args):
    db = _configure(args.db)
    from agents.runtime import run_pipeline

    cid = args.chat
    if not cid:
        row = db.q("SELECT id FROM chats ORDER BY id DESC LIMIT 1", one=True)
        cid = int(row["id"])
    start = db.q("SELECT COALESCE(MAX(idx), -1) m FROM turns WHERE chat_id=?",
                 (cid,), one=True)["m"] + 1
    beats = BEATS[:args.turns]
    print("playing chat %d, turns %d..%d" % (cid, start, len(beats) - 1),
          flush=True)

    for idx in range(start, len(beats)):
        text = beats[idx]
        tid = db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
            "VALUES(?,?,?,?,?)", (cid, idx, text, time.time(), None))
        started = time.time()
        error = ""
        try:
            for _ in run_pipeline(cid, tid):
                pass
        except Exception as exc:  # noqa: BLE001 - a live run keeps going
            error = "%s: %s" % (type(exc).__name__, exc)
        row = db.q(
            "SELECT v.content FROM steps s JOIN variants v "
            "ON v.step_id=s.id AND v.active=1 "
            "WHERE s.turn_id=? AND s.key='narrator'", (tid,), one=True)
        prose = ""
        if row:
            try:
                prose = (json.loads(row["content"]) or {}).get("prose") or ""
            except (TypeError, ValueError):
                prose = ""
        print("\n=== turn %d (%.1fs)%s ===" % (
            idx, time.time() - started, "  ERROR: " + error if error else ""),
            flush=True)
        print("> %s" % text, flush=True)
        print(prose[:1200] or "(no narration)", flush=True)
    print("\ndone", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("seed")
    s.add_argument("--providers-from", default="engine.db")
    s.add_argument("--db", required=True)
    s.add_argument("--out", default="enterprise_seed.json")
    s.add_argument("--utility-from", default="",
                   help="point the `utility` role (generation) at another "
                        "role's model, e.g. `director`")
    s.set_defaults(fn=seed)

    p = sub.add_parser("play")
    p.add_argument("--db", required=True)
    p.add_argument("--chat", type=int, default=0)
    p.add_argument("--turns", type=int, default=50)
    p.set_defaults(fn=play)

    args = parser.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
