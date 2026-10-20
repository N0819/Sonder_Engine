"""A happening no body performs has no actor.

Measured on the owner's chats 175 and 177 (2026-10-19). The encoder files
every step under some identity, and the card told it a happening the world
causes goes to "the body whose act it follows from" -- so a hen, a gate, a
cart in the lane and a window rattling upstairs were all filed under
Mellisande, and the act renderer gave her label to each: "The warm
approachable figure a hen clucks sharply once down the lane" (175 turn 2),
"Mellisande a log settles in the range hearth with a dry knock" (177 turn 12).
The encoder, not the composer, assigned the actor; the composer only rendered
the row it was given.

The contract now has a source for nobody (`director_prose.WORLD_SOURCE`,
named in the core card), and code re-files what it can know without reading
prose: a step whose every write is a signal that happened in a room its body
does not stand in (`a_signal_elsewhere_is_nobodys_act`).
"""

from __future__ import annotations

import copy

import agents.director as director
from agents import director_prose, perception
from llm import decisions
from llm.prompts import unified_specialist_prompt

from tests.director_fakes import BASE_SCENE, _fake_agent, _make_ctx, _speech_interp


def _signal(room, source, detail, *, actor="character:1", observable=""):
    return {"source_entity_id": actor, "source_event_id": "x",
            "event": observable, "observable": observable, "speech": False,
            "targets": [], "seconds": 2, "movement": None, "commitment": "asserted",
            "item_names": [], "transforms": [{"item": room, "patch": {"sensory_events": [
                {"kind": "sound", "room": room, "level": "faint", "source": source,
                 "detail": detail}]}}]}


def _lane():
    """Chat 175's two rooms: the cottage, and the lane outside its door."""
    return {"rooms": {"lane_end": {"name": "The Lane's End",
                                   "adjacent": [{"to": "the_lane", "barrier": "open_door"}]},
                      "the_lane": {"name": "The Lane", "adjacent": []}},
            "positions": {"Mellisande": "lane_end", "Hinami": "lane_end"}}


IDENTITIES = {"character:83": "Mellisande", "persona:10": "Hinami"}


def test_a_signal_down_the_lane_is_not_the_cooks_act():
    events = [
        # Chat 175 turns 2, 3 and 14, as the encoder wrote them.
        _signal("the_lane", "hen", "a hen clucking once down the lane",
                actor="character:83", observable="a hen clucks sharply once down the lane"),
        _signal("the_lane", "field_gate", "a gate clicking shut",
                actor="character:83", observable="a gate clicks shut down the lane"),
        # Her own noises, where she stands, stay hers (chat 177 turn 16's
        # torn scone; chat 175 turn 8's chewing).
        _signal("lane_end", "the cooling rack of scones", "a soft crack of crust",
                actor="character:83", observable="takes a scone and tears off a corner"),
        _signal("lane_end", "Hinami", "a small chewing noise",
                actor="persona:10", observable="makes a small chewing noise"),
    ]
    warned = []
    out = director_prose.a_signal_elsewhere_is_nobodys_act(
        events, _lane(), IDENTITIES, warn=warned.append)
    assert [e["source_entity_id"] for e in out] == [
        director_prose.WORLD_SOURCE, director_prose.WORLD_SOURCE,
        "character:83", "persona:10"]
    assert out[0]["source_event_id"] == "x"          # still follows from its input
    assert len(warned) == 2


def test_only_a_step_that_is_nothing_but_signals_is_refiled():
    lane = _lane()
    walked = _signal("the_lane", "door", "the door banging",
                     actor="character:83", observable="goes out and the door bangs")
    walked["movement"] = {"to_room": "the_lane", "mover": "Mellisande", "arrives": True}
    spoke = dict(_signal("the_lane", "hen", "a cluck", actor="character:83"), speech=True)
    wrote = _signal("the_lane", "gate", "a click", actor="character:83")
    wrote["transforms"].append({"item": "gate", "patch": {"entities": {
        "field_gate": {"state": {"open": False}}}}})
    # A body the beat walks into the lane makes its own noise there.
    there = _signal("the_lane", "boots", "boots on gravel", actor="character:83")
    moving = {"source_entity_id": "character:83", "transforms": [
        {"item": "Mellisande", "patch": {"positions": {"Mellisande": "the_lane"}}}]}
    nobody = _signal("the_lane", "hen", "a cluck", actor="a stranger")
    out = director_prose.a_signal_elsewhere_is_nobodys_act(
        [walked, spoke, wrote, moving, there, nobody], lane, IDENTITIES)
    assert [e["source_entity_id"] for e in out] == [
        "character:83", "character:83", "character:83", "character:83",
        "character:83", "a stranger"]


def test_the_world_happening_reaches_no_body_as_its_act(temp_db, monkeypatch):
    """End to end: the resolve files it under the world, and the act renderer
    puts nobody's label in front of it."""
    temp_db.set_setting("prose_contract_repair", "0")
    ctx = _make_ctx(temp_db, scene=copy.deepcopy(BASE_SCENE), interp=_speech_interp())
    cid = int(ctx.cast[0]["id"])
    key = f"character:{cid}"
    declared = [{"type": "action", "attempt": "lift the kettle", "observable": "lifts the kettle",
                 "visibility": "overt", "commitment": "asserted",
                 "event_id": f"turn:1:{key}:0:action"}]
    ctx["interaction_loop"] = {"rounds": [{"round": 0, "speaker_id": cid, "speaker": "Mara",
                                           "result": {"sequence": declared}}]}
    ctx.character_results[cid] = {"sequence": declared}
    lifted = {"source_entity_id": key, "source_event_id": declared[0]["event_id"],
              "event": "Mara lifts the kettle.", "observable": "lifts the kettle",
              "speech": False, "targets": [], "seconds": 2, "movement": None,
              "commitment": "asserted", "item_names": ["Mara"], "transforms": []}
    shutter = dict(_signal("lamp_room", "shutter", "a shutter banging once", actor=key,
                           observable="a shutter bangs once up in the lamp room"),
                   source_event_id=declared[0]["event_id"])
    monkeypatch.setattr(decisions, "OVERRIDE", lambda state, questions: {
        k: {"type": "noul", "noul": 0.95 if k == "sensory_events" else 0.02}
        for k in questions})
    monkeypatch.setattr(director, "_agent_json", _fake_agent([], {
        "director_prose": {"prose": "Mara lifts the kettle. Up in the lamp room, "
                                    "a shutter bangs once."},
        "director_specialist": {"events": [lifted, shutter], "missing_tools": [],
                                "missing_referents": [], "notes": []}}))
    out = director.director_resolve(ctx, nonce=0)
    assert [row["actor"] for row in out["sequence"]] == [key, director_prose.WORLD_SOURCE]
    ctx.director_resolve = out
    ctx["background_react"] = {"fired": False, "name": None, "reactions": [],
                               "selected": [], "mode": "background_react"}
    view = perception.perception_outcome(ctx, "n0")["views"]["player"]
    assert "lifts the kettle" in view
    # The defect's own rendering: her label in front of the shutter.
    assert "appearance a shutter" not in view


def test_the_encoder_is_told_a_happening_no_body_performs_has_no_actor():
    for language, needle in (("en", "has no actor"), ("ja", "行為者はいません")):
        core = unified_specialist_prompt([], language, [])
        assert needle in core
        assert f'"{director_prose.WORLD_SOURCE}"' in core
