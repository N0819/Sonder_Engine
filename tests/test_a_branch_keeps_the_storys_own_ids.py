"""A copy of a story keeps the ids that are the story's own.

`turn_branch` minted a fresh hex id for every `world_entities`,
`world_conditions`, `scheduled_events` and `world_events` id and then
rewrote EVERY string equal to one of them, anywhere in the world -- because
those tables once had global primary keys. They are `(chat_id, id)` since
v14/v16/v27, so the remap bought nothing and cost the fiction: an entity
keyed `door` turned every `barrier: "door"` into `6f6bd862658d41d6`, a
garment string equal to an entity id became hex (audit 2026-11-01,
persistence F10), and an authored event's idempotent id became random, so the
Director re-asserting it minted a second copy (story_scene_schema F3).

Only two world tables still have a GLOBAL key -- the deprecated
`fiction_worlds` and `fiction_locations` -- and a copy inside one install
must give their rows fresh ids or the insert collides: importing a story the
install still holds failed with `UNIQUE constraint failed:
fiction_worlds.world_id` (persistence F9). Those ids are rewritten only where
those rows name them, in the live tables and in every checkpoint alike.
"""

from __future__ import annotations

import json
import time

from core.db import wset
from persist.checkpoints import ensure_checkpoint, restore_checkpoint


def _story(db):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Inn", "", time.time()))
    wset(cid, "scene", {
        "rooms": {"hall": {"exits": {"north": {"to": "yard", "barrier": "door",
                                                "state": "closed"}}},
                  "yard": {}},
        "entities": {"door": {"name": "Door", "kind": "object"},
                     "lantern": {"name": "Lantern", "kind": "object"}},
        "attire": {"Mora": {"hands": {"garments": ["lantern"]}}},
        "positions": {"Mora": "hall"},
    })
    db.qi("INSERT INTO world_entities(entity_id,chat_id,kind,name,payload) "
          "VALUES(?,?,?,?,?)", ("door", cid, "object", "Door", "{}"))
    db.qi("INSERT INTO world_entities(entity_id,chat_id,kind,name,payload) "
          "VALUES(?,?,?,?,?)", ("lantern", cid, "object", "Lantern", "{}"))
    db.qi("INSERT INTO scheduled_events(event_id,chat_id,due_at,kind,payload,seed,status) "
          "VALUES(?,?,?,?,?,?,?)",
          ("authored:0123456789abcdef0123", cid, 50.0, "authored",
           json.dumps({"summary": "the bell rings at noon"}), "s", "pending"))
    turn = db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
                 (cid, 0, "begin", time.time()))
    ensure_checkpoint(cid, 1)
    return cid, turn


def test_a_branch_rewrites_no_word_that_happens_to_be_an_entity_id(temp_db):
    from web import app

    cid, turn = _story(temp_db)
    ncid = app.turn_branch(turn)["id"]

    scene = json.loads(temp_db.q("SELECT value FROM world WHERE chat_id=? AND key='scene'",
                                 (ncid,), one=True)["value"])
    assert scene["rooms"]["hall"]["exits"]["north"]["barrier"] == "door"
    assert scene["attire"]["Mora"]["hands"]["garments"] == ["lantern"]
    assert set(scene["entities"]) == {"door", "lantern"}
    assert sorted(r["entity_id"] for r in temp_db.q(
        "SELECT entity_id FROM world_entities WHERE chat_id=?", (ncid,))) == ["door", "lantern"]
    for row in temp_db.q("SELECT blob FROM checkpoints WHERE chat_id=?", (ncid,)):
        blob = json.loads(row["blob"])
        assert blob["world"]["scene"]["rooms"]["hall"]["exits"]["north"]["barrier"] == "door"


def test_a_branch_keeps_an_authored_events_id(temp_db):
    from web import app

    cid, turn = _story(temp_db)
    ncid = app.turn_branch(turn)["id"]

    assert [r["event_id"] for r in temp_db.q(
        "SELECT event_id FROM scheduled_events WHERE chat_id=?", (ncid,))] == [
        "authored:0123456789abcdef0123"]


def test_the_branch_remap_holds_only_the_global_keys(temp_db):
    from web.app import _build_world_id_remap

    blob = {"world_entities": [{"entity_id": "door"}],
            "world_conditions": [{"condition_id": "cond_1"}],
            "scheduled_events": [{"event_id": "evt_1"}],
            "world_events": [{"event_id": "evt_2"}],
            "fiction_worlds": [{"world_id": "w_old"}],
            "fiction_locations": [{"location_id": "l_old", "world_id": "w_old"}]}
    remap = _build_world_id_remap(blob)
    assert set(dict(remap)) == {"w_old", "l_old"}


def _with_a_fiction_world(db, cid):
    db.qi("INSERT INTO fiction_worlds(world_id,chat_id,name,kind,payload) "
          "VALUES(?,?,?,?,?)", ("w_old_1", cid, "Old world", "world", "{}"))
    db.qi("INSERT INTO fiction_locations(location_id,chat_id,world_id,name,kind,payload) "
          "VALUES(?,?,?,?,?,?)", ("l_old_1", cid, "w_old_1", "Old town", "location", "{}"))


def test_an_import_of_a_story_this_install_still_holds_gives_the_global_keys_fresh_ids(temp_db):
    from web import app

    cid, _turn = _story(temp_db)
    _with_a_fiction_world(temp_db, cid)
    ensure_checkpoint(cid, 0)
    archive = json.loads(json.dumps(app.chat_export(cid)))

    nx = app.chat_import({"data": archive})["id"]

    worlds = temp_db.q("SELECT world_id FROM fiction_worlds WHERE chat_id=?", (nx,))
    places = temp_db.q("SELECT location_id, world_id FROM fiction_locations WHERE chat_id=?", (nx,))
    assert len(worlds) == 1 and worlds[0]["world_id"] != "w_old_1"
    assert places[0]["world_id"] == worlds[0]["world_id"], "the row's own reference follows"
    restore_checkpoint(nx, 0)      # the imported checkpoint names the same fresh ids
    assert [r["world_id"] for r in temp_db.q(
        "SELECT world_id FROM fiction_worlds WHERE chat_id=?", (nx,))] == [worlds[0]["world_id"]]


def test_a_branchs_older_checkpoint_holding_a_global_key_the_branch_point_lost_restores(temp_db):
    from web import app

    cid, turn = _story(temp_db)
    _with_a_fiction_world(temp_db, cid)
    ensure_checkpoint(cid, 0)                       # holds w_old_1
    temp_db.qi("DELETE FROM fiction_locations WHERE chat_id=?", (cid,))
    temp_db.qi("DELETE FROM fiction_worlds WHERE chat_id=?", (cid,))
    temp_db.qi("DELETE FROM checkpoints WHERE chat_id=? AND turn_idx=1", (cid,))
    ensure_checkpoint(cid, 1)                       # the branch point: none
    _with_a_fiction_world(temp_db, cid)             # the source holds it again

    ncid = app.turn_branch(turn)["id"]
    restore_checkpoint(ncid, 0)

    assert [r["world_id"] for r in temp_db.q(
        "SELECT world_id FROM fiction_worlds WHERE chat_id=?", (ncid,))] != ["w_old_1"]
