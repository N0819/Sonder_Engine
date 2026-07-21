"""Single-book destruction (movement/space Phase 2, item 4).

The Director declares destruction in state_diff.destruction (the revived
DestructionEffect shape); commit realizes it deterministically: the
target's ONE book + its registered rooms are retired atomically (retire-
not-delete), the live rooms drop through the ordinary diff machinery, a
stranded occupant fails the whole commit -> rollback, engine notices are
staged, and awareness propagates only via latency-gated news_arrival
scheduled events the mechanics sweep fires frame-gated against the sim
clock -- with stable ids and whole-table checkpointing, so reruns
reproduce the exact pending/fired state.
"""

from __future__ import annotations

import json
import time

import pytest

import commit
from checkpoints import ensure_checkpoint, restore_checkpoint
from pipeline_context import ChatData, PipelineContext, TurnData


def _ship_scene():
    return {
        "location": "Harbor", "time": "dusk",
        "rooms": {
            "harbor": {"name": "Harbor", "adjacent": []},
            "deck_3": {"name": "Deck 3", "parent_entity": "ship_a",
                       "adjacent": []},
            "engine_room": {"name": "Engine Room", "parent_entity": "ship_a",
                            "adjacent": []},
        },
        "positions": {"ship_a": "harbor", "The Stranger": "deck_3"},
        "entities": {
            "ship_a": {"name": "The Aurora", "kind": "vehicle",
                       "interior_rooms": ["deck_3", "engine_room"],
                       "state": {}},
        },
        "attire": {}, "overlays": {},
    }


def _make_ctx(temp_db, scene, diff, *, turn_idx=1):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    canon = temp_db.qi(
        "INSERT INTO lorebooks(name,chat_id,book_type) VALUES(?,?,?)",
        ("Canon", chat_id, "general"),
    )
    temp_db.qi("UPDATE chats SET lorebook_id=? WHERE id=?", (canon, chat_id))
    ship_book = temp_db.qi(
        "INSERT INTO lorebooks(name,chat_id,book_type,anchor_entity_id,"
        "parent_id) VALUES(?,?,?,?,?)",
        ("The Aurora", chat_id, "vehicle", "ship_a", canon),
    )
    temp_db.wset(chat_id, "scene", scene)
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, turn_idx, "x", time.time()),
    )
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=canon, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=turn_idx,
                      player_input="x", created=time.time()),
        cast=[], input="x",
    )
    ctx.director_resolve = {
        "resolved_event": "beat", "dialogue_log": [], "state_diff": diff,
    }
    return ctx, {"canon": canon, "ship_book": ship_book}


def _commit_beat(ctx):
    prepared = commit.prepare_scene_commit(ctx)
    sweep = commit.commit_transit_sweep(ctx, 0, prepared=prepared)
    commit.commit_scene(ctx, 0, prepared=prepared)
    return prepared, sweep


def _destruction_diff(news=()):
    return {
        # Occupant repositioned in the same beat -- the legal case.
        "positions": {"The Stranger": "harbor"},
        "destruction": {
            "target_id": "ship_a", "scale": "vehicle", "kind": "sunk",
            "news": list(news),
        },
    }


