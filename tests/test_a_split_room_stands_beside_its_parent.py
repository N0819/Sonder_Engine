"""A room the charter closure invents stands beside the room it came from.

`charter_generate._spread_berths` splits a dwelling too full for one room
into siblings that copy its doorways, so whichever wall a hand gives the
parent's street, every sibling was laid on the same stretch of it: chat 165's
opening put the Back Row and its four siblings on the cross walk's north
wall and the planar layout stacked all five -- 8 of that town's 19 standing
plane-embedding rows, and no site plan for any room of the town
(`docs/design/DESIGN_CHARTER_PLACES.md`). Hand-made scenes; the names are
illustrations, not the rule.
"""

from __future__ import annotations

import copy

from world.frontage import (ANNEX_OF, FRONTAGE_MEASURES_STREETS, SPLIT_OF,
                            _span, lay_frontages, splits_from_specs)
from world.spatial import normalize_scene_bearings, room_layout_lint


def _stub(name, extent=None, **extra):
    room = {"name": name, "planned": True, "adjacent": []}
    if extent:
        room["extent"] = {"w": extent[0], "d": extent[1]}
    room.update(extra)
    return room


def _row_on_a_lane(lane_extent=(20, 3), siblings=2, *, plan_dir=None,
                   lane_desc=""):
    """A lane, a house on its north side and the house's siblings, every
    doorway declared north-south the way the opening's establish declared
    chat 165's -- the plan itself carrying no bearing unless `plan_dir`."""
    rooms = {"lane": _stub("the Lane", lane_extent, exposure="open")}
    if lane_desc:
        rooms["lane"]["desc"] = lane_desc
        rooms["lane"].pop("planned")
    specs = {"lane": {"name": "the Lane", "adjacent": []}}
    ids = ["house"] + [f"house_{n}" for n in range(2, siblings + 2)]
    for rid in ids:
        rooms[rid] = _stub(rid, (6, 5), exposure="enclosed")
        rooms[rid]["adjacent"].append({"to": "lane", "barrier": "open_door", "dir": "s"})
        rooms["lane"]["adjacent"].append({"to": rid, "barrier": "open_door", "dir": "n"})
        spec_edge = {"to": "lane", "barrier": "open_door"}
        if plan_dir:
            spec_edge["dir"] = plan_dir
        specs[rid] = {"name": rid, "adjacent": [spec_edge]}
        if rid != "house":
            specs[rid][SPLIT_OF] = "house"
    scene = {"rooms": rooms, "entities": {}, "positions": {}}
    # The merge's own pass: reciprocal bearings and the even doorway spread.
    normalize_scene_bearings(scene)
    return scene, specs, ids


def _plane_rows_naming(scene, ids):
    return [row for row in room_layout_lint(scene)
            if row["kind"] == "rooms_overlap_when_placed"
            and set(row["rooms"]) & set(ids)]


def _runs(scene, street, ids):
    return sorted(_span(scene, street, rid)[1:] for rid in ids)


def test_the_closures_marks_name_each_split_and_its_parent():
    specs = {"a": {SPLIT_OF: "house"}, "b": {SPLIT_OF: "house"},
             "c": {ANNEX_OF: "inn"}, "house": {}, "inn": {}}
    assert splits_from_specs(specs) == {
        "house": {"mode": "siblings", "rooms": ["a", "b"]},
        "inn": {"mode": "annexes", "rooms": ["c"]}}


def test_siblings_on_a_street_long_enough_are_laid_side_by_side():
    scene, specs, ids = _row_on_a_lane((20, 3), siblings=2)
    assert _plane_rows_naming(scene, ids[1:])          # stacked before
    report = lay_frontages(scene, specs)
    assert report[0]["placed"] == ids[1:] and report[0]["unplaced"] == []
    runs = _runs(scene, "lane", ids)
    assert all(a[1] <= b[0] for a, b in zip(runs, runs[1:]))   # side by side
    assert all(0 <= start and end <= 20 for start, end in runs)
    assert _plane_rows_naming(scene, ids) == []
    # A ROOM GIVEN ITS PLACE KEEPS IT: the second pass finds nothing waiting.
    before = copy.deepcopy(scene)
    assert lay_frontages(scene, specs) == []
    assert scene == before


