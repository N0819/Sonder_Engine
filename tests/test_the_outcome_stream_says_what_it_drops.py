"""The outcome stream says what it drops.

`_outcome_event_stream` carries three element kinds -- a line bound to its
dialogue row, a communication with a surface, an act with a surface -- and
skipped every other kind with no word anywhere (audit agents_perception F8,
2026-11-01). The engine itself writes two more into a sequence: a `ponder`
(private cognition, never perceived) and an `event` -- a player's world
assertion (`common_sequence`), or, on a rerun of an archived beat, the causal
projection of a world row (`director_evidence`: `timeline element types:
['event', 'action']` -> `stream: [('action', ...)]`). Both are refused by
design and RECORDED where they went; a kind nothing writes is a warning on the
turn, since a delivery that vanishes silently is indistinguishable from one
correctly withheld.
"""

import json
import time

from story.character_schema import default_persona_data
from core.pipeline_context import (ChatData, PipelineContext, TurnData,
                                   current_decision_sink)


def _ctx(temp_db, sequence):
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        ("Nera", json.dumps(default_persona_data("Nera")), "{}"))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Stream", "", time.time(), persona_id))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Stream", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="",
                      created=time.time()),
        cast=[], input="")
    return ctx, {"sequence": sequence}


def _stream(ctx, interp):
    from agents.perception import _outcome_event_stream
    scene = {"rooms": {"r": {"name": "Quay"}}, "positions": {"Nera": "r"}}
    decisions = []
    token = current_decision_sink.set(
        lambda *row: decisions.append(row))
    try:
        stream = _outcome_event_stream(ctx, scene, interp, {}, "Nera", [], [])
    finally:
        current_decision_sink.reset(token)
    return stream, decisions


BOARDS = {"type": "action", "attempt": "boards the boat",
          "observable": "boards the boat", "visibility": "overt",
          "event_id": "turn:1:player:0:action"}


def test_a_world_event_is_refused_and_recorded(temp_db):
    ctx, interp = _ctx(temp_db, [
        {"type": "event", "description": "The tide turns in the harbour.",
         "event_id": "turn:1:world:0"}, BOARDS])
    stream, decisions = _stream(ctx, interp)
    assert [e["kind"] for e in stream] == ["action"]
    refused = [d for d in decisions if d[0] == "outcome_stream"]
    assert refused and refused[0][2] == "refused", decisions
    assert "tide turns" in refused[0][3]
    # a world row is the engine's own kind: recorded, not alarmed
    assert not [w for w in ctx.warnings if "unknown type" in w], ctx.warnings


def test_a_kind_nothing_writes_is_a_warning(temp_db):
    ctx, interp = _ctx(temp_db, [
        {"type": "gesture", "description": "waves at the ferryman"}, BOARDS])
    stream, _decisions = _stream(ctx, interp)
    assert [e["kind"] for e in stream] == ["action"]
    said = [w for w in ctx.warnings if "unknown type" in w]
    assert said and "waves at the ferryman" in said[0], ctx.warnings


def test_the_kinds_it_carries_record_nothing(temp_db):
    ctx, interp = _ctx(temp_db, [BOARDS])
    stream, decisions = _stream(ctx, interp)
    assert [e["kind"] for e in stream] == ["action"]
    assert not [d for d in decisions if d[0] == "outcome_stream"], decisions
    assert not ctx.warnings, ctx.warnings
