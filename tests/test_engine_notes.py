"""What the deterministic layer did to a step's output, where somebody can see it.

`ctx.warnings` was a developer channel nothing in production read
(`docs/UNBUILT.md` 1.11). The cost of that is on the record rather than
hypothetical: in chat 38 turn idx 140, perception dropped both sight sentences
out of a character's view of an embrace happening six feet in front of him,
warned about it, and the warning went into a list with no reader. His view, his
structured observations and his committed memory of that beat were all
sound-only, and the diagnosis took a database excavation.

Two things had to be true to fix that. A warning has to know which step raised
it, and it has to survive the run.
"""

from __future__ import annotations

import json
import time

from agents.runtime import _with_engine_notes
from agents.storage import ENGINE_NOTES_KEY, active_content, save_step
from core.pipeline_context import (
    ChatData, PipelineContext, StepTaggedWarnings, TurnData, current_step_key,
)


def make_context(chat_id=1, turn_id=1):
    return PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                      player_input="test", created=time.time()),
        cast=[],
        input="test",
    )


class TestAWarningKnowsWhichStepRaisedIt:
    def test_both_spellings_are_tagged(self):
        """The engine warns from ~40 sites spelled two different ways. Tagging
        lives in the list rather than at the call sites precisely so neither
        spelling can be the untagged one."""
        ctx = make_context()
        token = current_step_key.set("perception_outcome")
        try:
            ctx.warnings.append("appended directly")
            ctx.add_warning("through the helper")
        finally:
            current_step_key.reset(token)
        assert ctx.warnings_for_step("perception_outcome") == [
            "appended directly", "through the helper"]

    def test_a_warning_raised_outside_any_step_belongs_to_none(self):
        ctx = make_context()
        ctx.add_warning("no step running")
        assert ctx.warnings_for_step("narrator") == []
        assert ctx.warnings == ["no step running"]

    def test_it_is_still_an_ordinary_list_of_strings(self):
        """Several stages and a dozen tests read `warnings` as plain strings;
        the tagging must not change what it is."""
        ctx = make_context()
        ctx.add_warning("one")
        ctx.warnings.extend(["two", "three"])
        assert ctx.warnings == ["one", "two", "three"]
        assert isinstance(ctx.warnings, list)
        assert " / ".join(ctx.warnings) == "one / two / three"

    def test_a_context_built_with_a_plain_list_still_works(self):
        ctx = make_context()
        ctx.warnings = ["from somewhere else"]
        ctx.add_warning("and another")
        assert ctx.warnings == ["from somewhere else", "and another"]
        assert ctx.warnings_for_step("narrator") == []

    def test_siblings_do_not_collect_each_others_warnings(self):
        """The parallel groups run on their own threads against a copied
        context, so attribution by list position would file one step's repair
        under whichever sibling finished first."""
        import contextvars
        import threading

        ctx = make_context()

        def run(key, message):
            current_step_key.set(key)
            ctx.warnings.append(message)

        threads = []
        for key, message in (("mapping_stage", "lore repair"),
                             ("perception_act", "view repair")):
            cv = contextvars.copy_context()
            threads.append(threading.Thread(
                target=lambda cv=cv, k=key, m=message: cv.run(run, k, m)))
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert ctx.warnings_for_step("mapping_stage") == ["lore repair"]
        assert ctx.warnings_for_step("perception_act") == ["view repair"]


class TestTheNotesRideTheSavedContent:
    def test_a_step_with_nothing_to_report_grows_no_key(self):
        """An unchanged pipeline must produce byte-identical content, or every
        stored turn in the corpus reads as modified."""
        ctx = make_context()
        content = {"views": {"player": "You see the door."}}
        assert _with_engine_notes(content, ctx, "perception_act") is content

    def test_a_repair_is_attached_to_the_step_that_made_it(self):
        ctx = make_context()
        token = current_step_key.set("perception_outcome")
        try:
            ctx.add_warning("perception_outcome: dropped self-narration")
        finally:
            current_step_key.reset(token)
        out = _with_engine_notes({"views": {}}, ctx, "perception_outcome")
        assert out[ENGINE_NOTES_KEY]["warnings"] == [
            "perception_outcome: dropped self-narration"]
        assert "views" in out

    def test_concurrency_is_recorded_where_the_ord_column_cannot_say_it(self):
        """The persisted pipeline view reads the steps table long after the
        stream events are gone, and `ord` cannot express "these two ran at
        once"."""
        ctx = make_context()
        out = _with_engine_notes(
            {"relevant_lore": []}, ctx, "mapping_stage",
            parallel_with=["perception_act"])
        assert out[ENGINE_NOTES_KEY]["parallel_with"] == ["perception_act"]

    def test_a_non_dict_output_is_passed_through(self):
        ctx = make_context()
        assert _with_engine_notes("prose", ctx, "narrator") == "prose"


