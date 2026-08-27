"""A body that changed room must be graded from the room it is in.

Two independent sites in `agents/perception.py` graded a body from the room it
had LEFT, and both were firewall breaches: they delivered lines that crossed a
boundary as if no boundary had been crossed.

(a) The action-onset pass resolved the player's room against the scene as
    STORED, and merged the player's own asserted state -- a declared step into
    the next room among it -- onto a copy fourteen lines later. Every
    `spatial_rel_between(..., target_room=p_room)` after that graded her from
    the old room while the same scene said she stood in the new one, so one
    observer's view carried her presence in the room she had entered AND her
    lines as co-present in the room she had left.

(b) The outcome pass's beat-start rescue in `_source_channels` fired on the
    RELATION changing rather than on whose act changed it. It exists for a
    source whose act severs the channel it is seen through -- a door slammed,
    a curtain drawn, a vehicle pulling away (chat 58 t27, pinned in
    `tests/test_perception_beat_transition.py`) -- but "visual then, none now"
    reads the same when the PERCEIVER is the one who walked out. She was
    handed her old room back for the whole beat with `same_room` true, so
    `line_hear_level` returned "full" and `speech_percept` emitted no `via`:
    four speeches arrived as unchannelled co-present voice from a room she was
    no longer in, and the narrator invented a display feed to explain them,
    two beats before any comm link existed.

Both fixes SUBTRACT. Nothing here grants a channel; each removes one the
perceiver's own relocation had already closed. The controls below pin what
must not change: a perceiver who neither entered nor left keeps the rescue,
and a perceiver elsewhere with a real comm channel still receives the line --
tagged with the channel that carried it.
"""

from __future__ import annotations

import json
import time

import pytest

from agents import composer
from agents.perception import (
    _body_relocated,
    _source_channels,
    _with_comm_channel,
)
from core.pipeline_context import ChatData, PipelineContext, TurnData
from story.character_schema import default_character_data, default_persona_data


PERCEIVER = "Perceiver"
SOURCE = "Source"
LINE = "Say it again."


def _two_rooms(barrier="closed_door", *, perceiver_room, source_room,
               comms=None):
    """Two rooms joined by one edge, and a body in each named place."""
    scene = {
        "rooms": {
            "room_a": {"name": "Room A", "desc": "", "adjacent": [
                {"to": "room_b", "barrier": barrier, "distance": "near"}]},
            "room_b": {"name": "Room B", "desc": "", "adjacent": [
                {"to": "room_a", "barrier": barrier, "distance": "near"}]},
        },
        "positions": {PERCEIVER: perceiver_room, SOURCE: source_room},
        "entities": {}, "attire": {}, "overlays": {},
    }
    if comms:
        scene["comms"] = comms
    return scene


LIVE_CHANNEL = {"link": {"live": True, "name": "the open channel",
                         "rooms": ["room_a", "room_b"]}}


def _sources(room="room_a"):
    return [{"name": SOURCE, "room": room}]


def _delivered(scene, rel, *, observer_room, volume="normal"):
    """One spoken line, through the exact path the outcome pass uses."""
    return composer.speech_percept(
        {"speaker": SOURCE, "exact_quote": LINE, "volume": volume},
        _with_comm_channel(scene, rel, speaker=SOURCE, observer=PERCEIVER,
                           observer_room=observer_room),
        PERCEIVER, display=SOURCE, can_see=False)


# --- (b) the rescue, and whose act closed the channel -----------------------

def test_the_perceiver_who_left_is_not_rescued_into_the_room_she_left():
    before = _two_rooms(perceiver_room="room_a", source_room="room_a")
    after = _two_rooms(perceiver_room="room_b", source_room="room_a")

    rel = _source_channels(after, PERCEIVER, "room_b", _sources(),
                           prev_sc=before)["spatial_to_sources"][SOURCE]

    assert rel.get("same_room") is not True
    assert "was_reachable_at_beat_start" not in rel


def test_a_line_from_the_room_she_left_is_not_unchannelled_co_present_voice():
    """The measured consequence, at the delivery seam it surfaced in.

    The rescued relation said `same_room`, which is what made
    `line_hear_level` return "full" and what suppressed `via` -- so the line
    arrived as a voice in the room, with nothing downstream able to tell it
    had crossed anything.
    """
    before = _two_rooms(perceiver_room="room_a", source_room="room_a")
    after = _two_rooms(perceiver_room="room_b", source_room="room_a")

    rel = _source_channels(after, PERCEIVER, "room_b", _sources(),
                           prev_sc=before)["spatial_to_sources"][SOURCE]
    percept = _delivered(after, rel, observer_room="room_b")

    assert percept is not None            # she is one room away, not deaf
    assert percept.data["level"] != "full"
    assert percept.fidelity == "fragment"
    assert "body" not in percept.data     # the full line is not hers to have
    assert "via" not in percept.data      # and no channel is invented for it


