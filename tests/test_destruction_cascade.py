"""Multi-book destructive cascades (movement/space Phase 3b).

The Director declares the causal destructive event and its ROOT target
(scale 'region' in state_diff.destruction); commit enumerates the doomed
cascade deterministically from the lorebook tree -- parent_id descendants
plus currently_within members physically positioned inside -- and, inside
the one outer transaction, retires every cascaded book and registered
room (retire-not-delete), folds every live room/entity removal into the
committing frame's scene through the ordinary diff machinery, and fails
the WHOLE commit if any doomed-room occupant is neither repositioned nor
departed. Awareness propagates only through latency-gated news_arrival
events, latency declared by the Director or derived from the audience's
hop distance in the book graph (near regions hear sooner).
"""

from __future__ import annotations

import json
import time

import pytest

import commit
from checkpoints import ensure_checkpoint, restore_checkpoint
from mechanics import (NEWS_HOP_LATENCY_SECONDS,
                       NEWS_UNREACHABLE_LATENCY_SECONDS)
from pipeline_context import ChatData, PipelineContext, TurnData


def _district_scene():
    return {
        "location": "Harbor District", "time": "dusk",
        "rooms": {
            "docks": {"name": "The Docks", "adjacent": []},
            "market": {"name": "Fish Market", "adjacent": []},
            "deck_3": {"name": "Deck 3", "parent_entity": "ship_a",
                       "adjacent": []},
        },
        "positions": {"ship_a": "docks", "The Stranger": "deck_3",
                      "Mira": "market"},
        "entities": {
            "ship_a": {"name": "The Aurora", "kind": "vehicle",
                       "interior_rooms": ["deck_3"], "state": {}},
        },
        "attire": {}, "overlays": {},
    }


def _make_world(temp_db):
    """One chat with a book tree spanning near and far places:

        canon
        |- region_book  "Harbor District" (scope harbor_district)
        |   `- records_book "Dockside Records"      (lore child, no rooms)
        |- ship_book    "The Aurora"  (anchor ship_a, within region_book,
        |                              ship_a physically at the docks)
        |- stale_book   "The Petrel"  (anchor ship_b, within region_book,
        |                              but ship_b nowhere in this scene)
        `- kingdom_book "The Inland Kingdom"        (2 hops from region)
            `- capital_book "The Capital"           (3 hops from region)
    """
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    canon = temp_db.qi(
        "INSERT INTO lorebooks(name,chat_id,book_type) VALUES(?,?,?)",
        ("Canon", chat_id, "general"),
    )
    temp_db.qi("UPDATE chats SET lorebook_id=? WHERE id=?", (canon, chat_id))

    def book(name, **cols):
        cols = {"chat_id": chat_id, "book_type": "general", **cols}
        keys = ",".join(["name", *cols])
        holes = ",".join("?" * (1 + len(cols)))
        return temp_db.qi(
            f"INSERT INTO lorebooks({keys}) VALUES({holes})",
            (name, *cols.values()),
        )

    ids = {
        "chat": chat_id, "canon": canon,
        "region": book("Harbor District", book_type="location",
                       scope_location_id="harbor_district", parent_id=canon),
        "kingdom": book("The Inland Kingdom", parent_id=canon),
    }
    ids["records"] = book("Dockside Records", parent_id=ids["region"])
    ids["capital"] = book("The Capital", parent_id=ids["kingdom"])
    ids["ship"] = book("The Aurora", book_type="vehicle",
                       anchor_entity_id="ship_a", parent_id=canon)
    ids["stale"] = book("The Petrel", book_type="vehicle",
                        anchor_entity_id="ship_b", parent_id=canon)
    return ids


