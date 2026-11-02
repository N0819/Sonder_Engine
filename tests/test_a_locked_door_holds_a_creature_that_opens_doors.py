"""A creature that can open doors opens the doors a hand opens, and no more.

`creature_neighbors` added every edge whose barrier merely CONTAINED "door"
when `can_open_doors` was set, so `locked_door`, `padlocked_door` and
`stuck_door` all opened to it while `charter_space.people_neighbors` -- the
graph a person walks -- held them by the engine's own fastening reader.
Measured (audit world_charter_behaviours F12): a cell behind a locked door
was `{'cell': {'hall'}, 'hall': {'cell'}}` to the creature and `{}` to
people; in a containment story the hunting thing left its locked cell off
screen. One rule now: a hand's."""
from world.charter_creature import creature_neighbors
from world.charter_space import people_neighbors


def _scene(barrier):
    return {"rooms": {
        "cell": {"name": "Cell", "adjacent": [{"to": "hall", "barrier": barrier}]},
        "hall": {"name": "Hall", "adjacent": [{"to": "cell", "barrier": barrier}]},
    }}


def test_a_fastened_door_holds_it():
    for barrier in ("locked_door", "padlocked_door", "stuck_door"):
        graph = creature_neighbors(_scene(barrier), {"can_open_doors": True})
        assert "hall" not in graph.get("cell", set()), barrier
        assert people_neighbors(_scene(barrier)).get("cell", set()) \
            == graph.get("cell", set()), barrier


def test_a_plain_shut_door_opens_to_it_as_it_opens_to_a_hand():
    graph = creature_neighbors(_scene("closed_door"), {"can_open_doors": True})
    assert "hall" in graph.get("cell", set())
    assert "cell" in graph.get("hall", set())


def test_without_hands_a_shut_door_is_a_wall():
    graph = creature_neighbors(_scene("closed_door"), {"can_open_doors": False})
    assert "hall" not in graph.get("cell", set())
