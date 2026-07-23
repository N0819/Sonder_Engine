"""Regression test for director_resolve's ownership-boundary backstop:
the DIALOGUE LOG prompt instruction now explicitly invites the director
to voice unsheeted background presences, but that license must not let
it invent additional lines for a REGISTERED cast member beyond what
their own character_step declaration actually said."""

from __future__ import annotations

import json
import time

from character_schema import default_character_data
from pipeline_context import ChatData, PipelineContext, TurnData


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


def test_invented_line_for_a_cast_member_is_dropped(temp_db, monkeypatch):
    import agents.director as director

    ctx, char_id = _make_ctx(temp_db, character_results=None)
    monkeypatch.setattr(director, "_agent_json", lambda *a, **k: {
        "dialogue_log": [{
            "speaker": "Mara", "exact_quote": '"I never said this."',
            "volume": "normal", "intended_target": None, "tone": "",
        }],
    })

    out = director.director_resolve(ctx, nonce=0)

    bodies = [d["exact_quote"] for d in out["dialogue_log"]]
    assert not any("never said this" in b for b in bodies)
    assert any("Dropped director-invented dialogue line" in w for w in ctx.warnings)


def test_line_matching_the_characters_own_declaration_is_kept(temp_db, monkeypatch):
    import agents.director as director

    ctx, char_id = _make_ctx(temp_db, character_results={
        "name": "Mara", "speech": "I told you already.",
        "sequence": [{"type": "speech", "text": "I told you already.", "volume": "normal"}],
        "action": None,
    })
    monkeypatch.setattr(director, "_agent_json", lambda *a, **k: {
        "dialogue_log": [{
            "speaker": "Mara", "exact_quote": '"I told you already."',
            "volume": "normal", "intended_target": None, "tone": "",
        }],
    })

    out = director.director_resolve(ctx, nonce=0)

    bodies = [d["exact_quote"] for d in out["dialogue_log"]]
    assert any("I told you already" in b for b in bodies)
    assert not any("Dropped director-invented dialogue line" in w for w in ctx.warnings)


def _make_player_ctx(temp_db, declared_speech):
    """Chat with a player persona 'Hinami' and a declared player speech line,
    for the player-speech-authority backstop."""
    from character_schema import default_persona_data
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


def test_invented_player_line_is_dropped(temp_db, monkeypatch):
    """Player-speech authority: the director took a wordless cry and ADDED an
    invented player line (Elevator Adventure t42: 'AaUaa!' -> a fabricated
    'Can't... not now...'). The declared cry survives; the invention is dropped."""
    import agents.director as director

    ctx = _make_player_ctx(temp_db, declared_speech="AaUaa!")
    monkeypatch.setattr(director, "_agent_json", lambda *a, **k: {
        "dialogue_log": [
            {"speaker": "Hinami", "exact_quote": '"AaUaa!"', "volume": "loud",
             "intended_target": None, "tone": "pained"},
            {"speaker": "Hinami", "exact_quote": '"Can\'t... not now..."',
             "volume": "normal", "intended_target": None, "tone": "strained"},
        ],
    })

    out = director.director_resolve(ctx, nonce=0)
    bodies = [d["exact_quote"] for d in out["dialogue_log"]]
    assert any("AaUaa" in b for b in bodies)           # declared line kept
    assert not any("not now" in b for b in bodies)     # invention dropped
    assert any("player-speech authority" in w for w in ctx.warnings)


def test_declared_player_line_is_kept(temp_db, monkeypatch):
    import agents.director as director

    ctx = _make_player_ctx(temp_db, declared_speech="Little better...")
    monkeypatch.setattr(director, "_agent_json", lambda *a, **k: {
        "dialogue_log": [
            {"speaker": "Hinami", "exact_quote": '"Little better..."',
             "volume": "normal", "intended_target": None, "tone": ""},
        ],
    })
    out = director.director_resolve(ctx, nonce=0)
    bodies = [d["exact_quote"] for d in out["dialogue_log"]]
    assert any("Little better" in b for b in bodies)
    assert not any("player-speech authority" in w for w in ctx.warnings)


def test_unsheeted_background_entity_dialogue_is_not_filtered(temp_db, monkeypatch):
    import agents.director as director

    ctx, char_id = _make_ctx(temp_db, character_results=None)
    monkeypatch.setattr(director, "_agent_json", lambda *a, **k: {
        "dialogue_log": [{
            "speaker": "Dr. Crusher", "exact_quote": '"Hold still."',
            "volume": "normal", "intended_target": None, "tone": "",
        }],
    })

    out = director.director_resolve(ctx, nonce=0)

    bodies = [d["exact_quote"] for d in out["dialogue_log"]]
    assert any("Hold still" in b for b in bodies)
    assert not ctx.warnings
