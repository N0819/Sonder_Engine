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


def test_a_quiet_beat_is_skipped(temp_db):
    ctx, _ = _story(temp_db)
    prepared = cm.prepare_mapping_commit(ctx)
    assert prepared["skipped"] is True and prepared["ops"] == []


# ---- room filings and world facts are RETIRED --------------------------------

def test_a_described_room_files_no_lore(temp_db):
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


def test_a_stale_world_fact_files_nothing_and_asks_for_nothing(temp_db):
    """`world_facts` is retired (2026-09-26): rooms, bodies and things carry
    what IS, the Writers' Room keeps the facts not yet in play, and the
    charter moves the ones that are. It had filed through a fallback writer,
    then as `setting_fact` needs -- 95 of the owner's 102 needs, 67 of them
    never answered. A variant written before the retirement still carries
    the key, and a rerun from stage hands it here, where nothing reads it:
    no entry, and no need for the Room."""
    ctx, book = _story(temp_db)
    ctx.director_resolve["state_diff"]["world_facts"] = [
        {"fact": "Iron burns the fae.", "source": {"kind": "resolved"}},
        "Salt keeps a door shut.",
    ]
    prepared = cm.prepare_mapping_commit(ctx)
    assert prepared["skipped"] is True
    cm.commit_mapping(ctx, "n", prepared=prepared)
    assert _entries(temp_db, book) == []
    assert open_planning_needs(ctx.chat.id) == []


def test_a_containment_room_need_is_dropped_at_commit(temp_db):
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


# ---- the opening delivers the author's premise, never the Director's truths --
#
# Live, chat 3 "Harrowell House" (2026-09-14): the scenario said "the evening
# after the funeral"; the opening commit recorded "Mr Harrowell's funeral took
# place today" as a `setting_fact` need no plan answered, and no mind received
# it. A character whose card said the funeral was this week played it as
# tomorrow for three beats. Everyone standing in the opening knows the
# premise -- which is the scenario as its author wrote it. The establish
# stage's world facts were what is TRUE, card secrets among them; on
# 2026-09-26 four of six test openings delivered one to the whole cast, and
# the channel was retired the same day.

PREMISE = ("Harrowell House, the evening after the funeral. The family has "
           "gathered in the drawing room for the reading of the will.")
SECRET = "Ysolde has written to her brother every month for ten years and told no one."


def _cast_story(temp_db, *, opening, scenario="", state_diff=None):
    """A story with two attached characters on default cards, whose Director
    stage -- the opening's (`director_establish`, turn 0, no resolve) or a
    later beat's (`director_resolve`) -- committed `state_diff` under
    `scenario`."""
    from story.character_schema import default_character_data
    ctx, book = _story(temp_db)
    cid = ctx.chat.id
    # `_story` hands the book to the context alone; a real story's row names
    # its canon book too, and the premise is filed into that book.
    temp_db.qi("UPDATE chats SET lorebook_id=?, scenario=? WHERE id=?", (book, scenario, cid))
    ctx.chat.scenario = scenario
    for name in ("Ysolde", "Perrin"):
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (name, __import__("json").dumps(default_character_data(name)),
             "{}", time.time(), "char_" + name.casefold()))
        temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
                   "VALUES(?,?,?,?)", (cid, char_id, "active", "{}"))
    diff = dict(state_diff or {})
    if opening:
        ctx.turn.idx = 0
        ctx.director_resolve = None
        ctx.director_establish = {"state_diff": diff, "summary": ""}
    else:
        ctx.director_resolve["state_diff"] = diff
    return ctx, book


def _cast_knowledge(temp_db, ctx):
    """What each attached character's mind is handed as world knowledge on
    the next beat: the exact call `agents/character.py` makes, with the
    tags, exclusions and circles its card gives it."""
    from agents.common import _char_known_tags
    from mind.memory import chat_lorebook_ids, knowledge_for_character
    out = {}
    for row in temp_db.q(
            "SELECT ch.name, ch.sheet FROM chat_chars cc JOIN characters ch "
            "ON ch.id=cc.char_id WHERE cc.chat_id=?", (ctx.chat.id,)):
        sheet = __import__("json").loads(row["sheet"])
        tags, excluded, circles = _char_known_tags(sheet)
        out[row["name"]] = [
            k["content"] for k in knowledge_for_character(
                chat_lorebook_ids(ctx.chat.id), "quay", tags, excluded,
                circles=circles, chat_id=ctx.chat.id)]
    return out


