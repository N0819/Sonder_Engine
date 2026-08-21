"""Five hundred hands and a thousand townsfolk, on real room graphs.

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
    normalize_charter, out_of_band, run, seed_roster)

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

        assert elapsed < 30.0, f"a month of 500 hands took {elapsed:.1f}s"


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
                   if pair[1] == blamed and weight < 1.0]
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
