"""The account's framing and the world agree.

Three defects of one thread, measured on the lighthouse replayed on
2026-10-21's code (job tmp `fixes/live_skip/live_control.db`, chat 3; every
event below is the captured encoder answer, after its repair, before the
floors ran):

1. THE OFFER WAS TOO THIN TO TAKE UP (turn 26, idx 9). The player wrote
   "That night, when Elias comes down from the first watch and sits across
   the table from her with his tea, Rhona looks up from the log and says,
   quietly: ...". The interpret encoder wrote the keeper's walk and his
   sitting down as two events, both filed under the player
   (`source_entity_id` persona:3). `director_prose.a_walk_is_its_owners`
   rightly kept him upstairs, but read the walk as the player's act with his
   walk written into it, and offered him the place alone: "in The Kitchen".
   The sitting down, no walk, was never that floor's, and stood.
2. THE RESOLVE AND THE NARRATOR PUT HIM AT THE TABLE ANYWAY. Both events
   stayed the player's. `already_happened` told the resolve "Elias Thorne
   comes down the Tower Stair ... Elias Thorne sits at the kitchen table
   across from Rhona Carrick", and the resolve wrote "He sits at the kitchen
   table with the mug of tea gone cold at his elbow" while his own
   declaration was timing the lamp upstairs. The narrator was handed both as
   HER acts (`current_events`: actor Rhona Carrick, "comes down the Tower
   Stair into the kitchen"), and walked her down the Tower Stair. Neither
   invented it; the interpretation told them. And the resolve was shown
   where the keeper stood but not where she did: her room was in no
   declarer's aperture.
3. THE PLAYER'S OWN ACCOUNT DID NOT MOVE HER (turn 25, idx 8). "Rhona keeps
   to the kitchen with the stove going and the log open on the table" was
   encoded as "Rhona Carrick sits to the open station log at the kitchen
   table", `entities` and `inventory_ops` -- the log onto `kitchen_table` --
   and no position: the decision model had answered the positions question
   0.18 without being told where anyone started. She stayed in the hall, and
   the log was stood "where the beat is". At turn 26 the encoder did write
   her into the kitchen, inside the keeper's event, and the repair removed
   it ("Rhona was already seated in the kitchen") -- her own pose at the
   kitchen bench and table stood in the hall.
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
from llm import decisions
from story.character_schema import default_character_data, default_persona_data
from tests.director_fakes import _fake_agent

ELIAS, RHONA = "Elias Thorne", "Rhona Carrick"
INDEX = {"character:1": ELIAS, "persona:3": RHONA}
RAW = "turn:26:primary:raw"
INPUTS = [{"entity_id": "persona:3", "authority_mode": "world_author",
           "events": [{"event_id": RAW, "type": "raw_input"}]}]


def _anchors(*ids):
    return {aid: {"desc": aid.replace("_", " "), "dir": "n", "height": "waist",
                  "footprint": "small"} for aid in ids}


#: The lighthouse's rooms as checkpoint 9 holds them (the four the two beats
#: touch), with their own fixtures: a stair foot and a row of pegs stand in
#: both the hall and the kitchen, as they do there.
ROOMS = {
    "tower_hall": {"name": "The Hall", "level": 1,
                   "anchors": _anchors("hall_table", "pegs", "stair_foot", "stove"),
                   "adjacent": [{"to": "the_stair", "barrier": "open_door"},
                                {"to": "kitchen", "barrier": "open", "vertical": "up",
                                 "way": "stair"}]},
    "kitchen": {"name": "The Kitchen", "level": 2,
                "anchors": _anchors("range", "kitchen_table", "bench", "dresser",
                                    "stair_foot", "pegs"),
                "adjacent": [{"to": "tower_hall", "barrier": "open", "vertical": "down",
                              "way": "stair"},
                             {"to": "lamp_room", "barrier": "open", "vertical": "up",
                              "way": "stair"}]},
    "lamp_room": {"name": "The Lamp Room", "level": 3,
                  "anchors": _anchors("lamp_pedestal", "work_bench", "rail",
                                      "stair_head"),
                  "adjacent": [{"to": "kitchen", "barrier": "open", "vertical": "down",
                                "way": "stair"}]},
    "the_stair": {"name": "The Steps", "level": 1,
                  "anchors": _anchors("ledge", "handrail"),
                  "adjacent": [{"to": "tower_hall", "barrier": "open_door"}]},
}

#: Checkpoint 9 (the world before turn 26): the player still in the hall,
#: where turn 25 left her; the keeper at the lamp pedestal; the log stood in
#: the hall "where the beat is".
BEFORE_26 = {
    "rooms": ROOMS,
    "positions": {RHONA: "tower_hall", ELIAS: "lamp_room",
                  "station_log": "tower_hall", "d6dd266e31074860": "kitchen"},
    "poses": {RHONA: {"posture": "standing", "support": "floor",
                      "relative_to": "stair_foot", "relation": "at",
                      "constraint": "", "detail": "at the foot of the tower stair"}},
    "stations": {ELIAS: {"at": "lamp_pedestal", "near": []}},
    "entities": {"station_log": {"name": "the station log"},
                 "d6dd266e31074860": {"name": "a folded letter"}},
    "attire": {}, "overlays": {}, "contacts": [], "contained": {},
}

#: Checkpoint 8 (the world before turn 25): the same, without the log.
BEFORE_25 = dict(copy.deepcopy(BEFORE_26),
                 positions={RHONA: "tower_hall", ELIAS: "lamp_room",
                            "d6dd266e31074860": "kitchen"},
                 entities={"d6dd266e31074860": {"name": "a folded letter"}})

COMES_DOWN = "comes down the Tower Stair into the kitchen"
SITS = "sits at the kitchen table across from Rhona Carrick"


def _he_comes_down(src="persona:3", raw=RAW):
    """Turn 26's first event (capture 204), after the repair took out the
    player's and the log's positions it also carried."""
    return {
        "source_entity_id": src, "source_event_id": raw,
        "event": "Elias Thorne comes down the Tower Stair from the lamp room into "
                 "the kitchen.",
        "observable": COMES_DOWN, "speech": False, "targets": ["kitchen"],
        "seconds": 15, "movement": None, "commitment": "asserted",
        "item_names": [ELIAS, RHONA, "the station log"],
        "transforms": [{"item": ELIAS, "patch": {"positions": {ELIAS: "kitchen"}}}]}


def _he_sits(src="persona:3", raw=RAW):
    """Turn 26's second event, verbatim: his sitting down, no walk in it."""
    return {
        "source_entity_id": src, "source_event_id": raw,
        "event": "Elias Thorne sits at the kitchen table across from Rhona Carrick, "
                 "his mug of tea with him.",
        "observable": SITS, "speech": False,
        "targets": ["kitchen_table", RHONA], "seconds": 5, "movement": None,
        "commitment": "asserted", "item_names": [ELIAS],
        "transforms": [{"item": ELIAS, "patch": {"poses": {ELIAS: {
            "posture": "seated", "support": "bench", "relative_to": RHONA,
            "relation": "across", "constraint": "",
            "detail": "seated at the kitchen table across from Rhona Carrick, "
                      "mug of tea with him"}}}}]}


