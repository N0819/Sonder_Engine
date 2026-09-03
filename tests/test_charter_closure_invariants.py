"""The charter closer enforces what the brief can only hope for.

Measured on the Harrowmere playtest (2026-09-02, `tests/data/harrowmere_plan.json`
is the planner's own output for that brief): one brief closed to 14 bodies on
one run and 108 on the next; every head post got a crew of three, so the town
had three reeves and three innkeepers; 65 householders were placed AND
berthed in one house; a fixed 7,000-token historian budget overran at 108
residents; and every generated name reached play as a lower-case mash
("halinham nookfeller"). Each of those is a closure invariant now, and each
carries a named number: `POPULATION_TOLERANCE`, `HEAD_SEATS`, `CREW_SIZE`,
`BERTH_CEILING`, `HISTORIAN_TOKENS_BASE` / `HISTORIAN_TOKENS_PER_RESIDENT`.
"""

from __future__ import annotations

import copy
import json
import os

import pytest

from world.charter_generate import (
    BERTH_CEILING, CREW_SIZE, HEAD_SEATS, HISTORIAN_RESIDENT_CAP,
    HISTORIAN_TOKENS_BASE, HISTORIAN_TOKENS_PER_RESIDENT, PLAN_MAX_TOKENS,
    POPULATION_TOLERANCE, _ensure_shift_crews, _head_posts, _post_seats,
    close_plan, historian_budget)

_HERE = os.path.dirname(os.path.abspath(__file__))


@pytest.fixture(scope="module")
def harrowmere():
    with open(os.path.join(_HERE, "data", "harrowmere_plan.json")) as fh:
        return json.load(fh)


def _bodies(town):
    return {f"{ckey}/{bkey}": body
            for ckey, charter in town["charters"].items()
            for bkey, body in charter["bodies"].items()}


def _holders(town, charter, post):
    return sorted(key for key, body in town["charters"][charter]["bodies"].items()
                  if body.get("home_post") == post)


# ------------------------------------------------------------- head posts

class TestAPostNobodyReportsPastIsOnePerson:

    def test_the_reeve_and_the_innkeeper_hold_their_office_alone(self, harrowmere):
        town = close_plan(harrowmere)
        assert len(_holders(town, "reeves_hall", "reeve")) == HEAD_SEATS
        assert len(_holders(town, "ford_inn", "innkeeper")) == HEAD_SEATS
        assert town["closure"]["heads"] == {
            "reeves_hall/reeve": 1, "ford_inn/innkeeper": 1}

    def test_a_lone_post_is_a_watch_and_keeps_its_crew(self, harrowmere):
        """The smith of a one-post smithy has no subordinate, so nobody
        reports past him -- and nobody reports TO him. He rotates."""
        town = close_plan(harrowmere)
        assert len(_holders(town, "smithy", "smith")) == CREW_SIZE
        assert len(_holders(town, "orrin_shrine", "shrine_keeper")) == CREW_SIZE

    def test_a_post_reporting_to_itself_is_a_root(self):
        posts = {"reeve": {"reports_to": "reeve"},
                 "clerk": {"reports_to": "reeve"}}
        assert _head_posts(posts) == {"reeve"}

    def test_the_subordinates_of_a_head_still_rotate(self, harrowmere):
        town = close_plan(harrowmere)
        assert len(_holders(town, "reeves_hall", "clerk")) == CREW_SIZE
        assert len(_holders(town, "ford_inn", "brewer")) == CREW_SIZE

    def test_authored_seats_and_singular_are_honoured(self):
        posts = {"captain": {"reports_to": "", "seats": 2},
                 "cook": {"reports_to": "captain", "singular": True},
                 "deckhand": {"reports_to": "captain"}}
        assert _post_seats(posts) == {"captain": 2, "cook": 1}

    def test_trimming_a_head_never_drops_a_featured_resident(self):
        bodies = {
            "captain:0001": {"competence": {}, "place": "bridge",
                             "berth": "bridge", "available": True,
                             "home_post": "captain"},
            "captain:0002": {"competence": {}, "place": "bridge",
                             "berth": "bridge", "available": True,
                             "home_post": "captain"},
            "captain:featured:abc": {"name": "Jean-Luc", "competence": {},
                                     "place": "bridge", "berth": "bridge",
                                     "available": True,
                                     "home_post": "captain"},
        }
        posts = {"captain": {"place": "bridge", "requires": {}}}
        added, trimmed = _ensure_shift_crews(
            bodies, posts, seats={"captain": 1})
        assert added == []
        assert set(trimmed) == {"captain:0001", "captain:0002"}
        assert list(bodies) == ["captain:featured:abc"]


