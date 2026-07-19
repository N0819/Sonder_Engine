"""Regression tests for provider API key handling: the key must never be
sent back to the frontend once stored, and leaving the field blank on
update must preserve the existing key rather than wiping it."""

from __future__ import annotations

import app


def test_add_provider_never_returns_raw_key(temp_db):
    result = app.add_provider({"kind": "openai", "api_key": "sk-secret-123"})

    assert "api_key" not in result
    assert result["has_key"] is True

    row = temp_db.q(
        "SELECT api_key FROM providers WHERE id=?", (result["id"],), one=True,
    )
    assert row["api_key"] == "sk-secret-123"


def test_add_provider_without_key_reports_has_key_false(temp_db):
    result = app.add_provider({"kind": "openai"})
    assert result["has_key"] is False


def test_put_provider_with_blank_key_preserves_existing_key(temp_db):
    created = app.add_provider({"kind": "openai", "api_key": "sk-original"})

    updated = app.put_provider(created["id"], {
        "name": "Renamed", "kind": "openai", "base_url": "https://api.example.com",
        "api_key": "",
    })

    assert "api_key" not in updated
    assert updated["has_key"] is True
    row = temp_db.q(
        "SELECT api_key, name FROM providers WHERE id=?", (created["id"],), one=True,
    )
    assert row["api_key"] == "sk-original"
    assert row["name"] == "Renamed"


def test_put_provider_with_new_key_replaces_existing_key(temp_db):
    created = app.add_provider({"kind": "openai", "api_key": "sk-original"})

    app.put_provider(created["id"], {
        "name": "x", "kind": "openai", "base_url": "",
        "api_key": "sk-replacement",
    })

    row = temp_db.q(
        "SELECT api_key FROM providers WHERE id=?", (created["id"],), one=True,
    )
    assert row["api_key"] == "sk-replacement"


def test_bootstrap_provider_list_omits_raw_keys(temp_db):
    app.add_provider({"kind": "openai", "api_key": "sk-should-not-leak"})

    boot = app.bootstrap()

    assert len(boot["providers"]) == 1
    assert "api_key" not in boot["providers"][0]
    assert boot["providers"][0]["has_key"] is True
