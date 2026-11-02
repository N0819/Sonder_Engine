"""Validation reads a field's declared shape once, and dumps as it did.

Profiled on the largest stored `director_resolve` (163 KB, review
2026-11-01, llm_schemas_prompts E1/E2): `_declared(field)` -- the field's
shape read off its annotation with `get_args`/`get_origin` -- was recomputed
for every field of every validation, ~35% of the time; the `_plain` walk
that turns enum members into values was another ~34%. Fields are fixed once
a model class exists, so the shape is read once per (class, field); and the
walk dispatches on the exact type of the common case before the
`isinstance` checks, with the same output by construction (JSON mode would
not be: it turns NaN into null and tuples into lists). Measured on that
resolve: 18.2 ms -> 12.6 ms a validation.
"""
from __future__ import annotations

import copy
import math
from collections import OrderedDict
from enum import Enum, IntEnum

import pytest

from llm import schemas


def _reference_plain(value):
    """The walk as it stood, kept as the specification."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {k: _reference_plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_reference_plain(v) for v in value]
    return value


def _same(a, b):
    """Equal, of exactly the same types all the way down, NaN equal to NaN."""
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return list(a) == list(b) and all(_same(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    if isinstance(a, float) and math.isnan(a):
        return math.isnan(b)
    return a == b


class _Level(IntEnum):
    low = 1


class _Mood(str, Enum):
    calm = "calm"


class _MyDict(dict):
    pass


class _MyList(list):
    pass


EDGES = [
    {"a": (1, _Mood.calm), "b": {1: _Mood.calm}, "c": [_Level.low, True, None,
                                                     float("nan"), b"x", {"s"}]},
    OrderedDict(x=[_Mood.calm]), _MyDict(y=_MyList([_Level.low, 2.5])),
    schemas.SpeechVolume.loud, "plain", 0, False, None,
]


@pytest.mark.parametrize("value", EDGES)
def test_the_walk_is_the_walk_it_was(value):
    assert _same(schemas._plain(value), _reference_plain(value))


@pytest.mark.parametrize("step", sorted(schemas.OUTPUT_EXAMPLES))
def test_every_example_dumps_as_it_did(step):
    model = schemas.SCHEMA_MAP.get(step)
    if model is None:
        pytest.skip("no model")
    validated = schemas._validate(
        model, schemas.preprocess_llm_output(step, copy.deepcopy(
            schemas.OUTPUT_EXAMPLES[step])))
    raw = validated.model_dump(exclude_none=True)
    assert _same(schemas._plain(raw), _reference_plain(raw))


def test_a_field_shape_is_read_once_per_class(monkeypatch):
    calls = []
    real = schemas._declared
    monkeypatch.setattr(schemas, "_declared",
                        lambda field: calls.append(field) or real(field))
    schemas._DECLARED_CACHE.clear()
    example = schemas.OUTPUT_EXAMPLES["director_specialist"]
    first = schemas.validate_llm_output_strict(
        "director_specialist", copy.deepcopy(example))
    read_once = len(calls)
    second = schemas.validate_llm_output_strict(
        "director_specialist", copy.deepcopy(example))
    assert read_once > 0 and len(calls) == read_once
    assert first.output == second.output and first.valid and second.valid
