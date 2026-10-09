"""Doorways keep the wall the designer chose; code finds where along it, and
where a new place can join the world (`director_rooms`, `world/spatial_pack.py`,
`world/spatial_lint.leaf_rows`).

Measured on the 2026-10-08 play database:
- Two doorways seeded onto the same cells of one wall were a row a designer
  spent a step on (chat 166, turn 26: the Gale house landing's door to the
  house and its stair down, one north wall). The merge already spreads two
  doorways a room declares on one wall; a stair beside a door, or a far side
  the neighbour's edge places, it does not.
- The doorway search gave each try a copy and a merge of the town and two
  whole checks -- 0.19 s a try on chat 166's 33-room checkpoint -- so its
  1.5 s offered 2 of the 12 walls that fit, never tried the two rooms the
  prose put the landing between, and read as "nothing fits" when it had
  only run out of time.
- A doorway written on both sides with the same bearing (the Gale house's
  door, `s` from the house and from its landing, turns 22 and 26) was
  merged with no wall at all.
"""

from __future__ import annotations

import time

from agents import director_rooms
from world.spatial import (layout_index, leaf_rows, merge_scene_with_diff,
                           room_layout_lint)


def test_two_drafted_doorways_seeded_on_one_cell_get_distinct_places():
    """A three-pace north wall seeds every one-pace doorway on its middle
    cell; a door and a stair on it are two kinds the merge does not spread.
    The later one is moved along the same wall; an offset the designer wrote
    is never touched."""
    scene = {"rooms": {"porch": {"name": "Porch", "desc": "A porch."},
                       "loft": {"name": "Loft", "desc": "A loft."}}, "positions": {}}
    hall = {"name": "Hall", "desc": "A narrow hall.", "extent": {"w": 3, "d": 5},
            "adjacent": [{"to": "porch", "barrier": "open_door", "dir": "n"},
                         {"to": "loft", "barrier": "open_door", "dir": "n",
                          "vertical": "up", "way": "stair"}]}
    steps = iter([{"calls": [{"tool": "draft_room", "args": {"room_id": "hall",
                                                             "room": hall}}]},
                  {"calls": [{"tool": "submit", "args": {}}]}])
    record = {}
    draft = director_rooms.design_rooms(None, scene, {}, "sheet", ["hall"],
                                        lambda s, p: next(steps), record)
    edges = {e["to"]: e for e in draft["rooms"]["hall"]["adjacent"]}
    assert "offset" not in edges["porch"]
    assert edges["loft"]["offset"] in (0.0, 1.0) and edges["loft"]["dir"] == "n"
    assert not any("same cells" in e for e in record["final_check"]["errors"])

    pinned = dict(hall, adjacent=[dict(hall["adjacent"][0], offset=0.5),
                                  dict(hall["adjacent"][1], offset=0.5)])
    steps = iter([{"calls": [{"tool": "draft_room", "args": {"room_id": "hall",
                                                             "room": pinned}}]},
                  {"calls": []}])
    record = {}
    draft = director_rooms.design_rooms(None, scene, {}, "sheet", ["hall"],
                                        lambda s, p: next(steps), record)
    assert [e["offset"] for e in draft["rooms"]["hall"]["adjacent"]] == [0.5, 0.5]
    assert any("same cells" in e for e in record["final_check"]["errors"])

    # A doorway the world already holds is never moved, even re-mentioned.
    standing = {"rooms": dict(scene["rooms"], hall=dict(hall)), "positions": {}}
    steps = iter([{"calls": [{"tool": "draft_room", "args": {"room_id": "hall", "room": {
        "adjacent": [{"to": "loft", "barrier": "closed_door"}]}}}]}, {"calls": []}])
    draft = director_rooms.design_rooms(None, standing, {}, "sheet", ["hall"],
                                        lambda s, p: next(steps), {})
    assert all("offset" not in e for e in draft["rooms"]["hall"]["adjacent"])


