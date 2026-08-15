"""An arriving presence must not be a ghost.

Live, chat 72 turn 47. The player had been ringing a hotel bell for four
beats. The Director finally brought somebody: a young man in a wrinkled
uniform stumbling out of the back office. He arrived in `cast_changes`
("young man", status "arrived") and in `positions` ("Sleepy Hotel Clerk"),
and in nothing else.

`track_background_presences` harvests candidates from `dialogue_log`
speakers, `state_diff.entities` with a non-inert kind, `director_establish`'s
top-level entities, and the background_react backstop's own line. A body
placed in a room by `positions` alone is none of those. So he became a name
in the position ledger with no presence record, no perception object and no
way to ever be picked to act -- `background_presences` for that story held
exactly one thing afterwards, and it was the sonic screwdriver.

The rule the file already states is "only structured fields commit already
trusts, never NER over prose". `positions` is such a field, and a stronger
one than most: it is the ledger the engine places bodies with.
"""

from __future__ import annotations

import json
import time

from character_schema import default_character_data
from commit import track_background_presences
from pipeline_context import ChatData, PipelineContext, TurnData


def _ctx(temp_db, resolve_out, *, scene=None):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Mara", json.dumps(default_character_data("Mara")), "{}",
         time.time(), "char_mara"))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"))
    temp_db.wset(chat_id, "scene", scene or {
        "location": "Hotel", "time": "night",
        "rooms": {"lobby": {"name": "Lobby", "adjacent": []}},
        "positions": {"The Stranger": "lobby", "Mara": "lobby"},
        "entities": {}, "attire": {}, "overlays": {}})
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 9, "ring", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=9,
                      player_input="ring", created=time.time()),
        cast=cast, input="ring")
    ctx.director_resolve = resolve_out
    return ctx


def test_a_body_the_beat_placed_in_a_room_is_tracked(temp_db):
    """The live shape: placed by `positions`, named nowhere else."""
    ctx = _ctx(temp_db, {
        "resolved_event": "A man in a wrinkled uniform steps into the lobby.",
        "dialogue_log": [],
        "state_diff": {"positions": {"Sleepy Hotel Clerk": "lobby"}},
    })

    track_background_presences(ctx, nonce=0)

    assert "Sleepy Hotel Clerk" in temp_db.wget(ctx.chat.id,
                                                "background_presences", {})


def test_the_arrival_takes_the_name_the_engine_places_it_under(temp_db):
    """`cast_changes.who` is a DESCRIPTION the model wrote ("young man");
    the `positions` key is the identity every other system keys on. Turn 47
    carried both for one figure, and tracking the description as well would
    have minted a second presence nobody could ever match to the first."""
    ctx = _ctx(temp_db, {
        "resolved_event": "A young man stumbles out of the back office.",
        "dialogue_log": [],
        "state_diff": {
            "cast_changes": [{"who": "young man", "status": "arrived",
                              "reason": "Came out after the bell."}],
            "positions": {"Sleepy Hotel Clerk": "lobby"},
        },
    })

    track_background_presences(ctx, nonce=0)

    tracked = temp_db.wget(ctx.chat.id, "background_presences", {})
    assert "Sleepy Hotel Clerk" in tracked
    assert "young man" not in tracked


def test_a_registered_character_is_never_tracked_as_a_presence(temp_db):
    """The roster floor, from the other direction: a cast member's position
    is written every beat and must never mint a shadow of them."""
    ctx = _ctx(temp_db, {
        "resolved_event": "Mara crosses the lobby.",
        "dialogue_log": [],
        "state_diff": {"positions": {"Mara": "lobby",
                                     "The Stranger": "lobby"}},
    })

    track_background_presences(ctx, nonce=0)

    tracked = temp_db.wget(ctx.chat.id, "background_presences", {})
    assert "Mara" not in tracked
    assert "The Stranger" not in tracked


def test_an_inert_entity_with_a_position_is_not_a_presence(temp_db):
    """A crate has a position too. The existing kind rule still decides:
    default to inclusion for anything agent-shaped, exclude the clearly
    inert -- a bare name with no entity def is agent-shaped by default,
    which is the same trade the entity harvest already makes."""
    ctx = _ctx(temp_db, {
        "resolved_event": "The crate sits by the door.",
        "dialogue_log": [],
        "state_diff": {
            "entities": {"crate": {"name": "Wooden Crate", "kind": "object"}},
            "positions": {"Wooden Crate": "lobby"},
        },
    })

    track_background_presences(ctx, nonce=0)

    assert "Wooden Crate" not in temp_db.wget(
        ctx.chat.id, "background_presences", {})
