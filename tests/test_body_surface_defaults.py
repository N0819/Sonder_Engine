"""Surface instructions accompany body work without inventing surface duties."""

from collections import defaultdict
from copy import deepcopy
from pathlib import Path
import re
from types import SimpleNamespace

import pytest

from agents import director
from llm import prompts
from persist.commit import compose_beat_scene
from tests.test_director_orchestration import BASE_SCENE, _fake_agent, _make_ctx


ROOT = Path(__file__).resolve().parents[1]


def _surface_chunk(language="en"):
    return (ROOT / "language_packs" / language / "cards" / "system_prompts"
            / "specialists" / "body" / "chunks" / "overlays.txt").read_text().strip()


def _row(chrono, event, categories, names=None):
    names = names or ["Mara"]
    return {
        "chrono_id": chrono, "item_ids": list(range(1, len(names) + 1)),
        "item_names": names, "source_entity_id": "character:mara",
        "source_event_id": "scene:1", "commitment": "asserted",
        "event": event, "observable": event, "resolution_notes": event,
        "categories": categories,
    }


@pytest.mark.parametrize("category", ["body", "attire", "conditions"])
@pytest.mark.parametrize("language", ["en", "ja"])
def test_addressed_body_gets_surface_instruction_without_standing_marks_or_physical_gate(
        category, language, monkeypatch):
    scene = deepcopy(BASE_SCENE)
    facts = defaultdict(lambda: False, vitals_tracked=False)
    facts["resolved_stage"] = True
    view = {"source": "resolve", "spans": [
        _row(1, "A new surface change is resolved.", [category])]}
    dispatch = director._dispatch_specialists(None, scene, facts, view)
    body = dispatch["body"]
    assert scene["overlays"] == {}
    assert body["run"] and "overlays" in body["scope"]
    assert [name for name, state in dispatch.items() if state["run"]] == ["body"]
    assert not body["facts"]["physical_beat"]
    assert not body["facts"]["overlays_present"]
    monkeypatch.setattr(prompts, "_preset_override", lambda *_: None)
    sheet = prompts.specialist_prompt("body", body["scope"], language)
    assert _surface_chunk(language) in sheet


@pytest.mark.parametrize("categories", [["entities"], ["speech"], []])
def test_default_surface_instruction_does_not_dispatch_an_unaddressed_body(categories):
    facts = defaultdict(lambda: False, vitals_tracked=False)
    view = {"source": "resolve", "spans": [_row(1, "Another kind of event.", categories)]}
    dispatch = director._dispatch_specialists(None, deepcopy(BASE_SCENE), facts, view)
    assert not dispatch["body"]["run"]
    assert dispatch["body"]["scope"] == []


@pytest.mark.parametrize("category", ["overlays", "marks"])
def test_retired_surface_category_still_routes_only_its_body_owner(category):
    facts = defaultdict(lambda: False, vitals_tracked=False)
    view = {"source": "resolve", "spans": [
        _row(1, "A historical surface event.", [category])]}
    dispatch = director._dispatch_specialists(None, deepcopy(BASE_SCENE), facts, view)
    assert [name for name, state in dispatch.items() if state["run"]] == ["body"]
    assert "overlays" in dispatch["body"]["scope"]
    omission = {"category": category, "subject": "Mara",
                "change": "Soot marks her cheek."}
    routed, core = director._route_repair_omissions([omission])
    assert not core and list(routed) == ["body"]


@pytest.mark.parametrize("language", ["en", "ja"])
def test_director_menu_routes_surface_changes_to_body(language):
    text = (ROOT / "language_packs" / language / "cards" / "system_prompts"
            / "causal_director.txt").read_text()
    menu = [line for line in text.splitlines()
            if line.split(":", 1)[0] in director.SPECIALISTS]
    assert len(menu) == len(director.SPECIALISTS)
    assert not re.search(r"\b(?:overlays|marks)\b", "\n".join(menu))
    body_menu = next(line for line in menu if line.startswith("body:"))
    assert body_menu.split(":", 1)[1].strip().startswith("body ")
    assert 'categories:["body"]' in text


def test_specialist_can_still_require_the_exact_overlay_output_channel():
    ledger = _row(1, "Soot marks Mara's cheek.", ["substance_ops"])
    requests = director._completion_requests(
        [("contact", {"ledger_items": [ledger]})],
        {"contact": {"results": [{"required_channels": ["overlays"]}]}})
    assert len(requests) == 1
    assert requests[0]["to"] == "body"
    assert requests[0]["channels"] == ["overlays"]
    assert not requests[0]["full_scope"]


