"""The Director seam: standing campaign context and Director payload hooks.

Three seams now exist and the difference between them is the whole reason
there are three. `on_character_payload` shapes what one MIND believes.
`on_narration_payload` shapes what the READER is told. This one shapes what
the ENGINE believes happened -- and that is the one that propagates: into
`state_diff`, into perception, into memory, into every beat after it. A
narration edit is wrong on one page; a Director edit is wrong in the world.

So the properties pinned here are the ones that make a campaign layer safe to
leave installed for a thousand turns: per-phase, replaced rather than appended,
attributed, bounded, hooked once per beat rather than once per attempt, and
underneath it all a deterministic floor the seam cannot reach.
"""

from __future__ import annotations

import pytest

import extension_runtime
from extension_runtime import ExtensionError

from tests.test_extensions import (  # noqa: F401 - fixtures are used by name
    _StubCtx, _chat, _enable, _write_extension, ext_root, real_ext_root,
)


@pytest.fixture
def bare(ext_root):
    """One enabled extension whose python entry does nothing."""
    _write_extension(ext_root, "campaign", {
        "id": "campaign", "version": "1.0.0", "ext_api": 1, "name": "Campaign",
        "capabilities": {"python": "extension.py", "chat_state": True},
    }, {"extension.py": "def register(api):\n    pass\n"})
    _enable("campaign")
    return extension_runtime._apis["campaign"]


def _dispatch(chat_id, payload=None, *, phase="resolve", ctx=None):
    return extension_runtime.dispatch_director_payload(
        ctx or _StubCtx(chat_id=chat_id), payload if payload is not None else {},
        phase=phase)


# ------------------------------------------------------------------- blocks


