"""A creature is an institution whose upkeep is fed from other institutions'
bodies or stock (`world/charter_creature.py`, `world/charter_predation.py`).

What these pin, in the order the design note builds it: the closed schema
and its named defaults; the graph a footprint and a door decide; the
contest and the caution floor; the prey table; senses; spoor read by
presence and by nobody else; the kill ceiling; tribute; and two structural
facts -- a registry of one ordinary charter replays `run` byte for byte,
and the same seed replays the round byte for byte.
"""

from __future__ import annotations

import copy
import json

from world.charter import normalize_charter, run, seed_needs, seed_roster
from world.charter_creature import (
    DEFAULT_CONTEST, DEFAULT_ENCOUNTER_ODDS, DEFAULT_KILL_CEILING,
    DEFAULT_PREY, DEFAULT_SENSE_RANGE_ROOMS, attack_odds, contest,
    creature_neighbors, creature_warnings, hunger_of, is_active,
    normalize_creature, prey_capability, predator_capability, room_fits,
    win_chance)
from world.charter_harm import is_gone
from world.charter_predation import (
    STOCK_WHOLE_LOT, creature_keys, hunt_moves, predation_round, qualified,
    read_spoor, run_registry, standing_spoor)

from charter_worlds import (bandit_band, dragon, guarded_town, small_town,
                            with_wilds, wolf_pack)


def _ready(spec, **day):
    charter = normalize_charter(copy.deepcopy(spec))
    charter["roster"] = seed_roster(charter["bodies"])
    charter["needs"] = seed_needs(charter["bodies"])
    charter.update(day)
    return charter


def _town_and(kind, *, size=None, day=None):
    town = small_town()
    scene = with_wilds(town["scene"], "north_2")
    town = guarded_town(dict(town, scene=scene), pen_place="north_2",
                        hall_place="square")
    if kind == "pack":
        beast = wolf_pack(scene, ground="north_2", size=size or 4)
    elif kind == "band":
        beast = bandit_band(scene, ground="north_2", size=size or 5)
    else:
        beast = dragon(scene, ground="north_2", town_key="town")
    day = day or {}
    return {"town": _ready(town, **day), beast["key"]: _ready(beast, **day)}


def _dumps(states):
    return json.dumps(states, sort_keys=True, default=str)


class TestTheSchemaIsClosed:
    def test_an_ordinary_institution_has_no_creature(self):
        charter = normalize_charter(copy.deepcopy(small_town()))
        assert charter["creature"] is None
        assert charter["spoor"] == [] and charter["carried_events"] == []
        assert creature_keys({"town": charter}) == []

    def test_defaults_are_the_named_ones(self):
        record = normalize_creature({"fed": {"upkeep": "belly"}})
        assert record["prey"] == list(DEFAULT_PREY)
        assert record["senses"]["range_rooms"] == DEFAULT_SENSE_RANGE_ROOMS
        assert record["encounter_odds"] == DEFAULT_ENCOUNTER_ODDS
        assert record["kill_ceiling"] == DEFAULT_KILL_CEILING
        assert record["contest"] == DEFAULT_CONTEST
        assert record["footprint"] == "point"
        assert record["can_open_doors"] is False
        assert "refused" not in record

    def test_an_unreadable_field_is_refused_with_a_notice(self):
        record = normalize_creature({
            "prey": ["stock", "children"], "contest": {"teeth": 3}})
        assert record["prey"] == ["stock"]
        assert "children" in record["refused"] and "teeth" in record["refused"]
        assert creature_warnings({"prey": ["children"]})

    def test_a_creature_round_trips_the_normalizer(self):
        beast = _ready(wolf_pack(with_wilds(small_town()["scene"], "north_2"),
                                 ground="north_2"))
        again = normalize_charter(json.loads(json.dumps(beast)))
        assert again["creature"] == beast["creature"]


