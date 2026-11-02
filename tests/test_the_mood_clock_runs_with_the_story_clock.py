"""A beat's own span of story time passes on the mood's clock: the mood
relaxes toward home over it and a recalled memory's habituation rests.

The mood pass (`mind/affect_pass.py`) runs inside the character call at the
START of a beat and decays the carried mood over
`elapsed_psych_units(active.affect_seconds, clock now)`. The commit stamps
`affect_seconds` with the clock at the END of the beat -- and the next
beat's call reads the clock before anything has advanced it, so the two
numbers are the same and 0 units pass, every beat; the commit then copied
the pass's `mood_clock` back unchanged. Measured by lane L9 on the owner's
db (2026-11-01): chats 175-178, every mind at `mood_clock 1.0` after 12-35
turns while the story clock reached 440-1143 s -- the mood never decayed
toward home, habits never rested, lived memories never faded. The commit
now advances the mood over the beat's own span (the stored clock it opened
on to the clock it ends on), which no call ever counts.
"""

from __future__ import annotations

import json
import time

from core.pipeline_context import ChatData, PipelineContext, TurnData
from mind import affect_mix as mix
from persist import commit
from story.character_schema import default_character_data

START = 1000.0
MOOD = {"pleasure": -0.6, "tension": 0.7, "energy": 0.4}
HABITS = {"m1": {"h": 0.4, "at": 3.0}}


def _ctx(temp_db, minutes):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()))
    prior = {"affect_seconds": START, "affect_turn": 1,
             "mood_coords": dict(MOOD), "mood_habits": dict(HABITS),
             "mood_clock": 3.0}
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Alice", json.dumps(default_character_data("Alice")), "{}",
         time.time(), "char_alice"))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active",
         json.dumps({"active_state": prior})))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 2, "test", time.time()))
    temp_db.wset(chat_id, "simulation_clock",
                 {"elapsed_seconds": START, "display": "now"})
    temp_db.wset(chat_id, "scene", {
        "rooms": {"kitchen": {"name": "Kitchen"}},
        "positions": {"Alice": "kitchen"},
        "entities": {}, "attire": {}, "overlays": {}})
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=2,
                      player_input="test", created=time.time()),
        cast=cast, input="test")
    ctx.director_resolve = {
        "summary": "s", "resolved_event": "e", "dialogue_log": [],
        "state_diff": {"time": {"duration_seconds": minutes * 60}}}
    ctx.perception_outcome = {"views": {str(char_id): "Alice sees."}}
    # What the pass handed on at the START of the beat: the clock had not
    # moved, so nothing decayed -- the mood as it was.
    ctx.character_results = {char_id: {
        "sequence": [], "appraisal": {"goal_impacts": []},
        "active_state": {"wants": []},
        "_affect_pass": {"mood_coords": dict(MOOD),
                         "mood_habits": dict(HABITS), "mood_clock": 3.0}}}
    return ctx, char_id


def _kept(ctx, char_id):
    prepared = commit.prepare_memory_commit(ctx)
    for _chat, cid, state_json in prepared["state_updates"]:
        if cid == char_id:
            return json.loads(state_json)["active_state"]
    raise AssertionError("no state update for the character")


def test_ten_minutes_of_story_relax_the_mood_toward_home(temp_db):
    ctx, char_id = _ctx(temp_db, minutes=10)
    kept = _kept(ctx, char_id)
    assert kept["mood_clock"] == 13.0, kept.get("mood_clock")
    assert abs(kept["mood_coords"].get("tension", 0.0)) < MOOD["tension"]
    assert kept["mood_coords"].get("pleasure", 0.0) > MOOD["pleasure"]


def test_ten_minutes_rest_a_recalled_memorys_habituation(temp_db):
    ctx, char_id = _ctx(temp_db, minutes=10)
    kept = _kept(ctx, char_id)
    _m, then = mix.recall_lands(HABITS, "m1", 3.0)
    _m, now = mix.recall_lands(kept["mood_habits"], "m1", kept["mood_clock"])
    assert now["m1"]["h"] < then["m1"]["h"], (now, then)


def test_a_beat_that_takes_no_time_moves_nothing(temp_db):
    ctx, char_id = _ctx(temp_db, minutes=0)
    kept = _kept(ctx, char_id)
    assert kept["mood_clock"] == 3.0
    assert kept["mood_coords"] == MOOD
