"""A supply chain, and the two defects the town fixture found.

The ship and the abbey are independent conditions. A town is a CHAIN — field
to mill to oven to counter — and adding one was what made the model grow
`depends_on`. Building it immediately found two things the ship never could:

  1. a fully staffed town starved its own shop on day two, because the
     planner spent its only trader on a job any labourer could do;
  2. a two-week run wrote 169 rows for five things happening, because an
     unfilled post re-reported every window — the exact "storage grows with
     incident, not with time" rule the design note states and this module had
     applied to upkeeps only.

Both are pinned below, because both are cheap to reintroduce.
"""

from __future__ import annotations

import copy

from world.charter import (
    criticality, normalize_charter, out_of_band, run, seed_roster,
    starving_input, supply_factor)

from charter_fixtures import TOWN


def _ready(spec):
    charter = normalize_charter(copy.deepcopy(spec))
    charter["roster"] = seed_roster(charter["bodies"])
    return charter


class TestTheChain:
    def test_a_staffed_town_feeds_itself_for_a_month_in_silence(self):
        town, events = run(_ready(TOWN), hours=720.0, window=4.0)

        assert events == []
        for key, upkeep in town["upkeeps"].items():
            assert not out_of_band(upkeep), (key, upkeep["level"])

    def test_losing_the_field_collapses_everything_downstream_in_order(self):
        """One absent body, one field, and no authored step in between.

        The order is the assertion: grain fails first because it is what was
        untended, and each link below it fails later and names the link above
        it as the cause. A log that recorded the counter running dry without
        saying it ran out of bread would be recording a symptom.
        """
        town = _ready(TOWN)
        town["bodies"]["maud"]["available"] = False
        town["bodies"]["wynn"]["available"] = False

        after, events = run(town, hours=720.0, window=4.0)
        failures = [e for e in events if e["kind"] == "upkeep_out_of_band"]
        order = [e["upkeep"] for e in failures]

        assert order == ["grain_standing", "flour_milled", "bread_baked",
                         "counter_stocked"]
        blamed = {e["upkeep"]: e["starved_by"] for e in failures}
        assert blamed["grain_standing"] is None, "nothing upstream starved it"
        assert blamed["flour_milled"] == "grain_standing"
        assert blamed["bread_baked"] == "flour_milled"
        assert blamed["counter_stocked"] == "bread_baked"
        # And each one fell strictly after the one it depended on.
        hours = [e["at_hours"] for e in failures]
        assert hours == sorted(hours)
        assert out_of_band(after["upkeeps"]["counter_stocked"])

    def test_the_weakest_input_governs_not_the_average(self):
        """A chain is as strong as its thinnest link. Averaging would let an
        abundant input paper over an exhausted one, which is the whole failure
        mode a supply chain has."""
        upkeeps = {"a": {"level": 1.0}, "b": {"level": 0.1}}

        assert supply_factor({"depends_on": ["a", "b"]}, upkeeps) == 0.1
        assert starving_input({"depends_on": ["a", "b"]}, upkeeps) == "b"
        assert supply_factor({"depends_on": []}, upkeeps) == 1.0


class TestSpendTheReplaceableBodyFirst:
    """Defect 1. No institution puts its only rated specialist on a job any
    hand could do, and the first planner did exactly that every window."""

    def test_the_only_trader_is_not_spent_on_general_labour(self):
        town = _ready(TOWN)
        plan_events = run(town, hours=4.0, window=4.0)[1]

        assert plan_events == [], plan_events

    def test_criticality_counts_posts_only_one_body_can_stand(self):
        town = _ready(TOWN)
        scarce = criticality(town)

        # One trade tag in the town, one baker, one miller: each is the sole
        # candidate for their own post and must be spent last elsewhere.
        assert scarce.get("alder") == 1
        assert scarce.get("greta") == 1
        assert scarce.get("tobin") == 1
        # Bodies holding only general labour are nobody's last resort.
        assert scarce.get("harrow", 0) == 0
        assert scarce.get("pell", 0) == 0


class TestAStandingConditionIsOneFact:
    """Defect 2, and the more serious of the two, because it is the cost
    model. A post unfilled for a fortnight is one fact, not eighty-four."""

    def test_an_unfilled_post_is_reported_once_not_every_window(self):
        town = _ready(TOWN)
        town["bodies"]["maud"]["available"] = False
        town["bodies"]["wynn"]["available"] = False

        _, events = run(town, hours=720.0, window=4.0)
        unfilled = [e for e in events if e["kind"] == "post_unfilled"
                    and e["post"] == "field_hand"]

        assert len(unfilled) == 1
        # 180 windows in a month; a per-window report would be two orders of
        # magnitude more than the whole event log.
        assert len(events) < 10

    def test_a_post_that_is_filled_again_says_so(self):
        """The standing condition has to CLEAR, or a repair is invisible and
        a second failure of the same post is never reported."""
        town = _ready(TOWN)
        town["bodies"]["greta"]["available"] = False

        broken, first = run(town, hours=48.0, window=4.0)
        assert any(e["kind"] == "post_believed_filled" for e in first)

        broken["bodies"]["greta"]["available"] = True
        _, second = run(broken, hours=48.0, window=4.0)

        assert not any(e["kind"] == "post_believed_filled" for e in second)
