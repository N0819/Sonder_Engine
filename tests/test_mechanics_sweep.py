"""Characterization tests for the mechanics sweep (movement/space Phase 2,
item 3) -- written BEFORE the commit_transit_sweep/prepare_scene_commit
refactor and kept green through it, per CLAUDE.md's orchestration-seam
warning.

They pin the composite behavior the refactor must preserve exactly:
- rerun determinism: same checkpoint + same input => identical world
  (scene KV, scheduled_events, world_conditions, engine_notices);
- the end-to-end prepare -> sweep -> commit_scene path (fire + schedule +
  expiry + dock-edge recompute + notice staging, persisted);
- pass (e) (companion-carry/zone inference) is applied to the PREPARED
  scene, so memory preparation -- which reads that scene before the write
  transaction opens -- sees carried companions at their new position.
"""

from __future__ import annotations

import json
import time

from checkpoints import ensure_checkpoint, restore_checkpoint
from commit import commit_scene, commit_transit_sweep, prepare_scene_commit
from pipeline_context import ChatData, PipelineContext, TurnData
from spatial import spatial_rel


def _elevator_scene(transit):
    return {
        "location": "Kessler Tower", "time": "night",
        "rooms": {
            "elevator_car": {
                "name": "Service Elevator", "desc": "A cramped car.",
                "adjacent": [], "parent_entity": "service_elevator",
            },
            "floor1_hall": {"name": "Floor One Hall", "desc": "Hallway.",
                            "adjacent": []},
            "sub4_shelter": {"name": "Sub-level 4 Shelter",
                             "desc": "Shelter.", "adjacent": []},
        },
        "entities": {"service_elevator": {
            "name": "Service Elevator", "kind": "vehicle",
            "state": {"transit": dict(transit)},
        }},
        "positions": {"service_elevator": "floor1_hall",
                      "The Stranger": "elevator_car"},
        "attire": {}, "overlays": {},
    }


def _make_chat(temp_db, persona_name=None):
    persona_id = None
    if persona_name:
        persona_id = temp_db.qi(
            "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
            (persona_name,
             json.dumps({"identity": {"name": persona_name}}), "{}"),
        )
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,persona_id,scenario,created) VALUES(?,?,?,?)",
        ("Test", persona_id, "", time.time()),
    )
    return chat_id, persona_id


def _make_ctx(temp_db, chat_id, persona_id, *, turn_idx, diff, cast=()):
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, turn_idx, "go", time.time()),
    )
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=turn_idx,
                      player_input="go", created=time.time()),
        cast=list(cast), input="go",
    )
    ctx.director_resolve = {
        "resolved_event": "Time passes.", "dialogue_log": [],
        "state_diff": diff,
    }
    return ctx


def _world_dump(temp_db, cid):
    """Everything the sweep + scene domains durably touch."""
    return {
        "world": {
            r["key"]: r["value"]
            for r in temp_db.q(
                "SELECT key, value FROM world WHERE chat_id=?", (cid,))
        },
        "scheduled_events": [
            dict(r) for r in temp_db.q(
                "SELECT * FROM scheduled_events WHERE chat_id=? "
                "ORDER BY event_id", (cid,))
        ],
        "world_conditions": [
            dict(r) for r in temp_db.q(
                "SELECT * FROM world_conditions WHERE chat_id=? "
                "ORDER BY condition_id", (cid,))
        ],
    }


def _run_turn(temp_db, ctx):
    prepared = prepare_scene_commit(ctx)
    result = commit_transit_sweep(ctx, 0, prepared=prepared)
    commit_scene(ctx, 0, prepared=prepared)
    return prepared, result


def test_end_to_end_schedule_fire_expire_and_persist(temp_db):
    """Golden path across two turns: turn 1 schedules the arrival from
    entity.state.transit; turn 2 fires it (position moved, docked, eta
    cleared, dock edge onto the new exterior, notice staged) and expires a
    due condition -- all persisted by commit_scene."""
    chat_id, _ = _make_chat(temp_db)
    temp_db.wset(chat_id, "scene", _elevator_scene(
        {"phase": "in_transit", "hatch": "closed",
         "destination_room": "sub4_shelter", "eta_seconds": 180}))
    temp_db.wset(chat_id, "simulation_clock",
                 {"elapsed_seconds": 1000.0, "display": "now"})
    temp_db.qi(
        "INSERT INTO world_conditions(condition_id,chat_id,subject_id,kind,"
        "started_at,expires_at,next_tick,payload,active) "
        "VALUES(?,?,?,?,?,?,?,?,?)",
        ("flare_burning", chat_id, "flare", "fire", 0.0, 1150.0, None,
         "{}", 1),
    )

    ctx1 = _make_ctx(temp_db, chat_id, None, turn_idx=1, diff={})
    _, r1 = _run_turn(temp_db, ctx1)
    assert r1["scheduled"] == 1 and r1["fired"] == 0 and r1["expired"] == 0
    row = temp_db.q("SELECT * FROM scheduled_events WHERE chat_id=?",
                    (chat_id,), one=True)
    assert row["status"] == "pending" and row["due_at"] == 1180.0

    ctx2 = _make_ctx(
        temp_db, chat_id, None, turn_idx=2,
        diff={"time": {"end_seconds": 1200.0, "display_advance": "later"}})
    prepared2, r2 = _run_turn(temp_db, ctx2)
    assert r2["fired"] == 1 and r2["scheduled"] == 0 and r2["expired"] == 1
    assert r2["notices"] and "sub4_shelter" in r2["notices"][0]

    sc = temp_db.wget(chat_id, "scene", {})
    assert sc["positions"]["service_elevator"] == "sub4_shelter"
    transit = sc["entities"]["service_elevator"]["state"]["transit"]
    assert transit["phase"] == "docked"
    assert "eta_seconds" not in transit
    assert spatial_rel(sc, "elevator_car", "sub4_shelter")["barrier"] \
        == "closed_door"
    assert temp_db.q(
        "SELECT status FROM scheduled_events WHERE chat_id=?",
        (chat_id,), one=True)["status"] == "fired"
    assert temp_db.q(
        "SELECT active FROM world_conditions WHERE chat_id=?",
        (chat_id,), one=True)["active"] == 0
    assert temp_db.wget(chat_id, "engine_notices", []) == r2["notices"]


