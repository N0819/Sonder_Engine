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
    # The region's look goes through the regions route, never the room PATCH.
    assert "/regions/${encodeURIComponent(region)}${frameQuery()}" in browser
    # No closed set is typed into the browser: every select reads `vocab`.
    for word in ('"closed_door"', '"see_through"', '"loosened"', '"bright"',
                 '"round"', '"rectangle"', '"nw"', '"wall_overfull"'):
        assert word not in browser, word


def test_every_label_is_in_both_language_packs():
    en = json.loads((ROOT / "language_packs" / "en" / "ui.json").read_text())
    ja = json.loads((ROOT / "language_packs" / "ja" / "ui.json").read_text())
    for label in ("Rooms", "Bodies", "Raw JSON", "Where the cast stands",
                  "Reachable from the cast", "Not yet reachable", "Retired",
                  "Exits", "Who is here", "Things", "The plan here", "Move here",
                  "Anchors", "Add exit", "Add garment", "Saved.",
                  "No room '${room_id}' in this story",
                  "A room needs a name", "Extent (paces)", "Shape", "Add part",
                  "Look of the region", "Shared by every room in", "Layout",
                  "No wall", "${paces} paces", "derived from the extent"):
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


class TestRoomMeasurement:
    """The room's extent, shape and parts (`docs/design/DESIGN_ROOM_FIDELITY.md`
    §2) through the same PATCH, under the engine's own normalisers; size shown
    as derived while an extent stands; the lint's rows on the slice, filed
    beside the field each concerns."""

    def test_an_extent_lands_clamped_and_size_is_derived_from_it(
            self, client, story, temp_db):
        from world.spatial import EXTENT_MAX_PACES, size_from_extent
        cid = story["chat_id"]
        client.patch(f"/api/chats/{cid}/rooms/kitchen", json={"size": "tiny"})
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen",
                         json={"extent": {"w": 3, "d": 12}})
        assert r.status_code == 200, r.text
        record = r.json()["record"]
        room = _scene(temp_db, cid)["rooms"]["kitchen"]
        assert room["extent"] == {"w": 3, "d": 12}
        # The size WORD follows the measurement: the card shows it derived,
        # and the record says what the card shows.
        assert room["size"] == size_from_extent({"w": 3, "d": 12}) == "medium"
        assert record["extent"] == {"w": 3, "d": 12} and record["size"] == "medium"
        geometry = record["geometry"]
        assert geometry["measured"] is True and geometry["size_derived"] == "medium"
        assert (geometry["w"], geometry["d"]) == (3, 12)
        # Each straight wall's paces: the long walls are the depth, the
        # short ones the width.
        assert geometry["walls"] == {"n": 3, "s": 3, "e": 12, "w": 12}
        # No lint row: the word and the measurement agree.
        assert r.json()["lint"] == []
        # A number past the ceiling is clamped by the engine, not refused.
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen",
                         json={"extent": {"w": 99, "d": 1}})
        assert r.status_code == 200, r.text
        assert _scene(temp_db, cid)["rooms"]["kitchen"]["extent"] == {
            "w": EXTENT_MAX_PACES, "d": 2}

    def test_clearing_the_extent_returns_the_room_to_its_tier(
            self, client, story, temp_db):
        cid = story["chat_id"]
        client.patch(f"/api/chats/{cid}/rooms/kitchen", json={"extent": {"w": 4, "d": 4}})
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen", json={"extent": None})
        assert r.status_code == 200, r.text
        room = _scene(temp_db, cid)["rooms"]["kitchen"]
        assert "extent" not in room
        # The size word the extent wrote stays: the room does not shrink to
        # an unsized default because its measurement was withdrawn.
        assert room["size"] == "small"
        geometry = r.json()["record"]["geometry"]
        assert geometry["measured"] is False and geometry["size_derived"] is None
        assert geometry["w"] == geometry["d"] == 4

    @pytest.mark.parametrize("bad", [
        {"w": 5}, {"w": "wide", "d": 3}, {"w": 0, "d": 3}, "3x4", 7,
    ])
    def test_an_extent_that_is_not_a_measurement_is_refused_naming_the_range(
            self, client, story, temp_db, bad):
        from world.spatial import EXTENT_MAX_PACES, EXTENT_MIN_PACES
        cid = story["chat_id"]
        before = json.dumps(_scene(temp_db, cid), sort_keys=True)
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen", json={"extent": bad})
        assert r.status_code == 400, r.text
        detail = r.json()["detail"]
        assert str(EXTENT_MIN_PACES) in detail and str(EXTENT_MAX_PACES) in detail
        assert json.dumps(_scene(temp_db, cid), sort_keys=True) == before

    def test_a_shape_lands_and_a_word_outside_the_set_is_refused(
            self, client, story, temp_db):
        cid = story["chat_id"]
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen", json={"shape": "round"})
        assert r.status_code == 200, r.text
        assert _scene(temp_db, cid)["rooms"]["kitchen"]["shape"] == "round"
        assert r.json()["record"]["shape"] == "round"
        assert r.json()["record"]["geometry"]["shape"] == "round"
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen", json={"shape": "hexagon"})
        assert r.status_code == 400
        assert "rectangle" in r.json()["detail"] and "hexagon" in r.json()["detail"]
        # Empty clears: the rectangle, which the record reports as unset.
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen", json={"shape": ""})
        assert "shape" not in _scene(temp_db, cid)["rooms"]["kitchen"]
        assert r.json()["record"]["shape"] == ""

    def test_l_parts_land_normalised_and_a_bad_corner_is_refused(
            self, client, story, temp_db):
        cid = story["chat_id"]
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen", json={
            "shape": "l", "extent": {"w": 8, "d": 8},
            "parts": [{"w": 8, "d": 3, "at": "north-west"},
                      {"w": 3, "d": 8, "at": "se"}]})
        assert r.status_code == 200, r.text
        room = _scene(temp_db, cid)["rooms"]["kitchen"]
        # The corner word folded to the compass, the sides whole paces.
        assert room["parts"] == [{"w": 8, "d": 3, "at": "nw"}, {"w": 3, "d": 8, "at": "se"}]
        assert r.json()["record"]["parts"] == room["parts"]
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen",
                         json={"parts": [{"w": 4, "d": 4, "at": "n"}]})
        assert r.status_code == 400
        assert "at" in r.json()["detail"] and "sw" in r.json()["detail"]
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen",
                         json={"parts": [{"w": 4, "at": "ne"}]})
        assert r.status_code == 400 and "paces" in r.json()["detail"]
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen", json={"parts": "two"})
        assert r.status_code == 400
        # An empty list clears.
        client.patch(f"/api/chats/{cid}/rooms/kitchen", json={"parts": []})
        assert "parts" not in _scene(temp_db, cid)["rooms"]["kitchen"]

    def test_the_slice_carries_the_lint_rows_naming_the_room_beside_their_field(
            self, client, story, temp_db):
        from web.world_routes import LINT_FIELDS
        from world.spatial import LAYOUT_LINT_KINDS
        assert set(LINT_FIELDS) == set(LAYOUT_LINT_KINDS)
        cid = story["chat_id"]
        scene = _scene(temp_db, cid)
        # Three anchors on a two-pace north wall (the lint's own fixture), a
        # size word that disagrees with the extent, and corner parts on a
        # round room -- three rows, three fields.
        scene["rooms"]["kitchen"].update({
            "extent": {"w": 2, "d": 6}, "size": "vast", "shape": "round",
            "parts": [{"w": 2, "d": 2, "at": "ne"}],
            "anchors": {"a": {"desc": "a chest", "dir": "n"},
                        "b": {"desc": "a crate", "dir": "n"},
                        "c": {"desc": "a barrel", "dir": "n"}}})
        temp_db.wset(cid, "scene", scene)
        slice_ = client.get(f"/api/chats/{cid}/rooms/kitchen").json()
        rows = {r["kind"]: r for r in slice_["lint"]}
        assert set(rows) == {"wall_overfull", "size_disagrees_with_extent",
                             "corner_in_round_room"}
        assert rows["wall_overfull"]["field"] == "anchors"
        assert rows["wall_overfull"]["wall"] == "n"
        assert "cannot hold" in rows["wall_overfull"]["text"]
        assert rows["size_disagrees_with_extent"]["field"] == "extent"
        assert rows["corner_in_round_room"]["field"] == "shape"
        assert all(r["rooms"] == ["kitchen"] for r in slice_["lint"])
        # A room the lint does not name carries no row, and the index marks
        # only the room that does.
        assert client.get(f"/api/chats/{cid}/rooms/study").json()["lint"] == []
        rows_ = {r["id"]: r for rows_ in client.get(f"/api/chats/{cid}/rooms")
                 .json()["groups"].values() for r in rows_}
        assert rows_["kitchen"]["lint"] == 3 and rows_["study"]["lint"] == 0

    def test_a_pair_row_names_both_rooms(self, client, story, temp_db):
        cid = story["chat_id"]
        scene = _scene(temp_db, cid)
        for edge in scene["rooms"]["kitchen"]["adjacent"]:
            if edge["to"] == "hallway":
                edge["dir"] = "n"
        for edge in scene["rooms"]["hallway"]["adjacent"]:
            if edge["to"] == "kitchen":
                edge["dir"] = "e"
        temp_db.wset(cid, "scene", scene)
        for rid in ("kitchen", "hallway"):
            (row,) = [r for r in client.get(f"/api/chats/{cid}/rooms/{rid}").json()["lint"]
                      if r["kind"] == "reciprocal_bearing_disagrees"]
            assert row["field"] == "exits"
            assert set(row["rooms"]) == {"kitchen", "hallway"}

    def test_stationable_anchors_carry_their_bearing(self, client, story, temp_db):
        cid = story["chat_id"]
        client.patch(f"/api/chats/{cid}/rooms/kitchen", json={"exits": [
            {"to": "hallway", "barrier": "open", "dir": "e"},
            {"to": "cellar", "barrier": "closed_door"}]})
        stationable = {a["id"]: a for a in
                       client.get(f"/api/chats/{cid}/rooms/kitchen").json()["stationable"]}
        assert stationable["door:hallway"]["implicit"] is True
        assert stationable["door:hallway"]["dir"] == "e"
        assert stationable["door:cellar"]["dir"] is None
        assert stationable["oak_table"]["dir"] is None