def _she_sits(src="persona:3", raw=RAW):
    """Turn 26's third event, verbatim: the player's own pose at the kitchen
    bench and table."""
    return {
        "source_entity_id": src, "source_event_id": raw,
        "event": "Rhona Carrick sits at the table with the station log before her, "
                 "and the folded letter lies on the kitchen table between them.",
        "observable": "sits at the table with the station log before her",
        "speech": False,
        "targets": ["kitchen_table", "station_log", "d6dd266e31074860"],
        "seconds": 2, "movement": None, "commitment": "asserted",
        "item_names": [RHONA],
        "transforms": [{"item": RHONA, "patch": {"poses": {RHONA: {
            "posture": "seated", "support": "bench", "relative_to": "kitchen_table",
            "relation": "at", "constraint": "",
            "detail": "seated at the table with the station log before her"}}}}]}


def _she_looks_up(src="persona:3", raw=RAW):
    return {"source_entity_id": src, "source_event_id": raw,
            "event": "Rhona looks up from the log.", "observable": "looks up from the log",
            "speech": False, "targets": [ELIAS], "look": ELIAS, "seconds": 2,
            "movement": None, "commitment": "asserted", "item_names": [],
            "transforms": []}


LINE = ("You read that letter of yours twice the day I came, and put it away like "
        "it bit you. Bad news from the shore?")


