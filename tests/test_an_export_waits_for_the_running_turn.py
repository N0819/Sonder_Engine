"""A chat export waits for a running beat, as `_require_chat_idle` says it does.

`_require_chat_idle`'s docstring has listed "export/import" among its callers,
and the export took no guard at all: `export_chat` is about fifteen separate
autocommit reads -- turns, then each turn's steps and variants, then the
world -- so an export taken while a beat commits (off-screen beats run
unprompted) could pair the world after turn N with a turn N that has no
narrator or commit step yet, and an import reproduced the torn story (audit
2026-11-01, web_app F8). It is refused with the same 409 every other
whole-chat operation gives while a beat runs. Import makes a new chat, which
no run can be writing, and stays unguarded.
"""
from __future__ import annotations

import threading
import time

import pytest
from fastapi import HTTPException


def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Story", "", time.time()))


def _route_endpoint():
    from web import app as app_module
    for route in app_module.app.routes:
        if getattr(route, "name", "") == "chat_export":
            return route.endpoint
    raise AssertionError("no chat_export route")


@pytest.mark.parametrize("call", ["route", "alias"])
def test_an_export_under_a_running_beat_is_refused(temp_db, call):
    """The ROUTE, as registered, and `app.chat_export`, the alias the drive
    tools borrow to export "what the route does"."""
    from agents.runtime import ABORTS
    from web import app

    cid = _chat(temp_db)
    export = _route_endpoint() if call == "route" else app.chat_export
    ABORTS[(cid, None)] = threading.Event()
    try:
        with pytest.raises(HTTPException) as refused:
            export(cid)
    finally:
        ABORTS.pop((cid, None), None)
    assert refused.value.status_code == 409


def test_an_idle_story_still_exports(temp_db):
    from web import app

    cid = _chat(temp_db)
    assert _route_endpoint()(cid)["chat"]["id"] == cid