class TestRegionLook:
    def test_the_look_is_written_once_and_read_from_every_room_in_the_region(
            self, client, story, temp_db):
        cid = story["chat_id"]
        for rid in ("kitchen", "hallway"):
            client.patch(f"/api/chats/{cid}/rooms/{rid}", json={"region": "East Wing"})
        assert client.get(f"/api/chats/{cid}/rooms/kitchen").json()["region_look"] == ""
        r = client.patch(f"/api/chats/{cid}/regions/east_wing",
                         json={"look": "  brick and iron   under sodium lamps "})
        assert r.status_code == 200, r.text
        assert r.json()["id"] == "east_wing"
        assert r.json()["look"] == "brick and iron under sodium lamps"
        assert r.json()["rooms"] == ["hallway", "kitchen"]
        # The registry holds it (`world.regions.region_registry`), and both
        # rooms' cards read it.
        from world.regions import region_registry
        assert region_registry(cid, None)["east_wing"]["look"] == \
            "brick and iron under sodium lamps"
        for rid in ("kitchen", "hallway"):
            assert client.get(f"/api/chats/{cid}/rooms/{rid}").json()["region_look"] == \
                "brick and iron under sodium lamps"
        # The vocab's region list carries it too, for the datalist.
        vocab = client.get(f"/api/chats/{cid}/rooms").json()["vocab"]
        assert {"id": "east_wing", "name": "east_wing",
                "look": "brick and iron under sodium lamps"} in vocab["regions"]
        # A room in no region reads no look; the scene itself is untouched.
        assert client.get(f"/api/chats/{cid}/rooms/study").json()["region_look"] == ""
        assert "look" not in json.dumps(_scene(temp_db, cid))
        # An empty look removes the field.
        r = client.patch(f"/api/chats/{cid}/regions/east_wing", json={"look": ""})
        assert r.status_code == 200 and r.json()["look"] == ""
        assert "look" not in region_registry(cid, None)["east_wing"]

    def test_the_route_is_era_scoped_and_refuses_a_bad_body(self, client, story, temp_db):
        cid = story["chat_id"]
        r = client.post(f"/api/chats/{cid}/frames",
                        json={"label": "Decades Ago", "ordinal": -10, "kind": "past"})
        fid = r.json()["id"]
        r = client.patch(f"/api/chats/{cid}/regions/old_town?frame_id={fid}",
                         json={"look": "gaslight"})
        assert r.status_code == 200, r.text
        from world.regions import region_registry
        assert region_registry(cid, fid)["old_town"]["look"] == "gaslight"
        assert "old_town" not in region_registry(cid, None)
        assert client.patch(f"/api/chats/{cid}/regions/old_town?frame_id=424242",
                            json={"look": "x"}).status_code == 404
        assert client.patch(f"/api/chats/{cid}/regions/old_town",
                            json={}).status_code == 400
        assert client.patch(f"/api/chats/{cid}/regions/old_town",
                            json={"look": ["x"]}).status_code == 400

    def test_the_route_is_host_only_and_idle_guarded(self, client, story, monkeypatch):
        from agents import runtime
        from web.auth_routes import GUEST_ALLOWED_API_PATHS
        cid = story["chat_id"]
        assert f"/api/chats/{cid}/regions/east_wing" not in GUEST_ALLOWED_API_PATHS
        anonymous = TestClient(app_module.app)
        assert anonymous.patch(f"/api/chats/{cid}/regions/east_wing",
                               json={"look": "x"}).status_code in (401, 403)
        monkeypatch.setitem(runtime.ABORTS, (cid, None), object())
        assert client.patch(f"/api/chats/{cid}/regions/east_wing",
                            json={"look": "x"}).status_code == 409


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
        from world.spatial import (_VALID_BARRIERS, EXTENT_MAX_PACES,
                                   EXTENT_MIN_PACES, FOOTPRINTS, HEIGHTS,
                                   LIGHT_LEVELS, OPACITIES, ROOM_CORNERS,
                                   ROOM_SIZES, SHAPES)
        from world.weather import EXPOSURES
        vocab = client.get(f"/api/chats/{story['chat_id']}/rooms").json()["vocab"]
        assert vocab["light"] == list(LIGHT_LEVELS)
        assert vocab["size"] == list(ROOM_SIZES)
        assert vocab["exposure"] == list(EXPOSURES)
        assert set(vocab["barriers"]) == set(_VALID_BARRIERS)
        assert vocab["heights"] == list(HEIGHTS)
        assert vocab["footprints"] == list(FOOTPRINTS)
        assert vocab["opacities"] == list(OPACITIES)
        assert vocab["shapes"] == list(SHAPES)
        assert vocab["corners"] == list(ROOM_CORNERS)
        assert vocab["walls"] == ["n", "e", "s", "w"]
        assert vocab["extent"] == {"min": EXTENT_MIN_PACES, "max": EXTENT_MAX_PACES}
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


