"""A finished off-screen beat at index 0 is not an unfinished opening.

The run plans an idx-0 turn as an opening only when it is not a bubble's own
beat (`_run_pipeline`: `idx == 0 and not is_offscreen_beat(...)`), because a
world stood up with no player has a bubble's first beat at index 0. Resume did
not ask the same question: `resume_key_for_turn` built the ESTABLISHMENT plan
for every idx-0 turn, found no `director_establish` row on a complete
off-screen beat, and reported it as the resume point -- so the drawer offered
Resume, `_require_turn_resolved` answered 409 to every new turn in that frame
while the beat was its latest, and the Resume itself raised "not in this
turn's plan" after rewinding (audit of 2026-11-01, agents_runtime_loops_
mapping F12, reproduced).
"""

from __future__ import annotations

import time

import agents.offscreen_beat as offscreen_beat
import agents.runtime as runtime
from agents.storage import save_step


def _beat(db):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Bubble", "", time.time()))
    tid = db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, 0, "", time.time()))
    return cid, tid


def test_a_complete_off_screen_beat_at_index_0_has_nothing_to_resume(
        temp_db, monkeypatch):
    import extension_runtime
    monkeypatch.setattr(extension_runtime, "apply_plan_splices",
                        lambda plan, chat_id=None: plan)
    monkeypatch.setattr(offscreen_beat, "is_offscreen_beat",
                        lambda chat_id, turn_row: True)
    cid, tid = _beat(temp_db)
    # the steps the OFF-SCREEN plan writes (build_plan(..., offscreen=True))
    for n, key in enumerate(["director_interpret", "compile_world_context",
                             "perception_act", "director_resolve",
                             "background_react", "perception_outcome",
                             "commit"]):
        save_step(tid, key, key, n,
                  {"flow": {}} if key == "director_interpret" else {"ok": True})
    assert runtime.resume_key_for_turn(tid, cid) is None


def test_an_opening_at_index_0_still_resumes_from_its_own_plan(
        temp_db, monkeypatch):
    import extension_runtime
    monkeypatch.setattr(extension_runtime, "apply_plan_splices",
                        lambda plan, chat_id=None: plan)
    monkeypatch.setattr(offscreen_beat, "is_offscreen_beat",
                        lambda chat_id, turn_row: False)
    cid, tid = _beat(temp_db)
    save_step(tid, "compile_world_context", "compile", 0, {"ok": True})
    assert runtime.resume_key_for_turn(tid, cid) == "director_establish"
