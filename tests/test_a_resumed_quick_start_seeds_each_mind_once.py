"""A retried quick start does not seed the same minds a second time.

`start_story` resumes a failed launch on the same chat, and its own comment
says every stage "asks the CHAT whether its own work is already there". The
minds stage did not: a start that failed after it -- turn 0, the journey
history, the featured-resident handoff, the chat-128 case -- re-ran
`_seed_minds` on retry, appending every interior belief again, writing every
relationship-ledger row again, and growing `persona_private_history`; and
since the extraction itself is re-asked on resume, the memory upsert key only
dedupes byte-identical seeds (story_attire_import audit F5; the lane brief's
F5).

The stage now asks the chat: a `greeting_minds` record already written means
the minds were routed, and a resume goes on after them.
"""

from __future__ import annotations

import json

import pytest

from story import importers


@pytest.fixture(autouse=True)
def _no_ai(monkeypatch):
    def fail(*a, **k):
        raise AssertionError("AI must not be called for heuristic imports")
    monkeypatch.setattr(importers, "chat_complete", fail)
    yield


EXTRACTION = {"time": "now", "knowledge_seeds": [], "minds": [
    {"who": "Dr. Moon",
     "knowledge_seeds": [{"content": "I saw {{PLAYER}} at the gate.",
                          "revealed_in_prose": True}],
     "beliefs": [{"belief": "The east lock is broken.", "confidence": 0.6}],
     "stances": [{"toward": "{{PLAYER}}", "trust": 0.4, "warmth": 0.2,
                  "because": "came when called"}],
     "affect": None},
    {"who": "{{PLAYER}}",
     "knowledge_seeds": [{"content": "I crossed the pass after dark.",
                          "revealed_in_prose": True}],
     "beliefs": [], "stances": [], "affect": None},
]}


def _counts(temp_db, chat_id, char_id):
    from core.db import wget
    row = temp_db.q("SELECT state FROM chat_chars WHERE chat_id=? AND "
                    "char_id=?", (chat_id, char_id), one=True)
    state = json.loads(row["state"] or "{}")
    beliefs = (state.get("interior") or {}).get("beliefs") or []
    ledger = temp_db.q("SELECT id FROM relationship_events WHERE chat_id=?",
                       (chat_id,))
    persona = wget(chat_id, "persona_private_history", None) or []
    return len(beliefs), len(ledger), len(persona)


def test_a_retry_after_a_late_failure_seeds_nothing_twice(temp_db,
                                                         monkeypatch):
    from story import greetings
    monkeypatch.setattr(greetings, "extract_greeting",
                        lambda sheet, prose: json.loads(json.dumps(EXTRACTION)))
    char_id, _ = importers.import_character(
        {"name": "Dr. Moon", "first_mes": "The gate creaks. {{user}} waits."},
        reinterpret=False)
    pid, _ = importers.import_persona({"name": "Dana"}, reinterpret=False)

    def turn_zero_fails(cid, tid):
        raise RuntimeError("establish failed")

    monkeypatch.setattr(greetings, "_run_pipeline", turn_zero_fails)
    with pytest.raises(RuntimeError):
        greetings.start_story(char_id, pid, greeting_index=0)
    chat_id = temp_db.q("SELECT id FROM chats ORDER BY id DESC LIMIT 1",
                        one=True)["id"]
    first = _counts(temp_db, chat_id, char_id)
    assert first[0] == 1 and first[1] >= 1 and first[2] >= 1

    monkeypatch.setattr(greetings, "_run_pipeline", lambda cid, tid: iter(()))
    resumed, _tid = greetings.start_story(char_id, pid, greeting_index=0,
                                         resume_chat_id=chat_id)
    assert resumed == chat_id
    assert _counts(temp_db, chat_id, char_id) == first
