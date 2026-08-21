"""One belief set per head, and the thing it exists to make possible.

With a single institutional roster, "what is believed about X" has exactly one
answer and there is no way for A to be wrong where B is right. Per-head belief
is only worth its cost if disagreement actually appears — so that is what is
asserted here, not the plumbing.

The defect this file exists downstream of: `co_present` filtered out every
body that could not stand a post, so nothing anywhere had a channel by which
the fact that somebody had gone down could travel. Thirty hands taken out of
five hundred, two simulated days later, bodies disagreed about: zero. Being
seen and being able to serve are different things, and collapsing them cost
the model its only route to being interestingly wrong.
"""

from __future__ import annotations

from world.charter import (
    RECALL_CAP, acquaintance, believes, contested, converse, decay_minds,
    divergence, normalize_charter, run, see, seed_roster, witnessed)

from charter_worlds import big_ship


def _ready(spec):
    charter = normalize_charter(spec)
    charter["roster"] = seed_roster(charter["bodies"])
    return charter


class TestHeadsAcquireOpinions:
    def test_a_crew_comes_to_know_the_people_it_shares_rooms_with(self):
        after, _ = run(_ready(big_ship(500)), hours=720.0, window=4.0)
        known = acquaintance(after["minds"])

        assert len(known) == 500
        assert min(known.values()) > 0, "somebody met nobody in a month"
        assert max(known.values()) <= RECALL_CAP

    def test_a_head_holds_no_more_than_it_can_carry(self):
        """Bounded acquaintance is the garbage collector and the realism in
        one rule — an unbounded mind is what would make this quadratic."""
        minds = {"a": {f"s{i}": {"body": f"s{i}", "strength": 1.0 - i / 200.0,
                                 "competence": {}, "believed_available": True,
                                 "as_of_hours": 0.0}
                       for i in range(RECALL_CAP * 3)}}

        after = decay_minds(minds, 1.0)

        assert len(after["a"]) == RECALL_CAP
        # The strongest survive, not an arbitrary slice.
        assert "s0" in after["a"]


class TestDisagreement:
    """The whole point. With one roster every one of these is impossible."""

    def test_nothing_is_disputed_while_nothing_changes(self):
        after, _ = run(_ready(big_ship(500)), hours=240.0, window=4.0)

        assert contested(after["minds"], after["bodies"]) == []

    def test_a_body_going_down_is_believed_by_some_and_not_others(self):
        charter = _ready(big_ship(500))
        charter, _ = run(charter, hours=240.0, window=4.0)

        down = [k for k, b in charter["bodies"].items()
                if "signals" in b["competence"]][:30]
        for key in down:
            charter["bodies"][key]["available"] = False

        after, _ = run(charter, hours=24.0, window=4.0)
        disputed = contested(after["minds"], after["bodies"])

        assert disputed, "nobody noticed thirty people go down"
        views = divergence(after["minds"], disputed[0])
        assert len(views) > 1
        # Both readings are genuinely held: some heads have seen them since,
        # some are still carrying the last thing they knew.
        assert {available for available, _competence in views} == {True, False}

    def test_the_news_travels_and_the_institution_converges(self):
        """Disagreement is a FRONT, not a permanent state. It appears when the
        world changes, spreads, and settles once everyone has been in a room
        with the truth."""
        charter = _ready(big_ship(500))
        charter, _ = run(charter, hours=240.0, window=4.0)
        for key in [k for k, b in charter["bodies"].items()
                    if "signals" in b["competence"]][:30]:
            charter["bodies"][key]["available"] = False

        early, _ = run({**charter}, hours=24.0, window=4.0)
        late, _ = run({**charter}, hours=168.0, window=4.0)

        assert len(contested(early["minds"], early["bodies"])) > 0
        assert len(contested(late["minds"], late["bodies"])) == 0


class TestSeeingIsNotServing:
    def test_a_body_that_cannot_stand_a_post_can_still_be_seen(self):
        bodies = {
            "down": {"key": "down", "competence": {}, "available": False,
                     "place": "room"},
            "up": {"key": "up", "competence": {}, "available": True,
                   "place": "room"},
        }

        pairs = witnessed(bodies)
        subjects = {subject for subject, _watcher, _place in pairs}

        assert "down" in subjects, "an absent body vanished from its own room"
        # ...but it does no watching and no talking.
        assert all(watcher == "up" for _s, watcher, _p in pairs)

    def test_hearsay_never_beats_a_seeing(self):
        bodies = {
            "a": {"key": "a", "competence": {"x": 1}, "available": True,
                  "place": "room"},
            "b": {"key": "b", "competence": {"x": 1}, "available": True,
                  "place": "room"},
        }
        minds = {}
        see(minds, "a", bodies["b"], 10.0)
        first = dict(believes(minds, "a", "b"))

        minds, _ = converse(minds, bodies, seed=1, at_hours=11.0)

        assert believes(minds, "a", "b")["strength"] >= first["strength"]
