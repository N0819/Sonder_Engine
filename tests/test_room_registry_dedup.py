"""Regression tests for the room registry + commit-side structural dedup
(movement/space Phase 1 item 4; table encoding from Phase 2 item 1).

Two live failure classes, one root -- commit had no memory of which rooms
an owner already has:
- two structurally identical vehicles minting the same flat key ('deck_3')
  silently merged one ship's deck into the other's;
- the same owner's room re-minted under a fresh key ('deck_three' for an
  existing 'Deck 3') created a live duplicate room.
The registry is the normalized `room_registry` table (it supersedes
Phase 1's derived lore_entries encoding), authoritative for room identity,
dedup, and retirement only; the scene JSON stays the sole authority for
live rooms. Removal RETIRES a row instead of deleting it. Ledger, not
cage: collisions are rekeyed/redirected, never rejected.
"""

import json
import time

import commit
from pipeline_context import ChatData, PipelineContext, TurnData


def _make_ctx(temp_db, scene, diff, *, with_books=()):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    canon = temp_db.qi(
        "INSERT INTO lorebooks(name,chat_id,book_type) VALUES(?,?,?)",
        ("Canon", chat_id, "general"),
    )
    temp_db.qi("UPDATE chats SET lorebook_id=? WHERE id=?", (canon, chat_id))
    books = {}
    for anchor in with_books:
        books[anchor] = temp_db.qi(
            "INSERT INTO lorebooks(name,chat_id,book_type,anchor_entity_id,"
            "parent_id) VALUES(?,?,?,?,?)",
            (anchor, chat_id, "vehicle", anchor, canon),
        )
    temp_db.wset(chat_id, "scene", scene)
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "x", time.time()),
    )
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=canon, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="x",
                      created=time.time()),
        cast=[],
        input="x",
    )
    ctx.director_resolve = {
        "resolved_event": "beat", "dialogue_log": [], "state_diff": diff,
    }
    return ctx, books, canon


def _two_ship_scene():
    return {
        "location": "Harbor",
        "rooms": {
            "harbor": {"name": "Harbor", "adjacent": []},
            "deck_3": {"name": "Deck 3", "parent_entity": "ship_a",
                       "adjacent": []},
        },
        "positions": {"ship_a": "harbor", "ship_b": "harbor",
                      "The Stranger": "harbor"},
        "entities": {
            "ship_a": {"name": "The Aurora", "kind": "vehicle",
                       "interior_rooms": ["deck_3"], "state": {}},
            "ship_b": {"name": "The Boreas", "kind": "vehicle",
                       "interior_rooms": [], "state": {}},
        },
        "attire": {}, "overlays": {},
    }


def test_two_ships_minting_deck_3_do_not_collide(temp_db):
    diff = {
        "rooms": {
            "deck_3": {"name": "Deck 3", "parent_entity": "ship_b",
                       "adjacent": []},
        },
        "positions": {"The Stranger": "deck_3"},
    }
    ctx, books, _ = _make_ctx(
        temp_db, _two_ship_scene(), diff, with_books=("ship_a", "ship_b"))

    prepared = commit.prepare_scene_commit(ctx)
    sc = prepared["scene"]

    # Ship A's deck survives untouched; ship B's new deck got its own key.
    assert sc["rooms"]["deck_3"]["parent_entity"] == "ship_a"
    rekeyed = [rid for rid, r in sc["rooms"].items()
               if r.get("parent_entity") == "ship_b"]
    assert len(rekeyed) == 1
    new_key = rekeyed[0]
    assert new_key != "deck_3"
    # Position references follow the rekey.
    assert sc["positions"]["The Stranger"] == new_key
    assert any("collision" in w.casefold() for w in ctx.warnings)

    # Each ship's room registers under its OWN book scope.
    commit.commit_scene(ctx, nonce=0, prepared=prepared)
    row_a = temp_db.q(
        "SELECT * FROM room_registry WHERE chat_id=? AND room_uid=?",
        (ctx.chat.id, "deck_3"), one=True)
    row_b = temp_db.q(
        "SELECT * FROM room_registry WHERE chat_id=? AND room_uid=?",
        (ctx.chat.id, new_key), one=True)
    assert row_a and row_a["owning_book_id"] == books["ship_a"] \
        and row_a["parent_entity"] == "ship_a"
    assert row_b and row_b["owning_book_id"] == books["ship_b"] \
        and row_b["parent_entity"] == "ship_b"


