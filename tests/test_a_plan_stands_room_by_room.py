"""A site plan is derived room by room, from the rooms as they stand, every
merge (`world/site_plan.py`, 2026-10-09).

Measured on the play database's 139 stored scenes before this: 0 of 1,069
rooms carried a site, and one merge left 54 sited -- every town refused its
plan whole on its first clash. The classes found there are pinned here, each
on a hand-made scene; the names are illustrations, never a list the rule
matches. Every test names the rule it pins.
"""
from __future__ import annotations

import copy

from world.site_plan import (DERIVED_KEY, ORIGIN_KEY, _stands_on, derive_site_plans,
                             plan_frames, plan_offset, plan_refusals, room_site,
                             site_is_derived, site_overlaps)
from world.spatial import merge_scene_with_diff, room_field, room_layout_lint


def _room(name, w, d, *edges, level=0, exposure="enclosed", **more):
    return dict({"name": name, "desc": f"{name}.", "level": level, "exposure": exposure,
                 "extent": {"w": w, "d": d}, "adjacent": [dict(e) for e in edges]}, **more)


def _merged(rooms):
    return merge_scene_with_diff({"rooms": {}, "positions": {}, "entities": {}},
                                 {"rooms": copy.deepcopy(rooms)})


def _sited(scene):
    return {rid for rid in scene["rooms"] if room_site(scene, rid)}


#: A two-storey house on a street, and two shops whose doorways the street's
#: south wall holds one pace apart: six paces wide each, they cannot both
#: stand there.
SHOPS = {
    "hall": _room("the hall", 6, 4, {"to": "street", "dir": "s", "barrier": "open_door",
                                     "offset": 0.5},
                  {"to": "loft", "vertical": "up", "barrier": "open", "way": "stair"}),
    "loft": _room("the loft", 6, 4, {"to": "hall", "vertical": "down", "barrier": "open",
                                     "way": "stair"}, level=1),
    "street": _room("the street", 12, 3, {"to": "hall", "dir": "n", "barrier": "open_door",
                                          "offset": 0.5},
                    {"to": "shop_a", "dir": "s", "barrier": "closed_door", "offset": 0.0},
                    {"to": "shop_b", "dir": "s", "barrier": "closed_door", "offset": 0.1},
                    exposure="open"),
    "shop_a": _room("the chandler's", 6, 4, {"to": "street", "dir": "n", "barrier": "closed_door",
                                              "offset": 0.5}),
    "shop_b": _room("the cooper's", 6, 4, {"to": "street", "dir": "n", "barrier": "closed_door",
                                            "offset": 0.5}),
}


def test_one_clash_leaves_one_room_off_the_plan_never_the_whole_group():
    """A town is one connected group, and one clash refused it whole: chat
    166's 32 rooms went without a plan over five pairs. The room that would
    land on a room already laid stands off the plan, and is named; every
    other room stands where its doorways put it."""
    sc = _merged(SHOPS)
    assert _sited(sc) == {"hall", "loft", "street", "shop_a"}
    assert site_overlaps(sc) == []
    assert all(site_is_derived(sc["rooms"][rid]["site"]) for rid in _sited(sc))
    (refusal,) = plan_refusals(sc)
    plan, room, lands_on, misses, via = refusal
    assert (room, lands_on, misses, via) == ("shop_b", ("shop_a",), (), "street")
    assert room_site(sc, "loft")["elev_m"] == 3.0 and room_site(sc, "hall")["elev_m"] == 0.0


#: A walk with an open side onto a staithe, and a house's door at the walk's
#: far end; boat sheds open off the staithe's east side.
STAITHE = {
    "house": _room("the house", 4, 3, {"to": "walk", "dir": "n", "barrier": "closed_door",
                                       "offset": 0.5},
                   {"to": "house_loft", "vertical": "up", "barrier": "open", "way": "stair"}),
    "house_loft": _room("the house loft", 4, 3, {"to": "house", "vertical": "down",
                                                 "barrier": "open", "way": "stair"}, level=1),
    "walk": _room("the walk", 12, 3, {"to": "staithe", "dir": "s", "barrier": "open"},
                  {"to": "house", "dir": "s", "barrier": "closed_door", "offset": 1.0},
                  exposure="open"),
    "staithe": _room("the staithe", 4, 5, {"to": "walk", "dir": "n", "barrier": "open"},
                     {"to": "sheds", "dir": "e", "barrier": "open"}, exposure="open"),
    "sheds": _room("the boat sheds", 6, 5, {"to": "staithe", "dir": "w", "barrier": "open"},
                   exposure="sheltered"),
}


def test_an_open_side_is_laid_where_it_stands_clear_along_its_wall():
    """An open side is the whole of its wall, so where along it the far room
    stands is nobody's measurement: every reader laid it flush with the
    wall's start, and chat 166's boat sheds, drying racks and reed flats each
    landed on a room that way. The plan takes the nearest place along the
    side where the room lands on nothing, and the sight field, which lays a
    neighbour beside its room, lays it where the plan has it."""
    sc = _merged(STAITHE)
    assert _sited(sc) == set(STAITHE) and plan_refusals(sc) == []
    staithe, sheds = room_site(sc, "staithe"), room_site(sc, "sheds")
    assert sheds["y"] - staithe["y"] == 3, "slid three paces south, clear of the house"
    rel = plan_offset(sc, "staithe", "sheds")
    assert rel == (sheds["x"] - staithe["x"], sheds["y"] - staithe["y"])
    field = room_field(sc, "staithe")
    assert field.offsets["sheds"] == (rel[0] + 1, rel[1]), "beyond the one-cell band"
    assert site_overlaps(sc) == []


def test_a_doorway_the_plan_lays_by_is_followed_by_the_field_cell_for_cell():
    """Wherever the plan laid a room by its doorway, following the plan is
    the doorway's own placement: the field's offset is unchanged."""
    sc = _merged(SHOPS)
    field = room_field(sc, "street")
    rel = plan_offset(sc, "street", "hall")
    assert rel is not None and field.offsets["hall"] == (rel[0], rel[1] - 1)
    off = copy.deepcopy(sc)
    for room in off["rooms"].values():
        room.pop("site", None)
    assert room_field(off, "street").offsets["hall"] == field.offsets["hall"]


#: A walk, a landing up a stair from it written on the walk's own storey,
#: and a two-storey house whose door opens onto both.
LANDING = {
    "walk": _room("the low walk", 12, 3,
                  {"to": "landing", "dir": "s", "vertical": "up", "barrier": "open",
                   "way": "stair"},
                  {"to": "house", "dir": "s", "barrier": "closed_door", "offset": 0.9},
                  exposure="open"),
    "landing": _room("the landing", 3, 2,
                     {"to": "walk", "dir": "n", "vertical": "down", "barrier": "open",
                      "way": "stair"},
                     {"to": "house", "barrier": "open_door"}, exposure="open"),
    "house": _room("the house", 6, 5, {"to": "walk", "dir": "n", "barrier": "closed_door"},
                   {"to": "landing", "barrier": "open_door"},
                   {"to": "upstairs", "vertical": "up", "barrier": "open", "way": "stair"}),
    "upstairs": _room("upstairs", 6, 5, {"to": "house", "vertical": "down", "barrier": "open",
                                         "way": "stair"}, level=1),
}


def test_a_stair_between_two_rooms_of_one_storey_is_no_stack():
    """A stair lands over where it left -- between two storeys. Between two
    rooms of one storey it laid the far room on the near one (chat 166's
    Gale house landing on the low walk), and the town had no plan. Such a
    stair places nothing: the landing stands off the plan for want of a
    doorway with a wall, and the rest stands on it."""
    sc = _merged(LANDING)
    assert sc["rooms"]["landing"]["level"] == 0
    assert _sited(sc) == {"walk", "house", "upstairs"}
    assert plan_refusals(sc) == [] and site_overlaps(sc) == []


