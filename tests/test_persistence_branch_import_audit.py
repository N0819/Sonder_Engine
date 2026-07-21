"""Regression tests for the branch/import/checkpoint persistence audit
fixes (AUDIT_FINDINGS #1, #3, #8, #9, #13, #14, #22, #25, #27).

These cover the highest-stakes data-integrity bugs: the checkpoint blob
kept SOURCE frame/persona ids across a branch/import (corrupting or
destroying frames on the next reroll), the normalized world_* tables were
never carried into a branch/import (false paradox on first commit),
world-entity turn FKs were never remapped (FK-fail aborts restore),
refresh_checkpoint re-snapshotted POST-turn state, restore never deleted
discarded-timeline lorebooks, export/import dropped the multiplayer roster
+ pre-submitted inputs + link graph, vehicle-book anchoring was lost on
branch, a 409-losing turn_new left a stepless orphan turn, and frame ids
were validated for existence but not chat ownership.
"""

from __future__ import annotations

import json
import time

import pytest
from fastapi import HTTPException

import app
import paradox
from character_schema import default_character_data
from checkpoints import ensure_checkpoint, restore_checkpoint, snapshot_state, refresh_checkpoint
from db import wget, wset
from frames import create_frame


def _make_chat(db, name="Story", persona_id=None):
    return db.qi(
        "INSERT INTO chats(name,persona_id,scenario,created) VALUES(?,?,?,?)",
        (name, persona_id, "", time.time()),
    )


def _make_char(db, name="Alice", uid=None):
    return db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) VALUES(?,?,?,?,?)",
        (name, json.dumps(default_character_data(name)), "{}", time.time(),
         uid or f"char_{name.lower()}"),
    )


def _make_persona(db, name="Player", uid=None):
    return db.qi(
        "INSERT INTO personas(name,sheet,source,resource_uid) VALUES(?,?,?,?)",
        (name, json.dumps({"identity": {"name": name, "uid": uid or name.lower()}}),
         "{}", uid or name.lower()),
    )


def _make_turn(db, chat_id, idx=0, frame_id=None):
    return db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) VALUES(?,?,?,?,?)",
        (chat_id, idx, "do", time.time(), frame_id),
    )


def _add_entity(db, chat_id, entity_id, created_turn_id=None):
    db.qi(
        "INSERT INTO world_entities(entity_id,chat_id,kind,subtype,name,payload,created_turn_id) "
        "VALUES(?,?,?,?,?,?,?)",
        (entity_id, chat_id, "object", "", entity_id, "{}", created_turn_id),
    )


# ---------------------------------------------------------------------------
# #1 -- branch remaps blob frames + chat_personas through frame_idmap
# ---------------------------------------------------------------------------

def test_branch_remaps_checkpoint_blob_frames_and_personas(temp_db):
    chat_id = _make_chat(temp_db)
    char_id = _make_char(temp_db)
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
               (chat_id, char_id, "active", "{}"))
    persona_id = _make_persona(temp_db, "Two", "persona_two")
    fid = create_frame(chat_id, label="past", ordinal=-1, kind="past")
    temp_db.qi("INSERT INTO chat_personas(chat_id,persona_id,status,frame_id) VALUES(?,?,?,?)",
               (chat_id, persona_id, "active", fid))
    tid = _make_turn(temp_db, chat_id, idx=0, frame_id=fid)
    ensure_checkpoint(chat_id, 0)
    ensure_checkpoint(chat_id, 1)

    branched = app.turn_branch(tid)
    ncid = branched["id"]

    # The branch's own frame id (not the source's).
    nfid = temp_db.q("SELECT id FROM frames WHERE chat_id=?", (ncid,), one=True)["id"]
    assert nfid != fid

    for cp in temp_db.q("SELECT blob FROM checkpoints WHERE chat_id=?", (ncid,)):
        blob = json.loads(cp["blob"])
        for fr in blob.get("frames") or []:
            assert fr["id"] == nfid, "blob frame id must be remapped to the branch's frame"
        for p in blob.get("chat_personas") or []:
            assert p["frame_id"] in (None, nfid), "persona station must be remapped"

    # And a restore of the branched chat must not PK-collide / crash.
    restore_checkpoint(ncid, 1)
    assert temp_db.q("SELECT COUNT(*) c FROM frames WHERE chat_id=?", (ncid,), one=True)["c"] == 1


