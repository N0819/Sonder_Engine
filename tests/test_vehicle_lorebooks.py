"""Regression tests for mobile ("vehicle" book_type) lorebooks.

Movement/space Phase 1 (item 3) reversal: sync_anchored_books no longer
mutates parent_id to make a book follow its anchor entity -- that collapsed
"belongs to" (canonical containment, parent_id) into "is at" (live
presence). Presence is now a 'currently_within' lorebook_link, rewritten
from scene positions at every commit; parent_id is canonical and commit
never touches it. follow_for_retrieval stays on so docked-location lore is
still reachable through the vehicle book, but the link is retrieval
bookkeeping only -- never perception authorization.
"""

from __future__ import annotations

import time

import commit
from memory import (
    chat_lorebook_ids,
    dump_lorebook_links,
    restore_lorebook_links,
)


def _make_chat(db):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )


def _make_location_book(db, name, scope_location_id, chat_id=None):
    return db.qi(
        "INSERT INTO lorebooks(name,chat_id,book_type,scope_location_id) VALUES(?,?,?,?)",
        (name, chat_id, "location", scope_location_id),
    )


def _make_vehicle_book(db, name, anchor_entity_id, parent_id=None, chat_id=None):
    return db.qi(
        "INSERT INTO lorebooks(name,chat_id,book_type,anchor_entity_id,parent_id) "
        "VALUES(?,?,?,?,?)",
        (name, chat_id, "vehicle", anchor_entity_id, parent_id),
    )


def _within_links(db, book_id):
    return db.q(
        "SELECT target_book_id, follow_for_retrieval FROM lorebook_links "
        "WHERE source_book_id=? AND relation_type='currently_within'",
        (book_id,),
    )


def test_vehicle_move_retargets_currently_within_and_leaves_parent_alone(temp_db):
    chat_id = _make_chat(temp_db)
    port = _make_location_book(temp_db, "Port Kael", "port_kael", chat_id=chat_id)
    meridian = _make_location_book(temp_db, "Meridian Station", "meridian_station", chat_id=chat_id)
    ship = _make_vehicle_book(temp_db, "The Wayfarer", "the_wayfarer", parent_id=port, chat_id=chat_id)

    commit.sync_anchored_books(chat_id, {"positions": {"the_wayfarer": "port_kael"}})
    links = _within_links(temp_db, ship)
    assert [l["target_book_id"] for l in links] == [port]

    commit.sync_anchored_books(chat_id, {"positions": {"the_wayfarer": "meridian_station"}})
    links = _within_links(temp_db, ship)
    assert [l["target_book_id"] for l in links] == [meridian]
    # follow_for_retrieval on: docked-location lore stays reachable.
    assert links[0]["follow_for_retrieval"] == 1

    # parent_id is canonical "belongs to" -- commit NEVER mutates it now.
    row = temp_db.q("SELECT parent_id FROM lorebooks WHERE id=?", (ship,), one=True)
    assert row["parent_id"] == port


def test_child_books_stay_parented_to_the_vehicle(temp_db):
    chat_id = _make_chat(temp_db)
    port = _make_location_book(temp_db, "Port Kael", "port_kael", chat_id=chat_id)
    _make_location_book(temp_db, "Meridian Station", "meridian_station", chat_id=chat_id)
    ship = _make_vehicle_book(temp_db, "The Wayfarer", "the_wayfarer", parent_id=port, chat_id=chat_id)
    crew_log = temp_db.qi(
        "INSERT INTO lorebooks(name,chat_id,book_type,parent_id) VALUES(?,?,?,?)",
        ("Crew Log", chat_id, "general", ship),
    )

    commit.sync_anchored_books(chat_id, {"positions": {"the_wayfarer": "meridian_station"}})

    crew_row = temp_db.q("SELECT parent_id FROM lorebooks WHERE id=?", (crew_log,), one=True)
    assert crew_row["parent_id"] == ship


def test_retrieval_reaches_current_location_lore_through_the_link(temp_db):
    chat_id = _make_chat(temp_db)
    meridian = _make_location_book(temp_db, "Meridian Station", "meridian_station", chat_id=chat_id)
    ship = _make_vehicle_book(temp_db, "The Wayfarer", "the_wayfarer", chat_id=chat_id)
    temp_db.qi(
        "INSERT INTO chat_lorebooks(chat_id,lorebook_id,enabled) VALUES(?,?,1)",
        (chat_id, ship),
    )

    commit.sync_anchored_books(chat_id, {"positions": {"the_wayfarer": "meridian_station"}})

    resolved = chat_lorebook_ids(chat_id)
    assert ship in resolved
    assert meridian in resolved, (
        "docked-location book must stay retrievable via the "
        "currently_within link"
    )


