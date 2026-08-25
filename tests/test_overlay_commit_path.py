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
