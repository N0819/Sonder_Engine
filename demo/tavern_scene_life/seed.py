"""Seed the tavern scene-life test chat.

Two full party characters walk into a tavern whose entire populace is left to
the Director/mapping agents to invent on the fly. The scene manager
(docs/BACKGROUND_LIFE_DESIGN.md §3.10) is enabled at `full` so the whole
populace is voiced by one batched call per beat.
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

# ---- provider, copied from the real engine.db (never written back) ----
# Read-only: this is the owner's live database and nothing here writes back.
src = sqlite3.connect("file:%s?mode=ro" % os.path.join(ROOT, "engine.db"),
                      uri=True)
src.row_factory = sqlite3.Row
prov = src.execute("SELECT * FROM providers WHERE name='nanogpt'").fetchone()
assert prov, "nanogpt provider not found in engine.db"
qi("INSERT INTO providers(id,name,kind,base_url,api_key,enabled) VALUES(?,?,?,?,?,?)",
   (prov["id"], prov["name"], prov["kind"], prov["base_url"], prov["api_key"], 1))
src.close()

MODEL = {"provider": prov["id"], "model": "zai-org/glm-latest"}
set_setting("agent_models", json.dumps({
    r: dict(MODEL) for r in
    ("default", "director", "narrator", "perception", "character",
     "character_bg", "mapping", "generator", "lore", "memory")
}))
# Auto-promotion off: ambient chatter currently accrues dialogue_turns, so a
# barfly would auto-promote mid-test and confound the thing being measured.
set_setting("auto_promote", "0")

# ---- persona (the player) ----
persona = normalize_character_data({
    "identity": {"name": "Kessa Vane",
                 "pronouns": {"subject": "she", "object": "her",
                              "possessive": "her"}},
    "embodiment": {"visible": {"summary": "A wiry woman in a road-stained "
                                          "cloak, shortsword at her hip."}},
})
pid = qi("INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
         ("Kessa Vane", json.dumps(persona), "{}"))

# ---- the party: two full characters ----
PARTY = [
    {
        "identity": {"name": "Bran Holt",
                     "pronouns": {"subject": "he", "object": "him",
                                  "possessive": "his"}},
        "embodiment": {"visible": {
            "summary": "A big man gone slightly to seed, greying beard, "
                       "a bandaged left hand."}},
        "psychology": {
            "traits": ["blunt", "sentimental when drunk", "hates being managed"],
            "values": ["never leave a debt unpaid"],
        },
        "competence": {"skills": ["axe", "tracking", "haggling badly"]},
        "initial_state": {"mood": "sore and thirsty",
                          "goal": "get a drink and a bed before talking shop"},
    },
    {
        "identity": {"name": "Ysolde Marr",
                     "pronouns": {"subject": "she", "object": "her",
                                  "possessive": "her"}},
        "embodiment": {"visible": {
            "summary": "Small, sharp-featured, ink on her fingers, a "
                       "travelling scholar's satchel."}},
        "psychology": {
            "traits": ["needling", "curious to a fault", "cannot let a "
                       "wrong claim stand"],
            "values": ["knowing more than she lets on"],
        },
        "competence": {"skills": ["old languages", "reading a room", "lockpicking"]},
        "initial_state": {"mood": "wound up from the road",
                          "goal": "find out what the locals know about the barrow"},
    },
]

CID = qi(
    "INSERT INTO chats(name,persona_id,lorebook_id,scenario,created) "
    "VALUES(?,?,?,?,?)",
    ("Tavern — scene life", pid, None,
     "Kessa Vane and her two companions, Bran Holt and Ysolde Marr, push into "
     "the common room of a busy roadside tavern at the edge of the moors. They "
     "have been three days on the road and mean to raid a barrow in the "
     "morning. The place is full: locals at the tables, someone behind the bar, "
     "the usual hangers-on. Nobody here is expecting them.",
     time.time()))
assert CID == 1, CID

for sheet in PARTY:
    s = normalize_character_data(sheet)
    cid_char = qi("INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
                  (character_name(s), json.dumps(s), "{}", time.time()))
    qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
       (CID, cid_char, "active", "{}"))

qi("INSERT INTO chat_personas(chat_id,persona_id) VALUES(?,?)", (CID, pid))

# ---- the feature under test ----
wset(CID, "background_config", {"scene_life": "full", "max_managed": 6,
                                "max_reactors": 1})
wset(CID, "style_guide", {"genre": "grounded low fantasy",
                          "tone": "dry, lived-in, unromantic",
                          "avoid": "epic register, prophecy, chosen ones"})

print("seeded chat", CID, "persona", pid,
      "party", [c["name"] for c in q("SELECT name FROM characters")])
