"""Charter bodies walk the town graph, and a promoted body inherits it.

PROTOTYPE, on a branch. The design under test (`world/charter_move.py`'s
header): a charter body carries the courier's shape between windows -- a
route computed once over the shared pathfinder, a leg, `place` always the
current leg's room -- a window buys `WALK_ROOMS_PER_HOUR` rooms per hour, a
shut door holds a body where it stands, every edge walked is recorded in
room-id vocabulary, and `charter_promote.inherited_place_graph` hands a
promoted townsperson the town's public rooms plus its own walked routes in
`chat_chars.state.place_graph`'s shape.

The BASELINE these tests were written against (measured on `small_town`
before the change, 48 simulated hours at 4-hour windows, seed 3): every
charter place was a room id and `charter["scene"]` was set, so the existing
code took its scene branch -- posted bodies relocated over `travel_rooms`
(the smith crossed six rooms in the window he left home), errands fired at
the default rate, `travelled` counted real distance (folk_4: 18 rooms), and
`REACH_LIMIT` (8) never bound on a map whose longest walk is 7. What the
baseline could not do is the subject of this file: no body was ever between
two rooms, no door could hold one, and nothing recorded which rooms the 18
were.
"""

from __future__ import annotations

import copy
import json
import time

import pytest

from charter_worlds import small_town
from world.charter import (
    WALK_ROOMS_PER_HOUR, en_route, normalize_charter, run, seed_needs,
    seed_roster, walked_edges)
from world.charter_promote import (
    PLACE_GRAPH_INHERIT_CAP, inherited_place_graph, private_rooms)


def _town(**over):
    charter = normalize_charter(dict(small_town(), **over))
    charter["roster"] = seed_roster(charter["bodies"])
    charter["needs"] = seed_needs(charter["bodies"])
    return charter


def _lock(scene, a, b):
    scene = copy.deepcopy(scene)
    for x, y in ((a, b), (b, a)):
        for edge in scene["rooms"][x]["adjacent"]:
            if edge["to"] == y:
                edge["barrier"] = "locked_door"
    return scene


# ---------------------------------------------------------------- baseline

class TestTheBaselineStillHolds:
    """What the existing code did on a charter WITH a graph keeps doing it:
    the prototype changes how a body gets there, not where it goes."""

    def test_posted_bodies_arrive_and_errands_fire(self):
        after, _events = run(_town(), hours=48.0, window=4.0, seed=3)
        places = {k: b["place"] for k, b in after["bodies"].items()}
        assert places["smith"] == "smithy"
        assert places["stallholder"] == "market"
        assert places["tapster"] == "tavern"
        # Off-duty folk circulated: somebody is not at their berth, or has
        # a travelled count that says they went out and came back.
        assert any(after["travelled"].get(f"folk_{i}") for i in range(5))

    def test_travelled_counts_the_rooms_actually_crossed(self):
        after, _ = run(_town(), hours=4.0, window=4.0, seed=3)
        # house_a -> north_2 -> north_1 -> north_0 -> square -> south_0 ->
        # smithy is six edges, and six is what the odometer says.
        assert after["travelled"]["smith"] == 6
        assert sum(n for _a, _b, n in walked_edges(after["walked"],
                                                   "smith")) == 6


# --------------------------------------------------------------- traversal

