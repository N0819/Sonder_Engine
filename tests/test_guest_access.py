"""Regression tests for guest_access.py: the join code lifecycle
(single-use, expiry, rate limiting) and guest token verification
underlying the "invite a friend" remote-join feature. Host account and
session functions are covered in test_host_secret_hashing.py."""

from __future__ import annotations

import time

import pytest

import guest_access as ga


@pytest.fixture(autouse=True)
def _reset_join_rate_limit():
    # _join_attempts is process-global (deliberately, so the rate limit
    # actually shares state across requests) -- without resetting it
    # between tests, earlier tests' redeem_code() calls in the same
    # second would spuriously trip the limit for later ones.
    ga._join_attempts.clear()
    yield
    ga._join_attempts.clear()


def _make_chat_and_persona(db):
    persona_id = db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        ("Guest Persona", "{}", "{}"),
    )
    chat_id = db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    return chat_id, persona_id


class TestJoinCodeLifecycle:
    def test_valid_code_redeems_to_a_token_for_the_right_chat_and_persona(
        self, temp_db,
    ):
        chat_id, persona_id = _make_chat_and_persona(temp_db)
        invite = ga.create_guest_invite(chat_id, persona_id)

        result = ga.redeem_code(invite["code"])

        assert result is not None
        assert result["chat_id"] == chat_id
        assert result["persona_id"] == persona_id
        assert result["token"]

    def test_code_is_single_use(self, temp_db):
        chat_id, persona_id = _make_chat_and_persona(temp_db)
        invite = ga.create_guest_invite(chat_id, persona_id)

        first = ga.redeem_code(invite["code"])
        second = ga.redeem_code(invite["code"])

        assert first is not None
        assert second is None

    def test_unknown_code_fails_closed(self, temp_db):
        assert ga.redeem_code("NOTAREALCODE") is None

    def test_expired_code_is_rejected(self, temp_db, monkeypatch):
        chat_id, persona_id = _make_chat_and_persona(temp_db)
        invite = ga.create_guest_invite(chat_id, persona_id)

        future = time.time() + ga.JOIN_CODE_TTL + 1
        monkeypatch.setattr(ga.time, "time", lambda: future)

        assert ga.redeem_code(invite["code"]) is None

    def test_revoked_grant_cannot_be_redeemed(self, temp_db):
        chat_id, persona_id = _make_chat_and_persona(temp_db)
        invite = ga.create_guest_invite(chat_id, persona_id)
        ga.revoke_grant(chat_id, invite["grant_id"])

        assert ga.redeem_code(invite["code"]) is None

    def test_rate_limit_blocks_rapid_join_attempts(self, temp_db):
        ga._join_attempts.clear()
        chat_id, persona_id = _make_chat_and_persona(temp_db)

        # Burn the window with wrong guesses -- each still counts against
        # the shared rate limit even though none of them match anything.
        for _ in range(ga._JOIN_WINDOW_MAX):
            ga.redeem_code("WRONGCODE")

        invite = ga.create_guest_invite(chat_id, persona_id)
        assert ga.redeem_code(invite["code"]) is None


class TestGuestTokenVerification:
    def test_valid_token_resolves_to_the_grant(self, temp_db):
        chat_id, persona_id = _make_chat_and_persona(temp_db)
        invite = ga.create_guest_invite(chat_id, persona_id)
        redeemed = ga.redeem_code(invite["code"])

        result = ga.verify_guest_token(redeemed["token"])

        assert result is not None
        assert result["chat_id"] == chat_id
        assert result["persona_id"] == persona_id

    def test_revoking_after_redemption_invalidates_the_token(self, temp_db):
        chat_id, persona_id = _make_chat_and_persona(temp_db)
        invite = ga.create_guest_invite(chat_id, persona_id)
        redeemed = ga.redeem_code(invite["code"])

        ga.revoke_grant(chat_id, invite["grant_id"])

        assert ga.verify_guest_token(redeemed["token"]) is None

    def test_expired_token_is_rejected_even_if_not_revoked(self, temp_db, monkeypatch):
        chat_id, persona_id = _make_chat_and_persona(temp_db)
        invite = ga.create_guest_invite(chat_id, persona_id)
        redeemed = ga.redeem_code(invite["code"])

        future = time.time() + ga.GUEST_TOKEN_TTL + 1
        monkeypatch.setattr(ga.time, "time", lambda: future)

        assert ga.verify_guest_token(redeemed["token"]) is None

    def test_garbage_token_is_rejected(self, temp_db):
        assert ga.verify_guest_token("not-a-real-token") is None
        assert ga.verify_guest_token(None) is None


class TestListGrants:
    def test_never_exposes_hashes(self, temp_db):
        chat_id, persona_id = _make_chat_and_persona(temp_db)
        ga.create_guest_invite(chat_id, persona_id)

        grants = ga.list_grants(chat_id)

        assert len(grants) == 1
        assert "code_hash" not in grants[0]
        assert "token_hash" not in grants[0]

    def test_status_reflects_lifecycle(self, temp_db):
        chat_id, persona_id = _make_chat_and_persona(temp_db)
        invite = ga.create_guest_invite(chat_id, persona_id)

        assert ga.list_grants(chat_id)[0]["status"] == "pending"

        ga.redeem_code(invite["code"])
        assert ga.list_grants(chat_id)[0]["status"] == "active"

        ga.revoke_grant(chat_id, invite["grant_id"])
        assert ga.list_grants(chat_id)[0]["status"] == "revoked"
