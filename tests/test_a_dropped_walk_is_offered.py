"""A walk another's declaration wrote is offered to the mind it would move.

Probe finding F16, the lighthouse story (job tmp `fixes/stories/control.db`,
chat 2, idx 9; `docs/design/DESIGN_THE_CAST_ACROSS_A_SKIP.md` § 0 and
§ 4.3.1). The player wrote "That night, when Elias comes down from the first
watch and sits across the table from her with his tea, Rhona looks up from
the log and says, quietly: ...". The interpret encoder filed the keeper's walk
as his own conduct (`source_entity_id` character:1) carried out from the
player's declaration, and `director_prose.a_walk_is_its_owners` dropped it
whole, as the owner's ruling of 2026-10-07 requires -- and recorded nothing:

  * no offer. `director.director_interpret` hands on as offers the refusals
    `conduct_is_its_owners` records, and that floor runs after this one, on
    events this one had already taken away (`authorial_offers: []`). The
    keeper answered from upstairs.
  * and the resolve was told it had happened. `already_happened` tells the
    resolve from the kept rows only when a refusal is on the record, so it
    handed on the interpret's prose, keeper walked down and seated, and the
    resolve wrote him down the stair and back up again.

The rule: a mind's conduct another's declaration wrote is never enacted. It
is OFFERED to that mind -- the walk the floor drops and the conduct riding
with it in that event -- in the offer shape a player-authored thought already
takes (`director_views._route_authorial_npc_beat`), with the event's own
surface about that mind as its words.
"""

from __future__ import annotations

import copy
import json
import time
import uuid

import pytest

import agents.director as director
from agents import director_prose
from agents.director_prose import a_walk_is_its_owners
from core.pipeline_context import ChatData, PipelineContext, TurnData
from story.character_schema import default_character_data, default_persona_data
from tests.director_fakes import _fake_agent

ELIAS, RHONA = "Elias Thorne", "Rhona Carrick"
INDEX = {"character:1": ELIAS, "persona:3": RHONA}
RAW = "turn:16:primary:raw"
INPUTS = [{"entity_id": "persona:3", "authority_mode": "world_author",
           "events": [{"event_id": RAW, "type": "raw_input"}]}]

#: The rooms of the lighthouse as checkpoint 9 holds them (the ones the beat
#: touches), and where everyone stood before idx 9: the player at the kitchen
#: table, the keeper up in the lamp room -- following her since turn 7, which
#: carries him only from a room he shares with her, so it carried nothing.
LIGHTHOUSE = {
    "rooms": {
        "kitchen": {"name": "The Kitchen", "adjacent": [
            {"to": "lamp_room", "barrier": "open"},
            {"to": "tower_hall", "barrier": "open"}]},
        "lamp_room": {"name": "The Lamp Room", "adjacent": [
            {"to": "kitchen", "barrier": "open"}]},
        "tower_hall": {"name": "The Hall", "adjacent": [
            {"to": "kitchen", "barrier": "open"}]},
    },
    "positions": {RHONA: "kitchen", ELIAS: "lamp_room"},
    "poses": {
        RHONA: {"posture": "seated", "support": "", "relative_to": "kitchen_table",
                "relation": "at", "constraint": "", "detail": ""},
        ELIAS: {"posture": "standing", "support": "floor",
                "relative_to": "lamp_pedestal", "relation": "at", "constraint": "",
                "detail": "standing beside the settled pedestal looking at the "
                          "cocked mechanism"},
    },
    "following": {ELIAS: {"target": RHONA, "since_turn": 7}},
    "entities": {}, "attire": {}, "overlays": {},
}

INPUT = ('That night, when Elias comes down from the first watch and sits across '
         'the table from her with his tea, Rhona looks up from the log and says, '
         'quietly: "You read that letter of yours twice the day I came, and put it '
         'away like it bit you. Bad news from the shore?"')
LINE = ("You read that letter of yours twice the day I came, and put it away like "
        "it bit you. Bad news from the shore?")