def test_destruction_retires_book_and_rooms_and_drops_live_scene(temp_db):
    ctx, ids = _make_ctx(temp_db, _ship_scene(), {})
    _commit_beat(ctx)  # registers deck_3/engine_room under the ship book

    ctx.director_resolve = {
        "resolved_event": "The Aurora goes down.", "dialogue_log": [],
        "state_diff": _destruction_diff(
            news=[{"audience": "Port Authority", "latency_seconds": 600,
                   "summary": "The Aurora sank in the harbor"}]),
    }
    prepared, _ = _commit_beat(ctx)
    cid = ctx.chat.id

    # Live scene: entity + interior rooms gone, occupant safe ashore.
    sc = temp_db.wget(cid, "scene", {})
    assert "ship_a" not in sc["entities"]
    assert "deck_3" not in sc["rooms"] and "engine_room" not in sc["rooms"]
    assert sc["positions"]["The Stranger"] == "harbor"

    # Book + registered rooms retired (never deleted) with this turn's id.
    book = temp_db.q("SELECT retired_turn_id FROM lorebooks WHERE id=?",
                     (ids["ship_book"],), one=True)
    assert book["retired_turn_id"] == ctx.turn.id
    rows = temp_db.q(
        "SELECT room_uid, retired_turn_id FROM room_registry "
        "WHERE chat_id=? AND owning_book_id=? ORDER BY room_uid",
        (cid, ids["ship_book"]))
    assert [(r["room_uid"], r["retired_turn_id"]) for r in rows] == [
        ("deck_3", ctx.turn.id), ("engine_room", ctx.turn.id)]

    # The book's lore remains retrievable history (rows intact).
    assert temp_db.q("SELECT id FROM lorebooks WHERE id=?",
                     (ids["ship_book"],), one=True) is not None

    # Engine notice staged for the next director beat.
    notices = temp_db.wget(cid, "engine_notices", [])
    assert any("sunk" in n for n in notices)

    # One news_arrival per audience, latency-gated on the sim clock.
    ev = temp_db.q(
        "SELECT * FROM scheduled_events WHERE chat_id=? AND "
        "kind='news_arrival'", (cid,), one=True)
    assert ev is not None and ev["status"] == "pending"
    assert ev["due_at"] == 600.0  # clock 0 + latency
    payload = json.loads(ev["payload"])
    assert payload["audience"] == "Port Authority"
    assert payload["provenance"] == "told"
    assert payload["frame_id"] is None


def test_destruction_stranding_occupant_fails_the_commit(temp_db):
    ctx, ids = _make_ctx(temp_db, _ship_scene(), {})
    _commit_beat(ctx)

    diff = _destruction_diff()
    del diff["positions"]  # nobody repositioned The Stranger
    ctx.director_resolve = {
        "resolved_event": "The Aurora goes down.", "dialogue_log": [],
        "state_diff": diff,
    }
    with pytest.raises(RuntimeError, match="strand"):
        commit.prepare_scene_commit(ctx)

    # Nothing was retired -- preparation failed before any durable write.
    assert temp_db.q("SELECT retired_turn_id FROM lorebooks WHERE id=?",
                     (ids["ship_book"],), one=True)["retired_turn_id"] is None
    assert temp_db.q(
        "SELECT COUNT(*) c FROM room_registry WHERE chat_id=? AND "
        "retired_turn_id IS NOT NULL", (ctx.chat.id,), one=True)["c"] == 0


def test_invalid_scale_is_dropped_with_warning_not_guessed(temp_db):
    ctx, ids = _make_ctx(temp_db, _ship_scene(), {})
    _commit_beat(ctx)
    ctx.director_resolve = {
        "resolved_event": "beat", "dialogue_log": [],
        "state_diff": {"destruction": {"target_id": "ship_a",
                                       "scale": "city", "kind": "razed"}},
    }
    prepared = commit.prepare_scene_commit(ctx)
    assert prepared["destruction"] is None
    assert any("scale" in w for w in ctx.warnings)
    assert "deck_3" in prepared["scene"]["rooms"], "nothing was destroyed"


def test_news_arrival_fires_frame_gated_when_due(temp_db):
    ctx, ids = _make_ctx(temp_db, _ship_scene(), {})
    _commit_beat(ctx)
    ctx.director_resolve = {
        "resolved_event": "Down she goes.", "dialogue_log": [],
        "state_diff": _destruction_diff(
            news=[{"audience": "Port Authority", "latency_seconds": 600,
                   "summary": "The Aurora sank in the harbor"},
                  {"audience": "the capital", "latency_seconds": 86400,
                   "summary": "A ship was lost at Harbor"}]),
    }
    _commit_beat(ctx)
    cid = ctx.chat.id
    assert temp_db.q(
        "SELECT COUNT(*) c FROM scheduled_events WHERE chat_id=? AND "
        "kind='news_arrival'", (cid,), one=True)["c"] == 2

    # Not yet due: nothing fires.
    ctx.director_resolve = {
        "resolved_event": "Waiting.", "dialogue_log": [],
        "state_diff": {"time": {"end_seconds": 300.0,
                                "display_advance": "later"}},
    }
    _, sweep = _commit_beat(ctx)
    assert sweep["news_fired"] == 0

    # The first scope's latency elapses: exactly one fires, with a
    # told/heard-provenance notice; the farther scope stays pending.
    ctx.director_resolve = {
        "resolved_event": "Later.", "dialogue_log": [],
        "state_diff": {"time": {"end_seconds": 700.0,
                                "display_advance": "evening"}},
    }
    _, sweep = _commit_beat(ctx)
    assert sweep["news_fired"] == 1
    assert any("Port Authority" in n and "told/heard" in n
               for n in sweep["notices"])
    statuses = {
        json.loads(r["payload"])["audience"]: r["status"]
        for r in temp_db.q(
            "SELECT * FROM scheduled_events WHERE chat_id=? AND "
            "kind='news_arrival'", (cid,))
    }
    assert statuses == {"Port Authority": "fired", "the capital": "pending"}


