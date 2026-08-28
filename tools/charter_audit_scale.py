"""Optional audit: five hundred hands and a thousand townsfolk.

The small fixtures prove the mechanism. These prove it survives the scale it
was built for, and they exist because every defect in this package so far was
found by running something bigger than the last thing, not by reading the
code:

  * a healthy crew watched its ship fail because rosters decayed and nothing
    refreshed them (fixed by standing-a-post being an observation);
  * a fully staffed town starved its own shop because the planner spent its
    only trader on drawing water;
  * 169 rows were written for five things happening;
  * every rated hand landed in one department because two cycles shared a
    period;
  * and at 500 hands, 476 of 500 roster entries sat at zero — the institution
    had forgotten its own crew existed while they were aboard and at work.
"""

from __future__ import annotations

import time

from world.charter import (
    PENDING_CHANGE_CAP, normalize_charter, out_of_band, regard_pair, run,
    seed_roster)

from charter_worlds import big_ship, big_town


def _ready(spec):
    charter = normalize_charter(spec)
    charter["roster"] = seed_roster(charter["bodies"])
    return charter


class TestItHoldsAtScale:
    def test_five_hundred_hands_run_a_ship_for_a_month_in_silence(self):
        ship = _ready(big_ship(500))
        assert len(ship["bodies"]) == 500
        assert len(ship["scene"]["rooms"]) > 90

        after, events = run(ship, hours=720.0, window=4.0)

        assert events == []
        for key, upkeep in after["upkeeps"].items():
            assert not out_of_band(upkeep), (key, upkeep["level"])

    def test_a_thousand_townsfolk_keep_a_supply_chain_fed(self):
        town = _ready(big_town(1000))
        assert len(town["bodies"]) == 1000

        after, events = run(town, hours=720.0, window=4.0)

        assert events == []
        assert not out_of_band(after["upkeeps"]["market_stocked"])
        # AND THE CONSEQUENCE FRAME IS BOUNDED AT SCALE. `pending_changes`
        # (`RESEARCH.md` §1.7.6 item 5) is the one new per-window persisted
        # field, and a thousand townsfolk is where an unbounded one would
        # show. Measured 2026-08-27 on a famine week of `twin_towns(240)`:
        # the busiest window produced 184 raw changes against a cap of 32.
        assert len(after["pending_changes"]) <= PENDING_CHANGE_CAP

    def test_a_simulated_month_costs_seconds_not_minutes(self):
        """Not a benchmark — a regression guard on the cost model.

        The graph walk was hoisted out of the window loop when a simulated
        week cost 8.9s; a change that puts it back would show here as a run
        an order of magnitude slower. Generous bound, because a shared CI box
        is not a quiet one.
        """
        ship = _ready(big_ship(500))

        started = time.perf_counter()
        run(ship, hours=720.0, window=4.0)
        elapsed = time.perf_counter() - started

        # Healthy runs on the same workstation measured below 30s in
        # isolation and 30.4--33.2s after several minutes of sustained test
        # load.  The regression this guards was order-of-magnitude graph-walk
        # work (minutes), so 45s keeps that tripwire without making scheduler
        # noise a product failure.
        #
        # THIS ASSERTION IS FAILING AND IS LEFT FAILING ON PURPOSE. Measured
        # 2026-08-27 on `.venv`, three trees strictly interleaved in one
        # sitting: `main` at 48cdd94 43.0/42.3s, this branch's committed
        # baseline 96916f6 89.5/88.6s, the working tree 90.0s (the same tree
        # reads 64.7s here on a quiet box -- the RATIOS are the measurement,
        # not the seconds). So `main`
        # PASSES and the branch does not -- the earlier register entry
        # (`docs/UNBUILT.md` §1.99c) blamed 48cdd94 and was measuring 100
        # commits from the wrong side of the branch point. Raising the number
        # would erase the only evidence of a 2x regression that is real,
        # reproducible and NOT in the §1.7.6 consequence layer (the same
        # fixture with the trigger pass inert reads within 1% of live). The
        # audit is opt-in -- `tools/` is outside `testpaths` -- so nothing in
        # CI is red because of it. See §1.99c for the bisect.
        assert elapsed < 45.0, f"a month of 500 hands took {elapsed:.1f}s"

    def test_a_simulated_year_of_a_town_still_costs_seconds_not_minutes(self):
        """The same guard for the per-window writers rather than the graph
        walk, and the arm the `charter_mark` layer (`RESEARCH.md` §1.7.6 item
        4) was measured against.

        Measured on `.venv`, this workstation, `big_town(40)` at 8,760 hours,
        window 4.0, seed 3, with the mark WRITER swapped for a no-op and the
        arms strictly INTERLEAVED in one process: 23.64/23.67s live against
        22.71/23.16s inert. The store adds one dict pass over the bodies per
        window and nothing quadratic, which is the property this guards -- a
        writer that paired a crowd here would show up as an order of
        magnitude, not as three per cent.

        THAT MEASUREMENT LEFT THE READER LIVE IN BOTH ARMS, and the reader was
        the quadratic half: `held_marks` normalized the whole store to answer
        for one body, so `charter_run.step`'s per-body reluctance loop cost
        bodies x marked-bodies every window. It was invisible at 40 bodies and
        was +17% at 500 (`world/charter_mark.py`, `_normalize_row`). Bounds set
        from measurement rather than from generosity, because a bound with 4x
        headroom cannot catch the class it is written for: this exact run reads
        14.1--15.8s on `.venv` under ordinary load, so 40s is about 2.5x the
        slowest reading and still an order of magnitude below the failure this
        guards.
        """
        town = _ready(big_town(40))

        started = time.perf_counter()
        after, _events = run(town, hours=8_760.0, window=4.0, seed=3)
        elapsed = time.perf_counter() - started

        # A simulated year of a healthy institution ends holding nothing:
        # every mark it minted has outlived its own lifetime.
        assert after["marks"] == {}
        # AND THE CONSEQUENCE LAYER (`RESEARCH.md` §1.7.6 item 5) IS FREE ON
        # IT. Measured 2026-08-27 on the same fixture at 4,380 hours with
        # `fire_triggers`/`changes_from` swapped for no-ops and three pairs of
        # arms strictly INTERLEAVED in one process: 10.71/10.27/10.23s live
        # against 10.15/10.53/10.17s inert -- +5.5%, -2.4%, +0.6%, mean +1.2%,
        # so the pass is not visible above run-to-run noise. Micro-profiled it
        # is 18 microseconds per window (`normalize_triggers` 15 of them),
        # which is 0.2% of the window. It stays free because the pass reads a
        # CHANGE and never a state: with an empty frame it returns on one
        # falsy test, and this fixture deposits an empty frame all year.
        assert after["fired"] == []
        assert elapsed < 40.0, f"a year of 40 townsfolk took {elapsed:.1f}s"


