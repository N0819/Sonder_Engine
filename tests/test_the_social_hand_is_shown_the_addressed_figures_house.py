"""A hand addressed through a figure is shown that figure's house.

Scratch play 2026-09-14, chat 9 turn 7: the social hand had the errand
contract in its sheet, the master of ceremonies' agreement as its row, and no
footman it could name -- so it called the dispatch already true and the errand
went nowhere. `addressed_house` lists the addressed figure's institution by
name, post and room; an errand names one of them.
"""

import time

from agents.director import addressed_house
from world.charter_runtime import save_registry


class _Ctx:
    def __init__(self, cid):
        self.chat = {"id": cid}
        self.turn = type("T", (), {"frame_id": None})()


def test_the_addressed_figures_institution_is_listed_by_name_post_and_room(temp_db):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Wendover", "", time.time()))
    save_registry(cid, {"version": 1, "items": {"assembly": {"state": {
        "key": "assembly",
        "bodies": {
            "master_of_ceremonies:featured:1": {"name": "Mr Pellew", "place": "ballroom",
                                                "berth": "ballroom", "available": True,
                                                "home_post": "master_of_ceremonies"},
            "footman:featured:2": {"name": "Thomas Ashby", "place": "stair_head_landing",
                                   "berth": "stair_head_landing", "available": True,
                                   "home_post": "footman"},
        },
        "posts": {"master_of_ceremonies": {"place": "ballroom", "serves": []},
                  "footman": {"place": "stair_head_landing", "serves": []}},
        "upkeeps": {}, "watch": {"footman": "footman:featured:2"}, "roster": {},
    }}, "crown": {"state": {"key": "crown", "bodies": {
        "landlord:featured:3": {"name": "Bragg", "place": "hall", "berth": "hall",
                                "available": True, "home_post": "landlord"}},
        "posts": {"landlord": {"place": "hall", "serves": []}}, "upkeeps": {},
        "watch": {}, "roster": {}}}}})
    house = addressed_house(_Ctx(cid), ["Mr Pellew"])
    assert list(house) == ["assembly"]
    rows = {r["name"]: (r["post"], r["place"]) for r in house["assembly"]}
    assert rows["Thomas Ashby"] == ("footman", "stair_head_landing")
    assert rows["Mr Pellew"] == ("master of ceremonies", "ballroom")
    assert addressed_house(_Ctx(cid), ["nobody at all"]) == {}
