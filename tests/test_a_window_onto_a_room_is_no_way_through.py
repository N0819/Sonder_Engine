"""A window onto another room is a window: no way through, and never a doorway.

Home 9 (chat 172, 2026-10-12), the owner: "windows are being read like doors
in the editor". The layout tier makes a window with laid ground beyond it a
`window` edge onto that ground, and every edge derives a `door:<to>` anchor,
so the World Browser's room editor drew Hinami's east window as a doorway
onto the garden and listed it among the exits; the story's one walk graph
(`room_slice.room_graph`) put the garden one hop from her second-storey room,
through the window; and the opening's echo of `windows: ["e"]` was kept as a
second east window beside the edge.
"""
from __future__ import annotations

import time


def _house():
    return {"rooms": {
        "bedroom": {"name": "Hinami's Room", "desc": "A tatami room.", "level": 1,
                    "extent": {"w": 8, "d": 5}, "exposure": "enclosed",
                    "windows": ["e"],
                    "adjacent": [
                        {"to": "garden", "barrier": "window", "dir": "e", "material": "glass",
                         "desc": "A wooden-framed window facing the moonrise."},
                        {"to": "hall", "barrier": "closed_door", "dir": "s", "material": "paper",
                         "desc": "A shoji door of paper over a light wooden lattice."}]},
        "hall": {"name": "the Upper Hallway", "desc": "A corridor.", "level": 1,
                 "extent": {"w": 8, "d": 3}, "exposure": "enclosed",
                 "adjacent": [{"to": "bedroom", "barrier": "closed_door", "dir": "n"}]},
        "garden": {"name": "the Garden", "desc": "Raked gravel.", "level": 0,
                   "extent": {"w": 12, "d": 12}, "exposure": "open",
                   "adjacent": [{"to": "bedroom", "barrier": "window", "dir": "w"}]}},
        "positions": {"Hinami": "bedroom"}, "stations": {}, "entities": {}}


# ---------------------------------------------------------------------------
# One window per window
# ---------------------------------------------------------------------------

def test_a_bare_bearing_a_window_edge_looks_along_is_that_window():
    from world.spatial import room_windows
    room = {"windows": ["e", "e", "n", {"id": "gable", "dir": "e", "cell": [5, 1]}],
            "adjacent": [{"to": "garden", "barrier": "window", "dir": "e"},
                         {"to": "hall", "barrier": "closed_door", "dir": "n"}]}
    # the edge answers ONE bare "e"; a second is a window of its own, a
    # record says where it stands and is never answered, a door answers none
    assert [w["id"] for w in room_windows(room)] == ["e", "n", "gable"]
    assert [w["id"] for w in room_windows(_house()["rooms"]["bedroom"])] == []


def test_a_beat_echoing_a_window_edge_as_a_bearing_stores_no_second_window():
    from world.spatial import merge_scene_with_diff
    sc = _house()
    sc["rooms"]["bedroom"].pop("windows")
    merged = merge_scene_with_diff(sc, {"rooms": {"bedroom": {"windows": ["e", "w"]}}})
    assert merged["rooms"]["bedroom"]["windows"] == ["w"], "the east one is the edge's"
    # the edge arriving in the same beat answers it too
    sc["rooms"]["bedroom"]["adjacent"] = [
        e for e in sc["rooms"]["bedroom"]["adjacent"] if e["to"] != "garden"]
    merged = merge_scene_with_diff(sc, {"rooms": {"bedroom": {
        "windows": ["e"], "adjacent": [{"to": "garden", "barrier": "window", "dir": "e"}]}}})
    assert not merged["rooms"]["bedroom"].get("windows")


# ---------------------------------------------------------------------------
# No walk steps through a window
# ---------------------------------------------------------------------------

def test_a_walk_over_the_plan_never_steps_through_its_window(temp_db):
    from story.room_slice import room_hops
    from world.structure import planned_topology, plant_structure
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Windows", "", time.time()))
    scene = {"rooms": {"loft": {"name": "the Loft", "desc": "A loft.", "level": 1,
                                "adjacent": [{"to": "garden", "barrier": "window", "dir": "e"},
                                             {"to": "stair", "barrier": "closed_door", "dir": "s"}]}},
             "positions": {"Mara": "loft"}, "entities": {}}
    temp_db.wset(cid, "scene", scene)
    plant_structure(cid, {"key": "house", "name": "House"}, {
        "stair": {"name": "the Stair", "purpose": "a stair", "exposure": "enclosed", "level": 1,
                  "adjacent": [{"to": "loft", "barrier": "closed_door", "dir": "n"},
                               {"to": "hall", "vertical": "down"}]},
        "hall": {"name": "the Hall", "purpose": "a hall", "exposure": "enclosed", "level": 0,
                 "adjacent": [{"to": "stair", "vertical": "up"},
                              {"to": "garden", "barrier": "open_door", "dir": "e"},
                              {"to": "cellar", "barrier": "wall", "dir": "w"}]},
        "garden": {"name": "the Garden", "purpose": "a garden", "exposure": "open", "level": 0,
                   "adjacent": [{"to": "loft", "barrier": "window", "dir": "w"},
                                {"to": "hall", "barrier": "open_door", "dir": "w"}]},
        "cellar": {"name": "the Cellar", "purpose": "a cellar", "exposure": "enclosed", "level": 0,
                   "adjacent": [{"to": "hall", "barrier": "bars", "dir": "e"}]}})
    every, routes = planned_topology(cid), planned_topology(cid, routes_only=True)
    assert "loft" in every["garden"] and "loft" not in routes["garden"]
    assert "cellar" in every["hall"] and "cellar" not in routes["hall"], "a wall is no way"
    assert routes["cellar"] == [] and set(routes) == set(every), "every room keeps its key"
    assert "hall" in routes["stair"], "a stair with no barrier word is an opening"
    hops = room_hops(cid, scene, ["loft"])
    assert hops["garden"] == 3, "down the stair and out the door, never out of the window"
    assert "cellar" not in hops


# ---------------------------------------------------------------------------
# The World Browser draws and lists it as a window
# ---------------------------------------------------------------------------

def test_the_editor_lists_a_window_onto_a_room_with_the_windows():
    from web.world_routes import _anchor_kind, grid_view
    sc = _house()
    view = grid_view(sc, "bedroom", [])
    assert [d["to"] for d in view["doorways"]] == ["hall"]
    (door,) = view["doorways"]
    assert door["desc"] == "A shoji door of paper over a light wooden lattice."
    (window,) = view["windows"]
    assert (window["id"], window["to"], window["dir"]) == ("door:garden", "garden", "e")
    assert window["desc"] == "A wooden-framed window facing the moonrise."
    assert window["material"] == "glass" and window["cells"], "drawn in its wall"
    assert _anchor_kind(sc, "bedroom", "door:garden") == "window"
    assert _anchor_kind(sc, "bedroom", "door:hall") == "doorway"
    sc["rooms"]["bedroom"]["windows"] = ["n"]
    assert _anchor_kind(sc, "bedroom", "window:n") == "window"
    assert _anchor_kind(sc, "bedroom", "futon") == "fixture"


def test_the_map_of_every_room_marks_a_window_as_one():
    from web.world_routes import map_view
    exits = {(row["id"], e["to"]): e for comp in map_view(_house(), [])["components"]
             for row in comp["rooms"] for e in row["exits"]}
    assert exits[("bedroom", "garden")]["window"] is True
    assert "window" not in exits[("bedroom", "hall")], "a door reads as it did"
