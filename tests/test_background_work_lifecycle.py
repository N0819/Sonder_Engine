"""What happens to background work when the START fails, not the work.

`core/jobs.py` and `core/outofband.py` both promise the same thing: submitting
never raises into the caller, and a failure is RECORDED rather than thrown.
Both kept that promise for the function they were handed and broke it for the
thread they had to start first -- the slot was published before anything could
run in it, so a `RuntimeError: can't start new thread` left a key or a
signature occupied by a worker that does not exist, for the life of the
process. That is durable damage rather than one lost job: neither module
supersedes on the ordinary path, so every later request for that key joins the
dead record and polls until it gives up.

The reproduction technique is the same in every test here -- monkeypatch
`threading.Thread.start` to raise, which is exactly what thread exhaustion
does.

Database-free, like the two modules and their own suites: scheduling is not a
storage question.
"""

from __future__ import annotations

import threading
import time

import pytest

from core import jobs, outofband


@pytest.fixture(autouse=True)
def _clean_queue():
    jobs.reset()
    yield
    jobs.reset()


def _wait(pred, timeout=3.0):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.005)
    return False


def _refuse_to_start(self):
    raise RuntimeError("can't start new thread")


class TestAJobThatCannotStart:
    def test_a_thread_that_will_not_start_files_the_job_rather_than_stranding_it(
            self, monkeypatch):
        """The (chat_id, key) slot was published before the thread existed, and
        jobs.py has no supersede: memory consolidation for that chat then never
        ran again until the process restarted, reporting 'pending' throughout.
        """
        monkeypatch.setattr(threading.Thread, "start", _refuse_to_start)
        job = jobs.submit(7, "compact", lambda _job: None)
        monkeypatch.undo()

        assert job.state == "failed"
        assert job.error.startswith("RuntimeError:")
        assert jobs.status(7, "compact") == "failed"
        assert jobs.active_jobs(7) == []
        assert job in jobs.history(7)

    def test_the_key_is_free_for_the_next_submit(self, monkeypatch):
        monkeypatch.setattr(threading.Thread, "start", _refuse_to_start)
        dead = jobs.submit(7, "compact", lambda _job: None)
        monkeypatch.undo()

        ran = threading.Event()
        second = jobs.submit(7, "compact", lambda _job: ran.set())
        assert second is not dead
        assert _wait(ran.is_set)
        assert _wait(lambda: second.state == "done")

    def test_submit_still_does_not_raise_into_the_turn(self, monkeypatch):
        """The module contract, and the reason production callers that already
        wrap this in a try are not what makes the behaviour correct."""
        monkeypatch.setattr(threading.Thread, "start", _refuse_to_start)
        jobs.submit(7, "unwrapped", lambda _job: None)   # must not raise

    def test_a_bootstrap_failure_inside_the_worker_files_the_job(self,
                                                                 monkeypatch):
        """`_clear_turn_scoped_context` ran before `_run`'s try, so anything it
        raised -- an import failure, most plausibly -- left the job pending in
        the active table with no thread behind it."""
        def boom():
            raise ImportError("llm.providers is half-initialised")

        monkeypatch.setattr(jobs, "_clear_turn_scoped_context", boom)
        job = jobs.submit(8, "tick", lambda _job: "never reached")
        assert _wait(lambda: job.state == "failed")
        assert job.error.startswith("ImportError:")
        assert jobs.active_jobs(8) == []


class TestAReplacementThatCannotStart:
    def test_the_incumbent_is_not_invalidated_until_the_replacement_can_run(
            self, monkeypatch):
        """`existing.cancelled.set()` came BEFORE `Thread.start()`, so a forced
        backdrop regeneration that could not get a thread killed the generation
        that was working and left the signature occupied by the replacement
        that never started. Only another forced reroll could clear it; every
        ordinary later request for that room's picture joined the dead record
        and polled to its 75s budget.
        """
        queue = outofband.Queue("test")
        release = threading.Event()
        first = queue.submit("sig", lambda work: release.wait(3.0))
        assert _wait(lambda: first.state == "running")

        monkeypatch.setattr(threading.Thread, "start", _refuse_to_start)
        second = queue.submit("sig", lambda work: None, supersede=True)
        monkeypatch.undo()

        assert not first.cancelled.is_set()
        assert second.state == "failed"
        assert queue.error("sig").startswith("RuntimeError:")
        assert queue.status("sig") == "pending"     # the incumbent, still live

        release.set()
        assert _wait(lambda: first.state == "done")
        assert queue.status("sig") == "absent"

    def test_an_ordinary_later_request_is_not_joined_to_a_dead_worker(
            self, monkeypatch):
        queue = outofband.Queue("test")
        release = threading.Event()
        first = queue.submit("sig", lambda work: release.wait(3.0))
        assert _wait(lambda: first.state == "running")
        release.set()
        assert _wait(lambda: first.state == "done")

        monkeypatch.setattr(threading.Thread, "start", _refuse_to_start)
        queue.submit("sig", lambda work: None)      # must not raise
        monkeypatch.undo()

        ran = threading.Event()
        assert queue.submit("sig", lambda work: ran.set()) is not None
        assert _wait(ran.is_set)
        assert _wait(lambda: len(queue) == 0)

    def test_submit_does_not_raise_at_the_route(self, monkeypatch):
        """The raise escaped unwrapped to the two backdrop/ambience routes,
        giving a 500 where the whole point of the queue is 'pending'."""
        queue = outofband.Queue("test")
        monkeypatch.setattr(threading.Thread, "start", _refuse_to_start)
        assert queue.submit("sig", lambda work: None) is not None


