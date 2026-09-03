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
    BERTH_CEILING, CREW_SIZE, HEAD_SEATS, HISTORIAN_CITATIONS_PER_ENTRY,
    HISTORIAN_OVERRUN_RETRIES, HISTORIAN_RESIDENT_CAP,
    HISTORIAN_SUMMARY_WORDS, HISTORIAN_TOKENS_BASE,
    HISTORIAN_TOKENS_PER_RESIDENT, HISTORIAN_TURNING_POINTS,
    PLAN_MAX_TOKENS, POPULATION_TOLERANCE, _HISTORIAN_SYSTEM,
    _ensure_shift_crews, _head_posts, _post_berths, _post_seats,
    close_plan, historian_budget, narrate_actual_history)
from world.charter_identity import (
    _consonant_run, _joins, display_name, identity_aliases)

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


class TestAFragmentJoinsAtASyllableBoundary:
    """Harrowmere replay (2026-09-03): "Brgaron Brfordwick", "Brbrookmere",
    "Stanwickwick", "Harfordford". The rule is on the boundary -- a fragment
    ending in a consonant cluster does not join a fragment beginning with a
    consonant, and no fragment joins a copy of itself -- never a list of
    the names it produced."""

    def test_the_boundary_rule(self):
        assert not _joins("br", "gar")          # onset + consonant
        assert not _joins("field", "dale")      # cluster + consonant
        assert not _joins("wick", "wick")       # an echo
        assert _joins("br", "ook")              # onset + vowel
        assert _joins("hal", "in") and _joins("stan", "wick")
        assert _joins("bren", "stone")          # a single consonant may meet a cluster
        assert _consonant_run("west", leading=False) == 2
        assert _consonant_run("field", leading=True) == 1
        # A script the vowel class cannot read is not judged.
        assert _consonant_run("\u3042\u304b", leading=False) == 0
        assert _joins("\u3042\u304b", "\u3055\u305f")

    def test_no_generated_name_meets_three_consonants_or_echoes(self, harrowmere):
        import re
        town = close_plan(harrowmere, population=100)
        for body in _bodies(town).values():
            given, family = body["given_name"], body["family_name"]
            for word in (given, family):
                assert not re.search(r"(.{3,})\1$", word.casefold()), body["name"]
        assert len(_bodies(town)) >= 90

    def test_a_law_of_onsets_and_consonant_middles_still_names_everyone(self):
        from world.charter_identity import _syllable_name
        parts = {"starts": ["br", "st"], "middles": ["gar", "ford"],
                 "ends": ["on", "wick"]}
        for seed in ("a", "b", "c", "d"):
            name = _syllable_name(parts, seed)
            assert name[:1].isupper() and name[2:3] in "aeiou", name

    def test_a_name_carries_the_post_title_and_the_style_stays_an_alias(self):
        profile = {
            "name_format": "{given} {family}",
            "formal_format": "{title} {given} {family}",
            "titles": {"posts": {"reeve": "Reeve"},
                       "ranks": {"head": "Reeve of Harrowmere"}},
        }
        body = {"name": "Bron Fenwick", "given_name": "Bron",
                "family_name": "Fenwick", "rank": "head"}
        assert display_name(body, ["reeve"], profile) == "Reeve Bron Fenwick"
        assert "Reeve of Harrowmere Bron Fenwick" in identity_aliases(
            body, ["reeve"], profile)
        # A rank with no post title keeps rendering, as every ship's captain
        # already does.
        assert display_name(body, (), profile) == "Reeve of Harrowmere Bron Fenwick"


# ---------------------------------------------------------------- budgets

