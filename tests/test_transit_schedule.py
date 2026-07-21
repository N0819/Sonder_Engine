"""Phase-2 transit tests: the scheduled_events revival (timed arrivals),
the condition-expiry sweep, the destroyed-mover guard, and the branch/
import id handling for scheduled events.

commit_transit_sweep is the deterministic commit-domain that (1) fires due
'transit_arrival' events for THIS frame only -- the frame id rides in each
event's payload because scheduled_events has no frame column while
simulation clocks are frame-scoped; (2) schedules new arrivals from
entity.state.transit.eta_seconds with deterministic event ids; (3)
deactivates expired world_conditions. It mutates the PREPARED scene before
commit_scene persists it, and checkpoint restore snapshots the whole
scheduled_events table, so a rerolled turn reproduces exact pending/fired
state.
"""

from __future__ import annotations

import json
import time

import pytest

from checkpoints import ensure_checkpoint, restore_checkpoint
from commit import commit_transit_sweep, prepare_scene_commit
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


def _make_ctx(temp_db, *, turn_idx=3, frame_id=None, director_resolve=None):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, turn_idx, "wait", time.time()),
    )
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=turn_idx,
                      player_input="wait", created=time.time(),
                      frame_id=frame_id),
        cast=[], input="wait",
    )
    ctx.director_resolve = director_resolve or {
        "resolved_event": "Time passes.", "dialogue_log": [],
        "state_diff": {},
    }
    return ctx


def _pending_rows(temp_db, cid):
    return temp_db.q(
        "SELECT * FROM scheduled_events WHERE chat_id=? ORDER BY due_at",
        (cid,),
    )


def test_eta_schedules_arrival_with_frame_scoped_due_at(temp_db):
    ctx = _make_ctx(temp_db)
    sc = _elevator_scene({"phase": "in_transit", "hatch": "closed",
                          "destination_room": "sub4_shelter",
                          "eta_seconds": 180})
    prepared = {"scene": sc,
                "clock": {"elapsed_seconds": 1000.0, "display": "later"}}

    result = commit_transit_sweep(ctx, 0, prepared=prepared)

    assert result["scheduled"] == 1 and result["fired"] == 0
    rows = _pending_rows(temp_db, ctx.chat.id)
    assert len(rows) == 1
    row = rows[0]
    assert row["status"] == "pending"
    assert row["kind"] == "transit_arrival"
    assert row["due_at"] == 1180.0  # this frame's clock + eta
    payload = json.loads(row["payload"])
    assert payload == {"entity_id": "service_elevator",
                       "destination_room": "sub4_shelter", "frame_id": None}

    # Re-sweeping before due neither fires nor double-schedules.
    result2 = commit_transit_sweep(ctx, 0, prepared=prepared)
    assert result2["scheduled"] == 0 and result2["fired"] == 0
    assert len(_pending_rows(temp_db, ctx.chat.id)) == 1


def test_due_sweep_fires_arrival_and_stages_notice(temp_db):
    ctx = _make_ctx(temp_db)
    cid = ctx.chat.id
    sc = _elevator_scene({"phase": "in_transit", "hatch": "closed",
                          "destination_room": "sub4_shelter",
                          "eta_seconds": 180})
    commit_transit_sweep(
        ctx, 0, prepared={"scene": sc,
                          "clock": {"elapsed_seconds": 1000.0,
                                    "display": "later"}})

    # Next beat: the clock has passed due_at -> the arrival completes
    # mechanically: position moved, phase docked, derived doorway onto the
    # NEW exterior, a notice staged for the next director turn.
    result = commit_transit_sweep(
        ctx, 0, prepared={"scene": sc,
                          "clock": {"elapsed_seconds": 1200.0,
                                    "display": "later"}})

    assert result["fired"] == 1
    assert sc["positions"]["service_elevator"] == "sub4_shelter"
    transit = sc["entities"]["service_elevator"]["state"]["transit"]
    assert transit["phase"] == "docked"
    assert "eta_seconds" not in transit
    rel = spatial_rel(sc, "elevator_car", "sub4_shelter")
    assert rel["barrier"] == "closed_door"  # hatch stays as encoded
    # Occupant rode along untouched.
    assert sc["positions"]["The Stranger"] == "elevator_car"

    rows = _pending_rows(temp_db, cid)
    assert [r["status"] for r in rows] == ["fired"]
    notices = temp_db.wget(cid, "engine_notices", [])
    assert notices and "sub4_shelter" in notices[0]

    # The following sweep with nothing due overwrites the notices -- they
    # self-expire after exactly one beat.
    commit_transit_sweep(
        ctx, 0, prepared={"scene": sc,
                          "clock": {"elapsed_seconds": 1300.0,
                                    "display": "later"}})
    assert temp_db.wget(cid, "engine_notices", []) == []


