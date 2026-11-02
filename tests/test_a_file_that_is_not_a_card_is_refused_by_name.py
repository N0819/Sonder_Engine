"""A file that is not a character card is refused, and told what was expected.

The import dialog accepts any JSON that parses, and `resolve_import_card`
handed any mapping on: a lorebook, or an unrelated JSON, uploaded to the
character importer with reinterpretation off became a default sheet named
"Unnamed" and a 200 carrying only the empty-drive warnings -- a junk row
nobody asked for, made silently (story_attire_import audit F20). The persona
importer did the same under the name "Player".

A payload is a card when it carries at least one field a card format
defines; a World Info book (an `entries` table and nothing a character has)
is named as one, so the author knows where it belongs. Refused before any
model call, on both paths.
"""

from __future__ import annotations

import pytest

from story import importers


def _no_model(monkeypatch):
    def fail(*a, **k):
        raise AssertionError("a payload that is not a card reached the model")
    monkeypatch.setattr(importers, "chat_complete", fail)


@pytest.mark.parametrize("reinterpret", [False, True])
def test_a_lorebook_is_refused_as_a_character(temp_db, monkeypatch,
                                              reinterpret):
    _no_model(monkeypatch)
    book = {"name": "Salt Road", "entries": {"0": {"content": "Tolls."}}}
    with pytest.raises(ValueError, match="lorebook"):
        importers.import_character(book, reinterpret=reinterpret)
    assert temp_db.q("SELECT id FROM characters") == []


@pytest.mark.parametrize("payload", [{"foo": 1}, {}, ["a", "list"]])
def test_an_unrelated_json_is_refused(temp_db, monkeypatch, payload):
    _no_model(monkeypatch)
    with pytest.raises(ValueError, match="not a character card"):
        importers.import_character(payload, reinterpret=False)
    with pytest.raises(ValueError, match="not a persona card"):
        importers.import_persona(payload, reinterpret=False)
    assert temp_db.q("SELECT id FROM characters") == []
    assert temp_db.q("SELECT id FROM personas") == []


def test_the_smallest_real_cards_still_import(temp_db):
    cid, sheet = importers.import_character({"name": "Dr. Moon"},
                                            reinterpret=False)
    assert sheet["identity"]["name"] == "Dr. Moon"
    pid, psheet = importers.import_persona({"name": "Dana"},
                                           reinterpret=False)
    assert psheet["identity"]["name"] == "Dana"
    v2 = {"spec": "chara_card_v2", "data": {"name": "Kit",
                                            "first_mes": "Hello."}}
    _cid, sheet = importers.import_character(v2, reinterpret=False)
    assert sheet["identity"]["name"] == "Kit"


def test_a_native_export_is_still_a_card(temp_db):
    from story.character_schema import CHARACTER_SCHEMA, default_character_data
    native = {"schema": CHARACTER_SCHEMA,
              "data": default_character_data("Kit")}
    _cid, sheet = importers.import_character(native, reinterpret=False)
    assert sheet["identity"]["name"] == "Kit"