def test_news_event_is_frame_scoped_like_transit(temp_db):
    """An event minted for another frame must never fire against this
    frame's clock, however overdue -- same gate as transit_arrival."""
    ctx, _ = _make_ctx(temp_db, _ship_scene(), {})
    cid = ctx.chat.id
    temp_db.qi(
        "INSERT INTO scheduled_events(event_id,chat_id,due_at,kind,"
        "location_id,payload,seed,status) VALUES(?,?,?,?,?,?,?,?)",
        ("evt_news_other_frame", cid, 5.0, "news_arrival", None,
         json.dumps({"frame_id": 999, "audience": "someone",
                     "summary": "old news"}),
         "seed", "pending"),
    )
    ctx.director_resolve = {
        "resolved_event": "beat", "dialogue_log": [],
        "state_diff": {"time": {"end_seconds": 99999.0,
                                "display_advance": "much later"}},
    }
    _, sweep = _commit_beat(ctx)
    assert sweep["news_fired"] == 0
    assert temp_db.q("SELECT status FROM scheduled_events WHERE chat_id=?",
                     (cid,), one=True)["status"] == "pending"


def test_destruction_rerun_reproduces_identical_state(temp_db):
    """Checkpoint-whole reproducibility: restore + rerun of the
    destruction turn yields identical books, registry, events, notices."""
    ctx, ids = _make_ctx(temp_db, _ship_scene(), {})
    _commit_beat(ctx)
    temp_db.wset(ctx.chat.id, "lore_cache", [])
    cid = ctx.chat.id
    ensure_checkpoint(cid, 2)

    diff = _destruction_diff(
        news=[{"audience": "Port Authority", "latency_seconds": 600,
               "summary": "The Aurora sank"}])
    turn2 = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, 2, "sink it", time.time()),
    )
    ctx2 = PipelineContext(
        chat=ctx.chat,
        turn=TurnData(id=turn2, chat_id=cid, idx=2, player_input="sink it",
                      created=time.time()),
        cast=[], input="sink it",
    )
    ctx2.director_resolve = {
        "resolved_event": "Down.", "dialogue_log": [],
        "state_diff": json.loads(json.dumps(diff)),
    }
    _commit_beat(ctx2)

    def dump():
        return {
            "books": [dict(r) for r in temp_db.q(
                "SELECT id, retired_turn_id FROM lorebooks WHERE chat_id=? "
                "ORDER BY id", (cid,))],
            "registry": [dict(r) for r in temp_db.q(
                "SELECT * FROM room_registry WHERE chat_id=? "
                "ORDER BY room_uid", (cid,))],
            "events": [dict(r) for r in temp_db.q(
                "SELECT * FROM scheduled_events WHERE chat_id=? "
                "ORDER BY event_id", (cid,))],
            "world": {r["key"]: r["value"] for r in temp_db.q(
                "SELECT key, value FROM world WHERE chat_id=?", (cid,))},
        }

    first = dump()
    restore_checkpoint(cid, 2)
    assert temp_db.q("SELECT retired_turn_id FROM lorebooks WHERE id=?",
                     (ids["ship_book"],), one=True)["retired_turn_id"] \
        is None, "restore must un-retire the book"
    ctx2b = PipelineContext(
        chat=ctx.chat, turn=ctx2.turn, cast=[], input="sink it")
    ctx2b.director_resolve = {
        "resolved_event": "Down.", "dialogue_log": [],
        "state_diff": json.loads(json.dumps(diff)),
    }
    _commit_beat(ctx2b)
    assert dump() == first