def test_sweep_is_frame_scoped(temp_db):
    """An event minted for another frame must never fire against this
    frame's clock, no matter how overdue it looks."""
    ctx = _make_ctx(temp_db, frame_id=None)
    cid = ctx.chat.id
    temp_db.qi(
        "INSERT INTO scheduled_events(event_id,chat_id,due_at,kind,"
        "location_id,payload,seed,status) VALUES(?,?,?,?,?,?,?,?)",
        ("evt_other_frame", cid, 5.0, "transit_arrival", "floor1_hall",
         json.dumps({"entity_id": "service_elevator",
                     "destination_room": "sub4_shelter", "frame_id": 999}),
         "seed", "pending"),
    )
    sc = _elevator_scene({"phase": "in_transit", "hatch": "closed"})

    result = commit_transit_sweep(
        ctx, 0, prepared={"scene": sc,
                          "clock": {"elapsed_seconds": 99999.0,
                                    "display": "much later"}})

    assert result["fired"] == 0
    assert _pending_rows(temp_db, cid)[0]["status"] == "pending"
    assert sc["positions"]["service_elevator"] == "floor1_hall"


def test_manually_docked_entity_cancels_its_pending_event(temp_db):
    """The director docked the elevator by hand before the timer ran out:
    the event is moot and must be cancelled, not fired over the top."""
    ctx = _make_ctx(temp_db)
    sc = _elevator_scene({"phase": "in_transit", "hatch": "closed",
                          "destination_room": "sub4_shelter",
                          "eta_seconds": 60})
    commit_transit_sweep(
        ctx, 0, prepared={"scene": sc,
                          "clock": {"elapsed_seconds": 100.0,
                                    "display": "now"}})
    sc["entities"]["service_elevator"]["state"]["transit"] = {
        "phase": "docked", "hatch": "open"}
    sc["positions"]["service_elevator"] = "floor1_hall"

    result = commit_transit_sweep(
        ctx, 0, prepared={"scene": sc,
                          "clock": {"elapsed_seconds": 500.0,
                                    "display": "later"}})

    assert result["fired"] == 0
    assert _pending_rows(temp_db, ctx.chat.id)[0]["status"] == "cancelled"
    assert sc["positions"]["service_elevator"] == "floor1_hall"


def test_checkpoint_restore_reproduces_pending_state(temp_db):
    """Reroll safety: restoring the pre-turn checkpoint returns the
    scheduled row to 'pending' exactly, so a rerun's sweep reproduces the
    original firing instead of finding it already consumed."""
    ctx = _make_ctx(temp_db)
    cid = ctx.chat.id
    sc = _elevator_scene({"phase": "in_transit", "hatch": "closed",
                          "destination_room": "sub4_shelter",
                          "eta_seconds": 60})
    commit_transit_sweep(
        ctx, 0, prepared={"scene": sc,
                          "clock": {"elapsed_seconds": 100.0,
                                    "display": "now"}})
    assert _pending_rows(temp_db, cid)[0]["status"] == "pending"

    ensure_checkpoint(cid, ctx.turn.idx)

    commit_transit_sweep(
        ctx, 0, prepared={"scene": sc,
                          "clock": {"elapsed_seconds": 500.0,
                                    "display": "later"}})
    assert _pending_rows(temp_db, cid)[0]["status"] == "fired"

    restore_checkpoint(cid, ctx.turn.idx)
    assert _pending_rows(temp_db, cid)[0]["status"] == "pending"


