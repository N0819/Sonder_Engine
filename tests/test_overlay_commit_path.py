"""The overlay collapse pinned where the turn actually runs it.

`tests/test_overlay_identity.py` calls the merge helpers directly, which
leaves the WIRING unpinned: a refactor that keeps the merge and drops the
dedupe passes every one of those tests. It also cannot fail on a tree where
the helpers do not exist yet -- it cannot even be collected there -- and an
ImportError is not a reproduction of anything.

This file names only `prepare_scene_commit`, the production caller, which has
existed all along. It therefore states the defect as an ASSERTION about the
committed blob: chat 88 turn 67 stood one overlay three times -- as its bare
name, as its bare description, and as the record carrying both -- and every
observer's appearance view rendered all three.
"""

from __future__ import annotations

import contextlib
import time

from persist.commit import prepare_scene_commit
from core.pipeline_context import ChatData, PipelineContext, TurnData


class TestThroughTheCommitPath:
    def _scene_after(self, temp_db, standing, incoming):
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Overlays", "", time.time()))
        temp_db.wset(chat_id, "scene", {
            "rooms": {"cell": {"name": "Cell", "adjacent": []}},
            "positions": {"Ada": "cell"},
            "overlays": {"Ada": list(standing)},
        })
        ctx = PipelineContext(
            chat=ChatData(id=chat_id, name="Overlays", persona_id=None,
                          lorebook_id=None, scenario="", created=time.time()),
            turn=TurnData(id=1, chat_id=chat_id, idx=4, player_input="wait",
                          created=time.time()),
            cast=[], input="wait")
        ctx.director_resolve = {"state_diff": {"overlays": {
            "Ada": list(incoming)}}}
        return (prepare_scene_commit(ctx) or {}).get("scene") or {}

    def test_the_live_shape_collapses_on_the_way_into_the_blob(self, temp_db):
        sc = self._scene_after(
            temp_db,
            ["red across the brow", "blush", "gold shimmer across the skin"],
            [{"name": "blush", "description": "gold shimmer across the skin"}])
        assert sc["overlays"]["Ada"] == [
            "red across the brow",
            {"name": "blush", "description": "gold shimmer across the skin"},
        ]

    def test_a_body_the_diff_never_names_is_healed_on_the_way_too(
            self, temp_db):
        sc = self._scene_after(
            temp_db,
            [{"name": "blush", "description": "gold shimmer"}, "blush"],
            [])
        assert sc["overlays"]["Ada"] == [
            {"name": "blush", "description": "gold shimmer"}]


@contextlib.contextmanager
def _under_commit_step(ctx):
    """Run a block with the sinks `agents.runtime.compute_step` installs for
    the commit step, so `note_step_decision` from inside a commit domain
    reaches this ctx.

    These tests drive the commit domain directly instead of through the
    runtime funnel, which is the only place those contextvars are normally
    set. Without this the decision channel is a no-op and the assertions
    below would pass against an engine that recorded nothing.
    """
    from core.pipeline_context import current_decision_sink, current_step_key
    token = current_step_key.set("commit")
    sink = current_decision_sink.set(ctx.note_decision)
    try:
        yield
    finally:
        current_decision_sink.reset(sink)
        current_step_key.reset(token)


class TestTheCapIsARulingAndSaysSo:
    """`overlays[key][-_MAX_OVERLAY_ENTRIES:]` is the only thing that ends an
    overlay other than the Director writing `active: false`, and nothing here
    expires one -- so the seventh mark arriving deletes the oldest standing
    appearance fact with no beat having said it stopped. That is a resolution
    reached by list position; it may keep happening, but it may not keep
    happening invisibly.
    """

    def _committed(self, temp_db, standing, incoming):
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Overlays", "", time.time()))
        temp_db.wset(chat_id, "scene", {
            "rooms": {"cell": {"name": "Cell", "adjacent": []}},
            "positions": {"Ada": "cell"},
            "overlays": {"Ada": list(standing)},
        })
        ctx = PipelineContext(
            chat=ChatData(id=chat_id, name="Overlays", persona_id=None,
                          lorebook_id=None, scenario="", created=time.time()),
            turn=TurnData(id=1, chat_id=chat_id, idx=4, player_input="wait",
                          created=time.time()),
            cast=[], input="wait")
        ctx.director_resolve = {"state_diff": {"overlays": {
            "Ada": list(incoming)}}}
        with _under_commit_step(ctx):
            scene = (prepare_scene_commit(ctx) or {}).get("scene") or {}
        return scene, ctx

    def test_the_mark_the_cap_deletes_is_named_in_the_decision_log(
            self, temp_db):
        scene, ctx = self._committed(
            temp_db,
            ["violent shuddering", "tears escape eyes", "soot at the jaw",
             "rope burn at the wrists", "a split lip", "dust in the hair"],
            ["a fresh bruise below the eye"])

        assert len(scene["overlays"]["Ada"]) == 6
        assert "violent shuddering" not in scene["overlays"]["Ada"]

        evictions = [d for d in ctx.decisions_for_step("commit")
                     if d["verdict"] == "evicted_by_cap"]
        assert len(evictions) == 1
        only = evictions[0]
        assert only["kind"] == "overlay_ledger"
        # Whose body, and which mark: a reader needs both to tell this from
        # the `active: false` ending, which is the only other way out.
        assert only["subject"] == "Ada: violent shuddering"
        assert "cap 6" in only["reason"]
        assert "No ending was written for it" in only["reason"]

    def test_a_record_shaped_overlay_is_labelled_by_its_own_words(
            self, temp_db):
        # The label must survive a shape the dedupe handles differently: a
        # record's name and description, not its repr, and not silence.
        _scene, ctx = self._committed(
            temp_db,
            [{"name": "flush", "description": "red across the brow"}]
            + ["mark %d" % i for i in range(5)],
            ["mark 5"])

        evictions = [d for d in ctx.decisions_for_step("commit")
                     if d["verdict"] == "evicted_by_cap"]
        assert [d["subject"] for d in evictions] == [
            "Ada: flush / red across the brow"]

    def test_a_ledger_under_the_cap_records_nothing(self, temp_db):
        _scene, ctx = self._committed(
            temp_db, ["soot at the jaw"], ["a split lip"])
        assert [d for d in ctx.decisions_for_step("commit")
                if d["verdict"] == "evicted_by_cap"] == []

    def test_an_ending_is_not_logged_as_a_cap_eviction(self, temp_db):
        # The distinction the log exists for: a mark the Director ENDED must
        # not read like one the cap deleted.
        scene, ctx = self._committed(
            temp_db, ["tears escape eyes"],
            [{"text": "tears escape eyes", "active": False}])
        assert scene["overlays"]["Ada"] == []
        assert [d for d in ctx.decisions_for_step("commit")
                if d["verdict"] == "evicted_by_cap"] == []
