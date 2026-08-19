"""The host credential: how it is stored, and who is allowed to guess at it.

Two findings, one subject.

MASTER-016. The work factor was a code constant and the stored value was a
bare digest, so nothing at rest recorded which factor had produced it. Raising
the number therefore invalidated every existing password -- which is the same
as saying it could never be raised, and 200_000 is below current guidance. A
verifier now says what made it (`pbkdf2_sha256$<iters>$<salt>$<digest>`), old
bare-hex records still verify, and a correct sign-in rewrites the record at
the current factor.

MASTER-015. The login limiter kept its ledger in a bare module list with no
lock, and `/api/auth/login` is a `def` -- FastAPI runs it in the anyio
threadpool, several at a time. Checking was one call, recording was another,
and a PBKDF2 verify sat between them, so concurrent requests all read a budget
none of them had spent. The window was worth a threadpool's width of guesses
per minute instead of ten, and the prune-then-index read could fault against a
concurrent clear.
"""

from __future__ import annotations

import threading
import time

import pytest

from core.db import get_setting, set_setting
from web import auth_routes
from web import guest_access as guest


PASSWORD = "correct horse battery staple"


@pytest.fixture(autouse=True)
def _clean_limiter():
    guest._login_attempts.clear()
    guest._join_attempts.clear()
    yield
    guest._login_attempts.clear()
    guest._join_attempts.clear()


class TestTheStoredVerifierSaysWhatMadeIt:
    def test_a_new_account_records_scheme_and_work_factor(self, temp_db):
        guest.create_host_account("host", PASSWORD)
        stored = get_setting(guest.HOST_PW_HASH_SETTING)
        scheme, iters, salt, digest = stored.split("$")
        assert scheme == "pbkdf2_sha256"
        assert int(iters) == guest._PBKDF2_ITERS
        assert salt == get_setting(guest.HOST_PW_SALT_SETTING)
        assert digest and digest != PASSWORD

    def test_the_work_factor_meets_current_guidance(self):
        # The number is allowed to move; it is not allowed to move DOWN to
        # where it was, which is what the frozen format made permanent.
        assert guest._PBKDF2_ITERS >= 600_000

    def test_nothing_stored_is_the_password(self, temp_db):
        guest.create_host_account("host", PASSWORD)
        stored = get_setting(guest.HOST_PW_HASH_SETTING)
        assert PASSWORD not in stored


class TestARecordFromBeforeTheFormatStillWorks:
    def _write_legacy_record(self):
        salt = "00112233445566778899aabbccddeeff"
        digest = guest._pbkdf2(PASSWORD, salt, guest._LEGACY_PBKDF2_ITERS)
        set_setting(guest.HOST_USERNAME_SETTING, "host")
        set_setting(guest.HOST_PW_SALT_SETTING, salt)
        set_setting(guest.HOST_PW_HASH_SETTING, digest)  # bare hex, no scheme
        return digest

    def test_a_bare_hex_digest_still_verifies(self, temp_db):
        self._write_legacy_record()
        assert guest.verify_host_login("host", PASSWORD) is True
        assert guest.verify_host_login("host", "wrong") is False

    def test_a_correct_sign_in_upgrades_the_record(self, temp_db):
        legacy = self._write_legacy_record()
        assert guest.verify_host_login("host", PASSWORD) is True

        upgraded = get_setting(guest.HOST_PW_HASH_SETTING)
        assert upgraded != legacy
        assert upgraded.startswith(f"pbkdf2_sha256${guest._PBKDF2_ITERS}$")
        # Re-salted, and still the same password.
        assert get_setting(guest.HOST_PW_SALT_SETTING) != (
            "00112233445566778899aabbccddeeff"
        )
        assert guest.verify_host_login("host", PASSWORD) is True

    def test_a_wrong_password_upgrades_nothing(self, temp_db):
        legacy = self._write_legacy_record()
        assert guest.verify_host_login("host", "wrong") is False
        assert get_setting(guest.HOST_PW_HASH_SETTING) == legacy

    def test_an_already_current_record_is_left_alone(self, temp_db):
        guest.create_host_account("host", PASSWORD)
        before = get_setting(guest.HOST_PW_HASH_SETTING)
        assert guest.verify_host_login("host", PASSWORD) is True
        assert get_setting(guest.HOST_PW_HASH_SETTING) == before


