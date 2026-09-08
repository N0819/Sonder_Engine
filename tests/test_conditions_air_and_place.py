"""The world acting on a body: air that stays taken, a condition of a PLACE,
a cadence that is not one, and a hazard nothing answered.

Live cases, all campaign 3, 2026-09-05:

* PR3 (`docs/experiments/PLAY_2026_09_05C_rush.md`) -- the body hand wrote
  `vitals: {Vesna: {air: 0.9}, Mirela: {air: 0.9}}` for climbing a
  smoke-filled stair on turn 7, and turn 8 committed `air: 1.0` for both;
  turn 14 wrote 0.85 and turn 15 committed 1.0. `tick_vitals` handed back
  `seconds / 60` of air to anyone `is_sealed_in` said False of, and a
  stairwell full of smoke is not sealed. Final air for all three bodies
  after five minutes of a burning tenement: 1.0.
* PR4 -- six conditions landed (`second_landing_fire` severity 0.9,
  `third_landing_fire` "critical", and four more) and acted on nobody: a
  ticking condition could only ever name a PERSON, and all six carried
  `tick_interval_seconds: 0`, which is not a cadence and was reported
  nowhere.
* PS12 (`docs/experiments/PLAY_2026_09_05C_solitude.md`) -- across 21 turns
  of a solitary story, `conditions` 0, `vitals` 0, `consequences` 0, because
  `resolution_flags.contested` keys off REACTORS and there was no second
  party. A contest needs an opposing FORCE, not an opposing person.
"""

from __future__ import annotations

import json

from world.mechanics import (inert_condition_ids, mechanics_sweep,
                             unanswered_hazard_subjects)
from world.survival import (AIR_DENIED_KEY, apply_vitals_diff, tick_vitals,
                            vitals_of)


def _cond(condition_id, subject, *, kind="fire", next_tick=None,
          expires_at=None, payload=None):
    return {"condition_id": condition_id, "subject_id": subject, "kind": kind,
            "started_at": 0.0, "expires_at": expires_at, "next_tick": next_tick,
            "payload": json.dumps(payload or {}, ensure_ascii=False)}


def _stair_scene():
    """Two landings joined by a stair, one body on each -- the tenement."""
    return {
        "rooms": {
            "second_landing": {"name": "Second Landing",
                               "adjacent": [{"to": "third_landing",
                                             "barrier": "open"}]},
            "third_landing": {"name": "Third Landing",
                              "adjacent": [{"to": "second_landing",
                                            "barrier": "open"}]},
        },
        "positions": {"Mirela": "second_landing", "Vesna": "third_landing"},
        "vitals": {"Mirela": {"air": 1.0, "stamina": 1.0,
                              "nourishment": 1.0, "injury": 0.0},
                   "Vesna": {"air": 1.0, "stamina": 1.0,
                             "nourishment": 1.0, "injury": 0.0}},
    }


def _sweep(scene, conditions, elapsed):
    return mechanics_sweep(scene, {"elapsed_seconds": elapsed}, "f1", [],
                           conditions=conditions, turn_idx=3)


# --- PR4a: a standing condition of a PLACE is a fact about standing in it ---

def test_a_condition_whose_subject_is_a_room_acts_on_who_is_in_it():
    scene = _stair_scene()
    fire = _cond("second_landing_fire", "second_landing", next_tick=0.0,
                 payload={"tick_interval_seconds": 30,
                          "tick": {"vitals": {"air": -0.1},
                                   "percept": "the smoke is thicker"}})
    _sweep(scene, [fire], 60.0)
    # Two fires in sixty seconds, on the body that is actually on the landing.
    assert vitals_of(scene, "Mirela")["air"] < 1.0
    # And on nobody else: a fire on the second landing is not a fire on the
    # third, which is the whole reason a place gets to carry a condition.
    assert vitals_of(scene, "Vesna")["air"] == 1.0


def test_a_room_condition_naming_an_empty_room_acts_on_nobody():
    scene = _stair_scene()
    scene["positions"] = {}
    fire = _cond("second_landing_fire", "second_landing", next_tick=0.0,
                 payload={"tick_interval_seconds": 30,
                          "tick": {"vitals": {"air": -0.1}}})
    _, _ops, notices, _counts = _sweep(scene, [fire], 60.0)
    assert vitals_of(scene, "Mirela")["air"] == 1.0
    assert not [n for n in notices if "no body of that name" in n]


def test_a_condition_whose_subject_is_a_person_still_names_that_person():
    scene = _stair_scene()
    smoke = _cond("vesna_smoke_inhalation", "Vesna", kind="smoke_inhalation",
                  next_tick=0.0,
                  payload={"tick_interval_seconds": 30,
                           "tick": {"vitals": {"air": -0.1}}})
    _sweep(scene, [smoke], 60.0)
    assert vitals_of(scene, "Vesna")["air"] < 1.0
    assert vitals_of(scene, "Mirela")["air"] == 1.0


# --- PR3: air does not come back while the world is taking it --------------