class TestFootprintAndDoors:
    def test_a_shut_door_holds_what_cannot_open_it(self):
        scene = {"rooms": {
            "a": {"adjacent": [{"to": "b", "barrier": "closed_door"}]},
            "b": {"adjacent": [{"to": "a", "barrier": "closed_door"}]},
        }}
        held = creature_neighbors(scene, {"can_open_doors": False})
        assert "b" not in held.get("a", set())
        opens = creature_neighbors(scene, {"can_open_doors": True})
        assert "b" in opens["a"] and "a" in opens["b"]

    def test_a_room_too_small_for_the_footprint_is_no_neighbour(self):
        scene = with_wilds(small_town()["scene"], "north_2")
        assert room_fits(scene["rooms"]["burrow"], "small")
        assert not room_fits(scene["rooms"]["burrow"], "large")
        assert not room_fits(scene["rooms"]["den"], "run")
        assert room_fits(scene["rooms"]["cave"], "run")
        # An unsized room fits everything: the ordinary case is not a wall.
        assert room_fits(scene["rooms"]["wood"], "run")
        large = creature_neighbors(scene, {"footprint": "large"})
        assert "burrow" not in large["wood"] and "cave" in large["wood"]
        small = creature_neighbors(scene, {"footprint": "small"})
        assert "burrow" in small["wood"]

    def test_the_walk_holds_at_the_door_rather_than_rerouting(self):
        """`charter_move._advance` re-checks each edge against the map the
        creature is handed and holds the body: no second mover."""
        scene = with_wilds(small_town()["scene"], "north_2")
        scene["rooms"]["wood"]["adjacent"] = [
            dict(e, barrier="closed_door") if e["to"] == "north_2" else e
            for e in scene["rooms"]["wood"]["adjacent"]]
        scene["rooms"]["north_2"]["adjacent"] = [
            dict(e, barrier="closed_door") if e["to"] == "wood" else e
            for e in scene["rooms"]["north_2"]["adjacent"]]
        pack = _ready(wolf_pack(scene, ground="north_2"))
        states, _ = run_registry({"pack": pack}, 24.0, seed=1)
        assert all(b["place"] in ("den", "wood")
                   for b in states["pack"]["bodies"].values())


class TestTheContest:
    def test_posted_beats_unposted_and_a_group_beats_a_straggler(self):
        spec = DEFAULT_CONTEST
        alone = prey_capability({"condition": "well"}, False, 1, spec)
        guard = prey_capability({"condition": "well"}, True, 1, spec)
        crowd = prey_capability({"condition": "well"}, False, 4, spec)
        assert guard > alone and crowd > alone
        hurt = prey_capability({"condition": "hurt"}, True, 1, spec)
        assert hurt < guard
        pack = predator_capability(
            [{"condition": "well"}, {"condition": "hurt"}], spec)
        assert pack == 1.5

    def test_the_draw_decides_and_replays(self):
        assert contest(3.0, 1.0, 0.7) is True
        assert contest(3.0, 1.0, 0.8) is False
        assert contest(0.0, 0.0, 0.0) is False
        assert win_chance(1.0, 3.0) == 0.25

    def test_a_hopeless_attack_is_not_made(self):
        """Caution: a creature does not throw itself at a guarded gate every
        window until it dies. Nothing is recorded, because nothing a body
        could see happened."""
        states = _town_and("pack", size=1)
        town = states["town"]
        pack = states["pack"]
        pack["creature"]["contest"]["caution"] = 0.9
        pack["creature"]["prey"] = ["posted"]
        pack["bodies"]["hound_0"]["place"] = "north_2"
        town["watch"] = {"herder": "herder_0"}
        town["bodies"]["herder_0"]["place"] = "north_2"
        for key in ("herder_1", "herder_2"):
            town["bodies"][key]["place"] = "square"
        events = predation_round(states, 4.0, seed=0)
        assert events == {}
        assert town["bodies"]["herder_0"]["condition"] == "well"


