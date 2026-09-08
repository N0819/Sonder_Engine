"""A quick start that failed is shown as a setup, with a way out of it.

Owner ruling, 2026-09-08: "maybe it should have a temporary story library
entry with a discard or retry button instead and have a little error
triangle in it", and "an export debugging log button".

Before it, a failed start deleted its chat, so the author was left with
nothing to act on -- no record of what happened, and no way to retry that did
not mean redoing the modal and paying for the model calls again. The row is
kept and MARKED instead. The marker is what makes it not a story: it has no
turn, the library refuses to open it, and the three things worth doing to it
are all on the row.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from core.db import QUICK_START_FAILURE_KEY, q, qi, wget, wset


ROOT = Path(__file__).resolve().parents[1]
APP_JS = (ROOT / "static/js/app.js").read_text(encoding="utf-8")


def _failed_chat(temp_db, *, error="the location generator returned junk"):
    import time

    cid = qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
             ("The Doctor — Hinami", "", time.time()))
    wset(cid, QUICK_START_FAILURE_KEY, {
        "version": 1, "when": time.time(), "stage": "planning",
        "error": error, "error_type": "ValueError",
        "traceback": "Traceback (most recent call last): ...",
        "plan_kept": True,
        "retry": {"char_id": 58, "persona_id": 10, "greeting_index": 0,
                  "lorebook_id": None, "already_known": True,
                  "language": "en",
                  "lived_location": {"enabled": True, "brief": "the port"}},
        "character_name": "The Doctor", "persona_name": "Hinami",
    })
    return cid


def _client():
    from fastapi.testclient import TestClient

    from web import app as app_module
    from web import guest_access as guest

    guest.reset_host_account()
    client = TestClient(app_module.app)
    client.__enter__()
    assert client.post("/api/auth/setup",
                       json={"username": "host", "password": "pw12345"}).status_code == 200
    return client


def test_the_library_is_told_which_rows_are_failed_setups(temp_db):
    cid = _failed_chat(temp_db)
    client = _client()
    try:
        boot = client.get("/api/bootstrap").json()
    finally:
        client.__exit__(None, None, None)

    entry = boot["failed_setups"][str(cid)]
    assert entry["error_type"] == "ValueError"
    assert entry["character_name"] == "The Doctor"
    assert entry["plan_kept"] is True
    # The chat is still in the list; what changes is how it is READ.
    assert any(c["id"] == cid for c in boot["chats"])


def test_an_ordinary_story_is_not_listed_as_a_failed_setup(temp_db):
    import time
    qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
       ("An ordinary story", "", time.time()))
    client = _client()
    try:
        assert client.get("/api/bootstrap").json()["failed_setups"] == {}
    finally:
        client.__exit__(None, None, None)


def test_the_setup_log_carries_what_the_attempt_recorded(temp_db):
    cid = _failed_chat(temp_db, error="Expecting value: line 1 column 1")
    client = _client()
    try:
        doc = client.get(f"/api/chats/{cid}/setup_log").json()
    finally:
        client.__exit__(None, None, None)

    assert doc["kind"] == "quick_start_failure" and doc["chat_id"] == cid
    assert "Expecting value" in doc["failure"]["error"]
    assert doc["failure"]["traceback"]
    # What was asked for travels with it, so the report is reproducible.
    assert doc["failure"]["retry"]["lived_location"]["brief"] == "the port"
    assert "attempt" in doc


def test_a_story_that_did_not_fail_has_no_setup_log(temp_db):
    import time
    cid = qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
             ("Fine", "", time.time()))
    client = _client()
    try:
        assert client.get(f"/api/chats/{cid}/setup_log").status_code == 404
        assert client.post(f"/api/chats/{cid}/retry_start").status_code == 404
    finally:
        client.__exit__(None, None, None)


def test_a_retry_asks_the_same_question_and_clears_the_failed_row(
        temp_db, monkeypatch):
    cid = _failed_chat(temp_db)
    asked = {}

    def fake_start(char_id, persona_id, greeting_index=0, **kwargs):
        asked.update({"char_id": char_id, "persona_id": persona_id,
                      "greeting_index": greeting_index, **kwargs})
        import time
        new = qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Retried", "", time.time()))
        return new, 1

    from story import greetings
    monkeypatch.setattr(greetings, "start_story", fake_start)

    client = _client()
    try:
        out = client.post(f"/api/chats/{cid}/retry_start")
        assert out.status_code == 200, out.text
    finally:
        client.__exit__(None, None, None)

    assert asked["char_id"] == 58 and asked["persona_id"] == 10
    assert asked["lived_location"] == {"enabled": True, "brief": "the port"}
    # The failed row is gone only once the new story exists.
    assert q("SELECT id FROM chats WHERE id=?", (cid,), one=True) is None
    assert out.json()["chat_id"] != cid


def test_a_retry_that_fails_leaves_the_setup_where_it_was(temp_db, monkeypatch):
    """The author must never be left with nothing again: a retry that fails is
    one failed setup, not none."""
    cid = _failed_chat(temp_db)

    def fail(*a, **k):
        raise ValueError("the location generator returned junk again")

    from story import greetings
    monkeypatch.setattr(greetings, "start_story", fail)

    client = _client()
    try:
        out = client.post(f"/api/chats/{cid}/retry_start")
        assert out.status_code == 422, out.text
    finally:
        client.__exit__(None, None, None)

    assert q("SELECT id FROM chats WHERE id=?", (cid,), one=True) is not None
    assert wget(cid, QUICK_START_FAILURE_KEY, None)


def test_the_row_is_rendered_as_a_setup_rather_than_opened():
    """The browser half, pinned at the source the way this repo pins its
    frontend rules: a failed setup takes its own row, and that row does not
    open a chat."""
    assert "failed_setups" in APP_JS
    assert "function failedSetupRow(" in APP_JS
    match = re.search(r"function failedSetupRow\(.*?\n}\n", APP_JS, re.S)
    assert match, "failedSetupRow has no body"
    body = match.group(0)
    # It may open the story a RETRY produces; it may never open itself,
    # because there is no story behind it.
    assert "openChat(chat.id)" not in body, "a failed setup has none to open"
    for needed in ("retry_start", "setup_log", "DELETE", "⚠"):
        assert needed in body, needed
