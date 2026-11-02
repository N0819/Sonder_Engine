"""The off-screen epoch: a boundary the world crossed, never a count of turns.

What `world/offscreen.py` keeps since its paid tiers were retired
(2026-11-01): `advance_epoch` stamps the beat identity the Charter advances on
every beat, and records an epoch when a beat crosses a boundary --
`epoch_reasons` names four. These tests came from `test_offscreen_resolution.py`,
which held them beside the retired importance x distance function, the seeded
tick draw and the profile rung; they pinned the part that is still live, so
they moved rather than went.
"""

from __future__ import annotations

import time

from world.offscreen import EPOCH_SECONDS, epoch_reasons


class TestTheEpochIsACanonicalEdge:
    def test_the_epoch_is_derived_from_canonical_edges_not_turn_count(self):
        """A conversation can consume many turns and only seconds; an epoch
        per N turns would price story length rather than dramatic density."""
        base = {"location": "Harbor"}
        assert epoch_reasons(
            turn_idx=8, previous_scene=base, scene=base,
            previous_clock={"elapsed_seconds": 5},
            clock={"elapsed_seconds": 3599}, transit_result={}) == []
        assert epoch_reasons(
            turn_idx=9, previous_scene=base, scene=base,
            previous_clock={"elapsed_seconds": EPOCH_SECONDS - 1},
            clock={"elapsed_seconds": EPOCH_SECONDS},
            transit_result={}) == ["time"]
        assert epoch_reasons(
            turn_idx=10, previous_scene=base,
            scene={"location": "Citadel"},
            previous_clock={"elapsed_seconds": EPOCH_SECONDS},
            clock={"elapsed_seconds": EPOCH_SECONDS},
            transit_result={}) == ["location"]
        assert epoch_reasons(
            turn_idx=11, previous_scene=base, scene=base,
            previous_clock={"elapsed_seconds": EPOCH_SECONDS},
            clock={"elapsed_seconds": EPOCH_SECONDS},
            transit_result={"consequences_fired": 1}) == ["due_event"]

    def test_an_opening_is_an_epoch_but_an_upgrade_is_not(self):
        assert epoch_reasons(
            turn_idx=0, previous_scene={}, scene={"location": "Harbor"},
            previous_clock={}, clock={}, transit_result={}) == ["opening"]
        assert epoch_reasons(
            turn_idx=40, previous_scene={"location": "Harbor"},
            scene={"location": "Harbor"}, previous_clock={}, clock={},
            transit_result={}) == []


class TestTheEpochTravelsWithTheTurn:
    def test_epoch_and_log_restore_with_the_turn_checkpoint(self, temp_db):
        """Both are diegetic frame state in world KV, so the foundational
        whole-state checkpoint restores them atomically without a bespoke
        side-channel serializer."""
        from persist.checkpoints import ensure_checkpoint, restore_checkpoint
        from core.db import wget, wset

        cid = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Test", "", time.time()))
        original_epoch = {"epoch_id": "epoch_before", "sequence": 2,
                          "turn": 6}
        original_log = [{"turn": 6, "seed": "epoch_before",
                         "rung": "stochastic", "events": []}]
        wset(cid, "offscreen_epoch", original_epoch)
        wset(cid, "offscreen_log", original_log)
        ensure_checkpoint(cid, 7)

        wset(cid, "offscreen_epoch", {"epoch_id": "discarded", "sequence": 3})
        wset(cid, "offscreen_log", original_log + [{"seed": "discarded"}])
        restore_checkpoint(cid, 7)

        assert wget(cid, "offscreen_epoch", {}) == original_epoch
        assert wget(cid, "offscreen_log", []) == original_log

    def test_nothing_cancels_jobs_on_turn_start(self):
        """The user's one explicit rule for out-of-band work: a turn starting
        must never cancel it, or the world's progress depends on player
        idleness (amendment 4). jobs.cancel exists for authored teardown; the
        pipeline must not call it."""
        import pathlib

        root = pathlib.Path(__file__).resolve().parents[1]
        for name in ("persist/commit.py", "web/app.py"):
            src = (root / name).read_text(encoding="utf-8")
            assert "jobs.cancel" not in src, name
        runtime = (root / "agents" / "runtime.py").read_text(encoding="utf-8")
        assert "jobs.cancel" not in runtime
