"""A line one player hides from another, by any name the other answers to,
stays hidden -- at interpret as at resolve.

The interpret resolved `conceal_from` against the CAST alone
(`_cast_match_forms`), while the resolve used the scene's bodies with the
players in them (`_scene_match_forms`, whose own docstring records this bug:
a player's spelling was "no body in this scene"). So an extra player's
whisper hidden from the primary player by her alias was kept raw, matched
against her name by the firewall reader, and published to her; and the
fail-closed branch for an unresolved engine form listed every cast body and
no player (review 2026-11-01, director floors F2 -- a LEAK). One set of
body maps for every concealment floor.
"""

from __future__ import annotations

import json

import agents.director as director
from agents.composer import concealed_from_observer

from tests.director_fakes import _make_ctx, _speech_interp, encoder_event


def _hinami(db, ctx):
    pid = db.qi("INSERT INTO personas(name,sheet) VALUES(?,?)", ("Hinami", json.dumps(
        {"identity": {"name": "Hinami", "aliases": ["Hina"]}})))
    db.qi("UPDATE chats SET persona_id=? WHERE id=?", (pid, ctx.chat.id))
    ctx.chat.persona_id = pid
    scene = db.wget(ctx.chat.id, "scene")
    scene["positions"] = {"Hinami": "keeper_room", "Mara": "keeper_room",
                          "Bob": "keeper_room"}
    db.wset(ctx.chat.id, "scene", scene)
    return pid


def test_an_extra_players_whisper_hidden_from_hinami_by_her_alias(
        temp_db, monkeypatch, prose_director):
    ctx = _make_ctx(temp_db, interp=_speech_interp(), player_input="I wait.")
    ctx.director_interpret = None
    pid = _hinami(temp_db, ctx)
    ctx.extra_players = [{"persona_id": 99, "name": "Bob", "idle": False,
                          "input": '"Meet me at the mill," I whisper to Mara.'}]

    def fake(role, step_key, system, payload, **kw):
        if step_key == "director_prose":
            return {"prose": 'Hinami waits. Bob whispers to Mara, "Meet me at the mill."'}
        if step_key == "director_specialist":
            return {"events": [
                encoder_event("Hinami waits.", source=f"persona:{pid}"),
                encoder_event("Meet me at the mill.", source="persona:99",
                              speech=True, targets=["Mara"],
                              visibility="concealed", conceal_from=["Hina"]),
            ]}
        return {}
    monkeypatch.setattr(director, "_agent_json", fake)

    out = director.director_interpret(ctx, nonce=0)

    line = next(e for e in out["other_players"]["99"]["sequence"]
                if e.get("type") == "speech")
    assert concealed_from_observer(line, "Hinami") is True, line.get("conceal_from")
    assert concealed_from_observer(line, "Mara") is False
