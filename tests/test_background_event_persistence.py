"""Step-1 regression: the deterministic background_react backstop line is
folded into the committed event record (commit.prepare_memory_commit) and
counted as a real dialogue turn (commit.track_background_presences), instead
of being invisible to bookkeeping -- while never mutating the already-
persisted director_resolve variant (which would desync it from what
perception/narrator rendered and lose the reaction on a rerun)."""

from __future__ import annotations

import json
import time

from commit import prepare_memory_commit, track_background_presences
from pipeline_context import ChatData, PipelineContext, TurnData


def _make_chat(db):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )


def _ctx(chat_id, turn_idx, director_resolve, background_react=None):
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_idx + 1, chat_id=chat_id, idx=turn_idx,
                      player_input="", created=time.time()),
        cast=[], input="", director_resolve=director_resolve,
    )
    if background_react is not None:
        ctx["background_react"] = background_react
    return ctx


_BR_ENTRY = {
    "speaker": "Doran", "exact_quote": '"We\'re closed to your kind."',
    "volume": "normal", "intended_target": None, "tone": "gruff",
    "visibility": "overt", "conceal_from": [],
}


def test_backstop_line_lands_in_event_content(temp_db):
    chat_id = _make_chat(temp_db)
    ctx = _ctx(
        chat_id, 1,
        {"resolved_event": "The taproom quiets.", "dialogue_log": []},
        {"fired": True, "name": "Doran", "dialogue_log_entry": _BR_ENTRY, "action": ""},
    )
    out = prepare_memory_commit(ctx)
    dlog = json.loads(out["event_content"])["dialogue_log"]
    assert len(dlog) == 1
    assert dlog[0]["speaker"] == "Doran"
    assert dlog[0]["source"] == "background_react"
    # The already-persisted director_resolve variant is untouched.
    assert ctx.director_resolve["dialogue_log"] == []


def test_unfired_background_react_adds_nothing(temp_db):
    chat_id = _make_chat(temp_db)
    ctx = _ctx(
        chat_id, 1,
        {"resolved_event": "Silence.", "dialogue_log": []},
        {"fired": False, "name": None, "dialogue_log_entry": None, "action": ""},
    )
    out = prepare_memory_commit(ctx)
    assert json.loads(out["event_content"])["dialogue_log"] == []


def test_backstop_firing_counts_dialogue_turn_without_double_count(temp_db):
    chat_id = _make_chat(temp_db)
    temp_db.wset(chat_id, "background_presences", {
        "Doran": {"first_turn": 0, "last_turn": 0,
                  "dialogue_turns": [], "mention_turns": []},
    })
    # resolved_event ALSO names Doran this beat -- must count once, as a
    # dialogue turn (backstop), never additionally as a mention.
    ctx = _ctx(
        chat_id, 2,
        {"resolved_event": "Doran wipes down the bar.", "dialogue_log": []},
        {"fired": True, "name": "Doran", "dialogue_log_entry": _BR_ENTRY, "action": ""},
    )
    track_background_presences(ctx, nonce=0)
    rec = temp_db.wget(chat_id, "background_presences", {})["Doran"]
    assert rec["dialogue_turns"] == [2]
    assert 2 not in rec["mention_turns"]
