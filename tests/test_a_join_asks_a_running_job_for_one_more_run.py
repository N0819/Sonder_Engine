"""A submit that finds work already running on an older world asks it for
one more run (`core.jobs.submit_latest`); a cancelled job is never joined;
a restore stops only the work that read a beat it discards.

`submit` joins a job in flight, which is right for work whose answer does
not depend on when it started and wrong for work that read the world once
and works from what it read. Measured on the rooms built in view (review of
the 2026-10-08 landing): a design run outlasts a sub-minute beat, so the
next beat's commit joined a run that never saw its view, and the room that
beat brought into view waited for the first commit after the run ended.

No database: scheduling is not a storage question.
"""

import threading
import time

import pytest

from core import jobs


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


def test_a_join_asks_a_running_job_for_one_more_run_under_the_newest_turn():
    """Two commits land while the job runs: they fold into ONE more run,
    which reads the newest turn that asked -- bounded by the commits, never
    one run per ask stacked up."""
    started, release = threading.Event(), threading.Event()
    seen = []

    def work(job):
        seen.append(job.base_turn)
        started.set()
        release.wait(3.0)
        return len(seen)

    job = jobs.submit_latest(1, "design", work, base_turn=4)
    assert started.wait(3.0)
    assert jobs.submit_latest(1, "design", work, base_turn=6) is job
    assert jobs.submit_latest(1, "design", work, base_turn=5) is job
    release.set()
    assert _wait(lambda: job.state == "done")
    assert seen == [4, 6], "one more run, under the newest turn that asked"
    assert job.base_turn == 6 and job.result == 2


def test_an_ask_after_the_jobs_last_look_is_never_lost():
    """The ask that lands after the job's work is done but before it gives
    up its slot -- here, made from inside the run's last moment -- is seen:
    the decision to finish is taken under the lock the ask is made under."""
    seen = []

    def work(job):
        seen.append(job.base_turn)
        if len(seen) == 1:
            assert jobs.submit_latest(2, "design", work, base_turn=9) is job
        return None

    job = jobs.submit_latest(2, "design", work, base_turn=8)
    assert _wait(lambda: job.state == "done")
    assert seen == [8, 9]


def test_an_ask_made_during_a_run_that_raises_is_still_run():
    """A commit asks while the run works, and the run then raises -- in the
    room design job, anything outside its per-room guard: the actors, the
    plan's briefs, the install's test, a card load. The ask is not lost with
    the failure: the job runs once more under the asking turn, on the world
    that commit left, and the failure stays on the record. A follow-up that
    raises too ends the job failed, with nothing more to run. Before, the
    exception path released the slot without looking, and the view that
    commit brought into reach waited for the next commit (review of the
    2026-10-08 rooms-in-view landing, round 3)."""
    for chat_id, follow_up_raises in ((7, False), (8, True)):
        started, release = threading.Event(), threading.Event()
        seen = []

        def work(job, seen=seen, started=started, release=release,
                 follow_up_raises=follow_up_raises):
            seen.append(job.base_turn)
            if len(seen) == 1:
                started.set()
                release.wait(3.0)
                raise RuntimeError("the plan could not be read")
            if follow_up_raises:
                raise RuntimeError("the plan still could not be read")
            return "designed"

        job = jobs.submit_latest(chat_id, "design", work, base_turn=4)
        assert started.wait(3.0)
        assert jobs.submit_latest(chat_id, "design", work, base_turn=5) is job
        release.set()
        assert _wait(lambda: job.state not in ("pending", "running"))
        assert seen == [4, 5], "the ask made during the failed run is run"
        assert job.base_turn == 5
        if follow_up_raises:
            assert job.state == "failed" and "still could not" in job.error
        else:
            assert job.state == "done" and job.result == "designed"
            assert "could not be read" in job.error, "the failure is recorded"
        assert jobs.active_jobs(chat_id) == []


def test_a_job_not_yet_running_is_joined_and_asked_nothing():
    """A pending job has read nothing yet: it reads the world as it stands
    when it starts, so a join then asks it for no second run."""
    held = jobs.Job(3, "design", 1)
    with jobs._LOCK:
        jobs._ACTIVE[(3, "design")] = held
    assert jobs.submit_latest(3, "design", lambda job: None, base_turn=2) is held
    assert held.asked_again is False and held.again_turn is None


def test_plain_submit_never_asks_again():
    """Only `submit_latest` asks; work that joined through `submit` runs
    once, as it always did."""
    started, release = threading.Event(), threading.Event()
    runs = []

    def work(job):
        runs.append(job.base_turn)
        started.set()
        release.wait(3.0)

    job = jobs.submit(4, "consolidate", work, base_turn=1)
    assert started.wait(3.0)
    assert jobs.submit(4, "consolidate", work, base_turn=2) is job
    release.set()
    assert _wait(lambda: job.state == "done")
    assert runs == [1]


def test_a_cancelled_job_is_never_joined_or_asked_again():
    """A restore cancels a run that read a discarded beat; the reroll's own
    commit, landing while that run is still inside its call, starts a fresh
    job instead of joining work told to write nothing -- and the cancelled
    job does not run again on an ask."""
    started, release = threading.Event(), threading.Event()
    runs = []

    def work(job):
        runs.append(job.base_turn)
        started.set()
        release.wait(3.0)

    old = jobs.submit_latest(5, "design", work, base_turn=7)
    assert started.wait(3.0)
    jobs.cancel(5, "design")
    fresh = jobs.submit_latest(5, "design", work, base_turn=7)
    assert fresh is not old
    release.set()
    assert _wait(lambda: old.state == "cancelled" and fresh.state == "done")
    assert runs == [7, 7], "the old run once, the fresh one once"
    assert jobs.status(5, "design") == "done"


def test_a_restore_stops_only_the_work_that_read_a_beat_it_discards():
    """Restoring checkpoint N discards beat N and after: a job based at N is
    stopped, one based before N goes on, and one with no stamp is stopped --
    the absence of a stamp is no evidence it read nothing discarded."""
    release = threading.Event()
    kept = jobs.submit(6, "a", lambda job: release.wait(3.0), base_turn=4)
    gone = jobs.submit(6, "b", lambda job: release.wait(3.0), base_turn=5)
    blind = jobs.submit(6, "c", lambda job: release.wait(3.0))
    assert jobs.cancel_from(6, "a", 5) is None
    assert jobs.cancel_from(6, "b", 5) is gone
    assert jobs.cancel_from(6, "c", 5) is blind
    assert not jobs.is_cancelled(kept) and jobs.is_cancelled(gone)
    assert jobs.is_cancelled(None) is False
    release.set()
    assert _wait(lambda: kept.state == "done" and gone.state == "cancelled")
