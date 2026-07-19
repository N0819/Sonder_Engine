"""Regression tests for mobile ("vehicle" book_type) lorebooks:
sync_anchored_books reparents an anchor_entity_id-flagged lorebook to
wherever its anchor entity currently is, so the vehicle's own lore (and
anything parented under it) follows the vehicle instead of staying
pinned to wherever it started."""

from __future__ import annotations

import time

import commit


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


def test_vehicle_reparents_to_the_location_matching_its_current_room(temp_db):
    chat_id = _make_chat(temp_db)
    port = _make_location_book(temp_db, "Port Kael", "port_kael", chat_id=chat_id)
    meridian = _make_location_book(temp_db, "Meridian Station", "meridian_station", chat_id=chat_id)
    ship = _make_vehicle_book(temp_db, "The Wayfarer", "the_wayfarer", parent_id=port, chat_id=chat_id)

    commit.sync_anchored_books(chat_id, {"positions": {"the_wayfarer": "meridian_station"}})

    row = temp_db.q("SELECT parent_id FROM lorebooks WHERE id=?", (ship,), one=True)
    assert row["parent_id"] == meridian


def test_vehicle_docked_where_no_matching_location_book_exists_is_untouched(temp_db):
    chat_id = _make_chat(temp_db)
    port = _make_location_book(temp_db, "Port Kael", "port_kael", chat_id=chat_id)
    ship = _make_vehicle_book(temp_db, "The Wayfarer", "the_wayfarer", parent_id=port, chat_id=chat_id)

    commit.sync_anchored_books(chat_id, {"positions": {"the_wayfarer": "deep_space_unknown"}})

    row = temp_db.q("SELECT parent_id FROM lorebooks WHERE id=?", (ship,), one=True)
    assert row["parent_id"] == port


def test_child_books_travel_with_the_reparented_vehicle(temp_db):
    chat_id = _make_chat(temp_db)
    port = _make_location_book(temp_db, "Port Kael", "port_kael", chat_id=chat_id)
    meridian = _make_location_book(temp_db, "Meridian Station", "meridian_station", chat_id=chat_id)
    ship = _make_vehicle_book(temp_db, "The Wayfarer", "the_wayfarer", parent_id=port, chat_id=chat_id)
    crew_log = temp_db.qi(
        "INSERT INTO lorebooks(name,chat_id,book_type,parent_id) VALUES(?,?,?,?)",
        ("Crew Log", chat_id, "general", ship),
    )

    commit.sync_anchored_books(chat_id, {"positions": {"the_wayfarer": "meridian_station"}})

    ship_row = temp_db.q("SELECT parent_id FROM lorebooks WHERE id=?", (ship,), one=True)
    crew_row = temp_db.q("SELECT parent_id FROM lorebooks WHERE id=?", (crew_log,), one=True)
    assert ship_row["parent_id"] == meridian
    # Never touched directly -- still parented to the ship, which moved.
    assert crew_row["parent_id"] == ship


def test_non_anchored_books_are_ignored(temp_db):
    chat_id = _make_chat(temp_db)
    port = _make_location_book(temp_db, "Port Kael", "port_kael", chat_id=chat_id)
    plain = temp_db.qi(
        "INSERT INTO lorebooks(name,chat_id,book_type,parent_id) VALUES(?,?,?,?)",
        ("Plain Book", chat_id, "general", port),
    )

    # Should not raise or touch anything with no anchored books at all.
    commit.sync_anchored_books(chat_id, {"positions": {"something": "meridian_station"}})

    row = temp_db.q("SELECT parent_id FROM lorebooks WHERE id=?", (plain,), one=True)
    assert row["parent_id"] == port


def test_missing_position_for_anchor_leaves_vehicle_untouched(temp_db):
    chat_id = _make_chat(temp_db)
    port = _make_location_book(temp_db, "Port Kael", "port_kael", chat_id=chat_id)
    ship = _make_vehicle_book(temp_db, "The Wayfarer", "the_wayfarer", parent_id=port, chat_id=chat_id)

    commit.sync_anchored_books(chat_id, {"positions": {}})

    row = temp_db.q("SELECT parent_id FROM lorebooks WHERE id=?", (ship,), one=True)
    assert row["parent_id"] == port
