"""INDEPENDENT REPRODUCTION -- drives the real perception stages and the real
commit path, not composer.environment_percept.

Route differences from the builder's tests:
  * the view comes out of `perception_establish` / `perception_act` /
    `perception_outcome` against a committed scene in a temp database, i.e.
    the stage entry points the runtime calls, not a hand-built percept;
  * the room description arrives from the SCENE ROW the way a committed turn
    puts it there;
  * the lore side is driven through `prepare_mapping_commit` + `commit_mapping`
    against a real `lore_entries` table, so the claim "the signal survives on
    source_notes" is checked by reading the column back out of SQLite;
  * the scene side is driven through `prepare_scene_commit`, which is what
    turns a staged layout entry into a room's `desc`.

No import of story.provenance_text: this file must run unchanged against the
pre-change tree.
"""

from __future__ import annotations

import json
import time

import pytest

from story.character_schema import default_character_data
from core.pipeline_context import ChatData, PipelineContext, TurnData

DIAG = "generated because no candidate described this location."
WORLD = "A cramped office over the water."
ROOM_NOTES = WORLD + " " + DIAG


def _mk(temp_db, notes):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Repro", "", time.time()))
    sheet = default_character_data("Reya")
    sheet["embodiment"]["visible"]["summary"] = "a wiry courier"
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Reya", json.dumps(sheet), "{}", time.time(), "char_reya"))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"))
    temp_db.wset(chat_id, "scene", {
        "location": "Waystation", "time": "night",
        "rooms": {"hall": {"name": "the Long Hall", "notes": notes,
                           "adjacent": []}},
        "positions": {"The Stranger": "hall", "Reya": "hall"},
        "entities": {}, "attire": {}, "overlays": {},
    })
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "hello", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Repro", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                      player_input="hello", created=time.time()),
        cast=cast, input="hello")
    ctx.director_interpret = {
        "sequence": [{"type": "action", "attempt": "raises the lantern",
                      "observable": "raises the lantern",
                      "visibility": "overt"}],
        "speech": None, "speech_volume": "normal", "action": None,
        "flow": {"reactors": [char_id], "addressed_to": [],
                 "authority_claims": [], "resolution_flags": {},
                 "fiction_frame": {}},
    }
    return ctx, char_id


def _blob(out):
    return json.dumps(out, ensure_ascii=False)


# ---- the delivery route: real stages ------------------------------------

def test_act_stage_view_carries_no_engine_diagnostic(temp_db):
    from agents.perception import perception_act
    ctx, char_id = _mk(temp_db, ROOM_NOTES)
    out = perception_act(ctx, "n0")
    view = out["views"][str(char_id)]
    assert WORLD in view, view
    assert "no candidate" not in _blob(out), view


def test_establish_stage_view_carries_no_engine_diagnostic(temp_db):
    from agents.perception import perception_establish
    ctx, char_id = _mk(temp_db, ROOM_NOTES)
    ctx.turn.idx = 0
    out = perception_establish(ctx, "n0")
    assert "no candidate" not in _blob(out), _blob(out)[:2000]


def test_outcome_stage_view_carries_no_engine_diagnostic(temp_db):
    from agents.perception import perception_outcome
    ctx, char_id = _mk(temp_db, ROOM_NOTES)
    ctx.director_resolve = {
        "resolved_event": "The lantern comes up.",
        "state_diff": {}, "dialogue_log": [], "summary": "lantern",
    }
    out = perception_outcome(ctx, "n0")
    assert "no candidate" not in _blob(out), _blob(out)[:2000]


def test_the_stage_still_delivers_an_ordinary_room_description(temp_db):
    """Positive control on the same route: subtraction must be scoped."""
    from agents.perception import perception_act
    ctx, char_id = _mk(temp_db, "Rope coils hang from the rafters.")
    out = perception_act(ctx, "n0")
    assert "Rope coils hang from the rafters." in out["views"][str(char_id)]


# ---- the scene-commit route ---------------------------------------------

def test_a_staged_layout_entry_does_not_put_bookkeeping_in_the_room(temp_db):
    from persist.commit import prepare_scene_commit
    ctx, char_id = _mk(temp_db, "")
    ctx.mapping_stage = {"staged_lore": [
        {"category": "layout", "keys": "back office",
         "content": ROOM_NOTES, "title": "back office"}]}
    ctx.director_interpret["movement"] = {"mover": "self", "to_room": "back_office"}
    ctx.director_resolve = {"state_diff": {"positions": {"Reya": "back_office"}},
                            "resolved_event": "", "dialogue_log": []}
    prepared = prepare_scene_commit(ctx)
    blob = json.dumps(prepared, ensure_ascii=False, default=str)
    assert "back_office" in blob, blob[:3000]
    assert "no candidate" not in blob, blob[:3000]


