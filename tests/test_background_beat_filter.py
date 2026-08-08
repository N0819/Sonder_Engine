"""Regression test for the background-presence perception leak
(AUDIT_FINDINGS #2 HIGH sub-item).

agents/background.py's background_react passed the RAW player declaration
(ctx.input) and the full objective resolved_event to an unregistered bystander
with no perception filtering, so concealed/whispered/private content leaked to
a presence that never legitimately sensed it -- and, worse, naming the presence
while concealing made the deterministic gate MORE likely to pick them.

Fix: the presence now receives a filtered beat -- concealed sequence elements
and the private thought are stripped from the player declaration, and audible
station-room dialogue is preferred over the raw objective outcome (with any
concealed quote body redacted from the fallback prose).
"""

from __future__ import annotations

import json
import time

from pipeline_context import ChatData, PipelineContext, TurnData

import agents.background as background
from agents.background import _beat_for_presence, _filtered_player_declaration


SECRET = "The shipment arrives at midnight."


def _ctx(temp_db, interp):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("T", "", time.time()),
    )
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="T", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=1, chat_id=chat_id, idx=1, player_input="", created=time.time()),
        cast=[], input="I lean in and whisper: " + SECRET,
    )
    ctx.director_interpret = interp
    return ctx


def test_filtered_declaration_drops_concealed_speech(temp_db):
    ctx = _ctx(temp_db, {
        "sequence": [
            {"type": "speech", "text": SECRET, "visibility": "concealed",
             "conceal_from": ["Doc"]},
            {"type": "speech", "text": "Evening.", "visibility": "overt"},
        ],
    })
    decl = _filtered_player_declaration(ctx)
    assert "midnight" not in decl
    assert "Evening." in decl


def test_filtered_declaration_withholds_raw_input_when_thought_private(temp_db):
    # No structured sequence, but a private thought exists -> the raw input
    # (which contains the whispered secret) must be withheld entirely.
    ctx = _ctx(temp_db, {"sequence": [], "private_thought": "don't let Doc hear"})
    assert _filtered_player_declaration(ctx) == ""


def test_filtered_declaration_passes_public_raw_input(temp_db):
    ctx = _ctx(temp_db, {"sequence": []})
    ctx.input = "I wave at the crowd."
    assert _filtered_player_declaration(ctx) == "I wave at the crowd."


def _scene_with(rooms_by_name):
    """A scene placing each speaker in a room, all mutually audible."""
    return {
        "rooms": {r: {"name": r, "adjacent": []} for r in set(rooms_by_name.values())},
        "positions": dict(rooms_by_name),
        "entities": {}, "attire": {}, "overlays": {},
    }


def test_beat_drops_concealed_dialogue_and_surfaces_an_audible_one():
    sc = _scene_with({"Player": "bar", "Guard": "bar", "Doc": "bar"})
    dr = {
        "resolved_event": "A hush falls. The shipment arrives at midnight, or so it seems.",
        "dialogue_log": [
            {"speaker": "Player", "exact_quote": SECRET,
             "visibility": "concealed", "conceal_from": ["Doc"], "volume": "whisper"},
            {"speaker": "Guard", "exact_quote": "Move along.", "visibility": "overt"},
        ],
    }
    beat = _beat_for_presence(dr, sc, "bar", "Doc")
    assert "midnight" not in beat
    # An overt line Doc is placed to hear is surfaced.
    assert "Move along." in beat


def test_an_unplaced_presence_receives_nothing(temp_db=None):
    """X1: the hearing check ran only `if station_room and sc`, so a presence
    tracked from a dialogue_log speaker alone -- which has no station room --
    fell through it and got every audible quote of the beat verbatim, then
    replied into public canon. This test previously asserted that leak
    ('Move along.' in beat) with `sc=None, station_room=None`; co-presence is
    not the default, and the no-audible-line fallback to resolved_event would
    have handed an unplaced presence the omniscient prose besides."""
    dr = {
        "resolved_event": "A hush falls. The shipment arrives at midnight.",
        "dialogue_log": [
            {"speaker": "Guard", "exact_quote": "Move along.", "visibility": "overt"},
        ],
    }
    assert _beat_for_presence(dr, None, None, "Doc") == ""


