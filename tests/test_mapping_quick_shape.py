"""The cached-recall path returns the same scene-patch shape as the full one.

`mapping_stage` runs `common._normalize_scene_patch` over the model's patch;
`mapping_quick` hand-wrote the same dictionary and was already one field
behind. Nothing broke, because every consumer spells the read
`diff.get("remove_adjacent") or []` -- which is exactly why the drift could
survive, and why the next field would go missing the same way.
"""

from __future__ import annotations

import agents.mapping as mapping
from agents.common import _normalize_scene_patch
from core.pipeline_context import ChatData, PipelineContext, TurnData


def _ctx(temp_db):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Quick", "", 0.0))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Quick", persona_id=None,
                      lorebook_id=None, scenario="", created=0.0),
        turn=TurnData(id=1, chat_id=chat_id, idx=1, player_input="look around",
                      created=0.0),
        cast=[], input="look around")
    ctx["director_interpret"] = {"flow": {}}
    return ctx


def test_the_quick_path_patch_carries_every_normalized_key(temp_db):
    out = mapping.mapping_quick(_ctx(temp_db), 0)
    assert out["cached"] is True
    assert set(out["scene_patch"]) == set(_normalize_scene_patch({}))
    assert out["scene_patch"]["remove_adjacent"] == []
