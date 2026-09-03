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
    PLANNING_NEEDS_CAP, close_planning_need, open_planning_needs,
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
    monkeypatch.setattr(cm, "embed_texts", lambda docs: [[0.0] * 4 for _ in docs])
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


# ---- room filings through the seam ----------------------------------------

def test_a_described_room_is_filed_as_layout_with_a_disposition(temp_db, wired):
    ctx, book = _story(temp_db)
    ctx.director_resolve["state_diff"]["rooms"] = {
        "bond_warehouse": {"name": "Bond Warehouse",
                           "desc": "Crates to the rafters, a smell of tar.",
                           "adjacent": [{"to": "quay", "barrier": "open"}]}}
    prepared = cm.prepare_mapping_commit(ctx)
    assert prepared["mout"]["rooms_filed"] == ["bond_warehouse"]
    cm.commit_mapping(ctx, "n", prepared=prepared)
    (row,) = _entries(temp_db, book)
    assert row["category"] == "layout"
    assert row["content"] == "Crates to the rafters, a smell of tar."
    assert "bond_warehouse" in row["knowledge_locations"]
    assert row["keys"].startswith("Bond Warehouse")
    assert "spatial_generation by director_resolve" in row["source_notes"]


def test_the_record_is_promoted_not_written_provisional(temp_db, wired):
    ctx, _ = _story(temp_db)
    diff = {"rooms": {"bond_warehouse": {"name": "Bond Warehouse", "desc": "Crates."}}}
    (record,) = cm.room_filings(ctx, diff, {"rooms": {}}, adjudicator="director_resolve")
    assert record["disposition"] == cm.FILED_ROOM_DISPOSITION
    assert record["adjudicator"] == "director_resolve"
    assert record["promoted_from"] == "provisional"
    assert record["subject"] == {"kind": "room", "id": "bond_warehouse",
                                 "display": "Bond Warehouse"}
    assert record["base_turn"] == 6 and record["basis"] == "deterministic"


def test_a_room_key_that_is_not_an_id_is_still_filed_under_its_slug(temp_db, wired):
    ctx, book = _story(temp_db)
    ctx.director_resolve["state_diff"]["rooms"] = {
        "Mirelle Sulmirath_throat": {"name": "Throat", "desc": "Wet dark."}}
    prepared = cm.prepare_mapping_commit(ctx)
    cm.commit_mapping(ctx, "n", prepared=prepared)
    (row,) = _entries(temp_db, book)
    assert "Mirelle Sulmirath_throat" in row["knowledge_locations"], (
        "the entry is keyed to the scene's own room key; the provenance "
        "subject is the id-shaped slug")


def test_an_unchanged_room_files_nothing_and_a_changed_one_updates(temp_db, wired):
    ctx, book = _story(temp_db)
    ctx.director_resolve["state_diff"]["rooms"] = {
        "quay": {"name": "The Quay", "desc": "Wet stone."}}
    assert cm.prepare_mapping_commit(ctx)["skipped"] is True, "re-asserted unchanged"
    ctx.director_resolve["state_diff"]["rooms"] = {
        "quay": {"name": "The Quay", "desc": "Wet stone, and a body."}}
    cm.commit_mapping(ctx, "n", prepared=cm.prepare_mapping_commit(ctx))
    ctx.director_resolve["state_diff"]["rooms"] = {
        "quay": {"name": "The Quay", "desc": "Wet stone, a body, a lantern."}}
    wset(ctx.chat.id, "scene", {"rooms": {"quay": {"name": "The Quay",
                                                   "desc": "Wet stone, and a body."}}})
    prepared = cm.prepare_mapping_commit(ctx)
    assert prepared["ops"][0]["op"] == "update"
    result = cm.commit_mapping(ctx, "n", prepared=prepared)
    assert result["applied"] == {"created": 0, "updated": 1}
    (row,) = _entries(temp_db, book)
    assert row["content"] == "Wet stone, a body, a lantern."


def test_a_room_without_a_description_is_not_filed(temp_db, wired):
    ctx, _ = _story(temp_db)
    ctx.director_resolve["state_diff"]["rooms"] = {
        "cellar": {"name": "Cellar", "adjacent": []}}
    assert cm.prepare_mapping_commit(ctx)["skipped"] is True


def test_the_opening_stage_is_its_own_adjudicator(temp_db, wired):
    ctx, book = _story(temp_db)
    ctx.director_resolve = None
    ctx.director_establish = {"state_diff": {"rooms": {
        "quay": {"name": "The Quay", "desc": "Fog on the water."}}}}
    cm.commit_mapping(ctx, "n", prepared=cm.prepare_mapping_commit(ctx))
    (row,) = _entries(temp_db, book)
    assert "spatial_generation by director_establish" in row["source_notes"]


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
    assert opened["need_id"] == need["need_id"]
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
    assert close_planning_need(cid, need["need_id"], answered_by="fill")
    assert open_planning_needs(cid) == []
    assert not close_planning_need(cid, need["need_id"])


def test_a_need_refuses_an_unknown_reason_and_an_empty_subject():
    with pytest.raises(ValueError):
        planning_need("room", "because", subject="x")
    with pytest.raises(ValueError):
        planning_need("room", "generation_request", subject="  ")
    need = planning_need("gizmo", "generation_request", subject="a gizmo")
    assert need["kind"] == "thing" and need["surface"]["declared_kind"] == "gizmo"
