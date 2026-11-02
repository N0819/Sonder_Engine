"""The commit stands a planned thing up in PREPARATION and marks its plan
rendered only INSIDE the turn's transaction.

`prepare_scene_commit` used the one-call `materialize_plans_in_sight`, which
wrote the plan's `rendered` mark during preparation -- before the turn's
transaction opens -- so a domain that raised afterwards rolled the scene back
(the thing was never stored) and left the ledger saying it stood: the plan
was never offered or stood up again (audit 2026-11-01,
world_layout_bridge_structure F1, reproduced; the seam pair
`plans_in_sight` / `mark_plans_rendered` is lane L12b's). The commit now
carries the marks from preparation and writes them in `commit_scene`.
"""

from __future__ import annotations

import time

import pytest

from core.db import transaction
from core.pipeline_context import ChatData, PipelineContext, TurnData
from persist.commit import commit_scene, prepare_scene_commit
from world.planned_entities import add_planned_entity, planned_entities


def _ctx(temp_db):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("A beach", "", time.time()))
    temp_db.wset(cid, "scene", {
        "location": "a beach", "rooms": {"beach": {"name": "Beach",
                                                   "adjacent": []}},
        "positions": {"The Stranger": "beach"}, "entities": {},
        "stations": {}, "attire": {}})
    plan = add_planned_entity(cid, {
        "kind": "thing", "name": "Police Box", "look": "a tall blue box",
        "brief": {"where": "beach"}}, turn_idx=0)
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, 3, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="A beach", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=cid, idx=3, player_input="",
                      created=time.time()),
        cast=[], input="")
    ctx.director_resolve = {"resolved_event": "Waves.", "dialogue_log": [],
                            "state_diff": {}}
    return ctx, plan["uid"]


def _stood(prepared):
    return [eid for eid, ent in prepared["scene"].get("entities", {}).items()
            if (ent.get("plan_ref") or {}).get("uid")]


def test_preparation_stands_it_up_and_marks_nothing(temp_db):
    ctx, uid = _ctx(temp_db)
    prepared = prepare_scene_commit(ctx)
    assert _stood(prepared), prepared["scene"].get("entities")
    assert uid in prepared["plan_marks"]
    assert "rendered" not in planned_entities(ctx.chat.id)[uid], \
        "preparation marked the plan before the transaction"


def test_the_commit_marks_it(temp_db):
    ctx, uid = _ctx(temp_db)
    commit_scene(ctx, 0, prepared=prepare_scene_commit(ctx))
    assert planned_entities(ctx.chat.id)[uid]["rendered"]["by"] == "engine"


def test_a_rolled_back_commit_leaves_the_plan_to_stand_up_again(temp_db):
    ctx, uid = _ctx(temp_db)
    prepared = prepare_scene_commit(ctx)
    with pytest.raises(RuntimeError):
        with transaction():
            commit_scene(ctx, 0, prepared=prepared)
            raise RuntimeError("a later commit domain failed")
    assert "rendered" not in planned_entities(ctx.chat.id)[uid]
    assert _stood(prepare_scene_commit(ctx))
