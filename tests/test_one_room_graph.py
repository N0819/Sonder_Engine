"""ONE graph answers "what can the story walk between" (B21, review
2026-09-07).

Three readers of the `story` layer asked that question and three built their
own walk: `room_slice.room_graph` (what the room index counts hops over),
`room_tools`' route graph (what `inspect_route` and the out-of-reach
structure lint walk), and `plot_packages._reach_warning` (what the package
preview warns on). Each rebuilt the same union -- the edges a body could
cross, plus the plan's topology -- and each got the two hard parts
differently:

* A ONE-WAY PASSAGE. `room_graph` honours `passage_from`; the reach check
  joined both ends, so a chute a body can only fall down read as a way back
  up and a package planted at the top of it was called reachable.
* THE INSIDE OF A BODY. `room_graph` joins a room carrying `parent_entity`
  to the room its holder stands in and to nothing else; the reach check left
  it in the graph as an ordinary room, so anything the inside declared an
  edge to read as reachable THROUGH the body.

Both now read `room_graph(cid, scene, extra_edges=)`, whose one parameter is
the only edge a second reader ever held of its own: the adjacency a draft
package's own `plan_rooms` declares.
"""

from __future__ import annotations

import time

from story.plot_packages import draft_operation, new_package, preview_package
from story.room_slice import read_scene, room_graph
from story.room_tools import run_tool

PLAYER = "Wren Ashby"


def _story(db, *, turns=3):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("One graph", "A works at night.", time.time()))
    db.wset(cid, "scene", {"location": "Works", "rooms": {
        "hall": {"name": "Hall", "desc": "Tiled floor.", "adjacent": [
            {"to": "gallery", "barrier": "open_door"}]},
        "gallery": {"name": "Gallery", "desc": "Portraits.", "adjacent": [
            {"to": "hall", "barrier": "open_door"}]},
        # Where the world put a body: the lift car the hall's service lift
        # is, standing in the hall, with a door of its own onto the sublevel.
        "lift_car": {"name": "Lift Car", "desc": "A cage.",
                     "parent_entity": "Service Lift", "adjacent": [
                         {"to": "hall", "barrier": "open"},
                         {"to": "sublevel", "barrier": "open"}]},
        "sublevel": {"name": "Sublevel", "desc": "Pipes.", "adjacent": [
            {"to": "lift_car", "barrier": "open"}]},
        # A one-way drop: crossable only from the shaft head, downward.
        "shaft_head": {"name": "Shaft Head", "desc": "A lip of brick.",
                       "adjacent": [
                           {"to": "hall", "barrier": "open",
                            "passage_from": "shaft_head"},
                           {"to": "attic", "barrier": "open_door"}]},
        "attic": {"name": "Attic", "desc": "Rafters.", "adjacent": [
            {"to": "shaft_head", "barrier": "open_door"}]},
    }, "positions": {PLAYER: "hall", "Service Lift": "hall"},
        "entities": {"Service Lift": {"name": "Service Lift",
                                      "kind": "vehicle"}},
        "attire": {}})
    # A registered cast member, so `_world_snapshot`'s `occupied` has
    # somebody in it -- the reach warning is about the rooms the cast stands
    # in and says nothing when the story stands nowhere.
    char = db.qi("INSERT INTO characters(name,sheet,created) VALUES(?,?,?)",
                 (PLAYER, "{}", time.time()))
    db.qi("INSERT INTO chat_chars(chat_id,char_id) VALUES(?,?)", (cid, char))
    for i in range(turns):
        db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
              "VALUES(?,?,?,?)", (cid, i, "", time.time()))
    return cid


def _arrival_warnings(db, cid, room):
    from world.planned_entities import add_planned_entity

    add_planned_entity(cid, {"kind": "person", "name": "Jem Clough"})
    uid = new_package(cid, title="A Caller At %s" % room)["uid"]
    draft_operation(cid, uid, {"op": "arrival", "who": "Jem Clough",
                               "room": room})
    return preview_package(cid, uid)["warnings"]


class TestOneGraph:
    def test_the_graph_joins_an_inside_to_its_holders_room_and_no_further(
            self, temp_db):
        cid = _story(temp_db)
        graph = room_graph(cid, read_scene(cid))
        assert graph["lift_car"] == {"hall"}
        assert "lift_car" in graph["hall"]
        # The sublevel's own edge is INTO the car, so the story cannot walk
        # to it at all -- and the walk must not offer the car as the way.
        assert graph["sublevel"] == set()

    def test_the_graph_honours_a_one_way_passage(self, temp_db):
        cid = _story(temp_db)
        graph = room_graph(cid, read_scene(cid))
        assert "hall" in graph["shaft_head"]
        assert "shaft_head" not in graph["hall"]


class TestTheReachWarningWalksTheSameGraph:
    """The package preview and `inspect_route` gave opposite answers about
    the same two rooms: the route tool refused both, the reach check called
    both two hops away and stayed silent."""

    def test_a_room_reachable_only_through_the_inside_of_a_body_warns(
            self, temp_db):
        cid = _story(temp_db)
        assert run_tool(cid, "inspect_route", {
            "from_room": "hall", "to_room": "sublevel"})["hops"] is None
        assert any("cannot reach this" in w
                   for w in _arrival_warnings(temp_db, cid, "sublevel"))

    def test_a_room_reachable_only_up_a_one_way_drop_warns(self, temp_db):
        cid = _story(temp_db)
        assert run_tool(cid, "inspect_route", {
            "from_room": "hall", "to_room": "attic"})["hops"] is None
        assert any("cannot reach this" in w
                   for w in _arrival_warnings(temp_db, cid, "attic"))

    def test_a_room_the_story_can_walk_to_does_not_warn(self, temp_db):
        cid = _story(temp_db)
        assert run_tool(cid, "inspect_route", {
            "from_room": "hall", "to_room": "gallery"})["hops"] == 1
        assert not any("cannot reach this" in w
                       for w in _arrival_warnings(temp_db, cid, "gallery"))

    def test_the_packages_own_planted_adjacency_still_counts(self, temp_db):
        """`extra_edges`: the one edge this reader holds that the world does
        not. A room the package plants beside a room the cast can reach is
        reachable, and was before the graphs were merged."""
        cid = _story(temp_db)
        uid = new_package(cid, title="The Steward's Office")["uid"]
        draft_operation(cid, uid, {
            "op": "plan_rooms",
            "structure": {"key": "working_wing", "name": "The Working Wing"},
            "rooms": {"stewards_office": {
                "name": "Steward's Office", "purpose": "accounts",
                "adjacent": [{"to": "gallery"}]}}})
        report = preview_package(cid, uid)
        assert not any("cannot reach this" in w for w in report["warnings"]), \
            report["warnings"]

    def test_a_planted_room_hanging_off_an_inside_does_not_count(self, temp_db):
        """A plan cannot hang a room off the inside of a body -- that room is
        the Director's, minted on the fly and living only while the
        containment does -- so the planted edge joins nothing and the package
        is warned about."""
        cid = _story(temp_db)
        uid = new_package(cid, title="The Cage Annexe")["uid"]
        draft_operation(cid, uid, {
            "op": "plan_rooms",
            "structure": {"key": "annexe", "name": "The Annexe"},
            "rooms": {"cage_annexe": {
                "name": "Cage Annexe", "purpose": "storage",
                "adjacent": [{"to": "lift_car"}]}}})
        report = preview_package(cid, uid)
        assert any("cannot reach this" in w for w in report["warnings"]), \
            report["warnings"]
