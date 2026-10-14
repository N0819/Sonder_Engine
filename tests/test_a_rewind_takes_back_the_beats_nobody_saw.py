"""A rewind takes back the off-screen beats nobody saw (`persist/beat_order.py`).

The owner, 2026-10-13: "undo-and-replay". Home 10 (chat 173, docs/
experiments/OBSERVE_2026_10_13_home10.md items 3 and 6):

* every commit of the player's beat schedules each live bubble's beat, which
  takes the next turn number -- so while a bubble lived the player's newest
  page could never be rerolled, edited or deleted ("another frame has
  advanced"), and an edit to it skipped its recompute in silence;
* a bubble beat numbered BELOW the page, finishing after the page began, was
  erased by rewinding the page while its rows stood (turn 2 in chats 167, 170
  and 173).

A checkpoint is an instant: `turns.commit_seq` records the order commits land
in and `checkpoints.commit_seq` the newest one a checkpoint holds. A rewind
takes back, inside its own restore, the unseen beats of bubbles split from the
page's frame that ran after it began; a beat somebody played still refuses.
"""
from __future__ import annotations

import json
import threading
import time

import pytest
from fastapi import HTTPException


def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Home", "", time.time()))


def _frame(db, cid, *, kind="spatial", parent=None, label="Bubble — Tamamo"):
    from core.frames import create_frame
    return create_frame(cid, label=label, ordinal=0, kind=kind,
                        parent_frame_id=parent, split_turn_idx=0)


def _turn(db, cid, idx, frame_id=None, typed="", committed=True, seq=None, narrated=False):
    tid = db.qi("INSERT INTO turns(chat_id,idx,player_input,created,frame_id,commit_seq) "
                "VALUES(?,?,?,?,?,?)", (cid, idx, typed, time.time(), frame_id, seq))
    keys = ["director_interpret"] + (["narrator"] if narrated else []) + (["commit"] if committed else [])
    for order, key in enumerate(keys):
        sid = db.qi("INSERT INTO steps(turn_id,key,ord,label) VALUES(?,?,?,?)",
                    (tid, key, order, key))
        db.qi("INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
              (sid, "{}", time.time()))
    return tid


def _offscreen_slot():
    """The abort event an off-screen beat holds its slot with."""
    event = threading.Event()
    event.offscreen_beat = True
    return event


def _row(db, tid):
    return dict(db.q("SELECT * FROM turns WHERE id=?", (tid,), one=True))


def _checkpoint(db, cid, idx, seq):
    from persist.checkpoints import ensure_checkpoint
    ensure_checkpoint(cid, idx)
    db.qi("UPDATE checkpoints SET commit_seq=? WHERE chat_id=? AND turn_idx=?", (seq, cid, idx))


# ------------------------------------------------------------ the record


class TestTheOrderCommitsLandIn:
    def test_a_commit_is_stamped_with_the_chats_next_number(self, temp_db):
        from persist import beat_order
        cid = _chat(temp_db)
        a = _turn(temp_db, cid, 0)
        b = _turn(temp_db, cid, 1)
        assert beat_order.stamp_commit(cid, b) == 1
        assert beat_order.stamp_commit(cid, a) == 2, "the order they LANDED in"
        assert beat_order.latest_commit_seq(cid) == 2

    def test_the_stamp_is_the_commits_last_write_inside_its_transaction(self):
        import inspect
        from persist import commit
        source = inspect.getsource(commit._commit_all_locked)
        stamp = source.index("beat_order.stamp_commit(")
        assert source.index("run_commit_domains(ctx, results)") < stamp \
            < source.index("except Exception as exc:"), "inside the transaction, last"

    def test_a_checkpoint_records_the_newest_commit_it_holds(self, temp_db):
        from persist import beat_order
        from persist.checkpoints import ensure_checkpoint
        cid = _chat(temp_db)
        beat_order.stamp_commit(cid, _turn(temp_db, cid, 0))
        ensure_checkpoint(cid, 1)
        assert beat_order.checkpoint_seq(cid, 1) == 1

    def test_the_turn_writer_records_it_with_the_snapshot(self, temp_db):
        from persist import beat_order
        from web import app
        cid = _chat(temp_db)
        beat_order.stamp_commit(cid, _turn(temp_db, cid, 0))
        app._insert_turn_row(cid, None, "I wait.")
        assert beat_order.checkpoint_seq(cid, 1) == 1

    def test_an_older_file_gains_both_columns_and_keeps_its_rows_unknown(self, temp_db):
        db = temp_db
        cid = _chat(db)
        _turn(db, cid, 0)
        with db.transaction() as c:
            c.execute("ALTER TABLE turns DROP COLUMN commit_seq")
            c.execute("ALTER TABLE checkpoints DROP COLUMN commit_seq")
            c.execute("INSERT INTO schema_meta(key,value) VALUES('version','44') "
                      "ON CONFLICT(key) DO UPDATE SET value=excluded.value")
        db.close_connection()
        db.init()
        assert "commit_seq" in {r["name"] for r in db.q("PRAGMA table_info(turns)")}
        assert "commit_seq" in {r["name"] for r in db.q("PRAGMA table_info(checkpoints)")}
        assert db.q("SELECT commit_seq FROM turns WHERE chat_id=?", (cid,), one=True)["commit_seq"] is None


# ------------------------------------------------------------- the plan


class TestWhatARewindTakesBack:
    def _home(self, db):
        cid = _chat(db)
        bubble = _frame(db, cid, parent=None)
        page = _turn(db, cid, 2, typed="I look around.", narrated=True, seq=2)
        _checkpoint(db, cid, 2, 1)
        return cid, bubble, page

    def test_a_later_beat_nobody_saw_is_taken_back(self, temp_db):
        from persist import beat_order
        cid, bubble, page = self._home(temp_db)
        beat = _turn(temp_db, cid, 3, frame_id=bubble, seq=3)
        plan = beat_order.rewind_plan(cid, _row(temp_db, page))
        assert [r["id"] for r in plan["carried"]] == [beat] and not plan["blocking"]

    def test_an_earlier_beat_that_landed_after_the_page_began_is_taken_back(self, temp_db):
        """Home 10: Tamamo's beat was turn 1 and landed after turn 2's
        checkpoint was taken."""
        from persist import beat_order
        cid, bubble, page = self._home(temp_db)
        late = _turn(temp_db, cid, 1, frame_id=bubble, seq=3)
        early = _turn(temp_db, cid, 0, frame_id=bubble, seq=1)
        plan = beat_order.rewind_plan(cid, _row(temp_db, page))
        assert [r["id"] for r in plan["carried"]] == [late]
        assert early not in [r["id"] for r in plan["carried"]]

    def test_an_order_never_recorded_reads_as_it_always_did(self, temp_db):
        from persist import beat_order
        cid, bubble, page = self._home(temp_db)
        temp_db.qi("UPDATE checkpoints SET commit_seq=NULL WHERE chat_id=?", (cid,))
        _turn(temp_db, cid, 1, frame_id=bubble, seq=3)
        plan = beat_order.rewind_plan(cid, _row(temp_db, page))
        assert not plan["carried"] and not plan["blocking"]

    def test_a_beat_somebody_played_elsewhere_still_refuses(self, temp_db):
        from persist import beat_order
        cid, _bubble, page = self._home(temp_db)
        era = _frame(temp_db, cid, kind="future", label="Future")
        _turn(temp_db, cid, 3, frame_id=era, typed="go")
        plan = beat_order.rewind_plan(cid, _row(temp_db, page))
        assert plan["blocking"] and plan["reason"] == beat_order.ANOTHER_FRAME_ADVANCED

    def test_a_beat_a_host_typed_into_the_bubble_holds_its_thread(self, temp_db):
        from persist import beat_order
        cid, bubble, page = self._home(temp_db)
        _turn(temp_db, cid, 3, frame_id=bubble)
        _turn(temp_db, cid, 4, frame_id=bubble, typed="Tamamo waits.", narrated=True)
        plan = beat_order.rewind_plan(cid, _row(temp_db, page))
        assert not plan["carried"] and len(plan["blocking"]) == 2

    def test_a_bubble_split_from_another_frame_is_not_this_rewinds(self, temp_db):
        from persist import beat_order
        cid, _bubble, page = self._home(temp_db)
        era = _frame(temp_db, cid, kind="past", label="Before")
        theirs = _frame(temp_db, cid, parent=era, label="Bubble — Ren")
        _turn(temp_db, cid, 3, frame_id=theirs)
        assert beat_order.rewind_plan(cid, _row(temp_db, page))["blocking"]

    def test_a_beat_running_now_is_stopped_and_taken_back(self, temp_db):
        from persist import beat_order
        cid, bubble, page = self._home(temp_db)
        running = _turn(temp_db, cid, 1, frame_id=bubble, committed=False)
        plan = beat_order.rewind_plan(cid, _row(temp_db, page), running_frames={bubble: True})
        assert [r["id"] for r in plan["carried"]] == [running]
        assert plan["stop"] == [bubble]

    def test_a_bubble_whose_beat_has_no_row_yet_is_still_stopped(self, temp_db):
        from persist import beat_order
        cid, bubble, page = self._home(temp_db)
        plan = beat_order.rewind_plan(cid, _row(temp_db, page), running_frames={bubble: True})
        assert plan["stop"] == [bubble] and not plan["blocking"]


