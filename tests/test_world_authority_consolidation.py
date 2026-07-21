"""Phase 3a: single-source-of-truth invariants for the physical world.

The authority model after consolidation:

- the frame-scoped `world.scene` blob is the sole runtime authority for
  LIVE rooms, adjacency, positions, and entity state (every spatial
  reader keeps reading it, unchanged);
- `room_registry` is the sole cross-frame ledger of room identity /
  existence-over-time / retirement, maintained as a deterministic
  projection of EVERY scene write (commit_scene and, now, the manual
  world editor);
- `world_entities` is a derived projection of the scene commit, built
  from the same post-dedup/post-destruction diff the blob was merged
  from -- never from the raw step diff, which dedup renames and
  destruction consequences were folded into a copy of;
- `world_placements` is decommissioned dead data (no runtime writer or
  reader; kept only so old snapshots/exports restore).

These tests pin the invariants that make the model actually hold -- each
one failed against the pre-consolidation code.
"""

from __future__ import annotations

import json
import time

import commit
from pipeline_context import ChatData, PipelineContext, TurnData


def _make_chat(db, scene, *, books=()):
    chat_id = db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Story", "", time.time()),
    )
    canon = db.qi(
        "INSERT INTO lorebooks(name,chat_id,book_type) VALUES(?,?,?)",
        ("Canon", chat_id, "general"),
    )
    db.qi("UPDATE chats SET lorebook_id=? WHERE id=?", (canon, chat_id))
    ids = {"chat_id": chat_id, "canon": canon}
    for name, anchor in books:
        ids[anchor] = db.qi(
            "INSERT INTO lorebooks(name,chat_id,book_type,anchor_entity_id,"
            "parent_id) VALUES(?,?,?,?,?)",
            (name, chat_id, "vehicle", anchor, canon),
        )
    if scene is not None:
        db.wset(chat_id, "scene", scene)
    return ids


def _make_ctx(db, ids, diff, *, turn_idx=1):
    turn_id = db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (ids["chat_id"], turn_idx, "do", time.time()),
    )
    ctx = PipelineContext(
        chat=ChatData(id=ids["chat_id"], name="Story", persona_id=None,
                      lorebook_id=ids["canon"], scenario="",
                      created=time.time()),
        turn=TurnData(id=turn_id, chat_id=ids["chat_id"], idx=turn_idx,
                      player_input="do", created=time.time()),
        cast=[], input="do",
    )
    ctx.director_resolve = {
        "resolved_event": "beat", "dialogue_log": [], "state_diff": diff,
    }
    return ctx


def _commit_beat(ctx):
    prepared = commit.prepare_scene_commit(ctx)
    commit.commit_transit_sweep(ctx, 0, prepared=prepared)
    commit.commit_scene(ctx, 0, prepared=prepared)
    commit.commit_world_entities(ctx, 0, prepared=prepared)
    return prepared


def _two_ship_scene():
    return {
        "location": "Harbor", "time": "dusk",
        "rooms": {
            "harbor": {"name": "Harbor", "adjacent": []},
            "deck_3": {"name": "Deck 3", "parent_entity": "ship_a",
                       "adjacent": []},
        },
        "positions": {"ship_a": "harbor", "The Stranger": "harbor"},
        "entities": {
            "ship_a": {"name": "The Aurora", "kind": "vehicle",
                       "interior_rooms": ["deck_3"], "state": {}},
        },
        "overlays": {}, "attire": {},
    }


def test_entity_projection_reflects_dedup_room_renames(temp_db):
    """A second ship minting a colliding 'deck_3' is rekeyed by
    dedup_minted_rooms; the world_entities projection must carry the SAME
    rekeyed interior room as the scene blob. Pre-consolidation it was built
    from the raw step diff and kept the stale colliding key."""
    ids = _make_chat(temp_db, _two_ship_scene(),
                     books=[("The Aurora", "ship_a")])
    ctx = _make_ctx(temp_db, ids, {
        "rooms": {"deck_3": {"name": "Deck 3", "parent_entity": "ship_b",
                             "adjacent": []}},
        "positions": {"ship_b": "harbor"},
        "entities": {"ship_b": {"name": "The Boreas", "kind": "vehicle",
                                "interior_rooms": ["deck_3"], "state": {}}},
    })
    _commit_beat(ctx)
    cid = ids["chat_id"]

    sc = temp_db.wget(cid, "scene", {})
    boreas_rooms = [rid for rid, r in sc["rooms"].items()
                    if isinstance(r, dict)
                    and r.get("parent_entity") == "ship_b"]
    assert boreas_rooms == ["ship_b_deck_3"]
    # Aurora's own deck untouched.
    assert sc["rooms"]["deck_3"]["parent_entity"] == "ship_a"

    row = temp_db.q(
        "SELECT payload FROM world_entities WHERE chat_id=? AND "
        "entity_id='ship_b'", (cid,), one=True)
    payload = json.loads(row["payload"])
    assert payload["interior_rooms"] == ["ship_b_deck_3"], (
        "world_entities projection disagrees with the scene blob about the "
        "rekeyed interior room")


