"""The turn's carrier index is built once, and every write rebuilds it.

Review 2026-09-07, C9: one enumeration (`story.carriers._carriers`) was
rebuilt six times in a normal turn -- the Director's carried-report view at
interpret and again at resolve, then `advance_carriers`, `apply_tellings`,
`run_couriers` and `run_artifacts`, the last four consecutive inside
`commit_information_carriers` and all four handed the same scene object.
Measured on the 307-body charter town (chat 114, 63 charter carriers in
reach): 45 ms a rebuild, 30 ms of it `charter_runtime.carrier_entries`, and
6 rebuilds -> 2 took the six sites from 0.362 s to 0.176 s.

These tests are about the INVALIDATION, which is the only part of a memo
that can be wrong. The memo answers only for the chat, frame and scene
OBJECT it was built from, and only while no carrier ledger has been written
since -- so a stale index can never be handed to a writer that is about to
save state over it, and one story's carriers can never answer for another's.
"""

from __future__ import annotations

import json
import time

import pytest

from core.pipeline_context import ChatData, PipelineContext, TurnData


def _ctx(cid, *, frame_id=None, persona_id=None):
    return PipelineContext(
        chat=ChatData(id=cid, name="s", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=1, chat_id=cid, idx=3, player_input="",
                      created=time.time(), frame_id=frame_id),
        cast=[], input="")


def _world(db):
    cid = db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Carrier memo", "", time.time()))
    char_id = db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        ("Mora", json.dumps({"identity": {"name": "Mora", "uid": "mora_uid"}}),
         "{}", time.time()))
    db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
          "VALUES(?,?,?,'{}')", (cid, char_id, "active"))
    scene = {"rooms": {"square": {"name": "Square"}},
             "positions": {"Mora": "square"}}
    return cid, char_id, scene


@pytest.fixture()
def counted(monkeypatch):
    """`_build_carriers` runs, counted -- patched where it is DEFINED."""
    from story import carriers

    calls = []
    real = carriers._build_carriers

    def counting(*a, **k):
        calls.append(1)
        return real(*a, **k)

    monkeypatch.setattr(carriers, "_build_carriers", counting)
    return calls


def test_one_scene_object_builds_the_index_once(temp_db, counted):
    """Commit's four consumers share the scene object, so they share the walk."""
    from story import carriers

    cid, _, scene = _world(temp_db)
    ctx = _ctx(cid)
    carriers._carriers(cid, None, scene, chat=ctx.chat, ctx=ctx)
    carriers._cast_index(cid, None, scene, chat=ctx.chat, ctx=ctx)
    carriers._cast_index(cid, None, scene, chat=ctx.chat, ctx=ctx)
    carriers.carried_reports_view(cid, None, scene, chat=ctx.chat, ctx=ctx)
    assert len(counted) == 1


def test_a_ledger_write_rebuilds_the_index(temp_db, counted):
    """`save_state` is the one place all three homes meet, so it is where the
    memo is invalidated -- `advance_carriers` writes an acquisition and
    `apply_tellings` must then see it."""
    from story import carriers

    cid, char_id, scene = _world(temp_db)
    ctx = _ctx(cid)
    first = carriers._carriers(cid, None, scene, chat=ctx.chat, ctx=ctx)
    carriers._carriers(cid, None, scene, chat=ctx.chat, ctx=ctx)
    assert len(counted) == 1
    entry = next(e for e in first if e.get("row") is not None)
    carriers.save_state(cid, entry, {carriers.STATE_KEY: [{
        "world_event_id": "world_bell", "claim": "a bell rang"}]})
    again = carriers._carriers(cid, None, scene, chat=ctx.chat, ctx=ctx)
    assert len(counted) == 2
    held = next(e for e in again if e.get("row") is not None)
    assert held["state"][carriers.STATE_KEY][0]["claim"] == "a bell rang"


def test_a_different_scene_object_rebuilds(temp_db, counted):
    """Rooms come from the scene, so a scene the memo has not seen rebuilds --
    deliberately by identity, not by guessing whether two dicts agree."""
    from story import carriers

    cid, _, scene = _world(temp_db)
    ctx = _ctx(cid)
    carriers._carriers(cid, None, scene, chat=ctx.chat, ctx=ctx)
    moved = json.loads(json.dumps(scene))
    moved["positions"]["Mora"] = "road"
    entries = carriers._carriers(cid, None, moved, chat=ctx.chat, ctx=ctx)
    assert len(counted) == 2
    assert [e["room"] for e in entries if e.get("row") is not None] == ["road"]


