"""While a checkpoint conversion runs, its poll answers its progress alone.

The maintenance card polls `GET /api/maintenance/checkpoints` every second
while a conversion runs, and reads nothing but `progress` until it ends
(`static/js/settings.js`). The route answered every poll with the full
storage status too -- `checkpoint_storage_status`, which selects and parses
EVERY checkpoint blob in scope (its own docstring: "NOT cheap"): 49 s on the
owner's store, so polls overlapped each other and the conversion they were
watching (settings UI lane, 2026-11-01). The route's docstring said "Safe to
poll ... not a full parse". Idle, the card wants the whole report, and gets it.
"""
from __future__ import annotations


def test_a_poll_during_a_run_parses_no_checkpoint(temp_db, monkeypatch):
    from persist import checkpoints
    from web import app

    scans = []
    monkeypatch.setattr(app, "checkpoint_storage_status",
                        lambda *a, **k: scans.append(1) or {"checkpoints": 0})
    monkeypatch.setitem(checkpoints._COMPACT_STATE, "running", True)
    monkeypatch.setitem(checkpoints._COMPACT_STATE, "done", 3)
    monkeypatch.setitem(checkpoints._COMPACT_STATE, "total", 9)

    out = app.maintenance_checkpoints()
    assert scans == []
    assert set(out) == {"progress"}
    assert out["progress"]["running"] is True and out["progress"]["done"] == 3


def test_an_idle_poll_answers_the_whole_report(temp_db, monkeypatch):
    from persist import checkpoints
    from web import app

    monkeypatch.setitem(checkpoints._COMPACT_STATE, "running", False)
    out = app.maintenance_checkpoints()
    assert out["progress"]["running"] is False
    assert "checkpoints" in out and "legacy" in out
