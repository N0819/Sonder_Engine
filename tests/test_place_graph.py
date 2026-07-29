"""What walking a place earns a character durably -- and what it must not.

Two real failures drove this. First, the maze runs sit at 59-60 beats against
VISITED_ROOMS_CAP=60, and `known_exits` used to be pruned to rooms still
inside that window: knowledge of the first rooms of a long walk was silently
deleted at exactly the moment it became useful. Worse than deleted -- the
frontier test read a room with no recorded exits as "never stood there,
everything past it is potentially new", so forgetting made stale ground look
PROMISING. Second, at the start of every repeat run the verdicts fell mute:
every neighbouring exit `known`, none untried, none proven, and the character
thrashed (north, back, north, back). Local history cannot answer "which known
exit leads TOWARD ground I have not explored"; the durable place graph can,
and the answer rides the verdict string and the ordering only.

Everything asserted here is the character's OWN walked route and OWN sight,
so none of it crosses an information boundary -- and one test exists solely
to prove the graph never quietly becomes the objective map.
"""

from __future__ import annotations

from agents.character import _annotate_known_exits
from commit import (PLACE_GRAPH_NODE_CAP, VISITED_ROOMS_CAP,
                    record_spatial_experience, update_place_graph)
from spatial import visible_adjacent_rooms


def _edge(to, dir=None, barrier="open"):
    e = {"to": to, "barrier": barrier}
    if dir:
        e["dir"] = dir
    return e


def _room(name, adjacent=()):
    return {"name": name, "light": "lit", "desc": f"{name}.",
            "adjacent": [dict(e) for e in adjacent]}


def _scene(rooms):
    return {"rooms": rooms, "positions": {}, "entities": {}, "attire": {},
            "overlays": {}}


class TestSightIsNotAMap:
    """The tempting implementation bug, written down so it stays impossible.

    Standing in a room, you see INTO the chamber next door: its name, and
    whether it visibly has another way out. You do not see that chamber's own
    doorways as routes -- `_onward_exits` returns counts and bearings, never
    destinations, precisely so the second representation cannot expand the
    information budget. An implementation that "fixes" that by reading
    scene["rooms"][neighbour]["adjacent"] hands the character the objective
    map one ring at a time.
    """

    def _corridor(self):
        return _scene({
            "here": _room("Here", [_edge("mid", "e")]),
            "mid": _room("Mid", [_edge("here", "w"), _edge("far", "e")]),
            "far": _room("Far", [_edge("mid", "w")]),
        })

    def test_a_room_seen_through_a_doorway_contributes_no_edges_of_its_own(self):
        sc = self._corridor()
        vis = visible_adjacent_rooms(sc, "here")
        graph = update_place_graph(None, sc, "here", 5, visible=vis)
        assert graph["nodes"]["mid"]["basis"] == "seen"
        assert "far" not in graph["nodes"], (
            "a room never stood in or seen must not exist in the graph")
        assert set(graph["edges"]) == {"here"}, (
            "only the room stood in may author edges")
        assert set(graph["edges"]["here"]) == {"mid"}
        flat = {b for side in graph["edges"].values() for b in side}
        assert "far" not in flat, (
            "the neighbour's own doorway leaked into the remembered map")

    def test_standing_there_is_what_earns_the_edges(self):
        """The same room, actually walked into, legitimately yields them."""
        sc = self._corridor()
        graph = update_place_graph(None, sc, "here", 5,
                                   visible=visible_adjacent_rooms(sc, "here"))
        graph = update_place_graph(graph, sc, "mid", 6, came_from="here",
                                   visible=visible_adjacent_rooms(sc, "mid"))
        assert graph["nodes"]["mid"]["basis"] == "walked"
        assert set(graph["edges"]["mid"]) == {"here", "far"}
        assert graph["edges"]["here"]["mid"]["taken"] is True

    def test_a_wall_is_visible_adjacency_but_never_a_doorway(self):
        sc = _scene({
            "here": _room("Here", [_edge("mid", "e"),
                                   _edge("sealed", "n", barrier="wall")]),
            "mid": _room("Mid", [_edge("here", "w")]),
            "sealed": _room("Sealed"),
        })
        graph = update_place_graph(None, sc, "here", 1)
        assert "sealed" not in graph["edges"]["here"]


