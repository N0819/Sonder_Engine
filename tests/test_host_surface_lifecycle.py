"""What startup and shutdown are responsible for.

MASTER-020, sweep half. `verify_host_session` filters on `expires > ?` and
`verify_guest_token` on `token_expires`, so a dead row never authenticated
anything -- but nothing ever DELETED one. `host_sessions` grew by a row per
sign-in for the life of the install and `guest_grants` by a row per invite,
both inside a file the host backs up, checkpoints and copies, and both scanned
behind every request that checks a cookie. Startup is the right cadence: one
worker, one process, no timer to leak.

MASTER-004, shutdown half. The lifespan had a startup half and nothing after
the `yield`, so a Ctrl-C left offscreen ticks, artifact generation, memory
consolidation, backdrop and ambience work running against a database the
process was closing. They are daemon threads, so nothing HUNG -- the cost is
paid where it is hardest to see: work that was mid-write when the interpreter
went away. Shutdown now asks them all to stop and waits a bounded moment,
which is all a cooperative cancellation can promise.
"""

from __future__ import annotations

import threading
import time

import pytest
from fastapi.testclient import TestClient

from core import jobs, outofband
from core.db import q, qi
from web import app as app_module
from web import guest_access as guest


DAY = 60 * 60 * 24


@pytest.fixture(autouse=True)
def _no_embedding_reconcile(monkeypatch):
    # `_startup_engine` hands the memory bank to a reconciler on its own
    # thread. Nothing here is about the bank, and a thread still writing when
    # the next test swaps databases underneath it is how a suite gets a
    # "database is locked" that has nothing to do with what it was testing.
    monkeypatch.setattr(app_module, "_reconcile_embedding_bank", lambda: None)


def _persona_and_chat(db):
    persona_id = db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        ("Guest Persona", "{}", "{}"),
    )
    chat_id = db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test Chat", "", time.time()),
    )
    return chat_id, persona_id


class TestDeadSessionsAreSwept:
    def test_an_expired_session_row_is_deleted(self, temp_db):
        now = time.time()
        qi(
            "INSERT INTO host_sessions(token_hash,created,expires) "
            "VALUES(?,?,?)",
            ("dead", now - 2 * DAY, now - DAY),
        )
        live = guest.create_host_session()

        assert guest.sweep_expired_access() == 1

        remaining = [r["token_hash"] for r in q("SELECT token_hash FROM host_sessions")]
        assert "dead" not in remaining
        assert guest.verify_host_session(live) is True

    def test_a_live_session_survives_startup(self, temp_db):
        token = guest.create_host_session()
        app_module._startup_engine()
        assert guest.verify_host_session(token) is True

    def test_startup_sweeps_without_being_asked(self, temp_db):
        now = time.time()
        qi(
            "INSERT INTO host_sessions(token_hash,created,expires) "
            "VALUES(?,?,?)",
            ("dead", now - 2 * DAY, now - DAY),
        )
        app_module._startup_engine()
        assert q("SELECT id FROM host_sessions WHERE token_hash='dead'") == []


