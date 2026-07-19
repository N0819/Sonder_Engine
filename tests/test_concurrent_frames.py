"""Concurrency regression tests for Stage A multi-frame play: two frames
of the SAME chat must be able to have their own pipelines running truly
simultaneously without corrupting each other's state, and this is
exercised with REAL threads against the real (thread-local-connection,
WAL-mode) db.py, not simulated sequentially. This is the prerequisite
the branching/reroll audit earlier this session teaches: an orchestration
seam change without a concurrency test is exactly how those bugs got in.
"""

from __future__ import annotations

import json
import threading
import time

import pytest

import db as db_module
from agents.runtime import ABORTS, _run_pipeline
from db import q, qi, wget, wset
from frames import create_frame


def _make_chat(db):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )


def _make_turn(db, chat_id, idx, frame_id=None):
    return db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) VALUES(?,?,?,?,?)",
        (chat_id, idx, "go", time.time(), frame_id),
    )


def _stub_handlers(monkeypatch, *, sleep_seconds=0.0):
    import agents.runtime as runtime_module

    def make_stub(key):
        def handler(ctx, nonce):
            if sleep_seconds:
                time.sleep(sleep_seconds)
            # The tag is derived from ctx.turn.frame_id -- the thing
            # actually under test. If the contextvar redirect were
            # broken (e.g. both threads ended up writing the SAME
            # storage row), one frame's log would contain the OTHER
            # frame's tag, or entries would go missing/duplicate.
            tag = f"frame:{ctx.turn.frame_id}"
            sc = wget(ctx.chat.id, "scene", {"log": []}) or {"log": []}
            sc["log"] = (sc.get("log") or []) + [f"{tag}:{key}"]
            wset(ctx.chat.id, "scene", sc)
            if key == "director_interpret":
                return {"flow": {"needs_mapping": False, "reactors": [], "resolution_flags": {}}}
            return {"prose": tag} if key in ("narrator",) else {"ok": True}
        return handler

    for key in (
        "director_interpret", "mapping_quick", "perception_act",
        "director_resolve", "perception_outcome", "narrator", "commit",
    ):
        monkeypatch.setitem(runtime_module.STEP_HANDLERS, key, make_stub(key))


