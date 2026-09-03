"""The world-context compiler replaces the two mapping model stages.

`agents/mapping.compile_world_context` assembles a beat's world context from
the story's own rows -- deterministically, with no model role -- and refuses
the one thing the stages it replaced also did: inventing. Where
`mapping_stage` staged a room for a door the plan had not drawn, the
compiler records a typed planning need (`world/planning_needs.py`) and the
Director renders the surface. These tests pin the contract: what the step
carries, what it never carries, what it records, and that no provider is
ever asked.
"""

from __future__ import annotations

import time

import pytest

import agents.mapping as mapping
from core.db import wset
from core.pipeline_context import ChatData, PipelineContext, TurnData


def _ctx(temp_db, *, interp=None, scene=None, frame_id=None, idx=4):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Compiled", "A harbour town.", time.time()))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, idx, "go", time.time()))
    wset(cid, "scene", scene if scene is not None else {
        "rooms": {"quay": {"name": "The Quay", "desc": "Wet stone.",
                           "adjacent": [{"to": "warehouse", "barrier": "open"}]},
                  "warehouse": {"name": "Bond Warehouse", "adjacent": []}},
        "positions": {"Wren": "quay"},
    })
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Compiled", persona_id=None, lorebook_id=None,
                      scenario="A harbour town.", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=cid, idx=idx, player_input="go",
                      created=time.time(), frame_id=frame_id),
        cast=[], input="go")
    if interp is not None:
        ctx.director_interpret = interp
    return ctx


@pytest.fixture
def no_retrieval(monkeypatch):
    calls = []
    monkeypatch.setattr(mapping, "search_lore",
                        lambda weights, query, **kw: calls.append((query, kw)) or [])
    return calls


# ---- the step is deterministic and makes no model call -------------------

def test_the_compiler_is_registered_in_place_of_both_mapping_stages():
    from agents import runtime
    assert "compile_world_context" in runtime.STEP_HANDLERS
    assert "mapping_stage" not in runtime.STEP_HANDLERS
    assert "mapping_quick" not in runtime.STEP_HANDLERS
    assert "compile_world_context" in runtime.STEP_LABELS
    plan = [k for k, _ in runtime.build_plan(
        {"flow": {"needs_mapping": True, "reactors": []}}, [])]
    assert plan[:3] == ["director_interpret", "compile_world_context", "perception_act"]
    plan = [k for k, _ in runtime.build_plan(
        {"flow": {"needs_mapping": False, "reactors": []}}, [])]
    assert plan[1] == "compile_world_context", "one step whatever the flag says"
    assert [k for k, _ in runtime.establishment_plan()][0] == "compile_world_context"


def test_there_is_no_mapping_model_role_and_no_schema():
    from llm.providers import ROLES
    from llm.schemas import SCHEMA_MAP
    assert "mapping" not in ROLES
    assert "mapping_stage" not in SCHEMA_MAP and "mapping_commit" not in SCHEMA_MAP


def test_the_compiler_imports_no_model_seam():
    import inspect
    src = inspect.getsource(mapping)
    assert "_agent_json" not in src
    assert "complete_validated_json" not in src
    assert "get_prompt" not in src


def test_the_same_inputs_compile_to_the_same_output(temp_db, no_retrieval):
    ctx = _ctx(temp_db, interp={"sequence": [], "movement": None, "flow": {}})
    first = mapping.compile_world_context(ctx, nonce=0)
    second = mapping.compile_world_context(ctx, nonce=7)
    assert first == second, "a reroll of a compilation is the same compilation"
    assert first["compiled"] is True


# ---- what it carries, and what it never carries ---------------------------

def test_relevant_lore_is_the_engines_own_rows(temp_db, monkeypatch):
    rows = [{"id": 5, "entry_uid": "e5", "book_id": 3, "keys": "quay",
             "content": "The quay floods at spring tide.", "category": "location",
             "locked": 0, "embedding": [0.1], "score": 0.9}]
    monkeypatch.setattr(mapping, "search_lore", lambda *a, **k: [dict(r) for r in rows])
    monkeypatch.setattr(mapping, "_books", lambda ctx, refresh=False: [3])
    monkeypatch.setattr(mapping, "_book_weights", lambda ctx, refresh=False: {3: 1.0})
    ctx = _ctx(temp_db, interp={"sequence": [], "movement": None, "flow": {}})
    out = mapping.compile_world_context(ctx, nonce=0)
    assert out["relevant_lore"] == [{
        "id": 5, "entry_uid": "e5", "book_id": 3, "keys": "quay",
        "content": "The quay floods at spring tide.", "category": "location",
        "locked": 0}], "verbatim rows, no echo, no embedding on the step"
    assert out["relevant_books"] == [3]


