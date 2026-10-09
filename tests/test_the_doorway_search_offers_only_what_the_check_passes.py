"""The doorway search offers only walls the designer's own check passes
(`director_rooms._doorways_that_fit`, `world/spatial_lint.leaf_rows`).

The check lays the rooms out by their bearings in walks (`layout_rooms`):
each connected part from its smallest id, breadth first, a room landing on
one already laid being a collision. A new room joined by one doorway adds
itself and nothing else -- but only where the walks say so. Round one of
2026-10-08 took every row naming the new place for the whole of what it
adds, and its search offered walls the designer's check then refused with
a row about two standing rooms that no refit could clear. Measured on that
day's play database by the round's review: 7 of chat 160 turn 13's 33
walls, every free wall of the corridor the walk could not place; 20 of the
three rooms chat 166's town never places, 24 with a place id sorting first.

The two towns below have the shapes that did it: a house the walk cannot
place beside a lane (`TOWN`), and a yard where a new shed meets the place a
collided hut would have taken before the room that hut was named against
(`YARD`).
"""

from __future__ import annotations

import time

from agents import director_rooms
from world.spatial import (layout_index, layout_row_key, leaf_rows,
                           merge_scene_with_diff, room_layout_lint)


def _room(name, w, d, *edges):
    return {"name": name, "desc": f"{name}.", "extent": {"w": w, "d": d},
            "adjacent": [{"to": to, "barrier": "open_door", "dir": way} for to, way in edges]}


#: The square's walk lays the north lane, the east lane, then the east house
#: off the north lane -- and the north house, off the east lane, lands on the
#: north lane: a standing collision, and a house no walk places.
TOWN = {
    "b_square": _room("the square", 6, 6, ("c_lane", "n"), ("d_lane", "e")),
    "c_lane": _room("the north lane", 6, 6, ("e_house", "e")),
    "d_lane": _room("the east lane", 6, 6, ("f_house", "n")),
    "e_house": _room("the east house", 6, 6),
    "f_house": _room("the north house", 6, 6),
}
#: The hut, off the shed row, lands on the alley: standing. A shed laid west
#: of the alley before the hut is tried takes some of the hut's would-be
#: cells, and sorts before the alley, so the collision now names the shed.
YARD = {
    "b_sq": _room("the yard", 6, 12, ("m_a", "n"), ("p_h", "w")),
    "m_a": _room("the alley", 6, 4),
    "p_h": _room("the shed row", 8, 4, ("q_x", "n")),
    "q_x": _room("the hut", 4, 4),
}
SHED = {"name": "the shed", "size": "small", "shape": "rectangle"}


def _world(rooms):
    return merge_scene_with_diff({"rooms": {}, "positions": {}}, {"rooms": rooms})


def _held_against(scene, rid, record):
    """The rows the designer's check holds against a draft of `rid` alone,
    but those about its own interior (the designer's to arrange)."""
    rows = []
    director_rooms._check(scene, {"rooms": {rid: record}, "remove_rooms": [],
                                  "remove_adjacent": []}, [rid], rows_out=rows)
    return [row for row in rows if row.get("room") != rid]


def _every_offer_passes(scene, rid, fits, shapes):
    for fit in fits:
        edge = {"to": fit["to"], "barrier": "open", "dir": fit["dir"]}
        for shape in shapes:
            record = dict(shape, desc="A shed.", adjacent=[edge])
            assert not _held_against(scene, rid, record), (rid, fit, shape)


def test_no_wall_of_a_room_the_walk_could_not_place_is_offered():
    """A doorway onto the north house starts a walk of its own through it,
    which re-lays the town in another order and reports the standing
    collision afresh, reversed: no wall of it can come back clean."""
    scene = _world(TOWN)
    assert [row["rooms"] for row in room_layout_lint(scene)
            if row["kind"] == "rooms_overlap_when_placed"] == [["f_house", "c_lane"]]
    for wall, mine in (("n", "s"), ("e", "w"), ("w", "e")):
        record = dict(SHED, desc="A shed.", adjacent=[
            {"to": "f_house", "barrier": "open", "dir": mine}])
        assert _held_against(scene, "zzz_shed", record), wall
    for rid in ("c_shed", "zzz_shed"):
        fits = director_rooms._doorways_that_fit(scene, rid, SHED, sorted(scene["rooms"]),
                                                 time.time() + 60)
        assert fits and not any(fit["to"] == "f_house" for fit in fits)
        _every_offer_passes(scene, rid, fits, director_rooms._trial_shapes(SHED))


