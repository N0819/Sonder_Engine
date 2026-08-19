"""What `mapping_stage` stores, and what it must not.

The retrieved candidate list is the engine's own working set. Storing it back
on the step made it durable content -- riding every checkpoint, branch, archive
and trace, and re-read on every rerun's hydration -- for no reader at all.
"""

from __future__ import annotations

import agents.mapping as mapping
from core.pipeline_context import ChatData, PipelineContext, TurnData


def _ctx(temp_db):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Mapping", "a quiet street", 0.0))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Mapping", persona_id=None,
                      lorebook_id=None, scenario="a quiet street",
                      created=0.0),
        turn=TurnData(id=1, chat_id=chat_id, idx=1, player_input="look",
                      created=0.0),
        cast=[], input="look")
    ctx["director_interpret"] = {"flow": {}}
    return ctx


def test_the_retrieved_candidate_list_is_not_stored_on_the_step(
        temp_db, monkeypatch):
    monkeypatch.setattr(
        mapping, "search_lore",
        lambda weights, query, k=14, exclude_categories=None: [
            {"id": 11, "content": "x" * 4000, "keys": "street"}])
    monkeypatch.setattr(
        mapping, "_agent_json",
        lambda *a, **kw: {"relevant_lore": [], "relevant_books": []})

    out = mapping.mapping_stage(_ctx(temp_db), 0)

    # `common.lore_for` is the only consumer of a stored mapping step and it
    # reads `relevant_lore`. The cited entries were already joined from this
    # same in-memory list, so nothing is lost by not persisting it.
    assert "candidates" not in out
    assert "relevant_lore" in out
