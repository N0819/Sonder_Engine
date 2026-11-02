"""A JSON mend that validates only by losing what the model wrote says so.

`_mended` took the FIRST mend that validated. The lenient schema ignores a
key it has no field for, so a closer in the wrong place could move a member
into another object and still validate -- measured over every single bracket
slip of all 16 `OUTPUT_EXAMPLES`: 427 mend back, 94 do not, and 10 mend into
a DIFFERENT object that validates (review 2026-11-01, llm_schemas_prompts
F3). The worked case is here: a `scene_life` answer missing the `}` that
closes `entries[0].speech` is mended by closing the object before its next
sibling, which puts `action` inside `speech`, where nothing reads it -- and
the only warning said the JSON "was mended locally".

A lossless mend is now preferred over a lossy one; and when every mend that
validates loses something, the one that loses least is taken and the lost
paths are said aloud on the step.
"""
from __future__ import annotations

import json

import pytest

from core.pipeline_context import current_warning_sink
from llm import json_mend, llm_quality
from llm.schemas import OUTPUT_EXAMPLES

SCENE_LIFE = json.dumps(OUTPUT_EXAMPLES["scene_life"], ensure_ascii=False)
#: The audit's case: the `}` closing `entries[0].speech`, deleted.
MISSING_CLOSER = SCENE_LIFE[:189] + SCENE_LIFE[190:]


@pytest.fixture
def said():
    seen = []
    token = current_warning_sink.set(seen.append)
    yield seen
    current_warning_sink.reset(token)


def test_the_audit_case_names_the_member_it_lost():
    found = llm_quality._mended("scene_life", MISSING_CLOSER, {})
    assert found is not None and found[1].valid
    assert any("entries.0.speech.action" in w for w in found[1].warnings), \
        found[1].warnings


def test_the_ladder_says_it_on_the_step(monkeypatch, said):
    monkeypatch.setattr(llm_quality, "chat_complete",
                        lambda *a, **k: MISSING_CLOSER)
    monkeypatch.setattr(llm_quality, "role_candidate_count", lambda role: 1)
    llm_quality.complete_validated_json(
        role="background", step_key="scene_life", system="S", payload={"x": 1})
    assert any("entries.0.speech.action" in w for w in said), said


def test_a_lossless_mend_is_preferred_to_a_lossy_one(monkeypatch):
    lossless = dict(OUTPUT_EXAMPLES["scene_life"])
    lossy = json.loads(json.dumps(lossless))
    lossy["entries"][0]["speech"] = dict(
        lossy["entries"][0]["speech"] if isinstance(lossy["entries"][0].get("speech"), dict)
        else {}, action=lossy["entries"][0].get("action", "x"))
    lossy["entries"][0].pop("action", None)

    def candidates(text):
        yield lossy, ["closed an object left open before its next sibling"]
        yield lossless, ["swapped two closers"]

    monkeypatch.setattr(json_mend, "mend_candidates", candidates)
    found = llm_quality._mended("scene_life", "{broken", {})
    assert found[2] == ["swapped two closers"]
    assert not any("dropping" in w for w in found[1].warnings)


def test_a_mend_that_loses_nothing_is_taken_as_before():
    whole = OUTPUT_EXAMPLES["scene_life"]
    text = json.dumps(whole, ensure_ascii=False)
    broken = text.replace("]", "]]", 1)
    found = llm_quality._mended("scene_life", broken, {})
    assert found is not None and found[1].valid and found[0] == whole
    assert not any("dropping" in w for w in found[1].warnings)
