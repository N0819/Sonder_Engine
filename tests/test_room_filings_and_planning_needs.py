"""The filing commit without a model: rooms through the provenance seam,
planning needs onto the frame's ledger.

`persist/commit_mapping` used to hand a `mapping_commit` model the beat's
staged lore and take back its verdict. Now every room the Director's
committed diff described is built as a provisional record, promoted through
`mind/canon_provenance.promote` on the ruling stage's authority, and filed
as a `layout` entry keyed to the room -- and every planning need the
world-context compiler raised is recorded, with the surface the beat
committed attached, so the plan that answers it may not contradict what a
body already saw.
"""

from __future__ import annotations

import time

import pytest

import persist.commit_mapping as cm
from core.db import wget, wset
from core.pipeline_context import ChatData, PipelineContext, TurnData
from world.planning_needs import (
    PLANNING_NEEDS_CAP, fill_planning_need, open_planning_needs,
    planning_need, record_planning_needs)


def _story(temp_db, *, frame_id=None):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Filed", "", time.time()))
    book = temp_db.qi("INSERT INTO lorebooks(name,chat_id) VALUES(?,?)", ("Canon", cid))
    temp_db.qi("INSERT INTO chat_lorebooks(chat_id,lorebook_id) VALUES(?,?)", (cid, book))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, 6, "go", time.time()))
    wset(cid, "scene", {"rooms": {"quay": {"name": "The Quay", "desc": "Wet stone."}},
                        "positions": {}})
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Filed", persona_id=None, lorebook_id=book,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=cid, idx=6, player_input="go",
                      created=time.time(), frame_id=frame_id),
        cast=[], input="go")
    ctx.compile_world_context = {"relevant_lore": [], "relevant_books": [book],
                                 "staged_lore": [], "planning_needs": []}
    ctx.director_resolve = {"state_diff": {}, "resolved_event": "", "summary": "",
                            "dialogue_log": []}
    return ctx, book


@pytest.fixture
def wired(monkeypatch):
    monkeypatch.setattr(cm, "search_lore", lambda *a, **k: [])


def _entries(temp_db, book):
    return [dict(r) for r in temp_db.q(
        "SELECT keys, content, category, knowledge_locations, source_notes "
        "FROM lore_entries WHERE lorebook_id=? ORDER BY id", (book,))]


# ---- the model is gone ------------------------------------------------------

def test_prepare_consults_no_model(monkeypatch):
    import inspect
    src = inspect.getsource(cm)
    assert "complete_validated_json" not in src
    assert "get_prompt" not in src


def test_a_quiet_beat_is_skipped(temp_db, wired):
    ctx, _ = _story(temp_db)
    prepared = cm.prepare_mapping_commit(ctx)
    assert prepared["skipped"] is True and prepared["ops"] == []


# ---- room filings are RETIRED; world facts are needs -------------------------

def test_a_described_room_files_no_lore(temp_db, wired):
    """Until 2026-09-03 every described room became a `layout` lore entry --
    a second representation of the scene, kept so a model stage could
    retrieve it. The registry and the scene are the record of a room; the
    commit files nothing about one."""
    ctx, book = _story(temp_db)
    ctx.director_resolve["state_diff"]["rooms"] = {
        "bond_warehouse": {"name": "Bond Warehouse",
                           "desc": "Crates to the rafters, a smell of tar.",
                           "adjacent": [{"to": "quay", "barrier": "open"}]}}
    prepared = cm.prepare_mapping_commit(ctx)
    assert prepared["skipped"] is True
    assert "rooms_filed" not in prepared["mout"]
    assert _entries(temp_db, book) == []
    src = __import__("inspect").getsource(cm)
    assert "'layout'" not in src and '"layout"' not in src, "no writer files layout"


def test_a_setting_fact_is_a_planning_need_not_a_filing(temp_db, wired):
    """The Director's `world_facts` used to file through a fallback writer.
    A fact with no physical seat is the setting bible's, and the bible is
    the Writers' Room's to file with provenance and a gate: the commit
    records a `setting_fact` need and writes no entry."""
    ctx, book = _story(temp_db)
    ctx.director_resolve["state_diff"]["world_facts"] = [
        {"fact": "Iron burns the fae.", "source": {"kind": "resolved"}},
        {"fact": "From the lore.", "source": {"kind": "lore"}},
        "Salt keeps a door shut.",
    ]
    prepared = cm.prepare_mapping_commit(ctx)
    assert prepared["skipped"] is False and prepared["ops"] == []
    assert prepared["mout"]["facts"] == 2
    kinds = [(n["kind"], n["reason"], n["subject"]) for n in prepared["needs"]]
    assert ("thing", "setting_fact", "Iron burns the fae.") in kinds
    assert ("thing", "setting_fact", "Salt keeps a door shut.") in kinds
    assert all(n["subject"] != "From the lore." for n in prepared["needs"])
    cm.commit_mapping(ctx, "n", prepared=prepared)
    assert _entries(temp_db, book) == []
    opened = open_planning_needs(ctx.chat.id)
    assert {n["reason"] for n in opened} == {"setting_fact"}
    assert opened[0]["surface"]["fact"] == "Iron burns the fae."


def test_a_setting_fact_an_entry_already_covers_raises_no_need(temp_db, monkeypatch):
    ctx, _ = _story(temp_db)
    monkeypatch.setattr(cm, "search_lore", lambda *a, **k: [
        {"content": "Iron burns the fae, as every smith knows."}])
    ctx.director_resolve["state_diff"]["world_facts"] = [
        {"fact": "Iron burns the fae.", "source": {"kind": "resolved"}}]
    assert cm.prepare_mapping_commit(ctx)["skipped"] is True


