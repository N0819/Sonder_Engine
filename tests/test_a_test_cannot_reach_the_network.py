"""No test reaches a host that is not this machine, whatever door it opens.

The suite is documented as offline -- no network, no model -- and until
2026-11-01 it was offline by luck: a fresh scratch database holds no provider
row, so nothing configured a door to open, and no fixture refused a connection
(tooling_gate F4). `tests/conftest.py`'s `network_guard` is now that floor, at
the socket, under every client library and every door a list could forget.
These tests provoke it on purpose, so each clears the record it is handed --
a refusal that is recorded and NOT cleared fails the test that made it, even
when the engine swallowed the exception.
"""

import socket

import pytest

from tests.helpers import NetworkRefused, is_local_host


def test_a_connection_off_this_machine_is_refused(network_guard):
    with pytest.raises(NetworkRefused):
        socket.create_connection(("192.0.2.1", 443), timeout=1)
    assert [where for _thread, where in network_guard] == ["192.0.2.1:443"]
    network_guard.clear()


def test_a_name_lookup_off_this_machine_is_refused(network_guard):
    with pytest.raises(NetworkRefused):
        socket.getaddrinfo("example.com", 443)
    assert network_guard
    network_guard.clear()


def test_a_library_call_is_refused_at_the_same_floor(network_guard):
    """`requests` resolves and connects through the same two calls; the
    refusal is not an `OSError`, so no client retries it as a blip."""
    import requests

    with pytest.raises(NetworkRefused):
        requests.get("https://example.com/", timeout=1)
    network_guard.clear()


def test_this_machine_is_still_reachable():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]
        client = socket.create_connection(("127.0.0.1", port), timeout=2)
        client.close()
    finally:
        server.close()


@pytest.mark.parametrize("host,local", [
    ("127.0.0.1", True), ("::1", True), ("[::1]", True), ("localhost", True),
    ("0.0.0.0", True), (None, True), ("app.localhost", True),
    ("192.0.2.1", False), ("example.com", False), ("10.0.0.1", False),
])
def test_what_counts_as_this_machine(host, local):
    assert is_local_host(host) is local


@pytest.mark.network
def test_a_test_about_the_network_says_so(network_guard):
    assert network_guard is None
