"""Every state-mutating stage's primary LLM call must go through the
strict validated-JSON path (agents.common._agent_json ->
llm_quality.complete_validated_json): schema+semantic validation, one
temperature-0 repair, per-candidate fallback, and a RuntimeError -- never
a silently-committed malformed dict -- when nothing validates.

These tests exercise _agent_json itself (the exact seam every stage
calls) with a scripted chat_complete, plus a source-level wiring guard
so no stage can quietly regress to jparse/bare chat_complete parsing.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import llm_quality
from agents.common import _agent_json

class _ScriptedLLM:
    """Stands in for llm_quality.chat_complete; returns queued raw
    responses in order and records every call's role/kwargs."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, role, system, user, **kwargs):
        self.calls.append({"role": role, "system": system,
                           "user": user, **kwargs})
        if not self.responses:
            raise AssertionError(
                "chat_complete called more times than scripted"
            )
        return self.responses.pop(0)

def _script(monkeypatch, responses, candidates=1):
    llm = _ScriptedLLM(responses)
    monkeypatch.setattr(llm_quality, "chat_complete", llm)
    monkeypatch.setattr(
        llm_quality, "role_candidate_count", lambda role: candidates)
    return llm

def test_well_formed_director_resolve_passes_on_first_call(monkeypatch):
    llm = _script(monkeypatch, [json.dumps({
        "resolved_event": "The door creaks open.",
        "summary": "door opened",
        "state_diff": {},
    })])

    out = _agent_json("director", "director_resolve", "sys", {"x": 1})

    assert out["resolved_event"] == "The door creaks open."
    assert out["summary"] == "door opened"
    assert isinstance(out["state_diff"], dict)
    # Success path: exactly one call, no repair invoked.
    assert len(llm.calls) == 1

def test_malformed_character_mind_models_trigger_repair(monkeypatch):
    bad = {
        "sequence": [], "interaction": {},
        "mind_model_updates": [{
            # missing the required 'about_entity' -> a structural malformation
            # that still triggers repair. (An out-of-[0,1] confidence is now
            # deliberately CLAMPED rather than repaired -- see AUDIT #6 and
            # tests/test_coerce_hardening.py -- so it no longer forces a repair.)
            "kind": "goal", "claim": "wants the key", "confidence": 0.9,
        }],
    }
    good = dict(bad)
    good["mind_model_updates"] = [{
        "about_entity": "player", "kind": "goal",
        "claim": "wants the key", "confidence": 0.9,
    }]
    llm = _script(monkeypatch, [json.dumps(bad), json.dumps(good)])

    out = _agent_json("character_mid", "character", "sys", {})

    # The raw invalid dict never flows through; the repaired one does.
    assert out["mind_model_updates"][0]["confidence"] == 0.9
    assert len(llm.calls) == 2
    # Repair pass is deterministic.
    assert llm.calls[1]["temperature"] == 0.0

def test_malformed_background_react_triggers_repair(monkeypatch):
    llm = _script(monkeypatch, [
        # dialogue_log_entry must be an object, not prose.
        json.dumps({"reacts": True, "dialogue_log_entry": "he flinches"}),
        json.dumps({"reacts": True, "action": "",
                    "dialogue_log_entry": {"speaker": "Barkeep",
                                           "exact_quote": "Oi!"}}),
    ])

    out = _agent_json("character_bg", "background_react", "sys", {})

    assert out["reacts"] is True
    assert out["dialogue_log_entry"]["exact_quote"] == "Oi!"
    assert len(llm.calls) == 2

def test_empty_narrator_prose_triggers_repair(monkeypatch):
    llm = _script(monkeypatch, [
        json.dumps({"prose": "", "new_specifics": []}),  # semantic failure
        json.dumps({"prose": "The rain stops.", "new_specifics": []}),
    ])

    out = _agent_json("narrator", "narrator", "sys", {})

    assert out["prose"] == "The rain stops."
    assert len(llm.calls) == 2

def test_director_interpret_semantic_check_uses_source_payload(monkeypatch):
    payload = {"player_raw_input": "I open the door"}
    llm = _script(monkeypatch, [
        # Valid JSON/schema but empty sequence despite nonempty input.
        json.dumps({"sequence": [], "flow": {}}),
        json.dumps({"sequence": [{"type": "action",
                                  "attempt": "open the door"}],
                    "flow": {}}),
    ])

    out = _agent_json("director", "director_interpret", "sys", payload)

    assert out["sequence"][0]["attempt"] == "open the door"
    assert len(llm.calls) == 2

def test_unparseable_output_triggers_repair(monkeypatch):
    llm = _script(monkeypatch, [
        "Sure! Here is the reaction you asked for.",
        json.dumps({"reacts": False, "dialogue_log_entry": None,
                    "action": ""}),
    ])

    out = _agent_json("character_bg", "background_react", "sys", {})

    assert out["reacts"] is False
    assert len(llm.calls) == 2

def test_failed_repair_falls_back_to_next_candidate(monkeypatch):
    llm = _script(monkeypatch, [
        json.dumps({"prose": ""}),                    # primary: invalid
        json.dumps({"prose": ""}),                    # repair: still invalid
        json.dumps({"prose": "Dust settles."}),       # candidate fallback
    ], candidates=2)

    out = _agent_json("narrator", "narrator", "sys", {})

    assert out["prose"] == "Dust settles."
    assert len(llm.calls) == 3
    assert llm.calls[2]["candidate_offset"] == 1

def test_exhausted_validation_raises_step_error(monkeypatch):
    _script(monkeypatch, [
        json.dumps({"prose": ""}),
        json.dumps({"prose": ""}),
    ], candidates=1)

    # This RuntimeError propagates out of the stage function, which is
    # exactly what makes the step fail as a normal rerunnable step
    # instead of committing a malformed dict.
    with pytest.raises(RuntimeError, match="narrator failed JSON validation"):
        _agent_json("narrator", "narrator", "sys", {})

# ---- source-level wiring guard ----

_AGENTS_DIR = Path(__file__).resolve().parents[1] / "agents"

_STAGE_STEP_KEYS = {
    "director.py": ["director_establish", "director_interpret",
                    "director_resolve"],
    "character.py": ["character"],
    "background.py": ["background_react"],
    "narration.py": ["narrator"],
}

@pytest.mark.parametrize("filename,step_keys", sorted(_STAGE_STEP_KEYS.items()))
def test_stage_modules_stay_on_strict_path(filename, step_keys):
    src = (_AGENTS_DIR / filename).read_text(encoding="utf-8")

    # No permissive parsing of a primary stage output.
    assert "jparse(" not in src, (
        f"{filename} must not parse stage output with jparse")
    assert not re.search(r"\bchat_complete\(", src), (
        f"{filename} must not call chat_complete directly")

    for key in step_keys:
        assert re.search(
            rf'_agent_json\(\s*[^,]+,\s*"{key}"', src), (
            f"{filename} must route step '{key}' through _agent_json")