#: A street with a chapel on it, a cellar the prose names off its east end,
#: and the inside of a cart standing in it.
TOWN = {"rooms": {
    "street": {"name": "the High Street", "desc": "A street.", "exposure": "open",
               "extent": {"w": 10, "d": 3},
               "adjacent": [{"to": "chapel", "barrier": "open_door", "dir": "n"}]},
    "chapel": {"name": "the Chapel", "desc": "A chapel.", "extent": {"w": 5, "d": 5}},
    "cellar": {"name": "the Old Cellar", "desc": "A cellar.", "extent": {"w": 4, "d": 4}},
    "cart_inside": {"name": "the cart's bed", "desc": "Planks.", "parent_entity": "cart"},
}, "positions": {"Mara": "street"}}
SHED = {"name": "the Shed", "size": "small", "shape": "rectangle"}


def test_the_doorway_search_tries_the_named_rooms_first_and_never_an_inside():
    named = director_rooms._named_in_prose(
        TOWN, "Mara ducks out of the High Street into a shed built against the "
              "old cellar, past the cart's bed.", ["shed"])
    assert named[:2] == ["street", "cellar"]
    fits = director_rooms._doorways_that_fit(
        TOWN, "shed", SHED, named + ["chapel"], time.time() + 30, named=named)
    assert fits and fits[0]["to"] in ("street", "cellar")
    assert any(f["to"] == "cellar" for f in fits)
    assert not any(f["to"] == "cart_inside" for f in fits)


def test_the_doorway_search_says_when_it_ran_out_of_time():
    left = []
    fits = director_rooms._doorways_that_fit(TOWN, "shed", SHED, ["street", "cellar"],
                                             time.time() - 1, left=left)
    assert fits == [] and left == ["street", "cellar"]


def test_a_one_doorway_room_adds_exactly_the_rows_the_whole_check_names_it_in():
    """`leaf_rows` against the check's own layouts, read once, against the
    whole check on the merged scene, wall by wall: the cheap try and the
    real one never disagree about where the new room lands."""
    index = layout_index(TOWN)
    for host in ("street", "chapel", "cellar"):
        for mine in ("n", "e", "s", "w"):
            edge = {"to": host, "barrier": "open", "dir": mine}
            record = dict(SHED, extent={"w": 6, "d": 3}, adjacent=[edge])
            merged = merge_scene_with_diff(TOWN, {"rooms": {"shed": record}})
            # Which of the two lands on the other is the walk's order; the
            # verdict -- that they collide -- is the same either way.
            whole = {(r["kind"], frozenset(r.get("rooms") or ()))
                     for r in room_layout_lint(merged)
                     if "shed" in (r.get("rooms") or ()) or r.get("via") == "shed"}
            cheap = {(r["kind"], frozenset(r.get("rooms") or ()))
                     for r in leaf_rows(merged, "shed", host, index)
                     if r["kind"] != "openings_overlap"}
            assert cheap == whole, (host, mine)


def test_a_far_side_follows_the_place_being_designed():
    """Written `s` from both rooms, the doorway kept no wall; the far
    room's copy now takes the opposite of the owed place's."""
    scene = {"rooms": {"house": {"name": "House", "desc": "A house.",
                                 "extent": {"w": 5, "d": 5}}}, "positions": {}}
    steps = iter([{"calls": [
        {"tool": "draft_room", "args": {"room_id": "landing", "room": {
            "name": "Landing", "desc": "A landing.", "extent": {"w": 3, "d": 2},
            "adjacent": [{"to": "house", "barrier": "closed_door", "dir": "s"}]}}},
        {"tool": "draft_room", "args": {"room_id": "house", "room": {
            "adjacent": [{"to": "landing", "barrier": "closed_door", "dir": "s"}]}}}]},
        {"calls": [{"tool": "submit", "args": {}}]}])
    record = {}
    draft = director_rooms.design_rooms(None, scene, {}, "sheet", ["landing"],
                                        lambda s, p: next(steps), record)
    back = [e for e in draft["rooms"]["house"]["adjacent"] if e["to"] == "landing"][0]
    assert back["dir"] == "n"
    merged = director_rooms._merged(scene, draft)
    mine = [e for e in merged["rooms"]["landing"]["adjacent"] if e["to"] == "house"][0]
    assert mine.get("dir") == "s", "the doorway keeps the wall its place gave it"


