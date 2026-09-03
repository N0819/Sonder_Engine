"""The harm model: a body can be hurt, killed or taken, and the institution
answers in its own vocabulary (`world/charter_harm.py`).

Before this existed every consequence of `harm_done` was wired -- news,
grievance, fear, a trigger change -- and nothing in the package could produce
one. These pin the producer and the four things a death does to an
institution: the post empties, the berth frees, the head post passes by
standing, and the room learns it.
"""

from __future__ import annotations

import copy

from world.charter import normalize_charter, run, seed_needs, seed_roster
from world.charter_harm import (
    GONE, HURT_CAPABILITY, HURT_HEALTH_LEVEL, HURT_RECOVERY_HOURS,
    POSTED_CAPABILITY, UNPOSTED_CAPABILITY, advance_harm, apply_harm,
    capability_of, head_posts, is_gone, normalize_condition)
from world.charter_news import witness

from charter_fixtures import SHIP


def _ready(spec):
    charter = normalize_charter(copy.deepcopy(spec))
    charter["roster"] = seed_roster(charter["bodies"])
    charter["needs"] = seed_needs(charter["bodies"])
    return charter


def _chain():
    """A three-post reporting chain: two hands report to one head."""
    spec = copy.deepcopy(SHIP)
    spec["posts"]["engine_watch"]["reports_to"] = "bridge_watch"
    spec["posts"]["damage_control"]["reports_to"] = "bridge_watch"
    spec["politics"] = {"standing": {"vega": 2.0, "hale": 1.0, "chief": 3.0}}
    return _ready(spec)


class TestTheConditionIsClosed:
    def test_an_unknown_word_reads_well(self):
        assert normalize_condition("wounded") == "well"
        assert normalize_condition(None) == "well"
        for word in ("well", "hurt", "dead", "missing"):
            assert normalize_condition(word.upper()) == word

    def test_a_dead_body_is_unavailable_at_the_normalizer(self):
        """Whatever the record says about `available`, a corpse cannot stand
        a post -- enforced where every path into the state runs."""
        spec = copy.deepcopy(SHIP)
        spec["bodies"]["chief"]["condition"] = "dead"
        spec["bodies"]["chief"]["available"] = True
        charter = normalize_charter(spec)
        assert charter["bodies"]["chief"]["available"] is False
        assert is_gone(charter["bodies"]["chief"])
        assert "dead" in GONE and "missing" in GONE and "hurt" not in GONE

    def test_a_hurt_body_keeps_its_clock_across_a_round_trip(self):
        spec = copy.deepcopy(SHIP)
        spec["bodies"]["chief"]["condition"] = "hurt"
        spec["bodies"]["chief"]["hurt_at_hours"] = 12.5
        charter = normalize_charter(spec)
        assert charter["bodies"]["chief"]["hurt_at_hours"] == 12.5
        assert charter["bodies"]["chief"]["available"] is True


class TestHurt:
    def test_a_hurt_body_fights_worse_and_heals_on_the_clock(self):
        charter = _ready(SHIP)
        charter, events = apply_harm(
            charter, "ramos", by="chief", at_hours=4.0, outcome="hurt")
        body = charter["bodies"]["ramos"]
        assert body["condition"] == "hurt" and body["available"] is True
        assert charter["needs"]["ramos"]["health"]["level"] == HURT_HEALTH_LEVEL
        assert capability_of(body, posted=True) == \
            POSTED_CAPABILITY * HURT_CAPABILITY
        assert capability_of({"condition": "well"}, posted=False) == \
            UNPOSTED_CAPABILITY
        assert [e["kind"] for e in events] == ["harm_done"]
        assert events[0]["actor"] == "chief" and events[0]["subject"] == "ramos"
        assert events[0]["outcome"] == "hurt"

        still, healed = advance_harm(charter, 4.0 + HURT_RECOVERY_HOURS - 1.0)
        assert healed == [] and still["bodies"]["ramos"]["condition"] == "hurt"
        well, healed = advance_harm(charter, 4.0 + HURT_RECOVERY_HOURS)
        assert healed == ["ramos"]
        assert well["bodies"]["ramos"]["condition"] == "well"
        assert "hurt_at_hours" not in well["bodies"]["ramos"]
        # The input was not mutated.
        assert charter["bodies"]["ramos"]["condition"] == "hurt"

    def test_the_step_reports_the_healing_where_the_body_stands(self):
        charter = _ready(SHIP)
        charter, _ = apply_harm(
            charter, "ramos", by="chief", at_hours=0.0, outcome="hurt")
        charter, events = run(charter, hours=HURT_RECOVERY_HOURS + 8.0)
        healed = [e for e in events if e["kind"] == "body_recovered"
                  and e.get("healed") == "hurt"]
        assert len(healed) == 1 and healed[0]["body"] == "ramos"
        assert charter["bodies"]["ramos"]["condition"] == "well"

    def test_a_second_hurt_does_not_restart_the_clock(self):
        charter = _ready(SHIP)
        charter, _ = apply_harm(
            charter, "ramos", by="chief", at_hours=0.0, outcome="hurt")
        charter, _ = apply_harm(
            charter, "ramos", by="chief", at_hours=40.0, outcome="hurt")
        assert charter["bodies"]["ramos"]["hurt_at_hours"] == 0.0


