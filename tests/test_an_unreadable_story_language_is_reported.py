"""A story whose language cannot be loaded runs in English, and SAYS so.

`story_language()` keeps the owner's "warn, never refuse" fallback: a stored
language whose pack or adapter cannot load still plays, in English. It used to
do that with no log line at any level (dressing audit F12): a Japanese story
whose adapter failed to import ran every turn with English prompts,
recognisers and renderer while its stored `story_language` still said `ja`,
and nothing anywhere recorded why. Now the fallback logs a warning naming the
stored language and the reason -- once per process per language id, because
the reader runs on every turn.
"""

from __future__ import annotations

import logging

import pytest

import language_runtime
from language_runtime import LanguagePackError


@pytest.fixture
def stored_language(monkeypatch):
    """Point `story_language`'s stored-value read at a chosen language."""
    import core.db

    holder = {"value": "ja"}
    monkeypatch.setattr(core.db, "wget",
                        lambda chat_id, key, default=None: holder["value"])
    monkeypatch.setattr(language_runtime, "_FALLBACK_REPORTED", set())
    return holder


def _fallback_warnings(caplog):
    return [r for r in caplog.records
            if r.levelno == logging.WARNING and "falls back to" in r.getMessage()]


def test_a_broken_adapter_falls_back_to_english_and_warns(stored_language,
                                                          monkeypatch, caplog):
    def broken(language_id, *, capability=None):
        raise LanguagePackError(
            "deterministic adapter 'japanese' could not be loaded: boom")

    monkeypatch.setattr(language_runtime, "require_language_pack", broken)
    with caplog.at_level(logging.WARNING, logger="fiction_engine"):
        assert language_runtime.story_language(7) == "en"
    warned = _fallback_warnings(caplog)
    assert len(warned) == 1
    assert "'ja'" in warned[0].getMessage()
    assert "could not be loaded" in warned[0].getMessage()


def test_the_warning_is_once_per_language_not_once_per_turn(stored_language,
                                                            caplog):
    stored_language["value"] = "xx"          # no such pack installed
    with caplog.at_level(logging.WARNING, logger="fiction_engine"):
        for _turn in range(5):
            assert language_runtime.story_language(7) == "en"
    assert len(_fallback_warnings(caplog)) == 1


def test_a_healthy_story_language_logs_nothing(stored_language, caplog):
    with caplog.at_level(logging.WARNING, logger="fiction_engine"):
        assert language_runtime.story_language(7) == "ja"
    assert _fallback_warnings(caplog) == []