def test_the_compiler_never_stages_and_never_patches(temp_db, no_retrieval):
    ctx = _ctx(temp_db, interp={
        "sequence": [], "location_query": "the drowned chapel",
        "movement": {"to_room": "drowned_chapel", "why": "the bell"},
        "flow": {"needs_mapping": True, "mapping_request": "new room: the chapel"}})
    out = mapping.compile_world_context(ctx, nonce=0)
    assert out["staged_lore"] == []
    assert all(not v for v in out["scene_patch"].values())


def test_the_cache_is_merged_after_fresh_rows_and_capped(temp_db, monkeypatch):
    fresh = [{"id": i, "book_id": 1, "keys": f"k{i}", "content": f"c{i}"}
             for i in range(10)]
    monkeypatch.setattr(mapping, "search_lore", lambda *a, **k: list(fresh))
    ctx = _ctx(temp_db, interp={"sequence": [], "movement": None, "flow": {}})
    wset(ctx.chat.id, "lore_cache", [
        {"id": 3, "book_id": 1, "keys": "k3", "content": "stale c3"},
        {"id": 40, "book_id": 1, "keys": "k40", "content": "cached only"},
        {"id": 41, "book_id": 1, "keys": "k41", "content": "cached only 2"},
        {"id": 42, "book_id": 1, "keys": "k42", "content": "cached only 3"}])
    out = mapping.compile_world_context(ctx, nonce=0)
    ids = [e["id"] for e in out["relevant_lore"]]
    assert ids[:10] == list(range(10)), "fresh first"
    assert 3 in ids and out["relevant_lore"][3]["content"] == "c3", "fresh revision wins"
    assert len(ids) == mapping.WORLD_CONTEXT_LORE_CAP


# ---- movement classification and planning needs ---------------------------

def test_a_known_destination_raises_no_need(temp_db, no_retrieval):
    ctx = _ctx(temp_db, interp={"sequence": [], "flow": {},
                                "movement": {"to_room": "warehouse"}})
    out = mapping.compile_world_context(ctx, nonce=0)
    assert out["movement"] == {"to_room": "warehouse", "status": "known"}
    assert out["planning_needs"] == []


def test_an_unplanned_destination_is_a_room_need(temp_db, no_retrieval):
    ctx = _ctx(temp_db, interp={
        "sequence": [], "flow": {"mapping_request": "a chapel by the water"},
        "movement": {"to_room": "drowned_chapel", "why": "follow the bell"}})
    out = mapping.compile_world_context(ctx, nonce=0)
    assert out["movement"]["status"] == "unplanned"
    (need,) = out["planning_needs"]
    assert need["kind"] == "room"
    assert need["reason"] == "declared_destination_unplanned"
    assert need["subject"] == "drowned_chapel"
    assert need["surface"] == {"why": "follow the bell",
                               "request": "a chapel by the water"}
    assert need["status"] == "open" and need["raised_turn"] == 4


def test_a_planned_destination_carries_the_plan_and_no_need(temp_db, no_retrieval, monkeypatch):
    from world import structure
    monkeypatch.setattr(structure, "planned_context", lambda cid, query: {
        "room_uid": "chapel", "name": "Drowned Chapel", "purpose": "worship",
        "structure": "", "access": "", "adjacent": ["The Quay"]}
        if "chapel" in str(query) else None)
    ctx = _ctx(temp_db, interp={"sequence": [], "flow": {},
                                "movement": {"to_room": "chapel"}})
    out = mapping.compile_world_context(ctx, nonce=0)
    assert out["movement"]["status"] == "planned"
    assert out["planned"]["name"] == "Drowned Chapel"
    assert out["planning_needs"] == []


def test_a_location_query_the_scene_answers_raises_nothing(temp_db, no_retrieval):
    ctx = _ctx(temp_db, interp={"sequence": [], "flow": {}, "movement": None,
                                "location_query": "Bond Warehouse"})
    out = mapping.compile_world_context(ctx, nonce=0)
    assert out["location_query"] == {"query": "Bond Warehouse", "status": "known"}
    assert out["planning_needs"] == []