def test_a_place_whose_id_sorts_first_is_judged_by_the_walk_it_starts():
    """`a_shed` sorts before the square, so a doorway onto the east lane
    starts the town's walk at the shed and lays the north house before the
    east house: the collision comes back about two other rooms. `zzz_shed`
    joins the square's walk and fits the east lane."""
    scene = _world(TOWN)
    late = director_rooms._doorways_that_fit(scene, "zzz_shed", SHED, sorted(scene["rooms"]),
                                             time.time() + 60)
    early = director_rooms._doorways_that_fit(scene, "a_shed", SHED, sorted(scene["rooms"]),
                                              time.time() + 60)
    assert any(fit["to"] == "d_lane" for fit in late)
    assert early and not any(fit["to"] == "d_lane" for fit in early)
    _every_offer_passes(scene, "a_shed", early, director_rooms._trial_shapes(SHED))


def test_a_collision_the_new_room_now_meets_first_names_it():
    """A collision names the first room in sorted order its room would land
    on; a new room laid before the collision is tried, and sorting before
    the room it named, is now that room -- a row naming the new room that no
    layout of the rest shows. Tried as drafted (the refit path, one shape),
    the alley's west wall was offered and the check then refused it."""
    scene = _world(YARD)
    assert [(row["rooms"], row["via"]) for row in room_layout_lint(scene)
            if row["kind"] == "rooms_overlap_when_placed"] == [(["q_x", "m_a"], "p_h")]
    shed = {"name": "the shed", "desc": "A shed.", "extent": {"w": 6, "d": 4}}
    trial = dict(scene, rooms=dict(scene["rooms"], c_r=dict(shed, adjacent=[
        {"to": "m_a", "barrier": "open", "dir": "e"}])))
    rows = leaf_rows(trial, "c_r", "m_a", layout_index(scene))
    assert ["q_x", "c_r"] in [row.get("rooms") for row in rows]
    assert ["q_x", "c_r"] in [row.get("rooms") for row in
                              room_layout_lint(trial, prev_scene=scene)]
    draft = {"rooms": {"c_r": dict(shed)}, "remove_rooms": [], "remove_adjacent": []}
    fits = director_rooms._doorways_that_fit(scene, "c_r", None, ["m_a", "b_sq", "p_h"],
                                             time.time() + 60, draft=draft)
    offered = {(fit["to"], fit["dir"]) for fit in fits}
    assert ("m_a", "e") not in offered
    assert ("m_a", "w") in offered and ("m_a", "s") in offered
    _every_offer_passes(scene, "c_r", fits, [shed])


def test_the_walks_answer_as_the_whole_check_does_or_not_at_all():
    """`leaf_rows`, read against the walks once, gives the whole check's
    verdict on every wall, shape and id -- or None, and the whole check
    answers; it never answers differently."""
    for rooms in (TOWN, YARD):
        scene = _world(rooms)
        index = layout_index(scene)
        standing = {layout_row_key(row) for row in room_layout_lint(scene)}
        judged = 0
        for rid in ("a_shed", "c_shed", "zzz_shed"):
            for host in sorted(scene["rooms"]):
                for mine in ("n", "e", "s", "w", "ne", "se", "sw", "nw"):
                    for shape in director_rooms._trial_shapes(SHED):
                        record = dict(shape, adjacent=[{"to": host, "barrier": "open",
                                                        "dir": mine}])
                        trial = dict(scene, rooms=dict(scene["rooms"], **{rid: record}))
                        rows = leaf_rows(trial, rid, host, index)
                        if rows is None:
                            continue
                        judged += 1
                        whole = [row for row in room_layout_lint(trial)
                                 if row.get("room") != rid
                                 and layout_row_key(row) not in standing]
                        said = any(row.get("room") != rid for row in rows)
                        assert said == bool(whole), (rid, host, mine, shape, rows, whole)
        assert judged