def test_a_derived_site_follows_the_room_and_a_decided_one_stays():
    """A derived site is the engine's reading of the rooms, recomputed every
    merge: a beat that measures a room has it laid out again where its
    doorway now puts it -- the plan never keeps a guessed square's corner
    under a measured room -- and nothing else moves, a room added later
    included (`ORIGIN_KEY`: the plan is grown again from where it was
    grown). A decided site -- solved, converted, placed by a host -- keeps
    its room's box against a beat, as it always did."""
    sc = _merged(SHOPS)
    before = {rid: dict(sc["rooms"][rid]["site"]) for rid in _sited(sc)}
    assert {s[ORIGIN_KEY] for s in before.values()} == {"hall"}
    sc = merge_scene_with_diff(sc, {"rooms": {"shop_a": {
        "extent": {"w": 4, "d": 4}, "adjacent": [{"to": "street", "offset": 0.0}]}}})
    assert sc["rooms"]["shop_a"]["extent"] == {"w": 4, "d": 4}, "the beat's measurement lands"
    assert room_site(sc, "shop_a")["x"] == before["shop_a"]["x"] + 2, \
        "laid out again where its moved door meets the street's"
    assert plan_offset(sc, "street", "shop_a") is not None
    assert {rid: sc["rooms"][rid]["site"] for rid in ("hall", "loft", "street")} == \
        {rid: before[rid] for rid in ("hall", "loft", "street")}
    leaf = _room("a lean-to", 3, 3, {"to": "hall", "dir": "e", "barrier": "open_door"})
    grown = merge_scene_with_diff(sc, {"rooms": {"a_shed": leaf}})
    assert room_site(grown, "a_shed"), "a room added later is laid out against the plan"
    assert {rid: grown["rooms"][rid]["site"] for rid in ("hall", "loft", "street")} == \
        {rid: before[rid] for rid in ("hall", "loft", "street")}, "and moves nothing on it"
    decided = copy.deepcopy(sc)
    decided["rooms"]["shop_a"]["site"] = {"plan": "town", "x": 30, "y": 30, "elev_m": 0.0}
    decided = merge_scene_with_diff(decided, {"rooms": {"shop_a": {"extent": {"w": 6, "d": 6}}}})
    assert decided["rooms"]["shop_a"]["extent"] == {"w": 4, "d": 4}, "described, never re-measured"
    assert decided["rooms"]["shop_a"]["site"] == {"plan": "town", "x": 30, "y": 30, "elev_m": 0.0}
    # and a second call changes nothing: every room's site, compared, since
    # the ids it returns cannot show a site it took off
    again = copy.deepcopy(grown)
    assert derive_site_plans(again) == []
    assert {rid: room.get("site") for rid, room in again["rooms"].items()} == \
        {rid: room.get("site") for rid, room in grown["rooms"].items()}


#: A yard with a lane east of it and a room south of both, whose two north
#: doorways are at its two ends: no plane holds both.
LOOP = {
    "yard": _room("the yard", 6, 4, {"to": "lane", "dir": "e", "barrier": "open_door",
                                     "offset": 0.5},
                  {"to": "room", "dir": "s", "barrier": "open_door", "offset": 0.0},
                  {"to": "cellar", "vertical": "down", "barrier": "open", "way": "stair"}),
    "lane": _room("the lane", 6, 4, {"to": "yard", "dir": "w", "barrier": "open_door",
                                     "offset": 0.5},
                  {"to": "room", "dir": "s", "barrier": "open_door", "offset": 1.0}),
    "room": _room("the room", 4, 3, {"to": "yard", "dir": "n", "barrier": "open_door",
                                     "offset": 0.0},
                  {"to": "lane", "dir": "n", "barrier": "open_door", "offset": 1.0}),
    "cellar": _room("the cellar", 6, 4, {"to": "yard", "vertical": "up", "barrier": "open",
                                         "way": "stair"}, level=-1),
}


def test_a_room_a_doorway_of_which_would_not_meet_stands_off_the_plan():
    """Every doorway between two rooms on the plan meets across the wall, or
    the plan holds two places for one doorway and the readers that follow it
    have none. Chat 27's shelter declared a descent east of a chamber whose
    east is the passage; laid by one doorway with two left unmet, the layout
    lint's rows about it fell silent once it stood on the plan."""
    sc = _merged(LOOP)
    assert _sited(sc) == {"yard", "lane", "cellar"}
    (refusal,) = plan_refusals(sc)
    assert refusal[1:] == ("room", (), ("yard",), "lane")
    assert plan_offset(sc, "yard", "lane") is not None


def test_a_building_stands_only_on_ground_it_opens_onto():
    """A building stands in its own grounds -- the Larch Hill tower over the
    landing its store room opens onto, the kitchen beside it included -- and
    on no other open ground: chat 166's laid-out town stood a chandlery on
    the drying racks and an inn in the channel, neither opening onto them."""
    rooms = {
        "landing": _room("the landing", 6, 3, {"to": "store", "dir": "n",
                                                "barrier": "open_door"}, exposure="open"),
        "store": _room("the store room", 3, 3, {"to": "landing", "dir": "s",
                                                 "barrier": "open_door"},
                       {"to": "kitchen", "dir": "e", "barrier": "open"}),
        "kitchen": _room("the kitchen", 3, 3, {"to": "store", "dir": "w", "barrier": "open"}),
        "racks": _room("the drying racks", 6, 6, exposure="open"),
        "shop": _room("the chandlery", 4, 4),
    }
    sc = {"rooms": rooms}
    assert _stands_on(sc, "landing", "store") and _stands_on(sc, "kitchen", "landing")
    assert not _stands_on(sc, "racks", "shop") and not _stands_on(sc, "shop", "racks")
    assert not _stands_on(sc, "racks", "landing"), "two grounds still clash"


def test_measured_rooms_and_buildings_are_laid_before_guesses_and_ground():
    """Where two rooms cannot both stand, the one the plan keeps is the one
    somebody measured -- a room with no `extent` is its size tier's square,
    nobody's measurement -- and a building before a stretch of open ground,
    whose loose rectangle is the likelier to be wrong."""
    rooms = copy.deepcopy(SHOPS)
    rooms["a_stub"] = rooms.pop("shop_a")
    rooms["a_stub"].pop("extent")
    for edge in rooms["street"]["adjacent"]:
        if edge["to"] == "shop_a":
            edge["to"] = "a_stub"
    sc = _merged(rooms)
    assert room_site(sc, "shop_b") and not room_site(sc, "a_stub")
    assert [r[1] for r in plan_refusals(sc)] == ["a_stub"]
    ground = copy.deepcopy(SHOPS)
    ground["a_yard"] = ground.pop("shop_a")
    ground["a_yard"]["exposure"] = "open"
    for edge in ground["street"]["adjacent"]:
        if edge["to"] == "shop_a":
            edge.update(to="a_yard", barrier="open_door")
    ground["a_yard"]["adjacent"][0]["barrier"] = "open_door"
    sc = _merged(ground)
    assert room_site(sc, "shop_b") and not room_site(sc, "a_yard"), \
        "the building keeps its ground, the open yard yields"
    assert [r[1] for r in plan_refusals(sc)] == ["a_yard"]


def test_the_room_and_the_host_are_told_what_the_plan_could_not_hold_and_the_designer_is_not():
    """A clash the derivation cannot resolve is said where the Room and the
    host read the world's contradictions -- the Room's
    `inspect_contradictions`, the commit's layout warnings and the World
    Browser ask for it -- and never in the room designer's own check, which
    judges a design by a rule that lays rooms one band apart."""
    from world.spatial import layout_warning
    sc = _merged(SHOPS)
    assert not any(row["kind"] == "site_plan_unplaced" for row in room_layout_lint(sc))
    (row,) = [r for r in room_layout_lint(sc, plan_rows=True) if r["kind"] == "site_plan_unplaced"]
    assert row["room"] == "shop_b" and row["lands_on"] == ["shop_a"]
    text = layout_warning(row)
    assert "the cooper's" in text and "the chandler's" in text and "the street" in text


