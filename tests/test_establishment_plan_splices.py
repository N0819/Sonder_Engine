"""The opening turn is a plan like any other, and extensions may splice it.

`build_plan` ends in `_extension_splices`; `establishment_plan` returned a bare
literal, so an extension anchored `after:mapping_stage`, `before:narrator` or
`after:commit` -- all steps the opening turn DOES run -- was silently not
planned there. `docs/guides/EXTENSIONS.md` states the opposite rule: a stage is
skipped only when the turn does not run its anchor step.
"""

from __future__ import annotations

import extension_runtime
from agents.runtime import establishment_plan


def _splice_after(monkeypatch, core, entry):
    def fake(plan, chat_id=None):
        out = []
        for key, label in plan:
            out.append((key, label))
            if key == core:
                out.append(entry)
        return out

    monkeypatch.setattr(extension_runtime, "apply_plan_splices", fake)


def test_an_opening_turn_carries_extension_stages(monkeypatch):
    entry = ("ext:demo:seed", "Demo · seed the world")
    _splice_after(monkeypatch, "mapping_stage", entry)
    keys = [key for key, _ in establishment_plan(7)]
    assert keys == ["mapping_stage", "ext:demo:seed", "director_establish",
                    "perception_establish", "narrator", "commit"]


def test_a_broken_splice_leaves_the_opening_plan_untouched(monkeypatch):
    def exploding(plan, chat_id=None):
        raise RuntimeError("extension is broken")

    monkeypatch.setattr(extension_runtime, "apply_plan_splices", exploding)
    # Same totality the normal-turn path has: a broken extension may never
    # cost a turn, least of all the first one.
    assert [key for key, _ in establishment_plan(7)] == [
        "mapping_stage", "director_establish", "perception_establish",
        "narrator", "commit"]


def test_resume_rebuilds_the_same_opening_plan_the_run_used(monkeypatch):
    # `resume_key_for_turn` walks this plan against the stored step rows, so a
    # splice the run planned and the resume did not would report the
    # extension's own step as the one to resume, forever.
    entry = ("ext:demo:seed", "Demo · seed the world")
    _splice_after(monkeypatch, "commit", entry)
    assert establishment_plan(7) == establishment_plan(7)
    assert establishment_plan(7)[-1] == entry