class TestDirectorBlocks:
    def test_an_installed_block_reaches_the_phase_it_was_set_for(self, temp_db,
                                                                 bare):
        chat_id = _chat(temp_db)
        bare.director_context(chat_id).set(
            resolve="A sealed deck refuses entry however it is attempted.")

        out = _dispatch(chat_id, {"scene": {}}, phase="resolve")

        assert out["extension_context"] == [
            {"source": "campaign",
             "text": "A sealed deck refuses entry however it is attempted.",
             "revision": 1}]
        assert out["scene"] == {}

    def test_a_block_does_not_leak_into_the_other_phases(self, temp_db, bare):
        """Interpret reads the player's declaration; resolve decides what it
        did. A rule aimed at one and applied to both is how an interpretive
        constraint starts silently vetoing outcomes."""
        chat_id = _chat(temp_db)
        bare.director_context(chat_id).set(interpret="Only interpret.")

        assert "extension_context" in _dispatch(chat_id, phase="interpret")
        assert "extension_context" not in _dispatch(chat_id, phase="resolve")
        assert "extension_context" not in _dispatch(chat_id, phase="establish")

    def test_every_phase_can_carry_its_own_block(self, temp_db, bare):
        chat_id = _chat(temp_db)
        bare.director_context(chat_id).set(
            establish="Opening.", interpret="Reading.", resolve="Deciding.")

        for phase, text in (("establish", "Opening."),
                            ("interpret", "Reading."),
                            ("resolve", "Deciding.")):
            out = _dispatch(chat_id, phase=phase)
            assert out["extension_context"][0]["text"] == text

    def test_no_block_leaves_the_payload_untouched(self, temp_db, bare):
        """The overwhelmingly common beat must cost the payload nothing.

        Not merely "no text": no KEY, for the reason the narration seam gives
        -- an always-empty field is one the model must be told to ignore on
        every beat of every story that never installed one.
        """
        payload = {"scene": {}}
        out = _dispatch(_chat(temp_db), payload)

        assert "extension_context" not in out
        assert out == payload

    def test_setting_a_block_replaces_rather_than_appends(self, temp_db, bare):
        chat_id = _chat(temp_db)
        block = bare.director_context(chat_id)
        block.set(resolve="Deck 4 is sealed.")
        block.set(resolve="Deck 4 is open again.")

        out = _dispatch(chat_id)

        assert out["extension_context"] == [
            {"source": "campaign", "text": "Deck 4 is open again.",
             "revision": 2}]

    def test_setting_one_phase_leaves_the_other_alone(self, temp_db, bare):
        """The common caller rebuilds one phase per host action.

        `None` means "not mine to say this time". If it cleared the other
        phase, a campaign that updates its resolve rule on an away mission
        would silently drop its interpret rule and never know.
        """
        chat_id = _chat(temp_db)
        block = bare.director_context(chat_id)
        block.set(interpret="Standing.", resolve="Also standing.")
        block.set(resolve="Rewritten.")

        assert block.text("interpret") == "Standing."
        assert block.text("resolve") == "Rewritten."

    def test_setting_empty_text_clears_that_phase(self, temp_db, bare):
        chat_id = _chat(temp_db)
        block = bare.director_context(chat_id)
        block.set(interpret="Standing.", resolve="Also standing.")
        block.set(resolve="   ")

        assert block.text("interpret") == "Standing."
        assert block.get("resolve") is None
        assert "extension_context" not in _dispatch(chat_id, phase="resolve")

    def test_reinstalling_identical_text_does_not_bump_the_revision(
            self, temp_db, bare):
        """A `syncForChat` loop would otherwise drive it to the turn count."""
        chat_id = _chat(temp_db)
        block = bare.director_context(chat_id)
        first = block.set(resolve="Deck 4 is sealed.")["resolve"]
        again = block.set(resolve="Deck 4 is sealed.")["resolve"]

        assert first["revision"] == again["revision"] == 1
        assert first["hash"] == again["hash"]

    def test_clearing_one_phase_and_clearing_all(self, temp_db, bare):
        chat_id = _chat(temp_db)
        block = bare.director_context(chat_id)
        block.set(interpret="A.", resolve="B.")

        block.clear("interpret")
        assert block.get("interpret") is None
        assert block.text("resolve") == "B."

        block.clear()
        assert block.get() == {}

    def test_an_unknown_phase_is_refused_rather_than_stored(self, temp_db,
                                                            bare):
        """A typo'd phase that stored silently is a campaign rule that never
        runs and nothing anywhere objecting."""
        chat_id = _chat(temp_db)
        with pytest.raises(ExtensionError) as excinfo:
            bare.director_context(chat_id).set(narrator="Wrong seam.")

        assert "narrator" in str(excinfo.value)
        assert bare.director_context(chat_id).get() == {}

    def test_an_oversized_block_is_refused_rather_than_truncated(self, temp_db,
                                                                 bare):
        chat_id = _chat(temp_db)
        with pytest.raises(ExtensionError) as excinfo:
            bare.director_context(chat_id).set(resolve="x" * 8001)

        assert "8000" in str(excinfo.value)
        assert bare.director_context(chat_id).get() == {}

    def test_the_ceiling_is_per_phase_not_per_extension(self, temp_db, bare):
        """A campaign with a full interpret rule and a full resolve rule pays
        two payloads, never one of 16,000."""
        chat_id = _chat(temp_db)
        bare.director_context(chat_id).set(
            interpret="i" * 8000, resolve="r" * 8000)

        assert len(_dispatch(chat_id, phase="interpret")
                   ["extension_context"][0]["text"]) == 8000
        assert len(_dispatch(chat_id, phase="resolve")
                   ["extension_context"][0]["text"]) == 8000

    def test_a_block_is_scoped_to_one_story(self, temp_db, bare):
        first, second = _chat(temp_db), _chat(temp_db)
        bare.director_context(first).set(resolve="Only the first story.")

        assert "extension_context" not in _dispatch(second)

    def test_a_block_is_attributed_on_the_turn_with_its_phase(self, temp_db,
                                                              bare):
        """Which phase an extension spoke into is half the answer.

        "campaign told the Director something" and "campaign told the Director
        what the player's words MEANT" are different facts about a beat, and
        only the second explains a resolution nobody asked for.
        """
        chat_id = _chat(temp_db)
        bare.director_context(chat_id).set(interpret="Standing.")
        ctx = _StubCtx(chat_id=chat_id)

        _dispatch(chat_id, phase="interpret", ctx=ctx)

        assert extension_runtime.routing_notes(ctx) == [
            {"ext": "campaign", "char_id": None, "scope": "director_interpret",
             "changed": ["extension_context"]}]


# -------------------------------------------------------------------- hooks


