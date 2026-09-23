"""Who told you a thing is said as you know them.

Playerless Aldermill round 8 (2026-09-23): the telling path records a
report's teller by canonical name, and Sal's character call carried
"told_by: Hostler Gidoton Barrelfielder" on all ten of her beats from idx 4 --
a name no channel ever gave her; her `known` ledger was empty. The name scrub
ran on lore and on her offscreen gap, never on what she carried.
"""
import time

from agents.character import tellers_as_known

TELLER = "Hostler Gidoton Barrelfielder"
REPORTS = [{"world_event_id": "e1", "claim": "No heavy team has come off the ford.",
            "told_by": TELLER, "retellings": 1}]
SCENE = {
    "rooms": {"inn_stables": {"name": "Inn Stables"}},
    "positions": {"Sal Weatherby": "inn_stables", TELLER: "inn_stables"},
    "entities": {TELLER: {"name": TELLER, "kind": "person",
                          "appearance": "a stooped hostler smelling of sweet hay",
                          "charter_ref": {"charter": "inn", "body": "hostler:0002"}}},
}


def _chat(db, known=None):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Aldermill", "", time.time()))
    if known is not None:
        db.wset(cid, "known", known)
    return {"id": cid, "persona_id": None}


def _shown(db, scene, known=None):
    return tellers_as_known(_chat(db, known), "Sal Weatherby", [], scene,
                            REPORTS)[0]["told_by"]


def test_a_teller_she_never_learned_is_not_named(temp_db):
    for scene in (SCENE, {"rooms": {}, "positions": {}, "entities": {}}):
        shown = _shown(temp_db, scene)
        assert shown.strip()
        assert "Gidoton" not in shown and "Barrelfielder" not in shown


def test_a_teller_she_knows_keeps_the_name(temp_db):
    assert _shown(temp_db, SCENE, {"Sal Weatherby": [TELLER]}) == TELLER


def test_the_stored_report_is_left_as_the_engine_wrote_it(temp_db):
    _shown(temp_db, SCENE)
    assert REPORTS[0]["told_by"] == TELLER