def test_a_derived_site_keeps_a_planned_building_from_the_tier_only_in_another_solves_frame():
    """The layout tier lays out a planned building no plan holds yet. A site
    the derivation wrote is no plan yet: it is recomputed every merge, and a
    solve laid onto the building's stubs replaces it -- unless it lies on a
    plan another solve holds, where a second solve would pull the ground that
    building opens onto off it. A decided site still keeps the building
    out."""
    from world import layout_bridge as lb
    specs = {
        "hall": ("the Hall", {"purpose": "a hall", "structure": "town", "exposure": "enclosed",
                              "adjacent": [{"to": "street", "dir": "s", "barrier": "closed_door"},
                                           {"to": "loft", "vertical": "up", "way": "stair"}]}),
        "loft": ("the Loft", {"purpose": "a loft", "structure": "town", "exposure": "enclosed",
                              "adjacent": [{"to": "hall", "vertical": "down", "way": "stair"}]}),
        "street": ("the Street", {"purpose": "the street", "structure": "town",
                                  "exposure": "open", "adjacent": [{"to": "hall", "dir": "n"}]}),
    }
    derived = {"plan": "town", "x": 0, "y": 0, "elev_m": 0.0, DERIVED_KEY: True, ORIGIN_KEY: "hall"}
    scene = {"rooms": {"hall": {"name": "the Hall", "planned": True, "site": dict(derived),
                                "adjacent": []},
                       "loft": {"name": "the Loft", "planned": True, "level": 1,
                                "site": dict(derived, elev_m=3.0), "adjacent": []},
                       "street": {"name": "the Street", "desc": "A street.",
                                  "site": dict(derived, y=4),
                                  "adjacent": [{"to": "hall", "dir": "n"}]}},
             "positions": {}, "entities": {}}
    (building,) = lb.plan_buildings(copy.deepcopy(specs), scene)
    assert building["refusal"] is None, building["refusal"]
    # ...unless the plan it was derived onto is another building's solve: a
    # second solve would pull the ground that building opens onto off it.
    held = copy.deepcopy(scene)
    held["rooms"]["inn"] = {"name": "the Inn", "planned": True, "adjacent": [],
                            "site": {"plan": "town", "x": 12, "y": 0, "elev_m": 0.0}}
    (building,) = lb.plan_buildings(copy.deepcopy(specs), held)
    assert "plan already" in building["refusal"]
    for room in scene["rooms"].values():
        room["site"].pop(DERIVED_KEY)
    (building,) = lb.plan_buildings(copy.deepcopy(specs), scene)
    assert "plan already" in building["refusal"]


def test_a_refused_room_is_in_the_frame_where_it_would_have_stood():
    """The frontage asks the plan's frames what a room it might move lands on
    (`plan_frames`): a room the plan refused stands in its frame where its
    first doorway would have put it, so what it lands on is seen."""
    from world.spatial import room_grid
    sc = _merged(SHOPS)
    (frame,) = plan_frames(sc)
    assert set(frame) == set(SHOPS)
    assert frame["shop_a"] == (room_site(sc, "shop_a")["x"], room_site(sc, "shop_a")["y"])

    def cells(rid):
        return {(x + frame[rid][0], y + frame[rid][1]) for x, y in room_grid(sc, rid).cells}
    assert cells("shop_b") & cells("shop_a"), "it stands where it would have landed"


def test_the_fringe_reads_the_plan_again_once_it_has_minted_its_stubs(temp_db):
    """The merge derives the plan before the fringe pass mints the beat's
    planned stubs; the scene the pass returns is what the next beat's
    readers see before their own merge, so it derives the plan again over
    what it minted -- a planned loft up the stair from the hall a walker
    has just entered stands on the plan from that commit on."""
    import time
    from world.structure import materialize_planned_fringe, plant_structure
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Fringe", "A town.", time.time()))
    plant_structure(cid, {"key": "town", "name": "Town"}, {
        "hall": {"name": "the Hall", "purpose": "a hall", "exposure": "enclosed",
                 "extent": {"w": 6, "d": 4}, "level": 0,
                 "adjacent": [{"to": "street", "dir": "s", "barrier": "closed_door"},
                              {"to": "loft", "vertical": "up", "way": "stair"}]},
        "loft": {"name": "the Loft", "purpose": "a loft", "exposure": "enclosed",
                 "extent": {"w": 6, "d": 4}, "level": 1,
                 "adjacent": [{"to": "hall", "vertical": "down", "way": "stair"}]},
        "street": {"name": "the Street", "purpose": "the street", "exposure": "open",
                   "extent": {"w": 12, "d": 3},
                   "adjacent": [{"to": "hall", "dir": "n"}]}})
    scene = {"rooms": {"street": {"name": "the Street", "desc": "A street.", "exposure": "open",
                                  "extent": {"w": 12, "d": 3},
                                  "adjacent": [{"to": "hall", "dir": "n",
                                                "barrier": "closed_door"}]},
                       "hall": {"name": "the Hall", "desc": "A hall.", "exposure": "enclosed",
                                "extent": {"w": 6, "d": 4}, "level": 0,
                                "adjacent": [{"to": "street", "dir": "s",
                                              "barrier": "closed_door"}]}},
             "positions": {"Walker": "hall"}, "entities": {}}
    scene, _added = materialize_planned_fringe(cid, scene)
    assert "loft" in scene["rooms"]
    assert {rid for rid in scene["rooms"] if room_site(scene, rid)} == {"street", "hall", "loft"}
    assert room_site(scene, "loft")["elev_m"] == 3.0


# ---------------------------------------------------------------------------
# Review of 2026-10-09: what stood on the plan stands where it stood
# ---------------------------------------------------------------------------

def _town_room(name, w, d, *edges, level=0, exposure="enclosed"):
    return _room(name, w, d, *edges, level=level, exposure=exposure, region="town")


#: Two buildings of two storeys each, joined by a lane between them, and a
#: road west of the first to a watch tower: one group, one plan.
TOWN = {
    "a_hall": _town_room("the Anchor hall", 6, 4,
                         {"to": "a_loft", "vertical": "up", "barrier": "open", "way": "stair"},
                         {"to": "lane", "dir": "e", "barrier": "open_door"},
                         {"to": "road", "dir": "w", "barrier": "open_door"}),
    "a_loft": _town_room("the Anchor loft", 6, 4,
                         {"to": "a_hall", "vertical": "down", "barrier": "open", "way": "stair"},
                         level=1),
    "road": _town_room("the west road", 40, 4, {"to": "a_hall", "dir": "e", "barrier": "open_door"},
                       {"to": "tower", "dir": "w", "barrier": "closed_door"}, exposure="open"),
    "tower": _town_room("the Watch tower", 6, 6, {"to": "road", "dir": "e",
                                                   "barrier": "closed_door"}),
    "lane": _town_room("the lane", 4, 4, {"to": "a_hall", "dir": "w", "barrier": "open_door"},
                       {"to": "b_hall", "dir": "e", "barrier": "open_door"}, exposure="open"),
    "b_hall": _town_room("the Bell hall", 6, 4, {"to": "lane", "dir": "w", "barrier": "open_door"},
                         {"to": "b_loft", "vertical": "up", "barrier": "open", "way": "stair"}),
    "b_loft": _town_room("the Bell loft", 6, 4,
                         {"to": "b_hall", "vertical": "down", "barrier": "open", "way": "stair"},
                         level=1),
}


def _town():
    return merge_scene_with_diff(
        {"rooms": {}, "positions": {"Ann": "a_hall"}, "entities": {},
         "stations": {"Ann": {"cell": [0, 2]}}, "day_phase": "day"},
        {"rooms": copy.deepcopy(TOWN)})


def _where(scene):
    return {rid: (s["plan"], s["x"], s["y"], s["elev_m"])
            for rid in scene["rooms"] if (s := room_site(scene, rid))}


def test_a_town_that_splits_keeps_both_halves_where_they_stood():
    """A town is one group until the room joining it is lost -- a collapse, a
    retirement, a doorway walled up. The half that keeps the room its plan
    was grown from is grown from it again; the other half is grown from a
    room of its own, where it stood, under the plan's name. Started afresh
    from (0, 0) under the region's name, it was laid on the first half: two
    storeys of overlaps nobody could clear, and the watch tower down the
    road said hidden behind the Bell hall, which stands across the lane."""
    from world.landscape import far_places
    sc = _town()
    joined = _where(sc)
    assert set(joined) == set(TOWN) and site_overlaps(sc) == []
    assert [p["room"] for p in far_places(sc, "Ann")] == ["tower"]
    # the lane lost, or the doorway onto it walled up: either way two groups
    for diff in ({"remove_rooms": ["lane"]},
                 {"remove_adjacent": [{"room": "a_hall", "to": "lane"}]}):
        split = merge_scene_with_diff(copy.deepcopy(sc), diff)
        assert _where(split) == {rid: at for rid, at in joined.items()
                                 if rid in split["rooms"]}, diff
        assert site_overlaps(split) == [] and plan_refusals(split) == []
        assert not [r for r in room_layout_lint(split, plan_rows=True)
                    if r["kind"].startswith("site_plan")]
        hidden = []
        assert [p["room"] for p in far_places(split, "Ann", hidden=hidden)] == ["tower"]
        assert not any(h["room"] == "tower" for h in hidden)
        again = copy.deepcopy(split)
        assert derive_site_plans(again) == [] and _where(again) == _where(split)


