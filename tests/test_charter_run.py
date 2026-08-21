"""The four properties `DESIGN_INSTITUTIONS_AND_UPKEEP.md` §11 says to build
alongside the simulation rather than after it.

A background simulation is testable in a way a model is not, and these are the
assertions that make "the crew operates the ship properly" a fact rather than
a hope:

  1. a healthy institution holds its upkeeps for a very long time;
  2. removing the one competent body degrades it in the reported way, not
     silently;
  3. the same seed replays byte-identically;
  4. a quiet week writes nothing at all.
"""

from __future__ import annotations

import copy

from world.charter import (
    normalize_charter, out_of_band, run, seed_roster, step)

from charter_fixtures import ABBEY, SHIP


def _ready(spec):
    """A charter whose roster happens to be accurate, at hour zero."""
    charter = normalize_charter(copy.deepcopy(spec))
    charter["roster"] = seed_roster(charter["bodies"])
    return charter


class TestAHealthyInstitutionRunsItself:
    """If a charter cannot hold a ship together under ideal conditions, the
    planner is wrong. This is a hard failure, not a feel problem."""

    def test_ten_thousand_hours_and_nothing_leaves_its_band(self):
        ship, events = run(_ready(SHIP), hours=10_000.0, window=4.0)

        assert [e for e in events if e["kind"] == "upkeep_out_of_band"] == []
        for key, upkeep in ship["upkeeps"].items():
            assert not out_of_band(upkeep), (key, upkeep["level"])

    def test_the_abbey_does_the_same_with_no_engine_change(self):
        abbey, events = run(_ready(ABBEY), hours=10_000.0, window=4.0)

        assert [e for e in events if e["kind"] == "upkeep_out_of_band"] == []
        for key, upkeep in abbey["upkeeps"].items():
            assert not out_of_band(upkeep), (key, upkeep["level"])


class TestAQuietWeekIsFree:
    """The whole cost model, pinned. Storage grows with INCIDENT, not with
    time — a tick that writes "nothing happened" every window is what makes a
    long story expensive, and it is the easy mistake to make here."""

    def test_a_week_of_a_working_ship_emits_zero_events(self):
        _, events = run(_ready(SHIP), hours=168.0, window=4.0)

        assert events == []

    def test_a_broken_thing_costs_one_row_not_one_per_window(self):
        """A condition already below its floor writes nothing further. Only
        the CROSSING is an event, or a wreck costs a row a window forever."""
        charter = _ready(SHIP)
        charter["bodies"]["chief"]["available"] = False
        charter["bodies"]["ramos"]["available"] = False
        charter["roster"] = seed_roster(charter["bodies"])

        _, events = run(charter, hours=2_000.0, window=4.0)
        crossings = [e for e in events
                     if e["kind"] == "upkeep_out_of_band"
                     and e["upkeep"] == "reactor_thermal"]

        assert len(crossings) == 1


class TestDegradationIsReportedNotSilent:
    def test_losing_the_only_rated_engineer_names_the_post_and_the_reason(
            self):
        """`engine_watch` needs engineering:2. Take both bodies that have it
        and the charter must SAY it cannot fill the post — the alternative is
        a ship that quietly stops being maintained."""
        charter = _ready(SHIP)
        charter["bodies"]["chief"]["available"] = False
        charter["bodies"]["ramos"]["available"] = False
        charter["roster"] = seed_roster(charter["bodies"])

        _, events = run(charter, hours=48.0, window=4.0)
        unfilled = [e for e in events if e["kind"] == "post_unfilled"]

        assert unfilled, "a post nobody can stand was filled anyway"
        assert {e["post"] for e in unfilled} == {"engine_watch"}
        assert {e["reason"] for e in unfilled} == {"no_competence"}
        assert any(e["kind"] == "upkeep_out_of_band"
                   and e["upkeep"] == "reactor_thermal" for e in events)

    def test_a_contended_body_is_distinguished_from_an_impossible_post(self):
        """Two posts wanting one body is a staffing story; a post nobody can
        stand is a competence story. An author reading the log has to be able
        to tell them apart."""
        charter = _ready(SHIP)
        for key in ("chief", "ramos", "hale", "cook"):
            charter["bodies"][key]["competence"] = {"engineering": 2}
        charter["roster"] = seed_roster(charter["bodies"])
        # Every remaining hand can stand engine_watch, so damage_control loses
        # its body to contention rather than to incapacity.
        charter["posts"]["damage_control"]["requires"] = {"engineering": 2}

        plan_events = step(charter, hours=4.0)[1]
        reasons = {e["post"]: e["reason"] for e in plan_events
                   if e["kind"] == "post_unfilled"}

        assert "no_competence" not in reasons.values()


class TestReplay:
    """Same seed, same events. This is what makes checkpoint restore and
    branching honest, and it is why the stochastic rung must be seeded rather
    than random."""

    def test_two_runs_of_the_same_seed_are_identical(self):
        a_state, a_events = run(_ready(SHIP), hours=500.0, window=4.0, seed=7)
        b_state, b_events = run(_ready(SHIP), hours=500.0, window=4.0, seed=7)

        assert a_events == b_events
        assert a_state["upkeeps"] == b_state["upkeeps"]

    def test_the_returned_charter_is_a_copy_not_a_mutation(self):
        """A caller must be able to explore a window without committing to it
        — which is what rerun-from-stage and checkpoint restore need."""
        charter = _ready(SHIP)
        before = copy.deepcopy(charter)

        step(charter, hours=4.0)

        assert charter == before
