"""Every invisible second model call now says it happened, and what it cost.

The repair ladder (llm_quality.complete_validated_json: truncation re-ask,
temperature-0 repair, per-candidate fallback) and the character stage's
decision-review retry each re-issue a full provider call, and none of them
left a stored trace when they SUCCEEDED -- a retry that came back clean was
indistinguishable from a first draft. The 2026-08-11 character-agent audit
could therefore bound the retry rate only from its failures: 14 "repetition
retained" notes in 401 recent-era calls, a floor of >=3.5% with the true
rate unknowable, while the live benchmark's 1.25-1.50 provider calls/turn
against 1.01 stored results/turn left a suspected ~8-15s/turn unattributed.
Its first recommendation was one warning line per fired retry/repair, then
re-measure; any bounded-delta retry design waits on that number.

The channel is pipeline_context.current_warning_sink -- set by
agents.runtime.compute_step beside current_step_key, so a note raised deep
inside llm_quality is attributed to the running step and rides the stored
variant's _engine_notes like every other repair diagnostic. Outside a
pipeline step (importers, generators, jobs) the sink is unset and noting is
a no-op.
"""

from __future__ import annotations

import json
import time

import llm_quality
import pipeline_context
import pytest
from agents.common import _agent_json


class _ScriptedLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, role, system, user, **kwargs):
        self.calls.append({"role": role, "system": system,
                           "user": user, **kwargs})
        if not self.responses:
            raise AssertionError("chat_complete called more times than scripted")
        return self.responses.pop(0)


def _script(monkeypatch, responses, candidates=1):
    llm = _ScriptedLLM(responses)
    monkeypatch.setattr(llm_quality, "chat_complete", llm)
    monkeypatch.setattr(
        llm_quality, "role_candidate_count", lambda role: candidates)
    return llm


@pytest.fixture
def sink():
    notes = []
    token = pipeline_context.current_warning_sink.set(notes.append)
    try:
        yield notes
    finally:
        pipeline_context.current_warning_sink.reset(token)


_BAD = json.dumps({
    "sequence": [], "interaction": {},
    "mind_model_updates": [{  # missing about_entity -> repair fires
        "kind": "goal", "claim": "wants the key", "confidence": 0.9}],
})
_GOOD = json.dumps({
    "sequence": [], "interaction": {},
    "mind_model_updates": [{
        "about_entity": "player", "kind": "goal",
        "claim": "wants the key", "confidence": 0.9}],
})


def test_a_successful_repair_is_noted_with_its_cost(monkeypatch, sink):
    _script(monkeypatch, [_BAD, _GOOD])

    out = _agent_json("character_mid", "character", "sys", {})

    assert out["mind_model_updates"][0]["about_entity"] == "player"
    repair_notes = [n for n in sink if "temperature-0 repair" in n]
    assert len(repair_notes) == 1
    # Which path, and what it cost: the note names the failure and carries a
    # duration -- the number the bounded-delta retry decision waits on.
    assert "validation failed" in repair_notes[0]
    assert "s)" in repair_notes[0]


def test_a_fallback_candidate_is_noted(monkeypatch, sink):
    # Primary invalid, repair invalid, fallback candidate 1 succeeds.
    _script(monkeypatch, [_BAD, _BAD, _GOOD], candidates=2)

    out = _agent_json("character_mid", "character", "sys", {})

    assert out["mind_model_updates"][0]["about_entity"] == "player"
    assert any("fallback candidate 1" in n for n in sink)


def test_a_clean_first_draft_notes_nothing(monkeypatch, sink):
    _script(monkeypatch, [_GOOD])
    _agent_json("character_mid", "character", "sys", {})
    assert sink == []


def test_noting_outside_a_pipeline_step_is_a_noop(monkeypatch):
    """Importers/generators repair without a sink; nothing may raise."""
    assert pipeline_context.current_warning_sink.get() is None
    pipeline_context.note_step_warning("nobody is listening")
    _script(monkeypatch, [_BAD, _GOOD])
    out = _agent_json("character_mid", "character", "sys", {})
    assert out["mind_model_updates"][0]["about_entity"] == "player"


# ---- the character stage's own decision-review retry ----


def test_decision_review_retry_is_warned_even_when_it_succeeds(
        temp_db, monkeypatch):
    """The asymmetry this closes: a warning used to land only when the retry
    FAILED a second time, which is why the fire rate was unknowable. Now the
    retry itself is one warning line, with the corrections that fired and the
    second call's duration."""
    import agents.character as character_module
    from character_schema import default_character_data
    from pipeline_context import ChatData, PipelineContext, TurnData

    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()))
    sheet = default_character_data("Sir Julian")
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Sir Julian", json.dumps(sheet), "{}", time.time(),
         sheet["identity"]["uid"]))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"))
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    temp_db.wset(chat_id, "scene", {
        "location": "Drawing Room", "time": "night",
        "rooms": {"drawing_room": {"name": "Drawing Room", "adjacent": []}},
        "positions": {"Sir Julian": "drawing_room"},
        "entities": {}, "attire": {}, "overlays": {},
    })
    # A committed prior turn where he already said the line the draft will
    # reissue -- the deterministic repetition screen's trigger.
    tid = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 0, "...", time.time()))
    sid = temp_db.qi("INSERT INTO steps(turn_id,key,label,ord) VALUES(?,?,?,?)",
                     (tid, "director_resolve", "", 0))
    temp_db.qi(
        "INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
        (sid, json.dumps({"dialogue_log": [
            {"speaker": "Sir Julian",
             "exact_quote": "The night is calm and the wine is good."}]}),
         time.time()))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "a toast", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                      player_input="a toast", created=time.time()),
        cast=cast, input="a toast")
    ctx.director_interpret = {"flow": {"reactors": [char_id],
                                       "tom_triggers": []}}

    calls = []

    def fake_agent_json(role, step_key, system, payload, **kwargs):
        calls.append(payload)
        return {"sequence": [
            {"type": "speech",
             "text": "The night is calm and the wine is good."}]}

    monkeypatch.setattr(character_module, "_agent_json", fake_agent_json)
    character_module.character_step(ctx, char_id, nonce=0)

    assert len(calls) == 2, "the repetition screen should have retried"
    assert "repeat_correction" in calls[1]
    retry_notes = [w for w in ctx.warnings if "decision review retry" in w]
    assert len(retry_notes) == 1
    assert "repeat_correction" in retry_notes[0]
    assert "s)" in retry_notes[0]
    # The old failure-only note still fires when the retry repeats again --
    # the two together are the numerator and the denominator.
    assert any("repetition retained" in w for w in ctx.warnings)
