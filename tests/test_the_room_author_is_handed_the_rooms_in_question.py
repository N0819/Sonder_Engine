"""The room author reads the records of the rooms in question, not the town.

The spatial slice the room author is built from carries every room the world
holds. Measured on chat 166 (the Brackwater run, 50 captured in-beat calls):
that ledger was 26.2k chars of a 75.3k payload, `inspect_rooms` was called 0
times in 49 steps, every room id a design wrote was already on `world_index`,
in `surroundings`, owed, or named by a plan's exits, and of the 91 field
values its drafts wrote none came only from a room outside the ones kept here
but the light word `dark`. The kept records -- the drawn rooms around the
place and the owed rooms that already stand -- averaged 7.3k chars.

What a drawing leaves out (a room's storey, light, surface, exposure and
region; a doorway's way and name) is exactly why the records of the drawn
rooms stay: dropping them was refuted on the same run. Every other room is
still on the map (`world_index.elsewhere`) and `inspect_rooms` hands any of
them over whole.
"""

from __future__ import annotations

import json

import agents.director as director
from agents import director_rooms
from llm import decisions

from tests.director_fakes import BASE_SCENE, _action_interp, _fake_agent, _make_ctx

TOWN = {
    "hall": {"name": "Hall", "desc": "A hall.", "extent": {"w": 6, "d": 4},
             "level": 0, "region": "the_house", "light": "dim",
             "adjacent": [{"to": "study", "barrier": "open", "dir": "n",
                           "name": "the study door"},
                          {"to": "loft_stub", "barrier": "open", "dir": "e"}]},
    "study": {"name": "Study", "desc": "A study.", "level": 0, "surface": "furnished",
              "adjacent": [{"to": "hall", "barrier": "open", "dir": "s"}]},
    # A plan's stub beside the hall that no beat has entered.
    "loft_stub": {"name": "east_1", "planned": True,
                  "adjacent": [{"to": "hall", "barrier": "open", "dir": "w"}]},
    # A plan's stub the beat develops: its record holds the plan's measurements.
    "gallery": {"name": "Gallery", "planned": True, "extent": {"w": 5, "d": 4},
                "adjacent": [{"to": "study", "barrier": "open", "dir": "s"}]},
    # Rooms across town.
    "boathouse": {"name": "Boathouse", "desc": "Far off.", "level": 0,
                  "adjacent": [{"to": "jetty", "barrier": "open", "dir": "e"}]},
    "jetty": {"name": "Jetty", "desc": "Planks over the water.", "level": 0,
              "adjacent": [{"to": "boathouse", "barrier": "open", "dir": "w"}]},
}


def _first_payload(scene, payload, owed):
    seen = []

    def call(system, step_payload):
        seen.append(step_payload)
        return {"calls": []}

    record = {}
    director_rooms.design_rooms(None, scene, payload, "sheet", owed, call, record)
    return seen[0], record


def test_the_designer_is_handed_the_records_of_the_rooms_around_its_place():
    scene = {"rooms": json.loads(json.dumps(TOWN)), "positions": {"Mara": "hall"}}
    payload = {"prose": "Mara climbs into the gallery.", "positions": {"Mara": "hall"},
               "develop": {"gallery": {"name": "Gallery", "exits": [{"to": "study"}]}},
               "rooms": json.loads(json.dumps(TOWN))}
    first, record = _first_payload(scene, payload, ["gallery"])
    # The drawn rooms around the place, and the owed room that stands.
    assert set(first["rooms"]) == {"hall", "study", "gallery"}
    assert first["rooms"]["hall"] == TOWN["hall"], "the record whole, as stored"
    assert first["rooms"]["gallery"]["extent"] == {"w": 5, "d": 4}
    # An unentered stub is drawn for no one and its record is not handed over.
    assert "loft_stub" not in first["rooms"]
    assert "loft_stub" not in first["surroundings"]
    # The town is left on the map.
    assert "boathouse" not in first["rooms"] and "jetty" not in first["rooms"]
    assert record["groundwork"]["records"] == ["gallery", "hall", "study"]
    assert record["groundwork"]["records_left_on_the_map"] == 3


