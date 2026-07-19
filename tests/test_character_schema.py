"""Tests for native and legacy character schemas."""

from character_schema import (
    CHARACTER_SCHEMA,
    default_character_data,
    normalize_character_data,
    normalize_persona_data,
    senses_as_text,
)

def test_default_character_is_agnostic():
    sheet = default_character_data("Test")

    assert sheet["identity"]["name"] == "Test"
    assert sheet["embodiment"]["senses"][0]["acuity"] == "ordinary"
    assert sheet["psychology"]["traits"] == []
    assert (
        sheet["social"]["baseline_stances"]["unknown_person"]["trust"]
        == 0.0
    )

def test_legacy_sheet_normalizes():
    legacy = {
        "name": "Legacy",
        "appearance": "A plainly dressed person.",
        "core": {
            "traits": ["careful"],
            "values": ["accuracy"],
            "self_image": "A reliable observer.",
        },
        "active_state": {
            "mood": "neutral",
            "goal": "",
        },
        "abilities": [
            {
                "name": "Observation",
                "level": "expert",
            },
        ],
        "private_history": [
            {
                "content": "secret",
                "known_by": [],
            },
        ],
    }

    normalized = normalize_character_data(legacy)

    assert normalized["identity"]["name"] == "Legacy"
    assert normalized["psychology"]["traits"][0]["name"] == "careful"
    assert (
        normalized["embodiment"]["visible"]["summary"]
        == "A plainly dressed person."
    )
    assert normalized["competence"]["abilities"][0]["level"] == "expert"
    assert (
        normalized["knowledge"]["private_history"][0]["content"]
        == "secret"
    )

def test_native_export_envelope_unwraps():
    sheet = default_character_data("Envelope")
    payload = {
        "schema": CHARACTER_SCHEMA,
        "version": 2,
        "data": sheet,
        "source": {"format": "native"},
    }

    normalized = normalize_character_data(payload)

    assert normalized["identity"]["name"] == "Envelope"

def test_native_character_defaults_missing_fields():
    normalized = normalize_character_data({
        "identity": {"name": "Partial"},
        "psychology": {"traits": []},
    })

    assert normalized["identity"]["name"] == "Partial"
    assert normalized["simulation"]["tier"] == "mid"
    assert normalized["knowledge"]["access_tags"] == ["common"]
    assert normalized["opening"]["first_message"] == ""

def test_native_persona_defaults_missing_fields():
    normalized = normalize_persona_data({
        "identity": {"name": "Partial Player"},
        "narration": {},
    })

    assert normalized["identity"]["name"] == "Partial Player"
    assert normalized["competence"]["abilities"] == []
    assert normalized["narration"]["voice_setting"] == ""

def test_native_private_history_coerces_bare_strings():
    # private_knowledge_for (scene.py) only accepts dict entries with a
    # "content" key. Every other list-of-facts field on this schema
    # (traits, values, abilities, senses) tolerates a legacy bare-string
    # form; private_history must too, or a character authored with plain
    # strings (e.g. hand-typed via the API, or the character generator
    # deviating from its prompted shape) silently ends up with zero
    # private knowledge and nothing signals why.
    normalized = normalize_character_data({
        "identity": {"name": "Secretive"},
        "knowledge": {
            "private_history": [
                "A plain-string secret only this character should carry.",
                {"content": "An already-structured secret.", "known_by": ["Ally"]},
                "",
            ],
        },
    })

    entries = normalized["knowledge"]["private_history"]

    assert entries == [
        {
            "content": "A plain-string secret only this character should carry.",
            "about": "",
            "known_by": [],
        },
        {"content": "An already-structured secret.", "known_by": ["Ally"]},
    ]

def test_legacy_character_private_history_coerces_bare_strings():
    normalized = normalize_character_data({
        "name": "Legacy Secretive",
        "private_history": ["A legacy-schema plain-string secret."],
    })

    assert normalized["knowledge"]["private_history"] == [
        {"content": "A legacy-schema plain-string secret.", "about": "", "known_by": []},
    ]

def test_native_persona_private_history_coerces_bare_strings():
    normalized = normalize_persona_data({
        "identity": {"name": "Secretive Player"},
        "knowledge": {"private_history": ["A plain-string persona secret."]},
    })

    assert normalized["knowledge"]["private_history"] == [
        {"content": "A plain-string persona secret.", "about": "", "known_by": []},
    ]

def test_senses_as_text_string_passthrough():
    assert (
        senses_as_text("ordinary human senses")
        == "ordinary human senses"
    )

def test_senses_as_text_structured():
    senses = [
        {
            "channel": "vision",
            "acuity": "ordinary",
            "range": "ordinary",
            "notes": "",
        },
        {
            "channel": "hearing",
            "acuity": "keen",
            "range": "ordinary",
            "notes": "can hear heartbeats",
        },
    ]

    text = senses_as_text(senses)

    assert "keen hearing" in text
    assert "can hear heartbeats" in text

def test_senses_as_text_rejects_invalid_container():
    assert senses_as_text(None) == "ordinary senses"
    assert senses_as_text({"channel": "vision"}) == "ordinary senses"