class TestThePreyTable:
    def test_stock_before_bodies_and_only_whole_lots(self):
        states = _town_and("pack", size=2)
        town, pack = states["town"], states["pack"]
        pack["creature"]["encounter_odds"] = 1.0
        pack["creature"]["boldness"] = 1.0
        for body in pack["bodies"].values():
            body["place"] = "north_2"
        before = town["economy"]["stocks"]["pen"]["livestock"]
        events = predation_round(states, 4.0, seed=0)
        taken = [e for e in events.get("town", ()) if e["kind"] == "stock_taken"]
        assert len(taken) == 1 and taken[0]["amount"] == 1.0
        assert town["economy"]["stocks"]["pen"]["livestock"] == before - 1.0
        assert pack["economy"]["stocks"]["pack"]["livestock"] == 1.0
        assert not [e for e in events.get("town", ())
                    if e["kind"] == "harm_done"]
        # Under a whole lot, stock is nothing to take.
        town["economy"]["stocks"]["pen"]["livestock"] = STOCK_WHOLE_LOT - 0.5
        events = predation_round(states, 8.0, seed=0)
        assert not [e for e in events.get("town", ())
                    if e["kind"] == "stock_taken"]

    def test_with_no_stock_the_straggler_is_taken_before_the_guard(self):
        states = _town_and("pack", size=4)
        town, pack = states["town"], states["pack"]
        town["economy"]["stocks"]["pen"] = {}
        pack["creature"]["encounter_odds"] = 1.0
        pack["creature"]["boldness"] = 1.0
        pack["creature"]["contest"]["capability"] = 10.0
        for body in pack["bodies"].values():
            body["place"] = "north_2"
        town["watch"] = {"herder": "herder_0"}
        for key in ("herder_0", "herder_1"):
            town["bodies"][key]["place"] = "north_2"
        town["bodies"]["herder_2"]["place"] = "square"
        events = predation_round(states, 4.0, seed=0)
        harm = [e for e in events["town"] if e["kind"] == "harm_done"]
        assert len(harm) == 1
        assert harm[0]["subject"] == "herder_1"      # the unposted one
        assert harm[0]["actor"].startswith("pack/")
        assert harm[0]["outcome"] == "dead"
        assert town["bodies"]["herder_1"]["condition"] == "dead"
        assert town["bodies"]["herder_0"]["condition"] == "well"
        # The creature's own record names the victim as another
        # institution's body, never as one of its own.
        mine = [e for e in events["pack"] if e["kind"] == "harm_done"]
        assert mine[0]["subject"] == qualified("town", "herder_1")
        assert hunger_of(pack) < 0.3

    def test_a_creature_that_takes_leaves_a_body_missing(self):
        states = _town_and("band", size=5)
        town, band = states["town"], states["band"]
        town["economy"]["stocks"]["pen"] = {}
        band["creature"]["encounter_odds"] = 1.0
        band["creature"]["boldness"] = 1.0
        band["creature"]["contest"]["capability"] = 10.0
        for body in band["bodies"].values():
            body["place"] = "north_2"
        town["watch"] = {}
        town["bodies"]["herder_0"]["place"] = "north_2"
        for key in ("herder_1", "herder_2"):
            town["bodies"][key]["place"] = "square"
        events = predation_round(states, 4.0, seed=0)
        harm = [e for e in events["town"] if e["kind"] == "harm_done"]
        assert harm and harm[0]["outcome"] == "missing"
        assert town["bodies"]["herder_0"]["condition"] == "missing"
        assert town["bodies"]["herder_0"]["place"] == ""
        assert is_gone(town["bodies"]["herder_0"])

    def test_the_guard_that_wins_hurts_the_attacker(self):
        states = _town_and("pack", size=1)
        town, pack = states["town"], states["pack"]
        town["economy"]["stocks"]["pen"] = {}
        pack["creature"]["encounter_odds"] = 1.0
        pack["creature"]["boldness"] = 1.0
        pack["creature"]["contest"]["capability"] = 0.05
        pack["creature"]["contest"]["caution"] = 0.0
        pack["creature"]["prey"] = ["posted"]
        pack["bodies"]["hound_0"]["place"] = "north_2"
        town["watch"] = {"herder": "herder_0"}
        town["bodies"]["herder_0"]["place"] = "north_2"
        for key in ("herder_1", "herder_2"):
            town["bodies"][key]["place"] = "square"
        events = predation_round(states, 4.0, seed=0)
        assert pack["bodies"]["hound_0"]["condition"] == "hurt"
        mine = [e for e in events["pack"] if e["kind"] == "harm_done"]
        assert mine[0]["subject"] == "hound_0"
        assert mine[0]["actor"] == qualified("town", "herder_0")
        theirs = [e for e in events["town"] if e["kind"] == "harm_done"]
        assert theirs[0]["actor"] == "herder_0" and theirs[0]["outcome"] == "hurt"

    def test_a_figure_is_never_prey_by_default(self):
        assert "figure" not in DEFAULT_PREY


