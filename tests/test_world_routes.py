"""The World Browser's backend and wiring: the room index grouped for
display, the per-room slice, and the two buttons that now open it.

`story/room_slice.py` holds the contract (its module docstring is the shape);
`web/world_routes.py` is transport over it -- host-only, era-scoped the way
the attire route is -- plus, since 2026-09-04, three NARROW writes (a room's
fields, a thing's fields, a body's station) so the browser edits a field
rather than a blob. The browser replaces the two raw JSON textareas as the
FIRST thing a host sees behind 🌍 and 👕 while keeping both editors as its
Raw JSON tab, so the properties worth defending are that the grouping says
where the cast is and what is reachable from them, that a slice carries what
the card renders, that an unknown id is a 404 rather than an empty card,
that a frame is honoured, that settings.js no longer binds the buttons a
file loading BEFORE it now owns -- and, for the writes, that a valid edit
lands and the registry projection agrees, that a word outside a closed set
is refused with the set named, that a doorway is written from both its
rooms, that a station names an anchor the room holds, and that a spanning
garment edited through the attire PUT keeps every region and its state.
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
    # A canon book, so the registry projection has a book to file live rooms
    # under (`_prepare_room_registry` skips a room with no owning book).
    canon = temp_db.qi("INSERT INTO lorebooks(name,chat_id,book_type) VALUES(?,?,?)",
                       ("Canon", cid, "general"))
    temp_db.qi("UPDATE chats SET lorebook_id=? WHERE id=?", (canon, cid))
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
    # The frontend calls the two reads and the three writes this module adds,
    # and sends attire through the ONE writer that re-derives it.
    assert "/api/chats/${chatId}/rooms${frameQuery()}" in browser
    assert "/api/chats/${chatId}/rooms/${encodeURIComponent(id)}${frameQuery()}" in browser
    assert 'api("PATCH"' in browser
    assert "/entities/${encodeURIComponent(" in browser
    assert "/bodies/${encodeURIComponent(" in browser and "/station${frameQuery()}" in browser
    # No closed set is typed into the browser: every select reads `vocab`.
    for word in ('"closed_door"', '"see_through"', '"loosened"', '"bright"'):
        assert word not in browser, word


def test_every_label_is_in_both_language_packs():
    en = json.loads((ROOT / "language_packs" / "en" / "ui.json").read_text())
    ja = json.loads((ROOT / "language_packs" / "ja" / "ui.json").read_text())
    for label in ("Rooms", "Bodies", "Raw JSON", "Where the cast stands",
                  "Reachable from the cast", "Not yet reachable", "Retired",
                  "Exits", "Who is here", "Things", "The plan here", "Move here",
                  "Anchors", "Add exit", "Add garment", "Saved.",
                  "No room '${room_id}' in this story",
                  "A room needs a name"):
        assert label in en, label
        assert ja.get(label) not in (None, label), label


# ---- the writes --------------------------------------------------------------

def _scene(temp_db, cid):
    return temp_db.wget(cid, "scene")


def _registry(temp_db, cid):
    return {r["room_uid"]: dict(r) for r in temp_db.q(
        "SELECT room_uid, name, retired_turn_id FROM room_registry WHERE chat_id=?",
        (cid,))}


class TestRoomPatch:
    def test_a_closed_set_word_lands_and_the_card_comes_back_fresh(
            self, client, story, temp_db):
        cid = story["chat_id"]
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen",
                         json={"light": "dim", "size": "large", "exposure": "enclosed",
                               "notes": "Bread.", "region": "East Wing"})
        assert r.status_code == 200, r.text
        slice_ = r.json()
        # The response IS the slice, decorated with what an editor needs.
        assert slice_["id"] == "kitchen" and slice_["record"]["light"] == "dim"
        assert slice_["record"]["size"] == "large"
        assert slice_["record"]["exposure"] == "enclosed"
        assert slice_["record"]["notes"] == "Bread."
        assert slice_["record"]["region"] == "east_wing"
        assert "oak_table" in [a["id"] for a in slice_["stationable"]]
        room = _scene(temp_db, cid)["rooms"]["kitchen"]
        assert room["light"] == "dim" and room["size"] == "large"
        assert room["region"] == "east_wing"
        # Fields the body did not name are untouched.
        assert room["desc"] == "A rustic kitchen with a heavy oak table."

    def test_an_empty_word_clears_the_field(self, client, story, temp_db):
        cid = story["chat_id"]
        client.patch(f"/api/chats/{cid}/rooms/kitchen", json={"light": "dark"})
        client.patch(f"/api/chats/{cid}/rooms/kitchen", json={"light": ""})
        assert "light" not in _scene(temp_db, cid)["rooms"]["kitchen"]

    @pytest.mark.parametrize("field,bad,set_word", [
        ("light", "gloomy-ish", "bright"),
        ("size", "enormous", "vast"),
        ("exposure", "outside", "sheltered"),
    ])
    def test_a_word_outside_its_set_is_refused_naming_the_set(
            self, client, story, temp_db, field, bad, set_word):
        cid = story["chat_id"]
        before = json.dumps(_scene(temp_db, cid), sort_keys=True)
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen", json={field: bad})
        assert r.status_code == 400
        assert field in r.json()["detail"] and set_word in r.json()["detail"]
        assert json.dumps(_scene(temp_db, cid), sort_keys=True) == before

    def test_a_rename_reaches_the_registry_projection(self, client, story, temp_db):
        cid = story["chat_id"]
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen", json={"name": "Scullery"})
        assert r.status_code == 200, r.text
        assert r.json()["name"] == "Scullery"
        assert _registry(temp_db, cid)["kitchen"]["name"] == "Scullery"
        # And an empty name is not a name.
        assert client.patch(f"/api/chats/{cid}/rooms/kitchen",
                            json={"name": "  "}).status_code == 400

    def test_an_added_exit_is_written_from_both_rooms(self, client, story, temp_db):
        cid = story["chat_id"]
        slice_ = client.get(f"/api/chats/{cid}/rooms/kitchen").json()
        exits = [{"to": e["to"], "barrier": e["barrier"], "dir": e.get("dir")}
                 for e in slice_["record"]["adjacent"]]
        exits.append({"to": "garden", "barrier": "closed_door", "dir": "north"})
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen", json={"exits": exits})
        assert r.status_code == 200, r.text
        rooms = _scene(temp_db, cid)["rooms"]
        mine = {e["to"]: e for e in rooms["kitchen"]["adjacent"]}
        theirs = {e["to"]: e for e in rooms["garden"]["adjacent"]}
        # Mine, with the bearing folded to the compass; theirs, the opposite.
        assert mine["garden"]["barrier"] == "closed_door" and mine["garden"]["dir"] == "n"
        assert theirs["kitchen"]["barrier"] == "closed_door" and theirs["kitchen"]["dir"] == "s"
        # An edge that kept its `to` kept the fields the editor does not show.
        assert mine["hallway"]["distance"] == "near"
        # The far room's card shows the doorway too.
        far = client.get(f"/api/chats/{cid}/rooms/garden").json()
        assert {x["to"] for x in far["exits"]} == {"kitchen"}

    def test_changing_a_barrier_changes_the_doorway_not_one_side(
            self, client, story, temp_db):
        cid = story["chat_id"]
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen", json={"exits": [
            {"to": "hallway", "barrier": "closed_door"},
            {"to": "cellar", "barrier": "open_door"}]})
        assert r.status_code == 200, r.text
        rooms = _scene(temp_db, cid)["rooms"]
        assert {e["to"]: e["barrier"] for e in rooms["hallway"]["adjacent"]}["kitchen"] \
            == "closed_door"
        assert {e["to"]: e["barrier"] for e in rooms["cellar"]["adjacent"]}["kitchen"] \
            == "open_door"

    def test_a_removed_exit_takes_the_reciprocal_edge_with_it(
            self, client, story, temp_db):
        cid = story["chat_id"]
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen",
                         json={"exits": [{"to": "hallway", "barrier": "open"}]})
        assert r.status_code == 200, r.text
        rooms = _scene(temp_db, cid)["rooms"]
        assert [e["to"] for e in rooms["kitchen"]["adjacent"]] == ["hallway"]
        assert [e["to"] for e in rooms["cellar"]["adjacent"]] == []

    def test_an_exit_with_an_unknown_barrier_or_bearing_is_refused(
            self, client, story):
        cid = story["chat_id"]
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen",
                         json={"exits": [{"to": "hallway", "barrier": "portcullis"}]})
        assert r.status_code == 400 and "closed_door" in r.json()["detail"]
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen",
                         json={"exits": [{"to": "hallway", "barrier": "open",
                                          "dir": "left"}]})
        assert r.status_code == 400 and "dir" in r.json()["detail"]

    def test_anchors_are_replaced_and_a_stranded_station_is_blanked(
            self, client, story, temp_db):
        cid = story["chat_id"]
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen", json={"anchors": {
            "hearth": {"desc": "the hearth", "dir": "w", "height": "waist",
                       "footprint": "small", "opacity": "opaque"},
            "": {"desc": "Long bench"}}})
        assert r.status_code == 200, r.text
        scene = _scene(temp_db, cid)
        anchors = scene["rooms"]["kitchen"]["anchors"]
        assert set(anchors) == {"hearth", "long_bench"}
        assert anchors["hearth"]["height"] == "waist"
        # Alice stood at the oak table, which no longer exists as an anchor:
        # the same station hygiene the merge runs blanks it.
        assert scene["stations"]["Alice"]["at"] is None
        assert {a["id"] for a in r.json()["stationable"]} >= {"hearth", "long_bench"}

    def test_an_anchor_geometry_word_outside_its_set_is_refused(self, client, story):
        cid = story["chat_id"]
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen", json={"anchors": {
            "hearth": {"desc": "the hearth", "height": "tall"}}})
        assert r.status_code == 400
        assert "height" in r.json()["detail"] and "waist" in r.json()["detail"]

    def test_a_planned_or_unknown_room_cannot_be_patched(self, client, story):
        cid = story["chat_id"]
        assert client.patch(f"/api/chats/{cid}/rooms/attic",
                            json={"light": "dim"}).status_code == 400
        assert client.patch(f"/api/chats/{cid}/rooms/ballroom",
                            json={"light": "dim"}).status_code == 400


class TestEntityPatch:
    def test_a_things_fields_land(self, client, story, temp_db):
        cid = story["chat_id"]
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen/entities/oak_table",
                         json={"kind": "table", "description": "Scarred oak.",
                               "portable": False, "light_source": "dim", "lit": True})
        assert r.status_code == 200, r.text
        ent = _scene(temp_db, cid)["entities"]["oak_table"]
        assert ent["kind"] == "table" and ent["description"] == "Scarred oak."
        assert ent["portable"] is False and ent["light_source"] == "dim"
        assert ent["state"]["lit"] is True
        assert [t["kind"] for t in r.json()["things"]] == ["table"]

    def test_a_light_word_outside_the_set_is_refused(self, client, story):
        cid = story["chat_id"]
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen/entities/oak_table",
                         json={"light_source": "blazing"})
        assert r.status_code == 400 and "bright" in r.json()["detail"]

    def test_a_thing_is_moved_by_its_position_row(self, client, story, temp_db):
        cid = story["chat_id"]
        r = client.patch(f"/api/chats/{cid}/rooms/study/entities/tardis",
                         json={"room": "garden"})
        assert r.status_code == 200, r.text
        assert _scene(temp_db, cid)["positions"]["tardis"] == "garden"
        # The vehicle left the study; its interior followed it in the index.
        rows = {r["id"]: r for rows in client.get(f"/api/chats/{cid}/rooms")
                .json()["groups"].values() for r in rows}
        assert rows["console_room"]["holder_room"] == "garden"
        # A thing placed only as an anchor is the anchor editor's business.
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen/entities/oak_table",
                         json={"room": "garden"})
        assert r.status_code == 400 and "anchor" in r.json()["detail"]

    def test_a_thing_not_in_the_room_is_refused(self, client, story):
        cid = story["chat_id"]
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen/entities/tardis",
                         json={"kind": "box"})
        assert r.status_code == 400 and "study" in r.json()["detail"]
        assert client.patch(f"/api/chats/{cid}/rooms/kitchen/entities/ghost",
                            json={"kind": "box"}).status_code == 404


class TestBodyStation:
    def test_a_station_names_an_anchor_the_room_holds(self, client, story, temp_db):
        cid = story["chat_id"]
        r = client.put(f"/api/chats/{cid}/bodies/Alice/station",
                       json={"at": "door:hallway", "near": []})
        assert r.status_code == 200, r.text
        assert r.json()["station"] == {"at": "door:hallway", "near": []}
        assert _scene(temp_db, cid)["stations"]["Alice"]["at"] == "door:hallway"
        r = client.put(f"/api/chats/{cid}/bodies/Alice/station",
                       json={"at": "throne", "near": []})
        assert r.status_code == 400
        assert "oak_table" in r.json()["detail"] and "throne" in r.json()["detail"]

    def test_near_names_a_body_in_the_same_room_and_is_symmetrised(
            self, client, story, temp_db):
        cid = story["chat_id"]
        client.put(f"/api/chats/{cid}/characters/{story['Bob']}/position",
                   json={"room": "kitchen"})
        r = client.put(f"/api/chats/{cid}/bodies/Alice/station",
                       json={"at": "oak_table", "near": ["Bob"]})
        assert r.status_code == 200, r.text
        stations = _scene(temp_db, cid)["stations"]
        assert stations["Alice"] == {"at": "oak_table", "near": ["Bob"]}
        assert "Alice" in stations["Bob"]["near"]
        r = client.put(f"/api/chats/{cid}/bodies/Alice/station",
                       json={"at": None, "near": ["Nathan"]})
        assert r.status_code == 400 and "Nathan" in r.json()["detail"]

    def test_a_body_nowhere_has_no_station(self, client, story):
        cid = story["chat_id"]
        r = client.put(f"/api/chats/{cid}/bodies/Zed/station", json={"at": None})
        assert r.status_code == 400


class TestBodiesAndVocab:
    def test_the_index_lists_every_body_with_its_ledger(self, client, story):
        cid = story["chat_id"]
        data = client.get(f"/api/chats/{cid}/rooms").json()
        bodies = {b["name"]: b for b in data["bodies"]}
        # The player first, then the cast by name; the vehicle is a thing.
        assert [b["name"] for b in data["bodies"]][0] == "Nathan"
        assert set(bodies) == {"Nathan", "Alice", "Bob"}
        assert bodies["Nathan"]["kind"] == "player" and bodies["Nathan"]["room"] == "study"
        assert bodies["Alice"]["kind"] == "cast" and bodies["Alice"]["char_id"] == story["Alice"]
        assert bodies["Alice"]["room_name"] == "Kitchen"
        assert bodies["Alice"]["station"] == {"at": "oak_table", "near": ["Bob"]}
        assert bodies["Alice"]["attire"]["regions"]["torso"]["garments"][0]["name"] == "apron"
        assert bodies["Bob"]["attire"] is None

    def test_a_dressed_body_nothing_places_is_still_listed(self, client, story, temp_db):
        cid = story["chat_id"]
        scene = _scene(temp_db, cid)
        scene["attire"]["Eve"] = {"wearing": ["cloak"], "state": [], "regions": {}}
        temp_db.wset(cid, "scene", scene)
        bodies = {b["name"]: b for b in
                  client.get(f"/api/chats/{cid}/rooms").json()["bodies"]}
        assert bodies["Eve"]["kind"] == "presence" and bodies["Eve"]["room"] is None

    def test_every_closed_set_comes_from_the_engine(self, client, story):
        from story.attire import GARMENT_STATES, REGIONS
        from world.spatial import (_VALID_BARRIERS, FOOTPRINTS, HEIGHTS,
                                   LIGHT_LEVELS, OPACITIES, ROOM_SIZES)
        from world.weather import EXPOSURES
        vocab = client.get(f"/api/chats/{story['chat_id']}/rooms").json()["vocab"]
        assert vocab["light"] == list(LIGHT_LEVELS)
        assert vocab["size"] == list(ROOM_SIZES)
        assert vocab["exposure"] == list(EXPOSURES)
        assert set(vocab["barriers"]) == set(_VALID_BARRIERS)
        assert vocab["heights"] == list(HEIGHTS)
        assert vocab["footprints"] == list(FOOTPRINTS)
        assert vocab["opacities"] == list(OPACITIES)
        assert vocab["attire_regions"] == list(REGIONS)
        assert vocab["garment_states"] == list(GARMENT_STATES)
        assert len(vocab["dirs"]) == 8 and "n" in vocab["dirs"]
        assert isinstance(vocab["regions"], list)


class TestAttireThroughThePut:
    """The Bodies tab writes the whole ledger through `PUT /attire`, which
    re-derives. The two faults that made the card editor unusable
    (`docs/UNBUILT.md` § 2.26): narrowing a spanning garment to one region,
    and resetting `state` to `worn`. The browser sends every copy of a
    spanning garment with the SAME state; the ledger keeps them one."""

    def test_a_spanning_garment_keeps_every_region_and_its_state(
            self, client, story, temp_db):
        cid = story["chat_id"]
        kimono = {"name": "silk kimono", "state": "open", "condition": "creased",
                  "covers": ["torso", "legs"]}
        ledger = client.get(f"/api/chats/{cid}/attire").json()
        ledger["Alice"] = {"wearing": [], "state": ["hair still damp"], "regions": {
            "torso": {"garments": [dict(kimono), {"name": "apron", "state": "worn"}],
                      "beneath": ""},
            "legs": {"garments": [dict(kimono)], "beneath": ""}}}
        r = client.put(f"/api/chats/{cid}/attire", json=ledger)
        assert r.status_code == 200, r.text
        stored = _scene(temp_db, cid)["attire"]["Alice"]
        torso = {g["name"]: g for g in stored["regions"]["torso"]["garments"]}
        legs = {g["name"]: g for g in stored["regions"]["legs"]["garments"]}
        assert torso["silk kimono"]["state"] == "open"
        assert legs["silk kimono"]["state"] == "open"
        assert torso["silk kimono"]["condition"] == "creased"
        assert set(torso["silk kimono"]["covers"]) == {"torso", "legs"}
        assert torso["apron"]["state"] == "worn"
        # `wearing` is re-derived and the authored note survives.
        assert set(stored["wearing"]) == {"silk kimono", "apron"}
        assert "hair still damp" in stored["state"]
        # The Bodies tab reads it back as one garment under two regions.
        alice = next(b for b in client.get(f"/api/chats/{cid}/rooms").json()["bodies"]
                     if b["name"] == "Alice")
        assert {g["name"] for g in alice["attire"]["regions"]["legs"]["garments"]} \
            == {"silk kimono"}


class TestWriteScoping:
    def test_a_frame_edit_lands_only_in_that_frame(self, client, story, temp_db):
        cid = story["chat_id"]
        r = client.post(f"/api/chats/{cid}/frames",
                        json={"label": "Decades Ago", "ordinal": -10, "kind": "past"})
        fid = r.json()["id"]
        temp_db.wset_for_frame(cid, "scene", {
            "location": "then", "rooms": {"kitchen": {"name": "Old Kitchen",
                                                      "adjacent": []}},
            "positions": {"Alice": "kitchen"}, "entities": {}, "attire": {}}, fid)
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen?frame_id={fid}",
                         json={"light": "dark"})
        assert r.status_code == 200, r.text
        assert temp_db.wget_for_frame(cid, "scene", fid)["rooms"]["kitchen"]["light"] == "dark"
        assert "light" not in _scene(temp_db, cid)["rooms"]["kitchen"]
        assert client.patch(f"/api/chats/{cid}/rooms/kitchen?frame_id=424242",
                            json={"light": "dark"}).status_code == 404
        assert client.put(f"/api/chats/{cid}/bodies/Alice/station?frame_id=424242",
                          json={"at": None}).status_code == 404

    def test_the_writes_are_host_only(self, story):
        from web.auth_routes import GUEST_ALLOWED_API_PATHS
        cid = story["chat_id"]
        for path in (f"/api/chats/{cid}/rooms", f"/api/chats/{cid}/rooms/kitchen",
                     f"/api/chats/{cid}/bodies/Alice/station"):
            assert path not in GUEST_ALLOWED_API_PATHS
        # No cookie at all: refused before the route runs.
        anonymous = TestClient(app_module.app)
        assert anonymous.patch(f"/api/chats/{cid}/rooms/kitchen",
                               json={"light": "dark"}).status_code in (401, 403)
        assert anonymous.put(f"/api/chats/{cid}/bodies/Alice/station",
                             json={"at": None}).status_code in (401, 403)

    def test_a_running_pipeline_refuses_the_edit(self, client, story, monkeypatch):
        from agents import runtime
        cid = story["chat_id"]
        monkeypatch.setitem(runtime.ABORTS, (cid, None), object())
        assert client.patch(f"/api/chats/{cid}/rooms/kitchen",
                            json={"light": "dark"}).status_code == 409
