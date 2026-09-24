"""The prose contract's encoder reads a card written for it.

It used to be sent the causal specialists' chunks verbatim, behind a core
paragraph telling it how to reread them ("a row is one of your events ...
ignore any instruction to return results, status, settled, verdicts,
required_channels ..."). The owner read the sheet from the debug capture
(2026-09-24): "Seems absurdly long", and then: "specific prompts for this
version of the director sound necessary? Otherwise we get a lot of weird
confusing wording if it's still receiving bits of the old contract." The
measured sheet was 32.5K characters for four channels -- half of it the
`entities` chunk, which ships whole whenever any object changes -- and it
told the encoder two opposite things about contacts at once.

So `encoder.*` is its own card: the same rules, restated for one writer of
ordered events, and the big channels split into `<channel>__<part>` parts
the decision model picks. These pin that the card is complete, that it
speaks none of the old contract, that its record shapes cannot drift from
the ones the engine binds against, and that parts ship only when chosen.
"""

from __future__ import annotations

import re

import pytest

import agents.director as director
from agents import director_prose
from agents.director import SPECIALISTS
from llm import decisions, prompts
from language_runtime import raw_card

from tests.test_director_orchestration import (
    _action_interp,
    _fake_agent,
    _make_ctx,
    _steps,
)

LANGUAGES = ("en", "ja")
SEP = prompts.ENCODER_PART_SEP


def _engine_channels():
    return [channel for spec in SPECIALISTS.values() if not spec.get("ext_id")
            for channel in spec["channels"]]


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_channel_has_a_chunk_and_every_part_a_channel_and_a_question(language):
    card = raw_card(language)
    encoder, questions = card["encoder"], card["jev_questions"]
    channels = _engine_channels()
    assert "core" in encoder
    for channel in channels:
        assert channel in encoder, f"{language}: no encoder chunk for {channel}"
    for name in encoder:
        if name == "core":
            continue
        parent = name.split(SEP, 1)[0]
        assert parent in channels, f"{language}: encoder chunk {name} has no channel"
        if SEP in name:
            assert name in questions, f"{language}: part {name} has no Jev question"


#: The several-hands contract's vocabulary. The encoder is every hand at once
#: and returns ordered events, so none of this may reach it.
_OLD_CONTRACT = re.compile(
    r"required_channels|reroute_to|assigned_hands|co_hands|not_mine"
    r"|resolved_event|state_diff|state_assertions|\"results\"|\bverdicts?\b"
    r"|\bledger rows?\b|\brows?\b"
    r"|\bthe (?:body|social|contact|objects|spatial) hand\b|\banother hand\b")


def test_the_card_speaks_none_of_the_old_contract():
    offenders = {}
    for name, text in raw_card("en")["encoder"].items():
        found = sorted(set(m.group(0) for m in _OLD_CONTRACT.finditer(str(text))))
        if found:
            offenders[name] = found
    assert not offenders, offenders


def _shape_fields(text):
    """The field names a chunk's printed shape declares: the first bracketed
    expression after `Shape`, and only the keys inside it."""
    text = str(text)
    at = text.find("Shape")
    if at < 0:
        return set()
    starts = [i for i in (text.find("{", at), text.find("[", at)) if i >= 0]
    if not starts:
        return set()
    start = min(starts)
    depth, end = 0, len(text)
    for i in range(start, len(text)):
        if text[i] in "{[":
            depth += 1
        elif text[i] in "}]":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    return set(re.findall(r"(?<![A-Za-z0-9_'])([a-z_][a-z0-9_]*)(?=\??\s*:)",
                          text[start:end]))


def test_no_record_shape_drifts_from_the_hands():
    """The engine binds the encoder's patches with the hands' own schemas,
    so a native chunk may say a rule differently but may not print a record
    with a field the hand's shape has and it has not."""
    card = raw_card("en")
    lost = {}
    for spec in card["specialists"].values():
        for channel, chunk in spec["chunks"].items():
            hand = _shape_fields(chunk)
            native = set()
            for name, text in card["encoder"].items():
                if name == channel or name.startswith(channel + SEP):
                    native |= _shape_fields(text)
            missing = hand - native
            if missing:
                lost[channel] = sorted(missing)
    assert not lost, lost