def test_the_walks_do_not_judge_a_place_another_room_already_names():
    """A standing room whose doorway already names the place gives it a
    second way in: not a leaf, so the whole check decides."""
    rooms = dict(TOWN, e_house=_room("the east house", 6, 6, ("zzz_shed", "e")))
    scene = _world(rooms)
    record = dict(SHED, adjacent=[{"to": "b_square", "barrier": "open", "dir": "n"}])
    trial = dict(scene, rooms=dict(scene["rooms"], zzz_shed=record))
    assert leaf_rows(trial, "zzz_shed", "b_square", layout_index(scene)) is None


def test_a_bearing_the_worlds_own_merge_drops_refuses_no_wall():
    """A lift docked in its shaft opens only from its car; the merge strips
    the hall's stale doorway onto the car whatever else it is given. Judged
    against the world as stored, that was a bearing every trial "lost", and
    the search offered no wall anywhere -- both places chat 160's turn 2
    asked about got none. Judged against the world as the merge holds it,
    the hall and the shaft have walls, and each passes the check."""
    scene = {"rooms": {
        "hall": {"name": "the hall", "desc": "A hall.", "extent": {"w": 8, "d": 4},
                 "adjacent": [{"to": "car", "barrier": "closed_door", "dir": "w"}]},
        "car": {"name": "the lift car", "desc": "A lift car.", "extent": {"w": 4, "d": 4},
                "parent_entity": "lift"},
        "shaft": {"name": "the shaft", "desc": "A shaft.", "extent": {"w": 4, "d": 4}}},
        "entities": {"lift": {"name": "Lift", "kind": "vehicle", "container": True,
                              "interior_rooms": ["car"], "state": {"transit": {
                                  "phase": "docked", "hatch": "closed",
                                  "destination_room": None, "route_room": "shaft"}}}},
        "positions": {"lift": "shaft"}}
    held = merge_scene_with_diff(scene, {"rooms": {}})
    assert not held["rooms"]["hall"].get("adjacent"), "the merge strips it on its own"
    fits = director_rooms._doorways_that_fit(scene, "shed", SHED, ["hall", "shaft"],
                                             time.time() + 60)
    assert {fit["to"] for fit in fits} == {"hall", "shaft"}
    _every_offer_passes(scene, "shed", fits, director_rooms._trial_shapes(SHED))


# ---- seeded random towns (round two's review, 2026-10-09) ------------------
#
# Two towns from a seeded random-town generator (`_seeded_town` below; seed 2,
# the tenth and the second), each the shape one branch of `leaf_rows` exists
# for. Neither shape is in the two towns above, and with either branch taken
# out every test above still passed.

def _r(rid, w, d, *edges, **more):
    """A room of a seeded town: named for its id, its edges `(to, barrier,
    dir[, vertical])`."""
    return dict({"name": rid.replace("_", " "), "desc": rid + ".", "extent": {"w": w, "d": d},
                 "adjacent": [dict({"to": e[0], "barrier": e[1], "dir": e[2]},
                                   **({"vertical": e[3]} if len(e) > 3 else {}))
                              for e in edges]}, **more)