class TestAStoredRecordIsNotTrustedInput:
    """A settings row is local, which is not the same as trustworthy: anything
    with filesystem access can write one, and the process must not hang or
    weaken itself on what it reads back."""

    def _store(self, value):
        set_setting(guest.HOST_USERNAME_SETTING, "host")
        set_setting(guest.HOST_PW_SALT_SETTING, "aabb")
        set_setting(guest.HOST_PW_HASH_SETTING, value)

    def test_an_absurd_work_factor_is_refused_not_computed(self, temp_db):
        self._store("pbkdf2_sha256$900000000$aabb$" + "0" * 64)
        started = time.time()
        assert guest.verify_host_login("host", PASSWORD) is False
        # Refused by the bounds check, not by grinding through it.
        assert time.time() - started < 1.0

    def test_a_weakened_work_factor_is_refused(self, temp_db):
        self._store("pbkdf2_sha256$1$aabb$" + guest._pbkdf2(PASSWORD, "aabb", 1))
        assert guest.verify_host_login("host", PASSWORD) is False

    def test_an_unknown_scheme_is_refused(self, temp_db):
        self._store("argon2id$3$aabb$" + "0" * 64)
        assert guest.verify_host_login("host", PASSWORD) is False

    def test_a_malformed_record_is_refused_without_raising(self, temp_db):
        for value in ("$$$", "pbkdf2_sha256$notanumber$aabb$ff",
                      "pbkdf2_sha256$600000$nothex$ff", "pbkdf2_sha256$600000$$"):
            self._store(value)
            assert guest.verify_host_login("host", PASSWORD) is False

    def test_a_legacy_record_with_no_salt_is_refused(self, temp_db):
        set_setting(guest.HOST_USERNAME_SETTING, "host")
        set_setting(guest.HOST_PW_SALT_SETTING, "")
        set_setting(guest.HOST_PW_HASH_SETTING, "ff" * 32)
        assert guest.verify_host_login("host", PASSWORD) is False

    def test_a_legacy_record_with_a_broken_salt_is_refused(self, temp_db):
        # `bytes.fromhex` on a non-hex salt is a ValueError out of the verify
        # -- a 500 on the login route rather than a rejected password.
        set_setting(guest.HOST_USERNAME_SETTING, "host")
        set_setting(guest.HOST_PW_SALT_SETTING, "not hex at all")
        set_setting(guest.HOST_PW_HASH_SETTING, "ff" * 32)
        assert guest.verify_host_login("host", PASSWORD) is False


class TestTheWindowIsSpentOnce:
    def test_a_slow_verify_cannot_let_more_than_the_budget_through(
        self, temp_db, monkeypatch
    ):
        # The real shape of the defect. `/api/auth/login` is a `def`, so
        # FastAPI runs it in the anyio threadpool: twenty requests arrive at
        # once, the check is non-consuming, and the record happens on the far
        # side of a PBKDF2 verify. Every one of them therefore read a budget
        # none of them had spent, and all twenty got a guess. The verify is
        # slowed here to make that gap the wide one it really is.
        guest.create_host_account("host", PASSWORD)

        def slow_verify(username, password):
            time.sleep(0.05)
            return False

        monkeypatch.setattr(guest, "verify_host_login", slow_verify)

        statuses = []
        gate = threading.Barrier(20)

        def attempt():
            gate.wait()
            response = auth_routes.auth_login(
                auth_routes.AuthCredentials(username="host", password="x")
            )
            statuses.append(response.status_code)

        threads = [threading.Thread(target=attempt) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert statuses.count(401) == guest._LOGIN_WINDOW_MAX
        assert statuses.count(429) == 20 - guest._LOGIN_WINDOW_MAX

    def test_a_refusal_spends_nothing(self):
        for _ in range(guest._LOGIN_WINDOW_MAX):
            assert guest.claim_login_attempt() == 0
        before = list(guest._login_attempts)
        for _ in range(5):
            assert guest.claim_login_attempt() > 0
        assert guest._login_attempts == before

    def test_a_success_refunds_the_slot_it_claimed(self):
        for _ in range(guest._LOGIN_WINDOW_MAX - 1):
            assert guest.claim_login_attempt() == 0
        assert guest.claim_login_attempt() == 0
        guest.record_login_success()
        assert guest._login_attempts == []

    def test_checking_still_never_consumes(self):
        assert guest.login_retry_after() == 0
        assert guest._login_attempts == []


class TestEveryTouchOfALedgerIsUnderTheGuard:
    """The sub-race that produced a 500: `_login_attempts[-_LOGIN_WINDOW_MAX]`
    and the prune loop's `pop(0)` both index a list a concurrent
    `record_login_success()` may have just cleared. That window is a few
    bytecodes wide, so pinning it by racing threads would pin luck. Pin the
    property instead -- every reader and every writer runs inside the one
    lock -- which is what actually closes it."""

    def _assert_guarded(self, monkeypatch, call):
        seen = {}
        real_prune = guest._prune

        def checking_prune(attempts, window, now):
            seen["locked"] = guest._RATE_GUARD.locked()
            real_prune(attempts, window, now)

        monkeypatch.setattr(guest, "_prune", checking_prune)
        call()
        assert seen.get("locked") is True

    def test_reading_the_login_window_is_guarded(self, monkeypatch):
        self._assert_guarded(monkeypatch, guest.login_retry_after)

    def test_claiming_a_login_slot_is_guarded(self, monkeypatch):
        self._assert_guarded(monkeypatch, guest.claim_login_attempt)

    def test_the_join_window_is_guarded_too(self, monkeypatch):
        # Same list-with-no-lock shape, same threadpool, same fix.
        self._assert_guarded(monkeypatch, guest._join_rate_limited)

    def test_clearing_the_ledger_is_guarded(self, monkeypatch):
        held = {}
        real_clear = list.clear

        class Watching(list):
            def clear(self):
                held["locked"] = guest._RATE_GUARD.locked()
                real_clear(self)

        monkeypatch.setattr(guest, "_login_attempts", Watching([time.time()]))
        guest.record_login_success()
        assert held.get("locked") is True