def test_a_perceiver_sealed_in_this_beat_is_not_rescued_either():
    """Relocation is not only a change of room. A body that shut itself
    inside something stands in the same room and is no longer in it for any
    perceptual purpose, so its own act closes the channel exactly as walking
    out does."""
    before = _two_rooms(perceiver_room="room_a", source_room="room_a")
    after = _two_rooms(perceiver_room="room_a", source_room="room_a")
    after["entities"] = {"container": {"name": "A Container"}}
    after["positions"]["container"] = "room_a"
    after["contained"] = {PERCEIVER: {"in": "container", "hidden": True}}

    rel = _source_channels(after, PERCEIVER, "room_a", _sources(),
                           prev_sc=before)["spatial_to_sources"][SOURCE]

    assert "was_reachable_at_beat_start" not in rel


# --- the controls: what must not change -------------------------------------

def test_a_source_whose_act_severed_the_channel_is_still_rescued():
    """The case the rescue was written for. The perceiver stood still and the
    SOURCE went where the channel does not reach."""
    before = _two_rooms(perceiver_room="room_a", source_room="room_a")
    after = _two_rooms(perceiver_room="room_a", source_room="room_b")

    rel = _source_channels(after, PERCEIVER, "room_a",
                           _sources("room_b"),
                           prev_sc=before)["spatial_to_sources"][SOURCE]

    assert rel.get("was_reachable_at_beat_start") is True


def test_a_beat_where_neither_body_moved_is_unchanged():
    """A third party shuts the door between two bodies that both stood still.
    Nobody relocated, so the transition is still preserved."""
    before = _two_rooms("open", perceiver_room="room_a", source_room="room_b")
    after = _two_rooms("wall", perceiver_room="room_a", source_room="room_b")

    rel = _source_channels(after, PERCEIVER, "room_a", _sources("room_b"),
                           prev_sc=before)["spatial_to_sources"][SOURCE]

    assert rel.get("was_reachable_at_beat_start") is True


def test_a_still_beat_is_byte_for_byte_what_it_was():
    """Nothing moved and nothing changed: the beat-start pass must be inert."""
    scene = _two_rooms(perceiver_room="room_a", source_room="room_a")

    assert _source_channels(scene, PERCEIVER, "room_a", _sources(),
                            prev_sc=scene) == \
        _source_channels(scene, PERCEIVER, "room_a", _sources())


def test_a_perceiver_elsewhere_all_beat_still_gets_her_via():
    """She began and ended in the other room, with a live channel between
    them. The line reaches her, and it reaches her AS a transmission."""
    scene = _two_rooms(perceiver_room="room_b", source_room="room_a",
                       comms=LIVE_CHANNEL)

    rel = _source_channels(scene, PERCEIVER, "room_b", _sources(),
                           prev_sc=scene)["spatial_to_sources"][SOURCE]
    percept = _delivered(scene, rel, observer_room="room_b")

    assert percept.data["level"] == "full"
    assert percept.data["via"] == "the open channel"


def test_a_perceiver_who_left_still_gets_her_via():
    """The two halves together: withdrawing the rescue does not take the line
    away from her, it takes away the claim that she was standing there to
    hear it. With a channel open she receives it in full -- named as
    transmitted, which is the fact the rescue was erasing."""
    before = _two_rooms(perceiver_room="room_a", source_room="room_a",
                        comms=LIVE_CHANNEL)
    after = _two_rooms(perceiver_room="room_b", source_room="room_a",
                       comms=LIVE_CHANNEL)

    rel = _source_channels(after, PERCEIVER, "room_b", _sources(),
                           prev_sc=before)["spatial_to_sources"][SOURCE]
    percept = _delivered(after, rel, observer_room="room_b")

    assert percept.data["level"] == "full"
    assert percept.data["via"] == "the open channel"


def test_relocation_is_not_asserted_from_silence():
    """An unplaced body has not been shown to have moved. The answer only ever
    withdraws a channel, so an unknown end must not withdraw one."""
    placed = _two_rooms(perceiver_room="room_a", source_room="room_a")
    unplaced = _two_rooms(perceiver_room="room_a", source_room="room_a")
    unplaced["positions"].pop(PERCEIVER)

    assert _body_relocated(unplaced, placed, PERCEIVER) is False
    assert _body_relocated(placed, unplaced, PERCEIVER) is False
    assert _body_relocated(None, placed, PERCEIVER) is False
    assert _body_relocated(placed, placed, PERCEIVER) is False


