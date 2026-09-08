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
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from web.app import SelectiveGZipMiddleware


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

    async def picture(_request):
        return Response(b"\x89PNG" + b"\x00" * 8000, media_type="image/png")

    async def bed(_request):
        return Response(b"ID3" + b"\x00" * 8000, media_type="audio/mpeg")

    async def drawing(_request):
        return Response(b"<svg>" + b"<rect/>" * 2000 + b"</svg>",
                        media_type="image/svg+xml")

    application = Starlette(routes=[
        Route("/stream", ndjson), Route("/sse", sse), Route("/blob", blob),
        Route("/picture", picture), Route("/bed", bed),
        Route("/drawing", drawing)])
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


# ------------------------------------------------------- text only (C22b)
#
# gzip is a text codec. A PNG, an MP3 and a font are already compressed, so
# deflating them buys nothing and costs the whole file's worth of CPU on the
# way out: measured at review 2026-09-07 (C22b), a 1MB backdrop PNG took 36ms
# and came out 338 bytes LARGER, a 2MB ambience bed 72ms for 658 bytes larger.
# Both routes serve one file per beat, so a reader scrolling back through a
# story's rooms paid it over and over.


@pytest.mark.parametrize("path", ["/picture", "/bed"])
def test_already_compressed_bytes_are_not_deflated_again(client, path):
    response = client.get(path, headers={"accept-encoding": "gzip"})
    assert response.headers.get("content-encoding") is None
    # and the bytes arrived whole, not merely unlabelled
    assert response.content.endswith(b"\x00" * 8000)


def test_text_wearing_an_image_type_is_still_compressed(client):
    """`image/svg+xml` is markup. The test is the type's own shape -- a
    structured text suffix -- not a list of the media the engine serves, so a
    textual type a route invents next is covered without being listed."""
    response = client.get("/drawing", headers={"accept-encoding": "gzip"})
    assert response.headers.get("content-encoding") == "gzip"


@pytest.mark.parametrize("content_type,is_text", [
    ("application/json", True),
    ("application/json; charset=utf-8", True),
    ("text/html; charset=utf-8", True),
    ("text/css", True),
    ("application/javascript", True),
    ("application/ld+json", True),
    ("image/svg+xml", True),
    ("image/png", False),
    ("image/webp", False),
    ("audio/mpeg", False),
    ("audio/ogg", False),
    ("video/mp4", False),
    ("font/woff2", False),
    ("application/zip", False),
    ("application/octet-stream", False),
    ("", False),
])
def test_the_classifier_reads_the_type_and_not_a_list_of_routes(
        content_type, is_text):
    assert SelectiveGZipMiddleware.is_text(content_type) is is_text


def test_a_client_that_cannot_decompress_is_left_alone(client):
    response = client.get("/blob", headers={"accept-encoding": "identity"})
    assert response.headers.get("content-encoding") is None
    assert len(response.json()["pad"]) == 8000


def test_the_real_turn_stream_declares_a_streamed_content_type():
    """The exclusion is keyed on this, so it is worth pinning."""
    import inspect

    from web import app as app_module

    source = inspect.getsource(app_module._stream)
    assert "application/x-ndjson" in source


# ---------------------------------------------------------------- the rewrite
#
# The first implementation wrapped Starlette's `GZipResponder` and reached for
# `.send_with_gzip`, a private attribute. `requirements.txt` declares
# `fastapi>=0.101,<1`, and that range resolves to Starlette versions where the
# attribute no longer exists -- every api request then raises AttributeError.
# CI never saw it because `constraints.txt` pins the pair; `Start Sonder.bat`
# installed `requirements.txt` WITHOUT those constraints, so the people who
# would hit it were exactly the ones running the launcher on a fresh machine.
#
# The middleware now compresses with `zlib` and owns nothing private. These
# pin the header handling that came with that, which the tests above did not
# cover because Starlette used to do it.


def test_the_middleware_owns_no_private_starlette_api():
    """The regression itself. A private attribute is a dependency on a version,
    not on a library.

    Asserted over the parsed tree rather than the source text: the comment
    above this block names the attribute in order to explain it, and a
    substring check would fail on the explanation instead of on the code.
    """
    import ast
    import pathlib

    tree = ast.parse(
        (pathlib.Path(__file__).resolve().parents[1] / "web" / "app.py")
        .read_text(encoding="utf-8"))

    used = {node.attr for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)}
    named = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    imported = {alias.name for node in ast.walk(tree)
                if isinstance(node, (ast.Import, ast.ImportFrom))
                for alias in node.names}

    assert "send_with_gzip" not in used
    assert "GZipResponder" not in named | imported


def test_content_length_is_dropped_when_the_body_is_compressed(client):
    """It describes the UNCOMPRESSED body. Left in place, the client waits for
    bytes that never come."""
    response = client.get("/blob", headers={"accept-encoding": "gzip"})
    assert response.headers.get("content-encoding") == "gzip"
    raw = response.headers.get("content-length")
    assert raw is None or int(raw) < 8000


def test_a_compressed_response_varies_on_accept_encoding(client):
    """Without it a shared cache serves gzip to a client that asked for
    identity."""
    response = client.get("/blob", headers={"accept-encoding": "gzip"})
    assert "accept-encoding" in response.headers.get("vary", "").lower()


def test_a_body_below_the_threshold_is_left_alone(client):
    """Compressing a few hundred bytes costs more than it saves, and the
    decision needs the first chunk to make -- so it is worth pinning that the
    held-back start message is still delivered."""
    application = _probe_app()

    async def small(_request):
        return JSONResponse({"ok": True})

    application.routes.append(Route("/small", small))
    with TestClient(application) as c:
        response = c.get("/small", headers={"accept-encoding": "gzip"})
    assert response.headers.get("content-encoding") is None
    assert response.json() == {"ok": True}


def test_an_already_encoded_response_is_not_compressed_twice():
    import gzip as _gzip

    from starlette.responses import Response

    async def preencoded(_request):
        return Response(_gzip.compress(b'{"pad":"' + b"x" * 8000 + b'"}'),
                        media_type="application/json",
                        headers={"content-encoding": "gzip"})

    application = Starlette(routes=[Route("/pre", preencoded)])
    application.add_middleware(SelectiveGZipMiddleware, minimum_size=2048)
    with TestClient(application) as c:
        response = c.get("/pre", headers={"accept-encoding": "gzip"})
    assert response.json()["pad"] == "x" * 8000