def _premise_rows(temp_db, cid):
    return [dict(r) for r in temp_db.q(
        "SELECT e.entry_uid, e.content, e.knowledge_tag, e.knowledge_range, "
        "e.circles, e.source_notes, e.lorebook_id FROM lore_entries e "
        "JOIN chats c ON c.lorebook_id=e.lorebook_id WHERE c.id=?", (cid,))]


def test_the_premise_as_its_author_wrote_it_reaches_every_cast_member(temp_db):
    """The scenario is delivered whole through the one channel a mind knows
    the world by standing: a `common`, explicitly public entry in the
    story's canon book. Every attached character reads it on the next beat
    -- the Harrowell case, met by the author's own sentence."""
    ctx, _ = _cast_story(temp_db, opening=True, scenario=PREMISE)
    prepared = cm.prepare_mapping_commit(ctx)
    assert prepared["mout"]["premise"] == 1
    cm.commit_mapping(ctx, "n", prepared=prepared)
    knowledge = _cast_knowledge(temp_db, ctx)
    assert set(knowledge) == {"Ysolde", "Perrin"}
    for name, held in knowledge.items():
        assert PREMISE in held, name
    (row,) = _premise_rows(temp_db, ctx.chat.id)
    assert row["content"] == PREMISE
    assert row["knowledge_tag"] == cm.OPENING_PREMISE_KNOWLEDGE_TAG
    assert row["knowledge_range"] == "global"
    assert row["circles"] == "[]", "public by declaration, not by inheritance"
    assert row["source_notes"].startswith(cm.OPENING_PREMISE_SOURCE_PREFIX)


def test_a_truth_the_director_states_at_the_opening_reaches_no_one(temp_db):
    """The establish stage states what IS true -- a card's secret included --
    and true is not known: 2026-09-26, a daughter's secret letters, filed
    as the opening's world fact, rode every call of the two characters she
    kept them from. Only the author's premise is delivered. The channel
    that carried the Director's fact is retired, and a stale one -- an old
    variant rerun from stage -- reaches no one and asks the Room for
    nothing."""
    ctx, _ = _cast_story(temp_db, opening=True, scenario=PREMISE,
                         state_diff={"world_facts": [SECRET]})
    cm.commit_mapping(ctx, "n", prepared=cm.prepare_mapping_commit(ctx))
    for name, held in _cast_knowledge(temp_db, ctx).items():
        assert SECRET not in held, name
    assert [r["content"] for r in _premise_rows(temp_db, ctx.chat.id)] == [PREMISE]
    assert open_planning_needs(ctx.chat.id) == []


def test_a_premise_written_to_the_player_says_whom_you_means(temp_db, monkeypatch):
    """A scenario is often written to the player ("You are the new
    deputy"), so the entry's title says whose "you" it is; with no player
    to name it says only whose words these are."""
    monkeypatch.setattr(cm, "_player_name_or_none", lambda ctx: "Tomaso Ricci")
    ctx, _ = _cast_story(temp_db, opening=True,
                         scenario="You are the new deputy of Hollin Ford.")
    (entry,) = cm.prepare_mapping_commit(ctx)["premise"]
    assert entry["title"].count("Tomaso Ricci") == 2
    monkeypatch.setattr(cm, "_player_name_or_none", lambda ctx: None)
    (entry,) = cm.prepare_mapping_commit(ctx)["premise"]
    assert "Tomaso" not in entry["title"] and entry["title"]