def test_a_bearing_a_hand_declared_is_never_moved():
    """The lane's north side holds the house and nothing more. The siblings'
    bearing was the establish's, not the plan's, so they are not carried to
    the far side: they are left where they stand and reported."""
    scene, specs, ids = _row_on_a_lane((6, 3), siblings=2)
    report = lay_frontages(scene, specs)
    assert report[0]["unplaced"] == ids[1:] and report[0]["far_side"] == []
    assert report[0]["short"] == 12
    for rid in ids[1:]:
        assert {e["dir"] for e in scene["rooms"][rid]["adjacent"]} == {"s"}


def test_the_plans_own_bearing_may_take_the_far_side_of_the_street():
    """Where the sibling's bearing is still the plan's copy of its parent's,
    it is the closure's, and the other side of a full street is free."""
    scene, specs, ids = _row_on_a_lane((6, 3), siblings=1, plan_dir="s")
    report = lay_frontages(scene, specs)
    assert report[0]["far_side"] == ["house_2"] and report[0]["unplaced"] == []
    sibling = scene["rooms"]["house_2"]
    assert [e["dir"] for e in sibling["adjacent"]] == ["n"]
    assert next(e["dir"] for e in scene["rooms"]["lane"]["adjacent"]
                if e["to"] == "house_2") == "s"
    assert _plane_rows_naming(scene, ids) == []


def test_a_developed_street_keeps_its_doorways_where_its_author_put_them():
    scene, specs, ids = _row_on_a_lane(
        (20, 3), siblings=2, lane_desc="A plank walk on piles.")
    lane_doors = copy.deepcopy(scene["rooms"]["lane"]["adjacent"])
    lay_frontages(scene, specs)
    assert scene["rooms"]["lane"]["adjacent"] == lane_doors


def test_a_street_nobody_measured_is_lengthened_and_a_measured_one_never():
    """The owner ruled on 2026-10-08: "unmeasured stubs only". The six
    paces an unmeasured street is drawn as are the engine's default, and
    lengthening it changes nobody's measurement; a street the Room
    measured keeps its length."""
    assert FRONTAGE_MEASURES_STREETS is True
    on, specs, ids = _row_on_a_lane(None, siblings=2)
    off = copy.deepcopy(on)
    report = lay_frontages(on, specs)
    assert report[0]["measured"] and report[0]["unplaced"] == []
    assert on["rooms"]["lane"]["extent"]["w"] == 18
    assert _plane_rows_naming(on, ids) == []
    report = lay_frontages(off, specs, measure_streets=False)
    assert "extent" not in off["rooms"]["lane"]
    assert report[0]["unplaced"] == ids[1:]
    # A street the plan measured is the Room's measurement, and stays.
    measured, specs, ids = _row_on_a_lane((6, 3), siblings=2)
    report = lay_frontages(measured, specs)
    assert measured["rooms"]["lane"]["extent"] == {"w": 6, "d": 3}
    assert not report[0]["measured"]
    # And so does one a story has entered: it is no longer the plan's stub.
    entered, specs, ids = _row_on_a_lane(None, siblings=2,
                                         lane_desc="A plank walk on piles.")
    report = lay_frontages(entered, specs)
    assert "extent" not in entered["rooms"]["lane"]
    assert not any(row.get("measured") for row in report)
    # And so does one a hand sized: a size tier somebody wrote is a
    # measurement too, never overridden (review B3).
    for tier in ("small", "medium", "large"):
        sized, specs, ids = _row_on_a_lane(None, siblings=2)
        sized["rooms"]["lane"]["size"] = tier
        report = lay_frontages(sized, specs)
        assert "extent" not in sized["rooms"]["lane"], tier
        assert not any(row.get("measured") for row in report), tier


