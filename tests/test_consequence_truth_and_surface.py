"""A82 (review 2026-09-07): a declared fuse is minted whatever the setting
says; the setting gates where a fired one can be LEARNED.

The prose author is asked for `state_diff.consequences` on every beat -- its
chunk carries no gate key -- and `commit_transit_sweep` used to mint only
when the chat's `scheduled_consequence` depth allowed it. That depth defaults
to OFF, so the default story spent the tokens declaring what the world was
about to owe and the commit discarded all of it with a warning. Approach D,
one screen below the same code, states the opposite rule for its own ledger:
layer-1 truth accumulates, settings gate surfaces.

So the mint is unconditional now -- a fuse is Director-adjudicated causality,
and switching the mechanism on later must not find the world had forgotten
its own causes -- and B's depth is read at the two NOTICE reads that put a
fired fuse's own `what` on the page: the walk-in notice
(`mechanics._fire_due_events`/`mechanics_sweep`) and the re-entry residue
(`routines.residue_for`). Those are what this file pins.

A third surface exists and is deliberately ungated: the carrier rail
(`story/carriers.advance_carriers`) hands a located `world_events` row's
`witnessed` text to a body physically standing in that room -- the
presence-gated acquisition LIVING_WORLD.md names. Presence decides there,
not the menu, so "off" means a story never meets a scheduled consequence
through the two notice reads; it does not mean a character standing where
one fires cannot carry what they saw.
"""

from __future__ import annotations

import json
import time

import pytest

from core.pipeline_context import ChatData, PipelineContext, TurnData
from persist import commit
from world.living_world import CONSEQUENCE_KIND

SCENE = {"rooms": {"tavern_main": {"name": "The Brass Tankard tavern",
                                   "adjacent": []}},
         "positions": {}}

DECLARED = [{"what": "the patrol is doubled on the harbour road",
             "where": "tavern_main", "due_seconds": 7200,
             "witnessed": "the watch captain says so in the taproom"}]


def _fuse_row(due_at=100.0, frame_id=None, base_turn=1,
              where="tavern_main"):
    return {"event_id": "event:aa", "due_at": due_at,
            "kind": CONSEQUENCE_KIND, "location_id": where,
            "payload": json.dumps({"frame_id": frame_id, "where": where,
                                   "what": "the patrol is doubled",
                                   "base_turn": base_turn})}


def _chat(temp_db, living_world=None):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Test", "", time.time()))
    temp_db.wset(cid, "scene", dict(SCENE))
    if living_world is not None:
        temp_db.wset(cid, "living_world", living_world)
    return cid


def _ctx(temp_db, cid, diff, turn_idx=1):
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, turn_idx, "x", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Test", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=cid, idx=turn_idx,
                      player_input="x", created=time.time()),
        cast=[], input="x")
    ctx.director_resolve = {"resolved_event": "beat", "dialogue_log": [],
                            "state_diff": diff}
    return ctx


def _minted(temp_db, cid):
    return temp_db.q("SELECT * FROM scheduled_events WHERE chat_id=? AND "
                     "kind=?", (cid, CONSEQUENCE_KIND))


