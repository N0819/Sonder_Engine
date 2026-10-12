"""A storey of a site plan is drawn as the layout lab draws it (`web/storey_plan.py`).

The owner, reading the shrine of chat 168 (2026-10-12), asked that the
World Browser look like the layout lab, and chose the lab's own plan view,
fed from the live scene. These pin the drawing's data: every room on one
frame of the plan, its doorways where the engine places them, a window a
line in its wall, a stair in its hall, and the storey beneath as a ghost.
"""
from __future__ import annotations

PLAN = "layout:hall"


def _scene():
    return {"rooms": {
        "hall": {"name": "the Hall", "level": 0, "exposure": "enclosed",
                 "extent": {"w": 4, "d": 3}, "site": {"plan": PLAN, "x": 0, "y": 0, "elev_m": 0},
                 "anchors": {"hearth": {"desc": "a stone hearth", "dir": "n", "cell": [1, 0],
                                        "extent": {"w": 2, "d": 1}, "height": "waist",
                                        "footprint": "large"}},
                 "adjacent": [{"to": "yard", "barrier": "open_door", "dir": "s", "offset": 0.5},
                              {"to": "stair_0", "barrier": "open", "dir": "e", "offset": 0.5}]},
        # described, so the story's: a hall no plan holds and nobody has
        # described leaves the scene (`structure.apply_planned_layout`)
        "stair_0": {"name": "the stair", "desc": "A narrow stair.", "level": 0,
                    "exposure": "enclosed", "made_by_layout": True,
                    "extent": {"w": 2, "d": 3}, "site": {"plan": PLAN, "x": 4, "y": 0, "elev_m": 0},
                    "adjacent": [{"to": "hall", "barrier": "open", "dir": "w", "offset": 0.5},
                                 {"to": "stair_1", "barrier": "open", "vertical": "up", "way": "stair"}]},
        "stair_1": {"name": "the stair", "desc": "A narrow stair.", "level": 1,
                    "exposure": "enclosed", "made_by_layout": True,
                    "extent": {"w": 2, "d": 3}, "site": {"plan": PLAN, "x": 4, "y": 0, "elev_m": 3},
                    "adjacent": [{"to": "stair_0", "barrier": "open", "vertical": "down", "way": "stair"},
                                 {"to": "loft", "barrier": "closed_door", "dir": "w", "offset": 0.5}]},
        "loft": {"name": "the Loft", "level": 1, "exposure": "enclosed",
                 "extent": {"w": 4, "d": 3}, "site": {"plan": PLAN, "x": 0, "y": 0, "elev_m": 3},
                 "windows": [{"id": "gable", "dir": "n", "cell": [1, 0], "name": "a gable window"}],
                 "adjacent": [{"to": "stair_1", "barrier": "closed_door", "dir": "e", "offset": 0.5}]},
        "yard": {"name": "the Yard", "level": 0, "exposure": "open",
                 "extent": {"w": 6, "d": 2}, "site": {"plan": PLAN, "x": 0, "y": 3, "elev_m": 0},
                 "adjacent": [{"to": "hall", "barrier": "open_door", "dir": "n", "offset": 0.3}]}},
        "positions": {"Mara": "loft"}, "stations": {"Mara": {"cell": [2, 1]}}, "entities": {}}


SPECS = {"hall": ("the Hall", {"layout": {"plan": PLAN, "purpose": "hall"},
                               "anchors": {"hearth": {"desc": "a stone hearth", "kind": "hearth"}}}),
         "stair_0": ("the stair", {"made_by_layout": True, "stair_kind": "l"}),
         "stair_1": ("the stair", {"made_by_layout": True, "stair_kind": "l"}),
         "yard": ("the Yard", {"layout": {"plan": PLAN, "grounds": "open"}})}


def test_the_ground_storey_is_every_room_on_one_frame_with_its_ways_in_its_walls():
    from web.storey_plan import storey_plan
    d = storey_plan(_scene(), PLAN, 0, SPECS)
    assert d["levels"] == [0, 1] and d["level"] == 0
    rooms = {r["id"]: r for r in d["rooms"]}
    assert set(rooms) == {"hall", "stair_0", "yard"}
    assert rooms["hall"]["purpose"] == "hall" and rooms["stair_0"]["purpose"] == "stair"
    assert rooms["yard"]["ground"] and rooms["yard"]["purpose"] == "ground"
    assert rooms["hall"]["rects"] == [{"x": 0, "y": 0, "w": 4, "d": 3}]
    # one doorway a pair, on the plan, in the wall its edge names
    pairs = {frozenset((x["a"], x["b"])): x for x in d["doors"]}
    assert set(pairs) == {frozenset(("hall", "yard")), frozenset(("hall", "stair_0"))}
    for door in d["doors"]:
        assert door["side"] in ("n", "e", "s", "w") and door["cells"]
    (stair,) = d["stairs"]
    assert (stair["room"], stair["kind"], stair["up"], stair["down"]) == ("stair_0", "l", True, False)
    (hearth,) = d["fixtures"]
    assert hearth["kind"] == "hearth" and hearth["rect"] == {"x": 1, "y": 0, "w": 2, "d": 1}
    assert d["below"] == []


