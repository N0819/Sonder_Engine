"""Tests for SQLite transaction and connection behavior."""

import sqlite3

import pytest

def test_nested_transactions_use_savepoints(temp_db):
    with temp_db.transaction():
        temp_db.qi(
            "INSERT INTO settings(key,value) VALUES(?,?)",
            ("outer", "one"),
        )

        with temp_db.transaction():
            temp_db.qi(
                "INSERT INTO settings(key,value) VALUES(?,?)",
                ("inner", "two"),
            )

    rows = temp_db.q(
        "SELECT key,value FROM settings ORDER BY key",
    )

    assert [(row["key"], row["value"]) for row in rows] == [
        ("inner", "two"),
        ("outer", "one"),
    ]

def test_inner_failure_rolls_back_to_savepoint(temp_db):
    with temp_db.transaction():
        temp_db.qi(
            "INSERT INTO settings(key,value) VALUES(?,?)",
            ("outer", "kept"),
        )

        with pytest.raises(sqlite3.IntegrityError):
            with temp_db.transaction():
                temp_db.qi(
                    "INSERT INTO settings(key,value) VALUES(?,?)",
                    ("inner", "first"),
                )
                temp_db.qi(
                    "INSERT INTO settings(key,value) VALUES(?,?)",
                    ("inner", "duplicate"),
                )

        temp_db.qi(
            "INSERT INTO settings(key,value) VALUES(?,?)",
            ("after", "kept"),
        )

    assert temp_db.get_setting("outer") == "kept"
    assert temp_db.get_setting("after") == "kept"
    assert temp_db.get_setting("inner") is None

def test_outer_failure_rolls_back_everything(temp_db):
    with pytest.raises(RuntimeError, match="abort"):
        with temp_db.transaction():
            temp_db.qi(
                "INSERT INTO settings(key,value) VALUES(?,?)",
                ("temporary", "value"),
            )
            raise RuntimeError("abort")

    assert temp_db.get_setting("temporary") is None

def test_qtx_requires_transaction(temp_db):
    with pytest.raises(RuntimeError, match="transaction"):
        temp_db.qtx(
            "INSERT INTO settings(key,value) VALUES(?,?)",
            ("invalid", "write"),
        )