"""WHAT MOVES BEHIND YOU IS HEARD ONLY OVER THE NOISE AT YOUR EAR.

The tavern probe (2026-10-20, chat 2, turns 3-5 by index): in a taproom
holding a few dozen people and a fiddler, the player's view said
"Something moves behind you." and then "Something moves to your left." on
three beats running -- the barman's routine acts behind his own bar, a rag
wiped along it and a walk round to the barrel rack, delivered by the act
percept's rear-arc rule as heard movement. Seven such lines reached three
listeners in three beats. In a quiet room someone moving behind you is
heard; in a crowd's din the ordinary movement of one body is not, and said
every beat it reads as a broken page.

The class: an act the observer cannot see is perceived as heard only where
its sound reaches the observer's ear over the noise there. An ordinary act
sounds no louder than its actor's own tread (`tread_events`' walk in the
walker's own room), graded against the noise at the listener's ear at the
margins every sound is heard by; an act that filed a sound event of its own
is heard as that sound and not told again as movement. Only ever a
subtraction: nothing here adds a percept.
"""

from __future__ import annotations

import json
import time

import agents.composer as composer
from world.spatial import (entity_arc, movement_heard_at_ear, proximity_rel,
                           sound_field)

ROOM = "taproom"
PLAYER = "Tamsin Reed"
BARMAN = "Hollis Crane"
CROWD = {"uid": "crowd:probe", "room_uid": ROOM, "band": "a few dozen"}


def _taproom():
    """The probe's shape, in a smaller taproom: the bar along its north
    wall, the player at a table toward the south facing south, the barman at
    the bar behind her, some five paces off and well out of reach."""
    return {
        "location": "The Gull and Anchor", "time": "night",
        "rooms": {ROOM: {
            "name": "The Gull and Anchor", "light": "bright",
            "exposure": "enclosed", "floor": "timber", "surface": "furnished",
            "extent": {"w": 9, "d": 6},
            "anchors": {"long_bar": {"desc": "the long bar", "dir": "n"},
                        "next_table": {"desc": "a square table", "dir": "s"}},
            "adjacent": []}},
        "positions": {PLAYER: ROOM, BARMAN: ROOM},
        "stations": {PLAYER: {"at": "next_table"},
                     BARMAN: {"at": "long_bar"}},
        "orientation": {PLAYER: {"facing": "s"}},
        "entities": {}, "attire": {}, "overlays": {}, "poses": {},
        "contained": {},
    }


def _act(scene, *, sound, own_sound=False, gait=None):
    return composer.act_percept(
        scene, {"event_id": "e1", "actor": BARMAN, "targets": []},
        PLAYER, BARMAN, {"same_room": True, "barrier": "open"},
        surface="drags a rag along the bar", display="the barman",
        can_see=False, sight="none", order_key=0,
        sound=sound, own_sound=own_sound, gait=gait)


def test_a_body_moving_behind_you_in_a_quiet_room_is_heard():
    """The rule PM5 built, kept: a few paces behind you in a quiet room a
    body's movement is heard -- that something moved, and where, never who
    and never what."""
    scene = _taproom()
    assert entity_arc(scene, PLAYER, BARMAN) == "rear", "not a blind spot"
    assert proximity_rel(scene, PLAYER, BARMAN) != "within_reach"
    field = sound_field(scene, PLAYER, room=ROOM)
    assert field is not None, "the room carries no geometry"
    assert movement_heard_at_ear(scene, PLAYER, field, BARMAN) != "none"
    percept = _act(scene, sound=field)
    assert percept is not None, "a quiet room lost the sound of a body"
    assert percept.channel == "hearing" and percept.data.get("unseen") is True
    assert percept.source_label == "" and "surface" not in percept.data
    line = composer.render_view([percept]).text
    assert "moves" in line and "rag" not in line and BARMAN not in line


def test_the_same_movement_in_a_crowds_din_is_not_heard():
    """A few dozen people talking fill the room at 68 dB; a walk's tread
    arrives a few paces off some thirty decibels under it. Nothing reaches
    the ear, so nothing is told."""
    scene = _taproom()
    field = sound_field(scene, PLAYER, room=ROOM, crowds=[CROWD])
    assert movement_heard_at_ear(scene, PLAYER, field, BARMAN) == "none"
    assert _act(scene, sound=field) is None


def test_a_run_behind_you_carries_where_a_walk_does_not_and_a_sneak_never():
    """The body's own gait is its sound -- `tread_events`' own three gaits:
    a run strikes some thirteen decibels over a walk, and a body moving so as
    not to be heard makes no tread in its own room at all. In a room loud
    with its own steady noise, short of a din (53 dB at her ear), the
    barman's walk behind her is lost and his run still carries."""
    scene = _taproom()
    scene["rooms"][ROOM]["sound"] = {"level": "audible",
                                     "detail": "a steady clatter of work"}
    field = sound_field(scene, PLAYER, room=ROOM)
    assert movement_heard_at_ear(scene, PLAYER, field, BARMAN) == "none"
    assert movement_heard_at_ear(scene, PLAYER, field, BARMAN,
                                 gait="run") != "none"
    assert _act(scene, sound=field) is None
    assert _act(scene, sound=field, gait="run") is not None
    quiet_scene = _taproom()
    quiet = sound_field(quiet_scene, PLAYER, room=ROOM)
    assert movement_heard_at_ear(quiet_scene, PLAYER, quiet, BARMAN,
                                 gait="sneak") == "none"
    assert _act(quiet_scene, sound=quiet, gait="sneak") is None