class TestForgottenGroundIsNotPromising:
    """`known_exits` was pruned to the visited_rooms window, and a room with
    no recorded exits read as "never stood there -- everything past it is
    potentially new". On runs that sit exactly on the 60-beat cap, the ground
    a character had exhausted first was exactly the ground the frontier test
    started recommending again. Walkedness must come from durable memory, not
    the recency window."""

    SCENE = _scene({
        "rHere": _room("Hall", [_edge("rOld1", "w")]),
        "rOld1": _room("Old One", [_edge("rHere", "e"), _edge("rOld2", "w")]),
        "rOld2": _room("Old Two", [_edge("rOld1", "e")]),
    })
    DIGEST = {"ahead": [{"room": "Old One", "barrier": "open"}]}
    KNOWN = {"rHere": ["rOld1"], "rOld1": ["rHere", "rOld2"],
             "rOld2": ["rOld1"]}

    def test_a_room_off_the_window_is_still_been_there(self):
        out = _annotate_known_exits(self.DIGEST, self.SCENE, ["rHere"],
                                    known_exits=self.KNOWN, here_rid="rHere")
        entry = out["ahead"][0]
        assert entry["been_there"] is True
        assert "untried" not in entry, (
            "forgetting the walk must not re-mint the door as discovery")

    def test_an_exhausted_branch_stays_exhausted_after_the_window_rolls(self):
        """The defect was stale ground reading as PROMISING. In this fixture
        the whole known world is walked, so exhaustion is now stated as the
        frame-level completeness fact plus a plain `known` -- never as
        frontier, and no longer as a `spent` that would brand every exit of
        a fully-known place as failure (see TestAFullyKnownMapSaysSo in
        test_spatial_affordances)."""
        out = _annotate_known_exits(self.DIGEST, self.SCENE, ["rHere"],
                                    known_exits=self.KNOWN, here_rid="rHere")
        verdict = out["ahead"][0]["verdict"]
        assert verdict.startswith("known")
        assert "door you have never taken" not in verdict
        assert out.get("ground_fully_known") is True

    def test_mid_run_an_exhausted_branch_still_reads_spent(self):
        """With genuine frontier elsewhere, `spent` keeps its comparative
        meaning: THIS branch has nothing new while some branch does."""
        scene = _scene({
            "rHere": _room("Hall", [_edge("rOld1", "w"), _edge("rNew", "e")]),
            "rOld1": _room("Old One", [_edge("rHere", "e"),
                                       _edge("rOld2", "w")]),
            "rOld2": _room("Old Two", [_edge("rOld1", "e")]),
            "rNew": _room("New", [_edge("rHere", "w")]),
        })
        known = {"rHere": ["rOld1", "rNew"], "rOld1": ["rHere", "rOld2"],
                 "rOld2": ["rOld1"]}
        out = _annotate_known_exits(self.DIGEST, scene, ["rHere"],
                                    known_exits=known, here_rid="rHere")
        assert out["ahead"][0]["verdict"].startswith("spent")
        assert "ground_fully_known" not in out

    def test_the_window_counters_are_simply_absent_not_invented(self):
        """Absent means cannot tell -- the ordinal/recency numbers belong to
        the window and must not be fabricated for ground outside it."""
        out = _annotate_known_exits(self.DIGEST, self.SCENE, ["rHere"],
                                    known_exits=self.KNOWN, here_rid="rHere")
        entry = out["ahead"][0]
        assert "times_entered" not in entry
        assert "last_seen_beats_ago" not in entry


