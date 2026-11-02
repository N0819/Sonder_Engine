"""A charter skip ends where the mind's last stretch put it, and a stretch
the town's grid never stepped is still the mind's own doing.

The town picks a window's directive by the stretch speaking at the window's
middle, so a final stretch shorter than half the last window -- every
`at_the_end` stretch (`skip_itinerary.AT_THE_END_SECONDS`, 30 minutes)
whenever the last window ran over an hour -- held no window at all: the town
never walked the body there, `far_end` reported the PENULTIMATE stretch's
room while the log's last row named the declared one, and the mind was
upstairs when the story resumed (audit world_charter_generation_run F2,
probed: span 08:00-21:00, tavern 0-12.5 h then house_a 12.5-13 h, far end
`tavern`). The stage's own executor ends at the last row
(`skip_itinerary.far_end_of`); the two now agree.

And the row itself read `not_known` -- "set about it, and the rest was out
of Mara's hands" -- because the grid had not stepped it (F5). The town not
watching is not the world's to judge: the ruling of 4d398090 for a stretch
off the map, one case over. It goes through `stretch_outcome` like any
other, routed by a check from where the body stood."""
from __future__ import annotations

import copy
import json
import time
import uuid

from charter_worlds import small_town
from story.character_schema import default_character_data
from world.charter_model import normalize_charter
from world.charter_needs import seed_needs
from world.charter_roster import seed_roster
from world.charter_runtime import save_registry
from world.charter_skip import live_in_charter

H = 3600.0


def _town(rooms=None):
    town = small_town()
    if rooms is not None:
        town["scene"] = {"rooms": copy.deepcopy(rooms)}
    for key, body in town["bodies"].items():
        body["name"] = "Folk %s" % key
    town = normalize_charter(town)
    town["roster"] = seed_roster(town["bodies"])
    town["needs"] = seed_needs(town["bodies"])
    return town


def _story(temp_db, rooms=None):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Skip", "", time.time()))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Mara", json.dumps(default_character_data("Mara")), "{}",
         time.time(), "char_mara_%s" % uuid.uuid4().hex[:8]))
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
               "VALUES(?,?,?,?)", (cid, char_id, "active", "{}"))
    rooms = copy.deepcopy(rooms or small_town()["scene"]["rooms"])
    scene = {"rooms": rooms, "positions": {"Mara": "square"}}
    temp_db.wset(cid, "scene", scene)
    temp_db.wset(cid, "simulation_clock", {
        "elapsed_seconds": 0.0, "anchor_hour": 8.0, "day_length_hours": 24.0})
    save_registry(cid, {"version": 1, "items": {"small_town": {
        "state": _town(rooms), "last_elapsed_seconds": 0.0}}})
    return cid, scene


def _stretch(a, b, room, doing, asleep=False):
    return {"from_s": a * H, "until_s": b * H, "room": room, "away": None,
            "where_text": room, "doing": doing, "asleep": asleep,
            "with": [], "why": "", "uses": []}


SPAN = {"from_s": 0.0, "until_s": 13 * H}       # 08:00 -> 21:00


def test_the_far_end_is_the_last_stretchs_room(temp_db):
    cid, scene = _story(temp_db)
    day = [_stretch(0, 12.5, "tavern", "Drink by the fire"),
           _stretch(12.5, 13, "house_a", "Sit by her own hearth with tea")]
    log, far = live_in_charter(cid, scene, "Mara", day, SPAN)
    assert log[-1]["room"] == "house_a"
    assert far["room"] == "house_a"
    assert log[-1]["outcome"] == "done"


def test_a_final_sleep_is_slept_in_its_bed(temp_db):
    cid, scene = _story(temp_db)
    day = [_stretch(0, 12.5, "tavern", "Drink by the fire"),
           _stretch(12.5, 13, "house_a", "Sleep", asleep=True)]
    log, far = live_in_charter(cid, scene, "Mara", day, SPAN)
    assert far["room"] == "house_a" and far["asleep"]
    assert log[-1]["outcome"] == "done"


def test_an_unstepped_stretch_it_cannot_reach_fails_and_the_body_stays(
        temp_db):
    rooms = copy.deepcopy(small_town()["scene"]["rooms"])
    for x, y in (("north_2", "house_a"), ("house_a", "north_2")):
        for edge in rooms[x]["adjacent"]:
            if edge["to"] == y:
                edge["barrier"] = "locked_door"
    cid, scene = _story(temp_db, rooms=rooms)
    day = [_stretch(0, 12.5, "tavern", "Drink by the fire"),
           _stretch(12.5, 13, "house_a", "Sit by her own hearth with tea")]
    log, far = live_in_charter(cid, scene, "Mara", day, SPAN)
    assert log[-1]["outcome"] == "failed"
    assert log[-1]["reason"] == "shut_way"
    assert far["room"] == "tavern"
