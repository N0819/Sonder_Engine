"""The debt note caches the raw record and labels at return; a background
presence has ONE label function for every field of its payload.

Review 2026-09-07 A8 and its siblings.
"""
import json

import agents.background as background
from agents.character import _labelled_debt
from story.character_schema import default_character_data

from tests.test_background_character_reply import _setup


def test_the_debt_note_is_labelled_at_return_not_in_the_cache():
    raw = {"awaiting_your_answer": {"from": "Tamamo", "asked": "Well?",
                                    "turns_ago": 1}}
    assert _labelled_debt(raw, None)["awaiting_your_answer"]["from"] == "Tamamo"
    labelled = _labelled_debt(raw, lambda n: "the fox-eared woman")
    assert labelled["awaiting_your_answer"]["from"] == "the fox-eared woman"
    assert raw["awaiting_your_answer"]["from"] == "Tamamo", "the cache is untouched"
    assert _labelled_debt({}, None) == {}


def test_a_presence_names_only_whom_its_own_ledger_earns(temp_db):
    chat_id, ctx = _setup(temp_db, cast_names=["Sara"], turn_idx=3)
    temp_db.wset(chat_id, "known", {"Reya": ["Sara"]})
    knows = background._presence_label_fn(ctx, "Reya")
    stranger = background._presence_label_fn(ctx, "Doran")
    assert knows("Sara") == "Sara"
    assert stranger("Sara") != "Sara"
    assert stranger("the lamp") == "the lamp", "not a body: nothing to gate"
