"""THE SWEEP MARKER IS STAMPED BEFORE THE OUTCOME PASS OPENS (2026-10-20).

`scene["_sweeping"]` -- who looked around this beat, which `effective_facing`
reads -- is in the scene read pass's read set, and the outcome views stamped
it INSIDE the pass, after the pass had fingerprinted the scene. Every
derivation memoised before that write could be stale, which is what the
pass's exit warning reports; it fired on a probe story's opening turn and
named no pass. Now the warning names the pass it was opened in, and the
outcome stage stamps the marker before opening it.
"""

from __future__ import annotations

import logging

import agents.perception as perception
from world import scene_memo
from world.scene_memo import SCENE_READS, scene_read_pass


def test_a_write_inside_a_pass_names_the_pass_that_was_open(caplog):
    scene = {"rooms": {}, "positions": {}}
    with caplog.at_level(logging.WARNING, logger=scene_memo.log.name):
        with scene_read_pass(scene):
            scene["_sweeping"] = ["Ada"]          # a read-set key, written late
    assert "_sweeping" in SCENE_READS
    messages = [r.getMessage() for r in caplog.records if "scene_read_pass" in r.getMessage()]
    assert len(messages) == 1
    assert "pass opened at" in messages[0] and "test_the_sweep_marker" in messages[0]


def test_the_outcome_stage_stamps_the_marker_before_opening_the_pass(caplog, monkeypatch):
    """The views find the marker already on the working copy, the pass is
    open while they run, and the pass closes without a warning."""
    seen = {}

    def views(ctx, sc, prev_scene, diff, interp, res, known, p_name, *rest, **kw):
        seen["marker"] = list(sc.get("_sweeping") or [])
        seen["pass_open"] = id(sc) in scene_memo._PASSES
        return {"views": {}}

    monkeypatch.setattr(perception, "_composer_outcome_views", views)
    monkeypatch.setattr(perception, "swept_this_beat",
                        lambda res, p_name, cast, interp=None: {p_name, "Mara"})

    class _Ctx:
        cast = ()

    scene = {"rooms": {"r": {"name": "r"}}, "positions": {"Ada": "r"}}
    with caplog.at_level(logging.WARNING, logger=scene_memo.log.name):
        out = perception._composer_outcome(
            _Ctx(), scene, None, {}, {}, {}, {}, "Ada",
            None, None, None, None, None, {}, {}, {}, [], [], {})
    assert out == {"views": {}}
    assert seen == {"marker": ["Ada", "Mara"], "pass_open": True}
    assert not [r for r in caplog.records if "scene_read_pass" in r.getMessage()]
    assert "_sweeping" not in scene or scene["_sweeping"] == ["Ada", "Mara"]