def _make_ctx(temp_db, ids, diff, *, turn_idx=1):
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (ids["chat"], turn_idx, "x", time.time()),
    )
    ctx = PipelineContext(
        chat=ChatData(id=ids["chat"], name="Test", persona_id=None,
                      lorebook_id=ids["canon"], scenario="",
                      created=time.time()),
        turn=TurnData(id=turn_id, chat_id=ids["chat"], idx=turn_idx,
                      player_input="x", created=time.time()),
        cast=[], input="x",
    )
    ctx.director_resolve = {
        "resolved_event": "beat", "dialogue_log": [], "state_diff": diff,
    }
    return ctx


def _commit_beat(ctx):
    prepared = commit.prepare_scene_commit(ctx)
    sweep = commit.commit_transit_sweep(ctx, 0, prepared=prepared)
    commit.commit_scene(ctx, 0, prepared=prepared)
    return prepared, sweep


def _seed(temp_db):
    """Build the world, commit the registration beat, then link both
    ships currently_within the district (after the commit -- the
    anchored-book sync would otherwise rewrite the links from positions,
    which is exactly what a live game does once the ships dock)."""
    ids = _make_world(temp_db)
    temp_db.wset(ids["chat"], "scene", _district_scene())
    _commit_beat(_make_ctx(temp_db, ids, {}))
    for source in ("ship", "stale"):
        temp_db.qi(
            "INSERT INTO lorebook_links(source_book_id,target_book_id,"
            "relation_type,created) VALUES(?,?,?,?)",
            (ids[source], ids["region"], "currently_within", time.time()),
        )
    return ids


def _razing_diff(news=()):
    return {
        # Both legal exits, one of each: The Stranger repositions to a
        # room minted this same beat; Mira departs the story.
        "positions": {"The Stranger": "headland"},
        "rooms": {"headland": {"name": "The Headland", "adjacent": []}},
        "cast_changes": [{"who": "Mira", "status": "dormant",
                          "reason": "fled inland"}],
        "destruction": {
            "target_id": "harbor_district", "scale": "region",
            "kind": "burned to the waterline", "news": list(news),
        },
    }


def test_region_cascade_retires_whole_subtree(temp_db):
    ids = _seed(temp_db)
    ctx = _make_ctx(temp_db, ids, _razing_diff(), turn_idx=2)
    _commit_beat(ctx)
    cid = ids["chat"]

    # The cascade: the region book, its lore child, and the ship whose
    # anchor was physically at the doomed docks -- all retired with this
    # turn's id, rows intact (retire-not-delete history).
    for key in ("region", "records", "ship"):
        row = temp_db.q("SELECT retired_turn_id FROM lorebooks WHERE id=?",
                        (ids[key],), one=True)
        assert row["retired_turn_id"] == ctx.turn.id, key
    # Spared: canon, the far books, and the ship whose currently_within
    # link is stale (its anchor is not positioned in any doomed room).
    for key in ("canon", "kingdom", "capital", "stale"):
        row = temp_db.q("SELECT retired_turn_id FROM lorebooks WHERE id=?",
                        (ids[key],), one=True)
        assert row["retired_turn_id"] is None, key

    # Every registered room of every cascaded book retired.
    rows = temp_db.q(
        "SELECT room_uid, retired_turn_id FROM room_registry "
        "WHERE chat_id=? ORDER BY room_uid", (cid,))
    stamped = {r["room_uid"]: r["retired_turn_id"] for r in rows}
    assert stamped["docks"] == ctx.turn.id
    assert stamped["market"] == ctx.turn.id
    assert stamped["deck_3"] == ctx.turn.id
    assert stamped["headland"] is None  # minted this beat, lives on

    # Live scene folded through the ordinary diff machinery: doomed
    # rooms and the doomed ship gone, the survivor safe on the headland,
    # the departed occupant's stale position vacated with her room.
    sc = temp_db.wget(cid, "scene", {})
    assert set(sc["rooms"]) == {"headland"}
    assert "ship_a" not in sc["entities"]
    assert sc["positions"] == {"The Stranger": "headland"}

    # Engine notice staged for the next director beat.
    notices = temp_db.wget(cid, "engine_notices", [])
    assert any("burned to the waterline" in n and "3 lorebook(s)" in n
               for n in notices)