def test_condition_expiry_sweep(temp_db):
    """expires_at <= this frame's clock deactivates a condition; unexpired
    and open-ended conditions are untouched -- 'the fire burns out' becomes
    encodable as expiry rather than neglect."""
    ctx = _make_ctx(temp_db)
    cid = ctx.chat.id
    for cond_id, expires in (("burning_out", 50.0), ("still_burning", 5000.0),
                             ("open_ended", None)):
        temp_db.qi(
            "INSERT INTO world_conditions(condition_id,chat_id,subject_id,"
            "kind,started_at,expires_at,next_tick,payload,active) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (cond_id, cid, "warehouse", "fire", 0.0, expires, None, "{}", 1),
        )
    sc = _elevator_scene({"phase": "docked", "hatch": "open"})

    result = commit_transit_sweep(
        ctx, 0, prepared={"scene": sc,
                          "clock": {"elapsed_seconds": 100.0,
                                    "display": "now"}})

    assert result["expired"] == 1
    actives = {
        r["condition_id"]: r["active"]
        for r in temp_db.q(
            "SELECT condition_id, active FROM world_conditions WHERE chat_id=?",
            (cid,))
    }
    assert actives == {"burning_out": 0, "still_burning": 1, "open_ended": 1}


def test_destroyed_occupied_mover_is_refused(temp_db):
    """Removing an entity whose interior rooms still hold occupants without
    repositioning them fails commit preparation -- the turn rolls back
    rather than stranding people inside a container that no longer exists."""
    ctx = _make_ctx(temp_db, director_resolve={
        "resolved_event": "The crate is smashed to splinters.",
        "dialogue_log": [],
        "state_diff": {"remove_entities": ["the_crate"]},
    })
    temp_db.wset(ctx.chat.id, "scene", {
        "rooms": {
            "crate_interior": {"name": "Inside the Crate", "desc": "Dark.",
                               "adjacent": [], "parent_entity": "the_crate"},
            "yard": {"name": "Yard", "desc": "Open.", "adjacent": []},
        },
        "entities": {"the_crate": {"name": "The Crate", "kind": "container",
                                   "state": {}}},
        "positions": {"the_crate": "yard", "Mara": "crate_interior"},
    })

    with pytest.raises(RuntimeError, match="strand"):
        prepare_scene_commit(ctx)

    # Repositioning the occupant in the same beat makes it legal.
    ctx.director_resolve["state_diff"]["positions"] = {"Mara": "yard"}
    prepared = prepare_scene_commit(ctx)
    assert "the_crate" not in prepared["scene"]["entities"]
    assert prepared["scene"]["positions"]["Mara"] == "yard"


def test_branch_clone_mints_fresh_event_ids_and_remaps_frames():
    """scheduled_events rows survive branch/clone with FRESH event ids
    (global TEXT PK -- collisions would silently drop rows) and payload
    frame ids remapped to the clone's own frames."""
    from app import _build_world_id_remap, _remap_scheduled_event_frames

    blob = {"scheduled_events": [{
        "event_id": "evt_original", "due_at": 100.0,
        "kind": "transit_arrival", "location_id": "floor1_hall",
        "payload": json.dumps({"entity_id": "service_elevator",
                               "destination_room": "sub4_shelter",
                               "frame_id": 7}),
        "seed": "s", "status": "pending",
    }]}
    remap = _build_world_id_remap(blob)
    assert "evt_original" in remap
    assert remap["evt_original"] != "evt_original"

    rows = blob["scheduled_events"]
    _remap_scheduled_event_frames(rows, {7: 42})
    assert json.loads(rows[0]["payload"])["frame_id"] == 42
    # An uncloned frame collapses to present rather than dangling.
    rows[0]["payload"] = json.dumps({"frame_id": 9, "entity_id": "x"})
    _remap_scheduled_event_frames(rows, {7: 42})
    assert json.loads(rows[0]["payload"])["frame_id"] is None