# ---------------------------------------------------------------------------
# #3 + #22 -- branch copies normalized world tables (no false paradox) and
#            carries vehicle-book anchor_entity_id
# ---------------------------------------------------------------------------

def test_branch_copies_world_tables_and_satisfies_fixed_point(temp_db):
    chat_id = _make_chat(temp_db)
    tid = _make_turn(temp_db, chat_id, idx=0)
    _add_entity(temp_db, chat_id, "ent_ship", created_turn_id=tid)
    # A required-exists anchor pointing at that entity: an empty world table
    # in the branch would make this fire a false paradox on first commit.
    paradox.add_fixed_point(chat_id, entity_id="ent_ship", frame_id=None,
                            required_exists=True, label="the ship")
    # A vehicle book anchored to the entity (#22).
    book_id = temp_db.qi(
        "INSERT INTO lorebooks(name,chat_id,book_type,anchor_entity_id,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Ship log", chat_id, "vehicle", "ent_ship", "book_ship"),
    )
    temp_db.qi("UPDATE chats SET lorebook_id=? WHERE id=?", (book_id, chat_id))
    ensure_checkpoint(chat_id, 1)

    branched = app.turn_branch(tid)
    ncid = branched["id"]

    ents = temp_db.q("SELECT entity_id FROM world_entities WHERE chat_id=?", (ncid,))
    assert len(ents) == 1, "the branch must carry the normalized world entity"
    new_ent_id = ents[0]["entity_id"]

    # The anchor must be satisfied against the branch's own world table --
    # entity id + fixed_point were remapped in lockstep.
    points = paradox.fixed_points(ncid)
    assert len(points) == 1
    assert paradox._anchor_satisfied(ncid, points[0]), "no false paradox after branch"

    # Vehicle book anchor followed the remapped entity.
    nbook = temp_db.q(
        "SELECT anchor_entity_id FROM lorebooks WHERE chat_id=? AND book_type='vehicle'",
        (ncid,), one=True,
    )
    assert nbook["anchor_entity_id"] == new_ent_id


def test_import_copies_world_tables_and_remaps_entity_turn_fk(temp_db):
    """#3 + #14: import must populate the normalized world tables from the
    export and remap world_entities.created_turn_id through the turn idmap
    (FK-valid), not carry the source turn id."""
    chat_id = _make_chat(temp_db)
    alice = _make_char(temp_db)
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
               (chat_id, alice, "active", "{}"))
    tid = _make_turn(temp_db, chat_id, idx=0)
    _add_entity(temp_db, chat_id, "ent_key", created_turn_id=tid)

    exported = app.chat_export(chat_id)
    assert any(e["entity_id"] == "ent_key" for e in exported["world_entities"])

    imported = app.chat_import({"data": exported})
    ncid = imported["id"]

    row = temp_db.q("SELECT * FROM world_entities WHERE chat_id=?", (ncid,), one=True)
    assert row is not None and row["entity_id"] == "ent_key"
    new_turn = temp_db.q("SELECT id FROM turns WHERE chat_id=?", (ncid,), one=True)
    assert row["created_turn_id"] == new_turn["id"], "created_turn_id remapped to the new turn"


def test_remap_cp_blob_remaps_world_entity_turn_ids(temp_db):
    """#14 unit check: _remap_cp_blob nulls an unmapped turn FK instead of
    leaving the source id to FK-fail on restore."""
    blob = {"world_entities": [
        {"entity_id": "e1", "kind": "object", "created_turn_id": 5, "retired_turn_id": 9},
        {"entity_id": "e2", "kind": "object", "created_turn_id": 99, "retired_turn_id": None},
    ]}
    app._remap_cp_blob(blob, {5: 500, 9: 900}, {}, None)
    assert blob["world_entities"][0]["created_turn_id"] == 500
    assert blob["world_entities"][0]["retired_turn_id"] == 900
    assert blob["world_entities"][1]["created_turn_id"] is None  # unmapped -> null


