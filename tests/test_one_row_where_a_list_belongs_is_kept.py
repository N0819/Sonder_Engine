"""One object where a list of them belongs is one row, never silently none.

`CharacterOutput.remember_lines` and `memory_disputes` returned `[]` for a
single object -- a line the character chose to keep, dropped with no note --
while `association_updates` beside them, given the same shape, was wrapped
by the base coercion. And a relationship update naming an axis outside the
set (`{axis: "affection", delta: 0.1}`) validated as an all-zero update,
silently (review 2026-11-01, llm_schemas_prompts F11). Both are dormant
today -- `character_bare.compile_bare` writes canonical lists -- and both
were the silent kind of drop this module otherwise says aloud.
"""
from __future__ import annotations

import pytest

from core.pipeline_context import current_warning_sink
from llm.schemas import CharacterOutput, RelationshipUpdate


@pytest.fixture
def said():
    seen = []
    token = current_warning_sink.set(seen.append)
    yield seen
    current_warning_sink.reset(token)


def test_a_single_remembered_line_is_kept():
    out = CharacterOutput(remember_lines={"quote": "Meet me at dawn",
                                          "why": "a promise"})
    assert [line.quote for line in out.remember_lines] == ["Meet me at dawn"]


def test_a_single_dispute_is_kept():
    out = CharacterOutput(memory_disputes={"gist": "the stranger at the gate",
                                           "now_reads": "it was Bran, disguised"})
    assert len(out.memory_disputes) == 1


def test_a_string_where_rows_belong_is_said(said):
    out = CharacterOutput(remember_lines="Meet me at dawn")
    assert out.remember_lines == []
    assert any("remember_lines" in w for w in said), said


def test_an_axis_outside_the_set_is_said(said):
    update = RelationshipUpdate(target_entity="Bran", axis="affection", delta=0.1)
    assert update.warmth_delta == 0 and update.trust_delta == 0
    assert any("affection" in w for w in said), said
