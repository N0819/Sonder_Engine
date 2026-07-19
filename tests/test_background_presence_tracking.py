"""Regression tests for track_background_presences/promotable_background_
presences: deterministic, LLM-free tracking of named entities the
director keeps writing into resolved_event/dialogue_log who have no
character sheet -- the "Dr. Crusher problem" (present and active for 35+
turns with zero mechanical backing)."""

from __future__ import annotations

import json
import time

from commit import (
    track_background_presences,
    promotable_background_presences,
    _background_name_mentioned,
    BACKGROUND_PROMOTION_DIALOGUE_THRESHOLD,
    BACKGROUND_PROMOTION_MENTION_THRESHOLD,
)
from character_schema import default_character_data
from pipeline_context import ChatData, PipelineContext, TurnData


def _make_chat(db):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )


def _make_character(db, name):
    return db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        (name, json.dumps(default_character_data(name)), "{}", time.time()),
    )


def _ctx(chat_id, turn_idx, cast, director_resolve):
    return PipelineContext(
        chat=ChatData(
            id=chat_id, name="Test", persona_id=None, lorebook_id=None,
            scenario="", created=time.time(),
        ),
        turn=TurnData(
            id=turn_idx + 1, chat_id=chat_id, idx=turn_idx, player_input="",
            created=time.time(),
        ),
        cast=cast, input="", director_resolve=director_resolve,
    )


class TestBackgroundNameMentioned:
    def test_full_name_match(self):
        assert _background_name_mentioned("Dr. Crusher", "Dr. Crusher checks the readout.")

    def test_last_name_only_still_matches(self):
        assert _background_name_mentioned("Dr. Crusher", "Crusher checks the readout.")

    def test_title_word_alone_does_not_match(self):
        # "Dr." stripped as a title word -- a scene full of OTHER doctors
        # must not count as a mention of this specific one.
        assert not _background_name_mentioned("Dr. Crusher", "The doctor on duty checks the readout.")

    def test_short_substring_does_not_false_positive(self):
        # "Ana" (a hypothetical 3-letter name) should not match inside
        # unrelated words like "banana" -- word-boundary regex, not a
        # bare substring check.
        assert not _background_name_mentioned("Ana", "The banana was left on the table.")

    def test_no_relation_does_not_match(self):
        assert not _background_name_mentioned("Dr. Crusher", "Picard stands at the viewscreen.")


def test_registered_cast_members_are_never_tracked(temp_db):
    chat_id = _make_chat(temp_db)
    char_id = _make_character(temp_db, "Jean-Luc Picard")
    cast = [dict(temp_db.q("SELECT * FROM characters WHERE id=?", (char_id,), one=True))]

    ctx = _ctx(chat_id, 0, cast, {
        "dialogue_log": [{"speaker": "Jean-Luc Picard", "exact_quote": "Make it so."}],
        "resolved_event": "Picard gives the order.",
    })
    track_background_presences(ctx, nonce=0)

    presences = temp_db.wget(chat_id, "background_presences", {})
    assert "Jean-Luc Picard" not in presences


def test_untracked_speaker_gets_tracked_and_counted(temp_db):
    chat_id = _make_chat(temp_db)

    ctx = _ctx(chat_id, 3, [], {
        "dialogue_log": [{"speaker": "Dr. Crusher", "exact_quote": "Hold still."}],
        "resolved_event": "Crusher checks the readout.",
    })
    track_background_presences(ctx, nonce=0)

    presences = temp_db.wget(chat_id, "background_presences", {})
    assert "Dr. Crusher" in presences
    assert presences["Dr. Crusher"]["dialogue_turns"] == [3]
    assert presences["Dr. Crusher"]["first_turn"] == 3
    assert presences["Dr. Crusher"]["last_turn"] == 3


def test_entity_with_person_kind_is_tracked(temp_db):
    chat_id = _make_chat(temp_db)

    ctx = _ctx(chat_id, 1, [], {
        "state_diff": {"entities": {
            "e1": {"kind": "person", "name": "The Innkeeper"},
            "e2": {"kind": "fixture", "name": "The Bar"},
        }},
    })
    track_background_presences(ctx, nonce=0)

    presences = temp_db.wget(chat_id, "background_presences", {})
    assert "The Innkeeper" in presences
    assert "The Bar" not in presences


def test_mentions_only_count_for_already_tracked_names(temp_db):
    chat_id = _make_chat(temp_db)
    temp_db.wset(chat_id, "background_presences", {
        "Dr. Crusher": {
            "first_turn": 1, "last_turn": 1,
            "dialogue_turns": [], "mention_turns": [],
        },
    })

    ctx = _ctx(chat_id, 5, [], {
        "resolved_event": "Crusher moves quietly near the biobed. A stranger watches from the door.",
    })
    track_background_presences(ctx, nonce=0)

    presences = temp_db.wget(chat_id, "background_presences", {})
    assert presences["Dr. Crusher"]["mention_turns"] == [5]
    # "A stranger" is never seeded as a candidate from free prose alone.
    assert "A stranger" not in presences
    assert "stranger" not in {n.lower() for n in presences}


def test_promotable_after_dialogue_threshold(temp_db):
    chat_id = _make_chat(temp_db)
    for turn in range(BACKGROUND_PROMOTION_DIALOGUE_THRESHOLD):
        ctx = _ctx(chat_id, turn, [], {
            "dialogue_log": [{"speaker": "Dr. Crusher", "exact_quote": f"Line {turn}."}],
        })
        track_background_presences(ctx, nonce=0)

    result = promotable_background_presences(chat_id)
    crusher = next(r for r in result if r["name"] == "Dr. Crusher")
    assert crusher["promotable"] is True


def test_not_promotable_below_threshold(temp_db):
    chat_id = _make_chat(temp_db)
    ctx = _ctx(chat_id, 0, [], {
        "dialogue_log": [{"speaker": "A Passing Waiter", "exact_quote": "Anything else?"}],
    })
    track_background_presences(ctx, nonce=0)

    result = promotable_background_presences(chat_id)
    waiter = next(r for r in result if r["name"] == "A Passing Waiter")
    assert waiter["promotable"] is False


def test_promotable_after_mention_threshold(temp_db):
    chat_id = _make_chat(temp_db)
    temp_db.wset(chat_id, "background_presences", {
        "Dr. Crusher": {
            "first_turn": 1, "last_turn": 1,
            "dialogue_turns": [], "mention_turns": [],
        },
    })
    for turn in range(2, 2 + BACKGROUND_PROMOTION_MENTION_THRESHOLD):
        ctx = _ctx(chat_id, turn, [], {
            "resolved_event": "Crusher tends quietly to her patient.",
        })
        track_background_presences(ctx, nonce=0)

    result = promotable_background_presences(chat_id)
    crusher = next(r for r in result if r["name"] == "Dr. Crusher")
    assert crusher["promotable"] is True
