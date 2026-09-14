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


def test_an_unnamed_generated_room_matches_the_plans_room_by_its_words(temp_db):
    """Chat 6: the planner minted `lamb_flag_yard` and `lamb_flag_taproom`
    with no names at all for the plan's "The Lamb and Flag Yard" and "The
    Taproom"; the content words are the same set."""
    cid = _chat(temp_db)
    temp_db.qi("INSERT INTO room_registry(chat_id,room_uid,name,aliases,payload) "
               "VALUES(?,?,?,?,?)",
               (cid, "inn_yard", "The Lamb and Flag Yard",
                json.dumps(["The Lamb and Flag Yard"]), json.dumps({"planned": {}})))
    temp_db.qi("INSERT INTO room_registry(chat_id,room_uid,name,aliases,payload) "
               "VALUES(?,?,?,?,?)",
               (cid, "taproom", "The Taproom", json.dumps(["The Taproom"]),
                json.dumps({"planned": {}})))
    town = {"structure": {"key": "lamb_flag"},
            "rooms": {"lamb_flag_yard": {"name": "lamb_flag_yard", "adjacent": []},
                      "lamb_flag_taproom": {"name": "lamb_flag_taproom", "adjacent": []},
                      "lamb_flag_cellar": {"name": "lamb_flag_cellar", "adjacent": []}},
            "charters": {"inn": {"key": "inn", "upkeeps": {}, "priority": [],
                                 "posts": {},
                                 "bodies": {"kit": {"place": "lamb_flag_taproom",
                                                    "berth": "lamb_flag_cellar"}}}}}
    out = _remap_generated_town(cid, town, {"items": {}})
    charter = next(iter(out["charters"].values()))
    assert charter["bodies"]["kit"]["place"] == "taproom"
    assert "lamb_flag_yard" not in out["rooms"] and "lamb_flag_taproom" not in out["rooms"]
    assert charter["bodies"]["kit"]["berth"] in out["rooms"]