def test_legacy_attire_repair_also_grants_and_keeps_surface_output(monkeypatch):
    warnings, calls = [], []
    ctx = SimpleNamespace(language="en", cast=[], add_warning=warnings.append)
    monkeypatch.setattr(director, "_specialist_payload", lambda *args: {})
    monkeypatch.setattr(prompts, "_preset_override", lambda *_: None)
    patch = {"attire": {"Mara": {"remove": ["coat"]}},
             "overlays": {"Mara": [{"name": "soot on cheek"}]}}
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_body": patch}))
    diff, report = {}, {}
    repaired, _ = director._specialist_repairs(
        ctx, deepcopy(BASE_SCENE), diff,
        {"body": [("attire", {"category": "attire", "subject": "Mara",
                               "change": "The coat is removed."})]},
        {"source": "resolve"}, {}, report)
    assert repaired and not warnings
    assert report["specialist_repairs"]["body"]["scope"] == ["attire", "overlays"]
    assert _surface_chunk() in calls[0]["system"]
    assert diff["overlays"] == patch["overlays"]


def test_fresh_forwarded_attire_call_gets_surface_scope_without_requiring_a_surface_write(
        temp_db, monkeypatch):
    initial = deepcopy(BASE_SCENE)
    initial["entities"]["coat"] = {
        "name": "Violet coat", "kind": "object", "portable": True,
        "state": {"clothing": True, "garment": "Violet coat", "shed": True},
    }
    initial["positions"]["coat"] = "keeper_room"
    initial["contained"] = {"coat": {"in": "Mara", "mode": "held"}}
    initial["attire"]["Mara"] = {"wearing": [], "regions": {}}
    calls = []
    responses = {
        "director_resolve": {"ledgers": [
            _row(1, "Mara puts the Violet coat on.", ["inventory_ops"],
                 ["Mara", "Violet coat"])]},
        "director_objects": {"results": [{
            "status": "encoded", "settled": {}, "transforms": [{
                "item": "Violet coat", "patch": {"inventory_ops": [{
                    "op": "transfer", "object_id": "coat", "from_id": "Mara",
                    "to_id": "Mara", "relation": "worn"}]}}]}]},
        "director_body": {"results": [{
            "status": "encoded", "settled": {}, "transforms": [{
                "item": "Violet coat", "patch": {"attire": {
                    "Mara": {"add": ["Violet coat"]}}}}]}]},
    }
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, responses))
    ctx = _make_ctx(temp_db, scene=initial, interp={"sequence": []})
    out = director.director_resolve(ctx, 0)
    body_calls = [call for call in calls if call["step_key"] == "director_body"]
    assert len(body_calls) == 1
    assert out["orchestration"]["forwards"] == {"body": [1]}
    assert out["orchestration"]["specialists"]["body"]["scope"] == ["attire", "overlays"]
    assert _surface_chunk() in body_calls[0]["system"]
    assert body_calls[0]["payload"]["ledgers"][0]["requested_channels"] == ["attire"]
    ctx.director_resolve = out
    composed = compose_beat_scene(ctx)
    assert "Violet coat" in composed.scene["attire"]["Mara"]["wearing"]
    assert not composed.scene.get("overlays", {}).get("Mara")
    assert composed.causal_worlds[0]["completion"]["action_status"] == "applied"
    requirements = out["state_diff"]["causal_steps"][0]["requirements"]
    assert all("overlays" not in row.get("channels", []) for row in requirements)


def test_generic_body_surface_changes_keep_intermediate_world_and_completion(
        temp_db, monkeypatch):
    initial = deepcopy(BASE_SCENE)
    rows = [
        _row(1, "Soot settles on Mara's cheek.", ["body"]),
        _row(2, "Mara wipes the soot from her cheek.", ["body"]),
    ]
    answers = [{"status": "encoded", "settled": {}, "transforms": [{
        "item": "Mara", "patch": {"overlays": {"Mara": [{
            "name": "soot on cheek", "active": active}]}}}]} for active in (True, False)]
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_resolve": {"ledgers": rows},
        "director_body": {"results": answers},
    }))
    ctx = _make_ctx(temp_db, scene=initial, interp={"sequence": []})
    out = director.director_resolve(ctx, 0)
    assert [call["step_key"] for call in calls] == ["director_resolve", "director_body"]
    body_call = calls[1]
    assert _surface_chunk() in body_call["system"]
    assert all(row["categories"] == ["body"] for row in body_call["payload"]["ledgers"])
    assert all(not {"chrono_id", "item_id", "item_ids"} & row.keys()
               for row in body_call["payload"]["ledgers"])
    history = out["orchestration"]["transform_history"]
    assert [(row["chrono_id"], row["item_id"]) for row in history] == [(1, 1), (2, 1)]
    ctx.director_resolve = out
    composed = compose_beat_scene(ctx)
    worlds = composed.causal_worlds
    assert not worlds[0]["before"].get("overlays", {}).get("Mara")
    assert worlds[1]["before"]["overlays"]["Mara"][0]["name"] == "soot on cheek"
    assert not composed.scene.get("overlays", {}).get("Mara")
    assert [world["completion"]["status"] for world in worlds] == ["applied", "applied"]
    assert [world["completion"]["action_status"] for world in worlds] == ["applied", "applied"]
    assert all(effect["status"] == "applied"
               for world in worlds for effect in world["completion"]["effects"])
    for step in out["state_diff"]["causal_steps"]:
        assert all(not requirement.get("channels") for requirement in step["requirements"])