def test_a_greeting_launch_files_no_premise(temp_db):
    """A story launched from a card's greeting stores the greeting as its
    scenario, and the greeting is the SCENE, not a premise: its lines reach
    minds through the opening's perception and its own conduct as the card
    character's memory. Filed whole as common knowledge, every aside and
    every line would reach any figure promoted later."""
    ctx, _ = _cast_story(temp_db, opening=True,
                         scenario='"You came back," she says, and sets down the cup.')
    wset(ctx.chat.id, "greeting_minds", {"extractor_version": 3, "minds": {}})
    cm.commit_mapping(ctx, "n", prepared=cm.prepare_mapping_commit(ctx))
    assert _premise_rows(temp_db, ctx.chat.id) == []


def test_an_opening_with_no_scenario_delivers_nothing(temp_db):
    ctx, _ = _cast_story(temp_db, opening=True)
    cm.commit_mapping(ctx, "n", prepared=cm.prepare_mapping_commit(ctx))
    assert _premise_rows(temp_db, ctx.chat.id) == []
    assert all(held == [] for held in _cast_knowledge(temp_db, ctx).values())


def test_only_the_opening_states_a_premise(temp_db):
    """A later beat under the same scenario files no premise: the premise is
    the opening's, filed once, when the story begins."""
    ctx, _ = _cast_story(temp_db, opening=False, scenario=PREMISE)
    prepared = cm.prepare_mapping_commit(ctx)
    assert prepared["premise"] == [] and "premise" not in prepared["mout"]
    cm.commit_mapping(ctx, "n", prepared=prepared)
    assert _premise_rows(temp_db, ctx.chat.id) == []
    assert all(held == [] for held in _cast_knowledge(temp_db, ctx).values())


def test_a_rerun_of_the_opening_files_the_premise_once(temp_db):
    """The entry uid is minted from the premise's text, so re-committing the
    opening (a reroll, a rerun from stage) finds its own filing and writes
    nothing."""
    ctx, _ = _cast_story(temp_db, opening=True, scenario=PREMISE)
    cm.commit_mapping(ctx, "n", prepared=cm.prepare_mapping_commit(ctx))
    cm.commit_mapping(ctx, "n2", prepared=cm.prepare_mapping_commit(ctx))
    assert len(_premise_rows(temp_db, ctx.chat.id)) == 1


# ---- introductions are the Director's typed rows --------------------------

def test_an_untyped_introduction_is_ignored_and_a_typed_one_read(temp_db):
    ctx, _ = _story(temp_db)
    ctx.director_resolve["state_diff"]["introductions"] = [
        "Alice meets Bob", {"who": "Alice"}, {"who": "Alice", "learns": "Bob"}]
    prepared = cm.prepare_mapping_commit(ctx)
    assert prepared["introductions"] == [{"who": "Alice", "learns": "Bob"}]


# ---- planning needs reach the ledger with the committed surface -----------

def test_a_need_is_recorded_at_commit_with_the_rendered_stub(temp_db):
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


def test_a_rerun_of_the_beat_records_the_need_once(temp_db):
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
        temp_db):
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


def test_a_rerun_opening_files_its_premise_into_the_book_the_database_holds(temp_db):
    """A rerun of an opening restores the checkpoint from BEFORE the opening,
    which deletes the canon book the opening minted and clears
    `chats.lorebook_id`; the pipeline's chat copy, read before the restore,
    still named the deleted book, and filing the premise into it failed the
    foreign key and rolled the whole commit back (the Larch Hill copy,
    2026-10-04: rerolling any step of turn 0 could not commit)."""
    ctx, book = _cast_story(temp_db, opening=True, scenario=PREMISE)
    # what the restore leaves behind: the book gone, the row cleared, the
    # context still naming it
    temp_db.qi("UPDATE chats SET lorebook_id=NULL WHERE id=?", (ctx.chat.id,))
    temp_db.qi("DELETE FROM lorebooks WHERE id=?", (book,))
    ctx.chat.lorebook_id = book
    prepared = cm.prepare_mapping_commit(ctx)
    cm.commit_mapping(ctx, "n", prepared=prepared)
    (row,) = _premise_rows(temp_db, ctx.chat.id)
    assert row["content"] == PREMISE
    owner = temp_db.q("SELECT chat_id FROM lorebooks WHERE id=?", (row["lorebook_id"],), one=True)
    assert owner and owner["chat_id"] == ctx.chat.id   # a book that exists, the chat's own
