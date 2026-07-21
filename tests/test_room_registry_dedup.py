"""Regression tests for the derived room registry + commit-side structural
dedup (movement/space Phase 1, item 4).

Two live failure classes, one root -- commit had no memory of which rooms
an owner already has:
- two structurally identical vehicles minting the same flat key ('deck_3')
  silently merged one ship's deck into the other's;
- the same owner's room re-minted under a fresh key ('deck_three' for an
  existing 'Deck 3') created a live duplicate room.
The registry rows are DERIVED lore_entries (category 'layout', entry_uid
'room:<book_id>:<room_key>'), rewritten each commit; scene JSON stays the
sole authority. Ledger, not cage: collisions are rekeyed/redirected, never
rejected.
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
    uid_a = f"room:{books['ship_a']}:deck_3"
    uid_b = f"room:{books['ship_b']}:{new_key}"
    assert temp_db.q("SELECT id FROM lore_entries WHERE entry_uid=?",
                     (uid_a,), one=True)
    assert temp_db.q("SELECT id FROM lore_entries WHERE entry_uid=?",
                     (uid_b,), one=True)


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
        "SELECT entry_uid FROM lore_entries WHERE lorebook_id=?",
        (books["ship_a"],),
    )
    assert [r["entry_uid"] for r in rows] == [f"room:{books['ship_a']}:deck_3"]


def test_stale_registry_rows_are_swept_when_the_room_is_gone(temp_db):
    scene = _two_ship_scene()
    ctx, books, _ = _make_ctx(temp_db, scene, {}, with_books=("ship_a",))
    prepared = commit.prepare_scene_commit(ctx)
    commit.commit_scene(ctx, nonce=0, prepared=prepared)

    # The deck is gone next beat (and nobody occupies it).
    scene2 = json.loads(json.dumps(scene))
    ctx.director_resolve = {
        "resolved_event": "gone", "dialogue_log": [],
        "state_diff": {"remove_rooms": ["deck_3"]},
    }
    prepared = commit.prepare_scene_commit(ctx)
    commit.commit_scene(ctx, nonce=0, prepared=prepared)

    rows = temp_db.q(
        "SELECT entry_uid FROM lore_entries WHERE lorebook_id=?",
        (books["ship_a"],),
    )
    assert rows == []
