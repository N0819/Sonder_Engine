"""A line is graded from where its speaker stood when they said it.

Live: chat 122 "The great debuging time travel story", turn 3 (2026-09-08).
The player answered two direct questions; the Doctor replied, turned, and
walked up the beach, all in one beat. Both of his lines and the player's own
were refused, and the page showed a man walking away from a conversation
without a word:

    speech_percept  The Doctor -> Hinami   refused    none via spatial; tier across
    act_percept     The Doctor -> Hinami   delivered  wheels around toward the dunes...
    speech_percept  The Doctor -> Hinami   refused    none via spatial; tier across
    speech_percept  Hinami -> The Doctor   refused    none via spatial; tier across

They never changed ROOMS -- `state_diff.positions` was empty. His STATION
moved, `sand_shelf` to `dune_foot`, and the replayed relation on the committed
scene reads `same_room: true, barrier: open, signal: 0.0029, noise: 0.81`: the
surf drowning a voice measured from a beach he had not been standing on when
he spoke.

THE PROOF THAT IT IS AN ORDERING FAULT AND NOT AN AUDIBILITY ONE is that the
player's own line got opposite verdicts inside one turn. `perception_act`
graded "Uhm.. You're in Okinawa?" `delivered / within_reach`;
`perception_outcome` re-graded that same line `refused / across`, because the
second pass composes the scene the commit will write and grades every event
against it. That composition is right for a STANDING fact -- the room she ends
in, the light there, the sand under her feet -- and an utterance is not one.

This is not a loosening of the firewall. The channel existed at the moment of
utterance, so grading at that moment is fixing the timestamp on the check, not
widening it; the same rule REFUSES a line shouted from the next room by
someone who then walks in, which the end-of-beat grading delivers today.
"""
from __future__ import annotations

import json
import time

import pytest

from agents.perception import perception_outcome
from core.pipeline_context import ChatData, PipelineContext, TurnData
from story.character_schema import (default_character_data,
                                    default_persona_data)
from world.spatial import (beat_movement_cuts, hear_level, moved_within_beat,
                           scene_as_of, spatial_rel_between)

STRAND = "tide_strand"
SHELF, DUNE = "sand_shelf", "dune_foot"


def _strand(doctor_at):
    """The Moonlit Strand, copied off chat 122's committed scene rather than
    invented: a 40m x 25m open rectangle, the shelf south and the dune foot
    east, and the surf standing at the west edge as a running audible source.
    The distance and the noise floor are the whole point -- an invented room
    grades both stations alike and proves nothing."""
    return {
        "location": "Okinawa", "time": "night",
        "rooms": {STRAND: {
            "name": "Moonlit Strand", "adjacent": [], "light": "dim",
            "size": "large", "exposure": "open", "shape": "rectangle",
            "extent": {"w": 40.0, "d": 25.0}, "sound": {"level": "faint"},
            "anchors": {
                SHELF: {"desc": "A flat stretch of packed sand.",
                        "dir": "s", "offset": 0.30434782608695654},
                "surf_line": {"desc": "The foaming edge of the water.",
                              "dir": "w"},
                DUNE: {"desc": "Soft dry sand at the foot of the dunes.",
                       "dir": "e"},
            },
        }},
        "positions": {"Hinami": STRAND, "The Doctor": STRAND,
                      "Ocean Surf": STRAND},
        "stations": {"Hinami": {"at": SHELF, "near": [], "cell": [7, 22]},
                     "The Doctor": {"at": doctor_at, "near": []},
                     "Ocean Surf": {"at": "surf_line", "near": []}},
        "entities": {"Ocean Surf": {
            "kind": "terrain", "name": "Ocean Surf",
            "description": "The dark swell breaking in a steady hiss of foam.",
            "sound_source": "audible", "state": {"running": True},
            "portable": False, "container": False, "interior_rooms": [],
        }},
        "attire": {}, "overlays": {}, "poses": {},
    }


