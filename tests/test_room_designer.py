"""The prose contract's room designer (agents/director_rooms.py).

A room is designed, not formatted: the designer works in steps with tools,
sees its floor plan on the engine's own grid, and checks its geometry with the
engine's own layout lint before it submits. These pin the tools and the loop;
`tests/test_prose_contract.py` pins how its draft joins the beat.
"""

from __future__ import annotations

import agents.director as director
from agents import director_rooms
from llm import decisions

from tests.test_director_orchestration import _action_interp, _fake_agent, _make_ctx

SCENE = {
    "rooms": {
        "hall": {"name": "Hall", "desc": "A hall.", "extent": {"w": 6, "d": 4},
                 "adjacent": [{"to": "study", "barrier": "open", "dir": "n"}]},
        "study": {"name": "Study", "desc": "A study.", "adjacent": [
            {"to": "hall", "barrier": "open", "dir": "s"}]},
    },
    "positions": {},
}


def test_view_room_draws_the_engine_grid_north_up():
    view = director_rooms.render_room(dict(SCENE, rooms=dict(SCENE["rooms"], hall=dict(
        SCENE["rooms"]["hall"], anchors={"bench": {"desc": "an oak bench", "dir": "s"}}))),
        "hall")
    assert "D" in view["map"][0]               # the north doorway, on the top row
    assert len(view["map"]) == 4 and len(view["map"][0]) == 6
    assert any("bench" in line and "engine read" in line for line in view["legend"])


def test_check_reports_owed_rooms_and_new_contradictions():
    draft = {"rooms": {"gallery": {"name": "Gallery", "size": "tiny",
                                   "extent": {"w": 20, "d": 20}}},
             "remove_rooms": [], "remove_adjacent": []}
    result = director_rooms._check(SCENE, draft, owed=["gallery", "cellar"])
    assert result["owed_not_drafted"] == ["cellar"]
    assert any("gallery" in e.casefold() or "Gallery" in e for e in result["errors"])
    assert result["clean"] is False


def test_the_designer_works_in_steps_and_sees_its_results():
    steps = iter([
        {"calls": [{"tool": "inspect_rooms", "args": {"room_ids": ["hall"]}},
                   {"tool": "draft_room", "args": {"room_id": "gallery", "room": {
                       "name": "Gallery", "extent": {"w": 4, "d": 3}, "size": "small"}}}]},
        {"calls": [{"tool": "draft_room", "args": {"room_id": "gallery", "room": {
            "anchors": {"rail": {"desc": "an iron rail", "dir": "n"}},
            "adjacent": [{"to": "hall", "barrier": "open", "dir": "s"}]}}},
                   {"tool": "view_room", "args": {"room_id": "gallery"}}]},
        {"calls": [{"tool": "check", "args": {}}, {"tool": "submit", "args": {}}]},
    ])
    seen = []

    def call(system, payload):
        seen.append(payload)
        return next(steps)

    record = {}
    draft = director_rooms.design_rooms(None, SCENE, {"prose": "x"}, "sheet",
                                        ["gallery"], call, record)
    gallery = draft["rooms"]["gallery"]
    assert gallery["name"] == "Gallery" and "rail" in gallery["anchors"]
    assert gallery["adjacent"][0]["to"] == "hall"
    assert record["steps"] == 3 and record["stopped"] == "submitted"
    # Each step saw what the previous ones returned.
    assert seen[1]["transcript"][0]["tool"] == "inspect_rooms"
    assert "map" in seen[2]["transcript"][-1]["result"]


def test_the_designer_stops_at_its_step_cap(monkeypatch):
    monkeypatch.setattr(director_rooms, "MAX_ROOM_STEPS", 2)
    record = {}
    director_rooms.design_rooms(None, SCENE, {}, "sheet", [], lambda s, p: {
        "calls": [{"tool": "check", "args": {}}]}, record)
    assert record["steps"] == 2 and record["stopped"] == "steps"


def test_a_planned_room_the_beat_enters_is_developed_under_its_id(temp_db, monkeypatch):
    """The Writers' Room plans; the beat that arrives develops. Jev says the
    passage enters the planned stub; the designer develops it under the
    plan's id, and the encoder places into that id from the start."""
    from agents import director_prose
    temp_db.set_setting("director_contract", "prose")
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
    out = director.director_resolve(_make_ctx(temp_db, interp=_action_interp()), nonce=0)
    by_key = {c["step_key"]: c for c in calls}
    assert by_key["director_rooms"]["payload"]["develop"] == planned
    assert "lamp_gallery" in by_key["director_specialist"]["payload"]["new_places"]
    assert out["state_diff"]["positions"]["Mara"] == "lamp_gallery"
    assert "lamp_gallery" in out["state_diff"]["rooms"]
    rooms = out["orchestration"]["prose_contract"]["room_author"]
    assert rooms["develop"] == ["lamp_gallery"] and rooms["stopped"] == "submitted"