# ---------------------------------------------------------------------------
# #8 -- refresh_checkpoint patches ONLY the lorebook sections
# ---------------------------------------------------------------------------

def test_refresh_checkpoint_preserves_pre_turn_world_state(temp_db):
    chat_id = _make_chat(temp_db)
    _make_turn(temp_db, chat_id, idx=0)
    wset(chat_id, "scene", {"location": "before"})
    ensure_checkpoint(chat_id, 0)

    # Simulate the turn mutating world state AFTER the pre-turn checkpoint.
    wset(chat_id, "scene", {"location": "after"})

    refresh_checkpoint(chat_id, 0)

    blob = json.loads(temp_db.q(
        "SELECT blob FROM checkpoints WHERE chat_id=? AND turn_idx=0", (chat_id,), one=True)["blob"])
    assert blob["world"]["scene"] == {"location": "before"}, (
        "refresh must NOT capture post-turn world state -- a checkpoint "
        "precedes durable mutation"
    )
    assert "lorebooks" in blob


# ---------------------------------------------------------------------------
# #9 -- restore deletes lorebooks created after the snapshot + resets canon
# ---------------------------------------------------------------------------

def test_restore_deletes_post_snapshot_book_and_resets_canon(temp_db):
    chat_id = _make_chat(temp_db)
    _make_turn(temp_db, chat_id, idx=0)
    ensure_checkpoint(chat_id, 1)  # snapshot with no books, no canon

    # A turn then mints a chat-owned book + binds it as canon.
    book_id = temp_db.qi(
        "INSERT INTO lorebooks(name,chat_id,resource_uid) VALUES(?,?,?)",
        ("Discarded", chat_id, "book_discard"),
    )
    temp_db.qi("INSERT INTO chat_lorebooks(chat_id,lorebook_id,enabled) VALUES(?,?,1)",
               (chat_id, book_id))
    temp_db.qi("UPDATE chats SET lorebook_id=? WHERE id=?", (book_id, chat_id))

    restore_checkpoint(chat_id, 1)

    assert temp_db.q("SELECT id FROM lorebooks WHERE id=?", (book_id,), one=True) is None, (
        "a book minted by a since-discarded timeline must be deleted on restore"
    )
    assert temp_db.q("SELECT lorebook_id FROM chats WHERE id=?", (chat_id,), one=True)["lorebook_id"] is None, (
        "canon must be reset when the snapshot had none"
    )


# ---------------------------------------------------------------------------
# #13 -- export/import round-trips chat_personas, turn_player_inputs, links
# ---------------------------------------------------------------------------

