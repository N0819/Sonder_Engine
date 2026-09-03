"""Charter is not a feature with a switch; it is where unwatched bodies live.

Ruled by the owner 2026-09-04: charter defaults on and cannot be turned off.
The only reason it does not run is that this story has no charter yet.

The gate that is gone read the `offscreen_life` ceiling and refused below
`deterministic`. That ceiling is a SPEND gate -- `living_world.effective_depth`
says so outright, and `story/artifacts.py` uses it to withhold model-authored
wording. Charter's advance path spends nothing: `world/charter_runtime.py`
contains no provider seam at all, and `advance_snapshot` is a deterministic walk
of a copied registry. So the ceiling was withholding free work, and a host who
set the ladder to `inert` for cost reasons silently froze the town instead.
"""
import time
import types

import pytest

from world.charter import normalize_charter, seed_needs, seed_roster
from world.charter_runtime import save_registry, schedule_charter_ticks


def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Charter always", "", time.time()))


def _ctx(cid):
    return types.SimpleNamespace(
        chat=types.SimpleNamespace(id=cid),
        turn=types.SimpleNamespace(idx=3, frame_id=None))


def _seed_one_charter(db, cid):
    db.wset(cid, "scene", {"rooms": {"room_a": {}}, "positions": {}})
    charter = normalize_charter({
        "key": "works",
        "upkeeps": {"safe": {"place": "room_a", "level": 1.0, "floor": 0.2,
                             "drift_per_hour": 0.0, "service_per_hour": 1.0}},
        "posts": {"safe_post": {"place": "room_a", "serves": ["safe"],
                                "requires": {"safe_skill": 1}}},
        "bodies": {"alice": {"place": "room_a",
                             "competence": {"safe_skill": 1}}},
        "priority": ["safe"],
    })
    charter["roster"] = seed_roster(charter["bodies"])
    charter["needs"] = seed_needs(charter["bodies"])
    save_registry(cid, {"items": {"works": {
        "state": charter, "last_elapsed_seconds": 0.0, "window_hours": 1.0,
    }}})


def _epoch():
    return {"opportunity": True, "epoch_id": "epoch-1", "elapsed_seconds": 3600.0}


@pytest.mark.parametrize("rung", ["inert", "deterministic", "stochastic"])
def test_charter_runs_at_every_rung_of_the_offscreen_ladder(temp_db, monkeypatch,
                                                            rung):
    cid = _chat(temp_db)
    temp_db.wset(cid, "dialogue_config", {"offscreen_life": rung})
    _seed_one_charter(temp_db, cid)
    submitted = {}

    def immediate_submit(chat_id, key, produce, base_turn=None):
        submitted["key"] = key
        return types.SimpleNamespace(as_dict=lambda: {"key": key})

    monkeypatch.setattr("world.charter_runtime.jobs.submit", immediate_submit)
    epoch = _epoch()

    job = schedule_charter_ticks(_ctx(cid), epoch)

    assert job is not None, "the ladder must not silence charter at %r" % rung
    assert epoch.get("charter_skip") is None
    assert submitted["key"] == "charter:epoch-1"


def test_the_only_reason_charter_does_not_run_is_that_there_is_none(temp_db):
    cid = _chat(temp_db)
    temp_db.wset(cid, "dialogue_config", {"offscreen_life": "stochastic"})
    epoch = _epoch()

    assert schedule_charter_ticks(_ctx(cid), epoch) is None
    assert epoch["charter_skip"] == "no_charters"


def test_a_beat_with_no_epoch_opportunity_still_schedules_nothing(temp_db):
    cid = _chat(temp_db)
    _seed_one_charter(temp_db, cid)

    assert schedule_charter_ticks(_ctx(cid), {}) is None
    assert schedule_charter_ticks(_ctx(cid), {"opportunity": True}) is None