def test_an_act_that_filed_its_own_sound_is_told_as_that_sound_only():
    """A barrel tapped behind you is heard as the mallet's blows -- the
    beat's sound channel tells them -- and is not told a second time as
    something moving."""
    scene = _taproom()
    field = sound_field(scene, PLAYER, room=ROOM)
    assert _act(scene, sound=field, own_sound=True) is None


def test_without_a_field_the_rear_arc_is_heard_as_it_was():
    """A room the engine holds no geometry for has no noise to grade by:
    the percept stands exactly as it did (the hearing rule's fail-open)."""
    scene = _taproom()
    percept = _act(scene, sound=None)
    assert percept is not None and percept.data.get("unseen") is True


def test_a_sneak_is_heard_nowhere_field_or_not():
    """A sneak files no tread in its own room whatever the room is
    (`tread_events`), so a body creeping up behind you is not heard moving
    even where no field can grade the noise."""
    scene = _taproom()
    assert movement_heard_at_ear(scene, PLAYER, None, BARMAN,
                                 gait="sneak") == "none"
    assert _act(scene, sound=None, gait="sneak") is None


# ---------------------------------------------------------------------------
# The outcome pass, end to end: the barman's act behind the player
# ---------------------------------------------------------------------------

def _outcome(db, *, crowd, act, sounds=()):
    from agents import director, perception
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    from story.character_schema import (default_character_data,
                                        default_persona_data)
    from world.causal_program import program_from_history
    from world.causality import compile_transforms
    from world.crowds import CROWDS_WORLD_KEY
    persona_id = db.qi("INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
                       (PLAYER, json.dumps(default_persona_data(PLAYER)), "{}"))
    chat_id = db.qi("INSERT INTO chats(name,scenario,created,persona_id) "
                    "VALUES(?,?,?,?)", ("Gull", "", time.time(), persona_id))
    char_id = db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (BARMAN, json.dumps(default_character_data(BARMAN)), "{}",
         time.time(), "char_hollis_%d" % len(sounds) + ("_c" if crowd else "")))
    db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
          "VALUES(?,?,?,?)", (chat_id, char_id, "active", "{}"))
    db.wset(chat_id, "scene", _taproom())
    db.wset(chat_id, "known", {PLAYER: [BARMAN], BARMAN: [PLAYER]})
    if crowd:
        db.wset(chat_id, CROWDS_WORLD_KEY, [CROWD])
    cast = db.q("SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
                "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
                (chat_id,))
    turn_id = db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                    "VALUES(?,?,?,?)", (chat_id, 4, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Gull", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=4, player_input="",
                      created=time.time()),
        cast=cast, input="")
    ctx.director_interpret = {
        "sequence": [], "speech": None, "speech_volume": "normal",
        "action": None,
        "flow": {"reactors": [], "addressed_to": [], "authority_claims": [],
                 "resolution_flags": {}, "fiction_frame": {}}}
    sequence = [{"type": "action", "actor": BARMAN, "attempt": act,
                 "observable": act, "commitment": "asserted",
                 "visibility": "overt", "conceal_from": [], "targets": [],
                 "event_id": "hollis:0", "chrono_id": 1}]
    transforms = ([{"chrono_id": 1, "item_id": 1, "specialist": "objects",
                    "patch": {"sensory_events": list(sounds)}}]
                  if sounds else [])
    diff, history, rejected = compile_transforms(
        transforms, allowed_channels=["sensory_events"])
    assert rejected == []
    diff["causal_steps"] = program_from_history(history, sequence, "resolve")
    ctx["interaction_loop"] = {"rounds": [{
        "round": 0, "speaker_id": int(cast[0]["id"]), "speaker": BARMAN,
        "result": {"sequence": sequence}}]}
    ctx.character_results[int(cast[0]["id"])] = {"sequence": sequence}
    ctx.director_resolve = {
        "ledgers": [{}], "state_diff": diff,
        "sequence": [{**row, "from_declaration": row["event_id"]}
                     for row in sequence],
        "resolved_event": "The barman " + act + ".",
        "dialogue_log": [], "dialogue_order": []}
    ctx.director_resolve["beat_events"] = director.beat_event_ledger(
        ctx.director_resolve, ctx.director_interpret,
        [{"name": BARMAN, "sequence": sequence}])
    ctx["background_react"] = {"fired": False, "name": None, "reactions": [],
                               "selected": [], "mode": "background_react"}
    return perception.perception_outcome(ctx, "n0")["views"]["player"]


