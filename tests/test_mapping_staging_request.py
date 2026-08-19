"""Two questions about `flow.mapping_request`, one vocabulary.

`runtime._mapping_must_precede_perception` decides whether mapping runs BEFORE
perception; `mapping.mapping_quick` decides whether cached recall may serve at
all. They were two hand-written phrase lists that had already drifted apart by
one entry, so a request saying "new location" serialized mapping and never
escalated it -- and perception's room-notes fallback then read a place nothing
had staged.
"""

from __future__ import annotations

import agents.mapping as mapping
from agents.mapping import (STAGING_REQUEST_PHRASES,
                            mapping_request_stages_a_room)
from agents.runtime import _mapping_must_precede_perception
from core.pipeline_context import ChatData, PipelineContext, TurnData


def _ctx(request):
    ctx = PipelineContext(
        chat=ChatData(id=1, name="", persona_id=None, lorebook_id=None,
                      scenario="", created=0.0),
        turn=TurnData(id=1, chat_id=1, idx=1, player_input="", created=0.0),
        cast=[], input="")
    ctx["director_interpret"] = {"flow": {"mapping_request": request}}
    return ctx


def test_every_phrase_answers_both_questions_the_same_way(monkeypatch):
    escalated = []
    monkeypatch.setattr(mapping, "mapping_stage",
                        lambda ctx, nonce: escalated.append(nonce) or {})

    for phrase in STAGING_REQUEST_PHRASES:
        request = f"the player walks somewhere -- {phrase} needed"
        assert mapping_request_stages_a_room(request), phrase
        assert _mapping_must_precede_perception(_ctx(request)), phrase
        escalated.clear()
        mapping.mapping_quick(_ctx(request), 3)
        assert escalated == [3], phrase


def test_an_ordinary_request_neither_serializes_nor_escalates():
    request = "recall what the tavern's regulars are called"
    assert not mapping_request_stages_a_room(request)
    assert not _mapping_must_precede_perception(_ctx(request))


def test_the_match_is_case_insensitive_and_null_tolerant():
    assert mapping_request_stages_a_room("Generate Room for the cellar")
    assert not mapping_request_stages_a_room(None)
    assert not mapping_request_stages_a_room("")
