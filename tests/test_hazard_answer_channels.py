"""The hazard floor reads the vocabulary this module wrote down (E30).

`world/mechanics.py` names `_HAZARD_ANSWER_CHANNELS` as "the whole vocabulary
the engine has for something happened to this body", and `_answered_bodies`
spelled the same four channels out for itself instead of reading it -- two
representations free to disagree, and a fifth channel added to the constant
would have reached neither floor. This walks the constant so the two cannot
drift apart again: every subject channel in it must answer for the body it
names, and the whole-beat channel must answer for everybody.

Found by the 2026-09-07 review, Section E (stale statements), row E30.
"""

from __future__ import annotations

import pytest

from world.mechanics import (_HAZARD_ANSWER_CHANNELS,
                             _HAZARD_WHOLE_BEAT_CHANNEL,
                             unanswered_hazard_subjects)

SUBJECT_CHANNELS = [c for c in _HAZARD_ANSWER_CHANNELS
                    if c != _HAZARD_WHOLE_BEAT_CHANNEL]


def _burning_landing():
    # The hazard is stated where B8 put it -- an active condition over the
    # room with a declared severity -- not as a `hazard` block on the room,
    # which `_hazard_rooms` no longer reads (one store per question).
    return {
        "rooms": {"second_landing": {"name": "Second Landing"}},
        "positions": {"Mirela": "second_landing"},
    }


_FIRE = [{"subject_id": "second_landing", "kind": "fire",
          "payload": {"severity": 0.9, "cause": "the bakery"}}]


def test_the_constant_is_not_empty_and_names_its_whole_beat_channel():
    assert _HAZARD_WHOLE_BEAT_CHANNEL in _HAZARD_ANSWER_CHANNELS
    assert SUBJECT_CHANNELS


def test_a_beat_with_no_answer_at_all_reports_the_body():
    assert unanswered_hazard_subjects(
        _burning_landing(), _FIRE, None, {}) == ["Mirela"]


@pytest.mark.parametrize("channel", SUBJECT_CHANNELS)
def test_every_subject_channel_in_the_vocabulary_answers(channel):
    """A channel the constant names must be one the floor actually reads."""
    diff = {channel: {"Mirela": {"note": "the world acted"}}}
    assert unanswered_hazard_subjects(
        _burning_landing(), _FIRE, None, diff) == []


def test_the_whole_beat_channel_answers_for_everybody():
    """A roll contests something, so it answers for a body it never names."""
    diff = {_HAZARD_WHOLE_BEAT_CHANNEL: [{"what": "the stair",
                                          "result": "partial"}]}
    assert unanswered_hazard_subjects(
        _burning_landing(), _FIRE, None, diff) == []


def test_a_channel_outside_the_vocabulary_is_not_an_answer():
    """The floor is about the world ACTING on a body; a change of clothes
    is not that, and widening the constant is how a channel joins."""
    diff = {"attire": {"Mirela": {"coat": "off"}}}
    assert unanswered_hazard_subjects(
        _burning_landing(), _FIRE, None, diff) == ["Mirela"]