#: The walk from `be_lane` places only three rooms -- the east lane collides
#: on `ma_room`, the north lane on `bl_room` -- and `xz_hall`'s walk lays the
#: whole town. A shed `knz_x` sorts after both lanes and before `xz_hall`:
#: joined to either lane it starts a walk of its own, which re-lays the town
#: from that lane and reports a standing collision afresh.
SORTS_FIRST = {
    "be_lane": _r("be_lane", 8, 4, ("bl_room", "open_door", "s"), ("lr_lane", "closed_door", "e")),
    "bl_room": _r("bl_room", 8, 9, ("ex_lane", "open_door", "w"), exposure="open"),
    "ex_lane": _r("ex_lane", 3, 2, shape="round"),
    "kn_lane": _r("kn_lane", 7, 4),
    "lr_lane": _r("lr_lane", 6, 5, ("bl_room", "closed_door", "s")),
    "ma_room": _r("ma_room", 6, 6, ("be_lane", "open_door", "n"), ("kn_lane", "closed_door", "e")),
    "xz_hall": _r("xz_hall", 8, 6, ("lr_lane", "closed_door", "w")),
}
#: Three walks: from `at_yard`, from `ip_yard`, and from `pv_hall`, which
#: reaches `at_yard` again. A shed `a_00`, joined to `pv_hall`, sorts before
#: all of them: laid out first, its walk runs through `at_yard` before
#: `at_yard`'s own walk would start, so that walk never runs, and what only
#: it reached is walked again from elsewhere -- which the walks cannot say.
WALK_BETWEEN = {
    "at_yard": _r("at_yard", 8, 3, ("ez_hall", "open_door", "s"),
                  ("gw_room", "closed_door", "w"), ("xx_yard", "open_door", "w")),
    "ez_hall": _r("ez_hall", 3, 3, ("ip_yard", "open_door", "n", "up"),
                  ("jl_yard", "open_door", "e"), ("xx_yard", "open", "w")),
    "gw_room": _r("gw_room", 4, 8),
    "ip_yard": _r("ip_yard", 2, 4, ("mh_lane", "closed_door", "w"), ("jl_yard", "open_door", "e")),
    "jl_yard": _r("jl_yard", 7, 9),
    "mh_lane": _r("mh_lane", 4, 8, exposure="open"),
    "pt_hall": _r("pt_hall", 6, 4, ("mh_lane", "open_door", "w")),
    "pv_hall": _r("pv_hall", 5, 8, ("jl_yard", "wall", "nw")),
    "xx_yard": _r("xx_yard", 4, 9, ("pv_hall", "open_door", "s"), shape="round"),
    "yb_yard": _r("yb_yard", 4, 8, ("gw_room", "open_door", "w")),
}
_EVERY_WALL = ("n", "e", "s", "w", "ne", "se", "sw", "nw")


def _verdicts_agree(scene, rid, shapes, hosts=None):
    """`leaf_rows`' verdict on every wall of every host at every shape is
    the whole check's, or None; returns how many it judged."""
    index = layout_index(scene)
    standing = {layout_row_key(row) for row in room_layout_lint(scene)}
    judged = 0
    for host in hosts or sorted(scene["rooms"]):
        for mine in _EVERY_WALL:
            for shape in shapes:
                record = dict(shape, adjacent=[{"to": host, "barrier": "open", "dir": mine}])
                trial = dict(scene, rooms=dict(scene["rooms"], **{rid: record}))
                rows = leaf_rows(trial, rid, host, index)
                if rows is None:
                    continue
                judged += 1
                whole = [row for row in room_layout_lint(trial)
                         if row.get("room") != rid and layout_row_key(row) not in standing]
                said = any(row.get("room") != rid for row in rows)
                assert said == bool(whole), (rid, host, mine, shape, rows, whole)
    return judged


def test_a_place_that_sorts_before_the_walk_laying_its_host_is_judged_by_its_own():
    """Read as the first room of `xz_hall`'s walk -- the walk that first lays
    its host -- the shed would be judged clean on walls where the walk it
    really starts re-reports a standing collision; the search then offered
    two walls the designer's check refused (round two's review)."""
    scene = _world(SORTS_FIRST)
    index = layout_index(scene)
    record = dict(SHED, adjacent=[{"to": "ex_lane", "barrier": "open", "dir": "ne"}])
    trial = dict(scene, rooms=dict(scene["rooms"], knz_x=record))
    rows = leaf_rows(trial, "knz_x", "ex_lane", index)
    assert rows and ["ma_room", "ex_lane"] in [row.get("rooms") for row in rows]
    assert "ex_lane" in index["from_host"], "judged by the host's own walk"
    shapes = director_rooms._trial_shapes(SHED)
    assert _verdicts_agree(scene, "knz_x", shapes)
    fits = director_rooms._doorways_that_fit(scene, "knz_x", SHED, sorted(scene["rooms"]),
                                             time.time() + 60)
    assert fits
    _every_offer_passes(scene, "knz_x", fits, shapes)


