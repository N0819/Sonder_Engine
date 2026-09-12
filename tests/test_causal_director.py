from types import SimpleNamespace

from agents import director
from llm.llm_quality import _step_json_schema
from llm.prompts import prose_author_prompt, specialist_prompt
from llm.schemas import validate_llm_output_strict
from world.causality import compile_transforms


_span_items = director._span_items
normalize_causal_ledger = director.normalize_causal_ledger
span_owners = director.span_owners


def test_both_director_invocations_share_one_minimal_contract():
    shared = prose_author_prompt(set())
    assert "Convert event_inputs into ordered event ledgers" in shared
    assert "state_diff" not in shared
    assert "resolved_event" not in shared
    assert "player_declaration" not in shared
    assert len(shared) < 4_500


def test_authority_is_attached_to_identity_and_asserted_input_is_not_rerun():
    ctx = SimpleNamespace(
        chat=SimpleNamespace(persona_id=7),
        extra_players=[],
    )
    interp = {
        "authority_mode": "world_author",
        "sequence": [
            {"event_id": "asserted", "type": "action",
             "attempt": "opens the door", "commitment": "asserted"},
            {"event_id": "contested", "type": "action",
             "attempt": "strikes the guard", "commitment": "contestable"},
        ],
    }
    declarations = [{
        "char_id": 11, "name": "Mara",
        "sequence": [{"event_id": "mara:1", "type": "action",
                      "attempt": "steps back", "commitment": "asserted"}],
    }]
    groups = director._causal_event_inputs(
        ctx, interp, declarations, [], [])

    assert groups[0]["entity_id"] == "persona:7"
    assert groups[0]["authority_mode"] == "world_author"
    assert [event["event_id"] for event in groups[0]["events"]] == [
        "contested"]
    assert groups[1]["entity_id"] == "character:11"
    assert groups[1]["authority_mode"] == "autonomous"
    assert groups[1]["events"][0]["event_id"] == "mara:1"


def test_one_ledger_routes_to_every_owner_and_keeps_the_numeric_join():
    out = {"ledgers": [{
        "chrono_id": 99,
        "item_id": 7,
        "object_name": "coat",
        "source_entity_id": "character:11",
        "authority_mode": "autonomous",
        "source_event_id": "mara:1",
        "kind": "action",
        "event": "drops the coat on the bench",
        "resolution_notes": "The coat is unworn and rests on the bench.",
        "categories": ["attire", "entities", "positions"],
    }]}
    normalize_causal_ledger(out)
    spans = _span_items(out)

    assert spans[0]["event_id"] == 99
    assert spans[0]["item_id"] == 7
    assert spans[0]["object_name"] == "coat"
    assert spans[0]["authority_mode"] == "autonomous"
    assert spans[0]["_items"] == [{"id": 7, "name": "coat"}]
    assert span_owners(spans[0]) == ["body", "objects", "spatial"]


def test_recompiler_uses_every_transform_in_chronological_order():
    transforms = [
        {"item_id": 1,
         "patch": {"rooms": {"hall": {"state": {"open": True}}}}},
        {"item_id": 2,
         "patch": {"rooms": {"hall": {
             "name": "Hall", "state": {"open": False}}}}},
        {"item_id": 3,
         "patch": {"rooms": {"hall": {"desc": "north door"}}}},
    ]
    ledgers = [
        {"item_id": 1, "chrono_id": 2, "object_name": "north door"},
        {"item_id": 2, "chrono_id": 1, "object_name": "north door"},
        {"item_id": 3, "chrono_id": 2, "object_name": "north door"},
    ]
    compiled, history, rejected = compile_transforms(
        transforms,
        allowed_channels=["rooms"],
        ledger_items=ledgers,
        allowed_item_ids=[1, 2, 3],
        specialist="spatial",
    )

    assert rejected == []
    assert [row["chrono_id"] for row in history] == [1, 2, 2]
    assert len(history) == len(transforms)
    assert compiled["rooms"]["hall"]["name"] == "Hall"
    assert compiled["rooms"]["hall"]["desc"] == "north door"
    assert compiled["rooms"]["hall"]["state"] == {"open": True}
    assert history[1]["supersedes"] == [{
        "channel": "rooms", "object": "hall",
        "prior_chrono_id": 1, "prior_item_id": 2,
    }]
    assert history[1]["patch"]["rooms"]["hall"]["state"] == {
        "open": True}


def test_specialist_results_are_positional_and_match_every_input_ledger():
    payload = {"ledgers": [{"object_name": "coat"},
                           {"object_name": "scarf"}]}
    report = validate_llm_output_strict(
        "director_body",
        {"results": [{
            "transforms": [{"patch": {"attire": {
                "Mara": {"remove": ["coat"]}}}}],
            "status": "encoded",
        }]},
        source_payload=payload,
    )
    assert not report.valid
    assert any("one entry per input ledger" in error
               for error in report.errors)


def test_specialists_are_prompted_for_multiple_transforms_not_direct_diffs():
    for name in ("body", "social", "contact", "objects", "spatial"):
        sheet = specialist_prompt(name, [], "en")
        assert "emit a transform" in sheet
        assert "same array position" in sheet
        assert "Do not emit item_id or chrono_id" in sheet
        assert 'Output STRICT JSON {"results":[' in sheet


def test_wire_grammars_expose_only_the_current_contracts():
    for step in ("director_interpret", "director_resolve"):
        schema = _step_json_schema(step)
        assert set(schema["properties"]) == {"ledgers"}
    for step in ("director_body", "director_social", "director_contact",
                 "director_objects", "director_spatial"):
        schema = _step_json_schema(step)
        assert set(schema["properties"]) == {"results", "notes"}


def test_current_director_rejects_invented_sources_and_unknown_channels():
    payload = {"event_inputs": [{
        "entity_id": "entity:1", "authority_mode": "autonomous",
        "events": [{"event_id": "source:1", "type": "action"}],
    }]}
    ledger = {
        "chrono_id": 1, "item_id": 1, "object_name": "door",
        "source_entity_id": "invented:2", "authority_mode": "autonomous",
        "source_event_id": "source:1", "kind": "action",
        "event": "The door opens.", "commitment": "asserted",
        "resolution_notes": "The door is open.",
        "categories": ["imaginary_channel"],
    }
    report = validate_llm_output_strict(
        "director_resolve", {"ledgers": [ledger]}, source_payload=payload)
    assert not report.valid
    assert any("source_entity_id was not supplied" in error
               for error in report.errors)
    assert any("unknown channels" in error for error in report.errors)


def test_recompiler_preserves_list_transforms_and_replaces_scalar_state():
    compiled, history, rejected = compile_transforms(
        [{"item_id": 1, "patch": {
            "following_ops": [{"op": "start", "who": "Mara"}],
            "location": "North Road",
        }}],
        allowed_channels=["following_ops", "location"],
        ledger_items=[{"item_id": 1, "chrono_id": 1,
                       "object_name": "Mara"}],
        specialist="spatial",
    )
    assert rejected == []
    assert compiled["following_ops"] == [{
        "op": "start", "who": "Mara", "from_event": 1}]
    assert compiled["location"] == "North Road"
    assert len(history) == 1