# ---- the map editor's reads, and `offset` -----------------------------------

def _seeded(*parts):
    """`spatial_fov._seed`, copied so the pin below is against the formula
    the geometry note wrote rather than against the code under test."""
    import hashlib
    joined = "\x1f".join(str(p) for p in parts)
    return int(hashlib.sha1(joined.encode("utf-8")).hexdigest()[:8], 16)


def _lay_out(temp_db, cid, shape=None, parts=None):
    """The manor with geometry: the kitchen measured 8x4 with a hearth on
    its west wall and the oak table standing free, the hallway east of it
    through a doorway beared from both sides, the study north of the
    hallway behind a closed door; Alice at the hearth, facing east."""
    scene = _scene(temp_db, cid)
    kitchen = scene["rooms"]["kitchen"]
    kitchen["extent"] = {"w": 8, "d": 4}
    if shape:
        kitchen["shape"] = shape
    if parts:
        kitchen["parts"] = parts
    kitchen["anchors"] = {
        "hearth": {"desc": "the hearth", "dir": "w", "height": "waist"},
        "oak_table": {"desc": "the oak table", "footprint": "large",
                      "height": "waist"},
    }
    bearings = {("kitchen", "hallway"): "e", ("hallway", "kitchen"): "w",
                ("hallway", "study"): "n", ("study", "hallway"): "s"}
    for rid, room in scene["rooms"].items():
        for edge in room.get("adjacent") or []:
            if (rid, edge["to"]) in bearings:
                edge["dir"] = bearings[(rid, edge["to"])]
    scene["stations"] = {"Alice": {"at": "hearth", "near": []}}
    scene["orientation"] = {"Alice": {"facing": "e"}}
    temp_db.wset(cid, "scene", scene)
    return scene


