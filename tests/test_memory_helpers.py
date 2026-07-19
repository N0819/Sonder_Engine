"""Tests for pure memory helper functions."""

from memory import (
    _default_category,
    _extract_entities,
    _extract_key_phrases,
    _gist,
    _temporal_mode,
)

def test_temporal_old_cues():
    assert _temporal_mode("What happened long ago?") == "old"
    assert _temporal_mode("When was the first time we met?") == "old"

def test_temporal_recent_cues():
    assert _temporal_mode("What just happened?") == "recent"

def test_temporal_neutral():
    assert _temporal_mode("What did Mara promise?") == "neutral"

def test_quoted_phrase_is_preserved():
    phrases = _extract_key_phrases(
        'Mara said, "I will return before dawn."',
    )

    assert "I will return before dawn." in phrases

def test_kind_to_category():
    assert _default_category("episodic") == "episode"
    assert _default_category("dialogue") == "dialogue"
    assert _default_category("inference") == "inference"
    assert _default_category("unknown") == "episode"

def test_entity_extraction():
    entities = _extract_entities(
        "Alice met Bob at the Old Bridge",
    )

    assert "Alice" in entities
    assert "Bob" in entities
    assert "Old Bridge" in entities

def test_gist_truncation():
    long_text = "This is a sentence. " * 50
    gist = _gist(long_text, limit=100)

    assert len(gist) <= 100

def test_gist_normalizes_whitespace():
    assert _gist("One\n\n  two\tthree.") == "One two three."

def test_empty_helpers_are_safe():
    assert _extract_entities("") == []
    assert _extract_key_phrases("") == []
    assert _gist("") == ""