def test_annexes_take_walls_no_other_doorway_uses():
    rooms = {
        "inn": _stub("the Inn", (6, 6), exposure="enclosed"),
        "quay": _stub("the Quay", (10, 4), exposure="open"),
        "inn_2": _stub("the Inn 2"), "inn_3": _stub("the Inn 3")}
    rooms["inn"]["adjacent"] = [{"to": "quay", "barrier": "open_door", "dir": "s"},
                                {"to": "inn_2", "barrier": "open_door"},
                                {"to": "inn_3", "barrier": "open_door"}]
    rooms["quay"]["adjacent"] = [{"to": "inn", "barrier": "open_door", "dir": "n"}]
    for rid in ("inn_2", "inn_3"):
        rooms[rid]["adjacent"] = [{"to": "inn", "barrier": "open_door"}]
    specs = {rid: {"name": rid, "adjacent": [dict(e) for e in room["adjacent"]]}
             for rid, room in rooms.items()}
    for rid in ("inn_2", "inn_3"):
        specs[rid][ANNEX_OF] = "inn"
    scene = {"rooms": rooms, "entities": {}, "positions": {}}
    report = lay_frontages(scene, specs)
    assert report[0]["placed"] == ["inn_2", "inn_3"]
    walls = {_span(scene, "inn", rid)[0] for rid in ("inn_2", "inn_3")}
    assert "s" not in walls
    for rid in ("inn_2", "inn_3"):
        here = _span(scene, "inn", rid)[0]
        assert scene["rooms"][rid]["adjacent"][0]["dir"] == {
            "n": "s", "s": "n", "e": "w", "w": "e"}[here]
    assert _plane_rows_naming(scene, ["inn_2", "inn_3"]) == []
    # A workplace with a doorway nobody has walled yet could be using any
    # wall, so its annexes wait rather than take one.
    waiting = copy.deepcopy(scene)
    for rid in ("inn_2", "inn_3"):
        for edge in waiting["rooms"][rid]["adjacent"]:
            edge.pop("dir", None)
            edge.pop("offset", None)
        for edge in waiting["rooms"]["inn"]["adjacent"]:
            if edge["to"] == rid:
                edge.pop("dir", None)
                edge.pop("offset", None)
    waiting["rooms"]["inn"]["adjacent"][0].pop("dir")
    waiting["rooms"]["quay"]["adjacent"][0].pop("dir")
    report = lay_frontages(waiting, specs)
    assert report[0]["waiting_on_walls"] and report[0]["placed"] == []
    assert all("dir" not in e for e in waiting["rooms"]["inn_2"]["adjacent"])


def test_a_parent_with_no_wall_leaves_its_siblings_where_nobody_put_them():
    """Chat 166's pile houses: neither the parent nor its siblings has a
    bearing onto either walk, so there is no wall to front and nothing to
    lay -- the frontage never invents the parent's place."""
    scene, specs, ids = _row_on_a_lane((20, 3), siblings=2)
    for room in scene["rooms"].values():
        for edge in room["adjacent"]:
            edge.pop("dir", None)
            edge.pop("offset", None)
    before = copy.deepcopy(scene)
    assert lay_frontages(scene, specs) == []
    assert scene == before


def test_the_fringe_lays_a_split_room_the_beat_its_street_gets_a_wall(temp_db):
    import time
    from world.structure import materialize_planned_fringe, plant_structure
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Frontage", "", time.time()))
    scene, specs, ids = _row_on_a_lane((20, 3), siblings=2)
    plant_structure(cid, {"key": "row", "name": "Row", "max_planned": 20},
                    {rid: dict(spec, purpose="homes") for rid, spec in specs.items()})
    scene["positions"] = {"Player": "lane"}
    assert _plane_rows_naming(scene, ids[1:])
    scene, _added = materialize_planned_fringe(cid, scene)
    assert _plane_rows_naming(scene, ids) == []


