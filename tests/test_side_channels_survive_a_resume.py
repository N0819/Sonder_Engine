"""Every value a stage leaves on the context is declared, and the two that
carry information forward are put back on a resume.

Review 2026-09-07 finding A31. `runtime._rehydrate_side_channels` rebuilt five
cross-stage values; perception wrote four more and nothing said so. Two of
them carry information a later stage needs and cannot re-derive:

  `_player_room` -- the room the beat ARRIVED in. `director_resolve` reads it
  directly, because it is the stage that decides where the beat ends up and
  needs the room the player came from. On a resume from that stage it was
  None: the player's own room dropped out of the figure aperture and the two
  movement floors under it were handed nothing.

  `_composer_turn_ledger` -- what each observer's view has already carried
  this turn, which is how the composer knows a body has been described once.
  `perception_outcome` merges the previous turn's ledger with this turn's; on
  a resume the act pass's half was gone, so every observer was re-handed a
  first-mention description of everyone present.

Both were already ON the step content -- the room is now stamped there by
`perception._stage_player_room`, the ledger has always been there under
`composer_ledger` -- and nothing read them back. The last test is the
structural half: a new writer must name its channel in
`runtime.SIDE_CHANNELS`, which is what makes the omission visible instead of
silent.
"""

from __future__ import annotations

import agents.perception as perception
import agents.runtime as runtime
from core.pipeline_context import ChatData, PipelineContext, TurnData


def _ctx():
    return PipelineContext(
        chat=ChatData(id=1, name="c", persona_id=None, lorebook_id=None,
                      scenario="", created=0.0),
        turn=TurnData(id=1, chat_id=1, idx=3, player_input="", created=0.0,
                      frame_id=None),
        cast=[], input="")


class TestTheOnsetRoom:
    def test_a_perception_stage_stamps_the_room_it_resolved(self):
        ctx = _ctx()
        ctx["_player_room"] = "gallery"

        out = perception._stage_player_room({"views": {}}, ctx)

        assert out["player_room"] == "gallery"

    def test_the_stamp_is_empty_when_the_stage_placed_nobody(self):
        assert perception._stage_player_room({}, _ctx())["player_room"] == ""

    def test_a_resume_gets_the_room_back(self):
        """The defect. Hydrating `perception_act`'s content restored the
        views; the room the views were built from was lost."""
        ctx = _ctx()
        content = {"views": {}, "player_room": "gallery"}

        ctx["perception_act"] = content
        assert ctx.get("_player_room") is None
        runtime._rehydrate_side_channels(ctx, "perception_act", content)

        assert ctx.get("_player_room") == "gallery"

    def test_the_later_stage_wins(self):
        """The onset room and the outcome room are different facts about one
        beat, and the caller walks the hydrated steps in ord order, so the
        live turn's last answer is the one that stands."""
        ctx = _ctx()
        runtime._rehydrate_side_channels(
            ctx, "perception_act", {"player_room": "gallery"})
        runtime._rehydrate_side_channels(
            ctx, "perception_outcome", {"player_room": "stairwell"})

        assert ctx.get("_player_room") == "stairwell"

    def test_a_stage_that_placed_nobody_does_not_erase_the_room(self):
        ctx = _ctx()
        runtime._rehydrate_side_channels(
            ctx, "perception_act", {"player_room": "gallery"})
        runtime._rehydrate_side_channels(
            ctx, "perception_outcome", {"player_room": ""})

        assert ctx.get("_player_room") == "gallery"


class TestTheComposerLedger:
    def test_a_resume_gets_the_turn_ledger_back(self):
        ctx = _ctx()
        content = {"views": {}, "composer_ledger": {"7": {"described": ["Mara"]}}}

        runtime._rehydrate_side_channels(ctx, "perception_act", content)

        assert ctx.get("_composer_turn_ledger") == {
            "7": {"described": ["Mara"]}}

    def test_two_stages_merge_the_way_the_live_turn_merged_them(self):
        """`perception_outcome` merges its own ledger over the act pass's;
        restoring them in ord order reproduces that, per observer, without
        any observer's entry reaching another's."""
        ctx = _ctx()
        runtime._rehydrate_side_channels(
            ctx, "perception_act",
            {"composer_ledger": {"7": {"described": ["Mara"]},
                                 "9": {"described": []}}})
        runtime._rehydrate_side_channels(
            ctx, "perception_outcome",
            {"composer_ledger": {"9": {"described": ["Kell"]}}})

        assert ctx.get("_composer_turn_ledger") == {
            "7": {"described": ["Mara"]},
            "9": {"described": ["Kell"]},
        }


