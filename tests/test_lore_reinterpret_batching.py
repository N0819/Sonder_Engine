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
import logging

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
    monkeypatch.setattr(importers, "get_prompt", lambda _prompt_id: "")

    long_entries = [("k", "x" * 20000, 0)]
    importers._reinterpret_entries(long_entries)

    assert captured_kwargs[0]["max_tokens"] > 3000


def test_an_unusable_batch_keeps_its_entries_and_reports_the_raw(
        monkeypatch, caplog):
    """CONTRACT CHANGED 2026-08-08. This asserted that an unusable batch RAISES,
    with the raw response in the message for diagnosis.

    Raising was the defect. `import_lorebook` turned it into "AI lore
    reinterpretation failed", so on the 300-entry, 354,677-character Re:Zero
    book -- about 59 batches -- one malformed reply discarded every batch that
    had already succeeded and every one that would have. The author's words:
    it should "take its time and do multiple calls so it doesn't lose all its
    progress on large books", and "repair call itself instead of just giving
    up".

    The diagnostic requirement this test was written for is unchanged and still
    asserted: the raw response must survive somewhere a human can read it. It
    moved from an exception message to the degradation report, because a book
    that imports with two rough entries beats a book that does not import.
    """
    def fake_chat_complete(role, system, user, **kwargs):
        return "not valid json at all {truncated"

    monkeypatch.setattr(importers, "chat_complete", fake_chat_complete)
    monkeypatch.setattr(importers, "get_prompt", lambda _prompt_id: "")

    with caplog.at_level(logging.WARNING):
        result = importers._reinterpret_entries([("k", "some content", 0)])

    # The entry survives, carrying the author's own text unrewritten.
    assert len(result) == 1
    assert result[0]["content"] == "some content"

    report = caplog.text
    assert "batch 1/1" in report
    assert "not valid json" in report, "the raw reply must stay diagnosable"


def test_a_repairable_batch_is_repaired_rather_than_degraded(monkeypatch):
    """One repair attempt before falling back, handed its own broken reply and
    the error -- never the source payload again, which is what makes it cheap.
    A batch the model can fix must not be silently imported unrewritten."""
    calls = []

    def fake_chat_complete(role, system, user, **kwargs):
        calls.append(user)
        if len(calls) == 1:
            return "{oops"
        return json.dumps({"entries": [
            {"keys": "k", "content": "rewritten properly", "category": "other"},
        ]})

    monkeypatch.setattr(importers, "chat_complete", fake_chat_complete)
    monkeypatch.setattr(importers, "get_prompt", lambda _prompt_id: "")

    result = importers._reinterpret_entries([("k", "some content", 0)])

    assert len(calls) == 2, "exactly one repair attempt, never a loop"
    assert "previous_reply" in calls[1], "the repair is handed its own output"
    assert result[0]["content"] == "rewritten properly"


def test_successful_reinterpretation_still_works(monkeypatch):
    def fake_chat_complete(role, system, user, **kwargs):
        return json.dumps({"entries": [
            {"keys": "castle", "content": "A stone castle.", "category": "location"},
        ]})

    monkeypatch.setattr(importers, "chat_complete", fake_chat_complete)
    monkeypatch.setattr(importers, "get_prompt", lambda _prompt_id: "")

    result = importers._reinterpret_entries([("castle, keep", "old text", 0)])

    assert len(result) == 1
    assert result[0]["content"] == "A stone castle."
    assert result[0]["category"] == "location"
