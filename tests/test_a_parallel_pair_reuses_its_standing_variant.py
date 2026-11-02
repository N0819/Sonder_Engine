"""A stage run in a parallel group mints no second, identical variant either.

`_save_or_reuse_variant` (PM19, 2026-09-05) keeps a stage's standing variant
when a rerun answers byte-for-byte the same -- but only the serial path called
it. `compile_world_context` and `perception_act`, the deterministic pair the
dedup was written for, run as a group on every beat without a skip (restored
two days after the dedup, 1d61d3d5), and the group saved through `save_step`
directly. Measured on the owner's database (audit of 2026-11-01,
agents_runtime_loops_mapping F19), last 400 turns: 135 inactive
`compile_world_context` variants and 32 `perception_act` ones byte-identical
to the active one, against 0 for the serial `perception_outcome`.
"""

from __future__ import annotations

import time

import agents.runtime as runtime
from agents.storage import variant_count


def test_a_rerun_of_the_deterministic_pair_keeps_one_variant_each(
        temp_db, monkeypatch):
    import extension_runtime
    monkeypatch.setattr(extension_runtime, "apply_plan_splices",
                        lambda plan, chat_id=None: plan)
    for key, fn in {
        "director_interpret": lambda c, n: {"flow": {"reactors": []}},
        "compile_world_context": lambda c, n: {"relevant_lore": [],
                                               "compiled": True},
        "perception_act": lambda c, n: {"views": {"player": "The hall."}},
        "director_resolve": lambda c, n: {"state_diff": {}},
        "background_react": lambda c, n: {"fired": False},
        "perception_outcome": lambda c, n: {"views": {}},
        "narrator": lambda c, n: {"prose": "ok"},
        "commit": lambda c, n: {"committed": True},
    }.items():
        monkeypatch.setitem(runtime.STEP_HANDLERS, key, fn)
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Pair", "", time.time()))
    tid = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, 1, "look", time.time()))
    list(runtime._run_pipeline(cid, tid))
    for _ in range(2):
        list(runtime._run_pipeline(cid, tid, from_key="compile_world_context"))
    assert variant_count(tid, "compile_world_context") == 1
    assert variant_count(tid, "perception_act") == 1
    stale = temp_db.q("SELECT key FROM steps WHERE turn_id=? AND stale=1",
                      (tid,))
    assert [r["key"] for r in stale] == []


def test_a_group_member_that_answers_differently_gets_its_variant(
        temp_db, monkeypatch):
    import extension_runtime
    monkeypatch.setattr(extension_runtime, "apply_plan_splices",
                        lambda plan, chat_id=None: plan)
    answers = iter(["first", "second"])
    for key, fn in {
        "director_interpret": lambda c, n: {"flow": {"reactors": []}},
        "compile_world_context": lambda c, n: {"lore": next(answers)},
        "perception_act": lambda c, n: {"views": {}},
        "director_resolve": lambda c, n: {"state_diff": {}},
        "background_react": lambda c, n: {"fired": False},
        "perception_outcome": lambda c, n: {"views": {}},
        "narrator": lambda c, n: {"prose": "ok"},
        "commit": lambda c, n: {"committed": True},
    }.items():
        monkeypatch.setitem(runtime.STEP_HANDLERS, key, fn)
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Pair", "", time.time()))
    tid = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, 1, "look", time.time()))
    list(runtime._run_pipeline(cid, tid))
    list(runtime._run_pipeline(cid, tid, from_key="compile_world_context"))
    assert variant_count(tid, "compile_world_context") == 2
    assert variant_count(tid, "perception_act") == 1