def test_a_doorway_the_world_holds_keeps_its_walls_however_the_draft_redeclares_it():
    """A parlour being developed and the hall beside it, joined by a door the
    world holds -- settled from both sides (east of the parlour, west of the
    hall), or written from the parlour's side alone. The designer drafts the
    parlour's copy `s` and re-mentions the hall's, `s` or the world's own
    `w`. Deriving the far copy as the opposite turned that into a matching
    two-sided re-declaration the merge's shield lets through, and the door
    moved to the parlour's south wall and the hall's north (round one's
    review, 2026-10-08). It keeps the walls the world gives it."""
    def world(both_sides):
        hall = {"name": "Hall", "desc": "A hall.", "extent": {"w": 6, "d": 4}}
        if both_sides:
            hall["adjacent"] = [{"to": "parlour", "barrier": "open_door", "dir": "w"}]
        return {"rooms": {
            "parlour": {"name": "Parlour", "desc": "A parlour (planned).",
                        "extent": {"w": 5, "d": 5},
                        "adjacent": [{"to": "hall", "barrier": "open_door", "dir": "e"}]},
            "hall": hall}, "positions": {}}

    for both_sides in (True, False):
        for theirs in ("s", "w"):
            scene = world(both_sides)
            before = director_rooms._merged(scene, {"rooms": {}})
            steps = iter([{"calls": [
                {"tool": "draft_room", "args": {"room_id": "parlour", "room": {
                    "desc": "A parlour with a bay window.",
                    "adjacent": [{"to": "hall", "barrier": "open_door", "dir": "s"}]}}},
                {"tool": "draft_room", "args": {"room_id": "hall", "room": {
                    "adjacent": [{"to": "parlour", "barrier": "open_door", "dir": theirs}]}}}]},
                {"calls": [{"tool": "submit", "args": {}}]}])
            record = {}
            draft = director_rooms.design_rooms(None, scene, {}, "sheet", ["parlour"],
                                                lambda s, p: next(steps), record)
            assert not record.get("bearings_derived"), (both_sides, theirs)
            hall = [e for e in draft["rooms"]["hall"]["adjacent"] if e["to"] == "parlour"][0]
            assert hall["dir"] == theirs, "the designer's own copy, as written"
            merged = director_rooms._merged(scene, draft)
            if both_sides:
                for rid, to in (("parlour", "hall"), ("hall", "parlour")):
                    was = [e for e in before["rooms"][rid]["adjacent"] if e["to"] == to][0]
                    now = [e for e in merged["rooms"][rid]["adjacent"] if e["to"] == to][0]
                    assert now.get("dir") == was.get("dir"), (rid, theirs)
            else:
                parlour = [e for e in merged["rooms"]["parlour"]["adjacent"]
                           if e["to"] == "hall"][0]
                assert parlour.get("dir") != "s", "never a wall code gave it"


def _far_side_draft(**place):
    """A house being designed, its door to the landing on its east wall, and
    the landing's copy of that door on the landing's south wall."""
    return {"rooms": {
        "house": {"name": "House", "desc": "A house.", "extent": {"w": 5, "d": 5},
                  "adjacent": [{"to": "landing", "barrier": "closed_door", "dir": "e"}]},
        "landing": {"adjacent": [dict({"to": "house", "barrier": "closed_door",
                                       "dir": "s"}, **place)]}},
        "remove_rooms": [], "remove_adjacent": []}


