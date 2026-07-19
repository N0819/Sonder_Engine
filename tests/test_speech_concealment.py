"""Regression tests for the speech-concealment leak found during live play:

agents/perception.py's deterministic dialogue-injection backstops
(perception_act's hear_level loop and perception_outcome's npc_dlog loop)
used to inject EVERY speech/dialogue_log entry into every in-range
perceiver's view based purely on physical distance, with no check of
visibility/conceal_from at all -- unlike the exactly parallel action-
handling code path, which already excluded visibility:'concealed'
elements. A concealed comm call or whispered aside was therefore
guaranteed to reach every hearing-range perceiver, including whoever it
was declared concealed from.

Fix: speech sequence elements and dialogue_log entries now carry their
own visibility/conceal_from (schemas.py), agents/director.py
deterministically stamps dialogue_log entries with the concealment of
their originating declaration (never trusting the director model to
transcribe it correctly), and both perception.py backstops skip
concealed entries -- exactly mirroring the pre-existing action_elems /
last_overt_by_actor concealment filters.
"""

from __future__ import annotations

import json
import time

from character_schema import default_character_data
from pipeline_context import ChatData, PipelineContext, TurnData


def _make_director_ctx(temp_db, character_results=None):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) VALUES(?,?,?,?,?)",
        ("Reya", json.dumps(default_character_data("Reya")), "{}", time.time(), "char_reya"),
    )
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"),
    )
    temp_db.wset(chat_id, "scene", {
        "location": "x", "time": "day",
        "rooms": {"room1": {"name": "Room 1", "adjacent": []}},
        "positions": {"The Stranger": "room1", "Reya": "room1"},
        "entities": {}, "attire": {}, "overlays": {},
    })
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,),
    )
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "whisper to my contact", time.time()),
    )
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="whisper to my contact",
                      created=time.time()),
        cast=cast, input="whisper to my contact",
    )
    ctx.director_interpret = {
        "sequence": [{"type": "speech", "text": "The shipment arrives at midnight.",
                      "volume": "normal", "tone": "hushed",
                      "visibility": "concealed", "conceal_from": [char_id]}],
        "speech": None, "action": None,
        "flow": {"reactors": [char_id], "authority_claims": [], "resolution_flags": {},
                 "fiction_frame": {}},
    }
    if character_results:
        ctx.character_results = {char_id: character_results}
    return ctx, char_id


def test_director_resolve_stamps_concealment_from_player_sequence(temp_db, monkeypatch):
    """The director model's dialogue_log entry omits visibility/conceal_from
    (as live models reliably do) -- director_resolve must stamp it anyway,
    from the player's own declared sequence element, not trust the model."""
    import agents.director as director

    ctx, char_id = _make_director_ctx(temp_db)
    monkeypatch.setattr(director, "_agent_json", lambda *a, **k: {
        "dialogue_log": [{
            "speaker": "The Stranger", "exact_quote": '"The shipment arrives at midnight."',
            "volume": "normal", "intended_target": None, "tone": "hushed",
        }],
    })

    out = director.director_resolve(ctx, nonce=0)

    entry = next(d for d in out["dialogue_log"] if "midnight" in d["exact_quote"])
    assert entry["visibility"] == "concealed"
    assert char_id in entry["conceal_from"]


def test_director_resolve_stamps_volume_from_player_sequence(temp_db, monkeypatch):
    """Live play (chat 10, turn 22) found a sibling bug to the concealment
    leak: the director model transcribed a whisper into dialogue_log as
    volume:'normal', which would let hear_level() carry a 200-meter-shaft
    whisper as if spoken normally. The same deterministic backstop that
    protects visibility/conceal_from must also protect volume."""
    import agents.director as director

    ctx, char_id = _make_director_ctx(temp_db)
    ctx.director_interpret["sequence"][0]["volume"] = "whisper"
    monkeypatch.setattr(director, "_agent_json", lambda *a, **k: {
        "dialogue_log": [{
            "speaker": "The Stranger", "exact_quote": '"The shipment arrives at midnight."',
            "volume": "normal", "intended_target": None, "tone": "hushed",
        }],
    })

    out = director.director_resolve(ctx, nonce=0)

    entry = next(d for d in out["dialogue_log"] if "midnight" in d["exact_quote"])
    assert entry["volume"] == "whisper"


def test_director_resolve_stamps_concealment_from_character_sequence(temp_db, monkeypatch):
    """Same backstop for an NPC's own concealed speech declaration."""
    import agents.director as director

    ctx, char_id = _make_director_ctx(
        temp_db,
        character_results={
            "name": "Reya", "speech": None, "action": None,
            "sequence": [{"type": "speech", "text": "Don't tell the Doctor.",
                          "volume": "normal", "tone": "low",
                          "visibility": "concealed", "conceal_from": ["the_doctor"]}],
        },
    )
    monkeypatch.setattr(director, "_agent_json", lambda *a, **k: {
        "dialogue_log": [{
            "speaker": "Reya", "exact_quote": '"Don\'t tell the Doctor."',
            "volume": "normal", "intended_target": None, "tone": "low",
        }],
    })

    out = director.director_resolve(ctx, nonce=0)

    entry = next(d for d in out["dialogue_log"] if "tell the Doctor" in d["exact_quote"])
    assert entry["visibility"] == "concealed"
    assert "the_doctor" in entry["conceal_from"]


def test_perception_act_does_not_inject_concealed_speech(temp_db, monkeypatch):
    """Reproduces the live leak (turn 130, chat 10): a concealed speech
    sequence element must never reach a perceiver's view via perception_
    act's deterministic hear_level backstop, regardless of physical
    proximity."""
    import agents.perception as perception

    ctx, char_id = _make_director_ctx(temp_db)
    ctx["_player_room"] = "room1"

    def fake_agent_json(role, step_key, system, payload, **kwargs):
        return {"views": {str(p["id"]): f"You are in {p['room_name']}."
                          for p in payload["perceivers"]}}

    monkeypatch.setattr(perception, "_agent_json", fake_agent_json)

    result = perception.perception_act(ctx, nonce=0)

    for pid, view in result["views"].items():
        assert "midnight" not in (view or ""), (
            f"concealed speech leaked into perceiver {pid}'s view via the "
            "deterministic hear_level backstop"
        )


def test_perception_outcome_does_not_inject_concealed_dialogue(temp_db, monkeypatch):
    """Same reproduction at the outcome stage: a dialogue_log entry marked
    visibility:'concealed' must never reach a perceiver's view via
    perception_outcome's deterministic npc_dlog backstop."""
    import agents.perception as perception

    ctx, char_id = _make_director_ctx(temp_db)
    ctx.director_resolve = {
        "resolved_event": "A quiet exchange passes unnoticed.",
        "dialogue_log": [{
            "speaker": "Reya", "exact_quote": '"The shipment arrives at midnight."',
            "volume": "normal", "intended_target": None, "tone": "hushed",
            "visibility": "concealed", "conceal_from": ["The Stranger"],
        }],
    }

    def fake_agent_json(role, step_key, system, payload, **kwargs):
        return {"views": {str(p["id"]): f"You are in {p['room_name']}."
                          for p in payload["perceivers"]}}

    monkeypatch.setattr(perception, "_agent_json", fake_agent_json)

    result = perception.perception_outcome(ctx, nonce=0)

    for pid, view in result["views"].items():
        assert "midnight" not in (view or ""), (
            f"concealed dialogue_log entry leaked into perceiver {pid}'s view "
            "via the deterministic npc_dlog backstop"
        )
