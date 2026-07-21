"""Schema-change checklist coverage for the Phase-2 room_registry table
and lorebooks.retired_turn_id (docs/DATABASE.md): migration from the
Phase-1 lore_entries encoding, checkpoint snapshot/restore, export/import,
and branch/clone id remapping. A schema change that doesn't round-trip
through checkpoints and import is a corruption bug -- these are the tests
that make that loud.
"""

from __future__ import annotations

import json
import time

import app
from checkpoints import ensure_checkpoint, restore_checkpoint, snapshot_state
from db import q


def _make_chat(db, name="Story"):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        (name, "", time.time()),
    )


def _make_turn(db, chat_id, idx=0):
    return db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, idx, "do", time.time()),
    )


def _make_book(db, chat_id, name, anchor=None, canon=False,
               retired_turn_id=None, parent_id=None):
    book_id = db.qi(
        "INSERT INTO lorebooks(name,chat_id,book_type,anchor_entity_id,"
        "parent_id,retired_turn_id) VALUES(?,?,?,?,?,?)",
        (name, chat_id, "vehicle" if anchor else "general", anchor,
         parent_id, retired_turn_id),
    )
    if canon:
        db.qi("UPDATE chats SET lorebook_id=? WHERE id=?", (book_id, chat_id))
    return book_id


def _add_registry_row(db, chat_id, room_uid, book_id, *, parent_entity=None,
                      name="", created_turn_id=None, retired_turn_id=None):
    db.qi(
        "INSERT INTO room_registry(chat_id,room_uid,owning_book_id,"
        "parent_entity,name,aliases,payload,created_turn_id,retired_turn_id) "
        "VALUES(?,?,?,?,?,?,?,?,?)",
        (chat_id, room_uid, book_id, parent_entity, name or room_uid,
         json.dumps([name or room_uid]), "{}", created_turn_id,
         retired_turn_id),
    )


def _registry_rows(db, chat_id):
    return [dict(r) for r in db.q(
        "SELECT * FROM room_registry WHERE chat_id=? ORDER BY room_uid",
        (chat_id,))]


def _build_ship_chat(db):
    """A chat with a canon book, a vehicle book anchored to a world
    entity, a live and a retired registry room, and a retired book."""
    chat_id = _make_chat(db)
    turn_id = _make_turn(db, chat_id, idx=0)
    canon = _make_book(db, chat_id, "Canon", canon=True)
    db.qi(
        "INSERT INTO world_entities(entity_id,chat_id,kind,subtype,name,"
        "payload,created_turn_id) VALUES(?,?,?,?,?,?,?)",
        ("ship_a", chat_id, "vehicle", "", "The Aurora",
         json.dumps({"aliases": ["Aurora"]}), turn_id),
    )
    # Parented under canon like real vehicle books (commit_world_entities
    # roots them there), so the lorebook graph resolves them.
    ship_book = _make_book(db, chat_id, "The Aurora", anchor="ship_a",
                           parent_id=canon)
    sunk_book = _make_book(db, chat_id, "The Boreas",
                           retired_turn_id=turn_id, parent_id=canon)
    _add_registry_row(db, chat_id, "deck_3", ship_book,
                      parent_entity="ship_a", name="Deck 3",
                      created_turn_id=turn_id)
    _add_registry_row(db, chat_id, "boreas_hold", sunk_book,
                      name="Cargo Hold", created_turn_id=turn_id,
                      retired_turn_id=turn_id)
    return {"chat_id": chat_id, "turn_id": turn_id, "canon": canon,
            "ship_book": ship_book, "sunk_book": sunk_book}


# ---- Migration from the Phase-1 lore_entries encoding ----

