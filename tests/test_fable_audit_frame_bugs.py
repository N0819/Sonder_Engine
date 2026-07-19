"""Regression tests for three interacting bugs Fable's whole-codebase
audit found in the temporal-frames concurrency machinery -- all three
were invisible to the existing test suite because every prior test drove
the pipeline via direct `for event in _run_pipeline(...)` iteration,
which never exercises the code paths where they actually bite:

B1 -- `active_frame_id`/`cancel_event` set inside run_pipeline's
generator body did not survive Starlette's real StreamingResponse
machinery. Starlette drives a sync generator's `next()` calls through
`anyio.to_thread.run_sync`, which copies a FRESH context for every
single call -- so a `.set()` made before the first yield was invisible
by the second yield onward. Every step after step_start ran with
active_frame_id=None, meaning a "future" turn actually read/wrote the
PRESENT's scene/known/relationships. Fixed in app.py's `_stream` by
draining the pipeline generator to completion on one dedicated thread
with one stable context, instead of handing it to StreamingResponse
directly.

B2 -- `restore_checkpoint` iterates already-fully-resolved storage keys
(pulled straight from the `world` table's own key column, suffix and
all) through `wset`, which re-applies frame-scoping on top. Mid a
framed turn's recompute (active_frame_id already set to that frame),
this silently re-scoped the present's bare "scene" key into the frame's
suffixed slot, wiping the present's world state on every reroll of a
framed turn. Fixed by forcing active_frame_id to None for the whole
restore.

B3 -- turn_reroll/turn_rerun/turn_resume/step_reroll registered the
pipeline under `(chat_id, None)` regardless of the turn's own frame_id,
so aborting or idle-checking a framed turn's recompute operated on the
wrong ABORTS key. Fixed by threading turn["frame_id"] through
begin_pipeline/run_pipeline in all four endpoints.
"""

from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient

import app as app_module
import guest_access as guest
from agents.runtime import ABORTS
from checkpoints import ensure_checkpoint, restore_checkpoint
from db import active_frame_id, wget, wset
from frames import create_frame


@pytest.fixture
def client(temp_db):
    guest._join_attempts.clear()
    with TestClient(app_module.app) as c:
        yield c


def _host_client(client):
    # TestClient startup may already have minted the one-time bootstrap
    # secret. Reset explicitly so this helper owns the plaintext it uses.
    secret = guest.reset_host_secret()
    r = client.get(f"/?host={secret}")
    assert r.status_code in (200, 307, 302)
    return client


def _make_chat(db):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )


def _stub_step_handlers(monkeypatch):
    import agents.runtime as runtime_module

    def make_stub(key):
        def handler(ctx, nonce):
            tag = f"frame:{ctx.turn.frame_id}"
            sc = wget(ctx.chat.id, "scene", {"log": []}) or {"log": []}
            sc["log"] = (sc.get("log") or []) + [f"{tag}:{key}"]
            wset(ctx.chat.id, "scene", sc)
            if key == "director_interpret":
                return {"flow": {"needs_mapping": False, "reactors": [], "resolution_flags": {}}}
            return {"prose": tag} if key == "narrator" else {"ok": True}
        return handler

    for key in (
        "director_interpret", "mapping_quick", "perception_act",
        "director_resolve", "perception_outcome", "narrator", "commit",
    ):
        monkeypatch.setitem(runtime_module.STEP_HANDLERS, key, make_stub(key))


class TestFrameScopingSurvivesRealHTTPStreaming:
    def test_a_framed_turn_writes_into_its_own_scoped_scene_over_real_http(
        self, temp_db, client, monkeypatch
    ):
        _host_client(client)
        chat_id = _make_chat(temp_db)
        # A real present-frame turn at idx 0 first, so the frame turn
        # below lands at idx 1 and takes the NORMAL plan, not the
        # establishment plan (different step keys entirely).
        temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
            (chat_id, 0, "start", time.time()),
        )
        future = create_frame(chat_id, label="Future", ordinal=10, kind="future")
        _stub_step_handlers(monkeypatch)

        resp = client.post(
            f"/api/chats/{chat_id}/turns",
            json={"input": "go", "frame_id": future},
        )
        assert resp.status_code == 200
        events = [json.loads(line) for line in resp.text.strip().splitlines() if line]
        assert not any(e.get("type") == "error" for e in events), events
        assert any(e.get("type") == "done" for e in events), events

        present_scene = wget(chat_id, "scene")
        token = active_frame_id.set(future)
        try:
            future_scene = wget(chat_id, "scene")
        finally:
            active_frame_id.reset(token)

        # Before the fix: every step after step_start ran with
        # active_frame_id=None, so ALL of these writes landed in the
        # present's "scene" row instead -- present_scene would be
        # non-empty and future_scene would be missing/empty.
        assert present_scene is None or not present_scene.get("log")
        assert future_scene and future_scene["log"]
        assert all(e.startswith(f"frame:{future}:") for e in future_scene["log"])
        assert any(e.endswith(":commit") for e in future_scene["log"])