class TestAFailureThatIsNotOurs:
    def test_a_superseded_failure_does_not_report_error_over_its_replacement(
            self):
        """`_retire` was identity-checked and `self._errors[...] = message` was
        not, so the attempt a reroll REPLACED could file its message over the
        reroll that succeeded -- a working feature reading as a broken one."""
        queue = outofband.Queue("test")
        release = threading.Event()

        def incumbent(work):
            release.wait(3.0)
            raise ValueError("the attempt nobody is waiting on")

        first = queue.submit("sig", incumbent)
        assert _wait(lambda: first.state == "running")
        second = queue.submit("sig", lambda work: "fresh picture",
                              supersede=True)
        assert _wait(lambda: second.state == "done")

        release.set()
        assert _wait(lambda: first.state == "failed")
        assert queue.status("sig") == "absent"
        assert queue.error("sig") is None

    def test_a_signature_that_succeeded_stops_reporting_a_failure(self):
        """`submit` clears the last failure when a fresh attempt STARTS, and
        nothing cleared it when one finished -- so a message written while the
        successful attempt was already running outlived it."""
        queue = outofband.Queue("test")
        release = threading.Event()
        work = queue.submit("sig", lambda w: release.wait(3.0))
        assert _wait(lambda: work.state == "running")

        with queue._guard:      # the write a late sibling used to make
            queue._errors["sig"] = "ValueError: an older attempt"

        release.set()
        assert _wait(lambda: work.state == "done")
        assert queue.error("sig") is None
        assert queue.status("sig") == "absent"


class TestResetAndWorkAlreadyRunning:
    def test_a_job_finishing_after_reset_writes_nothing_back(self):
        """`reset()` documents that it does not stop running threads. What it
        must also do is make them inert: a worker released after the tables
        were cleared put its record into the next test's history."""
        release = threading.Event()
        job = jobs.submit(9, "slow", lambda _job: release.wait(3.0))
        assert _wait(lambda: job.state == "running")

        jobs.reset()
        release.set()
        assert _wait(lambda: job.state in ("done", "cancelled"))

        assert jobs.history(9) == []
        assert jobs.active_jobs(9) == []
        assert jobs.status(9, "slow") == "absent"

    def test_work_failing_after_reset_writes_nothing_back(self):
        queue = outofband.Queue("test")
        release = threading.Event()

        def late(work):
            release.wait(3.0)
            raise ValueError("late")

        work = queue.submit("sig", late)
        assert _wait(lambda: work.state == "running")

        queue.reset()
        release.set()
        assert _wait(lambda: work.state == "failed")

        assert queue.error("sig") is None
        assert queue.status("sig") == "absent"
        assert len(queue) == 0


class TestDrainingForShutdown:
    def test_drain_stops_cooperative_work_and_reports_an_empty_queue(self):
        job = jobs.submit(10, "tick", lambda j: j.cancelled.wait(3.0))
        assert _wait(lambda: job.state == "running")

        assert jobs.drain(timeout=3.0) == []
        assert job.state == "cancelled"

    def test_drain_names_what_it_could_not_stop_rather_than_waiting_on_it(self):
        """Cancellation is cooperative, so a shutdown budget can expire with
        work still inside a provider call. The threads are daemons; what drain
        owes the caller is an honest list, not a join."""
        release = threading.Event()
        job = jobs.submit(11, "stubborn", lambda _job: release.wait(5.0))
        assert _wait(lambda: job.state == "running")

        t0 = time.time()
        left = jobs.drain(timeout=0.2)
        assert time.time() - t0 < 2.0
        assert left == [job]

        release.set()
        assert _wait(lambda: job.state in ("done", "cancelled"))

    def test_cancel_all_reaches_every_chat(self):
        a = jobs.submit(12, "tick", lambda j: j.cancelled.wait(3.0))
        b = jobs.submit(13, "tick", lambda j: j.cancelled.wait(3.0))
        assert _wait(lambda: a.state == "running" and b.state == "running")

        assert jobs.cancel_all() == 2
        assert _wait(lambda: a.state == "cancelled" and b.state == "cancelled")

    def test_drain_all_reaches_a_queue_the_caller_never_imported(self):
        """The two live queues belong to `backdrops` and `ambience`; a process
        shutting down should not have to import either to stop them."""
        queue = outofband.Queue("test")
        work = queue.submit("sig", lambda w: w.cancelled.wait(3.0))
        assert _wait(lambda: work.state == "running")

        assert outofband.drain_all(timeout=3.0) == []
        assert work.state == "cancelled"
        assert len(queue) == 0
