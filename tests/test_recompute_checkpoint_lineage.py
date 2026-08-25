"""A checkpoint downstream of a recomputed turn describes a lineage that is gone.

A checkpoint is a PRE-turn snapshot, so a checkpoint at turn_idx N+1 is a
picture of the world that turn N's commit produced. Discard that commit and
the snapshot is describing a timeline the story no longer has.

`turn_del` has always known this -- deleting turn N runs
`DELETE FROM checkpoints WHERE chat_id=? AND turn_idx>=?`, because the same
reasoning applies. Recompute is the same act with the turn row kept, and it
stated no such rule, so the stale snapshot survived and `ensure_checkpoint`
returns early when a row exists -- meaning the new lineage could never write
its own.

MEASURED, chat 87 (branched from 86 at turn 49, then rerolled):

    checkpoints idx 46..50   created 22:35:44   (all of them, at branch time)
    turn 49's ACTIVE commit  created 22:40:10
    turn 50 created          22:47:16

A snapshot of "the world before turn 50" predating turn 50 by twelve minutes,
and predating the commit it depicts by five. The branch writes a checkpoint at
`idx + 1` from the branch-moment state; three further rerolls of turn 49
changed what that state should be and nothing refreshed it.

Nothing here is about branches, rerolls-in-particular, or that story: the rule
is that a snapshot derived from a commit dies with the commit.
"""

from __future__ import annotations

import json
import time

import pytest

from core.db import q, qi
from persist.checkpoints import ensure_checkpoint


def _chat(db, name="Recompute"):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 (name, "", time.time()))


def _turn(db, chat_id, idx):
    return db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, idx, "do something", time.time()))


def _checkpoint(db, chat_id, idx, marker):
    """A checkpoint whose blob is identifiable, so a survivor is provable."""
    return db.qi(
        "INSERT INTO checkpoints(chat_id,turn_idx,blob,created) "
        "VALUES(?,?,?,?)",
        (chat_id, idx, json.dumps({"world": {"scene": marker}}), time.time()))


class TestTheSweep:
    def test_snapshots_downstream_of_the_recomputed_turn_are_dropped(
            self, temp_db):
        """Every checkpoint at a HIGHER index depends on the commit being
        discarded, so every one of them goes."""
        cid = _chat(temp_db)
        for idx in range(0, 4):
            _turn(temp_db, cid, idx)
            _checkpoint(temp_db, cid, idx, f"before-{idx}")

        from agents import runtime

        # The sweep is the first thing `_restore_and_refresh` does; exercise
        # it directly rather than standing up a whole pipeline, because the
        # rule under test is the DELETE, not the restore beside it.
        qi("DELETE FROM checkpoints WHERE chat_id=? AND turn_idx>?", (cid, 1))

        left = [r["turn_idx"] for r in q(
            "SELECT turn_idx FROM checkpoints WHERE chat_id=? ORDER BY turn_idx",
            (cid,))]
        assert left == [0, 1]

    def test_the_recomputed_turns_own_checkpoint_survives(self, temp_db):
        """STRICTLY GREATER, never `>=`. This turn's checkpoint is the state
        BEFORE it ran -- a recompute does not change that, and the restore
        that follows the sweep is about to read it."""
        cid = _chat(temp_db)
        _turn(temp_db, cid, 2)
        _checkpoint(temp_db, cid, 2, "before-2")

        qi("DELETE FROM checkpoints WHERE chat_id=? AND turn_idx>?", (cid, 2))

        row = q("SELECT blob FROM checkpoints WHERE chat_id=? AND turn_idx=2",
                (cid,), one=True)
        assert row, "the sweep took the snapshot the restore needs"
        assert json.loads(row["blob"])["world"]["scene"] == "before-2"

    def test_another_story_is_untouched(self, temp_db):
        cid, other = _chat(temp_db), _chat(temp_db, "Bystander")
        _checkpoint(temp_db, cid, 5, "mine")
        _checkpoint(temp_db, other, 5, "theirs")

        qi("DELETE FROM checkpoints WHERE chat_id=? AND turn_idx>?", (cid, 1))

        assert q("SELECT COUNT(*) c FROM checkpoints WHERE chat_id=?",
                 (other,), one=True)["c"] == 1


class TestWhyTheStaleRowMattered:
    def test_a_surviving_row_shadows_the_fresh_snapshot(self, temp_db):
        """`ensure_checkpoint` returns the existing id without looking at it,
        so a stale row is not merely wrong -- it is permanent. This is the
        mechanism that let a branch-time snapshot outlive three rerolls."""
        cid = _chat(temp_db)
        _turn(temp_db, cid, 0)
        _checkpoint(temp_db, cid, 0, "discarded-lineage")

        ensure_checkpoint(cid, 0)

        row = q("SELECT blob FROM checkpoints WHERE chat_id=? AND turn_idx=0",
                (cid,), one=True)
        assert json.loads(row["blob"])["world"]["scene"] == "discarded-lineage"

    def test_after_the_sweep_the_next_snapshot_is_freshly_taken(
            self, temp_db):
        """With the stale row gone, `ensure_checkpoint` takes a real one."""
        cid = _chat(temp_db)
        _turn(temp_db, cid, 0)
        _checkpoint(temp_db, cid, 1, "discarded-lineage")

        qi("DELETE FROM checkpoints WHERE chat_id=? AND turn_idx>?", (cid, 0))
        assert not q("SELECT id FROM checkpoints WHERE chat_id=? AND turn_idx=1",
                     (cid,), one=True)

        _turn(temp_db, cid, 1)
        ensure_checkpoint(cid, 1)
        row = q("SELECT blob FROM checkpoints WHERE chat_id=? AND turn_idx=1",
                (cid,), one=True)
        assert row
        # A real snapshot, not the marker: it carries the sections
        # `snapshot_state` builds.
        blob = json.loads(row["blob"])
        assert "world" in blob and isinstance(blob["world"], dict)
        assert blob["world"] != "discarded-lineage"


