"""A frontier stub is named for the direction it leaves in, never for a room
the plan already has.

Measured on the Harrowmere replay (2026-09-03, `demos/harrowmere-replay-
2026-09-03/COMPARISON.md`, N2): the planner wrote its planned rooms into the
structure grammar's name pools, and `mint_frontier` drew a rule at random and
a name from it, so the "upland road" axis off the gate minted "bridge road"
(`bridge_road_2`, purpose "crossing") beside the real Bridge Road; the
Director, shown a stub called "bridge road" north of the gate, then minted
`upland_road` beside it. `slate_lane_2`, `market_square_2` and `_3` were the
same class, and those were every duplicate room of the run.
"""

from __future__ import annotations

import time

from world.structure import (
    apply_frontier_mutations, mint_frontier, plant_structure,
    prepare_frontier_expansion)


#: The replay's own structure grammar, verbatim from its `world` row.
HARROWMERE = {"key": "harrowmere", "max_planned": 100, "grammar": [
    {"kind": "road", "names": ["upland road", "bridge road"],
     "purposes": ["approach", "crossing"]},
    {"kind": "square", "names": ["market square"],
     "purposes": ["trade", "assembly"]},
    {"kind": "lane", "names": ["stone lane", "slate lane", "mill lane"],
     "purposes": ["dwelling"]},
    {"kind": "water", "names": ["Harrow river", "millrace"],
     "purposes": ["ford", "power"]},
]}
PLANNED = ["bridge_road", "market_square", "stone_lane", "slate_lane",
           "mill_lane", "upland_gate", "toll_bridge", "mill", "far_bank"]


def test_a_planned_rooms_name_is_reserved_and_the_axis_names_the_stub():
    uid, spec = mint_frontier(HARROWMERE, "upland_gate", "upland road",
                              "1:harrowmere", PLANNED)
    assert uid == "upland_road"
    assert spec["name"] == "Upland Road"
    # The rule is the one the axis shares words with: a road's purposes,
    # never the residential lane's.
    assert spec["purpose"] in ("approach", "crossing")
    for axis in ("far road", "riverside", "millrace"):
        uid, spec = mint_frontier(HARROWMERE, "toll_bridge", axis,
                                  "1:harrowmere", PLANNED)
        assert uid not in PLANNED
        assert not uid.startswith(("bridge_road", "market_square",
                                   "slate_lane", "stone_lane", "mill_lane"))


def test_a_second_segment_of_one_axis_carries_an_ordinal_in_its_name():
    existing = list(PLANNED)
    first, first_spec = mint_frontier(HARROWMERE, "toll_bridge", "far road",
                                      "1:harrowmere", existing)
    existing.append(first)
    second, second_spec = mint_frontier(HARROWMERE, "far_bank", "far road",
                                        "1:harrowmere", existing)
    assert (first, first_spec["name"]) == ("far_road", "Far Road")
    assert (second, second_spec["name"]) == ("far_road_2", "Far Road 2")


def test_a_grammar_name_nobody_planned_is_still_drawn_for_its_own_kind():
    structure = {"key": "aldermere", "max_planned": 20, "grammar": [
        {"kind": "lane", "names": ["North Lane"], "purposes": ["homes"]}]}
    uid, spec = mint_frontier(structure, "square", "north", "1:aldermere",
                              ["square"])
    assert (uid, spec["name"], spec["purpose"]) == (
        "north_lane", "North Lane", "homes")


def test_an_axis_that_names_a_planned_room_draws_an_edge_not_a_stub(temp_db):
    cid = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Frontier", "", time.time()))
    rooms = {
        "square": {"name": "Market Square", "purpose": "market",
                   "adjacent": [], "frontier": []},
        "lane": {"name": "Stone Lane", "purpose": "dwelling",
                 "adjacent": [], "frontier": ["market square", "north"]},
    }
    plant_structure(cid, HARROWMERE, rooms)
    scene = {"rooms": {"lane": {"name": "Stone Lane", "adjacent": []},
                       "square": {"name": "Market Square", "adjacent": []}},
             "positions": {"Player": "lane"}}
    scene, mutations = prepare_frontier_expansion(cid, scene)
    with temp_db.transaction():
        apply_frontier_mutations(cid, None, mutations)

    minted = set(scene["rooms"]) - {"lane", "square"}
    assert len(minted) == 1                     # "north" alone was minted
    assert "market_square" not in minted and "market_square_2" not in minted
    lane_edges = {e["to"] for e in scene["rooms"]["lane"]["adjacent"]}
    assert "square" in lane_edges
    assert {e["to"] for e in scene["rooms"]["square"]["adjacent"]} == {"lane"}
    _, repeated = prepare_frontier_expansion(cid, scene)
    assert repeated == []
