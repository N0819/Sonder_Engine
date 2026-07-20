"""Regression tests for the host/guest access-control middleware in
app.py: every /api/* request must carry a valid host or guest cookie
(except the public /api/join and /api/auth/* endpoints), and a guest
cookie must only unlock the narrow guest-scoped endpoint allowlist --
everything else 403s even with a valid guest session."""

from __future__ import annotations

import json
import time

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


def _host_client(client):
    # Start from a clean slate so this helper owns the account it creates;
    # the setup response sets the fe_host session cookie on the client.
    guest.reset_host_account()
    r = client.post(
        "/api/auth/setup", json={"username": "host", "password": "pw12345"}
    )
    assert r.status_code == 200
    return client


def _make_chat_with_extra_persona(db):
    persona_id = db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        ("Guest Persona", "{}", "{}"),
    )
    chat_id = db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test Chat", "", time.time()),
    )
    db.qi(
        "INSERT INTO chat_personas(chat_id,persona_id,status) VALUES(?,?,'active')",
        (chat_id, persona_id),
    )
    return chat_id, persona_id


class TestUnauthenticatedRequests:
    def test_root_is_always_servable(self, client):
        assert client.get("/").status_code == 200

    def test_api_request_without_any_cookie_is_rejected(self, client):
        r = client.get("/api/bootstrap")
        assert r.status_code == 401

    def test_join_endpoint_is_reachable_without_a_cookie(self, client):
        # Not authorized to DO anything yet, but the auth gate itself
        # must not block reaching the join logic -- a bad code should
        # fail with the join endpoint's own 400, not a blanket 401.
        r = client.post("/api/join", json={"code": "WRONGCODE"})
        assert r.status_code == 400


class TestHostAccess:
    def test_wrong_login_does_not_authenticate(self, client):
        guest.reset_host_account()
        guest.create_host_account("host", "pw12345")
        r = client.post(
            "/api/auth/login",
            json={"username": "host", "password": "not-the-real-password"},
        )
        assert r.status_code == 401
        assert "fe_host" not in r.cookies
        assert client.get("/api/bootstrap").status_code == 401

    def test_correct_login_grants_full_api_access(self, client, temp_db):
        _host_client(client)
        assert client.get("/api/bootstrap").status_code == 200

    def test_host_can_create_and_list_guest_invites(self, client, temp_db):
        _host_client(client)
        chat_id, persona_id = _make_chat_with_extra_persona(temp_db)

        r = client.post(
            f"/api/chats/{chat_id}/guest_invites",
            json={"persona_id": persona_id},
        )
        assert r.status_code == 200
        assert r.json()["code"]

        r = client.get(f"/api/chats/{chat_id}/guest_invites")
        assert r.status_code == 200
        assert len(r.json()["grants"]) == 1


class TestGuestAccess:
    def test_redeeming_a_code_grants_only_guest_scope(self, client, temp_db):
        _host_client(client)
        chat_id, persona_id = _make_chat_with_extra_persona(temp_db)
        invite = client.post(
            f"/api/chats/{chat_id}/guest_invites",
            json={"persona_id": persona_id},
        ).json()

        # Fresh client with no host cookie, simulating the friend's browser.
        guest_client = TestClient(app_module.app)
        r = guest_client.post("/api/join", json={"code": invite["code"]})
        assert r.status_code == 200
        assert r.json()["persona_name"] == "Guest Persona"

        # Guest-allowed endpoint works.
        state = guest_client.get("/api/guest/state")
        assert state.status_code == 200
        assert state.json()["chat_name"] == "Test Chat"

        # Host-only endpoint is forbidden even with a valid guest session.
        assert guest_client.get("/api/bootstrap").status_code == 403
        assert guest_client.get(
            f"/api/chats/{chat_id}/guest_invites"
        ).status_code == 403

    def test_guest_input_is_forced_to_the_grants_own_persona(self, client, temp_db):
        _host_client(client)
        chat_id, persona_id = _make_chat_with_extra_persona(temp_db)
        # A second persona the guest must NOT be able to act as.
        other_persona_id = temp_db.qi(
            "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
            ("Someone Else", "{}", "{}"),
        )
        invite = client.post(
            f"/api/chats/{chat_id}/guest_invites",
            json={"persona_id": persona_id},
        ).json()

        guest_client = TestClient(app_module.app)
        guest_client.post("/api/join", json={"code": invite["code"]})

        r = guest_client.post(
            "/api/guest/input",
            json={"idx": 0, "input": "hello", "persona_id": other_persona_id},
        )
        assert r.status_code == 200

        row = temp_db.q(
            "SELECT persona_id FROM turn_player_inputs WHERE chat_id=? AND turn_idx=0",
            (chat_id,), one=True,
        )
        # The body's persona_id is ignored -- the grant's own persona wins.
        assert row["persona_id"] == persona_id

    def test_code_cannot_be_redeemed_twice(self, client, temp_db):
        _host_client(client)
        chat_id, persona_id = _make_chat_with_extra_persona(temp_db)
        invite = client.post(
            f"/api/chats/{chat_id}/guest_invites",
            json={"persona_id": persona_id},
        ).json()

        first = TestClient(app_module.app)
        second = TestClient(app_module.app)
        assert first.post("/api/join", json={"code": invite["code"]}).status_code == 200
        assert second.post("/api/join", json={"code": invite["code"]}).status_code == 400

    def test_revoking_a_grant_locks_out_the_guest(self, client, temp_db):
        _host_client(client)
        chat_id, persona_id = _make_chat_with_extra_persona(temp_db)
        invite = client.post(
            f"/api/chats/{chat_id}/guest_invites",
            json={"persona_id": persona_id},
        ).json()

        guest_client = TestClient(app_module.app)
        guest_client.post("/api/join", json={"code": invite["code"]})
        assert guest_client.get("/api/guest/state").status_code == 200

        client.delete(f"/api/chats/{chat_id}/guest_invites/{invite['grant_id']}")

        # verify_guest_token now correctly rejects the revoked token outright
        # (401, "not authenticated"), not just out-of-scope (403).
        assert guest_client.get("/api/guest/state").status_code == 401
