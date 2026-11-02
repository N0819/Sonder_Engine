"""An unset `embeddings` row is the local hash, never the default chat model.

The panel says so in three places (`static/js/settings.js`: "embeddings ...
is never inherited", "leave it unset and the engine falls back to a local
hash", "`embeddings` may NEVER follow Default"), and
`tests/test_provider_fallbacks.py` skips the role for that reason -- so no
test asked the server, and the server disagreed: `resolve_role_candidates`
followed `default` for every role, embeddings included. A host who left the
row unset with `default` on a chat model got one failing `/embeddings`
request per retrieval query and per commit batch, forever, each degrading to
crc32 with a warning blaming a "configured" provider, and the bank status
said the configured model did not answer (review 2026-11-01,
llm_providers_quality F6: `embedding_model_key with embeddings unset:
openrouter:1:z-ai/glm-5.3`).
"""
from __future__ import annotations

import pytest

from llm import providers


@pytest.fixture
def only_default(monkeypatch):
    monkeypatch.setattr(
        providers, "provider",
        lambda name: {"id": 1, "name": name, "kind": "openrouter",
                      "base_url": "https://openrouter.example/api/v1",
                      "api_key": "k"})
    monkeypatch.setattr(providers, "agent_models", lambda: {
        "default": {"provider": "openrouter", "model": "z-ai/glm-5.3"}})


def test_the_key_is_the_hash_and_the_role_resolves_to_nothing(only_default):
    assert providers.embedding_model_key() == "cheap:crc32:256"
    with pytest.raises(RuntimeError, match="embeddings"):
        providers.resolve_role("embeddings")


def test_no_request_is_made_for_an_unset_role(only_default, monkeypatch):
    sent = []

    class _NoWire:
        def post(self, url, **k):
            # Counted, not asserted: the retry ladder swallows any exception
            # the wire raises, so a raise here would pass unnoticed.
            sent.append(url)
            raise ConnectionError("refused")

    monkeypatch.setattr(providers, "_session", lambda: _NoWire())
    monkeypatch.setattr(providers.time, "sleep", lambda _s: None)
    got = providers.embed_texts_meta(["a memory"])
    assert sent == [], "an unset embeddings role sent a request"
    assert got.fallback and got.model_key == "cheap:crc32:256"


def test_every_other_role_still_follows_default(only_default):
    for role in providers.ROLES:
        if role in providers.NEVER_FOLLOWS_DEFAULT:
            continue
        prov, model, _cfg = providers.resolve_role(role)
        assert model == "z-ai/glm-5.3", role


def test_a_set_embeddings_row_is_used(monkeypatch):
    monkeypatch.setattr(
        providers, "provider",
        lambda name: {"id": 2, "name": name, "kind": "openrouter",
                      "base_url": "https://x/api/v1", "api_key": "k"})
    monkeypatch.setattr(providers, "agent_models", lambda: {
        "default": {"provider": "openrouter", "model": "z-ai/glm-5.3"},
        "embeddings": {"provider": "openrouter", "model": "perplexity/pplx-embed"}})
    assert providers.embedding_model_key() == "openrouter:2:perplexity/pplx-embed"
