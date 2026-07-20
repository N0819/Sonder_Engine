"""Ensemble gate: with background_config.max_reactors > 1, several qualifying
background presences can voice a single beat (one call each), and every merge
path (perception render, event persistence, dialogue-turn counting, owed-reply
discharge) handles the list. Default cap 1 is covered by the other background
tests remaining green."""

from __future__ import annotations

import json
import time

import agents.background as background
from commit import (
    pick_background_reactors,
    track_background_presences,
    _background_fired_reactions,
)
from pipeline_context import ChatData, PipelineContext, TurnData


def _setup(temp_db, presences, *, max_reactors=2, player_input="", turn_idx=5):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    temp_db.wset(chat_id, "scene", {"location": "x", "rooms": {}, "positions": {},
                                    "entities": {}, "attire": {}, "overlays": {}})
    temp_db.wset(chat_id, "background_presences", presences)
    temp_db.wset(chat_id, "background_config", {"max_reactors": max_reactors})
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, turn_idx, player_input, time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=turn_idx,
                      player_input=player_input, created=time.time()),
        cast=[], input=player_input)
    return chat_id, ctx


def _hist(name, **extra):
    rec = {"first_turn": 1, "last_turn": 4, "dialogue_turns": [1], "mention_turns": []}
    rec.update(extra)
    return rec


def test_gate_returns_multiple_when_cap_allows(temp_db):
    chat_id, ctx = _setup(temp_db, {"Doran": _hist("Doran"), "Mira": _hist("Mira")})
    dr = {"resolved_event": "The alarm bell clangs over the taproom.", "dialogue_log": []}
    picks = pick_background_reactors(ctx, dr, cap=2)
    assert set(picks) == {"Doran", "Mira"}
    # cap still clamps
    assert len(pick_background_reactors(ctx, dr, cap=1)) == 1


def test_ensemble_voices_each_reactor_once(temp_db, monkeypatch):
    chat_id, ctx = _setup(temp_db, {"Doran": _hist("Doran"), "Mira": _hist("Mira")})
    ctx.director_resolve = {"resolved_event": "The alarm bell clangs.", "dialogue_log": []}

    calls = []

    def canned(role, name, system, payload, **kw):
        who = payload["entity"]["name"]
        calls.append(who)
        return {"reacts": True, "dialogue_log_entry": {
            "speaker": "ignored", "exact_quote": f'"{who} reacts."', "volume": "normal",
            "intended_target": None, "tone": "", "visibility": "overt",
            "conceal_from": []}, "action": f"{who} stirs."}

    monkeypatch.setattr(background, "_agent_json", canned)
    out = background.background_react(ctx, nonce=0)

    assert out["fired"] is True
    assert {r["name"] for r in out["reactions"]} == {"Doran", "Mira"}
    assert set(out["selected"]) == {"Doran", "Mira"}
    assert sorted(calls) == ["Doran", "Mira"]          # one call each, no cross-talk
    # each speaker forced to its own gated name
    assert all(r["dialogue_log_entry"]["speaker"] == r["name"] for r in out["reactions"])


def test_ensemble_lines_all_persist_and_count(temp_db):
    chat_id, ctx = _setup(temp_db, {"Doran": _hist("Doran"), "Mira": _hist("Mira")},
                          turn_idx=6)
    ctx.director_resolve = {"resolved_event": "The bell clangs.", "dialogue_log": []}
    ctx["background_react"] = {
        "fired": True, "name": "Doran",
        "dialogue_log_entry": {"speaker": "Doran", "exact_quote": '"Trouble."'},
        "action": "",
        "reactions": [
            {"name": "Doran", "dialogue_log_entry": {"speaker": "Doran",
                                                     "exact_quote": '"Trouble."'}, "action": ""},
            {"name": "Mira", "dialogue_log_entry": {"speaker": "Mira",
                                                    "exact_quote": '"Eek!"'}, "action": ""},
        ],
        "selected": ["Doran", "Mira"],
    }
    # both fired lines are recognized by the normalizer
    assert len(_background_fired_reactions(ctx["background_react"])) == 2
    track_background_presences(ctx, nonce=0)
    presences = temp_db.wget(chat_id, "background_presences", {})
    assert 6 in presences["Doran"]["dialogue_turns"]
    assert 6 in presences["Mira"]["dialogue_turns"]