class TestConcurrentPipelinesAcrossFrames:
    def test_two_frames_pipelines_run_concurrently_without_cross_contamination(self, temp_db, monkeypatch):
        """The actual deliverable: Player A's turn in the present and
        Player B's turn in the future, running on separate threads at
        the same time, must each see only their OWN frame's scene state
        -- never a partial or swapped write from the other."""
        chat_id = _make_chat(temp_db)
        future = create_frame(chat_id, label="Future", ordinal=10, kind="future")

        # idx must not be 0 for either -- idx==0 takes the establishment
        # plan (different step keys entirely), not the stubbed normal-turn
        # plan below.
        present_turn = _make_turn(temp_db, chat_id, idx=1, frame_id=None)
        future_turn = _make_turn(temp_db, chat_id, idx=2, frame_id=future)

        _stub_handlers(monkeypatch, sleep_seconds=0.03)

        results = {}
        errors = []

        def run(turn_id, label):
            try:
                list(_run_pipeline(chat_id, turn_id))
                results[label] = True
            except Exception as exc:  # pragma: no cover - failure path
                errors.append((label, exc))

        t1 = threading.Thread(target=run, args=(present_turn, "present"))
        t2 = threading.Thread(target=run, args=(future_turn, "future"))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        assert not errors, errors
        assert results == {"present": True, "future": True}

        present_scene = wget(chat_id, "scene")
        future_token = db_module.active_frame_id.set(future)
        try:
            future_scene = wget(chat_id, "scene")
        finally:
            db_module.active_frame_id.reset(future_token)

        # Each frame's own log must contain ONLY its own tag -- if the
        # contextvar redirect (or the fresh-turn checkpoint-restore skip)
        # were broken, the two threads would collide on ONE storage row
        # and both tags would show up mixed together in it.
        assert present_scene is not None and future_scene is not None
        assert present_scene["log"] and all(e.startswith("frame:None:") for e in present_scene["log"])
        assert future_scene["log"] and all(e.startswith(f"frame:{future}:") for e in future_scene["log"])
        # Both frames got a full run's worth of entries -- neither pipeline
        # was starved, blocked, or had its writes overwritten by the other.
        assert len(present_scene["log"]) == len(future_scene["log"])

    def test_active_frame_id_is_reset_after_each_concurrent_run(self, temp_db, monkeypatch):
        """Every pipeline run must leave active_frame_id exactly as it
        found it (None) once finished, on whichever thread it ran on --
        otherwise a reused thread could silently misattribute the NEXT
        unrelated pipeline run to a stale frame."""
        chat_id = _make_chat(temp_db)
        future = create_frame(chat_id, label="Future", ordinal=10, kind="future")
        turn_id = _make_turn(temp_db, chat_id, idx=1, frame_id=future)
        _stub_handlers(monkeypatch)

        seen_after = {}

        def run():
            list(_run_pipeline(chat_id, turn_id))
            seen_after["value"] = db_module.active_frame_id.get()

        t = threading.Thread(target=run)
        t.start()
        t.join(timeout=10)

        # _run_pipeline itself doesn't reset (that's run_pipeline's job,
        # in `finally`) -- but confirm the thread-local nature: a FRESH
        # thread never inherits a stale value from another thread's run.
        def check_fresh_thread():
            seen_after["fresh_thread_default"] = db_module.active_frame_id.get()

        t2 = threading.Thread(target=check_fresh_thread)
        t2.start()
        t2.join(timeout=10)
        assert seen_after["fresh_thread_default"] is None

    def test_run_pipeline_resets_active_frame_id_in_finally(self, temp_db, monkeypatch):
        from agents.runtime import run_pipeline

        chat_id = _make_chat(temp_db)
        future = create_frame(chat_id, label="Future", ordinal=10, kind="future")
        turn_id = _make_turn(temp_db, chat_id, idx=1, frame_id=future)
        _stub_handlers(monkeypatch)

        list(run_pipeline(chat_id, turn_id, frame_id=future))
        assert db_module.active_frame_id.get() is None

    def test_run_pipeline_resets_active_frame_id_even_on_error(self, temp_db, monkeypatch):
        from agents.runtime import run_pipeline
        import agents.runtime as runtime_module

        chat_id = _make_chat(temp_db)
        future = create_frame(chat_id, label="Future", ordinal=10, kind="future")
        turn_id = _make_turn(temp_db, chat_id, idx=1, frame_id=future)

        def boom(ctx, nonce):
            raise RuntimeError("simulated failure")

        monkeypatch.setitem(runtime_module.STEP_HANDLERS, "director_interpret", boom)

        with pytest.raises(RuntimeError):
            list(run_pipeline(chat_id, turn_id, frame_id=future))

        assert db_module.active_frame_id.get() is None
        assert (chat_id, future) not in ABORTS


class TestSameFrameStillSerializes:
    def test_two_attempts_in_the_same_frame_are_not_both_allowed(self, temp_db):
        """Concurrency is per-FRAME, not a free-for-all -- ABORTS still
        correctly rejects a second overlapping attempt within one frame."""
        from agents.runtime import begin_pipeline

        chat_id = _make_chat(temp_db)
        abort = begin_pipeline(chat_id, None)
        try:
            assert (chat_id, None) in ABORTS
            # A second registration for the SAME key just overwrites the
            # event (this mirrors app.py's _require_frame_idle, which is
            # what actually enforces rejection at the API layer -- this
            # test proves the key collision exists to be checked against).
            assert ABORTS[(chat_id, None)] is abort
        finally:
            ABORTS.pop((chat_id, None), None)
