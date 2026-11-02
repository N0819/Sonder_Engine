"""A location generated into a story merges only into ITS OWN planned rooms.

`_merge_generated_rooms_by_name` matched a generated room against every
unlanded planned room of the chat by name, with no building scope, so a new
inn's "Kitchen" became the manor's planned kitchen and the inn's cook went
to work in the manor (audit world_charter_core F11, reproduced:
`{'lamb_flag_kitchen': 'manor_kitchen', 'lamb_flag_hall':
'manor_great_hall', ...}`). Two rooms of two different known structures are
never one room; and a name is compared in the parts its own script writes it
in, so a Japanese name merges by its words as an English one does."""
import json
import time

from world.charter_runtime import _merge_generated_rooms_by_name


def _plan_room(db, cid, uid, name, structure):
    db.qi("INSERT INTO room_registry(chat_id,room_uid,name,aliases,payload) "
          "VALUES(?,?,?,?,?)",
          (cid, uid, name, "[]", json.dumps({"name": name,
                                             "structure": structure})))


def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Town", "", time.time()))


def test_another_buildings_planned_kitchen_is_not_this_inns(temp_db):
    cid = _chat(temp_db)
    _plan_room(temp_db, cid, "manor_kitchen", "Kitchen", "manor")
    town = {"structure": {"key": "lamb_flag"},
            "rooms": {"lamb_flag_kitchen": {"name": "Kitchen"},
                      "lamb_flag_taproom": {"name": "Taproom"}}}
    assert _merge_generated_rooms_by_name(cid, town, ()) == {}


def test_its_own_planned_room_is_still_landed_under_its_plan(temp_db):
    cid = _chat(temp_db)
    _plan_room(temp_db, cid, "lamb_flag_yard", "The Lamb and Flag Yard",
               "lamb_flag")
    town = {"structure": {"key": "lamb_flag"},
            "rooms": {"lamb_and_flag_yard": {"name": "Lamb and Flag Yard"},
                      "lamb_and_flag_taproom": {"name": "Taproom"}}}
    assert _merge_generated_rooms_by_name(cid, town, ()) == {
        "lamb_and_flag_yard": "lamb_flag_yard"}


def test_a_japanese_name_merges_by_its_words(temp_db):
    cid = _chat(temp_db)
    _plan_room(temp_db, cid, "shrine_court", "神社の境内", "shrine")
    town = {"structure": {"key": "shrine"},
            "rooms": {"shrine_precinct": {"name": "境内 神社の"},
                      "shrine_hall": {"name": "本殿"}}}
    assert _merge_generated_rooms_by_name(cid, town, ()) == {
        "shrine_precinct": "shrine_court"}