#: Idx 9's interpret prose, as stored.
PROSE = ("That night, after the first watch, Elias Thorne comes down the tower stair "
         "from the lamp room into the kitchen and sits at the kitchen table across "
         "from Rhona Carrick, the mug of tea at the table with him. Rhona Carrick is "
         "at the kitchen table with the station log open in front of her and the "
         "stiff envelope held in her hand. She looks up from the log and says, "
         f'quietly: "{LINE}"')
#: The surface of the keeper's walk, as idx 9's encoder wrote it.
COMES_DOWN = ("comes down the tower stair into the kitchen and sits at the kitchen "
              "table across from Rhona Carrick")


def _keeper_comes_down(him="character:1", raw=RAW):
    """Idx 9's first encoder event, verbatim (capture 185)."""
    return {
        "source_entity_id": him, "source_event_id": raw,
        "event": "Elias Thorne comes down the tower stair from the lamp room into "
                 "the kitchen and sits at the kitchen table across from Rhona Carrick.",
        "speech": False, "observable": COMES_DOWN,
        "targets": ["kitchen", "kitchen_table", RHONA], "seconds": 8,
        "movement": None, "commitment": "asserted", "item_names": [ELIAS],
        "transforms": [{"item": ELIAS, "patch": {
            "positions": {ELIAS: "kitchen"},
            "poses": {ELIAS: {"posture": "seated", "support": "bench",
                              "relative_to": RHONA, "relation": "across",
                              "constraint": "",
                              "detail": "sitting at the kitchen table across "
                                        "from Rhona Carrick"}}}}]}


def _she_looks_up(me="persona:3", raw=RAW):
    """Idx 9's second encoder event, verbatim."""
    return {
        "source_entity_id": me, "source_event_id": raw,
        "event": "Rhona Carrick looks up from the log.", "speech": False,
        "observable": "looks up from the log", "targets": [ELIAS], "look": ELIAS,
        "seconds": 2, "movement": None, "commitment": "asserted",
        "item_names": [RHONA],
        "transforms": [{"item": RHONA, "patch": {"poses": {RHONA: {
            "posture": "seated", "support": "kitchen_table", "relative_to": ELIAS,
            "relation": "across", "constraint": "",
            "detail": "at the kitchen table with the log open before her, "
                      "looking up"}}}}]}


def _she_asks(me="persona:3", raw=RAW):
    """Idx 9's third encoder event, verbatim."""
    return {
        "source_entity_id": me, "source_event_id": raw, "event": LINE,
        "speech": True, "observable": "", "targets": [ELIAS], "volume": "whisper",
        "vocal_affect": "neutral", "look": ELIAS, "seconds": 4, "movement": None,
        "commitment": "asserted", "item_names": [], "transforms": []}


def _floor(events, inputs=INPUTS, scene=None, index=INDEX):
    warnings, rows = [], []
    out = a_walk_is_its_owners(events, inputs, index,
                               copy.deepcopy(LIGHTHOUSE if scene is None else scene),
                               warn=warnings.append, refusals=rows)
    return out, rows, warnings


# ---------------------------------------------------------------------------
# The floor: every mind it keeps in its room is a refusal on the record
# ---------------------------------------------------------------------------

def test_the_keepers_walk_is_offered_to_him_in_its_own_surface():
    """Idx 9. The event is his own conduct, so it goes whole, as before, and
    its surface -- the outward motion alone, his sitting down included -- is
    what he is offered: never the player's text, and never his own name told
    back to him in the third person."""
    out, rows, warnings = _floor([_keeper_comes_down(), _she_looks_up(), _she_asks()])
    assert out == [_she_looks_up(), _she_asks()], "dropped whole, as the ruling holds"
    assert warnings and ELIAS in warnings[0]
    assert rows == [{"mind": "character:1", "name": ELIAS, "event": COMES_DOWN,
                     "offer": True, "to": "kitchen"}]


