"""What the opening puts in a body's keeping is carried by that body.

The opening's way of saying so is `held_by` on the thing, asked of it since
2026-09-15 (Hollin Mill) and read by `derive_borne_containment`. It was never
declared on `SceneEntityDef`, so the validation round-trip dropped it from
every opening that wrote it -- on the shipped Pydantic 2 stack as on the
other. Saltmarsh Crossing (2026-10-11, chat 170) opened with a traveller
holding her ledger and the Office's letter; both were minted loose on the
slip, stayed there when she crossed the river, and the letter's hand-off at
the harbour office was refused as not hers.

Walked here through the path an opening takes: the establish validation, the
scene merge, and the carriage derivation the commit runs after it.
"""
from __future__ import annotations

from llm.schemas import validate_llm_output
from persist.commit import derive_borne_containment
from world.spatial import merge_scene_with_diff

ROOMS = {
    "south_slip": {"name": "South slip", "adjacent": ["chain_ferry"]},
    "chain_ferry": {"name": "Chain ferry", "adjacent": ["south_slip", "north_quay"]},
    "north_quay": {"name": "North quay", "adjacent": ["chain_ferry", "harbour_office"]},
    "harbour_office": {"name": "Harbour office", "adjacent": ["north_quay"],
                       "anchors": {"desk": {"desc": "a slant-topped desk"}}},
}


def _opening():
    """The establish's answer, as validated: she holds the letter and the
    ledger; the bag is set on the stone beside her."""
    answer = {
        "location": "Saltmarsh Crossing", "scene_description": "Low tide.",
        "rooms": ROOMS,
        "entities": {
            "agnes": {"name": "Agnes Holloway", "kind": "person"},
            "office_letter": {"name": "the Office's letter", "kind": "document",
                              "portable": True, "held_by": "Agnes Holloway"},
            "agnes_ledger": {"name": "ledger", "kind": "book", "portable": True,
                             "held_by": "Agnes Holloway"},
            "agnes_bag": {"name": "canvas bag", "kind": "bag", "portable": True},
        },
        "positions": {"Agnes Holloway": "south_slip", "office_letter": "south_slip",
                      "agnes_ledger": "south_slip", "agnes_bag": "south_slip"},
        "attire": {"Agnes Holloway": {"wearing": ["travelling coat"]}},
    }
    out, _warnings = validate_llm_output("director_establish", answer)
    return out


def _commit(scene, diff):
    scene = merge_scene_with_diff(scene, diff)
    derive_borne_containment(scene)
    return scene


def _scene_after_opening():
    out = _opening()
    return _commit({}, {"rooms": out["rooms"], "entities": out["entities"],
                        "positions": out["positions"],
                        "attire": {"Agnes Holloway": {"torso": [{"item": "travelling coat"}]}}})


def test_the_validation_keeps_who_carries_a_thing():
    entities = _opening()["entities"]
    assert entities["office_letter"]["held_by"] == "Agnes Holloway"
    assert "held_by" not in entities["agnes_bag"], "silence stays silence"


def test_what_she_holds_is_carried_and_what_she_set_down_is_not():
    scene = _scene_after_opening()
    assert scene["contained"]["office_letter"]["in"] == "Agnes Holloway"
    assert scene["contained"]["agnes_ledger"]["in"] == "Agnes Holloway"
    assert "agnes_bag" not in scene["contained"]


def test_it_crosses_the_river_with_her_and_the_bag_does_not():
    scene = _commit(_scene_after_opening(), {"positions": {"Agnes Holloway": "north_quay"}})
    assert scene["positions"]["office_letter"] == "north_quay"
    assert scene["positions"]["agnes_ledger"] == "north_quay"
    assert scene["positions"]["agnes_bag"] == "south_slip"


def test_a_later_beat_naming_the_letter_without_its_holder_does_not_set_it_down():
    scene = _commit(_scene_after_opening(), {"entities": {"office_letter": {
        "name": "the Office's letter", "kind": "document", "portable": True,
        "state": {"seal": "unbroken"}}}})
    assert scene["entities"]["office_letter"]["held_by"] == "Agnes Holloway"
    assert scene["contained"]["office_letter"]["in"] == "Agnes Holloway"


def test_set_down_at_the_desk_it_is_the_desks():
    scene = _commit(_scene_after_opening(), {"positions": {"Agnes Holloway": "harbour_office"}})
    scene = _commit(scene, {"inventory_ops": [{
        "op": "transfer", "object_id": "office_letter",
        "from_id": "Agnes Holloway", "to_id": "desk"}]})
    assert "office_letter" not in scene["contained"]
    assert "held_by" not in scene["entities"]["office_letter"]
    assert scene["positions"]["office_letter"] == "harbour_office"
    assert scene["stations"]["office_letter"]["at"] == "desk"