def test_the_same_scene_object_mutated_in_place_rebuilds(temp_db, counted):
    """The half identity keying cannot answer.

    `test_a_different_scene_object_rebuilds` round-trips the scene through
    JSON, so it proves the memo notices a NEW dict and says nothing about a
    mutated one -- and a dict mutated in place keeps its id. Reproduction
    (bench chat 114, review 2026-09-07 C9's rework): one ctx, one scene
    object, `positions["Mora"]` "square" -> "road" with no ledger write in
    between. Before `_positions_stamp` the memoised read answered room
    "square" where a fresh walk answered "road".
    """
    from story import carriers

    cid, _, scene = _world(temp_db)
    ctx = _ctx(cid)
    first = carriers._carriers(cid, None, scene, chat=ctx.chat, ctx=ctx)
    assert [e["room"] for e in first if e.get("row") is not None] == ["square"]

    scene["positions"]["Mora"] = "road"          # same object, no ledger write
    again = carriers._carriers(cid, None, scene, chat=ctx.chat, ctx=ctx)
    assert len(counted) == 2
    assert [e["room"] for e in again if e.get("row") is not None] == ["road"]

    # And still one walk while the positions hold still.
    carriers._carriers(cid, None, scene, chat=ctx.chat, ctx=ctx)
    assert len(counted) == 2


def test_another_chat_or_frame_never_reads_this_ones_index(temp_db, counted):
    from story import carriers

    cid, _, scene = _world(temp_db)
    other, _, _ = _world(temp_db)
    ctx = _ctx(cid)
    carriers._carriers(cid, None, scene, chat=ctx.chat, ctx=ctx)
    carriers._carriers(other, None, scene, chat=ctx.chat, ctx=ctx)
    carriers._carriers(cid, 7, scene, chat=ctx.chat, ctx=ctx)
    assert len(counted) == 3


def test_no_context_means_no_memo(temp_db, counted):
    """A caller with no ctx -- and a stub context that keeps no side channels
    -- rebuilds exactly as before the memo existed."""
    import types

    from story import carriers

    cid, _, scene = _world(temp_db)
    carriers._carriers(cid, None, scene)
    carriers._carriers(cid, None, scene)
    stub = types.SimpleNamespace(chat=None, turn=None)
    carriers._carriers(cid, None, scene, ctx=stub)
    carriers._carriers(cid, None, scene, ctx=stub)
    assert len(counted) == 4


def test_each_caller_gets_its_own_ledger_to_mutate(temp_db, counted):
    """Every consumer mutates the state it was handed and then saves it. A
    shared index must not let one consumer's half-finished mutation appear in
    the next one's list."""
    from story import carriers

    cid, _, scene = _world(temp_db)
    ctx = _ctx(cid)
    first = carriers._carriers(cid, None, scene, chat=ctx.chat, ctx=ctx)
    first[0]["state"][carriers.STATE_KEY] = [{"world_event_id": "x"}]
    second = carriers._carriers(cid, None, scene, chat=ctx.chat, ctx=ctx)
    assert len(counted) == 1
    assert second[0]["state"].get(carriers.STATE_KEY) is None


def test_the_two_director_stages_read_one_scene_and_one_index(
        temp_db, counted, monkeypatch):
    """`_carried_reports_view` runs at interpret and again at resolve. Both
    read the committed scene, so both read one scene object and one index --
    and a scene write between them (the commit that ends the turn) rebuilds."""
    from agents.director import _carried_reports_view
    from story import scene as scene_mod

    cid, _, scene = _world(temp_db)
    temp_db.wset(cid, "scene", scene)
    ctx = _ctx(cid)

    reads = []
    real = scene_mod.get_scene

    def counting(*a, **k):
        reads.append(1)
        return real(*a, **k)

    monkeypatch.setattr(scene_mod, "get_scene", counting)

    assert _carried_reports_view(ctx) == []
    assert _carried_reports_view(ctx) == []
    assert len(reads) == 1
    assert len(counted) == 1

    temp_db.wset(cid, "scene", dict(scene, positions={"Mora": "road"}))
    _carried_reports_view(ctx)
    assert len(reads) == 2
    assert len(counted) == 2