def test_his_follow_from_another_room_does_not_withhold_the_offer():
    """He stood following her since turn 7, from the lamp room. A follow
    carries a follower only from a room he shares with the one he follows
    (`director_movement._apply_following_movement`), so it would never have
    brought him down; the walk is his to take, and is offered."""
    _out, rows, _w = _floor([_keeper_comes_down()])
    assert LIGHTHOUSE["following"][ELIAS]["target"] == RHONA
    assert [row["offer"] for row in rows] == [True]


#: Idx 6: both at the kitchen table; the player climbs to the lamp room and
#: "finds Elias already in the lamp room with the crate from the Board open".
KITCHEN_TABLE = dict(copy.deepcopy(LIGHTHOUSE),
                     positions={RHONA: "kitchen", ELIAS: "kitchen"}, following={})


def _she_climbs_and_finds_him(his_pose=True):
    """Idx 6's second encoder event (capture of turn 13), trimmed to the two
    bodies: the player's own climb, with the keeper's room and pose written
    into her act."""
    poses = {RHONA: {"posture": "standing", "support": "floor",
                     "relative_to": ELIAS, "relation": "facing", "constraint": "",
                     "detail": "holding a stiff envelope with toolkit slung"}}
    if his_pose:
        poses[ELIAS] = {"posture": "standing", "support": "floor",
                        "relative_to": "work_bench", "relation": "at",
                        "constraint": "",
                        "detail": "standing in the lamp room beside the crate "
                                  "and clockwork"}
    return {
        "source_entity_id": "persona:3", "source_event_id": RAW,
        "event": "Rhona Carrick came up the Tower Stair from the kitchen into the "
                 "Lamp Room, the clockmaker's toolkit slung from her shoulder and "
                 "the stiff envelope in her hand, and found Elias Thorne already there.",
        "observable": "climbs the tower stair from the kitchen into the lamp room",
        "speech": False, "targets": ["lamp_room", ELIAS], "seconds": 15,
        "movement": {"to_room": "lamp_room", "why": "inspect the clockwork",
                     "mover": RHONA, "arrives": True},
        "commitment": "asserted", "item_names": [RHONA, ELIAS, "poses"],
        "transforms": [
            {"item": RHONA, "patch": {"positions": {RHONA: "lamp_room",
                                                    ELIAS: "lamp_room"}}},
            {"item": "poses", "patch": {"poses": poses}}]}


def test_a_walk_written_into_the_players_act_is_offered_in_the_words_it_was_given():
    """Idx 6. Her climb is hers and stands. His room and the pose that placed
    him there leave the event together: the pose was read back to him in the
    kitchen by his own view as "standing in the lamp room beside the crate
    and clockwork". Her act is hers and is never offered to him; what he is
    offered is the words the event gave his own body there."""
    out, rows, warnings = _floor([_she_climbs_and_finds_him()], scene=KITCHEN_TABLE)
    assert warnings and ELIAS in warnings[0]
    patches = [t["patch"] for t in out[0]["transforms"]]
    assert {RHONA: "lamp_room"} == patches[0]["positions"]
    assert set(patches[1]["poses"]) == {RHONA}, "his pose went with his walk"
    assert out[0]["movement"]["mover"] == RHONA
    assert rows == [{"mind": "character:1", "name": ELIAS,
                     "event": "standing in the lamp room beside the crate and clockwork",
                     "offer": True, "to": "lamp_room"}]


def test_a_walk_with_no_words_of_its_own_is_offered_as_the_place():
    out, rows, _w = _floor([_she_climbs_and_finds_him(his_pose=False)],
                           scene=KITCHEN_TABLE)
    assert [(row["event"], row["offer"]) for row in rows] == [
        ("in The Lamp Room", True)]
    assert out[0]["transforms"][0]["patch"]["positions"] == {RHONA: "lamp_room"}


