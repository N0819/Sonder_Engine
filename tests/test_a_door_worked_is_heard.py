"""A doorway that opens or shuts this beat is heard, at the doorway, in both
the rooms it joins.

Chat 168 turn 4591 (2026-10-12): Tamamo slid Hinami's shoji open a hand's
width. The resolve's prose had "a soft rasp of paper and a dry tick of
wood"; nothing wrote a sound event, so the body lying three paces off with
her back to the door was told nothing. `door_events` reads the barrier the
two scenes hold -- the typed edge, never the prose -- and sounds every door
that changed between shut and open, whoever wrote the change.
"""
from __future__ import annotations

import copy

from world.spatial import DOOR_SOURCE_PREFIX, door_events


def _scene(barrier="closed_door"):
    return {"rooms": {
        "hall": {"name": "Hall", "adjacent": [{"to": "bedroom", "barrier": barrier,
                                               "name": "a shoji door"}]},
        "bedroom": {"name": "Bedroom", "adjacent": [{"to": "hall", "barrier": barrier,
                                                     "name": "a shoji door"}]}}}


def test_a_door_opened_sounds_in_both_its_rooms_at_the_doorway():
    events = door_events(_scene("closed_door"), _scene("open_door"))
    assert sorted((e["room"], e["source"]) for e in events) == [
        ("bedroom", DOOR_SOURCE_PREFIX + "hall"), ("hall", DOOR_SOURCE_PREFIX + "bedroom")]
    assert {e["detail"] for e in events} == {"a door opening"}
    assert {e["level"] for e in events} == {"faint"}


def test_a_door_shut_sounds_too_and_one_left_alone_does_not():
    assert {e["detail"] for e in door_events(_scene("open_door"), _scene("closed_door"))} \
        == {"a door shutting"}
    assert door_events(_scene("closed_door"), _scene("closed_door")) == []
    assert door_events(_scene("open_door"), _scene("open_door")) == []


def test_a_locked_door_still_reads_as_shut():
    assert {e["detail"] for e in door_events(_scene("locked_door"), _scene("open_door"))} \
        == {"a door opening"}


def test_what_is_not_a_door_being_worked_makes_no_sound():
    # a curtain drawn, an archway, a doorway the beat itself made
    assert door_events(_scene("membrane"), _scene("open_door")) == []
    assert door_events(_scene("open"), _scene("closed_door")) == []
    made = copy.deepcopy(_scene("open_door"))
    assert door_events({"rooms": {"hall": {"adjacent": []}, "bedroom": {"adjacent": []}}}, made) == []


def test_it_speaks_the_storys_language():
    from language_runtime import language_scope
    with language_scope("ja"):
        events = door_events(_scene("closed_door"), _scene("open_door"))
    assert {e["detail"] for e in events} == {"戸が開く音"}