class TestTheKillCeiling:
    def test_one_institution_kills_at_most_the_ceiling_per_window(self):
        states = _town_and("pack", size=6)
        town, pack = states["town"], states["pack"]
        town["economy"]["stocks"]["pen"] = {}
        pack["creature"]["encounter_odds"] = 1.0
        pack["creature"]["boldness"] = 1.0
        pack["creature"]["kill_ceiling"] = 2
        pack["creature"]["contest"]["capability"] = 10.0
        # Two hunting places, each with a straggler.
        for index, body in enumerate(pack["bodies"].values()):
            body["place"] = "north_2" if index % 2 else "wood"
        town["watch"] = {}
        town["bodies"]["herder_0"]["place"] = "north_2"
        town["bodies"]["herder_1"]["place"] = "wood"
        town["bodies"]["herder_2"]["place"] = "square"
        town["bodies"]["smith"]["place"] = "wood"
        events = predation_round(states, 4.0, seed=0)
        dead = [e for e in events["town"] if e["kind"] == "harm_done"
                and e["outcome"] == "dead"]
        assert len(dead) == 2
        pack["creature"]["kill_ceiling"] = 0
        events = predation_round(states, 8.0, seed=0)
        assert not [e for e in events.get("town", ())
                    if e["kind"] == "harm_done"]


class TestSenses:
    def test_a_hunter_walks_toward_prey_it_noticed_and_no_further(self):
        states = _town_and("pack", size=1)
        town, pack = states["town"], states["pack"]
        pack["creature"]["senses"]["range_rooms"] = 1
        # Prey two rooms away is out of range; one room away is not.
        town["economy"]["stocks"]["pen"] = {}
        for body in town["bodies"].values():
            body["place"] = "square"
        pack["bodies"]["hound_0"]["place"] = "den"
        from world.charter_predation import _company
        bodies_at, stock_at = _company(states)
        neighbors = creature_neighbors(pack["scene"], pack["creature"])
        assert hunt_moves(states, "pack", bodies_at, stock_at, neighbors,
                          0, 4.0) == {}
        town["bodies"]["herder_0"]["place"] = "wood"
        bodies_at, stock_at = _company(states)
        assert hunt_moves(states, "pack", bodies_at, stock_at, neighbors,
                          0, 4.0) == {"hound_0": "wood"}

    def test_the_night_creature_sleeps_by_day(self):
        pack = _ready(wolf_pack(with_wilds(small_town()["scene"], "north_2"),
                                ground="north_2"),
                      day_anchor_hours=12.0, day_length_hours=24.0)
        assert not is_active(pack, 0.0)          # midday
        assert is_active(pack, 11.0)             # 23:00
        untold = _ready(wolf_pack(with_wilds(small_town()["scene"], "north_2"),
                                  ground="north_2"))
        assert is_active(untold, 0.0)            # no anchor: always