def test_air_does_not_return_to_full_while_a_room_condition_takes_it():
    """PR3 + PR4 together, over two beats: the smoke-filled stair."""
    scene = _stair_scene()
    fire = _cond("second_landing_fire", "second_landing", next_tick=0.0,
                 payload={"tick_interval_seconds": 30,
                          "tick": {"vitals": {"air": -0.1}}})
    _sweep(scene, [fire], 60.0)                 # beat one: the fire acts
    after_first = vitals_of(scene, "Mirela")["air"]
    assert after_first < 1.0
    assert scene[AIR_DENIED_KEY] == ["Mirela"]

    # Beat two begins with the merge's tick, which used to hand a full breath
    # back every sixty seconds regardless of what the world was doing.
    tick_vitals(scene, 120.0)
    assert vitals_of(scene, "Mirela")["air"] <= after_first
    assert vitals_of(scene, "Mirela")["air"] < 1.0


def test_a_body_that_walks_out_of_the_smoke_recovers():
    """The record REPLACES every sweep, so it self-expires."""
    scene = _stair_scene()
    scene["vitals"]["Mirela"]["air"] = 0.6
    scene[AIR_DENIED_KEY] = ["Mirela"]
    scene["positions"]["Mirela"] = "third_landing"
    _sweep(scene, [], 60.0)                     # no condition acts any more
    assert AIR_DENIED_KEY not in scene
    tick_vitals(scene, 120.0)
    assert vitals_of(scene, "Mirela")["air"] > 0.6


def test_a_declared_loss_is_not_handed_back_by_the_same_merge():
    """The exact turn-7 shape: the body hand writes `air: 0.9` and
    `merge_scene_with_diff` runs `apply_vitals_diff` then `tick_vitals` on
    the same scene, in that order."""
    scene = _stair_scene()
    apply_vitals_diff(scene, {"Mirela": {"air": 0.9}})
    tick_vitals(scene, 120.0)                   # a two-minute beat
    assert vitals_of(scene, "Mirela")["air"] == 0.9
    # Vesna, whom nothing declared anything about, breathes freely.
    assert vitals_of(scene, "Vesna")["air"] == 1.0


def test_a_declared_recovery_is_not_mistaken_for_a_loss():
    scene = _stair_scene()
    scene["vitals"]["Mirela"]["air"] = 0.4
    apply_vitals_diff(scene, {"Mirela": {"air": 0.7}})
    assert AIR_DENIED_KEY not in scene
    tick_vitals(scene, 120.0)
    assert vitals_of(scene, "Mirela")["air"] > 0.7


# --- PR4b: a cadence field filled with a non-cadence -----------------------

def test_a_spelled_interval_that_is_not_a_cadence_is_reported():
    rows = [
        _cond("second_landing_fire", "second_landing",
              payload={"tick_interval_seconds": 0}),
        _cond("third_landing_fire", "third_landing",
              payload={"state": {"tick_interval_seconds": 0}}),
        _cond("fourth_landing_smoke", "fourth_landing",
              payload={"tick_interval_seconds": 30}),
        _cond("a_row_that_never_claimed_to_act", "Vesna", payload={}),
    ]
    assert inert_condition_ids(rows) == ["second_landing_fire",
                                         "third_landing_fire"]


# --- PS12: the world is a party to a contest -------------------------------

def _fire_of(room, severity=0.9):
    return _cond("%s_fire" % room, room,
                 payload={"severity": severity,
                          "description": "Floorboards engulfed in flames"})


def test_a_body_in_a_stated_hazard_that_the_beat_never_answered():
    scene = _stair_scene()
    assert unanswered_hazard_subjects(
        scene, [_fire_of("second_landing")], None, {}) == ["Mirela"]


def test_a_beat_that_rolled_has_answered():
    scene = _stair_scene()
    diff = {"dice": [{"what": "the stair", "result": "partial"}]}
    assert unanswered_hazard_subjects(
        scene, [_fire_of("second_landing")], None, diff) == []


def test_a_beat_that_moved_the_body_s_vitals_has_answered():
    scene = _stair_scene()
    diff = {"vitals": {"Mirela": {"air": 0.8}}}
    assert unanswered_hazard_subjects(
        scene, [_fire_of("second_landing")], None, diff) == []


def test_a_room_condition_that_states_no_harm_is_not_a_hazard():
    """A room can stand under a festival as easily as under a fire, and
    `kind` is open vocabulary (106 distinct strings in the corpus). Severity
    and a vital-taking tick are the two fields that answer without one."""
    scene = _stair_scene()
    festival = _cond("second_landing_wake", "second_landing", kind="gathering",
                     payload={"description": "neighbours on the landing"})
    assert unanswered_hazard_subjects(scene, [festival], None, {}) == []


def test_the_scene_is_not_a_second_hazard_ledger():
    """ONE STORE (review 2026-09-07 B8). A standing hazard of a place is a
    `world_conditions` row and nothing else; this floor used to read a
    `hazard` block on the scene's room dict as well, and a question with two
    stores is a question with two answers. `world.region_events.apply_wave`
    now states its hazard in the table -- covered end to end in
    tests/test_ruin_and_hazard_one_store.py.
    """
    scene = _stair_scene()
    scene["rooms"]["second_landing"]["hazard"] = {"state": "burning",
                                                  "cause": "the bakery"}
    assert unanswered_hazard_subjects(scene, [], None, {}) == []
    assert unanswered_hazard_subjects(
        scene, [_fire_of("second_landing")], None, {}) == ["Mirela"]


def test_no_hazard_means_nothing_to_report():
    assert unanswered_hazard_subjects(_stair_scene(), [], None, {}) == []
