"""Regression tests for the background_react stage (agents/background.py)
and its deterministic gate (commit.py's pick_background_reactor).

Motivation: live play showed a named background presence (no character
sheet, voiced only through the director's own resolved_event/dialogue_log
authorship) can go inert for 25+ turns despite being directly addressed,
given orders, and present at dramatic beats -- even though prompts.py's
director_resolve entry explicitly licenses voicing them. This mirrors the
"prompt compliance alone is unreliable" lesson already learned for spatial
zone-tagging and speech concealment, so the fix is the same shape: a
deterministic gate (pick_background_reactor) decides WHETHER a reaction is
warranted this beat, and only then is a cheap, stateless LLM call spent
deciding WHAT it is.
"""

from __future__ import annotations

import json
import time

from character_schema import default_character_data
from commit import pick_background_reactor
from pipeline_context import ChatData, PipelineContext, TurnData


def _make_ctx(temp_db, background_presences=None, cast_names=None, player_input=""):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    cast_rows = []
    for name in (cast_names or []):
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) VALUES(?,?,?,?,?)",
            (name, json.dumps(default_character_data(name)), "{}", time.time(), f"char_{name.lower()}"),
        )
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
            (chat_id, char_id, "active", "{}"),
        )
    cast_rows = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,),
    )
    temp_db.wset(chat_id, "scene", {
        "location": "x", "time": "day", "rooms": {}, "positions": {},
        "entities": {}, "attire": {}, "overlays": {},
    })
    if background_presences is not None:
        temp_db.wset(chat_id, "background_presences", background_presences)

    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 5, player_input, time.time()),
    )
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=5, player_input=player_input,
                      created=time.time()),
        cast=cast_rows, input=player_input,
    )
    return ctx


def test_no_candidates_when_no_background_presences_tracked(temp_db):
    ctx = _make_ctx(temp_db, background_presences={})
    assert pick_background_reactor(ctx, {"resolved_event": "Nothing happens.", "dialogue_log": []}) is None


def test_picks_presence_with_prior_dialogue_history(temp_db):
    ctx = _make_ctx(temp_db, background_presences={
        "Reya": {"first_turn": 1, "last_turn": 4, "dialogue_turns": [1], "mention_turns": [2, 3, 4]},
    })
    dr_output = {"resolved_event": "The alarm blares through the corridor.", "dialogue_log": []}
    assert pick_background_reactor(ctx, dr_output) == "Reya"


def test_excludes_presence_already_voiced_this_beat(temp_db):
    ctx = _make_ctx(temp_db, background_presences={
        "Reya": {"first_turn": 1, "last_turn": 4, "dialogue_turns": [1], "mention_turns": []},
    })
    dr_output = {
        "resolved_event": "Reya nods.",
        "dialogue_log": [{"speaker": "Reya", "exact_quote": '"On it."'}],
    }
    assert pick_background_reactor(ctx, dr_output) is None


def test_excludes_presence_with_no_history_and_no_beat_salience(temp_db):
    ctx = _make_ctx(temp_db, background_presences={
        "Docking Control Operator": {"first_turn": 1, "last_turn": 1,
                                      "dialogue_turns": [], "mention_turns": []},
    })
    dr_output = {"resolved_event": "The Doctor keeps cutting the panel.", "dialogue_log": []}
    assert pick_background_reactor(ctx, dr_output) is None


def test_excludes_registered_cast_member_even_if_tracked(temp_db):
    ctx = _make_ctx(
        temp_db,
        cast_names=["Reya"],
        background_presences={
            "Reya": {"first_turn": 1, "last_turn": 4, "dialogue_turns": [1], "mention_turns": []},
        },
    )
    dr_output = {"resolved_event": "Reya says nothing.", "dialogue_log": []}
    assert pick_background_reactor(ctx, dr_output) is None


def test_prioritizes_addressed_presence_over_merely_mentioned(temp_db):
    ctx = _make_ctx(
        temp_db,
        player_input="Reya, can you cut the feed?",
        background_presences={
            "Reya": {"first_turn": 1, "last_turn": 1, "dialogue_turns": [], "mention_turns": []},
            "Docking Control Operator": {"first_turn": 1, "last_turn": 4,
                                          "dialogue_turns": [1, 2], "mention_turns": [3, 4]},
        },
    )
    dr_output = {
        "resolved_event": "The Docking Control Operator relays a status update.",
        "dialogue_log": [],
    }
    assert pick_background_reactor(ctx, dr_output) == "Reya"


def test_background_react_stage_skips_llm_call_when_no_candidate(temp_db, monkeypatch):
    import agents.background as background

    ctx = _make_ctx(temp_db, background_presences={})
    ctx.director_resolve = {"resolved_event": "Nothing happens.", "dialogue_log": []}

    def fail_if_called(*a, **k):
        raise AssertionError("LLM call must not fire when the gate finds no candidate")

    monkeypatch.setattr(background, "_agent_json", fail_if_called)

    result = background.background_react(ctx, nonce=0)
    assert result == {"fired": False, "name": None, "dialogue_log_entry": None, "action": ""}


def test_background_react_stage_returns_fired_entry_when_gate_passes(temp_db, monkeypatch):
    import agents.background as background

    ctx = _make_ctx(temp_db, background_presences={
        "Reya": {"first_turn": 1, "last_turn": 4, "dialogue_turns": [1], "mention_turns": []},
    })
    ctx.director_resolve = {"resolved_event": "The alarm blares.", "dialogue_log": []}

    monkeypatch.setattr(background, "_agent_json", lambda *a, **k: {
        "reacts": True,
        "dialogue_log_entry": {
            "speaker": "someone else", "exact_quote": '"That is not good."',
            "volume": "normal", "intended_target": None, "tone": "alarmed",
        },
        "action": "grips the console.",
    })

    result = background.background_react(ctx, nonce=0)
    assert result["fired"] is True
    assert result["name"] == "Reya"
    # Speaker is forced to the gate-picked name regardless of what the LLM echoed back --
    # never trust the model to correctly self-attribute the speaker it was asked to voice.
    assert result["dialogue_log_entry"]["speaker"] == "Reya"
    assert result["dialogue_log_entry"]["exact_quote"] == '"That is not good."'
    assert result["action"] == "grips the console."


def test_background_react_stage_handles_reacts_false(temp_db, monkeypatch):
    import agents.background as background

    ctx = _make_ctx(temp_db, background_presences={
        "Reya": {"first_turn": 1, "last_turn": 4, "dialogue_turns": [1], "mention_turns": []},
    })
    ctx.director_resolve = {"resolved_event": "The alarm blares.", "dialogue_log": []}

    monkeypatch.setattr(background, "_agent_json", lambda *a, **k: {
        "reacts": False, "dialogue_log_entry": None, "action": "",
    })

    result = background.background_react(ctx, nonce=0)
    assert result["fired"] is False
    assert result["dialogue_log_entry"] is None
