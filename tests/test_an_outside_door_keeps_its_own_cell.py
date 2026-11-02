"""A room never opens two doorways from one cell where its wall has another
-- outside doors included.

`layout_solver._place_doors(apart=True)` (the arrangement core's path) holds
the cells each inner doorway opens from and spreads the rest of a wall's
doorways off them (the review of 2026-10-16, visual 5). The outside-door loop
never read those cells: on a corridor two paces wide with rooms off its east
side and a door onto the yard at its south end, the doorway to the last room
and the yard door both opened from the corridor's south-east corner while the
south wall's other cell stood free -- 4 of 6 variants of that plan on the
core path (audit 2026-11-01, world_layout_core F3, `doors.py`). The lab's own
spread (`apart=False`) is unchanged.

Hand-made plans; the names are illustrations, not the rule.
"""
from __future__ import annotations

import collections
import copy

import pytest

from world.layout_arrange import solve_arranged

_STEP = {"n": (0, -1), "s": (0, 1), "e": (1, 0), "w": (-1, 0)}


def _spec(n_side_rooms, toilet_out=False):
    rooms = [{"id": "hall", "level": 0, "purpose": "living",
              "joins": [{"to": "corr", "side": "e"}],
              "fixtures": [{"id": "t", "kind": "table"}]},
             {"id": "corr", "level": 0, "purpose": "corridor",
              "joins": [{"to": f"r{i}", "side": "e", "order": i + 1} for i in range(n_side_rooms)]
              + [{"to": "yard", "side": "s"}]}]
    for i in range(n_side_rooms):
        rooms.append({"id": f"r{i}", "level": 0, "purpose": "bedroom",
                      "fixtures": [{"id": f"b{i}", "kind": "bed"}]})
    if toilet_out:
        rooms.append({"id": "wc", "level": 0, "purpose": "toilet", "fixtures": [{"id": "w", "kind": "toilet"}],
                      "joins": [{"to": "hall", "side": "w"}, {"to": "yard", "side": "s"}]})
    return {"name": "x", "front": "n", "entrance": {"room": "hall"}, "rooms": rooms,
            "grounds": {"areas": [{"id": "yard", "name": "Yard", "where": "s"}]}}


def _opened_from(lay):
    """{(storey, room, cell): [what each doorway from that cell leads to]}."""
    by = collections.defaultdict(list)
    for d in lay.doors:
        a, c = d["a"], tuple(d["cell"])
        by[(d["level"], a, c)].append(d["b"])
        if not d.get("outside"):
            dx, dy = _STEP[d["side"]]
            by[(d["level"], d["b"], (c[0] + dx, c[1] + dy))].append(a)
    return by


@pytest.mark.parametrize("rooms_off", (1, 2, 3))
@pytest.mark.parametrize("toilet_out", (False, True))
def test_an_outside_door_opens_from_a_cell_no_doorway_holds(rooms_off, toilet_out):
    lay = solve_arranged(copy.deepcopy(_spec(rooms_off, toilet_out)))
    by = _opened_from(lay)
    for door in lay.doors:
        if not door.get("outside"):
            continue
        lv, rid, side = door["level"], door["a"], door["side"]
        here = (lv, rid, tuple(door["cell"]))
        if len(by[here]) < 2:
            continue
        r = lay.floors[lv][rid][0]
        dx, dy = _STEP[side]
        wall = [c for c in r.cells() if (c[0] + dx, c[1] + dy) not in r.cells()]
        free = [c for c in wall if len(by.get((lv, rid, tuple(c)), ())) == 0]
        assert not free, (rid, door["b"], here, by[here], free)
