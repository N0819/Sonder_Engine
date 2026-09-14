"""A generated room that names a room the story has planned is that room.

Scratch play 2026-09-14, chat 5: the Writers' Room published the village's
rooms as a plan, then had the Charter Planner populate the same village; the
planner generated "The Boat Inn Taproom" again under its own id, both were
kept, the innkeeper stood in the copy and the player walked into the plan.
"""
import json
import time

from world.charter_runtime import _remap_generated_town


def _chat(db):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Blackwater", "", time.time()))
    db.qi("INSERT INTO room_registry(chat_id,room_uid,name,aliases,payload) "
          "VALUES(?,?,?,?,?)",
          (cid, "boat_inn_taproom", "The Boat Inn Taproom",
           json.dumps(["The Boat Inn Taproom", "boat inn taproom"]),
           json.dumps({"planned": {"name": "The Boat Inn Taproom"}})))
    turn_id = db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, 0, "", time.time()))
    db.qi("INSERT INTO room_registry(chat_id,room_uid,name,aliases,payload,"
          "created_turn_id) VALUES(?,?,?,?,?,?)",
          (cid, "lock_side", "Lock-side", json.dumps(["Lock-side"]),
           json.dumps({}), turn_id))
    return cid


def _town():
    return {"structure": {"key": "blackwater_village"},
            "rooms": {"the_boat_inn_taproom": {"name": "The Boat Inn Taproom",
                                               "adjacent": [{"to": "inn_yard"}]},
                      "inn_yard": {"name": "Inn Yard",
                                   "adjacent": [{"to": "the_boat_inn_taproom"}]}},
            "charters": {"the_boat_inn": {
                "key": "the_boat_inn", "upkeeps": {}, "priority": [],
                "posts": {"keep": {"place": "the_boat_inn_taproom",
                                   "serves": [], "requires": {}}},
                "bodies": {"hester": {"place": "the_boat_inn_taproom",
                                      "berth": "inn_yard"}}}}}


def test_the_planned_room_stands_and_the_bodies_stand_in_it(temp_db):
    cid = _chat(temp_db)
    town = _remap_generated_town(cid, _town(), {"items": {}})
    assert "the_boat_inn_taproom" not in town["rooms"]
    assert "boat_inn_taproom" not in town["rooms"]
    yard = next(iter(town["rooms"]))
    assert town["rooms"][yard]["adjacent"][0]["to"] == "boat_inn_taproom"
    charter = next(iter(town["charters"].values()))
    assert charter["bodies"]["hester"]["place"] == "boat_inn_taproom"
    assert charter["bodies"]["hester"]["berth"] == yard
    assert charter["posts"]["keep"]["place"] == "boat_inn_taproom"


def test_a_landed_room_of_the_same_name_is_not_merged(temp_db):
    cid = _chat(temp_db)
    town = _town()
    town["rooms"]["lock_side"] = {"name": "Lock-side", "adjacent": []}
    out = _remap_generated_town(cid, town, {"items": {}})
    assert "lock_side" not in out["rooms"]
    assert any(uid.endswith("lock_side") and uid != "lock_side"
               for uid in out["rooms"])