def test_a_room_added_to_one_half_of_a_split_town_never_lands_on_the_other():
    """Both halves stand on one plan, in one frame: a room either half adds is
    laid with the other half's rooms as ground it may not land on, and where
    it would, it is the room left off the plan and named."""
    split = merge_scene_with_diff(_town(), {"remove_rooms": ["lane"]})
    shed = _town_room("the lean-to", 6, 4, {"to": "a_hall", "dir": "w", "barrier": "open_door"})
    grown = merge_scene_with_diff(split, {"rooms": {
        "shed": shed,
        "a_hall": {"adjacent": [{"to": "shed", "dir": "e", "barrier": "open_door"}]}}})
    where = _where(split)
    assert {rid: at for rid, at in _where(grown).items() if rid in where} == where
    assert site_overlaps(grown) == []
    (refusal,) = plan_refusals(grown)
    assert refusal[1] == "shed" and set(refusal[2]) & {"b_hall"}


def _house(prefix):
    """A hall, the loft over it and the yard its door opens onto, of the town."""
    return {
        f"{prefix}_hall": _town_room(f"the {prefix} hall", 6, 4,
                                     {"to": f"{prefix}_loft", "vertical": "up",
                                      "barrier": "open", "way": "stair"},
                                     {"to": f"{prefix}_yard", "dir": "s",
                                      "barrier": "open_door"}),
        f"{prefix}_loft": _town_room(f"the {prefix} loft", 6, 4,
                                     {"to": f"{prefix}_hall", "vertical": "down",
                                      "barrier": "open", "way": "stair"}, level=1),
        f"{prefix}_yard": _town_room(f"the {prefix} yard", 6, 4,
                                     {"to": f"{prefix}_hall", "dir": "n",
                                      "barrier": "open_door"}, exposure="open"),
    }


def test_two_buildings_joined_by_no_room_never_share_a_plan_name():
    """A plan is one frame. Two buildings of one region joined by no room are
    two groups, each laid out from (0, 0): under one name, the two were read
    as one plan and stood on each other. A plan laid out for the first time
    takes a name no plan of the scene carries."""
    sc = _merged({**_house("east"), **_house("west")})
    plans = {rid: room_site(sc, rid)["plan"] for rid in sc["rooms"]}
    assert len(set(plans.values())) == 2
    assert plans["east_hall"] == plans["east_yard"] != plans["west_hall"] == plans["west_yard"]
    assert site_overlaps(sc) == []
    again = merge_scene_with_diff(copy.deepcopy(sc), {"rooms": {}})
    assert _where(again) == _where(sc), "and each keeps its name merge after merge"


def test_a_room_added_later_never_knocks_a_room_off_the_plan():
    """The rooms that stood on the plan are laid before a room that did not.
    A measured bakery drafted onto the street, its door a tenth of the way
    along the wall the chandler's opens off, and its id sorting first, took
    the chandler's place -- a body standing in it -- and the chandler's lost
    its site; so did a guessed square the moment a measured room was drafted
    beside it. The room added later is the one refused, and named."""
    base = {rid: room for rid, room in copy.deepcopy(SHOPS).items() if rid != "shop_b"}
    base["street"]["adjacent"] = [e for e in base["street"]["adjacent"] if e["to"] != "shop_b"]
    for measured_chandler in (True, False):
        rooms = copy.deepcopy(base)
        if not measured_chandler:
            rooms["shop_a"].pop("extent")
        sc = merge_scene_with_diff({"rooms": {}, "positions": {"Walker": "shop_a"},
                                    "entities": {}}, {"rooms": rooms})
        stood = room_site(sc, "shop_a")
        assert stood
        newcomer = "bakery" if measured_chandler else "zither"
        diff = {"rooms": {newcomer: _room("the newcomer", 6, 4, {"to": "street", "dir": "n",
                                                                  "barrier": "closed_door",
                                                                  "offset": 0.5}),
                          "street": {"adjacent": [{"to": newcomer, "dir": "s",
                                                   "barrier": "closed_door", "offset": 0.1}]}}}
        grown = merge_scene_with_diff(copy.deepcopy(sc), diff)
        assert room_site(grown, "shop_a") == stood, newcomer
        assert not room_site(grown, newcomer)
        assert [(r[1], r[2]) for r in plan_refusals(grown)] == [(newcomer, ("shop_a",))]
        (row,) = [r for r in room_layout_lint(grown, plan_rows=True)
                  if r["kind"] == "site_plan_unplaced"]
        assert row["room"] == newcomer


def test_the_layout_lint_walks_a_slid_open_side_where_the_plan_put_it():
    """The layout lint's walk lays a neighbour beside its room; where one plan
    holds both and slid an open side along its wall to stand clear, the walk
    lays it where the plan put it (`plan_offset`), or it draws the sheds on
    the house the plan slid them off. The World Browser's map and the
    frontage's plane read this walk; in chat 166 it decided six of the
    eighteen standing rows the plan changed (review of 2026-10-09)."""
    from world.spatial import layout_rooms
    sc = _merged(STAITHE)
    walk = layout_rooms(sc, "house")
    assert "sheds" not in (walk.get("collided") or {}), walk.get("collided")
    rel = plan_offset(sc, "staithe", "sheds")
    staithe = walk["offsets"]["staithe"]
    assert walk["offsets"]["sheds"] == (staithe[0] + rel[0] + 1, staithe[1] + rel[1]), \
        "where the plan put it, beyond the one-cell band"


def test_a_plan_never_lapses_when_the_room_it_grew_from_reaches_nothing():
    """The room a plan was grown from can stop reaching the rest -- its
    doorway onto the street lost its bearing -- while the group still holds
    together. The rooms that stood are laid where they stood, still clear
    there: the street and the chandler's keep their sites. Grown from the
    hall alone, they fell off the plan, named nowhere, and the derivation
    reported no change."""
    sc = _merged(SHOPS)
    before = _where(sc)
    for a, b in (("hall", "street"), ("street", "hall")):
        for edge in sc["rooms"][a]["adjacent"]:
            if edge["to"] == b:
                edge.pop("dir", None)
                edge.pop("offset", None)
    assert derive_site_plans(sc) == []
    assert _where(sc) == before


def test_a_group_with_nothing_still_standing_where_it_stood_is_laid_out_afresh():
    """Where nothing that stood can start the plan -- the one room that stood
    is now joined to the rest by a doorway with no bearing -- the group is
    laid out afresh, under a name of its own, rather than left with no plan:
    the new parlour and its attic span two storeys and stand on one."""
    sc = _merged(SHOPS)
    stood = room_site(sc, "hall")
    rooms = {
        "hall": copy.deepcopy(sc["rooms"]["hall"]),
        "parlour": _town_room("the parlour", 5, 4, {"to": "hall", "barrier": "open_door"},
                              {"to": "attic", "vertical": "up", "barrier": "open",
                               "way": "stair"}),
        "attic": _town_room("the attic", 5, 4, {"to": "parlour", "vertical": "down",
                                                 "barrier": "open", "way": "stair"}, level=1),
    }
    rooms["hall"]["adjacent"] = [{"to": "parlour", "barrier": "open_door"}]
    scene = {"rooms": rooms, "positions": {}, "entities": {}}
    derive_site_plans(scene)
    assert room_site(scene, "parlour") and room_site(scene, "attic")
    plan = room_site(scene, "parlour")["plan"]
    assert plan != stood["plan"] and room_site(scene, "attic")["plan"] == plan
    assert room_site(scene, "attic")["elev_m"] == 3.0


#: A yard with a lane east of it, and a stairwell south of both whose two
#: north doorways are at its two ends -- no plane holds both -- and the only
#: way up to the attic.
STAIRWELL = {
    "yard": _room("the yard", 6, 4, {"to": "lane", "dir": "e", "barrier": "open_door",
                                     "offset": 0.5},
                  {"to": "well", "dir": "s", "barrier": "open_door", "offset": 0.0}),
    "lane": _room("the lane", 6, 4, {"to": "yard", "dir": "w", "barrier": "open_door",
                                     "offset": 0.5},
                  {"to": "well", "dir": "s", "barrier": "open_door", "offset": 1.0}),
    "well": {"name": "the stairwell", "desc": "the stairwell.", "level": 0,
             "exposure": "enclosed",
             "adjacent": [{"to": "yard", "dir": "n", "barrier": "open_door", "offset": 0.0},
                          {"to": "lane", "dir": "n", "barrier": "open_door", "offset": 1.0},
                          {"to": "attic", "vertical": "up", "barrier": "open", "way": "stair"}]},
    "attic": {"name": "the attic", "desc": "the attic.", "level": 1, "exposure": "enclosed",
              "adjacent": [{"to": "well", "vertical": "down", "barrier": "open",
                            "way": "stair"}]},
}


