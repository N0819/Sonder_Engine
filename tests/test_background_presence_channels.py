"""A background presence is a body in a room, and reaches an observer through
the same channels every other body does.

It did not. Two halves of one gap, both in `perception_outcome`'s merge of
`background_react`:

* Only a reaction carrying a `dialogue_log_entry` was collected, so a
  presence's ACT reached no observer at all. It travelled to the narrator's
  `event_order` alone -- the one delivery path that never asks whether the
  player could see it.
* Every presence collected was located with `cast_room`, which resolves most
  of them through the entity table but answers None for a presence the scene
  places nowhere and for one whose name two entities answer to (ambiguity
  resolves to nothing, deliberately -- `room_of`). `presence_room` is the
  resolver that also knows the sketch's station room, and the background stage
  now records the room it actually voiced each presence at.

A None room makes `spatial_rel_between` report "no known spatial channel
between these entities". Chat 78 t3 hit exactly that -- a cell with two
identically-named guard entities in it -- and the two stages disagreed about
what it means: perception failed CLOSED and delivered the guard's line to
nobody, while the narrator's own sight gate failed OPEN, resolving the unknown
room to the PLAYER'S room and rendering that guard's act as fact. One missing
answer, an over-denial and a leak on the same beat.
"""

from __future__ import annotations

import json
import time

from agents.perception import perception_outcome
from core.pipeline_context import ChatData, PipelineContext, TurnData
from story.character_schema import default_character_data

_QUOTE = "Maintain restraint and keep the door sealed."
_ACT = "checks the weapon's safety, then glances at the monitor"


def _ctx(temp_db, *, presence_room, player_room="cell"):
    """A player and one background presence, the presence positioned the way
    `track_background_presences` writes one: under a scene entity id, never
    under its display name."""
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Presence channels", "", time.time()))
    sheet = default_character_data("Reya")
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Reya", json.dumps(sheet), "{}", time.time(), "char_reya"))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"))
    temp_db.wset(chat_id, "scene", {
        "location": "Site", "time": "night",
        "rooms": {
            "cell": {"name": "Interview Cell", "adjacent": [], "light": "lit"},
            "observation": {"name": "Observation Room", "adjacent": [],
                            "light": "lit"},
        },
        "positions": {"The Stranger": player_room, "Reya": player_room,
                      "bg0001": presence_room},
        "entities": {"bg0001": {"name": "Site Guard", "kind": "person"}},
        "attire": {}, "overlays": {},
    })
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "hello", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Presence channels", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                      player_input="hello", created=time.time()),
        cast=cast, input="hello")
    ctx.director_interpret = {
        "sequence": [], "speech": None, "speech_volume": "normal",
        "action": None,
        "flow": {"reactors": [], "addressed_to": [], "authority_claims": [],
                 "resolution_flags": {}, "fiction_frame": {}},
    }
    ctx.director_resolve = {"resolved_event": "", "dialogue_log": [],
                            "state_diff": {}}
    ctx["background_react"] = {
        "fired": True, "name": "Site Guard",
        "reactions": [{
            "name": "Site Guard",
            "dialogue_log_entry": {
                "speaker": "Site Guard", "exact_quote": _QUOTE,
                "volume": "normal", "visibility": "overt", "conceal_from": [],
                "tone": "flat", "intended_target": None},
            "action": _ACT,
            "room": presence_room,
        }],
        "selected": ["Site Guard"],
        "mode": "scene_life:full",
    }
    return ctx


def test_a_co_present_presence_is_heard_and_seen(temp_db):
    view = perception_outcome(
        _ctx(temp_db, presence_room="cell"), "n0")["views"]["player"]
    assert _QUOTE in view
    assert "safety" in view
    # The body reached the player; its NAME did not. A presence has no more
    # claim to be recognised on sight than any other stranger.
    assert "Site Guard" not in view


def test_a_presence_two_entities_answer_to_still_reaches_the_player(temp_db):
    # The live shape: a cell with a guard at each of two corner stations, so
    # the scene holds two entities under one name and every name-keyed room
    # lookup correctly refuses to pick one. The presence is still standing in
    # the player's room, and the station its record was harvested at is what
    # says so.
    ctx = _ctx(temp_db, presence_room="cell")
    scene = temp_db.wget(ctx.chat.id, "scene", {})
    scene["entities"]["bg0002"] = {"name": "Site Guard", "kind": "person"}
    scene["positions"]["bg0002"] = "cell"
    temp_db.wset(ctx.chat.id, "scene", scene)
    temp_db.wset(ctx.chat.id, "background_presences",
                 {"Site Guard": {"sketch": {"station_room": "cell"}}})
    ctx["background_react"]["reactions"][0]["room"] = ""

    view = perception_outcome(ctx, "n0")["views"]["player"]
    assert _QUOTE in view
    assert "safety" in view


def test_a_presence_in_another_room_reaches_neither_channel(temp_db):
    view = perception_outcome(
        _ctx(temp_db, presence_room="observation"), "n0")["views"]["player"]
    assert _QUOTE not in view
    assert "safety" not in view


def test_an_unplaceable_presence_reaches_neither_channel(temp_db):
    # No position, no entity, no station room, and no room on the reaction:
    # nothing can say where this body is, so nothing may be delivered from it.
    ctx = _ctx(temp_db, presence_room="cell")
    scene = temp_db.wget(ctx.chat.id, "scene", {})
    scene["positions"].pop("bg0001")
    scene["entities"] = {}
    temp_db.wset(ctx.chat.id, "scene", scene)
    ctx["background_react"]["reactions"][0]["room"] = ""

    view = perception_outcome(ctx, "n0")["views"]["player"]
    assert _QUOTE not in view
    assert "safety" not in view
