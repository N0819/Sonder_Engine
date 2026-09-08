"""The origin-on-drift mood signal reads the resolved valence, not English.

REVIEW_2026-09-07 B30. `_origin_on_drift`'s third signal is a sign flip in the
character's affect surface against their baseline -- a number. It used to gate
that number behind two module-local English word tuples ("despair", "elated",
...), so a mood label the tuples did not happen to contain never reached the
comparison at all. That is one fact stored twice: `persist/commit_memory.py`
writes `active_state["mood"]` as `affect.surface.label` and the valence beside
it off the SAME resolved surface, and the engine already keeps its mood
vocabulary in the language packs (`linguistics._MOOD_VALENCE`, read by
`memory_retrieval._mood_axis`) rather than in a module.

These tests hold the rule that the sign decides: a flip fires whatever the
label says or fails to say, and no flip fires nothing.
"""

from __future__ import annotations

import json
import time

import pytest

from mind import memory
from story.character_schema import default_character_data

ORIGIN = "She poled the ferry across, and the far bank was still dark."


@pytest.fixture
def bank(temp_db):
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Drift", "", time.time()))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Mara", json.dumps(default_character_data("Mara")), "{}", time.time(),
         "char_mara"))
    memory.save_memory_summary(chat_id, char_id, ORIGIN,
                               start_turn_idx=0, end_turn_idx=10)
    return {"chat": chat_id, "char": char_id}


def _state(mood, valence, base_v):
    return {"mood": mood,
            "affect": {"surface": {"label": mood, "valence": valence},
                       "baseline": {"valence": base_v}}}


def _fires(bank, state):
    payload = memory._origin_on_drift(
        bank["chat"], bank["char"], 60, state,
        clock=memory.MemoryClock(bank["chat"], bank["char"], 60,
                                 viewer_frame_id=None))
    return payload.get("where_i_came_from", {}).get(
        "what_i_lived_through_then") == ORIGIN


@pytest.mark.parametrize("mood", [
    # Illustrations of labels the deleted tuples did not carry, not a list to
    # match against: an English word outside them, a label in another
    # language, and no label at all. Each carries the same flipped number.
    "hollowed out", "絶望", "",
])
def test_a_sign_flip_fires_whatever_the_label_says(bank, mood):
    assert _fires(bank, _state(mood, -0.62, 0.4))


def test_a_label_the_old_tuples_carried_still_fires(bank):
    """The change subtracts nothing: the cases that fired before still fire."""
    assert _fires(bank, _state("despair", -0.62, 0.4))


def test_no_flip_fires_nothing_however_the_label_reads(bank):
    # Same side of zero as the baseline: a mood, not a change of heart.
    assert not _fires(bank, _state("despair", -0.62, -0.4))
    # Crossed zero but sitting on it: below `_MOOD_FLIP_MIN`, so not a flip.
    assert not _fires(bank, _state("uneasy", -0.05, 0.4))
    # No affect surface at all (a legacy row): nothing to compare.
    assert not _fires(bank, {"mood": "despair"})


def test_a_non_numeric_valence_is_not_a_flip(bank):
    """The number is authoritative, so it has to survive a malformed one."""
    assert not _fires(bank, _state("despair", "very low", 0.4))
    assert not _fires(bank, {"mood": "despair", "affect": {"surface": "sad"}})
