"""A partial entity diff must not erase the rest of the entity record.

Found live auditing chat "Elevator Adventure branch 41" (turn 91). The
Director sent a pose-only update for two entities that had been committed
correctly one turn earlier. Both came back gutted, and every later turn
read the corrupted values back:

    "Blue Police Box"  kind vehicle,   container, interior_rooms [tardis_interior_001]
        -> "Tardis 001"     kind object, not a container, no interior
    "The Doctor"       kind character, aliases [Doctor, Theta Sigma, John Smith]
        -> "The Doctor 10"  kind object, empty description

Two causes compounding: `merge_scene_with_diff` replaced entities wholesale
(`entities.update(diff)`) where rooms got `_merge_room`, and validation had
already filled every absent field -- so the replacement looked complete,
including a `name` invented from the dict key by `_fill_entity_names`.
"""

from __future__ import annotations

from schemas import is_derived_entity_name, validate_llm_output_strict
from spatial import merge_scene_with_diff


def _scene():
    return {
        "rooms": {
            "west_chamber": {"name": "West Passage Widening", "adjacent": []},
            "tardis_interior_001": {"name": "TARDIS Interior",
                                    "parent_entity": "tardis_001",
                                    "adjacent": []},
        },
        "entities": {
            "tardis_001": {
                "name": "Blue Police Box", "kind": "vehicle",
                "description": "A battered blue police box.",
                "aliases": ["tardis", "box", "police box"],
                "container": True, "interior_rooms": ["tardis_interior_001"],
                "state": {"transit": {"phase": "docked"}, "materializing": True},
            },
            "the_doctor_10": {
                "name": "The Doctor", "kind": "character",
                "description": "A lean, energetic figure in a pinstripe suit.",
                "aliases": ["Doctor", "Theta Sigma", "John Smith"],
                "state": {"pose": "standing"},
            },
        },
        "positions": {"tardis_001": "west_chamber",
                      "The Doctor": "west_chamber"},
    }


def _pose_only_diff():
    """The exact shape the live Director sent: state, nothing else."""
    raw = {"resolved_event": "The Doctor steps closer.",
           "state_diff": {"entities": {
               "the_doctor_10": {"state": {"pose": "stepping closer"}},
               "tardis_001": {"state": {"materializing": False}}}}}
    report = validate_llm_output_strict("director_resolve", raw)
    assert report.valid, report.errors
    return report.output["state_diff"]


def test_pose_only_diff_keeps_the_whole_entity():
    merged = merge_scene_with_diff(_scene(), _pose_only_diff())

    doctor = merged["entities"]["the_doctor_10"]
    assert doctor["name"] == "The Doctor"
    assert doctor["kind"] == "character"
    assert doctor["description"].startswith("A lean")
    assert doctor["aliases"] == ["Doctor", "Theta Sigma", "John Smith"]

    tardis = merged["entities"]["tardis_001"]
    assert tardis["name"] == "Blue Police Box"
    assert tardis["kind"] == "vehicle"
    assert tardis["container"] is True
    assert tardis["interior_rooms"] == ["tardis_interior_001"]


def test_the_update_itself_still_lands():
    merged = merge_scene_with_diff(_scene(), _pose_only_diff())
    assert merged["entities"]["the_doctor_10"]["state"]["pose"] == \
        "stepping closer"
    # Sibling state keys survive a partial state write -- the TARDIS keeps
    # the transit block the dock-edge derivation reads...
    tardis_state = merged["entities"]["tardis_001"]["state"]
    assert tardis_state["transit"] == {"phase": "docked"}
    # ...while the key the diff DID carry is applied, false included.
    assert tardis_state["materializing"] is False


def test_a_deliberate_change_still_wins():
    """Silence is not an erasure, but an authored value is not silence."""
    diff = {"entities": {"the_doctor_10": {
        "name": "The Doctor (disguised)", "kind": "character",
        "description": "Now in a stolen lab coat.", "aliases": ["Smith"]}}}
    doctor = merge_scene_with_diff(_scene(), diff)["entities"]["the_doctor_10"]
    assert doctor["name"] == "The Doctor (disguised)"
    assert doctor["description"] == "Now in a stolen lab coat."
    assert doctor["aliases"] == ["Smith"]


def test_a_brand_new_entity_is_unaffected():
    diff = {"entities": {"sonic_screwdriver": {
        "name": "Sonic Screwdriver", "kind": "object", "portable": True}}}
    merged = merge_scene_with_diff(_scene(), diff)
    assert merged["entities"]["sonic_screwdriver"]["portable"] is True
    assert merged["entities"]["sonic_screwdriver"]["name"] == "Sonic Screwdriver"


def test_derived_name_detection():
    # The forms _fill_entity_names can invent, for the keys that hit live.
    assert is_derived_entity_name("the_doctor_10", "The Doctor 10")
    assert is_derived_entity_name("tardis_001", "Tardis 001")
    assert is_derived_entity_name("41b518dc08c3436f", "Object", kind="object")
    # A real name is not a placeholder, even on the same key.
    assert not is_derived_entity_name("the_doctor_10", "The Doctor")
    assert not is_derived_entity_name("tardis_001", "Blue Police Box")
