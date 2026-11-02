"""A body the scene holds is the Director's to endanger, never a dice roll.

The predation round indexed every available body as prey with no lease
test, so a townsperson leased to the scene -- standing in the room the story
is being told in -- was killed off screen by the next charter tick: 30 of 40
seeds on the audit's probe (world_charter_generation_run F1), the scene still
showing the person standing there. The `figure` branch already files rather
than harms; a leased body is on screen by the same rule, and a leased
creature body is the scene's to move and to act with."""
import copy

from charter_worlds import small_town, with_wilds, wolf_pack
from world.charter_model import normalize_charter
from world.charter_needs import seed_needs
from world.charter_predation import predation_round
from world.charter_roster import seed_roster


def _ready(t):
    t = normalize_charter(copy.deepcopy(t))
    t["roster"] = seed_roster(t["bodies"])
    t["needs"] = seed_needs(t["bodies"])
    return t


def _world(leased_victim=True, leased_pack=False):
    town = small_town()
    scene = with_wilds(town["scene"], "north_2")
    town = _ready(dict(town, scene=scene))
    pack = wolf_pack(scene, ground="north_2", size=4)
    pack["creature"]["prey"] = ["unposted"]
    pack["creature"]["encounter_odds"] = 1.0
    pack["creature"]["active_phases"] = []
    pack = _ready(pack)
    victim = sorted(k for k in town["bodies"]
                    if k not in set((town.get("watch") or {}).values()))[0]
    town["bodies"][victim]["place"] = "north_2"
    if leased_victim:
        town["bodies"][victim]["leased"] = "present"
    for body in pack["bodies"].values():
        body["place"] = "north_2"
        if leased_pack:
            body["leased"] = "present"
    return town, pack, victim


def _harmed(body):
    return body.get("condition") not in (None, "", "well") \
        or not body.get("available", True)


def test_a_leased_townsperson_is_never_harmed_by_the_round():
    town, pack, victim = _world()
    for seed in range(40):
        states = {"town": copy.deepcopy(town), "pack": copy.deepcopy(pack)}
        predation_round(states, 22.0, seed=seed)
        assert not _harmed(states["town"]["bodies"][victim]), seed


def test_an_unleased_townsperson_is_still_prey():
    town, pack, victim = _world(leased_victim=False)
    hits = 0
    for seed in range(40):
        states = {"town": copy.deepcopy(town), "pack": copy.deepcopy(pack)}
        predation_round(states, 22.0, seed=seed)
        hits += _harmed(states["town"]["bodies"][victim])
    assert hits > 0


def test_a_leased_pack_attacks_nobody():
    town, pack, victim = _world(leased_victim=False, leased_pack=True)
    for seed in range(40):
        states = {"town": copy.deepcopy(town), "pack": copy.deepcopy(pack)}
        predation_round(states, 22.0, seed=seed)
        assert not _harmed(states["town"]["bodies"][victim]), seed