def _she_asks(src="persona:3", raw=RAW):
    return {"source_entity_id": src, "source_event_id": raw, "event": LINE,
            "observable": "", "speech": True, "targets": [ELIAS], "volume": "quiet",
            "seconds": 4, "movement": None, "commitment": "asserted",
            "item_names": [], "transforms": []}


def _turn_26(src="persona:3", raw=RAW):
    return [_he_comes_down(src, raw), _he_sits(src, raw), _she_sits(src, raw),
            _she_looks_up(src, raw), _she_asks(src, raw)]


def _floor(events, scene=None, inputs=INPUTS, index=INDEX):
    warnings, rows = [], []
    out = a_walk_is_its_owners(copy.deepcopy(events), inputs, index,
                               copy.deepcopy(BEFORE_26 if scene is None else scene),
                               warn=warnings.append, refusals=rows)
    return out, rows, warnings


# ---------------------------------------------------------------------------
# 1. The offer: every act the account wrote for him, in its own words
# ---------------------------------------------------------------------------

def test_his_walk_filed_under_her_is_his_conduct_and_offered_in_its_own_words():
    """The walk is the one body the event writes, his, and it is not aimed
    at him: his conduct, whoever's declaration wrote it. Dropped whole, as
    his own would be, and offered in the event's own surface -- not the place
    alone."""
    out, rows, warnings = _floor([_he_comes_down(), _she_asks()])
    assert [e["event"] for e in out] == [LINE]
    assert rows == [{"mind": "character:1", "name": ELIAS, "event": COMES_DOWN,
                     "offer": True, "to": "kitchen"}]
    assert warnings and ELIAS in warnings[0]


def test_what_rode_with_the_refused_walk_goes_with_it_in_the_order_told():
    """His sitting down writes no walk, so the walk floor never saw it, and it
    stood: his own view, upstairs, told him he sat on the bench. Once his walk
    is refused, every act of his that a declaration not his own wrote goes the
    walk's way, offered after it in the order the account told them."""
    out, rows, _w = _floor(_turn_26())
    assert [e["event"] for e in out] == [e["event"] for e in _turn_26()[2:]]
    assert [(row["event"], row["offer"]) for row in rows] == [
        (COMES_DOWN, True), (SITS, True)]
    assert all(row["mind"] == "character:1" for row in rows)
    assert ELIAS not in json.dumps([e.get("transforms") for e in out])


def test_an_act_before_the_walk_rides_with_it_too():
    """In the order the account told it: an act written before the walk is
    offered before it."""
    out, rows, _w = _floor([_he_sits(), _he_comes_down(), _she_asks()])
    assert [e["event"] for e in out] == [LINE]
    assert [row["event"] for row in rows] == [SITS, COMES_DOWN]


def test_the_players_act_on_him_is_hers_and_never_his_to_be_offered():
    """An event aimed at him -- the encoder's own word for whom a step is
    done to, never the event's source -- is the declarer's act: it stays
    hers, and he is offered only what it says of his body, as before."""
    beckons = _he_comes_down()
    beckons.update(event="Rhona Carrick calls Elias Thorne down to the kitchen.",
                   observable="calls him down to the kitchen", targets=[ELIAS])
    out, rows, _w = _floor([beckons])
    assert [e["event"] for e in out] == [beckons["event"]]
    assert out[0]["transforms"] == []
    assert [row["event"] for row in rows] == ["in The Kitchen"]