def test_destruction_removes_entity_projection_with_the_blob(temp_db):
    """Destruction folds remove_entities into the prepared diff copy only;
    the projection must follow the blob. Pre-consolidation the destroyed
    vehicle's world_entities row silently survived its own sinking."""
    ids = _make_chat(temp_db, _two_ship_scene(),
                     books=[("The Aurora", "ship_a")])
    # Seed the projection through the ordinary diff path (the projection
    # accumulates from diffs; a pre-seeded blob alone has no diff to echo).
    _commit_beat(_make_ctx(temp_db, ids, {
        "entities": {"ship_a": {"name": "The Aurora", "kind": "vehicle",
                                "interior_rooms": ["deck_3"], "state": {}}},
    }))
    cid = ids["chat_id"]
    assert temp_db.q("SELECT 1 FROM world_entities WHERE chat_id=? AND "
                     "entity_id='ship_a'", (cid,), one=True)

    ctx = _make_ctx(temp_db, ids, {
        "destruction": {"target_id": "ship_a", "scale": "vehicle",
                        "kind": "sunk", "news": []},
    }, turn_idx=2)
    _commit_beat(ctx)

    sc = temp_db.wget(cid, "scene", {})
    assert "ship_a" not in sc["entities"]
    assert temp_db.q("SELECT 1 FROM world_entities WHERE chat_id=? AND "
                     "entity_id='ship_a'", (cid,), one=True) is None


def test_legacy_direct_call_still_reads_the_step_diff(temp_db):
    """commit_world_entities without a prepared scene commit (direct
    callers, older tests) keeps its historical raw-diff behavior."""
    ids = _make_chat(temp_db, _two_ship_scene())
    ctx = _make_ctx(temp_db, ids, {
        "entities": {"crate": {"name": "Crate", "kind": "object"}},
    })
    commit.commit_world_entities(ctx, 0)
    assert temp_db.q("SELECT 1 FROM world_entities WHERE chat_id=? AND "
                     "entity_id='crate'", (ids["chat_id"],), one=True)


def test_world_put_syncs_room_registry_with_manual_scene_edit(temp_db):
    """The manual world editor is a scene writer: a hand-added room must
    register and a hand-removed room must retire, exactly like a committed
    removal. Pre-consolidation world_put bypassed the registry entirely."""
    import app
    ids = _make_chat(temp_db, _two_ship_scene(),
                     books=[("The Aurora", "ship_a")])
    ctx = _make_ctx(temp_db, ids, {})
    _commit_beat(ctx)                             # registers harbor + deck_3
    cid = ids["chat_id"]

    world = {w["key"]: json.loads(w["value"]) for w in temp_db.q(
        "SELECT * FROM world WHERE chat_id=?", (cid,))}
    sc = world["scene"]
    sc["rooms"]["lighthouse"] = {"name": "Lighthouse", "adjacent": []}
    del sc["rooms"]["deck_3"]
    sc["entities"]["ship_a"]["interior_rooms"] = []
    app.world_put(cid, world)

    rows = {r["room_uid"]: dict(r) for r in temp_db.q(
        "SELECT * FROM room_registry WHERE chat_id=?", (cid,))}
    assert rows["lighthouse"]["retired_turn_id"] is None
    assert rows["lighthouse"]["owning_book_id"] == ids["canon"]
    assert rows["deck_3"]["retired_turn_id"] == ctx.turn.id
    assert rows["harbor"]["retired_turn_id"] is None


def test_world_put_without_turns_registers_but_never_retires(temp_db):
    """With no turns yet there is no meaningful retirement stamp: the sync
    still registers new rooms but leaves the retire pass alone (a NULL
    stamp would silently read as 'live')."""
    import app
    ids = _make_chat(temp_db, None)
    cid = ids["chat_id"]
    app.world_put(cid, {"scene": {
        "location": "Somewhere", "time": "now",
        "rooms": {"clearing": {"name": "Clearing", "adjacent": []}},
        "positions": {}, "entities": {}, "overlays": {}, "attire": {},
    }})
    rows = {r["room_uid"]: dict(r) for r in temp_db.q(
        "SELECT * FROM room_registry WHERE chat_id=?", (cid,))}
    assert rows["clearing"]["retired_turn_id"] is None
    assert rows["clearing"]["created_turn_id"] is None


def test_world_placements_have_no_runtime_writer(temp_db):
    """Decommission guard: a full commit beat must leave world_placements
    empty -- the table is import/restore compatibility only. If a runtime
    writer reappears, the authority model has forked and this must fail."""
    ids = _make_chat(temp_db, _two_ship_scene(),
                     books=[("The Aurora", "ship_a")])
    _commit_beat(_make_ctx(temp_db, ids, {
        "entities": {"crate": {"name": "Crate", "kind": "object"}},
        "positions": {"crate": "harbor"},
    }))
    assert temp_db.q("SELECT * FROM world_placements WHERE chat_id=?",
                     (ids["chat_id"],)) == []