class TestSpoor:
    def _kill(self):
        states = _town_and("pack", size=4)
        town, pack = states["town"], states["pack"]
        town["economy"]["stocks"]["pen"] = {}
        pack["creature"]["encounter_odds"] = 1.0
        pack["creature"]["boldness"] = 1.0
        pack["creature"]["contest"]["capability"] = 10.0
        for body in pack["bodies"].values():
            body["place"] = "north_2"
        town["watch"] = {}
        town["bodies"]["herder_0"]["place"] = "north_2"
        for key in ("herder_1", "herder_2"):
            town["bodies"][key]["place"] = "square"
        predation_round(states, 4.0, seed=0)
        return states

    def test_a_kill_leaves_spoor_that_stands_for_its_hours(self):
        states = self._kill()
        rows = standing_spoor(states, 4.0)
        assert rows and all(owner == "pack" for owner, _ in rows)
        kinds = {row["kind"] for _, row in rows}
        assert "harm_done" in kinds
        assert all(row["until_hours"] == 4.0 + 72.0 for _, row in rows)
        assert standing_spoor(states, 4.0 + 72.0) == []

    def test_only_a_body_standing_there_reads_it(self):
        """THE FIREWALL HALF. A carcass is read by whoever comes upon it and
        by nobody else; the creature that left it does not read its own."""
        states = self._kill()
        town, pack = states["town"], states["pack"]
        # Nobody from the town is left standing at the pen; move somebody
        # in and somebody far away.
        town["bodies"]["smith"]["place"] = "north_2"
        town["bodies"]["tapster"]["place"] = "house_b_back"
        read = read_spoor(states, 8.0)
        assert read >= 1
        smith = town["minds"]["smith"]
        held = [c for c in smith.values() if c.get("provenance") == "read"]
        assert held and held[0]["event_kind"] == "harm_done"
        assert held[0]["heard_from"] is None
        assert "tapster" not in town["minds"] or not [
            c for c in town["minds"]["tapster"].values()
            if c.get("provenance") == "read"]
        assert not any(c.get("provenance") == "read"
                       for held in pack.get("minds", {}).values()
                       for c in held.values())
        # Reading twice is one claim.
        again = read_spoor(states, 12.0)
        assert again == 0

    def test_spoor_is_swept_when_it_expires(self):
        states = self._kill()
        read_spoor(states, 4.0 + 100.0)
        assert states["pack"]["spoor"] == []


class TestTribute:
    def test_a_bargain_holds_while_the_town_pays(self):
        states = _town_and("wyrm")
        town, wyrm = states["town"], states["wyrm"]
        wyrm["bodies"]["wyrm"]["place"] = "north_2"
        wyrm["creature"]["encounter_odds"] = 1.0
        events = predation_round(states, 4.0, seed=0)
        assert not [e for e in events.get("town", ())
                    if e["kind"] in ("harm_done", "stock_taken")]
        record = next(iter(wyrm["commitments"].values()))
        assert record["kind"] == "bargain" and record["state"] == "accepted"
        assert record["beneficiary"] == "town"
        # The first lot is collected the day the bargain stands, and the
        # next not before its cadence.
        paid = [e for e in events["wyrm"] if e["kind"] == "goods_exchanged"]
        assert paid and paid[0]["reason"] == "tribute"
        assert wyrm["economy"]["stocks"]["hoard"]["silver"] == 1.0
        assert town["economy"]["stocks"]["treasury"]["silver"] == 5.0
        events = predation_round(states, 8.0, seed=0)
        assert not [e for e in events.get("wyrm", ())
                    if e["kind"] == "goods_exchanged"]
        events = predation_round(states, 4.0 + 168.0, seed=0)
        assert [e for e in events["wyrm"] if e["kind"] == "goods_exchanged"]
        assert wyrm["economy"]["stocks"]["hoard"]["silver"] == 2.0

    def test_a_town_that_cannot_pay_defaults_and_is_hunted(self):
        states = _town_and("wyrm")
        town, wyrm = states["town"], states["wyrm"]
        town["economy"]["stocks"]["treasury"] = {}
        predation_round(states, 4.0, seed=0)
        events = predation_round(states, 4.0 + 168.0, seed=0)
        defaults = [e for e in events["town"]
                    if e["kind"] == "commitment_defaulted"]
        assert defaults
        record = next(iter(wyrm["commitments"].values()))
        assert record["state"] == "defaulted"
        wyrm["bodies"]["wyrm"]["place"] = "north_2"
        wyrm["creature"]["encounter_odds"] = 1.0
        wyrm["creature"]["boldness"] = 1.0
        events = predation_round(states, 4.0 + 172.0, seed=0)
        assert [e for e in events["town"] if e["kind"] == "stock_taken"]

    def test_a_creature_left_hungry_repudiates(self):
        states = _town_and("wyrm")
        wyrm = states["wyrm"]
        wyrm["upkeeps"]["maw"]["level"] = 0.1
        events = predation_round(states, 4.0, seed=0)
        assert [e for e in events["wyrm"] if e["kind"] == "commitment_repudiated"]
        record = next(iter(wyrm["commitments"].values()))
        assert record["state"] == "repudiated"


