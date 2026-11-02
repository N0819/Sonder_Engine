"""The room graph's sound flood depends on its source alone, so a read pass
derives it once per (source room, level, kind) -- not once per relation.

Audit world_spatial_sound E1 (2026-11-01): `far_path` flooded from the
speaker's room on every `stamp_sound_relation`; on chat 167 two 72-relation
sweeps ran the voice flood 72 times for 2 distinct source rooms (~18% of the
profiled sweep), and `distant_sounds` flooded per (listener x source).
"""

from world.scene_memo import scene_read_pass
from world.spatial import room_sound_flood


def _chain():
    rooms = {}
    names = ["a", "b", "c", "d"]
    for i, rid in enumerate(names):
        edges = []
        if i:
            edges.append({"to": names[i - 1], "barrier": "open_door"})
        if i + 1 < len(names):
            edges.append({"to": names[i + 1], "barrier": "open_door"})
        rooms[rid] = {"name": rid.upper(), "size": "small", "adjacent": edges}
    return {"rooms": rooms, "positions": {}, "entities": {}}


def test_inside_a_pass_the_flood_is_shared():
    sc = _chain()
    with scene_read_pass(sc):
        first = room_sound_flood(sc, "a", 80.0, voice=True)
        again = room_sound_flood(sc, "a", 80.0, voice=True)
        other = room_sound_flood(sc, "a", 80.0)
    assert first is again
    assert first and "c" in first
    assert other is not first


def test_outside_a_pass_it_is_derived_each_time_and_answers_the_same():
    sc = _chain()
    one = room_sound_flood(sc, "a", 80.0, voice=True)
    two = room_sound_flood(sc, "a", 80.0, voice=True)
    assert one == two and one is not two