class TestABodyWalksTheRoute:
    def test_the_pace_is_the_couriers(self):
        """One fact, two spellings: `story.couriers.PACES["walking"]` seconds
        per edge, and rooms per hour here. Pinned rather than imported
        because `world/` does not import `story/`."""
        from story.couriers import PACES
        assert WALK_ROOMS_PER_HOUR == 3600.0 / PACES["walking"]

    def test_a_long_walk_is_caught_in_the_street(self):
        """The tapster lives seven rooms from the tavern. A one-hour window
        buys six, so the window ends with the body in the last street
        before the door -- at a position, not an ETA -- and the next window
        finishes the walk."""
        after, _ = run(_town(), hours=1.0, window=1.0, seed=3)
        tapster = after["bodies"]["tapster"]
        assert en_route(tapster)
        assert tapster["place"] == "north_1"
        assert tapster["walk"]["route"][-1] == "tavern"
        assert tapster["walk"]["leg"] == 6
        later, _ = run(after, hours=1.0, window=1.0, seed=4)
        assert later["bodies"]["tapster"]["place"] == "tavern"
        assert not en_route(later["bodies"]["tapster"])
        assert "walk" not in later["bodies"]["tapster"]

    def test_a_body_is_in_every_room_it_passed(self):
        """No holes: the walked record is the route, edge for edge, and the
        odometer agrees with it."""
        after, _ = run(_town(), hours=4.0, window=4.0, seed=3)
        route = ["house_b_back", "house_b", "south_1", "south_0", "square",
                 "north_0", "north_1", "tavern"]
        assert walked_edges(after["walked"], "tapster") == [
            (a, b, 1) for a, b in sorted(zip(route, route[1:]))]
        assert after["travelled"]["tapster"] == len(route) - 1

    def test_a_shut_door_holds_the_body_where_it_stands(self):
        """Dispatched with the door open, then the door locks. The body is
        held in the last street, says so, and is NOT re-routed -- there is
        no other way to the tavern on this map, and if there were, finding
        it would be the second pathfinder the crowd proposal forbids."""
        after, _ = run(_town(), hours=1.0, window=1.0, seed=3)
        assert after["bodies"]["tapster"]["place"] == "north_1"
        after["scene"] = _lock(after["scene"], "north_1", "tavern")
        held, _ = run(after, hours=8.0, window=4.0, seed=5)
        tapster = held["bodies"]["tapster"]
        assert tapster["place"] == "north_1"
        assert tapster["walk"]["held"] is True
        assert tapster["walk"]["route"][-1] == "tavern"
        # And a held body banks at most one edge of credit, so the day the
        # door opens it walks a window's worth, not a week's.
        assert tapster["walk"]["credit"] <= 4.0 * WALK_ROOMS_PER_HOUR + 1.0

    def test_a_body_in_transit_counts_where_it_stands(self):
        """The crowd rule, stated in `charter_move`'s header: no in-transit
        limbo. `members_of` reads `place`, and `place` is the current leg."""
        from world.charter_crowd import members_of
        after, _ = run(_town(), hours=1.0, window=1.0, seed=3)
        assert "tapster" in members_of(after, "north_1")
        assert "tapster" not in members_of(after, "tavern")
        assert "tapster" not in members_of(after, "house_b_back")

    def test_the_walk_survives_normalization(self):
        """A charter is one restorable object: a body mid-route round-trips
        through `normalize_charter` (a checkpoint, an archive) with its
        route, its leg and its credit, and a record that no longer matches
        the body's place is dropped rather than walked from the wrong room."""
        after, _ = run(_town(), hours=1.0, window=1.0, seed=3)
        again = normalize_charter(json.loads(json.dumps(after)))
        assert again["bodies"]["tapster"]["walk"] == \
            after["bodies"]["tapster"]["walk"]
        assert again["walked"] == after["walked"]
        broken = json.loads(json.dumps(after))
        broken["bodies"]["tapster"]["place"] = "square"
        assert "walk" not in normalize_charter(broken)["bodies"]["tapster"]

    def test_a_bound_body_is_not_walked(self):
        """Promotion delegates motion to the registered character; a bound
        body's route is over and Charter does not advance it."""
        charter = _town()
        charter["bindings"] = {"tapster": {"char_id": 7, "name": "Tam"}}
        after, _ = run(charter, hours=8.0, window=4.0, seed=3)
        assert after["bodies"]["tapster"]["place"] == "house_b_back"
        assert "tapster" not in after["walked"]


# ------------------------------------------------------------- inheritance