def test_a_plan_whose_rooms_laid_out_stand_on_one_storey_is_not_written():
    """A plan is for height. Where the plan refuses the one room a storey is
    reached through, what it laid out stands on one storey: a plan of one
    storey gives height nothing to do and changes far sight, the owner's
    call for every one-storey group, so none is written (chat 40's roost
    stair: a plan of three rooms at -3 m). The room that cost the building
    its plan is still named, and the sentence says the plan is not there."""
    from world.site_plan import plan_refused
    from world.spatial import layout_warning
    sc = _merged(STAIRWELL)
    assert _sited(sc) == set()
    (refusal,) = plan_refused(sc)
    assert refusal["room"] == "well" and refusal["stands"] is False
    assert refusal["misses"] in (("yard",), ("lane",))
    (row,) = [r for r in room_layout_lint(sc, plan_rows=True) if r["kind"] == "site_plan_unplaced"]
    text = layout_warning(row)
    assert "cannot stand on a site plan" in text and "have no plan" in text


def test_the_world_browser_draws_a_room_the_plan_could_not_hold_on_the_plan():
    """The host is told a room stands off the plan (`site_plan_unplaced`, in
    the World Browser's rows) and sees it drawn on the plan's storey where
    its first doorway would have put it, flagged with what it lands on --
    never as a cluster of its own apart from the plan it clashes on (chat
    165: ten refused rooms drawn by the walk, away from the plan)."""
    from web.world_routes import _lint_rows, map_view
    sc = _merged(SHOPS)
    rows = _lint_rows(sc)
    assert any(r["kind"] == "site_plan_unplaced" and r["room"] == "shop_b" for r in rows)
    view = map_view(sc, rows)
    (storey,) = [c for c in view["components"] if c.get("plan") and c["level"] == 0]
    drawn = {r["id"]: r for r in storey["rooms"]}
    assert {"hall", "street", "shop_a", "shop_b"} <= set(drawn)
    cooper = drawn["shop_b"]
    assert cooper["collided"] and cooper["onto"] == "shop_a" and cooper["via"] == "street"
    (frame,) = plan_frames(sc)
    assert tuple(cooper["offset"]) == frame["shop_b"]
    assert {"room": "shop_b", "onto": "shop_a", "via": "street"} in storey["collisions"]
    assert not any("shop_b" in {r["id"] for r in c["rooms"]}
                   for c in view["components"] if c is not storey), "drawn once"
    street = next(e for e in drawn["street"]["exits"] if e["to"] == "shop_b")
    assert street["placed"], "its doorway leads to a room drawn on the plan"


def test_a_call_that_takes_sites_off_says_so():
    """`derive_site_plans` returns the rooms whose site it wrote, moved or
    took off: a group that comes down to one storey loses its plan, and
    every room of it is in the answer."""
    sc = _merged(SHOPS)
    sited = _sited(sc)
    flat = copy.deepcopy(sc)
    flat["rooms"]["loft"]["level"] = 0
    flat["rooms"]["loft"]["adjacent"] = []
    flat["rooms"]["hall"]["adjacent"] = [e for e in flat["rooms"]["hall"]["adjacent"]
                                         if e["to"] != "loft"]
    assert sorted(derive_site_plans(flat)) == sorted(sited)
    assert _sited(flat) == set()


def test_a_derived_half_never_stands_on_a_building_a_host_placed_where_it_stood():
    """A decided site stands where it was put, and the derivation never lays
    a room on it. Where a host has placed a kiosk on the plan over the spot
    the Bell hall stood on, the split half is not started there -- nor from
    its loft, which would leave the hall nowhere -- but laid out afresh
    under a name of its own, standing on nothing."""
    split = merge_scene_with_diff(_town(), {"remove_rooms": ["lane"]})
    b_hall = room_site(split, "b_hall")
    placed = copy.deepcopy(split)
    placed["rooms"]["kiosk"] = dict(_town_room("the kiosk", 6, 4),
                                    site={"plan": b_hall["plan"], "x": b_hall["x"],
                                          "y": b_hall["y"], "elev_m": 0.0})
    derive_site_plans(placed)
    assert site_overlaps(placed) == []
    assert room_site(placed, "kiosk")["x"] == b_hall["x"], "the host's kiosk stays"
    assert room_site(placed, "b_hall")["plan"] != b_hall["plan"]
    assert room_site(placed, "b_hall")["plan"] == room_site(placed, "b_loft")["plan"]
    assert room_site(placed, "a_hall") == room_site(split, "a_hall")


def test_a_room_laid_beside_a_placed_building_never_lands_on_another_group_on_its_plan():
    """A building a host placed on the town's plan is a group of its own,
    and what the derivation lays beside it -- its yard -- is laid with the
    rooms other groups hold on that plan as ground: where the yard would
    land on the Anchor hall it is refused and named, never laid on it."""
    split = merge_scene_with_diff(_town(), {"remove_rooms": ["lane"]})
    hall = room_site(split, "a_hall")
    rooms = {
        "kiosk": _town_room("the kiosk", 4, 4, {"to": "kiosk_loft", "vertical": "up",
                                                 "barrier": "open", "way": "stair"},
                            {"to": "kiosk_yard", "dir": "n", "barrier": "open_door"}),
        "kiosk_loft": _town_room("the kiosk loft", 4, 4, {"to": "kiosk", "vertical": "down",
                                                           "barrier": "open", "way": "stair"},
                                 level=1),
        "kiosk_yard": _town_room("the kiosk yard", 4, 4, {"to": "kiosk", "dir": "s",
                                                           "barrier": "open_door"},
                                 exposure="open"),
    }
    for rid in ("kiosk", "kiosk_loft"):
        rooms[rid]["site"] = {"plan": hall["plan"], "x": hall["x"] + 1, "y": hall["y"] + 4,
                              "elev_m": rooms[rid]["level"] * 3.0}
    sc = copy.deepcopy(split)
    sc["rooms"].update(rooms)
    derive_site_plans(sc)
    assert site_overlaps(sc) == []
    assert not room_site(sc, "kiosk_yard")
    assert [(r[1], r[2]) for r in plan_refusals(sc)] == [("kiosk_yard", ("a_hall",))]


def test_a_room_a_beat_moves_onto_another_storey_never_takes_the_place_of_one_it_did_not():
    """A beat can put a room where the plan cannot follow it by a doorway: in
    chat 160 the crash site was moved onto the elevator shaft's storey, so
    its stair joins two rooms of one storey and its doorways cross storeys,
    and where it stood it now lands on the shaft. The plan keeps the rest
    where it stood, and of the two on one spot it keeps the room the beat
    did not move: one still on the storey it stood on is laid before one a
    beat moved to another. Laid in the order of their ids, the unchanged
    lift was the room that left whenever the moved room's id sorted first
    (review of 2026-10-09). The room the beat moved stands where its column
    is clear, or nowhere -- no doorway tried for it, so no refusal names
    it (`UNBUILT_WORLD.md` §2.39)."""
    for hold in ("a_hold", "z_hold"):          # the plan's origin, then not
        rooms = {
            hold: _room("the hold", 6, 4, {"to": "corridor", "dir": "e", "barrier": "open_door"},
                        {"to": "lift", "vertical": "up", "barrier": "open", "way": "stair"}),
            "lift": _room("the lift", 6, 4, {"to": hold, "vertical": "down", "barrier": "open",
                                             "way": "stair"}, level=1),
            "corridor": _room("the corridor", 8, 3, {"to": hold, "dir": "w",
                                                     "barrier": "open_door"}),
        }
        sc = _merged(rooms)
        stood = _where(sc)
        assert set(stood) == set(rooms)
        moved = merge_scene_with_diff(sc, {"rooms": {hold: {"level": 1}}})
        assert site_overlaps(moved) == []
        assert _where(moved)["corridor"] == stood["corridor"], hold
        assert _where(moved)["lift"] == stood["lift"], hold
        assert hold not in _where(moved), hold


# ---------------------------------------------------------------------------
# Re-review of 2026-10-09: played forward, a change is read again
# ---------------------------------------------------------------------------

def _shape(scene, ref):
    """Every sited room's place relative to `ref`'s, and its floor's height:
    what a reading of the rooms says, in whatever frame it was grown."""
    at = room_site(scene, ref)
    return {rid: (s["x"] - at["x"], s["y"] - at["y"], s["elev_m"])
            for rid in scene["rooms"] if (s := room_site(scene, rid))}


