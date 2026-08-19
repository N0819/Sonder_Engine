"""Regression tests for draft_promoted_character: generating a character
sheet for a recurring background presence grounded in the chat's actual
events record, rather than a blank generate_character brief."""

from __future__ import annotations

import json
import time

import pytest

from story import importers
from story.character_schema import CHARACTER_SCHEMA


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

    def test_the_name_is_not_the_models_to_choose(self, temp_db, monkeypatch):
        """The bug this exists for: the evidence pack is the whole beat, so it
        is full of OTHER people's names -- the PLAYER's most of all. Two
        different market extras in one story were both minted carrying the
        player persona's name, which in an engine that keys minds by name is an
        identity collision, not a typo."""
        chat_id = _make_chat(temp_db)
        _add_event(temp_db, chat_id, 5,
                   "Hinami steps under the awning. The spice seller nods at her.",
                   dialogue_log=[{"speaker": "The Spice Seller",
                                  "exact_quote": "Rain's set in.", "tone": "dry"}])

        def fake_chat_complete(role, system, user, **kwargs):
            return json.dumps({
                "sheet": {"identity": {"name": "Hinami",
                                       "uid": "spice_seller_hinami"},
                          "opening": {"first_message": ""}},
                "memory_seeds": [],
            })

        monkeypatch.setattr(importers, "chat_complete", fake_chat_complete)

        draft = importers.draft_promoted_character(chat_id, "The Spice Seller")
        assert draft["sheet"]["identity"]["name"] == "The Spice Seller"

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


# --- the warnings are about a CARD, not about an import --------------------
#
# `character_import_warnings` ran on exactly one of the nine surfaces that
# create or edit a character card: the import route. Every other way a sheet
# comes into being -- the blank-card route, the editor's save, the generator,
# the psychology fill, a promotion from a background presence -- produced a
# sheet nobody checked. The blank-card route produces, BY CONSTRUCTION, the
# sheet the first three warnings exist to catch: `default_character_data`
# ships `{"essence": "", "expression": "", "taboo": ""}`, no goals and an
# empty capacity, and says nothing.
#
# CLAUDE.md names that shape as the worst failure mode in the engine: it
# reads as complete, never errors, and surfaces fifty beats later as a
# character who stopped wanting things. The check is a property of a sheet
# and always was; only its name and its home said "import".

class TestCardWarningsAreASheetProperty:
    def test_the_check_is_reachable_from_the_module_that_owns_the_card(self):
        """A validator named for one route is a validator nine other
        surfaces will not find. It lives with the format it validates."""
        from story.character_schema import character_card_warnings
        assert callable(character_card_warnings)

    def test_the_import_name_still_answers(self):
        """The import route is a caller, not the owner; it keeps working."""
        from story import importers
        from story.character_schema import character_card_warnings
        assert importers.character_import_warnings is character_card_warnings

    def test_the_blank_card_route_is_told_what_it_just_made(self):
        from story.character_schema import (character_card_warnings,
                                            default_character_data)
        warnings = character_card_warnings(default_character_data("Tamamo"))
        assert any("drive" in w for w in warnings)
        assert any("goals" in w for w in warnings)
        assert any("capacity" in w for w in warnings)

    def test_an_authored_card_says_nothing(self):
        from story.character_schema import (character_card_warnings,
                                            normalize_character_data)
        sheet = normalize_character_data({
            "identity": {"name": "Tamamo"},
            "psychology": {
                "drive": {"essence": "to be seen as she truly is",
                          "expression": "tests whether a kindness is real",
                          "taboo": "being pitied"},
                "capacity": "focused",
            },
            "initial_state": {"goals": [{"text": "reach the shrine"}]},
        })
        assert character_card_warnings(sheet) == []


class TestAPromotedCharacterIsCheckedToo:
    """A promotion mints a real character from a background presence, from a
    model-written sheet, and hands it to a review screen -- which is the one
    moment an author can still fix an empty drive. The draft carried its
    evidence and its memory seeds and no word about what the sheet was
    missing."""

    def test_the_draft_carries_its_own_warnings(self, temp_db, monkeypatch):
        chat_id = _make_chat(temp_db)
        _add_event(temp_db, chat_id, 5, "Crusher tends to the patient.")

        def fake_chat_complete(role, system, user, **kwargs):
            return json.dumps({"sheet": {"identity": {"name": "Dr. Crusher"}}})

        monkeypatch.setattr(importers, "chat_complete", fake_chat_complete)
        draft = importers.draft_promoted_character(chat_id, "Dr. Crusher")

        assert any("drive" in w for w in draft["warnings"])

    def test_a_complete_draft_warns_about_nothing(self, temp_db, monkeypatch):
        chat_id = _make_chat(temp_db)
        _add_event(temp_db, chat_id, 5, "Crusher tends to the patient.")

        def fake_chat_complete(role, system, user, **kwargs):
            return json.dumps({"sheet": {
                "identity": {"name": "Dr. Crusher"},
                "psychology": {
                    "drive": {"essence": "nobody dies on her watch",
                              "expression": "puts herself between them and it",
                              "taboo": "being ordered to stand down"},
                    "capacity": "broad",
                },
                "initial_state": {"goals": [{"text": "stabilise the patient"}]},
            }})

        monkeypatch.setattr(importers, "chat_complete", fake_chat_complete)
        draft = importers.draft_promoted_character(chat_id, "Dr. Crusher")

        assert draft["warnings"] == []
