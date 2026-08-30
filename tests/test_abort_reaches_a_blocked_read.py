"""An abort has to reach a read that is not receiving anything.

`_check_cancel` is polled between streamed chunks. That is the right place and
it is enough whenever chunks keep arriving. It is no help for the case that
actually strands a session: a connection that has stopped sending. `iter_lines`
blocks inside a socket read, no chunk arrives, the poll never runs, and the
flag the abort set is invisible until `REQUEST_TIMEOUT`'s read deadline --
300 seconds. A turn cancelled in its first second still held the pipeline for
five minutes, which is why force-killing the server was the faster way out.

So the abort closes the socket as well as setting the flag.
"""
import threading
import time

import pytest
import requests.exceptions as _req_exc

from llm import providers


class _FakeResponse:
    def __init__(self):
        self.closed = threading.Event()

    def close(self):
        self.closed.set()


class TestAbortClosesWhatIsBlocked:
    def test_a_live_response_is_closed_by_the_abort(self):
        ev = threading.Event()
        token = providers.cancel_event.set(ev)
        response = _FakeResponse()
        try:
            with providers._abortable(response):
                assert providers.abort_live_requests(ev) == 1
                assert response.closed.is_set()
        finally:
            providers.cancel_event.reset(token)

    def test_it_reaches_a_thread_blocked_on_the_read(self):
        """The property that matters: another thread calls abort, and the one
        parked in the read comes back rather than waiting out the deadline."""
        ev = threading.Event()
        response = _FakeResponse()
        started, finished = threading.Event(), threading.Event()

        def reader():
            providers.cancel_event.set(ev)
            with providers._abortable(response):
                started.set()
                # Stands in for a blocking socket read: returns only when the
                # response is closed under it.
                response.closed.wait(timeout=5)
            finished.set()

        thread = threading.Thread(target=reader)
        thread.start()
        assert started.wait(timeout=2)
        ev.set()
        providers.abort_live_requests(ev)
        assert finished.wait(timeout=2), "the blocked reader was never released"
        thread.join(timeout=2)

    def test_an_abort_that_lands_before_the_first_read_still_stops_it(self):
        """Set between registration and the first chunk, the old poll would
        not run until a chunk arrived -- and none is coming."""
        ev = threading.Event()
        ev.set()
        token = providers.cancel_event.set(ev)
        response = _FakeResponse()
        try:
            with pytest.raises(providers.Aborted):
                with providers._abortable(response):
                    pytest.fail("the read should never have begun")
            assert response.closed.is_set()
        finally:
            providers.cancel_event.reset(token)

    def test_it_touches_no_other_run(self):
        """Keyed by the cancel event, so one chat's abort cannot close the
        sockets of a chat running beside it."""
        mine, theirs = threading.Event(), threading.Event()
        ours, others = _FakeResponse(), _FakeResponse()
        t1 = providers.cancel_event.set(mine)
        try:
            with providers._abortable(ours):
                providers.cancel_event.reset(t1)
                t2 = providers.cancel_event.set(theirs)
                with providers._abortable(others):
                    assert providers.abort_live_requests(mine) == 1
                    assert ours.closed.is_set()
                    assert not others.closed.is_set()
                providers.cancel_event.reset(t2)
                t1 = providers.cancel_event.set(mine)
        finally:
            providers.cancel_event.reset(t1)

    def test_the_registry_empties_itself(self):
        """A run that finishes normally must leave nothing behind: this dict
        is keyed by a long-lived Event and would otherwise hold responses for
        the life of the process."""
        ev = threading.Event()
        token = providers.cancel_event.set(ev)
        try:
            with providers._abortable(_FakeResponse()):
                assert providers._LIVE_REQUESTS.get(ev)
            assert ev not in providers._LIVE_REQUESTS
        finally:
            providers.cancel_event.reset(token)

    def test_no_cancel_event_is_not_an_error(self):
        """Tools, scripts and the charter call the providers with no pipeline
        around them."""
        response = _FakeResponse()
        with providers._abortable(response):
            pass
        assert not response.closed.is_set()
        assert providers.abort_live_requests(None) == 0


class TestAnAbortIsNotATransportFault:
    """Closing the socket surfaces as an ordinary connection error, which
    every rule in the retry loop calls retryable. On any attempt but the last
    that costs nothing -- the backoff checks for cancellation before it sleeps.
    On the LAST attempt `_should_retry` is False and the connection error
    becomes the call's outcome, so the caller sees a network failure where the
    user pressed stop, and may spend a repair call on it."""

    @staticmethod
    def _stub_role(monkeypatch):
        """A configured role, without a provider table: the loop under test
        is the retry path, not resolution."""
        monkeypatch.setattr(
            providers, "resolve_role_candidates",
            lambda _role: [{"provider": {"name": "stub", "kind": "openai",
                                         "base_url": "http://stub"},
                            "model": "stub-model"}])

    def test_a_cancelled_run_raises_aborted_not_the_socket_error(
            self, monkeypatch):
        self._stub_role(monkeypatch)
        ev = threading.Event()
        token = providers.cancel_event.set(ev)
        attempts = []

        def boom(*_a, **_kw):
            attempts.append(1)
            ev.set()          # the abort lands mid-flight
            raise ConnectionError("socket closed under the read")

        monkeypatch.setattr(providers, "_chat_complete_once", boom)
        try:
            with pytest.raises(providers.Aborted):
                providers.chat_complete("narrator", "sys", "user")
        finally:
            providers.cancel_event.reset(token)
        assert len(attempts) == 1, "it retried a run the user had stopped"

    def test_an_ordinary_connection_error_still_retries(self, monkeypatch):
        """The inverse: with nothing cancelled, a transport fault is still a
        transport fault and still gets its attempts."""
        self._stub_role(monkeypatch)
        ev = threading.Event()
        token = providers.cancel_event.set(ev)
        attempts = []

        def boom(*_a, **_kw):
            attempts.append(1)
            raise _req_exc.ConnectionError("genuinely flaky")

        monkeypatch.setattr(providers, "_chat_complete_once", boom)
        monkeypatch.setattr(providers.time, "sleep", lambda _s: None)
        try:
            with pytest.raises(Exception) as caught:
                providers.chat_complete("narrator", "sys", "user")
            assert not isinstance(caught.value, providers.Aborted)
        finally:
            providers.cancel_event.reset(token)
        assert len(attempts) == providers.DEFAULT_RETRY.max_retries + 1