def test_same_owner_same_name_remint_redirects_to_existing_room(temp_db):
    scene = _two_ship_scene()
    diff = {
        "rooms": {
            # Same owner, same display name, fresh key: the live
            # duplicate-room class at creation.
            "deck_three": {"name": "Deck 3", "parent_entity": "ship_a",
                           "desc": "Re-minted.", "adjacent": []},
        },
        "positions": {"The Stranger": "deck_three"},
    }
    ctx, _, _ = _make_ctx(temp_db, scene, diff, with_books=("ship_a",))

    prepared = commit.prepare_scene_commit(ctx)
    sc = prepared["scene"]

    assert "deck_three" not in sc["rooms"], "no duplicate room minted"
    assert sc["rooms"]["deck_3"]["desc"] == "Re-minted."
    assert sc["positions"]["The Stranger"] == "deck_3"
    assert any("redirected" in w.casefold() for w in ctx.warnings)


def test_registry_alias_dedups_after_the_room_was_registered(temp_db):
    """The registry's aliases catch a re-mint whose fresh key does not
    lexically match the live key ('third_deck' for registered 'Deck 3')."""
    scene = _two_ship_scene()
    ctx, books, _ = _make_ctx(temp_db, scene, {}, with_books=("ship_a",))
    prepared = commit.prepare_scene_commit(ctx)
    commit.commit_scene(ctx, nonce=0, prepared=prepared)

    diff = {"rooms": {"third_deck": {"name": "Deck 3",
                                     "parent_entity": "ship_a",
                                     "adjacent": []}}}
    ctx.director_resolve = {"resolved_event": "again", "dialogue_log": [],
                            "state_diff": diff}
    prepared = commit.prepare_scene_commit(ctx)
    sc = prepared["scene"]
    assert "third_deck" not in sc["rooms"]
    assert "deck_3" in sc["rooms"]


def test_genuinely_new_room_is_never_rejected(temp_db):
    """Ledger, not cage: a new room with a new name mints untouched."""
    diff = {"rooms": {"engine_room": {"name": "Engine Room",
                                      "parent_entity": "ship_a",
                                      "adjacent": []}}}
    ctx, _, _ = _make_ctx(
        temp_db, _two_ship_scene(), diff, with_books=("ship_a",))
    prepared = commit.prepare_scene_commit(ctx)
    assert "engine_room" in prepared["scene"]["rooms"]
    assert not ctx.warnings


def test_dedup_never_mutates_the_persisted_resolve_diff(temp_db):
    """The resolve step/variant holding this diff was already persisted;
    the dedup rewrite must operate on a copy."""
    diff = {
        "rooms": {"deck_3": {"name": "Deck 3", "parent_entity": "ship_b",
                             "adjacent": []}},
        "positions": {"The Stranger": "deck_3"},
    }
    ctx, _, _ = _make_ctx(
        temp_db, _two_ship_scene(), diff, with_books=("ship_a", "ship_b"))
    commit.prepare_scene_commit(ctx)
    assert "deck_3" in ctx.director_resolve["state_diff"]["rooms"]
    assert ctx.director_resolve["state_diff"]["positions"]["The Stranger"] \
        == "deck_3"


def test_registry_rows_are_rewritten_not_duplicated(temp_db):
    scene = _two_ship_scene()
    ctx, books, _ = _make_ctx(temp_db, scene, {}, with_books=("ship_a",))
    for _ in range(2):
        prepared = commit.prepare_scene_commit(ctx)
        commit.commit_scene(ctx, nonce=0, prepared=prepared)
    rows = temp_db.q(
        "SELECT room_uid FROM room_registry WHERE owning_book_id=?",
        (books["ship_a"],),
    )
    assert [r["room_uid"] for r in rows] == ["deck_3"]


