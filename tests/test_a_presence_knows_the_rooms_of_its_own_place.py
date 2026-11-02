"""A background voice is shown the rooms of its own part of the map, and the
doorways in front of it -- not every room the scene holds.

`_presence_rooms` ("the layout anyone who works or lives here knows")
handed every per-presence voice every room of the scene by name: rooms of
other buildings, rooms named after cast members, and the stubs a plan holds
open past the map's edge. Measured (review 2026-11-01,
agents_character_background F4, the owner's engine.db read-only): 368 stored
rooms carry `planned: true`, 174 of them in chats >= 160 -- "Mellisande's
Room" (chats 177/178), "Decommissioned Corridor West" (160) -- and a
bystander in another building was handed both. A presence now knows the
rooms of its own region (`world.regions.room_region`, the part of the map
its room belongs to) and the rooms one doorway from where it stands; a
scene with no regions keeps every room, as before. An unbuilt frontier stub
(`spatial.held_open_from`) is a plan, not a room anyone lives beside.
"""

from __future__ import annotations

from agents.background import _presence_rooms


def _room(name, region=None, *to, **extra):
    room = {"name": name, "adjacent": [{"to": t, "barrier": "open_door"} for t in to]}
    if region:
        room["region"] = region
    room.update(extra)
    return room


SCENE = {"rooms": {
    "tap": _room("Taproom", "inn", "kitchen", "yard"),
    "kitchen": _room("Kitchen", "inn", "tap"),
    "yard": _room("Inn Yard", "inn", "tap", "lane"),
    "lane": _room("Mill Lane", "town", "yard", "mill_floor"),
    "mill_floor": _room("Mill Floor", "mill", "lane"),
    "cottage_bed": _room("Mellisande's Room", "cottage"),
    "edge": _room("North Reach", "town", "lane", planned=True, provisional=True,
                  frontier_of={"room": "lane"}),
}}


def _names(rows):
    return sorted(r["name"] for r in rows)


def test_a_presence_knows_its_own_places_rooms_and_the_doors_before_it():
    assert _names(_presence_rooms(SCENE, "yard")) == [
        "Inn Yard", "Kitchen", "Mill Lane", "Taproom"]


def test_another_buildings_rooms_and_a_held_open_stub_are_not_its():
    shown = _names(_presence_rooms(SCENE, "tap"))
    assert "Mellisande's Room" not in shown and "Mill Floor" not in shown
    assert "North Reach" not in _names(_presence_rooms(SCENE, "lane"))


def test_a_scene_without_regions_lists_every_built_room():
    plain = {"rooms": {"a": _room("A", None, "b"), "b": _room("B", None, "a"),
                       "c": _room("C")}}
    assert _names(_presence_rooms(plain, "a")) == ["A", "B", "C"]
    assert _names(_presence_rooms(plain)) == ["A", "B", "C"]