class TestTheGridAndTheMap:
    def test_the_grid_is_the_engines_own_for_a_rectangle(self, client, story, temp_db):
        from world.spatial import anchor_cells, body_cell, room_field
        cid = story["chat_id"]
        scene = _lay_out(temp_db, cid)
        r = client.get(f"/api/chats/{cid}/rooms/kitchen/grid")
        assert r.status_code == 200, r.text
        view = r.json()
        assert view["frame_id"] is None
        assert view["room"] == {
            "id": "kitchen", "name": "Kitchen", "w": 8, "d": 4,
            "shape": "rectangle", "measured": True,
            "cells": [[x, y] for x in range(8) for y in range(4)]}
        # The rims in `RoomGrid.rim`'s order -- the order `offset` counts in.
        assert view["rims"]["n"] == [[x, 0] for x in range(8)]
        assert view["rims"]["e"] == [[7, y] for y in range(4)]
        # Anchors exactly where `anchor_cells` puts them; the doorways are
        # not anchors here but a list of their own.
        placed = anchor_cells(scene, "kitchen")
        hearth = view["anchors"]["hearth"]
        assert hearth["cells"] == [list(c) for c in placed["hearth"]["cells"]]
        assert hearth["dir"] == "w" and hearth["height"] == "waist"
        assert hearth["footprint"] == "point" and hearth["opacity"] == "opaque"
        assert hearth["offset"] is None and hearth["implicit"] is False
        assert set(view["anchors"]) == {"hearth", "oak_table"}
        doors = {d["to"]: d for d in view["doorways"]}
        assert doors["hallway"]["dir"] == "e"
        assert doors["hallway"]["cells"] == [list(c) for c in placed["door:hallway"]["cells"]]
        assert doors["hallway"]["barrier"] == "open"
        assert doors["hallway"]["status"] == "live" and doors["hallway"]["name"] == "Hallway"
        # A doorway with no bearing has no wall to stand in: listed, no cells.
        assert doors["cellar"]["dir"] is None and doors["cellar"]["cells"] == []
        assert doors["cellar"]["barrier"] == "closed_door"
        # Bodies: the one standing here, at the cell `body_cell` derives,
        # with its facing, kind and station.
        assert set(view["bodies"]) == {"Alice"}
        alice = view["bodies"]["Alice"]
        assert alice["cell"] == list(body_cell(scene, "Alice"))
        assert alice["measured"] is True and alice["facing"] == "e"
        assert alice["kind"] == "cast" and alice["at"] == "hearth" and alice["near"] == []
        # The oak table is an entity AND an anchor of the room: filed as the
        # anchor, so the map draws it once.
        (table,) = view["things"]
        assert table["id"] == "oak_table" and table["placed"] == "anchor"
        assert table["anchor"] == "oak_table" and table["cell"] is None
        # The hallway placed exactly as `room_field` places it, its cells in
        # its own frame, its anchors along (the study is behind a closed door
        # and casts nothing here).
        field = room_field(scene, "kitchen")
        (hall,) = view["neighbours"]
        assert hall["id"] == "hallway" and hall["name"] == "Hallway"
        assert hall["offset"] == list(field.offsets["hallway"])
        assert hall["cells"] == [[x, y] for x in range(6) for y in range(6)]
        assert "door:kitchen" in hall["anchors"]
        # The wall between them as a line: the column past the east wall,
        # its aperture one cell wide, the neighbour named.
        (wall,) = view["walls"]
        assert wall["to"] == "hallway" and wall["name"] == "Hallway"
        assert wall["axis"] == 0 and wall["coord"] == 8
        assert wall["aperture"][1] - wall["aperture"][0] == 1.0
        assert view["lint"] == []
        # The overlays slot is filled by the readers the composer uses: the
        # light field's word per cell and the sound field's noise floor,
        # each quantised with its own ladder, over the room's own cells.
        from world.spatial import LIGHT_LEVELS, NOISE_WORDS
        assert set(view["overlays"]) == {"light", "noise"}
        for name, ladder in (("light", LIGHT_LEVELS), ("noise", NOISE_WORDS)):
            readings = view["overlays"][name]
            assert set(readings) == {f"{x},{y}" for x, y in view["room"]["cells"]}
            assert set(readings.values()) <= set(ladder)
        assert view["sound_sources"] == [] and view["light_sources"] == []

    @pytest.mark.parametrize("shape, parts", [
        ("round", None),
        ("l", [{"w": 8, "d": 2, "at": "nw"}, {"w": 3, "d": 4, "at": "ne"}]),
    ])
    def test_a_shaped_room_reports_the_shapes_cells_and_rims(
            self, client, story, temp_db, shape, parts):
        from world.spatial import room_grid
        cid = story["chat_id"]
        scene = _lay_out(temp_db, cid, shape=shape, parts=parts)
        view = client.get(f"/api/chats/{cid}/rooms/kitchen/grid").json()
        grid = room_grid(scene, "kitchen")
        assert view["room"]["shape"] == shape
        assert view["room"]["cells"] == [list(c) for c in sorted(grid.cells)]
        assert 0 < len(view["room"]["cells"]) < 32          # not the box
        for wall in ("n", "e", "s", "w"):
            assert view["rims"][wall] == [list(c) for c in grid.rim(wall)]
        # Everything placed stands on a cell of the shape.
        cells = {tuple(c) for c in view["room"]["cells"]}
        for anchor in view["anchors"].values():
            assert anchor["cells"] and all(tuple(c) in cells for c in anchor["cells"])
        for door in view["doorways"]:
            assert all(tuple(c) in cells for c in door["cells"])
        assert tuple(view["bodies"]["Alice"]["cell"]) in cells

    def test_the_grid_of_a_room_with_no_geometry_is_the_tiers_square(
            self, client, story):
        cid = story["chat_id"]
        view = client.get(f"/api/chats/{cid}/rooms/garden/grid").json()
        assert view["room"]["measured"] is False
        assert (view["room"]["w"], view["room"]["d"]) == (6, 6)
        assert view["anchors"] == {} and view["doorways"] == []
        assert view["bodies"] == {} and view["neighbours"] == [] and view["walls"] == []

    def test_an_unmeasured_body_has_no_cell(self, client, story, temp_db):
        cid = story["chat_id"]
        _lay_out(temp_db, cid)
        view = client.get(f"/api/chats/{cid}/rooms/hallway/grid").json()
        bob = view["bodies"]["Bob"]
        assert bob["cell"] is None and bob["measured"] is False
        assert bob["at"] is None and bob["kind"] == "cast"
        # The player is a body too, by kind.
        view = client.get(f"/api/chats/{cid}/rooms/study/grid").json()
        assert view["bodies"]["Nathan"]["kind"] == "player"
        # The vehicle standing in the study is a thing placed by position,
        # not a body; with no station it has no cell either.
        (tardis,) = view["things"]
        assert tardis["id"] == "tardis" and tardis["placed"] == "position"
        assert tardis["cell"] is None and tardis["anchor"] is None

    def test_the_map_places_the_rooms_by_bearing_and_draws_an_overlap(
            self, client, story, temp_db):
        from world.spatial import layout_rooms
        cid = story["chat_id"]
        scene = _lay_out(temp_db, cid)
        r = client.get(f"/api/chats/{cid}/map")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["location"] == "Old Manor" and data["frame_id"] is None
        comps = {c["start"]: c for c in data["components"]}
        # One component per connected set of beared edges, from its
        # smallest id; a room with no beared edge is a component of one.
        assert set(comps) == {"cellar", "console_room", "garden", "hallway"}
        comp = comps["hallway"]
        rows = {row["id"]: row for row in comp["rooms"]}
        assert set(rows) == {"hallway", "kitchen", "study"}
        layout = layout_rooms(scene, "hallway")
        for rid, offset in layout["offsets"].items():
            assert rows[rid]["offset"] == list(offset)
        assert rows["hallway"]["offset"] == [0, 0]
        assert (rows["kitchen"]["w"], rows["kitchen"]["d"]) == (8, 4)
        assert rows["kitchen"]["measured"] is True and rows["hallway"]["measured"] is False
        assert rows["kitchen"]["cells"] == [[x, y] for x in range(8) for y in range(4)]
        exits = {e["to"]: e for e in rows["kitchen"]["exits"]}
        from world.spatial import _door_cells
        door, _bearing = _door_cells(scene, "kitchen", "hallway")
        assert exits["hallway"] == {"to": "hallway", "name": "Hallway", "dir": "e",
                                    "barrier": "open", "placed": True,
                                    # The door's cells in the kitchen's own
                                    # frame (the structure map draws the
                                    # doorway where it stands), and no
                                    # passage record: the exits are edges.
                                    "cells": [[x, y] for x, y in sorted(door)],
                                    "passage": None}
        assert exits["cellar"]["dir"] is None and exits["cellar"]["placed"] is False
        assert exits["cellar"]["cells"] == []
        # The room each was placed FROM, the edge a structure-map drag
        # re-bears; the start of the component has none.
        assert rows["kitchen"]["placed_via"] == "hallway"
        assert rows["hallway"]["placed_via"] is None
        assert rows["kitchen"]["region"] is None
        assert rows["kitchen"]["occupants"] == ["Alice"]
        assert rows["study"]["occupants"] == ["Nathan"]
        assert all(row["lint"] == 0 and row["collided"] is False for row in rows.values())
        assert comp["collisions"] == []
        assert comps["console_room"]["rooms"][0]["holder"] == "tardis"
        assert comps["garden"]["rooms"][0]["offset"] == [0, 0]

        # An overlap: a pantry hung off the hallway's west wall, where the
        # kitchen already is. The doorways are pinned by `offset` so the two
        # rooms meet whatever the seeds say: the kitchen's at the north end
        # of the wall, the pantry's at the south end, four paces deep each.
        for edge in scene["rooms"]["kitchen"]["adjacent"]:
            if edge["to"] == "hallway":
                edge["offset"] = 0.0
        for edge in scene["rooms"]["hallway"]["adjacent"]:
            if edge["to"] == "kitchen":
                edge["offset"] = 0.0
        scene["rooms"]["pantry"] = {
            "name": "Pantry", "size": "small",
            "adjacent": [{"to": "hallway", "barrier": "open", "dir": "e", "offset": 1.0}]}
        scene["rooms"]["hallway"]["adjacent"].append(
            {"to": "pantry", "barrier": "open", "dir": "w", "offset": 1.0})
        temp_db.wset(cid, "scene", scene)
        data = client.get(f"/api/chats/{cid}/map").json()
        comp = {c["start"]: c for c in data["components"]}["hallway"]
        rows = {row["id"]: row for row in comp["rooms"]}
        pantry = rows["pantry"]
        # Drawn, never hidden: at the offset the rule gave it, flagged with
        # the room it lands on and the doorway it was reached through.
        assert pantry["collided"] is True
        assert pantry["onto"] == "kitchen" and pantry["via"] == "hallway"
        assert comp["collisions"] == [{"room": "pantry", "onto": "kitchen", "via": "hallway"}]
        layout = layout_rooms(scene, "hallway")
        assert "pantry" not in layout["offsets"]
        assert pantry["offset"] == list(layout["collided"]["pantry"])
        kitchen_cells = {(x + rows["kitchen"]["offset"][0], y + rows["kitchen"]["offset"][1])
                         for x, y in rows["kitchen"]["cells"]}
        pantry_cells = {(x + pantry["offset"][0], y + pantry["offset"][1])
                        for x, y in pantry["cells"]}
        assert kitchen_cells & pantry_cells
        # The lint names the pair, and each room's row counts it.
        assert pantry["lint"] >= 1 and rows["kitchen"]["lint"] >= 1

    def test_the_reads_are_host_only_frame_scoped_and_404_off_the_scene(
            self, client, story):
        from web.auth_routes import GUEST_ALLOWED_API_PATHS
        cid = story["chat_id"]
        # A planned room has no grid; a frame of another story is a 404.
        r = client.get(f"/api/chats/{cid}/rooms/attic/grid")
        assert r.status_code == 404 and "planned" in r.json()["detail"]
        assert client.get(f"/api/chats/{cid}/rooms/nowhere/grid").status_code == 404
        assert client.get(f"/api/chats/{cid}/rooms/kitchen/grid?frame_id=424242").status_code == 404
        assert client.get(f"/api/chats/{cid}/map?frame_id=424242").status_code == 404
        assert client.get("/api/chats/424242/map").status_code == 404
        for path in (f"/api/chats/{cid}/rooms/kitchen/grid", f"/api/chats/{cid}/map"):
            assert path not in GUEST_ALLOWED_API_PATHS
            anonymous = TestClient(app_module.app)
            assert anonymous.get(path).status_code in (401, 403)


