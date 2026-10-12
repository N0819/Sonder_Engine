"""A window is in its wall, never a fixture standing in the room.

The owner's shrine (chat 168, 2026-10-12): "windows are being made as
fixtures instead of being actual windows". The layout tier laid every window
as an anchor among the furniture, the opening wrote a second `window` anchor
beside two of them, and no view looked out of any, since only a room's
`windows` and a `window` edge look out. A window onto ground the solve laid
is now that ground's window edge (`tests/test_a_building_stands_in_its_grounds.py`);
every other one is a record in its room's `windows`, where it stands in the
wall, deriving a `window:<id>` pseudo-anchor a body can stand at.
"""
from __future__ import annotations

import copy
import time

WINDOW = {"id": "east_window", "dir": "e", "cell": [5, 2],
          "name": "a window facing the moonrise"}


def _scene(windows=None, **extra):
    room = {"name": "Bedroom", "desc": "A bedroom.", "extent": {"w": 6, "d": 5},
            "exposure": "enclosed", "adjacent": [],
            "windows": copy.deepcopy([WINDOW] if windows is None else windows)}
    room.update(extra)
    return {"rooms": {"bedroom": room}, "positions": {"Hinami": "bedroom"},
            "stations": {"Hinami": {"cell": [2, 2]}}, "entities": {}}


def test_a_window_is_the_rooms_own_and_a_body_can_stand_at_it():
    from world.spatial import anchor_cells, effective_anchors, room_windows
    sc = _scene([WINDOW, "n"])
    assert room_windows(sc["rooms"]["bedroom"]) == [
        {"id": "east_window", "dir": "e", "cell": (5, 2), "name": "a window facing the moonrise"},
        {"id": "n", "dir": "n", "cell": None, "name": ""}]
    anchors = effective_anchors(sc, "bedroom")
    east = anchors["window:east_window"]
    assert east["desc"] == "a window facing the moonrise" and east["implicit"] and east["described"]
    assert east["opacity"] == "see_through" and east["dir"] == "e"
    assert anchors["window:n"]["desc"] == "the window"
    assert [tuple(c) for c in anchor_cells(sc, "bedroom")["window:east_window"]["cells"]] == [(5, 2)]
    assert "anchors" not in sc["rooms"]["bedroom"], "derived, never written"


def test_a_view_names_the_window_where_it_stands():
    from agents.perception import _visible_features
    rows = _visible_features(_scene(), "Hinami", "bedroom", sweep=True)
    assert any(r["desc"] == "a window facing the moonrise" for r in rows), rows


def test_a_window_looks_out_along_its_bearing():
    from world.landscape import outlook
    assert outlook(_scene(), "bedroom") == {"ne", "e", "se"}
    assert outlook(_scene([]), "bedroom") == set()


def test_a_window_is_drawn_in_its_wall_and_never_hung_on_it():
    from dressing.backdrops import _openings_of, _walls_of
    sc = _scene()
    assert {"barrier": "window", "name": "a window facing the moonrise"} in _openings_of(sc, "bedroom")["e"]
    assert not any("window" in str(item) for items in _walls_of(sc, "bedroom").values()
                   for item in items)


def test_a_map_draws_the_window_in_its_wall_and_not_among_the_furniture():
    from web.world_routes import grid_view
    view = grid_view(_scene(), "bedroom", [])
    (window,) = view["windows"]
    assert window["id"] == "window:east_window" and window["dir"] == "e"
    assert window["cells"] == [[5, 2]]
    assert not any(aid.startswith("window:") for aid in view["anchors"])
    assert "windows" not in grid_view(_scene([]), "bedroom", []), "a room with none reads as it did"


def test_a_beat_echoing_bearings_never_wipes_a_placed_window():
    """Chat 168's opening wrote `windows: ["e"]` on Hinami's room, whose solve
    placed an east window: read as a replacement, the window would lose its
    place in the wall the first time the room was described."""
    from world.spatial import merge_scene_with_diff
    sc = merge_scene_with_diff(_scene(), {"rooms": {"bedroom": {"windows": ["e"]}}})
    assert sc["rooms"]["bedroom"]["windows"] == [WINDOW]
    sc = merge_scene_with_diff(_scene(), {"rooms": {"bedroom": {"windows": ["e", "n"]}}})
    assert sc["rooms"]["bedroom"]["windows"] == [WINDOW, "n"]
    # where the room holds only bearings, the beat's list is the room's
    sc = merge_scene_with_diff(_scene(["e"]), {"rooms": {"bedroom": {"windows": ["n"]}}})
    assert sc["rooms"]["bedroom"]["windows"] == ["n"]


