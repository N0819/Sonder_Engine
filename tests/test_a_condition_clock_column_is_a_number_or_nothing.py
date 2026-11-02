"""A condition's clock columns hold a number of seconds or nothing.

`commit_world_entities` stored the encoder's `expires_at_seconds` exactly as
written, and the schema types condition items as untyped dicts. SQLite's REAL
affinity keeps a non-numeric string as TEXT, so a model writing
`"expires_at_seconds": ""` (or a word) left a row the NEXT beat's transit
sweep -- the first domain inside the transaction -- could not compare:
`float("")` raised, `commit_all` rolled the beat back, and every later beat
after it, because the row was still there (review 2026-11-01,
world_offscreen_time F2; 0 of 538 live rows are non-numeric today). The
sweep's own guard is another lane's; the writer stores a number or NULL and
says what it dropped.
"""

from __future__ import annotations

import time

import pytest

from core.db import q
from core.pipeline_context import ChatData, PipelineContext, TurnData
from persist.commit import commit_world_entities


def _ctx(temp_db):
    cid = temp_db.qi("INSERT INTO chats(name,created) VALUES('t',0.0)")
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, 2, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="t", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=cid, idx=2, player_input="",
                      created=time.time()),
        cast=[], input="")
    ctx.director_resolve = {"resolved_event": "", "dialogue_log": [],
                            "state_diff": {}}
    return ctx


def _commit(ctx, **clock):
    commit_world_entities(ctx, 0, prepared={"diff": {"conditions": {
        "c1": [{"subject_id": "Mara", "kind": "injury",
                "state": {"what": "a cut palm"}, **clock}]}}})
    return q(
        "SELECT started_at, expires_at, typeof(expires_at) AS t "
        "FROM world_conditions WHERE chat_id=? AND condition_id='c1'",
        (ctx.chat.id,), one=True)


@pytest.mark.parametrize("value", ["", "soon", "dawn", "  "])
def test_a_word_is_stored_as_no_expiry(temp_db, value):
    ctx = _ctx(temp_db)
    row = _commit(ctx, expires_at_seconds=value)
    assert row["expires_at"] is None, row["t"]


def test_a_dropped_word_is_said(temp_db):
    ctx = _ctx(temp_db)
    _commit(ctx, expires_at_seconds="soon")
    assert any("expires_at_seconds" in w and "soon" in w
               for w in ctx.warnings)


def test_a_number_written_as_text_is_the_number(temp_db):
    ctx = _ctx(temp_db)
    row = _commit(ctx, expires_at_seconds="3600")
    assert row["expires_at"] == 3600.0 and row["t"] == "real"


def test_an_unreadable_start_falls_back_to_the_default(temp_db):
    ctx = _ctx(temp_db)
    row = _commit(ctx, started_at_seconds="earlier", expires_at_seconds=90)
    assert row["started_at"] == 0.0
    assert row["expires_at"] == 90.0


def test_a_re_emission_with_a_word_keeps_the_rows_own_expiry(temp_db):
    """The UPDATE branch COALESCEs: no authored expiry keeps the row's own.
    A word is no authored expiry."""
    ctx = _ctx(temp_db)
    _commit(ctx, expires_at_seconds=7200)
    row = _commit(ctx, expires_at_seconds="later")
    assert row["expires_at"] == 7200.0
