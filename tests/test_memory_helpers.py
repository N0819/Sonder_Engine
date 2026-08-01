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

class TestStrandedEmbeddingsAreAnnounced:
    """Configuring an `embeddings` provider on a story with history silently
    halves its retrieval, and nothing said a word.

    A row whose `embedding_model`/`embedding_dim` differ from the live
    provider's scores 0.0 on BOTH vector rankings — correct in itself, since a
    vector from another model is not comparable — and nothing re-embeds, so it
    stays 0.0 forever. Memories written before the switch drop to keyword and
    exact matching while newer ones keep all four signals: the bank splits into
    two eras at the moment of the upgrade. Retrieval still WORKS, which is
    precisely why it needs announcing rather than raising. See
    docs/UNBUILT.md §1.15.
    """

    def _capture(self, monkeypatch):
        import logging

        import memory
        seen = []

        class _H(logging.Handler):
            def emit(self, record):
                seen.append(record.getMessage())

        handler = _H()
        memory.logger.addHandler(handler)
        monkeypatch.setattr(memory, "_STRANDED_REPORTED", set())
        return memory, seen, handler

    def test_a_mismatched_bank_is_reported(self, monkeypatch):
        memory, seen, handler = self._capture(monkeypatch)
        try:
            memory._warn_stranded_embeddings(1, 2, 300, 442, "openai:x:embed-3")
        finally:
            memory.logger.removeHandler(handler)
        assert len(seen) == 1
        assert "300 of 442" in seen[0]

    def test_it_reports_once_per_situation_not_once_per_beat(self, monkeypatch):
        """Retrieval runs for every character on every beat; a warning per call
        is the noise it exists to cut through."""
        memory, seen, handler = self._capture(monkeypatch)
        try:
            for _ in range(5):
                memory._warn_stranded_embeddings(1, 2, 300, 442, "openai:x:embed-3")
        finally:
            memory.logger.removeHandler(handler)
        assert len(seen) == 1

    def test_a_different_model_is_a_new_situation(self, monkeypatch):
        memory, seen, handler = self._capture(monkeypatch)
        try:
            memory._warn_stranded_embeddings(1, 2, 300, 442, "openai:x:embed-3")
            memory._warn_stranded_embeddings(1, 2, 300, 442, "cheap:crc32:256")
        finally:
            memory.logger.removeHandler(handler)
        assert len(seen) == 2

    def test_a_compatible_bank_says_nothing(self, monkeypatch):
        memory, seen, handler = self._capture(monkeypatch)
        try:
            memory._warn_stranded_embeddings(1, 2, 0, 442, "cheap:crc32:256")
            memory._warn_stranded_embeddings(1, 2, 5, 0, "cheap:crc32:256")
        finally:
            memory.logger.removeHandler(handler)
        assert seen == []
