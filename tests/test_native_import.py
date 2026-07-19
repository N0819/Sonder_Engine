import json
from character_schema import (
    CHARACTER_SCHEMA,
    PERSONA_SCHEMA,
    default_character_data,
    default_persona_data,
)

def test_native_character_imports_without_ai(temp_db, monkeypatch):
    import importers

    def fail_if_called(*args, **kwargs):
        raise AssertionError("AI must not be called for native imports")

    monkeypatch.setattr(
        "importers.chat_complete",
        fail_if_called,
    )

    sheet = default_character_data("Test Character")
    sheet["psychology"]["traits"] = [{
        "name": "patient",
        "strength": 0.7,
        "expression": "waits before responding",
    }]

    payload = {
        "schema": CHARACTER_SCHEMA,
        "version": 2,
        "data": sheet,
        "source": {"format": "native", "original": None},
    }

    char_id, imported = importers.import_character(payload, reinterpret=False)

    assert char_id
    assert imported["identity"]["name"] == "Test Character"
    assert imported["psychology"]["traits"][0]["name"] == "patient"

def test_native_persona_imports_without_ai(temp_db, monkeypatch):
    import importers

    def fail_if_called(*args, **kwargs):
        raise AssertionError("AI must not be called for native imports")

    monkeypatch.setattr(
        "importers.chat_complete",
        fail_if_called,
    )

    sheet = default_persona_data("Test Player")
    payload = {
        "schema": PERSONA_SCHEMA,
        "version": 2,
        "data": sheet,
        "source": {"format": "native", "original": None},
    }

    pid, imported = importers.import_persona(payload, reinterpret=False)

    assert pid
    assert imported["identity"]["name"] == "Test Player"