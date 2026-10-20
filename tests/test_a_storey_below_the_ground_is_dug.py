"""Below the ground a storey is dug, not built.

The arrangement core laid a storey below the ground as it lays the ground: one
rectangle under the house, wholly floor, its rooms filling it wall to wall. A
two-room basement storey (the cellar stair's hall and the basement) then had
two shapes: side by side, each the storey's whole depth -- a stair hall far
past its landing cap -- or stacked, the basement beyond the flight. The flight
comes down along the house's edge, so the basement stood beyond it and the
stair hall held the wall the plan asked a cavern beyond: the owner's shrine
("at the far north end of the basement is the heavy warded door; it leads into
the Seal Cavern") turned its cavern to a side wall on 12 of 14 runs, and a
basement stated at 80 m2 was laid at 27.6 (the merge lane, 2026-10-15).

Now each room of a dug storey takes what it needs in the place the
arrangement gives it and the rest of the storey's rectangle is EARTH: no room,
no floor, no door, no window, never furnished (`layout_solver.Layout.earth`).
A flight below the ground may land beside its run (`ACROSS_LANDING`), within
the one landing a stair hall holds. The lab's own search lays no earth and
its layouts read as they did. The shrine is an illustration, not the rule.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from world.layout_arrange import ACROSS_LANDING, LANDING_MAX, _hall_fits, solve_arranged
from world.layout_solver import check, solve

_STEP = {"n": (0, -1), "s": (0, 1), "e": (1, 0), "w": (-1, 0)}
_LIKED = Path(__file__).resolve().parent.parent / "tools" / "layout_lab" / "baselines" / "shrine_rewritten.json"


def _liked():
    return json.loads(_LIKED.read_text())["spec"]


def _earth(lay, lv):
    cells = set()
    for r in lay.earth.get(lv, ()):
        cells |= r.cells()
    return cells


def test_what_no_room_takes_below_the_ground_is_earth():
    lay = solve_arranged(copy.deepcopy(_liked()))
    assert check(lay) == []
    earth = _earth(lay, -1)
    assert earth, "the liked shrine's basement storey leaves earth beside its stair"
    assert all(lv < 0 for lv in lay.earth)
    for b, levels in lay.outlines.items():
        o = levels.get(-1)
        if o is None:
            continue
        rooms = set()
        for rid, rects in lay.floors[-1].items():
            if lay.blocks.get(rid) == b:
                assert not rects[0].cells() & earth, rid
                rooms |= rects[0].cells()
        # every cell of the dug storey's outline is a room's or earth, never both
        assert rooms | (earth & o.cells()) == o.cells()
    # earth is no room, no store, no doorway, no window, never furnished
    assert not [rid for rid in lay.floors[-1] if rid.startswith("store_")]
    for d in lay.doors:
        if d["level"] == -1:
            dx, dy = _STEP[d["side"]]
            c = tuple(d["cell"])
            assert c not in earth and (c[0] + dx, c[1] + dy) not in earth, d
    assert not [w for w in lay.windows if w["level"] == -1 and tuple(w["cell"]) in earth]
    for rid, fxs in lay.fixtures.items():
        if rid in lay.floors[-1]:
            assert not [f for f in fxs if f["rect"].cells() & earth], rid
    assert "earth" in lay.as_dict()


def test_the_cavern_stands_beyond_the_basement_wall_the_plan_asks():
    lay = solve_arranged(copy.deepcopy(_liked()))
    basement = lay.floors[-1]["basement"][0]
    cavern = lay.floors[-1]["seal_cavern"][0]
    house = lay.outlines["main"][0]
    # the basement lies under the house, the cavern beyond its north wall --
    # beyond the house too -- through a doorway in that wall
    assert basement.cells() <= house.cells()
    assert cavern.y + cavern.d == basement.y == house.y
    assert min(cavern.x + cavern.w, basement.x + basement.w) - max(cavern.x, basement.x) > 0
    doors = [d for d in lay.doors if {d["a"], d["b"]} == {"basement", "seal_cavern"}]
    assert doors and all((d["side"] if d["a"] == "basement" else {"s": "n"}.get(d["side"])) == "n" for d in doors)
    assert not [w for w in lay.warnings if "Seal Cavern was asked beyond" in w]


def test_a_flight_below_the_ground_may_land_beside_its_run_within_one_landing():
    # a straight 5 x 2 flight: its hall the flight, landing at most
    # LANDING_MAX along the run -- and below the ground a row beside it,
    # within the sensible check's one landing (max(4, half the flight))
    assert _hall_fits(5, 2, 5, 2) and _hall_fits(5, 2, 5 + LANDING_MAX, 2)
    assert not _hall_fits(5, 2, 5, 3)
    assert ACROSS_LANDING >= 1
    assert _hall_fits(5, 2, 5, 3, ACROSS_LANDING)
    assert not _hall_fits(5, 2, 6, 3, ACROSS_LANDING)       # 18 cells: past the one landing
    assert not _hall_fits(5, 2, 5, 2 + ACROSS_LANDING + 1, ACROSS_LANDING)
    assert _hall_fits(2, 5, 3, 5, ACROSS_LANDING) and not _hall_fits(2, 5, 3, 5)


def test_the_labs_own_search_lays_no_earth():
    lay = solve(copy.deepcopy(_liked()))
    assert lay.earth == {}
    assert "earth" not in lay.as_dict()
