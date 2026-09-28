"""Completion is an observed domain result, not a model's success label."""
from copy import deepcopy

from agents import director
from tests.director_fakes import BASE_SCENE, _fake_agent, _make_ctx, encoder_event
from world.causal_completion import annotate_event_execution
from world.spatial import merge_scene_with_diff


def _tin_program(temp_db, monkeypatch, states):
    """One encoder event per lid state, each writing the tin's `hatch`."""
    initial = deepcopy(BASE_SCENE)
    initial["entities"]["tin"] = {"name": "Tin", "kind": "object", "state": {"hatch": "closed"}}
    initial["positions"]["tin"] = "keeper_room"
    events = [encoder_event(
        "Changes the tin lid", source="character:mara",
        observable="Changes the tin lid",
        transforms=[{"item": "Tin", "patch": {
            "entities": {"tin": {"state": {"hatch": state}}}}}])
        for state in states]
    responses = {"director_prose": {"prose": "Mara works the tin lid, again and again."},
                 "director_specialist": {"events": events, "missing_tools": [],
                                         "missing_referents": [], "notes": []}}
    monkeypatch.setattr(director, "_agent_json", _fake_agent([], responses))
    ctx = _make_ctx(temp_db, scene=initial, interp={"sequence": []})
    out = director.director_resolve(ctx, 0)
    worlds = []
    final = merge_scene_with_diff(initial, out["state_diff"], causal_worlds=worlds)
    return out, worlds, final


def test_unchanged_is_checked_after_previous_events_not_against_initial_scene(
        temp_db, monkeypatch, prose_director):
    out, worlds, final = _tin_program(temp_db, monkeypatch, ["open", "closed", "closed"])
    assert final["entities"]["tin"]["state"]["hatch"] == "closed"
    assert [world["completion"]["status"] for world in worlds] == ["applied", "applied", "unchanged"]
    events = annotate_event_execution(out["beat_events"], worlds)
    assert [event["execution"] for event in events] == ["applied", "applied", "unchanged"]


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

