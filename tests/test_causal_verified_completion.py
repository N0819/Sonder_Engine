"""Completion is an observed domain result, not a model's success label."""
from copy import deepcopy

from agents import director
from llm.llm_quality import _step_json_schema
from llm.schemas import semantic_output_errors
from tests.test_director_orchestration import BASE_SCENE, _fake_agent, _make_ctx
from world.causal_completion import annotate_event_execution
from world.spatial import merge_scene_with_diff


def test_live_wire_requires_desired_effect_for_already_true():
    wire = _step_json_schema("director_objects")
    definitions = wire.get("$defs", wire.get("definitions", {}))
    properties = definitions["LedgerTransformResult"]["properties"]
    assert "already_true" not in properties["status"]["enum"]
    assert "already_true" not in properties["settled"]["additionalProperties"]["enum"]
    payload = {"completion_contract": "verified_effects_v1", "ledgers": [
        {"item_names": ["Tin"], "categories": ["entities"]}]}
    result = {"results": [{"status": "already_true", "transforms": [], "settled": {}}]}
    errors = semantic_output_errors("director_objects", result, source_payload=payload)
    assert any("typed desired patch" in error for error in errors)
    # Stored old replies remain readable; current execution does not trust them.
    assert not semantic_output_errors("director_objects", result,
                                     source_payload={"ledgers": payload["ledgers"]})


def _tin_program(temp_db, monkeypatch, states):
    initial = deepcopy(BASE_SCENE)
    initial["entities"]["tin"] = {"name": "Tin", "kind": "object", "state": {"hatch": "closed"}}
    initial["positions"]["tin"] = "keeper_room"
    rows = [{"chrono_id": i, "item_ids": [7], "item_names": ["Tin"],
             "source_entity_id": "character:mara", "commitment": "asserted",
             "event": "Changes the tin lid", "observable": "Changes the tin lid",
             "resolution_notes": "Typed lid state", "categories": ["entities"]}
            for i, _ in enumerate(states, 1)]
    answers = [{"status": "encoded", "transforms": [{"item": "Tin", "patch": {
        "entities": {"tin": {"state": {"hatch": state}}}}}], "settled": {}}
        if state is not None else {"status": "already_true", "transforms": [], "settled": {}}
        for state in states]
    responses = {"director_resolve": {"ledgers": rows},
                 "director_objects": {"results": answers}}
    monkeypatch.setattr(director, "_agent_json", _fake_agent([], responses))
    ctx = _make_ctx(temp_db, scene=initial, interp={"sequence": []})
    out = director.director_resolve(ctx, 0)
    worlds = []
    final = merge_scene_with_diff(initial, out["state_diff"], causal_worlds=worlds)
    return out, worlds, final


def test_unchanged_is_checked_after_previous_events_not_against_initial_scene(temp_db, monkeypatch):
    out, worlds, final = _tin_program(temp_db, monkeypatch, ["open", "closed", "closed"])
    assert final["entities"]["tin"]["state"]["hatch"] == "closed"
    assert [world["completion"]["status"] for world in worlds] == ["applied", "applied", "unchanged"]
    events = annotate_event_execution(out["beat_events"], worlds)
    assert [event["execution"] for event in events] == ["applied", "applied", "unchanged"]


def test_bare_completion_claim_stays_in_log_as_unresolved(temp_db, monkeypatch):
    out, worlds, final = _tin_program(temp_db, monkeypatch, [None])
    assert final["entities"]["tin"]["state"]["hatch"] == "closed"
    assert worlds[0]["completion"]["status"] == "unresolved"
    events = annotate_event_execution(out["beat_events"], worlds)
    assert len(events) == 1
    assert events[0]["execution"] == "unresolved"
    assert not out["orchestration"]["specialists"]["objects"]["events_resolved"]


def test_unsupported_commit_domain_is_pending_not_a_verified_success():
    from world.causal_completion import execution_receipt
    receipt = execution_receipt({}, {}, {"chrono_id": 1, "transforms": [
        {"item_id": 2, "specialist": "social", "patch": {"public_evidence": [{"kind": "act"}]}}]})
    assert receipt["status"] == "pending"
    assert receipt["effects"][0]["code"] == "unsupported_channel"


def test_legacy_category_routes_owner_without_demanding_a_wrong_representation():
    from world.causal_completion import execution_receipt
    history = [{"chrono_id": 1, "item_id": 7, "specialist": "objects",
                "patch": {"entities": {"tin": {"state": {"hatch": "open"}}}}}]
    dispatch = {"objects": {"run": True,
        "ledger_items": [{"chrono_id": 1, "item_ids": [7], "item_names": ["Tin"],
                          "categories": ["artifacts"]}],
        "results": [{"status": "encoded"}]}}
    before = {"entities": {"tin": {"name": "Tin", "state": {"hatch": "closed"}}}}
    after = {"entities": {"tin": {"name": "Tin", "state": {"hatch": "open"}}}}
    requirements = director._causal_completion_requirements(dispatch, history)
    receipt = execution_receipt(before, after, {"chrono_id": 1, "transforms": history,
                                               "requirements": requirements})
    assert receipt["status"] == "applied"
    dispatch["objects"]["ledger_items"][0]["categories"] = ["artifact_ops"]
    requirements = director._causal_completion_requirements(dispatch, history)
    receipt = execution_receipt(before, after, {"chrono_id": 1, "transforms": history,
                                               "requirements": requirements})
    assert receipt["status"] == "unresolved"
