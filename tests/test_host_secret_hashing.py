"""Regression tests for host-secret hashing at rest.

The host secret must be stored only as a SHA-256 hash, never plaintext, so a
readable engine.db never yields a working host credential. The plaintext is
returned exactly once (at mint) for the console authorize URL; a pre-hashing
plaintext secret is migrated in place without logging out the current host.
"""

from __future__ import annotations

import hashlib

import guest_access as guest
from db import get_setting, set_setting


def _h(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def test_mint_returns_plaintext_but_stores_only_hash(temp_db):
    secret = guest.ensure_host_secret()
    assert secret and isinstance(secret, str)
    assert get_setting("host_secret_hash") == _h(secret)
    assert (get_setting("host_secret") or "") == ""
    assert guest.verify_host_secret(secret) is True
    assert guest.verify_host_secret("nope") is False
    assert guest.verify_host_secret(None) is False


def test_second_ensure_returns_none_but_secret_still_valid(temp_db):
    secret = guest.ensure_host_secret()
    assert guest.ensure_host_secret() is None
    assert guest.verify_host_secret(secret) is True


def test_reset_invalidates_prior_secret(temp_db):
    first = guest.ensure_host_secret()
    second = guest.reset_host_secret()
    assert second != first
    assert guest.verify_host_secret(second) is True
    assert guest.verify_host_secret(first) is False


def test_legacy_plaintext_secret_is_migrated_without_logout(temp_db):
    legacy = "legacy-plaintext-secret"
    set_setting("host_secret", legacy)  # a pre-hardening database
    assert guest.ensure_host_secret() is None
    assert get_setting("host_secret_hash") == _h(legacy)
    assert (get_setting("host_secret") or "") == ""
    # The host's existing cookie carries the plaintext -> must still verify.
    assert guest.verify_host_secret(legacy) is True
