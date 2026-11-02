"""An implied item in the PLAYER's greeting mind stays implied.

`extract_greeting` forced `revealed_in_prose = True` onto every seed whose
content named the `{{PLAYER}}` token, in every mind. The flag has exactly one
reader -- `_seed_player_mind`, where it is the admission gate to
`persona_private_history`, the one store the player can open. For a
character's mind it was inert (`_route_mind_memories` writes every seed
regardless); for the player's it WIDENED THE PAGE: "{{PLAYER}} drank the tea
the innkeeper poisoned", which the model itself marked unrevealed, was
upgraded and written into the panel the player reads. The design states why
implied player items are refused: a guess can embed another mind's secret in
its phrasing (story_attire_import audit F2).

The upgrade is now never applied to the player's mind.
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


POISON = "{{PLAYER}} drank the tea the innkeeper poisoned."


def _extraction():
    return {"time": "now", "knowledge_seeds": [], "minds": [
        {"who": "Dr. Moon", "knowledge_seeds": [], "beliefs": [],
         "stances": [], "affect": None},
        {"who": "{{PLAYER}}", "knowledge_seeds": [
            {"content": POISON, "revealed_in_prose": False}],
         "beliefs": [], "stances": [], "affect": None},
    ]}


def test_extraction_does_not_upgrade_a_player_mind_seed(monkeypatch):
    from story import greetings
    monkeypatch.setattr(greetings, "complete_validated_json",
                        lambda **k: json.loads(json.dumps(_extraction())))
    monkeypatch.setattr(greetings, "get_prompt", lambda pid: "p")
    out = greetings.extract_greeting({"identity": {"name": "Dr. Moon"}},
                                     "prose")
    player = next(m for m in out["minds"] if m["who"] == "{{PLAYER}}")
    assert player["knowledge_seeds"][0]["revealed_in_prose"] is False


def test_the_launch_refuses_it_and_says_so(temp_db, monkeypatch):
    from core.db import wget
    from story import greetings
    monkeypatch.setattr(greetings, "complete_validated_json",
                        lambda **k: json.loads(json.dumps(_extraction())))
    monkeypatch.setattr(greetings, "get_prompt", lambda pid: "p")
    monkeypatch.setattr(greetings, "_run_pipeline", lambda cid, tid: iter(()))
    char_id, _ = importers.import_character(
        {"name": "Dr. Moon", "first_mes": "The tea is poured. {{user}} "
         "drinks."}, reinterpret=False)
    pid, _ = importers.import_persona({"name": "Dana"}, reinterpret=False)
    chat_id, _tid = greetings.start_story(char_id, pid, greeting_index=0)
    entries = wget(chat_id, "persona_private_history", None) or []
    assert not any("poisoned" in str(e.get("content")) for e in entries)
    record = wget(chat_id, "greeting_minds", {})
    player = next(m for m in record["minds"].values()
                  if m["resolved"] == "player")
    assert any("unrevealed" in r for r in player["refused"])