class TestGossipKeepsTheInstitutionAwareOfItself:
    """The channel that was missing. Twenty-four posts observe twenty-four
    bodies; everyone else is known about only because they were seen."""

    def test_the_register_keeps_every_name_but_is_sure_of_few(self):
        """What a written register does, and what per-head belief changed.

        Once minds arrived, the roster stopped being refreshed by everyone
        being seen and became what it should be: the watch reports what IT
        believes, and the rest of the book goes stale. So the honest claim is
        no longer "everyone is known confidently" — it is that nobody is
        struck off, and that the bodies actually standing posts are the ones
        the institution is sure about.
        """
        ship = _ready(big_ship(500))

        after, _ = run(ship, hours=720.0, window=4.0)
        strengths = [float(r["strength"]) for r in after["roster"].values()]
        confident = [k for k, r in after["roster"].items()
                     if float(r["strength"]) >= 0.2]

        assert len(after["roster"]) == 500
        assert min(strengths) > 0.0, "a name was struck off the books"
        assert confident, "the institution is sure of nobody"
        # Standing a post is what makes the register sure of you.
        assert set(after.get("watch", {}).values()) <= set(confident)

    def test_hearsay_never_overwrites_a_first_hand_claim(self):
        """Two people must not be able to talk a rumour into certainty."""
        ship = _ready(big_ship(500))

        after, _ = run(ship, hours=48.0, window=4.0)
        posted = set(after.get("watch") or {}.values())
        for body in posted:
            record = after["roster"].get(body)
            if record is not None:
                assert not record.get("heard_from"), body


class TestReachIsAConstraint:
    def test_a_post_nobody_can_walk_to_says_so(self):
        """`out_of_reach` is a third story, distinct from having nobody rated
        and from losing them to a more urgent post. The first ship layout
        failed a whole department this way — for want of a corridor rather
        than for want of people."""
        ship = _ready(big_ship(500))
        # Strand every body far from one department's space.
        far = sorted(ship["scene"]["rooms"])[-1]
        for body in ship["bodies"].values():
            if "supply" in body["competence"]:
                body["place"] = far
        ship["roster"] = seed_roster(ship["bodies"])

        _, events = run(ship, hours=48.0, window=4.0)
        reasons = {e["reason"] for e in events if e["kind"] == "post_unfilled"}

        assert "out_of_reach" in reasons


class TestPolitics:
    def test_blame_attaches_to_the_watch_and_costs_regard(self):
        """Blame follows what the charter BELIEVED it had arranged, so a body
        can be held responsible for a post it was never at. That is the
        intended failure, not a defect in the attribution."""
        ship = _ready(big_ship(500))
        for key, body in ship["bodies"].items():
            if "environmental" in body["competence"]:
                body["available"] = False

        after, events = run(ship, hours=336.0, window=4.0)
        politics = after["politics"]

        assert any(e["kind"] == "upkeep_out_of_band" for e in events)
        assert politics["blame"], "a failure attached to nobody"
        blamed = max(politics["blame"], key=politics["blame"].get)
        dropped = [pair for pair, weight in politics["regard"].items()
                   if regard_pair(pair)[1] == blamed and weight < 1.0]
        assert dropped, "being blamed cost nobody's regard"

    def test_a_starved_link_does_not_blame_the_body_standing_it(self):
        """An institution that blamed the baker for the miller's empty hopper
        would be one this module got wrong."""
        town = _ready(big_town(1000))
        for body in town["bodies"].values():
            if "husbandry" in body["competence"]:
                body["available"] = False
        town["roster"] = seed_roster(town["bodies"])

        after, events = run(town, hours=720.0, window=4.0)
        starved = [e for e in events if e.get("starved_by")]

        assert starved, "the chain did not collapse"
        # Every downstream failure names its input; none of them minted blame.
        assert len(after["politics"]["blame"]) <= 1


class TestReplayAtScale:
    def test_the_same_seed_reproduces_the_run(self):
        a_state, a_events = run(_ready(big_ship(500)), hours=240.0, seed=3)
        b_state, b_events = run(_ready(big_ship(500)), hours=240.0, seed=3)

        assert a_events == b_events
        assert a_state["upkeeps"] == b_state["upkeeps"]
        assert a_state["roster"] == b_state["roster"]