class TestCheckpointRestoreDoesNotLeakAcrossFrames:
    def test_restoring_mid_a_framed_turn_does_not_clobber_the_present(self, temp_db):
        chat_id = _make_chat(temp_db)
        wset(chat_id, "scene", {"log": ["present original"]})
        future = create_frame(chat_id, label="Future", ordinal=10, kind="future")

        token = active_frame_id.set(future)
        try:
            wset(chat_id, "scene", {"log": ["future original"]})
        finally:
            active_frame_id.reset(token)

        temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) VALUES(?,?,?,?,?)",
            (chat_id, 1, "go", time.time(), future),
        )
        ensure_checkpoint(chat_id, 1)

        # Simulate _run_pipeline's real sequencing for a framed turn's
        # recompute: active_frame_id is already set to the turn's frame
        # BEFORE restore_checkpoint runs.
        token = active_frame_id.set(future)
        try:
            restore_checkpoint(chat_id, 1)
        finally:
            active_frame_id.reset(token)

        present_scene = wget(chat_id, "scene")
        token = active_frame_id.set(future)
        try:
            future_scene = wget(chat_id, "scene")
        finally:
            active_frame_id.reset(token)

        # Before the fix: wset(chat_id, "scene", <present's value>) got
        # re-scoped to the frame's slot mid-restore, so the present's
        # row came back empty/missing and the frame's slot held a
        # mixed/overwritten value depending on dict iteration order.
        assert present_scene == {"log": ["present original"]}
        assert future_scene == {"log": ["future original"]}


class TestRecomputeEndpointsUseTheTurnsOwnFrame:
    """B3: reroll/rerun/resume/step-reroll must register (and abort-check)
    under the TURN's own frame_id, not unconditionally (chat_id, None)."""

    def _make_framed_turn(self, db, chat_id, future, idx=1):
        return db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) VALUES(?,?,?,?,?)",
            (chat_id, idx, "go", time.time(), future),
        )

    def _spy_run_pipeline(self, monkeypatch):
        calls = []

        def fake_run_pipeline(*args, **kwargs):
            calls.append((args, kwargs))
            return iter(())

        monkeypatch.setattr(app_module, "run_pipeline", fake_run_pipeline)
        return calls

    def test_reroll_registers_under_the_turns_frame(self, temp_db, monkeypatch):
        chat_id = _make_chat(temp_db)
        future = create_frame(chat_id, label="Future", ordinal=10, kind="future")
        temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) VALUES(?,?,?,?,?)",
            (chat_id, 0, "start", time.time(), future),
        )
        calls = self._spy_run_pipeline(monkeypatch)

        turn = temp_db.q("SELECT * FROM turns WHERE chat_id=?", (chat_id,), one=True)
        try:
            app_module.turn_reroll(turn["id"])
            assert (chat_id, future) in ABORTS
            assert calls[-1][1]["frame_id"] == future
        finally:
            ABORTS.pop((chat_id, future), None)

    def test_rerun_registers_under_the_turns_frame(self, temp_db, monkeypatch):
        chat_id = _make_chat(temp_db)
        future = create_frame(chat_id, label="Future", ordinal=10, kind="future")
        temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) VALUES(?,?,?,?,?)",
            (chat_id, 0, "start", time.time(), future),
        )
        calls = self._spy_run_pipeline(monkeypatch)

        turn = temp_db.q("SELECT * FROM turns WHERE chat_id=?", (chat_id,), one=True)
        try:
            app_module.turn_rerun(turn["id"], {})
            assert (chat_id, future) in ABORTS
            assert calls[-1][1]["frame_id"] == future
        finally:
            ABORTS.pop((chat_id, future), None)

    def test_resume_registers_under_the_turns_frame(self, temp_db, monkeypatch):
        chat_id = _make_chat(temp_db)
        future = create_frame(chat_id, label="Future", ordinal=10, kind="future")
        temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) VALUES(?,?,?,?,?)",
            (chat_id, 0, "start", time.time(), future),
        )
        calls = self._spy_run_pipeline(monkeypatch)
        import agents
        monkeypatch.setattr(agents, "resume_key_for_turn", lambda *a, **k: "director_interpret")

        turn = temp_db.q("SELECT * FROM turns WHERE chat_id=?", (chat_id,), one=True)
        try:
            app_module.turn_resume(turn["id"])
            assert (chat_id, future) in ABORTS
            assert calls[-1][1]["frame_id"] == future
        finally:
            ABORTS.pop((chat_id, future), None)

    def test_step_reroll_registers_under_the_turns_frame(self, temp_db, monkeypatch):
        chat_id = _make_chat(temp_db)
        future = create_frame(chat_id, label="Future", ordinal=10, kind="future")
        turn_id = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) VALUES(?,?,?,?,?)",
            (chat_id, 0, "start", time.time(), future),
        )
        step_id = temp_db.qi(
            "INSERT INTO steps(turn_id,key,label,ord,stale) VALUES(?,?,?,?,0)",
            (turn_id, "narrator", "Narrator", 0),
        )
        calls = self._spy_run_pipeline(monkeypatch)

        try:
            app_module.step_reroll(step_id)
            assert (chat_id, future) in ABORTS
            assert calls[-1][1]["frame_id"] == future
        finally:
            ABORTS.pop((chat_id, future), None)
