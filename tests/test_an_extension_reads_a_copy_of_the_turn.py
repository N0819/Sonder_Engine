"""An extension's read of a running turn is ITS copy, never the turn's own.

Audit 2026-11-01 (web_routes_extensions F3, CONFIRMED by snippet): every read
surface but one handed out the pipeline's LIVE objects. `notify_step_saved`
passed the very dict `ctx[key]` holds, and `StepView.step`,
`PayloadContext.step`, `NarrationContext.step`, `DirectorContext.step`,
`CommitView.step_content` and `CommittedTurn.step_content` all returned
`ctx.get(key)`. An `on_step` observer that tidied what it was handed --
`content["state_diff"]["positions"].pop("Ash")` -- left Ash's move out of
what perception, the narrator and the commit then read, while the stored
`director_resolve` variant (saved before the notification) still carried
it: the durable step and the committed world disagreed, with no routing note
naming the extension. `DirectorResult` was the one surface that copied, and
its docstring states the rule this pins for every other: read-only by
construction.
"""

from __future__ import annotations

import copy

import extension_runtime
from extension_runtime.api import (CommitView, CommittedTurn, DirectorContext,
                                   NarrationContext, PayloadContext, StepView)

from tests.test_extensions import (  # noqa: F401 - fixtures are used by name
    _StubCtx, _chat, _enable, _write_extension, ext_root,
)


def _resolve():
    return {"resolved_event": "Ash crosses to the door.",
            "state_diff": {"positions": {"Ash": "hall"}},
            "dialogue_log": [{"speaker": "Ash", "line": "Wait."}]}


def _bare(ext_root):
    _write_extension(ext_root, "reader", {
        "id": "reader", "version": "1.0.0", "ext_api": 1, "name": "Reader",
        "capabilities": {"python": "extension.py"},
    }, {"extension.py": "def register(api):\n    pass\n"})
    _enable("reader")
    return extension_runtime._apis["reader"]


def test_a_step_observer_that_edits_its_content_changes_nothing_the_turn_reads(
        temp_db, ext_root):
    api = _bare(ext_root)
    resolve = _resolve()
    ctx = _StubCtx(chat_id=_chat(temp_db), values={"director_resolve": resolve})
    pristine = copy.deepcopy(resolve)

    def tidy(key, content):
        content["state_diff"]["positions"].pop("Ash", None)
        content["resolved_event"] = "nothing happened"

    api.on_step("director_resolve", tidy)
    # The runtime hands the observer the very object the context holds
    # (`_with_engine_notes` returns it unchanged when a step has no notes).
    extension_runtime.notify_step_saved(ctx, "director_resolve",
                                        ctx.get("director_resolve"))

    assert ctx.get("director_resolve") == pristine
    assert extension_runtime.observer_failures().get("reader", 0) == 0


def test_two_observers_cannot_pass_notes_through_the_content(temp_db, ext_root):
    api = _bare(ext_root)
    seen = []
    api.on_step("*", lambda key, content: content.setdefault("smuggled", 1))
    api.on_step("*", lambda key, content: seen.append(dict(content)))
    ctx = _StubCtx(chat_id=_chat(temp_db))

    extension_runtime.notify_step_saved(ctx, "narrator", {"prose": "hi"})

    assert seen == [{"prose": "hi"}]


def test_a_stage_that_edits_its_view_changes_nothing_the_turn_reads(
        temp_db, ext_root):
    from agents.runtime import compute_step

    api = _bare(ext_root)
    resolve = _resolve()
    ctx = _StubCtx(chat_id=_chat(temp_db), values={"director_resolve": resolve})
    pristine = copy.deepcopy(resolve)

    def stage(view, api_, nonce):
        view.state_diff["positions"].pop("Ash", None)
        view.dialogue_log.clear()
        view.step("director_resolve")["resolved_event"] = "rewritten"
        return {"ok": True}

    api.add_stage("tidy", anchor="after:director_resolve", handler=stage)
    assert compute_step("ext:reader:tidy", ctx, 0) == {"ok": True}

    assert ctx.get("director_resolve") == pristine


def test_every_context_step_read_is_a_copy(temp_db, ext_root):
    api = _bare(ext_root)
    resolve = _resolve()
    ctx = _StubCtx(chat_id=_chat(temp_db), values={"director_resolve": resolve})
    pristine = copy.deepcopy(resolve)

    readers = [
        StepView(ctx).step,
        PayloadContext(api, ctx, 7).step,
        NarrationContext(api, ctx).step,
        DirectorContext(api, ctx, phase="resolve").step,
        CommitView(api, ctx).step_content,
        CommittedTurn(api, ctx).step_content,
    ]
    for read in readers:
        got = read("director_resolve")
        assert got == pristine
        got["state_diff"]["positions"].clear()
        got["resolved_event"] = ""

    assert ctx.get("director_resolve") == pristine
