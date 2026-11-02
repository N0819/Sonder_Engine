"""A cast row's carried normalization is built on the first question, not before.

`sheet_state` hands back the card as stored carrying its normalization
(`CardWithNormalization`), and `stored_card_from_text` built that
normalization EAGERLY -- a deep copy of the memoised product on every call,
1.23 ms per call at a 40 KB card, 0.77 ms of it the copy, whether or not the
caller ever asked a normalized question (story_scene_schema audit E3). Most of
the fourteen call sites read only `cstate`'s mood and stance, which a
committed character always carries.

It is built now on the first `normalize_character_data(card)`, once per card,
and is the same object every later ask returns.
"""

from __future__ import annotations

import copy
import json

from story import character_schema, scene
from story.character_schema import normalize_character_data


_CARD = {"identity": {"name": "Kit", "uid": "char_lazy"},
         "psychology": {"drive": {"essence": "to be let back in"}}}
_STATE = {"active_state": {"mood": "wary", "goal": "get out"},
          "stance": {"axes": {"trust_player": 0.5}}}


def _counting(monkeypatch):
    calls = []
    real = character_schema.normalized_character_from_text
    monkeypatch.setattr(character_schema, "normalized_character_from_text",
                        lambda text: calls.append(text) or real(text))
    return calls


def test_reading_a_committed_row_builds_no_normalization(monkeypatch):
    calls = _counting(monkeypatch)
    card, active, stance = scene.sheet_state(
        {"sheet": json.dumps(_CARD), "cstate": json.dumps(_STATE)})
    assert calls == []
    assert active == _STATE["active_state"] and stance == _STATE["stance"]
    assert dict(card) == _CARD


def test_the_first_question_builds_it_once(monkeypatch):
    calls = _counting(monkeypatch)
    card, _a, _s = scene.sheet_state(
        {"sheet": json.dumps(_CARD), "cstate": json.dumps(_STATE)})
    first = normalize_character_data(card)
    assert len(calls) == 1
    assert normalize_character_data(card) is first is card.normalized
    assert len(calls) == 1
    assert first["identity"]["name"] == "Kit"


def test_a_copy_of_the_card_still_answers(monkeypatch):
    card, _a, _s = scene.sheet_state(
        {"sheet": json.dumps(_CARD), "cstate": json.dumps(_STATE)})
    deep = copy.deepcopy(card)
    assert normalize_character_data(deep) == normalize_character_data(card)
    assert dict(deep) == _CARD