def test_stranded_occupant_anywhere_in_cascade_fails_commit(temp_db):
    ids = _seed(temp_db)
    diff = _razing_diff()
    del diff["cast_changes"]  # Mira left in the doomed fish market
    ctx = _make_ctx(temp_db, ids, diff, turn_idx=2)
    with pytest.raises(RuntimeError, match="strand.*Mira"):
        commit.prepare_scene_commit(ctx)
    # Nothing was retired -- preparation failed before any durable write.
    assert temp_db.q(
        "SELECT COUNT(*) c FROM lorebooks WHERE chat_id=? AND "
        "retired_turn_id IS NOT NULL", (ids["chat"],), one=True)["c"] == 0
    assert temp_db.q(
        "SELECT COUNT(*) c FROM room_registry WHERE chat_id=? AND "
        "retired_turn_id IS NOT NULL", (ids["chat"],), one=True)["c"] == 0


def test_stranding_guard_reaches_presence_cascaded_books(temp_db):
    """The Stranger is aboard the ship that only joins the cascade via
    its currently_within link + physical position -- leaving him there
    must still fail the whole commit."""
    ids = _seed(temp_db)
    diff = _razing_diff()
    del diff["positions"]  # nobody repositioned The Stranger off deck_3
    ctx = _make_ctx(temp_db, ids, diff, turn_idx=2)
    with pytest.raises(RuntimeError, match="strand.*The Stranger"):
        commit.prepare_scene_commit(ctx)


def test_doomed_vehicle_inside_the_region_is_not_stranded(temp_db):
    """ship_a sits in the doomed docks but is itself destroyed by the
    cascade -- it must count as doomed cargo, not a stranded occupant
    (its own deck's occupants are guarded separately, above)."""
    ids = _seed(temp_db)
    ctx = _make_ctx(temp_db, ids, _razing_diff(), turn_idx=2)
    prepared = commit.prepare_scene_commit(ctx)  # must not raise
    assert prepared["destruction"]["doomed_entities"] == [
        "harbor_district", "ship_a"]


def test_news_latency_derived_from_book_graph_distance(temp_db):
    ids = _seed(temp_db)
    ctx = _make_ctx(temp_db, ids, _razing_diff(news=[
        # No latency declared: derived from hop distance to the root.
        {"audience": "The Inland Kingdom",
         "summary": "The Harbor District burned"},
        {"audience": "The Capital", "summary": "The kingdom's port is gone"},
        # Matches no book at all: the flat far default.
        {"audience": "The Silent Order", "summary": "A light went out"},
        # Declared latency always wins -- the Director owns causality.
        {"audience": "the capital", "latency_seconds": 60,
         "summary": "Signal flash: port lost"},
    ]), turn_idx=2)
    _commit_beat(ctx)

    due = {
        json.loads(r["payload"])["summary"]: r["due_at"]
        for r in temp_db.q(
            "SELECT * FROM scheduled_events WHERE chat_id=? AND "
            "kind='news_arrival'", (ids["chat"],))
    }
    # kingdom: region-canon-kingdom = 2 hops; capital: +1 = 3 hops.
    assert due["The Harbor District burned"] == 2 * NEWS_HOP_LATENCY_SECONDS
    assert due["The kingdom's port is gone"] == 3 * NEWS_HOP_LATENCY_SECONDS
    assert due["A light went out"] == NEWS_UNREACHABLE_LATENCY_SECONDS
    assert due["Signal flash: port lost"] == 60.0


