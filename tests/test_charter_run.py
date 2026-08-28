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
from world.charter_news import witness

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
        # THE CONSEQUENCE FRAME REPLAYS TOO. `pending_changes` is the input to
        # the next window's `charter_trigger` pass, so a restore that landed a
        # different frame would fire different rules on a state that is
        # otherwise byte-identical -- the divergence would appear a window
        # later and nowhere near its cause.
        assert a_state["pending_changes"] == b_state["pending_changes"]
        assert a_state["trigger_last"] == b_state["trigger_last"]

    def test_two_runs_of_the_same_seed_produce_the_same_marks(self):
        """`heard` is a dict of SETS and `politics.blame` a dict, and both
        feed the mark onsets. Either one left unsorted at that boundary lands
        a different past on a checkpoint restore, which is a different process
        -- so this is run under two `PYTHONHASHSEED` values in the same way
        `tools/charter_audit_feel.py` already runs the watch."""
        charter = normalize_charter({
            "key": "yard",
            "upkeeps": {"granary": {"place": "yard", "level": 0.9,
                                    "floor": 0.2, "drift_per_hour": 0.001,
                                    "service_per_hour": 0.03}},
            "posts": {"keeper": {"place": "yard", "serves": ["granary"]}},
            "bodies": {key: {"place": "yard"} for key in
                       ("ilse", "raul", "mira", "tomas")},
        })
        charter["roster"] = seed_roster(charter["bodies"])
        charter["needs"] = seed_needs(charter["bodies"])
        charter["active_places"] = ["yard"]
        charter["politics"] = {"blame": {"raul": 2}}
        # AND SOMEBODY SAW THE GRANARY FAIL. Since 2026-08-27 an accusation
        # follows the accuser's own claim rather than the institution's
        # register (`charter_practice.grievance_against`), so a fixture
        # carrying only a blame count mints no `accused` mark at all -- which
        # would make this a replay test over one kind instead of two, and the
        # assertion below says why that proves nothing.
        witness(charter["minds"], charter["bodies"],
                [{"kind": "upkeep_out_of_band", "place": "yard",
                  "upkeep": "granary", "at_hours": 0.0}], 0.0)

        a_state, a_events = run(copy.deepcopy(charter), hours=24.0,
                                window=4.0, seed=5)
        b_state, b_events = run(copy.deepcopy(charter), hours=24.0,
                                window=4.0, seed=5)

        assert a_events == b_events
        assert a_state["marks"] == b_state["marks"]
        assert {kind for entry in a_state["marks"].values()
                for kind in entry} >= {"posted", "accused"}, (
            "a fixture that mints no mark from a SET proves nothing")

    def test_blame_is_attributed_over_every_event_the_window_returns(self):
        """`attribute_blame` was HOISTED up `step` so the `disgraced` onset
        could read its delta, and that is safe only while every `events`
        append finishes above the new call site. A future writer appending an
        event below it would silently lose the blame it should have attached
        -- so the counter is recomputed here over the full returned list."""
        from world.charter import attribute_blame, normalize_politics

        charter = _ready(SHIP)
        before = normalize_politics(charter.get("politics"))
        after, events = step(charter, hours=4.0, seed=7)
        recomputed = attribute_blame(
            before, events, after["watch"], charter["posts"])

        assert after["politics"]["blame"] == recomputed["blame"]

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
        # `social` and `encounter` joined the coarse phase when the per-kind
        # dial was opened to every practice; the assertion is that the phase
        # writes SOMETHING and writes nothing the promotion side cannot read.
        assert {row["kind"] for row in rows} <= {
            "service", "acquaintance", "stood_through", "encounter",
            "social", "private_habit", "shared_prestory"}

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

    def test_marks_grow_with_incident_not_with_time(self):
        """The module's cost rule against the newest writer
        (`RESEARCH.md` §1.7.6 item 4), in the register of
        `test_a_body_remembers_taking_a_post_but_not_holding_it`. A socially
        temporary fact is bounded by bodies x kinds and pruned at expiry, so
        240 hours and 2,400 hours of the same quiet crew leave the same
        store -- which here is nothing at all, because the bill was handed out
        in the first day and nothing has been new since."""
        early = self._quiet(24.0)["marks"]
        short = self._quiet(240.0)["marks"]
        long = self._quiet(2400.0)["marks"]

        def rows(store):
            return sum(len(held) for held in store.values())

        assert rows(early) == len(self._quiet(24.0)["bodies"]), (
            "the institution handed its whole bill out and wrote none of it "
            "down")
        assert rows(long) <= rows(short) == 0, (
            "a mark nothing renewed outlived its own lifetime")

    def test_being_handed_a_post_is_the_one_mark_a_healthy_year_produces(self):
        """The argument for `posted` existing at all, and the answer to
        §1.7.6 item 2's complaint that every event this simulation emits is an
        institutional failure. Measured: 300 windows of the quiet crew, one
        mark kind ever held -- `posted` -- peaking at all six bodies in the
        first day and empty for the remaining 2,376 hours. The other three
        need somebody to go down, somebody to speak, or something to fail."""
        charter = self._quiet(0.0)
        held = set()
        for index in range(300):
            charter, _ = step(charter, hours=8.0, seed=5 + index)
            for entry in charter["marks"].values():
                held.update(entry)

        assert held == {"posted"}

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


