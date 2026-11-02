"""An output example shows only fields its own schema keeps.

A repair or fallback rung hands the model `output_example(step)` as the
shape to answer in, so a key the example shows and the schema drops is a
field the model is taught to write and that is then discarded -- the
`held_by` class (a field a card asks the model to WRITE must be on the output
schema; `held_by` was dropped 26 days). The repair example showed
`"sources": ["s3"]` on a recovered event; `UnifiedEvent` has no such field,
and `agents/director_repair.py` overwrites it with the job's own sentences
(`event.setdefault("sources", ...)`), so the answer was paid for and lost
(review 2026-11-01, llm_schemas_prompts F5/F6). The engine recomputes which
sentences an event encodes (`director_repair.attribute`), so the field is not
asked for.
"""
from __future__ import annotations

import copy

import pytest

from llm.schemas import OUTPUT_EXAMPLES, validate_llm_output_strict


def _paths(value, prefix=""):
    out = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if item is None:
                continue
            path = f"{prefix}.{key}" if prefix else str(key)
            out.add(path)
            out |= _paths(item, path)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            out |= _paths(item, f"{prefix}.{index}" if prefix else str(index))
    return out


@pytest.mark.parametrize("step", sorted(OUTPUT_EXAMPLES))
def test_validating_the_example_drops_nothing_it_shows(step):
    example = OUTPUT_EXAMPLES[step]
    report = validate_llm_output_strict(step, copy.deepcopy(example))
    assert report.valid, report.errors
    assert sorted(_paths(example) - _paths(report.output)) == []