def test_a_window_is_no_doorway_to_the_checks_that_count_doorways():
    """`implicit` says an anchor was derived; a doorway is the `door:` one.
    A window on the wall a doorway shares is not a second opening crowding
    it."""
    from world.spatial import room_layout_lint
    sc = _scene([dict(WINDOW, cell=[5, 1])])
    sc["rooms"]["hall"] = {"name": "Hall", "adjacent": [
        {"to": "bedroom", "barrier": "closed_door", "dir": "w"}]}
    sc["rooms"]["bedroom"]["adjacent"] = [
        {"to": "hall", "barrier": "closed_door", "dir": "e", "offset": 0.25}]
    assert not [r for r in room_layout_lint(sc) if r.get("kind") == "openings_overlap"]


def test_the_solves_windows_go_onto_its_stub_and_come_off_with_it():
    """A stub laid on its solved plan takes the plan's windows -- records,
    and each window edge the solve made, which a stub minted before the
    solve never had -- and loses any record of the plan the solve laid as a
    window. A re-plan takes back exactly those."""
    from world import structure
    spec = {"extent": {"w": 6, "d": 5}, "shape": "rectangle", "level": 1,
            "site": {"plan": "layout:hall", "x": 0, "y": 0, "elev_m": 3.0},
            "windows": [copy.deepcopy(WINDOW)],
            "adjacent": [{"to": "hall", "vertical": "down", "way": "stair"},
                         {"to": "garden", "barrier": "window", "dir": "n", "offset": 0.5,
                          "name": "a little window under the eaves"}],
            "layout": {"plan": "layout:hall", "made_edges": ["garden"],
                       "windows_from": ["gable_window"]}}
    room = {"name": "the Loft", "planned": True,
            "adjacent": [{"to": "hall", "vertical": "down", "way": "stair"}],
            "anchors": {"gable_window": {"desc": "a gable window"}, "bed": {"desc": "a bed"}}}
    structure._lay_stub_on_its_plan(room, spec)
    assert room["windows"] == [WINDOW]
    assert {e["to"]: e.get("barrier") for e in room["adjacent"]} == {"hall": None, "garden": "window"}
    assert set(room["anchors"]) == {"bed"}
    assert room[structure.LAID_OUT_KEY]["made"] == ["garden"]
    replanned = {"extent": {"w": 6, "d": 5},
                 "adjacent": [{"to": "hall", "vertical": "down", "way": "stair"}]}
    structure._take_the_solve_off(room, replanned, room[structure.LAID_OUT_KEY])
    assert "windows" not in room
    assert [e["to"] for e in room["adjacent"]] == ["hall"]


def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Windows", "A farm.", time.time()))


def test_a_re_solve_moves_or_takes_back_its_own_window_edges_and_nothing_else(temp_db):
    from world.structure import plant_structure, registry_rows, write_planned_layout
    cid = _chat(temp_db)
    plant_structure(cid, {"key": "farm", "name": "Farm"}, {
        "loft": {"name": "the Loft", "purpose": "a loft",
                 "anchors": {"gable_window": {"desc": "a gable window"}},
                 "adjacent": [{"to": "yard", "barrier": "closed_door"}]},
        "yard": {"name": "the Yard", "purpose": "a yard", "exposure": "open",
                 "adjacent": [{"to": "loft", "barrier": "closed_door"}]},
        "garden": {"name": "the Garden", "purpose": "a garden", "exposure": "open",
                   "adjacent": []}})

    def plans():
        return {uid: e["planned"] for uid, e in registry_rows(cid).items()}

    def ways(uid):
        return {e["to"]: e for e in plans()[uid].get("adjacent") or ()}

    first = {
        "loft": {"geometry": {"windows": None},
                 "made_edges": {"garden": {"barrier": "window", "dir": "n", "offset": 0.5}},
                 "layout": {"plan": "layout:loft", "made_edges": ["garden"],
                            "windows_from": ["gable_window"]}},
        "garden": {"geometry": {},
                   "made_edges": {"loft": {"barrier": "window", "dir": "s", "cell": [3, 4]}},
                   "layout": {"plan": "layout:loft", "made_edges": ["loft"]}}}
    assert write_planned_layout(cid, first, expected=plans())
    assert ways("loft")["garden"]["barrier"] == "window" and ways("garden")["loft"]["cell"] == [3, 4]
    assert "gable_window" not in (plans()["loft"].get("anchors") or {})
    assert ways("loft")["yard"]["barrier"] == "closed_door"
    moved = copy.deepcopy(first)
    moved["loft"]["made_edges"]["garden"]["offset"] = 0.25
    assert write_planned_layout(cid, moved, expected=plans())
    assert ways("loft")["garden"]["offset"] == 0.25 and len(plans()["loft"]["adjacent"]) == 2
    # a solve that lays the window in the wall instead takes its edge back
    # -- and never the plan's own door to the yard
    record = {"loft": {"geometry": {"windows": [copy.deepcopy(WINDOW)]},
                       "layout": {"plan": "layout:loft"}},
              "garden": {"geometry": {}, "layout": {"plan": "layout:loft"}}}
    assert write_planned_layout(cid, record, expected=plans())
    assert set(ways("loft")) == {"yard"} and set(ways("garden")) == set()
    assert plans()["loft"]["windows"] == [WINDOW]
