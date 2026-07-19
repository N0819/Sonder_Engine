"""Regression tests for the branching/reroll/rerun-from-stage integrity
fixes: an external audit found that an aborted reroll could leave a turn
looking falsely "complete" (stale flags were only ever cleared, never set
proactively before a run); replans silently hard-deleted manually-edited
step history; step-level edits skipped the latest-turn check; step
activation could deactivate every variant on a step while activating none
(and did so as two unguarded autocommits); and two nearly-identical async
turn-creation code paths existed, one of which had none of these guards
at all. Confirmed live against the user's own chat 9 (Fable's audit):
turn 30 already lost an interaction_loop step's history to the replan
bug, and turn 16 nearly hit the aborted-reroll bug."""

from __future__ import annotations

import json
import time

import pytest
from fastapi import HTTPException

import app
import db
from agents.runtime import ABORTS, _run_pipeline, begin_pipeline, resume_key_for_turn
from agents.storage import clear_steps_stale, mark_steps_stale, save_step, step_is_stale, variant_count


def _make_chat(conn):
    return conn.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )


def _make_turn(conn, chat_id, idx=1):
    return conn.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, idx, "do something", time.time()),
    )


def _add_variant(conn, step_id, content="{}", active=0):
    return conn.qi(
        "INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,?)",
        (step_id, content, time.time(), active),
    )


# ---- flaw: stale flags only ever cleared, never set proactively ----

class TestProactiveStaleMarking:
    def test_mark_steps_stale_only_touches_named_keys(self, temp_db):
        chat_id = _make_chat(temp_db)
        turn_id = _make_turn(temp_db, chat_id)
        for i, key in enumerate(["a", "b", "c"]):
            save_step(turn_id, key, key, i, {"k": key})

        mark_steps_stale(turn_id, ["b", "c"])

        rows = {r["key"]: bool(r["stale"]) for r in temp_db.q(
            "SELECT key, stale FROM steps WHERE turn_id=?", (turn_id,)
        )}
        assert rows == {"a": False, "b": True, "c": True}

    def test_clear_steps_stale_only_touches_named_keys(self, temp_db):
        chat_id = _make_chat(temp_db)
        turn_id = _make_turn(temp_db, chat_id)
        for i, key in enumerate(["a", "b"]):
            save_step(turn_id, key, key, i, {"k": key})
        mark_steps_stale(turn_id, ["a", "b"])

        clear_steps_stale(turn_id, ["a"])

        rows = {r["key"]: bool(r["stale"]) for r in temp_db.q(
            "SELECT key, stale FROM steps WHERE turn_id=?", (turn_id,)
        )}
        assert rows == {"a": False, "b": True}

    def test_resume_key_finds_stale_step_left_by_an_interrupted_run(self, temp_db):
        """This is the actual shape of the bug found live in chat 9's
        turn 16: a reroll computed director_interpret..director_resolve
        then stopped (simulating an abort) without ever touching the
        downstream steps left over from the PREVIOUS complete run. Before
        the fix, those downstream steps kept stale=0 from the old run, so
        resume_key_for_turn wrongly reported the turn as complete."""
        chat_id = _make_chat(temp_db)
        turn_id = _make_turn(temp_db, chat_id, idx=1)

        plan = [
            ("director_interpret", "Director · interpret"),
            ("mapping_quick", "Mapping"),
            ("perception_act", "Perception"),
            ("director_resolve", "Director · resolve"),
            ("perception_outcome", "Perception · outcome"),
            ("narrator", "Narrator"),
            ("commit", "Commit"),
        ]
        for i, (key, label) in enumerate(plan):
            save_step(turn_id, key, label, i, {"flow": {"needs_mapping": False, "reactors": []}})

        # A full reroll starts: everything from mapping_quick onward is
        # marked stale up front (the fix), then only director_interpret
        # and mapping_quick actually get recomputed before the process
        # is interrupted.
        keys = [k for k, _ in plan]
        mark_steps_stale(turn_id, keys[1:])
        save_step(turn_id, "director_interpret", "Director · interpret", 0,
                   {"flow": {"needs_mapping": False, "reactors": []}})
        save_step(turn_id, "mapping_quick", "Mapping", 1, {"relevant_lore": []})

        resume_key = resume_key_for_turn(turn_id, chat_id)
        assert resume_key == "perception_act"


# ---- flaw: replan hard-deleted manually-edited step history ----

