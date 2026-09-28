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

from llm import llm_quality
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

def test_well_formed_director_prose_passes_on_first_call(monkeypatch):
    """`director_resolve` until 2026-09-27; the Director's one call is
    `director_prose` since."""
    llm = _script(monkeypatch, [json.dumps({
        "prose": "The door creaks open.", "places": []})])

    out = _agent_json("director", "director_prose", "sys", {"x": 1})

    assert out["prose"] == "The door creaks open."
    assert out["places"] == []
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

def test_empty_narrator_prose_costs_no_second_call(monkeypatch):
    """The inverse of every other case in this file, deliberately. Narration
    is the one stage where a content judgment may not cost a call: the repair
    this used to trigger is what turned a model's empty answer into a dead
    turn once the retries hit the provider (chat 95 t18). One call, taken as
    it came."""
    llm = _script(monkeypatch, [
        json.dumps({"prose": "", "new_specifics": []}),
        json.dumps({"prose": "The rain stops.", "new_specifics": []}),
    ])

    out = _agent_json("narrator", "narrator", "sys", {})

    assert out["prose"] == ""
    assert len(llm.calls) == 1


def test_an_empty_director_answer_reasks_the_original_before_repair(monkeypatch):
    """The causal Director's `{}` until 2026-09-27; the prose Director's
    since, whose schema requires the prose."""
    payload = {"event_inputs": [{
        "entity_id": "persona:1", "authority_mode": "world_author",
        "events": [{"event_id": "e1", "raw_text": "I open the door"}],
    }], "identity_index": {"persona:1": "Corin"}}
    good = {"prose": "Corin opens the door.", "places": []}
    llm = _script(monkeypatch, ["{}", json.dumps(good)])

    out = _agent_json("director", "director_prose", "original", payload)

    assert out["prose"] == "Corin opens the door."
    assert len(llm.calls) == 2
    assert llm.calls[1]["system"] == "original"
    assert json.loads(llm.calls[1]["user"]) == payload

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
    """Driven through the prose Director (the causal interpret's semantic
    check until 2026-09-27): an empty prose, then a wordless one, both fail
    its schema. The cheap field-patch rung is stubbed so the ladder under
    test is the repair and then the fallback candidate. Narrator can no
    longer stand in: it fails no content check."""
    monkeypatch.setattr(llm_quality, "_targeted_field_patch",
                        lambda *a, **kw: None)
    llm = _script(monkeypatch, [
        json.dumps({"prose": "", "places": []}),        # primary: invalid
        json.dumps({"prose": ",", "places": []}),       # repair: still invalid
        json.dumps({"prose": "Corin opens the door.",   # candidate fallback
                    "places": []}),
    ], candidates=2)

    out = _agent_json("director", "director_prose", "sys", {"x": 1})

    assert out["prose"] == "Corin opens the door."
    assert len(llm.calls) == 3
    assert llm.calls[2]["candidate_offset"] == 1

def test_exhausted_validation_raises_step_error(monkeypatch):
    monkeypatch.setattr(llm_quality, "_targeted_field_patch",
                        lambda *a, **kw: None)
    _script(monkeypatch, [
        json.dumps({"prose": "", "places": []}),
        json.dumps({"prose": ",", "places": []}),
    ], candidates=1)

    # This RuntimeError propagates out of the stage function, which is
    # exactly what makes the step fail as a normal rerunnable step
    # instead of committing a malformed dict.
    with pytest.raises(RuntimeError,
                       match="director_prose failed JSON validation"):
        _agent_json("director", "director_prose", "sys", {"x": 1})

# ---- source-level wiring guard ----

_AGENTS_DIR = Path(__file__).resolve().parents[1] / "agents"

_STAGE_STEP_KEYS = {
    # The opening stays on the Director's own module; every later beat's
    # calls are the prose Director's (2026-09-27): its account and the
    # encoder, the optional repair pass and the room author.
    "director.py": ["director_establish"],
    "director_prose.py": ["director_prose", "director_specialist"],
    "director_repair.py": ["director_repair"],
    "director_rooms.py": ["director_rooms"],
    # The bare contract is the only one (2026-09-27): one call a beat.
    "character.py": ["character_bare"],
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
        # The step-key argument names the key -- as a literal, or as one
        # branch of a choice between literal step keys.
        assert re.search(
            rf'_agent_json\(\s*[^,]+,\s*(?:"[a-z_]+"\s+if\s+[^,]+?\s+else\s+)?"{key}"'
            rf'|_agent_json\(\s*[^,]+,\s*"{key}"\s+if\s', src), (
            f"{filename} must route step '{key}' through _agent_json")


def test_narration_filed_under_the_wrong_key_is_read_not_refused(monkeypatch):
    """The alias `llm/schemas.py` asked for and never got. A model that puts
    its page in `text` used to be refused for an empty `prose`; with nothing
    left to refuse it, the page has to be READ or the beat renders blank."""
    from agents import narration
    _script(monkeypatch, [
        json.dumps({"prose": "", "text": "The rain stops.",
                    "new_specifics": []}),
    ])
    out, _warnings, _fidelity = narration._generate_narration(
        {}, "", "", [], fidelity_facts={})
    assert out["prose"] == "The rain stops."


def test_prose_the_model_sent_reaches_the_page_unedited(monkeypatch):
    """No deterministic rewrite of accepted narration. Every reading that
    used to edit it -- player echo, raw-input echo, within-view dedupe, the
    repeated-quote cap -- now only reports, so what the reader gets is what
    the model wrote."""
    from agents import narration
    warnings = []
    prose = ('She said "hello" and then she said "hello" and then she said '
             '"hello" and then she said "hello" again.')
    kept = narration._report_prose_guards(
        prose, "", ['hello'], "I said hello", warnings)
    assert kept == prose


def test_an_empty_object_from_any_step_reasks_the_original_before_repair(monkeypatch):
    """The stall is a provider trait, not a causal-Director one. Measured on
    the owner's database 2026-09-14: eight bare `{}` replies across five roles
    since 09-08, none of them the causal Director; on chat 123 turn 9 the
    contact and objects hands each stalled, were handed their `{}` to repair,
    and stalled again -- two fruitless calls and a lost door state.

    Driven through the encoder since the hands went (2026-09-27), whose every
    field defaults -- so a `{}` validates, and only the stall rule stands
    between it and a beat that encodes nothing."""
    payload = {"prose": "Corin opens the door.", "event_inputs": []}
    good = {"events": [{"source_entity_id": "persona:1",
                        "event": "Corin opens the door."}],
            "missing_tools": [], "missing_referents": [], "notes": []}
    llm = _script(monkeypatch, ["{}", json.dumps(good)])

    out = _agent_json("encoder", "director_specialist", "original", payload)

    assert out["events"][0]["event"] == "Corin opens the door."
    assert len(llm.calls) == 2
    assert llm.calls[1]["system"] == "original"
    assert json.loads(llm.calls[1]["user"]) == payload


def test_an_empty_narrator_object_is_a_stall_not_a_page(monkeypatch):
    """Every narrator field defaults, so `{}` validated and committed an
    empty page (scratch play 2026-09-14, chat 3 turn 0). It now fails
    validation and the original request is re-asked before any repair."""
    llm = _script(monkeypatch, ["{}", json.dumps({"prose": "The fire burns."})])
    out = _agent_json("narrator", "narrator", "sys", {"beat": 1})
    assert out["prose"] == "The fire burns."
    assert len(llm.calls) == 2 and llm.calls[1]["system"] == "sys"
