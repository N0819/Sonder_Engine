"""A turn should not need its client attached.

`POST /api/chats/{cid}/turns` streams the pipeline's events, and a client
that disconnects mid-turn leaves the run going to completion -- which is
right, and was the whole story: there was no way to SUBMIT a turn without
holding a connection open for the minutes it takes, and no way to come back
for it. `?detach=1` claims the slot, creates the turn row exactly as the
streaming path does, starts the same drain thread, and answers at once;
`GET /api/turns/{tid}/status` reads whether the run is still going from the
one registry every other route consults (`runtime.ABORTS`) and lists the
stage keys that have saved so far.

The pipeline is driven by a stub, the way `tests/test_pipeline_audit.py`
and `tests/test_abort_is_immediate.py` do it: what is under test is the
route's contract with the slot and the rows, not any stage.
"""

import threading
import time

import pytest
from fastapi.responses import StreamingResponse

from agents.runtime import ABORTS
from agents.storage import save_step
from web import app as app_module


def _make_chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Test", "", time.time()))


def _wait_until(pred, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if pred():
            return True
        time.sleep(0.02)
    return pred()


@pytest.fixture
def joined(monkeypatch):
    """Every drain thread a test starts, joined at teardown. The route
    returns before the thread does -- that is the feature -- so without
    this the thread's post-commit log line can land after pytest has
    closed its capture stream."""
    threads = []
    real = app_module._drain_on_own_thread

    def spy(gen, sink):
        thread = real(gen, sink)
        threads.append(thread)
        return thread

    monkeypatch.setattr(app_module, "_drain_on_own_thread", spy)
    yield threads
    for thread in threads:
        thread.join(timeout=5)


def _pipeline_stub(gate=None, *, keys=("director_interpret", "commit")):
    """A pipeline that saves a step per key, pausing on `gate` before the
    last one, and releases the slot in its own `finally` as the real
    `run_pipeline` does -- the stub replaces the whole generator, so the
    slot discipline is the stub's to keep."""
    def fake_run_pipeline(cid, tid, abort=None, frame_id=None, **kw):
        try:
            for i, key in enumerate(keys):
                if gate is not None and i == len(keys) - 1:
                    assert gate.wait(5), "the test never released the gate"
                save_step(tid, key, key, i, {"key": key})
                yield {"type": "step", "key": key}
        finally:
            ABORTS.pop((cid, frame_id), None)
    return fake_run_pipeline


class TestDetachedSubmit:
    def test_a_detached_turn_answers_before_the_pipeline_ends(
            self, temp_db, monkeypatch, joined):
        chat_id = _make_chat(temp_db)
        gate = threading.Event()
        monkeypatch.setattr(app_module, "run_pipeline", _pipeline_stub(gate))

        try:
            out = app_module.turn_new(chat_id, {"input": "hello"}, detach=1)
            assert out["running"] is True
            tid = out["turn_id"]
            row = temp_db.q("SELECT * FROM turns WHERE id=?", (tid,), one=True)
            assert row and row["player_input"] == "hello", (
                "the turn row is created exactly as the streaming path does")

            # Still running: the first stage saves, the last waits on us.
            assert _wait_until(lambda: app_module.turn_status(tid)["steps"])
            status = app_module.turn_status(tid)
            assert status["running"] is True
            assert status["steps"] == ["director_interpret"]
            assert status["committed"] is False
            assert (chat_id, None) in ABORTS

            gate.set()
            assert _wait_until(
                lambda: not app_module.turn_status(tid)["running"])
            status = app_module.turn_status(tid)
            assert status["steps"] == ["director_interpret", "commit"]
            assert status["committed"] is True
            assert (chat_id, None) not in ABORTS
        finally:
            gate.set()
            ABORTS.pop((chat_id, None), None)

    def test_the_body_flag_spells_it_too(self, temp_db, monkeypatch, joined):
        chat_id = _make_chat(temp_db)
        monkeypatch.setattr(app_module, "run_pipeline", _pipeline_stub())
        try:
            out = app_module.turn_new(chat_id, {"input": "hi", "detach": True})
            assert out["running"] is True
            assert _wait_until(
                lambda: app_module.turn_status(out["turn_id"])["committed"])
        finally:
            ABORTS.pop((chat_id, None), None)

    def test_the_plain_route_still_streams(self, temp_db, monkeypatch,
                                           joined):
        chat_id = _make_chat(temp_db)
        monkeypatch.setattr(app_module, "run_pipeline", _pipeline_stub())
        try:
            resp = app_module.turn_new(chat_id, {"input": "hi"})
            assert isinstance(resp, StreamingResponse)
        finally:
            ABORTS.pop((chat_id, None), None)

    def test_a_busy_frame_still_refuses_a_second_turn(self, temp_db,
                                                       monkeypatch, joined):
        from fastapi import HTTPException
        chat_id = _make_chat(temp_db)
        gate = threading.Event()
        monkeypatch.setattr(app_module, "run_pipeline", _pipeline_stub(gate))
        try:
            out = app_module.turn_new(chat_id, {"input": "one"}, detach=1)
            with pytest.raises(HTTPException) as exc:
                app_module.turn_new(chat_id, {"input": "two"}, detach=1)
            assert exc.value.status_code == 409
            gate.set()
            assert _wait_until(
                lambda: not app_module.turn_status(out["turn_id"])["running"])
        finally:
            gate.set()
            ABORTS.pop((chat_id, None), None)


class TestStatus:
    def test_an_older_turn_is_not_running_while_a_newer_one_is(self, temp_db):
        """The slot names a FRAME; the turn it is running is the frame's
        latest. An older turn asked about while a newer one runs must not
        read the busy slot as its own."""
        chat_id = _make_chat(temp_db)
        older = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) "
            "VALUES(?,0,'a',0)", (chat_id,))
        newer = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) "
            "VALUES(?,1,'b',0)", (chat_id,))
        ABORTS[(chat_id, None)] = threading.Event()
        try:
            assert app_module.turn_status(older)["running"] is False
            assert app_module.turn_status(newer)["running"] is True
        finally:
            ABORTS.pop((chat_id, None), None)
        assert app_module.turn_status(newer)["running"] is False

    def test_an_unknown_turn_is_404(self, temp_db):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            app_module.turn_status(999999)
        assert exc.value.status_code == 404


@pytest.fixture
def host_client(temp_db):
    from fastapi.testclient import TestClient
    from web import guest_access as guest

    with TestClient(app_module.app) as client:
        r = client.post("/api/auth/setup",
                        json={"username": "host", "password": "pw12345"})
        assert r.status_code == 200, r.text
        yield client
    guest.reset_host_account()
    guest._join_attempts.clear()
    guest._login_attempts.clear()


class TestOverHttp:
    def test_the_query_flag_and_the_status_route(self, host_client, temp_db,
                                                 monkeypatch, joined):
        chat_id = _make_chat(temp_db)
        monkeypatch.setattr(app_module, "run_pipeline", _pipeline_stub())
        try:
            r = host_client.post(f"/api/chats/{chat_id}/turns?detach=1",
                                 json={"input": "hello"})
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["running"] is True and body["turn_id"]
            tid = body["turn_id"]
            assert _wait_until(
                lambda: host_client.get(f"/api/turns/{tid}/status")
                .json()["committed"])
            status = host_client.get(f"/api/turns/{tid}/status").json()
            assert status["running"] is False
            assert status["steps"] == ["director_interpret", "commit"]
        finally:
            ABORTS.pop((chat_id, None), None)