class TestReplanPreservesEditedSteps:
    def _run_stubbed_turn(self, monkeypatch, chat_id, turn_id):
        import agents.runtime as runtime

        def fake_director_interpret(ctx, nonce):
            return {"flow": {"needs_mapping": False, "reactors": [], "resolution_flags": {}}}

        stubs = {
            "director_interpret": fake_director_interpret,
            "mapping_quick": lambda ctx, nonce: {"relevant_lore": []},
            "perception_act": lambda ctx, nonce: {"view": ""},
            "director_resolve": lambda ctx, nonce: {"dialogue_log": [], "state_diff": {}},
            "perception_outcome": lambda ctx, nonce: {"view": ""},
            "narrator": lambda ctx, nonce: {"prose": "ok"},
            "commit": lambda ctx, nonce: {"committed": True},
        }
        for key, fn in stubs.items():
            monkeypatch.setitem(runtime.STEP_HANDLERS, key, fn)

        list(_run_pipeline(chat_id, turn_id))

    def test_multi_variant_orphan_survives_a_replan(self, temp_db, monkeypatch):
        chat_id = _make_chat(temp_db)
        turn_id = _make_turn(temp_db, chat_id, idx=1)

        # A step whose key will NOT appear in the freshly rebuilt plan
        # (the stub director_interpret always returns reactors=[]), but
        # which was rerolled/edited at least once -- variant_count > 1.
        ghost_id, _, _ = save_step(turn_id, "mapping_stage", "Mapping · full", 0, {"relevant_lore": ["a"]})
        _add_variant(temp_db, ghost_id, content=json.dumps({"relevant_lore": ["b"]}), active=0)
        assert variant_count(turn_id, "mapping_stage") == 2

        # A step in the same situation but never touched a second time --
        # safe to actually delete, no editorial investment lost.
        save_step(turn_id, "old_untouched_ghost", "Old ghost", 0, {"x": 1})
        assert variant_count(turn_id, "old_untouched_ghost") == 1

        self._run_stubbed_turn(monkeypatch, chat_id, turn_id)

        surviving = {r["key"] for r in temp_db.q("SELECT key FROM steps WHERE turn_id=?", (turn_id,))}
        assert "mapping_stage" in surviving
        assert "old_untouched_ghost" not in surviving

    def test_a_completed_stubbed_run_leaves_the_plan_clean(self, temp_db, monkeypatch):
        chat_id = _make_chat(temp_db)
        turn_id = _make_turn(temp_db, chat_id, idx=1)

        self._run_stubbed_turn(monkeypatch, chat_id, turn_id)

        rows = temp_db.q("SELECT key, stale FROM steps WHERE turn_id=?", (turn_id,))
        assert rows
        assert all(not r["stale"] for r in rows)
        keys = {r["key"] for r in rows}
        assert keys == {
            "director_interpret", "mapping_quick", "perception_act",
            "director_resolve", "background_react", "perception_outcome",
            "narrator", "commit",
        }
        for r in rows:
            assert variant_count(turn_id, r["key"]) == 1


# ---- flaw: rerun-from-stage silently "laundered" a stale earlier step ----

class TestStaleStepIsRefusedNotLaundered:
    def test_resuming_past_a_stale_earlier_step_raises(self, temp_db):
        chat_id = _make_chat(temp_db)
        turn_id = _make_turn(temp_db, chat_id, idx=1)

        plan = [
            ("director_interpret", "Director · interpret"),
            ("mapping_quick", "Mapping"),
        ]
        for i, (key, label) in enumerate(plan):
            save_step(turn_id, key, label, i, {"flow": {"needs_mapping": False, "reactors": []}})
        mark_steps_stale(turn_id, ["mapping_quick"])
        assert step_is_stale(turn_id, "mapping_quick")

        from agents.runtime import StaleStepError

        with pytest.raises(StaleStepError):
            list(_run_pipeline(chat_id, turn_id, from_key="perception_act"))


# ---- flaw: exactly-one-active-variant invariant was two unguarded writes ----

class TestVariantActivationAtomicityAndOwnership:
    def test_save_step_never_leaves_zero_active_variants(self, temp_db):
        chat_id = _make_chat(temp_db)
        turn_id = _make_turn(temp_db, chat_id, idx=1)

        save_step(turn_id, "narrator", "Narrator", 0, {"prose": "one"})
        save_step(turn_id, "narrator", "Narrator", 0, {"prose": "two"})
        save_step(turn_id, "narrator", "Narrator", 0, {"prose": "three"})

        step = temp_db.q("SELECT id FROM steps WHERE turn_id=? AND key='narrator'", (turn_id,), one=True)
        active = temp_db.q("SELECT COUNT(*) c FROM variants WHERE step_id=? AND active=1", (step["id"],), one=True)
        assert active["c"] == 1

    def test_step_activate_rejects_a_variant_from_another_step(self, temp_db):
        chat_id = _make_chat(temp_db)
        turn_id = _make_turn(temp_db, chat_id, idx=1)
        sid_a, vid_a, _ = save_step(turn_id, "narrator", "Narrator", 0, {"prose": "a"})
        sid_b, vid_b, _ = save_step(turn_id, "director_resolve", "Resolve", 1, {"x": 1})

        with pytest.raises(HTTPException) as exc_info:
            app.step_activate(sid_a, {"variant_id": vid_b})
        assert exc_info.value.status_code == 404

        # Rejected before touching anything -- step A's own variant is
        # still active, not deactivated-then-nothing-activated.
        active = temp_db.q("SELECT COUNT(*) c FROM variants WHERE step_id=? AND active=1", (sid_a,), one=True)
        assert active["c"] == 1

    def test_step_activate_switches_to_a_real_sibling_variant(self, temp_db):
        chat_id = _make_chat(temp_db)
        turn_id = _make_turn(temp_db, chat_id, idx=1)
        sid, vid1, _ = save_step(turn_id, "narrator", "Narrator", 0, {"prose": "a"})
        vid2 = _add_variant(temp_db, sid, content=json.dumps({"prose": "b"}), active=0)

        result = app.step_activate(sid, {"variant_id": vid2})
        assert result == {"ok": True}

        active = temp_db.q("SELECT id FROM variants WHERE step_id=? AND active=1", (sid,), one=True)
        assert active["id"] == vid2