# ---------------------------------------------------------- the take-back


class TestTheRestoreTakesThemBack:
    def test_inside_its_own_transaction_with_the_world(self, temp_db):
        from persist import beat_order
        from persist.checkpoints import restore_checkpoint
        cid = _chat(temp_db)
        bubble = _frame(temp_db, cid)
        temp_db.wset(cid, "marker", "before the page")
        page = _turn(temp_db, cid, 2, typed="I look around.", narrated=True)
        _checkpoint(temp_db, cid, 2, 0)
        beat_order.stamp_commit(cid, page)
        beat = _turn(temp_db, cid, 3, frame_id=bubble)
        beat_order.stamp_commit(cid, beat)
        temp_db.wset(cid, "marker", "after both commits")
        restore_checkpoint(cid, 2, carried=[beat])
        assert temp_db.wget(cid, "marker") == "before the page"
        assert not temp_db.q("SELECT 1 FROM turns WHERE id=?", (beat,), one=True)
        assert _row(temp_db, page)["commit_seq"] is None, "its commit is taken back too"

    def test_a_restore_that_fails_keeps_them(self, temp_db, monkeypatch):
        from persist import checkpoints
        cid = _chat(temp_db)
        bubble = _frame(temp_db, cid)
        _turn(temp_db, cid, 2, typed="I look around.")
        _checkpoint(temp_db, cid, 2, 0)
        beat = _turn(temp_db, cid, 3, frame_id=bubble)

        def broken(*_a, **_k):
            raise RuntimeError("boom")
        monkeypatch.setattr(checkpoints, "_restore_frames", broken)
        with pytest.raises(RuntimeError):
            checkpoints.restore_checkpoint(cid, 2, carried=[beat])
        assert temp_db.q("SELECT 1 FROM turns WHERE id=?", (beat,), one=True)

    def test_the_runs_own_restore_decides_under_the_lock_and_sweeps_inside(self):
        import inspect
        from agents import runtime
        from persist import checkpoints
        source = inspect.getsource(runtime._run_pipeline)
        assert source.index("halt_off_screen_job(chat_id, turn_row[\"idx\"])") \
            < source.index("beat_order.decide(chat_id, turn_row") \
            < source.index("restore_checkpoint(chat_id, turn_row[\"idx\"], carried=_decide, "
                           "sweep_later=True)")
        body = inspect.getsource(checkpoints._restore_checkpoint_body)
        assert body.index("with transaction():") < body.index("rows = carried() if callable") \
            < body.index("take_back(chat_id, rows") \
            < body.index('qi("DELETE FROM checkpoints WHERE chat_id=? AND turn_idx>?"')


# ------------------------------------------------------------- the routes


def _story_with_a_bubble_beat_after_the_page(db):
    cid = _chat(db)
    bubble = _frame(db, cid)
    page = _turn(db, cid, 2, typed="I look around.", narrated=True)
    _checkpoint(db, cid, 2, 0)
    beat = _turn(db, cid, 3, frame_id=bubble)
    return cid, bubble, page, beat


class TestTheControlsWork:
    def test_the_newest_page_is_recomputable_while_a_bubble_lives(self, temp_db):
        from web import app
        cid, _bubble, page, beat = _story_with_a_bubble_beat_after_the_page(temp_db)
        plan = app._require_rewindable(_row(temp_db, page))
        assert [r["id"] for r in plan["carried"]] == [beat]
        result = app.pipeline_get(page)
        assert result["editable"] is True and result["blocked_by_other_frame"] is False

    def test_a_beat_running_now_is_no_reason_to_refuse(self, temp_db):
        from agents.runtime import ABORTS
        from web import app
        cid, bubble, page, _beat = _story_with_a_bubble_beat_after_the_page(temp_db)
        ABORTS[(cid, bubble)] = _offscreen_slot()
        try:
            assert app._require_rewindable(_row(temp_db, page))["stop"] == [bubble]
        finally:
            ABORTS.pop((cid, bubble), None)

    def test_a_beat_running_in_a_thread_this_rewind_does_not_touch_is_named(self, temp_db):
        from agents.runtime import ABORTS
        from web import app
        cid, _bubble, page, _beat = _story_with_a_bubble_beat_after_the_page(temp_db)
        era = _frame(temp_db, cid, kind="past", label="Before")
        theirs = _frame(temp_db, cid, parent=era, label="Bubble — Ren")
        ABORTS[(cid, theirs)] = _offscreen_slot()
        try:
            with pytest.raises(HTTPException) as refused:
                app._require_rewindable(_row(temp_db, page))
            assert "off-screen beat is running (Bubble — Ren)" in refused.value.detail
            assert "Abort it" not in refused.value.detail
        finally:
            ABORTS.pop((cid, theirs), None)

    def test_deleting_the_page_takes_the_beat_back_with_it(self, temp_db):
        from web import app
        cid, _bubble, page, beat = _story_with_a_bubble_beat_after_the_page(temp_db)
        assert app.turn_del(page) == {"ok": True, "carried": 1}
        assert not temp_db.q("SELECT 1 FROM turns WHERE id IN (?,?)", (page, beat), one=True)

    def test_an_edit_to_the_newest_page_recomputes_it(self, temp_db):
        """The chat's newest turn was the bubble's beat, so the edit was
        cosmetic: no step went stale, nothing recomputed."""
        from web import app
        cid, _bubble, page, _beat = _story_with_a_bubble_beat_after_the_page(temp_db)
        assert app.edit_input(page, {"input": "I look for Tamamo."})["latest"] is True
        assert temp_db.q("SELECT COUNT(*) AS n FROM steps WHERE turn_id=? AND stale=1",
                         (page,), one=True)["n"] > 0

    def test_the_run_says_what_it_took_back(self, temp_db):
        """Said where the take-back happens, so every route that rewinds --
        reroll, rerun, resume, a step's reroll -- says it, and says what was
        actually taken rather than what the route expected."""
        from persist import beat_order
        cid, _bubble, page, _beat = _story_with_a_bubble_beat_after_the_page(temp_db)
        plan = beat_order.rewind_plan(cid, _row(temp_db, page))
        notice = beat_order.carried_notice(plan)
        assert notice == {"type": "notice", "kind": "carried", "count": 1,
                          "labels": ["Bubble — Tamamo"]}
        assert beat_order.carried_notice({"carried": []}) is None

    def test_every_restore_in_the_run_is_followed_by_its_notice(self):
        import inspect
        import re
        from agents import runtime
        source = inspect.getsource(runtime._run_pipeline)
        calls = [m.start() for m in re.finditer(r"\n\s+_restore_and_refresh\(\)\n", source)]
        assert len(calls) == 3
        for at in calls:
            following = source[at:].split("\n")[2].strip()
            assert following == "yield from _restored_notice", following