BEFORE = _strand(SHELF)     # beside her, where both lines were spoken
AFTER = _strand(DUNE)       # up the beach, where the beat left him


def _stream():
    """His declaration's own order: answer, walk, answer again."""
    return [
        {"kind": "speech",
         "entry": {"speaker": "The Doctor",
                   "exact_quote": "Okinawa! Japan -- that's Earth!"}},
        {"kind": "action", "actor": "The Doctor",
         "attempt": "wheels around toward the dunes and sets off up the sand",
         "event": {"type": "action"}},
        {"kind": "speech",
         "entry": {"speaker": "The Doctor",
                   "exact_quote": "But here's the thing, Hinami: kitsune."}},
    ]


# ---------------------------------------------------------------------------
# The quantity
# ---------------------------------------------------------------------------

def test_a_station_move_is_a_move():
    """`positions` never changed; the station did, and every grader reads it."""
    assert moved_within_beat(BEFORE, AFTER) == {"The Doctor"}


def test_the_cut_is_the_movers_last_action():
    assert beat_movement_cuts(BEFORE, AFTER, _stream()) == {"The Doctor": 1}


def test_the_scene_before_the_cut_is_where_he_spoke_from():
    cuts = beat_movement_cuts(BEFORE, AFTER, _stream())
    assert scene_as_of(BEFORE, AFTER, cuts, 0)["stations"]["The Doctor"]["at"] == SHELF
    assert scene_as_of(BEFORE, AFTER, cuts, 1)["stations"]["The Doctor"]["at"] == DUNE
    assert scene_as_of(BEFORE, AFTER, cuts, 2)["stations"]["The Doctor"]["at"] == DUNE


def test_an_unmoved_beat_is_the_same_object():
    """The 65% of beats nobody crosses must pay nothing: no copy, no splice."""
    cuts = beat_movement_cuts(BEFORE, BEFORE, _stream())
    assert cuts == {}
    assert scene_as_of(BEFORE, BEFORE, cuts, 0) is BEFORE


def test_a_body_the_beat_placed_has_not_moved():
    """The false positive this found on its first full run: the composition
    lays background presences, charter bodies and minted entities into
    `positions` as PART of composing the beat, so a guard who had stood in
    that cell the whole time read as having crossed it -- and winding him back
    to "nowhere" unplaced him, so his line reached no view. Exactly the defect
    this change exists to remove, reintroduced by the change itself
    (tests/test_background_presence_channels.py caught it).

    No room before the beat, no cut: "nowhere" is not a place to return to.
    """
    before = {"positions": {"Hinami": STRAND}, "stations": {}}
    after = {"positions": {"Hinami": STRAND, "Site Guard": STRAND},
             "stations": {"Site Guard": {"at": DUNE}}}
    assert moved_within_beat(before, after) == set()


def test_a_cell_written_where_there_was_none_is_not_a_move():
    """The same class one field down. A cell is derived from the station
    anchor and the composition assigns one where a body had none, so a body
    that never stirred would be a mover on the beat its coordinates were first
    written."""
    before = {"positions": {"Hinami": STRAND},
              "stations": {"Hinami": {"at": SHELF}}}
    after = {"positions": {"Hinami": STRAND},
             "stations": {"Hinami": {"at": SHELF, "cell": [7, 22]}}}
    assert moved_within_beat(before, after) == set()
    # ...but two real cells that differ still separate two places.
    moved_cell = {"positions": {"Hinami": STRAND},
                  "stations": {"Hinami": {"at": SHELF, "cell": [1, 1]}}}
    assert moved_within_beat(moved_cell, {
        "positions": {"Hinami": STRAND},
        "stations": {"Hinami": {"at": SHELF, "cell": [30, 4]}}}) == {"Hinami"}


def test_a_body_moved_by_something_other_than_its_own_act_keeps_the_end_state():
    """Carried, projected by `following_ops`, or simply placed: nothing in the
    beat can be said to have moved it, so this function claims nothing."""
    assert beat_movement_cuts(BEFORE, AFTER, [
        {"kind": "speech", "entry": {"speaker": "The Doctor",
                                     "exact_quote": "Hello."}}]) == {}