def _read_afresh(scene):
    """The same rooms with no site, merged once: one reading of them."""
    fresh = copy.deepcopy(scene)
    for room in fresh["rooms"].values():
        room.pop("site", None)
    return merge_scene_with_diff(fresh, {"rooms": {}})


def _guessed(name, size, *edges, exposure="enclosed"):
    room = _room(name, 1, 1, *edges, exposure=exposure, size=size)
    room.pop("extent")
    return room


def test_a_plan_a_beat_re_measures_is_read_again_as_one_reading_lays_it():
    """A room keeps the ground it stood on only while its doorway still puts
    it there. A guessed shed stood half-way along a street that was itself a
    guess; the chandler's, added beside it, was refused. Then a beat
    measured the street: the shed's doorway moved with the wall, and kept
    first because it had stood, the guessed square held the ground against
    the measured shop -- played forward through chat 165's stored
    checkpoints, a boat-shed stub laid against a six-pace main walk kept its
    first claim after the walk was measured at fourteen, and the plan held
    7 of 30 rooms where one reading of the same rooms holds 14. A place that
    moved claims nothing: the plan is what one reading lays, and the guess
    is the room named."""
    rooms = {
        "hall": _room("the hall", 6, 4, {"to": "street", "dir": "s", "barrier": "open_door",
                                         "offset": 0.5},
                      {"to": "loft", "vertical": "up", "barrier": "open", "way": "stair"}),
        "loft": _room("the loft", 6, 4, {"to": "hall", "vertical": "down", "barrier": "open",
                                         "way": "stair"}, level=1),
        "street": _guessed("the street", "medium",
                           {"to": "hall", "dir": "n", "barrier": "open_door", "offset": 0.5},
                           {"to": "shed", "dir": "s", "barrier": "closed_door", "offset": 0.5},
                           exposure="open"),
        "shed": _guessed("a shed", "small", {"to": "street", "dir": "n",
                                             "barrier": "closed_door"}),
    }
    sc = _merged(rooms)
    assert _sited(sc) == set(rooms)
    shop = _room("the chandler's", 6, 4, {"to": "street", "dir": "n", "barrier": "closed_door",
                                          "offset": 0.5})
    sc = merge_scene_with_diff(sc, {"rooms": {"shop": shop, "street": {"adjacent": [
        {"to": "shop", "dir": "s", "barrier": "closed_door", "offset": 0.7}]}}})
    assert [(r[1], r[2]) for r in plan_refusals(sc)] == [("shop", ("shed",))], \
        "added beside a room that stands where it stood, it is the one refused"
    measured = merge_scene_with_diff(sc, {"rooms": {"street": {"extent": {"w": 16, "d": 3}}}})
    assert _shape(measured, "hall") == _shape(_read_afresh(measured), "hall")
    assert room_site(measured, "shop") and not room_site(measured, "shed")
    assert [(r[1], r[2]) for r in plan_refusals(measured)] == [("shed", ("shop",))]
    again = copy.deepcopy(measured)
    assert derive_site_plans(again) == [] and _where(again) == _where(measured)


def test_an_open_side_slides_along_its_wall_for_a_room_added_later_with_its_storeys():
    """An open side holds its side, not a place along it. Chat 166's boat
    sheds stood at the reed staithe's north end, their loft over them,
    before the Gale house was written onto the low walk beside them; kept
    where they stood, they refused the house, though one reading stands
    both -- the case the slide along an open side exists for. The sheds and
    the loft stacked on them slide down the staithe together, every doorway
    still meeting, and the house stands where its doorway puts it."""
    first = {rid: copy.deepcopy(room) for rid, room in STAITHE.items()
             if rid not in ("house", "house_loft")}
    first["walk"]["adjacent"] = [e for e in first["walk"]["adjacent"] if e["to"] != "house"]
    first["walk"]["adjacent"].append({"to": "inn", "dir": "w", "barrier": "open_door"})
    first["inn"] = _room("the inn", 5, 4, {"to": "walk", "dir": "e", "barrier": "open_door"},
                         {"to": "inn_loft", "vertical": "up", "barrier": "open", "way": "stair"})
    first["inn_loft"] = _room("the inn loft", 5, 4, {"to": "inn", "vertical": "down",
                                                     "barrier": "open", "way": "stair"}, level=1)
    first["sheds"]["adjacent"].append({"to": "net_loft", "vertical": "up", "barrier": "open",
                                       "way": "ladder"})
    first["net_loft"] = _room("the net loft", 6, 5, {"to": "sheds", "vertical": "down",
                                                     "barrier": "open", "way": "ladder"},
                              level=1, exposure="sheltered")
    sc = _merged(first)
    assert _sited(sc) == set(first)
    stood = room_site(sc, "sheds")
    grown = merge_scene_with_diff(copy.deepcopy(sc), {"rooms": {
        "house": copy.deepcopy(STAITHE["house"]),
        "house_loft": copy.deepcopy(STAITHE["house_loft"]),
        "walk": {"adjacent": [{"to": "house", "dir": "s", "barrier": "closed_door",
                               "offset": 1.0}]}}})
    assert _sited(grown) == set(first) | {"house", "house_loft"}
    assert plan_refusals(grown) == [] and site_overlaps(grown) == []
    sheds, loft = room_site(grown, "sheds"), room_site(grown, "net_loft")
    assert sheds["x"] == stood["x"] and sheds["y"] != stood["y"], "slid along the staithe"
    assert (loft["x"], loft["y"]) == (sheds["x"], sheds["y"]), "the loft over them, with them"
    assert plan_offset(grown, "staithe", "sheds") is not None, "still on the staithe's side"
    assert _shape(grown, "walk") == _shape(_read_afresh(grown), "walk")


def test_a_room_that_declares_its_wall_with_the_plan_only_on_its_own_side_is_reached():
    """A wall the far room declares is still where the two stand side by
    side. Chat 27's deep-shelter corridor declared the wall it shares with
    the lobby on its own side only, and a wall is the one barrier a far
    side's edge is never derived from (`effective_adjacent`): grown from the
    lobby, where the plan stood, the plan never reached the corridor nor the
    six rooms past it -- played forward, 3 of 13 rooms sited where one
    reading sites 10. The plan reaches a room through an edge either room
    declares."""
    sc = _merged({
        "lobby": _room("the lobby", 6, 4, {"to": "shaft", "vertical": "up", "barrier": "open",
                                           "way": "stair"}),
        "shaft": _room("the shaft", 6, 4, {"to": "lobby", "vertical": "down", "barrier": "open",
                                           "way": "stair"}, level=1)})
    grown = merge_scene_with_diff(copy.deepcopy(sc), {"rooms": {
        "corridor": _room("the corridor", 8, 3, {"to": "lobby", "dir": "s", "barrier": "wall"},
                          {"to": "chamber", "dir": "n", "barrier": "open_door"}),
        "chamber": _room("the chamber", 6, 6, {"to": "corridor", "dir": "s",
                                               "barrier": "open_door"})}})
    assert _sited(grown) == {"lobby", "shaft", "corridor", "chamber"}
    assert plan_refusals(grown) == [] and site_overlaps(grown) == []
    assert _where(grown)["lobby"] == _where(sc)["lobby"]
    assert _shape(grown, "lobby") == _shape(_read_afresh(grown), "lobby")


