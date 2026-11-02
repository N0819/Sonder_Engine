"""A request that states no kind is one kind everywhere it is read.

The compiler read a kindless `generation_request` as a ROOM when it asked
the plan (`str(request.get("kind") or "room") == "room"`) and the ledger
filed the same request as a PERSON (`kind = declared_kind or "person"`), so a
declared rope, door or rumour went to the person drain, which can never enrol
a surface with no name and so re-queued it every beat (audit of 2026-11-01,
world_misc_causal F9 and F10). A declared PLACE the plan holds was never
checked against the plan at all, because "place" is not "room".

An unstated kind is now the closed set's catch-all, `thing`, in both readers,
and the plan answers any request it holds a room for unless the request
says it is a person or a thing.
"""

from __future__ import annotations

import time

import pytest

import agents.mapping as mapping
from core.db import wset
from core.pipeline_context import ChatData, PipelineContext, TurnData
from world.planning_needs import need_kind, planning_need
from world.structure import plant_structure


def test_an_unstated_kind_is_the_catch_all():
    assert need_kind(None) == need_kind("") == need_kind("  ") == "thing"
    assert need_kind("Room") == "room" and need_kind("person") == "person"
    assert need_kind("gizmo") == "thing"
    for kind in (None, ""):
        need = planning_need(kind, "generation_request", subject="a coil of rope")
        assert need["kind"] == "thing"
        assert "declared_kind" not in need["surface"]


@pytest.fixture
def no_retrieval(monkeypatch):
    monkeypatch.setattr(mapping, "search_lore", lambda *a, **k: [])


def _compile(db, requests):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Kinds", "", time.time()))
    plant_structure(cid, {"key": "harbour", "max_planned": 8, "grammar": []}, {
        "boathouse": {"name": "Boathouse", "purpose": "boats",
                      "access": "public", "adjacent": [], "frontier": []}})
    turn_id = db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, 2, "go", time.time()))
    wset(cid, "scene", {"rooms": {"quay": {"name": "Quay", "adjacent": []}},
                        "positions": {"Wren": "quay"}})
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Kinds", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=cid, idx=2, player_input="go",
                      created=time.time()),
        cast=[], input="go")
    ctx.director_interpret = {"sequence": [], "flow": {
        "generation_requests": requests}}
    return mapping.compile_world_context(ctx, nonce=0)["planning_needs"]


def test_a_kindless_request_the_plan_does_not_hold_is_a_thing(temp_db,
                                                              no_retrieval):
    needs = _compile(temp_db, [{"subject": "a coil of tarred rope"}])
    assert [(n["kind"], n["reason"]) for n in needs] == [
        ("thing", "generation_request")]


def test_the_plan_answers_a_request_for_a_room_it_holds_whatever_the_kind_word(
        temp_db, no_retrieval):
    for kind in (None, "room", "place"):
        request = {"subject": "the boathouse"}
        if kind:
            request["kind"] = kind
        assert _compile(temp_db, [request]) == [], kind


def test_a_request_that_says_person_or_thing_is_filed_as_it_says(
        temp_db, no_retrieval):
    needs = _compile(temp_db, [{"kind": "person", "subject": "the boathouse"}])
    assert [n["kind"] for n in needs] == ["person"]