# ---------------------------------------------------------------------------
# The verdict it decides
# ---------------------------------------------------------------------------

def test_the_two_positions_really_do_grade_differently():
    """The premise the whole fix rests on. If these agreed there would be no
    defect and no need for any of this."""
    beside = spatial_rel_between(BEFORE, "Hinami", "The Doctor")
    away = spatial_rel_between(AFTER, "Hinami", "The Doctor")
    assert hear_level(beside, "normal") == "full"
    # RECALIBRATED 2026-09-14: on the real ladder the committed scene's
    # `audible` surf is a kettle's worth of noise (50 dB(A) at a pace, 36
    # at Hinami's cell) and a real normal voice thirty paces off arrives at
    # 37.6 -- under the `full` margin and inside the fragment one. The line
    # is not delivered; it is caught in pieces. Before, on the compressed
    # ladder, the surf and the voice shared a rung and it was `none`.
    assert hear_level(away, "normal") == "fragment", (
        "chat 122's committed relation: same room, open barrier, and the "
        "surf's noise floor over a signal measured from the dune")


# ---------------------------------------------------------------------------
# End to end, through the stage that produced the live failure
# ---------------------------------------------------------------------------

def _beat(temp_db):
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        ("Hinami", json.dumps(default_persona_data("Hinami")), "{}"))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Time travel", "", time.time(), persona_id))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("The Doctor", json.dumps(default_character_data("The Doctor")),
         "{}", time.time(), "char_doctor"))
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
               "VALUES(?,?,?,?)", (chat_id, char_id, "active", "{}"))
    temp_db.wset(chat_id, "scene", BEFORE)
    temp_db.wset(chat_id, "known", {"Hinami": ["The Doctor"],
                                    "The Doctor": ["Hinami"]})
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 3, "You're in Okinawa?", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Time travel", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=3,
                      player_input="You're in Okinawa?", created=time.time()),
        cast=cast, input="You're in Okinawa?")
    ctx.director_interpret = {
        "sequence": [], "speech": None, "speech_volume": "normal",
        "action": None,
        "flow": {"reactors": [], "addressed_to": [], "authority_claims": [],
                 "resolution_flags": {}, "fiction_frame": {}},
    }
    # His declaration, in the order he made it, and the station the beat left
    # him at. This is exactly the pair chat 122 turn 3 committed.
    doctor_sequence = [
        {"type": "speech", "text": "Okinawa! Japan -- that's Earth!",
         "volume": "normal", "visibility": "overt",
         "event_id": "turn:1:character:1:0:speech"},
        {"type": "action",
         "attempt": "Turn toward the dunes and walk up the sand",
         "observable": "wheels around toward the dunes and sets off up the "
                       "damp sand",
         "visibility": "overt", "commitment": "asserted",
         "event_id": "turn:1:character:1:1:action"},
        {"type": "speech",
         "text": "But here's the thing, Hinami: kitsune.",
         "volume": "normal", "visibility": "overt",
         "event_id": "turn:1:character:1:2:speech"},
    ]
    # BOTH shapes, as a played beat carries them: `rounds` is the transcript
    # the stream binds its chronology from, and `character_results` is what
    # decides a character is a SOURCE for anybody's view at all.
    ctx["interaction_loop"] = {
        "rounds": [{"round": 0, "speaker_id": int(cast[0]["id"]),
                    "speaker": "The Doctor",
                    "result": {"sequence": doctor_sequence}}],
    }
    ctx.character_results[int(cast[0]["id"])] = {
        "sequence": doctor_sequence}
    ctx.director_resolve = {
        "resolved_event": "The Doctor answers and starts up the beach.",
        "dialogue_log": [
            {"speaker": "The Doctor",
             "exact_quote": "Okinawa! Japan -- that's Earth!",
             "volume": "normal"},
            {"speaker": "The Doctor",
             "exact_quote": "But here's the thing, Hinami: kitsune.",
             "volume": "normal"},
        ],
        "state_diff": {"stations": {"The Doctor": {"at": DUNE, "near": []}}},
    }
    ctx["background_react"] = {"fired": False, "name": None, "reactions": [],
                               "selected": [], "mode": "background_react"}
    return ctx


