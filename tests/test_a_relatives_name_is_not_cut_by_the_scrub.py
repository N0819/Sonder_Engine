"""A cast member's surname is never scrubbed out of a relative's name.

`observer_name_scrub` rewrites every form of an unmet cast member -- the bare
surname among them -- as a whole word, and a family shares a surname.
Measured (scratch story 165, turn 4582, 2026-10-07): public lore read "What
the town has to go on is Abel Gale's account"; the scrub for the unmet pilot
Hester GALE rewrote her surname inside her brother's name, the innkeeper was
handed "Abel the broad weather-worn woman's account", and told the player
"ask Abel, she's standing right there".

Adversarial in both directions: the relative's name survives whole, and the
cast member's own name is still scrubbed -- even where a plan carries it.
"""

import json
import time

from agents.common import observer_name_scrub
from core.db import wset_for_frame
from story.character_schema import default_character_data

TEXT = ("What the town has to go on is Abel Gale's account. "
        "Hester Gale piloted the lighter out at dawn; Gale knows the reach.")


def _chat_and_cast(db, *, plans):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Fen", "", time.time()))
    sheet = default_character_data("Hester Gale")
    sheet.setdefault("identity", {})["aliases"] = ["Gale"]
    key = db.qi("INSERT INTO characters(name,sheet,source,created,resource_uid) "
                "VALUES(?,?,?,?,?)",
                ("Hester Gale", json.dumps(sheet), "{}", time.time(), "hester"))
    db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
          (cid, key, "active", "{}"))
    wset_for_frame(cid, "planned_entities", plans, None)
    cast = db.q("SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
                "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (cid,))
    chat = dict(db.q("SELECT * FROM chats WHERE id=?", (cid,), one=True))
    return chat, cast


def _plan(uid, name):
    return {uid: {"uid": uid, "name": name, "kind": "person", "aliases": [],
                  "brief": {"where": "inn_common"}}}


def test_a_relatives_name_survives_and_the_unmet_name_does_not(temp_db):
    chat, cast = _chat_and_cast(temp_db, plans=_plan("plan:person:abel:1",
                                                     "Abel Gale"))
    out = observer_name_scrub(chat, "", cast)(TEXT)
    assert "Abel Gale's account" in out, out
    assert "Hester Gale" not in out and "Gale knows" not in out, out


def test_a_plan_under_the_cast_members_own_name_shields_nothing(temp_db):
    """The Writers' Room filed a plan under the PLAYER's name in the same
    run; a shield read off plans must never carry a scrubbed name past the
    floor."""
    plans = {**_plan("plan:person:abel:1", "Abel Gale"),
             **_plan("plan:person:hester:1", "Hester Gale")}
    chat, cast = _chat_and_cast(temp_db, plans=plans)
    out = observer_name_scrub(chat, "", cast)(TEXT)
    assert "Hester Gale" not in out, out
    assert "Abel Gale's account" in out, out
