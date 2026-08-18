"""Autobiographical consolidation runs BETWEEN turns, never inside one.

The defect (chat 71 turn 10, measured live 2026-08-12): the first beat to
reach the consolidation cadence spent 29.5s of a 45.8s commit stage on
`_consolidate_committed_memories` -- a background summarisation job, run
synchronously inside the player's wait, on the `utility` role, which was
absent from `providers.ROLE_FALLBACKS` and so silently resolved to
`default` (the model the host picked for the hardest work in the engine, at
~57 tok/s). Reproduced offline: 29.47s for the 34-memory window, 27.38s of
it the one LLM call.

Summaries are reconstructible caches -- that is exactly why they were
already allowed to run after the write lock -- so nothing about correctness
changes when they move out of band beside the offscreen ticks; only who
waits for them. The constraints that must survive the move: abandonable
(cancellation between characters), no write lock held, a failure is silence
toward the turn rather than a broken beat, and a checkpoint restore must not
race a stale summary onto rows it just rolled back.
"""

from __future__ import annotations

import inspect
import json
import threading
import time

import pytest

import commit
# The consolidation producers resolve maybe_consolidate_character_memory in
# THEIR module's globals -- commit_memory_write since the split; patching
# the commit facade would be inert.
import commit_memory_write
import jobs
from character_schema import default_character_data
from pipeline_context import ChatData, PipelineContext, TurnData


@pytest.fixture(autouse=True)
def _clean_jobs():
    jobs.reset()
    yield
    jobs.reset()


def _make_ctx(temp_db, names=("Alice", "Bob")):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    for name in names:
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (name, json.dumps(default_character_data(name)), "{}",
             time.time(), f"char_{name}"),
        )
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) "
            "VALUES(?,?,?,?)", (chat_id, char_id, "active", "{}"),
        )
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 12, "test", time.time()),
    )
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,),
    )
    return PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=12,
                      player_input="test", created=time.time()),
        cast=cast, input="test",
    )


def _join(chat_id, timeout=5.0):
    """Wait for the consolidation job to reach a terminal state."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        state = jobs.status(chat_id, commit.MEMORY_CONSOLIDATION_JOB_KEY)
        if state not in ("pending", "running"):
            return state
        time.sleep(0.01)
    raise AssertionError("consolidation job never finished")


def test_the_commit_tail_schedules_rather_than_waits(temp_db, monkeypatch):
    """The caller gets its Job back immediately; the per-character work --
    the part that spends an LLM call each -- happens on the job thread,
    attempted for every cast member, with the turn's own idx and frame."""
    ctx = _make_ctx(temp_db)
    called = []
    started = threading.Event()
    release = threading.Event()

    def fake_maybe(cid, char_id, turn_idx, *, frame_id=None):
        started.set()
        release.wait(timeout=5)
        called.append((cid, char_id, turn_idx, frame_id))
        return {"summary": "updated"}

    monkeypatch.setattr(commit_memory_write,
                        "maybe_consolidate_character_memory", fake_maybe)
    t0 = time.time()
    job = commit.schedule_memory_consolidation(ctx)
    scheduled_in = time.time() - t0

    assert job is not None
    # The schedule returned while the first "LLM call" was still blocked --
    # nobody's wall clock includes the summarisation any more.
    assert started.wait(timeout=5)
    assert scheduled_in < 1.0
    assert not called
    release.set()
    assert _join(ctx.chat.id) == "done"
    assert sorted(c[1] for c in called) == sorted(
        row["id"] for row in ctx.cast)
    assert all(c[0] == ctx.chat.id and c[2] == 12 for c in called)


def test_one_characters_failure_is_silence_not_a_broken_turn(temp_db,
                                                             monkeypatch):
    """A failure for one character is logged and skipped: the others are
    still attempted, the job finishes 'done', and nothing raises into any
    caller -- background work cannot fail a player's turn."""
    ctx = _make_ctx(temp_db, names=("Alice", "Bob", "Cara"))
    called = []

    def fake_maybe(cid, char_id, turn_idx, *, frame_id=None):
        called.append(char_id)
        if len(called) == 2:
            raise RuntimeError("simulated consolidation failure")
        return {"summary": "updated"}

    monkeypatch.setattr(commit_memory_write,
                        "maybe_consolidate_character_memory", fake_maybe)
    job = commit.schedule_memory_consolidation(ctx)
    assert _join(ctx.chat.id) == "done"
    assert len(called) == 3
    assert job.error == ""
    # Two of three consolidated; the failure cost only its own note.
    assert len(job.result) == 2


