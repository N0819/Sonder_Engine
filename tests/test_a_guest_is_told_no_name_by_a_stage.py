"""The guest's payload names no stage by a name the story filled in.

`guest_state` sent each turn's earliest stale step as `stale_from` with its
stored `key` and `label`, and a character's step is labelled
"Character · <true name>" (`agents.runtime.STEP_LABELS`, filled at plan time)
and keyed `character:<row id>`. A guest whose persona knew a woman only as
"the hooded woman" was sent her name on every ten-second poll (audit
2026-11-01, web_app F4 / web_routes_extensions F8); an extension's stage was
sent as "Extension · <id> · <key>", its campaign internals. The page no
longer prints either (frontend_core F1); the server stops sending them, so an
older page still open, or any other reader of the route, cannot either.

The guest is told the stage's PHASE in the engine's own words -- the table's
name for the step's family, with nothing filled in from the story -- and the
key's family, never its id.
"""
from __future__ import annotations

import json
import time
from types import SimpleNamespace


def _story(db):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Harbour", "", time.time()))
    pid = db.qi("INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
                ("Guest", "{}", "{}"))
    db.qi("INSERT INTO chat_personas(chat_id,persona_id,status) VALUES(?,?,'active')",
          (cid, pid))
    return cid, pid


def _turn(db, cid, idx, steps):
    tid = db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
                (cid, idx, "", time.time()))
    for order, (key, label, stale, content) in enumerate(steps):
        sid = db.qi("INSERT INTO steps(turn_id,key,ord,label,stale) VALUES(?,?,?,?,?)",
                    (tid, key, order, label, stale))
        db.qi("INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
              (sid, json.dumps(content), time.time()))
    return tid


def _guest(cid, pid):
    return SimpleNamespace(state=SimpleNamespace(
        guest_grant={"chat_id": cid, "persona_id": pid}))


def test_a_stale_character_step_is_named_by_its_phase_alone(temp_db):
    from web import app

    cid, pid = _story(temp_db)
    _turn(temp_db, cid, 0, [
        ("perception_act", "Perception · pass 1 — the act", 0, {}),
        ("character:12", "Character · Mirelle Sulmirath", 1, {}),
        ("narrator_extra", "Narrator · render (other players)", 1,
         {str(pid): {"prose": "The hooded woman turns."}}),
    ])
    state = app.guest_state(_guest(cid, pid))
    wire = json.dumps(state)
    assert "Mirelle" not in wire and "character:12" not in wire
    assert state["turns"][0]["stale_from"] == {
        "ord": 1, "key": "character", "label": "Character"}
    assert state["turns"][0]["prose"] == "The hooded woman turns."


def test_an_extension_stage_is_named_by_nothing_it_authored(temp_db):
    from web import app

    cid, pid = _story(temp_db)
    _turn(temp_db, cid, 0, [
        ("ext:campaign:reveal", "Extension · campaign · reveal the heir", 1, {}),
        ("narrator_extra", "Narrator · render (other players)", 0,
         {str(pid): {"prose": "Rain."}}),
    ])
    stale_from = app.guest_state(_guest(cid, pid))["turns"][0]["stale_from"]
    assert "campaign" not in json.dumps(stale_from)
    assert stale_from["key"] == "ext"


def test_a_core_stage_keeps_the_engines_name_for_it(temp_db):
    from agents.runtime import STEP_LABELS
    from web import app

    cid, pid = _story(temp_db)
    _turn(temp_db, cid, 0, [
        ("director_resolve", "Director · resolve", 1, {}),
        ("narrator_extra", "Narrator · render (other players)", 1,
         {str(pid): {"prose": "Rain."}}),
    ])
    stale_from = app.guest_state(_guest(cid, pid))["turns"][0]["stale_from"]
    assert stale_from == {"ord": 0, "key": "director_resolve",
                          "label": STEP_LABELS["director_resolve"]}
