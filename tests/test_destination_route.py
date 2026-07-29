"""Routing toward a room the character's own goals name (A12 run 4).

The measured failure this exists to fix: a courier with a re-armed
commission, 46 place-graph nodes, and a COMPLETE optimal 28-room remembered
route from the entrance to the shrine spent five beats standing still --
r0003 entered three times, one northward step into a wall -- because the
affordance layer answers "where have I not been" (frontier, verdicts) and
never "how do I reach the room I already want". His own proven route read
back to him as "spent Chamber 0003", and run 4 tracked SLOWER than run 3,
when nothing in his goal structure wanted the shrine at all. Only a
character who wants a specific known room can hit this gap, which is why
three arms ran before anyone did.

The firewall shape is the sprint_offers knowledge gate again: the route is
computed strictly from the character's own place graph -- doorways his feet
took, minus the disproven -- and never from the scene. If his map is wrong,
the route is wrong in exactly the way his map is wrong, which is the
property the maze-expansion arm needs measurable.

The salience shape is the _annotate_known_exits discipline: the reading
rides the verdict STRING and the ordering, never a key of its own, and the
raw markers stay underneath as the evidence needed to disagree with it.

Database-independent: pure graph and payload-shape contracts.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.character import (_annotate_known_exits, _destination_from_goals,
                              _en_route, _toward_hops)


def _room(name, adjacent=(), light="lit"):
    return {"name": name, "desc": name, "light": light,
            "adjacent": list(adjacent)}


def _e(to, direction):
    return {"to": to, "dir": direction, "barrier": "open"}


def _graph(taken_pairs, nodes):
    edges = {}
    for a, b in taken_pairs:
        edges.setdefault(a, {})[b] = {"taken": True}
    return {"nodes": {r: {"basis": "walked", "name": n}
                      for r, n in nodes.items()},
            "edges": edges}


class TestDestinationFromGoals:
    """The double legitimacy gate: his own text, his own node."""

    def _pg(self):
        return _graph([], {"rD": "Chamber 0603", "rQ": "Chamber 0401"})

    def test_the_goal_outranks_a_stale_intention(self):
        """The exact live shape that settled the scoping: no active
        intention named the wanted room ('the shrine at the far corner' --
        no chamber), the only chamber named by an active intention was a
        stale one at progress 1.0 pointing at Chamber 0401, and his
        self-authored active_state.goal named Chamber 0603 from the first
        pacing beat. Intention-only would have been actively wrong, not
        merely silent."""
        state = {
            "active_state": {"goal": "Enter Chamber 0603 and assess "
                                     "contents while maintaining stride"},
            "interior": {"intentions": [
                {"id": "i1", "status": "active", "progress": 1.0,
                 "intent": "Move east to Chamber 0401, then assess"},
                {"id": "i2", "status": "active", "priority": 0.9,
                 "intent": "Reach the shrine at the far corner."},
            ]},
        }
        dest = _destination_from_goals(state, self._pg())
        assert dest == {"rid": "rD", "name": "Chamber 0603"}

    def test_intentions_answer_when_the_goal_names_nothing(self):
        state = {
            "active_state": {"goal": "Keep moving"},
            "interior": {"intentions": [
                {"id": "i1", "status": "active", "priority": 0.2,
                 "intent": "later, look into Chamber 0401"},
                {"id": "i2", "status": "active", "priority": 0.9,
                 "intent": "get back to Chamber 0603"},
            ]},
        }
        dest = _destination_from_goals(state, self._pg())
        assert dest["rid"] == "rD", "higher-priority intention wins"

    def test_a_room_he_has_no_node_for_is_never_a_destination(self):
        """Wanting a room is not knowing it. A goal naming ground he has
        never walked must produce silence, not a route computed from the
        true scene -- that would hand him unearned map through the back
        door this feature was designed not to open."""
        state = {"active_state": {"goal": "Find Chamber 9999 at any cost"}}
        assert _destination_from_goals(state, self._pg()) is None

    def test_closed_goals_and_closed_intentions_are_ignored(self):
        state = {
            "active_state": {},
            "interior": {"intentions": [
                {"id": "ia1", "status": "abandoned",
                 "intent": "Reach Chamber 0603 fast."},
                {"id": "ia2", "status": "dormant",
                 "intent": "Circle back to Chamber 0401."},
            ]},
        }
        assert _destination_from_goals(state, self._pg()) is None

    def test_the_last_named_room_in_a_text_is_the_destination(self):
        """'From Chamber 0401 head to Chamber 0603' is going TO 0603."""
        state = {"active_state": {
            "goal": "From Chamber 0401 head for Chamber 0603"}}
        dest = _destination_from_goals(state, self._pg())
        assert dest["rid"] == "rD"


class TestTheWaypointDoesNotEatTheDestination:
    """A13 run 4. Characters phrase a goal as the NEXT STEP far more often
    than as the aim, and the aim is frequently not a chamber name at all:
    "Run east to Chamber 0004 to progress toward the shrine". The only room
    NAMED there is the waypoint he is walking into, so the goal text won the
    match and the standing shrine intention was never consulted -- the
    affordance answered "your remembered ground runs from here to Chamber
    0004", a route of length zero, in the most salient slot he has.
    """

    def _pg(self):
        return _graph([], {"rD": "Chamber 0603", "rH": "Chamber 0004"})

    def test_a_route_to_where_he_stands_yields_to_the_next_text(self):
        state = {
            "active_state": {"goal": "Run east to Chamber 0004 to progress "
                                     "toward the shrine"},
            "interior": {"intentions": [
                {"id": "ia4", "status": "active", "priority": 0.98,
                 "intent": "Walk the proved line to the shrine at "
                           "Chamber 0603, clean and fast."},
            ]},
        }
        dest = _destination_from_goals(state, self._pg(), here_rid="rH")
        assert dest == {"rid": "rD", "name": "Chamber 0603"}, (
            "standing in the room his goal names must not silence the "
            "intention that names where he is actually going")

    def test_without_a_position_the_old_reading_is_unchanged(self):
        """here_rid is optional, and absent it nothing may change: every
        caller that does not know where the character stands must still get
        the goal-first answer it got before."""
        state = {"active_state": {"goal": "Run east to Chamber 0004"}}
        assert _destination_from_goals(state, self._pg())["rid"] == "rH"

    def test_it_is_the_room_not_the_wording_that_disqualifies(self):
        """Standing elsewhere, the same goal text resolves as it always
        did -- this gate is about position, not about phrasing."""
        state = {"active_state": {"goal": "Run east to Chamber 0004"}}
        dest = _destination_from_goals(state, self._pg(), here_rid="rD")
        assert dest["rid"] == "rH"


class TestStaleIntentionsDoNotSteer:
    """`status == "active"` is not enough. Intentions are spent by the world
    rather than closed by a decision, so a character carries rows that were
    true fifty beats ago and are merely not yet swept. Harmless for
    motivation, where a dormant row simply loses; harmful here, where naming
    a chamber is the whole qualification.

    Measured in A13 run 4: `i3`, "Explore connectivity from Chamber 0504 via
    western passage", active at progress 0.2 long after that exploration was
    over, routed seventeen beats' worth of salience to Chamber 0504 while
    the character's own goal named the shrine.
    """

    def _pg(self):
        return _graph([], {"rD": "Chamber 0603", "rS": "Chamber 0504"})

    def _state(self, **extra):
        stale = {"id": "i3", "status": "active", "priority": 0.5,
                 "intent": "Explore connectivity from Chamber 0504",
                 "last_progress_turn": 120}
        stale.update(extra)
        return {"active_state": {"goal": "Keep moving"},
                "interior": {"intentions": [
                    stale,
                    {"id": "ia4", "status": "active", "priority": 0.4,
                     "intent": "Walk the proved line to Chamber 0603",
                     "last_progress_turn": 200},
                ]}}

    def test_an_intention_long_past_progress_is_not_a_destination(self):
        dest = _destination_from_goals(self._state(), self._pg(),
                                       now_turn=200)
        assert dest["rid"] == "rD", (
            "a row eighty turns without progress must not outrank a live "
            "one, even at higher priority")

    def test_a_stalled_row_is_dropped_however_recent(self):
        dest = _destination_from_goals(
            self._state(stalled_turn=199, last_progress_turn=199),
            self._pg(), now_turn=200)
        assert dest["rid"] == "rD"

    def test_a_blocked_row_is_dropped(self):
        dest = _destination_from_goals(
            self._state(blocked_turn=199, last_progress_turn=199),
            self._pg(), now_turn=200)
        assert dest["rid"] == "rD"

    def test_a_recent_row_still_steers(self):
        """The gate drops what he has moved on from, not a patient aim."""
        dest = _destination_from_goals(
            self._state(last_progress_turn=190), self._pg(), now_turn=200)
        assert dest["rid"] == "rS", "priority still decides among live rows"

    def test_without_a_turn_nothing_is_aged_out(self):
        assert _destination_from_goals(self._state(), self._pg())["rid"] == "rS"


class TestEnRoute:
    """Being underway is a stated status, not a coincidence that must recur.

    Measured (A14, after the completeness fix): a character 9 rooms from a
    destination he had himself chosen closed to 7 and gave it all back --
    trail 9 9 7 8 9, four beats, net zero. His previous goal text was in
    the payload every beat; what nothing stated was that he was ALREADY
    UNDERWAY, how far in, or that the last beat had closed distance, so a
    nine-room journey needed the same intent to win the beat auction nine
    independent times. Derived at payload time from rows that already
    exist: nothing persists, so every way a journey can end is a change in
    the derivation itself -- arrival empties the destination, renaming the
    aim moves it, a disproven doorway breaks the way into silence.
    """

    #  Gate -- Hall -- Stair -- Landing -- Shrine, every doorway taken.
    def _pg(self):
        return _graph(
            [("rA", "rB"), ("rB", "rC"), ("rC", "rD"), ("rD", "rE")],
            {"rA": "Gate", "rB": "Hall", "rC": "Stair",
             "rD": "Landing", "rE": "Shrine"})

    def _state(self, route, pg=None):
        return {"visited_rooms": route, "place_graph": pg or self._pg()}

    DEST = {"rid": "rE", "name": "Shrine"}

    def test_the_journey_is_stated_with_his_own_distance(self):
        got = _en_route(self._state(["rA", "rB"]), "rB", self.DEST)
        assert got == {"to": "Shrine", "rooms_left": 3,
                       "closer_than_last_room": True}

    def test_giving_ground_reads_as_giving_ground(self):
        """The oscillation fact itself: nine rooms walked and given back is
        not nine rooms walked."""
        got = _en_route(self._state(["rC", "rB"]), "rB", self.DEST)
        assert got["rooms_left"] == 3
        assert got.get("further_than_last_room") is True
        assert "closer_than_last_room" not in got

    def test_holding_distance_states_neither(self):
        """A sidestep neither spends nor buys; absent means nothing to say."""
        pg = _graph(
            [("rA", "rB"), ("rA", "rC"), ("rB", "rD"), ("rC", "rD"),
             ("rD", "rE")],
            {"rA": "Gate", "rB": "West", "rC": "East", "rD": "Join",
             "rE": "Shrine"})
        got = _en_route(self._state(["rC", "rB"], pg), "rB", self.DEST)
        assert got["rooms_left"] == 2
        assert "closer_than_last_room" not in got
        assert "further_than_last_room" not in got

    def test_no_remembered_way_is_silence(self):
        """The firewall: doorways his feet took, never the scene. A node
        merely known to exist earns no journey to it."""
        pg = _graph([("rA", "rB")],
                    {"rA": "Gate", "rB": "Hall", "rE": "Shrine"})
        assert _en_route(self._state(["rA", "rB"], pg), "rB",
                         self.DEST) is None

    def test_a_disproven_doorway_breaks_the_journey_into_silence(self):
        """One of the endings that needs no cancel machinery: the world
        retracting a doorway retracts the journey that ran through it."""
        pg = self._pg()
        pg["edges"]["rD"]["rE"] = {"taken": True, "disproven": 9}
        assert _en_route(self._state(["rA", "rB"], pg), "rB",
                         self.DEST) is None

    def test_a_neighbouring_destination_needs_no_status_line(self):
        """Under two rooms out the exit verdict already says 'through here
        is X itself'; a character crossing a house to answer a door is not
        on a journey."""
        assert _en_route(self._state(["rC", "rD"]), "rD", self.DEST) is None

    def test_standing_in_it_is_arrival_not_a_journey(self):
        assert _en_route(self._state(["rD", "rE"]), "rE", self.DEST) is None

    def test_no_destination_is_silence(self):
        assert _en_route(self._state(["rA", "rB"]), "rB", None) is None

    def test_the_scene_is_never_consulted_by_construction(self):
        """Pinned so a future signature change has to argue with a test:
        the derivation has no scene parameter to leak from."""
        import inspect
        params = set(inspect.signature(_en_route).parameters)
        assert params == {"stored_state", "here_rid", "destination"}


class TestTowardHops:
    def test_a_route_over_taken_doorways_is_counted_in_rooms(self):
        adj = {"rB": {"rA", "rC"}, "rC": {"rB", "rD"}, "rD": {"rC"},
               "rA": {"rB"}}
        assert _toward_hops("rB", "rA", adj, "rD") == 3

    def test_the_exit_that_is_the_destination_reads_one(self):
        assert _toward_hops("rD", "rA", {}, "rD") == 1

    def test_no_remembered_route_is_silence_not_zero(self):
        adj = {"rB": {"rA"}, "rA": {"rB"}}
        assert _toward_hops("rB", "rA", adj, "rD") is None

    def test_the_route_never_doubles_back_through_where_he_stands(self):
        """A route through the room he is standing in belongs to the OTHER
        exit; counting it here would recommend both doorways for one way."""
        adj = {"rB": {"rA"}, "rA": {"rB", "rD"}, "rD": {"rA"}}
        assert _toward_hops("rB", "rA", adj, "rD") is None


class TestTheVerdictCarriesTheRoute:
    """Salience relocation, not addition -- the _annotate_known_exits
    discipline, held to under test."""

    def _world(self):
        """here rA; east exit rB starts a walked chain rB-rC-rD (rD the
        destination); west exit rX is a walked pocket. Everything walked, no
        frontier anywhere, so both exits earn discouraging verdicts -- the
        exact texture of A12 run 4, where every step of the optimal route
        read spent BECAUSE he had walked it."""
        scene = {"rooms": {
            "rA": _room("Room A", [_e("rB", "e"), _e("rX", "w")]),
            "rB": _room("Room B", [_e("rA", "w"), _e("rC", "e")]),
            "rC": _room("Room C", [_e("rB", "w"), _e("rD", "e")]),
            "rD": _room("Room D", [_e("rC", "w")]),
            "rX": _room("Room X", [_e("rA", "e"), _e("rY", "w")]),
            "rY": _room("Room Y", [_e("rX", "e")]),
        }}
        pg = _graph(
            [("rA", "rB"), ("rB", "rC"), ("rC", "rD"), ("rA", "rX"),
             ("rX", "rY")],
            {"rA": "Room A", "rB": "Room B", "rC": "Room C",
             "rD": "Room D", "rX": "Room X", "rY": "Room Y"})
        digest = {"ahead": [{"room": "Room X", "barrier": "open"},
                            {"room": "Room B", "barrier": "open"}]}
        visited = ["rY", "rX", "rA", "rB", "rC", "rD", "rC", "rB", "rA"]
        return scene, pg, digest, visited

    def _annotate(self, destination):
        scene, pg, digest, visited = self._world()
        return _annotate_known_exits(
            dict(digest), scene, visited, here_rid="rA",
            place_graph=pg, destination=destination)

    def test_the_route_rides_the_verdict_string(self):
        out = self._annotate({"rid": "rD", "name": "Room D"})
        on_route = next(e for e in out["ahead"] if e["room"] == "Room B")
        assert ("your own remembered ground runs from here to Room D, "
                "about 3 rooms along this way") in on_route["verdict"]
        off_route = next(e for e in out["ahead"] if e["room"] == "Room X")
        assert "remembered ground runs" not in str(off_route.get("verdict"))

    def test_no_new_key_is_added(self):
        """The whole difference between this fix working and backfiring:
        adding a routed-exit KEY beside the verdict would hand the payload
        a second heavy citable block, re-creating the salience inversion
        the verdict layer exists to prevent. String and ordering only."""
        base = self._annotate(None)
        routed = self._annotate({"rid": "rD", "name": "Room D"})
        by_room = {e["room"]: e for e in base["ahead"]}
        for r_entry in routed["ahead"]:
            assert set(r_entry) == set(by_room[r_entry["room"]]), (
                "destination routing added a key -- it must ride the "
                "verdict string and the ordering only")

    def test_an_on_route_exit_is_not_buried_by_its_own_discouragement(self):
        """Every room of his optimal route read `spent` because he had
        walked it -- which is why it was the route. Discouraging verdicts
        answer 'anything NEW that way?'; a named destination asks a
        different question, so the on-route exit must sort ahead of an
        equally-discouraged exit that leads nowhere he wants."""
        base = self._annotate(None)
        assert [e["room"] for e in base["ahead"]] == ["Room X", "Room B"], (
            "without a destination the digest order stands -- precondition")
        routed = self._annotate({"rid": "rD", "name": "Room D"})
        assert [e["room"] for e in routed["ahead"]] == ["Room B", "Room X"]

    def test_the_adjacent_destination_is_named_as_itself(self):
        """The run-3 shrine shape: the wanted room one doorway away,
        carrying a verdict about where it LEADS (nowhere), while what
        matters is what it IS. The suffix says so in words."""
        scene = {"rooms": {
            "rA": _room("Room A", [_e("rD", "s")]),
            "rD": _room("Room D", [_e("rA", "n")]),
        }}
        pg = _graph([("rA", "rD")], {"rA": "Room A", "rD": "Room D"})
        out = _annotate_known_exits(
            {"ahead": [{"room": "Room D", "barrier": "open"}]}, scene,
            ["rD", "rA"], here_rid="rA", place_graph=pg,
            destination={"rid": "rD", "name": "Room D"})
        entry = out["ahead"][0]
        assert ("through here is Room D itself -- the room your goal "
                "names") in entry["verdict"]

    def test_the_scene_is_never_consulted(self):
        """The wrong-map asymmetry, pinned. The connecting corridor is gone
        from the scene entirely -- bricked up since he walked it -- and the
        route must still be offered, because it is his MEMORY read back and
        finding the world changed is the measurable behaviour the
        maze-expansion arm exists to observe. Silently correcting his map
        would both leak truth and erase the measurement."""
        scene = {"rooms": {
            "rA": _room("Room A", [_e("rB", "e")]),
            "rB": _room("Room B", [_e("rA", "w")]),   # rC, rD demolished
        }}
        pg = _graph(
            [("rA", "rB"), ("rB", "rC"), ("rC", "rD")],
            {"rA": "Room A", "rB": "Room B", "rC": "Room C",
             "rD": "Room D"})
        out = _annotate_known_exits(
            {"ahead": [{"room": "Room B", "barrier": "open"}]}, scene,
            ["rA"], here_rid="rA", place_graph=pg,
            destination={"rid": "rD", "name": "Room D"})
        assert ("remembered ground runs from here to Room D"
                in out["ahead"][0]["verdict"])

    def test_a_disproven_doorway_breaks_the_remembered_route(self):
        """The one correction memory does accept: present perception has
        shown the doorway absent, and a route through an edge he himself
        has disproven would be memory outvoting his own eyes."""
        scene, pg, digest, visited = self._world()
        pg["edges"]["rC"]["rD"]["disproven"] = True
        out = _annotate_known_exits(
            dict(digest), scene, visited, here_rid="rA",
            place_graph=pg, destination={"rid": "rD", "name": "Room D"})
        on_route = next(e for e in out["ahead"] if e["room"] == "Room B")
        assert "remembered ground runs" not in str(on_route.get("verdict"))

    def test_standing_in_the_destination_routes_nowhere(self):
        scene, pg, digest, visited = self._world()
        out = _annotate_known_exits(
            dict(digest), scene, visited, here_rid="rA",
            place_graph=pg, destination={"rid": "rA", "name": "Room A"})
        for entry in out["ahead"]:
            assert "remembered ground runs" not in str(entry.get("verdict"))
