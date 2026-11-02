"""A caller that asks for patience gets it from the socket AND the clock.

A streamed read has two deadlines: the socket's (how long a read may block)
and the activity clock's (how long the provider may send nothing but
keepalives). `request_timeout` raised only the socket and `patient_stream`
only the clock, so neither long-work caller got what it asked for: under
`request_timeout(600)` -- the lorebook generator's knob, AGENTS.md:554 -- a
slow local model's first token at 45 s was killed by the clock the moment it
arrived ("provider silent for 45s (before any token)"), and under
`patient_stream(180)` -- the location pass -- a host that thinks with no
keepalive still lost its socket at 30 s (review 2026-11-01,
llm_providers_quality F7). `_between_tokens_limit`'s own docstring said the
deadline was "never shorter than either" knob.

One function now gives both deadlines from both overrides, and the socket
and the clock read the same pair. With neither knob set nothing moves: 30 s
before the first token, 10 s between (the owner's 2026-09-23 split).
"""
from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from llm import providers


def test_with_no_knob_the_owner_s_split_stands():
    assert providers._stream_deadlines(None, None) == (
        providers.PROVIDER_FIRST_TOKEN_SECONDS, providers.PROVIDER_SILENCE_SECONDS)


def test_either_knob_raises_both_deadlines():
    assert providers._stream_deadlines(None, 600.0) == (600.0, 600.0)
    assert providers._stream_deadlines(180.0, None) == (180.0, 180.0)
    assert providers._stream_deadlines(180.0, 600.0) == (600.0, 600.0)
    # Never SHORTER than the defaults, whichever knob is small.
    assert providers._stream_deadlines(5.0, None) == (
        providers.PROVIDER_FIRST_TOKEN_SECONDS, providers.PROVIDER_SILENCE_SECONDS)


def _serve(script):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length") or 0))
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Transfer-Encoding", "chunked")
            self.send_header("Connection", "close")
            self.end_headers()
            try:
                for kind, value in script:
                    if kind == "sleep":
                        time.sleep(value)
                    else:
                        self.wfile.write(b"%x\r\n%s\r\n" % (len(value), value))
                        self.wfile.flush()
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()
            except OSError:
                pass

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    server.block_on_close = False
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def _content(text):
    return ("data: %s\n\n" % json.dumps(
        {"choices": [{"delta": {"content": text}}]})).encode()


@pytest.fixture
def short_limits(monkeypatch):
    """The real rule at a test's scale: 0.5 s before the first token, 0.2 s
    after, and a read override allowed down to 0.1 s."""
    monkeypatch.setattr(providers, "PROVIDER_SILENCE_SECONDS", 0.2)
    monkeypatch.setattr(providers, "PROVIDER_FIRST_TOKEN_SECONDS", 0.5)
    monkeypatch.setattr(providers, "REQUEST_TIMEOUT", (5, 0.5))
    monkeypatch.setattr(providers, "READ_TIMEOUT_MIN", 0.1)


def _stream(server):
    url = "http://127.0.0.1:%d/v1/chat/completions" % server.server_address[1]
    return providers._sse_openai(url, {}, {"model": "m", "messages": []},
                                 lambda _piece: None)


SLOW_FIRST_TOKEN = [("sleep", 1.0), ("line", _content('{"ok": ')),
                    ("line", _content("true}")), ("line", b"data: [DONE]\n\n")]


def test_a_longer_read_lets_a_slow_first_token_through_the_clock(short_limits):
    server = _serve(SLOW_FIRST_TOKEN)
    try:
        with providers.request_timeout(2.0):
            assert _stream(server) == '{"ok": true}'
    finally:
        server.shutdown()
        server.server_close()


def test_patience_lets_a_slow_first_token_through_the_socket(short_limits):
    server = _serve(SLOW_FIRST_TOKEN)
    try:
        with providers.patient_stream(2.0):
            assert _stream(server) == '{"ok": true}'
    finally:
        server.shutdown()
        server.server_close()


def test_without_either_the_same_silence_is_still_cut(short_limits):
    server = _serve(SLOW_FIRST_TOKEN)
    try:
        with pytest.raises(Exception) as err:
            _stream(server)
        assert isinstance(err.value, (providers.ProviderSilent,)
                          + providers._RETRYABLE_NETWORK)
    finally:
        server.shutdown()
        server.server_close()
