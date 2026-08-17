"""A turn is streamed, and compression must never buffer it.

Compression was added for the UI catalog: `/api/bootstrap` carries a full
message catalog (~190KB in Japanese) and `/api/ui` carries another, roughly
816KB per page load compressing to about a third.

Applied to the turn stream it was destructive. Starlette's `GZipResponder`
writes each streamed chunk into a `GzipFile`, and the compressor buffers
internally -- a turn's NDJSON lines are nowhere near large enough to fill it,
so nothing reached the browser until enough accumulated. Live symptoms, all
from one cause and all visible in English: the stage indicator above the input
stopped advancing, model output stopped appearing in the technical detail
pane, and the client eventually abandoned a connection that looked dead, which
the server recorded mid-turn as `Aborted: generation aborted by user`.

The rule is keyed on CONTENT TYPE, not on a list of paths, so a streaming
route added later is covered without anyone remembering to list it.
"""

from __future__ import annotations

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app import SelectiveGZipMiddleware


CHUNKS = 6


def _probe_app():
    async def ndjson(_request):
        def gen():
            for i in range(CHUNKS):
                yield b'{"type":"token","delta":"chunk %d"}\n' % i
        return StreamingResponse(gen(), media_type="application/x-ndjson")

    async def sse(_request):
        def gen():
            for i in range(CHUNKS):
                yield b"data: %d\n\n" % i
        return StreamingResponse(gen(), media_type="text/event-stream")

    async def blob(_request):
        return JSONResponse({"pad": "x" * 8000})

    application = Starlette(routes=[
        Route("/stream", ndjson), Route("/sse", sse), Route("/blob", blob)])
    application.add_middleware(SelectiveGZipMiddleware, minimum_size=2048)
    return application


@pytest.fixture
def client():
    with TestClient(_probe_app()) as c:
        yield c


@pytest.mark.parametrize("path", ["/stream", "/sse"])
def test_a_streamed_response_is_never_compressed(client, path):
    response = client.get(path, headers={"accept-encoding": "gzip"})
    assert response.headers.get("content-encoding") is None, (
        "compressing a stream buffers it: the reader sees nothing until the "
        "compressor's internal buffer fills")


def test_every_streamed_chunk_still_arrives(client):
    with client.stream("GET", "/stream",
                       headers={"accept-encoding": "gzip"}) as response:
        lines = [line for line in response.iter_lines() if line.strip()]
    assert len(lines) == CHUNKS


def test_a_large_json_body_is_still_compressed(client):
    """The reason the middleware exists at all."""
    response = client.get("/blob", headers={"accept-encoding": "gzip"})
    assert response.headers.get("content-encoding") == "gzip"
    assert len(response.json()["pad"]) == 8000


def test_a_client_that_cannot_decompress_is_left_alone(client):
    response = client.get("/blob", headers={"accept-encoding": "identity"})
    assert response.headers.get("content-encoding") is None
    assert len(response.json()["pad"]) == 8000


def test_the_real_turn_stream_declares_a_streamed_content_type():
    """The exclusion is keyed on this, so it is worth pinning."""
    import inspect

    import app as app_module

    source = inspect.getsource(app_module._stream)
    assert "application/x-ndjson" in source
