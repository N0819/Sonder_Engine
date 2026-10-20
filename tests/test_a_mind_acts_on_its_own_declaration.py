"""At interpret only the player declares, and every row keeps its own actor.

Measured on chats 177 and 178 (review of 2026-10-19, class 3). The interpret
encoder filed another mind's conduct under the player's input:

  * chat 177 t22 -- the player only spoke; the interpretation restated the
    room and the encoder wrote "Mellisande sits on the spare room bed."
    with `source_entity_id` character:83. It went out as the player's event
    `turn:4677:player:1:action`, and the page read "you fold onto the
    mattress".
  * chat 178 t27/t31/t35 -- three of Mellisande's poses the same way; the
    narrator was handed each as a `reconciled_player_action` with actor
    "Hinami", and `player_declared.action` was "bears down over Hinami on the
    bed".

Two floors, both on the engine's typed fields, never the prose: the
interpretation keeps only the declarers' conduct
(`director_prose.conduct_is_its_owners`, an offer to the mind where the act
would change how things stand), and the narrator's projections file a row
under its own actor (`narration._ordered_beat_events`,
`narration._narrator_player_declared`).
"""

from __future__ import annotations

import inspect
import json
import time

import pytest

import agents.director as director
from agents import director_prose
from agents.director_prose import conduct_is_its_owners
from agents.narration import (
    _narrator_perception_fields,
    _narrator_player_declared,
    _ordered_beat_events,
    _player_identity_forms,
)
from core.pipeline_context import ChatData, PipelineContext, TurnData
from story.character_schema import default_character_data, default_persona_data
from tests.director_fakes import BASE_SCENE, _fake_agent, _make_ctx


# ---------------------------------------------------------------------------
# The floor: an act of a mind that declared nothing is refused at interpret
# ---------------------------------------------------------------------------

INDEX = {"persona:10": "Hinami", "character:83": "Mellisande"}
RAW = "turn:4677:primary:raw"
INPUTS = [{"entity_id": "persona:10", "authority_mode": "world_author",
           "events": [{"type": "raw_input", "event_id": RAW}]}]
#: Chat 178 before turn 27, as the checkpoint holds it: both seated on the
#: spare room bed, Mellisande's hands at Hinami's wrists.
SPARE_ROOM = {
    "rooms": {"cottage_spare_room": {"name": "Second Room"}},
    "positions": {"Hinami": "cottage_spare_room",
                  "Mellisande": "cottage_spare_room"},
    "poses": {
        "Hinami": {"posture": "seated", "support": "spare_room_bed",
                   "relative_to": "Mellisande", "relation": "facing"},
        "Mellisande": {"posture": "seated", "support": "spare_room_bed",
                       "relative_to": "Hinami", "relation": "facing",
                       "detail": "sitting on the spare room bed"},
    },
    "contacts": [{"actor": "Mellisande", "actor_part": "hands",
                  "target": "Hinami", "target_part": "wrists",
                  "manner": "hold", "relation": "surface",
                  "motion": "settled"}],
}


def _sits():
    """Chat 177 t22's second event, verbatim but for the item handle."""
    return {"source_entity_id": "character:83", "source_event_id": RAW,
            "event": "Mellisande sits on the spare room bed.",
            "observable": "sits on the bed", "commitment": "asserted",
            "targets": ["spare_room_bed"], "item_names": ["Mellisande"],
            "transforms": [{"item": "Mellisande", "patch": {"poses": {
                "Mellisande": {"posture": "seated", "support": "spare_room_bed",
                               "relative_to": "Hinami", "relation": "facing",
                               "constraint": "",
                               "detail": "sitting on the spare room bed"}}}}]}


