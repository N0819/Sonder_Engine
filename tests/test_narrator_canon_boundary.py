import time

import commit
from pipeline_context import ChatData, PipelineContext, TurnData


def test_narrator_specifics_are_audit_flags_not_canon_inputs(temp_db):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "look", time.time()),
    )
    ctx = PipelineContext(
        chat=ChatData(
            id=chat_id, name="Test", persona_id=None, lorebook_id=None,
            scenario="", created=time.time(),
        ),
        turn=TurnData(
            id=turn_id, chat_id=chat_id, idx=1, player_input="look",
            created=time.time(),
        ),
        cast=[], input="look",
    )
    ctx.director_resolve = {
        "summary": "Nothing changes.",
        "resolved_event": "The player looks around.",
        "state_diff": {},
    }
    ctx.narrator = {
        "prose": "A silver moon called Vael hangs overhead.",
        "new_specifics": ["The moon is named Vael"],
    }

    prepared = commit.prepare_mapping_commit(ctx)

    assert prepared["skipped"] is True
    assert any("excluded from canon" in warning for warning in ctx.warnings)
    assert temp_db.q("SELECT * FROM lore_entries") == []