def test_a_location_query_nobody_answers_is_a_need(temp_db, no_retrieval):
    ctx = _ctx(temp_db, interp={"sequence": [], "flow": {}, "movement": None,
                                "location_query": "the customs house"})
    out = mapping.compile_world_context(ctx, nonce=0)
    assert out["location_query"]["status"] == "unmatched"
    (need,) = out["planning_needs"]
    assert (need["kind"], need["reason"], need["subject"]) == (
        "room", "location_query_unmatched", "the customs house")


def test_one_door_reached_twice_in_a_beat_is_one_need(temp_db, no_retrieval):
    ctx = _ctx(temp_db, interp={
        "sequence": [], "flow": {"generation_requests": [
            {"kind": "room", "subject": "drowned_chapel"},
            {"kind": "room", "subject": "drowned_chapel"}]},
        "movement": {"to_room": "drowned_chapel"}})
    out = mapping.compile_world_context(ctx, nonce=0)
    reasons = sorted(n["reason"] for n in out["planning_needs"])
    assert reasons == ["declared_destination_unplanned", "generation_request"]
    ids = [n["need_id"] for n in out["planning_needs"]]
    assert len(ids) == len(set(ids))


def test_a_need_id_is_stable_across_reruns_and_frames_apart(temp_db, no_retrieval):
    interp = {"sequence": [], "flow": {}, "movement": {"to_room": "drowned_chapel"}}
    a = mapping.compile_world_context(_ctx(temp_db, interp=interp), nonce=0)
    b = mapping.compile_world_context(_ctx(temp_db, interp=interp), nonce=1)
    c = mapping.compile_world_context(_ctx(temp_db, interp=interp, frame_id=9), nonce=0)
    assert a["planning_needs"][0]["need_id"] == b["planning_needs"][0]["need_id"]
    assert a["planning_needs"][0]["need_id"] != c["planning_needs"][0]["need_id"]


# ---- the owed-history seam keeps its one reader ---------------------------

def test_owed_history_is_attached_where_the_place_is_compiled(temp_db, monkeypatch):
    from world import living_world
    rows = [{"id": 1, "book_id": 1, "keys": "quay", "content": "Wet stone.",
             "category": "location"}]
    monkeypatch.setattr(mapping, "search_lore", lambda *a, **k: [dict(r) for r in rows])
    seen = {}

    def attach(cid, hits):
        seen["hits"] = list(hits)
        out = [dict(h) for h in hits]
        out[0]["content"] += " A debt: the ferry never came."
        return out
    monkeypatch.setattr(living_world, "attach_owed_history", attach)
    ctx = _ctx(temp_db, interp={"sequence": [], "movement": None, "flow": {}})
    out = mapping.compile_world_context(ctx, nonce=0)
    assert seen["hits"], "the obligation ledger's one consumer is the compiler"
    assert "the ferry never came" in out["relevant_lore"][0]["content"]
    assert out["owed_history_attached"] == 1


# ---- the one read every consumer goes through -----------------------------

def test_world_context_reads_the_compiler_or_a_retired_stage(temp_db):
    ctx = _ctx(temp_db)
    assert ctx.world_context() == {}
    ctx["mapping_quick"] = {"relevant_lore": [{"id": 1}], "staged_lore": []}
    assert ctx.world_context()["relevant_lore"] == [{"id": 1}], (
        "a turn stored before the compiler hydrates its retired step into "
        "_extra and is read through the same seam")
    ctx.compile_world_context = {"relevant_lore": [{"id": 2}]}
    assert ctx.world_context()["relevant_lore"] == [{"id": 2}]
    from agents.common import lore_for
    assert lore_for(ctx) == [{"id": 2}]


def test_the_director_payloads_carry_needs_and_no_proposal(temp_db, monkeypatch):
    """The prose author and the spatial hand receive `planning_needs`; the
    mapping proposal field is gone with the model that authored it."""
    import inspect
    from agents import director, director_fanout
    src = inspect.getsource(director) + inspect.getsource(director_fanout)
    assert "mapping_scene_proposal" not in src
    assert '"planning_needs"' in src
    assert "planning_need" in director._PROSE_DUTY_GATES
    assert "mapping_proposal" not in director._PROSE_DUTY_GATES
