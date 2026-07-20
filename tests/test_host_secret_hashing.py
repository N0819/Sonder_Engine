"""Regression tests for host account credential storage.

The host password must be stored only as a salted PBKDF2 hash, and session
tokens only as SHA-256 hashes, so a readable engine.db never yields a
working host credential. create_host_account is one-shot (refuses to
overwrite); reset_host_account is the only way back to first-run setup and
must invalidate every outstanding session.
"""

from __future__ import annotations

import guest_access as guest
from db import q, get_setting


PASSWORD = "correct horse battery staple"


def test_create_account_stores_only_hash_and_salt(temp_db):
    assert guest.host_account_exists() is False
    token = guest.create_host_account("host", PASSWORD)
    assert token and isinstance(token, str)
    assert guest.host_account_exists() is True

    assert get_setting("host_username") == "host"
    salt = get_setting("host_pw_salt")
    pw_hash = get_setting("host_pw_hash")
    assert salt and pw_hash
    assert pw_hash != PASSWORD
    assert pw_hash == guest._hash_password(PASSWORD, salt)
    # No setting anywhere holds the plaintext password.
    rows = q("SELECT key, value FROM settings")
    assert all(r["value"] != PASSWORD for r in rows)

    # The returned token is a live session.
    assert guest.verify_host_session(token) is True


def test_verify_host_login_accepts_correct_and_rejects_wrong(temp_db):
    guest.create_host_account("host", PASSWORD)
    assert guest.verify_host_login("host", PASSWORD) is True
    # Username is stripped before comparison.
    assert guest.verify_host_login("  host  ", PASSWORD) is True
    assert guest.verify_host_login("wrong", PASSWORD) is False
    assert guest.verify_host_login("host", "wrong-password") is False
    assert guest.verify_host_login("", PASSWORD) is False
    assert guest.verify_host_login("host", "") is False
    assert guest.verify_host_login("", "") is False


def test_login_rejected_when_no_account_exists(temp_db):
    assert guest.verify_host_login("host", PASSWORD) is False


def test_second_create_returns_none_and_does_not_overwrite(temp_db):
    guest.create_host_account("host", PASSWORD)
    salt_before = get_setting("host_pw_salt")
    hash_before = get_setting("host_pw_hash")

    assert guest.create_host_account("intruder", "other-password") is None

    assert get_setting("host_username") == "host"
    assert get_setting("host_pw_salt") == salt_before
    assert get_setting("host_pw_hash") == hash_before
    assert guest.verify_host_login("host", PASSWORD) is True
    assert guest.verify_host_login("intruder", "other-password") is False


def test_session_round_trip_and_destroy(temp_db):
    guest.create_host_account("host", PASSWORD)
    token = guest.create_host_session()
    assert guest.verify_host_session(token) is True
    assert guest.verify_host_session("not-a-real-token") is False
    assert guest.verify_host_session("") is False
    assert guest.verify_host_session(None) is False
    # Only the hash is at rest, never the token itself.
    rows = q("SELECT token_hash FROM host_sessions")
    assert all(r["token_hash"] != token for r in rows)

    guest.destroy_host_session(token)
    assert guest.verify_host_session(token) is False


def test_reset_clears_account_and_invalidates_sessions(temp_db):
    token = guest.create_host_account("host", PASSWORD)
    extra = guest.create_host_session()

    guest.reset_host_account()

    assert guest.host_account_exists() is False
    assert guest.verify_host_login("host", PASSWORD) is False
    assert guest.verify_host_session(token) is False
    assert guest.verify_host_session(extra) is False