class TestOffset:
    def test_an_anchor_offset_lands_and_moves_the_anchor_along_its_wall(
            self, client, story, temp_db):
        from world.spatial import anchor_cells
        cid = story["chat_id"]
        client.patch(f"/api/chats/{cid}/rooms/kitchen", json={"extent": {"w": 8, "d": 4}})
        hearth = {"desc": "the hearth", "dir": "n"}
        grid_of = lambda: client.get(f"/api/chats/{cid}/rooms/kitchen/grid").json()
        # 0 is the wall's start: the west end of the north wall.
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen",
                         json={"anchors": {"hearth": {**hearth, "offset": 0}}})
        assert r.status_code == 200, r.text
        assert _scene(temp_db, cid)["rooms"]["kitchen"]["anchors"]["hearth"]["offset"] == 0.0
        assert r.json()["record"]["anchors"]["hearth"]["offset"] == 0.0
        view = grid_of()
        assert view["anchors"]["hearth"]["cells"] == [[0, 0]]
        assert view["anchors"]["hearth"]["offset"] == 0.0
        # 1 is its far end; 0.5 the middle. A numeric string is a number.
        client.patch(f"/api/chats/{cid}/rooms/kitchen",
                     json={"anchors": {"hearth": {**hearth, "offset": 1}}})
        assert grid_of()["anchors"]["hearth"]["cells"] == [[7, 0]]
        client.patch(f"/api/chats/{cid}/rooms/kitchen",
                     json={"anchors": {"hearth": {**hearth, "offset": "0.5"}}})
        assert grid_of()["anchors"]["hearth"]["cells"] == [[4, 0]]
        # A run counts its offset over the positions its length leaves, and
        # a standing thing keeps its one pace off the wall.
        client.patch(f"/api/chats/{cid}/rooms/kitchen", json={"anchors": {
            "hearth": {**hearth, "offset": 1, "footprint": "run", "height": "waist"}}})
        assert grid_of()["anchors"]["hearth"]["cells"] == [[x, 1] for x in range(2, 8)]
        # Refused outside the range, naming it; never clamped.
        for bad in (1.5, -0.2, "far", [0.5], True):
            r = client.patch(f"/api/chats/{cid}/rooms/kitchen",
                             json={"anchors": {"hearth": {**hearth, "offset": bad}}})
            assert r.status_code == 400, bad
            assert "between 0 and 1" in r.json()["detail"] and "hearth" in r.json()["detail"]
        assert _scene(temp_db, cid)["rooms"]["kitchen"]["anchors"]["hearth"]["offset"] == 1.0
        # Absent or null clears it, and the anchor is back where the seed
        # put it -- exactly what `anchor_cells` says of a room with no offset.
        for cleared in ({**hearth}, {**hearth, "offset": None}, {**hearth, "offset": ""}):
            r = client.patch(f"/api/chats/{cid}/rooms/kitchen",
                             json={"anchors": {"hearth": cleared}})
            assert r.status_code == 200, r.text
            stored = _scene(temp_db, cid)["rooms"]["kitchen"]["anchors"]["hearth"]
            assert "offset" not in stored
        scene = _scene(temp_db, cid)
        seeded = anchor_cells(scene, "kitchen")["hearth"]["cells"]
        assert grid_of()["anchors"]["hearth"]["cells"] == [list(c) for c in seeded]
        start = 1 + _seeded("kitchen", "hearth") % 6
        assert seeded == [(start, 0)]
        # A corner anchor has no wall to run along: the offset is kept on the
        # record and moves nothing.
        client.patch(f"/api/chats/{cid}/rooms/kitchen",
                     json={"anchors": {"hearth": {"desc": "the hearth", "dir": "ne", "offset": 0}}})
        assert grid_of()["anchors"]["hearth"]["cells"] == [[7, 0]]

    def test_a_doorways_offset_is_written_on_both_edges_and_places_the_door(
            self, client, story, temp_db):
        cid = story["chat_id"]
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen", json={
            "extent": {"w": 8, "d": 4},
            "exits": [{"to": "hallway", "barrier": "open", "dir": "e", "offset": 1.0},
                      {"to": "cellar", "barrier": "closed_door"}]})
        assert r.status_code == 200, r.text
        scene = _scene(temp_db, cid)
        (mine,) = [e for e in scene["rooms"]["kitchen"]["adjacent"] if e["to"] == "hallway"]
        (theirs,) = [e for e in scene["rooms"]["hallway"]["adjacent"] if e["to"] == "kitchen"]
        # One doorway, one place along the wall: the same fraction from
        # either side, since a wall's start is the same end from both rooms.
        assert mine["offset"] == 1.0 and mine["dir"] == "e"
        assert theirs["offset"] == 1.0 and theirs["dir"] == "w"
        doors = {d["to"]: d for d in
                 client.get(f"/api/chats/{cid}/rooms/kitchen/grid").json()["doorways"]}
        assert doors["hallway"]["cells"] == [[7, 3]] and doors["hallway"]["offset"] == 1.0
        far = {d["to"]: d for d in
               client.get(f"/api/chats/{cid}/rooms/hallway/grid").json()["doorways"]}
        assert far["kitchen"]["cells"] == [[0, 5]]
        # Refused outside the range.
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen", json={"exits": [
            {"to": "hallway", "barrier": "open", "dir": "e", "offset": 2}]})
        assert r.status_code == 400 and "between 0 and 1" in r.json()["detail"]
        # An exit list that says nothing about the offset keeps it on both
        # sides (the card's ordinary barrier edit); null clears both.
        client.patch(f"/api/chats/{cid}/rooms/kitchen", json={"exits": [
            {"to": "hallway", "barrier": "open_door", "dir": "e"}]})
        scene = _scene(temp_db, cid)
        (mine,) = [e for e in scene["rooms"]["kitchen"]["adjacent"] if e["to"] == "hallway"]
        (theirs,) = [e for e in scene["rooms"]["hallway"]["adjacent"] if e["to"] == "kitchen"]
        assert mine["offset"] == 1.0 and theirs["offset"] == 1.0
        assert mine["barrier"] == "open_door" and theirs["barrier"] == "open_door"
        client.patch(f"/api/chats/{cid}/rooms/kitchen", json={"exits": [
            {"to": "hallway", "barrier": "open_door", "dir": "e", "offset": None}]})
        scene = _scene(temp_db, cid)
        (mine,) = [e for e in scene["rooms"]["kitchen"]["adjacent"] if e["to"] == "hallway"]
        (theirs,) = [e for e in scene["rooms"]["hallway"]["adjacent"] if e["to"] == "kitchen"]
        assert "offset" not in mine and "offset" not in theirs

    def test_placement_without_an_offset_is_the_seeded_placement_byte_for_byte(self):
        """THE FAIL-OPEN PIN for `offset`. A room whose anchors and edges
        carry no offset -- every room in every existing scene -- is placed
        by the seeded formula the geometry note wrote, on every shape; and
        an offset that reads as nothing (null, prose, a boolean, a number
        outside [0, 1]) is the same as none. The reference formula is
        copied here, not imported, so a drift is a failing test."""
        import copy
        from world.spatial import anchor_cells, room_grid
        anchors = {
            "bar": {"desc": "the long bar", "dir": "n", "footprint": "run",
                    "height": "waist"},
            "hearth": {"desc": "the hearth", "dir": "s"},
            "door": {"desc": "the front door", "dir": "w"},
            "rack": {"desc": "a rack", "dir": "e", "footprint": "small"},
            "keg": {"desc": "a keg", "dir": "e", "footprint": "large"},
            "urn": {"desc": "an urn", "dir": "ne", "height": "waist"},
            "stool": {"desc": "a stool"},
        }
        shapes = (
            {"size": "large"},
            {"extent": {"w": 12, "d": 4}},
            {"extent": {"w": 8, "d": 8}, "shape": "round"},
            {"extent": {"w": 8, "d": 8}, "shape": "l",
             "parts": [{"w": 8, "d": 3, "at": "nw"}, {"w": 3, "d": 8, "at": "ne"}]},
        )
        for room in shapes:
            sc = {"rooms": {"r": {"name": "R", **room, "anchors": dict(anchors),
                                  "adjacent": [{"to": "q", "barrier": "open", "dir": "n"}]},
                            "q": {"name": "Q", "size": "small"}},
                  "positions": {}, "stations": {}, "entities": {}}
            bare = anchor_cells(sc, "r")
            assert "door:q" in bare
            assert all(rec["offset"] is None for rec in bare.values())
            for junk in (None, "half", True, 1.5, -0.1, [0.5], {"along": 0.5}):
                sc2 = copy.deepcopy(sc)
                for anchor in sc2["rooms"]["r"]["anchors"].values():
                    anchor["offset"] = junk
                sc2["rooms"]["r"]["adjacent"][0]["offset"] = junk
                assert {aid: rec["cells"] for aid, rec in anchor_cells(sc2, "r").items()} \
                    == {aid: rec["cells"] for aid, rec in bare.items()}, junk
            # The seeded index along the wall's own rim, as the note wrote it.
            grid = room_grid(sc, "r")
            for aid, rec in bare.items():
                if rec["dir"] not in ("n", "e", "s", "w"):
                    continue
                rim = grid.rim(rec["dir"])
                along = len(rim)
                length = {"point": 1, "small": 2, "large": 2,
                          "run": max(2, along - 2)}[rec["footprint"]]
                start = 1 + _seeded("r", aid) % max(1, along - 2 - (length - 1)) \
                    if along > 2 else 0
                expected = [rim[(start + i) % along] for i in range(length)]
                axis = 0 if rec["dir"] in ("n", "s") else 1
                got = {c[axis] for c in rec["cells"]}
                assert got and got <= {c[axis] for c in expected}, (room, aid)

    def test_the_merge_keeps_an_anchors_offset_a_re_echo_left_out(self):
        from world.spatial import _merge_room
        existing = {"name": "R",
                    "adjacent": [{"to": "q", "barrier": "open", "dir": "n", "offset": 0.25}],
                    "anchors": {"bar": {"desc": "the bar", "dir": "n", "height": "waist",
                                        "offset": 0.75}}}
        merged = _merge_room(existing, {
            "name": "R", "adjacent": [{"to": "q", "barrier": "open_door"}],
            "anchors": {"bar": {"desc": "the long bar", "dir": "n", "height": ""}}}, "r")
        # Silence keeps the offset and the height; a value lands.
        assert merged["anchors"]["bar"] == {"desc": "the long bar", "dir": "n",
                                            "height": "waist", "offset": 0.75}
        assert merged["adjacent"] == [{"to": "q", "barrier": "open_door", "dir": "n",
                                       "offset": 0.25}]
        merged = _merge_room(existing, {"anchors": {
            "bar": {"desc": "the bar", "offset": 0.1}, "keg": {"desc": "a keg"}}}, "r")
        assert merged["anchors"]["bar"]["offset"] == 0.1
        assert merged["anchors"]["bar"]["height"] == "waist"
        assert merged["anchors"]["keg"] == {"desc": "a keg"}
        # An anchor the map does not name is still dropped: the map is
        # written whole, and `{}` alone is silence.
        merged = _merge_room(existing, {"anchors": {"keg": {"desc": "a keg"}}}, "r")
        assert "bar" not in merged["anchors"]
        merged = _merge_room(existing, {"anchors": {}}, "r")
        assert merged["anchors"]["bar"]["offset"] == 0.75


