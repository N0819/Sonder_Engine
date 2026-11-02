"""The player's own short name is the player, in every script.

THE FLOOR (story_scene_schema audit F5). A line the model attributes to just
the player's first or last name was matched against the words of every alias
-- the persona's name AND the generic "the player", "the protagonist" -- and
floored at four CODE POINTS to keep "the" out. Four Latin letters are a short
name and four kanji a whole one, so "ヒナミ" (persona "佐藤 ヒナミ") and "Kai"
("Kai Rowan") were never the player: the Director skipped the player-speech
authority check for the line, never retagged it to the persona, and
perception graded it from a bystander's room.

The floor existed because the generic aliases' words ("the" of "the
player") were in the same pool. The persona NAME's own words are now their
own pool -- whitespace words, and the script runs an unspaced name is written
in, so "佐藤ヒナミ" carries "ヒナミ" too -- and no length decides them; the
generic aliases keep their words and the floor they always had.

THE COST (E1). `is_player_speaker` runs per dialogue line, several times a
beat, and every call queried the persona and normalized it twice: 0.36 ms per
normalization on the median in-use persona, 3.2 ms on the largest. The name
is now read once per persona sheet TEXT, which is also the whole of the
invalidation: an edited persona is a different string.
"""

from __future__ import annotations

import json
import uuid

import pytest

from story import scene
from story.character_schema import default_persona_data


def _persona(db, name, **extra):
    sheet = default_persona_data(name)
    sheet.update(extra)
    return db.qi("INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
                 (name, json.dumps(sheet), "{}"))


@pytest.mark.parametrize("persona,speaker,expected", [
    ("佐藤 ヒナミ", "ヒナミ", True),
    ("佐藤ヒナミ", "ヒナミ", True),
    ("佐藤ヒナミ", "佐藤", True),
    ("Hinami Sato", "Hinami", True),
    ("Mira Vale", "Mira", True),
    ("Kai Rowan", "Kai", True),
    ("Kai Rowan", "Rowan", True),
    ("Alex Chen", "Al", False),
    ("Alex Chen", "Alexandra", False),
    ("Kai Rowan", "the", False),
    # The generic aliases keep their own words, floored as they always were.
    ("Kai Rowan", "Protagonist", True),
    ("佐藤ヒナミ", "ヒナミコ", False),
    ("Kai Rowan", "the player", True),
    ("Kai Rowan", "Kai Rowan", True),
])
def test_a_word_of_the_players_own_name_is_the_player(
        temp_db, persona, speaker, expected):
    chat = {"persona_id": _persona(temp_db, persona)}
    assert scene.is_player_speaker(speaker, chat) is expected


def test_no_persona_is_still_the_stranger(temp_db):
    assert scene.is_player_speaker("The Stranger", {}) is True
    assert scene.is_player_speaker("Someone", {}) is False


def test_a_beat_of_dialogue_normalizes_the_persona_once(temp_db, monkeypatch):
    # A sheet no earlier test has seen, so the first call is a miss.
    chat = {"persona_id": _persona(temp_db, "Kai Rowan",
                                   note=uuid.uuid4().hex)}
    calls = []
    real = scene.normalize_persona_data
    monkeypatch.setattr(scene, "normalize_persona_data",
                        lambda value: calls.append(1) or real(value))
    for _ in range(12):
        scene.is_player_speaker("Kai", chat)
        scene.is_player_speaker("Someone Else", chat)
    assert len(calls) <= 1


def test_an_edited_persona_is_read_afresh(temp_db):
    pid = _persona(temp_db, "Kai Rowan")
    chat = {"persona_id": pid}
    assert scene.is_player_speaker("Kai", chat) is True
    temp_db.qi("UPDATE personas SET sheet=? WHERE id=?",
               (json.dumps(default_persona_data("Mira Vale")), pid))
    assert scene.is_player_speaker("Kai", chat) is False
    assert scene.is_player_speaker("Mira", chat) is True