def test_a_line_between_two_moves_uses_the_intermediate_world(temp_db):
    from world.causality import compile_transforms
    from world.causal_program import program_from_history
    ctx = _beat(temp_db)
    sequence = ctx["interaction_loop"]["rounds"][0]["result"]["sequence"]
    sequence.append({"type": "action", "attempt": "returns to the shelf",
                     "observable": "walks back down to the shelf",
                     "event_id": "turn:1:character:1:3:action"})
    transforms = [
        {"chrono_id": 2, "item_id": 1, "patch": {"stations": {
            "The Doctor": {"at": DUNE, "near": []}}}},
        {"chrono_id": 4, "item_id": 1, "patch": {"stations": {
            "The Doctor": {"at": SHELF, "near": []}}}},
    ]
    diff, history, rejected = compile_transforms(transforms, allowed_channels=["stations"])
    assert not rejected
    diff["causal_steps"] = program_from_history(history, [
        {"chrono_id": i + 1, "event_id": row["event_id"]}
        for i, row in enumerate(sequence)])
    ctx.director_resolve["state_diff"] = diff
    out = perception_outcome(ctx, "n0")
    assert "Okinawa! Japan" in out["views"]["player"]
    assert "But here's the thing, Hinami: kitsune." not in out["views"]["player"]
    worlds = ctx["_composed_beat"].causal_worlds
    assert worlds[2]["before"]["stations"]["The Doctor"]["at"] == DUNE


def test_onset_also_reads_the_world_between_two_moves(temp_db):
    from agents.perception import perception_act
    from world.causality import compile_transforms
    from world.causal_program import program_from_history
    ctx = _beat(temp_db)
    sequence = [
        {"type": "action", "attempt": "walks up the beach", "observable": "walks up the beach",
         "event_id": "player:move:1", "commitment": "asserted"},
        {"type": "speech", "text": "Can you hear me up here?", "volume": "normal",
         "event_id": "player:speech:2"},
        {"type": "action", "attempt": "returns", "observable": "walks back down",
         "event_id": "player:move:3", "commitment": "asserted"},
    ]
    diff, history, _ = compile_transforms([
        {"chrono_id": 1, "item_id": 7, "patch": {"stations": {"Hinami": {"at": DUNE, "cell": [37, 10]}}}},
        {"chrono_id": 3, "item_id": 7, "patch": {"stations": {"Hinami": {"at": SHELF, "cell": [7, 22]}}}},
    ], allowed_channels=["stations"])
    diff["causal_steps"] = program_from_history(history, [
        {"chrono_id": i + 1, "event_id": row["event_id"]}
        for i, row in enumerate(sequence)], "interpret")
    ctx.director_interpret.update(sequence=sequence, state_assertions=diff)
    out = perception_act(ctx, "n0")
    other_views = [view for key, view in out["views"].items() if key != "player"]
    assert other_views
    assert all("Can you hear me up here?" not in view for view in other_views)


