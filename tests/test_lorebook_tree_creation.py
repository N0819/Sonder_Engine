"""Regression tests for live lorebook-tree creation, added after a live
playtest found the mapping/director pipeline only ever created ONE flat
canon lorebook and filed every entry -- locations, mechanics, AND
vehicles -- into it, despite the lorebook tree data model (parent_id,
book_type, scope_world_id, scope_location_id) already existing and being
exercised by the separate, manual lorebook-import/reinterpret flow.

Two complementary fixes:
1. Deterministic: an entity committed with kind="vehicle" and
   interior_rooms automatically gets its own anchored "vehicle" book
   (commit_world_entities) -- works at zero model compliance, matching
   this codebase's preference for deterministic detection over LLM
   compliance wherever an option exists.
2. Model-proposed, deterministically validated: commit_mapping's
   book_ops lets the model propose additional child books (locations,
   factions, etc.) for genuinely new subjects lorebook_manifest shows no
   existing book already covers -- validated/capped/deduped in
   _apply_mapping_book_ops, never trusted blindly.
"""

from __future__ import annotations

import json
import time

import pytest

import commit
from character_schema import default_character_data
from pipeline_context import ChatData, PipelineContext, TurnData


def _make_chat(db):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )


def _make_ctx(chat_id, turn_idx, state_diff, lorebook_id=None):
    turn_id = db_qi_turn(chat_id, turn_idx)
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None, lorebook_id=lorebook_id,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=turn_idx, player_input="test",
                      created=time.time(), frame_id=None),
        cast=[], input="test",
    )
    ctx.director_resolve = {"state_diff": state_diff}
    return ctx


def db_qi_turn(chat_id, idx):
    import db
    return db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, idx, "test", time.time()),
    )


class TestDeterministicVehicleBookCreation:
    def test_a_new_vehicle_entity_gets_its_own_anchored_book(self, temp_db):
        chat_id = _make_chat(temp_db)
        ctx = _make_ctx(chat_id, 1, {
            "entities": {
                "tardis": {
                    "kind": "vehicle", "name": "TARDIS",
                    "interior_rooms": ["tardis_console_room"],
                },
            },
        })

        commit.commit_world_entities(ctx, nonce=0)

        book = temp_db.q(
            "SELECT * FROM lorebooks WHERE chat_id=? AND anchor_entity_id='tardis'",
            (chat_id,), one=True,
        )
        assert book is not None
        assert book["book_type"] == "vehicle"
        assert book["name"] == "TARDIS"

    def test_a_non_vehicle_entity_gets_no_book(self, temp_db):
        chat_id = _make_chat(temp_db)
        ctx = _make_ctx(chat_id, 1, {
            "entities": {"crate": {"kind": "object", "name": "Supply Crate"}},
        })

        commit.commit_world_entities(ctx, nonce=0)

        book = temp_db.q(
            "SELECT * FROM lorebooks WHERE chat_id=? AND anchor_entity_id='crate'",
            (chat_id,), one=True,
        )
        assert book is None

    def test_a_vehicle_without_interior_rooms_gets_no_book(self, temp_db):
        chat_id = _make_chat(temp_db)
        ctx = _make_ctx(chat_id, 1, {
            "entities": {"drone": {"kind": "vehicle", "name": "Recon Drone"}},
        })

        commit.commit_world_entities(ctx, nonce=0)

        book = temp_db.q(
            "SELECT * FROM lorebooks WHERE chat_id=? AND anchor_entity_id='drone'",
            (chat_id,), one=True,
        )
        assert book is None

    def test_does_not_create_a_duplicate_on_a_later_turn(self, temp_db):
        chat_id = _make_chat(temp_db)
        ctx1 = _make_ctx(chat_id, 1, {
            "entities": {"tardis": {"kind": "vehicle", "name": "TARDIS",
                                    "interior_rooms": ["console_room"]}},
        })
        commit.commit_world_entities(ctx1, nonce=0)

        # A later turn re-committing the SAME entity (an update, not a
        # fresh INSERT) must not spawn a second book.
        ctx2 = _make_ctx(chat_id, 2, {
            "entities": {"tardis": {"kind": "vehicle", "name": "TARDIS",
                                    "interior_rooms": ["console_room", "wardrobe"]}},
        })
        commit.commit_world_entities(ctx2, nonce=0)

        books = temp_db.q(
            "SELECT * FROM lorebooks WHERE chat_id=? AND anchor_entity_id='tardis'",
            (chat_id,),
        )
        assert len(books) == 1


