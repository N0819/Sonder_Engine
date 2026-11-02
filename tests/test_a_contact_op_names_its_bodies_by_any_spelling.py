"""A contact `remove`, `clear` or `cross` ends the hold it names, whatever
spelling of the two bodies it is written in.

Audit world_spatial_movement_sight F3 (2026-11-01, CONFIRMED WRONG-SCENE): the
ledger's endpoints are canonicalised (`normalize_scene_contacts` ->
`canonical_subject`, the display name), but the release ops matched the raw op
text. The encoder writes entity keys (the module's own note: "the encoder wrote
`char_emory_vane`"), so with the ledger holding `Emory Vane hand -> Ada wrist`,
`{op: remove, actor: char_emory_vane, target: Ada}` and `{op: clear, actor:
char_emory_vane}` both left the hold standing, with no report -- and a missed
release stands through every contact-silent beat, delivered to both minds as a
live touch.
"""

from world.spatial import apply_contact_ops


def _scene():
    return {
        "rooms": {"hall": {"name": "Hall", "adjacent": []}},
        "positions": {"Emory Vane": "hall", "Ada": "hall"},
        "entities": {"char_emory_vane": {"name": "Emory Vane", "kind": "person"},
                     "char_ada": {"name": "Ada", "kind": "person"}},
        "attire": {"Emory Vane": {}, "Ada": {}},
        "contacts": [{"actor": "Emory Vane", "actor_part": "hand",
                      "target": "Ada", "target_part": "wrist",
                      "manner": "grip", "relation": "surface",
                      "motion": "settled", "unasserted": 0}],
    }


def test_a_remove_in_the_entity_key_spelling_ends_the_hold():
    sc = apply_contact_ops(_scene(), [
        {"op": "remove", "actor": "char_emory_vane", "target": "Ada"}])
    assert sc["contacts"] == []


def test_a_remove_naming_the_target_by_its_key_ends_the_hold():
    sc = apply_contact_ops(_scene(), [
        {"op": "remove", "actor": "Emory Vane", "target": "char_ada"}])
    assert sc["contacts"] == []


def test_a_clear_in_the_entity_key_spelling_ends_every_hold_of_that_body():
    sc = apply_contact_ops(_scene(), [{"op": "clear", "actor": "char_emory_vane"}])
    assert sc["contacts"] == []


def test_a_remove_naming_someone_else_leaves_the_hold():
    sc = _scene()
    sc["positions"]["Bo"] = "hall"
    sc["attire"]["Bo"] = {}
    sc = apply_contact_ops(sc, [{"op": "remove", "actor": "Bo", "target": "Ada"}])
    assert len(sc["contacts"]) == 1
