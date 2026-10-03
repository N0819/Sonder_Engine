"""An event with no body behind it happened where its targets are (2026-10-02).

Chat 160 turn 11: a scheduled event -- the elevator's power failing, the
free fall, the cables snapping -- was sourced to `authored_event:0`, which
the scene places nowhere, so every observer's relation to it read "no known
spatial channel" and the two people riding the car received none of it.
"""

from agents.perception import _sourceless_event_rel


def _scene():
    return {
        "rooms": {"elevator_car": {"name": "Car", "parent_entity": "freight_elevator", "adjacent": []},
                  "elevator_shaft": {"name": "Shaft", "adjacent": []},
                  "lobby": {"name": "Lobby", "adjacent": []}},
        "entities": {"freight_elevator": {"name": "Freight Elevator", "kind": "vehicle"},
                     "elevator_fluorescent": {"name": "Ceiling tube"},
                     "far_lamp": {"name": "Lobby lamp"}},
        "positions": {"freight_elevator": "elevator_shaft", "Hinami": "elevator_car",
                      "elevator_fluorescent": "elevator_car", "far_lamp": "lobby"},
    }


def test_the_thing_the_observer_rides_is_the_observers_own_place():
    rel = _sourceless_event_rel(_scene(), "Hinami", ["freight_elevator"], "elevator_car")
    assert rel["same_room"] is True


def test_a_target_in_the_observers_room_places_the_event_there():
    rel = _sourceless_event_rel(_scene(), "Hinami", ["elevator_fluorescent"], "elevator_car")
    assert rel["same_room"] is True


def test_no_target_places_it_nowhere_and_a_far_one_is_not_here():
    assert _sourceless_event_rel(_scene(), "Hinami", [], "elevator_car") is None
    assert _sourceless_event_rel(_scene(), "Hinami", ["nothing_known"], "elevator_car") is None
    far = _sourceless_event_rel(_scene(), "Hinami", ["far_lamp"], "elevator_car")
    assert far is not None and not far.get("same_room")
