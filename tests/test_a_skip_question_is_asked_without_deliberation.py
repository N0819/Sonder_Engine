"""THE SKIP QUESTION IS ASKED WITHOUT DELIBERATION (2026-10-22).

The owner, on a skip costing too much: "50 cents per skip? thats extreme".
Measured the same day, the keeper's real skip question on glm-5.2 at the
role's own reasoning effort billed 12,117 output tokens (45 s, about 8.5
cents); with reasoning off, 2,153 (10 s, about 1.5 cents), the answer
equally in character. A day's schedule is a listing, not a deliberation, so
the skip question asks at `SKIP_QUESTION_REASONING`, and the validated-JSON
path carries a per-call effort to every attempt it makes.
"""

from __future__ import annotations

import agents.skip_stage as skip_stage
from agents import common
from llm import llm_quality


def test_the_skip_question_is_asked_at_its_own_effort():
    assert skip_stage.SKIP_QUESTION_REASONING == "off"
    import inspect
    source = inspect.getsource(skip_stage)
    at = source.index('"character_skip", skip_card(')
    assert "reasoning_effort=SKIP_QUESTION_REASONING" in source[at:at + 400]


def test_the_validated_json_path_carries_the_effort_to_the_model(monkeypatch):
    seen = []

    def fake_chat_complete(role, system, user, **kwargs):
        seen.append(kwargs.get("reasoning_effort"))
        return '{"ok": true}'

    monkeypatch.setattr(llm_quality, "chat_complete", fake_chat_complete)
    monkeypatch.setattr(llm_quality, "validate_llm_output_strict",
                        lambda key, data, *a, **k: data, raising=False)
    try:
        common._agent_json("utility", "skip_memory_probe", "system", {"a": 1},
                           reasoning_effort="off")
    except Exception:
        pass          # validation of a probe key may refuse; the call was made
    assert seen and seen[0] == "off"


def test_no_effort_leaves_the_role_in_charge(monkeypatch):
    seen = []

    def fake_chat_complete(role, system, user, **kwargs):
        seen.append(kwargs.get("reasoning_effort", "absent"))
        return '{"ok": true}'

    monkeypatch.setattr(llm_quality, "chat_complete", fake_chat_complete)
    try:
        common._agent_json("utility", "skip_memory_probe", "system", {"a": 1})
    except Exception:
        pass
    assert seen and seen[0] is None
