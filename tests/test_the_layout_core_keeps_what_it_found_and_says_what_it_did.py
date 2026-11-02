"""The layout tier's core keeps a layout it has found, says when it gave the
building to the lab's search and why, stops when its job is stopped, and the
search it falls back to lays one plan one way in every process.

The audit of 2026-11-01 (world_layout_core), each reproduced:

* F1: `_arranged` turned ANY exception into "the core gave up" -- a
  `KeyError` in the core read exactly like a budget -- and the fallback's
  only trace was a sentence on a `Layout` nothing filed. A fault that is not
  the core's own refusal is logged with its traceback now, every fallback is
  logged, and a building both paths refuse carries the core's reason too.
* F2: `ArrangeBudget` raised inside an OPTIONAL pass -- `_climb`'s re-lay
  with a turned stair -- threw away the whole chain the first pass had
  found: on the test plan `STACKED`, a budget of the first pass's work plus
  1,000 entries raised from inside `_climb` (`climb_budget.py`). The budget
  bounds work; it does not unmake a layout in hand.
* E3: a cancelled layout job kept solving -- the core never asked, and the
  lab's four seeds neither -- for up to the budget plus four seeds of CPU.
* F4: the lab's search broke a tie between two asked walls by the iteration
  order of a set of one-letter strings, which `PYTHONHASHSEED` randomises:
  the same plan's upper storey stood against the other wall under hash
  seeds 3 and 5 (`part.py`).
* F6: `_support_hint` read the DEEPEST storey of a cellar shaft as the next
  one, so a shaft -1 -> -2 -> -3 priced storey -1 by the -3 room's wall.

Hand-made plans; the names are illustrations, not the rule.
"""
from __future__ import annotations

import copy
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.test_a_stair_is_climbed_and_its_landing_reached import STACKED, _room, _stair
from world import layout_arrange as A
from world import layout_bridge as lb
from world.layout_solver import Rect

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------- F1

def _through_hall():
    from tests.test_the_core_never_lays_worse_than_the_lab import THROUGH_HALL, _building
    spec = copy.deepcopy(THROUGH_HALL)
    return _building(spec), spec


def test_a_fault_in_the_core_is_logged_with_its_traceback_and_still_falls_back(monkeypatch, caplog):
    building, spec = _through_hall()

    def faulty(_spec, seed=None, face=True, cancelled=None):
        raise KeyError("a flight with no hall")
    monkeypatch.setattr(lb, "solve_arranged", faulty)
    with caplog.at_level(logging.WARNING, logger="fiction_engine"):
        layout, refused = lb.solve_for(building, spec)
    assert refused == []
    said = [w for w in layout.warnings if "arrangement core" in w]
    assert len(said) == 1 and "KeyError" in said[0]
    faults = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert faults and faults[0].exc_info and "KeyError" in faults[0].getMessage() + str(faults[0].exc_info[1])
    assert any("laid by the lab's search" in r.getMessage() for r in caplog.records)


def test_the_core_giving_up_is_said_without_a_traceback(monkeypatch, caplog):
    building, spec = _through_hall()

    def refuses(_spec, seed=None, face=True, cancelled=None):
        raise ValueError("block main: storey 0 could not be laid")
    monkeypatch.setattr(lb, "solve_arranged", refuses)
    with caplog.at_level(logging.WARNING, logger="fiction_engine"):
        layout, refused = lb.solve_for(building, spec)
    assert refused == []
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert any("could not lay the building" in r.getMessage() for r in caplog.records)


def test_a_building_both_refuse_says_the_core_gave_up_first(monkeypatch):
    building, spec = _through_hall()

    def refuses(_spec, seed=None, face=True, cancelled=None):
        raise ValueError("block main: storey 0 could not be laid")
    monkeypatch.setattr(lb, "solve_arranged", refuses)
    real = lb.refusals
    monkeypatch.setattr(lb, "refusals", lambda b, s, lay, breaches=None:
                        real(b, s, lay, breaches=breaches) + ["refused for the test"])
    layout, refused = lb.solve_for(building, spec)
    assert "refused for the test" in refused
    assert any("arrangement core" in w and "could not lay the building" in w
               for w in layout.warnings)


# ---------------------------------------------------------------- F2

def test_a_budget_spent_on_an_optional_pass_keeps_the_layout_found(monkeypatch):
    work = []
    real = A._Building._lay_kinds

    def counted(self, *args, **kwargs):
        out = real(self, *args, **kwargs)
        work.append(self.meter.total)
        return out
    monkeypatch.setattr(A._Building, "_lay_kinds", counted)
    A.solve_arranged(copy.deepcopy(STACKED))
    assert len(work) >= 2, "the first pass found a chain and _climb re-laid it"
    monkeypatch.setattr(A, "ARRANGE_WORK_BUDGET", work[0] + 1000)
    lay = A.solve_arranged(copy.deepcopy(STACKED))
    well = next(w for w in lay.stairwells if w["id"] == "c0__c1")
    assert well["kind"] == "straight", "the chain the first pass found"
    assert any("cannot be climbed" in w for w in lay.warnings)
    assert any("work budget" in w for w in lay.warnings)


def test_a_budget_spent_before_any_layout_is_found_still_gives_up(monkeypatch):
    monkeypatch.setattr(A, "ARRANGE_WORK_BUDGET", 50)
    with pytest.raises(A.ArrangeBudget):
        A.solve_arranged(copy.deepcopy(STACKED))


# ---------------------------------------------------------------- E3