class TestARunningBeatIsStopped:
    def test_its_abort_is_set_and_its_slot_waited_for(self):
        from agents import runtime
        event = _offscreen_slot()
        runtime.ABORTS[(999, 7)] = event

        def finish():
            event.wait(2)
            runtime.ABORTS.pop((999, 7), None)
        threading.Thread(target=finish, daemon=True).start()
        assert runtime.stop_off_screen_beats(999, [7], wait=3) == []
        assert event.is_set()

    def test_a_beat_taken_back_while_it_ran_leaves_nothing(self, temp_db, monkeypatch):
        from agents import offscreen_beat
        from world import spatial_frames
        cid = _chat(temp_db)
        db_persona = temp_db.qi("INSERT INTO personas(name,sheet) VALUES(?,?)", ("Hinami", "{}"))
        temp_db.qi("UPDATE chats SET persona_id=? WHERE id=?", (db_persona, cid))
        from story.character_schema import default_character_data
        char = temp_db.qi("INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
                          ("Tamamo", json.dumps(default_character_data("Tamamo")), "{}", time.time()))
        temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,'active','{}')",
                   (cid, char))
        temp_db.wset(cid, "scene", {"rooms": {"a": {"adjacent": []}, "b": {"adjacent": []}},
                                    "positions": {"Hinami": "a", "Tamamo": "b"}, "entities": {}})
        bubble = spatial_frames.perform_split(cid, None, 0, bubble=True, away_names=["Tamamo"])

        from agents.runtime import ABORTS

        def taken_back(chat_id, turn_id, frame_id=None, **_k):
            try:
                temp_db.qi("DELETE FROM turns WHERE id=?", (turn_id,))   # the rewind's take-back
                yield {"type": "aborted", "turn_id": turn_id}
            finally:
                ABORTS.pop((chat_id, frame_id), None)    # as the real run frees its slot
        monkeypatch.setattr("agents.runtime.run_pipeline", taken_back)
        out = offscreen_beat.run_offscreen_beat(cid, bubble)
        assert out["skipped"] == "stopped by a rewind while it ran"
        assert (cid, bubble) not in ABORTS


# ------------------------------------------------- the windows between reads


class TestNoBeatSlipsBetweenTheReads:
    def test_a_commit_landing_during_the_snapshot_is_read_again(self, temp_db):
        """The number is read before the snapshot, outside the lock; anything
        another connection committed between them may be in the blob, whole
        or in part, so both are read again under the lock."""
        from core.db import data_version
        from persist import beat_order
        cid = _chat(temp_db)
        tid = _turn(temp_db, cid, 0)
        version = data_version()
        held = beat_order.latest_commit_seq(cid)
        lands = threading.Thread(target=beat_order.stamp_commit, args=(cid, tid))
        lands.start()                                     # another connection
        lands.join()
        assert beat_order.settled(cid, held, "stale", lambda _c: "fresh", version) == (1, "fresh")
        version = data_version()
        assert beat_order.settled(cid, 1, "kept", lambda _c: "fresh", version) == (1, "kept")

    def test_a_commit_for_a_turn_taken_back_is_refused_whole(self, temp_db):
        from types import SimpleNamespace
        from persist import commit
        ctx = SimpleNamespace(turn=SimpleNamespace(id=987654, frame_id=None))
        with pytest.raises(RuntimeError, match="taken back by a rewind"):
            commit._refuse_a_taken_back_turn(ctx)
        cid = _chat(temp_db)
        ctx.turn.id = _turn(temp_db, cid, 0)
        commit._refuse_a_taken_back_turn(ctx)                     # stands: lands

    def test_the_refusal_is_asked_inside_the_commits_transaction(self):
        import inspect
        from persist import commit
        source = inspect.getsource(commit._commit_all_locked)
        assert source.index("with transaction(), registry_session():") \
            < source.index("_refuse_a_taken_back_turn(ctx)") \
            < source.index('"transit"')

    def test_the_job_is_cancelled_before_the_run_asks_what_is_running(self):
        """Otherwise the job starts the next bubble's beat during the stop's
        wait, and that beat runs across the restore."""
        import inspect
        from agents import runtime
        from web import app
        run = inspect.getsource(runtime._run_pipeline)
        assert run.index("halt_off_screen_job(chat_id, turn_row[\"idx\"])") \
            < run.index("stop_off_screen_beats(chat_id, beat_order.rewind_plan(")
        delete = inspect.getsource(app.turn_del)
        assert delete.index("halt_off_screen_job(") < delete.index("stop_off_screen_beats(") \
            < delete.index("beat_order.decide(") < delete.index("restore_checkpoint(")

    def test_a_beat_whose_job_was_cancelled_backs_out_after_its_claim(self, temp_db):
        from agents import offscreen_beat
        from agents.runtime import ABORTS
        from world import spatial_frames
        cid = _chat(temp_db)
        persona = temp_db.qi("INSERT INTO personas(name,sheet) VALUES(?,?)", ("Hinami", "{}"))
        temp_db.qi("UPDATE chats SET persona_id=? WHERE id=?", (persona, cid))
        from story.character_schema import default_character_data
        char = temp_db.qi("INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
                          ("Tamamo", json.dumps(default_character_data("Tamamo")), "{}", time.time()))
        temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,'active','{}')",
                   (cid, char))
        temp_db.wset(cid, "scene", {"rooms": {"a": {"adjacent": []}, "b": {"adjacent": []}},
                                    "positions": {"Hinami": "a", "Tamamo": "b"}, "entities": {}})
        bubble = spatial_frames.perform_split(cid, None, 0, bubble=True, away_names=["Tamamo"])
        cancelled = threading.Event()
        cancelled.set()
        out = offscreen_beat.run_offscreen_beat(cid, bubble, cancelled=cancelled)
        assert out["skipped"] == "its job was cancelled"
        assert (cid, bubble) not in ABORTS, "its slot is given back"
        assert not temp_db.q("SELECT 1 FROM turns WHERE chat_id=? AND frame_id=?",
                             (cid, bubble), one=True), "no row, no checkpoint"

    def test_the_stop_closes_the_beats_sockets_too(self, monkeypatch):
        from agents import runtime
        closed = []
        monkeypatch.setattr(runtime, "abort_live_requests", lambda ev: closed.append(ev) or 1)
        event = _offscreen_slot()
        runtime.ABORTS[(998, 3)] = event
        try:
            runtime.stop_off_screen_beats(998, [3], wait=0.05)
        finally:
            runtime.ABORTS.pop((998, 3), None)
        assert closed == [event] and event.is_set()

    def test_the_cancel_reaches_the_job(self, temp_db):
        """A cancel that raised inside its own guard would cancel nothing,
        silently."""
        from agents.offscreen_beat import OFFSCREEN_BEAT_JOB_KEY
        from core import jobs
        from persist.checkpoints import halt_off_screen_job
        release = threading.Event()
        job = jobs.submit(4242, OFFSCREEN_BEAT_JOB_KEY, lambda j: release.wait(5), base_turn=3)
        try:
            halt_off_screen_job(4242, 4)
            assert job.cancelled.is_set()
        finally:
            release.set()


