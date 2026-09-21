"""The snapshot the charter's movement is measured against belongs to a frame.

`charters` is frame-scoped, so two frames hold two institutions running two
histories. `charter_last_places` -- the "where every charter body stood last
beat" snapshot that `charter_runtime.charter_moves_since` diffs against to
produce the Director's author notes -- was NOT, and the call site said it was:
`agents/mapping.py` asks through `wget_for_frame(cid, "charter_last_places",
frame_id, {})`, which is a no-op for a key the scoping table does not name.

Measured (Aldermill, two causality bubbles, 2026-09-19, 60 beats): the world
table held `charters<RS>fr1` and `charters<RS>fr2` and exactly one unscoped
`charter_last_places`, and the two frames' forty-body place maps came back
byte-identical on every beat of the run -- each bubble's "what moved since
last beat" was a delta against the OTHER bubble's last beat.

This is the four-places rule's own failure mode (`declared-everywhere-still-
unroutable`): the key was declared frame-scoped at the call site and never
registered in the table that decides.
"""

import time

import core.db as db
from core.frames import create_frame


def test_two_frames_keep_their_own_charter_snapshot(temp_db):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("frames", "", time.time()))
    a = create_frame(cid, label="home", ordinal=0, kind="spatial",
                     split_turn_idx=0)
    b = create_frame(cid, label="away", ordinal=0, kind="spatial",
                     split_turn_idx=1)

    db.wset_for_frame(cid, "charter_last_places",
                      {"places": {"smith": "forge"}, "acts": []}, a)
    db.wset_for_frame(cid, "charter_last_places",
                      {"places": {"smith": "market"}, "acts": []}, b)

    assert db.wget_for_frame(cid, "charter_last_places", a, {}) \
        == {"places": {"smith": "forge"}, "acts": []}
    assert db.wget_for_frame(cid, "charter_last_places", b, {}) \
        == {"places": {"smith": "market"}, "acts": []}, (
            "the away frame's snapshot must not be the home frame's, or every "
            "bubble's charter_moves is a delta against another bubble's beat")

    stored = {row["key"] for row in db.q(
        "SELECT key FROM world WHERE chat_id=?", (cid,))}
    assert f"charter_last_places{db._FRAME_KEY_SEP}{a}" in stored
    assert f"charter_last_places{db._FRAME_KEY_SEP}{b}" in stored


def test_the_key_is_registered_where_the_scoping_is_decided():
    """A `wget_for_frame` call is a request, not the decision. The decision is
    this table, and a key missing from it is silently unscoped."""
    assert "charter_last_places" in db.FRAME_SCOPED_WORLD_KEYS
