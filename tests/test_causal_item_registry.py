"""The Director's explicit handles identify things across the whole input."""

import pytest

from llm.schemas import validate_llm_output_strict


PAYLOAD = {
    "event_inputs": [{"entity_id": "persona:1", "authority_mode": "world_author",
                      "events": [{"event_id": "raw:1", "type": "raw_input"}]}],
    "identity_index": {"persona:1": "Ilya", "character:2": "Sera"},
}


def row(number, handles, names):
    return {"chrono_id": number, "item_ids": handles, "item_names": names,
            "source_entity_id": "persona:1", "source_event_id": "raw:1",
            "event": "Ilya lifts the object.", "commitment": "asserted",
            "resolution_notes": "The object is held.", "categories": ["inventory_ops"]}


def report(*rows):
    return validate_llm_output_strict(
        "director_interpret", {"ledgers": list(rows)}, source_payload=PAYLOAD)


def test_same_handle_with_case_and_outer_whitespace_variation_is_stable():
    result = report(row(1, [1], ["Blue tin"]), row(2, [1], ["  BLUE TIN  "]))
    assert result.valid, result.errors


def test_distinct_handles_may_name_two_identical_cups():
    result = report(row(1, [1, 2], ["white cup", "white cup"]))
    assert result.valid, result.errors
    assert result.output["ledgers"][0]["item_ids"] == [1, 2]


def test_legacy_singular_rows_keep_their_existing_repair_path():
    rows = []
    for number, name in [(1, "Ilya"), (2, "Sera")]:
        legacy = row(number, [], [])
        legacy.pop("item_ids")
        legacy.pop("item_names")
        legacy.update(item_id=0, object_name=name)
        rows.append(legacy)
    result = report(*rows)
    assert result.valid, result.errors


def test_an_out_of_row_transform_never_borrows_the_first_item_identity():
    from agents.director import _transform_item_id, _bind_specialist_patches
    ledger = {"chrono_id": 4, "item_ids": [2, 3], "item_names": ["Ivo", "Grey satchel"]}
    bad = {"item": "Yellow tag", "patch": {"inventory_ops": [
        {"object_id": "tag", "to_id": "satchel", "relation": "mounted"}]}}
    notes = []
    assert _transform_item_id(ledger, bad, 2, notes, 0) is None
    assert "rejected" in notes[0]
    good = {"item": "Grey satchel", "patch": {"inventory_ops": [
        {"object_id": "satchel", "to_id": "Ivo", "relation": "held"}]}}
    scene = {"entities": {"satchel": {"name": "Grey satchel"},
                           "tag": {"name": "Yellow tag"}}, "positions": {"Ivo": "hall"}}
    patches, bindings, _ = _bind_specialist_patches(
        {"objects": {"results": [{"transforms": [bad, good]}]}},
        {"objects": {"ledger_items": [ledger]}}, scene, {})
    assert ("objects", 0, 0) not in patches
    assert patches[("objects", 0, 1)]["inventory_ops"][0]["to_id"] == "Ivo"
    assert "2" not in bindings


def test_related_transfer_object_cannot_replace_a_standing_actor_identity():
    from world.causal_program import bind_items
    scene = {"entities": {"tag": {"name": "Yellow tag"}},
             "positions": {"Ivo": "hall", "tag": "hall"}}
    rows = [{"chrono_id": 1, "item_id": 2, "object_name": "Ivo", "patch": {
        "inventory_ops": [{"object_id": "tag", "to_id": "Ivo", "relation": "held"}]}}]
    bound, bindings, notes = bind_items(rows, scene)
    assert bound[0]["patch"]["inventory_ops"][0] == rows[0]["patch"]["inventory_ops"][0]
    assert not bindings
    assert any(note["reason"] == "related world keys are not item aliases" for note in notes)


@pytest.mark.parametrize('reference', ['tag', 'Yellow tag', 'CLIPPED MARKER'])
def test_related_object_names_and_aliases_cannot_replace_actor_identity(reference):
    from world.causal_program import bind_items
    scene = {'entities': {'tag': {'name': 'Yellow tag', 'aliases': ['clipped marker']}},
             'positions': {'Ivo': 'hall', 'tag': 'hall'}}
    rows = [{'chrono_id': 1, 'item_id': 2, 'object_name': 'Ivo', 'patch': {
        'inventory_ops': [{'object_id': reference, 'to_id': 'Ivo', 'relation': 'held'}]}}]
    bound, bindings, _ = bind_items(rows, scene)
    assert bound[0]['patch']['inventory_ops'][0]['object_id'] == reference
    assert bound[0]['patch']['inventory_ops'][0]['to_id'] == 'Ivo'
    assert not bindings


def test_new_related_entity_cannot_overwrite_a_standing_actor():
    from world.causal_program import bind_items
    scene = {'positions': {'Ivo': 'hall'}}
    rows = [{'chrono_id': 1, 'item_id': 2, 'object_name': 'Ivo', 'patch': {
        'entities': {'tag': {'name': 'Yellow tag', 'kind': 'object'}}}}]
    bound, bindings, _ = bind_items(rows, scene)
    assert bound[0]['patch']['entities'] == rows[0]['patch']['entities']
    assert not bindings