class TestApplyMappingBookOps:
    def test_creates_a_book_under_canon_by_default(self, temp_db):
        chat_id = _make_chat(temp_db)
        canon = temp_db.qi(
            "INSERT INTO lorebooks(name,chat_id,book_type) VALUES(?,?,?)",
            ("Canon", chat_id, "general"),
        )
        temp_map = commit._apply_mapping_book_ops(chat_id, canon, [
            {"op": "create", "temp_id": "t1", "name": "Halyard's Rest",
             "book_type": "location", "scope_location_id": "halyards_rest"},
        ])
        assert "t1" in temp_map
        book = temp_db.q("SELECT * FROM lorebooks WHERE id=?", (temp_map["t1"],), one=True)
        assert book["parent_id"] == canon
        assert book["book_type"] == "location"
        assert book["scope_location_id"] == "halyards_rest"

    def test_builds_a_multi_level_chain_via_temp_id_parenting(self, temp_db):
        chat_id = _make_chat(temp_db)
        canon = temp_db.qi(
            "INSERT INTO lorebooks(name,chat_id,book_type) VALUES(?,?,?)",
            ("Canon", chat_id, "general"),
        )
        temp_map = commit._apply_mapping_book_ops(chat_id, canon, [
            {"op": "create", "temp_id": "world", "name": "The System", "book_type": "world"},
            {"op": "create", "temp_id": "city", "name": "Aran's Reach",
             "book_type": "location", "parent_id": "world"},
            {"op": "create", "temp_id": "building", "name": "Market Dome",
             "book_type": "location", "parent_id": "city"},
        ])
        world_book = temp_db.q("SELECT * FROM lorebooks WHERE id=?", (temp_map["world"],), one=True)
        city_book = temp_db.q("SELECT * FROM lorebooks WHERE id=?", (temp_map["city"],), one=True)
        building_book = temp_db.q("SELECT * FROM lorebooks WHERE id=?", (temp_map["building"],), one=True)
        assert world_book["parent_id"] == canon
        assert city_book["parent_id"] == temp_map["world"]
        assert building_book["parent_id"] == temp_map["city"]

    def test_dedupes_by_name_instead_of_creating_a_second_book(self, temp_db):
        chat_id = _make_chat(temp_db)
        canon = temp_db.qi(
            "INSERT INTO lorebooks(name,chat_id,book_type) VALUES(?,?,?)",
            ("Canon", chat_id, "general"),
        )
        existing = temp_db.qi(
            "INSERT INTO lorebooks(name,chat_id,book_type,parent_id) VALUES(?,?,?,?)",
            ("Halyard's Rest", chat_id, "location", canon),
        )
        temp_map = commit._apply_mapping_book_ops(chat_id, canon, [
            {"op": "create", "temp_id": "t1", "name": "halyard's rest", "book_type": "location"},
        ])
        assert temp_map["t1"] == existing
        count = temp_db.q("SELECT COUNT(*) c FROM lorebooks WHERE chat_id=?", (chat_id,), one=True)["c"]
        assert count == 2  # canon + the one pre-existing book, no third created

    def test_dedupes_by_anchor_entity_id(self, temp_db):
        chat_id = _make_chat(temp_db)
        canon = temp_db.qi(
            "INSERT INTO lorebooks(name,chat_id,book_type) VALUES(?,?,?)",
            ("Canon", chat_id, "general"),
        )
        existing = temp_db.qi(
            "INSERT INTO lorebooks(name,chat_id,book_type,parent_id,anchor_entity_id) "
            "VALUES(?,?,?,?,?)",
            ("TARDIS", chat_id, "vehicle", canon, "tardis"),
        )
        temp_map = commit._apply_mapping_book_ops(chat_id, canon, [
            {"op": "create", "temp_id": "t1", "name": "The TARDIS", "book_type": "vehicle",
             "anchor_entity_id": "tardis"},
        ])
        assert temp_map["t1"] == existing

    def test_caps_at_three_new_books_per_turn(self, temp_db):
        chat_id = _make_chat(temp_db)
        canon = temp_db.qi(
            "INSERT INTO lorebooks(name,chat_id,book_type) VALUES(?,?,?)",
            ("Canon", chat_id, "general"),
        )
        ops = [
            {"op": "create", "temp_id": f"t{i}", "name": f"Place {i}", "book_type": "location"}
            for i in range(5)
        ]
        temp_map = commit._apply_mapping_book_ops(chat_id, canon, ops)
        count = temp_db.q("SELECT COUNT(*) c FROM lorebooks WHERE chat_id=? AND parent_id=?",
                          (chat_id, canon), one=True)["c"]
        assert count == 3
        assert len(temp_map) == 3

    def test_an_invalid_book_type_falls_back_to_general(self, temp_db):
        chat_id = _make_chat(temp_db)
        canon = temp_db.qi(
            "INSERT INTO lorebooks(name,chat_id,book_type) VALUES(?,?,?)",
            ("Canon", chat_id, "general"),
        )
        temp_map = commit._apply_mapping_book_ops(chat_id, canon, [
            {"op": "create", "temp_id": "t1", "name": "Nonsense", "book_type": "not_a_real_type"},
        ])
        book = temp_db.q("SELECT * FROM lorebooks WHERE id=?", (temp_map["t1"],), one=True)
        assert book["book_type"] == "general"

    def test_an_unresolvable_parent_falls_back_to_canon(self, temp_db):
        chat_id = _make_chat(temp_db)
        canon = temp_db.qi(
            "INSERT INTO lorebooks(name,chat_id,book_type) VALUES(?,?,?)",
            ("Canon", chat_id, "general"),
        )
        temp_map = commit._apply_mapping_book_ops(chat_id, canon, [
            {"op": "create", "temp_id": "t1", "name": "Orphan", "book_type": "location",
             "parent_id": "no_such_temp_id"},
        ])
        book = temp_db.q("SELECT * FROM lorebooks WHERE id=?", (temp_map["t1"],), one=True)
        assert book["parent_id"] == canon