class TestOnlyABubblesBeatIsTakenBack:
    def _away_party(self, db):
        """A spatial child of the main frame that the PLAYER walked into: a
        party split, not a bubble -- its scene places the player."""
        from core.db import wset_for_frame
        cid = _chat(db)
        persona = db.qi("INSERT INTO personas(name,sheet) VALUES(?,?)",
                        ("Hinami", json.dumps({"identity": {"name": "Hinami"}})))
        db.qi("UPDATE chats SET persona_id=? WHERE id=?", (persona, cid))
        away = _frame(db, cid, label="Away")
        wset_for_frame(cid, "scene", {"rooms": {"b": {"adjacent": []}},
                                      "positions": {"Hinami": "b"}, "entities": {}}, away)
        page = _turn(db, cid, 2, typed="I look around.", narrated=True)
        _checkpoint(db, cid, 2, 0)
        return cid, away, page

    def test_a_humans_turn_with_no_line_is_not_an_unseen_beat(self, temp_db):
        """An empty line is a beat the player let pass; in flight it has no
        page yet, and it is still the player's."""
        from persist import beat_order
        from world.spatial_frames import is_bubble_frame
        cid, away, page = self._away_party(temp_db)
        assert not is_bubble_frame(cid, away)
        theirs = _turn(temp_db, cid, 3, frame_id=away, committed=False)
        plan = beat_order.rewind_plan(cid, _row(temp_db, page), running_frames={away})
        assert [r["id"] for r in plan["blocking"]] == [theirs]
        assert not plan["carried"] and plan["stop"] == []

    def test_a_humans_frame_still_starting_its_turn_is_never_stopped(self, temp_db):
        from persist import beat_order
        cid, away, page = self._away_party(temp_db)
        plan = beat_order.rewind_plan(cid, _row(temp_db, page), running_frames={away})
        assert plan["stop"] == []

    def test_a_beat_taken_back_takes_its_memories_with_it(self, temp_db):
        """A snapshot written before checkpoints carried the memory bank puts
        none back, so the rows the beat minted would outlive it."""
        from persist import beat_order
        cid = _chat(temp_db)
        bubble = _frame(temp_db, cid)
        beat = _turn(temp_db, cid, 3, frame_id=bubble)
        char = temp_db.qi("INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
                          ("Tamamo", "{}", "{}", time.time()))
        columns = {r["name"] for r in temp_db.q("PRAGMA table_info(memories)")}
        row = {"chat_id": cid, "char_id": char, "turn_id": beat, "content": "The owls.",
               "created": time.time()}
        row = {k: v for k, v in row.items() if k in columns}
        temp_db.qi("INSERT INTO memories(%s) VALUES(%s)" % (",".join(row), ",".join("?" * len(row))),
                   tuple(row.values()))
        with temp_db.transaction():
            beat_order.take_back(cid, [beat], 2)
        assert not temp_db.q("SELECT 1 FROM memories WHERE content='The owls.'", one=True)


# ------------------------------------------------- the review of 2026-10-13


class TestTheRowSaysWhoWroteIt:
    def test_an_old_beat_that_died_part_way_does_not_hold_its_bubble(self, temp_db):
        """IN FLIGHT is a running frame's newest row: counting every row with
        no commit made one failed beat refuse each rewind while its bubble
        lived."""
        from persist import beat_order
        cid = _chat(temp_db)
        bubble = _frame(temp_db, cid)
        _turn(temp_db, cid, 3, frame_id=bubble, committed=False)          # died part-way
        _turn(temp_db, cid, 5, frame_id=bubble, seq=1)
        page = _turn(temp_db, cid, 6, typed="I look around.", narrated=True, seq=2)
        _checkpoint(temp_db, cid, 6, 1)
        plan = beat_order.rewind_plan(cid, _row(temp_db, page), running_frames={bubble: True})
        assert not plan["blocking"] and plan["stop"] == [bubble]
        running = _turn(temp_db, cid, 7, frame_id=bubble, committed=False)
        plan = beat_order.rewind_plan(cid, _row(temp_db, page), running_frames={bubble: True})
        assert [r["id"] for r in plan["carried"]] == [running] and not plan["blocking"]

    def test_a_row_a_human_sent_is_never_carried_whatever_its_frame_became(self, temp_db):
        """An empty Send into an away party that has since rejoined looks like
        an off-screen beat until its page is written; the row says otherwise."""
        from persist import beat_order
        cid = _chat(temp_db)
        away = _frame(temp_db, cid, label="Away — Dock")
        temp_db.qi("UPDATE frames SET merged_turn_idx=2 WHERE id=?", (away,))
        page = _turn(temp_db, cid, 2, typed="I look around.", narrated=True)
        _checkpoint(temp_db, cid, 2, 0)
        passed = _turn(temp_db, cid, 3, frame_id=away, committed=False)
        temp_db.qi("UPDATE turns SET offscreen=0 WHERE id=?", (passed,))
        plan = beat_order.rewind_plan(cid, _row(temp_db, page), running_frames={away: False})
        assert [r["id"] for r in plan["blocking"]] == [passed] and plan["stop"] == []

    def test_a_row_the_off_screen_beat_wrote_is_carried_by_its_mark(self, temp_db):
        from persist import beat_order
        cid = _chat(temp_db)
        bubble = _frame(temp_db, cid)
        page = _turn(temp_db, cid, 2, typed="I look around.", narrated=True)
        _checkpoint(temp_db, cid, 2, 0)
        beat = _turn(temp_db, cid, 3, frame_id=bubble)
        temp_db.qi("UPDATE turns SET offscreen=1 WHERE id=?", (beat,))
        assert [r["id"] for r in beat_order.rewind_plan(cid, _row(temp_db, page))["carried"]] == [beat]

    def test_a_humans_run_with_no_row_yet_is_never_stopped(self, temp_db):
        """A line typed into a bubble's thread holds its slot while its
        snapshot is read, before its row exists: only a slot the off-screen
        beat tagged is stopped."""
        from agents.runtime import ABORTS
        from persist import beat_order
        from web import app
        cid, bubble, page, _beat = _story_with_a_bubble_beat_after_the_page(temp_db)
        assert beat_order.rewind_plan(cid, _row(temp_db, page),
                                      running_frames={bubble: False})["stop"] == []
        ABORTS[(cid, bubble)] = threading.Event()                          # a host's run
        try:
            with pytest.raises(HTTPException) as refused:
                app._require_rewindable(_row(temp_db, page))
            assert "active pipeline" in refused.value.detail
        finally:
            ABORTS.pop((cid, bubble), None)

    def test_running_frames_says_whose_slot_it_is(self):
        from agents import runtime
        runtime.ABORTS[(997, 1)] = _offscreen_slot()
        runtime.ABORTS[(997, 2)] = threading.Event()
        try:
            assert runtime.running_frames(997) == {1: True, 2: False}
        finally:
            runtime.ABORTS.pop((997, 1), None)
            runtime.ABORTS.pop((997, 2), None)

    def test_every_writer_says_who_wrote_the_row(self, temp_db):
        from web import app
        cid = _chat(temp_db)
        tid = app._insert_turn_row(cid, None, "")
        assert _row(temp_db, tid)["offscreen"] == 0, "an empty Send is still a human's"


