"""A30 (review 2026-09-07): an example must show every key its own prompt
asks for.

`OUTPUT_EXAMPLES` is not documentation. `llm_quality` hands it to the model as
`required_json_example` on every repair and fallback call. A key absent from
the object a model is told to imitate reads as not part of the answer.

The causal Director deliberately has one output key at both invocation
points: `ledgers`. Compatibility fields remain on the schemas for old
checkpoints, but must not leak back into the prompt or example. Specialists
likewise teach only transforms, receipts, and blocker notes; channel-specific
patch shapes are supplied by their selected chunks.

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
    """{step_key: the sheet the model is actually handed}, for the stages
    whose sheet carries ONE output shape.

    The specialists are deliberately not here: their cores say "one object
    holding exactly the channels the blocks below teach" and each block ends
    with its own `Shape:` line, so their requirement is the channel roster
    and `TestASpecialistShowsEveryChannelItOwns` asks it that way.
    """
    return {
        "director_interpret": prompts.DEFAULT_PROMPTS["director_interpret"],
        "director_establish": prompts.DEFAULT_PROMPTS["director_establish"],
        "director_resolve": prompts.prose_author_prompt(None),
    }


SHEET_STEPS = ["director_interpret", "director_establish", "director_resolve"]


class TestEveryRequestedKeyIsShown:
    @pytest.mark.parametrize("step_key", SHEET_STEPS)
    def test_the_example_shows_what_the_sheet_asks_for(self, step_key,
                                                       temp_db):
        text = _sheets()[step_key]
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
        interpret = _requested("director_interpret",
                               sheets["director_interpret"])
        assert interpret == {"ledgers"}
        resolve = _requested("director_resolve", sheets["director_resolve"])
        assert resolve == {"ledgers"}


class TestASpecialistShowsTheTransformEnvelope:
    """Specialist examples teach the positional transform envelope.

    Selected chunks teach the value nested under ``patch[channel]``; direct
    top-level channel fields exist only to read legacy saved responses.
    """

    @pytest.mark.parametrize("step_key", sorted(schemas.SPECIALIST_CHANNELS))
    def test_transform_receipts_and_notes_are_shown(self, step_key, temp_db):
        example = schemas.OUTPUT_EXAMPLES.get(step_key) or {}
        missing = sorted({"results", "notes"} - set(example))
        assert not missing, f"{step_key}'s example omits {missing}"
        result = example["results"][0]
        assert {"transforms", "status"} <= set(result)
        assert "item_id" not in result


class TestAnExampleTeachesOnlyChannelsTheHandOwns:
    @pytest.mark.parametrize("step_key", sorted(schemas.SPECIALIST_CHANNELS))
    def test_transform_patch_uses_an_owned_channel(self, step_key, temp_db):
        owned = set(schemas.SPECIALIST_CHANNELS[step_key])
        for result in schemas.OUTPUT_EXAMPLES[step_key]["results"]:
            for transform in result["transforms"]:
                assert set(transform["patch"]) <= owned