def test_a_payload_that_carried_no_ledger_is_given_none():
    """Predevelopment's payload never carried the spatial slice; the cut
    narrows a ledger that is there and never adds one."""
    scene = {"rooms": json.loads(json.dumps(TOWN)), "positions": {}}
    first, _record = _first_payload(
        scene, {"prose": "", "develop": {"gallery": {"name": "Gallery",
                                                     "exits": [{"to": "study"}]}}},
        ["gallery"])
    assert "rooms" not in first


def test_inspect_rooms_hands_any_room_over_whole():
    """A room left on the map is one call away, with every field its record
    holds -- the storey, the light, a doorway's name -- not the drawing's
    short projection of it."""
    scene = {"rooms": json.loads(json.dumps(TOWN)), "positions": {"Mara": "hall"}}
    steps = iter([{"calls": [{"tool": "inspect_rooms", "args": {"room_ids": ["hall"]}}]},
                  {"calls": []}])
    seen = []

    def call(system, step_payload):
        seen.append(step_payload)
        return next(steps)

    director_rooms.design_rooms(None, scene, {"prose": "x", "rooms": TOWN},
                                "sheet", [], call, {})
    shown = seen[1]["transcript"][0]["result"]["hall"]
    assert shown["record"] == TOWN["hall"]
    assert shown["record"]["adjacent"][0]["name"] == "the study door"
    assert "map" in shown and "legend" in shown


def test_the_stage_hands_the_room_author_the_rooms_in_question(temp_db, monkeypatch):
    """Through the real stage: the spatial slice carries the whole ledger,
    and the author's first step reads the records around the place it is
    developing, with the rest of the town on its map."""
    from agents import director_prose
    scene = json.loads(json.dumps(BASE_SCENE))
    scene["rooms"]["boathouse"] = {"name": "Boathouse", "desc": "Far off.",
                                   "adjacent": [{"to": "jetty", "barrier": "open"}]}
    scene["rooms"]["jetty"] = {"name": "Jetty", "desc": "Planks.",
                               "adjacent": [{"to": "boathouse", "barrier": "open"}]}
    planned = {"lamp_gallery": {"name": "Lamp Gallery", "purpose": "the keeper's walk",
                                "exits": {"lamp_room": {"to": "lamp_room"}}}}
    original = director_prose.run

    def run_with_plan(ctx, stage, sc, model_payload, view, extras, facts=None):
        return original(ctx, stage, sc, model_payload, view,
                        dict(extras, planned_rooms=planned), facts)

    monkeypatch.setattr(director_prose, "run", run_with_plan)
    monkeypatch.setattr(decisions, "OVERRIDE", lambda state, questions: {
        key: {"type": "noul", "noul": 0.95 if key in ("positions", "enter__lamp_gallery")
              else 0.0} for key in questions})
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_prose": {"prose": "Mara steps out onto the lamp gallery."},
        "director_rooms": {"calls": [
            {"tool": "draft_room", "args": {"room_id": "lamp_gallery", "room": {
                "name": "Lamp Gallery", "desc": "A narrow iron walk.",
                "adjacent": [{"to": "lamp_room", "barrier": "open", "dir": "s"}]}}},
            {"tool": "submit", "args": {}}]},
        "director_specialist": {"events": [
            {"source_entity_id": "character:1", "event": "Mara steps out.",
             "item_names": ["Mara"],
             "transforms": [{"item": "Mara", "patch": {
                 "positions": {"Mara": "lamp_gallery"}}}]}]},
    }))
    director.director_resolve(_make_ctx(temp_db, scene=scene, interp=_action_interp()),
                              nonce=0)
    rooms_calls = [c for c in calls if c["step_key"] == "director_rooms"]
    assert rooms_calls, "the room author did not run"
    handed = rooms_calls[0]["payload"]
    assert set(handed["rooms"]) == {"keeper_room", "lamp_room"}
    assert "boathouse" not in handed["rooms"] and "jetty" not in handed["rooms"]
    elsewhere = (handed.get("world_index") or {}).get("elsewhere") or {}
    assert {"boathouse", "jetty"} <= set(elsewhere), "the town stays on the map"
