"""A building's yard is its ground, whatever part of the map the plan files it under.

To the Writers' Room a structure is "the part of the map the rooms make",
and a building's yard is a fair part of its own. The live shrines of
2026-10-15 filed the torii, the lantern path, the well, the garden, the
camphor and the latrine as `shrine_grounds` beside the house's structure in
two runs of two -- the owner's three plans had filed them with the house --
and the grounds walk, reading the house's structure alone, laid none of
them: every grounds claim of both shrines failed. The walk now also reads a
part of the map the building's own rooms open onto, which no other
building opens onto and which holds no building of its own; nothing else.
The court and its names are the suite's illustration, not the rule.
"""
from __future__ import annotations

import copy

import pytest

from world import layout_bridge as lb

from tests.test_the_grounds_keep_their_doors import _court, _lay

YARD = ("court", "lane", "shed")


def _filed_apart(extra=None):
    """The court's yard -- the court, the lane, the shed -- filed as a part
    of the map of its own."""
    def mutate(specs, sort, relate):
        for uid in YARD:
            specs[uid][1]["structure"] = "court_yard"
        if extra:
            extra(specs, sort, relate)
    return mutate


def _grounds(plan):
    specs, scene, held, _sort, _relate = plan
    found = lb.plan_buildings(copy.deepcopy(specs), copy.deepcopy(scene), held_open=held,
                              grounds=True)
    return sorted(g["id"] for g in max(found, key=lambda x: len(x["rooms"]))["grounds"])


def test_a_yard_filed_apart_is_collected_as_one_filed_with_the_building():
    assert _grounds(_court(lambda *_: None)) == sorted(YARD)
    assert _grounds(_court(_filed_apart())) == sorted(YARD)


def test_a_yard_filed_apart_is_laid():
    spec, layout, refused = _lay(_court(_filed_apart()))
    assert refused == []
    assert not spec.get("places_dropped"), spec.get("places_dropped")
    assert set(YARD) <= set(spec.get("ground_is") or {}), spec.get("ground_is")


def test_ground_another_buildings_door_opens_onto_is_the_towns():
    """An inn of the town's own part of the map opens onto the court: the
    court is ground the two buildings share, and neither lays it out."""
    def inn(specs, sort, relate):
        specs["inn"] = ("the Inn", {"purpose": "an inn", "structure": "town", "exposure": "enclosed",
                                    "adjacent": [{"to": "court", "dir": "e", "barrier": "closed_door"}]})
        specs["court"][1]["adjacent"].append({"to": "inn", "dir": "w"})
    assert _grounds(_court(_filed_apart(inn))) == []


@pytest.mark.parametrize("holds", ["two walled places joined", "a storey above the ground"])
def test_a_part_of_the_map_that_holds_a_building_is_no_yard(holds):
    def mill(specs, sort, relate):
        if holds == "two walled places joined":
            specs["shed"][1]["exposure"] = "enclosed"
            specs["shed"][1]["adjacent"].append({"to": "mill", "dir": "w", "barrier": "closed_door"})
            specs["mill"] = ("the Mill", {"purpose": "a mill", "structure": "court_yard",
                                          "exposure": "enclosed",
                                          "adjacent": [{"to": "shed", "dir": "e", "barrier": "closed_door"}]})
        else:
            specs["shed"][1]["level"] = 1
    assert _grounds(_court(_filed_apart(mill))) == []


def test_a_stair_between_the_yard_and_the_house_is_one_of_its_ways_out():
    """An outside ladder from the court up to the loft is a way out of the
    house, never a storey of the yard."""
    def ladder(specs, sort, relate):
        specs["court"][1]["adjacent"].append({"to": "loft", "vertical": "up", "way": "ladder"})
        specs["loft"][1]["adjacent"].append({"to": "court", "vertical": "down", "way": "ladder"})
    assert _grounds(_court(_filed_apart(ladder))) == sorted(YARD)


def test_the_walk_never_enters_a_part_of_the_map_no_door_of_the_building_opens_onto():
    """The lane runs on to the valley road, a part of the map of its own the
    house's doors do not open onto: the yard is laid, the road is not."""
    def road(specs, sort, relate):
        specs["lane"][1]["adjacent"].append({"to": "road", "dir": "s"})
        specs["road"] = ("the Road", {"purpose": "the valley road", "structure": "valley",
                                      "exposure": "open", "adjacent": [{"to": "lane", "dir": "n"}]})
    assert _grounds(_court(_filed_apart(road))) == sorted(YARD)
    assert _grounds(_court(road)) == sorted(YARD)
