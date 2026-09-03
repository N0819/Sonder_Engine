"""The town's answer: the watch called out on a threat claim a body with
standing holds, crew pulled off their posts, a guarded place changing the
contest, and a false alarm landing on the caller
(`world/charter_decide.mobilisation_calls`, `charter_intervene.watch_shock`).
"""

from __future__ import annotations

import copy

from world.charter import normalize_charter, run, seed_needs, seed_roster
from world.charter_creature import prey_capability
from world.charter_decide import mobilisation_calls
from world.charter_intervene import (
    MOBILISATION_CREDENCE, MOBILISATION_CREW_CAP, MOBILISATION_HOURS,
    MOBILISE_AUTHORITY, THREAT_KINDS, apply_due, normalize_mobilisation,
    watch_post_key, watch_upkeep_key)
from world.charter_news import WITNESS_STRENGTH, news_claim
from world.charter_predation import predation_round

from charter_worlds import guarded_town, small_town, with_wilds, wolf_pack


def _ready(spec):
    charter = normalize_charter(copy.deepcopy(spec))
    charter["roster"] = seed_roster(charter["bodies"])
    charter["needs"] = seed_needs(charter["bodies"])
    return charter


def _town():
    town = small_town()
    scene = with_wilds(town["scene"], "north_2")
    return _ready(guarded_town(dict(town, scene=scene), pen_place="north_2",
                               hall_place="square"))


def _threat(place, strength=WITNESS_STRENGTH, heard_from=None):
    event = {"kind": "harm_done", "at_hours": 4.0, "place": place,
             "actor": "pack/hound_0", "subject": "herder_0"}
    return news_claim(event, 4.0, strength=strength, heard_from=heard_from)


class TestTheCall:
    def test_defaults_are_the_named_ones(self):
        config = normalize_mobilisation(None)
        assert config["credence"] == MOBILISATION_CREDENCE
        assert config["duration_hours"] == MOBILISATION_HOURS
        assert config["crew_cap"] == MOBILISATION_CREW_CAP
        assert "harm_done" in THREAT_KINDS

    def test_a_body_with_standing_calls_on_a_claim_it_holds(self):
        town = _town()
        town["watch"] = {"reeve": "reeve"}
        claim = _threat("north_2")
        minds = {"reeve": {claim["body"]: claim}}
        calls = mobilisation_calls(town, minds, town["watch"], town["posts"],
                                   town["bodies"], at_hours=8.0)
        assert len(calls) == 1
        call = calls[0]
        assert call["op"] == "watch_shock" and call["place"] == "north_2"
        assert call["called_by"] == "reeve" and call["from_place"] == "square"
        assert call["until_hours"] == 8.0 + town["mobilisation"]["duration_hours"]
        assert 1 <= call["crew"] <= town["mobilisation"]["crew_cap"]

    def test_the_same_claim_in_a_head_without_standing_calls_nothing(self):
        town = _town()
        town["watch"] = {"reeve": "reeve", "herder": "herder_0"}
        claim = _threat("north_2")
        minds = {"herder_0": {claim["body"]: claim}}
        assert mobilisation_calls(town, minds, town["watch"], town["posts"],
                                  town["bodies"], at_hours=8.0) == []
        assert MOBILISE_AUTHORITY in town["posts"]["reeve"]["authority"]
        assert MOBILISE_AUTHORITY not in town["posts"]["herder"]["authority"]

    def test_a_weak_word_does_not_clear_the_credence(self):
        """Strength already carries regard and retelling, so a stranger's
        thin rumour is refused by the same number a neighbour's word
        clears."""
        town = _town()
        town["watch"] = {"reeve": "reeve"}
        weak = _threat("north_2", strength=0.3, heard_from="somebody")
        minds = {"reeve": {weak["body"]: weak}}
        assert mobilisation_calls(town, minds, town["watch"], town["posts"],
                                  town["bodies"], at_hours=8.0) == []

    def test_a_place_already_watched_is_not_called_again(self):
        town = _town()
        town["watch"] = {"reeve": "reeve"}
        town["mobilisations"] = {"north_2": {"since": 0.0}}
        claim = _threat("north_2")
        minds = {"reeve": {claim["body"]: claim}}
        assert mobilisation_calls(town, minds, town["watch"], town["posts"],
                                  town["bodies"], at_hours=8.0) == []

    def test_a_claim_of_another_kind_is_no_threat(self):
        town = _town()
        town["watch"] = {"reeve": "reeve"}
        event = {"kind": "aid_given", "at_hours": 4.0, "place": "north_2",
                 "actor": "herder_0", "subject": "herder_1"}
        claim = news_claim(event, 4.0)
        minds = {"reeve": {claim["body"]: claim}}
        assert mobilisation_calls(town, minds, town["watch"], town["posts"],
                                  town["bodies"], at_hours=8.0) == []


