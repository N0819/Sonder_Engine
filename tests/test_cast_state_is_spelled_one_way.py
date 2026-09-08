"""A cast row's committed state has one spelling, and it is `cstate`.

Review 2026-09-07 finding A43. `story.scene.active_cast` projects
`chat_chars.state` (or the frame override) under the column name **cstate**;
`state` is a column no cast row carries. `loops._standing_pressure` read
`row["state"]`, `sqlite3.Row` raised `IndexError`, its own except returned
0.0 for every character, and the opening speaker of every untargeted beat in
every live story was therefore decided by the jitter alone -- the ranking the
function exists to provide never once applied.

It was invisible because the unit fixtures beside it were plain dicts carrying
`state`, so the test and the defect agreed. These tests use a real
`sqlite3.Row` from `active_cast`'s own projection, which is the only shape
that could have caught it.
"""

from __future__ import annotations

import json
import sqlite3

import agents.loops as loops
from story.character_schema import default_character_data
from story.scene import cast_state


def _row(cid, state_json):
    """A cast row shaped exactly as `story.scene.active_cast` returns one."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE c(id INTEGER, name TEXT, sheet TEXT, "
                 "source TEXT, created TEXT, resource_uid TEXT, "
                 "cstate TEXT, status TEXT)")
    conn.execute(
        "INSERT INTO c VALUES(?,?,?,?,?,?,?,?)",
        (cid, f"Char{cid}",
         json.dumps(default_character_data(f"Char{cid}")),
         "test", "", "", state_json, "active"))
    return conn.execute("SELECT * FROM c").fetchone()


class _Chat:
    id = 1


class _Turn:
    idx = 5
    frame_id = None


class _Ctx:
    def __init__(self, cast):
        self.chat = _Chat()
        self.turn = _Turn()
        self.cast = cast


def _wants(urgency):
    return json.dumps({"active_state": {"wants": [
        {"want": "say the thing", "urgency": urgency}]}})


def test_standing_pressure_reads_a_real_cast_row():
    """The defect, on the projection the engine actually produces."""
    ctx = _Ctx([_row(1, _wants(0.2)), _row(2, _wants(0.9))])

    assert loops._standing_pressure(ctx, 2) == 0.9
    assert loops._standing_pressure(ctx, 1) == 0.2


def test_an_uncommitted_mind_has_no_standing_pressure():
    """Missing state is 0, not an error -- a mind that has never been
    committed carries no standing wants, which is the true answer."""
    ctx = _Ctx([_row(1, None), _row(2, "{}")])

    assert loops._standing_pressure(ctx, 1) == 0.0
    assert loops._standing_pressure(ctx, 2) == 0.0


def test_cast_state_answers_nothing_for_a_row_with_no_such_column():
    """A row that is not a cast row is not an error either: the caller asked
    what this mind is carrying, and nothing carries it."""
    assert cast_state({"id": 1, "sheet": "{}"}) == {}
    assert cast_state({"cstate": "not json"}) == {}
    assert cast_state({"cstate": '"a string, not a dict"'}) == {}
    assert cast_state({"cstate": _wants(0.4)})["active_state"]["wants"]