def test_a_place_laid_first_is_not_judged_past_a_walk_it_would_cancel():
    """Read as the first room of `pv_hall`'s own walk, the shed was judged
    clean on its north wall, where the whole check -- `at_yard`'s walk never
    running -- holds a collision no walk of the world reported."""
    scene = _world(WALK_BETWEEN)
    for mine in _EVERY_WALL:
        record = dict(SHED, adjacent=[{"to": "pv_hall", "barrier": "open", "dir": mine}])
        trial = dict(scene, rooms=dict(scene["rooms"], a_00=record))
        assert leaf_rows(trial, "a_00", "pv_hall", layout_index(scene)) is None, mine
    shapes = director_rooms._trial_shapes(SHED)
    assert _verdicts_agree(scene, "a_00", shapes)
    fits = director_rooms._doorways_that_fit(scene, "a_00", SHED, sorted(scene["rooms"]),
                                             time.time() + 60)
    assert fits
    _every_offer_passes(scene, "a_00", fits, shapes)


def _seeded_town(rng):
    """A random town of 4 to 11 rooms: a spanning tree of doorways declared
    from one side, mostly on straight walls, a few up or down, a few at an
    offset, a few through walls, and extra ways besides -- the generator the
    two towns above came from."""
    bearings = ["n", "e", "s", "w", "ne", "se", "sw", "nw"]
    barriers = ["open_door", "closed_door", "open", "open_door", "closed_door", "wall"]
    n = rng.randint(4, 11)
    letters = "abcdefghijklmnopqrstuvwxyz"
    ids = set()
    while len(ids) < n:
        ids.add(rng.choice(letters) + rng.choice(letters) + "_"
                + rng.choice(["room", "lane", "hall", "yard"]))
    ids = sorted(ids)
    rooms = {}
    for rid in ids:
        room = {"name": rid.replace("_", " "), "desc": rid + ".",
                "extent": {"w": rng.randint(2, 9), "d": rng.randint(2, 9)}, "adjacent": []}
        if rng.random() < 0.15:
            room["exposure"] = "open"
        if rng.random() < 0.08:
            room["shape"] = rng.choice(["l", "round"])
        rooms[rid] = room
    for i, rid in enumerate(ids[1:], start=1):
        if rng.random() < 0.85:
            other = ids[rng.randrange(0, i)]
            a, b = (rid, other) if rng.random() < 0.5 else (other, rid)
            edge = {"to": b, "barrier": rng.choice(barriers),
                    "dir": rng.choice(bearings[:4] if rng.random() < 0.85 else bearings)}
            if rng.random() < 0.06:
                edge["vertical"] = rng.choice(["up", "down"])
            if rng.random() < 0.1:
                edge["offset"] = round(rng.random(), 2)
            rooms[a]["adjacent"].append(edge)
    for _ in range(rng.randint(0, n)):
        a, b = rng.sample(ids, 2)
        if any(e["to"] == b for e in rooms[a]["adjacent"]) \
                or any(e["to"] == a for e in rooms[b]["adjacent"]):
            continue
        rooms[a]["adjacent"].append({"to": b, "barrier": rng.choice(barriers),
                                     "dir": rng.choice(bearings[:4])})
    return rooms


