"""A truncated authoring response must fail loudly, not become a finished card.

`_jparse` (now `_jparse_salvage`) closes the open braces of a cut-off
response, which is the right policy for a pipeline beat that must not die and
the wrong one for a generator whose output a person is about to trust: a
half-written character sheet parses into a card that LOOKS complete, with the
missing tail simply gone. That lands squarely on the failure CLAUDE.md calls
the worst of them -- `psychology.drive` empty while `serves: "drive"` stays
valid -- fifty beats before anyone notices. `_json_arrived_whole` existed,
made exactly this argument in its docstring, and was called at ONE of the ten
`_jparse` sites (`fill_appearance`).

Pinned here: every whole-document authoring site refuses a salvaged parse
with the same actionable "Max output tokens" message `fill_appearance` uses,
and nothing half-written reaches the database. `_reinterpret_entries` is the
deliberate EXCEPTION and is pinned as such: it has a keep-the-source
fallback, so dying there would lose the book to save it.
"""

from __future__ import annotations

import json
import time

import pytest

from core.db import q
from story import importers


BIG_SHEET = {
    "identity": {"name": "Iseul", "aliases": ["the courier"]},
    "psychology": {
        "drive": {"essence": "deliver what was entrusted",
                  "expression": "keeps moving", "taboo": "opening the parcel"},
        "traits": [{"name": "wary", "strength": 0.7,
                    "expression": "checks exits",
                    "activation_cues": ["crowds"], "inhibited_by": ["home"]}],
    },
    "social": {"voice": {"register": "clipped", "markers": ["short answers"]}},
    "opening": {"first_message": "A knock at the door."},
}


def _truncated(payload):
    """A cut of the payload that _jparse_salvage still turns into a dict --
    the exact shape of a response that ran out of output budget."""
    whole = json.dumps(payload)
    cut = None
    for n in range(len(whole) - 10, 10, -1):
        if importers._jparse_salvage(whole[:n]):
            cut = whole[:n]
            break
    assert cut is not None and cut != whole
    return cut


def _stub_raw(monkeypatch, raw):
    monkeypatch.setattr(importers, "chat_complete", lambda *a, **k: raw)


class TestAuthoringSitesRefuseTruncation:
    def test_generate_character_refuses_and_writes_nothing(
        self, temp_db, monkeypatch,
    ):
        _stub_raw(monkeypatch, _truncated(BIG_SHEET))
        with pytest.raises(RuntimeError, match="[Mm]ax output tokens"):
            importers.generate_character("a courier")
        assert q("SELECT COUNT(*) AS c FROM characters", one=True)["c"] == 0

    def test_generate_persona_refuses_and_writes_nothing(
        self, temp_db, monkeypatch,
    ):
        _stub_raw(monkeypatch, _truncated(BIG_SHEET))
        with pytest.raises(RuntimeError, match="[Mm]ax output tokens"):
            importers.generate_persona("a traveler")
        assert q("SELECT COUNT(*) AS c FROM personas", one=True)["c"] == 0

    def test_import_character_reinterpret_refuses(self, temp_db, monkeypatch):
        _stub_raw(monkeypatch, _truncated(BIG_SHEET))
        with pytest.raises(RuntimeError, match="[Mm]ax output tokens"):
            importers.import_character(
                {"name": "Iseul", "description": "a courier"},
                reinterpret=True,
            )
        assert q("SELECT COUNT(*) AS c FROM characters", one=True)["c"] == 0

    def test_fill_character_psychology_refuses(self, temp_db, monkeypatch):
        cid = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created) "
            "VALUES(?,?,?,?)",
            ("Iseul", json.dumps({"identity": {"name": "Iseul"}}), "{}",
             time.time()),
        )
        _stub_raw(monkeypatch, _truncated(BIG_SHEET))
        with pytest.raises(RuntimeError, match="[Mm]ax output tokens"):
            importers.fill_character_psychology(cid, "fill her in")

    def test_generate_lore_entries_refuses_and_writes_nothing(
        self, temp_db, monkeypatch,
    ):
        lid = temp_db.qi(
            "INSERT INTO lorebooks(name,chat_id,book_type,summary) "
            "VALUES(?,?,?,?)", ("Book", None, "general", ""),
        )
        response = {"entry_ops": [
            {"op": "create", "keys": f"k{i}",
             "content": f"A long entry about subject number {i}.",
             "category": "other"}
            for i in range(6)
        ]}
        _stub_raw(monkeypatch, _truncated(response))
        with pytest.raises(RuntimeError, match="[Mm]ax output tokens"):
            importers.generate_lore_entries(lid, "more lore")
        assert q("SELECT COUNT(*) AS c FROM lore_entries", one=True)["c"] == 0


class TestReinterpretStaysOnSalvage:
    def test_a_truncated_batch_keeps_the_source_entries(
        self, temp_db, monkeypatch,
    ):
        """The exception, pinned: _reinterpret_entries must NOT adopt the
        strict check -- its recovery ladder ends in importing the author's own
        text unrewritten, and a hard failure there loses the book."""
        entries = [("keys one", "Content one about the harbor.", 0),
                   ("keys two", "Content two about the road.", 0)]
        monkeypatch.setattr(
            importers, "chat_complete",
            lambda *a, **k: '{"entries": [{"keys": "keys one", "content": "trunc',
        )
        out = importers._reinterpret_entries(entries)
        assert len(out) >= 2
        contents = {e["content"] for e in out}
        assert "Content one about the harbor." in contents
        assert "Content two about the road." in contents