class TestTheMintIsTruth:
    def test_a_declared_fuse_is_minted_with_the_setting_off(self, temp_db):
        """The default story: the sheet asked, the author answered, and the
        commit threw it away. Now it is a row."""
        cid = _chat(temp_db)
        ctx = _ctx(temp_db, cid, {"consequences": list(DECLARED)})
        result = commit.commit_transit_sweep(ctx, 0)
        assert result["consequences_minted"] == 1
        rows = _minted(temp_db, cid)
        assert len(rows) == 1 and rows[0]["status"] == "pending"
        assert not any("dropped" in w for w in ctx.warnings)

    def test_the_setting_on_mints_the_same_row(self, temp_db):
        """Turning the mechanism on changes no truth -- it was already
        being recorded -- so the two arms mint identically."""
        cid = _chat(temp_db, {"scheduled_consequence": "floor"})
        ctx = _ctx(temp_db, cid, {"consequences": list(DECLARED)})
        assert commit.commit_transit_sweep(ctx, 0)["consequences_minted"] == 1
        row = _minted(temp_db, cid)[0]
        payload = json.loads(row["payload"])
        assert payload["what"] == DECLARED[0]["what"]
        assert payload["disposition"] == "resolved_fact"

    def test_a_fuse_the_validator_refuses_is_still_reported(self, temp_db):
        """The mint's own refusals -- an unplaceable location, a due time
        that is not a number, the per-turn ceiling -- are the warnings that
        survive: a silently swallowed declaration looks like a quiet
        world."""
        cid = _chat(temp_db)
        ctx = _ctx(temp_db, cid, {"consequences": [
            {"what": "the quiet office empties", "where": "no_such_place",
             "due_seconds": 60}]})
        assert commit.commit_transit_sweep(ctx, 0)["consequences_minted"] == 0
        assert any("consequence not minted" in w for w in ctx.warnings)


class TestTheSettingGatesTheSurface:
    def test_the_walk_in_notice_is_withheld_when_the_setting_is_off(self):
        from world.mechanics import _fire_due_events

        ops, notices, counts, _ = _fire_due_events(
            {}, 200.0, None, [_fuse_row()], turn_idx=5,
            player_room="tavern_main", surface_consequences=False)
        assert ("status", "event:aa", "fired") in ops
        assert counts["consequences_fired"] == 1
        assert notices == []

    def test_the_notice_lands_when_the_setting_is_on(self):
        from world.mechanics import _fire_due_events

        _, notices, _, _ = _fire_due_events(
            {}, 200.0, None, [_fuse_row()], turn_idx=5,
            player_room="tavern_main", surface_consequences=True)
        assert len(notices) == 1

    @pytest.mark.parametrize("config,expected", [
        (None, 0), ({"scheduled_consequence": "floor"}, 1)])
    def test_the_sweep_reads_the_chats_own_depth(self, temp_db, config,
                                                 expected):
        from world.mechanics import mechanics_sweep

        cid = _chat(temp_db, config)
        _, ops, notices, counts = mechanics_sweep(
            dict(SCENE), {"elapsed_seconds": 200.0}, None, [_fuse_row()],
            chat_id=cid, turn_idx=5, player_room="tavern_main")
        assert counts["consequences_fired"] == 1
        assert ("status", "event:aa", "fired") in ops
        assert len([n for n in notices if "Falling due here" in n]) == expected

    @pytest.mark.parametrize("config,expected", [
        (None, False), ({"scheduled_consequence": "floor"}, True)])
    def test_the_re_entry_residue_reads_the_same_depth(self, temp_db, config,
                                                       expected):
        """The second place a fired fuse can be learned. Approach A's own
        halves (entropy, occupancy) are unaffected either way."""
        from world.routines import residue_for

        cid = _chat(temp_db, config)
        temp_db.wset(cid, "subject_last_seen",
                     {"tavern_main": {"turn": 3, "room": "tavern_main",
                                      "elapsed_seconds": 1000.0}})
        temp_db.qi(
            "INSERT INTO scheduled_events(event_id,chat_id,due_at,kind,"
            "location_id,payload,seed,status) VALUES(?,?,?,?,?,?,?,?)",
            ("event:c0", cid, 2000.0, CONSEQUENCE_KIND, "tavern_main",
             json.dumps({"what": "the patrol stands doubled"}), "s", "fired"))
        out = residue_for(cid, dict(SCENE), "tavern_main",
                          now_seconds=1000.0 + 9 * 86400.0)
        facts = (out or {}).get("facts") or []
        assert ("the patrol stands doubled" in facts) is expected
        assert facts, "the routine's own texture is not what B gates"
