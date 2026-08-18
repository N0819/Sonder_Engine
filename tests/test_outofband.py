"""The bounded machinery under both out-of-band queues.

`backdrops.py` and `ambience.py` are twins, so they leaked identically: four
tables that grew with the KEY SPACE rather than with the work in flight, and no
way at all to stop work nothing wanted any more. The per-module reproductions
live beside each module (`TestTheGenerationLockTable`,
`TestTheResolutionLockTable`); what is pinned here is the shared pattern, so
the next module built to it cannot inherit the same two defects a third time.

Database-free on purpose, like `jobs.py`: scheduling is not a storage question
and none of this needs ENGINE_DB.
"""

from __future__ import annotations

import threading
import time

import pytest

from core import outofband


def _wait(pred, timeout=3.0):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.005)
    return False


class TestKeyedLocks:
    def test_the_table_does_not_grow_with_the_key_space(self):
        """The defect both modules shipped: an entry per distinct signature,
        pruned by nothing, kept for the life of the process."""
        locks = outofband.KeyedLocks()
        for i in range(500):
            with locks.hold("key%d" % i):
                pass
        assert len(locks) == 0

    def test_an_entry_is_not_dropped_while_somebody_waits_on_it(self):
        """The reason the old code gave for never pruning. A waiter blocked on
        a lock leaves no evidence it wants that lock, so a bare delete really
        would race it -- and two callers handed different lock objects for one
        key both pay for the identical picture, which is the expense the table
        exists to prevent.
        """
        locks = outofband.KeyedLocks()
        order = []
        holding = threading.Event()
        release = threading.Event()

        def first():
            with locks.hold("shared"):
                order.append("in")
                holding.set()
                release.wait(3.0)
                order.append("out")

        def second():
            holding.wait(3.0)
            with locks.hold("shared"):
                order.append("second")

        threads = [threading.Thread(target=first), threading.Thread(target=second)]
        for t in threads:
            t.start()
        assert holding.wait(3.0)
        assert len(locks) == 1
        release.set()
        for t in threads:
            t.join(3.0)

        assert order == ["in", "out", "second"]
        assert len(locks) == 0

    def test_a_key_is_released_when_the_held_block_raises(self):
        """An entry orphaned by a failure would be a leak with an extra step,
        and the lock would never be acquirable again."""
        locks = outofband.KeyedLocks()
        with pytest.raises(ValueError):
            with locks.hold("boom"):
                raise ValueError("provider said no")
        assert len(locks) == 0
        with locks.hold("boom"):
            pass
        assert len(locks) == 0


