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
    normalize_charter, out_of_band, run, seed_needs, seed_roster, step)

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

    def test_a_recovered_worker_reports_fit_and_returns_to_the_roster(self):
        """A one-person office may need rest, but it must not become vacant
        forever merely because the register never hears that they recovered.
        The status transition is the missing information channel."""
        charter = normalize_charter({
            "key": "single_office",
            "upkeeps": {
                "office": {
                    "place": "office", "level": 1.0, "floor": 0.2,
                    "drift_per_hour": 0.01, "service_per_hour": 0.03,
                },
            },
            "posts": {
                "director": {
                    "place": "office", "requires": {"leadership": 1},
                    "serves": ["office"],
                },
            },
            "bodies": {
                "director": {
                    "place": "office", "berth": "office",
                    "competence": {"leadership": 1}, "available": True,
                },
            },
        })
        charter["roster"] = seed_roster(charter["bodies"])
        charter["needs"] = seed_needs(charter["bodies"])

        after, events = run(charter, hours=48.0, window=4.0)

        assert any(e["kind"] == "body_unable" for e in events)
        assert any(e["kind"] == "body_recovered" for e in events)
        assert any(e["kind"] == "post_filled_again" for e in events)
        assert after["roster"]["director"]["believed_available"] is True
        assert after["roster"]["director"]["strength"] == 1.0


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


class TestTheFeaturedCastGetsAPast:
    """A body a registered character will take over is excluded from cognition
    and motion -- correct during play, and exactly wrong before the story
    opens, when there is no registered character to delegate to and
    manufacturing that character's past is the entire point of the run.

    Measured on the site_17 presim before this was fixed: after 720 simulated
    hours the one featured resident had stood 25 watches and was the SINGLE
    body absent from both `minds` and `needs`, holding zero experiences, while
    the 39 unbound bodies around it averaged 4.4 experiences and knew 5.8
    people each. The major character was the emptiest body in its institution.
    """

    @staticmethod
    def _bound(spec, who):
        charter = _ready(spec)
        for body in charter["bodies"].values():
            body["place"] = "galley"
            body["berth"] = "galley"
        charter["needs"] = seed_needs(charter["bodies"])
        charter["bindings"] = {who: {"char_id": 1, "entity_id": "e1",
                                     "name": who.title(), "promoted_turn": 0}}
        return charter

    def test_a_bound_body_is_hollowed_out_by_default(self):
        """The play-time behaviour, pinned so the fix cannot silently widen:
        Charter keeps the bound body on the watch bill and nothing else."""
        state, _ = run(self._bound(SHIP, "vega"), hours=240.0, window=8.0,
                       seed=3)

        assert state["minds"].get("vega") in (None, {})
        assert state["needs"].get("vega") in (None, {})
        assert state["minds"]["chief"], "an unbound peer still forms beliefs"

    def test_the_presim_gives_a_bound_body_the_same_life_as_its_peers(self):
        """`simulate_bound` is the pre-story dial. The featured body must come
        out indistinguishable from the crew it served beside -- otherwise the
        one person the player actually meets is the one with no past."""
        state, _ = run(self._bound(SHIP, "vega"), hours=240.0, window=8.0,
                       seed=3, simulate_bound=True)

        peers = [key for key in state["bodies"] if key != "vega"]
        assert state["minds"]["vega"], "the featured body knows nobody"
        assert state["needs"]["vega"], "the featured body has no needs"
        assert len(state["minds"]["vega"]) >= min(
            len(state["minds"].get(key) or {}) for key in peers)

    def test_the_exclusion_deletes_state_rather_than_skipping_it(self):
        """Why the default is destructive and not merely inert: `owned_needs`
        filters the bound body out and the FILTERED result becomes the new
        store, so one window erases what generation seeded. A presim that ran
        with the exclusion on cannot be repaired after the fact."""
        charter = self._bound(SHIP, "vega")
        assert charter["needs"]["vega"], "seeded before the run"

        state, _ = run(charter, hours=8.0, window=8.0, seed=3)

        assert not state["needs"].get("vega"), "one window, and it is gone"