def test_split_resolve_spans_use_their_own_world_despite_a_shared_declaration(temp_db):
    from world.causality import compile_transforms
    from world.causal_program import program_from_history
    ctx = _beat(temp_db)
    sequence = ctx["interaction_loop"]["rounds"][0]["result"]["sequence"]
    resolved_rows = [dict(event) for event in sequence]
    resolved_rows.append({"type": "action", "observable": "walks back to the shelf"})
    source_id = "turn:1:character:1:whole"
    for n, event in enumerate(resolved_rows, 1):
        event.update(chrono_id=n, event_id=n, actor="The Doctor",
                     from_declaration=source_id)
    # One prose declaration contains the entire trip; resolve disassembles it.
    sequence[:] = [{"type": "action", "event_id": source_id,
                   "observable": "speaks, walks away, speaks again, and returns"}]
    diff, history, _ = compile_transforms([
        {"chrono_id": 2, "item_id": 1, "patch": {"stations": {
            "The Doctor": {"at": DUNE, "near": []}}}},
        {"chrono_id": 4, "item_id": 1, "patch": {"stations": {
            "The Doctor": {"at": SHELF, "near": []}}}},
    ], allowed_channels=["stations"])
    diff["causal_steps"] = program_from_history(history, resolved_rows)
    ctx.director_resolve.update(ledgers=[{}], sequence=resolved_rows, state_diff=diff)
    out = perception_outcome(ctx, "n0")
    assert "Okinawa! Japan" in out["views"]["player"]
    assert "But here's the thing, Hinami: kitsune." not in out["views"]["player"]


def test_a_gesture_between_opening_and_closing_a_door_is_seen(temp_db, monkeypatch):
    from agents import composer
    from tests.test_causal_program import program
    admitted = {}
    original = composer.act_percept

    def record(scene, event, observer, actor, rel, **kwargs):
        percept = original(scene, event, observer, actor, rel, **kwargs)
        if observer == "Hinami":
            admitted[event.get("event_id")] = percept
        return percept

    monkeypatch.setattr(composer, "act_percept", record)
    ctx = _beat(temp_db)
    rooms = {"hall": {"name": "Hall", "light": "lit", "adjacent": [
                {"to": "study", "barrier": "closed_door"}]},
             "study": {"name": "Study", "light": "lit", "adjacent": [
                {"to": "hall", "barrier": "closed_door"}]}}
    temp_db.wset(ctx.chat.id, "scene", {
        "rooms": rooms, "positions": {"Hinami": "hall", "The Doctor": "study"},
        "entities": {}, "stations": {}, "attire": {}})
    sequence = [{"type": "action", "observable": text, "attempt": text,
                 "visibility": "overt", "commitment": "asserted",
                 "event_id": f"door:{n}"}
                for n, text in enumerate(["opens the door", "raises two fingers", "closes the door"], 1)]
    ctx["interaction_loop"]["rounds"][0]["result"]["sequence"] = sequence
    ctx.character_results[int(ctx.cast[0]["id"])] = {"sequence": sequence}
    diff = program({"rooms": {"hall": {"adjacent": [{"to": "study", "barrier": "open_door"}]}}},
                   {},
                   {"rooms": {"hall": {"adjacent": [{"to": "study", "barrier": "closed_door"}]}}})
    diff["causal_steps"].insert(1, {"chrono_id": 2, "stage": "resolve", "patch": {}})
    for n, step in enumerate(diff["causal_steps"], 1):
        step["events"] = [f"door:{n}"]
    ctx.director_resolve = {"resolved_event": "He briefly opens the door and signals.",
                            "state_diff": diff, "dialogue_log": []}
    out = perception_outcome(ctx, "n0")
    # The distant doorway admits motion, not finger-level detail.
    assert admitted["door:2"].channel == "sight"
    assert admitted["door:1"] is None
    assert "moves" in out["views"]["player"]
    final = ctx["_composed_beat"].scene
    assert final["rooms"]["hall"]["adjacent"][0]["barrier"] == "closed_door"


def test_the_line_he_spoke_beside_her_reaches_her(temp_db):
    """The live failure, at the stage that produced it. Before this fix the
    player's view carried the walk and neither line."""
    out = perception_outcome(_beat(temp_db), "n0")
    view = (out["views"] or {}).get("player") or ""
    assert "Okinawa! Japan" in view, view


