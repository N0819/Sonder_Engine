"""A cast member's family name is never scrubbed out of a relative's name
written without spaces.

`_other_peoples_names` shields the full names of other people while
`observer_name_scrub` rewrites an unmet cast member's forms (the English
case: "Abel Gale's account" became "Abel the broad weather-worn woman's
account", scratch story 165 turn 4582). It took only a name with a SPACE in
it, and split the subjects' forms into words by whitespace, so 佐藤アベル was
never shielded and the scrub for the unmet 佐藤ヒナミ (aliased 佐藤) cut into
it (agents_common audit F14). Parts of an unspaced name are its script runs.
"""

import json
import time

from language_runtime import language_scope

from agents.common import observer_name_scrub
from core.db import wset_for_frame
from story.character_schema import default_character_data

TEXT = "町が頼りにしているのは佐藤アベルの話だ。佐藤は夜明けに船を出した。"


def _chat_and_cast(db):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Fen", "", time.time()))
    sheet = default_character_data("佐藤ヒナミ")
    sheet.setdefault("identity", {})["aliases"] = ["佐藤"]
    key = db.qi("INSERT INTO characters(name,sheet,source,created,resource_uid) "
                "VALUES(?,?,?,?,?)",
                ("佐藤ヒナミ", json.dumps(sheet), "{}", time.time(), "hinami"))
    db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
          (cid, key, "active", "{}"))
    wset_for_frame(cid, "planned_entities", {"plan:person:abel:1": {
        "uid": "plan:person:abel:1", "name": "佐藤アベル", "kind": "person",
        "aliases": [], "brief": {"where": "inn_common"}}}, None)
    cast = db.q("SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
                "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (cid,))
    chat = dict(db.q("SELECT * FROM chats WHERE id=?", (cid,), one=True))
    return chat, cast


def test_a_relatives_unspaced_name_survives_and_the_unmet_name_does_not(temp_db):
    chat, cast = _chat_and_cast(temp_db)
    with language_scope("ja"):
        out = observer_name_scrub(chat, "", cast)(TEXT)
    assert "佐藤アベルの話" in out, out
    assert "佐藤は夜明け" not in out, out
