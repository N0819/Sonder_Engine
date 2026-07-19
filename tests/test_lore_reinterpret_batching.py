"""Regression tests for _reinterpret_entries' batching and error
reporting. A flat 15-entries-per-batch cap paired with a flat
max_tokens=3000 silently truncated the model's JSON response for
lorebooks with long entries (confirmed live: an 8-entry lorebook
averaging ~2.6k chars/entry, single batch, response_tokens exactly
hit the 3000 cap), producing an unhelpful bare error. Batching by
character volume and scaling max_tokens off that volume fixes the
truncation; the improved error message must actually be diagnosable."""

from __future__ import annotations

import json

import pytest

import importers


def test_batches_split_by_character_volume_not_entry_count():
    # Three entries that individually fit the char budget, but not all
    # together -- should split into 2 batches, not 1.
    entries = [
        ("keys1", "x" * 4000, 0),
        ("keys2", "y" * 4000, 0),
        ("keys3", "z" * 100, 0),
    ]
    batches = importers._batch_entries_by_chars(entries, max_batch_chars=6000)
    assert len(batches) == 2
    assert batches[0] == [entries[0]]
    assert batches[1] == [entries[1], entries[2]]


def test_small_entries_all_fit_in_one_batch():
    entries = [(f"k{i}", "short content", 0) for i in range(10)]
    batches = importers._batch_entries_by_chars(entries, max_batch_chars=6000)
    assert len(batches) == 1
    assert len(batches[0]) == 10


def test_a_single_entry_larger_than_the_budget_still_gets_its_own_batch():
    entries = [("k", "x" * 20000, 0)]
    batches = importers._batch_entries_by_chars(entries, max_batch_chars=6000)
    assert len(batches) == 1
    assert batches[0] == entries


def test_max_tokens_scales_with_batch_character_volume(monkeypatch):
    captured_kwargs = []

    def fake_chat_complete(role, system, user, **kwargs):
        captured_kwargs.append(kwargs)
        return json.dumps({"entries": [{"keys": "k", "content": "rewritten", "category": "other"}]})

    monkeypatch.setattr(importers, "chat_complete", fake_chat_complete)

    long_entries = [("k", "x" * 20000, 0)]
    importers._reinterpret_entries(long_entries)

    assert captured_kwargs[0]["max_tokens"] > 3000


def test_no_usable_entries_error_includes_raw_response_for_diagnosis(monkeypatch):
    def fake_chat_complete(role, system, user, **kwargs):
        return "not valid json at all {truncated"

    monkeypatch.setattr(importers, "chat_complete", fake_chat_complete)

    with pytest.raises(RuntimeError) as exc_info:
        importers._reinterpret_entries([("k", "some content", 0)])

    message = str(exc_info.value)
    assert "batch 1/1" in message
    assert "not valid json" in message


def test_successful_reinterpretation_still_works(monkeypatch):
    def fake_chat_complete(role, system, user, **kwargs):
        return json.dumps({"entries": [
            {"keys": "castle", "content": "A stone castle.", "category": "location"},
        ]})

    monkeypatch.setattr(importers, "chat_complete", fake_chat_complete)

    result = importers._reinterpret_entries([("castle, keep", "old text", 0)])

    assert len(result) == 1
    assert result[0]["content"] == "A stone castle."
    assert result[0]["category"] == "location"
