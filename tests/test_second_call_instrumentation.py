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

from llm import llm_quality
from core import pipeline_context
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
    """A reissued line is recorded and does not buy a second model call.

    This test used to assert the opposite -- that the retry fired, and that a
    warning named its duration -- back when the fire rate was the thing worth
    measuring. The measurement is in: 36.3s, 58.0s and 155.6s per retry, kept
    unchanged 48 times, and on the slowest beat the "corrected" answer restated
    the same propositions in different words. So the retry is gone and the
    warning is the whole record.
    """
    import agents.character as character_module
    from story.character_schema import default_character_data
    from core.pipeline_context import ChatData, PipelineContext, TurnData

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

    # ONE call. A reissued line is weak output, not broken output, and a redo
    # on anything short of broken is a nuisance -- so the repetition is
    # recorded and the beat stands. What this used to assert (a second full
    # character call, and a warning naming its duration) is the cost that was
    # removed; the warning it left behind is the record.
    assert len(calls) == 1, "weak output must not buy a second model call"
    assert not [w for w in ctx.warnings if "decision review retry" in w]
    assert any("repeat_correction" in w and "the beat stands" in w
               for w in ctx.warnings)


# --- The deterministic prune, which does not fail and does not speak --------
#
# Every rung above re-issues a model call, and the ladder narrates each one.
# The prune inside `validate_llm_output_strict` costs nothing and therefore
# runs on the SUCCESS path: a malformed `state_diff` channel (or a whole
# specialist channel) is dropped, the report comes back `valid=True`, and the
# beat commits without it. That is the right trade -- absent is "no change
# asserted" and the reconcile seam catches the drift next beat -- but it is a
# change to committed world state, and it was made silently.

_DIFF_BAD = json.dumps({
    "resolved_event": "The door swings wide.",
    "summary": "the door opens",
    "state_diff": {"weather": 12345},
})

_SPECIALIST_BAD = json.dumps({"attire": 12345, "poses": {}})


def test_a_dropped_state_diff_channel_says_so(monkeypatch, sink):
    _script(monkeypatch, [_DIFF_BAD])
    out = llm_quality.complete_validated_json(
        role="director", step_key="director_resolve",
        system="s", payload={}, repair_attempts=1)
    # The beat commits: prose, summary and every well-formed channel stand.
    assert out["resolved_event"] == "The door swings wide."
    assert "weather" not in (out.get("state_diff") or {})
    assert any("state_diff.weather" in note for note in sink), (
        "a channel was dropped from a committed beat with nothing said: "
        f"{sink}")


def test_a_dropped_specialist_channel_says_so(monkeypatch, sink):
    _script(monkeypatch, [_SPECIALIST_BAD])
    out = llm_quality.complete_validated_json(
        role="director_body", step_key="director_body",
        system="s", payload={}, repair_attempts=1)
    assert not out.get("attire")
    assert any("attire" in note for note in sink), (
        f"a specialist channel was dropped with nothing said: {sink}")


# --- LLM-11: the drops that had no way to say so ---------------------------


def test_every_major_prune_in_schemas_says_what_it_dropped(sink):
    """`llm/schemas.py` subtracts in about a dozen places and every one was
    silent. Each is individually argued and mostly right -- a dropped
    alternative beats a crashed beat -- but the third option was always
    available and only `_uncross_concealed_speech` took it: keep the beat AND
    say what went. A list truncated at 64 and a well-formed list of 64 were
    indistinguishable in the stored variant.
    """
    from llm.schemas import FREE_STRING_LIST_LIMIT, validate_llm_output_strict

    cases = {
        "the free-string runaway ceiling": (
            "character",
            {"response_candidates": [
                {"response": "wait", "serves": ["x"] * 9}]},
            "serves"),
        "a line with no quote": (
            "director_resolve",
            {"resolved_event": "a", "summary": "a",
             "dialogue_log": [{"speaker": "Mara", "exact_quote": ""}]},
            "dialogue_log"),
        "a sequence entry that is neither object nor prose": (
            "character",
            {"sequence": [{"type": "action", "observable": "stands"}, 7]},
            "sequence"),
        "a scalar where the beat's clock belongs": (
            "director_resolve",
            {"resolved_event": "a", "summary": "a",
             "state_diff": {"time": "a minute passes"}},
            "state_diff.time"),
        "a memory dispute with no locator": (
            "character",
            {"memory_disputes": [{"now_reads": "he lied"}]},
            "memory_disputes"),
        "the whole deliberation": (
            "character",
            {"response_candidates": {"unrelated": 3}},
            "response_candidates"),
    }
    for label, (step_key, raw, expected) in cases.items():
        del sink[:]
        validate_llm_output_strict(step_key, raw)
        assert any(expected in note for note in sink), (
            f"{label}: nothing said about {expected} ({sink})")

    # The runaway ceiling itself: the shape a stuck sampler produces, which
    # is the one prune whose whole point is that the tail is not content.
    del sink[:]
    validate_llm_output_strict(
        "character",
        {"considered_responses":
            [f"option {n}" for n in range(FREE_STRING_LIST_LIMIT + 5)]})
    assert any("runaway ceiling" in note for note in sink), sink