class TestTheNotesNeverReachAModel:
    def test_a_rerun_rehydrates_without_them(self, temp_db):
        """`active_content` is the read path a rerun rehydrates ctx through,
        and several stages hand a prior step's dict to a model wholesale.
        Leaving the notes in would put the engine's own repair log into a
        prompt on resumed runs and nowhere else — the worst kind of difference
        between a fresh run and a resumed one."""
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Test", "", time.time()))
        turn_id = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) "
            "VALUES(?,?,?,?)", (chat_id, 1, "test", time.time()))

        stored = {"views": {"player": "You see the door."},
                  ENGINE_NOTES_KEY: {"warnings": ["dropped something"]}}
        save_step(turn_id, "perception_act", "Perception", 0, stored)

        rehydrated = active_content(turn_id, "perception_act")
        assert rehydrated == {"views": {"player": "You see the door."}}
        assert ENGINE_NOTES_KEY not in rehydrated

    def test_but_they_are_still_on_the_row_for_the_pipeline_view(self, temp_db):
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Test", "", time.time()))
        turn_id = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) "
            "VALUES(?,?,?,?)", (chat_id, 1, "test", time.time()))
        save_step(turn_id, "perception_act", "Perception", 0,
                  {"views": {}, ENGINE_NOTES_KEY: {"warnings": ["kept"]}})

        row = temp_db.q(
            "SELECT v.content FROM steps s JOIN variants v "
            "ON v.step_id=s.id AND v.active=1 WHERE s.turn_id=?",
            (turn_id,), one=True)
        assert json.loads(row["content"])[ENGINE_NOTES_KEY]["warnings"] == [
            "kept"]


class TestAConcurrentGroupEndToEnd:
    """The unit pieces agree; this runs a real group through the real streamer
    so the contextvar copy, the thread fan-out, the save and the events are
    checked together rather than assumed to compose."""

    def test_each_sibling_keeps_its_own_repairs_and_its_own_notes(
            self, temp_db, monkeypatch):
        from agents import runtime

        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Test", "", time.time()))
        turn_id = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) "
            "VALUES(?,?,?,?)", (chat_id, 1, "test", time.time()))

        ctx = make_context(chat_id, turn_id)

        def fake_compute(key, ctx_, nonce):
            token = current_step_key.set(key)
            try:
                ctx_.add_warning(f"{key}: repaired something")
                return {"produced_by": key}
            finally:
                current_step_key.reset(token)

        monkeypatch.setattr(runtime, "compute_step", fake_compute)

        group = [("mapping_stage", "Mapping"), ("perception_act", "Perception")]
        keys = ["director_interpret", "mapping_stage", "perception_act"]
        events = list(runtime._run_parallel_group(
            runtime.Bus(), turn_id, group, keys, ctx))

        starts = [e for e in events if e["type"] == "step_start"]
        assert [e["key"] for e in starts] == ["mapping_stage", "perception_act"]
        assert all(
            e["group"] == ["mapping_stage", "perception_act"] for e in starts)

        for key, sibling in (("mapping_stage", "perception_act"),
                             ("perception_act", "mapping_stage")):
            row = temp_db.q(
                "SELECT v.content FROM steps s JOIN variants v "
                "ON v.step_id=s.id AND v.active=1 "
                "WHERE s.turn_id=? AND s.key=?", (turn_id, key), one=True)
            notes = json.loads(row["content"])[ENGINE_NOTES_KEY]
            assert notes["warnings"] == [f"{key}: repaired something"]
            assert notes["parallel_with"] == [sibling]

    def test_ctx_keeps_the_stages_own_output_unpolluted(
            self, temp_db, monkeypatch):
        """Only what is PERSISTED carries the notes, so no downstream stage
        reads a key its schema never declared."""
        from agents import runtime

        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Test", "", time.time()))
        turn_id = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) "
            "VALUES(?,?,?,?)", (chat_id, 1, "test", time.time()))
        ctx = make_context(chat_id, turn_id)

        def fake_compute(key, ctx_, nonce):
            ctx_.add_warning("something was repaired")
            return {"views": {}}

        monkeypatch.setattr(runtime, "compute_step", fake_compute)
        list(runtime._run_parallel_group(
            runtime.Bus(), turn_id, [("perception_act", "Perception")],
            ["perception_act"], ctx))

        assert ctx["perception_act"] == {"views": {}}


def test_the_step_key_is_restored_after_a_step_finishes():
    """A sequential run must not leave the last step's key standing, or the
    next warning raised between steps is filed under whatever ran last."""
    import inspect

    from agents import runtime
    src = inspect.getsource(runtime.compute_step)
    assert "current_step_key.set" in src
    assert "current_step_key.reset" in src
    assert "finally" in src


def test_a_bare_tagged_list_reports_what_it_was_seeded_with():
    seeded = StepTaggedWarnings(["pre-existing"])
    assert seeded.notes == [{"step": None, "text": "pre-existing"}]
    assert seeded.for_step(None) == ["pre-existing"]