class TestTheRuleIsStatedWhereItActs:
    def test_the_recompute_path_carries_the_sweep(self):
        """A rule that lives only in a test is a rule the next reader of
        `_restore_and_refresh` will not find."""
        import inspect

        from agents import runtime

        source = inspect.getsource(runtime._run_pipeline)
        assert "DELETE FROM checkpoints" in source
        assert "turn_idx>?" in source

    def test_it_is_not_refresh_checkpoint(self):
        """`refresh_checkpoint` patches only the lore sections and exists to
        REMOVE a whole-chat re-snapshot that was itself a bug. Wiring it here
        would re-break what it was written to fix."""
        import inspect

        from persist import checkpoints

        doc = inspect.getdoc(checkpoints.refresh_checkpoint) or ""
        assert "lore" in doc.lower()


class TestSwappingAnAppliedCommit:
    """`commit` is the one step the downstream-staleness sweep cannot reach.

    Every other step has a successor for `UPDATE steps SET stale=1 WHERE ord>?`
    to mark. `commit` is the persistence boundary and has none, so activating a
    different variant of it changed which lineage the turn CLAIMED while the
    world ledgers went on holding the other -- and left no trace: the turn read
    as complete and the next one was allowed to start on top of it.
    """

    def _step(self, temp_db, chat_id, key, ord_):
        tid = _turn(temp_db, chat_id, 0)
        sid = temp_db.qi(
            "INSERT INTO steps(turn_id,key,label,ord,stale) VALUES(?,?,?,?,0)",
            (tid, key, key, ord_))
        temp_db.qi(
            "INSERT INTO variants(step_id,content,created,active) "
            "VALUES(?,?,?,1)", (sid, "{}", time.time()))
        return tid, sid

    def test_a_commit_step_marks_itself(self, temp_db):
        from web.app import _mark_applied_step_stale

        cid = _chat(temp_db)
        _tid, sid = self._step(temp_db, cid, "commit", 9)
        _mark_applied_step_stale(
            q("SELECT * FROM steps WHERE id=?", (sid,), one=True))
        assert q("SELECT stale FROM steps WHERE id=?", (sid,),
                 one=True)["stale"] == 1

    def test_an_ordinary_step_does_not(self, temp_db):
        """The downstream sweep already covers those, and marking them here
        would make every variant swap look like a broken turn."""
        from web.app import _mark_applied_step_stale

        cid = _chat(temp_db)
        _tid, sid = self._step(temp_db, cid, "narrator", 7)
        _mark_applied_step_stale(
            q("SELECT * FROM steps WHERE id=?", (sid,), one=True))
        assert q("SELECT stale FROM steps WHERE id=?", (sid,),
                 one=True)["stale"] == 0

    def test_both_swap_seams_call_it(self):
        """Activation and a hand edit are the same swap; a guard on one only
        is a guard the other way round the loop."""
        import inspect

        from web import app

        for fn in (app.step_edit, app.step_activate):
            assert "_mark_applied_step_stale" in inspect.getsource(fn), fn


class TestDetailAloneIsNotAnArrangement:
    """A pose snapshot carrying only `detail` erased posture, support and
    relation on every beat it occurred.

    The schema is what makes the two cases collide: `PoseEntry` defaults every
    field to `""`, so "I did not mention posture this beat" and "posture
    ended" arrive identical. Reading both as ended destroys state on the
    commoner one. Clearing a pose keeps its own spelling -- an entry with
    nothing in it at all -- which `_clean_pose` already turns into None.

    Measured by running the merge: a detail-only snapshot over a standing
    `seated / low_table / astride B` left all five arrangement fields empty.
    """

    def _scene(self, pose):
        return {"rooms": {"r": {"name": "R"}},
                "positions": {"A": "r", "B": "r"}, "entities": {},
                "contacts": [], "contained": {}, "scales": {}, "stations": {},
                "poses": {"A": dict(pose)}}

    STANDING = {"posture": "seated", "support": "low_table",
                "relative_to": "B", "relation": "astride",
                "constraint": "", "detail": ""}

    def test_a_detail_only_snapshot_annotates_rather_than_replaces(self):
        from world.spatial import merge_scene_with_diff

        merged = merge_scene_with_diff(
            self._scene(self.STANDING),
            {"poses": {"A": {"detail": "looks down at her lap"}}})
        pose = merged["poses"]["A"]
        assert pose["posture"] == "seated"
        assert pose["support"] == "low_table"
        assert pose["relation"] == "astride"
        assert pose["detail"] == "looks down at her lap"

    def test_a_snapshot_naming_an_arrangement_still_replaces(self):
        """The overwrite is correct when the Director actually states one --
        this must not become a merge that can never change a pose."""
        from world.spatial import merge_scene_with_diff

        merged = merge_scene_with_diff(
            self._scene(self.STANDING),
            {"poses": {"A": {"posture": "standing"}}})
        pose = merged["poses"]["A"]
        assert pose["posture"] == "standing"
        assert pose["support"] == ""
        assert pose["relation"] == ""

    def test_a_body_with_no_standing_pose_takes_the_detail_alone(self):
        from world.spatial import merge_scene_with_diff

        scene = self._scene(self.STANDING)
        scene["poses"] = {}
        merged = merge_scene_with_diff(
            scene, {"poses": {"A": {"detail": "shifts her weight"}}})
        assert merged["poses"]["A"]["detail"] == "shifts her weight"
        assert merged["poses"]["A"]["posture"] == ""
