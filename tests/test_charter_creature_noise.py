"""Review 2026-09-07 A51: a creature's noise follows a place that changed.

`hunt_moves` says "stay" by naming the body's own room -- a predator standing
on its prey does not report for duty -- and `predation_round` read every
entry in `moves` as a walk, so the thing crouched over its kill was heard
`moving` every window and its `idle` voice was suppressed by that same row.
"""
import copy

from charter_worlds import guarded_town, small_town, with_wilds, wolf_pack
from world.charter_model import normalize_charter
from world.charter_needs import seed_needs
from world.charter_predation import predation_round
from world.charter_roster import seed_roster


def _ready(spec):
    charter = normalize_charter(copy.deepcopy(spec))
    charter["roster"] = seed_roster(charter["bodies"])
    charter["needs"] = seed_needs(charter["bodies"])
    return charter


def _states(*, hound_place):
    town = small_town()
    scene = with_wilds(town["scene"], "north_2")
    town = guarded_town(dict(town, scene=scene), pen_place="north_2",
                        hall_place="square")
    pack = wolf_pack(scene, ground="north_2", size=1)
    pack["creature"]["voice"] = {
        "moving": {"level": "audible", "sound": "something heavy shifting"},
        "idle": {"level": "faint", "sound": "a slow wet breathing"}}
    pack["creature"]["active_phases"] = []
    pack["creature"]["encounter_odds"] = 0.0   # standing, not attacking
    states = {"town": _ready(town), "pack": _ready(pack)}
    states["pack"]["bodies"]["hound_0"]["place"] = hound_place
    states["town"]["bodies"]["herder_0"]["place"] = "north_2"
    return states


def _heard(states):
    return [(row["activity"], row["place"])
            for row in states["pack"].get("heard") or ()]


def test_a_creature_standing_on_its_prey_is_heard_standing_still():
    states = _states(hound_place="north_2")
    predation_round(states, 4.0, seed=0)
    assert states["pack"]["bodies"]["hound_0"]["place"] == "north_2"
    assert _heard(states) == [("idle", "north_2")]


def test_a_creature_that_crosses_rooms_is_heard_where_it_now_stands():
    states = _states(hound_place="den")
    predation_round(states, 4.0, seed=0)
    arrived = states["pack"]["bodies"]["hound_0"]["place"]
    assert arrived != "den"
    assert _heard(states) == [("moving", arrived)]


def _killing_states():
    """A pack standing on its meal: hungry, always willing, no phase gate."""
    town = small_town()
    scene = with_wilds(town["scene"], "north_2")
    town = guarded_town(dict(town, scene=scene), pen_place="north_2",
                        hall_place="square")
    pack = wolf_pack(scene, ground="north_2", size=1)
    pack["creature"]["voice"] = {
        "moving": {"level": "audible", "sound": "something heavy shifting"},
        "attacking": {"level": "loud", "sound": "a shriek cut short"},
        "feeding": {"level": "audible", "sound": "wet tearing"},
        "idle": {"level": "faint", "sound": "a slow wet breathing"}}
    pack["creature"]["active_phases"] = []
    pack["creature"]["encounter_odds"] = 1.0
    pack["creature"]["prey"] = ["unposted", "posted"]
    pack["upkeeps"]["belly"]["level"] = 0.0
    states = {"town": _ready(town), "pack": _ready(pack)}
    states["pack"]["bodies"]["hound_0"]["place"] = "north_2"
    states["town"]["bodies"]["herder_0"]["place"] = "north_2"
    return states


def test_a_predator_that_kills_where_it_stands_is_not_also_idle():
    """A51: a body that moved OR reached what it wanted is not standing still.

    "Did not move" is not the complement of the idle branch\'s own rule. A
    creature that kills without taking a step never moves, so gating idle on
    movement alone had it heard attacking, feeding and idle in one window, at
    one room -- the very case the moving half of A51 was written for. Failed
    across seeds 0-5 and 7 before the `acted` half of the gate landed.
    """
    for seed in (0, 1, 2, 3, 4, 5, 7):
        states = _killing_states()
        predation_round(states, 4.0, seed=seed)
        heard = _heard(states)
        if ("attacking", "north_2") not in heard:
            continue    # no kill on this seed; nothing to say about idle
        assert states["pack"]["bodies"]["hound_0"]["place"] == "north_2"
        assert heard == [("attacking", "north_2"), ("feeding", "north_2")], (
            f"seed {seed}")