class TestTheSocialWorldTurnsOffscreen:
    """Every social source in this module used to be gated on something going
    wrong: `tending` opens only when a body is under its floor, `greeting`
    only between people who have not met, `converse` was switched off
    offscreen for cost. Measured on the 40-body site_17 charter, a healthy
    simulated YEAR emitted zero events of any kind -- so the only thing an
    institution could ever be found to have done was fail, and a year of it
    promoted a character with 17.6 memories against a month's 16.7.
    """

    @staticmethod
    def _fresh(hours, bodies=6):
        charter = _ready(SHIP)
        for body in charter["bodies"].values():
            body["place"] = "galley"
            body["berth"] = "galley"
        charter["needs"] = seed_needs(
            charter["bodies"],
            TestTheQuietYearsAreRememberedToo.KEPT)
        charter["active_places"] = []
        return run(charter, hours=hours, window=8.0, seed=5)[0]

    def test_a_shared_watch_is_more_than_a_tally(self):
        """A counter says a pair stood three hundred watches together and says
        nothing about any of them. It is the right way to carry the volume and
        the wrong way to carry a life."""
        state = self._fresh(2400.0)

        rows = [row for held in state["experiences"].values() for row in held
                if row["kind"] == "encounter"]
        assert rows, "a year together and not one occasion out of it"
        assert all(row.get("other") for row in rows)
        # Both parties were there, so both keep it.
        one = rows[0]
        theirs = state["experiences"][one["other"]]
        assert any(row["kind"] == "encounter" and row["at_hours"] ==
                   one["at_hours"] for row in theirs)

    def test_occasions_stay_rarer_than_the_watches_that_hold_them(self):
        """Always in motion, and still sub-linear: the tally carries the
        volume so the rows do not have to."""
        state = self._fresh(2400.0)

        occasions = sum(1 for held in state["experiences"].values()
                        for row in held if row["kind"] == "encounter")
        shared = sum(sum(v.values()) for v in state["served_beside"].values())
        assert occasions < shared / 4, "every watch cannot be an occasion"

    def test_the_draw_replays(self):
        """Seeded, because a checkpoint restore and a branch have to land on
        the same encounters or the past changes under the player."""
        a = self._fresh(720.0)["experiences"]
        b = self._fresh(720.0)["experiences"]

        def occasions(store):
            return sorted(row["id"] for held in store.values() for row in held
                          if row["kind"] == "encounter")

        assert occasions(a) == occasions(b)
        assert occasions(a), "nothing drawn is not a replay"

    def test_the_dial_is_per_kind_and_not_only_per_place(self):
        """`COARSE_PRACTICES` is the half that was missing: offscreen you do
        not get gossip, and you do get the handful of situations that change
        who people are to one another. `converse` is the kind that saturates
        -- every acquainted pair in a room, every window, forever -- and it is
        the one that stays on screen.
        """
        from world.charter_practice import COARSE_PRACTICES, opportunities

        bodies = {
            "a": {"place": "hold", "available": True},
            "b": {"place": "hold", "available": True},
            "c": {"place": "hold", "available": True},
        }
        # `a` and `b` have met; `c` is a stranger to both.
        minds = {"a": {"b": {"strength": 0.9}}, "b": {"a": {"strength": 0.9}}}

        everything = opportunities(bodies, minds, {}, (), {}, 8.0)
        narrowed = opportunities(bodies, minds, {}, (), {}, 8.0,
                                 kinds={"greeting"})

        kinds = lambda opened: {row["kind"] for row in opened.values()}
        assert {"converse", "greeting"} <= kinds(everything)
        assert kinds(narrowed) == {"greeting"}, "the filter has to bite"
        # THE MECHANISM, NOT TODAY'S POLICY. `COARSE_PRACTICES` is None as of
        # 2026-08-27 -- the owner's call, on a measurement: excluding
        # `converse` offscreen rested on a 9x figure that does not reproduce
        # (twin_towns(40), a simulated month offscreen: 0.67s throttled
        # against 1.29s for every kind, and 1,276 rows against 3,932). The
        # seam a future throttle would use is what this pins.
        assert COARSE_PRACTICES is None or "converse" not in COARSE_PRACTICES
