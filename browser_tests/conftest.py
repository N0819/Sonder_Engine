"""Fixtures for the opt-in, real-browser frontend tests."""

from __future__ import annotations

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest


ROOT = Path(__file__).resolve().parents[1]


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        """Keep successful asset requests out of pytest's captured output."""


@pytest.fixture(scope="session")
def ui_base_url() -> str:
    """Serve the unbundled frontend exactly as the app mounts it."""

    handler = partial(_QuietHandler, directory=str(ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
