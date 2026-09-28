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
                       "name": "Gallery", "extent": {"w": 4, "d": 3}, "size": "tiny"}}}]},
        {"calls": [{"tool": "draft_room", "args": {"room_id": "gallery", "room": {
            "anchors": {"rail": {"desc": "an iron rail", "dir": "n"}},
            "adjacent": [{"to": "hall", "barrier": "open", "dir": "n"}]}}},
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
    # Each step saw what the previous ones returned: its own calls' results,
    # then the check the engine ran because the step changed the draft.
    assert seen[1]["transcript"][0]["tool"] == "inspect_rooms"
    last_step = [e for e in seen[2]["transcript"] if e["step"] == 2]
    assert "map" in last_step[-2]["result"]
    assert last_step[-1]["tool"] == "check" and last_step[-1]["by"] == "engine"
    assert record["calls"] == 6 and record["auto_checks"] == 2


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


def _stacked(anchors):
    return {"rooms": {"gallery": {"name": "Gallery", "extent": {"w": 4, "d": 3},
                                  "size": "small", "anchors": anchors,
                                  "adjacent": [{"to": "hall", "barrier": "open",
                                                "dir": "s"}]}},
            "remove_rooms": [], "remove_adjacent": []}


def test_two_fixtures_on_one_cell_at_one_height_are_reported():
    """Measured on chat 137 turn 11: a washstand and a chair shared cells
    with other fixtures and simply vanished from the drawn plan."""
    both = _stacked({"stool": {"desc": "a stool", "dir": "n", "cell": [1, 1]},
                     "chair": {"desc": "a chair", "dir": "n", "cell": [1, 1]}})
    result = director_rooms._check(SCENE, both, owed=["gallery"])
    assert result["fixtures_overlapping"] and result["clean"] is False
    view = director_rooms.render_room(director_rooms._merged(SCENE, both), "gallery")
    assert any("!" in row for row in view["map"])


def test_submit_is_refused_until_the_check_is_clean():
    steps = iter([
        {"calls": [{"tool": "submit", "args": {}}], "done": True},
        {"calls": [{"tool": "draft_room", "args": {"room_id": "gallery", "room": {
            "name": "Gallery", "size": "tiny", "extent": {"w": 4, "d": 3},
            "adjacent": [{"to": "hall", "barrier": "open", "dir": "n"}]}}},
                   {"tool": "submit", "args": {}}]},
    ])
    record = {}
    draft = director_rooms.design_rooms(None, SCENE, {}, "sheet", ["gallery"],
                                        lambda s, p: next(steps), record)
    assert "gallery" in draft["rooms"]
    assert record["steps"] == 2 and record["stopped"] == "submitted"


def test_a_prepared_design_starts_in_the_draft():
    """A room designed between turns seeds the in-turn designer, which only
    adapts it: submitting at once keeps the prepared design whole."""
    prepared = {"gallery": {"name": "Gallery", "size": "tiny", "extent": {"w": 4, "d": 3},
                            "adjacent": [{"to": "hall", "barrier": "open", "dir": "n"}],
                            "anchors": {"rail": {"desc": "an iron rail", "dir": "n"}}}}
    record = {}
    draft = director_rooms.design_rooms(None, SCENE, {}, "sheet", ["gallery"], lambda s, p: {
        "calls": [{"tool": "submit", "args": {}}]}, record, seed=prepared)
    assert draft["rooms"]["gallery"]["anchors"]["rail"]["desc"] == "an iron rail"
    assert record["prepared"] == ["gallery"] and record["steps"] == 1


def test_rooms_beside_the_player_are_prepared_between_turns(temp_db, monkeypatch):
    """After a prose-contract turn commits, the planned stubs beside the
    player are designed out of band and cached for the beat that enters one."""
    import agents.common as common
    from core import jobs
    from world import structure
    temp_db.set_setting("director_contract", "prose")
    ctx = _make_ctx(temp_db, interp=_action_interp())
    temp_db.wset(ctx.chat.id, "scene", dict(SCENE, positions={"The Stranger": "hall"}))
    brief = {"study": {"name": "Study", "purpose": "a quiet room", "exits": {}}}
    monkeypatch.setattr(structure, "planned_room_brief", lambda cid, sc, ids: brief)
    monkeypatch.setattr(common, "_agent_json", lambda *a, **k: {"calls": [
        {"tool": "draft_room", "args": {"room_id": "study", "room": {
            "name": "Study", "desc": "Shelves and a desk."}}},
        {"tool": "submit", "args": {}}]})
    job = director_rooms.schedule_room_predevelopment(ctx)
    assert job is not None
    import time
    deadline = time.monotonic() + 10.0
    while job.state in ("pending", "running") and time.monotonic() < deadline:
        time.sleep(0.02)
    assert job.state == "done", job.as_dict()
    assert director_rooms.prepared_rooms(ctx.chat.id, ["study"])["study"]["desc"] == \
        "Shelves and a desk."


def test_nothing_is_prepared_under_the_causal_contract(temp_db):
    ctx = _make_ctx(temp_db, interp=_action_interp())
    assert director_rooms.schedule_room_predevelopment(ctx) is None


# ---- code takes the steps a model did not need to (2026-09-27) --------------

#: The hall of SCENE with a neighbour behind a solid wall on its east side.
WALLED = dict(SCENE, rooms=dict(
    SCENE["rooms"],
    hall=dict(SCENE["rooms"]["hall"], adjacent=SCENE["rooms"]["hall"]["adjacent"] + [
        {"to": "cellar", "barrier": "wall", "dir": "e"}]),
    cellar={"name": "Cellar", "desc": "A cellar.", "adjacent": []}))
GALLERY = {"name": "Gallery", "size": "small", "shape": "rectangle"}


def test_doorways_that_fit_skip_every_wall_already_taken():
    """The layout check lays out only what a body can pass through, so a
    room behind a solid wall is invisible to it; a wall holding a doorway
    or a neighbour of any kind is never offered."""
    import time
    fits = director_rooms._doorways_that_fit(WALLED, "gallery", GALLERY, ["hall"],
                                             time.time() + 5)
    walls = {f["their_wall"] for f in fits}
    assert "n" not in walls and "e" not in walls        # the study; the cellar
    assert {"s", "w"} <= walls
    # Each is the edge as the new place writes it: its own wall faces back.
    south = next(f for f in fits if f["their_wall"] == "s")
    assert south == {"to": "hall", "dir": "n", "their_wall": "s"}


def test_the_floor_offered_for_a_size_is_what_the_engine_reads_as_that_size():
    from world.spatial import size_from_extent
    assert director_rooms._floor_for_size("small") == [13, 24]
    assert director_rooms._floor_for_size("Medium") == [25, 48]
    assert director_rooms._floor_for_size("enormous") is None
    assert size_from_extent({"w": 4, "d": 6}) == "small"      # 24
    assert size_from_extent({"w": 5, "d": 5}) == "medium"     # 25


def test_surroundings_and_placing_reach_the_first_step():
    seen = []

    def call(system, payload):
        seen.append(payload)
        return {"calls": []}

    record = {}
    director_rooms.design_rooms(
        None, WALLED, {"prose": "x", "positions": {"Mara": "hall"},
                       "reserved_places": {"gallery": GALLERY}},
        "sheet", ["gallery"], call, record)
    first = seen[0]
    # The bodies' room and its neighbours past anything but a wall.
    assert list(first["surroundings"]) == ["hall", "study"]
    assert "map" in first["surroundings"]["hall"]
    placing = first["placing"]["gallery"]
    assert placing["floor_square_paces"] == [13, 24]
    assert placing["doorways_that_fit"] and all(
        not (f["to"] == "hall" and f["their_wall"] in ("n", "e"))
        for f in placing["doorways_that_fit"])
    assert record["groundwork"]["surroundings"] == ["hall", "study"]


def test_a_planned_room_nobody_entered_is_not_drawn_but_still_takes_space():
    """Shown empty, a plan's stub reads as work: one run on the lighthouse
    rail developed seven of them in its first step (81.7 s, then the
    wall). It is left out of the drawing and kept in the doorway search."""
    scene = dict(WALLED, rooms=dict(WALLED["rooms"], study={
        "name": "Study", "planned": True,
        "adjacent": [{"to": "hall", "barrier": "open", "dir": "s"}]}))
    seen = []

    def call(system, payload):
        seen.append(payload)
        return {"calls": []}

    record = {}
    director_rooms.design_rooms(
        None, scene, {"prose": "x", "positions": {"Mara": "hall"},
                      "reserved_places": {"gallery": GALLERY}},
        "sheet", ["gallery"], call, record)
    assert list(seen[0]["surroundings"]) == ["hall"]
    assert record["groundwork"]["surroundings"] == ["hall", "study"]
    assert any(f["to"] == "study" for f in seen[0]["placing"]["gallery"]["doorways_that_fit"])


def _gallery_whole(**extra):
    room = {"name": "Gallery", "desc": "A long gallery hung with maps.", "size": "small",
            "extent": {"w": 6, "d": 4}, "adjacent": [{"to": "hall", "barrier": "open",
                                                      "dir": "n"}]}
    room.update(extra)
    return {"tool": "draft_room", "args": {"room_id": "gallery", "room": room}}


def test_the_engine_checks_after_a_draft_and_the_extent_sets_the_size():
    """A size word its extent disagrees with was a check row and a step
    spent relabelling (the yard, 2026-09-27: 'small' at 6x5). The extent
    decides, so code sets the word, and the check runs without being
    asked for."""
    steps = iter([{"calls": [_gallery_whole(size="tiny")]},
                  {"calls": [{"tool": "submit", "args": {}}]}])
    record = {}
    draft = director_rooms.design_rooms(None, SCENE, {}, "sheet", ["gallery"],
                                        lambda s, p: next(steps), record)
    assert draft["rooms"]["gallery"]["size"] == "small"       # 6x4 = 24
    assert record["auto_checks"] == 1 and record["stopped"] == "submitted"


def test_a_planned_room_keeps_its_plans_extent_and_the_size_follows_it():
    """The merge keeps a planned room's measurements, so the size is read
    off the extent the world holds: read off the draft, code wrote 'huge'
    for a 12x10 the merge never took while the designer wrote 'large' for
    the 10x8 it did, four steps running (the stage, 2026-09-27)."""
    scene = dict(SCENE, rooms=dict(SCENE["rooms"], stage={
        "name": "Stage", "planned": True, "extent": {"w": 10, "d": 8},
        "adjacent": [{"to": "hall", "barrier": "open", "dir": "w"}]}))
    steps = iter([{"calls": [{"tool": "draft_room", "args": {"room_id": "stage", "room": {
        "desc": "Boards.", "extent": {"w": 12, "d": 10}, "size": "huge"}}}]},
        {"calls": []}])
    seen = []

    def call(system, payload):
        seen.append(payload)
        return next(steps)

    draft = director_rooms.design_rooms(None, scene, {}, "sheet", ["stage"], call, {})
    assert draft["rooms"]["stage"]["extent"] == {"w": 10, "d": 8}
    assert draft["rooms"]["stage"]["size"] == "large"
    check = [e for e in seen[1]["transcript"] if e["tool"] == "check"][0]["result"]
    assert check["clean"] is True
    assert any("the plan's extent 10x8 stands" in s for s in check["sizes_agreed"])


def test_the_decision_model_finishes_a_clean_design(monkeypatch):
    asked = []

    def answer(state, questions):
        asked.append((state, sorted(questions)))
        return {key: {"type": "noul", "noul": 0.1} for key in questions}

    monkeypatch.setattr(decisions, "OVERRIDE", answer)
    calls = []

    def call(system, payload):
        calls.append(payload)
        return {"calls": [_gallery_whole()], "done": False}

    record = {}
    director_rooms.design_rooms(None, SCENE, {"prose": "Mara studies the maps."},
                                "sheet", ["gallery"], call, record)
    assert len(calls) == 1 and record["stopped"] == "complete"
    state, keys = asked[0]
    assert keys == ["room_done_missing", "room_done_unlisted"]
    assert state.startswith("PASSAGE:\nMara studies the maps.")
    assert "PLACE: Gallery" in state and "A long gallery hung with maps." in state
    assert record["jev"][0]["finished"] is True


def test_what_is_still_missing_comes_back_and_the_loop_goes_on(monkeypatch):
    monkeypatch.setattr(decisions, "OVERRIDE", lambda state, questions: {
        key: {"type": "noul", "noul": 0.9 if key == "room_done_unlisted" else 0.1}
        for key in questions})
    seen = []
    steps = iter([{"calls": [_gallery_whole()]},
                  {"calls": [{"tool": "submit", "args": {}}]}])

    def call(system, payload):
        seen.append(payload)
        return next(steps)

    record = {}
    director_rooms.design_rooms(None, SCENE, {"prose": "Mara leans on the map chest."},
                                "sheet", ["gallery"], call, record)
    assert record["stopped"] == "submitted" and record["steps"] == 2
    note = [e for e in seen[1]["transcript"] if e["tool"] == "complete"]
    assert note and note[0]["by"] == "engine"
    assert "not one of its fixtures" in note[0]["result"]["still_missing"][0]


def test_the_fixture_question_has_the_higher_bar(monkeypatch):
    """At 0.5 the fixture question held a finished yard three steps (0.54-
    0.56 on 'at Anselm's shoulder'); its bar is 0.6."""
    monkeypatch.setattr(decisions, "OVERRIDE", lambda state, questions: {
        key: {"type": "noul", "noul": 0.56 if key == "room_done_unlisted" else 0.3}
        for key in questions})
    record = {}
    director_rooms.design_rooms(None, SCENE, {"prose": "Luca stands at his shoulder."},
                                "sheet", ["gallery"], lambda s, p: {"calls": [_gallery_whole()]},
                                record)
    assert record["stopped"] == "complete" and record["steps"] == 1


def test_what_is_missing_is_said_once(monkeypatch):
    """A reader that can be wrong, repeated every step, is chased: the note
    goes out once, and the design stays unfinished while it holds."""
    monkeypatch.setattr(decisions, "OVERRIDE", lambda state, questions: {
        key: {"type": "noul", "noul": 0.9} for key in questions})
    monkeypatch.setattr(director_rooms, "MAX_ROOM_STEPS", 3)
    seen = []

    def call(system, payload):
        seen.append(payload)
        return {"calls": [_gallery_whole()]}

    record = {}
    director_rooms.design_rooms(None, SCENE, {"prose": "x"}, "sheet", ["gallery"], call, record)
    notes = [e for e in seen[-1]["transcript"] if e["tool"] == "complete"]
    assert len(notes) == 1 and record["still_missing_said"] == 1
    assert "never written into a room's text" in notes[0]["result"]["if_not"]
    assert record["stopped"] == "steps" and len(record["jev"]) == 3


def test_an_unanswered_decision_leaves_the_design_to_the_model(monkeypatch):
    def refuse(state, questions):
        raise decisions.DecisionError("unreachable")

    monkeypatch.setattr(decisions, "OVERRIDE", refuse)
    steps = iter([{"calls": [_gallery_whole()]},
                  {"calls": [{"tool": "submit", "args": {}}]}])
    record = {}
    director_rooms.design_rooms(None, SCENE, {"prose": "x"}, "sheet", ["gallery"],
                                lambda s, p: next(steps), record)
    assert record["stopped"] == "submitted" and record["steps"] == 2
    assert "failed" in record["jev"][0]


def test_a_prepared_design_can_be_finished_before_any_step(monkeypatch):
    monkeypatch.setattr(decisions, "OVERRIDE", lambda state, questions: {
        key: {"type": "noul", "noul": 0.1} for key in questions})
    prepared = {"gallery": _gallery_whole()["args"]["room"]}

    def call(system, payload):
        raise AssertionError("no model step is needed")

    record = {}
    draft = director_rooms.design_rooms(None, SCENE, {"prose": "Mara studies the maps."},
                                        "sheet", ["gallery"], call, record, seed=prepared)
    assert draft["rooms"]["gallery"]["desc"] == "A long gallery hung with maps."
    assert record["steps"] == 0 and record["stopped"] == "complete"


def test_a_doorway_leaves_the_draft_but_never_the_world():
    """A designer that could only add doorways circled five steps round one
    it could not take back (the yard, 2026-09-27). `drop` takes it out of
    the DRAFT; a standing doorway is not in the draft to drop."""
    room = director_rooms._merge_room(
        {"adjacent": [{"to": "hall", "barrier": "open", "dir": "n"},
                      {"to": "study", "barrier": "open", "dir": "e"}]},
        {"adjacent": [{"to": "hall", "drop": True}]})
    assert [e["to"] for e in room["adjacent"]] == ["study"]
    steps = iter([{"calls": [{"tool": "draft_room", "args": {"room_id": "study", "room": {
        "adjacent": [{"to": "hall", "drop": True}]}}}, {"tool": "submit", "args": {}}]}])
    draft = director_rooms.design_rooms(None, SCENE, {}, "sheet", [], lambda s, p: next(steps), {})
    merged = director_rooms._merged(SCENE, draft)
    assert any(e.get("to") == "hall" for e in merged["rooms"]["study"]["adjacent"])


def test_a_new_place_that_stands_where_it_cannot_gets_the_walls_that_fit_it():
    """The gallery drafted onto the hall's north wall, where the study
    already is: the check names the collision and hands back where the
    gallery, as drafted, would stand."""
    steps = iter([{"calls": [_gallery_whole(adjacent=[{"to": "hall", "barrier": "open",
                                                        "dir": "s"}])]},
                  {"calls": []}])
    seen = []

    def call(system, payload):
        seen.append(payload)
        return next(steps)

    record = {}
    director_rooms.design_rooms(None, WALLED, {"reserved_places": {"gallery": GALLERY},
                                               "positions": {"Mara": "hall"}},
                                "sheet", ["gallery"], call, record)
    check = [e for e in seen[1]["transcript"] if e["tool"] == "check"][0]["result"]
    assert check["clean"] is False
    fits = check["doorways_that_fit"]["gallery"]
    assert fits and not any(f["to"] == "hall" and f["their_wall"] in ("n", "e") for f in fits)
    assert record["refits"] >= 1


def test_a_new_place_joined_to_nothing_is_not_clean():
    """A harbour café drafted with no doorway at all was called clean. A new
    place is reached from somewhere, unless it is an inside (its way in is
    derived) or its zone says no walk reaches it."""
    def draft(**room):
        return {"rooms": {"gallery": dict({"name": "Gallery", "desc": "x"}, **room)},
                "remove_rooms": [], "remove_adjacent": []}

    alone = director_rooms._check(SCENE, draft(), ["gallery"])
    assert alone["clean"] is False and alone["no_way_in"]["places"] == ["gallery"]
    walled = director_rooms._check(SCENE, draft(adjacent=[{"to": "hall", "barrier": "wall",
                                                           "dir": "n"}]), ["gallery"])
    assert walled["no_way_in"]["places"] == ["gallery"]
    joined = director_rooms._check(SCENE, draft(adjacent=[{"to": "hall", "barrier": "open",
                                                           "dir": "n"}]), ["gallery"])
    assert joined["clean"] is True and "no_way_in" not in joined
    far = director_rooms._check(SCENE, draft(zone="the_capital"), ["gallery"])
    assert "no_way_in" not in far
    inside = director_rooms._check(SCENE, draft(parent_entity="wagon"), ["gallery"])
    assert "no_way_in" not in inside


def test_a_new_id_with_an_owed_places_name_is_that_place():
    """Drafted as `harbour_cafe` against the reserved `harbour_caf`, the café
    was built twice and the stray joined to nothing. The ids given are
    fixed; a standing room is never taken over this way."""
    steps = iter([
        {"calls": [{"tool": "draft_room", "args": {"room_id": "harbour_cafe", "room": dict(
            _gallery_whole()["args"]["room"], name="Harbour Café")}}]},
        {"calls": []}])
    seen = []

    def call(system, payload):
        seen.append(payload)
        return next(steps)

    reserved = {"harbour_caf": {"name": "Harbour Café", "size": "small", "shape": "rectangle"}}
    draft = director_rooms.design_rooms(None, SCENE, {"reserved_places": reserved}, "sheet",
                                        ["harbour_caf"], call, {})
    assert list(draft["rooms"]) == ["harbour_caf"]
    result = [e for e in seen[1]["transcript"] if e["tool"] == "draft_room"][0]["result"]
    assert result["drafted"] == "harbour_caf" and "fixed" in result["drafted_as"]
    assert director_rooms._fold_name("Harbour Café") == director_rooms._fold_name("harbour cafe")


def test_an_overfull_wall_comes_with_its_arithmetic():
    """'needs 7, has 5' sent the yard's designer widening the wrong side
    twice: a west wall runs north-south, so its length is the extent's d."""
    draft = {"rooms": {"gallery": {"name": "Gallery", "desc": "x", "extent": {"w": 8, "d": 3},
                                   "adjacent": [{"to": "hall", "barrier": "open", "dir": "n"}],
                                   "anchors": {
                                       "rack": {"desc": "a rack", "dir": "w", "footprint": "large",
                                                "height": "head"},
                                       "chest": {"desc": "a chest", "dir": "w",
                                                 "footprint": "large", "height": "waist"}}}},
             "remove_rooms": [], "remove_adjacent": []}
    result = director_rooms._check(SCENE, draft, ["gallery"])
    crowded = result["crowded_walls"]
    assert crowded[0]["room"] == "gallery" and crowded[0]["wall"] == "w"
    assert crowded[0]["length_paces"] == 3
    assert crowded[0]["length_is"].startswith("the extent's d")
    assert set(crowded[0]["fixtures_paces"]) == {"rack", "chest"}
    assert sum(crowded[0]["fixtures_paces"].values()) > 3


def test_calls_past_the_step_cap_are_named_not_silently_dropped(monkeypatch):
    monkeypatch.setattr(director_rooms, "MAX_ROOM_CALLS_PER_STEP", 1)
    seen = []
    steps = iter([{"calls": [_gallery_whole(), {"tool": "draft_room", "args": {
        "room_id": "cellar", "room": {"desc": "damp"}}}]}, {"calls": []}])

    def call(system, payload):
        seen.append(payload)
        return next(steps)

    draft = director_rooms.design_rooms(None, SCENE, {}, "sheet", ["gallery"], call, {})
    assert "cellar" not in draft["rooms"]
    note = [e for e in seen[1]["transcript"] if e["tool"] == "calls"][0]
    assert note["by"] == "engine"
    assert note["result"]["not_run"] == [{"tool": "draft_room", "room_id": "cellar"}]


def test_done_is_not_finished_while_the_check_names_a_contradiction():
    """`done` used to end the loop whatever the draft held; like submit, it
    now finishes only a design the check passes."""
    steps = iter([
        {"calls": [_gallery_whole(size=None, extent={"w": "wide", "d": 4})], "done": True},
        {"calls": [_gallery_whole()], "done": True},
    ])
    seen = []

    def call(system, payload):
        seen.append(payload)
        return next(steps)

    record = {}
    director_rooms.design_rooms(None, SCENE, {}, "sheet", ["gallery"], call, record)
    assert record["steps"] == 2 and record["stopped"] == "submitted"
    refusal = [e for e in seen[1]["transcript"] if e["tool"] == "done"]
    assert refusal and refusal[0]["result"]["refused"].startswith("not finished")