def test_a_containment_room_need_is_dropped_at_commit(temp_db, wired):
    """Where a body walks is its own; where the world puts it is the
    Director's. A room-need whose committed record carries `parent_entity`
    is a containment room the spatial hand minted the moment a body went
    inside another, and no plan could have held it."""
    ctx, _ = _story(temp_db)
    inside = planning_need("room", "declared_destination_unplanned",
                           subject="Mirelle Sulmirath_throat", turn_idx=6)
    door = planning_need("room", "declared_destination_unplanned",
                         subject="drowned_chapel", turn_idx=6)
    ctx.compile_world_context["planning_needs"] = [inside, door]
    ctx.director_resolve["state_diff"]["rooms"] = {
        "Mirelle Sulmirath_throat": {"name": "Throat", "desc": "Wet dark.",
                                     "parent_entity": "mirelle_sulmirath"},
        "drowned_chapel": {"name": "Drowned Chapel", "desc": "A bell.",
                           "adjacent": [{"to": "quay", "barrier": "open"}]}}
    cm.commit_mapping(ctx, "n", prepared=cm.prepare_mapping_commit(ctx))
    opened = open_planning_needs(ctx.chat.id)
    assert [n["subject"] for n in opened] == ["drowned_chapel"]


# ---- introductions are the Director's typed rows --------------------------

def test_an_untyped_introduction_is_ignored_and_a_typed_one_read(temp_db, wired):
    ctx, _ = _story(temp_db)
    ctx.director_resolve["state_diff"]["introductions"] = [
        "Alice meets Bob", {"who": "Alice"}, {"who": "Alice", "learns": "Bob"}]
    prepared = cm.prepare_mapping_commit(ctx)
    assert prepared["introductions"] == [{"who": "Alice", "learns": "Bob"}]


# ---- planning needs reach the ledger with the committed surface -----------

def test_a_need_is_recorded_at_commit_with_the_rendered_stub(temp_db, wired):
    ctx, _ = _story(temp_db)
    need = planning_need("room", "declared_destination_unplanned",
                         subject="drowned_chapel", surface={"why": "the bell"},
                         turn_idx=6)
    ctx.compile_world_context["planning_needs"] = [need]
    ctx.director_resolve["state_diff"]["rooms"] = {
        "drowned_chapel": {"name": "Drowned Chapel", "desc": "A bell, half under.",
                           "adjacent": [{"to": "quay", "barrier": "open"}]}}
    cm.commit_mapping(ctx, "n", prepared=cm.prepare_mapping_commit(ctx))
    (opened,) = open_planning_needs(ctx.chat.id)
    assert opened["uid"] == need["uid"]
    assert opened["surface"] == {"why": "the bell", "room": "drowned_chapel",
                                 "name": "Drowned Chapel", "exits": ["quay"]}
    assert any("planning need" in w for w in ctx.warnings)


def test_a_rerun_of_the_beat_records_the_need_once(temp_db, wired):
    ctx, _ = _story(temp_db)
    need = planning_need("room", "location_query_unmatched", subject="customs house")
    ctx.compile_world_context["planning_needs"] = [need]
    cm.commit_mapping(ctx, "n", prepared=cm.prepare_mapping_commit(ctx))
    cm.commit_mapping(ctx, "n", prepared=cm.prepare_mapping_commit(ctx))
    assert len(open_planning_needs(ctx.chat.id)) == 1


def test_the_ledger_is_frame_scoped_and_capped(temp_db):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Needs", "", time.time()))
    for i in range(PLANNING_NEEDS_CAP + 5):
        record_planning_needs(cid, [planning_need(
            "room", "location_query_unmatched", subject=f"place {i}")], frame_id=None)
    assert len(open_planning_needs(cid)) == PLANNING_NEEDS_CAP
    record_planning_needs(cid, [planning_need(
        "person", "generation_request", subject="a stranger")], frame_id=3)
    assert [n["subject"] for n in open_planning_needs(cid, frame_id=3)] == ["a stranger"]
    assert all(n["subject"] != "a stranger" for n in open_planning_needs(cid))
    from core.db import FRAME_SCOPED_WORLD_KEYS
    assert "planning_needs" in FRAME_SCOPED_WORLD_KEYS


def test_a_need_can_be_answered(temp_db):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Needs", "", time.time()))
    need = planning_need("thing", "generation_request", subject="a rifle")
    record_planning_needs(cid, [need])
    filled = fill_planning_need(cid, need["uid"], {"by": "fill"})
    assert filled["status"] == "filled" and filled["fill"] == {"by": "fill"}
    assert open_planning_needs(cid) == []
    assert fill_planning_need(cid, "need_nobody", {"by": "fill"}) is None
    # The two writers share one ledger: a need the surface-only mint files
    # and a need the compiler raised for the same subject are one record.
    record_planning_needs(cid, [{"kind": "thing", "surface": {"name": "a rifle"}}])
    assert [n["uid"] for n in open_planning_needs(cid)] == []
    assert len([n for n in __import__("world.planning_needs", fromlist=["planning_needs"]).planning_needs(cid)
                if n["subject"] == "a rifle"]) == 1


def test_a_need_refuses_an_unknown_reason_and_an_empty_subject():
    with pytest.raises(ValueError):
        planning_need("room", "because", subject="x")
    with pytest.raises(ValueError):
        planning_need("room", "generation_request", subject="  ")
    need = planning_need("gizmo", "generation_request", subject="a gizmo")
    assert need["kind"] == "thing" and need["surface"]["declared_kind"] == "gizmo"
