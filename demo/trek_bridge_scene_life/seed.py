"""Seed the Enterprise-D bridge scene-life test.

Picard is the ONLY registered character. The entire bridge crew is left to the
Director to invent as background presences -- the question being whether, given
an authorial canon licence in the style guide (§3.8.1), it generates the right
crew and gives them the right stations.

The player is a Starfleet observation officer: present, senior enough to be
tolerated, and mostly silent. That is deliberate -- a player who mainly watches
is the hardest case for the salience gate and the best case for the scene
manager.
"""
import json
import os
import sqlite3
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
# The repository root, derived from this file's own location. It was an
# absolute path naming a project that has since been renamed and a git
# worktree that no longer exists, so this script could not run anywhere.
ROOT = os.path.dirname(os.path.dirname(HERE))
RUN_DB = os.path.join(HERE, "run.db")
for suffix in ("", "-wal", "-shm"):
    if os.path.exists(RUN_DB + suffix):
        os.remove(RUN_DB + suffix)
os.environ["ENGINE_DB"] = RUN_DB
sys.path.insert(0, ROOT)

from core import db
from core.db import q, qi, set_setting, wset
from story.character_schema import normalize_character_data, character_name

db.configure(RUN_DB)
db.init()

# Read-only: this is the owner's live database and nothing here writes back.
src = sqlite3.connect("file:%s?mode=ro" % os.path.join(ROOT, "engine.db"),
                      uri=True)
src.row_factory = sqlite3.Row
prov = src.execute("SELECT * FROM providers WHERE name='nanogpt'").fetchone()
assert prov, "nanogpt provider not found"
qi("INSERT INTO providers(id,name,kind,base_url,api_key,enabled) VALUES(?,?,?,?,?,?)",
   (prov["id"], prov["name"], prov["kind"], prov["base_url"], prov["api_key"], 1))
src.close()

MODEL = {"provider": prov["id"], "model": "zai-org/glm-latest"}
set_setting("agent_models", json.dumps({
    r: dict(MODEL) for r in
    ("default", "director", "narrator", "perception", "character",
     "character_bg", "mapping", "generator", "lore", "memory")
}))
set_setting("auto_promote", "0")

persona = normalize_character_data({
    "identity": {"name": "Commander Sela Ndiaye",
                 "pronouns": {"subject": "she", "object": "her",
                              "possessive": "her"}},
    "embodiment": {"visible": {"summary": "A Starfleet commander in duty "
                                          "uniform, PADD always in hand, "
                                          "observer's insignia at the collar."}},
})
pid = qi("INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
         ("Commander Sela Ndiaye", json.dumps(persona), "{}"))

PICARD = normalize_character_data({
    "identity": {"name": "Jean-Luc Picard",
                 "pronouns": {"subject": "he", "object": "him",
                              "possessive": "his"}},
    "embodiment": {"visible": {
        "summary": "Bald, spare, straight-backed; a captain who occupies a "
                   "room without raising his voice."}},
    "psychology": {
        "traits": ["formal", "exacting about procedure", "dislikes being "
                   "observed at work", "protective of his crew's judgement"],
        "values": ["a captain answers for the ship", "an officer must be "
                   "allowed to be wrong in a drill"],
    },
    "competence": {"skills": ["command", "diplomacy", "tactical assessment",
                              "reading a bridge crew"]},
    "initial_state": {
        "mood": "composed, faintly irritated at the observation order",
        "goal": "run the exercise properly and let his officers make their "
                "own calls"},
})
cid_picard = qi(
    "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
    (character_name(PICARD), json.dumps(PICARD), "{}", time.time()))

CID = qi(
    "INSERT INTO chats(name,persona_id,lorebook_id,scenario,created) "
    "VALUES(?,?,?,?,?)",
    ("Enterprise bridge — scene life", pid, None,
     "The main bridge of the USS Enterprise-D, mid-watch. Captain Jean-Luc "
     "Picard is running a live tactical training exercise: the ship's systems "
     "are fed a simulated scenario while the full bridge crew works it in real "
     "time at their usual stations — first officer, operations, tactical, "
     "conn, engineering, counselor. Commander Sela Ndiaye is aboard from "
     "Starfleet Command as an observation officer, attached to this watch to "
     "evaluate bridge procedure. She is expected to watch and record, not to "
     "command. The crew know they are being graded.",
     time.time()))
assert CID == 1, CID

qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
   (CID, cid_picard, "active", "{}"))
qi("INSERT INTO chat_personas(chat_id,persona_id) VALUES(?,?)", (CID, pid))

wset(CID, "background_config", {"scene_life": "full", "max_managed": 6,
                                "max_reactors": 1})
# The authorial canon licence (§3.8.1): opt-in, explicit, and the ONLY thing
# that lets the engine reach for an established setting. Without this the
# standing no-outside-canon rule applies.
wset(CID, "style_guide", {
    "genre": "Star Trek: The Next Generation",
    "tone": "procedural, restrained, competent professionals under evaluation",
    "director_notes": "This is the USS Enterprise-D under Captain Picard. Use "
                      "the established senior staff at their usual stations. "
                      "Rank and procedure matter; officers address the captain "
                      "correctly and speak in station reports.",
    "avoid": "camp, technobabble for its own sake, anyone breaking discipline "
             "without cause",
})

print("seeded chat", CID, "| persona", pid, "| characters",
      [c["name"] for c in q("SELECT name FROM characters")])
