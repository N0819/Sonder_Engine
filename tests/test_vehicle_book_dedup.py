"""One vehicle -> one book (movement/space Phase 2, item 6).

Pre-existing two-ferry-books bug: _apply_mapping_book_ops' dup check
compared raw anchor ids only, so two DIFFERENT entity-id aliases of ONE
vehicle ('ferry_tamsin' vs 'tamsin_ferry_entity') minted two books for
the same ship, and a punctuation/case drift in the proposed name forked
one too. The dedup now resolves anchors to a canonical entity (via
world_entities/scene ids, names, and aliases, slug + sorted-token keys)
and compares names by normalized slug; commit_world_entities' automatic
vehicle-book creation applies the same canonical comparison.
"""

from __future__ import annotations

import json
import time

import commit
from pipeline_context import ChatData, PipelineContext, TurnData


def _make_chat(temp_db, *, entity_id="ferry_tamsin", entity_name="The Tamsin",
               aliases=("Tamsin Ferry",)):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    canon = temp_db.qi(
        "INSERT INTO lorebooks(name,chat_id,book_type) VALUES(?,?,?)",
        ("Canon", chat_id, "general"),
    )
    temp_db.qi("UPDATE chats SET lorebook_id=? WHERE id=?", (canon, chat_id))
    temp_db.qi(
        "INSERT INTO world_entities(entity_id,chat_id,kind,subtype,name,"
        "payload) VALUES(?,?,?,?,?,?)",
        (entity_id, chat_id, "vehicle", "", entity_name,
         json.dumps({"aliases": list(aliases)})),
    )
    book_id = temp_db.qi(
        "INSERT INTO lorebooks(name,chat_id,book_type,anchor_entity_id,"
        "parent_id) VALUES(?,?,?,?,?)",
        (entity_name, chat_id, "vehicle", entity_id, canon),
    )
    return chat_id, canon, book_id


def _book_count(temp_db, chat_id):
    return temp_db.q(
        "SELECT COUNT(*) c FROM lorebooks WHERE chat_id=? AND "
        "book_type='vehicle'", (chat_id,), one=True)["c"]


def test_alias_anchor_maps_to_the_existing_vehicle_book(temp_db):
    """The model re-coins the ferry under a different entity-id alias:
    the proposal must resolve to the SAME book, not mint a second one."""
    chat_id, canon, book_id = _make_chat(temp_db)

    temp_map = commit._apply_mapping_book_ops(chat_id, canon, [{
        "op": "create", "temp_id": "b1", "name": "Tamsin Ferry",
        "book_type": "vehicle", "anchor_entity_id": "tamsin_ferry_entity",
    }])

    assert _book_count(temp_db, chat_id) == 1, "one vehicle, one book"
    assert temp_map == {"b1": book_id}


def test_normalized_name_collision_dedups(temp_db):
    chat_id, canon, book_id = _make_chat(temp_db)

    temp_map = commit._apply_mapping_book_ops(chat_id, canon, [{
        "op": "create", "temp_id": "b1", "name": "the  tamsin!",
        "book_type": "vehicle",
    }])

    assert _book_count(temp_db, chat_id) == 1
    assert temp_map == {"b1": book_id}


def test_distinct_vehicles_still_get_their_own_books(temp_db):
    """Ledger, not cage: genuinely different vehicles are never merged."""
    chat_id, canon, _ = _make_chat(temp_db)
    temp_db.qi(
        "INSERT INTO world_entities(entity_id,chat_id,kind,subtype,name,"
        "payload) VALUES(?,?,?,?,?,?)",
        ("skiff_boreas", chat_id, "vehicle", "", "The Boreas", "{}"),
    )

    commit._apply_mapping_book_ops(chat_id, canon, [{
        "op": "create", "name": "The Boreas", "book_type": "vehicle",
        "anchor_entity_id": "skiff_boreas",
    }])

    assert _book_count(temp_db, chat_id) == 2


def test_created_book_stores_the_canonical_anchor_id(temp_db):
    """A book created against an alias spelling is anchored to the
    canonical entity id, so sync_anchored_books tracks the real entity."""
    chat_id, canon, _ = _make_chat(temp_db)
    temp_db.qi("DELETE FROM lorebooks WHERE book_type='vehicle'", ())

    commit._apply_mapping_book_ops(chat_id, canon, [{
        "op": "create", "name": "Tamsin Ferry", "book_type": "vehicle",
        "anchor_entity_id": "tamsin_ferry_entity",
    }])

    row = temp_db.q(
        "SELECT anchor_entity_id FROM lorebooks WHERE chat_id=? AND "
        "book_type='vehicle'", (chat_id,), one=True)
    assert row["anchor_entity_id"] == "ferry_tamsin"


def test_auto_vehicle_book_creation_respects_alias_anchors(temp_db):
    """commit_world_entities' deterministic vehicle-book creation must
    find the existing book through the canonical-anchor comparison when
    the director re-coins the vehicle under an alias entity id."""
    chat_id, canon, book_id = _make_chat(temp_db)
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "x", time.time()),
    )
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=canon, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="x",
                      created=time.time()),
        cast=[], input="x",
    )
    ctx.director_resolve = {
        "resolved_event": "beat", "dialogue_log": [],
        "state_diff": {"entities": {"tamsin_ferry_entity": {
            "name": "Tamsin Ferry", "kind": "vehicle",
            "interior_rooms": ["ferry_deck"], "state": {},
        }}},
    }

    commit.commit_world_entities(ctx, nonce=0)

    assert _book_count(temp_db, chat_id) == 1, \
        "the alias re-coin must not mint a second vehicle book"