def test_removed_room_is_retired_not_deleted(temp_db):
    """Retire-not-delete (Phase 2 item 2): a removed room's registry row
    survives with retired_turn_id set -- identity/history is kept -- and a
    retired room's aliases no longer participate in dedup."""
    scene = _two_ship_scene()
    ctx, books, _ = _make_ctx(temp_db, scene, {}, with_books=("ship_a",))
    prepared = commit.prepare_scene_commit(ctx)
    commit.commit_scene(ctx, nonce=0, prepared=prepared)

    # The deck is gone next beat (and nobody occupies it).
    ctx.director_resolve = {
        "resolved_event": "gone", "dialogue_log": [],
        "state_diff": {"remove_rooms": ["deck_3"]},
    }
    prepared = commit.prepare_scene_commit(ctx)
    commit.commit_scene(ctx, nonce=0, prepared=prepared)

    row = temp_db.q(
        "SELECT * FROM room_registry WHERE chat_id=? AND room_uid=?",
        (ctx.chat.id, "deck_3"), one=True,
    )
    assert row is not None, "the row must survive removal"
    assert row["retired_turn_id"] == ctx.turn.id
    # A retired room no longer feeds the alias-dedup index.
    assert commit._registry_alias_index(ctx.chat.id, books["ship_a"]) == {}


def test_reminted_room_key_revives_its_retired_row(temp_db):
    """Same chat, same key, minted live again: the registry records the
    identity as live again (one row per room_uid, ever)."""
    scene = _two_ship_scene()
    ctx, books, _ = _make_ctx(temp_db, scene, {}, with_books=("ship_a",))
    prepared = commit.prepare_scene_commit(ctx)
    commit.commit_scene(ctx, nonce=0, prepared=prepared)

    ctx.director_resolve = {
        "resolved_event": "gone", "dialogue_log": [],
        "state_diff": {"remove_rooms": ["deck_3"]},
    }
    commit.commit_scene(ctx, nonce=0,
                        prepared=commit.prepare_scene_commit(ctx))
    ctx.director_resolve = {
        "resolved_event": "rebuilt", "dialogue_log": [],
        "state_diff": {"rooms": {"deck_3": {
            "name": "Deck 3", "parent_entity": "ship_a", "adjacent": []}}},
    }
    commit.commit_scene(ctx, nonce=0,
                        prepared=commit.prepare_scene_commit(ctx))

    rows = temp_db.q(
        "SELECT * FROM room_registry WHERE chat_id=? AND room_uid=?",
        (ctx.chat.id, "deck_3"),
    )
    assert len(rows) == 1
    assert rows[0]["retired_turn_id"] is None


def test_dedup_reads_the_registry_table(temp_db):
    """Fail-without check for the table read, via accumulated aliases: a
    room renamed in the scene keeps its OLD name only in room_registry, so
    a re-mint under the old name can only be caught through the table.
    Deleting the rows out from under dedup makes the redirect vanish --
    proving dedup_minted_rooms consults room_registry, not any leftover
    lore-entry index or the live scene alone."""
    scene = _two_ship_scene()
    scene["rooms"]["bridge"] = {"name": "Command Bridge",
                                "parent_entity": "ship_a", "adjacent": []}
    ctx, books, _ = _make_ctx(temp_db, scene, {}, with_books=("ship_a",))
    commit.commit_scene(ctx, nonce=0,
                        prepared=commit.prepare_scene_commit(ctx))

    # The bridge is renamed; the registry keeps 'Command Bridge' as an
    # accumulated alias while the live scene forgets it.
    ctx.director_resolve = {
        "resolved_event": "renamed", "dialogue_log": [],
        "state_diff": {"rooms": {"bridge": {
            "name": "Ruined Bridge", "parent_entity": "ship_a",
            "adjacent": []}}},
    }
    commit.commit_scene(ctx, nonce=0,
                        prepared=commit.prepare_scene_commit(ctx))

    diff = {"rooms": {"command_bridge": {"name": "Command Bridge",
                                         "parent_entity": "ship_a",
                                         "adjacent": []}}}
    # Sanity: with the registry intact the alias redirect fires...
    renames = commit.dedup_minted_rooms(
        ctx.chat.id, temp_db.wget(ctx.chat.id, "scene", {}),
        json.loads(json.dumps(diff)))
    assert renames == {"command_bridge": "bridge"}
    # ...and with the table emptied it cannot.
    temp_db.qi("DELETE FROM room_registry WHERE chat_id=?", (ctx.chat.id,))
    renames = commit.dedup_minted_rooms(
        ctx.chat.id, temp_db.wget(ctx.chat.id, "scene", {}),
        json.loads(json.dumps(diff)))
    assert renames == {}