def test_a_far_side_the_designer_placed_is_left_on_the_wall_it_was_written_for():
    """The designer placed the landing's copy along the landing's south wall
    -- a fifth of the way along, or at a cell. Turned to the west to follow
    the house, that place was carried onto the west wall (round two's
    review, 2026-10-08): the copy is left as written, as every place the
    designer wrote is. An offset code wrote itself is no such place, and a
    copy with no place still follows the house."""
    scene = {"rooms": {"landing": {"name": "Landing", "desc": "A landing.",
                                   "extent": {"w": 6, "d": 6}}}, "positions": {}}
    for place in ({"offset": 0.2}, {"cell": [1, 5]}):
        draft = _far_side_draft(**place)
        assert director_rooms._derive_far_bearings(scene, draft, ["house"]) == []
        assert draft["rooms"]["landing"]["adjacent"][0] == dict(
            {"to": "house", "barrier": "closed_door", "dir": "s"}, **place)
    draft = _far_side_draft(offset=0.5)
    code = {("landing", "edge:house"): ("offset", 0.5, None)}
    assert director_rooms._derive_far_bearings(scene, draft, ["house"],
                                               placed_by_code=code)
    assert draft["rooms"]["landing"]["adjacent"][0]["dir"] == "w"
    draft = _far_side_draft()
    assert director_rooms._derive_far_bearings(scene, draft, ["house"])
    assert draft["rooms"]["landing"]["adjacent"][0]["dir"] == "w"


def test_a_held_doorway_with_no_bearing_gets_its_first_wall_only_on_the_owners_word(
        monkeypatch):
    """The world holds the house's door to the landing with no bearing (chat
    166's Gale house door, from turn 22). Written again from both rooms on
    walls that are not opposites, code leaves it as the world holds it --
    today's rule -- unless `DERIVE_FAR_SIDE_OF_A_HELD_BEARINGLESS_DOORWAY`
    is on; a held doorway WITH a bearing is left alone either way."""
    def scene(bearing=None):
        door = {"to": "house", "barrier": "closed_door"}
        if bearing:
            door["dir"] = bearing
        return {"rooms": {
            "landing": {"name": "Landing", "desc": "A landing.", "extent": {"w": 6, "d": 6},
                        "adjacent": [door]},
            "house": {"name": "House", "desc": "A house (planned).",
                      "extent": {"w": 5, "d": 5}}}, "positions": {}}

    assert director_rooms.DERIVE_FAR_SIDE_OF_A_HELD_BEARINGLESS_DOORWAY is False
    draft = _far_side_draft()
    assert director_rooms._derive_far_bearings(scene(), draft, ["house"]) == []
    assert draft["rooms"]["landing"]["adjacent"][0]["dir"] == "s"
    monkeypatch.setattr(director_rooms, "DERIVE_FAR_SIDE_OF_A_HELD_BEARINGLESS_DOORWAY", True)
    draft = _far_side_draft()
    assert director_rooms._derive_far_bearings(scene(), draft, ["house"])
    assert draft["rooms"]["landing"]["adjacent"][0]["dir"] == "w"
    draft = _far_side_draft()
    assert director_rooms._derive_far_bearings(scene("n"), draft, ["house"]) == []
    assert draft["rooms"]["landing"]["adjacent"][0]["dir"] == "s"


def test_a_way_written_up_from_both_ends_is_named_not_turned_into_a_bearing_row():
    """Each room said the other lies up; the merge kept neither direction and
    the check asked for opposite bearings, so the designer flipped n and s
    (the 2026-10-08 replay of chat 166, turn 22). The check names the
    direction that contradicts itself and repeats nothing downstream of it."""
    scene = {"rooms": {"walk": {"name": "the low walk", "desc": "A walk.",
                                "exposure": "open", "extent": {"w": 8, "d": 3}}},
             "positions": {}}
    draft = {"rooms": {
        "landing": {"name": "the landing", "desc": "A landing.", "extent": {"w": 3, "d": 2},
                    "adjacent": [{"to": "walk", "barrier": "open", "dir": "s",
                                  "vertical": "up", "way": "stair"}]},
        "walk": {"adjacent": [{"to": "landing", "barrier": "open", "dir": "s",
                               "vertical": "up", "way": "stair"}]}},
        "remove_rooms": [], "remove_adjacent": []}
    check = director_rooms._check(scene, draft, ["landing"])
    assert check["clean"] is False
    assert any("each say the other lies up" in e for e in check["errors"])
    assert not any("not opposites" in e for e in check["errors"])