def test_every_ops_field_the_card_asks_for_exists_on_a_hand():
    """`project_check.check_prompt_schema_ops`, for the card it never reads:
    an `_ops` field no hand's model has is one validation drops whole."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    from project_check import OPS_NAME, _field_names
    from llm import schemas
    fields = set()
    for spec in SPECIALISTS.values():
        model = schemas.SCHEMA_MAP.get(spec.get("step_key"))
        if model is not None:
            fields |= _field_names(model)
    asked = set()
    for text in raw_card("en")["encoder"].values():
        asked |= set(OPS_NAME.findall(str(text)))
    assert asked and not asked - fields, sorted(asked - fields)


def test_contact_lifetime_is_stated_once_and_as_the_engine_does_it():
    sheet = prompts.unified_specialist_prompt(["contact_ops"])
    assert sheet.count("ages nothing") == 1
    assert "Silence does not end contact" not in sheet
    assert "unmentioned as ended" not in sheet


def test_a_part_ships_only_when_chosen():
    transit = "A MOVING ROOM IS MOVED BY ITS ENTITY'S STATE"
    emits = "AN EMISSION IS A STATE; A NOISE IS AN EVENT"
    bare = prompts.unified_specialist_prompt(["entities"], parts=[])
    chosen = prompts.unified_specialist_prompt(["entities"],
                                               parts=["entities__transit"])
    every = prompts.unified_specialist_prompt(["entities"])
    assert transit not in bare and emits not in bare
    assert transit in chosen and emits not in chosen
    assert transit in every and emits in every
    # A part never ships without its channel.
    assert transit not in prompts.unified_specialist_prompt(
        ["poses"], parts=["entities__transit"])
    # And the base names its parts, so a missing one can be asked for.
    assert "entities__transit" in bare


def test_the_owners_sheet_is_half_what_it_was():
    """The sheet the owner pasted: obligations, entities, sensory_events and
    poses, 32,543 characters under the causal chunks."""
    sheet = prompts.unified_specialist_prompt(
        ["obligations", "entities", "sensory_events", "poses"], parts=[])
    assert len(sheet) < 32543 * 0.6, len(sheet)


def _scores(scores):
    def answer(state, questions):
        return {key: {"type": "noul", "noul": scores.get(key, 0.0)}
                for key in questions}
    return answer


def test_the_decision_model_picks_parts_only_with_their_channel(
        temp_db, monkeypatch):
    temp_db.set_setting("director_contract", "prose")
    monkeypatch.setattr(decisions, "OVERRIDE", _scores({
        "entities": 0.9, "entities__transit": 0.9, "entities__emits": 0.1,
        "contact_ops": 0.1, "contact_ops__interior": 0.9}))
    ctx = _make_ctx(temp_db, interp=_action_interp())
    selected, record = director_prose.select_channels(
        ctx, "resolve", "The lift doors shut and it drops.", {})
    assert "entities" in selected and "contact_ops" not in selected
    assert record["parts"] == ["entities__transit"]


def test_a_failed_decision_model_ships_every_part(temp_db, monkeypatch):
    temp_db.set_setting("director_contract", "prose")

    def broken(state, questions):
        raise RuntimeError("decision model down")

    monkeypatch.setattr(decisions, "OVERRIDE", broken)
    ctx = _make_ctx(temp_db, interp=_action_interp())
    selected, record = director_prose.select_channels(
        ctx, "resolve", "The lift doors shut and it drops.", {})
    assert set(record["parts"]) == set(director_prose.parts_of(selected))
    assert "entities__transit" in record["parts"]


def test_a_part_the_encoder_asks_for_buys_the_widened_call(temp_db, monkeypatch):
    temp_db.set_setting("director_contract", "prose")
    monkeypatch.setattr(decisions, "OVERRIDE", _scores({"entities": 0.9}))
    first = {"events": [{"source_entity_id": "character:1",
                         "event": "The lift sets off.", "item_names": ["lift"],
                         "transforms": []}],
             "missing_tools": ["entities__transit"]}
    second = {"events": [{"source_entity_id": "character:1",
                          "event": "The lift sets off.", "item_names": ["lift"],
                          "transforms": []}], "missing_tools": []}
    answers = iter([first, second])
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_prose": {"prose": "The lift sets off."},
        "director_specialist": lambda payload: next(answers),
    }))
    out = director.director_resolve(_make_ctx(temp_db, interp=_action_interp()),
                                    nonce=0)
    assert _steps(calls) == ["director_prose", "director_specialist",
                             "director_specialist"]
    transit = "A MOVING ROOM IS MOVED BY ITS ENTITY'S STATE"
    assert transit not in calls[1]["system"]
    assert transit in calls[2]["system"]
    assert "entities__transit" in calls[1]["payload"]["requestable_tools"]
    assert "entities__transit" in calls[2]["payload"]["granted_tools"]
    encoder = out["orchestration"]["prose_contract"]["encoder"]
    assert encoder["missing_tools"] == ["entities__transit"]
    assert "entities__transit" in encoder["parts"]
