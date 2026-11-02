"""A charter order the institution refuses lands NOTHING, inside a commit too.

`author_charter_ops` is all-or-nothing by design -- "an event that half lands
is a town whose ledgers disagree with the sentence that made them" -- and the
commit tells the Director "nothing was dispatched" when it refuses. Inside a
commit that was false. Every turn commits under `registry_session()`, where
`registry_for_update` hands out the SESSION's shared parsed copy, so ops 0..k-1
of a refused event were already applied to the copy `flush_registry_session`
then wrote whenever any other writer had dirtied it -- and
`_apply_charter_placements`, one line earlier in `commit_scene`, dirties it on
every beat that moves a townsperson.

Measured (review 2026-11-01, persist_scene_entities F1): `[vacate_post cook,
errand body:"nobody"]` was refused at op 1 and the cook's watch went from
`yusra` to None anyway. `test_charter_ops.py::test_a_refused_event_writes_
nothing` held only because it runs outside a session.
"""

from __future__ import annotations

import time

from core.db import transaction
from core.pipeline_context import ChatData, PipelineContext, TurnData
from persist.commit import _apply_charter_orders
from world.charter import normalize_charter, seed_needs, seed_roster
from world.charter_runtime import (flush_registry_session, registry_for,
                                   registry_for_update, registry_session,
                                   save_registry)


def _house():
    state = normalize_charter({
        "key": "caravanserai",
        "scene": {"rooms": {
            "gate": {"name": "Gate", "adjacent": [{"to": "kitchen"}]},
            "kitchen": {"name": "Kitchen", "adjacent": [{"to": "gate"}]},
        }},
        "posts": {
            "gate_warden": {"place": "gate", "requires": {},
                            "purpose": "keeps the gate"},
            "cook": {"place": "kitchen", "requires": {},
                     "purpose": "feeds the house"},
        },
        "bodies": {
            "vesk": {"name": "Orhan Vesk", "place": "gate",
                     "home_post": "gate_warden"},
            "yusra": {"name": "Yusra", "place": "kitchen", "home_post": "cook"},
        },
        "watch": {"gate_warden": "vesk", "cook": "yusra"},
        "clock_hours": 12.0,
    })
    state["roster"] = seed_roster(state["bodies"])
    state["needs"] = seed_needs(state["bodies"])
    return state


def _ctx(temp_db):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Caravanserai", "", time.time()))
    temp_db.wset(cid, "scene", {"rooms": {"gate": {"name": "Gate"},
                                          "kitchen": {"name": "Kitchen"}},
                                "positions": {}, "entities": {}})
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, 3, "", time.time()))
    save_registry(cid, {"items": {"caravanserai": {"state": _house()}}})
    return PipelineContext(
        chat=ChatData(id=cid, name="Caravanserai", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=cid, idx=3, player_input="",
                      created=time.time()),
        cast=[], input="")


def _watch(cid):
    return dict(registry_for(cid, None)["items"]["caravanserai"]["state"]
                ["watch"])


def _commit_orders(ctx, ops):
    """The commit's own shape: a transaction, a registry session, an earlier
    writer that dirtied the entry (`apply_scene_placements` does on every
    beat that moves a townsperson), the orders, then the flush."""
    with transaction(), registry_session():
        live = registry_for_update(ctx.chat.id, None)
        save_registry(ctx.chat.id, live, None)
        landed = _apply_charter_orders(ctx, ops)
        flush_registry_session()
    return landed


def test_a_refused_event_leaves_the_registry_as_it_was(temp_db):
    ctx = _ctx(temp_db)
    before = _watch(ctx.chat.id)
    assert before["cook"] == "yusra"
    landed = _commit_orders(ctx, [
        {"op": "vacate_post", "charter": "caravanserai", "post": "cook"},
        {"op": "errand", "charter": "caravanserai", "body": "nobody",
         "to": "gate"},
    ])
    assert landed == 0
    assert _watch(ctx.chat.id) == before, \
        "op 0 of a refused event landed: the event half-applied"
    assert any("nothing was dispatched" in note
               for note in ctx.engine_feedback)


def test_an_accepted_event_lands_whole(temp_db):
    ctx = _ctx(temp_db)
    landed = _commit_orders(ctx, [
        {"op": "vacate_post", "charter": "caravanserai", "post": "cook"},
        {"op": "errand", "charter": "caravanserai", "body": "vesk",
         "to": "kitchen"},
    ])
    assert landed == 2
    assert not _watch(ctx.chat.id).get("cook")


def test_the_registry_other_writers_hold_is_the_one_that_lands(temp_db):
    """The accepted event lands IN the session's own copy, so a writer
    later in the same commit that already holds it sees the event."""
    ctx = _ctx(temp_db)
    with transaction(), registry_session():
        live = registry_for_update(ctx.chat.id, None)
        assert _apply_charter_orders(ctx, [
            {"op": "vacate_post", "charter": "caravanserai",
             "post": "cook"}]) == 1
        assert registry_for_update(ctx.chat.id, None) is live
        assert not live["items"]["caravanserai"]["state"]["watch"].get("cook")
        flush_registry_session()
    assert not _watch(ctx.chat.id).get("cook")