class TestAPromotedBodyInheritsTheTown:
    def test_the_cap_is_the_walkers_cap(self):
        from persist.commit import PLACE_GRAPH_NODE_CAP
        assert PLACE_GRAPH_INHERIT_CAP == PLACE_GRAPH_NODE_CAP

    def test_private_is_somebody_elses_home(self):
        charter = _town()
        # The tapster berths in the back room of house_b; house_b itself is
        # the stallholder's and two folk's, house_a the smith's.
        assert private_rooms(charter, "tapster") == {"house_a", "house_b"}
        # Somebody who shares house_b knows house_b.
        assert private_rooms(charter, "stallholder") == {"house_a",
                                                         "house_b_back"}

    def test_public_rooms_are_told_and_walked_rooms_are_walked(self):
        after, _ = run(_town(), hours=48.0, window=4.0, seed=3)
        graph = inherited_place_graph(after, "tapster", turn_idx=12)
        nodes = graph["nodes"]
        # Every street and workplace: the town's, by living in it.
        for rid in ("square", "market", "smithy", "north_0", "north_2",
                    "south_0"):
            assert rid in nodes, rid
        assert nodes["market"]["basis"] == "told"
        assert nodes["market"]["visits"] == 0
        # The route to work, walked: through the stallholder's front room.
        assert nodes["house_b"]["basis"] == "walked"
        assert nodes["tavern"]["basis"] == "walked"
        assert nodes["tavern"]["visits"] >= 1
        # The smith's house is nobody's business of the tapster's.
        assert "house_a" not in nodes
        # Edges: told between public rooms, walked where the body went.
        assert graph["edges"]["north_1"]["tavern"]["taken"] is True
        assert graph["edges"]["north_1"]["north_2"]["basis"] == "told"
        assert "house_a" not in graph["edges"].get("north_2", {})
        # Stamped at the promotion turn, so eviction forgets the never-
        # walked before the walked.
        assert all(n["last_turn"] == 12 and n["first_turn"] == 12
                   for n in nodes.values())

    def test_a_charter_without_a_graph_hands_over_nothing(self):
        charter = _town()
        charter["scene"] = None
        assert inherited_place_graph(charter, "tapster") == {
            "nodes": {}, "edges": {}}

    def test_the_cap_keeps_walked_rooms_first(self):
        after, _ = run(_town(), hours=48.0, window=4.0, seed=3)
        graph = inherited_place_graph(after, "tapster", turn_idx=12, cap=4)
        assert len(graph["nodes"]) == 4
        assert all(n["basis"] == "walked" for n in graph["nodes"].values())
        assert all(b in graph["nodes"]
                   for side in graph["edges"].values() for b in side)

    def test_the_inherited_graph_is_the_one_the_walker_keeps_writing(self):
        """`update_place_graph` folds a real beat into the inherited graph
        without complaint: told nodes stay, a walked-through room gains a
        visit, and the standing room's doorways are confirmed."""
        from persist.commit import update_place_graph
        after, _ = run(_town(), hours=48.0, window=4.0, seed=3)
        graph = inherited_place_graph(after, "tapster", turn_idx=12)
        scene = after["scene"]
        folded = update_place_graph(graph, scene, "square", 13,
                                    came_from="north_0")
        assert folded["nodes"]["square"]["visits"] >= 2
        assert folded["nodes"]["market"]["basis"] == "told"
        assert folded["edges"]["north_0"]["square"]["taken"] is True
        assert folded["edges"]["square"]["market"]["last_confirmed"] == 13

    def test_promotion_writes_the_graph_onto_the_character(self, temp_db,
                                                           monkeypatch):
        """End to end through `promote_background_character`: the town's
        graph and the body's walked routes land on `chat_chars.state.
        place_graph`, the position is the body's real room, and the charter
        binds the body as before."""
        from persist.commit import promote_background_character
        from world.charter_runtime import registry_for, save_registry

        cid = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Small town", "", time.time()))
        after, _ = run(_town(), hours=48.0, window=4.0, seed=3)
        after["bodies"]["tapster"]["name"] = "Tam"
        save_registry(cid, {"small_town": after})
        temp_db.wset(cid, "scene", {
            "rooms": copy.deepcopy(after["scene"]["rooms"]),
            "positions": {}, "entities": {}, "attire": {},
        })
        temp_db.wset(cid, "background_presences", {
            "Tam": {"first_turn": 1, "last_turn": 4,
                    "dialogue_turns": [1, 2, 4], "mention_turns": [],
                    "nature": "person",
                    "charter_refs": [{"charter": "small_town",
                                      "body": "tapster"}]},
        })
        monkeypatch.setattr(
            "persist.commit_background.add_memories_batch",
            lambda rows: [])

        char_id = promote_background_character(
            cid, "Tam", sheet={"identity": {"name": "Tam"}},
            memory_seeds=[], promoted_turn=5)

        state = json.loads(temp_db.q(
            "SELECT state FROM chat_chars WHERE chat_id=? AND char_id=?",
            (cid, char_id), one=True)["state"])
        graph = state["place_graph"]
        assert graph["nodes"]["tavern"]["basis"] == "walked"
        assert graph["nodes"]["market"]["basis"] == "told"
        assert "house_a" not in graph["nodes"]
        assert all(n["first_turn"] == 5 for n in graph["nodes"].values())
        assert temp_db.wget(cid, "scene")["positions"]["Tam"] == "tavern"
        charter = registry_for(cid)["items"]["small_town"]["state"]
        assert charter["bindings"]["tapster"]["char_id"] == char_id


