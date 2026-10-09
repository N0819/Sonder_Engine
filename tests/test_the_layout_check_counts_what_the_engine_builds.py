"""The layout check counts what the engine actually builds
(`world/spatial_lint.py`, behind `world/spatial.py`).

Three rows fired on valid output, each measured over every stored scene of
the 2026-10-08 play database (139 scenes) before it was cut, and listed for
the owner:

- A WALL IS COUNTED AT EACH HEIGHT, along its rim. A head-height shelf over a
  waist-height bartop is one stretch of wall holding two things, and a large
  fixture's inward row is floor in front of the wall: the standing
  `co_op_office` row (a chair under a desk on a four-pace wall), copied into
  six chats, was this over-count.
- A WHOLE OPEN SIDE HOLDS ANY OTHER OPENING on its wall (the owner's rule of
  2026-09-15: an open way between two unenclosed rooms spans the wall), so
  no offset could clear the row: the Gale house landing's design ended its
  eight steps on it (chat 166, turn 22).
- A STAIR NAMES EACH FLOOR'S OWN WALL. The engine keeps both ends' bearings
  and gives a silent floor the other's (`normalize_scene_bearings`), and the
  check demanded opposites: a designer flipped one stair between n and s for
  seven steps.

What stays: two narrow doorways on one cell, a wall over-full at one height,
and a level doorway whose two bearings are not opposites.
"""

from __future__ import annotations

from world.spatial import room_layout_lint, wall_loads


def _scene(rooms):
    return {"rooms": rooms, "positions": {}, "entities": {}}


def _rows(scene, kind):
    return [row for row in room_layout_lint(scene) if row["kind"] == kind]


def test_a_shelf_over_a_bartop_is_not_an_overfull_wall():
    sc = _scene({"bar": {"name": "Bar", "extent": {"w": 6, "d": 4}, "anchors": {
        "bartop": {"desc": "a bartop", "dir": "n", "footprint": "run", "height": "waist"},
        "shelf": {"desc": "a bottle shelf", "dir": "n", "footprint": "run",
                  "height": "head"}}}})
    assert _rows(sc, "wall_overfull") == []
    assert wall_loads(sc, "bar") == {("n", "waist"): {"bartop": 4},
                                     ("n", "head"): {"shelf": 4}}


def test_a_large_fixtures_inward_row_is_floor_not_wall():
    sc = _scene({"room": {"name": "Room", "extent": {"w": 4, "d": 6}, "anchors": {
        "chest": {"desc": "a chest", "dir": "n", "footprint": "large", "height": "waist"},
        "crate": {"desc": "a crate", "dir": "n", "footprint": "small",
                  "height": "waist"}}}})
    assert _rows(sc, "wall_overfull") == []


def test_a_wall_overfull_at_one_height_is_still_a_row_and_says_which():
    sc = _scene({"room": {"name": "Room", "extent": {"w": 4, "d": 6}, "anchors": {
        aid: {"desc": aid, "dir": "n", "footprint": "small", "height": "waist"}
        for aid in ("a", "b", "c")}}})
    (row,) = _rows(sc, "wall_overfull")
    assert (row["wall"], row["height"], row["needs"], row["holds"]) == ("n", "waist", 6, 4)


def test_a_whole_open_side_holds_any_other_opening_and_two_doors_still_collide():
    yard = {"name": "Yard", "exposure": "open", "extent": {"w": 6, "d": 4},
            "adjacent": [{"to": "lane", "barrier": "open", "dir": "s"},
                         {"to": "shed", "barrier": "closed_door", "dir": "s"}]}
    sc = _scene({"yard": yard,
                 "lane": {"name": "Lane", "exposure": "open"},
                 "shed": {"name": "Shed"}})
    assert _rows(sc, "openings_overlap") == [], "the lane's open side spans the wall"
    narrow = _scene({"room": {"name": "Room", "extent": {"w": 2, "d": 6}, "adjacent": [
        {"to": "a", "barrier": "open_door", "dir": "n"},
        {"to": "b", "barrier": "open_door", "dir": "n"}]},
        "a": {"name": "A"}, "b": {"name": "B"}})
    (row,) = _rows(narrow, "openings_overlap")
    assert sorted(row["openings"]) == ["door:a", "door:b"]


def test_a_stair_names_each_floors_own_wall_and_a_door_still_needs_opposites():
    stair = _scene({
        "inn": {"name": "Inn", "adjacent": [{"to": "rooms", "barrier": "closed_door",
                                              "dir": "s", "vertical": "up",
                                              "way": "stair"}]},
        "rooms": {"name": "Rooms", "adjacent": [{"to": "inn", "barrier": "closed_door",
                                                  "dir": "s", "vertical": "down",
                                                  "way": "stair"}]}})
    assert _rows(stair, "reciprocal_bearing_disagrees") == []
    door = _scene({
        "a": {"name": "A", "adjacent": [{"to": "b", "barrier": "open_door", "dir": "n"}]},
        "b": {"name": "B", "adjacent": [{"to": "a", "barrier": "open_door", "dir": "n"}]}})
    assert len(_rows(door, "reciprocal_bearing_disagrees")) == 1
