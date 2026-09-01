"""An abort must reach a blocked read, and must stop the next stage.

Setting the flag was only ever half of it. `_check_cancel` polls between
streamed chunks, which is no help when a connection has stopped sending --
the thread parks in a socket read, no chunk arrives, and the flag goes unseen
until the read deadline. `providers._abortable` fixed that for the two
streaming readers and left every blocking post behind, so an abort landed
instantly on some stages and hung for minutes on others.

The second half is the pipeline itself: nothing checked the flag between
steps, so a stage that had not started reading yet ran in full, and so did
the stage after it. `commit` is a step like any other, which makes that check
the guard against writing a turn the host cancelled.
"""

import threading

import pytest

from llm import providers


class _FakeResponse:
    """Stands in for a requests.Response whose body never arrives."""

    def __init__(self, released):
        self.status_code = 200
        self._released = released
        self.closed = False

    @property
    def content(self):
        # The blocking read. Returns only once the socket is closed, which is
        # what abort_live_requests does from the other thread.
        if not self._released.wait(timeout=5):
            raise AssertionError("the read was never interrupted")
        return b"{}"

    def close(self):
        self.closed = True
        self._released.set()


def test_a_blocking_post_is_registered_and_closed_by_an_abort(monkeypatch):
    released = threading.Event()
    response = _FakeResponse(released)

    class _Session:
        def post(self, *a, **kw):
            assert kw.get("stream") is True, (
                "the body must be deferred, or there is nothing to interrupt")
            return response

    monkeypatch.setattr(providers, "_session", lambda: _Session())

    ev = threading.Event()
    token = providers.cancel_event.set(ev)
    entered = threading.Event()
    failure = {}

    def caller():
        try:
            entered.set()
            providers._post_abortable("http://example.invalid/v1/chat")
        except Exception as exc:          # noqa: BLE001 -- recorded, not raised
            failure["exc"] = exc

    # The context must be COPIED into the worker, exactly as
    # runtime._stream_one/_stream_parallel do it (runtime.py:466, :532):
    # a thread starts with a fresh context, so a cancel_event set in the
    # caller is invisible inside it and nothing would ever register.
    import contextvars
    ctx = contextvars.copy_context()
    worker = threading.Thread(target=lambda: ctx.run(caller))
    worker.start()
    assert entered.wait(timeout=2)
    # The abort arrives while the read is blocked.
    ev.set()
    closed = providers.abort_live_requests(ev)
    worker.join(timeout=5)
    providers.cancel_event.reset(token)

    assert closed == 1, "the in-flight post was not registered for abort"
    assert response.closed, "abort_live_requests did not close the socket"
    assert not worker.is_alive(), "the blocked read outlived the abort"


def test_no_step_starts_once_the_flag_is_set():
    """`commit` is a step, so this is also the guard on writing a cancelled turn."""
    from agents import runtime

    ev = threading.Event()
    ev.set()
    token = providers.cancel_event.set(ev)
    try:
        with pytest.raises(providers.Aborted):
            runtime.compute_step("commit", object(), 0)
    finally:
        providers.cancel_event.reset(token)


def test_the_boundary_check_guards_the_commit_step():
    """The guard must sit before dispatch, not inside one handler."""
    import inspect

    from agents import runtime

    src = inspect.getsource(runtime)
    i = src.index("_check_cancel()")
    j = src.index("handler = STEP_HANDLERS.get(key)")
    assert i < j, "the flag must be checked before a handler is chosen"
