"""A client that leaves mid-turn leaves the turn running and the server free.

`_stream` hands the pipeline to its own drain thread and relays its events
through a queue. Its generator's `finally` joined that thread, and when the
client disconnects Starlette closes the generator ON THE EVENT LOOP -- so the
join waited out the rest of the turn there, and every other request (other
stories, the guest's poll, `GET /`) hung until the turn committed. Measured in
the audit (web_app F1, 2026-11-01): a 2.5 s stall for a 2.8 s remainder,
against 0.09 s with no disconnect. Reloading the tab mid-turn was enough.

The run itself is unchanged: it finishes on its own thread and releases its
slot in `run_pipeline`'s own `finally`, exactly as a `_detach`ed run does.
"""
from __future__ import annotations

import asyncio
import threading
import time

from fastapi import FastAPI

#: What the generator still has to do after the client has gone.
REMAINDER_SECONDS = 2.8


def _slow_turn(finished):
    def gen():
        try:
            for i in range(15):
                time.sleep(REMAINDER_SECONDS / 14)
                yield {"type": "tick", "i": i}
        finally:
            finished.set()
    return gen()


async def _drive(asgi):
    """One request whose client goes away after the first body chunk, with a
    heartbeat on the same loop measuring the longest stall."""
    disconnect = asyncio.Event()
    gaps, stop = [], False

    async def heartbeat():
        last = time.monotonic()
        while not stop:
            await asyncio.sleep(0.05)
            now = time.monotonic()
            gaps.append(now - last)
            last = now

    beat = asyncio.create_task(heartbeat())
    sent = {"request": False, "body": False}

    async def receive():
        if not sent["request"]:
            sent["request"] = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await disconnect.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        if message["type"] == "http.response.body" and message.get("body") \
                and not sent["body"]:
            sent["body"] = True
            disconnect.set()

    scope = {"type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"},
             "http_version": "1.1", "method": "POST", "scheme": "http",
             "path": "/turn", "raw_path": b"/turn", "query_string": b"",
             "root_path": "", "headers": [], "client": ("127.0.0.1", 1),
             "server": ("127.0.0.1", 8008)}
    try:
        await asgi(scope, receive, send)
    except BaseException:  # noqa: BLE001 -- a cancelled response is the client's leaving
        pass
    # The generator is closed when its last reference goes; give that, and
    # whatever it does in its `finally`, the chance to happen on this loop.
    for _ in range(4):
        await asyncio.sleep(0.15)
        import gc
        gc.collect()
    stop = True
    await beat
    return max(gaps), sent["body"]


def test_a_disconnect_mid_turn_does_not_stall_the_event_loop():
    from web import app as app_module

    finished = threading.Event()
    asgi = FastAPI()

    @asgi.post("/turn")
    def turn():
        return app_module._stream(_slow_turn(finished))

    stall, streamed = asyncio.run(_drive(asgi))
    assert streamed, "the stream never sent its first chunk"
    assert stall < 1.0, (
        f"the event loop stalled {stall:.2f}s after the client left: the "
        "stream waited out the turn on the loop")
    # The turn itself was not abandoned: it runs to its end on its own thread.
    assert finished.wait(REMAINDER_SECONDS + 10)


def test_a_finished_stream_still_waits_for_its_thread():
    """The join stays where it costs nothing: after the run's last event,
    when the drain thread is already on its way out."""
    import inspect
    from web import app as app_module

    source = inspect.getsource(app_module._stream)
    assert "thread.join()" in source