class TestCommitMappingRoutesIntoBookOpsTemp:
    def test_a_lore_op_referencing_a_book_ops_temp_id_lands_in_the_new_book(
        self, temp_db, monkeypatch,
    ):
        chat_id = _make_chat(temp_db)
        ctx = _make_ctx(chat_id, 1, {"introductions": ["The Long Odds"]})
        ctx.narrator = {"new_specifics": ["The Long Odds is Kess's freighter"]}
        ctx.mapping_stage = {}

        import llm_quality
        monkeypatch.setattr(llm_quality, "complete_validated_json", lambda **k: {
            "validated": [{"fact": "The Long Odds is Kess's freighter", "ok": True}],
            "lore_ops": [{
                "op": "create", "book_id": "vehicle_book", "keys": "long_odds",
                "content": "Kess's battered independent freighter.", "category": "technology",
            }],
            "book_ops": [{
                "op": "create", "temp_id": "vehicle_book", "name": "The Long Odds",
                "book_type": "vehicle", "anchor_entity_id": "long_odds",
            }],
        })

        commit.commit_mapping(ctx, nonce=0)

        vehicle_book = temp_db.q(
            "SELECT * FROM lorebooks WHERE chat_id=? AND anchor_entity_id='long_odds'",
            (chat_id,), one=True,
        )
        assert vehicle_book is not None
        entry = temp_db.q(
            "SELECT * FROM lore_entries WHERE lorebook_id=?", (vehicle_book["id"],), one=True,
        )
        assert entry is not None
        assert "freighter" in entry["content"]

        canon = temp_db.q("SELECT lorebook_id FROM chats WHERE id=?", (chat_id,), one=True)["lorebook_id"]
        canon_entries = temp_db.q("SELECT * FROM lore_entries WHERE lorebook_id=?", (canon,))
        assert canon_entries == []  # nothing leaked into the flat canon book
