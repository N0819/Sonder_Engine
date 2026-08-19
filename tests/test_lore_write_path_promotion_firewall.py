"""Promotion memory seeds must come only from what the presence perceived.

`draft_promoted_character` sent the model an evidence pack whose
`resolved_event` is the Director's OMNISCIENT record of each whole beat --
every room, every private exchange -- and the model's `memory_seeds` built
from that pack are later written as first-person `provenance: "witnessed"`
memories with no per-observer filter (persist/commit_background.py's
promotion write). The only floor was a name-mention test, which proves the
person was NAMED in a beat, never that they perceived any of it. The engine
already knows this is wrong: `agents/background.py`'s `_beat_for_presence`
filters resolved_event per presence for exactly this reason; the promotion
path walked around it.

The firewall rule (AGENTS.md § Information boundaries): a leak is an engine
failure, never a model's, so the fix cannot be a prompt clause. The SHEET may
still be authored from the full record -- authoring is tooling, and reading a
record puts nothing in anyone's head. The breach is the WRITE side: the call
that produces `memory_seeds` now receives ONLY the presence's own quoted
lines and their own recorded conduct tail, so an omniscient fact cannot reach
a seed because it never reaches the call. Fail closed by construction: a
presence with no speech and no conduct on record gets no seed call at all.
"""

from __future__ import annotations

import json
import time

import pytest

from core.db import wset
from story import importers

SECRET = "the assassin poured poison into the decanter in the west wing"


def _make_chat(db):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )


def _add_event(db, chat_id, turn, event, dialogue_log=None):
    turn_id = db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, turn, "x", time.time()),
    )
    db.qi(
        "INSERT INTO events(chat_id,turn_id,content) VALUES(?,?,?)",
        (chat_id, turn_id, json.dumps({
            "turn": turn, "summary": "", "event": event,
            "dialogue_log": dialogue_log or [],
        })),
    )


def _capture(monkeypatch, seeds_per_call):
    """Stub chat_complete; each call returns the next seeds list."""
    calls = []

    def fake(role, system, user, **kwargs):
        calls.append(json.loads(user))
        idx = min(len(calls) - 1, len(seeds_per_call) - 1)
        return json.dumps({
            "sheet": {"identity": {"name": "Innkeeper"},
                      "opening": {"first_message": ""}},
            "memory_seeds": seeds_per_call[idx],
        })

    monkeypatch.setattr(importers, "chat_complete", fake)
    return calls


class TestSeedCallInformationBudget:
    def test_the_seed_call_never_sees_the_omniscient_record(
        self, temp_db, monkeypatch,
    ):
        chat_id = _make_chat(temp_db)
        _add_event(
            temp_db, chat_id, 1,
            f"While the Innkeeper polishes glasses downstairs, {SECRET}.",
            dialogue_log=[{"speaker": "Innkeeper",
                           "exact_quote": "Another round?", "tone": "warm"}],
        )

        calls = _capture(monkeypatch,
                         [["I watched " + SECRET], ["I asked about a round."]])

        draft = importers.draft_promoted_character(chat_id, "Innkeeper")

        # Two calls: the sheet call (full record -- authoring may see it) and
        # the seed call, whose payload must not contain the omniscient text.
        assert len(calls) == 2
        assert SECRET in json.dumps(calls[0])
        assert SECRET not in json.dumps(calls[1])
        # And the seeds the draft carries are the SECOND call's, so a seed
        # authored from the full record never reaches the memory write.
        assert draft["memory_seeds"] == ["I asked about a round."]

    def test_the_seed_call_carries_their_own_conduct_tail(
        self, temp_db, monkeypatch,
    ):
        chat_id = _make_chat(temp_db)
        _add_event(
            temp_db, chat_id, 1, "The Innkeeper wipes the counter.",
            dialogue_log=[{"speaker": "Innkeeper",
                           "exact_quote": "Mind the step.", "tone": "dry"}],
        )
        wset(chat_id, "background_presences", {
            "Innkeeper": {"recent": [
                {"turn": 1, "text": 'said "Mind the step."; wipes the counter'},
            ]},
        })

        calls = _capture(monkeypatch, [[], ["I wiped the counter."]])
        draft = importers.draft_promoted_character(chat_id, "Innkeeper")

        assert draft["memory_seeds"] == ["I wiped the counter."]
        seed_payload = json.dumps(calls[1])
        assert "wipes the counter" in seed_payload
        assert "Mind the step." in seed_payload

    def test_a_mention_only_presence_gets_no_seeds_and_no_seed_call(
        self, temp_db, monkeypatch,
    ):
        """Named in the beat is not the same as having perceived any of it.
        With no line of their own and no recorded conduct, there is nothing a
        witnessed memory could legitimately be made from -- so no seed call
        happens at all, rather than an empty-evidence call the model would
        feel obliged to answer."""
        chat_id = _make_chat(temp_db)
        _add_event(temp_db, chat_id, 1,
                   f"The Innkeeper is asleep upstairs while {SECRET}.")

        calls = _capture(monkeypatch, [["I saw everything."]])
        draft = importers.draft_promoted_character(chat_id, "Innkeeper")

        assert len(calls) == 1  # the sheet call only
        assert draft["memory_seeds"] == []

    def test_sheet_call_seeds_are_never_trusted(self, temp_db, monkeypatch):
        """Even when the seed call fails, the full-record call's seeds must
        not be used as a fallback -- they were authored against the
        omniscient record."""
        chat_id = _make_chat(temp_db)
        _add_event(
            temp_db, chat_id, 1, f"{SECRET}.",
            dialogue_log=[{"speaker": "Innkeeper",
                           "exact_quote": "Evening.", "tone": ""}],
        )

        calls = []

        def fake(role, system, user, **kwargs):
            calls.append(json.loads(user))
            if len(calls) == 1:
                return json.dumps({
                    "sheet": {"identity": {"name": "Innkeeper"},
                              "opening": {"first_message": ""}},
                    "memory_seeds": ["I watched " + SECRET],
                })
            return "not json at all"

        monkeypatch.setattr(importers, "chat_complete", fake)
        draft = importers.draft_promoted_character(chat_id, "Innkeeper")

        assert draft["memory_seeds"] == []