# ---- the lore-commit route: real prepare + commit, read the column back ----

def _wire_mapping(monkeypatch, lore_ops):
    import llm.llm_quality as q
    import persist.commit_mapping as cm
    monkeypatch.setattr(q, "complete_validated_json",
                        lambda **kw: {"validated": [], "lore_ops": lore_ops,
                                      "book_ops": [], "coherence_notes": []})
    monkeypatch.setattr(cm, "embed_texts", lambda docs: [[0.0] * 8 for _ in docs])
    monkeypatch.setattr(cm, "search_lore", lambda *a, **k: [])


def _mapping_ctx(temp_db, staged, lore_ops, monkeypatch):
    ctx, char_id = _mk(temp_db, "")
    book_id = temp_db.qi(
        "INSERT INTO lorebooks(name) VALUES(?)", ("B",))
    temp_db.qi("INSERT INTO chat_lorebooks(chat_id,lorebook_id) VALUES(?,?)",
               (ctx.chat.id, book_id))
    ctx.chat.lorebook_id = book_id
    ctx.mapping_stage = {"staged_lore": staged, "relevant_books": [book_id]}
    ctx.director_resolve = {"state_diff": {}, "resolved_event": "",
                            "summary": "s", "dialogue_log": []}
    _wire_mapping(monkeypatch, [dict(o, book_id=book_id) for o in lore_ops])
    return ctx, book_id


def _rows(temp_db, book_id):
    return [dict(r) for r in temp_db.q(
        "SELECT content, source_notes FROM lore_entries WHERE lorebook_id=?",
        (book_id,))]


def test_a_diagnostic_in_the_op_text_is_moved_to_the_column(temp_db, monkeypatch):
    """The model writes it into the prose anyway -- the floor. Driven through
    the real prepare/commit pair and read back out of SQLite."""
    from persist.commit import prepare_mapping_commit, commit_mapping
    staged = [{"category": "layout", "keys": "back office",
               "content": ROOM_NOTES, "title": "back office"}]
    ops = [{"op": "create", "keys": "back office", "content": ROOM_NOTES,
            "category": "layout", "title": "back office"}]
    ctx, book_id = _mapping_ctx(temp_db, staged, ops, monkeypatch)
    commit_mapping(ctx, "n0", prepared=prepare_mapping_commit(ctx))
    rows = _rows(temp_db, book_id)
    assert rows, "nothing committed"
    assert not any("no candidate" in (r["content"] or "") for r in rows), rows
    assert any("no candidate" in (r["source_notes"] or "") for r in rows), rows


def test_a_declared_provenance_field_survives_the_default_commit_path(temp_db, monkeypatch):
    """What the CHANGED PROMPT actually produces: the declaration arrives as a
    `provenance` FIELD on the staged entry and never as a sentence. The claim
    is that the signal survives -- so it must reach the column from there."""
    from persist.commit import prepare_mapping_commit, commit_mapping
    staged = [{"category": "layout", "keys": "back office", "content": WORLD,
               "title": "back office",
               "provenance": "generated; no candidate described this part of the place"}]
    # The mapping_commit model's normal output: it confirms the staged stub.
    ops = [{"op": "create", "keys": "back office", "content": WORLD,
            "category": "layout", "title": "back office"}]
    ctx, book_id = _mapping_ctx(temp_db, staged, ops, monkeypatch)
    commit_mapping(ctx, "n0", prepared=prepare_mapping_commit(ctx))
    rows = _rows(temp_db, book_id)
    assert rows, "nothing committed"
    assert any("no candidate" in (r["source_notes"] or "") for r in rows), rows


def test_the_fallback_branch_is_the_only_one_that_carries_the_field(temp_db, monkeypatch):
    """Control for the failure above: `_generate_fallback_ops` DOES copy
    `provenance` across -- and it runs only when the mapping_commit model
    returns no lore_ops at all."""
    from persist.commit import prepare_mapping_commit, commit_mapping
    staged = [{"category": "layout", "keys": "back office", "content": WORLD,
               "title": "back office",
               "provenance": "generated; no candidate described this part of the place"}]
    ctx, book_id = _mapping_ctx(temp_db, staged, [], monkeypatch)
    commit_mapping(ctx, "n0", prepared=prepare_mapping_commit(ctx))
    rows = _rows(temp_db, book_id)
    assert rows, "nothing committed"
    assert any("no candidate" in (r["source_notes"] or "") for r in rows), rows