class TestFrontierDirection:
    """The repeat-run open problem: every neighbouring exit `known`, and the
    verdicts had nothing left to say, so the character thrashed between two
    equally-marked doors. "Which known exit leads TOWARD ground I have not
    explored" is a fact about the character's own remembered ground, and the
    engine can compute it, so it says it."""

    SCENE = _scene({
        "rHere": _room("Hall", [_edge("rA", "n"), _edge("rD", "s")]),
        "rA": _room("A", [_edge("rHere", "s"), _edge("rB", "n")]),
        "rB": _room("B", [_edge("rA", "s"), _edge("rC", "n")]),
        "rC": _room("C", [_edge("rB", "s"), _edge("rX", "n")]),
        "rD": _room("D", [_edge("rHere", "n"), _edge("rY", "s")]),
        "rX": _room("X"), "rY": _room("Y"),
    })
    KNOWN = {"rHere": ["rA", "rD"], "rA": ["rHere", "rB"],
             "rB": ["rA", "rC"], "rC": ["rB", "rX"], "rD": ["rHere", "rY"]}
    DIGEST = {"ahead": [{"room": "A", "barrier": "open"},
                        {"room": "D", "barrier": "open"}]}

    def _exits(self):
        return _annotate_known_exits(
            self.DIGEST, self.SCENE, ["rHere"],
            known_exits=self.KNOWN, here_rid="rHere")

    def test_nearer_new_ground_comes_first_among_known_exits(self):
        rooms = [e["room"] for e in self._exits()["ahead"]]
        assert rooms == ["D", "A"], (
            "the exit with frontier one room off must outrank the one with "
            "frontier three rooms off -- this tie is the whole thrash")

    def test_the_distance_lives_in_the_verdict_string(self):
        by = {e["room"]: e for e in self._exits()["ahead"]}
        assert by["D"]["verdict"].startswith("known")
        assert "door you have never taken" in by["D"]["verdict"]
        assert "about 3 rooms" in by["A"]["verdict"]

    def test_the_distance_is_not_a_new_per_exit_key(self):
        """The salience inversion (the right door as the lightest entry) was
        fixed once; decorating every exit with hop counts would re-create it
        one key at a time."""
        for entry in self._exits()["ahead"]:
            for key in entry:
                assert "hop" not in key and "frontier" not in key \
                    and "nearest" not in key, f"leaked key: {key}"

    def test_untried_still_outranks_the_nearest_known(self):
        """The gradient breaks ties among known ways; it must not outrank a
        door never taken at all."""
        scene = _scene(dict(
            self.SCENE["rooms"],
            rZ=_room("Z", [_edge("rHere", "e"), _edge("rZZ", "w")]),
            rZZ=_room("ZZ", [_edge("rZ", "e")])))
        scene["rooms"]["rHere"] = _room(
            "Hall", [_edge("rA", "n"), _edge("rD", "s"), _edge("rZ", "w")])
        digest = {"ahead": [{"room": "A", "barrier": "open"},
                            {"room": "D", "barrier": "open"},
                            {"room": "Z", "barrier": "open"}]}
        out = _annotate_known_exits(digest, scene, ["rHere"],
                                    known_exits=self.KNOWN, here_rid="rHere")
        assert [e["room"] for e in out["ahead"]] == ["Z", "D", "A"]

    def test_a_closed_chamber_on_the_graph_node_is_not_frontier(self):
        """A visibly-closed chamber recorded on the node must stop the branch
        exactly as the legacy known_dead_ends list did -- the graph and the
        list must not disagree about what sight already ruled out."""
        graph = {"nodes": {"rX": {"basis": "seen", "closed": True}},
                 "edges": {}}
        out = _annotate_known_exits(
            self.DIGEST, self.SCENE, ["rHere"], known_exits=self.KNOWN,
            here_rid="rHere", place_graph=graph)
        by = {e["room"]: e for e in out["ahead"]}
        assert by["A"]["verdict"].startswith("spent"), (
            "the only door down A's branch is one sight showed closed")
        assert "door you have never taken" in by["D"]["verdict"]


class TestDisprovenDoorways:
    """The one place objective state may correct the graph is the room the
    character is standing in: a remembered doorway of THIS room that present
    perception does not show is disproven. Without retraction the map routes
    through doors the character has stood in front of and seen gone -- and
    the stale legacy known_exits copy must not resurrect the edge."""

    def _before(self):
        return _scene({
            "rHere": _room("Hall", [_edge("rGone", "n")]),
            "rGone": _room("Gone", [_edge("rHere", "s")]),
        })

    def _after(self):
        return _scene({
            "rHere": _room("Hall"),
            "rGone": _room("Gone"),
        })

    def test_a_vanished_doorway_is_disproven_both_ways(self):
        graph = update_place_graph(None, self._before(), "rHere", 1)
        graph = update_place_graph(graph, self._before(), "rGone", 2,
                                   came_from="rHere")
        graph = update_place_graph(graph, self._after(), "rHere", 9)
        assert graph["edges"]["rHere"]["rGone"]["disproven"] == 9
        assert graph["edges"]["rGone"]["rHere"]["disproven"] == 9

    def test_a_disproven_edge_stops_carrying_routes(self):
        """Even when a stale known_exits entry still lists it -- the legacy
        ledger refreshes a room's exits only when the character stands there
        again, so retraction must win the disagreement. Mid is dark so that
        live sight cannot answer the question first."""
        scene = _scene({
            "rHere": _room("Hall", [_edge("rMid", "n")]),
            "rMid": _room("Mid", [_edge("rHere", "s")]),
            "rGone": _room("Gone"),
        })
        scene["rooms"]["rMid"]["light"] = "dark"
        known = {"rHere": ["rMid"], "rMid": ["rHere", "rGone"]}
        digest = {"ahead": [{"room": "Mid", "barrier": "open"}]}
        without = _annotate_known_exits(
            digest, scene, ["rHere"], known_exits=known, here_rid="rHere")
        assert "door you have never taken" in without["ahead"][0]["verdict"], (
            "control: with the stale ledger unretracted the branch reads live")
        graph = {"nodes": {}, "edges": {"rMid": {"rGone": {"disproven": 9}}}}
        out = _annotate_known_exits(
            digest, scene, ["rHere"],
            known_exits=known, here_rid="rHere", place_graph=graph)
        verdict = out["ahead"][0]["verdict"]
        assert "door you have never taken" not in verdict, (
            "retraction must win: the branch may not read live")
        assert verdict.startswith("known"), (
            "with the disproven door retracted nothing anywhere is new, so "
            "the way reads familiar rather than failed -- the completeness "
            "fact below carries the exhaustion")
        assert out.get("ground_fully_known") is True

    def test_a_reappearing_doorway_is_believed_again(self):
        """The correction is perception, so perception can also undo it --
        a door found shut up one week and rebuilt the next."""
        graph = update_place_graph(None, self._before(), "rHere", 1)
        graph = update_place_graph(graph, self._after(), "rHere", 9)
        assert graph["edges"]["rHere"]["rGone"].get("disproven") == 9
        graph = update_place_graph(graph, self._before(), "rHere", 12)
        assert "disproven" not in graph["edges"]["rHere"]["rGone"]