def test_a_room_joining_two_planned_buildings_never_drops_the_second_ones_plan():
    """A room added later can join two buildings that each stood on a plan of
    its own -- an alley between their yards. Laid into the first plan's
    frame, the alley landed on the first building's hall, or the second
    building's hall on the alley, and the second building -- a body upstairs
    in it -- lost every site, named nowhere. A join stands whole or not at
    all: where the first plan cannot hold every room that stood on the
    second, each keeps its plan where it stood, and the alley is laid with
    the first."""
    sc = merge_scene_with_diff({"rooms": {}, "positions": {"Ann": "west_loft"}, "entities": {}},
                               {"rooms": {**_house("east"), **_house("west")}})
    before = _where(sc)
    assert len({site[0] for site in before.values()}) == 2

    def alley(width, east_side, west_side):
        back = {"n": "s", "s": "n", "e": "w", "w": "e"}
        return {"alley": _town_room("an alley", width, 4,
                                    {"to": "east_yard", "dir": back[east_side],
                                     "barrier": "open_door"},
                                    {"to": "west_yard", "dir": west_side,
                                     "barrier": "open_door"}, exposure="open"),
                "east_yard": {"adjacent": [{"to": "alley", "dir": east_side,
                                            "barrier": "open_door"}]},
                "west_yard": {"adjacent": [{"to": "alley", "dir": back[west_side],
                                            "barrier": "open_door"}]}}
    # an alley the first plan cannot hold: it lands on the east hall
    narrow = merge_scene_with_diff(copy.deepcopy(sc), {"rooms": alley(2, "e", "n")})
    assert {rid: at for rid, at in _where(narrow).items() if rid in before} == before
    assert [(r[1], r[2]) for r in plan_refusals(narrow)] == [("alley", ("east_hall",))]
    # an alley the first plan holds, where the west hall would land on it:
    # each building keeps its plan, its hall and loft where they stood (the
    # west yard's new door shares the wall its hall door is on, so the
    # yard's own doorway moves along it, and the yard with it)
    wide = merge_scene_with_diff(copy.deepcopy(sc), {"rooms": alley(8, "w", "s")})
    after = _where(wide)
    assert {rid: after[rid][0] for rid in before} == {rid: at[0] for rid, at in before.items()}
    for rid in ("east_hall", "east_loft", "west_hall", "west_loft"):
        assert after[rid] == before[rid], rid
    assert room_site(wide, "alley") and site_overlaps(wide) == []
    assert plan_refusals(wide) == []
    # where the first plan holds every room of the second, they are one plan
    whole = merge_scene_with_diff(copy.deepcopy(sc), {"rooms": alley(8, "w", "n")})
    assert {site[0] for site in _where(whole).values()} == {before["east_hall"][0]}
    assert set(_where(whole)) == set(before) | {"alley"}
    assert plan_refusals(whole) == [] and site_overlaps(whole) == []


def test_a_room_a_beat_rewires_through_a_room_it_added_follows_the_doorways_it_wrote():
    """A beat can rewire what stood: a lane replaced by a longer plank bridge,
    a porch put between a street and a shop. Laid where it stood before the
    room the beat added, the far room refused that room -- the Room told to
    mend a contradiction that existed only between the beat and the
    engine's memory of the plan. What a chain of doorways still reaches is
    laid by the chain, the room the beat added included; only what no chain
    reaches is laid where it stood."""
    bridge = merge_scene_with_diff(_town(), {"remove_rooms": ["lane"], "rooms": {
        "bridge": _town_room("the plank bridge", 6, 4,
                             {"to": "a_hall", "dir": "w", "barrier": "open_door"},
                             {"to": "b_hall", "dir": "e", "barrier": "open_door"},
                             exposure="open"),
        "a_hall": {"adjacent": [{"to": "bridge", "dir": "e", "barrier": "open_door"}]},
        "b_hall": {"adjacent": [{"to": "bridge", "dir": "w", "barrier": "open_door"}]}}})
    assert {"bridge", "b_hall", "b_loft"} <= _sited(bridge)
    assert plan_refusals(bridge) == [] and site_overlaps(bridge) == []
    assert _shape(bridge, "a_hall") == _shape(_read_afresh(bridge), "a_hall")
    rooms = {rid: room for rid, room in copy.deepcopy(SHOPS).items() if rid != "shop_b"}
    rooms["street"]["adjacent"] = [e for e in rooms["street"]["adjacent"] if e["to"] != "shop_b"]
    sc = merge_scene_with_diff({"rooms": {}, "positions": {"Walker": "shop_a"}, "entities": {}},
                               {"rooms": rooms})
    porch = merge_scene_with_diff(copy.deepcopy(sc), {
        "remove_adjacent": [{"room": "street", "to": "shop_a"}, {"room": "shop_a", "to": "street"}],
        "rooms": {"porch": _room("the porch", 4, 2, {"to": "street", "dir": "n",
                                                     "barrier": "open_door", "offset": 0.5},
                                 {"to": "shop_a", "dir": "s", "barrier": "closed_door",
                                  "offset": 0.5}),
                  "street": {"adjacent": [{"to": "porch", "dir": "s", "barrier": "open_door",
                                           "offset": 0.5}]},
                  "shop_a": {"adjacent": [{"to": "porch", "dir": "n",
                                           "barrier": "closed_door", "offset": 0.5}]}}})
    assert {"porch", "shop_a"} <= _sited(porch) and plan_refusals(porch) == []
    assert _shape(porch, "hall") == _shape(_read_afresh(porch), "hall")


def test_a_room_refused_beside_a_decided_plan_is_told_the_plan_stands():
    """`stands` says whether the plan a room was refused from stands, and a
    plan of decided sites spanning two storeys stands though the derivation
    wrote none of it. Read off what the derivation wrote, a passage refused
    beside a solved hall and loft was told its rooms have no plan, and the
    World Browser drew it apart from the plan it clashes on."""
    from web.world_routes import _lint_rows, map_view
    from world.site_plan import plan_refused
    from world.spatial import layout_warning
    solved = "layout:hall"
    sc = {"rooms": {
        "hall": _room("the hall", 6, 4, {"to": "loft", "vertical": "up", "barrier": "open",
                                         "way": "stair"},
                      {"to": "street", "dir": "s", "barrier": "open_door", "offset": 0.5},
                      {"to": "kitchen", "dir": "e", "barrier": "open_door", "offset": 0.5},
                      site={"plan": solved, "x": 0, "y": 0, "elev_m": 0.0}),
        "loft": _room("the loft", 6, 4, {"to": "hall", "vertical": "down", "barrier": "open",
                                         "way": "stair"},
                      level=1, site={"plan": solved, "x": 0, "y": 0, "elev_m": 3.0}),
        "kitchen": _room("the kitchen", 6, 4, {"to": "hall", "dir": "w", "barrier": "open_door",
                                               "offset": 0.5},
                         site={"plan": solved, "x": 1, "y": 4, "elev_m": 0.0}),
        "street": _room("the passage", 8, 3, {"to": "hall", "dir": "n", "barrier": "open_door",
                                              "offset": 0.5})},
        "positions": {}, "entities": {}}
    derive_site_plans(sc)
    (refusal,) = plan_refused(sc)
    assert refusal["room"] == "street" and refusal["plan"] == solved and refusal["stands"]
    (row,) = [r for r in room_layout_lint(sc, plan_rows=True) if r["kind"] == "site_plan_unplaced"]
    assert f"stands off the site plan {solved!r}" in layout_warning(row)
    view = map_view(sc, _lint_rows(sc))
    (storey,) = [c for c in view["components"] if c.get("plan") == solved and c["level"] == 0]
    drawn = {r["id"]: r for r in storey["rooms"]}
    assert drawn["street"]["collided"] and drawn["street"]["onto"] == "kitchen"


def test_a_one_storey_half_of_a_split_town_keeps_where_it_stood():
    """A group of one storey gets no plan of its own -- the owner's call --
    but the half of a town cut off when the lane between was lost is part of
    a plan that stands, never a plan of its own: the Bell hall, with no loft
    over it, keeps where it stood on the town's plan while the plan still
    spans two storeys, as the half with the loft does."""
    sc = merge_scene_with_diff(_town(), {"remove_rooms": ["b_loft"]})
    joined = _where(sc)
    assert "b_hall" in joined
    split = merge_scene_with_diff(copy.deepcopy(sc), {"remove_rooms": ["lane"]})
    assert _where(split) == {rid: at for rid, at in joined.items() if rid in split["rooms"]}
    assert plan_refusals(split) == [] and site_overlaps(split) == []
    again = copy.deepcopy(split)
    assert derive_site_plans(again) == [] and _where(again) == _where(split)


def test_every_room_is_in_one_group_whichever_side_declares_the_wall():
    """A group is every room joined by an edge either room declares. Read
    from each room's own side, a wall only one room declared joined the
    group grown from that room and not the group grown from the other: the
    rooms on the far side were counted in two groups, and could be laid out
    twice (chat 10's third frame, four rooms; one-storey groups measured on
    the play database went 157 of 663 rooms where they are 156 of 659)."""
    from world.site_plan import _groups
    rooms = {
        "a_lobby": _room("the lobby", 6, 4, {"to": "b_shaft", "vertical": "up",
                                             "barrier": "open", "way": "stair"}),
        "b_shaft": _room("the shaft", 6, 4, {"to": "a_lobby", "vertical": "down",
                                             "barrier": "open", "way": "stair"}, level=1),
        "z_corridor": _room("the corridor", 8, 3, {"to": "a_lobby", "dir": "s",
                                                   "barrier": "wall"}),
    }
    sc = _merged(rooms)
    groups = _groups(sc)
    assert sorted(sorted(g) for g in groups) == [sorted(rooms)]
    assert _sited(sc) == set(rooms)


