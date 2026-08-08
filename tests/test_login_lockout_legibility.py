"""The 2026-08 lockout incident, server half.

A password manager auto-resubmitting saved credentials burned the global
10-per-60s login window in seconds and locked the host out of his own
single-user app; the 429 said only "wait a minute". Three server defects
made that possible or made it illegible:

  (a) the limiter consumed a slot on EVERY call, success included -- ten
      successful sign-ins in a minute locked the host out;
  (b) the 429 carried no time remaining, so a waiting page was
      indistinguishable from a stuck one;
  (c) a login against a nonexistent account got the generic "Invalid
      username or password" -- a lie about a state /api/auth/status
      already reveals -- and burned a limiter slot for a non-guess.

The limiter now counts failures only, success clears the ledger, the 429
reports retry_after_seconds (body and Retry-After header), and the
no-account case names the real problem. The one thing that must NOT
become more specific is the credential-failure 401: never say which half
was wrong.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app as app_module
import guest_access as guest


@pytest.fixture
def client(temp_db):
    guest._join_attempts.clear()
    guest._login_attempts.clear()
    with TestClient(app_module.app) as c:
        yield c
    guest._join_attempts.clear()
    guest._login_attempts.clear()


@pytest.fixture
def account(client):
    r = client.post(
        "/api/auth/setup", json={"username": "host", "password": "pw12345"}
    )
    assert r.status_code == 200
    client.cookies.clear()  # tests below sign in explicitly
    return {"username": "host", "password": "pw12345"}


def _login(client, username, password):
    return client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )


class TestOnlyFailuresSpendTheBudget:
    def test_successful_logins_never_lock_the_host_out(self, client, account):
        # Old limiter: the 11th call found ten consumed slots -> 429, i.e.
        # signing in ten times in a minute locked you out of your own app.
        for _ in range(11):
            r = _login(client, account["username"], account["password"])
            assert r.status_code == 200

    def test_a_success_clears_earlier_failures(self, client, account):
        # 9 failures, then the host gets it right: the ledger resets, so
        # the next ten wrong guesses are each still evaluated. Old code
        # 429'd immediately after the success (10 consumed slots).
        for _ in range(9):
            assert _login(client, "host", "wrong").status_code == 401
        assert _login(
            client, account["username"], account["password"]
        ).status_code == 200
        for _ in range(10):
            assert _login(client, "host", "wrong").status_code == 401
        assert _login(client, "host", "wrong").status_code == 429


class TestLockoutIsLegible:
    def test_429_reports_seconds_remaining(self, client, account):
        for _ in range(10):
            assert _login(client, "host", "wrong").status_code == 401
        r = _login(client, account["username"], account["password"])
        assert r.status_code == 429
        data = r.json()
        seconds = data["retry_after_seconds"]
        assert isinstance(seconds, int) and 1 <= seconds <= 60
        # The standard header, for anything that isn't our page.
        assert r.headers["Retry-After"] == str(seconds)
        # And the human-readable detail carries the same number, not a
        # static "wait a minute".
        assert f"{seconds}s" in data["detail"]

    def test_checking_the_limit_does_not_spend_it(self, client, account):
        # Pin, not regression: login_retry_after() must stay non-consuming,
        # so a page retrying into a 429 (or polling it) never pushes the
        # unlock time further away.
        for _ in range(10):
            assert _login(client, "host", "wrong").status_code == 401
        before = list(guest._login_attempts)
        for _ in range(5):
            assert _login(client, "host", "wrong").status_code == 429
        assert guest._login_attempts == before


class TestFailureModesAreDistinct:
    def test_no_account_names_the_real_problem(self, client):
        # Against an empty database the old response was the generic 401
        # "Invalid username or password" -- a lie about a state that
        # /api/auth/status already reveals -- and it burned a limiter slot.
        r = _login(client, "anyone", "anything")
        assert r.status_code == 409
        assert r.json()["setup_required"] is True
        assert guest._login_attempts == []

    def test_wrong_username_and_wrong_password_read_identically(
        self, client, account
    ):
        # The deliberate security property that must survive all the new
        # verbosity: a credential failure never reveals which half was
        # wrong. Same status, same body, byte for byte.
        wrong_user = _login(client, "not-host", account["password"])
        wrong_pass = _login(client, account["username"], "not-the-password")
        assert wrong_user.status_code == wrong_pass.status_code == 401
        assert wrong_user.json() == wrong_pass.json()
