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


def test_the_room_is_told_why_a_need_is_open_and_not_only_its_kind(temp_db):
    """`NEED_KINDS` is three values against five reasons, so everything that
    is neither a room nor a person is filed as a `thing` -- and the two
    surfaces the Room reads FIRST showed the kind and dropped the reason.

    Measured on the owner's live stories, 2026-09-06: 8 of the 9 open needs
    are `setting_fact`, whose subject is a SENTENCE by nature ("A
    Euclid-class containment breach has occurred at Site-17"), and the
    ninth is a `generation_request` carrying a verbatim clause of the
    player's own prose ("comes back off the vaulting a half-second later")
    -- the player-authority backstop forwards the declaration word for word
    on purpose. So the frontier report said `{thing: 9}` and the Room read
    nine props to author. `inspect_needs` and the fill job always passed the
    whole record; only the summaries did not.
    """
    from story.room_frontier import frontier_report
    from story.room_slice import _plan_here

    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Reasons", "", time.time()))
    wset(cid, "scene", {"rooms": {"hall": {"name": "Hall", "adjacent": []}},
                        "positions": {"Player": "hall"}})
    record_planning_needs(cid, [
        planning_need("thing", "setting_fact",
                      subject="A Euclid-class containment breach has occurred.",
                      surface={"room": "hall"}),
        planning_need("thing", "generation_request",
                      subject="comes back off the vaulting a half-second later",
                      surface={"room": "hall"}),
    ])
    report = frontier_report(cid, None)
    assert report["open_needs"] == {"thing": 2}
    assert report["open_needs_by_reason"] == {
        "setting_fact": 1, "generation_request": 1}
    rows = [n for room in _plan_here(cid, None, ["hall"]).values()
            for n in room.get("needs") or ()]
    assert {n["reason"] for n in rows} == {"setting_fact", "generation_request"}


# ---- one read and one write for the beat (review 2026-09-07 C20) ------------

def _world_statements(fn):
    """Every world-row statement one call issues."""
    from core import db as _db
    seen = []
    connection = _db.conn()
    connection.set_trace_callback(
        lambda sql: seen.append(" ".join(sql.split())))
    try:
        fn()
    finally:
        connection.set_trace_callback(None)
    return [s for s in seen if "world" in s]


def test_a_beat_files_all_its_needs_in_one_read_and_one_write(temp_db):
    """Filing was read-normalize-write PER NEED: on chat 117's ledger (21
    records, 13,040 bytes) two needs cost two reads and 26,082 bytes of
    writes for one change. The ledger is the same either way."""
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Needs", "", time.time()))
    beat = [planning_need("room", "location_query_unmatched",
                          subject="the sail loft"),
            planning_need("thing", "generation_request",
                          subject="a brass key"),
            # A repeat of the first, as a rerun of the beat files it.
            planning_need("room", "location_query_unmatched",
                          subject="the sail loft")]
    statements = _world_statements(
        lambda: record_planning_needs(cid, beat, frame_id=None))
    assert len([s for s in statements if s.startswith("SELECT")]) == 1
    assert len([s for s in statements if s.startswith("INSERT")]) == 1
    one_at_a_time = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Needs one by one", "", time.time()))
    for need in beat:
        record_planning_needs(one_at_a_time, [need], frame_id=None)
    assert [(n["kind"], n["subject"], n["status"])
            for n in open_planning_needs(cid)] \
        == [(n["kind"], n["subject"], n["status"])
            for n in open_planning_needs(one_at_a_time)]


def test_a_beat_that_files_nothing_new_writes_nothing(temp_db):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Needs", "", time.time()))
    need = planning_need("room", "location_query_unmatched",
                         subject="the sail loft")
    record_planning_needs(cid, [need], frame_id=None)
    statements = _world_statements(
        lambda: record_planning_needs(cid, [need], frame_id=None))
    assert [s for s in statements if s.startswith("INSERT")] == []


def test_the_ledgers_a_beat_re_derives_are_written_only_when_they_move(
        temp_db, wired):
    """`known`, `lore_cache` and `active_books` are rebuilt from the same
    inputs every beat and were written byte-identical every beat -- 3,186
    bytes per beat on chat 114, none of it a change (C20)."""
    from core import db as _db
    ctx, _book = _story(temp_db)
    cm.commit_mapping(ctx, "n", prepared=cm.prepare_mapping_commit(ctx))
    before = {key: _db.world_read_token(ctx.chat.id, key)
              for key in ("known", "lore_cache", "active_books")}
    statements = _world_statements(
        lambda: cm.commit_mapping(ctx, "n",
                                  prepared=cm.prepare_mapping_commit(ctx)))
    assert [s for s in statements if s.startswith("INSERT")] == []
    # Nothing moved, so no cached parse of those rows was invalidated.
    assert {key: _db.world_read_token(ctx.chat.id, key)
            for key in before} == before