# ------------------------------------------------------------- population

class TestTheRequestedPopulationIsAClosureInput:

    def test_a_hundred_asked_is_a_hundred_closed(self, harrowmere):
        town = close_plan(harrowmere, population=100)
        closed = len(_bodies(town))
        assert abs(closed - 100) <= POPULATION_TOLERANCE * 100
        record = town["closure"]["population"]
        assert record["target"] == 100
        assert record["closed"] == closed
        assert record["authored"] != closed  # the planner did not hit it
        assert not [w for w in town["closure"]["warnings"]
                    if w.startswith("population closed")]

    def test_scaling_down_never_scales_a_head_or_below_a_crew(self, harrowmere):
        town = close_plan(harrowmere, population=40)
        assert abs(len(_bodies(town)) - 40) <= POPULATION_TOLERANCE * 40
        assert len(_holders(town, "reeves_hall", "reeve")) == HEAD_SEATS
        for charter, post in (("smithy", "smith"), ("mill", "miller"),
                              ("reeves_hall", "clerk")):
            assert len(_holders(town, charter, post)) >= CREW_SIZE

    def test_a_target_the_crew_floor_cannot_reach_is_said(self, harrowmere):
        """Eight posts times a crew of three is the floor; asking for five
        people is answered with the floor and a warning, not silence."""
        town = close_plan(harrowmere, population=5)
        assert len(_bodies(town)) > 5
        assert any(w.startswith("population closed") and "requested 5" in w
                   for w in town["closure"]["warnings"])

    def test_no_target_leaves_the_planner_counts_alone(self, harrowmere):
        town = close_plan(harrowmere)
        assert town["closure"]["population"]["target"] is None
        assert town["closure"]["population"]["factor"] == 1.0

    def test_closure_is_deterministic(self, harrowmere):
        a = close_plan(harrowmere, population=100)
        b = close_plan(harrowmere, population=100)
        assert json.dumps(a["charters"], sort_keys=True) == \
            json.dumps(b["charters"], sort_keys=True)
        assert json.dumps(a["rooms"], sort_keys=True) == \
            json.dumps(b["rooms"], sort_keys=True)

    def test_the_plan_handed_in_is_not_mutated(self, harrowmere):
        before = copy.deepcopy(harrowmere)
        close_plan(harrowmere, population=100)
        assert harrowmere == before


# ---------------------------------------------------------------- housing

def _berth_counts(town):
    counts = {}
    for body in _bodies(town).values():
        counts[body["berth"]] = counts.get(body["berth"], 0) + 1
    return counts


