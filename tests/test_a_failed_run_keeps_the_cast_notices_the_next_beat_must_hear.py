"""A run that fails keeps the cast's arrival and departure notices.

The cast routes queue an arrival or a departure on `pending`; the
interpretation reads it, and the commit's own `pending` domain clears it once
the beat that heard it lands. `run_pipeline`'s failure branch ALSO wiped it,
for any failure at all -- so a provider error at `director_interpret` (HTTP
402 is the measured PQ10 case) left the retry's interpretation never told the
character had arrived, while a user's Stop, which takes the `Aborted` branch,
kept it: the two failures disagreed (audit of 2026-11-01,
agents_runtime_loops_mapping F3). The wipe dated to the first upload with no
stated reason; the commit is the consumer.
"""

from __future__ import annotations

import time

import pytest

import agents.runtime as runtime
from core.db import wget, wset


def _stub(monkeypatch, interpret):
    import extension_runtime
    monkeypatch.setattr(extension_runtime, "apply_plan_splices",
                        lambda plan, chat_id=None: plan)
    stubs = {
        "director_interpret": interpret,
        "compile_world_context": lambda c, n: {"compiled": True},
        "perception_act": lambda c, n: {"views": {}},
        "director_resolve": lambda c, n: {"state_diff": {}},
        "background_react": lambda c, n: {"fired": False},
        "perception_outcome": lambda c, n: {"views": {}},
        "narrator": lambda c, n: {"prose": "ok"},
        "commit": lambda c, n: (wset(c.chat.id, "pending", [])
                                or {"committed": True}),
    }
    for key, fn in stubs.items():
        monkeypatch.setitem(runtime.STEP_HANDLERS, key, fn)


def _turn(db, cid, idx):
    return db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, idx, "look around", time.time()))


ARRIVAL = [{"type": "arrival", "char_id": 7, "name": "Ann"}]


def test_a_failure_at_the_interpretation_keeps_the_arrival(temp_db,
                                                          monkeypatch):
    def broke(ctx, nonce):
        raise RuntimeError("HTTP 402: out of credit")

    _stub(monkeypatch, broke)
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Pending", "", time.time()))
    wset(cid, "pending", ARRIVAL)
    tid = _turn(temp_db, cid, 1)
    with pytest.raises(RuntimeError, match="402"):
        list(runtime.run_pipeline(cid, tid))
    assert wget(cid, "pending") == ARRIVAL


def test_a_failure_after_the_interpretation_keeps_it_too(temp_db,
                                                        monkeypatch):
    _stub(monkeypatch, lambda c, n: {"flow": {"reactors": []}})

    def broke(ctx, nonce):
        raise RuntimeError("the resolve broke")

    monkeypatch.setitem(runtime.STEP_HANDLERS, "director_resolve", broke)
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Pending", "", time.time()))
    wset(cid, "pending", ARRIVAL)
    tid = _turn(temp_db, cid, 1)
    with pytest.raises(RuntimeError, match="resolve broke"):
        list(runtime.run_pipeline(cid, tid))
    assert wget(cid, "pending") == ARRIVAL


def test_the_commit_that_hears_it_still_clears_it(temp_db, monkeypatch):
    _stub(monkeypatch, lambda c, n: {"flow": {"reactors": []}})
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Pending", "", time.time()))
    wset(cid, "pending", ARRIVAL)
    tid = _turn(temp_db, cid, 1)
    list(runtime.run_pipeline(cid, tid))
    assert wget(cid, "pending") == []
