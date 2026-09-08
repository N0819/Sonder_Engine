"""A derived manifest event folds on garment PROOF, never on shared prose.

Review 2026-09-07 A41. `_fold_derived_manifest_events` accepted
`handle in attire.change` as proof that an entities/inventory entry described
the same change as an attire entry. An attire manifest entry is usually keyed
by the WEARER, so the wearer's name is in that prose: "Hinami picks up the
brass lantern" folded into "Hinami removes her cloak", and the lantern lost
its event id -- it was dispatched to no hand, checked against no evidence, and
left the manifest entirely.

The proof is now `resolve_garment`, and the wearer's own name is dropped from
the handles ONLY where the beat's register says that subject is a body -- a
registered cast member, or a scene key carrying attire/scales/vitals. String
identity with the sibling entry cannot stand in for that: the model also files
an attire entry keyed by the garment, and there the two entries share the
garment's name on purpose.
"""
import json

from story.character_schema import default_character_data

from agents.director import _manifest_items

#: The beat's register of who is a body. `scene["attire"]` is keyed by the
#: wearer, which is the ledger `world.spatial`'s `_is_body_entity` measured as
#: the exact split between a body and a lift car.
WEARER_SCENE = {"attire": {"Hinami": {"torso": []}}}


def _cast():
    sheet = default_character_data("Hinami")
    sheet["identity"]["uid"] = "hinami_uid"
    return [{"id": 3, "sheet": json.dumps(sheet)}]


def _items(*changes, cast=None, scene=None):
    return _manifest_items({"changes_asserted": list(changes)}, cast, scene)


def test_an_unrelated_entity_change_keeps_its_own_event():
    changes = (
        {"category": "attire", "subject": "Hinami",
         "change": "utility sash removed"},
        {"category": "entities", "subject": "Hinami",
         "change": "picks up the brass lantern from the table"},
        {"category": "entities", "subject": "utility sash",
         "change": "created in room, placed on floor"},
    )
    for register in ({"cast": _cast()}, {"scene": WEARER_SCENE}):
        items = _items(*changes, **register)
        assert [i["category"] for i in items] == ["attire", "entities"], register
        assert [i["event_id"] for i in items] == [1, 2]
        assert "lantern" in items[1]["change"]
        # The garment half still folds: one change, one owner, both categories.
        assert items[0].get("also_described_as") == ["entities"]


def test_the_shed_garment_still_folds_into_its_attire_event():
    items = _items(
        {"category": "attire", "subject": "Hinami",
         "change": "utility sash removed"},
        {"category": "attire", "subject": "Hinami",
         "change": "travel shorts removed"},
        {"category": "entities", "subject": "utility sash",
         "change": "created in room, placed on floor"},
        {"category": "entities", "subject": "travel shorts",
         "change": "created in room, placed on floor"},
        scene=WEARER_SCENE,
    )
    assert [i["category"] for i in items] == ["attire", "attire"]
    assert [i["event_id"] for i in items] == [1, 2]
    assert all(i.get("also_described_as") == ["entities"] for i in items)


def test_an_attire_entry_that_names_the_garment_as_subject_still_folds():
    items = _items(
        {"category": "attire", "subject": "silk robe",
         "change": "unbelted and drawn off Hinami"},
        {"category": "entities", "subject": "the robe",
         "change": "created in room, placed over the chair"},
        scene=WEARER_SCENE,
    )
    assert [i["category"] for i in items] == ["attire"]
    assert items[0].get("also_described_as") == ["entities"]


def test_the_two_entries_may_spell_the_garment_identically():
    """The measured shape of the duplication this fold exists to end: the
    attire entry keyed by the GARMENT, the entities entry naming the same
    garment with the same string. Dropping a handle that merely equals the
    sibling's subject left no handle at all, so the pair did not fold and the
    beat carried two events for one sash."""
    changes = (
        {"category": "attire", "subject": "utility sash",
         "change": "removed from Hinami"},
        {"category": "entities", "subject": "utility sash",
         "change": "created in room, placed on floor"},
    )
    for register in ({}, {"cast": _cast()}, {"scene": WEARER_SCENE}):
        items = _items(*changes, **register)
        assert [i["category"] for i in items] == ["attire"], register
        assert items[0].get("also_described_as") == ["entities"], register