def test_an_event_that_moves_two_bodies_is_no_one_minds_alone():
    """The encoder's first answer carried her walk in his event too: two
    bodies, so whose act it is cannot be read off it. His walk leaves it,
    hers stays, and the event's surface is offered to no one."""
    both = _he_comes_down()
    both["transforms"].append({"item": RHONA, "patch": {"positions": {RHONA: "kitchen"}}})
    out, rows, _w = _floor([both])
    assert [t["patch"] for t in out[0]["transforms"]] == [{"positions": {RHONA: "kitchen"}}]
    assert [row["event"] for row in rows] == ["in The Kitchen"]


def test_his_act_with_no_refused_walk_is_left_to_the_conduct_floor():
    """Only a mind this floor kept in its room has its other acts taken here."""
    out, rows, warnings = _floor([_he_sits(), _she_asks()])
    assert [e["event"] for e in out] == [_he_sits()["event"], LINE]
    assert rows == [] and warnings == []


def test_a_world_happening_that_moves_him_stays_the_worlds():
    """An event filed under no mind is the world's: its happening stands and
    only his walk leaves it, as before."""
    gust = _he_comes_down(src="world")
    gust.update(event="A gust drives Elias Thorne down the stair.",
                observable="the gust drives him down the stair", targets=[])
    out, rows, _w = _floor([gust])
    assert [e["event"] for e in out] == [gust["event"]]
    assert [row["event"] for row in rows] == ["in The Kitchen"]


# ---------------------------------------------------------------------------
# 1 and 2 end to end: the interpretation the beat is built from
# ---------------------------------------------------------------------------

def _lighthouse(temp_db, scene, player_input, idx=9):
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
    temp_db.wset(chat_id, "scene", copy.deepcopy(scene))
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, idx, player_input, time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Skerry Light", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=idx,
                      player_input=player_input, created=time.time()),
        cast=cast, input=player_input)
    return ctx, f"persona:{persona_id}", char_id


INPUT_26 = ('That night, when Elias comes down from the first watch and sits across '
            'the table from her with his tea, Rhona looks up from the log and says, '
            f'quietly: "{LINE}"')
#: Turn 26's interpret prose, as stored.
PROSE_26 = ("That night, after the first watch, Elias Thorne comes down the Tower "
            "Stair from the lamp room into the kitchen. He sits at the kitchen table "
            "across from Rhona Carrick, his mug of tea with him. Rhona Carrick sits "
            "at the table with the station log before her, and the folded letter "
            "lies on the kitchen table between them. She looks up from the log and "
            f'says, quietly: "{LINE}"')


def _interpret(ctx, monkeypatch, events, prose):
    monkeypatch.setattr(director, "_agent_json", _fake_agent([], {
        "director_prose": {"prose": prose},
        "director_specialist": {"events": events},
    }))
    out = director.director_interpret(ctx, nonce=0)
    ctx.director_interpret = out
    return out


@pytest.mark.usefixtures("prose_director")
def test_turn_26_offers_him_everything_he_was_written_doing(temp_db, monkeypatch):
    ctx, me, elias = _lighthouse(temp_db, BEFORE_26, INPUT_26)
    raw = f"turn:{ctx.turn.id}:primary:raw"
    out = _interpret(ctx, monkeypatch, _turn_26(me, raw), PROSE_26)
    assert out["authorial_offers"] == [
        {"subject_id": elias, "proposition": COMES_DOWN, "source": "player"},
        {"subject_id": elias, "proposition": SITS, "source": "player"}]
    # ...as his agent and the skip question read them, in that order.
    from agents.skip_stage import _offers_for
    assert _offers_for(out, elias) == [COMES_DOWN, SITS]
    # Offered, never enacted: upstairs, standing at his pedestal.
    for key in ("state_assertions", "onset_state_assertions"):
        assert ELIAS not in json.dumps((out.get(key) or {}).get("positions") or {})
        assert ELIAS not in json.dumps((out.get(key) or {}).get("poses") or {})