class TestDeadGrantsAreSwept:
    def test_a_long_expired_code_is_deleted(self, temp_db):
        chat_id, persona_id = _persona_and_chat(temp_db)
        invite = guest.create_guest_invite(chat_id, persona_id)
        qi(
            "UPDATE guest_grants SET code_expires=? WHERE id=?",
            (time.time() - 30 * DAY, invite["grant_id"]),
        )

        assert guest.sweep_expired_access() == 1
        assert guest.list_grants(chat_id) == []

    def test_a_recently_expired_code_is_still_shown_to_the_host(self, temp_db):
        # Expiry is not the same question as usefulness: the invite the host
        # is asking about is the one that just stopped working.
        chat_id, persona_id = _persona_and_chat(temp_db)
        invite = guest.create_guest_invite(chat_id, persona_id)
        qi(
            "UPDATE guest_grants SET code_expires=? WHERE id=?",
            (time.time() - 60, invite["grant_id"]),
        )

        assert guest.sweep_expired_access() == 0
        assert len(guest.list_grants(chat_id)) == 1

    def test_a_redeemed_grant_lives_until_its_token_dies_too(self, temp_db):
        # The code expired long ago; the 24h token from it has not. Sweeping
        # on the code's clock alone would sign a guest out mid-session.
        chat_id, persona_id = _persona_and_chat(temp_db)
        invite = guest.create_guest_invite(chat_id, persona_id)
        now = time.time()
        qi(
            "UPDATE guest_grants SET code_expires=?, redeemed_at=?, "
            "token_hash=?, token_expires=? WHERE id=?",
            (now - 30 * DAY, now - 30 * DAY, "tok", now + DAY,
             invite["grant_id"]),
        )

        assert guest.sweep_expired_access() == 0
        assert len(guest.list_grants(chat_id)) == 1

    def test_an_unredeemed_grant_is_not_immortal(self, temp_db):
        # `token_expires` is NULL for a grant nobody used, and `NULL < ?` is
        # NULL -- so a predicate naming only the token clock keeps exactly the
        # rows that pile up.
        chat_id, persona_id = _persona_and_chat(temp_db)
        invite = guest.create_guest_invite(chat_id, persona_id)
        qi(
            "UPDATE guest_grants SET code_expires=?, token_expires=NULL "
            "WHERE id=?",
            (time.time() - 30 * DAY, invite["grant_id"]),
        )

        assert guest.sweep_expired_access() == 1
        assert q("SELECT id FROM guest_grants") == []

    def test_a_live_invite_is_untouched(self, temp_db):
        chat_id, persona_id = _persona_and_chat(temp_db)
        invite = guest.create_guest_invite(chat_id, persona_id)
        assert guest.sweep_expired_access() == 0
        assert guest.redeem_code(invite["code"]) is not None


class TestShutdownStopsBackgroundWork:
    @pytest.fixture(autouse=True)
    def _clean_queues(self):
        jobs.reset()
        yield
        jobs.reset()

    def test_leaving_the_lifespan_cancels_a_running_job(self, temp_db):
        started = threading.Event()
        stopped = threading.Event()

        def slow(job):
            started.set()
            for _ in range(500):
                if job.cancelled.is_set():
                    stopped.set()
                    return
                time.sleep(0.01)

        with TestClient(app_module.app):
            jobs.submit(1, "slow", slow)
            assert started.wait(2.0)
            assert jobs.active_jobs()

        assert stopped.wait(2.0), "shutdown left the job running"
        assert jobs.active_jobs() == []

    def test_shutdown_asks_both_schedulers(self, temp_db, monkeypatch):
        # Two queues, two owners, one shutdown. `outofband` is reached through
        # its own module-level entry point rather than by importing the
        # backdrop and ambience modules that hold the queues -- an eager import
        # edge web/app.py must not add.
        called = {}

        monkeypatch.setattr(
            jobs, "drain", lambda timeout=2.0: called.setdefault("jobs", timeout) and []
        )
        monkeypatch.setattr(
            outofband, "drain_all",
            lambda timeout=2.0: called.setdefault("outofband", timeout) and [],
        )

        with TestClient(app_module.app):
            pass

        assert "jobs" in called and "outofband" in called
        # A shutdown budget a person will wait through.
        assert called["jobs"] + called["outofband"] <= 5.0

    def test_work_that_will_not_stop_does_not_block_the_exit(
        self, temp_db, monkeypatch
    ):
        # Cancellation is cooperative: a job inside a provider call finishes
        # that call. The drain REPORTS what is still in flight; it must not
        # raise, and it must not wait past its budget.
        monkeypatch.setattr(jobs, "drain", lambda timeout=2.0: ["still running"])
        monkeypatch.setattr(
            outofband, "drain_all", lambda timeout=2.0: ["still running"]
        )
        started = time.monotonic()
        with TestClient(app_module.app):
            pass
        assert time.monotonic() - started < 10.0
