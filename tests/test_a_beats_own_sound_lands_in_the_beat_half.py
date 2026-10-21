"""A BEAT'S OWN SOUND LANDS IN THE BEAT HALF OF THE OUTCOME VIEW
(DESIGN_SOUND_FIELD.md § 16, round 2 lane B, 2026-10-20; closes
UNBUILT_PERCEPTION § 2.36's first wave-B2 bullet).

`composer.ambient_percepts` says a beat's own sound event is not standing
state and lands it in the beat half when the caller keys it; the establish
pass keyed its beat sounds (`perception._AMBIENT_BEAT_BAND`) and the
outcome pass did not, so every sound a beat made -- in the observer's own
room, or heard from the next -- rendered lowercase in the view's background
half ("... You see a person of unremarkable appearance. a flat crack of
musket fire."), after the furniture and before the acts, as optional as the
colour of the floor.

The class: every sound a beat makes is told among the beat's events, after
the acts that made it, as a sentence of its own.
"""

from __future__ import annotations

import json
import time

PLAYER = "Pip"
CAST = "Wren Hollis"


def _fields(cast_room, cast_cell):
    def room(name, adjacent):
        return {"name": name, "exposure": "open", "extent": {"w": 96, "d": 6},
                "anchors": {}, "adjacent": adjacent, "light": "bright"}
    return {"location": "the fields", "time": "noon",
            "rooms": {"meadow": room("the meadow", [{"to": "pasture",
                                                    "barrier": "open",
                                                    "dir": "e"}]),
                      "pasture": room("the pasture", [{"to": "meadow",
                                                       "barrier": "open",
                                                       "dir": "w"}])},
            "positions": {PLAYER: "meadow", CAST: cast_room},
            "stations": {PLAYER: {"cell": [40, 3]}, CAST: {"cell": list(cast_cell)}},
            "entities": {}, "attire": {}, "overlays": {}, "poses": {},
            "orientation": {}, "contained": {}}


def _outcome(db, cast_room, cast_cell):
    from agents import perception
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    from story.character_schema import (default_character_data,
                                        default_persona_data)
    persona_id = db.qi("INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
                       (PLAYER, json.dumps(default_persona_data(PLAYER)), "{}"))
    cid = db.qi("INSERT INTO chats(name,scenario,created,persona_id) "
                "VALUES(?,?,?,?)", ("Fields", "", time.time(), persona_id))
    char_id = db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (CAST, json.dumps(default_character_data(CAST)), "{}", time.time(),
         "char_wren_%s_%d" % (cast_room, cast_cell[0])))
    db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
          (cid, char_id, "active", "{}"))
    db.wset(cid, "scene", _fields(cast_room, cast_cell))
    db.wset(cid, "known", {CAST: [PLAYER], PLAYER: [CAST]})
    cast = db.q("SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
                "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
                (cid,))
    turn = db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                 "VALUES(?,?,?,?)", (cid, 1, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Fields", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn, chat_id=cid, idx=1, player_input="",
                      created=time.time()),
        cast=cast, input="")
    ctx["_player_room"] = "meadow"
    ctx.director_interpret = {
        "action": {"attempt": "fires the musket into the air",
                   "visibility": "overt", "conceal_from": [], "targets": [],
                   "commitment": "asserted"},
        "sequence": [{"type": "action", "attempt": "fires the musket into the air",
                      "observable": "fires the musket into the air",
                      "visibility": "overt", "conceal_from": [], "targets": [],
                      "commitment": "asserted", "verb": "fire",
                      "stage": "immediate",
                      "event_id": "turn:1:player:0:action"}],
        "speech": None, "speech_volume": "normal", "flow": {"reactors": []}}
    ctx.director_resolve = {
        "resolved_event": "The musket fires.",
        "state_diff": {"sensory_events": [{
            "kind": "sound", "room": "meadow", "level": "loud",
            "source": PLAYER, "detail": "a flat crack of musket fire"}]},
        "dialogue_log": [], "dialogue_order": []}
    out = perception.perception_outcome(ctx, nonce="n")
    views = out.get("views") or {}
    return views.get(str(cast[0]["id"])) or "", views.get("player") or ""


def _in_the_beat_half(view, *, after_act=True):
    """The sound is a sentence of its own, capitalised as the beat's
    events are, told after the act that made it; and not the lowercase
    standing sentence it used to be."""
    assert "A flat crack of musket fire." in view, view
    assert "a flat crack of musket fire" not in view, view
    if after_act:
        assert view.index("fires the musket") < view.index("A flat crack"), view


def test_a_sound_in_the_observers_own_room_is_told_with_the_beat(temp_db):
    """Wren stands in the meadow beside Pip: the shot is seen and its crack
    is told right after it, among the beat's events. The player's own view
    does not narrate the player's act back, so there the crack simply leads
    the beat."""
    cast, player = _outcome(temp_db, "meadow", (42, 3))
    _in_the_beat_half(cast)
    _in_the_beat_half(player, after_act=False)
    assert player.index("A flat crack") < player.index("You are in the meadow")


def test_a_sound_heard_from_the_next_room_is_told_with_the_beat(temp_db):
    """Wren in the pasture, sixty-odd metres off through the gap: the crack
    reaches her by the near field and is told with the beat, not as the air
    of the place."""
    cast, _player = _outcome(temp_db, "pasture", (40, 3))
    _in_the_beat_half(cast)