@pytest.mark.usefixtures("prose_director")
def test_turn_26_tells_the_resolve_and_the_narrator_only_what_happened(
        temp_db, monkeypatch):
    """Defect 2 at the stage where it began: neither the resolve's
    `already_happened` nor the player's sequence -- what the narrator's
    `player_declared` and `current_events` are built from -- carries his walk
    or his sitting down as anything that happened, and never as hers."""
    ctx, me, _elias = _lighthouse(temp_db, BEFORE_26, INPUT_26)
    raw = f"turn:{ctx.turn.id}:primary:raw"
    out = _interpret(ctx, monkeypatch, _turn_26(me, raw), PROSE_26)
    told = director_prose.already_happened(ctx)
    assert "looks up from the log" in told
    assert "Tower Stair" not in told and "his mug of tea" not in told
    surfaces = json.dumps(out["sequence"])
    assert COMES_DOWN not in surfaces and SITS not in surfaces
    from agents.narration import _narrator_player_declared
    declared = json.dumps(_narrator_player_declared(out))
    assert "Tower Stair" not in declared and "across from" not in declared


@pytest.mark.usefixtures("prose_director")
def test_the_resolve_is_shown_where_the_player_stands(temp_db, monkeypatch):
    """The keeper declared from the lamp room, and the resolve's world was
    the rooms in his aperture: the player's own room, where her input had
    just entered the world, was 'elsewhere', and nothing told the author
    where she stood. Her room is in the resolve's aperture like any actor's."""
    ctx, me, elias = _lighthouse(temp_db, BEFORE_26, f'"{LINE}"')
    raw = f"turn:{ctx.turn.id}:primary:raw"
    act = f"turn:{ctx.turn.id}:character:{elias}:0:action"
    ctx.character_results[elias] = {
        "name": ELIAS,
        "sequence": [{"type": "action", "attempt": "times the sweep against his watch",
                      "observable": "times the sweep against his watch",
                      "event_id": act, "visibility": "overt", "conceal_from": []}]}
    calls = []
    staged = {"director_prose": [{"prose": f'Rhona Carrick says, quietly: "{LINE}"'},
                                 {"prose": "Elias Thorne times the sweep."}],
              "director_specialist": [{"events": [_she_asks(me, raw)]},
                                      {"events": []}]}

    def fake(role, step_key, system, payload, **kw):
        calls.append({"step_key": step_key, "payload": payload})
        queue = staged.get(step_key) or []
        return json.loads(json.dumps(queue.pop(0) if queue else {}))

    monkeypatch.setattr(director, "_agent_json", fake)
    ctx.director_interpret = director.director_interpret(ctx, nonce=0)
    director.director_resolve(ctx, nonce=0)
    author = [c["payload"] for c in calls if c["step_key"] == "director_prose"][-1]
    assert author["standing_relations"]["positions"].get(RHONA) == "tower_hall"
    assert author["standing_relations"]["positions"].get(ELIAS) == "lamp_room"
    assert "tower_hall" in author["world_index"]["rooms"]


# ---------------------------------------------------------------------------
# 3. The player's own account places the player where it says
# ---------------------------------------------------------------------------

RAW_25 = "turn:25:primary:raw"
INPUTS_25 = [{"entity_id": "persona:3", "authority_mode": "world_author",
              "events": [{"event_id": RAW_25, "type": "raw_input"}]}]
INPUT_25 = ("Two days later the wind gets up from the west and the sea comes white "
            "over the rock all morning. Rhona keeps to the kitchen with the stove "
            "going and the log open on the table, writing up the trial of the new "
            "mechanism.")
#: Turn 25's interpret prose, as stored, but for the weather's sentence.
PROSE_25 = ("Two days pass. On the second morning the wind comes up out of the west "
            "and drives the sea white over the rock, and it stays white all morning. "
            "Rhona Carrick keeps to the kitchen. The station log lies open on the "
            "kitchen table, and she sits to it, writing up the trial of the new "
            "mechanism.")