class TestDecidedUnderTheLock:
    def test_a_live_run_refuses_the_rewind_with_nothing_written(self, temp_db):
        from persist import beat_order
        from persist.checkpoints import restore_checkpoint
        cid, bubble, page, beat = _story_with_a_bubble_beat_after_the_page(temp_db)
        temp_db.wset(cid, "marker", "after both")
        with pytest.raises(beat_order.RewindRefused, match="still live"):
            restore_checkpoint(cid, 2, carried=lambda: beat_order.decide(
                cid, _row(temp_db, page), {bubble: True})["carried"])
        assert temp_db.wget(cid, "marker") == "after both"
        assert temp_db.q("SELECT 1 FROM turns WHERE id=?", (beat,), one=True)

    def test_the_rewinding_runs_own_slot_is_not_in_its_way(self, temp_db):
        from persist import beat_order
        cid, _bubble, page, beat = _story_with_a_bubble_beat_after_the_page(temp_db)
        plan = beat_order.decide(cid, _row(temp_db, page), {None: False}, own_frame=True)
        assert [r["id"] for r in plan["carried"]] == [beat]
        with pytest.raises(beat_order.RewindRefused):
            beat_order.decide(cid, _row(temp_db, page), {None: False})   # a delete's

    def test_the_decision_is_asked_inside_the_restores_transaction(self, temp_db):
        from core import db
        from persist.checkpoints import restore_checkpoint
        cid, _bubble, _page, _beat = _story_with_a_bubble_beat_after_the_page(temp_db)
        depth = []
        restore_checkpoint(cid, 2, carried=lambda: depth.append(int(getattr(db._local, "tx_depth", 0)))
                           or [])
        # first without the lock, so a refusal prepares and cancels nothing;
        # then under it, where the answer holds
        assert len(depth) == 2 and depth[0] == 0 and depth[1] >= 1

    def test_a_delete_refuses_when_a_run_started_while_it_waited(self, temp_db):
        from agents.runtime import ABORTS
        from web import app
        cid, _bubble, page, beat = _story_with_a_bubble_beat_after_the_page(temp_db)
        era = _frame(temp_db, cid, kind="past", label="Before")
        real_stop = app.__dict__.get("stop_off_screen_beats")
        from agents import runtime

        def a_line_is_sent_meanwhile(chat_id, frames, wait=5.0):
            ABORTS[(cid, era)] = threading.Event()
            return []
        original = runtime.stop_off_screen_beats
        runtime.stop_off_screen_beats = a_line_is_sent_meanwhile
        try:
            with pytest.raises(HTTPException) as refused:
                app.turn_del(page)
            assert refused.value.status_code == 409 and "still live" in refused.value.detail
        finally:
            runtime.stop_off_screen_beats = original
            ABORTS.pop((cid, era), None)
        assert temp_db.q("SELECT 1 FROM turns WHERE id=?", (page,), one=True)
        assert temp_db.q("SELECT 1 FROM turns WHERE id=?", (beat,), one=True)
        assert real_stop is None or callable(real_stop)

    def test_a_stopped_beat_writes_no_row(self, temp_db, monkeypatch):
        """Asked to stop while its snapshot was read, it backs out under the
        lock: either the rewind has not decided yet and sees its slot, or it
        has landed and this beat was asked to stop."""
        from agents import offscreen_beat
        from agents.runtime import ABORTS
        from persist import checkpoints
        from world import spatial_frames
        cid = _chat(temp_db)
        persona = temp_db.qi("INSERT INTO personas(name,sheet) VALUES(?,?)", ("Hinami", "{}"))
        temp_db.qi("UPDATE chats SET persona_id=? WHERE id=?", (persona, cid))
        from story.character_schema import default_character_data
        char = temp_db.qi("INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
                          ("Tamamo", json.dumps(default_character_data("Tamamo")), "{}", time.time()))
        temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,'active','{}')",
                   (cid, char))
        temp_db.wset(cid, "scene", {"rooms": {"a": {"adjacent": []}, "b": {"adjacent": []}},
                                    "positions": {"Hinami": "a", "Tamamo": "b"}, "entities": {}})
        bubble = spatial_frames.perform_split(cid, None, 0, bubble=True, away_names=["Tamamo"])
        real = checkpoints.snapshot_blob

        def stopped_meanwhile(chat_id):
            ABORTS[(cid, bubble)].set()
            return real(chat_id)
        monkeypatch.setattr(checkpoints, "snapshot_blob", stopped_meanwhile)
        out = offscreen_beat.run_offscreen_beat(cid, bubble)
        assert out["skipped"] == "stopped by a rewind before it began"
        assert (cid, bubble) not in ABORTS
        assert not temp_db.q("SELECT 1 FROM turns WHERE chat_id=? AND frame_id=?",
                             (cid, bubble), one=True)


class TestNothingIsTakenBackByAnotherTurnsId:
    def test_another_chats_row_is_never_touched(self, temp_db):
        from persist import beat_order
        mine, theirs = _chat(temp_db), _chat(temp_db)
        their_turn = _turn(temp_db, theirs, 0)
        with temp_db.transaction():
            beat_order.take_back(mine, [their_turn], 0)
        assert temp_db.q("SELECT 1 FROM turns WHERE id=?", (their_turn,), one=True)

    def test_a_commit_for_an_id_now_another_turns_is_refused(self, temp_db):
        from types import SimpleNamespace
        from persist import commit
        mine, theirs = _chat(temp_db), _chat(temp_db)
        tid = _turn(temp_db, theirs, 4)                  # the id, handed out again
        ctx = SimpleNamespace(turn=SimpleNamespace(id=tid, idx=4, frame_id=None),
                              chat=SimpleNamespace(id=mine))
        with pytest.raises(RuntimeError, match="taken back by a rewind"):
            commit._refuse_a_taken_back_turn(ctx)
        ctx.chat.id, ctx.turn.idx = theirs, 3            # this story, another place
        with pytest.raises(RuntimeError, match="taken back by a rewind"):
            commit._refuse_a_taken_back_turn(ctx)
        ctx.turn.idx = 4
        commit._refuse_a_taken_back_turn(ctx)

    def test_every_commit_the_checkpoint_does_not_hold_loses_its_number(self, temp_db):
        """A direct caller restores over a played beat with a warning; the
        number of a commit no longer in the world must not refuse the next
        rewind."""
        from persist import beat_order
        cid = _chat(temp_db)
        era = _frame(temp_db, cid, kind="future", label="Future")
        played = _turn(temp_db, cid, 1, frame_id=era, typed="go", seq=3)
        kept = _turn(temp_db, cid, 0, seq=1)
        with temp_db.transaction():
            beat_order.take_back(cid, [], 2, held=2)
        assert _row(temp_db, played)["commit_seq"] is None
        assert _row(temp_db, kept)["commit_seq"] == 1


class TestNoTurnAdoptsAnOrphan:
    def test_a_deleted_pages_lower_beat_leaves_no_checkpoint_to_adopt(self, temp_db):
        from persist import beat_order
        from web import app
        cid = _chat(temp_db)
        bubble = _frame(temp_db, cid)
        _turn(temp_db, cid, 0, narrated=True, seq=1)
        _checkpoint(temp_db, cid, 1, 1)
        late = _turn(temp_db, cid, 1, frame_id=bubble, seq=3)               # began first
        page = _turn(temp_db, cid, 2, typed="I look around.", narrated=True, seq=2)
        _checkpoint(temp_db, cid, 2, 1)                                     # landed after it
        assert [r["id"] for r in beat_order.rewind_plan(cid, _row(temp_db, page))["carried"]] == [late]
        assert app.turn_del(page) == {"ok": True, "carried": 1}
        assert [r["turn_idx"] for r in temp_db.q(
            "SELECT turn_idx FROM checkpoints WHERE chat_id=?", (cid,))] == []
        temp_db.wset(cid, "marker", "after the delete")
        fresh = app._insert_turn_row(cid, None, "I wait.")
        blob = json.loads(temp_db.q("SELECT blob FROM checkpoints WHERE chat_id=? AND turn_idx=?",
                                    (cid, _row(temp_db, fresh)["idx"]), one=True)["blob"])
        assert json.dumps(blob).count("after the delete") == 1

    def test_a_new_turn_never_adopts_a_stale_checkpoint(self, temp_db):
        from persist.checkpoints import ensure_checkpoint
        from web import app
        cid = _chat(temp_db)
        temp_db.wset(cid, "marker", "stale")
        ensure_checkpoint(cid, 0)                                           # nobody's
        temp_db.wset(cid, "marker", "now")
        tid = app._insert_turn_row(cid, None, "I wait.")
        blob = temp_db.q("SELECT blob FROM checkpoints WHERE chat_id=? AND turn_idx=?",
                         (cid, _row(temp_db, tid)["idx"]), one=True)["blob"]
        assert '"now"' in blob and '"stale"' not in blob


