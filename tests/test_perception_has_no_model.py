"""Perception makes no model call. Not by default — at all.

This replaces `test_perception_no_llm.py`, which pinned the behaviour of
the `PERCEPTION_NO_LLM` env var while the deterministic path was opt-in.
The flag is gone, `_per_observer_model_views` is gone, and the ~1,400 lines
of model path inside the three stage functions are gone with them: every
view is composed from the typed IR in `agents/composer.py`.

Why it went, in the numbers that decided it (design_notes/16, full-corpus
replay, identity-floor era, same scorer on both sides):

| | model path | composer |
|---|---|---|
| delivered-line recall | 94.32% | 99.63% |
| identity-leak views | 107 | 22 |
| self-narration views | 131 | 0 |
| invented dialogue | 7 | 0 |
| concealed-line leaks | 0 | 0 |

The composer is not a cheaper approximation of what the model was doing.
It is better at the thing perception exists to do, because the information
boundary is computed instead of requested — and a boundary that is computed
cannot be declined by a model having an off day.

These tests are structural on purpose. A behavioural test can pass while a
model call sits on a path it did not happen to take; only reading the
module can say the call is not there.
"""

from __future__ import annotations

import ast

import pytest

import agents.perception as perception

STAGES = ("perception_establish", "perception_act", "perception_outcome")


def _tree():
    return ast.parse(open(perception.__file__).read())


def _fn(name):
    return next(n for n in ast.walk(_tree())
                if isinstance(n, ast.FunctionDef) and n.name == name)


def test_the_module_contains_no_model_call():
    """`_agent_json` is the single seam every agent role calls a model
    through. Perception no longer imports it, let alone calls it."""
    source = open(perception.__file__).read()
    assert "_agent_json" not in source
    assert not hasattr(perception, "_agent_json")


def test_the_flag_is_gone_rather_than_defaulted_on():
    """A flag left switched on is a flag someone can switch off. There is
    nothing to switch: no predicate, no env var, no second path."""
    assert not hasattr(perception, "perception_llm_disabled")
    assert "PERCEPTION_NO_LLM" not in open(perception.__file__).read()


def test_the_fan_out_is_gone():
    assert not hasattr(perception, "_per_observer_model_views")


@pytest.mark.parametrize("stage", STAGES)
def test_every_stage_ends_in_the_composer(stage):
    """Each stage assembles its typed inputs and hands off. If a stage ever
    grows a second return, this test is the thing that notices."""
    fn = _fn(stage)
    returns = [n for n in ast.walk(fn) if isinstance(n, ast.Return)]
    assert len(returns) == 1, (
        f"{stage} has {len(returns)} returns; perception has one path")
    call = returns[0].value
    assert isinstance(call, ast.Call)
    assert call.func.id == f"_composer_{stage.split('_', 1)[1]}"


@pytest.mark.parametrize("stage", STAGES)
def test_no_stage_reads_the_omniscient_prose(stage):
    """`resolved_event` is the Director's omniscient account of the beat.
    The model path read it and asked a model to narrate it from one mind's
    side; the composer never touches it. This is the firewall getting
    shorter rather than better guarded."""
    src = ast.unparse(_fn(stage))
    assert "resolved_event" not in src


def test_no_perception_prompt_survives_anywhere():
    """Replay needs the STEP KEY, not a prompt.

    The entry used to be kept on the stated grounds that deleting it "would
    break the replay of every pre-change turn". It would not: replay validates
    a stored step against `schemas.SCHEMA_MAP`, and neither `pipeline_trace`,
    `chat_archive` nor `checkpoints` reads a prompt at all. What the entry
    actually did was appear in the host's prompt editor as if editing it
    changed anything, ride every bootstrap response, and cost 28,467
    characters of translation in each language pack.
    """
    from llm import schemas
    from language_runtime import installed_language_packs
    from llm.prompts import DEFAULT_PROMPTS

    assert "perception" not in DEFAULT_PROMPTS
    for language_id, pack in installed_language_packs().items():
        assert "perception" not in pack.card("system_prompts")["prompts"], language_id
    # Nor a schema. An earlier version of this test asserted `"perception" in
    # SCHEMA_MAP` on the grounds that "the step key is what replay resolves".
    # That was wrong twice over: the real step keys are `perception_act`,
    # `perception_outcome` and `perception_establish`, none of which are in
    # SCHEMA_MAP, and no `perception` step exists anywhere in the live corpus
    # (2,317 turns). Replay never resolved it, and the two `step_key ==
    # "perception"` branches it justified could never fire.
    assert "perception" not in schemas.SCHEMA_MAP
    assert not any(key.startswith("perception") for key in schemas.SCHEMA_MAP)
    assert "_agent_json" not in open(perception.__file__).read()
