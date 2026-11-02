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

SUPERSEDED 2026-11-01 (audit persistence F10): the branch no longer remaps
any `world_entities` id at all. The table is keyed `(chat_id, entity_id)`
since v14, so a branch can keep every id verbatim, and the exact-string
rewrite the remap drove turned ordinary words equal to an entity id
(`barrier: "door"`) into hex. These tests now pin the stronger rule the bug
above is a special case of: nothing chat-scoped moves, characters included.
`tests/test_a_branch_keeps_the_storys_own_ids.py` holds the new tests.
"""

from __future__ import annotations

from web.app import _build_world_id_remap, _deep_remap_ids


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
    # characters do not remap -- and since F10 neither do objects: the ids
    # are the story's own under a (chat_id, entity_id) key
    assert dict(remap) == {}


def test_scene_positions_keep_character_keys_after_remap():
    remap = _build_world_id_remap(_blob(), protected_ids={"Dr. Moon", "Hinami"})
    positions = {
        "Dr. Moon": "elevator", "Hinami": "elevator",
        "entity_shelter_elevator": "lobby", "entity_sloppy_runes": "elevator",
    }
    remapped = _deep_remap_ids(positions, remap)
    # character position keys survive verbatim -> room_of("Dr. Moon") resolves,
    # and (F10) the object keys survive too
    assert remapped == positions


def test_no_protection_still_remaps_nothing_chat_scoped():
    """With no protected set the character-name ids used to remap with the
    objects (the pre-fix behaviour); since F10 no world_entities id remaps,
    protected or not."""
    remap = _build_world_id_remap(_blob())
    assert dict(remap) == {}
