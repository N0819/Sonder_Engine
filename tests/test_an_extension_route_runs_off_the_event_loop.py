"""An extension's own route runs on the threadpool, never on the event loop.

`extension_route` is `async def` -- it has to `await request.json()` -- and it
called the synchronous `extension_runtime.dispatch_route` directly, so the
extension's handler ran ON the event loop. FastAPI moves only `def` endpoints
to the threadpool. A handler doing real work (`api.provision_story`'s whole
archive import, `api.generate_lived_location`, "minutes, not seconds") held
every other request, the turn stream included, for as long as it ran (audit
2026-11-01, web_app F5 / web_routes_extensions F20).
"""
from __future__ import annotations

import asyncio
import time

from fastapi import FastAPI

#: How long the extension's handler works.
HANDLER_SECONDS = 1.0


async def _call(asgi, method, path, body=b""):
    gaps, stop = [], False

    async def heartbeat():
        last = time.monotonic()
        while not stop:
            await asyncio.sleep(0.05)
            now = time.monotonic()
            gaps.append(now - last)
            last = now

    beat = asyncio.create_task(heartbeat())
    await asyncio.sleep(0.06)
    sent, out = {"request": False}, {"status": None, "body": b""}

    async def receive():
        if not sent["request"]:
            sent["request"] = True
            return {"type": "http.request", "body": body, "more_body": False}
        await asyncio.sleep(3600)

    async def send(message):
        if message["type"] == "http.response.start":
            out["status"] = message["status"]
        elif message["type"] == "http.response.body":
            out["body"] += message.get("body", b"")

    scope = {"type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"},
             "http_version": "1.1", "method": method, "scheme": "http",
             "path": path, "raw_path": path.encode(), "query_string": b"",
             "root_path": "", "headers": [(b"content-type", b"application/json")],
             "client": ("127.0.0.1", 1), "server": ("127.0.0.1", 8008)}
    await asgi(scope, receive, send)
    await asyncio.sleep(0.1)
    stop = True
    await beat
    return max(gaps), out


def test_a_slow_extension_handler_leaves_the_loop_free(monkeypatch):
    import extension_runtime
    from web import app as app_module

    seen = {}

    def slow_dispatch(ext_id, method, path, query=None, body=None):
        time.sleep(HANDLER_SECONDS)
        seen.update(ext_id=ext_id, method=method, path=path, body=body)
        return {"ok": True}

    monkeypatch.setattr(extension_runtime, "dispatch_route", slow_dispatch)
    asgi = FastAPI()
    asgi.add_api_route("/api/extensions/{eid}/x/{path:path}",
                       app_module.extension_route, methods=["GET", "POST"])

    stall, out = asyncio.run(_call(asgi, "POST", "/api/extensions/demo-ext/x/start",
                                   body=b'{"go": 1}'))
    assert out["status"] == 200 and b'"ok":true' in out["body"]
    assert seen == {"ext_id": "demo-ext", "method": "POST", "path": "start",
                    "body": {"go": 1}}
    assert stall < HANDLER_SECONDS / 2, (
        f"the event loop stalled {stall:.2f}s while the extension's handler ran")


def test_an_extensions_refusal_still_maps_to_its_status(monkeypatch):
    import extension_runtime
    from web import app as app_module

    def refuse(*_a, **_k):
        raise extension_runtime.ExtensionError("extension 'demo-ext' is not enabled")

    monkeypatch.setattr(extension_runtime, "dispatch_route", refuse)
    asgi = FastAPI()
    asgi.add_api_route("/api/extensions/{eid}/x/{path:path}",
                       app_module.extension_route, methods=["GET"])
    _stall, out = asyncio.run(_call(asgi, "GET", "/api/extensions/demo-ext/x/ping"))
    assert out["status"] == 404 and b"not enabled" in out["body"]
