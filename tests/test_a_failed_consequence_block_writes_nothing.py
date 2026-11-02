"""The living-world block the transit domain warns about lands whole or not
at all.

`commit_transit_sweep` mints the beat's consequence fuses, INSERTs them one
row at a time and records Approach D's obligations, all under one
`try/except Exception -> add_warning` inside the turn's transaction. A
failure after some INSERTs left those rows in the outer transaction and the
turn committed with them -- "any domain failure rolls the whole turn back"
became "half of this block lands", under a warning saying it was not
committed (review 2026-11-01, persist_scene_entities F11).
"""

from __future__ import annotations

import time

import world.living_world as living_world
from core.pipeline_context import ChatData, PipelineContext, TurnData
from persist import commit
from world.living_world import CONSEQUENCE_KIND


def _ctx(temp_db):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Test", "", time.time()))
    temp_db.wset(cid, "scene", {"rooms": {"tavern_main": {
        "name": "The Brass Tankard", "adjacent": []}}, "positions": {}})
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, 1, "x", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Test", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=cid, idx=1, player_input="x",
                      created=time.time()),
        cast=[], input="x")
    ctx.director_resolve = {"resolved_event": "beat", "dialogue_log": [],
                            "state_diff": {}}
    return ctx


def test_a_failure_part_way_leaves_no_row_and_the_turn_commits(
        temp_db, monkeypatch):
    real = living_world.mint_consequences

    def mint_then_break(*args, **kwargs):
        rows, warnings = real(*args, **kwargs)
        good = {"event_id": "event:first", "chat_id": args[0],
                "due_at": 600.0, "kind": CONSEQUENCE_KIND,
                "location_id": "tavern_main", "payload": "{}",
                "seed": "test", "status": "pending"}
        # The second row is missing its columns: the INSERT loop raises
        # after the first row is already written.
        return [good, {"event_id": "event:second"}], warnings

    monkeypatch.setattr(living_world, "mint_consequences", mint_then_break)
    ctx = _ctx(temp_db)
    result = commit.commit_transit_sweep(ctx, 0)
    rows = temp_db.q("SELECT event_id FROM scheduled_events WHERE chat_id=? "
                     "AND kind=?", (ctx.chat.id, CONSEQUENCE_KIND))
    assert [r["event_id"] for r in rows] == [], \
        "half the block landed under a warning that said it did not"
    assert result["consequences_minted"] == 0
    assert any("living-world consequences not committed" in w
               for w in ctx.warnings)
