"""A reactor written by name in a stored interpretation is planned, never a
crash.

`build_plan` and `reaction_loop` read `flow.reactors` with `int(char_id)`. The
model path normalises the list (`director.py`), but the step-edit route
stores any JSON, so an edited interpretation holding `"reactors": ["Ann"]`
raised `ValueError` in every replan -- every resume and rerun, and
`resume_key_for_turn` under `_require_turn_resolved`, which answered 500 to
the new-turn route for that frame (audit of 2026-11-01,
agents_runtime_loops_mapping F13). `interaction_loop` already read the list
through `normalize_character_refs`; the other two readers now do too.
"""

from __future__ import annotations

import json
import time

from story.character_schema import default_character_data


def _cast(db):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Names", "", time.time()))
    ids = {}
    for name in ("Ann", "Bob"):
        char_id = db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (name, json.dumps(default_character_data(name)), "{}",
             time.time(), f"char_{name.lower()}"))
        db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
              "VALUES(?,?,?,?)", (cid, char_id, "active", "{}"))
        ids[name] = char_id
    rows = db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (cid,))
    return cid, ids, rows


def test_a_name_in_the_stored_reactors_plans_its_character(temp_db):
    from agents.runtime import build_plan
    _cid, ids, rows = _cast(temp_db)
    keys = [key for key, _ in build_plan(
        {"flow": {"reactors": ["Ann", str(ids["Bob"]), "Nobody"]}}, rows)]
    # with no chat to read autonomy from, the planner names each reactor
    assert [k for k in keys if k.startswith("character:")] == [
        f"character:{ids['Ann']}", f"character:{ids['Bob']}"]


def test_the_reaction_phase_reads_a_name_too(temp_db, monkeypatch):
    from agents import loops
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    cid, ids, rows = _cast(temp_db)
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Names", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=1, chat_id=cid, idx=1, player_input="",
                      created=time.time()),
        cast=rows, input="",
        director_interpret={"flow": {
            "reactors": ["Ann"],
            "resolution_flags": {"contested": True}}})
    monkeypatch.setattr(loops, "reaction_config",
                        lambda chat_id: {"enabled": True, "max_reactors": 6})
    monkeypatch.setattr(loops, "widen_reactors_to_acted_upon",
                        lambda chat_id, cast, interp, reactors: list(reactors))
    seen = {}

    def gate(ctx_, reactor_ids):
        seen["ids"] = list(reactor_ids)
        return []

    monkeypatch.setattr(loops, "_drop_non_awake", gate)
    out = loops.reaction_loop(ctx, 0)
    assert seen["ids"] == [ids["Ann"]]
    assert out["stop_reason"] == "no reactors"