class TestDeath:
    def test_a_death_empties_the_post_frees_the_berth_and_is_final(self):
        charter = _ready(SHIP)
        charter, _ = run(charter, hours=4.0)
        assert charter["watch"]["engine_watch"] in ("chief", "ramos")
        victim = charter["watch"]["engine_watch"]
        charter, events = apply_harm(
            charter, victim, by="raider", at_hours=4.0, outcome="dead")
        body = charter["bodies"][victim]
        assert body["condition"] == "dead"
        assert body["available"] is False and body["stood_down"] is False
        assert body["berth"] == ""
        assert victim not in charter["watch"].values()
        assert events[0]["kind"] == "harm_done"
        assert events[0]["subject"] == victim and events[0]["actor"] == "raider"
        # Needs never pick a dead body up, however rested it becomes.
        charter, later = run(charter, hours=400.0)
        assert charter["bodies"][victim]["available"] is False
        assert charter["bodies"][victim]["condition"] == "dead"
        assert not [e for e in later if e["kind"] == "body_recovered"
                    and e["body"] == victim]

    def test_a_missing_body_stands_nowhere(self):
        charter = _ready(SHIP)
        charter, _ = apply_harm(
            charter, "cook", by="raider", at_hours=1.0, outcome="missing")
        assert charter["bodies"]["cook"]["place"] == ""
        assert charter["bodies"]["cook"]["available"] is False

    def test_harming_a_body_twice_over_is_nothing(self):
        charter = _ready(SHIP)
        charter, first = apply_harm(
            charter, "cook", by="raider", at_hours=1.0, outcome="dead")
        charter, again = apply_harm(
            charter, "cook", by="raider", at_hours=2.0, outcome="hurt")
        assert first and again == []


class TestSuccession:
    def test_head_posts_are_read_from_the_chain(self):
        charter = _chain()
        assert head_posts(charter["posts"]) == ["bridge_watch"]
        # A self-report is no superior; a lone watch is not a head.
        lone = normalize_charter(copy.deepcopy(SHIP))
        assert head_posts(lone["posts"]) == []

    def test_the_head_post_passes_by_standing(self):
        charter = _chain()
        charter, _ = run(charter, hours=4.0)
        # The planner spends the body of LEAST standing on the post, so the
        # head is whoever standing let it be; the succession rule reads the
        # office, not the name.
        holder = charter["watch"]["bridge_watch"]
        assert holder in ("vega", "hale")
        charter, events = apply_harm(
            charter, holder, by="raider", at_hours=4.0, outcome="dead")
        succession = [e for e in events if e["kind"] == "succession"]
        assert len(succession) == 1
        heir = succession[0]["body"]
        # The chief has the highest standing of the living, and the office
        # is now their ordinary duty.
        assert heir == "chief"
        assert charter["bodies"]["chief"]["home_post"] == "bridge_watch"
        standing = charter["politics"]["standing"]
        others = [v for k, v in standing.items() if k != "chief"]
        assert standing["chief"] >= max(others) + 1.0
        assert succession[0]["after"] == holder

    def test_no_succession_for_a_post_that_is_not_a_head(self):
        charter = _chain()
        charter, _ = run(charter, hours=4.0)
        hand = charter["watch"]["engine_watch"]
        charter, events = apply_harm(
            charter, hand, by="raider", at_hours=4.0, outcome="dead")
        assert [e["kind"] for e in events] == ["harm_done"]


class TestTheRoomLearnsIt:
    def test_only_a_body_standing_there_witnesses_the_harm(self):
        """The firewall half: presence is the whole test, exactly as it is
        for every other happening."""
        charter = _ready(SHIP)
        charter["bodies"]["chief"]["place"] = "engine_room"
        charter["bodies"]["ramos"]["place"] = "engine_room"
        charter["bodies"]["vega"]["place"] = "bridge"
        _after, events = apply_harm(
            charter, "ramos", by="raider", at_hours=2.0, outcome="hurt",
            place="engine_room")
        minds, seen = witness({}, charter["bodies"], events, 2.0)
        assert seen == 2
        assert any(c.get("event_kind") == "harm_done"
                   for c in minds["chief"].values())
        assert any(c.get("event_kind") == "harm_done"
                   for c in minds["ramos"].values())
        assert "vega" not in minds
        claim = next(c for c in minds["chief"].values()
                     if c.get("event_kind") == "harm_done")
        assert claim["actor"] == "raider" and claim["toward"] == "ramos"

    def test_a_hurt_hand_is_still_posted_when_it_is_the_only_one(self):
        """Reluctance never makes a body unpostable: a short-handed
        institution still posts the hurt hand, and it heals on watch."""
        spec = copy.deepcopy(SHIP)
        for key in ("ramos", "hale", "cook"):
            spec["bodies"].pop(key)
        charter = _ready(spec)
        charter, _ = apply_harm(
            charter, "chief", by="raider", at_hours=0.0, outcome="hurt")
        charter, _ = run(charter, hours=4.0)
        assert charter["watch"]["engine_watch"] == "chief"
