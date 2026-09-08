"""A revised memory is summarised as the character now reads it
(review 2026-09-07 A86).

`record_dispute` is the engine's whole account of a mind changing its mind: the
event stays exactly as it was -- "I saw this" is still true, and `content`,
`gist`, `provenance` and `salience` are untouched -- and what is recorded beside
it is that the character no longer reads it the way they first did. That is
what deception, disguise, staging and plain misidentification do to a mind.

The consolidator never saw it. `disputed` is on `_row_memory` and was not in
the payload, so a window was summarised from the reading the character had
already abandoned -- and the summary is what they carry forward once the
individual rows age out. The correction therefore un-happened: the mind
un-learned what it had worked out, with nothing left to correct against.

The rule that now holds: every row the consolidator is shown carries
`now_reads` when the character has re-read it. Absent, not empty, on a row
nobody has re-read.

NOT CLOSED BY THIS ALONE. The consolidator's own card has no sentence telling
it what `now_reads` is or which reading to summarise from; prompt text is the
owner's. This pins the payload half.
"""

from __future__ import annotations

import json
import time

import pytest

from mind import memory
from mind.memory import consolidate_character_memory, record_dispute
from tests.helpers import patch_provider_seam


@pytest.fixture
def seen(monkeypatch):
    """The payload the consolidator is handed, captured."""
    calls = []

    def fake(role, prompt, payload, **kw):
        calls.append(json.loads(payload))
        return json.dumps({
            "summary": "s", "hearsay_summary": "", "surmise_summary": "",
            "key_phrases": [], "unresolved_threads": [], "stable_facts": [],
        })

    patch_provider_seam(monkeypatch, "chat_complete", fake)
    patch_provider_seam(monkeypatch, "embed_texts_meta", lambda texts, **k: type(
        "E", (), {"vectors": [[0.0] * 8 for _ in texts],
                  "model_key": "stub", "dimensions": 8, "fallback": False})())
    return calls


def _chat_and_char(db):
    chat_id = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                    ("T", "", time.time()))
    char_id = db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        ("Mara", "{}", "{}", time.time()))
    return chat_id, char_id


def _mem(db, chat_id, char_id, turn_idx, content):
    return db.qi(
        "INSERT INTO memories(chat_id,char_id,turn_idx,kind,category,"
        "provenance,salience,content,gist) "
        "VALUES(?,?,?,'episodic','episode','witnessed',0.8,?,?)",
        (chat_id, char_id, turn_idx, content, content))


def test_a_re_read_memory_reaches_the_consolidator_with_its_new_reading(
        temp_db, seen):
    chat_id, char_id = _chat_and_char(temp_db)
    _mem(temp_db, chat_id, char_id, 1, "the steward gave her the key")
    _mem(temp_db, chat_id, char_id, 2, "she crossed the yard")
    assert record_dispute(
        chat_id, char_id, "the steward gave her the key",
        "it was not the steward -- someone wearing his coat", turn_idx=3)

    consolidate_character_memory(chat_id, char_id, through_turn_idx=3)

    rows = seen[0]["memories_chronological"]
    revised = [r for r in rows if "steward" in r["details"]]
    assert revised and revised[0]["now_reads"] == (
        "it was not the steward -- someone wearing his coat")
    # The event itself is untouched: this is an addendum, never an overwrite.
    assert revised[0]["details"] == "the steward gave her the key"


def test_a_memory_nobody_has_re_read_carries_no_such_key(temp_db, seen):
    """Absent rather than empty -- a key that is blank on every row teaches
    the reader to skip it."""
    chat_id, char_id = _chat_and_char(temp_db)
    _mem(temp_db, chat_id, char_id, 1, "she crossed the yard")

    consolidate_character_memory(chat_id, char_id, through_turn_idx=1)

    rows = seen[0]["memories_chronological"]
    assert rows and all("now_reads" not in r for r in rows)


def test_every_field_the_consolidator_already_read_is_still_there(temp_db,
                                                                  seen):
    chat_id, char_id = _chat_and_char(temp_db)
    _mem(temp_db, chat_id, char_id, 1, "she crossed the yard")

    consolidate_character_memory(chat_id, char_id, through_turn_idx=1)

    row = seen[0]["memories_chronological"][0]
    assert set(row) == {"id", "turn_idx", "category", "provenance", "salience",
                        "confidence", "gist", "details", "key_phrases",
                        "entities", "location", "emotional_context"}
