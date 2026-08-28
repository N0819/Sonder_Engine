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

from story.character_schema import default_character_data
from persist.commit import (presence_name_items, presence_record_for,
                            track_background_presences)
from core.pipeline_context import ChatData, PipelineContext, TurnData


def _rec(presences, name):
    return presence_record_for(presences, name)[1]


def _names(presences):
    return {n for n, _ in presence_name_items(presences)}


_UID = [0]


def _ctx(temp_db, resolve_out, *, scene=None):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()))
    _UID[0] += 1
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Mara", json.dumps(default_character_data("Mara")), "{}",
         time.time(), "char_mara_%d" % _UID[0]))
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

    assert "Sleepy Hotel Clerk" in _names(
        temp_db.wget(ctx.chat.id, "background_presences", {}))


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
    assert "Sleepy Hotel Clerk" in _names(tracked)
    assert "young man" not in _names(tracked)


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


# --- a schema field name is not a room -----------------------------------

class TestASchemaFieldNameIsNotARoom:
    """Live, chat 72 turn 44. `state_diff.rooms` came back carrying
    `resolved_events` and `notes` alongside two real rooms, and the shape
    normalizer -- whose whole job is to coerce whatever arrives into the
    container downstream readers assume -- dutifully turned each into a room
    dict. The map for that story now has a room called `resolved_events`,
    blank-named, sitting adjacent to the hotel lobby.

    They are not typos. They are field names from the output shape the model
    was just asked to produce, which is a nesting slip a model makes and a
    thing the engine can recognise for certain: no fiction has a room called
    `resolved_events`, and the cost of being wrong is refusing to mint a room
    somebody would have had to name after a JSON key.
    """

    def test_output_field_names_are_refused_as_rooms(self):
        from agents.director import _normalize_diff_shape

        sd = _normalize_diff_shape({"rooms": {
            "resolved_events": {"name": "", "desc": "", "adjacent": []},
            "notes": {"name": "", "desc": "", "adjacent": []},
            "hotel_lobby": {"name": "Hotel Lobby", "desc": "Warm.",
                            "adjacent": []},
        }})

        assert set(sd["rooms"]) == {"hotel_lobby"}

    def test_a_real_room_that_merely_shares_a_word_is_kept(self):
        """The check is on the WHOLE id, not a substring: a story may well
        have a room called `notes_office` or `summary_hall`."""
        from agents.director import _normalize_diff_shape

        sd = _normalize_diff_shape({"rooms": {
            "notes_office": {"name": "Notes Office", "adjacent": []},
            "summary_hall": {"name": "Summary Hall", "adjacent": []},
        }})

        assert set(sd["rooms"]) == {"notes_office", "summary_hall"}


def test_the_whole_chain_closes_for_the_clerk_who_never_came(temp_db):
    """Chat 72, all four fixes on one path.

    Beat 1: the Director brings somebody, placing them by `positions` alone
    -- which used to make a ghost. Beat 2: the player rings again from the
    next room, and the presence must now be pickable from where they stand
    and must receive what they can actually hear.

    Written as one test because the failure was a CHAIN: any single link
    still broken gives an empty lobby, and each link passing in isolation
    is what let four beats of bell-ringing go unanswered.
    """
    from agents.background import _beat_for_presence
    from persist.commit import pick_background_reactors, track_background_presences

    scene = {
        "location": "Hotel", "time": "night",
        "rooms": {
            "lobby": {"name": "Lobby", "adjacent": [
                {"to": "office", "barrier": "open", "distance": "adjacent"}]},
            "office": {"name": "Back Office", "adjacent": [
                {"to": "lobby", "barrier": "open", "distance": "adjacent"}]},
        },
        "positions": {"The Stranger": "lobby"},
        "entities": {}, "attire": {}, "overlays": {},
    }

    # BEAT 1 -- he arrives, named only by the position ledger.
    ctx = _ctx(temp_db, {
        "resolved_event": "A man in a wrinkled uniform appears in the office "
                          "doorway, rubbing his eyes.",
        "dialogue_log": [],
        "state_diff": {"positions": {"Night Clerk": "office"}},
    }, scene=scene)
    track_background_presences(ctx, nonce=0)

    tracked = temp_db.wget(ctx.chat.id, "background_presences", {})
    assert "Night Clerk" in _names(tracked), "arrived and was never recorded"
    assert _rec(tracked, "Night Clerk")["sketch"]["station_room"] == "office"

    # BEAT 2 -- the player rings again AND asks for somebody ("clerk" is the
    # demand: since Part C standing at a post no longer qualifies by itself,
    # and the chat-72 player did in fact ask in as many words -- "someone
    # should be staffing it"). He is one open doorway away and must be
    # pickable from where he stands.
    beat = {
        "resolved_event": "The bell rings out across the lobby.",
        "dialogue_log": [{"speaker": "The Stranger",
                          "exact_quote": '"Is anyone there?"',
                          "volume": "normal"}],
    }
    ctx2 = _ctx(temp_db, beat, scene=scene)
    ctx2.input = "I ring again. Clerk? Somebody should be staffing this desk."
    temp_db.wset(ctx2.chat.id, "background_presences", tracked)

    assert pick_background_reactors(ctx2, beat, cap=1) == ["Night Clerk"], (
        "asked for from one open doorway away and still not offered the beat")

    # And what he is handed is what he can hear, not the omniscient frame.
    heard = _beat_for_presence(beat, scene, "office", "Night Clerk",
                               beat_room="lobby")
    assert "Is anyone there?" in heard
    assert "rings out across the lobby" not in heard