class TestTheHistorianBudgetFollowsTheResidents:

    def test_the_budget_scales_and_stays_under_the_plan_ceiling(self):
        tokens, afforded = historian_budget(108)
        assert afforded == min(
            108, (PLAN_MAX_TOKENS - HISTORIAN_TOKENS_BASE)
            // HISTORIAN_TOKENS_PER_RESIDENT)
        assert tokens == HISTORIAN_TOKENS_BASE \
            + afforded * HISTORIAN_TOKENS_PER_RESIDENT
        assert tokens <= PLAN_MAX_TOKENS
        assert tokens > 7000  # the fixed budget that overran at 108

    def test_a_resident_is_allowed_what_its_entry_costs(self):
        """Replay 2026-09-03: at 90 a resident, 100 residents were cut off
        22,181 characters in. The allowance covers the entry the prompt
        asks for, and the prompt asks for the numbers the engine reserved."""
        assert HISTORIAN_TOKENS_PER_RESIDENT >= 200
        for number in (HISTORIAN_SUMMARY_WORDS, HISTORIAN_CITATIONS_PER_ENTRY,
                       HISTORIAN_TURNING_POINTS):
            assert ("%d" % number) in _HISTORIAN_SYSTEM

    def test_an_overrun_is_retried_with_half_the_residents(self):
        registry = {"items": {"t": {"state": {
            "bodies": {f"b{i}": {"name": f"B{i}"} for i in range(8)},
            "stood": {f"b{i}": {"post": i + 1} for i in range(8)},
            "travelled": {}, "posts": {}, "upkeeps": {}}}}}
        seen = []

        def historian(payload, budget=None):
            seen.append((len(payload["residents"]), budget))
            if len(payload["residents"]) > 2:
                raise ValueError("the location generator returned 22181 "
                                 "characters of unparseable JSON")
            return {"overview": {"summary": "quiet", "event_ids": []},
                    "eras": [], "residents": {}, "institutions": []}

        out = narrate_actual_history({"name": "T"}, registry, [],
                                     model_call=historian)
        assert [n for n, _b in seen] == [8, 4, 2]
        assert out["budget"]["residents"] == 2
        assert out["budget"]["overrun_retries"] == HISTORIAN_OVERRUN_RETRIES
        assert seen[-1][1] == historian_budget(2)[0]

    def test_prose_where_json_should_be_is_not_retried(self):
        registry = {"items": {"t": {"state": {
            "bodies": {"b1": {"name": "B"}}, "stood": {}, "travelled": {},
            "posts": {}, "upkeeps": {}}}}}
        calls = []

        def historian(payload):
            calls.append(1)
            raise ValueError("town generator returned a non-object")

        with pytest.raises(ValueError):
            narrate_actual_history({"name": "T"}, registry, [],
                                   model_call=historian)
        assert calls == [1]

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


# --------------------------------------------------------------- berths

class TestABodySleepsWhereTheWorkItServesIs:
    """Harrowmere replay (2026-09-03): one generic `household_member` post
    served `keep_house_*` for ten houses and carried one address, so 48
    sleepers were berthed behind one door and nine houses held three each."""

    def _plan(self):
        houses = [f"house_{c}" for c in "abcdefghij"]
        rooms = {"lane": {"name": "Lane", "purpose": "lane", "adjacent": []}}
        for house in houses:
            rooms[house] = {"name": house.title(), "purpose": "dwelling",
                            "adjacent": [{"to": "lane", "barrier": "open_door"}]}
        upkeeps = {f"keep_{h}": {"place": h, "floor": 0.3, "level": 1,
                                 "fails_untended": "a_week",
                                 "one_body_restores_in": "a_shift"}
                   for h in houses}
        posts = {f"holder_{h}": {"place": h, "serves": [f"keep_{h}"]}
                 for h in houses}
        posts["member"] = {"place": houses[0],
                           "serves": [f"keep_{h}" for h in houses]}
        populations = [{"post": f"holder_{h}", "count": 1} for h in houses]
        populations.append({"post": "member", "count": 45})
        return {"name": "Lane", "structure": {"key": "lane"}, "rooms": rooms,
                "charters": [{"key": "households", "upkeeps": upkeeps,
                              "posts": posts, "populations": populations}]}

    def test_the_post_is_dealt_round_the_places_its_work_is_served_at(self):
        upkeeps = {"keep_a": {"place": "a"}, "keep_b": {"place": "b"}}
        post = {"place": "a", "serves": ["keep_a", "keep_b"]}
        assert _post_berths(post, upkeeps, {"a", "b"}, "", "a") == ["a", "b"]
        assert _post_berths(post, upkeeps, {"a", "b"}, "b", "a") == ["b"]
        assert _post_berths({"place": "a", "serves": ["keep_a"]},
                            upkeeps, {"a", "b"}, "", "a") == ["a"]

    def test_no_house_holds_more_than_the_ceiling_and_none_is_annexed(self):
        town = close_plan(self._plan())
        berths = {}
        for body in town["charters"]["households"]["bodies"].values():
            berths[body["berth"]] = berths.get(body["berth"], 0) + 1
            assert body["place"] == body["berth"]
        assert max(berths.values()) <= BERTH_CEILING
        assert len(berths) == 10
        assert town["closure"]["berths_split"] == {}

    def test_the_real_plan_deals_its_households_across_its_lanes(self, harrowmere):
        town = close_plan(harrowmere, population=100)
        berths = {}
        for body in _bodies(town).values():
            berths[body["berth"]] = berths.get(body["berth"], 0) + 1
        assert max(berths.values()) <= BERTH_CEILING