def test_the_storey_above_has_its_window_in_its_wall_and_the_ground_as_its_ghost():
    from web.storey_plan import storey_plan
    d = storey_plan(_scene(), PLAN, 1, SPECS)
    assert {r["id"] for r in d["rooms"]} == {"loft", "stair_1"}
    (window,) = d["windows"]
    assert window["room"] == "loft" and window["side"] == "n" and window["cells"] == [[1, 0]]
    (stair,) = d["stairs"]
    assert (stair["up"], stair["down"]) == (False, True)
    assert d["bodies"] == [{"name": "Mara", "room": "loft", "cell": [2, 1]}]
    assert {g["id"] for g in d["below"]} == {"hall", "stair_0", "yard"}
    # a storey the plan does not hold is the ground's; a plan nothing stands on, none
    assert storey_plan(_scene(), PLAN, 7, SPECS)["level"] == 0
    assert storey_plan(_scene(), "layout:elsewhere", 0, SPECS) is None


# ---------------------------------------------------------------------------
# The route, over a story's own scene and plans
# ---------------------------------------------------------------------------

import json
import time

import pytest


@pytest.fixture
def client(temp_db):
    from fastapi.testclient import TestClient
    from web import app as app_module
    from web import guest_access as guest
    guest.reset_host_account()
    with TestClient(app_module.app) as c:
        response = c.post("/api/auth/setup", json={"username": "host", "password": "pw12345"})
        assert response.status_code == 200, response.text
        yield c
    guest.reset_host_account()


def _story(db):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Plans", "", time.time()))
    db.wset(cid, "scene", _scene())
    return cid


def test_the_map_draws_a_storey_and_the_grid_says_which(client, temp_db):
    cid = _story(temp_db)
    response = client.get(f"/api/chats/{cid}/map/plan", params={"plan": PLAN, "level": 1})
    assert response.status_code == 200, response.text
    d = response.json()
    assert d["level"] == 1 and d["levels"] == [0, 1]
    assert {r["id"] for r in d["rooms"]} == {"loft", "stair_1"}
    assert not any(r["planned"] for r in d["rooms"]), "every room is the live scene's"
    assert d["title"] == "the Hall", "named for the room the plan is named after"
    assert client.get(f"/api/chats/{cid}/map/plan", params={"plan": "nowhere"}).status_code == 404
    # the grid of a room on a plan says which plan and storey; one on none, nothing
    grid = client.get(f"/api/chats/{cid}/rooms/loft/grid").json()
    assert (grid["room"]["plan"], grid["room"]["level"]) == (PLAN, 1)


def test_a_planned_room_nobody_came_near_is_drawn_as_planned(client, temp_db):
    from world.structure import plant_structure
    cid = _story(temp_db)
    plant_structure(cid, {"key": "town", "name": "Town"}, {
        "pantry": {"name": "the Pantry", "purpose": "a pantry", "exposure": "enclosed",
                   "extent": {"w": 2, "d": 3}, "level": 0,
                   "adjacent": [{"to": "hall", "barrier": "closed_door"}]}})
    # a solve put it on the plan beside the hall
    from core.db import q, qi
    row = q("SELECT payload FROM room_registry WHERE chat_id=? AND room_uid='pantry'", (cid,), one=True)
    payload = json.loads(row["payload"])
    payload["planned"]["site"] = {"plan": PLAN, "x": -2, "y": 0, "elev_m": 0.0}
    qi("UPDATE room_registry SET payload=? WHERE chat_id=? AND room_uid='pantry'",
       (json.dumps(payload), cid))
    d = client.get(f"/api/chats/{cid}/map/plan", params={"plan": PLAN, "level": 0}).json()
    rooms = {r["id"]: r for r in d["rooms"]}
    assert rooms["pantry"]["planned"] and not rooms["hall"]["planned"]
    assert rooms["pantry"]["rects"] == [{"x": -2, "y": 0, "w": 2, "d": 3}]