class TestDirectorHooks:
    def test_a_hook_may_rewrite_the_payload(self, temp_db, bare):
        bare.on_director_payload(
            lambda payload, info: {**payload, "campaign_rules": ["sealed"]})

        out = _dispatch(_chat(temp_db), {"scene": {}})

        assert out["campaign_rules"] == ["sealed"]
        assert out["scene"] == {}

    def test_a_hook_sees_which_phase_it_is_answering(self, temp_db, bare):
        seen = []
        bare.on_director_payload(
            lambda payload, info: seen.append(info.phase) or None)
        chat_id = _chat(temp_db)

        for phase in ("establish", "interpret", "resolve"):
            _dispatch(chat_id, phase=phase)

        assert seen == ["establish", "interpret", "resolve"]

    def test_a_hook_that_mutates_in_place_is_still_attributed(self, temp_db,
                                                              bare):
        """The hole the character seam had, closed the same way.

        A hook handed the real payload can mutate both sides of a naive
        comparison at once and come back with an empty diff -- an unattributed
        edit to what the engine believes happened.
        """
        def hook(payload, info):
            payload["scene"] = {"location": "somewhere it is not"}
            return payload

        bare.on_director_payload(hook)
        ctx = _StubCtx(chat_id=_chat(temp_db))

        extension_runtime.dispatch_director_payload(
            ctx, {"scene": {"location": "the real one"}}, phase="resolve")

        assert extension_runtime.routing_notes(ctx) == [
            {"ext": "campaign", "char_id": None, "scope": "director_resolve",
             "changed": ["scene"]}]

    def test_a_hook_may_rewrite_the_standing_blocks(self, temp_db, bare):
        """Blocks are assembled first, so a hook is the escape hatch."""
        chat_id = _chat(temp_db)
        bare.director_context(chat_id).set(resolve="Standing.")
        bare.on_director_payload(
            lambda payload, info: {**payload, "extension_context": []})

        assert _dispatch(chat_id)["extension_context"] == []

    def test_a_raising_hook_leaves_the_payload_exactly_as_assembled(
            self, temp_db, bare):
        def hook(payload, info):
            raise RuntimeError("campaign planner exploded")

        bare.on_director_payload(hook)
        payload = {"scene": {"location": "the real one"}}

        assert _dispatch(_chat(temp_db), payload) == payload

    def test_a_hook_returning_a_non_dict_is_ignored(self, temp_db, bare):
        bare.on_director_payload(lambda payload, info: "not a payload")
        payload = {"scene": {}}

        assert _dispatch(_chat(temp_db), payload) == payload

    def test_a_disabled_extension_stops_contributing_immediately(self, temp_db,
                                                                 bare):
        """Disable is the kill switch the report asked for by name."""
        chat_id = _chat(temp_db)
        bare.director_context(chat_id).set(resolve="Standing.")
        bare.on_director_payload(
            lambda payload, info: {**payload, "hooked": True})

        extension_runtime.disable_extension("campaign")
        out = _dispatch(chat_id)

        assert "extension_context" not in out
        assert "hooked" not in out


# ------------------------------------------------------------------ wiring


class TestDirectorWiring:
    """That the seam is actually reached, and reached once per beat.

    `dispatch_director_payload` passing its own unit tests proves nothing about
    whether any Director call ever calls it -- which was the exact shape of the
    reasoning-trace defect: both halves built, correct, and never introduced.
    """

    def test_all_three_director_stages_call_the_seam(self):
        import inspect

        import agents.director as director

        source = inspect.getsource(director)
        for phase in ("establish", "interpret", "resolve"):
            assert (f'_extension_director_payload(ctx, payload, phase="{phase}")'
                    in source), f"director_{phase} does not reach the seam"

    def test_the_seam_is_total(self):
        """A broken extension must cost the beat nothing, so the wrapper
        swallows rather than propagates -- it runs inside the turn's clock."""
        import agents.director as director

        payload = {"scene": {}}
        assert director._extension_director_payload(
            None, payload, phase="resolve") == payload

    def test_resolve_hooks_the_payload_the_retries_reuse(self):
        """Once per beat, not once per attempt.

        The world-pressure floor and the player-act authority correction both
        re-enter generation with `{**payload, "correction_notes": ...}`. If the
        seam ran per attempt, a correction could be answered against campaign
        context the answer it corrects never saw.
        """
        import inspect

        import agents.director as director

        source = inspect.getsource(director.director_resolve)
        seam = source.index('_extension_director_payload')
        first_call = source.index('out = _agent_json(', seam)
        retries = [i for i in range(len(source))
                   if source.startswith('{**payload, "correction_notes"', i)]

        assert retries, "expected the resolve retries to rebuild from payload"
        assert all(i > first_call for i in retries)
        assert source.count('_extension_director_payload') == 1
