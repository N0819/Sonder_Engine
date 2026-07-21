"""Regression tests for audit finding #24: importers.py.

- Card macros {{char}}/<BOT> and {{user}}/<USER> must be resolved at import,
  or a literal "{{user}}" renders verbatim to the player.
- character-card-spec-v2 `character_book` entries with `enabled: false` must
  NOT be imported as active lore.
"""

from __future__ import annotations

import pytest

import importers
from db import q


@pytest.fixture(autouse=True)
def _no_ai(monkeypatch):
    # None of these paths should touch a provider; make it loud if they do.
    def fail(*a, **k):
        raise AssertionError("AI must not be called for heuristic imports")
    monkeypatch.setattr(importers, "chat_complete", fail)
    yield


class TestCharacterMacroSubstitution:
    def test_curly_macros_are_resolved_in_the_greeting(self, temp_db):
        payload = {
            "name": "Aria",
            "description": "{{char}} greets everyone warmly.",
            "first_mes": "Hello {{user}}, I am {{char}}. Welcome.",
        }
        _cid, sheet = importers.import_character(payload, reinterpret=False)

        greeting = sheet["opening"]["first_message"]
        assert "{{user}}" not in greeting
        assert "{{char}}" not in greeting
        assert "Aria" in greeting
        assert importers.PLAYER_TOKEN in greeting

        summary = sheet["embodiment"]["visible"]["summary"]
        assert "{{char}}" not in summary
        assert "Aria" in summary

    def test_angle_bracket_macros_are_resolved(self, temp_db):
        payload = {
            "name": "Kai",
            "first_mes": "<BOT> nods at <USER>.",
        }
        _cid, sheet = importers.import_character(payload, reinterpret=False)
        greeting = sheet["opening"]["first_message"]
        assert "<BOT>" not in greeting and "<USER>" not in greeting
        assert "Kai" in greeting
        assert importers.PLAYER_TOKEN in greeting

    def test_whitespace_inside_macro_braces_is_tolerated(self, temp_db):
        payload = {"name": "Nyx", "first_mes": "{{ user }} meets {{ char }}."}
        _cid, sheet = importers.import_character(payload, reinterpret=False)
        greeting = sheet["opening"]["first_message"]
        assert "user" not in greeting.lower().replace("welcome", "")
        assert "Nyx" in greeting
        assert importers.PLAYER_TOKEN in greeting


class TestPersonaMacroSubstitution:
    def test_user_macro_is_normalized_in_persona(self, temp_db):
        payload = {"name": "Rin", "description": "A traveler {{user}} once met."}
        _pid, sheet = importers.import_persona(payload, reinterpret=False)
        summary = sheet["embodiment"]["visible"]["summary"]
        assert "{{user}}" not in summary
        assert importers.PLAYER_TOKEN in summary


class TestDisabledLorebookEntriesSkipped:
    def test_card_book_enabled_false_entry_is_not_imported(self, temp_db):
        book = {
            "entries": [
                {"keys": ["alpha"], "content": "Alpha fact.", "enabled": True},
                {"keys": ["beta"], "content": "Beta fact.", "enabled": False},
            ]
        }
        lb, count = importers.import_lorebook(book, name="Card book")
        assert count == 1

        rows = q("SELECT content FROM lore_entries WHERE lorebook_id=?", (lb,))
        contents = [r["content"] for r in rows]
        assert any("Alpha" in c for c in contents)
        assert not any("Beta" in c for c in contents)

    def test_world_info_disable_flag_still_skipped(self, temp_db):
        book = {
            "entries": [
                {"keys": ["a"], "content": "Kept.", "disable": False},
                {"keys": ["b"], "content": "Dropped.", "disable": True},
            ]
        }
        lb, count = importers.import_lorebook(book, name="WI book")
        assert count == 1
        rows = q("SELECT content FROM lore_entries WHERE lorebook_id=?", (lb,))
        assert not any("Dropped" in r["content"] for r in rows)

    def test_character_book_macros_are_substituted(self, temp_db):
        payload = {
            "name": "Mira",
            "first_mes": "Hi.",
            "character_book": {
                "entries": [
                    {"keys": ["home"], "content": "{{char}} lives near {{user}}."},
                ]
            },
        }
        importers.import_character(payload, reinterpret=False)
        rows = q(
            "SELECT content FROM lore_entries WHERE content LIKE '%lives near%'"
        )
        assert rows, "character_book entry was not imported"
        content = rows[0]["content"]
        assert "{{char}}" not in content and "{{user}}" not in content
        assert "Mira" in content
        assert importers.PLAYER_TOKEN in content