def test_a_stopped_job_stops_the_core_and_the_lab_and_never_falls_back(monkeypatch):
    building, spec = _through_hall()
    asked = []

    def stopped():
        asked.append(1)
        return True
    with pytest.raises(A.ArrangeCancelled):
        A.solve_arranged(copy.deepcopy(STACKED), cancelled=stopped)
    assert asked
    # the core gives up on this one, and the job is stopped: no lab seed
    def refuses(_spec, seed=None, face=True, cancelled=None):
        raise ValueError("block main: storey 0 could not be laid")
    monkeypatch.setattr(lb, "solve_arranged", refuses)
    seeds = []
    real_solve = lb.solve
    monkeypatch.setattr(lb, "solve", lambda s, seed=None: seeds.append(seed) or real_solve(s, seed=seed))
    token = lb.CANCELLED.set(stopped)
    try:
        with pytest.raises(A.ArrangeCancelled):
            lb.solve_for(building, spec)
    finally:
        lb.CANCELLED.reset(token)
    assert seeds == [], "no lab seed is solved for a job that was stopped"


def test_a_job_stopped_between_seeds_solves_no_further_seed(monkeypatch):
    building, spec = _through_hall()
    seeds = []
    real_solve = lb.solve

    def solve(s, seed=None):
        seeds.append(seed)
        return real_solve(s, seed=seed)
    monkeypatch.setattr(lb, "solve", solve)
    monkeypatch.setattr(lb, "refusals", lambda *a, **k: ["refused for the test"])
    token = lb.CANCELLED.set(lambda: len(seeds) >= 1)
    try:
        with pytest.raises(A.ArrangeCancelled):
            lb.lab_solve_for(building, spec)
    finally:
        lb.CANCELLED.reset(token)
    assert len(seeds) == 1


# ---------------------------------------------------------------- F4

_TIE = {
    "name": "h2", "front": "s", "entrance": {"room": "hall"},
    "rooms": [{"id": "hall", "level": 0, "purpose": "living",
               "joins": [{"to": "kitchen", "side": "e"}, {"to": "dining", "side": "w"}],
               "fixtures": [{"id": "t", "kind": "table"}, {"id": "s", "kind": "sofa"},
                            {"id": "s2", "kind": "sofa"}]},
              {"id": "kitchen", "level": 0, "purpose": "kitchen",
               "fixtures": [{"id": "st", "kind": "stove"}, {"id": "c", "kind": "counter"}]},
              {"id": "dining", "level": 0, "purpose": "dining",
               "fixtures": [{"id": "dt", "kind": "table"}, {"id": "b1", "kind": "bench"}]},
              {"id": "work", "level": 0, "purpose": "workshop", "joins": [{"to": "kitchen", "side": "n"}],
               "fixtures": [{"id": "wb", "kind": "workbench"}]},
              {"id": "loft", "level": 1, "purpose": "bedroom", "fixtures": [{"id": "b", "kind": "bed"}]}],
    "stairs": [{"id": "a", "name": "Front stair", "from": "hall", "to": "loft", "from_at": "n", "kind": "ladder"},
               {"id": "b", "name": "Back stair", "from": "kitchen", "to": "loft", "from_at": "s", "kind": "ladder"}],
}

_PROBE = r"""
import copy, json, random, sys
import world.layout_solver as L
spec = json.loads(sys.argv[1])
p = L._prepare(copy.deepcopy(spec))
outlines = {b: {lv: [o.x, o.y, o.w, o.d] for lv, o in sorted(lv_.items())} for b, lv_ in p.outlines.items()}
spots = [[k, r.x, r.y, r.w, r.d] for k, r in L._shaft_spots(p.shafts[0], p.outlines, random.Random(1))]
print(json.dumps({"outlines": outlines, "spots": spots}, sort_keys=True))
"""


def test_the_lab_s_search_lays_one_plan_one_way_under_every_hash_seed():
    answers = set()
    for seed in ("1", "2", "3", "4", "5", "6"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        out = subprocess.run([sys.executable, "-c", _PROBE, json.dumps(_TIE)], cwd=ROOT, env=env,
                             capture_output=True, text=True, timeout=120, check=True)
        answers.add(out.stdout.strip())
    assert len(answers) == 1, answers


# ---------------------------------------------------------------- F6

def test_a_deep_cellar_s_storey_is_priced_by_the_storey_next_to_it():
    """One shaft from storey -1 down to -3. The -2 room's flights are asked on
    its east wall, so it stands WEST of the hall; the -3 room's on its west
    wall, so it stands EAST. Laid first, storey -1 with its floor west of the
    hall gives the storey laid next -- -2 -- all it needs: the hint costs
    nothing. Read off the deepest storey, it priced the east strip instead."""
    from world.layout_solver import _prepare
    spec = {"name": "cellars", "front": "s", "entrance": {"room": "hall"}, "blocks": [], "storeys": [],
            "rooms": [_room("hall", "living", 0, [{"to": "c1", "side": "n", "kind": "door"}]),
                      _room("c1", "cellar", -1), _room("c2", "cellar", -2), _room("c3", "cellar", -3)],
            "stairs": [_stair("s1", "c1", "c2", "e", "e", kind="spiral"),
                       _stair("s2", "c2", "c3", "e", "w", kind="spiral")]}
    p = _prepare(copy.deepcopy(spec), own_outlines=True)
    b = A._Building(p)
    [sh] = [s for s in p.shafts if -1 in s.levels]
    assert sorted(sh.levels) == [-3, -2, -1]

    class _Laid:
        pass
    laid = _Laid()
    laid.rects = {f"{sh.id}@-1": Rect(4, 4, 2, 2), "c1": Rect(0, 4, 4, 2)}
    assert b._support_hint(sh.block, -1, laid, set()) == 0
    laid.rects["c1"] = Rect(6, 4, 4, 2)           # the floor east: -2 has none
    assert b._support_hint(sh.block, -1, laid, set()) > 0