def test_a_room_said_again_is_no_walk_to_offer():
    """A position that only says again where a body stands is refused as it
    always was, but it walks nobody anywhere: no offer, and its pose -- no
    destination's -- stays."""
    finds = _she_climbs_and_finds_him()
    finds["transforms"][0]["patch"]["positions"][ELIAS] = "kitchen"
    out, rows, _w = _floor([finds], scene=KITCHEN_TABLE)
    assert [row["offer"] for row in rows] == [False]
    assert ELIAS in out[0]["transforms"][1]["patch"]["poses"]


def test_his_own_act_that_only_says_how_things_stand_is_no_offer():
    """The conduct floor's rule (`_restates_how_things_stand`), held for the
    walk floor's whole drops: a row that restates the scene offers nothing."""
    upstairs = _keeper_comes_down()
    upstairs["transforms"][0]["patch"] = {
        "positions": {ELIAS: "lamp_room"},
        "poses": {ELIAS: dict(LIGHTHOUSE["poses"][ELIAS])}}
    upstairs["observable"] = "stands at the pedestal"
    _out, rows, _w = _floor([upstairs])
    assert [row["offer"] for row in rows] == [False]


# ---------------------------------------------------------------------------
# What the floor already lets through is never offered
# ---------------------------------------------------------------------------

def test_a_hold_or_a_carry_still_moves_the_body_and_offers_nothing():
    grip = _she_climbs_and_finds_him()
    grip["transforms"].append({"item": RHONA, "patch": {"contact_ops": [
        {"op": "add", "actor": RHONA, "actor_part": "hand", "target": ELIAS,
         "target_part": "arm", "manner": "grip", "relation": "surface",
         "motion": "moving"}]}})
    out, rows, warnings = _floor([grip], scene=KITCHEN_TABLE)
    assert out == [grip] and rows == [] and warnings == []

    carried = dict(copy.deepcopy(KITCHEN_TABLE), contacts=[
        {"actor": RHONA, "target": ELIAS, "manner": "carry"}])
    out, rows, warnings = _floor([_she_climbs_and_finds_him()], scene=carried)
    assert out == [_she_climbs_and_finds_him()] and rows == [] and warnings == []

    inside = dict(copy.deepcopy(KITCHEN_TABLE), contained={ELIAS: {"in": RHONA}})
    out, rows, _w = _floor([_she_climbs_and_finds_him()], scene=inside)
    assert rows == []


def test_a_follow_the_floor_keeps_offers_nothing():
    """A follow op on the follower's own declaration stands, and so does a
    figure's (`_follows_of_the_declarer`); neither is a refusal."""
    his = [{"entity_id": "character:1", "authority_mode": "autonomous",
            "events": [{"event_id": "turn:16:character:1:0:action",
                        "type": "action"}]}]
    falls_in = {"source_entity_id": "character:1",
                "source_event_id": "turn:16:character:1:0:action",
                "event": "Elias Thorne falls in behind Rhona Carrick.",
                "observable": "falls in behind her", "movement": None,
                "transforms": [{"item": ELIAS, "patch": {"following_ops": [
                    {"op": "start", "follower": ELIAS, "target": RHONA}]}}]}
    figure = {"source_entity_id": "persona:3", "source_event_id": RAW,
              "event": "The boy from the mainland falls in behind her.",
              "movement": None,
              "transforms": [{"item": "the boy", "patch": {"following_ops": [
                  {"op": "start", "follower": "the boy", "target": RHONA}]}}]}
    index = dict(INDEX, **{"the boy": "the boy"})
    out, rows, warnings = _floor([falls_in], inputs=his, index=index)
    assert out == [falls_in] and rows == [] and warnings == []
    out, rows, warnings = _floor([figure], index=index)
    assert out == [figure] and rows == [] and warnings == []