def _house_with_a_side_room(*, sibling_shed_walled=False):
    """The review's own shape (2026-10-08, M4): a lane; the House on its
    north side; a Shed laid through the House's east wall; and the House's
    sibling, its lane door walled by a hand and stacked on the House, its
    copy of the shed doorway unwalled. Every stretch of the lane's north
    wall clear of the House is where the Shed stands."""
    rooms = {"lane": _stub("the Lane", (20, 3), exposure="open"),
             "house": _stub("the House", (6, 5), exposure="enclosed"),
             "house_2": _stub("the House 2", (6, 5), exposure="enclosed"),
             "shed": _stub("the Shed", (6, 5), exposure="enclosed")}

    def link(a, b, a_dir=None):
        back = {"n": "s", "s": "n", "e": "w", "w": "e", None: None}[a_dir]
        ea, eb = {"to": b, "barrier": "open_door"}, {"to": a, "barrier": "open_door"}
        if a_dir:
            ea["dir"], eb["dir"] = a_dir, back
        rooms[a]["adjacent"].append(ea)
        rooms[b]["adjacent"].append(eb)

    link("lane", "house", "n")
    link("house", "shed", "e")
    link("lane", "house_2", "n")
    link("house_2", "shed", "e" if sibling_shed_walled else None)
    scene = {"rooms": rooms, "entities": {}, "positions": {}}
    normalize_scene_bearings(scene)
    for edge in scene["rooms"]["lane"]["adjacent"]:
        edge["offset"] = 0.3            # stacked, as chat 165's copies were
    specs = {"lane": {"name": "the Lane", "adjacent": []},
             "house": {"name": "the House",
                       "adjacent": [{"to": "lane"}, {"to": "shed"}]},
             "shed": {"name": "the Shed",
                      "adjacent": [{"to": "house"}, {"to": "house_2"}]},
             "house_2": {"name": "the House 2", SPLIT_OF: "house",
                         "adjacent": [{"to": "lane"}, {"to": "shed"}]}}
    return scene, specs


def _overlapping(scene):
    return sorted({tuple(sorted(row["rooms"])) for row in room_layout_lint(scene)
                   if row["kind"] == "rooms_overlap_when_placed"})


def test_a_room_is_never_moved_onto_a_room_laid_through_another_doorway():
    """The lane's wall is free east of the House, and the Shed stands there:
    the sibling is left where it stands and reported, never moved onto it."""
    scene, specs = _house_with_a_side_room()
    before = copy.deepcopy(scene)
    assert _overlapping(scene) == [("house", "house_2")]
    report = lay_frontages(scene, specs)
    assert report[0]["placed"] == [] and report[0]["unplaced"] == ["house_2"]
    assert scene == before
    assert _overlapping(scene) == [("house", "house_2")]
    # Nothing was pinned, so the next pass looks again.
    assert lay_frontages(scene, specs)[0]["unplaced"] == ["house_2"]


def test_a_room_alone_on_its_wall_but_standing_on_another_is_not_pinned():
    """Alone along the lane is not alone on the plane: a sibling standing on
    the Shed is not written down where it stands."""
    scene, specs = _house_with_a_side_room()
    for edge in scene["rooms"]["lane"]["adjacent"]:
        if edge["to"] == "house_2":
            edge["offset"] = 0.6        # clear of the House, on the Shed
    assert ("house_2", "shed") in _overlapping(scene)
    report = lay_frontages(scene, specs)
    assert "house_2" not in report[0]["placed"]
    assert all("offset" not in edge
               for edge in scene["rooms"]["house_2"]["adjacent"])


