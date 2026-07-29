"""Consolidation must not melt provenance into one string (audit P8).

heard/told/read/inferred rows used to fold into a single autobiographical
summary that was then fed back wholesale every turn, so the distinction the
engine's thesis rests on -- what a character SAW vs was TOLD vs GUESSED -- did
not survive the summary layer. A few turns later an inference came back
indistinguishable from an observation: belief laundering into knowledge inside
a single mind.

Three summary rows rather than a tag inside the prose, because the prose is
written by a model and a convention it can drop is not a boundary. Rides
`memory_summaries.scope`, which already round-trips through checkpoint,
archive, and branch -- no migration.
"""

from __future__ import annotations

import json
import time

import pytest

import memory
from memory import (
    SUMMARY_SCOPE_FIRSTHAND,
    SUMMARY_SCOPE_HEARSAY,
    SUMMARY_SCOPE_SURMISE,
    build_character_memory_context,
    consolidate_character_memory,
    get_memory_summary,
    summary_scope_for,
)


def test_every_provenance_maps_to_a_scope():
    """A provenance with no mapping would silently fold into first-hand, which
    is the failure this exists to prevent."""
    for prov in memory.MEMORY_PROVENANCE:
        assert summary_scope_for(prov) in (
            SUMMARY_SCOPE_FIRSTHAND, SUMMARY_SCOPE_HEARSAY, SUMMARY_SCOPE_SURMISE)
    assert summary_scope_for("witnessed") == SUMMARY_SCOPE_FIRSTHAND
    assert summary_scope_for("remembered") == SUMMARY_SCOPE_FIRSTHAND
    assert summary_scope_for("told") == SUMMARY_SCOPE_HEARSAY
    assert summary_scope_for("read") == SUMMARY_SCOPE_HEARSAY
    assert summary_scope_for("inferred") == SUMMARY_SCOPE_SURMISE


def _chat_and_char(db):
    chat_id = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                    ("T", "", time.time()))
    char_id = db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        ("Mara", "{}", "{}", time.time()))
    return chat_id, char_id


def _mem(db, chat_id, char_id, turn_idx, provenance, content):
    return db.qi(
        "INSERT INTO memories(chat_id,char_id,turn_idx,kind,category,provenance,"
        "salience,content,gist) VALUES(?,?,?,'episodic','episode',?,0.8,?,?)",
        (chat_id, char_id, turn_idx, provenance, content, content))


@pytest.fixture
def _stub_consolidator(monkeypatch):
    """The consolidator is one LLM call; its OUTPUT contract is what is under
    test, not the model."""
    def fake(role, prompt, payload, **kw):
        return json.dumps({
            "summary": "She crossed the yard and opened the gate.",
            "hearsay_summary": "Bo told her the well was poisoned.",
            "surmise_summary": "She concluded the steward is lying.",
            "key_phrases": ["gate"], "unresolved_threads": ["who poisoned it"],
            "stable_facts": [],
        })
    monkeypatch.setattr(memory, "chat_complete", fake)
    monkeypatch.setattr(memory, "embed_texts_meta", lambda texts, **k: type(
        "E", (), {"vectors": [[0.0] * 8 for _ in texts],
                  "model_key": "stub", "dimensions": 8})())


def test_each_class_lands_in_its_own_row(temp_db, _stub_consolidator):
    chat_id, char_id = _chat_and_char(temp_db)
    _mem(temp_db, chat_id, char_id, 1, "witnessed", "crossed the yard")
    _mem(temp_db, chat_id, char_id, 2, "told", "the well is poisoned")
    _mem(temp_db, chat_id, char_id, 3, "inferred", "the steward is lying")

    consolidate_character_memory(chat_id, char_id, through_turn_idx=3)

    first = get_memory_summary(chat_id, char_id, SUMMARY_SCOPE_FIRSTHAND)
    hearsay = get_memory_summary(chat_id, char_id, SUMMARY_SCOPE_HEARSAY)
    surmise = get_memory_summary(chat_id, char_id, SUMMARY_SCOPE_SURMISE)
    assert "gate" in first["summary"]
    assert "Bo told her" in hearsay["summary"]
    assert "concluded" in surmise["summary"]
    # ...and the classes did not bleed into each other.
    assert "poisoned" not in first["summary"]
    assert "steward" not in first["summary"]


def test_the_character_context_keeps_them_apart(temp_db, _stub_consolidator):
    chat_id, char_id = _chat_and_char(temp_db)
    _mem(temp_db, chat_id, char_id, 1, "witnessed", "crossed the yard")
    _mem(temp_db, chat_id, char_id, 2, "told", "the well is poisoned")
    _mem(temp_db, chat_id, char_id, 3, "inferred", "the steward is lying")
    consolidate_character_memory(chat_id, char_id, through_turn_idx=3)

    ctx = build_character_memory_context(
        chat_id, char_id, current_turn_idx=9, current_view="a yard",
        active_state={"goal": "", "mood": ""})
    assert "poisoned" not in ctx["autobiographical_summary"]
    assert "Bo told her" in ctx["what_i_was_told"]
    assert "concluded" in ctx["what_i_concluded"]


def test_the_cursor_row_is_written_even_with_nothing_firsthand(temp_db,
                                                              _stub_consolidator):
    """maybe_consolidate_character_memory reads the first-hand row's
    end_turn_idx as its cursor. Skip that row on a hearsay-only window and the
    same memories re-consolidate forever."""
    chat_id, char_id = _chat_and_char(temp_db)
    _mem(temp_db, chat_id, char_id, 4, "told", "the well is poisoned")
    consolidate_character_memory(chat_id, char_id, through_turn_idx=4)
    assert get_memory_summary(
        chat_id, char_id, SUMMARY_SCOPE_FIRSTHAND)["end_turn_idx"] == 4


def test_scoped_rows_round_trip_through_a_dump(temp_db, _stub_consolidator):
    """The reason this needed no migration: dump/restore iterate rows and carry
    `scope` verbatim, so extra scopes travel through checkpoint, archive and
    branch with no per-seam work."""
    chat_id, char_id = _chat_and_char(temp_db)
    _mem(temp_db, chat_id, char_id, 1, "witnessed", "crossed the yard")
    _mem(temp_db, chat_id, char_id, 2, "inferred", "the steward is lying")
    consolidate_character_memory(chat_id, char_id, through_turn_idx=2)
    dumped = memory.dump_memory_summaries(chat_id)
    assert {d["scope"] for d in dumped} >= {
        SUMMARY_SCOPE_FIRSTHAND, SUMMARY_SCOPE_SURMISE}