def test_nested_vehicle_links_to_the_enclosing_vehicles_book(temp_db):
    """A van parked on a ferry's vehicle deck is 'currently within' the
    FERRY's book (the room's parent_entity resolves to its anchored book),
    not some location book -- this is what gives the monitoring walk the
    true nesting chain."""
    chat_id = _make_chat(temp_db)
    port = _make_location_book(temp_db, "Port Kael", "port_kael", chat_id=chat_id)
    ferry = _make_vehicle_book(temp_db, "The Ferry", "ferry", chat_id=chat_id)
    van = _make_vehicle_book(temp_db, "The Van", "van", chat_id=chat_id)

    scene = {
        "rooms": {
            "port_kael": {"name": "Port Kael"},
            "vehicle_deck": {"name": "Vehicle Deck", "parent_entity": "ferry"},
            "van_interior": {"name": "Van Interior", "parent_entity": "van"},
        },
        "positions": {"ferry": "port_kael", "van": "vehicle_deck"},
        "entities": {},
    }
    commit.sync_anchored_books(chat_id, scene)

    assert [l["target_book_id"] for l in _within_links(temp_db, ferry)] == [port]
    assert [l["target_book_id"] for l in _within_links(temp_db, van)] == [ferry]


def test_missing_position_leaves_last_link_standing(temp_db):
    chat_id = _make_chat(temp_db)
    port = _make_location_book(temp_db, "Port Kael", "port_kael", chat_id=chat_id)
    ship = _make_vehicle_book(temp_db, "The Wayfarer", "the_wayfarer", chat_id=chat_id)

    commit.sync_anchored_books(chat_id, {"positions": {"the_wayfarer": "port_kael"}})
    commit.sync_anchored_books(chat_id, {"positions": {}})

    assert [l["target_book_id"] for l in _within_links(temp_db, ship)] == [port]


def test_room_without_matching_book_clears_the_stale_link(temp_db):
    chat_id = _make_chat(temp_db)
    _make_location_book(temp_db, "Port Kael", "port_kael", chat_id=chat_id)
    ship = _make_vehicle_book(temp_db, "The Wayfarer", "the_wayfarer", chat_id=chat_id)

    commit.sync_anchored_books(chat_id, {"positions": {"the_wayfarer": "port_kael"}})
    commit.sync_anchored_books(chat_id, {"positions": {"the_wayfarer": "deep_space_unknown"}})

    # The ship is provably elsewhere; the old presence link must not linger.
    assert _within_links(temp_db, ship) == []


def test_non_anchored_books_are_ignored(temp_db):
    chat_id = _make_chat(temp_db)
    port = _make_location_book(temp_db, "Port Kael", "port_kael", chat_id=chat_id)
    plain = temp_db.qi(
        "INSERT INTO lorebooks(name,chat_id,book_type,parent_id) VALUES(?,?,?,?)",
        ("Plain Book", chat_id, "general", port),
    )

    commit.sync_anchored_books(chat_id, {"positions": {"something": "meridian_station"}})

    row = temp_db.q("SELECT parent_id FROM lorebooks WHERE id=?", (plain,), one=True)
    assert row["parent_id"] == port
    assert _within_links(temp_db, plain) == []


def test_currently_within_round_trips_through_dump_and_restore(temp_db):
    """Checkpoint/export snapshots links via dump_lorebook_links and
    restores them via restore_lorebook_links -> add_lorebook_link, which
    coerces unknown relation types to 'related' -- so 'currently_within'
    must be a registered link type or the round-trip silently rewrites it."""
    chat_id = _make_chat(temp_db)
    port = _make_location_book(temp_db, "Port Kael", "port_kael", chat_id=chat_id)
    ship = _make_vehicle_book(temp_db, "The Wayfarer", "the_wayfarer", chat_id=chat_id)
    commit.sync_anchored_books(chat_id, {"positions": {"the_wayfarer": "port_kael"}})

    links = dump_lorebook_links([port, ship])
    assert any(l["relation_type"] == "currently_within" for l in links)

    chat2 = _make_chat(temp_db)
    port2 = _make_location_book(temp_db, "Port Kael", "port_kael", chat_id=chat2)
    ship2 = _make_vehicle_book(temp_db, "The Wayfarer", "the_wayfarer", chat_id=chat2)
    restore_lorebook_links(chat2, {port: port2, ship: ship2}, links)

    restored = temp_db.q(
        "SELECT relation_type, target_book_id FROM lorebook_links "
        "WHERE source_book_id=?",
        (ship2,),
    )
    assert [(r["relation_type"], r["target_book_id"]) for r in restored] == [
        ("currently_within", port2)
    ]