def _two_days_pass(raw=RAW_25):
    return {"source_entity_id": "world", "source_event_id": raw,
            "event": "Two days pass.", "observable": "", "speech": False,
            "seconds": 0.0, "movement": None, "commitment": "asserted",
            "item_names": ["time"],
            "transforms": [{"item": "time", "patch": {"time": {
                "days": 2, "until_phase": "morning"}}}]}


def _she_writes_up_the_trial(src="persona:3", raw=RAW_25):
    """Turn 25's own event (capture 194), verbatim but for the log's long
    description: the log onto the kitchen table, and no position."""
    return {
        "source_entity_id": src, "source_event_id": raw,
        "event": "Rhona Carrick sits to the open station log at the kitchen table, "
                 "writing up the trial of the new mechanism.",
        "observable": "sits at the kitchen table writing in the open station log",
        "speech": False, "targets": ["kitchen_table"], "look": "kitchen_table",
        "seconds": 300.0, "movement": None, "commitment": "asserted",
        "item_names": ["station_log"],
        "transforms": [{"item": "station_log", "patch": {
            "entities": {"station_log": {"name": "the station log", "kind": "document",
                                         "portable": True}},
            "inventory_ops": [{"op": "transfer", "object_id": "station_log",
                               "to_id": "kitchen_table"}]}}]}


def _places(events, scene=None, inputs=INPUTS_25, index=INDEX):
    warnings = []
    out = director_prose.the_account_places_its_own_body(
        copy.deepcopy(events), inputs, index,
        copy.deepcopy(BEFORE_25 if scene is None else scene), warn=warnings.append)
    return out, warnings


def test_her_own_hands_at_the_kitchen_table_take_her_to_the_kitchen():
    """Turn 25: her own act sets the log on a fixture of the kitchen, and she
    stands in the hall. Her account places her there: her walk is written at
    that step, as her own, and nothing else of the beat changes."""
    events = [_two_days_pass(), _she_writes_up_the_trial()]
    out, warnings = _places(events)
    assert out[0] == events[0]
    assert out[1]["movement"] == {"to_room": "kitchen", "why": "", "mover": RHONA,
                                  "arrives": True, "to_anchor": "kitchen_table"}
    assert out[1]["transforms"][0] == {"item": RHONA,
                                       "patch": {"positions": {RHONA: "kitchen"}}}
    assert out[1]["transforms"][1:] == events[1]["transforms"]
    assert RHONA in out[1]["item_names"]
    assert warnings and "The Kitchen" in warnings[0]


def test_her_own_pose_at_the_kitchen_bench_takes_her_there():
    """Turn 26's own event: seated on the kitchen bench at the kitchen table,
    from the hall, the repair having taken her walk out."""
    out, _w = _places([_she_sits(raw=RAW_25)], scene=BEFORE_26)
    assert (out[0]["movement"] or {}).get("to_room") == "kitchen"
    assert out[0]["transforms"][0]["patch"] == {"positions": {RHONA: "kitchen"}}


def _posed_at(fixture, event):
    event["transforms"].append({"item": RHONA, "patch": {"poses": {RHONA: {
        "posture": "standing", "support": "floor", "relative_to": fixture,
        "relation": "at", "constraint": "", "detail": ""}}}})
    return event


def test_a_fixture_of_her_own_room_moves_her_nowhere():
    """A step that has her at a fixture of the room she stands in is not her
    account placing her elsewhere, whatever else it names: she reaches the
    other through its doorway, or the account is not plain."""
    at_home = _she_writes_up_the_trial()
    at_home["transforms"][0]["patch"]["inventory_ops"][0]["to_id"] = "hall_table"
    out, warnings = _places([at_home])
    assert out == [at_home] and warnings == []
    both = _posed_at("hall_table", _she_writes_up_the_trial())
    assert _places([both])[0] == [both]


def test_a_fixture_both_rooms_hold_is_read_in_hers():
    """The hall and the kitchen each have a stair foot: at hers, she is home."""
    stair = _posed_at("stair_foot", _she_writes_up_the_trial())
    assert _places([stair])[0] == [stair]


