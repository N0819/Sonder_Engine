"""Authored rules and ops for creatures: the `side` a change carries, the
institution pass (`fire_institution_rules`), the widened interventions, and
the one revert that used to be wrong.
"""

from __future__ import annotations

import copy

from world.charter import normalize_charter, run, seed_needs, seed_roster
from world.charter_intervene import INTERVENTION_OPS, apply_due
from world.charter_trigger import (
    INSTITUTION_OPS, SIDES, changes_from, fire_institution_rules,
    fire_triggers, normalize_triggers, trigger_warnings)

from charter_worlds import bandit_band, small_town, with_wilds, wolf_pack


def _pack(**overrides):
    scene = with_wilds(small_town()["scene"], "north_2")
    spec = wolf_pack(scene, ground="north_2", size=3)
    spec.update(overrides)
    charter = normalize_charter(copy.deepcopy(spec))
    charter["roster"] = seed_roster(charter["bodies"])
    charter["needs"] = seed_needs(charter["bodies"])
    return charter


class TestTheSideOfAChange:
    def test_a_change_says_which_side_our_body_was_on(self):
        bodies = {"hound_0": {"place": "den", "available": True}}
        suffered = changes_from(
            events=[{"kind": "harm_done", "at_hours": 4.0, "place": "wood",
                     "actor": "town/herder", "subject": "hound_0"}],
            bodies=bodies, at_hours=4.0)
        dealt = changes_from(
            events=[{"kind": "harm_done", "at_hours": 4.0, "place": "wood",
                     "actor": "hound_0", "subject": "town/herder"}],
            bodies=bodies, at_hours=4.0)
        neither = changes_from(
            events=[{"kind": "harm_done", "at_hours": 4.0, "place": "wood",
                     "actor": "a", "subject": "b"}],
            bodies=bodies, at_hours=4.0)
        assert suffered[0]["side"] == "suffered"
        assert dealt[0]["side"] == "dealt"
        assert neither[0]["side"] == ""
        assert set(SIDES) == {"dealt", "suffered"}

    def test_a_goods_exchange_carries_its_good_as_about(self):
        rows = changes_from(
            events=[{"kind": "goods_exchanged", "at_hours": 4.0,
                     "place": "cave", "holder": "hoard", "good": "silver",
                     "seller": "town", "buyer": "wyrm"}],
            bodies={}, at_hours=4.0)
        assert rows[0]["about"] == "silver"


class TestTheInstitutionPass:
    def test_the_per_body_pass_ignores_institution_ops(self):
        rules = [{"id": "r", "on": "event:harm_done",
                  "then": [{"op": "intervene",
                            "intervention": {"op": "relocate",
                                             "to": "nearest"}}]}]
        changes = changes_from(
            events=[{"kind": "harm_done", "at_hours": 4.0, "place": "wood",
                     "actor": "x", "subject": "hound_0"}],
            bodies={"hound_0": {"place": "wood", "available": True}},
            at_hours=4.0)
        events, opened, onsets, memory, fired, depths = fire_triggers(
            changes, {"hound_0": {"place": "wood", "available": True}}, 8.0,
            rules=rules)
        assert events == [] and opened == {} and fired == []

    def test_the_institution_pass_fires_and_resolves(self):
        rules = [{"id": "r", "on": "event:harm_done",
                  "where": {"side": "suffered"}, "refractory_hours": 48.0,
                  "then": [{"op": "intervene",
                            "intervention": {"op": "relocate",
                                             "to": "nearest",
                                             "cause": "a member was hurt"}},
                           {"op": "settle_commitment", "state": "repudiated",
                            "kind": "bargain"}]}]
        bodies = {"hound_0": {"place": "wood", "available": True}}
        changes = changes_from(
            events=[{"kind": "harm_done", "at_hours": 4.0, "place": "wood",
                     "actor": "x", "subject": "hound_0"}],
            bodies=bodies, at_hours=4.0)
        ops, memory, fired = fire_institution_rules(changes, bodies, 8.0,
                                                    rules=rules)
        assert [op["op"] for op in ops] == ["intervene", "settle_commitment"]
        assert ops[0]["intervention"]["op"] == "relocate"
        assert ops[0]["intervention"]["at_hours"] == 8.0
        assert fired and list(memory) and list(memory)[0].startswith("inst|")
        # The refractory holds on the second window.
        again, memory, fired = fire_institution_rules(
            changes, bodies, 12.0, rules=rules, last_fired=memory)
        assert again == [] and fired == []
        # The wrong side does not fire.
        dealt = changes_from(
            events=[{"kind": "harm_done", "at_hours": 4.0, "place": "wood",
                     "actor": "hound_0", "subject": "x"}],
            bodies=bodies, at_hours=4.0)
        ops, _m, _f = fire_institution_rules(dealt, bodies, 16.0, rules=rules)
        assert ops == []

    def test_an_unreadable_institution_op_is_refused_with_a_notice(self):
        assert trigger_warnings([
            {"id": "bad", "on": "event:harm_done",
             "then": [{"op": "intervene",
                       "intervention": {"op": "teleport"}}]}])
        assert trigger_warnings([
            {"id": "bad", "on": "event:harm_done",
             "then": [{"op": "settle_commitment", "state": "forgotten"}]}])
        assert set(INSTITUTION_OPS) == {"intervene", "settle_commitment"}
        rows = normalize_triggers([
            {"id": "ok", "on": "event:harm_done",
             "then": [{"op": "intervene",
                       "intervention": {"op": "creature_dial",
                                        "field": "boldness", "delta": -0.5}}]}])
        assert not any(r.get("refused") for r in rows)


