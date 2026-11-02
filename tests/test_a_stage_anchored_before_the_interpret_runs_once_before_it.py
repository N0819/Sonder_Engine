"""An extension stage anchored `before:director_interpret` runs once, before
the interpretation, and the turn completes.

`docs/guides/EXTENSIONS.md` names `director_interpret` first among the
anchors a stage may use, and `api.add_stage` accepts it. The runtime ran the
interpret explicitly at ord 0 and then walked the spliced plan from index 1
whatever index 0 held, so with the plan `[ext:demo:pre, director_interpret,
...]` the interpretation was computed TWICE (a second model call), the
extension stage never, the commit landed, and the completion invariant then
failed the committed turn -- every turn of every chat with such an extension
(audit of 2026-11-01, agents_runtime_loops_mapping F11, reproduced:
`interpret calls: 2  ext stage calls: 0`).
"""

from __future__ import annotations

import time

import pytest

import agents.runtime as runtime
from agents.storage import variant_count


@pytest.fixture
def spliced_before_the_interpret(monkeypatch):
    import extension_runtime

    def splice(plan, chat_id=None):
        out = []
        for key, label in plan:
            if key == "director_interpret":
                out.append(("ext:demo:pre", "Demo · before"))
            out.append((key, label))
        return out

    monkeypatch.setattr(extension_runtime, "apply_plan_splices", splice)
    calls = {"interpret": 0, "pre": 0, "seen_by_pre": []}

    def interpret(ctx, nonce):
        calls["interpret"] += 1
        assert ctx.get("ext:demo:pre") is not None, \
            "the stage anchored before the interpret ran before it"
        return {"flow": {"reactors": []}}

    def pre(ctx, nonce):
        calls["pre"] += 1
        calls["seen_by_pre"].append(ctx.get("director_interpret"))
        return {"pre": True}

    stubs = {
        "ext:demo:pre": pre,
        "director_interpret": interpret,
        "compile_world_context": lambda c, n: {"compiled": True},
        "perception_act": lambda c, n: {"views": {}},
        "director_resolve": lambda c, n: {"state_diff": {}},
        "background_react": lambda c, n: {"fired": False},
        "perception_outcome": lambda c, n: {"views": {}},
        "narrator": lambda c, n: {"prose": "ok"},
        "commit": lambda c, n: {"committed": True},
    }
    for key, fn in stubs.items():
        monkeypatch.setitem(runtime.STEP_HANDLERS, key, fn)
    return calls


def _turn(db):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Anchored", "", time.time()))
    tid = db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, 1, "look around", time.time()))
    return cid, tid


def _steps(db, tid):
    return [(r["key"], r["ord"]) for r in db.q(
        "SELECT key, ord FROM steps WHERE turn_id=? ORDER BY ord", (tid,))]


def test_the_stage_runs_once_before_the_interpretation(
        temp_db, spliced_before_the_interpret):
    calls = spliced_before_the_interpret
    cid, tid = _turn(temp_db)
    events = list(runtime._run_pipeline(cid, tid))
    assert events[-1]["type"] == "done"
    assert calls["interpret"] == 1 and calls["pre"] == 1
    assert calls["seen_by_pre"] == [None]
    steps = _steps(temp_db, tid)
    assert steps[:3] == [("ext:demo:pre", 0), ("director_interpret", 1),
                         ("compile_world_context", 2)]
    assert runtime.resume_key_for_turn(tid, cid) is None


def test_a_rerun_after_the_interpretation_reads_both_back(
        temp_db, spliced_before_the_interpret):
    calls = spliced_before_the_interpret
    cid, tid = _turn(temp_db)
    list(runtime._run_pipeline(cid, tid))
    list(runtime._run_pipeline(cid, tid, from_key="narrator"))
    assert calls["interpret"] == 1 and calls["pre"] == 1
    assert variant_count(tid, "director_interpret") == 1


def test_a_rerun_from_the_stage_runs_the_interpretation_again(
        temp_db, spliced_before_the_interpret):
    calls = spliced_before_the_interpret
    cid, tid = _turn(temp_db)
    list(runtime._run_pipeline(cid, tid))
    events = list(runtime._run_pipeline(cid, tid, from_key="ext:demo:pre"))
    assert events[-1]["type"] == "done"
    assert calls["pre"] == 2 and calls["interpret"] == 2


def test_a_rerun_from_the_interpretation_keeps_the_stage_before_it(
        temp_db, spliced_before_the_interpret):
    calls = spliced_before_the_interpret
    cid, tid = _turn(temp_db)
    list(runtime._run_pipeline(cid, tid))
    list(runtime._run_pipeline(cid, tid, from_key="director_interpret"))
    assert calls["pre"] == 1 and calls["interpret"] == 2


def test_a_beat_with_no_such_stage_plans_as_it_always_did(temp_db,
                                                          monkeypatch):
    import extension_runtime
    monkeypatch.setattr(extension_runtime, "apply_plan_splices",
                        lambda plan, chat_id=None: plan)
    for key, fn in {
        "director_interpret": lambda c, n: {"flow": {"reactors": []}},
        "compile_world_context": lambda c, n: {"compiled": True},
        "perception_act": lambda c, n: {"views": {}},
        "director_resolve": lambda c, n: {"state_diff": {}},
        "background_react": lambda c, n: {"fired": False},
        "perception_outcome": lambda c, n: {"views": {}},
        "narrator": lambda c, n: {"prose": "ok"},
        "commit": lambda c, n: {"committed": True},
    }.items():
        monkeypatch.setitem(runtime.STEP_HANDLERS, key, fn)
    cid, tid = _turn(temp_db)
    list(runtime._run_pipeline(cid, tid))
    assert _steps(temp_db, tid)[0] == ("director_interpret", 0)
