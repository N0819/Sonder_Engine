"""`story_view`'s living-world slice reads the charter registry through the
shared, cached parse rather than re-reading and re-parsing the row on every
call -- and never hands a caller the shared object itself.

Audit 2026-11-01 (web_routes_extensions F24 and Efficiency 2): the slice ran
`wget_for_frame` + `normalize_registry` on every call, on a comment that
predated the cache ("`registry_for` would re-read and re-parse"). Measured:
76 ms per call on chat 175's 0.9 MB registry; core/db.py's own note measured
0.95-2.3 s per parse for a 41.4 MB generated town; campaign-demo's
`/campaign` route builds a whole `story_view` for one field.
"""

from __future__ import annotations

import time

from core import db
from web.story_view import story_view


def _chat_with_a_registry(temp_db):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Town", "", time.time()))
    temp_db.wset(cid, "charters", {"version": 1, "items": {"watch": {
        "state": {"key": "watch", "bodies": {}, "posts": {}}}}})
    return cid


def test_a_second_read_does_not_reparse_an_unchanged_registry(
        temp_db, monkeypatch):
    cid = _chat_with_a_registry(temp_db)
    first = story_view(cid)["living_world"]["charters"]
    assert [row["key"] for row in first] == ["watch"]

    reads = []
    real = db.wget

    def counting(chat_id, key, d=None):
        if str(key).startswith("charters"):
            reads.append(key)
        return real(chat_id, key, d)

    monkeypatch.setattr(db, "wget", counting)
    second = story_view(cid)["living_world"]["charters"]

    assert second == first
    assert reads == []


def test_the_full_registry_is_the_callers_own_copy(temp_db):
    cid = _chat_with_a_registry(temp_db)
    full = story_view(cid, charters="full")["living_world"]["charters"]
    full["items"].clear()

    again = story_view(cid, charters="full")["living_world"]["charters"]
    assert list(again["items"]) == ["watch"]
