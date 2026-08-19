"""First-run setup is the one moment the engine has no owner.

`/api/auth/setup` sits in `PUBLIC_API_PATHS`, so `access_control` waves it
through by design -- there is no cookie to check before an account exists.
Until MASTER-017 the ONLY other gate was `host_account_exists()`, which means
the first caller to reach an unclaimed instance became its host: every chat,
persona and lorebook, plus the right to spend the host's stored provider
credentials. Two live shapes, both documented by the project itself:

  * `Start_Sonder.sh --host 0.0.0.0` (its own usage text) on a fresh install,
    where anything on the LAN can reach the port before the owner opens a
    browser;
  * `FICTION_ENGINE_RESET_HOST=1` re-opening setup on an instance that is
    ALREADY published -- the sharper one, because the tunnel is up first.

The rule this pins is about WHERE the request came from, not what it claims:
a claim of ownership over a machine may only be made from that machine. The
`Host` header and `X-Forwarded-For` are attacker-controlled and are therefore
never consulted.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from web import app as app_module
from web import auth_routes
from web import guest_access as guest


def _request(client_host, port=44444):
    """A bare Request carrying only a peer address -- the one input the gate
    is allowed to read."""
    return Request({
        "type": "http",
        "method": "POST",
        "path": "/api/auth/setup",
        "headers": [],
        "query_string": b"",
        "client": None if client_host is None else (client_host, port),
    })


def _setup(client_host, username="host", password="pw12345"):
    return auth_routes.auth_setup(
        request=_request(client_host),
        credentials=auth_routes.AuthCredentials(
            username=username, password=password
        ),
    )


@pytest.fixture(autouse=True)
def _no_embedding_reconcile(monkeypatch):
    # See the same fixture in test_host_surface_lifecycle.py: the reconciler
    # thread outlives the test that started it.
    monkeypatch.setattr(app_module, "_reconcile_embedding_bank", lambda: None)


@pytest.fixture(autouse=True)
def _clean_account(temp_db):
    guest.reset_host_account()
    yield
    guest.reset_host_account()


class TestOnlyTheMachineItselfMayClaimIt:
    def test_a_remote_caller_cannot_create_the_host_account(self):
        response = _setup("203.0.113.9")
        assert response.status_code == 403
        assert not guest.host_account_exists()

    def test_a_lan_neighbour_cannot_either(self):
        # The `--host 0.0.0.0` case: a private address is not a local one.
        assert _setup("192.168.1.50").status_code == 403
        assert not guest.host_account_exists()

    def test_ipv6_loopback_counts_as_local(self):
        assert _setup("::1").status_code == 200
        assert guest.host_account_exists()

    def test_ipv4_loopback_counts_as_local(self):
        assert _setup("127.0.0.1").status_code == 200
        assert guest.host_account_exists()

    def test_the_whole_127_block_counts_as_local(self):
        # 127.0.0.0/8 is loopback in its entirety; a host that reaches its own
        # server on 127.0.0.2 is still standing at the machine.
        assert _setup("127.0.0.2").status_code == 200

    def test_a_refusal_leaves_setup_open_for_the_owner(self):
        # The remote attempt must not consume the one-time claim, or a
        # drive-by would deny the owner their own instance.
        assert _setup("198.51.100.7").status_code == 403
        assert _setup("127.0.0.1").status_code == 200
        assert guest.host_account_exists()

    def test_the_refusal_does_not_say_which_address_would_work(self):
        detail = _setup("203.0.113.9").body.decode("utf-8")
        assert "127.0.0.1" not in detail and "::1" not in detail


class TestWhatTheGateRefusesToRead:
    def test_a_forwarded_header_cannot_forge_locality(self):
        request = Request({
            "type": "http",
            "method": "POST",
            "path": "/api/auth/setup",
            "headers": [
                (b"x-forwarded-for", b"127.0.0.1"),
                (b"host", b"localhost:8008"),
            ],
            "query_string": b"",
            "client": ("203.0.113.9", 44444),
        })
        response = auth_routes.auth_setup(
            request=request,
            credentials=auth_routes.AuthCredentials(
                username="host", password="pw12345"
            ),
        )
        assert response.status_code == 403
        assert not guest.host_account_exists()


class TestATransportWithNoNetworkPeerIsNotRemote:
    """An ASGI server always reports an IP for a network peer. A scope with no
    client at all, or a non-IP placeholder, is an in-process or unix-socket
    transport -- there is no remote caller to keep out, and refusing there
    would only break the callers that cannot be remote."""

    def test_a_missing_peer_is_allowed(self):
        assert _setup(None).status_code == 200

    def test_the_in_process_test_transport_still_reaches_setup(self, temp_db):
        with TestClient(app_module.app) as client:
            response = client.post(
                "/api/auth/setup",
                json={"username": "host", "password": "pw12345"},
            )
        assert response.status_code == 200


class TestSetupStaysClosedOnceClaimed:
    def test_a_local_second_setup_is_still_refused(self):
        assert _setup("127.0.0.1").status_code == 200
        assert _setup("127.0.0.1", username="other").status_code == 409

    def test_the_existing_account_answer_wins_over_the_locality_one(self):
        # A remote caller must learn nothing new from setup being closed:
        # once an account exists the answer is the same 409 everyone gets.
        assert _setup("127.0.0.1").status_code == 200
        assert _setup("203.0.113.9").status_code == 409


class TestStartupSaysWhenTheDoorIsOpen:
    """`_startup_engine` already prints the first-run URL. What it did not say
    is that the port is reachable from off the machine while setup is still
    unclaimed -- the state where the loopback gate is the only thing standing
    between a stranger and the whole install."""

    def test_a_public_bind_with_no_account_is_announced(
        self, temp_db, monkeypatch, capsys
    ):
        monkeypatch.setenv("FICTION_ENGINE_HOST", "0.0.0.0")
        monkeypatch.delenv("FICTION_ENGINE_RESET_HOST", raising=False)
        app_module._startup_engine()
        out = capsys.readouterr().out
        assert "0.0.0.0" in out
        assert "reachable" in out.lower()

    def test_a_loopback_bind_says_nothing_extra(
        self, temp_db, monkeypatch, capsys
    ):
        monkeypatch.setenv("FICTION_ENGINE_HOST", "127.0.0.1")
        monkeypatch.delenv("FICTION_ENGINE_RESET_HOST", raising=False)
        app_module._startup_engine()
        out = capsys.readouterr().out
        assert "reachable" not in out.lower()

    def test_a_claimed_account_is_not_warned_about(
        self, temp_db, monkeypatch, capsys
    ):
        # The warning is about the UNCLAIMED window. Once the host owns the
        # instance, a public bind is a deliberate choice, not an open door.
        guest.create_host_account("host", "pw12345")
        monkeypatch.setenv("FICTION_ENGINE_HOST", "0.0.0.0")
        monkeypatch.delenv("FICTION_ENGINE_RESET_HOST", raising=False)
        app_module._startup_engine()
        out = capsys.readouterr().out
        assert "reachable" not in out.lower()
