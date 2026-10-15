"""A thing the plan joins to a room across ground stands where it was put.

The owner's shrine, relayed on 2026-10-15: every Writers' Room plan joined
the well to the kitchen's back door at an authored distance, `near`, and to
the lantern path; the answers stood it by the path, east of it, as the lore
has it. The tier pinned it at the kitchen's door instead (`at_door`, the
rule for a thing the plan joins to a room), where it touched no path, and
the grounds floor dropped it. A join the plan states across ground is no
wall the two share: the thing keeps the answer's relation, and the room's
door opens onto the open ground it stands in. A join with no distance, or
one written `adjacent`, keeps the thing at the door. The farm and its names
are illustrations, not the rule: the rule reads the plan's typed distance.
"""
from __future__ import annotations

import copy

import pytest

from world import layout_bridge as lb

from tests.test_a_building_stands_in_its_grounds import HELD_OPEN, RELATE, SCENE, SORT, SPECS

_STEP = {"n": (0, -1), "s": (0, 1), "e": (1, 0), "w": (-1, 0)}


def _farm(distance=None, every_join=False):
    """The farm with its well joined to the path too, related by the path,
    east of it -- and its join to the kitchen at `distance`."""
    specs = copy.deepcopy(SPECS)
    kitchen = next(e for e in specs["kitchen"][1]["adjacent"] if e["to"] == "well")
    well = specs["well"][1]
    if distance:
        kitchen["distance"] = distance
    well["adjacent"].append({"to": "path", "dir": "w"})
    specs["path"][1]["adjacent"].append({"to": "well", "dir": "e"})
    if every_join:
        for _uid, (_name, spec) in specs.items():
            for edge in spec.get("adjacent") or ():
                if not edge.get("vertical"):
                    edge["distance"] = distance
    relate = copy.deepcopy(RELATE)
    for g in relate["grounds"]:
        if g["id"] == "well":
            g.pop("by", None)
            g.update(by="path", side="e")
    found = lb.plan_buildings(specs, copy.deepcopy(SCENE), held_open=HELD_OPEN, grounds=True)
    b = max(found, key=lambda x: len(x["rooms"]))
    inv = lb.hold_inventory(b, copy.deepcopy(SORT))
    spec = lb.spec_from_answers(b, inv, relate)
    return b, spec


@pytest.mark.parametrize("distance", ["near", "12 m"])
def test_a_thing_joined_across_ground_keeps_the_answers_relation(distance):
    b, spec = _farm(distance)
    well = next(f for f in spec["grounds"]["features"] if f["id"] == "well")
    assert "at_door" not in well and "reach" not in well
    assert well.get("by") == "path" and well.get("side") == "e"
    # the kitchen's door opens onto the open ground the well stands in
    assert spec["door_to"]["well"] == "garden"
    layout, refused = lb.solve_for(b, spec)
    assert refused == [], refused
    assert lb.ground_breaches(b, spec, layout) == []
    solved, _report = lb.planned_layout(b, spec, layout)
    # it stands by the path, touching it, and the kitchen's doorway onto it
    # opens onto the garden it stands in
    well_cells = lb._world_cells(b, "well", solved["well"]["geometry"])
    path_cells = lb._world_cells(b, "path", solved["path"]["geometry"])
    garden_cells = lb._world_cells(b, "garden", solved["garden"]["geometry"])
    assert any((x + dx, y + dy) in path_cells for x, y in well_cells for dx, dy in _STEP.values())
    door = next(d for d in layout.doors if d.get("outside") and d["a"] == "kitchen")
    step = (door["cell"][0] + _STEP[door["side"]][0], door["cell"][1] + _STEP[door["side"]][1])
    assert step in garden_cells
    assert solved["kitchen"]["edges"]["well"]["dir"] == door["side"]


@pytest.mark.parametrize("distance", [None, "adjacent", "a fair way"])
def test_a_thing_joined_with_no_ground_between_stands_at_the_door(distance):
    """No distance, a shared wall's, or a word the engine cannot read: the
    thing stands across the room's door, reaching the way it is joined to."""
    _b, spec = _farm(distance)
    well = next(f for f in spec["grounds"]["features"] if f["id"] == "well")
    assert well["at_door"] == {"room": "kitchen", "onto": "garden"}
    assert well.get("reach") == ["path"]
    assert "well" not in spec["door_to"]


def test_a_distance_every_join_carries_keeps_the_thing_at_the_door():
    """A plan that writes `near` on every join says how it writes joins,
    not that one thing stands off a wall."""
    _b, spec = _farm("near", every_join=True)
    well = next(f for f in spec["grounds"]["features"] if f["id"] == "well")
    assert well["at_door"]["room"] == "kitchen"


def test_a_join_across_ground_is_refused_where_the_door_meets_no_ground_the_thing_stands_on():
    """The floor still reads the room's doorway: one whose threshold lies on
    no ground the thing stands on -- the garden taken off the kitchen's step
    here -- is charged to the thing."""
    b, spec = _farm("near")
    layout, refused = lb.solve_for(b, spec)
    assert refused == []
    door = next(d for d in layout.doors if d.get("outside") and d["a"] == "kitchen")
    step = (door["cell"][0] + _STEP[door["side"]][0], door["cell"][1] + _STEP[door["side"]][1])
    layout.areas["garden"] = {c for c in layout.areas["garden"]
                              if max(abs(c[0] - step[0]), abs(c[1] - step[1])) > 2}
    found = lb.ground_breaches(b, spec, layout)
    assert ("kitchen's doorway onto well opens onto no ground well stands on", "well") in found, found
