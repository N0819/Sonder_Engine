"""The referring grammar's pack tables are built once per language, and loudly.

`referring` rebuilt `articles()`, `number_words()`, `phrase_openers()`,
`conjunctions()`, `generic_heads()` and `feature_connectives()` on every call,
and `is_boundary` asks three of them per WORD: one label ladder cost 378
`compositor_value` calls and 7,120 casefolds, 6.29 ms (dressing audit E1;
a scratch prototype memoizing the six tables per language measured 1.51 ms,
identical output). They are now built once per language and dropped whenever
the packs reload.

And they no longer swallow a lookup error (dressing audit F13): a renamed key
turned `articles()` into an empty set, which silently switched English labels
to the Japanese head-final rule. `LanguagePackError` is the loud failure the
loader designed, so it propagates.
"""

from __future__ import annotations

import pytest

from language_runtime import LanguagePackError, language_scope, referring


def test_each_language_reads_its_own_tables():
    with language_scope("en"):
        english = referring.articles()
        assert not referring.head_final()
    with language_scope("ja"):
        assert referring.articles() == frozenset()
        assert referring.head_final()
    with language_scope("en"):
        assert referring.articles() == english and english


@pytest.mark.parametrize("language_id", ["en", "ja"])
def test_the_cached_tables_are_the_computed_tables(language_id):
    with language_scope(language_id):
        cached = referring._tables(language_id)
        assert cached == referring._compute_tables(language_id)
        assert referring.number_words() == cached.number_words
        assert referring.phrase_openers() == cached.phrase_openers
        assert referring.conjunctions() == cached.conjunctions
        assert referring.generic_heads() == cached.generic_heads
        assert referring.feature_connectives() == cached.feature_connectives


def test_a_missing_table_fails_loudly(monkeypatch):
    def missing(name, language_id=None):
        raise LanguagePackError(f"language pack lacks compositor value {name!r}")

    monkeypatch.setattr(referring, "compositor_value", missing)
    referring._tables.cache_clear()
    try:
        with language_scope("en"), pytest.raises(LanguagePackError):
            referring.articles()
    finally:
        monkeypatch.undo()
        referring._tables.cache_clear()


def test_a_pack_reload_drops_the_cached_tables():
    from language_runtime import installed_language_packs

    with language_scope("en"):
        referring.articles()
    assert referring._tables.cache_info().currsize >= 1
    installed_language_packs(refresh=True)
    assert referring._tables.cache_info().currsize == 0
