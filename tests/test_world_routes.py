"""The World Browser's backend and wiring: the room index grouped for
display, the per-room slice, and the two buttons that now open it.

`story/room_slice.py` holds the contract (its module docstring is the shape);
`web/world_routes.py` is transport over it -- read-only, host-only, era-
scoped the way the attire route is. The browser replaces the two raw JSON
textareas as the FIRST thing a host sees behind 🌍 and 👕 while keeping both
editors as its Raw JSON tab, so the properties worth defending are that the
grouping says where the cast is and what is reachable from them, that a
slice carries what the card renders, that an unknown id is a 404 rather than
an empty card, that a frame is honoured, and that settings.js no longer
binds the buttons a file loading BEFORE it now owns.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from web import app as app_module
from web import guest_access as guest
from web.world_routes import GROUPS, group_rows

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def client(temp_db):
    guest.reset_host_account()
    with TestClient(app_module.app) as c:
        response = c.post("/api/auth/setup",
                          json={"username": "host", "password": "pw12345"})
        assert response.status_code == 200, response.text
        yield c
    guest.reset_host_account()


@pytest.fixture
def story(temp_db, sample_scene):
    """The manor with two registered cast members and the player standing in
    it, a vehicle whose interior is a room, a thing on the kitchen floor, a
    planned room joined to the hallway by the plan alone, a planned room
    joined to nothing, and a retired id."""
    persona = temp_db.qi(
        "INSERT INTO personas(name,sheet) VALUES(?,?)",
        ("Nathan", json.dumps({"identity": {"name": "Nathan"}})))
    cid = temp_db.qi(
        "INSERT INTO chats(name,persona_id,scenario,created) VALUES(?,?,?,?)",
        ("Old Manor", persona, "", time.time()))
    ids = {}
    for name in ("Alice", "Bob"):
        ids[name] = temp_db.qi(
            "INSERT INTO characters(name,sheet,created) VALUES(?,?,?)",
            (name, json.dumps({"identity": {"name": name}}), time.time()))
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status) VALUES(?,?,'active')",
            (cid, ids[name]))

    scene = json.loads(json.dumps(sample_scene))
    scene["rooms"]["console_room"] = {
        "name": "Console Room", "desc": "Humming.", "parent_entity": "tardis",
        "adjacent": [],
    }
    scene["positions"] = {"Alice": "kitchen", "Bob": "hallway", "Nathan": "study",
                          "tardis": "study"}
    # A thing placed the second way: as one of the room's anchors.
    scene["rooms"]["kitchen"]["anchors"] = {"oak_table": {"kind": "furniture"}}
    scene["entities"] = {
        "tardis": {"name": "The TARDIS", "kind": "vehicle"},
        "oak_table": {"name": "Oak table", "kind": "furniture"},
    }
    scene["attire"] = {"Alice": {"wearing": ["apron"], "state": [],
                                 "regions": {"torso": {"garments": [
                                     {"name": "apron", "state": "worn"}],
                                     "beneath": ""}}}}
    scene["stations"] = {"Alice": {"at": "oak_table", "near": ["Bob"]}}
    temp_db.wset(cid, "scene", scene)

    turn = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, 0, "", time.time()))
    for uid, name, payload, retired in (
            ("attic", "Attic", {"planned": {"purpose": "storage",
                                            "adjacent": [{"to": "hallway",
                                                          "barrier": "open"}]}},
             None),
            ("crypt", "Crypt", {"planned": {"purpose": "the dead",
                                            "adjacent": []}}, None),
            ("old_wing", "Old Wing", {}, turn)):
        temp_db.qi(
            "INSERT INTO room_registry(chat_id,room_uid,name,payload,retired_turn_id) "
            "VALUES(?,?,?,?,?)", (cid, uid, name, json.dumps(payload), retired))
    return {"chat_id": cid, "persona_id": persona, **ids}


def _ids(rows):
    return [r["id"] for r in rows]


# ---- the index ---------------------------------------------------------------

class TestTheIndex:
    def test_rooms_are_grouped_cast_first_then_by_reach(self, client, story):
        data = client.get(f"/api/chats/{story['chat_id']}/rooms").json()
        groups = data["groups"]

        assert list(groups) == list(GROUPS)
        assert data["location"] == "Old Manor"
        # The cast: every room a body stands in, the player included; the
        # vehicle standing in the study is a thing, not a cast member.
        assert set(_ids(groups["cast"])) == {"kitchen", "hallway", "study"}
        assert all(r["hops"] == 0 for r in groups["cast"])
        # Reachable: the walk from the cast, over passable edges AND the
        # plan's edges (the attic joins the hallway only in the plan), with
        # the interior joined to the room its holder stands in.
        reachable = _ids(groups["reachable"])
        assert "attic" in reachable and "console_room" in reachable
        hops = [r["hops"] for r in groups["reachable"]]
        assert hops == sorted(hops) and all(h > 0 for h in hops)
        # Unreachable: unretired rooms the walk never reaches, planned or
        # live -- the garden has no edge, the crypt's plan names none.
        assert set(_ids(groups["unreachable"])) >= {"garden", "crypt"}
        assert all(r["hops"] is None for r in groups["unreachable"])
        # Retired ids are listed as spent, never as places.
        assert _ids(groups["retired"]) == ["old_wing"]
        assert groups["retired"][0]["hops"] is None

    def test_rows_carry_what_the_tree_needs(self, client, story):
        groups = client.get(f"/api/chats/{story['chat_id']}/rooms").json()["groups"]
        rows = {r["id"]: r for rows in groups.values() for r in rows}

        # Occupants beside a cast room, by name.
        assert rows["kitchen"]["occupants"] == ["Alice"]
        # The vehicle's position row places a thing, not a body.
        assert rows["study"]["occupants"] == ["Nathan"]
        # An interior room names its holder for display and the room the
        # holder stands in for nesting.
        console = rows["console_room"]
        assert console["holder"] == "tardis"
        assert console["holder_name"] == "The TARDIS"
        assert console["holder_room"] == "study"
        assert rows["kitchen"]["holder"] is None and rows["kitchen"]["holder_room"] is None
        # Status rides every row.
        assert rows["attic"]["status"] == "planned"
        assert rows["kitchen"]["status"] == "live"
        assert rows["old_wing"]["status"] == "retired"

    def test_grouping_is_pure_over_the_index(self):
        scene = {"positions": {"A": "r1", "B": "r1", "crate": "r1"},
                 "entities": {"B": {"kind": "creature"},
                              "crate": {"kind": "object"}}}
        index = [
            {"id": "r1", "name": "One", "status": "live", "holder": None, "hops": 0},
            {"id": "r2", "name": "Two", "status": "live", "holder": None, "hops": 1},
            {"id": "p1", "name": "Plan", "status": "planned", "holder": None, "hops": 2},
            {"id": "far", "name": "Far", "status": "planned", "holder": None, "hops": None},
            {"id": "gone", "name": "Gone", "status": "retired", "holder": None, "hops": None},
        ]
        groups = group_rows(index, scene)
        assert {k: _ids(v) for k, v in groups.items()} == {
            "cast": ["r1"], "reachable": ["r2", "p1"],
            "unreachable": ["far"], "retired": ["gone"]}
        assert groups["cast"][0]["occupants"] == ["A", "B"]

    def test_a_story_with_no_scene_has_empty_groups(self, client, temp_db):
        cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Unstarted", "", time.time()))
        data = client.get(f"/api/chats/{cid}/rooms").json()
        assert all(rows == [] for rows in data["groups"].values())

    def test_an_unknown_story_is_a_404(self, client):
        assert client.get("/api/chats/999999/rooms").status_code == 404


# ---- the slice ---------------------------------------------------------------

class TestTheSlice:
    def test_a_live_room_carries_what_the_card_renders(self, client, story):
        r = client.get(f"/api/chats/{story['chat_id']}/rooms/kitchen")
        assert r.status_code == 200, r.text
        slice_ = r.json()

        assert slice_["id"] == "kitchen" and slice_["status"] == "live"
        assert slice_["holder"] is None and slice_["holder_name"] is None
        assert "oak table" in slice_["description"]
        exits = {x["to"]: x for x in slice_["exits"]}
        assert exits["hallway"]["status"] == "live"
        assert exits["cellar"]["barrier"] == "closed_door"
        # The body here, with its station and its ledger AS STORED.
        (alice,) = slice_["occupants"]
        assert alice["name"] == "Alice"
        assert alice["station"] == {"at": "oak_table", "near": ["Bob"]}
        assert alice["attire"]["wearing"] == ["apron"]
        assert alice["attire"]["regions"]["torso"]["garments"][0]["name"] == "apron"
        # The table is a thing, not an occupant.
        assert [t["name"] for t in slice_["things"]] == ["Oak table"]
        assert slice_["planned_stub"] is None
        assert slice_["plan_here"] == {"planned_entities": [], "needs": [],
                                       "package_ops": []}

    def test_an_interior_room_names_its_holder(self, client, story):
        slice_ = client.get(
            f"/api/chats/{story['chat_id']}/rooms/console_room").json()
        assert slice_["holder"] == "tardis"
        assert slice_["holder_name"] == "The TARDIS"

    def test_a_planned_room_carries_the_plans_stub(self, client, story):
        slice_ = client.get(f"/api/chats/{story['chat_id']}/rooms/attic").json()
        assert slice_["status"] == "planned"
        assert slice_["planned_stub"]["purpose"] == "storage"
        assert [x["to"] for x in slice_["planned_stub"]["exits"]] == ["hallway"]
        assert [x["to"] for x in slice_["exits"]] == ["hallway"]
        assert slice_["occupants"] == [] and slice_["description"] == ""

    def test_an_unknown_room_is_a_404_not_an_empty_card(self, client, story):
        r = client.get(f"/api/chats/{story['chat_id']}/rooms/ballroom")
        assert r.status_code == 404
        assert "ballroom" in r.json()["detail"]


# ---- eras --------------------------------------------------------------------

class TestFrames:
    @pytest.fixture
    def past(self, client, story, temp_db):
        cid = story["chat_id"]
        r = client.post(f"/api/chats/{cid}/frames",
                        json={"label": "Decades Ago", "ordinal": -10,
                              "kind": "past"})
        assert r.status_code == 200, r.text
        fid = r.json()["id"]
        temp_db.wset_for_frame(cid, "scene", {
            "location": "the manor, decades ago",
            "rooms": {"ballroom": {"name": "Ballroom", "desc": "Chandeliers.",
                                   "adjacent": [{"to": "terrace", "barrier": "open"}]},
                      "terrace": {"name": "Terrace", "adjacent": []}},
            "positions": {"Alice": "ballroom", "Nathan": "ballroom"},
            "entities": {}, "attire": {}}, fid)
        return fid

    def test_the_index_answers_for_the_frame_asked_about(self, client, story, past):
        cid = story["chat_id"]
        present = client.get(f"/api/chats/{cid}/rooms").json()
        then = client.get(f"/api/chats/{cid}/rooms?frame_id={past}").json()

        assert "kitchen" in _ids(present["groups"]["cast"])
        assert then["frame_id"] == past
        assert then["location"] == "the manor, decades ago"
        assert _ids(then["groups"]["cast"]) == ["ballroom"]
        assert _ids(then["groups"]["reachable"]) == ["terrace"]
        # The registry is the story's, not the era's: the plan's rooms show
        # in every frame, unreachable where the frame's scene has no edge.
        assert "attic" in _ids(then["groups"]["unreachable"])

    def test_the_slice_answers_for_the_frame_asked_about(self, client, story, past):
        cid = story["chat_id"]
        assert client.get(f"/api/chats/{cid}/rooms/ballroom").status_code == 404
        then = client.get(f"/api/chats/{cid}/rooms/ballroom?frame_id={past}")
        assert then.status_code == 200, then.text
        assert [o["name"] for o in then.json()["occupants"]] == ["Alice", "Nathan"]

    def test_a_frame_of_another_story_or_none_at_all_is_a_404(
            self, client, story, past, temp_db):
        cid = story["chat_id"]
        other = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                           ("Other", "", time.time()))
        assert client.get(f"/api/chats/{other}/rooms?frame_id={past}").status_code == 404
        assert client.get(f"/api/chats/{cid}/rooms?frame_id=424242").status_code == 404
        assert client.get(
            f"/api/chats/{cid}/rooms/kitchen?frame_id=424242").status_code == 404


# ---- the page's wiring -------------------------------------------------------

def test_the_browser_loads_after_chat_and_before_settings():
    html = (ROOT / "static" / "index.html").read_text()
    order = re.findall(r'/static/js/([a-z_-]+)\.js', html)
    assert (order.index("chat") < order.index("world_browser")
            < order.index("settings") < order.index("app"))


def test_the_two_buttons_are_bound_once_by_the_browser():
    """A later-loading file's top-level `onclick` assignment silently wins,
    so settings.js must no longer bind the buttons world_browser.js owns."""
    settings = (ROOT / "static" / "js" / "settings.js").read_text()
    browser = (ROOT / "static" / "js" / "world_browser.js").read_text()
    for button in ("#b-world", "#b-attire"):
        assert f'$("{button}").onclick' not in settings
        assert f'$("{button}").onclick' in browser
    # The raw editors survive as the Raw JSON tab: both PUTs, same toasts.
    assert "/api/chats/${chatId}/world`" in browser
    assert "/api/chats/${chatId}/attire${frameQuery()}`" in browser
    assert '"World state saved."' in browser and '"Attire saved."' in browser
    # The frontend calls the two routes this module adds.
    assert "/api/chats/${chatId}/rooms${frameQuery()}" in browser
    assert "/api/chats/${chatId}/rooms/${encodeURIComponent(id)}${frameQuery()}" in browser


def test_every_label_is_in_both_language_packs():
    en = json.loads((ROOT / "language_packs" / "en" / "ui.json").read_text())
    ja = json.loads((ROOT / "language_packs" / "ja" / "ui.json").read_text())
    for label in ("Browse", "Raw JSON", "Where the cast stands",
                  "Reachable from the cast", "Not yet reachable", "Retired",
                  "Exits", "Who is here", "Things", "The plan here", "Move here",
                  "Attire is read-only here; hand-correct it under",
                  "No room '${room_id}' in this story"):
        assert label in en, label
        assert ja.get(label) not in (None, label), label
