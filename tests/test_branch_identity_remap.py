"""Regression test for the branch "unspecified location" bug.

Found live (Elevator Adventure branch ⎇16): after branching, Dr. Moon (and the
player) resolved to no room -> "unspecified location" on the next turn/reroll.
Cause: characters are projected into world_entities keyed by their NAME, and
`_build_world_id_remap` regenerated a fresh opaque uid for EVERY world_entities
id -- including the character names -- so `deep_remap` rewrote the
scene.positions key from "Dr. Moon" to that uid. But characters are looked up by
name/character-uid (character_scene_keys), never by that regenerated id, so the
position became unreachable.

Fix: the remap protects character / player-persona identity strings; object
entity ids still remap freely.
"""

from __future__ import annotations

from app import _build_world_id_remap, _deep_remap_ids


def _blob():
    # Characters are (wrongly, but really) projected into world_entities under
    # their name; genuine objects use entity_* ids.
    return {"world_entities": [
        {"entity_id": "Dr. Moon"},
        {"entity_id": "Hinami"},
        {"entity_id": "entity_shelter_elevator"},
        {"entity_id": "entity_sloppy_runes"},
    ]}


def test_character_ids_are_not_remapped():
    remap = _build_world_id_remap(_blob(), protected_ids={"Dr. Moon", "Hinami",
                                                          "char_moon_uid"})
    # objects remap...
    assert "entity_shelter_elevator" in remap and "entity_sloppy_runes" in remap
    # ...characters do not
    assert "Dr. Moon" not in remap and "Hinami" not in remap
    assert "char_moon_uid" not in remap


def test_scene_positions_keep_character_keys_after_remap():
    remap = _build_world_id_remap(_blob(), protected_ids={"Dr. Moon", "Hinami"})
    positions = {
        "Dr. Moon": "elevator", "Hinami": "elevator",
        "entity_shelter_elevator": "lobby", "entity_sloppy_runes": "elevator",
    }
    remapped = _deep_remap_ids(positions, remap)
    # character position keys survive verbatim -> room_of("Dr. Moon") resolves
    assert remapped.get("Dr. Moon") == "elevator"
    assert remapped.get("Hinami") == "elevator"
    # object key was rewritten to its new uid (no longer the old string)
    assert "entity_shelter_elevator" not in remapped
    assert "lobby" in remapped.values()


def test_no_protection_still_remaps_everything():
    """Back-compat: with no protected set, behaviour is unchanged (all ids
    remap, including the character-name ids -- the pre-fix behaviour)."""
    remap = _build_world_id_remap(_blob())
    assert set(remap.keys()) == {"Dr. Moon", "Hinami",
                                 "entity_shelter_elevator", "entity_sloppy_runes"}