def test_a_half_heard_line_is_not_quotable():
    """X2: a line was dropped only at hear_level 'none', so 'fragment' handed
    over the whole exact_quote -- commit._character_address_of requires 'full'
    to count the same line as addressed, and the two disagreeing is the bug."""
    sc = {
        "rooms": {"bar": {"name": "bar", "adjacent": [{"to": "yard", "barrier": "open_door"}]},
                  "yard": {"name": "yard", "adjacent": [{"to": "bar", "barrier": "open_door"}]}},
        "positions": {"Guard": "yard", "Doc": "bar"},
        "entities": {}, "attire": {}, "overlays": {},
    }
    from spatial import hear_level, spatial_rel
    level = hear_level(spatial_rel(sc, "yard", "bar"), "normal")
    dr = {"resolved_event": "", "dialogue_log": [
        {"speaker": "Guard", "exact_quote": "Move along.", "visibility": "overt"}]}
    beat = _beat_for_presence(dr, sc, "bar", "Doc")
    if level == "full":
        assert "Move along." in beat
    else:
        assert "Move along." not in beat


def test_beat_concealed_from_this_presence_only():
    dr = {
        "resolved_event": "Quiet words pass.",
        "dialogue_log": [
            {"speaker": "Player", "exact_quote": SECRET,
             "conceal_from": ["Doc"], "visibility": "overt"},
        ],
    }
    # Concealed FROM Doc (even without a global concealed flag) -> excluded.
    assert "midnight" not in _beat_for_presence(dr, None, None, "Doc")


def test_background_react_payload_is_filtered(temp_db, monkeypatch):
    """End-to-end: the payload handed to the presence's LLM call must not
    contain the concealed line, from either channel."""
    ctx = _ctx(temp_db, {
        "sequence": [{"type": "speech", "text": SECRET, "visibility": "concealed",
                      "conceal_from": ["Doc"]}],
    })
    ctx.director_resolve = {
        "resolved_event": "A tense pause.",
        "dialogue_log": [{"speaker": "Player", "exact_quote": SECRET,
                          "visibility": "concealed", "conceal_from": ["Doc"]}],
    }
    temp_db.wset(ctx.chat.id, "scene", {"rooms": {}, "positions": {}})
    temp_db.wset(ctx.chat.id, "background_presences", {"Doc": {"sketch": {}}})

    monkeypatch.setattr(background, "pick_background_reactors", lambda *a, **k: ["Doc"])

    captured = {}

    def fake_agent_json(role, step_key, system, payload, **kwargs):
        captured["payload"] = payload
        return {"reacts": False}

    monkeypatch.setattr(background, "_agent_json", fake_agent_json)

    background.background_react(ctx, nonce=0)

    blob = json.dumps(captured["payload"], ensure_ascii=False)
    assert "midnight" not in blob, "concealed line leaked into background payload"


def test_a_known_station_in_another_room_is_not_a_vantage_on_the_beat():
    """The fall-through inversion: with no audible line, a presence whose
    station was KNOWN but elsewhere received the full omniscient prose --
    deterministically computed as out of earshot, then handed strictly MORE
    than an in-earshot presence. Chat 65's Vendor (fountain_plaza) received
    eastern_market prose through exactly this path on t2147."""
    sc = {
        "rooms": {"bar": {"name": "bar", "adjacent": [{"to": "yard", "barrier": "wall"}]},
                  "yard": {"name": "yard", "adjacent": [{"to": "bar", "barrier": "wall"}]}},
        "positions": {}, "entities": {}, "attire": {}, "overlays": {},
    }
    dr = {"resolved_event": "In the bar, coins change hands over the counter.",
          "dialogue_log": []}
    assert _beat_for_presence(dr, sc, "yard", "Doc", beat_room="bar") == ""
    # The same station co-located with the beat keeps its bystander's view.
    assert "coins change hands" in _beat_for_presence(
        dr, sc, "bar", "Doc", beat_room="bar")


def test_an_unknown_beat_room_fails_closed():
    """Not knowing where the beat resolved is the same epistemic state as not
    knowing where the presence stands, and the X1 rule already answers that:
    deliver nothing."""
    dr = {"resolved_event": "Something happens somewhere.", "dialogue_log": []}
    assert _beat_for_presence(dr, None, "bar", "Doc") == ""
    assert _beat_for_presence(dr, None, "bar", "Doc", beat_room=None) == ""