# ------------------------------------------------------------- reverse sync

def test_the_bound_body_sync_says_when_the_namespaces_disagree(temp_db,
                                                              caplog):
    """The one line that writes a scene room id into a charter `place` used
    to sit in a bare `except: pass`. With bodies walking the room graph it
    is load-bearing, so a bound body standing in a room the charter's graph
    does not contain is logged and its place left alone -- not written for
    the mover to fail on next window."""
    import logging
    from world.charter_runtime import advance_snapshot, normalize_registry

    charter = _town()
    charter["bindings"] = {"tapster": {"char_id": 7, "name": "Tam"}}
    registry = normalize_registry({"items": {"small_town": {
        "state": charter, "window_hours": 4.0,
        "last_elapsed_seconds": 0.0, "last_epoch_id": "e0"}}})
    scene = {"rooms": copy.deepcopy(charter["scene"]["rooms"]),
             "positions": {"Tam": "elsewhere"}}
    scene["rooms"]["elsewhere"] = {"name": "elsewhere", "adjacent": []}
    with caplog.at_level(logging.WARNING):
        advanced, _rows, _events = advance_snapshot(
            registry, elapsed_seconds=4 * 3600.0, epoch_id="e1",
            base_turn=1, cid=1, frame_id=None, scene=scene)
    body = advanced["items"]["small_town"]["state"]["bodies"]["tapster"]
    # The composed charter scene is the live scene here, so `elsewhere` IS
    # in the graph and the sync writes it; the disagreement case is the one
    # where the charter keeps its own structure. Pin the write and the
    # absence of a swallowed failure on this path, then the other below.
    assert body["place"] == "elsewhere"
    assert "walk" not in body

    stale = {"rooms": {"bridge": {"name": "Bridge", "adjacent": []}},
             "positions": {"Tam": "bridge"}}
    charter2 = _town()
    charter2["bindings"] = {"tapster": {"char_id": 7, "name": "Tam"}}
    charter2["structure"] = "planned"
    registry2 = normalize_registry({"items": {"small_town": {
        "state": charter2, "window_hours": 4.0,
        "last_elapsed_seconds": 0.0, "last_epoch_id": "e0"}}})
    monkey_rooms = copy.deepcopy(charter2["scene"]["rooms"])
    import world.structure as structure
    original_skeleton = structure.skeleton_rooms
    original_composed = structure.composed_scene
    structure.skeleton_rooms = lambda *a, **k: {"rooms": monkey_rooms}
    structure.composed_scene = lambda skeleton, live: {"rooms": monkey_rooms}
    try:
        with caplog.at_level(logging.WARNING):
            advanced2, _r, _e = advance_snapshot(
                registry2, elapsed_seconds=4 * 3600.0, epoch_id="e1",
                base_turn=1, cid=1, frame_id=None, scene=stale)
    finally:
        structure.skeleton_rooms = original_skeleton
        structure.composed_scene = original_composed
    body2 = advanced2["items"]["small_town"]["state"]["bodies"]["tapster"]
    assert body2["place"] == "house_b_back"
    assert any("does not contain" in rec.getMessage()
               for rec in caplog.records)
