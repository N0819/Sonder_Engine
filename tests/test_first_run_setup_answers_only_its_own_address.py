"""First-run setup is claimed only at this machine's own address, never at a
name a page could have rebound.

While no host account exists (a fresh install, or every restart under
`FICTION_ENGINE_RESET_HOST=1`), `/api/auth/setup` is public and its only gate
is `request_is_local`: the TCP peer must be loopback. A DNS-rebinding page
satisfies that from the host's own browser -- `evil.example:8008` rebound to
127.0.0.1 IS a loopback peer -- claims the account, and holds a cookie that
is same-origin to itself, so it can then read provider keys from
`/api/bootstrap` (audit 2026-11-01, web_routes_extensions F2). The host then
gets "Account already exists" for their own instance.

A rebinding page cannot choose the Host its browser sends: it is the page's
own name. So setup over a network connection is refused unless the Host is an
address, `localhost`, or a name the host declared in `SONDER_SETUP_HOSTS`. An
in-process transport (the test client, a unix socket) has no browser to
rebind, and is unchanged.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

CREDENTIALS = {"username": "host", "password": "pw12345"}


@pytest.fixture
def unclaimed(temp_db, monkeypatch):
    from web import guest_access as guest
    monkeypatch.delenv("SONDER_SETUP_HOSTS", raising=False)
    guest._login_attempts.clear()
    guest.reset_host_account()
    yield guest
    guest._login_attempts.clear()


def _post_from_this_machine(path, host, body):
    """A real browser on this machine: a loopback TCP peer, sending `host`."""
    from web import app as app_module
    client = TestClient(app_module.app, client=("127.0.0.1", 51234))
    return client.post(path, json=body, headers={"host": host})


def test_a_rebound_name_cannot_claim_the_instance(unclaimed):
    r = _post_from_this_machine("/api/auth/setup", "evil.example:8008", CREDENTIALS)
    assert r.status_code == 403
    assert not unclaimed.host_account_exists(), "the claim was not consumed"


@pytest.mark.parametrize("host", ["127.0.0.1:8008", "localhost:8008",
                                  "[::1]:8008", "localhost"])
def test_this_machines_own_address_claims_it(unclaimed, host):
    r = _post_from_this_machine("/api/auth/setup", host, CREDENTIALS)
    assert r.status_code == 200, r.text
    assert unclaimed.host_account_exists()


def test_a_name_the_host_declared_claims_it(unclaimed, monkeypatch):
    monkeypatch.setenv("SONDER_SETUP_HOSTS", "workbench, other.lan")
    r = _post_from_this_machine("/api/auth/setup", "Workbench:8008", CREDENTIALS)
    assert r.status_code == 200, r.text


def test_an_in_process_caller_is_unchanged(unclaimed):
    from web import app as app_module
    r = TestClient(app_module.app).post("/api/auth/setup", json=CREDENTIALS)
    assert r.status_code == 200, r.text


def test_signing_in_is_not_held_to_it(unclaimed):
    """Only the unclaimed window is at stake: a rebinding page has no
    password, and an instance published under a name keeps signing in."""
    unclaimed.create_host_account("host", "pw12345")
    r = _post_from_this_machine("/api/auth/login", "published.example", CREDENTIALS)
    assert r.status_code == 200, r.text