def test_an_account_that_already_walks_her_is_left_as_written():
    walks = _she_writes_up_the_trial()
    walks["movement"] = {"to_room": "kitchen", "mover": RHONA, "arrives": True}
    walks["transforms"].insert(0, {"item": RHONA, "patch": {
        "positions": {RHONA: "kitchen"}}})
    out, warnings = _places([walks])
    assert out == [walks] and warnings == []
    # ...even where the step names a fixture of a room it passes through:
    # the account's own walk is where she ends.
    on_the_way = copy.deepcopy(walks)
    on_the_way["movement"]["to_room"] = "lamp_room"
    on_the_way["transforms"][0]["patch"]["positions"][RHONA] = "lamp_room"
    out, warnings = _places([on_the_way])
    assert out == [on_the_way] and warnings == []
    # ...and a walk an earlier step wrote is where the later step stands.
    earlier = {"source_entity_id": "persona:3", "source_event_id": RAW_25,
               "event": "Rhona Carrick climbs to the kitchen.", "speech": False,
               "movement": {"to_room": "kitchen", "mover": RHONA, "arrives": True},
               "transforms": [{"item": RHONA, "patch": {"positions": {RHONA: "kitchen"}}}]}
    out, warnings = _places([earlier, _she_writes_up_the_trial()])
    assert out[1] == _she_writes_up_the_trial() and warnings == []


def test_a_walk_still_under_way_has_not_put_her_there():
    """Her own walk toward the kitchen that does not arrive this step leaves
    her where she was; her next step at the kitchen table is where she gets
    there."""
    sets_off = {"source_entity_id": "persona:3", "source_event_id": RAW_25,
                "event": "Rhona Carrick starts up the stair to the kitchen.",
                "speech": False, "transforms": [],
                "movement": {"to_room": "kitchen", "mover": RHONA, "arrives": False}}
    out, _w = _places([sets_off, _she_writes_up_the_trial()])
    assert out[0] == sets_off
    assert (out[1]["movement"] or {}).get("to_room") == "kitchen"


def test_a_fact_about_how_things_stand_places_her_and_walks_her_nowhere():
    """A standing event is performed by nobody (`UnifiedEvent.standing`): her
    own account's correction of where she is writes the room, never a walk."""
    stands = _she_writes_up_the_trial()
    stands["standing"] = True
    out, _w = _places([stands])
    assert out[0]["transforms"][0]["patch"] == {"positions": {RHONA: "kitchen"}}
    assert out[0]["movement"] is None


def test_a_walk_another_player_wrote_for_her_is_not_where_she_stands():
    """Another player's declaration that walks her is the walk floor's to
    refuse, so it leaves her where she stood; her own account then places
    her by her own step."""
    mara = "Mara Venn"
    theirs = "turn:25:extra:4:raw"
    inputs = INPUTS_25 + [{"entity_id": "persona:4", "authority_mode": "world_author",
                           "events": [{"event_id": theirs, "type": "raw_input"}]}]
    index = dict(INDEX, **{"persona:4": mara})
    hauls = {"source_entity_id": "persona:4", "source_event_id": theirs,
             "event": "Mara Venn hauls Rhona Carrick up to the kitchen.", "speech": False,
             "movement": None, "targets": [RHONA],
             "transforms": [{"item": RHONA, "patch": {"positions": {RHONA: "kitchen"}}}]}
    out, _w = _places([hauls, _she_writes_up_the_trial()], inputs=inputs, index=index)
    assert out[0] == hauls
    assert (out[1]["movement"] or {}).get("to_room") == "kitchen"


def test_a_doorway_belongs_to_both_its_rooms_and_places_her_in_neither():
    """From the kitchen, at the hall's door onto the steps: which side of it
    is not the account's to say."""
    in_kitchen = dict(copy.deepcopy(BEFORE_25),
                      positions={RHONA: "kitchen", ELIAS: "lamp_room"})
    door = _posed_at("door:the_stair", _she_writes_up_the_trial())
    door["transforms"][0]["patch"].pop("inventory_ops")
    assert _places([door], scene=in_kitchen)[0] == [door]


