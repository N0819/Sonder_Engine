"""The plan is not stable across the turn's own commit.

`build_plan`'s consciousness gate reads `awareness_map` live, and
`director_resolve` merges condition endings that commit persists -- so the
reactor set depends on state the same turn writes. `_run_pipeline` is safe by
ordering (it restores the pre-turn checkpoint before building the plan);
`resume_key_for_turn` runs from web handlers against the live world and had no
such protection.
"""

from __future__ import annotations

import json
import time

from agents.runtime import resume_key_for_turn
from agents.storage import save_step
from story.character_schema import default_character_data


TAIL = ["director_resolve", "background_react", "perception_outcome",
        "narrator", "commit"]


def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Drift", "", time.time()))


def _turn(db, chat_id, idx=1):
    return db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, idx, "shake them awake", time.time()))


def _cast_member(db, chat_id, name="Sleeper"):
    char_id = db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (name, json.dumps(default_character_data(name)), "{}",
         time.time(), f"char_{name.lower()}"))
    db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
          "VALUES(?,?,?,?)", (chat_id, char_id, "active", "{}"))
    return char_id


def _seed(db, turn_id, char_id, keys):
    interp = {"flow": {"needs_mapping": False, "reactors": [char_id],
                       "resolution_flags": {"contested": False}}}
    for ordn, key in enumerate(keys):
        save_step(turn_id, key, key, ordn,
                  interp if key == "director_interpret" else {"ok": True})


def test_a_step_the_plan_gained_after_the_run_is_not_a_resume_point(temp_db):
    chat_id = _chat(temp_db)
    char_id = _cast_member(temp_db, chat_id)
    turn_id = _turn(temp_db, chat_id)

    # The turn as it ACTUALLY ran: the reactor was asleep, so the gate emptied
    # the reactor set and no interaction_loop was planned. Everything else ran,
    # commit included. The rouse is now persisted, so recomputing the plan here
    # -- against the live, un-restored world -- produces an interaction_loop.
    _seed(temp_db, turn_id, char_id,
          ["director_interpret", "mapping_quick", "perception_act"] + TAIL)

    assert resume_key_for_turn(turn_id, chat_id) is None


def test_an_interrupted_turn_still_reports_where_to_resume(temp_db):
    chat_id = _chat(temp_db)
    char_id = _cast_member(temp_db, chat_id)
    turn_id = _turn(temp_db, chat_id)

    # Stopped after the interaction loop: the whole tail is missing, so the run
    # plainly did not finish without it.
    _seed(temp_db, turn_id, char_id,
          ["director_interpret", "mapping_quick", "perception_act",
           "interaction_loop"])

    assert resume_key_for_turn(turn_id, chat_id) == "director_resolve"


def test_a_turn_that_never_committed_resumes_at_commit(temp_db):
    chat_id = _chat(temp_db)
    char_id = _cast_member(temp_db, chat_id)
    turn_id = _turn(temp_db, chat_id)

    # The missing step is the LAST one, so there are no successors to prove the
    # run finished without it. A tail is an interrupted turn, never drift.
    _seed(temp_db, turn_id, char_id,
          ["director_interpret", "mapping_quick", "perception_act",
           "interaction_loop"] + TAIL[:-1])

    assert resume_key_for_turn(turn_id, chat_id) == "commit"


def test_a_stale_step_is_still_a_resume_point(temp_db):
    chat_id = _chat(temp_db)
    char_id = _cast_member(temp_db, chat_id)
    turn_id = _turn(temp_db, chat_id)
    _seed(temp_db, turn_id, char_id,
          ["director_interpret", "mapping_quick", "perception_act",
           "interaction_loop"] + TAIL)
    temp_db.qi("UPDATE steps SET stale=1 WHERE turn_id=? AND key=?",
               (turn_id, "narrator"))

    assert resume_key_for_turn(turn_id, chat_id) == "narrator"