class TestTheQueue:
    def test_the_caller_never_waits_for_the_work(self):
        """The property both modules are built around: a route asks for a
        picture or a sound and gets an answer back, because the prose is
        already on screen and nothing may WAIT on either."""
        release = threading.Event()
        started = threading.Event()
        queue = outofband.Queue("test")

        def slow(work):
            started.set()
            release.wait(3.0)

        t0 = time.time()
        work = queue.submit("sig", slow)
        assert time.time() - t0 < 0.5
        assert _wait(started.is_set)
        release.set()
        assert _wait(lambda: work.state == "done")

    def test_the_same_signature_twice_is_one_piece_of_work(self):
        release = threading.Event()
        calls = []
        queue = outofband.Queue("test")

        def slow(work):
            calls.append(work)
            release.wait(3.0)

        first = queue.submit("sig", slow)
        assert _wait(lambda: first.state == "running")
        assert queue.submit("sig", slow) is None
        release.set()
        assert _wait(lambda: first.state == "done")
        assert len(calls) == 1

    def test_a_failure_is_recorded_rather_than_raised_at_the_caller(self):
        """`_LAST_ERROR` exists because out-of-band work that fails silently is
        worse than work that fails loudly: a picture that never appears and
        never explains itself is indistinguishable from one never asked for."""
        queue = outofband.Queue("test")

        def boom(work):
            raise ValueError("provider said no")

        work = queue.submit("sig", boom)
        assert _wait(lambda: work.state == "failed")
        assert queue.status("sig") == "error"
        assert queue.error("sig") == "ValueError: provider said no"

    def test_a_failure_nobody_came_back_for_stops_being_remembered(self):
        """The second leak, which the lock dicts hid: the only thing that ever
        removed an error entry was somebody asking for that exact signature
        again, and a reader who never walks back into that room never does.
        Measured on the unmodified modules: 500 failures, 500 entries kept.
        """
        queue = outofband.Queue("test")

        def boom(work):
            raise ValueError("no")

        for i in range(outofband.ERROR_LIMIT + 20):
            work = queue.submit("sig%03d" % i, boom)
            assert _wait(lambda: work.state == "failed")

        assert len(queue._errors) == outofband.ERROR_LIMIT
        assert queue.error("sig000") is None            # the oldest, evicted
        assert queue.error("sig%03d" % (outofband.ERROR_LIMIT + 19))

    def test_finished_work_leaves_the_active_table(self):
        queue = outofband.Queue("test")
        for i in range(200):
            work = queue.submit("sig%03d" % i, lambda work: True)
            assert _wait(lambda: work.state == "done")
        assert len(queue) == 0
        assert queue.active() == []

    def test_work_is_cancelled_between_steps_and_not_killed_mid_flight(self):
        """Neither queue had any cancellation path, so an image nobody was
        looking at any more ran to completion and was paid for. Cooperative on
        purpose: a call already inside a provider finishes it and is then filed
        as cancelled, because a half-written image is worse than a wasted one.
        """
        queue = outofband.Queue("test")
        finished_its_step = threading.Event()

        def cooperative(work):
            work.cancelled.wait(3.0)
            finished_its_step.set()     # the step it was inside completes
            return "partial"

        work = queue.submit("sig", cooperative, group=7)
        assert _wait(lambda: work.state == "running")
        assert queue.cancel_group(7) == 1
        assert _wait(lambda: work.state == "cancelled")
        assert finished_its_step.is_set()

    def test_cancelled_work_reports_absent_rather_than_error(self):
        """A stop somebody asked for is not a failure. Folding the two together
        would put 'error' in front of a reader for something nobody did wrong,
        and would cost the error table the one meaning it has."""
        queue = outofband.Queue("test")
        work = queue.submit("sig", lambda work: None, group=1)
        assert _wait(lambda: work.state == "done")
        work.cancelled.set()
        assert queue.status("sig") == "absent"
        assert queue.error("sig") is None

    def test_a_superseding_request_replaces_the_one_it_found_running(self):
        """An explicit force or reroll used to JOIN the work already in flight
        and return 'pending' -- so the caller waited and was handed back the
        very result they had asked to replace, by a queue reporting success.
        """
        queue = outofband.Queue("test")
        release = threading.Event()
        started = []

        def slow(work):
            started.append(work)
            release.wait(3.0)

        first = queue.submit("sig", slow)
        assert _wait(lambda: first.state == "running")
        second = queue.submit("sig", slow, supersede=True)

        assert second is not None and second is not first
        assert first.cancelled.is_set()
        release.set()
        assert _wait(lambda: second.state == "done")
        assert _wait(lambda: first.state == "cancelled")
        assert len(started) == 2

    def test_work_that_finishes_late_does_not_evict_what_replaced_it(self):
        """The incumbent is cancelled cooperatively, so it is still running when
        its replacement is registered. A bare delete on the way out would take
        the replacement's entry with it and the queue would report 'absent' for
        work that is very much in flight.
        """
        queue = outofband.Queue("test")
        release = threading.Event()
        hold_second = threading.Event()

        first = queue.submit("sig", lambda work: release.wait(3.0))
        assert _wait(lambda: first.state == "running")
        second = queue.submit("sig", lambda work: hold_second.wait(3.0),
                              supersede=True)
        assert _wait(lambda: second.state == "running")

        release.set()                       # the incumbent finishes LAST
        assert _wait(lambda: first.state == "cancelled")

        assert queue.status("sig") == "pending"
        hold_second.set()
        assert _wait(lambda: second.state == "done")
        assert queue.status("sig") == "absent"

    def test_two_signatures_run_at_once(self):
        """Out-of-band work runs in parallel: a barrier deadlocks unless both
        are genuinely in flight together."""
        queue = outofband.Queue("test")
        both = threading.Barrier(2, timeout=3.0)
        a = queue.submit("a", lambda work: both.wait())
        b = queue.submit("b", lambda work: both.wait())
        assert _wait(lambda: a.state == "done" and b.state == "done")

    def test_a_retry_is_not_reported_broken_while_it_runs(self):
        """A stale error left standing over a running retry is how a feature
        that is working reads as one that is not."""
        queue = outofband.Queue("test")
        work = queue.submit("sig", lambda work: (_ for _ in ()).throw(
            RuntimeError("nope")))
        assert _wait(lambda: queue.status("sig") == "error")

        release = threading.Event()
        queue.submit("sig", lambda work: release.wait(3.0))
        assert queue.status("sig") == "pending"
        assert queue.error("sig") is None
        release.set()


class TestStopped:
    def test_a_direct_caller_with_nothing_to_cancel_reads_correctly(self):
        """Every blocking caller of a generator passes None, and a guard each
        of them has to remember is a guard that gets forgotten."""
        assert outofband.stopped(None) is False
        work = outofband.Work("sig")
        assert outofband.stopped(work) is False
        work.cancelled.set()
        assert outofband.stopped(work) is True