class TestCells:
    """`cell` on a station and on an anchor -- the map editor's placement on
    ANY cell (the owner, 2026-09-04: "why are characters and personas
    locked to stations?"; "I can only place anchors at stations when I
    don't wall-attach them"). The engine's side is `tests/test_body_cells.py`;
    here, the routes: a cell lands, is refused outside naming the bounds,
    clears, is exclusive with an anchor's offset, and is reported with its
    source by the grid."""

    def test_a_station_cell_lands_and_the_grid_says_so(self, client, story, temp_db):
        cid = story["chat_id"]
        _lay_out(temp_db, cid)
        r = client.put(f"/api/chats/{cid}/bodies/Alice/station",
                       json={"at": None, "near": [], "cell": [5, 2]})
        assert r.status_code == 200, r.text
        assert r.json()["station"] == {"at": None, "near": [], "cell": [5, 2]}
        assert _scene(temp_db, cid)["stations"]["Alice"] == {"at": None, "near": [], "cell": [5, 2]}
        alice = client.get(f"/api/chats/{cid}/rooms/kitchen/grid").json()["bodies"]["Alice"]
        assert alice["cell"] == [5, 2] and alice["measured"] is True
        assert alice["source"] == "cell" and alice["at"] is None
        # `at` and `cell` together: the anchor for prose, the cell for geometry.
        r = client.put(f"/api/chats/{cid}/bodies/Alice/station",
                       json={"at": "hearth", "near": [], "cell": [5, 2]})
        assert r.status_code == 200, r.text
        alice = client.get(f"/api/chats/{cid}/rooms/kitchen/grid").json()["bodies"]["Alice"]
        assert alice == {**alice, "cell": [5, 2], "at": "hearth", "source": "cell"}

    def test_the_grid_reports_an_anchor_derived_cell_and_none(self, client, story, temp_db):
        cid = story["chat_id"]
        _lay_out(temp_db, cid)
        view = client.get(f"/api/chats/{cid}/rooms/kitchen/grid").json()
        assert view["bodies"]["Alice"]["source"] == "anchor"        # at the hearth
        view = client.get(f"/api/chats/{cid}/rooms/hallway/grid").json()
        assert view["bodies"]["Bob"]["source"] == "none"

    def test_a_cell_outside_the_room_is_refused_naming_the_bounds(
            self, client, story, temp_db):
        cid = story["chat_id"]
        _lay_out(temp_db, cid)                                          # 8 by 4
        for cell in ([8, 0], [0, 4], [-1, 0], [3, 9]):
            r = client.put(f"/api/chats/{cid}/bodies/Alice/station",
                           json={"at": None, "near": [], "cell": cell})
            assert r.status_code == 400, cell
            assert "8 by 4" in r.json()["detail"] and "0..7" in r.json()["detail"]
        for junk in ("3,2", [3], [1.5, 2], True, {"x": 3}):
            r = client.put(f"/api/chats/{cid}/bodies/Alice/station",
                           json={"at": None, "near": [], "cell": junk})
            assert r.status_code == 400, junk
            assert "[x, y]" in r.json()["detail"]
        # Nothing landed.
        assert "cell" not in _scene(temp_db, cid)["stations"]["Alice"]

    def test_a_cell_off_the_shape_is_refused_too(self, client, story, temp_db):
        """An L's notch is in the box and not in the room."""
        cid = story["chat_id"]
        _lay_out(temp_db, cid, shape="l",
                 parts=[{"w": 8, "d": 2, "at": "nw"}, {"w": 2, "d": 4, "at": "ne"}])
        r = client.put(f"/api/chats/{cid}/bodies/Alice/station",
                       json={"at": None, "near": [], "cell": [0, 3]})
        assert r.status_code == 400
        assert "shape keeps" in r.json()["detail"]
        r = client.put(f"/api/chats/{cid}/bodies/Alice/station",
                       json={"at": None, "near": [], "cell": [7, 3]})
        assert r.status_code == 200, r.text

    def test_null_or_absent_clears_the_cell_and_cover_rides_through(
            self, client, story, temp_db):
        cid = story["chat_id"]
        _lay_out(temp_db, cid)
        scene = _scene(temp_db, cid)
        scene["stations"]["Alice"] = {"at": "hearth", "near": [], "cell": [5, 2], "cover": True}
        temp_db.wset(cid, "scene", scene)
        r = client.put(f"/api/chats/{cid}/bodies/Alice/station",
                       json={"at": "hearth", "near": [], "cell": None})
        assert r.status_code == 200, r.text
        assert _scene(temp_db, cid)["stations"]["Alice"] == {"at": "hearth", "near": [],
                                                              "cover": True}
        client.put(f"/api/chats/{cid}/bodies/Alice/station",
                   json={"at": "hearth", "near": [], "cell": [5, 2]})
        r = client.put(f"/api/chats/{cid}/bodies/Alice/station",
                       json={"at": "hearth", "near": []})
        assert r.status_code == 200, r.text
        assert "cell" not in _scene(temp_db, cid)["stations"]["Alice"]

    def test_the_player_is_pinned_within_her_room_like_the_cast(
            self, client, story, temp_db):
        cid = story["chat_id"]
        r = client.put(f"/api/chats/{cid}/bodies/Nathan/station",
                       json={"at": None, "near": [], "cell": [1, 1]})
        assert r.status_code == 200, r.text
        assert _scene(temp_db, cid)["stations"]["Nathan"]["cell"] == [1, 1]
        view = client.get(f"/api/chats/{cid}/rooms/study/grid").json()
        assert view["bodies"]["Nathan"] == {**view["bodies"]["Nathan"], "cell": [1, 1],
                                            "kind": "player", "source": "cell"}

    def test_a_body_moved_between_rooms_loses_its_cell(self, client, story, temp_db):
        """The cast editor's position route drops the pin: a cell is in the
        old room's coordinates. The map re-pins in the new room afterwards
        with its own station PUT, as `moveBody` chains them."""
        cid = story["chat_id"]
        _lay_out(temp_db, cid)
        client.put(f"/api/chats/{cid}/bodies/Alice/station",
                   json={"at": None, "near": [], "cell": [5, 2]})
        r = client.put(f"/api/chats/{cid}/characters/{story['Alice']}/position",
                       json={"room": "hallway"})
        assert r.status_code == 200, r.text
        station = _scene(temp_db, cid)["stations"]["Alice"]
        assert "cell" not in station
        assert client.get(f"/api/chats/{cid}/rooms/hallway/grid").json()["bodies"]["Alice"]["cell"] is None
        # The same room again is not a move.
        client.put(f"/api/chats/{cid}/bodies/Alice/station",
                   json={"at": None, "near": [], "cell": [2, 2]})
        client.put(f"/api/chats/{cid}/characters/{story['Alice']}/position",
                   json={"room": "hallway"})
        assert _scene(temp_db, cid)["stations"]["Alice"]["cell"] == [2, 2]

    def test_an_anchor_cell_lands_clears_and_is_exclusive_with_offset(
            self, client, story, temp_db):
        cid = story["chat_id"]
        _lay_out(temp_db, cid)
        grid_of = lambda: client.get(f"/api/chats/{cid}/rooms/kitchen/grid").json()
        seeded = grid_of()["anchors"]["oak_table"]["cells"]
        assert grid_of()["anchors"]["oak_table"]["source"] == "seed"
        anchors = {"hearth": {"desc": "the hearth", "dir": "w", "height": "waist"},
                   "oak_table": {"desc": "the oak table", "footprint": "large",
                                 "height": "waist", "cell": [4, 1]}}
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen", json={"anchors": anchors})
        assert r.status_code == 200, r.text
        stored = _scene(temp_db, cid)["rooms"]["kitchen"]["anchors"]["oak_table"]
        assert stored["cell"] == [4, 1] and "offset" not in stored
        table = grid_of()["anchors"]["oak_table"]
        # A large footprint laid from its origin: 2 by 2, east and south.
        assert table["cells"] == [[4, 1], [4, 2], [5, 1], [5, 2]]
        assert table["source"] == "cell" and table["cell"] == [4, 1]
        # A cell and an offset together: the cell wins and the offset is not kept.
        anchors["hearth"] = {**anchors["hearth"], "offset": 0.5, "cell": [2, 2]}
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen", json={"anchors": anchors})
        assert r.status_code == 200, r.text
        hearth = _scene(temp_db, cid)["rooms"]["kitchen"]["anchors"]["hearth"]
        assert hearth["cell"] == [2, 2] and "offset" not in hearth
        assert hearth["dir"] == "w"                       # the wall stays, for prose
        view = grid_of()["anchors"]["hearth"]
        assert view["cells"] == [[2, 2]] and view["source"] == "cell" and view["dir"] == "w"
        # An offset with the cell cleared: placed along the wall again.
        anchors["hearth"] = {"desc": "the hearth", "dir": "w", "height": "waist",
                             "offset": 0.0, "cell": None}
        r = client.patch(f"/api/chats/{cid}/rooms/kitchen", json={"anchors": anchors})
        assert r.status_code == 200, r.text
        hearth = _scene(temp_db, cid)["rooms"]["kitchen"]["anchors"]["hearth"]
        assert "cell" not in hearth and hearth["offset"] == 0.0
        assert grid_of()["anchors"]["hearth"]["source"] == "offset"
        # Clearing the table's cell returns it to the seed, byte for byte.
        anchors["oak_table"] = {"desc": "the oak table", "footprint": "large",
                                "height": "waist", "cell": None}
        client.patch(f"/api/chats/{cid}/rooms/kitchen", json={"anchors": anchors})
        assert grid_of()["anchors"]["oak_table"]["cells"] == seeded
        assert grid_of()["anchors"]["oak_table"]["source"] == "seed"

    def test_an_anchor_cell_outside_the_room_is_refused_naming_the_bounds(
            self, client, story, temp_db):
        cid = story["chat_id"]
        _lay_out(temp_db, cid)
        for cell in ([8, 1], [2, 4], "2,2", [2]):
            r = client.patch(f"/api/chats/{cid}/rooms/kitchen", json={"anchors": {
                "hearth": {"desc": "the hearth", "dir": "w", "cell": cell}}})
            assert r.status_code == 400, cell
            assert "hearth" in r.json()["detail"]
        assert "cell" not in _scene(temp_db, cid)["rooms"]["kitchen"]["anchors"]["hearth"]