def test_the_walks_answer_as_the_whole_check_does_on_seeded_random_towns():
    """Twelve seeded towns, a place id sorting first, one in the middle and
    one last, every wall of every room, at the square its size word gives
    it: `leaf_rows` gives the whole check's verdict or None. With either of
    the two branches above taken out, these towns disagree as well (the
    sort-first one on 7 trials, the walk-between one on 6)."""
    import random
    rng = random.Random(4)
    judged = 0
    for _ in range(12):
        scene = _world(_seeded_town(rng))
        ids = sorted(scene["rooms"])
        for rid in ("a_00", ids[len(ids) // 2][:2] + "z_x", "zzz_shed"):
            if rid in scene["rooms"]:
                continue
            judged += _verdicts_agree(scene, rid, director_rooms._trial_shapes(SHED)[:1])
    assert judged > 1000


#: A seeded town with a way down (seed 21, the second, ways up or down at
#: 0.3): the merge stands the whole group on one site plan, and a shed joined
#: to it is stood on that plan as well.
STOREYS = {
    "cf_yard": _r("cf_yard", 8, 4, ("hd_lane", "open_door", "e"), ("lf_room", "open", "s")),
    "hd_lane": _r("hd_lane", 7, 9, ("vq_lane", "closed_door", "n"),
                  ("lf_room", "closed_door", "s")),
    "lf_room": _r("lf_room", 5, 4),
    "ly_hall": dict(_r("ly_hall", 8, 9, exposure="open"), adjacent=[
        {"to": "hd_lane", "barrier": "closed_door", "dir": "e", "offset": 0.69},
        {"to": "cf_yard", "barrier": "closed_door", "dir": "n"}]),
    "ul_hall": _r("ul_hall", 6, 6, exposure="open"),
    "vq_lane": _r("vq_lane", 8, 3, ("ul_hall", "closed_door", "sw", "down"),
                  ("ly_hall", "closed_door", "n")),
}


def test_a_wall_a_site_plan_makes_good_is_offered():
    """A shed whose doorway is on its south wall into the yard, or on its
    north wall into the room: laid out unmerged, with no site, the walks lay
    it onto another room of the plan. Merged, it stands on the plan beside
    them, which is no collision, and the designer's check passes either wall
    at every shape. Judged by the unmerged screen alone, both were lost
    (round two's review)."""
    from world.site_plan import room_site
    scene = _world(STOREYS)
    assert room_site(scene, "cf_yard") and room_site(scene, "lf_room")
    fits = director_rooms._doorways_that_fit(scene, "a_00", SHED, sorted(scene["rooms"]),
                                             time.time() + 60)
    offered = {(fit["to"], fit["dir"]) for fit in fits}
    assert {("cf_yard", "s"), ("lf_room", "n")} <= offered
    _every_offer_passes(scene, "a_00", fits, director_rooms._trial_shapes(SHED))


def test_a_collision_found_again_reversed_is_the_same_only_on_the_owners_word(monkeypatch):
    """A doorway onto the north house re-lays the town and reports the
    world's own collision reversed. By the whole row -- today's rule -- that
    is a row the world does not hold, and no wall of the house is offered.
    With `LAYOUT_COLLISIONS_COMPARED_BY_PAIR` on, a collision naming the same
    two rooms is the same collision in every comparison the check makes: the
    house's free walls are offered, each one the designer's check passes,
    and the walks still answer as the whole check does."""
    import world.spatial_lint as lint                # the switch's own module
    scene = _world(TOWN)
    record = dict(SHED, desc="A shed.", adjacent=[{"to": "f_house", "barrier": "open",
                                                   "dir": "s"}])
    trial = dict(scene, rooms=dict(scene["rooms"], zzz_shed=record))
    assert lint.LAYOUT_COLLISIONS_COMPARED_BY_PAIR is False
    assert [row["rooms"] for row in room_layout_lint(trial, prev_scene=scene)
            if row.get("room") != "zzz_shed"] == [["c_lane", "f_house"]]
    monkeypatch.setattr(lint, "LAYOUT_COLLISIONS_COMPARED_BY_PAIR", True)
    assert not [row for row in room_layout_lint(trial, prev_scene=scene)
                if row.get("room") != "zzz_shed"]
    shapes = director_rooms._trial_shapes(SHED)
    fits = director_rooms._doorways_that_fit(scene, "zzz_shed", SHED, sorted(scene["rooms"]),
                                             time.time() + 60)
    assert any(fit["to"] == "f_house" for fit in fits)
    _every_offer_passes(scene, "zzz_shed", fits, shapes)
    for rooms, rid in ((TOWN, "a_shed"), (SORTS_FIRST, "knz_x"), (WALK_BETWEEN, "a_00")):
        assert _verdicts_agree(_world(rooms), rid, shapes)