def test_a_move_that_lands_on_a_room_is_taken_back(monkeypatch):
    """The plane, read again after everything moved, is the last word: a
    placement the choice let through is put back and reported."""
    from world import frontage
    monkeypatch.setattr(frontage._Plane, "clear",
                        lambda self, rid, shift, axis, ignore: True)
    scene, specs = _house_with_a_side_room()
    before = copy.deepcopy(scene)
    report = lay_frontages(scene, specs)
    assert report[0]["lands_on_a_room"] == ["house_2"]
    assert report[0]["placed"] == [] and report[0]["unplaced"] == ["house_2"]
    assert scene == before


def test_a_street_measured_onto_a_room_is_measured_back():
    """Measuring a street longer lays its rooms side by side and moves what
    stands through its other walls: where that puts a room on a room, the
    measurement is taken back whole."""
    scene, specs = _house_with_a_side_room()
    scene["rooms"]["lane"].pop("extent")             # nobody measured it
    for edge in scene["rooms"]["lane"]["adjacent"]:
        edge.pop("offset", None)
    report = lay_frontages(copy.deepcopy(scene), specs, measure_streets=True)
    assert not report[0]["measured"] and report[0]["unplaced"] == ["house_2"]
    # Refused before anything was laid, not laid and then put back.
    assert "lands_on_a_room" not in report[0]
    measured = copy.deepcopy(scene)
    lay_frontages(measured, specs, measure_streets=True)
    assert "extent" not in measured["rooms"]["lane"]
    assert _overlapping(measured) == _overlapping(scene)


def test_a_sibling_fronts_the_street_its_own_door_is_walled_onto():
    """The House fronts a lane and a garden, and its sibling copied both
    doorways. Walled onto neither, which one it stands on is a choice and is
    left and reported; walled onto the lane by a hand, it is the lane."""
    def scene_of(lane_dir):
        rooms = {"lane": _stub("the Lane", (30, 3), exposure="open"),
                 "house": _stub("the House", (6, 5), exposure="enclosed"),
                 "house_2": _stub("the House 2", (6, 5), exposure="enclosed"),
                 "garden": _stub("the Garden", (6, 5), exposure="open")}
        for a, b, a_dir in (("lane", "house", "n"), ("house", "garden", "e"),
                            ("lane", "house_2", lane_dir),
                            ("house_2", "garden", None)):
            back = {"n": "s", "e": "w", None: None}[a_dir]
            ea, eb = {"to": b, "barrier": "open_door"}, {"to": a, "barrier": "open_door"}
            if a_dir:
                ea["dir"], eb["dir"] = a_dir, back
            rooms[a]["adjacent"].append(ea)
            rooms[b]["adjacent"].append(eb)
        scene = {"rooms": rooms, "entities": {}, "positions": {}}
        normalize_scene_bearings(scene)
        specs = {rid: {"name": rid, "adjacent": [{"to": e["to"]}
                                                 for e in room["adjacent"]]}
                 for rid, room in rooms.items()}
        specs["house_2"][SPLIT_OF] = "house"
        return scene, specs

    scene, specs = scene_of(None)
    before = copy.deepcopy(scene)
    report = lay_frontages(scene, specs)
    assert [row["unplaced"] for row in report] == [["house_2"]]
    assert report[0]["streets"] == {"house_2": ["garden", "lane"]}
    assert scene == before
    walled, specs = scene_of("n")
    report = lay_frontages(walled, specs)
    assert [(row["street"], row["placed"]) for row in report] == [
        ("lane", ["house_2"])]
    assert _span(walled, "garden", "house_2") is None
    assert _overlapping(walled) == []


def _a_longer_lane(house_at, sibling_at):
    scene, specs = _house_with_a_side_room()
    scene["rooms"]["lane"]["extent"] = {"w": 30, "d": 3}
    for edge in scene["rooms"]["lane"]["adjacent"]:
        edge["offset"] = sibling_at if edge["to"] == "house_2" else house_at
    return scene, specs


