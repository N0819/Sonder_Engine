"""Regression tests for draft_promoted_character: generating a character
sheet for a recurring background presence grounded in the chat's actual
events record, rather than a blank generate_character brief."""

from __future__ import annotations

import json
import time

import pytest

import importers
from character_schema import CHARACTER_SCHEMA


def _make_chat(db):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )


def _add_event(db, chat_id, turn, event, dialogue_log=None):
    turn_id = db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, turn, "x", time.time()),
    )
    db.qi(
        "INSERT INTO events(chat_id,turn_id,content) VALUES(?,?,?)",
        (chat_id, turn_id, json.dumps({
            "turn": turn, "summary": "", "event": event,
            "dialogue_log": dialogue_log or [],
        })),
    )
    return turn_id


class TestPromotionEvidence:
    def test_collects_turns_with_dialogue_or_mention(self, temp_db):
        chat_id = _make_chat(temp_db)
        _add_event(temp_db, chat_id, 1, "Crusher checks a readout.")
        _add_event(temp_db, chat_id, 2, "Nothing relevant happens.")
        _add_event(temp_db, chat_id, 3, "Crusher speaks up.", dialogue_log=[
            {"speaker": "Dr. Crusher", "exact_quote": "Hold still.", "tone": "calm"},
        ])

        evidence = importers._promotion_evidence(chat_id, "Dr. Crusher")

        turns = [e["turn"] for e in evidence]
        assert turns == [1, 3]
        assert evidence[1]["quoted_lines"][0]["exact_quote"] == "Hold still."

    def test_unrelated_chat_yields_no_evidence(self, temp_db):
        chat_id = _make_chat(temp_db)
        _add_event(temp_db, chat_id, 1, "Picard stands at the viewscreen.")

        evidence = importers._promotion_evidence(chat_id, "Dr. Crusher")
        assert evidence == []


class TestDraftPromotedCharacter:
    def test_raises_when_no_evidence_exists(self, temp_db):
        chat_id = _make_chat(temp_db)
        with pytest.raises(ValueError):
            importers.draft_promoted_character(chat_id, "Nobody")

    def test_produces_a_normalized_sheet_with_empty_opening(
        self, temp_db, monkeypatch,
    ):
        chat_id = _make_chat(temp_db)
        _add_event(temp_db, chat_id, 5, "Crusher tends to the patient.", dialogue_log=[
            {"speaker": "Dr. Crusher", "exact_quote": "How are you feeling?", "tone": "warm"},
        ])

        def fake_chat_complete(role, system, user, **kwargs):
            return json.dumps({
                "sheet": {
                    "identity": {"name": "Dr. Crusher"},
                    "opening": {"first_message": "Hello, I'm Dr. Crusher!"},
                },
                "memory_seeds": ["Asked a patient how they were feeling.", "  ", ""],
            })

        monkeypatch.setattr(importers, "chat_complete", fake_chat_complete)

        draft = importers.draft_promoted_character(chat_id, "Dr. Crusher")

        assert draft["sheet"]["identity"]["name"] == "Dr. Crusher"
        # Forced empty regardless of what the model produced -- she's
        # already mid-scene, not meeting the player for the first time.
        assert draft["sheet"]["opening"]["first_message"] == ""
        assert draft["memory_seeds"] == ["Asked a patient how they were feeling."]
        assert draft["evidence_turns"] == [5]

    def test_raises_clearly_when_model_returns_no_sheet(self, temp_db, monkeypatch):
        chat_id = _make_chat(temp_db)
        _add_event(temp_db, chat_id, 1, "Crusher is present.", dialogue_log=[
            {"speaker": "Dr. Crusher", "exact_quote": "Yes.", "tone": ""},
        ])

        monkeypatch.setattr(
            importers, "chat_complete", lambda *a, **k: "not json at all",
        )

        with pytest.raises(RuntimeError):
            importers.draft_promoted_character(chat_id, "Dr. Crusher")