class TestTheRegister:
    def test_every_declared_channel_is_a_string_with_a_reason(self):
        assert runtime.SIDE_CHANNELS
        for name, why in runtime.SIDE_CHANNELS.items():
            assert isinstance(name, str) and name
            assert isinstance(why, str) and len(why) > 10, name

    def test_the_two_rebuilt_channels_say_so(self):
        for name in ("_player_room", "_composer_turn_ledger", "outcome_scene",
                     "interaction_views"):
            assert runtime.SIDE_CHANNELS[name].startswith("rebuilt")

    def test_the_structure_check_holds_the_register_against_the_source(self):
        """The guard itself: an unregistered writer is an error, not a
        silently-None channel on the next resume."""
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
        import project_check  # noqa: E402

        errors = []
        project_check.check_pipeline_side_channels(errors)

        assert errors == []


class TestTheWalkerSeesEveryWriteForm:
    """The guard's own class defect (A31 rework).

    The register shipped naming 21 channels and missing three --
    `reaction_views`, `character_turn_snapshot` and `absent_reactors_noted` --
    and the guard could not have caught them, because it knew one write form
    and those three are written only by the other two. `setdefault` is a
    write: the first stage to call it creates the channel and every later
    stage in the turn reads what it left.
    """

    def _keys(self, source):
        import ast
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
        import project_check  # noqa: E402

        tree = ast.parse(source)
        constants = project_check._module_string_constants(tree)
        found = []
        for node in ast.walk(tree):
            found.extend(
                project_check._pipeline_context_channel_writes(node, constants))
        return found

    def test_a_plain_assignment_is_a_write(self):
        assert self._keys('ctx["_player_room"] = room') == ["_player_room"]
        assert self._keys('ctx._extra["outcome_scene"] = sc') == [
            "outcome_scene"]

    def test_setdefault_is_a_write(self):
        """`loops.rehydrate_loop_views` creates `reaction_views` this way, and
        so do `character_turn_snapshot` (loops.py:754/803, character.py:3237)
        and `absent_reactors_noted` (loops.py:456)."""
        assert self._keys('views = ctx._extra.setdefault("reaction_views", {})') \
            == ["reaction_views"]
        assert self._keys('ctx.setdefault("_books", [])') == ["_books"]

    def test_a_write_into_a_channel_is_a_write(self):
        """`ctx._extra["reaction_views"][rid] = view` (loops.py:1379): the
        channel is the inner key, not the body it indexes."""
        assert self._keys('ctx._extra["reaction_views"][rid] = view') == [
            "reaction_views"]

    def test_somebody_elses_dict_is_not_a_channel(self):
        assert self._keys('shared.setdefault("scene", {})') == []
        assert self._keys('local["_player_room"] = room') == []

    def test_a_module_constant_key_still_resolves(self):
        assert self._keys('KEY = "_books"\nctx._extra.setdefault(KEY, [])') \
            == ["_books"]

    def test_the_three_missed_channels_are_now_registered(self):
        for name in ("reaction_views", "character_turn_snapshot",
                     "absent_reactors_noted"):
            assert name in runtime.SIDE_CHANNELS, name
        assert runtime.SIDE_CHANNELS["reaction_views"].startswith("rebuilt")


class TestTheEstablishmentResume:
    """The opening turn hydrates its own prior steps, and rebuilds their side
    channels too (A31 rework).

    `perception_establish` composes views exactly as `perception_act` does and
    stamps the same `player_room`; the establishment branch restored the step
    content and nothing else, so a resume from the opening narrator ran
    against a None room.
    """

    def test_every_hydration_in_the_pipeline_rehydrates_its_channels(self):
        import ast
        import inspect
        import textwrap

        tree = ast.parse(textwrap.dedent(inspect.getsource(runtime)))
        run = next(n for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef)
                   and n.name == "_run_pipeline")
        hydrations = 0
        for node in ast.walk(run):
            for field in ("body", "orelse", "finalbody"):
                block = getattr(node, field, None)
                if not isinstance(block, list):
                    continue
                for i, stmt in enumerate(block):
                    if not (isinstance(stmt, ast.Assign)
                            and len(stmt.targets) == 1
                            and isinstance(stmt.targets[0], ast.Subscript)
                            and isinstance(stmt.targets[0].value, ast.Name)
                            and stmt.targets[0].value.id == "ctx"
                            and isinstance(stmt.targets[0].slice, ast.Name)):
                        continue
                    hydrations += 1
                    rest = ast.Module(body=block[i + 1:], type_ignores=[])
                    assert any(
                        isinstance(c, ast.Call)
                        and isinstance(c.func, ast.Name)
                        and c.func.id == "_rehydrate_side_channels"
                        for c in ast.walk(rest)), (
                        "a hydration at line %d restores the step content "
                        "without rebuilding its side channels" % stmt.lineno)
        # Two: the establishment plan's and the normal plan's.
        assert hydrations == 2