class TestTheRegistryStepper:
    def test_one_ordinary_charter_is_byte_identical_to_run(self):
        """THE STRUCTURAL FACT. A town with no creature in its registry is
        advanced by exactly the code it always was."""
        town = _ready(small_town())
        alone, events_alone = run(copy.deepcopy(town), 48.0, window=4.0,
                                  seed=3)
        states, events = run_registry({"town": copy.deepcopy(town)}, 48.0,
                                      window=4.0, seed=3)
        assert _dumps(states["town"]) == _dumps(alone)
        assert events["town"] == events_alone

    def test_the_same_seed_replays_the_round_byte_for_byte(self):
        one = _town_and("pack")
        two = copy.deepcopy(one)
        a, ea = run_registry(one, 96.0, seed=7)
        b, eb = run_registry(two, 96.0, seed=7)
        assert _dumps(a) == _dumps(b) and ea == eb
        c, ec = run_registry(copy.deepcopy(one), 96.0, seed=8)
        assert _dumps(c) != _dumps(a)

    def test_a_month_of_predation_reaches_the_town_through_channels(self):
        """Kills land on bodies; the town knows only what reached it; the
        events are reported once, at the window that lived through them."""
        states = _town_and("pack", day={"day_anchor_hours": 0.0,
                                        "day_length_hours": 24.0})
        states, events = run_registry(states, 720.0, seed=3)
        town = states["town"]
        harm = [e for e in events["town"] if e["kind"] == "harm_done"
                and e.get("outcome") in ("dead", "missing")]
        gone = [k for k, b in town["bodies"].items() if is_gone(b)]
        assert len(harm) == len(gone) and harm
        keys = [e["at_hours"] for e in events["town"] if e["kind"] == "harm_done"]
        assert len(keys) == len(set(zip(keys, [e["subject"] for e in events["town"]
                                               if e["kind"] == "harm_done"])))
        # News decays; the experience of having stood through it does not.
        knowing = [k for k, rows in town["experiences"].items()
                   if any(r.get("kind") == "stood_through"
                          and r.get("event_kind") == "harm_done"
                          for r in rows)]
        assert knowing
        # A dead body holds no new claim and stands in no room.
        from world.charter_talk import co_present
        rooms = co_present(town["bodies"])
        assert not any(k in keys for keys in rooms.values() for k in gone)

    def test_the_hunter_starves_when_it_catches_nothing(self):
        """The famine spiral, applied to the hunter: an empty fed upkeep
        drifts under its floor and the bodies fed by it go under."""
        scene = with_wilds(small_town()["scene"], "north_2")
        pack = wolf_pack(scene, ground="north_2", size=2)
        pack["upkeeps"]["belly"]["level"] = 0.35
        pack["upkeeps"]["belly"]["drift_per_hour"] = 0.05
        charter = _ready(pack)
        for held in charter["needs"].values():
            held["sustenance"]["fed_by"] = "belly"
        states, events = run_registry({"pack": charter}, 240.0, seed=1)
        assert [e for e in events["pack"] if e["kind"] == "upkeep_out_of_band"]
        assert [e for e in events["pack"] if e["kind"] == "body_unable"]
        assert hunger_of(states["pack"]) > 0.9
        assert attack_odds(states["pack"]["creature"], 1.0) > \
            attack_odds(states["pack"]["creature"], 0.0)