class TestTheOpsInTheStep:
    def test_a_member_hurt_moves_the_den(self):
        """The wolf fixture's own rule, end to end: a hurt member last
        window, the rule fires this window, the lair moves next."""
        pack = _pack()
        assert all(b["berth"] == "den" for b in pack["bodies"].values())
        pack["carried_events"] = [{
            "kind": "harm_done", "at_hours": 0.0, "place": "wood",
            "actor": "town/herder_0", "subject": "hound_0", "outcome": "hurt"}]
        pack = normalize_charter(pack)
        pack, events = run(pack, 12.0, window=4.0, seed=1)
        moved = [e for e in events if e["kind"] == "lair_moved"]
        assert len(moved) == 1
        assert moved[0]["from"] == "den" and moved[0]["place"] != "den"
        assert all(b["berth"] == moved[0]["place"]
                   for b in pack["bodies"].values())

    def test_a_dial_turns_and_a_bargain_settles(self):
        band = normalize_charter(copy.deepcopy(bandit_band(
            with_wilds(small_town()["scene"], "north_2"), ground="north_2")))
        band["interventions"] = [
            {"op": "creature_dial", "at_hours": 0.0, "field": "boldness",
             "delta": -0.5},
            {"op": "creature_dial", "at_hours": 0.0, "field": "temper",
             "delta": 1.0},
        ]
        band, _events = apply_due(band, 4.0)
        assert abs(band["creature"]["boldness"] - 0.1) < 1e-9
        assert band["refused_interventions"][0]["refused"] == \
            "no such creature dial"
        assert "creature_dial" in INTERVENTION_OPS

    def test_the_drift_dial_revert_restores_what_it_found(self):
        """Before this, the end of a dial set the drift to ZERO forever:
        a creature fed to sleep for three days would never have woken."""
        pack = _pack()
        was = pack["upkeeps"]["belly"]["drift_per_hour"]
        assert was > 0.0
        pack["interventions"] = [{
            "op": "drift_dial", "at_hours": 0.0, "upkeep": "belly",
            "drift_per_hour": 0.0, "until_hours": 8.0, "cause": "fed"}]
        pack, _ = apply_due(pack, 4.0)
        assert pack["upkeeps"]["belly"]["drift_per_hour"] == 0.0
        pack, _ = apply_due(pack, 8.0)
        assert pack["upkeeps"]["belly"]["drift_per_hour"] == was

    def test_relocate_refuses_where_there_is_nowhere_to_go(self):
        pack = _pack()
        pack["scene"] = None
        pack["interventions"] = [{"op": "relocate", "at_hours": 0.0,
                                  "to": "nearest"}]
        pack, events = apply_due(pack, 4.0)
        assert not [e for e in events if e["kind"] == "lair_moved"]
        assert pack["refused_interventions"]
