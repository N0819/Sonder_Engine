"""A SLEEPER RECOVERS STAMINA THROUGH THE COMMIT (UNBUILT_WORLD 1.218, closed
2026-10-20).

`tests/test_world_model_sleep_recovery.py` pins the `sleeping=` seam of
`merge_scene_with_diff`; this pins the caller that feeds it. The commit built
its sleeper set as `{subject for subject, level in awareness_map(cid).items()
if level == "asleep"}` -- but `awareness_map` maps a name to a RECORD, never
to a level string, so the comparison was never true, the set was empty on
every beat, and the recovery branch the seam was wired for was unreachable
again. Found by wave B1 verifying what wakes a sleeper.
"""

from __future__ import annotations

import inspect
import json

from persist.commit import compose_beat_scene, sleepers_of
from story.scene import awareness_map


def _chat(temp_db):
    import time
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        ("Mora", "{}", "{}"))
    return temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("The cell", "", time.time(), persona_id))


def _condition(temp_db, chat_id, subject, level):
    cond = f"cond_aware_{subject.casefold()}"
    temp_db.qi(
        "INSERT INTO world_conditions(condition_id,chat_id,subject_id,kind,"
        "started_at,expires_at,next_tick,payload,active) VALUES(?,?,?,?,?,?,?,?,?)",
        (cond, chat_id, subject, "awareness", 0.0, None, None,
         json.dumps({"condition_id": cond, "subject_id": subject,
                     "kind": "awareness",
                     "state": {"level": level, "cause": "the night"}}), 1))


def test_the_commit_reads_the_record_not_the_map_value(temp_db):
    """On the real `awareness_map` shape, the sleeper is found by the
    subject's own spelling; a body struck unconscious is not a sleeper."""
    chat_id = _chat(temp_db)
    _condition(temp_db, chat_id, "Mora", "asleep")
    _condition(temp_db, chat_id, "Dr. Moon", "unconscious")
    amap = awareness_map(chat_id)
    assert isinstance(amap["mora"], dict), "the map's value is a record"
    assert sleepers_of(amap) == {"Mora"}
    # The pre-fix comparison, on the same map, answered nobody.
    assert {s for s, level in amap.items() if level == "asleep"} == set()


def test_the_older_shape_is_read_too():
    assert sleepers_of({"mora": "asleep", "jin": "dazed"}) == {"mora"}
    assert sleepers_of({}) == set() and sleepers_of(None) == set()


def test_the_beat_composition_feeds_the_seam_from_it():
    """The commit's sleeper set is this function's answer, and it reaches
    `merge_scene_with_diff(sleeping=)`."""
    body = inspect.getsource(compose_beat_scene)
    assert "_sleeping = sleepers_of(awareness_map(cid))" in body
    assert "sleeping=_sleeping" in body