def test_rerun_determinism_same_checkpoint_same_input_identical_world(temp_db):
    """Reroll safety for the whole refactor surface: restore the pre-turn
    checkpoint and re-run the identical turn -- the durable world state
    (world KV, scheduled_events, world_conditions) must come out
    byte-identical, including deterministic event ids/statuses."""
    chat_id, _ = _make_chat(temp_db)
    temp_db.wset(chat_id, "scene", _elevator_scene(
        {"phase": "in_transit", "hatch": "closed",
         "destination_room": "sub4_shelter", "eta_seconds": 180}))
    temp_db.wset(chat_id, "simulation_clock",
                 {"elapsed_seconds": 1000.0, "display": "now"})
    temp_db.qi(
        "INSERT INTO world_conditions(condition_id,chat_id,subject_id,kind,"
        "started_at,expires_at,next_tick,payload,active) "
        "VALUES(?,?,?,?,?,?,?,?,?)",
        ("flare_burning", chat_id, "flare", "fire", 0.0, 1150.0, None,
         "{}", 1),
    )
    # Seeded because checkpoint restore always (re)writes this key; without
    # it the post-restore world would differ by its mere existence.
    temp_db.wset(chat_id, "lore_cache", [])
    ctx1 = _make_ctx(temp_db, chat_id, None, turn_idx=1, diff={})
    _run_turn(temp_db, ctx1)

    ensure_checkpoint(chat_id, 2)
    diff2 = {"time": {"end_seconds": 1200.0, "display_advance": "later"}}
    ctx2 = _make_ctx(temp_db, chat_id, None, turn_idx=2, diff=diff2)
    _run_turn(temp_db, ctx2)
    first = _world_dump(temp_db, chat_id)

    restore_checkpoint(chat_id, 2)
    # Same turn row re-used on a rerun (reroll keeps the turn id).
    ctx2b = PipelineContext(
        chat=ctx2.chat, turn=ctx2.turn, cast=[], input="go")
    ctx2b.director_resolve = {
        "resolved_event": "Time passes.", "dialogue_log": [],
        "state_diff": json.loads(json.dumps(diff2)),
    }
    _run_turn(temp_db, ctx2b)
    second = _world_dump(temp_db, chat_id)

    assert first == second


def test_companion_carry_applies_to_the_prepared_scene(temp_db):
    """Pass (e) must be visible on the PREPARED scene: memory preparation
    reads it before the write transaction opens, so a carried companion's
    episodic memories this beat are located at the new position."""
    from character_schema import default_character_data

    chat_id, persona_id = _make_chat(temp_db, persona_name="Vera")
    scene = {
        "location": "Harbor", "time": "dawn",
        "rooms": {
            "dock": {"name": "Dock", "adjacent": []},
            "cabin": {"name": "Cabin", "adjacent": [],
                      "parent_entity": "the_boat"},
        },
        "entities": {"the_boat": {"name": "The Boat", "kind": "vehicle",
                                  "state": {}}},
        "positions": {"the_boat": "dock", "Vera": "dock", "Mara": "dock"},
        "attire": {}, "overlays": {},
    }
    temp_db.wset(chat_id, "scene", scene)
    cast = [{"id": 1, "sheet": json.dumps(default_character_data("Mara")),
             "cstate": "{}"}]
    ctx = _make_ctx(
        temp_db, chat_id, persona_id, turn_idx=1,
        diff={"positions": {"Vera": "cabin"}}, cast=cast)

    prepared = prepare_scene_commit(ctx)

    assert prepared["scene"]["positions"]["Vera"] == "cabin"
    assert prepared["scene"]["positions"]["Mara"] == "cabin", \
        "companion carry must be applied at preparation time"