def test_the_probe_beat_quiet_room_the_barman_is_heard_behind_you(temp_db):
    view = _outcome(temp_db, crowd=False, act="drags a rag along the bar")
    assert "Something moves" in view, view
    assert "rag" not in view, view


def test_the_probe_beat_in_the_din_nothing_moves_behind_you(temp_db):
    """The probe's turn, re-composed in its shape: a few dozen people in
    the room, the barman's rag behind the player, and her view no longer
    tells her that something moved."""
    view = _outcome(temp_db, crowd=True, act="drags a rag along the bar")
    assert "moves" not in view, view
    assert "rag" not in view, view


def test_the_probe_beat_a_barrel_tapped_behind_you_is_told_once(temp_db):
    """His act files the mallet's blows: the player hears them, and only
    them -- the sound is its own telling."""
    view = _outcome(temp_db, crowd=False,
                    act="drives a spile into the barrel with a mallet",
                    sounds=[{"kind": "sound", "room": ROOM, "level": "loud",
                             "source": BARMAN,
                             "detail": "three sharp blows of a mallet on a "
                                       "barrel"}])
    assert view.count("Three sharp blows of a mallet on a barrel.") == 1, view
    assert "Something moves" not in view, view


# ---------------------------------------------------------------------------
# The onset pass: the player's own act behind a cast member
# ---------------------------------------------------------------------------

def _onset(db, *, pace):
    from agents import perception
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    from story.character_schema import (default_character_data,
                                        default_persona_data)
    persona_id = db.qi("INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
                       (PLAYER, json.dumps(default_persona_data(PLAYER)), "{}"))
    chat_id = db.qi("INSERT INTO chats(name,scenario,created,persona_id) "
                    "VALUES(?,?,?,?)", ("Gull", "", time.time(), persona_id))
    char_id = db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (BARMAN, json.dumps(default_character_data(BARMAN)), "{}",
         time.time(), "char_hollis_onset_%s" % (pace or "walk")))
    db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
          "VALUES(?,?,?,?)", (chat_id, char_id, "active", "{}"))
    scene = _taproom()
    # He faces his shelves; she is at the table behind him.
    scene["orientation"] = {BARMAN: {"facing": "n"}}
    db.wset(chat_id, "scene", scene)
    db.wset(chat_id, "known", {PLAYER: [BARMAN], BARMAN: [PLAYER]})
    cast = db.q("SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
                "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
                (chat_id,))
    turn_id = db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                    "VALUES(?,?,?,?)", (chat_id, 4, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Gull", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=4, player_input="",
                      created=time.time()),
        cast=cast, input="")
    act = "shifts along the bench and gets to her feet"
    ctx.director_interpret = {
        "sequence": [{"type": "action", "attempt": act, "observable": act,
                      "visibility": "overt", "conceal_from": [],
                      "targets": [], "commitment": "asserted",
                      "event_id": "turn:4:player:0:action", "chrono_id": 1,
                      **({"movement": {"pace": pace}} if pace else {})}],
        "speech": None, "speech_volume": "normal", "action": None,
        "flow": {"reactors": [int(cast[0]["id"])], "addressed_to": [],
                 "authority_claims": [], "resolution_flags": {},
                 "fiction_frame": {}}}
    assert entity_arc(scene, BARMAN, PLAYER) == "rear", "not a blind spot"
    return perception.perception_act(ctx, "n0")["views"][str(cast[0]["id"])]


def test_at_onset_a_body_behind_you_is_heard_at_the_gait_its_act_declares(
        temp_db):
    """The player's own act at the onset, behind the barman in a quiet
    room: made at a walk it is heard as movement; made at a sneak -- the
    gait whose point is not to be heard -- it is not. The act's own
    `movement.pace` says which, before any travel record exists."""
    walked = _onset(temp_db, pace="")
    assert "Something moves" in walked, walked
    crept = _onset(temp_db, pace="sneak")
    assert "moves" not in crept, crept
    assert "bench" not in walked and "bench" not in crept


def test_an_acts_own_sound_is_found_by_its_step_never_by_its_number():
    """The resolve's diff carries the interpret's sounds too, and the two
    stages number their steps from 1 each: on the probe's idx 5 the
    player's call (interpret 2) and a turn of the heads at the bar
    (resolve 2) shared a number. The step that filed the sound says which
    act it was; a sound the beat no longer holds files nothing."""
    from agents.perception import _sound_filing_spans
    call = {"kind": "sound", "room": ROOM, "level": "loud",
            "source": PLAYER, "detail": "a voice calling across the room",
            "from_event": 2}
    diff = {"sensory_events": [call], "causal_steps": [
        {"stage": "interpret", "chrono_id": 2,
         "patch": {"sensory_events": [call]}},
        {"stage": "resolve", "chrono_id": 2,
         "patch": {"poses": {BARMAN: {"posture": "standing"}}}},
        {"stage": "resolve", "chrono_id": 3,
         "patch": {"sensory_events": [{**call, "from_event": 3}]}}]}
    delivered = [{**call, "_at": "2"}]
    assert _sound_filing_spans(diff, delivered) == {("interpret", "2")}
    assert _sound_filing_spans({}, delivered) == set()
