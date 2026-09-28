"""A30 (review 2026-09-07): an example must show every key its own prompt
asks for.

`OUTPUT_EXAMPLES` is not documentation. `llm_quality` hands it to the model as
`required_json_example` on every repair and fallback call. A key absent from
the object a model is told to imitate reads as not part of the answer.

The prose Director has the same two output keys at both invocation points,
`prose` and `places` (one step, `director_prose`, with a sheet per stage).
Compatibility fields remain on the schemas for old checkpoints, but must not
leak back into the prompt or example. The encoder's channel shapes are
supplied by its selected chunks; its repair example is its card's own
worked example (2026-09-28; `{}` before).

The check reads the PROMPT rather than a list kept here: a key is required in
the example when the step's own sheet names it at the top level of its output
shape AND the step's model declares it. Two spellings of one contract, folded
-- the `check_prompt_schema_ops` convention, applied to the examples.
"""

from __future__ import annotations

import re

import pytest

from llm import prompts, schemas


def _shape_keys(text):
    """Top-level keys an `Output STRICT JSON {...}` shape names.

    Depth-1 `name:` tokens inside the braces the shape opens. A bare key
    (`speech` in interpret's shape, with no colon) is invisible here, which
    is the honest floor: this reports keys the shape SPELLS OUT as fields,
    never a guess about English.
    """
    keys = set()
    for match in re.finditer(r"STRICT JSON", text):
        start = text.find("{", match.end())
        if start < 0:
            continue
        depth = 0
        for i in range(start, len(text)):
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    break
            elif depth == 1 and ch == ":":
                name = re.search(r'["\']?([A-Za-z_][A-Za-z0-9_]*)["\']?\s*$',
                                 text[start:i])
                if name:
                    keys.add(name.group(1))
    return keys


def _requested(step_key, text):
    model = schemas.SCHEMA_MAP.get(step_key)
    fields = set(schemas._fields(model) or {}) if model is not None else set()
    return _shape_keys(text) & fields


def _sheets():
    """{label: (step_key, the sheet the model is actually handed)}, for the
    stages whose sheet carries ONE output shape.

    The prose Director is one step at two stages, so a label names the stage.
    The encoder is deliberately not here: its card teaches one object per
    event, and each granted channel's chunk carries that channel's shape.
    """
    return {
        "director_prose:interpret": (
            "director_prose", prompts.prose_director_prompt("interpret")),
        "director_prose:resolve": (
            "director_prose", prompts.prose_director_prompt("resolve")),
        "director_establish": (
            "director_establish", prompts.DEFAULT_PROMPTS["director_establish"]),
    }


SHEET_STEPS = ["director_prose:interpret", "director_prose:resolve",
               "director_establish"]


class TestEveryRequestedKeyIsShown:
    @pytest.mark.parametrize("label", SHEET_STEPS)
    def test_the_example_shows_what_the_sheet_asks_for(self, label, temp_db):
        step_key, text = _sheets()[label]
        example = schemas.OUTPUT_EXAMPLES.get(step_key)
        assert example is not None, f"{step_key} has no example to repair to"
        missing = sorted(_requested(step_key, text) - set(example))
        assert not missing, (
            f"{step_key}'s sheet asks for {missing} and its example does not "
            "show them, so a repaired call reads them as not part of the "
            "answer")

    def test_the_scan_finds_the_keys_it_is_supposed_to(self, temp_db):
        """The guard's own floor: a shape reader that silently found nothing
        would pass every step forever."""
        sheets = _sheets()
        for label in ("director_prose:interpret", "director_prose:resolve"):
            assert _requested(*sheets[label]) == {"prose", "places"}, label