def test_migration_moves_phase1_lore_rows_into_room_registry(temp_db):
    chat_id = _make_chat(temp_db)
    book_id = _make_book(temp_db, chat_id, "The Aurora", anchor="ship_a",
                         canon=True)
    # A Phase-1 derived registry row, exactly as commit used to write it.
    temp_db.qi(
        "INSERT INTO lore_entries(lorebook_id,keys,content,category,"
        "entry_uid,importance) VALUES(?,?,?,?,?,?)",
        (book_id, "Deck 3, deck 3", "Room registry: Deck 3 ...", "layout",
         f"room:{book_id}:deck_3", 0.2),
    )
    # Rewind the version stamp and re-run init: the v14->v15 migration
    # must move the row into the table and delete the superseded entry.
    temp_db.qi(
        "UPDATE schema_meta SET value='14' WHERE key='version'", ())
    temp_db.close_connection()
    temp_db.init()

    rows = _registry_rows(temp_db, chat_id)
    assert len(rows) == 1
    assert rows[0]["room_uid"] == "deck_3"
    assert rows[0]["owning_book_id"] == book_id
    assert rows[0]["retired_turn_id"] is None
    assert temp_db.q(
        "SELECT id FROM lore_entries WHERE entry_uid LIKE 'room:%'") == []
    version = temp_db.q(
        "SELECT value FROM schema_meta WHERE key='version'", one=True)
    # The current version, not a literal: re-running init from v14 walks
    # every later migration too (v16 scheduled_events repartition, ...).
    assert int(version["value"]) == temp_db.SCHEMA_VERSION


# ---- Checkpoint snapshot + restore ----

def test_checkpoint_restore_round_trips_registry_and_book_retirement(temp_db):
    ids = _build_ship_chat(temp_db)
    chat_id = ids["chat_id"]
    before_rows = _registry_rows(temp_db, chat_id)
    snap = snapshot_state(chat_id)
    assert len(snap["room_registry"]) == 2, "snapshot must capture the table"
    assert any(b["retired_turn_id"] == ids["turn_id"]
               for b in snap["lorebooks"]), \
        "snapshot must capture book retirement"
    ensure_checkpoint(chat_id, 1)

    # Mutate everything the checkpoint should undo: retire the live room,
    # revive the retired one, add a stray row, un-retire the book.
    temp_db.qi("UPDATE room_registry SET retired_turn_id=? "
               "WHERE chat_id=? AND room_uid='deck_3'",
               (ids["turn_id"], chat_id))
    temp_db.qi("UPDATE room_registry SET retired_turn_id=NULL "
               "WHERE chat_id=? AND room_uid='boreas_hold'", (chat_id,))
    _add_registry_row(temp_db, chat_id, "stray_room", ids["canon"])
    temp_db.qi("UPDATE lorebooks SET retired_turn_id=NULL WHERE id=?",
               (ids["sunk_book"],))

    restore_checkpoint(chat_id, 1)

    assert _registry_rows(temp_db, chat_id) == before_rows
    assert temp_db.q("SELECT retired_turn_id FROM lorebooks WHERE id=?",
                     (ids["sunk_book"],), one=True)["retired_turn_id"] \
        == ids["turn_id"]


def test_restore_nulls_owner_of_a_vanished_book(temp_db):
    """FK safety: a snapshot registry row whose owning book no longer
    exists (and maps to nothing) restores with owner NULL instead of
    aborting the whole restore."""
    ids = _build_ship_chat(temp_db)
    chat_id = ids["chat_id"]
    ensure_checkpoint(chat_id, 1)
    blob = json.loads(temp_db.q(
        "SELECT blob FROM checkpoints WHERE chat_id=?", (chat_id,),
        one=True)["blob"])
    # Point one registry row at a book id that exists nowhere.
    for rr in blob["room_registry"]:
        if rr["room_uid"] == "deck_3":
            rr["owning_book_id"] = 999999
    # And drop that book from the snapshot so _restore_books can't map it.
    blob["lorebooks"] = [b for b in blob["lorebooks"]
                         if b["lorebook_id"] != ids["ship_book"]]
    temp_db.qi("UPDATE checkpoints SET blob=? WHERE chat_id=?",
               (json.dumps(blob), chat_id))

    restore_checkpoint(chat_id, 1)

    row = temp_db.q(
        "SELECT owning_book_id FROM room_registry WHERE chat_id=? AND "
        "room_uid='deck_3'", (chat_id,), one=True)
    assert row is not None and row["owning_book_id"] is None


# ---- Export / import ----

