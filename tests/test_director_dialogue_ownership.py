"""Regression test for director_resolve's ownership-boundary backstop:
the DIALOGUE LOG prompt instruction now explicitly invites the director
to voice unsheeted background presences, but that license must not let
it invent additional lines for a REGISTERED cast member beyond what
their own character_step declaration actually said.

Since 2026-09-27 the Director writes prose and the encoder files each quoted
line as a speech event; `dialogue_log` is rebuilt from the beat's declarations
alone, so a line nobody declared never reaches it. What it still reaches is
`state_diff.speech`, the resolve's sequence and its rows (no view and no
self-memory -- UNBUILT_PIPELINE §1.1).
"""

from __future__ import annotations

import json
import time

from story.character_schema import default_character_data
from core.pipeline_context import ChatData, PipelineContext, TurnData
from tests.director_fakes import encoder_event, prose_resolve_agent


def _speech_events(*events):
    """What the encoder files: `events` and nothing else."""
    return {"director_specialist": {"events": list(events), "missing_tools": [],
                                    "missing_referents": [], "notes": []}}


def _make_ctx(temp_db, character_results):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) VALUES(?,?,?,?,?)",
        ("Mara", json.dumps(default_character_data("Mara")), "{}", time.time(), "char_mara"),
    )
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"),
    )
    temp_db.wset(chat_id, "scene", {
        "location": "x", "time": "day", "rooms": {}, "positions": {},
        "entities": {}, "attire": {}, "overlays": {},
    })
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,),
    )
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "look around", time.time()),
    )
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="look around",
                      created=time.time()),
        cast=cast, input="look around",
    )
    ctx.director_interpret = {
        "sequence": [], "speech": None, "action": None,
        "flow": {"reactors": [], "authority_claims": [], "resolution_flags": {},
                 "fiction_frame": {}},
    }
    if character_results:
        ctx.character_results = {char_id: character_results}
    return ctx, char_id


def test_invented_line_for_a_cast_member_is_dropped(temp_db, monkeypatch,
                                                    prose_director):
    """The encoder files the invented line as Mara's speech; the log, built
    from declarations, never carries it. (The "Dropped director-invented"
    warning belonged to a log the Director wrote, which no longer exists.)"""
    import agents.director as director

    ctx, char_id = _make_ctx(temp_db, character_results=None)
    monkeypatch.setattr(director, "_agent_json", prose_resolve_agent(
        {"resolved_event": 'Mara says, "I never said this."'},
        per_step=_speech_events(encoder_event(
            "I never said this.", source=f"character:{char_id}", speech=True))))

    out = director.director_resolve(ctx, nonce=0)

    bodies = [d["exact_quote"] for d in out["dialogue_log"]]
    assert not any("never said this" in b for b in bodies)


def test_line_matching_the_characters_own_declaration_is_kept(temp_db, monkeypatch,
                                                              prose_director):
    import agents.director as director

    ctx, char_id = _make_ctx(temp_db, character_results={
        "name": "Mara", "speech": "I told you already.",
        "sequence": [{"type": "speech", "text": "I told you already.", "volume": "normal"}],
        "action": None,
    })
    monkeypatch.setattr(director, "_agent_json", prose_resolve_agent(
        {"resolved_event": 'Mara says, "I told you already."'}))

    out = director.director_resolve(ctx, nonce=0)

    bodies = [d["exact_quote"] for d in out["dialogue_log"]]
    assert any("I told you already" in b for b in bodies)
    assert not any("Dropped director-invented dialogue line" in w for w in ctx.warnings)


def _make_player_ctx(temp_db, declared_speech):
    """Chat with a player persona 'Hinami' and a declared player speech line,
    for the player-speech-authority backstop."""
    from story.character_schema import default_persona_data
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        ("Hinami", json.dumps(default_persona_data("Hinami")), "{}"),
    )
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Test", "", time.time(), persona_id),
    )
    temp_db.wset(chat_id, "scene", {
        "location": "x", "time": "day", "rooms": {}, "positions": {},
        "entities": {}, "attire": {}, "overlays": {},
    })
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, declared_speech, time.time()),
    )
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                      player_input=declared_speech, created=time.time()),
        cast=[], input=declared_speech,
    )
    ctx.director_interpret = {
        "sequence": [{"type": "speech", "text": declared_speech, "volume": "loud"}],
        "speech": declared_speech, "action": None,
        "flow": {"reactors": [], "authority_claims": [], "resolution_flags": {},
                 "fiction_frame": {}},
    }
    return ctx


def test_invented_player_line_is_dropped(temp_db, monkeypatch, prose_director):
    """Player-speech authority: the director took a wordless cry and ADDED an
    invented player line (Elevator Adventure t42: 'AaUaa!' -> a fabricated
    'Can't... not now...'). The declared cry survives; the invention is dropped.

    On the prose path the invention is flagged on the step by the prose-quote
    reading rather than in ctx.warnings."""
    import agents.director as director

    ctx = _make_player_ctx(temp_db, declared_speech="AaUaa!")
    pid = ctx.chat.persona_id
    monkeypatch.setattr(director, "_agent_json", prose_resolve_agent(
        {"resolved_event": 'Hinami cries out, "AaUaa!" Then: "Can\'t... not now..."'},
        per_step=_speech_events(
            encoder_event("AaUaa!", source=f"persona:{pid}", speech=True),
            encoder_event("Can't... not now...", source=f"persona:{pid}",
                          speech=True))))

    out = director.director_resolve(ctx, nonce=0)
    bodies = [d["exact_quote"] for d in out["dialogue_log"]]
    assert any("AaUaa" in b for b in bodies)           # declared line kept
    assert not any("not now" in b for b in bodies)     # invention dropped
    assert any("prose-quote authority" in w and "not now" in w
               for w in (out.get("player_act_warnings") or []))


def test_declared_player_line_is_kept(temp_db, monkeypatch, prose_director):
    import agents.director as director

    ctx = _make_player_ctx(temp_db, declared_speech="Little better...")
    monkeypatch.setattr(director, "_agent_json", prose_resolve_agent(
        {"resolved_event": 'Hinami murmurs, "Little better..."'}))
    out = director.director_resolve(ctx, nonce=0)
    bodies = [d["exact_quote"] for d in out["dialogue_log"]]
    assert any("Little better" in b for b in bodies)
    assert not any("player-speech authority" in w for w in ctx.warnings)