def test_a_second_beat_joins_the_running_job_instead_of_stacking(
        temp_db, monkeypatch):
    """Deduped on the chat: a consolidation still in flight when the next
    beat commits keeps running and that beat schedules nothing new. The
    cadence check re-reads its cursor next time, so a skipped window is
    deferred, never lost."""
    ctx = _make_ctx(temp_db)
    release = threading.Event()
    monkeypatch.setattr(
        commit_memory_write, "maybe_consolidate_character_memory",
        lambda *a, **k: release.wait(timeout=5) and None)

    first = commit.schedule_memory_consolidation(ctx)
    second = commit.schedule_memory_consolidation(ctx)
    assert first is not None
    assert second is first          # joined, not stacked
    release.set()
    _join(ctx.chat.id)


def test_cancellation_stops_between_characters(temp_db, monkeypatch):
    """Abandonable at every unit boundary: a cancel asked mid-run lets the
    in-flight character finish and consolidates nobody after it."""
    ctx = _make_ctx(temp_db, names=("Alice", "Bob", "Cara"))
    called = []
    first_started = threading.Event()
    release = threading.Event()

    def fake_maybe(cid, char_id, turn_idx, *, frame_id=None):
        called.append(char_id)
        first_started.set()
        release.wait(timeout=5)
        return None

    monkeypatch.setattr(commit_memory_write,
                        "maybe_consolidate_character_memory", fake_maybe)
    commit.schedule_memory_consolidation(ctx)
    assert first_started.wait(timeout=5)
    jobs.cancel(ctx.chat.id, commit.MEMORY_CONSOLIDATION_JOB_KEY)
    release.set()
    assert _join(ctx.chat.id) == "cancelled"
    assert len(called) == 1


def test_checkpoint_restore_cancels_the_inflight_job(temp_db, monkeypatch):
    """A summary computed from rows a restore is rolling back must not land
    afterward: restore_checkpoint asks the consolidation job -- and ONLY
    that job -- to stop. The offscreen ticks beside it are deliberately
    left running (their landings are provisional; a turn starting must
    never cancel them)."""
    import checkpoints

    ctx = _make_ctx(temp_db)
    temp_db.wset(ctx.chat.id, "scene", {"rooms": {}, "positions": {},
                                        "entities": {}})
    checkpoints.ensure_checkpoint(ctx.chat.id, 12)

    cancelled = []
    monkeypatch.setattr(jobs, "cancel",
                        lambda cid, key: cancelled.append((cid, key)))
    checkpoints.restore_checkpoint(ctx.chat.id, 12)
    assert cancelled == [(ctx.chat.id, commit.MEMORY_CONSOLIDATION_JOB_KEY)]


def test_the_commit_tail_no_longer_blocks_on_consolidation():
    """Superseded by `tests/test_commit_tail_producers.py`.

    This asserted a substring of `inspect.getsource`, which cannot fail on a
    behavioural change: `job = None if True else schedule_memory_consolidation(ctx)`
    keeps the text and never runs the call. The replacement drives a real
    commit and asserts the producer was reached.
    """
    import tests.test_commit_tail_producers  # noqa: F401  (the real cover)
def test_utility_is_configured_not_inherited(monkeypatch):
    """`utility` is the background helper lane (memory consolidation above
    all), and unset it follows `default` -- the model hosts pick for their
    hardest work.

    That is the arrangement under which a 27.4s summarisation call once
    landed inside a live commit, and it is deliberate again: `utility` spent
    a while inheriting `mapping` to dodge that, which fixed the symptom by
    means of an inheritance no host could see. The defect was the call being
    INSIDE the turn, and that is fixed above -- consolidation is scheduled
    out of band, so a slow default now costs money and background time
    rather than the player's wall clock. A host who wants the helper lane on
    a cheap model sets this row, where the choice is visible.

    Load-bearing consequence: if a background lane is ever moved back onto
    the turn's critical path, it needs its own role SET, not a fallback
    re-added under it."""
    import providers

    monkeypatch.setattr(providers, "provider",
                        lambda name: {"name": name, "kind": "openai",
                                      "base_url": "http://x", "api_key": ""})

    monkeypatch.setattr(providers, "agent_models", lambda: {
        "default": {"provider": "frontier", "model": "big"},
        "mapping": {"provider": "cheap", "model": "fast"},
    })
    prov, model, _cfg = providers.resolve_role("utility")
    assert (prov["name"], model) == ("frontier", "big")

    monkeypatch.setattr(providers, "agent_models", lambda: {
        "default": {"provider": "frontier", "model": "big"},
        "mapping": {"provider": "cheap", "model": "fast"},
        "utility": {"provider": "own", "model": "chosen"},
    })
    prov, model, _cfg = providers.resolve_role("utility")
    assert (prov["name"], model) == ("own", "chosen")

    monkeypatch.setattr(providers, "agent_models", lambda: {
        "default": {"provider": "frontier", "model": "big"},
    })
    prov, model, _cfg = providers.resolve_role("utility")
    assert (prov["name"], model) == ("frontier", "big")