class TestDestroyedPlacesAreStillRemembered:
    """The registry retires rooms; memory must not follow it. A character
    learns a place is gone by standing where it was, not by objective
    destruction reaching into their state -- remembering a place that no
    longer exists is correct belief behaviour, and walking toward it is a
    scene, not a bug."""

    def test_a_room_absent_from_the_scene_keeps_its_nodes_and_edges(self):
        lost = _scene({
            "rLost": _room("Lost Shrine", [_edge("rPath", "n")]),
            "rPath": _room("Path", [_edge("rLost", "s")]),
        })
        graph = update_place_graph(None, lost, "rLost", 1)
        graph = update_place_graph(graph, lost, "rPath", 2, came_from="rLost")
        elsewhere = _scene({"rElse": _room("Elsewhere")})
        graph = update_place_graph(graph, elsewhere, "rElse", 50)
        assert graph["nodes"]["rLost"]["name"] == "Lost Shrine"
        assert "disproven" not in graph["edges"]["rLost"]["rPath"]
        assert "disproven" not in graph["edges"]["rPath"]["rLost"]


class TestWalkedEdges:
    """A walked edge is evidence a doorway exists, so only an actual step may
    mint one. Position changes also happen by teleport, relocation, and being
    carried -- none of which taught the character a route."""

    SCENE = _scene({
        "rHere": _room("Hall", [_edge("rNext", "n")]),
        "rNext": _room("Next", [_edge("rHere", "s")]),
        "rFar": _room("Far Tower"),
    })

    def test_a_teleport_mints_no_walked_edge(self):
        graph = update_place_graph(None, self.SCENE, "rHere", 3,
                                   came_from="rFar")
        assert "rFar" not in graph["edges"], (
            "a gap-cross is not a route the character learned")

    def test_an_honest_step_is_recorded_as_taken(self):
        graph = update_place_graph(None, self.SCENE, "rNext", 3,
                                   came_from="rHere")
        rec = graph["edges"]["rHere"]["rNext"]
        assert rec["taken"] is True
        assert rec["basis"] == "walked"


