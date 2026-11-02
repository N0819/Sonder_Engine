"""A town stepped beside a creature walks the graph its people walk.

`charter_predation._Caches` planned and walked every ordinary institution of
a creature registry on `passable_neighbors`, where a shut door is a wall,
while `charter_run.run` uses `people_neighbors` -- the Aldermill fix of
2026-09-19. Measured (audit world_charter_generation_run F4): `small_town`
with the smithy's doors shut, 48 h, seed 3 -- `run` filled the smith's shift,
`run_registry` reported it `out_of_reach` and left the smithy empty, so the
"byte-identical to `run`" property `tests/test_charter_creature.py` pins held
only because the shipped fixture has no shut door."""
import copy
import json

from charter_worlds import small_town
from world.charter_model import normalize_charter
from world.charter_needs import seed_needs
from world.charter_predation import run_registry
from world.charter_roster import seed_roster
from world.charter_run import run


def _town():
    town = small_town()
    for rid, room in town["scene"]["rooms"].items():
        for edge in room.get("adjacent") or ():
            if edge.get("to") == "smithy" or rid == "smithy":
                edge["barrier"] = "closed_door"
    town = normalize_charter(town)
    town["roster"] = seed_roster(town["bodies"])
    town["needs"] = seed_needs(town["bodies"])
    return town


def test_a_shut_door_is_no_wall_in_either_stepper():
    town = _town()
    alone, _events = run(copy.deepcopy(town), 48.0, window=4.0, seed=3)
    states, _ = run_registry({"town": copy.deepcopy(town)}, 48.0,
                             window=4.0, seed=3)
    assert json.dumps(alone, sort_keys=True, default=str) == \
        json.dumps(states["town"], sort_keys=True, default=str)
