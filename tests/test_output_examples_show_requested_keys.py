"""A30 (review 2026-09-07): an example must show every key its own prompt
asks for.

`OUTPUT_EXAMPLES` is not documentation. `llm_quality` hands it to the model as
`required_json_example` on every repair and fallback call, and this file's own
comments state the consequence twice: a key absent from the object a model is
told to imitate "reads as not part of the answer", and `background_react`'s
missing example steered a compliant model to return `{}` -- which validated,
silently swallowing the reaction.

Measured at head before this test: the interpret example showed neither
`state_assertions` (what the player says happens, happens that turn) nor
`ledger_notes` (the ruling that dispatches the specialists at all), nor
`contact_assertions`, `follow_op` or `other_players`; the prose author's
showed neither `ledger_notes`, `thoughts_omitted`, `travel_interrupted` nor
`world_pressure`; establish's showed neither `weather`, `crowd_ops`,
`comms_ops` nor `world_pressure`. Every one of them is a key the sheet asks
for in the same breath, so a repaired call read it as no part of the answer.

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
                name = re.search(r"([A-Za-z_][A-Za-z0-9_]*)\s*$",
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
        assert {"state_assertions", "ledger_notes", "contact_assertions",
                "follow_op", "other_players"} <= interpret
        resolve = _requested("director_resolve", sheets["director_resolve"])
        assert {"ledger_notes", "thoughts_omitted", "travel_interrupted",
                "world_pressure", "state_diff"} <= resolve


class TestASpecialistShowsEveryChannelItOwns:
    """A specialist sheet carries no single output shape -- its core says
    "one object holding exactly the channels the blocks below teach", and
    each block ends with its own `Shape:` line. So the requirement is the
    channel roster itself, plus the `notes` every core asks for."""

    @pytest.mark.parametrize("step_key", sorted(schemas.SPECIALIST_CHANNELS))
    def test_every_channel_and_notes_are_shown(self, step_key, temp_db):
        example = schemas.OUTPUT_EXAMPLES.get(step_key) or {}
        missing = sorted(
            (set(schemas.SPECIALIST_CHANNELS[step_key]) | {"notes"})
            - set(example))
        assert not missing, f"{step_key}'s example omits {missing}"


class TestAnExampleTeachesOnlyValuesTheEngineAccepts:
    def test_the_comms_mode_is_one_the_engine_owns(self, temp_db):
        """`mode: 'voice'` stood here and `_clean_comms_channel` folded it to
        duplex without a word, so the example taught a value that only ever
        survived by being replaced."""
        from world.spatial import COMMS_MODES

        for op in schemas.OUTPUT_EXAMPLES["director_spatial"]["comms_ops"]:
            assert op["mode"] in COMMS_MODES