class TestTheControlsSayWhatIsTrue:
    def test_the_narration_picker_is_refused_only_by_a_later_beat(self, temp_db):
        """A choice between a turn's own pages restores nothing; a beat another
        frame began EARLIER never read this prose."""
        from web import app
        cid = _chat(temp_db)
        era = _frame(temp_db, cid, kind="past", label="Before")
        _turn(temp_db, cid, 1, frame_id=era, typed="go", narrated=True, seq=2)   # began first
        page = _turn(temp_db, cid, 2, typed="I look around.", narrated=True, seq=3)
        _checkpoint(temp_db, cid, 2, 1)
        variant = temp_db.q("SELECT v.id FROM variants v JOIN steps s ON s.id=v.step_id "
                            "WHERE s.turn_id=? AND s.key='narrator'", (page,), one=True)["id"]
        assert app.turn_narration_select(page, {"variant_id": variant})["ok"]
        _turn(temp_db, cid, 3, frame_id=era, typed="go on", narrated=True, seq=4)
        with pytest.raises(HTTPException):
            app.turn_narration_select(page, {"variant_id": variant})

    def test_a_line_sent_into_a_thread_whose_beat_runs_is_told_so(self, temp_db):
        from agents.runtime import ABORTS
        from web import app
        cid = _chat(temp_db)
        bubble = _frame(temp_db, cid)
        ABORTS[(cid, bubble)] = _offscreen_slot()
        try:
            with pytest.raises(HTTPException) as refused:
                app._require_frame_idle(cid, bubble)
            assert "off-screen beat is running (Bubble — Tamamo)" in refused.value.detail
        finally:
            ABORTS.pop((cid, bubble), None)


# ------------------------------------------------ the second review, 2026-10-13


def _stub_stages(monkeypatch):
    """Every stage a stub that writes nothing but its own row, so a reroll
    runs through the real `_run_pipeline` (`tests/test_concurrent_frames.py`'s
    harness)."""
    import agents.runtime as runtime

    def make(key):
        def handler(ctx, nonce):
            if key == "director_interpret":
                return {"flow": {"needs_mapping": False, "reactors": [], "resolution_flags": {}}}
            return {"prose": "The rain."} if key == "narrator" else {"ok": True}
        return handler
    for key in ("director_interpret", "mapping_quick", "perception_act",
                "director_resolve", "perception_outcome", "narrator", "commit"):
        monkeypatch.setitem(runtime.STEP_HANDLERS, key, make(key))


def _played_page_with_a_beat_after_it(db, monkeypatch):
    from agents.runtime import run_pipeline
    _stub_stages(monkeypatch)
    cid = _chat(db)
    page = db.qi("INSERT INTO turns(chat_id,idx,player_input,created,frame_id,offscreen) "
                 "VALUES(?,?,?,?,?,0)", (cid, 2, "I look around.", time.time(), None))
    list(run_pipeline(cid, page))
    bubble = _frame(db, cid)
    beat = _turn(db, cid, 3, frame_id=bubble)
    db.qi("UPDATE turns SET offscreen=1 WHERE id=?", (beat,))
    db.wset(cid, "marker", "after the page")
    return cid, bubble, page, beat


class TestAStopIsAStop:
    def test_a_stop_pressed_while_the_beat_is_stopped_rewinds_nothing(self, temp_db, monkeypatch):
        from agents import runtime
        cid, _bubble, page, beat = _played_page_with_a_beat_after_it(temp_db, monkeypatch)
        own = threading.Event()
        monkeypatch.setattr(runtime, "stop_off_screen_beats",
                            lambda chat_id, frames, wait=5.0: own.set() or [])
        events = list(runtime.run_pipeline(cid, page, abort=own))
        assert events[-1]["type"] == "aborted"
        assert temp_db.wget(cid, "marker") == "after the page"
        assert temp_db.q("SELECT 1 FROM turns WHERE id=?", (beat,), one=True)
        assert not temp_db.q("SELECT 1 FROM steps WHERE turn_id=? AND stale=1", (page,), one=True)

    def test_a_stop_after_the_restore_leaves_a_turn_that_offers_resume(self, temp_db, monkeypatch):
        """The restore took the commit back: a run stopped before the plan
        is built left the turn reading complete over a world without it."""
        from agents import resume_key_for_turn, runtime
        cid, _bubble, page, _beat = _played_page_with_a_beat_after_it(temp_db, monkeypatch)
        assert resume_key_for_turn(page, cid) is None
        own = threading.Event()
        real = runtime.restore_checkpoint

        def restored_then_stopped(*a, **k):
            real(*a, **k)
            own.set()
        monkeypatch.setattr(runtime, "restore_checkpoint", restored_then_stopped)
        events = list(runtime.run_pipeline(cid, page, abort=own))
        assert events[-1]["type"] == "aborted"
        assert resume_key_for_turn(page, cid) is not None

    def test_the_recompute_routes_refuse_a_played_beat_found_under_the_lock(self):
        import inspect
        from agents import runtime
        from web import app
        assert 'if refuse_blocking and plan["blocking"]:' in inspect.getsource(runtime._run_pipeline)
        for route in (app.turn_reroll, app.turn_rerun, app.turn_resume, app.step_reroll):
            assert "refuse_blocking=True" in inspect.getsource(route), route.__name__


class TestTheStopStopsOnlyAnOffScreenBeat:
    def test_a_humans_run_that_took_the_slot_since_is_left_alone(self):
        from agents import runtime
        human = threading.Event()
        runtime.ABORTS[(996, 4)] = human
        try:
            assert runtime.stop_off_screen_beats(996, [4], wait=0.05) == []
            assert not human.is_set()
        finally:
            runtime.ABORTS.pop((996, 4), None)

    def test_a_slot_is_tagged_as_it_is_claimed(self):
        from agents import runtime
        event = runtime.begin_pipeline(995, 2, offscreen_beat=True)
        try:
            assert runtime.running_frames(995) == {2: True} and event.offscreen_beat
        finally:
            runtime.ABORTS.pop((995, 2), None)


class TestAStoppedBeatTakesItselfAway:
    def test_a_beat_stopped_before_its_commit_leaves_nothing(self, temp_db, monkeypatch):
        """Its row, steps and checkpoint go by its own hand: once its slot is
        free the rewind may no longer count it, or may be refused."""
        from agents import offscreen_beat
        from agents.runtime import ABORTS
        from agents.storage import save_step
        from world import spatial_frames
        cid = _chat(temp_db)
        persona = temp_db.qi("INSERT INTO personas(name,sheet) VALUES(?,?)", ("Hinami", "{}"))
        temp_db.qi("UPDATE chats SET persona_id=? WHERE id=?", (persona, cid))
        from story.character_schema import default_character_data
        char = temp_db.qi("INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
                          ("Tamamo", json.dumps(default_character_data("Tamamo")), "{}", time.time()))
        temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,'active','{}')",
                   (cid, char))
        temp_db.wset(cid, "scene", {"rooms": {"a": {"adjacent": []}, "b": {"adjacent": []}},
                                    "positions": {"Hinami": "a", "Tamamo": "b"}, "entities": {}})
        bubble = spatial_frames.perform_split(cid, None, 0, bubble=True, away_names=["Tamamo"])

        def stopped_after_a_step(chat_id, turn_id, abort=None, frame_id=None, **_k):
            try:
                save_step(turn_id, "director_interpret", "Director", 0, {"ok": True})
                abort.set()                              # the rewind's stop
                yield {"type": "aborted", "turn_id": turn_id}
            finally:
                ABORTS.pop((chat_id, frame_id), None)
        monkeypatch.setattr("agents.runtime.run_pipeline", stopped_after_a_step)
        out = offscreen_beat.run_offscreen_beat(cid, bubble)
        assert out["skipped"] == "stopped by a rewind while it ran"
        assert not temp_db.q("SELECT 1 FROM turns WHERE chat_id=? AND frame_id=?", (cid, bubble), one=True)
        assert not temp_db.q("SELECT 1 FROM checkpoints WHERE chat_id=? AND turn_idx=?",
                             (cid, out["idx"]), one=True)