def _pins():
    """Chat 178 t27's first event: a pose and a hold the world does not hold."""
    return {"source_entity_id": "character:83", "source_event_id": RAW,
            "event": "Mellisande bears down over Hinami on the spare room bed, "
                     "pinning her beneath her weight.",
            "observable": "bears down over Hinami on the bed",
            "commitment": "asserted", "targets": ["Hinami", "spare_room_bed"],
            "item_names": ["Mellisande"],
            "transforms": [{"item": "Mellisande", "patch": {
                "poses": {"Mellisande": {"posture": "prone", "support": "Hinami",
                                         "relative_to": "Hinami",
                                         "relation": "above"}},
                "contact_ops": [{"op": "add", "actor": "Mellisande",
                                 "actor_part": "body", "target": "Hinami",
                                 "target_part": "body", "manner": "press"}]}}]}


def _says(line="Did you want to cuddle?"):
    return {"source_entity_id": "persona:10", "source_event_id": RAW,
            "event": line, "speech": True, "targets": ["Mellisande"],
            "item_names": [], "transforms": []}


def _floor(events, scene=SPARE_ROOM, inputs=INPUTS):
    warnings = []
    kept, refused = conduct_is_its_owners(events, inputs, INDEX, scene,
                                          warn=warnings.append)
    return kept, refused, warnings


def test_a_restated_pose_of_another_mind_is_not_the_players_event():
    kept, refused, warnings = _floor([_says(), _sits()])
    assert kept == [_says()]
    assert [(row["mind"], row["offer"]) for row in refused] == [
        ("character:83", False)], "it only said again how she sits"
    assert warnings and "Mellisande" in warnings[0]


def test_an_act_another_mind_never_declared_is_offered_to_it():
    kept, refused, _ = _floor([_pins(), _says()])
    assert kept == [_says()]
    assert refused == [{"mind": "character:83", "name": "Mellisande",
                        "event": _pins()["event"], "offer": True}]


def test_a_restated_hold_is_read_by_its_endpoints():
    """A plural part is the same hold (`contact_id` folds the region)."""
    held = {"source_entity_id": "Mellisande", "source_event_id": RAW,
            "event": "Mellisande keeps hold of Hinami's wrists.",
            "transforms": [{"item": "Mellisande", "patch": {"contact_ops": [
                {"op": "add", "actor": "Mellisande", "actor_part": "hand",
                 "target": "Hinami", "target_part": "wrist",
                 "manner": "grip"}]}}]}
    _, refused, _ = _floor([held])
    assert [row["offer"] for row in refused] == [False]


def test_a_line_or_a_bare_act_of_another_mind_is_offered():
    """What an act did cannot be read off a record it never wrote, so it is
    never taken for a restatement."""
    line = dict(_says("Come here."), source_entity_id="character:83")
    smile = {"source_entity_id": "character:83", "source_event_id": RAW,
             "event": "Mellisande smiles.", "transforms": []}
    _, refused, _ = _floor([line, smile])
    assert [row["offer"] for row in refused] == [True, True]


def test_the_declarer_and_the_world_keep_their_events():
    figure = {"source_entity_id": "the miller", "source_event_id": RAW,
              "event": "The miller looks up from the lane.", "transforms": []}
    by_name = dict(_says(), source_entity_id="Hinami")
    kept, refused, warnings = _floor([_says(), figure, by_name])
    assert kept == [_says(), figure, by_name]
    assert refused == [] and warnings == []


def test_a_mind_with_its_own_input_is_a_declarer():
    """A second human player's own conduct is theirs at interpret."""
    inputs = INPUTS + [{"entity_id": "character:83",
                        "authority_mode": "world_author",
                        "events": [{"type": "raw_input", "event_id": "x"}]}]
    kept, refused, _ = _floor([_sits()], inputs=inputs)
    assert kept == [_sits()] and refused == []


def test_the_floor_runs_at_interpret_before_rows_are_made():
    source = inspect.getsource(director_prose.run)
    assert "conduct_is_its_owners(" in source
    assert source.index("conduct_is_its_owners(") < source.index(
        "ledger_from_events(")


