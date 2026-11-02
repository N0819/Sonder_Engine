"""The layout tier files what its solve said, stops solving when its job is
stopped, and builds only the buildings an actor is near.

Three requests from the layout core's lane (L12b, 2026-11-01), each the tier's
half of a change in `world/layout_bridge.py`:

* WARNINGS. The bridge now says why a building was laid by the lab's search
  instead of the arrangement core (`_fell_back`, `Layout.warnings`, and the
  report's `warnings`), and that sentence reached no run record: the tier
  filed counts and reasons and dropped the warnings, so a fallback was
  silent everywhere but the log (audit of 2026-11-01, world_layout_core F1).
* CANCELLATION. `layout_bridge.CANCELLED` is a predicate the job sets around
  its solves; the core and the lab's search raise `ArrangeCancelled` when it
  says stop. Nothing set it, so a rerolled job kept solving to the core's
  budget and four lab seeds of pure-Python CPU beside the beat that replaced
  it (world_layout_core E3) -- and an `ArrangeCancelled` the tier caught as
  an ordinary failure would be filed as a refusal.
* ONLY THE BUILDINGS NEAR AN ACTOR. `plan_buildings(only=...)` builds only the
  buildings holding one of the rooms asked about; built whole and then
  filtered, a street of expanded lots cost 112 ms at 25 lots and 1,485 ms at
  100, per rooms-in-view run (world_layout_bridge_structure E2).
"""

from __future__ import annotations

import threading
import time

import pytest

from agents import director_layout
from world import layout_bridge, structure
from world.layout_arrange import ArrangeCancelled


SCENE = {"rooms": {"hall": {"name": "Hall", "planned": True, "adjacent": []}},
         "positions": {"Wren": "hall"}}

BUILDING = {"key": "house", "signature": "sig-1", "plan": "house_plan",
            "rooms": ["hall", "loft"], "refusal": None,
            "specs": {"hall": {"name": "Hall"}, "loft": {"name": "Loft"}}}


class _Job:
    def __init__(self):
        self.cancelled = threading.Event()
        self.base_turn = 4


class _Layout:
    def __init__(self, warnings):
        self.warnings = list(warnings)


@pytest.fixture
def chat(temp_db, monkeypatch):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Tier", "", time.time()))
    monkeypatch.setattr(director_layout, "architect_lore",
                        lambda *a, **k: "")
    return cid


def test_only_the_buildings_holding_the_rooms_asked_about_are_built(chat,
                                                                   monkeypatch):
    asked = {}

    def plan_buildings(specs, scene, **kwargs):
        asked.update(kwargs)
        return []

    monkeypatch.setattr(layout_bridge, "plan_buildings", plan_buildings)
    director_layout.lay_out_buildings(None, chat, dict(SCENE), ["hall", "yard"],
                                      "en", call=lambda *a: {})
    assert asked.get("only") == {"hall", "yard"}


def test_the_job_tells_the_solves_when_it_is_stopped(chat, monkeypatch):
    job = _Job()
    seen = []
    monkeypatch.setattr(layout_bridge, "plan_buildings",
                        lambda specs, scene, **kwargs: [dict(BUILDING)])

    def solving(building, call, language_id):
        predicate = layout_bridge.CANCELLED.get()
        seen.append(None if predicate is None else predicate())
        job.cancelled.set()             # the job is rerolled mid-solve...
        seen.append(None if predicate is None else predicate())
        raise ArrangeCancelled("the job was stopped")   # ...and the solve stops

    monkeypatch.setattr(director_layout, "lay_out", solving)
    scene, laid = director_layout.lay_out_buildings(job, chat, dict(SCENE),
                                                    ["hall"], "en",
                                                    call=lambda *a: {})
    assert seen == [False, True]
    assert laid == set()
    # a stopped job is no failure: nothing waits on a retry
    assert director_layout._read_runs(chat) == {}
    # and the predicate is the job's alone: off once the run ends
    assert layout_bridge.CANCELLED.get() is None


