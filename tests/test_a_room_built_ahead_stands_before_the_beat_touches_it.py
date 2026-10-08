"""A ROOM BUILT AHEAD STANDS BEFORE THE BEAT TOUCHES IT.

A room the between-turns job built rides the beat it opens on as that
beat's first causal step, whatever kind of beat it is. On a played beat the
prose contract carries it as the first event; a silent beat (empty input)
and a causality bubble's own beat carry it through
`director_rooms.carry_installed_rooms`, which put it at the TOP LEVEL of the
interpret's assertions alone -- so it yielded to any resolve write naming
the same room (`merge_player_state_assertions`: "the assertion yields") and
applied after the resolve's steps. A room shown built, its door pulled to
or its rail leaned on during that beat, was committed as its stub. Found by
the round-4 review of the rooms-in-view lane (2026-10-08); the played-beat
cases are the controls."""

from __future__ import annotations


import pytest

import agents.director as director
from llm import decisions

from tests.director_fakes import _fake_agent
from tests.test_a_room_in_view_is_built_before_anyone_walks_in import (
    GALLERY, _beat_at, _decide, _prepare, _story)


DOOR_TO = {"source_entity_id": "character:1",
           "event": "Mara steps out onto the gallery and pulls its door to behind her.",
           "item_names": ["Mara", "Lamp Gallery"],
           "transforms": [
               {"item": "Lamp Gallery", "patch": {"rooms": {"lamp_gallery": {
                   "adjacent": [{"to": "keeper_room", "barrier": "closed_door"}]}}}},
           ]}


def _agents(calls):
    return _fake_agent(calls, {
        "director_prose": {"prose": "Mara steps out onto the gallery and pulls the door to."},
        "director_specialist": {"events": [DOOR_TO]},
        "director_rooms": {"calls": [{"tool": "submit", "args": {}}]},
    })


@pytest.mark.parametrize("text", ["", "I look up."], ids=["silent", "played"])
def test_a_door_edit_on_a_room_built_ahead_keeps_the_room(temp_db, monkeypatch, text):
    from persist import commit
    ctx = _story(temp_db)
    _prepare(temp_db, monkeypatch, ctx, {"lamp_gallery": GALLERY})
    beat = _beat_at(temp_db, ctx, 2, text)
    monkeypatch.setattr(decisions, "OVERRIDE", _decide())
    calls = []
    monkeypatch.setattr(director, "_agent_json", _agents(calls))
    out = director.director_interpret(beat, nonce=0)
    beat.director_interpret = out
    res = director.director_resolve(beat, nonce=0)
    sd = res.get("state_diff") or {}
    beat.director_resolve = res
    commit.commit_scene(beat, nonce=0, prepared=commit.prepare_scene_commit(beat))
    stored = temp_db.wget(ctx.chat.id, "scene")["rooms"]["lamp_gallery"]
    assert stored.get("desc") == GALLERY["desc"], (
        "the room the beat opened on, built in and shown, was committed as its stub")


def test_a_bubbles_beat_keeps_the_room_it_built_ahead(temp_db, monkeypatch):
    import agents.common as common
    from core import db
    from persist import commit
    from agents import director_rooms
    from tests.test_a_room_in_view_is_built_before_anyone_walks_in import (
        BELL, _bubble, _designer, _wait)
    ctx = _story(temp_db)
    cid = ctx.chat.id
    fid, away = _bubble(temp_db, ctx)
    monkeypatch.setattr(common, "_agent_json", _designer([], {"bell_loft": BELL}))
    _wait(director_rooms.schedule_room_predevelopment(
        _beat_at(temp_db, ctx, 2, "", frame_id=fid)))
    nxt = _beat_at(temp_db, ctx, 3, "", frame_id=fid)
    monkeypatch.setattr(decisions, "OVERRIDE", _decide())
    trap = {"source_entity_id": "character:1",
            "event": "Mara climbs into the bell loft and drops the trap shut.",
            "item_names": ["Mara", "Bell Loft"],
            "transforms": [{"item": "Bell Loft", "patch": {"rooms": {"bell_loft": {
                "adjacent": [{"to": "stair_foot", "barrier": "closed_door"}]}}}}]}
    monkeypatch.setattr(director, "_agent_json", _fake_agent([], {
        "director_prose": {"prose": "Mara climbs into the bell loft and drops the trap shut."},
        "director_specialist": {"events": [trap]},
        "director_rooms": {"calls": [{"tool": "submit", "args": {}}]},
    }))
    token = db.active_frame_id.set(fid)
    try:
        out = director.director_interpret(nxt, nonce=0)
        nxt.director_interpret = out
        nxt.director_resolve = director.director_resolve(nxt, nonce=0)
        commit.commit_scene(nxt, nonce=0, prepared=commit.prepare_scene_commit(nxt))
    finally:
        db.active_frame_id.reset(token)
    stored = temp_db.wget_for_frame(cid, "scene", fid)["rooms"]["bell_loft"]
    assert stored.get("desc") == BELL["desc"], "her loft, built in and shown, committed as its stub"


@pytest.mark.parametrize("text", ["", "I look up."], ids=["silent", "played"])
def test_a_body_stationed_at_a_fixture_of_a_room_built_ahead_keeps_the_room(temp_db, monkeypatch, text):
    from persist import commit
    ctx = _story(temp_db)
    _prepare(temp_db, monkeypatch, ctx, {"lamp_gallery": GALLERY})
    beat = _beat_at(temp_db, ctx, 2, text)
    monkeypatch.setattr(decisions, "OVERRIDE", _decide())
    lean = {"source_entity_id": "character:1",
            "event": "Mara steps out onto the gallery and leans on the rail.",
            "item_names": ["Mara"],
            "transforms": [{"item": "Mara", "patch": {
                "positions": {"Mara": "lamp_gallery"},
                "stations": {"Mara": {"at": "rail"}}}}]}
    monkeypatch.setattr(director, "_agent_json", _fake_agent([], {
        "director_prose": {"prose": "Mara steps out onto the gallery and leans on the rail."},
        "director_specialist": {"events": [lean]},
        "director_rooms": {"calls": [{"tool": "submit", "args": {}}]},
    }))
    out = director.director_interpret(beat, nonce=0)
    beat.director_interpret = out
    beat.director_resolve = director.director_resolve(beat, nonce=0)
    commit.commit_scene(beat, nonce=0, prepared=commit.prepare_scene_commit(beat))
    scene = temp_db.wget(ctx.chat.id, "scene")
    assert ((scene.get("stations") or {}).get("Mara") or {}).get("at") == "rail", (
        "the body stationed at a fixture of the room the beat opened on lost the fixture")