def test_a_players_walk_is_never_offered_to_anyone():
    """Scratch story 166 turn 4587's shape: the pilot's declaration walked
    the player off the landing stage. Refused and recorded, offered to no one
    -- a player's body goes where the player's own input takes it, and the
    walk is not the pilot's to be handed. Her own walk is no refusal at all."""
    tamsin, hester = "Tamsin Coyle", "Hester Gale"
    act = "turn:9:character:81:2:action"
    inputs = [{"entity_id": "character:81", "authority_mode": "autonomous",
               "events": [{"event_id": act, "type": "action"}]}]
    walked = {"source_entity_id": "persona:21", "source_event_id": act,
              "event": f"{tamsin} falls in beside {hester}.",
              "observable": "falls in beside her",
              "movement": {"to_room": "low_walk", "mover": tamsin},
              "transforms": [{"item": tamsin, "patch": {
                  "positions": {tamsin: "low_walk"}}}]}
    index = {"persona:21": tamsin, "character:81": hester}
    out, rows, _w = _floor([walked], inputs=inputs, scene={}, index=index)
    assert out == []
    assert [(row["mind"], row["offer"]) for row in rows] == [("persona:21", False)]

    hers = dict(walked, source_event_id=RAW)
    out, rows, warnings = _floor(
        [hers], scene={}, index=index,
        inputs=[{"entity_id": "persona:21", "authority_mode": "world_author",
                 "events": [{"event_id": RAW, "type": "raw_input"}]}])
    assert out == [hers] and rows == [] and warnings == []


def test_a_walk_offers_its_mind_once():
    twice = [_keeper_comes_down(), _keeper_comes_down()]
    _out, rows, _w = _floor(twice)
    assert [row["event"] for row in rows] == [COMES_DOWN]


# ---------------------------------------------------------------------------
# End to end: the interpretation the beat is built from
# ---------------------------------------------------------------------------

def _lighthouse(temp_db, player_input=INPUT):
    """The probe's chat in miniature: the player Rhona Carrick, the keeper
    Elias Thorne, idx 9's world."""
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        (RHONA, json.dumps(default_persona_data(RHONA)), "{}"))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Skerry Light", "", time.time(), persona_id))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (ELIAS, json.dumps(default_character_data(ELIAS)), "{}", time.time(),
         f"char_elias_{uuid.uuid4().hex[:8]}"))
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
               "VALUES(?,?,?,?)", (chat_id, char_id, "active", "{}"))
    temp_db.wset(chat_id, "scene", copy.deepcopy(LIGHTHOUSE))
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 9, player_input, time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Skerry Light", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=9,
                      player_input=player_input, created=time.time()),
        cast=cast, input=player_input)
    return ctx, f"persona:{persona_id}", char_id


def _interpret(ctx, monkeypatch, events, prose=PROSE):
    monkeypatch.setattr(director, "_agent_json", _fake_agent([], {
        "director_prose": {"prose": prose},
        "director_specialist": {"events": events},
    }))
    out = director.director_interpret(ctx, nonce=0)
    ctx.director_interpret = out
    return out


@pytest.mark.usefixtures("prose_director")
def test_the_probes_beat_offers_the_keeper_his_walk(temp_db, monkeypatch):
    ctx, me, elias = _lighthouse(temp_db)
    raw = f"turn:{ctx.turn.id}:primary:raw"
    out = _interpret(ctx, monkeypatch, [
        _keeper_comes_down(f"character:{elias}", raw),
        _she_looks_up(me, raw), _she_asks(me, raw)])
    assert out["authorial_offers"] == [
        {"subject_id": elias, "proposition": COMES_DOWN, "source": "player"}]
    # ...offered, never enacted: he is in the lamp room until he walks.
    for key in ("state_assertions", "onset_state_assertions"):
        assert ELIAS not in json.dumps((out.get(key) or {}).get("positions") or {})
        assert "bench" not in json.dumps((out.get(key) or {}).get("poses") or {})
    assert {row.get("actor") for row in out["sequence"]} == {me}
    # ...and the resolve is not told he came down: the refusal is on the
    # record, so it is told from the rows the stage kept.
    told = director_prose.already_happened(ctx)
    assert "looks up from the log" in told
    assert "comes down" not in told and "tower stair" not in told