class TestEviction:
    """The graph is a memory and must stay one: bounded, with the places
    least revisited and longest unseen forgotten first. Unbounded it would
    grow with every campaign forever; evicting by recency-of-standing alone
    would forget a home base visited a hundred times as readily as a corridor
    passed once."""

    def _big_graph(self, n):
        nodes = {f"r{i:04d}": {"basis": "walked", "visits": 1,
                               "first_turn": i, "last_turn": i}
                 for i in range(n)}
        edges = {"r0001": {"r0000": {"basis": "seen", "last_confirmed": 1}},
                 "r0100": {"r0000": {"basis": "seen", "last_confirmed": 1}}}
        return {"nodes": nodes, "edges": edges}

    SCENE = _scene({"rHome": _room("Home")})

    def test_the_oldest_least_visited_are_forgotten_first(self):
        graph = self._big_graph(PLACE_GRAPH_NODE_CAP + 5)
        graph = update_place_graph(graph, self.SCENE, "rHome", 9999)
        assert len(graph["nodes"]) == PLACE_GRAPH_NODE_CAP
        assert "r0000" not in graph["nodes"]
        assert f"r{PLACE_GRAPH_NODE_CAP + 4:04d}" in graph["nodes"]

    def test_the_room_being_stood_in_is_never_evicted(self):
        graph = self._big_graph(PLACE_GRAPH_NODE_CAP + 5)
        graph = update_place_graph(graph, self.SCENE, "rHome", 9999)
        assert "rHome" in graph["nodes"]

    def test_edges_to_the_forgotten_are_dropped_with_them(self):
        graph = self._big_graph(PLACE_GRAPH_NODE_CAP + 5)
        graph = update_place_graph(graph, self.SCENE, "rHome", 9999)
        assert "r0000" not in graph["edges"]
        flat = {b for side in graph["edges"].values() for b in side}
        assert "r0000" not in flat, "a dangling edge to a forgotten place"

    def test_visits_protect_a_place_from_recency_eviction(self):
        # Exactly one slot over the cap once rHome is added, so exactly one
        # node must go -- and at equal staleness, visits decide which.
        graph = self._big_graph(PLACE_GRAPH_NODE_CAP)
        graph["nodes"]["r0000"]["last_turn"] = 0
        graph["nodes"]["r0000"]["visits"] = 100
        graph["nodes"]["r0001"]["last_turn"] = 0
        graph["nodes"]["r0001"]["visits"] = 1
        graph = update_place_graph(graph, self.SCENE, "rHome", 9999)
        assert "r0001" not in graph["nodes"], "the tie-loser goes first"
        assert "r0000" in graph["nodes"], (
            "at equal staleness, the place walked a hundred times outlives "
            "the corridor passed once")


class TestRecordSpatialExperience:
    """The commit-side recorder, end to end over a walk longer than the
    window. The pruning that lived here erased `known_exits` past
    VISITED_ROOMS_CAP; the window itself must survive (the loop detectors
    measure recency with it) while knowledge no longer dies with it."""

    def _chain(self, n):
        rooms = {}
        for i in range(n):
            adj = []
            if i:
                adj.append(_edge(f"r{i - 1:02d}", "s"))
            if i + 1 < n:
                adj.append(_edge(f"r{i + 1:02d}", "n"))
            rooms[f"r{i:02d}"] = _room(f"Room {i}", adj)
        return _scene(rooms)

    def _walk(self, n=70):
        sc = self._chain(n)
        st = {}
        for i in range(n):
            record_spatial_experience(st, sc, f"r{i:02d}", i)
        return st, sc

    def test_the_recency_window_is_still_a_window(self):
        st, _ = self._walk()
        assert len(st["visited_rooms"]) == VISITED_ROOMS_CAP
        assert "r00" not in st["visited_rooms"]

    def test_knowledge_survives_the_window(self):
        st, _ = self._walk()
        assert "r00" in st["known_exits"], (
            "the pruning that erased this is the defect this test pins shut")
        assert st["place_graph"]["nodes"]["r00"]["basis"] == "walked"
        assert st["place_graph"]["edges"]["r00"]["r01"]["taken"] is True

    def test_seventy_beats_in_the_exhausted_chain_reads_exhausted(self):
        """The full defect: standing at the far end of a fully-walked chain,
        the way back must never read as frontier -- before the fix, the
        rooms the window had forgotten made it read as discovery. With the
        WHOLE known world walked the exhaustion is now the frame-level
        completeness fact plus a plain `known`, not a `spent` that brands a
        fully-known place as failure."""
        st, sc = self._walk()
        out = _annotate_known_exits(
            {"behind": [{"room": "Room 68", "barrier": "open"}]}, sc,
            st["visited_rooms"], known_exits=st["known_exits"],
            here_rid="r69", known_dead_ends=st["known_dead_ends"],
            place_graph=st["place_graph"])
        verdict = out["behind"][0]["verdict"]
        assert verdict.startswith("known")
        assert "door you have never taken" not in verdict
        assert out.get("ground_fully_known") is True

    def test_an_idle_beat_neither_walks_nor_revisits(self):
        sc = self._chain(3)
        st = {}
        record_spatial_experience(st, sc, "r00", 1)
        record_spatial_experience(st, sc, "r00", 2)
        assert st["visited_rooms"] == ["r00"]
        assert st["place_graph"]["nodes"]["r00"]["visits"] == 1

    def test_no_room_records_nothing(self):
        st = {"visited_rooms": ["r00"]}
        record_spatial_experience(st, self._chain(2), None, 5)
        assert st == {"visited_rooms": ["r00"]}