class TestARefusedRewindCancelsNothing:
    def test_the_jobs_are_asked_after_the_decision(self, temp_db, monkeypatch):
        from core import jobs
        from persist import beat_order
        from persist.checkpoints import restore_checkpoint
        cid, bubble, page, _beat = _story_with_a_bubble_beat_after_the_page(temp_db)
        cancelled = []
        monkeypatch.setattr(jobs, "cancel", lambda c, key: cancelled.append(key))
        monkeypatch.setattr(jobs, "cancel_from", lambda c, key, idx: cancelled.append(key))

        def refused():
            raise beat_order.RewindRefused("A run is still live")
        with pytest.raises(beat_order.RewindRefused):
            restore_checkpoint(cid, 2, carried=refused)
        assert cancelled == [], "asked before anything is prepared or cancelled"
        restore_checkpoint(cid, 2, carried=lambda: [])
        assert len(cancelled) > 2


class TestEveryCheckpointARewindCanRestoreHearsOfTheBooks:
    def test_a_lorebook_change_reaches_the_page_under_a_bubbles_beat(self, temp_db, monkeypatch):
        from web import app
        cid, _bubble, page, beat = _story_with_a_bubble_beat_after_the_page(temp_db)
        _checkpoint(temp_db, cid, 3, 0)
        refreshed = []
        monkeypatch.setattr(app, "refresh_checkpoint",
                            lambda c, idx, book_set_only=False: refreshed.append((idx, book_set_only)))
        app._refresh_rewindable_checkpoints(cid)
        # the chat's newest whole, as it always was; the page's book set only
        assert sorted(refreshed) == [(2, True), (3, False)]

    def test_a_frame_with_no_checkpoint_at_its_newest_turn_is_left_alone(self, temp_db, monkeypatch):
        """Written now, it would be the world after the chat's newest turn."""
        from web import app
        cid, _bubble, page, _beat = _story_with_a_bubble_beat_after_the_page(temp_db)
        temp_db.qi("DELETE FROM checkpoints WHERE chat_id=? AND turn_idx=2", (cid,))
        refreshed = []
        monkeypatch.setattr(app, "refresh_checkpoint",
                            lambda c, idx, book_set_only=False: refreshed.append(idx))
        app._refresh_rewindable_checkpoints(cid)
        assert refreshed == [3]


class TestAHostsWriteMakesTheBeatTheirs:
    def test_an_edited_off_screen_beat_holds_its_thread(self, temp_db):
        from persist import beat_order
        from web import app
        cid, _bubble, page, beat = _story_with_a_bubble_beat_after_the_page(temp_db)
        temp_db.qi("UPDATE turns SET offscreen=1 WHERE id=?", (beat,))
        app.edit_input(beat, {"input": "Tamamo puts the kettle on."})
        assert _row(temp_db, beat)["offscreen"] == 0
        assert [r["id"] for r in beat_order.rewind_plan(cid, _row(temp_db, page))["blocking"]] == [beat]


class TestTheWorldBrowserSaysWhatIsTrue:
    def test_an_edit_while_a_beat_runs_names_the_beat(self, temp_db):
        from agents.runtime import ABORTS
        from web import world_routes
        cid = _chat(temp_db)
        bubble = _frame(temp_db, cid)
        ABORTS[(cid, bubble)] = _offscreen_slot()
        try:
            with pytest.raises(HTTPException) as refused:
                world_routes._require_idle(cid)
            assert "off-screen beat is running (Bubble — Tamamo)" in refused.value.detail
        finally:
            ABORTS.pop((cid, bubble), None)


class TestABranchClaimsOnlyWhatItsWorldHolds:
    def test_a_copied_commit_the_branch_world_lacks_loses_its_number(self, temp_db):
        """Branch at a bubble's beat that landed after the next page began:
        the branch's world is that page's checkpoint, without the beat."""
        from persist import beat_order
        from web import app
        cid = _chat(temp_db)
        bubble = _frame(temp_db, cid)
        _turn(temp_db, cid, 0, narrated=True, seq=1)
        _checkpoint(temp_db, cid, 1, 1)
        beat = _turn(temp_db, cid, 1, frame_id=bubble, seq=3)
        temp_db.qi("UPDATE turns SET offscreen=1 WHERE id=?", (beat,))
        _turn(temp_db, cid, 2, typed="I look around.", narrated=True, seq=2)
        _checkpoint(temp_db, cid, 2, 1)
        branched = app.turn_branch(beat)
        ncid = branched.get("chat_id") or branched.get("id")
        assert beat_order.latest_commit_seq(ncid) == 1


# ------------------------------------------------- the third review, 2026-10-13


class TestTheEarlyMarkGivesBackWhatThePlanDoesNotRewrite:
    def test_a_step_the_new_plan_dropped_is_not_left_stale(self, temp_db, monkeypatch):
        """Kept for its variants, rewritten by nobody: left stale it made the
        page read "partly out of date" and refused every "Reroll only"."""
        from agents.runtime import run_pipeline
        from agents.storage import save_step
        _stub_stages(monkeypatch)
        cid = _chat(temp_db)
        page = temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created,frame_id,offscreen) "
                          "VALUES(?,?,?,?,?,0)", (cid, 2, "I look around.", time.time(), None))
        list(run_pipeline(cid, page))
        for _ in range(2):                      # an interaction the next plan drops
            save_step(page, "interaction_loop", "Characters", 3, {"ok": True})
        list(run_pipeline(cid, page))
        flags = {r["key"]: r["stale"] for r in temp_db.q(
            "SELECT key, stale FROM steps WHERE turn_id=?", (page,))}
        assert flags["interaction_loop"] == 0
        assert not any(flags.values()), flags

    def test_a_step_a_partial_rerun_hydrates_is_not_marked(self, temp_db, monkeypatch):
        from agents.runtime import run_pipeline
        _stub_stages(monkeypatch)
        cid = _chat(temp_db)
        page = temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created,frame_id,offscreen) "
                          "VALUES(?,?,?,?,?,0)", (cid, 2, "I look around.", time.time(), None))
        list(run_pipeline(cid, page))
        resolve = temp_db.q("SELECT ord FROM steps WHERE turn_id=? AND key='director_resolve'",
                            (page,), one=True)["ord"]
        # a plan that shrank since: a hydrated step now sits at the rerun's ord
        temp_db.qi("UPDATE steps SET ord=? WHERE turn_id=? AND key='perception_act'", (resolve, page))
        events = list(run_pipeline(cid, page, from_key="director_resolve"))
        assert events[-1]["type"] == "done", events[-1]
        assert temp_db.q("SELECT stale FROM steps WHERE turn_id=? AND key='perception_act'",
                         (page,), one=True)["stale"] == 0

    def test_a_commit_only_reroll_that_fails_offers_resume(self, temp_db, monkeypatch):
        from agents import resume_key_for_turn, runtime
        _stub_stages(monkeypatch)
        cid = _chat(temp_db)
        page = temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created,frame_id,offscreen) "
                          "VALUES(?,?,?,?,?,0)", (cid, 2, "I look around.", time.time(), None))
        list(runtime.run_pipeline(cid, page))

        def fails(ctx, nonce):
            raise RuntimeError("Commit failed and was rolled back: boom")
        monkeypatch.setitem(runtime.STEP_HANDLERS, "commit", fails)
        with pytest.raises(RuntimeError):
            list(runtime.run_pipeline(cid, page, only_key="commit"))
        assert resume_key_for_turn(page, cid) == "commit"


class TestTheJobsStopBeforeTheRestorePrepares:
    def test_consolidation_is_told_before_the_bank_is_prepared(self, temp_db, monkeypatch):
        """It asks only between members and writes its summary without asking
        again: told after the preparation, a member started from the rows
        being discarded and landed after the restore."""
        from core import jobs
        from persist import checkpoints, commit
        cid, _bubble, _page, _beat = _story_with_a_bubble_beat_after_the_page(temp_db)
        release = threading.Event()
        job = jobs.submit(cid, commit.MEMORY_CONSOLIDATION_JOB_KEY, lambda j: release.wait(5))
        seen = []
        real = checkpoints.prepare_chat_memory_restore
        monkeypatch.setattr(checkpoints, "prepare_chat_memory_restore",
                            lambda *a, **k: seen.append(job.cancelled.is_set()) or real(*a, **k))
        try:
            checkpoints.restore_checkpoint(cid, 2, carried=lambda: [])
        finally:
            release.set()
        assert seen and seen[0] is True