class TestTheWatch:
    def _called(self):
        town = _town()
        town["interventions"] = [{
            "op": "watch_shock", "at_hours": 4.0, "place": "north_2",
            "until_hours": 52.0, "crew": 2, "called_by": "reeve",
            "from_place": "square", "cause": "a threat reported at north_2"}]
        return town

    def test_the_shock_raises_posts_and_an_urgent_upkeep(self):
        town = self._called()
        town, events = apply_due(town, 4.0)
        assert watch_post_key("north_2", 0) in town["posts"]
        assert watch_post_key("north_2", 1) in town["posts"]
        upkeep = town["upkeeps"][watch_upkeep_key("north_2")]
        assert upkeep["level"] == 0.0 and upkeep["place"] == "north_2"
        assert town["priority"][0] == watch_upkeep_key("north_2")
        record = town["mobilisations"]["north_2"]
        assert record["called_by"] == "reeve" and record["harm_seen"] is False
        called = [e for e in events if e["kind"] == "mobilisation_called"]
        assert called and called[0]["place"] == "square"
        assert called[0]["subject"] == "north_2"
        # The stand-down is scheduled where every other physical change is.
        assert any(row["op"] == "watch_stand_down"
                   for row in town["interventions"])

    def test_crew_are_pulled_off_their_posts_and_the_ordinary_work_fails(self):
        """The cost the owner asked for by name: hands on the watch are
        hands off the forge."""
        quiet = _town()
        quiet, quiet_events = run(quiet, 48.0, window=4.0, seed=1)
        town = self._called()
        town, events = run(town, 48.0, window=4.0, seed=1)
        watch_posts = [p for p in town["watch"] if p.startswith("watch:")]
        assert watch_posts, "nobody stood the called watch"
        failed = [e for e in events if e["kind"] == "upkeep_out_of_band"
                  and not e["upkeep"].startswith("guard:")]
        quiet_failed = [e for e in quiet_events
                        if e["kind"] == "upkeep_out_of_band"]
        assert len(failed) >= len(quiet_failed)

    def test_the_watch_stands_down_and_a_false_alarm_lands_on_the_caller(self):
        town = self._called()
        town, _ = run(town, 56.0, window=4.0, seed=1)
        assert "north_2" not in town["mobilisations"]
        assert not [p for p in town["posts"] if p.startswith("watch:")]
        assert watch_upkeep_key("north_2") not in town["upkeeps"]
        assert town["politics"]["blame"].get("reeve", 0) == 1

    def test_a_watch_that_saw_the_threat_is_no_false_alarm(self):
        town = self._called()
        town, _ = apply_due(town, 4.0)
        town["mobilisations"]["north_2"]["harm_seen"] = True
        town["interventions"] = [{
            "op": "watch_stand_down", "at_hours": 52.0, "place": "north_2"}]
        town, events = apply_due(town, 52.0)
        lapsed = [e for e in events if e["kind"] == "mobilisation_lapsed"]
        assert lapsed and lapsed[0]["false_alarm"] is False

    def test_the_round_marks_the_watch_that_met_the_creature(self):
        town = self._called()
        town, _ = apply_due(town, 4.0)
        scene = town["scene"]
        pack = _ready(wolf_pack(scene, ground="north_2", size=4))
        pack["creature"]["encounter_odds"] = 1.0
        pack["creature"]["boldness"] = 1.0
        pack["creature"]["contest"]["caution"] = 0.0
        for body in pack["bodies"].values():
            body["place"] = "north_2"
        town["economy"]["stocks"]["pen"] = {}
        town["watch"] = {watch_post_key("north_2", 0): "smith"}
        town["bodies"]["smith"]["place"] = "north_2"
        for key, body in town["bodies"].items():
            if key != "smith":
                body["place"] = "square"
        states = {"town": town, "pack": pack}
        predation_round(states, 8.0, seed=0)
        assert states["town"]["mobilisations"]["north_2"]["harm_seen"] is True

    def test_a_guarded_place_changes_the_contest(self):
        spec = {"posted_weight": 1.0, "unposted_weight": 0.4,
                "group_bonus": 0.5}
        alone = prey_capability({"condition": "well"}, False, 1, spec)
        guarded = prey_capability({"condition": "well"}, False, 3, spec)
        assert guarded == alone * 2.0

    def test_the_whole_chain_from_a_witnessed_kill_to_the_watch(self):
        """Witnessed at the pen, carried to the square, called from the
        hall, raised at the pen, next window: every step a channel."""
        town = _town()
        # The harm happens where the reeve stands its post, and the reeve
        # sees it; the watch is called there the window after.
        town["carried_events"] = [{
            "kind": "harm_done", "at_hours": 4.0, "place": "square",
            "actor": "pack/hound_0", "subject": "herder_1", "outcome": "dead"}]
        town["bodies"]["herder_1"]["condition"] = "dead"
        town = normalize_charter(town)
        town, events = run(town, 8.0, window=4.0, seed=1)
        assert "square" in town["mobilisations"]
        called = [e for e in events if e["kind"] == "mobilisation_called"]
        assert called and called[0]["actor"] == "reeve"