def test_the_line_he_spoke_from_up_the_beach_does_not(temp_db):
    """The other half, and the reason this is a correction rather than a
    loosening: the second line really was delivered from the dune, and the
    surf really does take it. A fix that delivered both would have bought
    the first line by throwing away the geometry.

    RECALIBRATED 2026-09-14: on the real ladder the surf takes the WORDS
    and leaves the pieces (`test_the_two_positions_really_do_grade_
    differently`), so the line arrives as something she cannot make out
    and never verbatim."""
    out = perception_outcome(_beat(temp_db), "n0")
    view = (out["views"] or {}).get("player") or ""
    assert "But here's the thing, Hinami: kitsune." not in view, view
    assert "cannot make out" in view, view


def test_the_dropped_line_says_so(temp_db):
    """`perception_outcome` raised ZERO warnings on the live beat while
    dropping three lines; the only alarm in the turn came from the narrator,
    after it had invented a replacement. A line that reaches no view is
    either a refusal worth stating or a fault, and silence cannot tell them
    apart.

    RECALIBRATED 2026-09-14: neither line is dropped any more -- the first
    arrives whole and the second in pieces -- so what this pins is the
    principle's other face: a line that DID reach a view files no
    "reached no view" warning. The dropped-line warning itself is pinned
    on a beat that still drops one
    (`test_played_scene_classes`, the Hob Tarry beat)."""
    ctx = _beat(temp_db)
    out = perception_outcome(ctx, "n0")
    view = (out["views"] or {}).get("player") or ""
    assert "Okinawa! Japan" in view and "cannot make out" in view, view
    assert not [w for w in (ctx.warnings or []) if "reached no view" in w], (
        ctx.warnings)


def test_a_gesture_made_after_she_left_the_room_is_not_seen_through_the_door(temp_db):
    """Sight is graded at the event's moment too. Scratch play 2026-09-14,
    chat 4 turn 2: the nurse walked from the sickroom to the scullery; the
    patient then clenched his fingers in the quilt; her view carried the
    gesture as SIGHT through a shut door and two rooms, because the
    beat-wide sight map says yes if either end of the beat could see."""
    ctx = _beat(temp_db)
    rooms = {
        "sickroom": {"name": "Sickroom", "light": "lit",
                     "adjacent": [{"to": "passage", "barrier": "closed_door"}]},
        "passage": {"name": "Passage", "light": "dim",
                    "adjacent": [{"to": "sickroom", "barrier": "closed_door"},
                                 {"to": "scullery", "barrier": "open_door"}]},
        "scullery": {"name": "Scullery", "light": "dim",
                     "adjacent": [{"to": "passage", "barrier": "open_door"}]},
    }
    before = {"rooms": rooms, "positions": {"Hinami": "sickroom",
                                             "The Doctor": "sickroom"},
              "stations": {}, "entities": {}, "orientation": {}, "poses": {},
              "attire": {}}
    temp_db.wset(ctx.chat.id, "scene", before)
    ctx.director_interpret["sequence"] = [{
        "type": "action", "attempt": "walks out to the scullery",
        "observable": "walks out to the scullery",
        "visibility": "overt", "commitment": "asserted",
        "event_id": "turn:1:player:0:action",
        "movement": {"to_room": "scullery", "mover": "Hinami", "arrives": True},
    }]
    ctx.director_interpret["movement"] = {
        "to_room": "scullery", "mover": "Hinami", "arrives": True}
    gesture = [{
        "type": "action", "attempt": "clench my fingers in the quilt",
        "observable": "clenches his fingers into the quilt and stares at the door",
        "visibility": "overt", "commitment": "asserted",
        "event_id": "turn:1:character:1:0:action"}]
    ctx["interaction_loop"]["rounds"][0]["result"]["sequence"] = gesture
    ctx.character_results[int(ctx.cast[0]["id"])] = {"sequence": gesture}
    ctx.director_resolve = {
        "resolved_event": "She goes to the scullery; he clenches the quilt.",
        "dialogue_log": [],
        "state_diff": {"positions": {"Hinami": "scullery"}},
    }
    out = perception_outcome(ctx, "n0")
    view = (out["views"] or {}).get("player") or ""
    assert "clenches his fingers" not in view, view
    assert "quilt" not in view, view