# ---------------------------------------------------------------------------
# End to end: the interpretation the player's sequence is built from
# ---------------------------------------------------------------------------

SEATED = dict(BASE_SCENE, poses={
    "Mara": {"posture": "seated", "support": "cot",
             "relative_to": "The Stranger", "relation": "facing"}})


def _interpret(temp_db, monkeypatch, mara_events, prose):
    ctx = _make_ctx(temp_db, scene=SEATED,
                    player_input='"Did you want to cuddle?"')
    mara = f"character:{ctx.cast[0]['id']}"
    events = [dict(event, source_entity_id=mara) for event in mara_events]
    events.append({"source_entity_id": "persona:primary",
                   "event": "Did you want to cuddle?", "speech": True,
                   "targets": ["Mara"], "item_names": [], "transforms": []})
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_prose": {"prose": prose},
        "director_specialist": {"events": events},
    }))
    return ctx, director.director_interpret(ctx, nonce=0)


@pytest.mark.usefixtures("prose_director")
def test_a_restatement_never_becomes_the_players_event(temp_db, monkeypatch):
    sits = {"event": "Mara sits on the cot.", "observable": "sits on the cot",
            "item_names": ["Mara"],
            "transforms": [{"item": "Mara", "patch": {"poses": {"Mara": {
                "posture": "seated", "support": "cot",
                "relative_to": "The Stranger", "relation": "facing"}}}}]}
    ctx, out = _interpret(temp_db, monkeypatch, [sits],
                          'The Stranger stands by the cot where Mara sits. '
                          'The Stranger says, "Did you want to cuddle?"')
    actors = [row.get("actor") for row in out["sequence"]]
    assert actors == ["persona:primary"], actors
    assert not out.get("authorial_offers")
    assert "Mara" not in json.dumps(
        (out.get("state_assertions") or {}).get("poses") or {})
    refused = out["orchestration"]["prose_contract"]["conduct_refused"]
    assert [row["offer"] for row in refused] == [False]


@pytest.mark.usefixtures("prose_director")
def test_an_authored_act_goes_to_its_mind_and_not_into_the_world(
        temp_db, monkeypatch):
    pins = {"event": "Mara presses The Stranger down onto the cot.",
            "observable": "presses her down onto the cot",
            "item_names": ["Mara"],
            "transforms": [{"item": "Mara", "patch": {"poses": {"Mara": {
                "posture": "prone", "support": "The Stranger",
                "relative_to": "The Stranger", "relation": "above"}}}}]}
    ctx, out = _interpret(temp_db, monkeypatch, [pins],
                          'The Stranger finds herself pinned under Mara.')
    assert [row.get("actor") for row in out["sequence"]] == ["persona:primary"]
    assert out["authorial_offers"] == [{
        "subject_id": ctx.cast[0]["id"], "proposition": pins["event"],
        "source": "player"}]
    assert "prone" not in json.dumps(out.get("state_assertions") or {})
    assert "prone" not in json.dumps(out.get("onset_state_assertions") or {})


def test_the_resolve_is_not_told_a_refused_act_already_happened():
    interp = {
        "orchestration": {"prose_contract": {
            "prose": "Hinami lies on the bed, Mellisande above her, pinning her.",
            "conduct_refused": [{"mind": "character:83", "name": "Mellisande",
                                 "event": "Mellisande pins Hinami.",
                                 "offer": True}]}},
        "causal_ledger": [{"chrono_id": 1, "commitment": "asserted",
                           "event": "Hinami makes a slightly confused noise."}],
    }

    class _Ctx:
        director_interpret = interp

    told = director_prose.already_happened(_Ctx())
    assert told == "Hinami makes a slightly confused noise."


# ---------------------------------------------------------------------------
# The narrator's projections: every row under its own actor
# ---------------------------------------------------------------------------

