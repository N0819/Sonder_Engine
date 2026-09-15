"""Two generated rooms under one folded name are one room, and a featured
resident stands the post their role names.

Scratch play 2026-09-14, chat 8 "Wendover Assembly": the Charter Planner
answered a brief naming nine places with nineteen rooms -- the author's id
and its own "the_" spelling for each, one name apiece -- and put "Bragg the
landlord" and "Mr Pellew the master of ceremonies" under the inn-maid post
while its own minted names held the landlord's and the master's.
"""

import time

from world.charter_generate import _featured_assignments
from world.charter_runtime import _merge_town_rooms_by_name, _remap_generated_town


def _town():
    return {"structure": {"key": "wendover"}, "rooms": {
        "ballroom": {"name": "The Assembly Ballroom",
                     "adjacent": [{"to": "card_room", "barrier": "open"}]},
        "the_assembly_ballroom": {"name": "The Assembly Ballroom",
                                  "adjacent": [{"to": "main_stair", "barrier": "open"}]},
        "card_room": {"name": "The Card Room", "adjacent": [{"to": "ballroom"}]},
        "main_stair": {"name": "The Main Staircase",
                       "adjacent": [{"to": "the_assembly_ballroom"}]},
    }, "charters": {"assembly": {"key": "assembly", "posts": {
        "master": {"place": "ballroom", "serves": []}}, "bodies": {
        "master:0001": {"place": "ballroom", "berth": "ballroom", "available": True}},
        "upkeeps": {}}}}


def test_the_authors_id_is_kept_and_the_twin_dropped():
    assert _merge_town_rooms_by_name(_town(), pinned=("ballroom",)) == {
        "the_assembly_ballroom": "ballroom"}


def test_without_a_pin_the_room_somebody_stands_in_is_kept():
    assert _merge_town_rooms_by_name(_town()) == {"the_assembly_ballroom": "ballroom"}


def test_the_landed_town_carries_the_twins_doorways(temp_db):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Wendover", "", time.time()))
    town = _remap_generated_town(cid, _town(), {"items": {}}, pinned=("ballroom",))
    assert "the_assembly_ballroom" not in town["rooms"]
    ballroom = {e["to"] for e in town["rooms"]["ballroom"]["adjacent"]}
    assert ballroom == {"card_room", "main_stair"}
    stair = {e["to"] for e in town["rooms"]["main_stair"]["adjacent"]}
    assert stair == {"ballroom"}
    body = town["charters"]["assembly"]["bodies"]["master:0001"]
    assert body["place"] == "ballroom"


def test_a_resident_stands_the_post_their_role_names():
    plan = {"charters": [
        {"key": "crown", "posts": {"landlord": {}, "inn_maid": {}, "ostler": {}},
         "featured_residents": [{"seed_id": "authored:bragg", "post": "inn_maid"},
                                {"seed_id": "authored:betty", "post": "inn_maid"}]},
        {"key": "assembly", "posts": {"master_of_ceremonies": {}, "matron": {}},
         "featured_residents": []},
    ]}
    residents = [
        {"seed_id": "authored:bragg", "name": "Bragg", "role": "the landlord"},
        {"seed_id": "authored:betty", "name": "Betty", "role": "a maid"},
        {"seed_id": "authored:pellew", "name": "Mr Pellew",
         "role": "the master of ceremonies"},
        {"seed_id": "authored:dacre", "name": "Mrs Dacre", "role": "a matron"},
    ]
    _sources, assigned = _featured_assignments(plan, residents)
    got = {seed: (ci, row["post"]) for seed, (ci, row) in assigned.items()}
    assert got["authored:bragg"] == (0, "landlord")
    assert got["authored:betty"] == (0, "inn_maid")
    assert got["authored:pellew"] == (1, "master_of_ceremonies")
    assert got["authored:dacre"] == (1, "matron")