# ---- flaw: step edit/activate skipped the latest-turn check ----

class TestStepMutationRequiresLatestTurn:
    def test_step_edit_rejects_a_non_latest_turn(self, temp_db):
        chat_id = _make_chat(temp_db)
        turn1 = _make_turn(temp_db, chat_id, idx=1)
        _make_turn(temp_db, chat_id, idx=2)  # turn1 is no longer latest
        sid, _, _ = save_step(turn1, "narrator", "Narrator", 0, {"prose": "a"})

        with pytest.raises(HTTPException) as exc_info:
            app.step_edit(sid, {"content": {"prose": "edited"}})
        assert exc_info.value.status_code == 409

    def test_step_activate_rejects_a_non_latest_turn(self, temp_db):
        chat_id = _make_chat(temp_db)
        turn1 = _make_turn(temp_db, chat_id, idx=1)
        _make_turn(temp_db, chat_id, idx=2)
        sid, vid, _ = save_step(turn1, "narrator", "Narrator", 0, {"prose": "a"})
        vid2 = _add_variant(temp_db, sid, content=json.dumps({"prose": "b"}), active=0)

        with pytest.raises(HTTPException) as exc_info:
            app.step_activate(sid, {"variant_id": vid2})
        assert exc_info.value.status_code == 409

    def test_step_edit_allowed_on_the_actual_latest_turn(self, temp_db):
        chat_id = _make_chat(temp_db)
        turn1 = _make_turn(temp_db, chat_id, idx=1)
        sid, _, _ = save_step(turn1, "narrator", "Narrator", 0, {"prose": "a"})

        result = app.step_edit(sid, {"content": {"prose": "edited"}})
        assert "variant_id" in result


# ---- flaw: starting a new turn didn't check the latest turn was resolved ----

class TestTurnCreationRequiresLatestTurnResolved:
    def test_turn_new_rejects_when_latest_turn_has_a_stale_step(self, temp_db):
        chat_id = _make_chat(temp_db)
        turn1 = _make_turn(temp_db, chat_id, idx=0)
        save_step(turn1, "director_interpret", "Director · interpret", 0, {"flow": {}})
        save_step(turn1, "narrator", "Narrator", 1, {"prose": "a"})
        mark_steps_stale(turn1, ["narrator"])

        with pytest.raises(HTTPException) as exc_info:
            app.turn_new(chat_id, {"input": "next"})
        assert exc_info.value.status_code == 409

    def test_turn_new_allows_a_fresh_chat_with_no_turns_yet(self, temp_db, monkeypatch):
        chat_id = _make_chat(temp_db)
        captured = {}
        monkeypatch.setattr(app, "run_pipeline", lambda *a, **k: captured.setdefault("called", True) or iter(()))
        try:
            app.turn_new(chat_id, {"input": "start"})
        finally:
            ABORTS.pop((chat_id, None), None)
        assert captured.get("called")


# ---- flaw: ABORTS registration was deferred until the generator was iterated ----

class TestPipelineRegistrationIsSynchronous:
    def test_begin_pipeline_registers_before_any_iteration(self, temp_db):
        chat_id = _make_chat(temp_db)
        assert (chat_id, None) not in ABORTS
        abort = begin_pipeline(chat_id)
        try:
            assert ABORTS[(chat_id, None)] is abort
        finally:
            ABORTS.pop((chat_id, None), None)

    def test_run_pipeline_reuses_a_preregistered_abort_event(self, temp_db):
        from agents.runtime import run_pipeline

        chat_id = _make_chat(temp_db)
        turn_id = _make_turn(temp_db, chat_id, idx=1)
        abort = begin_pipeline(chat_id)
        gen = run_pipeline(chat_id, turn_id, only_key="nonexistent", abort=abort)
        try:
            list(gen)
        except Exception:
            pass
        assert ABORTS.get((chat_id, None)) is None or ABORTS.get((chat_id, None)) is abort


# ---- flaw: a second, unused async pipeline duplicated + drifted from the real one ----

class TestDeadAsyncPipelineWasRemoved:
    def test_turns_async_route_no_longer_exists(self):
        paths = {getattr(r, "path", None) for r in app.app.router.routes}
        assert "/api/chats/{cid}/turns/async" not in paths