def test_of_two_rooms_a_beat_moves_onto_one_spot_the_room_that_stood_keeps_it():
    """A place that moved claims nothing, and among rooms with no claim the
    plan reads the rooms as one reading would -- except that where two are
    otherwise alike, the room that stood is laid before the room the beat
    added. A beat measured the street and drafted a new shop beside the
    chandler's in the same breath: the chandler's door moved with the wall,
    and the new shop, its id sorting first, is the one refused."""
    rooms = {rid: room for rid, room in copy.deepcopy(SHOPS).items() if rid != "shop_b"}
    rooms["street"]["adjacent"] = [e for e in rooms["street"]["adjacent"] if e["to"] != "shop_b"]
    for edge in rooms["street"]["adjacent"]:
        if edge["to"] == "shop_a":
            edge["offset"] = 0.25
    sc = _merged(rooms)
    stood = room_site(sc, "shop_a")
    grown = merge_scene_with_diff(copy.deepcopy(sc), {"rooms": {
        "street": {"extent": {"w": 16, "d": 3},
                   "adjacent": [{"to": "a_bakery", "dir": "s", "barrier": "closed_door",
                                 "offset": 0.3}]},
        "a_bakery": _room("the bakery", 6, 4, {"to": "street", "dir": "n",
                                               "barrier": "closed_door", "offset": 0.5})}})
    moved = room_site(grown, "shop_a")
    assert moved and (moved["x"], moved["y"]) != (stood["x"], stood["y"]), "it moved with the wall"
    assert not room_site(grown, "a_bakery")
    assert [(r[1], r[2]) for r in plan_refusals(grown)] == [("a_bakery", ("shop_a",))]


def test_a_room_laid_along_an_open_side_with_a_room_hung_from_it_by_a_doorway_holds():
    """Only a stack slides along an open side. A room laid from the sheds by
    a doorway holds them where they are -- its doorway would no longer meet
    -- so the house whose doorway lands on them is the room refused and
    named. Carrying the rooms laid from it too, the main walk of chat 165,
    laid along the landing stage with the town hanging off it, slid the
    whole town three to six paces at five of its six checkpoints played
    forward."""
    first = {rid: copy.deepcopy(room) for rid, room in STAITHE.items()
             if rid not in ("house", "house_loft")}
    first["walk"]["adjacent"] = [e for e in first["walk"]["adjacent"] if e["to"] != "house"]
    first["walk"]["adjacent"].append({"to": "inn", "dir": "w", "barrier": "open_door"})
    first["inn"] = _room("the inn", 5, 4, {"to": "walk", "dir": "e", "barrier": "open_door"},
                         {"to": "inn_loft", "vertical": "up", "barrier": "open", "way": "stair"})
    first["inn_loft"] = _room("the inn loft", 5, 4, {"to": "inn", "vertical": "down",
                                                     "barrier": "open", "way": "stair"}, level=1)
    first["sheds"]["adjacent"].append({"to": "office", "dir": "s", "barrier": "closed_door"})
    first["office"] = _room("the shed office", 3, 3, {"to": "sheds", "dir": "n",
                                                      "barrier": "closed_door"})
    sc = _merged(first)
    assert _sited(sc) == set(first)
    before = _where(sc)
    grown = merge_scene_with_diff(copy.deepcopy(sc), {"rooms": {
        "house": copy.deepcopy(STAITHE["house"]),
        "house_loft": copy.deepcopy(STAITHE["house_loft"]),
        "walk": {"adjacent": [{"to": "house", "dir": "s", "barrier": "closed_door",
                               "offset": 1.0}]}}})
    assert {rid: at for rid, at in _where(grown).items() if rid in before} == before
    assert [r[1] for r in plan_refusals(grown)] == ["house"]


def test_a_room_a_chain_reaches_only_through_a_room_the_plan_refuses_keeps_where_it_stood():
    """What stood and a chain of doorways still reaches is laid by the chain;
    where the chain is refused, what stood beyond it is laid where it stood
    once nothing else can lay it. The hall's doorway onto the street lost
    its bearing, and a porch the beat added between them lands on a kiosk a
    host placed: the porch is refused and named, and the street and the
    chandler's beyond it keep where they stood, never leaving the plan
    unnamed."""
    rooms = {rid: room for rid, room in copy.deepcopy(SHOPS).items() if rid != "shop_b"}
    rooms["street"]["adjacent"] = [e for e in rooms["street"]["adjacent"] if e["to"] != "shop_b"]
    sc = _merged(rooms)
    before = _where(sc)
    for a, b in (("hall", "street"), ("street", "hall")):
        for edge in sc["rooms"][a]["adjacent"]:
            if edge["to"] == b:
                edge.pop("dir", None)
                edge.pop("offset", None)
    sc["rooms"]["hall"]["adjacent"].append({"to": "porch", "dir": "e", "barrier": "open_door"})
    sc["rooms"]["porch"] = _room("the porch", 3, 3, {"to": "hall", "dir": "w",
                                                     "barrier": "open_door"},
                                 {"to": "street", "dir": "s", "barrier": "open_door"})
    sc["rooms"]["street"]["adjacent"].append({"to": "porch", "dir": "n", "barrier": "open_door",
                                              "offset": 1.0})
    hall = before["hall"]
    sc["rooms"]["kiosk"] = _room("the kiosk", 3, 3, site={"plan": hall[0], "x": hall[1] + 6,
                                                          "y": hall[2] + 1, "elev_m": 0.0})
    derive_site_plans(sc)
    assert {rid: at for rid, at in _where(sc).items() if rid in before} == before
    assert [(r[1], r[2]) for r in plan_refusals(sc)] == [("porch", ("kiosk",))]


def _staithe_with_the_inn(body_in_sheds):
    """The staithe before its house was written, with an inn on the walk, and
    Mara standing in the sheds or nowhere -- then the beat that adds the house
    whose one place lands on the sheds."""
    import copy
    from world.spatial import merge_scene_with_diff
    first = {rid: copy.deepcopy(room) for rid, room in STAITHE.items()
             if rid not in ("house", "house_loft")}
    first["walk"]["adjacent"] = [e for e in first["walk"]["adjacent"] if e["to"] != "house"]
    first["walk"]["adjacent"].append({"to": "inn", "dir": "w", "barrier": "open_door"})
    first["inn"] = _room("the inn", 5, 4, {"to": "walk", "dir": "e", "barrier": "open_door"},
                         {"to": "inn_loft", "vertical": "up", "barrier": "open", "way": "stair"})
    first["inn_loft"] = _room("the inn loft", 5, 4,
                              {"to": "inn", "vertical": "down", "barrier": "open", "way": "stair"},
                              level=1)
    base = {"rooms": {}, "positions": {}, "entities": {}, "stations": {}}
    if body_in_sheds:
        base = {"rooms": {}, "positions": {"Mara": "sheds"},
                "entities": {"Mara": {"kind": "person", "name": "Mara"}},
                "stations": {"Mara": {"cell": [2, 2]}}}
    before = merge_scene_with_diff(base, {"rooms": first})
    grown = merge_scene_with_diff(copy.deepcopy(before), {"rooms": {
        "house": copy.deepcopy(STAITHE["house"]),
        "house_loft": copy.deepcopy(STAITHE["house_loft"]),
        "walk": {"adjacent": [{"to": "house", "dir": "s", "barrier": "closed_door",
                               "offset": 1.0}]}}})
    return before, grown


def test_a_room_somebody_stands_in_never_slides_for_a_newcomer():
    """(review V3-2) An open side holds its side, not a place along it, so a
    room laid along one slides for a room with one place -- never with
    somebody standing in it: the ground a mind stands on is the stability
    the plan owes it. Slid, the sheds moved three paces with Mara in them,
    and her place on the plan with them. The newcomer is refused, and named."""
    from world.site_plan import plan_point, plan_refusals, room_site
    before, grown = _staithe_with_the_inn(body_in_sheds=True)
    assert room_site(grown, "sheds") == room_site(before, "sheds")
    assert plan_point(grown, "Mara") == plan_point(before, "Mara")
    assert room_site(grown, "house") is None
    assert any(row[1] == "house" and "sheds" in row[2] for row in plan_refusals(grown))
    # With nobody in them, the sheds still slide down the staithe for the house.
    before, grown = _staithe_with_the_inn(body_in_sheds=False)
    assert room_site(grown, "sheds") != room_site(before, "sheds")
    assert room_site(grown, "house") is not None
