"""A room is named by its whole spelling, never by the letters inside a word.

`planned_context`'s loose tier and `planned_rooms_named_in` tested a folded
spelling with `key in folded`, and the compiler's location-query reader did
the same over the scene's rooms. Measured (audits of 2026-11-01,
agents_runtime_loops_mapping F5 and world_layout_bridge_structure F8): a
planned `inn` answered "the spinning mill", "Finnegan's forge" and "the inner
keep", a planned `hall` answered "a shallow ford", and the scenario sentence
"the spinning room of a marshall's house" handed the opening Director the
residents of the inn AND the hall. The declared walk to the spinning mill was
made canonical as the inn (`canonical_movement`), so the beat walked the
player into the inn and no planning need was filed.

A spelling now stands in a description only as a whole name, in whatever
script it is written (`language_runtime.find_names`, each end bounded by
`name_boundary_pattern`), and where one spelling sits inside another the
longest is the one named.
"""

from __future__ import annotations

import time

import pytest

import agents.mapping as mapping
from core.db import wset
from core.pipeline_context import ChatData, PipelineContext, TurnData
from world.structure import (planned_context, planned_rooms_named_in,
                             plant_structure, rooms_named_whole)


def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Whole names", "", time.time()))


def _plant(cid, rooms):
    plant_structure(cid, {"key": "town", "max_planned": 32, "grammar": []}, {
        uid: {"name": name, "purpose": "a place", "access": "public",
              "adjacent": [], "frontier": []}
        for uid, name in rooms.items()})


# ---- the one matcher ---------------------------------------------------------

def test_a_spelling_inside_another_word_names_no_room():
    rooms = {"inn": ["inn", "Inn"], "hall": ["hall", "Hall"]}
    for text in ("the spinning mill", "Finnegan's forge", "the inner keep",
                 "dinner at the Ferrier house", "a shallow ford",
                 "the spinning room of a marshall's house"):
        assert rooms_named_whole(text, rooms) == set(), text


def test_a_whole_spelling_names_its_room_however_it_is_written():
    rooms = {"reeves_hall": ["reeves_hall", "Reeve's Hall"], "inn": ["inn"]}
    assert rooms_named_whole("reeves_hall interior and occupants",
                             rooms) == {"reeves_hall"}
    assert rooms_named_whole("the Inn's back room", rooms) == {"inn"}
    assert rooms_named_whole("INN", rooms) == {"inn"}


def test_the_longest_spelling_is_the_one_named():
    rooms = {"hall": ["hall"], "great_hall": ["great_hall", "Great Hall"]}
    assert rooms_named_whole("past the screens into the great hall",
                             rooms) == {"great_hall"}
    assert rooms_named_whole("the great hall, then the hall",
                             rooms) == {"great_hall", "hall"}


def test_a_name_in_a_script_without_spaces_is_found_where_it_stands():
    rooms = {"yadoya": ["yadoya", "宿屋"], "hall_jp": ["hall_jp", "ホール"]}
    assert rooms_named_whole("宿屋の裏手へ", rooms) == {"yadoya"}
    # katakana inside a longer katakana word is another word
    assert rooms_named_whole("マーシャルホールへ", rooms) == set()
    assert rooms_named_whole("ホールで待つ", rooms) == {"hall_jp"}


# ---- the plan's readers --------------------------------------------------------

def test_the_plan_answers_no_description_its_room_sits_inside(temp_db):
    cid = _chat(temp_db)
    _plant(cid, {"inn": "Inn", "hall": "Hall"})
    for query in ("the spinning mill", "Finnegan's forge", "the inner keep",
                  "a shallow ford"):
        assert planned_context(cid, query) is None, query


def test_the_plan_still_answers_a_description_that_names_its_room(temp_db):
    cid = _chat(temp_db)
    _plant(cid, {"inn": "Inn"})
    hit = planned_context(cid, "the Inn's back room")
    assert hit is not None and hit["room_uid"] == "inn"


def test_the_plan_answers_the_longest_name_a_query_holds(temp_db):
    """Two rooms whose spellings sit one inside the other: the loose tier
    used to see both and refuse the query as ambiguous."""
    cid = _chat(temp_db)
    _plant(cid, {"hall": "Hall", "great_hall": "Great Hall"})
    hit = planned_context(cid, "the great hall, past the screens")
    assert hit is not None and hit["room_uid"] == "great_hall"


def test_a_scenario_names_only_the_rooms_it_names_whole(temp_db):
    cid = _chat(temp_db)
    _plant(cid, {"inn": "Inn", "hall": "Hall", "great_hall": "Great Hall"})
    assert planned_rooms_named_in(
        cid, "the spinning room of a marshall's house") == []
    assert planned_rooms_named_in(
        cid, "supper at the inn, then up to the great hall") == [
            "great_hall", "inn"]


def test_the_plan_reads_a_japanese_name(temp_db):
    cid = _chat(temp_db)
    _plant(cid, {"yadoya": "宿屋", "hall_jp": "ホール"})
    hit = planned_context(cid, "宿屋の裏手へ")
    assert hit is not None and hit["room_uid"] == "yadoya"
    assert planned_context(cid, "マーシャルホールへ") is None
    assert planned_rooms_named_in(cid, "宿屋で夕食をとる") == ["yadoya"]


# ---- the compiler ----------------------------------------------------------------

@pytest.fixture
def no_retrieval(monkeypatch):
    monkeypatch.setattr(mapping, "search_lore", lambda *a, **k: [])


def _ctx(db, cid, interp):
    turn_id = db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, 4, "go", time.time()))
    wset(cid, "scene", {
        "rooms": {"quay": {"name": "The Quay", "desc": "Wet stone.",
                           "adjacent": []}},
        "positions": {"Wren": "quay"}})
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Whole names", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=cid, idx=4, player_input="go",
                      created=time.time()),
        cast=[], input="go")
    ctx.director_interpret = interp
    return ctx


def test_a_walk_to_a_place_the_plan_does_not_hold_is_a_need(temp_db,
                                                             no_retrieval):
    cid = _chat(temp_db)
    _plant(cid, {"inn": "Inn"})
    ctx = _ctx(temp_db, cid, {"sequence": [], "flow": {}, "movement": {
        "to_room": "the spinning mill", "why": "to find the miller"}})
    out = mapping.compile_world_context(ctx, nonce=0)
    assert out["movement"] == {"to_room": "the spinning mill",
                               "status": "unplanned"}
    assert [n["reason"] for n in out["planning_needs"]] == [
        "declared_destination_unplanned"]


def test_a_held_room_does_not_answer_a_query_for_a_word_it_sits_inside():
    scene = {"rooms": {"inn": {"name": "Inn"}}}
    nothing = lambda _query: None  # noqa: E731 -- no plan
    assert mapping._location_query_status(
        "the inner keep", scene, planned_for=nothing) == "unmatched"
    assert mapping._location_query_status(
        "the old spinning mill", scene, planned_for=nothing) == "unmatched"
    assert mapping._location_query_status(
        "the inn's cellar", scene, planned_for=nothing) == "known"


def test_a_held_room_answers_a_query_in_its_own_script():
    scene = {"rooms": {"yadoya": {"name": "宿屋"}}}
    nothing = lambda _query: None  # noqa: E731
    assert mapping._location_query_status(
        "宿屋の二階", scene, planned_for=nothing) == "known"
    assert mapping._location_query_status(
        "鍛冶屋", scene, planned_for=nothing) == "unmatched"