def test_a_sibling_is_laid_at_the_nearest_run_the_plane_leaves_clear():
    """The House stands at the lane's west end and the Shed beside it: the
    nearest stretch of wall is where the Shed stands, so the sibling is laid
    past it -- not on it, and not left stacked because the first run failed."""
    scene, specs = _a_longer_lane(0.0, 0.0)
    report = lay_frontages(scene, specs)
    assert report[0]["placed"] == ["house_2"]
    assert _overlapping(scene) == []
    assert _span(scene, "lane", "house_2")[1] > _span(scene, "lane", "house")[2]


def test_a_room_alone_on_its_wall_but_on_another_is_moved_clear():
    """Alone along the lane and standing on the Shed: the sibling is moved to
    a stretch the plane leaves clear rather than written down where it is."""
    scene, specs = _a_longer_lane(0.3, 0.6)
    assert _overlapping(scene) == [("house_2", "shed")]
    report = lay_frontages(scene, specs)
    assert report[0]["placed"] == ["house_2"]
    assert _overlapping(scene) == []


def _lane_of(lane_w=6, house_w=3, siblings=2):
    """A lane `lane_w` paces long, measured; the House and its siblings,
    each `house_w` wide, walled north-south by a hand, spread along the
    wall by the merge's own doorway spread."""
    rooms = {"lane": _stub("the Lane", (lane_w, 3), exposure="open")}
    specs = {"lane": {"name": "the Lane", "adjacent": []}}
    for rid in ["house"] + [f"house_{n}" for n in range(2, siblings + 2)]:
        rooms[rid] = _stub(rid, (house_w, 5), exposure="enclosed")
        rooms[rid]["adjacent"].append({"to": "lane", "barrier": "open_door", "dir": "s"})
        rooms["lane"]["adjacent"].append({"to": rid, "barrier": "open_door", "dir": "n"})
        specs[rid] = {"name": rid, "adjacent": [{"to": "lane", "barrier": "open_door"}]}
        if rid != "house":
            specs[rid][SPLIT_OF] = "house"
    scene = {"rooms": rooms, "entities": {}, "positions": {}}
    normalize_scene_bearings(scene)
    return scene, specs


def test_a_sibling_the_pass_leaves_where_it_stands_is_in_the_way():
    """Review N2: a sibling still standing where the doorway spread put it
    was no obstacle to the take-back, so house_2 was moved from (1,4) onto
    house_3 at (3,6), reported placed, and pinned there for good."""
    scene, specs = _lane_of()
    assert _runs(scene, "lane", ["house", "house_2", "house_3"]) == [
        (0, 3), (1, 4), (3, 6)]
    before = copy.deepcopy(scene)
    report = lay_frontages(scene, specs)
    assert report[0]["placed"] == [] and report[0]["far_side"] == []
    assert sorted(report[0]["unplaced"]) == ["house_2", "house_3"]
    assert all("offset" not in edge
               for edge in scene["rooms"]["house_2"]["adjacent"])
    # Nothing it could not keep is left moved: the House was slid along its
    # wall only to make room for the two beside it.
    assert scene == before


def test_a_parent_moved_for_its_siblings_goes_back_when_none_of_them_stays():
    """A twelve-pace lane, the House and four siblings three paces wide: the
    House was slid to the lane's end to make room for a block of three of
    them, the fourth stood where the block was laid, and every one of the
    block went back -- leaving the House moved, and pinned, for nobody."""
    scene, specs = _lane_of(12, 3, siblings=4)
    ids = ["house"] + [f"house_{n}" for n in range(2, 6)]
    assert _runs(scene, "lane", ids)[0] == (1, 4)
    before = copy.deepcopy(scene)
    report = lay_frontages(scene, specs)
    assert report[0]["placed"] == [] and report[0]["far_side"] == []
    assert scene == before