class TestNoBerthHoldsMoreThanTheCeiling:

    def test_every_berth_is_under_the_ceiling(self, harrowmere):
        town = close_plan(harrowmere, population=100)
        counts = _berth_counts(town)
        assert counts
        assert max(counts.values()) <= BERTH_CEILING
        assert all(berth in town["rooms"] for berth in counts)

    def test_a_workplace_overflows_into_annexes_off_it(self, harrowmere):
        """The householders' lane is where their upkeep is served, so it is
        a workplace: it keeps eight and the rest sleep in rooms hung off it
        that claim no purpose (the Director furnishes a planned room on
        entry; the plan does not know what they are)."""
        town = close_plan(harrowmere, population=100)
        split = town["closure"]["berths_split"]
        assert split["house_lane_east"]["mode"] == "annexes"
        annex = split["house_lane_east"]["rooms"][0]
        room = town["rooms"][annex]
        assert room["purpose"] == ""
        assert [e["to"] for e in room["adjacent"]] == ["house_lane_east"]
        assert any(e["to"] == annex
                   for e in town["rooms"]["house_lane_east"]["adjacent"])
        assert _berth_counts(town)["house_lane_east"] == BERTH_CEILING

    def test_a_dwelling_overflows_into_siblings_beside_it(self):
        """A house that is nobody's post and no upkeep's place is a dwelling:
        its siblings share its purpose and its lane."""
        plan = {
            "name": "Row", "structure": {"key": "row", "max_planned": 10},
            "rooms": {
                "lane": {"name": "The Lane", "purpose": "a lane",
                         "adjacent": [{"to": "house", "barrier": "open_door"},
                                      {"to": "yard", "barrier": "open_door"}]},
                "house": {"name": "Stone House", "purpose": "family dwelling",
                          "adjacent": [{"to": "lane", "barrier": "open_door"}]},
                "yard": {"name": "Work Yard", "purpose": "labour",
                         "adjacent": [{"to": "lane", "barrier": "open_door"}]},
            },
            "charters": [{
                "key": "yard", "naming": {"given": ["Ann", "Bo", "Cy"],
                                          "family": ["Reed"]},
                "upkeeps": {"stack": {"place": "yard", "floor": 0.3,
                                      "fails_untended": "days",
                                      "one_body_restores_in": "hours"}},
                "posts": {"hand": {"place": "yard", "serves": ["stack"],
                                   "requires": {"labour": 1}}},
                "populations": [{"post": "hand", "count": 20,
                                 "competence": {"labour": 1},
                                 "berth": "house"}],
            }],
        }
        town = close_plan(plan)
        split = town["closure"]["berths_split"]["house"]
        assert split["mode"] == "siblings"
        assert len(split["rooms"]) == 2
        for uid in split["rooms"]:
            room = town["rooms"][uid]
            assert room["purpose"] == "family dwelling"
            assert [e["to"] for e in room["adjacent"]] == ["lane"]
            assert any(e["to"] == uid for e in town["rooms"]["lane"]["adjacent"])
        counts = _berth_counts(town)
        assert max(counts.values()) <= BERTH_CEILING
        assert sum(counts.values()) == 20
        # A body standing at home follows its berth; a body at its post
        # stays there.
        for body in _bodies(town).values():
            assert body["place"] == body["berth"] or body["place"] == "yard"

    def test_max_planned_grows_with_the_rooms(self, harrowmere):
        town = close_plan(harrowmere, population=100)
        assert town["structure"]["max_planned"] >= len(town["rooms"])


# ------------------------------------------------------------------ names

def test_an_assembled_name_is_a_proper_noun(harrowmere):
    town = close_plan(harrowmere)
    for body in _bodies(town).values():
        for word in body["name"].split():
            assert word[:1] == word[:1].upper(), body["name"]


# ---------------------------------------------------------------- budgets

class TestTheHistorianBudgetFollowsTheResidents:

    def test_the_budget_scales_and_stays_under_the_plan_ceiling(self):
        tokens, afforded = historian_budget(108)
        assert afforded == 108
        assert tokens == HISTORIAN_TOKENS_BASE + 108 * HISTORIAN_TOKENS_PER_RESIDENT
        assert tokens <= PLAN_MAX_TOKENS
        assert tokens > 7000  # the fixed budget that overran at 108

    def test_residents_are_trimmed_to_what_the_ceiling_affords(self):
        tokens, afforded = historian_budget(HISTORIAN_RESIDENT_CAP)
        assert tokens <= PLAN_MAX_TOKENS
        assert afforded <= HISTORIAN_RESIDENT_CAP
        assert afforded == (PLAN_MAX_TOKENS - HISTORIAN_TOKENS_BASE) \
            // HISTORIAN_TOKENS_PER_RESIDENT

    def test_the_utility_json_calls_turn_reasoning_off(self, monkeypatch):
        from world import charter_generate
        seen = {}

        def fake(role, system, user, **kwargs):
            seen.update(kwargs)
            return "{}"
        monkeypatch.setattr("llm.providers.chat_complete", fake)
        charter_generate._json_call("s", {"a": 1})
        assert seen["reasoning_effort"] == "off"
