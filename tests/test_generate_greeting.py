"""Tests for greeting generation (feature: generate opening greetings).

A greeting is the opening message a player sees when starting a story with a
character, shown verbatim. Authors can hand-write, import, or recover greetings;
this generates one in the character's voice from an optional situation brief.

The generated greeting must be a normal `sheet.opening.greetings` entry -- the
same shape as an imported or hand-added one -- and must keep the {{PLAYER}}
token so it stays reusable across personas.
"""

from __future__ import annotations

import json

import pytest

from story import greetings
from story.character_schema import default_character_data


def _make_character(temp_db, name="Mara", voice_register="dry, clipped"):
    sheet = default_character_data(name)
    sheet["social"]["voice"]["register"] = voice_register
    sheet["knowledge"]["public_history"] = "Runs the last open café on the pier."
    return temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (name, json.dumps(sheet), "{}", 0, sheet["identity"]["uid"]))


GREETING = ('The rain hasn\'t let up all night. Mara looks up from the till as '
            'the bell jangles. "We\'re shut, {{PLAYER}} — oh. It\'s you. '
            'Sit down before you fall down."')


def test_generates_a_greeting_entry(temp_db, monkeypatch):
    cid = _make_character(temp_db)
    monkeypatch.setattr(greetings, "get_prompt", lambda k: "SYS")

    captured = {}

    def fake_complete(role, sys, user, **kw):
        captured["role"] = role
        captured["payload"] = json.loads(user)
        return GREETING

    monkeypatch.setattr("llm.providers.chat_complete", fake_complete)

    g = greetings.generate_greeting(cid, brief="she's closing up in a storm")

    # Shape matches a hand-added / imported greeting.
    assert set(g) == {"greeting_id", "prose", "extraction", "extractor_version"}
    assert g["greeting_id"].startswith("greet_")
    assert g["extraction"] is None
    # {{PLAYER}} is preserved for per-play substitution.
    assert "{{PLAYER}}" in g["prose"]
    assert "Sit down before you fall down" in g["prose"]

    # The model saw the character's own voice/history and the brief.
    assert captured["role"] == "utility"
    assert captured["payload"]["character"]["name"] == "Mara"
    assert "storm" in captured["payload"]["situation_brief"]


def test_blank_brief_still_generates(temp_db, monkeypatch):
    cid = _make_character(temp_db)
    monkeypatch.setattr(greetings, "get_prompt", lambda k: "SYS")
    monkeypatch.setattr("llm.providers.chat_complete",
                        lambda *a, **kw: "Mara nods at you across the bar.")
    g = greetings.generate_greeting(cid, brief="")
    assert g["prose"] == "Mara nods at you across the bar."


def test_code_fence_wrapping_is_stripped(temp_db, monkeypatch):
    cid = _make_character(temp_db)
    monkeypatch.setattr(greetings, "get_prompt", lambda k: "SYS")
    monkeypatch.setattr("llm.providers.chat_complete",
                        lambda *a, **kw: '```\nMara looks up. "You\'re late."\n```')
    g = greetings.generate_greeting(cid, brief="")
    assert "```" not in g["prose"]
    assert g["prose"].startswith("Mara looks up")


def test_char_macro_is_resolved_player_macro_is_kept(temp_db, monkeypatch):
    cid = _make_character(temp_db, name="Mara")
    monkeypatch.setattr(greetings, "get_prompt", lambda k: "SYS")
    monkeypatch.setattr("llm.providers.chat_complete",
                        lambda *a, **kw: '{{char}} waves you over. "Hi, {{PLAYER}}."')
    g = greetings.generate_greeting(cid, brief="")
    assert "{{char}}" not in g["prose"]
    assert "Mara waves you over" in g["prose"]
    assert "{{PLAYER}}" in g["prose"]


def test_empty_generation_raises(temp_db, monkeypatch):
    cid = _make_character(temp_db)
    monkeypatch.setattr(greetings, "get_prompt", lambda k: "SYS")
    monkeypatch.setattr("llm.providers.chat_complete", lambda *a, **kw: "   ")
    with pytest.raises(RuntimeError):
        greetings.generate_greeting(cid, brief="")


def test_missing_character_raises(temp_db):
    with pytest.raises(ValueError):
        greetings.generate_greeting(999999, brief="")


def test_endpoint_returns_greeting_without_persisting(temp_db, monkeypatch):
    from web import app as app_module
    cid = _make_character(temp_db)
    monkeypatch.setattr(greetings, "get_prompt", lambda k: "SYS")
    monkeypatch.setattr("llm.providers.chat_complete", lambda *a, **kw: GREETING)

    out = app_module.char_generate_greeting(cid, {"prompt": "storm"})
    assert "{{PLAYER}}" in out["greeting"]["prose"]

    # NOT persisted: the character's stored sheet still has no greetings.
    sheet = json.loads(temp_db.q("SELECT sheet FROM characters WHERE id=?",
                                 (cid,), one=True)["sheet"])
    assert not (sheet.get("opening") or {}).get("greetings")
