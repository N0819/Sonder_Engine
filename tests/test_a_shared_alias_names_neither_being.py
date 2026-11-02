"""An alias two beings share names NEITHER of them -- in `same_subject` as in
every other identity reader of the module.

Audit world_spatial_structure_light F5 (2026-11-01, CONFIRMED mechanism):
`same_subject` resolved each side through `_entity_named` (first match wins),
while `room_of` and `canonical_subject_map` refuse ambiguity under the module's
own rule, "AMBIGUITY RESOLVES TO NOTHING". With "Guard Aldo" and "Guard Bren"
both aliased "the guard" and a contact's actor written "the guard",
`same_subject('the guard', 'Guard Aldo')` and `same_subject('the guard', 'Guard
Bren')` were both True, and `contact_sensation` told BOTH guards "You feel
Hinami's shoulder against your hand" -- a non-party "feels nothing, and this
must never be the thing that tells them otherwise".
"""

from world.spatial import contact_sensation, same_subject


def _scene():
    return {
        "rooms": {"gate": {"name": "Gate", "adjacent": []}},
        "positions": {"Guard Aldo": "gate", "Guard Bren": "gate", "Hinami": "gate",
                      "Captain Vey": "gate"},
        "entities": {
            "aldo": {"name": "Guard Aldo", "kind": "person", "aliases": ["the guard"]},
            "bren": {"name": "Guard Bren", "kind": "person", "aliases": ["the guard"]},
            "vey": {"name": "Captain Vey", "kind": "person", "aliases": ["the captain"]},
        },
        "attire": {"Guard Aldo": {}, "Guard Bren": {}, "Hinami": {}, "Captain Vey": {}},
        "contacts": [],
    }


def test_a_shared_alias_matches_neither():
    sc = _scene()
    assert same_subject(sc, "the guard", "Guard Aldo") is False
    assert same_subject(sc, "the guard", "Guard Bren") is False
    assert same_subject(sc, "Guard Aldo", "the guard") is False


def test_an_alias_one_being_holds_still_matches():
    sc = _scene()
    assert same_subject(sc, "the captain", "Captain Vey") is True
    assert same_subject(sc, "vey", "the captain") is True
    assert same_subject(sc, "the guard", "the guard") is True     # same spelling


def test_neither_guard_feels_a_touch_written_to_the_shared_alias():
    contact = {"actor": "the guard", "actor_part": "hand", "target": "Hinami",
               "target_part": "shoulder", "manner": "rest",
               "relation": "surface", "motion": "settled"}
    for guard in ("Guard Aldo", "Guard Bren"):
        assert contact_sensation(contact, you=guard, scene=_scene()) == ""