def test_export_import_round_trips_roster_inputs_and_links(temp_db):
    primary = _make_persona(temp_db, "Primary", "persona_primary")
    extra = _make_persona(temp_db, "Extra", "persona_extra")
    chat_id = _make_chat(temp_db, persona_id=primary)
    alice = _make_char(temp_db)
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
               (chat_id, alice, "active", "{}"))
    _make_turn(temp_db, chat_id, idx=0)

    temp_db.qi("INSERT INTO chat_personas(chat_id,persona_id,status,frame_id) VALUES(?,?,?,?)",
               (chat_id, extra, "active", None))
    temp_db.qi("INSERT INTO turn_player_inputs(chat_id,turn_idx,persona_id,input,created) "
               "VALUES(?,?,?,?,?)", (chat_id, 1, extra, "peek ahead", time.time()))

    # No resource_uid -> import mints fresh ones (this test re-imports into
    # the same DB, where reusing a uid would collide -- pre-existing import
    # behavior, unrelated to the roster/link fix under test).
    b1 = temp_db.qi("INSERT INTO lorebooks(name,chat_id) VALUES(?,?)", ("A", chat_id))
    b2 = temp_db.qi("INSERT INTO lorebooks(name,chat_id) VALUES(?,?)", ("B", chat_id))
    for b in (b1, b2):
        temp_db.qi("INSERT INTO chat_lorebooks(chat_id,lorebook_id,enabled) VALUES(?,?,1)",
                   (chat_id, b))
    from memory import add_lorebook_link, get_lorebook_links
    add_lorebook_link(b1, b2, "related")

    exported = app.chat_export(chat_id)
    assert exported["turn_player_inputs"] and exported["lorebook_links"]
    assert any(p["persona_id"] == extra for p in exported["chat_personas"])
    assert any(ep["old_id"] == extra for ep in exported["resources"]["extra_personas"])

    imported = app.chat_import({"data": exported})
    ncid = imported["id"]

    roster = temp_db.q("SELECT persona_id FROM chat_personas WHERE chat_id=?", (ncid,))
    assert len(roster) == 1  # the extra persona (same DB -> matched by uid)
    tpi = temp_db.q("SELECT input FROM turn_player_inputs WHERE chat_id=?", (ncid,), one=True)
    assert tpi is not None and tpi["input"] == "peek ahead"
    new_books = {r["name"]: r["id"] for r in
                 temp_db.q("SELECT id,name FROM lorebooks WHERE chat_id=?", (ncid,))}
    links = get_lorebook_links(new_books["A"])
    assert any(l["target_book_id"] == new_books["B"] for l in links), "link graph restored"


# ---------------------------------------------------------------------------
# #25 -- turn_new must not leave an orphan turn when the pipeline slot is lost
# ---------------------------------------------------------------------------

def test_turn_new_leaves_no_orphan_turn_when_pipeline_slot_lost(temp_db, monkeypatch):
    chat_id = _make_chat(temp_db)

    def _lose(*a, **k):
        raise HTTPException(409, "A pipeline is already running for this.")

    monkeypatch.setattr(app, "_begin_pipeline_or_409", _lose)

    with pytest.raises(HTTPException) as exc:
        app.turn_new(chat_id, {"input": "start"})
    assert exc.value.status_code == 409

    assert temp_db.q("SELECT COUNT(*) c FROM turns WHERE chat_id=?", (chat_id,), one=True)["c"] == 0, (
        "a 409-losing request must not persist a stepless orphan turn"
    )


# ---------------------------------------------------------------------------
# #27 -- frame ids must belong to the chat, not just exist
# ---------------------------------------------------------------------------

def test_turn_new_rejects_a_foreign_chats_frame(temp_db):
    chat_a = _make_chat(temp_db, name="A")
    chat_b = _make_chat(temp_db, name="B")
    foreign = create_frame(chat_a, label="a-frame", ordinal=1, kind="future")
    with pytest.raises(HTTPException) as exc:
        app.turn_new(chat_b, {"input": "x", "frame_id": foreign})
    assert exc.value.status_code == 404


def test_persona_station_rejects_a_foreign_chats_frame(temp_db):
    chat_a = _make_chat(temp_db, name="A")
    chat_b = _make_chat(temp_db, name="B")
    persona = _make_persona(temp_db, "P", "persona_p")
    temp_db.qi("INSERT INTO chat_personas(chat_id,persona_id,status,frame_id) VALUES(?,?,?,?)",
               (chat_b, persona, "active", None))
    foreign = create_frame(chat_a, label="a-frame", ordinal=1, kind="future")
    with pytest.raises(HTTPException) as exc:
        app.chat_persona_station(chat_b, persona, {"frame_id": foreign})
    assert exc.value.status_code == 404


def test_fixed_point_create_rejects_a_foreign_chats_frame(temp_db):
    chat_a = _make_chat(temp_db, name="A")
    chat_b = _make_chat(temp_db, name="B")
    foreign = create_frame(chat_a, label="a-frame", ordinal=1, kind="future")
    with pytest.raises(HTTPException) as exc:
        app.fixed_points_create(chat_b, {"entity_id": "e", "label": "L", "frame_id": foreign})
    assert exc.value.status_code == 404
