"""A way the plan joins to a room of the house and to a building apart is the
walk between their two doors.

A relay of the owner's shrine (2026-10-15): the plan joined a roofed walkway
to the washroom's back door, to the latrine standing apart, and to the garden
round the house. The walkway was sent out of the garden past its far edge, as
a lane leaving open ground is, and the latrine -- which no room opens onto --
was given a walk of its own that only its own door opened onto, so it was
never laid. Neither door met the walkway; the floor dropped the latrine, the
walkway and the torii charged beside them. The walkway is the walk between
the two doors, the latrine's door opens onto it, and only a way the plan
joins to no room of the house leaves the open ground. Built from the suite's
court; the names are illustrations, not the rule.
"""
from __future__ import annotations

import pytest

from world import layout_bridge as lb

from tests.test_the_grounds_keep_their_doors import _STEP, _add, _building, _court, _lay, _spec


def _walk(court=None):
    """The side room's east door onto a roofed walk, the walk on to a privy
    standing apart -- and, with `court`, joined to the court as well, which
    the answer then says lies there (`around`, or a side)."""
    def mutate(specs, sort, relate):
        specs["side"][1]["adjacent"].append({"to": "walk", "dir": "e", "barrier": "closed_door"})
        edges = [{"to": "side", "dir": "w"}, {"to": "privy", "dir": "e"}]
        if court:
            edges.append({"to": "court", "dir": "s"})
            specs["court"][1]["adjacent"].append({"to": "walk", "dir": "n"})
            next(g for g in relate["grounds"] if g["id"] == "court")["where"] = court
        _add(specs, "walk", "the Roofed Walk", "a roofed walk from the side room's back door",
             edges, exposure="sheltered")
        _add(specs, "privy", "the Privy", "a privy apart from the house",
             [{"to": "walk", "dir": "w"}], exposure="enclosed")
        sort["grounds"] += [{"id": "walk", "is": "way"}, {"id": "privy", "is": "outbuilding"}]
        # what the live answer said of each: the walk from the entrance to the
        # privy, the privy on a side the plan's way does not face
        relate["grounds"] += [{"id": "walk", "from": "entrance", "to": "privy"},
                              {"id": "privy", "side": "s"}]
    return mutate


@pytest.mark.parametrize("court", [None, "around"])
def test_the_walk_is_written_between_the_two_doors(court):
    """No start of its own and no walk of the privy's: the privy's door opens
    onto the plan's walk, on the wall the plan states, and the privy stands
    on the side the side room's door onto that walk faces, whatever the
    answer said."""
    _b, spec = _spec(_court(_walk(court)))
    walk = next(w for w in spec["grounds"]["ways"] if w["id"] == "walk")
    assert "from" not in walk
    assert "privy__way" not in {w["id"] for w in spec["grounds"]["ways"]}
    privy = next(r for r in spec["rooms"] if r["id"] == "privy")
    assert privy["joins"] == [{"to": "walk", "kind": "door", "side": "w"}]
    assert next(x for x in spec["blocks"] if x["id"] == "privy")["beside"]["side"] == "e"
    assert "privy" not in spec["door_to"]


@pytest.mark.parametrize("court", [None, "around"])
def test_the_walk_its_privy_and_the_ground_all_stand(court):
    """Laid through the tier's own path: nothing is dropped, the walk holds
    the step of each door, and the floor finds nothing to charge."""
    spec, layout, refused = _lay(_court(_walk(court)))
    assert refused == []
    assert not spec.get("places_dropped"), spec.get("grounds_dropped")
    assert {"court", "lane", "shed", "walk", "privy"} <= set(spec["ground_is"])
    cells = layout.ways["walk"]["cells"]
    for d in layout.doors:
        if d.get("outside") and d["b"] == "walk":
            sx, sy = _STEP[d["side"]]
            assert (d["cell"][0] + sx, d["cell"][1] + sy) in cells, d
    assert {d["a"] for d in layout.doors if d.get("outside") and d["b"] == "walk"} == {"side", "privy"}
    assert lb.ground_breaches(_building(_court(_walk(court))), spec, layout) == []


@pytest.mark.xfail(strict=True, reason=(
    "a walk the plan also joins to open ground lying on another side of the house is laid "
    "between its two doors and never reaches that ground: the floor drops the walk and the "
    "privy, as it did before the walk was laid between its doors (6 of the 34 such plans "
    "of the walk fuzz, 2026-10-15)"))
def test_a_walk_joined_to_ground_on_another_side_reaches_it():
    spec, _layout, refused = _lay(_court(_walk("s")))
    assert refused == []
    assert not spec.get("places_dropped"), spec.get("grounds_dropped")


def test_a_way_joined_to_a_door_never_leaves_the_ground_past_its_edge():
    """A path the plan joins to the side room's door and to the court, and to
    nothing with a door of its own: it runs out of that door, never from the
    court's far edge a plot's width from it."""
    def mutate(specs, sort, relate):
        specs["side"][1]["adjacent"].append({"to": "path", "dir": "e", "barrier": "open_door"})
        specs["court"][1]["adjacent"].append({"to": "path", "dir": "e"})
        _add(specs, "path", "the Path", "a gravel path",
             [{"to": "side", "dir": "w"}, {"to": "court", "dir": "w"}], exposure="open")
        sort["grounds"].append({"id": "path", "is": "way"})
        relate["grounds"].append({"id": "path"})

    _b, spec = _spec(_court(mutate))
    assert next(w for w in spec["grounds"]["ways"] if w["id"] == "path")["from"] == "door"
    lane = next(w for w in spec["grounds"]["ways"] if w["id"] == "lane")
    assert lane["from"] == "court", "a way joined to open ground alone still leaves it"