def test_export_import_round_trips_registry_with_remapped_ids(temp_db):
    ids = _build_ship_chat(temp_db)
    exported = app.chat_export(ids["chat_id"])
    assert len(exported["room_registry"]) == 2, "export must carry the table"

    imported = app.chat_import({"data": exported})
    ncid = imported["id"]

    rows = _registry_rows(temp_db, ncid)
    assert [r["room_uid"] for r in rows] == ["boreas_hold", "deck_3"]
    new_turn = temp_db.q("SELECT id FROM turns WHERE chat_id=?", (ncid,),
                         one=True)["id"]
    new_ship_book = temp_db.q(
        "SELECT id FROM lorebooks WHERE chat_id=? AND anchor_entity_id=?",
        (ncid, "ship_a"), one=True)["id"]
    by_uid = {r["room_uid"]: r for r in rows}
    assert by_uid["deck_3"]["owning_book_id"] == new_ship_book
    assert by_uid["deck_3"]["created_turn_id"] == new_turn
    assert by_uid["deck_3"]["retired_turn_id"] is None
    assert by_uid["deck_3"]["parent_entity"] == "ship_a"
    assert by_uid["boreas_hold"]["retired_turn_id"] == new_turn

    # Book retirement survived with a remapped turn FK.
    nbook = temp_db.q(
        "SELECT retired_turn_id FROM lorebooks WHERE chat_id=? AND name=?",
        (ncid, "The Boreas"), one=True)
    assert nbook["retired_turn_id"] == new_turn


def test_import_tolerates_archives_without_the_new_keys(temp_db):
    """Old exports (pre-Phase-2) have neither room_registry nor
    lorebooks.retired_turn_id; import must not choke on their absence."""
    ids = _build_ship_chat(temp_db)
    exported = app.chat_export(ids["chat_id"])
    exported.pop("room_registry", None)
    for b in exported["lorebooks"]:
        b["book"].pop("retired_turn_id", None)

    imported = app.chat_import({"data": exported})
    assert _registry_rows(temp_db, imported["id"]) == []


# ---- Branch / clone ----

def test_branch_remaps_registry_owner_entity_and_turn_ids(temp_db):
    ids = _build_ship_chat(temp_db)
    branched = app.turn_branch(ids["turn_id"])
    ncid = branched["id"]

    rows = _registry_rows(temp_db, ncid)
    assert len(rows) == 2
    by_name = {r["name"]: r for r in rows}
    deck = by_name["Deck 3"]

    # parent_entity followed the branch's fresh world-entity id.
    new_ent = temp_db.q(
        "SELECT entity_id FROM world_entities WHERE chat_id=?",
        (ncid,), one=True)["entity_id"]
    assert new_ent != "ship_a"
    assert deck["parent_entity"] == new_ent

    # owning_book_id points at the branch's own cloned vehicle book.
    nbook = temp_db.q(
        "SELECT id, retired_turn_id FROM lorebooks WHERE chat_id=? AND "
        "anchor_entity_id=?", (ncid, new_ent), one=True)
    assert deck["owning_book_id"] == nbook["id"]

    # Turn FKs remapped to the branch's cloned turn rows.
    new_turn = temp_db.q("SELECT id FROM turns WHERE chat_id=?", (ncid,),
                         one=True)["id"]
    assert deck["created_turn_id"] == new_turn
    assert by_name["Cargo Hold"]["retired_turn_id"] == new_turn

    # The retired book kept its (remapped) retirement stamp.
    sunk = temp_db.q(
        "SELECT retired_turn_id FROM lorebooks WHERE chat_id=? AND name=?",
        (ncid, "The Boreas"), one=True)
    assert sunk["retired_turn_id"] == new_turn

    # And the branch's checkpoint blobs carry the remapped registry too:
    # a restore inside the branch must not resurrect source-chat ids.
    for cp in temp_db.q("SELECT blob FROM checkpoints WHERE chat_id=?",
                        (ncid,)):
        blob = json.loads(cp["blob"])
        for rr in blob.get("room_registry") or []:
            assert rr["parent_entity"] in (None, new_ent)
            assert rr["owning_book_id"] != ids["ship_book"]
    restore_checkpoint(ncid, ids["turn_id"] and 1)
    assert len(_registry_rows(temp_db, ncid)) == 2