class TestTheQuietYearsAreRememberedToo:
    """`active_places` is documented as "uniform existence, variable
    resolution -- everybody keeps needs, feeling, belief and A PAST". The past
    was the one item on that list that was not true: measured before this,
    the coarse phase produced ZERO experience rows over 240 simulated hours,
    so a 720-hour presim was 624 hours of silence and a 96-hour tail.
    """

    #: A crew that does not starve. SHIP's needs drain faster than anything
    #: aboard replenishes them, so over a long run every hand goes unavailable
    #: and ends up alone at a different post -- true of that fixture and
    #: nothing to do with what these tests are about, which is what a LIVING
    #: institution deposits while nothing is going wrong.
    KEPT = {"rest": {"floor": 0.05, "drift_per_hour": 0.0005,
                     "service_per_hour": 0.20},
            "sustenance": {"floor": 0.05, "drift_per_hour": 0.0005,
                           "service_per_hour": 0.20}}

    @classmethod
    def _quiet(cls, hours, **kw):
        charter = _ready(SHIP)
        for body in charter["bodies"].values():
            body["place"] = "galley"
            body["berth"] = "galley"
        charter["needs"] = seed_needs(charter["bodies"], cls.KEPT)
        charter["active_places"] = []
        return run(charter, hours=hours, window=8.0, seed=5, **kw)[0]

    def test_the_coarse_phase_writes_a_past_at_all(self):
        state = self._quiet(240.0)

        rows = [row for held in state["experiences"].values() for row in held]
        assert rows, "the long phase of every presim recorded nothing"
        assert {row["kind"] for row in rows} <= {
            "service", "acquaintance", "stood_through"}

    def test_a_body_remembers_taking_a_post_but_not_holding_it(self):
        """The module's cost rule -- storage grows with incident, not with
        time -- has to survive the new writers. A watch bill that settles and
        stays settled is one row per body, not one per window."""
        short = self._quiet(240.0)["experiences"]
        long = self._quiet(2400.0)["experiences"]

        def service(store):
            return sum(1 for held in store.values() for row in held
                       if row["kind"] == "service")

        assert service(short), "taking a post is worth remembering"
        assert service(long) < service(short) * 4, (
            "ten times the hours must not be ten times the rows")

    def test_familiarity_is_counted_rather_than_narrated(self):
        """What a quiet year actually deposits is not incident, it is who you
        were beside. Measured on the 40-body site_17 charter: a healthy
        simulated year emitted zero events and the watch bill stopped changing
        after about three months, so anything written only on change goes
        silent while the crew is still living."""
        short = self._quiet(240.0)["served_beside"]
        long = self._quiet(2400.0)["served_beside"]

        assert short, "nobody was beside anybody"
        assert set(short) == set(long), "the same crew, either way"
        assert max(sum(v.values()) for v in long.values()) > \
            max(sum(v.values()) for v in short.values()), (
                "familiarity has to deepen with time even when nothing happens")

    def test_a_bound_body_accumulates_the_quiet_past_too(self):
        """The two fixes have to compose: simulating the featured cast is
        worth nothing if the phase they are simulated through writes nothing.
        """
        charter = _ready(SHIP)
        for body in charter["bodies"].values():
            body["place"] = "galley"
            body["berth"] = "galley"
        charter["needs"] = seed_needs(charter["bodies"], self.KEPT)
        charter["active_places"] = []
        charter["bindings"] = {"vega": {"char_id": 1, "entity_id": "e1",
                                        "name": "Vega", "promoted_turn": 0}}

        state = run(charter, hours=240.0, window=8.0, seed=5,
                    simulate_bound=True)[0]

        assert state["experiences"].get("vega"), "the featured body again"
        assert state["served_beside"].get("vega")
