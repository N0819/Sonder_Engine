"""An emission is stoppable in the vocabulary it was declared in.

Measured on the owner's chat 176 (2026-10-19): the opening set the kettle
`sound_source: loud` (with `whistling: true`, and no switch). At turn 4 the
encoder stopped it the way it was declared -- `sound_source: null`,
`whistling: false` -- and the merge, which reads a field written as nothing
as silence (`spatial_merge._ENTITY_DEFAULT_FIELDS`), kept it loud. Only
`state.running` stops a sound (`spatial_sound_field._running`), so the kettle
stayed loud through turn 11 -- seven beats past its stop -- masking the
player's speech.

The encoder's own null is read before validation, where it cannot be a
schema's default: a level written as nothing on a thing that emits is its
switch written off, and the level stays for the day it starts again.
"""

from __future__ import annotations

import copy

import agents.director as director
from agents import director_prose
from llm import decisions
from world.spatial import merge_scene_with_diff, sound_sources

from tests.director_fakes import BASE_SCENE, _action_interp, _fake_agent, _make_ctx


def _kitchen():
    scene = copy.deepcopy(BASE_SCENE)
    scene["entities"] = {
        "kitchen_kettle": {"name": "the kettle", "kind": "object", "aliases": ["kettle"],
                           "portable": True, "sound_source": "loud",
                           "state": {"on_the_range": True, "whistling": True}},
        "lamp": {"name": "the lamp", "kind": "object", "light_source": "lit",
                 "state": {}},
        "stool": {"name": "a stool", "kind": "object", "state": {}},
    }
    scene["positions"].update({"kitchen_kettle": "keeper_room", "lamp": "keeper_room",
                               "stool": "keeper_room"})
    return scene


def _stop(record):
    return {"events": [{
        "source_entity_id": "character:1", "source_event_id": "x",
        "event": "Mara lifts the kettle off the heat.",
        "observable": "lifts the kettle off the heat", "speech": False,
        "targets": ["kitchen_kettle"], "seconds": 2, "movement": None,
        "commitment": "asserted", "item_names": ["the kettle"],
        "transforms": [{"item": "the kettle",
                        "patch": {"entities": {"kitchen_kettle": record}}}]}],
        "missing_tools": [], "missing_referents": [], "notes": []}


def _resolve(temp_db, monkeypatch, record, scene):
    temp_db.set_setting("prose_contract_repair", "0")
    monkeypatch.setattr(decisions, "OVERRIDE", lambda state, questions: {
        key: {"type": "noul", "noul": 0.95 if key in ("entities", "entities__emits") else 0.02}
        for key in questions})
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_prose": {"prose": "Mara lifts the kettle off the heat and it falls quiet."},
        "director_specialist": _stop(record),
    }))
    ctx = _make_ctx(temp_db, scene=scene, interp=_action_interp())
    return director.director_resolve(ctx, nonce=0)


def _heard(scene):
    return {source["id"] for source in sound_sources(scene)[0] if source["kind"] == "entity"}


def test_a_level_written_as_nothing_stops_the_kettle(temp_db, monkeypatch):
    """Chat 176 turn 4's exact write."""
    scene = _kitchen()
    assert "kitchen_kettle" in _heard(scene)
    out = _resolve(temp_db, monkeypatch,
                   {"sound_source": None, "state": {"whistling": False}}, scene)
    after = merge_scene_with_diff(copy.deepcopy(scene), out["state_diff"])
    kettle = after["entities"]["kitchen_kettle"]
    assert kettle["state"]["running"] is False
    assert kettle["sound_source"] == "loud"      # kept for the day it starts again
    assert "kitchen_kettle" not in _heard(after)


def test_the_floor_reads_only_the_encoders_own_nothing():
    scene = _kitchen()
    events = [
        {"transforms": [{"item": "lamp", "patch": {"entities": {
            "lamp": {"light_source": "", "state": {"pointed_at": "n"}}}}}]},
        # A thing that never emitted: its null is left as written.
        {"transforms": [{"item": "stool", "patch": {"entities": {
            "stool": {"sound_source": None}}}}]},
        # A re-statement of the level is not a stop.
        {"transforms": [{"item": "kettle", "patch": {"entities": {
            "kitchen_kettle": {"sound_source": "loud"}}}}]},
    ]
    out = director_prose.an_emission_stops_in_its_own_words(events, scene)
    lamp = out[0]["transforms"][0]["patch"]["entities"]["lamp"]
    assert "light_source" not in lamp and lamp["state"] == {"pointed_at": "n", "lit": False}
    assert out[1]["transforms"][0]["patch"]["entities"]["stool"] == {"sound_source": None}
    assert out[2]["transforms"][0]["patch"]["entities"]["kitchen_kettle"] == {
        "sound_source": "loud"}


def test_a_source_lit_this_beat_is_put_out_in_the_same_words():
    """Declared at one step and stopped at a later one, within one beat."""
    events = [
        {"transforms": [{"item": "torch", "patch": {"entities": {
            "torch": {"name": "a torch", "light_source": "lit", "state": {"lit": True}}}}}]},
        {"transforms": [{"item": "torch", "patch": {"entities": {
            "torch": {"light_source": None}}}}]},
    ]
    out = director_prose.an_emission_stops_in_its_own_words(events, {"entities": {}})
    assert out[1]["transforms"][0]["patch"]["entities"]["torch"] == {"state": {"lit": False}}


def test_the_card_says_how_a_source_stops():
    """The model writes the stop; the card says what stops one -- its switch,
    or its level written as nothing -- and that the thing's own word for
    working, flipped, stops nothing (chat 176's `whistling: false`)."""
    from llm.prompts import unified_specialist_prompt
    en = unified_specialist_prompt(["entities"], "en", ["entities__emits"])
    ja = unified_specialist_prompt(["entities"], "ja", ["entities__emits"])
    assert "A source stops by that switch" in en
    assert "a level written as nothing reads the same" in en
    assert "段階を空にして書いても同じに読まれます" in ja
