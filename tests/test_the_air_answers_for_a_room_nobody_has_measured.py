"""The room graph's answers need no grid: a listener in a room nobody has
measured still gets the `air` stamp and the far field.

Audit world_spatial_sound F1 (2026-11-01, CONFIRMED LEAK, live corpus): the
`air`, `far_loss_db`, `far_muffled` and `floor_db` stamps are ROOM-GRAPH facts
(`far_path`, `_rooms_joined`, `rooms_adjacent`, `quiet_floor`), but
`stamp_sound_relation` returned before stamping them whenever the LISTENER's
room had no grid -- 440 of 1,093 live rooms. Over the owner's scenes, 693
joined body pairs had a gridless listener and in 492 of them a named normal
line the hearing table refuses (a wall) was rescued to `full` by the
addressed-line rescue as "a transmission by device" -- the shout-up-the-tower
class the `air` stamp was built to close. And rooms-away pairs kept the edge
model's `separated` row instead of the far field.
"""

from agents.composer import line_hear_level
from world.spatial import hear_level, spatial_rel_between


def _room(name, edges):
    return {"name": name, "desc": f"The {name}.", "adjacent": edges}


def _scene(rooms, positions):
    return {"rooms": rooms, "positions": dict(positions), "stations": {},
            "orientation": {}, "poses": {}, "entities": {}, "contained": {}}


def _walled():
    return _scene({
        "main_corridor": _room("Main Corridor",
                               [{"to": "room_1a", "barrier": "wall"}]),
        "room_1a": _room("Room 1A", [{"to": "main_corridor", "barrier": "wall"}]),
    }, {"Alex": "main_corridor", "Marcus": "room_1a"})


def _line(volume="normal"):
    return {"speaker": "Alex", "intended_target": "Marcus", "volume": volume,
            "text": "Marcus, can you hear me?"}


def test_a_named_line_through_a_wall_is_not_rescued_as_a_device():
    sc = _walled()
    rel = spatial_rel_between(sc, "Marcus", "Alex")
    assert rel.get("air") is True
    assert hear_level(rel, "normal") == "none"
    assert line_hear_level(_line(), rel, "Marcus") == "none"


def test_rooms_away_get_the_far_field_without_a_grid():
    rooms = {
        "a": _room("A", [{"to": "b", "barrier": "open_door"}]),
        "b": _room("B", [{"to": "a", "barrier": "open_door"},
                         {"to": "c", "barrier": "open_door"}]),
        "c": _room("C", [{"to": "b", "barrier": "open_door"}]),
    }
    sc = _scene(rooms, {"S": "a", "L": "c"})
    rel = spatial_rel_between(sc, "L", "S")
    assert rel.get("air") is True
    assert rel.get("far_loss_db") is not None
    assert "floor_db" in rel


def test_rooms_no_edge_joins_carry_no_air_and_keep_the_device_rescue():
    """The rescue's earned case stays: a pair the room graph does not join
    at all -- a ship in orbit -- has no air, so a by-name line arrives as a
    transmission."""
    rooms = {"bridge": _room("Bridge", []), "surface": _room("Surface", [])}
    sc = _scene(rooms, {"Alex": "bridge", "Marcus": "surface"})
    rel = spatial_rel_between(sc, "Marcus", "Alex")
    assert not rel.get("air")
    assert line_hear_level(_line(), rel, "Marcus") == "full"