def _hinami_ctx(temp_db, sequence):
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        ("Hinami", json.dumps(default_persona_data("Hinami")), "{}"))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Cottage", "", time.time(), persona_id))
    cast = [{"id": 83, "sheet": json.dumps(default_character_data("Mellisande")),
             "cstate": "{}", "status": "active"}]
    temp_db.wset(chat_id, "scene", SPARE_ROOM)
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Cottage", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=4705, chat_id=chat_id, idx=27,
                      player_input="You find yourself pinned under her",
                      created=time.time()),
        cast=cast, input="You find yourself pinned under her")
    own = f"persona:{persona_id}"
    ctx.director_interpret = {"sequence": [
        dict(row, actor=own if row.get("actor") == "persona:10" else row["actor"])
        for row in sequence]}
    return ctx, own


#: Chat 178 t27's interpret sequence, as stored.
T27 = [
    {"type": "action", "actor": "character:83",
     "event_id": "turn:4705:player:0:action",
     "attempt": "Mellisande bears down over Hinami on the spare room bed, "
                "pinning her beneath her weight.",
     "observable": "bears down over Hinami on the bed, settling her weight "
                   "over her",
     "commitment": "asserted", "visibility": "overt",
     "targets": ["Hinami", "spare_room_bed"]},
    {"type": "action", "actor": "persona:10",
     "event_id": "turn:4705:player:1:action",
     "attempt": "Hinami makes a slightly confused noise.",
     "observable": "makes a slightly confused noise",
     "commitment": "asserted", "visibility": "overt",
     "targets": ["Mellisande"]},
]


def test_another_minds_row_is_filed_under_its_own_actor(temp_db):
    ctx, _own = _hinami_ctx(temp_db, T27)
    events = _ordered_beat_events(
        ctx, "Hinami", "", {"Mellisande"},
        {"Mellisande": {"appearance": "", "aliases": []}},
        scene=SPARE_ROOM, p_room="cottage_spare_room")
    assert [(event["actor"], event["kind"]) for event in events] == [
        ("Mellisande", "action"), ("Hinami", "action")]
    acts = _narrator_perception_fields(
        [], "", [event for event in events
                 if event["kind"] == "action" and event["actor"] == "Hinami"])
    assert [event["text"] for event in acts["current_events"]] == [
        "makes a slightly confused noise"]


def test_an_unseen_minds_row_never_reaches_the_record(temp_db):
    """It takes that mind's gate: an act the player cannot perceive is not
    listed, as for any other mind's (`_seq_events`)."""
    ctx, _own = _hinami_ctx(temp_db, T27)
    apart = dict(SPARE_ROOM, rooms={"cottage_spare_room": {"name": "Second Room"},
                                    "kitchen": {"name": "Kitchen",
                                                "barrier": "wall"}},
                 positions={"Hinami": "cottage_spare_room",
                            "Mellisande": "kitchen"})
    events = _ordered_beat_events(
        ctx, "Hinami", "", {"Mellisande"},
        {"Mellisande": {"appearance": "", "aliases": []}},
        scene=apart, p_room="cottage_spare_room")
    assert [event["actor"] for event in events] == ["Hinami"]


def test_the_players_declared_conduct_is_hers_alone(temp_db):
    ctx, own = _hinami_ctx(temp_db, T27)
    declared = _narrator_player_declared(
        ctx.director_interpret, _player_identity_forms(ctx, "Hinami"))
    assert declared["action"] == "makes a slightly confused noise"
    assert [row["event_id"] for row in declared["sequence"]] == [
        "turn:4705:player:1:action"]
    # Without the player's forms a cast member's row is still never hers.
    legacy = _narrator_player_declared(ctx.director_interpret)
    assert legacy["action"] == "makes a slightly confused noise"


def test_a_row_with_no_actor_is_the_players_as_it_always_was():
    declared = _narrator_player_declared({"sequence": [{
        "type": "action", "attempt": "steps to the console",
        "observable": "steps to the console", "commitment": "asserted"}]},
        {"persona:1", "hinami"})
    assert declared["action"] == "steps to the console"
