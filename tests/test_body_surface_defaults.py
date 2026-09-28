"""Surface instructions accompany body work without inventing surface duties."""

from collections import defaultdict
from copy import deepcopy
from pathlib import Path

import pytest

from agents import director
from llm import prompts
from persist.commit import compose_beat_scene
from tests.director_fakes import BASE_SCENE, _fake_agent, _make_ctx, encoder_event


ROOT = Path(__file__).resolve().parents[1]


def _row(chrono, event, categories, names=None):
    names = names or ["Mara"]
    return {
        "chrono_id": chrono, "item_ids": list(range(1, len(names) + 1)),
        "item_names": names, "source_entity_id": "character:mara",
        "source_event_id": "scene:1", "commitment": "asserted",
        "event": event, "observable": event, "resolution_notes": event,
        "categories": categories,
    }


def test_specialist_can_still_require_the_exact_overlay_output_channel():
    ledger = _row(1, "Soot marks Mara's cheek.", ["substance_ops"])
    requests = director._completion_requests(
        [("contact", {"ledger_items": [ledger]})],
        {"contact": {"results": [{"required_channels": ["overlays"]}]}})
    assert len(requests) == 1
    assert requests[0]["to"] == "body"
    assert requests[0]["channels"] == ["overlays"]
    assert not requests[0]["full_scope"]


def _coat_scene():
    initial = deepcopy(BASE_SCENE)
    initial["entities"]["coat"] = {
        "name": "Violet coat", "kind": "object", "portable": True,
        "state": {"clothing": True, "garment": "Violet coat", "shed": True},
    }
    initial["positions"]["coat"] = "keeper_room"
    initial["contained"] = {"coat": {"in": "Mara", "mode": "held"}}
    initial["attire"]["Mara"] = {"wearing": [], "regions": {}}
    return initial

WORN = {"op": "transfer", "object_id": "coat", "from_id": "Mara",
        "to_id": "Mara", "relation": "worn"}


@pytest.mark.parametrize("with_attire", [True, False])
def test_fresh_forwarded_attire_call_gets_surface_scope_without_requiring_a_surface_write(temp_db, prose_director, monkeypatch, with_attire):
    """Ported 2026-09-27 to the prose Director: one encoder event writes the
    worn transfer and, with `with_attire`, the attire add. Without it the
    garment's `attire` requirement is reported unfulfilled -- there is no hand
    left to forward it to.
    """
    initial = _coat_scene()
    transforms = [{"item": "Violet coat", "patch": {"inventory_ops": [dict(WORN)]}}]
    if with_attire:
        transforms.append({"item": "Violet coat", "patch": {
            "attire": {"Mara": {"add": ["Violet coat"]}}}})
    event = encoder_event("Mara puts the Violet coat on.", source="character:mara",
                          transforms=transforms)
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_prose": {"prose": "Mara puts the Violet coat on."},
        "director_specialist": {"events": [event], "missing_tools": [],
                                "missing_referents": [], "notes": []},
    }))
    ctx = _make_ctx(temp_db, scene=initial, interp={"sequence": []})
    out = director.director_resolve(ctx, 0)
    reqs = out["state_diff"]["causal_steps"][0]["requirements"]
    ctx.director_resolve = out
    composed = compose_beat_scene(ctx)
    if with_attire:
        assert "Violet coat" in composed.scene["attire"]["Mara"]["wearing"]
        assert not composed.scene.get("overlays", {}).get("Mara")
        assert composed.causal_worlds[0]["completion"]["action_status"] == "applied"
        assert all("overlays" not in row.get("channels", []) for row in reqs)
        assert not out["orchestration"].get("unfulfilled_requests")
    else:
        assert any(r["to"] == "body" and r["channels"] == ["attire"]
                   for r in out["orchestration"]["unfulfilled_requests"])


def test_generic_body_surface_changes_keep_intermediate_world_and_completion(temp_db, prose_director, monkeypatch):
    """Ported 2026-09-27 to the prose Director: two encoder events, the soot
    and its wiping.
    """
    initial = deepcopy(BASE_SCENE)
    events = [
        encoder_event("Soot settles on Mara's cheek.", source="character:mara",
                      transforms=[{"item": "Mara", "patch": {"overlays": {"Mara": [
                          {"name": "soot on cheek", "active": True}]}}}]),
        encoder_event("Mara wipes the soot from her cheek.", source="character:mara",
                      transforms=[{"item": "Mara", "patch": {"overlays": {"Mara": [
                          {"name": "soot on cheek", "active": False}]}}}]),
    ]
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_prose": {"prose": "Soot settles on Mara's cheek; she wipes it away."},
        "director_specialist": {"events": events, "missing_tools": [],
                                "missing_referents": [], "notes": []},
    }))
    ctx = _make_ctx(temp_db, scene=initial, interp={"sequence": []})
    out = director.director_resolve(ctx, 0)
    assert [c["step_key"] for c in calls] == ["director_prose", "director_specialist"]
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


@pytest.mark.parametrize("language", ["en", "ja"])
def test_surface_appearance_is_always_askable_and_its_chunk_reaches_the_encoder(
        language, monkeypatch):
    """Replaces the causal body hand's always-loaded surface chunk: on the
    prose path the decision model is asked about `overlays` on every beat that
    keeps it, and granting it ships the encoder's overlays chunk whole."""
    from collections import defaultdict
    from agents import director_prose
    from llm import prompts

    facts = defaultdict(lambda: False, vitals_tracked=False)
    assert "overlays" in director_prose.candidate_channels("resolve", facts)
    monkeypatch.setattr(prompts, "_preset_override", lambda *_: None)
    sheet = prompts.unified_specialist_prompt(["overlays"], language, [])
    card = (ROOT / "language_packs" / language / "cards" / "system_prompts"
            / "encoder" / "overlays.txt").read_text(encoding="utf-8").strip()
    assert card in sheet