class TestNothingIsClaimedThatWasNotWritten:
    def test_an_edit_that_changes_nothing_claims_nothing(self, temp_db):
        from web import app
        cid, _bubble, _page, beat = _story_with_a_bubble_beat_after_the_page(temp_db)
        temp_db.qi("UPDATE turns SET offscreen=1 WHERE id=?", (beat,))
        app.edit_input(beat, {"input": ""})
        assert _row(temp_db, beat)["offscreen"] == 1

    def test_a_refused_activate_claims_nothing(self, temp_db):
        from web import app
        cid, _bubble, _page, beat = _story_with_a_bubble_beat_after_the_page(temp_db)
        temp_db.qi("UPDATE turns SET offscreen=1 WHERE id=?", (beat,))
        sid = temp_db.q("SELECT id FROM steps WHERE turn_id=? LIMIT 1", (beat,), one=True)["id"]
        with pytest.raises(HTTPException):
            app.step_activate(sid, {"variant_id": 999999})
        assert _row(temp_db, beat)["offscreen"] == 1

    def test_the_recompute_routes_leave_the_claim_to_the_run(self):
        """Claimed after the slot was won and before the run, a refused or
        stopped run left its beat claimed -- and a failed claim leaked the
        slot."""
        import inspect
        from agents import runtime
        from web import app
        for route in (app.turn_reroll, app.turn_rerun, app.turn_resume, app.step_reroll):
            assert "_claim_turn(" not in inspect.getsource(route), route.__name__
        assert inspect.getsource(runtime._run_pipeline).count("_claim_the_rerun(turn_id)") == 2


class TestARetirementOutlivesNoTurn:
    def test_a_book_retired_by_a_beat_taken_back_is_restored_unretired(self, temp_db):
        from persist.checkpoints import _turn_still_here
        cid = _chat(temp_db)
        kept = _turn(temp_db, cid, 0)
        assert _turn_still_here(cid, kept) == kept
        assert _turn_still_here(cid, kept + 999) is None
        assert _turn_still_here(_chat(temp_db), kept) is None, "another story's turn"
        assert _turn_still_here(cid, None) is None


class TestAnErrorIsTranslatedWhereItIsMade:
    def test_api_and_the_stream_translate_the_engines_sentence(self):
        from pathlib import Path
        utils = Path(__file__).resolve().parents[1].joinpath("static", "js", "utils.js").read_text(
            encoding="utf-8")
        assert utils.count("throw new Error(message ? t(message) : `HTTP ${response.status}`)") == 2


# ------------------------------------------------- the final check, 2026-10-13


class TestOnlyTheCommitIsMarkedEarly:
    def test_a_reroll_stopped_before_its_plan_leaves_no_step_stale_for_good(self, temp_db, monkeypatch):
        """Marking every step early left a step the next plan dropped stale
        after the next run succeeded: the run that would have given its flag
        back never built a plan."""
        from agents import resume_key_for_turn, runtime
        from agents.storage import save_step
        _stub_stages(monkeypatch)
        cid = _chat(temp_db)
        page = temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created,frame_id,offscreen) "
                          "VALUES(?,?,?,?,?,0)", (cid, 2, "I look around.", time.time(), None))
        list(runtime.run_pipeline(cid, page))
        for _ in range(2):
            save_step(page, "interaction_loop", "Characters", 3, {"ok": True})
        own = threading.Event()
        real = runtime.restore_checkpoint

        def restored_then_stopped(*a, **k):
            real(*a, **k)
            own.set()
        monkeypatch.setattr(runtime, "restore_checkpoint", restored_then_stopped)
        assert list(runtime.run_pipeline(cid, page, abort=own))[-1]["type"] == "aborted"
        monkeypatch.setattr(runtime, "restore_checkpoint", real)
        key = resume_key_for_turn(page, cid)
        assert key is not None
        assert list(runtime.run_pipeline(cid, page, from_key=key))[-1]["type"] == "done"
        assert not temp_db.q("SELECT key FROM steps WHERE turn_id=? AND stale=1", (page,))
        assert list(runtime.run_pipeline(cid, page, only_key="narrator"))[-1]["type"] == "done"


class TestAnOlderCheckpointTakesTheBookSetOnly:
    def test_what_it_held_of_its_own_books_stays_as_taken(self):
        from persist.checkpoints import _carry_the_book_set
        held = {
            "lore": {"lorebook_id": 1, "entries": ["the mill stands"]},
            "lorebooks": [
                {"lorebook_id": 1, "resource_uid": "c", "canon": True, "enabled": 1,
                 "entries": ["the mill stands"], "retired_turn_id": None},
                {"lorebook_id": 2, "library": True, "resource_uid": "lib-a", "enabled": 1},
                {"lorebook_id": 3, "library": True, "resource_uid": "lib-b", "enabled": 1},
            ],
            "lorebook_links": [{"source_book_id": 1, "target_book_id": 2},
                               {"source_book_id": 1, "target_book_id": 3}],
            "lore_overlays": [{"book_uid": "lib-a", "frame_id": None, "content": "as taken"}],
        }
        now = {
            "lore": {"lorebook_id": 1, "entries": ["the mill stands", "the ferryman drowned"]},
            "lorebooks": [
                {"lorebook_id": 1, "resource_uid": "c", "canon": True, "enabled": 1,
                 "entries": ["the mill stands", "the ferryman drowned"], "retired_turn_id": 9},
                {"lorebook_id": 2, "library": True, "resource_uid": "lib-a", "enabled": 0},
                {"lorebook_id": 4, "library": True, "resource_uid": "lib-c", "enabled": 1},
            ],
            "lorebook_links": [{"source_book_id": 1, "target_book_id": 2},
                               {"source_book_id": 1, "target_book_id": 4}],
            "lore_overlays": [{"book_uid": "lib-a", "frame_id": 7, "content": "a later thread"},
                              {"book_uid": "lib-c", "frame_id": None, "content": "attached since"}],
        }
        out = _carry_the_book_set(held, now)
        books = {b["lorebook_id"]: b for b in out["lorebooks"]}
        assert set(books) == {1, 2, 4}, "attached since in, detached since out"
        assert books[1]["entries"] == ["the mill stands"] and books[1]["retired_turn_id"] is None
        assert books[2]["enabled"] == 0, "the set: enabled as it is now"
        assert out["lore"]["entries"] == ["the mill stands"], "canon unchanged: as taken"
        assert {(l["source_book_id"], l["target_book_id"]) for l in out["lorebook_links"]} == {(1, 2), (1, 4)}
        assert [o["content"] for o in out["lore_overlays"]] == ["as taken", "attached since"]


class TestARestoreHoldsOnlyItsOwnThreadsOverlays:
    def test_an_overlay_for_a_thread_the_restore_does_not_hold_is_not_written(self, temp_db, monkeypatch):
        from persist import checkpoints
        cid, _bubble, _page, _beat = _story_with_a_bubble_beat_after_the_page(temp_db)
        row = temp_db.q("SELECT blob FROM checkpoints WHERE chat_id=? AND turn_idx=2", (cid,), one=True)
        blob = json.loads(row["blob"])
        blob["lore_overlays"] = [{"entry_uid": "e1", "book_uid": "lib", "frame_id": None},
                                 {"entry_uid": "e2", "book_uid": "lib", "frame_id": 987654}]
        temp_db.qi("UPDATE checkpoints SET blob=? WHERE chat_id=? AND turn_idx=2", (json.dumps(blob), cid))
        written = []
        monkeypatch.setattr(checkpoints, "restore_lore_overlays",
                            lambda chat_id, overlays: written.extend(o["entry_uid"] for o in overlays))
        checkpoints.restore_checkpoint(cid, 2)
        assert written == ["e1"]
