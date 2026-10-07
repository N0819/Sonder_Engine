"""A tie from before the story is recognition, both ways.

Owner ruling, 2026-10-07. Until now only an in-play introduction wrote the
`known` ledger, so nothing authored before the story could make two people
know each other. Measured (scratch story 165, turn 4584): the pilot Hester
Gale called her own brother an impostor -- "That's not Abel. Abel Gale is my
brother ... This man's a stranger to me" -- because the Writers' Room had
planned him at the inn and nothing said she had known his face since before
either of them could walk. A plan now names the cast who know the person
from before (`known_by`), and publishing writes `known` both ways.
"""

import json
import time

from core.db import wget
from story.character_schema import default_character_data, default_persona_data
from story.plot_packages import (draft_operation, get_package, new_package,
                                 preview_package, publish_package,
                                 validate_package)
from world.planned_entities import planned_entities

ROOM = "quay"


def _story(db):
    pid = db.qi("INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
                ("Tamsin Coyle", json.dumps(default_persona_data("Tamsin Coyle")),
                 "{}"))
    cid = db.qi("INSERT INTO chats(name,scenario,created,persona_id) "
                "VALUES(?,?,?,?)", ("Fen", "", time.time(), pid))
    key = db.qi("INSERT INTO characters(name,sheet,source,created,resource_uid) "
                "VALUES(?,?,?,?,?)",
                ("Hester Gale", json.dumps(default_character_data("Hester Gale")),
                 "{}", time.time(), "hester"))
    db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
          (cid, key, "active", "{}"))
    db.wset(cid, "scene", {"location": "Fen", "rooms": {
        ROOM: {"name": "Quay", "desc": "Wet stone.", "adjacent": []}},
        "positions": {"Tamsin Coyle": ROOM}, "entities": {}, "attire": {}})
    for idx in range(3):
        db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
              "VALUES(?,?,?,?)", (cid, idx, "", time.time()))
    return cid


def _plan(cid, known_by):
    pkg = new_package(cid, title="The Gales", premise="Her brother is here.")
    draft_operation(cid, pkg["uid"], {
        "op": "plan_entity", "name": "Abel Gale", "kind": "person",
        "role": "bargeman", "known_by": known_by,
        "brief": {"purpose": "Hester's younger brother", "where": ROOM}})
    return pkg["uid"]


def _publish(cid, uid):
    validate_package(cid, uid)
    return publish_package(cid, uid,
                           expected_revision=get_package(cid, uid)["revision"])


def test_a_sister_and_her_brother_know_each_other(temp_db):
    cid = _story(temp_db)
    uid = _plan(cid, ["Hester Gale"])
    assert preview_package(cid, uid)["errors"] == []
    _publish(cid, uid)
    known = wget(cid, "known", {})
    assert "Abel Gale" in known["Hester Gale"]
    assert "Hester Gale" in known["Abel Gale"]
    plan = next(p for p in planned_entities(cid).values()
                if p["name"] == "Abel Gale")
    assert plan["known_by"] == ["Hester Gale"]


def test_the_player_is_named_by_the_truths_own_word(temp_db):
    cid = _story(temp_db)
    _publish(cid, _plan(cid, ["player"]))
    known = wget(cid, "known", {})
    assert "Abel Gale" in known["Tamsin Coyle"]
    assert "Tamsin Coyle" in known["Abel Gale"]


def test_a_tie_to_nobody_the_story_holds_is_refused(temp_db):
    cid = _story(temp_db)
    errors = preview_package(cid, _plan(cid, ["Nobody Here"]))["errors"]
    assert any("Nobody Here" in e and "not a registered character" in e
               for e in errors)


def test_a_plan_with_no_tie_writes_no_recognition(temp_db):
    cid = _story(temp_db)
    _publish(cid, _plan(cid, []))
    assert "Abel Gale" not in (wget(cid, "known", {}) or {})