def test_a_body_inside_a_thing_is_where_the_thing_is():
    inside = dict(copy.deepcopy(BEFORE_25), contained={RHONA: {"in": "the_boat"}})
    assert _places([_she_writes_up_the_trial()], scene=inside)[0] == [
        _she_writes_up_the_trial()]


def test_an_act_filed_under_another_mind_is_not_her_account():
    """His act that seats her at the kitchen table is his conduct (the
    conduct floor's to refuse), never her own account of where she is."""
    his = _posed_at("kitchen_table", _she_writes_up_the_trial(src="character:1"))
    assert _places([his])[0] == [his]


def test_a_place_no_way_reaches_moves_nobody_and_says_so():
    cut_off = copy.deepcopy(BEFORE_25)
    cut_off["rooms"]["tower_hall"]["adjacent"] = [{"to": "the_stair",
                                                    "barrier": "open_door"}]
    cut_off["rooms"]["kitchen"]["adjacent"] = [
        a for a in cut_off["rooms"]["kitchen"]["adjacent"] if a["to"] != "tower_hall"]
    out, warnings = _places([_she_writes_up_the_trial()], scene=cut_off)
    assert out == [_she_writes_up_the_trial()]
    assert warnings and "no way" in warnings[0]


@pytest.mark.usefixtures("prose_director")
def test_the_skip_stage_reads_the_walk_from_the_accounts_typed_steps(
        temp_db, monkeypatch):
    """`skip_stage.player_span_place` places the player through a stretch
    only where the account's typed steps put her at or before it. Her own
    act told before the stretch now carries her walk, and it reaches it."""
    from agents.skip_stage import player_span_place
    ctx, me, _elias = _lighthouse(temp_db, BEFORE_25, INPUT_25, idx=8)
    raw = f"turn:{ctx.turn.id}:primary:raw"
    out = _interpret(ctx, monkeypatch, [_she_writes_up_the_trial(me, raw),
                                        _two_days_pass(raw)], PROSE_25)
    assert player_span_place(out, RHONA, BEFORE_25) == "kitchen"


def test_the_decision_model_is_told_where_everyone_started(temp_db, monkeypatch):
    """The positions question asks whether a body ends the passage
    "somewhere other than where it started", and turn 25's decision model
    was never told where anyone started: "Rhona Carrick keeps to the kitchen"
    read as staying put (0.18). The question's fact, handed to it."""
    from tests.director_fakes import _make_ctx
    states = []

    def answer(state, questions):
        states.append(state)
        return {key: {"type": "noul", "noul": 0.5} for key in questions}

    monkeypatch.setattr(decisions, "OVERRIDE", answer)
    ctx = _make_ctx(temp_db, player_input="Rhona keeps to the kitchen.")
    payload = {"identity_index": {"persona:3": RHONA, "character:1": ELIAS}}
    director_prose.select_channels(ctx, "interpret", "Rhona Carrick keeps to the "
                                   "kitchen.", payload, scene=copy.deepcopy(BEFORE_25))
    assert ("WHERE EACH PERSON IS BEFORE THE PASSAGE: Elias Thorne: The Lamp Room; "
            "Rhona Carrick: The Hall") in states[-1]
    # No scene, no line: the state is what it was.
    director_prose.select_channels(ctx, "interpret", "Rhona keeps to it.", payload)
    assert "WHERE EACH PERSON" not in states[-1]


@pytest.mark.usefixtures("prose_director")
def test_turn_25_ends_with_her_in_the_kitchen(temp_db, monkeypatch):
    ctx, me, _elias = _lighthouse(temp_db, BEFORE_25, INPUT_25, idx=8)
    raw = f"turn:{ctx.turn.id}:primary:raw"
    out = _interpret(ctx, monkeypatch, [_two_days_pass(raw),
                                        _she_writes_up_the_trial(me, raw)], PROSE_25)
    assert (out["state_assertions"].get("positions") or {}).get(RHONA) == "kitchen"
    assert (out.get("movement") or {}).get("to_room") == "kitchen"