def test_distant_region_unaware_until_news_arrives(temp_db):
    """Objective destruction is immediate; awareness is latency-gated.
    The capital's audience learns 'the port fell' only when its
    news_arrival fires -- and then only as an engine notice with
    told/heard provenance for the normal director/perception path,
    never as directly injected knowledge."""
    ids = _seed(temp_db)
    _commit_beat(_make_ctx(temp_db, ids, _razing_diff(news=[
        {"audience": "The Inland Kingdom", "summary": "The port burned"},
        {"audience": "The Capital", "summary": "The port is gone"},
    ]), turn_idx=2))
    cid = ids["chat"]

    # Not yet due anywhere: no fire, no notice of it.
    ctx = _make_ctx(temp_db, ids, {"time": {"end_seconds": 3600.0,
                                            "display_advance": "later"}},
                    turn_idx=3)
    _, sweep = _commit_beat(ctx)
    assert sweep["news_fired"] == 0
    assert not any("port" in n for n in sweep["notices"])

    # The nearer audience's derived latency (2h) elapses first.
    ctx = _make_ctx(temp_db, ids, {"time": {"end_seconds": 7300.0,
                                            "display_advance": "evening"}},
                    turn_idx=4)
    _, sweep = _commit_beat(ctx)
    assert sweep["news_fired"] == 1
    assert any("The Inland Kingdom" in n and "told/heard" in n
               for n in sweep["notices"])
    assert not any("The Capital" in n for n in sweep["notices"])

    # Then the farther one (3h).
    ctx = _make_ctx(temp_db, ids, {"time": {"end_seconds": 11000.0,
                                            "display_advance": "night"}},
                    turn_idx=5)
    _, sweep = _commit_beat(ctx)
    assert sweep["news_fired"] == 1
    assert any("The Capital" in n and "told/heard" in n
               for n in sweep["notices"])
    statuses = {
        json.loads(r["payload"])["audience"]: r["status"]
        for r in temp_db.q(
            "SELECT * FROM scheduled_events WHERE chat_id=? AND "
            "kind='news_arrival'", (cid,))
    }
    assert statuses == {"The Inland Kingdom": "fired",
                        "The Capital": "fired"}


def test_region_without_a_book_is_dropped_not_guessed(temp_db):
    ids = _seed(temp_db)
    diff = _razing_diff()
    diff["destruction"]["target_id"] = "the_lost_moon"
    ctx = _make_ctx(temp_db, ids, diff, turn_idx=2)
    prepared = commit.prepare_scene_commit(ctx)
    assert prepared["destruction"] is None
    assert any("cascade" in w for w in ctx.warnings)
    assert "docks" in prepared["scene"]["rooms"], "nothing was destroyed"


def test_cascade_rerun_reproduces_identical_state(temp_db):
    """Checkpoint-whole reproducibility: restore un-retires the ENTIRE
    subtree, and rerunning the same declaration reproduces byte-identical
    books, registry, links, scheduled events, and world state."""
    ids = _seed(temp_db)
    cid = ids["chat"]
    temp_db.wset(cid, "lore_cache", [])
    ensure_checkpoint(cid, 2)

    diff = _razing_diff(news=[
        {"audience": "The Capital", "summary": "The port is gone"}])
    ctx = _make_ctx(temp_db, ids, json.loads(json.dumps(diff)), turn_idx=2)
    _commit_beat(ctx)

    def dump():
        return {
            "books": [dict(r) for r in temp_db.q(
                "SELECT * FROM lorebooks WHERE chat_id=? ORDER BY id",
                (cid,))],
            "links": [dict(r) for r in temp_db.q(
                "SELECT source_book_id, target_book_id, relation_type "
                "FROM lorebook_links ORDER BY source_book_id,"
                "target_book_id, relation_type")],
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
    for key in ("region", "records", "ship"):
        assert temp_db.q(
            "SELECT retired_turn_id FROM lorebooks WHERE id=?",
            (ids[key],), one=True)["retired_turn_id"] is None, \
            f"restore must un-retire the whole subtree ({key})"

    # The same turn rerun, as reroll does: same turn row, fresh context.
    ctx2 = PipelineContext(chat=ctx.chat, turn=ctx.turn, cast=[], input="x")
    ctx2.director_resolve = {
        "resolved_event": "beat", "dialogue_log": [],
        "state_diff": json.loads(json.dumps(diff)),
    }
    _commit_beat(ctx2)
    assert dump() == first