def test_a_stop_is_never_filed_as_a_refusal(chat, monkeypatch):
    """Even when the stop reaches the tier before the job's own flag does."""
    monkeypatch.setattr(layout_bridge, "plan_buildings",
                        lambda specs, scene, **kwargs: [dict(BUILDING)])

    def stopped(building, call, language_id):
        raise ArrangeCancelled("the job was stopped")

    monkeypatch.setattr(director_layout, "lay_out", stopped)
    director_layout.lay_out_buildings(_Job(), chat, dict(SCENE), ["hall"], "en",
                                      call=lambda *a: {})
    assert director_layout._read_runs(chat) == {}


FELL_BACK = ("the arrangement core's layout did not stand -- it passed its "
             "work budget (12000); laid by the lab's search (seed 7)")


def test_a_layout_laid_by_the_lab_says_so_on_its_run_record(chat, monkeypatch):
    monkeypatch.setattr(layout_bridge, "plan_buildings",
                        lambda specs, scene, **kwargs: [dict(BUILDING)])
    monkeypatch.setattr(director_layout, "lay_out",
                        lambda building, call, language_id: (
                            {}, _Layout([FELL_BACK]), None, []))
    monkeypatch.setattr(layout_bridge, "planned_layout",
                        lambda building, spec, layout, **kwargs: (
                            {"hall": {}, "loft": {}},
                            {"plan": "house_plan", "moved": [], "unplaced": [],
                             "restored": [], "marks": [],
                             "warnings": list(layout.warnings)}))
    monkeypatch.setattr(director_layout, "_take_off_what_is_not_laid",
                        lambda *a, **k: None)
    monkeypatch.setattr(structure, "write_planned_layout",
                        lambda *a, **k: True)
    monkeypatch.setattr(structure, "apply_planned_layout", lambda *a, **k: None)
    _scene, laid = director_layout.lay_out_buildings(None, chat, dict(SCENE),
                                                     ["hall"], "en",
                                                     call=lambda *a: {})
    assert laid == {"hall", "loft"}
    entry = director_layout._read_runs(chat)["house"]
    assert entry["warnings"] == [FELL_BACK]


def test_a_refused_building_files_what_its_solve_said_too(chat, monkeypatch):
    monkeypatch.setattr(layout_bridge, "plan_buildings",
                        lambda specs, scene, **kwargs: [dict(BUILDING)])
    gave_up = "the arrangement core gave up first -- it could not lay the building"
    monkeypatch.setattr(director_layout, "lay_out",
                        lambda building, call, language_id: (
                            {}, _Layout([gave_up]), None,
                            ["a stair lands in no room"]))
    director_layout.lay_out_buildings(None, chat, dict(SCENE), ["hall"], "en",
                                      call=lambda *a: {})
    entry = director_layout._read_runs(chat)["house"]
    assert entry["failed"] == 1 and entry["reasons"] == ["a stair lands in no room"]
    assert entry["warnings"] == [gave_up]


def test_a_clean_solve_files_no_warnings_key(chat, monkeypatch):
    monkeypatch.setattr(layout_bridge, "plan_buildings",
                        lambda specs, scene, **kwargs: [dict(BUILDING)])
    monkeypatch.setattr(director_layout, "lay_out",
                        lambda building, call, language_id: (
                            {}, _Layout([]), None, []))
    monkeypatch.setattr(layout_bridge, "planned_layout",
                        lambda building, spec, layout, **kwargs: (
                            {"hall": {}}, {"plan": "house_plan", "moved": [],
                                           "unplaced": [], "restored": [],
                                           "marks": [], "warnings": []}))
    monkeypatch.setattr(director_layout, "_take_off_what_is_not_laid",
                        lambda *a, **k: None)
    monkeypatch.setattr(structure, "write_planned_layout", lambda *a, **k: True)
    monkeypatch.setattr(structure, "apply_planned_layout", lambda *a, **k: None)
    director_layout.lay_out_buildings(None, chat, dict(SCENE), ["hall"], "en",
                                      call=lambda *a: {})
    assert "warnings" not in director_layout._read_runs(chat)["house"]
