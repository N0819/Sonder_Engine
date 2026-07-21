"""Regression tests for audit finding #28: guest_access.py.

(a) Join-code redemption was SELECT-then-UPDATE with an unconditional
    UPDATE-by-id -- two requests that both passed the SELECT while the code
    was still unredeemed would BOTH mint a token off one single-use code. The
    fix guards the UPDATE with `redeemed_at IS NULL` and confirms the claim by
    reading back token_hash.

(b) verify_host_login passed str to secrets.compare_digest, which is
    ASCII-only -- a non-ASCII host username raised TypeError -> 500, a
    permanently broken login. The fix compares UTF-8 byte encodings.
"""

from __future__ import annotations

import time

import pytest

import guest_access as ga


@pytest.fixture(autouse=True)
def _reset_join_rate_limit():
    # _join_attempts is process-global; clear it so redeem_code() calls from
    # other tests in the same second don't spuriously trip the rate limit.
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


class TestJoinCodeAtomicSingleUse:
    def test_second_redemption_of_the_same_code_is_rejected(self, temp_db):
        chat_id, persona_id = _make_chat_and_persona(temp_db)
        invite = ga.create_guest_invite(chat_id, persona_id)

        first = ga.redeem_code(invite["code"])
        assert first is not None and first["token"]

        # Straightforward single-use: once redeemed, the code is dead.
        assert ga.redeem_code(invite["code"]) is None

    def test_stale_read_race_does_not_double_issue(self, temp_db, monkeypatch):
        # Simulate the concurrency window directly: force the code-lookup
        # SELECT to report the grant as still unredeemed (redeemed_at NULL)
        # even though it was already claimed. Under the old unconditional
        # UPDATE-by-id this minted a SECOND token off the single-use code;
        # the guarded UPDATE + token_hash read-back must reject it instead.
        chat_id, persona_id = _make_chat_and_persona(temp_db)
        invite = ga.create_guest_invite(chat_id, persona_id)

        first = ga.redeem_code(invite["code"])
        assert first is not None
        winner_hash = ga._hash(first["token"])

        real_q = ga.q

        def stale_q(sql, args=(), one=False):
            row = real_q(sql, args, one=one)
            # Only the code_hash lookup is faked stale; the id read-back that
            # confirms the claim passes through the true (already-redeemed) row.
            if "code_hash=?" in sql and row is not None:
                d = dict(row)
                d["redeemed_at"] = None
                return d
            return row

        monkeypatch.setattr(ga, "q", stale_q)

        second = ga.redeem_code(invite["code"])
        assert second is None  # lost the race -> no second token issued

        monkeypatch.setattr(ga, "q", real_q)
        # The grant still holds the ORIGINAL winner's token, untouched.
        grant = ga.q(
            "SELECT token_hash FROM guest_grants WHERE id=?",
            (invite["grant_id"],), one=True,
        )
        assert grant["token_hash"] == winner_hash


class TestHostLoginNonAsciiUsername:
    def test_non_ascii_username_login_does_not_raise_and_verifies(self, temp_db):
        username = "café-héro-Ω"  # non-ASCII code points
        password = "correct horse battery staple"
        assert ga.create_host_account(username, password)

        # Old code raised TypeError here (compare_digest is ASCII-only on str).
        assert ga.verify_host_login(username, password) is True
        assert ga.verify_host_login(username, "wrong password") is False
        # A wrong non-ASCII username is also handled without raising.
        assert ga.verify_host_login("другой", password) is False
