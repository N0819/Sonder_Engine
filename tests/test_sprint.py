"""Running: more than one room in a beat, bounded by what you can see.

A character could only ever move one room per beat, which makes a courier
whose whole craft is speed indistinguishable from someone strolling and turns
distance into a queue of identical beats.

The bound is sight, and that is the whole firewall argument: a run can only
carry a body down a passage they can already see along, so it hands them no
knowledge they had not earned by looking. Every test here is really a test
that the run stops where looking stops.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from spatial import SPRINT_BUDGET, sprint_reach


def _room(name, adjacent, **kw):
    return {"name": name, "desc": name, "adjacent": adjacent, **kw}


def _e(to, direction, barrier="open"):
    return {"to": to, "dir": direction, "barrier": barrier}


def _scene(rooms):
    return {"rooms": rooms, "positions": {}, "entities": {}, "attire": {},
            "overlays": {}}


def _corridor(n=6, **room_kw):
    """A straight run of n rooms east from `start`."""
    rooms = {"start": _room("Start", [_e("c1", "e")])}
    for i in range(1, n + 1):
        adj = [_e("start" if i == 1 else f"c{i-1}", "w")]
        if i < n:
            adj.append(_e(f"c{i+1}", "e"))
        rooms[f"c{i}"] = _room(f"C{i}", adj, **room_kw)
    return _scene(rooms)


def _one(reach, bearing="e"):
    return next((r for r in reach if r["bearing"] == bearing), None)


def test_a_run_covers_several_rooms():
    run = _one(sprint_reach(_corridor(), "start"))
    assert run and run["rooms"] == SPRINT_BUDGET
    assert run["path"] == ["c1", "c2", "c3"]
    assert run["stops"] == "winded"


def test_the_path_is_every_room_crossed_not_just_the_destination():
    """A body that runs through three chambers has been in three chambers.
    Recording only where they stopped would leave holes in their map exactly
    where their feet went -- and the place graph builds walked edges from
    this, so the holes would be permanent."""
    run = _one(sprint_reach(_corridor(), "start"))
    assert run["path"][-1] == "c3", "path must END at the room they stop in"
    assert len(run["path"]) == run["rooms"]
    assert len(set(run["path"])) == len(run["path"]), "no room twice"


def test_a_big_room_eats_more_of_the_run():
    """Distance, not room count. Crossing a hall is not one stride."""
    small = _one(sprint_reach(_corridor(), "start"))
    large = _one(sprint_reach(_corridor(size="large"), "start"))
    assert large["rooms"] < small["rooms"]
    vast = _one(sprint_reach(_corridor(size="vast"), "start"))
    assert vast["rooms"] == 1, "a vast hall is the whole beat"


def test_it_stops_at_a_turn():
    """You cannot see round a corner, so you cannot run round one."""
    sc = _scene({
        "start": _room("Start", [_e("c1", "e")]),
        "c1": _room("C1", [_e("start", "w"), _e("c2", "n")]),
        "c2": _room("C2", [_e("c1", "s")]),
    })
    run = _one(sprint_reach(sc, "start"))
    assert run["path"] == ["c1"] and run["stops"] == "turn"


def test_it_stops_at_a_junction():
    """A junction is a decision and a decision is a beat. Running blind
    through one would be choosing without looking."""
    sc = _scene({
        "start": _room("Start", [_e("c1", "e")]),
        "c1": _room("C1", [_e("start", "w"), _e("c2", "e"), _e("c3", "n")]),
        "c2": _room("C2", [_e("c1", "w")]),
        "c3": _room("C3", [_e("c1", "s")]),
    })
    run = _one(sprint_reach(sc, "start"))
    assert run["path"] == ["c1"] and run["stops"] == "junction"


def test_it_stops_at_the_dark():
    """Running into a room you cannot see into is how a body breaks an ankle,
    and it is also how a character would learn a room they never saw."""
    sc = _corridor(4)
    sc["rooms"]["c2"]["light"] = "dark"
    run = _one(sprint_reach(sc, "start"))
    assert run["path"] == ["c1"]
    assert run["stops"] == "darkness"


def test_you_cannot_run_through_glass():
    """The sightline follows any see-through barrier; a run follows only
    passable ones. You can see through bars and you cannot run through them."""
    sc = _scene({
        "start": _room("Start", [_e("c1", "e", barrier="bars")]),
        "c1": _room("C1", [_e("start", "w")]),
    })
    assert sprint_reach(sc, "start") == []

    sc2 = _corridor(4)
    sc2["rooms"]["c1"]["adjacent"][1]["barrier"] = "window"
    run = _one(sprint_reach(sc2, "start"))
    assert run["path"] == ["c1"] and run["stops"] == "door"


def test_a_closed_door_ends_the_run_rather_than_opening_itself():
    sc = _corridor(4)
    sc["rooms"]["c1"]["adjacent"][1]["barrier"] = "closed_door"
    run = _one(sprint_reach(sc, "start"))
    assert run["path"] == ["c1"] and run["stops"] == "door"


def test_a_dead_end_is_reported_as_one():
    run = _one(sprint_reach(_corridor(2), "start"))
    assert run["path"] == ["c1", "c2"] and run["stops"] == "dead_end"


def test_a_scene_without_directions_offers_no_runs():
    """No `dir` means no line to follow, and inventing one would invent a
    sense -- the same rule corridor_sightlines keeps."""
    sc = _scene({
        "start": _room("Start", [{"to": "c1", "barrier": "open"}]),
        "c1": _room("C1", [{"to": "start", "barrier": "open"}]),
    })
    assert sprint_reach(sc, "start") == []


def test_junk_does_not_crash_it():
    assert sprint_reach({}, "nowhere") == []
    assert sprint_reach(None, "start") == []
    assert sprint_reach(_scene({"start": _room("S", ["junk", None])}),
                        "start") == []
    # An edge naming a room that is not in the scene stops the run, and does
    # not put a phantom room in the path.
    sc = _scene({"start": _room("Start", [_e("gone", "e")])})
    assert sprint_reach(sc, "start") == []


def test_every_passage_out_gets_its_own_answer():
    sc = _scene({
        "start": _room("Start", [_e("e1", "e"), _e("w1", "w")]),
        "e1": _room("E1", [_e("start", "w")]),
        "w1": _room("W1", [_e("start", "e")]),
    })
    reach = sprint_reach(sc, "start")
    assert {r["bearing"] for r in reach} == {"e", "w"}


class TestRunningIsRemembered:
    """The rooms crossed at a run must land in memory, or the map gets holes
    exactly where the feet went -- and worse than holes: the place graph mints
    walked edges from adjacent steps, so a corridor sprinted end to end would
    keep reading as untrodden and pull him back down it."""

    def _sc(self):
        return _corridor(4)

    def test_the_rooms_run_through_are_recorded(self):
        from commit import record_spatial_experience
        sc = self._sc()
        st = {}
        record_spatial_experience(st, sc, "start", 1)
        record_spatial_experience(st, sc, "c3", 2)      # ran three rooms
        assert st["visited_rooms"] == ["start", "c1", "c2", "c3"]

    def test_the_walked_edges_span_the_whole_run(self):
        from commit import record_spatial_experience
        sc = self._sc()
        st = {}
        record_spatial_experience(st, sc, "start", 1)
        record_spatial_experience(st, sc, "c3", 2)
        edges = st["place_graph"]["edges"]
        assert edges.get("c2", {}).get("c3", {}).get("taken") is True, (
            "the last leg of the run must read as walked")

    def test_a_teleport_still_mints_nothing(self):
        """No passable route means carried, teleported, or shipped. A
        character learns a place by being carried through it about as well as
        a parcel does."""
        from commit import record_spatial_experience
        sc = _scene({
            "here": _room("Here", []),
            "far": _room("Far", []),
        })
        st = {}
        record_spatial_experience(st, sc, "here", 1)
        record_spatial_experience(st, sc, "far", 2)
        assert st["visited_rooms"] == ["here", "far"], "no invented rooms"
        assert not (st["place_graph"]["edges"].get("here") or {}).get("far")

    def test_an_ordinary_step_is_unchanged(self):
        """One room is a one-element path, so a walk needs no special case --
        and must not gain one."""
        from commit import record_spatial_experience
        sc = self._sc()
        st = {}
        record_spatial_experience(st, sc, "start", 1)
        record_spatial_experience(st, sc, "c1", 2)
        assert st["visited_rooms"] == ["start", "c1"]
        assert st["place_graph"]["edges"]["start"]["c1"]["taken"] is True
