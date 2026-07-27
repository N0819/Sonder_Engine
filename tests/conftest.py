"""Shared pytest configuration and fixtures."""

from __future__ import annotations

import os
import tempfile

import pytest


def pytest_collection_modifyitems(items):
    """Keep the fast tier free of measured database setup cost.

    The instrumented suite showed each ``temp_db`` setup taking roughly
    1.2--1.6 seconds in a populated development checkout.  Database-backed
    tests remain part of ``make test-full``; the fast tier concentrates on
    pure contracts, schemas, spatial rules, prompt boundaries, and frontend
    source guards.
    """

    for item in items:
        if "temp_db" in item.fixturenames:
            item.add_marker(pytest.mark.slow)


@pytest.fixture
def temp_db():
    """Create and configure a temporary test database."""
    fd, db_path = tempfile.mkstemp(
        suffix=".db"
    )
    os.close(fd)
    os.remove(db_path)

    import db

    old_path = db.DB
    db.configure(db_path)
    db.init()

    try:
        yield db
    finally:
        db.close_connection()
        db.configure(old_path)

        for path in (
            db_path,
            db_path + "-wal",
            db_path + "-shm",
        ):
            if os.path.exists(path):
                os.remove(path)

@pytest.fixture
def sample_scene():
    """Return a scene with several rooms and characters."""
    return {
        "location": "Old Manor",
        "time": "evening",
        "rooms": {
            "kitchen": {
                "name": "Kitchen",
                "desc": "A rustic kitchen with a heavy oak table.",
                "notes": "Smell of fresh bread. Warm fireplace.",
                "adjacent": [
                    {
                        "to": "hallway",
                        "barrier": "open",
                        "distance": "near",
                    },
                    {
                        "to": "cellar",
                        "barrier": "closed_door",
                        "distance": "near",
                    },
                ],
            },
            "hallway": {
                "name": "Hallway",
                "desc": "A long, dim hallway.",
                "notes": "Cold draft. Dusty portraits.",
                "adjacent": [
                    {
                        "to": "kitchen",
                        "barrier": "open",
                        "distance": "near",
                    },
                    {
                        "to": "study",
                        "barrier": "closed_door",
                        "distance": "near",
                    },
                ],
            },
            "study": {
                "name": "Study",
                "desc": "A cluttered study filled with books.",
                "notes": "Smell of old paper. Flickering candle.",
                "adjacent": [
                    {
                        "to": "hallway",
                        "barrier": "closed_door",
                        "distance": "near",
                    },
                ],
            },
            "cellar": {
                "name": "Cellar",
                "desc": "A dark, damp cellar.",
                "notes": "Cold and musty. Sound of dripping water.",
                "adjacent": [
                    {
                        "to": "kitchen",
                        "barrier": "closed_door",
                        "distance": "near",
                    },
                ],
            },
            "garden": {
                "name": "Garden",
                "desc": "An overgrown garden.",
                "notes": "Night air. Rustling leaves.",
                "adjacent": [],
            },
        },
        "positions": {
            "Alice": "kitchen",
            "Bob": "hallway",
            "Charlie": "study",
            "Diana": "cellar",
        },
        "entities": {},
        "overlays": {},
        "attire": {},
    }