def test_a_wall_with_no_free_run_is_not_read_from_the_plane(monkeypatch):
    """Review N3: the plane was read before every change of wall and marked
    stale on the next line, twelve reads and half a second a commit on chat
    165 while its siblings waited, for nothing placed. The plane is read
    only once a run along a wall is free."""
    from world import frontage
    reads = []
    real = frontage._Plane._read
    monkeypatch.setattr(frontage._Plane, "_read",
                        lambda self: (reads.append(1), real(self))[1])
    scene, specs, ids = _row_on_a_lane((6, 3), siblings=2)
    # A quay fills the lane's far side, and the siblings' doorways onto the
    # lane are still the plan's: no wall to take, near side or far.
    scene["rooms"]["quay"] = _stub("the Quay", (6, 5), exposure="open")
    scene["rooms"]["quay"]["adjacent"].append(
        {"to": "lane", "barrier": "open_door", "dir": "n"})
    scene["rooms"]["lane"]["adjacent"].append(
        {"to": "quay", "barrier": "open_door", "dir": "s"})
    for rid in ids[1:]:
        for edge in scene["rooms"][rid]["adjacent"]:
            edge.pop("dir", None)
            edge.pop("offset", None)
        for edge in scene["rooms"]["lane"]["adjacent"]:
            if edge["to"] == rid:
                edge.pop("dir", None)
                edge.pop("offset", None)
    before = copy.deepcopy(scene)
    report = lay_frontages(scene, specs)
    assert report[0]["placed"] == [] and report[0]["far_side"] == []
    assert reads == []
    assert scene == before


def _a_shed_beside_a_short_house():
    """The review's constructed case (N5): an unmeasured lane, the House
    three paces wide and its sibling four, both stacked at the lane's west
    end, and a two-pace shed off the House's east wall."""
    scene, specs = _house_with_a_side_room()
    scene["rooms"]["lane"].pop("extent")
    scene["rooms"]["house"]["extent"] = {"w": 3, "d": 5}
    scene["rooms"]["house_2"]["extent"] = {"w": 4, "d": 5}
    scene["rooms"]["shed"]["extent"] = {"w": 2, "d": 2}
    for edge in scene["rooms"]["lane"]["adjacent"]:
        edge["offset"] = 0.0
    return scene, specs


def test_a_measurement_whose_room_would_stand_on_a_room_is_never_made():
    """Review N5: the sibling already touched the shed by a column, so
    laying it onto the shed was no NEW touch; it was put back afterwards
    and the lane kept the length measured for it."""
    scene, specs = _a_shed_beside_a_short_house()
    before = copy.deepcopy(scene)
    report = lay_frontages(scene, specs, measure_streets=True)
    assert not report[0]["measured"]
    assert report[0]["unplaced"] == ["house_2"]
    # Never made: no room was laid onto the shed, so none had to go back.
    assert "lands_on_a_room" not in report[0]
    assert "extent" not in scene["rooms"]["lane"]
    assert scene == before


def test_a_measurement_goes_back_whole_with_any_room_it_laid():
    """And where a room a measurement laid is put back afterwards -- another
    room returned onto it -- the street goes back to its own length and
    every doorway the measurement wrote with it."""
    from world import frontage
    scene, specs = _a_shed_beside_a_short_house()
    snapshot = {rid: copy.deepcopy(room["adjacent"])
                for rid, room in scene["rooms"].items()}
    extents = {rid: ("extent" in room, copy.deepcopy(room.get("extent")))
               for rid, room in scene["rooms"].items()}
    before = copy.deepcopy(scene)
    laid = frontage._measure_street(scene, specs, "lane", "n",
                                    ["house", "house_2"])
    assert laid == ["house", "house_2"] and "extent" in scene["rooms"]["lane"]
    row = {"parent": "house", "mode": "siblings", "street": "lane",
           "wall": "n", "placed": ["house_2"], "far_side": [],
           "measured": True, "unplaced": [], "short": 0,
           "moved": ["house", "house_2"], "laid_by_measure": laid}
    frontage._take_back(scene, frontage._Plane(scene), [row], snapshot,
                        extents)
    assert not row["measured"] and row["unplaced"] == ["house_2"]
    assert scene == before
