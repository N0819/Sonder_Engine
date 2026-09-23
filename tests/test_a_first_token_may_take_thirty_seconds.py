"""A provider reading a prompt is not a provider that stopped.

The owner's silence rule (2026-09-14) is `PROVIDER_SILENCE_SECONDS`, 10: a
stream that sends neither a reasoning fragment nor a content token for that
long is unresponsive. It was one number for two different silences. Before the
first token a model is reading its prompt -- a large one on a reasoning model
takes a little over ten seconds -- and after it a stream that stops is a
stream that stopped.

Measured on the playerless Aldermill runs (2026-09-23): the whole-call
failures of round 6 were both first-token silences ("provider silent for 10s
(before any token)" on a director_specialist, and a socket "Read timed out.
(read timeout=10.0)" on a character_kernel), and the cut-and-retry cycles
before them cost about 370 s of a run with nothing in any log. The owner's
split (2026-09-23): thirty seconds before the first token, ten between.

The socket's own read deadline had to move with it: `REQUEST_TIMEOUT`'s read
half was the same 10, so raising only the activity clock would still have cut
a slow first token at 10. Once the first token arrives the socket is narrowed
back to the clock's limit, so a stream that goes completely quiet -- no
keepalive the clock could count -- still dies in ten.
"""
from __future__ import annotations

import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from llm import providers


def test_the_two_silences_have_two_limits():
    clock = providers._ActivityClock(limit=providers.silence_limit_override.get())
    assert clock.limit == providers.PROVIDER_SILENCE_SECONDS == 10.0
    assert clock.first == providers.PROVIDER_FIRST_TOKEN_SECONDS == 30.0


def test_the_socket_waits_as_long_as_a_first_token_may_take():
    assert providers.REQUEST_TIMEOUT[1] == providers.PROVIDER_FIRST_TOKEN_SECONDS


def test_before_the_first_token_thirty_seconds_is_not_silence():
    now = [0.0]
    clock = providers._ActivityClock(now=lambda: now[0])
    now[0] = 25.0
    clock.tick()                                   # reading the prompt
    now[0] = 31.0
    with pytest.raises(providers.ProviderSilent, match="before any token"):
        clock.tick()


def test_after_the_first_token_ten_seconds_is():
    now = [0.0]
    clock = providers._ActivityClock(now=lambda: now[0])
    now[0] = 20.0
    clock.tick(content="{")                        # the stream has begun
    now[0] = 29.0
    clock.tick()
    now[0] = 30.5
    with pytest.raises(providers.ProviderSilent, match="after 0 chars of reasoning and 1 of content"):
        clock.tick()


def test_a_patient_caller_is_patient_before_and_after():
    with providers.patient_stream(180):
        clock = providers._ActivityClock(limit=providers.silence_limit_override.get())
    assert clock.limit == 180.0 and clock.first == 180.0


# ---- the same rule on a real socket -----------------------------------------

def _serve(script):
    """A local SSE endpoint that plays `script`: ("sleep", s) | ("line", bytes).
    Chunked, as a provider's stream is: each line is its own chunk and arrives
    when it is written, not when a read buffer fills."""

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
    server.block_on_close = False     # a handler mid-sleep is abandoned, not joined
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def _stop(server):
    server.shutdown()
    server.server_close()


def _content(text):
    import json
    return ("data: %s\n\n" % json.dumps(
        {"choices": [{"delta": {"content": text}}]})).encode()


@pytest.fixture
def short_limits(monkeypatch):
    """The real rule at a test's scale: 3s before the first token, 0.5s after."""
    monkeypatch.setattr(providers, "PROVIDER_SILENCE_SECONDS", 0.5)
    monkeypatch.setattr(providers, "PROVIDER_FIRST_TOKEN_SECONDS", 3.0)
    monkeypatch.setattr(providers, "REQUEST_TIMEOUT", (5, 3.0))


def _stream(server):
    url = "http://127.0.0.1:%d/v1/chat/completions" % server.server_address[1]
    return providers._sse_openai(url, {}, {"model": "m", "messages": []},
                                 lambda _piece: None)


def test_a_slow_first_token_is_waited_for(short_limits):
    server = _serve([("sleep", 1.5), ("line", _content('{"ok": ')),
                     ("line", _content("true}")), ("line", b"data: [DONE]\n\n")])
    try:
        assert _stream(server) == '{"ok": true}'
    finally:
        _stop(server)


def test_a_stream_that_stops_dead_after_its_first_token_dies_at_the_short_limit(short_limits):
    """No keepalive at all, so only the socket can notice -- and it must notice
    at the between-token limit, not the first-token one."""
    server = _serve([("line", _content('{"ok": ')), ("sleep", 4.0),
                     ("line", _content("true}")), ("line", b"data: [DONE]\n\n")])
    started = time.monotonic()
    try:
        with pytest.raises((providers.ProviderSilent,) + providers._RETRYABLE_NETWORK):
            _stream(server)
        assert time.monotonic() - started < 2.0
    finally:
        _stop(server)


def test_keepalives_after_the_first_token_are_not_activity(short_limits):
    keepalives = [("line", b": keepalive\n\n"), ("sleep", 0.2)] * 10
    server = _serve([("line", _content('{"ok": '))] + keepalives
                    + [("line", _content("true}")), ("line", b"data: [DONE]\n\n")])
    try:
        with pytest.raises(providers.ProviderSilent, match="after"):
            _stream(server)
    finally:
        _stop(server)
