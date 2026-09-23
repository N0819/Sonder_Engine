"""A contact naming a body by its entity key is kept, under the body's name.

`normalize_scene_subjects` folds every subject-keyed ledger onto one spelling
at the top of the merge, before the beat's contact ops are applied, and
`normalize_scene_contacts` drops a contact whose endpoint has no position. An
op naming a body by its scene-entity key therefore arrived unfolded and was
dropped without a word: playerless Aldermill round 9 (2026-09-23), idx 3 and
8, the encoder wrote `char_emory_vane` for his fingers on the sluice cheek
and his knee on the flags, and neither survived the commit.
"""

from __future__ import annotations

from world.spatial import merge_scene_with_diff


def _race():
    return {
        "rooms": {"mill_race": {
            "name": "Mill Race", "adjacent": [],
            "anchors": {"sluice_gate": {"desc": "The oak sluice gate."}}}},
        "positions": {"Emory Vane": "mill_race"},
        "entities": {"char_emory_vane": {"name": "Emory Vane", "kind": "person"}},
        "contacts": [],
    }


def _fingers(actor):
    return {"op": "add", "actor": actor, "actor_part": "fingers",
            "target": "sluice_gate", "target_part": "oak sluice cheek",
            "manner": "press", "relation": "surface", "motion": "settled"}


def test_an_entity_key_is_folded_to_the_body_and_kept():
    merged = merge_scene_with_diff(_race(), {"contact_ops": [_fingers("char_emory_vane")]})
    kept = [c for c in merged.get("contacts") or []
            if c.get("target_part") == "oak sluice cheek"]
    assert [c["actor"] for c in kept] == ["Emory Vane"]


def test_the_name_itself_is_unchanged():
    merged = merge_scene_with_diff(_race(), {"contact_ops": [_fingers("Emory Vane")]})
    assert [c["actor"] for c in merged.get("contacts") or []] == ["Emory Vane"]


def test_nobody_the_scene_holds_is_still_dropped():
    merged = merge_scene_with_diff(_race(), {"contact_ops": [_fingers("char_nobody")]})
    assert merged.get("contacts") == []
