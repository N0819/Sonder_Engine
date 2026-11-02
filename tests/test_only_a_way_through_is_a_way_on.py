"""What a body is told about the way on counts only ways a body could go
through: a window, bars or a wall is no exit, a door ahead is a door, and a
dead end is a dead end.

Audit world_spatial_movement_sight (2026-11-01, all CONFIRMED WRONG-SCENE):

* F12: `_onward_exits` counted every non-wall edge, so a chamber whose only
  other opening is a window (or bars, or an `unknown`) reported
  `{'onward_exits': 1, 'onward_bearings': ['n']}` -- handing a maze runner a
  north "exit" made of glass; the class is the one `_ROUTE_MEMORY_BARRIERS`
  states ("sends its owner marching at a pane of glass").
* F13: `corridor_sightlines` called a closed door or a curtain straight ahead
  a "turn" (the passage "bends and continues"), and a dead end whose only
  other edge is a side window a "turn" too.
* F14: `sprint_reach` said `stops: "door"` for a dead end whose only other
  edge is a wall or a window -- a runner told to expect a door he may open.
"""

from world.spatial import corridor_sightlines, sprint_reach, visible_adjacent_rooms


def _room(name, edges, **extra):
    return {"name": name, "desc": f"The {name}.", "adjacent": edges, **extra}


def _chamber(other_barrier):
    return {"rooms": {
        "hall": _room("Hall", [{"to": "chamber", "barrier": "open_door", "dir": "e"}]),
        "chamber": _room("Chamber", [
            {"to": "hall", "barrier": "open_door", "dir": "w"},
            {"to": "garden", "barrier": other_barrier, "dir": "n"}]),
        "garden": _room("Garden", [], exposure="open"),
    }, "positions": {"Ada": "hall"}, "entities": {}}


def _onward(scene):
    return {r["room_id"]: r for r in visible_adjacent_rooms(scene, "hall")}["chamber"]


def test_a_window_bars_or_unknown_is_no_way_on():
    for barrier in ("window", "bars", "unknown", "wall"):
        row = _onward(_chamber(barrier))
        assert row.get("onward_exits") == 0, (barrier, row)
        assert "onward_bearings" not in row


def test_a_door_or_an_opening_is_a_way_on():
    for barrier in ("open_door", "closed_door", "open", "membrane"):
        row = _onward(_chamber(barrier))
        assert row.get("onward_exits") == 1, (barrier, row)
        assert row.get("onward_bearings") == ["n"]


def _corridor(end_barrier, *, side=None):
    rooms = {
        "start": _room("Start", [{"to": "c1", "barrier": "open", "dir": "n"}]),
        "c1": _room("C1", [{"to": "start", "barrier": "open", "dir": "s"},
                           {"to": "c2", "barrier": "open", "dir": "n"}]),
        "c2": _room("C2", [{"to": "c1", "barrier": "open", "dir": "s"}]),
        "c3": _room("C3", []),
        "side": _room("Side", []),
    }
    if end_barrier:
        rooms["c2"]["adjacent"].append({"to": "c3", "barrier": end_barrier, "dir": "n"})
    if side:
        rooms["c2"]["adjacent"].append({"to": "side", "barrier": side, "dir": "e"})
    return {"rooms": rooms, "positions": {"Ada": "start"}, "entities": {}}


def _north(scene):
    lines = [line for line in corridor_sightlines(scene, "start") if line["dir"] == "n"]
    assert len(lines) == 1, lines
    return lines[0]


def test_a_shut_door_ahead_ends_the_line_as_a_door():
    for barrier in ("closed_door", "membrane"):
        line = _north(_corridor(barrier))
        assert line["terminus"] == "door", (barrier, line)


def test_a_dead_end_with_only_a_side_window_is_a_dead_end():
    line = _north(_corridor(None, side="window"))
    assert line["terminus"] == "dead_end", line


def test_a_real_bend_is_still_a_turn():
    line = _north(_corridor(None, side="open"))
    assert line["terminus"] == "turn", line


def _run(end_barrier):
    sc = _corridor(None)
    sc["rooms"]["c2"]["adjacent"].append(
        {"to": "c3", "barrier": end_barrier, "dir": "e"})
    runs = [r for r in sprint_reach(sc, "start") if r.get("bearing") == "n"]
    assert len(runs) == 1, runs
    return runs[0]


def test_a_run_into_a_wall_or_a_window_is_a_dead_end():
    for barrier in ("wall", "window", "bars"):
        assert _run(barrier)["stops"] == "dead_end", barrier


def test_a_run_into_a_shut_door_stops_at_the_door():
    assert _run("closed_door")["stops"] == "door"
