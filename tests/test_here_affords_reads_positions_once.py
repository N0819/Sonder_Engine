"""What the room affords is read off one index of where things stand, not a
fresh name resolution per entity.

world_misc_causal E3 (audit 2026-11-01): `here_affords` asked `room_of` for
each entity's name and id, and a name miss falls to `_unique_entity_keyed`,
a scan of every entity -- quadratic in the entity count: 30 entities 4.4 ms,
100 -> 50 ms, 300 -> 394 ms per character payload build (the owner's live
scenes peak at 28 entities; procgen worlds scale it).
"""

import world.place_purpose as place_purpose


def _scene(n):
    entities = {"bed_1": {"name": "Bed", "kind": "furniture"},
                "stove_1": {"name": "Iron stove", "kind": "fixture"}}
    positions = {"Ada": "hall", "bed_1": "hall", "Iron stove": "hall"}
    for i in range(n):
        entities["crate_%d" % i] = {"name": "Crate %d" % i, "kind": "object"}
        positions["crate_%d" % i] = "hall" if i % 2 else "yard"
    return {"rooms": {"hall": {"name": "Hall", "light": "lit"},
                      "yard": {"name": "Yard", "light": "lit"}},
            "entities": entities, "positions": positions}


def test_the_room_is_resolved_once_whatever_the_entity_count(monkeypatch):
    calls = []
    real = place_purpose.room_of

    def counting(scene, name, **kw):
        calls.append(name)
        return real(scene, name, **kw)

    monkeypatch.setattr(place_purpose, "room_of", counting)
    found = place_purpose.here_affords(_scene(60), "Ada")
    assert found == ["rest (the Bed)", "warmth (the Iron stove)"]
    assert len(calls) == 1, len(calls)


def test_an_entity_placed_under_any_of_its_spellings_is_in_the_room():
    scene = _scene(4)
    scene["entities"]["cot_1"] = {"name": "Camp cot", "kind": "furniture",
                                  "aliases": ["the cot"]}
    scene["positions"]["the cot"] = "hall"
    scene["entities"].pop("bed_1")
    scene["positions"].pop("bed_1")
    assert place_purpose.here_affords(scene, "Ada")[0] == "rest (the Camp cot)"
