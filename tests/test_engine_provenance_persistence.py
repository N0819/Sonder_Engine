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


# ---- the lore-commit route: nothing is filed about a room any more -------

def _filing_ctx(temp_db, room_desc, monkeypatch, *, world_facts=()):
    """A beat whose Director described a room and asserted facts."""
    import persist.commit_mapping as cm
    ctx, char_id = _mk(temp_db, "")
    book_id = temp_db.qi(
        "INSERT INTO lorebooks(name) VALUES(?)", ("B",))
    temp_db.qi("INSERT INTO chat_lorebooks(chat_id,lorebook_id) VALUES(?,?)",
               (ctx.chat.id, book_id))
    ctx.chat.lorebook_id = book_id
    ctx.compile_world_context = {"relevant_lore": [], "relevant_books": [book_id],
                                 "staged_lore": [], "planning_needs": []}
    ctx.director_resolve = {
        "state_diff": {
            "rooms": {"back_office": {"name": "Back Office", "desc": room_desc,
                                      "adjacent": []}},
            "world_facts": list(world_facts),
        },
        "resolved_event": "", "summary": "s", "dialogue_log": []}
    monkeypatch.setattr(cm, "search_lore", lambda *a, **k: [])
    return ctx, book_id


def _rows(temp_db, book_id):
    return [dict(r) for r in temp_db.q(
        "SELECT content, source_notes, category FROM lore_entries "
        "WHERE lorebook_id=?", (book_id,))]


def test_a_described_room_writes_no_lore_row(temp_db, monkeypatch):
    """The room filing (a `layout` entry per described room, promoted to
    `spatial_generation`) is retired: the scene is the record of a room, so
    a diagnostic the Director wrote into a room's prose has no lore row to
    be moved onto. It is stripped where the room is delivered
    (`_room_notes_from_lore`), which the stage tests above cover."""
    from persist.commit import prepare_mapping_commit, commit_mapping
    ctx, book_id = _filing_ctx(temp_db, ROOM_NOTES, monkeypatch)
    commit_mapping(ctx, "n0", prepared=prepare_mapping_commit(ctx))
    assert _rows(temp_db, book_id) == []


def test_a_world_fact_is_a_need_and_never_a_row(temp_db, monkeypatch):
    """The fallback fact writer is retired with the filing: a Director
    `world_fact` becomes a `setting_fact` planning need for the room to
    file with provenance and a gate, and no entry is written here."""
    from persist.commit import prepare_mapping_commit, commit_mapping
    from world.planning_needs import open_planning_needs
    ctx, book_id = _filing_ctx(
        temp_db, "", monkeypatch,
        world_facts=[{"fact": "The ferry runs at dawn.", "source": {"kind": "resolved"}}])
    commit_mapping(ctx, "n0", prepared=prepare_mapping_commit(ctx))
    assert _rows(temp_db, book_id) == []
    (need,) = open_planning_needs(ctx.chat.id)
    assert (need["kind"], need["reason"]) == ("thing", "setting_fact")
    assert need["surface"]["fact"] == "The ferry runs at dawn."