@pytest.mark.usefixtures("prose_director")
def test_a_thought_offer_still_reaches_its_mind_beside_a_walk(temp_db, monkeypatch):
    """The player-authored thought keeps its own route
    (`director_views._route_authorial_npc_beat`), and both reach him."""
    ctx, me, elias = _lighthouse(temp_db)
    raw = f"turn:{ctx.turn.id}:primary:raw"
    thinks = {"source_entity_id": me, "source_event_id": raw,
              "event": "Elias Thorne remembers the letter he put away.",
              "observable": "", "speech": False, "targets": [ELIAS],
              "movement": None, "commitment": "asserted", "item_names": [],
              "transforms": []}
    out = _interpret(ctx, monkeypatch, [
        _keeper_comes_down(f"character:{elias}", raw), thinks,
        _she_looks_up(me, raw), _she_asks(me, raw)])
    assert out["authorial_offers"] == [
        {"subject_id": elias, "proposition": thinks["event"], "source": "player"},
        {"subject_id": elias, "proposition": COMES_DOWN, "source": "player"}]


@pytest.mark.usefixtures("prose_director")
def test_a_walk_refused_at_resolve_is_recorded_and_offered_to_nobody(
        temp_db, monkeypatch):
    """Every character step of a beat runs before the resolve, and nothing
    after it reads an offer; and the resolve's identity index lists only the
    minds that declared, who keep their own walks -- so the only mind it can
    refuse is the player. Story 166 turn 4587's shape: the keeper's own
    declared walk, written by the resolve with the player taken along."""
    ctx, me, elias = _lighthouse(temp_db, player_input=f'"{LINE}"')
    raw = f"turn:{ctx.turn.id}:primary:raw"
    act = f"turn:{ctx.turn.id}:character:{elias}:0:action"
    ctx.character_results[elias] = {
        "name": ELIAS,
        "sequence": [{"type": "action", "attempt": "goes up to the lamp room",
                      "observable": "goes up to the lamp room", "event_id": act,
                      "visibility": "overt", "conceal_from": []}]}

    def resolve_events(payload):
        his = [event.get("event_id") for entry in payload.get("event_inputs") or ()
               if entry.get("entity_id") == f"character:{elias}"
               for event in entry.get("events") or ()]
        assert his == [act], "the keeper's declaration is the resolve's input"
        return {"events": [{
            "source_entity_id": f"character:{elias}", "source_event_id": act,
            "event": "Elias Thorne goes up to the lamp room, Rhona Carrick with him.",
            "observable": "goes up to the lamp room", "speech": False,
            "movement": {"to_room": "lamp_room", "mover": ELIAS, "arrives": True},
            "commitment": "asserted", "item_names": [ELIAS, RHONA],
            "transforms": [{"item": ELIAS, "patch": {"positions": {
                ELIAS: "lamp_room", RHONA: "lamp_room"}}}]}]}

    staged = {"director_prose": [{"prose": PROSE.split(" She looks up")[0]
                                  + f' She says, quietly: "{LINE}"'},
                                 {"prose": "Elias Thorne goes up to the lamp room, "
                                           "Rhona Carrick with him."}],
              "director_specialist": [{"events": [_she_asks(me, raw)]},
                                      resolve_events]}

    def fake(role, step_key, system, payload, **kw):
        queue = staged.get(step_key) or []
        value = queue.pop(0) if queue else {}
        if callable(value):
            value = value(payload)
        return json.loads(json.dumps(value))

    monkeypatch.setattr(director, "_agent_json", fake)
    ctx.director_interpret = director.director_interpret(ctx, nonce=0)
    resolved = director.director_resolve(ctx, nonce=0)
    refused = resolved["orchestration"]["prose_contract"]["conduct_refused"]
    assert [(row["mind"], row["offer"]) for row in refused] == [(me, False)]
    assert not resolved.get("authorial_offers")
    assert resolved["state_diff"]["positions"].get(ELIAS) == "lamp_room"
    assert RHONA not in resolved["state_diff"]["positions"]
