"""Two per-beat costs inside the write lock, paid only when something reads
what they produce.

* `commit_world_pressure` parsed the whole scene on every beat and used it
  only for `tick` ops (review 2026-11-01, persist_scene_entities E1): a beat
  with no tick parses nothing.
* `_refuse_unheld_transfers` re-merged the whole scene (a deep copy) after
  EVERY accepted inventory op once a diff carried two or more (E2: O(ops x
  scene), ~2.4 ms each on the largest stored scene). The merged scene is read
  only by a LATER op's source check, so a merge is now made only when such
  a check is about to read it -- the same merges, in the same order, minus
  the ones nothing read. What is refused is unchanged.
"""

from __future__ import annotations

import time

import persist.commit_ledgers as commit_ledgers
import persist.commit_scene_state as commit_scene_state
from core.pipeline_context import ChatData, PipelineContext, TurnData
from persist.commit import _refuse_unheld_transfers, commit_world_pressure


def _ctx(temp_db, diff):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Test", "", time.time()))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, 3, "x", time.time()))
    temp_db.wset(cid, "scene", {"rooms": {"hall": {}}, "positions": {}})
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Test", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=cid, idx=3, player_input="x",
                      created=time.time()),
        cast=[], input="x")
    ctx.director_resolve = {"resolved_event": "", "dialogue_log": [],
                            "state_diff": diff}
    return ctx


def test_a_beat_with_no_tick_parses_no_scene(temp_db, monkeypatch):
    ctx = _ctx(temp_db, {})
    reads = []
    real = commit_ledgers.wget

    def counting(cid, key, default=None):
        reads.append(key)
        return real(cid, key, default)

    monkeypatch.setattr(commit_ledgers, "wget", counting)
    commit_world_pressure(ctx, 0)
    assert "scene" not in reads


def _scene():
    return {"rooms": {"hall": {"name": "Hall"}},
            "positions": {"Mara": "hall", "Vesna": "hall", "Tam": "hall",
                          "box": "hall"},
            "entities": {"box": {"name": "box", "kind": "object",
                                 "portable": True}},
            "contained": {"box": {"in": "Mara", "mode": "held"}}}


def _count_merges(monkeypatch):
    merges = []
    real = commit_scene_state.merge_scene_with_diff

    def counting(*args, **kwargs):
        merges.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(commit_scene_state, "merge_scene_with_diff", counting)
    return merges


class _Ctx:
    def __init__(self):
        self.warnings, self.told = [], []

    def add_warning(self, msg):
        self.warnings.append(msg)

    def tell_director(self, msg):
        self.told.append(msg)


def test_ops_no_later_check_reads_cost_no_merge(monkeypatch):
    merges = _count_merges(monkeypatch)
    diff = {"inventory_ops": [
        {"op": "transfer", "object_id": "box", "from_id": "Mara",
         "to_id": "Vesna"},
        {"op": "move", "object_id": "box", "to_id": "hall"},
        {"op": "move", "object_id": "box", "to_id": "hall"}]}
    assert _refuse_unheld_transfers(_Ctx(), _scene(), diff) == []
    assert merges == [], "a merge nothing read was made"


def test_a_later_check_still_sees_the_earlier_transfer(monkeypatch):
    """The causal order the merges exist for: the second transfer's source
    holds the box only because the first transfer landed."""
    merges = _count_merges(monkeypatch)
    ctx = _Ctx()
    diff = {"inventory_ops": [
        {"op": "transfer", "object_id": "box", "from_id": "Mara",
         "to_id": "Vesna"},
        {"op": "transfer", "object_id": "box", "from_id": "Vesna",
         "to_id": "Tam"}]}
    assert _refuse_unheld_transfers(ctx, _scene(), diff) == []
    assert len(diff["inventory_ops"]) == 2 and not ctx.told
    assert len(merges) == 1