# --- (a) the onset pass resolves the player against the previewed scene -----

PLAYER = "Player"
OBSERVER = "Observer"


def _onset_ctx(temp_db, *, assertions=None, player_placed=True,
               cached_room=None):
    persona = default_persona_data(PLAYER)
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        (PLAYER, json.dumps(persona), "{}"))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Onset", "", time.time(), persona_id))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (OBSERVER, json.dumps(default_character_data(OBSERVER)), "{}",
         time.time(), "char_observer"))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"))

    scene = _two_rooms(perceiver_room="room_a", source_room="room_a")
    scene["positions"] = {OBSERVER: "room_a"}
    if player_placed:
        scene["positions"][PLAYER] = "room_a"
    scene["location"] = "somewhere"
    temp_db.wset(chat_id, "scene", scene)
    temp_db.wset(chat_id, "known", {OBSERVER: [PLAYER]})

    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Onset", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="",
                      created=time.time()),
        cast=cast, input="")
    if cached_room is not None:
        ctx["_player_room"] = cached_room
    ctx.director_interpret = {
        "action": {"attempt": "steps through", "visibility": "overt",
                   "conceal_from": [], "targets": [],
                   "commitment": "asserted"},
        "sequence": [{
            "type": "action", "attempt": "steps through",
            "observable": "steps through", "visibility": "overt",
            "conceal_from": [], "targets": [], "commitment": "asserted",
            "verb": "step", "stage": "immediate",
            "event_id": "turn:1:player:0:action",
        }],
        "speech": None, "speech_volume": "normal",
        "onset_state_assertions": assertions,
        "flow": {"reactors": [char_id]},
    }
    return ctx, char_id


def _captured_onset(ctx, monkeypatch):
    """Run pass 1 and return the scene and perceivers the composer was given.

    `resolver_calls` counts trips to `_resolve_player_room`, which is the one
    step of the ladder that can cost a model call.
    """
    import agents.perception as perception

    seen = {"resolver_calls": 0}
    real_resolver = perception._resolve_player_room

    def _fake(ctx_, sc, interp, perceivers, *args, **kwargs):
        seen["scene"] = sc
        seen["perceivers"] = perceivers
        return {"views": {}}

    def _counting_resolver(*args, **kwargs):
        seen["resolver_calls"] += 1
        return real_resolver(*args, **kwargs)

    monkeypatch.setattr(perception, "_composer_act", _fake)
    monkeypatch.setattr(perception, "_resolve_player_room",
                        _counting_resolver)
    perception.perception_act(ctx, nonce="n")
    return seen


def test_an_asserted_step_grades_the_player_from_the_room_she_entered(
        temp_db, monkeypatch):
    """Presence and channel are two readings of ONE scene. The observer who
    stayed behind may not be told she is standing next to him."""
    ctx, char_id = _onset_ctx(
        temp_db, assertions={"positions": {PLAYER: "room_b"}})
    seen = _captured_onset(ctx, monkeypatch)

    assert seen["scene"]["positions"][PLAYER] == "room_b"
    assert ctx["_player_room"] == "room_b"
    observer = seen["perceivers"][0]
    assert observer["name"] == OBSERVER
    assert observer["spatial_to_actor"].get("same_room") is not True


def test_a_beat_with_no_declared_move_is_unchanged(temp_db, monkeypatch):
    """The control: she neither entered nor left, so she is co-present with
    the observer exactly as before."""
    ctx, char_id = _onset_ctx(temp_db, assertions=None)
    seen = _captured_onset(ctx, monkeypatch)

    assert ctx["_player_room"] == "room_a"
    assert seen["perceivers"][0]["spatial_to_actor"].get("same_room") is True


def test_the_scene_answers_before_the_resolver_is_asked(temp_db, monkeypatch):
    """The ladder's first rung. Resolving costs a model call when the scene
    tracks no position, so a scene that DOES place the player must settle it
    without one."""
    ctx, char_id = _onset_ctx(
        temp_db, assertions={"positions": {PLAYER: "room_b"}})

    assert _captured_onset(ctx, monkeypatch)["resolver_calls"] == 0


def test_the_cached_room_still_stands_in_when_the_scene_tracks_none(
        temp_db, monkeypatch):
    """The fallback ladder, in order: the scene, then the cached room, then
    the resolver -- which may cost a model call and so is asked last. A scene
    that never placed the player must not start asking it."""
    ctx, char_id = _onset_ctx(temp_db, player_placed=False,
                              cached_room="room_a")
    seen = _captured_onset(ctx, monkeypatch)

    assert ctx["_player_room"] == "room_a"
    assert seen["resolver_calls"] == 0
    assert seen["perceivers"][0]["spatial_to_actor"].get("same_room") is True
